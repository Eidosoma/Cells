#!/usr/bin/env node
// Checks the gap-junction example's tumour tissue (src/lenses/tissue_line.js) with real pointer input, through the
// DevTools protocol, on its real runs: the run folders the page's selection names for the line and the sheet, packaged
// here by the page's own overlay and selection, with one run of the example's networks. What it expects (the arms, their
// names and ends, the card's lines, a stated state to press on, the stated changes) is read from the packaged catalogue,
// the overlay and the driver's own criterion files, so that a new run folder is data alone. Where the runs' folders are
// not on this machine the check is skipped, and says so.
//
//   wide     1400 by 900, light: the tab opens on the line (the example's opens.part); its arms in D's order with their
//            names, places and ends; the record's words in the card; the sheet's caption with its door over the line;
//            each cell's colour as drawn is the scale's colour of the stated value; a real press on a map moves the clock
//            and opens the cell, ringed on the picture, with the driver's state; the timeline's next change; the even
//            scale; a run's details; the way back to the networks (the seven-cell network shown); a real press on the
//            sheet's door shows the sheet with the line beside it; what the opening fetches; the theme; a narrow window;
//            the bar's stamp at a laptop's widths.
//   phone    390 by 844, dark: the way to the networks and back by real presses; the line and the sheet inside the window.
//   reduced  1400 by 900, light, less motion, not held still: nothing plays.
//   play     1280 by 720, light, motion: the clock plays the stated changes, each on the screen for its stretch, and the
//            picture at each change differs from the picture before it.
//   sheet    1280 by 720, light: the switch turned to the sheet (the example's opens.part, in this check's own packaged
//            catalogue): the extension sentence in full on the first screen beside "Development work, not judged.", the
//            sheet's own bracket, x2 named as the line's wherever a place is, the line beside it as the record the
//            threshold comes from, no heading that reads it as the preprint's; what it fetches; and on a phone.
//
//   layout   at 1280 by 720, 1024 by 768, 1440 by 900, 400 by 860 and 360 by 780: in every state a press reaches (the
//            line; at a change; a pressed cell; the sheet; the sheet at a change; the sheet with every arm; playing at a
//            change) no two names on the picture meet, no name but a change's or a chosen cell's lies on a cell, every
//            name is inside the window; and the tissues are large enough (a line's cell 28 px at 1280 by 720 and 36 at 1440
//            by 900, three sheets 200 px each at 1280 by 720, six 130).
//
//   node tools/check_tissue.mjs [OUT_DIR]
//
// Set by the environment: CASE (wide, phone, reduced, play or sheet; wide unless set), WIDTH, HEIGHT and THEME (by the
// case unless set), NAME (the pictures' prefix), EVIDENCE (the folder that holds the evidence folders). Chrome is what
// CHROME names (tools/chrome_gpu.sh for the graphics card), in a place taken through tools/lib/browser_lock.mjs.

import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { acquireBrowser } from "./lib/browser_lock.mjs";
import { createServer } from "./serve.mjs";
import { lineOf } from "../src/replay/tissue_line.js";
import { clock } from "../src/replay/format.js";
import { DWELL } from "../src/replay/tissue_play.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const CASE = process.env.CASE || "wide";
const CASES = { wide: [1400, 900, "light"], phone: [390, 844, "dark"], reduced: [1400, 900, "light"], play: [1280, 720, "light"], sheet: [1280, 720, "light"], layout: [1280, 720, "light"] };
if (!CASES[CASE]) throw new Error(`no case ${CASE}: ${Object.keys(CASES).join(", ")}`);
const WIDTH = Number(process.env.WIDTH || CASES[CASE][0]), HEIGHT = Number(process.env.HEIGHT || CASES[CASE][1]), THEME = process.env.THEME || CASES[CASE][2];
const REDUCED = CASE === "reduced" || process.env.REDUCED === "1";
const NAME = process.env.NAME || `tissue-${CASE}`;
const OUT = path.resolve(process.argv[2] || path.join(ROOT, "out", "check-tissue"));
const EVIDENCE = process.env.EVIDENCE || "/mnt/workspaces/Cells";
const PART = "gap-junction-tissue-line", SHEET = "gap-junction-tissue-sheet", WHOLE = "gap-junction-linear-network";
// What the opening may fetch, and one arm (about 3 MB and 1 MB: the coordinator's budget, 18 November 2026).
const OPENING_BYTES = 3.2e6, ARM_BYTES = 1.1e6;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const lower = (text) => (text ? text.charAt(0).toLowerCase() + text.slice(1) : "");
const results = [];
const check = (name, ok, detail = "") => {
  results.push(Boolean(ok));
  console.log(`${ok ? "pass" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`);
};
const note = (text) => console.log(`note  ${text}`);

// ---------------------------------------------------------------- the runs, as the page's overlay and selection package them
const selection = JSON.parse(readFileSync(path.join(ROOT, "data", "replays", "selection.json"), "utf8"));
const OVERLAY = JSON.parse(readFileSync(path.join(ROOT, "data", "replays", "overlay.json"), "utf8"));
const folderOf = (part) => path.join(EVIDENCE, selection[part].evidence_folder, ...(selection[part].within || []));
const missing = [PART, SHEET].filter((part) => !existsSync(folderOf(part)));
if (missing.length) {
  note(`the tissue's runs are not on this machine (${missing.map(folderOf).join(", ")}): the check is skipped`);
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
// One run of the example's networks (its seven cells), so that the example and its card stand; then the line and the sheet.
adapt(["--experiment", WHOLE, "--run", "figure5-network-g1"]);
adapt(["--experiment", PART]);
adapt(["--experiment", SHEET]);
const indexFile = path.join(runs, "index.json");
const index = JSON.parse(readFileSync(indexFile, "utf8"));
// Which part the tab opens on is one field, the example's opens.part: the sheet case turns it in this check's own catalogue.
const OPENS = index.experiments.find((item) => item.id === WHOLE)?.opens?.part;
if (CASE === "sheet") {
  index.experiments.find((item) => item.id === WHOLE).opens.part = SHEET;
  writeFileSync(indexFile, JSON.stringify(index));
}
// What the page should show, from the data: each part's slots as the catalogue states them, the overlay's words, and
// each arm's criterion as the driver's file gives it.
const LINE = lineOf(index, PART), SHEETS = lineOf(index, SHEET);
const ENTRY = OVERLAY.experiments[PART], SHEET_ENTRY = OVERLAY.experiments[SHEET];
const stated = (line) => Object.fromEntries(line.runs.map((slot) => [slot.arm, JSON.parse(readFileSync(path.join(folderOf(line.id), slot.arm, "criterion.json"), "utf8"))]));
const STATED = { ...stated(LINE), ...stated(SHEETS) };
const ARMS = LINE.runs.map((slot) => slot.arm);
const criterion = STATED[ARMS[0]].criterion;
// A record to press on: the first where a line's cell is stated neither M nor E (the criterion's between).
const PRESS = (() => {
  for (const arm of ARMS) for (const [row, states] of STATED[arm].states.entries()) { const cell = states.findIndex((word) => word !== "M" && word !== "E"); if (cell >= 0) return { arm, cell, record: row, state: states[cell] }; }
  return { arm: ARMS[0], cell: 0, record: 0, state: STATED[ARMS[0]].states[0][0] };
})();
PRESS.time = STATED[PRESS.arm].times_s[PRESS.record];
PRESS.name = STATED[PRESS.arm].cells[PRESS.cell];
PRESS.end = LINE.runs.find((slot) => slot.arm === PRESS.arm).end;
const placeWords = (slot) => [slot.label, slot.where && /x2/.test(slot.where) ? slot.where : null].filter(Boolean).join(" · "); // a line's name on the picture and in the card
const SIDE = { M: "below", E: "above" }; // the criterion's words for a state, to hold a colour's side beside the driver's state
// The stated changes of the line's arms, record to record, as the driver's files give them.
const changesOf = (arms) => arms.flatMap((arm) => { const c = STATED[arm], out = []; for (let k = 1; k < c.states.length; k++) c.states[k].forEach((state, n) => { if (state !== c.states[k - 1][n]) out.push({ arm, time: c.times_s[k], cell: n, from: c.states[k - 1][n], to: state }); }); return out; });
note(`opens on ${OPENS}; the line: ${LINE.slots.map((slot) => slot.arm).join(", ")}; the sheet: ${SHEETS.slots.map((slot) => slot.arm).join(", ")}; a press at ${PRESS.arm} ${PRESS.name}, record ${PRESS.record} (${PRESS.state})`);

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
  // What the page fetched of the runs' files, by file: the bytes that came over the wire.
  const fetched = new Map(), urls = new Map();
  socket.onmessage = (event) => {
    const m = JSON.parse(event.data);
    if (m.method === "Network.responseReceived") urls.set(m.params.requestId, m.params.response.url);
    if (m.method === "Network.loadingFinished") { const url = urls.get(m.params.requestId); if (url && /\/runs\/[^/]+\.json$/.test(url)) fetched.set(path.basename(new URL(url).pathname), m.params.encodedDataLength); }
    const w = waiting.get(m.id); if (!w) return; waiting.delete(m.id); if (m.error) w.reject(new Error(m.error.message)); else w.resolve(m.result);
  };
  const send = (method, params = {}, sessionId) => new Promise((resolve, reject) => { const id = nextId++; waiting.set(id, { resolve, reject }); socket.send(JSON.stringify({ id, method, params, sessionId })); });
  const { targetId } = await send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
  const page = (method, params) => send(method, params, sessionId);
  await page("Runtime.enable");
  await page("Page.enable");
  await page("Network.enable");
  await page("Network.setCacheDisabled", { cacheDisabled: true });
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
  const shownPart = (part) => `Boolean(${L}?.partId === ${JSON.stringify(part)} && ${L}.runs?.length && ${L}.pieces && !${L}.loading)`;
  const networks = `Boolean(!${V}.state.part && ${L}?.run && ${L}.sheet && ${L}.run.id === ${L}.runId)`;
  const shot = async (name) => {
    await evaluate(`${V}.stage.invalidate()`);
    await sleep(1200);
    const { data } = await page("Page.captureScreenshot", { format: "png" });
    const file = path.join(OUT, "pictures", `${NAME}-${name}.png`);
    mkdirSync(path.dirname(file), { recursive: true });
    await writeFile(file, Buffer.from(data, "base64"));
    note(`wrote ${file}`);
  };
  /** What the picture shows now: its names, the card's and the legend's words, where each tissue stands, the clock. */
  const state = () => evaluate(`(() => {
    const v = ${V}, root = v.shadowRoot, lens = v.current, box = v.getBoundingClientRect();
    const words = (el) => { const lines = [...el.querySelectorAll(".tissue-line")].filter((line) => !line.hidden && getComputedStyle(line).visibility !== "hidden"); return lines.length ? lines.map((line) => line.textContent).join(" / ") : el.textContent; };
    const tags = (kind) => [...root.querySelectorAll(".label-" + kind)].filter((el) => !el.classList.contains("is-off")).map((el) => { const r = el.getBoundingClientRect(); return { text: words(el), x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2), top: Math.round(r.top), bottom: Math.round(r.bottom), left: Math.round(r.left), right: Math.round(r.right), inside: r.left >= box.left - 1 && r.right <= box.right + 1 && r.top >= box.top - 1 && r.bottom <= box.bottom + 1 }; });
    v.stage.camera.updateMatrixWorld();
    lens?.root?.updateMatrixWorld(true);
    const V3 = lens?.root?.position.constructor;
    const tissues = lens?.pieces ? [...lens.pieces.values()].filter((piece) => piece.item).map((piece) => { const xs = [], ys = []; for (const cell of [piece.sheet.cells[0], piece.sheet.cells[piece.sheet.cells.length - 1]]) { const p = v.stage.project(piece.group.localToWorld(new V3(cell.centre[0], piece.thick, cell.centre[1])), new V3()); xs.push(p.x); ys.push(p.y); } return { arm: piece.item.slot.arm, part: piece.item.group.id, left: Math.round(Math.min(...xs)), right: Math.round(Math.max(...xs)), top: Math.round(Math.min(...ys)), bottom: Math.round(Math.max(...ys)), cell: Math.round(piece.sheet.pitch * (v.stage.project(piece.group.localToWorld(new V3(1, 0, 0)), new V3()).x - v.stage.project(piece.group.localToWorld(new V3(0, 0, 0)), new V3()).x)) }; }) : [];
    const card = root.querySelector(".view");
    return {
      part: lens?.partId || null, tab: v.state.lens, groups: (lens?.groups || []).map((group) => group.id), arms: (lens?.runs || []).map((item) => item.slot.arm),
      heads: tags("tissue-head"), ends: tags("tissue-end"), refused: tags("tissue-refused"), ticks: tags("tissue-tick"), chosen: tags("tissue-state"), changes: tags("tissue-change"),
      caption: tags("tissue-caption"), group: tags("tissue-group"), over: tags("tissue-over"), door: tags("tissue-door"), sibling: root.querySelector(".tissue-sibling-block")?.textContent || "", divider: Boolean(lens?.bracket),
      says: [...root.querySelectorAll(".tissue-says li")].map((li) => li.textContent),
      slotsCard: [...root.querySelectorAll(".tissue-slot")].map((el) => [el.dataset.arm, el.querySelector("b")?.textContent, el.querySelector("span")?.textContent]),
      criterion: root.querySelector(".tissue-criterion")?.textContent || "",
      heading: [...root.querySelectorAll(".view .card-title")].map((el) => el.textContent).join(" | "), stamp: root.querySelector(".stamp")?.textContent || "",
      card: card?.textContent || "", legend: root.querySelector("cells-legend")?.textContent || "",
      own: (() => { if (!card) return ""; const copy = card.cloneNode(true); for (const el of copy.querySelectorAll(".experiments, #cells-experiment, .tissue-criterion, .eyebrow")) el.remove(); for (const el of copy.querySelectorAll("details")) if (/Sources and licences/.test(el.querySelector("summary")?.textContent || "")) el.remove(); return copy.textContent; })(),
      list: [...root.querySelectorAll(".view .exp-row")].map((b) => [b.textContent, b.getAttribute("aria-pressed")]),
      tissues, time: lens?.player?.time ?? null, playing: lens?.player?.playing ?? null, speed: lens?.player?.speed ?? null, scale: lens?.scale || null, axis: lens?.axisNow?.words || "",
      selected: v.state.selected, panel: root.querySelector("cells-panel")?.textContent || "", flight: Boolean(v.stage.rig.flight),
      chosenRing: (() => { const piece = lens?.selected && lens.pieces?.get(lens.selected.arm); return piece?.chosen ? { visible: piece.chosen.visible, cell: lens.selected.cell } : null; })(),
      errors: window.__pageErrors,
    };
  })()`);
  /**
   * The colours drawn on cells' tops at the record shown: the camera looks close at each cell (as close as the view lets
   * a visitor come), the frame is drawn, and the pixel at a point of the cell's top clear of its dots and of the beads'
   * lanes is read back, beside the scale's colour of the stated value. The camera goes back after.
   * [{ arm, cell, record, value, drawn, wanted, side }]
   */
  const drawn = (samples) => evaluate(`(() => {
    const v = ${V}, lens = v.current, stage = v.stage, gl = stage.renderer.getContext(), ratio = stage.renderer.getPixelRatio(), pixel = new Uint8Array(4), out = [];
    const V3 = lens.root.position.constructor, before = stage.rig.view();
    lens.root.updateMatrixWorld(true);
    for (const [arm, cell] of ${JSON.stringify(samples)}) {
      const piece = lens.pieces.get(arm);
      if (!piece?.item) continue;
      // Between two of its dots (they stand a third of a turn apart round its middle) and off the beads' lanes.
      const c = piece.sheet.cells[cell], r = c.radius * 0.62, turn = -Math.PI / 6;
      const point = piece.group.localToWorld(new V3(c.centre[0] + Math.cos(turn) * r, piece.thick, c.centre[1] + Math.sin(turn) * r));
      stage.rig.setView({ target: point.clone(), distance: lens.home.distance * 0.16, azimuth: lens.home.azimuth, polar: lens.home.polar });
      stage.draw();
      const p = stage.project(point, new V3());
      gl.readPixels(Math.round(p.x * ratio), Math.round((stage.height - p.y) * ratio), 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
      const record = piece.item.run.indexAt(lens.player.time), value = piece.item.record.at(record, piece.item.cells.columns[cell]), rgb = lens.breaks.colour(value);
      out.push({ arm, cell, record, value: Number(value.toFixed(3)), drawn: [...pixel.slice(0, 3)], wanted: rgb.map((x) => Math.round(x * 255)), side: lens.breaks.side(value) });
    }
    stage.rig.setView(before);
    stage.draw();
    return out;
  })()`);
  const close = (sample) => sample.drawn.every((c, k) => Math.abs(c - sample.wanted[k]) <= 3);
  const allClose = (colours, least) => colours.length >= least && colours.every(close);
  const lineSamples = ARMS.flatMap((arm) => [[arm, 0], [arm, 5], [arm, 12], [arm, 24]]);
  const forbidden = /replicat|reproduc|\bagree|\bmatch|modelled|qualified|simulated|Grodstein|preprint/i;
  const EXTENSION = SHEET_ENTRY.tissue.says[1];
  /** What came over the wire of the runs' files since the counter was cleared: in all, and each arm's (its run file and its parts). */
  const bytes = () => {
    const total = [...fetched.values()].reduce((sum, n) => sum + n, 0);
    const arms = {};
    for (const [file, n] of fetched) { const arm = file.replace(/\.json$/, "").split(".")[0]; arms[arm] = (arms[arm] || 0) + n; }
    return { total, arms, files: [...fetched.keys()] };
  };

  /**
   * The play watched whole from the start, at the speed it opens on (the stated changes): every frame, the changes named
   * on the picture, and each arm's beads drawn. Returns { seen: [{ at, time, names, beads }], total } (seconds of watching
   * the schedule gives). A shot is taken a third of the way in.
   */
  const watchPlay = async (name) => {
    await evaluate(`(() => { const v = ${V}, lens = v.current; lens.player.pause(); lens.player.seek(lens.player.start); window.__seen = []; const look = () => { const names = [...v.shadowRoot.querySelectorAll(".label-tissue-change")].filter((el) => !el.classList.contains("is-off")).map((el) => el.textContent); const beads = Object.fromEntries([...lens.pieces.values()].filter((piece) => piece.item).map((piece) => [piece.item.slot.arm, piece.stream ? (piece.stream.drawn?.beads || 0) + (piece.stream.drawn?.chevrons || 0) + (piece.stream.drawn?.streams || 0) : null])); window.__seen.push({ at: performance.now(), time: lens.player.time, names, beads }); if (lens.player.playing || window.__seen.length < 5) requestAnimationFrame(look); }; lens.player.play(); requestAnimationFrame(look); return true; })()`);
    const total = await evaluate(`${L}.schedule.total`);
    await sleep((total / 3) * 1000);
    await shot(`${name}-playing`);
    await until(`!${L}.player.playing`, Math.ceil((total + 30) * 4));
    return { seen: await evaluate(`window.__seen`), total };
  };
  /** How long each name stood on the picture, in seconds of watching. */
  const spansOf = (seen) => {
    const spans = new Map();
    for (let k = 1; k < seen.length; k++) for (const name of seen[k - 1].names) spans.set(name, (spans.get(name) || 0) + (seen[k].at - seen[k - 1].at) / 1000);
    return spans;
  };
  /** The words the picture names a record's changes by: a line's cell by its number, a sheet's cells of one kind together by their ids. */
  const changeWords = (arms) => {
    const out = new Set();
    for (const arm of arms) {
      const c = STATED[arm], lined = LINE.runs.some((slot) => slot.arm === arm);
      for (let k = 1; k < c.states.length; k++) {
        // A line's changes of one record are named together, cell by cell; a sheet's of one record and kind together.
        const groups = new Map(), each = [];
        c.states[k].forEach((state, n) => { if (state !== c.states[k - 1][n]) { each.push(`cell ${n + 1}: ${c.states[k - 1][n]} to ${state}`); const key = `${c.states[k - 1][n]}>${state}`; if (!groups.has(key)) groups.set(key, { from: c.states[k - 1][n], to: state, cells: [] }); groups.get(key).cells.push(n); } });
        if (lined && each.length) out.add(each.join("; "));
        if (!lined) for (const { from, to, cells } of groups.values()) out.add(cells.length === 1 ? `${c.cells[cells[0]]}: ${from} to ${to}` : `${cells.map((n) => c.cells[n]).join(", ")}: ${from} to ${to}`);
      }
    }
    return [...out];
  };
  /** The view's own work on a frame of the play, the labels' layout with it: the median and the most of 60 frames, in milliseconds (the page's budget is 8, shelves-frame's). */
  const frameCost = () => evaluate(`(() => { const v = ${V}, lens = v.current, times = []; lens.player.seek(lens.player.start); lens.player.play(); for (let i = 0; i < 60; i++) { const t = performance.now(); lens.update(1 / 60, 0, 1000 / 60); v.labels.layout(); times.push(performance.now() - t); } lens.player.pause(); times.sort((a, b) => a - b); return { median: Math.round(times[30] * 100) / 100, most: Math.round(times[59] * 100) / 100 }; })()`);

  // A fresh browser's first page on the card loses its context about five seconds in: it is a throwaway.
  await page("Page.navigate", { url: `${base}?lens=engine` });
  await sleep(7000);
  note(`case ${CASE}, ${WIDTH} by ${HEIGHT}, ${THEME}${REDUCED ? ", less motion" : ""}`);

  if (CASE === "wide") {
    fetched.clear();
    await page("Page.navigate", { url: `${base}?lens=experiments&still=1` });
    check("the Experiments tab opens on the tumour tissue's line, the part the example's entry names (opens.part)", OPENS === PART && (await until(shownPart(PART), 240)), OPENS);
    await sleep(1500);
    let s = await state();
    const got = bytes();
    note(`the opening fetched ${got.total.toLocaleString("en-US")} bytes of runs: ${JSON.stringify(got.arms)}`);
    check(`what the opening fetches of the runs stays under ${OPENING_BYTES / 1e6} MB, and each arm under ${ARM_BYTES / 1e6} MB: only the arms in view, and of each only what the picture draws`, got.total > 0 && got.total <= OPENING_BYTES && Object.values(got.arms).every((n) => n <= ARM_BYTES) && !got.files.some((file) => /\.(amount|junction-gate|junction-voltage-v|membrane-voltage-v)\.json$/.test(file)), JSON.stringify(got));
    check(`the line's ${LINE.runs.length} arms stand in D's order, under one clock`, JSON.stringify(s.arms) === JSON.stringify(ARMS) && s.tab === "experiments" && JSON.stringify(s.groups) === JSON.stringify([PART]), JSON.stringify(s.arms));
    const heads = s.heads.map((tag) => tag.text);
    check("each arm is named on the picture by its D and its place as the summary states it, top to bottom in D's order, inside the window", LINE.runs.every((slot, k) => heads[k] === placeWords(slot)) && s.heads.every((tag, k) => tag.inside && (k === 0 || tag.y > s.heads[k - 1].y)), JSON.stringify(heads));
    check("each arm's end states stand by it, in the note's words; an arm with no routes says so", LINE.runs.every((slot) => s.ends.some((tag) => tag.text.startsWith(slot.end))) && s.ends.some((tag) => tag.text.includes(ENTRY.tissue.no_routes.replace(/^D = 0: /, ""))), JSON.stringify(s.ends.map((tag) => tag.text)));
    check("each line stands inside the room the cards leave it, clear of the timeline, its cells large enough to see", s.tissues.every((t) => t.left > 290 && t.right <= WIDTH - 4 && t.top > 56 && t.bottom < HEIGHT - 90 && t.cell >= 14), JSON.stringify(s.tissues));
    check("the card says what the record lets it say, in its words", JSON.stringify(s.says) === JSON.stringify(ENTRY.tissue.says), JSON.stringify(s.says));
    check("the card lists the arms with each run's end", JSON.stringify(s.slotsCard.filter(([arm]) => ARMS.includes(arm)).map(([, label, end]) => [label, end])) === JSON.stringify(LINE.runs.map((slot) => [placeWords(slot), slot.end])), JSON.stringify(s.slotsCard));
    check("the criterion stands in the card in its own words, with its source, as the driver's file gives them", s.criterion.includes(`“${criterion.words}”`) && s.criterion.includes(criterion.source), s.criterion.slice(0, 120));
    // The sheet one press away: a small door on the picture, and the card's block with its caption in full over its door.
    check("the sheet is one press away: a small door on the picture, in sight, and the card's block with the sheet's caption in full", s.door.length === 1 && s.door[0].inside && s.door[0].text === SHEETS.short && s.caption.length === 0 && s.sibling.includes(SHEET_ENTRY.tissue.caption), JSON.stringify([s.door, s.sibling.slice(0, 80)]));
    const own = [s.own, s.legend, ...[...s.heads, ...s.ends, ...s.ticks, ...s.caption, ...s.door].map((tag) => tag.text)].join(" ").split(EXTENSION).join(" ");
    const beyond = ENTRY.tissue.says.filter((line) => /BITSEY|logged/.test(line)).reduce((text, line) => text.replace(line, ""), own);
    const judging = /replicat|reproduc|\bagree|\bmatch|modelled|qualified|simulated|Grodstein/i;
    check("nothing the tissue says (but the criterion's own words, the lead's one sentence on the logged value and one on BITSEY, and the sheet's sentence that it is not part of the replication) names the preprint, its authors or their code, or says replicated, agrees or matches", !forbidden.test(beyond) && !judging.test(own) && !/BITSEY|authors|logged/.test(beyond), (beyond.match(forbidden) || own.match(judging) || beyond.match(/BITSEY|authors|logged/) || [""])[0]);
    // The colours as drawn, at the first record and at the last.
    let colours = await drawn(lineSamples);
    check("each cell's colour as drawn is the scale's colour of the value the driver states there, at the first record", allClose(colours, 12), JSON.stringify(colours.filter((c) => !close(c))));
    const sides = colours.filter((c) => c.cell === 0).map((c) => ({ arm: c.arm, side: c.side, stated: STATED[c.arm].states[c.record]?.[0] }));
    check("each line's first tumor cell is drawn on the side of the scale its stated state names", sides.every((item) => !SIDE[item.stated] || item.side === SIDE[item.stated]), JSON.stringify(sides));
    await evaluate(`${L}.seek(${L}.clock.end)`);
    await sleep(800);
    const last = await drawn(lineSamples);
    check("and at the last record", allClose(last, 12) && last.some((c, k) => c.wanted.join() !== colours[k]?.wanted.join()), JSON.stringify(last.filter((c) => !close(c))));
    await evaluate(`${L}.seek(0)`);
    await shot("line");
    // A real press on a map, at a cell and record where the driver states a cell between its two states.
    const target = await evaluate(`(() => { const v = ${V}, lens = v.current, piece = lens.pieces.get(${JSON.stringify(PRESS.arm)}), V3 = lens.root.position.constructor; lens.root.updateMatrixWorld(true); const band = piece.bands[${PRESS.record}]; const local = new V3(((${PRESS.cell} + 0.5) / piece.item.cells.count) * piece.mapWidth, 0, ((band.from + band.to) / 2) * piece.mapDepth); const p = v.stage.project(piece.board.localToWorld(local), new V3()); return { x: p.x, y: p.y, time: piece.item.run.t[${PRESS.record}], tall: (band.to - band.from) }; })()`);
    await click(target.x, target.y, 1600);
    s = await state();
    check(`a real press on a map opens that cell and moves the clock to the record pressed (${PRESS.arm}, ${PRESS.name}, ${clock(PRESS.time)})`, s.selected === `tissue:${PRESS.arm}:${PRESS.cell}` && Math.abs(s.time - target.time) < 1e-6, JSON.stringify([s.selected, s.time, target]));
    const said = new RegExp(`State there, as the driver states it\\s*${PRESS.state}`);
    check(`its panel gives its value and its state as the driver states it (${PRESS.state} there), and the note's end line`, said.test(s.panel) && s.panel.includes(`miR200 minus Zeb mRNA at ${clock(PRESS.time)}`) && s.panel.includes(PRESS.end), s.panel.slice(0, 260));
    check("the pressed cell is told apart on the picture: ringed, and named with the driver's state", s.chosenRing?.visible && s.chosenRing.cell === PRESS.cell && s.chosen.length === 1 && s.chosen[0].text === `${PRESS.name} · ${PRESS.state}`, JSON.stringify([s.chosenRing, s.chosen]));
    await shot("pressed");
    // The timeline's next change: the clock goes to the first stated change, which is named over its cell.
    await evaluate(`${V}.select(null)`);
    await evaluate(`${L}.seek(0)`);
    await sleep(500);
    const first = changesOf(ARMS).sort((a, b) => a.time - b.time)[0];
    const next = await placeOf(`root.querySelector('cells-timeline .tl-step[data-step="next"]')`);
    if (next) await click(next.x, next.y, 1200);
    s = await state();
    check(`a real press on the timeline's next change moves the clock to the first stated change, named over its cell (${first ? `cell ${first.cell + 1}: ${first.from} to ${first.to}, ${clock(first.time)}` : "none"})`, Boolean(next) && first && Math.abs(s.time - first.time) < 1e-3 && s.changes.some((tag) => tag.text === `cell ${first.cell + 1}: ${first.from} to ${first.to}`), JSON.stringify([s.time, s.changes.map((tag) => tag.text)]));
    // The even time scale, chosen on the card.
    await evaluate(`(() => { const select = ${V}.shadowRoot.querySelector('.view select[data-choice="time-scale"]'); select.value = "even"; select.dispatchEvent(new Event("change")); })()`);
    await sleep(1200);
    s = await state();
    check("the card's time scale draws time down the maps evenly, and the legend says so", s.scale === "even" && /on an even scale/.test(s.axis) && s.ticks.some((tag) => /^[1-5] h$/.test(tag.text)), JSON.stringify([s.scale, s.ticks.map((tag) => tag.text)]));
    // A run's details, from its line in the card's picks.
    const details = await placeOf(`[...root.querySelectorAll('.tissue-slot[data-arm="${ARMS[0]}"] .tissue-open')][0]`);
    if (details) await click(details.x, details.y, 1200);
    s = await state();
    check("a real press on an arm's \"Run details\" opens that run's panel, with how its replay was made", Boolean(details) && s.selected === `run:${LINE.runs[0].id}` && s.panel.includes(ARMS[0]) && /How this replay was (derived|made)/.test(s.panel), JSON.stringify([s.selected, s.panel.slice(0, 160)]));
    await evaluate(`${V}.select(null)`);
    await sleep(600);
    // The list's pressed row is the example's: with the line shown it says so, in the line's own short name.
    const lineRow = await evaluate(`${V}.shadowRoot.querySelector('.exp-row[aria-pressed="true"]')?.textContent || null`);
    check("with the line shown, the list's pressed row (the example's) carries the line's own short name under the example's", Boolean(lineRow) && lineRow.includes(ENTRY.short), JSON.stringify(lineRow));
    // The way to the networks: the card's own button; the seven-cell network is shown.
    const back = await placeOf(`root.querySelector(".view .tissue-back:not(.tissue-sibling)")`);
    if (back) await click(back.x, back.y, 1500);
    const atNetworks = await until(networks, 240);
    const net = await evaluate(`({ run: ${L}.runId || null, cells: ${L}.sheet?.cells.length ?? 0 })`).catch(() => ({}));
    check("a real press on the card's button shows the example's networks: the seven-cell network", Boolean(back) && atNetworks && net.run === `${WHOLE}--figure5-network-g1` && net.cells === 7, JSON.stringify(net));
    const netRow = await evaluate(`[...${V}.shadowRoot.querySelectorAll(".exp-within")].length`);
    check("with the networks shown, the list's rows are as they were: no part named under the example's", netRow === 0, String(netRow));
    // And back to the tissue by the example's card, then to the sheet by a real press on its door over the line.
    await page("Page.navigate", { url: `${base}?lens=experiments&still=1&part=${PART}` });
    await until(shownPart(PART), 240);
    await sleep(1500);
    fetched.clear();
    const sheetDoor = await evaluate(`(() => { const el = ${V}.shadowRoot.querySelector(".label-tissue-door .tissue-door-button"); if (!el) return null; const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
    if (sheetDoor) await click(sheetDoor.x, sheetDoor.y, 1500);
    check("a real press on the sheet's door over the line shows the sheet, with the line beside it", Boolean(sheetDoor) && (await until(shownPart(SHEET), 240)), JSON.stringify(sheetDoor));
    await sleep(1500);
    s = await state();
    check("the sheet's caption stands over it in full, in sight: \"Development work, not judged.\" and the extension sentence", s.caption.length === 1 && s.caption[0].text === SHEET_ENTRY.tissue.caption && s.caption[0].inside, JSON.stringify(s.caption));
    note(`the sheet fetched ${bytes().total.toLocaleString("en-US")} bytes more (the line's arms in view were in already)`);
    await shot("sheet");
    // The page's theme turns dark while the line is shown: the cells take the dark tokens.
    await page("Page.navigate", { url: `${base}?lens=experiments&still=1` });
    await until(shownPart(PART), 240);
    await sleep(1200);
    colours = await drawn(lineSamples);
    await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "dark" }] });
    await sleep(1500);
    const dark = await drawn(lineSamples);
    check("the theme turned dark: the colours as drawn are the scale's colours in the dark tokens", allClose(dark, 12) && dark.every((c, k) => c.wanted.join() !== colours[k]?.wanted.join()), JSON.stringify(dark.filter((c) => !close(c)).slice(0, 3)));
    await shot("dark");
    await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "light" }] });
    // The window turns narrow: the lines stand inside it.
    await page("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
    await sleep(2000);
    s = await state();
    check("the window turned narrow: every line stands inside it", s.tissues.every((t) => t.left >= 0 && t.right <= 390), JSON.stringify(s.tissues));
    await page("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: HEIGHT, deviceScaleFactor: 1, mobile: false });
    await sleep(1500);
    // The bar's stamp never drops onto the pictures' heads, at a laptop's widths, on the line and on the networks.
    for (const [width, height] of [[1280, 720], [1024, 768], [800, 760]]) {
      await page("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: false });
      await sleep(1800);
      const bar = await evaluate(`(() => { const root = ${V}.shadowRoot, box = (el) => { const r = el?.getBoundingClientRect(); return r && r.width ? [r.left, r.top, r.right, r.bottom] : null; }; const stamp = root.querySelector(".stamp"), list = root.querySelector(".bar-end .pill-button"), s = box(stamp), b = box(root.querySelector(".bar")), heads = [...root.querySelectorAll(".label-tissue-head, .label-tissue-caption, .label-tissue-door")].map(box).filter(Boolean); return { stamp: s, words: s ? stamp.textContent : "", inRow: !s || (s[1] >= b[1] && s[3] <= b[3]), over: s ? heads.filter((h) => !(h[2] <= s[0] || h[0] >= s[2] || h[3] <= s[1] || h[1] >= s[3])).length : 0, heads: heads.length, list: Boolean(list) && list.getBoundingClientRect().right <= innerWidth && list.scrollWidth <= list.clientWidth + 1, sideways: document.documentElement.scrollWidth > innerWidth + 1 }; })()`);
      // The part's standing in sight in full: the stamp's first words where they show, else on the picture.
      const seen = await evaluate(`(() => { const root = ${V}.shadowRoot, stamp = root.querySelector(".stamp"); let stampShows = false; if (stamp && stamp.getClientRects().length) { const text = document.createTreeWalker(stamp, NodeFilter.SHOW_TEXT).nextNode(); if (text && /^Development work, not judged/.test(text.data)) { const range = document.createRange(); range.setStart(text, 0); range.setEnd(text, 28); stampShows = range.getBoundingClientRect().right <= stamp.getBoundingClientRect().right - 1; } } const el = root.querySelector(".label-tissue-door .tissue-standing"), r = el?.getBoundingClientRect(); return { stampShows, picture: Boolean(r && r.width && r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight) && el.textContent === "Development work, not judged." }; })()`);
      check(`${width} by ${height}: "Development work, not judged" is in sight in full, in the bar's stamp or on the line's picture`, seen.stampShows || seen.picture, JSON.stringify(seen));
      check(`${width} by ${height}: the stamp stands in the bar's row, over none of the pictures' names, beginning with the part's standing, the List whole`, bar.inRow && bar.over === 0 && bar.heads > 0 && bar.list && !bar.sideways && (!bar.stamp || /^Development work, not judged/.test(bar.words)), JSON.stringify(bar));
    }
    // An address that names something of the networks' own view still opens them: a run, or a run to choose.
    const opensOn = [];
    for (const query of [`run=${WHOLE}--figure5-network-g1`, `select=run:${WHOLE}--figure5-network-g1`, `example=gard`]) {
      await page("Page.navigate", { url: `${base}?lens=experiments&still=1&${query}` });
      await sleep(2500);
      opensOn.push([query, await evaluate(`({ part: ${V}.state.part || null, example: ${V}.state.example || null, run: ${L}?.runId || null })`)]);
    }
    check("an address that names a run of the networks (run=, or select=run:) opens the networks, and example= its door, over the opening part", opensOn.every(([query, at]) => !at.part && (query.startsWith("example") ? at.example === "gard" : at.run === `${WHOLE}--figure5-network-g1`)), JSON.stringify(opensOn));
    await page("Page.navigate", { url: `${base}?lens=experiments&still=1&run=${WHOLE}--figure5-network-g1` });
    await until(networks, 240);
    await page("Emulation.setDeviceMetricsOverride", { width: 1280, height: 720, deviceScaleFactor: 1, mobile: false });
    await sleep(1800);
    const netBar = await evaluate(`(() => { const root = ${V}.shadowRoot, stamp = root.querySelector(".stamp"), bar = root.querySelector(".bar").getBoundingClientRect(), r = stamp.getBoundingClientRect(); return { words: stamp.textContent, inRow: r.top >= bar.top && r.bottom <= bar.bottom, lines: Math.round(r.height / parseFloat(getComputedStyle(stamp).lineHeight || "16")) }; })()`);
    check("1280 by 720, the networks: the stamp's engine revision is its first eight characters, and the stamp stays in the bar's row", /engine [0-9a-f]{8}(\s|$)/.test(netBar.words) && !/[0-9a-f]{9,}/.test(netBar.words) && netBar.inRow, JSON.stringify(netBar));
    s = await state();
    check("the page logged no error", !(s.errors || []).length, JSON.stringify(s.errors));
  } else if (CASE === "phone") {
    await page("Page.navigate", { url: `${base}?lens=experiments&still=1` });
    check("on a phone the tab opens on the tissue's line", await until(shownPart(PART), 240), "");
    await sleep(1500);
    let s = await state();
    check("on a phone the lines stand one above the other, inside the window, their cells large enough to see", s.tissues.length === LINE.runs.length && s.tissues.every((t, k) => t.left >= 0 && t.right <= WIDTH && (k === 0 || t.top > s.tissues[k - 1].bottom) && t.cell >= 10), JSON.stringify(s.tissues));
    check("on the picture the sheet's small door, inside the window", s.door.length === 1 && s.door[0].inside, JSON.stringify(s.door));
    // The bar's stamp is hidden and the card folded: the line's picture says its standing on the first screen, unpressed.
    const standing = await evaluate(`(() => { const root = ${V}.shadowRoot, el = root.querySelector(".label-tissue-door .tissue-standing"); if (!el) return null; const r = el.getBoundingClientRect(), at = root.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return { text: el.textContent, inside: r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight, clear: Boolean(at && (at === el || el.contains(at))), stamp: getComputedStyle(root.querySelector(".stamp")).display, open: ${V}.state.viewOpen }; })()`);
    check("on a phone the line's first screen says \"Development work, not judged.\" on the picture, in the window and under nothing, without a press", Boolean(standing) && standing.text === ENTRY.tissue.says[0] && standing.inside && standing.clear && !standing.open, JSON.stringify(standing));
    const colours = await drawn(lineSamples);
    check("the colours as drawn are the scale's colours of the stated values, in the dark page's tokens", allClose(colours, 8), JSON.stringify(colours.filter((c) => !close(c)).slice(0, 3)));
    await shot("line");
    const unfold = async () => {
      if (await evaluate(`${V}.state.viewOpen`)) return true;
      const fold = await placeOf(`root.querySelector(".view-toggle")`);
      if (fold) await click(fold.x, fold.y, 1000);
      return Boolean(fold);
    };
    await unfold();
    s = await state();
    check("a real press opens the card: the record's lines and the arms", JSON.stringify(s.says) === JSON.stringify(ENTRY.tissue.says) && s.slotsCard.length >= LINE.slots.length, JSON.stringify([s.says, s.slotsCard.length]));
    await shot("card");
    const back = await placeOf(`root.querySelector(".view .tissue-back:not(.tissue-sibling)")`);
    if (back) await click(back.x, back.y, 1500);
    check("and a real press on the card's button gives the tab to the networks", Boolean(back) && (await until(networks, 240)), "");
    await page("Page.navigate", { url: `${base}?lens=experiments&still=1&part=${SHEET}` });
    check("the address opens the sheet on a phone", await until(shownPart(SHEET), 240), "");
    await sleep(1500);
    s = await state();
    check("on a phone the sheet's caption stands in full inside the window, and every tissue inside its width", s.caption.length === 1 && s.caption[0].inside && s.caption[0].text === SHEET_ENTRY.tissue.caption && s.tissues.every((t) => t.left >= 0 && t.right <= WIDTH), JSON.stringify([s.caption, s.tissues]));
    await shot("sheet");
    check("the page logged no error", !(s.errors || []).length, JSON.stringify(s.errors));
  } else if (CASE === "reduced") {
    await page("Page.navigate", { url: `${base}?lens=experiments` });
    check("the tab opens on the tissue with less motion asked for", await until(shownPart(PART), 240), "");
    await sleep(3000);
    const s = await state();
    check("with less motion nothing plays: the clock stands at the first record, and the camera did not fly", s.playing === false && s.time === 0 && !s.flight, JSON.stringify([s.playing, s.time, s.flight]));
    const colours = await drawn(lineSamples);
    check("the cells are drawn at once in the scale's colours of the first record", allClose(colours, 12), JSON.stringify(colours.filter((c) => !close(c))));
    await shot("line");
    check("the page logged no error", !(s.errors || []).length, JSON.stringify(s.errors));
  } else if (CASE === "play") {
    await page("Page.navigate", { url: `${base}?lens=experiments` });
    check("the tab opens on the tissue, and a page that may move plays it, following the stated changes", (await until(shownPart(PART), 240)) && (await until(`${L}.player.playing`, 80)), "");
    const { seen, total } = await watchPlay("line");
    const spans = spansOf(seen);
    const named = changeWords(ARMS);
    const short = named.filter((name) => !((spans.get(name) || 0) >= DWELL - 0.3));
    const watched = (seen.at(-1).at - seen[0].at) / 1000;
    check(`the whole play takes about a minute or less (${Math.round(watched)} s of watching, the schedule ${Math.round(total)} s)`, watched <= 80 && Math.abs(watched - total) < 12, JSON.stringify([watched, total]));
    check(`each stated change of the line's arms is on the screen, named under its cell, for its stretch (${DWELL} s) or more: ${named.length} names`, named.length > 0 && short.length === 0, JSON.stringify(short.map((name) => [name, spans.get(name) || 0])));
    // The beads: each arm whose run declares routes draws what they carried at some time of the play; one with no routes, none.
    const most = {};
    for (const frame of seen) for (const [arm, beads] of Object.entries(frame.beads)) most[arm] = beads === null ? null : Math.max(most[arm] ?? 0, beads);
    const quiet = LINE.runs.filter((slot) => !JSON.parse(readFileSync(path.join(runs, `${slot.id}.json`), "utf8")).view.sets.some((set) => set.id === "passive_route")).map((slot) => slot.arm);
    check(`during the play the beads run on every arm whose run declares routes, and on none of the ${quiet.length} with no routes`, ARMS.every((arm) => (quiet.includes(arm) ? most[arm] === null : most[arm] > 0)), JSON.stringify(most));
    const cost = await frameCost();
    note(`the line's play: the view's work on a frame, labels with it: ${JSON.stringify(cost)} ms`);
    check("the view's own work on a frame of the play, the labels' layout with it, leaves room at 60 frames a second (a median under 8 ms)", cost.median < 8, JSON.stringify(cost));
    // At each mark the picture differs from the picture at the record before it.
    const marks = await evaluate(`${L}.marks.map((mark) => mark.time)`);
    const same = [];
    for (const time of marks) {
      const before = await evaluate(`(() => { const lens = ${L}, t = lens.clock.t, k = lens.clock.indexAt(${time}); return t[Math.max(0, k - 1)]; })()`);
      const picture = async (at) => { await evaluate(`${L}.player.pause(); ${L}.seek(${at}); ${V}.stage.draw(); true`); await sleep(300); return evaluate(`(() => { const v = ${V}, gl = v.stage.renderer.getContext(); v.stage.draw(); const w = gl.drawingBufferWidth, h = gl.drawingBufferHeight, px = new Uint8Array(w * h * 4); gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, px); let sum = 0; for (let i = 0; i < px.length; i += 7) sum = (sum * 31 + px[i]) % 2147483647; return sum; })()`); };
      if ((await picture(before)) === (await picture(time))) same.push(time);
    }
    check(`at each of the ${marks.length} marks the picture differs from the picture at the record before it`, marks.length > 0 && same.length === 0, JSON.stringify(same));
    const s = await state();
    check("the page logged no error", !(s.errors || []).length, JSON.stringify(s.errors));
  } else if (CASE === "layout") {
    /** Where the names and the cells stand now, and whether any two names meet or a name lies on a cell. */
    const crowd = () => evaluate(`(() => {
      const v = ${V}, root = v.shadowRoot, lens = v.current, box = v.getBoundingClientRect(), V3 = lens.root.position.constructor;
      lens.root.updateMatrixWorld(true);
      v.stage.camera.updateMatrixWorld();
      const labels = [...root.querySelectorAll(".label")].filter((el) => !el.classList.contains("is-off") && !el.hidden && el.getClientRects().length).map((el) => { const r = el.getBoundingClientRect(); return { kind: [...el.classList].find((c) => c.startsWith("label-")) || "", text: el.textContent.slice(0, 48), l: r.left, t: r.top, r: r.right, b: r.bottom }; });
      const cells = [], sizes = { line: Infinity, sheet: Infinity, sheets: 0 };
      for (const piece of lens.pieces?.values() || []) {
        if (!piece.item) continue;
        const project = (x, z) => v.stage.project(piece.group.localToWorld(new V3(x, piece.thick, z)), new V3());
        for (const cell of piece.sheet.cells) {
          const c = project(cell.centre[0], cell.centre[1]), e = project(cell.centre[0] + cell.radius, cell.centre[1]);
          const radius = Math.abs(e.x - c.x);
          cells.push({ l: c.x - radius, t: c.y - radius, r: c.x + radius, b: c.y + radius });
          if (piece.item.lined && piece.item.group.role === "main") sizes.line = Math.min(sizes.line, 2 * radius);
        }
        if (!piece.item.lined) {
          sizes.sheets++;
          sizes.sheet = Math.min(sizes.sheet, Math.abs(project(piece.sheet.extent, 0).x - project(-piece.sheet.extent, 0).x));
        }
      }
      const meet = (a, b) => a.l < b.r - 1 && b.l < a.r - 1 && a.t < b.b - 1 && b.t < a.b - 1;
      const pairs = [];
      for (let i = 0; i < labels.length; i++) for (let j = i + 1; j < labels.length; j++) if (meet(labels[i], labels[j])) pairs.push([labels[i].text, labels[j].text]);
      const onCells = labels.filter((label) => !/tissue-change|tissue-state/.test(label.kind) && cells.some((cell) => meet(label, cell))).map((label) => label.text);
      const outside = labels.filter((label) => label.l < box.left - 1 || label.r > box.right + 1 || label.t < box.top - 1 || label.b > box.bottom + 1).map((label) => label.text);
      return { labels: labels.length, changes: labels.filter((label) => /tissue-change/.test(label.kind)).length, pairs: pairs.slice(0, 4), onCells: onCells.slice(0, 4), outside: outside.slice(0, 4), sizes: { line: Math.round(sizes.line), sheet: Math.round(sizes.sheet), sheets: sizes.sheets } };
    })()`);
    const firstChange = changesOf(ARMS).sort((a, b) => a.time - b.time)[0];
    const sheetChange = changesOf(SHEETS.runs.map((slot) => slot.arm).filter((arm) => (SHEET_ENTRY.tissue.front || []).includes(arm))).sort((a, b) => a.time - b.time)[0];
    const states = [
      ["the line", `lens=experiments&still=1`, null],
      ["the line at a change", `lens=experiments&still=1&time=${firstChange.time}`, null],
      ["a pressed cell", `lens=experiments&still=1&time=${PRESS.time}&select=tissue:${PRESS.arm}:${PRESS.cell}`, null],
      ["the sheet", `lens=experiments&still=1&part=${SHEET}`, null],
      ["the sheet at a change", `lens=experiments&still=1&part=${SHEET}&time=${sheetChange.time}`, null],
      ["the sheet with every arm", `lens=experiments&still=1&part=${SHEET}`, "all"],
      ["playing at a change", `lens=experiments`, "play"],
    ];
    for (const [width, height] of [[1280, 720], [1024, 768], [1440, 900], [400, 860], [360, 780]]) {
      await page("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: width < 760 });
      for (const [name, query, then] of states) {
        await page("Page.navigate", { url: `${base}?${query}` });
        const part = query.includes(SHEET) ? SHEET : PART;
        await until(shownPart(part), 240);
        await sleep(1200);
        if (then === "all") {
          await evaluate(`(() => { const select = ${V}.shadowRoot.querySelector('.view select[data-choice="arms"]'); if (!select) return false; select.value = "all"; select.dispatchEvent(new Event("change")); return true; })()`);
          await until(`${L}.runs.length === ${SHEETS.runs.length + LINE.runs.length} && !${L}.loading`, 240);
          await sleep(1500);
        } else if (then === "play") {
          await evaluate(`(() => { const lens = ${L}; lens.player.pause(); lens.player.seek(${firstChange.time}); lens.player.play(); return true; })()`);
          await sleep(700);
        }
        const c = await crowd();
        const tag = `${width} by ${height}, ${name}`;
        check(`${tag}: no two names meet, none but a change's or a chosen cell's lies on a cell, all inside the window (${c.labels} names${c.changes ? `, ${c.changes} of changes` : ""})`, c.labels > 0 && !c.pairs.length && !c.onCells.length && !c.outside.length && (!/change/.test(name) || c.changes > 0), JSON.stringify(c));
        if (width === 1280 && name === "the line") check(`${tag}: a line's cell is drawn 28 px across or more (${c.sizes.line} px)`, c.sizes.line >= 28, JSON.stringify(c.sizes));
        if (width === 1440 && name === "the line") check(`${tag}: a line's cell is drawn 36 px across or more (${c.sizes.line} px)`, c.sizes.line >= 36, JSON.stringify(c.sizes));
        if (width === 1280 && name === "the sheet") check(`${tag}: each of the ${c.sizes.sheets} sheets is 200 px across or more (${c.sizes.sheet} px)`, c.sizes.sheets === 3 && c.sizes.sheet >= 200, JSON.stringify(c.sizes));
        if (width === 1280 && name === "the sheet with every arm") check(`${tag}: each of the ${c.sizes.sheets} sheets is 130 px across or more (${c.sizes.sheet} px)`, c.sizes.sheets === 6 && c.sizes.sheet >= 130, JSON.stringify(c.sizes));
        if ((width === 1280 || width === 360) && /line$|sheet$|every arm|pressed/.test(name)) await shot(`${width}-${name.replace(/[^a-z]+/gi, "-")}`);
      }
    }
    const s = await state();
    check("the page logged no error", !(s.errors || []).length, JSON.stringify(s.errors));
  } else if (CASE === "sheet") {
    fetched.clear();
    await page("Page.navigate", { url: `${base}?lens=experiments&still=1` });
    check("with the switch turned to the sheet (the example's opens.part, in this check's catalogue), the tab opens on the sheet", await until(shownPart(SHEET), 240), "");
    await sleep(1800);
    let s = await state();
    const got = bytes();
    note(`the opening fetched ${got.total.toLocaleString("en-US")} bytes of runs: ${JSON.stringify(got.arms)}`);
    check(`what the sheet's opening fetches of the runs stays under ${OPENING_BYTES / 1e6} MB, each arm under ${ARM_BYTES / 1e6} MB`, got.total > 0 && got.total <= OPENING_BYTES && Object.values(got.arms).every((n) => n <= ARM_BYTES), JSON.stringify(got));
    // 1. The extension sentence on the first screen, in full, beside "Development work, not judged."
    check("1. the extension sentence stands on the first screen in full, beside \"Development work, not judged.\", over the sheet, not behind a fold or a press", s.caption.length === 1 && s.caption[0].text === `Development work, not judged. ${EXTENSION}` && s.caption[0].inside && s.caption[0].top >= 56 && s.tissues.filter((t) => t.part === SHEET).every((t) => t.top > s.caption[0].bottom), JSON.stringify(s.caption));
    // 2. The sheet's own bracket, in the note's words; x2 named as the line's wherever a place is.
    const bracket = SHEET_ENTRY.tissue.bracket;
    check("2. the sheet shows its own observed bracket in the note's words, at a dashed line between the two arms it lies between", s.divider && s.over.length === 1 && s.over[0].inside && s.over[0].text.includes(lower(bracket.says)) && s.says.includes(SHEET_ENTRY.tissue.says[2]), JSON.stringify([s.divider, s.over]));
    const places = s.heads.filter((tag) => /^x2/.test(tag.text));
    check("2. over the sheets, once, x2 is named as the line's threshold, and each sheet is named by its place (\"x2/4\")", places.length >= 1 && s.over[0]?.text.includes(SHEET_ENTRY.tissue.place_says) && s.slotsCard.filter(([arm]) => SHEETS.runs.some((slot) => slot.arm === arm)).length === SHEETS.slots.length, JSON.stringify([places.map((tag) => tag.text), s.over]));
    // 3. The line beside it, labelled as the record the threshold comes from.
    const lineTissues = s.tissues.filter((t) => t.part === PART);
    check("3. the line stays in sight beside the sheet, labelled as the record the threshold comes from (section 7.5)", lineTissues.length >= 1 && lineTissues.every((t) => t.top >= 56 && t.bottom <= HEIGHT - 90) && s.group.length === 1 && s.group[0].text === SHEET_ENTRY.tissue.beside.says && s.group[0].inside, JSON.stringify([lineTissues, s.group]));
    // 4. No heading or caption reads the sheet as the preprint's experiment.
    const words = [s.heading, s.stamp, ...[...s.heads, ...s.caption, ...s.group, ...s.over, ...s.ends].map((tag) => tag.text)].join(" ");
    // 4. The list's pressed row is the example's (its name, with the preprint's authors): it carries the sheet's own short
    // name under it, so that it reads as the example and, within it, the sheet, not as the sheet's attribution.
    const sheetRow = await evaluate(`${V}.shadowRoot.querySelector('.exp-row[aria-pressed="true"]')?.textContent || null`);
    check("4. with the sheet shown, the list's pressed row (the example's, with its authors) carries the sheet's own short name under it", Boolean(sheetRow) && sheetRow.includes(SHEET_ENTRY.short), JSON.stringify(sheetRow));
    check("4. no heading or caption reads the sheet as the preprint's experiment: it is Cells' extension", /Cells' extension/.test(s.heading + s.stamp) && !/Grodstein|Levin|preprint|after .* \(2026\)/i.test(words), words.slice(0, 300));
    check("the sheet's arms in view stand inside the room, their cells large enough to see", s.tissues.filter((t) => t.part === SHEET).every((t) => t.left > 290 && t.right <= WIDTH - 4 && t.bottom < HEIGHT - 90 && t.cell >= 10), JSON.stringify(s.tissues));
    await shot("sheet");
    // The play: past the sheets' 2,000 s each says its record ended, and shows its last record.
    await evaluate(`${L}.seek(${L}.clock.end)`);
    await sleep(1000);
    s = await state();
    check("past the sheets' end the words over them say, once, that each shows its last record, its run's record ending at 2,000 s", s.over.length === 1 && /Past 33 min 20 s each sheet shows its last record/.test(s.over[0].text) && s.over[0].inside, JSON.stringify(s.over));
    // The sheet's own play: each stated change named on the picture for its stretch; the beads on every arm with routes.
    const sheetArms = (await evaluate(`${L}.runs.map((item) => item.slot.arm)`));
    const { seen, total } = await watchPlay("sheet");
    const spans = spansOf(seen);
    const named = changeWords(sheetArms);
    const short = named.filter((name) => !((spans.get(name) || 0) >= DWELL - 0.3));
    note(`the sheet's play: ${named.length} names, ${Math.round(total)} s of watching; the sheets' changes: ${JSON.stringify(sheetArms.filter((arm) => SHEETS.runs.some((slot) => slot.arm === arm)).map((arm) => [arm, changeWords([arm]).length]))}`);
    check(`the sheet's play takes about a minute or less, and each stated change in view is named on the picture for its stretch (${DWELL} s) or more: ${named.length} names, the cells of a record and kind together`, total <= 80 && named.length > 0 && short.length === 0, JSON.stringify(short.map((name) => [name, spans.get(name) || 0])));
    const most = {};
    for (const frame of seen) for (const [arm, beads] of Object.entries(frame.beads)) most[arm] = beads === null ? null : Math.max(most[arm] ?? 0, beads);
    check("during the sheet's play the beads run on every arm in view", sheetArms.every((arm) => most[arm] > 0), JSON.stringify(most));
    const cost = await frameCost();
    note(`the sheet's play: the view's work on a frame, labels with it: ${JSON.stringify(cost)} ms`);
    check("the view's own work on a frame of the sheet's play, the labels' layout with it, leaves room at 60 frames a second (a median under 8 ms)", cost.median < 8, JSON.stringify(cost));
    // Every arm in view, chosen on the card: the six sheets and the line's four, under one clock; D = 0 says it has no
    // routes; the bracket stands between the two rows its arms are in.
    await evaluate(`${L}.player.pause(); ${L}.seek(0); true`);
    fetched.clear();
    await evaluate(`(() => { const select = ${V}.shadowRoot.querySelector('.view select[data-choice="arms"]'); select.value = "all"; select.dispatchEvent(new Event("change")); return true; })()`);
    await until(`${L}.runs.length === ${SHEETS.runs.length + LINE.runs.length} && !${L}.loading`, 240);
    await sleep(2000);
    s = await state();
    note(`every arm fetched ${bytes().total.toLocaleString("en-US")} bytes more`);
    const zero = SHEETS.runs.find((slot) => slot.value === 0);
    check(`"All" on the card brings the ${SHEETS.runs.length} sheets into view, three to a row, the line folded away (the card opens it)`, JSON.stringify(s.tissues.map((t) => t.arm).sort()) === JSON.stringify(SHEETS.runs.map((slot) => slot.arm).sort()) && s.group.length === 0, JSON.stringify(s.tissues.map((t) => t.arm)));
    check("the sheet with D = 0 says under it, with its end words, that it declares no routes", Boolean(zero) && s.ends.some((tag) => tag.text.includes(zero.end) && tag.text.includes(SHEET_ENTRY.tissue.no_routes.replace(/^D = 0: /, ""))), JSON.stringify(s.ends.map((tag) => tag.text)));
    check("the dashed line stands between the rows its two arms are in, and the words over the sheets say what it is", s.divider && s.over.length === 1 && s.over[0].text.includes(lower(bracket.says)), JSON.stringify(s.over));
    await shot("sheet-all");
    // On a phone, the same first screen.
    await page("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
    await page("Page.navigate", { url: `${base}?lens=experiments&still=1` });
    await until(shownPart(SHEET), 240);
    await sleep(2000);
    s = await state();
    check("on a phone too: the extension sentence in full inside the window, the bracket's words and the line's in sight", s.caption.length === 1 && s.caption[0].inside && s.caption[0].text === `Development work, not judged. ${EXTENSION}` && s.over.every((tag) => tag.inside) && s.group.length === 1 && s.group.every((tag) => tag.inside), JSON.stringify([s.caption, s.over, s.group]));
    // On a phone the folded chip names the sheet; opened, the list's chosen example says the sheet is shown within it.
    const chosen = await evaluate(`(() => { const select = ${V}.shadowRoot.querySelector("#cells-experiment"); return select ? [select.selectedOptions[0]?.textContent || "", select.parentElement.querySelector(".exp-within")?.textContent || ""] : null; })()`);
    check("on a phone the card's list (a list to choose from) says the sheet's own short name with the example chosen, and under it", Boolean(chosen) && chosen.every((words) => words.includes(SHEET_ENTRY.short)), JSON.stringify(chosen));
    await shot("sheet-phone");
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
