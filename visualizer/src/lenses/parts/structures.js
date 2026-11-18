// The nucleus, the ER, the Golgi, the vesicles and the ribosomes (cell_structures.js, called
// as it is, from its own stream of chance). It hands on what it built, for the probes, and the
// scenery it drew that can be chosen (an animal cell's centrosome), which the scenery part lists.
//
// A part module of the cell's builder (parts/index.js), moved unchanged from buildCell in
// cell_parts.js. It draws through the lens's context, from the layout (cell_layout.js).
// It draws from a stream of chance of its own, so it moves no other part.

import { CUT } from "../cell_layout.js";
import { seeded, instanced, dots } from "./geometry.js";
import { buildStructures } from "../cell_structures.js";

export default {
  kind: "structures",
  draws: ["nucleus", "chromatin", "er", "golgi", "vesicles", "ribosomes"],
  build(env) {
    const { ctx, handles } = env;
    const { mode, real, style, has, parts, organelle, frame, outline, inside, inCytoplasm, NUCLEUS, ER_FACING, GOLGI, CENTROSOME, vacuole, coreAt, coreRadius, coreReach, fine, nm, slab, ribosome, ribosomeFactor } = env.layout;
    // The middle of what regulation acts on (the nucleus, or the free chromosome) is the layout's `core`.
    const structures = buildStructures({
      ctx, mode, real, style, frame, parts, has, organelle, cut: CUT, outline, inside, inCytoplasm, instanced, dots,
      nucleusAt: parts.nucleus ? NUCLEUS : null, erFacing: ER_FACING, golgiAt: GOLGI, centrosomeAt: CENTROSOME, vacuole, core: { at: coreAt, radius: coreRadius, reach: coreReach },
      random: seeded(real ? 3103 : 3101),
      fine, nm, slab, // a cell drawn to scale whose molecules are shapes (cell_layout.js): its free chromosome is drawn in the slab under the cut
      ribosome, ribosomeFactor, // a ribosome's measured shape (the species' `ribosome`) and how much this mode enlarges it
    });
    handles.structures = structures.drawn; // what the panel says was drawn of each, by part
    return { structures };
  },
};
