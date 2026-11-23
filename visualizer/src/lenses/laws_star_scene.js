import * as THREE from "../three.js";
import { engineId, pageId } from "./laws_data.js";
import { displayName, familyKey } from "./laws_connections.js";

const TAU = Math.PI * 2, GOLDEN = Math.PI * (3 - Math.sqrt(5));
const v = (x, y, z) => new THREE.Vector3(x, y, z);
// These are display coordinates. A shelf and its families keep their addresses as pieces are added.
const berths = {
  channel: [-10.2, .3, -5.8], cycle: [-6.3, 1.2, -7.4], route: [-3.5, .55, -4.4],
  junction: [-8.8, .45, -1.6], binding: [-4.7, .05, -.25], law: [-9.3, -.1, 4.55],
  kind: [-.55, 1.25, -1.75], split: [2.05, 1.35, -6.6], "event-split": [5.9, 1.65, -7.6],
  event: [6.1, .72, -2.9], process: [2.7, .22, -.25], "no-part": [10.3, .6, -4.6],
  operator: [-4.15, -.35, 5.75], "design-channel": [1.45, -.55, 4.3],
  "design-cycle": [5.55, -.4, 3.3], "design-junction": [9.65, -.2, 2.25],
  "design-release": [4.25, -1.1, 8.25], "design-factor": [8.7, -.75, 6.9],
};
const shelfNames = { laws: "Inner-model laws", "family-laws": "Model-family laws", kinds: "Kinds",
  operators: "Composite operators", "family-operators": "Model-family operators", design: "Design notes" };
const tones = { laws: "#76dff1", "family-laws": "#b3a1fc", kinds: "#8dbcf7", operators: "#75e6c4",
  "family-operators": "#c1a6ff", design: "#e9bc87" };
export const linkTone = {
  requires: "#62eee4", requiredBy: "#62eee4", reads: "#83c4ff", writes: "#ffc189",
  direct: "#a3ddec", inner: "#bdabff", kind: "#cba5f6", ledgers: "#c9a8ef",
  provides: "#91eab6", owns: "#a8c5df", conflicts: "#ff9ca9",
};
export const starVerb = { requires: "Requires", reads: "Reads", writes: "Writes", provides: "Provides",
  owns: "Owns", ledgers: "Lists ledger", requiredBy: "Required by", conflicts: "Cannot combine with",
  direct: "Declared by", inner: "Via inner model", kind: "Via host kind" };

// An ID, rather than its row number, locates a piece. Inserting an alphabetically earlier
// declaration in a later catalogue must not move every star that follows it.
function coordinate(id, axis) {
  let seed = 2166136261 ^ axis;
  for (let i=0;i<id.length;i++) seed = Math.imul(seed ^ id.charCodeAt(i),16777619);
  seed = Math.imul(seed ^ (seed >>> 16), 0x85ebca6b);
  return ((seed ^ (seed >>> 13)) >>> 0) / 4294967296;
}

export function starLayout(library) {
  const families = new Map(), stars = new Map(), shelves = new Map();
  let extra = 0;
  for (const family of library.families) {
    const a = extra * GOLDEN, r = 15 + Math.sqrt(extra) * 3.4;
    const center = berths[family.id] ? v(...berths[family.id]) : v(r * Math.cos(a), 0, r * Math.sin(a));
    if (!berths[family.id]) extra++;
    families.set(family.id, center);
    if (!shelves.has(family.shelf)) shelves.set(family.shelf, []);
    shelves.get(family.shelf).push(center);
    library.inFamily.get(family.id).forEach(p => {
      const radius = .15 + 1.32 * Math.sqrt(coordinate(p.id,0));
      const angle = TAU * coordinate(p.id,1);
      const height = .32 + (.32 + 1.25 * coordinate(p.id,2)) * Math.sqrt(1 - (radius/1.7)**2);
      stars.set(p.id, center.clone().add(v(radius * Math.cos(angle), height, radius * Math.sin(angle))));
    });
  }
  return { families, stars, shelves };
}

export function routeCurve(start, end) {
  const control = start.clone().lerp(end, .5);
  control.y += .45 + Math.min(2.8, start.distanceTo(end) * .23);
  return new THREE.QuadraticBezierCurve3(start, control, end);
}

function drawRoute(d, light, curve, colour, id, past, symmetric = false) {
  const points = curve.getPoints(28);
  for (let i = 1; i < points.length; i++) d.segment(points[i-1], points[i], past ? .026 : .023, colour, id);
  if (!symmetric) {
    const direction = new THREE.Quaternion().setFromUnitVectors(d.axis, curve.getTangent(.73).normalize());
    d.mark("arrow", curve.getPoint(.73), [.09, .25, .09], colour, id, direction, true);
  }
  light.star(curve.getPoint(.73), colour, past ? .27 : .43);
}

function drawCompass(light) {
  const center = v(0, -1.45, 0);
  for (const r of [5, 10, 15, 19]) light.ring(center, r, "#182f43");
  for (let i = 0; i < 72; i++) {
    const a = i * TAU / 72, x = Math.cos(a), z = Math.sin(a);
    const inner = i % 6 === 0 ? 18.42 : 18.84;
    light.line(v(inner*x, center.y, inner*z), v(19*x, center.y, 19*z), "#2b475a");
  }
}

function drawPod(d, light, at, key, rim, lit, active) {
  const base = at.clone().add(v(0,-.16,0)), dial = at.clone().add(v(0,.09,0));
  d.mark("island", base, [1.63,.29,1.63], active ? "#304b5b" : "#203546", key);
  d.mark("island", at, [1.54,.11,1.54], "#101f31", key);
  // Instrument rings mark the extent of a family. Only the separately drawn routes carry a verb.
  light.ring(dial,1.64,lit || active ? "#597c89" : "#263d50");
  light.ring(dial,1.79,rim,.12,2.65); light.ring(dial,1.79,rim,3.1,5.2);
  light.ring(dial,.85,lit || active ? "#345367" : "#233646");
  light.ring(dial,.32,lit || active ? "#46717b" : "#263b4a");
  const cap = at.clone().add(v(0,.26,0)), ribs = lit || active ? "#355267" : "#203344";
  for (const a of [.55,2.65]) {
    let prev=cap.clone().add(v(1.62*Math.cos(a),0,1.62*Math.sin(a)));
    for (let i=1;i<=20;i++) {
      const t = Math.PI*i/20, r = 1.62*Math.cos(t);
      const pt = cap.clone().add(v(r*Math.cos(a),1.61*Math.sin(t),r*Math.sin(a)));
      light.line(prev,pt,ribs);prev=pt;
    }
  }
  for (let i=0;i<18;i++) {
    const angle=i*TAU/18, x=Math.cos(angle), z=Math.sin(angle);
    const major=i%3===0;
    light.line(dial.clone().add(v((major?1.48:1.6)*x,0,(major?1.48:1.6)*z)),
      dial.clone().add(v(1.73*x,0,1.73*z)),major ? rim : ribs);
  }
  // Include the actual silhouette when fitting the camera, even for a family's single piece.
  for (const offset of [[-1.8,0,0],[1.8,0,0],[0,0,-1.8],[0,0,1.8],[0,1.9,0]]) d.include(at.clone().add(v(...offset)));
  return dial;
}

function drawFamilies(d, view) {
  const { library, map, light, graph, primary, family, nearFamily } = view;
  const tracing = view.mode === "wiring", comparing = view.mode === "compare";
  const members = graph.members.get(primary);
  const other = comparing ? graph.members.get(view.other) : null;
  const activeFamily = tracing ? library.piece(view.trace).family : family || nearFamily;
  const filtering = Boolean(view.filter.query || view.filter.where || view.filter.box || view.anatomy);
  for (const f of library.families) {
    const at = map.families.get(f.id), key = familyKey(f.id), pieces = library.inFamily.get(f.id);
    const tone = tones[f.shelf] || tones.kinds, active = activeFamily === f.id;
    const matching = pieces.filter(p => view.matches(p) && (!members || members.has(p.id)));
    const lit = !tracing && (!family || active) && matching.length > 0;
    const rim = tracing && !active ? "#22384a" : lit || active ? tone : "#3a5366";
    const dial = drawPod(d,light,at,tracing ? null : key,rim,lit,active);
    const title = (f.shelf === "design" ? "Design · " : "") + f.short;
    const counter = members && !tracing && !comparing ? matching.length + "/" + pieces.length : String(pieces.length);
    d.anchor(key, at.clone().add(v(0,-.35,1.32)), !tracing || active ? title + "  ·  " + counter : null,
      active ? 925 : lit ? 570 : 365, lit || active ? "star-family" : "star-quiet");
    let named = 0;
    for (const p of pieces) {
      const pt = map.stars.get(p.id), id = pageId(p.id), belongs = !members || members.has(p.id);
      const matches = view.matches(p);
      let colour = lit && belongs && matches ? (primary ? "#8ef9f0" : tone) : "#466075";
      if (comparing) colour = members?.has(p.id) ? (other?.has(p.id) ? "#c4adff" : "#70e3e0") : other?.has(p.id) ? "#ffc189" : "#344b60";
      if (tracing) colour = active ? "#4b6475" : "#293e52";
      const hot = !tracing && matches && belongs && (!family || active);
      const pick = tracing ? null : id;
      if (p.where === "design") d.mark("socket", pt, hot ? .105 : .09, colour, pick, [Math.PI/2,0,0], true);
      else d.mark("pin", pt, hot ? .078 : .055, colour, pick, null, true);
      if (p.where !== "design") light.star(pt, colour, hot ? .9 : .44, hot && primary ? THREE.MathUtils.clamp((pt.x+14)/28,0,1) : -10);
      const label = !tracing && (active || filtering) && matches && named < 14;
      if (label) named++;
      d.anchor(id, pt, label ? displayName(p.id) : null, filtering ? 815 : 710, "star-piece");
      if (active && view.mode === "atlas" && matches && belongs) {
        const membership = primary && p.declared_by.find(entry => entry.frame === primary);
        if (membership) light.line(dial, pt, {direct:"#54888e", inner:"#74618e", kind:"#705a83"}[membership.how]);
        else if (pieces.length <= 30 || label) light.line(dial, pt, "#345666");
      }
    }
  }
  if (!tracing && !family && !nearFamily) {
    for (const [id, centres] of map.shelves) {
      if (centres.length < 2) continue;
      const box = new THREE.Box3().setFromPoints(centres), at = box.getCenter(v(0,0,0));
      at.z = box.min.z - 1.85; at.y += .45;
      d.anchor(null, at, shelfNames[id] || id, 780, "star-sector");
    }
  }
}

export function starConnection(map, sourceId, edge, index, count) {
  const source = map.stars.get(sourceId), peer = map.stars.get(engineId(edge.id));
  if (peer) return routeCurve(source, peer);
  // Fields and model references are local terminals of this declaration.
  const lane = Math.floor(index/4), row = index%4, rows = Math.min(4, count - lane*4);
  return routeCurve(source,source.clone().add(v(3.65 + 1.7*lane, 1.1 + .42*(rows-1-row) + 1.65*lane, (row-(rows-1)/2)*2 + .65*lane)));
}

export function drawStars(d, view) {
  const { light } = view;
  light.reset(); drawCompass(light); drawFamilies(d, view);
  view.links = new Map();
  if (view.mode === "wiring") {
    const subject = view.library.piece(view.trace), origin = view.map.stars.get(subject.id);
    const here = view.terminal ? view.path.at(-1).curve.v2 : origin;
    const focus = new THREE.Box3().setFromCenterAndSize(here, v(3.4,2.6,3.1));
    for (const step of view.path) {
      drawRoute(d, light, step.curve, "#e8b97a", null, true, step.edge.verb === "conflicts");
      d.mark("pin", step.curve.v0, .145, "#e9c693", pageId(step.from), null, true);
      light.star(step.curve.v0, "#eac38b", .9);
    }
    d.mark("pin", origin, .195, "#e2ffff", pageId(subject.id), null, true);
    light.star(origin, "#7deee4", 1.7);
    d.anchor(pageId(subject.id), origin, displayName(subject.id), 985, "star-subject");
    const visible = view.terminal ? [] : Object.values(view.traceLayers()).flat();
    visible.forEach((e,i) => {
      const curve = starConnection(view.map, subject.id, e, i, visible.length), end = curve.v2;
      const colour = linkTone[e.verb] || "#b3dce8";
      if (e.id) view.links.set(e.id, {edge:e, curve});
      drawRoute(d, light, curve, colour, e.id, false, e.verb === "conflicts");
      d.mark(e.layer === "fields" ? "dock" : "pin", end, e.layer === "fields" ? [.15,.19,.15] : .14, colour, e.id, null, true);
      light.star(end, colour, 1.0);
      d.anchor(e.id, end, e.label, 930, "star-target", e.layer === "fields" && i % 2 ? 26 : 7);
      if (visible.length<=4 || i===0) d.anchor(null,curve.getPoint(.38+.08*(i%3)),starVerb[e.verb]?.toLowerCase(),900,"star-verb");
      focus.expandByPoint(end); focus.expandByPoint(curve.getPoint(.5));
    });
    if (view.terminal) {
      const e = view.path.at(-1).edge;
      d.mark("dock", here, [.24,.34,.24], "#fee2ab", e.id, null, true);
      light.star(here, "#ffd094", 1.5);
      d.anchor(e.id, here, e.label, 998, "star-target");
    }
    view.traceBox = focus.expandByScalar(.65);
  }
  light.finish();
}
