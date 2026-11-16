// The playhead of a replay: a time in the run that plays, pauses and jumps. It knows
// nothing of drawing; the timeline, the sheet and the chart all listen to it.
//
// It is the replay's one clock. What moves on the picture (the beads of a layer on the
// motion channel) moves in the run's time as the playhead does: paused, it stands; played
// at a speed, as much of the run passes for the beads as for the playhead.
//
// Events: "time" when the playhead moves, "state" when playing, speed or the run changes.

/**
 * Seconds of the run per second of watching, slowest first: the ladder every run is offered
 * from. Below true speed a replay is slowed, so that a short run, and a bead of a fast flow,
 * can be followed; above it, a long run is made faster.
 */
export const LADDER = [1e-6, 1e-3, 0.25, 1, 4, 15, 60, 240];
/** A step faster than four times true speed is offered where the run still lasts this many seconds of watching. */
export const SHORTEST = 5;

// The speeds offered for the run shown. The list is refilled when a run is loaded, so whoever
// reads it offers the speeds that suit the run.
export const SPEEDS = [...LADDER];

/**
 * The speeds a run of a given length is offered, slowest first: every step below true speed,
 * true speed, four times faster, and each faster one under which the run still lasts five
 * seconds of watching. Every run can be slowed and made faster; a long run (39 minutes) is
 * offered the fast steps too.
 */
export function speedsFor(seconds) {
  return LADDER.filter((speed) => speed <= 4 || seconds / speed >= SHORTEST);
}

/**
 * The speed a run opens at, always one it is offered: true speed for a run under two minutes;
 * for a longer one a minute of the run each second, or the fastest step it is offered where
 * that is slower (a run of two to five minutes is not offered 60 times: it would be over in
 * under five seconds, so it opens at 15 times).
 */
export function openingSpeed(seconds) {
  if (seconds < 120) return 1;
  return Math.max(...speedsFor(seconds).filter((speed) => speed <= 60));
}

const count = (value) => Math.round(value).toLocaleString("en-US");

/** A stretch of time in words, for "one second here is … of the run". */
function span(seconds) {
  const say = (value, unit) => {
    const shown = Number(value.toPrecision(3));
    return shown === 1 ? `one ${unit}` : `${shown.toLocaleString("en-US")} ${unit}s`;
  };
  if (seconds >= 60) return say(seconds / 60, "minute");
  if (seconds >= 1) return say(seconds, "second");
  if (seconds >= 1e-3) return say(seconds * 1e3, "millisecond");
  if (seconds >= 1e-6) return say(seconds * 1e6, "microsecond");
  return say(seconds * 1e9, "nanosecond");
}

/**
 * How fast a replay runs, in the page's words: `short` for the timeline's button ("60×",
 * "1/1,000×"), `phrase` for the statement on the picture ("60 times faster", "slowed 1,000
 * times", "true speed"), and `says` in full, with what a second of watching is in the run.
 */
export function speedWords(speed) {
  if (!(speed > 0) || speed === 1) return { short: "1×", phrase: "true speed", says: "True speed: one second here is one second of the run" };
  if (speed > 1) return { short: `${count(speed)}×`, phrase: `${count(speed)} times faster`, says: `${count(speed)} times faster: one second here is ${span(speed)} of the run` };
  const slowed = count(1 / speed);
  return { short: `1/${slowed}×`, phrase: `slowed ${slowed} times`, says: `Slowed ${slowed} times: one second here is ${span(speed)} of the run` };
}

export class Player extends EventTarget {
  constructor() {
    super();
    this.run = null;
    this.time = 0;
    this.start = 0;
    this.end = 0;
    this.playing = false;
    this.speed = 60;
    this.chosen = false; // whether the visitor chose the speed: a chosen speed is kept from run to run where it is offered
  }

  /** Point the player at a run (or at none), at the run's first record. */
  load(run) {
    this.run = run;
    this.start = run ? run.start : 0;
    this.end = run ? run.end : 0;
    this.time = this.start;
    this.playing = false;
    if (run) {
      const length = this.end - this.start, speeds = speedsFor(length);
      SPEEDS.splice(0, SPEEDS.length, ...speeds);
      if (!this.chosen || !speeds.includes(this.speed)) this.speed = openingSpeed(length);
    }
    this.emit("state");
    this.emit("time");
  }

  get index() {
    return this.run ? this.run.indexAt(this.time) : 0;
  }

  get atEnd() {
    return this.time >= this.end;
  }

  seek(seconds) {
    const next = Math.min(this.end, Math.max(this.start, Number.isFinite(seconds) ? seconds : this.start));
    if (next === this.time) return;
    this.time = next;
    this.emit("time");
  }

  /** Jump to the record before or after the one shown. */
  step(direction) {
    if (!this.run) return;
    const index = this.index;
    const exact = this.run.t[index] === this.time;
    const target = direction > 0 ? Math.min(this.run.count - 1, index + 1) : exact ? Math.max(0, index - 1) : index;
    this.seek(this.run.t[target]);
  }

  play() {
    if (!this.run || this.playing) return;
    if (this.atEnd) this.time = this.start; // playing from the end starts over
    this.playing = true;
    this.emit("state");
    this.emit("time");
  }

  pause() {
    if (!this.playing) return;
    this.playing = false;
    this.emit("state");
  }

  toggle() {
    if (this.playing) this.pause();
    else this.play();
  }

  /** The visitor's choice of speed (seconds of the run each second of watching). */
  setSpeed(speed) {
    if (!(speed > 0)) return;
    this.chosen = true;
    if (speed === this.speed) return;
    this.speed = speed;
    this.emit("state");
  }

  /** Advance by a stretch of watching time, in milliseconds. Returns true while playing. */
  tick(milliseconds) {
    if (!this.playing) return false;
    const next = this.time + (milliseconds / 1000) * this.speed;
    if (next >= this.end) {
      this.time = this.end;
      this.playing = false;
      this.emit("time");
      this.emit("state");
      return false;
    }
    this.time = next;
    this.emit("time");
    return true;
  }

  emit(name) {
    this.dispatchEvent(new Event(name));
  }
}
