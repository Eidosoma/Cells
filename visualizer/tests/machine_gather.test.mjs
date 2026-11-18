// The Machines catalogue's dossiers (schema/MACHINE_DOSSIERS.md): data/catalogue/gather.json, kept
// by hand, and data/catalogue/dossiers/<species>.json, which tools/gather_machines.py writes from it
// and from saved downloads. Held here: the hand file's shape; each dossier's join to the Protein
// atlas, both ways (every protein by the atlas's own id, and for each protein the machines it is a
// part of); each structure's measure call in the terms of tools/measure_particle.py --machine (every
// entity either measured in a part or left out, never both); every value resting on a source whose
// licence and class agree, and on a permissive one; no word that says what Cells does of a machine;
// no path of this machine. Where the saved downloads are on this machine, the tool must write the
// dossiers byte for byte from them; elsewhere that one check is skipped.
//
//   node --test tests/machine_gather.test.mjs
//   GATHER_DATASETS=DATA node --test tests/machine_gather.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { ROOT } from "../tools/lib/build_page.mjs";

const json = (file) => JSON.parse(readFileSync(path.join(ROOT, file), "utf8"));
const gather = json("data/catalogue/gather.json");
const SPECIES = Object.keys(gather.species);
const dossiers = Object.fromEntries(SPECIES.map((species) => [species, json(`data/catalogue/dossiers/${species}.json`)]));
const DATASETS = process.env.GATHER_DATASETS || "/mnt/datasets/Cells";
const SAVED = SPECIES.every((species) => existsSync(path.join(DATASETS, gather.species[species].rcsb, "MANIFEST.json")));
// The groups the Machines tab already has (the catalogue's overlay, data/catalogue/overlay.json), which the kinds may name beside the ones proposed here.
const KNOWN_GROUPS = ["proteins", "genes", "atp", "ions", "membranes", "breaking", "moving"];
const MACHINE = /\/home\/|\/mnt\/|\/Users\/|\/tmp\//;
const SAYS_MODEL = /\b(modelled|modeled|qualified|judged|simulated)\b/i;
// The same classes as tests/licence_classes.test.mjs.
const NON_COMMERCIAL = /CC BY-NC|^Academic licence\b|^For academic users only\b/;
const NO_TERMS = /^(No open licence stated|no licence stated|no open licence|Terms not read\b)/;
const PERMISSIVE = /^CC BY\b(?!-NC)|^CC0\b|[Nn]o restrictions?\b|places no restriction|[Ii]mposes no restrictions|no use restrictions|^Public domain|BSD 3-Clause|^Bibliographic facts only/;
const classOf = (licence) => (NON_COMMERCIAL.test(licence) ? "non-commercial" : NO_TERMS.test(licence) ? "no stated terms" : PERMISSIVE.test(licence) ? "permissive" : null);

function atlasIds(species) {
  const atlas = gather.species[species].atlas;
  const [head, ...rows] = readFileSync(path.join(ROOT, atlas ? atlas.table : path.join("data", "proteins", species, "proteins.tsv")), "utf8").replace(/\n$/, "").split("\n");
  const at = head.split("\t").indexOf(atlas ? atlas.id : "id");
  assert.ok(at >= 0, `${species}: the atlas table has no id column`);
  return new Set(rows.map((row) => row.split("\t")[at]));
}
const GO_ROUTE = SPECIES.filter((species) => gather.species[species].route !== "family");
const FAMILY_ROUTE = SPECIES.filter((species) => gather.species[species].route === "family");

test("gather.json: one entry per kind, kinds in known or proposed groups, and every machine names its proteins by a term or an entry", () => {
  assert.equal(gather.format, "cells.visualizer.machine_gather@1");
  const groups = new Set([...KNOWN_GROUPS, ...gather.groups_proposed.map((group) => group.id)]);
  for (const group of gather.groups_proposed) assert.ok(!KNOWN_GROUPS.includes(group.id), `${group.id} is proposed and already known`);
  const kinds = new Map(gather.kinds.map((kind) => [kind.id, kind]));
  assert.equal(kinds.size, gather.kinds.length, "a kind is listed twice");
  for (const kind of gather.kinds) {
    assert.match(kind.id, /^[a-z0-9]+(-[a-z0-9]+)*$/, kind.id);
    assert.ok(groups.has(kind.group), `${kind.id}: no group ${kind.group}`);
    assert.doesNotMatch(kind.plain || "", SAYS_MODEL, kind.id);
  }
  for (const [species, block] of Object.entries(gather.species)) {
    if (block.route === "family") {
      // A species with no curated record of its machines looks for them by family, in a reference species that has one.
      assert.ok(GO_ROUTE.includes(block.reference), `${species}: its reference ${block.reference} has no record of its own`);
      for (const key of ["table", "id", "label", "signatures", "source", "licence"]) assert.ok(block.atlas[key], `${species}: atlas.${key}`);
      assert.equal(classOf(block.atlas.licence), "permissive", `${species}: the atlas table's licence`);
      continue;
    }
    const seen = new Set();
    for (const machine of block.machines) {
      assert.ok(kinds.has(machine.kind), `${species}: no kind ${machine.kind}`);
      assert.ok(!seen.has(machine.kind), `${species}: ${machine.kind} twice`);
      seen.add(machine.kind);
      assert.ok((machine.go || []).length || machine.seed, `${species}, ${machine.kind}: nothing names its proteins`);
      for (const term of machine.go || []) assert.match(term, /^GO:\d{7}$/);
      if (machine.entry) assert.ok(machine.entry.why && machine.entry.why.length > 40, `${species}, ${machine.kind}: an entry chosen by hand says why`);
      if (machine.structure === false) assert.ok(machine.why, `${species}, ${machine.kind}: no structure, and no word why`);
    }
  }
  assert.doesNotMatch(JSON.stringify(gather), MACHINE);
});

test("a dossier by family: every candidate is a line of the species' atlas, stands for a part of the reference's machine, and is given back", () => {
  for (const species of FAMILY_ROUTE) {
    const dossier = dossiers[species];
    const block = gather.species[species];
    assert.equal(dossier.route, "family");
    assert.equal(dossier.reference, block.reference);
    const reference = dossiers[block.reference];
    const kinds = reference.machines.map((machine) => machine.kind);
    // Every machine of the reference is looked for, or listed as not looked for (the reference gives it no part).
    const looked = dossier.machines.map((machine) => machine.kind);
    const skipped = (dossier.not_looked_for || []).map((item) => item.kind);
    assert.deepEqual([...looked, ...skipped].sort(), (block.machines && block.machines !== "all" ? kinds.filter((kind) => block.machines.includes(kind)) : kinds).sort());
    for (const kind of skipped) assert.ok(!reference.machines.find((m) => m.kind === kind).proteins.rows.some((row) => row[3] !== "named"), `${species}: ${kind} is not looked for, and the reference has parts of it`);
    const ids = atlasIds(species);
    const back = new Map();
    for (const machine of dossier.machines) {
      const where = `${species}, ${machine.kind}`;
      const refMachine = reference.machines.find((item) => item.kind === machine.kind);
      const refParts = new Map(refMachine.proteins.rows.filter((row) => row[3] !== "named").map((row) => [row[0], row[1]]));
      assert.deepEqual(machine.proteins.columns, ["id", "gene", "label", "kind", "families", "stands_for", "same_as", "how"], where);
      assert.equal(machine.looked_for.parts, refParts.size, `${where}: every part of the reference is looked for`);
      const listed = new Set(machine.proteins.rows.map((row) => row[0]));
      assert.equal(listed.size, machine.proteins.rows.length, `${where}: a candidate twice`);
      for (const [reference_, gene, tier, families, candidates, outcome] of machine.looked_for.rows) {
        assert.equal(refParts.get(reference_), gene, `${where}: ${reference_}`);
        assert.ok(["part", "part by keyword"].includes(tier), `${where}: ${reference_} ${tier}`);
        for (const id of candidates) assert.ok(listed.has(id), `${where}: ${id} is found for ${gene} and not listed`);
        // A part with no candidate is "not in the table" only where every scan of the table knew its families; else "cannot tell".
        assert.equal(outcome, !families.length ? "no family signature" : candidates.length ? "candidates" : families.some((level) => level[4] === "cannot tell") ? "cannot tell" : "not in the table", `${where}: ${gene}`);
        for (const level of families) {
          assert.ok(["narrowest", "broader", "not in the table", "cannot tell"].includes(level[4]), `${where}: ${gene}`);
          assert.equal(level[2] !== null, ["narrowest", "broader"].includes(level[4]), `${where}: ${gene}`);
          if (level[4] === "narrowest") assert.equal(level[2], level[0], `${where}: ${gene}`);
        }
      }
      assert.equal(machine.looked_for.with_candidates, machine.looked_for.rows.filter((row) => row[4].length).length, where);
      for (const row of machine.proteins.rows) {
        assert.ok(ids.has(row[0]), `${where}: ${row[0]} is not a line of the atlas`);
        assert.ok(row[4].length && row[5].length, `${where}: ${row[0]} names no family or no part`);
        back.set(row[0], [...(back.get(row[0]) || []), { machine: machine.kind, tier: "candidate by family" }]);
      }
      assert.equal(machine.join.not_in_atlas.length, 0, where);
      assert.doesNotMatch(`${machine.plain || ""} ${machine.named.text}`, SAYS_MODEL, where);
      assert.match(machine.named.text, /candidate/, `${where}: a candidate is said to be one`);
      if (!machine.structure) assert.match(machine.no_structure, /^None in hand/, where);
    }
    assert.deepEqual(Object.keys(dossier.by_protein).sort(), [...back.keys()].sort(), `${species}: by_protein is not the candidates`);
    for (const [id, items] of back) assert.deepEqual(dossier.by_protein[id], [...items].sort((a, b) => (a.machine < b.machine ? -1 : a.machine > b.machine ? 1 : 0)), `${species}: ${id}`);
  }
});

test("each dossier joins every protein to the Protein atlas by its id, and gives each protein's machines back", () => {
  for (const species of GO_ROUTE) {
    const dossier = dossiers[species];
    assert.equal(dossier.format, "cells.visualizer.machine_dossiers@1");
    assert.equal(dossier.species, species);
    assert.deepEqual(dossier.machines.map((machine) => machine.kind), gather.species[species].machines.map((machine) => machine.kind));
    const ids = atlasIds(species);
    const partOf = new Map();
    for (const machine of dossier.machines) {
      const where = `${species}, ${machine.kind}`;
      const { columns, rows, counts } = machine.proteins;
      assert.deepEqual(columns, ["id", "gene", "label", "tier", "go", "keyword", "entities", "in_atlas"], where);
      const named = (row) => Object.fromEntries(columns.map((column, index) => [column, row[index]]));
      const proteins = rows.map(named);
      assert.equal(new Set(proteins.map((p) => p.id)).size, proteins.length, `${where}: a protein twice`);
      const tally = {};
      for (const protein of proteins) {
        assert.ok(["part", "part by keyword", "named"].includes(protein.tier), `${where}: ${protein.id} ${protein.tier}`);
        if (protein.tier === "part by keyword") assert.ok(protein.keyword.length && !protein.entities.length, `${where}: ${protein.id} is a part by keyword with no keyword, or held by the entry`);
        tally[protein.tier] = (tally[protein.tier] || 0) + 1;
        assert.equal(protein.in_atlas, ids.has(protein.id), `${where}: ${protein.id} in_atlas says ${protein.in_atlas}`);
        if (protein.tier === "named") assert.ok(protein.go.length, `${where}: ${protein.id} is named with it by no term`);
        if (protein.tier !== "named") partOf.set(protein.id, [...(partOf.get(protein.id) || []), { machine: machine.kind, tier: protein.tier }]);
      }
      assert.deepEqual(counts, Object.fromEntries(Object.entries(tally).sort()), `${where}: the counts`);
      const join = machine.join;
      assert.equal(join.parts, (tally.part || 0) + (tally["part by keyword"] || 0), where);
      assert.equal(join.held_by_entry, tally.part || 0, where);
      assert.equal(join.parts_in_atlas, proteins.filter((p) => p.tier !== "named" && p.in_atlas).length, where);
      assert.equal(join.all_in_atlas, proteins.filter((p) => p.in_atlas).length, where);
      assert.deepEqual(join.not_in_atlas, proteins.filter((p) => !p.in_atlas).map((p) => p.id), where);
      assert.doesNotMatch(`${machine.plain || ""} ${machine.named.text}`, SAYS_MODEL, where);
      // UniProt's own words on how many copies go together, for parts only, each with its entry.
      for (const item of machine.uniprot_subunit?.items || []) {
        assert.ok(proteins.some((p) => p.id === item.id && p.tier !== "named"), `${where}: ${item.id} is no part`);
        assert.ok(item.says.length && item.says.every((sentence) => typeof sentence === "string" && !/ECO:|SUBUNIT:/.test(sentence)), `${where}: ${item.id}`);
      }
    }
    // Both ways: by_protein holds exactly the parts, each with its machines, and only proteins the atlas knows or the join lists as missing.
    const back = Object.fromEntries([...partOf].map(([id, items]) => [id, [...items].sort((a, b) => (a.machine < b.machine ? -1 : a.machine > b.machine ? 1 : 0))]).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)));
    assert.deepEqual(dossier.by_protein, back, `${species}: by_protein is not the parts`);
  }
});

test("each structure is one call of tools/measure_particle.py --machine: every entity measured in a part or left out, never both", () => {
  for (const [species, dossier] of Object.entries(dossiers)) {
    for (const machine of dossier.machines) {
      const where = `${species}, ${machine.kind}`;
      const s = machine.structure;
      if (!s) {
        assert.ok(machine.no_structure, `${where}: no structure and no word why`);
        continue;
      }
      assert.match(s.entry, /^[0-9][A-Z0-9]{3}$/, where);
      const ids = s.entities.map((entity) => entity.id);
      assert.equal(new Set(ids).size, ids.length, `${where}: an entity twice`);
      const measured = Object.values(s.measure.parts).flat();
      assert.equal(new Set(measured).size, measured.length, `${where}: an entity in two parts`);
      assert.deepEqual([...measured, ...s.measure.exclude].sort(), [...ids].sort(), `${where}: every entity is in a part or left out`);
      for (const entity of s.entities) {
        const inPart = measured.includes(entity.id);
        assert.equal(inPart, !entity.role.startsWith("left out"), `${where}: entity ${entity.id} is ${entity.role}`);
        if (entity.role === "part" || entity.role === "named with it") assert.ok(entity.same_organism, `${where}: entity ${entity.id} of another organism names a protein of the species`);
      }
      assert.ok(s.measure.call.startsWith("python3 -I tools/measure_particle.py --machine "), where);
      for (const [name, entities] of Object.entries(s.measure.parts)) assert.ok(s.measure.call.includes(`--part ${name}=${entities.join(",")}`), `${where}: the call lacks ${name}`);
      if (s.measure.exclude.length) assert.ok(s.measure.call.includes(`--exclude ${s.measure.exclude.join(",")}`), `${where}: the call lacks the left-out entities`);
      if (s.measure.frame) for (const part of s.measure.frame) assert.ok(part in s.measure.parts, `${where}: the frame names no part ${part}`);
      assert.equal(typeof s.measurable, "boolean", where);
      // A protein of the species that the entry holds and the ontology does not name with the machine is left out, and counted.
      if (s.in_entry_only) {
        assert.equal(s.in_entry_only.count, s.in_entry_only.proteins.length, where);
        for (const other of s.in_entry_only.proteins) for (const id of other.entities) assert.ok(s.measure.exclude.includes(id), `${where}: ${other.id}'s entity ${id} is measured`);
      }
      assert.ok(s.file || s.file_to_fetch, `${where}: no file`);
      if (s.file) assert.match(s.file, /^[a-z0-9]+\/[a-z0-9-]+\/[0-9A-Z]{4}(-assembly1)?\.cif\.gz$/, where);
      assert.ok(s.sources.every((key) => key in dossier.sources), where);
    }
  }
});

test("every value rests on a source whose licence and class agree, and that is permissive", () => {
  for (const [species, dossier] of Object.entries(dossiers)) {
    for (const [key, source] of Object.entries(dossier.sources)) {
      assert.ok(source.licence && source.class, `${species}: ${key}`);
      assert.equal(source.class, classOf(source.licence), `${species}: ${key}: the class does not follow from "${source.licence}"`);
    }
    for (const machine of dossier.machines) {
      const behind = [...machine.named.sources, ...(machine.structure?.sources || []), ...(machine.structure_elsewhere?.sources || []), ...(machine.uniprot_subunit?.sources || []), ...(machine.uniprot_fractions?.sources || []), ...(machine.complex_portal?.sources || []), ...(machine.paxdb?.sources || []), ...(machine.sub_assemblies?.sources || []), ...(machine.per_cell || []).flatMap((item) => item.sources || [item.source])];
      // A value read from PaxDb or the Complex Portal is of a part of the machine, and PaxDb's is said as that database's abundance, never as copies.
      const partIds = new Set((machine.proteins.rows || []).filter((row) => row[3] !== "named").map((row) => row[0]));
      for (const [id] of machine.paxdb?.items || []) assert.ok(partIds.has(id), `${species}, ${machine.kind}: PaxDb's value of ${id}, no part`);
      if (machine.paxdb) assert.ok(machine.paxdb.unit === "ppm" && /no count of copies/.test(machine.paxdb.note) && machine.paxdb.dataset_id, `${species}, ${machine.kind}: PaxDb's values say what they are`);
      for (const complex of machine.complex_portal?.complexes || []) for (const id of Object.keys(complex.stoichiometry)) assert.ok(partIds.has(id), `${species}, ${machine.kind}: ${complex.id} ${id}`);
      for (const group of Object.values(machine.uniprot_fractions?.groups || {})) for (const id of group) assert.ok(partIds.has(id), `${species}, ${machine.kind}: fraction ${id}`);
      for (const key of behind) {
        assert.ok(dossier.sources[key], `${species}, ${machine.kind}: ${key} is not a source`);
        assert.equal(dossier.sources[key].class, "permissive", `${species}, ${machine.kind}: ${key} is ${dossier.sources[key].class}`);
      }
      for (const item of machine.per_cell || []) {
        if (item.fact) continue;
        assert.ok(item.where && item.as_written.length && item.counts && item.cell, `${species}, ${machine.kind}: a number says what it counts, in what cell and where it stands`);
        const values = [item.value].flat();
        for (const value of values) assert.ok(item.as_written.some((said) => Number(said.replace(/,/g, "")) * (item.scale || 1) === value), `${species}, ${machine.kind}: ${value} is not as written`);
        if (item.scale) assert.ok(item.written, `${species}, ${machine.kind}: a power of ten says how it is written`);
      }
    }
    const text = JSON.stringify(dossier);
    assert.doesNotMatch(text, MACHINE, `${species}: a path of this machine`);
  }
});

test("a held source is read by no step: the Complex Portal, off in gather.json, and on and off on a made-up folder", () => {
  const held = gather.sources_held?.complex_portal;
  assert.ok(held && typeof held.use === "boolean" && /^Held on \d{1,2} [A-Z][a-z]+ \d{4}:/.test(held.held), "the switch and its dated line");
  if (!held.use) {
    for (const [species, dossier] of Object.entries(dossiers)) {
      assert.ok(!("complex_portal" in dossier.sources), `${species}: a source that is held`);
      for (const machine of dossier.machines) {
        assert.ok(!("complex_portal" in machine), `${species}, ${machine.kind}: complex_portal while held`);
        assert.equal((machine.sub_assemblies?.complex_portal || []).length, 0, `${species}, ${machine.kind}: a sub-assembly that rests on a held source`);
        assert.ok(!(machine.sub_assemblies?.sources || []).includes("complex_portal"), `${species}, ${machine.kind}`);
      }
    }
  }
  // Both states on a made-up folder, through the tool's own functions.
  const script = [
    "import sys, json",
    `sys.path.insert(0, ${JSON.stringify(path.join(ROOT, "tools"))})`,
    "import gather_machines as G",
    `d = G.P.Datasets(${JSON.stringify(path.join(ROOT, "tests", "fixtures", "machine-gather", "datasets"))})`,
    "block = {'complex_portal': {'folder': 'madeup/complex-portal-x', 'file': 'complextab.tsv'}}",
    "parts = {'P00001', 'P00002', 'P00003'}",
    "item = {'proteins': {'rows': [[a, a, None, 'part', ['GO:0000001'], [], ['1'], True] for a in sorted(parts)]}}",
    "onto = {'name': lambda t: 'made-up term'}",
    "out = {}",
    "for use in (False, True):",
    "    config = {'sources_held': {'complex_portal': {'use': use, 'held': 'Held on 17 November 2026: made up.'}}}",
    "    portal = G.read_complex_portal(d, block, config)",
    "    out[str(use)] = {'portal': G.complex_portal_for(portal, parts), 'sub': G.sub_assemblies({'go': []}, item, portal, parts, onto)}",
    "print(json.dumps(out))",
  ].join("\n");
  const run = spawnSync("python3", ["-I", "-c", script], { encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr);
  const out = JSON.parse(run.stdout);
  assert.equal(out.False.portal, null, "off: no complex_portal");
  assert.ok(!("complex_portal" in out.False.sub), "off: no sub-assembly from it");
  assert.ok(!out.False.sub.sources.includes("complex_portal"));
  assert.deepEqual(Object.keys(out.False.sub.go), ["GO:0000001"], "off: the ontology's sub-assemblies stay");
  assert.deepEqual(out.True.portal.complexes.map((c) => [c.id, c.parts_held]), [["CPX-1", 3], ["CPX-2", 2]]);
  assert.deepEqual(out.True.portal.complexes[0].stoichiometry, { P00001: 2, P00002: 1, P00003: 0 });
  assert.deepEqual(out.True.sub.complex_portal.map((c) => c.id), ["CPX-2"], "on: a complex of some of the parts is a sub-assembly");
  assert.ok(out.True.sub.sources.includes("complex_portal"));
});

test("an entry of another machine is never a pick, and every pick carries its entry's own title", () => {
  const left = gather.entries_left_out || [];
  for (const item of left) {
    assert.ok(SPECIES.includes(item.species) && item.kind && /^[0-9][A-Z0-9]{3}$/.test(item.entry) && item.title, JSON.stringify(item));
    assert.match(item.why, /^Left out on \d{1,2} [A-Z][a-z]+ \d{4}: /, `${item.entry}: a dated line`);
  }
  for (const [species, dossier] of Object.entries(dossiers)) {
    for (const machine of dossier.machines) {
      const where = `${species}, ${machine.kind}`;
      const out = new Set(left.filter((item) => item.species === species && item.kind === machine.kind).map((item) => item.entry));
      if (machine.structure) {
        assert.ok(!out.has(machine.structure.entry), `${where}: ${machine.structure.entry} is left out and picked`);
        assert.ok(typeof machine.structure.title === "string" && machine.structure.title.length, `${where}: the pick has no title`);
      }
      if (machine.structure_elsewhere) assert.ok(machine.structure_elsewhere.title, `${where}: the entry named elsewhere has no title`);
      const noted = (gather.entries_noted || []).find((item) => item.species === species && item.kind === machine.kind && item.entry === machine.structure?.entry);
      assert.equal(Boolean(machine.structure?.holds_more), Boolean(noted), `${where}: a kept entry that holds other complexes says so, and no other does`);
      if (noted) assert.ok(machine.structure.holds_more.says === noted.holds && machine.structure.holds_more.left_out_entities >= 2, where);
      for (const gone of (machine.structure || machine).left_out || []) assert.ok(out.has(gone.entry) && gone.title && gone.why, `${where}: ${gone.entry}`);
    }
  }
});

test("the tool writes the dossiers as they are, from the saved downloads", { skip: !SAVED && "the saved downloads are not on this machine" }, () => {
  const run = spawnSync("python3", ["-I", path.join(ROOT, "tools", "gather_machines.py"), "check", "--datasets", DATASETS], { encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr || run.stdout);
});
