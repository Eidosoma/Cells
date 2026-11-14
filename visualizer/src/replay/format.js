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
  if (seconds < 60) return `${precise ? number(seconds, 1) : Math.round(seconds)} s`;
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
const DISPLAY = { V: { unit: "mV", factor: 1000, decimals: 1 } };

/** The unit a record is shown in, and how to get there from the stored value. */
export function display(record) {
  return DISPLAY[record?.unit] || { unit: record?.unit && record.unit !== "1" ? record.unit : "", factor: 1, decimals: record?.dtype?.startsWith("float") ? 3 : 0 };
}

/** A recorded value with its unit, or null for a record that may only be drawn. */
export function reading(record, value) {
  if (!record || record.quantised) return null; // a quantised record is never printed as a recorded number
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
