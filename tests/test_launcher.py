"""Regression coverage for the preview's single-command startup and process cleanup."""
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.request


ROOT = Path(__file__).resolve().parent.parent


def unused_port():
    with socket.socket() as connection:
        connection.bind(('127.0.0.1', 0))
        return connection.getsockname()[1]


class LauncherTests(unittest.TestCase):
    def test_single_command_dev_starts_api_and_proxy_and_cleans_up(self):
        public_port, api_port = unused_port(), unused_port()
        while api_port == public_port:
            api_port = unused_port()
        environment = {**os.environ, 'PORT': str(public_port), 'BLOCKWRIGHT_API_PORT': str(api_port)}
        # Run outside the checkout and without activating .venv, like an external launcher.
        with tempfile.TemporaryDirectory() as directory:
            child = subprocess.Popen(['node', str(ROOT / 'scripts/run.mjs'), 'dev'], cwd=directory, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            try:
                base = f'http://127.0.0.1:{public_port}'
                deadline = time.monotonic() + 20
                while True:
                    if child.poll() is not None:
                        self.fail('Launcher exited early: ' + child.communicate()[0])
                    try:
                        with urllib.request.urlopen(base + '/api/health', timeout=.5) as response:
                            health = json.load(response)
                        break
                    except OSError:
                        if time.monotonic() > deadline:
                            self.fail('Preview did not start within 20 seconds.')
                        time.sleep(.1)
                self.assertEqual(health['application'], 'blockwright')
                with urllib.request.urlopen(base + '/') as response:
                    self.assertIn(b'Blockwright', response.read())
                request = urllib.request.Request(base + '/api/generate', data=b'{"prompt":"A modern 21x19 villa"}', headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(request) as response:
                    build = json.load(response)
                self.assertTrue(build['validation']['passed'])
                self.assertGreater(build['block_count'], 1000)
                with urllib.request.urlopen(f"{base}/api/builds/{build['id']}/schem") as response:
                    self.assertEqual(response.read(2), b'\x1f\x8b')
            finally:
                if child.poll() is None:
                    child.terminate()
                try:
                    logs, _ = child.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    logs, _ = child.communicate()
                    self.fail('Launcher failed to stop its child processes: ' + logs)
            self.assertEqual(child.returncode, 0, logs)
            for port in (public_port, api_port):
                with socket.socket() as connection:
                    self.assertNotEqual(connection.connect_ex(('127.0.0.1', port)), 0, f'Process leaked on port {port}')
