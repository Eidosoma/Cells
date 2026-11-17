// The cytoplasm's cut face, its specks (or dots to scale), and the vesicles of a cell with
// inner membranes, as scenery.
//
// A part module of the cell's builder (parts/index.js), moved unchanged from buildCell in
// cell_parts.js. It draws through the lens's context, from the layout (cell_layout.js).
// It takes from the layout's one stream of chance, in the builder's fixed order.

import * as THREE from "../../three.js";
import { CUT, TO_SCALE } from "../cell_layout.js";
import { instanced, dots, fan, band, seeded } from "./geometry.js";

export default {
  kind: "cytoplasm",
  draws: ["cytoplasm"],
  build(env) {
    const { ctx } = env;
    const { real, style, parts, frame, outline, random, vacuole, inCytoplasm, scatter, seat, NUCLEUS, fine, nm, slab, body, inside, membraneNm } = env.layout;
    const chemistry = ctx.part("cytoplasm", outline.point(Math.atan2(-7.4, -3.9), -1.45, CUT + 0.15));
    const gelEdge = outline.ring(real ? -0.003 : -style.band * 0.72, real ? CUT - 0.0006 : CUT - 0.02, 16);
    const gel = new THREE.Mesh(
      // Beside a vacuole the cytoplasm is the rim between it and the membrane: the vacuole's own section is left clear.
      vacuole ? band(outline.ring(-vacuole.inset, real ? CUT - 0.0006 : CUT - 0.02, 16), gelEdge) : fan(gelEdge),
      chemistry.material({ hue: "bioCyto", opacity: real ? 0.42 : 0.3, side: THREE.DoubleSide, roughness: 0.12, depthWrite: false, rim: 0 })
    );
    gel.renderOrder = 3;
    // Over the nucleus the cut face is the nucleus's own: a click there goes on to what is in it.
    if (parts.nucleus) gel.userData.pickFilter = (hit) => Math.hypot(hit.point.x / frame.u - NUCLEUS.x, hit.point.z / frame.u - NUCLEUS.z) > style.nucleusRadius;
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
    // The crowd of proteins, for a cell drawn to scale whose file counts them (schema/SPECIES_SHAPES.md, `proteins`):
    // only in a slab under the cut, as an electron tomogram shows a cell, since drawn whole they would hide it (Syn3A's
    // would cover its cut face more than six times over). In the slab, the share of the count that the slab's share of
    // the cell's volume holds; of the membrane's share, what the slab's ring of membrane holds. Each a mark about 5 nm
    // across: neutral scenery, which cannot be chosen. Placed from a stream of chance of its own.
    const crowd = fine && parts.proteins ? proteinSlab(env, { parts, outline, nm, slab, body, inside, membraneNm }) : null;
    // Vesicles: scenery, so neutral glass. They belong to a cell with inner membranes.
    if (parts.nucleus) {
      const bubbles = real
        ? scatter(80, (point) => inCytoplasm(point, 0.8)).map((position) => ({ position, scale: 0.12 + random() * 0.22 }))
        : [[-5.9, 1.5], [0.4, 8.0], [7.4, -3.4], [-2.6, -4.4], [4.3, 6.9], [-7.6, -3.6]].map(([x, z]) => ({ position: seat(new THREE.Vector3(x, CUT + 0.05, z), 1.75), scale: 0.45 + random() * 0.3 }));
      ctx.illustrate(instanced(new THREE.SphereGeometry(1, 20, 14), ctx.neutral({ opacity: 0.14, glass: 0.5 }), bubbles));
    }
    return crowd ? { crowd } : {};
  },
};

/** The crowd of proteins in the slab under the cut, drawn as neutral marks. Returns how many of how many, for the words. */
function proteinSlab(env, { parts, outline, nm, slab, body, inside, membraneNm }) {
  const { ctx } = env;
  const random = seeded(5101);
  const count = parts.proteins.count, inMembrane = parts.proteins.membrane || 0;
  const radius = (TO_SCALE.protein / 2) * nm;
  const share = (body.section * slab) / body.volume; // the slab's share of the cell's volume
  const ring = (outline.length * slab) / body.area; // the slab's share of the membrane
  const loose = Math.round((count - inMembrane) * share), held = Math.round(inMembrane * ring);
  const across = outline.apothem, top = CUT - radius, bottom = CUT - slab + radius; // the outline's half-width across its narrow way
  const marks = [];
  for (let guard = 0; marks.length < loose && guard < loose * 60; guard++) {
    const point = new THREE.Vector3((random() * 2 - 1) * outline.widest, bottom + random() * (top - bottom), (random() * 2 - 1) * across);
    if (inside(point) > radius + (membraneNm * nm) / 2) marks.push({ position: point, scale: 0.8 + random() * 0.4 });
  }
  const placedLoose = marks.length;
  for (let index = 0; index < held; index++) {
    const s = random() * outline.length;
    marks.push({ position: outline.spot(s, (random() - 0.5) * membraneNm * nm, bottom + random() * (top - bottom)), scale: 0.8 + random() * 0.4 });
  }
  if (marks.length) ctx.illustrate(instanced(new THREE.IcosahedronGeometry(radius, 0), ctx.neutral({ opacity: 0.55, glass: 0.3 }), marks));
  return { loose: placedLoose, held, count, inMembrane, share, ring, depth: TO_SCALE.slab };
}
