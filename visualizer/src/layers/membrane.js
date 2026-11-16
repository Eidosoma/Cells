// The numbers of the layers that are drawn on one membrane of a chosen cell
// (schema/QUANTITY_LAYERS.md, rule 7): for each ion the terms of its potential difference,
// and the charge the membrane's voltage stands for. Nothing is drawn here: this module
// reads a run's saved records and the constants its view states, by the parts a layer's
// rule names, and applies the two declared rules of ./derive.js. The marks, the panel and
// the checks all read the same numbers from it.

import { potentialTerms, charge, chargesIn } from "./derive.js";

/**
 * Which membrane lies on which cell, as the run's view says it: { ids, cell, outside,
 * of(cell) } with, for each membrane, the index of its cell and of the outside node it
 * faces, and of(cell) the membranes of one cell. Null where the view does not say.
 */
export function membranesOf(run) {
  const set = run.sets.get("membrane");
  if (!set || set.geometry?.kind !== "on" || set.geometry.set !== "cell") return null;
  const cell = set.geometry.index, outside = set.outside?.index || null;
  return {
    ids: set.ids,
    cell,
    outside,
    of: (number) => cell.reduce((found, on, membrane) => (on === number ? [...found, membrane] : found), []),
  };
}

/**
 * How one filled part of a rule is read: (step, entity, species id) -> a number, or
 * undefined where the run has none for that species. `input` is what `feeds` gave for the
 * part: a saved record, one record for each species, a constant, or an amount over a volume.
 */
export function readerOf(run, input) {
  if (input.how === "ratio") {
    const amount = readerOf(run, input.amount), over = readerOf(run, input.over);
    return (step, entity, species) => {
      const top = amount(step, entity, species), under = over(step, entity, species);
      return top === undefined || under === undefined ? undefined : top / under;
    };
  }
  if (input.how === "constant") {
    const constant = run.constants.get(input.constant.id);
    const order = run.sets.get("species")?.ids || [];
    return (step, entity, species) => {
      const row = constant.axes.includes("species") ? order.indexOf(species) : 0;
      return row < 0 ? undefined : constant.at(entity, row);
    };
  }
  if (input.how === "records") {
    const bySpecies = new Map(input.members.map((member) => [member.species, run.records.get(member.id)]));
    return (step, entity, species) => bySpecies.get(species)?.at(step, entity);
  }
  const series = run.records.get(input.record.id);
  return (step, entity) => series.at(step, entity);
}

/** The voltage of a membrane as the inside less the outside: the saved record, turned round where its sign says the outside is the higher. */
function voltageOf(run, input) {
  const read = readerOf(run, input);
  const turn = input.record?.sign?.high === "outside" ? -1 : 1;
  return (step, membrane) => read(step, membrane) * turn;
}

/**
 * The push and pull on each ion at one membrane, from a layer fed with the rule
 * `potential terms`. Returns { species, missing, at(step, membrane) }:
 *   species   the ions the run can give every input for, in the run's order
 *   missing   those it cannot, each with what it lacks: [{ id, lacks }]
 *   at        for each of `species`: { id, valence, inside, outside, voltage, temperature,
 *             and the rule's own result: concentration, electrical, sum (J/mol), volts,
 *             size (V) and drives ("out", "in" or null) }; null for an ion where the rule
 *             gives nothing at that record (a concentration that is not positive)
 */
export function pushPull(run, fed) {
  const membranes = membranesOf(run), { inputs } = fed;
  const voltage = voltageOf(run, inputs.voltage);
  const inside = readerOf(run, inputs.inside), outside = readerOf(run, inputs.outside);
  const temperature = readerOf(run, inputs.temperature), valence = readerOf(run, inputs.valence);
  const all = run.sets.get("species")?.ids || [];
  const has = (input, id) => (input.how === "ratio" ? has(input.amount, id) : input.how === "records" ? input.members.some((member) => member.species === id) : true);
  const species = [], missing = [];
  for (const id of all) {
    const charged = valence(0, 0, id);
    if (!has(inputs.inside, id)) missing.push({ id, lacks: "its concentration in the cell" });
    else if (!has(inputs.outside, id)) missing.push({ id, lacks: "its concentration outside" });
    else if (!charged) missing.push({ id, lacks: "a charge: with no valence it has no pull of the voltage" });
    else species.push(id);
  }
  return {
    species,
    missing,
    at(step, membrane) {
      const cell = membranes.cell[membrane], node = membranes.outside[membrane];
      const volts = voltage(step, membrane), kelvin = temperature(step, 0);
      return species.map((id) => {
        const reading = { id, valence: valence(step, 0, id), inside: inside(step, cell, id), outside: outside(step, node, id), voltage: volts, temperature: kelvin };
        const terms = potentialTerms(reading);
        return terms ? { ...reading, ...terms } : null;
      });
    },
  };
}

/**
 * The charge a membrane's voltage stands for, from a layer fed with the rule `charge`.
 * at(step, membrane) gives { voltage, capacitance, area, coulombs, charges, per_um2, inside }:
 * the charge on the inner face in coulombs (capacitance times the voltage, the inside less
 * the outside), its size as a count of elementary charges, that count for each square
 * micrometre of membrane, and the sign that sits at the inner face ("minus", "plus" or
 * null for none). The outer face carries as much of the other sign.
 */
export function membraneCharge(run, fed) {
  const { inputs } = fed;
  const voltage = voltageOf(run, inputs.voltage);
  const capacitance = readerOf(run, inputs.capacitance), area = readerOf(run, inputs.area);
  return {
    at(step, membrane) {
      const volts = voltage(step, membrane), farads = capacitance(step, membrane), squareMetres = area(step, membrane);
      const coulombs = charge(farads, volts), charges = chargesIn(coulombs);
      return { voltage: volts, capacitance: farads, area: squareMetres, coulombs, charges, per_um2: charges / (squareMetres * 1e12), inside: coulombs < 0 ? "minus" : coulombs > 0 ? "plus" : null };
    },
  };
}

/** The largest of a function's values over every valid record of a run and every one of `count` entities. */
export function largest(run, count, valueAt) {
  let most = 0;
  for (let step = 0; step < run.count; step++) {
    if (!run.isValid(step)) continue;
    for (let entity = 0; entity < count; entity++) {
      const value = valueAt(step, entity);
      if (value > most) most = value;
    }
  }
  return most;
}
