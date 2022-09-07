import argparse
from typing import List

import zmq

from caniusethat._logging import getLogger
from caniusethat._types import SharedMethodDescriptor
from caniusethat.thing import _make_rpc_and_validate_response

_logger = getLogger("caniusethat.cli")


def list_server_objects(args) -> None:
    ctx = zmq.Context.instance()
    socket: zmq.Socket = ctx.socket(zmq.REQ)
    _logger.info(f"Connecting to 👀 CanIUseThat server at {args.server_address}...")
    socket.connect(args.server_address)
    object_list = _make_rpc_and_validate_response(socket, "_server", "get_object_list")
    print("Available objects:")
    for obj_name in object_list:
        print(f"- {obj_name}")


def list_objects_methods(args) -> None:
    ctx = zmq.Context.instance()
    socket: zmq.Socket = ctx.socket(zmq.REQ)
    _logger.info(f"Connecting to 👀 CanIUseThat server at {args.server_address}...")
    socket.connect(args.server_address)
    try:
        method_list: List[SharedMethodDescriptor] = _make_rpc_and_validate_response(
            socket, "_server", "get_object_methods", args.object_name
        )
    except RuntimeError:
        _logger.exception(f"Could not find object {args.object_name}.")
    else:
        print("Available methods:")
        for method in method_list:
            print(f"- {args.object_name}.{method.name}{method.signature}")
            print(f"    {method.docstring}")


def unlock(args) -> None:
    ctx = zmq.Context.instance()
    socket: zmq.Socket = ctx.socket(zmq.REQ)
    _logger.info(f"Connecting to 👀 CanIUseThat server at {args.server_address}...")
    socket.connect(args.server_address)
    try:
        _make_rpc_and_validate_response(
            socket, "_server", "force_release_lock", args.object_name
        )
    except RuntimeError:
        _logger.exception(f"Could not release lock for object {args.object_name}")
    else:
        _logger.info(f"Released lock for object {args.object_name} (if any).")


def run_cli() -> None:
    parser = argparse.ArgumentParser(description="caniusethat CLI utility")

    subparsers = parser.add_subparsers(title="subcommands")

    parser_list_objects = subparsers.add_parser(
        "list_objects", aliases=["lo"], help="List available objects on the server."
    )
    parser_list_objects.add_argument(
        "server_address",
        type=str,
        help="address of the server, e.g tcp://127.0.0.1:6555",
    )
    parser_list_objects.set_defaults(func=list_server_objects)

    parser_list_methods = subparsers.add_parser(
        "list_methods",
        aliases=["lm"],
        help="List available methods for the specific object.",
    )
    parser_list_methods.add_argument(
        "server_address",
        type=str,
        help="address of the server, e.g tcp://127.0.0.1:6555",
    )
    parser_list_methods.add_argument(
        "object_name", type=str, help="name of the object, e.g my_obj"
    )
    parser_list_methods.set_defaults(func=list_objects_methods)

    parser_unlock = subparsers.add_parser(
        "unlock", help="Release lock for the specific object, if one is present."
    )
    parser_unlock.add_argument(
        "server_address",
        type=str,
        help="address of the server, e.g tcp://127.0.0.1:6555",
    )
    parser_unlock.add_argument(
        "object_name", type=str, help="name of the object, e.g my_obj"
    )
    parser_unlock.set_defaults(func=unlock)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    run_cli()
