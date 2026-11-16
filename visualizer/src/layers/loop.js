// A species' own looping run, read for the Cell view (schema/QUANTITY_LAYERS.md, rule 7):
// "a run the engine made of that one cell and packaged to loop. The picture then names the
// run, says that it loops, and gives the loop's length in the cell's time and how much it
// is slowed."
//
// Its place in the data. A packaged replay (schema/RUN_VIEW.md) says that it is a loop in
// its view, in the shape the engine's run-view writer gives it (docs/LOOPING_REPLAY_DESIGN.md
// on the engine's side, proposed 16 November 2026):
//   view.loop = { species, cell, period, closes: { within, says, tolerance, zero? }, not_measured?, follows? }
//     species   the id of the species whose cell the run is
//     cell      the id of that cell in the run's set of cells
//     period    the loop's length in the run's time; it must agree with the records' span
//     closes    the run's own word that its last record meets its first: `within`, the
//               largest relative difference of any level between the two as the writer
//               measured it, `tolerance`, the one its caller declared (the writer refuses a
//               block above it, and so does the reader), and `says`, the sentence the page
//               may show. A run that does not say so is not played.
//     not_measured  the records the run's closure leaves out, by reason ([{ why, records }]: the running totals,
//               which grow by design); `closes.zero` the records identically zero over the loop. Carried, and said
//               with the closure: a record not measured is never read as one that meets itself.
//     follows   for a cell cycle: [{ time, from, to }], the cell the loop follows from that
//               time on, after a division. Carried and said on the page; the hand-over itself
//               is not drawn yet, and the streams are read for the loop's first cell.
// The loop is the run's records from the first to the last, the last being the closing
// record: its length is the period, and every rate is a mean between two records that both
// lie inside it. No difference is ever taken across the seam, where a running total falls
// back from its last value to its first.
//
// The revision: the packaged replay's own `run.revision`, or where a package carries the
// engine's source instead, `run.source.revision` (with its dirty flag, carried).
//
// The species names its run from its own side (the species' file, `cell.loop`: the
// replay's id); until a species does, the Cell view has no run and may show illustration.
//
// Refused: a run that is an example (rule 6: invented numbers are no species' run), one
// that names no model of the engine or no revision, one made of another species' cell, one
// that does not say it closes or closes above its own tolerance, one whose period is not the
// records' span, and one that follows a cell the run does not have.

import { layersFor, readDeclarations } from "./layers.js";
import { declared, family, fromFirst, livesOn } from "./records.js";
import { membranesOf } from "./membrane.js";
import { MARKS } from "./marks/index.js";
import { streamsOf, meanRate, tokenFor, beadsASecond, ionsASecond } from "./marks/beads.js";
import declaredLayers from "../../data/layers/layers.json" with { type: "json" };

const { layers: LAYERS } = readDeclarations(declaredLayers, MARKS);
/** The declared layer whose records the loop's lanes are read from: the totals carried through channel populations, with the pump's cycles and the membrane's own routes. */
export const TRAFFIC = "ion-traffic";
/** The declared layer whose totals give the loop's lanes across the cell's borders: through its junctions, and by its exchange routes. */
export const TRANSFERS = "transfers";
/** What is read of a looping run, in the page's words: for a part whose total is none of these, the reason it is not drawn. */
export const READ_WORDS = "of a looping run the viewer reads what crossed the cell's channels, its pumps, its membrane itself, its junctions and its exchange routes";

/**
 * The streams across the loop's cell's borders that the run saved totals for, as the
 * transfers layer declares them (marks/stream.js): one for each species of each junction
 * that has the cell at one end, and one for each exchange route on any membrane of the cell. A
 * stream is as marks/beads.js, streamsOf, gives one: { kind ("junction" or "route"), name,
 * record, source, entity, species, per, out }, `out` saying whether a positive total left
 * the cell. A junction's total is positive from its sender to its receiver as its sign
 * declares, so it leaves the cell where the cell is the end the sign names as the source; a
 * route's is positive out of the cell where its sign's source is the cell. A total with no
 * declared direction gives no stream, and neither does one that never changes.
 */
export function bordersOf(run, sources, cell) {
  const streams = [];
  const membranes = membranesOf(run)?.of(cell) || [];
  for (const source of sources) {
    const record = run.records.get(source.id), set = run.sets.get(source.set), geometry = set?.geometry;
    const first = fromFirst(source.sign);
    if (!record || !geometry || first === null) continue;
    for (let entity = 0; entity < set.ids.length; entity++) {
      let kind = null, out = null;
      if (geometry.kind === "links" && geometry.between === "cell") {
        const ends = geometry.ends[entity] || [];
        if (ends[0] === cell) [kind, out] = ["junction", first];
        else if (ends[1] === cell) [kind, out] = ["junction", !first];
      } else if (geometry.kind === "on" && geometry.set === "membrane" && membranes.includes(geometry.index[entity]) && livesOn(run, source.set) === "route") {
        [kind, out] = ["route", first];
      }
      if (!kind) continue;
      let moves = false;
      const at0 = record.at(0, entity);
      for (let step = 1; step < run.count && !moves; step++) moves = record.at(step, entity) !== at0;
      if (!moves) continue;
      const species = source.species ?? (Array.isArray(set.species) && typeof set.species[entity] === "string" ? set.species[entity] : null);
      streams.push({ kind, name: set.ids[entity], record, source, entity, species, per: 1, out });
    }
  }
  return streams;
}


/**
 * A run as a species' loop: { ok: true, loop } or { ok: false, why }. The loop is
 * { run, species, name, label, models, revision, dirty, cell, membrane, start, length,
 * closes, follows }: `cell` and `membrane` are numbers in the run's sets (`membrane` null
 * where the cell has none), `length` is the period in seconds of the cell's time, `follows`
 * the cells it follows after a division ([] for none).
 */
export function readLoop(run, speciesId) {
  const no = (why) => ({ ok: false, why });
  const said = run?.view?.loop;
  if (!said || typeof said !== "object") return no("The run does not say that it is a loop.");
  if (run.example) return no("The run is an example with invented numbers: it is no species' run.");
  const models = run.info?.engine_models || [];
  const revision = run.info?.revision || run.info?.source?.revision || null;
  if (!models.length || !revision) return no("The run names no model of the engine, or no revision: it is not shown as a species' run.");
  if (said.species !== speciesId) return no(`The run is the loop of another species' cell (${said.species ?? "none named"}).`);
  const cell = run.sets.get("cell")?.ids.indexOf(said.cell) ?? -1;
  if (cell < 0) return no(`The run has no cell called ${said.cell ?? "(none named)"}.`);
  const closes = said.closes;
  if (!closes || !(closes.within >= 0) || !(closes.tolerance >= 0) || typeof closes.says !== "string" || !closes.says.trim()) return no("The run does not say that its end meets its start within a tolerance: a loop that does not close is not played.");
  if (closes.within > closes.tolerance) return no(`The run's last record meets its first within ${figure(closes.within)}, above its own tolerance of ${figure(closes.tolerance)}: it is not played as a loop.`);
  if (!(run.count >= 2) || !(run.end > run.start)) return no("The run holds a single record: a loop needs an interval.");
  const span = run.end - run.start;
  // The records are kept in 32 bits: the period agrees with their span to within what that allows.
  if (!(said.period > 0) || Math.abs(said.period - span) > 1e-6 * Math.max(1, said.period)) return no(`The run's loop gives a period of ${said.period ?? "none"}, and its records span ${clock_(span)}: they must be the same.`);
  const follows = [];
  for (const step of said.follows || []) {
    const to = run.sets.get("cell")?.ids.indexOf(step?.to) ?? -1;
    if (!(step?.time >= run.start && step.time <= run.end) || typeof step.from !== "string" || to < 0) return no(`The loop follows a cell the run does not have, or at a time outside it (${JSON.stringify(step)}).`);
    follows.push({ time: step.time, from: step.from, to: step.to });
  }
  const membranes = membranesOf(run);
  const own = membranes ? membranes.of(cell) : [];
  return {
    ok: true,
    loop: {
      run, species: speciesId, name: run.id, label: run.info?.label || null, models, revision, dirty: run.info?.source?.dirty ?? null,
      cell, membrane: own.length ? own[0] : null, start: run.start, length: said.period,
      closes: { within: closes.within, tolerance: closes.tolerance, says: closes.says.trim() }, follows,
      // What the run's closure leaves out, by its reason, and the records identically zero over the loop, as the run
      // states them: a record not measured is not one that meets itself, and the page says how many there are.
      notMeasured: (Array.isArray(said.not_measured) ? said.not_measured : []).filter((group) => typeof group?.why === "string" && Array.isArray(group.records) && group.records.length).map((group) => ({ why: group.why.trim(), records: [...group.records] })),
      zero: Array.isArray(closes.zero) ? [...closes.zero] : [],
    },
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
 * the pump, and through the membrane itself; and, as the transfers layer reads them
 * (bordersOf), through each of its junctions and by each exchange route on its membrane. Returns { ok, streams, busiest, needs, why }:
 * `busiest` is the largest mean rate of any of them over any interval of the loop, in fmol
 * a second (what the token is sized by); `needs` names the files of records that must be
 * fetched first.
 */
export function loopStreams(loop) {
  const { run, membrane, cell } = loop;
  const offers = layersFor(run, LAYERS, MARKS);
  const fed = offers.find((item) => item.layer.id === TRAFFIC), across = offers.find((item) => item.layer.id === TRANSFERS);
  // What crossed the cell's junctions and its exchange routes is read where the run saved it, beside its membrane's own traffic.
  const borders = across?.ok ? across : null;
  const needs = [...(fed?.ok ? fed.parts : []), ...(borders ? borders.parts : [])];
  if (!fed?.ok && !borders) return { ok: false, streams: [], busiest: 0, needs: [], why: fed?.why || "The run saved no totals of what crossed its membranes." };
  if (needs.length) return { ok: false, streams: [], busiest: 0, needs, why: "Some of the run's records are in files of their own that are not yet fetched." };
  if (membrane === null) return { ok: false, streams: [], busiest: 0, needs: [], why: "The run does not say which membrane lies on the loop's cell." };
  const streams = [];
  if (fed?.ok) {
    const pump = fed.extras.find((entry) => entry.role === "pump");
    const cycles = pump ? declared(run, pump.record) : null;
    const leak = fed.extras.find((entry) => entry.role === "leak");
    const leaks = !leak ? [] : leak.field ? family(run, leak.field) : [declared(run, leak.record)].filter(Boolean);
    streams.push(...streamsOf(run, fed.sources || [], cycles, membrane, leaks));
  }
  if (borders) streams.push(...bordersOf(run, borders.sources || [], cell));
  if (!streams.length) return { ok: false, streams: [], busiest: 0, needs: [], why: `The run saved no total of anything that crossed this cell's borders that the viewer reads: ${READ_WORDS}.` };
  let busiest = 0;
  for (const stream of streams) {
    for (let step = 1; step < run.count; step++) {
      const mean = meanRate(run, stream.record, stream.entity, step);
      if (mean !== null) busiest = Math.max(busiest, Math.abs(mean * stream.per));
    }
  }
  return { ok: true, streams, busiest, needs: [], why: null };
}

/**
 * One token for the whole loop at a slow-down: how many particles a bead stands for. The
 * Cell view has no timeline, so a loop is slowed from its legend (marks/beads.js, SLOWS); a
 * slow-down of a thousand is a speed of a thousandth.
 */
export function loopToken(busiest, slow = 1) {
  return tokenFor(ionsASecond(busiest), 1 / slow);
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
    return { stream, mean, ions, perSecond: mean ? beadsASecond(ionsASecond(mean), token, 1 / slow) : 0, out: mean ? mean > 0 === stream.out : null };
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
      // Fuel has no path in the engine, run or no run; anything else is simply not among what is read of a run.
      withheld.push({ id: kind.id, part: kind.part, label: kind.label, why: kind.nothing || `Not read from the run: ${READ_WORDS}, and no total of this is among them.` });
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

/**
 * What the picture says of a loop for as long as it shows: the run's name (and its own label,
 * where it has one), that it loops, its length in the cell's time, and from when it follows
 * another cell after a division.
 */
export function loopWords(loop, speciesLabel, clock) {
  const follows = (loop.follows || []).map((step) => ` · from ${clock(step.time)} it follows ${step.to}, a daughter of ${step.from}`).join("");
  return `${speciesLabel} · the engine's looping run ${loop.name}${loop.label ? ` (${loop.label})` : ""} · a loop of ${clock(loop.length)} of the cell's time${follows}`;
}

/**
 * The engine's revision behind the loop, and what the run says of the tree it was made from: clean, or with changes
 * that were not committed. Nothing is said of the tree where the package carries no source of the engine's.
 */
export function engineWords(loop) {
  const tree = loop.dirty === true ? ", from a tree with changes that were not committed" : loop.dirty === false ? ", from a clean tree" : "";
  return `Made by the engine at revision ${loop.revision}${tree}`;
}

/**
 * How closely the loop closes, as the run measured it and against the tolerance its caller declared; and, where the run
 * says its closure leaves records out (running totals grow by design) or finds some identically zero, how many, in its
 * own words.
 */
export function closesWords(loop) {
  const are = (count) => `${count} ${count === 1 ? "is" : "are"}`;
  const rest = [...(loop.notMeasured || []).map((group) => `${are(group.records.length)} not measured (${group.why})`), ...(loop.zero?.length ? [`${are(loop.zero.length)} identically zero over the loop`] : [])];
  return `Its last record meets its first within ${figure(loop.closes.within)} (tolerance ${figure(loop.closes.tolerance)})${rest.length ? `, in the records it measures; of its records, ${rest.join("; ")}` : ""}`;
}

/** A small relative figure, for the page. */
function figure(value) {
  return value === 0 ? "0" : value < 1e-3 ? value.toExponential(1) : String(Number(value.toPrecision(2)));
}

const clock_ = (seconds) => `${Number(seconds.toPrecision(6))} s`;
