// One run, opened: its view (schema/RUN_VIEW.md) with typed arrays over its payload.
// Read-only. It gives back what the run recorded and computes no verdict.

import { reading } from "./format.js";

export const REPLAY_FORMAT = "cells.visualizer.replay@1";
export const VIEW_FORMAT = "cells.run_view@1";
export const INDEX_FORMAT = "cells.visualizer.replay_index@1";

const TYPES = { float32: Float32Array, uint8: Uint8Array, uint16: Uint16Array, int32: Int32Array };
const PATHS = /(^|[\s"'(=:])\/(home|mnt|Users|root|var|tmp)\//;

const TIME_SLACK = 5e-4; // seconds

const count = (shape) => shape.reduce((total, size) => total * size, 1);

/** Structural checks of a run file against the contract. Returns a list of problems. */
export function validateReplay(file) {
  const problems = [];
  if (!file || typeof file !== "object") return ["not an object"];
  if (file.format !== REPLAY_FORMAT) problems.push(`format is ${file.format}, expected ${REPLAY_FORMAT}`);
  const { view, payload } = file;
  if (!view || typeof view !== "object") return [...problems, "no view"];
  if (view.format !== VIEW_FORMAT) problems.push(`view.format is ${view.format}, expected ${VIEW_FORMAT}`);
  if (!payload || payload.encoding !== "base64" || typeof payload.data !== "string" || !Number.isInteger(payload.byte_length)) {
    return [...problems, "payload must be base64 with a byte_length"];
  }
  if (view.derived && !(Array.isArray(view.derivation) && view.derivation.length)) problems.push("a derived view must list its derivation");
  const run = view.run;
  if (!run || typeof run.id !== "string" || !/^[a-z0-9.-]+$/.test(run.id)) problems.push("view.run.id is missing or has other characters than a-z, 0-9, dot and hyphen");
  for (const key of ["parameters", "readouts"]) {
    if (run && run[key] !== undefined && !Array.isArray(run[key])) problems.push(`view.run.${key} must be a list`);
  }
  for (const key of ["sets", "records"]) if (!Array.isArray(view[key])) problems.push(`view.${key} is missing`);
  if (problems.length) return problems;

  const sets = new Map();
  for (const set of view.sets) {
    if (!set.id || !Array.isArray(set.ids)) {
      problems.push("a set lacks an id or its ids");
      continue;
    }
    sets.set(set.id, set);
    const geometry = set.geometry || {};
    if (geometry.kind === "polygons") {
      if (!Array.isArray(geometry.vertices) || !Array.isArray(geometry.faces)) problems.push(`set ${set.id}: polygons need vertices and faces`);
      else {
        if (geometry.faces.length !== set.ids.length) problems.push(`set ${set.id}: ${geometry.faces.length} faces for ${set.ids.length} ids`);
        const most = geometry.vertices.length;
        if (geometry.faces.some((face) => !Array.isArray(face) || face.length < 3 || face.some((index) => !(index >= 0 && index < most)))) {
          problems.push(`set ${set.id}: a face names a vertex that does not exist`);
        }
      }
    } else if (geometry.kind === "links") {
      const between = view.sets.find((other) => other.id === geometry.between);
      if (!between) problems.push(`set ${set.id}: links between an unknown set ${geometry.between}`);
      else if (!Array.isArray(geometry.ends) || geometry.ends.length !== set.ids.length) problems.push(`set ${set.id}: ends do not match its ids`);
      else if (geometry.ends.some((pair) => !Array.isArray(pair) || pair.length !== 2 || pair.some((index) => !(index >= 0 && index < between.ids.length)))) {
        problems.push(`set ${set.id}: a link names an entity that does not exist`);
      }
    }
  }

  const seen = new Set();
  let times = null;
  for (const record of view.records) {
    const name = `record ${record.id}`;
    if (!record.id || seen.has(record.id)) problems.push(`${name}: missing or repeated id`);
    seen.add(record.id);
    const Type = TYPES[record.dtype];
    if (!Type) {
      problems.push(`${name}: dtype ${record.dtype}`);
      continue;
    }
    if (!Array.isArray(record.shape) || !Array.isArray(record.axes) || record.shape.length !== record.axes.length) {
      problems.push(`${name}: shape and axes do not match`);
      continue;
    }
    if (!Number.isInteger(record.offset) || record.offset % 4 !== 0) problems.push(`${name}: offset ${record.offset} is not a multiple of 4`);
    else if (record.offset + count(record.shape) * Type.BYTES_PER_ELEMENT > payload.byte_length) problems.push(`${name}: runs past the end of the payload`);
    if (record.scale !== undefined && !record.quantised) problems.push(`${name}: a scaled record must be marked quantised`);
    if (record.axes[0] !== "time") problems.push(`${name}: the first axis must be time`);
    if (record.id === "t") times = record;
    if (record.set) {
      const set = sets.get(record.set);
      if (!set) problems.push(`${name}: unknown set ${record.set}`);
      else if (record.shape[record.shape.length - 1] !== set.ids.length) problems.push(`${name}: its last axis is ${record.shape[record.shape.length - 1]} long, the set has ${set.ids.length}`);
    }
  }
  if (!times) problems.push("no record of the times (id t)");
  else {
    if (view.time?.record !== "t") problems.push('view.time.record must be "t"');
    for (const record of view.records) {
      if (record.shape?.[0] !== times.shape[0]) problems.push(`record ${record.id}: ${record.shape?.[0]} times, the run has ${times.shape[0]}`);
    }
  }

  for (const region of view.regions || []) {
    const set = sets.get(region.set);
    if (!region.id || !set || !Array.isArray(region.indices) || region.indices.some((index) => !(index >= 0 && index < set.ids.length))) {
      problems.push(`region ${region.id}: unknown set or index`);
    }
  }
  for (const event of view.events || []) {
    for (const end of [event.at, event.from]) {
      if (!end) continue;
      const set = sets.get(end.set);
      if (!set || !(end.index >= 0 && end.index < set.ids.length)) problems.push(`event at ${event.time}: unknown set or index`);
    }
    if (!Number.isFinite(event.time) || !event.at) problems.push("an event lacks its time or its place");
  }
  if (PATHS.test(JSON.stringify(view))) problems.push("the view holds a machine path");
  return problems;
}

/** A record of the run with its array. */
class Series {
  constructor(record, buffer) {
    Object.assign(this, record);
    this.array = new TYPES[record.dtype](buffer, record.offset, count(record.shape));
    this.times = record.shape[0];
    this.width = this.array.length / this.times; // values per record time
    this.factor = record.scale ?? 1;
  }

  /** The value at a record time for one entity (or the only value of a time-only record). */
  at(time, index = 0) {
    return this.array[time * this.width + index] * this.factor;
  }

  /** The value as text with its unit, or null: a quantised record is for drawing only. */
  text(time, index = 0) {
    return reading(this, this.at(time, index));
  }
}

export class Run {
  constructor(view, buffer, entry = null) {
    this.view = view;
    this.entry = entry;
    this.info = view.run;
    this.id = view.run.id;
    this.derived = Boolean(view.derived);
    this.derivation = view.derivation || [];
    this.sets = new Map(view.sets.map((set) => [set.id, set]));
    this.records = new Map(view.records.map((record) => [record.id, new Series(record, buffer)]));
    this.t = this.records.get("t").array;
    this.count = this.t.length;
    this.start = this.t[0];
    this.end = this.t[this.count - 1];
    this.validity = this.records.get("valid")?.array || null;
    this.regions = view.regions || [];
    this.events = [...(view.events || [])].sort((a, b) => a.time - b.time);
    this.space = view.space || { unit: "", dimensions: 2 };
    this.layers = view.layers || [];
  }

  /** Records laid over one set, such as the cells: the ones a sheet can be coloured by. */
  recordsOn(setId) {
    return [...this.records.values()].filter((record) => record.set === setId && record.axes.length === 2);
  }

  /**
   * The last record at or before a time in the run. Times need not be evenly spaced.
   * Record times are stored as 32-bit floats, so a time is matched to within half a
   * millisecond: an event's time finds the record taken at it.
   */
  indexAt(seconds) {
    const { t } = this;
    const limit = seconds + TIME_SLACK;
    if (!(limit > t[0])) return 0;
    let low = 0, high = this.count - 1;
    while (low < high) {
      const middle = (low + high + 1) >> 1;
      if (t[middle] <= limit) low = middle;
      else high = middle - 1;
    }
    return low;
  }

  /** Whether the run itself counts a record as valid. One that is not is never shown as data. */
  isValid(index) {
    return !this.validity || this.validity[index] !== 0;
  }

  /** Events from just after `from` up to and including `to` (times in the run). */
  eventsBetween(from, to) {
    return this.events.filter((event) => event.time > from && event.time <= to);
  }

  /** How many events have happened by a time in the run. */
  eventsBy(seconds) {
    let low = 0, high = this.events.length;
    while (low < high) {
      const middle = (low + high) >> 1;
      if (this.events[middle].time <= seconds) low = middle + 1;
      else high = middle;
    }
    return low;
  }

  /** The events that touch one entity: as the place of the event, or as its source. */
  eventsOf(setId, index) {
    return this.events.filter((event) => (event.at?.set === setId && event.at.index === index) || (event.from?.set === setId && event.from.index === index));
  }

  /** The first record at or after a time, for marks such as the judged record. */
  indexFrom(seconds) {
    const index = this.indexAt(seconds);
    return this.t[index] >= seconds - TIME_SLACK || index === this.count - 1 ? index : index + 1;
  }
}
