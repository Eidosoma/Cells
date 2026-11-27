// A species' own proteins, for the atlas's shelves (schema/SPECIES_PROTEINS.md): the file as
// the page reads it, where each marker stands, and the words said of a protein or a family.
// Nothing here draws; src/lenses/shelves_view.js does. Everything here runs without a browser.
//
// One format for every species: a shelf is a membrane, and a protein sits outside it, in it
// or inside it. A protein whose side is not known is set apart, never placed by guess.
//   a small catalogue   one marker for each protein (Syn3A, M. pneumoniae);
//   a large catalogue   every protein still shown, as families that open (the planarian).
//
// A species may have several shelves, one for each membrane its data tells apart (a curated
// proteome: human). Every line (a protein, a family's line, a part's line) is then on exactly
// one shelf or on none, and is identified by its id and its shelf together: a family has one
// line for each shelf that holds members of it. A protein with a shelf and no known side is
// set apart beside that shelf; one with no shelf at all stands apart from every shelf.
//
// A family with one member in the whole catalogue has no line: its protein is listed under
// `lone`, in parts by shelf, district and side. A part of `lone` opens straight to its
// proteins, each of which names its family; it is never called a family.

export const SHELVES_FORMAT = "cells.visualizer.species_proteins@1";
export const MEMBERS_FORMAT = "cells.visualizer.species_protein_members@1";
export const NAMES_FORMAT = "cells.visualizer.species_protein_names@1";
export const NAMES_FILE = "names.json";
export const SIDES = ["outside", "in", "inside", "not known"];
export const BASES = ["stated", "predicted", "by function", "none"];

// A family of this many proteins or more has a marker of its own; smaller ones are gathered,
// by district and side, into one marker that opens to them. The same for the parts of
// "no family", from this many. Where a family stands on several shelves, it is the family's
// members on every shelf and on none that count: every line of a family of five or more
// stands on its own, however few it holds on its shelf, so that no such family is seen only
// inside a gathering and a small shelf shows its families (settled on 15 November 2026, by
// looking: the human's cell shelf is not swamped by it). The parts of "no family" likewise.
export const OWN_FAMILY = 5;
export const OWN_PART = 10;

// The first letter in lower case, for a name within a sentence; an acronym keeps its capitals ("ER membrane").
const lower = (text) => (/^[A-Z][A-Z]/.test(text) ? text : text.charAt(0).toLowerCase() + text.slice(1));
const upper = (text) => text.charAt(0).toUpperCase() + text.slice(1);
const count = (n, one, many = `${one}s`) => `${n.toLocaleString("en-US")} ${n === 1 ? one : many}`;
export const plural = count;

/**
 * The id of a part the shelves make themselves: "own:<species>:<type>:<id>".
 * Where a species has several shelves, a family's line on one shelf is told from the same
 * family's line on another by its shelf, which stands with the type:
 * "own:<species>:<type>@<shelf>:<id>", with nothing after the @ for a line on no shelf.
 * Pass `shelf` (an id, or null for no shelf) only for such a line: without it the key is the
 * one-shelf key, which never changes. A protein's key never carries a shelf: it has one line.
 */
export const keyOf = (species, type, id, shelf) => (shelf === undefined ? `own:${species}:${type}:${id}` : `own:${species}:${type}@${shelf ?? ""}:${id}`);
/** A key's parts: { species, type, id }, and `shelf` (an id, or null for no shelf) where the key carries one. */
export function parseKey(key) {
  const parts = /^own:([^:]+):([a-z])(?:@([^:]*))?:(.*)$/.exec(key || "");
  if (!parts) return null;
  const out = { species: parts[1], type: parts[2], id: parts[4] };
  if (parts[3] !== undefined) out.shelf = parts[3] || null;
  return out;
}

/** The name under which the counts of the proteins on no shelf are given, beside the shelves' ids. */
export const NO_SHELF = "no shelf";

/**
 * How a source may be used, read from its own words: "permissive", "non-commercial", or
 * "no stated terms". A source that says so itself (a `class`) is taken at its word.
 */
export function licenceClass(source) {
  const said = String(source?.class || "").toLowerCase();
  if (/non-?commercial/.test(said)) return "non-commercial";
  if (/no stated|unlicen|no licence/.test(said)) return "no stated terms";
  if (said.includes("permissive")) return "permissive";
  const text = String(source?.licence || "").toLowerCase();
  if (/by-nc|(^|[^a-z])nc([^a-z]|$)|non-?commercial/.test(text)) return "non-commercial";
  if (/cc0|cc by|creative commons attribution|bsd|mit licen|public domain|no restriction|unrestricted|biopython licen/.test(text)) return "permissive";
  return "no stated terms";
}

/** Every source is shown with its class, in the contract's words. What was taken from it is in its own line. */
export const LICENCE_NOTE = {
  permissive: "A permissive licence: CC BY, CC0, or a plain statement that no restriction is placed on use.",
  "non-commercial": "Its licence does not allow commercial use.",
  "no stated terms": "It states no open licence.",
};
export const LICENCE_TAG = { permissive: "Permissive", "non-commercial": "Non-commercial", "no stated terms": "No stated terms" };

/**
 * A file published beside the page: a species' shelves, or the members of its families. It
 * is looked for in the page first (<script type="application/json" data-file="path">), as a
 * page opened from disk carries it, then fetched from `path`, an address relative to the page.
 * A request that gets no answer at all (a connection the server had just closed, a network
 * that blinked) is made again after each of `waits` (milliseconds) before the page gives it
 * up; an answer is taken at its word, "not there" included.
 */
export async function loadBeside(path, { root = globalThis.document, fetcher = globalThis.fetch, waits = [400, 1500] } = {}) {
  const inline = root?.querySelector?.(`script[type="application/json"][data-file="${path}"]`);
  if (inline) return JSON.parse(inline.textContent);
  if (typeof fetcher !== "function") throw new Error("this page cannot fetch it");
  let response = null;
  for (let attempt = 0; !response; attempt++) {
    try {
      response = await fetcher(path);
    } catch {
      if (attempt >= waits.length) throw new Error(`${path} could not be fetched`);
      await new Promise((resolve) => setTimeout(resolve, waits[attempt]));
    }
  }
  if (!response.ok) throw new Error(`${path} answered ${response.status}`);
  return response.json();
}

/**
 * The first problems of a shelves file against its contract; an empty list if it holds.
 * A file with several shelves is held to their rules as well: every line is on one of the
 * file's shelves or on none; a line on none holds only proteins whose side is not known; a
 * family has at most one line on a shelf; and what the file says of each shelf's counts, and
 * of the number of its families, is what its lines add up to.
 */
export function validateShelves(data) {
  const problems = [];
  if (data?.format !== SHELVES_FORMAT) return [`its format is ${data?.format}, not ${SHELVES_FORMAT}`];
  if (!data.species) problems.push("it names no species");
  if (!Array.isArray(data.shelves) || !data.shelves.length) problems.push("it has no shelf");
  if (!Array.isArray(data.proteins) && !Array.isArray(data.families)) problems.push("it holds neither proteins nor families");
  const groups = new Set((data.groups || []).map((group) => group.id));
  const ids = (Array.isArray(data.shelves) ? data.shelves : []).map((shelf) => shelf?.id);
  const several = ids.length > 1;
  if (several && (ids.some((id) => typeof id !== "string" || !id || id === NO_SHELF) || new Set(ids).size !== ids.length)) problems.push("its shelves do not each have an id of their own");
  // On several shelves: what stands on each, by side, as the lines have it.
  const tally = new Map();
  const add = (shelf, side, n) => {
    if (!tally.has(shelf)) tally.set(shelf, Object.fromEntries(SIDES.map((name) => [name, 0])));
    tally.get(shelf)[side] += n;
  };
  /** What is wrong with the shelf of a line that holds proteins on these sides, or null. */
  const misplaced = (shelf, sides) => {
    if (shelf === null) return Object.keys(sides).some((side) => side !== "not known" && sides[side]) ? "it is on no shelf, yet a side of it is known" : null;
    return ids.includes(shelf) ? null : `its shelf ${JSON.stringify(shelf)} is not one of the file's`;
  };
  if (Array.isArray(data.proteins)) {
    const at = Object.fromEntries((data.columns || []).map((name, index) => [name, index]));
    for (const name of ["id", "label", "shelf", "side", "basis", "group"]) if (!(name in at)) problems.push(`its columns lack ${name}`);
    if (!problems.length) {
      for (const row of data.proteins) {
        if (!SIDES.includes(row[at.side])) problems.push(`${row[at.id]}: the side ${row[at.side]}`);
        else if (!BASES.includes(row[at.basis])) problems.push(`${row[at.id]}: the basis ${row[at.basis]}`);
        else if (!groups.has(row[at.group])) problems.push(`${row[at.id]}: the group ${row[at.group]} is not declared`);
        else if (several) {
          const wrong = misplaced(row[at.shelf], { [row[at.side]]: 1 });
          if (wrong) problems.push(`${row[at.id]}: ${wrong}`);
          else add(row[at.shelf], row[at.side], 1);
        }
        if (problems.length > 4) break;
      }
    }
  }
  if (Array.isArray(data.families)) {
    const at = Object.fromEntries((data.family_columns || []).map((name, index) => [name, index]));
    for (const name of ["id", "label", "side", "group", "count", "file", "at", ...(several ? ["shelf", "sides"] : [])]) if (!(name in at)) problems.push(`its family columns lack ${name}`);
    if (!data.no_family) problems.push("it does not say where the proteins with no family are");
    // The proteins that are the only member of their family: parts shaped like those of no_family.
    const lone = data.lone && typeof data.lone === "object" ? data.lone : null;
    const loneAt = Object.fromEntries((lone?.part_columns || []).map((name, index) => [name, index]));
    const loneParts = lone?.parts || [];
    for (const name of ["id", "side", "group", "count", "sides", "file", "at", ...(several ? ["shelf"] : [])]) if (loneParts.length && !(name in loneAt)) problems.push(`the columns of the parts of lone lack ${name}`);
    if (lone && !problems.length && loneParts.reduce((sum, row) => sum + row[loneAt.count], 0) !== (lone.count ?? 0)) problems.push("the parts of lone do not add up to its count");
    if (several && !problems.length) {
      const none = data.no_family;
      const partAt = Object.fromEntries((none.part_columns || []).map((name, index) => [name, index]));
      const parts = none.parts || [];
      if (!parts.length && none.count) problems.push("on several shelves the proteins with no family are given in parts, each on its shelf");
      for (const name of ["id", "shelf", "side", "count", "sides"]) if (parts.length && !(name in partAt)) problems.push(`the columns of its parts lack ${name}`);
      if (!problems.length) {
        for (const [lines, where, what] of [[data.families, at, "family"], [loneParts, loneAt, "part of lone"], [parts, partAt, "part"]]) {
          const seen = new Set();
          for (const row of lines) {
            const shelf = row[where.shelf], sides = row[where.sides] || {}, name = `${row[where.id]}${shelf === null ? "" : ` on ${shelf}`}`;
            const wrong = shelf === undefined ? "it names no shelf" : misplaced(shelf, sides) || (shelf === null && row[where.side] !== "not known" ? "it is on no shelf, yet it stands on a side" : null);
            if (wrong) problems.push(`${name}: ${wrong}`);
            else if (seen.has(`${shelf}|${row[where.id]}`)) problems.push(`${name}: the ${what} has two lines on one shelf`);
            else if (Object.keys(sides).some((side) => !SIDES.includes(side)) || Object.values(sides).reduce((sum, n) => sum + n, 0) !== row[where.count]) problems.push(`${name}: its sides do not add up to its ${row[where.count]} members`);
            else for (const [side, n] of Object.entries(sides)) add(shelf, side, n);
            seen.add(`${shelf}|${row[where.id]}`);
            if (problems.length > 4) break;
          }
          if (problems.length > 4) break;
        }
      }
    }
    // Families with lines, and with those of one member as well: what the file says of them is what its lines give.
    if (!problems.length) {
      const distinct = new Set(data.families.map((row) => row[at.id])).size;
      if (typeof data.distinct_families === "number" && data.distinct_families !== distinct) problems.push(`it says it has ${data.distinct_families} families; its lines are of ${distinct}`);
      else if (typeof data.families_in_all === "number" && data.families_in_all !== distinct + (lone?.count ?? 0)) problems.push(`it says it has ${data.families_in_all} families in all; its lines and its lone proteins are of ${distinct + (lone?.count ?? 0)}`);
    }
    // The proteins picked out as sets (`highlights`): each names a mark the file declares and a line the file has.
    const picked = data.highlights;
    if (picked && !problems.length) {
      const where = Object.fromEntries((picked.columns || []).map((name, index) => [name, index]));
      const missing = ["mark", "value", "id", "kind", "under", "shelf", "side"].filter((name) => !(name in where));
      if (missing.length || !Array.isArray(picked.rows)) problems.push(`its highlights lack ${missing.join(", ") || "their rows"}`);
      else {
        const partAt = Object.fromEntries((data.no_family?.part_columns || []).map((name, index) => [name, index]));
        const lines = (list, columns) => new Set(list.map((row) => `${several ? row[columns.shelf] ?? null : ""}|${row[columns.id]}`));
        const has = { family: lines(data.families, at), lone: lines(loneParts, loneAt), part: lines(data.no_family?.parts || [], partAt) };
        for (const row of picked.rows) {
          const known = has[row[where.kind]];
          const wrong = !data.marks?.[row[where.mark]] ? `the mark ${row[where.mark]} is not declared` : !known ? `the kind ${row[where.kind]}` : !known.has(`${several ? row[where.shelf] ?? null : ""}|${row[where.under]}`) ? `no line ${row[where.under]}${several && row[where.shelf] !== null ? ` on ${row[where.shelf]}` : ""}` : null;
          if (!wrong) continue;
          problems.push(`highlights, ${row[where.id]}: ${wrong}`);
          break;
        }
      }
    }
  }
  // What the file says stands on each shelf is what its lines put there.
  if (several && !problems.length && data.shelf_counts && typeof data.shelf_counts === "object") {
    for (const name of Object.keys(data.shelf_counts)) if (name !== NO_SHELF && !ids.includes(name)) problems.push(`it counts a shelf ${JSON.stringify(name)} that it does not have`);
    for (const id of [...ids, null]) {
      const stated = data.shelf_counts[id ?? NO_SHELF], found = tally.get(id);
      if (!stated && !found) continue;
      if (SIDES.some((side) => (stated?.[side] || 0) !== (found?.[side] || 0))) problems.push(`its counts for ${id === null ? "the proteins on no shelf" : `the shelf ${id}`} are not those of its lines`);
    }
  }
  return problems;
}

const rows = (columns, lines) => lines.map((line) => Object.fromEntries(columns.map((name, index) => [name, line[index]])));

/**
 * How a membrane is named within a sentence, from its shelf's label: "the cell membrane";
 * "a membrane" for one shelf that stands for several not told apart; "a membrane, not told
 * which"; "one of the other membranes" for a shelf that stands for several that are named.
 */
function within(label) {
  const name = String(label).split(":")[0].trim();
  if (/not told apart/i.test(name)) return "a membrane";
  if (/^an? /i.test(name)) return lower(name);
  const definite = /^the /i.test(name) ? lower(name) : `the ${lower(name)}`;
  return /\bmembranes\b/i.test(name) ? `one of ${definite}` : definite;
}

/**
 * One species' own proteins, as read from its file.
 *   kind      "proteins" (one marker each) or "families" (families that open)
 *   markers   what stands on the shelves at rest
 *   several   whether the species has more than one shelf; a line's `shelf` is then the id
 *             of its shelf, or null for a line on no shelf
 *   byShelf   what stands on each shelf, and on none
 */
export class Shelves {
  constructor(data, { label = null, organism = null, links = null, units = null, found = null } = {}) {
    const problems = validateShelves(data);
    if (problems.length) throw new Error(`the file of proteins does not follow its format: ${problems.slice(0, 3).join("; ")}`);
    this.data = data;
    this.id = data.species;
    this.label = label || data.label || data.species;
    this.organism = organism || data.organism || null;
    this.links = links || {};
    this.units = units || new Map(); // inventory unit id -> the scene's part for it
    // How the species' atlas found each protein it lists with a unit (schema/SPECIES_PROTEINS.md, found_by), and the
    // atlas's own words for each way (the scene's product_found_by). A file without the block says nothing of it.
    const block = data.found_by || null;
    this.foundWords = new Map((found || []).map((word) => [word.id, word]));
    this.foundDefault = block?.default || null;
    this.foundOf = new Map(Object.entries(block?.proteins || {}).flatMap(([how, ids]) => ids.map((id) => [id, how])));
    this.goesWith = new Set(block?.families?.["accessory signature"] || []);
    // A species with no atlas of its own (the human) ties a protein to a unit by the inventory's own naming: those
    // whose every role there goes with the machine are listed, with their roles (inventory_roles), and drawn plain too.
    const roles = data.inventory_roles || null;
    this.roleOf = new Map(Object.entries(roles?.proteins || {}));
    this.rolesFamilies = new Set(roles?.families || []);
    for (const id of this.rolesFamilies) this.goesWith.add(id);
    // Every protein's name, once the names file beside the members is in (addNames): for the page's search.
    this.names = null;
    this.kind = Array.isArray(data.proteins) ? "proteins" : "families";
    this.shelves = data.shelves;
    this.shelf = data.shelves[0];
    this.several = data.shelves.length > 1;
    this.shelfById = new Map(data.shelves.map((shelf) => [shelf.id, shelf]));
    this.groups = new Map((data.groups || []).map((group) => [group.id, group]));
    this.marks = data.marks || {};
    this.notes = { ...(data.side_notes || {}) };
    this.notes.none ??= this.notes["not known"]; // a file may give that note under the side's own word
    this.sources = data.sources || [];
    // Whether every protein of the catalogue is itself a prediction (from a genome or from
    // transcripts, with none measured). The file says so: with a key of its own, or in the
    // words of its `from`. Nothing else makes the page call a protein predicted.
    this.predicted = typeof data.predicted === "boolean" ? data.predicted : /\bevery one is predicted\b/i.test(String(data.from || ""));
    this.byKey = new Map();
    this.lines = new Map(); // "<type>:<id>" -> a family's lines, or a part's, one for each shelf it is on
    this.loaded = new Map(); // member file -> its members, once fetched
    this.highlight = new Map(); // a mark picked out as a set -> its values -> { total, lines: line key -> its proteins, ids }
    if (this.kind === "proteins") {
      this.proteins = rows(data.columns, data.proteins).map((protein) => this.protein(protein, null));
      this.total = this.proteins.length;
      this.markers = this.proteins;
    } else this.readFamilies();
    this.counts = Object.fromEntries(SIDES.map((side) => [side, typeof data.counts?.[side] === "number" ? data.counts[side] : this.tally(side)]));
    this.byShelf = this.countShelves();
    // Where there are several shelves, each is itself a thing that can be chosen: the picture
    // then frames it. So is what stands on no shelf. Their keys carry the shelf as a line's does.
    this.shelfItems = new Map();
    if (this.several) {
      for (const entry of this.byShelf) {
        const item = { type: "s", key: keyOf(this.id, "s", "shelf", entry.id), id: "shelf", shelf: entry.id, label: entry.label ?? "No place known", count: entry.proteins, sides: entry.counts, units: [], entry };
        this.byKey.set(item.key, item);
        this.shelfItems.set(entry.id, item);
      }
    }
  }

  /** The key of a line: on several shelves a family's, a part's or a gathering's carries its shelf; a protein's never does. */
  keyFor(type, id, shelf) {
    return this.several && type !== "p" ? keyOf(this.id, type, id, shelf ?? null) : keyOf(this.id, type, id);
  }

  /** The shelf a line is on: its own, or that of the line it is under. With one shelf, that shelf; with several, null is no shelf. */
  shelfIdOf(line, under = null) {
    if (!this.several) return line.shelf ?? under?.shelf ?? this.shelf.id;
    return line.shelf !== undefined ? line.shelf : under ? under.shelf : null;
  }

  /** The shelf an item is on, as the file gives it, or null for one on no shelf. */
  shelfOf(item) {
    return item.shelf === null || item.shelf === undefined ? null : this.shelfById.get(item.shelf) || (this.several ? null : this.shelf);
  }

  /**
   * What stands on each shelf, in the file's order, and last what stands on none (where
   * anything does): { id, shelf, label, proteins, counts, lines, families, lone }. `counts`
   * are the four sides; `lines` the proteins of a small catalogue, or the lines of families
   * and of parts of a large one; `families` the families' lines among them; `lone` the
   * proteins that are the only member of their family. Counted from the lines.
   */
  countShelves() {
    const blank = (shelf) => ({ id: shelf ? shelf.id : null, shelf, label: shelf ? shelf.label : null, proteins: 0, counts: Object.fromEntries(SIDES.map((side) => [side, 0])), lines: 0, families: 0, lone: 0 });
    const all = new Map(this.shelves.map((shelf) => [shelf.id, blank(shelf)]));
    const none = blank(null);
    const of = (item) => (this.several ? (item.shelf === null ? none : all.get(item.shelf)) : all.get(this.shelf.id));
    for (const item of this.kind === "proteins" ? this.proteins : [...this.families, ...this.lone, ...this.parts]) {
      const entry = of(item);
      if (!entry) continue;
      entry.lines += 1;
      if (item.type === "f") entry.families += 1;
      if (item.type === "l") entry.lone += item.count;
      for (const [side, n] of this.kind === "proteins" ? [[item.side, 1]] : Object.entries(item.sides)) {
        entry.counts[side] += n;
        entry.proteins += n;
      }
    }
    return none.lines ? [...all.values(), none] : [...all.values()];
  }

  /** The same family's lines on the other shelves (a part's likewise), in the file's order: split over shelves, it is still one family. */
  sameFamily(item) {
    return (this.lines.get(`${item.type}:${item.id}`) || []).filter((other) => other !== item);
  }

  /** How many proteins a family has on all its shelves together. */
  familyTotal(item) {
    return (this.lines.get(`${item.type}:${item.id}`) || [item]).reduce((sum, line) => sum + line.count, 0);
  }

  /**
   * The key the shelves know for a key as it was given: itself; or, for a family's key that
   * names no shelf where the species has several (a link from another species, where the
   * family has the same id), that of the family's line with the most members. Null if none.
   */
  resolve(key) {
    if (this.byKey.has(key)) return key;
    const parts = parseKey(key);
    if (!parts || parts.species !== this.id || "shelf" in parts) return null;
    const lines = this.lines.get(`${parts.type}:${parts.id}`) || [];
    return lines.length ? lines.reduce((best, line) => (line.count > best.count ? line : best)).key : null;
  }

  tally(side) {
    if (this.kind === "proteins") return this.proteins.filter((protein) => protein.side === side).length;
    return [...this.families, ...this.lone, ...this.parts].reduce((sum, family) => sum + (family.sides?.[side] || 0), 0);
  }

  /** A protein of the catalogue, or a member of a family. */
  protein(line, under) {
    const unit = Array.isArray(line.unit) ? line.unit : line.unit ? [line.unit] : [];
    const protein = { ...line, type: "p", key: keyOf(this.id, "p", line.id), marks: line.marks || {}, units: unit, under, count: 1 };
    protein.found = unit.length ? this.foundOf.get(line.id) || this.foundDefault : null;
    protein.label = line.label || under?.label || line.id;
    protein.group = line.group ?? under?.group;
    protein.shelf = this.shelfIdOf(line, under);
    this.byKey.set(protein.key, protein);
    return protein;
  }

  readFamilies() {
    const data = this.data;
    const family = (line, type) => {
      const shelf = this.several ? this.shelfIdOf(line) : line.shelf || this.shelf.id;
      const item = { ...line, type, key: this.keyFor(type, line.id, shelf), units: line.units || [], where: line.where || [], sides: line.sides || {}, shelf };
      this.byKey.set(item.key, item);
      // A family's lines, and a part's, belong together across shelves. The parts of `lone` do not: each is of its own shelf.
      if (type !== "l") {
        const lines = this.lines.get(`${type}:${line.id}`);
        if (lines) lines.push(item);
        else this.lines.set(`${type}:${line.id}`, [item]);
      }
      return item;
    };
    this.families = rows(data.family_columns, data.families).map((line) => family(line, "f"));
    const none = data.no_family || {};
    this.parts = rows(none.part_columns || [], none.parts || []).map((line) => family(line, "g"));
    // "No family" given whole, with no parts: it opens like one family.
    if (!this.parts.length && none.count) this.parts = [family({ id: "none", label: none.label || "No family assigned", side: majority(none.sides), group: null, count: none.count, sides: none.sides || {}, file: none.file, at: none.at, kind: "no family" }, "g")];
    this.noFamily = { label: none.label || "No family assigned", count: none.count ?? this.parts.reduce((sum, part) => sum + part.count, 0), from: none.parts_from || null };
    // The proteins that are the only member of their family: no line among the families, but
    // parts of their own, one for a shelf, a district and a side, which open straight to them.
    const alone = data.lone || {};
    this.lone = rows(alone.part_columns || [], alone.parts || []).map((line) => family(line, "l"));
    this.loneAll = { label: alone.label || "The only member of its family", count: alone.count ?? this.lone.reduce((sum, part) => sum + part.count, 0), from: alone.parts_from || null };
    this.total = this.families.reduce((sum, item) => sum + item.count, 0) + this.loneAll.count + this.noFamily.count;
    // A family split over several shelves is one family: how many have lines, as well as how
    // many lines; and how many there are in all, with those of one member.
    this.familyCount = new Set(this.families.map((item) => item.id)).size;
    this.familiesInAll = this.familyCount + this.loneAll.count;
    // The parts of "no family" stand in a district of their own, after the others.
    this.noGroup = { id: "no-family", label: this.noFamily.label, from: this.noFamily.from };
    for (const part of this.parts) part.district = this.noGroup.id;
    for (const item of this.families) item.district = item.group;
    for (const part of this.lone) part.district = part.group; // among the families of its district
    // A line stands on its own if its family (or its part) has enough members on all its shelves
    // together: the line says so itself (`total`), or its lines are added up. With one shelf that is its own count.
    const whole = (item) => (typeof item.total === "number" ? item.total : this.familyTotal(item));
    // The smaller ones, gathered: one marker for a district and a side (and, where there are
    // several shelves, for a shelf), which opens to them.
    const gather = (items, limit, type, words) => {
      const own = [], small = new Map();
      for (const item of items) {
        // A part that is not a superfamily (the proteins with a domain only, or no signature) stands alone.
        if (whole(item) >= limit || (type === "n" && item.kind && item.kind !== "superfamily")) own.push(item);
        else {
          const id = `${item.district}|${item.side}`, among = this.several ? `${item.shelf ?? ""}|${id}` : id;
          if (!small.has(among)) small.set(among, { type, key: this.keyFor(type, id, item.shelf), id, district: item.district, group: item.group, side: item.side, shelf: item.shelf, holds: [], count: 0, sides: {}, units: [], where: [] });
          const more = small.get(among);
          more.holds.push(item);
          more.count += item.count;
          for (const [side, n] of Object.entries(item.sides)) more.sides[side] = (more.sides[side] || 0) + n;
          for (const unit of item.units) if (!more.units.includes(unit)) more.units.push(unit);
          item.within = more;
        }
      }
      for (const more of small.values()) {
        more.label = `${count(more.holds.length, `smaller ${words[0]}`, `smaller ${words[1]}`)}`;
        this.byKey.set(more.key, more);
      }
      return [...own, ...small.values()];
    };
    this.markers = [...gather(this.families, OWN_FAMILY, "m", ["family", "families"]), ...this.lone, ...gather(this.parts, OWN_PART, "n", ["group", "groups"])];
    // The proteins that carry a mark the page may pick out as a set (`highlights`), by the line
    // each stands on: so the markers that hold them are known before any member is fetched.
    const picked = this.data.highlights, at = Object.fromEntries((picked?.columns || []).map((name, index) => [name, index]));
    for (const row of picked?.rows || []) {
      const type = { family: "f", lone: "l", part: "g" }[row[at.kind]], key = type ? this.keyFor(type, row[at.under], row[at.shelf]) : null;
      if (!this.marks[row[at.mark]] || !this.byKey.has(key)) continue;
      if (!this.highlight.has(row[at.mark])) this.highlight.set(row[at.mark], new Map());
      const values = this.highlight.get(row[at.mark]), value = String(row[at.value]);
      if (!values.has(value)) values.set(value, { total: 0, lines: new Map(), ids: new Set() });
      const set = values.get(value);
      set.total += 1;
      set.ids.add(row[at.id]);
      if (!set.lines.has(key)) set.lines.set(key, []);
      set.lines.get(key).push({ id: row[at.id], gene: row[at.gene] || null });
    }
  }

  /**
   * The proteins of one set (a mark of `highlights` and one of its values) that an item
   * holds: those on a line; those on the lines a gathering holds; for a protein, itself if
   * it is one of them. Each { id, gene }.
   */
  highlightOf(item, name, value, ids = null) {
    const set = this.highlight.get(name)?.get(String(value));
    if (!set || !item) return [];
    // A door may name some proteins of the set (the proteins of one part of a machine): only those are picked out.
    const keep = ids ? (protein) => ids.has(protein.id) : () => true;
    if (item.type === "p") return set.ids.has(item.id) && keep(item) ? [{ id: item.id, gene: item.gene || null }] : [];
    if (item.holds) return item.holds.flatMap((line) => set.lines.get(line.key) || []).filter(keep);
    return (set.lines.get(item.key) || []).filter(keep);
  }

  /** How many proteins of a set there are, or of the ones of it a door names: what a marker's tag counts against. */
  highlightTotal(name, value, ids = null) {
    const set = this.highlight.get(name)?.get(String(value));
    if (!set) return 0;
    return ids ? [...set.ids].filter((id) => ids.has(id)).length : set.total;
  }

  get(key) {
    return this.byKey.get(key) || null;
  }

  /** The district a marker stands in. */
  district(item) {
    const id = item.district ?? item.group;
    return id === this.noGroup?.id ? this.noGroup : this.groups.get(id) || { id, label: id || "Not classed" };
  }

  /** The district's name, as it is written on the shelf. */
  districtLabel(item) {
    return this.district(item).label;
  }

  /** The district with the wider class it belongs to, where the file names one: for the panel and the list. */
  districtPath(item) {
    const group = this.district(item);
    return group.within ? `${group.within}: ${group.label}` : group.label;
  }

  /** What holds the products of one inventory unit: its proteins in a small catalogue, its families in a large one; the largest first. */
  holdersOf(unit) {
    const from = this.kind === "proteins" ? this.proteins : [...this.families, ...this.lone, ...this.parts];
    return from.filter((item) => item.units.includes(unit)).sort((a, b) => b.count - a.count);
  }

  /** The member files a family, a part or a gathering needs before it can open. */
  filesOf(item) {
    const files = new Set();
    for (const family of item.holds || [item]) if (family.file) files.add(family.file);
    return [...files];
  }

  /** Take in a fetched member file (schema: cells.visualizer.species_protein_members@1). */
  addMembers(name, file) {
    if (file?.format !== MEMBERS_FORMAT || !Array.isArray(file.members)) throw new Error(`${name} is not a file of members`);
    this.loaded.set(name, { columns: file.columns, members: file.members });
  }

  /** The members of a family, a part or a gathering, once their files are in; null before. */
  membersOf(item) {
    if (this.kind === "proteins") return null;
    if (item.members) return item.members;
    const out = [];
    for (const family of item.holds || [item]) {
      const file = this.loaded.get(family.file);
      if (!file) return null;
      const [from, to] = family.at;
      if (!family.members) {
        const lines = file.members.slice(from, to);
        if (lines.length !== family.count) throw new Error(`${family.file} holds ${lines.length} members of ${family.label}, not the ${family.count} stated: the files beside the page are of another catalogue`);
        family.members = rows(file.columns, lines).map((line) => this.protein(line, family));
      }
      out.push(...family.members);
    }
    item.members = out;
    return out;
  }

  // ------------------------------------------------------------ words

  /** A shelf of the file, from its id, from itself, or from nothing (the first); null for what is on no shelf. */
  shelfFor(of) {
    if (of === null) return this.several ? null : this.shelf;
    return of === undefined ? this.shelf : typeof of === "string" ? this.shelfById.get(of) || this.shelf : of;
  }

  /**
   * A shelf's membrane as it is named within a sentence: "the cell membrane", "a membrane,
   * not told which", "one of the other membranes". A shelf may say it itself, in the words
   * of its `in` ("In the envelope of the nucleus"), where its label does not read so.
   */
  membraneOf(of) {
    const shelf = this.shelfFor(of);
    if (!shelf) return "a membrane";
    return typeof shelf.in === "string" && /^In \S/.test(shelf.in) ? shelf.in.slice(3) : within(shelf.label);
  }

  /**
   * The names of the four sides against one shelf: short for the picture, long for the page.
   * `of` is a shelf's id or the shelf itself; with none, the species' first shelf. For what
   * is on no shelf (null) only "not known" has a meaning: no place is known for it.
   */
  sideWords(of) {
    const shelf = this.shelfFor(of);
    const short = (text) => String(text).split(":")[0];
    const one = this.membraneOf(of);
    if (!shelf) {
      return {
        outside: { short: "Beyond a membrane", long: "Beyond a membrane", swatch: "own-outside" },
        in: { short: `In ${one}`, long: `Spans ${one}`, swatch: "own-in" },
        inside: { short: "Within a membrane", long: "Within a membrane", swatch: "own-inside" },
        "not known": { short: "No place known", long: "No source states where it is and nothing predicts it: it stands apart from every shelf, not placed by guess", swatch: "own-unknown" },
      };
    }
    return {
      outside: { short: short(shelf.outside), long: shelf.outside, swatch: "own-outside" },
      in: { short: `In ${one}`, long: `Spans ${one}`, swatch: "own-in" },
      inside: { short: short(shelf.inside), long: shelf.inside, swatch: "own-inside" },
      "not known": this.several
        ? { short: "Side not known", long: `No source states its side of ${one.split(",")[0]} and nothing predicts it: set apart beside its shelf, not placed by guess`, swatch: "own-unknown" }
        : { short: "Side not known", long: "No source states the side and nothing predicts it: set apart, not placed by guess", swatch: "own-unknown" },
    };
  }

  /** How a side is known, in a few plain words. */
  basisWords(basis) {
    return {
      stated: { label: "Stated", sentence: "A curated entry or a paper states it." },
      predicted: { label: "Predicted", sentence: this.predicted ? "That is predicted from the sequence of a protein that is itself predicted; it was not measured." : "That is predicted from its sequence; it was not measured." },
      "by function": { label: "By function", sentence: "That is taken from what the protein is annotated to do, not measured." },
      none: { label: "Not known", sentence: "No source states its side and nothing predicts it, so it is set apart and not placed by guess." },
    }[basis];
  }

  /** Where a protein on that side of a shelf is, as the end of a sentence that begins "It"; null where the side is not known. */
  where(side, of) {
    const words = this.sideWords(of)[side];
    return side === "not known" ? null : side === "in" ? lower(words.long) : `is ${lower(words.short)}`;
  }

  /** Addresses to look a protein up at, built from the overlay's patterns for this species. */
  linksFor(item) {
    const out = [];
    if (item.type === "p") {
      for (const pattern of this.links[this.id] || []) {
        if (pattern.kind && pattern.kind !== item.marks?.kind) continue;
        if (pattern.match && !new RegExp(pattern.match).test(item.id)) continue;
        out.push({ text: pattern.text.replaceAll("{id}", item.id), url: pattern.url.replaceAll("{id}", encodeURIComponent(item.id)) });
      }
    } else if (/^IPR\d{6}$/.test(item.id) && this.links.family) {
      const pattern = this.links.family;
      out.push({ text: pattern.text.replaceAll("{id}", item.id), url: pattern.url.replaceAll("{id}", item.id) });
    }
    return out;
  }

  /** What the page lists of the file's sources, each with how it may be used. */
  sourceItems() {
    return this.sources.map((source) => {
      const kind = licenceClass(source);
      const holds = source.holds ? `${source.holds.charAt(0).toUpperCase()}${source.holds.slice(1)}` : null;
      return {
        label: source.name,
        tag: LICENCE_TAG[kind] || null,
        tag_title: LICENCE_NOTE[kind] || "",
        detail: holds,
        lines: [source.licence ? `Terms: ${source.licence}` : "It states no terms.", source.through ? `Read through ${source.through}.` : null].filter(Boolean),
        links: /^https:\/\//.test(source.url || "") ? [{ text: source.name, url: source.url }] : [],
        kind,
      };
    });
  }

  /**
   * The marks a protein carries, as lines of facts, in the file's own labels (an estimate is
   * labelled so there). A mark the file declares as measured says so; no other is called measured.
   * A mark may say its value in a sentence of the file's own (`says`, with "{value}" where the
   * value goes), each value in the words the file gives it (`words`): the planarian's members
   * filed by what its own scan added say so, with the databases behind them. `only` keeps those alone.
   */
  markFacts(item, but = [], only = false) {
    const facts = [];
    for (const [name, value] of Object.entries(item.marks || {})) {
      const mark = this.marks[name];
      if (!mark || value === null || value === undefined || but.includes(name) || only !== this.tells(name)) continue;
      // "No" is said only of a mark that can be either; a mark that is only ever set is left out when it is not.
      if (value === false && !(Array.isArray(mark.values) && mark.values.includes(false))) continue;
      let said = value === true ? "yes" : value === false ? "no" : Array.isArray(value) ? value.join(", ") : typeof value === "number" ? value.toLocaleString("en-US") : String(value);
      if (this.tells(name)) {
        const words = [].concat(value).map((one) => String(mark.words?.[one] ?? one));
        said = mark.says.replace("{value}", words.length > 1 ? `${words.slice(0, -1).join(", ")} and ${words.at(-1)}` : words[0]);
      }
      facts.push([mark.label || name, mark.measured ? `${said} (measured)` : said]);
    }
    return facts;
  }

  /** Whether a mark says its value in a sentence of the file's own (`says`). */
  tells(name) {
    return typeof this.marks[name]?.says === "string" && this.marks[name].says.includes("{value}");
  }

  /**
   * Whether the atlas lists this protein, or every protein of this family that has a unit, with
   * the unit only because it carries the signature of a family that goes with the machine (a
   * regulator, or a subunit that makes none by itself). Such a one is drawn plain, not in the
   * unit's shape, and is no candidate for the machine's own work.
   */
  goesWithOnly(item) {
    if (!item?.units?.length) return false;
    if (item.type === "p") return item.found === "accessory signature" || this.roleOf.has(item.id);
    return item.type === "f" && this.goesWith.has(item.id);
  }

  /** Everything the panel says of one protein. */
  describeProtein(protein) {
    const words = this.sideWords(protein.shelf)[protein.side], basis = this.basisWords(protein.basis);
    const modelled = protein.units.length > 0;
    const where = this.where(protein.side, protein.shelf);
    const shelf = this.shelfOf(protein);
    // With several shelves, a side that is not known is one of two things: the shelf is known
    // and the side of it is not; or no place is known at all.
    const unplaced = !this.several
      ? `${this.predicted ? "A predicted protein. Its" : "Its"} side of the membrane is not known. ${basis.sentence}`
      : shelf
        ? `${this.predicted ? "A predicted protein. Its" : "Its"} side of ${this.membraneOf(shelf).split(",")[0]} is not known. No source states it and nothing predicts it, so it is set apart beside its shelf and not placed by guess.`
        : `${this.predicted ? "A predicted protein. No" : "No"} place is known for it: no source states where it is and nothing predicts it, so it stands apart from every shelf and is not placed by guess.`;
    const goes = this.goesWithOnly(protein);
    const chips = [
      !modelled
        ? { label: "Not in the law inventory", swatch: "own-plain", title: "This protein is listed with no unit of Cells' law inventory. It is one of the species' own proteins, drawn as a plain marker." }
        : goes && this.roleOf.has(protein.id)
          ? { label: "Goes with a unit of the law inventory", swatch: "own-plain", title: `The law inventory names it among the unit's products as ${this.roleOf.get(protein.id).map((role) => `"${role}"`).join(" and ")}: a part that goes with the machine, not the one that does its work. It is no candidate for the machine's own work, and is drawn as a plain marker. The law is the unit's: the engine does not model this protein.` }
          : goes
          ? { label: "Goes with a unit of the law inventory", swatch: "own-plain", title: "The species' atlas lists it with a unit of the law inventory because its own record carries only the signature of a family that goes with the machine: a regulator, or a subunit that makes none by itself. It is no candidate for the machine's own work, and is drawn as a plain marker. The law is the unit's: the engine does not model this protein." }
          : { label: "Would make a unit of the law inventory", swatch: "map-assigned", title: "The species' atlas lists it among the gene products that would make a unit of the law inventory. The law is the unit's: the engine does not model this protein." },
      { label: words.short, swatch: words.swatch, title: words.long },
      { label: basis.label, title: basis.sentence },
    ];
    const under = protein.under;
    const facts = [["Identifier", protein.id]];
    if (protein.gene) facts.push(["Gene", protein.gene]);
    if (protein.length) facts.push(["Length", `${Number(protein.length).toLocaleString("en-US")} amino acids`]);
    // How the atlas found it, and what that makes it a candidate for, in the atlas panel's own words.
    const found = modelled ? this.foundWords.get(protein.found) : null;
    if (found) {
      facts.push(["How the atlas found it", found.label]);
      if (found.line) facts.push(["In the atlas", found.line]);
    }
    // Where the tie is the inventory's own naming (inventory_roles), its role in the inventory's words.
    if (modelled && this.roleOf.has(protein.id)) facts.push(["Named by the inventory as", `${this.roleOf.get(protein.id).join("; ")}: it goes with the machine`]);
    // One listed among the only members of their families names its own family in a mark: [accession, name].
    const alone = under?.type === "l";
    const family = alone ? [].concat(protein.marks?.family || []) : [];
    if (under && !alone) facts.push([under.type === "g" ? "Filed under" : "Family", `${under.label}${/^IPR\d/.test(under.id) ? ` (${under.id})` : ""}`]);
    if (family.length) facts.push(["Family", `${family[1] || family[0]}${family[1] && /^IPR\d/.test(family[0]) ? ` (${family[0]})` : ""}: its only member in this catalogue`]);
    // What it is filed by, where the file says so in a sentence (a member filed by what the species' own scan added).
    facts.push(...this.markFacts(protein, [], true));
    if (protein.group || under) facts.push(["District", this.districtPath(under || protein)]);
    if (this.several) facts.push(["Shelf", shelf ? shelf.label : "None: no place is known"]);
    facts.push(...this.markFacts(protein, family.length ? ["family"] : []));
    const notes = Object.entries(protein.marks || {}).map(([name]) => this.marks[name]).filter((mark) => mark?.note).map((mark) => `${mark.label}: ${mark.note}${mark.source ? ` Source: ${mark.source}.` : ""}`);
    const links = this.linksFor(protein);
    // Its own family is looked up where any family is.
    if (/^IPR\d{6}$/.test(family[0] || "") && this.links.family) links.push({ text: this.links.family.text.replaceAll("{id}", family[0]), url: this.links.family.url.replaceAll("{id}", family[0]) });
    return {
      id: protein.key,
      kind: "protein",
      label: protein.label,
      eyebrow: `${this.label} protein`,
      chips,
      plain: where ? `${this.predicted ? "A predicted protein. It" : "It"} ${where}. ${basis.sentence}` : unplaced,
      facts,
      sections: [
        links.length ? { title: "Look it up", items: [{ label: protein.id, links }] } : null,
        { title: "Sources and licences", items: this.sourceItems() },
      ].filter(Boolean),
      // How the side was read, and what the marks mean, in the file's own words: a press away.
      disclosures: [
        this.notes[protein.basis] ? { title: `How a side is ${protein.basis === "none" ? "left unknown" : protein.basis === "by function" ? "taken from function" : protein.basis}`, lines: [this.notes[protein.basis]] } : null,
        notes.length ? { title: "What its marks mean", lines: notes } : null,
      ].filter(Boolean),
      related: modelled ? [{ title: goes ? "Listed in the atlas with" : "Drawn in the atlas as", ids: protein.units.map((unit) => this.units.get(unit)).filter(Boolean) }] : [],
      opens: under ? [{ title: under.type === "g" ? "Filed under" : alone ? "Listed with" : "Its family", items: [{ id: under.within?.key && !under.members ? under.within.key : under.key, label: under.label, swatch: under.units.length ? "map-assigned" : "own-family" }] }] : [],
      keywords: [protein.id, protein.gene, alone ? family.join(" ") : under?.label].filter(Boolean).join(" "),
      swatch: modelled ? "map-assigned" : "own-plain",
    };
  }

  /**
   * How the sides of a large catalogue's proteins are known, as a sentence about the members
   * of a family. Where curators state most of them (a curated proteome), it says so and
   * leaves the rest to each member's own card; otherwise they are predictions.
   */
  membersBasis() {
    if (this.mostlyStated()) return "Most members' sides are as curated entries state them; each member's card says how its own is known.";
    // A file of several shelves that does not count its sides by how they are known: nothing is claimed of them here.
    if (this.several && !this.data.by_basis) return "Each member's card says how its side is known.";
    return this.basisWords("predicted").sentence.replace(/^That is/, "Each member's side is");
  }

  /** Whether sources state more of the sides than are predicted or taken from function: a curated proteome. Counted once. */
  mostlyStated() {
    if (this.statedMost === undefined) {
      const how = this.byBasis();
      this.statedMost = how.stated > how.predicted + how["by function"];
    }
    return this.statedMost;
  }

  /** Everything the panel says of a family, a part of "no family", or a gathering of small ones. */
  describeFamily(item) {
    const sides = this.sideWords(item.shelf);
    const gathered = Boolean(item.holds);
    const part = item.type === "g" || item.type === "n";
    const lone = item.type === "l"; // the only members of their families: not a family, and it says so
    const shelf = this.shelfOf(item), loose = this.several && !shelf;
    const spread = SIDES.filter((side) => item.sides?.[side]).map((side) => `${count(item.sides[side], "protein")} ${side === "not known" ? (loose ? "with no place known" : "with no side known") : side === "in" ? lower(sides.in.long).replace(/^spans/, "spanning") : lower(sides[side].short)}`);
    const members = this.membersOf(item);
    const modelled = item.units.length > 0;
    // A family split over several shelves is one family: this line holds its members on one shelf.
    const others = gathered ? [] : this.sameFamily(item);
    const all = others.reduce((sum, other) => sum + other.count, item.count);
    const here = loose ? "on no shelf, since no place is known for them" : `on this shelf, ${this.membraneOf(shelf)}`;
    const those = item.count === 1 ? "that one" : `those ${item.count.toLocaleString("en-US")}`;
    const what = gathered
      ? `${item.label} of ${this.districtLabel(item)}, gathered so that they do not swamp the shelf: ${count(item.count, "protein")} in all. Opening it shows every one of them.`
      : lone
        ? item.count === 1
          ? `The only member of its family: 1 protein of ${this.districtLabel(item)}, alone in its family in this catalogue. ${loose ? "No place is known for it, so it stands apart from every shelf" : "It stands here among the families of its district"}; opening this shows it, with the name of its family. This is not a family.`
          : `The only member of its family: ${count(item.count, "protein")} of ${this.districtLabel(item)}, each alone in its family in this catalogue. ${loose ? "No place is known for any of them, so they stand together apart from every shelf" : "They stand together here so that they do not swamp the shelf"}; opening it shows every one of them, each with the name of its family. This is not a family.`
        : part
        ? `${count(item.count, "protein")} with no family signature, filed here ${item.kind === "superfamily" ? "by the superfamily they share, a wider grouping than a family" : item.kind === "no signature" ? "because they carry no signature of any kind" : "because they carry only a domain, a repeat or a site signature"}. This is not a family.${others.length ? ` These are the ones ${here}; ${count(all - item.count, "more stands", "more stand")} elsewhere.` : ""}`
        : others.length
          ? `A family of ${count(all, "protein")}, ${item.count.toLocaleString("en-US")} of them ${here}. Opening it shows ${those}.`
          : `A family of ${count(item.count, "protein")}. Opening it shows every member.`;
    const facts = [];
    if (/^IPR\d/.test(item.id)) facts.push(["InterPro entry", item.id]);
    facts.push(["Proteins", item.count.toLocaleString("en-US")]);
    if (gathered) facts.push([part ? "Groups" : "Families", item.holds.length.toLocaleString("en-US")]);
    facts.push(["District", this.districtPath(item)]);
    if (this.several) facts.push(["Shelf", shelf ? shelf.label : "None: no place is known"]);
    if (spread.length) facts.push(["Where its members sit", spread.join("; ")]);
    if (others.length) facts.push(["Elsewhere", others.map((other) => `${count(other.count, "protein")} ${other.shelf === null ? "on no shelf" : `at ${this.membraneOf(other.shelf)}`}`).join("; ")]);
    if (item.where?.length) facts.push(["Named place", `${item.where.join(", ")} (an annotation carried by signatures, not a prediction for these proteins)`]);
    // Once its members are in: how many are filed by what a mark that tells its ground names (the planarian's own scan).
    for (const [name, mark] of Object.entries(this.marks)) {
      const by = this.tells(name) && mark.members_label && members ? members.filter((member) => member.marks?.[name]).length : 0;
      if (by) facts.push([mark.members_label, by === members.length ? (by === 1 ? "its one member" : `all ${by.toLocaleString("en-US")}`) : `${by.toLocaleString("en-US")} of ${members.length.toLocaleString("en-US")}`]);
    }
    const links = this.linksFor(item);
    const listed = (members || []).slice(0, 400).map((member) => ({ id: member.key, label: member.label === item.label ? member.id : `${member.label} · ${member.id}`, swatch: member.units.length ? "map-assigned" : "own-plain" }));
    const held = gathered ? item.holds.slice(0, 400).map((family) => ({ id: family.key, label: `${family.label} · ${family.count}`, swatch: family.units.length ? "map-assigned" : "own-family" })) : [];
    // The same family's lines on the other shelves; one that stands gathered there leads to what holds it.
    const elsewhere = others.map((other) => ({ id: other.within?.key && !other.members ? other.within.key : other.key, label: `${other.shelf === null ? "On no shelf" : this.shelfOf(other)?.label || other.shelf} · ${other.count}`, swatch: other.units.length ? "map-assigned" : "own-family" }));
    const stated = this.mostlyStated();
    return {
      id: item.key,
      kind: "family",
      label: item.label,
      eyebrow: gathered ? `${this.label} proteins` : lone ? `${this.label} proteins, each the only one of its family` : part ? `${this.label} proteins with no family` : `${this.label} protein family`,
      chips: [
        !modelled
          ? { label: "Not in the law inventory", swatch: "own-family", title: "These proteins are listed with no unit of Cells' law inventory." }
          : this.goesWithOnly(item) && this.rolesFamilies.has(item.id)
            ? { label: "Holds parts that go with a unit of the law inventory", swatch: "own-family", title: "The law inventory names its members with a unit only in roles that go with the machine: an auxiliary subunit, or a regulator. None is a candidate for the machine's own work, and the family is drawn plain. The law is the unit's: the engine does not model these proteins." }
          : this.goesWithOnly(item)
            ? { label: "Holds parts that go with a unit of the law inventory", swatch: "own-family", title: "Its members are listed with a unit of the law inventory only because they carry the signature of a family that goes with the machine: a regulator, or a subunit that makes none by itself. None is a candidate for the machine's own work, and the family is drawn plain. The law is the unit's: the engine does not model these proteins." }
            : { label: "Holds parts of a unit of the law inventory", swatch: "map-assigned", title: "Some of its members are listed with a unit of the law inventory: candidates for its unit, or parts that go with it. The law is the unit's: the engine does not model these proteins." },
        { label: loose ? "No place known" : `Most ${lower(sides[item.side].short)}`, swatch: sides[item.side].swatch, title: "A family stands on the side where most of its members sit; each member keeps its own." },
      ],
      plain: `${what} ${this.membersBasis()}`,
      facts,
      disclosures: [
        stated && this.notes.stated ? { title: "How a side is stated", lines: [this.notes.stated] } : null,
        this.notes.predicted ? { title: "How a side is predicted", lines: [this.notes.predicted] } : null,
      ].filter(Boolean),
      sections: [
        links.length ? { title: "Look it up", items: [{ label: item.id, links }] } : null,
        { title: "Sources and licences", items: this.sourceItems() },
      ].filter(Boolean),
      related: modelled ? [{ title: "Holds proteins listed with", ids: item.units.map((unit) => this.units.get(unit)).filter(Boolean) }] : [],
      opens: [
        held.length ? { title: part ? "Its groups" : "Its families", items: held, more: item.holds.length - held.length, count: item.holds.length } : null,
        elsewhere.length ? { title: part ? "The same grouping on other shelves" : "The same family on other shelves", items: elsewhere, more: 0, count: elsewhere.length } : null,
        members ? { title: "Its proteins", items: listed, more: members.length - listed.length, count: members.length } : null,
      ].filter(Boolean),
      keywords: [item.id, ...(item.holds || []).map((family) => family.label)].join(" "),
      swatch: modelled ? "map-assigned" : "own-family",
    };
  }

  /** What the panel says of one shelf, or of what stands on no shelf: what it is and what stands on it. */
  describeShelf(item) {
    const entry = item.entry, shelf = entry.shelf, words = this.sideWords(shelf ? shelf.id : null);
    const spread = SIDES.filter((side) => entry.counts[side]).map((side) => `${count(entry.counts[side], "protein")} ${side === "not known" ? (shelf ? "with no side known, set apart beside it" : "with no place known") : side === "in" ? lower(words.in.long).replace(/^spans/, "spanning") : lower(words[side].short)}`);
    const facts = [["Proteins", entry.proteins.toLocaleString("en-US")]];
    if (spread.length) facts.push(["Where they sit", spread.join("; ")]);
    if (this.kind === "families") {
      facts.push(["Lines of families", entry.families.toLocaleString("en-US")]);
      if (entry.lone) facts.push(["The only member of its family", entry.lone.toLocaleString("en-US")]);
    }
    return {
      id: item.key,
      kind: "family",
      label: item.label,
      eyebrow: shelf ? `${this.label} proteins: one of ${this.shelves.length} shelves` : `${this.label} proteins on no shelf`,
      chips: [{ label: "No shelf in the law inventory", swatch: "own-family", title: "A shelf is a membrane of the cell, drawn so that each protein can be placed against it. Cells' law inventory lists machines, not shelves." }],
      plain: shelf
        ? `A shelf is a membrane: ${count(entry.proteins, "protein")} stand against ${this.membraneOf(shelf)}, each outside it, in it or inside it, as far as the sources say.${shelf.note ? ` ${shelf.note}` : ""}`
        : `${count(entry.proteins, "protein")} have no stated place and nothing predicts one. They stand apart from every shelf and are not placed by guess.`,
      facts,
      disclosures: [],
      sections: [{ title: "Sources and licences", items: this.sourceItems() }],
      related: [],
      opens: [],
      keywords: item.label,
      swatch: "own-family",
    };
  }

  describe(key) {
    const item = this.get(key);
    if (!item) return null;
    return item.type === "p" ? this.describeProtein(item) : item.type === "s" ? this.describeShelf(item) : this.describeFamily(item);
  }

  /**
   * The marks the legend can show alone: those with a short list of values, each value with
   * how many proteins carry it. A mark that is only ever set counts those without it as "no".
   * A catalogue with one marker for each protein has them at rest. One in families has those
   * its file lists the proteins of (`highlights`): each is a set (`set: true`), counted from
   * that list, and a marker is lit for the proteins of the set it holds (highlightOf).
   */
  filterable() {
    if (this.kind !== "proteins") {
      return [...this.highlight].map(([name, values]) => {
        const mark = this.marks[name];
        const order = Array.isArray(mark.values) ? mark.values.map(String).filter((value) => values.has(value)) : [...values.keys()];
        return { id: name, label: mark.label || name, measured: Boolean(mark.measured), note: mark.note || null, source: mark.source || null, set: true, items: order.map((value) => ({ id: value, label: value === "true" ? "Yes" : upper(value), count: values.get(value).total })) };
      });
    }
    const out = [];
    for (const [name, mark] of Object.entries(this.marks)) {
      if (!Array.isArray(mark.values) || mark.values.length > 8) continue;
      const flag = mark.values.every((value) => typeof value === "boolean");
      const values = flag ? [true, false] : mark.values;
      const tally = new Map(values.map((value) => [String(value), 0]));
      for (const protein of this.proteins) {
        const value = String(protein.marks[name] ?? (flag ? false : ""));
        if (tally.has(value)) tally.set(value, tally.get(value) + 1);
      }
      const items = values.map((value) => ({ id: String(value), label: value === true ? "Yes" : value === false ? "No" : upper(String(value)), count: tally.get(String(value)) }));
      if (!items.some((item) => item.count)) continue;
      out.push({ id: name, label: mark.label || name, measured: Boolean(mark.measured), note: mark.note || null, source: mark.source || null, items });
    }
    return out;
  }

  /** How many proteins have their side known in each way. */
  byBasis() {
    const tally = Object.fromEntries(BASES.map((basis) => [basis, 0]));
    if (this.kind === "proteins") for (const protein of this.proteins) tally[protein.basis] += 1;
    else for (const sides of Object.values(this.data.by_basis || {})) for (const [basis, n] of Object.entries(sides)) tally[basis] = (tally[basis] || 0) + n;
    return tally;
  }

  /**
   * What holds a protein listed with a unit of Cells' law inventory, in a catalogue that
   * stands as families: the families that do (one with lines on several shelves counted
   * once), the gatherings of families of one, the groups of "no family" (counted once
   * likewise), and the markers at rest that are lit for any of them.
   */
  lawHolders() {
    const held = (items = []) => items.filter((item) => item.units.length);
    const once = (items) => new Set(held(items).map((item) => item.id)).size;
    return { families: once(this.families), lone: held(this.lone).length, parts: once(this.parts), markers: held(this.kind === "families" ? this.markers : []).length };
  }

  // ------------------------------------------------------------ the names of every protein (for the search)

  /**
   * Take in the names file of a large catalogue (schema/SPECIES_PROTEINS.md, "The names file"):
   * one row for each member, in the members' files' order, with how many each file holds.
   */
  addNames(file) {
    if (file?.format !== NAMES_FORMAT || !Array.isArray(file.names) || !Array.isArray(file.files) || !Array.isArray(file.counts)) throw new Error("it is not a file of names");
    if (file.counts.reduce((sum, n) => sum + n, 0) !== file.names.length) throw new Error("its counts do not add up to its names");
    const at = Object.fromEntries(file.columns.map((name, index) => [name, index]));
    // Each members' file's lines, by where their members begin in it: a name's row finds its line.
    const lines = new Map();
    for (const line of [...this.families, ...this.parts, ...this.lone]) {
      if (!line.file || !Array.isArray(line.at)) continue;
      if (!lines.has(line.file)) lines.set(line.file, []);
      lines.get(line.file).push(line);
    }
    for (const list of lines.values()) list.sort((a, b) => a.at[0] - b.at[0]);
    // Each row's file and its place there, from the files' order and counts.
    // Columns after the four are marks the catalogue says the search finds a member by (its other entries' names).
    const searched = file.columns.filter((name) => !["id", "gene", "label", "side"].includes(name));
    let index = 0, row = 0;
    this.names = file.names.map((line) => {
      while (row >= file.counts[index]) (index += 1), (row = 0);
      const more = searched.map((mark) => [mark, String(line[at[mark]] || "")]).filter(([, value]) => value);
      return { id: line[at.id], gene: line[at.gene] || "", label: line[at.label] || "", side: line[at.side] || null, file: file.files[index], row: row++, ...(more.length ? { more } : {}) };
    });
    this.namesLines = lines;
    for (const name of this.names) {
      name.own = `${name.gene} ${name.label} ${name.id}`.toLowerCase();
      name.text = name.more ? `${name.own} ${name.more.map(([, value]) => value).join(" ")}`.toLowerCase() : name.own;
    }
  }

  /** The line a named member stands on: the family, part or gathering of families of one whose members hold its row. */
  lineOfName(name) {
    const list = this.namesLines?.get(name.file) || [];
    let low = 0, high = list.length - 1;
    while (low <= high) {
      const middle = (low + high) >> 1, line = list[middle];
      if (name.row < line.at[0]) high = middle - 1;
      else if (name.row >= line.at[1]) low = middle + 1;
      else return line;
    }
    return null;
  }

  /**
   * What a search finds, in a few kinds: proteins by gene, name or identifier (each with the line
   * it stands on, and its shelf), the families' lines and the parts by name or accession, and the
   * shelves. A gene that is the whole query comes first, then names that begin with it.
   */
  search(query, { limit = 6 } = {}) {
    const q = String(query || "").trim().toLowerCase();
    if (q.length < 2) return null;
    const rank = (gene, text) => (gene.toLowerCase() === q ? 0 : gene.toLowerCase().startsWith(q) ? 1 : text.startsWith(q) ? 2 : 3);
    const proteins = [];
    if (this.kind === "proteins") {
      for (const item of this.proteins) {
        const text = `${item.gene || ""} ${item.label} ${item.id}`.toLowerCase();
        if (text.includes(q)) proteins.push({ rank: rank(item.gene || "", text), key: item.key, id: item.id, gene: item.gene || "", label: item.label, side: item.side, shelf: item.shelf ?? null, under: shelvesDistrict(this, item) });
      }
    } else if (this.names) {
      for (const name of this.names) {
        if (!name.text.includes(q)) continue;
        const line = this.lineOfName(name);
        // Found only by a mark the search reads (an entry of its gene that is not shown): the hit says by which, in the mark's own label.
        const by = !name.own.includes(q) && name.more ? name.more.find(([, value]) => value.toLowerCase().includes(q)) : null;
        const via = by ? { label: this.marks[by[0]]?.label || by[0], value: by[1] } : null;
        proteins.push({ rank: rank(name.gene, name.text) + (via ? 1 : 0), id: name.id, gene: name.gene, label: name.label || line?.label || name.id, line, side: name.side, shelf: line ? line.shelf ?? null : null, under: line ? (line.type === "l" ? "the only member of its family" : line.label) : "", ...(via ? { via } : {}) });
      }
    }
    proteins.sort((a, b) => a.rank - b.rank || (a.gene || a.label).localeCompare(b.gene || b.label));
    const families = this.kind === "families" ? [...this.families, ...this.parts].filter((line) => `${line.label} ${line.id}`.toLowerCase().includes(q)) : [];
    const shelves = this.several ? this.byShelf.filter((entry) => String(entry.label ?? "No place known").toLowerCase().includes(q)).map((entry) => this.shelfItems.get(entry.id)) : [];
    return { query: q, proteins: proteins.slice(0, limit), more: Math.max(0, proteins.length - limit), total: proteins.length, families: families.slice(0, limit), familiesMore: Math.max(0, families.length - limit), shelves, namesMissing: this.kind === "families" && !this.names };
  }

  /** A row of the list for a marker or a protein. A member named only after its family is told apart by its identifier. */
  listed(item) {
    const label = item.type === "p" && item.under && item.label === item.under.label ? `${item.label} · ${item.id}` : item.type === "p" ? item.label : `${item.label} · ${item.count.toLocaleString("en-US")}`;
    // With several shelves the same family is listed once for each shelf it stands on, each row
    // with that line's own key. The row does not name the shelf: the list's headings do (a
    // shelf's name among a row's words would make a search for "membrane" find every row).
    return { id: item.key, label, short: item.gene || null, keywords: [item.id, item.gene, item.under?.label].filter(Boolean).join(" "), swatch: item.units?.length ? "map-assigned" : item.type === "p" ? "own-plain" : "own-family" };
  }
}

/** The district a protein of a small catalogue stands in, by name. */
function shelvesDistrict(shelves, item) {
  return shelves.districtLabel(item);
}

function majority(sides = {}) {
  return SIDES.reduce((best, side) => ((sides[side] || 0) > (sides[best] || 0) ? side : best), "inside");
}

// ---------------------------------------------------------------- where each marker stands

const ORDER = (shelves) => {
  const at = new Map([...shelves.groups.keys()].map((id, index) => [id, index]));
  if (shelves.noGroup) at.set(shelves.noGroup.id, at.size);
  return at;
};

/**
 * Pack blocks left to right in rows no wider than `limit`. Each block has width and depth.
 * Returns the band's size and sets each block's x and z (its centre, in the band's own frame).
 */
export function packBand(blocks, limit, gap = 5, between = 9) {
  const lines = [];
  let line = { blocks: [], width: 0, depth: 0 };
  for (const block of blocks) {
    if (line.blocks.length && line.width + gap + block.width > limit) {
      lines.push(line);
      line = { blocks: [], width: 0, depth: 0 };
    }
    line.width += (line.blocks.length ? gap : 0) + block.width;
    line.depth = Math.max(line.depth, block.depth);
    line.blocks.push(block);
  }
  if (line.blocks.length) lines.push(line);
  const width = Math.max(0, ...lines.map((item) => item.width));
  const depth = lines.reduce((sum, item) => sum + item.depth, 0) + between * Math.max(0, lines.length - 1);
  let z = -depth / 2;
  for (const item of lines) {
    let x = -item.width / 2;
    for (const block of item.blocks) {
      block.x = x + block.width / 2;
      block.z = z + block.depth / 2; // blocks of one row share their back edge
      x += block.width + gap;
    }
    z += item.depth + between;
  }
  return { width, depth };
}

export const PITCH = 3.1; // between two protein markers
const BLOCK_PAD = 2.2;

/** A block of equal markers in a grid of `deep` rows. Items get dx, dz from the block's centre. */
function gridBlock(items, deep, pitch = PITCH) {
  deep = Math.max(1, Math.min(deep, items.length));
  const across = Math.ceil(items.length / deep);
  deep = Math.ceil(items.length / across);
  const places = items.map((item, index) => ({ item, dx: ((index % across) - (across - 1) / 2) * pitch, dz: (Math.floor(index / across) - (deep - 1) / 2) * pitch, radius: pitch * 0.34 }));
  return { places, width: across * pitch + 2 * BLOCK_PAD, depth: deep * pitch + 2 * BLOCK_PAD };
}

/** How large a family's marker is: it grows with its members, slowly, so the largest stay on the shelf. */
export const familyRadius = (members) => 0.6 + 0.9 * Math.cbrt(members);
const PUCK_GAP = 1.2;
const puckSize = (item) => 2 * familyRadius(item.count) + PUCK_GAP;

/**
 * A block of round markers of several sizes, the largest first, about `deep` from back to
 * front. They stand in rows as deep as the row's first marker; a smaller one stands behind
 * the one before it while there is room.
 */
function puckBlock(items, deep) {
  const sized = items.map((item) => ({ item, radius: familyRadius(item.count), size: puckSize(item) })).sort((a, b) => b.radius - a.radius || a.item.label.localeCompare(b.item.label));
  const area = sized.reduce((sum, place) => sum + place.size ** 2, 0);
  const limit = Math.max(sized[0].size, (area * 1.12) / Math.max(deep, sized[0].size));
  const lines = [];
  let line = null, column = null;
  for (const place of sized) {
    const size = place.size;
    if (column && column.height + size <= line.depth + 1e-9) {
      column.height += size;
      column.places.push(place);
      continue;
    }
    if (!line || line.width + size > limit + 1e-9) {
      line = { columns: [], width: 0, depth: size };
      lines.push(line);
    }
    column = { at: line.width + size / 2, height: size, places: [place] };
    line.columns.push(column);
    line.width += size;
  }
  const width = Math.max(...lines.map((item) => item.width)), depth = lines.reduce((sum, item) => sum + item.depth, 0);
  let z = -depth / 2;
  const places = [];
  for (const item of lines) {
    for (const stack of item.columns) {
      let at = z + (item.depth - stack.height) / 2;
      for (const place of stack.places) {
        places.push({ item: place.item, radius: place.radius, dx: stack.at - item.width / 2, dz: at + place.size / 2 });
        at += place.size;
      }
    }
    z += item.depth;
  }
  return { places, width: width + 2 * BLOCK_PAD, depth: depth + 2 * BLOCK_PAD };
}

// The three areas of one shelf, and the sides that stand in each.
const AREAS = [["plate", ["in", "outside"]], ["tray", ["inside"]], ["apart", ["not known"]]];

/** Of some markers, those on the given sides, by district: each district with its name, its count and its markers in their order. */
function districtsOf(shelves, markers, sides, order) {
  const byDistrict = new Map();
  for (const item of markers) {
    if (!sides.includes(item.side)) continue;
    const district = item.district ?? item.group;
    if (!byDistrict.has(district)) byDistrict.set(district, []);
    byDistrict.get(district).push(item);
  }
  return [...byDistrict.entries()]
    .sort((a, b) => (order.get(a[0]) ?? 99) - (order.get(b[0]) ?? 99))
    .map(([district, items]) => ({
      district,
      label: shelves.districtLabel(items[0]),
      count: items.reduce((sum, item) => sum + item.count, 0),
      // What spans the membrane first, then what stands on it; members of one assembly together.
      items: [...items].sort((a, b) => sides.indexOf(a.side) - sides.indexOf(b.side) || String(b.marks?.complex || "").localeCompare(String(a.marks?.complex || "")) || String(a.marks?.class || "").localeCompare(String(b.marks?.class || ""))),
    }));
}

/** One area's districts as blocks, packed no wider than `across`: { blocks, width, depth }. */
function bandOf(districts, across, families) {
  const largest = Math.max(0, ...districts.flatMap((district) => district.items.map((item) => (families ? puckSize(item) : 0))));
  const depths = families ? [1, 1.25, 1.5, 2, 2.5, 3, 4].map((times) => largest * times) : [1, 2, 3, 4, 5, 6, 7, 8, 9];
  let best = null;
  for (const deep of depths) {
    const blocks = districts.map(({ items, ...district }) => ({ ...(families ? puckBlock(items, deep) : gridBlock(items, deep)), ...district }));
    const size = packBand(blocks, Math.max(across, ...blocks.map((block) => block.width)));
    // The shallowest shelf that is no wider than asked; of equal ones, the narrowest. A district
    // that would stand much deeper than it is wide counts against a choice: its name would not fit it.
    const thin = blocks.reduce((sum, block) => sum + Math.max(0, block.depth - 1.25 * block.width), 0) / Math.max(1, blocks.length);
    const cost = size.depth + Math.max(0, size.width - across) * 4 + size.width * 0.02 + thin * 1.5;
    if (!best || cost < best.cost) best = { blocks, ...size, cost };
  }
  return best || { blocks: [], width: 0, depth: 0 };
}

/** One shelf's three areas at a width: their bands, and the shelf's size with what the drawing adds around each area and between two. */
function stackOf(areas, across, families, margin, step) {
  const bands = areas.map((area) => bandOf(area.districts, across, families));
  const used = bands.filter((item) => item.blocks.length);
  const width = Math.max(0, ...used.map((item) => item.width)) + 2 * margin;
  const depth = used.reduce((sum, item) => sum + item.depth + 2 * margin, 0) + step * Math.max(0, used.length - 1);
  return { bands, width, depth, across };
}

/**
 * The first of `widths` whose stack fits, found by halving the range: a wider stack is a
 * shallower one. The widest, if none fits. `make` builds the stack for a width, once.
 */
function narrowest(widths, make, fits) {
  const tried = new Map();
  const at = (index) => {
    if (!tried.has(index)) tried.set(index, make(widths[index]));
    return tried.get(index);
  };
  let low = 0, high = widths.length - 1;
  while (low < high) {
    const middle = (low + high) >> 1;
    if (fits(at(middle))) high = middle;
    else low = middle + 1;
  }
  return at(low);
}

/**
 * Where everything stands at rest. Three areas, stacked like shelves:
 *   plate   the membrane: what spans it stands in it, what is outside stands on it;
 *   tray    below it, inside the cell;
 *   apart   to the front, set apart: what has no known side.
 * Each area holds blocks, one for a district; each block holds places { item, dx, dz, radius }.
 * `shape` is how deep the whole stack may be for its width: about 1 for a wide screen, which
 * sees it from the front and above, and more for a tall one. The stack is the narrowest that
 * keeps to it, and the districts of one shelf are as deep as lets that shelf be shallowest.
 * `margin` and `step` are what the drawing adds around each shelf and between two.
 *
 * This is the layout of a species with one shelf. For several shelves, see `layoutStack`,
 * which gives each shelf these three areas and, for one shelf, these same places.
 */
export function layoutShelves(shelves, { shape = 1.15, margin = 6, step = 12, limit = null } = {}) {
  const order = ORDER(shelves);
  const families = shelves.kind === "families";
  const areas = AREAS.map(([id, sides]) => ({ id, sides, districts: districtsOf(shelves, shelves.markers, sides, order) }));
  // The narrowest stack that is no deeper than its shape allows; the widest tried, if none is.
  const widths = limit ? [limit] : Array.from({ length: 27 }, (_, index) => 60 + index * 10);
  const chosen = narrowest(widths, (across) => stackOf(areas, across, families, margin, step), (stack) => stack.depth <= stack.width * shape);
  const out = { limit: chosen.across, width: chosen.width, depth: chosen.depth };
  areas.forEach(({ id, sides }, index) => (out[id] = { id, sides, blocks: chosen.bands[index].blocks, width: chosen.bands[index].width, depth: chosen.bands[index].depth }));
  return out;
}

/**
 * Where everything stands at rest where a species may have several shelves: a stack of
 * shelves in the file's order, each with the three areas above (its membrane; the glass
 * below it; and, set apart beside it, the proteins of that shelf whose side is not known),
 * and in front of them all the page's one set-apart area, for what is on no shelf.
 *
 *   - Every membrane and every glass is one width (`common`), so they read as one stack.
 *   - Each shelf can be framed alone: the width is the narrowest at which every shelf, with
 *     its own three areas, is no deeper than `shape` allows for its width. It is the largest
 *     shelf that decides, not the whole stack, which is far deeper than any screen.
 *   - Each shelf comes in its own frame, as `layoutShelves` gives one shelf: `plate`, `tray`
 *     and `apart` hold blocks whose places are told from the middle of their area. `areas`
 *     lists the areas that hold anything, with the middle of each (`z`, from the middle of
 *     the shelf's first area) and its size with the margin around it (`width`, `depth`).
 *     `back` and `front` are the shelf's edges in that frame, `width` and `depth` its size.
 *   - A shelf's place in the stack is apart from all that: `z`, where the origin of its
 *     frame stands, each shelf further to the front than the one before with `between`
 *     left free. The drawing moves a shelf there, and lower or higher as it likes.
 *   - `apart` is the page's one set-apart area (null where every protein has a shelf): its
 *     blocks, its size with the margin (`size`) and its place in the stack (`z`).
 *
 * For a species with one shelf, every marker stands exactly where `layoutShelves` puts it,
 * and the stack's width, depth and limit are that layout's.
 */
export function layoutStack(shelves, { shape = 1.15, margin = 6, step = 12, between = 2 * step, limit = null } = {}) {
  const order = ORDER(shelves);
  const families = shelves.kind === "families";
  // What stands on each shelf; with one shelf, everything stands on it.
  const groups = shelves.several ? shelves.shelves.map((shelf) => ({ shelf, markers: shelves.markers.filter((item) => item.shelf === shelf.id) })) : [{ shelf: shelves.shelf, markers: shelves.markers }];
  for (const group of groups) group.areas = AREAS.map(([id, sides]) => ({ id, sides, districts: districtsOf(shelves, group.markers, sides, order) }));
  const loose = shelves.several ? districtsOf(shelves, shelves.markers.filter((item) => item.shelf === null || item.shelf === undefined), SIDES, order) : [];
  // One width for all: the membranes and the glasses are as wide as the widest of them; a
  // shelf's own set-apart area keeps its own width, and may reach past them. `over` is by
  // how much the shelf that keeps to the shape least is too deep for its width.
  const made = new Map();
  const whole = (across) => {
    if (made.has(across)) return made.get(across);
    const each = groups.map((group) => stackOf(group.areas, across, families, margin, step));
    const common = Math.max(0, ...each.flatMap((one) => one.bands.slice(0, 2).filter((band) => band.blocks.length).map((band) => band.width)));
    for (const one of each) one.width = Math.max(common, one.bands[2].blocks.length ? one.bands[2].width : 0) + 2 * margin;
    const stack = { each, common, across, over: Math.max(...each.map((one) => one.depth - one.width * shape)) };
    made.set(across, stack);
    return stack;
  };
  // With one shelf, the widths `layoutShelves` tries; with several, further: a shelf must fit alone.
  const widths = limit ? [limit] : Array.from({ length: shelves.several ? 59 : 27 }, (_, index) => 60 + index * 10);
  let chosen = narrowest(widths, whole, (stack) => stack.over <= 0);
  if (shelves.several && chosen.over > 0) {
    // No width lets every shelf keep to the shape: one of them is as shallow as its few
    // markers let it be, and no wider for a wider stack. The narrowest that does as well
    // as the widest, so that such a shelf does not stretch all the others.
    const least = chosen.over;
    chosen = narrowest(widths, whole, (stack) => stack.over <= least + 1e-9);
  }
  const out = { limit: chosen.across, common: chosen.common, width: 0, depth: 0, shelves: [], apart: null };
  let front = null;
  groups.forEach((group, index) => {
    const one = chosen.each[index];
    if (!one.bands.some((band) => band.blocks.length)) return; // a shelf with nothing on it takes no place
    const shelf = { id: group.shelf.id, shelf: group.shelf, index, areas: [], width: one.width, depth: one.depth, proteins: group.markers.reduce((sum, item) => sum + item.count, 0), markers: group.markers.length };
    let edge = null;
    group.areas.forEach(({ id, sides }, at) => {
      const band = one.bands[at];
      shelf[id] = { id, sides, blocks: band.blocks, width: band.width, depth: band.depth };
      if (!band.blocks.length) return;
      // As the drawing has it: the first area's middle is the frame's origin; each next one stands a step in front.
      const size = { width: (id === "apart" ? band.width : chosen.common) + 2 * margin, depth: band.depth + 2 * margin };
      const z = edge === null ? 0 : edge + step + size.depth / 2;
      edge = z + size.depth / 2;
      shelf.areas.push({ id, z, ...size });
    });
    shelf.back = -shelf.areas[0].depth / 2;
    shelf.front = edge;
    shelf.z = front === null ? 0 : front + between - shelf.back;
    front = shelf.z + shelf.front;
    out.shelves.push(shelf);
  });
  if (loose.length) {
    const band = bandOf(loose, chosen.across, families);
    const size = { width: band.width + 2 * margin, depth: band.depth + 2 * margin };
    const z = front === null ? 0 : front + between + size.depth / 2;
    front = z + size.depth / 2;
    out.apart = { id: "apart", sides: ["not known"], blocks: band.blocks, width: band.width, depth: band.depth, size, z, proteins: loose.reduce((sum, district) => sum + district.count, 0) };
  }
  out.width = Math.max(0, ...out.shelves.map((shelf) => shelf.width), out.apart ? out.apart.size.width : 0);
  // From its first shelf's back edge to the front edge of what stands last: the shelves, what is between them, and the set-apart area.
  const standing = [...out.shelves.map((shelf) => shelf.depth), ...(out.apart ? [out.apart.size.depth] : [])];
  out.depth = standing.reduce((sum, depth) => sum + depth, 0) + between * Math.max(0, standing.length - 1);
  return out;
}

/**
 * Where each shelf of a stack stands: one staircase in the file's order, each shelf lower
 * than the one before it and further to the front; or, for a wide screen, the same shelves
 * as several staircases side by side, so that the whole fills the screen instead of
 * running many times deeper than wide. `stack` is what `layoutStack` gives.
 *
 *   columns   how many staircases (no more than there are shelves); consecutive shelves
 *             share one, cut so that the deepest staircase is as shallow as can be
 *   between   the room between two shelves of a staircase, from one's front to the next's back
 *   gap       the room between two staircases
 *   drop      how much lower each shelf of a staircase stands than the one before it
 *
 * Returns { columns, shelves: [{ id, column, row, x, y, z }], apart, width, depth, drop }:
 * for each shelf where the origin of its own frame stands; `apart` likewise for the page's
 * one set-apart area (its middle), in front of every shelf and lower than all; and the size
 * of the whole on the ground. With one staircase the back of the first shelf's first area is
 * where `layoutStack` has it, so a species with one shelf stands where it always has.
 */
export function arrangeStack(stack, { columns = 1, between = 24, gap = 30, drop = 28 } = {}) {
  const shelves = stack.shelves;
  const count = Math.max(1, Math.min(Math.floor(columns) || 1, shelves.length || 1));
  const deep = (from, to) => shelves.slice(from, to).reduce((sum, shelf) => sum + shelf.depth, 0) + between * Math.max(0, to - from - 1);
  // The cuts between staircases: every way of cutting is tried (there are few shelves), and the one whose deepest staircase is shallowest is kept.
  let best = null;
  const tryCuts = (cuts) => {
    if (cuts.length === count - 1) {
      const edges = [0, ...cuts, shelves.length];
      const deepest = Math.max(...edges.slice(1).map((to, index) => deep(edges[index], to)));
      if (!best || deepest < best.deepest - 1e-9) best = { edges, deepest };
      return;
    }
    for (let cut = (cuts.at(-1) ?? 0) + 1; cut <= shelves.length - (count - 1 - cuts.length); cut++) tryCuts([...cuts, cut]);
  };
  tryCuts([]);
  const edges = best ? best.edges : [0, shelves.length];
  const pitch = stack.width + gap;
  const back = shelves.length ? shelves[0].back : 0;
  const out = { columns: count, shelves: [], apart: null, width: count * stack.width + (count - 1) * gap, depth: 0, drop };
  let front = back, rows = 0;
  for (let column = 0; column < count; column++) {
    let edge = back;
    shelves.slice(edges[column], edges[column + 1]).forEach((shelf, row) => {
      const z = edge - shelf.back;
      out.shelves.push({ id: shelf.id, column, row, x: (column - (count - 1) / 2) * pitch, y: row ? -row * drop : 0, z });
      edge = z + shelf.front + between;
      front = Math.max(front, z + shelf.front);
      rows = Math.max(rows, row + 1);
    });
  }
  if (stack.apart) {
    const z = (shelves.length ? front + between : 0) + stack.apart.size.depth / 2;
    out.apart = { x: 0, y: rows ? -rows * drop : 0, z };
    out.width = Math.max(out.width, stack.apart.size.width);
    front = z + stack.apart.size.depth / 2;
  }
  out.depth = front - (shelves.length ? back : -(stack.apart ? stack.apart.size.depth / 2 : 0));
  return out;
}

/**
 * Where the members of an open family stand: on a small set of shelves of their own, round,
 * in rings from the middle. First those that span the membrane and those outside it (a round
 * piece of membrane), then those inside the cell (glass around it, a step lower), then those
 * with no known side (beyond the rim, set apart). Members that follow one another stand side
 * by side, so the families of a gathering stay together. A member with `wide` (one drawn as
 * a unit) takes a place twice as wide, and those stand first within their side.
 * Returns { places: [{ item, dx, dz, zone, size }], plate, tray, reach }: the radius of the
 * membrane piece and of the glass (0 where nothing stands on one), and of everything.
 */
export function layoutDish(members, pitch = PITCH, wide = () => false) {
  const rank = { in: 0, outside: 1, inside: 2, "not known": 3 };
  const zoneOf = (side) => (side === "inside" ? "tray" : side === "not known" ? "apart" : "plate");
  const sized = members.map((item, index) => ({ item, index, size: wide(item) ? 2 : 1, zone: zoneOf(item.side) }));
  sized.sort((a, b) => rank[a.item.side] - rank[b.item.side] || b.size - a.size || a.index - b.index);
  const places = [];
  const radius = { plate: 0, tray: 0, apart: 0 };
  let edge = 0, ring = 0;
  for (const zone of ["plate", "tray", "apart"]) {
    const items = sized.filter((entry) => entry.zone === zone);
    if (!items.length) continue;
    // A step between two zones: past the rim of the one before.
    if (edge > 0) edge += pitch * (zone === "apart" ? 1.5 : 1.1);
    let index = 0;
    while (index < items.length) {
      const size = items[index].size, thick = pitch * size;
      let run = 1;
      while (index + run < items.length && items[index + run].size === size) run++;
      const middle = edge + thick / 2;
      const fits = Math.max(1, Math.floor((2 * Math.PI * middle) / thick));
      const take = Math.min(fits, run);
      // One alone in the very middle stands on the middle itself.
      const at = edge === 0 && take === 1 && run === 1 ? 0 : middle;
      const phase = ring * 2.39996;
      for (let k = 0; k < take; k++) {
        const angle = phase + (k / Math.max(take, Math.min(fits, 6))) * 2 * Math.PI;
        places.push({ item: items[index + k].item, dx: Math.cos(angle) * at, dz: Math.sin(angle) * at, zone, size });
      }
      index += take;
      edge = at === 0 ? thick / 2 : edge + thick;
      ring += 1;
    }
    radius[zone] = edge + pitch * 0.55;
    edge = radius[zone];
  }
  return { places, plate: radius.plate, tray: radius.tray, reach: Math.max(pitch * 1.6, edge) };
}
