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
import { copyFileSync, mkdirSync, readFileSync, existsSync, writeFileSync } from "node:fs";
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
writeFileSync(path.join(scene, "overlay.json"), JSON.stringify(overlay));
python("adapt_run.py", ["--experiment", "synthetic-world", "--root", path.join(fixtures, "run-world"), "--run", "secreting", "--run", "viewed", "--run", "retiring", "--overlay", path.join(scene, "overlay.json"), "--out", runs]);
python("adapt_run.py", ["--experiment", "example-sheet", "--root", path.join(fixtures, "run-example"), "--run", "invented-numbers", "--overlay", path.join(scene, "overlay.json"), "--out", runs]);
const gap = existsSync(path.join(GAP_FIXTURE, "fixture-figure3-g1"));
if (gap) python("adapt_run.py", ["--experiment", "gap-junction-fixture", "--root", GAP_FIXTURE, "--run", "fixture-figure3-g1", "--overlay", path.join(scene, "overlay.json"), "--out", runs]);
else note(`the gap-junction fixture is not on this machine (${GAP_FIXTURE}): its part is skipped`);
const index = JSON.parse(readFileSync(path.join(runs, "index.json"), "utf8"));
const runOf = (experiment, arm) => index.runs.find((row) => row.experiment === experiment && row.arm === arm)?.id;

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
