// Similarity, drawn two ways. The fence: a post at each fission as tall as H, the parent's
// similarity with a daughter, read from the run; capped with a bead where the run's analysis marks
// the fission inherited and a ring where it marks a break (read, never decided here). The analysis's
// threshold stands as a glass sheet across the posts, and only on the comparison it was made for:
// the parent with the daughter that carries on (schema/ASSEMBLY_RUN.md, rule 2). The carpet: H
// between every two grown assemblies, fission against fission, worked out by the view from the
// saved counts and said so; strong squares along its diagonal are stretches where the mix held.

import * as THREE from "../three.js";
import { similarity } from "./assembly_run.js";
import { dataTexture, rampAt } from "./composition_marks.js";

export const COMPARE = [
  { id: "carried", label: "Parent → carried on", says: "H of the parent just before a fission with the daughter that carries on: the run's own", own: true },
  { id: "other", label: "Parent → other daughter", says: "H of the parent with the daughter that is not followed: the run's own", own: true },
  { id: "grown", label: "Birth → grown", says: "H of a daughter at its birth with itself grown to the next fission: worked out by the view from the saved counts", own: false },
];

/** The value the fence shows at fission k for a comparison, and whether it is the run's own. */
export function valueAt(run, k, compare) {
  if (compare === "other") return run.similarityAt(k).other;
  if (compare === "grown") return k < run.fissionCount ? similarity(run.carried(k), run.parent(k + 1)) : null;
  return run.similarityAt(k).carried;
}

/** H from `low` (the fence's foot) to 1 (its top), in the scene's height. */
export const HEIGHT = { low: 0.6, top: 3.2 };
const heightOf = (h) => Math.max(0.02, ((h - HEIGHT.low) / (1 - HEIGHT.low)) * HEIGHT.top);

export class SimilarityFence {
  constructor(parent, run, { xOf, z, y, materials }) {
    this.run = run;
    this.xOf = xOf;
    this.z = z;
    this.y = y;
    const n = run.fissionCount;
    this.posts = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.035, 0.035, 1, 6), materials.post, n);
    this.caps = new THREE.InstancedMesh(new THREE.SphereGeometry(0.075, 8, 6), materials.cap, n);
    this.rings = new THREE.InstancedMesh(new THREE.TorusGeometry(0.075, 0.022, 5, 12), materials.cap, n);
    for (const mesh of [this.posts, this.caps, this.rings]) {
      mesh.count = 0;
      mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      mesh.frustumCulled = false;
      parent.add(mesh);
    }
    const pickK = (list) => (hit) => (list[hit.instanceId] ? `assembly:fission:${run.id}:${list[hit.instanceId]}` : null);
    this.postK = []; this.capK = []; this.ringK = [];
    this.posts.userData.pick = pickK(this.postK);
    this.caps.userData.pick = pickK(this.capK);
    this.rings.userData.pick = pickK(this.ringK);
    // The analysis's threshold, where it states one: a glass sheet along the fence.
    this.threshold = run.threshold;
    this.sheet = null;
    if (this.threshold) {
      const width = Math.abs(xOf(n) - xOf(1)) + 0.6;
      this.sheet = new THREE.Mesh(new THREE.PlaneGeometry(width, 0.9), materials.sheet);
      this.sheet.rotation.x = -Math.PI / 2;
      this.sheet.position.set((xOf(1) + xOf(n)) / 2, y + heightOf(this.threshold.value), z);
      this.sheet.userData.pick = "assembly:threshold";
      parent.add(this.sheet);
    }
    this.key = "";
  }

  /** Posts up to fission `upTo` for the comparison; the sheet only on the comparison the analysis made. */
  draw(upTo, compare, { chosen = null } = {}) {
    const key = `${upTo}:${compare}:${chosen}`;
    if (key === this.key) return;
    this.key = key;
    const dummy = new THREE.Object3D(), run = this.run;
    let posts = 0, caps = 0, rings = 0;
    this.postK.length = this.capK.length = this.ringK.length = 0;
    for (let k = 1; k <= upTo; k++) {
      const h = valueAt(run, k, compare);
      if (h === null) continue;
      const tall = heightOf(h), x = this.xOf(k);
      dummy.position.set(x, this.y + tall / 2, this.z);
      dummy.scale.set(1, tall, 1);
      dummy.rotation.set(0, 0, 0);
      dummy.updateMatrix();
      this.posts.setMatrixAt(posts, dummy.matrix);
      this.postK[posts++] = k;
      // The analysis's mark, read as written: only on the comparison it was made for.
      const mark = compare === "carried" ? run.inherited(k) : null;
      dummy.position.set(x, this.y + tall, this.z);
      dummy.scale.setScalar(k === chosen ? 1.8 : 1);
      if (mark === false) {
        dummy.rotation.set(0, Math.PI / 2, 0);
        dummy.updateMatrix();
        this.rings.setMatrixAt(rings, dummy.matrix);
        this.ringK[rings++] = k;
      } else {
        dummy.updateMatrix();
        this.caps.setMatrixAt(caps, dummy.matrix);
        this.capK[caps++] = k;
      }
    }
    this.posts.count = posts;
    this.caps.count = caps;
    this.rings.count = rings;
    for (const mesh of [this.posts, this.caps, this.rings]) { mesh.instanceMatrix.needsUpdate = true; mesh.computeBoundingSphere(); }
    if (this.sheet) this.sheet.visible = compare === "carried";
  }

  /** The top of the post at fission k, for its label. */
  topOf(k, compare) {
    const h = valueAt(this.run, k, compare);
    return new THREE.Vector3(this.xOf(k), this.y + heightOf(h ?? HEIGHT.low), this.z);
  }

  dispose() {
    for (const mesh of [this.posts, this.caps, this.rings]) mesh.geometry.dispose();
    this.sheet?.geometry.dispose();
  }
}

/** H between every two grown assemblies of a run, worked out by the view (the run saves H only across each fission). */
export function carpetOf(run) {
  const n = run.fissionCount, values = new Float32Array(n * n);
  for (let a = 0; a < n; a++) {
    values[a * n + a] = 1;
    for (let b = a + 1; b < n; b++) values[a * n + b] = values[b * n + a] = similarity(run.parent(a + 1), run.parent(b + 1));
  }
  return values;
}

export class SimilarityCarpet {
  constructor(parent, run, { size, at, materials }) {
    this.run = run;
    this.values = carpetOf(run);
    const n = run.fissionCount;
    this.texture = dataTexture(n, n);
    this.material = new THREE.MeshBasicMaterial({ map: this.texture, transparent: true, toneMapped: false });
    this.material.userData.noContact = true;
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(size, size), this.material);
    this.mesh.rotation.x = -Math.PI / 2;
    this.mesh.position.set(at[0], at[1], at[2]);
    this.mesh.userData.pick = (hit) => {
      const a = Math.min(n, Math.max(1, Math.floor(hit.uv.x * n) + 1)), b = Math.min(n, Math.max(1, Math.floor((1 - hit.uv.y) * n) + 1));
      return `assembly:pair:${run.id}:${a}:${b}`;
    };
    parent.add(this.mesh);
    // The cursor: two lines across the carpet at the fission the clock stands at.
    const cursor = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()]);
    this.cursor = new THREE.LineSegments(cursor, materials.cursor);
    this.cursor.userData.unpickable = true;
    parent.add(this.cursor);
    this.size = size;
    this.shown = -1;
  }

  value(a, b) {
    return this.values[(a - 1) * this.run.fissionCount + (b - 1)];
  }

  draw(upTo, ramp) {
    if (upTo === this.shown && ramp === this.ramp) return;
    this.shown = upTo;
    this.ramp = ramp;
    const n = this.run.fissionCount, data = this.texture.image.data;
    data.fill(0);
    for (let a = 0; a < upTo; a++) for (let b = 0; b < upTo; b++) {
      const [r, g, bl] = rampAt(ramp, (this.values[a * n + b] - 0.2) / 0.8);
      const o = ((n - 1 - b) * n + a) * 4; // fission a across, fission b down from the top
      data[o] = r; data[o + 1] = g; data[o + 2] = bl; data[o + 3] = 255;
    }
    this.texture.needsUpdate = true;
    const half = this.size / 2, { x, y, z } = this.mesh.position, step = this.size / n;
    const c = upTo > 0 ? -half + (upTo - 0.5) * step : -half;
    const points = this.cursor.geometry.attributes.position;
    points.setXYZ(0, x + c, y + 0.01, z - half); points.setXYZ(1, x + c, y + 0.01, z + half);
    points.setXYZ(2, x - half, y + 0.01, z + c); points.setXYZ(3, x + half, y + 0.01, z + c);
    points.needsUpdate = true;
    this.cursor.visible = upTo > 0;
  }

  dispose() {
    this.mesh.geometry.dispose();
    this.texture.dispose();
    this.material.dispose();
    this.cursor.geometry.dispose();
  }
}
