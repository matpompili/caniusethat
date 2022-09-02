import threading
import time

import pytest

from caniusethat.shareable import (
    Server,
    _force_remote_server_stop,
    acquire_lock,
    release_lock,
    you_can_use_this,
)
from caniusethat.thing import Thing

SERVER_ADDRESS = "tcp://127.0.0.1:6555"


class ClassWithoutLocks:
    @you_can_use_this
    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    @you_can_use_this
    def method_without_docs(self, a, b):
        return a - b


class ClassWithLocks:
    @you_can_use_this
    @acquire_lock
    def initialize(self) -> None:
        """Initialize the class."""
        pass

    @you_can_use_this
    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    @you_can_use_this
    @release_lock
    def finalize(self) -> None:
        """Finalize the class."""
        pass


class ClassWithReservedName:
    @you_can_use_this
    def close_this_thing(self) -> None:
        """This method has a reserved name."""
        pass


@pytest.fixture(autouse=True)
def wait_for_context_cleanup():
    yield
    time.sleep(0.1)


def test_local_server_shutdown():
    my_obj = ClassWithoutLocks()

    my_server = Server(SERVER_ADDRESS)
    my_server.start()
    my_server.add_object("my_obj", my_obj)
    time.sleep(0.5)
    my_server.stop()


def test_remote_server_shutdown():
    my_obj = ClassWithoutLocks()

    my_server = Server(SERVER_ADDRESS)
    my_server.start()
    my_server.add_object("my_obj", my_obj)
    _force_remote_server_stop(SERVER_ADDRESS)
    my_server.join()


def test_shared_thing():

    my_obj = ClassWithoutLocks()

    my_server = Server(SERVER_ADDRESS)
    my_server.start()
    my_server.add_object("my_obj", my_obj)
    time.sleep(0.5)

    my_thing = Thing("my_obj", SERVER_ADDRESS)
    assert hasattr(my_thing, "add")
    assert not hasattr(my_thing, "multiply")
    assert my_thing.add(1, 2) == 3
    assert my_thing.add(10, 20) == 30
    assert my_thing.add.__doc__ == "(a: int, b: int) -> int\nAdd two numbers."
    with pytest.raises(RuntimeError, match="RemoteProcedureError.METHOD_EXCEPTION"):
        my_thing.add(1, 2, 3)
    my_thing.close_this_thing()

    _force_remote_server_stop(SERVER_ADDRESS)

    my_server.join()


def test_locked_shared_thing():
    my_obj = ClassWithLocks()

    my_server = Server(SERVER_ADDRESS)
    my_server.start()
    my_server.add_object("my_obj", my_obj)
    time.sleep(0.5)

    my_thing = Thing("my_obj", SERVER_ADDRESS)
    assert hasattr(my_thing, "initialize")
    assert hasattr(my_thing, "add")
    assert hasattr(my_thing, "finalize")
    my_thing.initialize()
    assert my_thing.add(1, 2) == 3
    my_thing.finalize()
    my_thing.close_this_thing()

    _force_remote_server_stop(SERVER_ADDRESS)

    my_server.join()


def test_reserved_name():
    my_obj = ClassWithReservedName()

    my_server = Server(SERVER_ADDRESS)
    my_server.start()
    my_server.add_object("my_obj", my_obj)
    time.sleep(0.5)

    with pytest.raises(
        RuntimeError,
        match="Method name `close_this_thing` is reserved for internal use, please change it in the remote class.",
    ):
        my_thing = Thing("my_obj", SERVER_ADDRESS)

    _force_remote_server_stop(SERVER_ADDRESS)

    my_server.join()
