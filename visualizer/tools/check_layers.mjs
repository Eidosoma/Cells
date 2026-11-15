#!/usr/bin/env node
// Checks the quantity layers of a replay (schema/QUANTITY_LAYERS.md) with real pointer
// input, through the DevTools protocol, in the manner of tools/check_shelves.mjs: that the
// replay opens as it always did (layer zero), that the legend's switch puts one layer on a
// channel, that a record in a file of its own is fetched only when its layer is switched
// on, and that the legend says what stands behind each layer.
//
//   node tools/check_layers.mjs [SCENARIO] [RUNS_DIR] [OUT_DIR]
//
// SCENARIO is zero (the default), switch or picture. `picture` writes into OUT_DIR a
// picture of the page at QUERY (the page's query string), named NAME, once the page has
// settled; or the few pictures that PICTURES lists as JSON, [{ name, query, size, do }], at
// most four a call, so that the one browser is held as briefly as can be.
// RUNS_DIR is the folder of replays to serve (default: out/runs). WIDTH, HEIGHT and RUN
// (a run's id) may be set. One browser at a time: it takes the lock in
// tools/lib/browser_lock.mjs, whose profile folder is on disk and removed afterwards.

import { spawn } from "node:child_process";
import { writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { createServer } from "./serve.mjs";
import { acquireBrowser } from "./lib/browser_lock.mjs";
import { DEFAULT_RUNS, DEFAULT_SCENE } from "./lib/build_page.mjs";

const scenario = process.argv[2] || "zero";
const runs = path.resolve(process.argv[3] || DEFAULT_RUNS);
const outDir = process.argv[4] ? path.resolve(process.argv[4]) : null;
if (outDir) await mkdir(outDir, { recursive: true });

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const results = [];
const check = (name, ok, detail = "") => {
  results.push(Boolean(ok));
  console.log(`${ok ? "pass" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`);
};
const note = (text) => console.log(`note  ${text}`);
const pageLog = [];
const release = await acquireBrowser({ wait: 60 * 60 * 1000 });
const server = createServer({ offline: true, scene: DEFAULT_SCENE, runs, log: (line) => pageLog.push(line) });
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}/`;
const WIDTH = Number(process.env.WIDTH || 1400), HEIGHT = Number(process.env.HEIGHT || 900);
const chrome = spawn(
  process.env.CHROME || "google-chrome",
  ["--headless=new", `--user-data-dir=${release.profile}`, "--disable-breakpad", "--no-first-run", "--no-sandbox", "--mute-audio", "--hide-scrollbars", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", `--window-size=${WIDTH},${HEIGHT}`, "--remote-debugging-port=0", "about:blank"],
  { stdio: ["ignore", "ignore", "pipe"] }
);
const endpoint = await new Promise((resolve, reject) => {
  let text = "";
  chrome.stderr.on("data", (chunk) => {
    text += chunk;
    const match = text.match(/DevTools listening on (ws:\/\/\S+)/);
    if (match) resolve(match[1]);
  });
  setTimeout(() => reject(new Error("Chrome did not report a DevTools address")), 30000);
});
const socket = new WebSocket(endpoint);
await new Promise((resolve, reject) => {
  socket.onopen = resolve;
  socket.onerror = reject;
});
let nextId = 1;
const waiting = new Map();
socket.onmessage = (event) => {
  const message = JSON.parse(event.data);
  const entry = waiting.get(message.id);
  if (!entry) return;
  waiting.delete(message.id);
  if (message.error) entry.reject(new Error(message.error.message));
  else entry.resolve(message.result);
};
const send = (method, params = {}, sessionId) =>
  new Promise((resolve, reject) => {
    const id = nextId++;
    waiting.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params, sessionId }));
  });
const { targetId } = await send("Target.createTarget", { url: "about:blank" });
const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
const page = (method, params) => send(method, params, sessionId);
await page("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: HEIGHT, deviceScaleFactor: 1, mobile: false });
const evaluate = async (expression) => {
  const reply = await page("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (reply.exceptionDetails) throw new Error(reply.exceptionDetails.exception?.description || reply.exceptionDetails.text);
  return reply.result.value;
};
const V = "document.querySelector('cells-viewer')";
const L = `${V}.current`;

/** The view holds still: three looks in a row with the camera and the stage where they were (at most 8 s). */
const rest = async () => {
  let before = null, same = 0;
  for (let tries = 0; tries < 80 && same < 3; tries++) {
    const now = await evaluate(`(() => { const s = ${V}.stage, c = s.camera; return JSON.stringify([c.position.toArray(), c.quaternion.toArray(), s.width, s.height].flat().map((n) => Math.round(n * 1000) / 1000)); })()`).catch(() => null);
    same = now !== null && now === before ? same + 1 : 0;
    before = now;
    await sleep(100);
  }
};
/** Open the page on the replay and wait until its run is drawn and the view holds still. */
const open = async (query) => {
  await page("Page.navigate", { url: `${base}?lens=experiments&still=1${query ? `&${query}` : ""}` });
  // On a busy machine the page and its run can take a long while: wait up to three minutes, and say so if they do not come.
  let drawn = false;
  for (let tries = 0; tries < 720 && !drawn; tries++) {
    await sleep(250);
    drawn = await evaluate(`Boolean(${V} && ${V}.current && ${V}.stage && ${V}.state.lens === "experiments" && ${L}.run && ${L}.sheet && ${L}.run.id === ${L}.runId)`).catch(() => false);
  }
  if (!drawn) throw new Error("the replay's run was not drawn within three minutes of opening the page");
  await evaluate(`Promise.resolve(${L}.ready)`);
  // Layers asked for in the address may still be fetching their records.
  for (let tries = 0; tries < 160; tries++) {
    if (await evaluate(`${L}.fetching.size === 0`).catch(() => false)) break;
    await sleep(250);
  }
  await evaluate(`${L}.player.pause()`);
  await rest();
  await sleep(400);
};
const mouse = (type, x, y, extra = {}) => page("Input.dispatchMouseEvent", { type, x, y, button: "left", buttons: 1, clickCount: 1, ...extra });
const click = async (x, y, wait = 400) => {
  await mouse("mouseMoved", x, y, { button: "none", buttons: 0 });
  await mouse("mousePressed", x, y);
  await mouse("mouseReleased", x, y, { buttons: 0 });
  await sleep(wait);
};
const middle = (selector) =>
  evaluate(`(() => { const el = ${V}.shadowRoot.querySelector(${JSON.stringify(selector)}); if (!el) return null; el.scrollIntoView({ block: "nearest" }); const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2, text: el.textContent, pressed: el.getAttribute("aria-pressed") }; })()`);
const press = async (selector, wait = 500) => {
  const at = await middle(selector);
  if (!at) throw new Error(`nothing matches ${selector}`);
  await click(at.x, at.y, wait);
};
const option = (channel, layer) => `cells-legend .layer-row[data-channel="${channel}"] button[data-layer="${layer}"]`;
const shot = async (name) => {
  if (!outDir) return;
  const { data } = await page("Page.captureScreenshot", { format: "png" });
  await writeFile(path.join(outDir, `${name}.png`), Buffer.from(data, "base64"));
  note(`wrote ${path.join(outDir, `${name}.png`)}`);
};
/** What the replay shows now, as the page itself has it. */
const state = () =>
  evaluate(`(() => {
    const v = ${V}, root = v.shadowRoot, lens = v.current, sheet = lens.sheet;
    const heights = sheet.cells.map((cell) => cell.height);
    const drops = lens.drawn.get("junction-drops")?.mark;
    return {
      run: lens.runId, on: lens.switch.on, strength: lens.switch.strength, time: lens.player.time,
      low: lens.low, pitch: lens.pitch, lowest: Math.min(...heights), tallest: Math.max(...heights),
      rows: [...root.querySelectorAll("cells-legend .layer-row")].map((row) => row.dataset.channel + ": " + [...row.querySelectorAll("button")].map((b) => b.textContent + (b.getAttribute("aria-pressed") === "true" ? "*" : "")).join(" | ")),
      cannot: [...root.querySelectorAll("cells-legend .layer-cannot")].map((p) => p.textContent),
      keys: [...root.querySelectorAll("cells-legend .legend-key .key")].map((k) => k.className.replace("key key-", "")),
      note: root.querySelector("cells-legend .legend-note")?.textContent ?? root.querySelector("cells-legend .legend-key-note")?.textContent ?? null,
      scale: root.querySelector("cells-legend .legend-scale-title")?.textContent ?? null,
      panel: (() => { const panel = root.querySelector("cells-panel"); return !panel || panel.hidden ? null : { title: panel.querySelector("h2")?.textContent ?? null, text: panel.textContent }; })(),
      legendBox: (() => { const box = root.querySelector("cells-legend").getBoundingClientRect(); return [Math.round(box.top), Math.round(box.bottom)]; })(),
      drops: drops ? { ...drops.counts, full: drops.full } : null,
      bar: [...root.querySelectorAll(".label")].filter((el) => !el.classList.contains("is-off") && /^[\\d.]+ m?V$/.test(el.textContent)).map((el) => el.textContent),
      fetched: performance.getEntriesByType("resource").filter((entry) => /\\.junction-gate\\.json$/.test(entry.name)).length,
      selected: v.state.selected,
      frame: (() => { const times = []; for (let i = 0; i < 5; i++) { const t = performance.now(); v.stage.renderer.render(v.stage.scene, v.stage.camera); v.stage.renderer.getContext().finish(); times.push(performance.now() - t); } times.sort((a, b) => a - b); return Math.round(times[2] * 10) / 10; })(),
    };
  })()`);

try {
  const run = process.env.RUN ? `run=${process.env.RUN}&` : "";
  if (scenario === "zero") {
    // Layer zero: the replay as it always opened, now drawn by two layers.
    await open(`${run}time=1170`);
    const s = await state();
    check("the replay opens with its colouring and its quiet relief on, and nothing else", JSON.stringify(s.on) === JSON.stringify(["voltage-tint", "voltage-relief"]) && s.strength === "quiet", JSON.stringify([s.on, s.strength]));
    // The sheet's own arrays against the replay's loop as it stood before layers.
    const same = await evaluate(`(() => {
      const lens = ${L}, sheet = lens.sheet, record = lens.record, step = lens.player.index, valid = lens.run.isValid(step);
      const { low, high, steps } = lens.scaleOf(record);
      const position = sheet.geometry.attributes.position.array, colour = sheet.geometry.attributes.color.array;
      const rgb = [0, 0, 0], linear = new (lens.ink.constructor)();
      let heights = 0, colours = 0, cells = 0;
      sheet.cells.forEach((cell, number_) => {
        let share = (record.at(step, number_) - low) / (high - low);
        if (steps) share = Math.round(share * steps) / steps;
        share = Math.min(1, Math.max(0, share));
        if (valid) lens.ramp.at(share, rgb); else rgb.splice(0, 3, ...lens.neutral);
        const height = valid ? lens.low + (lens.high - lens.low) * share : lens.low;
        linear.setRGB(rgb[0], rgb[1], rgb[2], "srgb");
        cells += 1;
        if (position[cell.start * 3 + 1] === Math.fround(height) && cell.height === height) heights += 1;
        if (colour[cell.start * 3] === Math.fround(linear.r) && colour[cell.start * 3 + 1] === Math.fround(linear.g) && colour[cell.start * 3 + 2] === Math.fround(linear.b)) colours += 1;
      });
      return { record: record.id, step, valid, cells, heights, colours };
    })()`);
    check("every cell has the colour and the height the replay gave it before layers", same.cells > 0 && same.heights === same.cells && same.colours === same.cells, JSON.stringify(same));
    check("the legend reads as before: the scale of the voltage, and that height repeats the colour", /Membrane voltage/.test(s.scale || "") && /Height repeats the colour\. Every step is a saved record\./.test(s.note || ""), JSON.stringify([s.scale, s.note]));
    check("the switch offers a row for the height and one for the junctions, and no record of its own has been fetched", s.rows.length === 3 && /^height: Off \| Voltage\*/.test(s.rows[0]) && /^links: Off\* \| Voltage drops$/.test(s.rows[1]) && /^strength: Quiet\* \| Bold$/.test(s.rows[2]) && s.fetched === 0, JSON.stringify([s.rows, s.fetched]));
    note(`a frame at rest: ${s.frame} ms`);
    // The card's choice of colour still moves the height with it.
    const records = await evaluate(`${L}.offers.filter((item) => item.ok && item.layer.mark === "tint").map((item) => item.source.id)`);
    if (records.includes("generation")) {
      await evaluate(`${L}.setRecord("generation")`);
      const g = await state();
      check("colouring by another record moves the height with it, as it always did", JSON.stringify(g.on) === JSON.stringify(["generation-tint", "generation-relief"]) && /Height repeats the colour/.test(g.note || ""), JSON.stringify([g.on, g.note]));
      await evaluate(`${L}.setRecord("vm")`);
    }
    await shot("zero");
  }

  if (scenario === "switch") {
    await open(`${run}time=1170`);
    let s = await state();
    // Height off, with a real press on the legend's switch: the sheet lies flat.
    await press(option("height", ""));
    s = await state();
    check("Off on the height row lays the sheet flat", JSON.stringify(s.on) === JSON.stringify(["voltage-tint"]) && s.tallest === s.low && s.lowest === s.low && /The sheet is flat/.test(s.note || ""), JSON.stringify([s.on, s.lowest, s.tallest, s.note]));
    await press(option("height", "voltage-relief"));
    s = await state();
    check("Voltage on the height row raises it again", s.on.includes("voltage-relief") && s.tallest > s.low && /Height repeats the colour/.test(s.note || ""), JSON.stringify([s.on, s.tallest]));
    // The drops: their gate comes in a file of its own, fetched now and not before.
    check("before the drops are switched on, no record of their own has been fetched", s.fetched === 0, String(s.fetched));
    await press(option("links", "junction-drops"));
    for (let tries = 0; tries < 120; tries++) {
      if (await evaluate(`${L}.switch.isOn("junction-drops") && ${L}.fetching.size === 0`)) break;
      await sleep(250);
    }
    s = await state();
    check("Voltage drops on the junctions row fetches the junctions' gate and draws a sign on each junction that carries a drop", s.on.includes("junction-drops") && s.fetched === 1 && s.drops && s.drops.solid + s.drops.hollow + s.drops.break > 0, JSON.stringify([s.on, s.fetched, s.drops]));
    check("the other layers stay on beside it: one layer on each channel", s.on.includes("voltage-tint") && s.on.includes("voltage-relief"), JSON.stringify(s.on));
    check("the legend shows the wedge, with what a hollow one and two bars mean", s.keys.includes("wedge") && s.keys.includes("wedge-hollow") && s.keys.includes("break"), JSON.stringify(s.keys));
    note(`drops at ${s.time.toFixed(0)} s: ${JSON.stringify(s.drops)}; a frame: ${s.frame} ms`);
    check("the legend stays within the window with the drops' signs listed", s.legendBox[0] >= 0 && s.legendBox[1] <= HEIGHT, JSON.stringify(s.legendBox));
    // What stands behind them, opened with a real press: the panel says it.
    await press("cells-legend .layer-details");
    s = await state();
    const said = s.panel?.text || "";
    check("the panel says the drops are worked out by the viewer, from what, and what that rests on", s.panel?.title === "What the layers show" && /Worked out by the viewer from the saved membrane voltage/.test(said) && /held bath at 0 V/.test(said) && /not a current/.test(said), `${s.panel?.title}: ${said.slice(0, 300)}`);
    check("and of the voltage that it is saved by the run, with the model that computed it", /Its numbers: saved by the run.*Saved by the run; computed by resolved_pump_replacement@1/i.test(said), said.slice(0, 300));
    await evaluate(`${V}.select(null)`);
    // Bold: the same values stand higher, and a bar says how much one stretch of height is.
    const before = s.tallest;
    await press(option("strength", "bold"));
    s = await state();
    check("Bold raises the same values higher and stands a bar beside the sheet", s.strength === "bold" && s.tallest > 3 * before && s.bar.length === 1, JSON.stringify([s.strength, before, s.tallest, s.bar]));
    note(`bold: tallest ${(s.tallest / s.pitch).toFixed(2)} cells across; bar ${s.bar[0]}; a frame: ${s.frame} ms`);
    await shot("switch-bold");
    // A cell can still be picked with the drops over the sheet: they take no clicks.
    await rest();
    const cell = await evaluate(`(() => {
      const viewer = ${V}, lens = viewer.current, cells = lens.sheet.cells;
      for (let index = 0; index < cells.length; index++) {
        const out = cells[index].top.clone();
        viewer.stage.project(cells[index].top, out);
        if (out.x < 330 || out.x > 980 || out.y < 140 || out.y > 600) continue;
        const hit = viewer.stage.pick(out.x, out.y, lens.pickRoots);
        if (hit && hit.id === "cell:" + index && viewer.shadowRoot.elementFromPoint(out.x, out.y) === viewer.canvas) return { id: "cell:" + index, x: out.x, y: out.y };
      }
      return null;
    })()`);
    await click(cell.x, cell.y);
    s = await state();
    check("a click on a cell still picks it with the drops drawn over the sheet", s.selected === cell.id, `${cell.id} -> ${s.selected}`);
    await evaluate(`${V}.select(null)`);
    await press(option("strength", "quiet"));
    await press(option("links", ""));
    s = await state();
    check("Off on the junctions row takes the drops away, and Quiet brings the heights back", !s.on.includes("junction-drops") && s.drops === null && s.strength === "quiet" && Math.abs(s.tallest - before) < 1e-9 && !s.keys.includes("wedge"), JSON.stringify([s.on, s.strength, s.tallest, s.keys]));
    // Another run: a layer that was on is fetched for it too.
    await press(option("links", "junction-drops"));
    const other = await evaluate(`(() => { const lens = ${L}; const next = lens.catalogue.runs.find((item) => item.id !== lens.runId && item.experiment === lens.catalogue.byId.get(lens.runId).experiment); if (next) lens.show(next.id); return next ? next.id : null; })()`);
    if (other) {
      for (let tries = 0; tries < 160; tries++) {
        if (await evaluate(`${L}.run && ${L}.run.id === ${JSON.stringify(other)} && ${L}.switch.isOn("junction-drops") && ${L}.fetching.size === 0`)) break;
        await sleep(250);
      }
      s = await state();
      check("in another run the drops stay on: its own gate is fetched", s.run === other && s.on.includes("junction-drops") && s.fetched === 2, JSON.stringify([s.run, s.on, s.fetched]));
    }
  }

  if (scenario === "picture") {
    // Pictures of the page as its address asks for it: one, or the few that PICTURES lists
    // ([{ name, query, size: [width, height] }]). At most four a call, so the browser is held briefly.
    const list = process.env.PICTURES ? JSON.parse(process.env.PICTURES) : [{ name: process.env.NAME || "picture", query: process.env.QUERY || `${run}time=1170` }];
    if (list.length > 4) throw new Error("at most four pictures a call: the one browser is shared");
    for (const item of list) {
      const [width, height] = item.size || [WIDTH, HEIGHT];
      await page("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: false });
      await open(item.query);
      // `do` is a script for the page once it has settled, with `viewer` and `lens` at hand (to open the legend on a phone, say).
      if (item.do) {
        await evaluate(`(async () => { const viewer = ${V}, lens = viewer.current; ${item.do} })()`);
        await rest();
        await sleep(500);
      }
      const s = await state();
      note(`${item.name}: ${JSON.stringify({ size: [width, height], run: s.run, on: s.on, strength: s.strength, time: s.time, drops: s.drops, bar: s.bar, tallest_cells: Number((s.tallest / s.pitch).toFixed(2)), frame_ms: s.frame, rows: s.rows, cannot: s.cannot })}`);
      await shot(item.name);
    }
  }
} catch (error) {
  check("the run completed", false, error.stack || error.message);
} finally {
  for (const line of pageLog) console.log(line);
  check("no script errors or blocked loads were reported by the page", pageLog.length === 0, `${pageLog.length} messages`);
  socket.close();
  {
    const closed = new Promise((resolve) => chrome.once("close", resolve));
    chrome.kill();
    await Promise.race([closed, new Promise((resolve) => setTimeout(resolve, 4000))]);
    if (chrome.exitCode === null && chrome.signalCode === null) chrome.kill("SIGKILL");
    await Promise.race([closed, new Promise((resolve) => setTimeout(resolve, 2000))]);
  }
  server.close();
  release();
}
const failed = results.filter((ok) => !ok).length;
console.log(`${results.length - failed} of ${results.length} checks passed`);
process.exit(failed ? 1 : 0);
