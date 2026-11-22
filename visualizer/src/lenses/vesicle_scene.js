// Display geometry. All positions, molecular packing and release shapes are illustrative.
import * as T from "../three.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import popc from "../../data/origin/reference-popc.json" with { type: "json" };

const axis = new T.Vector3(0, 1, 0),
  cut = new T.Vector3(0.91, 0.4, 0.24).normalize();
const sphere = (n = 12) => new T.SphereGeometry(1, n, Math.max(5, n / 2));
const color = (value) => new T.Color(value);
const body = (tone, options = {}) => new T.MeshStandardMaterial({ color: tone, roughness: 0.4, metalness: 0.05, ...options });
const phi = Math.PI * (3 - Math.sqrt(5)),
  tau = 2 * Math.PI;
const green = color("#50c6b3"),
  lilac = color("#aa9bd6"),
  amber = color("#e88b4c");
const helper = new T.Object3D(),
  p = new T.Vector3(),
  q = new T.Quaternion();
const headColors = [green, lilac, color("#e6bd6d"), color("#91bbdc")];

function batch(parent, geometry, material, capacity) {
  const m = new T.InstancedMesh(geometry, material, capacity);
  m.instanceMatrix.setUsage(T.DynamicDrawUsage);
  m.frustumCulled = false;
  m.count = 0;
  parent.add(m);
  return m;
}
function put(mesh, i, point, rotation, x, y = x, z = x, tint = null) {
  helper.position.copy(point);
  helper.quaternion.copy(rotation);
  helper.scale.set(x, y, z);
  helper.updateMatrix();
  mesh.setMatrixAt(i, helper.matrix);
  if (tint) mesh.setColorAt(i, tint);
}
function finish(mesh, n) {
  mesh.count = n;
  mesh.instanceMatrix.needsUpdate = true;
  if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
}
function direction(i, n) {
  const y = 1 - (2 * (i + 0.5)) / n,
    r = Math.sqrt(1 - y * y);
  return new T.Vector3(r * Math.cos(i * phi), y, r * Math.sin(i * phi));
}
function joined(parts) {
  const geo = mergeGeometries(parts);
  parts.forEach((p) => p.dispose());
  return geo;
}
function tails() {
  const pieces = [-1, 1].map(
    (k) =>
      new T.TubeGeometry(
        new T.CatmullRomCurve3([
          new T.Vector3(0, 0, 0),
          new T.Vector3(k * 0.17, -0.22, 0),
          new T.Vector3(k * 0.28, -0.62, 0.06 * k),
          new T.Vector3(k * (k > 0 ? 0.45 : 0.23), -1, 0.16 * k),
        ]),
        9,
        0.086,
        6,
        false,
      ),
  );
  return joined(pieces);
}
function mesh(group, geo, mat) {
  const m = new T.Mesh(geo, mat);
  group.add(m);
  return m;
}

function referenceMolecule() {
  const group = new T.Group(),
    colors = { C: "#72a7a4", N: "#5476d4", O: "#ed785f", P: "#eeb64f" };
  const atoms = popc.atoms.map(([, x, y, z]) => new T.Vector3(x, y, z));
  const bounds = new T.Box3().setFromPoints(atoms),
    centre = bounds.getCenter(new T.Vector3());
  atoms.forEach((v) => v.sub(centre).multiplyScalar(0.17));
  const balls = batch(group, sphere(20), body("white"), atoms.length);
  const bonds = batch(group, new T.CylinderGeometry(1, 1, 1, 10), body("#8da7a7"), popc.bonds.length * 2);
  atoms.forEach((v, i) => {
    const el = popc.atoms[i][0];
    put(
      balls,
      i,
      v,
      new T.Quaternion(),
      el === "P" ? 0.146 : el === "C" ? 0.099 : 0.12,
      el === "P" ? 0.146 : el === "C" ? 0.099 : 0.12,
      el === "P" ? 0.146 : el === "C" ? 0.099 : 0.12,
      color(colors[el]),
    );
  });
  let n = 0;
  for (const [a, b, order] of popc.bonds) {
    const dir = atoms[b].clone().sub(atoms[a]),
      length = dir.length(),
      mid = atoms[a].clone().lerp(atoms[b], 0.5);
    q.setFromUnitVectors(axis, dir.normalize());
    const side = new T.Vector3().crossVectors(dir, Math.abs(dir.y) < 0.9 ? axis : new T.Vector3(0, 0, 1)).normalize();
    for (let j = 0; j < order; j++)
      put(bonds, n++, mid.clone().addScaledVector(side, (j - (order - 1) / 2) * 0.055), q, 0.032, length, 0.032);
  }
  finish(balls, atoms.length);
  finish(bonds, n);
  group.userData.head = atoms[popc.atoms.findIndex((a) => a[0] === "P")];
  return group;
}

export class VesicleScene {
  constructor() {
    this.root = new T.Group();
    this.whole = new T.Group();
    this.patch = new T.Group();
    this.population = new T.Group();
    this.release = new T.Group();
    this.molecule = referenceMolecule();
    this.root.add(this.whole, this.patch, this.molecule, this.population, this.release);
    this.coat = new T.Group();
    this.whole.add(this.coat);
    this.coat.quaternion.setFromUnitVectors(axis, cut);
    const theta = 1.05;
    const lipidCore = body("#487d7b", { roughness: 0.45, side: T.DoubleSide, transparent: true, opacity: 0.73, depthWrite: false });
    this.film = mesh(this.coat, new T.SphereGeometry(0.965, 72, 48, 0, tau, theta, Math.PI - theta), lipidCore);
    const face = [0.875, 0.92, 1].map((r) => new T.Vector2(Math.sin(theta) * r, Math.cos(theta) * r));
    mesh(
      this.coat,
      new T.LatheGeometry(face, 96),
      body("#a89371", { side: T.DoubleSide, transparent: true, opacity: 0.32, depthWrite: false }),
    );
    this.leaflets = [1, 0.875].map((r) => {
      const m = mesh(this.coat, new T.TorusGeometry(r * Math.sin(theta), 0.006, 8, 96), body("#d6d1a4"));
      m.rotation.x = Math.PI / 2;
      m.position.y = Math.cos(theta) * r;
      return m;
    });
    const rimPacking = this.lipids(this.coat, 220),
      rim = [];
    for (let i = 0; i < 102; i++) {
      const a = (tau * i) / 102,
        d = new T.Vector3(Math.sin(theta) * Math.cos(a), Math.cos(theta), Math.sin(theta) * Math.sin(a));
      for (const [r, sign] of [
        [1, 1],
        [0.875, -1],
      ])
        rim.push({
          at: d.clone().multiplyScalar(r),
          normal: d.clone().multiplyScalar(sign),
          size: 0.023,
          length: 0.064,
          tint: i % 9 ? green : lilac,
          spin: i * phi,
        });
    }
    this.makeLipids(rimPacking, rim);
    this.cutHeads = rimPacking.heads;
    this.liquid = mesh(
      this.whole,
      sphere(64),
      new T.MeshPhysicalMaterial({
        color: "#439fbd",
        roughness: 0.18,
        metalness: 0.12,
        clearcoat: 0.85,
        transparent: true,
        opacity: 0.39,
        depthWrite: false,
      }),
    );
    this.solutes = batch(this.whole, sphere(8), body("white"), 100);
    this.marks = this.lipids(this.coat, 2200);
    this.section = this.lipids(this.patch, 380);
    this.flights = batch(this.root, sphere(12), body("#f2b65a", { emissive: 0x352010 }), 18);
    this.cloud = batch(this.population, sphere(24), body("white"), 1);
    this.trail = batch(this.release, sphere(10), body("white"), 180);
    // A threshold tear leaves two illustrated bilayer fragments. A pore is drawn as a local aperture.
    this.fragments = new T.Group();
    this.release.add(this.fragments);
    const broken = [];
    for (let i = 0; i < 340; i++) {
      const d = direction(i, 340);
      if (Math.abs(d.x) < 0.5) continue;
      for (const sign of [1, -1]) {
        const at = d.clone().multiplyScalar(sign > 0 ? 1.43 : 1.23);
        at.x += 0.52 * Math.sign(d.x);
        broken.push({ at, normal: d.clone().multiplyScalar(sign), size: 0.085, length: 0.105, tint: green, spin: i * phi });
      }
    }
    this.makeLipids(this.lipids(this.fragments, broken.length), broken);
    this.rim = mesh(this.release, new T.TorusGeometry(1, 0.1, 14, 72), body("#f0a342"));
    this.rim.quaternion.setFromUnitVectors(new T.Vector3(0, 0, 1), cut);
    this.daughter = mesh(this.root, sphere(32), body("#83c7b9", { transparent: true, opacity: 0.65 }));
    this.daughter.visible = false;
    this.coat.userData.pick = "vesicle:membrane";
    this.patch.userData.pick = "vesicle:membrane";
    this.liquid.userData.pick = this.solutes.userData.pick = "vesicle:lumen";
    this.molecule.userData.pick = "vesicle:molecule";
    this.daughter.userData.pick = "vesicle:daughter";
    this.release.userData.pick = "vesicle:release";
    this.molecule.visible = false;
    this.signature = "";
  }
  lipids(parent, n) {
    return {
      heads: batch(parent, sphere(16), body("white", { roughness: 0.34 }), n),
      tails: batch(parent, tails(), body("#b38c60", { roughness: 0.48 }), n),
    };
  }
  makeLipids(marks, items) {
    items.forEach(({ at, normal, size, length, tint, spin }, i) => {
      q.setFromUnitVectors(axis, normal);
      q.multiply(new T.Quaternion().setFromAxisAngle(axis, spin));
      put(marks.heads, i, at, q, size, size * 0.81, size, tint);
      put(marks.tails, i, at, q, size * 2.05, length, size * 2.05);
    });
    finish(marks.heads, items.length);
    finish(marks.tails, items.length);
  }
  draw(state, run, level, layer, time, slot) {
    const sample = state.sample,
      e = state.event;
    const ended = e?.cause && (!run.pop || e.slot === slot) && !sample?.membrane_footprint_quanta;
    const population = run.pop && level === "vesicle";
    this.whole.visible = level === "vesicle" && !ended && !population;
    this.release.visible = level === "vesicle" && Boolean(ended) && !population;
    this.population.visible = population;
    this.patch.visible = level === "membrane";
    this.molecule.visible = level === "molecule";
    this.daughter.visible = false;
    this.flights.visible = this.whole.visible;
    const rad = 2.25 * Math.sqrt((sample?.membrane_footprint_quanta || 0) / (run.maxFoot || 1));
    const tension = state.hold?.sigma_N_per_m ?? sample?.tension_N_per_m ?? 0;
    const shade =
      level === "vesicle" && layer === "tension" && run.hasTension
        ? green.clone().lerp(amber, Math.min(1, tension / (run.maxTension || 1)))
        : null;
    const composition = run.membrane.map((p) => state.counts[p.index] || 0);
    const total = composition.reduce((a, b) => a + b, 0);
    const tintFor = (i) => {
      if (shade) return shade;
      let n = ((i * 0.61803398875) % 1) * total;
      for (let j = 0; j < composition.length; j++) {
        n -= composition[j];
        if (n < 0) return headColors[j % headColors.length];
      }
      return green;
    };
    const sig = [run.file.id, level, layer, state.row.t, state.n, slot];
    if (this.signature !== sig.join("/") && (this.whole.visible || this.patch.visible)) {
      this.signature = sig.join("/");
      if (this.whole.visible) {
        for (let i = 0; i < this.cutHeads.count; i++) this.cutHeads.setColorAt(i, tintFor(Math.floor(i / 2)));
        this.cutHeads.instanceColor.needsUpdate = true;
        const items = [],
          slots = Math.min(1050, Math.max(12, Math.ceil(total / 2)));
        for (let i = 0; i < slots; i++) {
          const d = direction(i, slots);
          if (d.y > Math.cos(1.05)) continue;
          for (const [r, sign] of [
            [1, 1],
            [0.875, -1],
          ])
            items.push({
              at: d.clone().multiplyScalar(r),
              normal: d.clone().multiplyScalar(sign),
              size: Math.min(0.14, 1.54 / Math.sqrt(slots)),
              length: 0.064,
              tint: tintFor(i)
                .clone()
                .multiplyScalar(0.85 + 0.23 * ((i * 0.7351) % 1)),
              spin: i * phi,
            });
        }
        this.makeLipids(this.marks, items);
        const lumenScale =
          run.maxVolume && sample?.lumen_volume_L ? Math.cbrt(sample.lumen_volume_L / run.maxVolume) * run.lumenDisplayScale : 0;
        this.liquid.scale.setScalar(lumenScale);
        this.liquid.visible = lumenScale > 0;
        let dots = 0;
        for (const [j, place] of run.lumen.entries()) {
          const count = state.counts[place.index] || 0;
          if (!count) continue;
          for (let k = 0; k < Math.min(32, count); k++) {
            const pos = direction(k + j * 32, 80).multiplyScalar(
              lumenScale * 0.82 * Math.cbrt((((k * 0.754877 + j * 0.21) % 1) + 0.02) / 1.02),
            );
            put(this.solutes, dots++, pos, new T.Quaternion(), 0.031, 0.031, 0.031, headColors[(j + 1) % 4]);
          }
        }
        finish(this.solutes, dots);
      }
      if (this.patch.visible) {
        const items = [];
        for (let j = 0; j < 7; j++)
          for (let i = 0; i < 16; i++) {
            const x = (i - 7.5 + (j % 2) * 0.45) * 0.3 + 0.028 * Math.sin(i + 13 * j),
              z = (j - 3) * 0.31 + 0.025 * Math.cos(3 * i + j),
              y = 0.12 * Math.cos(x * 1.3) + 0.05 * z + 0.035 * Math.sin(i * 7 + j);
            for (const sign of [-1, 1])
              items.push({
                at: new T.Vector3(x, y + sign * 0.48, z),
                normal: new T.Vector3(0.12 * Math.sin(x + i), sign, 0.07 * Math.cos(j - i)).normalize(),
                size: 0.136,
                length: 0.48,
                tint: tintFor(i + 16 * j)
                  .clone()
                  .multiplyScalar(0.78 + 0.32 * ((i * 0.71 + j * 0.27) % 1)),
                spin: (i + 16 * j) * phi,
              });
          }
        this.makeLipids(this.section, items);
      }
    }
    this.coat.scale.setScalar(rad);
    if (this.whole.visible) {
      let n = 0;
      for (let j = state.n - 1; j >= 0 && time - run.file.trace.time[j] < 0.36 && n < 18; j--) {
        const age = (time - run.file.trace.time[j]) / 0.36;
        for (const transfer of run.movements(run.channels.get(run.file.trace.channel[j]))) {
          if (n >= 18) break;
          const rs = { pool: rad + 1.05, membrane: rad, lumen: rad * 0.45 };
          const d = direction((j * 37) % 193, 193);
          p.copy(d).multiplyScalar(rs[transfer.from.phase] * (1 - age) + rs[transfer.to.phase] * age);
          put(this.flights, n++, p, new T.Quaternion(), 0.07);
        }
      }
      finish(this.flights, n);
      if (e?.outcome === "split" && time - e.time < 1.4) {
        this.daughter.visible = true;
        this.daughter.position.set(1.85 + (time - e.time) * 0.4, 0.3, -0.45);
        // This daughter has counts but no separately sampled footprint or lumen.
        this.daughter.scale.setScalar(0.42);
      }
    }
    if (this.release.visible) {
      this.fragments.visible = e.cause === "threshold";
      this.rim.visible = e.cause === "pore";
      this.rim.scale.setScalar(0.7);
      for (let i = 0; i < 150; i++) {
        const d = direction(i, 150);
        if (e.cause === "threshold") d.x += d.x > 0 ? 0.3 : -0.3;
        else d.addScaledVector(cut, Math.max(0, d.dot(cut)) * 0.8);
        put(this.trail, i, d.multiplyScalar(1.6), new T.Quaternion(), 0.055, 0.055, 0.055, i % 4 ? green : amber);
      }
      finish(this.trail, 150);
    }
    if (population) {
      const count = state.row.slots.length,
        cols = Math.ceil(Math.sqrt(count)),
        gap = 4.6 / cols;
      if (this.cloud.instanceMatrix.count < count) {
        this.population.remove(this.cloud);
        this.cloud.dispose();
        this.cloud = batch(this.population, this.cloud.geometry, this.cloud.material, count);
      }
      const drawnSlots = [];
      this.cloud.userData.pick = (hit) => "vesicle:slot:" + drawnSlots[hit.instanceId];
      this.fragments.visible = false;
      let n = 0;
      state.row.slots.forEach((s, i) => {
        if (!s) return;
        const r = 0.4 * gap * Math.sqrt(s.membrane_footprint_quanta / (run.maxFoot || 1));
        p.set(
          ((i % cols) - (cols - 1) / 2) * gap,
          (Math.floor(i / cols) - (Math.ceil(count / cols) - 1) / 2) * gap,
          Math.sin(i * phi) * 0.15,
        );
        drawnSlots.push(i);
        put(this.cloud, n++, p, new T.Quaternion(), r, r, r, i === slot ? amber : green);
      });
      finish(this.cloud, n);
      const recent = e?.cause === "pore" && time - e.time < Math.max(0.2, (run.end - run.start) * 0.03);
      this.release.visible = Boolean(recent);
      this.trail.visible = !population;
      if (recent) {
        this.rim.visible = true;
        this.release.position.set(
          ((e.slot % cols) - (cols - 1) / 2) * gap,
          (Math.floor(e.slot / cols) - (Math.ceil(count / cols) - 1) / 2) * gap,
          0.1,
        );
        this.rim.scale.setScalar(gap * 0.38);
      }
    } else {
      this.release.position.set(0, 0, 0);
      this.trail.visible = true;
    }
  }
  dispose() {
    const geos = new Set(),
      mats = new Set();
    this.root.traverse((o) => {
      if (o.geometry) geos.add(o.geometry);
      if (o.material) mats.add(o.material);
      if (o.isInstancedMesh) o.dispose();
    });
    geos.forEach((g) => g.dispose());
    mats.forEach((m) => m.dispose());
  }
}
