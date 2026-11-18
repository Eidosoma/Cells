// The four rules by which the viewer may work a number out from saved ones
// (schema/QUANTITY_LAYERS.md, rule 1). The list is closed: a layer's numbers are a saved
// record, or one of these, and one of these is always shown as "worked out by the viewer
// from …". Nothing here computes a law again: no flux from a permeability, no gate, no
// reaction rate. Pure functions, no state.

// The engine's own constants (src/cells/laws/electrochemistry.py), written the same way.
export const ELEMENTARY = 1.602176634e-19; // C
export const FARADAY = 6.02214076e23 * ELEMENTARY; // C/mol
export const GAS = 6.02214076e23 * 1.380649e-23; // J/(mol K)

/** A level at one end of a junction less the level at the other. */
export function difference(here, there) {
  return here - there;
}

/**
 * A cumulative record at one saved time less the same at the one before, divided by the
 * time between: the mean rate over that interval. Null where there is no earlier record or
 * no time between them.
 */
export function rate(now, before, seconds) {
  if (!(seconds > 0) || !Number.isFinite(now) || !Number.isFinite(before)) return null;
  return (now - before) / seconds;
}

/** Capacitance times voltage: the charge a membrane voltage stands for, in coulombs. */
export function charge(capacitance, voltage) {
  return capacitance * voltage;
}

/** How many elementary charges a charge in coulombs is: its size, without its sign. */
export function chargesIn(coulombs) {
  return Math.abs(coulombs) / ELEMENTARY;
}

/** Which way a term of the potential difference drives its ion: out of the cell where the ion's potential is the higher inside. */
const driven = (joulesPerMole) => (joulesPerMole > 0 ? "out" : joulesPerMole < 0 ? "in" : null);

/**
 * For one ion at one membrane: the two terms of the engine's own electrochemical potential
 * difference, R T ln(c inside / c outside) and z F V, and their sum, in J/mol; each divided
 * by z F, in volts, which is how the contract writes them (`volts`); and for drawing, each
 * term's size in volts (`size`) with the way it drives the ion itself (`drives`: "out" of
 * the cell, "in", or null where it is nothing). `voltage` is the inside less the outside.
 *
 * The way a term drives its ion is read from the term in J/mol, never from the volts:
 * dividing by z F turns the sign round for a negative ion.
 *
 * Null where a concentration is not positive, the valence is zero or the temperature is
 * not positive: the engine refuses such values too.
 */
export function potentialTerms({ inside, outside, voltage, valence, temperature }) {
  if (!(inside > 0) || !(outside > 0) || !valence || !(temperature > 0) || !Number.isFinite(voltage)) return null;
  // A difference of logarithms, as the engine writes it.
  const concentration = GAS * temperature * (Math.log(inside) - Math.log(outside));
  const electrical = valence * FARADAY * voltage;
  const sum = concentration + electrical;
  const per = valence * FARADAY;
  const each = Math.abs(per);
  return {
    concentration,
    electrical,
    sum,
    volts: { concentration: concentration / per, electrical: voltage, sum: sum / per },
    size: { concentration: Math.abs(concentration) / each, electrical: Math.abs(electrical) / each, sum: Math.abs(sum) / each },
    drives: { concentration: driven(concentration), electrical: driven(electrical), sum: driven(sum) },
  };
}

/**
 * The rules, by name, with the words each is shown under. `inputs` names what a rule is
 * worked out from, so a legend can say it.
 *
 * A rule with several inputs lists them by the part each plays (`inputs`): what the input
 * must lie on, whether there is one for each species (`per`), and whether its sign must be
 * declared for the rule to give a direction (`signed`). A layer's declaration names, for
 * each part, the records or the constants of a run that may fill it.
 */
export const DERIVATIONS = {
  difference: {
    label: "A difference",
    says: (inputs) => `Worked out by the viewer from ${inputs}: the value at one end of a junction less the value at the other.`,
  },
  rate: {
    label: "A mean rate",
    says: (inputs) => `Worked out by the viewer from ${inputs}: the saved total at one record less the total at the record before, divided by the time between. A mean over that interval.`,
  },
  charge: {
    label: "Charge",
    says: (inputs) => `Worked out by the viewer from ${inputs}: capacitance times voltage. It is shown as a count of charges, that charge over the charge of one, on a stated area of the membrane.`,
    inputs: {
      voltage: { on: "membrane", signed: true, says: "the membrane voltage" },
      capacitance: { on: "membrane", says: "the membrane's capacitance" },
      area: { on: "membrane", says: "the membrane's area" },
    },
  },
  "potential terms": {
    label: "The terms of the electrochemical potential",
    says: (inputs) => `Worked out by the viewer from ${inputs}: the two terms of the engine's own electrochemical potential difference, R T ln(c inside / c outside) and z F V, each divided by z F.`,
    inputs: {
      voltage: { on: "membrane", signed: true, says: "the membrane voltage" },
      inside: { on: "cell", per: "species", says: "the concentration of each ion in the cell" },
      outside: { on: "outside node", per: "species", says: "the concentration of each ion outside" },
      temperature: { on: "world", says: "the temperature" },
      valence: { per: "species", says: "each ion's valence" },
    },
  },
};

export const isDerivation = (name) => Object.prototype.hasOwnProperty.call(DERIVATIONS, name);
