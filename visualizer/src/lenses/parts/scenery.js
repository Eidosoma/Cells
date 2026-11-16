// The species' own scenery (cell_scenery.js, called as it is, from its own stream of chance):
// threads and hairs, a plant cell's vacuole and chloroplasts. Built last.
//
// A part module of the cell's builder (parts/index.js), moved unchanged from buildCell in
// cell_parts.js. It draws through the lens's context, from the layout (cell_layout.js).
// It draws from a stream of chance of its own, so it moves no other part.

import { CUT } from "../cell_layout.js";
import { seeded, instanced, fan } from "./geometry.js";
import { buildScenery } from "../cell_scenery.js";

export default {
  kind: "scenery",
  draws: [],
  build(env) {
    const { ctx, built } = env;
    const { real, parts, frame, prism, inCut, vacuole, skinAt, uncutSide } = env.layout;
    // Threads and hairs that stand out from the cell, and a plant cell's vacuole and chloroplasts
    // (cell_scenery.js). Drawn last and from a stream of chance of their own, so that a cell
    // without them is built exactly as before. They can be chosen: the lens describes each.
    const scenery = buildScenery({
      frame, u: frame.u, real, cut: CUT, parts, vacuole, inCut,
      random: seeded(real ? 4203 : 4201),
      skinAt, solid: prism, instanced, fan,
      shells: built.shells,
      thinnest: 0.035, // no thread is drawn thinner than this, in the cell's frame: a cell of twenty micrometres has threads one can see
      clear: [uncutSide], clearBy: 1.6,
      glass: (options) => ctx.neutral(options),
      line: (options) => ctx.neutralLine(options),
      add: (object, id) => (id ? ctx.scenery(object, id) : ctx.illustrate(object)),
    });
    return { scenery };
  },
};
