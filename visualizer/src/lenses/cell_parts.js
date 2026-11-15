// Geometry for the cell lens. Every shape built here is either bound to a capability
// from the scene file (through ctx.part) or is neutral illustration (ctx.neutral).
// Nothing is drawn that looks like a capability without being one.
//
// Some materials ask for part of the resting look (core/look.js): `thin` lets a little light
// through a part's thin edges, `texture` gives a surface its grain, folds or pores, `shimmer`
// marks the membrane, and `drift` lets a crowd jostle about its places. All four are
// scenery: no data stands behind a fold, a pore or a jostle, and none is drawn where the
// look is plain.
//
// A new kind of scenery (an appendage, say) is built here as the wall and the vesicles are:
// with ctx.neutral(...) where no capability stands behind it, with ctx.part(name) and its
// material(...) where one does. A solid shape (opaque, or nearly) takes part in contact shade
// by itself; `contact: false` keeps it out, which suits what is thin or cut open. A crowd of
// copies may ask for `drift`. What moves with a direction is not scenery: see animate() in cell.js.
//
// Nothing here belongs to one species. A cell's shape, what it holds and which
// capabilities have a place in it come from the species shown (schema/SPECIES.md,
// schema/SPECIES_SHAPES.md). The cell is built in a frame of its own (shapes.js), in which
// it is always about as wide as the reference cell this layout was drawn for; the lens
// scales the whole to the size the species gives. In that frame 1 is one micrometre for a
// cell about 20 µm across.
//
// A cell that has neighbours (a species with a tissue level) is drawn as one cell of a
// layer: its neighbours stand round it, and under the layer lies a thin plate. Those, and
// the outline of the part cut away, are scenery.
// Two size modes share one layout:
//   schematic  parts enlarged and few, so each can be seen (like a textbook cutaway);
//   real       sizes and numbers nearer a real cell; what is too small to see at this
//              zoom is drawn as dots, and appears as shapes when the camera comes close.
// A cell under 2 µm across is drawn in the first mode only: at that size its molecules
// are large enough to see, so the picture is already near scale.

import * as THREE from "../three.js";
import { REF, cellFrame } from "./shapes.js";

// The layer's packing in the frame: six-sided, this far from a cell's centre to a corner.
export const HEX = { radius: REF.radius };
export const R = 10; // about half the cell's width
export const CUT = REF.cut; // the cell is opened by one flat cut at this height
const LATTICE = HEX.radius * Math.sqrt(3); // from one cell's centre to the next
const SIXTH = Math.PI / 3, TWELFTH = Math.PI / 6;

/** A small repeatable random source, so the cell looks the same on every load. */
export function seeded(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function unit(random) {
  const z = random() * 2 - 1, angle = random() * Math.PI * 2, r = Math.sqrt(1 - z * z);
  return new THREE.Vector3(r * Math.cos(angle), z, r * Math.sin(angle));
}

const UP = new THREE.Vector3(0, 1, 0);
const along = (direction) => new THREE.Quaternion().setFromUnitVectors(UP, direction.clone().normalize());
const radial = (angle) => new THREE.Vector3(Math.cos(angle), 0, Math.sin(angle));
const turnY = (angle) => new THREE.Quaternion().setFromAxisAngle(UP, angle);

/** Many copies of one shape, each at a position, turned by a quaternion or along a direction. */
function instanced(geometry, material, placements) {
  const mesh = new THREE.InstancedMesh(geometry, material, placements.length);
  const matrix = new THREE.Matrix4(), scale = new THREE.Vector3(), none = new THREE.Quaternion();
  placements.forEach((placement, index) => {
    scale.setScalar(placement.scale ?? 1);
    matrix.compose(placement.position, placement.turn ?? (placement.direction ? along(placement.direction) : none), scale);
    mesh.setMatrixAt(index, matrix);
  });
  mesh.instanceMatrix.needsUpdate = true;
  return mesh;
}

/** Dots: how things too small to draw as shapes are shown. */
function dots(points, material) {
  const geometry = new THREE.BufferGeometry();
  const flat = new Float32Array(points.length * 3);
  points.forEach((point, index) => point.toArray(flat, index * 3));
  geometry.setAttribute("position", new THREE.BufferAttribute(flat, 3));
  return new THREE.Points(geometry, material);
}

/** A flat ring-shaped arc standing as a wall: radius, arc length, thickness and height. */
function arcWall(radius, start, span, thickness, height) {
  const geometry = new THREE.TorusGeometry(radius, thickness / 2, 8, Math.max(24, Math.round(span * 26)), span);
  geometry.scale(1, 1, height / thickness);
  const mesh = new THREE.Mesh(geometry);
  // Lay the arc flat (its plane becomes horizontal), then turn it to its start angle.
  mesh.quaternion.copy(turnY(-start)).multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), Math.PI / 2));
  return mesh;
}

/** A flat shape filling a closed loop of points that lie level, facing up. */
function fan(points) {
  const centre = points.reduce((sum, point) => sum.add(point), new THREE.Vector3()).multiplyScalar(1 / points.length);
  const geometry = new THREE.BufferGeometry().setFromPoints([centre, ...points]);
  const index = [];
  for (let q = 0; q < points.length; q++) index.push(0, 1 + ((q + 1) % points.length), 1 + q);
  geometry.setIndex(index);
  geometry.setAttribute("normal", new THREE.Float32BufferAttribute(new Array(points.length + 1).fill([0, 1, 0]).flat(), 3));
  return geometry;
}

/** A flat band between two closed loops of as many points, facing up. */
function band(inner, outer) {
  const count = inner.length;
  const geometry = new THREE.BufferGeometry().setFromPoints([...inner, ...outer]);
  const index = [];
  for (let q = 0; q < count; q++) {
    const next = (q + 1) % count;
    index.push(q, next, count + q, next, count + next, count + q);
  }
  geometry.setIndex(index);
  geometry.setAttribute("normal", new THREE.Float32BufferAttribute(new Array(count * 2).fill([0, 1, 0]).flat(), 3));
  return geometry;
}

/** Picks random places on a surface, evenly by area: each a position and the way the surface faces there. */
function surfaceSampler(geometry) {
  const position = geometry.attributes.position, normal = geometry.attributes.normal, index = geometry.index;
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
  const upTo = [];
  let total = 0;
  for (let start = 0; start < index.count; start += 3) {
    a.fromBufferAttribute(position, index.getX(start));
    b.fromBufferAttribute(position, index.getX(start + 1)).sub(a);
    c.fromBufferAttribute(position, index.getX(start + 2)).sub(a);
    total += b.cross(c).length() / 2;
    upTo.push(total);
  }
  const blend = (attribute, start, u, v) =>
    a.fromBufferAttribute(attribute, index.getX(start)).multiplyScalar(1 - u - v).addScaledVector(b.fromBufferAttribute(attribute, index.getX(start + 1)), u).addScaledVector(c.fromBufferAttribute(attribute, index.getX(start + 2)), v).clone();
  return (random) => {
    const pick = random() * total;
    let low = 0, high = upTo.length - 1;
    while (low < high) {
      const middle = (low + high) >> 1;
      if (upTo[middle] < pick) low = middle + 1;
      else high = middle;
    }
    let u = random(), v = random();
    if (u + v > 1) [u, v] = [1 - u, 1 - v];
    return { position: blend(position, low * 3, u, v), direction: blend(normal, low * 3, u, v).normalize() };
  };
}

// ------------------------------------------------------------------ layout shared by both modes

// Where things sit on the cut edge, as angles round the cell's centre. The sides face the six
// neighbours, at 0, 60, 120 degrees and so on. Between them are the corners, where three cells
// meet and the space between cells is widest: what enters or leaves the cell is drawn there.
const SPOT = {
  channels: [0.3, 1.3, 2.1, 3.45, 4.5, 5.25],
  pumps: [1.02, 2.42, 4.95],
  junction: 0, // the middle of the side that faces the first neighbour
  water: [(5 * Math.PI) / 6, (7 * Math.PI) / 6],
  wound: Math.PI / 2,
  secretion: Math.PI / 6,
  furrow: 2.32,
  charges: [2.9, 3.25, 3.95, 4.25],
};
// The cell's neighbours in the layer, as turns round the cell from the junction: six, a sixth of a turn apart.
const NEIGHBOUR_TURNS = [0, 1, 2, 3, 4, 5].map((step) => step * SIXTH);
const GAP_CORNER = (3 * Math.PI) / 2; // the corner at which the space between cells is named
const NUCLEUS = new THREE.Vector3(2.6, CUT - 0.3, -2.2);
const ER_FACING = 2.42; // the side of the nucleus the ER wraps, as an angle
const GOLGI = new THREE.Vector3(-4.9, CUT + 0.15, 4.3);
const MACHINE = new THREE.Vector3(-7.2, CUT + 0.9, -1.0);
const MITO_AT_SURFACE = [[-4.7, -4.5, 0.5, 2.5], [6.9, 0.9, 1.45, 2.1], [1.9, 6.1, -0.35, 2.7]]; // x, z, turn, and how far it keeps from the cell's sides
const CAGES_AT_SURFACE = [new THREE.Vector3(4.9, CUT + 0.55, 3.9), new THREE.Vector3(-1.4, CUT + 0.5, -7.0)];

const STYLE = {
  schematic: {
    id: "schematic",
    shellOpacity: 0.44, band: 0.5, beads: true,
    nucleusRadius: 3.1, nucleolus: 1.05,
    er: { layers: 4, first: 3.95, gap: 0.72, thickness: 0.22, height: 1.35, span: 3.0, shrink: 0.42 },
    golgi: { inner: 1.5, gap: 0.36, count: 5, half: 0.14, tube: 0.035, span: 1.7 },
    drop: 0.19, bead: 0.2, wound: 0.5, dash: 0.12, charge: 0.8, neighbourGap: 0.9, floor: 0.45,
  },
  real: {
    id: "real",
    shellOpacity: 0.3, band: 0.06, beads: false,
    nucleusRadius: 3.0, nucleolus: 0.8,
    er: { layers: 8, first: 3.3, gap: 0.3, thickness: 0.07, height: 0.6, span: 3.3, shrink: 0.3 },
    golgi: { inner: 0.75, gap: 0.14, count: 6, half: 0.05, tube: 0.014, span: 1.5 },
    drop: 0.055, bead: 0.06, wound: 0.25, dash: 0.05, charge: 0.45, neighbourGap: 0.04, floor: 0.12,
  },
};

// The lipid heads along the cut edge: their spacing, a whole number of them round the outline.
const beadStep = (outline) => outline.length / Math.round(outline.length / 0.43);

/**
 * Builds one cell in the given size mode, from what the species says of it:
 *   cell.shape       its shape (schema/SPECIES_SHAPES.md)
 *   cell.parts       what it holds: a nucleus, organelles, a free chromosome, ribosomes
 *   cell.has(part)   whether the capability drawn at that part has a place in this cell
 *   cell.neighbours  whether it stands in a layer, with neighbours round it
 *   cell.notes       what the picture says in words beside it
 * Returns handles the lens animates, the points the input check clicks, and the cell's frame.
 */
export function buildCell(ctx, studsCtx, mode, cell) {
  const style = STYLE[mode];
  const real = mode === "real";
  const frame = cellFrame(cell.shape, cell.neighbours ? style.neighbourGap : 0);
  const outline = frame.outline; // the cell's outline where the cut passes through it
  const { top: TOP, base: BASE, bevel: BEVEL } = frame;
  const { has, parts } = cell;
  const organelle = (name) => (parts.organelles ? parts.organelles.includes(name) : Boolean(parts.nucleus));
  const random = seeded(real ? 23 : 7);
  const handles = { cages: [], frame, streams: [], signals: [], signalPath: () => new THREE.Vector3() };
  const inCut = (point) => point.y > (CUT + 0.01) * frame.u; // a point of the world, above the cut
  // How far inside the cell a point is: from its sides, its base and its outer face.
  const inside = frame.inside;
  const inCytoplasm = (point, clear = 0.6, wall = 1.1) => inside(point) > wall && point.y < CUT + 0.2 && (!parts.nucleus || point.distanceTo(NUCLEUS) > style.nucleusRadius + clear);
  const widest = frame.equator.widest;
  const scatter = (count, test = inCytoplasm) => {
    const found = [];
    let guard = 0;
    while (found.length < count && guard++ < count * 60) {
      const point = new THREE.Vector3((random() * 2 - 1) * widest, BASE + random() * (CUT + 0.2 - BASE), (random() * 2 - 1) * widest);
      if (test(point)) found.push(point);
    }
    return found;
  };
  // The layout is shared by both modes: a spot too near a side is moved toward the middle until it is clear.
  const seat = (point, margin) => {
    const seated = point.clone();
    for (let tries = 0; tries < 60 && outline.depth(seated.x, seated.z) < margin; tries++) seated.set(seated.x * 0.99, seated.y, seated.z * 0.99);
    return seated;
  };
  const prism = frame.solid();
  const skinAt = surfaceSampler(prism);
  const junction = cell.neighbours && has("junctions"); // a junction needs a neighbour to lead to
  const junctionAt = outline.point(SPOT.junction, 0, 0);
  const onSkin = (count, minGap = 0) => {
    // Random spots on the sides and the base, below the cut and clear of the junction.
    const found = [];
    let guard = 0;
    while (found.length < count && guard++ < count * 80) {
      const spot = skinAt(random);
      if (spot.position.y > CUT - 0.9) continue;
      if (junction && spot.position.distanceTo(junctionAt) < 2.8) continue;
      if (minGap && found.some((other) => other.position.distanceTo(spot.position) < minGap)) continue;
      found.push(spot);
    }
    return found;
  };

  // ---------------------------------------------------------------- membrane
  const membrane = ctx.part("membrane", outline.point(4.42, 0.9, CUT + 0.3));
  const shell = new THREE.Mesh(
    prism,
    membrane.material({ hue: "bioMembrane", opacity: style.shellOpacity, side: THREE.DoubleSide, clip: true, roughness: 0.25, depthWrite: false, rim: 0.5, alphaRim: 0.5, shimmer: true })
  );
  shell.userData.pickFilter = (hit) => !inCut(hit.point);
  shell.renderOrder = 6; // after what is inside it, so it tints them like glass
  membrane.add(shell);
  // The cut edge: the membrane seen in section. Schematic: a thick band with lipid beads.
  const edgeLine = () => new THREE.BufferGeometry().setFromPoints(outline.ring(0, CUT + 0.0002, 16));
  const edgeBand = () => band(outline.ring(-style.band * 0.72, CUT + 0.004, 16), outline.ring(style.band * 0.28, CUT + 0.004, 16));
  if (real) membrane.add(new THREE.LineLoop(edgeLine(), membrane.lineMaterial({ hue: "bioMembrane", opacity: 1 })));
  else membrane.add(new THREE.Mesh(edgeBand(), membrane.material({ hue: "bioMembrane", shade: -0.22, side: THREE.DoubleSide, roughness: 0.5 })));
  // What stands in the cut edge, each as an angle and half the stretch of edge it takes.
  const taken = [...[...(has("channels") ? SPOT.channels : []), ...(has("pumps") ? SPOT.pumps : []), ...(has("wound") ? [SPOT.wound] : [])].map((angle) => [angle, 0.74]), ...(junction ? [[SPOT.junction, 1.3]] : [])];
  if (style.beads) {
    // Counted from the channel of the close-up, so its lipid tails meet their heads.
    const heads = [];
    const step = beadStep(outline), first = outline.reach(SPOT.channels[1]);
    for (let index = 0; index < Math.round(outline.length / step); index++) {
      const s = first + index * step;
      if (taken.some(([angle, stretch]) => outline.apart(s, outline.reach(angle)) < stretch)) continue;
      heads.push({ position: outline.spot(s, 0.15, CUT + 0.06) }, { position: outline.spot(s + 0.2, -0.33, CUT + 0.06) });
    }
    membrane.add(instanced(new THREE.SphereGeometry(0.2, 12, 9), membrane.material({ hue: "bioMembrane", shade: 0.22, roughness: 0.3 }), heads));
  }
  // Charge across the membrane: plus outside, in the cleft between the cells, and minus inside.
  for (const angle of SPOT.charges) {
    studsCtx.sprite(membrane, "+", outline.point(angle, real ? 0.35 : 0.6, CUT + 0.3), style.charge);
    studsCtx.sprite(membrane, "−", outline.point(angle, real ? -0.5 : -1.15, CUT + 0.3), style.charge);
  }
  // A wall, or a second membrane, lies outside the cell membrane: scenery, drawn as clear shells.
  const shells = [...(parts.membranes === 2 ? [1.035] : []), ...(parts.wall ? [parts.membranes === 2 ? 1.075 : 1.045] : [])];
  for (const grow of shells) {
    const outer = new THREE.Mesh(prism, ctx.neutral({ opacity: 0.1, glass: 0.35, clip: true, side: THREE.DoubleSide }));
    outer.scale.setScalar(grow);
    outer.renderOrder = 7;
    ctx.illustrate(outer);
    const rim = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(outline.ring(0, CUT + 0.0002, 16)), ctx.neutralLine({ opacity: 0.55 }));
    rim.scale.set(grow, 1, grow);
    ctx.illustrate(rim);
  }

  // ---------------------------------------------------------------- channels and pumps
  const channels = has("channels") ? ctx.part("channels", outline.point(SPOT.channels[3], 0.5, CUT + 0.5)) : null;
  const pumps = has("pumps") ? ctx.part("pumps", outline.point(SPOT.pumps[1], 0.5, CUT + 0.5)) : null;
  if (!real) {
    // Set in the cut edge: each channel is two walls with a pore between; each pump a lobed block.
    if (channels) {
      const wall = new THREE.CapsuleGeometry(0.17, 0.62, 6, 12).rotateZ(Math.PI / 2); // long axis along x
      const walls = [];
      for (const angle of SPOT.channels) {
        for (const offset of [-0.25, 0.25]) walls.push({ position: outline.walk(angle, offset, -0.1, CUT + 0.07), turn: turnY(-outline.facing(angle, offset)) });
      }
      channels.add(instanced(wall, channels.material({ hue: "bioProtein", roughness: 0.35, thin: 0.3 }), walls));
    }
    if (pumps) {
      const lobes = pumps.material({ hue: "bioPump", roughness: 0.35, thin: 0.35 });
      for (const angle of SPOT.pumps) {
        const outer = new THREE.Mesh(new THREE.SphereGeometry(0.46, 18, 14), lobes);
        outer.position.copy(outline.point(angle, -0.05, CUT + 0.08));
        outer.scale.set(1, 0.85, 1);
        const inner = new THREE.Mesh(new THREE.SphereGeometry(0.32, 16, 12), lobes);
        inner.position.copy(outline.point(angle, -0.62, CUT));
        pumps.add(outer, inner);
      }
    }
    // And over the rest of the membrane: pores and low domes.
    if (channels) {
      const exteriorChannels = studsCtx.part("channels");
      exteriorChannels.add(
        instanced(new THREE.TorusGeometry(0.3, 0.1, 8, 18).rotateX(Math.PI / 2), exteriorChannels.material({ hue: "bioProtein", roughness: 0.4 }), onSkin(30, 2.2))
      );
    }
    if (pumps) {
      const exteriorPumps = studsCtx.part("pumps");
      exteriorPumps.add(
        instanced(new THREE.SphereGeometry(0.44, 16, 12).scale(1, 0.6, 1), exteriorPumps.material({ hue: "bioPump", roughness: 0.4, thin: 0.35 }), onSkin(12, 4))
      );
    }
  } else {
    // At this scale a channel is about 10 nm across: far too small to see. Thousands of them
    // are drawn as dots; the close-up of the membrane shows them as shapes.
    if (channels) {
      const dust = studsCtx.part("channels");
      dust.add(dots(onSkin(4200).map((spot) => spot.position), dust.points({ hue: "bioProtein", size: 1.9 })));
    }
    if (pumps) {
      const pumpDust = studsCtx.part("pumps");
      pumpDust.add(dots(onSkin(2400).map((spot) => spot.position), pumpDust.points({ hue: "bioPump", size: 1.9 })));
    }
  }

  // ---------------------------------------------------------------- gap junctions and the neighbours
  // The cell is one of a layer, so its neighbours stand round it, side against side, six as
  // in a packed sheet and where the sheet's own cells stand. They are scenery: faint glass
  // that cannot be clicked, opened by the same cut. The one the junction leads to is drawn a
  // little stronger; the others are only a thin outline where the cut passes through them.
  const neighbours = cell.neighbours ? NEIGHBOUR_TURNS.map((turn) => radial(turn).multiplyScalar(LATTICE)) : [];
  const cells = [new THREE.Vector3(), ...neighbours]; // where the seven stand
  if (cell.neighbours) {
    const glass = ctx.neutral({ opacity: 0.03, glass: 0.12, clip: true, side: THREE.DoubleSide });
    const fainter = ctx.neutral({ opacity: 0.012, glass: 0.05, clip: true, side: THREE.DoubleSide });
    const neighbourLine = ctx.neutralLine({ opacity: real ? 0.6 : 0.5 });
    const fainterLine = ctx.neutralLine({ opacity: 0.3 });
    neighbours.forEach((at, index) => {
      const first = index === 0;
      const neighbour = new THREE.Mesh(prism, first ? glass : fainter);
      neighbour.position.copy(at);
      neighbour.renderOrder = 7;
      ctx.illustrate(neighbour);
      const edge = real || !first ? new THREE.LineLoop(edgeLine(), first ? neighbourLine : fainterLine) : new THREE.Mesh(edgeBand(), ctx.neutral({ opacity: 0.3, side: THREE.DoubleSide }));
      edge.position.copy(at);
      ctx.illustrate(edge);
    });
  }
  const junctions = junction ? ctx.part("junctions", outline.point(SPOT.junction, 0.6, CUT + 0.6)) : null;
  const toward = outline.normal(SPOT.junction);
  if (!junction) {
    // A cell on its own has no neighbour for a junction to lead to.
  } else if (!real) {
    // Two rows of channels bridging the cleft, half-way between the two membranes.
    const bridge = [];
    for (const drop of [0.02, -0.62]) {
      for (let index = -2; index <= 2; index++) bridge.push({ position: outline.walk(SPOT.junction, index * 0.46, style.neighbourGap / 2, CUT + drop), direction: toward });
    }
    junctions.add(instanced(new THREE.CylinderGeometry(0.19, 0.19, 1.55, 10), junctions.material({ hue: "bioProtein", shade: -0.08, roughness: 0.35 }), bridge));
  } else {
    // A plaque of some hundreds of channels where the two cells touch.
    const plaque = [];
    const centre = outline.point(SPOT.junction, style.neighbourGap / 2, 0.2), across = outline.tangent(SPOT.junction);
    for (let index = 0; index < 700; index++) {
      const r = 0.55 * Math.sqrt(random()), angle = random() * Math.PI * 2;
      plaque.push(centre.clone().addScaledVector(across, Math.cos(angle) * r).addScaledVector(UP, Math.sin(angle) * r));
    }
    junctions.add(dots(plaque, junctions.points({ hue: "bioProtein", size: 1.9 })));
  }

  // ---------------------------------------------------------------- the part cut away, and what the layer stands on
  // The cut takes away the cell's outer face. Its outline is kept as a faint dashed line, so the
  // cell's whole height shows. Under a layer lies a thin plate, where a skin's cells would
  // rest on a basement membrane, lined where each of the seven cells stands on it. Both are
  // scenery, like the neighbours.
  const dashes = ctx.neutralLine({ opacity: 0.5, dashed: true, dash: 0.45, gap: 0.32 });
  // On a round cell the outline runs half-way up the part cut away, where its surface has
  // turned through half a right angle; the body is as high as it is wide at each place.
  const onRound = (place, turn) => new THREE.Vector3(place.x - Math.cos(place.facing) * place.rho * (1 - Math.cos(turn)), place.rho * Math.sin(turn), place.z - Math.sin(place.facing) * place.rho * (1 - Math.cos(turn)));
  const lid = frame.round ? frame.equator.samples(10, 6).map((place) => onRound(place, Math.PI / 4)) : frame.equator.ring(-BEVEL * 0.3, TOP - BEVEL * 0.3, 10, 6);
  const cutAway = [[...lid, lid[0]]];
  for (const angle of frame.equator.corners) {
    if (frame.round) {
      // A round cell has no edges: the lines follow its surface from just above the cut up to the outline.
      const place = frame.equator.at(frame.equator.reach(angle)), from = Math.asin(Math.min(1, (CUT + 0.3) / place.rho));
      if (from < Math.PI / 4) cutAway.push(Array.from({ length: 9 }, (_, step) => onRound(place, from + ((Math.PI / 4 - from) * step) / 8)));
    } else {
      // Up each upright edge, and over the rounded edge to the face.
      cutAway.push([outline.point(angle, 0, CUT + 0.3), outline.point(angle, 0, TOP - BEVEL), outline.point(angle, -BEVEL * 0.3, TOP - BEVEL * 0.3)]);
    }
  }
  for (const points of cutAway) {
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), dashes);
    line.computeLineDistances();
    ctx.illustrate(line);
  }
  if (cell.neighbours) {
    // The plate reaches as far as the seven cells do: its edge follows their outer corners.
    const under = BASE - style.floor;
    const cornerOf = (at, corner) => radial(TWELFTH + corner * SIXTH).multiplyScalar(HEX.radius).add(at).setY(under);
    const footing = neighbours.flatMap((at, index) => [-1, 0, 1].map((corner) => cornerOf(at, index + corner)));
    ctx.illustrate(new THREE.Mesh(fan(footing), ctx.neutral({ opacity: 0.05, side: THREE.DoubleSide })));
    const tiles = [], lined = new Set();
    for (const at of cells) {
      for (let corner = 0; corner < 6; corner++) {
        const a = cornerOf(at, corner), b = cornerOf(at, corner + 1);
        const key = [a, b].map((point) => `${point.x.toFixed(1)},${point.z.toFixed(1)}`).sort().join("|");
        if (lined.has(key)) continue;
        lined.add(key);
        tiles.push(a, b);
      }
    }
    ctx.illustrate(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(tiles), ctx.neutralLine({ opacity: 0.34 })));
  }

  // ---------------------------------------------------------------- cytoplasm
  const chemistry = ctx.part("cytoplasm", outline.point(Math.atan2(-7.4, -3.9), -1.45, CUT + 0.15));
  const gel = new THREE.Mesh(
    fan(outline.ring(real ? -0.003 : -style.band * 0.72, real ? CUT - 0.0006 : CUT - 0.02, 16)),
    chemistry.material({ hue: "bioCyto", opacity: real ? 0.42 : 0.3, side: THREE.DoubleSide, roughness: 0.12, depthWrite: false, rim: 0 })
  );
  gel.renderOrder = 3;
  chemistry.add(gel);
  if (!real) {
    const specks = instanced(new THREE.SphereGeometry(0.09, 8, 6), chemistry.material({ hue: "bioCyto", shade: -0.3, drift: 0.09 }), scatter(190).map((position) => ({ position, scale: 0.6 + random() * 0.9 })));
    const tone = new THREE.Color();
    for (let index = 0; index < specks.count; index++) specks.setColorAt(index, tone.setHSL(random(), 0.5, 0.72));
    specks.instanceColor.needsUpdate = true;
    chemistry.add(specks);
  } else {
    chemistry.add(dots(scatter(7000), chemistry.points({ hue: "bioCyto", shade: -0.35, size: 1.3, opacity: 0.5, drift: 0.1 })));
  }
  // Vesicles: scenery, so neutral glass. They belong to a cell with inner membranes.
  if (parts.nucleus) {
    const bubbles = real
      ? scatter(80, (point) => inCytoplasm(point, 0.8)).map((position) => ({ position, scale: 0.12 + random() * 0.22 }))
      : [[-5.9, 1.5], [0.4, 8.0], [7.4, -3.4], [-2.6, -4.4], [4.3, 6.9], [-7.6, -3.6]].map(([x, z]) => ({ position: seat(new THREE.Vector3(x, CUT + 0.05, z), 1.75), scale: 0.45 + random() * 0.3 }));
    ctx.illustrate(instanced(new THREE.SphereGeometry(1, 20, 14), ctx.neutral({ opacity: 0.14, glass: 0.5 }), bubbles));
  }
  const cagesAt = CAGES_AT_SURFACE.map((point) => seat(point, 2.2)), machineAt = seat(MACHINE, 1.9);

  // ---------------------------------------------------------------- nucleus
  // The middle of what regulation acts on, and how far it reaches: the nucleus, or the free chromosome.
  const slim = outline.apothem; // half the cell's width across its narrow way, where the cut passes
  const coreAt = parts.nucleus ? NUCLEUS : new THREE.Vector3(frame.middle, CUT - slim * 0.46, 0), coreRadius = parts.nucleus ? style.nucleusRadius : slim * 0.42;
  // In a long cell the chromosome lies along it: how far it reaches each way from its middle.
  const coreReach = coreRadius + Math.max(0, frame.long / 2 - frame.equator.apothem) * 0.8;
  if (parts.nucleus) {
  const nucleus = ctx.part("nucleus", NUCLEUS.clone().add(new THREE.Vector3(0, style.nucleusRadius + 0.1, 0)));
  const envelope = new THREE.Mesh(new THREE.SphereGeometry(style.nucleusRadius, 56, 40), nucleus.material({ hue: "bioNucleus", opacity: 0.78, roughness: 0.3, rim: 0.55, depthWrite: true, thin: 0.9, texture: "pores" }));
  envelope.position.copy(NUCLEUS);
  envelope.renderOrder = 2;
  const nucleolus = new THREE.Mesh(new THREE.SphereGeometry(style.nucleolus, 28, 20), nucleus.material({ hue: "bioNucleus", shade: -0.38, roughness: 0.5, thin: 0.5 }));
  nucleolus.position.copy(NUCLEUS).add(new THREE.Vector3(0.55, 1.15, 0.85));
  nucleus.add(nucleolus, envelope);
  const pores = [];
  while (pores.length < (real ? 1500 : 80)) {
    const direction = unit(random);
    if (real || direction.y > -0.25) pores.push(NUCLEUS.clone().addScaledVector(direction, style.nucleusRadius + 0.01));
  }
  if (real) nucleus.add(dots(pores, nucleus.points({ hue: "bioNucleus", shade: 0.4, size: 1.4, opacity: 0.8 })));
  else nucleus.add(instanced(new THREE.SphereGeometry(0.085, 8, 6), nucleus.material({ hue: "bioNucleus", shade: 0.32 }), pores.map((position) => ({ position }))));
  } else if (parts.chromosome_kbp) {
    // A cell without a nucleus: its chromosome lies free in the cell, one closed thread.
    // Regulation acts there, so it is where the regulatory circuits are drawn. The thread
    // is a tangle through the cell's middle; its true length would fill the cell far more.
    const chromosome = ctx.part("nucleus", coreAt.clone().add(new THREE.Vector3(0, coreRadius + 0.3, 0)));
    const turns = Math.round(Math.min(900, Math.max(60, parts.chromosome_kbp / 2)));
    const knots = [];
    let at = coreAt.clone(), heading = unit(random);
    // In a long cell the thread runs to and fro along it, so that it lies through the whole length.
    const lengthwise = coreReach > coreRadius * 1.5 ? new THREE.Vector3(0.5, 0, 0) : null;
    for (let step = 0; step < turns; step++) {
      // Each step keeps most of its heading and is turned back when it would leave the middle of the cell.
      heading.add(unit(random).multiplyScalar(0.9));
      if (lengthwise) {
        if (Math.abs(at.x - coreAt.x) > coreReach * 0.86) lengthwise.x = at.x > coreAt.x ? -0.5 : 0.5;
        heading.add(lengthwise);
      }
      heading.normalize();
      const next = at.clone().addScaledVector(heading, coreRadius * 0.34);
      const away = next.clone().sub(coreAt);
      if (Math.hypot(away.x * (coreRadius / coreReach), away.y, away.z) > coreRadius || next.y > CUT - 0.15 || inside(next) < 0.9) {
        heading.addScaledVector(away.normalize(), -1.5).normalize();
        next.copy(at).addScaledVector(heading, coreRadius * 0.34);
      }
      knots.push(next);
      at = next;
    }
    const thread = new THREE.CatmullRomCurve3(knots, true, "catmullrom", 0.5);
    const strand = new THREE.Mesh(new THREE.TubeGeometry(thread, turns * 5, 0.075, 5, true), chromosome.material({ hue: "bioNucleus", roughness: 0.35, clip: true, thin: 0.5 }));
    strand.renderOrder = 2;
    chromosome.add(strand);
    const reach = new THREE.Mesh(new THREE.SphereGeometry(coreRadius * 0.92, 20, 14), chromosome.proxyMaterial());
    reach.position.copy(coreAt);
    reach.scale.set(coreReach / coreRadius, 1, 1);
    chromosome.add(reach);
  }

  // Gene regulation coupled to tissue is planned: a sketched network round the nucleus.
  if (has("genome")) {
  const genome = ctx.part("genome", coreAt.clone().add(new THREE.Vector3(coreRadius + 0.3, 1.5, 1.9)));
  const net = new THREE.IcosahedronGeometry(coreRadius + 0.6, 1);
  const cage = new THREE.LineSegments(new THREE.EdgesGeometry(net, 1), genome.lineMaterial({ opacity: 0.75 }));
  cage.position.copy(coreAt);
  const knots = [], seen = new Set(), corner = new THREE.Vector3();
  for (let index = 0; index < net.attributes.position.count; index++) {
    corner.fromBufferAttribute(net.attributes.position, index);
    const key = corner.toArray().map((value) => value.toFixed(2)).join();
    if (!seen.has(key)) {
      seen.add(key);
      knots.push({ position: corner.clone().add(coreAt) });
    }
  }
  const body = new THREE.Mesh(net, genome.proxyMaterial());
  body.position.copy(coreAt);
  genome.add(cage, body, instanced(new THREE.SphereGeometry(0.1, 8, 6), genome.material({ line: true }), knots));
  }

  // Free ribosomes, where the species gives a count: scenery, since protein synthesis is not a
  // capability. A ribosome is about 20 nm across, so in a small cell it is a shape of its own.
  if (parts.ribosomes) {
    const size = Math.min(0.46, Math.max(0.085, 0.01 / frame.u));
    // Only those below the cut are drawn: the cut takes the rest away with the top of the cell.
    const free = scatter(Math.round(parts.ribosomes * 0.6), (point) => inside(point) > size + 0.25 && point.y < CUT - size * 0.4);
    ctx.illustrate(instanced(new THREE.SphereGeometry(size, 10, 8), ctx.neutral({ opacity: 0.5, glass: 0.35, depthWrite: false, drift: 0.1 }), free.map((position) => ({ position, scale: 0.85 + random() * 0.3 }))));
  }

  // ---------------------------------------------------------------- endoplasmic reticulum, the calcium store
  if (organelle("er")) {
  const er = ctx.part("er", NUCLEUS.clone().addScaledVector(radial(ER_FACING), style.er.first + style.er.gap * 1.5).setY(CUT + style.er.height * 0.45));
  const sheet = er.material({ hue: "bioEr", roughness: 0.4, side: THREE.DoubleSide, thin: 0.8, texture: "grain" });
  const studs = [];
  for (let layer = 0; layer < style.er.layers; layer++) {
    const radius = style.er.first + layer * style.er.gap;
    const span = Math.max(0.9, style.er.span - layer * style.er.shrink);
    const start = ER_FACING - span / 2 + (layer % 2 ? 0.12 : -0.08);
    const wall = arcWall(radius, start, span, style.er.thickness, style.er.height);
    wall.material = sheet;
    wall.position.copy(NUCLEUS).setY(CUT - style.er.height * 0.12);
    er.add(wall);
    // Ribosomes on the sheets. Protein synthesis is not a capability, so they are scenery: neutral grey.
    const perLayer = real ? Math.round(span * radius * 22) : Math.round(span * radius * 1.7);
    for (let index = 0; index < perLayer; index++) {
      const angle = start + (span * (index + random() * 0.6)) / perLayer;
      const out = (random() < 0.5 ? 1 : -1) * (style.er.thickness / 2 + (real ? 0.012 : 0.07));
      studs.push(NUCLEUS.clone().addScaledVector(radial(angle), radius + out).setY(CUT - style.er.height * 0.12 + (random() - 0.5) * style.er.height * 0.9));
    }
  }
  if (real) {
    ctx.illustrate(dots(studs, ctx.neutralPoints({ size: 1.3, opacity: 0.8 })));
    // The network reaches through the cell as tubules; free ribosomes (scenery) fill the cytosol.
    const tubes = [];
    for (let strand = 0; strand < 70; strand++) {
      const point = NUCLEUS.clone().addScaledVector(unit(random), style.nucleusRadius + 0.4 + random() * 2.5);
      const heading = unit(random);
      for (let step = 0; step < 14; step++) {
        const next = point.clone().addScaledVector(heading.add(unit(random).multiplyScalar(0.55)).normalize(), 0.42);
        if (!inCytoplasm(next, 0.2)) break;
        tubes.push(point.x, point.y, point.z, next.x, next.y, next.z);
        point.copy(next);
      }
    }
    const web = new THREE.BufferGeometry();
    web.setAttribute("position", new THREE.Float32BufferAttribute(tubes, 3));
    er.add(new THREE.LineSegments(web, er.lineMaterial({ hue: "bioEr", opacity: 0.55 })));
    ctx.illustrate(dots(scatter(6000), ctx.neutralPoints({ size: 1.1, opacity: 0.35, drift: 0.1 })));
  } else {
    ctx.illustrate(instanced(new THREE.SphereGeometry(0.085, 8, 6), ctx.neutral({ opacity: 0.8, depthWrite: true }), studs.map((position) => ({ position }))));
  }
  }

  // ---------------------------------------------------------------- Golgi and trafficking: planned, so sketched as outlines
  if (organelle("golgi")) {
  const golgi = ctx.part("golgi", GOLGI.clone().add(new THREE.Vector3(0, 0.7, 0)));
  const sketch = golgi.material({ line: true });
  const facing = Math.atan2(GOLGI.z - NUCLEUS.z, GOLGI.x - NUCLEUS.x);
  const hub = GOLGI.clone().addScaledVector(radial(facing), -(style.golgi.inner + style.golgi.gap * 2));
  for (let index = 0; index < style.golgi.count; index++) {
    const radius = style.golgi.inner + index * style.golgi.gap;
    const span = style.golgi.span - index * 0.1;
    const points = [];
    for (let step = 0; step <= 14; step++) points.push(hub.clone().addScaledVector(radial(facing - span / 2 + (span * step) / 14), radius + style.golgi.half));
    for (let step = 14; step >= 0; step--) points.push(hub.clone().addScaledVector(radial(facing - span / 2 + (span * step) / 14), radius - style.golgi.half));
    golgi.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points, true, "catmullrom", 0.25), 110, style.golgi.tube, 6, true), sketch));
  }
  const far = style.golgi.inner + style.golgi.count * style.golgi.gap;
  for (const [turn, reach] of [[-0.5, 1.5], [0.05, 1.8], [0.55, 1.45], [0.2, 2.6]]) {
    const vesicle = new THREE.Mesh(new THREE.TorusGeometry(style.golgi.half * 1.5, style.golgi.tube, 6, 22), sketch);
    vesicle.position.copy(hub).addScaledVector(radial(facing + turn), far + reach * style.golgi.gap);
    vesicle.rotation.x = Math.PI / 2;
    golgi.add(vesicle);
  }
  const golgiBody = new THREE.Mesh(new THREE.CylinderGeometry(far * 0.75, far * 0.75, 0.5, 16), golgi.proxyMaterial());
  golgiBody.position.copy(GOLGI);
  golgi.add(golgiBody);
  }

  // ---------------------------------------------------------------- mitochondria and fuel
  if (!organelle("mitochondria")) {
    // No mitochondria: the fuel is made in the cytoplasm, and is drawn through it near the cut.
    if (has("atp")) {
      const fuel = ctx.part("atp", seat(new THREE.Vector3(-0.9, CUT + 0.55, 7.4), 1.3));
      const sparks = scatter(real ? 400 : 30, (point) => inside(point) > 0.9 && point.y < CUT + 0.2 && point.y > CUT - 1.4 && point.distanceTo(coreAt) > coreRadius * 0.5);
      fuel.add(instanced(new THREE.SphereGeometry(0.17, 12, 9), fuel.material({ hue: "bioFuel", emissive: 0.22, roughness: 0.3 }), sparks.map((position) => ({ position, scale: 0.8 + random() * 0.5 }))));
    }
  } else {
  const lying = MITO_AT_SURFACE.map(([x, z, turn, margin]) => ({ at: seat(new THREE.Vector3(x, CUT - 0.12, z), margin), turn }));
  const mitochondria = ctx.part("mitochondria", lying[1].at.clone().setY(CUT + 0.75));
  const fuel = ctx.part("atp", new THREE.Vector3(-0.9, CUT + 0.55, 7.4));
  if (!real) {
    // The shell of one cut open stays out of contact shade: the gap between its wall and the
    // floor laid in it would go dark like a pit, where the approved picture has a bright rim.
    // The folds drawn on the ones left whole are shown here as the shelves themselves.
    const outer = mitochondria.material({ hue: "bioMito", clip: true, side: THREE.DoubleSide, roughness: 0.35, thin: 0.7, contact: false });
    const matrix = mitochondria.material({ hue: "bioMito", shade: 0.5, roughness: 0.5 });
    const crista = mitochondria.material({ hue: "bioMito", shade: -0.05, roughness: 0.45 });
    const stadium = new THREE.Shape();
    stadium.absarc(1.0, 0, 0.8, -Math.PI / 2, Math.PI / 2, false);
    stadium.absarc(-1.0, 0, 0.8, Math.PI / 2, (3 * Math.PI) / 2, false);
    for (const { at, turn } of lying) {
      const one = new THREE.Group();
      one.add(new THREE.Mesh(new THREE.CapsuleGeometry(0.95, 2.0, 10, 24).rotateZ(Math.PI / 2), outer));
      const floor = new THREE.Mesh(new THREE.ShapeGeometry(stadium, 16).rotateX(-Math.PI / 2), matrix);
      floor.position.y = 0.1;
      one.add(floor);
      [-1.2, -0.6, 0, 0.6, 1.2].forEach((offset, index) => {
        const fold = new THREE.Mesh(new THREE.BoxGeometry(0.13, 0.34, 1.05), crista);
        fold.position.set(offset, 0.03, index % 2 ? 0.27 : -0.27);
        one.add(fold);
      });
      one.position.copy(at);
      one.rotation.y = turn;
      mitochondria.add(one);
    }
    const whole = mitochondria.material({ hue: "bioMito", roughness: 0.4, thin: 0.7, texture: "folds", axis: UP });
    const deep = [[-6.0, -3.0, 0.6], [0.6, -4.5, -3.4], [5.0, -3.75, 3.0], [-2.6, -4.9, 4.0], [-3.4, -2.1, -6.4], [6.4, -2.0, -4.6]];
    // Lying roughly level, like the ones at the surface.
    const level = () => radial(random() * Math.PI * 2).setY((random() - 0.5) * 0.5);
    mitochondria.add(instanced(new THREE.CapsuleGeometry(0.8, 1.8, 8, 20), whole, deep.map((xyz) => ({ position: seat(new THREE.Vector3(...xyz), 2.5), direction: level() }))));
    const sparks = [];
    for (const [x, z] of [...lying.map(({ at }) => [at.x, at.z]), [-0.9, 7.2]]) {
      for (let index = 0; index < 7; index++) {
        const angle = random() * Math.PI * 2, reach = 1.5 + random() * 0.9;
        const point = new THREE.Vector3(x + Math.cos(angle) * reach * 1.25, CUT + 0.12 + random() * 0.3, z + Math.sin(angle) * reach);
        if (outline.depth(point.x, point.z) > 1.1 && point.distanceTo(NUCLEUS) > style.nucleusRadius + 0.6) sparks.push({ position: point, scale: 0.8 + random() * 0.5 });
      }
    }
    fuel.add(instanced(new THREE.SphereGeometry(0.17, 12, 9), fuel.material({ hue: "bioFuel", emissive: 0.22, roughness: 0.3 }), sparks));
  } else {
    // Mitochondria are about 0.6 µm wide and a few µm long; a cell holds hundreds.
    const many = scatter(120, (point) => inCytoplasm(point, 0.7) && point.y < CUT);
    // Each is a clear outer membrane, curved more or less, with the folds of its inner
    // membrane (the cristae) showing through: stacked shelves across the long axis.
    const shapes = [
      { radius: 0.26, length: 1.1, bend: 0 },
      { radius: 0.3, length: 1.8, bend: 0.26 },
      { radius: 0.27, length: 2.7, bend: -0.42 },
    ];
    const curved = ({ radius, length, bend }) => {
      const geometry = new THREE.CapsuleGeometry(radius, length, 8, 18);
      const half = length / 2 + radius, spot = geometry.attributes.position;
      for (let index = 0; index < spot.count; index++) spot.setX(index, spot.getX(index) + bend * (spot.getY(index) / half) ** 2);
      geometry.computeVertexNormals();
      return geometry;
    };
    const outer = mitochondria.material({ hue: "bioMito", shade: 0.1, opacity: 0.3, alphaRim: 0.55, rim: 0.45, clip: true, side: THREE.DoubleSide, roughness: 0.3, depthWrite: false });
    // The shelves are thin and soft: a little light comes through them. The clear outer membrane stays glass.
    // They stand so close that contact shade between them turned each stack brown: they stay out of it.
    const fold = mitochondria.material({ hue: "bioMito", shade: -0.06, clip: true, roughness: 0.5, thin: 0.5, contact: false });
    const placed = shapes.map(() => []);
    for (const position of many) {
      const which = Math.floor(random() * shapes.length), scale = 0.85 + random() * 0.35;
      // Turned any way that keeps both its ends inside the cell and out of the nucleus.
      const reach = (shapes[which].length / 2) * scale;
      let direction = unit(random);
      for (let tries = 0; tries < 16; tries++) {
        if ([1, -1].every((end) => inCytoplasm(position.clone().addScaledVector(direction, end * reach), 0.35, 0.45))) break;
        direction = unit(random);
      }
      placed[which].push({ position, turn: along(direction), scale });
    }
    const folds = [];
    shapes.forEach((shape, which) => {
      const bodies = instanced(curved(shape), outer, placed[which]);
      bodies.renderOrder = 4; // after the folds, so they show through the membrane
      mitochondria.add(bodies);
      const half = shape.length / 2 + shape.radius;
      const count = Math.max(3, Math.round(shape.length / 0.3));
      for (const one of placed[which]) {
        const base = new THREE.Matrix4().compose(one.position, one.turn, new THREE.Vector3().setScalar(one.scale));
        for (let index = 0; index < count; index++) {
          const y = -shape.length / 2 + (shape.length * (index + 0.5)) / count;
          const side = index % 2 ? 1 : -1; // shelves reach in from alternate sides
          const at = new THREE.Vector3(shape.bend * (y / half) ** 2 + side * 0.16 * shape.radius, y, 0);
          const tilt = new THREE.Quaternion().setFromEuler(new THREE.Euler(0, 0, side * 0.14));
          folds.push(base.clone().multiply(new THREE.Matrix4().compose(at, tilt, new THREE.Vector3(shape.radius * 0.74, 1, shape.radius * 0.82))));
        }
      }
    });
    const shelves = new THREE.InstancedMesh(new THREE.CylinderGeometry(1, 1, 0.05, 14), fold, folds.length);
    folds.forEach((matrix, index) => shelves.setMatrixAt(index, matrix));
    shelves.instanceMatrix.needsUpdate = true;
    mitochondria.add(shelves);
    mitochondria.anchor.copy(many.reduce((best, point) => (point.y > best.y ? point : best), many[0])).y += 0.5;
    // ATP is a small molecule: shown as a haze, densest beside the mitochondria.
    const haze = [];
    for (let index = 0; index < 4500; index++) {
      const point = many[Math.floor(random() * many.length)].clone().addScaledVector(unit(random), 0.35 + random() * 0.9);
      if (inCytoplasm(point, 0.1)) haze.push(point);
    }
    fuel.add(dots(haze, fuel.points({ hue: "bioFuel", size: 1.3, opacity: 0.55 })));
    fuel.anchor.copy(mitochondria.anchor).add(new THREE.Vector3(1.2, 0, 1.2));
  }
  }

  // ---------------------------------------------------------------- protein cages (assembly) and larger machines (planned)
  const assembly = has("cage") ? ctx.part("cage", cagesAt[0].clone().add(new THREE.Vector3(0, 1.25, 0))) : null;
  const machine = has("machine") ? ctx.part("machine", machineAt.clone().add(new THREE.Vector3(0, 1.2, 0))) : null;
  if (!real) {
    if (assembly) {
    const corners = new THREE.DodecahedronGeometry(0.78).attributes.position, unique = new Map(), at = new THREE.Vector3();
    for (let index = 0; index < corners.count; index++) {
      at.fromBufferAttribute(corners, index);
      unique.set(at.toArray().map((value) => value.toFixed(2)).join(), at.clone());
    }
    const subunit = assembly.material({ hue: "bioProtein", shade: 0.12, roughness: 0.3 });
    const ball = new THREE.SphereGeometry(0.3, 14, 10);
    for (const centre of [...cagesAt, seat(new THREE.Vector3(-5.5, -3.0, -3.0), 2.2), seat(new THREE.Vector3(3.0, -4.6, 2.0), 2.2)]) {
      const cluster = instanced(ball, subunit, [...unique.values()].map((position) => ({ position })));
      cluster.position.copy(centre);
      handles.cages.push(cluster);
      assembly.add(cluster);
      // Free subunits beside it: the finite pool the cage is built from.
      assembly.add(instanced(ball, subunit, [0, 1, 2].map(() => ({ position: seat(centre.clone().add(new THREE.Vector3((random() - 0.5) * 3.2, random() * 0.25, (random() - 0.5) * 3.2)), 0.95) }))));
    }
    }
    if (machine) {
    const rings = machine.material({ line: true });
    for (let index = 0; index < 4; index++) {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(index % 3 ? 0.62 : 0.5, 0.035, 6, 30), rings);
      ring.position.copy(machineAt).add(new THREE.Vector3(0, (index - 1.5) * 0.36, 0));
      ring.rotation.x = Math.PI / 2;
      machine.add(ring);
    }
    const barrel = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.62, 1.4, 12), machine.proxyMaterial());
    barrel.position.copy(machineAt);
    machine.add(barrel);
    }
  } else {
    // A cage is tens of nanometres across: dots at this scale.
    if (assembly) assembly.add(dots(scatter(2200), assembly.points({ hue: "bioProtein", shade: 0.12, size: 1.7, opacity: 0.85 })));
    // Planned machines: a sketched ring marks where their dots would be.
    if (machine) {
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.7, 0.014, 6, 40), machine.material({ line: true }));
    ring.position.copy(machineAt).setY(CUT + 0.03);
    ring.rotation.x = Math.PI / 2;
    const spot = new THREE.Mesh(new THREE.CylinderGeometry(0.7, 0.7, 0.3, 16), machine.proxyMaterial());
    spot.position.copy(ring.position);
    const few = [];
    for (let index = 0; index < 140; index++) few.push(ring.position.clone().add(new THREE.Vector3((random() - 0.5) * 1.1, (random() - 0.6) * 0.5, (random() - 0.5) * 1.1)));
    machine.add(ring, spot, dots(few, machine.points({ size: 1.6, opacity: 0.8 })));
    machine.anchor.copy(ring.position).y += 0.4;
    }
    if (assembly) assembly.anchor.copy(cagesAt[0]).setY(CUT + 0.3);
  }

  // ---------------------------------------------------------------- water, wound, division, secretion
  // Water crosses the membrane at two corners, to and from the space between the cells.
  if (has("water")) {
    const water = ctx.part("water", outline.point(SPOT.water[0], 1.9, CUT + 0.4));
    const dropMaterial = water.material({ hue: "bioWater", roughness: 0.08, rim: 0.6 });
    const dropShape = new THREE.SphereGeometry(style.drop, 14, 10);
    handles.streams = SPOT.water.map((angle, which) => {
      const drops = Array.from({ length: real ? 9 : 5 }, () => new THREE.Mesh(dropShape, dropMaterial));
      drops.forEach((drop) => water.add(drop));
      return { inward: which === 0, drops, reach: real ? 0.7 : 1.6, at: (offset) => outline.point(angle, offset, CUT + 0.28) };
    });
  }

  if (has("wound")) {
  const wound = ctx.part("wound", outline.point(SPOT.wound, 1.5, CUT - 0.2));
  const woundAt = outline.point(SPOT.wound, 0.03, CUT - 0.9), woundOut = outline.normal(SPOT.wound), woundAcross = outline.tangent(SPOT.wound);
  const scar = new THREE.Mesh(new THREE.TorusGeometry(style.wound, style.wound * 0.17, 8, 28), wound.material({ hue: "bioWound", roughness: 0.4 }));
  scar.position.copy(woundAt);
  scar.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), woundOut);
  wound.add(scar);
  wound.add(
    instanced(
      new THREE.SphereGeometry(style.wound * 0.24, 8, 6),
      wound.material({ hue: "bioWound", shade: 0.25 }),
      [0.5, 1.1, 1.8, 2.5].map((reach, index) => ({ position: woundAt.clone().addScaledVector(woundOut, reach * style.wound * 2).addScaledVector(woundAcross, (index % 2 ? 0.5 : -0.4) * style.wound) }))
    )
  );
  }

  // The line along which the cell divides: down one side, under the base and up the other,
  // a little off the membrane.
  if (has("furrow")) {
  const furrow = ctx.part("furrow", outline.point(SPOT.furrow, 0.9, CUT + 0.2));
  const off = real ? 0.08 : 0.22;
  const leg = (angle) => {
    if (frame.round) {
      // A round cell: the line follows its surface from above the cut down to the point under its middle.
      const under = -frame.inside(new THREE.Vector3()) - off, points = [];
      for (let step = 0; step <= 28; step++) {
        const y = CUT + 0.6 + (under - CUT - 0.6) * Math.sin(((step / 28) * Math.PI) / 2);
        points.push(frame.skin(angle, y, off));
      }
      return points;
    }
    const out = radial(angle), points = [out.clone().multiplyScalar(outline.radius(angle, off)).setY(CUT + 0.6)];
    for (let step = 0; step <= 8; step++) {
      const t = (step / 8) * (Math.PI / 2); // round the edge of the base
      points.push(out.clone().multiplyScalar(outline.radius(angle, off * Math.cos(t) - BEVEL * (1 - Math.cos(t)))).setY(BASE + BEVEL * (1 - Math.sin(t)) - off * Math.sin(t)));
    }
    return points;
  };
  const line = [...leg(SPOT.furrow), ...leg(SPOT.furrow + Math.PI).reverse()];
  const pieces = [];
  let next = 0.35; // how far along the line the next dash is
  for (let index = 0; index + 1 < line.length; index++) {
    const length = line[index].distanceTo(line[index + 1]), direction = line[index + 1].clone().sub(line[index]).normalize();
    for (; next < length; next += 1.235) pieces.push({ position: line[index].clone().addScaledVector(direction, next), direction });
    next -= length;
  }
  furrow.add(instanced(new THREE.CylinderGeometry(style.dash, style.dash, 0.7, 6), furrow.material({ hue: "bioMembrane", shade: -0.42, clip: true }), pieces));
  // The same line continues a little way across the cut surface, at both ends.
  const mark = furrow.material({ hue: "bioMembrane", shade: -0.42 });
  for (const side of [0, Math.PI]) {
    for (let step = 0; step < 3; step++) {
      const piece = new THREE.Mesh(new THREE.BoxGeometry(0.5, style.dash, style.dash * 1.6), mark);
      piece.position.copy(radial(SPOT.furrow + side).multiplyScalar(outline.radius(SPOT.furrow + side) - 1.0 - step * 0.95).setY(CUT + 0.05));
      piece.rotation.y = -(SPOT.furrow + side);
      furrow.add(piece);
    }
  }
  }

  // Signals leave at a corner and drift up and away over the neighbours.
  if (has("secretion")) {
    const secretion = ctx.part("secretion", outline.point(SPOT.secretion, 4.6, CUT + 2.0));
    const drift = outline.tangent(SPOT.secretion);
    handles.signalPath = (t) => outline.point(SPOT.secretion, 0.3 + t * 5.5, CUT - 0.1).addScaledVector(UP, t * 0.8 + t * t * 1.6).addScaledVector(drift, t * t * 1.2);
    const signal = secretion.material({ hue: "bioSignal", roughness: 0.25 });
    handles.signals = Array.from({ length: real ? 24 : 9 }, () => new THREE.Mesh(new THREE.SphereGeometry(style.bead, 12, 9), signal));
    handles.signals.forEach((bead) => secretion.add(bead));
  }

  // ---------------------------------------------------------------- the space between cells
  // Packed cells leave little room between them: the narrow clefts between their flat sides,
  // and the gaps where three cells meet. The ions are drawn in those gaps from the cut down to
  // the base, and in the clefts only where the cut opens them, so the cell's sides stay clear.
  // To scale a cleft is 40 nm wide, so there the ions are a dotted line round the cut edge.
  // The name points into one of the gaps.
  if (has("extracellular") && !cell.neighbours) {
    // A cell on its own: what lies outside it is the medium all round, drawn as ions near the cut edge.
    const medium = ctx.part("extracellular", outline.point(GAP_CORNER, 2.1, CUT - 0.3));
    const around = [];
    for (let index = 0; index < 150; index++) around.push({ position: outline.spot(random() * outline.length, 0.7 + random() * 2.6, CUT + 0.05 - random() * 1.2), scale: 0.6 + random() * 0.7 });
    medium.add(instanced(new THREE.SphereGeometry(0.14, 8, 6), medium.material({ hue: "bioIon", opacity: 0.9 }), around));
  }
  if (has("extracellular") && cell.neighbours) {
  const clearOf = (point, clear) => cells.every((at) => outline.depth(point.x - at.x, point.z - at.z) < -clear);
  const gapAt = (angle) => radial(angle).multiplyScalar(HEX.radius); // where the cell and two of its neighbours meet
  const outside = ctx.part("extracellular", gapAt(GAP_CORNER).setY(CUT - 0.5));
  // Kept clear: what stands in the cut edge, the charges, and the stretch that the close-up of the membrane shows.
  const shown = [...taken, ...SPOT.charges.map((angle) => [angle, 0.6]), [SPOT.channels[1], 3.4]].map(([angle, stretch]) => [outline.reach(angle), stretch]);
  const between = (count, clear) => {
    const found = [];
    let guard = 0;
    while (found.length < count * (real ? 0.5 : 0.35) && guard++ < count * 200) {
      const corner = TWELFTH + Math.floor(random() * 6) * SIXTH;
      const down = (real ? random() ** 2 : random()) * (CUT + 0.1 - BASE - 0.6); // to scale, most are near the cut, where the gap is seen from above
      const point = gapAt(corner).addScaledVector(radial(random() * Math.PI * 2), (real ? 0.7 : 1.3) * Math.sqrt(random())).setY(CUT + 0.1 - down);
      if (Math.abs(corner - SPOT.wound) < 0.01 && point.y > CUT - 2.4) continue; // what leaves the wound is drawn there
      if (clearOf(point, clear)) found.push(point);
    }
    guard = 0;
    const nearest = real ? clear : 0.5; // the lipid heads along the cut edge are kept clear
    while (found.length < count && guard++ < count * 400) {
      const s = random() * outline.length;
      const point = outline.spot(s, nearest + random() * Math.max(0, style.neighbourGap - clear - nearest), CUT + 0.05 - random() * (real ? 0.35 : 1.1));
      if (!real && shown.some(([at, stretch]) => outline.apart(s, at) < stretch)) continue;
      if (clearOf(point, clear * 0.9)) found.push(point);
    }
    return found;
  };
  if (real) outside.add(dots(between(3200, 0.004), outside.points({ hue: "bioIon", shade: -0.3, size: 1.7, opacity: 0.9 })));
  else outside.add(instanced(new THREE.SphereGeometry(0.14, 8, 6), outside.material({ hue: "bioIon", opacity: 0.9 }), between(200, 0.2).map((position) => ({ position, scale: 0.6 + random() * 0.7 }))));
  }

  // What the picture says in words beside the cell (the lens writes them under the stop's name).
  // Short lines, so they stay clear of the names in the columns beside the cell.
  handles.notes = cell.notes || [];

  handles.probes = {
    // In the nucleus, or in the middle of the free chromosome where a cell has no nucleus.
    nucleus: parts.nucleus ? NUCLEUS.clone().add(new THREE.Vector3(-0.9, style.nucleusRadius * 0.9, 0.9)) : coreAt.clone().add(new THREE.Vector3(-coreRadius * 0.2, coreRadius * 0.85, coreRadius * 0.2)),
    cutGel: outline.point(Math.atan2(-7.6, -3.9), -1.7, CUT), // on the cut face of the cytoplasm, well inside the membrane's edge
    uncutSide: frame.skin(1.14, -2.5), // on the side that faces the viewer, below the cut
    sheetCell: new THREE.Vector3(73.4, 6.5, 31.8),
  };
  // The outline, for the lens: a point of it, and how far inside it a point is.
  handles.shape = { point: outline.point, depth: (point) => outline.depth(point.x, point.z) };
  return handles;
}

// ------------------------------------------------------------------ molecules

/**
 * The membrane seen close, at the channel on the near side of the cut edge.
 * Schematic: tails for the lipid beads and ions moving through the pore.
 * Real: the same stretch at true proportions (bilayer about 4.5 nm, channel about 9 nm).
 */
export function buildMolecules(ctx, mode, frame, has = () => true) {
  const outline = frame.outline;
  const NM = 0.001 / frame.u; // one nanometre, in the cell's frame
  // The close-up is of a channel; in a cell that has none, of a pump.
  const pored = has("channels");
  const angle = pored || !has("pumps") ? SPOT.channels[1] : SPOT.pumps[0];
  const patch = outline.point(angle);
  const outward = outline.normal(angle), sideways = outline.tangent(angle);
  const handles = { outward, centre: patch.clone(), pored, ions: [], ionPath: () => patch.clone() };
  const membrane = ctx.part("membrane");
  const channel = ctx.part("channels");
  const tails = [];
  if (mode === "schematic") {
    // The lipid heads along the cut edge are counted from the first channel's place, so each tail meets its head.
    const step = beadStep(outline), counted = outline.reach(SPOT.channels[1]);
    const here = counted + Math.round((outline.reach(angle) - counted) / step) * step;
    for (let index = -9; index <= 9; index++) {
      if (Math.abs(index) < 2) continue;
      // One tail for the head on the outer face of the membrane and one for the head on the inner.
      for (const [shift, from, to] of [[0, 0.15, -0.02], [0.2, -0.33, -0.16]]) {
        const a = outline.spot(here + index * step + shift, from, CUT + 0.06), b = outline.spot(here + index * step + shift, to, CUT + 0.06);
        tails.push(a.x, a.y, a.z, b.x, b.y, b.z);
      }
    }
    if (pored) {
      handles.ionPath = (t) => patch.clone().addScaledVector(outward, 1.3 - t * 2.7).setY(CUT + 0.12);
      handles.ions = Array.from({ length: 6 }, () => new THREE.Mesh(new THREE.SphereGeometry(0.06, 10, 8), channel.material({ hue: "bioIon", emissive: 0.25, roughness: 0.3 })));
    }
    handles.view = [5.4, 3.6];
  } else {
    // True proportions: lipid head groups under a nanometre across, in two leaflets 3.8 nm apart.
    const heads = [];
    for (let index = -70; index <= 70; index++) {
      const base = patch.clone().addScaledVector(sideways, index * 0.85 * NM).setY(CUT + 0.5 * NM);
      if (Math.abs(index * 0.85) < 5.2 || Math.abs(index * 0.85 - 24) < 6) continue; // the channel and the pump stand here
      for (const leaflet of [1.9, -1.9]) {
        const head = base.clone().addScaledVector(outward, leaflet * NM);
        const end = base.clone().addScaledVector(outward, leaflet * 0.12 * NM);
        heads.push({ position: head });
        tails.push(head.x, head.y, head.z, end.x, end.y, end.z);
      }
    }
    membrane.add(instanced(new THREE.SphereGeometry(0.4 * NM, 10, 8), membrane.material({ hue: "bioMembrane", shade: 0.22, roughness: 0.3 }), heads));
    // A channel: two walls about 3 nm thick and 10 nm long, with a pore between.
    const wall = new THREE.CapsuleGeometry(1.5 * NM, 7 * NM, 6, 12).rotateZ(Math.PI / 2);
    channel.add(
      instanced(wall, channel.material({ hue: "bioProtein", roughness: 0.35 }), [-2.2, 2.2].map((offset) => ({ position: patch.clone().addScaledVector(sideways, offset * NM).setY(CUT + 0.5 * NM), turn: turnY(-outline.facing(angle)) })))
    );
    // A pump beside it: larger, with most of its bulk on the cytoplasm side.
    const pump = ctx.part("pumps");
    const lobes = pump.material({ hue: "bioPump", roughness: 0.35 });
    for (const [inward, size] of [[0, 4.2], [5.5, 3.6], [-3.2, 2.6]]) {
      const lobe = new THREE.Mesh(new THREE.SphereGeometry(size * NM, 18, 14), lobes);
      lobe.position.copy(patch).addScaledVector(sideways, 24 * NM).addScaledVector(outward, -inward * NM).setY(CUT + 0.5 * NM);
      pump.add(lobe);
    }
    handles.ionPath = (t) => patch.clone().addScaledVector(outward, (11 - t * 22) * NM).setY(CUT + 0.9 * NM);
    handles.ions = Array.from({ length: 7 }, () => new THREE.Mesh(new THREE.SphereGeometry(0.22 * NM, 10, 8), channel.material({ hue: "bioIon", emissive: 0.25, roughness: 0.3 })));
    handles.view = [0.085 / frame.u, 0.056 / frame.u]; // 85 nm by 56 nm
    handles.fromInside = true;
  }
  handles.ions.forEach((ion) => channel.add(ion));
  const strands = new THREE.BufferGeometry();
  strands.setAttribute("position", new THREE.Float32BufferAttribute(tails, 3));
  ctx.illustrate(new THREE.LineSegments(strands, ctx.neutralLine({ opacity: 0.8, colour: "ghost" })));
  return handles;
}

// ------------------------------------------------------------------ tissue

/** Axial coordinates of a six-sided sheet: 127 cells for six rings. */
export function sheetCells(rings) {
  const cells = [];
  for (let q = -rings; q <= rings; q++) {
    for (let r = Math.max(-rings, -q - rings); r <= Math.min(rings, -q + rings); r++) cells.push({ q, r });
  }
  return cells;
}

export const hexCentre = ({ q, r }) => new THREE.Vector3(HEX.radius * Math.sqrt(3) * (q + r / 2), 0, HEX.radius * 1.5 * r);

/**
 * A sheet of the species' own cells, in the cell's frame: `rings` rings round the middle
 * cell, each cell `height` tall. `beyond` says how far the layer goes on as faint outlines,
 * as [ring, strength] pairs. The cells stand in a six-sided packing whatever the cell's shape.
 */
export function buildTissue(ctx, { rings, height, beyond, notes }) {
  const prism = new THREE.CylinderGeometry(HEX.radius * 0.955, HEX.radius * 0.955, height, 6);
  const cells = sheetCells(rings);
  const same = (a, b) => a.q === b.q && a.r === b.r;
  const within = (cell) => cells.some((item) => same(item, cell));
  // Which cells show replacement and mechanics: fixed places in a sheet large enough to hold them.
  const leaving = within({ q: 3, r: -1 }) ? { q: 3, r: -1 } : null, arriving = within({ q: -2, r: 3 }) ? { q: -2, r: 3 } : null;
  const inPatch = (cell) => rings >= 4 && cell.q + cell.r / 2 < -2.4 && cell.r < 0; // the mechanics patch
  const plain = cells.filter((cell) => !(leaving && same(cell, leaving)) && !(arriving && same(cell, arriving)) && !inPatch(cell));

  const sheet = ctx.part("sheet", new THREE.Vector3(40, height / 2 + 6, -58));
  const body = instanced(prism, sheet.material({ hue: "bioCell", roughness: 0.5 }), plain.map((cell) => ({ position: hexCentre(cell) })));
  const tone = seeded(11), shadeOf = new THREE.Color();
  plain.forEach((_, index) => body.setColorAt(index, shadeOf.setScalar(0.9 + tone() * 0.18)));
  body.instanceColor.needsUpdate = true;
  sheet.add(body);
  // The cell this lens opens on, marked so the zoom out keeps its place.
  const marker = new THREE.Mesh(new THREE.TorusGeometry(HEX.radius * 0.8, 0.5, 8, 6), ctx.neutral({ opacity: 0.9, colour: "fg" }));
  marker.rotation.set(Math.PI / 2, 0, Math.PI / 6);
  marker.position.y = height / 2 + 0.4;
  ctx.illustrate(marker);
  // Lines between neighbours: the junction network that couples the sheet.
  const links = [];
  for (const cell of cells) {
    for (const [dq, dr] of [[1, 0], [0, 1], [-1, 1]]) {
      const other = { q: cell.q + dq, r: cell.r + dr };
      if (!cells.some((item) => same(item, other))) continue;
      const a = hexCentre(cell), b = hexCentre(other);
      const y = height / 2 + 0.3;
      links.push(a.x * 0.6 + b.x * 0.4, y, a.z * 0.6 + b.z * 0.4, a.x * 0.4 + b.x * 0.6, y, a.z * 0.4 + b.z * 0.6);
    }
  }
  const linkGeometry = new THREE.BufferGeometry();
  linkGeometry.setAttribute("position", new THREE.Float32BufferAttribute(links, 3));
  ctx.illustrate(new THREE.LineSegments(linkGeometry, ctx.neutralLine({ opacity: 0.55, colour: "fg" })));

  // Replacement: one cell lifted out, one newcomer coming in.
  if (leaving && arriving) {
    const replacement = ctx.part("replacement", hexCentre(leaving).add(new THREE.Vector3(0, height * 2.1, 0)));
    const out = new THREE.Mesh(prism, replacement.material({ hue: "bioCell", opacity: 0.5, depthWrite: false }));
    out.position.copy(hexCentre(leaving)).y = height * 1.25;
    const incoming = new THREE.Mesh(prism, replacement.material({ hue: "bioCell", shade: 0.25 }));
    incoming.position.copy(hexCentre(arriving)).y = height * 0.55;
    replacement.add(out, incoming);
    for (const cell of [leaving, arriving]) {
      const centre = hexCentre(cell);
      const guide = new THREE.BufferGeometry().setFromPoints([centre.clone().setY(-height / 2), centre.clone().setY(height * 2.4)]);
      const line = new THREE.Line(guide, ctx.neutralLine({ opacity: 0.6, colour: "fg", dashed: true }));
      line.computeLineDistances();
      ctx.illustrate(line);
    }
  }

  // Mechanics: a patch drawn as its edges and vertices, the way the vertex model sees it.
  const corner = (cell, index) => {
    const angle = (Math.PI / 3) * index + Math.PI / 6;
    return hexCentre(cell).add(new THREE.Vector3(Math.cos(angle) * HEX.radius, height / 2 + 0.2, Math.sin(angle) * HEX.radius));
  };
  const patch = cells.filter(inPatch);
  if (patch.length) {
    const centreOfPatch = patch.reduce((sum, cell) => sum.add(hexCentre(cell)), new THREE.Vector3()).multiplyScalar(1 / patch.length);
    const mechanics = ctx.part("mechanics", centreOfPatch.clone().add(new THREE.Vector3(-8, height / 2 + 7, -10)));
    mechanics.add(instanced(prism, mechanics.material({ hue: "bioCell", opacity: 0.32, depthWrite: false }), patch.map((cell) => ({ position: hexCentre(cell) }))));
    const edgeMaterial = mechanics.material({ hue: "bioCell", shade: -0.3 });
    const seen = new Set();
    for (const cell of patch) {
      for (let index = 0; index < 6; index++) {
        const a = corner(cell, index), b = corner(cell, (index + 1) % 6);
        const key = [a, b].map((point) => `${point.x.toFixed(1)},${point.z.toFixed(1)}`).sort().join("|");
        if (seen.has(key)) continue;
        seen.add(key);
        const edge = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.42, a.distanceTo(b), 6), edgeMaterial);
        edge.position.copy(a).add(b).multiplyScalar(0.5);
        edge.quaternion.copy(along(b.clone().sub(a)));
        mechanics.add(edge);
        const knot = new THREE.Mesh(new THREE.SphereGeometry(0.85, 10, 8), edgeMaterial);
        knot.position.copy(a);
        mechanics.add(knot);
      }
    }
  }
  // The layer goes on beyond the sheet: more cells of the same size, drawn as outlines only
  // and fainter with distance. Scenery: it says the sheet is a patch of a larger layer.
  const ringOf = (cell) => Math.max(Math.abs(cell.q), Math.abs(cell.r), Math.abs(cell.q + cell.r));
  const drawn = new Set();
  let inner = rings;
  for (const [outer, opacity] of beyond || []) {
    const segments = [];
    for (const cell of sheetCells(outer)) {
      if (ringOf(cell) <= inner) continue;
      for (let index = 0; index < 6; index++) {
        const a = corner(cell, index), b = corner(cell, (index + 1) % 6);
        const key = [a, b].map((point) => `${point.x.toFixed(1)},${point.z.toFixed(1)}`).sort().join("|");
        if (drawn.has(key)) continue;
        drawn.add(key);
        segments.push(a, b);
      }
    }
    ctx.illustrate(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(segments), ctx.neutralLine({ opacity })));
    inner = outer;
  }

  // What the sheet stands for, in the species' words (the lens writes it under the stop's name).
  return { extent: HEX.radius * Math.sqrt(3) * (rings * 2 + 1), notes: notes || [] };
}

export { instanced };
