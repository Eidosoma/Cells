// The frog in the viewer: its species file and outline, its side of the protein atlas and its own proteins on
// shelves are held to their contracts (schema/SPECIES.md, SPECIES_SHAPES.md, SPECIES_ATLAS.md, SPECIES_PROTEINS.md)
// and to the eight rules decided on 19 November 2026 for its proteins (docs/XENOPUS.md): both copies of a gene shown,
// a reviewed entry over its unreviewed twins, every protein's copy from UniProt's proteome component, a twin not shown
// found by the page's own search, what still stands twice said, the gene names UniProt's with Xenbase named behind
// them and nothing else of it, no NCBI gene identifier written, and nothing of another species changed. Where the saved
// downloads are on this machine, the build tool must reproduce the six files byte for byte and the rules are checked
// against the downloads themselves; it builds into out/, never into the memory-backed /tmp.
//
//   node --test tests/xenopus_atlas.test.mjs
//   XENOPUS_DATASETS=DATA node --test tests/xenopus_atlas.test.mjs    (DATA holds every species' downloads)

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { mkdir, mkdtemp, readFile, rm } from "node:fs/promises";
import { gunzipSync } from "node:zlib";
import path from "node:path";
import { ROOT, NAMES_FILE, proteinFiles } from "../tools/lib/build_page.mjs";
import { Shelves, keyOf } from "../src/lenses/protein_shelves.js";
import { accessoryRoles } from "./helpers/atlas_products.mjs";

const ACCESSORY = accessoryRoles();
const TOOL = path.join(ROOT, "tools", "build_xenopus_atlas.py");
const FOLDER = path.join(ROOT, "data", "proteins", "xenopus");
const SPECIES = path.join(ROOT, "data", "species", "xenopus.json");
const SHAPES = path.join(ROOT, "data", "species", "shapes", "xenopus.json");
const ATLAS = path.join(ROOT, "data", "proteins", "atlases", "xenopus.json");
const DATASETS = process.env.XENOPUS_DATASETS || "/mnt/datasets/Cells";
const KB = path.join(DATASETS, "xenopus", "uniprot-xenopus-reference-proteome");
const SAVED = ["xenopus/uniprot-xenopus-reference-proteome", "xenopus/europepmc-stage-sources-e1", "human/interpro-entries-tree-and-go", "human/uniprot-docs-and-terms"].every((folder) => existsSync(path.join(DATASETS, folder, "MANIFEST.json")));
const SIDES = ["outside", "in", "inside", "not known"];
const MACHINE = /\/home\/|\/mnt\/|\/Users\/|\/tmp\//;
// A Xenbase identifier (XB-GENE-…, XB-ART-…) or the address of one of its pages; its site's address alone may stand, on its line among the sources.
const XENBASE_ID = /\bXB-[A-Z]+-\d|xenbase\.org\/[^"]/i;
const SCRATCH = path.join(ROOT, "out", "tests");
// A placeholder name of Xenbase's nomenclature, which embeds the gene's number there: a word of XB and four or more digits,
// with or without .L or .S. While the tool's switch holds (WRITE_PLACEHOLDER_NAMES false), no gene or name field writes one.
const PLACEHOLDER = /\bXB\d{4,}(?:\.[LS])?\b/;
const PLACEHOLDERS_LEFT_OUT = { gene_names: 304, protein_names: 49, twins: 4 };
/** The values of gene and name fields that hold a placeholder name, as [where, value]. */
const placeholdersIn = (rows) => rows.flatMap(([where, ...values]) => values.filter((value) => PLACEHOLDER.test(String(value ?? ""))).map((value) => [where, value]));

const json = async (file) => JSON.parse(await readFile(file, "utf8"));
const species = await json(SPECIES);
const shapes = await json(SHAPES);
const atlas = await json(ATLAS);
const mouse = await json(path.join(ROOT, "data", "species", "mouse.json"));
const planarian = await json(path.join(ROOT, "data", "species", "planarian.json"));
const overlay = await json(path.join(ROOT, "data", "proteins", "overlay.json"));
const shelvesText = await readFile(path.join(FOLDER, "shelves.json"), "utf8");
const shelves = JSON.parse(shelvesText);
const tableText = await readFile(path.join(FOLDER, "proteins.tsv"), "utf8");
const readme = await readFile(path.join(FOLDER, "README.md"), "utf8");
const note = await readFile(path.join(ROOT, "docs", "XENOPUS.md"), "utf8");
const snapshot = await json(path.join(ROOT, "data", "proteins", "inventory.snapshot.json"));
const [head, ...tableLines] = tableText.replace(/\n$/, "").split("\n");
const columns = head.split("\t");
const table = tableLines.map((line) => Object.fromEntries(line.split("\t").map((value, index) => [columns[index], value])));
const byId = new Map(table.map((row) => [row.id, row]));
const named = (names, row) => Object.fromEntries(names.map((name, index) => [name, row[index]]));
const families = shelves.families.map((row) => named(shelves.family_columns, row));
const lone = shelves.lone.parts.map((row) => named(shelves.lone.part_columns, row));
const parts = shelves.no_family.parts.map((row) => named(shelves.no_family.part_columns, row));
const lines = [...families.map((line) => ["family", line]), ...lone.map((line) => ["lone", line]), ...parts.map((line) => ["part", line])];
const sum = (numbers) => numbers.reduce((total, number) => total + number, 0);
const count = (rows, test_) => rows.filter(test_).length;
const said = (n) => n.toLocaleString("en-US");
const level = (id) => species.levels.find((item) => item.id === id);
const part = (name) => shapes.parts.find((item) => item.name === name);
const twinsOf = (row) => (row.same_gene ? row.same_gene.split(";").map((written) => written.split("|")[0]) : []);
// The numbers as built on 19 November 2026 from UniProt's release 2026_04, and those the rules were decided on (docs/XENOPUS.md).
const FROM_COUNTS = [62048, 3523, 58525, 36429, 35004, 3523, 31481, 1425, 1410, 476, 952]; // entries, reviewed, unreviewed, genes, shown, shown reviewed, shown unreviewed, not shown, their genes, genes still twice, their entries
const COPIES = { L: 20031, S: 14296, "L and S": 132, "neither stated": 545 };
const SHELF_SOURCES = [
  ["UniProt", "permissive", null], ["InterPro", "permissive", null], ["Gene Ontology", "permissive", null],
  ["PROSITE", "non-commercial", "UniProt"], ["HAMAP", "permissive", "UniProt"], ["TMHMM", "non-commercial", "UniProt"], ["Phobius", "non-commercial", "UniProt"],
  ["SignalP", "non-commercial", "UniProt"], ["TargetP", "non-commercial", "UniProt"], ["Memsat", "no stated terms", "UniProt"], ["Predotar", "no stated terms", "UniProt"],
  ["Xenbase", "non-commercial", "UniProt"],
];

test("the species file says what it is: an animal whose generic cell and sheet Cells models, drawn as an adult, with placeholder outlines", () => {
  assert.deepEqual(Object.keys(species), ["format", "id", "label", "organism", "taxon", "plain", "group", "order", "default", "made", "modelled", "levels", "cell", "stages", "sources"]);
  assert.deepEqual([species.format, species.id, species.label, species.organism, species.taxon, species.group, species.default], ["cells.visualizer.species@1", "xenopus", "Frog", "Xenopus laevis", 8355, "Animals", false]);
  // Among the animals, after the mouse and before the planarian.
  assert.ok(mouse.order < species.order && species.order < planarian.order, `order ${species.order}`);
  // The mouse's state and words, and nothing more of the engine: no record of the egg, and no stage gives a word of its own.
  assert.equal(species.modelled.state, "generic");
  assert.match(species.modelled.text, /^Cells models a generic cell and a sheet of such cells, not this animal\./);
  assert.match(species.modelled.text, /placeholder outlines: nothing at those scales is simulated\.$/);
  assert.ok(!("record" in species.modelled) && species.stages.list.every((stage) => !("modelled" in stage)));
  assert.match(species.plain, /The frog is drawn as an adult; on the strip of its life stages its fertilised egg is drawn too, and four stages between are named and not drawn\.$/);
  assert.deepEqual(species.levels.map((item) => item.id), ["molecules", "cell", "tissue", "organ", "organism"]);
  // The cell and the sheet are the mouse's: one cell of a sheet that stands for skin-like tissue.
  const theirs = Object.fromEntries(mouse.levels.map((item) => [item.id, item]));
  assert.deepEqual(level("cell").shape, theirs.cell.shape);
  assert.deepEqual(level("tissue").shape, theirs.tissue.shape);
  assert.equal(level("cell").note, theirs.cell.note.replace("a mouse's skin cell", "a frog's skin cell"));
  const [, , , organ, organism] = species.levels;
  assert.deepEqual([organ.label, organ.shape, organism.label, organism.shape], ["Hind foot", { kind: "outline", ref: "xenopus", parts: ["left hind foot", "left hind toes"], context: ["head and body", "left hind leg"] }, "Whole frog", { kind: "outline", ref: "xenopus" }]);
  for (const item of [organ, organism]) assert.match(item.note, /the picture's choice/);
  // No measurement of a foot was read: the foot's sizes are the picture's choice and it names no source; the body's rest on the paper.
  assert.match(organ.note, /no measurement of a foot was read for this file/);
  assert.ok(!organ.sources);
  assert.deepEqual(organism.sources, ["boswald2022"]);
  assert.match(organism.sheet_mark.note, /not to scale/);
  assert.deepEqual(species.cell.parts, { membranes: 1, wall: false, nucleus: true, organelles: ["er", "golgi", "mitochondria"] });
  for (const fact of species.cell.facts) assert.ok(fact.sources.every((key) => species.sources[key]?.class === "permissive"), fact.label);
  // Nothing says that Cells models a frog.
  for (const text of [JSON.stringify(species), JSON.stringify(atlas), shelvesText, readme]) assert.ok(!/\b(is|are|was|were) modelled\b|Cells models (the frog|this frog|a frog|Xenopus)/i.test(text.replace(/no foot is modelled/g, "").replace(/own cells are not modelled/g, "")));
});

test("its life stages: the block kept by hand, as the tool writes it; the egg and the adult drawn, four stages named, every number an open paper's", async () => {
  // The tool writes the block it keeps by hand (data/species/stages/xenopus.json) into the species file as it is.
  const kept = await json(path.join(ROOT, "data", "species", "stages", "xenopus.json"));
  assert.deepEqual([kept.format, kept.species], ["cells.visualizer.species_stages@1", "xenopus"]);
  assert.deepEqual(species.stages, kept.stages);
  const { stageProblems, openingStage, stripOf, speciesAt } = await import("../src/scene/life_stages.js");
  assert.deepEqual(stageProblems(species), []);
  // Decided on 19 November 2026 by the viewer's coordinator: the egg and the adult drawn, four named; the frog opens on its adult.
  assert.deepEqual(stripOf(species).map((mark) => [mark.id, mark.index, mark.drawn, mark.own]), [["egg", "1", true, false], ["two-cell", "2", false, false], ["four-cell", "3", false, false], ["tadpole", "35-36", false, false], ["froglet", "66", false, false], ["adult", null, true, true]]);
  assert.equal(openingStage(species), "adult");
  assert.ok(!("opens_on" in species.stages));
  assert.equal(speciesAt(species), species, "at its own stage the frog is the file, exactly as before");
  // The egg: one cell 1.2 mm across, ending at its cell; its picture's words say that its parts are a generic cell's, not an egg's own.
  const egg = speciesAt(species, "egg");
  assert.deepEqual(egg.levels.map((item) => item.id), ["molecules", "cell"]);
  const cell = egg.levels[1];
  assert.deepEqual([cell.shape, cell.sources], [{ kind: "sphere", across_um: 1200 }, ["sato2025"]]);
  assert.match(cell.note, /not the egg's own structure: its parts are the generic cell's/);
  assert.match(cell.notes.map((item) => item.text).join(" "), /Its parts are a generic cell's, enlarged: not the egg's own; its yolk and pigment are not drawn/);
  assert.deepEqual(egg.stage.inherits, ["cell.parts", "modelled"]);
  // Each named stage says what is not in hand; the one time given is the first division's, at its temperature.
  for (const stage of species.stages.list.filter((item) => item.missing)) assert.match(stage.missing, /^No (size|length) of .* is in hand under usable terms, and nothing of it is drawn\.$/, stage.id);
  assert.deepEqual(species.stages.list.filter((item) => item.time).map((item) => [item.id, item.time.value, item.time.unit, item.time.temperature_c]), [["two-cell", 90, "min", 23]]);
  // Every source a stage cites is an open paper among the species' sources, permissive, with its DOI; nothing of Xenbase.
  for (const key of ["zahn2022", "sato2025"]) assert.deepEqual([species.sources[key].class, species.sources[key].licence], ["permissive", "CC BY 4.0"], key);
  assert.deepEqual([species.sources.zahn2022.doi, species.sources.sato2025.doi], ["10.1242/dev.200356", "10.3390/biom16010022"]);
  assert.ok(!/xenbase/i.test(JSON.stringify(species.stages)) && !/xenbase/i.test(JSON.stringify(kept)));
});

test("the outline: an adult frog, its length and widths the paper's, with the sheet on the left hind foot", () => {
  assert.deepEqual([shapes.format, shapes.parts.map((item) => [item.name, item.group ?? null, item.kind])], ["cells.visualizer.outline@1", [["head and body", "body", "loft"], ["left hind leg", "hind legs", "loft"], ["right hind leg", "hind legs", "loft"], ["left hind foot", "hind feet", "loft"], ["left hind toes", "hind feet", "lines"], ["right hind foot", "hind feet", "loft"], ["right hind toes", "hind feet", "lines"], ["left foreleg", "forelegs", "loft"], ["right foreleg", "forelegs", "loft"]]]);
  assert.match(shapes.note, /the picture's choice/);
  // Snout to vent 12.1 cm; 5.1 cm wide behind the forelimbs and 6.2 cm in front of the hindlimbs; a thigh 3.4 cm wide (Table 1's means for females).
  const body = part("head and body").stations;
  assert.equal(body.at(-1)[0] - body[0][0], 121000);
  assert.equal(Math.max(...body.map((station) => station[3])) * 2, 62000);
  assert.ok(body.some((station) => station[3] * 2 === 51000), "the width behind the forelimbs is a station's");
  assert.ok(body.some((station) => station[3] * 2 === 62000), "the width in front of the hindlimbs is a station's");
  for (const name of ["left hind leg", "right hind leg"]) assert.equal(Math.max(...part(name).stations.map((station) => station[3])) * 2, 34000, name);
  for (const value of ["12.1 ± 1.0 cm", "5.1 ± 0.5 cm", "6.2 ± 0.7 cm", "3.4 ± 0.3 cm", "7.7 ± 0.3 cm"]) assert.ok(species.sources.boswald2022.text.includes(value), value);
  assert.deepEqual([species.sources.boswald2022.class, species.sources.boswald2022.doi], ["permissive", "10.3390/ani12212986"]);
  // The sheet lies on the upper face of the left hind foot, half-way along it.
  const foot = part("left hind foot").stations, middle = foot[10];
  assert.deepEqual(shapes.tissue_on.at_um, [middle[0], middle[1] + middle[4], middle[2]]);
  assert.ok(middle[2] < 0, "the left foot is on the side of negative z");
});

test("rules 1, 2 and 5: both copies of a gene shown; a reviewed entry wins over its unreviewed twins; the counts the build asserts, and what still stands twice", () => {
  const from = shelves.from_counts;
  assert.deepEqual([from.entries, from.reviewed, from.unreviewed, from.genes, from.shown, from.shown_reviewed, from.shown_unreviewed, from.not_shown, from.not_shown_genes, from.twice_unreviewed_genes, from.twice_unreviewed_entries], FROM_COUNTS);
  assert.equal(table.length, from.shown);
  assert.equal(new Set(table.map((row) => row.id)).size, table.length);
  // All the reviewed entries are shown; the ones not shown are unreviewed, each named on a reviewed entry of its gene, and none is shown.
  assert.equal(count(table, (row) => row.reviewed === "1"), from.reviewed);
  const twins = table.flatMap(twinsOf);
  assert.equal(new Set(twins).size, from.not_shown);
  assert.ok(table.every((row) => !row.same_gene || row.reviewed === "1"), "only a reviewed entry names twins");
  assert.ok(twins.every((id) => !byId.has(id)), "a twin is never shown");
  // Both copies stand: the L and the S copies of a symbol are two proteins (kcna1.L and kcna1.S, mvp and mvp.S).
  for (const pair of [["kcna1.L", "kcna1.S"], ["atp1a1", "atp1a1.S"]]) assert.ok(pair.every((gene) => table.some((row) => row.gene === gene)), pair.join(" "));
  for (const text of [shelves.from, atlas.method.join(" "), readme, note]) {
    assert.ok(text.includes(said(from.not_shown)) && text.includes(said(from.not_shown_genes)), "the twins not shown are counted");
    assert.ok(text.includes(said(from.twice_unreviewed_genes)) && text.includes("still stand twice or more"), "what still stands twice is said");
  }
});

test("rule 3: every protein is marked with its copy, read from UniProt's proteome component", () => {
  assert.deepEqual(shelves.marks.copy.values, Object.keys(COPIES));
  assert.deepEqual(Object.fromEntries(Object.keys(COPIES).map((copy) => [copy, count(table, (row) => row.copy === copy)])), COPIES);
  assert.deepEqual(shelves.from_counts.copies, COPIES);
  for (const row of table) {
    const chromosomes = row.chromosome.split("; ");
    const sets = new Set(chromosomes.map((name) => /^\d+(?:_\d+)?([LS])$/.exec(name)?.[1]).filter(Boolean));
    assert.equal(row.copy, sets.size === 2 ? "L and S" : sets.size ? [...sets][0] : "neither stated", `${row.id}: ${row.chromosome}`);
  }
  // Never from the symbol: a reviewed entry with a plain name has its copy (rpa2-b, mvp), and the copy need not follow a suffix.
  assert.deepEqual([byId.get("A1L2H9")?.gene, byId.get("A1L2H9")?.copy], ["rpa2-b", "S"]);
  assert.deepEqual([byId.get("Q6PF69")?.copy, byId.get("Q6PF69")?.chromosome], ["L", "9_10L"]);
});

test("rule 3 against the download: the copy and the chromosomes are the proteome component's own", { skip: SAVED ? false : "the saved downloads are not on this machine (set XENOPUS_DATASETS)" }, () => {
  const component = new Map(gunzipSync(readFileSync(path.join(KB, "uniprotkb_UP000186698_proteome_component.tsv.gz"))).toString("utf8").trim().split("\n").slice(1).map((line) => line.split("\t")));
  for (const row of table) assert.equal(row.chromosome, component.get(row.id).split("; ").map((item) => item.replace(/^UP000186698: (Chromosome )?/, "")).join("; "), row.id);
});

test("rules 2 and 7 against the download: no reviewed entry stands beside an unreviewed twin of its gene, and no gene identifier is written as a field or a tie", { skip: SAVED ? false : "the saved downloads are not on this machine (set XENOPUS_DATASETS)" }, () => {
  const results = JSON.parse(gunzipSync(readFileSync(path.join(KB, "uniprotkb_UP000186698_places.json.gz"))).toString("utf8")).results;
  const genesOf = new Map(results.map((item) => [item.primaryAccession, (item.uniProtKBCrossReferences || []).filter((ref) => ref.database === "GeneID").map((ref) => ref.id)]));
  // A gene identifier of a shown reviewed entry: no shown unreviewed entry carries it (by the identifiers shared directly).
  const reviewedGenes = new Set(table.filter((row) => row.reviewed === "1").flatMap((row) => genesOf.get(row.id)));
  const beside = table.filter((row) => row.reviewed === "0" && genesOf.get(row.id).some((gene) => reviewedGenes.has(gene)));
  assert.deepEqual(beside.map((row) => row.id), [], "an unreviewed entry shown beside the reviewed entry of its gene");
  // Each twin a reviewed entry names shares a gene with it.
  for (const row of table) for (const twin of twinsOf(row)) assert.ok(genesOf.get(twin).length, `${twin} has a gene identifier`);
  // The placeholder names left out are UniProt's own, and counted: gene names and protein names of the shown, and twins' gene names.
  const of = new Map(results.map((item) => [item.primaryAccession, { gene: (item.genes || []).map((gene) => gene.geneName?.value).find(Boolean) || "", name: item.proteinDescription?.recommendedName?.fullName?.value || item.proteinDescription?.submissionNames?.[0]?.fullName?.value || "" }]));
  const twinsShown = new Set(table.flatMap(twinsOf));
  assert.deepEqual({ gene_names: count(table, (row) => PLACEHOLDER.test(of.get(row.id).gene)), protein_names: count(table, (row) => PLACEHOLDER.test(of.get(row.id).name)), twins: [...twinsShown].filter((id) => PLACEHOLDER.test(of.get(id).gene)).length }, PLACEHOLDERS_LEFT_OUT);
  assert.ok(table.every((row) => !PLACEHOLDER.test(of.get(row.id).gene) || row.gene === ""), "a placeholder gene name is left out whole");
  // No NCBI gene identifier is written as a field, a mark or a tie: no column, mark or number of the frog's files is one. (UniProt's
  // gene names of the form LOC and a number carry the gene's number at NCBI, as UniProt gives it; they are written as gene names.)
  assert.deepEqual([count(table, (row) => /^LOC\d+$/.test(row.gene)), count(table, (row) => /^LOC\d+$/.test(row.gene) && genesOf.get(row.id).includes(row.gene.slice(3)))], [10878, 10826]);
  assert.match(readme, /^No NCBI gene identifier is written as a column, a mark or a tie\. 10,878 of the gene names written are UniProt's \(CC BY 4\.0\) of the form LOC and a number; in 10,826 of them the number is the gene's own at NCBI/m);
  const ids = new Set(table.flatMap((row) => genesOf.get(row.id)));
  const written = [shelvesText, tableText, readme, JSON.stringify(atlas), JSON.stringify(species)].join(" ");
  const numbers = new Set(written.match(/\b\d{9}\b/g) || []);
  assert.deepEqual([...ids].filter((id) => id.length === 9 && numbers.has(id)), [], "an NCBI gene identifier is written");
});

test("the placeholder names are not written: no gene or name field of the frog's tracked files holds one, and the counts are said", () => {
  assert.deepEqual(shelves.from_counts.placeholder_names_not_written, PLACEHOLDERS_LEFT_OUT);
  assert.deepEqual(placeholdersIn(table.map((row) => [row.id, row.gene, row.name, row.same_gene])), [], "the table");
  assert.deepEqual(placeholdersIn(Object.values(atlas.units).flatMap((unit) => unit.products.map((product) => [product.ids[0].id, product.gene, product.name]))), [], "the atlas");
  // A planted name is caught; InterPro's "Homeobox protein Hox-B9/HXC9" is no placeholder.
  assert.deepEqual(placeholdersIn([["A0A8J1KYR9", "XB5993457.L", "Aquaporin-4"], ["A0A8J1MNX2", "", "Uncharacterized protein XB22166507.L [provisonal] isoform X2"], ["IPR000000", "", "Homeobox protein Hox-B9/HXC9"]]).map(([where]) => where), ["A0A8J1KYR9", "A0A8J1MNX2"]);
  // Such a protein is in the table by its accession, with no gene or no name written, and the README says so in one sentence.
  assert.ok(count(table, (row) => row.gene === "") >= PLACEHOLDERS_LEFT_OUT.gene_names && count(table, (row) => row.name === "") === PLACEHOLDERS_LEFT_OUT.protein_names);
  assert.match(readme, /^304 gene names and 49 protein names of the proteins shown, and the gene names of 4 twins not shown, are not written here: UniProt gives them, and they are placeholder names of Xenbase's nomenclature that embed the gene's number there/m);
  assert.match(note, /304 gene names and 49 protein names of the\s+proteins shown, and the gene names of 4 twins not shown, are not written here/);
});

test("rule 4: a twin not shown is found by the page's own search, through the names file the page builder writes, and the panel lists it", async () => {
  await mkdir(SCRATCH, { recursive: true });
  const membersDir = await mkdtemp(path.join(SCRATCH, "xenopus-names-"));
  try {
    const files = [...new Set(lines.map(([, line]) => line.file))].sort();
    const found = await proteinFiles({ proteins: { shelves: [{ id: "xenopus", file: "proteins/xenopus/shelves.json", members: files }] } }, { membersDir });
    assert.deepEqual(found.problems, []);
    const names = await json(path.join(membersDir, "xenopus", NAMES_FILE));
    assert.deepEqual(names.columns, ["id", "gene", "label", "side", "same_gene"], "the mark the shelves declare for the search is a column of the names file");
    const page = new Shelves(shelves, { label: "Frog", links: overlay.shelves.links });
    page.addNames(names);
    // By the twin's accession and by its gene: the reviewed entry Q6PF69 (mvp), and the hit says which entry found it.
    for (const query of ["A0A8J0U5T9", "mvp.L (A0A8"]) {
      const hit = page.search(query).proteins.find((item) => item.id === "Q6PF69");
      assert.ok(hit, `${query} finds Q6PF69`);
      assert.deepEqual(hit.via, { label: "Unreviewed entries of its gene, not shown", value: "mvp.L (A0A8J0U5T9)" });
    }
    // A protein found by its own name says nothing more.
    assert.equal(page.search("Q6PF69").proteins[0].via, undefined);
    // Its panel lists the twin as what it is, with its copy and its chromosome: its line's members fetched, as the page's reveal does.
    const line = page.search("A0A8J0U5T9").proteins.find((item) => item.id === "Q6PF69").line;
    page.addMembers(line.file, await json(path.join(membersDir, "xenopus", line.file)));
    page.membersOf(line);
    const facts = Object.fromEntries(page.describe(keyOf("xenopus", "p", "Q6PF69")).facts);
    assert.equal(facts["Unreviewed entries of its gene, not shown"], "mvp.L (A0A8J0U5T9)");
    assert.deepEqual([facts["Copy of its gene"], facts["Chromosome, as UniProt places the entry"]], ["L", "9_10L"]);
    // The published files write no placeholder name either: the members' names and genes, and the names file's.
    for (const file of files) {
      const data = await json(path.join(membersDir, "xenopus", file));
      const at = Object.fromEntries(data.columns.map((column, index) => [column, index]));
      assert.deepEqual(placeholdersIn(data.members.map((member) => [member[at.id], member[at.gene], member[at.label], ...(member[at.marks].same_gene || [])])), [], file);
    }
    assert.deepEqual(placeholdersIn(names.names.map((row) => [row[0], row[1], row[2], row[4]])), [], NAMES_FILE);
    // A protein whose gene name is not written is still found by its accession.
    const nameless = table.find((row) => row.gene === "" && row.name !== "");
    assert.ok(page.search(nameless.id).proteins.some((item) => item.id === nameless.id), `${nameless.id} is found by its accession`);
    // Every twin named in the table is in the names file, on its reviewed entry's row.
    const ofRow = new Map(names.names.map((item) => [item[0], item[4]]));
    for (const item of table.filter((entry) => entry.same_gene)) for (const twin of twinsOf(item)) assert.ok(ofRow.get(item.id).includes(`(${twin})`) || ofRow.get(item.id).split(", ").includes(twin), `${twin} on ${item.id}`);
  } finally {
    await rm(membersDir, { recursive: true, force: true });
  }
});

test("rule 6: the gene names are UniProt's, Xenbase is named behind them through UniProt, and no Xenbase identifier or page is written", () => {
  assert.deepEqual(shelves.sources.map((source) => [source.name, source.class, source.through ?? null]), SHELF_SOURCES);
  for (const source of shelves.sources.filter((item) => item.through)) assert.match(source.holds, /^Nothing was downloaded from it/, source.name);
  const xenbase = shelves.sources.find((source) => source.name === "Xenbase");
  assert.match(xenbase.licence, /^For research and education only: .*"Data are to be used only for purposes of research and education\. Commercial use is prohibited without written permission from Xenbase\."$/);
  assert.equal(xenbase.url, "https://www.xenbase.org/", "its site's address alone");
  assert.match(xenbase.holds, /The gene names were read in UniProt's entries, whose evidence names Xenbase's nomenclature as the names' source: [\d,]+ of the 35,004 proteins shown/);
  // Named only in the shelves' sources and their README; the atlas, the species file and the outline do not name it.
  for (const [name, text] of [["atlas", JSON.stringify(atlas)], ["species", JSON.stringify(species)], ["shapes", JSON.stringify(shapes)], ["table", tableText]]) assert.ok(!/xenbase/i.test(text), `${name} names Xenbase`);
  for (const [name, text] of [["shelves", shelvesText], ["table", tableText], ["readme", readme], ["atlas", JSON.stringify(atlas)], ["species", JSON.stringify(species)], ["note", note]]) assert.ok(!XENBASE_ID.test(text), `${name} holds a Xenbase identifier or page`);
  assert.equal(shelvesText.match(/xenbase/gi).length, JSON.stringify(xenbase).match(/xenbase/gi).length, "Xenbase is named in its source alone");
  const section = note.slice(note.indexOf("## What rests on non-commercial or unlicensed sources"));
  for (const name of ["PROSITE", "TMHMM", "Phobius", "SignalP", "TargetP", "Memsat", "Predotar", "Xenbase"]) assert.ok(section.includes(name), name);
});

test("the shelves are an animal cell's six; every protein is in exactly one line and the counts add up", () => {
  assert.deepEqual([shelves.format, shelves.species], ["cells.visualizer.species_proteins@1", "xenopus"]);
  assert.deepEqual(shelves.shelves.map((shelf) => shelf.id), ["cell", "er", "mito", "nucleus", "other", "membrane"]);
  assert.equal(sum(lines.map(([, line]) => line.count)), table.length);
  let cursor = 0;
  for (const [kind, line] of lines) {
    const rows = table.slice(cursor, cursor + line.count);
    cursor += line.count;
    assert.ok(rows.every((row) => row.shelf === (line.shelf ?? "") && (kind === "lone" ? row.family : row.under === line.id)), `${line.id} on ${line.shelf}`);
    assert.deepEqual(Object.fromEntries(SIDES.map((side) => [side, count(rows, (row) => row.side === side)]).filter(([, n]) => n)), line.sides, `${line.id} on ${line.shelf}`);
  }
  for (const side of SIDES) assert.equal(shelves.counts[side], count(table, (row) => row.side === side), side);
  assert.ok(table.every((row) => (row.side === "not known") === (row.basis === "n") && (row.shelf !== "" || row.side === "not known")));
  // The frog's members are cut 6,000 to a file, by its own value.
  assert.ok(lines.every(([, line]) => line.at[1] <= 6000) && new Set(lines.map(([, line]) => line.file)).size === 6);
});

test("the atlas holds found to a family that makes the machine itself; its products are the proteins that carry the signature", () => {
  assert.deepEqual(Object.keys(atlas.units), snapshot.units.map((unit) => unit.id));
  const findings = Object.values(atlas.units).map((unit) => unit.finding);
  assert.deepEqual(["found", "different family", "none found", "nothing to look for"].map((word) => count(findings, (f) => f === word)), [43, 0, 0, 6]);
  for (const [id, unit] of Object.entries(atlas.units)) {
    for (const product of unit.products) {
      const row = byId.get(product.ids[0].id);
      assert.ok(row && row.units.split(";").includes(id), `${id}: ${product.gene}`);
      assert.equal(product.entry, row.reviewed === "1" ? "reviewed" : "unreviewed", `${id}: ${product.gene}`);
      assert.equal(product.found_by, ACCESSORY.has(product.role) ? "accessory signature" : "family signature", `${id}: ${product.gene}`);
      assert.match(product.evidence_note, /UniProtKB entry carries IPR\d{6}/, `${id}: ${product.gene}`);
    }
  }
  assert.ok(atlas.method.some((line) => /no source of orthology was read, and nothing is called an ortholog/.test(line)));
  assert.ok(atlas.method.some((line) => /Both copies are shown, each as its own protein: nothing read here says they are one, and no pair is merged\./.test(line)));
  // Both copies are listed where both carry the family: the connexin gja1 and its S copy, the Kv1.1 channel's L and S.
  assert.ok(["gja1", "gja1.S"].every((gene) => atlas.units.U36.products.some((product) => product.gene === gene)));
  assert.ok(["kcna1.L", "kcna1.S"].every((gene) => atlas.units.U05.products.some((product) => product.gene === gene)));
  for (const source of atlas.sources) assert.equal(source.class, "permissive", source.name);
  assert.ok(!MACHINE.test(JSON.stringify(atlas)));
});

test("the files keep the frog's own bounds, hold no machine path, and the notes give the files' own numbers", () => {
  const bounds = overlay.shelves.limits.xenopus;
  assert.ok(bounds.why && bounds.since === "2026-11-19");
  assert.ok(Buffer.byteLength(shelvesText) < bounds.shelves_bytes && Buffer.byteLength(tableText) < 5_000_000);
  assert.ok(!MACHINE.test(shelvesText) && !MACHINE.test(tableText) && !MACHINE.test(readme) && !MACHINE.test(JSON.stringify(species)) && !MACHINE.test(JSON.stringify(shapes)) && !MACHINE.test(note), "a machine path");
  const from = shelves.from_counts;
  for (const n of [from.entries, from.reviewed, from.unreviewed, from.genes, from.shown, from.shown_unreviewed]) assert.ok(note.includes(said(n)), `${said(n)} is not in the note`);
  for (const n of [from.shown, sum(Object.values(shelves.shelf_counts.cell)), shelves.families_in_all]) assert.ok(readme.includes(said(n)) && note.includes(said(n)), `${said(n)} is not in the notes`);
});

test("the build tool reproduces the six files from the saved downloads", { skip: SAVED ? false : "the folders of saved downloads are not on this machine (set XENOPUS_DATASETS)" }, async (t) => {
  // The quick sweep (npm run test:quick) skips it where it passed before on the same inputs; npm test always runs it.
  const { passedBefore } = await import("./lib/test_cache.mjs");
  if (await passedBefore(t, { downloads: [path.join(DATASETS, "*", "*")], env: ["XENOPUS_DATASETS"] })) return;
  await mkdir(SCRATCH, { recursive: true });
  const folder = await mkdtemp(path.join(SCRATCH, "xenopus-build-"));
  try {
    const built = spawnSync("python3", ["-I", TOOL, "build", "--datasets", DATASETS, "--out-dir", path.join(folder, "xenopus"), "--out-species", path.join(folder, "species.json"), "--out-shapes", path.join(folder, "shapes.json"), "--out-atlas", path.join(folder, "atlas.json")], { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
    assert.equal(built.status, 0, built.stderr);
    for (const [made, kept] of [["xenopus/shelves.json", path.join(FOLDER, "shelves.json")], ["xenopus/proteins.tsv", path.join(FOLDER, "proteins.tsv")], ["xenopus/README.md", path.join(FOLDER, "README.md")], ["species.json", SPECIES], ["shapes.json", SHAPES], ["atlas.json", ATLAS]]) {
      assert.equal(await readFile(path.join(folder, made), "utf8"), await readFile(kept, "utf8"), `${made} is not what the tool builds`);
    }
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});
