// The planarian's own scan of its proteins (docs/PLANARIAN_ATLAS.md, "The planarian's own scan"): what
// tools/read_planarian_scan.py makes of InterProScan's outputs, and how the machine dossiers' rule reads it
// (tools/gather_machines.py, schema/MACHINE_DOSSIERS.md). On a small fixture cut from the scan's finished test
// outputs (tests/fixtures/planarian-scan/, with made-up families for the rules): the reader's counts, its join and
// its two checks; the union of a line's own entries and the scan's reaching by_family and not newest; the database
// rule beside the number rule; a dossier by family with the scan and without it. On the tree's own two files: what
// stays true after the full run (every added entry names its databases and is new to its line, the record's counts
// are those of the file, the note's block is the record's).
//
//   node --test tests/planarian_scan.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { ROOT } from "../tools/lib/build_page.mjs";

const FIXTURE = path.join(ROOT, "tests", "fixtures", "planarian-scan");
const READER = path.join(ROOT, "tools", "read_planarian_scan.py");
const MACHINE = /\/home\/|\/mnt\/|\/Users\/|\/tmp\//;
const CLOCK = /\d{2}:\d{2}:\d{2}|T\d{2}:\d{2}/;
const python = (args, input) => spawnSync("python3", ["-I", ...args], { encoding: "utf8", input, maxBuffer: 64 * 1024 * 1024 });
const tsv = (text) => text.replace(/\n$/, "").split("\n").map((line) => line.split("\t"));
/** The added entries as the dossier tool reads them: {id: {entry: [databases]}}. */
const readAdded = (text) => {
  const [head, ...rows] = tsv(text);
  assert.deepEqual(head, ["id", "added"]);
  return Object.fromEntries(rows.map(([id, field]) => [id, Object.fromEntries(field.split(";").map((item) => [item.split(":")[0], item.split(":")[1].split(",")]))]));
};
const ownColumn = (file) => {
  const [head, ...rows] = tsv(readFileSync(file, "utf8"));
  const at = (name) => head.indexOf(name);
  return new Map(rows.map((row) => [row[at("id")], new Set(row[at("interpro")].split(";").filter(Boolean))]));
};

// The reader, run once on the fixture into a folder of its own.
const OUT = mkdtempSync(path.join(os.tmpdir(), "planarian-scan-"));
const built = python([READER, "build", "--scan", path.join(FIXTURE, "scan"), "--tool", path.join(FIXTURE, "tool"), "--datasets", path.join(FIXTURE, "datasets"), "--table", path.join(FIXTURE, "table.tsv"), "--out", OUT]);
const fixtureRecord = built.status === 0 ? JSON.parse(readFileSync(path.join(OUT, "interproscan.json"), "utf8")) : null;
const fixtureAdded = built.status === 0 ? readFileSync(path.join(OUT, "interproscan_added.tsv"), "utf8") : null;
test.after(() => rmSync(OUT, { recursive: true, force: true }));

test("the reader on the fixture: a chunk counts only with both outputs and exit 0, each database's proteins are those its pass ran on, and nothing is filtered", () => {
  assert.equal(built.status, 0, built.stderr);
  const record = fixtureRecord;
  assert.equal(record.format, "cells.visualizer.interpro_scan@1");
  assert.equal(record.tool.release, "5.78-109.0");
  assert.deepEqual(record.run.days, ["2026-11-18"], "the day is the outputs' own");
  // The first pass's chunk-01 was stopped once with PRINTS among its analyses; what counts is the start that ended with exit 0.
  assert.deepEqual(record.run.passes.pass1.analyses, ["Pfam", "SFLD", "HAMAP", "CATH-Gene3D", "NCBIfam", "AntiFam", "CDD", "Coils"]);
  assert.deepEqual(record.run.passes.pass1.chunks_counted, ["chunk-01", "chunk-02"]);
  // PANTHER's chunk-02 started and has no exit line and no outputs: its pass ran on 4 of the 8 proteins.
  assert.deepEqual(record.run.passes["pass2-panther"].chunks_counted, ["chunk-01"]);
  assert.deepEqual([record.databases.PANTHER.proteins_run, record.databases.PANTHER.of, record.databases.PANTHER.on_every_protein], [4, 8, false]);
  for (const name of ["Pfam", "PRINTS", "CDD", "NCBIfam", "SFLD", "HAMAP"]) assert.equal(record.databases[name].on_every_protein, true, name);
  // A database that ran and matched nothing is in the record, run on every protein, with no release the outputs could state.
  assert.deepEqual([record.databases.HAMAP.matches, record.databases.HAMAP.release], [0, null]);
  // Coils and AntiFam are counts only: no entries, no added, and Coils names no source (a program, with its terms said).
  for (const name of ["Coils", "AntiFam"]) assert.ok(record.databases[name].counts_only && !("added" in record.databases[name]) && !("entries_reached" in record.databases[name]), name);
  assert.ok(record.databases.Coils.matches > 0 && record.databases.Coils.terms && !record.databases.Coils.source);
  // Every file read is named by its place in the scan's folder and its SHA-256; nothing names this machine or a clock time.
  assert.ok(record.read.outputs.every((file) => /^out\/[\w-]+\/chunk-0\d\.(tsv|json)$/.test(file.file) && /^[0-9a-f]{64}$/.test(file.sha256)));
  assert.equal(record.read.outputs.length, 2 * 5);
  assert.doesNotMatch(JSON.stringify(record), MACHINE);
  assert.doesNotMatch(JSON.stringify(record), CLOCK);
  assert.equal(record.check_of_the_list.differences, 0, "the tool's list gives every pair of the outputs");
  assert.equal(record.tsv_and_json_differ, 0);
});

test("the reader on the fixture: an added entry keeps its databases, one the dossier's release does not hold is dropped and counted, and the table's own column is never an added entry", () => {
  const added = readAdded(fixtureAdded);
  const own = ownColumn(path.join(FIXTURE, "table.tsv"));
  assert.deepEqual(added.h1SMcG0000011, { IPR050216: ["PANTHER"], IPR055414: ["Pfam"] });
  // The fixture's table lacks IPR002155 on this line, which CDD and NCBIfam both find: the entry keeps both.
  assert.deepEqual(added.h1SMcG0000028, { IPR002155: ["CDD", "NCBIfam"] });
  // IPR059039 (found by Pfam on h1SMcG0000051) is not in the fixture's dossier release: dropped, and counted.
  assert.ok(!added.h1SMcG0000051);
  assert.deepEqual([fixtureRecord.entries.dropped_not_in_dossier_release.pairs, fixtureRecord.entries.dropped_not_in_dossier_release.entries], [1, 1]);
  for (const [id, entries] of Object.entries(added)) {
    for (const [entry, databases] of Object.entries(entries)) {
      assert.ok(!own.get(id).has(entry), `${id}: ${entry} is in its own column`);
      assert.ok(databases.length && databases.every((name) => fixtureRecord.databases[name]?.source), `${id}: ${entry}`);
    }
  }
  const pairs = Object.values(added).flatMap((entries) => Object.values(entries));
  assert.equal(fixtureRecord.entries.added, pairs.length);
  assert.equal(fixtureRecord.entries.added_by_cdd_alone, pairs.filter((names) => names.join() === "CDD").length);
  assert.equal(fixtureRecord.databases.CDD.added, pairs.filter((names) => names.includes("CDD")).length);
  // What each database could see, in the stated universe: the fixture's made-up families by their signatures.
  const sees = (name, family) => {
    const held = fixtureRecord.could_see.databases[name];
    return "with" in held ? held.with.split(" ").includes(family) : !held.without.split(" ").includes(family);
  };
  assert.ok(sees("Pfam", "IPR900001") && sees("Pfam", "IPR900006") && sees("PANTHER", "IPR900003") && sees("PANTHER", "IPR900005"));
  assert.ok(!["Pfam", "PANTHER", "CDD", "NCBIfam", "PRINTS"].some((name) => sees(name, "IPR900002") || sees(name, "IPR900004")), "a family whose only signature is PIRSF's, or that the tool's list lacks, no database run could see");
});

// The dossier's rule, through the tool's own functions, on the fixture's record and table.
const RULES = String.raw`
import json, sys
from collections import defaultdict
sys.path.insert(0, sys.argv[1] + "/tools")
import gather_machines as G
fixture, out = sys.argv[2], sys.argv[3]
d = G.P.Datasets(fixture + "/datasets")
families = G.Families(d)
atlas = {"table": fixture + "/table.tsv", "id": "id", "label": "name", "gene": "gene", "kind": "kind", "signatures": "interpro", "accessions": ["id", "match"], "match": "match", "length": "length"}
import csv
table = list(csv.DictReader(open(atlas["table"], encoding="utf-8"), delimiter="\t"))
scan = G.Scan({"record": out + "/interproscan.json", "added": out + "/interproscan_added.tsv"}, atlas["table"], {r["id"] for r in table}, families)
by_family, own_family, newest = G.lines_by_family(table, atlas, scan)
_, _, newest_alone = G.lines_by_family(table, atlas)
known = min(newest.values())
def level(f, s=scan, lines=by_family):
    hit, lvl, through = G.family_level(f, lines, known, families, s)
    return [hit, lvl, through]
result = {"newest": newest, "newest_alone": newest_alone, "complete": scan.complete,
          "carried": {e: sorted(by_family.get(e, [])) for e in ("IPR050216", "IPR055414", "IPR002155")},
          "own_carried": {e: sorted(own_family.get(e, [])) for e in ("IPR050216", "IPR055414", "IPR002155")},
          "levels": {f: {"scan": level(f), "head": level(f, None, own_family)} for f in ("IPR900001", "IPR900002", "IPR900003", "IPR900004", "IPR900005", "IPR900006", "IPR050216", "IPR000500")}}
# A whole dossier by family: a made-up reference machine whose parts' narrowest families are these, with the scan and without.
class Ref: pass
proteome = Ref()
proteome.interpro = {"P1": ["IPR050216"], "P2": ["IPR900001"], "P3": ["IPR900003"], "P4": ["IPR900006"], "P5": ["IPR900002"], "P6": ["IPR002155"]}
reference = {"proteome": proteome, "label": "Human"}
machine_ref = {"kind": "made", "proteins": {"columns": ["id", "gene", "label", "tier"], "rows": [[p, "G" + p[1:], None, "part"] for p in sorted(proteome.interpro)]}}
config = {"groups_proposed": []}
kinds = {"made": {"id": "made", "label": "Made-up machine", "group": "proteins"}}
block = {"atlas": atlas, "reference": "human", "lineage": [79327, "Schmidtea mediterranea"]}
dossiers = {}
for name, s in (("scan", scan), ("none", None)):
    sources = {}
    dossiers[name] = G.family_dossier(d, config, kinds, "planarian", block, machine_ref, reference, families, table, {}, "2026-11-18", defaultdict(list), sources, s)
    dossiers[name]["sources_added"] = sorted(sources)
result["dossiers"] = dossiers
result["head_note"] = G.SCAN_NOTE
print(json.dumps(result))
`;
const rules = built.status === 0 ? python(["-", ROOT, FIXTURE, OUT], RULES) : { status: 1, stderr: "the reader did not run" };
const ruled = rules.status === 0 ? JSON.parse(rules.stdout) : null;

test("the union of a line's own entries and the scan's reaches by_family and not newest", () => {
  assert.equal(rules.status, 0, rules.stderr);
  assert.deepEqual(ruled.newest, ruled.newest_alone, "newest reads the table's own column alone");
  assert.deepEqual(ruled.newest, { "gene model": "IPR900000" });
  assert.deepEqual(ruled.carried.IPR050216, ["h1SMcG0000011"], "an entry the scan added counts as carried by its line");
  assert.deepEqual(ruled.own_carried.IPR050216, [], "and is not in the line's own column");
  assert.deepEqual(ruled.carried.IPR002155, ["h1SMcG0000028"]);
  assert.deepEqual(ruled.complete, ["Pfam", "PRINTS", "SFLD", "HAMAP", "CATH-Gene3D", "NCBIfam", "CDD"], "the databases run on every protein; PANTHER's pass is not finished");
});

test("the database rule beside the number rule: settled only by a database run on every protein that has a signature in the family", () => {
  const { levels } = ruled;
  // Its database ran on every protein and found nothing: not in the table, through that database.
  assert.deepEqual(levels.IPR900001.scan, [null, "not in the table", ["Pfam"]]);
  assert.deepEqual(levels.IPR900001.head, [null, "cannot tell", null]);
  // Its only signature is in a database that was not run (PIRSF), or the tool's list lacks it: cannot tell, as before.
  assert.deepEqual(levels.IPR900002.scan, [null, "cannot tell", null]);
  assert.deepEqual(levels.IPR900004.scan, [null, "cannot tell", null]);
  // Its only signature is PANTHER's, whose pass is incomplete: as before, broader where a broader family is carried, else cannot tell.
  assert.deepEqual(levels.IPR900003.scan, levels.IPR900003.head);
  assert.deepEqual(levels.IPR900003.scan, ["IPR900000", "broader", null]);
  assert.deepEqual(levels.IPR900005.scan, [null, "cannot tell", null]);
  // Broader before, and now seen absent on every protein: not in the table, so the broader family's candidates are no longer taken.
  assert.deepEqual(levels.IPR900006.head, ["IPR900000", "broader", null]);
  assert.deepEqual(levels.IPR900006.scan, [null, "not in the table", ["Pfam"]]);
  // An entry only the scan carries is matched narrowest; the number rule alone placed it "not in the table".
  assert.deepEqual(levels.IPR050216.scan, ["IPR050216", "narrowest", null]);
  assert.deepEqual(levels.IPR050216.head, [null, "not in the table", null]);
  // A family numbered at or below what every group carries: the number rule, with or without the scan.
  assert.deepEqual(levels.IPR000500.scan, [null, "not in the table", null]);
});

test("a dossier by family with the scan says which family rests on it and through which databases; without it, nothing of the scan", () => {
  const withScan = ruled.dossiers.scan, without = ruled.dossiers.none;
  // The rows keep their columns, and each family row its five.
  assert.deepEqual(withScan.looked_for.columns, without.looked_for.columns);
  assert.deepEqual(withScan.proteins.columns, ["id", "gene", "label", "kind", "families", "stands_for", "same_as", "how"]);
  for (const row of withScan.looked_for.rows) for (const level of row[3]) assert.equal(level.length, 5);
  const scan = withScan.looked_for.scan;
  assert.deepEqual(scan.rests_on_it, [["IPR002155", "narrowest", ["CDD", "NCBIfam"]], ["IPR050216", "narrowest", ["PANTHER"]], ["IPR900001", "not in the table", ["Pfam"]], ["IPR900006", "not in the table", ["Pfam"]]]);
  assert.equal(scan.family_rows_changed, 4);
  assert.deepEqual(scan.candidates_only_by_it, ["h1SMcG0000011", "h1SMcG0000028"]);
  // h1SMcG0000009 carries IPR900000, the broader family of IPR900006 and of IPR900003: it stands for the part of IPR900006 no
  // longer (that family is seen absent on every protein), and still for the part of IPR900003 (PANTHER's pass is not finished).
  assert.deepEqual(scan.candidates_lost_by_part, [["G4", ["h1SMcG0000009"]]]);
  assert.deepEqual(scan.no_longer_candidates, []);
  const standsFor = (dossier, id) => dossier.proteins.rows.find((row) => row[0] === id)?.[5];
  assert.deepEqual([standsFor(withScan, "h1SMcG0000009"), standsFor(without, "h1SMcG0000009")], [["G3"], ["G3", "G4"]]);
  const how = Object.fromEntries(withScan.proteins.rows.map((row) => [row[0], row[7]]));
  assert.match(how.h1SMcG0000011, /^by the narrowest family, which only the entries the species' own scan added to its line carry \(PANTHER\)$/);
  assert.match(how.h1SMcG0000028, /\(CDD, NCBIfam\)$/);
  // Each database a value rests on is a source, with the record's terms; CDD among them, of no stated terms.
  assert.deepEqual(withScan.sources_added, ["scan_cdd", "scan_interpro", "scan_ncbifam", "scan_panther", "scan_pfam"]);
  assert.deepEqual(withScan.named.sources.slice(3), withScan.sources_added);
  // The machine's sentence keeps the number rule's words, its numbers the rows' own (the catalogue counts them again).
  assert.doesNotMatch(withScan.named.text, /scan_|own scan|InterProScan/);
  assert.match(withScan.named.text, /^3 of the species' proteins carry the narrowest InterPro family .* of at least one of the 6 parts .*For 2 no line of the species' table carries the family.*for 1 the table can tell nothing, its scan being older than the family; 0 have no family signature to look for\.$/);
  assert.equal(withScan.looked_for.note, ruled.head_note);
  // Without a scan: no field, word or source of it; the candidate by IPR900000 stands for the part of IPR900006, as before.
  assert.ok(!("scan" in without.looked_for) && without.sources_added.length === 0 && without.named.sources.length === 3);
  assert.doesNotMatch(JSON.stringify(without), /scan_|own scan|InterProScan/);
  assert.ok(without.proteins.rows.some((row) => row[0] === "h1SMcG0000009" && row[7] === "by a broader family"));
  assert.ok(without.proteins.rows.every((row) => /^by (the narrowest|a broader) family$/.test(row[7])));
});

// The tree's own two files: what stays true after the full run.
const RECORD = JSON.parse(readFileSync(path.join(ROOT, "data", "proteins", "planarian", "interproscan.json"), "utf8"));
const ADDED = readAdded(readFileSync(path.join(ROOT, "data", "proteins", "planarian", "interproscan_added.tsv"), "utf8"));
const OWN = ownColumn(path.join(ROOT, "data", "proteins", "planarian", "predicted_proteins.tsv"));

test("the tree's scan files: every added entry names its databases and is new to its line, and the record's counts are the file's", () => {
  assert.equal(RECORD.run.proteins, OWN.size);
  assert.equal(RECORD.run.table.file, "data/proteins/planarian/predicted_proteins.tsv");
  const pairs = [];
  for (const [id, entries] of Object.entries(ADDED)) {
    assert.ok(OWN.has(id), `${id} is not a line of the table`);
    for (const [entry, databases] of Object.entries(entries)) {
      assert.match(entry, /^IPR\d{6}$/);
      assert.ok(!OWN.get(id).has(entry), `${id}: ${entry} is already in its own column`);
      assert.ok(databases.length && databases.every((name) => RECORD.databases[name] && !RECORD.databases[name].counts_only), `${id}: ${entry} names no database of the record`);
      assert.deepEqual(databases, [...databases].sort(), `${id}: ${entry}`);
      pairs.push(databases);
    }
  }
  assert.equal(RECORD.entries.added, pairs.length);
  assert.equal(RECORD.entries.proteins_gaining, Object.keys(ADDED).length);
  assert.equal(RECORD.entries.added_by_ncbifam_alone, pairs.filter((names) => names.join() === "NCBIfam").length);
  assert.equal(RECORD.entries.added_by_cdd_alone, pairs.filter((names) => names.join() === "CDD").length);
  for (const [name, item] of Object.entries(RECORD.databases)) {
    if (item.counts_only) continue;
    assert.equal(item.added, pairs.filter((names) => names.includes(name)).length, name);
    assert.equal(item.added_by_it_alone, pairs.filter((names) => names.join() === name).length, name);
    // A database's pass ran on at most every protein, and on every protein only where it says so.
    assert.ok(item.proteins_run <= item.of && item.on_every_protein === (item.proteins_run === item.of), name);
    assert.ok(item.proteins_matched <= item.proteins_run && (item.proteins_run > 0 || item.matches === 0), name);
  }
  assert.equal(RECORD.check_of_the_list.differences, 0, "the tool's list gives every signature-to-entry pair of the outputs");
  assert.doesNotMatch(JSON.stringify(RECORD), MACHINE);
  assert.doesNotMatch(JSON.stringify(RECORD), CLOCK);
  const size = readFileSync(path.join(ROOT, "data", "proteins", "planarian", "interproscan.json")).length;
  assert.ok(size < 1.2 * 1024 * 1024, `the record is ${size} bytes`);
});

test("the note's block is the record's, and the note names the sources that are not plainly permissive", () => {
  const run = python([READER, "note", "--check"]);
  assert.equal(run.status, 0, run.stderr);
  const note = readFileSync(path.join(ROOT, "docs", "PLANARIAN_ATLAS.md"), "utf8");
  for (const name of ["NCBIfam", "CDD", "share-alike", "18 November 2026"]) assert.ok(note.includes(name), name);
  assert.ok(RECORD.sources.ncbifam?.licence.includes("share-alike") && RECORD.sources.cdd?.class === "no stated terms");
});
