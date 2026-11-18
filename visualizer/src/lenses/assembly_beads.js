// One assembly as beads: a bead for each molecule, so the count is exact. Where each bead sits is
// the picture's choice, since the model gives an assembly no shape: on a ball, heads out and tails
// in (a micelle, as the papers sketch one), or loosely in a ball (a cluster, which claims the
// least). The beads follow the run: a molecule joins, a molecule leaves, and at a fission the beads
// part into the two daughters as the run split the counts, one carrying on and one let go.
//
// Motion at speed (schema/ASSEMBLY_RUN.md, rule 4): a molecule flies in only molecule by molecule.
// At any step of fissions a second it appears at its place with a short glow, and no more than
// GLOW_CAP glow at once; at FAST_GLOW fissions a second and faster none glows, so the assembly
// reads as an assembly at every speed. With less motion asked for nothing eases or glows.

import * as THREE from "../three.js";

/** How the assembly may be packed, the picture's choice: a protocell (the view opens with it), a micelle, a loose cluster. BeadLayout draws the last two; the protocell is LipidLayout's (src/lenses/lipid_assembly.js). */
export const SHAPES = ["protocell", "micelle", "cluster"];
export const FLIGHT_S = 0.45; // seconds a molecule takes to fly in or out, molecule by molecule
export const GLOW_S = 0.55;   // seconds a molecule's glow lasts where it appears
export const GLOW_CAP = 10;   // glows shown at once, at most
export const FAST_GLOW = 2;   // from this many fissions a second, nothing glows

/** A small stream of numbers that is the same everywhere: where beads first stand. */
function stream(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

/** Where the beads of one assembly stand, as numbers: the drawing reads them. */
export class BeadLayout {
  constructor({ seed = 2026 } = {}) {
    this.random = stream(seed);
    this.beads = [];
    this.shape = "micelle";
    this.at = null; // the run's phase the beads stand for
    this.centres = [[0, 0, 0], [0, 0, 0]];
    this.fade = 0;
    this.counts = [0, 0];
    this.mode = "glow"; // "flight", "glow" or "still": how a molecule that joins appears
    this.axis = 0; // which way the daughters part: across (0), or up and down (1) on a tall screen
  }

  direction() {
    const z = this.random() * 2 - 1, a = this.random() * Math.PI * 2, s = Math.sqrt(1 - z * z);
    return [s * Math.cos(a), z, s * Math.sin(a)];
  }

  bead(type, arriving) {
    return { type, dir: this.direction(), depth: Math.cbrt(0.15 + 0.85 * this.random()), side: 0, pos: null, flight: arriving && this.mode === "flight" ? 0 : 1, glow: arriving && this.mode === "glow" ? GLOW_S : 0, leaving: false, gone: false, scale: 1 };
  }

  /** Every bead afresh, from a composition (a jump of the clock). */
  rebuild(x) {
    this.beads = [];
    for (let type = 0; type < x.length; type++) for (let c = 0; c < x[type]; c++) this.beads.push(this.bead(type, false));
    this.relax(30);
    for (const bead of this.beads) bead.pos = null;
  }

  /** Spread the beads of each group over their ball: a few steps of repulsion between near directions. */
  relax(steps) {
    const groups = [[], []];
    for (const bead of this.beads) if (!bead.gone) groups[bead.side].push(bead);
    for (let step = 0; step < steps; step++) {
      for (const group of groups) {
        const n = group.length;
        if (n < 2) continue;
        const reach = 2.6 / Math.sqrt(n), reach2 = reach * reach;
        for (let a = 0; a < n; a++) {
          const p = group[a].dir;
          for (let b = a + 1; b < n; b++) {
            const q = group[b].dir;
            const dx = p[0] - q[0], dy = p[1] - q[1], dz = p[2] - q[2], d2 = dx * dx + dy * dy + dz * dz;
            if (d2 > reach2 || d2 < 1e-12) continue;
            const f = (0.035 * (reach2 - d2)) / reach2;
            p[0] += dx * f; p[1] += dy * f; p[2] += dz * f; q[0] -= dx * f; q[1] -= dy * f; q[2] -= dz * f;
          }
        }
        for (const bead of group) { const p = bead.dir, l = Math.hypot(p[0], p[1], p[2]) || 1; p[0] /= l; p[1] /= l; p[2] /= l; }
      }
    }
  }

  radius(count) {
    return this.shape === "cluster" ? 1.05 * Math.cbrt(count / 80) : Math.sqrt(count / 80);
  }

  /** A molecule joins or leaves. */
  apply(event) {
    const type = Math.abs(event) - 1;
    if (event > 0) this.beads.push(this.bead(type, true));
    else {
      for (let index = this.beads.length - 1; index >= 0; index--) {
        const bead = this.beads[index];
        if (bead.type === type && !bead.leaving) {
          bead.leaving = true;
          bead.flight = this.mode === "flight" ? 0 : 1;
          if (this.mode !== "flight") bead.gone = true;
          break;
        }
      }
    }
  }

  /**
   * Bring the beads to the run at a clock's phase. `run` is an AssemblyRun; `phase` is its phaseAt.
   * Returns whether the beads were rebuilt (a jump) rather than moved on.
   */
  follow(run, phase) {
    const last = this.at;
    let rebuilt = false;
    const sameGrowth = last && last.phase === "grow" && phase.phase === "grow" && last.g === phase.g && phase.e >= last.e && phase.e - last.e <= 240;
    const fromSplit = last && last.phase === "split" && phase.phase === "grow" && phase.g === last.k && phase.e <= 240;
    const intoSplit = last && last.phase === "grow" && phase.phase === "split" && last.g === phase.k - 1;
    const sameSplit = last && last.phase === "split" && phase.phase === "split" && last.k === phase.k;
    if (sameGrowth) this.events(run, phase.g, last.e, phase.e);
    else if (fromSplit) {
      // The daughter that carries on becomes the assembly; the other is let go.
      this.beads = this.beads.filter((bead) => bead.side === 0 && !bead.gone);
      for (const bead of this.beads) bead.side = 0;
      this.events(run, phase.g, 0, phase.e);
    } else if (intoSplit) {
      this.events(run, last.g, last.e, run.growthLength(last.g));
      this.part(run, phase.k);
    } else if (!sameSplit) {
      this.rebuild(phase.phase === "split" ? run.parent(phase.k) : run.during(phase.g, phase.e));
      if (phase.phase === "split") this.part(run, phase.k);
      rebuilt = true;
    }
    this.at = { ...phase };
    // Where the two groups stand during a split: apart, then the daughter back to the middle.
    const s = phase.phase === "split" ? phase.part : 0;
    const d = this.radius(40) * 1.3, apart = smooth(0, 0.55, s), back = smooth(0.55, 1, s);
    const along = (amount) => (this.axis === 1 ? [0, amount, 0] : [amount, 0, 0]);
    this.centres = [along(-d * apart * (1 - back)), along(d * apart * (1 + 1.6 * back))];
    this.fade = back;
    this.split = s;
    this.counts = [0, 0];
    for (const bead of this.beads) if (!bead.gone) this.counts[bead.side]++;
    return rebuilt;
  }

  events(run, g, from, to) {
    const events = run.growthEvents(g);
    for (let k = from; k < to; k++) this.apply(events[k]);
  }

  /** The beads part as the run split the counts: type by type, so many to the daughter that carries on. */
  part(run, k) {
    const keep = Int32Array.from(run.carried(k));
    this.beads = this.beads.filter((bead) => !bead.gone);
    for (const bead of this.beads) {
      if (keep[bead.type] > 0) { keep[bead.type]--; bead.side = 0; } else bead.side = 1;
    }
  }

  /** Move each bead toward its place; returns whether anything still moves. */
  step(seconds, { still = false } = {}) {
    this.relax(still ? 0 : 1);
    const k = still || !seconds ? 1 : 1 - Math.exp(-seconds * 9);
    let moving = false, glowing = 0;
    for (const bead of this.beads) {
      const centre = this.centres[bead.side], R = this.radius(this.counts[bead.side] || 1);
      const reach = this.shape === "cluster" ? R * bead.depth : R;
      if (bead.flight < 1) { bead.flight = still ? 1 : Math.min(1, bead.flight + seconds / FLIGHT_S); moving = true; }
      const fly = bead.leaving ? smooth(0, 1, bead.flight) : 1 - smooth(0, 1, bead.flight);
      const target = [0, 1, 2].map((a) => centre[a] + bead.dir[a] * (reach + fly * 2.2));
      if (!bead.pos) bead.pos = target.slice();
      for (let a = 0; a < 3; a++) {
        const gap = target[a] - bead.pos[a];
        if (Math.abs(gap) > 1e-4) moving = true;
        bead.pos[a] += gap * k;
      }
      bead.scale = bead.leaving ? 1 - smooth(0, 1, bead.flight) : 1;
      if (bead.leaving && bead.flight >= 1) bead.gone = true;
      if (bead.glow > 0) {
        bead.glow = still ? 0 : Math.max(0, bead.glow - seconds);
        if (bead.glow > 0) { glowing++; moving = true; }
      }
      bead.tail = this.shape === "cluster" ? null : [0, 1, 2].map((a) => centre[a] + bead.dir[a] * R * 0.36);
    }
    this.beads = this.beads.filter((bead) => !bead.gone);
    // No more than GLOW_CAP glow at once: the oldest give theirs up first.
    if (glowing > GLOW_CAP) {
      const lit = this.beads.filter((bead) => bead.glow > 0).sort((a, b) => a.glow - b.glow);
      for (const bead of lit.slice(0, glowing - GLOW_CAP)) bead.glow = 0;
    }
    return moving;
  }

  /** How many beads are in flight, and how many glow, now: the bound the tests hold. */
  inMotion() {
    let flying = 0, glowing = 0;
    for (const bead of this.beads) {
      if (bead.flight < 1) flying++;
      if (bead.glow > 0) glowing++;
    }
    return { flying, glowing };
  }
}

/**
 * How a molecule that joins or leaves is drawn, at a speed of the clock: with less motion, at its place
 * at once ("still"); otherwise in flight at every speed, as many as the stride lets (src/lenses/
 * lipid_assembly.js, `streamStride`; the user, 17 November 2026: the molecules seen moving in and out).
 * BeadLayout's own glow at fission steps (`glow`) is kept for a caller that asks for it.
 */
export function arrivalMode({ still }) {
  return still ? "still" : "flight";
}

/** The beads' meshes: one set of instances for each shape, and the tails as one set of lines. */
export class BeadMeshes {
  constructor(parent, materials, capacity = 200) {
    this.capacity = capacity;
    // The three leading types: a diamond, a cube, a tetrahedron; every other type a sphere.
    const shapes = [new THREE.OctahedronGeometry(0.11), new THREE.BoxGeometry(0.135, 0.135, 0.135), new THREE.TetrahedronGeometry(0.12), new THREE.SphereGeometry(0.07, 10, 8)];
    this.meshes = shapes.map((geometry, slot) => {
      const mesh = new THREE.InstancedMesh(geometry, slot < 3 ? materials.lead : materials.other, capacity);
      mesh.count = 0;
      mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(capacity * 3).fill(1), 3);
      mesh.frustumCulled = false;
      mesh.userData.slot = slot;
      parent.add(mesh);
      return mesh;
    });
    const tails = new THREE.BufferGeometry();
    tails.setAttribute("position", new THREE.BufferAttribute(new Float32Array(capacity * 6), 3));
    tails.setAttribute("color", new THREE.BufferAttribute(new Float32Array(capacity * 6), 3));
    this.tails = new THREE.LineSegments(tails, materials.tail);
    this.tails.frustumCulled = false;
    this.tails.userData.unpickable = true;
    parent.add(this.tails);
    // The glows: one sprite each, drawn where a molecule has just taken its place.
    const glows = new THREE.InstancedMesh(new THREE.SphereGeometry(0.2, 12, 8), materials.glow, GLOW_CAP);
    glows.count = 0;
    glows.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    glows.userData.unpickable = true;
    glows.frustumCulled = false;
    parent.add(glows);
    this.glows = glows;
    this.dummy = new THREE.Object3D();
    this.colour = new THREE.Color();
    this.lists = [[], [], [], []];
  }

  /** Draw the layout's beads: `slotOf(type)` gives a leading type's slot (0 to 2) or -1. */
  draw(layout, { slotOf, colours, chosen = null }) {
    const { dummy, colour } = this;
    const counts = [0, 0, 0, 0];
    this.lists = [[], [], [], []];
    const positions = this.tails.geometry.attributes.position.array, tint = this.tails.geometry.attributes.color.array;
    let tails = 0, glows = 0;
    for (const bead of layout.beads) {
      if (!bead.pos) continue;
      const slot = slotOf(bead.type) >= 0 ? slotOf(bead.type) : 3;
      const index = counts[slot]++;
      if (index >= this.capacity) continue;
      this.lists[slot][index] = bead;
      const fade = bead.side === 1 ? 0.75 * layout.fade : 0;
      dummy.position.set(bead.pos[0], bead.pos[1], bead.pos[2]);
      dummy.scale.setScalar(Math.max(1e-3, bead.scale * (bead === chosen ? 1.35 : 1)));
      dummy.rotation.set(bead.dir[1] * 2, bead.dir[0] * 3, 0);
      dummy.updateMatrix();
      this.meshes[slot].setMatrixAt(index, dummy.matrix);
      colour.copy(slot < 3 ? colours.lead[slot] : colours.other).lerp(colours.stage, fade);
      if (bead === chosen) colour.copy(colours.chosen);
      this.meshes[slot].setColorAt(index, colour);
      if (bead.tail && tails < this.capacity) {
        positions.set([bead.pos[0], bead.pos[1], bead.pos[2], bead.tail[0], bead.tail[1], bead.tail[2]], tails * 6);
        colour.copy(colours.tail).lerp(colours.stage, fade);
        tint.set([colour.r, colour.g, colour.b, colour.r, colour.g, colour.b], tails * 6);
        tails++;
      }
      if (bead.glow > 0 && glows < GLOW_CAP) {
        dummy.position.set(bead.pos[0], bead.pos[1], bead.pos[2]);
        dummy.scale.setScalar(0.6 + 1.4 * (1 - bead.glow / GLOW_S));
        dummy.updateMatrix();
        this.glows.setMatrixAt(glows++, dummy.matrix);
      }
    }
    this.meshes.forEach((mesh, slot) => {
      mesh.count = Math.min(this.capacity, counts[slot]);
      mesh.instanceMatrix.needsUpdate = true;
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
      mesh.computeBoundingSphere();
    });
    this.tails.geometry.setDrawRange(0, tails * 2);
    this.tails.geometry.attributes.position.needsUpdate = true;
    this.tails.geometry.attributes.color.needsUpdate = true;
    this.glows.count = glows;
    this.glows.instanceMatrix.needsUpdate = true;
  }

  /** The bead a picking ray hit. */
  beadOf(hit) {
    const slot = hit.object.userData.slot;
    return slot === undefined ? null : this.lists[slot][hit.instanceId] || null;
  }

  dispose() {
    for (const mesh of [...this.meshes, this.glows]) mesh.geometry.dispose();
    this.tails.geometry.dispose();
  }
}
