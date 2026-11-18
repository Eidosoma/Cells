// The tissue's play: a clock that follows what the runs in view state, not an even one. These runs change in moments
// separated by hours (at the line's threshold its cells turn between 729 and 19,300 s), so a clock
// that gives every second of the run the same time on the screen shows hours of nothing and then a change too quick
// to see. The play's schedule is built from the union of the stated state changes of the runs in view (each run's
// stated states, as its driver states them): each change's record is held on the screen for a stretch of its own
// (DWELL seconds of watching), the time between two changes is passed quickly (at most GAP seconds, and visibly so on
// the timeline, whose track is the play), and a whole play lasts about a minute or less. No moment is shown that no
// record holds: the picture shows a run's record at or before the clock, as every replay does.
//
// Nothing here draws or reads a colour: the changes are the driver's stated states, compared record to record.

import { speedWords, speedsFor } from "./player.js";
import { clock } from "./format.js";

export const DWELL = 2.2; // seconds of watching a stated change's record stays on the screen, at least
export const GAP = 1.0; // seconds of watching, at most, for the time between two changes
export const GAP_LEAST = 0.3; // and at least
export const IDLE = 12; // seconds of watching for a play with no stated change at all
/** The speed the clock "plays the changes" at, as the timeline names it: a tag, not a rate (its advance is the schedule's). */
export const FOLLOW = 1 / 7;

/**
 * The stated state changes of the runs in view, earliest first: each { time, record, arm, label, cell, name, number,
 * from, to, words }, read from each run's record of states (the driver's words for each cell at each record).
 * `items`: [{ arm, label, run, states, naming }], where `states` is the run's record of states (a Series with words)
 * and `naming` how a cell is named in the words: "number" (a line's "cell 6", counted from one along the view's order,
 * as the note's tables count them) or "id" (a sheet's cell by the run's own id, "c3_3").
 */
export function changesOf(items) {
  const out = [];
  for (const { arm, label, run, states, naming = "number" } of items) {
    if (!states) continue;
    const cells = run.sets.get("cell")?.ids || [];
    const width = states.width;
    for (let k = 1; k < run.count; k++) {
      for (let c = 0; c < width; c++) {
        const before = states.text(k - 1, c), after = states.text(k, c);
        if (before === after) continue;
        // "cell 6" counts from one along the view's own order, as the note's tables do; its id is the run's own.
        const name = cells[c] ?? String(c);
        out.push({ time: run.t[k], record: k, arm, label, cell: c, name, number: c + 1, from: before, to: after, words: `${naming === "id" ? name : `cell ${c + 1}`}: ${before} to ${after}` });
      }
    }
  }
  return out.sort((a, b) => a.time - b.time || a.cell - b.cell);
}

/**
 * The play's schedule over a run's saved times `t` (the runs in view share them): segments [{ from, to, seconds,
 * dwell }] that cover the run end to end. Each distinct time of a stated change starts a dwell segment, from that record
 * to the next, held DWELL seconds; the stretches between are passed in GAP_LEAST to GAP seconds, longer ones a little
 * longer. With no change, the whole run plays in IDLE seconds.
 */
export class Schedule {
  constructor(t, changes, { dwell = DWELL, gap = GAP, least = GAP_LEAST, idle = IDLE } = {}) {
    const start = t[0], end = t[t.length - 1];
    this.start = start;
    this.end = end;
    const times = [...new Set(changes.map((change) => change.time))].sort((a, b) => a - b);
    const next = (time) => {
      for (let k = 0; k < t.length; k++) if (t[k] > time + 1e-6) return t[k];
      return end;
    };
    const segments = [];
    const pass = (from, to) => {
      if (!(to > from)) return;
      // A stretch of the run between two changes: the longer, the longer it takes, within [least, gap], on a log of its length.
      const share = Math.min(1, Math.log10(1 + (to - from) / 100) / Math.log10(1 + (end - start) / 100 || 10));
      segments.push({ from, to, seconds: least + (gap - least) * share, dwell: false });
    };
    if (!times.length) {
      segments.push({ from: start, to: end, seconds: idle, dwell: false });
    } else {
      let at = start;
      for (const time of times) {
        if (time < at - 1e-9) continue;
        pass(at, time);
        const to = Math.min(end, next(time));
        segments.push({ from: time, to: to > time ? to : time, seconds: dwell, dwell: true, time });
        at = Math.max(at, to);
      }
      pass(at, end);
    }
    let watched = 0;
    for (const segment of segments) {
      segment.begins = watched;
      watched += segment.seconds;
    }
    this.segments = segments;
    this.total = watched;
    this.times = times;
  }

  /** The segment that holds a time of the run (the last one at its end). */
  segmentAt(time) {
    const { segments } = this;
    for (let k = 0; k < segments.length; k++) {
      const segment = segments[k];
      if (time < segment.to - 1e-9 || k === segments.length - 1) return segment;
    }
    return segments[segments.length - 1];
  }

  /** Where a time of the run stands in the play: 0 at its start, 1 at its end. */
  place(time) {
    const segment = this.segmentAt(time);
    const span = segment.to - segment.from;
    const within = span > 0 ? Math.min(1, Math.max(0, (time - segment.from) / span)) : 0;
    return Math.min(1, (segment.begins + within * segment.seconds) / this.total);
  }

  /** The time of the run at a place in the play (0 to 1). */
  timeAt(place) {
    const watched = Math.min(1, Math.max(0, place)) * this.total;
    for (const segment of this.segments) {
      if (watched <= segment.begins + segment.seconds + 1e-9) {
        const within = segment.seconds > 0 ? (watched - segment.begins) / segment.seconds : 0;
        return segment.from + Math.min(1, Math.max(0, within)) * (segment.to - segment.from);
      }
    }
    return this.end;
  }

  /** Where the clock is after `seconds` of watching, from `time`. */
  advance(time, seconds) {
    return this.timeAt(this.place(time) + seconds / this.total);
  }

  /** Seconds of the run each second of watching passes now: the rate the beads keep. */
  rateAt(time) {
    const segment = this.segmentAt(time);
    return segment.seconds > 0 ? Math.max(1e-9, (segment.to - segment.from) / segment.seconds) : 1;
  }
}

/**
 * The time base of the tissue's clock (src/replay/player.js, `timeBase`): it opens on FOLLOW, the schedule's play, and
 * offers the even speeds of any run of its length too. The timeline then draws its track as the play (`place`,
 * `timeAt`) while it follows the changes, and evenly otherwise.
 */
export function followBase(schedule) {
  const even = (time, seconds, speed) => time + seconds * speed;
  return Object.freeze({
    id: "follow",
    speedsFor: (length) => [FOLLOW, ...speedsFor(length).filter((speed) => speed >= 1)],
    openingSpeed: () => FOLLOW,
    words: (speed) =>
      speed === FOLLOW
        ? { short: "Changes", phrase: "following the stated changes", says: `Plays the stated changes: each is held ${DWELL} seconds, the time between two changes passes in a second or less, about ${Math.round(schedule.total)} seconds in all; the read-out gives the run's own time` }
        : speedWords(speed),
    clock: null,
    length: null,
    advance: (time, seconds, speed) => (speed === FOLLOW ? schedule.advance(time, seconds) : even(time, seconds, speed)),
    // The timeline's track: the play while it follows the changes, else the run's even time.
    place: (time, speed) => (speed === FOLLOW ? schedule.place(time) : (time - schedule.start) / Math.max(1e-9, schedule.end - schedule.start)),
    timeAt: (place, speed) => (speed === FOLLOW ? schedule.timeAt(place) : schedule.start + Math.min(1, Math.max(0, place)) * (schedule.end - schedule.start)),
    scale: (speed) => (speed === FOLLOW ? `The track is the play: each stated change ${DWELL} s, the hours between passed fast` : "The track is the run's own time, evenly"),
  });
}

/** The marks of the timeline: one for each distinct time of a change, with every change of that time named. */
export function marksOf(changes) {
  const byTime = new Map();
  for (const change of changes) {
    const list = byTime.get(change.time) || [];
    list.push(change);
    byTime.set(change.time, list);
  }
  return [...byTime].map(([time, list]) => ({ time, label: `${clock(time)}: ${list.map((change) => `${change.words} (${change.label})`).join("; ")}`, changes: list }));
}
