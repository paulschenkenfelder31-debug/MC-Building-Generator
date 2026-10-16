"""Deterministic geometry primitives. Coordinates use Minecraft's Y-up convention."""
import math
import random

from .model import state, World
from .catalog import BLOCKS, canonical_state, split_state, format_state


PALETTES = {
    'medieval': {'wall': 'white_terracotta', 'beam': 'spruce_log', 'floor': 'spruce_planks', 'roof': 'deepslate_tiles', 'stair': 'deepslate_tile_stairs'},
    'modern': {'wall': 'white_concrete', 'beam': 'smooth_quartz', 'floor': 'oak_planks', 'roof': 'smooth_quartz', 'stair': 'quartz_stairs'},
    'japanese': {'wall': 'white_terracotta', 'beam': 'dark_oak_log', 'floor': 'dark_oak_planks', 'roof': 'polished_blackstone_bricks', 'stair': 'polished_blackstone_brick_stairs'},
}


def stair(name, facing):
    block, props = split_state(canonical_state(name))
    values = dict(facing=facing, half='bottom', shape='straight', waterlogged='false')
    props.update({k: v for k, v in values.items() if v in BLOCKS[block]['properties'].get(k, [])})
    return format_state(block, props)


def beam(name, axis='y'):
    block, props = split_state(canonical_state(name))
    if 'axis' in props:
        props['axis'] = axis
    return format_state(block, props)


def foundation(world, x, z, width, depth, rng):
    for xx in range(x, x + width):
        for zz in range(z, z + depth):
            for yy in (2, 3):
                world.set(xx, yy, zz, rng.choice(['stone_bricks'] * 7 + ['cobblestone', 'mossy_stone_bricks']))


def shell(world, x, z, width, depth, floors, palette, style):
    for level in range(floors):
        floor_y = 4 + level * 5
        world.box(x, floor_y, z, x + width - 1, floor_y, z + depth - 1, palette['floor'])
        for yy in range(floor_y + 1, floor_y + 5):
            for xx in range(x, x + width):
                for zz in (z, z + depth - 1):
                    is_beam = xx in (x, x + width - 1) or (xx - x) % 5 == 0 or yy == floor_y + 4
                    window = 1 <= (xx - x) % 5 <= 3 and floor_y + 2 <= yy <= floor_y + 3 and x < xx < x + width - 1
                    material = beam(palette['beam']) if is_beam else 'glass' if window else palette['wall']
                    world.set(xx, yy, zz, material)
            for zz in range(z + 1, z + depth - 1):
                for xx in (x, x + width - 1):
                    is_beam = (zz - z) % 5 == 0 or yy == floor_y + 4
                    window = 1 <= (zz - z) % 5 <= 3 and floor_y + 2 <= yy <= floor_y + 3
                    world.set(xx, yy, zz, beam(palette['beam']) if is_beam else 'glass' if window else palette['wall'])
        if style != 'modern':
            # Projecting floor bands give the facade depth without filling windows.
            for xx in range(x - 1, x + width + 1):
                for zz in (z - 1, z + depth):
                    world.set(xx, floor_y, zz, palette['floor'])
    ceiling = 4 + floors * 5
    world.box(x, ceiling, z, x + width - 1, ceiling, z + depth - 1, palette['floor'])


def gable_roof(world, x, z, width, depth, base_y, palette):
    for xx in range(x - 2, x + width + 2):
        inset = min(xx - (x - 2), x + width + 1 - xx)
        yy = base_y + math.ceil(inset * .75)
        facing = 'east' if xx < x + width / 2 else 'west'
        material = stair(palette['stair'], facing)
        if abs(xx - (x + (width - 1) / 2)) < 1:
            material = palette['roof']
        for zz in range(z - 2, z + depth + 2):
            world.set(xx, yy, zz, material)
        if x <= xx < x + width:
            for zz in (z, z + depth - 1):
                for gy in range(base_y, yy):
                    world.set(xx, gy, zz, beam(palette['beam']) if xx == x + width // 2 or (xx - x) % 5 == 0 else palette['wall'])
    if width >= 15:
        center = x + width // 2
        for zz in (z, z + depth - 1):
            world.box(center - 1, base_y + 2, zz, center + 1, base_y + 3, zz, 'glass')
            world.set(center, base_y + 4, zz, 'glass')
        # A supported chimney penetrates the roof rather than floating above it.
        cx, cz = x + 3, z + depth - 5
        world.box(cx, base_y, cz, cx + 1, base_y + 8, cz + 1, 'stone_bricks')


def hip_roof(world, x, z, width, depth, base_y, palette):
    rise = max(3, min(width, depth) // 3)
    for level in range(rise + 1):
        x1, x2 = x - 2 + level, x + width + 1 - level
        z1, z2 = z - 2 + level, z + depth + 1 - level
        y = base_y + level
        if x1 > x2 or z1 > z2:
            break
        if level == rise:
            world.box(x1, y, z1, x2, y, z2, palette['roof'])
        else:
            for xx in range(x1, x2 + 1):
                world.set(xx, y, z1, stair(palette['stair'], 'south'))
                world.set(xx, y, z2, stair(palette['stair'], 'north'))
            for zz in range(z1 + 1, z2):
                world.set(x1, y, zz, stair(palette['stair'], 'east'))
                world.set(x2, y, zz, stair(palette['stair'], 'west'))


def flat_roof(world, x, z, width, depth, y, palette):
    world.box(x - 1, y, z - 1, x + width, y, z + depth, palette['roof'])
    for xx in range(x, x + width):
        for zz in (z, z + depth - 1):
            world.set(xx, y + 1, zz, 'glass')
    for zz in range(z + 1, z + depth - 1):
        for xx in (x, x + width - 1):
            world.set(xx, y + 1, zz, 'glass')


def doorway(world, x, z, base_y):
    for half, y in [('lower', base_y + 1), ('upper', base_y + 2)]:
        world.set(x, y, z, state('spruce_door', facing='north', half=half, hinge='left', open='false', powered='false'))
    # Covered stoop and steps down to the terrain surface (y=1).
    for offset, y in ((1, 4), (2, 3), (3, 2)):
        world.box(x - 1, 0, z - offset, x + 1, y - 1, z - offset, 'stone_bricks')
        for xx in range(x - 1, x + 2):
            world.set(xx, y, z - offset, stair('stone_brick_stairs', 'south'))


def interiors(world, x, z, width, depth, floors, palette):
    for level in range(floors):
        y = 4 + level * 5
        world.box(x + 2, y + 1, z + 2, x + 5, y + 2, z + 2, 'bookshelf')
        world.set(x + 2, y + 1, z + 2, 'crafting_table')
        world.box(x + 4, y + 1, z + 4, x + 6, y + 1, z + 5, palette['floor'])
        for xx in (x + 4, x + 6):
            world.set(xx, y + 1, z + 3, stair('spruce_stairs', 'south'))
        if level < floors - 1:
            sx, sz = x + width - 8, z + depth - 4
            for step in range(5):
                # Stringers directly below each step leave clearance for the flight below.
                for zz in (sz, sz + 1):
                    if step:
                        world.set(sx + step, y + step, zz, palette['floor'])
                    world.set(sx + step, y + step + 1, zz, stair('spruce_stairs', 'east'))
                    world.box(sx + step, y + step + 2, zz, sx + step, y + step + 3, zz, 'air')


def tree(world, x, z, height):
    world.box(x, 2, z, x, height + 1, z, state('oak_log', axis='y'))
    for y in range(height, height + 3):
        radius = 2 if y < height + 2 else 1
        for dx in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                if abs(dx) + abs(dz) <= radius + 1 and (x + dx, y, z + dz) not in world.blocks:
                    world.set(x + dx, y, z + dz, state('oak_leaves', persistent='true', distance='1'))


def generate(spec):
    world = World()
    rng = random.Random(spec.seed)
    palette = PALETTES[spec.style] | spec.palette
    x, z = 6, 6
    w, d = spec.width, spec.depth
    if spec.terrain:
        world.box(0, 0, 0, w + 11, 0, d + 11, 'dirt')
        world.box(0, 1, 0, w + 11, 1, d + 11, 'grass_block')
    main_w = w - 7 if spec.tower else w
    foundation(world, x, z, main_w, d, rng)
    shell(world, x, z, main_w, d, spec.floors, palette, spec.style)
    roof_y = 4 + spec.floors * 5
    roof = {'medieval': gable_roof, 'japanese': hip_roof, 'modern': flat_roof}[spec.style]
    roof(world, x, z, main_w, d, roof_y, palette)
    interiors(world, x, z, main_w, d, spec.floors, palette)
    entrance = x + main_w // 2
    doorway(world, entrance, z, 4)
    if spec.tower:
        tx, tz, tw = x + w - 10, z + d - 11, 10
        # Clear intersecting main-roof blocks before creating the taller tower.
        world.box(tx, 5, tz, tx + tw - 1, roof_y + main_w, tz + tw - 1, 'air')
        foundation(world, tx, tz, tw, tw, rng)
        shell(world, tx, tz, tw, tw, spec.floors + 2, palette, 'medieval')
        hip_roof(world, tx, tz, tw, tw, roof_y + 10, palette)
        # Connect the tower on each shared storey; upper tower is reached by its own flight.
        for level in range(spec.floors):
            y = 4 + level * 5
            world.box(tx, y + 1, tz + 3, tx, y + 3, tz + 4, 'air')
            world.box(tx - 1, y, tz + 3, tx + 1, y, tz + 4, palette['floor'])
        interiors(world, tx, tz, tw, tw, spec.floors + 2, palette)
    if spec.terrain:
        world.box(entrance - 1, 1, 0, entrance + 1, 1, z - 4, 'cobblestone')
        tree(world, 2, d + 7, 5)
        tree(world, w + 9, 3, 4)
    return world
