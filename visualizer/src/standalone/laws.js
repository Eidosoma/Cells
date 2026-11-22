// The Laws library standing alone (src/standalone/laws.page.json says what the page carries):
// the view as the viewer will hold it, with its legend's swatches.

import { mountView } from "./shell.js";
import { makeLawsView } from "../lenses/laws_atlas.js";
import { LAWS_CSS } from "../lenses/laws_styles.js";

mountView({ make: makeLawsView, styles: LAWS_CSS });
