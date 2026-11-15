// beads: tokens that cross a piece of one membrane through its channel populations and
// its pumps, as many a second as the run's saved totals grew between two records. A bead is
// a token of a rate, not an ion: the legend says how many ions one stands for and what time
// the picture keeps (schema/QUANTITY_LAYERS.md, rule 3).
//
//   beads a second on the screen = ions a second / (ions in one bead x how much it is slowed)
//
// The rate sets how many beads pass, never how fast one travels: every bead crosses the
// membrane in the same time, which stands for nothing.
//
// This module holds the mark's place in the design and its arithmetic. It does not draw
// yet (`built: false`): no run on disk saved the amounts transferred, and the contract
// allows no made-up example for it now. A layer whose mark is not built is listed for a run
// with that reason, and cannot be switched on. When it is built it draws on the close-up of
// a chosen cell's membrane, like the arrows and the marks of the charge: forms that stand
// through the piece (one for each channel population and pump), with the beads crossing in
// them, drawn in the order the close-up keeps for them (`forms`, `beads`), and it moves on
// the lens's own frames through `tick(milliseconds)`.

export const PER_FMOL = 6.02214076e23 * 1e-15; // ions in a femtomole
export const BUSIEST = 10; // beads a second on the screen for a run's busiest stream
export const SLOWS = [1, 1e3, 1e6]; // the slow-downs offered: true speed, a thousand times, a million times

/**
 * How many ions one bead stands for at a slow-down: 1, 2 or 5 times a power of ten, the
 * smallest with which the run's busiest stream passes at most ten beads a second. Never
 * under one ion: slowed enough, a bead is an ion.
 */
export function tokenFor(busiest, slow = 1) {
  const raw = Math.abs(busiest) / (BUSIEST * slow);
  if (!(raw > 1)) return 1;
  const power = Math.pow(10, Math.floor(Math.log10(raw)));
  const size = [1, 2, 5, 10].find((step) => step * power >= raw * (1 - 1e-9)) ?? 10;
  return Math.round(size * power);
}

/** How many beads pass in a second on the screen, for a rate in ions a second: its size alone. */
export function beadsASecond(ions, token, slow = 1) {
  return Math.abs(ions) / (token * slow);
}

/** A rate in femtomoles a second as ions a second. */
export const ionsASecond = (fmol) => fmol * PER_FMOL;

/** What time the picture keeps, in the legend's words: true speed, or how much it is slowed and what a second here is in the cell. */
export function timeWords(slow = 1) {
  if (!(slow > 1)) return "True speed: one second here is one second in the cell";
  const seconds = 1 / slow;
  const [value, unit] = seconds >= 1e-3 ? [seconds * 1e3, "millisecond"] : seconds >= 1e-6 ? [seconds * 1e6, "microsecond"] : [seconds * 1e9, "nanosecond"];
  const shown = Number(value.toPrecision(3));
  return `Slowed ${slow.toLocaleString("en-US")} times: one second here is ${shown === 1 ? `one ${unit}` : `${shown.toLocaleString("en-US")} ${unit}s`} in the cell`;
}

/** What one bead stands for, in the legend's words. */
export function tokenWords(token) {
  return token === 1 ? "One bead is one ion" : `One bead is ${token.toLocaleString("en-US")} ions`;
}

export const beads = {
  name: "beads",
  channels: ["motion"],
  lives_on: ["channel population", "pump population", "membrane"],
  surface: "membrane",
  built: false,
  /** Why a run that saved what the layer needs is still not shown it. */
  waits: "The viewer's beads are not built yet: they come with the first run that saved the amounts carried through channels and pumps.",

  /** The legend's lines for a layer of beads: what one bead stands for, and what time the picture keeps. */
  keys(busiest, slow = 1) {
    return [
      { key: "bead", text: `${tokenWords(tokenFor(busiest, slow))}. More beads a second means more ions a second; how fast a bead travels stands for nothing` },
      { key: "time", text: timeWords(slow) },
    ];
  },

  create() {
    throw new Error("the beads are not built yet");
  },
};
