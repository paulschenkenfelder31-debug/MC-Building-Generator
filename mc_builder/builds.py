"""Shared build storage for the browser and MCP. No model calls live here."""
from collections import OrderedDict
from dataclasses import asdict
import threading
import uuid

from .generator import generate
from .model import validate


class BuildStore:
    def __init__(self, capacity=8):
        self.capacity = capacity
        self._builds = OrderedDict()
        self._lock = threading.Lock()
        self._generation_slots = threading.Semaphore(2)

    def create(self, spec, planning):
        with self._generation_slots:
            world = generate(spec)
            validation = validate(world)
            if not validation['passed']:
                raise ValueError('Generated block validation failed.')
            build_id = uuid.uuid4().hex
            payload = {'id': build_id, 'spec': asdict(spec), 'planning': planning,
                       'validation': validation, **world.payload()}
        with self._lock:
            self._builds[build_id] = (spec, world, payload)
            while len(self._builds) > self.capacity:
                self._builds.popitem(last=False)
        return payload

    def get(self, build_id):
        with self._lock:
            return self._builds.get(build_id)


def assistant_planning():
    return {
        'mode': 'assistant',
        'description': 'Design supplied through MCP by a connected assistant. This server made no model API call.',
        'limitations': ['The connected assistant selects supported template parameters.',
                        'No reference-image interpretation or visual critique runs on this server.'],
    }


def summary(payload, base_url=''):
    build_id = payload['id']
    return {
        key: payload[key] for key in ('id', 'spec', 'dimensions', 'block_count', 'materials', 'validation', 'planning')
    } | {
        'preview_url': f'{base_url}/?build={build_id}',
        'downloads': {fmt: f'{base_url}/api/builds/{build_id}/{fmt}' for fmt in ('schem', 'litematic', 'json')},
        'availability': 'In-memory build: download now. A restart or eight newer builds can expire these links.',
    }
