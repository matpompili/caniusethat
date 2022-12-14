from caniusethat.shareable import Server, acquire_lock, release_lock, you_can_use_this

SERVER_ADDRESS = "tcp://127.0.0.1:6555"


class ClassWithoutLocks:
    def __init__(self, secret_number: int) -> None:
        self._secret_number = secret_number

    @you_can_use_this
    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b + self._secret_number


class ClassWithLocks:
    def __init__(self, secret_number: int) -> None:
        self._secret_number = secret_number

    @you_can_use_this
    @acquire_lock
    def initialize(self) -> None:
        """Initialize the class."""
        pass

    @you_can_use_this
    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b + self._secret_number

    @you_can_use_this
    @release_lock
    def finalize(self) -> None:
        """Finalize the class."""
        pass


if __name__ == "__main__":
    my_obj = ClassWithLocks(secret_number=42)

    my_server = Server(SERVER_ADDRESS)
    my_server.start()
    my_server.add_object("my_obj", my_obj)

    try:
        my_server.join()
    except KeyboardInterrupt:
        my_server.stop()
        my_server.join()
