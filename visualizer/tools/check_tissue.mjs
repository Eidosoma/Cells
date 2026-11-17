#!/usr/bin/env node
// Checks the gap-junction example's tissue line (src/lenses/tissue_line.js) with real pointer input, through the
// DevTools protocol, on its real runs: the run folder the page's selection names, packaged here by the page's own overlay
// and selection, with one run of the example's networks. What it expects (the arms, their names and ends, the card's
// lines, a stated state to press on) is read from the packaged catalogue, the overlay and the driver's own criterion
// files, so that a new run folder is data alone. Where the runs' folder is not on this machine the check is skipped,
// and says so.
//
//   wide     1400 by 900, light: the example opens on its network; a real press on the door in its card shows the
//            tissue line in the tab's place; the picks in D's order, any refused named with nothing drawn;
//            the record's words in the card; each picture's colours as drawn are the scale's colour of the saved value;
//            a real press on a picture moves the clock to that record and opens the cell, with the driver's state;
//            the even time scale; the way back to the networks; the address opens it.
//   phone    390 by 844, dark: one run above the other, the colours as drawn in the dark tokens, the card's picks.
//   reduced  1400 by 900, light, less motion, not held still: nothing plays, and the pictures are whole at once.
//
//   node tools/check_tissue.mjs [OUT_DIR]
//
// Set by the environment: CASE (wide, phone or reduced; wide unless set), WIDTH, HEIGHT and THEME (by the case unless
// set), NAME (the pictures' prefix), EVIDENCE (the folder that holds the evidence folders). Chrome is what CHROME
// names (tools/chrome_gpu.sh for the graphics card), in a place taken through tools/lib/browser_lock.mjs.

import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, rmSync } from "node:fs";
import { writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { acquireBrowser } from "./lib/browser_lock.mjs";
import { createServer } from "./serve.mjs";
import { lineOf } from "../src/replay/tissue_line.js";
import { clock } from "../src/replay/format.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const CASE = process.env.CASE || "wide";
const CASES = { wide: [1400, 900, "light"], phone: [390, 844, "dark"], reduced: [1400, 900, "light"] };
if (!CASES[CASE]) throw new Error(`no case ${CASE}: wide, phone or reduced`);
const WIDTH = Number(process.env.WIDTH || CASES[CASE][0]), HEIGHT = Number(process.env.HEIGHT || CASES[CASE][1]), THEME = process.env.THEME || CASES[CASE][2];
const REDUCED = CASE === "reduced" || process.env.REDUCED === "1";
const NAME = process.env.NAME || `tissue-${CASE}`;
const OUT = path.resolve(process.argv[2] || path.join(ROOT, "out", "check-tissue"));
const EVIDENCE = process.env.EVIDENCE || "/mnt/workspaces/Cells";
const PART = "gap-junction-tissue-line", WHOLE = "gap-junction-linear-network";
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const results = [];
const check = (name, ok, detail = "") => {
  results.push(Boolean(ok));
  console.log(`${ok ? "pass" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`);
};
const note = (text) => console.log(`note  ${text}`);

// ---------------------------------------------------------------- the runs, as the page's overlay and selection package them
const selection = JSON.parse(readFileSync(path.join(ROOT, "data", "replays", "selection.json"), "utf8"));
const chosen = selection[PART];
const picks = path.join(EVIDENCE, chosen.evidence_folder, ...(chosen.within || []));
if (!existsSync(picks)) {
  note(`the tissue line's runs are not on this machine (${picks}): the check is skipped`);
  console.log("0 of 0 checks passed (skipped)");
  process.exit(0);
}
const runs = path.join(OUT, `${NAME}-runs`);
rmSync(runs, { recursive: true, force: true }); // packaged afresh each time: no run of an earlier selection stays beside them
mkdirSync(runs, { recursive: true });
const adapt = (args) => {
  const done = spawnSync("python3", [path.join(ROOT, "tools", "adapt_run.py"), "--evidence", EVIDENCE, "--out", runs, ...args], { encoding: "utf8" });
  if (done.status !== 0) throw new Error(`adapt_run.py ${args.join(" ")} failed: ${done.stderr.slice(-600)}`);
  return done.stdout;
};
// One run of the example's networks (its seven cells), so that the example opens and its card holds the door; then the tissue line.
adapt(["--experiment", WHOLE, "--run", "figure5-network-g1"]);
adapt(["--experiment", PART]);
const index = JSON.parse(readFileSync(path.join(runs, "index.json"), "utf8"));
// What the page should show, from the data: the line's slots as the catalogue states them, the overlay's words, and each
// arm's criterion as the driver's file gives it.
const LINE = lineOf(index, PART);
const ENTRY = JSON.parse(readFileSync(path.join(ROOT, "data", "replays", "overlay.json"), "utf8")).experiments[PART];
const ARMS = LINE.runs.map((slot) => slot.arm);
const STATED = Object.fromEntries(ARMS.map((arm) => [arm, JSON.parse(readFileSync(path.join(picks, arm, "criterion.json"), "utf8"))]));
const criterion = STATED[ARMS[0]].criterion;
const LAST = STATED[ARMS[0]].times_s.length - 1;
// A record to press on: the first where a cell's stated state is neither M nor E (the criterion's between), else the first
// stated change, else the first record of the first arm's first cell.
const PRESS = (() => {
  for (const arm of ARMS) for (const [row, states] of STATED[arm].states.entries()) { const cell = states.findIndex((word) => word !== "M" && word !== "E"); if (cell >= 0) return { arm, cell, record: row, state: states[cell] }; }
  for (const arm of ARMS) for (let row = 1; row < STATED[arm].states.length; row++) { const cell = STATED[arm].states[row].findIndex((word, k) => word !== STATED[arm].states[row - 1][k]); if (cell >= 0) return { arm, cell, record: row, state: STATED[arm].states[row][cell] }; }
  return { arm: ARMS[0], cell: 0, record: 0, state: STATED[ARMS[0]].states[0][0] };
})();
PRESS.time = STATED[PRESS.arm].times_s[PRESS.record];
PRESS.name = STATED[PRESS.arm].cells[PRESS.cell];
PRESS.end = LINE.runs.find((slot) => slot.arm === PRESS.arm).end;
const SIDE = { M: "below", E: "above" }; // the criterion's words for a state, to hold a colour's side beside the driver's state
note(`the line: ${LINE.slots.map((slot) => `${slot.kind} ${slot.arm}`).join(", ")}; a press at ${PRESS.arm} ${PRESS.name}, record ${PRESS.record} (${PRESS.state})`);

// ---------------------------------------------------------------- the browser
const release = await acquireBrowser({ wait: 60 * 60 * 1000 });
const server = createServer({ offline: true, runs, log: () => {} });
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}/`;
const chrome = spawn(process.env.CHROME || "google-chrome", ["--headless=new", `--user-data-dir=${release.profile}`, "--disable-breakpad", "--no-first-run", "--no-sandbox", "--mute-audio", "--hide-scrollbars", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", `--window-size=${WIDTH},${HEIGHT}`, "--remote-debugging-port=0", "about:blank"], { stdio: ["ignore", "ignore", "pipe"] });
let failed = null;
try {
  const endpoint = await new Promise((resolve, reject) => {
    let text = "";
    chrome.stderr.on("data", (chunk) => { text += chunk; const m = text.match(/DevTools listening on (ws:\/\/\S+)/); if (m) resolve(m[1]); });
    setTimeout(() => reject(new Error("no DevTools address")), 120000);
  });
  const socket = new WebSocket(endpoint);
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  let nextId = 1;
  const waiting = new Map();
  socket.onmessage = (event) => { const m = JSON.parse(event.data); const w = waiting.get(m.id); if (!w) return; waiting.delete(m.id); if (m.error) w.reject(new Error(m.error.message)); else w.resolve(m.result); };
  const send = (method, params = {}, sessionId) => new Promise((resolve, reject) => { const id = nextId++; waiting.set(id, { resolve, reject }); socket.send(JSON.stringify({ id, method, params, sessionId })); });
  const { targetId } = await send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
  const page = (method, params) => send(method, params, sessionId);
  await page("Runtime.enable");
  await page("Page.enable");
  await page("Page.addScriptToEvaluateOnNewDocument", { source: `window.__pageErrors = []; addEventListener("error", (event) => __pageErrors.push(String(event.error?.stack || event.message)));` });
  await page("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: HEIGHT, deviceScaleFactor: 1, mobile: WIDTH < 760 });
  const media = [{ name: "prefers-color-scheme", value: THEME }];
  if (REDUCED) media.push({ name: "prefers-reduced-motion", value: "reduce" });
  await page("Emulation.setEmulatedMedia", { features: media });
  const evaluate = async (expression) => {
    const reply = await page("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (reply.exceptionDetails) throw new Error(reply.exceptionDetails.exception?.description || reply.exceptionDetails.text);
    return reply.result.value;
  };
  const V = "document.querySelector('cells-viewer')", L = `${V}.current`;
  const mouse = (type, x, y, extra = {}) => page("Input.dispatchMouseEvent", { type, x, y, button: "left", buttons: 1, clickCount: 1, ...extra });
  const click = async (x, y, wait = 900) => {
    await mouse("mouseMoved", x, y, { button: "none", buttons: 0 });
    await mouse("mousePressed", x, y);
    await mouse("mouseReleased", x, y, { buttons: 0 });
    await sleep(wait);
  };
  /** The middle of what an expression finds, scrolled into view, if nothing lies over it. */
  const placeOf = (expression) => evaluate(`(() => { const root = ${V}.shadowRoot, el = ${expression}; if (!el) return null; el.scrollIntoView({ block: "center" }); const r = el.getBoundingClientRect(); if (!r.width || !r.height) return null; const x = r.left + r.width / 2, y = r.top + r.height / 2; const top = root.elementFromPoint(x, y); return top && (top === el || el.contains(top)) ? { x, y } : null; })()`);
  const until = async (test, tries = 160) => {
    for (let k = 0; k < tries; k++) {
      if (await evaluate(test).catch(() => false)) return true;
      await sleep(250);
    }
    return false;
  };
  const shown = `Boolean(${L}?.partId === ${JSON.stringify(PART)} && ${L}.runs?.length && ${L}.pieces)`;
  const shot = async (name) => {
    await evaluate(`${V}.stage.invalidate()`);
    await sleep(1200);
    const { data } = await page("Page.captureScreenshot", { format: "png" });
    const file = path.join(OUT, "pictures", `${NAME}-${name}.png`);
    mkdirSync(path.dirname(file), { recursive: true });
    await writeFile(file, Buffer.from(data, "base64"));
    note(`wrote ${file}`);
  };
  /** What the picture shows now: the slots' names on it, the card's and the legend's words, where the pictures stand, the clock. */
  const state = () => evaluate(`(() => {
    const v = ${V}, root = v.shadowRoot, lens = v.current, box = v.getBoundingClientRect();
    const tags = (kind) => [...root.querySelectorAll(".label-" + kind)].filter((el) => !el.classList.contains("is-off")).map((el) => { const r = el.getBoundingClientRect(); return { text: el.textContent, x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2), inside: r.left >= box.left - 1 && r.right <= box.right + 1 }; });
    v.stage.camera.updateMatrixWorld();
    const pictures = lens?.pieces ? [...lens.pieces.values()].map(({ place, item }) => { const a = new lens.root.position.constructor(place.x0, place.top, 0).project(v.stage.camera), b = new lens.root.position.constructor(place.x1, place.bottom, 0).project(v.stage.camera); return { arm: item.slot.arm, left: Math.round(((a.x + 1) / 2) * box.width), top: Math.round(((1 - a.y) / 2) * box.height), right: Math.round(((b.x + 1) / 2) * box.width), bottom: Math.round(((1 - b.y) / 2) * box.height) }; }) : [];
    const card = root.querySelector(".view");
    return {
      part: lens?.partId || null, tab: v.state.lens, columns: lens?.columns ?? null, slots: lens?.line?.slots.map((slot) => slot.kind + ":" + slot.arm) || [],
      heads: tags("tissue-head"), ends: tags("tissue-end"), refused: tags("tissue-refused"), ticks: tags("tissue-tick"), chosen: tags("tissue-state"),
      says: [...root.querySelectorAll(".tissue-says li")].map((li) => li.textContent),
      slotsCard: [...root.querySelectorAll(".tissue-slot")].map((el) => [el.querySelector("b")?.textContent, el.querySelector("span")?.textContent]),
      criterion: root.querySelector(".tissue-criterion")?.textContent || "",
      card: card?.textContent || "", legend: root.querySelector("cells-legend")?.textContent || "",
      // The card's words that are the tissue line's own: not the tab's list (the page's names for its examples), not the criterion's own words.
      own: (() => { if (!card) return ""; const copy = card.cloneNode(true); for (const el of copy.querySelectorAll(".experiments, #cells-experiment, .tissue-criterion, .eyebrow")) el.remove(); for (const el of copy.querySelectorAll("details")) if (/Sources and licences/.test(el.querySelector("summary")?.textContent || "")) el.remove(); return copy.textContent; })(),
      list: [...root.querySelectorAll(".view .exp-row")].map((b) => [b.textContent, b.getAttribute("aria-pressed")]),
      pictures, time: lens?.player?.time ?? null, playing: lens?.player?.playing ?? null, scale: lens?.scale || null, axis: lens?.axisNow?.words || "",
      selected: v.state.selected, panel: root.querySelector("cells-panel")?.textContent || "", flight: Boolean(v.stage.rig.flight),
      errors: window.__pageErrors,
    };
  })()`);
  /**
   * The colours drawn at a cell's column of a picture, at a record's band: the camera looks close at the place (as
   * close as the view lets a visitor come), the frame is drawn, and the pixel there is read back, beside the scale's
   * colour of the saved value. A band drawn under four pixels even then is not read. The camera goes back after.
   * [{ arm, cell, record, value, drawn, wanted, side }]
   */
  const drawn = (samples) => evaluate(`(() => {
    const v = ${V}, lens = v.current, stage = v.stage, gl = stage.renderer.getContext(), box = v.getBoundingClientRect(), before = stage.rig.view();
    const ratio = stage.renderer.getPixelRatio(), pixel = new Uint8Array(4), out = [];
    for (const [arm, cell, record] of ${JSON.stringify(samples)}) {
      const { place, item } = lens.pieces.get(arm), { from, to } = lens.bandsNow[record];
      // Read a little above the band's middle: the picture's frame lies just under the last band.
      const y = place.top - (from + 0.4 * (to - from)) * (place.top - place.bottom), x = place.x0 + item.cells.x[cell];
      stage.rig.setView({ target: new lens.root.position.constructor(x, y, 0), distance: lens.home.distance * 0.18, azimuth: 0, polar: Math.PI / 2 });
      stage.draw();
      const p = new lens.root.position.constructor(x, y, 0).project(stage.camera);
      const px = Math.round(((p.x + 1) / 2) * stage.width * ratio), py = Math.round(((p.y + 1) / 2) * stage.height * ratio);
      // How tall the band is drawn: one under two pixels is shared with its neighbours, and is not read.
      const q = new lens.root.position.constructor(x, place.top - to * (place.top - place.bottom), 0).project(stage.camera), r0 = new lens.root.position.constructor(x, place.top - from * (place.top - place.bottom), 0).project(stage.camera);
      if (Math.abs(q.y - r0.y) * stage.height / 2 < 4) continue;
      gl.readPixels(px, py, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
      const value = item.record.at(record, item.cells.columns[cell]), rgb = lens.breaks.colour(value);
      out.push({ arm, cell, record, value: Number(value.toFixed(3)), drawn: [...pixel.slice(0, 3)], wanted: rgb.map((c) => Math.round(c * 255)), side: lens.breaks.side(value) });
    }
    stage.rig.setView(before);
    stage.draw();
    return out;
  })()`);
  const close = (sample) => sample.drawn.every((c, k) => Math.abs(c - sample.wanted[k]) <= 3);
  /** Every band read is the scale's colour of its value, and enough of them were read. */
  const allClose = (colours, least = 6) => colours.length >= least && colours.every(close);
  // Every sample: the tumor's first cell of each run at its first and last record, a healthy cell midway, and the cell pressed.
  const SAMPLES = [...ARMS.flatMap((arm) => [[arm, 0, 0], [arm, 0, LAST], [arm, 10, Math.round(LAST / 2)]]), [PRESS.arm, PRESS.cell, PRESS.record]];
  const forbidden = /replicat|reproduc|\bagree|\bmatch|modelled|qualified|simulated|Grodstein|preprint/i;

  // A fresh browser's first page on the card loses its context about five seconds in: it is a throwaway.
  await page("Page.navigate", { url: `${base}?lens=engine` });
  await sleep(7000);
  note(`case ${CASE}, ${WIDTH} by ${HEIGHT}, ${THEME}${REDUCED ? ", less motion" : ""}`);

  if (CASE === "wide") {
    // The example opens on its seven cells; its card holds the door to its tissue line.
    await page("Page.navigate", { url: `${base}?lens=experiments&still=1` });
    await until(`Boolean(${L}?.run && ${L}.sheet)`, 240);
    const opened = await evaluate(`({ run: ${L}.runId, part: ${V}.state.part })`);
    check("the Experiments view still opens on the example's network, not on its tissue line", opened.run === `${WHOLE}--figure5-network-g1` && !opened.part, JSON.stringify(opened));
    const door = await placeOf(`root.querySelector('.view .tissue-door[data-part="${PART}"]')`);
    check("the example's card holds the door to its tissue line, as a part of the example", Boolean(door), "");
    if (door) await click(door.x, door.y, 1200);
    check("a real press on the door shows the tissue line in the tab's place, the tab still pressed", await until(shown, 240), "");
    await sleep(1500);
    let s = await state();
    check(`the ${LINE.slots.length} picks stand in D's order (${LINE.runs.length} runs, ${LINE.refused.length} refused)`, JSON.stringify(s.slots) === JSON.stringify(LINE.slots.map((slot) => `${slot.kind}:${slot.arm}`)) && s.tab === "experiments", JSON.stringify(s.slots));
    const heads = s.heads.map((tag) => tag.text);
    check("each pick is named on the picture by its D, left to right in that order, inside the window", JSON.stringify(heads) === JSON.stringify(LINE.slots.map((slot) => slot.label)) && s.heads.every((tag, k) => tag.inside && (k === 0 || tag.x > s.heads[k - 1].x)), JSON.stringify(s.heads));
    check(LINE.refused.length ? "the refused picks are said on the picture, with nothing drawn in them" : "no pick was refused: none is said, and every run is drawn", s.refused.length === LINE.refused.length && s.refused.every((tag) => tag.text === LINE.refusedWords) && s.pictures.length === LINE.runs.length, JSON.stringify([s.refused, s.pictures.map((p) => p.arm)]));
    check("each run's end states stand under its picture, in the note's words", JSON.stringify(s.ends.map((tag) => tag.text)) === JSON.stringify(LINE.runs.map((slot) => slot.end)), JSON.stringify(s.ends));
    check("the runs stand side by side, each picture inside the room the cards leave it, clear of the timeline", s.columns === true && s.pictures.every((p) => p.left > 290 && p.right <= WIDTH - 4 && p.top > 56 && p.bottom < HEIGHT - 70), JSON.stringify(s.pictures));
    check("the card says what the record lets it say, in its words", JSON.stringify(s.says) === JSON.stringify(ENTRY.tissue.says), JSON.stringify(s.says));
    check("the card lists the picks with each run's end and each refusal", JSON.stringify(s.slotsCard) === JSON.stringify(LINE.slots.map((slot) => [slot.label, slot.kind === "refused" ? LINE.refusedWords : slot.end])), JSON.stringify(s.slotsCard));
    check("the criterion stands in the card in its own words, with its source, as the driver's file gives them", s.criterion.includes(`“${criterion.words}”`) && s.criterion.includes(criterion.source), s.criterion.slice(0, 120));
    // The tissue line's own words: its card (but the tab's list, which names the example as the page does, and the criterion in its own words), its legend and its names on the picture.
    // Its one sentence on the logged value and its one on what BITSEY is are the lead's (the card's lines, checked above word for word).
    const own = [s.own, s.legend, ...[...s.heads, ...s.ends, ...s.refused, ...s.ticks].map((tag) => tag.text)].join(" ");
    const beyond = ENTRY.tissue.says.filter((line) => /BITSEY|logged/.test(line)).reduce((text, line) => text.replace(line, ""), own);
    // The sentence on what BITSEY is names the preprint for whose code it is, and for that alone: the other forbidden words hold in it too.
    const judging = /replicat|reproduc|\bagree|\bmatch|modelled|qualified|simulated|Grodstein/i;
    check("nothing the tissue line says (but the criterion's own words, and the lead's one sentence on the logged value and one on BITSEY) names the preprint, its authors or their code, or says replicated, agrees or matches", !forbidden.test(beyond) && !judging.test(own) && !/BITSEY|authors|logged/.test(beyond), (beyond.match(forbidden) || own.match(judging) || beyond.match(/BITSEY|authors|logged/) || [""])[0]);
    check("the tab's list stands at the head of the card, the example's row pressed", s.list.length === 2 && s.list[0][1] === "true", JSON.stringify(s.list));
    // The colours as drawn: the scale's colour of the saved value, at each sample's band.
    const colours = await drawn(SAMPLES);
    check("each picture's colour as drawn is the scale's colour of the value the driver states there, record by record", allClose(colours, 8), `${colours.length} bands read; ${JSON.stringify(colours.filter((sample) => !close(sample)))}`);
    const sides = ARMS.flatMap((arm) => [0, LAST].map((record) => ({ arm, record, side: colours.find((c) => c.arm === arm && c.cell === 0 && c.record === record)?.side, stated: STATED[arm].states[record][0] })));
    check("each run's first tumor cell, at its first and last record, is drawn on the side of the scale its stated state names", sides.every((item) => !SIDE[item.stated] || item.side === SIDE[item.stated]), JSON.stringify(sides));
    await shot("line");
    // A real press on a picture, at a cell and record where the driver states a cell between its two states: the clock goes there, and the cell opens with the driver's state.
    const target = await evaluate(`(() => { const v = ${V}, lens = v.current, { place, item } = lens.pieces.get(${JSON.stringify(PRESS.arm)}), t = lens.clockRun.t, k = ${PRESS.record}; const { from, to } = lens.bandsNow[k]; const p = new lens.root.position.constructor(place.x0 + item.cells.x[${PRESS.cell}], place.top - ((from + to) / 2) * (place.top - place.bottom), 0).project(v.stage.camera); const box = v.getBoundingClientRect(); return { x: box.left + ((p.x + 1) / 2) * box.width, y: box.top + ((1 - p.y) / 2) * box.height, time: t[k], tall: Math.abs(to - from) * (place.top - place.bottom) }; })()`);
    await click(target.x, target.y, 1600);
    s = await state();
    check(`a real press on a picture opens that cell and moves the clock to the record pressed (${PRESS.arm}, ${PRESS.name}, ${clock(PRESS.time)})`, s.selected === `tissue:${PRESS.arm}:${PRESS.cell}` && Math.abs(s.time - target.time) < 1e-6, JSON.stringify([s.selected, s.time, target.time]));
    const said = new RegExp(`State there, as the driver states it\\s*${PRESS.state}`);
    check(`its panel gives its value and its state as the driver states it (${PRESS.state} there), and the note's end line`, said.test(s.panel) && s.panel.includes(`miR200 minus Zeb mRNA at ${clock(PRESS.time)}`) && s.panel.includes(PRESS.end), s.panel.slice(0, 260));
    check("the chosen cell is named on the picture with the driver's state", s.chosen.length === 1 && s.chosen[0].text === `${PRESS.name} · ${PRESS.state}`, JSON.stringify(s.chosen));
    await shot("pressed");
    // The even time scale, chosen on the card; the clock is moved off the bands read, and the cell let go.
    await evaluate(`${V}.select(null)`);
    await evaluate(`${L}.seek(5000)`);
    await evaluate(`(() => { const select = ${V}.shadowRoot.querySelector('.view select[data-choice="time-scale"]'); select.value = "even"; select.dispatchEvent(new Event("change")); })()`);
    await sleep(1200);
    s = await state();
    check("the card's time scale draws time down the pictures evenly, and the legend says so", s.scale === "even" && /on an even scale/.test(s.axis) && s.ticks.some((tag) => tag.text === "2 h"), JSON.stringify([s.scale, s.ticks.map((tag) => tag.text)]));
    const evenColours = await drawn(SAMPLES);
    check("on the even scale too, the colours as drawn are the scale's colours of the saved values, where a band is four pixels or more, looked at close", allClose(evenColours, 4), `${evenColours.length} bands read; ${JSON.stringify(evenColours.filter((sample) => !close(sample)))}`);
    await shot("even");
    // A run's details, from its line in the card's picks: a real press on "Run details" opens the run's own panel.
    const details = await placeOf(`[...root.querySelectorAll('.tissue-slot[data-arm="${ARMS[0]}"] .tissue-open')][0]`);
    if (details) await click(details.x, details.y, 1200);
    s = await state();
    check("a real press on a pick's \"Run details\" opens that run's panel, with how its replay was made", Boolean(details) && s.selected === `run:${LINE.runs[0].id}` && s.panel.includes(ARMS[0]) && /How this replay was (derived|made)/.test(s.panel), JSON.stringify([s.selected, s.panel.slice(0, 160)]));
    // The way back: a real press on the example's row in the list at the head of the card.
    await evaluate(`${V}.select(null)`);
    await sleep(600);
    const back = await placeOf(`root.querySelector(".view .exp-row:not([data-door])")`);
    if (back) await click(back.x, back.y, 1500);
    await until(`Boolean(${L}?.run && ${L}.sheet)`, 120);
    const after = await evaluate(`({ run: ${L}.runId || null, part: ${V}.state.part })`);
    check("a real press on the example's row gives the tab back to its networks", Boolean(back) && after.run?.startsWith(`${WHOLE}--`) && !after.part, JSON.stringify(after));
    // The address opens it, and a page that moves plays it.
    await page("Page.navigate", { url: `${base}?lens=experiments&part=${PART}` });
    check("the address (part=) opens the tissue line", await until(shown, 240), "");
    await sleep(2500);
    s = await state();
    check("a page that may move plays the three runs under one clock as it opens", s.playing === true && s.time > 0, JSON.stringify([s.playing, s.time]));
    // The timeline's own keys step the three runs' one clock, record by record.
    await evaluate(`${L}.player.pause(); ${L}.player.seek(0)`);
    await evaluate(`${V}.shadowRoot.querySelector("cells-timeline")?.shadowRoot?.querySelector('input[type="range"]')?.focus() || ${V}.timeline.range?.focus()`);
    for (const _ of [0, 1, 2]) {
      await page("Input.dispatchKeyEvent", { type: "rawKeyDown", key: "ArrowRight", code: "ArrowRight", windowsVirtualKeyCode: 39 });
      await page("Input.dispatchKeyEvent", { type: "keyUp", key: "ArrowRight", code: "ArrowRight", windowsVirtualKeyCode: 39 });
      await sleep(300);
    }
    s = await state();
    check("the timeline's arrow key steps the one clock record by record: three presses, the third record", s.time === 300, JSON.stringify(s.time));
    // The page's theme turns dark while the line is shown: the pictures take the dark tokens.
    await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "dark" }] });
    await sleep(1500);
    const dark = await drawn(SAMPLES);
    check("the theme turned dark: the colours as drawn are the scale's colours in the dark tokens", allClose(dark, 8) && dark.every((c) => { const light = colours.find((x) => x.arm === c.arm && x.cell === c.cell && x.record === c.record); return !light || light.wanted.join() !== c.wanted.join(); }), `${dark.length} bands read; ${JSON.stringify(dark.filter((sample) => !close(sample)).slice(0, 3))}`);
    await shot("dark");
    // The window turns narrow: the runs stand one above the other, each inside the window.
    await page("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
    await sleep(2000);
    s = await state();
    check("the window turned narrow: the runs stand one above the other, inside it", s.columns === false && s.pictures.every((p) => p.left >= 0 && p.right <= 390), JSON.stringify(s.pictures));
    await page("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: HEIGHT, deviceScaleFactor: 1, mobile: false });
    await sleep(1500);
    s = await state();
    check("and wide again: side by side", s.columns === true, "");
    // The bar's stamp never drops onto the pictures' heads: at a laptop's widths it stays in the bar's one row, shortened where
    // the row is short, its first words (the part's standing) kept, the List whole.
    for (const [width, height] of [[1280, 720], [1024, 768], [800, 760]]) {
      await page("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: false });
      await sleep(1800);
      const bar = await evaluate(`(() => { const root = ${V}.shadowRoot, box = (el) => { const r = el?.getBoundingClientRect(); return r && r.width ? [r.left, r.top, r.right, r.bottom] : null; }; const stamp = root.querySelector(".stamp"), list = root.querySelector(".bar-end .pill-button"), s = box(stamp), b = box(root.querySelector(".bar")), heads = [...root.querySelectorAll(".label-tissue-head")].map(box).filter(Boolean); return { stamp: s, words: s ? stamp.textContent : "", inRow: !s || (s[1] >= b[1] && s[3] <= b[3]), over: s ? heads.filter((h) => !(h[2] <= s[0] || h[0] >= s[2] || h[3] <= s[1] || h[1] >= s[3])).length : 0, heads: heads.length, list: Boolean(list) && list.getBoundingClientRect().right <= innerWidth && list.scrollWidth <= list.clientWidth + 1, sideways: document.documentElement.scrollWidth > innerWidth + 1 }; })()`);
      check(`${width} by ${height}: the stamp stands in the bar's row, over none of the pictures' heads, beginning with the part's standing, the List whole`, bar.inRow && bar.over === 0 && bar.heads > 0 && bar.list && !bar.sideways && (!bar.stamp || /^Development work, not judged/.test(bar.words)), JSON.stringify(bar));
    }
    await page("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: HEIGHT, deviceScaleFactor: 1, mobile: false });
    await sleep(1200);
    check("the page logged no error", !(s.errors || []).length, JSON.stringify(s.errors));
  } else if (CASE === "phone") {
    // The way in by real presses: the example's folded card opened, its door pressed.
    await page("Page.navigate", { url: `${base}?lens=experiments&still=1` });
    await until(`Boolean(${L}?.run && ${L}.sheet)`, 240);
    const unfold = async () => {
      if (await evaluate(`${V}.state.viewOpen`)) return true;
      const fold = await placeOf(`root.querySelector(".view-toggle")`);
      if (fold) await click(fold.x, fold.y, 1000);
      return Boolean(fold);
    };
    await unfold();
    const door = await placeOf(`root.querySelector('.view .tissue-door[data-part="${PART}"]')`);
    if (door) await click(door.x, door.y, 1200);
    check("on a phone, a real press on the door in the example's opened card shows the tissue line", Boolean(door) && (await until(shown, 240)), "");
    await sleep(1500);
    // The way back by real presses: the card opened, its own button.
    await unfold();
    const back = await placeOf(`root.querySelector(".view .tissue-back")`);
    if (back) await click(back.x, back.y, 1500);
    const returned = await until(`Boolean(${L}?.run && ${L}.sheet && !${V}.state.part)`, 120);
    check("and a real press on the card's \"Back to the example's networks\" gives the tab back to the networks", Boolean(back) && returned, "");
    await page("Page.navigate", { url: `${base}?lens=experiments&still=1&part=${PART}` });
    check("the address opens the tissue line on a phone", await until(shown, 240), "");
    await sleep(1500);
    let s = await state();
    check("on a phone the runs stand one above the other, each picture inside the window's width", s.columns === false && s.pictures.length === LINE.runs.length && s.pictures.every((p, k) => p.left >= 0 && p.right <= WIDTH && (k === 0 || p.top > s.pictures[k - 1].bottom)), JSON.stringify(s.pictures));
    check("each run is named by its D and its end, and each refused pick by its D and its refusal, on the picture", JSON.stringify(s.heads.map((tag) => tag.text)) === JSON.stringify(LINE.runs.map((slot) => slot.label)) && s.refused.length === LINE.refused.length && s.refused.every((tag) => LINE.refused.some((slot) => tag.text.startsWith(`${slot.label} · `)) && tag.inside) && JSON.stringify(s.ends.map((tag) => tag.text)) === JSON.stringify(LINE.runs.map((slot) => slot.end)), JSON.stringify([s.heads, s.refused, s.ends.map((tag) => tag.text)]));
    const colours = await drawn(SAMPLES);
    check("the colours as drawn are the scale's colours of the saved values, in the dark page's tokens", allClose(colours, 4) && colours[0].wanted.join() !== "161,74,12", `${colours.length} bands read; ${JSON.stringify(colours.filter((sample) => !close(sample)).slice(0, 3))}`);
    await shot("line");
    // The folded card opens on a real press: the record's lines and the picks.
    const fold = await placeOf(`root.querySelector(".view-toggle")`);
    if (fold) await click(fold.x, fold.y, 1000);
    s = await state();
    check("a real press opens the card: the record's lines and the picks", JSON.stringify(s.says) === JSON.stringify(ENTRY.tissue.says) && s.slotsCard.length === LINE.slots.length, JSON.stringify([s.says, s.slotsCard.length]));
    await shot("card");
    check("the page logged no error", !(s.errors || []).length, JSON.stringify(s.errors));
  } else if (CASE === "reduced") {
    await page("Page.navigate", { url: `${base}?lens=experiments&part=${PART}` });
    check("the address opens the tissue line with less motion asked for", await until(shown, 240), "");
    await sleep(3000);
    const s = await state();
    check("with less motion nothing plays: the clock stands at the first record, and the camera did not fly", s.playing === false && s.time === 0 && !s.flight, JSON.stringify([s.playing, s.time, s.flight]));
    const colours = await drawn(SAMPLES);
    check("the whole of each run is drawn at once, the last record as the first: no record waits for the clock", allClose(colours) && colours.some((c) => c.record === LAST), `${colours.length} bands read; ${JSON.stringify(colours.filter((sample) => !close(sample)))}`);
    await shot("line");
    check("the page logged no error", !(s.errors || []).length, JSON.stringify(s.errors));
  }
  const font = await evaluate(`document.fonts.check('12px Inter') ? "the page's font" : "a stand-in font"`).catch(() => "unknown");
  note(`drawn with ${font}`);
  socket.close();
} catch (error) {
  failed = error;
} finally {
  chrome.kill("SIGTERM");
  await new Promise((resolve) => { chrome.once("exit", resolve); setTimeout(resolve, 8000); });
  await release();
  server.close();
}
if (failed) {
  console.error(`check_tissue: ${failed.stack || failed}`);
  process.exit(2);
}
const passed = results.filter(Boolean).length;
console.log(`${passed} of ${results.length} checks passed`);
process.exit(passed === results.length ? 0 : 1);
