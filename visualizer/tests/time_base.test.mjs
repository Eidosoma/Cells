// The player's time base (src/replay/player.js): a run that names none keeps seconds, exactly as
// before; a run that counts steps of its own (an assembly run's fissions) is offered its own ladder
// and words, and a speed chosen in one base is never carried into another.

import test from "node:test";
import assert from "node:assert/strict";
import { Player, SPEEDS, SECONDS, baseOf, countedBase, speedWords, speedsFor, openingSpeed } from "../src/replay/player.js";

const fakeRun = (length, timeBase) => ({ start: 0, end: length, t: Array.from({ length: Math.floor(length) + 1 }, (_, k) => k), count: Math.floor(length) + 1, indexAt: (time) => Math.floor(time), events: [], timeBase });
const fine = { speed: 1 / 1000, words: { short: "step by step", phrase: "one event at a time", says: "One event at a time: four events a second" }, advance: (time, seconds) => time + seconds * 0.01 };
const counted = countedBase({ id: "steps", unit: "step", plural: "steps", ladder: [0.25, 0.5, 1, 2, 4, 8], opening: 0.5, fine });

test("a run that names no time base keeps seconds: the same speeds and words as before", () => {
  assert.equal(baseOf(null), SECONDS);
  assert.equal(baseOf(fakeRun(600)), SECONDS);
  assert.equal(SECONDS.words, speedWords);
  assert.deepEqual(SECONDS.speedsFor(600), speedsFor(600));
  assert.equal(SECONDS.openingSpeed(600), openingSpeed(600));
  const player = new Player();
  player.load(fakeRun(600));
  assert.equal(player.speed, openingSpeed(600));
  assert.deepEqual([...SPEEDS], speedsFor(600));
  assert.deepEqual(player.words, speedWords(player.speed));
  player.play();
  player.tick(1000);
  assert.equal(player.time, player.speed, "a second of watching is speed seconds of the run, as before");
});

test("a counted base: its own ladder, its opening step, and words that never speak of true speed", () => {
  assert.deepEqual(counted.speedsFor(120), [fine.speed, 0.25, 0.5, 1, 2, 4, 8]);
  assert.equal(counted.openingSpeed(120), 0.5);
  assert.deepEqual(counted.words(0.5), { short: "½/s", phrase: "½ step a second", says: "½ step each second of watching" });
  assert.equal(counted.words(1).phrase, "1 step a second");
  assert.equal(counted.words(8).phrase, "8 steps a second");
  assert.equal(counted.words(fine.speed), fine.words, "the fine step keeps the run's own words");
  for (const speed of counted.speedsFor(120)) assert.ok(!/true speed|slowed|times faster|×/.test(JSON.stringify(counted.words(speed))), `${speed}: ${JSON.stringify(counted.words(speed))}`);
  assert.equal(counted.clock(37.64), "37.6");
  assert.equal(counted.length(120.15), "120 steps");
  // Without a fine step, none is offered.
  const plain = countedBase({ id: "steps", unit: "step", plural: "steps", ladder: [0.5, 1], opening: 1 });
  assert.deepEqual(plain.speedsFor(10), [0.5, 1]);
});

test("a speed chosen in one time base is not carried into another", () => {
  const player = new Player();
  player.load(fakeRun(600));
  player.setSpeed(4); // four times true speed, on a replay
  player.load(fakeRun(120, counted));
  assert.equal(player.speed, 0.5, "the counted run opens at its own step, not at four steps a second");
  assert.deepEqual([...SPEEDS], counted.speedsFor(120));
  player.setSpeed(2);
  player.load(fakeRun(100, counted));
  assert.equal(player.speed, 2, "within one base a chosen speed is kept where it is offered");
  player.load(fakeRun(600));
  assert.equal(player.speed, openingSpeed(600), "and back on a replay the replay's own opening speed");
  assert.deepEqual([...SPEEDS], speedsFor(600));
});

test("the playhead moves by the base's own step where it has one", () => {
  const player = new Player();
  player.load(fakeRun(120, counted));
  player.play();
  player.tick(2000);
  assert.equal(player.time, 1, "half a step a second, for two seconds");
  player.setSpeed(fine.speed);
  const before = player.time;
  player.tick(1000);
  assert.ok(Math.abs(player.time - (before + 0.01)) < 1e-12, "the fine step advances as the run says, not by its number");
  player.seek(119.995);
  player.setSpeed(8);
  assert.equal(player.tick(1000), false, "the end stops the playhead");
  assert.equal(player.time, 120);
});
