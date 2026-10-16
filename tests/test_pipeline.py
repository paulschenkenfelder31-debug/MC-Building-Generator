import gzip
import io
import json
import tempfile
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

import nbtlib
from litemapy import Region, Schematic

from mc_builder.exporters import litematic, pack_states, schematic, varint
from mc_builder.generator import generate
from mc_builder.model import BuildSpec, validate, World
from mc_builder.planner import plan
from server_test_support import LiveServer


def read_nbt(data):
    return nbtlib.File.parse(io.BytesIO(gzip.decompress(data)))


def read_varints(data):
    output, value, shift = [], 0, 0
    for byte in data:
        byte = int(byte) & 255
        value |= (byte & 127) << shift
        if byte & 128:
            shift += 7
        else:
            output.append(value)
            value, shift = 0, 0
    if shift:
        raise AssertionError('Truncated VarInt')
    return output


def unpack_states(data, count, bits):
    words = [int(n) & ((1 << 64) - 1) for n in data]
    result = []
    for i in range(count):
        word, shift = divmod(i * bits, 64)
        value = words[word] >> shift
        if shift + bits > 64:
            value |= words[word + 1] << (64 - shift)
        result.append(value & ((1 << bits) - 1))
    return result


class PlannerTests(unittest.TestCase):
    def test_prompt_parameters_and_overrides(self):
        spec, meta = plan('A modern 33×21 villa with 3 floors', {'seed': 123})
        self.assertEqual((spec.style, spec.width, spec.depth, spec.floors, spec.tower, spec.seed), ('modern', 33, 21, 3, False, 123))
        self.assertEqual(meta['mode'], 'offline')
        spec, _ = plan('Japanese 27x23 temple. No terrain.')
        self.assertEqual(spec.style, 'japanese')
        self.assertFalse(spec.terrain)

    def test_untrusted_parameters_rejected(self):
        for overrides in ({'width': 200}, {'width': True}, {'style': '<script>'}, {'floors': 0}, {'terrain': 'false'}, {'seed': -1}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                plan('A house', overrides)
        for prompt in ('', ' ' * 3, 'x' * 2001):
            with self.assertRaises(ValueError):
                plan(prompt)

    @patch.dict('os.environ', {}, clear=True)
    def test_ai_missing_key_is_explicit(self):
        with self.assertRaisesRegex(ValueError, 'OPENAI_API_KEY'):
            plan('A manor', mode='ai')

    @patch('mc_builder.planner.ai_plan')
    def test_ai_spec_is_validated_before_geometry(self, ai):
        ai.return_value = {'width': 10000}
        with self.assertRaises(ValueError):
            plan('A very big manor', mode='ai')


class GeneratorTests(unittest.TestCase):
    def test_styles_and_extreme_supported_sizes(self):
        for style in ('medieval', 'modern', 'japanese'):
            for width, depth, floors in ((15, 15, 1), (29, 25, 2), (65, 65, 3)):
                with self.subTest(style=style, width=width):
                    spec = BuildSpec.from_dict({'style': style, 'width': width, 'depth': depth, 'floors': floors})
                    world = generate(spec)
                    self.assertTrue(validate(world)['passed'])
                    self.assertGreater(len(world.blocks), 1000)
                    self.assertLess(len(world.blocks), 150000)
                    # The main entrance is a complete, north-facing door.
                    main_w = width - 7 if spec.tower else width
                    door = world.blocks[(6 + main_w // 2, 5, 6)]
                    self.assertIn('spruce_door', door)
                    self.assertIn('half=lower', door)

    def test_seed_reproducibility_and_variation(self):
        self.assertEqual(generate(BuildSpec()).blocks, generate(BuildSpec()).blocks)
        self.assertNotEqual(generate(BuildSpec()).blocks, generate(BuildSpec(seed=43)).blocks)

    def test_stairs_have_clear_headroom(self):
        world = generate(BuildSpec(floors=3))
        for (x, y, z), block in world.blocks.items():
            if 'minecraft:spruce_stairs' in block and 'facing=east' in block:
                for dy in (1, 2):
                    self.assertTrue((x, y + dy, z) not in world.blocks, f'Obstructed staircase at {x},{y},{z}')

    def test_invalid_states_and_broken_doors_fail(self):
        world = World()
        world.set(0, 0, 0, 'not_a_real_block')
        self.assertFalse(validate(world)['passed'])
        world = generate(BuildSpec())
        door = next(pos for pos, block in world.blocks.items() if 'half=upper' in block)
        del world.blocks[door]
        self.assertFalse(validate(world)['passed'])


class ExportTests(unittest.TestCase):
    def test_independent_sponge_reader(self):
        world = generate(BuildSpec())
        region, version = Region.from_sponge_nbt(read_nbt(schematic(world, 'Independent reader')))
        self.assertEqual(version, 5023)
        dimensions, blocks = world.normalized()
        self.assertEqual((region.width, region.height, region.length), dimensions)
        for pos, block in blocks.items():
            self.assertEqual(str(region[pos]), block)

    def test_independent_litematica_reader(self):
        world = generate(BuildSpec())
        with tempfile.NamedTemporaryFile(suffix='.litematic') as file:
            file.write(litematic(world, 'Independent reader'))
            file.flush()
            loaded = Schematic.load(file.name)
        region = loaded.regions['Building']
        dimensions, blocks = world.normalized()
        self.assertEqual((region.width, region.height, region.length), dimensions)
        for pos, block in blocks.items():
            self.assertEqual(str(region[pos]), block)

    def test_sponge_roundtrip_every_coordinate(self):
        world = generate(BuildSpec())
        root = read_nbt(schematic(world, 'Round-trip test'))
        self.assertEqual(root.root_name, 'Schematic')
        self.assertEqual(root['Version'], 2)
        dimensions, expected = world.normalized()
        self.assertEqual((root['Width'], root['Height'], root['Length']), dimensions)
        palette = {int(v): k for k, v in root['Palette'].items()}
        values = read_varints(root['BlockData'])
        self.assertEqual(len(values), dimensions[0] * dimensions[1] * dimensions[2])
        decoded = {}
        for i, value in enumerate(values):
            if value:
                decoded[(i % dimensions[0], i // (dimensions[0] * dimensions[2]), i // dimensions[0] % dimensions[2])] = palette[value]
        self.assertEqual(decoded, expected)

    def test_litematic_roundtrip_every_coordinate(self):
        world = generate(BuildSpec())
        root = read_nbt(litematic(world, 'Round-trip test'))
        self.assertEqual(root['Version'], 6)
        self.assertEqual(root['MinecraftDataVersion'], 5023)
        region = root['Regions']['Building']
        dimensions, expected = world.normalized()
        palette = []
        for block in region['BlockStatePalette']:
            props = block.get('Properties', {})
            palette.append(str(block['Name']) + ('[' + ','.join(f'{k}={v}' for k, v in sorted(props.items())) + ']' if props else ''))
        count = dimensions[0] * dimensions[1] * dimensions[2]
        values = unpack_states(region['BlockStates'], count, max(2, (len(palette) - 1).bit_length()))
        decoded = {(i % dimensions[0], i // (dimensions[0] * dimensions[2]), i // dimensions[0] % dimensions[2]): palette[v] for i, v in enumerate(values) if v}
        self.assertEqual(decoded, expected)
        self.assertEqual(root['Metadata']['TotalBlocks'], len(expected))

    def test_bit_packing_crosses_signed_word_boundaries(self):
        for bits in (2, 5, 7, 9):
            values = [i % (1 << bits) for i in range(400)]
            self.assertEqual(unpack_states(pack_states(values, bits), len(values), bits), values)
        self.assertEqual(read_varints(varint(16384)), [16384])

    def test_empty_world_rejected(self):
        with self.assertRaises(ValueError):
            schematic(World(), 'Empty')


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = LiveServer().start()
        cls.base = cls.server.base

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def post(self, data):
        request = urllib.request.Request(self.base + '/api/generate', data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
        return urllib.request.urlopen(request)

    def test_generate_then_download_all_formats(self):
        with self.post({'prompt': 'A modern 21x19 villa with 2 floors'}) as response:
            result = json.load(response)
        self.assertTrue(result['validation']['passed'])
        self.assertEqual(result['spec']['style'], 'modern')
        for fmt in ('schem', 'litematic', 'json'):
            with urllib.request.urlopen(f"{self.base}/api/builds/{result['id']}/{fmt}") as response:
                self.assertIn('attachment', response.headers['Content-Disposition'])
                data = response.read()
                if fmt == 'json':
                    self.assertEqual(json.loads(data)['block_count'], result['block_count'])
                else:
                    self.assertGreater(len(read_nbt(data)), 0)

    def test_malformed_and_oversized_requests(self):
        for data in ([], {'prompt': 'House', 'overrides': {'width': 1000}}, {'prompt': 'x' * 17000}):
            with self.subTest(data_type=type(data)), self.assertRaises(urllib.error.HTTPError) as caught:
                self.post(data)
            self.assertIn(caught.exception.code, (400, 413))

    def test_cross_origin_simple_post_cannot_trigger_generation(self):
        request = urllib.request.Request(self.base + '/api/generate', data=b'{"prompt":"House"}', headers={'Content-Type': 'text/plain'})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request)
        self.assertEqual(caught.exception.code, 415)


if __name__ == '__main__':
    unittest.main()
