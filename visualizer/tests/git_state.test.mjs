// What the page's tools take as an uncommitted change (tools/lib/git_state.mjs): every line of `git status --porcelain`
// but an untracked node_modules, which a checkout that links the folder shows though the ignore rule names it.
//
//   node --test tests/git_state.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { changedLines, hasChanges } from "../tools/lib/git_state.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("an untracked node_modules is no change of the page, wherever the folder stands; anything else is", () => {
  assert.equal(hasChanges(""), false);
  assert.equal(hasChanges("?? visualizer/node_modules\n"), false);
  assert.equal(hasChanges("?? node_modules"), false);
  assert.equal(hasChanges("?? visualizer/node_modules/"), false);
  assert.equal(hasChanges(" M visualizer/src/ui/viewer.js\n?? visualizer/node_modules"), true);
  assert.deepEqual(changedLines(" M visualizer/src/ui/viewer.js\n?? visualizer/node_modules\n"), [" M visualizer/src/ui/viewer.js"]);
  // A file that only ends like the folder's name is a change.
  assert.equal(hasChanges("?? visualizer/notes_node_modules"), true);
  assert.equal(hasChanges("?? visualizer/node_modules.txt"), true);
});

test("a status that could not be read is not called clean", () => {
  assert.equal(hasChanges(null), null);
  assert.equal(changedLines(undefined), null);
});

test("the tools that record whether a checkout was clean read it through this one rule", () => {
  for (const tool of ["tools/check_all.mjs", "tools/make_stills.mjs"]) {
    const text = readFileSync(path.join(ROOT, tool), "utf8");
    assert.match(text, /from "\.\/lib\/git_state\.mjs"/, tool);
    assert.doesNotMatch(text, /node_modules\\?\/\?\$/, `${tool} keeps no rule of its own`);
  }
});
