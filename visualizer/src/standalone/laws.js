// The Laws library standing alone (src/standalone/laws.page.json says what the page carries):
// the view as the viewer will hold it, with its legend's swatches.

import { mountView } from "./shell.js";
import { LawsLens } from "../lenses/laws.js";
import { LAWS_CSS } from "../lenses/laws_styles.js";

mountView({ make: (stage, model, labels) => new LawsLens(stage, model, labels), styles: LAWS_CSS });
