// How a replay writes times and values. Plain units, and the true minus sign.

const MINUS = "−";

/** A number with a fixed count of decimals, written with a real minus sign. */
export function number(value, decimals = 1) {
  if (!Number.isFinite(value)) return "no value";
  const text = Math.abs(value).toFixed(decimals);
  return (value < 0 && Number(text) !== 0 ? MINUS : "") + text;
}

/** A time in the run: "13.8 s", "12 min 30 s", "1 h 5 min". */
export function clock(seconds, { precise = false } = {}) {
  if (!Number.isFinite(seconds)) return "";
  // Under ten seconds a tenth matters (a run of four seconds): it is kept unless the time is whole.
  if (seconds < 60) return `${precise || (seconds < 10 && Math.abs(seconds - Math.round(seconds)) >= 0.05) ? number(seconds, 1) : Math.round(seconds)} s`;
  const whole = Math.round(seconds);
  const hours = Math.floor(whole / 3600), minutes = Math.floor((whole % 3600) / 60), rest = whole % 60;
  if (hours) return minutes ? `${hours} h ${minutes} min` : `${hours} h`;
  return rest ? `${minutes} min ${rest} s` : `${minutes} min`;
}

/** A length of time, rounded for reading: "39 min". */
export function duration(seconds) {
  if (seconds < 90) return `${Math.round(seconds)} s`;
  if (seconds < 5400) return `${Math.round(seconds / 60)} min`;
  return `${number(seconds / 3600, 1)} h`;
}

// A record keeps the unit it was saved in; some read better in another.
// A unit written in plain letters is shown in its own sign (uM as µM): the same unit, never converted.
const DISPLAY = { V: { unit: "mV", factor: 1000, decimals: 1 }, uM: { unit: "µM", factor: 1, decimals: 3 } };
// An amount or an energy far under one unit reads in a smaller one: the largest in which the record's largest value is at least a tenth.
const SMALLER = { fmol: [["fmol", 1], ["amol", 1e3], ["zmol", 1e6]], pJ: [["pJ", 1], ["fJ", 1e3], ["aJ", 1e6]] };
const RATES = { fmol: [["fmol a second", 1], ["amol a second", 1e3], ["zmol a second", 1e6]], pJ: [["pW", 1], ["fW", 1e3], ["aW", 1e6]] };
const fitting = (steps, most) => (most > 0 ? steps.find(([, factor]) => most * factor >= 0.1) || steps[steps.length - 1] : steps[0]);

/** A unit as the page writes it, where only its sign differs (uM as µM); a unit shown in another size (V as mV) is left as given. */
export const unitSign = (unit) => (DISPLAY[unit]?.factor === 1 ? DISPLAY[unit].unit : unit);

/** The unit a record is shown in, and how to get there from the stored value. */
export function display(record) {
  if (DISPLAY[record?.unit]) return DISPLAY[record.unit];
  const steps = SMALLER[record?.unit];
  if (steps && Array.isArray(record.range)) {
    const [unit, factor] = fitting(steps, Math.max(Math.abs(record.range[0]), Math.abs(record.range[1])));
    return { unit, factor, decimals: 3 };
  }
  return { unit: record?.unit && record.unit !== "1" ? record.unit : "", factor: 1, decimals: record?.dtype?.startsWith("float") ? 3 : 0 };
}

/**
 * The unit a rate is shown in, for the unit of the total it is worked out from and the
 * largest rate there is to show: { unit, factor }. An energy a second is a power.
 */
export function rateDisplay(unit, most) {
  const steps = RATES[unit];
  if (!steps) return { unit: unit && unit !== "1" ? `${unit} a second` : "a second", factor: 1 };
  const [name, factor] = fitting(steps, Math.abs(most));
  return { unit: name, factor };
}

/** A recorded value with its unit, or null for a record that may only be drawn. */
export function reading(record, value) {
  if (!record || record.quantised) return null; // a quantised record is never printed as a recorded number
  if (Array.isArray(record.words)) return record.words[value] ?? "no value"; // a state, in the words its record gives
  if (!Number.isFinite(value)) return "no value";
  const shown = display(record);
  return `${number(value * shown.factor, shown.decimals)}${shown.unit ? ` ${shown.unit}` : ""}`;
}

/** Round limits for a scale: the range widened to whole steps of 1, 2 or 5 times a power of ten. */
export function niceDomain(low, high, steps = 7) {
  if (!(high > low)) return { low: low - 0.5, high: high + 0.5, step: 0.5 };
  const rough = (high - low) / steps;
  const power = Math.pow(10, Math.floor(Math.log10(rough)));
  const step = [1, 2, 5, 10].map((size) => size * power).find((size) => size >= rough) ?? 10 * power;
  // Rounding keeps a limit that already sits on a step (to within floating error) where it is.
  const fit = (value, round) => Number((round(value / step + (round === Math.floor ? 1e-9 : -1e-9)) * step).toPrecision(12));
  return { low: fit(low, Math.floor), high: fit(high, Math.ceil), step };
}
