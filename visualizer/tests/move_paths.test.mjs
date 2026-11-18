// Carrying the engine map's paths through a move of the engine's source (tools/move_paths.py),
// on a made-up table: patterns re-formed under the new folders, cited sources moved, a stop for
// what needs an eye, and the ownership check before against after.
//
//   node --test tests/move_paths.test.mjs

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TOOL = path.join(ROOT, "tools", "move_paths.py");

const BEFORE = [
  "src/cells/models/surface_a.py",
  "src/cells/models/surface_b.py",
  "src/cells/models/surface_keep.py",
  "src/cells/core/x_excision.py",
  "src/cells/processes/lone.py",
  "src/cells/assembly_cell/__init__.py",
  "src/cells/assembly_cell/engine.py",
  "src/cells/core/old_spec.py",
  "src/cells/core/vanish.py",
  "src/cells/core/misc.py",
  "src/cells/models/operators/water.py",
  "docs/NOTE.md",
];
const MOVES = {
  "src/cells/models/surface_a.py": "src/cells/legacy/models/surface_a.py",
  "src/cells/models/surface_b.py": "src/cells/legacy/models/surface_b.py",
  "src/cells/core/x_excision.py": "src/cells/legacy/core/x_excision.py",
  "src/cells/processes/lone.py": "src/cells/legacy/processes/lone.py",
  "src/cells/assembly_cell/__init__.py": "src/cells/legacy/assembly_cell/__init__.py",
  "src/cells/assembly_cell/engine.py": "src/cells/legacy/assembly_cell/engine.py",
  "src/cells/core/old_spec.py": "src/cells/legacy/core/old_spec.py",
};
const CREATED = ["src/cells/legacy/__init__.py", "src/cells/legacy/models/__init__.py"];
const SPLIT = { kind: "split", commit: "abc1234", old: "src/cells/core/old_spec.py", new: "src/cells/core/values.py", names: ["positive"], note: "moved verbatim" };
const AFTER = [
  ...BEFORE.filter((file) => !(file in MOVES) && file !== "src/cells/core/vanish.py"),
  ...Object.values(MOVES),
  ...CREATED,
  SPLIT.new,
];

const TABLE = {
  kind: "cells.source_moves.path_table@1",
  move: "made-up-move",
  rows: [
    ...Object.entries(MOVES).map(([old, neu]) => ({ old, new: neu, kind: "move", to_legacy: true, old_module: null, new_module: null })),
    ...CREATED.map((neu) => ({ old: null, new: neu, kind: "created", to_legacy: true, old_module: null, new_module: null })),
    SPLIT,
  ],
};

const part = (id, match, more = {}) => ({ id, label: id, layer: "x", status: "established", match, plain: "", sources: [], ...more });
const OVERLAY = {
  operators: { items: { "water@1": { label: "Water", sources: [{ path: "src/cells/processes/lone.py" }] } } },
  capabilities: [{ id: "cap.x", sources: [{ path: "docs/NOTE.md" }] }],
  scales: [],
  components: [
    part("p.surface", ["src/cells/models/surface_*.py"]),
    part("p.excision", ["src/cells/core/*excision.py"]),
    part("p.lone", ["src/cells/processes/lone.py"], { sources: [{ path: "src/cells/processes/lone.py", where: "top" }] }),
    part("p.assembly", ["src/cells/assembly_cell/**"]),
    part("p.specs", ["src/cells/core/*_spec.py"]),
    part("p.vanish", ["src/cells/core/vanish.py"]),
    part("p.other", ["src/cells/core/*.py", "src/cells/*.py"], { catch_all: true }),
  ],
};
// The operator registry places this file, not a pattern.
const PREPLACED = { "src/cells/models/operators/water.py": "op.water@1" };

async function setUp() {
  const folder = await mkdtemp(path.join(os.tmpdir(), "move-paths-"));
  const write = (name, data) => writeFile(path.join(folder, name), typeof data === "string" ? data : JSON.stringify(data));
  await write("table.json", TABLE);
  await write("overlay.json", OVERLAY);
  await write("before.txt", BEFORE.join("\n"));
  await write("after.txt", AFTER.join("\n"));
  await write("preplaced.json", PREPLACED);
  return folder;
}

const tool = (folder, ...args) => spawnSync("python3", ["-I", TOOL, ...args], { cwd: folder, encoding: "utf8" });
const json = async (folder, name) => JSON.parse(await readFile(path.join(folder, name), "utf8"));

test("rewrite: each pattern's moved files get a pattern under their new folder, and the rest keep theirs", async () => {
  const folder = await setUp();
  try {
    const run = tool(folder, "rewrite", "--table", "table.json", "--overlay", "overlay.json", "--before", "before.txt", "--after", "after.txt", "--preplaced-before", "preplaced.json", "--out", "new.json", "--report", "report.json");
    assert.equal(run.status, 2, `it stops on what needs an eye: ${run.stdout}${run.stderr}`);
    const parts = Object.fromEntries((await json(folder, "new.json")).components.map((item) => [item.id, item.match]));
    // A glob that keeps a file in place keeps its pattern, and gains one for the files that moved.
    assert.deepEqual(parts["p.surface"], ["src/cells/models/surface_*.py", "src/cells/legacy/models/surface_*.py"]);
    assert.deepEqual(parts["p.excision"], ["src/cells/legacy/core/*excision.py"]);
    assert.deepEqual(parts["p.lone"], ["src/cells/legacy/processes/lone.py"]);
    assert.deepEqual(parts["p.assembly"], ["src/cells/legacy/assembly_cell/**"]);
    assert.deepEqual(parts["p.specs"], ["src/cells/legacy/core/*_spec.py"]);
    assert.deepEqual(parts["p.other"], ["src/cells/core/*.py", "src/cells/*.py"], "a catch-all that held no moved file is left alone");
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});

test("rewrite: cited sources follow their files, wherever they are cited, and a document that did not move is left", async () => {
  const folder = await setUp();
  try {
    tool(folder, "rewrite", "--table", "table.json", "--overlay", "overlay.json", "--before", "before.txt", "--after", "after.txt", "--preplaced-before", "preplaced.json", "--out", "new.json", "--report", "report.json");
    const overlay = await json(folder, "new.json");
    assert.deepEqual(overlay.components.find((item) => item.id === "p.lone").sources, [{ path: "src/cells/legacy/processes/lone.py", where: "top" }]);
    assert.deepEqual(overlay.operators.items["water@1"].sources, [{ path: "src/cells/legacy/processes/lone.py" }]);
    assert.deepEqual(overlay.capabilities[0].sources, [{ path: "docs/NOTE.md" }]);
    assert.equal((await json(folder, "report.json")).sources.length, 2);
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});

test("rewrite: it stops on a split, on a file the table does not name that is gone, on a part left empty and on a new file no part takes", async () => {
  const folder = await setUp();
  try {
    tool(folder, "rewrite", "--table", "table.json", "--overlay", "overlay.json", "--before", "before.txt", "--after", "after.txt", "--preplaced-before", "preplaced.json", "--out", "new.json", "--report", "report.json");
    const stops = (await json(folder, "report.json")).stops.map((stop) => `${stop.kind} ${stop.part} ${stop.path || ""}`.trim());
    assert.deepEqual(stops.sort(), [
      "empty part p.vanish",
      "gone p.vanish src/cells/core/vanish.py",
      "new file null src/cells/legacy/__init__.py",
      "new file null src/cells/legacy/models/__init__.py",
      "split p.specs src/cells/core/values.py",
    ]);
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});

test("check: with the stops answered, every file keeps its part at its new path, and the new files are named", async () => {
  const folder = await setUp();
  try {
    tool(folder, "rewrite", "--table", "table.json", "--overlay", "overlay.json", "--before", "before.txt", "--after", "after.txt", "--preplaced-before", "preplaced.json", "--out", "new.json");
    const overlay = await json(folder, "new.json");
    // A person's answers: the vanished part goes, the package files and the split's new file get parts.
    overlay.components = overlay.components.filter((item) => item.id !== "p.vanish");
    overlay.components.splice(0, 0, part("p.legacy", ["src/cells/legacy/__init__.py", "src/cells/legacy/models/__init__.py"]));
    overlay.components.find((item) => item.id === "p.specs").match.push("src/cells/core/values.py");
    const before = { ...OVERLAY, components: OVERLAY.components.filter((item) => item.id !== "p.vanish") };
    await writeFile(path.join(folder, "answered.json"), JSON.stringify(overlay));
    await writeFile(path.join(folder, "before-overlay.json"), JSON.stringify(before));
    await writeFile(path.join(folder, "before-left.txt"), BEFORE.filter((file) => file !== "src/cells/core/vanish.py").join("\n"));
    const run = tool(folder, "check", "--table", "table.json", "--before-overlay", "before-overlay.json", "--after-overlay", "answered.json", "--before", "before-left.txt", "--after", "after.txt", "--preplaced-before", "preplaced.json", "--preplaced-after", "preplaced.json", "--report", "check.json");
    assert.equal(run.status, 0, run.stdout + run.stderr);
    const report = await json(folder, "check.json");
    assert.equal(report.ok, true);
    assert.deepEqual(report.moved_with_their_part, { "p.assembly": 2, "p.excision": 1, "p.lone": 1, "p.specs": 1, "p.surface": 2 });
    assert.deepEqual(report.new_to_the_map.map((item) => `${item.path} ${item.part}`), [
      "src/cells/core/values.py p.specs",
      "src/cells/legacy/__init__.py p.legacy",
      "src/cells/legacy/models/__init__.py p.legacy",
    ]);
    assert.deepEqual(report.engine_files_unplaced, []);
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});

test("check: a file that lands in another part, and a new file only a catch-all takes, are each caught", async () => {
  const folder = await setUp();
  try {
    tool(folder, "rewrite", "--table", "table.json", "--overlay", "overlay.json", "--before", "before.txt", "--after", "after.txt", "--preplaced-before", "preplaced.json", "--out", "new.json");
    const overlay = await json(folder, "new.json");
    overlay.components = overlay.components.filter((item) => item.id !== "p.vanish");
    overlay.components.splice(0, 0, part("p.legacy", ["src/cells/legacy/__init__.py", "src/cells/legacy/models/__init__.py"]));
    // A planted mistake: the excision file is taken by an earlier part, and the split's file is left to the catch-all.
    overlay.components.splice(0, 0, part("p.thief", ["src/cells/legacy/core/x_*.py"]));
    const before = { ...OVERLAY, components: OVERLAY.components.filter((item) => item.id !== "p.vanish") };
    await writeFile(path.join(folder, "planted.json"), JSON.stringify(overlay));
    await writeFile(path.join(folder, "before-overlay.json"), JSON.stringify(before));
    await writeFile(path.join(folder, "before-left.txt"), BEFORE.filter((file) => file !== "src/cells/core/vanish.py").join("\n"));
    const run = tool(folder, "check", "--table", "table.json", "--before-overlay", "before-overlay.json", "--after-overlay", "planted.json", "--before", "before-left.txt", "--after", "after.txt", "--preplaced-before", "preplaced.json", "--preplaced-after", "preplaced.json", "--report", "check.json");
    assert.equal(run.status, 1);
    const report = await json(folder, "check.json");
    assert.deepEqual(report.changed_part, [{ path: "src/cells/core/x_excision.py", now: "src/cells/legacy/core/x_excision.py", was: "p.excision", is: "p.thief" }]);
    assert.deepEqual(report.catch_all_gains, [{ path: "src/cells/core/values.py", part: "p.other" }]);
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});

test("a file that is not a path table is refused", async () => {
  const folder = await setUp();
  try {
    await writeFile(path.join(folder, "not-a-table.json"), JSON.stringify({ kind: "cells.source_moves.map@1", rows: [] }));
    const run = tool(folder, "check", "--table", "not-a-table.json", "--before-overlay", "overlay.json", "--after-overlay", "overlay.json", "--before", "before.txt", "--after", "after.txt");
    assert.notEqual(run.status, 0);
    assert.match(run.stderr, /not a path table/);
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});

test("with a legacy folder set, the files under it need no part: left out and counted, never unplaced", async () => {
  const folder = await setUp();
  try {
    const legacy = { folder: "src/cells/legacy/", since: "2026-11-17", reason: "made-up reason" };
    await writeFile(path.join(folder, "overlay.json"), JSON.stringify({ ...OVERLAY, legacy }));
    const run = tool(folder, "rewrite", "--table", "table.json", "--overlay", "overlay.json", "--before", "before.txt", "--after", "after.txt", "--preplaced-before", "preplaced.json", "--out", "new.json", "--report", "report.json");
    assert.equal(run.status, 2);
    const stops = (await json(folder, "report.json")).stops.map((stop) => stop.kind);
    assert.ok(!stops.includes("new file"), "a package file the move made under the legacy folder is not a stop");
    const overlay = await json(folder, "new.json");
    overlay.components = overlay.components.filter((item) => item.id !== "p.vanish");
    overlay.components.find((item) => item.id === "p.specs").match.push("src/cells/core/values.py");
    await writeFile(path.join(folder, "answered.json"), JSON.stringify(overlay));
    await writeFile(path.join(folder, "before-overlay.json"), JSON.stringify({ ...OVERLAY, components: OVERLAY.components.filter((item) => item.id !== "p.vanish") }));
    await writeFile(path.join(folder, "before-left.txt"), BEFORE.filter((file) => file !== "src/cells/core/vanish.py").join("\n"));
    const check = tool(folder, "check", "--table", "table.json", "--before-overlay", "before-overlay.json", "--after-overlay", "answered.json", "--before", "before-left.txt", "--after", "after.txt", "--preplaced-before", "preplaced.json", "--preplaced-after", "preplaced.json", "--report", "check.json");
    assert.equal(check.status, 0, check.stdout + check.stderr);
    const report = await json(folder, "check.json");
    assert.deepEqual(report.engine_files_unplaced, []);
    assert.equal(report.engine_files_left_out_as_legacy, 9);
    assert.deepEqual(report.left_out_as_legacy_with_no_part, ["src/cells/legacy/__init__.py", "src/cells/legacy/models/__init__.py"]);
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});
