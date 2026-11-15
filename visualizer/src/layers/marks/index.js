// The marks the viewer has (schema/QUANTITY_LAYERS.md): one small module each. A mark
// says which visual channels it takes and what it is drawn on; `create` builds it for one
// run and gives back { update(step, valid), setStrength?, setColours?, dispose() }.
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

import { tint } from "./tint.js";
import { relief } from "./relief.js";
import { wedge } from "./wedge.js";

export const MARKS = { tint, relief, wedge };
