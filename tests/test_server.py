import time

import pytest

from caniusethat.shareable import Server, you_can_use_this


# def test_simple_share():
class MyClass:
    @you_can_use_this
    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        time.sleep(0.5)
        return a + b


my_obj = MyClass()

my_server = Server("tcp://127.0.0.1:6555")
my_server.start()
my_server.add_object("my_obj", my_obj)

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass

my_server.stop()
