"""Run the same ASGI server used by the hosting container on a private test port."""
import socket
import threading
import time

import uvicorn

from mc_builder.web_app import create_app


class LiveServer:
    def __init__(self, public_base_url=None, assets_directory=None):
        self.socket = socket.socket()
        self.socket.bind(('127.0.0.1', 0))
        self.base = f'http://127.0.0.1:{self.socket.getsockname()[1]}'
        try:
            self.app = create_app(public_base_url or self.base, assets_directory=assets_directory)
        except Exception:
            self.socket.close()
            raise
        self.server = uvicorn.Server(uvicorn.Config(self.app, log_level='error', timeout_graceful_shutdown=3))
        self.thread = threading.Thread(target=lambda: self.server.run(sockets=[self.socket]), daemon=True)

    def start(self):
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started:
            if not self.thread.is_alive() or time.monotonic() > deadline:
                self.stop()
                raise RuntimeError('ASGI test server failed to start.')
            time.sleep(.01)
        return self

    def stop(self):
        self.server.should_exit = True
        self.thread.join(timeout=10)
        self.socket.close()
        if self.thread.is_alive():
            raise RuntimeError('ASGI test server failed to stop.')
