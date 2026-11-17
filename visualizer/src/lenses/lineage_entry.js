// The assembly view (src/lenses/lineage.js) on the map's page: the view of a model system whose
// entry's `view.kind` is "assembly" (schema/MODEL_SYSTEMS.md), registered with the seam in
// src/ui/entry_views.js. Its line in src/ui/model_views.js puts it on the page.
//
// It is made from the entry and its run files as the page has read them: the engine's runs wherever
// the entry names any (read together, so that two runs of one world, one of each form, stand side by
// side), and the marked example where it names none (the user's word of 16 November 2026: "yes lets
// play the marked example"; the lead's of 17 November: the view opens on a real run wherever the
// entry names one). Going from the example to the engine's runs is data alone: the entry's `runs`.
// The page's controls reach it through the seam: its
// levels on the rail, its timeline, its legend and note, and these choices on its card beyond its
// modes (the packing) and marks (the composition's form): the similarity compared at each fission,
// and the two forms of the law side by side, which the view offers only for two real runs of the
// engine of one world, never for an example (schema/ASSEMBLY_RUN.md).

import { registerEntryView } from "../ui/entry_views.js";
import { LineageLens } from "./lineage.js";
import { mergeRunFiles, runToPlay } from "./assembly_run.js";
import { originTokens, originCss } from "../ui/origin_styles.js";

// What the view plays, chosen and read together in src/lenses/assembly_run.js, so that the page of its own
// (src/standalone/lineage.js) chooses by the same rule.
export { mergeRunFiles, runToPlay };

registerEntryView("assembly", {
  // The first tab's name while the view is shown; on a narrow window the short one. The bar keeps to one row with it
  // (the viewer tightens the bar where its words would not fit; tools/check_species.mjs holds it at 390 px).
  label: "Origin of life",
  short: "Origin",
  make: (stage, model, labels, { entry, runs, autoplay }) => new LineageLens(stage, model, labels, runToPlay(runs), { entry, autoplay }),
  choices: {
    compare: (lens, value) => lens.setCompare(value),
    // The two forms side by side ("pair"), or one run by its id (on a phone, one at a time).
    pair: (lens, value) => lens.setPair(value),
  },
  styles: { page: originTokens, shadow: originCss },
});
