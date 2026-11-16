// Geometry for the cell lens: the cell (buildCell, which calls the part modules in parts/),
// the close-up of its membrane (buildMolecules) and the sheet (buildTissue). Every shape
// built here or in a part module is either bound to a capability
// from the scene file (through ctx.part) or is neutral illustration (ctx.neutral).
// Nothing is drawn that looks like a capability without being one.
//
// Some materials ask for part of the resting look (core/look.js): `thin` lets a little light
// through a part's thin edges, `texture` gives a surface its grain, folds or pores, `shimmer`
// marks the membrane, and `drift` lets a crowd jostle about its places. All four are
// scenery: no data stands behind a fold, a pore or a jostle, and none is drawn where the
// look is plain.
//
// A new kind of scenery (an appendage, say) is built in a part module as the wall and the vesicles are:
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
// A cell under 2 µm across is drawn in one size mode for now: the schematic layout scaled
// down to the cell's own size. Its flagella, fimbriae and ribosomes are drawn at their sizes;
// its membranes, membrane proteins, ions and small molecules are still enlarged, the more so
// the larger the cell (in E. coli a membrane is drawn about six times as thick as it is).
//
// The layout (cell_layout.js) holds where every part stands and the one stream of chance the
// parts draw from, in a fixed order; the small pieces of geometry are in parts/geometry.js.

import * as THREE from "../three.js";
import { REF, packing } from "./shapes.js";
import { CUT, SPOT, beadStep, makeLayout } from "./cell_layout.js";
import { seeded, along, turnY, instanced, dots } from "./parts/geometry.js";
import { CELL_PARTS } from "./parts/index.js";

// The layer's packing in the frame: six-sided, this far from a cell's centre to a corner.
export const HEX = { radius: REF.radius };
export const R = 10; // about half the cell's width
export { CUT, seeded };

/**
 * Builds one cell in the given size mode, from what the species says of it:
 *   cell.shape       its shape (schema/SPECIES_SHAPES.md)
 *   cell.parts       what it holds: a nucleus, organelles, a free chromosome, ribosomes
 *   cell.has(part)   whether the capability drawn at that part has a place in this cell
 *   cell.neighbours  whether it stands in a layer, with neighbours round it
 *   cell.notes       what the picture says in words beside it
 * Returns handles the lens animates, the points the input check clicks, and the cell's frame.
 *
 * The cell is drawn by its part modules (parts/index.js), each called once, in the registry's
 * order, with the same layout and so the same stream of chance (cell_layout.js). `modules` is
 * that list; a caller may give its own, in the same form.
 */
export function buildCell(ctx, studsCtx, mode, cell, modules = CELL_PARTS) {
  const layout = makeLayout(mode, cell);
  const { style, frame, outline, parts, NUCLEUS, junction, coreAt, coreRadius, uncutSide } = layout;
  const handles = { cages: [], frame, streams: [], signals: [], signalPath: () => new THREE.Vector3() };
  // What a part hands on for those after it and for the builder: the shells' distances, the structures built, the scenery.
  const built = {};
  const env = { ctx, studsCtx, layout, handles, built };
  for (const part of modules) Object.assign(built, part.build(env));

  const structures = built.structures || {}, scenery = built.scenery || { items: [], reach: 0, notes: [] };
  handles.probes = {
    // In the nucleus, or in the middle of the free chromosome where a cell has no nucleus.
    nucleus: parts.nucleus ? NUCLEUS.clone().add(new THREE.Vector3(-0.9, style.nucleusRadius * 0.9, 0.9)) : coreAt.clone().add(new THREE.Vector3(-coreRadius * 0.2, coreRadius * 0.85, coreRadius * 0.2)),
    // On the cut faces of the opened nucleus, where a click reaches the chromatin within (cell_structures.js).
    ...(structures.nucleus ? { chromatin: structures.nucleus.probe } : {}),
    cutGel: outline.point(Math.atan2(-7.6, -3.9), -1.7, CUT), // on the cut face of the cytoplasm, well inside the membrane's edge
    uncutSide, // on the side that faces the viewer, below the cut
    sheetCell: new THREE.Vector3(73.4, 6.5, 31.8),
  };
  // The outline, for the lens: a point of it, and how far inside it a point is.
  handles.shape = { point: outline.point, depth: (point) => outline.depth(point.x, point.z) };
  // Where on the outline the parts stand that something flows through, for flux (layers/cellflux.js).
  handles.spots = { ...SPOT, junction: junction ? SPOT.junction : null, gap: style.neighbourGap };
  // How far outside the cell membrane each shell outside it stands, in the cell's frame (0 where the cell has none).
  handles.shells = built.shells || { outerGap: 0, wallGap: 0 };
  handles.scenery = scenery.items;
  handles.reach = scenery.reach; // how far from the cell's middle its longest thread goes
  // What the picture says in words beside the cell (the lens writes them under the stop's name).
  // Short lines, so they stay clear of the names in the columns beside the cell.
  handles.notes = [...(cell.notes || []), ...scenery.notes];
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
/**
 * A sheet of the species' own cells, in the cell's frame: `rings` rings round the middle
 * cell, each cell `height` tall. `beyond` says how far the layer goes on as faint outlines,
 * as [ring, strength] pairs. `sides` is the number of sides of the species' cell: the sheet
 * is packed as that asks (shapes.js, packing), in squares for a four-sided cell, else in sixes.
 */
export function buildTissue(ctx, { rings, height, beyond, notes, sides = 6 }) {
  const pack = packing(sides);
  const hexCentre = pack.centre, sheetCells = pack.cells;
  // A cell of the sheet: a prism of the packing's sides, with one side facing the first neighbour.
  const prism = new THREE.CylinderGeometry(pack.radius * 0.955, pack.radius * 0.955, height, pack.sides);
  if (pack.sides === 4) prism.rotateY(Math.PI / 4);
  const cells = sheetCells(rings);
  const same = (a, b) => a.q === b.q && a.r === b.r;
  const within = (cell) => cells.some((item) => same(item, cell));
  // Which cells show replacement and mechanics: fixed places in a sheet large enough to hold them.
  const leaving = within({ q: 3, r: -1 }) ? { q: 3, r: -1 } : null, arriving = within({ q: -2, r: 3 }) ? { q: -2, r: 3 } : null;
  const inPatch = (cell) => rings >= 4 && (pack.sides === 4 ? cell.q : cell.q + cell.r / 2) < -2.4 && cell.r < 0; // the mechanics patch
  const plain = cells.filter((cell) => !(leaving && same(cell, leaving)) && !(arriving && same(cell, arriving)) && !inPatch(cell));

  const sheet = ctx.part("sheet", new THREE.Vector3(40, height / 2 + 6, -58));
  const body = instanced(prism, sheet.material({ hue: "bioCell", roughness: 0.5 }), plain.map((cell) => ({ position: hexCentre(cell) })));
  const tone = seeded(11), shadeOf = new THREE.Color();
  plain.forEach((_, index) => body.setColorAt(index, shadeOf.setScalar(0.9 + tone() * 0.18)));
  body.instanceColor.needsUpdate = true;
  sheet.add(body);
  // The cell this lens opens on, marked so the zoom out keeps its place.
  const marker = new THREE.Mesh(new THREE.TorusGeometry(pack.radius * 0.8, 0.5, 8, pack.sides), ctx.neutral({ opacity: 0.9, colour: "fg" }));
  marker.rotation.set(Math.PI / 2, 0, pack.turn / 2);
  marker.position.y = height / 2 + 0.4;
  ctx.illustrate(marker);
  // Lines between neighbours: the junction network that couples the sheet.
  const links = [];
  for (const cell of cells) {
    for (const [dq, dr] of pack.links) {
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
    const angle = pack.sides === 6 ? (Math.PI / 3) * index + Math.PI / 6 : pack.corner(index);
    return hexCentre(cell).add(new THREE.Vector3(Math.cos(angle) * pack.radius, height / 2 + 0.2, Math.sin(angle) * pack.radius));
  };
  const patch = cells.filter(inPatch);
  if (patch.length) {
    const centreOfPatch = patch.reduce((sum, cell) => sum.add(hexCentre(cell)), new THREE.Vector3()).multiplyScalar(1 / patch.length);
    const mechanics = ctx.part("mechanics", centreOfPatch.clone().add(new THREE.Vector3(-8, height / 2 + 7, -10)));
    mechanics.add(instanced(prism, mechanics.material({ hue: "bioCell", opacity: 0.32, depthWrite: false }), patch.map((cell) => ({ position: hexCentre(cell) }))));
    const edgeMaterial = mechanics.material({ hue: "bioCell", shade: -0.3 });
    const seen = new Set();
    for (const cell of patch) {
      for (let index = 0; index < pack.sides; index++) {
        const a = corner(cell, index), b = corner(cell, (index + 1) % pack.sides);
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
  const ringOf = pack.ring;
  const drawn = new Set();
  let inner = rings;
  for (const [outer, opacity] of beyond || []) {
    const segments = [];
    for (const cell of sheetCells(outer)) {
      if (ringOf(cell) <= inner) continue;
      for (let index = 0; index < pack.sides; index++) {
        const a = corner(cell, index), b = corner(cell, (index + 1) % pack.sides);
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
  return { extent: pack.pitch * (rings * 2 + 1), spread: pack.sides === 4 ? 1.24 : 1, notes: notes || [] };
}

export { instanced };
