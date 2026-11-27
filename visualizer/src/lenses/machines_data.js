// The Machines catalogue as the page reads it (schema/MACHINE_CATALOGUE.md): the generated
// catalogue (data/catalogue/catalogue.json, carried in the scene as `catalogue`) and, beside it,
// the membrane units of the law inventory, read from the scene's protein units as the
// Protein atlas reads them. Nothing here draws; the view (machines.js), its card and the text
// page all read the catalogue through this one class.

import { loadBeside } from "./protein_shelves.js";

export const CATALOGUE_FORMAT = "cells.visualizer.machine_catalogue@1";
export const BENCH_FORMAT = "cells.visualizer.machine_bench@1";
/** A machine's id on the page: `machine:<kind>`, the same id its closer view in the Cell view uses (one machine, one identity). */
export const PREFIX = "machine:";
export const pageId = (kind) => `${PREFIX}${kind}`;
export const kindOf = (id) => (typeof id === "string" && id.startsWith(PREFIX) ? id.slice(PREFIX.length).split(":")[0] : null);
/** An organelle's id on the page: `organelle:<kind>` (schema/MACHINE_CATALOGUE.md, "Organelles"). An organelle is no machine: it stands on the shelf. */
export const ORGANELLE = "organelle:";
export const organelleKind = (id) => (typeof id === "string" && id.startsWith(ORGANELLE) ? id.slice(ORGANELLE.length) : null);
/** The dossier's word for a machine that only its family route names (schema/MACHINE_DOSSIERS.md): candidates, not parts. */
export const FAMILY = "family signature";
/** Whether a machine of a bench is named only by its dossier's family route: a machine its species' records do not name. */
export const byFamily = (item) => item?.entry?.named?.by === FAMILY;
/** The group the units of the law inventory that are protein assemblies stand in (the overlay's groups name it). */
export const IONS = "ions";
/** A unit of the law inventory is a machine of a species where its atlas found its family there, or built from another. */
const HAS_IT = new Set(["found", "different family"]);

export class Catalogue {
  constructor(raw, scene = null) {
    this.raw = raw || { groups: [], kinds: [], entries: [], sources: {}, records: {} };
    this.scene = scene;
    this.groups = this.raw.groups || [];
    this.groupById = new Map(this.groups.map((group) => [group.id, group]));
    this.kinds = new Map((this.raw.kinds || []).map((kind) => [kind.id, kind]));
    this.units = (scene?.entities || []).filter((entity) => entity.group === "proteins" && entity.kind === "unit");
    this.reference = (scene?.proteins?.atlases || []).find((atlas) => atlas.reference)?.id || null;
    this.leftOut = new Map(Object.entries(this.raw.units_left_out?.units || {}));
    this.unitSizes = this.raw.unit_sizes || null;
    this.cache = new Map();
    // Each species' bench: carried whole (a catalogue with its entries: the tests, an older page), or read when it is shown
    // from its file beside the page (`benches`: schema/MACHINE_CATALOGUE.md). `benches` holds what is read, by species.
    this.benches = new Map();
    this.reading = new Map();
    // A shape file the view could not read, by its path: the words its panel gives instead.
    this.shapeWords = new Map();
    if (this.raw.entries) for (const name of new Set(this.raw.entries.map((entry) => entry.species))) this.benches.set(name, { status: "found", entries: this.raw.entries.filter((entry) => entry.species === name), byProtein: this.raw.by_protein?.[name] || {}, noneFound: this.raw.none_found?.[name] || [], organelles: (this.raw.organelles || []).filter((entry) => entry.species === name) });
  }

  /** Whether a species' bench is in hand (read, or carried whole). */
  hasBench(species) {
    return this.benches.get(species)?.status === "found";
  }

  /** What became of a species' bench: null before it is asked for; else { status: "found" | "failed", words }. */
  benchState(species) {
    return this.benches.get(species) || null;
  }

  /**
   * Reads a species' bench from beside the page, once (`loadBeside`: the page's own copy where it carries one). Resolves
   * to its state; a bench that cannot be read says why in plain words, and the catalogue goes on without it.
   */
  loadBench(species, { load = loadBeside } = {}) {
    if (this.benches.has(species)) return Promise.resolve(this.benches.get(species));
    const path = this.raw.benches?.[species]?.file;
    if (!path) return Promise.resolve(null);
    if (!this.reading.has(species)) {
      this.reading.set(species, Promise.resolve()
        .then(() => load(path))
        .then((data) => {
          if (data?.format !== BENCH_FORMAT || data.species !== species) throw new Error(`it is not the bench of ${species}`);
          return { status: "found", entries: data.entries || [], byProtein: data.by_protein || {}, noneFound: data.none_found || [], organelles: data.organelles || [] };
        })
        .catch((error) => ({ status: "failed", words: `The machines of this species could not be read (${path}: ${error?.message || error}). The units of the law inventory stand without them.` }))
        .then((state) => {
          this.benches.set(species, state);
          this.reading.delete(species);
          this.cache.delete(species);
          // The views and the page's list read the catalogue again (src/ui/viewer.js listens).
          globalThis.dispatchEvent?.(new CustomEvent("cells-bench", { detail: { species, status: state.status } }));
          return state;
        }));
    }
    return this.reading.get(species);
  }

  /**
   * A unit's size on a species' bench, where the catalogue gives one: by the species' atlas's finding (the inventory's
   * own species counts as "found"), the measure of a structure of the unit's own kind, or of the family the species
   * builds it from. Null where none is in hand: the unit is a card.
   */
  unitSize(unit, species) {
    if (!this.unitSizes?.species?.includes(species)) return null;
    const finding = species === this.reference ? "found" : unit.species?.[species]?.finding;
    return this.unitSizes.units?.[unit.id]?.[finding] || null;
  }

  /** The species the catalogue holds machines for, in the order of its benches (or of its entries, carried whole). */
  get species() {
    return this.raw.benches ? Object.keys(this.raw.benches) : [...new Set((this.raw.entries || []).map((entry) => entry.species))];
  }

  /** Whether a unit of the law inventory is a machine of this species, by its atlas's finding. */
  unitIn(unit, species) {
    // A unit that is no protein assembly (a leak, a permeability, a law that names no protein) is not a machine of the catalogue.
    if (!species || this.leftOut.has(unit.id)) return false;
    // The inventory's own species: a unit that names gene products (a lumped permeability or a configured transporter names none, and is no machine).
    if (species === this.reference) return (unit.sections || []).some((section) => section.key === "products" && section.items?.length);
    return HAS_IT.has(unit.species?.[species]?.finding);
  }

  /**
   * The machines of a species, in the order of the groups: each { id, label, group, kind, entry,
   * unit, size, sized }. A kind's entry carries what the catalogue gives; a unit is the scene's own;
   * `size` is the size it is drawn at, or null.
   */
  of(species) {
    if (this.cache.has(species)) return this.cache.get(species);
    const items = [];
    const bench = this.benches.get(species);
    for (const entry of bench?.entries || []) {
      if (entry.species !== species) continue;
      const kind = this.kinds.get(entry.id);
      if (!kind) continue;
      items.push({ id: pageId(entry.id), label: entry.label || kind.label, group: kind.group, kind, entry, unit: null, size: entry.size || null, sized: Boolean(entry.size || entry.closer) });
    }
    for (const unit of this.units) {
      if (!this.unitIn(unit, species)) continue;
      const size = this.unitSize(unit, species);
      items.push({ id: unit.id, label: unit.label, short: unit.short, group: IONS, kind: null, entry: null, unit, size, sized: Boolean(size) });
    }
    const rank = new Map(this.groups.map((group, index) => [group.id, index]));
    const ordered = items.map((item, index) => [item, index]).sort((a, b) => (rank.get(a[0].group) ?? 99) - (rank.get(b[0].group) ?? 99) || a[1] - b[1]).map(([item]) => item);
    // A bench not yet read is not kept: it is read again once its file is in.
    if (this.hasBench(species) || !this.raw.benches?.[species]) this.cache.set(species, ordered);
    return ordered;
  }

  /**
   * The organelles on a species' shelf (`organelles` of its bench), in the overlay's order: each { id, label, group, kind,
   * entry, size, organelle: true }. They are no machines: in no count of machines and in no tray.
   */
  organellesOf(species) {
    const bench = this.benches.get(species);
    return (bench?.organelles || []).filter((entry) => entry.species === species && this.kinds.has(entry.id)).map((entry) => ({ id: `${ORGANELLE}${entry.id}`, label: entry.label || this.kinds.get(entry.id).label, group: this.kinds.get(entry.id).group, kind: this.kinds.get(entry.id), entry, unit: null, size: entry.size || null, sized: Boolean(entry.size), organelle: true }));
  }

  /** One machine of a species by its page id, or one of its organelles; null for neither. */
  item(species, id) {
    if (organelleKind(id)) return this.organellesOf(species).find((item) => item.id === id) || null;
    return this.of(species).find((item) => item.id === id) || null;
  }

  /** The species that have a machine of this kind (for a machine the species shown lacks). */
  speciesWith(id) {
    const kind = kindOf(id);
    if (kind) return this.kinds.get(kind)?.species || [...new Set((this.raw.entries || []).filter((entry) => entry.id === kind).map((entry) => entry.species))];
    const unit = this.units.find((item) => item.id === id);
    return unit ? (this.scene?.proteins?.atlases || []).map((atlas) => atlas.id).filter((species) => this.unitIn(unit, species)) : [];
  }

  /** What one machine group holds for a species, in order. */
  inGroup(species, group) {
    return this.of(species).filter((item) => item.group === group);
  }

  /** A filter of the catalogue's search: the label, the kind's words, the genes and the identifiers of its proteins. */
  passes(item, query) {
    const words = String(query || "").trim().toLowerCase();
    if (!words) return true;
    return keywords(item).toLowerCase().includes(words);
  }

  /**
   * The machines a species' dossier looked for by family and found no candidate for (`none_found`): not on its bench, in
   * no count; each with its reference machine and what was looked for, part by part. Empty while the bench is not in hand.
   */
  noneFound(species) {
    return this.benches.get(species)?.noneFound || [];
  }

  /** Counts for the card and the legend. */
  counts(species) {
    const items = this.of(species);
    const family = items.filter(byFamily).length, laws = items.filter((item) => item.unit).length;
    // Of the machines that are not units of the law inventory: those the species' records name, and the candidates by family.
    return { machines: items.length, sized: items.filter((item) => item.sized).length, cards: items.filter((item) => !item.sized).length, laws, groups: new Set(items.map((item) => item.group)).size, named: items.length - laws - family, family, none: this.noneFound(species).length };
  }

  source(key) {
    return this.raw.sources?.[key] || null;
  }

  /** The machines a protein of a species is a part of, by its dossier (`by_protein`): [[kind, tier], …]. */
  machinesOf(species, accession) {
    return this.benches.get(species)?.byProtein?.[accession] || [];
  }

  record(key) {
    return this.raw.records?.[key] || null;
  }
}

/** The words a search finds a machine by. */
export function keywords(item) {
  const proteins = [...(item.entry?.proteins?.items || []), ...(item.entry?.gathered?.proteins || [])];
  const structures = (item.entry?.structures || []).flatMap(({ id, title, partner_organisms }) => [id, title, ...(partner_organisms || [])]);
  const chains = item.entry?.structures ? item.size.chains.flatMap(({ label, protein }) => [label, protein]) : [];
  return [item.label, item.short, item.kind?.plain, item.unit?.eyebrow, item.unit?.keywords, ...proteins.map(([id, gene, label]) => [id, gene, label].filter(Boolean).join(" ")), ...structures, ...chains].filter(Boolean).join(" ");
}

/** "Gilbert and others (2021)": the citation's head, for a line that names its source. */
export function citeShort(source) {
  const text = String(source?.text || "");
  const entry = /^Protein Data Bank entry (\S+?):/.exec(text);
  if (entry) return `PDB ${entry[1]}`;
  const head = /^(.+?\(\d{4}\))/.exec(text);
  return head ? head[1] : text.split(". ")[0];
}
