// What the page's panel and list say of the Laws library's parts (schema/LAWS_LIBRARY.md,
// "What the view may say"): what the engine's declarations manifest states of a piece or a
// model, in plain words, and no more. The shapes are the ones every view hands to <cells-panel>
// and <cells-index>; nothing here is new to the page.

import { Library, PREFIX, WHERE, FAMILY, pageId, engineId, namespaced, interfaceWords, isId } from "./laws_data.js";
import { portLines, portTable } from "./law_port.js";

/** A piece's swatch in the list and the panel: the mark it is drawn with on the wall (laws.js MARKS, laws_styles.js). */
export function swatchOf(piece) {
  return piece?.where === "design" ? "laws-design" : "laws-declared";
}

const whereWords = (piece) => WHERE.find((item) => item.id === piece.where)?.label || piece.where;
const list = (value) => (Array.isArray(value) ? value.join(", ") : String(value));

/** The words for each meaning of null (the format page, "The three meanings of null"); not applicable says nothing. */
export const NULL_WORDS = { "not extracted": "not yet extracted in the engine's declarations", "not stated": "not stated" };
/** An empty list or object: the declaration lists none. */
export const NONE_WORDS = "the declaration lists none";

/** The words of a provenance tag (the format page, "Provenance keys"). */
export const TAGS = { parity: "moved from an older family (moving is not calibrating)", cited: "cited", calibrated: "calibrated" };

/** The piece keys a panel says, in the format page's order, with the words it says them in. */
const KEY_WORDS = {
  kernels: "Kernels",
  provenance: "Provenance",
  test: "Test",
  reads: "Reads",
  changes: "Changes",
  owns: "Owns",
  writes: "Writes",
  provides: "Provides",
  controls: "Controls",
  ledgers: "Ledgers",
  energy: "Energy",
  units: "Units",
  signs: "Signs",
  requires: "Requires",
  laws: "Laws it hosts",
};

/** What a nested field's null means, where the format page gives it a meaning of its own. */
const FIELD_NULLS = {
  rk4_step_s: "none: a law with no gate",
  loop_term: "none",
  stage_term: "none",
  step_method: "none",
};

/** Each interface's own fields as the format page names them ("Each interface's own fields"). */
const FIELD_WORDS = {
  code: "Code",
  gates: "Gates",
  permeant: "Permeant ions",
  voltage_domain_V: "Voltage domain",
  rk4_step_s: "Reference RK4 step bound",
  stage_term: "Stage term",
  loop_term: "Loop term",
  moves: "Moves per forward cycle",
  fuel_kinds: "Fuel kinds",
  hosts: "Hosts",
  basis: "Basis",
  ligands: "Ligands",
  gated: "Gated",
  max_abs_voltage_V: "Largest voltage across a junction",
  model_key: "Definition key",
  layout_fields: "Layout fields",
  experiment_keys: "Experiment keys",
  hooks: "Hooks",
  record_kinds: "Record kinds",
  record_layers: "Record layers",
  parts: "Parts of the step",
  declaration_only: "Declaration only",
  step_method: "Step method",
  closes: "Closes",
  retires: "Retires slots",
  class_name: "Class",
};

/** A value as plain words: a list joined, a pair of numbers as a range, true and false as yes and no. */
function words(key, value, units = {}) {
  if (value === null || value === undefined) return FIELD_NULLS[key] || "not given";
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (key === "voltage_domain_V" && Array.isArray(value)) return `${value[0]} to ${value[1]} V`;
  if (key === "permeant" && Array.isArray(value)) return value.map(([species, valence, relative]) => `${species} (valence ${valence}, relative permeability ${relative})`).join(", ");
  if (key === "moves" && Array.isArray(value)) return value.map(([role, count]) => `${role} ${count}`).join(", ");
  if (Array.isArray(value)) return value.length ? value.map((item) => (typeof item === "object" ? JSON.stringify(item) : String(item))).join(", ") : NONE_WORDS;
  if (typeof value === "object") {
    const entries = Object.entries(value);
    return entries.length ? entries.map(([name, item]) => `${name}: ${typeof item === "object" ? JSON.stringify(item) : item}`).join("; ") : NONE_WORDS;
  }
  const unit = units[key];
  return unit && typeof value === "number" ? `${value} ${unit}` : String(value);
}

/**
 * The manifest's revision for a link, and the words beside it where the map's is another: a file
 * the manifest names is there by construction at the revision it was written from.
 */
function linkAt(library, map) {
  const revision = library.manifest.revision;
  const same = map && ((map.source_base_url || "").includes(`/blob/${revision}/`) || (map.revision && revision.startsWith(map.revision)));
  return { revision, words: same ? "" : `, as declared at main ${library.manifest.short}` };
}

/**
 * The panel's entity for a piece, a model, a row with no piece, a legacy model ID or any other
 * ID, by its page id; null for anything else. `drawn(boxId)`: whether the page draws that Engine
 * view box; where the page has no Engine view (the view standing alone) it is not given, and no
 * box is linked. `map`: the page's scene meta, whose revision the words beside a link compare with.
 */
export function describe(library, id, { drawn = null, map = null } = {}) {
  const name = engineId(id);
  if (!name) return null;
  const piece = library.piece(name);
  if (piece) return piece.where === "design" ? describeDesigned(library, piece, map) : describePiece(library, piece, drawn, map);
  const frame = library.frame(name);
  if (frame) return describeModel(library, frame, drawn, map);
  const row = library.rowOf(name);
  if (row) return describeRow(library, row);
  const legacy = library.legacyOf(name);
  if (legacy) return notice(name, `The engine's declarations list ${legacy.id} among the older model families: legacy code, to be dropped, with no page of its own. The map does not show it.`, "Legacy code; not shown");
  return isId(name) ? notice(name, `The engine's declarations do not list ${name}: no active registry declares it, so the map does not show it.`, "Not declared") : null;
}

function notice(id, plain, chip) {
  return { id: pageId(id), label: id, kind: "not shown", eyebrow: "Laws library · not shown", status: null, chips: [{ label: chip }], plain, facts: [], sources: [] };
}

/** A key of a piece, said as the manifest states it: its value, an empty list, or the meaning of its null. Null where nothing is said. */
function stated(library, piece, key) {
  const value = piece.declared[key];
  if (value === null || value === undefined) {
    const meaning = library.nullMeaning(piece, key);
    return meaning === "not applicable" ? null : { meaning, words: NULL_WORDS[meaning] };
  }
  if (Array.isArray(value) ? !value.length : typeof value === "object" && !Object.keys(value).length) return { meaning: "none", words: NONE_WORDS };
  return { value };
}

function describePiece(library, piece, drawn, map) {
  const d = piece.declared;
  const family = library.familyById.get(piece.family);
  const at = linkAt(library, map);
  const facts = [];
  const sections = [];
  const sources = [];
  const host = d.declared_host ? d.declared_host : `${d.host} (not stated as a registered model, kind or operator)`;
  facts.push(["ID", d.declared_id === d.id ? d.id : `${d.id}, declared as ${d.declared_id}`]);
  facts.push(["Interface", d.interface]);
  facts.push(["Host", host]);
  facts.push(["Family", d.family]);
  facts.push(["Models", list(d.models)]);
  facts.push(["Declared in", d.module_path ? `${d.module_path}, line ${d.line}` : `${d.module}, outside the cells package`]);
  if (d.module_path) sources.push({ path: d.module_path, where: `line ${d.line}${at.words}`, revision: at.revision });
  // The keys a piece of its kind may state, each as the manifest states it.
  for (const key of Object.keys(KEY_WORDS)) {
    const said = stated(library, piece, key);
    if (!said) continue;
    if (!("value" in said)) {
      facts.push([KEY_WORDS[key], said.words]);
      continue;
    }
    const value = said.value;
    switch (key) {
      case "kernels":
        sections.push({ title: "Kernels", items: Object.entries(value).map(([field, kernel]) => ({ label: kernel.function, code: true, detail: `${field}${kernel.module_path ? ` · ${kernel.module_path}` : " · no file of its own"}` })) });
        for (const kernel of Object.values(value)) if (kernel.module_path) sources.push({ path: kernel.module_path, where: `${kernel.function.split(".").at(-1)}${at.words}`, revision: at.revision });
        break;
      case "provenance": {
        facts.push(["Provenance", TAGS[value.tag] || value.tag]);
        if (value.source) facts.push(["Rests on", value.source]);
        const citation = value.citation;
        if (citation) {
          facts.push(["Cited", citation.source]);
          facts.push(["Where in it", citation.place]);
          facts.push(["Licence", citation.licence]);
          facts.push(["Departs from it", citation.departures?.length ? citation.departures.join("; ") : NONE_WORDS]);
          if (citation.works?.length)
            sections.push({
              title: "Works",
              items: citation.works.map((work) => ({
                label: work.title,
                lines: [`${list(work.authors)}, ${work.year}`],
                links: [work.doi ? { text: `doi:${work.doi}`, url: `https://doi.org/${work.doi}` } : null, work.url ? { text: work.url.replace(/^https:\/\//, ""), url: work.url } : null].filter(Boolean),
              })),
            });
          else facts.push(["Works", "the citation names its works in words only, or Cells' own documents"]);
        }
        break;
      }
      case "test":
        facts.push(["Test", value]);
        break;
      case "reads":
        sections.push({ title: "Reads", items: value.map((read) => ({ label: read.name, code: true, detail: `${read.mode}, at the ${read.stage} stage${read.scoped ? ", only the slots it names" : ""}` })) });
        break;
      case "changes":
        sections.push({ title: "Changes", items: value.map((row) => ("species" in row ? { label: row.species, detail: `valence ${row.valence}, relative permeability ${row.relative_permeability}` } : { label: row.role, detail: `${row.per_cycle} per forward cycle` })) });
        break;
      case "owns":
        sections.push({ title: "Owns", items: Object.entries(value).map(([field, axes]) => ({ label: field, code: true, detail: `by ${list(axes)}` })) });
        break;
      case "writes":
        sections.push({ title: "Writes", items: Object.entries(value).map(([field, books]) => ({ label: field, code: true, detail: `booked in ${list(books)}` })) });
        break;
      case "provides":
      case "controls":
      case "ledgers":
        sections.push({ title: KEY_WORDS[key], items: value.map((field) => ({ label: field, code: true })) });
        break;
      case "energy":
        facts.push(["Energy", `heat ${value.heat?.length ? list(value.heat) : "none"}; work ${value.work?.length ? list(value.work) : "none"}`]);
        break;
      case "units":
        sections.push({ title: "Units", items: Object.entries(value).map(([field, unit]) => ({ label: field, code: true, detail: unit === null ? "not stated" : unit })) });
        break;
      case "signs":
        sections.push({ title: "Signs", items: Object.entries(value).map(([field, sign]) => ({ label: field, code: true, detail: typeof sign === "string" ? sign : [sign.from && sign.to ? `from ${sign.from} to ${sign.to}` : null, sign.says].filter(Boolean).join(": ") || JSON.stringify(sign) })) });
        break;
      case "requires":
        facts.push(["Requires before it", value.laws?.length ? list(value.laws) : NONE_WORDS]);
        facts.push(["Requires the kinds", value.kinds?.length ? list(value.kinds) : NONE_WORDS]);
        break;
      default:
        break;
    }
  }
  // The rest of its declaration, by its interface's own fields.
  for (const [key, value] of Object.entries(d.fields || {})) facts.push([FIELD_WORDS[key] || key, words(key, value, d.units || {})]);
  // A status only where the manifest gives one, with the record it was copied from.
  facts.push(["Status", d.status ? `${d.status} (from ${d.status_source})` : "not stated: the engine's declarations give no level for it"]);
  if (d.status && d.status_source) sources.push({ path: d.status_source, where: "the record its status was copied from" });
  facts.push(["Page", d.doc ? d.doc : "none given yet: the engine's pages are written in batches"]);
  if (d.doc) sources.push({ path: d.doc, where: `its page${at.words}`, revision: at.revision });
  const declared = (piece.declared_by || []).map((entry) => ({ id: pageId(entry.frame), label: entry.how === "direct" ? entry.frame : `${entry.frame} (through ${entry.via})`, swatch: "laws-rack" }));
  const opens = [{ title: "Declared by", items: declared, count: declared.length }];
  if (d.laws?.length) opens.push({ title: "Laws it hosts", items: d.laws.map((law) => ({ id: pageId(library.piece(law)?.id || law), label: library.piece(law)?.id || law, swatch: "laws-declared" })), count: d.laws.length });
  // The way back to the Engine view: the box that holds its file, or the operator's own part, where the page draws it.
  const boxes = [piece.box?.id, d.piece === "operator" ? `op.${piece.id}` : null].filter((box) => box && drawn && drawn(box));
  return {
    id: pageId(piece.id),
    label: piece.id,
    kind: piece.kind,
    eyebrow: `${family?.label || piece.family} · ${interfaceWords(d)}`,
    status: null,
    chips: [{ label: whereWords(piece) }, ...(d.provenance?.tag ? [{ label: capitalise(TAGS[d.provenance.tag] || d.provenance.tag).replace(/ \(.*\)$/, "") }] : [])],
    plain: `${/^[aeiou]/i.test(interfaceWords(d)) ? "An" : "A"} ${interfaceWords(d)}, hosted by ${d.declared_host || d.host}${d.family !== d.host ? `, in the registries of ${d.family}` : ""}. The engine declares it in ${d.module_path || d.module}${d.line ? `, at line ${d.line}` : ""}. Being declared is not a level: its status is said apart, where the declarations give one.`,
    facts,
    sections,
    opens,
    related: boxes.length ? [{ title: "On the Engine view", ids: boxes }] : [],
    sources,
  };
}

const capitalise = (text) => text.charAt(0).toUpperCase() + text.slice(1);

function describeDesigned(library, piece, map) {
  const at = linkAt(library, map);
  return {
    id: pageId(piece.id),
    label: piece.id,
    kind: piece.kind,
    eyebrow: `Named in a design note · ${piece.kind}`,
    status: null,
    chips: [{ label: whereWords(piece) }],
    plain: "A design note names this law, and the engine's declarations do not list it: there is no declared piece of it.",
    facts: [],
    sections: [{ title: "Named in", note: `Each note names it at main ${library.manifest.short}, the revision of the declarations.`, items: piece.named_in.map((note) => ({ label: note.path, code: true, detail: `${note.section}, line ${note.line}` })) }],
    sources: piece.named_in.map((note) => ({ path: note.path, where: `line ${note.line}${at.words}`, revision: at.revision })),
  };
}

const MODEL_WORDS = {
  "inner model": "The inner model: it hosts its own laws and its kinds.",
  composite: "The composite: an inner model and any ordered list of operators. Any ordered list of them is a definition's composition.",
  composition: "A composition: the composite with a fixed operator list, an inner model and each operator by position.",
  [FAMILY]: "A model family with no rows: its laws are tables inside it, and the engine's declarations list none of them as a piece.",
  "family with rows": "A model family of its own: its laws and its operators are its rows, each a declared piece of its own interface.",
};

function describeModel(library, frame, drawn, map) {
  const d = frame.declared;
  const at = linkAt(library, map);
  const slotWords = (row, index) => {
    const tag = row.tags?.[index];
    return tag === null || tag === undefined ? "" : row.role === "channel law" ? ` (code ${tag})` : row.role === "kind" ? ` (key ${tag})` : ` (position ${tag})`;
  };
  const opens = (frame.rows || []).map((row) => ({
    title: row.label,
    items: [
      ...row.pieces.map((id, index) => ({ id: pageId(id), label: `${id}${slotWords(row, index)}`, swatch: swatchOf(library.piece(id)) })),
      ...(row.none || []).map((entry) => ({ id: pageId(entry.id), label: `${entry.id} (no piece of its own)`, swatch: "laws-none" })),
    ],
    count: row.pieces.length + (row.none || []).length,
  }));
  const facts = [["ID", d.declared_id === d.id ? d.id : `${d.id}, declared as ${d.declared_id}`], ["Type", d.type]];
  if (frame.inner) facts.push(["Holds", `the inner model ${frame.inner}`]);
  facts.push(["Its definitions are read by", `${d.module_path} (${d.module})`]);
  if (d.next_code !== null && d.next_code !== undefined) facts.push(["Next free channel code", `${d.next_code}: a new channel law takes it`]);
  facts.push(["Rows", d.rows.length ? String(d.rows.length) : NONE_WORDS]);
  facts.push(["Page", d.doc ? d.doc : d.type === "family" && !d.rows.length ? "none: a family with no rows gets no page" : "none given yet: the engine's pages are written in batches"]);
  const sources = [{ path: d.module_path, where: `its parse${at.words}`, revision: at.revision }];
  if (d.doc) sources.push({ path: d.doc, where: `its page${at.words}`, revision: at.revision });
  const boxes = (frame.boxes || []).filter((box) => drawn && drawn(box.id)).map((box) => box.id);
  return {
    id: pageId(frame.id),
    label: frame.id,
    kind: "frame",
    eyebrow: frame.kind === FAMILY && !frame.rows.length ? "A model family with no rows" : `A model · ${frame.kind}`,
    status: null,
    chips: [{ label: "An active model of the engine's declarations" }],
    plain: (frame.kind === FAMILY && frame.rows.length ? MODEL_WORDS["family with rows"] : MODEL_WORDS[frame.kind]) || null,
    facts,
    opens,
    related: boxes.length ? [{ title: "On the Engine view", ids: boxes }] : [],
    sources,
  };
}

/** A row of a model that has no entry of its own (a fuel kind): what the model's rows and its pieces say of it. */
function describeRow(library, row) {
  const users = library.pieces.filter((piece) => (piece.declared?.fields?.fuel_kinds || []).some((id) => namespaced(id) === namespaced(row.id)));
  return {
    id: pageId(row.id),
    label: row.id,
    kind: row.role,
    eyebrow: `A row of ${row.frame} · ${row.role}`,
    status: null,
    chips: [{ label: "No piece of its own" }],
    plain: `A ${row.role} of the model ${row.frame}: a row with no entry of its own in the engine's declarations, so they say nothing more of it.`,
    facts: [["Model", row.frame], ["Role", row.role]],
    opens: [{ title: "Runs the cycle laws", items: users.map((piece) => ({ id: pageId(piece.id), label: piece.id, swatch: "laws-declared" })), count: users.length }],
    sources: [],
  };
}

/**
 * The doors this view offers on another view's parts (the viewer asks every view it offers):
 * - an Engine view box that holds the files of declared pieces: one into the library with them picked out;
 * - an Engine view operator (op.<id>) the manifest declares: one onto that operator;
 * - a unit of the Protein atlas: one onto each of its laws the manifest declares; and for those it
 *   does not, lines of words that open nothing (no lens): one for each mark the law-port inventory
 *   gives them (law_port.js), and one that names each law the inventory has no row for.
 */
export function doorsFor(entity, scene) {
  if (!entity?.id || !scene?.laws?.pieces) return [];
  const library = libraryOf(scene.laws);
  if (!library) return [];
  const out = [];
  const count = library.inBox(entity.id).length;
  if (count) out.push({ label: `Show its ${count} declared piece${count === 1 ? "" : "s"} in the Laws library`, lens: "laws", value: entity.id });
  const operator = entity.id.startsWith("op.") ? library.piece(entity.id.slice(3)) : null;
  if (operator?.declared?.piece === "operator") out.push({ label: `Open ${operator.id} on the Laws library's wall`, lens: "laws", value: pageId(operator.id) });
  const undeclared = [];
  for (const law of unitLaws(entity)) {
    const piece = library.piece(law);
    if (piece?.where === "declared") out.push({ label: `Open ${piece.id} on the Laws library's wall`, lens: "laws", value: pageId(piece.id) });
    else undeclared.push(law);
  }
  // The laws no active model declares, named as the unit's panel names them: a line for each mark's
  // words in the law-port inventory, the laws of one mark gathered; and one line for the laws it has no row for.
  const { lines, uncovered } = portLines(portTable(scene), entity.id.replace(/^unit\./, ""), undeclared, unitLaws(entity));
  for (const line of lines) out.push({ says: true, label: line.label });
  if (uncovered.length === 1) out.push({ says: true, label: `No active model declares this unit's law ${uncovered[0]}. The engine's declarations do not list it, and the Laws library does not show it.` });
  else if (uncovered.length) out.push({ says: true, label: `No active model declares these laws of this unit: ${uncovered.join(", ")}. The engine's declarations do not list them, and the Laws library does not show them.` });
  return out;
}

/** The laws a unit of the Protein atlas names (its "Laws in the inventory" list), as its panel names them: an ID, or the inventory's words where it has none. */
export function unitLaws(entity) {
  if (entity?.kind !== "unit") return [];
  return (entity.sections || []).filter((section) => section.key === "laws").flatMap((section) => (section.items || []).map((item) => item.label)).filter(Boolean);
}

/** The list that stands in where 3D cannot be drawn, and the keyboard's way in: every piece by family, the models, and what is not shown. */
export function sections(library) {
  const out = library.families.map((family) => ({
    label: family.label,
    entities: library.inFamily.get(family.id).map((piece) => ({
      id: pageId(piece.id),
      label: piece.id,
      swatch: swatchOf(piece),
      keywords: [piece.declared?.id, piece.declared?.interface, piece.kind, piece.declared?.module_path, family.label, whereWords(piece)].filter(Boolean).join(" "),
    })),
  }));
  out.push({ label: "Models", entities: library.racks.map((frame) => ({ id: pageId(frame.id), label: frame.id, swatch: "laws-rack", keywords: [frame.kind, frame.declared.id, frame.declared.module_path].join(" ") })) });
  out.push({ label: "Model families with no rows", entities: library.cases.map((frame) => ({ id: pageId(frame.id), label: frame.id, swatch: "laws-case", keywords: `model family ${frame.declared.id} ${frame.declared.module_path}` })) });
  out.push({ label: "Rows with no piece of their own", entities: [...library.rowOnly.values()].map((row) => ({ id: pageId(row.id), label: row.id, swatch: "laws-none", keywords: `${row.role} ${row.frame}` })) });
  // What the wall does not show, by ID as the manifest gives it, in the manifest's own words.
  out.push({ label: "Not shown: the older model families (legacy code, to be dropped)", limit: 12, entities: [...library.legacy.values()].map((item) => ({ id: pageId(item.id), label: item.id, keywords: "legacy older model family not shown" })) });
  return out.filter((section) => section.entities.length);
}

/** The list and the panel where no 3D can be drawn (the viewer's text fallback): from the scene's `laws`. */
const libraries = new WeakMap();
const libraryOf = (raw) => {
  if (!raw?.pieces) return null;
  if (!libraries.has(raw)) libraries.set(raw, new Library(raw));
  return libraries.get(raw);
};
export const textSections = (scene) => (libraryOf(scene?.laws) ? sections(libraryOf(scene.laws)) : []);
export const textDescribe = (scene, id) => (libraryOf(scene?.laws) ? describe(libraryOf(scene.laws), id, { drawn: drawnIn(scene), map: scene.meta }) : null);

/** Whether the page draws an Engine view box, read from the scene: null where the page has no Engine view. */
export function drawnIn(scene, lensOf = null) {
  const entities = scene?.entities || [];
  if (!entities.length) return null;
  const groups = new Map((scene.groups || []).map((group) => [group.id, group.lens || "engine"]));
  const byId = new Map(entities.map((entity) => [entity.id, entity]));
  return (id) => {
    const entity = byId.get(id);
    return Boolean(entity) && (lensOf ? lensOf(entity) : groups.get(entity.group) || "engine") === "engine";
  };
}

export { PREFIX };
