#!/usr/bin/env node
// Checks the quantity layers of a replay (schema/QUANTITY_LAYERS.md) with real pointer
// input, through the DevTools protocol, in the manner of tools/check_shelves.mjs: that the
// replay opens as it always did (layer zero), that the legend's switch puts one layer on a
// channel, that a record in a file of its own is fetched only when its layer is switched
// on, and that the legend says what stands behind each layer.
//
//   node tools/check_layers.mjs [SCENARIO] [RUNS_DIR] [OUT_DIR]
//
// SCENARIO is zero (the default), switch, closeup or picture. `closeup` checks the layers
// that are drawn on a chosen cell's membrane: that the close-up comes with a cell and a
// layer and goes with either, that it says what it is, and that the page's own numbers are
// the two declared rules applied to the run's saved arrays. With REFERENCE set to a JSON
// file of numbers worked out outside the viewer ({ run, time, cells: { "63": { vm_mV,
// terms: { Na: { concentration_mV, concentration, voltage_mV, voltage, left_mV, left } },
// charge_pC, charges, per_um2, on_piece } } }), it also holds the page to those, to within
// what storing the records in 32 bits allows. `picture` writes into OUT_DIR a
// picture of the page at QUERY (the page's query string), named NAME, once the page has
// settled; or the few pictures that PICTURES lists as JSON, [{ name, query, size, do }], at
// most four a call, so that the one browser is held as briefly as can be.
// RUNS_DIR is the folder of replays to serve (default: out/runs). WIDTH, HEIGHT and RUN
// (a run's id) may be set. One browser at a time: it takes the lock in
// tools/lib/browser_lock.mjs, whose profile folder is on disk and removed afterwards.

import { spawn } from "node:child_process";
import { readFile, writeFile, mkdir } from "node:fs/promises";
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
  // On a busy machine the page and its run can take a long while: wait up to six minutes, and say so if they do not come.
  let drawn = false;
  for (let tries = 0; tries < 1440 && !drawn; tries++) {
    await sleep(250);
    drawn = await evaluate(`Boolean(${V} && ${V}.current && ${V}.stage && ${V}.state.lens === "experiments" && ${L}.run && ${L}.sheet && ${L}.run.id === ${L}.runId)`).catch(() => false);
  }
  if (!drawn) throw new Error("the replay's run was not drawn within six minutes of opening the page");
  await evaluate(`Promise.resolve(${L}.ready)`);
  // Layers asked for in the address may still be fetching their records.
  for (let tries = 0; tries < 160; tries++) {
    if (await evaluate(`${L}.fetching.size === 0`).catch(() => false)) break;
    await sleep(250);
  }
  await evaluate(`${L}.player.pause()`);
  await rest();
  // A close-up just built waits a moment for the window to settle and may then move the view to make room: wait for that too.
  for (let tries = 0; tries < 240; tries++) {
    if (await evaluate(`!(${L}.closeup && ${L}.roomIn > 0)`).catch(() => true)) break;
    await sleep(250);
  }
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
/** Where a cell of the sheet can be pressed: the middle of its top, if nothing lies over it and a press there picks it. */
const cellAt = (number) =>
  evaluate(`(() => {
    const viewer = ${V}, lens = viewer.current, cell = lens.sheet.cells[${number}];
    if (!cell) return null;
    const out = cell.top.clone();
    viewer.stage.project(cell.top, out);
    const hit = viewer.stage.pick(out.x, out.y, lens.pickRoots);
    return hit && hit.id === "cell:${number}" && viewer.shadowRoot.elementFromPoint(out.x, out.y) === viewer.canvas ? { x: out.x, y: out.y } : null;
  })()`);
/** Wait until no layer is fetching its records (at most two minutes). */
const fetched = async () => {
  for (let tries = 0; tries < 480; tries++) {
    if (await evaluate(`${L}.fetching.size === 0`).catch(() => false)) return;
    await sleep(250);
  }
};
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
      ions: performance.getEntriesByType("resource").filter((entry) => /\\.concentration-[a-z0-9-]+\\.json$/.test(entry.name)).length,
      hint: root.querySelector("cells-legend .layer-hint")?.textContent ?? null,
      chips: [...root.querySelectorAll("cells-legend .key-chip")].map((chip) => chip.textContent + " " + chip.querySelector("i").style.background),
      selected: v.state.selected,
      // The close-up of a chosen cell's membrane: where it stands, what it says, and the page's own numbers.
      closeup: lens.closeup ? {
        cell: lens.closeup.cell, membrane: lens.closeup.membrane.id, layers: [...lens.onMembrane.keys()],
        placed: lens.closeup.placed ? Object.fromEntries(Object.entries(lens.closeup.placed).map(([key, value]) => [key, typeof value === "number" ? Math.round(value * 10) / 10 : value])) : null,
        words: [...root.querySelectorAll(".label-closeup")].filter((el) => !el.classList.contains("is-off")).map((el) => el.textContent),
        arrows: (() => { const mark = lens.onMembrane.get("ion-push-pull")?.mark; return mark && mark.readings ? { full: mark.full, terms: mark.readings.map((term) => term && { id: term.id, valence: term.valence, inside: term.inside, outside: term.outside, voltage: term.voltage, size: term.size, drives: term.drives, volts: term.volts }) } : null; })(),
        charge: (() => { const mark = lens.onMembrane.get("membrane-charge")?.mark; return mark && mark.readings ? { ...mark.readings, piece: mark.piece } : null; })(),
      } : null,
      frame: (() => { const times = []; for (let i = 0; i < 5; i++) { const t = performance.now(); v.stage.renderer.render(v.stage.scene, v.stage.camera); v.stage.renderer.getContext().finish(); times.push(performance.now() - t); } times.sort((a, b) => a - b); return Math.round(times[2] * 10) / 10; })(),
    };
  })()`);

/**
 * Wait until the page shows what a step leads to: look every 150 ms until `test` holds for
 * the page's state, for at most `limit` ms, and give back the state last seen. A label or
 * a mark may come a frame or two after the press that asks for it; a fixed wait would
 * sometimes read the page too early. The limit is generous: the browser runs at the lowest
 * priority on one processor (tools/lib/browser_lock.mjs), beside the engine's own jobs.
 */
const until = async (test, limit = 45000) => {
  let seen = await state();
  for (const started = Date.now(); !test(seen) && Date.now() - started < limit; ) {
    await sleep(150);
    seen = await state();
  }
  return seen;
};

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
    const row = (channel) => s.rows.find((item) => item.startsWith(`${channel}:`)) || "";
    check("the switch offers a row for the height and one for the junctions, and no record of its own has been fetched", /^height: Off \| Voltage\*/.test(row("height")) && /^links: Off\* \| Voltage drops$/.test(row("links")) && /^strength: Quiet\* \| Bold$/.test(row("strength")) && s.fetched === 0 && s.ions === 0, JSON.stringify([s.rows, s.fetched, s.ions]));
    // The layers of a chosen cell's membrane: offered and off where the run can feed them, named with the reason where it cannot.
    const offered = /^surface: Off\* \| Charge$/.test(row("surface")) && /^arrows: Off\* \| Push and pull on ions$/.test(row("arrows"));
    const named = s.cannot.some((text) => /^Arrows: push and pull on ions /.test(text)) && s.cannot.some((text) => /^Membrane: membrane charge |^Membrane: charge /i.test(text));
    check("the layers of a membrane are off as the replay opens: offered in the switch, or named as ones this run cannot feed", (offered || named) && s.closeup === null, JSON.stringify([s.rows, s.cannot]));
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
    s = await until((seen) => !seen.on.includes("voltage-relief") && seen.tallest === seen.low);
    check("Off on the height row lays the sheet flat", JSON.stringify(s.on) === JSON.stringify(["voltage-tint"]) && s.tallest === s.low && s.lowest === s.low && /The sheet is flat/.test(s.note || ""), JSON.stringify([s.on, s.lowest, s.tallest, s.note]));
    await press(option("height", "voltage-relief"));
    s = await until((seen) => seen.on.includes("voltage-relief") && seen.tallest > seen.low);
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
    s = await until((seen) => seen.panel?.title === "What the layers show");
    const said = s.panel?.text || "";
    check("the panel says the drops are worked out by the viewer, from what, and what that rests on", s.panel?.title === "What the layers show" && /Worked out by the viewer from the saved membrane voltage/.test(said) && /held bath at 0 V/.test(said) && /not a current/.test(said), `${s.panel?.title}: ${said.slice(0, 300)}`);
    check("and of the voltage that it is saved by the run, with the model that computed it", /Its numbers: saved by the run.*Saved by the run; computed by resolved_pump_replacement@1/i.test(said), said.slice(0, 300));
    await evaluate(`${V}.select(null)`);
    // Bold: the same values stand higher, and a bar says how much one stretch of height is.
    const before = s.tallest;
    await press(option("strength", "bold"));
    s = await until((seen) => seen.strength === "bold" && seen.tallest > 3 * before && seen.bar.length === 1);
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
    s = await until((seen) => seen.selected === cell.id);
    check("a click on a cell still picks it with the drops drawn over the sheet", s.selected === cell.id, `${cell.id} -> ${s.selected}`);
    await evaluate(`${V}.select(null)`);
    await press(option("strength", "quiet"));
    await press(option("links", ""));
    s = await until((seen) => !seen.on.includes("junction-drops") && seen.strength === "quiet" && !seen.keys.includes("wedge"));
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

  if (scenario === "closeup") {
    const reference = process.env.REFERENCE ? JSON.parse(await readFile(path.resolve(process.env.REFERENCE), "utf8")) : null;
    const time = reference?.time ?? 1170;
    await open(`${reference ? `run=${reference.run}&` : run}time=${time}`);
    let s = await state();
    check("the switch offers a row for the marks on a membrane and one for the arrows through it, both off; no ion's record has been fetched", s.rows.some((row) => /^surface: Off\* \| Charge$/.test(row)) && s.rows.some((row) => /^arrows: Off\* \| Push and pull on ions$/.test(row)) && s.ions === 0 && s.closeup === null, JSON.stringify([s.rows, s.ions]));
    // The arrows, switched on with a real press and no cell chosen: the ions' records are fetched, nothing is drawn, and the switch says how to see it.
    await press(option("arrows", "ion-push-pull"));
    await fetched();
    s = await until((seen) => seen.on.includes("ion-push-pull") && seen.ions === 3 && /Choose a cell/.test(seen.hint || ""));
    check("Push and pull fetches one record for each ion; with no cell chosen nothing is drawn and the switch says to choose a cell", s.on.includes("ion-push-pull") && s.ions === 3 && s.closeup === null && /Choose a cell of the sheet/.test(s.hint || ""), JSON.stringify([s.on, s.ions, s.hint]));
    check("the sheet is as it was: its colouring and relief stay on", s.on.includes("voltage-tint") && s.on.includes("voltage-relief"), JSON.stringify(s.on));
    // A cell chosen with a real press on the sheet: the close-up comes for it.
    const wanted = reference ? Object.keys(reference.cells).map(Number) : [];
    let first = null;
    for (const number of [...wanted, ...Array.from({ length: 127 }, (_, k) => k)]) {
      const at = await cellAt(number);
      if (at) {
        first = { number, ...at };
        break;
      }
    }
    await click(first.x, first.y, 700);
    s = await until((seen) => seen.selected === `cell:${first.number}` && seen.closeup?.cell === first.number && (seen.closeup.words || []).some((text) => text.startsWith("Membrane of")) && seen.closeup.placed?.fits !== false);
    await rest();
    s = await state();
    check("a press on a cell chooses it, and a piece of its membrane is drawn beside the sheet with the arrows on it", s.selected === `cell:${first.number}` && s.closeup?.cell === first.number && JSON.stringify(s.closeup.layers) === '["ion-push-pull"]' && s.hint === null, JSON.stringify([s.selected, s.closeup && [s.closeup.cell, s.closeup.layers]]));
    const caption = (s.closeup?.words || []).find((text) => text.startsWith("Membrane of")) || "";
    check("the close-up says what it is: the membrane and its cell, the time, the run, and what its numbers are worked out from", new RegExp(`^Membrane of cell_${first.number} at 19 min 30 s`).test(caption) && /Worked out by the viewer from the saved membrane voltage and ion concentrations, with the composition outside, temperature and valences of the run's definition\./.test(caption) && s.closeup.words.includes("Outside") && s.closeup.words.includes("Inside"), JSON.stringify(s.closeup?.words));
    check("it stands in the window, clear of the cards and the panel", s.closeup.placed && s.closeup.placed.x - s.closeup.placed.width / 2 >= 0 && s.closeup.placed.x + s.closeup.placed.width / 2 <= WIDTH && s.closeup.placed.y - s.closeup.placed.height / 2 >= 56 && s.closeup.placed.y + s.closeup.placed.height / 2 <= HEIGHT, JSON.stringify(s.closeup?.placed));
    check("each ion's colour stands beside its name in the legend", s.chips.length >= 3 && s.chips.every((chip) => /^\S+ rgb\(/.test(chip)) && new Set(s.chips.map((chip) => chip.split(" ").slice(1).join(" "))).size >= Math.min(3, s.chips.length), JSON.stringify(s.chips));
    // The page's own numbers against the rule applied to the page's own arrays, with nothing rounded.
    const consistent = () =>
      evaluate(`(() => {
        const lens = ${L}, run = lens.run, step = lens.player.index, cell = lens.closeup.cell, membrane = lens.closeup.membrane.index;
        const F = 6.02214076e23 * 1.602176634e-19, R = 6.02214076e23 * 1.380649e-23, e = 1.602176634e-19;
        const species = run.sets.get("species").ids, voltage = run.records.get("vm").at(step, cell);
        const temperature = run.constants.get("temperature").at(), out = { arrows: null, charge: null };
        const arrows = lens.onMembrane.get("ion-push-pull")?.mark;
        if (arrows) {
          out.arrows = arrows.readings.map((term) => {
            const row = species.indexOf(term.id), z = run.constants.get("valence").at(0, row);
            const inside = run.records.get("concentration_mM." + term.id).at(step, cell), outside = run.constants.get("extracellular_concentration_mM").at(membrane, row);
            const push = R * temperature * (Math.log(inside) - Math.log(outside)), pull = z * F * voltage;
            const way = (x) => (x > 0 ? "out" : x < 0 ? "in" : null);
            return term.concentration === push && term.electrical === pull && term.sum === push + pull && term.size.concentration === Math.abs(push) / Math.abs(z * F) && term.size.sum === Math.abs(push + pull) / Math.abs(z * F) && term.drives.concentration === way(push) && term.drives.electrical === way(pull) && term.drives.sum === way(push + pull);
          });
        }
        const charge = lens.onMembrane.get("membrane-charge")?.mark;
        if (charge) {
          const C = run.constants.get("membrane_capacitance").at(membrane), A = run.constants.get("membrane_area").at(membrane), reading = charge.readings;
          const count = Math.abs(C * voltage) / e, piece = charge.piece.width_nm * charge.piece.depth_nm * 1e-6;
          out.charge = reading.coulombs === C * voltage && reading.charges === count && reading.per_um2 === count / (A * 1e12) && reading.marks === Math.min(160, Math.round((count / (A * 1e12)) * piece / charge.worth)) && reading.inside === (C * voltage < 0 ? "minus" : "plus");
          out.marks = [reading.marks, lens.closeup.piece.children.filter((child) => child.isInstancedMesh).map((mesh) => mesh.count)];
        }
        return out;
      })()`);
    let same = await consistent();
    check("every arrow's number is the rule applied to the run's saved arrays: R T ln(c inside / c outside), z F V and their sum, each ion driven the way of its own term", Array.isArray(same.arrows) && same.arrows.length >= 1 && same.arrows.every(Boolean), JSON.stringify(same.arrows));
    /** The page's numbers for the cell shown, against numbers worked out outside the viewer. */
    const against = (state_, number) => {
      const told = reference?.cells?.[String(number)];
      if (!told) return null;
      const near = (a, b, slack) => Math.abs(a - b) <= slack;
      const problems = [];
      for (const term of state_.closeup.arrows?.terms || []) {
        const want = told.terms[term.id];
        if (!want) continue;
        // Stored in 32 bits: a voltage to about 4e-6 mV, a concentration to 1 part in 10 million.
        if (!near(term.size.concentration * 1000, want.concentration_mV, 2e-4) || term.drives.concentration !== want.concentration) problems.push(`${term.id} concentration ${term.size.concentration * 1000} ${term.drives.concentration}`);
        if (!near(term.size.electrical * 1000, want.voltage_mV, 2e-4) || term.drives.electrical !== want.voltage) problems.push(`${term.id} voltage ${term.size.electrical * 1000} ${term.drives.electrical}`);
        if (!near(term.size.sum * 1000, want.left_mV, 4e-4) || term.drives.sum !== want.left) problems.push(`${term.id} left ${term.size.sum * 1000} ${term.drives.sum}`);
        if (!near(term.inside, want.inside, 2e-5)) problems.push(`${term.id} inside ${term.inside}`);
      }
      const charge = state_.closeup.charge;
      if (charge) {
        if (!near(charge.coulombs * 1e12, told.charge_pC, 2e-6) || !near(charge.charges, told.charges, 2) || !near(charge.per_um2, told.per_um2, 0.01) || charge.marks !== Math.round(told.on_piece)) problems.push(`charge ${charge.coulombs * 1e12} pC, ${charge.charges}, ${charge.per_um2}, ${charge.marks} marks`);
      }
      return problems;
    };
    const report = (state_) => {
      const terms = (state_.closeup.arrows?.terms || []).map((term) => `${term.id} (z ${term.valence}, ${term.inside.toFixed(4)} mM in, ${term.outside} mM out): concentration ${(term.size.concentration * 1000).toFixed(3)} mV ${term.drives.concentration}, voltage ${(term.size.electrical * 1000).toFixed(3)} mV ${term.drives.electrical}, left ${(term.size.sum * 1000).toFixed(3)} mV ${term.drives.sum}`);
      const charge = state_.closeup.charge;
      return `cell_${state_.closeup.cell} at ${state_.time.toFixed(0)} s, ${(state_.closeup.arrows ? state_.closeup.arrows.terms[0].voltage * 1000 : charge.voltage * 1000).toFixed(3)} mV: ${terms.join("; ")}${charge ? `; charge ${(charge.coulombs * 1e12).toFixed(4)} pC, ${Math.round(charge.charges).toLocaleString("en-US")} charges, ${Math.round(charge.per_um2).toLocaleString("en-US")} per square micrometre, ${charge.on_piece.toFixed(2)} on the piece, ${charge.marks} marks of ${charge.worth} at each face, ${charge.inside} inside` : ""}`;
    };
    // The charge beside the arrows, with a real press: its own channel.
    await press(option("surface", "membrane-charge"));
    s = await until((seen) => JSON.stringify(seen.closeup?.layers) === '["membrane-charge","ion-push-pull"]' && Boolean(seen.closeup.charge) && seen.keys.includes("charges") && /marks stand at the inner face/.test(seen.panel?.text || ""));
    await rest();
    s = await state();
    same = await consistent();
    check("Charge on the membrane row shows beside the arrows: capacitance times voltage, as many marks at each face as charges on the piece", JSON.stringify(s.closeup?.layers) === '["membrane-charge","ion-push-pull"]' && same.charge === true && same.marks[1].length === 2 && same.marks[1].every((count) => count === same.marks[0]), JSON.stringify([s.closeup?.layers, same.charge, same.marks]));
    note(report(s));
    if (reference?.cells?.[String(first.number)]) {
      const problems = against(s, first.number);
      check(`the numbers of cell_${first.number} are those worked out outside the viewer in 64 bits`, problems.length === 0, problems.join("; ") || "all within what 32-bit storage allows");
    }
    check("the legend names the marks and the arrows, and stays within the window", s.keys.includes("charges") && s.keys.includes("arrow-hollow") && s.keys.includes("arrow-faint") && s.keys.includes("arrow-solid") && s.legendBox[0] >= 0 && s.legendBox[1] <= HEIGHT, JSON.stringify([s.keys, s.legendBox]));
    check("the chosen cell's panel gives the numbers of the moment, each with the way it drives the ion", /On its membrane at 19 min 30 s/.test(s.panel?.text || "") && /Push of the concentration difference: [\d.]+ mV (into|out of) the cell/.test(s.panel.text) && /marks stand at the inner face/.test(s.panel.text), (s.panel?.text || "").slice(0, 400));
    note(`a frame with the close-up: ${s.frame} ms`);
    await shot("closeup");
    // What stands behind them: the panel opens, and the cell stays chosen.
    await press("cells-legend .layer-details");
    s = await until((seen) => seen.panel?.title === "What the layers show");
    const said = s.panel?.text || "";
    check("the panel on what the layers show leaves the close-up where it is, and says the rule and each input", s.closeup?.cell === first.number && s.panel?.title === "What the layers show" && /Worked out by the viewer from the saved membrane voltage and concentration of each ion in the cell, with the concentration of each ion outside, the temperature and each ion's valence as the run's definition gives them/.test(said) && /capacitance times voltage/.test(said) && /the viewer's reading of the run's own files, not a declaration by the run/.test(said) && /A held bath keeps its composition/.test(said), `${s.closeup?.cell}; ${said.slice(0, 300)}`);
    // Another cell: the close-up is for that one. Chosen as the page's list would choose it, so that any cell can be reached.
    const second = wanted.find((number) => number !== first.number) ?? (first.number === 0 ? 1 : 0);
    await evaluate(`${V}.select("cell:${second}", { fly: true })`);
    s = await until((seen) => seen.closeup?.cell === second && (seen.closeup.words || []).some((text) => text.startsWith(`Membrane of cell_${second} at`)) && Boolean(seen.closeup.arrows) && Boolean(seen.closeup.charge));
    await rest();
    s = await state();
    same = await consistent();
    check("another cell chosen: the close-up is that cell's, with that cell's numbers", s.closeup?.cell === second && same.arrows.every(Boolean) && same.charge === true && new RegExp(`^Membrane of cell_${second} at`).test((s.closeup.words || []).find((text) => text.startsWith("Membrane of")) || ""), JSON.stringify([s.closeup?.cell, same]));
    note(report(s));
    if (reference?.cells?.[String(second)]) {
      const problems = against(s, second);
      check(`the numbers of cell_${second} are those worked out outside the viewer in 64 bits`, problems.length === 0, problems.join("; ") || "all within what 32-bit storage allows");
    }
    // Bold draws the same numbers more strongly.
    const quiet = JSON.stringify([s.closeup.arrows.terms.map((term) => term.size), s.closeup.charge.marks]);
    await press(option("strength", "bold"));
    s = await until((seen) => seen.strength === "bold" && (seen.closeup?.words || []).filter((text) => /^\d+$/.test(text)).length >= 2);
    check("Bold draws the same numbers more strongly, with a number at each part's tip", s.strength === "bold" && JSON.stringify([s.closeup.arrows.terms.map((term) => term.size), s.closeup.charge.marks]) === quiet && s.closeup.words.filter((text) => /^\d+$/.test(text)).length >= 2, JSON.stringify([s.strength, s.closeup.words]));
    await shot("closeup-bold");
    await press(option("strength", "quiet"));
    await until((seen) => seen.strength === "quiet");
    // The time moves: the close-up follows the record shown.
    const beforeTime = s.closeup.arrows.terms[0].voltage;
    await evaluate(`${L}.seek(0)`);
    s = await until((seen) => (seen.closeup?.words || []).some((text) => /^Membrane of .* at 0\.0 s/.test(text)) && seen.closeup.arrows?.terms[0].voltage !== beforeTime);
    same = await consistent();
    check("moved to the first record, the close-up shows that record's numbers and says its time", s.closeup.arrows.terms[0].voltage !== beforeTime && same.arrows.every(Boolean) && same.charge === true && /at 0\.0 s/.test((s.closeup.words || []).find((text) => text.startsWith("Membrane of")) || ""), JSON.stringify([s.closeup.arrows.terms[0].voltage, s.closeup.words[0]]));
    note(report(s));
    // No cell chosen: the close-up goes; the layers stay on and wait.
    await evaluate(`${V}.select(null)`);
    s = await until((seen) => seen.closeup === null && /Choose a cell/.test(seen.hint || ""));
    check("with no cell chosen the close-up is gone, and the layers wait for a cell", s.closeup === null && s.on.includes("ion-push-pull") && s.on.includes("membrane-charge") && /Choose a cell/.test(s.hint || ""), JSON.stringify([s.closeup, s.on, s.hint]));
    // A cell chosen again, and the layers switched off with real presses: the close-up goes with the last of them.
    await evaluate(`${V}.select("cell:${first.number}", { fly: true })`);
    await until((seen) => seen.closeup?.cell === first.number);
    await press(option("arrows", ""));
    s = await until((seen) => JSON.stringify(seen.closeup?.layers) === '["membrane-charge"]' && !seen.keys.includes("arrow-solid"));
    check("Off on the arrows row leaves the marks of the charge on the close-up", JSON.stringify(s.closeup?.layers) === '["membrane-charge"]' && !s.keys.includes("arrow-solid"), JSON.stringify([s.closeup?.layers, s.keys]));
    await press(option("surface", ""));
    s = await until((seen) => seen.closeup === null && !seen.on.includes("membrane-charge"));
    check("Off on the membrane row takes the close-up away; the cell stays chosen and the sheet is as it always was", s.closeup === null && s.selected === `cell:${first.number}` && JSON.stringify(s.on) === JSON.stringify(["voltage-tint", "voltage-relief"]), JSON.stringify([s.closeup, s.selected, s.on]));
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
      note(`${item.name}: ${JSON.stringify({ size: [width, height], run: s.run, on: s.on, strength: s.strength, time: s.time, drops: s.drops, bar: s.bar, tallest_cells: Number((s.tallest / s.pitch).toFixed(2)), frame_ms: s.frame, rows: s.rows, cannot: s.cannot, legend: s.legendBox, closeup: s.closeup && { cell: s.closeup.cell, layers: s.closeup.layers, placed: s.closeup.placed, words: s.closeup.words } })}`);
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
