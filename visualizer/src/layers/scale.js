// Where a value stands between the two ends of the scale it is drawn on.

/**
 * The share of the way from `low` to `high`, held to 0..1. A count is drawn in whole
 * steps (`steps`), so that every step has one colour and one height.
 */
export function shareOf(value, { low, high, steps = 0 }) {
  let share = (value - low) / (high - low);
  if (steps) share = Math.round(share * steps) / steps;
  return Math.min(1, Math.max(0, share));
}

/**
 * A round number at or just above a magnitude, for the full size of a scale: close enough
 * that the largest value nearly fills it (59.2 gives 60, not 100).
 */
export function roundUp(value) {
  if (!(value > 0)) return 1;
  const power = Math.pow(10, Math.floor(Math.log10(value)));
  const size = [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 7, 8, 10].find((step) => step * power >= value * (1 - 1e-9)) ?? 10;
  return Number((size * power).toPrecision(12));
}
