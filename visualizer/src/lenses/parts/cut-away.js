// The outline of the part the cut takes away, as dashes, and the plate a layer stands on:
// scenery.
//
// A part module of the cell's builder (parts/index.js), moved unchanged from buildCell in
// cell_parts.js. It draws through the lens's context, from the layout (cell_layout.js).
// It takes nothing from the layout's stream of chance.

import * as THREE from "../../three.js";
import { CUT } from "../cell_layout.js";
import { radial, fan } from "./geometry.js";

export default {
  kind: "cut-away",
  draws: [],
  build(env) {
    const { ctx } = env;
    const { style, cell, frame, outline, TOP, BASE, BEVEL, pack, neighbours, cells } = env.layout;
    // The cut takes away the cell's outer face. Its outline is kept as a faint dashed line, so the
    // cell's whole height shows. Under a layer lies a thin plate, where a skin's cells would
    // rest on a basement membrane, lined where each of the seven cells stands on it. Both are
    // scenery, like the neighbours.
    const dashes = ctx.neutralLine({ opacity: 0.5, dashed: true, dash: 0.45, gap: 0.32 });
    // On a round cell the outline runs half-way up the part cut away, where its surface has
    // turned through half a right angle; the body is as high as it is wide at each place.
    const onRound = (place, turn) => new THREE.Vector3(place.x - Math.cos(place.facing) * place.rho * (1 - Math.cos(turn)), place.rho * Math.sin(turn), place.z - Math.sin(place.facing) * place.rho * (1 - Math.cos(turn)));
    const lid = frame.round ? frame.equator.samples(10, 6).map((place) => onRound(place, Math.PI / 4)) : frame.equator.ring(-BEVEL * 0.3, TOP - BEVEL * 0.3, 10, 6);
    const cutAway = [[...lid, lid[0]]];
    for (const angle of frame.equator.corners) {
      if (frame.round) {
        // A round cell has no edges: the lines follow its surface from just above the cut up to the outline.
        const place = frame.equator.at(frame.equator.reach(angle)), from = Math.asin(Math.min(1, (CUT + 0.3) / place.rho));
        if (from < Math.PI / 4) cutAway.push(Array.from({ length: 9 }, (_, step) => onRound(place, from + ((Math.PI / 4 - from) * step) / 8)));
      } else {
        // Up each upright edge, and over the rounded edge to the face.
        cutAway.push([outline.point(angle, 0, CUT + 0.3), outline.point(angle, 0, TOP - BEVEL), outline.point(angle, -BEVEL * 0.3, TOP - BEVEL * 0.3)]);
      }
    }
    for (const points of cutAway) {
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), dashes);
      line.computeLineDistances();
      ctx.illustrate(line);
    }
    if (cell.neighbours) {
      // The plate reaches as far as the seven cells do: its edge follows their outer corners.
      const under = BASE - style.floor;
      const cornerOf = (at, corner) => radial(pack.corner(corner)).multiplyScalar(pack.radius).add(at).setY(under);
      const footing = neighbours.flatMap((at, index) => [-1, 0, 1].map((corner) => cornerOf(at, index + corner)));
      ctx.illustrate(new THREE.Mesh(fan(footing), ctx.neutral({ opacity: 0.05, side: THREE.DoubleSide })));
      const tiles = [], lined = new Set();
      for (const at of cells) {
        for (let corner = 0; corner < pack.sides; corner++) {
          const a = cornerOf(at, corner), b = cornerOf(at, corner + 1);
          const key = [a, b].map((point) => `${point.x.toFixed(1)},${point.z.toFixed(1)}`).sort().join("|");
          if (lined.has(key)) continue;
          lined.add(key);
          tiles.push(a, b);
        }
      }
      ctx.illustrate(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(tiles), ctx.neutralLine({ opacity: 0.34 })));
    }
  },
};
