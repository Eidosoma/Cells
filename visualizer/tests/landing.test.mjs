// The Experiments landing, as far as it can be held without a browser (src/replay/landing.js): the bands and cards in the
// order the cards' file gives, every card on the page once, a band, a level or a kind it has not seen drawn plainly, the
// first words first, words shortened only at their end, verdicts shown each as they are (never summed), what a press
// opens (by rule, never by a card's id), the addresses, the detail with its sources at their revisions and its door to
// the Engine map, and that the page's code types no standing, count, card or band of its own. The stills the cards name
// are files of their record, of the size and checksum it states. The rules are held on the real file and on made-up ones,
// so that tomorrow's cards are held by them too (18 November 2026).
//
//   node --test tests/landing.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { CARD, CARDS_FORMAT, FACE, addressOf, cardsProblems, countWords, detailOf, faceOf, landingOf, opensOf, shorten, standingWords, stillOf, verdictsOf } from "../src/replay/landing.js";
import { landingFiles, publishedReplays } from "../tools/lib/build_page.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const readJson = (file) => JSON.parse(readFileSync(path.join(ROOT, file), "utf8"));
const cards = readJson("data/replays/cards.json");
const overlay = readJson("data/replays/overlay.json");
const scene = readJson("data/architecture/architecture.scene.json");

/** A catalogue as the adapter writes it from the overlay, one run an experiment (its opening arm where it names one). */
const catalogueOf = (experiments = overlay.experiments, doors = overlay.doors) => ({
  format: "cells.visualizer.replay_index@1",
  experiments: Object.entries(experiments).map(([id, entry]) => ({ id, ...entry })),
  runs: Object.entries(experiments).map(([id, entry]) => ({ id: `${id}--${entry.opens?.run || "a"}`, experiment: id, arm: entry.opens?.run || "a" })),
  doors,
});

test("every card of the file stands on the page once, in its band, in the order the file gives", () => {
  assert.deepEqual(cardsProblems(cards), []);
  const landing = landingOf(cards);
  assert.deepEqual(landing.bands.map((band) => band.id), cards.bands.map((band) => band.id).filter((id) => cards.cards.some((card) => card.band === id)));
  const shown = landing.bands.flatMap((band) => band.cards.map((card) => card.id));
  assert.deepEqual([...shown].sort(), cards.cards.map((card) => card.id).sort(), "every card, once");
  assert.equal(new Set(shown).size, shown.length);
  for (const band of landing.bands) {
    const given = cards.bands.find((item) => item.id === band.id);
    assert.deepEqual(band.cards.map((card) => card.id), given.cards, `${band.id}: in the band's own order`);
    assert.equal(band.label, given.label);
  }
  assert.deepEqual(landing.notRun, { says: cards.not_run.says, lens: cards.not_run.lens });
});

test("a band, a level or a kind the landing has not seen still stands, by its own words", () => {
  const made = {
    format: CARDS_FORMAT,
    bands: [{ id: "first", label: "A first band", cards: ["b", "a"] }, { id: "empty", label: "Nothing in it", cards: [] }],
    cards: [
      { id: "a", band: "first", kind: "standing", title: "A", asks: "Does a?", standing: { says: "A's words." }, record: [] },
      { id: "b", band: "first", kind: "something-new", title: "B", asks: "Does b?", standing: { status: "a-level-never-seen", level: { label: "A level never seen", says: "Its words." }, says: "B's words." }, record: [] },
      { id: "c", band: "first", kind: "standing", title: "C, listed by no band", asks: "Does c?", standing: { says: "C's words." }, record: [] },
      { id: "d", band: "a-band-never-seen", kind: "standing", title: "D", asks: "Does d?", standing: { says: "D's words." }, record: [] },
    ],
  };
  const landing = landingOf(made);
  assert.deepEqual(landing.bands.map((band) => [band.id, band.cards.map((card) => card.id)]), [["first", ["b", "a", "c"]], ["a-band-never-seen", ["d"]]], "a band of none is left out; a card listed by no band stands in its own; an unknown band stands after the others");
  assert.equal(landing.bands[1].label, "a-band-never-seen");
  const face = faceOf(made.cards[1]);
  assert.deepEqual(face.level, { label: "A level never seen", says: "Its words.", status: "a-level-never-seen" });
  const detail = detailOf(made.cards[1], { statuses: new Set(scene.statuses.map((status) => status.id)) });
  assert.deepEqual(detail.chips[0], { label: "A level never seen", title: "Its words.", swatch: null }, "a level the map does not draw has its words and no swatch");
  assert.deepEqual(cardsProblems({ format: "another@1", cards: [] }), ["it is another@1, not cells.visualizer.experiment_cards@1"]);
});

test("a card's first words come first, and its standing's words follow them without saying them twice", () => {
  const firsts = cards.cards.filter((card) => card.standing?.first);
  assert.ok(firsts.length >= 1, "the gap-junction work's card has its first words");
  for (const card of cards.cards) {
    const face = faceOf(card), words = standingWords(card);
    assert.equal(face.first, card.standing.first || null, card.id);
    if (card.standing.first) {
      assert.ok(!face.standing.text.startsWith(card.standing.first), `${card.id}: the first words are not said again`);
      assert.equal(detailOf(card).note, card.standing.first, `${card.id}: the detail's first note is the first words`);
    }
    // A level only where the card has one.
    assert.equal(Boolean(face.level), Boolean(card.standing.level?.label), card.id);
    assert.ok(words.whole === (card.standing.says || card.standing.none || ""), card.id);
    // The card's own question is asked once on its face, though its standing's words go on with it; the detail keeps them whole.
    if (card.asks) assert.ok(!face.standing.text.startsWith(card.asks.trim()), `${card.id}: its question is not asked twice`);
  }
  // On a made-up card too: the standing's words lose the question they open with, and nothing else.
  const made = { id: "x", kind: "standing", asks: "Does it hold?", standing: { first: "A probe.", says: "A probe. Does it hold? It held for an hour.", level: null } };
  assert.equal(faceOf(made).standing.text, "It held for an hour.");
  assert.equal(faceOf({ ...made, asks: "Does it last?" }).standing.text, "Does it hold? It held for an hour.");
  assert.ok(detailOf(made).sections.find((section) => section.title === "Its standing").items[0].lines[0].startsWith("Does it hold?"));
});

test("words too long for a card's face are shortened at their end only, with \"…\", and the detail holds them whole", () => {
  // An initial ("M. Levin") is no end of a sentence.
  assert.equal(shorten("Made by J. Grodstein, J. Mathews and M. Levin in the year of the preprint", 52).text, "Made by J. Grodstein, J. Mathews and M. Levin in…");
  for (const [words, most] of [["One. Two three four five six seven eight nine ten.", 20], ["no stop in these words at all here", 12], ["short", 50]]) {
    const cut = shorten(words, most);
    assert.ok(cut.text.length <= most + 2, cut.text);
    if (cut.cut) assert.ok(cut.text.endsWith("…") && words.startsWith(cut.text.replace(/ ?…$/, "")), cut.text);
    else assert.equal(cut.text, words);
  }
  for (const card of cards.cards) {
    const face = faceOf(card), words = standingWords(card);
    // What the face shows is the start of the standing's words, after the card's own question where they open with it.
    assert.ok(words.rest.endsWith(words.face), card.id);
    if (face.standing.cut) assert.ok(words.face.startsWith(face.standing.text.replace(/ ?…$/, "")), card.id);
    else assert.equal(face.standing.text, words.face.trim(), card.id);
    const detail = detailOf(card);
    if (words.rest) assert.ok(detail.sections.find((section) => section.title === "Its standing").items[0].lines.includes(words.first ? words.rest : words.whole), `${card.id}: the whole standing in the detail`);
    for (const [k, verdict] of verdictsOf(card, { scope: FACE.scope }).entries()) {
      const whole = card.record.filter((entry) => entry?.verdict)[k].scope?.says;
      if (verdict.scope) assert.ok(whole.startsWith(verdict.scope.text.replace(/ ?…$/, "")), card.id);
      if (whole) assert.ok(detail.sections.find((section) => section.title === "The record").items.some((item) => item.lines.includes(whole)), `${card.id}: the scope line whole in the detail`);
    }
  }
});

test("each verdict stands as the record has it: passed or failed, its own count and day, never summed and never one picked", () => {
  for (const card of cards.cards) {
    const entries = (card.record || []).filter((entry) => entry?.verdict);
    const verdicts = verdictsOf(card);
    assert.equal(verdicts.length, entries.length, card.id);
    entries.forEach((entry, k) => {
      assert.equal(verdicts[k].passed, typeof entry.verdict.passed === "boolean" ? entry.verdict.passed : null, card.id);
      assert.equal(verdicts[k].day, entry.verdict.day?.date || null, card.id);
      assert.equal(verdicts[k].count, entry.verdict.count ? `${entry.verdict.count.passed} of ${entry.verdict.count.of}${entry.verdict.count.unit ? ` ${entry.verdict.count.unit}` : ""}${entry.verdict.count.not_evaluable ? `, ${entry.verdict.count.not_evaluable} not evaluable` : ""}` : null, card.id);
    });
  }
  // A failed verdict stands beside the passes (the file holds some), each by its own word, not by a colour.
  assert.ok(cards.cards.some((card) => verdictsOf(card).some((verdict) => verdict.passed === false)));
  assert.equal(countWords(null), null, "a count the file withholds shows no number");
  const many = { id: "x", record: [{ verdict: { passed: true, count: { passed: 3, of: 3, unit: "runs" } } }, { verdict: { passed: false, count: { passed: 0, of: 3, unit: "runs" } } }] };
  assert.deepEqual(verdictsOf(many).map((verdict) => [verdict.passed, verdict.count]), [[true, "3 of 3 runs"], [false, "0 of 3 runs"]]);
  const detail = detailOf({ id: "x", title: "X", standing: {}, record: many.record.map((entry, k) => ({ ...entry, says: `Run ${k}` })) });
  assert.deepEqual(detail.sections.find((section) => section.title === "The record").items.map((item) => [item.tag, item.detail]), [["Passed", "3 of 3 runs"], ["Failed", "0 of 3 runs"]]);
});

test("a press on a replay's card opens, by rule, what the tab opens: a model system's view, an experiment's part, or its opening run", () => {
  const replays = catalogueOf();
  for (const card of cards.cards.filter((item) => item.kind === "replay")) {
    const opened = opensOf(card, replays), opens = card.replay.opens;
    if (opens.entry) assert.deepEqual(opened, { example: opens.entry }, card.id);
    else {
      const part = overlay.experiments[opens.experiment]?.opens?.part;
      assert.deepEqual(opened, part ? { part } : { run: `${opens.experiment}--${overlay.experiments[opens.experiment]?.opens?.run || "a"}` }, card.id);
    }
  }
  // What the page does not carry does not play: no door, no run, no part.
  assert.equal(opensOf({ replay: { opens: { entry: "no-such-entry" } } }, replays), null);
  assert.equal(opensOf({ replay: { opens: { experiment: "no-such-experiment" } } }, replays), null);
  assert.equal(opensOf({ kind: "standing" }, replays), null);
  // A part named that the catalogue does not carry: the experiment's opening run, as the tab always did.
  const named = catalogueOf({ whole: { opens: { run: "w", part: "not-carried" } } }, []);
  assert.deepEqual(opensOf({ replay: { opens: { experiment: "whole" } } }, named), { run: "whole--w" });
});

test("the addresses: a view opened from a card is the page's own address of it, and a card's detail is select=card:<id>", () => {
  assert.equal(addressOf({ example: "gard" }), "lens=experiments&example=gard");
  assert.equal(addressOf({ part: "a-part" }), "lens=experiments&part=a-part");
  assert.equal(addressOf({ run: "x--y" }), "lens=experiments&run=x--y");
  assert.equal(addressOf({ detail: "fr1" }), `lens=experiments&select=${encodeURIComponent(CARD)}fr1`);
  assert.equal(new URLSearchParams(addressOf({ detail: "some-card" })).get("select"), "card:some-card");
  assert.equal(addressOf(null), null);
});

test("a card's detail: the record's sentences, every count with its day, the sources at their revisions, a door to the Engine map", () => {
  const sourceUrl = (source) => (source.revision ? `https://example.invalid/${source.revision}/${source.path}` : null);
  const door = (part) => (scene.entities.some((entity) => entity.id === part) ? { lens: "engine", select: part, label: "Its part on the Engine map" } : null);
  for (const card of cards.cards) {
    const detail = detailOf(card, { sourceUrl, door, titleOf: (id) => cards.cards.find((item) => item.id === id)?.title || null });
    assert.equal(detail.id, CARD + card.id);
    assert.equal(detail.label, card.title);
    for (const source of detail.sources) assert.ok(source.path, card.id);
    const record = (card.record || []).filter(Boolean);
    if (record.length) {
      const items = detail.sections.find((section) => section.title === "The record").items;
      assert.equal(items.length, record.length, `${card.id}: every entry of its record`);
      record.forEach((entry, k) => {
        assert.equal(items[k].label, entry.says || "", card.id);
        if (entry.verdict?.count) assert.ok(items[k].detail.startsWith(`${entry.verdict.count.passed} of ${entry.verdict.count.of}`), card.id);
        if (entry.verdict?.day?.date) assert.ok(items[k].detail, `${card.id}: its day`);
        for (const link of items[k].links) assert.match(link.url, /^https:\/\/example\.invalid\/[0-9a-f]{40}\//, card.id);
        for (const other of entry.verdict?.also_on || []) assert.ok(items[k].lines.some((line) => line.includes(cards.cards.find((item) => item.id === other).title)), `${card.id}: the run's other cards named`);
      });
    }
    if (card.standing.part && scene.entities.some((entity) => entity.id === card.standing.part)) assert.deepEqual(detail.doors, [{ lens: "engine", select: card.standing.part, label: "Its part on the Engine map" }], card.id);
    // Where it plays here, its view is a door of its detail too.
    assert.deepEqual(detailOf(card, { plays: { run: "x" } }).doors[0], { label: "Open its replay", card: card.id });
    if (card.kind === "rows") {
      const rows = detail.sections.find((section) => section.title === "Its rows").items;
      assert.equal(rows.length, card.rows.length);
      card.rows.forEach((row, k) => {
        assert.equal(rows[k].tag, row.passed ? "Passed" : "Failed");
        assert.ok(rows[k].links.some((link) => link.url.endsWith(row.reference.path)), `${row.id}: its reference, at its revision`);
      });
    }
    // Room for a rerun, which is null today: nothing of one is shown.
    if ("rerun" in card && card.rerun === null) assert.ok(!detail.sections.some((section) => section.title === "Run again"), card.id);
  }
  const rerun = detailOf({ id: "r", title: "R", standing: {}, record: [], rerun: { revision: "0".repeat(40), says: "A rerun at a named revision, not the judged run.", replay: null } });
  assert.deepEqual(rerun.sections.at(-1).items[0].label, "A rerun at a named revision, not the judged run.");
});

test("the page's code types no card, band, level, standing or count of the record: they are the file's", () => {
  const strip = (text) => text.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`])\/\/.*$/gm, "$1");
  const code = ["src/replay/landing.js", "src/ui/landing.js"].map((file) => strip(readFileSync(path.join(ROOT, file), "utf8"))).join("\n");
  const statuses = scene.statuses.flatMap((status) => [status.id, status.label]);
  for (const word of [...cards.cards.map((card) => card.id), ...cards.bands.flatMap((band) => [band.id, band.label]), ...statuses, ...cards.bands.flatMap((band) => (band.levels || []).map((level) => level.label))]) {
    if (word.length < 3) continue;
    assert.ok(!new RegExp(`["'\`]${word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}["'\`]`).test(code), `the code names ${JSON.stringify(word)}`);
  }
  assert.doesNotMatch(code, /\bjudged\b|\bqualified\b/i, "no word of a standing is typed");
  assert.doesNotMatch(code, /replicat|reproduc|\bagree|\bmatches\b/i);
  // The words it types (its strings; the code's keys, such as an address's `example=`, are not words a visitor reads).
  const literals = [...code.matchAll(/"([^"\n]*)"|`([^`]*)`/g)].map((match) => (match[1] ?? match[2]).replace(/\$\{[^}]*\}/g, "")).join(" | ");
  assert.doesNotMatch(literals, /\bexamples?\b(?![=_.])/i, "no word the code types calls anything an example");
});

test("no card that opens the gap-junction work says of it replicated, reproduces, agrees or matches, on its face or in its detail", () => {
  for (const card of cards.cards.filter((item) => item.standing?.part === "exp.gap_junction" || (item.replay?.experiments || []).some((id) => id.startsWith("gap-junction-")))) {
    const detail = detailOf(card);
    const words = JSON.stringify([faceOf(card), detail.label, detail.plain, detail.note, detail.facts, detail.sections]);
    assert.doesNotMatch(words, /replicated|reproduc|\bagree|\bmatches\b/i, card.id);
    assert.equal(faceOf(card).first, card.standing.first, `${card.id}: its first words`);
  }
});

test("the stills: each card's still for each theme is a file of the stills' record, of the size and checksum it states, beside the page", async () => {
  const recordFile = path.join(ROOT, "data", "replays", "stills", "stills.json");
  const named = cards.cards.filter((card) => card.replay?.still);
  if (!existsSync(recordFile)) {
    assert.equal(named.length, 0, "a card names a still and there is no record of the stills");
    return;
  }
  const record = JSON.parse(readFileSync(recordFile, "utf8"));
  assert.equal(record.format, "cells.visualizer.landing_stills@1");
  assert.ok(typeof record.renderer === "string" && record.renderer, "the record names its renderer");
  assert.match(record.page?.revision || "", /^[0-9a-f]{40}$/);
  assert.doesNotMatch(JSON.stringify(record), /\d{1,2}:\d{2}(:\d{2})?|\/mnt\/|\/home\//, "no clock time, no path of a machine");
  const byFile = new Map(record.stills.map((still) => [still.file, still]));
  for (const card of named) {
    for (const dark of [false, true]) {
      const still = stillOf(card, dark);
      assert.ok(still, `${card.id}: its still for ${dark ? "dark" : "light"}`);
      const kept = byFile.get(still.file);
      assert.ok(kept && kept.card === card.id && kept.theme === (dark ? "dark" : "light"), `${card.id}: ${still.file} is in the record`);
      const bytes = readFileSync(path.join(ROOT, "data", "replays", still.file));
      assert.equal(bytes.length, kept.bytes, still.file);
      assert.ok(bytes.length < 60000, `${still.file}: well under 60 KB`);
      assert.equal(createHash("sha256").update(bytes).digest("hex"), kept.sha256, still.file);
      assert.deepEqual([still.width, still.height], [kept.width, kept.height], still.file);
      assert.equal(bytes[0] === 0xff && bytes[1] === 0xd8, true, `${still.file}: a JPEG`);
    }
  }
  // Every card that plays here has a still, and every still recorded is named by a card.
  const replays = catalogueOf();
  for (const card of cards.cards.filter((item) => item.kind === "replay" && opensOf(item, replays))) assert.ok(card.replay.still, `${card.id}: a replay's card carries a still of its view`);
  for (const still of record.stills) assert.ok(named.some((card) => card.id === still.card), still.file);
  // The export publishes the cards and every still beside the page, and nothing else of the landing.
  const files = await landingFiles();
  assert.deepEqual(files.problems, []);
  assert.deepEqual(files.files.map((file) => file.path).sort(), ["cards.json", ...record.stills.map((still) => still.file)].sort());
});

test("the export publishes the experiments the landing lists, and the landing lists every experiment its replay cards open", () => {
  const index = catalogueOf();
  const published = publishedReplays(index, scene, cards.listing);
  const opened = new Set(cards.cards.flatMap((card) => card.replay?.experiments || []));
  for (const id of opened) assert.ok(published.experiments.some((item) => item.id === id), id);
  // An experiment of the overlay no card opens (the W1 pilot, held back) is not published, unless the scene names its run.
  for (const id of Object.keys(overlay.experiments).filter((id) => !opened.has(id) && !overlay.experiments[id].part_of)) assert.ok(!published.runs.some((run) => run.experiment === id) || JSON.stringify(scene).includes(`"${id}--`), id);
});
