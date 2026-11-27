// What the page's panel, list and text page say of the Machines catalogue
// (schema/MACHINE_CATALOGUE.md, "What the view may say"). The shapes are the ones every view
// hands to <cells-panel> and <cells-index>. What Cells models of a machine is said only as a
// record says it: a line of the engine's feature requests, the map's own status of a part, or,
// for the membrane units of the law inventory, the Protein atlas's own panel of the unit.

import { Catalogue, IONS, PREFIX, ORGANELLE, FAMILY, byFamily, kindOf, organelleKind, citeShort } from "./machines_data.js";
import { membraneOf, partsByChains, partOfChain as partOfChainIn, SHELF } from "./machines_layout.js";
import { inSpecies } from "./proteins.js";

/** A swatch for each kind of mark the view draws (machines_styles.js), and one for each group. */
export const SWATCH = { sized: "mach-sized", card: "mach-card", chosen: "mach-chosen", none: "mach-none", organelle: "mach-organelle" };
export const groupSwatch = (group) => `mach-g-${group}`;
/** UniProt's accession numbers, which link to UniProt; a genome's own locus tag does not. */
const ACCESSION = /^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})$/;
const SHOWN = 12; // proteins listed in a panel before "and N more"
const number = (value) => Number(value).toLocaleString("en-US");

const catalogues = new WeakMap();
/** One Catalogue for each scene, shared by the view, its card and the text page. */
export function catalogueOf(scene) {
  if (!scene?.catalogue?.entries && !scene?.catalogue?.benches) return null;
  if (!catalogues.has(scene)) catalogues.set(scene, new Catalogue(scene.catalogue, scene));
  return catalogues.get(scene);
}

/** The organism a species' data is of, as the scene names it (its scientific name). */
const organismOf = (scene, id) => scene?.catalogue?.benches?.[id]?.organism || (scene?.species || []).find((item) => item.id === id)?.organism || (scene?.proteins?.atlases || []).find((item) => item.id === id)?.organism || null;
/** Whether two organisms' names are of one species: their first two words (a strain's name after them does not count). */
const sameOrganism = (a, b) => Boolean(a && b) && a.split(/\s+/).slice(0, 2).join(" ") === b.split(/\s+/).slice(0, 2).join(" ");
/** "<the structure's organism>", and, where the species shown is of another, that none of its own is in hand. */
const elsewhereWords = (organism, of) => (organism && !sameOrganism(organism, of) ? `${of} (one of ${organism}: none in hand)` : of);

export const speciesLabel = (scene, id) => scene?.catalogue?.benches?.[id]?.label || (scene?.species || []).find((item) => item.id === id)?.label || (scene?.proteins?.atlases || []).find((item) => item.id === id)?.label || id;
const uniprotLink = (id) => ({ text: `UniProt ${id}`, url: `https://www.uniprot.org/uniprotkb/${id}/entry` });
const chainItem = (chain) => ({ label: chain.label, detail: chain.organism, links: chain.protein ? [uniprotLink(chain.protein)] : [] });

/**
 * What a size says, in words, with what it rests on. `organism` is the organism of the species shown: where the
 * structure measured is of another, the words say so, and that none of the species' own is in hand.
 */
export function sizeWords(catalogue, size, { organism = null } = {}) {
  if (!size) return null;
  const source = size.sources?.map((key) => citeShort(catalogue.source(key))).join(", ");
  if (size.shape === "measured") {
    const by = (list) => list.map((n) => Number(n).toFixed(1)).join(" by ");
    return [
      `${by(size.whole.across_nm)} nm, the ellipsoid of the same spread as its atoms${size.whole.farthest_nm ? ` (its farthest atoms ${by(size.whole.farthest_nm)} nm)` : ""}.`,
      `The viewer's own measure from Protein Data Bank entry ${size.entry}, a structure of ${size.whose ? size.of : elsewhereWords(organism, size.of)}, with tools/measure_particle.py; the database states no size.`,
      size.whose || "", // the species' file's own words where the structure is another organism's
      size.beside ? `Entry ${size.beside.entry} beside it: ${by(size.beside.across_nm)} nm.` : "",
      size.note ? `Of the entry: ${size.note}.` : "",
      size.modelled ? shareWords(size) : "",
      size.between_nm && size.parts?.length === 2 && !size.chains?.length ? `Its two subunits' centres are ${Number(size.between_nm).toFixed(1)} nm apart.` : "",
      size.membrane && membraneOf(size) ? `${size.membrane.says}: ${membraneOf(size).thick_nm.toFixed(1)} nm.` : "",
      size.outline === "whole"
        ? `Drawn as the whole's ellipsoid among the others; chosen, as each chain's. (${source})`
        : partsByChains(size)
          ? `Drawn as its chains' ellipsoids, each at its measured size, centre and axes, in the colour of the part that holds it: the chains, not the whole, are its outline, and each part's own ellipsoid is its size, in its panel. (${source})`
          : `Drawn as its parts' ellipsoids, each at its measured size, centre and axes: the parts, not the whole, are its outline. (${source})`,
    ].filter(Boolean).join(" ");
  }
  if (size.shape === "ellipsoid") return `${size.across_nm.join(" by ")} nm, as its species' file states it (${size.part}${size.says ? `: ${size.says}` : ""}; ${source}). Drawn as an ellipsoid of those widths.`;
  if (size.shape === "rod") return `${size.long_nm[0]} to ${size.long_nm[1]} nm long (${source}: “${size.text}”). Drawn ${size.long_nm[1]} nm long, the top of the range; its width is ${size.width}.`;
  return null;
}

/** How much of each kind of chain stands in the entry's coordinates, in words. */
function shareWords(size) {
  const [low, high] = size.modelled.map((share) => Math.round(share * 100));
  const range = low === high ? `${low}%` : `${low} to ${high}%`;
  return size.kinds > 1 ? `Of each of its ${size.kinds} kinds of chain, ${range} of the sequence stands in the entry's coordinates.` : `Of its one kind of chain, ${range} of the sequence stands in the entry's coordinates.`;
}

/** The Shape level's number: after Subunits (3), whichever levels before it a machine has. */
export const SHAPE_LEVEL = 4;

/** What a machine's shape is, in the contract's words: whose surface, of which entry, by what definition, at what setting. */
export function shapeWords(surface) {
  const of = `Protein Data Bank entry ${surface.entry}${surface.assembly ? ` (its biological assembly ${surface.assembly})` : ""}`;
  const standard = surface.setting_width_nm;
  const width = surface.width_nm < standard ? surface.width_nm : Number(surface.width_nm).toFixed(1);
  const coarser = surface.width_nm > standard ? `, coarser than the setting's ${Number(standard).toFixed(1)} nm to hold the budget` : "";
  const by = `${surface.by === "parts" ? "each part as one solid, at" : "a chain at"} ${width} nm${coarser}`;
  return `The viewer's own smooth surface of ${of}'s coordinates (${by}), worked out by tools/shape_particle.py: ${surface.definition}. An illustration, not the structure and not a measurement; the Protein Data Bank states no surface.`;
}

/** "Its shape", for a panel: what the shape is, and whose, where the structure is of another organism than the species'. */
export function shapeFact(item, scene, species) {
  const size = item?.size, surface = size?.surface;
  if (!surface) return null;
  // Where the view could not read its file, why (the catalogue keeps the words, so that a unit's panel says it too).
  const failed = catalogueOf(scene)?.shapeWords?.get(surface.file);
  if (failed) return ["Its shape", failed];
  const whose = size.of && !sameOrganism(organismOf(scene, species), size.of) ? ` It is the shape of a structure of ${size.of}, as its size is.` : "";
  return ["Its shape", `${shapeWords(surface)}${whose}`];
}

/** The drawing levels a machine has (a catalogue item): its closer view's file's, or, measured from a structure, an outline and its parts. */
export function levelsOf(item) {
  if (item?.entry?.closer?.levels) return item.entry.closer.levels;
  const size = item?.size;
  if (size?.shape !== "measured") return null;
  const chains = partsByChains(size);
  const levels = [{ id: 1, label: "Outline", says: size.outline === "whole" ? "The whole's ellipsoid, as one outline among the other machines." : chains ? "Its chains, in its group's colour, as one outline among the other machines." : "Its measured parts as one outline among the other machines." }];
  if (size.parts?.length > 1) levels.push({ id: 2, label: "Parts", says: chains ? "Each named part in a colour of its own, drawn as its chains, each at its measured size, centre and axes; a part's own ellipsoid is its size, in its panel." : "Each named part a body of its own, at its measured size, centre and axes." });
  if (size.chains?.length > 1) levels.push({ id: 3, label: "Subunits", says: "Each chain of the entry a body of its own, at its measured size, centre and axes, shaded by its kind." });
  // Where a shape file is published for it (schema/MACHINE_SHAPES.md), a level after the others: the viewer's own surface.
  if (size.surface) levels.push({ id: SHAPE_LEVEL, label: "Shape", says: shapeWords(size.surface) });
  return levels.length > 1 ? levels : null;
}

/** The panel of one measured part of a machine (`machine:<kind>:<part>`), with the way back to the machine. */
export function describePart(catalogue, species, owner, partId, { scene = catalogue?.scene } = {}) {
  const item = catalogue?.item(species, owner), size = item?.size;
  const part = size?.parts?.find((value) => value.id === partId) || size?.chains?.find((value) => value.id === partId);
  if (!part) return null;
  // Its proteins by its dossier: a part's (the genes the overlay groups in it), a chain's (the protein its entity is).
  const rows = new Map((item.entry?.gathered?.proteins || []).map((row) => [row[0], row]));
  const proteins = (part.proteins || []).map((id) => rows.get(id)).filter(Boolean);
  const protein = part.protein ? rows.get(part.protein) || [part.protein, null, ""] : null;
  const holder = size.chains?.includes(part) ? partOfChainIn(size, part) : null;
  const deposited = Boolean(part.organism);
  const by = (list) => list.map((n) => Number(n).toFixed(1)).join(" by ");
  return {
    id: `${owner}:${part.id}`,
    label: part.label,
    kind: "machine part",
    eyebrow: `${item.label} · a part`,
    chips: [{ label: "Illustration", title: deposited ? "Drawn from the measured polymer coordinates" : "An ellipsoid at its measured size, centre and axes: not a structure" }],
    plain: size.parts.includes(part) ? `One of the ${item.label}'s ${size.parts.length} measured parts.` : `One of the ${size.chains.length} chains of the entry the ${item.label} is measured from.`,
    facts: [
      ...(deposited ? [["Source organism", part.organism]] : protein ? [["Its protein", `${protein[1] || protein[0]}, ${protein[2]} (UniProt ${protein[0]}), as its dossier reads the entry's entity ${part.entity}`]] : []),
      ["How big", `${by(part.across_nm)} nm, the ellipsoid of the same spread as its atoms${part.farthest_nm ? ` (its farthest atoms ${by(part.farthest_nm)} nm)` : ""}`],
      ["Where", `Its centre at ${part.centre_nm.map((n) => Number(n).toFixed(1)).join(", ")} nm from the machine's, in the measure's frame`],
      ...(partsByChains(size) && size.parts.includes(part) ? [["Drawn as", `Its ${size.chains.filter((chain) => partOfChainIn(size, chain) === part).length} chains' ellipsoids, in its colour; the size above is the part's own ellipsoid, of the same spread as all its atoms`]] : []),
      ["Measured from", `Protein Data Bank entry ${size.entry}, a structure of ${size.whose ? size.of : elsewhereWords(organismOf(scene, species), size.of)}, by the viewer with tools/measure_particle.py`],
    ],
    sections: deposited && part.protein ? [{ title: "Protein record", count: false, items: [chainItem(part)] }] : proteins.length ? [{ title: "Its proteins", items: proteins.map(gatheredItem) }] : [],
    doors: [
      ...(protein && (!deposited || part.in_atlas) ? [{ label: `Show ${protein[1] || protein[0]} in the Protein atlas`, lens: "proteins", show: "own", find: protein[0] }] : []),
      // A chain's part, where a named part holds it.
      ...(holder ? [{ label: `Its part: ${holder.label}`, lens: "machines", value: `${owner}:${holder.id}` }] : []),
      { label: "Back to the machine", lens: "machines", value: owner },
    ],
  };
}

/** The lines of the record on what Cells models of a machine: each names its record and says only what it says. */
export function recordLines(catalogue, item, scene) {
  const lines = [];
  for (const line of item.kind?.records || []) {
    const own = typeof line === "object" ? line : null;
    const record = catalogue.record(own ? own.ref : line);
    if (!record) continue;
    if (own) {
      lines.push({ label: record.label, detail: own.status, lines: [own.says], source: { path: record.path, where: record.where, revision: record.revision }, own: true });
      continue;
    }
    if (record.map) {
      // The map's own status of the part of the Cell view the organelle is drawn at, read from the scene as it is: its label,
      // its status and its own words, and the files it rests on. Nothing more is said of it here.
      const part = (scene?.entities || []).find((entity) => entity.id === record.map);
      if (!part) continue;
      const status = (scene.statuses || []).find((value) => value.id === part.status);
      const at = item.kind?.drawn_at || item.label.toLowerCase();
      lines.push({ label: `The map: ${part.label}`, detail: status?.label || part.status || "no status", lines: [`The map's own status for “${part.label}”, the part of the Cell view drawn at the ${at}${part.as_of ? `, as of ${part.as_of}` : ""}: ${status?.label || part.status || "no status"}.`, ...(part.plain ? [`In the map's own words: “${part.plain}”`] : [])], sources: (part.sources || []).map((source) => ({ path: source.path, where: source.where || "" })) });
      continue;
    }
    if (record.entity) {
      const part = (scene?.entities || []).find((entity) => entity.id === record.entity);
      if (!part) continue;
      const status = (scene.statuses || []).find((value) => value.id === part.status);
      lines.push({ label: `The map: ${part.label}`, detail: status?.label || part.status || "no status", lines: [`The map's status for the ${part.label.toLowerCase()} of the Cell view${part.as_of ? `, as of ${part.as_of}` : ""}, which rests on ${record.path.replace(/^visualizer\//, "")} (${record.where}).`], source: { path: record.path, where: record.where } });
      continue;
    }
    const named = item.kind.absent_as && (record.names_absent || []).includes(item.kind.absent_as);
    lines.push({
      label: record.label,
      detail: record.status,
      lines: [named ? `It names the ${item.kind.absent_as} among the machines the engine has no model of.` : "It asks for molecular machines in general and does not name this one: it is not on the engine's plan."],
      source: { path: record.path, where: record.where, revision: record.revision },
    });
  }
  return lines;
}

/** The doors from a machine into the other views: the Protein atlas on its proteins, the Cell view where it sits, its closer view. */
export function doorsOf(item, scene, species) {
  const doors = [];
  if (item.organelle) {
    // (The Cell view's panel of the part offers the way back: doorsFor.)
    const part = item.kind?.map_part && (scene?.entities || []).find((entity) => entity.id === item.kind.map_part);
    return part ? [{ label: "Show where it is drawn in the cell", lens: "cell", select: part.id }] : [];
  }
  if (item.unit) {
    doors.push({ label: "Show it in the Protein atlas", lens: "proteins", show: "units", select: item.unit.id });
    return doors;
  }
  const proteins = item.entry?.proteins;
  const summary = (scene?.proteins?.shelves || []).find((shelf) => shelf.id === species);
  const offered = proteins && (summary?.sets?.[proteins.mark] || []).some((value) => String(value) === proteins.value);
  if (offered) doors.push({ label: `Show its ${number(proteins.items.length)} proteins in the Protein atlas`, lens: "proteins", show: "own", mark: proteins.mark, value: proteins.value });
  if (item.entry?.structures) {
    const deposited = [...new Set(item.size.chains.filter((chain) => chain.in_atlas).map((chain) => chain.protein))];
    if (deposited.length) doors.push({ label: "Find the deposited proteins in the Protein atlas", lens: "proteins", show: "own", ids: deposited });
    const entry = (scene?.models || []).find((model) => model.view?.machine_bench === species);
    if (entry) doors.push({ label: "Return to the 3D organism view", lens: "cell", entry: entry.id });
  }
  if (item.entry?.closer) doors.push({ label: "Look closer in the cell", lens: "cell", look: "closer", machine: item.entry.id });
  else if (item.kind?.cell_part && (scene?.entities || []).some((entity) => entity.id === item.kind.cell_part)) doors.push({ label: "Show where it sits in the cell", lens: "cell", select: item.kind.cell_part });
  return doors;
}

/** The proteins the species' data marks with a machine, as panel items with links to UniProt where the id is an accession. */
function proteinItems(proteins) {
  return proteins.items.slice(0, SHOWN).map(([id, gene, label]) => ({ label: gene || id, detail: [label, gene ? id : null].filter(Boolean).join(" · "), links: ACCESSION.test(id) ? [{ text: `UniProt ${id}`, url: `https://www.uniprot.org/uniprotkb/${id}/entry` }] : [] }));
}

/** The tiers of a machine's proteins in its dossier (schema/MACHINE_DOSSIERS.md), each as its panel says it. */
const TIERS = [
  ["part", "Its parts, held by the structure"],
  ["part by keyword", "Its parts by UniProt's keyword, not held by the structure"],
  ["named", "Named with it by the Gene Ontology alone"],
];

/** A protein of a dossier's rows as a panel item: its gene, its name and accession, and its UniProt entry. */
const gatheredItem = ([id, gene, label]) => ({ label: gene || id, detail: [label, id].filter(Boolean).join(" · "), links: ACCESSION.test(id) ? [{ text: `UniProt ${id}`, url: `https://www.uniprot.org/uniprotkb/${id}/entry` }] : [] });

/** All of the archive results remain accessible without loading their coordinates into the viewer. */
function structureItem(row, reference) {
  const method = { "X-RAY DIFFRACTION": "X-ray diffraction", "SOLUTION NMR": "Solution NMR", "ELECTRON MICROSCOPY": "Electron microscopy" }[row.method] || row.method;
  return {
    label: `PDB ${row.id}`, tag: reference ? "Shown in 3D" : null,
    detail: row.title,
    lines: [[method, row.resolution_A && `${row.resolution_A.toFixed(2)} Å`].filter(Boolean).join(" · "),
      ...(row.partner_organisms?.length ? [`Partner source: ${row.partner_organisms.join(", ")}`] : [])],
    links: [{ text: "Open in RCSB PDB", url: `https://www.rcsb.org/structure/${row.id}` }],
  };
}

/**
 * A number per cell from an open paper: the paper's own number as it writes it (with its power of ten), what it counts, in
 * what cell (each condition its own), the paper and where in it, and whom it cites where it gives another's number.
 */
const perCellWords = (catalogue, number) => `${number.written || Number(number.value).toLocaleString("en-US")} ${number.unit}: ${number.counts}, in ${number.cell} (${citeShort(catalogue.source(number.source))}, ${number.where}${number.cites ? `; it cites ${number.cites}` : ""})`;

/** What a search for candidates by family found for each part of the reference's machine, in the dossier schema's words. */
const LOOKED = {
  candidates: "by its narrowest family (or a broader one)",
  "not in the table": "not in the table: no line of the species' table carries its family, which says what the table holds, not that the species lacks the protein",
  "cannot tell": "cannot tell: the table's scan is older than its family",
  "no family signature": "no family signature to look for",
};

/** A file of the tree that a source's words name in brackets: `(data/…)`. */
const TREE_FILE = /\s*\(((?:data|schema)\/[^)\s]+)\)/;
/** A source as a panel lists it: its short name (a file of the tree in words), its licence and class, and its link. */
const sourceItem = (source) => ({ label: citeShort(source).replace(TREE_FILE, ""), detail: `${source.licence}${source.class ? `, ${source.class}` : ""}`, links: source.doi ? [{ text: `doi:${source.doi}`, url: `https://doi.org/${source.doi}` }] : source.url ? [{ text: source.url, url: source.url }] : [] });
/** The heading and the caveat of what a species' dossier looked for by family and found no candidate for. */
export const NONE_FOUND = "Looked for by family, no candidate found";
export const noneFoundNote = (where) => `Each was looked for in ${where}'s table by the InterPro families of its reference machine's parts, and no candidate was found. This says what ${where}'s table holds, not that ${where} lacks the machine; none of them is on ${where}'s bench.`;

/**
 * What a dossier by family looked for (schema/MACHINE_DOSSIERS.md), in its counts, from its rows part by part: the
 * species' candidates, the parts they stand for, and the parts whose family no line of the species' table carries, those
 * the table cannot tell of, and those with no family to look for. The dossier's own sentence gives the same numbers.
 */
export function lookedFor(gathered, where, reference) {
  const rows = gathered.looked_for || [], many = (test) => rows.filter(test).length;
  const parts = (n) => `${number(n)} ${n === 1 ? "part" : "parts"}`;
  const held = many(([, tier]) => tier === "part"), found = (row) => row[2] === "candidates", proteins = (gathered.proteins || []).length;
  const none = many((row) => row[2] === "no family signature");
  return [
    proteins
      ? `${number(proteins)} of ${where}'s proteins ${proteins === 1 ? "is a candidate, by its" : "are candidates, by their"} InterPro family, for ${number(many(found))} of the ${parts(rows.length)} of ${reference}'s machine${held < rows.length ? ` (${number(many((row) => row[1] === "part" && found(row)))} of the ${number(held)} its entry holds)` : ""}.`
      : `No protein of ${where}'s table is a candidate, by its InterPro family, for any of the ${parts(rows.length)} of ${reference}'s machine.`,
    `For ${parts(many((row) => row[2] === "not in the table"))} no line of ${where}'s table carries the family, which says what the table holds, not that ${where} lacks the protein; for ${number(many((row) => row[2] === "cannot tell"))} the table cannot tell, its scan being older than the family; ${number(none)} ${none === 1 ? "has" : "have"} no family to look for.`,
  ].join(" ");
}

/** The head of the list of a kind's forms (the Complex Portal's entries that stand beneath it), and how many stand before the rest open by a press. */
export const FORMS_TITLE = "Forms the Complex Portal curates";
const FORMS_SHOWN = 4;
const PORTAL_PAGE = "https://www.ebi.ac.uk/complexportal/complex/";

/** An entry's stoichiometry as the Complex Portal gives it (the dossier's compact form), in words; null where it gives none. */
export function stoichiometryWords(stoichiometry, geneOf = new Map()) {
  if (!stoichiometry) return null;
  const copies = (n) => `${number(n)} ${n === 1 ? "copy" : "copies"}`;
  const parts = [`${number(stoichiometry.n_most)} ${stoichiometry.n_most === 1 ? "protein" : "proteins"} at ${copies(stoichiometry.most)} each`];
  if (stoichiometry.except?.length) parts.push(stoichiometry.except.map(([id, n]) => `${geneOf.get(id) || id} at ${copies(n)}`).join(", "));
  if (stoichiometry.not_given) parts.push(`no count given for ${number(stoichiometry.not_given)}`);
  return `Stoichiometry, as the Complex Portal gives it: ${parts.join("; ")}.`;
}

/** The evidence line of a form: the Complex Portal's own term, then one plain line; an inferred entry names the species it is taken from. */
export function evidenceWords(code, template, inferred) {
  const from = (inferred || []).map(([id, of]) => of || `another species (its entry ${id})`);
  const names = [...new Set(from)];
  const where = names.length ? names.join(" and ").replace(/, (?=[^,]*$)/, " and ") : "another species, which its record does not name";
  return `Evidence ${code}. ${String(template).replace("{from}", where)}`;
}

/** The forms beneath a kind, as a panel list: a line for each entry, with its page at the Complex Portal. */
function formsSection(forms, where, geneOf) {
  return {
    title: FORMS_TITLE,
    note: `Entries of the Complex Portal whose proteins are, at least 80 per cent of them and at least two, parts of this machine in ${where}'s dossier. A form is not a machine of its own: it is no mark on the bench and in no count of machines. An entry may hold only some of the machine's parts, and says how many. Where an entry's stoichiometry differs from a count this panel shows, both stand, each with its source; the page reconciles nothing. The first ${FORMS_SHOWN} stand; the rest open by a press.`,
    shown: FORMS_SHOWN,
    items: forms.items.map(([id, name, proteins, held, of, stoichiometry, evidence, inferred]) => ({
      label: name,
      detail: `${id} · ${number(proteins)} ${proteins === 1 ? "protein" : "proteins"} · holds ${number(held)} of this machine's ${number(of)} parts`,
      lines: [stoichiometryWords(stoichiometry, geneOf), evidenceWords(evidence, forms.evidence[evidence], inferred)].filter(Boolean),
      links: [{ text: `Complex Portal ${id}`, url: `${PORTAL_PAGE}${id}` }],
    })),
  };
}

/** One vault sentence's evidence, as UniProt marks it. */
/** Whose protein a sentence "by similarity" names, where a saved file says: "the human protein Q14764", else "the protein of <organism> <accession>". */
const whose = (id, of, scene) => {
  const label = (scene?.species || []).find((item) => item.organism === of)?.label;
  return label ? `the ${label.toLowerCase()} protein ${id}` : of ? `the protein of ${of} ${id}` : id;
};
const similarTo = (lines, scene) => asList([...new Set(lines.flatMap((line) => (line.similar_to || []).map((id) => whose(id, line.similar_of?.[id], scene))))]);
const lineEvidence = (line, scene) => (line.evidence === "by similarity" ? `by similarity${line.similar_to?.length ? ` to ${asList(line.similar_to.map((id) => whose(id, line.similar_of?.[id], scene)))}` : ""}` : line.evidence === "cited" ? `cites ${line.publications.map((id) => `PubMed:${id}`).join(", ")}` : "carries no note of its own");
const quoted = (statement) => `“${statement.quote}” (${statement.place})`;
const asList = (items) => items.join(", ").replace(/, (?=[^,]*$)/, " and ");

/**
 * How one protein of the vault stands, in words, on the footing it stands on: by the record (a member of the Complex
 * Portal's entry), named by a reviewed UniProt entry (every sentence by similarity, or some citing publications), or a candidate by
 * its family. The footings are never mixed, and only the record says part.
 */
export function vaultFooting(id, row, vault, where, scene = null) {
  const lines = row.entry?.lines || [];
  const out = [];
  const portal = vault.reference_portal;
  if (row.tier === "part by record") {
    const copies = row.copies;
    out.push(`By the record: a member of the Complex Portal's entry ${portal.id}, “${portal.name}” (${copies ? `${number(copies)} copies stated` : "no number of copies stated"}; its evidence ${portal.evidence}, put together by the Complex Portal's curators from the literature).`);
  }
  if (lines.length) {
    const similar = lines.filter((line) => line.evidence === "by similarity"), cited = lines.filter((line) => line.evidence === "cited");
    const to = similarTo(similar, scene);
    if (row.tier === "named by a reviewed entry, by similarity") {
      out.push(`Named by a reviewed entry, by similarity: UniProt's reviewed entry ${id} names the vault particle in ${number(lines.length)} sentences of its own, every one marked “by similarity” to ${to}. This is a footing of its own, firmer than a family alone and weaker than a record; it does not make the protein a part of the vault.`);
    } else if (row.tier === "named by a reviewed entry, citing publications") {
      out.push(`Named by a reviewed entry: UniProt's reviewed entry ${id} names the vault particle in ${number(lines.length)} sentences of its own; ${number(cited.length)} ${cited.length === 1 ? "cites" : "cite"} publications${similar.length ? ` and ${number(similar.length)} are marked “by similarity” to ${to}` : ""}. Those are the entry's lines, with the evidence each carries; the page reads none of the papers and does not call the protein a part.`);
    } else {
      out.push(`UniProt's reviewed entry ${id} also names the vault particle in ${number(lines.length)} sentences of its own, each with the evidence it carries.`);
    }
    for (const line of lines) out.push(`${line.comment.toUpperCase()}: “${line.says}” (${lineEvidence(line, scene)})`);
  }
  // Its entry may also make it a component of another complex (TEP1, of telomerase): said as the entry says it, with its evidence.
  for (const line of row.entry?.also || []) out.push(`Its entry also names it a component of another complex, ${line.comment.toUpperCase()}: “${line.says}” (${lineEvidence(line, scene)})`);
  if (row.tier === "candidate by family") {
    out.push(`A candidate by its family: it carries ${asList(row.marks || [])}${row.marks?.includes(vault.signatures.family) ? ", the signature of the major vault protein family" : ", the marker domain of PARP4"}. A candidate is a candidate: it is not called a part of the vault, and nothing in ${where}'s data says it is in one.`);
  }
  return out;
}

/** The three sizes of the vault side by side, each with its source, none hidden. */
function vaultSizes(vault, sizeLine, scene) {
  const portal = vault.reference_portal;
  const ofSpecies = speciesLabel(scene, portal?.species).toLowerCase();
  const by = (list) => list.map((n) => Number(n).toFixed(1).replace(/\.0$/, "")).join(" by ");
  const statement = (id) => vault.preprint.statements.find((value) => value.id === id);
  return [
    portal?.size_nm ? `The Complex Portal's entry ${portal.id} (the ${ofSpecies} vault): ${by(portal.size_nm)} nm${portal.mass_MDa ? `, about ${portal.mass_MDa} MDa` : ""}.` : null,
    statement("mammal-size") ? `The preprint, for mammalian vaults: ${quoted(statement("mammal-size"))}.` : null,
    sizeLine ? `The viewer's measure of a structure: ${sizeLine}` : null,
  ].filter(Boolean).join(" ");
}

/** The vault's passage on the preprint, in one piece: what it is, what it reports, each number with its place, and what is not known. */
export function preprintWords(vault) {
  const preprint = vault.preprint, find = (id) => preprint.statements.find((value) => value.id === id);
  return `${preprint.text} (${preprint.licence.split(",")[0]}), reports that relatives of the major vault protein from phages and some bacteria form vault-like particles when they are made in a host bacterium: it says ${quoted(find("host"))}, ${quoted(find("survey"))}, and reports ${quoted(find("eight"))}. Of one phage relative, L05, it reports ${quoted(find("shell"))} at a ${quoted(find("resolution"))}. It calls the family rare, ${quoted(find("rare"))}. Whether such particles form in the organisms themselves, and what they do, is not known: ${quoted(find("not-established"))}. No prokaryotic vault stands on any bench as a species' machine: the particles were made in that host from other organisms' genes. Nothing of the preprint's figures is drawn.`;
}

/** The panel of the vault (a kind with an identity of its own: the Gene Ontology has no term for it): each footing in its own words. */
function describeVault(catalogue, species, item, scene, level) {
  const entry = item.entry, kind = item.kind, vault = entry.gathered.vault, gathered = entry.gathered;
  const group = catalogue.groupById.get(item.group), where = speciesLabel(scene, species);
  const rows = Object.entries(vault.proteins);
  const records = recordLines(catalogue, item, scene);
  const levels = levelsOf(item);
  const portal = vault.reference_portal;
  const named = [];
  if (vault.footings.record) named.push(`By the record: the Complex Portal's entry ${portal.id}, “${portal.name}”, lists ${asList(rows.filter(([, row]) => row.tier === "part by record").map(([id, row]) => `${row.entry?.gene || id}${row.copies ? ` (${number(row.copies)} copies)` : " (no number of copies given)"}`))} and ${number(portal.others.length)} vault RNAs, named by their RNAcentral identifiers (${portal.others.join(", ")}); RNAcentral itself is not read. UniProt's reviewed entries for the same proteins state the particle in lines of their own, each with the experiment or the similarity it cites.`);
  if (vault.footings.entry) {
    const accessions = rows.filter(([, row]) => row.tier.startsWith("named by a reviewed entry")).map(([id]) => id);
    if (accessions.length) named.push(`Named by a reviewed entry, by similarity or with citations: UniProt's reviewed ${accessions.length === 1 ? "entry" : "entries"} ${asList(accessions)} name the vault particle in their own lines, each line with the evidence it carries (below). That is firmer than a family alone and weaker than a record; the proteins are not called parts.`);
  }
  if (vault.footings.family) {
    const candidates = rows.filter(([, row]) => row.tier === "candidate by family").map(([id, row]) => `${row.entry?.gene || id} (${asList(row.marks || [])})`);
    named.push(`By family alone: ${asList(candidates)} ${candidates.length === 1 ? "carries" : "carry"} the signature of the major vault protein family (${vault.signatures.family}) or PARP4's marker domain (${vault.signatures.parp4}), as marked. A candidate is a candidate. A signature not found is not an absence: ${where}'s table was looked in, and that says what it holds.`);
  }
  const facts = [["Named by", named.join(" ")]];
  const hedge = rows.flatMap(([, row]) => row.entry?.lines || []).find((line) => /may play a role/.test(line.says));
  facts.push(["What it does", `Not known. ${hedge ? `UniProt's own lines are hedged: “${(/(which is [^()]*may play a role[^()]*)/.exec(hedge.says) || [, hedge.says])[1].trim()}”. ` : ""}The preprint says ${quoted(vault.preprint.statements.find((value) => value.id === "function"))}.`]);
  const perCell = vault.preprint.statements.find((value) => value.id === "per-cell");
  facts.push(["How many", species === vault.reference_portal?.species && perCell ? `${quoted(perCell)}: a prediction the preprint cites from another work, not a measured count.` : "No count in hand for this species"]);
  const own = vault.structure.own;
  const sizeLine = sizeWords(catalogue, item.size, { organism: null });
  facts.push(["How big", [vaultSizes(vault, sizeLine, scene), "None of the three is hidden; they differ in what they measure."].join(" ")]);
  if (shapeFact(item, scene, species)) facts.push(shapeFact(item, scene, species));
  if (!own && item.size) {
    const kept = vault.structure.left_out;
    facts.push(["A structure of its own", `Of the ${vault.structure.entries_read} vault-related entries of the Protein Data Bank read on ${vault.structure.asked}, ${kept.length ? `the ones of ${where}'s own organism are ${asList(kept.map((value) => value.entry))}, ${kept.length === 1 ? "which is a fragment or a part" : "which are fragments or parts"} of the particle, none taken for it` : `none is of ${where}'s own organism`}. The size and shape are those of a vault of the ${speciesLabel(scene, vault.reference_portal?.species).toLowerCase()}, measured from Protein Data Bank entry ${item.size.entry.split("-assembly")[0]}${gathered.proteins?.length ? `; ${where}'s protein rests on the footing said above` : ""}.`]);
  }
  facts.push(["A preprint on prokaryotic vaults", preprintWords(vault)]);
  facts.push(["Its proteins", `${number(rows.length)} in ${where}'s table, each on its own footing (below)${gathered.in_atlas ? "; every one is in the Protein atlas" : ""}`]);
  const geneOf = (id, row) => row.entry?.gene || gathered.proteins.find((value) => value[0] === id)?.[1] || id;
  const items = rows.map(([id, row]) => {
    const info = gathered.proteins.find((value) => value[0] === id) || [id, null, ""];
    return { label: geneOf(id, row), detail: [info[2], id, row.tier].filter(Boolean).join(" · "), lines: vaultFooting(id, row, vault, where, scene), links: ACCESSION.test(id) ? [{ text: `UniProt ${id}`, url: `https://www.uniprot.org/uniprotkb/${id}/entry` }] : [] };
  });
  // Where the record gives a number of copies of one of its proteins and that protein's own reviewed entry gives another, both stand
  // on that protein's line, each in its source's words (the dossier finds the protein by the record's own name for it).
  const said = portal?.copies_said;
  if (said?.protein && vault.footings.record) {
    items.find((value) => value.links[0]?.text === `UniProt ${said.protein}`)?.lines.push(`Copies of ${said.of} in a vault, two curated sources: the Complex Portal's entry says “${said.says}”${said.entry ? `; UniProt's entry says “${said.entry.says}”` : ""}. Both stand, each in its source's words; the page reconciles nothing.`);
  }
  const sections = [
    { title: "What Cells models of it", note: "Only what a record says.", items: records.map(({ label, detail, lines }) => ({ label, detail, lines })) },
    { title: "Its proteins, each on its own footing", note: "Three footings, never mixed: by the record, named by a reviewed UniProt entry, and by family alone. Only the record says part.", items },
    vault.structure.left_out.length && !own ? { title: `Entries of ${where}'s own that are not the particle`, items: vault.structure.left_out.map((value) => ({ label: `PDB ${value.entry}`, detail: `“${value.title}”`, lines: [value.why] })) } : null,
    levels ? { title: "How it is drawn", items: levels.map((value) => ({ label: `${value.id}. ${value.label}${value.id === level ? " (shown)" : ""}`, lines: [value.says] })) } : null,
  ].filter((section) => section?.items?.length);
  const keys = [...(item.size?.sources || []), ...(gathered.vault.sources || []), vault.preprint.source].filter((key, index, all) => key && all.indexOf(key) === index);
  sections.push({ title: "Sources and licences", items: keys.map((key) => catalogue.source(key)).filter(Boolean).map(sourceItem) });
  const doors = [...doorsOf(item, scene, species), ...rows.filter(([id]) => (gathered.proteins.find((value) => value[0] === id))).slice(0, 4).map(([id, row]) => ({ label: `Show ${geneOf(id, row)} in the Protein atlas`, lens: "proteins", show: "own", find: id }))];
  return {
    id: item.id, label: item.label, kind: "machine", eyebrow: `${group?.label || "Machines"} · ${where}`, swatch: item.sized ? SWATCH.sized : SWATCH.card,
    chips: [{ label: "Illustration", title: "Drawn as a simple shape from a published size, or as a card where no size is in hand: not a structure, and not a run" }, { label: item.sized ? "Drawn to scale" : "No size in hand" }, { label: "Function not known", title: "UniProt's lines are hedged and the preprint says the function remains unknown" }],
    plain: kind.plain,
    note: records.length ? `What Cells models of it: ${records.map((line) => `${line.label.split(",")[0]}: ${line.detail}`).join("; ")}.` : null,
    facts, sections, doors,
    sources: [...records.map((line) => line.source).filter(Boolean), { path: "visualizer/data/catalogue/catalogue.json", where: "generated by visualizer/tools/build_catalogue.py" }],
    keywords: [kind.plain, ...(gathered.proteins || []).map(([pid, gene]) => `${pid} ${gene || ""}`)].join(" "),
  };
}

/**
 * What an organelle's size says, in words: the fact of its species' file whole (which names the cell type and species the
 * paper measured), its source, and the width the shelf draws it at. A range is drawn at its middle, and says so.
 */
export function organelleSizeWords(catalogue, size) {
  if (!size) return null;
  const source = size.sources?.map((key) => citeShort(catalogue.source(key))).join(", ");
  const middle = (values) => (values.length > 1 ? (values[0] + values[values.length - 1]) / 2 : values[0]);
  const range = (values) => (values.length > 1 ? ", the middle of the range" : "");
  const um = (value) => `${Number(value.toPrecision(3))} µm`;
  // What the number is, where the model takes it as another measure (a sheet's bilayer separation drawn as its thickness).
  const what = size.what ? `: ${size.what}` : "";
  const drawn = size.shape === "sphere" || size.shape === "lens" ? `Drawn ${um(middle(size.across_um))} across${range(size.across_um)}${what}.`
    : size.shape === "sheet" ? `Its sheets are drawn ${Number(middle(size.thick_nm).toPrecision(3))} nm thick${range(size.thick_nm)}${what}.`
    : size.shape === "stack" ? `Its widest cisterna is drawn ${um(middle(size.across_um))} across${range(size.across_um)}${what}.`
    : size.shape === "capsule" ? `Drawn ${um(middle(size.across_um))} across${range(size.across_um)} and ${um(middle(size.long_um))} long${range(size.long_um)}${what}.`
    : "";
  // A size held in the project's files (a paper under a non-commercial licence: the owner's ruling of 20 November 2026): the page says
  // the size drawn and its basis in words, never the paper's numbers or name; a permissive source's measure, where there is one, beside it.
  if (size.held) return [`Drawn about ${um(middle(size.across_um))} across${size.long_um ? ` and ${um(middle(size.long_um))} long` : ""}, ${size.words}, on a published measurement that the project's files cite and this page does not show.`, size.text ? `What a permissive source says: ${size.text} (${source}).` : "", size.why || ""].filter(Boolean).join(" ");
  return `${size.text.charAt(0).toUpperCase()}${size.text.slice(1)} (${source}). ${drawn}`.trim();
}

/**
 * The panel of an organelle on the shelf (schema/MACHINE_CATALOGUE.md, "Organelles"): what it is, what names it in the
 * species' file, how big (the file's fact whole, with the cell type the paper measured), how it is drawn (the Cell view's
 * own model, at that size: `drawn`, from the view), what the map says Cells models of it, and its door into the cell.
 */
function describeOrganelle(catalogue, species, item, scene, { drawn = null } = {}) {
  const entry = item.entry, kind = item.kind, where = speciesLabel(scene, species);
  const group = catalogue.groupById.get(item.group);
  const records = recordLines(catalogue, item, scene);
  const facts = [];
  if (entry.named?.text) facts.push(["Named by", entry.named.text]);
  facts.push(["How big", organelleSizeWords(catalogue, item.size) || entry.no_size || "No size in hand: it stands on the shelf as a card, not a shape"]);
  if (drawn) facts.push(["How it is drawn", drawn]);
  const sources = [...(item.size?.sources || [])].filter((key, index, all) => all.indexOf(key) === index);
  return {
    id: item.id,
    label: item.label,
    kind: "organelle",
    eyebrow: `${group?.label || "Organelles"} · ${where}`,
    swatch: item.sized ? SWATCH.organelle : SWATCH.card,
    chips: [{ label: "Illustration", title: item.sized ? "The Cell view's model of it where there is one, else a simple model of its own, at a size this panel gives with its source (a measurement in one cell type, or a general figure): not a structure, and not a run" : "A card on the shelf: no size in hand, so not to scale; not a structure, and not a run" }, { label: item.sized ? "Drawn to scale" : "No size in hand" }],
    plain: kind.plain,
    note: records.length ? `What Cells models of it: ${records.map((line) => `${line.label}: ${line.detail}`).join("; ")}.` : "No part of the map stands at it, so nothing is said here of what Cells models of it.",
    facts,
    sections: [
      { title: "What Cells models of it", note: "Only what the map says of the part of the Cell view it is drawn at.", items: records.map(({ label, detail, lines }) => ({ label, detail, lines })) },
      { title: "Sources and licences", items: sources.map((key) => catalogue.source(key)).filter(Boolean).map(sourceItem) },
    ].filter((section) => section.items.length),
    doors: doorsOf(item, scene, species),
    sources: [...records.flatMap((line) => line.sources || []), item.size?.held ? { path: `visualizer/${item.size.file}`, where: "the measurement this size rests on, cited and held there" } : null, entry.named?.file ? { path: `visualizer/${entry.named.file}`, where: "cell.parts" } : null, { path: "visualizer/data/catalogue/catalogue.json", where: "generated by visualizer/tools/build_catalogue.py" }].filter(Boolean),
    keywords: [kind.plain, group?.label].filter(Boolean).join(" "),
  };
}

/** The panel of a machine of the species shown, by its page id; null for an id the catalogue does not hold. */
export function describe(catalogue, species, id, { scene = catalogue?.scene, level = null, drawn = null } = {}) {
  if (!catalogue || !id) return null;
  const item = catalogue.item(species, id);
  if (!item && organelleKind(id)) return null;
  if (!item) return elsewhere(catalogue, species, id, scene);
  if (item.organelle) return describeOrganelle(catalogue, species, item, scene, { drawn });
  const group = catalogue.groupById.get(item.group);
  const where = speciesLabel(scene, species);
  if (item.unit) {
    // A unit of the law inventory: the Protein atlas's own panel of the unit, for this species, with the way into the atlas.
    const shown = inSpecies(item.unit, scene?.proteins, species);
    const base = { ...shown, eyebrow: `${group?.label || "Machines"} · ${item.unit.eyebrow || "unit"}`, doors: [...(shown.doors || []), ...doorsOf(item, scene, species)] };
    if (!item.size) return { ...base, swatch: SWATCH.card, note: "A unit of the law inventory, and a protein assembly. The panel says what the inventory states of its laws, as the Protein atlas does. No size of it is in hand, so it is a card, not a shape." };
    // Measured from a structure: of its own kind, or, where the species' atlas finds it built from another family, of that family.
    const other = species !== catalogue.reference && item.unit.species?.[species]?.finding === "different family";
    const levels = levelsOf(item);
    return {
      ...base,
      // The atlas's own line for such a species says the shape drawn is of the family the engine's law names: there it is. Here
      // the shape is of the family this species has, so the line says that.
      ...(other && base.finding?.more ? { finding: { ...base.finding, more: "The description above, the assembly and the reference structures belong to the family the engine's law names. The shape drawn here is of the family this species has." } } : {}),
      swatch: SWATCH.sized,
      chips: [...(base.chips || []), { label: "Drawn to scale", title: "An ellipsoid of each body at its measured size, from a structure: an illustration, not the structure" }],
      note: `A unit of the law inventory, and a protein assembly. The panel says what the inventory states of its laws, as the Protein atlas does. It is drawn to scale from the viewer's own measure of a structure${other ? ` of the family ${where}'s atlas finds it built from` : " of its own kind"}: an illustration, not the structure.`,
      facts: [...(shown.facts || []), ["How big", sizeWords(catalogue, item.size, { organism: organismOf(scene, species) })], shapeFact(item, scene, species)].filter(Boolean),
      sections: [
        ...(shown.sections || []),
        levels ? { title: "How it is drawn", items: levels.map((value) => ({ label: `${value.id}. ${value.label}${value.id === level ? " (shown)" : ""}`, lines: [value.says] })) } : null,
        { title: "Its size's sources", items: item.size.sources.map((key) => catalogue.source(key)).filter(Boolean).map((source) => ({ label: citeShort(source), detail: `${source.licence}${source.class ? `, ${source.class}` : ""}`, links: source.url ? [{ text: source.url, url: source.url }] : [] })) },
      ].filter((section) => section?.items?.length),
    };
  }
  const entry = item.entry, kind = item.kind;
  if (entry.gathered?.vault) return describeVault(catalogue, species, item, scene, level);
  const facts = [];
  const gathered = entry.gathered || {}, pick = gathered.pick, family = gathered.route?.by === "family";
  const reference = family ? speciesLabel(scene, gathered.route.reference) : null;
  // What names it: the species' file, a record of the viewer, or the machine's dossier (the Gene Ontology and UniProt).
  // A dossier that looked for its proteins by family names nothing: its line says what was looked for, labelled so.
  const familyNamed = (said) => family && said?.by === FAMILY;
  if (entry.structures) facts.push(["Reference", `PDB ${entry.size.surface.entry} · biological assembly ${entry.size.surface.assembly}`]);
  else if (familyNamed(entry.named)) facts.push(["Looked for, by family", lookedFor(gathered, where, reference)]);
  else if (entry.named?.by) facts.push(["Named by", entry.named.text]);
  else if (entry.named?.text) facts.push(["Named by", `${speciesLabel(scene, species)}'s file: “${entry.named.text}”`]);
  else if (entry.named?.record) facts.push(["Named by", `${catalogue.record(entry.named.record)?.path.replace(/^visualizer\//, "") || entry.named.record}: ${entry.named.word}`]);
  if (familyNamed(entry.also_named)) facts.push(["Looked for, by family", lookedFor(gathered, where, reference)]);
  else if (entry.also_named) facts.push(["Also named by", entry.also_named.text]);
  if (entry.count) facts.push([entry.count.says ? `How many (${entry.count.says})` : "How many", entry.count.text]);
  else if (entry.per_cell?.length === 1) facts.push(["How many", perCellWords(catalogue, entry.per_cell[0])]);
  else if (entry.per_cell?.length) facts.push(["How many", `${entry.per_cell.length} numbers, each in its own condition (below); none is picked`]);
  else if (!entry.structures) facts.push(["How many", "No count in hand for this species"]);
  const size = sizeWords(catalogue, item.size, { organism: organismOf(scene, species) });
  if (entry.structures) facts.push(["Resolved span", `${entry.size.whole.farthest_nm.map((nm) => nm.toFixed(1)).join(" × ")} nm`]);
  else if (size) facts.push(["How big", size]);
  else if (entry.closer) facts.push(["How big", "As its closer view draws it: each part's size is in its own panel, with its paper"]);
  else if (entry.no_size) facts.push(["How big", entry.no_size]);
  else facts.push(["How big", "No size in hand: it stands as a card, not a shape"]);
  const surface = shapeFact(item, scene, species);
  if (surface && (!entry.structures || catalogue.shapeWords.has(entry.size.surface.file))) facts.push(surface);
  // The entry the gathering would measure it from, where its size is not measured from that one.
  if (pick) facts.push(["The gathering's pick", `Protein Data Bank entry ${pick.entry}${pick.title ? `, “${pick.title}”` : ""}${pick.resolution_A ? ` (${pick.resolution_A} Å)` : ""}${pick.present !== undefined && pick.wanted ? `, which holds ${pick.present} of the ${pick.wanted} proteins its dossier seeks` : ""}${pick.holds_more ? `; it holds ${pick.holds_more.says}${pick.holds_more.left_out_entities ? `, and a measure would leave ${pick.holds_more.left_out_entities} of its entities out` : ""}` : ""}${item.size?.shape === "measured" ? `: not the entry this size is measured from` : entry.no_size ? "" : ": not measured here yet"}`]);
  // Where the species has no entry of its own: what its dossier says, and another organism's entry, named as that organism's.
  if (gathered.no_structure && !item.size) facts.push(["A structure of its own", gathered.no_structure]);
  if (gathered.elsewhere) facts.push(["A structure elsewhere", `Protein Data Bank entry ${gathered.elsewhere.entry}${gathered.elsewhere.title ? `, “${gathered.elsewhere.title}”` : ""}${gathered.elsewhere.resolution_A ? ` (${gathered.elsewhere.resolution_A} Å)` : ""}, a structure of ${gathered.elsewhere.organism}; none of ${where}'s own is in hand`]);
  const levels = levelsOf(item);
  const tiers = TIERS.map(([tier, title]) => ({ title, items: (entry.gathered?.proteins || []).filter((row) => row[3] === tier) }));
  const candidates = family ? gathered.proteins : [];
  if (entry.structures) facts.push(["Source organisms", [...new Set(entry.size.chains.filter((chain) => chain.protein).map((chain) => chain.organism))].join(" · ")]);
  else if (entry.proteins) facts.push(["Its proteins", `${number(entry.proteins.items.length)} in ${where}'s data carry the mark “${entry.proteins.label}: ${entry.proteins.value}”. ${entry.proteins.by || ""}`.trim()]);
  else if (family) facts.push(["Its proteins", `${number(candidates.length)} of ${where}'s proteins are candidates by their family (InterPro) for parts of ${reference}'s machine: candidates, not the machine's parts${gathered.in_atlas ? "; every one is in the Protein atlas" : ""}`]);
  else if (entry.gathered) facts.push(["Its proteins", `${number(tiers[0].items.length + tiers[1].items.length)} parts and ${number(tiers[2].items.length)} named with it alone, by the Gene Ontology and UniProt (its dossier)${entry.gathered.in_atlas && entry.gathered.proteins.length ? "; every one is in the Protein atlas" : ""}`]);
  else facts.push(["Its proteins", `${where}'s own data marks no set of proteins for it`]);
  const records = recordLines(catalogue, item, scene);
  const sources = (entry.size?.sources || []).concat(entry.count?.sources || [], entry.named?.sources || [], entry.also_named?.sources || [], (entry.per_cell || []).map((value) => value.source), pick?.source ? [pick.source] : [], gathered.elsewhere?.source ? [gathered.elsewhere.source] : [], gathered.paxdb?.source ? [gathered.paxdb.source] : [], gathered.forms?.source ? [gathered.forms.source] : []).filter((key, index, all) => key && all.indexOf(key) === index);
  const geneOf = new Map((gathered.proteins || []).map((row) => [row[0], row[1] || row[0]]));
  const sections = [
    entry.structures ? { title: "Chains in the 3D surface", items: entry.size.chains.map(chainItem) } : null,
    entry.structures ? { title: "Experimental structures", items: entry.structures.map((row, index) => structureItem(row, index === 0)), shown: 4 } : null,
    { title: "What Cells models of it", note: "Only what a record says.", items: [...records.map(({ label, detail, lines }) => ({ label, detail, lines })), ...(entry.closer ? [{ label: "Its closer view", lines: [entry.closer.modelled] }] : [])] },
    // Its proteins: by tier where a dossier gives them, else the set the species' own data marks.
    ...(entry.per_cell?.length > 1 ? [{ title: "Counts per cell, each in its condition", items: entry.per_cell.map((value) => ({ label: value.written || Number(value.value).toLocaleString("en-US"), detail: value.counts, lines: [perCellWords(catalogue, value)] })) }] : []),
    // Its proteins: by tier where its dossier names them; for a species by family, its candidates and what was looked for.
    ...(entry.gathered && !family ? tiers.map(({ title, items }) => ({ title, items: items.map(gatheredItem) })) : []),
    ...(family ? [
      { title: "Candidates by family, not its parts", note: `Each is a protein of ${where} that carries the narrowest InterPro family of a part of ${reference}'s machine (or, where no line of ${where}'s table carries that one, the nearest broader one that a line carries); it is never called the part.`, items: candidates.map((row) => ({ ...gatheredItem(row), lines: row[4]?.length ? [`A candidate for ${row[4].join(", ")}`] : [] })) },
      { title: `What was looked for, part by part of ${reference}'s machine`, items: (gathered.looked_for || []).map(([gene, tier, outcome, count]) => ({ label: gene, detail: `${tier}: ${outcome === "candidates" ? `${number(count)} ${count === 1 ? "candidate" : "candidates"} ${LOOKED.candidates}` : LOOKED[outcome] || outcome}` })) },
    ] : []),
    gathered.own_mark ? { title: `Its proteins by ${where}'s own mark`, items: [{ label: `${gathered.own_mark.mark}: ${gathered.own_mark.value}`, lines: [`${number(gathered.own_mark.marked)} of ${where}'s proteins carry the mark; ${number(gathered.own_mark.both)} of them are candidates too; ${number(gathered.own_mark.marked_only)} carry the mark only, and ${number(gathered.own_mark.candidates_only)} are candidates only.`] }] } : null,
    gathered.sub_assemblies ? { title: "Sub-assemblies its records name (the Gene Ontology's narrower terms)", items: Object.entries(gathered.sub_assemblies).map(([name, parts]) => ({ label: name, detail: parts.map((id) => geneOf.get(id) || id).join(", ") })) } : null,
    gathered.forms ? formsSection(gathered.forms, where, geneOf) : null,
    gathered.fractions ? { title: "Fractions, in UniProt's words", items: Object.entries(gathered.fractions).map(([name, parts]) => ({ label: name, detail: parts.map((id) => geneOf.get(id) || id).join(", ") })) } : null,
    gathered.subunit?.length ? { title: "Copies, in UniProt's words (its SUBUNIT comments)", note: "UniProt's sentences on how many copies of a protein go together: not a count of copies in a cell.", items: gathered.subunit.map(([gene, id, says]) => ({ label: gene || id, lines: says.map((line) => `“${line}”`) })) } : null,
    gathered.paxdb ? { title: `PaxDb's abundance, in parts per million`, note: `In its dataset “${gathered.paxdb.dataset}”: parts per million of the dataset's protein molecules, as that database gives them; no count of copies in a cell.`, items: gathered.paxdb.items.map(([id, gene, ppm]) => ({ label: gene || id, detail: `${ppm} ${gathered.paxdb.unit}` })) } : null,
    gathered.left_out?.length ? { title: "Entries left out, and why", items: gathered.left_out.map(([id, title, why]) => ({ label: `PDB ${id}`, detail: title ? `“${title}”` : null, lines: why ? [why] : [] })) } : null,
    entry.proteins && !entry.gathered ? { title: `Its proteins in ${where}'s data`, note: entry.proteins.items.length > SHOWN ? `The first ${SHOWN} of ${number(entry.proteins.items.length)}; the Protein atlas shows them all.` : null, items: proteinItems(entry.proteins) } : null,
    levels ? { title: "How it is drawn", items: levels.map((value) => ({ label: `${value.id}. ${value.label}${value.id === level ? " (shown)" : ""}`, lines: [value.says] })) } : null,
    // A source that is a file of the tree (a species' table, another dossier) is named in words here, and the file itself
    // stands in the panel's own list of files, at its revision, as every file of the tree does.
    { title: "Sources and licences", items: sources.map((key) => catalogue.source(key)).filter(Boolean).map(sourceItem) },
  ].filter((section) => section?.items?.length);
  const files = [...new Set(sources.map((key) => TREE_FILE.exec(catalogue.source(key)?.text || "")?.[1]).filter(Boolean))];
  const status = records.find((line) => line.source && !line.source.revision && line.detail);
  const part = kind.cell_part ? (scene?.entities || []).find((entity) => entity.id === kind.cell_part) : null;
  return {
    id: item.id,
    label: item.label,
    kind: "machine",
    eyebrow: `${group?.label || "Machines"} · ${where}`,
    swatch: item.sized ? SWATCH.sized : SWATCH.card,
    status: status && part?.status ? part.status : null,
    as_of: status && part?.as_of ? part.as_of : null,
    chips: [{ label: entry.structures ? "Structure-derived surface" : "Illustration", title: entry.structures ? "A smoothed surface derived from the deposited polymer coordinates" : "Drawn as a simple shape from a published size, or as a card where no size is in hand: not a structure, and not a run" }, { label: item.sized ? "Drawn to scale" : "No size in hand" }, ...records.filter((line) => line.own).map((line) => ({ label: `${line.detail} · ${line.label.split(",")[0]}`, title: line.lines[0] }))],
    plain: kind.plain,
    note: records.length ? `What Cells models of it: ${records.map((line) => `${line.label.split(",")[0]}: ${line.detail}`).join("; ")}.` : null,
    facts,
    sections,
    ...(entry.structures ? { disclosures: [{ title: "How the coordinates were measured", lines: [size] }] } : {}),
    doors: doorsOf(item, scene, species),
    sources: [
      ...records.map((line) => line.source).filter(Boolean),
      entry.named?.file ? { path: `visualizer/${entry.named.file}`, where: `cell.capabilities, ${entry.named.capability}` } : null,
      ...files.map((file) => ({ path: `visualizer/${file}`, where: "a source of its proteins" })),
      { path: "visualizer/data/catalogue/catalogue.json", where: "generated by visualizer/tools/build_catalogue.py" },
    ].filter(Boolean),
    keywords: [kind.plain, ...[...(entry.proteins?.items || []), ...(entry.gathered?.proteins || [])].map(([pid, gene]) => `${pid} ${gene || ""}`)].join(" "),
  };
}

/** A machine named by the address that the species shown does not have: which species have it. */
function elsewhere(catalogue, species, id, scene) {
  const kind = catalogue.kinds.get(kindOf(id));
  const unit = kind ? null : catalogue.units.find((item) => item.id === id);
  if (!kind && !unit) return null;
  // A machine of the species whose bench is not in hand (being read, or not readable): not "not in" it.
  const waiting = kind && catalogue.raw.benches?.[species] && !catalogue.hasBench(species) && (kind.species || []).includes(species);
  if (waiting) return { id, label: kind.label, kind: "machine", eyebrow: `Machines · ${speciesLabel(scene, species)}`, chips: [], plain: kind.plain, note: catalogue.benchState(species)?.words || `The machines of ${speciesLabel(scene, species)} are being read.`, facts: [], sections: [] };
  // A machine its dossier looked for by family and found no candidate for: what was looked for, and that it is not on the bench.
  const looked = kind && id === `${PREFIX}${kind.id}` ? catalogue.noneFound(species).find((row) => row.id === kind.id) : null;
  if (looked) {
    const where = speciesLabel(scene, species), reference = speciesLabel(scene, looked.reference);
    const files = [...new Set(looked.sources.map((key) => TREE_FILE.exec(catalogue.source(key)?.text || "")?.[1]).filter(Boolean))];
    return {
      id,
      label: looked.label,
      kind: "machine",
      eyebrow: `${catalogue.groupById.get(looked.group)?.label || "Machines"} · ${where}`,
      chips: [{ label: "No candidate found", title: "Looked for by family; not on the bench" }],
      plain: kind.plain,
      note: `${NONE_FOUND}: ${noneFoundNote(where)}`,
      facts: [["Looked for, by family", lookedFor({ looked_for: looked.looked_for, proteins: [] }, where, reference)]],
      sections: [
        { title: `What was looked for, part by part of ${reference}'s machine`, items: looked.looked_for.map(([gene, tier, outcome]) => ({ label: gene, detail: `${tier}: ${LOOKED[outcome] || outcome}` })) },
        { title: "Sources and licences", items: looked.sources.map((key) => catalogue.source(key)).filter(Boolean).map(sourceItem) },
      ],
      sources: [...files.map((file) => ({ path: `visualizer/${file}`, where: "a source of what was looked for" })), { path: "visualizer/data/catalogue/catalogue.json", where: "generated by visualizer/tools/build_catalogue.py" }],
    };
  }
  const others = catalogue.speciesWith(id).map((other) => speciesLabel(scene, other));
  // A kind with an identity of its own (the vault) says what was looked for in the species and that a signature not found is not an
  // absence: only where its dossier looked. A species nothing was looked in (one with no bench gathered) is said nothing of the kind.
  const lookedIn = kind?.looked?.[species];
  // A species the catalogue holds no bench for (one shown for the units its atlas finds): nothing was gathered, so the panel says
  // that, and not that the machine is "not in" the species.
  const where = speciesLabel(scene, species), gathered = catalogue.species.includes(species);
  return {
    id,
    label: kind?.label || unit.label,
    kind: "machine",
    eyebrow: lookedIn ? `Machines · not shown for ${where}` : gathered ? `Machines · not in ${where}` : `Machines · no bench for ${where} yet`,
    chips: [{ label: lookedIn ? `Not on ${where}'s bench` : gathered ? `Not listed for ${where}` : `No bench gathered for ${where}` }],
    plain: kind?.plain || unit.plain,
    note: `${gathered ? "" : `No bench of machines has been gathered for ${where} yet: nothing here says whether it has this one. `}${others.length ? `The catalogue lists it for ${others.join(", ").replace(/, (?=[^,]*$)/, " and ")}: choose one of them in the species switch.${lookedIn && kind?.absence ? ` ${kind.absence}` : ""}` : "No species of the catalogue lists it."}`,
    facts: lookedIn ? [["What was looked for", lookedIn.words]] : [],
    sections: lookedIn ? [{ title: "Sources and licences", items: lookedIn.sources.map((key) => catalogue.source(key)).filter(Boolean).map(sourceItem) }] : [],
  };
}

/**
 * The shelf and its stops in words, for the List and the text page: each organelle's size (or that it is a card), at the one scale
 * the view draws the bench and the shelf at, and the stops the view's rail travels between.
 */
export function shelfNote(shelf) {
  const middle = (values) => (values.length > 1 ? (values[0] + values[values.length - 1]) / 2 : values[0]);
  const sizes = shelf.map((item) => {
    const size = item.size;
    if (!size) return `${item.label}: a card, no size in hand`;
    if (size.across_um && size.long_um) return `${item.label}: ${middle(size.across_um)} µm across and ${middle(size.long_um)} µm long`;
    if (size.shape === "stack") return `${item.label}: its cisternae ${middle(size.across_um)} µm across`;
    if (size.across_um) return `${item.label}: ${middle(size.across_um)} µm across`;
    return `${item.label}: its sheets ${middle(size.thick_nm)} nm thick`;
  });
  // The small ones (SHELF.small.um at their longest, or less) stand on a plank of their own, with a stop of their own.
  const small = shelf.filter((item) => longestUm(item.size) !== null && longestUm(item.size) <= SHELF.small.um);
  const plank = small.length ? ` The small ones (${small.map((item) => item.label).join(", ")}) stand on a plank of their own between the bench and the shelf.` : "";
  return `On a shelf behind the bench, at the bench's one scale (one unit, ten nanometres): ${sizes.join("; ")}. Each panel says whose cell the size is of, or that it is a general figure.${plank} The view's rail travels from the bench's stop (its bar reads about 100 nm)${small.length ? " by the small organelles' stop" : ""} to the shelf's (some micrometres), through the powers of ten between, each in the same time.`;
}

/** An organelle's size at its longest, in micrometres, by what its size states (a sheet's thickness says nothing of its length: null). */
function longestUm(size) {
  if (!size?.across_um) return null;
  if (size.shape === "stack") return null; // a cisterna's width: the ribbon of stacks is wider
  const middle = (values) => (values.length > 1 ? (values[0] + values[values.length - 1]) / 2 : values[0]);
  return Math.max(middle(size.across_um), size.long_um ? middle(size.long_um) : 0);
}

/** The list that stands in where 3D cannot be drawn, and the keyboard's way in: each group with its machines. */
export function sections(catalogue, species) {
  if (!catalogue) return [];
  const where = speciesLabel(catalogue.scene, species), none = catalogue.noneFound(species);
  const shelf = catalogue.organellesOf(species), shelfGroup = catalogue.groups.find((group) => group.stands === "shelf");
  return [
    // The organelles on the shelf, under their own group: no machines, and first, as the shelf stands above the bench.
    ...(shelf.length ? [{ label: shelfGroup?.label || "Organelles", note: shelfNote(shelf), entities: shelf.map((item) => ({ id: item.id, label: item.label, swatch: item.sized ? SWATCH.organelle : SWATCH.card, keywords: [shelfGroup?.label, item.kind?.plain].filter(Boolean).join(" ") })) }] : []),
    ...catalogue.groups
      .map((group) => ({
        label: group.label,
        // A machine its species' records do not name, only its dossier's family route: said so beside its name.
        entities: catalogue.inGroup(species, group.id).map((item) => ({ id: item.id, label: byFamily(item) ? `${item.label} · candidates by family` : item.label, swatch: item.sized ? SWATCH.sized : SWATCH.card, keywords: [group.label, item.kind?.plain, item.unit?.eyebrow, ...(item.entry?.proteins?.items || []).map(([id, gene]) => `${id} ${gene || ""}`)].filter(Boolean).join(" ") })),
      }))
      .filter((section) => section.entities.length),
    // What was looked for by family and not found: listed under its own heading, never as a machine of the species.
    ...(none.length ? [{ label: NONE_FOUND, note: noneFoundNote(where), entities: none.map((row) => ({ id: `${PREFIX}${row.id}`, label: `${row.label} (${speciesLabel(catalogue.scene, row.reference)}'s)`, swatch: SWATCH.none, keywords: [NONE_FOUND, catalogue.kinds.get(row.id)?.plain, ...row.looked_for.map(([gene]) => gene)].filter(Boolean).join(" ") })) }] : []),
  ];
}

/**
 * What a protein of the atlas is to a machine of its species, by its dossier's tier (`by_protein`), in the words of the
 * door that opens Machines on it: a part, a part by UniProt's keyword, named with it, or a candidate by its family for a
 * part of the reference's machine. A tier these words do not know has no door: nothing is said that the dossier does not.
 */
export function doorWords(tier, item, scene) {
  const name = /^[A-Z][a-z]/.test(item.label) ? `${item.label.charAt(0).toLowerCase()}${item.label.slice(1)}` : item.label;
  if (item.kind?.identified_by === "vault") {
    if (tier === "part by record") return `It is a part, by the Complex Portal's record, of the ${name}`;
    if (tier === "named by a reviewed entry, by similarity") return `It is named with the ${name} in UniProt's reviewed entry, by similarity to another species' protein`;
    if (tier === "named by a reviewed entry, citing publications") return `It is named with the ${name} in UniProt's reviewed entry, which cites publications for some of its lines`;
    if (tier === "candidate by family") return `It is a candidate, by its family, for a part of the ${name}`;
    return null;
  }
  if (tier === "part") return `It is a part of the ${name}`;
  if (tier === "deposited chain") return `A chain of this protein is resolved in ${item.label}`;
  if (tier === "part by keyword") return `It is a part, by UniProt's keyword, of the ${name}`;
  if (tier === "named") return `It is named with the ${name}`;
  const reference = item.entry?.gathered?.route?.reference;
  if (tier === "candidate by family" && reference) return `It is a candidate, by its family, for a part of ${speciesLabel(scene, reference)}'s ${name}`;
  return null;
}

/**
 * The doors this view offers on another view's parts (the viewer asks every view it offers): on a
 * unit of the law inventory that the species shown has, on the ribosomes of the Cell view, and on a
 * machine's closer view, one into the catalogue on that machine.
 */
export function doorsFor(entity, scene, { species = null } = {}) {
  const catalogue = catalogueOf(scene);
  if (!catalogue || !entity?.id || !species) return [];
  const open = (id) => [{ label: "Show it in the Machines catalogue", lens: "machines", value: id }];
  // A protein of the species' own in the Protein atlas: the machines its dossier makes it a part of, or names it with.
  const own = /^own:([^:]+):p(?:@[^:]*)?:(.+)$/.exec(entity.id);
  const kind = own ? null : [...catalogue.kinds.values()].find((value) => value.cell_part === entity.id);
  // The Cell view's part an organelle of the shelf is drawn at (its kind's `map_part`): a door to it on the shelf, where the species has it.
  const shelfKind = own || kind ? null : [...catalogue.kinds.values()].find((value) => value.map_part === entity.id);
  if (shelfKind) {
    if (!catalogue.benchState(species)) catalogue.loadBench(species);
    return catalogue.item(species, `${ORGANELLE}${shelfKind.id}`) ? [{ label: "Show it on the Machines shelf", lens: "machines", value: `${ORGANELLE}${shelfKind.id}` }] : [];
  }
  // A part none of the doors below can open (a run of the Experiments view, a cell of a run) reads no bench: an address fetches
  // what it draws (until 18 November 2026 a run chosen by the address fetched the species' bench too).
  if (!own && !kind && !(entity.kind === "unit" && entity.group === "proteins") && !(entity.id.startsWith(PREFIX) && !entity.id.slice(PREFIX.length).includes(":"))) return [];
  // Its machines are on its species' bench, read when first wanted; the page draws the panel again when it is in.
  if (!catalogue.benchState(species)) catalogue.loadBench(species);
  if (own) {
    if (!catalogue.benchState(own[1])) catalogue.loadBench(own[1]);
    return catalogue.machinesOf(own[1], own[2]).flatMap(([kind, tier]) => {
      const item = catalogue.item(own[1], `${PREFIX}${kind}`);
      const words = item ? doorWords(tier, item, scene) : null;
      return words ? [{ label: `${words}: show it in Machines`, lens: "machines", value: item.id }] : [];
    });
  }
  if (entity.kind === "unit" && entity.group === "proteins") return catalogue.item(species, entity.id) ? open(entity.id) : [];
  if (entity.id.startsWith(PREFIX) && !entity.id.slice(PREFIX.length).includes(":")) return catalogue.item(species, entity.id) ? open(entity.id) : [];
  return kind && catalogue.item(species, `${PREFIX}${kind.id}`) ? open(`${PREFIX}${kind.id}`) : [];
}

/** A part as this view shows it: a unit of the law inventory as the catalogue presents it (with or without a stage). */
export function present(entity, scene, species) {
  const catalogue = catalogueOf(scene);
  if (!catalogue || !entity) return entity;
  if (entity.kind === "unit" && entity.group === "proteins") return describe(catalogue, species, entity.id, { scene }) || entity;
  return entity;
}

// The page's list and its text page read a species' bench as the view does: asked for when first wanted, and listed
// again when it is in (the page listens for "cells-bench").
const wanting = (scene, species) => {
  const catalogue = catalogueOf(scene);
  if (catalogue && species && !catalogue.benchState(species)) catalogue.loadBench(species);
  return catalogue;
};
export const textSections = (scene, species) => sections(wanting(scene, species), species);
export const textDescribe = (scene, id, species) => describe(wanting(scene, species), species, id, { scene });
export const owns = (id) => typeof id === "string" && (id.startsWith(PREFIX) || id.startsWith(ORGANELLE));
export { IONS };
