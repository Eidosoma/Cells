// The space between cells, or round a cell on its own: its ions.
//
// A part module of the cell's builder (parts/index.js), moved unchanged from buildCell in
// cell_parts.js. It draws through the lens's context, from the layout (cell_layout.js).
// It takes from the layout's one stream of chance, in the builder's fixed order.

import * as THREE from "../../three.js";
import { CUT, SPOT, GAP_CORNER } from "../cell_layout.js";
import { radial, instanced, dots } from "./geometry.js";

export default {
  kind: "extracellular",
  draws: ["extracellular"],
  build(env) {
    const { ctx } = env;
    const { real, style, cell, has, outline, BASE, random, taken, pack, cells } = env.layout;
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
    const gapAt = (angle) => radial(angle).multiplyScalar(pack.radius); // where the cell and its neighbours meet at a corner
    const outside = ctx.part("extracellular", gapAt(pack.sides === 6 ? GAP_CORNER : pack.cornerNear(GAP_CORNER)).setY(CUT - 0.5));
    // Kept clear: what stands in the cut edge, the charges, and the stretch that the close-up of the membrane shows.
    const shown = [...taken, ...SPOT.charges.map((angle) => [angle, 0.6]), [SPOT.channels[1], 3.4]].map(([angle, stretch]) => [outline.reach(angle), stretch]);
    const between = (count, clear) => {
      const found = [];
      let guard = 0;
      while (found.length < count * (real ? 0.5 : 0.35) && guard++ < count * 200) {
        const corner = pack.corner(Math.floor(random() * pack.sides));
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
  },
};
