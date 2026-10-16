"""Bounded, immutable build edits in the coordinates shown in the preview."""
from .catalog import BLOCKS, canonical_state, format_state, split_state
from .model import World


def partner(pos, value):
    name, props = split_state(canonical_state(value))
    x, y, z = pos
    if props.get('half') in ('lower', 'upper'):
        upper = props['half'] == 'upper'
        return (x, y + (-1 if upper else 1), z), format_state(name, props | {'half': 'lower' if upper else 'upper'})
    if name.endswith('_bed'):
        dx, dz = {'north': (0, -1), 'south': (0, 1), 'east': (1, 0), 'west': (-1, 0)}[props['facing']]
        head = props['part'] == 'head'
        return (x + dx * (-1 if head else 1), y, z + dz * (-1 if head else 1)), format_state(name, props | {'part': 'foot' if head else 'head'})


def check_position(pos):
    if len(pos) != 3 or any(type(n) is not int or not 0 <= n <= 127 for n in pos):
        raise ValueError('Coordinates must be integers from 0 to 127.')


def edit_world(original, changes=None, replace=None):
    world = World()
    _, world.blocks = original.normalized()
    if changes is None:
        changes = []
    if not isinstance(changes, list) or len(changes) > 256 or (not changes and not replace):
        raise ValueError('Supply 1–256 block changes or a material replacement.')
    if replace is not None:
        if not isinstance(replace, dict) or set(replace) != {'from', 'to'}:
            raise ValueError('Replacement needs from and to block states.')
        source, _ = split_state(canonical_state(replace['from']))
        target, target_props = split_state(canonical_state(replace['to']))
        for pos, value in list(world.blocks.items()):
            name, props = split_state(value)
            if name == source:
                compatible = {k: v for k, v in props.items() if v in BLOCKS[target]['properties'].get(k, [])}
                world.set(*pos, format_state(target, target_props | compatible))
    for change in changes:
        if not isinstance(change, dict) or set(change) != {'x', 'y', 'z', 'block'}:
            raise ValueError('Each change needs x, y, z, block (air removes a block).')
        pos = tuple(change[k] for k in ('x', 'y', 'z'))
        check_position(pos)
        value = canonical_state(change['block'])
        # Remove an old two-block object as a unit before placing its replacement.
        old = world.blocks.get(pos, 'minecraft:air')
        other = partner(pos, old)
        if other and world.blocks.get(other[0]) == other[1]:
            world.set(*other[0], 'air')
        other = partner(pos, value)
        if other:
            check_position(other[0])
            occupied = world.blocks.get(other[0], 'minecraft:air')
            occupied_partner = partner(other[0], occupied)
            if occupied_partner and occupied_partner[0] != pos:
                raise ValueError('The paired block would intersect another two-block object.')
            world.set(*other[0], other[1])
        world.set(*pos, value)
    dimensions, _ = world.normalized()
    if max(dimensions) > 128 or len(world.blocks) > 150000:
        raise ValueError('Edited builds are limited to 128 blocks per axis and 150,000 placed blocks.')
    return world
