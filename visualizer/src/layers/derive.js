// The four rules by which the viewer may work a number out from saved ones
// (schema/QUANTITY_LAYERS.md, rule 1). The list is closed: a layer's numbers are a saved
// record, or one of these, and one of these is always shown as "worked out by the viewer
// from …". Nothing here computes a law again: no flux from a permeability, no gate, no
// reaction rate. Pure functions, no state.

// The engine's own constants (src/cells/processes/electrochemistry.py), written the same way.
export const FARADAY = 6.02214076e23 * 1.602176634e-19; // C/mol
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

/**
 * For one ion at one membrane: the two terms of the engine's own electrochemical potential
 * difference, R T ln(c inside / c outside) and z F V, and their sum, in J/mol; and each
 * divided by z F, in volts, which is how they are shown. Null where a concentration is not
 * positive, the valence is zero or the temperature is not positive: the engine refuses
 * such values too.
 */
export function potentialTerms({ inside, outside, voltage, valence, temperature }) {
  if (!(inside > 0) || !(outside > 0) || !valence || !(temperature > 0) || !Number.isFinite(voltage)) return null;
  // A difference of logarithms, as the engine writes it.
  const concentration = GAS * temperature * (Math.log(inside) - Math.log(outside));
  const electrical = valence * FARADAY * voltage;
  const per = valence * FARADAY;
  return {
    concentration,
    electrical,
    sum: concentration + electrical,
    volts: { concentration: concentration / per, electrical: voltage, sum: (concentration + electrical) / per },
  };
}

/**
 * The rules, by name, with the words each is shown under. `inputs` names what a rule is
 * worked out from, so a legend can say it.
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
    says: (inputs) => `Worked out by the viewer from ${inputs}: capacitance times voltage, with the capacitance and the area as the run's definition gives them.`,
  },
  "potential terms": {
    label: "The terms of the electrochemical potential",
    says: (inputs) => `Worked out by the viewer from ${inputs}: the two terms of the engine's own electrochemical potential difference, R T ln(c inside / c outside) and z F V, each divided by z F.`,
  },
};

export const isDerivation = (name) => Object.prototype.hasOwnProperty.call(DERIVATIONS, name);
