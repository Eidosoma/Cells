// Organs and bodies, drawn as outlines from a species' shape file
// (schema/SPECIES_SHAPES.md). Nothing here belongs to one species: a shape file lists
// parts, each a loft (a body of oval section along a middle line), lines or small discs,
// and a level of a species names which of them are its own and which are its surroundings.
// Outlines are placeholders: nothing at these scales is simulated.
//
// Units: micrometres, in the shape file's own frame (x along the body from its front, y up,
// z across). The lens puts the frame where the species' sheet of cells lies on the body.

import * as THREE from "../three.js";
import { instanced } from "./cell_parts.js";

const UP = new THREE.Vector3(0, 1, 0);
const pairs = (points, out, closed = false) => {
  for (let index = 0; index + 1 < points.length; index++) out.push(points[index], points[index + 1]);
  if (closed && points.length > 2) out.push(points[points.length - 1], points[0]);
};
const lineGeometry = (segments) => new THREE.BufferGeometry().setFromPoints(segments);
const vector = (xyz) => new THREE.Vector3(xyz[0], xyz[1], xyz[2]);

/** A loft's stations: the point on its middle line, its half width and half height, any flap, and the direction across it. */
function stationsOf(part) {
  const stations = part.stations.map((values) => ({
    point: vector(values),
    hw: values[3],
    hh: values[4],
    flap: values.length >= 6 ? values[5] : 0,
    out: values.length === 8 ? new THREE.Vector3(values[6], 0, values[7]) : null,
  }));
  stations.forEach((station, index) => {
    if (station.out) return;
    // Across the part: level, and at right angles to the way its middle line runs here.
    const run = stations[Math.min(stations.length - 1, index + 1)].point.clone().sub(stations[Math.max(0, index - 1)].point).setY(0);
    if (run.lengthSq() === 0) run.set(1, 0, 0);
    run.normalize();
    station.out = new THREE.Vector3(-run.z, 0, run.x);
  });
  return stations;
}

/** A point of a loft's surface at a station: angle 0 on its right edge, a quarter turn on its top. */
function surface(station, angle) {
  const side = Math.cos(angle);
  return station.point
    .clone()
    .addScaledVector(UP, station.hh * Math.sin(angle))
    .addScaledVector(station.out, (station.hw + station.flap * Math.pow(Math.abs(side), 6)) * side);
}

/** The station a fraction of the way along a straight loft, between the two it lies between. */
function between(stations, fraction) {
  const first = stations[0].point.x, last = stations[stations.length - 1].point.x;
  const x = first + (last - first) * fraction;
  let index = 1;
  while (index < stations.length - 1 && (last > first ? stations[index].point.x < x : stations[index].point.x > x)) index++;
  const a = stations[index - 1], b = stations[index];
  const t = b.point.x === a.point.x ? 0 : (x - a.point.x) / (b.point.x - a.point.x);
  const mix = (p, q) => p + (q - p) * t;
  return { point: a.point.clone().lerp(b.point, t), hw: mix(a.hw, b.hw), hh: mix(a.hh, b.hh), flap: mix(a.flap, b.flap), out: a.out.clone().lerp(b.out, t).normalize() };
}

/** Everything a loft can be drawn as: its outline from above, its wire, its fill and its unseen skin. */
function loftShapes(part) {
  const stations = stationsOf(part);
  // The outline seen from above: along one edge and back along the other.
  const rights = stations.map((station) => surface(station, 0));
  const lefts = stations.map((station) => surface(station, Math.PI).setY(station.point.y)).reverse();
  const loop = [];
  for (const point of [...rights, ...lefts]) if (!loop.length || loop[loop.length - 1].distanceToSquared(point) > 1e-12) loop.push(point);
  if (loop.length > 2 && loop[0].distanceToSquared(loop[loop.length - 1]) < 1e-12) loop.pop();
  const edge = [];
  pairs(loop, edge, true);
  // Rings round it and lines along it.
  const wire = [];
  const rings = part.rings;
  if (rings?.step) {
    for (let t = rings.from ?? 0; t < (rings.to ?? 1); t += rings.step) {
      const station = between(stations, t);
      pairs(Array.from({ length: rings.points }, (_, step) => surface(station, (step / rings.points) * Math.PI * 2)), wire, true);
    }
  } else if (rings?.every) {
    stations.forEach((station, index) => {
      if (index % rings.every === (rings.first ?? 0)) pairs(Array.from({ length: rings.points }, (_, step) => surface(station, (step / rings.points) * Math.PI * 2)), wire, true);
    });
  }
  for (const turn of part.lines || []) pairs(stations.map((station) => surface(station, turn * Math.PI)), wire);
  // A skin of triangles over the stations: it is never drawn, only clicked.
  let skin = null;
  if (part.pick) {
    const around = part.pick, corners = [], faces = [];
    for (const station of stations) for (let step = 0; step < around; step++) corners.push(surface(station, (step / around) * Math.PI * 2));
    for (let row = 0; row + 1 < stations.length; row++) {
      for (let step = 0; step < around; step++) {
        const a = row * around + step, b = row * around + ((step + 1) % around);
        faces.push(a, a + around, b, b, a + around, b + around); // wound to face outwards
      }
    }
    skin = new THREE.BufferGeometry().setFromPoints(corners);
    skin.setIndex(faces);
  }
  const level = stations.reduce((sum, station) => sum + station.point.y, 0) / stations.length;
  const fill = () => new THREE.ShapeGeometry(new THREE.Shape(loop.map((point) => new THREE.Vector2(point.x, point.z))), 1).rotateX(Math.PI / 2).translate(0, level, 0);
  return { edge: lineGeometry(edge), wire: wire.length ? lineGeometry(wire) : null, skin, fill, points: [...rights, ...lefts, ...stations.map((station) => surface(station, Math.PI / 2)), ...stations.map((station) => surface(station, -Math.PI / 2))] };
}

/** The points a part reaches, for working out where a level lies when the species does not say. */
function reachOf(part) {
  if (part.kind === "loft") return loftShapes(part).points;
  if (part.kind === "lines") return part.paths.flatMap((path) => path.points.map(vector));
  return part.at.map(vector);
}

/**
 * Where a level lies and how the camera frames it: from the species' level where it says,
 * and from the size of the level's own parts where it does not.
 */
export function outlineFrame(level, shape) {
  const mine = ownParts(level, shape);
  const box = new THREE.Box3().setFromPoints(mine.flatMap(reachOf));
  const size = box.getSize(new THREE.Vector3());
  const centre = level.centre_um ? vector(level.centre_um) : box.getCenter(new THREE.Vector3());
  const long = Math.max(size.x, size.z, 1), wide = Math.max(Math.min(size.x, size.z), size.y, long * 0.3);
  const view = level.view || {};
  return {
    centre,
    size,
    frame: view.frame_um || [long * 1.5, Math.max(long * 0.96, wide * 2.2)],
    toward: view.toward_um ? vector(view.toward_um) : new THREE.Vector3(),
    azimuth: view.azimuth ?? -0.35,
    polar: view.polar ?? 0.95,
    label: level.label_um ? vector(level.label_um) : new THREE.Vector3(0, size.y / 2 + long * 0.03, -size.z / 2 - long * 0.06),
  };
}

const named = (part, names) => names.includes(part.name) || (part.group && names.includes(part.group));
const ownParts = (level, shape) => (level.shape.parts ? shape.parts.filter((part) => named(part, level.shape.parts)) : shape.parts);

/** Where the shape file's frame lies in the world: the species' sheet rests on the body at `tissue_on`. */
export function outlineOrigin(shape) {
  const on = shape.tissue_on;
  return on ? new THREE.Vector3(-on.at_um[0], -on.at_um[1] - (on.clearance_um ?? 0), -on.at_um[2]) : new THREE.Vector3();
}

/**
 * Draws one level of a species as an outline: its own parts bound to the level's entity
 * (so they can be clicked and take its status), and its surroundings faintly, as scenery.
 * `sheet` is the radius of the species' sheet of cells in the world, or 0 where it has none.
 * Returns where the level lies, how to frame it and the notes written beside it.
 */
export function buildOutline(ctx, { level, shape, entity, zone, sheet }) {
  const origin = outlineOrigin(shape);
  const frame = outlineFrame(level, shape);
  const centre = frame.centre.clone().add(origin);
  const place = (object) => {
    object.position.copy(origin);
    return object;
  };
  const own = ctx.scale(entity, centre.clone().add(frame.label));
  const mine = ownParts(level, shape);
  // The level's own parts are the whole file's unless it names some; a part named alone is drawn a little stronger.
  const alone = Boolean(level.shape.parts);
  for (const part of mine) {
    const strength = (alone ? part.alone : undefined) ?? part.strength ?? 0.8;
    if (part.kind === "loft") {
      const shapes = loftShapes(part);
      if (shapes.wire) own.add(place(new THREE.LineSegments(shapes.wire, own.lineMaterial({ opacity: strength }))));
      own.add(place(new THREE.LineSegments(shapes.edge, own.lineMaterial({ opacity: (alone ? part.alone : undefined) ?? part.edge ?? strength }))));
      if (shapes.skin) own.add(place(new THREE.Mesh(shapes.skin, own.proxyMaterial())));
      if (part.fill) ctx.illustrate(place(new THREE.Mesh(shapes.fill(), ctx.neutral({ opacity: part.fill, side: THREE.DoubleSide }))), zone);
    } else if (part.kind === "lines") {
      const segments = [];
      for (const path of part.paths) pairs(path.points.map(vector), segments, Boolean(path.closed));
      own.add(place(new THREE.LineSegments(lineGeometry(segments), own.lineMaterial({ opacity: strength }))));
    } else {
      const disc = new THREE.CircleGeometry(part.radius_um, 16).rotateX(-Math.PI / 2);
      ctx.illustrate(instanced(disc, ctx.neutral({ opacity: strength, colour: "fg", side: THREE.DoubleSide }), part.at.map((at) => ({ position: vector(at).add(origin) }))), zone);
    }
  }
  // Its surroundings: the outline of a part it lies in, faint, so the level is seen where it lies.
  for (const part of shape.parts.filter((item) => named(item, level.shape.context || []) && !mine.includes(item))) {
    if (part.kind !== "loft") continue;
    const shapes = loftShapes(part);
    const faint = part.context || {};
    ctx.illustrate(place(new THREE.LineSegments(shapes.edge, ctx.neutralLine({ opacity: faint.edge ?? 0.4 }))), zone);
    if (faint.fill ?? part.fill) ctx.illustrate(place(new THREE.Mesh(shapes.fill(), ctx.neutral({ opacity: faint.fill ?? 0.06, side: THREE.DoubleSide }))), zone);
  }
  const notes = [];
  // A ring the size of the sheet, where the sheet is: it says how small the simulated tissue is here.
  const mark = level.sheet_mark;
  if (sheet && mark) {
    const band = mark.band ?? 0.02;
    // Beside a body thousands of times its size the sheet could not be seen: its ring is then
    // drawn large enough to find, and the species' note beside it says that it is not to scale.
    const drawn = Math.max(sheet, frame.frame[0] / 240);
    const ring = new THREE.Mesh(new THREE.RingGeometry(drawn * (1 - band), drawn * (1 + band), 48), ctx.neutral({ opacity: 0.9, colour: "fg", side: THREE.DoubleSide }));
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = Math.max(1, drawn * 0.004);
    ctx.illustrate(ring, zone);
    // "roomy" marks a note that is written only where the screen is wide enough for it.
    if (mark.note) notes.push({ text: mark.note, anchor: mark.note_at_um ? vector(mark.note_at_um) : new THREE.Vector3(0, 0, drawn * 1.6), roomy: Boolean(mark.roomy) });
  }
  for (const item of level.notes || []) {
    const note = typeof item === "string" ? { text: item } : item;
    notes.push({ text: note.text, short: note.short, anchor: centre.clone().add(note.at_um ? vector(note.at_um) : new THREE.Vector3(0, 0, frame.size.z / 2 + frame.frame[0] * 0.05)), lift: note.lift, roomy: Boolean(note.roomy) });
  }
  return { notes, centre, frame };
}
