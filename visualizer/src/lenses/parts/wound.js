// A wound in the membrane, and what leaves it.
//
// A part module of the cell's builder (parts/index.js), moved unchanged from buildCell in
// cell_parts.js. It draws through the lens's context, from the layout (cell_layout.js).
// It takes nothing from the layout's stream of chance.

import * as THREE from "../../three.js";
import { CUT, SPOT } from "../cell_layout.js";
import { instanced } from "./geometry.js";

export default {
  kind: "wound",
  draws: ["wound"],
  build(env) {
    const { ctx } = env;
    const { style, has, outline } = env.layout;
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
  },
};
