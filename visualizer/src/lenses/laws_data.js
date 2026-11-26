// The Laws library's list, indexed for the view (schema/LAWS_LIBRARY.md): the engine's declared
// pieces and models as its declarations manifest gives them, who declares what, the search and
// the filters. No drawing here: the view, its card and its tests all ask this one place, so what
// is lit and what is said agree.

export const LAWS_FORMAT = "cells.visualizer.laws@2";
/** The manifest this view reads, and the one major of it it knows (the engine's page docs/library/DECLARATIONS_FORMAT.md). */
export const MANIFEST = "cells.declarations";
export const MANIFEST_MAJOR = 3;
/** Ids the page uses for this view's parts: a piece or a model, by its declared id. */
export const PREFIX = "laws:";
export const WHERE = [
  { id: "declared", label: "Declared by an active model", short: "Declared" },
  { id: "design", label: "Named in a design note; not declared", short: "Design note" },
];
/** A model with no rows, by the manifest's type: drawn as a closed case on the plinth. */
export const FAMILY = "family";
const ID = /^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*@[0-9]+$/;

// Only the engine's published move table translates old identifiers into current ones.
export function canonicalAddress(id, aliases = {}) {
  if (typeof id !== "string") return id;
  const move = name => Object.hasOwn(aliases, name) ? aliases[name] : name;
  if (id.startsWith("op.")) return "op." + move(id.slice(3));
  if (!id.startsWith(PREFIX)) return move(id);
  const raw = id.slice(PREFIX.length);
  if (!raw.includes("/")) return PREFIX + move(raw);
  try {
    const [type, owner, ...rest] = raw.split("/").map(decodeURIComponent);
    if (type !== "field" && type !== "bridge") return id;
    return PREFIX + [type, move(owner), ...rest].map(encodeURIComponent).join("/");
  } catch { return id; }
}

export const pageId = (id) => (id ? PREFIX + id : null);
export const engineId = (id) => (typeof id === "string" && id.startsWith(PREFIX) ? id.slice(PREFIX.length) : null);
/** D185: a bare ID is in the cells namespace (the format page, "The ID rule"); both spellings name one piece. */
export const namespaced = (id) => (typeof id !== "string" ? null : id.split("@")[0].includes(".") ? id : `cells.${id}`);
export const isId = (id) => typeof id === "string" && ID.test(id);

/** The words for a piece's interface: a law type's, a kind, an operator; another is a model family's own. */
const INTERFACES = {
  "cells.channel_law@1": "channel law",
  "cells.cycle_law@1": "cycle law",
  "cells.route_law@1": "route law",
  "cells.junction_law@1": "junction law",
  "cells.binding_law@1": "binding law",
  "cells.kind@1": "kind",
  "cells.operator@1": "operator",
};
export const CELLS_LAWS = new Set(Object.keys(INTERFACES).filter((id) => id.endsWith("_law@1")));
export function interfaceWords(piece) {
  if (!piece) return null;
  return INTERFACES[piece.interface] || `${piece.piece} of its model family's own interface`;
}

/** The inner model's row roles, in the manifest's order, as the rack names its rows (the format page, "Roles"). */
const ROLE_ROWS = {
  "channel law": "Channel laws, by code",
  "junction law": "Junction law",
  "cycle law": "Cycle laws",
  "route law": "Route laws",
  "binding law": "Binding laws",
  law: "Laws",
  "fuel kind": "Fuel kind",
  kind: "Kinds, by key",
  operator: "Operators",
};

/** What the manifest's `kind` says of its major: the number, or null. */
export function majorOf(kind) {
  const match = /^cells\.declarations@([0-9]+)$/.exec(String(kind || ""));
  return match ? Number(match[1]) : null;
}

/** The structural rules of the file, as a list of problems (empty when it holds). The tests and the view share them. */
export function problemsOf(raw) {
  if (!raw || raw.format !== LAWS_FORMAT) return [`not a ${LAWS_FORMAT} file`];
  const problems = [];
  const manifest = raw.stamp?.manifest;
  if (majorOf(manifest?.kind) !== MANIFEST_MAJOR) problems.push(`read from ${manifest?.kind}, not ${MANIFEST}@${MANIFEST_MAJOR}`);
  if (raw.viewer_ids?.revision !== manifest?.revision) problems.push("the identifier moves and manifest have different revisions");
  if (manifest?.dirty !== false) problems.push("read from a manifest whose tree was not clean");
  if (!/^[0-9a-f]{40}$/.test(String(manifest?.revision))) problems.push("the manifest's revision is not a full Git revision");
  const families = new Set((raw.families || []).map((family) => family.id));
  const seen = new Set();
  for (const piece of raw.pieces || []) {
    const key = namespaced(piece.id);
    if (seen.has(key)) problems.push(`${piece.id} is listed twice`);
    seen.add(key);
    if (!families.has(piece.family)) problems.push(`${piece.id}: family ${piece.family} is not a family of the file`);
    if (!WHERE.some((where) => where.id === piece.where)) problems.push(`${piece.id}: where is ${piece.where}`);
    if (piece.where === "declared" ? piece.declared?.declared_id !== piece.id : piece.declared !== null || !piece.named_in?.length) problems.push(`${piece.id}: its declaration does not match where it stands`);
    if (piece.status !== undefined || piece.box?.level) problems.push(`${piece.id}: a level that is not the manifest's`);
  }
  for (const model of raw.models || []) {
    if (model.declared?.declared_id !== model.id) problems.push(`model ${model.id}: its declaration is not its own`);
    if (seen.has(namespaced(model.id))) problems.push(`${model.id} is both a piece and a model`);
  }
  return problems;
}

export class Library {
  constructor(raw) {
    const problems = problemsOf(raw);
    if (problems.length) throw new Error(`The Laws library's list is not valid: ${problems.slice(0, 3).join("; ")}`);
    this.raw = raw;
    this.stamp = raw.stamp;
    this.manifest = raw.stamp.manifest;
    this.families = raw.families;
    this.shelves = raw.shelves;
    this.familyById = new Map(raw.families.map((family) => [family.id, family]));
    this.shelfById = new Map((raw.shelves || []).map((shelf) => [shelf.id, shelf]));
    this.notExtracted = new Set((raw.not_extracted || []).map((item) => `${item.interface}|${item.key}`));
    this.aliases = raw.viewer_ids?.aliases || {};
    const historical = raw.viewer_ids?.historical;
    const active = new Set(raw.models.map(model => model.id));
    this.legacy = new Map((historical?.legacy || []).filter(id => !active.has(this.resolve(id)))
      .map(id => [namespaced(id), {id, revision: historical.revision}]));
    // Pieces: the manifest's, as declared, then those a design note names. Both spellings of an ID find one.
    this.pieces = raw.pieces.map((piece) => ({ ...piece, kind: piece.declared ? interfaceWords(piece.declared) : piece.kind }));
    this.byKey = new Map(this.pieces.map((piece) => [namespaced(piece.id), piece]));
    // Models: those with rows are racks; a family with none is a closed case.
    this.models = raw.models.map((model) => this.frameOf(model));
    this.frames = this.models;
    this.frameByKey = new Map(this.frames.map((frame) => [namespaced(frame.id), frame]));
    // A row of a model with no entry of its own (a fuel kind): the model and the row that name it.
    this.rowOnly = new Map();
    for (const frame of this.frames) for (const [r, row] of (frame.rows || []).entries()) for (const entry of row.none || []) this.rowOnly.set(namespaced(entry.id), { ...entry, frame: frame.id, row: r });
    for (const piece of this.pieces) piece.declared_by = this.declarersOf(piece);
    this.inFamily = new Map(raw.families.map((family) => [family.id, this.pieces.filter((piece) => piece.family === family.id)]));
  }

  /** A model as the rack draws it: its rows grouped by role, in the manifest's order, with their slots. */
  frameOf(model) {
    const declared = model.declared;
    const kind = { inner: "inner model", composite: "composite", composition: "composition", family: FAMILY }[declared.type] || declared.type;
    const frame = { id: model.id, kind, short: model.short || null, boxes: model.boxes || [], declared, rows: [], inner: null };
    const pieceOf = (row) => (row.piece && row.piece !== "model" ? this.piece(row.declared_id) || this.piece(row.id) : null);
    for (const row of declared.rows) {
      if (row.role === "inner model") {
        frame.inner = row.declared_id;
        continue;
      }
      const label = ROLE_ROWS[row.role] || row.role;
      let group = frame.rows.at(-1);
      if (!group || group.role !== row.role) frame.rows.push((group = { role: row.role, label, pieces: [], tags: [], none: [] }));
      const piece = pieceOf(row);
      if (piece) {
        group.pieces.push(piece.id);
        group.tags.push(row.slot ? Object.values(row.slot)[0] : null);
      } else group.none.push({ id: row.declared_id, role: row.role });
    }
    if (kind === "composite") {
      // The composite holds an inner model: the one whose pieces the manifest lets the composite declare.
      const inner = this.pieces.find((piece) => piece.declared?.models?.includes(declared.id) && piece.declared.family !== declared.id);
      frame.inner = inner ? this.raw.models.find((item) => item.declared.id === inner.declared.family)?.id || null : null;
    }
    if (kind === "inner model" && declared.next_code !== null) {
      const channels = frame.rows.find((row) => row.role === "channel law");
      if (channels) channels.next_code = declared.next_code;
    }
    if (frame.rows.length && kind !== "inner model") for (const row of frame.rows) row.label = kind === "composition" ? "Operators, by position" : kind === "composite" ? "Operators, in ID order" : row.label;
    return frame;
  }

  /** What declares a piece, from the models' rows: a row of its own, the kind that hosts it, or the inner model a model holds. */
  declarersOf(piece) {
    const declared = piece.declared;
    if (!declared) return [];
    const out = [];
    for (const frame of this.frames) {
      const rows = frame.rows || [];
      if (rows.some((row) => row.pieces.includes(piece.id))) out.push({ frame: frame.id, how: "direct" });
      else if (declared.host && rows.some((row) => row.role === "kind" && row.pieces.some((id) => namespaced(id) === declared.host))) out.push({ frame: frame.id, how: "kind", via: this.piece(declared.host).id });
      else if (frame.inner && namespaced(declared.family) === namespaced(frame.inner) && (frame.kind === "composition" || declared.models?.includes(frame.declared.id))) out.push({ frame: frame.id, how: "inner", via: frame.inner });
    }
    return out;
  }

  resolve(id) { return canonicalAddress(id, this.aliases); }

  /** A piece by its current ID or an exact historical bookmark. */
  piece(id) {
    return this.byKey.get(namespaced(this.resolve(id))) || null;
  }

  frame(id) {
    return this.frameByKey.get(namespaced(this.resolve(id))) || null;
  }

  /** A legacy model ID, as the manifest lists it ({ id, legacy, piece }), or null. */
  legacyOf(id) {
    return this.legacy.get(namespaced(id)) || null;
  }

  /** A row of a model with no entry of its own (a fuel kind), or null. */
  rowOf(id) {
    return this.rowOnly.get(namespaced(this.resolve(id))) || null;
  }

  /** The models with rows, drawn as racks: a model family with rows of its own among them. */
  get racks() {
    return this.frames.filter((frame) => frame.kind !== FAMILY || frame.rows.length);
  }

  /** The model families with no rows, drawn as closed cases on the plinth. */
  get cases() {
    return this.frames.filter((frame) => frame.kind === FAMILY && !frame.rows.length);
  }

  /** Whether a piece matches a search: its IDs, its interface, its family, its file. */
  matches(piece, query) {
    const words = String(query || "").trim().toLowerCase();
    if (!words) return true;
    const family = this.familyById.get(piece.family);
    return [piece.id, piece.declared?.id, piece.declared?.interface, piece.kind, piece.declared?.module_path, family?.label].some((text) => text && String(text).toLowerCase().includes(words));
  }

  /** Whether a piece passes the view's filters: a family, where it stands, a search, an Engine view box (the door from that box). */
  passes(piece, { family = null, where = null, query = "", box = null } = {}) {
    return (!family || piece.family === family) && (!where || piece.where === where) && (!box || piece.box?.id === box) && this.matches(piece, query);
  }

  /** The declared pieces an Engine view box holds (their module_path matched to its globs): what the door from that box opens on. */
  inBox(id) {
    return this.pieces.filter((piece) => piece.box?.id === id);
  }

  /**
   * The slots a chosen piece lights: in each model that declares it, its slot, the slot of the
   * kind that hosts it, or the block of the inner model it comes through. Each is
   * { frame, row, index } or { frame, block }.
   */
  slotsOf(id) {
    const piece = this.piece(id);
    if (!piece) return [];
    const out = [];
    for (const entry of piece.declared_by || []) {
      const frame = this.frame(entry.frame);
      if (!frame) continue;
      if (entry.how === "inner") {
        out.push({ frame: frame.id, block: entry.via });
        continue;
      }
      const target = entry.how === "kind" ? entry.via : piece.id;
      frame.rows.forEach((row, r) => row.pieces.forEach((name, index) => name === target && out.push({ frame: frame.id, row: r, index })));
    }
    return out;
  }

  /** The pieces a chosen model lights: every piece it declares, in any way. */
  piecesOf(frameId) {
    const frame = this.frame(frameId);
    return new Set(frame ? this.pieces.filter((piece) => (piece.declared_by || []).some((entry) => entry.frame === frame.id)).map((piece) => piece.id) : []);
  }

  /** The family columns, each with its pieces and, for a test of size only, empty slots in today's proportions (null). */
  columns(size = 0) {
    const extra = Math.max(0, size - this.pieces.length);
    const total = this.pieces.length || 1;
    const shares = this.families.map((family) => ({ id: family.id, raw: (extra * this.inFamily.get(family.id).length) / total }));
    const given = new Map(shares.map((share) => [share.id, Math.floor(share.raw)]));
    let left = extra - [...given.values()].reduce((sum, value) => sum + value, 0);
    for (const share of [...shares].sort((a, b) => (b.raw % 1) - (a.raw % 1))) {
      if (left <= 0) break;
      given.set(share.id, given.get(share.id) + 1);
      left -= 1;
    }
    return this.families.map((family) => ({ family, pieces: [...this.inFamily.get(family.id), ...new Array(given.get(family.id)).fill(null)] }));
  }

  /** Counts of the file, by where each piece stands and by family. The declared count is the manifest's. */
  counts() {
    const where = Object.fromEntries(WHERE.map((item) => [item.id, this.pieces.filter((piece) => piece.where === item.id).length]));
    const family = Object.fromEntries(this.families.map((item) => [item.id, this.inFamily.get(item.id).length]));
    return { pieces: this.pieces.length, declared: where.declared, where, family, frames: this.racks.length, cases: this.cases.length, legacy: this.legacy.size };
  }

  /**
   * What a key that is null on a piece means (the format page, "The three meanings of null"):
   * "not extracted" where (its interface, the key) is in not_extracted; "not applicable" where
   * the key does not apply to that kind of piece; else "not stated".
   */
  nullMeaning(piece, key) {
    const declared = piece?.declared || piece;
    if (this.notExtracted.has(`${declared.interface}|${key}`)) return "not extracted";
    return appliesTo(declared, key) ? "not stated" : "not applicable";
  }
}

/** Which pieces a key applies to (the format page, "Piece keys", its third column). */
export function appliesTo(piece, key) {
  const law = piece.piece === "law";
  const cellsLaw = law && CELLS_LAWS.has(piece.interface);
  const familyOperator = piece.piece === "operator" && piece.interface !== "cells.operator@1";
  const operator = piece.piece === "operator" && !familyOperator;
  const kind = piece.piece === "kind";
  switch (key) {
    case "kernels":
    case "provenance":
    case "test":
      return law || familyOperator;
    case "reads":
      return cellsLaw || operator;
    case "changes":
      return cellsLaw;
    case "owns":
    case "provides":
    case "controls":
      return kind || operator;
    case "writes":
    case "ledgers":
    case "energy":
    case "requires":
      return operator;
    case "laws":
      return kind;
    default:
      return true;
  }
}
