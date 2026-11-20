// A bound on time, held as a measure. A check that holds a time (a frame's milliseconds, a view's update, a repaint)
// wraps that comparison in `within(name, value, bound)`: the measure's line, with its value, its unit, its bound and
// whether it stands within it, goes into the scenario's log, and tools/check_all.mjs gathers it into the run's summary.
//
// Every bound is held on every run:
//   - run by hand, in the runner's alone phase, or run again there, a measure over its bound fails its check, as any
//     check fails;
//   - beside other browsers (tools/check_all.mjs sets CELLS_MEASURES=beside while several scenarios run at once), a
//     measure within its bound has been held there, under load, the harder case; one over its bound is said in the log
//     ("deferred") and leaves its check to the rest of its condition, and the runner runs the scenario again alone,
//     after the others, where the measure is judged. A check whose other parts fail fails beside others as before, and
//     the scenario is not run again.
// A count of work (draw calls, triangles, files fetched, bytes) is never a measure: it stays pass or fail everywhere.

export const MEASURE_LINE = /^measure {2}(\{.*\})$/gm;

/** Whether the scenario runs beside others, where a measure over its bound is left to a run alone. */
export const beside = (env = process.env) => env.CELLS_MEASURES === "beside";

/**
 * Whether `value` stands within `bound` (under it; at most it with `most`), its line written into the log. Beside
 * others, a finite value over its bound returns true and says it is deferred to a run alone; anything else returns
 * the comparison itself.
 */
export function within(name, value, bound, { unit = "ms", most = false, env = process.env, log = console.log } = {}) {
  const number = typeof value === "number" && Number.isFinite(value);
  const holds = number && (most ? value <= bound : value < bound);
  const deferred = !holds && number && beside(env);
  log(`measure  ${JSON.stringify({ name, value: number ? value : String(value), unit, bound, op: most ? "<=" : "<", within: holds, ...(deferred ? { deferred: true } : {}) })}`);
  return holds || deferred;
}

/** Every measure a scenario's log holds, in order. */
export function measuresIn(text) {
  const found = [];
  for (const match of String(text).matchAll(MEASURE_LINE)) {
    try {
      found.push(JSON.parse(match[1]));
    } catch {}
  }
  return found;
}
