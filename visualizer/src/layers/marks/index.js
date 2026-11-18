// The marks the viewer has (schema/QUANTITY_LAYERS.md): one small module each. A mark
// says which visual channels it takes and what it is drawn on; `create` builds it for one
// run and gives back { update(step, valid), setStrength?, setColours?, keys?, dispose() }.
//
// Adding a mark is adding one module and its line here. Nothing else in the viewer changes.
//
// The marks of a sheet draw on the lens's own geometry, handed to them as `surface`:
//   cells     per cell: start and walls (where its vertices lie in the sheet's mesh), shade,
//             inset (its corners), centre, radius, height and top (kept current by the relief)
//   geometry  the sheet's mesh: one position and one colour per vertex
//   links     the junctions that can be drawn between two neighbours: { a, b, link, points }
//   pitch     about one cell across; low, high: the heights the sheet has always had;
//   extent    half the sheet's width; root: the group a mark adds its own meshes to
//   outside   where the run's view gives the spaces outside the cells tiles of their own: the
//             tiles ({ inset, centre, start, held }), their mesh and the level they lie at
//   world     the borders between tiles, and where each entity of the run stands (../world.js)
//
// A mark that says `surface: "membrane"` draws on the close-up of one chosen cell's
// membrane instead (../closeup.js), and is built for that membrane when a cell is chosen:
//   root      the group of the piece of membrane: x along it, y through it (up is outside)
//   piece     its measures: width, depth, thick, and reach (how far a full arrow stands out)
//   order     the order its parts are drawn in; label(spec): a label that follows a point of it
//   free      whether a place on it is clear of the close-up's own words

import { tint } from "./tint.js";
import { relief } from "./relief.js";
import { wedge } from "./wedge.js";
import { arrows } from "./arrows.js";
import { stipple } from "./stipple.js";
import { beads } from "./beads.js";
import { stream } from "./stream.js";
import { glow } from "./glow.js";
import { fog } from "./fog.js";
import { network } from "./network.js";

// A mark that says `built: false` has its place and its arithmetic, and does not draw yet:
// a layer that names it is listed for a run with that reason, and cannot be switched on.
// A mark that moves has `tick(milliseconds)`, and one the lens may mark to shine lists what
// shines under `shines`.
export const MARKS = { tint, relief, wedge, network, arrows, stipple, beads, stream, glow, fog };
