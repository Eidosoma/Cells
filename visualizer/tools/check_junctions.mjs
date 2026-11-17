#!/usr/bin/env node
// Checks the Experiments view's junction network and a sweep's chart with real pointer and key
// input, through the DevTools protocol, on a check-only scene: never on the published page.
//
//   network  the gap-junction fixture (two cells, one junction; the engine side's development
//            fixture, packaged here from GAP_FIXTURE when that folder is on this machine, else
//            skipped with a note) and the example sheet (19 cells, invented numbers): a real press
//            on the legend's Junctions row "Coupling" draws each junction as a line whose width is
//            its gate, the legend says the quantity and its scale, Transfers runs along the line,
//            and a chosen cell's panel gives each of its junctions' number.
//   sweep    a made-up experiment (tests/engine-views/sweep-made-up/summary.json over the run
//            fixture's synthetic world): the card's chart has a point for each arm, the arm shown
//            marked, an arm with no run said so; a real press on another arm shows its run, the
//            keys reach every arm and Enter shows one; the numbers stand in a table.
//
//   node tools/check_junctions.mjs [OUT_DIR]
//
// Set by the environment: CASE (network or sweep; network unless set), WIDTH and HEIGHT (1400 by
// 900), THEME (dark), REDUCED (1: the visitor asks for less motion), NAME (the pictures' prefix),
// GAP_FIXTURE (the fixture's viewer folder). The scene's runs are made in OUT_DIR/runs by the run
// fixture tool and the adapter, each time.

import { spawn, spawnSync } from "node:child_process";
import { copyFileSync, cpSync, mkdirSync, readFileSync, existsSync, writeFileSync } from "node:fs";
import { writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { acquireBrowser } from "./lib/browser_lock.mjs";
import { createServer } from "./serve.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const CASE = process.env.CASE || "network";
const WIDTH = Number(process.env.WIDTH || 1400), HEIGHT = Number(process.env.HEIGHT || 900), THEME = process.env.THEME || "light";
const NAME = process.env.NAME || `junctions-${CASE}`;
const OUT = path.resolve(process.argv[2] || path.join(ROOT, "out", "check-junctions"));
const GAP_FIXTURE = process.env.GAP_FIXTURE || "/mnt/workspaces/Cells/gap-junction-20261117/runs/fixture-02/viewer";
// The replication's runs (case levin): the page's own overlay and selection, read from the evidence folder's parent.
const EVIDENCE = process.env.EVIDENCE || "/mnt/workspaces/Cells";
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const results = [];
const check = (name, ok, detail = "") => {
  results.push(Boolean(ok));
  console.log(`${ok ? "pass" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`);
};
const note = (text) => console.log(`note  ${text}`);

// ---------------------------------------------------------------- the check-only scene's runs
const scene = path.join(OUT, `${NAME}-scene`), runs = path.join(scene, "runs"), fixtures = path.join(scene, "fixtures");
mkdirSync(runs, { recursive: true });
const python = (tool, args) => {
  const done = spawnSync("python3", [path.join(ROOT, "tools", tool), ...args], { encoding: "utf8" });
  if (done.status !== 0) throw new Error(`${tool} failed: ${done.stderr.slice(-600)}`);
  return done.stdout;
};
python("make_run_fixture.py", ["--out", fixtures]);
const overlay = JSON.parse(readFileSync(path.join(fixtures, "overlay.json"), "utf8"));
overlay.experiments["synthetic-world"].summary = "summary.json";
copyFileSync(path.join(ROOT, "tests", "engine-views", "sweep-made-up", "summary.json"), path.join(fixtures, "run-world", "summary.json"));
// The gap-junction fixture's entry: a development fixture, not shown on the page, named as such.
overlay.experiments["gap-junction-fixture"] = {
  adapter: "standard-history",
  development: true,
  label: "Gap-junction network (development fixture)",
  plain: "A fixture of the engine's development, for the viewer's own checks and never shown on the page: two cells that exchange one neutral species through one gap junction, each with a membrane to a held reservoir. A development run of the engine, not judged.",
  outcome: { judged: false, status: "Development fixture, no verdict", answer: null, text: "A fixture for the viewer's checks." },
  stops: { complete: { label: "Ran to its end" } },
};
// The same fixture with a made-up criterion beside it (cells.experiment_criterion@1, two thresholds): the colour is its values', the states are carried as given.
overlay.experiments["gap-junction-criterion"] = { ...overlay.experiments["gap-junction-fixture"], label: "Gap-junction network (development fixture, a made-up criterion)", opens: { record: ["stated.score"] } };
writeFileSync(path.join(scene, "overlay.json"), JSON.stringify(overlay));
python("adapt_run.py", ["--experiment", "synthetic-world", "--root", path.join(fixtures, "run-world"), "--run", "secreting", "--run", "viewed", "--run", "retiring", "--overlay", path.join(scene, "overlay.json"), "--out", runs]);
python("adapt_run.py", ["--experiment", "example-sheet", "--root", path.join(fixtures, "run-example"), "--run", "invented-numbers", "--overlay", path.join(scene, "overlay.json"), "--out", runs]);
const gap = existsSync(path.join(GAP_FIXTURE, "fixture-figure3-g1"));
if (gap) python("adapt_run.py", ["--experiment", "gap-junction-fixture", "--root", GAP_FIXTURE, "--run", "fixture-figure3-g1", "--overlay", path.join(scene, "overlay.json"), "--out", runs]);
if (gap && CASE === "network") {
  const criterion = path.join(fixtures, "gap-criterion"), arm = path.join(criterion, "fixture-figure3-g1");
  cpSync(path.join(GAP_FIXTURE, "fixture-figure3-g1"), arm, { recursive: true });
  const read = spawnSync("python3", ["-I", "-"], { encoding: "utf8", input: `import json, sys\nsys.path.insert(0, ${JSON.stringify(path.join(ROOT, "tools"))})\nimport adapt_run as a\nfrom pathlib import Path\nfolder = Path(${JSON.stringify(arm)})\nview = json.load(open(folder / "view.json"))\nbases = {b["id"]: b for b in view["time"]["bases"]}\nline = next(i for i in ("observation", "accepted") if i in bases and bases[i].get("files"))\n_, times, count = a.view_rows("arm", folder, bases[line], bases[line].get("array"))\nprint(json.dumps({"times": list(times), "cells": [c for c in next(s for s in view["sets"] if s["id"] == "cell")["ids"] if c is not None]}))\n` });
  const { times, cells } = JSON.parse(read.stdout);
  writeFileSync(path.join(arm, "criterion.json"), JSON.stringify({
    format: "cells.experiment_criterion@1",
    quantity: { id: "score", label: "A made-up score of each cell", unit: "1" },
    criterion: { threshold: 2, above: "epithelial", lower: { threshold: -2, below: "mesenchymal" }, between: "neither (X)", words: "A made-up criterion, for the viewer's checks.", source: "tools/check_junctions.mjs" },
    times_s: times,
    cells,
    values: times.map((_, row) => cells.map((_, k) => (k === 0 ? -3 + (6 * row) / Math.max(1, times.length - 1) : 0.5))),
    states: times.map(() => cells.map(() => "X")),
  }));
  writeFileSync(path.join(criterion, "index.json"), JSON.stringify({ packages: [{ arm: "fixture-figure3-g1", view: "written", sidecar: "criterion.json" }] }));
  python("adapt_run.py", ["--experiment", "gap-junction-criterion", "--root", criterion, "--run", "fixture-figure3-g1", "--overlay", path.join(scene, "overlay.json"), "--out", runs]);
}
else note(`the gap-junction fixture is not on this machine (${GAP_FIXTURE}): its part is skipped`);
// The replication, as the page packages it, in a scene of its own: its list is the page's (the listed experiment and GARD's door).
const levinRuns = path.join(OUT, `${NAME}-levin`, "runs");
let levin = false;
if (CASE === "levin") {
  mkdirSync(levinRuns, { recursive: true });
  try {
    python("adapt_run.py", ["--evidence", EVIDENCE, "--experiment", "gap-junction-linear-network", "--out", levinRuns]);
    levin = true;
  } catch (error) {
    note(`the replication's runs are not on this machine (${EVIDENCE}): the case is skipped (${String(error.message).slice(0, 160)})`);
  }
}
const index = JSON.parse(readFileSync(path.join(runs, "index.json"), "utf8"));
const runOf = (experiment, arm) => index.runs.find((row) => row.experiment === experiment && row.arm === arm)?.id;

// ---------------------------------------------------------------- the browser
const release = await acquireBrowser({ wait: 60 * 60 * 1000 });
const server = createServer({ offline: true, runs: CASE === "levin" ? levinRuns : runs, log: () => {} });
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
  if (process.env.REDUCED === "1") media.push({ name: "prefers-reduced-motion", value: "reduce" });
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
  const key = async (name, code = 0) => {
    await page("Input.dispatchKeyEvent", { type: name === "Enter" ? "keyDown" : "rawKeyDown", key: name, code: name, windowsVirtualKeyCode: code, ...(name === "Enter" ? { text: "\r" } : {}) });
    await page("Input.dispatchKeyEvent", { type: "keyUp", key: name, code: name, windowsVirtualKeyCode: code });
    await sleep(700);
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
  const open = async (query) => {
    await page("Page.navigate", { url: `${base}?lens=experiments&still=1&${query}` });
    return until(`Boolean(${V}?.current?.run && ${V}.current.sheet && ${V}.current.run.id === ${V}.current.runId)`, 240);
  };
  const shot = async (name) => {
    await evaluate(`${V}.stage.invalidate()`);
    await sleep(1200);
    const { data } = await page("Page.captureScreenshot", { format: "png" });
    const file = path.join(OUT, "pictures", `${NAME}-${name}.png`);
    mkdirSync(path.dirname(file), { recursive: true });
    await writeFile(file, Buffer.from(data, "base64"));
    note(`wrote ${file}`);
  };
  // A fresh browser's first page on the card loses its context about five seconds in: it is a throwaway.
  await page("Page.navigate", { url: `${base}?lens=engine` });
  await sleep(7000);
  note(`case ${CASE}, ${WIDTH} by ${HEIGHT}, ${THEME}${process.env.REDUCED === "1" ? ", less motion" : ""}`);

  if (CASE === "network") {
    // A real press on the legend's Junctions row: the option "Coupling".
    const pressCoupling = async () => {
      let at = await placeOf(`[...root.querySelectorAll('cells-legend .layer-row[data-channel="links"] button')].find((button) => button.textContent === "Coupling")`);
      if (!at) {
        const fold = await placeOf(`root.querySelector("cells-legend .legend-toggle")`);
        if (fold) await click(fold.x, fold.y);
        at = await placeOf(`[...root.querySelectorAll('cells-legend .layer-row[data-channel="links"] button')].find((button) => button.textContent === "Coupling")`);
      }
      if (at) await click(at.x, at.y, 1500);
      return Boolean(at);
    };
    const state = () => evaluate(`(() => { const lens = ${L}, held = lens.markOn("links"); return { on: lens.switch.on, mark: held?.layer.mark || null, counts: held?.mark.counts || null, full: held?.mark.full ?? null, keys: (lens.chrome().legend.layers?.keys || []).map((item) => item.text), lanes: lens.drawn.get("transfers")?.mark.drawn || null, errors: window.__pageErrors }; })()`);
    for (const [label, id, lines] of [["the gap-junction fixture", gap ? runOf("gap-junction-fixture", "fixture-figure3-g1") : null, 1], ["the example sheet", runOf("example-sheet", "invented-numbers"), null]]) {
      if (!id) continue;
      check(`${label} opens`, await open(`run=${id}&time=${label.includes("fixture") ? 30 : 6}`));
      check(`a real press on Junctions: Coupling switches the network on`, await pressCoupling());
      await until(`${L}.markOn("links")?.layer.mark === "network"`);
      let s = await state();
      const drawn = (s.counts?.open || 0) + (s.counts?.shut || 0);
      check(`${label}: each junction is a line between its two cells${lines ? `: ${lines} here` : ""}`, s.mark === "network" && (lines ? drawn === lines : drawn > 10), JSON.stringify(s.counts));
      check(`${label}: the legend says what the line's width is, and its scale`, s.keys.some((text) => /^A line joins the two cells of each junction; its width is the junction gate: full width fully open \(1\), a hairline shut \(0\)$/.test(text)) && s.full === 1, JSON.stringify(s.keys.slice(0, 3)));
      // Transfers on: what crosses runs along the same line.
      const transfers = await placeOf(`[...root.querySelectorAll('cells-legend .layer-row[data-channel="motion"] button')].find((button) => button.textContent === "Transfers")`);
      if (transfers) await click(transfers.x, transfers.y, 1500);
      await until(`Boolean(${L}.drawn.get("transfers"))`);
      s = await state();
      check(`${label}: Transfers runs along the junctions' lines, the network still drawn`, s.on.includes("transfers") && s.on.includes("junction-coupling") && s.lanes?.streams >= 1, JSON.stringify([s.on, s.lanes]));
      // A chosen cell's panel gives each of its junctions' number.
      await evaluate(`${V}.select("cell:0")`);
      await sleep(1200);
      const panel = await evaluate(`${V}.shadowRoot.querySelector("cells-panel")?.textContent || ""`);
      check(`${label}: the chosen cell's panel gives each of its junctions' number`, /On its junctions at/.test(panel) && /junction gate: 1(\.0+)?/.test(panel), panel.slice(0, 200));
      await shot(label.includes("fixture") ? "fixture" : "sheet");
      check(`${label}: the page logged no error`, !(s.errors || []).length, JSON.stringify(s.errors));
    }
    // A made-up criterion with two thresholds beside the fixture: the cells coloured by its values, both thresholds ticked on the
    // scale with the three words as given, its words and source under the scale, and a chosen cell's state as stated.
    const scored = gap ? runOf("gap-junction-criterion", "fixture-figure3-g1") : null;
    if (scored) {
      check("the fixture with a made-up criterion opens", await open(`run=${scored}&time=30`));
      await until(`${L}.switch.holder("colour") === "stated-score-tint"`, 60);
      const c = await evaluate(`(() => { const lens = ${L}, legend = lens.chrome().legend, colour = lens.markOn("colour")?.mark; return { holder: lens.switch.holder("colour"), marks: (legend.scale?.marks || []).map((mark) => mark.text), said: legend.scale?.said || "", offered: lens.offers.filter((item) => item.ok).map((item) => item.layer.id), shades: colour ? [0, 1].map((k) => lens.surface ? [...lens.surface.geometry.attributes.color.array.slice(lens.sheet.cells[k].start * 3, lens.sheet.cells[k].start * 3 + 3)].map((v) => v.toFixed(3)).join(",") : null) : null }; })()`);
      check("the cells are coloured by the criterion's values, and its states colour nothing", c.holder === "stated-score-tint" && !c.offered.some((id) => id.startsWith("stated-score-state")) && c.shades?.[0] !== c.shades?.[1], JSON.stringify([c.holder, c.offered, c.shades]));
      check("both thresholds are ticked on the scale with the three words as given", JSON.stringify(c.marks) === JSON.stringify(["−2.0: mesenchymal below, neither (X) between", "2.0: epithelial above"]), JSON.stringify(c.marks));
      check("under the scale: the experiment's own quantity, and its criterion in its own words with its source", /experiment's own quantity, stated by its driver beside the run \(criterion\.json\)/.test(c.said) && /“A made-up criterion, for the viewer's checks\.” \(tools\/check_junctions\.mjs\)/.test(c.said), c.said);
      await evaluate(`${V}.select("cell:0")`);
      await sleep(1200);
      const panel = await evaluate(`${V}.shadowRoot.querySelector("cells-panel")?.textContent || ""`);
      check("a chosen cell's panel gives its state as the driver states it", /state X/.test(panel), panel.slice(0, 240));
      await shot("criterion");
    }
  } else if (CASE === "levin" && levin) {
    const R = "gap-junction-linear-network";
    const state = () => evaluate(`(async () => { await new Promise((r) => setTimeout(r, 1500)); const v = ${V}, lens = v.current, legend = lens.chrome().legend; return { unit: legend.scale?.unit ?? null, said: legend.scale?.said || "", units: v.shadowRoot.querySelector(".run-units")?.textContent || null, run: lens.runId, cells: lens.sheet?.cells.length ?? null, error: lens.error, colour: lens.switch.holder("colour"), on: lens.switch.on, links: lens.markOn("links")?.mark.counts || null, note: lens.scaleInfo?.()?.note || null, list: v.shadowRoot.querySelector("#cells-experiment") ? [...v.shadowRoot.querySelector("#cells-experiment").options].map((o) => o.textContent) : [...v.shadowRoot.querySelectorAll(".exp-row")].map((b) => b.textContent), sweep: v.shadowRoot.querySelector(".sweep .seg-label")?.textContent || null, shown: [...v.shadowRoot.querySelectorAll(".sweep-arm")].filter((b) => b.getAttribute("aria-pressed") === "true").map((b) => b.dataset.arm), errors: window.__pageErrors }; })()`);
    // The view opens on the listed experiment, its list the two examples.
    await page("Page.navigate", { url: `${base}?lens=experiments&still=1` });
    await until(`Boolean(${V}?.current?.run && ${V}.current.sheet)`, 240);
    let s = await state();
    check("the Experiments view opens on the replication, and its list is the two examples: the replication and GARD", s.run?.startsWith(`${R}--`) && s.list.length === 2 && /^(Development run: )?Gap-junction networks of a linear model/.test(s.list[0]) && /GARD/.test(s.list[1]), JSON.stringify([s.run, s.list]));
    // Each arm opens on the quantity the experiment's driver states beside it (concentration.json), in its own unit, with Coupling on; else on the amount.
    const index = JSON.parse(readFileSync(path.join(levinRuns, "index.json"), "utf8"));
    const stated = (arm) => /"stated\.concentration"/.test(readFileSync(path.join(levinRuns, `${R}--${arm}.json`), "utf8"));
    for (const [arm, cells, lines, label, unit] of [["figure5-network-g1", 7, 6, "Figure 5a's seven cells", "mM"], ["figure8-chain10-held0.5", 10, 9, "a chain of ten", "mM"], ["aw-figure3-g1", 2, 1, "the two-cell pair as written", "µM"], ["figure3-g1", 2, 1, "the two-cell pair", "mM"]]) {
        if (!index.runs.some((row) => row.id === `${R}--${arm}`)) { note(`${label}: ${arm} is not among the runs the folder's index chooses: skipped`); continue; }
        const ok = await open(`run=${R}--${arm}&time=600`);
        if (!ok) { check(`${label} opens`, false, ""); continue; }
        const colour = stated(arm) ? "stated-concentration-tint" : "amount-mr-tint";
        await until(`${L}.markOn("links")?.mark.counts && ${L}.switch.holder("colour") === ${JSON.stringify(colour)}`, 60);
        s = await state();
        check(`${label}: the cells stand where the run's view prescribes them, every junction a line between its two cells`, s.cells === cells && (s.links?.open || 0) + (s.links?.shut || 0) === lines && s.note === "cell positions as the run's view prescribes" && !s.error, JSON.stringify([s.cells, s.links, s.note, s.error]));
        check(colour.startsWith("stated") ? `${label}: it opens on the quantity the experiment's driver states beside it, in its own unit (${unit}), said to be the experiment's and not the engine's, with Coupling on` : `${label}: it opens on the experiment's quantity, the amount of its species in each cell, with Coupling on`, s.colour === colour && s.on.includes("junction-coupling") && (!colour.startsWith("stated") || (s.unit === unit && /experiment's own quantity, stated by its driver beside the run \(concentration\.json\)/.test(s.said) && /not a field of the engine/.test(s.said))), JSON.stringify([s.colour, s.on, s.unit, s.said.slice(0, 160)]));
        check(`${label}: the card says the two forms state the quantity in their own units, never converted`, /Norton form's runs in mM, the as-written runs in µM/.test(s.units || "") && /never converts/.test(s.units || ""), s.units || "");
        check(`${label}: the sweeps' card shows the sweep that holds the run shown, its arm marked`, Boolean(s.sweep) && JSON.stringify(s.shown) === JSON.stringify([arm]), JSON.stringify([s.sweep, s.shown]));
        // On a wide window the picture makes room for the sweeps' card: no cell lies under it.
        if (WIDTH >= 760) {
          const room = await evaluate(`(() => { const v = ${V}, lens = v.current, card = v.shadowRoot.querySelector(".sweep-card"), box = v.getBoundingClientRect(); if (!card || card.hidden || !lens.sheet) return null; const Vector = lens.sheet.cells[0].top.constructor; v.stage.camera.updateMatrixWorld(); let right = -Infinity; for (const cell of lens.sheet.cells) for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { const p = new Vector(cell.centre[0] + dx * cell.radius, 0, cell.centre[1] + dz * cell.radius).project(v.stage.camera); right = Math.max(right, ((p.x + 1) / 2) * box.width); } return { right: Math.round(right), card: Math.round(card.getBoundingClientRect().left - box.left) }; })()`);
          check(`${label}: the picture makes room for the sweeps' card, no cell under it`, room && room.right <= room.card, JSON.stringify(room));
        }
        await shot(arm);
    }
    // GARD's row shows the origin view in the Experiments tab's place (its levels, its clock, its panels); the species switch and the first tab stay as they were.
    const before = await evaluate(`({ run: ${L}.runId, model: ${V}.state.model || null, first: ${V}.shadowRoot.querySelector('[data-lens="cell"] .long')?.textContent })`);
    const door = () => evaluate(`(() => { const v = ${V}, root = v.shadowRoot, lens = v.current; return { tab: v.state.lens, pressed: root.querySelector('[data-lens="experiments"]')?.getAttribute("aria-pressed"), door: v.state.example, model: v.state.model || null, first: root.querySelector('[data-lens="cell"] .long')?.textContent, entry: new URL(location.href).searchParams.get("entry"), view: Boolean(lens?.levels && lens.player), rail: root.querySelector(".rail .rail-title")?.textContent || null, levels: [...root.querySelectorAll(".rail [data-stop]")].length, timeline: !v.timeline.hidden && v.timeline.player === lens?.player, pair: Boolean(lens?.pairRuns), pairChoice: Boolean(root.querySelector('.view select[data-choice="pair"]')), list: root.querySelector("#cells-experiment") ? [...root.querySelector("#cells-experiment").options].map((o) => [o.textContent, String(o.selected)]) : [...root.querySelectorAll(".view .exp-row")].map((b) => [b.textContent, b.getAttribute("aria-pressed")]), sweepCard: !root.querySelector(".sweep-card")?.hidden || Boolean(root.querySelector(".view .sweep")), run: lens?.runId ?? null, sheet: Boolean(lens?.sheet), errors: window.__pageErrors }; })()`);
    // A row of the list: on a wide window a real press; on a phone its list is a select in the folded card, opened by a real press.
    const choose = async (wanted) => {
      if (WIDTH >= 760) {
        const at = await placeOf(`root.querySelector(${JSON.stringify(wanted === "gard" ? '.view .exp-row[data-door="gard"]' : ".view .exp-row:not([data-door])")})`);
        if (at) await click(at.x, at.y, 1500);
        return Boolean(at);
      }
      if (!(await evaluate(`${V}.state.viewOpen`))) {
        const fold = await placeOf(`root.querySelector(".view-toggle")`);
        if (fold) await click(fold.x, fold.y, 900);
      }
      return evaluate(`(() => { const select = ${V}.shadowRoot.querySelector("#cells-experiment"); const option = select && [...select.options].find((o) => ${wanted === "gard" ? `o.value === "door:gard"` : `!o.value.startsWith("door:")`}); if (!option) return false; select.value = option.value; select.dispatchEvent(new Event("change")); return true; })()`);
    };
    const gard = await choose("gard");
    await until(`Boolean(${L}?.levels && ${L}.player)`, 120);
    let d = await door();
    check("a real press on GARD's row shows the origin view in the Experiments tab's place: the tab stays pressed, the species switch and the first tab as they were", Boolean(gard) && d.tab === "experiments" && d.pressed === "true" && d.door === "gard" && d.view && d.model === before.model && d.first === before.first && !d.entry, JSON.stringify(d));
    check("its levels stand on the rail, its clock on the timeline, and the tab's list at the head of its card, GARD's row pressed", d.rail === "Level" && d.levels >= 2 && d.timeline && d.list.length === 2 && d.list[1][1] === "true" && d.list[0][1] === "false" && !d.sweepCard, JSON.stringify([d.rail, d.levels, d.timeline, d.list, d.sweepCard]));
    check(d.pair ? "the entry names the engine's two runs: the card offers the two forms of the law (side by side where there is room)" : "the entry names no pair of the engine's runs here: the card offers none", d.pair === d.pairChoice, JSON.stringify([d.pair, d.pairChoice]));
    // Its panels: a part the view describes opens its panel here.
    const part = await evaluate(`${L}.sections().flatMap((section) => section.entities || []).find((entity) => entity?.id && !String(entity.id).startsWith("model:"))?.id || null`);
    if (part) await evaluate(`${V}.select(${JSON.stringify(part)})`);
    await sleep(1200);
    const panel = await evaluate(`${V}.shadowRoot.querySelector("cells-panel")?.textContent || ""`);
    check("a part of the origin view opens its panel in the Experiments tab", Boolean(part) && panel.length > 40, `${part}: ${panel.slice(0, 120)}`);
    await evaluate(`${V}.select(null)`);
    await sleep(600);
    await shot("gard-door");
    // The replication's row: its run again, as it was left, with its sweeps' card.
    const back = await choose("replication");
    await until(`Boolean(${L}?.sheet && ${L}.run)`, 120);
    d = await door();
    check("a real press on the replication's row shows its runs again, the run left before, with its sweeps' card", Boolean(back) && d.tab === "experiments" && !d.door && d.run === before.run && d.sheet && d.sweepCard, JSON.stringify([d.door, d.run, before.run, d.sheet, d.sweepCard]));
    const errors = await evaluate(`window.__pageErrors`);
    check("the page logged no error", !errors.length, JSON.stringify(errors));
  } else if (CASE === "sweep") {
    const viewed = runOf("synthetic-world", "viewed"), secreting = runOf("synthetic-world", "secreting");
    check("the made-up experiment opens on its arm 'viewed'", await open(`run=${viewed}&time=1`));
    const chart = () => evaluate(`(() => { const root = ${V}.shadowRoot, sweep = root.querySelector(".sweep"); if (!sweep) return null; return { arms: [...sweep.querySelectorAll(".sweep-arm")].map((b) => ({ arm: b.dataset.arm, pressed: b.getAttribute("aria-pressed"), disabled: b.disabled, words: b.getAttribute("aria-label") })), rows: [...sweep.querySelectorAll(".sweep-table tbody tr")].map((tr) => [...tr.children].map((cell) => cell.textContent)), head: [...sweep.querySelectorAll(".sweep-table thead th")].map((th) => th.textContent), points: sweep.querySelectorAll(".sweep-point").length, rings: sweep.querySelectorAll(".sweep-ref").length, label: sweep.querySelector(".seg-label")?.textContent, text: sweep.textContent, run: ${L}.runId }; })()`);
    let s = await chart();
    check("the card offers the sweep's chart: a point for each readout of each arm, rings where the summary states its reference", s && s.label === "Made-up sweep over a coupling" && s.points === 8 && s.rings === 6, JSON.stringify(s && [s.label, s.points, s.rings]));
    check("each arm is a button; the arm shown is marked; the arm with no run says so and cannot be pressed", s && s.arms.length === 4 && s.arms.find((arm) => arm.arm === "viewed")?.pressed === "true" && s.arms.find((arm) => arm.arm === "not-run")?.disabled === true && /no run of it is packaged here$/.test(s.arms.find((arm) => arm.arm === "not-run").words), JSON.stringify(s?.arms));
    check("the numbers stand in a table, as the summary gives them", s && s.rows.length === 4 && JSON.stringify(s.rows[0]) === JSON.stringify(["secreting", "0.5", "6.2", "8.8", "6.25", "8.75"]), JSON.stringify(s?.rows));
    check("nothing on the chart judges the numbers", s && !/agree|replicat|reproduc/i.test(s.text), "");
    await shot("chart");
    // A real press on the arm 'secreting' shows its run.
    const at = await placeOf(`root.querySelector('.sweep-arm[data-arm="secreting"]')`);
    if (at) await click(at.x, at.y, 1500);
    await until(`${L}.runId === ${JSON.stringify(secreting)} && Boolean(${L}.run)`);
    s = await chart();
    check("a real press on another arm's point shows that arm's run, and the chart marks it", at && s?.run === secreting && s.arms.find((arm) => arm.arm === "secreting")?.pressed === "true", JSON.stringify([s?.run, s?.arms.map((arm) => arm.pressed)]));
    // The keys: Tab reaches every arm with a run; Enter on one shows it.
    await evaluate(`${V}.shadowRoot.querySelector('.sweep-arm[data-arm="secreting"]').focus()`);
    const reached = [];
    for (let k = 0; k < 6; k++) {
      reached.push(await evaluate(`${V}.shadowRoot.activeElement?.dataset?.arm || ${V}.shadowRoot.activeElement?.className || ""`));
      await key("Tab", 9);
    }
    check("the keys reach every arm that has a run, one after the other", ["secreting", "viewed", "retiring"].every((arm) => reached.includes(arm)), JSON.stringify(reached));
    await evaluate(`${V}.shadowRoot.querySelector('.sweep-arm[data-arm="retiring"]').focus()`);
    await key("Enter", 13);
    const retiring = runOf("synthetic-world", "retiring");
    check("Enter on an arm shows its run", await until(`${L}.runId === ${JSON.stringify(retiring)}`), "");
    await shot("chart-pressed");
    const errors = await evaluate(`window.__pageErrors`);
    check("the page logged no error", !errors.length, JSON.stringify(errors));
  }
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
  console.error(`check_junctions: ${failed.stack || failed}`);
  process.exit(2);
}
const passed = results.filter(Boolean).length;
console.log(`${passed} of ${results.length} checks passed`);
process.exit(passed === results.length ? 0 : 1);
