import pickle
import types
from typing import Any, Callable, List

import zmq

from caniusethat.logging import getLogger
from caniusethat.types import (
    RemoteProcedureCall,
    RemoteProcedureError,
    RemoteProcedureResponse,
    SharedMethodDescriptor,
)

_logger = getLogger(__name__)


class Thing:
    def __init__(self, name: str, server_address: str) -> None:
        self.name = name
        context = zmq.Context.instance()
        self.request_socket = context.socket(zmq.REQ)
        self.request_socket.connect(server_address)
        _logger.info(f"Connecting to server at {server_address}")
        self._methods = self._get_object_description_from_server()
        self._populate_methods_from_description()

    def _get_object_description_from_server(self) -> List[SharedMethodDescriptor]:
        rpc_pickle = pickle.dumps(
            RemoteProcedureCall("_server", "get_object_methods", (self.name,))
        )
        self.request_socket.send(rpc_pickle)
        result = pickle.loads(self.request_socket.recv())
        if not isinstance(result, RemoteProcedureResponse):
            raise RuntimeError(f"Received invalid RemoteProcedureResponse: {result}")
        if result.error != RemoteProcedureError.NO_ERROR:
            raise RuntimeError(f"Remote procedure error: {result}")
        if not isinstance(result.result, list):
            raise RuntimeError(f"Received invalid RemoteProcedureResponse: {result}")
        return result.result

    def _populate_methods_from_description(self) -> None:
        for (name, signature, docstring) in self._methods:
            _logger.info(f"Adding method {name}({signature})")
            method_fn = self._make_method_fn(name)
            method_fn.__name__ = name
            method_fn.__signature__ = signature  # type: ignore
            method_fn.__doc__ = signature + "\n" + docstring
            setattr(self, name, types.MethodType(method_fn, self))

    @staticmethod
    def _make_method_fn(name: str) -> Callable:
        return lambda _self, *args, **kwargs: _self._call_remote_method(
            name, *args, **kwargs
        )

    def _call_remote_method(self, method_name: str, *args, **kwargs) -> Any:
        rpc_pickle = pickle.dumps(
            RemoteProcedureCall(self.name, method_name, args, kwargs)
        )
        self.request_socket.send(rpc_pickle)
        result = pickle.loads(self.request_socket.recv())
        if not isinstance(result, RemoteProcedureResponse):
            raise RuntimeError(f"Received invalid RemoteProcedureResponse: {result}")
        if result.error != RemoteProcedureError.NO_ERROR:
            raise RuntimeError(f"Remote procedure error: {result}")
        return result.result

    def available_methods(self) -> List[SharedMethodDescriptor]:
        return self._methods

    def __del__(self) -> None:
        _logger.info(f"Closing connection to server")
        rpc_pickle = pickle.dumps(
            RemoteProcedureCall("_server", "release_lock_if_any", (self.name,))
        )
        self.request_socket.send(rpc_pickle)
        result = pickle.loads(self.request_socket.recv())
        if not isinstance(result, RemoteProcedureResponse):
            raise RuntimeError(f"Received invalid RemoteProcedureResponse: {result}")
        if result.error != RemoteProcedureError.NO_ERROR:
            raise RuntimeError(f"Remote procedure error: {result}")
