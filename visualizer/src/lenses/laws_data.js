// The Laws library's list, indexed for the view (schema/LAWS_LIBRARY.md): the pieces, the
// frames, who declares what, the search and the filters. No drawing here: the view, its card
// and its tests all ask this one place, so what is lit and what is said agree.

export const LAWS_FORMAT = "cells.visualizer.laws@1";
/** Ids the page uses for this view's parts: a piece or a frame, by its engine id. */
export const PREFIX = "laws:";
export const WHERE = [
  { id: "main", label: "On main", short: "Main" },
  { id: "candidate", label: "Landing candidate, not on main yet", short: "Candidate" },
  { id: "design", label: "Named in a design note; no code", short: "Design note" },
];

/** Where a piece stands registered: the lead's provisional answers of 16 November 2026 (schema, "What counts as a piece"). */
export const REGISTRIES = ["inner_laws.py", "the kind registry", "a registered kind", "OPERATORS", "a registered operator", "the inner model's structure", "a solver or step method", "an older family", "no registry"];
/** Not registered as a piece of the one model: drawn apart, narrower, on the upper part of its shelf. */
export const APART = new Set(["an older family", "no registry"]);

export const pageId = (id) => (id ? PREFIX + id : null);
export const engineId = (id) => (typeof id === "string" && id.startsWith(PREFIX) ? id.slice(PREFIX.length) : null);

/** The structural rules of the file, as a list of problems (empty when it holds). The tests and the view share them. */
export function problemsOf(raw) {
  const problems = [];
  if (!raw || raw.format !== LAWS_FORMAT) return [`not a ${LAWS_FORMAT} file`];
  const families = new Set((raw.families || []).map((family) => family.id));
  const frames = new Set((raw.frames || []).map((frame) => frame.id));
  const seen = new Set();
  for (const piece of raw.pieces || []) {
    if (seen.has(piece.id)) problems.push(`${piece.id} is listed twice`);
    seen.add(piece.id);
    if (!families.has(piece.family)) problems.push(`${piece.id}: family ${piece.family} is not a family of the file`);
    if (!WHERE.some((where) => where.id === piece.where)) problems.push(`${piece.id}: where is ${piece.where}`);
    if (piece.where === "design" ? piece.read !== null : !piece.read?.path || !piece.read?.revision) problems.push(`${piece.id}: its reading does not say where it was read`);
    if (piece.status && !(piece.status.source?.path && piece.status.level)) problems.push(`${piece.id}: a status with no source`);
    if (piece.box && !(piece.box.source?.path && piece.box.level)) problems.push(`${piece.id}: a box with no source`);
    for (const entry of piece.declared_by || []) if (!frames.has(entry.frame)) problems.push(`${piece.id}: declared by ${entry.frame}, which is not a frame of the file`);
    if (piece.where === "design" ? piece.registry !== null : !REGISTRIES.includes(piece.registry)) problems.push(`${piece.id}: its registry is ${piece.registry}`);
  }
  for (const item of raw.unregistered || []) if (seen.has(item.id)) problems.push(`${item.id} is not registered, and is listed as a piece`);
  for (const frame of raw.frames || []) {
    if (seen.has(frame.id)) problems.push(`${frame.id} is both a piece and a frame`);
    for (const row of frame.rows || []) for (const id of row.pieces) if (!seen.has(id)) problems.push(`frame ${frame.id} names ${id}, which is not a piece of the file`);
  }
  return problems;
}

export class Library {
  constructor(raw) {
    const problems = problemsOf(raw);
    if (problems.length) throw new Error(`The Laws library's list is not valid: ${problems.slice(0, 3).join("; ")}`);
    this.raw = raw;
    this.stamp = raw.stamp;
    this.families = raw.families;
    this.shelves = raw.shelves;
    this.pieces = raw.pieces;
    this.frames = raw.frames;
    this.byId = new Map(raw.pieces.map((piece) => [piece.id, piece]));
    this.frameById = new Map(raw.frames.map((frame) => [frame.id, frame]));
    this.familyById = new Map(raw.families.map((family) => [family.id, family]));
    this.shelfById = new Map((raw.shelves || []).map((shelf) => [shelf.id, shelf]));
    this.inFamily = new Map(raw.families.map((family) => [family.id, raw.pieces.filter((piece) => piece.family === family.id)]));
    // A kind's own pieces, as the file reads them.
    this.kindOf = new Map();
    for (const piece of raw.pieces) for (const id of piece.kind === "kind" ? piece.read?.fields?.pieces || [] : []) this.kindOf.set(id, piece.id);
  }

  piece(id) {
    return this.byId.get(id) || null;
  }

  frame(id) {
    return this.frameById.get(id) || null;
  }

  /** The frames drawn as racks (the older families stand apart, as a strip). */
  get racks() {
    return this.frames.filter((frame) => frame.kind !== "older family");
  }

  get older() {
    return this.frames.filter((frame) => frame.kind === "older family");
  }

  /** Whether a piece matches a search: its id, its unit, its file, its family and its label. */
  matches(piece, query) {
    const words = String(query || "").trim().toLowerCase();
    if (!words) return true;
    const family = this.familyById.get(piece.family);
    return [piece.id, piece.curated?.unit, piece.curated?.label, piece.read?.path, family?.label, piece.kind].some((text) => text && String(text).toLowerCase().includes(words));
  }

  /** Whether a piece passes the view's filters: a family, where it stands, and a search. */
  /** `box`: the pieces whose file an Engine view box holds (the door from that box; schema, "box"). */
  passes(piece, { family = null, where = null, query = "", box = null } = {}) {
    return (!family || piece.family === family) && (!where || piece.where === where) && (!box || piece.box?.id === box) && this.matches(piece, query);
  }

  /** The pieces an Engine view box holds, by the list's `box`: what the door from that box opens on. */
  inBox(id) {
    return this.pieces.filter((piece) => piece.box?.id === id);
  }

  /**
   * The slots a chosen piece lights: in each frame that declares it, the slots of its row, or
   * the slot of the kind or the block of the inner model it comes through (schema, "What
   * declares a piece"). Each is { frame, row, index } or { frame, block }.
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
      const target = entry.how === "kind" ? entry.via : id;
      frame.rows.forEach((row, r) => row.pieces.forEach((name, index) => name === target && out.push({ frame: frame.id, row: r, index })));
    }
    return out;
  }

  /** The pieces a chosen frame lights: every piece the file says it declares, in any way. */
  piecesOf(frameId) {
    return new Set(this.pieces.filter((piece) => (piece.declared_by || []).some((entry) => entry.frame === frameId)).map((piece) => piece.id));
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

  /** Counts of the file, by where each piece stands and by family. */
  counts() {
    const where = Object.fromEntries(WHERE.map((item) => [item.id, this.pieces.filter((piece) => piece.where === item.id).length]));
    const family = Object.fromEntries(this.families.map((item) => [item.id, this.inFamily.get(item.id).length]));
    return { pieces: this.pieces.length, where, family, frames: this.racks.length, older: this.older.length };
  }
}
