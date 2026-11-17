// The assembly view (src/lenses/lineage.js) on the map's page: the view of a model system whose
// entry's `view.kind` is "assembly" (schema/MODEL_SYSTEMS.md), registered with the seam in
// src/ui/entry_views.js. Its line in src/ui/model_views.js puts it on the page.
//
// It is made from the entry and its run files as the page has read them: an example run where the
// entry lists one (the page plays the marked example, the user's word of 16 November 2026: "yes lets
// play the marked example"), else the first. The page's controls reach it through the seam: its
// levels on the rail, its timeline, its legend and note, and these choices on its card beyond its
// modes (the packing) and marks (the composition's form): the similarity compared at each fission,
// and the two forms of the law side by side, which the view offers only for two real runs of the
// engine of one world, never for an example (schema/ASSEMBLY_RUN.md).

import { registerEntryView } from "../ui/entry_views.js";
import { LineageLens } from "./lineage.js";
import { originTokens, originCss } from "../ui/origin_styles.js";

/** The run file the view plays: the entry's example where it lists one, else its first. */
export function runToPlay(runs = []) {
  return (runs.find((run) => run.kind === "example") || runs[0])?.data || null;
}

registerEntryView("assembly", {
  // The first tab's name while the view is shown; on a narrow window the short one. The bar keeps to one row with it
  // (the viewer tightens the bar where its words would not fit; tools/check_species.mjs holds it at 390 px).
  label: "Origin of life",
  short: "Origin",
  make: (stage, model, labels, { entry, runs, autoplay }) => new LineageLens(stage, model, labels, runToPlay(runs), { entry, autoplay }),
  choices: {
    compare: (lens, value) => lens.setCompare(value),
    pair: (lens, value) => lens.setPair(value === "pair"),
  },
  styles: { page: originTokens, shadow: originCss },
});
