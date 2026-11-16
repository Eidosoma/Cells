// The signals that leave the cell at a corner: the beads the lens moves.
//
// A part module of the cell's builder (parts/index.js), moved unchanged from buildCell in
// cell_parts.js. It draws through the lens's context, from the layout (cell_layout.js).
// It takes nothing from the layout's stream of chance.

import * as THREE from "../../three.js";
import { CUT, SPOT } from "../cell_layout.js";
import { UP } from "./geometry.js";

export default {
  kind: "secretion",
  draws: ["secretion"],
  build(env) {
    const { ctx, handles } = env;
    const { real, style, has, outline } = env.layout;
    // Signals leave at a corner and drift up and away over the neighbours.
    if (has("secretion")) {
      const secretion = ctx.part("secretion", outline.point(SPOT.secretion, 4.6, CUT + 2.0));
      const drift = outline.tangent(SPOT.secretion);
      handles.signalPath = (t) => outline.point(SPOT.secretion, 0.3 + t * 5.5, CUT - 0.1).addScaledVector(UP, t * 0.8 + t * t * 1.6).addScaledVector(drift, t * t * 1.2);
      const signal = secretion.material({ hue: "bioSignal", roughness: 0.25 });
      handles.signals = Array.from({ length: real ? 24 : 9 }, () => new THREE.Mesh(new THREE.SphereGeometry(style.bead, 12, 9), signal));
      handles.signals.forEach((bead) => secretion.add(bead));
    }
  },
};
