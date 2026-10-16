import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
import zipfile

import nbtlib
from PIL import Image
from mcp import Client

from mc_builder.builds import BuildStore, assistant_planning
from mc_builder.catalog import BLOCKS, VERSION, DATA_VERSION, canonical_state, catalog_page, split_state
from mc_builder.editing import edit_world, partner
from mc_builder.exporters import schematic, litematic
from mc_builder.model import BuildSpec, World, validate
from scripts.prepare_minecraft_assets import download, package
from server_test_support import LiveServer


class CatalogTests(unittest.TestCase):
    def test_complete_version_pinned_registry_and_every_default(self):
        self.assertEqual((VERSION, DATA_VERSION, len(BLOCKS)), ('26.3', 5023, 1286))
        for name, entry in BLOCKS.items():
            with self.subTest(block=name):
                state = canonical_state(name)
                self.assertEqual(canonical_state(state), state)
                self.assertEqual(split_state(state)[1], entry['defaults'])
                self.assertEqual(set(entry['properties']), set(entry['defaults']))

    def test_invalid_properties_unknown_blocks_and_duplicates_rejected(self):
        for value in ('invented', 'oak_stairs[facing=up]', 'stone[axis=y]',
                      'oak_log[axis=x,axis=y]', '../stone', 'minecraft:stone[]', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                canonical_state(value)

    def test_catalog_search_and_pagination_cover_every_id(self):
        found = []
        for offset in range(0, len(BLOCKS), 100):
            found += [b['id'] for b in catalog_page(offset=offset, limit=100)['blocks']]
        self.assertEqual(set(found), set(BLOCKS))
        self.assertEqual(len(found), len(set(found)))
        result = catalog_page('cherry stairs')
        self.assertEqual(result['total'], 1)
        self.assertIn('facing', result['blocks'][0]['properties'])

    def test_all_non_air_ids_survive_both_export_palettes(self):
        world = World()
        for index, name in enumerate(BLOCKS):
            pos = (2 + index % 32 * 3, 2, 2 + index // 32 * 3)
            value = canonical_state(name)
            world.set(*pos, value)
            other = partner(pos, value)
            if other:
                world.set(*other[0], other[1])
        self.assertTrue(validate(world)['passed'])
        expected = set(BLOCKS) - {'minecraft:air', 'minecraft:cave_air', 'minecraft:void_air'}
        root = nbtlib.File.parse(io.BytesIO(gzip.decompress(schematic(world, 'Full catalog'))))
        self.assertEqual(int(root['DataVersion']), 5023)
        names = {str(state).split('[')[0] for state in root['Palette']} - {'minecraft:air'}
        self.assertEqual(names, expected)
        root = nbtlib.File.parse(io.BytesIO(gzip.decompress(litematic(world, 'Full catalog'))))
        names = {str(state['Name']) for state in root['Regions']['Building']['BlockStatePalette']} - {'minecraft:air'}
        self.assertEqual(names, expected)


class EditingTests(unittest.TestCase):
    def test_palette_customization_and_immutable_replacement(self):
        store = BuildStore()
        first = store.create(BuildSpec.from_dict({'palette': {'wall': 'cherry_planks', 'beam': 'bamboo_block', 'stair': 'oxidized_cut_copper_stairs'}}), assistant_planning())
        self.assertIn('minecraft:cherry_planks', [m['block'] for m in first['materials']])
        second = store.edit(first['id'], replace={'from': 'oxidized_cut_copper_stairs', 'to': 'cherry_stairs'})
        self.assertNotEqual(first['id'], second['id'])
        self.assertTrue(any('oxidized_cut_copper_stairs' in state for state in first['palette']))
        for state in second['palette']:
            if state.startswith('minecraft:cherry_stairs'):
                self.assertIn('facing=', state)
        self.assertTrue(second['validation']['passed'])

    def test_place_remove_two_block_objects_and_bounds(self):
        original = World(); original.set(0, 0, 0, 'stone')
        for block in ('cherry_door', 'red_bed', 'tall_grass'):
            world = edit_world(original, [{'x': 5, 'y': 5, 'z': 5, 'block': block}])
            self.assertEqual(len(world.blocks), 3)
            self.assertTrue(validate(world)['passed'])
            world = edit_world(world, [{'x': 5, 'y': 5, 'z': 5, 'block': 'air'}])
            self.assertEqual(world.blocks, original.blocks)
        for coord in (-1, 128, True, 1.5):
            with self.assertRaises(ValueError):
                edit_world(original, [{'x': coord, 'y': 5, 'z': 5, 'block': 'stone'}])
        with self.assertRaises(ValueError):
            edit_world(original, [{'x': 5, 'y': 127, 'z': 5, 'block': 'oak_door'}])
        self.assertEqual(len(original.blocks), 1)


class CatalogAPITests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = LiveServer().start()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    async def test_http_catalog_edit_and_download(self):
        base = self.server.base
        with urllib.request.urlopen(base + '/api/blocks?q=cherry_stairs') as response:
            self.assertEqual(json.load(response)['total'], 1)
        for query in ('limit=101', 'offset=-1', 'limit=abc'):
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(base + '/api/blocks?' + query)
        payload = self.server.app.state.builds.create(BuildSpec(), assistant_planning())
        request = urllib.request.Request(base + f"/api/builds/{payload['id']}/edit", data=json.dumps({
            'changes': [{'x': 15, 'y': 40, 'z': 15, 'block': 'cherry_stairs[facing=east]'}]}).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request) as response:
            edited = json.load(response)
        self.assertNotEqual(edited['id'], payload['id'])
        self.assertTrue(any('cherry_stairs' in b for b in edited['palette']))
        with urllib.request.urlopen(base + f"/api/builds/{edited['id']}/schem") as response:
            root = nbtlib.File.parse(io.BytesIO(gzip.decompress(response.read())))
        self.assertTrue(any('cherry_stairs' in b for b in root['Palette']))

    async def test_mcp_catalog_and_edits_without_model_api(self):
        async with Client(self.server.base + '/mcp') as client:
            result = await client.call_tool('search_blocks', {'query': 'cherry_stairs'})
            self.assertEqual(result.structured_content['total'], 1)
            result = await client.call_tool('create_build', {'palette': {'wall': 'cherry_planks'}})
            build_id = result.structured_content['id']
            result = await client.call_tool('edit_build', {'build_id': build_id, 'changes': [{'x': 1, 'y': 50, 'z': 1, 'block': 'copper_block'}]})
            self.assertFalse(result.is_error)
            self.assertNotEqual(result.structured_content['id'], build_id)


class AssetPreparationTests(unittest.TestCase):
    def test_stale_or_missing_assets_are_reported_as_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            assets = Path(directory)
            for manifest in (None, [], {'version': '1.20.1', 'data_version': 3465}):
                if manifest is not None:
                    (assets / 'manifest.json').write_text(json.dumps(manifest))
                server = LiveServer(assets_directory=assets).start()
                try:
                    with urllib.request.urlopen(server.base + '/api/assets') as response:
                        self.assertFalse(json.load(response)['available'])
                finally:
                    server.stop()

    def test_checksum_mismatch_fails_and_removes_download(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'client.jar'
            with patch('urllib.request.urlopen', return_value=io.BytesIO(b'incorrect download')):
                with self.assertRaisesRegex(ValueError, 'checksum'):
                    download('https://piston-data.mojang.com/client.jar', path, '0' * 40)
            self.assertFalse(path.exists())

    def test_safe_extraction_original_pngs_atlas_and_first_animation_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            image = Image.new('RGBA', (16, 32), 'red')
            image.paste(Image.new('RGBA', (16, 16), 'blue'), (0, 16))
            png = io.BytesIO(); image.save(png, format='PNG')
            client = directory / 'fixture.jar'
            with zipfile.ZipFile(client, 'w') as jar:
                # Official client JARs include directory records, including the namespace root.
                for name in ('assets/', 'assets/minecraft/', 'assets/minecraft/textures/',
                             'assets/minecraft/textures/block/', 'assets/minecraft/models/',
                             'assets/minecraft/blockstates/', 'assets/minecraft/textures/fake.png/'):
                    jar.writestr(name, b'')
                # A normalized namespace-root record should also be harmless.
                jar.writestr('assets/minecraft/.', b'')
                jar.writestr('assets/minecraft/textures/block/stone.png', png.getvalue())
                jar.writestr('assets/minecraft/textures/item/diamond.png', png.getvalue())
                jar.writestr('assets/minecraft/blockstates/stone.json', '{"variants":{"":{"model":"minecraft:block/stone"}}}')
                jar.writestr('assets/minecraft/models/block/stone.json', '{"textures":{"all":"minecraft:block/stone"}}')
                jar.writestr('assets/minecraft/../../escape.png', b'no')
                jar.writestr('client.class', b'no')
            destination = directory / 'prepared'
            manifest = package(client, destination, {'client_sha1': 'fixture-only'})
            self.assertEqual(manifest['texture_count'], 2)
            self.assertEqual((destination / 'textures/block/stone.png').read_bytes(), png.getvalue())
            library = json.loads((destination / 'models.json').read_text())
            with Image.open(destination / 'atlas.png') as atlas:
                u, v, _, _ = library['textures']['block/stone']
                self.assertEqual(atlas.getpixel((round(u * atlas.width) + 16, round(v * atlas.height) + 16)), (255, 0, 0, 255))
            self.assertFalse((directory / 'escape.png').exists())
            self.assertFalse((destination / 'client.class').exists())
            server = LiveServer(assets_directory=destination).start()
            try:
                with urllib.request.urlopen(server.base + '/api/assets') as response:
                    status = json.load(response)
                self.assertTrue(status['available'])
                self.assertEqual(status['client_sha1'], 'fixture-only')
                with urllib.request.urlopen(server.base + '/minecraft-assets/textures/block/stone.png') as response:
                    self.assertEqual(response.read(), png.getvalue())
            finally:
                server.stop()
            with self.assertRaises(ValueError):
                package(client, directory, {})
