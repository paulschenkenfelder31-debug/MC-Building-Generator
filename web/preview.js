import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { BlockModels, FACE_DATA } from './block-models.js';

const COLORS = {
  grass_block: '#799665', dirt: '#8b7254', stone: '#92988e', stone_bricks: '#969b91', mossy_stone_bricks: '#7a8768', cobblestone: '#858e80',
  spruce_planks: '#a17c50', spruce_log: '#5b4431', stripped_spruce_log: '#9e7b50', white_terracotta: '#d9c7aa', deepslate_tiles: '#49555c', deepslate_tile_stairs: '#49555c',
  glass: '#bad6d0', crafting_table: '#9a7348', bookshelf: '#987c50', spruce_door: '#79603e', spruce_stairs: '#a17c50', oak_leaves: '#648454', oak_log: '#735e3c',
  white_concrete: '#e9e7dc', gray_concrete: '#64696a', smooth_quartz: '#ece8da', quartz_stairs: '#ece8da', oak_planks: '#c8aa73', dark_oak_planks: '#6c4a33',
  dark_oak_log: '#463526', dark_oak_stairs: '#6c4a33', red_terracotta: '#ac5c45', polished_blackstone_bricks: '#454751', polished_blackstone_brick_stairs: '#454751', stone_brick_stairs: '#969b91',
};

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
    const canvas = this.renderer.domElement;
    canvas.addEventListener('pointerdown', e => { this.pointerStart = [e.clientX, e.clientY]; });
    canvas.addEventListener('pointerup', e => {
      if (!this.onPick || !this.data || !this.pointerStart || Math.hypot(e.clientX-this.pointerStart[0], e.clientY-this.pointerStart[1]) > 4 || e.button !== 0) return;
      const rect = canvas.getBoundingClientRect(), ray = new THREE.Raycaster();
      ray.setFromCamera(new THREE.Vector2((e.clientX-rect.left)/rect.width*2-1, -(e.clientY-rect.top)/rect.height*2+1), this.camera);
      const hit = ray.intersectObjects(this.group.children)[0];
      if (hit) {
        const coords = hit.object.geometry.getAttribute('blockPosition');
        const i = hit.face.a;
        const normal = hit.face.normal.toArray();
        const strongest = normal.map(Math.abs).indexOf(Math.max(...normal.map(Math.abs)));
        this.onPick([coords.getX(i), coords.getY(i), coords.getZ(i)], normal.map((n, axis) => axis === strongest ? Math.sign(n) : 0));
      }
    });
    this.renderer.setAnimationLoop(() => { this.controls.update(); this.renderer.render(this.scene, this.camera); });
  }

  colorFor(block) { return COLORS[block.replace('minecraft:', '').split('[')[0]] || '#999388'; }

  load(data) {
    this.data = data; this.setLayer(data.dimensions[1] - 1); this.setView('iso');
  }

  async enableTextures(library) {
    const atlas = await new THREE.TextureLoader().loadAsync('/minecraft-assets/atlas.png');
    atlas.colorSpace = THREE.SRGBColorSpace; atlas.magFilter = THREE.NearestFilter;
    atlas.minFilter = THREE.NearestFilter; atlas.generateMipmaps = false;
    this.atlas = atlas; this.models = new BlockModels(library);
    if (this.data) this.setLayer(this.layer);
  }

  setLayer(layer) {
    this.layer = layer;
    while (this.group.children.length) { const mesh = this.group.children[0]; this.group.remove(mesh); mesh.geometry.dispose(); mesh.material.dispose(); }
    const { blocks, palette, dimensions } = this.data;
    const visible = new Map(blocks.filter(b => b[1] <= layer).map(b => [`${b[0]},${b[1]},${b[2]}`, b[3]]));
    const bucket = () => ({ p: [], n: [], c: [], uv: [], pos: [] });
    const buckets = { textured: bucket(), transparent: bucket(), plain: bucket() };
    const isTransparent = block => /glass|water(?:\[|$)|ice(?:\[|$)|slime_block|honey_block/.test(block);
    const facesById = palette.map(block => this.models?.faces(block) || FACE_DATA.map(([,n,v]) => ({ n, v, cull:n, textured:false })));
    const full = facesById.map((faces, id) => !/leaves|glass|water|ice|slime|honey|air|barrier|light(?:\[|$)/.test(palette[id]) && faces.length === 6 && faces.every(face => face.v.every(v => v.every(n => n === 0 || n === 1))));
    const colors = palette.map(b => new THREE.Color(this.colorFor(b)));
    for (const [x,y,z,id] of blocks) {
      if (y > layer) continue;
      const block = palette[id];
      for (const face of facesById[id]) {
        if (face.cull) {
          const n = face.cull;
          const neighborId = visible.get(`${x+n[0]},${y+n[1]},${z+n[2]}`);
          if (neighborId !== undefined && (full[neighborId] || (isTransparent(block) && palette[neighborId] === block))) continue;
        }
        const textured = !!face.textured && !!this.atlas;
        const target = textured ? (isTransparent(block) ? buckets.transparent : buckets.textured) : buckets.plain;
        const tint = block.includes('water') ? '#3f76e4' : /birch/.test(block) ? '#80a755' : /spruce/.test(block) ? '#619961' : '#8ebc59';
        const color = textured ? new THREE.Color(face.tint ? tint : '#ffffff') : colors[id];
        for (const index of [0,1,2,0,2,3]) {
          const vertex = face.v[index];
          target.p.push(x+vertex[0]-dimensions[0]/2, y+vertex[1], z+vertex[2]-dimensions[2]/2);
          target.n.push(...face.n); target.c.push(color.r, color.g, color.b);
          target.uv.push(...(face.uv?.[index] || [0,0])); target.pos.push(x,y,z);
        }
      }
    }
    for (const [kind, data] of Object.entries(buckets)) {
      if (!data.p.length) continue;
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.Float32BufferAttribute(data.p, 3));
      geometry.setAttribute('normal', new THREE.Float32BufferAttribute(data.n, 3));
      geometry.setAttribute('color', new THREE.Float32BufferAttribute(data.c, 3));
      geometry.setAttribute('uv', new THREE.Float32BufferAttribute(data.uv, 2));
      geometry.setAttribute('blockPosition', new THREE.Float32BufferAttribute(data.pos, 3));
      geometry.computeBoundingSphere();
      const transparent = kind === 'transparent';
      this.group.add(new THREE.Mesh(geometry, new THREE.MeshLambertMaterial({ vertexColors: true,
        map: kind === 'plain' ? null : this.atlas, side: THREE.DoubleSide, alphaTest: .1,
        transparent, opacity: transparent ? .72 : 1, depthWrite: !transparent })));
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
