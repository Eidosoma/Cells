// A run's records, read as the contract declares them (schema/QUANTITY_LAYERS.md, "Three
// things, kept apart"): what a record lives on, its unit, its kind, what its sign means,
// who computed it and how that layer of the engine is represented. This module only reads
// what the run's view states; where the view states less, it says what is missing and
// fills nothing in.
//
// Beside its records a run's view may state named constants of its definition (a
// temperature, a membrane's capacitance): values that nothing the run schedules changes.
// A derivation may read one in place of a saved record, and only where the view states it.

export const LIVES_ON = ["cell", "junction", "membrane", "channel population", "pump population", "face", "outside node", "world"];
export const KINDS = ["level", "amount", "cumulative", "rate"];
export const REPRESENTATIONS = ["simulated", "modelled", "prescribed"];

/** What the entities of a set are, in the contract's words: the set says so, or its id is one of them. */
export function livesOn(run, setId) {
  if (!setId) return "world";
  const set = run.sets.get(setId);
  const said = set?.holds || setId;
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
    loaded: run.records.has(id),
    lacks,
  };
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
  return { id: constant.id, label: constant.label || constant.id, unit: constant.unit || null, lives_on: livesOn(run, constant.set), set: constant.set || null, axes: constant.axes, says: constant.says || "", from: constant.from || null, constant: true };
}

const REPRESENTED = { simulated: "simulated", modelled: "modelled in aggregate", prescribed: "prescribed by the experiment" };

/** In one sentence, what stands behind a saved record: who computed it and how it is represented. */
export function behind(record) {
  if (!record) return "";
  const who = record.owner ? `Saved by the run; computed by ${record.owner}` : "Saved by the run; its files do not say which model or law computed it";
  const how = record.representation ? `, ${REPRESENTED[record.representation]}.` : `. ${record.owner ? "Its files do not say" : "Nor do they say"} how that part of the engine is represented.`;
  // A sign the run's view does not declare itself says where it comes from (the adapter's own table).
  const sign = record.sign?.says ? ` Positive means: ${record.sign.says}.${record.sign.by ? ` That is ${record.sign.by}.` : ""}` : "";
  return `${who}${how}${sign}`;
}
