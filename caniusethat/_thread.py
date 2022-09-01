from threading import Thread


class StoppableThread(Thread):
    def __init__(self):
        super().__init__()
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    def is_running(self):
        return not self._stop_requested

    def run(self):
        self._task_setup()

        while not self._stop_requested:
            self._task_cycle()

        self._task_cleanup()

    def _task_setup(self):
        pass

    def _task_cycle(self):
        pass

    def _task_cleanup(self):
        pass
