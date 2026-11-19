// The click runner's list of scenarios (tools/check_all.mjs --list): each named once, and the scenarios that hold a
// time bound marked to run alone, after the others (a frame's cost measured beside other browsers says more of them
// than of the page). Nothing is started: --list runs no scenario.
//
//   node --test tests/check_all_list.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const listed = spawnSync(process.execPath, [path.join(ROOT, "tools", "check_all.mjs"), "--list"], { cwd: ROOT, encoding: "utf8" });

test("--list names every scenario once and runs none", () => {
  assert.equal(listed.status, 0, listed.stderr);
  const names = listed.stdout.trim().split("\n").map((line) => line.split(/\s+/)[0]);
  assert.ok(names.length >= 100, `${names.length} scenarios`);
  assert.equal(new Set(names).size, names.length, "no name twice");
  assert.ok(!/scenarios on /.test(listed.stdout), "nothing was started");
});

test("a scenario that holds a frame's time bound runs alone, after the others", () => {
  const lines = listed.stdout.trim().split("\n");
  const frame = lines.filter((line) => /^[a-z0-9-]*-frame\s/.test(line));
  assert.ok(frame.length >= 1);
  for (const line of frame) assert.match(line, /\[alone, after the others\]/, line);
  // The runner starts them only when the others have ended, one at a time, and its summary names them.
  const text = readFileSync(path.join(ROOT, "tools", "check_all.mjs"), "utf8");
  assert.match(text, /const waiting = chosen\.filter\(\(item\) => !item\.alone\)/);
  assert.match(text, /await Promise\.all\(Array\.from\(\{ length: jobs \}, worker\)\);\nif \(apart\.length\) \{[\s\S]*?waiting\.push\(\.\.\.apart\);\n  await worker\(\);/);
  assert.match(text, /alone: apart\.map/);
});
