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
  const [head, ...rows] = readFileSync(path.join(ROOT, "data", "proteins", species, "proteins.tsv"), "utf8").replace(/\n$/, "").split("\n");
  const at = head.split("\t").indexOf("id");
  return new Set(rows.map((row) => row.split("\t")[at]));
}

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

test("each dossier joins every protein to the Protein atlas by its id, and gives each protein's machines back", () => {
  for (const [species, dossier] of Object.entries(dossiers)) {
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
      assert.equal(s.in_entry_only.count, s.in_entry_only.proteins.length, where);
      for (const other of s.in_entry_only.proteins) for (const id of other.entities) assert.ok(s.measure.exclude.includes(id), `${where}: ${other.id}'s entity ${id} is measured`);
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
      const behind = [...machine.named.sources, ...(machine.structure?.sources || []), ...(machine.per_cell || []).flatMap((item) => item.sources || [item.source])];
      for (const key of behind) {
        assert.ok(dossier.sources[key], `${species}, ${machine.kind}: ${key} is not a source`);
        assert.equal(dossier.sources[key].class, "permissive", `${species}, ${machine.kind}: ${key} is ${dossier.sources[key].class}`);
      }
      for (const item of machine.per_cell || []) {
        if (item.fact) continue;
        assert.ok(item.where && item.as_written.length && item.counts && item.cell, `${species}, ${machine.kind}: a number says what it counts, in what cell and where it stands`);
        const values = [item.value].flat();
        for (const value of values) assert.ok(item.as_written.some((said) => Number(said.replace(/,/g, "")) === value), `${species}, ${machine.kind}: ${value} is not as written`);
      }
    }
    const text = JSON.stringify(dossier);
    assert.doesNotMatch(text, MACHINE, `${species}: a path of this machine`);
  }
});

test("the tool writes the dossiers as they are, from the saved downloads", { skip: !SAVED && "the saved downloads are not on this machine" }, () => {
  const run = spawnSync("python3", ["-I", path.join(ROOT, "tools", "gather_machines.py"), "check", "--datasets", DATASETS], { encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr || run.stdout);
});
