// The clock of an assembly view: what the page's one time control (the Experiments timeline and
// its Player) is handed for a lineage of fissions. The run states its clock (schema/ASSEMBLY_RUN.md,
// `time`): it counts fissions, in the run's own words. The steps are fissions a second of watching,
// with molecule by molecule at the slow end where every run shown has its event trace; there is no
// "true speed", since the model's time is nominal.

import { countedBase } from "../replay/player.js";
import { PART } from "./assembly_run.js";

/** Fissions a second of watching, slowest first; the opening step; and the slow end, in molecules. */
export const LADDER = [0.25, 0.5, 1, 2, 4, 8];
export const OPENING = 0.5;
export const MOLECULES_A_SECOND = 4;
export const SPLIT_SECONDS = 1.6; // how long a split takes to watch, molecule by molecule
/** The number the molecule-by-molecule step goes by in the ladder: a tag, not a rate (its advance is its own). */
export const FINE = 1 / 1000;

/** Where the clock is after `seconds` of watching molecule by molecule: so many molecules, and the splits at their own pace. */
export function advanceByMolecules(run, time, seconds, end) {
  let t = time, left = seconds;
  for (let guard = 0; left > 1e-9 && t < end && guard < 10000; guard++) {
    const at = run.phaseAt(t);
    if (at.phase === "split") {
      const rate = (2 * PART) / SPLIT_SECONDS, boundary = Math.min(end, at.k + PART + 1e-6);
      const needed = (boundary - t) / rate;
      if (needed >= left) return t + left * rate;
      t = boundary;
      left -= needed;
    } else {
      const from = at.g === 0 ? 0 : at.g + PART, to = at.g + 1 - PART;
      const perEvent = (to - from) / (run.growthLength(at.g) + 1);
      const rate = perEvent * MOLECULES_A_SECOND, boundary = Math.min(end, to + 1e-6);
      const needed = (boundary - t) / rate;
      if (needed >= left) return t + left * rate;
      t = boundary;
      left -= needed;
    }
  }
  return Math.min(end, t);
}

/** What the Player loads for these runs: their records are the fissions, and the time base is the runs' own. */
export function clockOf(set, runs) {
  const count = Math.max(...runs.map((run) => run.fissionCount));
  const end = count + PART;
  const traced = runs.every((run) => run.hasTrace);
  const words = set.time;
  const fine = traced
    ? {
        speed: FINE,
        words: {
          short: "by molecule",
          phrase: `molecule by molecule, ${MOLECULES_A_SECOND} a second`,
          says: `Molecule by molecule: ${MOLECULES_A_SECOND} molecules join or leave each second of watching, and a ${words.unit} takes ${SPLIT_SECONDS} seconds`,
        },
        advance: (time, seconds) => advanceByMolecules(runs[0], time, seconds, end),
      }
    : null;
  const timeBase = countedBase({ id: words.base, unit: words.unit, plural: words.plural, ladder: LADDER, opening: OPENING, fine });
  const t = Array.from({ length: count + 1 }, (_, k) => k);
  return {
    start: 0,
    end,
    t,
    count: t.length,
    indexAt: (time) => Math.min(count, Math.max(0, Math.floor(time + 1e-9))),
    events: [],
    eventsBy: () => 0,
    validity: null,
    isValid: () => true,
    info: { judged_s: null },
    timeBase,
    traced,
  };
}

/** Fissions a second of watching at a speed of the clock, for the beads' rule on motion (the molecule step is slower than any). */
export function fissionsPerSecond(speed) {
  return speed === FINE ? 0 : speed;
}
