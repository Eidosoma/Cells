// The part modules of the cell's builder, in the order buildCell (cell_parts.js) calls them.
//
// The order is the builder's own, and it matters: the modules draw from the layout's one
// stream of chance in this order, and the lens writes the names of the parts in the order
// they are first asked for. A module that moves, or is added before another, moves what
// comes after it; tests/cell_build.test.mjs holds the picture to that. A new part is added
// after the others, from a stream of chance of its own, as the structures and the scenery are.
//
// Each module is { kind, draws, build(env) }: `kind` its name, `draws` the map's part names it
// asks the lens for (through ctx.part), and `build` draws through env.ctx and env.studsCtx
// from env.layout, may set what the lens moves in env.handles, and returns what later parts
// and the builder read (into env.built).

import membrane from "./membrane.js";
import surface from "./surface.js";
import junctions from "./junctions.js";
import cutAway from "./cut-away.js";
import cytoplasm from "./cytoplasm.js";
import structures from "./structures.js";
import genome from "./genome.js";
import mitochondria from "./mitochondria.js";
import machines from "./machines.js";
import water from "./water.js";
import wound from "./wound.js";
import furrow from "./furrow.js";
import secretion from "./secretion.js";
import extracellular from "./extracellular.js";
import scenery from "./scenery.js";

export const CELL_PARTS = [membrane, surface, junctions, cutAway, cytoplasm, structures, genome, mitochondria, machines, water, wound, furrow, secretion, extracellular, scenery];
