// A run's records, read as the contract declares them (schema/QUANTITY_LAYERS.md, "Three
// things, kept apart"): what a record lives on, its unit, its kind, what its sign means,
// who computed it and how that layer of the engine is represented. This module only reads
// what the run's view states; where the view states less, it says what is missing and
// fills nothing in.
//
// Beside its records a run's view may state named constants of its definition (a
// temperature, a membrane's capacitance): values that nothing the run schedules changes.
// A derivation may read one in place of a saved record, and only where the view states it.

export const LIVES_ON = ["cell", "junction", "membrane", "channel population", "pump population", "face", "outside node", "route", "world"];
// What the engine's own run view calls two of them (a set's `holds`): read as written.
const ALSO_CALLED = { "membrane patch": "membrane", "exchange route": "route" };
// The end a sign names as the source of a positive value: a link's first entity (its sender) or a membrane's cell
// (its inside); or the other end. The viewer's older packages say first and second, cell and outside node; the
// engine's run view names the roles of the record's set: sender and receiver, inside and outside.
export const FROM_FIRST = ["first", "sender", "cell", "inside"];
export const FROM_SECOND = ["second", "receiver", "outside node", "outside"];

/** Whether a positive value goes from its entity's first end (a link's sender, a membrane's cell) to the other: true, false, or null where the sign names no such end. */
export function fromFirst(sign) {
  return FROM_FIRST.includes(sign?.from) ? true : FROM_SECOND.includes(sign?.from) ? false : null;
}
export const KINDS = ["level", "amount", "cumulative", "rate"];
export const REPRESENTATIONS = ["simulated", "modelled", "prescribed"];

/** What the entities of a set are, in the contract's words: the set says so, or its id is one of them. */
export function livesOn(run, setId) {
  if (!setId) return "world";
  const set = run.sets.get(setId);
  const said = ALSO_CALLED[set?.holds] || set?.holds || setId;
  return LIVES_ON.includes(said) ? said : null;
}

/**
 * One record as the contract declares it, or null when the run's view names no such
 * record. `loaded` is false for a record whose array comes in a file of its own that has
 * not been fetched (rule 10); `lacks` lists what the view does not state.
 */
export function declared(run, id) {
  const record = run.records.get(id) || run.pending?.get(id) || null;
  if (!record) return null;
  const layer = record.layer ? run.layers.find((item) => item.id === record.layer) || null : null;
  const representation = REPRESENTATIONS.includes(layer?.representation) ? layer.representation : null;
  const lives_on = livesOn(run, record.set);
  const signed = Array.isArray(record.range) && record.range[0] < 0;
  const lacks = [];
  if (!record.unit) lacks.push("unit");
  if (!KINDS.includes(record.kind)) lacks.push("kind");
  if (signed && !record.sign) lacks.push("sign");
  if (!record.owner) lacks.push("owner");
  if (!representation && record.set) lacks.push("representation");
  if (!lives_on) lacks.push("lives_on");
  return {
    id: record.id,
    label: record.label || record.id,
    unit: record.unit || null,
    lives_on,
    set: record.set || null,
    kind: KINDS.includes(record.kind) ? record.kind : null,
    sign: record.sign || null,
    owner: record.owner || null,
    representation,
    layer: layer ? { id: layer.id, label: layer.label || layer.id } : null,
    times: record.shape?.[0] ?? null,
    quantised: Boolean(record.quantised),
    part: record.part || null,
    // One of a field's records, one for each species (a concentration of each ion).
    field: record.field || null,
    species: record.species ?? null,
    // The same array as another record, declared over another set (a membrane's voltage where each cell has one membrane).
    same_as: record.same_as || null,
    // A total that only ever grows (the dissipated-energy ledgers), in the engine's own word: a rate worked out from it is never negative.
    never_falls: record.monotone === "non-decreasing",
    // A total that restarts at nought on a slot when an operator retires that slot ({ by: [laws], says }): no rate is taken across such an event.
    resets: record.resets || null,
    // What the run's view itself notes of the record, in its own words.
    note: record.note || null,
    // A record of an example run: its numbers are invented, and no model computed them (rule 6).
    example: Boolean(run.example),
    loaded: run.records.has(id),
    lacks,
  };
}

/** The cells an entity of a set lies on or joins, by number: itself, the cell of its membrane, a junction's two cells; or null where the run's view gives no way to it. */
export function cellsOf(run, setId, entity) {
  if (setId === "cell") return [entity];
  const geometry = run.sets.get(setId)?.geometry;
  if (geometry?.kind === "on") return geometry.index[entity] === undefined ? null : cellsOf(run, geometry.set, geometry.index[entity]);
  if (geometry?.kind === "links" && geometry.between === "cell") return geometry.ends[entity] || null;
  return null;
}

/**
 * Whether a total restarts on one entity between two times of the run. A record that says
 * `resets` names the operators that retire slots (`by`); their events say when, and at which
 * cell; the entity is traced to its cell or cells. A retired slot's total restarts at nought,
 * so a difference across such an event is the operator's booking and no flow: the `rate`
 * rule takes none there. An event at either end of the interval counts, since the run's files
 * do not say which side of it a record at that moment shows; and where the entity cannot be
 * traced to a cell, any such event in the interval counts.
 */
export function restartsBetween(run, record, entity, from, to) {
  const by = record?.resets?.by;
  if (!Array.isArray(by) || !by.length) return false;
  const layers = new Set(run.layers.filter((layer) => by.includes(layer.owner)).map((layer) => layer.id));
  const slack = 5e-4;
  const events = run.events.filter((event) => layers.has(event.layer) && event.time >= from - slack && event.time <= to + slack);
  if (!events.length) return false;
  const cells = cellsOf(run, record.set, entity);
  if (!cells) return true;
  return events.some((event) => [event.at, event.from].some((end) => end && end.set === "cell" && cells.includes(end.index)));
}

/** Every record of a run that lies over a set (one value per entity at each time), as declared. */
export function declaredOn(run, livesOnWhat) {
  const ids = [...run.records.keys(), ...(run.pending ? run.pending.keys() : [])];
  return ids.map((id) => declared(run, id)).filter((record) => record && record.lives_on === livesOnWhat && record.set);
}

/** The records of one field, one for each species the run saved it for, in the order of the run's species. */
export function family(run, field) {
  const species = run.sets.get("species")?.ids || [];
  const ids = [...run.records.keys(), ...(run.pending ? run.pending.keys() : [])];
  return ids
    .map((id) => declared(run, id))
    .filter((record) => record && record.field === field && record.species !== null)
    .sort((a, b) => species.indexOf(a.species) - species.indexOf(b.species));
}

/**
 * A named constant of the run's definition as its view states it, or null: { id, label, unit,
 * lives_on, set, axes, says }. `says` is the view's own account of why nothing in the run changes it.
 */
export function constantOf(run, id) {
  const constant = run.constants?.get(id);
  if (!constant) return null;
  // The engine's view gives a constant no set of its own: it is the set its values run along, beside the species.
  const set = constant.set || constant.axes.filter((axis) => axis !== "species").at(-1) || null;
  return { id: constant.id, label: constant.label || constant.id, unit: constant.unit || null, lives_on: livesOn(run, set), set, axes: constant.axes, says: constant.says || "", from: constant.from || null, constant: true };
}

const REPRESENTED = { simulated: "simulated", modelled: "modelled in aggregate", prescribed: "prescribed by the experiment" };

/** Whose word a sign is, as a sentence: the reading an adapter gives with it, or the run's own view. */
export function signedBy(sign) {
  if (!sign) return "";
  if (sign.by) return ` That is ${sign.by}.`;
  return ` Declared by the run's own view${sign.confirmed ? `; confirmed by ${sign.confirmed}` : ""}.`;
}

/** The same for a legend: its first sentence. What more an adapter says with it (how the run's own amounts agree) stands in the panel on what the layers show. */
export function signedByShort(sign) {
  return signedBy(sign).trim().split(/(?<=\.) /)[0];
}

/** In one sentence, what stands behind a saved record: who computed it and how it is represented. */
export function behind(record) {
  if (!record) return "";
  // A sign the run's view does not declare itself says where it comes from (the adapter's own table); one the view declares may say who confirmed it.
  const sign = record.sign?.says ? ` Positive means: ${record.sign.says}.${signedBy(record.sign)}` : "";
  // An example's numbers are invented: no model stands behind them, whatever the record is called.
  if (record.example) return `Example: invented numbers. Written by the viewer's run-fixture tool under the engine's own name for this record; no model computed it.${sign}`;
  const who = record.owner ? `Saved by the run; computed by ${record.owner}` : "Saved by the run; its files do not say which model or law computed it";
  const how = record.representation ? `, ${REPRESENTED[record.representation]}.` : `. ${record.owner ? "Its files do not say" : "Nor do they say"} how that part of the engine is represented.`;
  return `${who}${how}${sign}`;
}
