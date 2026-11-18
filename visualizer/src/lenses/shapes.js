// Shapes built from a species' parameters (schema/SPECIES_SHAPES.md). Nothing here
// belongs to one species: a cell is a sphere, a capsule or a prism of any number of
// sides, and everything that stands on its edge or its skin is placed through its outline.
//
// A cell is built in a frame of its own, in which it is always about as wide as the
// reference cell the layout was drawn for. The lens then scales the whole to the size
// the species gives, so one layout serves a 20 µm animal cell and a 0.4 µm minimal cell.

import * as THREE from "../three.js";

const radial = (angle) => new THREE.Vector3(Math.cos(angle), 0, Math.sin(angle));

/** Adds to an outline what follows from its basic functions. Points lie at the height `cut` unless told otherwise. */
function finish(core, cut) {
  const { at, reach, length } = core;
  const lift = (place, offset, y) => new THREE.Vector3(place.x + Math.cos(place.facing) * offset, y, place.z + Math.sin(place.facing) * offset);
  return {
    ...core,
    /** A point this far along the outline; offset is out from it (+) or in (-), y its height. */
    spot: (s, offset = 0, y = cut) => lift(at(s), offset, y),
    /** The point of the outline at this angle. */
    point: (angle, offset = 0, y = cut) => lift(at(reach(angle)), offset, y),
    /** The same, moved a distance along the outline. */
    walk: (angle, distance, offset = 0, y = cut) => lift(at(reach(angle) + distance), offset, y),
    /** Which way the outline faces there, as an angle and as directions out from it and along it. */
    facing: (angle, distance = 0) => at(reach(angle) + distance).facing,
    normal: (angle, distance = 0) => radial(at(reach(angle) + distance).facing),
    tangent: (angle, distance = 0) => radial(at(reach(angle) + distance).facing + Math.PI / 2),
    /** A closed loop of points round the outline. */
    ring: (offset = 0, y = cut, arcSteps = 12, flatSteps = 1) => core.samples(arcSteps, flatSteps).map((place) => lift(place, offset, y)),
    /** How far apart two places are along the outline, the short way round. */
    apart: (a, b) => {
      const gap = (((a - b) % length) + length) % length;
      return Math.min(gap, length - gap);
    },
  };
}

/**
 * A flat-sided outline: `sides` flat sides joined by rounded corners, one side facing angle 0.
 * A place on it is named by its angle round the centre, or by how far along the outline it is.
 */
export function polygonOutline(sides, apothem, round, cut) {
  const A = Math.PI / (sides / 2), H = Math.PI / sides; // the angle a side takes, and half of it
  const half = (apothem - round) * Math.tan(H); // half the length of a flat side
  const side = 2 * half + round * A; // a flat side and the corner after it
  const length = sides * side;
  const hub = (apothem - round) / Math.cos(H); // from the centre to the middle of a corner's curve

  /** Where the outline is this far along it, counted from the middle of the side that faces angle 0. */
  const at = (s) => {
    const whole = (((s + half) % length) + length) % length;
    const k = Math.floor(whole / side), u = whole - k * side, face = k * A;
    if (u <= 2 * half) {
      const w = u - half;
      return { x: apothem * Math.cos(face) - w * Math.sin(face), z: apothem * Math.sin(face) + w * Math.cos(face), facing: face };
    }
    const facing = face + (u - 2 * half) / round, corner = face + H;
    return { x: hub * Math.cos(corner) + round * Math.cos(facing), z: hub * Math.sin(corner) + round * Math.sin(facing), facing };
  };
  /** How far from the centre the outline is at this angle; offset moves the whole outline out (+) or in (-). */
  const radius = (angle, offset = 0) => {
    const phi = Math.abs(angle - Math.round(angle / A) * A); // the angle off the middle of the nearest side
    if ((apothem + offset) * Math.tan(phi) <= half) return (apothem + offset) / Math.cos(phi);
    const gamma = H - phi; // the angle off the middle of the corner
    return hub * Math.cos(gamma) + Math.sqrt((round + offset) ** 2 - (hub * Math.sin(gamma)) ** 2);
  };
  /** How far along the outline the point seen from the centre at this angle is. */
  const reach = (angle) => {
    const k = Math.round(angle / A), phi = angle - k * A;
    const w = apothem * Math.tan(phi);
    if (Math.abs(w) <= half) return k * side + w;
    const sign = phi < 0 ? -1 : 1, r = radius(angle);
    const facing = Math.atan2(r * Math.sin(phi) - hub * Math.sin(sign * H), r * Math.cos(phi) - hub * Math.cos(sign * H));
    return k * side + sign * half + round * facing;
  };
  /** The places a closed loop round the outline passes through: the ends of each flat side, and steps round each corner. */
  const samples = (arcSteps = 12, flatSteps = 1) => {
    const places = [];
    for (let k = 0; k < sides; k++) {
      for (let step = 0; step < flatSteps; step++) places.push(at(k * side - half + (2 * half * step) / flatSteps));
      for (let step = 0; step < arcSteps; step++) places.push(at(k * side + half + (round * A * step) / arcSteps));
    }
    return places;
  };
  /** How far inside the outline a point is (negative outside it). */
  const depth = (x, z) => {
    const face = Math.round(Math.atan2(z, x) / A) * A;
    const u = x * Math.cos(face) + z * Math.sin(face) - (apothem - round), w = Math.abs(z * Math.cos(face) - x * Math.sin(face)) - half;
    return round - (u > 0 && w > 0 ? Math.hypot(u, w) : u);
  };
  return finish(
    {
      apothem, length, at, radius, reach, samples, depth,
      widest: radius(H),
      /** The angles of its corners. */
      corners: Array.from({ length: sides }, (_, corner) => H + corner * A),
      /** The same outline drawn this far inside itself. */
      inset: (d) => polygonOutline(sides, apothem - d, Math.max(round - d, 0.02), cut),
    },
    cut
  );
}

/**
 * A round-ended outline: two round ends joined by two flat sides, the long way lying
 * along x. The end that faces angle 0 has radius r and its centre at x = a; the other has
 * radius `tip` (r where none is given) and its centre at x = -a, so a smaller tip makes a
 * cell that narrows to one end. With a = 0 it is a circle.
 */
export function stadiumOutline(a, r, cut, tip = r) {
  const h = 2 * a; // from the middle of one end to the middle of the other
  const slope = h > 0 ? Math.min(0.999, (r - tip) / h) : 0, lean = Math.sqrt(1 - slope * slope); // how the sides lean in toward the tip
  const tilt = Math.asin(slope), f1 = Math.PI / 2 + tilt; // the way the upper side faces
  const side = h * lean; // the length of a flat side
  const big = r * f1, small = tip * (Math.PI - 2 * tilt); // half the arc of the wide end; the arc of the tip
  const length = 2 * big + 2 * side + small;
  /** Where the outline is this far along it, counted from the middle of the end that faces angle 0; `rho` is the cell's radius there. */
  const at = (s) => {
    const whole = ((s % length) + length) % length;
    if (whole <= big) return { x: a + r * Math.cos(whole / r), z: r * Math.sin(whole / r), facing: whole / r, rho: r };
    if (whole <= big + side) {
      const w = whole - big;
      return { x: a - r * slope - lean * w, z: r * lean - slope * w, facing: f1, rho: r - (r - tip) * (side ? w / side : 0) };
    }
    if (whole <= big + side + small) {
      const facing = f1 + (whole - big - side) / tip;
      return { x: -a + tip * Math.cos(facing), z: tip * Math.sin(facing), facing, rho: tip };
    }
    if (whole <= big + 2 * side + small) {
      const w = whole - big - side - small;
      return { x: -a - tip * slope + lean * w, z: -tip * lean - slope * w, facing: 2 * Math.PI - f1, rho: tip + (r - tip) * (side ? w / side : 0) };
    }
    const facing = 2 * Math.PI - f1 + (whole - big - 2 * side - small) / r;
    return { x: a + r * Math.cos(facing), z: r * Math.sin(facing), facing, rho: r };
  };
  /** How far outside the shape a point is (negative inside): x along it, and its distance from the long axis. */
  const outside = (x, lateral) => {
    const along = a - x; // from the middle of the wide end toward the tip
    if (h === 0) return Math.hypot(lateral, along) - r;
    const k = lean * along - slope * lateral;
    if (k < 0) return Math.hypot(lateral, along) - r;
    if (k > lean * h) return Math.hypot(lateral, along - h) - tip;
    return lean * lateral + slope * along - r;
  };
  /**
   * How far from the centre the shape reaches at this angle; offset moves its edge out (+) or
   * in (-). At a height y above the middle it is the girth of the round body there.
   */
  const radius = (angle, offset = 0, y = 0) => {
    const c = Math.cos(angle), s = Math.sin(angle);
    if (h === 0) return Math.sqrt(Math.max(0, (r + offset) ** 2 - y * y));
    // The shape is convex: between the centre and a point well outside, the edge is crossed once.
    let near = 0, far = a + r + Math.max(0, offset) + 1;
    for (let step = 0; step < 50; step++) {
      const middle = (near + far) / 2;
      if (outside(middle * c, Math.hypot(middle * s, y)) > offset) far = middle;
      else near = middle;
    }
    return (near + far) / 2;
  };
  const reach = (angle) => {
    const turn = ((angle % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
    const rho = radius(turn), x = rho * Math.cos(turn), z = rho * Math.sin(turn);
    const k = lean * (a - x) - slope * Math.abs(z);
    if (h === 0 || k <= 0) return r * Math.atan2(z, x - a);
    if (k >= lean * h) {
      const facing = Math.atan2(z, x + a);
      return big + side + ((facing < 0 ? facing + 2 * Math.PI : facing) - f1) * tip;
    }
    // On a flat side: how far along it from where it leaves the round end before it.
    return z > 0 ? big + (-(x - (a - r * slope)) * lean - (z - r * lean) * slope) : big + side + small + ((x - (-a - tip * slope)) * lean - (z + tip * lean) * slope);
  };
  const samples = (arcSteps = 12, flatSteps = 1) => {
    const places = [], ends = arcSteps * 3;
    const wide = Math.max(4, Math.round((ends * 2 * f1) / Math.PI)), narrow = Math.max(3, Math.round((ends * (Math.PI - 2 * tilt)) / Math.PI));
    for (let step = 0; step < wide; step++) places.push(at(-big + (2 * big * step) / wide));
    if (a > 0) for (let step = 0; step < flatSteps; step++) places.push(at(big + (side * step) / flatSteps));
    for (let step = 0; step < narrow; step++) places.push(at(big + side + (small * step) / narrow));
    if (a > 0) for (let step = 0; step < flatSteps; step++) places.push(at(big + side + small + (side * step) / flatSteps));
    return places;
  };
  return finish(
    {
      apothem: r, length, at, radius, reach, samples,
      /** How far inside the outline a point is (negative outside it). */
      depth: (x, z) => -outside(x, Math.abs(z)),
      /** How far inside the round body a point is: the outline turned about its long axis. */
      depth3: (point) => -outside(point.x, Math.hypot(point.y, point.z)),
      widest: a + r,
      corners: Array.from({ length: 6 }, (_, corner) => Math.PI / 6 + (corner * Math.PI) / 3),
      inset: (d) => stadiumOutline(a, Math.max(r - d, 0.001), cut, Math.max(tip - d, 0.001)),
    },
    cut
  );
}

/**
 * A closed surface: the outline drawn up from the base to the top, with the edges of both
 * rounded by `bevel`. With the bevel as large as half the height the outline is the
 * widest girth and the surface is fully round: a circle gives a sphere, a round-ended
 * outline a capsule, and one that narrows to a tip a body that is round all along and
 * thinner at that end. Its normals are exact on flat sides, so those are lit as flat.
 */
export function solidGeometry(outline, top, base, bevel) {
  const places = outline.samples(12, 1), count = places.length;
  // From the top down to the base: how far in from the outline, how high, and how the surface tilts.
  const profile = [];
  const steps = bevel > 3 ? 18 : 6;
  for (let step = 0; step <= steps; step++) {
    const t = (step / steps) * (Math.PI / 2);
    profile.push([bevel * (1 - Math.sin(t)), top - bevel * (1 - Math.cos(t)), Math.PI / 2 - t]);
  }
  for (let step = steps; step >= 0; step--) {
    const t = (step / steps) * (Math.PI / 2);
    profile.push([bevel * (1 - Math.sin(t)), base + bevel * (1 - Math.cos(t)), t - Math.PI / 2]);
  }
  const position = [], normal = [];
  const middle = (top + base) / 2, flat = top - middle - bevel; // how far the upright part reaches above the middle
  for (const [inset, y, tilt] of profile) {
    const above = y - middle, rounded = Math.sign(above) * (Math.abs(above) - flat); // the part of the height that the rounded edge takes
    for (const place of places) {
      // A round body is as high as it is wide at each place: `rho` is its radius there.
      const k = place.rho === undefined ? 1 : place.rho / bevel;
      position.push(place.x - Math.cos(place.facing) * inset * k, k === 1 ? y : middle + Math.sign(above) * flat + rounded * k, place.z - Math.sin(place.facing) * inset * k);
      normal.push(Math.cos(tilt) * Math.cos(place.facing), Math.sin(tilt), Math.cos(tilt) * Math.sin(place.facing));
    }
  }
  const index = [];
  for (let row = 0; row + 1 < profile.length; row++) {
    for (let q = 0; q < count; q++) {
      const a = row * count + q, b = row * count + ((q + 1) % count), c = a + count, d = b + count;
      index.push(a, c, b, b, c, d);
    }
  }
  // The top and the base close it. A fully round body has neither: its two halves meet along its middle line.
  if (bevel < top - middle - 1e-9) {
    const face = position.length / 3;
    position.push(0, top, 0, 0, base, 0);
    normal.push(0, 1, 0, 0, -1, 0);
    const last = (profile.length - 1) * count;
    for (let q = 0; q < count; q++) index.push(face, q, (q + 1) % count, face + 1, last + q, last + ((q + 1) % count));
  }
  // Every face is wound so that its front looks out of the cell.
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3(), out = new THREE.Vector3();
  const read = (target, from, which) => target.set(from[which * 3], from[which * 3 + 1], from[which * 3 + 2]);
  for (let start = 0; start < index.length; start += 3) {
    read(a, position, index[start]);
    const across = read(b, position, index[start + 1]).sub(a).cross(read(c, position, index[start + 2]).sub(a));
    read(out, normal, index[start]).add(read(a, normal, index[start + 1])).add(read(a, normal, index[start + 2]));
    if (across.dot(out) < 0) [index[start + 1], index[start + 2]] = [index[start + 2], index[start + 1]];
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(position, 3));
  geometry.setAttribute("normal", new THREE.Float32BufferAttribute(normal, 3));
  geometry.setIndex(index);
  return geometry;
}

// The reference cell the layout is drawn for: six-sided, this far from its centre to a
// corner, so this far from one cell's centre to the next in a packed layer.
export const REF = { radius: 10.6, cut: 1.6, pitch: 10.6 * 2 * Math.cos(Math.PI / 6) };
const LATTICE = REF.radius * Math.sqrt(3);

/** The species' cell as a width in micrometres: between opposite sides, or across its short way. */
export function cellAcross(shape) {
  if (shape.kind === "prism" && shape.radius_um) return shape.radius_um * 2 * Math.cos(Math.PI / shape.sides);
  return shape.across_um;
}

/**
 * The frame a cell is built in. `gap` is the room left between the cell and a neighbour
 * (none for a cell that has no neighbours). Returns the cell's outline at its widest
 * and at the cut, its top, base and how round its edges are, all in reference units,
 * and `u`, the micrometres one reference unit stands for.
 */
export function cellFrame(shape, gap = 0) {
  const cut = REF.cut;
  const u = cellAcross(shape) / REF.pitch;
  const across = LATTICE - gap; // the cell's width in the frame
  if (shape.kind === "prism") {
    const top = shape.height_um / u / 2, base = -top;
    const corner = shape.corner_um !== undefined ? shape.corner_um / u : across * 0.13;
    const bevel = shape.edge_um !== undefined ? shape.edge_um / u : top * 0.2;
    const equator = polygonOutline(shape.sides, across / 2, corner, cut);
    /** How far in from its widest girth the surface is at a height. */
    const insetAt = (y) => {
      const away = y > top - bevel ? (y - (top - bevel)) / bevel : y < base + bevel ? (base + bevel - y) / bevel : 0;
      return away <= 0 ? 0 : bevel * (1 - Math.sqrt(Math.max(0, 1 - Math.min(1, away) ** 2)));
    };
    const drop = insetAt(cut);
    return {
      kind: shape.kind, u, cut, top, base, bevel, corner, equator, round: false,
      long: 2 * equator.widest, // the cell's length along its long way
      middle: 0, // where its middle lies along that way, from the frame's centre
      /** The cell's outline where the cut passes through it. */
      outline: drop > 1e-9 ? equator.inset(drop) : equator,
      /** A point of the cell's surface at this angle and height; off moves it out (+) or in (-). */
      skin: (angle, y, off = 0) => equator.point(angle, off - insetAt(y), y),
      solid: () => solidGeometry(equator, top, base, bevel),
      /** How far inside the cell a point is, from its sides, its base and its top. */
      inside: (point) => {
        const side = equator.depth(point.x, point.z), floor = point.y - base, roof = top - point.y;
        const low = side < bevel && floor < bevel ? bevel - Math.hypot(bevel - side, bevel - floor) : Math.min(side, floor);
        const high = side < bevel && roof < bevel ? bevel - Math.hypot(bevel - side, bevel - roof) : Math.min(side, roof);
        return Math.min(low, high);
      },
    };
  }
  // A round cell: a sphere, or a capsule lying on its side, which may narrow to a tip at one end.
  const r = across / 2;
  const tip = shape.kind === "capsule" && shape.tip_um !== undefined ? r * Math.min(1, shape.tip_um / shape.across_um) : r;
  const a = shape.kind === "capsule" ? Math.max(0, (shape.length_um / u - (LATTICE / 2) * (1 + tip / r)) / 2) : 0;
  const equator = stadiumOutline(a, r, cut, tip);
  // Where the cut passes through it the body is a little narrower than at its middle, at both ends.
  const narrowed = (radius) => Math.sqrt(Math.max(radius * radius - cut * cut, (radius * 0.12) ** 2));
  return {
    kind: shape.kind, u, cut, top: r, base: -r, bevel: r, corner: 0, equator, round: true,
    long: 2 * a + r + tip,
    middle: (r - tip) / 2,
    outline: stadiumOutline(a, narrowed(r), cut, narrowed(tip)),
    skin: (angle, y, off = 0) => {
      const reach = equator.radius(angle, off, y);
      return new THREE.Vector3(reach * Math.cos(angle), y, reach * Math.sin(angle));
    },
    solid: () => solidGeometry(equator, r, -r, r),
    inside: (point) => equator.depth3(point),
  };
}

/**
 * How the cells of a layer are packed, from the number of sides of the species' cell: a
 * four-sided cell stands in squares, every other cell in sixes, as a packed sheet does.
 * All that the picture of a layer needs follows from this one answer: where the neighbours
 * stand, where the corners of a cell's place are, which cells a sheet of so many rings
 * holds, where each stands, and which are joined. Lengths are in the cell's frame.
 */
export function packing(sides) {
  const four = sides === 4;
  const count = four ? 4 : 6, turn = (2 * Math.PI) / count;
  return {
    sides: count,
    turn,
    /** From the middle of a cell's place to its corners. */
    radius: four ? (LATTICE / 2) * Math.SQRT2 : REF.radius,
    /** From one cell's middle to the next. */
    pitch: LATTICE,
    /** The neighbours that share a side with a cell, as turns from the side that faces angle 0. */
    turns: Array.from({ length: count }, (_, step) => step * turn),
    /** The angle of a corner of a cell's place: half a step past each side. */
    corner: (index) => turn / 2 + index * turn,
    /** The corner nearest an angle. */
    cornerNear: (angle) => turn / 2 + Math.round((angle - turn / 2) / turn) * turn,
    /** The cells of a sheet: so many rings round the middle one, each as its steps along the sheet's two ways. */
    cells(rings) {
      const cells = [];
      for (let q = -rings; q <= rings; q++) {
        if (four) for (let r = -rings; r <= rings; r++) cells.push({ q, r });
        else for (let r = Math.max(-rings, -q - rings); r <= Math.min(rings, -q + rings); r++) cells.push({ q, r });
      }
      return cells;
    },
    /** Where a cell stands. */
    centre: ({ q, r }) => (four ? new THREE.Vector3(LATTICE * q, 0, LATTICE * r) : new THREE.Vector3(REF.radius * Math.sqrt(3) * (q + r / 2), 0, REF.radius * 1.5 * r)),
    /** Which ring round the middle cell a cell stands in. */
    ring: ({ q, r }) => (four ? Math.max(Math.abs(q), Math.abs(r)) : Math.max(Math.abs(q), Math.abs(r), Math.abs(q + r))),
    /** The steps from a cell to the neighbours it is joined to, each pair once. */
    links: four ? [[1, 0], [0, 1]] : [[1, 0], [0, 1], [-1, 1]],
  };
}
