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
export const GOLGI_HOME = new THREE.Vector3(-4.9, CUT + 0.15, 4.3); // where the Golgi stood before 17 November 2026; now only a cell with a vacuole starts from it
// An animal cell's Golgi stands beside the nucleus, toward the cell's middle, where the ER faces: in the cell's frame, how far
// its cis face stands from the nuclear envelope, and the centrosome's middle, in each size mode (the picture's choice: a
// micrometre, and half of one to scale, in the generic animal cell). The user chose this on 17 November 2026 (docs/CELL_STRUCTURES.md).
export const BESIDE = { schematic: { golgi: 1.0, centrosome: 0.45 }, real: { golgi: 0.5, centrosome: 0.25 } };
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

// ---------------------------------------------------------------- to scale, in nanometres
// Drawn to scale, a part's size is worked out in nanometres from the cell's own size, and the
// part is a shape where it covers two pixels or more at the cell's stop and dots where it covers
// less. So a cell 20 µm across draws every molecule as dots (its stop holds about 34 nm a pixel),
// and a bacterium draws its membranes, membrane proteins and ribosomes as themselves (E. coli's
// stop holds about 2.3 nm a pixel, Syn3A's 0.75). Nothing here names a size of cell.
//
// The cell's stop as the lens frames it (cell.js, makeStops and nominal()): 31 units tall, as
// wide as the cell's length asks (1.3 times it, between 42 and 96 units), on a nominal wide
// screen 900 pixels tall and half as wide again, through the camera's view 34 degrees tall.
export const STOP = { tall: 31, wide: [42, 96], length: 1.3, view: 34, aspect: 1.5, pixels: 900 };
/** The cell's stop: its frame [wide, tall] in units, and how many nanometres one pixel holds there on the nominal wide screen. */
export function stopOf(frame) {
  const half = Math.tan((STOP.view * Math.PI) / 360);
  const size = [Math.min(STOP.wide[1], Math.max(STOP.wide[0], frame.long * STOP.length)), STOP.tall];
  const distance = Math.max(size[1] / (2 * half), size[0] / (2 * half * STOP.aspect)); // in units
  return { size, pixel: ((2 * distance * half) / STOP.pixels) * frame.u * 1000 };
}
// A channel and a pump as the picture draws them to scale, in nanometres (the picture's choice): in every
// cell's close-up, and in a bacterium's cut edge and on its skin. The shapes, their spacing on the skin and
// the page's words all read these, so that the words say what is drawn.
// A channel: two walls `wall` in radius and `length` long, their middles `apart` apart, with a pore between.
const channelOf = (wall, length, apart) => Object.freeze({ wall, length, apart, across: apart + 2 * wall });
export const CHANNEL = channelOf(1.5, 10, 4.4); // 7.4 nm across
// A pump: three lobes, each [how far inward of the membrane's middle, radius], most of its bulk on the cytoplasm side.
const pumpOf = (lobes) => Object.freeze({ lobes, across: 2 * Math.max(...lobes.map(([, radius]) => radius)) });
export const PUMP = pumpOf([[0, 4.2], [5.5, 3.6], [-3.2, 2.6]]); // 8.4 nm across
/** Where the close-up of the membrane stands: at a channel, or in a cell that has none, at a pump (cell_parts.js, buildMolecules). */
export const closeUpAngle = (has) => (has("channels") || !has("pumps") ? SPOT.channels[1] : SPOT.pumps[0]);
// How far either way along the outline the close-up drawn to scale reaches, in nanometres: its heads (60 nm) and the wall's strip (72).
export const CLOSE_UP_REACH = 75;
// The picture's choices for a cell drawn to scale, in nanometres, where the species' file gives
// nothing: a membrane's thickness (the textbook bilayer, as the close-up draws it), the depth of the
// slab under the cut in which the crowd of proteins and the chromosome are drawn (as an electron
// tomogram shows a cell: drawn whole they would hide it), a protein's size there, a ribosome's,
// DNA's width and length a base pair, and a channel's and a pump's width (the shapes above).
export const TO_SCALE = { membrane: 4.5, slab: 10, protein: 5, ribosome: 20, dna: 2, perBase: 0.34, channel: CHANNEL.across, pump: PUMP.across };
const middleOf = (value) => (Array.isArray(value) ? (value[0] + value[1]) / 2 : value);

/** The size of a cell's body in its frame: the surface of its membrane, its volume, and the area and length of its outline at the cut. */
function bodyOf(frame) {
  const outline = frame.outline, ring = outline.ring(0, CUT, 16);
  let section = 0;
  ring.forEach((point, index) => {
    const next = ring[(index + 1) % ring.length];
    section += point.x * next.z - next.x * point.z;
  });
  section = Math.abs(section) / 2;
  if (frame.round) {
    // A sphere or a capsule: a cylinder between two half spheres (a club is taken at its full width, a little over).
    const r = frame.top, straight = Math.max(0, frame.long - 2 * r);
    return { area: 2 * Math.PI * r * straight + 4 * Math.PI * r * r, volume: Math.PI * r * r * straight + (4 / 3) * Math.PI * r ** 3, section, perimeter: outline.length };
  }
  // A prism: its outline drawn up through its height (its rounded edges are left out: a little over).
  const height = frame.top - frame.base, equator = frame.equator.ring(0, 0, 16);
  let face = 0;
  equator.forEach((point, index) => {
    const next = equator[(index + 1) % equator.length];
    face += point.x * next.z - next.x * point.z;
  });
  face = Math.abs(face) / 2;
  return { area: frame.equator.length * height + 2 * face, volume: face * height, section, perimeter: outline.length };
}

/**
 * Where the shells of a cell drawn to scale stand from its envelope's widths (schema/SPECIES_SHAPES.md,
 * `envelope`), in nanometres from the cell membrane's middle to each shell's middle, with each
 * one's thickness. Null where the file gives no envelope.
 */
export function envelopeOf(parts) {
  const given = parts.envelope;
  if (!given) return null;
  const membrane = middleOf(given.membrane_nm ?? TO_SCALE.membrane);
  const out = { membrane };
  if (parts.membranes === 2 && given.between_nm !== undefined) {
    const outer = middleOf(given.outer_nm ?? TO_SCALE.membrane), between = middleOf(given.between_nm);
    out.outer = { at: membrane / 2 + between + outer / 2, thick: outer };
    if (parts.wall && given.wall_nm !== undefined && given.wall_to_outer_nm !== undefined) {
      const wall = middleOf(given.wall_nm);
      out.wall = { at: membrane / 2 + between - middleOf(given.wall_to_outer_nm) - wall / 2, thick: wall };
    }
  }
  return out;
}

/**
 * The layout of one cell in one size mode, from what the species says of it (buildCell's
 * `cell`: shape, parts, has, neighbours, notes). Returns the places, tests, finders and claims
 * set out above, the frame and its outline, and the stream of chance. Draws nothing, and takes
 * nothing from the stream.
 */
export function makeLayout(mode, cell) {
  const real = mode === "real";
  const frame = cellFrame(cell.shape, cell.neighbours ? STYLE[mode].neighbourGap : 0);
  // To scale, in nanometres: one nanometre in the cell's frame, how many a pixel holds at the cell's stop, whether a
  // thing of a given size is drawn as a shape there, and whether the cell's molecules are drawn as themselves (its
  // ribosomes cover two pixels): a cell `fine` to scale takes the sizes below in place of STYLE.real's, which are
  // micrometres of a cell 20 µm across.
  const nm = 0.001 / frame.u, pixel = stopOf(frame).pixel;
  const seen = (size) => real && size / pixel >= 2;
  const fine = seen(TO_SCALE.ribosome);
  const envelope = fine ? envelopeOf(cell.parts) : null;
  const membraneNm = envelope?.membrane ?? TO_SCALE.membrane;
  // The marks that move or point (drops, signals, a wound, a dashed line) are the picture's choice: a few pixels at the stop.
  const mark = (pixels) => pixels * pixel * nm;
  const style = fine ? { ...STYLE.real, fine: true, band: membraneNm * nm, drop: mark(2.5), bead: mark(2.5), wound: mark(12), dash: mark(0.7) } : STYLE[mode];
  const body = bodyOf(frame);
  // The close-up of the membrane is built from the frame alone (cell_parts.js, buildMolecules): it reads the scale there.
  frame.scale = { fine, nm, pixel, envelope, membraneNm };
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
  // Beside a vacuole a plant cell's Golgi is many small stacks in the thin cytoplasm (cell_structures.js), which places
  // them itself. A cell with a nucleus and room in its middle has its Golgi beside the nucleus, round its centrosome:
  // the stack's middle stands half its depth beyond the gap, so that the cis face is about that far from the envelope.
  const beside = !vacuole && parts.nucleus;
  const golgiDepth = (style.golgi.count - 1) * style.golgi.gap + style.golgi.half * (real ? 1.6 : 1.9);
  const GOLGI = vacuole ? seat(GOLGI_HOME, style.golgi.inner + style.golgi.gap * 4 + 0.6) : beside ? NUCLEUS.clone().addScaledVector(radial(ER_FACING), style.nucleusRadius + BESIDE[mode].golgi + golgiDepth / 2).setY(CUT + 0.15) : GOLGI_HOME;
  const CENTROSOME = beside ? NUCLEUS.clone().addScaledVector(radial(ER_FACING), style.nucleusRadius + BESIDE[mode].centrosome).setY(CUT + 0.1) : null;
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
    nm, pixel, seen, fine, envelope, membraneNm, body, slab: TO_SCALE.slab * nm,
    frame, outline, TOP, BASE, BEVEL, prism,
    random, inCut, inside, vacuole, inCytoplasm, scatter, seat, skinAt, onSkin,
    NUCLEUS, ER_FACING, GOLGI, CENTROSOME,
    junction, junctionAt, edgeLine, edgeBand,
    taken, pack, neighbours, cells, cagesAt, machineAt,
    coreAt, coreRadius, coreReach, uncutSide,
  };
}
