// What the page says it is busy with (src/core/busy.js, the viewer's busy()), held without a browser on made-up states:
// each reason the page keeps is said when it holds and only then, none at rest, and asking changes nothing. A few
// milliseconds.
//
//   node --test tests/busy.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { busyReasons } from "../src/core/busy.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const atRest = () => ({
  model: {},
  current: { loading: false, pending: null, fetching: new Set(), mounted: { opening: null } },
  landingView: { fetching: null },
  stage: { rig: { flight: null }, needsRender: false, moving: false, running: false },
});

test("at rest the page says nothing; each thing it is busy with is said while it holds, and only then", () => {
  assert.deepEqual(busyReasons(atRest()), []);
  const cases = [
    ["the scene is not yet in", (v) => (v.model = null)],
    ["the view is loading", (v) => (v.current.loading = true)],
    ["a run is on its way", (v) => (v.current.pending = { id: "run", promise: Promise.resolve() })],
    ["a layer's records are on their way", (v) => v.current.fetching.add("voltage")],
    ["a family is opening", (v) => (v.current.mounted.opening = Promise.resolve())],
    ["the landing's cards are on their way", (v) => (v.landingView.fetching = Promise.resolve())],
    ["the camera is in flight", (v) => (v.stage.rig.flight = { elapsed: 0, duration: 600 })],
    ["a frame is owed", (v) => (v.stage.needsRender = true)],
    ["a view is moving", (v) => (v.stage.moving = true)],
  ];
  for (const [reason, make] of cases) {
    const viewer = atRest();
    make(viewer);
    assert.deepEqual(busyReasons(viewer), [reason], reason);
  }
  // Several at once, each said.
  const viewer = atRest();
  for (const [, make] of cases.slice(1)) make(viewer);
  assert.deepEqual(busyReasons(viewer), cases.slice(1).map(([reason]) => reason));
});

test("a page with no view, no landing or no stage yet is read as it stands", () => {
  assert.deepEqual(busyReasons({ model: {} }), []);
  assert.deepEqual(busyReasons({}), ["the scene is not yet in"]);
  assert.deepEqual(busyReasons(null), ["the scene is not yet in"]);
});

test("asking changes nothing: the state read is the state left", () => {
  const viewer = atRest();
  viewer.stage.needsRender = true;
  viewer.current.fetching.add("voltage");
  const before = JSON.stringify({ ...viewer, current: { ...viewer.current, fetching: [...viewer.current.fetching] } });
  for (let n = 0; n < 3; n++) busyReasons(viewer);
  assert.equal(JSON.stringify({ ...viewer, current: { ...viewer.current, fetching: [...viewer.current.fetching] } }), before);
  assert.doesNotMatch(readFileSync(path.join(ROOT, "src", "core", "busy.js"), "utf8").replace(/\/\/.*$|\/\*[\s\S]*?\*\//gm, ""), /\b(?:invalidate|requestAnimationFrame|setTimeout|addEventListener|delete)\b|\.[A-Za-z_$][\w$]*\s*=(?!=)|\.(?:add|clear|set)\(/, "it only reads: it calls nothing of the page and sets no property");
});

test("the viewer answers busy() with these reasons", () => {
  const text = readFileSync(path.join(ROOT, "src", "ui", "viewer.js"), "utf8");
  assert.match(text, /import \{ busyReasons \} from "\.\.\/core\/busy\.js";/);
  assert.match(text, /\n  busy\(\) \{\n    return busyReasons\(this\);\n  \}\n/);
});
