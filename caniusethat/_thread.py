from threading import Thread


class StoppableThread(Thread):
    def __init__(self):
        super().__init__()
        self._stop = False

    def stop(self):
        self._stop = True

    def is_running(self):
        return not self._stop

    def run(self):
        self._task_setup()

        while not self._stop:
            self._task_cycle()

        self._task_cleanup()

    def _task_setup(self):
        pass

    def _task_cycle(self):
        pass

    def _task_cleanup(self):
        pass
