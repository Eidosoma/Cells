// What the page's panel and list say of the Laws library's parts (schema/LAWS_LIBRARY.md,
// "What the view may say"). The shapes are the ones every view hands to <cells-panel> and
// <cells-index>; nothing here is new to the page.

import { Library, PREFIX, WHERE, APART, pageId, engineId } from "./laws_data.js";

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
    default: return "not as a piece of the one model: it stands in the older families' channel catalogue, a table inside its own module, until a use moves it (D167)";
  }
}

/** The panel's entity for one piece or one frame, by its page id; null for anything else. */
export function describe(library, id) {
  const name = engineId(id);
  if (!name) return null;
  const piece = library.piece(name);
  if (piece) return describePiece(library, piece);
  const frame = library.frame(name);
  return frame ? describeFrame(library, frame) : null;
}

function describePiece(library, piece) {
  const family = library.familyById.get(piece.family);
  const read = piece.read;
  const fields = read?.fields || {};
  const chips = [{ label: whereWords(piece) }];
  if (piece.registry === "an older family") chips.push({ label: "In an older family" });
  if (piece.registry === "no registry") chips.push({ label: "A named law in no registry" });
  if (!piece.status) chips.push({ label: "No level recorded for this piece" });
  const facts = [];
  if (read) {
    facts.push(["Read", `${ref(read)}, ${read.path}`]);
    facts.push(["Found by", read.found_by]);
    facts.push(["Registered", registered(piece)]);
    if (fields.provenance) facts.push(["Provenance tag", `${fields.provenance}: a source tag in inner_laws.py, not a level`]);
    if (fields.unversioned) facts.push(["Version", "None: it has no version. The declarations manifest's design is to close that gap; the page gives it none."]);
    if (fields.code !== undefined) facts.push(["Registry code", `${fields.code} in the older families' catalogue tables`]);
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
  const status = piece.status
    ? null
    : piece.box
      ? `No level recorded for this piece. Its box on the Engine view, ${piece.box.label}, is ${piece.box.level_label.toLowerCase()}${piece.box.as_of ? ` (${piece.box.as_of})` : ""}: a status of the box, not of the piece.`
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
  if (read && onMain(library, read)) sources.push({ path: read.path, where: read.found_by });
  if (piece.status?.source) sources.push(piece.status.source);
  if (piece.box?.source && !piece.status) sources.push(piece.box.source);
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
    related: piece.box ? [{ title: "On the Engine view", ids: [piece.box.id] }] : [],
    sources,
  };
}

function describeFrame(library, frame) {
  const facts = [["Read", `${ref(frame.read)}, ${frame.read.path} (${frame.read.found_by})`]];
  if (frame.inner) facts.push(["Holds", frame.inner]);
  if (frame.development_status) facts.push(["What a composition is worth", `“${frame.development_status}” (src/cells/core/pump_composite_spec.py)`]);
  for (const box of frame.boxes || []) facts.push(["The Engine view's box", `${box.name} is ${box.label.toLowerCase()}${box.as_of ? `, ${box.as_of}` : ""} (${box.source.path}${box.source.where ? `: ${box.source.where}` : ""}): the box's status, not one the frame takes from its parts`]);
  const opens = (frame.rows || []).map((row) => ({
    title: row.label + (row.read && !onMain(library, row.read) ? ` (read on ${row.read.ref} ${row.read.revision}, not on main yet)` : row.curated ? " (the viewer's reading of frozen_definition)" : ""),
    items: row.pieces.map((id) => ({ id: pageId(id), label: id, swatch: swatchOf(library.piece(id)) })),
    count: row.pieces.length,
  }));
  if (frame.rows?.[0]?.codes) facts.push(["Its registry codes", Object.entries(frame.rows[0].codes).map(([law, code]) => `${law} ${code}`).join(", ") + ` (${frame.rows[0].codes_read.path}, ${frame.rows[0].codes_read.name}): the inner model's own codes, not the older families' catalogue codes`]);
  if (frame.rows?.[0]?.next_code !== undefined) facts.push(["Next free registry code", `${frame.rows[0].next_code}: a new channel law takes it, and no code is reused`]);
  const sources = [];
  if (onMain(library, frame.read)) sources.push({ path: frame.read.path, where: frame.read.found_by });
  for (const box of frame.boxes || []) sources.push(box.source);
  return {
    id: pageId(frame.id),
    label: frame.id,
    kind: "frame",
    eyebrow: frame.kind === "older family" ? "An older model family" : `A model frame · ${frame.kind}`,
    status: null,
    chips: [{ label: frame.kind === "older family" ? "Its laws are a table inside its own module" : "Its status never comes from its parts" }],
    plain: frame.kind === "older family" ? library.raw.older_words : frame.plain || null,
    facts,
    opens,
    related: frame.boxes?.length ? [{ title: "On the Engine view", ids: frame.boxes.map((box) => box.id) }] : [],
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
  const count = scene.laws.pieces.filter((piece) => piece.box?.id === entity.id).length;
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
  out.push({ label: "Older families", limit: 12, entities: library.older.map((frame) => ({ id: pageId(frame.id), label: frame.id, swatch: "laws-older-family", keywords: `older family ${frame.read.path}` })) });
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
export const textDescribe = (scene, id) => (libraryOf(scene?.laws) ? describe(libraryOf(scene.laws), id) : null);

export { PREFIX };
