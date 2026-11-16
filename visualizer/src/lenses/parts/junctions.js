// The neighbours of a cell in a layer, as faint glass, and the gap junctions that bridge the
// cleft to the first of them.
//
// A part module of the cell's builder (parts/index.js), moved unchanged from buildCell in
// cell_parts.js. It draws through the lens's context, from the layout (cell_layout.js).
// It takes from the layout's one stream of chance, in the builder's fixed order.

import * as THREE from "../../three.js";
import { CUT, SPOT } from "../cell_layout.js";
import { UP, instanced, dots } from "./geometry.js";

export default {
  kind: "junctions",
  draws: ["junctions"],
  build(env) {
    const { ctx } = env;
    const { real, style, cell, outline, prism, random, junction, edgeLine, edgeBand, neighbours } = env.layout;
    // The cell is one of a layer, so its neighbours stand round it, side against side, six as
    // in a packed sheet and where the sheet's own cells stand. They are scenery: faint glass
    // that cannot be clicked, opened by the same cut. The one the junction leads to is drawn a
    // little stronger; the others are only a thin outline where the cut passes through them.
    // How the layer is packed, and where the neighbours stand, are the layout's (`pack`, `neighbours`, `cells`).
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
  },
};
