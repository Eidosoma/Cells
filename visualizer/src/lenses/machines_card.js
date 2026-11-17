// What the page's panel, list and text page say of the Machines catalogue
// (schema/MACHINE_CATALOGUE.md, "What the view may say"). The shapes are the ones every view
// hands to <cells-panel> and <cells-index>. What Cells models of a machine is said only as a
// record says it: a line of the engine's feature requests, the map's own status of a part, or,
// for the membrane units of the law inventory, the Protein atlas's own panel of the unit.

import { Catalogue, IONS, PREFIX, kindOf, citeShort } from "./machines_data.js";
import { membraneOf, partsByChains, partOfChain as partOfChainIn } from "./machines_layout.js";
import { inSpecies } from "./proteins.js";

/** A swatch for each kind of mark the view draws (machines_styles.js), and one for each group. */
export const SWATCH = { sized: "mach-sized", card: "mach-card", chosen: "mach-chosen" };
export const groupSwatch = (group) => `mach-g-${group}`;
/** UniProt's accession numbers, which link to UniProt; a genome's own locus tag does not. */
const ACCESSION = /^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})$/;
const SHOWN = 12; // proteins listed in a panel before "and N more"
const number = (value) => Number(value).toLocaleString("en-US");

const catalogues = new WeakMap();
/** One Catalogue for each scene, shared by the view, its card and the text page. */
export function catalogueOf(scene) {
  if (!scene?.catalogue?.entries) return null;
  if (!catalogues.has(scene)) catalogues.set(scene, new Catalogue(scene.catalogue, scene));
  return catalogues.get(scene);
}

/** The organism a species' data is of, as the scene names it (its scientific name). */
const organismOf = (scene, id) => (scene?.species || []).find((item) => item.id === id)?.organism || (scene?.proteins?.atlases || []).find((item) => item.id === id)?.organism || null;
/** Whether two organisms' names are of one species: their first two words (a strain's name after them does not count). */
const sameOrganism = (a, b) => Boolean(a && b) && a.split(/\s+/).slice(0, 2).join(" ") === b.split(/\s+/).slice(0, 2).join(" ");
/** "<the structure's organism>", and, where the species shown is of another, that none of its own is in hand. */
const elsewhereWords = (organism, of) => (organism && !sameOrganism(organism, of) ? `${of} (one of ${organism}: none in hand)` : of);

const speciesLabel = (scene, id) => (scene?.species || []).find((item) => item.id === id)?.label || (scene?.proteins?.atlases || []).find((item) => item.id === id)?.label || id;

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

/** The drawing levels a machine has (a catalogue item): its closer view's file's, or, measured from a structure, an outline and its parts. */
export function levelsOf(item) {
  if (item?.entry?.closer?.levels) return item.entry.closer.levels;
  const size = item?.size;
  if (size?.shape !== "measured") return null;
  const chains = partsByChains(size);
  const levels = [{ id: 1, label: "Outline", says: size.outline === "whole" ? "The whole's ellipsoid, as one outline among the other machines." : chains ? "Its chains, in its group's colour, as one outline among the other machines." : "Its measured parts as one outline among the other machines." }];
  if (size.parts?.length > 1) levels.push({ id: 2, label: "Parts", says: chains ? "Each named part in a colour of its own, drawn as its chains, each at its measured size, centre and axes; a part's own ellipsoid is its size, in its panel." : "Each named part a body of its own, at its measured size, centre and axes." });
  if (size.chains?.length > 1) levels.push({ id: 3, label: "Subunits", says: "Each chain of the entry a body of its own, at its measured size, centre and axes, shaded by its kind." });
  return levels.length > 1 ? levels : null;
}

/** The panel of one measured part of a machine (`machine:<kind>:<part>`), with the way back to the machine. */
export function describePart(catalogue, species, owner, partId, { scene = catalogue?.scene } = {}) {
  const item = catalogue?.item(species, owner), size = item?.size;
  const part = size?.parts?.find((value) => value.id === partId) || size?.chains?.find((value) => value.id === partId);
  if (!part) return null;
  const by = (list) => list.map((n) => Number(n).toFixed(1)).join(" by ");
  return {
    id: `${owner}:${part.id}`,
    label: part.label,
    kind: "machine part",
    eyebrow: `${item.label} · a part`,
    chips: [{ label: "Illustration", title: "An ellipsoid at its measured size, centre and axes: not a structure" }],
    plain: size.parts.includes(part) ? `One of the ${item.label}'s ${size.parts.length} measured parts.` : `One of the ${size.chains.length} chains of the entry the ${item.label} is measured from.`,
    facts: [
      ["How big", `${by(part.across_nm)} nm, the ellipsoid of the same spread as its atoms${part.farthest_nm ? ` (its farthest atoms ${by(part.farthest_nm)} nm)` : ""}`],
      ["Where", `Its centre at ${part.centre_nm.map((n) => Number(n).toFixed(1)).join(", ")} nm from the machine's, in the measure's frame`],
      ...(partsByChains(size) && size.parts.includes(part) ? [["Drawn as", `Its ${size.chains.filter((chain) => partOfChainIn(size, chain) === part).length} chains' ellipsoids, in its colour; the size above is the part's own ellipsoid, of the same spread as all its atoms`]] : []),
      ["Measured from", `Protein Data Bank entry ${size.entry}, a structure of ${size.whose ? size.of : elsewhereWords(organismOf(scene, species), size.of)}, by the viewer with tools/measure_particle.py`],
    ],
    sections: [],
    doors: [{ label: "Back to the machine", lens: "machines", value: owner }],
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
  if (item.unit) {
    doors.push({ label: "Show it in the Protein atlas", lens: "proteins", show: "units", select: item.unit.id });
    return doors;
  }
  const proteins = item.entry?.proteins;
  const summary = (scene?.proteins?.shelves || []).find((shelf) => shelf.id === species);
  const offered = proteins && (summary?.sets?.[proteins.mark] || []).some((value) => String(value) === proteins.value);
  if (offered) doors.push({ label: `Show its ${number(proteins.items.length)} proteins in the Protein atlas`, lens: "proteins", show: "own", mark: proteins.mark, value: proteins.value });
  if (item.entry?.closer) doors.push({ label: "Look closer in the cell", lens: "cell", look: "closer", machine: item.entry.id });
  else if (item.kind?.cell_part && (scene?.entities || []).some((entity) => entity.id === item.kind.cell_part)) doors.push({ label: "Show where it sits in the cell", lens: "cell", select: item.kind.cell_part });
  return doors;
}

/** The proteins the species' data marks with a machine, as panel items with links to UniProt where the id is an accession. */
function proteinItems(proteins) {
  return proteins.items.slice(0, SHOWN).map(([id, gene, label]) => ({ label: gene || id, detail: [label, gene ? id : null].filter(Boolean).join(" · "), links: ACCESSION.test(id) ? [{ text: `UniProt ${id}`, url: `https://www.uniprot.org/uniprotkb/${id}/entry` }] : [] }));
}

/** The panel of a machine of the species shown, by its page id; null for an id the catalogue does not hold. */
export function describe(catalogue, species, id, { scene = catalogue?.scene, level = null } = {}) {
  if (!catalogue || !id) return null;
  const item = catalogue.item(species, id);
  if (!item) return elsewhere(catalogue, species, id, scene);
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
      facts: [...(shown.facts || []), ["How big", sizeWords(catalogue, item.size, { organism: organismOf(scene, species) })]],
      sections: [
        ...(shown.sections || []),
        levels ? { title: "How it is drawn", items: levels.map((value) => ({ label: `${value.id}. ${value.label}${value.id === level ? " (shown)" : ""}`, lines: [value.says] })) } : null,
        { title: "Its size's sources", items: item.size.sources.map((key) => catalogue.source(key)).filter(Boolean).map((source) => ({ label: citeShort(source), detail: `${source.licence}${source.class ? `, ${source.class}` : ""}`, links: source.url ? [{ text: source.url, url: source.url }] : [] })) },
      ].filter((section) => section?.items?.length),
    };
  }
  const entry = item.entry, kind = item.kind;
  const facts = [];
  if (entry.named?.text) facts.push(["Named by", `${speciesLabel(scene, species)}'s file: “${entry.named.text}”`]);
  else if (entry.named?.record) facts.push(["Named by", `${catalogue.record(entry.named.record)?.path.replace(/^visualizer\//, "") || entry.named.record}: ${entry.named.word}`]);
  if (entry.count) facts.push([entry.count.says ? `How many (${entry.count.says})` : "How many", entry.count.text]);
  else facts.push(["How many", "No count in hand for this species"]);
  const size = sizeWords(catalogue, item.size, { organism: organismOf(scene, species) });
  if (size) facts.push(["How big", size]);
  else if (entry.closer) facts.push(["How big", "As its closer view draws it: each part's size is in its own panel, with its paper"]);
  else facts.push(["How big", "No size in hand: it stands as a card, not a shape"]);
  const levels = levelsOf(item);
  if (entry.proteins) facts.push(["Its proteins", `${number(entry.proteins.items.length)} in ${where}'s data carry the mark “${entry.proteins.label}: ${entry.proteins.value}”. ${entry.proteins.by || ""}`.trim()]);
  else facts.push(["Its proteins", `${where}'s own data marks no set of proteins for it`]);
  const records = recordLines(catalogue, item, scene);
  const sources = (entry.size?.sources || []).concat(entry.count?.sources || [], entry.named?.sources || []).filter((key, index, all) => all.indexOf(key) === index);
  const sections = [
    { title: "What Cells models of it", note: "Only what a record says.", items: [...records.map(({ label, detail, lines }) => ({ label, detail, lines })), ...(entry.closer ? [{ label: "Its closer view", lines: [entry.closer.modelled] }] : [])] },
    entry.proteins ? { title: `Its proteins in ${where}'s data`, note: entry.proteins.items.length > SHOWN ? `The first ${SHOWN} of ${number(entry.proteins.items.length)}; the Protein atlas shows them all.` : null, items: proteinItems(entry.proteins) } : null,
    levels ? { title: "How it is drawn", items: levels.map((value) => ({ label: `${value.id}. ${value.label}${value.id === level ? " (shown)" : ""}`, lines: [value.says] })) } : null,
    { title: "Sources and licences", items: sources.map((key) => catalogue.source(key)).filter(Boolean).map((source) => ({ label: citeShort(source), detail: `${source.licence}${source.class ? `, ${source.class}` : ""}`, links: source.doi ? [{ text: `doi:${source.doi}`, url: `https://doi.org/${source.doi}` }] : source.url ? [{ text: source.url, url: source.url }] : [] })) },
  ].filter((section) => section?.items?.length);
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
    chips: [{ label: "Illustration", title: "Drawn as a simple shape from a published size, or as a card where no size is in hand: not a structure, and not a run" }, { label: item.sized ? "Drawn to scale" : "No size in hand" }, ...records.filter((line) => line.own).map((line) => ({ label: `${line.detail} · ${line.label.split(",")[0]}`, title: line.lines[0] }))],
    plain: kind.plain,
    note: records.length ? `What Cells models of it: ${records.map((line) => `${line.label.split(",")[0]}: ${line.detail}`).join("; ")}.` : null,
    facts,
    sections,
    doors: doorsOf(item, scene, species),
    sources: [
      ...records.map((line) => line.source).filter(Boolean),
      entry.named?.file ? { path: `visualizer/${entry.named.file}`, where: `cell.capabilities, ${entry.named.capability}` } : null,
      { path: "visualizer/data/catalogue/catalogue.json", where: "generated by visualizer/tools/build_catalogue.py" },
    ].filter(Boolean),
    keywords: [kind.plain, ...(entry.proteins?.items || []).map(([pid, gene]) => `${pid} ${gene || ""}`)].join(" "),
  };
}

/** A machine named by the address that the species shown does not have: which species have it. */
function elsewhere(catalogue, species, id, scene) {
  const kind = catalogue.kinds.get(kindOf(id));
  const unit = kind ? null : catalogue.units.find((item) => item.id === id);
  if (!kind && !unit) return null;
  const others = catalogue.speciesWith(id).map((other) => speciesLabel(scene, other));
  return {
    id,
    label: kind?.label || unit.label,
    kind: "machine",
    eyebrow: `Machines · not in ${speciesLabel(scene, species)}`,
    chips: [{ label: `Not listed for ${speciesLabel(scene, species)}` }],
    plain: kind?.plain || unit.plain,
    note: others.length ? `The catalogue lists it for ${others.join(", ").replace(/, (?=[^,]*$)/, " and ")}: choose one of them in the species switch.` : "No species of the catalogue lists it.",
    facts: [],
    sections: [],
  };
}

/** The list that stands in where 3D cannot be drawn, and the keyboard's way in: each group with its machines. */
export function sections(catalogue, species) {
  if (!catalogue) return [];
  return catalogue.groups
    .map((group) => ({
      label: group.label,
      entities: catalogue.inGroup(species, group.id).map((item) => ({ id: item.id, label: item.label, swatch: item.sized ? SWATCH.sized : SWATCH.card, keywords: [group.label, item.kind?.plain, item.unit?.eyebrow, ...(item.entry?.proteins?.items || []).map(([id, gene]) => `${id} ${gene || ""}`)].filter(Boolean).join(" ") })),
    }))
    .filter((section) => section.entities.length);
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
  if (entity.kind === "unit" && entity.group === "proteins") return catalogue.item(species, entity.id) ? open(entity.id) : [];
  if (entity.id.startsWith(PREFIX) && !entity.id.slice(PREFIX.length).includes(":")) return catalogue.item(species, entity.id) ? open(entity.id) : [];
  const kind = [...catalogue.kinds.values()].find((value) => value.cell_part === entity.id);
  return kind && catalogue.item(species, `${PREFIX}${kind.id}`) ? open(`${PREFIX}${kind.id}`) : [];
}

/** A part as this view shows it: a unit of the law inventory as the catalogue presents it (with or without a stage). */
export function present(entity, scene, species) {
  const catalogue = catalogueOf(scene);
  if (!catalogue || !entity) return entity;
  if (entity.kind === "unit" && entity.group === "proteins") return describe(catalogue, species, entity.id, { scene }) || entity;
  return entity;
}

export const textSections = (scene, species) => sections(catalogueOf(scene), species);
export const textDescribe = (scene, id, species) => describe(catalogueOf(scene), species, id, { scene });
export const owns = (id) => typeof id === "string" && id.startsWith(PREFIX);
export { IONS };
