// The Experiments landing (schema/EXPERIMENT_CARDS.md), read for the page: its bands and cards in the order the
// cards' file gives them, what each card says on its face, what a press on it opens, and what its detail holds in the
// page's own panel. Nothing here needs a document or the 3D stage, so it is tested on its own.
//
// Every standing, count, date, scope line and source is the file's (data/replays/cards.json, published beside the page
// as cards.json and fetched when the landing first opens). Nothing here names a card, a band or a level: the landing
// draws whatever bands and cards the file gives, in its order, and a band, a level or a kind of card it has not seen
// still stands, plainly, by its own words. Where a card's words are too long for its face they are shortened at their
// end only, with "…", and the whole is one press away (the card's detail).

import { Catalogue } from "./catalogue.js";
import { partsOf } from "./tissue_line.js";
import { formatDate } from "../ui/dom.js";

export const CARDS_FORMAT = "cells.visualizer.experiment_cards@1";
export const CARDS_FILE = "cards.json"; // beside the page, as the export publishes it
export const CARD = "card:"; // the id of a card's detail in the page's panel, and in its address (`select=card:<id>`)
// How much of a standing's words, and of a scope line, a card's face shows before it says "…".
export const FACE = { standing: 170, scope: 120, asks: 200 };

const text = (value) => (typeof value === "string" && value.trim() ? value : null);

/** What is wrong with a file of cards as the landing reads it; an empty list where it can be drawn. */
export function cardsProblems(data) {
  if (data?.format !== CARDS_FORMAT) return [`it is ${data?.format ?? "no file of cards"}, not ${CARDS_FORMAT}`];
  if (!Array.isArray(data.cards) || !data.cards.length) return ["it holds no card"];
  return [];
}

/**
 * The landing's bands, in the file's order, each with its cards in the order the band lists them. A card that no band
 * lists stands in the band it names, after that band's own; a card that names a band the file does not hold stands in
 * one of that band's name, after the others. So every card of the file is on the page, once.
 */
export function landingOf(data) {
  const cards = (Array.isArray(data?.cards) ? data.cards : []).filter((card) => card && typeof card.id === "string" && card.id);
  const byId = new Map(cards.map((card) => [card.id, card]));
  const placed = new Set();
  const bands = [];
  for (const band of Array.isArray(data?.bands) ? data.bands : []) {
    if (!band || typeof band.id !== "string") continue;
    const own = (Array.isArray(band.cards) ? band.cards : []).map((id) => byId.get(id)).filter((card) => card && !placed.has(card.id));
    for (const card of own) placed.add(card.id);
    bands.push({ id: band.id, label: text(band.label) || band.id, says: text(band.says), status: text(band.status), cards: own });
  }
  for (const card of cards) {
    if (placed.has(card.id)) continue;
    const named = String(card.band ?? "");
    let band = bands.find((item) => item.id === named);
    if (!band) bands.push((band = { id: named, label: named || "Other", says: null, status: null, cards: [] }));
    band.cards.push(card);
    placed.add(card.id);
  }
  const notRun = text(data?.not_run?.says) ? { says: data.not_run.says, lens: text(data.not_run.lens) } : null;
  return { bands: bands.filter((band) => band.cards.length), notRun, cards: cards.length };
}

/**
 * Words shortened at their end only: the first sentences that fit in `most` characters, else the words that do, with
 * "…" after them. `cut` says whether anything was left out; what is shown, less its "…", is the start of the whole.
 */
export function shorten(words, most) {
  const whole = text(words) ? words.trim() : "";
  if (whole.length <= most) return { text: whole, cut: false };
  const head = whole.slice(0, most);
  // The end of a sentence, not of an initial ("M. Levin") or a short form ("e.g."): its stop follows a word of two letters or more.
  let sentence = -1;
  for (const found of head.matchAll(/[.?!;:](?= )/g)) if (/[\p{Ll}\p{N})\]"”'’]{2}[.?!;:]$|[\p{Ll}\p{N})\]"”'’][.?!;:]$/u.test(head.slice(Math.max(0, found.index - 2), found.index + 1)) && !/(^|[\s(])\p{Lu}[.]$/u.test(head.slice(Math.max(0, found.index - 2), found.index + 1))) sentence = found.index;
  const space = head.lastIndexOf(" ");
  const end = sentence >= most * 0.5 ? sentence + 1 : space > 0 ? space : most;
  const kept = whole.slice(0, end).replace(/[\s,;:]+$/, "");
  // After a whole sentence the "…" stands apart from its stop.
  return { text: /[.?!]$/.test(kept) ? `${kept} …` : `${kept}…`, cut: true };
}

/** A verdict's count in its own unit ("44 of 44 judged criteria"), or null where the file gives none. */
export function countWords(count) {
  if (!count || !Number.isInteger(count.passed) || !Number.isInteger(count.of)) return null;
  const open = Number.isInteger(count.not_evaluable) && count.not_evaluable > 0 ? `, ${count.not_evaluable} not evaluable` : "";
  return `${count.passed} of ${count.of}${text(count.unit) ? ` ${count.unit}` : ""}${open}`;
}

/** The verdicts a card's record holds, in its order: whether each passed, its count, its day and its scope line. */
export function verdictsOf(card, { scope = Infinity } = {}) {
  return (Array.isArray(card?.record) ? card.record : [])
    .filter((entry) => entry && typeof entry.verdict === "object" && entry.verdict)
    .map((entry) => ({
      says: text(entry.says),
      passed: typeof entry.verdict.passed === "boolean" ? entry.verdict.passed : null,
      count: countWords(entry.verdict.count),
      day: text(entry.verdict.day?.date),
      scope: text(entry.scope?.says) ? shorten(entry.scope.says, scope) : null,
    }));
}

/** A card's level: the label and words the file gives it, and its status (the Engine map's) where it names one; null where it has none. */
export function levelOf(card) {
  const level = card?.standing?.level;
  return level && text(level.label) ? { label: level.label, says: text(level.says), status: text(card.standing.status) } : null;
}

/**
 * The standing's words for a card: the words it shows first (`first`, the D138 words of the gap-junction work), and the
 * rest of its words (its `says`, or the reason it has none), less those first words where they begin with them. `face` is
 * what a card's face shows of the rest: where the rest goes on with the card's own question (a map part that asks it
 * too), the face asks it once, above, and its standing starts after it; the detail keeps the rest whole.
 */
export function standingWords(card) {
  const standing = card?.standing || {};
  const first = text(standing.first);
  const said = text(standing.says) || text(standing.none) || "";
  const rest = first && said.startsWith(first) ? said.slice(first.length).trim() : first === said ? "" : said;
  const asked = text(card?.asks) ? card.asks.trim() : null;
  return { first, rest, whole: said, face: asked && rest.startsWith(asked) ? rest.slice(asked.length).trim() : rest };
}

/** The answer a card's record gives (an experiment that found yes, no or mixed), in its words; null where it has none. */
export function answerOf(card) {
  const answer = card?.answer;
  if (!answer || !text(answer.label)) return null;
  return { label: answer.label, mark: ["yes", "no", "mixed"].includes(answer.answer) ? answer.answer : "none", text: text(answer.text) };
}

/**
 * What a press on a replay's card opens, as the Experiments tab opens it (by rule, never by the card's id): a model
 * system's entry its own view (`example`); an experiment whose entry names a part to open (`opens.part`) that part; any
 * other experiment its opening run. Null where the page carries nothing of it (the card then does not play here).
 */
export function opensOf(card, replays) {
  const opens = card?.replay?.opens;
  if (!opens || typeof opens !== "object") return null;
  if (typeof opens.entry === "string") return (replays?.doors || []).some((door) => door?.entry === opens.entry) ? { example: opens.entry } : null;
  if (typeof opens.experiment !== "string") return null;
  const part = partOpenedBy(replays, opens.experiment);
  if (part) return { part };
  const catalogue = new Catalogue(replays);
  const run = catalogue.runs.some((item) => item.experiment === opens.experiment) ? catalogue.openingRun(opens.experiment) : null;
  return run ? { run } : null;
}

/** The part an experiment's entry opens on (`opens.part`), where it is a part of it the catalogue carries with runs; else null. */
export function partOpenedBy(replays, experimentId) {
  const entry = (replays?.experiments || []).find((item) => item.id === experimentId);
  const part = entry?.opens?.part;
  return typeof part === "string" && partsOf(replays, experimentId).some((item) => item.id === part) ? part : null;
}

/** The page's address for what a card opens, or for its detail: the query each is reached by (`lens=experiments&…`). */
export function addressOf(opened) {
  if (!opened) return null;
  if (opened.example) return `lens=experiments&example=${encodeURIComponent(opened.example)}`;
  if (opened.part) return `lens=experiments&part=${encodeURIComponent(opened.part)}`;
  if (opened.run) return `lens=experiments&run=${encodeURIComponent(opened.run)}`;
  if (opened.detail) return `lens=experiments&select=${encodeURIComponent(CARD + opened.detail)}`;
  return null;
}

/** A card's still for a theme (`replay.still`: { light, dark, width, height }, paths beside the page); null where it has none. */
export function stillOf(card, dark = false) {
  const still = card?.replay?.still;
  if (!still || typeof still !== "object") return null;
  const file = text(dark ? still.dark : still.light) || text(dark ? still.light : still.dark);
  if (!file || !/^stills\/[a-z0-9][a-z0-9._-]*\.(jpg|jpeg|png|webp)$/.test(file)) return null;
  const width = Number.isInteger(still.width) && still.width > 0 ? still.width : null, height = Number.isInteger(still.height) && still.height > 0 ? still.height : null;
  return width && height ? { file, width, height } : null;
}

/**
 * What a card's face says, in its order: its title; what it asks (or shows); its standing (its first words, a level
 * where it has one, then its words, shortened); its answer; each verdict of its record (passed or not, its count, its
 * day, its scope line, shortened); how many runs it has and whether it plays here (`plays`, from opensOf).
 */
export function faceOf(card, { plays = null } = {}) {
  const words = standingWords(card);
  const asks = text(card?.asks) ? shorten(card.asks, FACE.asks) : null;
  const shows = !asks && text(card?.shows) ? shorten(card.shows, FACE.asks) : null;
  const standing = shorten(words.face, FACE.standing);
  const verdicts = verdictsOf(card, { scope: FACE.scope });
  const runs = Number.isInteger(card?.replay?.runs) ? card.replay.runs : null;
  const rows = Array.isArray(card?.rows) ? card.rows.length : null;
  const cut = Boolean(asks?.cut || shows?.cut || standing.cut || verdicts.some((verdict) => verdict.scope?.cut));
  return { id: card.id, kind: card.kind, title: text(card.title) || card.id, asks, shows, first: words.first, level: levelOf(card), standing, answer: answerOf(card), verdicts, runs, rows, plays: Boolean(plays), replay: card.kind === "replay" || Boolean(card.replay), cut };
}

/**
 * A card's detail as the page's panel shows it: the record's sentences, the scope lines whole, every count with its day,
 * the sources as links at their revisions (`sourceUrl`, the scene's), and a door to the card's part on the Engine map
 * (`door(part)`, the viewer's: null where the map has no such part). `band` is the card's band, for its eyebrow.
 */
export function detailOf(card, { band = null, sourceUrl = () => null, door = () => null, plays = null, statuses = null, titleOf = (id) => id } = {}) {
  const words = standingWords(card);
  const standing = card.standing || {};
  const level = levelOf(card);
  const link = (source) => {
    const url = source ? sourceUrl(source) : null;
    return url ? { url, text: [source.path, source.where].filter(Boolean).join(" · ") } : null;
  };
  const chips = [];
  if (level) chips.push({ label: level.label, title: level.says || "", swatch: level.status && (!statuses || statuses.has(level.status)) ? level.status : null });
  if (text(standing.as_of)) chips.push({ label: `As of ${formatDate(standing.as_of)}`, title: "The date of this standing, as the record gives it." });
  const facts = [];
  const sections = [];
  // The standing in the record's words, whole: its level's own words under it, where it has a level.
  const said = words.first ? words.rest : words.whole;
  if (said || level) sections.push({ title: "Its standing", count: false, items: [{ label: level ? level.label : "", lines: [said, level?.says ? `${level.label}: ${level.says}` : null].filter(Boolean), note: text(standing.level_withheld) }] });
  if (text(standing.none) && text(standing.says)) facts.push(["Why no level", standing.none]);
  if (Array.isArray(standing.tests) && standing.tests.length) facts.push(["Tests it rests on", standing.tests.join("; ")]);
  if (card.replay) facts.push(["Runs", `${card.replay.runs ?? "none"}${plays ? ", played here" : ", not played here"}`]);
  const answer = answerOf(card);
  if (answer) sections.push({ title: "Its answer", items: [{ label: answer.label, lines: answer.text ? [answer.text] : [], links: (card.answer.sources || []).map(link).filter(Boolean) }] });
  const record = (Array.isArray(card.record) ? card.record : []).filter(Boolean);
  if (record.length) {
    sections.push({
      title: "The record",
      items: record.map((entry) => {
        const verdict = entry.verdict || null;
        const count = countWords(verdict?.count);
        const day = text(verdict?.day?.date);
        const lines = [];
        if (text(entry.item)) lines.push(entry.item);
        if (text(entry.scope?.says)) lines.push(entry.scope.says);
        if (text(verdict?.protocol)) lines.push(`Protocol ${verdict.protocol}`);
        if (verdict?.snapshot?.revision) lines.push(`Run from revision ${verdict.snapshot.revision}`);
        else if (text(verdict?.snapshot?.says)) lines.push(verdict.snapshot.says);
        if (text(verdict?.count_withheld)) lines.push(verdict.count_withheld);
        if (text(verdict?.count?.note)) lines.push(verdict.count.note);
        for (const other of verdict?.count?.differs_from || []) if (text(other?.says)) lines.push(`${[other.path, other.where].filter(Boolean).join(", ")}${other.revision ? ` at ${other.revision.slice(0, 8)}` : ""} words it otherwise: “${other.says}”`);
        // One run behind several cards: each says so, with the run's folder.
        const also = (verdict?.also_on || []).map((id) => titleOf(id)).filter(Boolean);
        if (also.length) lines.push(`The same run${verdict.run?.evidence ? ` (${verdict.run.evidence})` : ""} stands behind ${also.join(", ")} too`);
        if (verdict?.count?.from) lines.push(`Counted from ${fileOf(verdict.count.from)}: ${verdict.count.from.field || ""}`.trim());
        return {
          label: text(entry.says) || "",
          tag: typeof verdict?.passed === "boolean" ? (verdict.passed ? "Passed" : "Failed") : null,
          tag_title: typeof verdict?.passed === "boolean" ? "The verdict of the run's own file." : "",
          detail: [count, day ? formatDate(day) : null].filter(Boolean).join(" · ") || null,
          lines,
          links: [link(entry.source), link(entry.scope?.source)].filter(Boolean),
        };
      }),
    });
  }
  if (Array.isArray(card.rows) && card.rows.length) {
    sections.push({
      title: "Its rows",
      items: card.rows.map((row) => ({
        label: [row.id, row.claim].filter(Boolean).join(": "),
        tag: typeof row.passed === "boolean" ? (row.passed ? "Passed" : "Failed") : null,
        tag_title: "The row's result in the run of record.",
        detail: row.reference ? `Reference: ${[row.reference.path, row.reference.where].filter(Boolean).join(" · ")}` : null,
        links: [link(row.reference), ...(row.modules || []).map(link)].filter(Boolean),
      })),
    });
  }
  if (card.cite && text(card.cite.says)) sections.push({ title: "Cited", items: [{ label: card.cite.says }] });
  if (card.switch && Array.isArray(card.switch.items) && card.switch.items.length) sections.push({ title: card.switch.heading || "", items: card.switch.items.map((item) => ({ label: item })), note: null });
  // A replay made again later, at a named revision of main, says so in its own words (schema: `rerun`); none today.
  if (card.rerun && typeof card.rerun === "object" && text(card.rerun.says)) sections.push({ title: "Run again", items: [{ label: card.rerun.says, detail: text(card.rerun.revision) ? `At ${card.rerun.revision}` : null }] });
  const doors = [];
  // A replay's card: its view, from its detail as from the card.
  if (plays) doors.push({ label: "Open its replay", card: card.id });
  const toMap = text(standing.part) ? door(standing.part) : null;
  if (toMap) doors.push(toMap);
  const seen = new Set();
  const sources = [...(standing.sources || []), ...(card.answer?.sources || []), ...record.flatMap((entry) => [entry.source, entry.scope?.source])].filter((source) => {
    if (!source?.path) return false;
    const key = `${source.path}|${source.where || ""}|${source.revision || ""}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  return {
    id: CARD + card.id,
    label: text(card.title) || card.id,
    eyebrow: band?.label || "",
    kind: "card",
    plain: text(card.asks) || text(card.shows) || "",
    note: words.first,
    chips,
    facts,
    sections,
    doors,
    sources,
    keywords: [card.id, standing.part].filter(Boolean).join(" "),
  };
}

/** A verdict's file as the cards name it: its run folder, then its folders and file, by name, never as a path of a machine. */
function fileOf(from) {
  return [from.evidence, ...(from.within || []), ...(Array.isArray(from.file) ? from.file : [from.file])].filter(Boolean).join(" / ");
}
