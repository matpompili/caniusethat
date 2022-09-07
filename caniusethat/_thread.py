from threading import Thread


class StoppableThread(Thread):
    """Thread class with a stop() method.
    Subclasses should override the _task_setup(), _task_cycle() and _task_cleanup() methods.
    Once `stop()` is called, the thread will finish its current cycle, run the cleanup and then exit.
    """

    def __init__(self):
        super().__init__()
        self._stop_requested = False

    def stop(self):
        """Request the thread to stop."""
        self._stop_requested = True

    def is_running(self):
        """Return True if the thread is running."""
        return not self._stop_requested

    def run(self):
        self._task_setup()

        while not self._stop_requested:
            self._task_cycle()

        self._task_cleanup()

    def _task_setup(self):
        """Called once before entering the main loop.
        Override this method to perform any setup required by the task."""
        pass

    def _task_cycle(self):
        """Called repeatedly in the main loop.
        Override this method to perform the task."""
        pass

    def _task_cleanup(self):
        """Called once after exiting the main loop.
        Override this method to perform any cleanup required by the task."""
        pass
