// What a trace (src/replay/trace.js) reads at the clock, apart from the page so that it can be tested on real runs: the
// run's own record at or before the player's time, or the record under the pointer. A view may keep a clock of its own
// (the tumour tissue's is the union of the times of every run in view), so the player's row is not the run's row: the
// run's own record is found by time. Past the run's last record, its last record.

import { clock, number } from "./format.js";

/** The run's own record shown at the player's time: its last record at or before that time. */
export const recordAt = (run, player) => run.indexAt(player.time);

/**
 * The read-out: { playing, step, reading, when }. `value(step)` is the series' value in the units `shown` gives
 * ({ decimals, unit }); `extra(step)` more words, or null; `pinned` the record under the pointer, or null.
 */
export function traceReading({ run, player, pinned = null, value, shown, extra = null }) {
  const playing = recordAt(run, player);
  const step = pinned ?? playing;
  const reading = run.isValid(step) ? `${number(value(step), shown.decimals)}${shown.unit ? ` ${shown.unit}` : ""}` : "not a valid record";
  const more = extra ? extra(step) : "";
  return { playing, step, reading, when: ` at ${clock(run.t[step], { precise: true })}${pinned === null ? "" : " (under the pointer)"}${more ? ` · ${more}` : ""}` };
}
