// The Experiments landing, as far as it can be held without a browser (src/replay/landing.js): the bands and cards in the
// order the cards' file gives, every card on the page once, a band, a level or a kind it has not seen drawn plainly, the
// first words first, words shortened only at their end, verdicts shown each as they are (never summed), what a press
// opens (by rule, never by a card's id), the addresses, the detail with its sources at their revisions and its door to
// the Engine map, and that the page's code types no standing, count, card or band of its own. The stills the cards name
// are files of their record, of the size and checksum it states. The rules are held on the real file and on made-up ones,
// so that tomorrow's cards are held by them too (18 November 2026). The first band stands open and every later band folds
// behind a control in the file's words, by the bands' places and never by their ids; a card asked for opens its band; and
// which bands a visitor opened is kept in the browser's storage, read and written so that a refusal breaks nothing
// (19 November 2026).
//
//   node --test tests/landing.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { CARD, CARDS_FORMAT, FACE, KEPT, addressOf, bandHolding, cardsProblems, controlOf, countWords, detailOf, faceOf, landingOf, openFirst, opensOf, partNameOf, readKept, shorten, standingWords, stillOf, verdictsOf, writeKept } from "../src/replay/landing.js";
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

test("as the landing first opens, its first band stands open and every later band folds, by their places, never by their ids", () => {
  const landing = landingOf(cards);
  assert.deepEqual([...openFirst(landing)], [cards.bands[0].id], "the first band alone, as the landing first opens");
  assert.deepEqual(landing.bands[0].cards.map((card) => card.id), cards.bands[0].cards);
  // Bands the landing has not seen (other ids, other labels), in another order: the first of them stands open, the rest fold.
  const made = {
    format: CARDS_FORMAT,
    bands: [{ id: "nothing", label: "Nothing in it", cards: [] }, { id: "zeta", label: "Zeta", cards: ["z"] }, { id: "alpha", label: "Alpha", control: "the alpha cards", cards: ["a", "b"] }],
    cards: [{ id: "a", band: "alpha", kind: "standing", title: "A", standing: {} }, { id: "b", band: "alpha", kind: "standing", title: "B", standing: {} }, { id: "z", band: "zeta", kind: "standing", title: "Z", standing: {} }, { id: "n", band: "never-named", kind: "standing", title: "N", standing: {} }],
  };
  const other = landingOf(made);
  assert.deepEqual(other.bands.map((band) => band.id), ["zeta", "alpha", "never-named"], "a band of no card is not drawn, so it is not the first");
  assert.deepEqual([...openFirst(other)], ["zeta"]);
  const turned = landingOf({ ...cards, bands: [...cards.bands].reverse() });
  assert.deepEqual([...openFirst(turned)], [cards.bands.at(-1).id], "the first band by its place: the file's order turned, the other band opens");
  // What a visitor opened before stands open again; ids the file does not hold, the first band's own, and anything else are let go.
  assert.deepEqual([...openFirst(landing, [cards.bands[2].id, "no-such-band", cards.bands[0].id, 7, null])], [cards.bands[0].id, cards.bands[2].id]);
  assert.deepEqual([...openFirst(landing, "not a list")], [cards.bands[0].id]);
  assert.deepEqual([...openFirst(landingOf({ format: CARDS_FORMAT, cards: [] }))], [], "no band, nothing open");
});

test("a card asked for (by its address, from the List, by the way back) is in one band, which opens for it", () => {
  const landing = landingOf(cards);
  for (const band of cards.bands) for (const id of band.cards) assert.equal(bandHolding(landing, id)?.id, band.id, id);
  assert.equal(bandHolding(landing, "no-such-card"), null);
  assert.equal(bandHolding(landing, null), null);
  // A card that names a band the file does not hold stands in a band of that name, and opens it.
  const made = landingOf({ format: CARDS_FORMAT, bands: [{ id: "first", label: "First", cards: ["a"] }], cards: [{ id: "a", band: "first", title: "A", standing: {} }, { id: "b", band: "elsewhere", title: "B", standing: {} }] });
  assert.equal(bandHolding(made, "b").id, "elsewhere");
});

test("a folded band's control: the file's words, true of every card in the band, beside the band's count, or a plain one from its label", () => {
  const landing = landingOf(cards);
  for (const band of landing.bands.slice(1)) {
    const given = cards.bands.find((item) => item.id === band.id);
    assert.ok(given.control, `${band.id}: its control's words are in the file`);
    assert.deepEqual(controlOf(band), { words: given.control, says: `Show ${given.control}`, count: given.cards.length, open: false }, band.id);
    assert.deepEqual(controlOf(band, true), { words: given.control, says: `Hide ${given.control}`, count: given.cards.length, open: true }, band.id);
  }
  // The judged band's control does not say "qualifications" alone: its cards are qualifications and judged runs.
  assert.equal(controlOf(landing.bands.find((band) => band.id === "judged")).says, "Show qualifications and judged runs");
  // Without words of its own, a band's control says its label, after "Show", with a sentence's capital lowered and a name's kept.
  const plain = (label, id = "x") => controlOf(landingOf({ format: CARDS_FORMAT, bands: [{ id, label, cards: ["a"] }], cards: [{ id: "a", band: id, title: "A", standing: {} }] }).bands[0]);
  assert.equal(plain("Development runs").says, "Show development runs");
  assert.equal(plain("BETSE runs").says, "Show BETSE runs");
  assert.equal(plain("E07-v1 and its kin").says, "Show E07-v1 and its kin");
  assert.equal(plain("", "a-band-id").says, "Show a-band-id");
  assert.equal(plain("Development runs").count, 1);
});

test("which bands a visitor opened is kept in the browser's storage, and nothing breaks where storage is refused, empty or unreadable", () => {
  const store = () => {
    const kept = new Map();
    return { getItem: (key) => (kept.has(key) ? kept.get(key) : null), setItem: (key, value) => kept.set(key, String(value)), kept };
  };
  const one = store();
  assert.deepEqual(readKept(() => one), [], "empty: nothing kept");
  assert.equal(writeKept(new Set(["judged", "development"]), () => one), true);
  assert.deepEqual(readKept(() => one), ["judged", "development"]);
  assert.deepEqual(JSON.parse(one.kept.get(KEPT)), ["judged", "development"]);
  // Refused (the storage itself throws, as in a frame that allows none), or its calls throw, or it holds something else.
  const refused = () => {
    throw new Error("SecurityError: storage is refused here");
  };
  assert.deepEqual(readKept(refused), []);
  assert.equal(writeKept(new Set(["judged"]), refused), false);
  const throwing = () => ({ getItem: () => { throw new Error("no"); }, setItem: () => { throw new Error("full"); } });
  assert.deepEqual(readKept(throwing), []);
  assert.equal(writeKept(new Set(["judged"]), throwing), false);
  assert.deepEqual(readKept(() => null), []);
  for (const raw of ["not json", "{\"judged\": true}", "42", "null", "[1, \"judged\", null, \"\"]"]) {
    const odd = store();
    odd.setItem(KEPT, raw);
    assert.deepEqual(readKept(() => odd), raw.startsWith("[") ? ["judged"] : [], raw);
  }
  // Nothing kept: the first band alone stands open.
  assert.deepEqual([...openFirst(landingOf(cards), readKept(refused))], [cards.bands[0].id]);
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
  // A card that opens a part of its experiment says which, in the part's own name (its still pictures that part); a card
  // that opens a run or a model system's view names none. The gap-junction example opens its sheet since 19 November 2026,
  // and the sheet's own name says that it is Cells' extension.
  for (const card of cards.cards.filter((item) => item.kind === "replay")) {
    const opened = opensOf(card, replays), name = partNameOf(opened, replays);
    if (opened?.part) assert.equal(name, overlay.experiments[opened.part].short || overlay.experiments[opened.part].label, card.id);
    else assert.equal(name, null, card.id);
  }
  assert.match(partNameOf(opensOf(cards.cards.find((item) => item.id === "tumour-tissue"), replays), replays), /Cells' extension/);
  assert.equal(partNameOf({ part: "no-such-part" }, replays), null);
  assert.equal(partNameOf({ part: "p" }, { experiments: [{ id: "p", label: "A made-up part" }] }), "A made-up part");
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
  for (const word of [...cards.cards.map((card) => card.id), ...cards.bands.flatMap((band) => [band.id, band.label, band.control].filter(Boolean)), ...statuses, ...cards.bands.flatMap((band) => (band.levels || []).map((level) => level.label))]) {
    if (word.length < 3) continue;
    assert.ok(!new RegExp(`["'\`]${word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}["'\`]`).test(code), `the code names ${JSON.stringify(word)}`);
  }
  assert.doesNotMatch(code, /\bjudged\b|\bqualified\b|\bqualifications?\b/i, "no word of a standing is typed");
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
