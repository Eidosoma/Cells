// The engine map reads what the engine declares from the engine's own manifest
// (data/engine/declarations.json, cells.declarations@3; data/engine/README.md), never from its
// registries: the manifest is the one written at the scene's revision, from a clean tree, and
// what the map draws as a declared operator, law, kind or model is in it. The reader's refusals
// are checked on made-up manifests.
//
//   node --test tests/engine_declarations.test.mjs

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const awaitedIds = await readFile(path.join(ROOT, "data/engine/viewer-ids.json"), "utf8");
const manifest = JSON.parse(await readFile(path.join(ROOT, "data", "engine", "declarations.json"), "utf8"));
const scene = JSON.parse(await readFile(path.join(ROOT, "data", "architecture", "architecture.scene.json"), "utf8"));

test("the manifest the map read was written at the scene's own revision, from a clean tree", () => {
  assert.equal(manifest.kind, "cells.declarations@3");
  assert.equal(manifest.dirty, false);
  assert.match(manifest.revision, /^[0-9a-f]{40}$/);
  // The scene's revision as the extractor read it from the checkout, not from the manifest: its links' base.
  const linked = scene.meta.source_base_url.match(/\/blob\/([0-9a-f]{40})\/$/)?.[1];
  assert.equal(linked, manifest.revision, "the scene is built at another revision than the manifest's");
  assert.ok(manifest.revision.startsWith(scene.meta.revision));
  assert.equal(scene.meta.declarations?.kind, manifest.kind);
  assert.equal(scene.meta.declarations?.revision, manifest.revision);
});

test("the composite's operators drawn are the manifest's, and nothing else is drawn as one", () => {
  const declared = manifest.pieces.filter((piece) => piece.piece === "operator" && piece.interface === "cells.operator@1").map((piece) => piece.declared_id);
  const drawn = scene.entities.filter((entity) => entity.kind === "operator").map((entity) => entity.id.replace(/^op\./, ""));
  assert.deepEqual([...drawn].sort(), [...declared].sort());
  // A module may declare two operators (cells.operator.species_regulated_availability@1 and @2 since main 93fc8c2c): its file stays the
  // part of the first the manifest lists, whose imports it draws, and each operator's detail names that operator only.
  for (const entity of scene.entities.filter((item) => item.kind === "operator")) {
    const named = /^(?:Operator )?([a-z_][a-z0-9_]*@\d+)\b/.exec(entity.detail || "")?.[1];
    if (named) assert.equal(named, entity.id.slice(3), `${entity.id}: its detail is another operator's`);
  }
  const modules = new Map();
  for (const piece of manifest.pieces.filter((item) => item.piece === "operator" && item.interface === "cells.operator@1")) modules.set(piece.module_path, [...(modules.get(piece.module_path) || []), piece.declared_id]);
  const users = new Set(scene.relations.filter((relation) => relation.kind === "uses").map((relation) => relation.from));
  for (const [file, laws] of modules) {
    if (laws.length < 2) continue;
    assert.ok(users.has(`op.${laws[0]}`), `${file}: the first operator, ${laws[0]}, keeps the file's imports`);
    for (const law of laws.slice(1)) assert.ok(!users.has(`op.${law}`), `${file}: ${law} draws no import of a file that is another's part`);
  }
});

test("the transcription-site assay is filed with its measurements and links to the expression operator", () => {
  const owners = scene.entities.filter((entity) => entity.files?.includes("src/cells/assays/transcription_sites.py"));
  assert.deepEqual(owners.map((entity) => entity.id), ["exp.transcription_sites"]);
  assert.ok(scene.relations.some((relation) => relation.from === owners[0].id
    && relation.to === "op.cells.operator.templated_polymerisation@1" && relation.kind === "reads"));
});

test("a model, law, kind or family operator is drawn as declared only if the manifest declares it; the older families' IDs are not drawn", () => {
  const models = new Set(manifest.models.map((model) => model.declared_id));
  // Laws, kinds and a family's own operators (an interface other than the composite's) are drawn on the part that holds their file.
  const own = manifest.pieces.filter((piece) => piece.piece !== "operator" || piece.interface !== "cells.operator@1");
  const pieces = new Map(own.map((piece) => [piece.declared_id, piece.piece]));
  const interfaces = new Map(own.map((piece) => [piece.declared_id, piece.interface]));
  const bookmarks = JSON.parse(awaitedIds);
  const legacy = new Set(bookmarks.historical.legacy.filter(id => !models.has(bookmarks.aliases[id])));
  const members = scene.entities.flatMap((entity) => (entity.members || []).map((member) => ({ ...member, part: entity.id })));
  const drawnModels = new Set();
  for (const member of members) {
    assert.ok(!legacy.has(member.label), `${member.part} draws ${member.label}, which the engine lists among the older families`);
    const said = /^(law|kind|operator)(?: \(([^)]+)\))?, declared in /.exec(member.detail || "");
    if (said) {
      assert.equal(pieces.get(member.label), said[1], `${member.part}: ${member.label}`);
      if (said[1] === "operator") assert.equal(said[2], interfaces.get(member.label), `${member.part}: ${member.label} names its family's interface`);
    }
    else if (/@\d+$/.test(member.label)) {
      assert.ok(models.has(member.label), `${member.part} draws ${member.label} as a model, which the manifest does not list`);
      drawnModels.add(member.label);
    }
  }
  assert.deepEqual([...drawnModels].sort(), [...models].sort(), "every model the engine declares is drawn");
  const drawnPieces = members.filter((member) => /^(law|kind|operator)( \([^)]+\))?, declared in /.test(member.detail || "")).map((member) => member.label);
  assert.deepEqual(drawnPieces.sort(), [...pieces.keys()].sort(), "every law, kind and family operator the engine declares is drawn once");
});

test("the reader refuses another major, another revision and a tree with changes, each in so many words", async (t) => {
  const folder = await mkdtemp(path.join(os.tmpdir(), "cells-declarations-"));
  t.after(() => rm(folder, { recursive: true, force: true }));
  const read = async (data, revision = manifest.revision) => {
    const file = path.join(folder, "declarations.json");
    await writeFile(file, JSON.stringify(data));
    const code = "import sys; sys.path.insert(0, sys.argv[1]); import extract_architecture as x; x.read_declarations(sys.argv[2], sys.argv[3])";
    const run = spawnSync("python3", ["-c", code, path.join(ROOT, "tools"), file, revision], { encoding: "utf8" });
    return { status: run.status, said: (run.stderr + run.stdout).trim() };
  };
  const ok = await read(manifest);
  assert.equal(ok.status, 0, ok.said);
  const cases = [
    [{ ...manifest, kind: "cells.declarations@4" }, manifest.revision, /a major this reader does not know/],
    [{ ...manifest, kind: "cells.relations@1" }, manifest.revision, /not the engine's declarations manifest/],
    [manifest, "0".repeat(40), /but the scene is built at 0{40}/],
    [{ ...manifest, dirty: true }, manifest.revision, /from a tree with changes/],
    [{ ...manifest, dirty: null }, manifest.revision, /from a tree with changes/],
  ];
  for (const [data, revision, says] of cases) {
    const run = await read(data, revision);
    assert.notEqual(run.status, 0, `${data.kind} ${data.dirty} at ${revision} was read`);
    assert.match(run.said, says);
    assert.doesNotMatch(run.said, /Traceback/, "a refusal is said, not a crash");
  }
});

test("an entry called modelled names a model the manifest lists with its declared structure", async () => {
  // schema/ENTRIES.md: "modelled" needs the record of main to say a registered model of it exists. The build checks the
  // model it names against the manifest; here, on the entries as they stand, and on a made-up one.
  const withRows = new Set(manifest.models.filter((model) => model.rows?.length).flatMap((model) => [model.declared_id, model.id]));
  const { readdir } = await import("node:fs/promises");
  for (const folder of ["models", "species", "cells"]) {
    const dir = path.join(ROOT, "data", folder);
    for (const name of (await readdir(dir).catch(() => [])).filter((file) => file.endsWith(".json"))) {
      const data = JSON.parse(await readFile(path.join(dir, name), "utf8"));
      if (data.modelled?.state === "modelled") assert.ok(withRows.has(JSON.parse(awaitedIds).aliases[data.modelled.model] || data.modelled.model), `${folder}/${name}: ${data.modelled.model}`);
    }
  }
  const code = [
    "import sys; sys.path.insert(0, sys.argv[1])",
    "from lib.entries import Entries",
    "entries = Entries({}, models={'cells.model.assembly_lineages@1'})",
    "block = lambda model: {'state': 'modelled', 'text': 't', 'record': [{'path': 'PROGRESS.md', 'where': 'x'}], 'design': 'docs/GARD_DESIGN.md', 'model': model}",
    "print(entries.modelled(block('cells.model.assembly_lineages@1'), 'model system', 'here'))",
    "print(entries.modelled(block('cells.model.resolved_tissue@1'), 'model system', 'here'))",
  ].join("\n");
  const run = spawnSync("python3", ["-c", code, path.join(ROOT, "tools")], { encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr);
  const [ok, refused] = run.stdout.trim().split("\n");
  assert.equal(ok, "[]");
  assert.match(refused, /cells.model.resolved_tissue@1.*not a model the engine's declarations list with its declared structure/);
});
