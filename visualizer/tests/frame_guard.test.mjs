// A frame that fails because its WebGL context was just lost does not stop the page's frames, and any other failure
// is still thrown (src/core/frame_guard.js, used by the stage's frame loop).
//
//   node --test tests/frame_guard.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { drawGuarded } from "../src/core/frame_guard.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("a frame that is drawn is drawn once, and says so", () => {
  let drawn = 0;
  assert.equal(drawGuarded(() => drawn++, () => false), true);
  assert.equal(drawn, 1);
});

test("a frame that fails while the context is lost is let go; one that fails with the context in hand is thrown on", () => {
  // What three.js throws when it reads a program's log from a lost context.
  const fail = () => {
    throw new TypeError("Cannot read properties of null (reading 'trim')");
  };
  assert.equal(drawGuarded(fail, () => true), false);
  assert.throws(() => drawGuarded(fail, () => false), /reading 'trim'/);
  // A context that cannot even be asked is not taken as lost: the failure is the page's to hear of.
  assert.throws(() => drawGuarded(fail, () => { throw new Error("no context"); }), /reading 'trim'/);
});

test("the stage draws every frame through the guard, and leaves the renderer's counts as it found them", () => {
  const stage = readFileSync(path.join(ROOT, "src", "core", "stage.js"), "utf8");
  assert.match(stage, /import \{ drawGuarded \} from "\.\/frame_guard\.js";/);
  assert.match(stage, /drawGuarded\(\(\) => this\.draw\(\), \(\) => this\.renderer\.getContext\(\)\.isContextLost\(\)\)/);
  assert.match(stage, /finally \{\s*info\.autoReset = true;/);
  // No other place of the frame loop calls draw unguarded.
  const frame = stage.slice(stage.indexOf("  frame(time) {"), stage.indexOf("  /** One picture:"));
  assert.equal((frame.match(/this\.draw\(\)/g) || []).length, 1);
});
