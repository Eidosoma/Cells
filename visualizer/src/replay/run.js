// One run, opened: its view (schema/RUN_VIEW.md) with typed arrays over its payload.
// Read-only. It gives back what the run recorded and computes no verdict.

import { reading } from "./format.js";

export const REPLAY_FORMAT = "cells.visualizer.replay@1";
export const PART_FORMAT = "cells.visualizer.replay_part@1";
export const VIEW_FORMAT = "cells.run_view@1";
export const INDEX_FORMAT = "cells.visualizer.replay_index@1";
// What kind of number a record is, where its view says (schema/QUANTITY_LAYERS.md).
export const RECORD_KINDS = ["level", "amount", "cumulative", "rate"];

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

  // Records may come in files of their own beside the run's (parts): each part states its length.
  const parts = new Map();
  for (const part of view.parts || []) {
    if (!part || typeof part.id !== "string" || !/^[a-z0-9-]+$/.test(part.id) || parts.has(part.id)) problems.push("a part's id is missing, repeated or has other characters than a-z, 0-9 and hyphen");
    else if (!Number.isInteger(part.byte_length) || typeof part.file !== "string") problems.push(`part ${part.id}: it needs a file and a byte_length`);
    else parts.set(part.id, part);
  }
  if (view.surroundings !== undefined && (typeof view.surroundings !== "object" || typeof view.surroundings.shared !== "boolean" || typeof view.surroundings.says !== "string")) {
    problems.push("view.surroundings must say whether the cells' surroundings share one potential, and how that is known");
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
    const part = record.part === undefined ? null : parts.get(record.part);
    if (record.part !== undefined && !part) problems.push(`${name}: its part ${record.part} is not one of the run's`);
    const room = part ? part.byte_length : payload.byte_length;
    if (!Number.isInteger(record.offset) || record.offset % 4 !== 0) problems.push(`${name}: offset ${record.offset} is not a multiple of 4`);
    else if (record.offset + count(record.shape) * Type.BYTES_PER_ELEMENT > room) problems.push(`${name}: runs past the end of ${part ? `its part ${part.id}` : "the payload"}`);
    if (record.kind !== undefined && !RECORD_KINDS.includes(record.kind)) problems.push(`${name}: kind ${record.kind} is not one of ${RECORD_KINDS.join(", ")}`);
    if (record.sign !== undefined && (typeof record.sign !== "object" || typeof record.sign?.says !== "string" || (record.sign.high !== undefined && !["first", "second"].includes(record.sign.high)) || (record.sign.by !== undefined && typeof record.sign.by !== "string"))) {
      problems.push(`${name}: a sign says in words what positive means, for a record on links which end is the higher, and where it comes from when the run does not declare it`);
    }
    if (record.owner !== undefined && typeof record.owner !== "string") problems.push(`${name}: its owner must be a name`);
    if (record.scale !== undefined && !record.quantised) problems.push(`${name}: a scaled record must be marked quantised`);
    if (record.axes[0] !== "time") problems.push(`${name}: the first axis must be time`);
    if (record.id === "t") times = record;
    if (record.id === "t" && record.part !== undefined) problems.push("the record of the times must be in the run's own file");
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
    // A record whose array comes in a file of its own waits in `pending` until that file is in.
    this.records = new Map(view.records.filter((record) => record.part === undefined).map((record) => [record.id, new Series(record, buffer)]));
    this.pending = new Map(view.records.filter((record) => record.part !== undefined).map((record) => [record.id, record]));
    this.parts = new Map((view.parts || []).map((part) => [part.id, { ...part, loaded: false }]));
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

  /**
   * Take in the arrays of one part (a file of its own beside the run's). Its records are
   * then read like any other. Throws when the bytes are not the length the run states.
   */
  attach(partId, buffer) {
    const part = this.parts.get(partId);
    if (!part) throw new Error(`the run has no part ${partId}`);
    if (part.loaded) return;
    if (buffer.byteLength !== part.byte_length) throw new Error(`the part ${partId} is ${buffer.byteLength} bytes long, not the ${part.byte_length} the run states`);
    for (const [id, record] of [...this.pending]) {
      if (record.part !== partId) continue;
      this.records.set(id, new Series(record, buffer));
      this.pending.delete(id);
    }
    part.loaded = true;
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
