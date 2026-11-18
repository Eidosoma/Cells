// The way into a part of an example from the example's own card (src/ui/viewer.js, runCard), and the
// address's word for it (`part=<entry id>`). A part is a catalogue entry that names the experiment it
// belongs to (`part_of`) and holds the record's words for its picture (`tissue`): today the
// gap-junction example's tissue line (src/lenses/tissue_line.js), shown in the Experiments tab's place.

import { h } from "./dom.js";
import { partsOf } from "../replay/tissue_line.js";
import { mountStyles } from "./entry_views.js";
import { tissueTokens, tissueCss } from "./tissue_styles.js";

/** The part's styles, once: its tokens into the page's document, its rules into the viewer's shadow root. */
export const mountPartStyles = (root, document = globalThis.document) => mountStyles("tissue-line", { page: tissueTokens, shadow: tissueCss }, { root, document });

/** Whether an id names a part the page can show: a catalogue entry with `part_of`, its words and runs. */
export function isPart(raw, id) {
  if (typeof id !== "string" || !id) return false;
  const entry = (raw?.experiments || []).find((item) => item.id === id);
  return Boolean(entry?.part_of) && partsOf(raw, entry.part_of).some((item) => item.id === id);
}

/** The part the Experiments tab opens on: the one its first listed example names (`opens.part`), where it is a part the page can show; else null. */
export function openingPart(raw) {
  const named = (raw?.experiments || []).filter((item) => item.listed === true).map((item) => item.opens?.part).find(Boolean);
  return named && isPart(raw, named) ? named : null;
}

/** The run a part's whole opens on (its first run), for the list's pressed row while the part is shown; null where none. */
export function wholeRunOf(raw, id) {
  const entry = (raw?.experiments || []).find((item) => item.id === id);
  return entry?.part_of ? (raw.runs || []).find((run) => run.experiment === entry.part_of)?.id || null : null;
}

/** The doors to an experiment's parts, for its card: a button each, in the part's own words; none where it has none. */
export function partDoors(raw, experimentId, open, { root = null } = {}) {
  const parts = partsOf(raw, experimentId);
  if (!parts.length) return [];
  mountPartStyles(root);
  return [
    h(
      "div",
      { class: "tissue-part", role: "group", "aria-label": "Part of this example" },
      h("p", { class: "eyebrow" }, parts.length > 1 ? "Parts of this example" : "Part of this example"),
      ...parts.map((part) =>
        h(
          "button",
          { class: "tissue-door", type: "button", dataset: { part: part.id }, "aria-label": `${part.label}. ${part.outcome?.status || ""}`, onclick: () => open(part.id) },
          h("span", { class: "tissue-door-mark", "aria-hidden": "true" }),
          h("span", { class: "tissue-door-words" }, h("span", { class: "tissue-door-title" }, part.short || part.label), h("span", { class: "tissue-door-sub" }, [part.short ? part.label.replace(/^[^:]*:\s*/, "") : "", part.outcome?.status].filter(Boolean).join(" · ")))
        )
      )
    ),
  ];
}
