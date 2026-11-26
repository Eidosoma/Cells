import { h, emit } from "../ui/dom.js";
import { engineId } from "./laws_data.js";
import { displayName, modelName, relationLabel } from "./laws_connections.js";
import { NEIGHBOURS_PER_LAYER } from "./laws_atlas_scene.js";

export function control(label, key, options, active, change) {
  const option = ([value, text]) => h("option", { value, selected: value === active }, text);
  const select = h(
    "select",
    {
      class: "run-select",
      dataset: { atlasControl: key },
      "aria-label": label,
      onchange: (event) => {
        const root = event.target.getRootNode();
        change(event.target.value);
        const next = root.querySelector('[data-atlas-control="' + key + '"]');
        const folded = next?.closest("details:not([open])");
        (folded ? folded.querySelector("summary") : next)?.focus({ preventScroll: true });
      },
    },
    options.map(item => Array.isArray(item[1]) ? h("optgroup", {label:item[0]}, item[1].map(option)) : option(item)),
  );
  return h("label", { class: "laws-control" }, h("span", {}, label), select);
}
export const action = (label, key, click, main = false) =>
  h(
    "button",
    { type: "button", class: main ? "laws-action laws-primary" : "laws-action", dataset: { atlasAction: key }, onclick: click },
    label,
  );
const note = (s) => h("p", { class: "laws-guide" }, s);
const tally = (s) => h("p", { class: "laws-tally", "aria-live": "polite" }, s);
const nameRow = (m) => [m.id, modelName(m)];

export function search(view, pieces) {
  const input = h("input", {
    class: "run-select",
    type: "search",
    placeholder: "Find a piece",
    value: view.filter.query,
    "aria-label": "Find a piece",
    dataset: { atlasControl: "search" },
    oninput: (event) => {
      const field = event.target,
        root = field.getRootNode(),
        caret = field.selectionStart;
      view.setQuery(field.value);
      const next = root.querySelector('[data-atlas-control="search"]');
      if (next) {
        next.focus({ preventScroll: true });
        if (caret !== null) next.setSelectionRange(caret, caret);
      }
    },
  });
  if (!view.filter.query) return input;
  const results = pieces.slice(0, 6);
  return h(
    "div",
    { class: "laws-results" },
    input,
    tally(pieces.length + " matching " + (pieces.length === 1 ? "piece" : "pieces")),
    results.map((p) => action(displayName(p.id), "result", () => view.tracePiece(p.id))),
    pieces.length > results.length
      ? control(
          "All matching pieces",
          "matches",
          [["", "Choose a match…"], ...pieces.map((p) => [p.id, displayName(p.id)])],
          "",
          (id) => id && view.tracePiece(id),
        )
      : null,
  );
}
function atlas(view) {
  const { library: l, graph, primary, family } = view,
    pieces = view.filtered();
  const models = l.frames.map(nameRow),
    source = view.anatomy ? view.model.get(view.anatomy) : null;
  const bundle = Array.from(graph.bundles.values()).filter((b) => (!primary || b.model === primary) && (!family || b.family === family));
  const counts = bundle.map((b) => b.entries.filter((e) => view.matches(e.piece)).length).filter(Boolean);
  const example =
    pieces.find((p) => p.id === "site_occupant_replacement@1") || pieces.find((p) => graph.requirements(p).length) || pieces[0];
  return [
    note(
      source
        ? "Mapped from " + source.label + " through the protein inventory."
        : view.filter.box
          ? "Pieces declared in " + (l.inBox(view.filter.box)[0]?.box?.label || view.filter.box) + "."
          : "Choose an island to browse a family, or a bridge to see how a model declares its pieces.",
    ),
    control("Model", "model", [["", "All models"], ...models], primary || "", (id) => view.setPrimary(id)),
    control("Family", "family", [["", "All families"], ...l.families.map((f) => [f.id, f.label])], family || "", (id) => view.setMark(id)),
    tally(counts.length + " bridges · " + counts.reduce((a, b) => a + b, 0) + " memberships"),
    primary
      ? control(
          "Pin a second model",
          "compare",
          [["", "Compare models…"], ...models.filter(([id]) => id !== primary)],
          "",
          (id) => id && view.compareWith(id),
        )
      : null,
    search(view, pieces),
    !view.filter.query && (family || source || view.filter.box)
      ? control(
          "Trace a piece",
          "piece",
          [["", "Choose a piece…"], ...pieces.map((p) => [p.id, displayName(p.id)])],
          "",
          (id) => id && view.tracePiece(id),
        )
      : null,
    !view.filter.query && !family && !source && !view.filter.box && example
      ? action("Trace an example", "example", () => view.tracePiece(example.id), true)
      : null,
    h(
      "details",
      { class: "laws-filters", open: Boolean(view.filter.where) },
      h("summary", {}, "Filter catalogue"),
      control(
        "Catalogue entries",
        "origin",
        [["all", "All entries"], ["declared", "Declared pieces"], ["design", "Design notes"]],
        view.filter.where || "all",
        (id) => view.setMode(id),
      ),
    ),
    source
      ? action("Return to " + source.label, "scope", () => emit(view.stage.canvas, "cells-door", { lens: "cell", select: source.id }))
      : null,
  ];
}
function wiring(view) {
  const p = view.library.piece(view.trace),
    rows = view.traceRows,
    groups = view.traceGroups();
  const verbs = [...new Set(rows.map((e) => (e.layer === "models" ? "models" : e.verb)))];
  const words = {
    models: "Model membership",
    requires: "Requires",
    requiredBy: "Required by",
    reads: "Reads",
    writes: "Writes",
    ledgers: "Ledgers",
    provides: "Provides",
    owns: "Owned state",
    conflicts: "Incompatible operators",
  };
  const pages = Math.max(1, ...Object.values(groups).map((g) => Math.ceil(g.length / NEIGHBOURS_PER_LAYER)));
  const neighbours = view.traceLayers();
  const opts = Object.values(neighbours)
    .flat()
    .filter((e) => e.id)
    .map((e) => [e.id, (words[e.verb] || relationLabel[e.verb]) + " · " + e.label]);
  return [
    h("p", { class: "laws-subject" }, displayName(p.id)),
    note(
      p.declared
        ? "Follow a connection, or separate the layers to see where it ends."
        : "This piece is named in a design note. Its connections await a declaration.",
    ),
    rows.length
      ? control(
          "Connections",
          "relation",
          [["main", "Main connections"], ["all", "All connections"], ...verbs.map((v) => [v, words[v]])],
          view.relation,
          (id) => {
            view.relation = id;
            view.page = 0;
            view.notice();
          },
        )
      : null,
    rows.length
      ? h(
          "label",
          { class: "laws-control" },
          h("span", {}, "Layer spacing"),
          h("input", {
            type: "range",
            min: 1.6,
            max: 3.6,
            step: 0.1,
            value: view.spread,
            "aria-label": "Layer spacing",
            dataset: { atlasControl: "spread" },
            oninput: (e) => {
              view.spread = Number(e.target.value);
              view.rebuild();
            },
            onchange: () => view.fit(true),
          }),
        )
      : null,
    opts.length
      ? control("Inspect a connection", "neighbour", [["", "Choose a connection…"], ...opts], "", (id) => {
          if (id && !view.openOnMap(id)) view.selectOnPage(id);
        })
      : null,
    pages > 1
      ? control(
          "Page of connections",
          "page",
          Array.from({ length: pages }, (_, i) => [String(i), i + 1 + " of " + pages]),
          String(view.page),
          (v) => {
            view.page = Number(v);
            view.notice();
          },
        )
      : null,
    tally(Object.values(neighbours).flat().length + " of " + rows.length + " connections shown"),
    action("Read declaration", "declaration", () => view.selectOnPage("laws:" + p.id)),
  ];
}
function comparison(view) {
  const { library: l, primary, other } = view,
    groups = view.graph.compare(primary, other);
  const selected = l.piece(engineId(view.selected));
  return [
    note("The centre holds the shared pieces. Each outer ring holds the pieces unique to that model."),
    control("First model", "model", l.frames.filter((f) => f.id !== other).map(nameRow), primary, (id) => view.setPrimary(id)),
    control("Second model", "compare", l.frames.filter((f) => f.id !== primary).map(nameRow), other, (id) => view.compareWith(id)),
    h(
      "div",
      { class: "laws-sets" },
      ["First only", "Shared", "Second only"].map((name, i) => h("div", {}, h("strong", {}, groups[i].length), h("span", {}, name))),
    ),
    control(
      "Inspect a piece",
      "piece",
      [
        ["", "Choose a piece…"],
        ...groups.flatMap((list, i) => list.map((p) => [p.id, ["First only", "Shared", "Second only"][i] + " · " + displayName(p.id)])),
      ],
      selected?.id || "",
      (id) => id && view.selectOnPage("laws:" + id),
    ),
    selected ? action("Trace its connections", "trace", () => view.tracePiece(selected.id), true) : null,
  ];
}
export function atlasControls(view) {
  const body = view.mode === "atlas" ? atlas(view) : view.mode === "wiring" ? wiring(view) : comparison(view);
  return [h("div", { class: "laws-navigation" }, body)];
}
