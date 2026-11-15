// A species' own looping run, read for the Cell view (schema/QUANTITY_LAYERS.md, rule 7):
// "a run the engine made of that one cell and packaged to loop. The picture then names the
// run, says that it loops, and gives the loop's length in the cell's time and how much it
// is slowed."
//
// Its place in the data. A packaged replay (schema/RUN_VIEW.md) says that it is a loop in
// its view:
//   view.loop = { species, cell, closes: { within, says } }
//     species   the id of the species whose cell the run is
//     cell      the id of that cell in the run's set of cells
//     closes    the run's own word that its last record meets its first: `within`, the
//               largest relative difference of any level between the two, and `says`, the
//               sentence the page may show. A run that does not say so is not played.
// The loop is the run's records from the first to the last, the last being the closing
// record: its length is the time between them, and every rate is a mean between two
// records that both lie inside it. No difference is ever taken across the seam, where a
// running total falls back from its last value to its first.
//
// The species names its run from its own side (the species' file, `cell.loop`: the
// replay's id); until a species does, the Cell view has no run and may show illustration.
//
// Refused: a run that is an example (rule 6: invented numbers are no species' run), one
// that names no model of the engine or no revision, one made of another species' cell,
// and one that does not say it closes.

import { layersFor, readDeclarations } from "./layers.js";
import { declared, family } from "./records.js";
import { membranesOf } from "./membrane.js";
import { MARKS } from "./marks/index.js";
import { streamsOf, meanRate, tokenFor, beadsASecond, ionsASecond } from "./marks/beads.js";
import declaredLayers from "../../data/layers/layers.json" with { type: "json" };

const { layers: LAYERS } = readDeclarations(declaredLayers, MARKS);
/** The declared layer whose records the loop's lanes are read from: the totals carried through channel populations, with the pump's cycles and the membrane's own routes. */
export const TRAFFIC = "ion-traffic";

/**
 * A run as a species' loop: { ok: true, loop } or { ok: false, why }. The loop is
 * { run, species, name, models, revision, cell, membrane, start, length, closes }: `cell`
 * and `membrane` are numbers in the run's sets (`membrane` null where the cell has none),
 * `length` is in seconds of the cell's time.
 */
export function readLoop(run, speciesId) {
  const no = (why) => ({ ok: false, why });
  const said = run?.view?.loop;
  if (!said || typeof said !== "object") return no("The run does not say that it is a loop.");
  if (run.example) return no("The run is an example with invented numbers: it is no species' run.");
  const models = run.info?.engine_models || [];
  if (!models.length || !run.info?.revision) return no("The run names no model of the engine, or no revision: it is not shown as a species' run.");
  if (said.species !== speciesId) return no(`The run is the loop of another species' cell (${said.species ?? "none named"}).`);
  const cell = run.sets.get("cell")?.ids.indexOf(said.cell) ?? -1;
  if (cell < 0) return no(`The run has no cell called ${said.cell ?? "(none named)"}.`);
  const closes = said.closes;
  if (!closes || !(closes.within >= 0) || typeof closes.says !== "string" || !closes.says.trim()) return no("The run does not say that its end meets its start: a loop that does not close is not played.");
  if (!(run.count >= 2) || !(run.end > run.start)) return no("The run holds a single record: a loop needs an interval.");
  const membranes = membranesOf(run);
  const own = membranes ? membranes.of(cell) : [];
  return {
    ok: true,
    loop: { run, species: speciesId, name: run.id, models, revision: run.info.revision, cell, membrane: own.length ? own[0] : null, start: run.start, length: run.end - run.start, closes: { within: closes.within, says: closes.says.trim() } },
  };
}

/**
 * Where a loop stands after `seconds` of the cell's time since it began to play: { time,
 * step, interval, turns }. `step` is the record that ends the interval the time lies in, so
 * a rate at that record is a mean over an interval inside the loop, whatever the time; it
 * is never the first record, across which lies the seam. `turns` counts the times round.
 */
export function loopAt(loop, seconds) {
  const { run, length, start } = loop;
  const elapsed = Math.max(0, seconds);
  const turns = Math.floor(elapsed / length);
  const time = start + (elapsed - turns * length);
  let step = 1;
  while (step < run.count - 1 && run.t[step] <= time) step++;
  return { time, step, interval: [run.t[step - 1], run.t[step]], turns };
}

/**
 * The streams through the loop's cell that the run saved totals for, as the bead layer of
 * the replay reads them (marks/beads.js, streamsOf): through each channel population, by
 * the pump, and through the membrane itself. Returns { ok, streams, busiest, needs, why }:
 * `busiest` is the largest mean rate of any of them over any interval of the loop, in fmol
 * a second (what the token is sized by); `needs` names the files of records that must be
 * fetched first.
 */
export function loopStreams(loop) {
  const { run, membrane } = loop;
  const fed = layersFor(run, LAYERS, MARKS).find((item) => item.layer.id === TRAFFIC);
  if (!fed?.ok) return { ok: false, streams: [], busiest: 0, needs: [], why: fed?.why || "The run saved no totals of what crossed its membranes." };
  if (fed.parts.length) return { ok: false, streams: [], busiest: 0, needs: fed.parts, why: "Some of the run's records are in files of their own that are not yet fetched." };
  if (membrane === null) return { ok: false, streams: [], busiest: 0, needs: [], why: "The run does not say which membrane lies on the loop's cell." };
  const pump = fed.extras.find((entry) => entry.role === "pump");
  const cycles = pump ? declared(run, pump.record) : null;
  const leak = fed.extras.find((entry) => entry.role === "leak");
  const leaks = !leak ? [] : leak.field ? family(run, leak.field) : [declared(run, leak.record)].filter(Boolean);
  const streams = streamsOf(run, fed.sources || [], cycles, membrane, leaks);
  let busiest = 0;
  for (const stream of streams) {
    for (let step = 1; step < run.count; step++) {
      const mean = meanRate(run, stream.record, stream.entity, step);
      if (mean !== null) busiest = Math.max(busiest, Math.abs(mean * stream.per));
    }
  }
  return { ok: true, streams, busiest, needs: [], why: null };
}

/** One token for the whole loop at a slowing: how many particles a bead stands for. */
export function loopToken(busiest, slow = 1) {
  return tokenFor(ionsASecond(busiest), slow);
}

/**
 * Each stream's rate over the interval that ends at record `step`: [{ stream, mean, ions,
 * perSecond, out }]. `mean` is in fmol a second and positive as the record's sign says,
 * `ions` in particles a second, `perSecond` in beads a second on the screen, and `out`
 * says whether what moved left the cell (null where nothing moved, or no rate is given).
 */
export function loopRates(loop, streams, step, token, slow = 1) {
  return streams.map((stream) => {
    const rate = meanRate(loop.run, stream.record, stream.entity, step);
    const mean = rate === null ? null : rate * stream.per;
    const ions = mean === null ? null : Math.abs(ionsASecond(mean));
    return { stream, mean, ions, perSecond: mean ? beadsASecond(ionsASecond(mean), token, slow) : 0, out: mean ? mean > 0 === stream.out : null };
  });
}

/**
 * What a loop draws for a species: the plan's shape of ./flux.js, with one lane for each
 * stream. `flux` are the checked declarations: a kind that names a `stream` takes the
 * run's streams of that kind; the kinds the reader does not read from a run are named in
 * `withheld`, each with that reason, where the species has the part. Illustration never
 * fills them in: a species with a run shows no illustration (rule 11), and that holds
 * where nothing of the run could be read (`unread` says why): everything is then withheld.
 */
export function planFromLoop(flux, loop, streams, { has, unread = null }) {
  const kinds = [], withheld = [];
  for (const kind of flux?.kinds || []) {
    if (!has(kind.part)) continue;
    if (!kind.stream) {
      withheld.push({ id: kind.id, part: kind.part, label: kind.label, why: "Not read from the run: of a looping run the viewer reads what crossed the membrane through its channels, by its pumps and by its own routes." });
      continue;
    }
    const own = streams.filter((stream) => stream.kind === kind.stream);
    if (!own.length) {
      // `unread` is why nothing of the run's streams could be read at all (./loop.js, loopStreams).
      withheld.push({ id: kind.id, part: kind.part, label: kind.label, why: unread || "The run saved no total for it." });
      continue;
    }
    const lanes = own.map((stream, index) => ({
      id: `${stream.name}/${stream.species ?? index}`,
      key: `${kind.id}/${stream.name}/${stream.species ?? index}`,
      label: [stream.name, stream.species].filter(Boolean).join(" · "),
      way: null, // the run's own sign says it, interval by interval
      species: stream.species || null,
      spots: null,
      count: null,
      claimed: true,
      stream,
    }));
    kinds.push({ id: kind.id, part: kind.part, label: kind.label, token: kind.token || "particle", groups: [{ id: "run", label: kind.label, claimed: true, law: null, says: "Each lane goes the way its total grew over the interval shown, by the run's own signs.", basis: null, lanes }] });
  }
  return { kinds, withheld };
}

/** What the picture says of a loop for as long as it shows: the run's name, that it loops, and its length in the cell's time. */
export function loopWords(loop, speciesLabel, clock) {
  return `${speciesLabel} · the engine's looping run ${loop.name} · a loop of ${clock(loop.length)} of the cell's time`;
}
