// The life stages of a species, on one strip (schema/SPECIES_STAGES.md). Nothing here draws.
//
// A species file may carry an optional `stages` block: a staging system, the stages in their order, and the
// spans between stages that follow each other. A species without the block is read exactly as before: every
// function here gives it back as it is, with no strip. One stage is the file's own (`own`): the form the
// species file itself describes. The page opens on it, or on the drawn stage the block's `opens_on` names. Every other stage states only what differs from the
// file, each number with its source, or is named and not drawn (`missing`): it stands on the strip, says what
// is missing, and cannot be entered.
//
// What is here:
//   readStages(species)          the block, held to the contract: { stages, byId, own, spans, ... }, or the
//                                problems that refuse it ({code, says}), or null where there is none;
//   speciesAt(species, id)       the species read through a stage: the stage's own values over the file;
//   stripOf(species)             the marks on the strip, evenly by order, with what each says;
//   elapsedBetween(...)          the time between two stages, worked out from their stated times;
//   passagesOf(species, hooks)   what fills each stretch of the strip, each with a player;
//   illustration(...)            the viewer's own plain change between two drawn stages;
//   recordsPlayer(run, ...)      a saved run's records as the player of a span;
//   journeyOf(species, ...)      the strip's one clock, for the page's one Player (src/replay/player.js);
//   openingStage, stageFromAddress, stageToAddress, writeStage: the stage a species opens on, and `stage=`.
//
// The span's players keep the contract of the Experiments tab's Player: a clock with a start, an end and a
// time base (what its time is counted in, its speeds, its words, its advance), as the lineage view's clock
// does (src/lenses/lineage_clock.js). A journey of several spans is itself such a clock, whose track is the
// strip, so the page's one timeline control (src/ui/timeline.js) can play it.

import { SECONDS } from "../replay/player.js";
import { REPRESENTATIONS } from "../layers/records.js";
import { LADDER, cellTypesOf } from "./entries.js";

/** The levels a species may have, small to large (schema/SPECIES.md). */
export const LEVEL_IDS = ["molecules", "cell", "tissue", "organ", "organism"];
const FURTHER = ["tissue", "organ", "organism"];

/** What may fill a span: the viewer's own illustration, or a saved run, in its own word for how it is represented. */
export const FILL_KINDS = ["illustrative", ...REPRESENTATIONS];

/** Each kind's status line, as a span and every layer drawn in it say it. Nothing is called growth that emerged. */
export const FILL_WORDS = Object.freeze({
  illustrative: "Illustration: not a run",
  simulated: "Simulated by a run of the engine",
  modelled: "Modelled in aggregate by a run of the engine",
  prescribed: "Prescribed by the run's caller: not grown in the run",
  none: "Nothing is drawn here",
});

/** A time's units, in minutes. */
const MINUTES = Object.freeze({ s: 1 / 60, min: 1, h: 60, d: 1440 });
const UNIT_WORDS = Object.freeze({ s: "s", min: "min", h: "h", d: "days" });

/** How long the viewer's own plain change takes to watch, and how long a stretch with nothing in it: the picture's choices. */
export const ILLUSTRATION_SECONDS = 4;
export const EMPTY_SECONDS = 1.5;
/** How long each end of a plain change is held, as a share of it; between, one picture gives way through an empty picture to the next. */
export const HOLD = 0.15;
/** The journey's paces: shares of each span's own pace, slowest first, and the one it opens at. */
export const PACES = Object.freeze([0.25, 0.5, 1, 2, 4]);
export const OWN_PACE = 1;

const ID = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const BLOCK_KEYS = new Set(["system", "times_after", "opens_on", "list", "spans"]);
const SYSTEM_KEYS = new Set(["id", "label", "short", "sources"]);
const NAMING_KEYS = ["id", "order", "label", "short", "index", "time", "plain", "note", "sources"];
const DRAWING_KEYS = ["levels", "ends_at", "no_further_levels", "cell", "capability_sources", "cell_type", "cell_types", "default_cell_type"];
const STAGE_KEYS = new Set([...NAMING_KEYS, ...DRAWING_KEYS, "own", "missing", "modelled"]);
const TIME_KEYS = new Set(["value", "unit", "about", "temperature_c", "sources", "where"]);
const CELL_KEYS = new Set(["facts", "parts", "capabilities"]);
const SPAN_KEYS = new Set(["from", "to", "fill", "note"]);
const FILL_KEYS = new Set(["kind", "run", "note"]);

const text = (value) => typeof value === "string" && value.trim().length > 0;
const isNumber = (value) => typeof value === "number" && Number.isFinite(value);
const problem = (code, says) => ({ code, says });
const smooth = (a, b, x) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

/** The first number of a stage's index ("35-36" gives 35), or null where it gives none. */
export function indexNumber(index) {
  const found = String(index ?? "").match(/^\s*(\d+(?:\.\d+)?)/);
  return found ? Number(found[1]) : null;
}

/** Where a time's value is a number above nought, or a rising range of two. */
const amount = (value) => (isNumber(value) && value > 0) || (Array.isArray(value) && value.length === 2 && value.every((item) => isNumber(item) && item > 0) && value[0] <= value[1]);

// ------------------------------------------------------------------ reading the block

const cache = new WeakMap();
// A species read through a stage keeps the species as its file gives it here, so that its block is always read against the file.
const FILE = Symbol("the species' file");

/** The species as its file gives it: itself, or, for a species read through a stage, the species it was read from. */
export const fileOf = (species) => (species && species[FILE]) || species;

/**
 * The species' stages, held to the contract (schema/SPECIES_STAGES.md): null where the species has no
 * block; { ok: false, problems } where the block is refused (the species is then read as if it had none);
 * else { ok: true, system, timesAfter, stages (in their order), byId, own, spans (declared, in order), problems: [] }.
 * A species read through a stage gives its file's.
 */
export function readStages(given) {
  const species = fileOf(given);
  if (!species || typeof species !== "object" || species.stages === undefined) return null;
  if (cache.has(species)) return cache.get(species);
  const problems = check(species);
  const read = problems.length ? { ok: false, problems } : sound(species);
  cache.set(species, read);
  return read;
}

/** The problems that refuse a species' stages block, each { code, says }; none for a sound block or for a species without one. */
export function stageProblems(species) {
  return readStages(species)?.problems || [];
}

/** Whether the species carries a sound stages block. */
export const hasStages = (species) => Boolean(readStages(species)?.ok);

function sound(species) {
  const block = species.stages;
  const stages = [...block.list].sort((a, b) => a.order - b.order);
  const byId = new Map(stages.map((stage) => [stage.id, stage]));
  const spans = [...(block.spans || [])].sort((a, b) => byId.get(a.from).order - byId.get(b.from).order);
  const own = stages.find((stage) => stage.own);
  return { ok: true, problems: [], system: block.system || null, timesAfter: block.times_after || null, stages, byId, own, opensOn: block.opens_on ? byId.get(block.opens_on) : own, spans };
}

function check(species) {
  const out = [];
  const block = species.stages;
  if (!block || typeof block !== "object" || Array.isArray(block)) return [problem("block-shape", "stages is a block: {system, times_after, list, spans}")];
  for (const key of Object.keys(block)) if (!BLOCK_KEYS.has(key)) out.push(problem("block-key", `stages takes system, times_after, opens_on, list and spans, not ${key}`));
  const sources = species.sources && typeof species.sources === "object" ? species.sources : {};
  const cite = (keys, where) => {
    if (keys === undefined) return;
    if (!Array.isArray(keys)) return out.push(problem("source-unknown", `${where}: its sources are a list of keys of the species' sources`));
    for (const key of keys) {
      if (!(key in sources)) out.push(problem("source-unknown", `${where} cites ${JSON.stringify(key)}, which is not among the species' sources`));
      else if (sources[key]?.class !== "permissive") out.push(problem("source-not-permissive", `${where} cites ${JSON.stringify(key)}, whose class is not permissive: nothing may be taken from it`));
    }
  };
  const sourced = (keys) => Array.isArray(keys) && keys.length > 0;

  // The staging system: the species' own index for its stages, with its source.
  const system = block.system;
  if (system !== undefined) {
    if (!system || typeof system !== "object" || Object.keys(system).some((key) => !SYSTEM_KEYS.has(key)) || !(typeof system.id === "string" && ID.test(system.id)) || !text(system.label) || !text(system.short) || !sourced(system.sources)) {
      out.push(problem("system-shape", "stages.system is {id, label, short, sources}: a plain id, its name, its short name, and the sources that give it"));
    } else cite(system.sources, "stages.system");
  }
  if (block.times_after !== undefined && !text(block.times_after)) out.push(problem("times-after", "stages.times_after names the event every stage's time is counted from"));

  // The stages: an identity, a name, a place in the order, and what differs.
  const list = block.list;
  if (!Array.isArray(list) || list.length < 2 || !list.every((stage) => stage && typeof stage === "object" && !Array.isArray(stage))) {
    out.push(problem("list-shape", "stages.list holds two stages or more, each a block"));
    return out;
  }
  const ids = new Set();
  for (const stage of list) {
    if (!(typeof stage.id === "string" && ID.test(stage.id))) out.push(problem("stage-id", `a stage's id is a plain id of lower-case letters, digits and hyphens, not ${JSON.stringify(stage.id)}`));
    else if (ids.has(stage.id)) out.push(problem("stage-repeat", `the stage ${stage.id} is listed twice`));
    ids.add(stage.id);
  }
  const orders = list.map((stage) => stage.order);
  if (!orders.every((order) => Number.isInteger(order) && order >= 1)) out.push(problem("order-shape", "each stage's order is a whole number from 1"));
  else {
    const seen = new Set();
    for (const order of orders) {
      if (seen.has(order)) out.push(problem("order-repeat", `two stages stand at order ${order}`));
      seen.add(order);
    }
    for (let order = 1; order <= list.length; order++) if (!seen.has(order)) out.push(problem("order-gap", `the order has a gap: no stage stands at ${order} of ${list.length}`));
  }
  const owns = list.filter((stage) => stage.own === true);
  if (owns.length !== 1) out.push(problem("own-count", `exactly one stage is the file's own (own: true); ${owns.length} say so`));
  if (list.some((stage) => stage.own !== undefined && stage.own !== true)) out.push(problem("own-shape", "own is true, or left out"));
  const byId = new Map(list.map((stage) => [stage.id, stage]));
  const species_levels = Array.isArray(species.levels) ? species.levels : [];
  // The species' cell types other than its own, as its file names them or as the scene carries them resolved.
  const otherTypes = (Array.isArray(species.cell_types) ? species.cell_types : []).filter((type) => !(type && type.own)).map((type) => (typeof type === "string" ? type : type?.id));

  for (const stage of list) {
    const at = `the stage ${stage.id}`;
    for (const key of Object.keys(stage)) if (!STAGE_KEYS.has(key)) out.push(problem("stage-key", `${at} has a key the contract does not give: ${key}`));
    if (!text(stage.label)) out.push(problem("stage-label", `${at} has no label`));
    if (stage.short !== undefined && !(text(stage.short) && stage.short.length <= 18)) out.push(problem("stage-label", `${at}: its short name is a few letters, at most 18`));
    for (const key of ["plain", "note"]) if (stage[key] !== undefined && !text(stage[key])) out.push(problem("stage-text", `${at}: its ${key} is a sentence`));
    cite(stage.sources, at);
    if (stage.index !== undefined) {
      if (!system) out.push(problem("index-without-system", `${at} gives an index, but stages.system names no staging system`));
      if (!(text(stage.index) && stage.index.length <= 12)) out.push(problem("index-shape", `${at}: its index is a short text, as the system writes it`));
    }
    // A time after the block's event, at a stated temperature, with its source and the place in it.
    const time = stage.time;
    if (time !== undefined) {
      if (!block.times_after) out.push(problem("times-after", `${at} gives a time, but stages.times_after does not say what it is counted from`));
      if (!time || typeof time !== "object" || Object.keys(time).some((key) => !TIME_KEYS.has(key)) || !amount(time.value) || !(time.unit in MINUTES) || !isNumber(time.temperature_c) || (time.about !== undefined && typeof time.about !== "boolean")) {
        out.push(problem("time-shape", `${at}: its time is {value, unit, about, temperature_c, sources, where}, its value a number or a rising range of two, its unit one of ${Object.keys(MINUTES).join(", ")}`));
      }
      if (!(time && sourced(time.sources) && text(time.where))) out.push(problem("number-unsourced", `${at} states a time without its source and the place in it`));
      else cite(time.sources, `${at}'s time`);
    }
    if (stage.modelled !== undefined) {
      const modelled = stage.modelled;
      if (stage.own) out.push(problem("own-differs", `${at} is the file's own: what Cells models of it is the species' own modelled`));
      else if (!(modelled && LADDER.includes(modelled.state) && text(modelled.text) && (modelled.state === "generic" || (Array.isArray(modelled.record) && modelled.record.length)))) {
        out.push(problem("modelled-shape", `${at}: modelled needs a word of the ladder (${LADDER.join(", ")}), a text, and its record for every word above generic`));
      }
    }
    const draws = DRAWING_KEYS.filter((key) => stage[key] !== undefined);
    if (stage.own) {
      if (stage.missing !== undefined) out.push(problem("own-differs", `${at} is the file's own, which is drawn: it cannot be missing`));
      if (draws.length) out.push(problem("own-differs", `${at} is the file's own: it states nothing over the file (${draws.join(", ")})`));
      continue;
    }
    if (stage.missing !== undefined) {
      if (!text(stage.missing)) out.push(problem("named-shape", `${at}: missing says, in a sentence, what is not in hand`));
      if (draws.length) out.push(problem("named-draws", `${at} is named and not drawn: it states nothing to draw (${draws.join(", ")})`));
      continue;
    }
    // A drawn stage: what differs from the file.
    if (!draws.some((key) => ["levels", "ends_at", "cell"].includes(key))) out.push(problem("drawn-states-nothing", `${at} is drawn but states no level, no end and no cell of its own: name what differs, or say what is missing`));
    const end = stage.ends_at === undefined ? LEVEL_IDS.length - 1 : LEVEL_IDS.indexOf(stage.ends_at);
    if (stage.ends_at !== undefined && end < 1) out.push(problem("ends-at", `${at}: ends_at is a level from cell up, not ${JSON.stringify(stage.ends_at)}`));
    const levels = stage.levels ?? [];
    if (!Array.isArray(levels) || !levels.every((level) => level && typeof level === "object")) out.push(problem("level-shape", `${at}: its levels are a list of levels`));
    else {
      const given = new Set();
      for (const level of levels) {
        const where = `${at}'s ${level.id} level`;
        if (!LEVEL_IDS.includes(level.id)) {
          out.push(problem("level-shape", `${at}: a level's id is one of ${LEVEL_IDS.join(", ")}`));
          continue;
        }
        if (given.has(level.id)) out.push(problem("level-shape", `${at} gives its ${level.id} level twice`));
        given.add(level.id);
        if (LEVEL_IDS.indexOf(level.id) > end) out.push(problem("level-above-end", `${at} ends at its ${stage.ends_at}, and gives a ${level.id} level above it`));
        if (level.id === "molecules") {
          if (level.shape !== undefined) out.push(problem("level-shape", `${where} takes no shape`));
        } else if (!level.shape || typeof level.shape !== "object") out.push(problem("level-shape", `${where} gives no shape`));
        else if (!sourced(level.sources)) out.push(problem("number-unsourced", `${where} states a shape without a source: nothing is invented to fill a stage`));
        cite(level.sources, where);
      }
      // The composed levels: molecules and cell stay; a species short of a further level says so.
      const kept = new Set([...species_levels.map((level) => level.id), ...given].filter((id) => LEVEL_IDS.indexOf(id) <= end));
      const lacks = FURTHER.some((id) => !kept.has(id));
      if (lacks && !text(stage.no_further_levels) && !text(species.no_further_levels)) out.push(problem("no-further-sentence", `${at} has no ${FURTHER.filter((id) => !kept.has(id)).join(", ")}, and neither it nor the species gives no_further_levels`));
      if (stage.no_further_levels !== undefined && !text(stage.no_further_levels)) out.push(problem("no-further-sentence", `${at}: no_further_levels is a sentence`));
      const cell = stage.cell;
      if (cell !== undefined) {
        if (!cell || typeof cell !== "object" || Object.keys(cell).some((key) => !CELL_KEYS.has(key))) out.push(problem("cell-shape", `${at}: its cell takes facts, parts and capabilities`));
        else {
          if (cell.facts !== undefined && !Array.isArray(cell.facts)) out.push(problem("cell-shape", `${at}: its cell's facts are a list`));
          for (const fact of Array.isArray(cell.facts) ? cell.facts : []) {
            if (!(fact && text(fact.label) && text(fact.value))) out.push(problem("cell-shape", `${at}: a fact has a label and a value`));
            else if (!sourced(fact.sources)) out.push(problem("number-unsourced", `${at}'s fact ${JSON.stringify(fact.label)} states a value without a source`));
            else cite(fact.sources, `${at}'s fact ${JSON.stringify(fact.label)}`);
          }
          if (cell.parts !== undefined && (!cell.parts || typeof cell.parts !== "object" || Array.isArray(cell.parts))) out.push(problem("cell-shape", `${at}: its cell's parts are keyed`));
          if (cell.capabilities !== undefined && (!cell.capabilities || typeof cell.capabilities !== "object" || Array.isArray(cell.capabilities))) out.push(problem("cell-shape", `${at}: its cell's capabilities are keyed`));
        }
      }
      // Facts of another form are not carried over: a stage with a cell of its own states its own facts (an empty list where it has none).
      if (given.has("cell") && !Array.isArray(cell?.facts)) out.push(problem("facts-of-another-form", `${at} draws a cell of its own, so it gives its own cell.facts (an empty list where it states none): the file's facts are of another form`));
      for (const [key, keys] of Object.entries(stage.capability_sources || {})) cite(keys, `${at}'s capability_sources.${key}`);
      // Its cell types: its own type's name and loop, and the species' other types that exist at this stage.
      if (stage.cell_type !== undefined && !(stage.cell_type && typeof stage.cell_type === "object" && Object.keys(stage.cell_type).every((key) => ["id", "label", "loop"].includes(key)) && Object.values(stage.cell_type).every(text))) out.push(problem("cell-type-shape", `${at}: cell_type is {id, label, loop}, each a text`));
      if (stage.cell_types !== undefined && !(Array.isArray(stage.cell_types) && stage.cell_types.every((id) => typeof id === "string" && ID.test(id)))) out.push(problem("cell-type-shape", `${at}: cell_types is a list of the species' cell-type ids`));
      else for (const id of stage.cell_types || []) if (!otherTypes.includes(id)) out.push(problem("cell-type-unknown", `${at} names the cell type ${id}, which is not one of the species' own cell_types`));
      if (stage.default_cell_type !== undefined) {
        const own = stage.cell_type?.id || "cell";
        if (![own, ...(Array.isArray(stage.cell_types) ? stage.cell_types : [])].includes(stage.default_cell_type)) out.push(problem("cell-type-shape", `${at}: default_cell_type ${JSON.stringify(stage.default_cell_type)} is not one of its cell types`));
      }
    }
  }
  // The stage the species opens on: the file's own unless the block names another, and always one that is drawn.
  if (block.opens_on !== undefined) {
    const opens = byId.get(block.opens_on);
    if (!opens) out.push(problem("opens-on-unknown", `stages.opens_on names ${JSON.stringify(block.opens_on)}, which is not one of its stages`));
    else if (!opens.own && opens.missing !== undefined) out.push(problem("opens-on-named", `stages.opens_on names ${opens.id}, which is named and not drawn: the page opens on a stage it can draw`));
  }
  // The index rises with the order, where both stages give a number.
  const numbered = [...list].filter((stage) => Number.isInteger(stage.order)).sort((a, b) => a.order - b.order).filter((stage) => indexNumber(stage.index) !== null);
  for (let k = 1; k < numbered.length; k++) {
    if (!(indexNumber(numbered[k].index) > indexNumber(numbered[k - 1].index))) out.push(problem("index-order", `the stage ${numbered[k].id} (${numbered[k].index}) stands after ${numbered[k - 1].id} (${numbered[k - 1].index}) in the order, and its index does not rise`));
  }

  // The spans: each between two stages that follow each other, filled by the viewer's illustration or a saved run.
  const spans = block.spans ?? [];
  if (!Array.isArray(spans)) out.push(problem("span-shape", "stages.spans is a list"));
  else {
    const pairs = new Set();
    for (const span of spans) {
      const at = `the span ${span?.from} to ${span?.to}`;
      if (!span || typeof span !== "object") {
        out.push(problem("span-shape", "a span is a block"));
        continue;
      }
      for (const key of Object.keys(span)) if (!SPAN_KEYS.has(key)) out.push(problem("span-key", `${at} has a key the contract does not give: ${key}`));
      const from = byId.get(span.from), to = byId.get(span.to);
      if (!from || !to) {
        out.push(problem("span-unknown-stage", `${at} names a stage the species does not list`));
        continue;
      }
      if (to.order !== from.order + 1) out.push(problem("span-not-neighbours", `${at}: a span lies between two stages that follow each other, and ${span.to} does not follow ${span.from}`));
      const pair = `${span.from}>${span.to}`;
      if (pairs.has(pair)) out.push(problem("span-repeat", `${at} is given twice`));
      pairs.add(pair);
      if (span.note !== undefined && !text(span.note)) out.push(problem("span-shape", `${at}: its note is a sentence`));
      const fill = span.fill;
      if (!fill || typeof fill !== "object" || Object.keys(fill).some((key) => !FILL_KEYS.has(key)) || !FILL_KINDS.includes(fill.kind)) {
        out.push(problem("fill-kind", `${at}: its fill is {kind, run, note}, its kind one of ${FILL_KINDS.join(", ")}`));
        continue;
      }
      if (fill.kind === "illustrative") {
        if (fill.run !== undefined) out.push(problem("fill-illustrative-run", `${at} is the viewer's own illustration: it names no run`));
        const drawn = (stage) => stage && (stage.own || stage.missing === undefined);
        const before = [...list].filter((stage) => stage.order <= from.order).sort((a, b) => b.order - a.order).find(drawn);
        const after = [...list].filter((stage) => stage.order >= to.order).sort((a, b) => a.order - b.order).find(drawn);
        if (!before || !after) out.push(problem("fill-illustrative-ends", `${at}: an illustration runs from one drawn stage to the next, and this span has none on one side`));
      } else if (!text(fill.run)) out.push(problem("fill-run-missing", `${at} is ${fill.kind}: it names the saved run whose frames fill it`));
    }
  }
  return out;
}

// ------------------------------------------------------------------ the species read through a stage

const changesTheCell = (stage) => ["cell", "cell_type", "cell_types", "default_cell_type", "ends_at"].some((key) => stage[key] !== undefined) || (stage.levels || []).some((level) => level.id === "cell" || level.id === "tissue");

/**
 * The species read through a stage: the stage's own values over the species' file, and nothing else changed.
 * A species without a sound stages block is given back as it is, whatever the id; so is a species asked at its
 * own stage, or at no stage. A stage that cannot be entered (named and not drawn) or that the species does not
 * have gives null: the caller keeps the species' own stage. The species given is never changed.
 *
 * It works on the species as a file gives it and as the scene carries it (each with `cell_types` resolved, its
 * own type first, holding copies of the cell's levels, parts, capabilities and facts: tools/lib/entries.py). In
 * the scene's shape the own type is made again from the stage, so that a copy of the file's cell never stands
 * in for the stage's.
 */
export function speciesAt(given, id = null) {
  const species = fileOf(given);
  const read = readStages(species);
  if (!read?.ok || id === null || id === undefined || id === "") return species;
  const stage = read.byId.get(id);
  if (!stage || stage.missing !== undefined) return null;
  if (stage.own) return species;
  const out = compose(species, stage, read);
  Object.defineProperty(out, FILE, { value: species });
  return out;
}

function compose(species, stage, read) {
  const inherits = [];
  const given = new Map((stage.levels || []).map((level) => [level.id, level]));
  const end = stage.ends_at ? LEVEL_IDS.indexOf(stage.ends_at) : LEVEL_IDS.length - 1;
  const levels = LEVEL_IDS.slice(0, end + 1)
    .map((level) => given.get(level) || (species.levels || []).find((item) => item.id === level) || null)
    .filter(Boolean);
  const file = species.cell || {};
  const own = stage.cell || {};
  if (own.parts === undefined) inherits.push("cell.parts");
  if (own.facts === undefined) inherits.push("cell.facts");
  const cell = {
    facts: own.facts ?? file.facts ?? [],
    parts: own.parts ?? file.parts ?? {},
    capabilities: { ...(file.capabilities || {}), ...(own.capabilities || {}) },
  };
  const modelled = stage.modelled ?? species.modelled;
  if (stage.modelled === undefined) inherits.push("modelled");
  const out = { ...species, levels, cell, modelled };
  const lacks = FURTHER.some((level) => !levels.some((item) => item.id === level));
  if (lacks) out.no_further_levels = stage.no_further_levels || species.no_further_levels;
  else delete out.no_further_levels;
  if (stage.capability_sources) out.capability_sources = { ...(species.capability_sources || {}), ...stage.capability_sources };

  // Its cell types. A stage that leaves the cell alone keeps the species' cell types whole, with their looping run;
  // one that changes the cell has a cell type of its own, and those of the species' other types it names.
  const keeps = !changesTheCell(stage);
  const types = cellTypesOf(species);
  const fileOwn = types.find((type) => type.own) || types[0] || null;
  const sceneShaped = Array.isArray(species.cell_types) && species.cell_types.some((type) => type && typeof type === "object");
  if (keeps) inherits.push("cell types");
  const ownType = {
    id: keeps ? fileOwn?.id || "cell" : stage.cell_type?.id || "cell",
    label: keeps ? fileOwn?.label : stage.cell_type?.label || (modelled?.state === "generic" ? "Generic cell" : "Its cell"),
    own: true,
    modelled,
    levels: levels.filter((level) => level.id === "cell" || level.id === "tissue"),
    parts: cell.parts,
    capabilities: cell.capabilities,
    facts: cell.facts,
    loop: keeps ? fileOwn?.loop || null : stage.cell_type?.loop || null,
  };
  if (!keeps) {
    if (stage.cell_type) out.cell_type = { ...stage.cell_type };
    else delete out.cell_type;
  }
  const named = keeps ? null : stage.cell_types || [];
  if (sceneShaped) {
    const others = species.cell_types.filter((type) => type && typeof type === "object" && !type.own);
    out.cell_types = [ownType, ...(keeps ? others : others.filter((type) => named.includes(type.id)))];
    out.default_cell_type = keeps ? species.default_cell_type ?? ownType.id : stage.default_cell_type || ownType.id;
  } else if (!keeps) {
    if (named.length) out.cell_types = [...named];
    else delete out.cell_types;
    if (stage.default_cell_type) out.default_cell_type = stage.default_cell_type;
    else delete out.default_cell_type;
  }
  out.stage = Object.freeze({
    id: stage.id,
    label: stage.label,
    index: stage.index ?? null,
    system: read.system ? { id: read.system.id, label: read.system.label, short: read.system.short } : null,
    plain: stage.plain ?? null,
    note: stage.note ?? null,
    // What the stage takes from the file unchanged, so that the page can say so ("its parts are drawn as the species' own cell's").
    inherits: Object.freeze(inherits),
  });
  return out;
}

// ------------------------------------------------------------------ the strip and its axis

/** A stage's time in words: "about 90 min after fertilisation, at 23 °C". */
export function timeWords(time, after) {
  if (!time) return null;
  const value = Array.isArray(time.value) ? `${time.value[0].toLocaleString("en-US")} to ${time.value[1].toLocaleString("en-US")}` : time.value.toLocaleString("en-US");
  return `${time.about ? "about " : ""}${value} ${UNIT_WORDS[time.unit]}${after ? ` after ${after}` : ""}, at ${time.temperature_c} °C`;
}

/**
 * The marks on the strip, in their order. The strip is the stages' order, evenly: each stage one step, whatever
 * time lies between, so that no place on it is invented. A stated time is written on its mark, never used to place it.
 * Each mark: { id, order, place (0 to 1), label, short, index, indexWords, own, drawn, enterable, missing, time,
 * timeWords, words (the mark's name), says (in full, for a screen reader) }. A species without stages has none.
 */
export function stripOf(species) {
  const read = readStages(species);
  if (!read?.ok) return [];
  const n = read.stages.length;
  return read.stages.map((stage) => {
    const drawn = Boolean(stage.own) || stage.missing === undefined;
    const indexWords = stage.index !== undefined && read.system ? `${read.system.short} ${stage.index}` : null;
    const when = timeWords(stage.time, read.timesAfter);
    const words = [indexWords, stage.label].filter(Boolean).join(" · ");
    const says = [words, when, drawn ? null : `named, not drawn: ${stage.missing}`].filter(Boolean).join(". ");
    return Object.freeze({
      id: stage.id,
      order: stage.order,
      place: n > 1 ? (stage.order - 1) / (n - 1) : 0,
      label: stage.label,
      short: stage.short || stage.label,
      index: stage.index ?? null,
      indexWords,
      own: Boolean(stage.own),
      drawn,
      enterable: drawn,
      missing: stage.missing ?? null,
      time: stage.time ?? null,
      timeWords: when,
      words,
      says,
    });
  });
}

/**
 * The time between two stages, worked out by the viewer from their stated times: { ok: true, low, high, unit:
 * "min", temperature_c, says } where both give a time at one temperature; else { ok: false, why }. It is a
 * derivation, and its words say so.
 */
export function elapsedBetween(species, fromId, toId) {
  const read = readStages(species);
  const from = read?.ok ? read.byId.get(fromId) : null, to = read?.ok ? read.byId.get(toId) : null;
  if (!from || !to) return { ok: false, why: "the species does not list both stages" };
  if (!from.time || !to.time) return { ok: false, why: `${!from.time ? from.label : to.label} gives no time` };
  if (from.time.temperature_c !== to.time.temperature_c) return { ok: false, why: "their times are stated at different temperatures" };
  const range = (time) => (Array.isArray(time.value) ? time.value : [time.value, time.value]).map((value) => value * MINUTES[time.unit]);
  const [a0, a1] = range(from.time), [b0, b1] = range(to.time);
  const low = Math.max(0, b0 - a1), high = b1 - a0;
  if (!(high > 0)) return { ok: false, why: "the later stage's time is not later" };
  const round = (value) => Number(value.toPrecision(3));
  const value = round(low) === round(high) ? `${round(high).toLocaleString("en-US")}` : `${round(low).toLocaleString("en-US")} to ${round(high).toLocaleString("en-US")}`;
  return { ok: true, low, high, unit: "min", temperature_c: from.time.temperature_c, says: `about ${value} min between them at ${from.time.temperature_c} °C, worked out by the viewer from the two stages' stated times` };
}

// ------------------------------------------------------------------ what fills the strip: passages and their players

/**
 * The level each end of a plain change is drawn at: the level asked for where the stage has it, else its largest
 * level below it (an egg that ends at its cell is drawn at its cell when the visitor is at the whole body).
 */
export function levelFor(species, wanted) {
  const have = (species?.levels || []).map((level) => level.id);
  const at = LEVEL_IDS.indexOf(wanted);
  for (let k = at < 0 ? LEVEL_IDS.length - 1 : at; k >= 0; k--) if (have.includes(LEVEL_IDS[k])) return LEVEL_IDS[k];
  return have[0] || null;
}

/** The time base of the viewer's own plain change: its time is how far the change has gone, from 0 to 1, and it keeps no clock of life. */
export const ILLUSTRATION_BASE = Object.freeze({
  id: "illustration",
  speedsFor: () => [1],
  openingSpeed: () => 1,
  words: () => ({ short: "Own pace", phrase: "at the illustration's own pace", says: `An illustration, not a run: it takes ${ILLUSTRATION_SECONDS} seconds to watch, and keeps no time of life` }),
  clock: (progress) => `${Math.round(Math.min(1, Math.max(0, progress)) * 100)}%`,
  length: () => "the change",
  advance: (progress, seconds, speed) => progress + (seconds * speed) / ILLUSTRATION_SECONDS,
});

/**
 * The viewer's own plain change from one drawn stage to the next drawn one, passing the named stages between
 * (`through`). Each end's picture is held, then gives way through an empty picture to the other, so that no moment
 * of the change shows a blend that could be read as a form between the two. It claims nothing of what lies between.
 */
export function illustration(species, { from, to, through = [] }) {
  const ends = { [from]: speciesAt(species, from), [to]: speciesAt(species, to) };
  if (!ends[from] || !ends[to]) throw new Error(`an illustration runs between two drawn stages, not ${from} and ${to}`);
  const read = readStages(species);
  const label = (id) => read.byId.get(id).label;
  // The stages passed are named where they are few; where there are more, they are counted, so that the words stay short on the picture.
  const passed = through.length > 2 ? `the ${through.length} stages between are named, not drawn` : `${through.map(label).join(", ")} ${through.length > 1 ? "are" : "is"} named, not drawn`;
  const says = `${FILL_WORDS.illustrative}. A plain change from ${label(from)} to ${label(to)}${through.length ? `; ${passed}` : ""}. Nothing of how the one becomes the other is shown.`;
  return {
    kind: "illustrative",
    from,
    to,
    through,
    start: 0,
    end: 1,
    base: ILLUSTRATION_BASE,
    watch: ILLUSTRATION_SECONDS,
    levels: LEVEL_IDS.filter((level) => [ends[from], ends[to]].some((item) => item.levels.some((entry) => entry.id === level))),
    says,
    /** What is drawn at a point of the change: each end's picture at its weight, at the level it is drawn at. */
    frameAt(progress, wanted = "cell") {
      const p = Math.min(1, Math.max(0, progress));
      const weights = [
        [from, 1 - smooth(HOLD, 0.5, p)],
        [to, smooth(0.5, 1 - HOLD, p)],
      ];
      return { kind: "illustrative", says, at: p, draws: weights.filter(([, weight]) => weight > 0).map(([stage, weight]) => ({ stage, weight, level: levelFor(ends[stage], wanted) })) };
    },
    /** The clock the page's one Player loads to play this change alone. */
    asRun() {
      return clockLike({ start: 0, end: 1, t: [0, 1], timeBase: ILLUSTRATION_BASE });
    },
  };
}

/**
 * A saved run's records as the player of a span: the run's own clock between `from_s` and `to_s` (its stated times
 * at the span's two stages), its own time base, and at each time the record at or before it, as every replay shows
 * one. `run` is what the page's run reader gives (src/replay/run.js): { id, start, end, t, count, indexAt, timeBase }.
 * `kind` is the run's own word for the layer that gives the span its geometry; `levels` where its sets lie.
 */
export function recordsPlayer(run, { from, to, kind, from_s = run.start, to_s = run.end, levels = ["cell"], label = run.id }) {
  if (!REPRESENTATIONS.includes(kind)) throw new Error(`a run fills a span as ${REPRESENTATIONS.join(", ")}, not ${kind}`);
  if (!(to_s > from_s)) throw new Error("a run's span runs forward in its time");
  const base = run.timeBase || SECONDS;
  const length = to_s - from_s;
  const says = `${FILL_WORDS[kind]}: ${label}, from its record at ${from_s} to its record at ${to_s} in its own time`;
  return {
    kind,
    from,
    to,
    through: [],
    start: from_s,
    end: to_s,
    base,
    watch: length / base.openingSpeed(length),
    levels,
    says,
    frameAt(time) {
      const at = Math.min(to_s, Math.max(from_s, time));
      const record = run.indexAt(at);
      return { kind, says, at, run: run.id, record, draws: levels.map((level) => ({ run: run.id, record, level })) };
    },
    /** The run itself, held to the span's two times: what the Player loads to play this span alone. */
    asRun() {
      return Object.create(run, { start: { value: from_s, enumerable: true }, end: { value: to_s, enumerable: true } });
    },
  };
}

/** A stretch that nothing fills: nothing is drawn, and the reason is given. Illustration never stands in for a run. */
function emptyPlayer(from, to, why) {
  const says = `${FILL_WORDS.none}: ${why}`;
  return { kind: "none", from, to, through: [], start: 0, end: 1, base: ILLUSTRATION_BASE, watch: EMPTY_SECONDS, levels: [], says, frameAt: (progress) => ({ kind: "none", says, at: Math.min(1, Math.max(0, progress)), draws: [] }) };
}

/**
 * What fills the strip, stretch by stretch, in order: [{ from, to, a, b, player }], `a` and `b` the places of its
 * two stages on the strip (0 for the first stage, 1 for the next). A span a run fills is a passage of its own; the
 * spans between one drawn stage and the next drawn one that no run fills are one passage of the viewer's
 * illustration; a stretch with no drawn stage at one end, or a run that is not at hand, is a passage with nothing
 * in it. `runPlayer(fill, span)` gives the player of a run's fill, or `{ none: why }` (or null) where it has none.
 */
export function passagesOf(species, { runPlayer = () => null } = {}) {
  const read = readStages(species);
  if (!read?.ok) return [];
  const stages = read.stages;
  const declared = new Map(read.spans.map((span) => [`${span.from}>${span.to}`, span]));
  const drawn = (stage) => Boolean(stage.own) || stage.missing === undefined;
  const out = [];
  const plain = (from, to) => {
    // From stage index `from` to `to`, no run in between: split at each drawn stage.
    let k = from;
    while (k < to) {
      if (!drawn(stages[k])) {
        const next = stages.findIndex((stage, j) => j > k && j <= to && drawn(stage));
        const stop = next < 0 ? to : next;
        out.push({ from: stages[k].id, to: stages[stop].id, a: k, b: stop, player: emptyPlayer(stages[k].id, stages[stop].id, `${stages[k].label} is named, not drawn, and no run fills what follows it`) });
        k = stop;
        continue;
      }
      const next = stages.findIndex((stage, j) => j > k && j <= to && drawn(stage));
      if (next < 0) {
        out.push({ from: stages[k].id, to: stages[to].id, a: k, b: to, player: emptyPlayer(stages[k].id, stages[to].id, `${stages[to].label} is named, not drawn, and no run fills the way to it`) });
        break;
      }
      const through = stages.slice(k + 1, next).map((stage) => stage.id);
      out.push({ from: stages[k].id, to: stages[next].id, a: k, b: next, player: illustration(species, { from: stages[k].id, to: stages[next].id, through }) });
      k = next;
    }
  };
  let open = 0;
  for (let k = 0; k < stages.length - 1; k++) {
    const span = declared.get(`${stages[k].id}>${stages[k + 1].id}`);
    if (!span || span.fill.kind === "illustrative") continue;
    if (open < k) plain(open, k);
    // The hook gives the run's player, or { none: why } where it cannot (on its way, not among the page's runs), or null.
    const player = runPlayer(span.fill, span);
    const fills = player && !player.none;
    out.push({ from: stages[k].id, to: stages[k + 1].id, a: k, b: k + 1, player: fills ? player : emptyPlayer(stages[k].id, stages[k + 1].id, player?.none || `the run ${span.fill.run} that fills it is not at hand`) });
    open = k + 1;
  }
  if (open < stages.length - 1) plain(open, stages.length - 1);
  return out;
}

// ------------------------------------------------------------------ the journey: the strip's one clock

const FRACTIONS = new Map([[0.25, "¼"], [0.5, "½"]]);

/** The journey's pace in the timeline's words: never "true speed", since no span but a run's keeps a clock of life. */
export function paceWords(pace) {
  if (pace === OWN_PACE) return { short: "Own pace", phrase: "each span at its own pace", says: `Each span at its own pace: an illustration takes ${ILLUSTRATION_SECONDS} seconds to watch, a run plays at the speed its replay opens at` };
  const amount = FRACTIONS.get(pace) || String(pace);
  return { short: `${amount}× pace`, phrase: `${amount} times each span's own pace`, says: `${amount} times each span's own pace` };
}

/** What the Player loads for an illustration or a single span: the fields src/ui/timeline.js reads. */
function clockLike({ start, end, t, timeBase, events = [] }) {
  return {
    start,
    end,
    t,
    count: t.length,
    indexAt: (time) => {
      let index = 0;
      for (let k = 0; k < t.length; k++) if (t[k] <= time + 1e-9) index = k;
      return index;
    },
    events,
    eventsBy: (time) => events.filter((event) => event.time <= time + 1e-9).length,
    validity: null,
    isValid: () => true,
    info: { judged_s: null },
    timeBase,
  };
}

/** Which passages the journey's play control plays, unless the caller asks otherwise: every one that draws something. */
export const PLAYS_ALL = (passage) => passage.player.kind !== "none";

/**
 * The strip's one clock, for the page's one Player and timeline: its time is a place in the stages' order (0 at the
 * first stage, 1 at the next), each stage is a record and a labelled event (a stop), its track is the strip (evenly by
 * order), and it plays each passage at its own pace, in order. `plays(passage)` says which passages its play may play
 * (all that draw something, by default); it plays on through those that follow one another and stops where one that
 * it may not play begins. Beyond the Player's fields it gives `frameAt(time, level)` (what is drawn),
 * `passageAt(time)`, `stageAt(time)`, `placeOf(id)`, `read(time)` (the read-out's words), `stretchEnd(time)` (where a
 * play from here would stop, or null where none can start) and `playable` (whether any passage plays).
 */
export function journeyOf(species, passages = passagesOf(species), { plays = PLAYS_ALL } = {}) {
  const marks = stripOf(species);
  const n = marks.length;
  const start = 0;
  const end = Math.max(0, n - 1);
  const t = marks.map((mark) => mark.order - 1);
  const events = marks.map((mark) => ({ time: mark.order - 1, label: mark.words, short: mark.indexWords || mark.short, says: mark.says, kind: "stage", stage: mark.id, enterable: mark.enterable }));
  const passageAt = (time) => {
    const inside = passages.filter((passage) => passage.a <= time + 1e-9 && time < passage.b - 1e-9);
    return inside[0] || passages.find((passage) => Math.abs(passage.b - time) < 1e-9) || null;
  };
  const ownTime = (passage, time) => passage.player.start + ((time - passage.a) / (passage.b - passage.a)) * (passage.player.end - passage.player.start);
  const stageAt = (time) => marks.find((mark) => Math.abs(mark.order - 1 - time) < 1e-9) || null;
  // A place within a hair of a stage is that stage's, so that the playhead stops on it and at the end.
  const snap = (at) => {
    const near = Math.round(at);
    return Math.abs(at - near) < 1e-9 ? near : at;
  };
  const playingAt = (at) => passages.find((item) => item.a <= at && at < item.b && plays(item)) || null;
  // Where a play from here stops: the end of the passages it may play that follow one another from this place.
  const stretchEnd = (time) => {
    let at = snap(time), out = null;
    for (let passage = playingAt(at), guard = 0; passage && guard < 1000; passage = playingAt(at), guard++) {
      out = passage.b;
      at = passage.b;
    }
    return out;
  };
  // Where the clock is after `seconds` of watching at a pace: each passage it may play at its own pace, one after
  // another; it does not move into a passage it may not play.
  const advance = (time, seconds, pace) => {
    let at = snap(Math.min(end, Math.max(start, time))), left = seconds * pace;
    for (let guard = 0; left > 1e-12 && at < end && guard < 1000; guard++) {
      const passage = playingAt(at);
      if (!passage) break;
      const needed = (passage.player.watch * (passage.b - at)) / (passage.b - passage.a);
      if (left < needed) return snap(at + (left / passage.player.watch) * (passage.b - passage.a));
      at = passage.b;
      left -= needed;
    }
    return Math.min(end, at);
  };
  const read = (time) => {
    const mark = stageAt(time);
    if (mark) return { now: mark.words, of: mark.drawn ? "" : ": named, not drawn" };
    const passage = passageAt(time);
    if (!passage) return { now: "", of: "" };
    const name = (id) => marks.find((item) => item.id === id).words;
    return { now: `Between ${name(passage.from)} and ${name(passage.to)}`, of: ` · ${FILL_WORDS[passage.player.kind]}` };
  };
  const timeBase = Object.freeze({
    id: "stages",
    speedsFor: () => [...PACES],
    openingSpeed: () => OWN_PACE,
    words: paceWords,
    clock: (time) => read(time).now,
    length: () => `${n} stages`,
    advance,
    place: (time) => (n > 1 ? Math.min(1, Math.max(0, time / (n - 1))) : 0),
    timeAt: (place) => Math.min(1, Math.max(0, place)) * Math.max(0, n - 1),
    scale: () => "The track is the stages' order: each stage one step, whatever time lies between",
  });
  return {
    ...clockLike({ start, end, t, timeBase, events }),
    playable: passages.some(plays),
    marks,
    passages,
    passageAt,
    stageAt,
    stretchEnd,
    read,
    placeOf: (id) => {
      const mark = marks.find((item) => item.id === id);
      return mark ? mark.order - 1 : null;
    },
    /** What is drawn at a time of the journey: an enterable stage's own picture where the time stands on it, else its passage's frame. */
    frameAt(time, wanted = "cell") {
      const mark = stageAt(time);
      if (mark?.enterable) return { kind: "stage", stage: mark.id, says: mark.says, draws: [{ stage: mark.id, weight: 1, level: levelFor(speciesAt(species, mark.id), wanted) }] };
      const passage = passageAt(time);
      if (!passage) return { kind: "none", says: FILL_WORDS.none, draws: [] };
      return { ...passage.player.frameAt(ownTime(passage, time), wanted), passage: `${passage.from}>${passage.to}`, stage: mark?.id ?? null };
    },
  };
}

// ------------------------------------------------------------------ the address: `stage=`

/** The address's key for the stage shown. It is kept with the species (`entry=`), and written only for a stage that is not the one the species opens on. */
export const ADDRESS_KEY = "stage";

/** The stage a species opens on: the block's `opens_on`, else the file's own; null for a species without stages. */
export function openingStage(species) {
  const read = readStages(species);
  return read?.ok ? read.opensOn.id : null;
}

/**
 * The stage an address's `stage=` text asks for, for the species it names: { stage, open }. `stage` is the stage to
 * show: the one named where it can be entered, else the one the species opens on (null for a species without
 * stages). `open` is a named stage whose card is opened, since it cannot be entered. A stage the species does not have
 * is passed over.
 */
export function stageFromAddress(value, species) {
  const id = typeof value === "string" ? value.trim() : "";
  const read = readStages(species);
  if (!read?.ok) return { stage: null, open: null };
  const stage = id ? read.byId.get(id) : null;
  if (stage && !stage.own && stage.missing !== undefined) return { stage: read.opensOn.id, open: stage.id };
  return { stage: stage ? stage.id : read.opensOn.id, open: null };
}

/** The text `stage=` takes for a stage of the species, or null where nothing is written (the stage it opens on, a stage it cannot enter or does not have). */
export function stageToAddress(species, id) {
  const read = readStages(species);
  const stage = read?.ok ? read.byId.get(id) : null;
  return stage && (stage.own || stage.missing === undefined) && stage !== read.opensOn ? stage.id : null;
}

/** Writes the stage into an address's parameters (URLSearchParams), or takes it away where nothing is written. */
export function writeStage(params, species, id) {
  const value = stageToAddress(species, id);
  if (value) params.set(ADDRESS_KEY, value);
  else params.delete(ADDRESS_KEY);
  return params;
}
