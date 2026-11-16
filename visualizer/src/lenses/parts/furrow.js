// The line along which the cell divides.
//
// A part module of the cell's builder (parts/index.js), moved unchanged from buildCell in
// cell_parts.js. It draws through the lens's context, from the layout (cell_layout.js).
// It takes nothing from the layout's stream of chance.

import * as THREE from "../../three.js";
import { CUT, SPOT } from "../cell_layout.js";
import { radial, instanced } from "./geometry.js";

export default {
  kind: "furrow",
  draws: ["furrow"],
  build(env) {
    const { ctx } = env;
    const { real, style, has, frame, outline, BASE, BEVEL } = env.layout;
    // The line along which the cell divides: down one side, under the base and up the other,
    // a little off the membrane.
    if (has("furrow")) {
    const furrow = ctx.part("furrow", outline.point(SPOT.furrow, 0.9, CUT + 0.2));
    const off = real ? 0.08 : 0.22;
    const leg = (angle) => {
      if (frame.round) {
        // A round cell: the line follows its surface from above the cut down to the point under its middle.
        const under = -frame.inside(new THREE.Vector3()) - off, points = [];
        for (let step = 0; step <= 28; step++) {
          const y = CUT + 0.6 + (under - CUT - 0.6) * Math.sin(((step / 28) * Math.PI) / 2);
          points.push(frame.skin(angle, y, off));
        }
        return points;
      }
      const out = radial(angle), points = [out.clone().multiplyScalar(outline.radius(angle, off)).setY(CUT + 0.6)];
      for (let step = 0; step <= 8; step++) {
        const t = (step / 8) * (Math.PI / 2); // round the edge of the base
        points.push(out.clone().multiplyScalar(outline.radius(angle, off * Math.cos(t) - BEVEL * (1 - Math.cos(t)))).setY(BASE + BEVEL * (1 - Math.sin(t)) - off * Math.sin(t)));
      }
      return points;
    };
    const line = [...leg(SPOT.furrow), ...leg(SPOT.furrow + Math.PI).reverse()];
    const pieces = [];
    let next = 0.35; // how far along the line the next dash is
    for (let index = 0; index + 1 < line.length; index++) {
      const length = line[index].distanceTo(line[index + 1]), direction = line[index + 1].clone().sub(line[index]).normalize();
      for (; next < length; next += 1.235) pieces.push({ position: line[index].clone().addScaledVector(direction, next), direction });
      next -= length;
    }
    furrow.add(instanced(new THREE.CylinderGeometry(style.dash, style.dash, 0.7, 6), furrow.material({ hue: "bioMembrane", shade: -0.42, clip: true }), pieces));
    // The same line continues a little way across the cut surface, at both ends.
    const mark = furrow.material({ hue: "bioMembrane", shade: -0.42 });
    for (const side of [0, Math.PI]) {
      for (let step = 0; step < 3; step++) {
        const piece = new THREE.Mesh(new THREE.BoxGeometry(0.5, style.dash, style.dash * 1.6), mark);
        piece.position.copy(radial(SPOT.furrow + side).multiplyScalar(outline.radius(SPOT.furrow + side) - 1.0 - step * 0.95).setY(CUT + 0.05));
        piece.rotation.y = -(SPOT.furrow + side);
        furrow.add(piece);
      }
    }
    }
  },
};
