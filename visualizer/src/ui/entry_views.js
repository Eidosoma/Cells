// The seam by which the viewer hands a model system to the view that draws it (schema/ENTRIES.md,
// "What a view gets from an entry"; schema/MODEL_SYSTEMS.md, `view.kind`).
//
// A model system chosen in the species switch is shown in the place of the Cell view: the first
// tab takes the view's name, and the view is made from the entry and its run files. A view does
// not know the viewer: a small registration, written beside it, says how to make it and how the
// viewer's controls reach it.
//
//   registerEntryView("assembly", {
//     label: "One assembly", short: "Assembly",      // the first tab's name while it is shown (short: on a narrow window)
//     make: (stage, model, labels, { entry, runs, autoplay }) =>
//       new SomeLens(stage, model, labels, runs[0].data, { entry, autoplay }),
//     choices: { pair: (lens, value) => lens.setPair(value === "pair") }, // card keys beyond modes and marks
//     styles: { page: TOKENS, shadow: RULES },         // CSS for the page's document, and for the viewer's shadow root
//   });
//
// What the viewer gives the view, and where:
//   - `entry`: the scene's block for the model system (tools/lib/entries.py): id, label, `is`,
//     group, levels (id, label, shows, waits), view, clock, runs, modelled (state, text, record,
//     design), facts, sources and notes.
//   - `runs`: its run files as read, each { file, label, kind, path, data }, in the entry's order;
//     `data` is the file's JSON, fetched beside the page at `path` (models/<id>/<name>.json), or
//     read from the page where it was built with its files inside.
//   - `autoplay`: true unless the page is held still (`still=1`); a view still honours reduced
//     motion itself.
//   - The frame's times: the viewer's tick calls `update(dt, time, real)` on the view shown.
//   - Its chrome, as the other lenses': `caveat`, `card`, `legend` (false for none; a `note` is
//     always shown), `timeline` ({ player, eventWord }, bound to the page's one timeline, whose
//     space bar plays and pauses a player with a run) and `stamp`. Its levels go on the page's
//     rail, under "Level": the chrome's `rail` where it gives one, else its `levels()` (each
//     { id, label, active }), chosen with `setLevel(id)`. Its card's `modes` and `marks` are the
//     card's own controls (`setMode`, `setMark`); any other choice the registration names in
//     `choices` (a card key holding { label, options, active }) becomes a choice on the card too.
//     The viewer puts the page's switch into its card, and the model system's word beside it;
//     where the view's chrome gives no caveat, no status and no timeline, the line under the
//     picture gives that word ("<label>: designed, not modelled.").
//   - The entry's own panel and its levels' panels (`model:<id>`, `model:<id>:level:<level>`)
//     stay the entry card's, and are listed after the view's own sections: the statement beside
//     the switch opens them whatever view is shown.
//   - Its styles: `styles.page` once into the page's document (tokens on :root), and
//     `styles.shadow` once into the viewer's shadow root.
//
// A registration is put on the page by one import line in src/ui/model_views.js, which the
// viewer imports; nothing in the viewer names a view of a model system.
//
// Until a view's run files are read, and for good where no view is registered for the kind, the
// entry's card stands in (src/lenses/entry_card.js): what the entry is, its levels, its word.

import { EntryCardLens, entryId } from "../lenses/entry_card.js";
import { MODELLED } from "../scene/entries.js";
import { loadBeside } from "../lenses/protein_shelves.js";

const VIEWS = new Map();

/** Register the view that draws model systems of one `view.kind`. A second registration of a kind replaces the first. */
export function registerEntryView(kind, view) {
  if (!kind || typeof view?.make !== "function") throw new Error("a model system's view is registered with its kind and a make()");
  VIEWS.set(kind, view);
}

/** The view registered for a kind, or null. */
export const entryView = (kind) => VIEWS.get(kind) || null;

/** The name of the first tab while this entry is shown: its view's, or the card's. */
export function entryTab(entry) {
  const view = entryView(entry?.view?.kind);
  return { label: view?.label || "Model system", short: view?.short || "Model" };
}

/** A registration's styles, each put in once: its tokens into the page's document, its rules into the viewer's shadow root. */
export function mountStyles(kind, styles, { root = null, document = globalThis.document } = {}) {
  const put = (where, text) => {
    if (!where || !text || where.querySelector?.(`style[data-entry-view="${kind}"]`)) return;
    const style = (document || where.ownerDocument).createElement("style");
    style.dataset.entryView = kind;
    style.textContent = text;
    where.append(style);
  };
  put(document?.head, styles?.page);
  put(root, styles?.shadow);
}

const nothing = () => {};

/**
 * A made view fitted to the viewer's lens interface, without its knowing the viewer: its levels on
 * the rail, the registration's choices on its card, what its card does not give filled in, and
 * the calls the viewer makes of every lens answered. Returns the same object.
 */
export function fitView(view, entry, registration = {}) {
  const own = typeof view.chrome === "function" ? view.chrome.bind(view) : () => ({});
  view.chrome = () => fitChrome(own() || {}, view, entry, registration);
  if (typeof view.goToScale !== "function") view.goToScale = (id) => view.setLevel?.(id);
  for (const name of ["setHover", "setIsolate", "setSelection", "setSpecies", "setAtlas", "focus", "applyPalette"]) if (typeof view[name] !== "function") view[name] = nothing;
  // The entry's own panels stay its card's, beside what the view describes of its own.
  const card = entry?.levels?.length ? new EntryCardLens(null, null, null, entry, { shown: registration.label || null }) : null;
  const has = typeof view.has === "function" ? view.has.bind(view) : () => false;
  const describe = typeof view.describe === "function" ? view.describe.bind(view) : () => null;
  const sections = typeof view.sections === "function" ? view.sections.bind(view) : () => [];
  view.has = (id) => Boolean(card?.has(id)) || has(id);
  view.describe = (id) => (card?.has(id) ? card.describe(id) : describe(id));
  view.sections = () => [...sections(), ...(card ? [{ label: "Model system", entities: [card.describe(entryId(entry))] }] : [])];
  // What the card answers for is never the view's own selection or hover: the view is told nothing is chosen.
  for (const name of ["setSelection", "setHover"]) {
    const set = view[name].bind(view);
    view[name] = (id, ...rest) => set(card?.has(id) ? null : id, ...rest);
  }
  if (typeof view.entities !== "function") view.entities = () => view.sections().flatMap((section) => section.entities || []);
  if (typeof view.update !== "function") view.update = () => false;
  if (!("pickRoots" in view)) view.pickRoots = view.root ? [view.root] : [];
  return view;
}

function fitChrome(chrome, view, entry, registration) {
  const out = { ...chrome };
  const word = MODELLED[entry?.modelled?.state] || "";
  // Not over a timeline, which stands where the caveat does: the statement beside the switch gives the word there.
  if (!out.caveat && !out.status && !out.timeline && entry && word) out.caveat = `${entry.label}: ${word.charAt(0).toLowerCase()}${word.slice(1)}.`;
  if (!out.rail && typeof view.levels === "function") {
    const levels = view.levels() || [];
    if (levels.length) {
      out.rail = levels.map((level) => ({ id: level.id, label: level.label, title: entry?.levels?.find((item) => item.id === level.id)?.shows || "" }));
      out.railActive = levels.find((level) => level.active)?.id ?? levels[0].id;
    }
  }
  if (out.rail) out.railTitle ||= "Level";
  if (chrome.card) {
    const card = chrome.card;
    const choices = Object.entries(registration.choices || {})
      .filter(([key, set]) => card[key]?.options?.length && typeof set === "function")
      .map(([key, set]) => ({ key, label: card[key].label, options: card[key].options, active: card[key].active, set: (value) => set(view, value) }));
    out.card = {
      ...card,
      organism: card.organism ?? entry?.is ?? null,
      stats: card.stats || [],
      // A source of the project's record ({path, where}) is listed by its path, with where in it.
      sources: (card.sources || []).map((source) => (source.path && !source.name ? { name: source.path, licence: source.where || "" } : source)),
      choices: [...(card.choices || []), ...choices],
    };
  }
  return out;
}

/**
 * The lens for a model system: its card at once, and, where a view is registered for its kind,
 * a promise of that view, fitted, once the run files are read (`ready`, null where there is none).
 * A run file that cannot be read leaves the card standing, saying why.
 */
export function makeEntryLens(stage, model, labels, entry, { loader = loadBeside, root = null, document = globalThis.document, autoplay = true } = {}) {
  const kind = entry?.view?.kind;
  const view = entryView(kind);
  const runs = entry?.runs || [];
  if (!view) return { lens: new EntryCardLens(stage, model, labels, entry), ready: null };
  const card = new EntryCardLens(stage, model, labels, entry, { waiting: runs.length ? `${runs.length === 1 ? "its run file is" : `its ${runs.length} run files are`} being read` : null });
  const ready = Promise.all(runs.map(async (run) => ({ ...run, data: await loader(run.path) })))
    .then((read) => {
      mountStyles(kind, view.styles, { root, document });
      return fitView(view.make(stage, model, labels, { entry, runs: read, autoplay }), entry, view);
    })
    .catch((error) => {
      card.failed = String(error?.message || error);
      card.waiting = null;
      card.onChrome?.();
      return null;
    });
  // The card answers for the view while it waits: what waits on the lens shown (the address's select=, a check) waits for the view.
  card.ready = ready;
  return { lens: card, ready };
}
