import assert from 'node:assert/strict';
import test from 'node:test';
import { BlockModels, FACE_DATA } from '../web/block-models.js';

const cube = { textures: { all: 'minecraft:block/test', particle: '#all' }, elements: [{ from: [0,0,0], to: [16,16,16],
  faces: Object.fromEntries(FACE_DATA.map(([name]) => [name, { texture: '#all', cullface: name }])) }] };
const library = () => new BlockModels({ textures: { 'block/test': [.1,.2,.1,.1] },
  models: { 'block/cube': cube, 'block/child': { parent: 'minecraft:block/cube', textures: { all: '#other', other: 'minecraft:block/test' } },
    'block/slab': { parent: 'block/cube', elements: [{ ...cube.elements[0], to: [16,8,16] }] } },
  blockstates: { test: { variants: { 'axis=x': { model: 'block/child', x:90, y:90 }, 'axis=y': { model: 'block/child' } } },
    slab: { multipart: [{ when: { OR: [{ powered: 'true' }, { facing: 'north|south' }] }, apply: { model: 'block/slab' } }] } } });

test('inheritance, texture indirection, UVs, normals, and model cache', () => {
  const models = library(), faces = models.faces('minecraft:test[axis=y]');
  assert.equal(faces.length, 6);
  assert.equal(models.faces('minecraft:test[axis=y]'), faces);
  assert.equal(models.icon('minecraft:test[axis=y]'), '/minecraft-assets/textures/block/test.png');
  for (const face of faces) {
    assert.ok(face.textured);
    assert.ok(face.n.every((n,i) => Math.abs(n - face.cull[i]) < .00001));
    for (const [u,v] of face.uv) { assert.ok(u >= .1 && u <= .200001); assert.ok(v >= .699999 && v <= .8); }
  }
});

test('variant rotations transform geometry and culling normals together', () => {
  const faces = library().faces('minecraft:test[axis=x]');
  assert.equal(faces.length, 6);
  for (const face of faces) {
    assert.ok(face.n.every((n,i) => Math.abs(n - face.cull[i]) < .00001));
    assert.ok(face.v.every(vertex => vertex.every(n => n > -.00001 && n < 1.00001)));
  }
});

test('multipart conditions and non-cube geometry preserve slab height', () => {
  const models = library();
  const faces = models.faces('minecraft:slab[powered=false,facing=north]');
  assert.equal(faces.length, 6);
  assert.equal(Math.max(...faces.flatMap(face => face.v.map(vertex => vertex[1]))), .5);
  assert.ok(models.matches({ AND: [{ powered:'false' }, { facing:'east|west' }] }, { powered:'false', facing:'east' }));
  assert.equal(models.faces('minecraft:air').length, 0);
  assert.ok(models.faces('minecraft:unknown_entity').every(face => !face.textured));
});

test('Java 26.3 sprite objects resolve through inherited aliases without interrupting other blocks', () => {
  const models = library();
  models.models['block/glass'] = { parent: 'block/cube', textures: {
    all: { force_translucent: true, sprite: 'minecraft:block/test' },
  } };
  models.blockstates.glass = { variants: { '': { model: 'block/glass' } } };
  const faces = models.faces('minecraft:glass');
  assert.equal(faces.length, 6);
  assert.ok(faces.every(face => face.textured && face.translucent));
  assert.equal(models.icon('minecraft:glass'), '/minecraft-assets/textures/block/test.png');
  assert.ok(models.faces('minecraft:test[axis=y]').every(face => face.textured));
});

test('missing, malformed, and cyclic texture references do not abort a build', () => {
  const models = library();
  const model = { textures: { loop: '#other', other: '#loop', missing: '#absent',
    object: { sprite: { bad: true } }, number: 3, array: [] } };
  for (const value of ['#loop', '#missing', '#object', '#number', '#array', {}, 3, null]) {
    assert.equal(models.texture(value, model), undefined);
  }
  assert.equal(models.texture({ sprite: '#alias' }, { textures: { alias: 'minecraft:block/test' } }), 'block/test');
});

test('catalog icons use available sprites beyond the block atlas and item fallbacks', () => {
  const models = new BlockModels({ ...library(), texture_files: ['block/test', 'item/engine_block', 'entity/test'] });
  models.models['block/particle'] = { textures: { particle: { sprite: 'minecraft:entity/test' } } };
  models.blockstates.engine = { variants: { '': { model: 'block/particle' } } };
  assert.equal(models.icon('minecraft:engine'), '/minecraft-assets/textures/entity/test.png');
  assert.equal(models.icon('minecraft:engine_block'), '/minecraft-assets/textures/item/engine_block.png');
  assert.equal(models.icon('minecraft:not_present'), null);
});
