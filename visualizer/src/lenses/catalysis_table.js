// The molecules level: the environment's table of catalysis, a row for each molecule type i and a
// column for each type j, the factor by which a molecule of type j in the assembly speeds the joining
// and the leaving of type i. A floor of cells, a stronger colour for a larger factor (on a
// logarithmic scale), with a column standing on each entry of at least TALL, as high as its
// logarithm: most factors are tiny, a few are very large. The leading types are marked on the edges.
// The table is the run's environment, never the assembly's state; the view computes no rate from it.

import * as THREE from "../three.js";
import { dataTexture, rampAt } from "./composition_marks.js";

export const TALL = 1; // log10: the entries of ten and more stand as columns

export class CatalysisTable {
  constructor(parent, environment, { size, centre, materials, leading }) {
    this.environment = environment;
    const n = environment.count;
    this.size = size;
    this.centre = centre;
    this.group = new THREE.Group();
    this.group.position.set(...centre);
    parent.add(this.group);
    this.texture = dataTexture(n, n);
    this.material = new THREE.MeshBasicMaterial({ map: this.texture, toneMapped: false });
    this.material.userData.noContact = true;
    this.floor = new THREE.Mesh(new THREE.PlaneGeometry(size, size), this.material);
    this.floor.rotation.x = -Math.PI / 2;
    this.floor.position.y = 0.02;
    this.floor.userData.pick = (hit) => {
      const j = Math.min(n - 1, Math.max(0, Math.floor(hit.uv.x * n))), i = Math.min(n - 1, Math.max(0, Math.floor((1 - hit.uv.y) * n)));
      return `assembly:entry:${environment.id}:${i}:${j}`;
    };
    this.group.add(this.floor);
    const cell = size / n;
    this.cell = cell;
    const tall = [];
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) if (environment.catalysis(i, j) >= TALL) tall.push([i, j]);
    this.tall = tall;
    this.columns = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), materials.column, Math.max(1, tall.length));
    this.columns.count = tall.length;
    this.columns.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(Math.max(1, tall.length) * 3).fill(1), 3);
    this.columns.userData.pick = (hit) => { const [i, j] = tall[hit.instanceId] || []; return i === undefined ? null : `assembly:entry:${environment.id}:${i}:${j}`; };
    this.group.add(this.columns);
    const dummy = new THREE.Object3D();
    tall.forEach(([i, j], index) => {
      const height = 0.28 * environment.catalysis(i, j);
      dummy.position.set(-size / 2 + (j + 0.5) * cell, height / 2 + 0.02, -size / 2 + (i + 0.5) * cell);
      dummy.scale.set(cell * 0.72, height, cell * 0.72);
      dummy.updateMatrix();
      this.columns.setMatrixAt(index, dummy.matrix);
    });
    this.columns.instanceMatrix.needsUpdate = true;
    this.columns.computeBoundingSphere();
    // The leading types along two edges: their row (down the left) and their column (along the far edge).
    this.marks = new THREE.Group();
    this.group.add(this.marks);
    this.markAt = [];
    const shapes = [new THREE.OctahedronGeometry(cell * 1.6), new THREE.BoxGeometry(cell * 2.2, cell * 2.2, cell * 2.2), new THREE.TetrahedronGeometry(cell * 1.9)];
    leading.forEach((type, slot) => {
      for (const [x, z] of [[-size / 2 - cell * 3, -size / 2 + (type + 0.5) * cell], [-size / 2 + (type + 0.5) * cell, -size / 2 - cell * 3]]) {
        const mark = new THREE.Mesh(shapes[slot], materials.leading[slot]);
        mark.position.set(x, cell * 1.6, z);
        mark.userData.pick = `assembly:type:${type}`;
        this.marks.add(mark);
      }
      this.markAt.push({ type, slot, row: new THREE.Vector3(centre[0] - size / 2 - cell * 3, centre[1], centre[2] - size / 2 + (type + 0.5) * cell) });
    });
  }

  draw(ramp, colours) {
    if (ramp === this.ramp) return;
    this.ramp = ramp;
    const n = this.environment.count, data = this.texture.image.data;
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
      const [r, g, b] = rampAt(ramp, (this.environment.catalysis(i, j) + 4) / 7);
      const o = ((n - 1 - i) * n + j) * 4; // type i down from the far edge, type j across
      data[o] = r; data[o + 1] = g; data[o + 2] = b; data[o + 3] = 255;
    }
    this.texture.needsUpdate = true;
    const colour = new THREE.Color();
    this.tall.forEach(([i, j], index) => {
      const [r, g, b] = rampAt(ramp, (this.environment.catalysis(i, j) + 4) / 7);
      colour.setRGB(r / 255, g / 255, b / 255, THREE.SRGBColorSpace);
      this.columns.setColorAt(index, colour);
    });
    if (this.columns.instanceColor) this.columns.instanceColor.needsUpdate = true;
  }

  /** Where entry (i, j) stands, for its label. */
  entryAt(i, j) {
    const s = this.size, cell = this.cell, height = Math.max(0, 0.28 * this.environment.catalysis(i, j));
    return new THREE.Vector3(this.centre[0] - s / 2 + (j + 0.5) * cell, this.centre[1] + height + 0.05, this.centre[2] - s / 2 + (i + 0.5) * cell);
  }

  dispose() {
    this.group.traverse((object) => object.geometry?.dispose?.());
    this.texture.dispose();
    this.material.dispose();
  }
}
