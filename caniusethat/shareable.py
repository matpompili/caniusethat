import inspect
import logging
import pickle
from functools import wraps
from threading import Lock
from typing import Any, Callable, Dict, List

import zmq
from zmq.utils.win32 import allow_interrupt

from caniusethat._logging import getLogger
from caniusethat._thread import StoppableThread
from caniusethat._types import (
    RemoteProcedureCall,
    RemoteProcedureError,
    RemoteProcedureResponse,
    SharedMethodDescriptor,
    SharedObjectDescriptor,
)

_logger = getLogger(__name__)


def _is_shared_method(obj: Any) -> bool:
    return inspect.ismethod(obj) and hasattr(obj, "_you_can_use_this")


def _is_locking_method(obj: Any) -> bool:
    return inspect.ismethod(obj) and hasattr(obj, "_acquire_lock")


def _is_unlocking_method(obj: Any) -> bool:
    return inspect.ismethod(obj) and hasattr(obj, "_release_lock")


def _dealer_address(name: str) -> str:
    return f"inproc://{name}_worker"


def _force_remote_server_stop(server_address: str) -> Any:
    context = zmq.Context.instance()
    request_socket = context.socket(zmq.REQ)
    request_socket.connect(server_address)

    rpc_pickle = pickle.dumps(RemoteProcedureCall("_server", "stop"))
    request_socket.send(rpc_pickle)
    result = pickle.loads(request_socket.recv())
    request_socket.close(linger=10)
    return result


def _package_reply(reply: Any, error: RemoteProcedureError) -> bytes:
    return pickle.dumps(RemoteProcedureResponse(reply, error))


def _package_error(error: RemoteProcedureError) -> bytes:
    return _package_reply(None, error)


def _package_success_reply(reply: Any) -> bytes:
    return _package_reply(reply, RemoteProcedureError.NO_ERROR)


def you_can_use_this(f: Callable) -> Callable:
    """A decorator that marks a method as a shared method.

    Example:
        >>> @you_can_use_this
        ... def get_name(self) -> str:
        ...     return self.name
    """

    @wraps(f)
    def wrapper(*args, **kwds):
        return f(*args, **kwds)

    wrapper._you_can_use_this = True  # type: ignore
    return wrapper


def acquire_lock(f: Callable) -> Callable:
    """A decorator that acquires the lock of the object before calling the method.

    Example:
        >>> @acquire_lock
        ... @you_can_use_this
        ... def start_phone_call(self, phone_number: str) -> None:
        ...     self._make_phone_call(phone_number)
    """

    @wraps(f)
    def wrapper(*args, **kwds):
        return f(*args, **kwds)

    wrapper._acquire_lock = True  # type: ignore
    return wrapper


def release_lock(f: Callable) -> Callable:
    """A decorator that releases the lock of the object after calling the method.

    Example:
        >>> @release_lock
        ... @you_can_use_this
        ... def stop_phone_call(self) -> None:
        ...     self._hang_up()
    """

    @wraps(f)
    def wrapper(*args, **kwds):
        return f(*args, **kwds)

    wrapper._release_lock = True  # type: ignore
    return wrapper


class Server(StoppableThread):
    """The Server takes care of sharing the objects on the network,
    handling the remote procedure calls from multiple users and their
    locks.

    Attributes:
        router_address (str): The address that the server will listen on.

    Example:
        >>> server = Server("tcp://127.0.0.1:6555")
        >>> server.start()
        >>> server.add_object("mobile_phone_interface", mobile_phone_interface)
    """

    _LINGER_TIME = 1000  # milliseconds

    def __init__(self, router_address: str) -> None:
        super().__init__()
        self.router_address = router_address
        self.shared_objects: Dict[str, SharedObjectDescriptor] = {}
        self.shared_objects_queue: Dict[str, SharedObjectDescriptor] = {}
        self.new_object_lock = Lock()
        self.dealers: Dict[str, Any] = {}
        self.workers: Dict[str, _ObjectWorker] = {}
        self.worker_locks: Dict[str, bytes] = {}

        self.log_lock = Lock()

    def _safe_log(self, message: str, level: int = logging.INFO) -> None:
        with self.log_lock:
            _logger.log(level, message)

    def _task_setup(self):
        self._safe_log(
            f"Starting 👀 caniusethat server, listening on {self.router_address}."
        )
        self.context = zmq.Context.instance()
        self.router_socket = self.context.socket(zmq.ROUTER)
        self.router_socket.bind(self.router_address)

        self.poller = zmq.Poller()
        self.poller.register(self.router_socket, zmq.POLLIN)

    def _task_cleanup(self):
        self._safe_log("Closing 👀 caniusethat server connections.")
        self.poller.unregister(self.router_socket)
        self.router_socket.close(linger=self._LINGER_TIME)

        for dealer_socket in self.dealers.values():
            self.poller.unregister(dealer_socket)
            dealer_socket.close(linger=self._LINGER_TIME)

        for worker in self.workers.values():
            worker.stop()

    def _task_cycle(self):
        # Add any new objects to the shared objects.
        with allow_interrupt(self.stop):
            with self.new_object_lock:
                self._process_new_object_queue()

            poll_sockets = dict(self.poller.poll(timeout=10))

            # Check if there are new requests.
            if poll_sockets.get(self.router_socket) == zmq.POLLIN:
                address, _, message = self.router_socket.recv_multipart()
                self._process_incoming_rpc(address, message)

            # Check if there are any new replies
            for dealer_socket in self.dealers.values():
                if poll_sockets.get(dealer_socket) == zmq.POLLIN:
                    self._safe_log(
                        f"Received reply from worker {dealer_socket}", logging.DEBUG
                    )
                    message = dealer_socket.recv_multipart()
                    # Send the reply back to the client
                    self.router_socket.send_multipart(message)

    def _process_incoming_rpc(self, address: bytes, message: bytes) -> None:
        rpc = pickle.loads(message)

        # Check if the RPC is properly formatted.
        if not isinstance(rpc, RemoteProcedureCall):
            self._safe_log(
                f"Received invalid RemoteProcedureCall: {rpc}", logging.WARNING
            )
            message = _package_error(RemoteProcedureError.INVALID_RPC)
            self.router_socket.send_multipart([address, b"", message])
            return

        self._safe_log(f"Received RPC: {rpc}", logging.DEBUG)

        # Check if the RPC is asking for the list of shared methods.
        if rpc.name == "_server" and rpc.method == "get_object_methods":
            if rpc.args[0] not in self.shared_objects:
                self._safe_log(f"No such object: {rpc.args[0]}", logging.WARNING)
                message = _package_error(RemoteProcedureError.NO_SUCH_THING)
                self.router_socket.send_multipart([address, b"", message])
            else:
                message = _package_success_reply(
                    self.shared_objects[rpc.args[0]].shared_methods
                )
                self.router_socket.send_multipart([address, b"", message])
            return

        # Check if the RPC is asking for the list of shared list.
        if rpc.name == "_server" and rpc.method == "get_object_list":
            message = _package_success_reply(list(self.shared_objects.keys()))
            self.router_socket.send_multipart([address, b"", message])
            return

        # Check if the RPC is asking for the server to terminate (useful in testing).
        if rpc.name == "_server" and rpc.method == "stop":
            message = _package_success_reply(None)
            self.router_socket.send_multipart([address, b"", message])
            self.stop()
            return

        # Check if the RPC is asking for the server to release a lock.
        if rpc.name == "_server" and rpc.method == "release_lock_if_any":
            if self.worker_locks.get(rpc.args[0]) == address:
                self.worker_locks.pop(rpc.args[0])
                self._safe_log(f"Released lock for {rpc.args[0]}", logging.DEBUG)

            message = _package_success_reply(None)
            self.router_socket.send_multipart([address, b"", message])
            return

        # Check if the RPC is asking for the server to release a lock forcefully.
        if rpc.name == "_server" and rpc.method == "force_release_lock":
            if rpc.args[0] in self.worker_locks:
                self.worker_locks.pop(rpc.args[0])
                self._safe_log(
                    f"Forcefully released lock for {rpc.args[0]}", logging.WARNING
                )

            message = _package_success_reply(None)
            self.router_socket.send_multipart([address, b"", message])
            return

        # Check if the RPC object is in the server.
        if rpc.name not in self.shared_objects:
            self._safe_log(
                f"Received RPC for unknown object: {rpc.name}", logging.WARNING
            )
            message = _package_error(RemoteProcedureError.NO_SUCH_THING)
            self.router_socket.send_multipart([address, b"", message])
            return

        # Check if the RPC method is not one of the shared ones.
        if rpc.method not in [
            method.name for method in self.shared_objects[rpc.name].shared_methods
        ]:
            self._safe_log(
                f"Received RPC for unknown method: {rpc.name}.{rpc.method}",
                logging.WARNING,
            )
            message = _package_error(RemoteProcedureError.NO_SUCH_METHOD)
            self.router_socket.send_multipart([address, b"", message])
            return

        # Check if the worker has a lock.
        if (rpc.name in self.worker_locks) and (self.worker_locks[rpc.name] != address):
            self._safe_log(
                f"Worker {rpc.name} is already locked by {str(self.worker_locks[rpc.name])}",
                logging.WARNING,
            )
            message = _package_error(RemoteProcedureError.THING_IS_LOCKED)
            self.router_socket.send_multipart([address, b"", message])
            return

        # Check if the worker needs to be locked.
        if (rpc.name not in self.worker_locks) and (
            rpc.method in self.shared_objects[rpc.name].locking_methods
        ):
            self._safe_log(
                f"Locking worker {rpc.name} to {str(address)}", logging.DEBUG
            )
            self.worker_locks[rpc.name] = address

        # Everything looks good so far, dispatch the RPC to the correct worker.
        self._safe_log(f"Dispatching RPC to worker {rpc.name}", logging.DEBUG)
        self.dealers[rpc.name].send_multipart([address, b"", message])

        # Check if the worker needs to be unlocked.
        if (rpc.name in self.worker_locks) and (
            rpc.method in self.shared_objects[rpc.name].unlocking_methods
        ):
            self._safe_log(f"Unlocking worker {rpc.name}", logging.DEBUG)
            self.worker_locks.pop(rpc.name)

    def add_object(self, name: str, obj: Any):
        """Add an object to the server.

        Args:
            name: A unique name that will be used to refer to the object.
            obj: The object to add to the server.
        """
        # Build the SharedObjectDescriptor
        shared_methods = []
        for method_name, method in inspect.getmembers(obj, _is_shared_method):
            signature = str(inspect.signature(method))
            docstring = inspect.getdoc(method)
            if docstring is None:
                docstring = ""
            shared_methods.append(
                SharedMethodDescriptor(method_name, signature, docstring)
            )

        if len(shared_methods) == 0:
            raise RuntimeError(f"No shared methods found in {obj:!r}")

        locking_methods = []
        for method_name, method in inspect.getmembers(obj, _is_locking_method):
            locking_methods.append(method_name)

        unlocking_methods = []
        for method_name, method in inspect.getmembers(obj, _is_unlocking_method):
            unlocking_methods.append(method_name)

        if (locking_methods) and (not unlocking_methods):
            raise RuntimeError(
                f"Locking methods found in {obj:!r} but no unlocking methods."
            )

        if (unlocking_methods) and (not locking_methods):
            raise RuntimeError(
                f"Unlocking methods found in {obj:!r} but no locking methods."
            )

        descriptor = SharedObjectDescriptor(
            name, obj, shared_methods, locking_methods, unlocking_methods
        )

        self._safe_log(f"Adding object {name} to server")
        with self.new_object_lock:
            self.shared_objects_queue[name] = descriptor

    def get_object_methods(self, name: str) -> List[SharedMethodDescriptor]:
        """Returns a list of methods of the object with the given name.

        Args:
            name: The name of the object to get the methods of.

        Returns:
            A list of SharedMethodDescriptors."""
        return self.shared_objects[name].shared_methods

    def get_object_list(self) -> List[str]:
        """Returns a list of the names of the objects in the server.

        Returns:
            A list of strings.
        """
        return list(self.shared_objects.keys())

    def _process_new_object_queue(self):
        # First obtain a list of the names, we don't want to change the
        # dictionary while we're iterating over it.
        names = list(self.shared_objects_queue.keys())

        for name in names:
            descriptor = self.shared_objects_queue.pop(name)

            if name in self.shared_objects:
                raise RuntimeError(
                    f"Object {name} already exists, use a different name."
                )

            self.shared_objects[name] = descriptor

            dealer_socket = self.context.socket(zmq.DEALER)
            dealer_socket.bind(_dealer_address(name))
            self.poller.register(dealer_socket, zmq.POLLIN)
            self.dealers[name] = dealer_socket

            worker = _ObjectWorker(name, descriptor)
            worker.start()
            self.workers[name] = worker


class _ObjectWorker(StoppableThread):
    _LINGER_TIME = 1000  # milliseconds

    def __init__(self, worker_name: str, shared_object: SharedObjectDescriptor) -> None:
        super().__init__()
        self.worker_name = worker_name
        self.shared_object = shared_object

    def reply_address(self) -> str:
        return _dealer_address(self.worker_name)

    def _task_setup(self):
        self.context = zmq.Context.instance()
        self.reply_socket = self.context.socket(zmq.REP)
        self.reply_socket.connect(self.reply_address())

        self.poller = zmq.Poller()
        self.poller.register(self.reply_socket, zmq.POLLIN)

    def _task_cleanup(self):
        self.reply_socket.close(linger=self._LINGER_TIME)

    def _task_cycle(self):

        with allow_interrupt(self.stop):
            # Wait for a request
            poll_sockets = dict(self.poller.poll(timeout=10))

            # Check if there are new requests
            if poll_sockets.get(self.reply_socket) == zmq.POLLIN:
                message = self.reply_socket.recv()
                rpc: RemoteProcedureCall = pickle.loads(message)

                try:
                    call_result = self.shared_object.obj.__getattribute__(rpc.method)(
                        *rpc.args, **rpc.kwargs
                    )
                except Exception as e:
                    call_result = e
                    call_error = RemoteProcedureError.METHOD_EXCEPTION
                else:
                    call_error = RemoteProcedureError.NO_ERROR

                response = RemoteProcedureResponse(call_result, call_error)
                # Send the result back to the client
                self.reply_socket.send(pickle.dumps(response))
