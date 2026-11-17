#!/usr/bin/env node
// Checks the Machines tab (schema/MACHINE_CATALOGUE.md) on the map's page with real pointer and
// key input, through the DevTools protocol, in the manner of tools/check_laws.mjs:
//
//   main     lens=machines opens the second tab on the species shown; E. coli's bench has its
//            trays, its shapes to scale and its cards; a real press on a card and on a shape's name
//            chooses it and its panel says what Cells models of it as the record does; the search
//            finds a machine by a gene; the panel's door opens the Protein atlas on its proteins; the
//            flagellar motor chosen shows its parts and, by the card's Detail, its subunits; a
//            frame at 1400 by 900 leaves room at 60 frames a second, within the draw ceiling.
//            THEME=dark: the same in the dark theme.
//   phone    on a 390 px phone the bar keeps to one row, the card folds to one line, and a machine
//            chosen opens its panel as a sheet with the picture above it.
//   address  select=machine:<id> with no lens opens the catalogue on it; lens=cell with machine=
//            and select=machine:<id> keeps the Cell view's closer view (one machine, one identity);
//            the catalogue's "Look closer in the cell" opens that closer view, and its panel's door
//            comes back; a machine the species lacks is chosen and says which species have it; with less motion
//            a choice rises at once.
//   text     with no 3D (WebGL switched off), the List gives the groups and a machine's panel.
//   tabs     the six tabs on a phone of 360, 390 and 400 px, with the page's font and the stand-in,
//            for a species and for a model system: one row, each button at least 44 px, the List
//            whole, and every tab pressed in turn in sight.
//
//   node tools/check_catalogue.mjs [OUT_DIR]
//
// Set by the environment: CASE (main unless set), THEME (dark), NAME (what the pictures are
// called), WIDTH and HEIGHT. One browser at a time: it takes the lock in tools/lib/browser_lock.mjs.

import { spawn } from "node:child_process";
import { writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { createServer } from "./serve.mjs";
import { acquireBrowser } from "./lib/browser_lock.mjs";
import { DEFAULT_RUNS, DEFAULT_SCENE } from "./lib/build_page.mjs";

const outDir = process.argv[2] ? path.resolve(process.argv[2]) : null;
if (outDir) await mkdir(outDir, { recursive: true });
const CASE = process.env.CASE || "main";
const PHONE = CASE === "phone" || CASE === "tabs";
const WIDTH = Number(process.env.WIDTH || (PHONE ? 390 : 1400)), HEIGHT = Number(process.env.HEIGHT || (PHONE ? 844 : 900));
const NAME = process.env.NAME || `catalogue-${CASE}`;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const results = [];
const check = (name, ok, detail = "") => {
  results.push(Boolean(ok));
  console.log(`${ok ? "pass" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`);
};
const note = (text) => console.log(`note  ${text}`);
const pageLog = [];
const release = await acquireBrowser({ wait: Number(process.env.WAIT_MINUTES || 30) * 60 * 1000 });
const server = createServer({ offline: true, scene: DEFAULT_SCENE, runs: DEFAULT_RUNS, log: (line) => pageLog.push(line) });
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}/`;
const chrome = spawn(
  process.env.CHROME || "google-chrome",
  ["--headless=new", `--user-data-dir=${release.profile}`, "--disable-breakpad", "--no-first-run", "--no-sandbox", "--mute-audio", "--hide-scrollbars", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", ...(CASE === "text" ? ["--disable-webgl", "--disable-3d-apis"] : []), `--window-size=${WIDTH},${HEIGHT}`, "--remote-debugging-port=0", "about:blank"],
  { stdio: ["ignore", "ignore", "pipe"] }
);
let failed = null, socket = null;
try {
  const endpoint = await new Promise((resolve, reject) => {
    let text = "";
    chrome.stderr.on("data", (chunk) => {
      text += chunk;
      const match = text.match(/DevTools listening on (ws:\/\/\S+)/);
      if (match) resolve(match[1]);
    });
    setTimeout(() => reject(new Error("Chrome did not report a DevTools address")), 30000);
  });
  socket = new WebSocket(endpoint);
  await new Promise((resolve, reject) => ((socket.onopen = resolve), (socket.onerror = reject)));
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
  const size = (width, height) => page("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: width < 760 });
  await size(WIDTH, HEIGHT);
  const media = (features) => page("Emulation.setEmulatedMedia", { features });
  await media([{ name: "prefers-color-scheme", value: process.env.THEME === "dark" ? "dark" : "light" }]);
  await page("Page.enable");
  await page("Page.addScriptToEvaluateOnNewDocument", {
    source: `window.__pageErrors = []; addEventListener("error", (event) => __pageErrors.push(String(event.error?.stack || event.message))); addEventListener("unhandledrejection", (event) => __pageErrors.push("rejection: " + String(event.reason?.stack || event.reason)));`,
  });
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
  const type = async (text) => {
    for (const letter of text) await page("Input.dispatchKeyEvent", { type: "char", text: letter });
    await sleep(500);
  };
  /** The middle of what an expression finds, if it is on the screen and nothing lies over it. */
  const placeOf = (expression) =>
    evaluate(`(() => { const root = ${V}.shadowRoot, el = ${expression}; if (!el) return null; el.scrollIntoView({ block: "nearest", inline: "nearest" }); const r = el.getBoundingClientRect(); if (!r.width || !r.height) return null; const x = r.left + r.width / 2, y = r.top + r.height / 2; const top = root.elementFromPoint(x, y); return top && (top === el || el.contains(top)) ? { x, y, words: el.textContent } : null; })()`);
  const until = async (test, tries = 120) => {
    for (let k = 0; k < tries; k++) {
      if (await evaluate(test).catch(() => false)) return true;
      await sleep(250);
    }
    return false;
  };
  const shot = async (name) => {
    if (!outDir) return;
    await evaluate(`new Promise((done) => { ${V}.stage?.invalidate(); requestAnimationFrame(() => requestAnimationFrame(done)); })`);
    await sleep(300);
    const { data } = await page("Page.captureScreenshot", { format: "png" });
    await writeFile(path.join(outDir, `${name}.png`), Buffer.from(data, "base64"));
    note(`wrote ${path.join(outDir, `${name}.png`)}`);
  };
  const open = async (query, settle = 2200) => {
    await page("Page.navigate", { url: `${base}?${query}` });
    const up = await until(CASE === "text" ? `Boolean(${V}?.model)` : `Boolean(${V}?.current)`, 240);
    await sleep(settle);
    return up;
  };
  const state = () =>
    evaluate(`(() => {
      const v = ${V}, root = v.shadowRoot, lens = v.current, panel = root.querySelector("cells-panel");
      return { lens: v.state.lens, species: v.state.species, selected: v.state.selected, insets: v.stage?.insets || {},
        panel: panel && !panel.hidden ? panel.textContent : "", doors: panel && !panel.hidden ? [...panel.querySelectorAll(".panel-door button")].map((b) => b.textContent) : [],
        views: [...root.querySelectorAll(".switch button")].map((b) => ({ id: b.dataset.lens, pressed: b.getAttribute("aria-pressed"), words: b.textContent })),
        legend: [...root.querySelectorAll("cells-legend .legend-item, cells-legend [data-id]")].map((el) => el.textContent.trim()).filter(Boolean),
        level: lens?.built?.get?.(v.state.selected)?.level ?? null, query: lens?.query ?? null, mode: lens?.mode ?? null, cost: lens?.cost?.() ?? null };
    })()`);
  /** Where an item of the bench stands on the screen: its top's middle. */
  const itemAt = (id) =>
    evaluate(`(() => { const v = ${V}, item = v.current.layout.items.find((value) => value.id === ${JSON.stringify(id)}); if (!item) return null; const THREE_V = v.current.root.position.clone(); const p = THREE_V.set(item.x, item.y + item.h + (v.current.lifts.get(item.id) || 0), item.z); const q = v.stage.project(p, p.clone()); const r = v.canvas.getBoundingClientRect(); return { x: r.left + q.x, y: r.top + q.y }; })()`);
  const press = async (selector, wait) => {
    const at = await placeOf(`root.querySelector(${JSON.stringify(selector)})`);
    if (at) await click(at.x, at.y, wait);
    return at;
  };
  const errorsAtEnd = async () => {
    const errors = pageLog.filter((line) => /error|exception|rejection|blocked/i.test(line));
    check("the page logged no error", errors.length === 0, errors.slice(0, 3).join(" / "));
    const thrown = await evaluate(`(window.__pageErrors || []).slice(0, 3)`);
    check("the page threw no error", thrown.length === 0, thrown.join(" / "));
  };

  if (CASE === "main") {
    // ---------------------------------------------------------- the second tab, on E. coli
    check("the page opens on lens=machines with E. coli", await open("lens=machines&entry=ecoli", 3500));
    let s = await state();
    check("the switch offers six views, Machines second and pressed", s.views.length === 6 && s.views[1]?.id === "machines" && s.views[1].pressed === "true", JSON.stringify(s.views));
    const layout = await evaluate(`(() => { const lens = ${L}; return { trays: lens.layout.trays.map((t) => t.group), shapes: lens.layout.items.filter((i) => i.type === "shape").map((i) => i.id), cards: lens.layout.items.filter((i) => i.type === "card").length, sized: lens.counts.sized, machines: lens.counts.machines, scale: Boolean(lens.scaleBar), measured: Object.keys(lens.measured) }; })()`);
    check("E. coli's bench: six trays; its machines measured from structures and the flagellar motor from its own file drawn to scale, the rest cards; the scale bar", layout.trays.length === 6 && layout.shapes.includes("machine:flagellar-motor") && layout.shapes.length === layout.sized && layout.shapes.length + layout.cards === layout.machines && layout.shapes.length >= 7 && layout.scale && layout.measured.includes("machine:flagellar-motor"), JSON.stringify(layout));
    const legend = await evaluate(`${L}.chrome().legend.items.map((item) => item.id)`);
    check("the legend names the shape, the card and the choice, and each group", ["mach-sized", "mach-card", "mach-chosen"].every((id) => legend.includes(id)) && legend.filter((id) => id.startsWith("mach-g-")).length === 6, legend.join(" "));
    await shot(`${NAME}-bench`);
    // A real press on a card.
    const card = await itemAt("machine:rna-polymerase");
    if (card) await click(card.x, card.y, 1500);
    s = await state();
    // The record's words are read from the catalogue the page carries, not written here.
    const records = await evaluate(`(() => { const c = ${L}.catalogue, own = c.kinds.get("atp-synthase").records.find((line) => typeof line === "object"); return { fr13: c.record("fr13").status, own: own ? { status: own.status, label: c.record(own.ref).label.split(",")[0] } : null }; })()`);
    const escaped = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    check("a real press on the RNA polymerase's card chooses it; its panel says what FR-13 states, and nothing is modelled", s.selected === "machine:rna-polymerase" && new RegExp(`What Cells models of it: FR-13: ${escaped(records.fr13)}`).test(s.panel) && !/(?<!not )modelled/i.test(s.panel), JSON.stringify([card, s.selected, records.fr13, s.panel.slice(0, 160)]));
    check("its panel's door opens the Protein atlas on its 7 proteins", s.doors.some((door) => /Show its 7 proteins in the Protein atlas/.test(door)), JSON.stringify(s.doors));
    // The ATP synthase: "planned, first", on D209's line alone.
    await evaluate(`${V}.select("machine:atp-synthase", { fly: true })`);
    await sleep(1200);
    s = await state();
    check("the ATP synthase's panel gives its own record line, with its status and its decision", Boolean(records.own) && s.panel.includes(records.own.status) && s.panel.includes(records.own.label), JSON.stringify([records.own, s.panel.slice(0, 220)]));
    // The search.
    const field = await placeOf(`root.querySelector("#cells-find")`);
    if (field) await click(field.x, field.y, 300);
    await type("rpoB");
    s = await state();
    const found = await evaluate(`${L}.chrome().legend.items.find((item) => item.id === "mach-found")?.count ?? null`);
    check("typing a gene in the card's search finds its machine, and the field keeps its focus", s.query === "rpoB" && found === 1 && (await evaluate(`${V}.shadowRoot.activeElement?.id || null`)) === "cells-find", JSON.stringify([s.query, found]));
    await shot(`${NAME}-search`);
    await evaluate(`${L}.setQuery(""); ${V}.renderChrome()`);
    const home = async () => {
      await evaluate(`(() => { const v = ${V}; v.select(null); v.stage.rig.setView(v.current.homeView()); })()`);
      await sleep(1200);
    };
    await home();
    // A shape chosen by its name on the picture: the flagellar motor's, then the ribosome (a shape or a card, as its species' file has its size).
    const named = await placeOf(`root.querySelector('[data-label="machine:flagellar-motor"]')`);
    if (named) await click(named.x, named.y, 1500);
    s = await state();
    check("a real press on the flagellar motor's name on the picture chooses it, drawn to scale", s.selected === "machine:flagellar-motor" && /Drawn to scale/.test(s.panel), JSON.stringify([named, s.selected]));
    await home();
    const ribosome = await itemAt("machine:ribosome");
    if (ribosome) await click(ribosome.x, ribosome.y, 1500);
    s = await state();
    const sized = await evaluate(`Boolean(${L}.item("machine:ribosome")?.sized)`);
    check("a real press on the ribosome chooses it; its size is the viewer's own measure from a structure, with its entry", s.selected === "machine:ribosome" && sized && /The viewer's own measure from Protein Data Bank entry \w{4}/.test(s.panel), JSON.stringify([ribosome, s.selected, sized]));
    const parts = await evaluate(`[...(${L}.built.get("machine:ribosome")?.ids || [])]`);
    const shades = await evaluate(`${L}.built.get("machine:ribosome")?.group.children.map((mesh) => mesh.material.color.getHexString()) ?? []`);
    check("chosen, the ribosome shows its two measured subunits, each a part that can be chosen, in shades of their own", parts.length === 2 && parts.every((id) => /^machine:ribosome:(large|small)$/.test(id)) && shades.length === 2 && shades[0] !== shades[1], JSON.stringify([parts, shades]));
    check("the ribosome's panel keeps the map's status of the Cell view's ribosomes and FR-13's line", /Planned/.test(s.panel) && /FR-13/.test(s.panel) && /CELL_STRUCTURES/.test(s.panel), s.panel.slice(0, 200));
    // Its door into the Protein atlas, pressed.
    const door = await placeOf(`[...root.querySelectorAll("cells-panel .panel-door button")].find((button) => /Protein atlas/.test(button.textContent))`);
    if (door) await click(door.x, door.y, 2500);
    for (let tries = 0; tries < 60 && (await state()).mode !== "own"; tries++) await sleep(250);
    s = await state();
    check("the door opens the Protein atlas on E. coli's own proteins", s.lens === "proteins" && s.mode === "own", JSON.stringify([s.lens, s.mode]));
    // Back to Machines, the motor.
    await press('.switch [data-lens="machines"]', 1500);
    await evaluate(`${V}.select("machine:flagellar-motor", { fly: true })`);
    await sleep(2200);
    s = await state();
    check("the flagellar motor chosen shows its parts (level 2), and its panel offers its closer view", s.selected === "machine:flagellar-motor" && s.level === 2 && s.doors.some((value) => /Look closer in the cell/.test(value)), JSON.stringify([s.selected, s.level, s.doors]));
    const subunits = await placeOf(`root.querySelector('[data-show="3"]')`);
    if (subunits) await click(subunits.x, subunits.y, 1500);
    s = await state();
    check("the card's Detail shows its subunits (level 3)", s.level === 3, JSON.stringify([subunits, s.level]));
    await shot(`${NAME}-motor`);
    // The ATP synthase, the machine the engine plans first: its measured parts, then each chain, by the card's Detail.
    await evaluate(`${V}.select("machine:atp-synthase", { fly: true })`);
    await sleep(2200);
    let atp = await evaluate(`(() => { const b = ${L}.built.get("machine:atp-synthase"); return { level: b?.level, ids: [...(b?.ids || [])] }; })()`);
    check("the ATP synthase chosen stands as its five measured parts: head, two stalks, the ring and the stator's foot", atp.level === 2 && ["head", "central-stalk", "peripheral-stalk", "ring", "stator-foot"].every((part) => atp.ids.includes(`machine:atp-synthase:${part}`)), JSON.stringify(atp));
    await shot(`${NAME}-atp-parts`);
    const chains = await placeOf(`root.querySelector('[data-show="3"]')`);
    if (chains) await click(chains.x, chains.y, 1500);
    atp = await evaluate(`(() => { const b = ${L}.built.get("machine:atp-synthase"); return { level: b?.level, ids: b?.ids.size }; })()`);
    check("a real press on the card's Subunits shows its 22 chains", atp.level === 3 && atp.ids === 22, JSON.stringify([chains, atp]));
    await shot(`${NAME}-atp-subunits`);
    // A frame at this size: the view's own work, the labels and the draw, within a frame at 60 a second, and the draw ceiling.
    await evaluate(`${V}.select(null); ${V}.current.stage.rig.setView(${V}.current.homeView())`);
    await sleep(1200);
    const cost = await evaluate(`(() => {
      const v = ${V}, stage = v.stage, lens = v.current;
      const time = (fn, n = 20) => { const times = []; for (let i = 0; i < n; i++) { const t = performance.now(); fn(); times.push(performance.now() - t); } times.sort((a, b) => a - b); return Math.round(times[Math.floor(n / 2)] * 100) / 100; };
      return { update: time(() => lens.update(16)), labels: time(() => v.labels.layout()), draw: time(() => { stage.renderer.render(stage.scene, stage.camera); stage.renderer.getContext().finish(); }, 12), cost: lens.cost(),
        renderer: (() => { const gl = stage.renderer.getContext(), info = gl.getExtension("WEBGL_debug_renderer_info"); return String(info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)); })() };
    })()`);
    note(`${WIDTH} by ${HEIGHT}: ${JSON.stringify(cost)} (milliseconds, the median)`);
    check(`${WIDTH} by ${HEIGHT}: the view's work, its labels and the draw leave room at 60 frames a second`, cost.update + cost.labels + cost.draw < 16.7, JSON.stringify(cost));
    check("a frame draws within the ceiling the tests hold (90 draws, 40,000 triangles)", cost.cost.draws <= 90 && cost.cost.triangles <= 40000, JSON.stringify(cost.cost));
    // While a card rises (with motion), each frame's update of the view, timed.
    const rising = await evaluate(`(() => {
      const v = ${V}, lens = v.current, still = v.stage.reducedMotion;
      v.stage.reducedMotion = false;
      v.select("machine:rna-polymerase");
      const times = [];
      for (let i = 0; i < 60; i++) { const t = performance.now(); const moving = lens.update(16); times.push(performance.now() - t); if (!moving) break; }
      v.stage.reducedMotion = still;
      times.sort((a, b) => a - b);
      return { frames: times.length, median: Math.round(times[Math.floor(times.length / 2)] * 100) / 100, most: Math.round(times.at(-1) * 100) / 100 };
    })()`);
    note(`while a card rises: ${JSON.stringify(rising)} (milliseconds of the view's update for each frame)`);
    check(`${WIDTH} by ${HEIGHT}: while a chosen card rises, the view's update on each frame leaves room at 60 frames a second`, rising.frames > 1 && rising.most < 8, JSON.stringify(rising));
    // Another species: the planarian has no machine with a size in hand, and says so.
    await evaluate(`${V}.setSpecies("planarian")`);
    await sleep(1500);
    const planarian = await evaluate(`(() => { const lens = ${L}; return { cards: lens.layout.items.filter((i) => i.type === "card").length, shapes: lens.layout.items.filter((i) => i.type === "shape").length, notice: lens.chrome().card.notice }; })()`);
    check("the planarian's bench is all cards, the law inventory's units among them, and the card says why", planarian.shapes === 0 && planarian.cards > 30 && /no size in hand|each is a card/i.test(planarian.notice || ""), JSON.stringify(planarian));
    await shot(`${NAME}-planarian`);
    await errorsAtEnd();
  } else if (CASE === "phone") {
    check("the page opens on lens=machines with E. coli, on a phone", await open("lens=machines&entry=ecoli", 3500));
    const bar = await evaluate(`(() => {
      const root = ${V}.shadowRoot, shown = (el) => Boolean(el) && el.getClientRects().length > 0;
      const kids = [...root.querySelector(".bar").children].filter(shown).map((el) => el.getBoundingClientRect()).filter((r) => r.width > 1);
      const presses = [...root.querySelectorAll(".bar button")].filter(shown).map((el) => { const r = el.getBoundingClientRect(); return Math.round(Math.min(r.width, r.height)); });
      const box = root.querySelector(".switch").getBoundingClientRect(), pressed = root.querySelector('.switch [aria-pressed="true"]').getBoundingClientRect();
      const toggle = root.querySelector(".view-toggle");
      return { row: kids.every((a) => kids.every((b) => a.top < b.bottom - 1 && b.top < a.bottom - 1)), least: Math.min(...presses), seen: pressed.left >= box.left - 0.5 && pressed.right <= box.right + 0.5, sideways: document.documentElement.scrollWidth > innerWidth + 1, folded: shown(toggle) ? toggle.textContent : null };
    })()`);
    check(`on a ${WIDTH} px phone the bar keeps to one row, each button at least 44 px, the Machines tab in sight`, bar.row && bar.least >= 44 && bar.seen && !bar.sideways, JSON.stringify(bar));
    check("the card is folded to one line under the bar, naming the catalogue", /Machines/.test(bar.folded || ""), JSON.stringify(bar.folded));
    await shot(`${NAME}-rest`);
    await evaluate(`${V}.select("machine:flagellar-motor", { fly: true })`);
    await sleep(2500);
    const s = await state();
    check("a machine chosen opens its panel as a sheet, and the picture keeps room above it", s.selected === "machine:flagellar-motor" && s.insets.bottom > 0 && !s.insets.left, JSON.stringify(s.insets));
    const motor = await itemAt("machine:flagellar-motor");
    const sheet = await evaluate(`(() => { const p = ${V}.shadowRoot.querySelector("cells-panel"); const r = p.getBoundingClientRect(); return Math.round(r.top); })()`);
    check("the chosen motor stands in the picture, above the sheet", Boolean(motor) && motor.x >= 0 && motor.x <= WIDTH && motor.y >= 56 && motor.y <= sheet, JSON.stringify([motor, sheet]));
    await shot(`${NAME}-motor`);
    await errorsAtEnd();
  } else if (CASE === "address") {
    check("select=machine:ribosome&entry=syn3a, with no lens, opens the catalogue on Syn3A's ribosome", (await open("select=machine:ribosome&entry=syn3a", 3000)) && (await state()).lens === "machines" && (await state()).selected === "machine:ribosome");
    let s = await state();
    check("its panel says about 500 in a small cell, from its species' file", /about 500 in a small cell/.test(s.panel), s.panel.slice(0, 200));
    await shot(`${NAME}-syn3a-ribosome`);
    // The closer view keeps its own id in the Cell view.
    await open("lens=cell&entry=ecoli&machine=flagellar-motor&select=machine:flagellar-motor", 6000);
    s = await state();
    check("lens=cell with machine= and select=machine:flagellar-motor keeps the Cell view's closer view (one id, its own view)", s.lens === "cell" && s.selected === "machine:flagellar-motor", JSON.stringify([s.lens, s.selected]));
    check("the closer view's panel offers a door into the Machines catalogue", s.doors.some((value) => /Machines catalogue/.test(value)), JSON.stringify(s.doors));
    const into = await placeOf(`[...root.querySelectorAll("cells-panel .panel-door button")].find((button) => /Machines catalogue/.test(button.textContent))`);
    if (into) await click(into.x, into.y, 2500);
    s = await state();
    check("and a real press on it opens the catalogue on the motor", s.lens === "machines" && s.selected === "machine:flagellar-motor", JSON.stringify([s.lens, s.selected]));
    const closer = await placeOf(`[...root.querySelectorAll("cells-panel .panel-door button")].find((button) => /Look closer in the cell/.test(button.textContent))`);
    if (closer) await click(closer.x, closer.y, 1000);
    await until(`${V}.state.lens === "cell" && ${V}.state.selected === "machine:flagellar-motor"`, 80);
    s = await state();
    check("the catalogue's Look closer in the cell opens the Cell view's closer view of the same machine", s.lens === "cell" && s.selected === "machine:flagellar-motor", JSON.stringify([s.lens, s.selected]));
    // A machine the species lacks.
    await open("lens=machines&entry=planarian&select=machine:flagellar-motor", 2500);
    s = await state();
    check("a machine the species shown lacks is chosen, and its panel says which species have it", s.selected === "machine:flagellar-motor" && /Not listed for Planarian/.test(s.panel) && /E\. coli/.test(s.panel), JSON.stringify([s.selected, s.panel.slice(0, 160)]));
    // Less motion: a choice rises at once.
    await media([{ name: "prefers-reduced-motion", value: "reduce" }]);
    await open("lens=machines&entry=ecoli", 2500);
    await evaluate(`${V}.select("machine:ribosome")`);
    await sleep(120);
    const lift = await evaluate(`${L}.lifts.get("machine:ribosome") ?? null`);
    check("with less motion the chosen machine stands lifted at once", Math.abs((lift ?? 0) - 0.7) < 1e-3, String(lift));
    await errorsAtEnd();
  } else if (CASE === "text") {
    check("with WebGL off the page opens on lens=machines with E. coli", await open("lens=machines&entry=ecoli", 1500));
    const said = await evaluate(`${V}.shadowRoot.querySelector(".fallback")?.textContent || ""`);
    check("it says that 3D is not available", /3D drawing is not available/.test(said), said);
    const listed = await evaluate(`${V}.sections().map((section) => [section.label, section.entities.length])`);
    check("the List holds E. coli's machines by group", listed.length === 6 && listed.some(([label, n]) => label === "Moving, sensing and attaching" && n === 2), JSON.stringify(listed));
    await evaluate(`${V}.select("machine:ribosome")`);
    await sleep(600);
    const s = await state();
    check("a machine chosen from the List has its panel", s.selected === "machine:ribosome" && /Making proteins/.test(s.panel) && /FR-13/.test(s.panel), s.panel.slice(0, 160));
    await evaluate(`${V}.setSpecies("planarian")`);
    await sleep(400);
    const units = await evaluate(`${V}.sections().find((section) => /units of the law inventory/.test(section.label))?.entities.length ?? 0`);
    check("the planarian's List holds the law inventory's units", units > 30, String(units));
    await errorsAtEnd();
  } else if (CASE === "tabs") {
    // The six tabs on a phone: one row, each button at least 44 px, the List whole, and every tab pressed in sight.
    const lettered = `document.fonts.status === "loaded" && ["Inter", "Space Grotesk"].every((family) => [...document.fonts].some((face) => face.family.includes(family) && face.status === "loaded"))`;
    const barNow = () =>
      evaluate(`(() => {
        const root = ${V}.shadowRoot, shown = (el) => Boolean(el) && el.getClientRects().length > 0;
        const kids = [...root.querySelector(".bar").children].filter(shown).map((el) => el.getBoundingClientRect()).filter((r) => r.width > 1);
        const presses = [...root.querySelectorAll(".bar button")].filter(shown).map((el) => { const r = el.getBoundingClientRect(); return Math.round(Math.min(r.width, r.height)); });
        const box = root.querySelector(".switch").getBoundingClientRect(), pressed = root.querySelector('.switch [aria-pressed="true"]').getBoundingClientRect(), list = root.querySelector(".bar-end .pill-button");
        return { row: kids.every((a) => kids.every((b) => a.top < b.bottom - 1 && b.top < a.bottom - 1)), least: Math.min(...presses), seen: pressed.left >= box.left - 0.5 && pressed.right <= box.right + 0.5, list: list.scrollWidth <= list.clientWidth + 1 && list.getBoundingClientRect().right <= innerWidth, squeeze: root.querySelector(".bar").dataset.squeeze || "", sideways: document.documentElement.scrollWidth > innerWidth + 1, tabs: [...root.querySelectorAll(".switch button")].length };
      })()`);
    for (const width of [360, 390, 400]) {
      await size(width, 800);
      // A model system shown in the Experiments tab's place (example=gard): the bar is as tight there, and the List stays whole.
      await open("lens=experiments&example=gard", 2500);
      await until(`${V}.state.example === "gard" && Boolean(${V}.current)`, 60);
      if (await until(lettered, 40)) await evaluate(`${V}.renderChrome()`);
      const inTab = await barNow();
      const listShown = await evaluate(`(() => { const list = ${V}.shadowRoot.querySelector(".bar-end .pill-button"), end = list.parentElement.getBoundingClientRect(), box = list.getBoundingClientRect(); return box.left >= end.left - 0.5 && box.right <= end.right + 0.5 && box.right <= innerWidth; })()`);
      check(`${width} px, a model system shown in the Experiments tab: its tab is in sight, the bar on one row, every button at least 44 px, the List whole and not cut by the bar's end`, inTab.row && inTab.least >= 44 && inTab.seen && inTab.list && listShown && !inTab.sideways && inTab.tabs === 6, JSON.stringify({ ...inTab, listShown }));
      for (const entry of ["planarian", "gard"]) {
        for (const font of ["the page's own font", "the stand-in font"]) {
          await open(`lens=cell&entry=${entry}`, 2500);
          if (font === "the stand-in font") await evaluate(`(async () => { document.querySelector('link[href*="fonts.googleapis"]')?.remove(); await new Promise((resolve) => setTimeout(resolve, 400)); ${V}.renderChrome(); })()`);
          else if (await until(lettered, 40)) await evaluate(`${V}.renderChrome()`);
          const seen = [];
          for (const lens of ["cell", "machines", "proteins", "engine", "laws", "experiments"]) {
            const at = await placeOf(`root.querySelector('.switch [data-lens="${lens}"]')`);
            if (at) await click(at.x, at.y, 900);
            const bar = await barNow();
            seen.push({ lens, pressed: await evaluate(`${V}.state.lens`), ...bar });
          }
          const ok = seen.every((item) => item.pressed === item.lens && item.row && item.least >= 44 && item.seen && item.list && !item.sideways && item.tabs === 6);
          check(`${width} px, ${entry === "gard" ? "a model system" : "a species"}, ${font}: each of the six tabs pressed in turn is in sight, the bar on one row, every button at least 44 px, the List whole`, ok, JSON.stringify(seen.filter((item) => !(item.pressed === item.lens && item.row && item.least >= 44 && item.seen && item.list && !item.sideways)).slice(0, 2).concat([{ squeeze: seen[0].squeeze }])));
          if (width === 360 && font === "the stand-in font") {
            await shot(`${NAME}-${width}-${entry}-standin`);
            // A visitor's own scroll of the row holds when the page draws its chrome again.
            const held = await evaluate(`(() => { const v = ${V}, box = v.shadowRoot.querySelector(".switch"); box.scrollLeft = 0; const at = box.scrollLeft; v.renderChrome(); return { at, after: box.scrollLeft, more: box.scrollWidth - box.clientWidth }; })()`);
            check(`${width} px, ${entry === "gard" ? "a model system" : "a species"}: a visitor's own scroll of the tab row holds when the page draws its chrome again`, held.more > 1 && Math.abs(held.after - held.at) < 1, JSON.stringify(held));
          }
        }
      }
    }
    await errorsAtEnd();
  } else throw new Error(`no case ${CASE}`);
} catch (error) {
  failed = error;
} finally {
  socket?.close();
  const closed = new Promise((resolve) => chrome.once("close", resolve));
  chrome.kill();
  await Promise.race([closed, sleep(4000)]);
  if (chrome.exitCode === null && chrome.signalCode === null) chrome.kill("SIGKILL");
  await Promise.race([closed, sleep(2000)]);
  server.close();
  release();
}
if (failed) {
  console.error(`check_catalogue: ${failed.stack || failed}`);
  process.exit(2);
}
const passed = results.filter(Boolean).length;
console.log(`${passed} of ${results.length} checks passed`);
process.exit(passed === results.length ? 0 : 1);
