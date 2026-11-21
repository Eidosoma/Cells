// The Experiments landing's cards (schema/EXPERIMENT_CARDS.md): the file is what its tool writes from
// tracked files; every card has a band, a kind and a standing or the stated reason for none; every count
// names its file and every source its revision; the map and the cards say one thing of each part; the
// gap-junction work keeps its D138 words and no word of agreement; "example" and "invented numbers"
// never stand on one card; and the gathering reads each layout of the record as it is (on fixtures: no
// test reads the saved runs or the engine's repository).
//
//   node --test tests/experiment_cards.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { cpSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { faceOf, levelOf, verdictsOf } from "../src/replay/landing.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TOOL = path.join(ROOT, "tools", "build_cards.py");
const FIXTURES = path.join(ROOT, "tests", "cards-fixtures");
const read = (file) => JSON.parse(readFileSync(path.join(ROOT, file), "utf8"));
const text = (file) => readFileSync(path.join(ROOT, file), "utf8");
// The cards as the tool builds them: their faces (cards.json, what the landing draws) and each card whole (cards.details.json).
// The rules on standings, sources and counts below are held on the cards whole; the faces are held to be the cards whole
// with every field the face does not read left out.
const faces = read("data/replays/cards.json");
const details = read("data/replays/cards.details.json");
const cards = { ...faces, cards: details.cards };
const readings = read("data/replays/cards.readings.json");
const source = read("data/replays/cards.source.json");
const catalogue = read("data/replays/overlay.json");
const map = read("data/architecture/overlay.json");
const scene = read("data/architecture/architecture.scene.json");
const byId = new Map(cards.cards.map((card) => [card.id, card]));
const typed = new Map(source.cards.map((card) => [card.id, card]));
const tool = (args) => spawnSync("python3", ["-I", TOOL, ...args], { encoding: "utf8" });

const FULL = /^[0-9a-f]{40}$/;
const NAME = /^[A-Za-z0-9._-]+$/;
const CLOCK = /\b\d{1,2}:\d{2}\b/;
const MACHINE = /\/(mnt|home|tmp|root)\//;
// The gap-junction work: never said to have been replicated, to reproduce, to agree or to match (the record's
// own name for the work, "replication", stands only in a source's path and place).
const AGREEMENT = /replicated|replicates|reproduc|agree|\bmatch(es|ed|ing)?\b/i;
const D138 = "Development work, not judged (D138).";

/** A map part as the map's overlay holds it: a component, or an operator by its scene id (op.<key>). */
const partOf = (id) => (id.startsWith("op.") ? { id, ...map.operators.items[id.slice(3)] } : map.components.find((part) => part.id === id));
/** A place of the record with its clock time left out, as the tool leaves it out (a date stays, a time of day in UTC goes). */
const withoutClock = (value) =>
  value
    .replace(/,?\s*(?:about\s+|at\s+)?\b\d{1,2}:\d{2}(?:\s*[–-]\s*\d{1,2}:\d{2})?\s*UTC\b/g, "")
    .replace(/\(\s*[,;]?\s*\)/g, "")
    .replace(/\(\s*[,;]\s*/g, "(")
    .replace(/\s+([),.;:])/g, "$1")
    .replace(/\s+/g, " ")
    .trim();

/** Every object in a value that is a source: a path with a revision (or, wrongly, a path without one). */
function sourcesIn(value, found = []) {
  if (Array.isArray(value)) value.forEach((item) => sourcesIn(item, found));
  else if (value && typeof value === "object") {
    if (typeof value.path === "string") found.push(value);
    Object.values(value).forEach((item) => sourcesIn(item, found));
  }
  return found;
}

/** The strings of a card a visitor may read: none of its sources, provenance, identifiers or addresses. */
const NOT_SHOWN = new Set(["id", "part", "experiment", "experiments", "entry", "opens", "evidence", "within", "file", "field", "revision", "path", "where", "protocol", "from", "run", "runs_from", "sources", "source", "reference", "modules", "rows_from", "status", "kind", "band", "still", "folder", "catalogue"]);
function shown(value, found = []) {
  if (typeof value === "string") found.push(value);
  else if (Array.isArray(value)) value.forEach((item) => shown(item, found));
  else if (value && typeof value === "object") for (const [key, item] of Object.entries(value)) if (!NOT_SHOWN.has(key)) shown(item, found);
  return found;
}

/** What a card says that the gap-junction work may never say: each string a visitor reads that does. */
const agreementWords = (card) => shown(card).filter((words) => AGREEMENT.test(words) || /replicat/i.test(words));
/** Whether a card puts "example" and "invented numbers" on one card, in any of their forms ("the numbers are invented"). */
const mixesExample = (card) => {
  const words = [...shown(card), ...sourcesIn(card).map((item) => item.where || "")].join(" ");
  return /\bexamples?\b/i.test(words) && /\binvent/i.test(words);
};
/** The words typed by hand in a source file that claim a standing (none may: what a card says of one is read). */
const typedClaims = (given) =>
  [...given.bands.filter((band) => band.id !== "judged").flatMap((band) => [band.label, band.says, band.control]), given.not_run.says, ...given.cards.flatMap((card) => [card.title, typeof card.asks === "string" ? card.asks : null, card.shows, card.none])]
    .filter(Boolean)
    .filter((words) => /judg|qualif/i.test(words));
const copy = (value) => JSON.parse(JSON.stringify(value));

test("the faces are the cards whole with every field the face does not read left out: the landing draws the same card from either", () => {
  assert.deepEqual(faces.cards.map((card) => card.id), details.cards.map((card) => card.id), "one card a face, in the same order");
  assert.deepEqual(Object.keys(faces), ["format", "note", "built_from", "bands", "not_run", "listing", "details", "cards"], "the faces' top level: the bands, the listing, and the file of the details");
  assert.deepEqual(Object.keys(details), ["format", "note", "built_from", "cards"]);
  // Every value of a face is the whole card's own (its record: the entries with a verdict, in their order).
  const within = (part, of) => (part === null || typeof part !== "object" ? part === of : Array.isArray(part) ? Array.isArray(of) && part.length === of.length && part.every((item, n) => within(item, of[n])) : of !== null && typeof of === "object" && Object.entries(part).every(([key, value]) => key in of && within(value, of[key])));
  for (const [n, face] of faces.cards.entries()) {
    const whole = { ...details.cards[n], record: (details.cards[n].record || []).filter((entry) => entry?.verdict && typeof entry.verdict === "object") };
    assert.ok(within(face, whole), `${face.id}: its face holds a value its whole card does not`);
    for (const plays of [null, { run: "x" }]) assert.deepEqual(faceOf(face, { plays }), faceOf(details.cards[n], { plays }), `${face.id}: the landing draws the same face from either`);
  }
  // The List and the search read a card's id, title and part; llms.txt its title, level and verdict lines: the faces hold them.
  for (const [n, face] of faces.cards.entries()) assert.deepEqual([face.id, face.title, face.standing.part, levelOf(face), verdictsOf(face)], [details.cards[n].id, details.cards[n].title, details.cards[n].standing.part, levelOf(details.cards[n]), verdictsOf(details.cards[n])]);
  assert.ok(text("data/replays/cards.json").length * 2 < text("data/replays/cards.details.json").length, "the faces are under half the whole");
});

test("the cards are what the tool writes from tracked files and the readings", () => {
  const run = tool(["--check"]);
  assert.equal(run.status, 0, run.stderr || run.stdout);
  assert.equal(faces.format, "cells.visualizer.experiment_cards@2");
  assert.equal(details.format, "cells.visualizer.experiment_card_details@1");
  assert.equal(faces.details, "cards.details.json");
  assert.deepEqual(details.built_from, faces.built_from);
  assert.equal(readings.format, "cells.visualizer.experiment_cards_readings@1");
  assert.equal(cards.built_from.record.revision, source.record.revision);
  assert.equal(readings.record.revision, source.record.revision);
  // The map's revision is the scene's own, the one its links are built at.
  assert.ok(scene.meta.source_base_url.endsWith(`/blob/${cards.built_from.map.revision}/`));
});

test("four bands in order, each card in one, of one of three kinds, with a standing or the stated reason for none", () => {
  assert.deepEqual(cards.bands.map((band) => band.id), ["examples", "judged", "development", "invented"]);
  const listed = cards.bands.flatMap((band) => band.cards);
  assert.deepEqual(listed, cards.cards.map((card) => card.id));
  for (const band of cards.bands) for (const id of band.cards) assert.equal(byId.get(id).band, band.id);
  for (const card of cards.cards) {
    assert.ok(["replay", "standing", "rows"].includes(card.kind), card.id);
    assert.ok(typeof card.title === "string" && card.title, card.id);
    assert.ok(typeof card.asks === "string" || typeof card.shows === "string", `${card.id}: it says what it asks or what it shows`);
    const standing = card.standing;
    assert.ok((typeof standing.says === "string" && standing.says) || (typeof standing.none === "string" && standing.none), `${card.id}: a standing or the reason for none`);
    if (standing.status === null && standing.from === "map") assert.ok(standing.none && standing.first, `${card.id}: the map states no level, and the card says why and what stands first`);
    if (card.kind === "replay") {
      assert.ok(card.replay && "still" in card.replay, `${card.id}: a replay names its still (the landing's)`);
      assert.ok(Number.isInteger(card.replay.runs) && card.replay.runs >= 1, card.id);
      assert.equal(card.replay.runs_from.reduce((sum, item) => sum + item.runs, 0), card.replay.runs, card.id);
    } else {
      // Room for a rerun at a named revision, which is never the judged run.
      assert.ok("rerun" in card, card.id);
      if (card.rerun !== null) {
        assert.match(card.rerun.revision, FULL);
        // It says that it is a rerun, and never calls itself the judged run ("not the judged run" may stand).
        assert.ok(/rerun|run again/i.test(card.rerun.says || "") && !/(?<!not )the judged run/i.test(card.rerun.says), card.id);
      }
    }
    if (card.kind === "rows") {
      assert.ok(card.rows.length > 0);
      for (const row of card.rows) assert.ok(row.id && row.claim && typeof row.passed === "boolean" && FULL.test(row.reference.revision), JSON.stringify(row));
    }
  }
  // The examples to start with are the two the page has today, and the invented numbers stand alone.
  assert.deepEqual(cards.bands[0].cards, ["tumour-tissue", "assembly"]);
  assert.deepEqual(cards.bands[3].cards, ["test-sheet"]);
  // Each later band folds on the landing behind a control in the file's words (19 November 2026), carried from the source
  // as typed; a band may leave them out (the landing then makes a plain control from its label).
  for (const band of cards.bands) {
    const given = source.bands.find((item) => item.id === band.id);
    assert.equal(band.control, given.control, band.id);
    if ("control" in band) assert.ok(typeof band.control === "string" && band.control.trim() === band.control && band.control, band.id);
  }
  assert.ok(cards.bands.slice(1).every((band) => band.control), "every later band has its control's words");
  // The judged band's words are true of each of its cards: a registered qualification or a judged run (passed or failed).
  assert.equal(cards.bands[1].control, "qualifications and judged runs");
  for (const id of cards.bands[1].cards) {
    const card = byId.get(id);
    const said = card.record.map((entry) => `${entry.says} ${entry.item || ""}`).join(" ");
    assert.ok(/qualif|judged|passes|passed|FAIL|fails/i.test(said) || ["qualified", "failed"].includes(card.standing.status), `${id}: neither a qualification nor a judged run in its record`);
  }
  const folder = mkdtempSync(path.join(os.tmpdir(), "cells-cards-control-"));
  try {
    const given = path.join(folder, "source.json"), built = path.join(folder, "cards.json");
    const unworded = copy(source);
    delete unworded.bands[2].control;
    writeFileSync(given, JSON.stringify(unworded));
    const run = tool(["--source", given, "--out", built]);
    assert.equal(run.status, 0, run.stderr);
    assert.ok(!("control" in JSON.parse(readFileSync(built, "utf8")).bands[2]), "a band without its control's words is built without them");
    const blank = copy(source);
    blank.bands[1].control = " ";
    writeFileSync(given, JSON.stringify(blank));
    assert.equal(tool(["--source", given, "--out", built]).status, 2, "a blank control's words are refused");
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test("every source names its revision, each one the gathering found on main, and nothing names a machine or a clock", () => {
  const known = new Set([...readings.on_main, readings.record.revision]);
  for (const item of sourcesIn(cards.cards)) {
    assert.match(item.revision || "", FULL, JSON.stringify(item));
    assert.ok(known.has(item.revision), `${item.path} at ${item.revision}: not among the revisions the gathering found on main`);
    assert.ok(!item.path.startsWith("/") && !item.path.includes(".."), item.path);
  }
  for (const file of ["data/replays/cards.json", "data/replays/cards.details.json", "data/replays/cards.readings.json", "data/replays/cards.source.json"]) {
    assert.doesNotMatch(text(file), MACHINE, file);
    assert.doesNotMatch(text(file), CLOCK, file);
  }
});

test("every count names its file and field, and every verdict its run and day", () => {
  let counted = 0;
  for (const card of cards.cards) {
    for (const entry of card.record) {
      assert.ok(entry.says && FULL.test(entry.source.revision), card.id);
      const verdict = entry.verdict;
      if (!verdict) continue;
      assert.equal(typeof verdict.passed, "boolean");
      assert.ok(NAME.test(verdict.run.evidence) && verdict.run.within.every((part) => NAME.test(part)), card.id);
      assert.match(verdict.day.date, /^\d{4}-\d{2}-\d{2}$/);
      assert.ok(verdict.day.from.file.length > 0 && verdict.day.from.field, card.id);
      if (verdict.count === null) {
        assert.ok(verdict.count_withheld, `${card.id}: a count left off says why`);
        continue;
      }
      counted += 1;
      const { count } = verdict;
      assert.ok(Number.isInteger(count.passed) && Number.isInteger(count.of) && count.passed <= count.of && count.unit, card.id);
      assert.equal(verdict.passed, count.passed === count.of, card.id);
      assert.ok(NAME.test(count.from.evidence) && count.from.file.length > 0 && count.from.file.every((part) => NAME.test(part)) && count.from.field, card.id);
      if (verdict.snapshot) assert.ok(verdict.snapshot.revision === null ? verdict.snapshot.says : FULL.test(verdict.snapshot.revision), card.id);
    }
  }
  assert.ok(counted >= 10, `${counted} counts`);
});

test("a card's standing is its map part's, word for word: its level as the map gives it, and the tests the map names", () => {
  for (const card of cards.cards) {
    const standing = card.standing;
    if (standing.from !== "map") continue;
    const part = partOf(standing.part);
    assert.ok(part, standing.part);
    assert.equal(typed.get(card.id).map, standing.part);
    assert.equal(standing.status, part.status ?? null, card.id);
    assert.equal(standing.as_of, part.as_of ?? null, card.id);
    assert.equal(standing.says, part.plain, card.id);
    assert.equal(standing.label, part.label, card.id);
    assert.deepEqual(standing.sources.map((item) => item.path), part.sources.map((item) => item.path), card.id);
    for (const [index, item] of standing.sources.entries()) {
      assert.equal(item.revision, part.sources[index].revision || cards.built_from.map.revision);
      assert.equal(item.where, part.sources[index].where === undefined ? undefined : withoutClock(part.sources[index].where), card.id);
    }
    const status = map.statuses.find((item) => item.id === part.status);
    assert.deepEqual(standing.level, status ? { label: status.label, says: status.description } : null, card.id);
    assert.ok(!("level_withheld" in standing), card.id);
    assert.deepEqual(standing.tests, part.sources.map((item) => item.path).filter((file) => file.startsWith("tests/")), card.id);
  }
});

test("a card says judged or qualified only where a map part or a verdict says so", () => {
  // One band for everything judged under a registered protocol, passed or failed: each card in it shows its own map
  // level, one of the band's, and a card whose level is neither qualified nor failed reads a judged run's verdict file.
  const judged = cards.bands.find((band) => band.id === "judged");
  assert.equal(judged.status, null);
  for (const level of judged.levels) {
    const status = map.statuses.find((item) => item.id === level.id);
    assert.deepEqual(level, { id: status.id, label: status.label, says: status.description });
  }
  for (const id of judged.cards) {
    const card = byId.get(id);
    assert.equal(card.standing.from, "map", id);
    assert.ok(judged.levels.some((level) => level.id === partOf(card.standing.part).status), id);
    if (!["qualified", "failed"].includes(card.standing.status)) assert.ok(card.record.some((entry) => entry.verdict), `${id}: no judged run's verdict behind it`);
  }
  // Passes and failures side by side in it, not set apart: a failed level and failed verdicts are among its cards.
  assert.ok(judged.cards.some((id) => byId.get(id).standing.status === "failed"));
  assert.ok(judged.cards.filter((id) => byId.get(id).record.some((entry) => entry.verdict?.passed === false)).length >= 4);
  for (const band of cards.bands.filter((item) => item.id !== "judged")) for (const id of band.cards) assert.notEqual(byId.get(id).standing.status, "failed", id);
  // Nothing typed by hand says either word: what the cards say of a standing is read.
  assert.deepEqual(typedClaims(source), []);
  // An answer of a judged experiment is the catalogue's, beside a map part at the judged level.
  for (const card of cards.cards.filter((item) => item.answer)) {
    const outcome = catalogue.experiments[card.answer.experiment].outcome;
    assert.deepEqual([card.answer.judged, card.answer.answer, card.answer.label, card.answer.text], [outcome.judged, outcome.answer, outcome.label, outcome.text]);
    if (card.answer.judged) assert.equal(card.standing.status, "qualified", card.id);
  }
  // A standing from the catalogue or an entry is its words, unchanged.
  for (const card of cards.cards) {
    const standing = card.standing;
    if (standing.from === "catalogue" && standing.says) {
      const outcome = catalogue.experiments[standing.experiment].outcome;
      assert.deepEqual([standing.says, standing.text], [outcome.status, outcome.text]);
    }
    if (standing.from === "entry") assert.equal(standing.says, read(`data/models/${standing.entry}.json`).modelled.text);
  }
});

test("the gap-junction work: the D138 words first, no standing of its own, its citation as the catalogue's, and no word of agreement", () => {
  const work = cards.cards.filter((card) => card.standing.part === "exp.gap_junction" || (card.replay?.experiments || []).some((id) => id.startsWith("gap-junction-")));
  assert.deepEqual(work.map((card) => card.id), ["tumour-tissue"]);
  for (const card of work) {
    assert.equal(card.standing.status, null);
    assert.equal(card.standing.first, D138);
    assert.ok(card.standing.says.startsWith(D138));
    for (const part of card.replay.parts) assert.match(part.status, /^Development work, not judged/);
    assert.deepEqual(agreementWords(card), []);
    assert.ok(catalogue.experiments[card.cite.from.catalogue].plain.includes(card.cite.says));
    assert.match(card.cite.says, /^J\. Grodstein, J\. Mathews and M\. Levin, .*doi:10\.64898\/2026\.09\.02\.748840 \(v1, CC BY 4\.0\)$/);
    // The note's own paragraph on the switch, at the revision whose words it is.
    assert.equal(card.switch.heading, "The switch, in plain words");
    assert.equal(card.switch.items.length, 4);
    assert.equal(card.switch.source.path, "docs/GAP_JUNCTION_CANCER_REPLICATION.md");
    assert.ok(card.switch.source.revision.startsWith("a4b2db3d"));
  }
  // What the card plays is the four experiments the page lists as one today.
  assert.deepEqual([...byId.get("tumour-tissue").replay.experiments].sort(), Object.keys(catalogue.experiments).filter((id) => id.startsWith("gap-junction-")).sort());
});

test("\"example\" and \"invented numbers\" never stand on one card", () => {
  for (const card of cards.cards) assert.ok(!mixesExample(card), card.id);
  const sheet = byId.get("test-sheet");
  assert.doesNotMatch([...shown(sheet), ...sourcesIn(sheet).map((item) => item.where || "")].join(" "), /\bexample/i);
  assert.match(sheet.standing.none, /invented/);
  const [examples, , , invented] = cards.bands;
  assert.doesNotMatch(`${examples.label} ${examples.says}`, /invented/i);
  assert.doesNotMatch(`${invented.label} ${invented.says} ${invented.control || ""}`, /\bexample/i);
  // The assembly keeps the catalogue's scoped words and is not called an example of invented numbers.
  assert.doesNotMatch(shown(byId.get("assembly")).join(" "), /invented/i);
});

test("the word rules catch what they are for: a planted card of each fault", () => {
  // "Agrees" in the note's paragraph, and "replicated" in a part's label, are caught; "replication" in a
  // source's place is the record's own name for the work, and is not.
  const agreeing = copy(byId.get("tumour-tissue"));
  agreeing.switch.items[0] += " The engine agrees with the preprint.";
  assert.equal(agreementWords(agreeing).length, 1);
  const replicated = copy(byId.get("tumour-tissue"));
  replicated.replay.parts[0].label = "The tissue line, replicated";
  assert.equal(agreementWords(replicated).length, 1);
  const sourced = copy(byId.get("tumour-tissue"));
  sourced.switch.source.where = "Section 4, The replication worlds";
  assert.deepEqual(agreementWords(sourced), []);
  // "Example" on the test sheet, beside its invented numbers.
  const sheet = copy(byId.get("test-sheet"));
  sheet.shows = "An example of the quantity layers.";
  assert.ok(mixesExample(sheet));
  // "Qualified" in a typed title, or "judged" in a typed question.
  const titled = copy(source);
  titled.cards[3].title = "FR-1: qualified";
  titled.cards[4].asks = "Was it judged?";
  assert.deepEqual(typedClaims(titled), ["FR-1: qualified", "Was it judged?"]);
  // "Judged" in a later band's control, outside the judged band; the judged band's own control may say it.
  const controlled = copy(source);
  controlled.bands.find((band) => band.id === "development").control = "development runs, not judged";
  assert.deepEqual(typedClaims(controlled), ["development runs, not judged"]);
});

test("a card's map part says on the page what it says in the map's overlay (the scene the page draws)", () => {
  const entities = new Map(scene.entities.map((entity) => [entity.id, entity]));
  for (const card of cards.cards.filter((item) => item.standing.from === "map")) {
    const part = partOf(card.standing.part);
    const entity = entities.get(card.standing.part);
    assert.ok(entity, `${card.standing.part} is not in the scene`);
    assert.deepEqual([entity.status ?? null, entity.as_of ?? null, entity.label, entity.plain], [part.status ?? null, part.as_of ?? null, part.label, part.plain], card.id);
    // The scene may name the part's code first; the overlay's sources follow in its order.
    const paths = (entity.sources || []).map((item) => item.path);
    let at = 0;
    for (const item of part.sources) {
      at = paths.indexOf(item.path, at);
      assert.ok(at >= 0, `${card.id}: ${item.path} is not among the scene's sources in order`);
      at += 1;
    }
  }
});

test("every entry of PROGRESS.md's runs that reports a judged run or a registered qualification is on a card or left out with a reason", () => {
  // The gathering lists them by their leads' words; a judged entry added to the record fails here until it is placed.
  assert.ok(readings.judged_entries.length >= 50, `${readings.judged_entries.length} entries`);
  const onCards = new Set(cards.cards.flatMap((card) => card.record.map((entry) => entry.says)));
  for (const item of source.entries_left_out) assert.ok(item.why && readings.judged_entries.some((lead) => lead.startsWith(item.entry)), `left out, and no such entry: ${item.entry}`);
  for (const lead of readings.judged_entries) {
    const left = source.entries_left_out.filter((item) => lead.startsWith(item.entry));
    assert.ok(onCards.has(lead) || left.length === 1, `not placed: ${lead}`);
    assert.ok(!(onCards.has(lead) && left.length), `both on a card and left out: ${lead}`);
  }
});

test("one judged run behind several cards says so on each, with its run's folder", () => {
  const byRun = new Map();
  for (const card of cards.cards) for (const entry of card.record) if (entry.verdict) {
    const key = JSON.stringify([entry.verdict.run.evidence, entry.verdict.run.within]);
    byRun.set(key, new Set([...(byRun.get(key) || []), card.id]));
  }
  for (const card of cards.cards) for (const entry of card.record) if (entry.verdict) {
    const others = [...byRun.get(JSON.stringify([entry.verdict.run.evidence, entry.verdict.run.within]))].filter((id) => id !== card.id).sort();
    assert.deepEqual(entry.verdict.also_on || [], others, card.id);
  }
  // The L4's run C stands behind the water, the replacement and the L4 agreement cards.
  const runC = byId.get("l4-agreement").record.find((entry) => entry.verdict?.run.within.join("/") === "c");
  assert.deepEqual(runC.verdict.also_on, ["replacement", "water"]);
});

test("what the landing lists: every replay the page packages, and today's list left as it is", () => {
  const replays = cards.cards.filter((card) => card.kind === "replay");
  assert.deepEqual(cards.listing.experiments, [...new Set(replays.flatMap((card) => card.replay.experiments))]);
  for (const id of cards.listing.experiments) assert.ok(catalogue.experiments[id], id);
  for (const id of ["e07-v1", "heredity-turnover-literature", "secreted-species-dev-run", "planarian-loop", "example-sheet"]) assert.ok(cards.listing.experiments.includes(id), id);
  assert.deepEqual(cards.listing.entries, catalogue.doors.map((door) => door.entry));
  // The tab opens on the landing, which lists from the cards (18 November 2026): the catalogue's overlay says nothing of listing.
  assert.deepEqual(Object.entries(catalogue.experiments).filter(([, entry]) => "listed" in entry).map(([id]) => id), []);
  // Every experiment part of the map is a card or is left out with a reason.
  const placed = new Set([...cards.cards.map((card) => card.standing.part).filter(Boolean), ...source.left_out.map((item) => item.part)]);
  for (const part of map.components.filter((item) => item.layer === "experiments")) assert.ok(placed.has(part.id), `${part.id} is neither on a card nor left out`);
  for (const item of source.left_out) assert.ok(item.why, item.part);
});

// --------------------------------------------------------------------------- the gathering, on fixtures

/** A copy of the fixture record, with what holds a clock time in the real record written here. */
function fixtureCopy(change = () => {}) {
  const folder = mkdtempSync(path.join(os.tmpdir(), "cells-cards-"));
  cpSync(FIXTURES, folder, { recursive: true });
  const time = (h, m, s) => [h, m, s].join(":");
  writeFileSync(path.join(folder, "evidence", "fixture-fr1", "judged", "run-a", "judged.done"), `2026-11-18T${time("01", "07", "35")}Z\n`);
  writeFileSync(path.join(folder, "evidence", "fixture-mg0a", "judged-01", "run.log"), `start 2026-11-09T${time("14", "00", "02")}Z\nexit 0 2026-11-10T${time("14", "02", "37")}Z\n`);
  writeFileSync(path.join(folder, "evidence", "fixture-harness", "run-1.log"), `2026-11-18T${time("12", "31", "01")}Z start\n2026-11-18T${time("12", "31", "30")}Z exit 0\n`);
  const progress = path.join(folder, "engine", source_main(), "PROGRESS.md");
  writeFileSync(progress, readFileSync(progress, "utf8").replace("(18 November 2026).**", `(18 November 2026, ${[["00", "57"].join(":"), ["01", "08"].join(":")].join("–")} UTC).**`));
  // The map's own revision counts as on main, as it does in the real repository.
  mkdirSync(path.join(folder, "engine", cards.built_from.map.revision), { recursive: true });
  change(folder);
  return folder;
}
const source_main = () => JSON.parse(readFileSync(path.join(FIXTURES, "source.json"), "utf8")).record.revision;
/** What the tool built in a folder: the faces' top level, with each card whole (from cards.details.json beside them). */
const builtIn = (folder) => ({ ...JSON.parse(readFileSync(path.join(folder, "cards.json"), "utf8")), cards: JSON.parse(readFileSync(path.join(folder, "cards.details.json"), "utf8")).cards });
const gatherIn = (folder, ...extra) => tool(["--gather", "--source", path.join(folder, "source.json"), "--readings", path.join(folder, "readings.json"), "--out", path.join(folder, "cards.json"), "--evidence", path.join(folder, "evidence"), "--repo-folders", path.join(folder, "engine"), ...extra]);

test("the gathering reads a verdict's own count, day and revision, and the record's sentence and scope line", () => {
  const folder = fixtureCopy();
  try {
    const run = gatherIn(folder);
    assert.equal(run.status, 0, run.stderr);
    const built = builtIn(folder);
    const fr1 = built.cards.find((card) => card.id === "fr1");
    const [first, second] = fr1.record;
    // Only the judged rows count: the unjudged row that failed is not one of them.
    assert.deepEqual([first.verdict.count.passed, first.verdict.count.of, first.verdict.count.unit], [3, 3, "judged criteria"]);
    assert.deepEqual(first.verdict.count.from.file, ["verdict", "verdict.json"]);
    assert.deepEqual(first.verdict.count.confirmed_by.map((item) => item.file || item.path), [["reading.json"], "PROGRESS.md"]);
    assert.equal(first.verdict.day.date, "2026-11-18");
    assert.equal(first.verdict.snapshot.revision, "4".repeat(40));
    assert.equal(first.verdict.protocol, "fixture-fr1-v1");
    // The record's lead with its clock time left out, and its scope line in its own words.
    assert.equal(first.says, "FR-1 judged: passed (18 November 2026).");
    assert.equal(first.scope.says, "Scope: the fixture operator as built at 4444444, on CPU only.");
    // A count the record words otherwise is left off, and says why; a snapshot off main names no revision.
    assert.equal(second.verdict.count, null);
    assert.match(second.verdict.count_withheld, /counts 5 of 5.*All 4 criteria/);
    assert.equal(second.verdict.snapshot.revision, null);
    assert.equal(second.verdict.day.date, "2026-11-10", "the day of the line it names, not of the file's first line");
    // The paragraph at its own revision, the same at the record's, its items as the note words them.
    assert.deepEqual(fr1.switch.items, ["The first item of the paragraph, on two lines.", "The second item."]);
    assert.equal(fr1.switch.source.revision, "2".repeat(40));
    // The other layouts of a verdict: a file's own tally with what was not evaluable; a mapping of names to verdicts
    // (a revision beside them is no verdict); several files, one verdict each. A date written out counts.
    const [, , tally, named, parts] = fr1.record;
    assert.deepEqual([tally.verdict.passed, tally.verdict.count.passed, tally.verdict.count.of, tally.verdict.count.not_evaluable, tally.verdict.protocol], [false, 1, 3, 1, "fixture-tally-v1"]);
    assert.equal(tally.verdict.day.date, "2026-11-10");
    assert.deepEqual([named.verdict.passed, named.verdict.count.passed, named.verdict.count.of, named.verdict.snapshot.revision], [true, 2, 2, "4".repeat(40)]);
    assert.deepEqual([parts.verdict.passed, parts.verdict.count.passed, parts.verdict.count.of], [false, 1, 2]);
    assert.deepEqual(parts.verdict.count.from.files, [["part-a", "Q1.json"], ["part-b", "Q2.json"]]);
    // A comparison's own numbers (FR-7's F4): each named table's compared and failed, or each quantity's, summed; its
    // day and its snapshot's revision as its RUN.txt writes them; the record's "All 11 rows" confirms the count.
    const compared = fr1.record[5];
    assert.deepEqual([compared.verdict.passed, compared.verdict.count.passed, compared.verdict.count.of, compared.verdict.count.unit], [true, 11, 11, "compared rows"]);
    assert.match(compared.verdict.count.from.field, /^arm_a\.quantities and arm_b\.quantities and persistence: each quantity's compared and failed numbers, summed/);
    assert.deepEqual(compared.verdict.count.confirmed_by.map((item) => item.says), ["All 11 rows"]);
    assert.deepEqual([compared.verdict.day.date, compared.verdict.snapshot.revision], ["2026-11-10", "4".repeat(40)]);
    // The gathering lists the record's judged entries by their leads, the registration among them, for placing.
    const listed = JSON.parse(readFileSync(path.join(folder, "readings.json"), "utf8")).judged_entries;
    assert.ok(listed.includes("A fixture qualification: FAIL (10 November).") && listed.some((lead) => lead.startsWith("The fixture's protocol registered")), listed.join(" | "));
    assert.ok(!listed.some((lead) => lead.startsWith("GARD's G1")), "an entry whose lead reports no judged run is not listed");
    // Rows with their references, at the references' own revision.
    const rows = built.cards.find((card) => card.id === "origin-laws").rows;
    assert.deepEqual(rows.map((row) => [row.id, row.claim, row.passed, row.modules.map((module) => module.path)]), [["OL1-1", "Claim one", true, ["validation/refs/one.py", "validation/refs/two.py"]], ["OL1-2", "Claim two", true, ["validation/refs/two.py"]]]);
    assert.equal(rows[0].reference.revision, "3".repeat(40));
    // A source the entry names with no revision is stamped with the record's, where the file is there.
    const assembly = built.cards.find((card) => card.id === "assembly");
    assert.ok(assembly.standing.sources.every((item) => item.revision === "1".repeat(40)));
    assert.doesNotMatch(readFileSync(path.join(folder, "cards.json"), "utf8"), CLOCK);
    assert.doesNotMatch(readFileSync(path.join(folder, "cards.details.json"), "utf8"), CLOCK);
    // The full check passes on what was just gathered, and fails once a run's own file changes.
    const again = gatherIn(folder, "--check");
    assert.equal(again.status, 0, again.stderr);
    writeFileSync(path.join(folder, "evidence", "fixture-fr1", "judged", "run-a", "judged.done"), `2026-11-19T${["01", "07", "35"].join(":")}Z\n`);
    const stale = tool(["--check", "--source", path.join(folder, "source.json"), "--readings", path.join(folder, "readings.json"), "--out", path.join(folder, "cards.json"), "--evidence", path.join(folder, "evidence"), "--repo-folders", path.join(folder, "engine")]);
    assert.equal(stale.status, 1, stale.stderr + stale.stdout);
    assert.match(stale.stderr, /stale against the record/);
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test("one command moves the record forward: the gathering at another revision writes it into the source file", () => {
  const later = "6".repeat(40);
  const folder = fixtureCopy((root) => cpSync(path.join(root, "engine", source_main()), path.join(root, "engine", later), { recursive: true }));
  try {
    const run = gatherIn(folder, "--revision", later.slice(0, 8));
    assert.equal(run.status, 0, run.stderr);
    assert.equal(JSON.parse(readFileSync(path.join(folder, "source.json"), "utf8")).record.revision, later);
    assert.equal(JSON.parse(readFileSync(path.join(folder, "readings.json"), "utf8")).record.revision, later);
    assert.equal(JSON.parse(readFileSync(path.join(folder, "cards.json"), "utf8")).built_from.record.revision, later);
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test("a count the record words otherwise stands where the registered protocol confirms it, with the record's words beside it", () => {
  const folder = fixtureCopy((root) => {
    // The fixture's MG0a-like run, with two parts of one numbered criterion, and its protocol listing all five.
    const results = path.join(root, "evidence", "fixture-mg0a", "judged-01", "results", "results.json");
    writeFileSync(results, readFileSync(results, "utf8").replace('"A4a"', '"A4_one"').replace('"A4b"', '"A4_two"'));
    writeFileSync(path.join(root, "evidence", "fixture-mg0a", "judged-01", "source", "protocol.json"), JSON.stringify({ criteria: ["A1", "A2", "A3", "A4_one", "A4_two"].map((id) => ({ id })) }));
    const file = path.join(root, "source.json");
    writeFileSync(file, readFileSync(file, "utf8").replace('"snapshot": { "file": ["source", "SNAPSHOT.json"], "field": "git_revision" }\n          }\n        },\n        {\n          "progress": { "entry": "A fixture qualification', '"snapshot": { "file": ["source", "SNAPSHOT.json"], "field": "git_revision" },\n            "confirm": { "file": ["source", "protocol.json"], "entries": "criteria" }\n          }\n        },\n        {\n          "progress": { "entry": "A fixture qualification'));
  });
  try {
    const run = gatherIn(folder);
    assert.equal(run.status, 0, run.stderr);
    const second = builtIn(folder).cards.find((card) => card.id === "fr1").record[1];
    assert.deepEqual([second.verdict.count.passed, second.verdict.count.of], [5, 5]);
    assert.deepEqual(second.verdict.count.confirmed_by.map((item) => item.file.join("/")), ["source/protocol.json"]);
    assert.deepEqual(second.verdict.count.differs_from.map((item) => item.says), ["All 4 criteria"]);
    assert.equal(second.verdict.count.note, "A4 is judged in 2 parts: A4_one and A4_two.");
    assert.ok(!("count_withheld" in second.verdict));
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test("the gathering refuses a path of a machine in words it would carry, a paragraph changed since its revision, and a folder named as a path", () => {
  const cases = [
    [(folder) => {
      const file = path.join(folder, "engine", source_main(), "PROGRESS.md");
      writeFileSync(file, readFileSync(file, "utf8").replace("on CPU only.", `on CPU only, in ${["", "mnt", "workspaces", "elsewhere", ""].join("/")}.`));
    }, /path of a machine/],
    [(folder) => {
      const file = path.join(folder, "engine", source_main(), "docs", "NOTE.md");
      writeFileSync(file, readFileSync(file, "utf8").replace("The second item.", "The second item, reworded."));
    }, /differs at/],
    [(folder) => {
      const file = path.join(folder, "source.json");
      writeFileSync(file, readFileSync(file, "utf8").replace('"within": ["judged", "run-a"]', '"within": ["judged/run-a"]'));
    }, /folder by folder/],
    // A comparison that says it passed while a table it counts states a failed row.
    [(folder) => {
      const file = path.join(folder, "evidence", "fixture-compared", "comparison.json");
      writeFileSync(file, readFileSync(file, "utf8").replace('"y": {"compared": 2, "failed": 0', '"y": {"compared": 2, "failed": 1'));
    }, /passes with 1 rows failed/],
  ];
  for (const [change, refusal] of cases) {
    const folder = fixtureCopy(change);
    try {
      const run = gatherIn(folder);
      assert.equal(run.status, 2, run.stdout);
      assert.match(run.stderr, refusal);
    } finally {
      rmSync(folder, { recursive: true, force: true });
    }
  }
});
