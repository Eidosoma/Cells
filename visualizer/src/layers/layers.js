// Quantity layers (schema/QUANTITY_LAYERS.md): a layer is data that maps a record of a
// run to a mark. This module holds what does not draw: the declarations and their checks,
// which layers a run can feed and why not, and the rule that one layer holds each visual
// channel. The marks are in ./marks/, the rules for working a number out in ./derive.js.

import { declared, declaredOn, behind } from "./records.js";
import { DERIVATIONS, isDerivation } from "./derive.js";

export const LAYERS_FORMAT = "cells.visualizer.quantity_layers@1";
export const CHANNELS = ["colour", "height", "links", "surface", "arrows", "motion", "glow"];
export const CHANNEL_WORDS = { colour: "Colour", height: "Height", links: "Junctions", surface: "Membrane", arrows: "Arrows", motion: "Motion", glow: "Glow" };
export const STRENGTHS = ["quiet", "bold"];
export const NOT_SAVED = "This run did not save it.";
// The one condition a rule may ask of a run: that every cell's surroundings share one
// potential, so that the difference of two membrane voltages is the junction's own voltage.
export const SHARED_SURROUNDINGS = "shared surroundings";

const text = (value) => typeof value === "string" && value.trim().length > 0;
const names = (value) => (Array.isArray(value) ? value.filter(text) : text(value) ? [value] : []);
const lower = (words) => (words ? words.charAt(0).toLowerCase() + words.slice(1) : "");

/**
 * The quantities a layer may take its numbers from, in the order it prefers them. Most
 * layers have one. A layer that can read the engine's own readout where a run kept it,
 * and otherwise works the number out, lists them under `first_of`.
 */
export const alternatives = (layer) => (Array.isArray(layer?.quantity?.first_of) ? layer.quantity.first_of : layer?.quantity ? [layer.quantity] : []);

/** The names under which a quantity's record may be saved: the engine's readout name, or an adapter's. */
export const recordNames = (quantity) => names(quantity?.record ?? quantity?.of);

/** What is wrong with one layer's declaration, given the marks that exist ({ name: { channels, lives_on } }). */
export function validateLayer(layer, marks = {}) {
  const problems = [];
  if (!layer || typeof layer !== "object") return ["not an object"];
  if (!text(layer.id) || !/^[a-z0-9-]+$/.test(layer.id)) problems.push("its id is missing or has other characters than a-z, 0-9 and hyphen");
  if (!text(layer.label)) problems.push("it has no label");
  if (!text(layer.says)) problems.push("it does not say what it shows");
  const mark = marks[layer.mark];
  if (!mark) problems.push(`its mark ${layer.mark} is not one the viewer has`);
  if (!Array.isArray(layer.channels) || !layer.channels.length || layer.channels.some((channel) => !CHANNELS.includes(channel))) problems.push("its channels are missing or not ones the contract names");
  else if (mark && layer.channels.some((channel) => !mark.channels.includes(channel))) problems.push(`its mark ${layer.mark} does not draw on a channel it names`);
  const several = alternatives(layer);
  if (!several.length) problems.push("it names no quantity");
  for (const quantity of several) {
    if (!quantity || typeof quantity !== "object") {
      problems.push("a quantity is not an object");
      continue;
    }
    if (quantity.derivation !== undefined) {
      if (!isDerivation(quantity.derivation)) problems.push(`${quantity.derivation} is not one of the declared rules`);
      if (!names(quantity.of).length) problems.push("a derived quantity names the record it is worked out from");
      if (quantity.where !== undefined && quantity.where !== SHARED_SURROUNDINGS) problems.push(`${quantity.where} is not a condition the contract names`);
    } else if (!names(quantity.record).length) problems.push("a quantity names neither a record nor a rule");
  }
  for (const extra of layer.also || []) if (!names(extra?.record).length || !text(extra?.says)) problems.push("an optional record needs its id and what it adds");
  return problems;
}

/** A file of declarations (data/layers/layers.json), checked: { layers, problems }. */
export function readDeclarations(file, marks) {
  const problems = [];
  if (file?.format !== LAYERS_FORMAT) problems.push(`format is ${file?.format}, expected ${LAYERS_FORMAT}`);
  const layers = [], seen = new Set();
  for (const layer of file?.layers || []) {
    const wrong = validateLayer(layer, marks);
    if (seen.has(layer?.id)) wrong.push("its id is used twice");
    if (wrong.length) problems.push(`${layer?.id || "a layer"}: ${wrong.join("; ")}`);
    else {
      seen.add(layer.id);
      layers.push(layer);
    }
  }
  return { layers, problems };
}

/** The first of a quantity's record names that the run declares, as declared; or null. */
function sourceOf(run, quantity) {
  for (const name of recordNames(quantity)) {
    const record = declared(run, name);
    if (record) return record;
  }
  return null;
}

/** Whether a run can feed one quantity through a mark: { ok, why, source, across, parts }. */
function tryQuantity(run, quantity, mark) {
  const source = sourceOf(run, quantity);
  if (!source) return { ok: false, why: NOT_SAVED };
  if (quantity.signed && !source.sign) return { ok: false, why: "This run saved it, but does not say which way it is positive." };
  let livesOn = source.lives_on, across = null;
  if (quantity.derivation === "difference") {
    // A difference is across the links between the entities the record lies on.
    across = [...run.sets.values()].find((set) => set.geometry?.kind === "links" && set.geometry.between === source.set && (!quantity.across || (set.holds || set.id) === quantity.across)) || null;
    if (!across) return { ok: false, why: `This run has no ${quantity.across || "link"}s between its ${source.set}s.` };
    if (quantity.where === SHARED_SURROUNDINGS && run.view?.surroundings?.shared !== true) {
      return { ok: false, why: "This run did not save each junction's voltage, and its files do not say that all its cells' surroundings share one potential: the difference of two membrane voltages would not be the junction's voltage." };
    }
    livesOn = across.holds || across.id;
  }
  if (!mark.lives_on.includes(livesOn)) return { ok: false, why: `Its mark is drawn on ${mark.lives_on.join(" or ")}s, and this record lies on ${livesOn || "something the run does not name"}.` };
  return { ok: true, why: null, source, across, parts: !source.loaded && source.part ? [source.part] : [] };
}

/**
 * Whether a run can feed a layer. Returns { ok, why, quantity, source, across, parts,
 * lacking, extras }: `quantity` is the first of the layer's alternatives the run can feed
 * and `source` its record as declared; `why` is the reason it cannot, in the page's words;
 * `parts` are the files of their own that must be fetched first (rule 10); `extras` are the
 * optional records the run saved, by their place in `also`, and `lacking` those it did not,
 * each with what the layer then cannot show.
 */
export function feeds(run, layer, marks) {
  const mark = marks[layer.mark];
  if (!mark) return { ok: false, why: "The viewer has no such mark yet.", parts: [], lacking: [], extras: [] };
  let found = null, why = NOT_SAVED;
  for (const quantity of alternatives(layer)) {
    const tried = tryQuantity(run, quantity, mark);
    if (tried.ok) {
      found = { quantity, ...tried };
      break;
    }
    why = tried.why;
  }
  if (!found) return { ok: false, why, parts: [], lacking: [], extras: [] };
  const parts = new Set(found.parts), lacking = [], extras = [];
  for (const extra of layer.also || []) {
    const record = sourceOf(run, extra);
    if (!record) lacking.push({ record: names(extra.record)[0], says: extra.without || `This run did not save ${names(extra.record)[0]}.` });
    else {
      if (!record.loaded && record.part) parts.add(record.part);
      extras.push({ ...extra, record: record.id });
    }
  }
  return { ok: true, why: null, quantity: found.quantity, source: found.source, across: found.across, parts: [...parts], lacking, extras };
}

/**
 * The layers of one run: the declared ones, and for every plain record laid over the
 * cells that no declared layer shows, a colouring and a relief of it (a record over the
 * cells can always be coloured and raised: a new quantity with a known mark needs no code).
 * Each comes with whether the run can feed it: [{ layer, ok, why, … }].
 */
export function layersFor(run, declarations, marks) {
  const layers = declarations.map((layer) => ({ ...layer }));
  const shown = (mark) => new Set(layers.filter((layer) => layer.mark === mark).flatMap((layer) => alternatives(layer).filter((quantity) => !quantity.derivation).flatMap(recordNames)));
  const tinted = shown("tint"), raised = shown("relief");
  for (const record of declaredOn(run, "cell")) {
    if (record.quantised || !record.loaded) continue;
    const name = record.id.replace(/[^a-z0-9]+/gi, "-").toLowerCase();
    if (marks.tint && !tinted.has(record.id)) layers.push({ id: `${name}-tint`, label: record.label, quantity: { record: record.id }, mark: "tint", channels: ["colour"], says: `Each cell is coloured by its ${lower(record.label)}.`, plain: true });
    if (marks.relief && !raised.has(record.id)) layers.push({ id: `${name}-relief`, label: record.label, quantity: { record: record.id }, mark: "relief", channels: ["height"], says: `Each cell stands as high as its ${lower(record.label)}.`, plain: true });
  }
  return layers.map((layer) => ({ layer, ...feeds(run, layer, marks) }));
}

/**
 * Which layer holds each visual channel (rule 2). Switching a layer on takes its channels
 * from whichever layer held them; layers on different channels show together.
 */
export class Switch {
  constructor() {
    this.held = new Map(); // channel -> layer id
    this.strength = "quiet";
  }

  /** The ids of the layers that are on, in the order of the channels. */
  get on() {
    return [...new Set(CHANNELS.map((channel) => this.held.get(channel)).filter(Boolean))];
  }

  isOn(id) {
    return [...this.held.values()].includes(id);
  }

  holder(channel) {
    return this.held.get(channel) || null;
  }

  /** Switch a layer on. Returns the ids of the layers it took a channel from, which are now off. */
  switchOn(layer) {
    const evicted = new Set();
    for (const channel of layer.channels) {
      const before = this.held.get(channel);
      if (before && before !== layer.id) evicted.add(before);
    }
    // A layer that loses one of its channels is off altogether: it never shows on half of them.
    for (const [channel, id] of [...this.held]) if (evicted.has(id)) this.held.delete(channel);
    for (const channel of layer.channels) this.held.set(channel, layer.id);
    return [...evicted];
  }

  switchOff(id) {
    for (const [channel, held] of [...this.held]) if (held === id) this.held.delete(channel);
  }

  /** Drop what a run cannot feed (given the ids it can), keeping the rest as it stands. */
  keep(ids) {
    const can = new Set(ids);
    for (const [channel, id] of [...this.held]) if (!can.has(id)) this.held.delete(channel);
  }

  setStrength(value) {
    if (STRENGTHS.includes(value)) this.strength = value;
    return this.strength;
  }
}

/**
 * What the page says of a layer that is on (rule 4): what it shows; where its numbers come
 * from (what stands behind a saved record, and for a derivation the rule, its inputs and the
 * condition it rests on); and what else the run saved about it, or did not. `fed` is what
 * `feeds` gave for the layer. `lines` is all of it, in order.
 */
export function account(run, layer, fed) {
  const { quantity, source, lacking = [], extras = [] } = fed;
  const rule = quantity?.derivation ? DERIVATIONS[quantity.derivation] : null;
  const numbers = [];
  if (rule) {
    numbers.push(rule.says(`the saved ${lower(source?.label || recordNames(quantity)[0])}`));
    if (quantity.where === SHARED_SURROUNDINGS && run.view?.surroundings?.says) numbers.push(`${run.view.surroundings.says} So the difference is the voltage across the junction itself.`);
  }
  numbers.push(behind(source));
  const more = [...extras.map((extra) => extra.says), ...lacking.map((item) => item.says)];
  return {
    id: layer.id,
    label: layer.label,
    channel: layer.channels.map((channel) => CHANNEL_WORDS[channel]).join(" and "),
    derived: Boolean(rule),
    shows: layer.says,
    numbers: numbers.filter(Boolean),
    more: more.filter(Boolean),
    lines: [layer.says, ...numbers, ...more].filter(Boolean),
  };
}
