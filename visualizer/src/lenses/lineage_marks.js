// A lineage across its fissions, and its compositions as places in a map.
//
// The spine: one node for each fission, along the run's time; the daughter that carries on goes
// on along the spine, the other is a short stub ending in a faded bead (not followed). A node is
// filled where the run's analysis marks the fission inherited and a ring where it marks a break; a
// segment after a break is drawn thin. Where a run has no analysis, every node is plain.
//
// The map: each grown assembly is a point, joined in order by the lineage's trail. Its axes are the
// three directions along which the lineage's compositions differ most (principal components),
// worked out by the view: a layout, the picture's choice. A crowd of points is where the lineage
// stayed; it is ringed and named as a composome only where the run's analysis names one.

import * as THREE from "../three.js";

const dummy = new THREE.Object3D();

export class LineageSpine {
  constructor(parent, run, { xOf, y, z, materials }) {
    this.run = run;
    this.xOf = xOf;
    this.y = y;
    this.z = z;
    const n = run.fissionCount;
    this.nodes = new THREE.InstancedMesh(new THREE.SphereGeometry(0.09, 8, 6), materials.node, n);
    this.breaks = new THREE.InstancedMesh(new THREE.TorusGeometry(0.085, 0.025, 5, 12), materials.node, n);
    this.stubs = new THREE.InstancedMesh(new THREE.SphereGeometry(0.06, 6, 4), materials.stub, n);
    for (const mesh of [this.nodes, this.breaks, this.stubs]) { mesh.count = 0; mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage); mesh.frustumCulled = false; parent.add(mesh); }
    this.nodeK = []; this.breakK = [];
    const pick = (list) => (hit) => (list[hit.instanceId] ? `assembly:fission:${run.id}:${list[hit.instanceId]}` : null);
    this.nodes.userData.pick = pick(this.nodeK);
    this.breaks.userData.pick = pick(this.breakK);
    this.stubs.userData.unpickable = true;
    // The spine's segments and the stubs' stems: thick where inherited, thin after a break.
    const segment = (count) => {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(count * 6), 3));
      geometry.setDrawRange(0, 0);
      return geometry;
    };
    this.solid = new THREE.LineSegments(segment(n + 1), materials.spine);
    this.thin = new THREE.LineSegments(segment(n + 1), materials.spineThin);
    this.stems = new THREE.LineSegments(segment(n), materials.stem);
    for (const line of [this.solid, this.thin, this.stems]) { line.frustumCulled = false; line.userData.unpickable = true; parent.add(line); }
    this.key = "";
  }

  draw(upTo, progress, { chosen = null } = {}) {
    const key = `${upTo}:${progress.toFixed(3)}:${chosen}`;
    if (key === this.key) return;
    this.key = key;
    const { run, y, z } = this, n = run.fissionCount;
    let nodes = 0, breaks = 0, stubs = 0, solid = 0, thin = 0, stems = 0;
    this.nodeK.length = this.breakK.length = 0;
    const ps = this.solid.geometry.attributes.position.array, pt = this.thin.geometry.attributes.position.array, pm = this.stems.geometry.attributes.position.array;
    const start = this.xOf(0.35);
    // The founder's growth up to the first fission.
    const end1 = upTo >= 1 ? this.xOf(1) : start + (this.xOf(1) - start) * progress;
    ps.set([start, y, z, end1, y, z], 6 * solid++);
    for (let k = 1; k <= upTo; k++) {
      const x = this.xOf(k), mark = run.inherited(k);
      dummy.position.set(x, y, z);
      dummy.scale.setScalar(k === chosen ? 1.7 : 1);
      dummy.rotation.set(0, Math.PI / 2, 0);
      dummy.updateMatrix();
      if (mark === false) { this.breaks.setMatrixAt(breaks, dummy.matrix); this.breakK[breaks++] = k; }
      else { this.nodes.setMatrixAt(nodes, dummy.matrix); this.nodeK[nodes++] = k; }
      // The other daughter: a stub up or down, ending in a faded bead.
      const side = k % 2 ? 1 : -1, tip = [x + 0.06, y + side * 0.42, z + 0.12];
      pm.set([x, y, z, ...tip], 6 * stems++);
      dummy.position.set(...tip);
      dummy.scale.setScalar(1);
      dummy.updateMatrix();
      this.stubs.setMatrixAt(stubs++, dummy.matrix);
      // The segment on to the next node: as far as the clock has grown it.
      if (k < n) {
        const next = k + 1 <= upTo ? this.xOf(k + 1) : x + (this.xOf(k + 1) - x) * (k === upTo ? progress : 0);
        if (mark === false) pt.set([x, y, z, next, y, z], 6 * thin++);
        else ps.set([x, y, z, next, y, z], 6 * solid++);
      }
    }
    this.nodes.count = nodes; this.breaks.count = breaks; this.stubs.count = stubs;
    for (const mesh of [this.nodes, this.breaks, this.stubs]) { mesh.instanceMatrix.needsUpdate = true; mesh.computeBoundingSphere(); }
    this.solid.geometry.setDrawRange(0, solid * 2); this.thin.geometry.setDrawRange(0, thin * 2); this.stems.geometry.setDrawRange(0, stems * 2);
    for (const line of [this.solid, this.thin, this.stems]) line.geometry.attributes.position.needsUpdate = true;
  }

  nodeAt(k) {
    return new THREE.Vector3(this.xOf(k), this.y, this.z);
  }

  dispose() {
    for (const object of [this.nodes, this.breaks, this.stubs, this.solid, this.thin, this.stems]) object.geometry.dispose();
  }
}

/** The map's layout: the first three principal components of the grown compositions, worked out by the view. */
export function mapLayout(run) {
  const rows = run.parents, n = rows.length, d = run.n, mean = new Float64Array(d);
  for (const row of rows) for (let i = 0; i < d; i++) mean[i] += row[i] / n;
  const C = new Float64Array(d * d), c = new Float64Array(d);
  for (const row of rows) {
    for (let i = 0; i < d; i++) c[i] = row[i] - mean[i];
    for (let i = 0; i < d; i++) { const ci = c[i]; if (!ci) continue; for (let j = 0; j < d; j++) C[i * d + j] += ci * c[j]; }
  }
  // Power iteration, from a fixed start, with deflation: the same axes every time.
  const axes = [];
  for (let v = 0; v < 3; v++) {
    let x = new Float64Array(d).map((_, i) => Math.sin(1 + i * (v + 2)));
    for (let step = 0; step < 300; step++) {
      const y = new Float64Array(d);
      for (let i = 0; i < d; i++) { let s = 0; for (let j = 0; j < d; j++) s += C[i * d + j] * x[j]; y[i] = s; }
      for (const axis of axes) { let p = 0; for (let i = 0; i < d; i++) p += y[i] * axis[i]; for (let i = 0; i < d; i++) y[i] -= p * axis[i]; }
      const length = Math.hypot(...y) || 1;
      for (let i = 0; i < d; i++) y[i] /= length;
      x = y;
    }
    axes.push(x);
  }
  const project = (x) => {
    const size = x.reduce((a, b) => a + b, 0) || 1;
    return axes.map((axis) => { let s = 0; for (let i = 0; i < d; i++) s += ((x[i] * 80) / size - mean[i]) * axis[i]; return s; });
  };
  const points = rows.map(project);
  // Nine in ten points within the frame: a founder's first mixes can lie far out.
  const reach = points.map((p) => Math.max(...p.map(Math.abs))).sort((a, b) => a - b)[Math.floor(n * 0.9)] || 1;
  const scale = 0.9 / reach;
  const place = (p) => p.map((value) => Math.max(-1.3, Math.min(1.3, value * scale)));
  return { axes, points: points.map(place), at: (x) => place(project(x)) };
}

export class CompositionMap {
  constructor(parent, run, { centre, size, materials, leading }) {
    this.run = run;
    this.layout = mapLayout(run);
    this.centre = centre;
    this.size = size;
    const n = run.fissionCount;
    this.group = new THREE.Group();
    this.group.position.set(...centre);
    parent.add(this.group);
    this.points = new THREE.InstancedMesh(new THREE.SphereGeometry(0.06, 8, 6), materials.point, n);
    this.points.count = 0;
    this.points.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.points.frustumCulled = false;
    this.points.userData.pick = (hit) => `assembly:fission:${run.id}:${hit.instanceId + 1}`;
    this.group.add(this.points);
    const lines = (count, material) => {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(count * 6), 3));
      geometry.setDrawRange(0, 0);
      const line = new THREE.LineSegments(geometry, material);
      line.frustumCulled = false;
      line.userData.unpickable = true;
      this.group.add(line);
      return line;
    };
    this.trail = lines(n, materials.trail);
    this.broken = lines(n, materials.trailDashed);
    this.frame = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(size * 2.1, size * 2.1, size * 2.1)), materials.frame);
    this.frame.userData.unpickable = true;
    this.group.add(this.frame);
    this.now = new THREE.Mesh(new THREE.TorusGeometry(0.13, 0.02, 8, 28), materials.now);
    this.now.userData.unpickable = true;
    this.group.add(this.now);
    // An arrow for each leading type: the direction in which more of it lies.
    this.arrows = leading.map((type, slot) => {
      const d = new THREE.Vector3(this.layout.axes[0][type], this.layout.axes[1][type], this.layout.axes[2][type]).normalize();
      const arrow = new THREE.ArrowHelper(d, new THREE.Vector3(), size * 0.95, 0xffffff, 0.16, 0.09);
      arrow.line.material = materials.arrows[slot];
      arrow.cone.material = materials.arrowHeads[slot];
      arrow.traverse((object) => (object.userData.unpickable = true));
      this.group.add(arrow);
      return { arrow, tip: d.clone().multiplyScalar(size * 1.05), type };
    });
    // Composomes, only where the run's analysis names them: a ring round each named crowd.
    this.composomes = [];
    const named = run.composomes;
    if (named) {
      for (const name of named.names) {
        const ps = name.fissions.map((k) => this.layout.points[k - 1]);
        const c = [0, 1, 2].map((a) => ps.reduce((s, p) => s + p[a], 0) / ps.length);
        const r = Math.max(0.12, ...ps.map((p) => Math.hypot(p[0] - c[0], p[1] - c[1], p[2] - c[2])));
        const ring = new THREE.Mesh(new THREE.TorusGeometry(r * size + 0.1, 0.015, 6, 40), materials.composome);
        ring.position.set(c[0] * size, c[1] * size, c[2] * size);
        ring.userData.pick = `assembly:composome:${run.id}:${name.id}`;
        this.group.add(ring);
        this.composomes.push({ name, ring, centre: ring.position.clone() });
      }
    }
    this.key = "";
  }

  draw(upTo, current, camera) {
    const run = this.run, { points } = this.layout, s = this.size;
    const key = `${upTo}`;
    if (key !== this.key) {
      this.key = key;
      for (let k = 0; k < upTo; k++) {
        dummy.position.set(points[k][0] * s, points[k][1] * s, points[k][2] * s);
        dummy.scale.setScalar(1);
        dummy.updateMatrix();
        this.points.setMatrixAt(k, dummy.matrix);
      }
      this.points.count = upTo;
      this.points.instanceMatrix.needsUpdate = true;
      this.points.computeBoundingSphere();
      const a = this.trail.geometry.attributes.position.array, b = this.broken.geometry.attributes.position.array;
      let solid = 0, broken = 0;
      for (let k = 1; k < upTo; k++) {
        const p = points[k - 1].map((v) => v * s), q = points[k].map((v) => v * s);
        if (run.inherited(k) === false) b.set([...p, ...q], 6 * broken++);
        else a.set([...p, ...q], 6 * solid++);
      }
      this.trail.geometry.setDrawRange(0, solid * 2);
      this.broken.geometry.setDrawRange(0, broken * 2);
      this.trail.geometry.attributes.position.needsUpdate = this.broken.geometry.attributes.position.needsUpdate = true;
      this.broken.computeLineDistances();
    }
    // The composition of the moment, between two points.
    const at = this.layout.at(current);
    this.now.position.set(at[0] * s, at[1] * s, at[2] * s);
    if (camera) this.now.quaternion.copy(camera.quaternion);
  }

  pointAt(k) {
    const p = this.layout.points[k - 1];
    return new THREE.Vector3(p[0] * this.size, p[1] * this.size, p[2] * this.size).add(this.group.position);
  }

  dispose() {
    this.group.traverse((object) => object.geometry?.dispose?.());
  }
}
