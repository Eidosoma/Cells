// Instanced landmarks, pins and tubes share the viewer's orbit camera and picking.
import * as THREE from "../three.js";
import { pageId } from "./laws_data.js";
import { bridgeKey, displayName, familyKey, modelName } from "./laws_connections.js";

const TAU = Math.PI * 2,
  GOLDEN = Math.PI * (3 - Math.sqrt(5));
const pos = (x, y, z) => new THREE.Vector3(x, y, z);
const poses = {
  channel: [-6, -2.4],
  cycle: [-3.3, -3.35],
  route: [-3.6, -0.7],
  junction: [-6.55, 0.25],
  binding: [-5.45, 2.55],
  law: [-2.7, 3.2],
  assembly: [-2.7, 3.2], reaction: [-3.8, 5.4], regulation: [-7.7, 3.6],
  kind: [-0.85, -0.85],
  split: [0.55, -3.8],
  "event-split": [3.25, -3.3],
  event: [3.25, -0.9],
  process: [1.25, 0.35],
  "no-part": [5.65, -2.3],
  operator: [0.1, 3.25],
  "design-channel": [3.15, 2.05],
  "design-cycle": [5.5, 0.55],
  "design-junction": [7.05, -0.85],
  "design-release": [6.8, 2.6],
  "design-factor": [4.85, 4.15],
};
const circle = (rx, rz, a) => pos(rx * Math.cos(a), 0, rz * Math.sin(a));
const scaled = (s) => (typeof s === "number" ? [s, s, s] : s);

export class AtlasDrawing {
  constructor() {
    this.root = new THREE.Group();
    this.geometries = {
      island: new THREE.CylinderGeometry(0.94, 1, 1, 6),
      deck: new THREE.BoxGeometry(1, 1, 1),
      dock: new THREE.CylinderGeometry(0.87, 1, 1, 4),
      pin: new THREE.IcosahedronGeometry(1, 1),
      arrow: new THREE.ConeGeometry(1, 1, 8),
      tube: new THREE.CylinderGeometry(1, 1, 1, 8),
      ring: new THREE.TorusGeometry(1, 0.023, 6, 64),
      socket: new THREE.TorusGeometry(1, 0.19, 6, 14),
    };
    this.solid = new THREE.MeshStandardMaterial({ roughness: 0.48, metalness: 0.1 });
    this.ink = new THREE.MeshBasicMaterial({ toneMapped: false });
    this.axis = pos(0, 1, 0);
    this.dummy = new THREE.Object3D();
    this.reset();
  }
  reset() {
    for (const mesh of [...this.root.children]) {
      this.root.remove(mesh);
      mesh.dispose();
    }
    this.batches = new Map();
    this.labels = [];
    this.anchors = new Map();
    this.bounds = new THREE.Box3();
    this.extent = [];
  }
  mark(shape, point, size, colour, id = null, rotation = null, ink = false) {
    const key = shape + (ink ? "/ink" : "");
    if (!this.batches.has(key)) this.batches.set(key, { shape, ink, items: [] });
    const dummy = this.dummy;
    dummy.position.copy(point);
    dummy.scale.set(...scaled(size));
    if (rotation?.isQuaternion) dummy.quaternion.copy(rotation);
    else dummy.rotation.set(...(rotation || [0, 0, 0]));
    dummy.updateMatrix();
    this.batches.get(key).items.push({ matrix: dummy.matrix.clone(), colour, id });
  }
  anchor(id, point, text, priority, kind = "part", lift = 7) {
    if (id) this.anchors.set(id, point);
    if (text) this.labels.push({ id, anchor: point, text, priority, kind, lift });
    this.include(point);
  }
  include(point) {
    this.bounds.expandByPoint(point);
    this.extent.push(point);
  }
  segment(a, b, width, colour, id = null) {
    const direction = b.clone().sub(a),
      length = direction.length();
    if (!length) return;
    const q = new THREE.Quaternion().setFromUnitVectors(this.axis, direction.normalize());
    this.mark("tube", a.clone().lerp(b, 0.5), [width, length, width], colour, id, q, true);
  }
  route(from, to, { rise = 0.8, width = 0.038, colour, id = null, arrow = false, dashed = false, segments = 20 }) {
    const delta = to.clone().sub(from);
    const ctrl = from
      .clone()
      .lerp(to, 0.5)
      .add(pos(0, rise * 2, 0));
    const curve = new THREE.QuadraticBezierCurve3(from, ctrl, to);
    const pts = curve.getPoints(segments);
    for (let i = 0; i < segments; i++) if (!dashed || i % 3 !== 2) this.segment(pts[i], pts[i + 1], width, colour, id);
    if (arrow && delta.lengthSq()) {
      const at = 0.6,
        q = new THREE.Quaternion().setFromUnitVectors(this.axis, curve.getTangent(at).normalize());
      this.mark("arrow", curve.getPoint(at), [0.13, 0.42, 0.13], colour, id, q, true);
    }
    return curve.getPoint(0.5);
  }
  finish() {
    for (const { shape, ink, items } of this.batches.values()) {
      const mesh = new THREE.InstancedMesh(this.geometries[shape], ink ? this.ink : this.solid, items.length);
      items.forEach(({ matrix, colour }, i) => {
        mesh.setMatrixAt(i, matrix);
        mesh.setColorAt(i, new THREE.Color(colour));
      });
      mesh.userData.pick = (hit) => items[hit.instanceId]?.id || null;
      mesh.computeBoundingSphere();
      this.root.add(mesh);
    }
    if (this.bounds.isEmpty()) this.bounds.set(pos(-2, -1, -1), pos(2, 1, 1));
    this.bounds.expandByScalar(0.9);
  }
  dispose() {
    this.reset();
    Object.values(this.geometries).forEach((g) => g.dispose());
    this.solid.dispose();
    this.ink.dispose();
  }
}

export function atlasColours(p) {
  const dark = p.dark;
  return {
    land: dark ? "#536e83" : "#a4bac9",
    side: dark ? "#354e63" : "#7790a4",
    rim: dark ? "#698899" : "#c4d5dc",
    design: dark ? "#52616f" : "#c4ccd0",
    quiet: dark ? "#647789" : "#91a4af",
    faint: dark ? "#334652" : "#c9d4da",
    model: dark ? "#a2c7d4" : "#375c70",
    subject: dark ? "#53d9bd" : "#087b70",
    top: dark ? "#4c9f93" : "#89c8b7",
    direct: dark ? "#a2c7d4" : "#375c70",
    inner: dark ? "#85b0d7" : "#456d9b",
    kind: dark ? "#caabd9" : "#78518c",
    requires: dark ? "#7bdcc7" : "#007d72",
    requiredBy: dark ? "#7bdcc7" : "#007d72",
    reads: dark ? "#82b9ee" : "#346ba0",
    writes: dark ? "#ffb470" : "#a45619",
    ledgers: dark ? "#c4a6eb" : "#7b579f",
    shared: dark ? "#b6b2ff" : "#645ca8",
    provides: dark ? "#85d1ac" : "#377556",
    owns: dark ? "#9caab8" : "#53667a",
    conflicts: dark ? "#ffa4ab" : "#aa4755",
  };
}

export function drawAtlas(d, state, c) {
  const { library, graph, primary, family, filter, selected } = state;
  const activeFilter = Boolean(filter.query || filter.where || filter.box || state.anatomy);
  const belongs = (p) => state.matches(p);
  const centres = new Map(),
    docks = new Map();
  let extra = 0,
    radiusX = 10.0,
    radiusZ = 6.8;
  for (const f of library.families) {
    let at = poses[f.id];
    if (!at) {
      const i = extra++,
        a = i * GOLDEN;
      at = [(9 + Math.sqrt(i) * 2.5) * Math.cos(a), (6 + Math.sqrt(i) * 2.4) * Math.sin(a)];
    }
    const [x, z] = at,
      pieces = library.inFamily.get(f.id),
      count = pieces.length;
    const matching = pieces.filter((p) => (!primary || graph.members.get(primary)?.has(p.id)) && belongs(p));
    const selectedFamily = f.id === family,
      focus = (!family || selectedFamily) && matching.length > 0;
    const design = f.shelf === "design",
      r = 0.83 + Math.min(0.42, Math.sqrt(count) * 0.085),
      height = 0.22 + Math.min(1.25, Math.log2(1 + count) * 0.26);
    const id = familyKey(f.id),
      hit = pos(x, height + 0.1, z);
    centres.set(f.id, hit);
    radiusX = Math.max(radiusX, Math.abs(x) + 2.4);
    radiusZ = Math.max(radiusZ, Math.abs(z) + 2);
    d.mark("island", pos(x, -0.15, z), [r * 1.08, 0.27, r * 1.08], c.side, id);
    d.mark("island", pos(x, height / 2, z), [r, height, r], design ? c.design : focus ? c.top : c.land, id);
    d.mark("island", pos(x, height + 0.025, z), [r * 0.955, 0.055, r * 0.955], design ? c.rim : focus ? c.top : c.rim, id);
    const showName = selectedFamily || !family || focus;
    const tag = design ? "Design · " : "";
    d.anchor(
      id,
      hit,
      showName ? tag + f.short + " · " + count : null,
      selectedFamily ? 960 : (focus ? 500 : 170) + Math.min(count, 40),
      "atlas-family",
    );
    // An island keeps its footprint as the library grows. Its full membership is always in its inspector.
    const matchSet = new Set(matching);
    const marks = selectedFamily || activeFilter ? [...matching, ...pieces.filter((p) => !matchSet.has(p))] : pieces;
    const n = Math.min(36, marks.length);
    for (let j = 0; j < n; j++) {
      const p = marks[j],
        a = j * GOLDEN,
        rad = r * 0.73 * Math.sqrt((j + 0.5) / n);
      const pt = pos(x + rad * Math.cos(a), height + 0.105, z + rad * Math.sin(a)),
        pid = pageId(p.id);
      const lit = activeFilter || selectedFamily ? belongs(p) : focus && matchSet.has(p);
      d.mark(
        design ? "socket" : "pin",
        pt,
        design ? 0.091 : 0.086,
        lit ? c.subject : c.quiet,
        pid,
        design ? [Math.PI / 2, 0, 0] : null,
        true,
      );
      d.anchor(
        pid,
        pt,
        (selectedFamily || activeFilter || state.nearFamily === f.id) && lit ? displayName(p.id) : null,
        pid === selected ? 1000 : activeFilter ? 800 : 440,
        "atlas-piece",
      );
    }
  }
  const ringCapacity = 12;
  library.frames.forEach((m, i) => {
    const level = Math.floor(i / ringCapacity),
      a = (TAU * ((i % ringCapacity) + 0.72)) / ringCapacity;
    const p = circle(radiusX + level * 2.1, radiusZ + level * 1.8, a),
      id = pageId(m.id),
      on = primary === m.id;
    d.mark("dock", p.clone().add(pos(0, 0.05, 0)), [0.66, 0.38, 0.66], on ? c.subject : c.model, id, [0, -a, 0]);
    d.mark("dock", p.clone().add(pos(0, 0.28, 0)), [0.43, 0.14, 0.43], on ? c.top : c.rim, id, [0, -a, 0]);
    if (on) d.mark("ring", p.clone().add(pos(0, -0.075, 0)), 0.83, c.subject, id, [Math.PI / 2, 0, 0], true);
    p.y = 0.4;
    docks.set(m.id, p);
    d.anchor(id, p, modelName(m), on ? 990 : family && graph.bundles.has(bridgeKey(m.id, family)) ? 650 : 260, "atlas-model");
  });
  for (const bundle of graph.bundles.values()) {
    const entries = activeFilter ? bundle.entries.filter((e) => belongs(e.piece)) : bundle.entries;
    if (!entries.length) continue;
    const { id, model, family: f } = bundle,
      on = (!primary || model === primary) && (!family || f === family);
    const hot = id === selected || (on && Boolean(primary || family));
    const colour = hot ? c.subject : on ? c.model : c.faint,
      thickness = hot ? 0.043 : on ? 0.023 : 0.012;
    const mid = d.route(docks.get(model), centres.get(f), {
      colour,
      id,
      width: thickness * (0.65 + Math.sqrt(entries.length) * 0.38),
      rise: hot ? 1.2 + Math.log2(1 + entries.length) * 0.49 : 0.53,
      segments: 18,
    });
    d.anchor(id, mid, hot && (family || id === selected) ? String(entries.length) : null, 610, "atlas-count");
  }
}

export const NEIGHBOURS_PER_LAYER = 8;
export function drawWiring(d, state, c) {
  const phone = state.portrait,
    piece = state.library.piece(state.trace),
    id = pageId(piece.id),
    spread = state.spread * (phone ? 1.55 : 1);
  const source = phone ? pos(0, 0.36, 1.8) : pos(-3.75, 0.36, 0.6);
  const byLayer = state.traceLayers();
  const deck = (y, w, z) => {
    const a = pos(-w, y, -z),
      b = pos(w, y, -z),
      e = pos(-w, y, z),
      f = pos(w, y, z);
    for (const [p, q] of [
      [a, b],
      [b, f],
      [f, e],
      [e, a],
    ])
      d.segment(p, q, 0.022, c.quiet);
    for (const p of [a, b, e, f]) d.include(p);
  };
  const floors = { models: spread, pieces: 0, fields: -spread };
  const titles = { models: "Models", pieces: "Pieces", fields: "Fields & ledgers" };
  for (const [layer, y] of Object.entries(floors)) {
    const half = phone ? 3.4 : 6.3;
    deck(y, half, phone ? 2.3 : 1.95);
    const visible = byLayer[layer];
    d.anchor(null, pos(-half, y, -1.95), titles[layer], 350, "atlas-deck");
    visible.forEach((e, i) => {
      const cols = Math.min(phone ? 3 : 4, visible.length),
        rows = Math.ceil(visible.length / cols);
      const col = i % cols,
        row = Math.floor(i / cols),
        used = Math.min(cols, visible.length - row * cols);
      const x0 = layer === "pieces" && !phone ? 1.45 : 0,
        reach = phone ? 5.4 : layer === "pieces" ? 6.4 : 10.3;
      const x = x0 + (col - (used - 1) / 2) * Math.min(3.45, reach / Math.max(1, used - 1));
      const z = (row - (rows - 1) / 2) * 2.25 + (layer === "pieces" ? -0.55 : 0);
      const pt = pos(x, y + 0.28, z),
        colour = c[e.verb] || c.model,
        half = layer === "models" ? 0.53 : 0.34;
      d.mark(
        layer === "models" ? "dock" : layer === "pieces" ? "island" : "deck",
        pt,
        [half, layer === "fields" ? 0.2 : 0.4, half],
        colour,
        e.id,
      );
      const from = e.incoming ? pt : source,
        to = e.incoming ? source : pt;
      d.route(from, to, {
        id: e.id,
        colour,
        width: 0.036,
        rise: layer === "pieces" ? 0.68 + 0.18 * i : 0.09,
        dashed: ["writes", "inner", "kind", "conflicts"].includes(e.verb),
        arrow: !["ledgers", "conflicts"].includes(e.verb),
      });
      d.anchor(e.id, pt, e.label, layer === "pieces" ? 810 : 710, "atlas-node");
    });
  }
  d.mark("island", source, [0.82, 0.63, 0.82], c.subject, id);
  d.mark("socket", source.clone().add(pos(0, 0.35, 0)), 0.43, c.top, id, [Math.PI / 2, 0, 0], true);
  d.anchor(id, source, displayName(piece.id), 990, "atlas-subject");
}

export function drawComparison(d, state, c) {
  const groups = state.graph.compare(state.primary, state.other);
  const xs = [-5.7, 0, 5.7],
    tones = [c.subject, c.shared, c.writes];
  const names = [modelName(state.library.frame(state.primary)) + " only", "Shared", modelName(state.library.frame(state.other)) + " only"];
  const point = (x, y, z) => (state.portrait ? pos(y, -x, z) : pos(x, y, z));
  groups.forEach((pieces, i) => {
    const x = xs[i],
      radius = i === 1 ? 3.2 : 2.55,
      origin = point(x, 0, 0);
    for (const r of [1, 0.67, 0.33])
      d.mark(
        "ring",
        origin,
        r * radius,
        r === 1 ? tones[i] : c.faint,
        null,
        state.portrait ? [Math.PI / 2, 0, 0] : [0, Math.PI / 2, 0],
        true,
      );
    d.anchor(
      null,
      state.portrait ? point(x, 0, radius + 0.4) : point(x, -radius - 0.27, 0.2),
      names[i] + " · " + pieces.length,
      980,
      "atlas-orbit",
    );
    for (let j = 0; j < 24; j++) d.include(point(x, radius * Math.cos((TAU * j) / 24), radius * Math.sin((TAU * j) / 24)));
    pieces.forEach((p, j) => {
      const a = j * GOLDEN,
        rad = pieces.length === 1 ? 0 : radius * 0.91 * Math.sqrt((j + 0.5) / pieces.length);
      const pt = point(x, rad * Math.cos(a), rad * Math.sin(a)),
        id = pageId(p.id),
        on = state.selected === id;
      d.mark(
        "pin",
        pt,
        on ? 0.23 : Math.max(0.065, Math.min(0.19, 0.69 / Math.sqrt(pieces.length || 1))),
        on ? c.model : tones[i],
        id,
        null,
        true,
      );
      d.anchor(id, pt, on ? displayName(p.id) : null, 995, "atlas-subject");
    });
  });
  for (const x of [xs[0], xs[2]]) for (const sign of [-1, 1]) d.segment(point(x, sign * 2.55, 0), point(0, sign * 3.2, 0), 0.025, c.quiet);
}
