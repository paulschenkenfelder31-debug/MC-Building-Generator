import * as THREE from 'three';

export const FACE_DATA = [
  ['east', [1,0,0], [[1,0,0],[1,1,0],[1,1,1],[1,0,1]]],
  ['west', [-1,0,0], [[0,0,1],[0,1,1],[0,1,0],[0,0,0]]],
  ['up', [0,1,0], [[0,1,1],[1,1,1],[1,1,0],[0,1,0]]],
  ['down', [0,-1,0], [[0,0,0],[1,0,0],[1,0,1],[0,0,1]]],
  ['south', [0,0,1], [[1,0,1],[1,1,1],[0,1,1],[0,0,1]]],
  ['north', [0,0,-1], [[0,0,0],[0,1,0],[1,1,0],[1,0,0]]],
];
const strip = value => value?.replace('minecraft:', '');
const axis = { x: new THREE.Vector3(1,0,0), y: new THREE.Vector3(0,1,0), z: new THREE.Vector3(0,0,1) };
const radians = degrees => degrees * Math.PI / 180;

export class BlockModels {
  constructor(library) { Object.assign(this, library); this.cache = new Map(); this.parents = new Map(); }
  resolve(name, chain = new Set()) {
    name = strip(name);
    if (this.parents.has(name)) return this.parents.get(name);
    if (chain.has(name)) return {};
    chain.add(name);
    const own = this.models[name] || {};
    const parent = own.parent ? this.resolve(own.parent, chain) : {};
    const model = { ...parent, ...own, textures: { ...parent.textures, ...own.textures } };
    this.parents.set(name, model); return model;
  }
  texture(value, model) {
    const seen = new Set();
    while (value?.startsWith('#') && !seen.has(value)) { seen.add(value); value = model.textures?.[value.slice(1)]; }
    return strip(value);
  }
  matches(condition, props) {
    if (!condition) return true;
    if (condition.OR) return condition.OR.some(c => this.matches(c, props));
    if (condition.AND) return condition.AND.every(c => this.matches(c, props));
    return Object.entries(condition).every(([key, value]) => String(value).split('|').includes(props[key]));
  }
  applications(state) {
    const [name, raw] = strip(state).split('[');
    const props = Object.fromEntries((raw?.replace(']', '').split(',') || []).map(v => v.split('=')));
    const definition = this.blockstates[name];
    if (!definition) return [];
    const apps = [];
    for (const [key, apply] of Object.entries(definition.variants || {})) {
      if (!key || this.matches(Object.fromEntries(key.split(',').map(p => p.split('='))), props)) {
        apps.push(Array.isArray(apply) ? apply[0] : apply); break;
      }
    }
    for (const part of definition.multipart || []) if (this.matches(part.when, props)) apps.push(Array.isArray(part.apply) ? part.apply[0] : part.apply);
    return apps;
  }
  icon(state) {
    for (const app of this.applications(state)) {
      const model = this.resolve(app.model);
      const texture = this.texture(model.textures?.particle || Object.values(model.textures || {})[0], model);
      if (this.textures[texture]) return `/minecraft-assets/textures/${texture}.png`;
    }
    return null;
  }
  faces(state) {
    if (this.cache.has(state)) return this.cache.get(state);
    const faces = [];
    const baseName = strip(state).split('[')[0];
    if (['air', 'cave_air', 'void_air', 'structure_void', 'light', 'barrier'].includes(baseName)) return [];
    const apps = this.applications(state);
    for (const app of apps) {
      const model = this.resolve(app.model);
      for (const element of model.elements || []) {
        const from = element.from.map(n => n / 16), to = element.to.map(n => n / 16);
        const rotate = point => {
          let p = new THREE.Vector3(...point);
          if (element.rotation) {
            const r = element.rotation, origin = new THREE.Vector3(...r.origin.map(n => n / 16));
            p.sub(origin);
            if (r.rescale) {
              const scale = 1 / Math.cos(radians(r.angle));
              for (const dim of ['x', 'y', 'z']) if (dim !== r.axis) p[dim] *= scale;
            }
            p.applyAxisAngle(axis[r.axis], radians(r.angle)).add(origin);
          }
          return p.subScalar(.5).applyAxisAngle(axis.x, radians(-(app.x || 0)))
            .applyAxisAngle(axis.y, radians(-(app.y || 0))).addScalar(.5);
        };
        for (const [name, normal, vertices] of FACE_DATA) {
          const face = element.faces?.[name]; if (!face) continue;
          const texture = this.textures[this.texture(face.texture, model)];
          const v = vertices.map(vertex => rotate(vertex.map((n, i) => from[i] + n * (to[i] - from[i]))));
          const n = new THREE.Vector3().subVectors(v[1], v[0]).cross(new THREE.Vector3().subVectors(v[2], v[0])).normalize();
          let cull = null;
          if (face.cullface) {
            const direction = FACE_DATA.find(f => f[0] === face.cullface)?.[1];
            if (direction) cull = new THREE.Vector3(...direction).applyAxisAngle(axis.x, radians(-(app.x || 0))).applyAxisAngle(axis.y, radians(-(app.y || 0))).toArray().map(Math.round);
          }
          const f = element.from, t = element.to;
          const defaults = {
            down: [f[0], 16-t[2], t[0], 16-f[2]], up: [f[0], f[2], t[0], t[2]],
            north: [16-t[0], 16-t[1], 16-f[0], 16-f[1]], south: [f[0], 16-t[1], t[0], 16-f[1]],
            west: [f[2], 16-t[1], t[2], 16-f[1]], east: [16-t[2], 16-t[1], 16-f[2], 16-f[1]],
          };
          const [u1, v1, u2, v2] = face.uv || defaults[name];
          // Vertex order differs between vertical and horizontal Minecraft faces.
          let uv = ['up', 'down'].includes(name) ? [[u1,v2],[u2,v2],[u2,v1],[u1,v1]] : [[u2,v2],[u2,v1],[u1,v1],[u1,v2]];
          if (name === 'north' || name === 'west') uv = [[u1,v2],[u1,v1],[u2,v1],[u2,v2]];
          const turns = (face.rotation || 0) / 90;
          uv = uv.map((_, i) => uv[(i + turns) % 4]);
          faces.push({ v: v.map(p => p.toArray()), n: n.toArray(), cull,
            uv: uv.map(([u,w]) => texture ? [texture[0] + u/16*texture[2], 1-texture[1]-w/16*texture[3]] : [0,0]),
            textured: !!texture, tint: face.tintindex !== undefined });
        }
      }
    }
    // Fluids and block entities are engine-rendered, outside vanilla JSON models.
    if (!faces.length) {
      let textureName = `block/${baseName}`;
      if (baseName === 'water' || baseName === 'lava') textureName += '_still';
      const particle = apps.map(app => { const model = this.resolve(app.model); return this.texture(model.textures?.particle, model); }).find(name => this.textures[name]);
      const texture = this.textures[particle || textureName];
      for (const [, n, v] of FACE_DATA) faces.push({ v, n, cull: n,
        uv: [[0,1],[0,0],[1,0],[1,1]].map(([u,w]) => texture ? [texture[0]+u*texture[2], 1-texture[1]-w*texture[3]] : [0,0]),
        textured: !!texture, tint: baseName === 'water' });
    }
    this.cache.set(state, faces); return faces;
  }
}
