// A model system's card, as a view of its own (schema/MODEL_SYSTEMS.md): what the viewer shows
// for a model system whose view (`view.kind`) is not on the page yet. It draws nothing in 3D. Its
// card and its panel say what the entry is ("a model, not an organism"), what Cells models of it
// in the ladder's words, the levels it has and what each will show, and what the words rest on;
// its rail steps through the levels, each opening its panel. It names no model in its code: all
// of it is the entry's.
//
// A view that draws a model system (src/ui/entry_views.js, `registerEntryView`) takes its place
// for the kinds it draws; until its run files arrive, this card stands in, saying so.

import * as THREE from "../three.js";
import { MODELLED } from "../scene/entries.js";

/** The id of the entry's own panel, and of each of its levels'. */
export const entryId = (entry) => `model:${entry.id}`;
export const levelId = (entry, level) => `model:${entry.id}:level:${level}`;

export class EntryCardLens {
  /** `waiting`: what the page is waiting for, where the entry's own view is on its way (its run files). */
  constructor(stage, model, labels, entry, { waiting = null, failed = null } = {}) {
    this.id = "model";
    this.stage = stage;
    this.model = model;
    this.labels = labels;
    this.entry = entry;
    this.waiting = waiting;
    this.failed = failed;
    this.root = new THREE.Group();
    this.level = entry.levels.some((level) => level.id === "assembly") ? "assembly" : entry.levels[0]?.id;
    this.selected = null;
    this.active = false;
  }

  get pickRoots() {
    return [this.root];
  }

  get word() {
    return MODELLED[this.entry.modelled?.state] || this.entry.modelled?.state || "";
  }

  activate() {
    this.active = true;
    this.stage.scene?.add?.(this.root);
    this.labels?.clear?.();
    this.stage.invalidate?.();
  }

  deactivate() {
    this.active = false;
    this.stage.scene?.remove?.(this.root);
    this.labels?.clear?.();
  }

  setSpecies() {}
  setAtlas() {}
  setIsolate() {}
  setHover() {}
  focus() {}
  update() {
    return false;
  }
  applyPalette() {}
  dispose() {}

  setSelection(id) {
    this.selected = this.has(id) ? id : null;
  }

  /** A level of the rail: it becomes the one shown, and its panel opens. */
  goToScale(id) {
    if (!this.entry.levels.some((level) => level.id === id)) return;
    this.level = id;
    this.levelChosen = true; // a level the visitor or the address chose: the entry's own view opens on it
    this.onChrome?.();
    this.onShown?.(levelId(this.entry, id));
  }

  has(id) {
    return Boolean(id) && (id === entryId(this.entry) || this.entry.levels.some((level) => id === levelId(this.entry, level.id)));
  }

  /** The sources of the record behind its word, as the panel lists them: a tracked file and where in it. */
  record() {
    return (this.entry.modelled?.record || []).map((item) => ({ label: item.path, lines: [item.where].filter(Boolean) }));
  }

  describe(id) {
    const entry = this.entry, chips = [{ label: this.word, title: "What Cells models of it" }, { label: entry.is }];
    const level = entry.levels.find((item) => id === levelId(entry, item.id));
    if (level) {
      return {
        id, kind: "level", group: "biology", label: level.label, eyebrow: `${entry.label} · level`, chips,
        plain: level.shows || "",
        note: level.waits ? `It waits for ${level.waits}.` : null,
        sections: [{ title: "Its view", items: [{ label: "Not on this page yet", lines: [this.waitingWords()] }] }],
      };
    }
    if (id !== entryId(entry)) return null;
    const sources = entry.sources || {};
    const links = (keys) => (keys || []).map((key) => sources[key]).filter(Boolean).map((source) => ({ text: source.text, url: source.doi ? `https://doi.org/${source.doi}` : source.url }));
    return {
      id, kind: "model system", group: "biology", label: entry.label, eyebrow: "Model system", chips,
      plain: entry.modelled?.text || "",
      note: entry.plain,
      sections: [
        { title: "Its levels", note: "A model system has levels of its own, not a cell's.", items: entry.levels.map((item) => ({ label: item.label, lines: [item.shows, item.waits ? `It waits for ${item.waits}.` : null].filter(Boolean) })) },
        { title: "What it is", items: (entry.facts || []).map((fact) => ({ label: fact.label, detail: fact.value, links: links(fact.sources) })) },
        // Its sourced notes (schema/ENTRIES.md, "Notes"), word for word, each with what it cites.
        { title: "Notes", items: (entry.notes || []).map((note) => ({ label: note.label, lines: [note.text], note: `It rests on ${(note.record || []).map((item) => `${item.path} (${item.where})`).join("; ")}.` })) },
        { title: "What the word rests on", note: "Tracked files of the engine's main, or the viewer's own notes.", items: this.record() },
      ].filter((section) => section.items.length),
    };
  }

  waitingWords() {
    if (this.failed) return `Its view could not be shown: ${this.failed}`;
    if (this.waiting) return `Its view is on its way: ${this.waiting}.`;
    return "The view that draws it is not on this page yet. The page shows what it is, its levels and what Cells models of it.";
  }

  sections() {
    return [
      { label: "Levels", entities: this.entry.levels.map((level) => this.describe(levelId(this.entry, level.id))) },
      { label: "Model system", entities: [this.describe(entryId(this.entry))] },
    ];
  }

  entities() {
    return this.sections().flatMap((section) => section.entities);
  }

  chrome() {
    const entry = this.entry;
    const runs = entry.runs || [];
    return {
      caveat: `${entry.label}: ${this.word.charAt(0).toLowerCase()}${this.word.slice(1)}. ${this.failed || this.waiting ? this.waitingWords() : "Its view is not on this page yet."}`,
      // It draws nothing, so no colours or statuses of parts to explain.
      legend: false,
      rail: entry.levels.map((level) => ({ id: level.id, label: level.label, title: level.shows || "" })),
      railActive: this.level,
      railTitle: "Level",
      card: {
        heading: entry.label,
        species: null, // the viewer puts the page's switch here (src/ui/entry_views.js)
        organism: entry.is,
        notice: this.failed || this.waiting ? this.waitingWords() : null, // else the caveat under the picture says it, and the card stays short on a phone
        stats: [[entry.levels.length, entry.levels.length === 1 ? "level" : "levels"], [runs.length, runs.length === 1 ? "run" : "runs"]],
        text: entry.plain,
        sources: Object.values(entry.sources || {}).map((source) => ({ name: source.text.split(".")[0], url: source.doi ? `https://doi.org/${source.doi}` : source.url, licence: source.licence, accessed: source.accessed })),
      },
    };
  }
}
