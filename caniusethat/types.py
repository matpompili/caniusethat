from enum import Enum, auto
from typing import Any, Dict, List, NamedTuple, Optional, Tuple


class SharedMethodDescriptor(NamedTuple):
    name: str
    signature: str
    docstring: str


class SharedObjectDescriptor(NamedTuple):
    name: str
    object: Any
    shared_methods: List[SharedMethodDescriptor]
    locking_methods: List[str]
    unlocking_methods: List[str]


class RemoteProcedureCall(NamedTuple):
    name: str
    method: str
    args: Tuple[Any, ...] = ()
    kwargs: Dict[str, Any] = {}


class RemoteProcedureError(Enum):
    NO_ERROR = auto()
    NO_SUCH_THING = auto()
    NO_SUCH_METHOD = auto()
    METHOD_EXCEPTION = auto()
    INVALID_RPC = auto()
    THING_IS_LOCKED = auto()


class RemoteProcedureResponse(NamedTuple):
    result: Any
    error: RemoteProcedureError
