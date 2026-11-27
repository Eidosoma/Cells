// The protein atlas lens: the units of Cells' law inventory, set in the membranes
// where their laws act. One stretch of plasma membrane holds the channels, pumps and
// transporters; a second membrane above one corner is the neighbouring cell, for the
// junction channels; pieces of ER and mitochondrial membrane and the protein cage sit
// below, inside the cell.
//
// The picture keeps the inventory's own distinction, and form carries it:
//   assigned in source   a solid assembly, drawn from the stated subunit counts;
//   candidate            the candidate's assembly, drawn clear;
//   generic              a plain grey stand-in with no subunits: no protein is assigned.
// These are the inventory's words, not engine statuses.
//
// A unit has no species; which gene products would make it does. The inventory's candidates
// are human. Another species' atlas (schema/SPECIES_ATLAS.md) changes what the panel lists
// and puts a flat ring beside each unit where that species differs. The units, their forms
// and the engine's laws are the same in every atlas.
//
// The lens shows one of two things. "units" is that board: the units of Cells' law inventory.
// "own" is the species' own proteins on shelves (schema/SPECIES_PROTEINS.md), whether or not
// they are listed with a unit of the inventory: protein_shelves.js reads them and shelves_view.js draws them.
// Their file is published beside the page and fetched when the species is first shown.

import * as THREE from "../three.js";
import { soften } from "../core/materials.js";
import { disposeTree } from "../core/stage.js";
import { makeEnvironment } from "../core/environment.js";
import { SHEET, UPPER, buildUnit, findingMark, membrane, outline } from "./protein_parts.js";
import { BASES, LICENCE_NOTE, LICENCE_TAG, NAMES_FILE, NO_SHELF, SIDES, Shelves, keyOf, licenceClass, loadBeside, plural } from "./protein_shelves.js";
import { ORDERED_MARKS, ShelvesView, columnsFor, opensFor, shapeFor } from "./shelves_view.js";

// The legend's row for the whole stack of a species with several shelves, beside its shelves' rows.
const WHOLE = "stack";

const PITCH = 11.5; // spacing of units within a district
const GUTTER = 9; // between districts
const BETWEEN_BANDS = 17;
const MARGIN = 8; // from the outermost units to the membrane's edge
const DROP = 30; // how far below the plasma membrane the organelle membranes sit
const HALF = SHEET / 2;
const WHITE = new THREE.Color(0xffffff), BLACK = new THREE.Color(0x000000);

// How each tone is drawn. "named" is the colour of a protein the law names; "generic" is grey.
const TONES = {
  main: { hue: "named", shade: 0 },
  alt: { hue: "named", shade: -0.24 },
  aux: { hue: "named", shade: 0.36 },
  second: { hue: "named", shade: 0.44 },
  secondAlt: { hue: "named", shade: 0.27 },
  ghost: { hue: "named", shade: 0.3, opacity: 0.26, glass: 0.6 },
  glass: { hue: "named", shade: 0.08, opacity: 0.4, glass: 0.55 },
  glassAlt: { hue: "named", shade: -0.06, opacity: 0.4, glass: 0.55 },
  glassAux: { hue: "named", shade: 0.32, opacity: 0.32, glass: 0.55 },
  plain: { hue: "generic", shade: 0, roughness: 0.78, side: THREE.DoubleSide },
  plainSoft: { hue: "generic", shade: 0.12, opacity: 0.55 },
};
const CLEAR = { main: "glass", alt: "glassAlt", aux: "glassAux", second: "glassAux", secondAlt: "glassAux", ghost: "ghost" };
const SHEET_HUE = { plasma: "bioMembrane", neighbour: "bioMembrane", er: "bioEr", mitochondria: "bioMito" };
const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const day = (iso) => (iso ? `${Number(iso.slice(8, 10))} ${months[Number(iso.slice(5, 7)) - 1]} ${iso.slice(0, 4)}` : "");

/** What is known about the identifiers the engine gained since the inventory: a dated review, or nothing. */
function gainedNote(gained) {
  const review = gained.review;
  if (!review) return "The inventory has not reviewed them, so a law added since would be missing here.";
  if (review.covers_all) return review.text;
  return `${review.count} of them were reviewed on ${day(review.date)}; the rest are unreviewed, so a law added since would be missing here.`;
}

const lower = (text) => text.charAt(0).toLowerCase() + text.slice(1);
const LAWS_NOTE = "The same laws for every species.";
const number = (value) => Number(value).toLocaleString("en-US");

/** What the scene says of one species' own proteins (the file beside the page), or null. */
export function shelvesOf(proteins, id) {
  return (proteins?.shelves || []).find((item) => item.id === id) || null;
}

/**
 * Which of the two the atlas opens on for a species: the units of Cells' law inventory, or the
 * species' own proteins. A species in which the atlas found almost none of those units,
 * or which has no side of the atlas at all, says most with its own proteins.
 */
export function firstMode(proteins, id) {
  if (!shelvesOf(proteins, id)) return "units";
  const atlas = atlasOf(proteins, id);
  return !atlas || quietAtlas(proteins, atlas) ? "own" : "units";
}

/** One species' atlas in the scene's protein block, or null. */
export function atlasOf(proteins, id) {
  return (proteins?.atlases || []).find((atlas) => atlas.id === id) || null;
}

/** The atlas the view opens on: the inventory's own, else the first; null in a scene without atlases. */
export function defaultAtlas(proteins) {
  const atlases = proteins?.atlases || [];
  return (atlases.find((atlas) => atlas.reference) || atlases[0])?.id ?? null;
}

/**
 * Whether a species' atlas differs from the inventory's for so many units that a ring
 * beside each would bury the picture (a bacterium has almost none of the units the
 * laws name). Such an atlas is shown quietly: no rings, and the units it found no product
 * for, or another family for, are drawn faint.
 */
export function quietAtlas(proteins, atlas) {
  if (!atlas || atlas.reference) return false;
  const marked = new Set((proteins.findings || []).filter((word) => word.mark).map((word) => word.id));
  const differing = (atlas.findings || []).filter((item) => marked.has(item.id)).reduce((sum, item) => sum + item.count, 0);
  return differing > (atlas.counts?.units || 0) / 4;
}

/**
 * A unit as one species' atlas shows it: the same unit, form and engine laws, with that
 * species' finding and its gene products where the inventory's candidates stood.
 * In the inventory's own atlas (human) a unit is the scene's part, untouched.
 */
export function inSpecies(entity, proteins, id) {
  const atlas = atlasOf(proteins, id);
  if (!entity || entity.kind !== "unit" || !atlas || atlas.reference) return entity;
  const own = entity.species?.[atlas.id] || {};
  const evidence = proteins.unitEvidence?.get(atlas.id)?.units?.[entity.id] || own;
  const word = (proteins.findings || []).find((item) => item.id === own.finding) || null;
  // In a quiet atlas a unit that differs is drawn faint, and the same faint mark says so in words.
  const quiet = quietAtlas(proteins, atlas);
  const swatch = word?.mark ? (quiet ? "find-faint" : `find-${word.mark}`) : null;
  const said = `${atlas.label}: ${word ? lower(word.label) : "no entry"}`;
  const sections = (entity.sections || [])
    .filter((section) => section.key !== "products")
    .map((section) => (section.key === "laws" ? { ...section, note: LAWS_NOTE } : section));
  sections.splice(sections.findIndex((section) => section.key === "laws") + 1, 0, { key: "products", title: `${atlas.label} gene products`, items: evidence.items || [] });
  return {
    ...entity,
    chips: [...(entity.chips || []), { label: said, title: word?.description || proteins.no_entry, swatch }],
    finding: { title: atlas.label, organism: atlas.organism, swatch, text: word?.sentence || proteins.no_entry, note: evidence.note || null, more: word?.more || null },
    sections,
    sign: swatch && !quiet ? { swatch, title: said } : null,
    faint: Boolean(swatch) && quiet,
    keywords: [entity.keywords, own.keywords].filter(Boolean).join(" "),
  };
}

/** A list of clauses as a sentence's parts: "a", "a and b", "a, b and c". */
const listed = (items) => (items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items.at(-1)}`);

/**
 * How a species' products were found, and what their records are: two sentences from the two
 * counts the scene gives (schema/SPECIES_ATLAS.md), kept apart. How a product was found decides
 * what it is a candidate for; how its entry was written never does. A scene made before the
 * two facts were kept apart has neither count, and then nothing is said of either.
 */
export function productWords(counts, foundBy, entries) {
  const total = counts.products;
  if (!total || !foundBy || !entries) return "";
  const n = (list, id) => list.find((item) => item.id === id)?.count || 0;
  const one = (count, single, many) => (count === 1 ? single : many);
  const found = [
    [n(foundBy, "family signature"), (c) => `by the signature of a family that makes the machine, ${one(c, "a candidate", "candidates")} by family, not ${one(c, "an established counterpart", "established counterparts")}`],
    [n(foundBy, "similarity search"), (c) => `by sequence similarity, ${one(c, "a candidate", "candidates")}, not ${one(c, "an established counterpart", "established counterparts")}`],
    [n(foundBy, "accessory signature"), (c) => `only by that of a family that goes with one (a regulator, or a subunit that makes none by itself), no ${one(c, "candidate", "candidates")} for its own work`],
    [n(foundBy, "named in a publication"), () => "named in a publication"],
    [n(foundBy, "not stated"), () => "in a way the file does not state"],
  ].filter(([count]) => count);
  // The records: UniProtKB entries are named once, then counted by how they were written.
  let entryNamed = false;
  const uniprot = (c, how) => {
    const noun = entryNamed ? "" : `UniProtKB ${one(c, "entry", "entries")} `;
    entryNamed = true;
    return `${noun}${how}`;
  };
  const records = [
    [n(entries, "reviewed"), (c) => uniprot(c, "reviewed by a curator")],
    [n(entries, "unreviewed"), (c) => uniprot(c, "annotated automatically")],
    [n(entries, "genome annotation"), (c) => `${one(c, "a gene model or genome-record protein", "gene models or genome-record proteins")} with no UniProtKB entry`],
    [n(entries, "not stated"), () => "not stated in the file"],
  ].filter(([count]) => count);
  // A kind that covers every product is said with "all"; several are counted one by one.
  const counted = (parts) => (parts.length === 1 && parts[0][0] === total ? [`${total === 1 ? "the one" : `all ${number(total)}`} ${parts[0][1](total)}`] : parts.map(([count, said]) => `${number(count)} ${said(count)}`));
  const reviewed = n(entries, "reviewed");
  return [
    `How they were found: ${counted(found).join("; ")}.`,
    records.length ? `Their records: ${counted(records).join(", ")}${reviewed ? "; a reviewed entry says how the entry was written, not that the protein does a unit's work" : ""}.` : "",
  ].filter(Boolean).join(" ");
}

/**
 * What the view says on a species other than the inventory's own: the species' counts, sources
 * and findings. The units and laws are named as the engine's, the same for every species, and
 * nothing here says the engine models the species' proteins. It reads the data only.
 */
export function speciesWords(proteins, species) {
  // A species named by a plain word is written small in a sentence ("the planarian atlas"); a name such as Syn3A keeps its letters.
  const name = /^[A-Z][a-z]+$/.test(species.label) ? lower(species.label) : species.label;
  const counts = species.counts;
  const words = new Map((proteins.findings || []).map((word) => [word.id, word]));
  // The two facts of the products, apart. A scene made before they were has neither, and the card then says nothing of them.
  const kept = Array.isArray(species.found_by) && Array.isArray(species.entries);
  const said = kept ? productWords(counts, species.found_by, species.entries) : "";
  const quiet = quietAtlas(proteins, species);
  const more = (species.extra || []).length;
  return {
    caveat: quiet
      ? `Shapes are schematic and show what the engine's law names, the same for every species. A unit drawn faint is one the ${name} atlas found no gene product for.`
      : `Shapes are schematic and show what the engine's law names, the same for every species. A ring marks a unit where the ${name} atlas differs.`,
    stamp: `${species.label} atlas${species.made ? ` of ${day(species.made)}` : ""} · inventory of ${day(proteins.stamp.created)}`,
    findings: {
      title: "In this species",
      unit: "units",
      items: (species.findings || []).map((item) => {
        const word = words.get(item.id);
        return { id: item.id, label: word?.label || item.id, title: word?.description, count: item.count, swatch: word?.mark ? (quiet ? "find-faint" : `find-${word.mark}`) : null };
      }),
    },
    card: {
      heading: `${species.label} atlas`,
      organism: species.organism,
      stats: [[counts.with_products, `of ${counts.units} units have products`], [counts.products, "gene products"], ...(kept ? [[counts.candidates, "of them candidates for a unit"]] : [])],
      text: species.plain,
      check:
        `The ${counts.units} units of Cells' law inventory and their laws are the same for every species. Listed here are the ${name} gene products that would make each unit, not anything the engine models.` +
        (said ? ` ${said}` : "") +
        // Where the species has almost none of these units, the card points at the proteins it does have.
        (quiet && more ? ` Most of these units were not found in it. The ${more} of its own proteins that bear on the picture are listed below.` : ""),
      method: species.method,
      extra: species.extra,
      extraOpen: quiet && more > 0,
      sources: species.sources || [],
      notCopied: species.not_copied,
    },
  };
}

export class ProteinLens {
  constructor(stage, model, labels) {
    this.id = "proteins";
    this.stage = stage;
    this.model = model;
    this.labels = labels;
    this.atlas = model.raw.proteins;
    this.root = new THREE.Group();
    this.nodes = new Map(); // unit id -> { entity, group, meshes, reach, top, ... }
    this.tones = new Map();
    this.sheets = [];
    this.districts = [];
    this.selected = null;
    this.hovered = null;
    this.isolate = null; // a mapping id
    this.evidence = null; // a kind of evidence
    this.shown = defaultAtlas(this.atlas); // the id of the atlas shown
    this.species = null; // that atlas, when it is another species than the inventory's own
    this.list = model.raw.species || []; // the species the page can show (schema/SPECIES.md)
    this.page = this.shown; // the species the page shows; it may have no atlas yet
    this.finding = null; // one thing the species' atlas found, shown alone
    this.waitingFinding = null; // a finding asked for while the species' own proteins were still being fetched
    this.marks = []; // the rings beside the units where the species differs
    this.markMaterial = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide });
    this.active = false;
    this.environment = makeEnvironment(stage.renderer);
    // The species' own proteins: which of the two is shown, what the visitor asked for, and
    // each species' shelves once its file is in.
    this.mode = "units"; // "units": the units of Cells' law inventory; "own": the species' own proteins
    this.wanted = null; // the one of the two the visitor asked for, kept from species to species
    this.own = new Map(); // species id -> { status: "loading" | "ready" | "failed", shelves, views, error, promise }
    this.mounted = null; // the shelves that are drawn, in place of the board of units; null while the board is
    this.markName = null; // the mark the legend's last block shows
    this.ready = null; // settles when what the lens is about to show has loaded
    this.build();
    this.applyPalette(stage.palette);
  }

  // ------------------------------------------------------------ layout

  build() {
    const units = this.model.inGroup("proteins");
    const districts = this.atlas.districts
      .map((district) => ({ ...district, units: units.filter((unit) => unit.district === district.id) }))
      .filter((district) => district.units.length);
    for (const district of districts) {
      district.rows = Math.ceil(district.units.length / district.columns);
      district.width = district.columns * PITCH;
      district.depth = district.rows * PITCH;
    }
    const band = (index) => districts.filter((district) => district.band === index);
    const span = (row, gap = GUTTER) => row.reduce((sum, district) => sum + district.width, 0) + gap * (row.length - 1);
    const deepest = (row) => Math.max(0, ...row.map((district) => district.depth));
    const back = band(0), front = band(1), inside = band(2);
    const width = Math.max(span(back), span(front)) + 2 * MARGIN;
    const depth = deepest(back) + (front.length ? BETWEEN_BANDS + deepest(front) : 0) + 2 * MARGIN;
    const place = (row, z, y, gap = GUTTER, centre = 0) => {
      let x = centre - span(row, gap) / 2;
      for (const district of row) {
        district.centre = new THREE.Vector3(x + district.width / 2, y, z);
        x += district.width + gap;
      }
    };
    place(back, -depth / 2 + MARGIN + deepest(back) / 2, 0);
    place(front, depth / 2 - MARGIN - deepest(front) / 2, 0);
    place(inside, depth / 2 + 22, -DROP, 20, width * 0.12);

    this.lineMaterial = new THREE.LineBasicMaterial({ transparent: true, opacity: 0.4, depthWrite: false });
    this.dashes = new THREE.LineDashedMaterial({ transparent: true, opacity: 0.9, dashSize: 0.7, gapSize: 0.5 });
    this.sheet("plasma", width, depth, new THREE.Vector3(0, 0, 0), 7);
    for (const district of districts) {
      const { centre } = district;
      const own = district.band === 2 && SHEET_HUE[district.id];
      if (own) this.sheet(district.id, district.width + 12, district.depth + 12, centre, 6);
      if (district.id === "junctions") this.sheet("neighbour", district.width + 8, district.depth + 8, centre.clone().setY(UPPER), 6);
      if (district.band !== 2) {
        const edge = new THREE.LineLoop(outline(district.width + 1.5, district.depth + 1.5, 4), this.lineMaterial);
        edge.position.set(centre.x, HALF + 0.08, centre.z);
        edge.userData.unpickable = true;
        edge.renderOrder = 3;
        this.root.add(edge);
      }
      // The district's name lies just in front of it, on the membrane.
      const drop = district.id === "assembly" ? -5 : HALF;
      district.anchor = new THREE.Vector3(centre.x, centre.y + drop, centre.z + district.depth / 2 + (own ? 9.5 : 4.4));
      district.units.forEach((unit, index) => {
        const column = index % district.columns, row = Math.floor(index / district.columns);
        this.unit(unit, new THREE.Vector3(centre.x - district.width / 2 + (column + 0.5) * PITCH, centre.y, centre.z - district.depth / 2 + (row + 0.5) * PITCH));
      });
    }
    this.districts = districts;
    this.sides = [
      { text: "Outside the cell", anchor: new THREE.Vector3(-width / 2 + 4, 13, -depth / 2 + 2) },
      { text: "Inside the cell", anchor: new THREE.Vector3(-width / 2 + 4, -DROP * 0.55, depth / 2 + 6) },
    ];
    this.board = { minX: -width / 2, maxX: width / 2, minZ: -depth / 2, maxZ: depth / 2 + 22 + PITCH, minY: -DROP - 8, maxY: UPPER + 4 };

    // One ring marks the unit in focus, a lighter one the unit under the pointer.
    const ring = new THREE.TorusGeometry(1, 0.02, 8, 72);
    this.ring = new THREE.Mesh(ring, new THREE.MeshBasicMaterial());
    this.hoverRing = new THREE.Mesh(ring, new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.6 }));
    for (const mark of [this.ring, this.hoverRing]) {
      mark.rotation.x = Math.PI / 2;
      mark.visible = false;
      mark.renderOrder = 6;
      mark.userData.unpickable = true;
      this.root.add(mark);
    }
    this.fill = new THREE.DirectionalLight(0xffffff, 0.6);
    this.fill.position.set(-80, -30, 60); // from below and in front, so the parts under the membrane read
    this.root.add(this.fill);
  }

  sheet(name, width, depth, centre, radius) {
    const sheet = membrane(width, depth, radius);
    sheet.group.position.copy(centre);
    sheet.hue = SHEET_HUE[name];
    this.sheets.push(sheet);
    this.root.add(sheet.group);
  }

  tone(name) {
    if (!this.tones.has(name)) {
      const spec = TONES[name];
      const opacity = spec.opacity ?? 1;
      const lit = new THREE.MeshStandardMaterial({ roughness: spec.roughness ?? 0.42, metalness: 0, transparent: opacity < 1, opacity, depthWrite: opacity === 1, side: spec.side ?? THREE.FrontSide });
      soften(lit, { rim: 0.32, alphaRim: spec.glass || 0 });
      const dim = new THREE.MeshStandardMaterial({ roughness: 0.9, metalness: 0, transparent: true, opacity: Math.max(0.06, opacity * 0.14), depthWrite: false, side: spec.side ?? THREE.FrontSide });
      this.tones.set(name, { spec, lit, dim });
    }
    return this.tones.get(name);
  }

  /** A unit's form as a group of its own, not yet placed: { entity, group, meshes, reach }. */
  makeUnit(entity) {
    const form = entity.form;
    const group = new THREE.Group();
    const node = { entity, group, meshes: [] };
    const scratch = new THREE.Object3D();
    const add = (geometry, tone, at, options = {}) => {
      if (options.line) {
        const line = new THREE.LineLoop(geometry, this.dashes);
        line.computeLineDistances();
        line.position.fromArray(at);
        line.userData.unpickable = true;
        group.add(line);
        return;
      }
      const name = form.style === "glass" ? CLEAR[tone] || tone : tone;
      const set = this.tone(name);
      const scale = options.scale ?? 1;
      let mesh;
      if (Array.isArray(at) && at[0]?.isVector3) {
        // Many copies of one shape, each a little lighter or darker (the cage's trimers).
        mesh = new THREE.InstancedMesh(geometry, set.lit, at.length);
        at.forEach((point, index) => {
          scratch.position.copy(point);
          scratch.scale.setScalar(scale);
          scratch.updateMatrix();
          mesh.setMatrixAt(index, scratch.matrix);
          mesh.setColorAt(index, new THREE.Color().setScalar(options.shades?.[index] ?? 1));
        });
        mesh.instanceMatrix.needsUpdate = true;
      } else {
        mesh = new THREE.Mesh(geometry, set.lit);
        mesh.position.fromArray(at);
        if (Array.isArray(scale)) mesh.scale.fromArray(scale);
        else mesh.scale.setScalar(scale);
      }
      mesh.userData.tone = name;
      mesh.renderOrder = 4; // clear parts are drawn after the membranes they stand in
      group.add(mesh);
      node.meshes.push(mesh);
    };
    const reach = buildUnit(form, add);
    if (form.flip) group.rotation.x = Math.PI;
    node.reach = reach;
    return node;
  }

  unit(entity, position) {
    const form = entity.form;
    const node = this.makeUnit(entity);
    const { group, reach } = node;
    group.position.copy(position);
    group.userData.pick = entity.id;
    node.position = position;
    if (reach.floats) group.position.y += 3;
    node.top = group.position.clone().setY(group.position.y + reach.top + 0.6);
    // The ring lies on the membrane the unit stands in; a junction channel's, on the neighbouring cell's.
    node.ringAt = group.position.clone().setY(group.position.y + (reach.floats ? 0 : form.shape === "junction" ? UPPER + HALF + 0.2 : HALF + 0.2));
    this.root.add(group);
    this.nodes.set(entity.id, node);
  }

  // ------------------------------------------------------------ lens interface

  /** The proteins of the species shown, once their file is in; null before, or if it has none. */
  ownData() {
    const state = this.own.get(this.page);
    return state?.status === "ready" ? state.shelves : null;
  }

  /**
   * The shelves of the species shown, laid out for the screen as it is now (a tall screen
   * sees a narrower, deeper stack); null if they are not in.
   */
  ownView() {
    const state = this.own.get(this.page);
    if (state?.status !== "ready") return null;
    const shape = shapeFor(this.stage);
    // Several shelves stand as two staircases side by side on a wide screen, where the page opens
    // on the whole stack as a map to pick a shelf from; and as one staircase on a narrow screen,
    // where it opens on the first shelf (settled on 15 November 2026, by looking at both).
    const columns = state.shelves.several ? columnsFor(this.stage) : 1;
    const opens = state.shelves.several ? opensFor(this.stage) : "stack";
    const key = `${shape}:${columns}:${opens}`;
    if (!state.views.has(key)) {
      const view = new ShelvesView(this, state.shelves, { shape, columns, opens });
      view.setColourBy(this.ownColour || "side", this.ownMark || null);
      view.applyPalette(this.stage.palette);
      state.views.set(key, view);
    }
    return state.views.get(key);
  }

  get bounds() {
    return this.mounted ? this.mounted.bounds : this.board;
  }

  /**
   * The shelves' own key for a key as it was given, or null: a family named without its
   * shelf (in an address, or by a page of another species, where it has the same id) is
   * the family's line with the most members.
   */
  ownKey(id) {
    return (id && this.ownData()?.resolve(id)) || null;
  }

  has(id) {
    return this.nodes.has(id) || Boolean(this.ownKey(id));
  }

  entities() {
    if (this.mounted) return this.mounted.entities();
    return [...this.nodes.values()].map((node) => node.entity);
  }

  sections() {
    if (this.mounted) return this.mounted.sections();
    return this.districts.map((district) => ({ label: district.label, entities: district.units.map((unit) => this.present(unit)) }));
  }

  /** A part the shelves make themselves: one protein, a family, or a gathering of small ones. */
  describe(id) {
    const key = this.ownKey(id);
    const said = key ? this.ownData().describe(key) : null;
    // Coloured by side, the panel's chip for a side takes the side's colour, as the markers and the legend do.
    if (said && this.mounted?.colourBy === "side") for (const chip of said.chips || []) if (/^own-(outside|in|inside)$/.test(chip.swatch || "")) chip.swatch = chip.swatch.replace(/^own-/, "own-side-");
    // While a set is picked out, a family, a part or a gathering says how many of the set it holds, and which.
    const view = this.mounted, set = view?.mark, shelves = view?.shelves;
    const held = said && set && shelves.kind === "families" && shelves.get(key).type !== "p" ? shelves.highlightOf(shelves.get(key), set.name, set.value) : [];
    if (held.length) {
      const mark = shelves.marks[set.name] || {}, total = shelves.highlight.get(set.name).get(set.value).total;
      const names = held.map((protein) => protein.gene || protein.id);
      said.facts = [...(said.facts || []), [set.value === "true" ? mark.label || set.name : `${mark.label || set.name}: ${set.value}`, `${number(held.length)} of the ${number(total)} proteins: ${names.slice(0, 12).join(", ")}${names.length > 12 ? `, and ${number(names.length - 12)} more` : ""}`]];
    }
    return said;
  }

  // ------------------------------------------------------------ the species' own proteins

  /**
   * One species' own proteins: the file is fetched once, from beside the page. Returns the
   * state, whose promise settles when the proteins are in or could not be read; null for a
   * species the scene names no file for.
   */
  ownState(id) {
    let state = this.own.get(id);
    const summary = shelvesOf(this.atlas, id);
    if (state || !summary) return state || null;
    const named = this.list.find((item) => item.id === id) || atlasOf(this.atlas, id);
    state = { status: "loading", error: null, shelves: null, views: new Map() };
    state.promise = loadBeside(summary.file)
      .then((data) => {
        if (data.species !== id) throw new Error(`${summary.file} holds the proteins of ${data.species}`);
        const units = new Map(this.model.inGroup("proteins").map((unit) => [unit.id.replace(/^unit\./, ""), unit.id]));
        state.shelves = new Shelves(data, { label: named?.label, organism: named?.organism, links: this.atlas.shelf_links, units, found: this.atlas.product_found_by });
        state.status = "ready";
      })
      .catch((error) => {
        state.status = "failed";
        state.error = error.message;
      });
    this.own.set(id, state);
    return state;
  }

  /** The member files of a large catalogue, fetched when a family is first opened. */
  async loadMembers(shelves, names) {
    const folder = shelvesOf(this.atlas, shelves.id).file.replace(/[^/]*$/, "");
    await Promise.all(names.filter((name) => !shelves.loaded.has(name)).map(async (name) => shelves.addMembers(name, await loadBeside(folder + name))));
  }

  /**
   * Show the units of Cells' law inventory ("units") or the species' own proteins ("own").
   * The own proteins are shown once their file is in; until then, and if it cannot be read,
   * the units are. Returns a promise that settles when the lens shows what it will.
   */
  setMode(mode, { user = false } = {}) {
    const wants = mode === "own" && shelvesOf(this.atlas, this.page) ? "own" : "units";
    if (user) this.wanted = wants;
    // Asked for again after they could not be read: they are fetched again.
    if (user && wants === "own" && this.own.get(this.page)?.status === "failed") this.own.delete(this.page);
    // The species' own proteins are fetched when it is shown here, whichever of the two is drawn:
    // a unit's panel then names the families that hold its products.
    const state = this.ownState(this.page);
    if (!state || state.status === "ready") {
      this.enter(wants);
      return (this.ready = Promise.resolve());
    }
    // Still being fetched, or it failed: the units are shown, and the card says which.
    const page = this.page;
    this.enter("units");
    this.onChrome?.();
    return (this.ready = state.promise.then(() => {
      if (this.page !== page) return; // another species was chosen meanwhile
      if (state.status === "ready" && wants === "own" && (this.wanted || firstMode(this.atlas, page)) === "own") {
        this.enter("own");
        const waiting = this.waitingFinding;
        this.waitingFinding = null;
        if (waiting?.page === page && this.mounted) this.setFinding(waiting.finding);
      } else {
        this.onChrome?.();
        this.onPanel?.();
      }
    }));
  }

  /** After the species changed: the one of the two that the visitor asked for, or that says most of it. */
  settleMode() {
    return this.setMode(shelvesOf(this.atlas, this.page) ? this.wanted || firstMode(this.atlas, this.page) : "units");
  }

  /** Put the board of units or the shelves in the scene, whichever `mode` says and is there. */
  enter(mode) {
    const next = mode === "own" ? this.ownView() : null;
    const before = this.mounted;
    this.mode = next ? "own" : "units";
    if (next === before) return;
    // What was chosen and filtered belongs to what was shown.
    this.selected = this.hovered = null;
    this.isolate = this.evidence = this.finding = null;
    before?.reset();
    next?.reset();
    this.mounted = next;
    if (this.active) {
      this.stage.scene.remove(before ? before.group : this.root);
      this.stage.scene.add(next ? next.group : this.root);
      this.stage.rig.limits = this.rigLimits();
      this.stage.rig.setView(this.homeView());
      this.buildLabels();
      this.refresh();
    }
    this.onMode?.();
  }

  /** How near and how far the camera may go: far enough to see whatever is drawn whole (several shelves reach far). */
  rigLimits() {
    const bounds = this.bounds;
    const reach = this.mounted?.shelves.several ? Math.max(bounds.maxX - bounds.minX, bounds.maxZ - bounds.minZ) : 0;
    return { minDistance: 16, maxDistance: Math.max(900, reach * 4), minPolar: 0.12, maxPolar: 2.5 };
  }

  /** Close the family that is open, if one is. Returns whether one was. */
  back() {
    const view = this.mounted;
    if (view?.opened || view?.wanted) {
      view.close();
      return true;
    }
    // Of several shelves: from the shelf in focus back to the whole stack.
    return Boolean(view?.shelves.several && view.focused !== undefined && view.focusOn(undefined));
  }

  // ------------------------------------------------------------ what colour carries

  /** The choices of "Colour" for a species' own proteins: [value, words]. A mark is "mark:<its name>". */
  colourChoices(shelves) {
    const out = [["side", "Side of its membrane"], ["basis", "How the side is known"]];
    const small = shelves.kind === "proteins" ? shelves.filterable() : [];
    const ordered = small.filter((mark) => ORDERED_MARKS.has(mark.id));
    for (const mark of ordered) out.push([`mark:${mark.id}`, mark.measured ? `${mark.label}, measured` : mark.label]);
    out.push(["law", "Cells' law inventory"]);
    // The other marks of a catalogue of one marker each (what its "Show by" offered): a protein with a value is coloured.
    for (const mark of small.filter((item) => !ORDERED_MARKS.has(item.id))) out.push([`mark:${mark.id}`, mark.label]);
    return out;
  }

  /** Show the species' own proteins coloured by a choice of colourChoices(); the visitor's choice is kept for the next species where it has a meaning there. */
  setOwnColour(choice) {
    const [mode, name] = String(choice || "side").split(":");
    this.ownColour = ["side", "basis", "mark", "law"].includes(mode) ? mode : "side";
    this.ownMark = this.ownColour === "mark" ? name || null : null;
    for (const state of this.own.values()) for (const view of state.views?.values() || []) view.setColourBy(this.ownColour, this.ownMark);
    const view = this.mounted;
    if (view) {
      // What was shown alone belonged to what colour carried.
      view.isolate = view.basis = null;
      if (view.shelves.kind === "proteins") view.mark = null;
      view.paint();
      // The page lets go of what its legend showed alone, too.
      this.stage.renderer.domElement.dispatchEvent(new CustomEvent("cells-isolate", { detail: null, bubbles: true, composed: true }));
    }
    this.onChrome?.();
  }

  /** The legend's first block for what colour carries now: its title, the choice at its head, and the values with their counts. */
  colourLegend(shelves, view, near, words, basis) {
    const several = shelves.several, families = shelves.kind === "families";
    const by = view.colourBy;
    const choices = this.colourChoices(shelves);
    const active = by === "mark" ? `mark:${view.markName}` : by;
    const colour = { options: choices, active: choices.some(([id]) => id === active) ? active : "side" };
    // The sides: with one shelf, its own words; of several, those of the shelf in focus, or, for the whole stack, the
    // words that hold on every shelf (each shelf names what lies on each side of its membrane).
    const generic = { outside: ["Beyond its membrane", "Beyond the membrane of its shelf: each shelf names what lies there"], in: ["In its membrane", "Spans the membrane of its shelf"], inside: ["Enclosed by its membrane", "Enclosed by the membrane of its shelf: each shelf names what lies there"], "not known": ["Side not known", "No source states the side and nothing predicts it: set apart, hollow, not placed by guess"] };
    const sideItem = (side, count) => {
      const [label, description] = several && !near ? generic[side] : [words[side].short, words[side].long];
      return { id: side, label, description, count, swatch: by === "side" && side !== "not known" ? `own-side-${side}` : words[side].swatch };
    };
    const sideItems = () => {
      if (!several) return SIDES.map((side) => sideItem(side, shelves.counts[side]));
      const counts = near ? near.counts : shelves.counts;
      return SIDES.filter((side) => counts[side] || view.isolate === side).map((side) => sideItem(side, counts[side]));
    };
    const sideTitle = !several ? "Side of the membrane" : near ? (near.id === null ? "No place known" : `${near.label}: sides`) : "Side of its membrane";
    if (by === "basis") {
      const items = [...BASES.filter((id) => id !== "none"), "none"].filter((id) => basis[id]).map((id, index) => ({ id, label: shelves.basisWords(id).label, description: shelves.basisWords(id).sentence, count: basis[id], swatch: id === "none" ? "own-unknown" : `own-basis-${["stated", "predicted", "by function"].indexOf(id) + 1}` }));
      return { title: "How the side is known", items, colour, note: families ? { text: "A family's marker carries no basis and stays grey: open it to see each member's." } : null };
    }
    if (by === "mark") {
      const mark = shelves.filterable().find((item) => item.id === view.markName);
      if (mark) {
        const ordered = ORDERED_MARKS.has(mark.id);
        const values = Array.isArray(shelves.marks[mark.id]?.values) ? shelves.marks[mark.id].values.map(String) : [];
        const items = mark.items.map((item) => ({ id: item.id, label: item.label, description: mark.note || "", count: item.count, swatch: ordered ? `own-mark-${Math.min(3, values.indexOf(item.id) + 1) || 1}` : item.id === "false" || item.id === "" ? "own-plain" : "own-mark-1" }));
        return { title: mark.measured ? `${mark.label}, measured` : mark.label, items, colour, note: ordered ? null : { text: "A protein that carries a value of this mark takes its colour; the others stay grey." } };
      }
    }
    return { title: sideTitle, items: sideItems(), colour, note: by === "law" ? { swatch: "map-assigned", text: "One hue for a protein or family that makes a unit of Cells' law inventory; every other is grey." } : null };
  }

  // ------------------------------------------------------------ the trail, Escape, the search and the map

  /**
   * Where the visitor is among the species' own proteins, as the trail says it: the species, the shelf in focus,
   * a side shown alone, the family open (or on its way), the protein chosen. Each { id, label, title, side }.
   */
  trailLevels() {
    const view = this.mounted;
    if (!view) return [];
    const shelves = view.shelves;
    const out = [{ id: "species", label: `${shelves.label} · ${number(shelves.total)}`, title: shelves.several ? "The whole stack" : "All its proteins" }];
    if (shelves.several && view.focused !== undefined) {
      const entry = shelves.byShelf.find((item) => item.id === view.focused);
      out.push({ id: "shelf", label: entry?.label ?? "No place known", title: "This shelf, with nothing open" });
    }
    if (view.isolate) {
      const words = shelves.sideWords(shelves.several ? (view.focused ?? null) : undefined)[view.isolate];
      out.push({ id: "side", label: words?.short || view.isolate, title: "Only this side", side: view.isolate });
    }
    const item = view.opened || view.wanted;
    if (item) {
      const label = item.type === "l" ? plural(item.count, "family of one", "families of one") : item.label;
      out.push({ id: "family", label: view.opened ? `${label} · ${number(item.count)}` : `Opening ${label}…`, title: view.opened ? "The open family" : "Its proteins are being fetched", side: item.side, opening: !view.opened });
    }
    const chosen = view.selected ? shelves.get(view.selected) : null;
    if (chosen?.type === "p") out.push({ id: "protein", label: chosen.gene && chosen.gene !== chosen.label ? `${chosen.gene} · ${chosen.label}` : chosen.label, title: "The protein chosen", side: chosen.side });
    return out;
  }

  /** Go back to a level of the trail: what is deeper is let go of. Returns whether anything changed. */
  goTo(level) {
    const view = this.mounted;
    if (!view) return false;
    const levels = this.trailLevels(), at = levels.findIndex((item) => item.id === level);
    if (at < 0 || at === levels.length - 1) return false;
    const select = (key) => this.choose(key);
    if (level === "family") {
      select(view.opened?.key || null);
      return true;
    }
    // Every level above the family: nothing chosen, and nothing open.
    if (view.selected) select(null);
    if (view.opened || view.wanted) view.close({ quiet: level === "species" });
    if (level === "side") return true;
    view.isolate = null;
    if (level === "species") {
      if (view.shelves.several && view.focused !== undefined) view.focusOn(undefined);
      else this.stage.rig.flyTo(this.homeView(), 700);
    }
    this.refresh();
    this.onChrome?.();
    return true;
  }

  /** Choose a part through the page, as a press would: the page's panel, list and address follow. */
  choose(key, options = {}) {
    this.stage.renderer.domElement.dispatchEvent(new CustomEvent("cells-select", { detail: { id: key, ...options }, bubbles: true, composed: true }));
  }

  /** Escape in the atlas: one level of the trail back. Returns whether there was one. */
  escape() {
    if (!this.active || !this.mounted) return false;
    const levels = this.trailLevels();
    return levels.length > 1 && this.goTo(levels[levels.length - 2].id);
  }

  /** The names of a large catalogue's proteins, fetched once from beside its members' files (schema/SPECIES_PROTEINS.md). */
  async loadNames(shelves) {
    if (shelves.kind !== "families" || shelves.names) return true;
    shelves.namesLoading ??= loadBeside(shelvesOf(this.atlas, shelves.id).file.replace(/[^/]*$/, "") + NAMES_FILE)
      .then((file) => (shelves.addNames(file), true))
      .catch((error) => ((shelves.namesError = error.message), false));
    return shelves.namesLoading;
  }

  /** What the search in view finds for a query, with the names fetched first where a large catalogue has them. */
  async searchOwn(query) {
    const shelves = this.mounted?.shelves;
    if (!shelves) return null;
    if (String(query || "").trim().length >= 2) await this.loadNames(shelves);
    if (this.mounted?.shelves !== shelves) return null;
    return shelves.search(query);
  }

  /** Choose what the search found: a protein (its family's members are fetched first, then it opens with the protein chosen), a family's line, or a shelf. */
  async reveal(found) {
    const view = this.mounted, shelves = view?.shelves;
    if (!shelves) return;
    let key = found.key || null;
    if (!key && found.line) {
      // A member of a family not yet open: its line's members are fetched, and the protein is then known by its key.
      const line = found.line;
      await this.loadMembers(shelves, shelves.filesOf(line));
      shelves.membersOf(line);
      key = keyOf(shelves.id, "p", found.id);
    }
    if (key && this.mounted?.shelves === shelves) this.choose(key, { fly: true });
  }

  /** The map of the stack: every shelf with its sides, the one in focus, and the one a family is open on. */
  stackMap() {
    const view = this.mounted, shelves = view.shelves;
    const active = view.focused === undefined ? WHOLE : view.focused ?? NO_SHELF;
    const open = view.opened ? view.opened.shelf ?? NO_SHELF : null;
    return {
      active,
      rows: [
        { id: WHOLE, label: "The whole stack", count: shelves.total, counts: null },
        ...shelves.byShelf.map((entry) => ({ id: entry.id ?? NO_SHELF, label: entry.label ?? "No place known", count: entry.proteins, counts: entry.counts, open: open === (entry.id ?? NO_SHELF) })),
      ],
      most: Math.max(...shelves.byShelf.map((entry) => entry.proteins)),
      whole: shelves.counts,
    };
  }

  /** A press on the map: a shelf comes into focus, or the whole stack. */
  showShelf(id) {
    const view = this.mounted;
    if (!view?.shelves.several) return;
    this.choose(null);
    view.focusOn(id === WHOLE ? undefined : id === NO_SHELF ? null : id);
  }

  /**
   * The keys that move between the shelves of a species with several, when the picture has
   * the keyboard: Page Down to the next shelf, Page Up to the one before, Home to the whole
   * stack. (Escape closes what is open, then leaves the shelf: see back().)
   */
  onKey(event) {
    const view = this.mounted;
    if (!this.active || !view?.shelves.several || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === "PageDown") view.stepShelf(1);
    else if (event.key === "PageUp") view.stepShelf(-1);
    else if (event.key === "Home") view.focusOn(undefined);
    else return;
    event.preventDefault();
  }

  /**
   * Nothing is chosen any more. If what was let go is the open family itself, or nothing was
   * held, the family closes; letting go of one of its proteins leaves it open.
   */
  letGo(held) {
    const view = this.mounted;
    if (!view?.opened) return;
    const item = held ? view.shelves.get(view.shelves.resolve(held) || held) : null; // a key given without its shelf is the family's largest line
    if (!held || item === view.opened || item?.within === view.opened) view.close();
  }

  /** The mark whose values the legend's last block lists. */
  markShown(shelves) {
    const marks = shelves.filterable();
    // A catalogue in families picks out a set only once it is asked for ("show by"): until then the legend's last block is the shelves', or none.
    if (shelves.kind === "families") return marks.find((mark) => mark.id === this.markName) || null;
    return marks.find((mark) => mark.id === this.markName) || marks.find((mark) => mark.id === "essential") || marks[0] || null;
  }

  setMark(name) {
    // A catalogue of one marker each shows a mark by the legend's "Colour" (its "Show by" folded into it).
    // A mark let go of (a door to a shelf asks it) lets go of a value shown alone and keeps the colour chosen.
    if (this.mounted?.shelves.kind === "proteins") {
      this.markName = name;
      this.pickedIds = null;
      if (name) this.setOwnColour(`mark:${name}`);
      else if (this.mounted.mark || this.mounted.basis || this.mounted.isolate) this.stage.renderer.domElement.dispatchEvent(new CustomEvent("cells-isolate", { detail: null, bubbles: true, composed: true }));
      return;
    }
    this.markName = name;
    this.pickedIds = null;
    if (this.mounted) this.mounted.mark = null;
    // A set with one value (the proteins of chemotaxis) is picked out as soon as it is chosen.
    const chosen = this.mounted ? this.markShown(this.mounted.shelves) : null;
    if (chosen?.set && chosen.items.length === 1) this.mounted.mark = { name: chosen.id, value: chosen.items[0].id };
    this.refresh();
    this.onChrome?.();
  }

  /**
   * A part as the page shows it for the species: a unit with the species' side of the atlas
   * and, once the species' own proteins are in, where its products stand among them.
   */
  asShown(entity) {
    const shown = inSpecies(entity, this.atlas, this.page);
    const shelves = entity?.kind === "unit" ? this.ownData() : null;
    const holders = shelves ? shelves.holdersOf(entity.id.replace(/^unit\./, "")) : [];
    if (!holders.length) return shown;
    const items = holders.slice(0, 60).map((item) => ({ id: item.key, label: item.type === "p" ? item.label : `${item.label} · ${number(item.count)}`, swatch: "map-assigned" }));
    const title = shelves.kind === "families" ? `Among ${shelves.label}'s own proteins: the families` : `Among ${shelves.label}'s own proteins`;
    return { ...shown, opens: [{ title, items, more: holders.length - items.length, count: holders.length }] };
  }

  /** A unit as the atlas shown has it (see inSpecies). */
  present(entity) {
    return inSpecies(entity, this.atlas, this.shown);
  }

  /** The switch between species: the page's own, the same control as in the cell view. */
  speciesChoice() {
    // A scene that names no species offers its atlases, once it holds more than one.
    const offered = this.list.length ? this.list : this.atlas.atlases || [];
    return offered.length > 1 ? { options: offered.map((item) => [item.id, item.label, item.organism]), active: this.page } : null;
  }

  /**
   * What the card says of the two things the atlas can show for the species: the switch
   * between them where the species has proteins of its own, and one line where they are
   * being fetched, could not be read, or are not made yet.
   */
  ownChoice() {
    const summary = shelvesOf(this.atlas, this.page);
    const label = this.mounted?.shelves.label || (this.list.find((item) => item.id === this.page) || atlasOf(this.atlas, this.page))?.label || "This species";
    if (!summary) {
      // Said only in a scene that has such proteins for some species: an older scene knows none.
      return { modes: null, notice: this.atlas.shelves?.length ? `${label}'s own catalogue of proteins is not made yet: the atlas shows the units of Cells' law inventory.` : null };
    }
    const state = this.own.get(this.page);
    const modes = { label: "What the atlas shows", options: [["units", `Cells' ${number(this.atlas.counts.units)} units`], ["own", `Its ${number(summary.proteins)} proteins`]], active: this.mode };
    let notice = null;
    if (!this.mounted && state?.status === "loading" && (this.wanted || firstMode(this.atlas, this.page)) === "own") notice = `Fetching ${label}'s own proteins…`;
    else if (state?.status === "failed") notice = `${label}'s own proteins could not be loaded (${state.error}). The atlas shows the units of Cells' law inventory.`;
    return { modes, notice };
  }

  /** What the page says while the species' own proteins are shown: the card, the legend, the caveat. */
  ownChrome() {
    const view = this.mounted, shelves = view.shelves, data = shelves.data;
    const families = shelves.kind === "families", several = shelves.several;
    // Of several shelves the legend's first block counts the sides of the shelf in focus, in
    // that shelf's own words. Of the whole stack it lists none: a side means something else on
    // each shelf, and the legend then lists the shelves themselves (its third block).
    const near = several && view.focused !== undefined ? shelves.byShelf.find((entry) => entry.id === view.focused) || null : null;
    const words = shelves.sideWords(near ? near.id : undefined);
    const total = shelves.total, basis = shelves.byBasis();
    // What holds a protein listed with a unit of Cells' law inventory. With one shelf, its
    // families (or its proteins). With several: the families that do on any shelf, the
    // gatherings of families of one and the groups of "no family" that do, and the markers
    // that are lit for them (Shelves.lawHolders).
    const withUnit = (families ? shelves.families : shelves.proteins).filter((item) => item.units.length).length;
    const holders = families && several ? shelves.lawHolders() : null;
    const lawFamilies = holders ? holders.families : withUnit, lawLone = holders ? holders.lone : 0, lawParts = holders ? holders.parts : 0;
    const lawMarkers = holders ? holders.markers : withUnit;
    const unknown = shelves.counts["not known"];
    const soft = basis.predicted + basis["by function"];
    const counted = !families || Boolean(data.by_basis); // a large catalogue counts its sides by basis in the file, or not at all
    const some = (count, all) => (count === all ? (all === 1 ? "its one" : `all ${number(all)}`) : `${number(count)} of the ${number(all)}`);
    // The legend's first block names what colour carries (docs/ATLAS_LOOK.md, decided 16 November 2026), with the
    // choice at its head: the side of each protein's own membrane, how that side is known, a mark the species
    // states (a small catalogue's "Show by" folded into it), or Cells' law inventory. A press on a value shows it alone.
    const legend = this.colourLegend(shelves, view, near, words, basis);
    // The second: what holds a unit of the law inventory (in families), or how the side is known (one marker each; not
    // while colour itself is that).
    const filter = families
      ? withUnit
        ? { title: "Cells' law inventory", unit: several ? "markers" : "families", items: [{ id: "units", label: "Holds parts of a unit of the law inventory", title: "Families that hold proteins listed with a unit of the law inventory: candidates for its unit, or parts that go with it. No other is listed with a unit of the inventory.", count: lawMarkers }], active: view.units ? "units" : null }
        : null
      : view.colourBy === "basis"
        ? null
        : {
            title: "How the side is known",
            unit: "proteins",
            items: BASES.filter((id) => basis[id]).map((id) => ({ id, label: shelves.basisWords(id).label, title: shelves.basisWords(id).sentence, count: basis[id] })),
            active: view.basis,
          };
    // The third: of a catalogue in families, the values of a set its file lists (E. coli's chemotaxis proteins,
    // its assemblies), chosen by "Show by". The shelves themselves are in the map of the stack (src/ui/atlas_nav.js).
    const marks = families ? shelves.filterable() : [];
    const mark = families ? this.markShown(shelves) : null;
    const findings = mark
      ? {
          title: mark.measured ? `${mark.label}, measured` : mark.label,
          unit: "proteins",
          items: mark.items.map((item) => ({ id: item.id, label: item.label, count: item.count, title: mark.note || "" })),
          active: view.mark?.name === mark.id ? view.mark.value : null,
        }
      : null;
    // The shelf's own name, as the file gives it, and what its sides cover where the file says more than their names.
    // Whether the one shelf says more of its sides than their names.
    const fuller = !several && shelves.shelf.outside !== words.outside.short;
    const shelf = several
      ? `The shelves, one for each membrane the data tells apart: ${shelves.shelves.map((item) => item.label).join("; ")}.`
      : `The shelf: ${shelves.shelf.label}.` + (fuller ? ` ${shelves.shelf.outside}. ${shelves.shelf.inside}.` : "");
    const law = withUnit
      ? families
        ? several
          ? `${[plural(lawFamilies, "family", "families"), lawLone ? `${plural(lawLone, "gathering")} of families of one` : "", lawParts ? `${plural(lawParts, "group")} of proteins with no family` : ""].filter(Boolean).join(", ").replace(/, ([^,]*)$/, " and $1")} hold proteins listed with units of Cells' law inventory. No other protein here is listed with one.`
          : `${number(withUnit)} families hold proteins listed with units of Cells' law inventory: one that makes a unit carries its shape, one that only goes with it is drawn plain. No other protein here is listed with one.`
        : `${number(withUnit)} of them are drawn as a unit of Cells' law inventory. Every other is a plain marker: it is listed with no unit of the inventory.`
      : "None of these proteins is listed with a unit of Cells' law inventory: every one is a plain marker.";
    const sides =
      [
        basis.stated ? `${number(basis.stated)} stated by a curated entry or a paper` : "",
        basis.predicted ? `${number(basis.predicted)} predicted from the sequence` : "",
        basis["by function"] ? `${number(basis["by function"])} taken from what the protein does` : "",
      ]
        .filter(Boolean)
        .join(", ") || "none known";
    const apart = unknown ? ` ${number(unknown)} have no known side: they are set apart, not placed by guess.` : "";
    const notes = Object.entries({ stated: "Stated", predicted: "Predicted", "by function": "By function", none: "Not known" })
      .filter(([id]) => shelves.notes[id])
      .map(([id, label]) => `${label}: ${shelves.notes[id]}`);
    const made = [
      shelf,
      `Sides: ${sides}.${apart}`,
      data.from ? `The catalogue: ${data.from}` : null,
      ...notes,
      // Of several shelves the card itself is kept short, beside the legend's list of shelves: what it leaves out is said here.
      several && families ? `A family has a marker on each shelf that holds members of it, and stands there on the side where most of those members sit. Every line of a family of five or more opens on its own; smaller families are gathered by district and side. "${shelves.noFamily.label}" holds the ${number(shelves.noFamily.count)} proteins that have none, by what else they share.` : null,
      several && families && shelves.loneAll.count ? `Families of one: ${number(shelves.loneAll.count)} families have a single member in this catalogue. Their proteins stand together, by shelf, district and side, in ringed markers that open straight to them; each names its family.` : null,
      data.family_from ? `Families: ${data.family_from}` : null,
      data.no_family?.parts_from ? `No family: ${data.no_family.parts_from}` : null,
      data.groups_from ? `Districts: ${data.groups_from}` : null,
    ].filter(Boolean);
    const opened = view.opened;
    return {
      caveat: view.status
        ? null
        : families
        ? `A round marker is a family of ${shelves.predicted ? "predicted proteins" : "proteins"}: press it to open it. ${shelves.predicted ? "Sides are predictions on predicted proteins." : counted ? `${soft >= total / 2 ? "Most sides" : `${number(soft)} sides`} are predicted or inferred, not measured.` : "Each protein's panel says how its side is known."} ${fuller ? `The shelf: ${lower(shelves.shelf.label)}. ` : ""}${withUnit ? "A drawn shape is a unit of Cells' law inventory; a plain marker is listed with none." : "None of them is listed with a unit of Cells' law inventory."}`
        : `Each marker is one protein of ${shelves.label}, by its side of the membrane. ${soft >= total / 2 ? "Most sides" : `${number(soft)} sides`} are predicted or inferred, not measured. ${fuller ? `The shelf: ${lower(shelves.shelf.label)}. ` : ""}${withUnit ? "A drawn shape is a unit of Cells' law inventory; a plain marker is listed with none." : "None of them is listed with a unit of Cells' law inventory."}`,
      status: view.status || null,
      stamp: `${shelves.label} proteins${data.made ? ` of ${day(data.made)}` : ""} · ${number(total)}`,
      legend,
      filter,
      findings,
      // The trail, the search and the map of the stack (src/ui/atlas_nav.js).
      nav: { trail: this.trailLevels(), species: shelves.id, several, map: several ? this.stackMap() : null, finding: families ? "Gene, protein or family" : "Gene or protein" },
      card: {
        heading: `${shelves.label} proteins`,
        organism: shelves.organism,
        species: this.speciesChoice(),
        ...this.ownChoice(),
        // A family that could not be opened is said on the card too; what is being fetched, under the picture only.
        notice: view.failed ? view.status : null,
        // Of several shelves: the families that open (those with a line), beside the families in all, with those of one member.
        stats: families
          ? several
            ? [[number(total), shelves.predicted ? "proteins, all predicted" : "proteins"], [number(shelves.familyCount), "families that open"], [number(shelves.familiesInAll), "families in all"]]
            : [[number(total), shelves.predicted ? "proteins, all predicted" : "proteins"], [number(shelves.familyCount), "families that open"], [number(shelves.noFamily.count), "with no family"]]
          : [[number(total), "proteins"], [number(shelves.counts.in + shelves.counts.outside), several ? "in a membrane or beyond one" : "in or on the membrane"], [number(withUnit), "with a unit of the law inventory"]],
        open: opened ? { label: opened.label, count: `${number(opened.count)} ${opened.count === 1 ? "protein" : "proteins"}`, id: opened.key } : null,
        text: families
          ? several
            ? `Every protein of the catalogue is here, on ${number(shelves.shelves.length)} shelves: a shelf is a membrane, and a protein stands outside it, in it or inside it. A round marker is a family on that shelf; a ringed one gathers smaller families, or families of one.`
            : `Every protein of the catalogue is here, in families. A round marker is one family, sized by its members: press it and it opens to every one of them. A ringed marker gathers a district's smaller families. "${shelves.noFamily.label}" holds the ${number(shelves.noFamily.count)} that have none, by what else they share.`
          : "Every protein of the catalogue is one marker, in the district of its function: on the membrane if it is outside the cell, through it if it spans it, on the glass below if it is inside.",
        check: families
          ? several
            ? law
            : `${law} ${shelves.predicted ? "Every protein here is itself predicted, and so is its side: a prediction on a predicted protein, not a measurement." : soft ? `The side of ${some(soft, total)} is predicted or taken from what the protein does, not measured.` : ""} A family stands where most of its members sit.${apart}`
          : `${law} ${soft ? `The side of ${some(soft, total)} is predicted or taken from what the protein does, not measured.` : ""}${apart}`,
        // In families the first choice is the plain view (the shelves, or the families); each other picks out a set.
        // A catalogue of one marker each shows its marks by the legend's "Colour" instead.
        marks: families && marks.length ? { label: "Show by", options: [["", several ? "Shelves" : "Families"], ...marks.map((item) => [item.id, item.label])], active: mark ? mark.id : "" } : null,
        method: made,
        sources: shelves.sources.map((source) => {
          const kind = licenceClass(source);
          return { ...source, tag: LICENCE_TAG[kind] || null, tag_title: LICENCE_NOTE[kind] || "" };
        }),
        notCopied: null,
      },
    };
  }

  chrome() {
    if (this.mounted) return this.ownChrome();
    const { atlas } = this;
    const { stamp, counts } = atlas;
    const lost = stamp.found.missing || 0;
    const choice = this.speciesChoice();
    const own = this.ownChoice();
    // A species without a file of its own in the atlas: the units are shown as the inventory has them, and the card says so.
    const lacking = this.page !== this.shown ? this.list.find((item) => item.id === this.page) : null;
    const reference = (atlas.atlases || []).find((item) => item.reference) || null; // the inventory's own side
    // The mapping and the evidence describe the engine's laws: they are the same in every atlas.
    const legend = {
      title: "Mapping",
      items: atlas.mappings.map((item) => ({ id: item.id, label: item.label, description: item.description, count: item.count, swatch: `map-${item.id}` })),
    };
    const filter = {
      title: "Evidence for a law",
      unit: "records",
      items: atlas.evidence.filter((item) => item.count).map((item) => ({ id: item.id, label: item.label, title: item.description, count: item.count })),
      active: this.evidence,
    };
    if (this.species) {
      // Another species: its own counts, sources and findings, beside the engine's unchanged legend.
      const said = speciesWords(atlas, this.species);
      return { ...said, legend, filter, findings: { ...said.findings, active: this.finding }, card: { ...said.card, species: choice, ...own } };
    }
    return {
      caveat: atlas.caveat,
      stamp: `Inventory of ${day(stamp.created)} · engine ${stamp.read_at}`,
      legend,
      filter,
      card: {
        heading: "The units of Cells' law inventory",
        species: choice,
        ...own,
        stats: [[counts.units, "functional units"], [counts.laws, "laws"], [counts.genes, "candidate genes"]],
        organism: lacking ? lacking.organism : undefined,
        text: `${lacking ? `${lacking.label} has no protein atlas yet. The units are shown as the inventory has them, with its own candidate products${reference ? ` (${reference.label})` : ""}. ` : ""}${atlas.summary} The inventory was made on ${day(stamp.created)}, at engine ${stamp.read_at}.`,
        check:
          `${lost ? `${lost} of its ${stamp.records} law records are no longer found` : `All ${stamp.records} of its law records are still found`} at main ${stamp.checked_at}.` +
          (stamp.gained?.added ? ` The engine has gained ${stamp.gained.added} identifiers since, most under ${stamp.gained.where[0][0]}. ${gainedNote(stamp.gained)}` : ""),
        sources: atlas.sources,
        notCopied: atlas.not_copied,
      },
    };
  }

  get pickRoots() {
    return [this.mounted ? this.mounted.group : this.root];
  }

  activate() {
    const { stage } = this;
    // Which of the two is shown for this species; its own proteins are fetched only now, when the view is.
    this.settleMode();
    this.active = true;
    stage.scene.add(this.mounted ? this.mounted.group : this.root);
    stage.sun.castShadow = false;
    stage.sun.position.set(-60, 150, 110);
    stage.sun.target.position.set(0, 0, 0);
    stage.rig.limits = this.rigLimits();
    this.light();
    stage.rig.setView(this.homeView());
    this.buildLabels();
    this.refresh();
    // The picture's own keys, while this view is shown.
    this.keys ??= (event) => this.onKey(event);
    stage.renderer.domElement.addEventListener("keydown", this.keys);
  }

  deactivate() {
    this.active = false;
    if (this.keys) this.stage.renderer.domElement.removeEventListener("keydown", this.keys);
    this.mounted?.reset(); // an open family closes with the view
    this.stage.scene.remove(this.mounted ? this.mounted.group : this.root);
    this.stage.scene.environment = null;
    this.stage.applyPalette(); // back to the stage's own lighting
    this.labels.clear();
  }

  light() {
    const { stage } = this;
    const dark = stage.palette.dark;
    stage.scene.environment = this.environment;
    stage.scene.environmentIntensity = dark ? 0.5 : 0.62;
    stage.sky.intensity = dark ? 1.0 : 1.25;
    stage.sun.intensity = dark ? 1.5 : 1.25;
    this.fill.intensity = dark ? 0.8 : 0.55;
  }

  homeView() {
    if (this.mounted) return this.mounted.home();
    const stage = this.stage, bounds = this.board;
    const half = Math.tan((stage.camera.fov * Math.PI) / 360);
    const wide = bounds.maxX - bounds.minX, deep = bounds.maxZ - bounds.minZ, tall = bounds.maxY - bounds.minY;
    const target = new THREE.Vector3((bounds.minX + bounds.maxX) / 2, -7, (bounds.minZ + bounds.maxZ) / 2 - 2);
    if (stage.width < stage.height * 0.9) {
      // A tall screen looks along the membrane, so its long side runs up the screen.
      const polar = 0.74, across = deep + 66, up = wide * Math.cos(polar) + tall * Math.sin(polar) + 10;
      target.z += 13;
      return { target, distance: Math.max(up / (2 * half), across / (2 * half * stage.camera.aspect)) * 1.04 + wide * 0.2, azimuth: 1.36, polar };
    }
    const polar = 0.98, across = wide + 14, up = deep * Math.cos(polar) + tall * Math.sin(polar) + 34;
    target.y = -11; // leaves room below for the note on the shapes
    return { target, distance: Math.max(up / (2 * half), across / (2 * half * stage.camera.aspect)) * 1.02 + deep * 0.3, azimuth: 0.24, polar };
  }

  buildLabels() {
    const labels = this.labels;
    labels.clear();
    labels.calloutFrame = null;
    if (this.mounted) return this.mounted.buildLabels(labels);
    for (const district of this.districts) {
      district.tag = labels.add({ text: district.label, anchor: district.anchor, priority: 500, kind: "layer label-district", lift: -8 });
    }
    for (const side of this.sides) labels.add({ text: side.text, anchor: side.anchor, priority: 400, kind: "note", lift: 0 });
    for (const node of this.nodes.values()) {
      // Where the species shown differs, the name carries the same sign as the ring beside the unit.
      const sign = this.present(node.entity).sign;
      node.label = labels.add({ id: node.entity.id, text: node.entity.short || node.entity.label, anchor: node.top, priority: sign ? 26 : 20, kind: "part label-unit", lift: 6, swatch: sign?.swatch });
    }
  }

  /** Show one species' atlas. The units, their forms and the engine's laws stay as they are. */
  setAtlas(id) {
    const atlas = atlasOf(this.atlas, id) || atlasOf(this.atlas, defaultAtlas(this.atlas));
    const species = atlas && !atlas.reference ? atlas : null;
    this.shown = atlas?.id ?? null;
    // The species the page shows, also where it has no atlas of its own (the inventory's is then shown).
    const page = this.list.some((item) => item.id === id) || atlasOf(this.atlas, id) || shelvesOf(this.atlas,id) ? id : this.shown;
    const moved = page !== this.page;
    this.page = page;
    if (species !== this.species) {
      this.species = species;
      this.finding = null;
      this.buildMarks();
      if (this.active && !this.mounted) {
        this.buildLabels();
        this.refresh();
      }
    } else if (moved) this.onChrome?.();
    // The units or the species' own proteins: settled now if the view is shown, else when it next is.
    if (moved && this.active) this.settleMode();
  }

  /**
   * A flat ring on the membrane beside each unit where the species shown differs from the
   * inventory's candidates: unbroken for another protein family, broken for nothing found.
   * The ring lies in the scene, outside the unit's own group, so the unit's form (which
   * says what the engine's law names) is left alone. The inventory's own atlas has none.
   */
  buildMarks() {
    for (const mark of this.marks) this.root.remove(mark.mesh);
    this.marks = [];
    this.quiet = quietAtlas(this.atlas, this.species);
    if (!this.species) return;
    const words = new Map((this.atlas.findings || []).map((word) => [word.id, word]));
    for (const node of this.nodes.values()) {
      const kind = words.get(node.entity.species?.[this.species.id]?.finding)?.mark;
      node.faint = this.quiet && Boolean(kind); // a quiet atlas draws the unit faint, and no ring
      if (!kind || this.quiet) continue;
      // Inside the ring of the unit in focus, and clear of the neighbouring units.
      const radius = (node.reach.floats ? node.reach.radius : Math.min(node.reach.radius, 4.3)) + 0.7;
      const mesh = new THREE.Mesh(findingMark(kind, radius), this.markMaterial);
      mesh.position.copy(node.ringAt);
      mesh.position.y -= 0.06;
      mesh.renderOrder = 3;
      mesh.userData.pick = node.entity.id; // a click on the ring picks its unit
      this.root.add(mesh);
      mesh.updateMatrixWorld(); // so it can be picked at once, before the next frame is drawn
      this.marks.push({ mesh, node });
    }
  }

  /** What is in focus: a unit of the board, or a protein or a family of the shelves. Choosing either shows where it stands. */
  setSelection(id) {
    const own = id && !this.nodes.has(id) ? this.ownKey(id) : null;
    if (own) {
      if (!this.mounted) this.enter("own");
      this.mounted?.setSelection(own);
      return;
    }
    if (id && this.nodes.has(id) && this.mounted) this.enter("units");
    this.mounted?.setSelection(null);
    this.selected = id && this.nodes.has(id) ? id : null;
    this.refresh();
  }

  setHover(id) {
    if (this.mounted) return this.mounted.setHover(id);
    const next = id && this.nodes.has(id) ? id : null;
    if (next === this.hovered) return;
    this.hovered = next;
    this.refresh();
  }

  /** Show only the units of one mapping (the legend's first block). */
  setIsolate(mapping) {
    // On the shelves the legend's first block lists what colour carries: the sides of the membrane, how a side is
    // known, or the values of a mark; a press shows those proteins alone.
    const view = this.mounted;
    if (view && view.colourBy === "basis") {
      view.basis = BASES.includes(mapping) ? mapping : null;
      view.isolate = null;
    } else if (view && view.colourBy === "mark" && view.shelves.kind === "proteins") {
      view.mark = mapping !== null && mapping !== undefined ? { name: view.markName, value: String(mapping) } : null;
      view.isolate = null;
    } else if (view) view.isolate = SIDES.includes(mapping) ? mapping : null;
    else this.isolate = mapping || null;
    this.refresh();
    if (view) this.onChrome?.(); // the trail names a side shown alone
  }

  /** Show only the units with a law resting on one kind of evidence (the legend's second block). */
  setTogether(evidence) {
    const view = this.mounted;
    if (view) {
      // On the shelves: how a side is known, or (of families) those holding a unit of the law inventory.
      view.units = evidence === "units";
      view.basis = BASES.includes(evidence) ? evidence : null;
    } else this.evidence = evidence || null;
    this.refresh();
    this.onChrome?.();
  }

  /**
   * Of the set picked out, only some proteins: those a door names (the proteins of one part of
   * a machine, schema/MACHINES.md). The legend's choice of the set stays; choosing again in it
   * picks out the whole set. Returns how many of them the species' own proteins hold.
   */
  pickIds(ids) {
    const view = this.mounted, wanted = ids?.length ? new Set(ids.map(String)) : null;
    this.pickedIds = wanted;
    if (view?.mark) view.mark = wanted ? { ...view.mark, ids: wanted } : { name: view.mark.name, value: view.mark.value };
    this.refresh();
    this.onChrome?.();
    return view?.mark && wanted ? view.shelves.highlightTotal(view.mark.name, view.mark.value, wanted) : 0;
  }

  /** Show only the units for which the species' atlas found one thing (the legend's third block). */
  setFinding(finding) {
    this.pickedIds = null;
    const view = this.mounted, mark = view ? this.markShown(view.shelves) : null;
    if (view && view.shelves.kind === "proteins" && mark) {
      // One marker each: a value of a mark (a door, or the address's "finding=") is shown by colouring by that mark
      // and pressing its value in the legend, so that the legend says what is shown alone and lets go of it.
      if (view.colourBy !== "mark" || view.markName !== mark.id) this.setOwnColour(`mark:${mark.id}`);
      const value = finding !== null && finding !== undefined && mark.items.some((item) => item.id === String(finding)) ? String(finding) : null;
      this.stage.renderer.domElement.dispatchEvent(new CustomEvent("cells-isolate", { detail: value, bubbles: true, composed: true }));
      return;
    }
    if (view && !mark && view.shelves.several && view.shelves.kind === "families") {
      // Of several shelves the block lists the shelves: one comes into focus, or the whole stack does.
      view.focusOn(finding === null || finding === WHOLE ? undefined : finding === NO_SHELF ? null : finding);
    } else if (view) {
      // On the shelves the block lists the values of one mark.
      view.mark = mark && finding !== null && mark.items.some((item) => item.id === String(finding)) ? { name: mark.id, value: String(finding) } : null;
    } else {
      this.finding = this.species && (this.atlas.findings || []).some((word) => word.id === finding) ? finding : null;
      // Asked before the species' own proteins are in (an address opened afresh): it waits for them as well.
      this.waitingFinding = this.wanted === "own" && this.ownState(this.page)?.status === "loading" && finding !== null ? { page: this.page, finding } : null;
    }
    this.refresh();
    this.onChrome?.();
  }

  lit(entity) {
    if (this.isolate && entity.mapping !== this.isolate) return false;
    if (this.evidence && !(entity.evidence || []).includes(this.evidence)) return false;
    if (this.finding && entity.species?.[this.species?.id]?.finding !== this.finding) return false;
    return true;
  }

  refresh() {
    if (this.mounted) return this.mounted.paint();
    for (const [id, node] of this.nodes) {
      const lit = this.lit(node.entity);
      const hot = id === this.selected || id === this.hovered;
      // A unit the species' quiet atlas found nothing for is drawn faint, unless it is in focus.
      const faint = Boolean(this.species && node.faint) && !hot;
      for (const mesh of node.meshes) {
        const set = this.tones.get(mesh.userData.tone);
        mesh.material = lit && !faint ? set.lit : set.dim;
      }
      if (node.label) {
        node.label.boost = hot ? 1000 : 0;
        node.label.hidden = !lit && !hot;
        node.label.element.classList.toggle("is-focus", id === this.selected);
        node.label.element.classList.toggle("is-faint", faint && lit);
      }
    }
    for (const mark of this.marks) mark.mesh.visible = this.lit(mark.node.entity);
    this.mark(this.ring, this.selected);
    this.mark(this.hoverRing, this.hovered && this.hovered !== this.selected ? this.hovered : null);
    this.stage.invalidate();
  }

  mark(ring, id) {
    const node = id ? this.nodes.get(id) : null;
    ring.visible = Boolean(node);
    if (!node) return;
    ring.position.copy(node.ringAt);
    ring.scale.setScalar(node.reach.radius + 1.5);
  }

  focus(id) {
    if (this.mounted) return this.mounted.focus(id);
    const node = this.nodes.get(id);
    if (!node) return;
    const rig = this.stage.rig;
    rig.flyTo({ target: node.group.position.clone().setY(node.group.position.y + 1), distance: Math.min(rig.distance, 78), polar: Math.min(rig.polar, 1.02) }, 1100);
  }

  update(dt) {
    const view = this.mounted;
    if (!view) return false;
    // A window turned or resized across the two shapes: the shelves laid out for the other one.
    if (this.active && view !== this.ownView()) {
      const chosen = view.selected;
      this.enter("own");
      if (chosen) this.mounted?.setSelection(chosen); // what was chosen, and the family it opened, on the new shelves
      return true;
    }
    return view.update(dt);
  }

  applyPalette(palette) {
    const named = new THREE.Color(palette.bioProtein), generic = new THREE.Color(palette.atlasGeneric);
    for (const { spec, lit, dim } of this.tones.values()) {
      const colour = (spec.hue === "named" ? named : generic).clone();
      if (spec.shade > 0) colour.lerp(WHITE, spec.shade);
      else if (spec.shade < 0) colour.lerp(BLACK, -spec.shade);
      lit.color.copy(colour);
      dim.color.copy(colour);
      lit.userData.rim?.uRimColor.value.copy(colour).lerp(WHITE, palette.dark ? 0.35 : 0.65);
    }
    for (const sheet of this.sheets) {
      // On a dark page a membrane this large would glare, so it is drawn deeper there.
      const colour = new THREE.Color(palette[sheet.hue] || palette.ghost);
      sheet.body.color.copy(colour).lerp(BLACK, palette.dark ? 0.45 : 0);
      sheet.body.opacity = palette.dark ? 0.55 : 0.45;
      if (palette.dark) sheet.faces.color.copy(colour).lerp(BLACK, 0.42);
      else sheet.faces.color.copy(colour).lerp(WHITE, 0.3);
    }
    this.lineMaterial.color.set(palette.edge);
    this.dashes.color.set(palette.ghost);
    this.ring.material.color.set(palette.fg);
    this.hoverRing.material.color.set(palette.fg);
    this.markMaterial.color.set(palette.fg);
    for (const state of this.own.values()) for (const view of state.views.values()) view.applyPalette(palette);
    if (this.active) this.light();
    this.stage.invalidate();
  }

  dispose() {
    for (const state of this.own.values()) for (const view of state.views.values()) view.dispose();
    disposeTree(this.root);
    for (const { lit, dim } of this.tones.values()) {
      lit.dispose();
      dim.dispose();
    }
    this.markMaterial.dispose();
    this.environment?.dispose();
  }
}
