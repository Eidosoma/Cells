// What the page's panel and list say of the Laws library's parts (schema/LAWS_LIBRARY.md,
// "What the view may say"). The shapes are the ones every view hands to <cells-panel> and
// <cells-index>; nothing here is new to the page.

import { Library, PREFIX, WHERE, APART, FAMILY, pageId, engineId } from "./laws_data.js";

/** A piece's swatch in the list and the panel: the mark it is drawn with on the wall (laws.js MARKS, laws_styles.js). */
export function swatchOf(piece) {
  if (!piece) return "laws-main";
  if (piece.where === "design") return "laws-design";
  if (APART.has(piece.registry)) return "laws-older";
  return `laws-${piece.where}`;
}

const whereWords = (piece) => WHERE.find((item) => item.id === piece.where)?.label || piece.where;
const list = (value) => (Array.isArray(value) ? value.join(", ") : String(value));
// "origin/main 8e255d45"; a list read at a revision by its own name says it once ("fa19d80c").
const ref = (read) => (read?.ref && read.ref !== read.revision ? `${read.ref} ${read.revision}` : read?.revision || "");
/** A revision on main can be linked; one on a working branch is said in words only (schema, "Sources and links"). */
const onMain = (library, read) => read && read.revision === library.stamp.main.revision;
/**
 * A file the list was read from, as a source: linked at the revision the list was read at, where the
 * file is by construction, not at the map's (the file may have moved since). Where that is not the
 * map's revision, the words beside the link say so.
 */
function readSource(library, read, map) {
  const main = library.stamp.main;
  const revision = main.full_revision || main.revision;
  const same = map && ((map.source_base_url || "").includes(`/blob/${revision}/`) || (map.revision && revision.startsWith(map.revision)));
  return { path: read.path, where: same ? read.found_by : `${read.found_by}, as read at main ${main.revision}`, revision };
}

function moved(permeant) {
  return (permeant || []).map(([species, relative]) => (relative === 1 ? species : `${species} (${relative} relative)`)).join(", ");
}

function gates(fields) {
  if (Array.isArray(fields.gate_powers)) {
    const [m, h] = fields.gate_powers;
    const parts = [m ? (m === 1 ? "m" : `m^${m}`) : null, h ? (h === 1 ? "h" : `h^${h}`) : null].filter(Boolean);
    return parts.length ? `gate powers ${parts.join(" · ")}` : "no gates";
  }
  if (fields.gate_states !== undefined) return `${fields.gate_states} gate state${fields.gate_states === 1 ? "" : "s"}`;
  return null;
}

/** Where a piece stands registered, in words (the lead's provisional answers of 16 November 2026). */
function registered(piece) {
  const where = piece.registered_in || {};
  switch (piece.registry) {
    case "inner_laws.py": return `in ${where.path}, ${where.name}: a declared piece of the one inner model`;
    case "the kind registry": return "as a built-in kind of the kind registry (src/cells/core/kind_registry.py)";
    case "a registered kind": return `as one of ${where.kind}'s own pieces`;
    case "OPERATORS": return "in OPERATORS, the composite's registry (src/cells/models/operators/__init__.py)";
    case "the inner model's structure": return `in the inner model's structure (${where.path}, ${where.name})`;
    case "a registered operator": return `as a law named in ${where.operator}'s own module, an operator of OPERATORS`;
    case "no registry": return "in no registry the page reads: a constant named for a law, shelved by the page's reading until the engine's manifest says what it is";
    case "a solver or step method": return "a solver or step method: counted as a piece (the lead's provisional answer)";
    default: return "not as a piece of the one model: it stands in a model family's table, the channel catalogue's LAW_CODES inside its own module, until a use moves it (D167)";
  }
}

/**
 * The panel's entity for one piece or one frame, by its page id; null for anything else.
 * `drawn(boxId)`: whether the page draws that Engine view box (the viewer's scene holds it, in the
 * Engine view). Where the page has no Engine view (the view standing alone) it is not given, and
 * nothing is said of the boxes beyond what the list read. `map`: the page's scene meta, whose
 * revision the words beside a link from the list compare with.
 */
export function describe(library, id, { drawn = null, map = null } = {}) {
  const name = engineId(id);
  if (!name) return null;
  const piece = library.piece(name);
  if (piece) return describePiece(library, piece, drawn, map);
  const frame = library.frame(name);
  if (frame) return describeFrame(library, frame, drawn, map);
  const gone = library.notShown(name);
  return gone ? describeNotShown(gone) : null;
}

/**
 * What the map no longer shows, named by an address (laws:<id>): legacy code, said plainly, with
 * nothing of what it was. Only what moved into src/cells/legacy/ is called legacy code.
 */
function describeNotShown(gone) {
  const moved = gone.now ? " Its module moved into the engine's legacy code, src/cells/legacy/, in D188's first move." : "";
  const plain =
    gone.as === "frame"
      ? `The map does not show legacy code, and this model family is legacy code now.${moved}`
      : `The map no longer shows this piece: no model declares it, and nothing outside the engine's legacy code names it.${moved}`;
  return { id: pageId(gone.id), label: gone.id, kind: "not shown", eyebrow: "Laws library · not shown", status: null, chips: [{ label: "Not shown on the map" }], plain, facts: [], sources: [] };
}

function describePiece(library, piece, drawn, map) {
  const family = library.familyById.get(piece.family);
  const read = piece.read;
  const fields = read?.fields || {};
  const chips = [{ label: whereWords(piece) }];
  if (piece.registry === "an older family") chips.push({ label: "In a model family's table" });
  if (piece.registry === "no registry") chips.push({ label: "A named law in no registry" });
  if (!piece.status) chips.push({ label: "No level recorded for this piece" });
  const facts = [];
  if (read) {
    facts.push(["Read", `${ref(read)}, ${read.path}`]);
    facts.push(["Found by", read.found_by]);
    facts.push(["Registered", registered(piece)]);
    if (fields.provenance) facts.push(["Provenance tag", `${fields.provenance}: a source tag in inner_laws.py, not a level`]);
    if (fields.unversioned) facts.push(["Version", "None: it has no version. The declarations manifest's design is to close that gap; the page gives it none."]);
    if (fields.code !== undefined) facts.push(["Registry code", `${fields.code} in the model families' catalogue tables`]);
    if (fields.permeant) facts.push(["Moves", moved(fields.permeant)]);
    if (gates(fields)) facts.push(["Gates", gates(fields)]);
    if (fields.pieces?.length) facts.push(["Its pieces", list(fields.pieces)]);
    if (fields.parts?.length) facts.push(["Parts of the step", list(fields.parts)]);
    if (fields.provides) facts.push(["Provides", list(fields.provides)]);
    if (fields.reads_declared) facts.push(["Reads as declared", list(fields.reads_declared)]);
    if (fields.reads_current) facts.push(["Reads", list(fields.reads_current)]);
    if (fields.writes) facts.push(["Writes", list(fields.writes)]);
    if (fields.requires) facts.push(["Requires before it", list(fields.requires)]);
    if (fields.step_method) facts.push(["Step method", fields.step_method]);
    if (fields.heat) facts.push(["Heat booked in", list(fields.heat)]);
    if (fields.work) facts.push(["Work booked in", list(fields.work)]);
    if (fields.ledgers) facts.push(["Own ledgers", list(fields.ledgers)]);
  }
  if (piece.curated?.unit) facts.push(["Acts on", `${piece.curated.unit} (${piece.curated.unit_by})`]);
  facts.push(["Family", `${family?.label || piece.family}: the viewer's shelving, not the engine's`]);
  // A box the page does not draw (the Engine view no longer shows it) is named, and its status is not said.
  const boxGone = Boolean(piece.box && drawn && !drawn(piece.box.id));
  const status = piece.status
    ? null
    : piece.box && !boxGone
      ? `No level recorded for this piece. Its box on the Engine view, ${piece.box.label}, is ${piece.box.level_label.toLowerCase()}${piece.box.as_of ? ` (${piece.box.as_of})` : ""}: a status of the box, not of the piece.`
      : boxGone
        ? `No level recorded for this piece. Its box when the list was read, ${piece.box.label}, is not on the Engine view now.`
        : "No level recorded for this piece.";
  if (status) facts.push(["Status", status]);
  const declared = (piece.declared_by || []).map((entry) => ({
    id: pageId(entry.frame),
    label: entry.how === "direct" ? entry.frame : `${entry.frame} (through ${entry.via})`,
    swatch: "laws-rack",
  }));
  const sections = [];
  if (piece.where === "design") {
    sections.push({
      title: "Named in",
      note: "A design note names it, and the code does not hold it yet. A note on a development branch is not in the public repository until it lands.",
      items: (piece.curated.named_in || []).map((note) => ({ label: note.path, detail: `${note.where} · ${note.ref === "main" ? "on main" : `on the development branch ${note.ref}, not on main`}` })),
    });
  }
  if (read && !onMain(library, read)) {
    sections.push({ title: "File", note: "Read on the landing candidate, which is not in the public repository until it lands.", items: [{ label: read.path, code: true, detail: ref(read) }] });
  }
  const sources = [];
  if (read && onMain(library, read)) sources.push(readSource(library, read, map));
  if (piece.status?.source) sources.push(piece.status.source);
  if (piece.box?.source && !piece.status && !boxGone) sources.push(piece.box.source);
  return {
    id: pageId(piece.id),
    label: piece.id,
    kind: piece.kind,
    eyebrow: `${family?.label || piece.family} · ${piece.kind}`,
    status: piece.status?.level || null,
    as_of: piece.status?.as_of || null,
    chips,
    plain: read ? (fields.doc ? `Its module says: “${fields.doc}”` : "Its module says nothing of what it computes: it has no docstring.") : "Named in a design note; it has no code yet.",
    note: piece.curated?.label ? `On the Engine view: ${piece.curated.label}.` : null,
    facts,
    sections,
    opens: declared.length ? [{ title: "Declared by", items: declared, count: declared.length }] : [{ title: "Declared by", items: [], count: 0 }],
    // The way back to the Engine view: the box that holds the piece's file (the panel links it where the page's scene has it).
    related: piece.box && !boxGone ? [{ title: "On the Engine view", ids: [piece.box.id] }] : [],
    sources,
  };
}

function describeFrame(library, frame, drawn, map) {
  const facts = [["Read", `${ref(frame.read)}, ${frame.read.path} (${frame.read.found_by})`]];
  if (frame.inner) facts.push(["Holds", frame.inner]);
  if (frame.development_status) facts.push(["What a composition is worth", `“${frame.development_status}” (src/cells/core/pump_composite_spec.py)`]);
  for (const box of frame.boxes || []) {
    if (drawn && !drawn(box.id)) facts.push(["The Engine view's box", `${box.name}, when the list was read, is not on the Engine view now`]);
    else facts.push(["The Engine view's box", `${box.name} is ${box.label.toLowerCase()}${box.as_of ? `, ${box.as_of}` : ""} (${box.source.path}${box.source.where ? `: ${box.source.where}` : ""}): the box's status, not one the frame takes from its parts`]);
  }
  const opens = (frame.rows || []).map((row) => ({
    title: row.label + (row.read && !onMain(library, row.read) ? ` (read on ${row.read.ref} ${row.read.revision}, not on main yet)` : row.curated ? " (the viewer's reading of frozen_definition)" : ""),
    items: row.pieces.map((id) => ({ id: pageId(id), label: id, swatch: swatchOf(library.piece(id)) })),
    count: row.pieces.length,
  }));
  if (frame.rows?.[0]?.codes) facts.push(["Its registry codes", Object.entries(frame.rows[0].codes).map(([law, code]) => `${law} ${code}`).join(", ") + ` (${frame.rows[0].codes_read.path}, ${frame.rows[0].codes_read.name}): the inner model's own codes, not the model families' catalogue codes`]);
  if (frame.rows?.[0]?.next_code !== undefined) facts.push(["Next free registry code", `${frame.rows[0].next_code}: a new channel law takes it, and no code is reused`]);
  const sources = [];
  if (onMain(library, frame.read)) sources.push(readSource(library, frame.read, map));
  for (const box of frame.boxes || []) if (!drawn || drawn(box.id)) sources.push(box.source);
  return {
    id: pageId(frame.id),
    label: frame.id,
    kind: "frame",
    eyebrow: frame.kind === FAMILY ? "A model family" : `A model frame · ${frame.kind}`,
    status: null,
    chips: [{ label: frame.kind === FAMILY ? "Its laws are a table inside it; it declares no piece" : "Its status never comes from its parts" }],
    plain: frame.kind === FAMILY ? library.raw.older_words || null : frame.plain || null,
    facts,
    opens,
    related: (frame.boxes || []).some((box) => !drawn || drawn(box.id)) ? [{ title: "On the Engine view", ids: frame.boxes.filter((box) => !drawn || drawn(box.id)).map((box) => box.id) }] : [],
    sources,
  };
}

/**
 * The doors this view offers on another view's parts (the viewer asks every view it offers): on an
 * Engine view box that holds the files of pieces of the list, one into the library with those
 * pieces picked out. The words say what the door does; the count is the list's.
 */
export function doorsFor(entity, scene) {
  if (!entity?.id || !scene?.laws?.pieces) return [];
  const library = libraryOf(scene.laws);
  const count = library ? library.inBox(entity.id).length : 0;
  if (!count) return [];
  return [{ label: `Show its ${count} piece${count === 1 ? "" : "s"} in the Laws library`, lens: "laws", value: entity.id }];
}

/** The list that stands in where 3D cannot be drawn, and the keyboard's way in: every piece by family, then the frames. */
export function sections(library) {
  const out = library.families.map((family) => ({
    label: family.label,
    entities: library.inFamily.get(family.id).map((piece) => ({
      id: pageId(piece.id),
      label: piece.id,
      swatch: swatchOf(piece),
      keywords: [piece.curated?.unit, piece.curated?.label, piece.read?.path, family.label, whereWords(piece), piece.registry].filter(Boolean).join(" "),
    })),
  }));
  out.push({ label: "Frames", entities: library.racks.map((frame) => ({ id: pageId(frame.id), label: frame.id, swatch: "laws-rack", keywords: [frame.kind, frame.label].filter(Boolean).join(" ") })) });
  out.push({ label: "Model families", entities: library.cases.map((frame) => ({ id: pageId(frame.id), label: frame.id, swatch: "laws-case", keywords: `model family ${frame.read.path}` })) });
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
