// A sweep's chart for the Experiments view: where an experiment's summary lists arms with a
// parameter and readouts (the catalogue's `sweeps`, written by tools/adapt_run.py from the
// summary and from nothing else; schema/RUN_VIEW.md, "A sweep's chart"), each arm is a point:
// the parameter along the chart, the readouts up it (one line for each), the arm shown marked,
// and the experiment's own reference for a readout drawn as that, in the summary's words. The
// viewer computes nothing from the numbers and says nothing of how they compare: it places
// them, and the table gives them as the summary states them.

/** Whether a parameter's values ask for a logarithmic scale: all above nought, the largest ten times the smallest or more. */
export function logScaleFor(values) {
  const finite = values.filter((value) => Number.isFinite(value));
  if (finite.length < 2 || finite.some((value) => value <= 0)) return false;
  return Math.max(...finite) / Math.min(...finite) >= 10;
}

/** Round bounds for a readout axis that hold every value given, with a few round ticks between. */
export function niceRange(values) {
  const finite = values.filter((value) => Number.isFinite(value));
  if (!finite.length) return { low: 0, high: 1, ticks: [0, 0.5, 1] };
  let low = Math.min(...finite), high = Math.max(...finite);
  if (low === high) {
    const pad = Math.abs(low) * 0.1 || 1;
    low -= pad;
    high += pad;
  }
  const raw = (high - low) / 4, power = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((k) => k * power).find((k) => k >= raw) || 10 * power;
  const start = Math.floor(low / step) * step, end = Math.ceil(high / step) * step;
  const ticks = [];
  for (let at = start; at <= end + step * 1e-9; at += step) ticks.push(Number(at.toPrecision(12)));
  return { low: start, high: end, ticks };
}

/**
 * The experiment's sweeps as the card draws them: each arm with its run in the catalogue (null where
 * none is packaged), whether it is the run shown, and whether the parameter is drawn on a log scale.
 */
export function sweepsOf(experiment, runIds, shown) {
  const known = new Set(runIds);
  return (experiment?.sweeps || [])
    .filter((sweep) => Array.isArray(sweep?.arms) && sweep.arms.length >= 2 && Array.isArray(sweep.readouts) && sweep.readouts.length && sweep.parameter)
    .map((sweep) => {
      const arms = sweep.arms.map((arm) => ({ ...arm, run: arm.run && known.has(arm.run) ? arm.run : null, active: Boolean(arm.run) && arm.run === shown }));
      return { ...sweep, arms, log: logScaleFor(arms.map((arm) => arm.parameter)) };
    });
}

/**
 * Where each thing of a sweep's chart stands, in a box `width` by `height` with room `pad` round the
 * plot: { x(value), y(value), points: [{ arm, readout, value, x, y }], references: [...], xTicks, yTicks }.
 * Arms are ordered along the parameter as the summary gives their values.
 */
export function chartOf(sweep, { width = 240, height = 150, pad = { left: 38, right: 10, top: 10, bottom: 30 } } = {}) {
  const values = sweep.arms.map((arm) => arm.parameter);
  const lowX = Math.min(...values), highX = Math.max(...values);
  const span = (value) => (sweep.log ? Math.log10(value) : value);
  const [a, b] = lowX === highX ? [span(lowX) - 1, span(highX) + 1] : [span(lowX), span(highX)];
  const inner = { left: pad.left, right: width - pad.right, top: pad.top, bottom: height - pad.bottom };
  const margin = (inner.right - inner.left) * 0.06;
  const x = (value) => inner.left + margin + ((span(value) - a) / (b - a)) * (inner.right - inner.left - 2 * margin);
  const all = [];
  for (const arm of sweep.arms) for (const readout of sweep.readouts) {
    if (Number.isFinite(arm.readouts?.[readout.id])) all.push(arm.readouts[readout.id]);
    if (Number.isFinite(arm.reference?.[readout.id])) all.push(arm.reference[readout.id]);
  }
  const range = niceRange(all);
  const y = (value) => inner.bottom - ((value - range.low) / (range.high - range.low)) * (inner.bottom - inner.top);
  const points = [], references = [];
  sweep.arms.forEach((arm, index) => {
    sweep.readouts.forEach((readout, line) => {
      const value = arm.readouts?.[readout.id];
      if (Number.isFinite(value)) points.push({ arm: index, readout: readout.id, line, value, x: x(arm.parameter), y: y(value) });
      const reference = arm.reference?.[readout.id];
      if (Number.isFinite(reference)) references.push({ arm: index, readout: readout.id, line, value: reference, x: x(arm.parameter), y: y(reference) });
    });
  });
  // Ticks along the parameter: the arms' own values, as the summary gives them.
  const xTicks = [...new Set(values)].sort((p, q) => p - q).map((value) => ({ value, at: x(value) }));
  const yTicks = range.ticks.map((value) => ({ value, at: y(value) }));
  return { width, height, inner, x, y, points, references, xTicks, yTicks, range };
}

/** A sweep as a table: a row for each arm, its parameter, its readouts and, where stated, the reference. */
export function tableOf(sweep, write = String) {
  const unit = (item) => (item.unit && item.unit !== "1" ? ` (${item.unit})` : "");
  const references = sweep.reference ? sweep.readouts.filter((readout) => sweep.arms.some((arm) => Number.isFinite(arm.reference?.[readout.id]))) : [];
  const head = [`${sweep.parameter.label}${unit(sweep.parameter)}`, ...sweep.readouts.map((readout) => `${readout.label}${unit(readout)}`), ...references.map((readout) => `${readout.label}, ${sweep.reference.label}${unit(readout)}`)];
  const rows = [...sweep.arms]
    .sort((p, q) => p.parameter - q.parameter)
    .map((arm) => ({ arm: arm.arm, run: arm.run, active: arm.active, cells: [write(arm.parameter), ...sweep.readouts.map((readout) => (Number.isFinite(arm.readouts?.[readout.id]) ? write(arm.readouts[readout.id]) : "")), ...references.map((readout) => (Number.isFinite(arm.reference?.[readout.id]) ? write(arm.reference[readout.id]) : ""))] }));
  return { head, rows };
}

/** What a point says to a screen reader and in its title: the arm, its parameter and its readouts, whether it is shown, and whether it has a run. */
export function armWords(sweep, arm, write = String) {
  const unit = (item) => (item.unit && item.unit !== "1" ? ` ${item.unit}` : "");
  const readouts = sweep.readouts.filter((readout) => Number.isFinite(arm.readouts?.[readout.id])).map((readout) => `${readout.label} ${write(arm.readouts[readout.id])}${unit(readout)}`);
  const reference = sweep.reference ? sweep.readouts.filter((readout) => Number.isFinite(arm.reference?.[readout.id])).map((readout) => `${sweep.reference.label}: ${write(arm.reference[readout.id])}${unit(readout)}`) : [];
  const state = arm.active ? "shown now" : arm.run ? "press to show it" : "no run of it is packaged here";
  return `${arm.arm}: ${sweep.parameter.label} ${write(arm.parameter)}${unit(sweep.parameter)}; ${[...readouts, ...reference].join("; ")}; ${state}`;
}
