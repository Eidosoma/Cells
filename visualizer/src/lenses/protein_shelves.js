// A species' own proteins, for the atlas's shelves (schema/SPECIES_PROTEINS.md): the file as
// the page reads it, where each marker stands, and the words said of a protein or a family.
// Nothing here draws; src/lenses/shelves_view.js does. Everything here runs without a browser.
//
// One format for every species: a shelf is a membrane, and a protein sits outside it, in it
// or inside it. A protein whose side is not known is set apart, never placed by guess.
//   a small catalogue   one marker for each protein (Syn3A, M. pneumoniae);
//   a large catalogue   every protein still shown, as families that open (the planarian).

export const SHELVES_FORMAT = "cells.visualizer.species_proteins@1";
export const MEMBERS_FORMAT = "cells.visualizer.species_protein_members@1";
export const SIDES = ["outside", "in", "inside", "not known"];
export const BASES = ["stated", "predicted", "by function", "none"];

// A family of this many proteins or more has a marker of its own; smaller ones are gathered,
// by district and side, into one marker that opens to them. The same for the parts of
// "no family", from this many.
export const OWN_FAMILY = 5;
export const OWN_PART = 10;

const lower = (text) => text.charAt(0).toLowerCase() + text.slice(1);
const upper = (text) => text.charAt(0).toUpperCase() + text.slice(1);
const count = (n, one, many = `${one}s`) => `${n.toLocaleString("en-US")} ${n === 1 ? one : many}`;
export const plural = count;

/** The id of a part the shelves make themselves: "own:<species>:<type>:<id>". */
export const keyOf = (species, type, id) => `own:${species}:${type}:${id}`;
export function parseKey(key) {
  const parts = /^own:([^:]+):([a-z]):(.*)$/.exec(key || "");
  return parts ? { species: parts[1], type: parts[2], id: parts[3] } : null;
}

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
 */
export async function loadBeside(path, { root = globalThis.document, fetcher = globalThis.fetch } = {}) {
  const inline = root?.querySelector?.(`script[type="application/json"][data-file="${path}"]`);
  if (inline) return JSON.parse(inline.textContent);
  if (typeof fetcher !== "function") throw new Error("this page cannot fetch it");
  let response;
  try {
    response = await fetcher(path);
  } catch {
    throw new Error(`${path} could not be fetched`);
  }
  if (!response.ok) throw new Error(`${path} answered ${response.status}`);
  return response.json();
}

/** The first problems of a shelves file against its contract; an empty list if it holds. */
export function validateShelves(data) {
  const problems = [];
  if (data?.format !== SHELVES_FORMAT) return [`its format is ${data?.format}, not ${SHELVES_FORMAT}`];
  if (!data.species) problems.push("it names no species");
  if (!Array.isArray(data.shelves) || !data.shelves.length) problems.push("it has no shelf");
  if (!Array.isArray(data.proteins) && !Array.isArray(data.families)) problems.push("it holds neither proteins nor families");
  const groups = new Set((data.groups || []).map((group) => group.id));
  if (Array.isArray(data.proteins)) {
    const at = Object.fromEntries((data.columns || []).map((name, index) => [name, index]));
    for (const name of ["id", "label", "shelf", "side", "basis", "group"]) if (!(name in at)) problems.push(`its columns lack ${name}`);
    if (!problems.length) {
      for (const row of data.proteins) {
        if (!SIDES.includes(row[at.side])) problems.push(`${row[at.id]}: the side ${row[at.side]}`);
        else if (!BASES.includes(row[at.basis])) problems.push(`${row[at.id]}: the basis ${row[at.basis]}`);
        else if (!groups.has(row[at.group])) problems.push(`${row[at.id]}: the group ${row[at.group]} is not declared`);
        if (problems.length > 4) break;
      }
    }
  }
  if (Array.isArray(data.families)) {
    const at = Object.fromEntries((data.family_columns || []).map((name, index) => [name, index]));
    for (const name of ["id", "label", "side", "group", "count", "file", "at"]) if (!(name in at)) problems.push(`its family columns lack ${name}`);
    if (!data.no_family) problems.push("it does not say where the proteins with no family are");
  }
  return problems;
}

const rows = (columns, lines) => lines.map((line) => Object.fromEntries(columns.map((name, index) => [name, line[index]])));

/**
 * One species' own proteins, as read from its file.
 *   kind      "proteins" (one marker each) or "families" (families that open)
 *   markers   what stands on the shelves at rest
 */
export class Shelves {
  constructor(data, { label = null, organism = null, links = null, units = null } = {}) {
    const problems = validateShelves(data);
    if (problems.length) throw new Error(`the file of proteins does not follow its format: ${problems.slice(0, 3).join("; ")}`);
    this.data = data;
    this.id = data.species;
    this.label = label || data.species;
    this.organism = organism;
    this.links = links || {};
    this.units = units || new Map(); // inventory unit id -> the scene's part for it
    this.kind = Array.isArray(data.proteins) ? "proteins" : "families";
    this.shelves = data.shelves;
    this.shelf = data.shelves[0];
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
    this.loaded = new Map(); // member file -> its members, once fetched
    if (this.kind === "proteins") {
      this.proteins = rows(data.columns, data.proteins).map((protein) => this.protein(protein, null));
      this.total = this.proteins.length;
      this.markers = this.proteins;
    } else this.readFamilies();
    this.counts = Object.fromEntries(SIDES.map((side) => [side, data.counts?.[side] ?? this.tally(side)]));
  }

  tally(side) {
    if (this.kind === "proteins") return this.proteins.filter((protein) => protein.side === side).length;
    return [...this.families, ...this.parts].reduce((sum, family) => sum + (family.sides?.[side] || 0), 0);
  }

  /** A protein of the catalogue, or a member of a family. */
  protein(line, under) {
    const unit = Array.isArray(line.unit) ? line.unit : line.unit ? [line.unit] : [];
    const protein = { ...line, type: "p", key: keyOf(this.id, "p", line.id), marks: line.marks || {}, units: unit, under, count: 1 };
    protein.label = line.label || under?.label || line.id;
    protein.group = line.group ?? under?.group;
    protein.shelf = line.shelf ?? under?.shelf ?? this.shelf.id;
    this.byKey.set(protein.key, protein);
    return protein;
  }

  readFamilies() {
    const data = this.data;
    const family = (line, type) => {
      const item = { ...line, type, key: keyOf(this.id, type, line.id), units: line.units || [], where: line.where || [], sides: line.sides || {}, shelf: line.shelf || this.shelf.id };
      this.byKey.set(item.key, item);
      return item;
    };
    this.families = rows(data.family_columns, data.families).map((line) => family(line, "f"));
    const none = data.no_family || {};
    this.parts = rows(none.part_columns || [], none.parts || []).map((line) => family(line, "g"));
    // "No family" given whole, with no parts: it opens like one family.
    if (!this.parts.length && none.count) this.parts = [family({ id: "none", label: none.label || "No family assigned", side: majority(none.sides), group: null, count: none.count, sides: none.sides || {}, file: none.file, at: none.at, kind: "no family" }, "g")];
    this.noFamily = { label: none.label || "No family assigned", count: none.count ?? this.parts.reduce((sum, part) => sum + part.count, 0), from: none.parts_from || null };
    this.total = this.families.reduce((sum, item) => sum + item.count, 0) + this.noFamily.count;
    // The parts of "no family" stand in a district of their own, after the others.
    this.noGroup = { id: "no-family", label: this.noFamily.label, from: this.noFamily.from };
    for (const part of this.parts) part.district = this.noGroup.id;
    for (const item of this.families) item.district = item.group;
    // The smaller ones, gathered: one marker for a district and a side, which opens to them.
    const gather = (items, limit, type, words) => {
      const own = [], small = new Map();
      for (const item of items) {
        // A part that is not a superfamily (the proteins with a domain only, or no signature) stands alone.
        if (item.count >= limit || (type === "n" && item.kind && item.kind !== "superfamily")) own.push(item);
        else {
          const id = `${item.district}|${item.side}`;
          if (!small.has(id)) small.set(id, { type, key: keyOf(this.id, type, id), id, district: item.district, group: item.group, side: item.side, shelf: item.shelf, holds: [], count: 0, sides: {}, units: [], where: [] });
          const more = small.get(id);
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
    this.markers = [...gather(this.families, OWN_FAMILY, "m", ["family", "families"]), ...gather(this.parts, OWN_PART, "n", ["group", "groups"])];
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
    const from = this.kind === "proteins" ? this.proteins : [...this.families, ...this.parts];
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

  /** The names of the four sides for this species' shelf: short for the picture, long for the page. */
  sideWords() {
    const shelf = this.shelf;
    const short = (text) => String(text).split(":")[0];
    const one = /not told apart|membranes/i.test(shelf.label) ? "a membrane" : `the ${lower(shelf.label)}`;
    return {
      outside: { short: short(shelf.outside), long: shelf.outside, swatch: "own-outside" },
      in: { short: `In ${one}`, long: `Spans ${one}`, swatch: "own-in" },
      inside: { short: short(shelf.inside), long: shelf.inside, swatch: "own-inside" },
      "not known": { short: "Side not known", long: "No source states the side and nothing predicts it: set apart, not placed by guess", swatch: "own-unknown" },
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

  where(side) {
    const words = this.sideWords()[side];
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
   */
  markFacts(item) {
    const facts = [];
    for (const [name, value] of Object.entries(item.marks || {})) {
      const mark = this.marks[name];
      if (!mark || value === null || value === undefined) continue;
      // "No" is said only of a mark that can be either; a mark that is only ever set is left out when it is not.
      if (value === false && !(Array.isArray(mark.values) && mark.values.includes(false))) continue;
      const said = value === true ? "yes" : value === false ? "no" : Array.isArray(value) ? value.join(", ") : typeof value === "number" ? value.toLocaleString("en-US") : String(value);
      facts.push([mark.label || name, mark.measured ? `${said} (measured)` : said]);
    }
    return facts;
  }

  /** Everything the panel says of one protein. */
  describeProtein(protein) {
    const words = this.sideWords()[protein.side], basis = this.basisWords(protein.basis);
    const modelled = protein.units.length > 0;
    const where = this.where(protein.side);
    const chips = [
      modelled
        ? { label: "Would make a machine Cells has a law for", swatch: "map-assigned", title: "The species' atlas lists it among the gene products that would make a unit of the law inventory. The law is the unit's: the engine does not model this protein." }
        : { label: "No law in Cells", swatch: "own-plain", title: "Cells has no law for this protein. It is one of the species' own proteins, drawn as a plain marker." },
      { label: words.short, swatch: words.swatch, title: words.long },
      { label: basis.label, title: basis.sentence },
    ];
    const under = protein.under;
    const facts = [["Identifier", protein.id]];
    if (protein.gene) facts.push(["Gene", protein.gene]);
    if (protein.length) facts.push(["Length", `${Number(protein.length).toLocaleString("en-US")} amino acids`]);
    if (under) facts.push([under.type === "g" ? "Filed under" : "Family", `${under.label}${/^IPR\d/.test(under.id) ? ` (${under.id})` : ""}`]);
    if (protein.group || under) facts.push(["District", this.districtPath(under || protein)]);
    facts.push(...this.markFacts(protein));
    const notes = Object.entries(protein.marks || {}).map(([name]) => this.marks[name]).filter((mark) => mark?.note).map((mark) => `${mark.label}: ${mark.note}${mark.source ? ` Source: ${mark.source}.` : ""}`);
    const links = this.linksFor(protein);
    return {
      id: protein.key,
      kind: "protein",
      label: protein.label,
      eyebrow: `${this.label} protein`,
      chips,
      plain: where ? `${this.predicted ? "A predicted protein. It" : "It"} ${where}. ${basis.sentence}` : `${this.predicted ? "A predicted protein. Its" : "Its"} side of the membrane is not known. ${basis.sentence}`,
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
      related: modelled ? [{ title: "Drawn in the atlas as", ids: protein.units.map((unit) => this.units.get(unit)).filter(Boolean) }] : [],
      opens: under ? [{ title: under.type === "g" ? "Filed under" : "Its family", items: [{ id: under.within?.key && !under.members ? under.within.key : under.key, label: under.label, swatch: under.units.length ? "map-assigned" : "own-family" }] }] : [],
      keywords: [protein.id, protein.gene, under?.label].filter(Boolean).join(" "),
      swatch: modelled ? "map-assigned" : "own-plain",
    };
  }

  /** Everything the panel says of a family, a part of "no family", or a gathering of small ones. */
  describeFamily(item) {
    const sides = this.sideWords();
    const gathered = Boolean(item.holds);
    const part = item.type === "g" || item.type === "n";
    const spread = SIDES.filter((side) => item.sides?.[side]).map((side) => `${count(item.sides[side], "protein")} ${side === "not known" ? "with no side known" : side === "in" ? lower(sides.in.long).replace(/^spans/, "spanning") : lower(sides[side].short)}`);
    const members = this.membersOf(item);
    const modelled = item.units.length > 0;
    const what = gathered
      ? `${item.label} of ${this.districtLabel(item)}, gathered so that they do not swamp the shelf: ${count(item.count, "protein")} in all. Opening it shows every one of them.`
      : part
        ? `${count(item.count, "protein")} with no family signature, filed here ${item.kind === "superfamily" ? "by the superfamily they share, a wider grouping than a family" : item.kind === "no signature" ? "because they carry no signature of any kind" : "because they carry only a domain, a repeat or a site signature"}. This is not a family.`
        : `A family of ${count(item.count, "protein")}. Opening it shows every member.`;
    const facts = [];
    if (/^IPR\d/.test(item.id)) facts.push(["InterPro entry", item.id]);
    facts.push(["Proteins", item.count.toLocaleString("en-US")]);
    if (gathered) facts.push([part ? "Groups" : "Families", item.holds.length.toLocaleString("en-US")]);
    facts.push(["District", this.districtPath(item)]);
    if (spread.length) facts.push(["Where its members sit", spread.join("; ")]);
    if (item.where?.length) facts.push(["Named place", `${item.where.join(", ")} (an annotation carried by signatures, not a prediction for these proteins)`]);
    const links = this.linksFor(item);
    const listed = (members || []).slice(0, 400).map((member) => ({ id: member.key, label: member.label === item.label ? member.id : `${member.label} · ${member.id}`, swatch: member.units.length ? "map-assigned" : "own-plain" }));
    const held = gathered ? item.holds.slice(0, 400).map((family) => ({ id: family.key, label: `${family.label} · ${family.count}`, swatch: family.units.length ? "map-assigned" : "own-family" })) : [];
    return {
      id: item.key,
      kind: "family",
      label: item.label,
      eyebrow: gathered ? `${this.label} proteins` : part ? `${this.label} proteins with no family` : `${this.label} protein family`,
      chips: [
        modelled ? { label: "Holds parts of a machine Cells has a law for", swatch: "map-assigned", title: "Some of its members are candidate products of a unit of the law inventory. The law is the unit's: the engine does not model these proteins." } : { label: "No law in Cells", swatch: "own-family", title: "Cells has no law for these proteins." },
        { label: `Most ${lower(sides[item.side].short)}`, swatch: sides[item.side].swatch, title: "A family stands on the side where most of its members sit; each member keeps its own." },
      ],
      plain: `${what} ${this.basisWords("predicted").sentence.replace(/^That is/, "Each member's side is")}`,
      facts,
      disclosures: this.notes.predicted ? [{ title: "How a side is predicted", lines: [this.notes.predicted] }] : [],
      sections: [
        links.length ? { title: "Look it up", items: [{ label: item.id, links }] } : null,
        { title: "Sources and licences", items: this.sourceItems() },
      ].filter(Boolean),
      related: modelled ? [{ title: "Holds candidate products of", ids: item.units.map((unit) => this.units.get(unit)).filter(Boolean) }] : [],
      opens: [
        held.length ? { title: part ? "Its groups" : "Its families", items: held, more: item.holds.length - held.length, count: item.holds.length } : null,
        members ? { title: "Its proteins", items: listed, more: members.length - listed.length, count: members.length } : null,
      ].filter(Boolean),
      keywords: [item.id, ...(item.holds || []).map((family) => family.label)].join(" "),
      swatch: modelled ? "map-assigned" : "own-family",
    };
  }

  describe(key) {
    const item = this.get(key);
    if (!item) return null;
    return item.type === "p" ? this.describeProtein(item) : this.describeFamily(item);
  }

  /**
   * The marks the legend can show alone: those with a short list of values, each value with
   * how many proteins carry it. A mark that is only ever set counts those without it as "no".
   * Only a catalogue with one marker for each protein has them at rest.
   */
  filterable() {
    if (this.kind !== "proteins") return [];
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

  /** A row of the list for a marker or a protein. A member named only after its family is told apart by its identifier. */
  listed(item) {
    const label = item.type === "p" && item.under && item.label === item.under.label ? `${item.label} · ${item.id}` : item.type === "p" ? item.label : `${item.label} · ${item.count.toLocaleString("en-US")}`;
    return { id: item.key, label, short: item.gene || null, keywords: [item.id, item.gene, item.under?.label].filter(Boolean).join(" "), swatch: item.units?.length ? "map-assigned" : item.type === "p" ? "own-plain" : "own-family" };
  }
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
 */
export function layoutShelves(shelves, { shape = 1.15, margin = 6, step = 12, limit = null } = {}) {
  const order = ORDER(shelves);
  const families = shelves.kind === "families";
  const gathered = (sides) => {
    const byDistrict = new Map();
    for (const item of shelves.markers) {
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
  };
  const areas = [["plate", ["in", "outside"]], ["tray", ["inside"]], ["apart", ["not known"]]].map(([id, sides]) => ({ id, sides, districts: gathered(sides) }));
  const band = ({ districts }, across) => {
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
  };
  const stack = (across) => {
    const bands = areas.map((area) => band(area, across));
    const used = bands.filter((item) => item.blocks.length);
    const width = Math.max(0, ...used.map((item) => item.width)) + 2 * margin;
    const depth = used.reduce((sum, item) => sum + item.depth + 2 * margin, 0) + step * Math.max(0, used.length - 1);
    return { bands, width, depth, across };
  };
  // The narrowest stack that is no deeper than its shape allows; the widest tried, if none is.
  // A wider stack is a shallower one, so the width is found by halving the range of widths.
  const widths = limit ? [limit] : Array.from({ length: 27 }, (_, index) => 60 + index * 10);
  const tried = new Map();
  const at = (index) => {
    if (!tried.has(index)) tried.set(index, stack(widths[index]));
    return tried.get(index);
  };
  const fits = (index) => at(index).depth <= at(index).width * shape;
  let low = 0, high = widths.length - 1;
  while (low < high) {
    const middle = (low + high) >> 1;
    if (fits(middle)) high = middle;
    else low = middle + 1;
  }
  const chosen = at(low);
  const out = { limit: chosen.across, width: chosen.width, depth: chosen.depth };
  areas.forEach(({ id, sides }, index) => (out[id] = { id, sides, blocks: chosen.bands[index].blocks, width: chosen.bands[index].width, depth: chosen.bands[index].depth }));
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
