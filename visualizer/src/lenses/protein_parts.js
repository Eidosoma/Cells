// Shapes for the protein atlas. Every shape is schematic and drawn from counts the
// inventory states: how many subunits, how many repeats, which auxiliary partners.
// Nothing here is a measured structure, and nothing is to scale.
//
// A unit's form (from the scene) says what to draw:
//   ring      n subunits around one pore                      (Kv, Kir, HCN)
//   chain     one chain folded into n repeats around a pore   (NaV, CaV)
//   junction  two rings of n, one in each cell's membrane      (connexin channels)
//   cage      trimers on the corners of a dodecahedron         (the engineered cage)
// and, for a generic law, a plain stand-in with no subunits:
//   pore, pump, carrier, patch, junction
//
// The builders call add(geometry, tone, position, options) and return how far the
// shape reaches (top, bottom, radius), so the lens can place rings and labels.

import * as THREE from "../three.js";

const TAU = Math.PI * 2;
export const SHEET = 4.2; // thickness of a membrane, in the lens's units (about a nanometre)
const HALF = SHEET / 2;
export const CLEFT = 3.4; // between the two membranes of a junction
export const UPPER = SHEET + CLEFT; // height of the neighbouring cell's membrane above this one
const LIFT = 0.5; // a channel stands a little higher outside the cell than inside

let cache = null;
/** Geometries shared by every unit. */
function shapes() {
  if (cache) return cache;
  const lathe = (points, segments = 40) => new THREE.LatheGeometry(points.map(([r, y]) => new THREE.Vector2(r, y)), segments);
  cache = {
    lobe: new THREE.CapsuleGeometry(1.9, 4.6, 6, 22).translate(0, LIFT, 0), // one subunit across the membrane
    repeat: new THREE.CapsuleGeometry(1.75, 4.9, 6, 22).translate(0, LIFT, 0), // one repeat of a long chain
    core: new THREE.CapsuleGeometry(1.45, 4.4, 6, 18).translate(0, LIFT, 0),
    connexin: new THREE.CapsuleGeometry(1.3, 4.4, 6, 18),
    ball: new THREE.SphereGeometry(1, 24, 16),
    stalk: new THREE.CylinderGeometry(0.42, 0.42, 1, 12),
    // A plain barrel with a hole through it.
    pore: lathe([[1.1, -3.25], [1.9, -3.6], [2.7, -3.2], [2.9, -2.2], [2.9, 2.2], [2.7, 3.2], [1.9, 3.6], [1.1, 3.25], [0.95, 2.2], [0.95, -2.2], [1.1, -3.25]]),
    // An hourglass: a carrier that opens to one side, then the other.
    carrier: lathe([[0, -3.6], [2.2, -3.6], [2.8, -3.0], [2.65, -1.9], [1.3, 0], [2.65, 1.9], [2.8, 3.0], [2.2, 3.6], [0, 3.6]]),
    body: new THREE.CapsuleGeometry(2.5, 2.6, 6, 22),
    disc: new THREE.CylinderGeometry(3.3, 3.3, 0.16, 44),
    circle: new THREE.BufferGeometry().setFromPoints(Array.from({ length: 65 }, (_, index) => new THREE.Vector3(Math.cos((index / 64) * TAU) * 4, 0, Math.sin((index / 64) * TAU) * 4))),
  };
  return cache;
}

/** Auxiliary subunits. An unspecified pairing is drawn as a ghost; a stated one is firm. */
function auxiliary(form, add, reach) {
  const G = shapes();
  for (const item of form.aux || []) {
    const tone = item.firm ? "aux" : "ghost";
    if (item.role === "Kv-beta") {
      // Four small subunits under the channel, inside the cell.
      for (let k = 0; k < item.count; k++) {
        const angle = (k / item.count) * TAU;
        add(G.ball, tone, [Math.cos(angle) * 2.0, -5.5, Math.sin(angle) * 2.0], { scale: 1.35 });
      }
      reach.bottom = Math.min(reach.bottom, -6.9);
    } else if (item.side === "in") {
      add(G.ball, tone, [1.5, -5.7, 0.9], { scale: 1.8 });
      reach.bottom = Math.min(reach.bottom, -7.5);
    } else if (item.role === "alpha2delta") {
      // A large lobe outside the cell, held to the membrane by a thin anchor.
      add(G.ball, tone, [-0.9, 7.2, -0.5], { scale: [2.6, 2.1, 2.3] });
      add(G.stalk, tone, [-3.7, 3.9, -0.5], { scale: [1, 3.6, 1] });
      reach.top = Math.max(reach.top, 9.3);
    } else {
      // One pass through the membrane with a small domain outside.
      add(G.stalk, tone, [4.7, 0.5, 0], { scale: [1, 6.2, 1] });
      add(G.ball, tone, [4.7, 4.6, 0], { scale: 1.45 });
      reach.top = Math.max(reach.top, 6.1);
      reach.radius = Math.max(reach.radius, 6.2);
    }
  }
}

const BUILDERS = {
  ring(form, add) {
    const G = shapes();
    const count = form.subunits, radius = 2.35;
    for (let k = 0; k < count; k++) {
      const angle = (k / count) * TAU + TAU / (2 * count);
      // Neighbouring subunits alternate in shade, so separate chains read as separate.
      add(G.lobe, k % 2 ? "alt" : "main", [Math.cos(angle) * radius, 0, Math.sin(angle) * radius]);
    }
    const reach = { top: 4.7, bottom: -3.7, radius: radius + 1.9 };
    auxiliary(form, add, reach);
    return reach;
  },

  chain(form, add) {
    const G = shapes();
    const count = form.repeats, radius = 1.95;
    // One chain: the repeats share one shade and one core, and short links join them inside the cell.
    add(G.core, "main", [0, 0, 0]);
    for (let k = 0; k < count; k++) {
      const angle = (k / count) * TAU + TAU / (2 * count);
      add(G.repeat, "main", [Math.cos(angle) * radius, 0, Math.sin(angle) * radius]);
      if (k < count - 1) {
        const between = angle + TAU / (2 * count);
        add(G.ball, "alt", [Math.cos(between) * 2.5, -3.75, Math.sin(between) * 2.5], { scale: 0.72 });
      }
    }
    const reach = { top: 4.7, bottom: -4.5, radius: radius + 1.75 };
    auxiliary(form, add, reach);
    return reach;
  },

  junction(form, add) {
    const G = shapes();
    if (form.style === "plain") {
      add(G.pore, "plain", [0, 0.3, 0], { scale: [1, 0.972, 1] });
      add(G.pore, "plain", [0, 7.3, 0], { scale: [1, 0.972, 1] });
      return { top: UPPER + 3.4, bottom: -3.2, radius: 2.9 };
    }
    const count = form.subunits, radius = 2.85;
    for (const [level, tones] of [[0.3, ["main", "alt"]], [7.3, form.hetero ? ["second", "secondAlt"] : ["main", "alt"]]]) {
      for (let k = 0; k < count; k++) {
        const angle = (k / count) * TAU;
        add(G.connexin, tones[k % 2], [Math.cos(angle) * radius, level, Math.sin(angle) * radius]);
      }
    }
    return { top: UPPER + 3.4, bottom: -3.2, radius: radius + 1.3 };
  },

  cage(form, add) {
    // Twenty trimers on the corners of a dodecahedron: sixty subunits.
    const corners = [];
    const source = new THREE.DodecahedronGeometry(5.4).attributes.position;
    for (let index = 0; index < source.count; index++) {
      const point = new THREE.Vector3().fromBufferAttribute(source, index);
      if (!corners.some((other) => other.distanceTo(point) < 0.01)) corners.push(point);
    }
    const points = [], shades = [];
    for (const corner of corners.slice(0, form.trimers)) {
      const out = corner.clone().normalize();
      const side = new THREE.Vector3(0, 1, 0).cross(out);
      if (side.lengthSq() < 0.01) side.set(1, 0, 0);
      side.normalize();
      const up = out.clone().cross(side);
      for (let k = 0; k < 3; k++) {
        const angle = (k / 3) * TAU;
        points.push(corner.clone().addScaledVector(side, Math.cos(angle) * 1.0).addScaledVector(up, Math.sin(angle) * 1.0));
        shades.push([1, 0.86, 0.74][k]);
      }
    }
    add(shapes().ball, "main", points, { scale: 0.98, shades });
    return { top: 6.5, bottom: -6.5, radius: 6.6, floats: true };
  },

  pore(form, add) {
    const wide = form.wide ? 1.3 : 1;
    add(shapes().pore, "plain", [0, 0, 0], { scale: [wide, 1, wide] });
    return { top: 3.6, bottom: -3.6, radius: 2.9 * wide };
  },

  pump(form, add) {
    const G = shapes();
    // A body through the membrane and a larger head on the side that takes up ATP.
    add(G.body, "plain", [0, 0, 0]);
    add(G.ball, "plain", [0.6, -5.7, 0], { scale: 3.0 });
    return { top: 3.8, bottom: -8.7, radius: 3.1 };
  },

  carrier(form, add) {
    add(shapes().carrier, "plain", [0, 0, 0]);
    return { top: 3.6, bottom: -3.6, radius: 2.8 };
  },

  patch(form, add) {
    const G = shapes();
    // No protein: a marked stretch of the membrane itself.
    add(G.disc, "plainSoft", [0, HALF + 0.1, 0]);
    add(G.disc, "plainSoft", [0, -HALF - 0.1, 0]);
    add(G.circle, "dashes", [0, HALF + 0.14, 0], { line: true });
    return { top: HALF + 0.4, bottom: -HALF - 0.4, radius: 3.6 };
  },
};

/** Draw one unit with the given add(); returns how far it reaches. */
export function buildUnit(form, add) {
  const builder = BUILDERS[form.shape];
  if (!builder) throw new Error(`protein atlas: no shape called ${form.shape}`);
  const reach = builder(form, add);
  if (form.flip) [reach.top, reach.bottom] = [-reach.bottom, -reach.top];
  return reach;
}

/** A rounded rectangle in the xz plane, as a flat outline or a face. */
function roundedShape(width, depth, radius) {
  const shape = new THREE.Shape();
  const x = -width / 2, y = -depth / 2, r = Math.min(radius, width / 2, depth / 2);
  shape.moveTo(x + r, y);
  shape.lineTo(x + width - r, y);
  shape.quadraticCurveTo(x + width, y, x + width, y + r);
  shape.lineTo(x + width, y + depth - r);
  shape.quadraticCurveTo(x + width, y + depth, x + width - r, y + depth);
  shape.lineTo(x + r, y + depth);
  shape.quadraticCurveTo(x, y + depth, x, y + depth - r);
  shape.lineTo(x, y + r);
  shape.quadraticCurveTo(x, y, x + r, y);
  return shape;
}

export function outline(width, depth, radius = 3) {
  const points = roundedShape(width, depth, radius).getPoints(8).map((point) => new THREE.Vector3(point.x, 0, point.y));
  return new THREE.BufferGeometry().setFromPoints(points);
}

let beads = null;
/** Rows of round heads, the way a membrane's surface is usually drawn. */
function beadTexture() {
  if (beads) return beads;
  const canvas = document.createElement("canvas");
  canvas.width = 64;
  canvas.height = 111; // one cell of a hexagonal packing
  const context = canvas.getContext("2d");
  context.fillStyle = "#b4b4b4"; // between the heads the face is a little clearer
  context.fillRect(0, 0, 64, 111);
  context.fillStyle = "#ffffff";
  for (const [x, y] of [[0, 0], [64, 0], [0, 111], [64, 111], [32, 55.5]]) {
    context.beginPath();
    context.arc(x, y, 23, 0, TAU);
    context.fill();
  }
  beads = new THREE.CanvasTexture(canvas);
  beads.wrapS = beads.wrapT = THREE.RepeatWrapping;
  beads.repeat.set(1 / 1.15, 1 / 2.0);
  beads.colorSpace = THREE.NoColorSpace; // read as opacity, not colour
  beads.anisotropy = 4;
  return beads;
}

/**
 * A stretch of membrane: a clear slab with a layer of heads on each face.
 * Returns { group, body, faces }, with materials for the lens to colour.
 */
export function membrane(width, depth, radius = 6) {
  const group = new THREE.Group();
  const shape = roundedShape(width, depth, radius);
  const slab = new THREE.ExtrudeGeometry(shape, { depth: SHEET, bevelEnabled: false, curveSegments: 8 });
  slab.rotateX(-Math.PI / 2);
  slab.translate(0, -HALF, 0);
  const body = new THREE.MeshStandardMaterial({ roughness: 0.5, metalness: 0, transparent: true, opacity: 0.45, depthWrite: false });
  const core = new THREE.Mesh(slab, body);
  core.renderOrder = 2;
  const faces = new THREE.MeshStandardMaterial({ roughness: 0.55, metalness: 0, alphaMap: beadTexture(), transparent: true, opacity: 0.94, depthWrite: false, side: THREE.DoubleSide });
  const face = new THREE.ShapeGeometry(shape, 8);
  face.rotateX(-Math.PI / 2);
  const top = new THREE.Mesh(face, faces), bottom = new THREE.Mesh(face, faces);
  top.position.y = HALF + 0.02;
  bottom.position.y = -HALF - 0.02;
  top.renderOrder = bottom.renderOrder = 2;
  group.add(core, top, bottom);
  group.userData.unpickable = true; // a click on the membrane reaches what stands in it
  return { group, body, faces };
}
