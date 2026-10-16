"""Share an offline-only demo with a temporary Cloudflare Quick Tunnel."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parent.parent
VERSION = '2026.10.1'
# Official GitHub release asset digest, verified over HTTPS on 2026-10-16:
# https://github.com/cloudflare/cloudflared/releases/expanded_assets/2026.10.1
SHA256 = '3bfc539f45d2620c71debb7a86be0efa737ed5ccbad9eb85c787116900e5c586'
URL = f'https://github.com/cloudflare/cloudflared/releases/download/{VERSION}/cloudflared-linux-amd64'
BINARY = ROOT / 'artifacts' / 'tools' / f'cloudflared-{VERSION}'


def prepare_binary():
    if sys.platform != 'linux' or os.uname().machine != 'x86_64':
        raise RuntimeError('This pinned tunnel helper currently supports Linux x86_64 only.')
    if not BINARY.exists():
        BINARY.parent.mkdir(parents=True, exist_ok=True)
        temporary = BINARY.with_suffix('.download')
        try:
            request = urllib.request.Request(URL, headers={'User-Agent': 'Blockwright-public-demo'})
            with urllib.request.urlopen(request, timeout=60) as response, temporary.open('wb') as target:
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > 128 * 1024 * 1024:
                        raise RuntimeError('Tunnel download exceeds expected size.')
                    target.write(chunk)
            with temporary.open('rb') as source:
                if hashlib.file_digest(source, 'sha256').hexdigest() != SHA256:
                    raise RuntimeError('Cloudflared checksum verification failed; download will not be executed.')
            temporary.replace(BINARY)
        finally:
            temporary.unlink(missing_ok=True)
    with BINARY.open('rb') as source:
        if hashlib.file_digest(source, 'sha256').hexdigest() != SHA256:
            raise RuntimeError('Cached cloudflared checksum does not match. Remove the cached binary and retry.')
    BINARY.chmod(0o755)
    return BINARY


def stop(child):
    if child is not None and child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--port', type=int, default=3002)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        raise RuntimeError('Port must be between 1 and 65535.')
    binary = prepare_binary()
    print(f'Cloudflared {VERSION}: SHA-256 verified.', flush=True)
    if args.prepare_only:
        return 0
    if not (ROOT / 'dist/index.html').is_file():
        raise RuntimeError('Build the frontend first with npm run build.')
    # Use a separate offline demo process; do not expose any server-side AI billing.
    environment = {key: value for key, value in os.environ.items() if key != 'OPENAI_API_KEY'}
    origin = f'http://127.0.0.1:{args.port}'
    server = tunnel = None
    try:
        server = subprocess.Popen([sys.executable, '-m', 'mc_builder.server', '--host', '127.0.0.1', '--port', str(args.port)], cwd=ROOT, env=environment)
        deadline = time.monotonic() + 10
        while True:
            if server.poll() is not None:
                raise RuntimeError('The public demo server could not start. Choose an unused --port.')
            try:
                with urllib.request.urlopen(origin + '/api/health', timeout=.5) as response:
                    health = json.load(response)
                if health.get('application') != 'blockwright' or health.get('ai_configured'):
                    raise RuntimeError('The public demo must be an offline-only Blockwright instance.')
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise RuntimeError('The demo server did not become ready.')
                time.sleep(.1)
        print('Starting a temporary public link. It stops when this process or the cloud environment stops.', flush=True)
        tunnel = subprocess.Popen([str(binary), 'tunnel', '--no-autoupdate', '--protocol', 'http2', '--edge-ip-version', '4', '--url', origin], cwd=BINARY.parent, env=environment)
        return tunnel.wait()
    finally:
        stop(tunnel)
        stop(server)


def interrupted(_signum, _frame):
    raise KeyboardInterrupt


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, interrupted)
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0)
    except (RuntimeError, OSError, urllib.error.URLError) as error:
        print(f'Public link unavailable: {error}', file=sys.stderr)
        raise SystemExit(1)
