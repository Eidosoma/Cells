// The cytoplasm's cut face, its specks (or dots to scale), and the vesicles of a cell with
// inner membranes, as scenery.
//
// A part module of the cell's builder (parts/index.js), moved unchanged from buildCell in
// cell_parts.js. It draws through the lens's context, from the layout (cell_layout.js).
// It takes from the layout's one stream of chance, in the builder's fixed order.

import * as THREE from "../../three.js";
import { CUT } from "../cell_layout.js";
import { instanced, dots, fan, band } from "./geometry.js";

export default {
  kind: "cytoplasm",
  draws: ["cytoplasm"],
  build(env) {
    const { ctx } = env;
    const { real, style, parts, frame, outline, random, vacuole, inCytoplasm, scatter, seat, NUCLEUS } = env.layout;
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
    // Vesicles: scenery, so neutral glass. They belong to a cell with inner membranes.
    if (parts.nucleus) {
      const bubbles = real
        ? scatter(80, (point) => inCytoplasm(point, 0.8)).map((position) => ({ position, scale: 0.12 + random() * 0.22 }))
        : [[-5.9, 1.5], [0.4, 8.0], [7.4, -3.4], [-2.6, -4.4], [4.3, 6.9], [-7.6, -3.6]].map(([x, z]) => ({ position: seat(new THREE.Vector3(x, CUT + 0.05, z), 1.75), scale: 0.45 + random() * 0.3 }));
      ctx.illustrate(instanced(new THREE.SphereGeometry(1, 20, 14), ctx.neutral({ opacity: 0.14, glass: 0.5 }), bubbles));
    }
  },
};
