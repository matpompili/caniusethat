import re
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
    def __init__(self) -> None:
        self._wallet_value: int = 0

    @you_can_use_this
    def deposit(self, amount: int) -> int:
        """Deposit some money into the wallet.

        Args:
            amount: The amount of money to deposit.

        Returns:
            The new value of the wallet.
        """
        self._wallet_value = self._wallet_value + amount
        return self._wallet_value

    @you_can_use_this
    def withdraw(self, amount: int) -> int:
        if self._wallet_value < amount:
            raise RuntimeError("Insufficient funds")
        self._wallet_value = self._wallet_value - amount
        return self._wallet_value


class ClassWithLocks:
    def __init__(self) -> None:
        self._secret = ""

    @you_can_use_this
    @acquire_lock
    def write_secret(self, secret: str) -> None:
        """Write the secret to the class."""
        self._secret = secret

    @you_can_use_this
    @release_lock
    def read_secret(self) -> str:
        """Read the secret from the class."""
        secret = self._secret
        self._secret = ""
        return secret


class ClassWithReservedName:
    @you_can_use_this
    def close_this_thing(self) -> None:
        """This method has a reserved name."""
        pass


@pytest.fixture(autouse=True)
def wait_for_context_cleanup():
    yield
    time.sleep(0.5)


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
    assert hasattr(my_thing, "deposit")
    assert not hasattr(my_thing, "free_cash")
    assert my_thing.deposit(1) == 1
    assert my_thing.deposit(10) == 11
    assert my_thing.deposit.__doc__ == (
        """(amount: int) -> int
Deposit some money into the wallet.

Args:
    amount: The amount of money to deposit.

Returns:
    The new value of the wallet."""
    )
    with pytest.raises(
        RuntimeError, match="takes 2 positional arguments but 3 were given"
    ):
        my_thing.deposit(9, 5)

    assert my_thing.withdraw(1) == 10
    assert my_thing.withdraw(10) == 0
    with pytest.raises(RuntimeError, match="Insufficient funds"):
        my_thing.withdraw(100)
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
    assert hasattr(my_thing, "write_secret")
    assert hasattr(my_thing, "read_secret")
    my_thing.write_secret("This is a secret")
    assert my_thing.read_secret() == "This is a secret"
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
