from collections import Counter
from dataclasses import asdict, dataclass
import re


DATA_VERSION = 3465  # Java Edition 1.20.1; all generated blocks exist in this version.
STYLES = ('medieval', 'modern', 'japanese')


@dataclass(frozen=True)
class BuildSpec:
    style: str = 'medieval'
    width: int = 29
    depth: int = 25
    floors: int = 2
    tower: bool = True
    terrain: bool = True
    seed: int = 42
    title: str = 'Timber & stone manor'

    @classmethod
    def from_dict(cls, values):
        if not isinstance(values, dict):
            raise ValueError('Design must be an object.')
        defaults = asdict(cls())
        data = {k: values.get(k, v) for k, v in defaults.items()}
        if data['style'] not in STYLES:
            raise ValueError('Choose medieval, modern, or japanese.')
        for key, low, high in [('width', 15, 65), ('depth', 15, 65), ('floors', 1, 3), ('seed', 0, 2147483647)]:
            value = data[key]
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f'{key} must be an integer from {low} to {high}.')
        for key in ('tower', 'terrain'):
            if type(data[key]) is not bool:
                raise ValueError(f'{key} must be true or false.')
        if not isinstance(data['title'], str) or not 1 <= len(data['title']) <= 100:
            raise ValueError('Title must contain 1–100 characters.')
        data['tower'] = data['tower'] and data['width'] >= 25 and data['style'] == 'medieval'
        return cls(**data)


def state(block, **properties):
    name = block if block.startswith('minecraft:') else f'minecraft:{block}'
    if properties:
        name += '[' + ','.join(f'{k}={v}' for k, v in sorted(properties.items())) + ']'
    return name


class World:
    def __init__(self):
        self.blocks = {}

    def set(self, x, y, z, block):
        pos = (int(x), int(y), int(z))
        if block == 'air' or block == 'minecraft:air':
            self.blocks.pop(pos, None)
        else:
            self.blocks[pos] = block if block.startswith('minecraft:') else state(block)

    def box(self, x1, y1, z1, x2, y2, z2, block):
        for y in range(y1, y2 + 1):
            for z in range(z1, z2 + 1):
                for x in range(x1, x2 + 1):
                    self.set(x, y, z, block)

    def normalized(self):
        if not self.blocks:
            raise ValueError('Cannot export an empty structure.')
        minimum = tuple(min(p[i] for p in self.blocks) for i in range(3))
        dimensions = tuple(max(p[i] for p in self.blocks) - minimum[i] + 1 for i in range(3))
        blocks = {tuple(p[i] - minimum[i] for i in range(3)): block for p, block in self.blocks.items()}
        return dimensions, blocks

    def payload(self):
        dimensions, blocks = self.normalized()
        palette = ['minecraft:air'] + sorted(set(blocks.values()))
        ids = {block: index for index, block in enumerate(palette)}
        materials = Counter(b.split('[')[0] for b in blocks.values())
        return {
            'dimensions': list(dimensions),
            'palette': palette,
            'blocks': [[*p, ids[b]] for p, b in blocks.items()],
            'materials': [{'block': b, 'count': n} for b, n in materials.most_common()],
            'block_count': len(blocks),
        }


# The generator owns this small, versioned palette rather than trusting model block IDs.
SOLIDS = {
    'grass_block', 'dirt', 'stone', 'stone_bricks', 'mossy_stone_bricks', 'cobblestone',
    'spruce_planks', 'spruce_log', 'stripped_spruce_log', 'white_terracotta',
    'deepslate_tiles', 'glass', 'crafting_table', 'bookshelf', 'oak_leaves',
    'white_concrete', 'gray_concrete', 'smooth_quartz', 'oak_planks', 'oak_log',
    'dark_oak_planks', 'dark_oak_log', 'red_terracotta', 'polished_blackstone_bricks',
}
STAIRS = {'spruce_stairs', 'deepslate_tile_stairs', 'dark_oak_stairs', 'polished_blackstone_brick_stairs', 'quartz_stairs', 'stone_brick_stairs'}


def validate(world):
    errors = []
    for (x, y, z), block in world.blocks.items():
        match = re.fullmatch(r'minecraft:([a-z_]+)(?:\[([^\]]+)\])?', block)
        if not match:
            errors.append(f'Invalid state: {block}')
            continue
        name, raw = match.groups()
        props = dict(p.split('=', 1) for p in raw.split(',')) if raw else {}
        allowed = {}
        if name in STAIRS:
            allowed = {'facing': {'north', 'south', 'east', 'west'}, 'half': {'bottom', 'top'}, 'shape': {'straight'}, 'waterlogged': {'false'}}
        elif name == 'spruce_door':
            allowed = {'facing': {'north'}, 'half': {'lower', 'upper'}, 'hinge': {'left'}, 'open': {'false'}, 'powered': {'false'}}
            other_y = y + (1 if props.get('half') == 'lower' else -1)
            other = world.blocks.get((x, other_y, z), '')
            expected = block.replace('half=lower', 'half=upper') if props.get('half') == 'lower' else block.replace('half=upper', 'half=lower')
            if other != expected:
                errors.append(f'Door pair missing at {x},{y},{z}')
        elif name in ('spruce_log', 'stripped_spruce_log', 'dark_oak_log', 'oak_log'):
            allowed = {'axis': {'x', 'y', 'z'}}
        elif name == 'oak_leaves':
            allowed = {'persistent': {'true'}, 'distance': {'1'}}
        elif name not in SOLIDS:
            errors.append(f'Block outside supported palette: {name}')
        if set(props) != set(allowed) or any(v not in allowed.get(k, set()) for k, v in props.items()):
            errors.append(f'Unsupported block properties: {block}')
    return {
        'passed': not errors,
        'errors': errors[:30],
        'checks': ['Java 1.20.1 palette', 'Generated block-state properties', 'Two-block door pairs'],
        'limitations': ['Does not simulate Minecraft lighting, navigation, or neighbor updates.'],
    }
