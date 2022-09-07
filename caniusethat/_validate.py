import pickle
from typing import Any

from caniusethat._types import (
    RemoteProcedureCall,
    RemoteProcedureError,
    RemoteProcedureResponse,
)


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
