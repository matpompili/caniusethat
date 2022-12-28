import pickle
from typing import Any

from caniusethat._types import (
    RemoteProcedureCall,
    RemoteProcedureError,
    RemoteProcedureResponse,
)


def validate_rpc_response(response: bytes) -> Any:
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


def prepare_rpc_pickle(name, method, args, kwargs) -> bytes:
    """Prepares a remote procedure call for pickling.

    Args:
        name: The name of the remote object.
        method: The name of the method to call.
        args: The positional arguments to pass to the method.
        kwargs: The keyword arguments to pass to the method.

    Returns:
        The pickled RemoteProcedureCall."""
    return pickle.dumps(RemoteProcedureCall(name, method, args, kwargs))
