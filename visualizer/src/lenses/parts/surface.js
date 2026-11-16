// The channels and pumps: set in the cut edge, and over the rest of the membrane as pores and
// domes, or to scale as dots.
//
// A part module of the cell's builder (parts/index.js), moved unchanged from buildCell in
// cell_parts.js. It draws through the lens's context, from the layout (cell_layout.js).
// It takes from the layout's one stream of chance, in the builder's fixed order.

import * as THREE from "../../three.js";
import { CUT, SPOT } from "../cell_layout.js";
import { turnY, instanced, dots } from "./geometry.js";

export default {
  kind: "surface",
  draws: ["channels", "pumps"],
  build(env) {
    const { ctx, studsCtx } = env;
    const { real, has, outline, onSkin } = env.layout;
    const channels = has("channels") ? ctx.part("channels", outline.point(SPOT.channels[3], 0.5, CUT + 0.5)) : null;
    const pumps = has("pumps") ? ctx.part("pumps", outline.point(SPOT.pumps[1], 0.5, CUT + 0.5)) : null;
    if (!real) {
      // Set in the cut edge: each channel is two walls with a pore between; each pump a lobed block.
      if (channels) {
        const wall = new THREE.CapsuleGeometry(0.17, 0.62, 6, 12).rotateZ(Math.PI / 2); // long axis along x
        const walls = [];
        for (const angle of SPOT.channels) {
          for (const offset of [-0.25, 0.25]) walls.push({ position: outline.walk(angle, offset, -0.1, CUT + 0.07), turn: turnY(-outline.facing(angle, offset)) });
        }
        channels.add(instanced(wall, channels.material({ hue: "bioProtein", roughness: 0.35, thin: 0.3 }), walls));
      }
      if (pumps) {
        const lobes = pumps.material({ hue: "bioPump", roughness: 0.35, thin: 0.35 });
        for (const angle of SPOT.pumps) {
          const outer = new THREE.Mesh(new THREE.SphereGeometry(0.46, 18, 14), lobes);
          outer.position.copy(outline.point(angle, -0.05, CUT + 0.08));
          outer.scale.set(1, 0.85, 1);
          const inner = new THREE.Mesh(new THREE.SphereGeometry(0.32, 16, 12), lobes);
          inner.position.copy(outline.point(angle, -0.62, CUT));
          pumps.add(outer, inner);
        }
      }
      // And over the rest of the membrane: pores and low domes.
      if (channels) {
        const exteriorChannels = studsCtx.part("channels");
        exteriorChannels.add(
          instanced(new THREE.TorusGeometry(0.3, 0.1, 8, 18).rotateX(Math.PI / 2), exteriorChannels.material({ hue: "bioProtein", roughness: 0.4 }), onSkin(30, 2.2))
        );
      }
      if (pumps) {
        const exteriorPumps = studsCtx.part("pumps");
        exteriorPumps.add(
          instanced(new THREE.SphereGeometry(0.44, 16, 12).scale(1, 0.6, 1), exteriorPumps.material({ hue: "bioPump", roughness: 0.4, thin: 0.35 }), onSkin(12, 4))
        );
      }
    } else {
      // At this scale a channel is about 10 nm across: far too small to see. Thousands of them
      // are drawn as dots; the close-up of the membrane shows them as shapes.
      if (channels) {
        const dust = studsCtx.part("channels");
        dust.add(dots(onSkin(4200).map((spot) => spot.position), dust.points({ hue: "bioProtein", size: 1.9 })));
      }
      if (pumps) {
        const pumpDust = studsCtx.part("pumps");
        pumpDust.add(dots(onSkin(2400).map((spot) => spot.position), pumpDust.points({ hue: "bioPump", size: 1.9 })));
      }
    }
  },
};
