// The run an assembly view reads (schema/ASSEMBLY_RUN.md, cells.visualizer.assembly_run@1): a
// lineage of assemblies, each a list of counts of molecule types, growing one molecule at a time
// and splitting in two. This module holds a file to its contract and gives the view what it draws,
// as numbers: no drawing here. It names no model: the model is the file's.
//
// The run's own words stand: its similarity at each fission is read, never worked out again; its
// analysis's marks of inheritance are read, never decided here. What the view does work out is
// said to be the view's (shares, the second daughter, H between two compositions the run did not
// compare, a layout).

export const ASSEMBLY_FORMAT = "cells.visualizer.assembly_run@1";
export const PREFIX = "assembly:";
/** The share of each fission's interval on the clock spent on the split itself, on either side of the fission's time. */
export const PART = 0.15;

/**
 * The two forms of the law of catalysis a run may state (`law.form`), in the words of the engine's
 * decision (docs/DECISIONS.md, D192). A run names the engine's own name for its form in
 * `law.engine_name` once the engine has one; the view shows that name as words and binds to none.
 */
export const LAW_FORMS = {
  "single-event": "the preprint's single-event form, built for the reference comparison",
  "pair-consistent": "the pair-consistent form, the engine's own law",
};
/** The forms' names alone: what is said of a run that is not the engine's (an example), of which nothing was built. */
export const LAW_FORM_NAMES = {
  "single-event": "the preprint's single-event form",
  "pair-consistent": "the pair-consistent form",
};

const isCounts = (list) => Array.isArray(list) && list.every((pair) => Array.isArray(pair) && pair.length === 2 && Number.isInteger(pair[0]) && pair[0] >= 0 && Number.isInteger(pair[1]) && pair[1] > 0);

/** What is wrong with a file, as plain lines; an empty list where it holds to the contract. */
export function problemsOf(file) {
  const problems = [];
  if (!file || file.format !== ASSEMBLY_FORMAT) return [`the file is not ${ASSEMBLY_FORMAT}`];
  if (file.example !== undefined && !(file.example && typeof file.example.says === "string" && file.example.says)) problems.push("example must say in words that the file is an example");
  if (!file.model?.id || !file.model?.label) problems.push("model must give an id and a label");
  if (file.time?.base !== "fission" || !file.time.unit || !file.time.plural) problems.push("time must count fissions and give its words (base, unit, plural)");
  const environments = new Map();
  for (const environment of file.environments || []) {
    const n = environment.types?.length || 0;
    if (!n || new Set(environment.types).size !== n) problems.push(`${environment.id}: its types must be listed once each`);
    const rows = environment.catalysis?.rows;
    if (!Array.isArray(rows) || rows.length !== n || rows.some((row) => !Array.isArray(row) || row.length !== n || row.some((value) => !Number.isFinite(value)))) problems.push(`${environment.id}: its catalysis must be a table of ${n} by ${n} numbers`);
    if (environment.catalysis?.encoding !== "log10, two decimals") problems.push(`${environment.id}: its catalysis must state its encoding as "log10, two decimals"`);
    if (!(environment.reservoir?.each > 0) && !Array.isArray(environment.reservoir?.of)) problems.push(`${environment.id}: its reservoir must give each type's concentration`);
    environments.set(environment.id, environment);
  }
  if (!environments.size) problems.push("the file holds no environment");
  if (!Array.isArray(file.runs) || !file.runs.length) problems.push("the file holds no run");
  const ids = new Set();
  for (const run of file.runs || []) {
    const where = `run ${run.id}`;
    if (!run.id || ids.has(run.id)) problems.push(`${where}: a run needs an id of its own`);
    ids.add(run.id);
    const environment = environments.get(run.environment);
    if (!environment) { problems.push(`${where}: no environment ${run.environment}`); continue; }
    const n = environment.types.length;
    if (!["single lineage", "population"].includes(run.mode)) problems.push(`${where}: its mode must be "single lineage" or "population"`);
    if (run.mode === "population") problems.push(`${where}: a population is reserved and not read yet`);
    if (!run.law?.name) problems.push(`${where}: it must name the law of catalysis it ran`);
    if (run.law?.form !== undefined && !(run.law.form in LAW_FORMS)) problems.push(`${where}: its law's form is one of ${Object.keys(LAW_FORMS).join(", ")}`);
    if (run.law?.engine_name !== undefined && run.law.engine_name !== null && !(typeof run.law.engine_name === "string" && run.law.engine_name)) problems.push(`${where}: the engine's name for its law is words, or null until the engine has one`);
    if (run.world !== undefined && run.world !== null && !(typeof run.world === "string" && run.world)) problems.push(`${where}: the world it is of is named in words`);
    if (file.example && (run.engine_models?.length || run.revision)) problems.push(`${where}: an example names no engine model and no revision`);
    const inRange = (list) => isCounts(list) && list.every(([type]) => type < n);
    if (!inRange(run.founder)) problems.push(`${where}: its founder must be sparse counts of the environment's types`);
    const fissions = run.fissions || [];
    if (!fissions.length) problems.push(`${where}: it has no fission`);
    let totals = null;
    fissions.forEach((fission, index) => {
      const at = `${where}, fission ${fission.k}`;
      if (fission.k !== index + 1) problems.push(`${at}: fissions must be numbered 1, 2, … in order`);
      if (!inRange(fission.parent) || !inRange(fission.first)) problems.push(`${at}: its parent and first daughter must be sparse counts`);
      else {
        const parent = new Map(fission.parent);
        if (fission.first.some(([type, count]) => count > (parent.get(type) || 0))) problems.push(`${at}: the first daughter holds more of a type than its parent`);
      }
      if (!["first", "second"].includes(fission.continues)) problems.push(`${at}: continues must be "first" or "second"`);
      if (!Array.isArray(fission.similarity) || fission.similarity.length !== 2 || fission.similarity.some((h) => !(h >= 0 && h <= 1))) problems.push(`${at}: similarity must be the parent's H with each daughter, from 0 to 1`);
      const t = fission.totals;
      if (t && totals && (t.joined < totals.joined || t.left < totals.left || t.discarded < totals.discarded)) problems.push(`${at}: the totals are cumulative and never fall`);
      if (t) totals = t;
    });
    if (run.trace) {
      const growths = run.trace.growths || [];
      if (growths.length !== fissions.length) problems.push(`${where}: the trace must give one growth for each fission`);
      const events = decodeEvents(run.trace.events);
      if (events.length !== growths.reduce((a, b) => a + b, 0)) problems.push(`${where}: the trace's events must number what its growths say`);
      else if (!problems.length) {
        // The trace must take the founder, and each carried-on daughter, to the next parent exactly.
        let x = dense(run.founder, n), at = 0;
        for (let g = 0; g < growths.length && !problems.length; g++) {
          for (let e = 0; e < growths[g]; e++) { const v = events[at++]; x[Math.abs(v) - 1] += v > 0 ? 1 : -1; }
          const parent = dense(fissions[g].parent, n);
          if (x.some((count, type) => count !== parent[type])) problems.push(`${where}: the trace does not reach fission ${g + 1}'s parent`);
          const first = dense(fissions[g].first, n);
          x = fissions[g].continues === "first" ? first : parent.map((count, type) => count - first[type]);
        }
      }
    }
    const inheritance = run.analysis?.inheritance;
    if (inheritance) {
      if (!(inheritance.threshold > 0 && inheritance.threshold < 1) || typeof inheritance.strict !== "boolean" || !inheritance.compares) problems.push(`${where}: an analysis's inheritance must state what it compares, its threshold and whether it is strict`);
      if (!Array.isArray(inheritance.marks) || inheritance.marks.length !== fissions.length || inheritance.marks.some((mark) => typeof mark !== "boolean")) problems.push(`${where}: an analysis's inheritance needs a mark for each fission`);
    }
    const composomes = run.analysis?.composomes;
    if (composomes) {
      if (!composomes.method || !Array.isArray(composomes.names)) problems.push(`${where}: composomes are named only with the method that named them`);
      for (const name of composomes.names || []) if (!name.id || !Array.isArray(name.fissions) || name.fissions.some((k) => !(k >= 1 && k <= fissions.length))) problems.push(`${where}: composome ${name.id} must name fissions of the run`);
    }
  }
  for (const [key, source] of Object.entries(file.sources || {})) if (!source.class || !source.licence) problems.push(`source ${key}: it must state its licence and its class`);
  return problems;
}

/** The trace's events: signed type numbers, decoded from base64 of signed bytes. */
export function decodeEvents(text) {
  if (!text) return new Int8Array(0);
  const bytes = typeof atob === "function" ? Uint8Array.from(atob(text), (c) => c.charCodeAt(0)) : new Uint8Array(Buffer.from(text, "base64"));
  return new Int8Array(bytes.buffer, bytes.byteOffset, bytes.byteLength);
}

function dense(list, n) {
  const x = new Int32Array(n);
  for (const [type, count] of list || []) x[type] = count;
  return x;
}

export const sizeOf = (x) => { let n = 0; for (let i = 0; i < x.length; i++) n += x[i]; return n; };
export const typesHeld = (x) => { let n = 0; for (let i = 0; i < x.length; i++) if (x[i]) n++; return n; };

/** H, the cosine of two count lists: worked out by the view only where the run did not save it. */
export function similarity(x, y) {
  let dot = 0, a = 0, b = 0;
  for (let i = 0; i < x.length; i++) { dot += x[i] * y[i]; a += x[i] * x[i]; b += y[i] * y[i]; }
  return a > 0 && b > 0 ? dot / Math.sqrt(a * b) : 0;
}

/** One environment: its types and its table of catalysis, as read. */
export class Environment {
  constructor(raw) {
    this.raw = raw;
    this.id = raw.id;
    this.types = raw.types;
    this.count = raw.types.length;
    this.log10 = new Float32Array(this.count * this.count);
    raw.catalysis.rows.forEach((row, i) => row.forEach((value, j) => (this.log10[i * this.count + j] = value)));
  }

  /** log10 of the factor by which type j in the assembly speeds type i. */
  catalysis(i, j) {
    return this.log10[i * this.count + j];
  }
}

/** One run: a lineage of fissions, its compositions, its own H, its analysis, and the time its clock keeps. */
export class AssemblyRun {
  constructor(raw, environment, file) {
    this.raw = raw;
    this.file = file;
    this.id = raw.id;
    this.label = raw.label;
    this.environment = environment;
    this.n = environment.count;
    this.law = raw.law;
    this.form = raw.law?.form || null;
    this.world = raw.world || null;
    this.example = file.example || null;
    this.fissionCount = raw.fissions.length;
    this.founder = dense(raw.founder, this.n);
    this.parents = raw.fissions.map((fission) => dense(fission.parent, this.n));
    this.firsts = raw.fissions.map((fission) => dense(fission.first, this.n));
    this.seconds = this.parents.map((parent, index) => parent.map((count, type) => count - this.firsts[index][type]));
    this.events = raw.trace ? decodeEvents(raw.trace.events) : null;
    this.starts = [];
    if (raw.trace) {
      let at = 0;
      for (const count of raw.trace.growths) { this.starts.push(at); at += count; }
    }
    this.cache = { key: "", x: null };
  }

  get hasTrace() {
    return Boolean(this.events);
  }

  /** The fission's entry (k from 1). */
  fission(k) {
    return this.raw.fissions[k - 1] || null;
  }

  parent(k) { return this.parents[k - 1]; }
  /** The daughter that carries the lineage on from fission k. */
  carried(k) { return this.raw.fissions[k - 1].continues === "first" ? this.firsts[k - 1] : this.seconds[k - 1]; }
  /** The daughter that is not followed. */
  other(k) { return this.raw.fissions[k - 1].continues === "first" ? this.seconds[k - 1] : this.firsts[k - 1]; }
  /** What growth g starts from: the founder (g 0), or the daughter carried on from fission g. */
  born(g) { return g === 0 ? this.founder : this.carried(g); }

  /** The run's own H at fission k: of the parent with the daughter carried on, and with the other. */
  similarityAt(k) {
    const fission = this.raw.fissions[k - 1];
    const [first, second] = fission.similarity;
    return fission.continues === "first" ? { carried: first, other: second } : { carried: second, other: first };
  }

  /** The analysis's threshold of inheritance, as it states it, or null where it states none. */
  get threshold() {
    const inheritance = this.raw.analysis?.inheritance;
    return inheritance ? { value: inheritance.threshold, strict: inheritance.strict, compares: inheritance.compares, says: inheritance.says, by: this.raw.analysis.by } : null;
  }

  /** The analysis's mark at fission k: true inherited, false a break, null where no analysis marks it. */
  inherited(k) {
    const marks = this.raw.analysis?.inheritance?.marks;
    return marks ? marks[k - 1] : null;
  }

  /** The composomes the run's analysis names, or none. */
  get composomes() {
    const named = this.raw.analysis?.composomes;
    return named ? { method: named.method, settings: named.settings || null, names: named.names } : null;
  }

  composomeAt(k) {
    return this.composomes?.names.find((name) => name.fissions.includes(k)) || null;
  }

  /** How many molecules joined or left in growth g (only with a trace). */
  growthLength(g) {
    return this.raw.trace ? this.raw.trace.growths[g] : 0;
  }

  /** The composition of growth g after its first e events; without a trace, the composition it was born with. */
  during(g, e) {
    const key = `${g}:${e}`;
    if (this.cache.key === key) return this.cache.x;
    const x = Int32Array.from(this.born(g));
    if (this.events) {
      const from = this.starts[g];
      for (let k = 0; k < e; k++) { const v = this.events[from + k]; x[Math.abs(v) - 1] += v > 0 ? 1 : -1; }
    }
    this.cache = { key, x };
    return x;
  }

  /** The events of growth g, in order (signed type numbers). */
  growthEvents(g) {
    return this.events ? this.events.subarray(this.starts[g], this.starts[g] + this.raw.trace.growths[g]) : new Int8Array(0);
  }

  /** The three types that lead over the run, by their summed counts in every parent: they wear colour. */
  leading(count = 3) {
    const total = new Float64Array(this.n);
    for (const parent of this.parents) for (let i = 0; i < this.n; i++) total[i] += parent[i];
    return Array.from(total, (value, i) => [value, i]).sort((a, b) => b[0] - a[0] || a[1] - b[1]).slice(0, count).map(([, i]) => i);
  }

  /**
   * Where the clock stands in the run, from a time in fissions: a growth (g, with how many of its
   * events have happened) or a split (fission k, with how far the two daughters have parted).
   * Fission k happens at time k: its split is drawn from k - PART to k + PART, and the growth
   * after it fills the rest of the interval.
   */
  phaseAt(time) {
    const end = this.fissionCount;
    const t = Math.min(end + PART, Math.max(0, time));
    const k = Math.round(t);
    if (k >= 1 && k <= end && Math.abs(t - k) <= PART + 1e-9) return { phase: "split", k, part: Math.min(1, Math.max(0, (t - (k - PART)) / (2 * PART))), g: k - 1 };
    const g = Math.min(end - 1, Math.max(0, Math.floor(t + PART)));
    const from = g === 0 ? 0 : g + PART, to = g + 1 - PART;
    const progress = Math.min(1, Math.max(0, (t - from) / (to - from)));
    const length = this.growthLength(g);
    const e = this.events ? Math.min(length, Math.floor(progress * (length + 1))) : 0;
    return { phase: "grow", g, e, progress, k: g };
  }

  /** The composition the clock shows at a time: during a split, the parent. */
  compositionAt(time) {
    const at = this.phaseAt(time);
    return at.phase === "split" ? this.parent(at.k) : this.during(at.g, at.e);
  }

  /** The time on the clock at which growth g has had e events. */
  timeOf(g, e) {
    const from = g === 0 ? 0 : g + PART, to = g + 1 - PART, length = this.growthLength(g);
    return from + ((e + 0.5) / (length + 1)) * (to - from);
  }
}

/** A file read: its environments and its runs, held to the contract (a file that breaks it is refused). */
export class AssemblySet {
  constructor(file) {
    const problems = problemsOf(file);
    if (problems.length) throw new Error(`the assembly run file is not valid: ${problems.slice(0, 6).join("; ")}`);
    this.file = file;
    this.example = file.example || null;
    this.model = file.model;
    this.time = file.time;
    this.environments = new Map(file.environments.map((raw) => [raw.id, new Environment(raw)]));
    this.runs = file.runs.map((raw) => new AssemblyRun(raw, this.environments.get(raw.environment), file));
  }

  run(id) {
    return this.runs.find((run) => run.id === id) || null;
  }

  /**
   * Two runs to show side by side as the two forms of the law, or null. Only real runs of the
   * engine (a revision and the engine's models named), never an example; of the same world (the
   * world they say they are of, and the same environment), by the same rules, one of each form.
   */
  formsPair() {
    if (this.example) return null;
    const real = this.runs.filter((run) => run.raw.revision && run.raw.engine_models?.length && run.world && run.form && run.raw.mode === "single lineage");
    for (let a = 0; a < real.length; a++) {
      for (let b = a + 1; b < real.length; b++) {
        const one = real[a], two = real[b];
        if (one.world !== two.world || one.environment !== two.environment || one.form === two.form) continue;
        if (JSON.stringify(one.raw.rules || null) !== JSON.stringify(two.raw.rules || null)) continue;
        return [one, two];
      }
    }
    return null;
  }
}

/**
 * A run's form of the law, in words: the engine's name for it where the run gives one. What the engine's
 * decision says a form is for ("built for the reference comparison", "the engine's own law") is said only
 * of a real run of the engine, which names its revision and its models: beside an example of invented
 * numbers it would read as if the engine had built it.
 */
export function formWords(run) {
  if (!run.form) return run.law?.name || "its law";
  const real = Boolean(run.raw?.revision && run.raw?.engine_models?.length);
  return `${(real ? LAW_FORMS : LAW_FORM_NAMES)[run.form]}${run.law.engine_name ? ` (${run.law.engine_name})` : ""}`;
}
