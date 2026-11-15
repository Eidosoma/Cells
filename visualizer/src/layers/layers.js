// Quantity layers (schema/QUANTITY_LAYERS.md): a layer is data that maps a record of a
// run to a mark. This module holds what does not draw: the declarations and their checks,
// which layers a run can feed and why not, and the rule that one layer holds each visual
// channel. The marks are in ./marks/, the rules for working a number out in ./derive.js.

import { declared, declaredOn, behind, family, constantOf } from "./records.js";
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
const capital = (words) => (words ? words.charAt(0).toUpperCase() + words.slice(1) : "");
const bare = (words) => String(words || "").replace(/^the /, "");

/**
 * The quantities a layer may take its numbers from, in the order it prefers them. Most
 * layers have one. A layer that can read the engine's own readout where a run kept it,
 * and otherwise works the number out, lists them under `first_of`.
 */
export const alternatives = (layer) => (Array.isArray(layer?.quantity?.first_of) ? layer.quantity.first_of : layer?.quantity ? [layer.quantity] : []);

/** The names under which a quantity's record may be saved: the engine's readout name, or an adapter's. */
export const recordNames = (quantity) => names(quantity?.record ?? quantity?.of ?? quantity?.any_of);

/** The species a quantity is shown for, where its record is saved once for each: the run's secreted species, or the first. */
function speciesOf(run, quantity) {
  const set = run.sets.get("species");
  if (quantity?.species === "secreted") return set?.secreted?.[0] ?? null;
  return typeof quantity?.species === "string" ? quantity.species : undefined;
}

/** The parts a rule is worked out from, where it has several ({ part: { on, per, signed, says } }); or null. */
export const partsOf = (quantity) => DERIVATIONS[quantity?.derivation]?.inputs || null;

/** The ways a layer names to fill one part of a rule, in the order it prefers them: a name, or { amount, over }. */
const waysOf = (value) => (Array.isArray(value) ? value : value ? [value] : []);
const isWay = (way) => text(way) || (way && typeof way === "object" && text(way.amount) && text(way.over));

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
      const parts = partsOf(quantity);
      if (parts) {
        // A rule with several inputs: the layer names what may fill each part.
        const given = quantity.of && typeof quantity.of === "object" && !Array.isArray(quantity.of) ? quantity.of : {};
        for (const part of Object.keys(parts)) if (!waysOf(given[part]).length || !waysOf(given[part]).every(isWay)) problems.push(`its rule needs ${part}, and it names nothing for it`);
        for (const part of Object.keys(given)) if (!parts[part]) problems.push(`${part} is not a part of the rule ${quantity.derivation}`);
      } else if (!names(quantity.of ?? quantity.any_of).length) problems.push("a derived quantity names the record it is worked out from");
      if (quantity.where !== undefined && quantity.where !== SHARED_SURROUNDINGS) problems.push(`${quantity.where} is not a condition the contract names`);
      if (quantity.any_of !== undefined && (quantity.derivation !== "rate" || !names(quantity.any_of).length)) problems.push("only a rate may be worked out from every one of several records, and it names them");
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

/** One name of a run's records as declared: the record itself, or of a record saved once for each species the one for the quantity's species. */
function named(run, name, quantity) {
  const record = declared(run, name);
  if (record) return record;
  const members = family(run, name);
  if (!members.length) return null;
  const species = speciesOf(run, quantity);
  return species === undefined ? members[0] : members.find((member) => member.species === species) || null;
}

/** The first of a quantity's record names that the run declares, as declared; or null. */
function sourceOf(run, quantity) {
  for (const name of recordNames(quantity)) {
    const record = named(run, name, quantity);
    if (record) return record;
  }
  return null;
}

/** One named thing of a run that may fill a part of a rule: its records (one, or one for each species), or its constant. */
function thingOf(run, name) {
  const members = family(run, name);
  if (members.length) return { how: "records", name, members };
  const record = declared(run, name);
  if (record) return { how: "record", name, record };
  const constant = constantOf(run, name);
  return constant ? { how: "constant", name, constant } : null;
}

/**
 * Whether one way fills one part of a rule: { ok, why, sure, … }. `sure` marks a reason that
 * says more than "not saved": the run has the thing, in a form the rule cannot read.
 */
function fillWay(run, way, spec) {
  if (typeof way === "object") {
    // An amount over a volume: a concentration, where the run saved amounts.
    const amount = fillWay(run, way.amount, spec), over = amount.ok ? fillWay(run, way.over, { on: spec.on, says: "the volume those amounts are in" }) : null;
    if (!amount.ok) return amount;
    if (!over.ok) return over;
    return { ok: true, how: "ratio", name: way.amount, amount, over, parts: [...amount.parts, ...over.parts] };
  }
  const thing = thingOf(run, way);
  if (!thing) {
    const unstated = run.unstated?.get(way);
    return { ok: false, sure: Boolean(unstated), why: unstated ? `This run did not save ${spec.says} over time. ${unstated}` : `This run did not save ${spec.says}.` };
  }
  const wrong = (found) => ({ ok: false, sure: true, why: `This run saved ${spec.says} for each ${found || "thing it does not name"}, not for each ${spec.on}.` });
  if (thing.how === "constant") {
    const { constant } = thing;
    const perSpecies = constant.axes.includes("species");
    if (Boolean(spec.per) !== perSpecies) return { ok: false, sure: true, why: `This run's definition gives ${spec.says} ${perSpecies ? "for each species" : "as one value"}, which the rule cannot read.` };
    if (constant.set && spec.on && spec.on !== "world" && constant.lives_on !== spec.on) return wrong(constant.lives_on);
    return { ok: true, ...thing, parts: [] };
  }
  const records = thing.how === "records" ? thing.members : [thing.record];
  if (Boolean(spec.per) !== (thing.how === "records")) return { ok: false, sure: true, why: `This run saved ${spec.says} ${thing.how === "records" ? "for each species" : "as one record"}, which the rule cannot read.` };
  if (spec.on && records.some((record) => record.lives_on !== spec.on)) return wrong(records[0].lives_on);
  if (spec.signed && records.some((record) => !record.sign)) return { ok: false, sure: true, why: `This run saved ${spec.says}, but does not say which way it is positive.` };
  return { ok: true, ...thing, parts: [...new Set(records.filter((record) => !record.loaded && record.part).map((record) => record.part))] };
}

/** Whether a run can feed a rule that has several inputs: { ok, why, source, inputs, parts, livesOn }. */
function tryParts(run, quantity) {
  const parts = partsOf(quantity), inputs = {}, files = new Set();
  for (const [part, spec] of Object.entries(parts)) {
    let filled = null, why = null;
    for (const way of waysOf(quantity.of?.[part])) {
      const tried = fillWay(run, way, spec);
      if (tried.ok) {
        filled = tried;
        break;
      }
      if (!why || (tried.sure && !why.sure)) why = tried;
    }
    if (!filled) return { ok: false, why: why?.why || NOT_SAVED };
    inputs[part] = { part, says: spec.says, ...filled };
    for (const file of filled.parts) files.add(file);
  }
  // The rule is for one membrane: the run must say which cell each membrane lies on, and which outside it faces.
  const membranes = run.sets.get("membrane");
  const outside = membranes?.outside ? run.sets.get(membranes.outside.set) : null;
  const facesOutside = !Object.values(parts).some((spec) => spec.on === "outside node") || (outside && (outside.holds || outside.id) === "outside node");
  if (!(membranes?.geometry?.kind === "on" && membranes.geometry.set === "cell") || !facesOutside) {
    return { ok: false, why: "This run's files do not say which membrane lies on which cell, and which outside it faces." };
  }
  const lead = inputs.voltage || Object.values(inputs)[0];
  return { ok: true, why: null, source: lead.record || lead.members?.[0] || null, across: null, inputs, parts: [...files], livesOn: "membrane" };
}

/** Whether a run can feed one quantity through a mark: { ok, why, source, across, parts }. */
function tryQuantity(run, quantity, mark) {
  if (partsOf(quantity)) {
    const tried = tryParts(run, quantity);
    if (!tried.ok) return tried;
    if (!mark.lives_on.includes(tried.livesOn)) return { ok: false, why: `Its mark is drawn on ${mark.lives_on.join(" or ")}s, and this rule is for one ${tried.livesOn}.` };
    return tried;
  }
  if (quantity.species === "secreted" && speciesOf(run, quantity) === null) return { ok: false, why: "This run's files name no secreted species." };
  // A rate of every one of several totals (what crossed each kind of link; what was dissipated at each): each record the run saved is read.
  if (quantity.any_of) {
    const sources = [], whys = [], left = [];
    const wanted = speciesOf(run, quantity);
    for (const name of names(quantity.any_of)) {
      // One record, or a field saved once for each species: every species' record is read, or the one the layer names.
      const single = declared(run, name);
      const records = single ? [single] : family(run, name).filter((member) => wanted === undefined || member.species === wanted);
      for (const record of records) {
        let why = null;
        if (record.kind !== "cumulative") why = "This run saved it, but not as a total since the run's start: no rate can be worked out from it.";
        else if (!mark.lives_on.includes(record.lives_on)) why = `Its mark is drawn on ${mark.lives_on.join(" or ")}s, and this record lies on ${record.lives_on || "something the run does not name"}.`;
        else if (mark.needs_sign && !record.sign) why = "This run saved it, but does not say which way it is positive: a bead would have no way to go.";
        // A ledger that only grows, or one that says where it restarts: either gives a rate that is never negative.
        else if (mark.needs_growth && !record.never_falls && !record.resets) why = "This run saved it, but does not say that it only ever grows: a rate worked out from it could be negative.";
        // Where the run's own view says why it does not state something of the record, the reason is given in its words.
        const said = why ? run.unstated?.get(record.field || record.id) : null;
        if (why && said) why = `${why} The run's view says: ${said}.`;
        if (why) {
          whys.push(why);
          left.push({ record, why });
        } else sources.push(record);
      }
    }
    if (!sources.length) return { ok: false, why: whys[0] || NOT_SAVED };
    // A total saved once for each species is left out once, by its field.
    const leftOut = [...new Map(left.map((item) => [item.record.field || item.record.id, item])).values()];
    return { ok: true, why: null, source: sources[0], sources, left: leftOut, across: null, parts: [...new Set(sources.filter((record) => !record.loaded && record.part).map((record) => record.part))], species: speciesOf(run, quantity) ?? null };
  }
  const source = sourceOf(run, quantity);
  if (!source) return { ok: false, why: NOT_SAVED };
  if (quantity.signed && !source.sign) return { ok: false, why: "This run saved it, but does not say which way it is positive." };
  if (quantity.derivation === "rate") {
    // A mean rate is the growth of a total between two records: only a total can be differenced, and only a declared sign gives the way.
    if (source.kind !== "cumulative") return { ok: false, why: "This run saved it, but not as a total since the run's start: no rate can be worked out from it." };
    if (!source.sign) return { ok: false, why: "This run saved it, but does not say which way it is positive: a bead would have no way to go." };
  }
  let livesOn = source.lives_on, across = null;
  if (quantity.derivation === "difference") {
    // A difference is across the links between the entities the record lies on.
    across = [...run.sets.values()].find((set) => set.geometry?.kind === "links" && set.geometry.between === source.set && (!quantity.across || (set.holds || set.id) === quantity.across)) || null;
    if (!across || !across.ids.length) {
      // A run that lists its junctions and has none says so plainly, whatever the record tried lies on.
      const listed = [...run.sets.values()].find((set) => set.geometry?.kind === "links" && (set.holds || set.id) === quantity.across);
      return { ok: false, why: listed && !listed.ids.length ? `This run has no ${quantity.across}s between its ${listed.geometry.between}s.` : `This run has no ${quantity.across || "link"}s between its ${source.set}s.` };
    }
    if (quantity.where === SHARED_SURROUNDINGS && run.view?.surroundings?.shared !== true) {
      return { ok: false, why: "This run did not save each junction's voltage, and its files do not say that all its cells' surroundings share one potential: the difference of two membrane voltages would not be the junction's voltage." };
    }
    livesOn = across.holds || across.id;
  }
  if (!mark.lives_on.includes(livesOn)) return { ok: false, why: `Its mark is drawn on ${mark.lives_on.join(" or ")}s, and this record lies on ${livesOn || "something the run does not name"}.` };
  return { ok: true, why: null, source, across, parts: !source.loaded && source.part ? [source.part] : [], species: source.species ?? null };
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
  // A mark that has its place and does not draw yet: the run saved what the layer needs, and the layer waits.
  if (mark.built === false) return { ok: false, why: `This run saved it. ${mark.waits || "The viewer does not draw this layer yet."}`, parts: [], lacking: [], extras: [] };
  const parts = new Set(found.parts), lacking = [], extras = [];
  for (const extra of layer.also || []) {
    const record = sourceOf(run, { ...extra, species: extra.species ?? found.quantity.species });
    if (!record) lacking.push({ record: names(extra.record)[0], says: extra.without || `This run did not save ${names(extra.record)[0]}.` });
    else {
      // A record saved once for each species goes with the layer whole: every species' file is fetched with it.
      const all = record.field && extra.species === undefined && found.quantity.species === undefined ? family(run, record.field) : [record];
      for (const member of all) if (!member.loaded && member.part) parts.add(member.part);
      extras.push({ ...extra, record: record.id, field: record.field || null });
    }
  }
  return { ok: true, why: null, quantity: found.quantity, source: found.source, sources: found.sources || null, left: found.left || [], species: found.species ?? null, across: found.across, inputs: found.inputs || null, parts: [...parts], lacking, extras };
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
    // A record that comes in a file of its own is not offered here: it would appear only once another layer had fetched it.
    if (record.quantised || !record.loaded || record.part) continue;
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
  const { quantity, source, inputs = null, lacking = [], extras = [] } = fed;
  const rule = quantity?.derivation ? DERIVATIONS[quantity.derivation] : null;
  const numbers = [];
  if (rule && inputs) {
    // A rule with several inputs: each is named with where it comes from, the saved ones first.
    const all = Object.values(inputs);
    const saved = all.filter((input) => input.how !== "constant"), stated = all.filter((input) => input.how === "constant");
    const list = (items) => (items.length > 1 ? `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}` : items[0] || "");
    const words = [
      saved.length ? `the saved ${list(saved.map((input) => (input.how === "ratio" ? `${bare(input.says)} (an amount over a volume)` : bare(input.says))))}` : "",
      stated.length ? `${list(stated.map((input) => input.says))} as the run's definition gives ${stated.length > 1 ? "them" : "it"}` : "",
    ].filter(Boolean);
    numbers.push(rule.says(words.join(", with ")));
    for (const input of saved) for (const record of input.record ? [input.record] : input.members ? input.members.slice(0, 1) : [input.amount.record || input.amount.members?.[0]].filter(Boolean)) numbers.push(`${capital(input.says)}: ${lower(behind(record))}`);
    for (const input of stated) numbers.push(`${capital(input.says)}: ${lower(input.constant.says)}`);
    // What the run did not save for some of its species is said, species by species.
    const species = run.sets.get("species")?.ids || [];
    for (const input of saved) {
      if (!input.members) continue;
      const missing = species.filter((id) => !input.members.some((member) => member.species === id));
      if (missing.length) numbers.push(`This run did not save ${input.says.replace("each ion", list(missing))}: nothing is drawn for ${missing.length > 1 ? "them" : "it"}.`);
    }
  } else if (rule && fed.sources) {
    // A rate of several saved totals: the rule once, then what stands behind each total.
    // Totals saved once for each species are named once, by their field.
    const fields = [...new Map(fed.sources.map((record) => [record.field || record.id, record])).values()];
    const nameOf = (record) => lower(record.field ? record.label.replace(/: [^:]*$/, "") : record.label);
    numbers.push(rule.says(`the saved totals (${fields.map(nameOf).join("; ")})`));
    for (const record of fields) numbers.push(`${capital(nameOf(record))}: ${lower(behind(record))}${record.note ? ` The run's view notes: ${record.note}.` : ""}${record.resets ? ` It restarts at nought where a slot is retired (${record.resets.by.join(", ")}): no rate is taken across such an event.` : ""}`);
    // What the run saved and the layer cannot draw is said, with the reason.
    for (const item of fed.left || []) numbers.push(`Not drawn: ${nameOf(item.record)}. ${item.why}`);
  } else {
    if (rule) {
      numbers.push(rule.says(`the saved ${lower(source?.label || recordNames(quantity)[0])}`));
      if (quantity.where === SHARED_SURROUNDINGS && run.view?.surroundings?.says) numbers.push(`${run.view.surroundings.says} So the difference is the voltage across the junction itself.`);
    }
    numbers.push(behind(source));
  }
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
