// The views of model systems that the page offers (schema/MODEL_SYSTEMS.md, `view.kind`): one
// import for each, of the file beside the view that registers it with src/ui/entry_views.js
// (`registerEntryView`). The viewer imports this list once; a view is added to the page by a
// line here, and by nothing in the viewer. A kind with no view here is shown by its card
// (src/lenses/entry_card.js).
//
//   import "../lenses/<view>_entry.js";

import "../lenses/lineage_entry.js";
import "../lenses/vesicle.js";
import "../lenses/physarum.js";
import "../lenses/haloferax.js";
