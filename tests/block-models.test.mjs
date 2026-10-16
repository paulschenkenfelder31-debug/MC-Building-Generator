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
