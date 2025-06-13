class MotoServer:
    def __init__(self):
        self.is_running = False
        self.port: int | None = None
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
        from moto.server import ThreadedMotoServer

        from .util import find_free_port

        port = find_free_port()
        self.port = port
        self.moto_server = ThreadedMotoServer(ip_address="127.0.0.1", port=port)
        self.moto_server.start()
        self.wait_for_start()

    def wait_for_start(self):
        import time
        import urllib.error
        import urllib.request

        max_attempts = 20
        for attempt in range(max_attempts):
            try:
                url = f"http://127.0.0.1:{self.port}/"
                urllib.request.urlopen(url, timeout=1)
                return
            except urllib.error.URLError:
                if attempt < max_attempts - 1:
                    time.sleep(1)
                else:
                    raise RuntimeError(f"Moto server failed to start after {max_attempts} seconds")

    def _do_stop(self):
        if self.moto_server:
            self.moto_server.stop()
        self.moto_server = None
