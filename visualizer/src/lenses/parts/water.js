// Water crossing the membrane at two corners: the drops the lens moves.
//
// A part module of the cell's builder (parts/index.js), moved unchanged from buildCell in
// cell_parts.js. It draws through the lens's context, from the layout (cell_layout.js).
// It takes nothing from the layout's stream of chance.

import * as THREE from "../../three.js";
import { CUT, SPOT } from "../cell_layout.js";

export default {
  kind: "water",
  draws: ["water"],
  build(env) {
    const { ctx, handles } = env;
    const { real, style, has, outline } = env.layout;
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
  },
};
