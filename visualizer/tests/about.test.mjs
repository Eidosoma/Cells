// About and the first-visit line (src/ui/about.js; data/site/about.json): the words are whole and each names where it was
// taken from, and say nobody's name; the page carries them in its scene; `#about` is the panel's name and no view's; the
// line's closing is kept where the browser keeps it and breaks nothing where it does not; the line stands where it covers
// nothing the page has put over the picture, or waits; the licence links at the map's revision. No browser: under a second.
//
//   node --test tests/about.test.mjs

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { ABOUT, ABOUT_FORMAT, INTRO_KEY, NEW_TAB, aboutAsked, aboutOf, introClosed, keepIntroClosed, licenceUrl, pageFacts, placeIntro } from "../src/ui/about.js";
import { formatDate } from "../src/ui/dom.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const WORDS = JSON.parse(readFileSync(path.join(ROOT, "data", "site", "about.json"), "utf8"));
const VIEWER = readFileSync(path.join(ROOT, "src", "ui", "viewer.js"), "utf8");
const VIEW_IDS = [...VIEWER.slice(VIEWER.indexOf("const LENSES = ["), VIEWER.indexOf("];", VIEWER.indexOf("const LENSES = ["))).matchAll(/\{ id: "([a-z]+)"/g)].map((match) => match[1]);

test("the words: whole, each with the place it was taken from, every view's, the source and its licence, and nobody named", () => {
  assert.equal(WORDS.format, ABOUT_FORMAT);
  const said = [WORDS.title, WORDS.description, WORDS.line, ...WORDS.lead, ...WORDS.reading, ...WORDS.views];
  for (const item of said) assert.ok(item.text?.trim() && item.from?.trim(), `${item.text?.slice(0, 40)}: its words and where they were taken from`);
  assert.deepEqual(WORDS.views.map((view) => view.id), VIEW_IDS, "one line for each view, in the switch's order");
  assert.equal(WORDS.source.url, "https://github.com/Eidosoma/Cells");
  // The repository's LICENSE (the folder above this one) is the licence the words name.
  const licence = readFileSync(path.join(ROOT, "..", WORDS.source.licence.path), "utf8").split("\n")[0];
  assert.equal(licence, `${WORDS.source.licence.name} License`);
  // Nobody is named until the owner says who is (20 November 2026): no credit, no contact, no further links, no address.
  assert.deepEqual([WORDS.credit, WORDS.contact, WORDS.links], [null, null, []]);
  const all = said.map((item) => item.text).join(" ");
  assert.ok(!/@|mailto:|doi|preprint|bioRxiv|Bjarnason|Eidosoma\b(?!\/)/i.test(all.replace("github.com/Eidosoma", "")), "no person, organisation, address or preprint in the words");
  assert.ok(!/\b(first|best|only|unique|revolutionary|will|soon)\b/i.test(all), "no superlative and no promise");
  const read = aboutOf({ about: WORDS });
  assert.equal(read.line, WORDS.line.text);
  assert.equal(read.views.length, VIEW_IDS.length);
  // A credit, a contact and further links are added in the data file alone, and read where they are given.
  const more = aboutOf({ about: { ...WORDS, credit: { text: "A line of credit." }, contact: { label: "Write", url: "mailto:someone@example.org" }, links: [{ label: "More", url: "https://example.org/" }, { label: "Not a link", url: "javascript:void 0" }] } });
  assert.deepEqual([more.credit, more.contact, more.links], ["A line of credit.", { label: "Write", url: "mailto:someone@example.org" }, [{ label: "More", url: "https://example.org/" }]]);
  for (const broken of [null, {}, { ...WORDS, format: "cells.visualizer.about@2" }, { ...WORDS, source: { url: "http://example.org" } }]) assert.equal(aboutOf({ about: broken }), null);
});

test("the address: #about opens the panel and is no view's name; a tab press writes #<view>, and About writes nothing", () => {
  assert.ok(!VIEW_IDS.includes(ABOUT), "no view is named about");
  for (const [hash, asked] of [["#about", true], ["about", true], ["#About", false], ["#cell", false], ["", false], [null, false]]) assert.equal(aboutAsked(hash), asked, String(hash));
  assert.ok(!/location\.hash\s*=|url\.hash\s*=\s*ABOUT|replaceState[^;]*about/i.test(readFileSync(path.join(ROOT, "src", "ui", "about.js"), "utf8")), "About is read from the address, never written to it");
  assert.deepEqual({ ...NEW_TAB }, { target: "_blank", rel: "noopener noreferrer" });
});

test("the line's closing is kept where the browser keeps it, and nothing breaks where it refuses", () => {
  const store = new Map();
  const storage = { getItem: (key) => (store.has(key) ? store.get(key) : null), setItem: (key, value) => store.set(key, String(value)) };
  assert.equal(introClosed(() => storage), false, "a first visit");
  assert.equal(keepIntroClosed(() => storage), true);
  assert.equal(store.get(INTRO_KEY), "closed");
  assert.equal(introClosed(() => storage), true, "closed, it stays closed in this browser");
  const refusing = () => {
    throw new DOMException("refused", "SecurityError");
  };
  assert.equal(introClosed(refusing), false, "no storage: the line shows again");
  assert.equal(keepIntroClosed(refusing), false, "and closing it breaks nothing");
  assert.equal(introClosed(() => null), false);
  assert.equal(keepIntroClosed(() => ({ setItem: refusing })), false, "a full or refused store");
});

test("the line stands in the first band under the bar that covers nothing the page put over the picture, near the middle, or waits", () => {
  const size = { width: 520, height: 38 };
  // A wide window: the view's card at the left, nothing in the middle: under the bar, in the middle.
  assert.deepEqual(placeIntro({ width: 1440, height: 900, top: 64, taken: [{ left: 16, top: 64, right: 252, bottom: 184 }], size }), { left: 460, top: 64 });
  // The Protein atlas's trail across the top: under it.
  const trail = { left: 324, top: 64, right: 1244, bottom: 107 };
  assert.deepEqual(placeIntro({ width: 1280, height: 720, top: 64, taken: [{ left: 16, top: 64, right: 284, bottom: 380 }, trail], size }), { left: 380, top: 116 });
  // A card on the right near the middle: the line keeps its gap from both.
  const spot = placeIntro({ width: 1280, height: 720, top: 64, taken: [{ left: 16, top: 64, right: 284, bottom: 380 }, { left: 900, top: 60, right: 1264, bottom: 200 }], size });
  assert.ok(spot.left >= 284 + 8 && spot.left + size.width <= 900 - 8 && spot.top === 64, JSON.stringify(spot));
  // Where the band between them is too narrow, it goes down until one is wide enough.
  const lower = placeIntro({ width: 1280, height: 720, top: 64, taken: [{ left: 16, top: 64, right: 284, bottom: 380 }, { left: 700, top: 60, right: 1264, bottom: 200 }], size });
  assert.deepEqual(lower, { left: 380, top: 208 });
  // The rule alone, at a phone's size: the card and the rail's button under the bar leave no band wide enough, so the first
  // free band is under the card. (The page does not place the line on a phone: it waits there, src/ui/about.js, place.)
  const phone = placeIntro({ width: 360, height: 780, top: 68, taken: [{ left: 16, top: 68, right: 224, bottom: 268 }, { left: 241, top: 68, right: 344, bottom: 112 }], size: { width: 328, height: 70 } });
  assert.deepEqual(phone, { left: 16, top: 276 });
  // Nothing free in the upper half (the landing's cards fill it), or a line wider than the window: it waits.
  assert.equal(placeIntro({ width: 1280, height: 720, top: 64, taken: [{ left: 0, top: 60, right: 1280, bottom: 720 }], size }), null);
  assert.equal(placeIntro({ width: 300, height: 600, top: 64, taken: [], size: { width: 290, height: 40 } }), null);
  // Never within the gap of anything taken, at any place it finds.
  const taken = [{ left: 16, top: 64, right: 300, bottom: 400 }, { left: 900, top: 64, right: 1264, bottom: 300 }, { left: 400, top: 90, right: 600, bottom: 130 }];
  const found = placeIntro({ width: 1280, height: 720, top: 64, taken, size });
  assert.ok(found && taken.every((rect) => found.left + size.width + 8 <= rect.left || found.left >= rect.right + 8 || found.top + size.height + 8 <= rect.top || found.top >= rect.bottom + 8), JSON.stringify(found));
});

test("what the page knows of itself: the stamp's date and revision, the release on the site, the licence at the map's revision", () => {
  const meta = { as_of: "2026-11-20", revision: "93fc8c2c", source_base_url: `https://github.com/Eidosoma/Cells/blob/${"9".repeat(40)}/` };
  assert.deepEqual(pageFacts(meta, { release: null }, formatDate), [["Map", "As of 20 Nov 2026 · main 93fc8c2c"]], "the artifact: no release named");
  assert.deepEqual(pageFacts(meta, { release: "v53" }, formatDate), [["Map", "As of 20 Nov 2026 · main 93fc8c2c"], ["Release", "v53"]]);
  assert.deepEqual(pageFacts({}, {}), [], "nothing it does not know");
  const read = aboutOf({ about: WORDS });
  assert.equal(licenceUrl(read, meta), `https://github.com/Eidosoma/Cells/blob/${"9".repeat(40)}/LICENSE`);
  assert.equal(licenceUrl(read, { source_base_url: "https://example.org/blob/x/" }), null, "only at a revision of the source's own repository");
  // The page carries the words in its scene (tools/lib/build_page.mjs), and the viewer reads them from there.
  assert.match(readFileSync(path.join(ROOT, "tools", "lib", "build_page.mjs"), "utf8"), /data\.about = JSON\.parse\(await readFile\(aboutPath, "utf8"\)\)/);
});
