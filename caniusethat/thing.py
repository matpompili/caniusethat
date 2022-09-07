import pickle
import types
from typing import Any, Callable, List

import zmq

from caniusethat._logging import getLogger
from caniusethat._types import (
    RemoteProcedureCall,
    RemoteProcedureError,
    RemoteProcedureResponse,
    SharedMethodDescriptor,
)

_logger = getLogger(__name__)


def _validate_rpc_response(response: bytes) -> Any:
    """Validates the response from the server.

    Args:
        response: The response from the server.

    Returns:
        The result of the RPC call, or raises an exception if the response is invalid.

    Raises:
        RuntimeError: If the response is invalid or if the response is an error."""
    result = pickle.loads(response)
    if not isinstance(result, RemoteProcedureResponse):
        raise RuntimeError(f"Received invalid RemoteProcedureResponse: {result}")
    if result.error != RemoteProcedureError.NO_ERROR:
        raise RuntimeError(f"Remote procedure error: {result}")
    else:
        return result.result


def _make_rpc_and_validate_response(
    socket: zmq.Socket, name: str, method: str, *args, **kwargs
) -> Any:
    rpc_pickle = pickle.dumps(RemoteProcedureCall(name, method, args, kwargs))
    socket.send(rpc_pickle)
    return _validate_rpc_response(socket.recv())


class Thing:
    """A representation of a remote object, or `thing`, that has methods that can be called.

    Attributes:
        name: The unique name of the remote object.
        server_address: The address of the server that is hosting the remote object.

    Example:
        >>> from caniusethat import thing
        >>> my_thing = thing.Thing("remote_calculator", "tcp://127.0.0.1:6555")
        >>> my_thing.add(2, 3)
        5
    """

    _RESERVED_NAMES = ["available_methods", "close_this_thing"]

    def __init__(self, name: str, server_address: str) -> None:
        self.name = name
        context = zmq.Context.instance()
        self.request_socket: zmq.Socket = context.socket(zmq.REQ)
        self.request_socket.connect(server_address)
        _logger.info(f"Connecting to 👀 CanIUseThat server at {server_address}")
        self._methods = self._get_object_description_from_server()
        self._populate_methods_from_description()

        self._closed = False

    @staticmethod
    def _make_method_fn(name: str) -> Callable:
        return lambda _self, *args, **kwargs: _make_rpc_and_validate_response(
            _self.request_socket, _self.name, name, *args, **kwargs
        )

    # def _call_remote_server_method(self, method_name: str, *args, **kwargs) -> Any:
    #     """A helper method that calls a remote server method with the given name and arguments."""
    #     rpc_pickle = pickle.dumps(
    #         RemoteProcedureCall("_server", method_name, args, kwargs)
    #     )
    #     self.request_socket.send(rpc_pickle)
    #     return _validate_rpc_response(self.request_socket.recv())

    # def _call_remote_method(self, method_name: str, *args, **kwargs) -> Any:
    #     """A helper method that calls a remote method with the given name and arguments."""
    #     rpc_pickle = pickle.dumps(
    #         RemoteProcedureCall(self.name, method_name, args, kwargs)
    #     )
    #     self.request_socket.send(rpc_pickle)
    #     return _validate_rpc_response(self.request_socket.recv())

    def _get_object_description_from_server(self) -> List[SharedMethodDescriptor]:
        """Gets the description of the remote object from the server."""
        object_description = _make_rpc_and_validate_response(
            self.request_socket, "_server", "get_object_methods", self.name
        )
        if not isinstance(object_description, list):
            raise RuntimeError(
                f"Received invalid RemoteProcedureResponse: {object_description}"
            )
        for method_descriptor in object_description:
            if not isinstance(method_descriptor, SharedMethodDescriptor):
                raise RuntimeError(
                    f"Received invalid RemoteProcedureResponse: {object_description}"
                )
        return object_description

    def _populate_methods_from_description(self) -> None:
        """Populates the methods of this object from the description of the remote object."""
        for (name, signature, docstring) in self._methods:
            if name in self._RESERVED_NAMES:
                raise RuntimeError(
                    f"Method name `{name}` is reserved for internal use, please change it in the remote class."
                )
            _logger.debug(f"Adding method {name}({signature})")
            method_fn = self._make_method_fn(name)
            method_fn.__name__ = name
            method_fn.__signature__ = signature  # type: ignore
            method_fn.__doc__ = signature + "\n" + docstring
            setattr(self, name, types.MethodType(method_fn, self))

    def available_methods(self) -> List[SharedMethodDescriptor]:
        """Returns a list of the available methods of this object."""
        return self._methods

    def close_this_thing(self) -> None:
        """Closes the connection to the remote object and server, releasing
        any locks if any are still held."""
        if not self._closed:
            _logger.info("Closing connection to 👀 CanIUseThat server")
            _ = _make_rpc_and_validate_response(
                self.request_socket, "_server", "release_lock_if_any", self.name
            )
            self._closed = True
            self.request_socket.close()
        else:
            RuntimeError("Connection to 👀 CanIUseThat server already closed.")
