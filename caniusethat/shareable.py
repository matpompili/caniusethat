import inspect
import pickle
from functools import wraps
from threading import Lock
from typing import Any, Callable, Dict, List

import zmq

from caniusethat._thread import StoppableThread
from caniusethat.logging import getLogger
from caniusethat.types import (
    RemoteProcedureCall,
    RemoteProcedureError,
    RemoteProcedureResponse,
    SharedMethodDescriptor,
    SharedObjectDescriptor,
)

_logger = getLogger(__name__)


def is_shared_method(object: Any) -> bool:
    return inspect.ismethod(object) and hasattr(object, "_you_can_use_this")


def dealer_address(name: str) -> str:
    return f"inproc://{name}_worker"


def you_can_use_this(f: Callable) -> Callable:
    @wraps(f)
    def wrapper(*args, **kwds):
        return f(*args, **kwds)

    wrapper._you_can_use_this = True  # type: ignore
    return wrapper


class Server(StoppableThread):
    def __init__(self, router_address: str) -> None:
        super().__init__()
        self.router_address = router_address
        self.shared_objects: Dict[str, SharedObjectDescriptor] = {}
        self.shared_objects_queue: Dict[str, SharedObjectDescriptor] = {}
        self.new_object_lock = Lock()
        self.dealers: Dict[str, Any] = {}
        self.workers: Dict[str, _ObjectWorker] = {}

    def _task_setup(self):
        _logger.info("Server setup")
        self.context = zmq.Context.instance()
        self.router_socket = self.context.socket(zmq.ROUTER)
        self.router_socket.bind(self.router_address)

        self.poller = zmq.Poller()
        self.poller.register(self.router_socket, zmq.POLLIN)

    def _task_cleanup(self):
        _logger.info("Server cleanup")
        self.poller.unregister(self.router_socket)
        self.router_socket.close(linger=1000)

        for dealer_socket in self.dealers.values():
            self.poller.unregister(dealer_socket)
            dealer_socket.close(linger=1000)

        for worker in self.workers.values():
            worker.stop()

    def _task_cycle(self):
        # Add any new objects to the shared objects.
        with self.new_object_lock:
            self._process_new_object_queue()

        poll_sockets = dict(self.poller.poll(timeout=10))

        # Check if there are new requests
        if poll_sockets.get(self.router_socket) == zmq.POLLIN:
            address, _, message = self.router_socket.recv_multipart()
            # Dispatch the message to the correct worker
            rpc = pickle.loads(message)

            if not isinstance(rpc, RemoteProcedureCall):
                _logger.warning(f"Received invalid RemoteProcedureCall: {rpc}")
                message = self._package_error(RemoteProcedureError.INVALID_RPC)
                self.router_socket.send_multipart([address, b"", message])

            elif rpc.name == "_server" and rpc.method == "get_object_methods":
                if rpc.args[0] not in self.shared_objects:
                    _logger.warning(f"No such object: {rpc.args[0]}")
                    message = self._package_error(RemoteProcedureError.NO_SUCH_THING)
                    self.router_socket.send_multipart([address, b"", message])
                else:
                    message = self._package_success_reply(
                        self.shared_objects[rpc.args[0]].shared_methods
                    )
                    self.router_socket.send_multipart([address, b"", message])

            elif rpc.name not in self.shared_objects:
                _logger.warning(f"Received RPC for unknown object: {rpc.name}")
                message = self._package_error(RemoteProcedureError.NO_SUCH_THING)
                self.router_socket.send_multipart([address, b"", message])

            elif rpc.method not in [
                method.name for method in self.shared_objects[rpc.name].shared_methods
            ]:
                _logger.warning(
                    f"Received RPC for unknown method: {rpc.name}.{rpc.method}"
                )
                message = self._package_error(RemoteProcedureError.NO_SUCH_METHOD)
                self.router_socket.send_multipart([address, b"", message])

            else:
                _logger.info(f"Dispatching RPC to worker {rpc.name}")
                self.dealers[rpc.name].send_multipart([address, b"", message])

        # Check if there are any new replies
        for dealer_socket in self.dealers.values():
            if poll_sockets.get(dealer_socket) == zmq.POLLIN:
                _logger.info(f"Received reply from worker {dealer_socket}")
                message = dealer_socket.recv_multipart()
                # Send the reply back to the client
                self.router_socket.send_multipart(message)

    def _package_reply(self, reply: Any, error: RemoteProcedureError) -> bytes:
        return pickle.dumps(RemoteProcedureResponse(reply, error))

    def _package_error(self, error: RemoteProcedureError) -> bytes:
        return self._package_reply(None, error)

    def _package_success_reply(self, reply: Any) -> bytes:
        return self._package_reply(reply, RemoteProcedureError.NO_ERROR)

    def add_object(self, name: str, object: Any):
        # Build the SharedObjectDescriptor
        shared_methods = []
        for method_name, method in inspect.getmembers(object, is_shared_method):
            signature = str(inspect.signature(method))
            docstring = method.__doc__
            shared_methods.append(
                SharedMethodDescriptor(method_name, signature, docstring)
            )

        if len(shared_methods) == 0:
            raise RuntimeError(f"No shared methods found in {object:!r}")

        descriptor = SharedObjectDescriptor(name, object, shared_methods)

        _logger.info(f"Adding object {name}")
        with self.new_object_lock:
            self.shared_objects_queue[name] = descriptor

    def get_object_methods(self, name: str) -> List[SharedMethodDescriptor]:
        """Returns a list of methods of the object with the given name."""
        return self.shared_objects[name].shared_methods

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
            dealer_socket.bind(dealer_address(name))
            self.poller.register(dealer_socket, zmq.POLLIN)
            self.dealers[name] = dealer_socket

            worker = _ObjectWorker(name, descriptor)
            worker.start()
            self.workers[name] = worker


class _ObjectWorker(StoppableThread):
    def __init__(self, worker_name: str, shared_object: SharedObjectDescriptor) -> None:
        super().__init__()
        self.worker_name = worker_name
        self.shared_object = shared_object

    def reply_address(self) -> str:
        return dealer_address(self.worker_name)

    def _task_setup(self):
        self.context = zmq.Context.instance()
        self.reply_socket = self.context.socket(zmq.REP)
        self.reply_socket.connect(self.reply_address())

        self.poller = zmq.Poller()
        self.poller.register(self.reply_socket, zmq.POLLIN)

    def _task_cleanup(self):
        self.reply_socket.close(linger=1000)

    def _task_cycle(self):
        # Wait for a request
        poll_sockets = dict(self.poller.poll(timeout=10))

        # Check if there are new requests
        if poll_sockets.get(self.reply_socket) == zmq.POLLIN:
            message = self.reply_socket.recv()
            rpc: RemoteProcedureCall = pickle.loads(message)

            try:
                call_result = self.shared_object.object.__getattribute__(rpc.method)(
                    *rpc.args, **rpc.kwargs
                )
            except Exception:
                _logger.exception(f"Error executing {rpc}")
                call_result = None
                call_error = RemoteProcedureError.METHOD_EXCEPTION
            else:
                call_error = RemoteProcedureError.NO_ERROR

            response = RemoteProcedureResponse(call_result, call_error)
            # Send the result back to the client
            self.reply_socket.send(pickle.dumps(response))
