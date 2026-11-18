// The tissue's play (src/replay/tissue_play.js): the clock follows the driver's stated changes. Each change is read
// record to record from the stated states, named by the cell's number along a line or by the run's own id on a sheet;
// each distinct time of a change is held DWELL seconds of watching, the stretches between are passed in GAP_LEAST to GAP
// seconds; the track is the play, and a time and its place on the track go both ways; the marks are the changes, those
// of one record together.
//
//   node --test tests/tissue_play.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { changesOf, Schedule, followBase, marksOf, DWELL, GAP, GAP_LEAST, IDLE, FOLLOW } from "../src/replay/tissue_play.js";

/** A run of three cells with its stated states, as the replay holds them: a record of words per cell and time. */
function runOf(t, states, ids = ["c0", "c1", "c2"]) {
  return {
    run: { t: Float32Array.from(t), count: t.length, sets: new Map([["cell", { ids }]]) },
    states: { width: ids.length, text: (k, c) => states[k][c] },
  };
}

const T = [0, 1, 10, 100, 1000, 10000, 20000];
const line = runOf(T, [["M", "E", "E"], ["M", "E", "E"], ["M", "E", "E"], ["X", "E", "E"], ["X", "E", "E"], ["E", "E", "E"], ["E", "E", "E"]]);
const other = runOf(T, [["M", "M", "E"], ["M", "M", "E"], ["M", "M", "E"], ["M", "X", "E"], ["M", "X", "E"], ["M", "X", "E"], ["M", "X", "E"]], ["c3_3", "c3_4", "c3_5"]);

test("the stated changes are read record to record, a line's cell by its number and a sheet's by its id", () => {
  const changes = changesOf([
    { arm: "a", label: "D = 1", ...line },
    { arm: "b", label: "D = 2", ...other, naming: "id" },
  ]);
  assert.deepEqual(changes.map((change) => [change.time, change.arm, change.words]), [
    [100, "a", "cell 1: M to X"],
    [100, "b", "c3_4: M to X"],
    [10000, "a", "cell 1: X to E"],
  ]);
  assert.deepEqual(changesOf([{ arm: "a", label: "x", run: line.run, states: null }]), [], "a run with no stated states has no changes");
});

test("each time of a change is held DWELL seconds; the stretches between pass in GAP_LEAST to GAP; a place and a time go both ways", () => {
  const changes = changesOf([{ arm: "a", label: "D = 1", ...line }, { arm: "b", label: "D = 2", ...other, naming: "id" }]);
  const schedule = new Schedule(T, changes);
  const dwell = schedule.segments.filter((segment) => segment.dwell);
  assert.deepEqual(dwell.map((segment) => [segment.time, segment.from, segment.to, segment.seconds]), [[100, 100, 1000, DWELL], [10000, 10000, 20000, DWELL]], "one stretch for each time of a change, from its record to the next, the changes of one record together");
  for (const segment of schedule.segments.filter((item) => !item.dwell)) assert.ok(segment.seconds >= GAP_LEAST - 1e-12 && segment.seconds <= GAP + 1e-12, JSON.stringify(segment));
  assert.equal(schedule.total, schedule.segments.reduce((sum, segment) => sum + segment.seconds, 0));
  assert.deepEqual([schedule.place(0), schedule.place(20000)], [0, 1]);
  for (const time of [0, 5, 100, 550, 1000, 9999, 10000, 15000, 20000]) assert.ok(Math.abs(schedule.timeAt(schedule.place(time)) - time) < 1e-6 * Math.max(1, time), `${time}`);
  for (let k = 1; k < T.length; k++) assert.ok(schedule.place(T[k]) > schedule.place(T[k - 1]), "the track runs one way");
  // Watching a change's record: the clock stays in it for DWELL seconds of watching.
  const start = schedule.place(100) * schedule.total;
  assert.ok(Math.abs(schedule.timeAt((start + DWELL - 0.01) / schedule.total) - 1000) < 10 && schedule.timeAt((start + DWELL - 0.01) / schedule.total) < 1000);
  assert.ok(Math.abs(schedule.advance(100, DWELL) - 1000) < 1e-6);
  // With no change at all, the whole run in IDLE seconds.
  assert.equal(new Schedule(T, []).total, IDLE);
});

test("the time base opens on the play, offers the even speeds too, and draws its track as the play while it follows", () => {
  const schedule = new Schedule(T, changesOf([{ arm: "a", label: "D = 1", ...line }]));
  const base = followBase(schedule);
  assert.equal(base.openingSpeed(), FOLLOW);
  assert.equal(base.speedsFor(20000)[0], FOLLOW);
  assert.ok(base.speedsFor(20000).slice(1).every((speed) => speed >= 1));
  assert.equal(base.words(FOLLOW).short, "Changes");
  assert.equal(base.place(100, FOLLOW), schedule.place(100));
  assert.equal(base.place(10000, 1), 0.5, "at an even speed the track is the run's own time");
  assert.equal(base.advance(0, 2, 10), 20);
});

test("the timeline's marks: one for each time of a change, every change of that time named with its run", () => {
  const changes = changesOf([{ arm: "a", label: "D = 1", ...line }, { arm: "b", label: "D = 2", ...other, naming: "id" }]);
  const marks = marksOf(changes);
  assert.deepEqual(marks.map((mark) => [mark.time, mark.changes.length]), [[100, 2], [10000, 1]]);
  assert.match(marks[0].label, /cell 1: M to X \(D = 1\); c3_4: M to X \(D = 2\)$/);
});
