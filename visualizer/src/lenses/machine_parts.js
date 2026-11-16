// A molecular machine drawn from its file (schema/MACHINES.md): the envelope round it, each
// part as the simple shape its kind names, at the sizes the file gives, and at level 3 the
// copies of a protein where the file gives how many. Nothing here belongs to one machine or
// one species: every size, count and place is the file's, and every number the file does not
// give is said in the file to be the picture's choice. What is drawn is an illustration; Cells
// has no model of any machine drawn here, and the panel says so.
//
// The machine is built in nanometres along its own axis (y, out of the cell; zero at the
// middle of the membrane it sits in), in a group scaled to the view's micrometres. The lens
// places and turns that group at the place the machine stands (a flagellum's foot).
//
// The lens gives a small context: `material(role, options)` returns a material for a role
// (`membrane`, `wall`, `rotor`, `stator`, `bearing`, `export`, `mark`, `swept`, `arrow`), and
// `add(object, id)` puts an object in the picture, to be chosen under `id` where one is given.
// What turns, and how, is machine_motion.js's: this module only says which objects turn about
// the machine's axis, which about a part's own line, and what each set of marks looks like
// when it turns too fast to be drawn sharp.

import * as THREE from "../three.js";

export const MACHINE_FORMAT = "cells.visualizer.machine@1";
export const KINDS = ["ring", "units", "rod", "tube", "band"];
export const LAYOUTS = ["round", "band", "smooth", "bundle", "beside", "spokes", "axis", "along"];
export const NM = 0.001; // one nanometre in the view's units, micrometres
// The envelope is opened by a wedge towards the viewer (+z), a quarter of a turn wide, so the
// parts inside the membranes can be seen; the parts themselves are whole.
export const WEDGE = 0.25;
// Segments round a body of revolution, at each level: the picture's choice.
const ROUND = { 1: 32, 2: 64, 3: 64 };

/** A number the file gives as one value or as a range of two: its middle. */
export const mid = (value) => (Array.isArray(value) ? (value[0] + value[1]) / 2 : value);
const nm = (node) => (node && node.nm !== undefined ? node.nm : undefined);

/** Where each part and layer is along the axis and how wide: { lo, hi, mid, radius, bore }, in nm. */
export function spans(machine) {
  const out = new Map();
  for (const layer of machine.layers || []) {
    const z = mid(nm(layer.z_nm)), t = nm(layer.thick_nm) ?? 0;
    out.set(layer.id, { lo: z - t / 2, hi: z + t / 2, mid: z, radius: mid(nm(layer.across_nm)) / 2, bore: 0 });
  }
  for (const part of machine.parts) {
    const z = nm(part.z_nm) || nm(part.body?.z_nm);
    if (!Array.isArray(z)) continue;
    const across = mid(nm(part.across_nm) ?? nm(part.body?.across_nm) ?? 0);
    out.set(part.id, { lo: z[0], hi: z[1], mid: (z[0] + z[1]) / 2, radius: across / 2, bore: (mid(nm(part.bore_nm)) || 0) / 2 });
  }
  return out;
}

/** The citation of a source in a few words: "Nakamura and Minamino 2019", "Mandela and others 2022", "UniProt". */
export function cite(source) {
  if (!source) return "";
  const text = source.text || "";
  const year = /\((\d{4})\)/.exec(text)?.[1];
  if (!year) return text.split(/[,:]/)[0];
  const names = text.split(" (")[0].split(/, | and /).map((author) => author.trim().split(" ")[0]).filter((name) => name && name !== "others");
  const others = /\band others\b/.test(text.split(" (")[0]) || names.length > 2;
  return `${names[0]}${others ? " and others" : names.length === 2 ? ` and ${names[1]}` : ""} ${year}`;
}

/**
 * What the file's own rules ask that a reader can check without the saved papers: its format,
 * the kinds and layouts it uses, a basis for every number, places that agree with the spans
 * and bores, and the parts that turn being the rotor's. Returns what is broken, in words.
 */
export function problemsOf(machine) {
  const problems = [];
  if (machine.format !== MACHINE_FORMAT) problems.push(`its format is ${JSON.stringify(machine.format)}`);
  const sentences = machine.sentences || {}, sources = machine.sources || {};
  const walk = (node, where) => {
    if (Array.isArray(node)) return node.forEach((item, index) => walk(item, `${where}[${item?.id ?? item?.gene ?? index}]`));
    if (!node || typeof node !== "object") return;
    const isNumber = ["nm", "n", "turns_per_s", "most_turns_per_s"].some((key) => key in node);
    if (isNumber) {
      const bases = ["says", "read", "choice", "derived"].filter((key) => key in node);
      if (bases.length !== 1) problems.push(`${where}: a number with ${bases.length ? bases.join(" and ") : "no basis"}`);
      if (node.derived !== undefined && !(node.from || node.from_says)) problems.push(`${where}: worked out from nothing named`);
      if (node.read) {
        const source = sources[node.read.source];
        if (source?.standing !== "open paper, numbers only") problems.push(`${where}: read from ${node.read.source}, which is not an open paper whose numbers alone are taken`);
        if (!node.read.where) problems.push(`${where}: read with no place in the paper`);
      }
    }
    for (const key of ["says", "also_says", "caveat_says", "from_says"]) {
      for (const id of [node[key]].flat().filter((id) => typeof id === "string")) if (!sentences[id]) problems.push(`${where}: ${key} ${id}, which is no sentence`);
    }
    for (const [key, value] of Object.entries(node)) if (key !== "sentences" && key !== "sources") walk(value, `${where}.${key}`);
  };
  for (const key of ["layers", "spacings", "parts", "not_drawn", "motion", "disagreements"]) walk(machine[key], key);
  for (const [id, sentence] of Object.entries(sentences)) {
    const source = sources[sentence.source];
    if (!source) problems.push(`sentence ${id}: no source ${sentence.source}`);
    else if (source.class !== "permissive") problems.push(`sentence ${id}: a sentence of ${sentence.source}, which is not permissive`);
  }
  const at = spans(machine), byId = new Map(machine.parts.map((part) => [part.id, part]));
  const overlap = (a, b) => a.lo < b.hi && b.lo < a.hi;
  for (const part of machine.parts) {
    if (!KINDS.includes(part.kind)) problems.push(`${part.id}: a kind the viewer does not draw, ${part.kind}`);
    const here = at.get(part.id);
    if (!here) {
      problems.push(`${part.id}: no span along the axis`);
      continue;
    }
    if (part.in && !(at.has(part.in) && overlap(here, at.get(part.in)))) problems.push(`${part.id}: not in ${part.in}`);
    if (part.under && !(at.has(part.under) && here.hi <= at.get(part.under).lo + 1e-9)) problems.push(`${part.id}: not under ${part.under}`);
    for (const key of ["inside", "within"]) {
      const outer = part[key] && at.get(part[key]);
      if (!part[key]) continue;
      if (!outer || here.radius > outer.bore + 1e-9) problems.push(`${part.id}: does not fit ${part[key]}'s bore`);
      if (key === "within" && outer && !(outer.lo <= here.lo && here.hi <= outer.hi)) problems.push(`${part.id}: not within ${part[key]} along the axis`);
    }
    if (part.kind === "rod" && (Math.abs(here.lo - (at.get(part.from)?.hi ?? NaN)) > 0.5 || Math.abs(here.hi - (at.get(part.to)?.mid ?? NaN)) > 0.5)) problems.push(`${part.id}: does not run from ${part.from} to ${part.to}`);
    if (part.kind === "units") {
      const contact = nm(part.radius_nm), inner = at.get(machine.parts.find((other) => other.role === "rotor" && other.in === part.in)?.id);
      const rim = Math.max(...machine.parts.filter((other) => other.role === "rotor" && other.kind === "ring").map((other) => at.get(other.id)?.radius || 0));
      if (inner && !(inner.radius < contact && contact <= rim)) problems.push(`${part.id}: meets the rotor at ${contact} nm, not between the ring it stands in and the widest ring's rim`);
      const arm = nm(part.arm?.z_nm), to = at.get(part.arm?.to);
      if (arm && to && (Math.abs(arm[0] - here.hi) > 0.5 || Math.abs(arm[1] - to.mid) > 0.5)) problems.push(`${part.id}: its arm does not run from the body to the middle of ${part.arm.to}`);
    }
    if (part.kind === "rod") {
      for (const ring of machine.parts.filter((other) => other.kind === "ring" && other.role === "bearing")) if (here.radius > (at.get(ring.id)?.bore ?? 0) + 1e-9) problems.push(`${part.id} does not pass through ${ring.id}'s bore`);
    }
    for (const sub of part.subunits?.of || []) {
      if (!part.proteins.some((protein) => protein.id === sub.id)) problems.push(`${part.id}: subunit ${sub.gene} is not among its proteins`);
      if (sub.layout && !LAYOUTS.includes(sub.layout)) problems.push(`${part.id}: ${sub.gene} has a layout the viewer does not draw, ${sub.layout}`);
    }
  }
  // Parts set end to end along a line meet.
  for (const part of machine.parts) {
    const after = part.from && byId.get(part.from), here = at.get(part.id);
    if (after && part.kind !== "rod" && after.kind !== "ring" && here && Math.abs(at.get(after.id).hi - here.lo) > 0.5) problems.push(`${after.id} does not meet ${part.id}`);
  }
  const turning = machine.parts.filter((part) => part.turns).map((part) => part.id).sort();
  const rotor = [...(machine.motion?.rotor?.parts || [])].sort();
  if (JSON.stringify(turning) !== JSON.stringify(rotor)) problems.push(`the parts that turn (${turning.join(", ")}) are not the rotor's (${rotor.join(", ")})`);
  return problems;
}

// ------------------------------------------------------------------ shapes

/** A ring as a body of revolution: inner and outer radius, from lo to hi, its corners a little round. */
function ringProfile(inner, outer, lo, hi, step = null) {
  const r = Math.min(0.8, (outer - inner) / 4, (hi - lo) / 4);
  const points = [];
  const push = (x, y) => points.push(new THREE.Vector2(Math.max(0, x), y));
  push(inner + r, lo);
  push(outer - r, lo);
  push(outer, lo + r);
  if (step) {
    // The wider ring below, the narrower one above (a ring and its step: the MS ring's M and S rings).
    const at = lo + (hi - lo) * 0.55;
    push(outer, at);
    push(step, at);
    push(step, hi - r);
    push(step - r, hi);
  } else {
    push(outer, hi - r);
    push(outer - r, hi);
  }
  push(inner + r, hi);
  push(inner, hi - r);
  push(inner, lo + r);
  push(inner + r, lo);
  return points;
}

const lathe = (points, segments, start = 0, length = Math.PI * 2) => new THREE.LatheGeometry(points, segments, start, length);

/** A thin band round the axis: what a mark on a ring looks like when it is turned too fast to be seen. */
const sweptRing = (inner, outer, lo, hi, segments) => lathe([new THREE.Vector2(inner, lo), new THREE.Vector2(outer, lo), new THREE.Vector2(outer, hi), new THREE.Vector2(inner, hi), new THREE.Vector2(inner, lo)], segments);

/** The curve of a bent tube that starts along the axis at `lo`, goes `length` along its own line and ends at height `hi`. */
export function bentLine(lo, hi, length) {
  const rise = hi - lo, aside = length > rise ? Math.sqrt(length * length - rise * rise) : 0;
  return new THREE.QuadraticBezierCurve3(new THREE.Vector3(0, lo, 0), new THREE.Vector3(0, lo + rise * 0.6, 0), new THREE.Vector3(aside, hi, 0));
}

const UP = new THREE.Vector3(0, 1, 0);

/** A frame along a curve at a share `t` of its length: its point, its tangent and two normals. */
function frameAt(curve, t) {
  const point = curve.getPointAt(t), tangent = curve.getTangentAt(t).normalize();
  const side = new THREE.Vector3(0, 0, 1).cross(tangent).normalize();
  if (side.lengthSq() < 1e-6) side.set(1, 0, 0);
  const other = new THREE.Vector3().crossVectors(tangent, side).normalize();
  return { point, tangent, side, other };
}

/**
 * Places `count` copies on `strands` strands along a curve, each at a share of the length and
 * an angle round the curve's own line, turned on by `angle`: the matrices of an instanced mesh.
 * Called again with a new angle as the part turns about its own line; nothing is rebuilt.
 */
export function placeAlong(mesh, curve, { count, strands, radius, angle = 0, from = 0, to = 1 }) {
  const each = Math.ceil(count / strands), matrix = new THREE.Matrix4(), turn = new THREE.Quaternion(), place = new THREE.Vector3();
  let index = 0;
  for (let step = 0; step < each && index < count; step++) {
    const t = from + ((step + 0.5) / each) * (to - from);
    const { point, tangent, side, other } = frameAt(curve, t);
    for (let strand = 0; strand < strands && index < count; strand++, index++) {
      // Each strand a little further round at each step, so that the strands lie as a helix: the picture's choice.
      const phi = angle + (strand / strands) * Math.PI * 2 + step * 0.12;
      place.copy(point).addScaledVector(side, Math.cos(phi) * radius).addScaledVector(other, Math.sin(phi) * radius);
      turn.setFromUnitVectors(UP, tangent);
      matrix.compose(place, turn, new THREE.Vector3(1, 1, 1));
      mesh.setMatrixAt(index, matrix);
    }
  }
  mesh.count = index;
  mesh.instanceMatrix.needsUpdate = true;
  return index;
}

function instanced(geometry, material, placements) {
  const mesh = new THREE.InstancedMesh(geometry, material, Math.max(1, placements.length));
  const matrix = new THREE.Matrix4(), scale = new THREE.Vector3(1, 1, 1), quaternion = new THREE.Quaternion();
  placements.forEach(({ position, turn = 0, along = null }, index) => {
    if (along) quaternion.setFromUnitVectors(UP, along);
    else quaternion.setFromAxisAngle(UP, turn);
    matrix.compose(position, quaternion, scale);
    mesh.setMatrixAt(index, matrix);
  });
  mesh.count = placements.length;
  return mesh;
}

/** `n` copies evenly round the axis at a radius and a height. */
const round = (n, radius, y, offset = 0) => Array.from({ length: n }, (_, k) => {
  const phi = offset + (k / n) * Math.PI * 2;
  return { position: new THREE.Vector3(Math.sin(phi) * radius, y, Math.cos(phi) * radius), turn: phi };
});

// ------------------------------------------------------------------ the machine

/**
 * Builds the machine at a level of detail (1 Outline, 2 Parts, 3 Subunits). Returns:
 * - `root`: the group, in nanometres along its own axis, scaled to micrometres;
 * - `items`: each part that can be chosen, with its id, what it is, and a point for its name;
 * - `spin`: the group that turns about the machine's axis (the rotor's rings and rod);
 * - `line`: what turns about a bent part's own line (the hook), and the straight parts after it;
 * - `sets`: each set of marks or copies that shows a turn: what turns it, how many like copies
 *   it has (its period is a turn over that), its objects, and its swept form;
 * - `arrow`: the arrowhead that shows the way the rotor turns.
 */
export function buildMachine(ctx, machine, { level = 2 } = {}) {
  const segments = ROUND[level] || 64;
  const at = spans(machine), byId = new Map(machine.parts.map((part) => [part.id, part]));
  const pick = (part) => `machine:${machine.id}:${part.id}`;
  const root = new THREE.Group();
  root.scale.setScalar(NM);
  root.userData.machine = machine.id;
  const spin = new THREE.Group(); // turns about the machine's axis
  spin.name = "spin";
  root.add(spin);
  const items = [], sets = [];
  const drawn = (part) => (part.levels || [1, 2, 3]).includes(level);
  const material = (role, options = {}) => ctx.material(role, options);
  const put = (parent, object, id) => {
    parent.add(object);
    ctx.add(object, id);
    return object;
  };

  // The envelope: each layer a slab round the machine, opened by a wedge, with a hole the size of the widest ring set in it.
  for (const layer of machine.layers || []) {
    const span = at.get(layer.id);
    const hole = Math.max(0, ...machine.parts.filter((part) => part.in === layer.id && part.kind === "ring").map((part) => at.get(part.id)?.radius || 0)) + 0.6;
    const geometry = lathe(ringProfile(hole, span.radius, span.lo, span.hi), segments, Math.PI * WEDGE, Math.PI * 2 * (1 - WEDGE));
    const mesh = new THREE.Mesh(geometry, material(layer.role || "membrane", { layer: layer.id }));
    mesh.renderOrder = 4;
    put(root, mesh, `machine:${machine.id}:${layer.id}`);
    items.push({ id: `machine:${machine.id}:${layer.id}`, part: layer.id, label: layer.label, role: layer.role || "membrane", layer: true, anchor: new THREE.Vector3(span.radius * 0.72, span.mid, -span.radius * 0.45) });
  }

  // The bent part's line, and where the straight parts after it point.
  const bent = machine.parts.find((part) => part.kind === "tube" && part.bend);
  let curve = null, after = null;
  if (bent && at.get(bent.id)) {
    const span = at.get(bent.id);
    curve = bentLine(span.lo, span.hi, mid(nm(bent.length_nm)) ?? span.hi - span.lo);
    after = new THREE.Group(); // at the bent part's end, its y along the end's direction
    after.position.copy(curve.getPointAt(1));
    after.quaternion.setFromUnitVectors(UP, curve.getTangentAt(1).normalize());
    after.name = "after";
    root.add(after);
  }
  const afterSpin = new THREE.Group(); // turns about the line of the straight parts after the bent one
  afterSpin.name = "after-spin";
  after?.add(afterSpin);
  const lineSets = []; // sets placed along the bent part's own line, turned by placing them again
  let afterFrom = null; // where along the straight line the next straight part begins
  // The parts set end to end after the bent one: one set between it and another, and what starts from such a part.
  const follows = new Set();
  for (const part of machine.parts) if (curve && (part.between?.includes(bent.id) || follows.has(part.from))) follows.add(part.id);

  for (const part of machine.parts) {
    const span = at.get(part.id);
    if (!span || !drawn(part)) continue;
    const id = pick(part), turns = Boolean(part.turns);
    const followsBent = follows.has(part.id);
    const parent = part.id === bent?.id ? root : followsBent ? afterSpin : turns ? spin : root;
    const counted = level === 3 ? (part.subunits?.of || []).filter((sub) => sub.layout) : [];
    const body = material(part.role, { part: part.id });
    const meshes = [];
    const add = (object) => meshes.push(put(parent, object, id));
    // Along the straight parts after the bent one, each starts where the one before it ended.
    const base = followsBent ? (afterFrom ?? 0) : 0, length = span.hi - span.lo;
    if (followsBent) afterFrom = base + length;
    let anchor = new THREE.Vector3(span.radius + 2, span.mid, 0);

    if (part.kind === "ring") {
      const bore = span.bore || (nm(part.channel_nm) ? mid(nm(part.channel_nm)) / 2 : span.radius * 0.35), step = nm(part.step_nm) ? mid(nm(part.step_nm)) / 2 : null;
      const ownBlocks = counted.filter((sub) => sub.count && ["round", "bundle"].includes(sub.layout) && !sub.z_nm);
      if (!ownBlocks.length) add(new THREE.Mesh(lathe(ringProfile(bore, span.radius, span.lo, span.hi, step), segments), body));
      for (const sub of counted) {
        const n = sub.count?.n, protein = material(part.role, { part: part.id, protein: sub.id });
        if (sub.layout === "round" && n) {
          const radius = mid(nm(sub.radius_nm)) ?? (span.radius + bore) / 2, z = nm(sub.z_nm) || [span.lo, span.hi];
          const deep = nm(sub.radius_nm) ? 3 : (span.radius - bore) * 0.9, tall = (z[1] - z[0]) * 0.9, wide = ((2 * Math.PI * radius) / n) * 0.78;
          const blocks = instanced(new THREE.BoxGeometry(wide, tall, deep), protein, round(n, radius, (z[0] + z[1]) / 2));
          add(blocks);
          if (turns) sets.push(swept(ctx, machine, part, { objects: [blocks], copies: n, about: "axis", geometry: sweptRing(radius - deep / 2, radius + deep / 2, z[0] + tall * 0.05, z[1] - tall * 0.05, segments), parent }));
        } else if (sub.layout === "band" || sub.layout === "smooth") {
          const share = 0.2, z = sub.layout === "band" ? [span.lo, span.lo + length * share] : [span.hi - length * share, span.hi];
          add(new THREE.Mesh(lathe(ringProfile(bore, span.radius + 0.3, z[0], z[1]), segments), protein));
        } else if (sub.layout === "bundle" && n) {
          const radius = span.radius * 0.45, top = [span.hi - Math.min(8, length / 2), span.hi];
          const all = counted.filter((other) => other.layout === "bundle"), total = all.reduce((sum, other) => sum + (other.count?.n || 0), 0);
          const first = all.slice(0, all.indexOf(sub)).reduce((sum, other) => sum + (other.count?.n || 0), 0);
          const places = Array.from({ length: n }, (_, k) => {
            const j = first + k, phi = (j / total) * Math.PI * 2, y = top[0] + 1.2 + (j / total) * (top[1] - top[0] - 2.4); // a right-handed helix
            return { position: new THREE.Vector3(Math.sin(phi) * radius, y, Math.cos(phi) * radius), turn: phi };
          });
          add(instanced(new THREE.CapsuleGeometry(1.2, 3, 3, 8), protein, places));
        } else if (sub.layout === "beside") {
          add(instanced(new THREE.CapsuleGeometry(1.4, 4, 3, 8), protein, [{ position: new THREE.Vector3(span.radius * 0.95, span.hi - 4, -span.radius * 0.4) }]));
        } else if (sub.layout === "spokes" && n) {
          const reach = (at.get(sub.to)?.bore || span.radius * 2) - span.radius, y = span.mid;
          const places = round(n, span.radius + reach / 2, y).map((place) => ({ ...place, along: new THREE.Vector3(Math.sin(place.turn), 0, Math.cos(place.turn)) }));
          add(instanced(new THREE.CylinderGeometry(0.5, 0.5, reach, 6), protein, places));
        } else if (sub.layout === "axis") {
          add(new THREE.Mesh(new THREE.CylinderGeometry(0.9, 0.9, length, 8).translate(0, span.mid, 0), protein));
        } else if (sub.layout === "round" && !n && nm(sub.radius_nm)) {
          add(new THREE.Mesh(lathe(ringProfile(mid(nm(sub.radius_nm)) - 1.5, mid(nm(sub.radius_nm)) + 1.5, ...(nm(sub.z_nm) || [span.lo, span.hi])), segments), protein));
        }
      }
      if (turns && !counted.some((sub) => sub.layout === "round" && sub.count)) {
        // One ridge on the outer face (of a stepped ring, on its wider part): the mark that shows the ring turn.
        const face = step ? [span.lo, span.lo + length * 0.55] : [span.lo, span.hi];
        const tall = (face[1] - face[0]) * 0.6, centre = (face[0] + face[1]) / 2, deep = 1.2;
        const ridge = new THREE.Mesh(new THREE.BoxGeometry(2.4, tall, deep).translate(0, centre, span.radius + deep / 2 - 0.2), material("mark", { part: part.id }));
        add(ridge);
        sets.push(swept(ctx, machine, part, { objects: [ridge], copies: 1, about: "axis", geometry: sweptRing(span.radius - 0.2, span.radius + deep, centre - tall / 2, centre + tall / 2, segments), parent }));
      }
    } else if (part.kind === "units") {
      const n = part.count?.n || 0, contact = nm(part.radius_nm), across = mid(nm(part.body.across_nm)), z = nm(part.body.z_nm);
      const centre = contact + across / 2, tall = z[1] - z[0];
      add(instanced(new THREE.CapsuleGeometry(across / 2, Math.max(0.1, tall - across), 4, level === 1 ? 8 : 12), body, round(n, centre, (z[0] + z[1]) / 2, Math.PI / n)));
      const arm = nm(part.arm?.z_nm);
      if (arm) add(instanced(new THREE.CylinderGeometry(0.6, 0.6, arm[1] - arm[0], 6), body, round(n, centre + across * 0.2, (arm[0] + arm[1]) / 2, Math.PI / n)));
      anchor = new THREE.Vector3(Math.sin(Math.PI / n) * (centre + across), (z[0] + z[1]) / 2, Math.cos(Math.PI / n) * (centre + across));
    } else if (part.kind === "rod") {
      add(new THREE.Mesh(new THREE.CylinderGeometry(span.radius, span.radius, length, Math.max(16, segments / 2)).translate(0, span.mid, 0), body));
      if (turns) {
        const stripe = new THREE.Mesh(new THREE.BoxGeometry(1.6, length * 0.9, 0.8).translate(0, span.mid, span.radius + 0.2), material("mark", { part: part.id }));
        add(stripe);
        sets.push(swept(ctx, machine, part, { objects: [stripe], copies: 1, about: "axis", geometry: sweptRing(span.radius, span.radius + 0.6, span.lo + length * 0.05, span.hi - length * 0.05, segments), parent }));
      }
    } else if (part.kind === "tube" && part.id === bent?.id) {
      const radius = span.radius, blocks = counted.find((sub) => sub.layout === "along" && sub.count);
      add(new THREE.Mesh(new THREE.TubeGeometry(curve, 48, blocks ? radius * 0.45 : radius, level === 1 ? 12 : 16), body));
      if (blocks) {
        const strands = part.subunits.strands?.n || 1, n = blocks.count.n;
        const mesh = new THREE.InstancedMesh(new THREE.BoxGeometry(radius * 0.5, (2.2 * mid(nm(part.length_nm))) / Math.ceil(n / strands), radius * 0.5), material(part.role, { part: part.id, protein: blocks.id }), n);
        placeAlong(mesh, curve, { count: n, strands, radius: radius * 0.72 });
        add(mesh);
        lineSets.push({ mesh, count: n, strands, radius: radius * 0.72 });
        if (turns) sets.push(swept(ctx, machine, part, { objects: [mesh], copies: strands, about: "line", curve, place: { count: n, strands, radius: radius * 0.72 }, geometry: new THREE.TubeGeometry(curve, 48, radius * 1.01, 16), parent: root }));
      } else if (turns) {
        const dots = new THREE.InstancedMesh(new THREE.SphereGeometry(0.9, 8, 6), material("mark", { part: part.id }), 12);
        placeAlong(dots, curve, { count: 12, strands: 1, radius: radius + 0.2, from: 0.04, to: 0.96 });
        add(dots);
        sets.push(swept(ctx, machine, part, { objects: [dots], copies: 1, about: "line", curve, place: { count: 12, strands: 1, radius: radius + 0.2, from: 0.04, to: 0.96 }, geometry: new THREE.TubeGeometry(curve, 48, radius + 0.9, 16), parent: root }));
      }
      const half = curve.getPointAt(0.5);
      anchor = new THREE.Vector3(half.x + radius + 3, half.y, 0);
    } else if (part.kind === "band" || part.kind === "tube") {
      // A straight part after the bent one, along its end's direction, from `base` for `length`.
      const radius = part.kind === "band" ? (at.get(bent?.id)?.radius || 10) + 0.5 : span.radius, bore = span.bore;
      const blocks = counted.find((sub) => sub.layout === "along");
      const shape = bore && !blocks ? lathe(ringProfile(bore, radius, base, base + length), segments) : new THREE.CylinderGeometry(blocks ? radius * 0.45 : radius, blocks ? radius * 0.45 : radius, length, segments).translate(0, base + length / 2, 0);
      add(new THREE.Mesh(shape, body));
      if (blocks) {
        const strands = part.subunits.strands?.n || 1, step = mid(nm(blocks.step_nm)) || 5, each = Math.floor(length / step);
        const places = [];
        for (let k = 0; k < each; k++) for (let s = 0; s < strands; s++) {
          const phi = (s / strands) * Math.PI * 2 + k * 0.12, r = radius * 0.72;
          places.push({ position: new THREE.Vector3(Math.sin(phi) * r, base + (k + 0.5) * step, Math.cos(phi) * r), turn: phi });
        }
        const mesh = instanced(new THREE.BoxGeometry(radius * 0.5, step * 0.86, radius * 0.5), material(part.role, { part: part.id, protein: blocks.id }), places);
        add(mesh);
        if (turns) sets.push(swept(ctx, machine, part, { objects: [mesh], copies: strands, about: "after", geometry: new THREE.CylinderGeometry(radius * 1.01, radius * 1.01, length * 0.98, segments, 1, true).translate(0, base + length / 2, 0), parent: afterSpin }));
      } else if (turns && part.kind === "tube") {
        const stripe = new THREE.Mesh(new THREE.BoxGeometry(1.6, length * 0.92, 0.8).translate(0, base + length / 2, radius + 0.2), material("mark", { part: part.id }));
        add(stripe);
        sets.push(swept(ctx, machine, part, { objects: [stripe], copies: 1, about: "after", geometry: new THREE.CylinderGeometry(radius + 0.6, radius + 0.6, length * 0.92, segments, 1, true).translate(0, base + length / 2, 0), parent: afterSpin }));
      }
      // Its name's point, in the machine's frame: from the straight line's frame at the bent part's end.
      const point = new THREE.Vector3(radius + 3, base + Math.min(length / 2, 20), 0);
      anchor = after ? point.applyQuaternion(after.quaternion).add(after.position) : point;
    }
    items.push({ id, part: part.id, label: part.label, role: part.role, turns, about: part.id === bent?.id ? "line" : followsBent ? "after" : turns ? "axis" : null, proteins: part.proteins, anchor, objects: meshes });
  }

  // The arrowhead: a curved arrow round the machine's axis, a little outside the outer membrane, pointing the way the rotor turns.
  const arrow = new THREE.Group();
  arrow.name = "arrow";
  const way = machine.motion?.rotor?.way;
  if (way) {
    const outer = machine.layers?.length ? at.get(machine.layers.at(-1).id) : null;
    const y = (outer ? outer.hi : 0) + 6, radius = Math.max(16, (at.get(bent?.id)?.radius || 10) + 6);
    const sign = /^counter-clockwise/.test(way) ? 1 : -1; // counter-clockwise seen from outside: a positive turn about the outward axis
    const arc = 1.35 * Math.PI, start = Math.PI * 0.35;
    const path = new THREE.CatmullRomCurve3(Array.from({ length: 25 }, (_, k) => {
      const phi = start + sign * (k / 24) * arc;
      return new THREE.Vector3(Math.sin(phi) * radius, y, Math.cos(phi) * radius);
    }));
    const look = material("arrow", {});
    arrow.add(new THREE.Mesh(new THREE.TubeGeometry(path, 40, 0.7, 8), look));
    const tip = path.getPointAt(1), along = path.getTangentAt(1).normalize();
    const head = new THREE.Mesh(new THREE.ConeGeometry(1.9, 4.6, 12), look);
    head.position.copy(tip).addScaledVector(along, 1.6);
    head.quaternion.setFromUnitVectors(UP, along);
    arrow.add(head);
    arrow.userData = { sign, way, radius, y };
    root.add(arrow);
    ctx.add(arrow, null);
  }
  return { root, items, spin, curve, after, afterSpin, lineSets, sets, arrow, level, machine };
}

/** A set of marks or copies that shows a turn, with its swept form: the marks smeared round, drawn while they turn too fast to be seen. */
function swept(ctx, machine, part, { objects, copies, about, geometry, parent, curve = null, place = null }) {
  const blur = new THREE.Mesh(geometry, ctx.material("swept", { part: part.id }));
  blur.visible = false;
  blur.renderOrder = 6;
  blur.userData.unpickable = true;
  parent.add(blur);
  ctx.add(blur, null);
  return { part: part.id, about, copies, period: 1 / copies, objects, blur, curve, place };
}

// ------------------------------------------------------------------ what the panel says

const SIZE_WORDS = { across_nm: "Across", step_nm: "The narrower ring, across", bore_nm: "Its bore", z_nm: "Along the axis", length_nm: "Length along its own line", channel_nm: "Its central channel", radius_nm: "Where a unit meets the rotor, from the axis", thick_nm: "Thickness" };

/** A number in words: "about 45 nm", "30 to 32 nm", "34". */
export function valueWords(node, unit = "nm") {
  const value = node.nm ?? node.n ?? node.most_turns_per_s ?? node.turns_per_s;
  const said = Array.isArray(value) ? `${value[0].toLocaleString("en-US")} to ${value[1].toLocaleString("en-US")}` : Number(value).toLocaleString("en-US");
  return `${node.about ? "about " : ""}${said}${unit && node.nm !== undefined ? ` ${unit}` : ""}`;
}

/** Where a number comes from, in words: the organism as the sentence names it and the paper; the picture's choice; how it was worked out. */
export function basisWords(machine, node) {
  const sentences = machine.sentences || {}, sources = machine.sources || {};
  if (node.choice !== undefined) return `the picture's choice: ${node.choice}`;
  if (node.derived !== undefined) return `worked out: ${node.derived}`;
  if (node.read) return `${cite(sources[node.read.source])}, ${node.read.where} (an open paper with no licence declared: its number alone is taken)${node.measured_in ? `; in ${node.measured_in.replace(/^other bacteria: /, "")}` : ""}`;
  const keys = [node.says].flat().filter(Boolean);
  const papers = [...new Set(keys.map((key) => cite(sources[sentences[key]?.source])))].join("; ");
  const where = node.measured_in === "not stated" ? "the sentence names no species" : node.measured_in ? `measured in ${node.measured_in}` : "";
  return [where, papers].filter(Boolean).join(" · ");
}

/** What the file says of how a number was measured (`how`), and the caveats its papers carry (a source's `caveat`). */
function caveatsOf(machine, node) {
  const sources = [...new Set([node.says, node.from_says].flat().filter(Boolean).map((key) => machine.sentences?.[key]?.source))];
  return [node.how || null, ...sources.map((name) => machine.sources?.[name]?.caveat || null)].filter(Boolean);
}

/** The links of a number's papers. */
function linksOf(machine, node) {
  const keys = [node.says, node.from_says].flat().filter(Boolean);
  const names = [...new Set([...keys.map((key) => machine.sentences?.[key]?.source), node.read?.source].filter(Boolean))];
  return names.map((name) => machine.sources[name]).filter(Boolean).map((source) => ({ text: cite(source), url: source.doi ? `https://doi.org/${source.doi}` : source.url }));
}

/** The door from a part into the Protein atlas: the machine's set, and of it this part's proteins. */
export function machineDoor(machine, part) {
  const ids = (part.proteins || []).map((protein) => protein.id);
  if (!ids.length || !machine.set) return null;
  const these = ids.length === 1 ? `${part.proteins[0].gene}` : `these ${ids.length} proteins`;
  return { label: `Show ${these} in the Protein atlas`, lens: "proteins", show: "own", mark: machine.set.mark, value: machine.set.value, ids };
}

/** "Cells has no model of this motor": the machine's own short name, from its file. */
export const noModel = (machine) => `Cells has no model of this ${machine.called || machine.label.toLowerCase()}`;

/**
 * A part of the machine as its panel describes it: what it does, its proteins, each size with
 * where it comes from, what is the picture's choice, where the sources disagree, how it turns
 * or why it stands, and the door into the atlas. `names` maps a protein's id to its name
 * (the species' own proteins); `species` gives the eyebrow.
 */
export function describeMachinePart(machine, partId, { species = null, names = {}, capability = null } = {}) {
  const part = machine.parts.find((item) => item.id === partId) || (machine.layers || []).find((item) => item.id === partId);
  if (!part) return null;
  const isLayer = !machine.parts.includes(part);
  const sizes = [], drawn = [], disagree = [], sentences = new Set();
  const note = (node) => [node.says, node.from_says].flat().filter(Boolean).forEach((key) => sentences.add(key));
  for (const [key, label] of Object.entries(SIZE_WORDS)) {
    const node = part[key];
    if (!node || node.nm === undefined) continue;
    const item = { label: node.of ? `${label}: ${node.of}` : label, detail: valueWords(node), lines: [basisWords(machine, node), ...caveatsOf(machine, node)] };
    if (node.disagree) item.lines.push(`The sources disagree: ${node.disagree}`);
    if (node.also) item.lines.push(`Also: ${node.also.text} (${basisWords(machine, node.also)})`);
    (node.choice !== undefined ? drawn : sizes).push({ ...item, links: linksOf(machine, node) });
    note(node);
  }
  if (part.count) {
    sizes.push({ label: "How many", detail: valueWords(part.count), lines: [basisWords(machine, part.count), ...(part.count.when ? [`When: ${part.count.when}`] : []), ...(part.count.also || []).map((also) => `Also: ${also.text} (${basisWords(machine, also)})`)], links: linksOf(machine, part.count) });
    note(part.count);
    (part.count.also || []).forEach(note);
  }
  if (part.copies) {
    sizes.push({ label: part.copies.of ? `Copies in ${part.copies.of}` : "Copies", detail: valueWords(part.copies), lines: [basisWords(machine, part.copies), ...(part.copies.disagree ? [part.copies.disagree] : [])], links: linksOf(machine, part.copies) });
    note(part.copies);
  }
  for (const figure of part.holds?.figures || []) {
    sizes.push({ label: `What ${part.holds.of} holds`, detail: figure.text, lines: [basisWords(machine, figure)], links: linksOf(machine, figure) });
    note(figure);
  }
  for (const sub of part.subunits?.of || []) {
    if (!sub.count) continue;
    sizes.push({ label: `${sub.gene}, copies`, detail: valueWords(sub.count), lines: [basisWords(machine, sub.count), `Drawn at level 3 (${sub.arranged || sub.layout}).`], links: linksOf(machine, sub.count) });
    note(sub.count);
  }
  if (part.drawn_as) drawn.push({ label: "As drawn", lines: [part.drawn_as.choice] });
  if (part.subunits?.why) drawn.push({ label: "Its copies", lines: [part.subunits.why] });
  for (const item of machine.disagreements || []) {
    if (item.part !== part.id && !(item.part === "motion" && part.turns)) continue;
    disagree.push({ label: item.of[0].toUpperCase() + item.of.slice(1), lines: [item.values, `Drawn: ${item.drawn}.`] });
    [item.says].flat().filter(Boolean).forEach((key) => sentences.add(key));
  }
  const motion = machine.motion || {}, rotor = motion.rotor;
  const how = [];
  if (part.turns && rotor) {
    how.push({ label: "How it turns", lines: [`${rotor.as ? `${rotor.as[0].toUpperCase()}${rotor.as.slice(1)}, it` : "It"} turns ${rotor.way}, seen ${rotor.seen_from?.text || "from outside the cell"}.`, rotor.about?.why?.text && rotor.about.own_line?.includes(part.id) ? rotor.about.why.text : null, rotor.drawn ? `Drawn at ${valueWords(rotor.drawn)} turns a second (${rotor.drawn.as}), at real-life speed unless the flux is slowed; up to ${valueWords(rotor.rate)} at its top speed (${basisWords(machine, rotor.rate)}).` : null, rotor.caveat || null].filter(Boolean) });
    [rotor.says, rotor.seen_from?.says, rotor.rate?.says, rotor.drawn?.from_says, rotor.caveat_says].flat().filter(Boolean).forEach((key) => sentences.add(key));
    if (rotor.seams && !(part.subunits?.of || []).some((sub) => sub.count && sub.layout === "round")) how.push({ label: "Its mark", lines: [rotor.seams.choice] });
  } else if (!isLayer && rotor) {
    const held = (motion.held || []).find((item) => item.parts.includes(part.id));
    if (held) how.push({ label: "Held still", lines: [held.why] });
  }
  const proteins = (part.proteins || []).map((protein) => ({ label: protein.gene, detail: names[protein.id] || protein.id, lines: protein.where ? [protein.where] : [], links: [{ text: `UniProt ${protein.id}`, url: `https://www.uniprot.org/uniprotkb/${protein.id}` }] }));
  if (part.does) [part.does.says].flat().filter(Boolean).forEach((key) => sentences.add(key));
  const quoted = [...sentences].filter((key) => machine.sentences[key] && machine.sources[machine.sentences[key].source]?.class === "permissive").map((key) => `${cite(machine.sources[machine.sentences[key].source])}: "${machine.sentences[key].text}"`);
  const plans = capability ? [{ label: capability.label || "Molecular machines", detail: capability.status || "planned", lines: [capability.plain || ""].filter(Boolean), entity: capability.id }] : [];
  const door = isLayer ? null : machineDoor(machine, part);
  return {
    id: `machine:${machine.id}:${part.id}`,
    kind: "machine part",
    group: "biology",
    label: part.label,
    eyebrow: `${species?.label ? `${species.label} · ` : ""}${machine.label}`,
    chips: [{ label: "Illustration", title: `${noModel(machine)}; drawn from published sizes` }],
    plain: part.does?.text || (isLayer ? `Part of the envelope round the ${machine.called || "machine"}, drawn at the spacing the file gives.` : ""),
    note: `${noModel(machine)}: what is drawn is an illustration, built from sizes and counts that papers give.`,
    doors: door ? [door] : [],
    sections: [
      { title: "Its proteins", items: proteins },
      { title: "Sizes", items: sizes },
      { title: "As drawn", items: drawn },
      { title: "The sources disagree", items: disagree },
      { title: "How it moves", items: how },
      { title: "What Cells plans", items: plans },
    ].filter((section) => section.items.length),
    disclosures: quoted.length ? [{ title: "The sentences", lines: quoted }] : [],
  };
}
