import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const COLORS = {
  grass_block: '#799665', dirt: '#8b7254', stone: '#92988e', stone_bricks: '#969b91', mossy_stone_bricks: '#7a8768', cobblestone: '#858e80',
  spruce_planks: '#a17c50', spruce_log: '#5b4431', stripped_spruce_log: '#9e7b50', white_terracotta: '#d9c7aa', deepslate_tiles: '#49555c', deepslate_tile_stairs: '#49555c',
  glass: '#bad6d0', crafting_table: '#9a7348', bookshelf: '#987c50', spruce_door: '#79603e', spruce_stairs: '#a17c50', oak_leaves: '#648454', oak_log: '#735e3c',
  white_concrete: '#e9e7dc', gray_concrete: '#64696a', smooth_quartz: '#ece8da', quartz_stairs: '#ece8da', oak_planks: '#c8aa73', dark_oak_planks: '#6c4a33',
  dark_oak_log: '#463526', dark_oak_stairs: '#6c4a33', red_terracotta: '#ac5c45', polished_blackstone_bricks: '#454751', polished_blackstone_brick_stairs: '#454751', stone_brick_stairs: '#969b91',
};
const FACES = [
  { n: [1,0,0], v: [[1,0,0],[1,1,0],[1,1,1],[1,0,1]] },
  { n: [-1,0,0], v: [[0,0,1],[0,1,1],[0,1,0],[0,0,0]] },
  { n: [0,1,0], v: [[0,1,1],[1,1,1],[1,1,0],[0,1,0]] },
  { n: [0,-1,0], v: [[0,0,0],[1,0,0],[1,0,1],[0,0,1]] },
  { n: [0,0,1], v: [[1,0,1],[1,1,1],[0,1,1],[0,0,1]] },
  { n: [0,0,-1], v: [[0,0,0],[0,1,0],[1,1,0],[1,0,0]] },
];

export class Preview {
  constructor(container) {
    this.container = container;
    this.scene = new THREE.Scene(); this.scene.background = new THREE.Color('#e9ece2');
    this.renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.domElement.setAttribute('aria-label', 'Interactive 3D Minecraft building. Use the camera buttons and layer slider to inspect.');
    this.renderer.domElement.setAttribute('role', 'img');
    container.prepend(this.renderer.domElement);
    this.camera = new THREE.PerspectiveCamera(35, 1, .1, 1000);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true; this.controls.maxPolarAngle = Math.PI * .49;
    this.controls.minDistance = 8; this.controls.maxDistance = 300;
    this.scene.add(new THREE.AmbientLight('#ffffff', 1.8));
    const sun = new THREE.DirectionalLight('#fff5de', 2.6); sun.position.set(-40, 70, -30); this.scene.add(sun);
    const fill = new THREE.DirectionalLight('#c1d7df', .8); fill.position.set(30, 20, 40); this.scene.add(fill);
    this.grid = new THREE.GridHelper(180, 90, '#c9d0c0', '#d9dfd0'); this.grid.position.y = -.08; this.scene.add(this.grid);
    this.group = new THREE.Group(); this.scene.add(this.group);
    this.resize = new ResizeObserver(() => { const w = container.clientWidth, h = container.clientHeight; this.renderer.setSize(w, h); this.camera.aspect = w / h; this.camera.updateProjectionMatrix(); });
    this.resize.observe(container);
    this.renderer.setAnimationLoop(() => { this.controls.update(); this.renderer.render(this.scene, this.camera); });
  }

  colorFor(block) { return COLORS[block.replace('minecraft:', '').split('[')[0]] || '#999388'; }

  load(data) {
    this.data = data; this.setLayer(data.dimensions[1] - 1); this.setView('iso');
  }

  setLayer(layer) {
    while (this.group.children.length) { const mesh = this.group.children[0]; this.group.remove(mesh); mesh.geometry.dispose(); mesh.material.dispose(); }
    const { blocks, palette, dimensions } = this.data;
    const visible = new Map(blocks.filter(b => b[1] <= layer).map(b => [`${b[0]},${b[1]},${b[2]}`, b[3]]));
    const opaque = { p: [], n: [], c: [] }, glass = { p: [], n: [], c: [] };
    const colors = palette.map(b => new THREE.Color(this.colorFor(b)));
    const fullBlock = b => b && !b.includes('_stairs') && !b.includes('_door') && !b.includes('glass');
    const addBox = (target, x, y, z, id, min = [0,0,0], max = [1,1,1], cull = true) => {
      const color = colors[id].clone();
      const variation = 1 - ((x * 17 + z * 31 + y * 13) % 7) * .009;
      color.multiplyScalar(variation);
      for (const { n, v } of FACES) {
        const neighborId = visible.get(`${x+n[0]},${y+n[1]},${z+n[2]}`);
        const neighbor = neighborId === undefined ? '' : palette[neighborId];
        if (cull && (fullBlock(neighbor) || (palette[id].includes('glass') && neighbor.includes('glass')))) continue;
        for (const index of [0,1,2,0,2,3]) {
          const vertex = v[index];
          target.p.push(x + min[0] + vertex[0]*(max[0]-min[0]) - dimensions[0]/2, y + min[1] + vertex[1]*(max[1]-min[1]), z + min[2] + vertex[2]*(max[2]-min[2]) - dimensions[2]/2);
          target.n.push(...n); target.c.push(color.r, color.g, color.b);
        }
      }
    };
    for (const [x,y,z,id] of blocks) {
      if (y > layer) continue;
      const block = palette[id]; const target = block.includes('glass') ? glass : opaque;
      if (block.includes('_stairs')) {
        addBox(target, x,y,z,id, [0,0,0], [1,.5,1], false);
        const facing = /facing=(\w+)/.exec(block)?.[1];
        const min = [0,.5,0], max = [1,1,1];
        if (facing === 'east') min[0] = .5;
        if (facing === 'west') max[0] = .5;
        if (facing === 'south') min[2] = .5;
        if (facing === 'north') max[2] = .5;
        addBox(target,x,y,z,id,min,max,false);
      } else if (block.includes('_door')) addBox(target,x,y,z,id,[0,0,0],[1,1,.1875],false);
      else addBox(target,x,y,z,id);
    }
    for (const [data, transparent] of [[opaque, false], [glass, true]]) {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.Float32BufferAttribute(data.p, 3));
      geometry.setAttribute('normal', new THREE.Float32BufferAttribute(data.n, 3));
      geometry.setAttribute('color', new THREE.Float32BufferAttribute(data.c, 3));
      geometry.computeBoundingSphere();
      this.group.add(new THREE.Mesh(geometry, new THREE.MeshLambertMaterial({ vertexColors: true, transparent, opacity: transparent ? .42 : 1, depthWrite: !transparent })));
    }
  }

  setView(view) {
    if (!this.data) return;
    const [w,h,d] = this.data.dimensions;
    const radius = Math.max(w, d, h * 1.3) * 1.65 * Math.max(1, 1 / this.camera.aspect);
    this.controls.target.set(0, h * .32, 0);
    if (view === 'top') this.camera.position.set(.01, radius * 1.45, .01);
    else if (view === 'front') this.camera.position.set(0, h * .48, -radius * 1.4);
    else this.camera.position.set(-radius * .83, radius * .72, -radius * .96);
    this.controls.update();
  }

  snapshot() { this.renderer.render(this.scene, this.camera); return this.renderer.domElement.toDataURL('image/png'); }
}
