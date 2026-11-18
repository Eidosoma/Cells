// The gap-junction example's tissue line, read for the picture: a line of cells run at several
// strengths of coupling, each run a package of the engine's with the quantity its driver states
// beside it (a criterion's quantity and each cell's state), and the picks an engine check refused,
// named and never drawn as runs. Nothing here needs the 3D stage, so it is tested without one.
//
// What it reads is the catalogue's (schema/RUN_VIEW.md, "A part of an example"): the entry's
// sweep gives each run's value of the parameter and its order; the entry's `refused_picks` name the
// picks an engine check refused, by their value of that parameter alone; the entry's `tissue` gives
// the record's words (what the page may say, which cells are the tumor, each run's end states in
// the record's table), each with its source. The viewer works nothing out: no state is read from a
// colour, no count is made, no front is found. The colour of a value is placed on a scale whose
// breaks are the criterion's own thresholds; a cell's state is the driver's, as stated.

import { clock, unitSign } from "./format.js";

export const PART = "part:"; // the id of a part of an example shown in the Experiments tab's place (`part:<entry id>`)
const TIME_SLACK = 5e-4; // seconds: record times are stored as 32-bit numbers (src/replay/run.js)

/** The catalogue entries that are parts of an experiment (`part_of`), in the catalogue's order, each with runs. */
export function partsOf(raw, experimentId) {
  if (!experimentId) return [];
  const runs = raw?.runs || [];
  // A part drawn inside another's view (`tissue.walk_of`: the ladder, in the line's) is no door of its own.
  return (raw?.experiments || []).filter((item) => item.part_of === experimentId && item.tissue && !item.tissue.walk_of && runs.some((run) => run.experiment === item.id));
}

/** The experiment a part belongs to, or null. */
export function wholeOf(raw, partId) {
  const part = (raw?.experiments || []).find((item) => item.id === partId);
  return part?.part_of ? (raw.experiments || []).find((item) => item.id === part.part_of) || null : null;
}

/** A parameter's unit in its own signs (m^2/s as m²/s, uM as µM): the same unit, never converted. */
export const unitWords = (unit) => unitSign(String(unit || "")).replace(/\^2(?![0-9])/g, "²").replace(/\^3(?![0-9])/g, "³");

/** A value of the sweep's parameter as the run states it ("6.25e-15"), never rounded: the record's own number. */
export const valueWords = (value) => (value === 0 ? "0" : String(value));

/**
 * The tissue line as the catalogue states it, or null where the entry is not one: its slots in the order of the
 * sweep's parameter (each a run with its end words, or a pick an engine check refused), its parameter's words,
 * the tumor's cells and the record's words with their sources.
 */
export function lineOf(raw, id) {
  const entry = (raw?.experiments || []).find((item) => item.id === id);
  const sweep = entry?.sweeps?.[0];
  if (!entry?.tissue || !sweep) return null;
  const rows = new Map((raw.runs || []).map((run) => [run.id, run]));
  const tissue = entry.tissue;
  const runs = sweep.arms.filter((arm) => arm.run && rows.has(arm.run)).map((arm) => ({ kind: "run", arm: arm.arm, id: arm.run, row: rows.get(arm.run), value: arm.parameter, end: tissue.ends?.[arm.arm] || null, place: arm.place || null }));
  const refused = (entry.refused_picks || []).filter((pick) => pick.sweep === sweep.id).map((pick) => ({ kind: "refused", arm: pick.arm, id: null, row: null, value: pick.parameter, end: null }));
  // In the order of the parameter's own values: a refused pick stands where its value puts it, between the runs.
  const slots = [...runs, ...refused].map((slot, order) => ({ slot, order })).sort((a, b) => a.slot.value - b.slot.value || a.order - b.order).map(({ slot }) => slot);
  const unit = unitWords(sweep.parameter.unit);
  const symbol = /\bD\b/.test(sweep.parameter.label) ? "D" : sweep.parameter.id;
  for (const slot of slots) {
    slot.short = `${symbol} = ${valueWords(slot.value)}`;
    slot.label = `${slot.short} ${unit}`;
    // Its place against the threshold, as the summary states it ("x2/2"), where it does.
    slot.where = slot.place?.relative_to_x2 || null;
  }
  return {
    id: entry.id,
    entry,
    sweep,
    parameter: { id: sweep.parameter.id, label: sweep.parameter.label, unit, symbol },
    slots,
    runs: slots.filter((slot) => slot.kind === "run"),
    refused: slots.filter((slot) => slot.kind === "refused"),
    // The tumour's cells as the summary states them (`tumor_cells`, as seeded), else as the overlay's words name them.
    tumor: Array.isArray(sweep.tumor_cells) ? { cells: sweep.tumor_cells, label: "Tumor: its cells as seeded", source: "the run folder's summary, tumor_cells" } : tissue.tumor || null,
    species: sweep.species || null,
    says: tissue.says || [],
    endsLabel: tissue.ends_label || "End states",
    endsSaid: tissue.ends_says || null, // whose words the end states are, as the entry says it (the card's line)
    refusedWords: tissue.refused || "Refused by an engine check: no run to show.",
    sources: tissue.sources || entry.sources || [],
    short: entry.short || entry.label,
  };
}

/** The runs' one clock: their saved times, which must be the same in every run shown together (no run is resampled). */
export function oneClock(runs) {
  if (!runs.length) throw new Error("no run to keep a clock for");
  const [first, ...rest] = runs;
  for (const run of rest) {
    if (run.count !== first.count) throw new Error(`the runs do not share their times: ${first.id} saves ${first.count} records, ${run.id} ${run.count}`);
    for (let k = 0; k < run.count; k++) {
      if (Math.abs(run.t[k] - first.t[k]) > TIME_SLACK) throw new Error(`the runs do not share their times: record ${k} is at ${first.t[k]} s in ${first.id} and ${run.t[k]} s in ${run.id}`);
    }
  }
  return first;
}

/**
 * The clock of runs shown together, where their saved times differ (one arm recorded a step in at a finer step than the
 * others): the union of their times. No run is resampled: at any time each run shows its own record at or before it.
 * Gives { t, count, start, end, indexAt(seconds) }, as the player reads a run's.
 */
export function unionClock(runs) {
  if (!runs.length) throw new Error("no run to keep a clock for");
  const all = runs.flatMap((run) => Array.from(run.t)).sort((a, b) => a - b);
  const t = [];
  for (const time of all) if (!t.length || time - t[t.length - 1] > TIME_SLACK) t.push(time);
  const indexAt = (seconds) => {
    const limit = seconds + TIME_SLACK;
    if (!(limit > t[0])) return 0;
    let low = 0, high = t.length - 1;
    while (low < high) {
      const middle = (low + high + 1) >> 1;
      if (t[middle] <= limit) low = middle;
      else high = middle - 1;
    }
    return low;
  };
  return { t, count: t.length, start: t[0], end: t[t.length - 1], indexAt };
}

const channel = (hex, at) => parseInt(hex.slice(at, at + 2), 16) / 255;
const rgb = (hex) => (/^#[0-9a-f]{6}$/i.test(hex || "") ? [channel(hex, 1), channel(hex, 3), channel(hex, 5)] : [0.53, 0.53, 0.53]);
const mixed = (stops, t, out) => {
  const last = stops.length - 1, x = Math.min(1, Math.max(0, t)) * last, index = Math.min(last - 1, Math.floor(x)), f = x - index;
  for (let c = 0; c < 3; c++) out[c] = stops[index][c] + (stops[index + 1][c] - stops[index][c]) * f;
  return out;
};

/**
 * A value's colour on a scale broken at the criterion's own thresholds: one hue below the lower threshold, another above
 * the upper, from light at the threshold to strong at the scale's end (dark to light on a dark page), and a neutral grey
 * between them. With one threshold, the two hues meet at it. The scale's ends are given (the records' stated ranges,
 * widened to round numbers); a value beyond them takes the end's colour.
 *   marks: the record's ticks ([{ value, label }], one or two, as the adapter wrote them from the criterion)
 *   colours: { below: [near, …, far], between, above: [near, …, far] } as "#rrggbb"
 */
export class Breaks {
  constructor(marks, low, high, colours) {
    const values = (marks || []).map((mark) => mark.value).filter(Number.isFinite).sort((a, b) => a - b);
    if (!values.length || values.length > 2) throw new Error("a criterion gives one threshold or two");
    this.lower = values[0];
    this.upper = values[values.length - 1];
    this.low = Math.min(low, this.lower);
    this.high = Math.max(high, this.upper);
    this.marks = marks;
    this.setColours(colours);
  }

  setColours(colours) {
    this.hex = colours;
    this.below = colours.below.map(rgb);
    this.above = colours.above.map(rgb);
    this.between = rgb(colours.between);
  }

  /** Which side of the criterion's thresholds a value lies on: "below", "between" (two thresholds only) or "above". */
  side(value) {
    if (value < this.lower) return "below";
    if (value > this.upper) return "above";
    return this.lower === this.upper ? (value < this.lower ? "below" : "above") : "between";
  }

  /** The colour of a value, as [r, g, b] in sRGB 0..1; written into `out` where given. */
  colour(value, out = [0, 0, 0]) {
    if (!Number.isFinite(value)) return mixed([this.between, this.between], 0, out);
    const side = this.side(value);
    if (side === "between") return mixed([this.between, this.between], 0, out);
    if (side === "below") return mixed(this.below, (this.lower - value) / Math.max(1e-12, this.lower - this.low), out);
    return mixed(this.above, (value - this.upper) / Math.max(1e-12, this.high - this.upper), out);
  }

  /** The scale as stops along it from its low end to its high end, for a legend: [{ at (0..1), hex }], with the breaks as hard edges. */
  stops() {
    const span = this.high - this.low, at = (value) => (value - this.low) / span;
    const out = [];
    const arm = (list, from, to) => list.forEach((hex, k) => out.push({ at: at(from + ((to - from) * k) / Math.max(1, list.length - 1)), hex }));
    arm([...this.hex.below].reverse(), this.low, this.lower);
    if (this.lower !== this.upper) {
      out.push({ at: at(this.lower), hex: this.hex.between }, { at: at(this.upper), hex: this.hex.between });
    }
    arm(this.hex.above, this.upper, this.high);
    return out;
  }

  /** The same as a CSS gradient. */
  css(direction = "to right") {
    return `linear-gradient(${direction}, ${this.stops().map((stop) => `${stop.hex} ${(stop.at * 100).toFixed(2)}%`).join(", ")})`;
  }
}

/** The scale's ends from the records' own stated ranges (each record's `range`), widened to round numbers; nothing is read out of the values. */
export function rangeOf(records) {
  let low = Infinity, high = -Infinity;
  for (const record of records) {
    if (!Array.isArray(record?.range)) continue;
    low = Math.min(low, record.range[0]);
    high = Math.max(high, record.range[1]);
  }
  if (!(high >= low)) return { low: -1, high: 1 };
  const round = (value, up) => {
    if (value === 0) return 0;
    const step = Math.pow(10, Math.floor(Math.log10(Math.abs(value))));
    return (up ? Math.ceil(value / step) : Math.floor(value / step)) * step;
  };
  return { low: round(low, false), high: round(high, true) };
}

/** The time scales the space–time picture offers: the first is the one it opens on. */
export const TIME_SCALES = [
  ["log", "Logarithmic"],
  ["even", "Even"],
];
const NICE_TIMES = [1, 5, 15, 30, 60, 300, 900, 1800, 3600, 7200, 10800, 14400, 21600, 43200, 86400, 172800];

/**
 * The space–time picture's time axis, from the runs' first time to their last. `at(t)` gives a time's place along it,
 * 0..1. On the logarithmic scale (the picture's choice, which it opens on) a time t after the start stands at
 * log(1 + t / step), `step` being the runs' first saved step, so that the start can stand on it and the first minutes
 * are drawn wider than the last; on the even scale every second is as long. Its ticks are round times of the clock,
 * none nearer another than `gap` of the axis.
 */
export function timeAxis(start, end, { scale = "log", step = null, gap = 0.075 } = {}) {
  const span = end - start;
  const log = scale === "log" && step > 0 && span > step;
  const whole = log ? Math.log1p(span / step) : span;
  const at = (t) => {
    if (!(span > 0)) return 0;
    const after = Math.min(end, Math.max(start, t)) - start;
    return log ? Math.log1p(after / step) / whole : after / span;
  };
  const ticks = [{ time: start, at: 0, words: start === 0 ? "0" : clock(start), major: true }];
  // An even scale ticks one round step (of NICE_TIMES) all along it; a logarithmic one each round time that has room.
  const even = NICE_TIMES.find((size) => span / size <= 7) || NICE_TIMES[NICE_TIMES.length - 1];
  const candidates = log ? NICE_TIMES.map((size) => start + size) : Array.from({ length: Math.floor(span / even) }, (_, k) => start + (k + 1) * even);
  for (const time of candidates) {
    if (!(time > start && time < end)) continue;
    const place = at(time);
    if (place - ticks[ticks.length - 1].at >= gap && 1 - place >= gap) ticks.push({ time, at: place, words: clock(time - start), major: false });
  }
  ticks.push({ time: end, at: 1, words: clock(end - start), major: true });
  const words = log
    ? `Time runs down each map on a logarithmic scale, the picture's choice: a time t stands at log(1 + t / ${Number(step.toPrecision(6)).toLocaleString("en-US")} s), a two-hundredth of the run, so the first minutes are drawn wider than the last; the ticks give the times. Every saved record is drawn, each as a band from its time to the next.`
    : "Time runs down each map on an even scale: every second is as long. Every saved record is drawn, each as a band from its time to the next.";
  return { at, scale: log ? "log" : "even", step: log ? step : null, start, end, ticks, words };
}

/** The least length of the last record's band, as a share of the axis, so that it is seen. */
export const LAST_BAND = 0.006;

/**
 * The bands of the space–time picture for a run's saved times: record k is drawn from its time to the next record's,
 * and the last record, which has no next, as a band past the run's end, as long as the shortest band before it and at
 * least LAST_BAND of the axis (so that it is seen). Returns [{ k, from, to }] in the axis's units (0..1, the last band
 * a little past 1).
 */
export function bands(times, axis) {
  const out = [];
  let shortest = Infinity;
  for (let k = 0; k < times.length - 1; k++) {
    const from = axis.at(times[k]), to = axis.at(times[k + 1]);
    out.push({ k, from, to });
    if (to > from) shortest = Math.min(shortest, to - from);
  }
  const last = axis.at(times[times.length - 1]);
  out.push({ k: times.length - 1, from: last, to: last + Math.max(LAST_BAND, Number.isFinite(shortest) ? shortest : 0) });
  return out;
}
