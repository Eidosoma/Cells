// The cell's own structures, drawn as parts of their own: the nucleus with its double
// envelope, its pores, its nucleolus and its chromatin; the rough endoplasmic reticulum, one
// folded sheet that runs on from the nuclear envelope; the Golgi apparatus, a stack of
// curved cisternae with vesicles budding from their rims; the vesicles that would carry
// proteins on to the membrane; the ribosomes, free, in strings on a messenger, and on the
// rough ER; and a free chromosome where a cell has no nucleus.
//
// The user, 16 November 2026: nucleus, Golgi and ribosomes "1st class items ... in the
// default mode show it all in the coolest possible way" (docs/CELL_STRUCTURES.md). Each is
// bound to its capability in the scene where the scene has one, and is planned there: with
// "Colour: Biology" a planned part is drawn whole, with "Colour: Status" it is a sketch
// (cell.js, Part). A scene without these capabilities draws the structures as before: the
// chromatin with the nucleus, the ribosomes as neutral scenery, no carriers.
//
// What a cell holds comes from its species' file (cell.parts): a nucleus or a free
// chromosome, the organelles it lists, and a count of ribosomes where it gives one. Every
// other number here is the picture's choice, and the panel says so (asDrawn).
//
// Everything is placed from a stream of chance of its own, so that what the cell builder
// draws after it does not move when a structure changes.

import * as THREE from "../three.js";
import STRUCTURES from "../../data/parts/structures.json" with { type: "json" };

const UP = new THREE.Vector3(0, 1, 0);
const radial = (angle) => new THREE.Vector3(Math.cos(angle), 0, Math.sin(angle));
const along = (direction) => new THREE.Quaternion().setFromUnitVectors(UP, direction.clone().normalize());
const turned = (random) => new THREE.Quaternion().setFromEuler(new THREE.Euler(random() * Math.PI * 2, random() * Math.PI * 2, random() * Math.PI * 2));

// The nucleus is opened by a wedge of its upper half, as a globe is cut away, toward where the
// camera of the cell's stop stands (cell.js, makeStops: azimuth 0.52), a little to the side away
// from the ER. WEDGE is half the wedge's width.
const OPEN = Math.PI / 2 - 0.52 - 0.3, WEDGE = Math.PI / 3;

// The structures a capability is drawn at, with what a cell must hold to have it (cell.parts),
// and the reason given where it does not: one table, read here and by the species reader
// (data/parts/structures.json; tools/lib/species.py). Read only where a species' file says
// nothing of the capability.
const NEEDS = Object.fromEntries(
  Object.entries(STRUCTURES.structures).map(([part, need]) => [
    part,
    {
      holds: (parts) => (need.held_when === "nucleus" ? Boolean(parts.nucleus) : organelles(parts).includes(need.held_when.replace(/^organelle:/, ""))),
      why: (parts) => (need.why_free_chromosome && parts.chromosome_kbp ? need.why_free_chromosome : need.why),
    },
  ])
);
/** The organelles a cell holds: its file's list, or, where it gives none, an animal cell's where it has a nucleus. */
export const organelles = (parts) => parts.organelles || (parts.nucleus ? STRUCTURES.nucleated_organelles : []);

/**
 * The capabilities that have no place in a species' cell because it does not hold the
 * structure they are drawn at, each with the reason, as read from its file's cell.parts.
 * A capability the file itself places (present or absent) is left to the file.
 */
export function structureAbsence(capabilities, species) {
  const parts = species.cell?.parts || {}, said = species.cell?.capabilities || {};
  const absent = new Map();
  for (const entity of capabilities) {
    const need = NEEDS[entity.part];
    if (need && !said[entity.id] && !need.holds(parts)) absent.set(entity.id, need.why(parts));
  }
  return absent;
}

// ------------------------------------------------------------------ doors into the Protein atlas

// Where a structure's proteins stand among a species' own: the shelf of its membrane
// (schema/SPECIES_PROTEINS.md fixes these shelf ids), or a set its marks pick out by name.
const SHELF_OF = { nucleus: "nucleus", er: "er", mitochondria: "mito" };
const SET_OF = { ribosomes: "ribosome" };

/**
 * The doors from a part of the cell into the Protein atlas, for the species shown: one where
 * the species' own proteins can show the set (a shelf the scene's summary lists, or a mark's
 * value it lists), none where they cannot. `summary` is the species' entry in the scene's
 * proteins.shelves.
 */
export function structureDoors(entity, species, summary) {
  if (!entity || !summary || !species?.id) return [];
  const shelf = SHELF_OF[entity.part] && (summary.shelves || []).find((item) => item.id === SHELF_OF[entity.part]);
  if (shelf) {
    const count = Number(shelf.proteins || 0).toLocaleString("en-US");
    return [{ label: `Show the ${count} proteins of the ${shelf.label.charAt(0).toLowerCase()}${shelf.label.slice(1)} shelf in the Protein atlas`, lens: "proteins", show: "own", shelf: shelf.id }];
  }
  const wanted = SET_OF[entity.part];
  if (wanted) {
    for (const [mark, values] of Object.entries(summary.sets || {})) {
      const value = (values || []).find((item) => String(item).toLowerCase() === wanted);
      if (value !== undefined) return [{ label: `Show the proteins of the ${wanted} in the Protein atlas`, lens: "proteins", show: "own", mark, value: String(value) }];
    }
  }
  return [];
}

// ------------------------------------------------------------------ geometry

/** One geometry from several, each with positions and normals (and an index, or none). */
function merged(list) {
  const positions = [], normals = [], index = [];
  let offset = 0;
  for (const geometry of list) {
    const position = geometry.attributes.position, normal = geometry.attributes.normal;
    for (let at = 0; at < position.count; at++) {
      positions.push(position.getX(at), position.getY(at), position.getZ(at));
      normals.push(normal.getX(at), normal.getY(at), normal.getZ(at));
    }
    if (geometry.index) for (let at = 0; at < geometry.index.count; at++) index.push(geometry.index.getX(at) + offset);
    else for (let at = 0; at < position.count; at++) index.push(at + offset);
    offset += position.count;
    geometry.dispose();
  }
  const out = new THREE.BufferGeometry();
  out.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  out.setAttribute("normal", new THREE.Float32BufferAttribute(normals, 3));
  out.setIndex(index);
  return out;
}

/**
 * A wall that stands along a path drawn on the level: a tube along the path, stretched
 * upward, so that it is `thickness` wide and `height` tall with rounded edges. The path's
 * points lie at y = 0; the wall is centred there.
 */
function wallAlong(points, thickness, height, closed = false, { segments = null, around = 10 } = {}) {
  const curve = new THREE.CatmullRomCurve3(points, closed, "centripetal");
  const geometry = new THREE.TubeGeometry(curve, segments ?? Math.max(24, Math.round(curve.getLength() / (thickness * 0.9))), thickness / 2, around, closed);
  const stretch = height / thickness;
  const position = geometry.attributes.position, normal = geometry.attributes.normal, n = new THREE.Vector3();
  for (let at = 0; at < position.count; at++) {
    position.setY(at, position.getY(at) * stretch);
    n.set(normal.getX(at), normal.getY(at) / stretch, normal.getZ(at)).normalize(); // a normal of a stretched surface
    normal.setXYZ(at, n.x, n.y, n.z);
  }
  return geometry;
}

/** A quarter of a disc or of a ring, in the plane of two axes at right angles: the first quadrant of `first` and `second`. */
function quarter(centre, first, second, inner, outer, from = 0, to = Math.PI / 2, segments = 24) {
  const geometry = inner > 0 ? new THREE.RingGeometry(inner, outer, segments, 1, from, to - from) : new THREE.CircleGeometry(outer, segments, from, to - from);
  const basis = new THREE.Matrix4().makeBasis(first, second, new THREE.Vector3().crossVectors(first, second));
  geometry.applyMatrix4(basis.setPosition(centre));
  return geometry;
}

/** An arc of points in the plane of two axes, from one angle to another. */
function arc(centre, first, second, radius, from, to, steps = 24) {
  return Array.from({ length: steps + 1 }, (_, step) => {
    const angle = from + ((to - from) * step) / steps;
    return centre.clone().addScaledVector(first, Math.cos(angle) * radius).addScaledVector(second, Math.sin(angle) * radius);
  });
}

/**
 * The two subunits of a ribosome: a large one, and a small one that sits on it. Its long way is up.
 * `light` draws each with fewer faces (128 triangles in place of 312), for a small cell that holds
 * thousands of them, each a few pixels across at its stop.
 */
function subunits(radius, light = false) {
  const large = new THREE.SphereGeometry(radius, light ? 8 : 12, light ? 6 : 9).scale(1, 0.84, 1);
  const small = new THREE.SphereGeometry(radius * 0.7, light ? 6 : 10, light ? 5 : 7).scale(1.18, 0.62, 0.92).translate(0, radius * 0.86, 0);
  return { large, small };
}

/** A random walk inside a ball, smoothed: a strand of chromatin, or a free chromosome's thread. */
function walk(random, start, steps, step, inBall) {
  const knots = [start.clone()];
  const heading = new THREE.Vector3(random() - 0.5, random() - 0.5, random() - 0.5).normalize();
  for (let index = 0; index < steps; index++) {
    heading.add(new THREE.Vector3(random() - 0.5, random() - 0.5, random() - 0.5).multiplyScalar(1.4)).normalize();
    let next = knots.at(-1).clone().addScaledVector(heading, step);
    for (let tries = 0; tries < 8 && !inBall(next); tries++) {
      heading.set(random() - 0.5, random() - 0.5, random() - 0.5).normalize();
      next = knots.at(-1).clone().addScaledVector(heading, step);
    }
    if (inBall(next)) knots.push(next);
  }
  return knots;
}

// ------------------------------------------------------------------ the structures

/**
 * Builds the cell's structures in one size mode. `env` is what the cell builder knows of the
 * cell (cell_parts.js, buildCell): its context, mode and style, frame, parts, where the
 * nucleus, the ER and the Golgi stand, and how to test a place. Returns the anchors and
 * probes the lens needs, and what the panel says was drawn of each part.
 */
export function buildStructures(env) {
  const { ctx, real, parts } = env;
  const known = (name) => Boolean(ctx.known?.(name));
  const random = env.random;
  const out = { drawn: {}, studs: [] };
  const chromatinPart = known("chromatin") ? "chromatin" : "nucleus";
  if (parts.nucleus) {
    out.nucleus = nucleus(env, random, chromatinPart);
    out.drawn[out.nucleus.part] = out.nucleus.said;
  } else if (parts.chromosome_kbp) {
    out.chromosome = chromosome(env, random, chromatinPart);
    out.drawn[chromatinPart] = out.chromosome.said;
  }
  // An animal cell's Golgi stands beside the nucleus, round its centrosome (cell_layout.js): its ER leaves it a window.
  if (env.organelle("golgi") && env.nucleusAt && env.centrosomeAt) env.golgiWindow = golgiWindow(env);
  if (env.organelle("er")) {
    const er = reticulum(env, random);
    out.studs = er.studs;
    out.drawn.er = er.said;
  }
  if (env.organelle("golgi")) {
    const golgi = golgiOf(env, random);
    out.drawn.golgi = golgi.said;
    // An animal cell's centrosome, drawn as scenery that can be chosen: the scenery part lists it (parts/scenery.js).
    if (golgi.centrosome) out.scenery = [golgi.centrosome];
    if (known("vesicles") && env.has("vesicles")) out.drawn.vesicles = carriers(env, random, golgi);
  }
  const made = ribosomes(env, random, out, known("ribosomes") && env.has("ribosomes"));
  if (made) out.drawn.ribosomes = made;
  return out;
}

/** The nucleus: its double envelope opened at one corner, its pores, its nucleolus and its chromatin. */
function nucleus(env, random, chromatinPart) {
  const { ctx, real, style, frame } = env;
  const c = env.nucleusAt, R = style.nucleusRadius, u = frame.u;
  // The space between the two membranes is about 40 nm; drawn to scale it is that, and wider where parts are enlarged.
  const gap = real ? 0.04 / u : 0.16, skin = real ? 0.008 / u : 0.055;
  const rim = R - skin, lumen = R - skin - gap, core = R - 2 * skin - gap; // the outer membrane's inside, the inner membrane's outside, and its inside
  // The wedge is where both A and B face (and above the middle): its sides are the rays at OPEN - WEDGE and OPEN + WEDGE.
  const A = radial(OPEN + WEDGE - Math.PI / 2), B = radial(OPEN - WEDGE + Math.PI / 2);
  const opened = (point) => {
    const away = point.clone().sub(c);
    return away.dot(A) > 0 && away.dot(B) > 0 && away.y > 0;
  };
  // The corner cut away, for the renderer (in the world, where the cell's frame is scaled by u) and for picking.
  const centre = c.clone().multiplyScalar(u);
  const planes = [A, B, UP].map((normal) => new THREE.Plane(normal.clone().negate(), normal.dot(centre)));
  const clipped = (material) => {
    for (const one of [material, material.userData?.twin].filter(Boolean)) {
      one.clippingPlanes = planes;
      one.clipIntersection = true;
    }
    return material;
  };
  const notOpened = (hit) => !opened(hit.point.clone().multiplyScalar(1 / u));
  const shell = (geometry, material, order) => {
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.copy(c);
    mesh.renderOrder = order;
    mesh.userData.pickFilter = notOpened;
    return mesh;
  };

  const envelope = ctx.part("nucleus", c.clone().add(new THREE.Vector3(-0.35 * R, R + 0.1, -0.35 * R)));
  envelope.priority = 54; // where names clash, the three structures' names are kept before other planned parts' (cell.js, buildLabels)
  // The two membranes of the envelope: the outer one with its pores' texture, the inner one a shade deeper.
  const outer = clipped(envelope.material({ hue: "bioNucleus", opacity: 0.74, roughness: 0.3, rim: 0.55, alphaRim: 0.2, depthWrite: true, side: THREE.DoubleSide, thin: 0.9, texture: "pores" }));
  const inner = clipped(envelope.material({ hue: "bioNucleus", shade: -0.14, opacity: 0.5, roughness: 0.4, side: THREE.DoubleSide, depthWrite: false, thin: 0.6 }));
  envelope.add(shell(new THREE.SphereGeometry(R, 72, 48), outer, 2), shell(new THREE.SphereGeometry(lumen, 60, 40), inner, 1));
  // The faces of the cut: the nucleoplasm a light tone, and the two membranes in section with the space between.
  // Each face of the cut as two axes and the angles between them that it spans: the two upright sides, and the level floor.
  const X = new THREE.Vector3(1, 0, 0), Z = new THREE.Vector3(0, 0, 1);
  const faces = [[radial(OPEN + WEDGE), UP, 0, Math.PI / 2], [radial(OPEN - WEDGE), UP, 0, Math.PI / 2], [X, Z, OPEN - WEDGE, OPEN + WEDGE]];
  const plasm = envelope.material({ hue: "bioNucleus", shade: 0.5, opacity: 0.72, roughness: 0.7, side: THREE.DoubleSide, depthWrite: false, rim: 0 });
  const space = envelope.material({ hue: "bioNucleus", shade: 0.8, opacity: 0.75, roughness: 0.6, side: THREE.DoubleSide, depthWrite: false, rim: 0 });
  const membrane = envelope.material({ hue: "bioNucleus", shade: -0.42, roughness: 0.4, side: THREE.DoubleSide, rim: 0 });
  const plasmFaces = new THREE.Mesh(merged(faces.map(([first, second, from, to]) => quarter(c, first, second, 0, core * 0.999, from, to, 32))), plasm);
  plasmFaces.renderOrder = 3;
  plasmFaces.userData.unpickable = true; // a click on the cut face reaches the chromatin behind it
  envelope.add(plasmFaces);
  // Where a pore crosses the cut, the two membranes meet round it: each face has two pores in section.
  const poresAt = (from, to) => [from + (to - from) * 0.22, from + (to - from) * 0.71];
  const poreHalf = (real ? 0.06 : 0.13) / R; // half the angle a pore takes in the section
  const pieces = (from, to) => {
    const spans = [];
    let start = from;
    for (const angle of poresAt(from, to)) {
      spans.push([start, angle - poreHalf]);
      start = angle + poreHalf;
    }
    spans.push([start, to]);
    return spans;
  };
  if (real) {
    // To scale a membrane in section is far under a pixel: a fine line for each.
    const lines = [];
    for (const [first, second, start, end] of faces) {
      for (const radius of [R - skin / 2, core + skin / 2]) {
        for (const [from, to] of pieces(start, end)) {
          const points = arc(c, first, second, radius, from, to, 12);
          for (let at = 0; at + 1 < points.length; at++) lines.push(points[at], points[at + 1]);
        }
      }
    }
    const section = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(lines), envelope.lineMaterial({ hue: "bioNucleus", opacity: 0.95 }));
    section.userData.unpickable = true; // a line is picked from far round it: a click on the cut faces goes on to the chromatin
    envelope.add(section);
  } else {
    const rings = [], gaps = [];
    for (const [first, second, start, end] of faces) {
      for (const [from, to] of pieces(start, end)) {
        rings.push(quarter(c, first, second, rim, R, from, to, 12), quarter(c, first, second, core, core + skin, from, to, 12));
        gaps.push(quarter(c, first, second, core + skin, rim, from, to, 12));
      }
    }
    const section = new THREE.Mesh(merged(rings), membrane);
    section.renderOrder = 4;
    const between = new THREE.Mesh(merged(gaps), space);
    between.renderOrder = 4;
    envelope.add(section, between);
  }
  // The pores: rings set in the envelope, all over what the cut leaves, and across each face of the cut.
  const pores = [];
  for (let tries = 0; pores.length < (real ? 1500 : 110) && tries < 6000; tries++) {
    const direction = new THREE.Vector3(random() * 2 - 1, random() * 2 - 1, random() * 2 - 1);
    if (direction.lengthSq() > 1 || direction.lengthSq() < 0.01) continue;
    direction.normalize();
    const at = c.clone().addScaledVector(direction, R + (real ? 0.004 : 0.012));
    if (opened(at)) continue;
    pores.push({ position: at, direction });
  }
  if (real) envelope.add(env.dots(pores.map((pore) => pore.position), envelope.points({ hue: "bioNucleus", shade: -0.3, size: 1.5, opacity: 0.85 })));
  else {
    const complex = envelope.material({ hue: "bioNucleus", shade: -0.4, roughness: 0.45 });
    envelope.add(env.instanced(new THREE.TorusGeometry(0.12, 0.042, 8, 16).rotateX(Math.PI / 2), complex, pores));
    // In section a pore is where the two membranes meet: a plug across the space between them.
    const plugs = [];
    for (const [first, second, start, end] of faces) {
      for (const angle of poresAt(start, end)) {
        const way = first.clone().multiplyScalar(Math.cos(angle)).addScaledVector(second, Math.sin(angle));
        plugs.push({ position: c.clone().addScaledVector(way, (R + core) / 2), direction: way });
      }
    }
    envelope.add(env.instanced(new THREE.CapsuleGeometry(0.075, R - core - 0.1, 4, 10), complex, plugs));
  }
  // The nucleolus, where ribosomes are put together: a dense body sitting in the corner the cut opens, as the core of a cut-away globe.
  const toward = radial(OPEN);
  const nucleolusAt = c.clone().addScaledVector(toward, style.nucleolus * 0.32).addScaledVector(UP, style.nucleolus * 0.28);
  const body = envelope.material({ hue: "bioNucleus", shade: -0.45, roughness: 0.6, thin: 0.4, texture: "grain" });
  const nucleolus = new THREE.Mesh(new THREE.SphereGeometry(style.nucleolus, 40, 28), body);
  nucleolus.position.copy(nucleolusAt);
  envelope.add(nucleolus);
  const fibrils = [];
  for (let index = 0; index < (real ? 0 : 7); index++) {
    const way = new THREE.Vector3(random() - 0.5, random() * 0.8, random() - 0.5).normalize();
    fibrils.push({ position: nucleolusAt.clone().addScaledVector(way, style.nucleolus * 0.93), scale: 0.7 + random() * 0.6 });
  }
  if (fibrils.length) envelope.add(env.instanced(new THREE.SphereGeometry(style.nucleolus * 0.2, 14, 10), envelope.material({ hue: "bioNucleus", shade: -0.2, roughness: 0.5 }), fibrils));

  // The chromatin: strands of DNA and protein through the nucleoplasm, densest by the envelope.
  // It is where regulatory circuits act, and is their part where the scene gives them one.
  const chromatin = ctx.part(chromatinPart, c.clone().addScaledVector(toward, core * 0.55).addScaledVector(UP, core * 0.04));
  const strandMaterial = clipped(chromatin.material({ hue: "bioNucleus", shade: -0.5, roughness: 0.5, thin: 0.3 }));
  const reach = core * 0.94;
  const inBall = (point) => point.distanceTo(c) < reach && point.distanceTo(nucleolusAt) > style.nucleolus * 1.05;
  const strands = [];
  for (let index = 0; index < (real ? 30 : 18); index++) {
    let start;
    for (let tries = 0; tries < 40; tries++) {
      const way = new THREE.Vector3(random() - 0.5, random() - 0.5, random() - 0.5).normalize();
      start = c.clone().addScaledVector(way, reach * (index % 3 ? 0.85 : 0.55) * (0.8 + random() * 0.2));
      if (inBall(start)) break;
    }
    const knots = walk(random, start, real ? 40 : 30, core * (real ? 0.07 : 0.1), inBall);
    if (knots.length < 4) continue;
    strands.push(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(knots, false, "catmullrom", 0.5), knots.length * 4, real ? 0.018 : 0.062, 6, false));
  }
  const tangle = new THREE.Mesh(merged(strands), strandMaterial);
  tangle.userData.pickFilter = notOpened;
  tangle.renderOrder = 1;
  chromatin.add(tangle);
  // Where the cut passes through the chromatin: its strands cut across, as specks on each face, most of them by the envelope.
  const specks = [];
  faces.forEach(([first, second, from, to], index) => {
    const out = [A, B, UP][index].clone(); // off the face, toward the side that was cut away, so that the face does not hide them
    for (let count = 0; count < (real ? 160 : 70); count++) {
      const angle = from + (to - from) * random(), radius = core * (0.3 + 0.66 * Math.sqrt(random()));
      const at = c.clone().addScaledVector(first, Math.cos(angle) * radius).addScaledVector(second, Math.sin(angle) * radius);
      if (at.distanceTo(nucleolusAt) < style.nucleolus * 1.05) continue;
      specks.push({ position: at.addScaledVector(out, real ? 0.004 : 0.012), direction: out, scale: 0.6 + random() * 0.8 });
    }
  });
  const speck = new THREE.CylinderGeometry(real ? 0.022 : 0.06, real ? 0.022 : 0.06, 0.004, 10);
  const cut = env.instanced(speck, chromatin.material({ hue: "bioNucleus", shade: -0.5, roughness: 0.6 }), specks);
  cut.renderOrder = 5;
  chromatin.add(cut);
  // What a click on the cut faces reaches: the chromatin within.
  // Drawn on both sides: a click that comes in through the wedge meets its far side.
  const within = new THREE.Mesh(new THREE.SphereGeometry(core * 0.96, 24, 16), new THREE.MeshBasicMaterial({ colorWrite: false, depthWrite: false, side: THREE.DoubleSide }));
  within.position.copy(c);
  within.userData.pickFilter = notOpened;
  chromatin.add(within);
  // And the cut faces themselves, a hair in front of them: a click on what the cut shows of the nucleoplasm chooses the
  // chromatin there, before anything that lies just under the faces (a plant cell's vacuole, where the nucleus reaches into it).
  const lift = real ? 0.016 : 0.03; // above a vacuole's section, which lies 0.012 over the cut (cell_scenery.js)
  const facesAt = merged(faces.map(([first, second, from, to], index) => quarter(c.clone().addScaledVector([A, B, UP][index], lift), first, second, 0, core * 0.999, from, to, 16)));
  chromatin.add(new THREE.Mesh(facesAt, within.material));

  const across = (2 * R * u).toPrecision(2);
  return {
    part: "nucleus",
    probe: c.clone().addScaledVector(toward, core * 0.78).addScaledVector(radial(OPEN + Math.PI / 2), core * 0.12).addScaledVector(UP, 0.02),
    said: [
      ["Drawn", `${across} µm across, in the cell drawn here: the picture's choice, since the species' file gives no size. A wedge of it is cut away, as of a globe, to show the two membranes of its envelope, the chromatin and the nucleolus.`],
      ["Its envelope", real ? `Two membranes about ${Math.round(gap * u * 1000)} nm apart, with ${pores.length.toLocaleString("en-US")} pores drawn as dots: the picture's choice.` : `Two membranes, drawn farther apart than they are so that the space between them shows, with ${pores.length} pores: the picture's choice.`],
    ],
  };
}

/** A cell without a nucleus: its chromosome lies free in the cytoplasm, one closed thread. */
function chromosome(env, random, partName) {
  const { ctx, frame, parts } = env;
  const { at: coreAt, radius: coreRadius, reach: coreReach } = env.core;
  const thread = ctx.part(partName, coreAt.clone().add(new THREE.Vector3(0, coreRadius + 0.3, 0)));
  if (env.fine) return chromosomeInSlab(env, random, thread);
  // Regulation acts there, so it is where the regulatory circuits are drawn. The thread is a
  // tangle through the cell's middle; its true length would fill the cell far more.
  const turns = Math.round(Math.min(900, Math.max(60, parts.chromosome_kbp / 2)));
  const knots = [];
  let at = coreAt.clone();
  const heading = new THREE.Vector3(random() - 0.5, random() - 0.5, random() - 0.5).normalize();
  const lengthwise = coreReach > coreRadius * 1.5 ? new THREE.Vector3(0.5, 0, 0) : null;
  for (let step = 0; step < turns; step++) {
    heading.add(new THREE.Vector3(random() - 0.5, random() - 0.5, random() - 0.5).normalize().multiplyScalar(0.9));
    if (lengthwise) {
      if (Math.abs(at.x - coreAt.x) > coreReach * 0.86) lengthwise.x = at.x > coreAt.x ? -0.5 : 0.5;
      heading.add(lengthwise);
    }
    heading.normalize();
    const next = at.clone().addScaledVector(heading, coreRadius * 0.34);
    const away = next.clone().sub(coreAt);
    if (Math.hypot(away.x * (coreRadius / coreReach), away.y, away.z) > coreRadius || next.y > env.cut - 0.15 || env.inside(next) < 0.9) {
      heading.addScaledVector(away.normalize(), -1.5).normalize();
      next.copy(at).addScaledVector(heading, coreRadius * 0.34);
    }
    knots.push(next);
    at = next;
  }
  const path = new THREE.CatmullRomCurve3(knots, true, "catmullrom", 0.5), width = 0.075 * 2;
  const strand = new THREE.Mesh(new THREE.TubeGeometry(path, turns * 5, width / 2, 5, true), thread.material({ hue: "bioNucleus", roughness: 0.35, clip: true, thin: 0.5 }));
  strand.renderOrder = 2;
  thread.add(strand);
  const reach = new THREE.Mesh(new THREE.SphereGeometry(coreRadius * 0.92, 20, 14), thread.proxyMaterial());
  reach.position.copy(coreAt);
  reach.scale.set(coreReach / coreRadius, 1, 1);
  thread.add(reach);
  // What the panel says was drawn: the thread's width and length against what the file's length in
  // base pairs would make as DNA, by the textbook's 0.34 nm a base pair and 2 nm across.
  const drawn = path.getLength() * frame.u, whole = parts.chromosome_kbp * 0.34;
  const said = [["Drawn", `One closed thread ${Number((width * frame.u * 1000).toPrecision(2))} nm thick and ${Number(drawn.toPrecision(2)).toLocaleString("en-US")} µm long, in the part of the cell kept below the cut. Its ${parts.chromosome_kbp.toLocaleString("en-US")} kbp would make about ${Math.round(whole).toLocaleString("en-US")} µm of DNA 2 nm thick, at 0.34 nm a base pair (textbook figures): the thread shows about ${Math.max(1, Math.round((drawn / whole) * 100))}% of that length. Its width, its length and how it winds are the picture's choice.`]];
  return { knots, said };
}

/**
 * The rough endoplasmic reticulum: one sheet folded to and fro round the nucleus, that runs
 * on from the nucleus's outer membrane, with its lumen joined to the space in the envelope.
 * Where an animal cell's Golgi stands beside the nucleus (env.golgiWindow, the half-angle it
 * takes, seen from the nucleus's middle), the sheet is two arms, one each side of it, each
 * running on from the envelope. Returns where the ribosomes on it sit, where its sheets lie (for
 * the carriers that leave it) and what the panel says was drawn. To scale, tubules reach on
 * through the cell.
 */
function reticulum(env, random) {
  const { ctx, real, style, frame } = env;
  const c = env.nucleusAt, shape = style.er, facing = env.erFacing;
  const spans = Array.from({ length: shape.layers }, (_, layer) => Math.max(0.9, shape.span - layer * shape.shrink));
  const open = env.golgiWindow || 0;
  // Each arm turns back at the end where its sheet before stopped; `way` is the way its first sheet runs from the nucleus.
  // Without a window, one arm, whose first sheet begins at the nucleus on its far side, away from where the nucleus is opened.
  const arms = open ? [{ start: facing + open, way: 1 }, { start: facing - open, way: -1 }] : [{ start: facing + spans[0] * 0.75, way: -1 }];
  const spanOf = (layer) => (open ? Math.max(0.35, (spans[layer] - 2 * open) / 2) : spans[layer]);
  const er = ctx.part("er", c.clone().addScaledVector(radial(open ? facing + open + spanOf(0) / 2 : facing), shape.first + shape.gap * 1.5).setY(env.cut + shape.height * 0.45));
  const sheet = er.material({ hue: "bioEr", roughness: 0.4, side: THREE.DoubleSide, thin: 0.8, texture: "grain" });
  const y = env.cut + shape.height * 0.38; // the middle of the sheet's height: it stands on the cut face, a little below it
  const flat = (angle, radius) => c.clone().addScaledVector(radial(angle), radius).setY(0);
  const nuclear = env.nucleusAt ? style.nucleusRadius : 0;
  const sheets = [];
  for (const arm of arms) {
    const own = [];
    let end = arm.start;
    for (let layer = 0; layer < shape.layers; layer++) {
      const from = end, to = layer % 2 ? from - arm.way * spanOf(layer) : from + arm.way * spanOf(layer);
      own.push({ radius: shape.first + layer * shape.gap, from, to });
      end = to;
    }
    const path = [];
    // From inside the outer nuclear membrane, out to the first sheet.
    path.push(flat(own[0].from - arm.way * 0.16, nuclear * 0.86), flat(own[0].from - arm.way * 0.08, (nuclear + own[0].radius) / 2));
    own.forEach((one, index) => {
      const steps = Math.max(8, Math.round(Math.abs(one.to - one.from) * one.radius * 3));
      for (let step = 0; step <= steps; step++) path.push(flat(one.from + ((one.to - one.from) * step) / steps, one.radius));
      if (own[index + 1]) {
        // The turn: out past the sheet's end and round to the next one.
        const beyond = Math.sign(one.to - one.from) * (shape.gap * 0.55) / one.radius;
        path.push(flat(one.to + beyond, one.radius + shape.gap * 0.5));
      }
    });
    const wall = new THREE.Mesh(wallAlong(path, shape.thickness, shape.height), sheet);
    wall.position.y = y;
    er.add(wall);
    sheets.push(...own);
  }
  // Ribosomes on both faces of each sheet: they make it rough.
  const studs = [];
  for (const one of sheets) {
    const span = Math.abs(one.to - one.from), count = Math.round(span * one.radius * (real ? 22 : 3.4));
    for (let index = 0; index < count; index++) {
      const angle = Math.min(one.from, one.to) + (span * (index + random())) / count;
      const lift = (random() * 2 - 1) * 0.86; // up or down the sheet, as a share of its half height
      const half = (shape.thickness / 2) * Math.sqrt(Math.max(0, 1 - lift * lift)); // the sheet is thinner toward its edges
      const side = random() < 0.5 ? 1 : -1;
      const out = radial(angle).multiplyScalar(side);
      studs.push({ position: c.clone().addScaledVector(radial(angle), one.radius + side * (half + (real ? 0.012 : 0.05))).setY(y + lift * shape.height * 0.5), direction: out });
    }
  }
  if (real) {
    // The network reaches on through the cell as tubules.
    const tubes = [];
    for (let strand = 0; strand < 70; strand++) {
      const way = new THREE.Vector3(random() - 0.5, random() - 0.5, random() - 0.5).normalize();
      const point = c.clone().addScaledVector(way, style.nucleusRadius + 0.4 + random() * 2.5);
      const heading = new THREE.Vector3(random() - 0.5, random() - 0.5, random() - 0.5).normalize();
      for (let step = 0; step < 14; step++) {
        const next = point.clone().addScaledVector(heading.add(new THREE.Vector3(random() - 0.5, random() - 0.5, random() - 0.5).multiplyScalar(0.55)).normalize(), 0.42);
        if (!env.inCytoplasm(next, 0.2)) break;
        tubes.push(point.x, point.y, point.z, next.x, next.y, next.z);
        point.copy(next);
      }
    }
    const web = new THREE.BufferGeometry();
    web.setAttribute("position", new THREE.Float32BufferAttribute(tubes, 3));
    er.add(new THREE.LineSegments(web, er.lineMaterial({ hue: "bioEr", opacity: 0.55 })));
  }
  // Where its sheets lie, for the carriers that leave it for the Golgi.
  env.erSheets = { centre: c, y, sheets };
  const um = (units) => Number((units * frame.u).toPrecision(2)).toLocaleString("en-US");
  const where = open ? `in two arms, one each side of the Golgi, which stands beside the nucleus` : `on one side of the nucleus`;
  const said = [["Drawn", `Rough endoplasmic reticulum: ${shape.layers} sheets folded to and fro ${where}, running on from the outer membrane of the nuclear envelope; ${um(shape.thickness)} µm thick and ${um(shape.gap)} µm apart${real ? ", with tubules reaching on through the cell" : ", enlarged"}. Their number, size and place are the picture's choice.`]];
  return { studs, said };
}

// ------------------------------------------------------------------ the Golgi apparatus

// A stack's cisternae, from the cis face, as widths in the cell's frame; and to scale, an animal cell's ribbon of stacks
// side by side, each about a micrometre across. The picture's choice (docs/CELL_STRUCTURES.md).
const CISTERNAE = { real: [1.0, 1.15, 1.2, 1.15, 1.0, 0.85], schematic: [2.2, 2.55, 2.7, 2.5, 2.1] };
const RIBBON = { count: 4, width: 1.2, gap: 0.3 };

/** The half-angle, seen from the nucleus's middle, that an animal cell's Golgi takes beside it, with room on each side: where its ER leaves a window. */
function golgiWindow(env) {
  const c = env.nucleusAt, at = env.golgiAt;
  const reach = Math.hypot(at.x - c.x, at.z - c.z);
  const half = env.real ? (RIBBON.count * RIBBON.width + (RIBBON.count - 1) * RIBBON.gap) / 2 : Math.max(...CISTERNAE.schematic) / 2;
  return half / reach + 0.2;
}

/**
 * The Golgi apparatus, as the cell holds it (the user, 17 November 2026; docs/CELL_STRUCTURES.md):
 *   an animal cell   beside the nucleus, toward the cell's middle, round its centrosome (drawn as
 *                    scenery): one stack where parts are enlarged, a ribbon of four stacks to scale;
 *   a plant cell     many small stacks spread through the thin cytoplasm by the membrane, with no
 *                    ribbon and no centrosome: 14 where parts are enlarged and few, 40 to scale.
 * However many stacks there are, they are one shared geometry: each level of cisterna one mesh,
 * the rims and the buds one instanced mesh each, so a frame draws as many of them as for one
 * stack. Their number, size and place are the picture's choice, and the panel says so.
 * Returns the stack the carriers leave from (its cis and trans faces), what the panel says was
 * drawn, and the centrosome as an item of scenery that can be chosen, where there is one.
 */
function golgiOf(env, random) {
  const { real, frame } = env;
  const g = env.style.golgi;
  const depth = (g.count - 1) * g.gap + g.half * (real ? 1.6 : 1.9);
  const um = (units) => Number((units * frame.u).toPrecision(2)).toLocaleString("en-US");
  if (env.vacuole) return dispersed(env, random, depth, um);
  const c = env.nucleusAt, at = env.golgiAt;
  if (!c) {
    // A cell that names a Golgi and no nucleus: one stack where the layout puts it, facing the cell's middle.
    const made = drawStacks(env, [stackPieces(env, random, { at, facing: Math.atan2(at.z, at.x) + Math.PI })], at);
    return { ...made, said: [["Drawn", `A stack of ${g.count} cisternae: the picture's choice, since the species' file gives no size or number.`]] };
  }
  const facing = Math.atan2(at.z - c.z, at.x - c.x); // from the nucleus to the Golgi
  const reach = Math.hypot(at.x - c.x, at.z - c.z);
  // To scale, a ribbon of four stacks side by side along the nucleus, each about a micrometre across.
  const ribbon = real ? RIBBON : null;
  const angles = ribbon ? Array.from({ length: ribbon.count }, (_, index) => facing + ((index - (ribbon.count - 1) / 2) * (ribbon.width + ribbon.gap)) / reach) : [facing];
  const pieces = angles.map((angle) => stackPieces(env, random, { at: c.clone().addScaledVector(radial(angle), reach).setY(at.y), facing: angle }));
  const made = drawStacks(env, pieces, at);
  const centrosome = env.centrosomeAt ? drawCentrosome(env, facing) : null;
  // The cis face's own surface: the cis point lies half a cisterna's thickness inside it.
  const cisGap = um(pieces[0].cis.distanceTo(c.clone().setY(pieces[0].cis.y)) + pieces[0].thickness / 2 - env.style.nucleusRadius);
  const widest = um(Math.max(...pieces[0].widths));
  const buds = pieces.reduce((sum, piece) => sum + piece.buds.length, 0);
  const said = ribbon
    ? `A ribbon of ${ribbon.count} stacks of ${g.count} cisternae, each about ${widest} µm wide, along the nucleus beside its centrosome; the cis face of each, bowed toward the nucleus, about ${cisGap} µm from the envelope, with ${buds} vesicles budding from the rims.`
    : `A stack of ${g.count} cisternae about ${widest} µm wide beside the nucleus and its centrosome, the cis face bowed toward the nucleus about ${cisGap} µm from the envelope, with ${buds} vesicles budding from the rims, enlarged.`;
  return { ...made, centrosome, said: [["Drawn", `${said} In an animal cell the Golgi lies beside the nucleus, by the centrosome. Its size, number and place here are the picture's choice, since the species' file gives none.`]] };
}

/** A plant cell's Golgi: many small stacks in the thin cytoplasm by the membrane. The first stands by the nucleus, where carriers from the ER reach it. */
function dispersed(env, random, depth, um) {
  const { real, frame, style } = env;
  const count = real ? 40 : 14, scale = real ? 0.38 : 0.4, apart = real ? 1.2 : 2.4;
  const c = env.nucleusAt, places = [];
  if (c) {
    // Beside the nucleus, along the wall on the side the ER does not wrap (the ER lies on its inner side).
    const inward = Math.atan2(-c.z, -c.x), along = inward - Math.PI / 2;
    for (let step = 0; step < 12 && !places.length; step++) {
      const at = c.clone().addScaledVector(radial(along), style.nucleusRadius + (0.6 + step * 0.25) * scale * 2 + (depth * scale) / 2);
      if (env.inCytoplasm(at, 0.1, 0.1)) places.push({ at, facing: along });
    }
  }
  const wide = frame.equator.widest;
  for (let guard = 0; places.length < count && guard < count * 600; guard++) {
    const at = new THREE.Vector3((random() * 2 - 1) * wide, frame.base + random() * (env.cut - frame.base), (random() * 2 - 1) * wide);
    if (!env.inCytoplasm(at, 0.3, 0.25) || places.some((other) => other.at.distanceTo(at) < apart)) continue;
    places.push({ at, facing: Math.atan2(at.z, at.x) + (random() - 0.5) * 1.2 }); // lying along the wall, more or less
  }
  const pieces = places.map(({ at, facing }) => stackPieces(env, random, { at, facing, scale, y: at.y, lean: true }));
  const made = drawStacks(env, pieces, places[0].at);
  const across = um(Math.max(...pieces[0].widths));
  return { ...made, said: [["Drawn", `${pieces.length} small stacks, each about ${across} µm across${real ? "" : ", enlarged"}, spread through the thin cytoplasm by the membrane: a plant cell's Golgi is many separate stacks, with no ribbon and no centrosome. Their number and size are the picture's choice, since the species' file gives none.`]] };
}

/**
 * One stack's pieces, to be drawn with the others (drawStacks): its curved cisternae as walls
 * (the one nearest the nucleus, the cis face, bowed toward it), their swollen rims, and the
 * vesicles budding from the rims of the far (trans) side. `scale` makes a smaller stack;
 * `lean` draws it with fewer facets, for a stack that is a few pixels across.
 */
function stackPieces(env, random, { at, facing, scale = 1, y = null, lean = false }) {
  const { real } = env;
  const base = env.style.golgi;
  const g = scale === 1 ? base : { ...base, inner: base.inner * scale, gap: base.gap * scale, half: base.half * scale };
  const height = (real ? 0.42 : 0.95) * scale, thickness = g.half * (real ? 1.6 : 1.9);
  y ??= env.cut + height * 0.36;
  // The middle of each cisterna's curve lies on the far side, toward the membrane: the cis face bows toward the nucleus.
  const hub = at.clone().addScaledVector(radial(facing), g.inner + g.gap * 2);
  const widths = CISTERNAE[real ? "real" : "schematic"].slice(0, g.count).map((width) => width * scale);
  const sacs = [], rims = [], buds = [];
  widths.forEach((width, index) => {
    const radius = g.inner + (g.count - 1 - index) * g.gap; // the first (cis) is the farthest from the hub
    const half = width / 2 / radius, middle = facing + Math.PI;
    const points = Array.from({ length: lean ? 7 : 17 }, (_, step, all) => hub.clone().addScaledVector(radial(middle - half + (2 * half * step) / (lean ? 6 : 16)), radius).setY(0));
    const sac = wallAlong(points, thickness, height, false, lean ? { segments: 10, around: 6 } : {});
    sac.translate(0, y, 0);
    sacs.push({ geometry: sac, level: index });
    for (const end of [-1, 1]) {
      const angle = middle + end * half;
      const tip = hub.clone().addScaledVector(radial(angle), radius).setY(y);
      rims.push({ position: tip, scale });
      // Vesicles bud from the rims, more of them toward the trans face.
      if (index >= g.count - 3 && random() < 0.85) {
        const out = radial(angle + end * Math.PI / 2);
        buds.push({ position: tip.clone().addScaledVector(out, thickness * 0.95).setY(y + (random() - 0.4) * height * 0.5), scale: scale * (0.8 + random() * 0.4) });
      }
    }
    // And from the top edge of the trans cisternae.
    if (index >= g.count - 2) {
      for (let bud = 0; bud < 2; bud++) {
        const angle = middle + (random() * 2 - 1) * half * 0.7;
        buds.push({ position: hub.clone().addScaledVector(radial(angle), radius).setY(y + height * 0.5 + thickness * 0.35), scale: scale * (0.75 + random() * 0.3) });
      }
    }
  });
  // What a click on the stack reaches.
  const far = g.inner + g.count * g.gap;
  const body = new THREE.CylinderGeometry(far * 0.7, far * 0.7, height, lean ? 8 : 16).translate(at.x, y, at.z);
  const cis = hub.clone().addScaledVector(radial(facing + Math.PI), g.inner + (g.count - 1) * g.gap + thickness).setY(y);
  const trans = hub.clone().addScaledVector(radial(facing + Math.PI), g.inner - thickness).setY(y);
  return { sacs, rims, buds, body, cis, trans, facing, thickness, widths, scale, lean };
}

/** Stacks drawn as one: each level of cisterna one mesh for every stack, the rims and the buds one instanced mesh each, one body to click. */
function drawStacks(env, pieces, anchorAt) {
  const { ctx, real } = env;
  const first = pieces[0], scale = first.scale, lean = first.lean;
  const golgi = ctx.part("golgi", anchorAt.clone().setY(first.cis.y).add(new THREE.Vector3(0, (real ? 0.5 : 0.95) * Math.max(scale, 0.5), 0)));
  golgi.priority = 53;
  const levels = Math.max(...pieces.flatMap((piece) => piece.sacs.map((sac) => sac.level))) + 1;
  for (let level = 0; level < levels; level++) {
    const geometry = merged(pieces.flatMap((piece) => piece.sacs.filter((sac) => sac.level === level).map((sac) => sac.geometry)));
    golgi.add(new THREE.Mesh(geometry, golgi.material({ hue: "bioGolgi", shade: 0.22 - level * 0.1, roughness: 0.38, side: THREE.DoubleSide, thin: 0.7, texture: "grain" })));
  }
  const height = (real ? 0.42 : 0.95), thickness = env.style.golgi.half * (real ? 1.6 : 1.9);
  const rimMaterial = golgi.material({ hue: "bioGolgi", shade: 0.05, roughness: 0.35, thin: 0.6 });
  golgi.add(env.instanced(new THREE.CapsuleGeometry(thickness * 0.64, height * 0.62, lean ? 1 : 6, lean ? 5 : 12), rimMaterial, pieces.flatMap((piece) => piece.rims)));
  golgi.add(env.instanced(new THREE.SphereGeometry(thickness * 0.62, lean ? 6 : 14, lean ? 4 : 10), golgi.material({ hue: "bioGolgi", shade: 0.12, roughness: 0.3, thin: 0.6 }), pieces.flatMap((piece) => piece.buds)));
  golgi.add(new THREE.Mesh(merged(pieces.map((piece) => piece.body)), golgi.proxyMaterial()));
  return { cis: first.cis, trans: first.trans, facing: first.facing, thickness: first.thickness, stacks: pieces.length };
}

/**
 * An animal cell's centrosome, where its Golgi gathers beside the nucleus: two centrioles, short
 * barrels of nine rods at right angles, in a faint cloud. Scenery: Cells models no centrosome, so
 * it is neutral glass with no status, and its panel says so. Its size is the picture's choice.
 */
function drawCentrosome(env, facing) {
  const { ctx, real, frame } = env;
  const at = env.centrosomeAt;
  const length = real ? 0.5 : 0.9, radius = real ? 0.1 : 0.19, rod = real ? 0.018 : 0.034;
  // The first barrel stands upright; the second lies across it, along the nucleus.
  const across = radial(facing + Math.PI / 2);
  const barrels = [
    { centre: at.clone(), axis: new THREE.Vector3(0, 1, 0) },
    { centre: at.clone().addScaledVector(across, radius * 2.4).setY(at.y - length * 0.25), axis: across.clone() },
  ];
  const rods = [];
  for (const { centre, axis } of barrels) {
    const side = new THREE.Vector3().crossVectors(axis, Math.abs(axis.y) > 0.9 ? new THREE.Vector3(1, 0, 0) : UP).normalize(), other = new THREE.Vector3().crossVectors(axis, side);
    for (let index = 0; index < 9; index++) {
      const angle = (index / 9) * Math.PI * 2;
      rods.push({ position: centre.clone().addScaledVector(side, Math.cos(angle) * radius).addScaledVector(other, Math.sin(angle) * radius), direction: axis });
    }
  }
  const group = new THREE.Group();
  group.add(env.instanced(new THREE.CylinderGeometry(rod, rod, length, 6), ctx.neutral({ opacity: 0.9, glass: 0.2, depthWrite: true }), rods));
  // A faint cloud round both, which is also what a click on it reaches.
  const cloud = new THREE.Mesh(new THREE.SphereGeometry(length * 0.95, 20, 14), ctx.neutral({ opacity: 0.12, glass: 0.45 }));
  cloud.position.copy(at).addScaledVector(across, radius * 1.2);
  group.add(cloud);
  ctx.scenery(group, "scenery:centrosome");
  const um = (units) => Number((units * frame.u).toPrecision(2)).toLocaleString("en-US");
  return {
    id: "scenery:centrosome", kind: "centrosome", label: "Centrosome", facts: {}, sources: [], drawn: 1, of: 1,
    sizes: [
      ["What it is", "The cell's centre for organising its microtubules: two centrioles, short barrels at right angles, in a cloud of protein. In an animal cell the Golgi gathers round it, beside the nucleus. A plant cell has none."],
      ["Drawn", `Two barrels of nine rods, each ${um(length)} µm long and ${um(radius * 2)} µm across${real ? "" : ", enlarged"}, between the nucleus and the Golgi: the picture's choice. Nothing in the engine stands behind it.`],
    ],
  };
}

/** The point of the ER's sheets nearest a place (the Golgi's cis face): where carriers for the Golgi leave the ER. Null without an ER. */
function erNearest(env, place) {
  const er = env.erSheets;
  if (!er) return null;
  const c = er.centre, toward = Math.atan2(place.z - c.z, place.x - c.x);
  let best = null;
  for (const one of er.sheets) {
    const low = Math.min(one.from, one.to), high = Math.max(one.from, one.to);
    // The angle of the sheet nearest the place's own, the long way round included.
    const near = [toward - Math.PI * 2, toward, toward + Math.PI * 2].map((angle) => Math.min(high, Math.max(low, angle))).sort((a, b) => Math.abs(a - toward) - Math.abs(b - toward))[0];
    const point = c.clone().addScaledVector(radial(near), one.radius).setY(er.y);
    if (!best || point.distanceTo(place) < best.distanceTo(place)) best = point;
  }
  return best;
}

/** The vesicles that would carry proteins from the ER to the Golgi and on to the membrane: membrane trafficking. */
function carriers(env, random, golgi) {
  const { ctx, real, outline } = env;
  const spot = Math.atan2(golgi.trans.z, golgi.trans.x); // where on the outline the trans face looks
  const towardMembrane = outline.point(spot, real ? -0.35 : -0.75, golgi.trans.y);
  const path = new THREE.CatmullRomCurve3([golgi.trans.clone(), golgi.trans.clone().lerp(towardMembrane, 0.5).add(new THREE.Vector3(0, 0.1, 0)), towardMembrane]);
  const part = ctx.part("vesicles", path.getPoint(0.8).add(new THREE.Vector3(0, real ? 0.3 : 0.5, 0)));
  part.priority = 45; // where names clash, the Golgi's own is kept and this one gives way
  const size = golgi.thickness * (real ? 0.55 : 0.62);
  const out = [0.18, 0.4, 0.62, 0.84].map((t) => ({ position: path.getPoint(t), scale: 0.9 + random() * 0.3 }));
  const from = erNearest(env, golgi.cis) || golgi.cis.clone().addScaledVector(radial(golgi.facing + Math.PI), 1);
  const into = [0.25, 0.5, 0.75].map((t) => ({ position: from.clone().lerp(golgi.cis, t).add(new THREE.Vector3(0, Math.sin(Math.PI * t) * 0.15, 0)), scale: 0.65 + random() * 0.2 }));
  const glass = part.material({ hue: "bioGolgi", shade: 0.4, roughness: 0.25, opacity: 0.9, thin: 0.6 });
  part.add(env.instanced(new THREE.SphereGeometry(size, 16, 12), glass, [...out, ...into]));
  // One meets the membrane, half merged with it.
  const fusing = new THREE.Mesh(new THREE.SphereGeometry(size * 1.1, 18, 12, 0, Math.PI * 2, 0, Math.PI / 2), glass);
  fusing.position.copy(outline.point(spot, -size * 0.6, golgi.trans.y));
  fusing.quaternion.copy(along(outline.normal(spot).negate()));
  part.add(fusing);
  return [["Drawn", `${out.length + into.length + 1} vesicles: three on their way from the endoplasmic reticulum to the Golgi, four from the Golgi to the membrane, and one that meets it. Their number and size are the picture's choice.`]];
}

/**
 * A free chromosome drawn to scale (a cell whose molecules are shapes at its stop): DNA is 2 nm
 * across and 0.34 nm a base pair (textbook figures), so the file's length in base pairs would fill
 * the cut face of a small cell more than once over (Syn3A's 1.8 times). It is drawn as an electron
 * tomogram shows it: only in the slab under the cut, as short pieces of a fine line, the share of
 * its length that the slab holds of the region it fills in the middle of the cell. Where that
 * region lies and how the line winds are the picture's choice. A body that draws nothing, where
 * the schematic thread's is, takes a click as before.
 */
function chromosomeInSlab(env, random, thread) {
  const { frame, parts, nm, slab, cut } = env;
  const { at: coreAt, radius: coreRadius, reach: coreReach } = env.core;
  const slim = frame.outline.apothem;
  // The region it fills: a body round the cell's middle, as long as the schematic thread reaches and 0.7 of the cell's half-width across.
  const across = slim * 0.7, length = Math.max(coreReach, across), centre = new THREE.Vector3(coreAt.x, 0, 0);
  const inRegion = (point) => ((point.x - centre.x) / length) ** 2 + (point.y / across) ** 2 + (point.z / across) ** 2 < 1 && env.inside(point) > 4 * nm;
  const low = cut - slab, mid = cut - slab / 2;
  const share = mid < across ? 0.75 * (1 - (mid / across) ** 2) * (slab / across) : 0; // the slab's share of the region
  const whole = parts.chromosome_kbp * 1000 * 0.34 * nm, wanted = whole * share; // in the cell's units
  const step = 4 * nm, lines = [];
  let drawn = 0;
  for (let guard = 0; drawn < wanted && guard < 20000; guard++) {
    // A piece: where the chain crosses the slab, a short way, before it leaves it.
    const at = new THREE.Vector3(centre.x + (random() * 2 - 1) * length, low + random() * slab, (random() * 2 - 1) * across);
    if (!inRegion(at)) continue;
    const heading = new THREE.Vector3(random() - 0.5, (random() - 0.5) * 0.3, random() - 0.5).normalize();
    const steps = 5 + Math.floor(random() * 25);
    for (let index = 0; index < steps && drawn < wanted; index++) {
      heading.add(new THREE.Vector3(random() - 0.5, (random() - 0.5) * 0.3, random() - 0.5).multiplyScalar(0.8)).normalize();
      const next = at.clone().addScaledVector(heading, step);
      if (next.y < low || next.y > cut || !inRegion(next)) break;
      lines.push(at.x, at.y, at.z, next.x, next.y, next.z);
      drawn += step;
      at.copy(next);
    }
  }
  const strands = new THREE.BufferGeometry();
  strands.setAttribute("position", new THREE.Float32BufferAttribute(lines, 3));
  const line = new THREE.LineSegments(strands, thread.lineMaterial({ hue: "bioNucleus", opacity: 0.95 }));
  line.userData.unpickable = true; // a line is picked from far round it: the body below takes the click
  thread.add(line);
  const reach = new THREE.Mesh(new THREE.SphereGeometry(coreRadius * 0.92, 20, 14), thread.proxyMaterial());
  reach.position.copy(coreAt);
  reach.scale.set(coreReach / coreRadius, 1, 1);
  thread.add(reach);
  const um = (units) => Number((units * frame.u).toPrecision(units * frame.u >= 100 ? 3 : 2)).toLocaleString("en-US");
  const said = [["Drawn", `A fine line, in a slab ${Math.round(slab / nm)} nm deep under the cut, as an electron tomogram shows a cell: ${um(drawn)} µm of the ${um(whole)} µm its ${parts.chromosome_kbp.toLocaleString("en-US")} kbp would make as DNA, at 0.34 nm a base pair, 2 nm across (textbook figures). That is the share the slab holds of the region the chromosome fills in the middle of the cell; drawn whole, it would cover most of the cut face. Where that region lies and how the line winds are the picture's choice.`]];
  return { knots: [], said, drawn: drawn * frame.u, whole: whole * frame.u };
}

/**
 * Ribosomes: free in the cytoplasm, several in a string on one messenger, and on the rough
 * ER. Where the species' file gives a count, that many are drawn of the part of the cell
 * kept below the cut; else the number is the picture's choice. To scale in a large cell they
 * are dots. With no capability in the scene they are neutral scenery, as they were.
 */
function ribosomes(env, random, built, bound) {
  const { ctx, real, frame, parts } = env;
  const given = parts.ribosomes;
  const own = bound ? ctx.part("ribosomes", null) : null;
  if (own) own.priority = 52;
  const tone = (shade) => (own ? own.material({ hue: "bioRibosome", shade, roughness: 0.42, drift: 0.06 }) : ctx.neutral({ opacity: 0.6, glass: 0.35, depthWrite: false, drift: 0.06 }));
  const drawShapes = (placements, radius, shade = 0, light = false) => {
    if (!placements.length) return;
    const { large, small } = subunits(radius, light);
    const add = (object) => (own ? own.add(object) : ctx.illustrate(object));
    add(env.instanced(large, tone(shade), placements));
    add(env.instanced(small, tone(shade + 0.38), placements));
  };
  const scatterIn = (count, test, bounds) => {
    const found = [];
    for (let guard = 0; found.length < count && guard < count * 80; guard++) {
      const point = new THREE.Vector3((random() * 2 - 1) * bounds.wide, bounds.low + random() * (bounds.high - bounds.low), (random() * 2 - 1) * bounds.wide);
      if (test(point)) found.push(point);
    }
    return found;
  };
  const wide = frame.equator.widest;
  // A string of ribosomes on a messenger: a loose helix, its thread drawn through them.
  const strings = [];
  const polysome = (centre, count, radius) => {
    const axis = new THREE.Vector3(random() - 0.5, (random() - 0.5) * 0.6, random() - 0.5).normalize();
    const side = new THREE.Vector3().crossVectors(axis, UP).normalize(), other = new THREE.Vector3().crossVectors(axis, side);
    const knots = [], placements = [];
    for (let index = 0; index < count; index++) {
      const t = index - (count - 1) / 2, turn = t * 1.05;
      const at = centre.clone().addScaledVector(axis, t * radius * 1.55).addScaledVector(side, Math.cos(turn) * radius * 1.7).addScaledVector(other, Math.sin(turn) * radius * 1.7);
      placements.push({ position: at, turn: along(at.clone().sub(centre).sub(axis.clone().multiplyScalar(t * radius * 1.55))) });
      knots.push(at.clone().addScaledVector(at.clone().sub(centre).normalize(), -radius * 0.5));
    }
    const ends = [knots[0].clone().addScaledVector(axis, -radius * 2), ...knots, knots.at(-1).clone().addScaledVector(axis, radius * 2)];
    strings.push(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(ends), ends.length * 6, radius * 0.16, 5, false));
    return placements;
  };
  let free = [], onStrings = [], radius, polysomes = 0, anchor = null;
  if (given && !parts.nucleus) {
    // A small cell whose file counts them: each about 20 nm across, a shape of its own at this size.
    // No cap in the cell's units: in a cell as thin as 0.2 µm a cap drew them at half that size.
    radius = Math.max(0.085, 0.01 / frame.u);
    const total = Math.round(given * 0.6); // those of the part kept below the cut; the cut takes the rest away with the top of the cell
    const strung = Math.round((total * 0.15) / 5) * 5;
    // Each wholly below the cut: a ribosome reaches about 1.3 times its radius up from its middle, a string of five about four times.
    const below = (point, clear, rise) => env.inside(point) > clear && point.y < env.cut - rise * radius;
    const centres = scatterIn(strung / 5, (point) => below(point, radius * 5 + 0.3, 4), { wide, low: frame.base, high: env.cut });
    for (const centre of centres) onStrings.push(...polysome(centre, 5, radius));
    polysomes = centres.length;
    free = scatterIn(total - onStrings.length, (point) => below(point, radius + 0.25, 1.3), { wide, low: frame.base, high: env.cut }).map((position) => ({ position, turn: turned(random), scale: 0.85 + random() * 0.3 }));
    drawShapes([...free, ...onStrings], radius * 0.95, 0, true);
    anchor = (centres[0] || free[0]?.position || env.core.at).clone();
  } else if (!real) {
    // A large cell, parts enlarged: a few hundred, the number the picture's choice.
    radius = 0.08;
    const near = (point) => env.inCytoplasm(point, 0.45) && point.y > env.cut - 2.4 && point.y < env.cut - 0.05;
    free = scatterIn(130, near, { wide, low: env.cut - 2.4, high: env.cut }).map((position) => ({ position, turn: turned(random), scale: 0.85 + random() * 0.3 }));
    const centres = scatterIn(9, (point) => env.inCytoplasm(point, 1.2) && point.y > env.cut - 1.2 && point.y < env.cut - 0.35, { wide, low: env.cut - 1.2, high: env.cut });
    for (const centre of centres) onStrings.push(...polysome(centre, 7, radius));
    polysomes = centres.length;
    const studs = built.studs.map((stud) => ({ position: stud.position, direction: stud.direction, scale: 0.85 }));
    drawShapes([...free, ...onStrings, ...studs], radius);
    anchor = centres.reduce((best, point) => (!best || point.y > best.y ? point : best), null)?.clone() || null;
  } else {
    // To scale in a large cell a ribosome is about 25 nm: dots, free and on the rough ER.
    const dust = own ? own.points({ hue: "bioRibosome", size: 1.1, opacity: 0.4, drift: 0.1 }) : ctx.neutralPoints({ size: 1.1, opacity: 0.35, drift: 0.1 });
    free = scatterIn(6000, (point) => env.inCytoplasm(point), { wide, low: frame.base, high: env.cut + 0.2 }).map((position) => ({ position }));
    const studDots = own ? own.points({ hue: "bioRibosome", shade: -0.15, size: 1.3, opacity: 0.8 }) : ctx.neutralPoints({ size: 1.3, opacity: 0.8 });
    const add = (object) => (own ? own.add(object) : ctx.illustrate(object));
    add(env.dots(free.map((item) => item.position), dust));
    if (built.studs.length) add(env.dots(built.studs.map((stud) => stud.position), studDots));
    anchor = free.reduce((best, item) => (!best || item.position.y > best.y ? item.position : best), null)?.clone() || null;
  }
  if (strings.length) {
    const thread = own ? own.material({ hue: "bioRibosome", shade: -0.35, roughness: 0.5 }) : ctx.neutral({ opacity: 0.5, glass: 0.3 });
    const messenger = new THREE.Mesh(merged(strings), thread);
    if (own) own.add(messenger);
    else ctx.illustrate(messenger);
  }
  if (!own) return null;
  own.anchor = (anchor || env.nucleusAt || env.core.at).clone().add(new THREE.Vector3(0, real ? 0.5 : 0.9, 0));
  const studs = built.studs.length;
  const count = free.length + onStrings.length;
  if (given && !parts.nucleus) {
    return [["Drawn", `${count.toLocaleString("en-US")} of the ${given.toLocaleString("en-US")} the species' file gives: those in the part of the cell kept below the cut, ${onStrings.length} of them in ${polysomes} strings on a messenger. Each is drawn about 20 nm across, as two subunits: a textbook size and the picture's choice, since the species' file gives none.`]];
  }
  const where = studs ? ` and ${studs.toLocaleString("en-US")} on the rough endoplasmic reticulum` : "";
  if (real) return [["Drawn", `${count.toLocaleString("en-US")} dots free in the cytoplasm${where}: the picture's choice. A cell of this size holds millions; the species' file gives no count.`]];
  return [["Drawn", `${count.toLocaleString("en-US")} free, ${onStrings.length} of them in ${polysomes} strings on a messenger${where}, enlarged as every small part is here: the picture's choice, since the species' file gives no count.`]];
}
