// An assembly's composition, drawn three ways: the wheel, a ring of the types' shares around the
// assembly's equator; the strip, a bar of the same shares beneath it, as long as the assembly is
// large; and the tape, every fission's grown composition side by side as a wall (types down,
// fissions along). The types keep their places, t000 to t099, so a change of mix reads as a change
// of widths. Shares are counts over the size: the view's own division, said so on the card.

import * as THREE from "../three.js";

const RING_QUADS = 480; // the ring's whole budget of quads, shared by its arcs
const GAP = 0.012;      // radians between two arcs

/** The colour of a type: a leading type's own, or one of two greys that alternate between neighbours. */
export function typeColour(type, x, { slotOf, colours }) {
  const slot = slotOf(type);
  if (slot >= 0) return colours.lead[slot];
  let others = 0;
  for (let j = 0; j < type; j++) if (x[j] && slotOf(j) < 0) others++;
  return others % 2 ? colours.otherAlt : colours.other;
}

/** The wheel: one ring of arcs for each group the assembly stands in (two during a split). */
export class CompositionRing {
  constructor(parent, material) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(RING_QUADS * 2 * 18), 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(new Float32Array(RING_QUADS * 2 * 18), 3));
    geometry.setDrawRange(0, 0);
    this.mesh = new THREE.Mesh(geometry, material);
    this.mesh.frustumCulled = false;
    this.mesh.userData.pick = "assembly:composition";
    parent.add(this.mesh);
    this.key = "";
  }

  /**
   * groups: [{ x (counts), centre [x, y, z], radius, fade }]; only redrawn when what it shows changes.
   */
  draw(groups, style, key) {
    if (key === this.key) return;
    this.key = key;
    const positions = this.mesh.geometry.attributes.position.array, tint = this.mesh.geometry.attributes.color.array;
    let at = 0;
    const colour = new THREE.Color();
    const budget = Math.floor(RING_QUADS / Math.max(1, groups.length));
    for (const group of groups) {
      const { x, centre, radius, fade } = group;
      const total = x.reduce((a, b) => a + b, 0) || 1;
      const inner = radius * 1.38, outer = radius * 1.38 + 0.26 * Math.max(0.6, radius);
      let angle = -Math.PI / 2;
      for (let type = 0; type < x.length; type++) {
        if (!x[type]) continue;
        const span = (x[type] / total) * Math.PI * 2;
        const quads = Math.max(1, Math.round((span / (Math.PI * 2)) * budget));
        colour.copy(typeColour(type, x, style)).lerp(style.colours.stage, fade);
        const from = angle + GAP / 2, to = angle + Math.max(GAP / 2 + 0.002, span - GAP / 2);
        for (let q = 0; q < quads && at < RING_QUADS * 2 * 18; q++) {
          const a0 = from + ((to - from) * q) / quads, a1 = from + ((to - from) * (q + 1)) / quads;
          const p = (r, a) => [centre[0] + Math.cos(a) * r, centre[1], centre[2] + Math.sin(a) * r];
          const quad = [p(inner, a0), p(outer, a0), p(outer, a1), p(inner, a0), p(outer, a1), p(inner, a1)];
          for (const point of quad) {
            positions.set(point, at);
            tint.set([colour.r, colour.g, colour.b], at);
            at += 3;
          }
        }
        angle += span;
      }
    }
    this.mesh.geometry.setDrawRange(0, at / 3);
    this.mesh.geometry.attributes.position.needsUpdate = true;
    this.mesh.geometry.attributes.color.needsUpdate = true;
    this.mesh.geometry.computeBoundingSphere();
  }

  dispose() { this.mesh.geometry.dispose(); }
}

/** The strip: one box for each type an assembly holds, in type order, as long as the assembly is large. */
export class CompositionStrip {
  constructor(parent, material, capacity = 220) {
    this.mesh = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), material, capacity);
    this.mesh.count = 0;
    this.mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(capacity * 3).fill(1), 3);
    this.mesh.frustumCulled = false;
    this.mesh.userData.pick = (hit) => (this.types[hit.instanceId] !== undefined ? `assembly:type:${this.types[hit.instanceId]}` : "assembly:composition");
    parent.add(this.mesh);
    this.capacity = capacity;
    this.types = [];
    this.key = "";
  }

  /** groups: [{ x, centre, fade }]; a full assembly of `full` molecules is `length` long. */
  draw(groups, style, key, { length = 3.2, full = 80, height = 0.22, below = 1.75 } = {}) {
    if (key === this.key) return;
    this.key = key;
    const dummy = new THREE.Object3D(), colour = new THREE.Color();
    let index = 0;
    this.types = [];
    for (const group of groups) {
      const { x, centre, fade } = group;
      const unit = length / full;
      const total = x.reduce((a, b) => a + b, 0);
      let at = centre[0] - (total * unit) / 2;
      for (let type = 0; type < x.length && index < this.capacity; type++) {
        if (!x[type]) continue;
        const width = x[type] * unit;
        dummy.position.set(at + width / 2, centre[1] - below, centre[2]);
        dummy.scale.set(Math.max(0.004, width - 0.012), height, 0.14);
        dummy.updateMatrix();
        this.mesh.setMatrixAt(index, dummy.matrix);
        colour.copy(typeColour(type, x, style)).lerp(style.colours.stage, fade);
        this.mesh.setColorAt(index, colour);
        this.types[index] = type;
        index++;
        at += width;
      }
    }
    this.mesh.count = index;
    this.mesh.instanceMatrix.needsUpdate = true;
    if (this.mesh.instanceColor) this.mesh.instanceColor.needsUpdate = true;
    this.mesh.computeBoundingSphere();
  }

  dispose() { this.mesh.geometry.dispose(); }
}

/** A ramp, faint to strong, from the view's tokens: an [r, g, b] in 0..255 for t in 0..1. */
export function rampAt(stops, t) {
  const x = Math.min(1, Math.max(0, t)) * (stops.length - 1), k = Math.min(stops.length - 2, Math.floor(x)), f = x - k;
  const a = stops[k], b = stops[k + 1];
  return [a.r + (b.r - a.r) * f, a.g + (b.g - a.g) * f, a.b + (b.b - a.b) * f].map((value) => Math.round(value * 255));
}

/** A texture from numbers: no canvas, so it is made the same in a page and in a test. */
export function dataTexture(width, height) {
  const texture = new THREE.DataTexture(new Uint8Array(width * height * 4), width, height, THREE.RGBAFormat);
  texture.magFilter = THREE.NearestFilter;
  texture.minFilter = THREE.NearestFilter;
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.needsUpdate = true;
  return texture;
}

/** The tape: each fission's parent as a column, types down from t000, a stronger colour for more molecules. */
export class CompositionTape {
  constructor(parent, run, { width, height, at }) {
    this.run = run;
    this.texture = dataTexture(run.fissionCount, run.n);
    this.material = new THREE.MeshBasicMaterial({ map: this.texture, transparent: true, toneMapped: false, side: THREE.DoubleSide });
    this.material.userData.noContact = true;
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(width, height), this.material);
    this.mesh.position.set(at[0], at[1], at[2]);
    this.mesh.userData.pick = (hit) => {
      const k = Math.min(run.fissionCount, Math.max(1, Math.floor(hit.uv.x * run.fissionCount) + 1));
      return `assembly:fission:${run.id}:${k}`;
    };
    parent.add(this.mesh);
    this.width = width;
    this.height = height;
    this.shown = -1;
  }

  /** Fill the columns up to fission `upTo` (0: none); the rest stay clear. */
  draw(upTo, ramp) {
    if (upTo === this.shown && ramp === this.ramp) return;
    this.shown = upTo;
    this.ramp = ramp;
    const { run } = this, data = this.texture.image.data, columns = run.fissionCount;
    data.fill(0);
    for (let k = 1; k <= upTo; k++) {
      const parent = run.parent(k);
      for (let type = 0; type < run.n; type++) {
        if (!parent[type]) continue;
        const [r, g, b] = rampAt(ramp, 0.45 + 0.55 * Math.sqrt(parent[type] / 60)); // a single molecule still shows, in either theme
        // Rows run from the top (t000) down: the texture's first row is its bottom.
        const o = ((run.n - 1 - type) * columns + (k - 1)) * 4;
        data[o] = r; data[o + 1] = g; data[o + 2] = b; data[o + 3] = 255;
      }
    }
    this.texture.needsUpdate = true;
  }

  /** Where fission k's column stands, along the wall. */
  xOf(k) {
    return this.mesh.position.x - this.width / 2 + ((k - 0.5) / this.run.fissionCount) * this.width;
  }

  dispose() {
    this.mesh.geometry.dispose();
    this.texture.dispose();
    this.material.dispose();
  }
}
