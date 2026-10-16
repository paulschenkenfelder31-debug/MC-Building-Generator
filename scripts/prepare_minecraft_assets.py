"""Fetch a checksum-verified official client, extract artwork, and build a web atlas.

Original Minecraft assets are downloaded at setup/image-build time, never committed.
Requires Pillow (requirements-assets.txt). Animation previews use the first frame.
"""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import urllib.request
import urllib.error
import zipfile

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = json.loads((ROOT / 'mc_builder/data/catalog.json').read_text())
MANIFEST_URL = 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'


def download(url, destination, checksum=None, size=None):
    if not url.startswith(('https://piston-meta.mojang.com/', 'https://piston-data.mojang.com/')):
        raise ValueError('Unexpected Minecraft download host.')
    digest = hashlib.sha1()
    count = 0
    with urllib.request.urlopen(url, timeout=90) as response, destination.open('wb') as output:
        while chunk := response.read(1024 * 1024):
            count += len(chunk)
            if count > 1500 * 1024 * 1024:
                raise ValueError('Client download exceeds safety limit.')
            digest.update(chunk)
            output.write(chunk)
    if (checksum and digest.hexdigest() != checksum) or (size is not None and count != size):
        destination.unlink(missing_ok=True)
        raise ValueError('Minecraft download checksum or size mismatch.')
    return digest.hexdigest()


def package(client, destination, provenance):
    """Extract whitelisted files without trusting archive paths; replace only after success."""
    if destination.exists() and any(destination.iterdir()):
        marker = destination / 'manifest.json'
        if not marker.is_file() or json.loads(marker.read_text()).get('source') != 'Official Mojang Minecraft Java client':
            raise ValueError('Refusing to replace a directory that is not a generated Minecraft asset cache.')
    with tempfile.TemporaryDirectory(prefix='mc-assets-', dir=destination.parent) as temporary:
        stage = Path(temporary) / 'assets'
        stage.mkdir()
        models, states, textures = {}, {}, {}
        with zipfile.ZipFile(client) as archive:
            total = 0
            for entry in archive.infolist():
                path = PurePosixPath(entry.filename)
                if (entry.is_dir() or '..' in path.parts
                        or not entry.filename.startswith('assets/minecraft/')):
                    continue
                relative = PurePosixPath(*path.parts[2:])
                if not relative.parts:
                    continue
                category = relative.parts[0]
                allowed = ((category == 'textures' and relative.suffix == '.png') or
                           (category in ('models', 'blockstates') and relative.suffix == '.json'))
                if not allowed:
                    continue
                total += entry.file_size
                if entry.file_size > 16 * 1024 * 1024 or total > 512 * 1024 * 1024:
                    raise ValueError('Unexpected asset archive size.')
                data = archive.read(entry)
                target = stage.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                key = str(PurePosixPath(*relative.parts[1:]).with_suffix(''))
                if category == 'models':
                    models[key] = json.loads(data)
                elif category == 'blockstates':
                    states[key] = json.loads(data)
                elif key.startswith('block/'):
                    with Image.open(io.BytesIO(data)) as image:
                        image = image.convert('RGBA')
                        # Animated vanilla textures are vertically stacked square frames.
                        image = image.crop((0, 0, image.width, min(image.width, image.height)))
                        textures[key] = image.resize((32, 32), Image.Resampling.NEAREST)
        if not states or not textures:
            raise ValueError('Client does not contain vanilla block artwork.')
        missing = sorted(name.removeprefix('minecraft:') for name in REGISTRY['blocks']
                         if name.removeprefix('minecraft:') not in states)
        # Air and some engine-rendered technical blocks can legitimately have no model.
        tile = 36
        side = 2 ** math.ceil(math.log2(math.ceil(math.sqrt(len(textures))) * tile))
        atlas = Image.new('RGBA', (side, side))
        uv = {}
        columns = side // tile
        for index, (name, texture) in enumerate(sorted(textures.items())):
            x, y = (index % columns) * tile + 2, (index // columns) * tile + 2
            atlas.paste(texture, (x, y))
            # Gutters prevent sampling adjacent tiles at fractional UV coordinates.
            atlas.paste(texture.crop((0, 0, 1, 32)).resize((2, 32)), (x - 2, y))
            atlas.paste(texture.crop((31, 0, 32, 32)).resize((2, 32)), (x + 32, y))
            atlas.paste(texture.crop((0, 0, 32, 1)).resize((32, 2)), (x, y - 2))
            atlas.paste(texture.crop((0, 31, 32, 32)).resize((32, 2)), (x, y + 32))
            uv[name] = [x / side, y / side, 32 / side, 32 / side]
        atlas.save(stage / 'atlas.png')
        (stage / 'models.json').write_text(json.dumps({'models': models, 'blockstates': states, 'textures': uv}, separators=(',', ':')))
        manifest = {'version': REGISTRY['version'], 'data_version': REGISTRY['data_version'],
                    'source': 'Official Mojang Minecraft Java client', **provenance,
                    'texture_count': len(list((stage / 'textures').rglob('*.png'))),
                    'block_texture_count': len(textures), 'blockstate_count': len(states),
                    'missing_blockstates': missing,
                    'notice': 'Minecraft artwork © Mojang / Microsoft. Not affiliated with Mojang.',
                    'preview_limits': ['First animation frame only', 'Entity-rendered blocks use approximate geometry',
                                       'No lighting, fluid, redstone, or neighbor-update simulation']}
        (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        if destination.exists():
            shutil.rmtree(destination)
        shutil.move(str(stage), destination)
        return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'minecraft-assets')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='minecraft-client-') as temporary:
        cache = Path(temporary)
        download(MANIFEST_URL, cache / 'manifest.json')
        versions = json.loads((cache / 'manifest.json').read_text())
        entry = next(v for v in versions['versions'] if v['id'] == REGISTRY['version'] and v['type'] == 'release')
        download(entry['url'], cache / 'version.json', entry['sha1'])
        version = json.loads((cache / 'version.json').read_text())
        client = version['downloads']['client']
        print(f"Downloading official Minecraft Java {REGISTRY['version']} client ({client['size'] // 1048576} MiB)…", flush=True)
        download(client['url'], cache / 'client.jar', client['sha1'], client['size'])
        result = package(cache / 'client.jar', args.output, {'client_sha1': client['sha1'],
            'client_url': client['url'], 'version_manifest_sha1': entry['sha1']})
        print(f"Prepared {result['texture_count']} original textures and {result['blockstate_count']} blockstate models.")


if __name__ == '__main__':
    try:
        main()
    except (urllib.error.URLError, TimeoutError, ValueError, StopIteration) as error:
        raise SystemExit(f'Original Minecraft asset preparation failed: {error}. '
                         'The exact stable release and verified downloads from piston-meta.mojang.com '
                         'and piston-data.mojang.com are required; no placeholder artwork was installed.') from error
