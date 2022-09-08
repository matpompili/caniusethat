import pickle
import types
from typing import Any, Callable, List

import zmq
from zmq.utils.win32 import allow_interrupt

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


class Thing:
    """A representation of a remote object, or `thing`, that has methods that can be called.

    Attributes:
        name: The unique name of the remote object.
        server_address: The address of the server that is hosting the remote object.
        request_timeout: The timeout in seconds for requests to the server. If no
            response is received within this time, an exception is raised. Defaults to 1 s.

    Example:
        >>> from caniusethat import thing
        >>> my_thing = thing.Thing("remote_calculator", "tcp://127.0.0.1:6555")
        >>> my_thing.add(2, 3)
        5
    """

    _RESERVED_NAMES = ["available_methods", "close_this_thing"]
    _LINGER_TIME = 1000

    def __init__(
        self, name: str, server_address: str, request_timeout: float = 1.0
    ) -> None:
        self.name = name
        self.request_timeout = request_timeout

        _logger.info(f"Connecting to 👀 CanIUseThat server at {server_address}...")
        context = zmq.Context.instance()
        self.request_socket: zmq.Socket = context.socket(zmq.REQ)
        self.request_socket.connect(server_address)
        self.poller = zmq.Poller()
        self.poller.register(self.request_socket, zmq.POLLIN)

        self._methods = self._get_object_description_from_server()
        self._populate_methods_from_description()

        self._closed = False

    def _make_method_fn(self, name: str) -> Callable:
        return lambda _self, *args, **kwargs: self._make_rpc_and_validate_response(
            _self.name, name, *args, **kwargs
        )

    def _socket_receive(self) -> bytes:
        """Receives a message from the server.
        If no message is received within the timeout, an exception is raised."""
        with allow_interrupt(self.close_this_thing):
            socks = dict(self.poller.poll(round(self.request_timeout * 1000)))
            if (
                self.request_socket in socks
                and socks[self.request_socket] == zmq.POLLIN
            ):
                return self.request_socket.recv()
            else:
                raise TimeoutError("Timed out waiting for response from server.")

    def _make_rpc_and_validate_response(
        self, name: str, method: str, *args, **kwargs
    ) -> Any:
        rpc_pickle = pickle.dumps(RemoteProcedureCall(name, method, args, kwargs))
        self.request_socket.send(rpc_pickle)
        return _validate_rpc_response(self._socket_receive())

    def _get_object_description_from_server(self) -> List[SharedMethodDescriptor]:
        """Gets the description of the remote object from the server."""
        object_description = self._make_rpc_and_validate_response(
            "_server", "get_object_methods", self.name
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
            _ = self._make_rpc_and_validate_response(
                "_server", "release_lock_if_any", self.name
            )
            self.poller.unregister(self.request_socket)
            self.request_socket.close(linger=self._LINGER_TIME)
            self._closed = True
        else:
            RuntimeError("Connection to 👀 CanIUseThat server already closed.")
