// The layout of one cell in one size mode: where its parts stand, how they find room, and the
// one stream of chance they draw from. The cell's builder (cell_parts.js, buildCell) makes it
// once and hands it to every part module (parts/index.js) in a fixed order, so the picture is
// the same on every load. Nothing here draws.
//
// What it holds, all in the cell's own frame (shapes.js, cellFrame):
//   the places    SPOT (angles on the cut edge), the homes of the nucleus, the ER, the Golgi,
//                 the machine, the mitochondria lying at the surface and the cages, and the
//                 sizes of each size mode (STYLE);
//   the tests     inside, inCut, inCytoplasm: how far inside the cell, or above the cut, a point
//                 is, and whether it lies free in the cytoplasm;
//   the finders   scatter (places free in the cytoplasm), seat (a home moved clear of the
//                 sides, or pressed against them beside a vacuole), onSkin (places on the
//                 cell's sides and base) and skinAt;
//   the claims    what more than one part reads: what stands in the cut edge (taken), whether
//                 a junction is drawn and where, the neighbours and how the layer is packed,
//                 where the cages and the machine stand, the middle of what regulation acts on
//                 (the nucleus, or the free chromosome: core), and the place on the uncut side
//                 that the click checks press and the scenery keeps clear of (uncutSide).
//
// The stream of chance is `random`, seeded by the size mode. Every part that draws from it
// draws in the builder's fixed order, so a part that moves, or draws once more or once less,
// moves every part after it (tests/cell_build.test.mjs holds that). Parts that must not move
// the others take a stream of their own, as the structures and the species' own scenery do.
// Making the layout draws nothing from it.

import * as THREE from "../three.js";
import { REF, cellFrame, packing } from "./shapes.js";
import { vacuoleOf } from "./cell_scenery.js";
import { seeded, radial, band, surfaceSampler } from "./parts/geometry.js";

export const CUT = REF.cut; // the cell is opened by one flat cut at this height
export const LATTICE = REF.radius * Math.sqrt(3); // from one cell's centre to the next

// Where things sit on the cut edge, as angles round the cell's centre. The sides face the six
// neighbours, at 0, 60, 120 degrees and so on. Between them are the corners, where three cells
// meet and the space between cells is widest: what enters or leaves the cell is drawn there.
export const SPOT = {
  channels: [0.3, 1.3, 2.1, 3.45, 4.5, 5.25],
  pumps: [1.02, 2.42, 4.95],
  junction: 0, // the middle of the side that faces the first neighbour
  water: [(5 * Math.PI) / 6, (7 * Math.PI) / 6],
  wound: Math.PI / 2,
  secretion: Math.PI / 6,
  furrow: 2.32,
  charges: [2.9, 3.25, 3.95, 4.25],
};
export const GAP_CORNER = (3 * Math.PI) / 2; // the corner at which the space between cells is named
// Where the nucleus, the ER beside it and the Golgi sit in a cell that has room for them in its
// middle. In a cell with a large vacuole each is pressed out to the side (makeLayout).
export const NUCLEUS_HOME = new THREE.Vector3(2.6, CUT, -2.2); // its middle at the cut, so that the wedge cut away from it starts at the cut face (cell_structures.js)
export const ER_HOME = 2.42; // the side of the nucleus the ER wraps, as an angle
export const GOLGI_HOME = new THREE.Vector3(-4.9, CUT + 0.15, 4.3);
export const MACHINE = new THREE.Vector3(-7.2, CUT + 0.9, -1.0);
export const MITO_AT_SURFACE = [[-4.7, -4.5, 0.5, 2.5], [6.9, 0.9, 1.45, 2.1], [1.9, 6.1, -0.35, 2.7]]; // x, z, turn, and how far it keeps from the cell's sides
export const CAGES_AT_SURFACE = [new THREE.Vector3(4.9, CUT + 0.55, 3.9), new THREE.Vector3(-1.4, CUT + 0.5, -7.0)];

export const STYLE = {
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
export const beadStep = (outline) => outline.length / Math.round(outline.length / 0.43);

/**
 * The layout of one cell in one size mode, from what the species says of it (buildCell's
 * `cell`: shape, parts, has, neighbours, notes). Returns the places, tests, finders and claims
 * set out above, the frame and its outline, and the stream of chance. Draws nothing, and takes
 * nothing from the stream.
 */
export function makeLayout(mode, cell) {
  const style = STYLE[mode];
  const real = mode === "real";
  const frame = cellFrame(cell.shape, cell.neighbours ? style.neighbourGap : 0);
  const outline = frame.outline; // the cell's outline where the cut passes through it
  const { top: TOP, base: BASE, bevel: BEVEL } = frame;
  const { has, parts } = cell;
  const organelle = (name) => (parts.organelles ? parts.organelles.includes(name) : Boolean(parts.nucleus));
  const random = seeded(real ? 23 : 7);
  const inCut = (point) => point.y > (CUT + 0.01) * frame.u; // a point of the world, above the cut
  // How far inside the cell a point is: from its sides, its base and its outer face.
  const inside = frame.inside;
  // A plant cell's vacuole takes up most of the cell: what else the cell holds lies between it and the membrane.
  const vacuole = vacuoleOf(frame, parts);
  const inCytoplasm = (point, clear = 0.6, wall = 1.1) =>
    vacuole
      ? inside(point) > Math.min(wall, vacuole.inset * 0.3) && point.y < CUT + 0.2 && !vacuole.holds(point) && (!parts.nucleus || point.distanceTo(NUCLEUS) > style.nucleusRadius + clear)
      : inside(point) > wall && point.y < CUT + 0.2 && (!parts.nucleus || point.distanceTo(NUCLEUS) > style.nucleusRadius + clear);
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
    // Beside a vacuole a part is pressed against the side: it moves out, the way it lies from the
    // middle, until it is as near the membrane as its own margin lets it. It then reaches into the vacuole.
    if (vacuole) {
      if (Math.hypot(seated.x, seated.z) < 0.5) seated.x += 0.5;
      for (let tries = 0; tries < 600 && outline.depth(seated.x, seated.z) > margin + 0.04; tries++) seated.set(seated.x * 1.01, seated.y, seated.z * 1.01);
    }
    return seated;
  };
  const NUCLEUS = vacuole ? seat(NUCLEUS_HOME, style.nucleusRadius + 0.35) : NUCLEUS_HOME;
  const ER_FACING = vacuole ? Math.atan2(-NUCLEUS.z, -NUCLEUS.x) + 0.5 : ER_HOME; // beside a vacuole the ER lies on the nucleus's inner side
  const GOLGI = vacuole ? seat(GOLGI_HOME, style.golgi.inner + style.golgi.gap * 4 + 0.6) : GOLGI_HOME;
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
  // The membrane seen in section where the cut passes through it, for the cell and its neighbours alike: a fine line, or a band.
  const edgeLine = () => new THREE.BufferGeometry().setFromPoints(outline.ring(0, CUT + 0.0002, 16));
  const edgeBand = () => band(outline.ring(-style.band * 0.72, CUT + 0.004, 16), outline.ring(style.band * 0.28, CUT + 0.004, 16));

  // ---------------------------------------------------------------- what more than one part reads
  // What stands in the cut edge, each as an angle and half the stretch of edge it takes: the lipid
  // heads leave it clear, and the ions between cells keep off it.
  const taken = [...[...(has("channels") ? SPOT.channels : []), ...(has("pumps") ? SPOT.pumps : []), ...(has("wound") ? [SPOT.wound] : [])].map((angle) => [angle, 0.74]), ...(junction ? [[SPOT.junction, 1.3]] : [])];
  // How the layer is packed follows from the cell's own sides (shapes.js): four-sided cells in squares, others in sixes.
  const pack = packing(cell.shape.kind === "prism" ? cell.shape.sides : 6);
  const neighbours = cell.neighbours ? pack.turns.map((turn) => radial(turn).multiplyScalar(LATTICE)) : [];
  const cells = [new THREE.Vector3(), ...neighbours]; // where the seven stand
  // Where the cages and the machine stand, clear of the sides.
  const cagesAt = CAGES_AT_SURFACE.map((point) => seat(point, 2.2)), machineAt = seat(MACHINE, 1.9);
  // The middle of what regulation acts on, and how far it reaches: the nucleus, or the free chromosome.
  const slim = outline.apothem; // half the cell's width across its narrow way, where the cut passes
  const coreAt = parts.nucleus ? NUCLEUS : new THREE.Vector3(frame.middle, CUT - slim * 0.46, 0), coreRadius = parts.nucleus ? style.nucleusRadius : slim * 0.42;
  // In a long cell the chromosome lies along it: how far it reaches each way from its middle.
  const coreReach = coreRadius + Math.max(0, frame.long / 2 - frame.equator.apothem) * 0.8;
  // A place on the side that faces the viewer, below the cut: the click checks press it, and the species' own scenery keeps clear of it.
  const uncutSide = frame.skin(1.14, -2.5);

  return {
    mode, real, style, cell, has, parts, organelle,
    frame, outline, TOP, BASE, BEVEL, prism,
    random, inCut, inside, vacuole, inCytoplasm, scatter, seat, skinAt, onSkin,
    NUCLEUS, ER_FACING, GOLGI,
    junction, junctionAt, edgeLine, edgeBand,
    taken, pack, neighbours, cells, cagesAt, machineAt,
    coreAt, coreRadius, coreReach, uncutSide,
  };
}
