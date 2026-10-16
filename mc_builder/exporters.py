"""Sponge schematic v2 and Litematica v6 exports, using Minecraft Y/Z/X indexing."""
import gzip
import io
import math
import time

import nbtlib
import numpy as np
from nbtlib import tag as t

from .model import DATA_VERSION


def compressed(root, root_name=''):
    buffer = io.BytesIO()
    nbtlib.File(root, root_name=root_name).write(buffer)
    return gzip.compress(buffer.getvalue(), mtime=0)


def varint(value):
    output = bytearray()
    while value > 127:
        output.append((value & 127) | 128)
        value >>= 7
    output.append(value)
    return output


def ordered(world):
    dimensions, blocks = world.normalized()
    palette = ['minecraft:air'] + sorted(set(blocks.values()))
    lookup = {name: i for i, name in enumerate(palette)}
    width, height, depth = dimensions
    values = [lookup[blocks.get((x, y, z), 'minecraft:air')] for y in range(height) for z in range(depth) for x in range(width)]
    return dimensions, blocks, palette, values


def schematic(world, name):
    (width, height, depth), _, palette, values = ordered(world)
    data = bytearray()
    for value in values:
        data.extend(varint(value))
    return compressed({
        'Version': t.Int(2), 'DataVersion': t.Int(DATA_VERSION),
        'Width': t.Short(width), 'Height': t.Short(height), 'Length': t.Short(depth),
        'Offset': t.IntArray([0, 0, 0]),
        'PaletteMax': t.Int(len(palette)),
        'Palette': t.Compound({block: t.Int(index) for index, block in enumerate(palette)}),
        'BlockData': t.ByteArray(np.frombuffer(bytes(data), dtype=np.int8)),
        'BlockEntities': t.List[t.Compound]([]), 'Entities': t.List[t.Compound]([]),
        'Metadata': t.Compound({'Name': t.String(name), 'Author': t.String('MC Building Generator')}),
    }, 'Schematic')


def palette_entry(block):
    name, _, raw = block.partition('[')
    entry = {'Name': t.String(name)}
    if raw:
        entry['Properties'] = t.Compound({k: t.String(v) for k, v in (item.split('=') for item in raw[:-1].split(','))})
    return t.Compound(entry)


def pack_states(values, bits):
    # Litematica uses a continuous bit stream: entries may straddle 64-bit words.
    words = [0] * math.ceil(len(values) * bits / 64)
    for index, value in enumerate(values):
        bit = index * bits
        word, shift = divmod(bit, 64)
        words[word] |= value << shift & ((1 << 64) - 1)
        if shift + bits > 64:
            words[word + 1] |= value >> (64 - shift)
    return [word if word < 1 << 63 else word - (1 << 64) for word in words]


def litematic(world, name):
    (width, height, depth), blocks, palette, values = ordered(world)
    size = t.Compound({'x': t.Int(width), 'y': t.Int(height), 'z': t.Int(depth)})
    now = int(time.time() * 1000)
    return compressed({
        'Version': t.Int(6), 'SubVersion': t.Int(1), 'MinecraftDataVersion': t.Int(DATA_VERSION),
        'Metadata': t.Compound({
            'Name': t.String(name), 'Author': t.String('MC Building Generator'),
            'Description': t.String('Procedurally generated building; review before placement.'),
            'RegionCount': t.Int(1), 'TimeCreated': t.Long(now), 'TimeModified': t.Long(now),
            'TotalBlocks': t.Int(len(blocks)), 'TotalVolume': t.Int(len(values)), 'EnclosingSize': size,
        }),
        'Regions': t.Compound({'Building': t.Compound({
            'Position': t.Compound({'x': t.Int(0), 'y': t.Int(0), 'z': t.Int(0)}), 'Size': size,
            'BlockStatePalette': t.List[t.Compound]([palette_entry(block) for block in palette]),
            'BlockStates': t.LongArray(pack_states(values, max(2, (len(palette) - 1).bit_length()))),
            'Entities': t.List[t.Compound]([]), 'TileEntities': t.List[t.Compound]([]),
            'PendingBlockTicks': t.List[t.Compound]([]), 'PendingFluidTicks': t.List[t.Compound]([]),
        })}),
    })
