"""Version-pinned vanilla registry facts. No Minecraft artwork is stored here."""
from functools import lru_cache
import json
from pathlib import Path
import re

CATALOG = json.loads((Path(__file__).parent / 'data/catalog.json').read_text())
VERSION = CATALOG['version']
DATA_VERSION = CATALOG['data_version']
BLOCKS = CATALOG['blocks']
AIR = {'minecraft:air', 'minecraft:cave_air', 'minecraft:void_air'}


def split_state(value):
    if not isinstance(value, str) or len(value) > 500:
        raise ValueError('Block must be a vanilla block state string.')
    match = re.fullmatch(r'(?:minecraft:)?([a-z0-9_]+)(?:\[([a-z0-9_=,]+)\])?', value)
    if not match:
        raise ValueError(f'Invalid block state: {value}')
    name, raw = match.groups()
    props = {}
    for pair in raw.split(',') if raw else []:
        parts = pair.split('=')
        if len(parts) != 2 or parts[0] in props:
            raise ValueError(f'Invalid block properties: {value}')
        props[parts[0]] = parts[1]
    return 'minecraft:' + name, props


def format_state(name, props):
    return name + ('[' + ','.join(f'{k}={v}' for k, v in sorted(props.items())) + ']' if props else '')


@lru_cache(maxsize=8192)
def canonical_state(value):
    name, props = split_state(value)
    entry = BLOCKS.get(name)
    if entry is None:
        raise ValueError(f'Unknown Java {VERSION} block: {name}')
    for key, val in props.items():
        if val not in entry['properties'].get(key, []):
            raise ValueError(f'Invalid property {key}={val} for {name}')
    return format_state(name, entry['defaults'] | props)


def catalog_page(query='', offset=0, limit=60):
    if not isinstance(query, str) or len(query) > 100:
        raise ValueError('Search must contain at most 100 characters.')
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Use offset >=0 and limit 1..100.')
    words = query.lower().replace('minecraft:', '').replace(' ', '_')
    names = [name for name in BLOCKS if words in name]
    return {'version': VERSION, 'data_version': DATA_VERSION, 'block_count': len(BLOCKS),
            'total': len(names), 'offset': offset,
            'blocks': [{'id': name, 'state': canonical_state(name), **BLOCKS[name]}
                       for name in names[offset:offset + limit]]}
