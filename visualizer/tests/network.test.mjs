// The junctions of a replay's sheet drawn as a network (src/layers/marks/network.js): each line's
// width is the junction's own number on a stated scale; a shut one is a fainter hairline.
//
//   node --test tests/network.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { fullOf, lineOf, isGate, WIDTH, SHUT, SPAN, network } from "../src/layers/marks/network.js";
import { MARKS } from "../src/layers/marks/index.js";

test("a junction's line is as wide as its number on a stated scale: a gate from shut to fully open, any other number up to a round top", () => {
  assert.equal(MARKS.network, network);
  assert.deepEqual([network.channels, network.lives_on], [["links"], ["junction"]]);
  assert.ok(isGate({ id: "junction_gate", unit: "1" }) && isGate({ id: "junction_gate", unit: "" }) && !isGate({ id: "junction_conductance_S", unit: "S" }));
  assert.equal(fullOf({ id: "junction_gate", unit: "1" }, [0.2, 0.4]), 1, "a gate's scale is nought to one, whatever the run's largest");
  assert.equal(fullOf({ id: "junction_conductance_S", unit: "S" }, [3e-9, 7.3e-9]), 8e-9, "a conductance's top is a round number at or above the largest");
  assert.deepEqual(lineOf(1, 1), { share: 1, width: WIDTH.most, shut: false });
  assert.deepEqual(lineOf(0, 1), { share: 0, width: WIDTH.least, shut: true });
  const half = lineOf(0.5, 1);
  assert.ok(Math.abs(half.width - (WIDTH.least + WIDTH.most) / 2) < 1e-12 && !half.shut);
  assert.equal(lineOf(SHUT / 2, 1).shut, true);
  assert.equal(lineOf(Number.NaN, 1), null, "no number, no line");
  assert.ok(SPAN > 0.5 && SPAN < 1, "a line stops short of each cell's middle, so a row of junctions reads one by one");
});
