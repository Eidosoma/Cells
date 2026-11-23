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
const headColors = [green, lilac, color("#70a8d3"), color("#e58c3e")];
const FLIGHT_SECONDS = 0.85, FLIGHT_CAP = 72;
const smooth = (x) => x * x * (3 - 2 * x);
const identity = new T.Quaternion();
const lean = new T.Quaternion();
const motion = new T.Vector3(), normal = new T.Vector3(), tip = new T.Vector3();
const inkFor = (run, species) => headColors[run.palette.indexOf(species) % headColors.length];
const patchSite = new T.Vector3();
function siteOf(i, j) {
  const x = (i - 7.5 + (j % 2) * 0.45) * 0.3 + 0.028 * Math.sin(i + 13 * j);
  const z = (j - 3) * 0.31 + 0.025 * Math.cos(3 * i + j);
  return patchSite.set(x, 0.12 * Math.cos(x * 1.3) + 0.05 * z + 0.035 * Math.sin(i * 7 + j), z);
}

// Bend the same two leaflets, cut rim, water and solutes into a neck. This is a display morph
// in world coordinates. Neither its onset nor its profile is a sample of membrane mechanics.
function shearMaterial(material, uniforms) {
  material.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, uniforms);
    shader.vertexShader = 'uniform float pinch, parentRadius, birthRatio;\n' + shader.vertexShader.replace(
      '#include <project_vertex>',
      `#include <project_vertex>
      if (pinch > 0.0) {
        vec4 local = vec4(transformed, 1.);
        #ifdef USE_INSTANCING
          local = instanceMatrix * local;
        #endif
        vec3 pos = (modelMatrix * local).xyz;
        #ifdef USE_INSTANCING
          vec3 centre = (modelMatrix * instanceMatrix * vec4(0., 0., 0., 1.)).xyz;
          vec3 offset = pos - centre;
          pos = centre;
        #endif
        float u = clamp(pos.x / parentRadius, -1., 1.);
        float a = max(abs(u), .001);
        float curve = 2. * sqrt(a / (1. + a));
        float width = mix(1., birthRatio * curve, pinch);
        float lengthX = mix(1., 2. * birthRatio, pinch);
        float slope = pinch * birthRatio * sign(u) / (parentRadius * sqrt(a) * pow(1. + a, 1.5));
        vec3 shaped = vec3(pos.x * lengthX, pos.yz * width);
        #ifdef USE_INSTANCING
          // Carry each packed molecule rigidly along the bending surface.
          vec3 oldN = normalize(pos + vec3(0., 1.e-8, 0.));
          vec3 newN = normalize(vec3((oldN.x - dot(oldN.yz, pos.yz) * slope / width) / lengthX, oldN.yz / width));
          vec3 turn = cross(oldN, newN);
          float divisor = max(.001, 1. + dot(oldN, newN));
          shaped += offset + cross(turn, offset) + cross(turn, cross(turn, offset)) / divisor;
        #endif
        #ifndef FLAT_SHADED
          vec3 n = inverseTransformDirection(transformedNormal, viewMatrix);
          #ifdef USE_INSTANCING
          n += cross(turn, n) + cross(turn, cross(turn, n)) / divisor;
          #else
          n.x = (n.x - dot(n.yz, pos.yz) * slope / width) / lengthX;
          n.yz /= width;
          #endif
          vNormal = transformDirection(normalize(n), viewMatrix);
        #endif
        mvPosition = viewMatrix * vec4(shaped, 1.);
        gl_Position = projectionMatrix * mvPosition;
      }`,
    );
  };
}

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
    this.flights = new T.Group();
    this.root.add(this.flights);
    this.flights.userData.unpickable = true;
    this.travelLipids = this.lipids(this.flights, FLIGHT_CAP);
    this.travelSolutes = batch(this.flights, new T.IcosahedronGeometry(1, 0), body("white"), FLIGHT_CAP);
    this.arrows = batch(this.flights, new T.ConeGeometry(1, 1, 8), body("white"), FLIGHT_CAP);
    this.streaks = batch(this.flights, new T.CylinderGeometry(1, 1, 1, 7), body("white"), FLIGHT_CAP);
    this.contacts = batch(this.flights, new T.TorusGeometry(1, 0.06, 5, 28).rotateX(Math.PI / 2), body("white"), FLIGHT_CAP);
    this.guide = batch(this.flights, sphere(6), body("white"), 13);
    this.trackedPosition = new T.Vector3();
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
    this.shearUniforms = { pinch: { value: 0 }, parentRadius: { value: 1 }, birthRatio: { value: 1 } };
    this.whole.traverse((o) => { if (o.material) shearMaterial(o.material, this.shearUniforms); });
    this.daughter = new T.Group();
    this.root.add(this.daughter);
    this.sisterFilm = mesh(this.daughter, sphere(40), body("#528e89", { transparent: true, opacity: 0.6, depthWrite: false }));
    this.sisterLipids = this.lipids(this.daughter, 270);
    for (const m of Object.values(this.sisterLipids)) m.material.transparent = true;
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
      q.multiply(lean.setFromAxisAngle(axis, spin));
      put(marks.heads, i, at, q, size, size * 0.81, size, tint);
      put(marks.tails, i, at, q, size * 2.05, length, size * 2.05);
    });
    finish(marks.heads, items.length);
    finish(marks.tails, items.length);
  }
  drawDivision(run, split, radius) {
    this.whole.position.set(0, 0, 0);
    this.daughter.visible = false;
    this.shearUniforms.pinch.value = 0;
    if (!split || radius <= 0) return;
    const { event, after, part } = split;
    const birth = run.at(event.time).sample;
    if (!birth?.membrane_footprint_quanta) return;
    const birthRadius = 2.25 * Math.sqrt(birth.membrane_footprint_quanta / run.maxFoot);
    if (!after) {
      this.shearUniforms.parentRadius.value = radius;
      this.shearUniforms.birthRatio.value = birthRadius / radius;
      this.shearUniforms.pinch.value = smooth(part);
      return;
    }
    // Only the continuing daughter has a measured footprint. The sister is a schematic at
    // the same starting display scale. Its membrane colours and label use its own partition.
    const sister = event.daughters[1 - event.followed], key = run.file.id + "/" + event.time;
    if (this.sisterKey !== key) {
      this.sisterKey = key;
      const counts = run.membrane.map((p) => sister.counts[p.index]), total = counts.reduce((a,b) => a+b, 0);
      const items = [];
      for (let i = 0; i < 260 && total > 0; i++) {
        const d = direction(i, 260);
        let quota = ((i * 0.61803398875) % 1) * total, j = 0;
        while (j + 1 < counts.length && quota >= counts[j]) quota -= counts[j++];
        items.push({ at: d, normal: d, size: 0.092, length: 0.12, spin: i * phi, tint: inkFor(run, run.membrane[j].species) });
      }
      this.makeLipids(this.sisterLipids, items);
    }
    this.whole.position.x = -birthRadius * (1 - smooth(part));
    this.daughter.visible = true;
    this.daughter.position.set(birthRadius * (1 + 1.25 * smooth(part)), 0.26 * part, -0.43 * part);
    this.daughter.scale.setScalar(birthRadius);
    const opacity = 1 - smooth(Math.max(0, (part - 0.58) / 0.42));
    this.sisterFilm.material.opacity = 0.6 * opacity;
    for (const m of Object.values(this.sisterLipids)) m.material.opacity = opacity;
  }
  drawTraffic(run, state, time, rad, patch, route, reducedMotion) {
    const since = state.event?.outcome === "split" ? state.event.time : -Infinity;
    const transfers = run.traffic(time, FLIGHT_SECONDS, state.slot, route, since);
    let lipids = 0, solutes = 0, contacts = 0, n = 0;
    let guide = 0;
    for (const move of transfers.slice(-FLIGHT_CAP)) {
      const age = (time - move.time) / FLIGHT_SECONDS, f = reducedMotion ? 0.5 : smooth(age);
      const lipid = move.from.phase === "membrane" || move.to.phase === "membrane";
      const tint = inkFor(run, move.from.species), i = move.index + 1;
      const lane = ((i * 0.61803398875) % 1) * 2 - 1, depth = (i * 0.754877666) % 1;
      const bend = (lipid ? 0.16 : 0.27) * Math.sin(i * 7.13), arc = 4 * f * (1 - f);
      if (patch) {
        const {x, y: surface, z} = siteOf(Math.min(15, Math.floor((lane + 1) * 8)), 6);
        const y = { pool: surface + 1.83, membrane: surface + 0.48, lumen: surface - 1.74 };
        const dy = y[move.to.phase] - y[move.from.phase];
        p.set(x + bend * arc, y[move.from.phase] + dy * f, z + (lipid ? 0 : 0.28));
        normal.set(0, 1, 0);
        motion.set(4 * bend * (1 - 2 * f), dy, 0).normalize();
        const face = p.y >= surface ? 0.48 : -0.48;
        const proximity = 1 - Math.abs(p.y - surface - face) / 0.55;
        if (proximity > 0) {
          tip.set(x, surface + face + Math.sign(face) * 0.07, p.z);
          put(this.contacts, contacts++, tip, identity, 0.17 + 0.11 * proximity, 0.15, 0.17 + 0.11 * proximity, tint);
        }
        if (move === transfers.at(-1) && (route || transfers.length <= 3)) {
          this.trackedMove = move;
          this.trackedPosition.copy(p);
          for (let j = 0; route && j < this.guide.instanceMatrix.count; j++) {
            const along = j / (this.guide.instanceMatrix.count - 1);
            tip.set(x + 4 * bend * along * (1 - along), y[move.from.phase] + dy * along, p.z);
            put(this.guide, guide++, tip, identity, 0.025, 0.025, 0.025, tint);
          }
        }
      } else {
        if (lipid) normal.set(lane, (depth - 0.5) * 1.85, 0.47 + depth * 0.32).normalize();
        else normal.copy(cut).addScaledVector(axis, lane * 0.5).addScaledVector(tip.set(0,0,1), depth * 0.45).normalize();
        const r = { pool: rad + 1.05, membrane: rad, lumen: rad * 0.40 }, dr = r[move.to.phase] - r[move.from.phase];
        p.copy(normal).multiplyScalar(r[move.from.phase] + dr * f).add(this.whole.position);
        const pinch = this.shearUniforms.pinch.value;
        if (pinch > 0) {
          const a = Math.max(0.001, Math.abs(normal.x)), ratio = this.shearUniforms.birthRatio.value;
          p.x += normal.x * rad * pinch * (2 * ratio - 1);
          const adjust = rad * pinch * (2 * ratio * Math.sqrt(a / (1 + a)) - 1);
          p.y += normal.y * adjust;
          p.z += normal.z * adjust;
        }
        p.y += bend * arc;
        motion.copy(normal).multiplyScalar(dr); motion.y += 4 * bend * (1 - 2 * f); motion.normalize();
      }
      const size = patch ? 0.14 : 0.09;
      if (lipid) {
        q.setFromUnitVectors(axis, normal).multiply(lean.setFromAxisAngle(axis, i * phi));
        const aspect = run.membrane.findIndex((place) => place.species === move.from.species) % 2 ? 1.35 : 1;
        put(this.travelLipids.heads, lipids, p, q, size * aspect, size * 0.84, size / aspect, tint);
        put(this.travelLipids.tails, lipids++, p, q, size * 1.45, size * 2.0, size * 1.45);
      } else put(this.travelSolutes, solutes++, p, identity, size, size, size, tint);
      q.setFromUnitVectors(axis, motion);
      tip.copy(p).addScaledVector(motion, -size * 2.65);
      put(this.streaks, n, tip, q, size * 0.13, size * 2.4, size * 0.13, tint);
      tip.copy(p).addScaledVector(motion, -size * 1.39);
      put(this.arrows, n++, tip, q, size * 0.48, size * 0.96, size * 0.48, tint);
    }
    finish(this.travelLipids.heads, lipids); finish(this.travelLipids.tails, lipids);
    finish(this.travelSolutes, solutes); finish(this.arrows, n); finish(this.streaks, n);
    finish(this.contacts, contacts);
    finish(this.guide, guide);
  }
  draw(state, run, level, layer, time, slot, route = null, reducedMotion = false) {
    const sample = state.sample,
      e = state.event;
    const ended = e?.cause && (!run.pop || e.slot === slot) && !sample?.membrane_footprint_quanta;
    const population = run.pop && level === "vesicle";
    this.whole.visible = level === "vesicle" && !ended && !population;
    this.release.visible = level === "vesicle" && Boolean(ended) && !population;
    this.population.visible = population;
    this.patch.visible = level === "membrane";
    this.molecule.visible = level === "molecule";
    this.flights.visible = Boolean((this.whole.visible || this.patch.visible) && sample?.membrane_footprint_quanta && !ended);
    this.trackedMove = null;
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
        if (n < 0) return inkFor(run, run.membrane[j].species);
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
          for (let k = 0; k < Math.min(32, count) && dots < this.solutes.instanceMatrix.count; k++) {
            const pos = direction(k, 32).applyAxisAngle(axis, j * phi).multiplyScalar(
              lumenScale * 0.82 * Math.cbrt((((k * 0.754877 + j * 0.21) % 1) + 0.02) / 1.02),
            );
            put(this.solutes, dots++, pos, identity, 0.031, 0.031, 0.031, inkFor(run, place.species));
          }
        }
        finish(this.solutes, dots);
      }
      if (this.patch.visible) {
        const items = [];
        for (let j = 0; j < 7; j++)
          for (let i = 0; i < 16; i++) {
            const {x, y, z} = siteOf(i, j);
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
    const split = this.whole.visible ? run.divisionAt(time) : null;
    this.drawDivision(run, reducedMotion ? (split?.after ? { ...split, part: 0.38 } : null) : split, rad);
    if (this.flights.visible) this.drawTraffic(run, state, time, rad, this.patch.visible, route, reducedMotion);
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
