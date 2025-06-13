class LocalStack:
    def __init__(self):
        self.is_running = False
        self.moto_server = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()

    def start(self):
        if self.is_running:
            return

        self._do_start()
        self.is_running = True

    def stop(self):
        if not self.is_running:
            return

        self._do_stop()
        self.is_running = False

    def restart(self):
        self.stop()
        self.start()

    def _do_start(self):
        pass

    def _do_stop(self):
        pass
