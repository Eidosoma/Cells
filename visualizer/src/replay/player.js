// The playhead of a replay: a time in the run that plays, pauses and jumps. It knows
// nothing of drawing; the timeline, the sheet and the chart all listen to it.
//
// Events: "time" when the playhead moves, "state" when playing, speed or the run changes.

// Seconds of the run per second of watching: the speeds offered for the run shown. The list is
// refilled when a run is loaded, so whoever cycles through it offers the speeds that suit the run.
export const SPEEDS = [15, 60, 240];
const LONG = [15, 60, 240], SHORT = [0.25, 1, 4];

/**
 * The speeds a run of a given length is offered, slowest first; the middle one is the one it
 * opens at. A run of under two minutes opens at true speed: a second of watching is a second
 * of the run.
 */
export function speedsFor(seconds) {
  return seconds < 120 ? SHORT : LONG;
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
  }

  /** Point the player at a run (or at none), at the run's first record. */
  load(run) {
    this.run = run;
    this.start = run ? run.start : 0;
    this.end = run ? run.end : 0;
    this.time = this.start;
    this.playing = false;
    if (run) {
      const speeds = speedsFor(this.end - this.start);
      SPEEDS.splice(0, SPEEDS.length, ...speeds);
      if (!speeds.includes(this.speed)) this.speed = speeds[1];
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

  setSpeed(speed) {
    if (!(speed > 0) || speed === this.speed) return;
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
