from enum import Enum, auto
from typing import Any, Dict, List, NamedTuple, Tuple


class SharedMethodDescriptor(NamedTuple):
    """A description of a method that can be shared between processes.

    Attributes:
        name: The name of the method.
        signature: The signature of the method.
        docstring: The docstring of the method.

    Example:
        >>> SharedMethodDescriptor(
        ...     name="add",
        ...     signature="add(a: int, b: int) -> int",
        ...     docstring="Add two numbers."
        ... )
    """

    name: str
    signature: str
    docstring: str


class SharedObjectDescriptor(NamedTuple):
    """A description of an object that can be shared between processes.

    Attributes:
        name: The name of the object.
        obj: The Python object to be shared.
        methods: A list of SharedMethodDescriptor objects.
        locking_methods: A list of methods that acquire the object lock.
        unlocking_methods: A list of methods that release the object lock.
    """

    name: str
    obj: Any
    shared_methods: List[SharedMethodDescriptor]
    locking_methods: List[str]
    unlocking_methods: List[str]


class RemoteProcedureCall(NamedTuple):
    """A description of a remote procedure call.

    Attributes:
        name: The name of the remote object.
        method_name: The name of the method to call.
        args: The positional arguments to pass to the method.
        kwargs: The keyword arguments to pass to the method.
    """

    name: str
    method: str
    args: Tuple[Any, ...] = ()
    kwargs: Dict[str, Any] = {}


class RemoteProcedureError(Enum):
    """The error codes returned by the remote procedure call.

    NO_ERROR: The call was successful.
    NO_SUCH_THING: The remote object does not exist.
    NO_SUCH_METHOD: The remote object does not have the requested method.
    METHOD_EXCEPTION: The remote method raised an exception when called.
    INVALID_RPC: The RPC was invalid.
    THING_IS_LOCKED: The remote object is locked by another process.
    """

    NO_ERROR = auto()
    NO_SUCH_THING = auto()
    NO_SUCH_METHOD = auto()
    METHOD_EXCEPTION = auto()
    INVALID_RPC = auto()
    THING_IS_LOCKED = auto()


class RemoteProcedureResponse(NamedTuple):
    """A response to a remote procedure call.

    Attributes:
        result: The result of the remote method call.
        error: The error code returned by the remote method call.
    """

    result: Any
    error: RemoteProcedureError
