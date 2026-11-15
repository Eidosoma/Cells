// The playhead of a replay: a time in the run that plays, pauses and jumps. It knows
// nothing of drawing; the timeline, the sheet and the chart all listen to it.
//
// Events: "time" when the playhead moves, "state" when playing, speed or the run changes.

export const SPEEDS = [15, 60, 240]; // seconds of the run per second of watching

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
