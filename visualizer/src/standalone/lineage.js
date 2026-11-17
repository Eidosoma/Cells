// The origin-of-life view standing alone (src/standalone/lineage.page.json says what the page
// carries): an assembly as lipids in water, playing the runs its entry names by the map's page's own
// rule (src/lenses/assembly_run.js, runToPlay: the engine's runs wherever the entry names any, else
// the marked example), with the page's one clock. The view's colour tokens go on the page itself,
// beside the page's own (src/page.css), as the hook-up puts them; its swatches go in with the view's
// styles.

import { mountView } from "./shell.js";
import { LineageLens } from "../lenses/lineage.js";
import { runToPlay } from "../lenses/assembly_run.js";
import { originTokens, originCss } from "../ui/origin_styles.js";

const tokens = document.createElement("style");
tokens.dataset.origin = "tokens";
tokens.textContent = originTokens;
document.head.append(tokens);

mountView({
  make: (stage, model, labels) => new LineageLens(stage, model, labels, runToPlay(model.raw.runs), { entry: model.raw.entry, autoplay: true }),
  styles: originCss,
});
