import argparse
from collections import OrderedDict
from dataclasses import asdict
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
from urllib.parse import urlsplit
import uuid

from .exporters import litematic, schematic
from .generator import generate
from .model import validate
from .planner import plan


ROOT = Path(__file__).resolve().parent.parent
BUILDS = OrderedDict()
LOCK = threading.Lock()


class Handler(SimpleHTTPRequestHandler):
    def json_response(self, value, status=200):
        payload = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/health':
            return self.json_response({'application': 'blockwright', 'status': 'ok', 'ai_configured': bool(os.environ.get('OPENAI_API_KEY')), 'minecraft_version': 'Java 1.20.1'})
        if path.startswith('/api/builds/'):
            parts = path.strip('/').split('/')
            if len(parts) != 4 or parts[3] not in ('schem', 'litematic', 'json'):
                return self.json_response({'error': 'Unknown export.'}, 404)
            with LOCK:
                build = BUILDS.get(parts[2])
            if not build:
                return self.json_response({'error': 'Build expired. Generate it again.'}, 404)
            spec, world, payload = build
            fmt = parts[3]
            data = json.dumps(payload).encode() if fmt == 'json' else schematic(world, spec.title) if fmt == 'schem' else litematic(world, spec.title)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json' if fmt == 'json' else 'application/octet-stream')
            self.send_header('Content-Disposition', f'attachment; filename="building-{spec.seed}.{fmt}"')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(data)
            return
        if path.startswith('/api/'):
            return self.json_response({'error': 'Unknown endpoint.'}, 404)
        # Only serve the compiled frontend, never source files or server credentials.
        if not (ROOT / 'dist' / 'index.html').is_file():
            return self.json_response({'error': 'Frontend not built. Run npm ci && npm run build, or use npm run dev.'}, 503)
        super().do_GET()

    def do_POST(self):
        if self.path != '/api/generate':
            return self.json_response({'error': 'Unknown endpoint.'}, 404)
        if self.headers.get_content_type() != 'application/json':
            return self.json_response({'error': 'Use Content-Type: application/json.'}, 415)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 16384:
                return self.json_response({'error': 'Request must be 1–16,384 bytes.'}, 413)
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Request must be a JSON object.')
            spec, planning = plan(data.get('prompt', ''), data.get('overrides'), data.get('mode', 'offline'))
            world = generate(spec)
            validation = validate(world)
            if not validation['passed']:
                return self.json_response({'error': 'Generated block validation failed.', 'validation': validation}, 500)
            build_id = uuid.uuid4().hex
            payload = {'id': build_id, 'spec': asdict(spec), 'planning': planning, 'validation': validation, **world.payload()}
            with LOCK:
                BUILDS[build_id] = (spec, world, payload)
                while len(BUILDS) > 8:
                    BUILDS.popitem(last=False)
            self.json_response(payload)
        except (ValueError, TypeError) as exc:
            self.json_response({'error': str(exc)}, 400)
        except RuntimeError as exc:
            self.json_response({'error': str(exc)}, 502)


def main():
    parser = argparse.ArgumentParser(description='MC Building Generator development server')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '8000')))
    args = parser.parse_args()
    handler = partial(Handler, directory=str(ROOT / 'dist'))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f'Building workbench listening on {args.host}:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
