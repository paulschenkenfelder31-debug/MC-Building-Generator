from collections import Counter
from dataclasses import asdict, dataclass, field
from .catalog import AIR, BLOCKS, VERSION, DATA_VERSION, canonical_state, split_state, format_state


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
    palette: dict = field(default_factory=dict)

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
        if not isinstance(data['palette'], dict) or set(data['palette']) - {'wall', 'beam', 'floor', 'roof', 'stair'}:
            raise ValueError('Palette roles: wall, beam, floor, roof, stair.')
        data['palette'] = {key: canonical_state(value) for key, value in data['palette'].items()}
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
        try:
            block = canonical_state(block)
        except ValueError:
            pass
        if block in AIR or block == 'air':
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


def validate(world):
    errors = []
    for (x, y, z), block in world.blocks.items():
        try:
            canonical = canonical_state(block)
            name, props = split_state(canonical)
        except ValueError as error:
            errors.append(str(error))
            continue
        if name.endswith('_door') and not name.endswith('_trapdoor'):
            other_y = y + (1 if props['half'] == 'lower' else -1)
            expected = format_state(name, props | {'half': 'upper' if props['half'] == 'lower' else 'lower'})
            other = world.blocks.get((x, other_y, z), 'air')
            try:
                matches = canonical_state(other) == expected
            except ValueError:
                matches = False
            if not matches:
                errors.append(f'Door pair missing at {x},{y},{z}')
    return {
        'passed': not errors, 'errors': errors[:30],
        'checks': [f'Java {VERSION}: full {len(BLOCKS):,}-block registry', 'Block-state properties', 'Two-block door pairs'],
        'limitations': ['Does not simulate lighting, navigation, gravity, or neighbor updates. Block-entity inventories and text are not exported.'],
    }
