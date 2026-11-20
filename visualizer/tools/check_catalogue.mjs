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
import { within } from "./lib/measures.mjs";

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
    const layout = await evaluate(`(() => { const lens = ${L}; return { trays: lens.layout.trays.map((t) => t.group), shapes: lens.layout.items.filter((i) => i.type === "shape").map((i) => i.id), cards: lens.layout.items.filter((i) => i.type === "card").length, sized: lens.counts.sized, machines: lens.counts.machines, scale: Boolean(lens.scaleBar), measured: Object.keys(lens.measured), groups: lens.catalogue.counts("ecoli").groups }; })()`);
    check("E. coli's bench: a tray for each of its groups; its machines measured from structures and the flagellar motor from its own file drawn to scale, the rest cards; the scale bar", layout.trays.length === layout.groups && layout.groups >= 8 && layout.shapes.includes("machine:flagellar-motor") && layout.shapes.length === layout.sized && layout.shapes.length + layout.cards === layout.machines && layout.shapes.length >= 7 && layout.scale && layout.measured.includes("machine:flagellar-motor"), JSON.stringify(layout));
    const legend = await evaluate(`${L}.chrome().legend.items.map((item) => item.id)`);
    check("the legend names the shape, the card and the choice, and each group", ["mach-sized", "mach-card", "mach-chosen"].every((id) => legend.includes(id)) && legend.filter((id) => id.startsWith("mach-g-")).length === (await evaluate(`${L}.catalogue.counts("ecoli").groups`)), legend.join(" "));
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
    const shades = await evaluate(`${L}.bodyColours("machine:ribosome")`);
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
    const membrane = await evaluate(`(() => { const root = ${V}.shadowRoot, label = [...root.querySelectorAll(".label")].find((el) => /Its membrane/.test(el.textContent)); return { label: label?.textContent || null, button: label?.tagName === "BUTTON", slab: Boolean(${L}.built.get("machine:atp-synthase")?.group?.children.some((child) => child.userData.slab)) }; })()`);
    check("where its membrane lies: a thin slab at the ring, named an illustration on the picture", membrane.slab && /illustration/.test(membrane.label || "") && !membrane.button, JSON.stringify(membrane));
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
    check(`${WIDTH} by ${HEIGHT}: the view's work, its labels and the draw leave room at 60 frames a second`, within(`${WIDTH} by ${HEIGHT}: the view's update, its labels and the draw on a frame (the medians, summed)`, cost.update + cost.labels + cost.draw, 16.7), JSON.stringify(cost));
    check("a frame draws within the ceiling the tests hold (40 draws, 40,000 triangles)", cost.cost.draws <= 40 && cost.cost.triangles <= 40000, JSON.stringify(cost.cost));
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
    check(`${WIDTH} by ${HEIGHT}: while a chosen card rises, the view's update on each frame leaves room at 60 frames a second`, rising.frames > 1 && within(`${WIDTH} by ${HEIGHT}: the most of the view's update on a frame while a chosen card rises`, rising.most, 8), JSON.stringify(rising));
    // Another species: the thale cress, its 80S drawn at the human's measure and its ER calcium pump at the human SERCA2b's.
    await evaluate(`${V}.setSpecies("thalecress")`);
    await sleep(1500);
    const plant = await evaluate(`(() => { const lens = ${L}; return { cards: lens.layout.items.filter((i) => i.type === "card").length, shapes: lens.layout.items.filter((i) => i.type === "shape").map((i) => i.id).sort(), notice: lens.chrome().card.notice }; })()`);
    check("the thale cress's bench: its ribosome and its ER calcium pump drawn to scale, the rest cards", JSON.stringify(plant.shapes) === JSON.stringify(["machine:ribosome", "unit.U41"]) && plant.cards >= 3 && !plant.notice, JSON.stringify(plant));
    await shot(`${NAME}-thalecress`);
    await errorsAtEnd();
  } else if (CASE === "animals") {
    // ---------------------------------------------------------- the planarian's bench: the machines the animals share
    check("the page opens on lens=machines with the planarian", await open("lens=machines&entry=planarian", 3500));
    const layout = await evaluate(`(() => { const lens = ${L}; return { shapes: lens.layout.items.filter((i) => i.type === "shape").map((i) => i.id).sort(), sized: lens.counts.sized, scale: Boolean(lens.scaleBar), outlines: lens.outlineItems.length }; })()`);
    check("the planarian's bench: the eukaryotic ribosome, the vault (since 19 November 2026) and five units of the law inventory drawn to scale, all their outlines one instanced mesh, and the scale bar", JSON.stringify(layout.shapes) === JSON.stringify(["machine:ribosome", "machine:vault", "unit.U06", "unit.U36", "unit.U39", "unit.U41", "unit.U43"]) && layout.sized === 7 && layout.scale && layout.outlines >= 6, JSON.stringify(layout));
    await shot(`${NAME}-bench`);
    // A real press on a unit's outline, at the middle of its box: the bench's instanced outlines are picked by their instance.
    const middleOf = (id) =>
      evaluate(`(() => { const v = ${V}, item = v.current.layout.items.find((value) => value.id === ${JSON.stringify(id)}); if (!item) return null; const p = v.current.root.position.clone().set(item.x, item.y + item.h / 2, item.z); const q = v.stage.project(p, p.clone()); const r = v.canvas.getBoundingClientRect(); return { x: r.left + q.x, y: r.top + q.y }; })()`);
    await evaluate(`${V}.stage.rig.setView(${V}.current.homeView())`);
    await sleep(800);
    const pump = await middleOf("unit.U39");
    if (pump) await click(pump.x, pump.y, 1800);
    let s = await state();
    check("a real press on the sodium pump's outline chooses it: its panel gives the measure, whose structure it is, and that the planarian's own is not in hand", s.selected === "unit.U39" && /7E1Z, a structure of Homo sapiens \(one of Schmidtea mediterranea: none in hand\)/.test(s.panel) && s.level === 2, JSON.stringify([pump, s.selected, s.level, s.panel.slice(0, 160)]));
    check("its panel says nothing is modelled, qualified or judged", !/(?<!not )\bmodell?ed\b|qualified|judged/i.test(s.panel), s.panel.slice(0, 200));
    // Seen close (as its panel's view of it is), a real press on one of its parts.
    await evaluate(`${V}.current.focus("unit.U39")`);
    await sleep(2200);
    // A real press on one of its parts: at a point of the part, along its own axes, that the page shows uncovered and
    // where the part is the nearest thing (its thin γ subunit lies against it, and may stand in front of its centre).
    const part = await evaluate(`(() => { const v = ${V}, lens = v.current, built = lens.built.get("unit.U39"), size = lens.item("unit.U39").size, alpha = size.parts.find((value) => value.id === "alpha");
      const r = v.canvas.getBoundingClientRect();
      for (const t of [0, 0.3, -0.3, 0.6, -0.6]) for (let k = 0; k < 3; k++) {
        const local = alpha.centre_nm.map((n, i) => (n + t * alpha.axes[k][i] * alpha.across_nm[k] / 2) / 10);
        const p = built.group.localToWorld(built.group.position.clone().set(...local)); const q = v.stage.project(p, p.clone());
        const x = r.left + q.x, y = r.top + q.y;
        const top = v.shadowRoot.elementFromPoint(x, y);
        if (top !== v.canvas && !(top && top.tagName === "CANVAS")) continue;
        if (v.stage.pick(x, y, lens.pickRoots)?.id === "unit.U39:alpha") return { x, y };
      }
      return null; })()`);
    if (part) await click(part.x, part.y, 1500);
    s = await state();
    check("a real press on its α subunit chooses that part, under the unit's id", s.selected === "unit.U39:alpha" && /α, the pump/.test(s.panel), JSON.stringify([part, s.selected, s.panel.slice(0, 120)]));
    // The ribosome: the eukaryotic one, from the human structure.
    await evaluate(`${V}.select("machine:ribosome", { fly: true })`);
    await sleep(1800);
    s = await state();
    check("the planarian's ribosome is measured from the human 80S (8YOP); its panel names that organism, and what the measure leaves out", /8YOP, a structure of Homo sapiens \(one of Schmidtea mediterranea: none in hand\)/.test(s.panel) && /RACK1/.test(s.panel), s.panel.slice(0, 200));
    // The gap-junction unit: an innexin channel, the family the planarian builds it from; its sixteen chains by the card's Detail.
    await evaluate(`${V}.select("unit.U36", { fly: true })`);
    await sleep(2200);
    s = await state();
    check("the planarian's gap-junction unit is measured from an innexin channel (5H1R), the family its atlas finds", /5H1R, a structure of Caenorhabditis elegans/.test(s.panel) && /family/.test(s.panel), s.panel.slice(0, 200));
    // On a phone the card is folded to one line: unfold it to reach its Detail.
    let chains = await placeOf(`root.querySelector('[data-show="3"]')`);
    if (!chains) {
      await press(".view-toggle", 900);
      chains = await placeOf(`root.querySelector('[data-show="3"]')`);
    }
    if (chains) await click(chains.x, chains.y, 1500);
    const channel = await evaluate(`(() => { const b = ${L}.built.get("unit.U36"); return { level: b?.level, ids: b?.ids.size, shades: new Set(${L}.bodyColours("unit.U36")).size, cost: ${L}.cost() }; })()`);
    check("a real press on Subunits shows its sixteen chains, the two hemichannels told apart, in one more draw", channel.level === 3 && channel.ids === 16 && channel.shades >= 2 && channel.cost.draws <= 40, JSON.stringify([chains, channel]));
    await shot(`${NAME}-innexin`);
    // Its Shape level: the unit drawn by its page id, a surface chosen as its chain, within the ceiling.
    let shapeButton = await placeOf(`root.querySelector('[data-show="4"]')`);
    if (!shapeButton) {
      await press(".view-toggle", 900);
      shapeButton = await placeOf(`root.querySelector('[data-show="4"]')`);
    }
    if (shapeButton) await click(shapeButton.x, shapeButton.y, 1200);
    await until(`Boolean(${L}.built.get("unit.U36")?.surface)`, 60);
    const unitShape = await evaluate(`(() => { const b = ${L}.built.get("unit.U36"); return { level: b?.level, surface: Boolean(b?.surface), picked: b?.surface?.mesh.userData.pick({ faceIndex: 0 }) || null, cost: ${L}.cost() }; })()`);
    s = await state();
    check("a real press on Shape draws the innexin channel's surfaces by the unit's id, within the ceiling, and says whose structure it is", unitShape.level === 4 && unitShape.surface && /^unit\.U36:chain-/.test(unitShape.picked || "") && unitShape.cost.draws <= 40 && unitShape.cost.triangles <= 40000 && /It is the shape of a structure of Caenorhabditis elegans/.test(s.panel), JSON.stringify([shapeButton, unitShape, s.panel.slice(0, 120)]));
    await shot(`${NAME}-innexin-shape`);
    await evaluate(`${V}.select(null); ${V}.stage.rig.setView(${V}.current.homeView())`);
    await sleep(1200);
    const cost = await evaluate(`(() => {
      const v = ${V}, stage = v.stage, lens = v.current;
      const time = (fn, n = 20) => { const times = []; for (let i = 0; i < n; i++) { const t = performance.now(); fn(); times.push(performance.now() - t); } times.sort((a, b) => a - b); return Math.round(times[Math.floor(n / 2)] * 100) / 100; };
      return { update: time(() => lens.update(16)), labels: time(() => v.labels.layout()), draw: time(() => { stage.renderer.render(stage.scene, stage.camera); stage.renderer.getContext().finish(); }, 12), cost: lens.cost() };
    })()`);
    note(`${WIDTH} by ${HEIGHT}: ${JSON.stringify(cost)} (milliseconds, the median)`);
    check(`${WIDTH} by ${HEIGHT}: the planarian's bench within the ceiling the tests hold (40 draws, 40,000 triangles), and a frame leaves room at 60 a second`, cost.cost.draws <= 40 && cost.cost.triangles <= 40000 && within(`${WIDTH} by ${HEIGHT}: the planarian's bench, the view's update, its labels and the draw on a frame (the medians, summed)`, cost.update + cost.labels + cost.draw, 16.7), JSON.stringify(cost));
    await shot(`${NAME}-rest`);
    // By address: a part of a unit, before the unit is drawn with its parts, opens on Machines with its own panel.
    check("the page opens on lens=machines&entry=planarian&select=unit.U39:alpha", await open("lens=machines&entry=planarian&select=unit.U39:alpha", 3500));
    s = await state();
    const addressed = await evaluate(`(() => { const lens = ${L}; return { selected: lens.selected, part: lens.selectedPart, level: lens.built.get("unit.U39")?.level ?? null }; })()`);
    check("an address of a unit's part opens on Machines, its unit drawn with its parts and the part's panel shown", s.lens === "machines" && addressed.selected === "unit.U39" && addressed.part === "unit.U39:alpha" && addressed.level === 2 && /α, the pump/.test(s.panel), JSON.stringify([s.lens, s.selected, addressed, s.panel.slice(0, 100)]));
    await errorsAtEnd();
  } else if (CASE === "human") {
    // ---------------------------------------------------------- the human's bench: its dossier's machines, and the way to and from the atlas
    check("the page opens on lens=machines with the human", await open("lens=machines&entry=human", 3500));
    const bench = await evaluate(`(() => { const lens = ${L}, counts = lens.catalogue.counts("human"); return { trays: lens.layout.trays.length, groups: counts.groups, machines: counts.machines, sized: counts.sized, shapes: lens.layout.items.filter((i) => i.type === "shape").length, cost: lens.cost() }; })()`);
    check("the human's bench: a tray for each group, every measured machine and unit drawn to scale, and the frame within the ceiling (40 draws, 40,000 triangles)", bench.trays === bench.groups && bench.shapes === bench.sized && bench.sized >= 13 && bench.cost.draws <= 40 && bench.cost.triangles <= 40000, JSON.stringify(bench));
    // The opening view: no tray runs off the screen at its edge (the measured machines spread over most of the bench).
    const edges = await evaluate(`(() => { const v = ${V}, lens = v.current, r = v.canvas.getBoundingClientRect(), out = [];
      for (const tray of lens.layout.trays) for (const [dx, dz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
        const p = lens.root.position.clone().set(tray.x + dx * tray.w / 2, 0, tray.z + dz * tray.d / 2); const q = v.stage.project(p, p.clone());
        if (q.x < -2 || q.x > r.width + 2 || q.y < -2 || q.y > r.height + 2) out.push(tray.group);
      }
      return [...new Set(out)]; })()`);
    check(`${WIDTH} by ${HEIGHT}: the opening view cuts no tray at the screen's edge`, edges.length === 0, JSON.stringify(edges));
    await shot(`${NAME}-bench`);
    // A real press on the proteasome's outline, at the middle of its box.
    const middleOf = (id) =>
      evaluate(`(() => { const v = ${V}, item = v.current.layout.items.find((value) => value.id === ${JSON.stringify(id)}); if (!item) return null; const p = v.current.root.position.clone().set(item.x, item.y + item.h / 2, item.z); const q = v.stage.project(p, p.clone()); const r = v.canvas.getBoundingClientRect(); return { x: r.left + q.x, y: r.top + q.y }; })()`);
    await evaluate(`${V}.current.focus("machine:proteasome")`);
    await sleep(2200);
    const at = await middleOf("machine:proteasome");
    if (at) await click(at.x, at.y, 1800);
    let s = await state();
    check("a real press on the proteasome chooses it: its parts are its core, base and lid; FR-13 names it; its proteins by tier", s.selected === "machine:proteasome" && s.level === 2 && /It names the proteasome among the machines the engine has no model of/.test(s.panel) && /Its parts, held by the structure/.test(s.panel) && !/(?<!not |no )\bmodell?ed\b|qualified|judged/i.test(s.panel.replace(/What Cells models of it/g, "")), JSON.stringify([at, s.selected, s.level, s.panel.slice(0, 160)]));
    // Its subunits by the card's Detail (on a phone the card is unfolded first), then a real press on one chain.
    let chains = await placeOf(`root.querySelector('[data-show="3"]')`);
    if (!chains) {
      await press(".view-toggle", 900);
      chains = await placeOf(`root.querySelector('[data-show="3"]')`);
    }
    if (chains) await click(chains.x, chains.y, 1500);
    await evaluate(`${V}.current.focus("machine:proteasome")`);
    await sleep(2200);
    const chainAt = await evaluate(`(() => { const v = ${V}, lens = v.current, built = lens.built.get("machine:proteasome"), size = lens.item("machine:proteasome").size, r = v.canvas.getBoundingClientRect();
      for (const chain of size.chains) for (const t of [0, 0.3, -0.3]) for (let k = 0; k < 3; k++) {
        const local = chain.centre_nm.map((n, i) => (n + t * chain.axes[k][i] * chain.across_nm[k] / 2) / 10);
        const p = built.group.localToWorld(built.group.position.clone().set(...local)); const q = v.stage.project(p, p.clone());
        const x = r.left + q.x, y = r.top + q.y, top = v.shadowRoot.elementFromPoint(x, y);
        if (top !== v.canvas && !(top && top.tagName === "CANVAS")) continue;
        const id = v.stage.pick(x, y, lens.pickRoots)?.id;
        if (id === "machine:proteasome:" + chain.id) return { x, y, id };
      }
      return null; })()`);
    if (chainAt) await click(chainAt.x, chainAt.y, 1500);
    s = await state();
    const door = s.doors.find((value) => /^Show \S+ in the Protein atlas\b/.test(value)) || null;
    check("a real press on one of its chains shows that chain's panel: its protein, as the dossier reads the entry, and the door to it in the atlas", Boolean(chainAt) && s.selected === chainAt?.id && /Its protein/.test(s.panel) && Boolean(door), JSON.stringify([chainAt, s.selected, s.doors]));
    // Through that door into the atlas, onto the protein; and from its panel back to the proteasome.
    const accession = await evaluate(`${L}.item("machine:proteasome").size.chains.find((chain) => "machine:proteasome:" + chain.id === ${JSON.stringify(chainAt?.id || "")})?.protein || null`);
    const into = await placeOf(`[...root.querySelectorAll("cells-panel .panel-door button")].find((button) => /in the Protein atlas/.test(button.textContent))`);
    if (into) await click(into.x, into.y, 2500);
    for (let tries = 0; tries < 80 && !String((await state()).selected || "").endsWith(":" + accession); tries++) await sleep(250);
    s = await state();
    check("the door opens the Protein atlas on that protein", s.lens === "proteins" && String(s.selected || "").startsWith("own:human:") && String(s.selected).endsWith(":" + accession), JSON.stringify([accession, s.lens, s.selected]));
    const backDoor = await placeOf(`[...root.querySelectorAll("cells-panel .panel-door button")].find((button) => /It is a part of the proteasome: show it in Machines/.test(button.textContent))`);
    check("the protein's panel in the atlas offers its machine", Boolean(backDoor), JSON.stringify(s.doors));
    if (backDoor) await click(backDoor.x, backDoor.y, 2500);
    s = await state();
    check("a real press on it brings the proteasome back, chosen, in Machines", s.lens === "machines" && s.selected === "machine:proteasome", JSON.stringify([s.lens, s.selected]));
    await shot(`${NAME}-back`);
    await errorsAtEnd();
  } else if (CASE === "shape") {
    // ---------------------------------------------------------- the Shape level, on E. coli's measured machines
    check("the page opens on lens=machines with E. coli", await open("lens=machines&entry=ecoli", 3500));
    // Its Detail at Shape, by a real press (on a phone the card is unfolded first); the four levels in one row.
    const toShape = async (id) => {
      await evaluate(`${V}.select(${JSON.stringify(id)}, { fly: true })`);
      await sleep(1800);
      let button = await placeOf(`root.querySelector('[data-show="4"]')`);
      if (!button) {
        await press(".view-toggle", 900);
        button = await placeOf(`root.querySelector('[data-show="4"]')`);
      }
      if (button) await click(button.x, button.y, 1200);
      await until(`Boolean(${L}.built.get(${JSON.stringify(id)})?.surface)`, 60);
      const row = await evaluate(`(() => { const els = [...${V}.shadowRoot.querySelectorAll('[data-show]')].filter((el) => el.getBoundingClientRect().width > 0), buttons = els.map((el) => el.getBoundingClientRect()); return { count: buttons.length, rows: new Set(buttons.map((r) => Math.round(r.top))).size, narrowest: Math.round(Math.min(...buttons.map((r) => r.width))), cut: els.filter((el) => el.scrollWidth > el.clientWidth + 1).map((el) => el.textContent) }; })()`);
      if (await evaluate(`Boolean(${V}.shadowRoot.querySelector(".view-toggle")) && ${V}.clientWidth < 760`)) await press(".view-toggle", 600);
      return { button, row };
    };
    let shown = await toShape("machine:atp-synthase");
    let built = await evaluate(`(() => { const b = ${L}.built.get("machine:atp-synthase"); return { level: b?.level, surface: Boolean(b?.surface), bodies: b?.bodies?.visible, cost: ${L}.cost() }; })()`);
    check("a real press on Shape draws the ATP synthase's surfaces in the place of its ellipsoids, in one draw, within the ceiling", Boolean(shown.button) && built.level === 4 && built.surface && built.bodies === false && built.cost.draws <= 40 && built.cost.triangles <= 40000, JSON.stringify([shown.button, built]));
    check("the Detail's four levels stand in one row on a wide screen, in two of two on a phone, and no label is cut", shown.row.count === 4 && shown.row.rows === (WIDTH < 560 ? 2 : 1) && shown.row.cut.length === 0, JSON.stringify(shown.row));
    let s = await state();
    check("its panel says what the shape is: the viewer's own surface of 6OQR's coordinates, an illustration, not a measurement", /The viewer's own smooth surface of Protein Data Bank entry 6OQR's coordinates \(a chain at 1\.0 nm\)/.test(s.panel) && /An illustration, not the structure and not a measurement/.test(s.panel), s.panel.slice(0, 200));
    await shot(`${NAME}-atp`);
    // A real press on one of its surfaces: the chain chosen, lit, its panel with its protein and its part.
    const surfaceAt = await evaluate(`(() => { const v = ${V}, lens = v.current, built = lens.built.get("machine:atp-synthase"), size = lens.item("machine:atp-synthase").size, r = v.canvas.getBoundingClientRect();
      for (const chain of size.chains) for (const t of [0, 0.25, -0.25]) for (let k = 0; k < 3; k++) {
        const local = chain.centre_nm.map((n, i) => (n + t * chain.axes[k][i] * chain.across_nm[k] / 2) / 10);
        const p = built.group.localToWorld(built.group.position.clone().set(...local)); const q = v.stage.project(p, p.clone());
        const x = r.left + q.x, y = r.top + q.y, top = v.shadowRoot.elementFromPoint(x, y);
        if (top !== v.canvas && !(top && top.tagName === "CANVAS")) continue;
        const id = v.stage.pick(x, y, lens.pickRoots)?.id;
        if (id && id.startsWith("machine:atp-synthase:chain-")) return { x, y, id };
      }
      return null; })()`);
    if (surfaceAt) await click(surfaceAt.x, surfaceAt.y, 1500);
    s = await state();
    const lit = await evaluate(`(() => { const lens = ${L}, b = lens.built.get("machine:atp-synthase"), row = b?.surface?.surfaces.find((value) => value.chain === ${JSON.stringify(surfaceAt?.id || "")}); if (!row) return null; const c = b.surface.mesh.geometry.getAttribute("color"); const at = (n) => [c.getX(n), c.getY(n), c.getZ(n)].map((x) => Math.round(x * 255)); const accent = ${V}.stage.palette.accent; return { chosen: at(row.firstVertex), accent }; })()`);
    // The mesh keeps its colours in linear light (three.js's working space): the accent's sRGB, made linear.
    const linear = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
    const accentRgb = lit ? [1, 3, 5].map((i) => Math.round(linear(parseInt(lit.accent.slice(i, i + 2), 16) / 255) * 255)) : null;
    check("a real press on a surface chooses its chain, lit in the page's accent, its panel with its protein and a door to its part", Boolean(surfaceAt) && s.selected === surfaceAt.id && /Its protein/.test(s.panel) && s.doors.some((door) => /^Its part:/.test(door)) && Boolean(lit) && lit.chosen.every((value, i) => Math.abs(value - accentRgb[i]) <= 3), JSON.stringify([surfaceAt, s.selected, lit, s.doors]));
    await shot(`${NAME}-atp-chain`);
    // The ribosome at Shape: its two subunits as solids; and the same in two tones, for the look only.
    shown = await toShape("machine:ribosome");
    built = await evaluate(`(() => { const b = ${L}.built.get("machine:ribosome"); return { surfaces: b?.surface?.surfaces.map((row) => row.partId) || [], cost: ${L}.cost() }; })()`);
    check("the ribosome at Shape: its two subunits as solids, within the ceiling", JSON.stringify(built.surfaces.sort()) === JSON.stringify(["large", "small"]) && built.cost.draws <= 40 && built.cost.triangles <= 40000, JSON.stringify(built));
    await shot(`${NAME}-ribosome`);
    await evaluate(`(() => { const lens = ${L}; lens.surfaceTones = true; lens.rebuildMachine("machine:ribosome"); })()`);
    await until(`Boolean(${L}.built.get("machine:ribosome")?.surface)`, 40);
    await sleep(600);
    await shot(`${NAME}-ribosome-tones`);
    await evaluate(`(() => { const lens = ${L}; lens.surfaceTones = false; lens.rebuildMachine("machine:ribosome"); })()`);
    // Syn3A's ribosome takes E. coli's shape, and says whose it is.
    await evaluate(`${V}.setSpecies("syn3a")`);
    await sleep(1500);
    shown = await toShape("machine:ribosome");
    s = await state();
    check("Syn3A's ribosome at Shape is E. coli's shape, and its panel says whose", /It is the shape of a structure of Escherichia coli, as its size is\./.test(s.panel), s.panel.slice(0, 160));
    await errorsAtEnd();
  } else if (CASE === "benches") {
    // ---------------------------------------------------------- the benches read beside the page: the planarian's, the thale cress's
    check("the page opens on lens=machines with the planarian", await open("lens=machines&entry=planarian", 3500));
    const benchIn = (species) => until(`${L}.catalogue.hasBench(${JSON.stringify(species)}) && ${L}.layout.items.some((item) => !item.item.unit)`, 80);
    check("its bench is read from beside the page (catalogue/planarian.json), and no other species' bench is", (await benchIn("planarian")) && (await evaluate(`(() => { const read = performance.getEntriesByType("resource").map((entry) => entry.name).filter((name) => /\\/catalogue\\/[a-z0-9]+\\.json$/.test(name)); return read.length === 1 && read[0].endsWith("/catalogue/planarian.json"); })()`)), JSON.stringify(await evaluate(`performance.getEntriesByType("resource").map((entry) => entry.name).filter((name) => /catalogue/.test(name))`)));
    const bench = await evaluate(`(() => { const lens = ${L}, counts = lens.catalogue.counts("planarian"); return { trays: lens.layout.trays.length, groups: counts.groups, machines: counts.machines, cost: lens.cost(), sections: ${V}.sections().length, apart: lens.catalogue.noneFound("planarian").length ? 1 : 0 }; })()`);
    check("the planarian's bench: a tray for each group, its machines and units, the List by group (and what was looked for and not found, apart), within the ceiling", bench.trays === bench.groups && bench.machines >= 60 && bench.sections === bench.groups + bench.apart && bench.cost.draws <= 40 && bench.cost.triangles <= 40000, JSON.stringify(bench));
    const edges = await evaluate(`(() => { const v = ${V}, lens = v.current, r = v.canvas.getBoundingClientRect(), out = [];
      for (const tray of lens.layout.trays) for (const [dx, dz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
        const p = lens.root.position.clone().set(tray.x + dx * tray.w / 2, 0, tray.z + dz * tray.d / 2); const q = v.stage.project(p, p.clone());
        if (q.x < -2 || q.x > r.width + 2 || q.y < -2 || q.y > r.height + 2) out.push(tray.group);
      }
      return [...new Set(out)]; })()`);
    check(`${WIDTH} by ${HEIGHT}: the opening view cuts no tray at the screen's edge`, edges.length === 0, JSON.stringify(edges));
    await shot(`${NAME}-planarian`);
    // A real press on a machine named by family: its panel says its proteins are candidates, and what was looked for.
    const card = await evaluate(`(() => { const v = ${V}, item = v.current.layout.items.find((value) => value.id === "machine:proteasome"); if (!item) return null; v.current.focus("machine:proteasome"); return true; })()`);
    await sleep(2000);
    const at = await evaluate(`(() => { const v = ${V}, item = v.current.layout.items.find((value) => value.id === "machine:proteasome"); const p = v.current.root.position.clone().set(item.x, item.y + item.h, item.z); const q = v.stage.project(p, p.clone()); const r = v.canvas.getBoundingClientRect(); return { x: r.left + q.x, y: r.top + q.y }; })()`);
    if (card && at) await click(at.x, at.y, 1500);
    let s = await state();
    check("a real press on the proteasome's card: its proteins are candidates by their family, not its parts, with what was looked for part by part (\"Looked for, by family\", not \"Named by\")", s.selected === "machine:proteasome" && /candidates by their family \(InterPro\) for parts of Human's machine: candidates, not the machine's parts/.test(s.panel) && /What was looked for, part by part/.test(s.panel) && /Looked for, by family/.test(s.panel) && !/Named by/.test(s.panel) && !/Its parts, held by the structure/.test(s.panel), JSON.stringify([at, s.selected, s.panel.slice(0, 200)]));
    await shot(`${NAME}-planarian-proteasome`);
    // The planarian's bench by family: the machines its records name and the candidates by family, counted apart in the card.
    // Since the species' own scan (19 November 2026) every machine looked for has a candidate, myosin II among them, so none
    // is listed apart (Syn3A's bench, below, holds that list); a candidate's card says so on its face.
    const family = await evaluate(`(() => { const lens = ${L}, stats = Object.fromEntries(lens.chrome().card.stats.map(([value, label]) => [label, value])); return { stats, bench: lens.layout.items.filter((item) => !item.item.unit).length, none: lens.catalogue.noneFound("planarian").map((row) => row.id), myosin: lens.layout.items.some((item) => item.id === "machine:myosin-ii"), face: lens.plaques.some((plaque) => plaque.text === "candidates for 31 of 32 parts,"), list: [...${V}.shadowRoot.querySelectorAll(".mach-none-found summary")].map((el) => el.textContent) }; })()`);
    check("the planarian's card counts 1 machine its records name and 31 candidates by family (the vault's one gene model among them, since 19 November 2026); myosin II has candidates and stands on the bench, and none is listed apart; the proteasome's card says its candidates on its face", family.stats["named by its own records"] === 1 && family.stats["candidates by family"] === 31 && family.bench === 32 && family.myosin && family.none.length === 0 && family.face && family.list.length === 0, JSON.stringify(family));
    // The search finds a machine by a candidate's name.
    await evaluate(`(() => { const v = ${V}; v.select(null); v.current.setQuery("proteasome subunit alpha"); v.renderChrome(); })()`);
    await sleep(500);
    const found = await evaluate(`${L}.chrome().legend.items.find((item) => item.id === "mach-found")?.count ?? null`);
    check("the card's search finds the proteasome by a candidate's name", found >= 1, String(found));
    await evaluate(`(() => { const v = ${V}; v.current.setQuery(""); v.renderChrome(); })()`);
    // A candidate's door in the Protein atlas says what it is, and a real press on it opens Machines on its machine.
    await evaluate(`${V}.openDoor({ lens: "proteins", show: "own", find: "h1SMcG0000958" })`);
    await until(`String(${V}.state.selected || "").endsWith(":h1SMcG0000958")`, 80);
    await sleep(800);
    const candidate = await placeOf(`[...root.querySelectorAll("cells-panel .panel-door button")].find((button) => /^It is a candidate, by its family, for a part of Human's proteasome: show it in Machines/.test(button.textContent))`);
    const atlasDoors = (await state()).doors;
    if (candidate) await click(candidate.x, candidate.y, 2500);
    await until(`${V}.state.lens === "machines" && ${V}.state.selected === "machine:proteasome"`, 40);
    await sleep(1500);
    const flown = await evaluate(`(() => { const v = ${V}, lens = v.current, item = lens.layout.items.find((value) => value.id === "machine:proteasome"); const r = v.canvas.getBoundingClientRect(), insets = v.stage.insets || {}; const p = lens.root.position.clone().set(item.x, item.y + item.h, item.z); const q = v.stage.project(p, p.clone()); const x = r.left + q.x, y = r.top + q.y, top = v.shadowRoot.elementFromPoint(x, y); return { x: Math.round(x), y: Math.round(y), clear: top === v.canvas, inside: x >= r.left + (insets.left || 0) && x <= r.right - (insets.right || 0) && y >= r.top && y <= r.bottom - (insets.bottom || 0) }; })()`);
    check("a planarian protein's door says it is a candidate, by its family, for a part of Human's proteasome, never \"a part of\"; a real press opens Machines on the proteasome, in sight", Boolean(candidate) && !atlasDoors.some((door) => /^It is a part of/.test(door)) && flown.clear && flown.inside, JSON.stringify([candidate, atlasDoors, flown]));
    await shot(`${NAME}-planarian-candidate-door`);
    // The thale cress: its machines of light in a tray of their own.
    await evaluate(`${V}.setSpecies("thalecress")`);
    await benchIn("thalecress");
    await sleep(1200);
    const plant = await evaluate(`(() => { const lens = ${L}; return { trays: lens.layout.trays.map((tray) => tray.group), machines: lens.catalogue.counts("thalecress").machines, cost: lens.cost() }; })()`);
    check("the thale cress's bench: its machines of light in a tray of their own, within the ceiling", plant.trays.includes("light") && plant.machines >= 38 && plant.cost.draws <= 40 && plant.cost.triangles <= 40000, JSON.stringify(plant));
    await shot(`${NAME}-thalecress`);
    // Syn3A: what its own file names stays; the ten machines looked for by family with no candidate are off the bench,
    // listed in the card under their own heading, and the card's search finds one there, not as a machine of Syn3A.
    await evaluate(`(() => { const v = ${V}; v.select(null); v.setSpecies("syn3a"); })()`);
    await benchIn("syn3a");
    await sleep(1200);
    await evaluate(`(() => { const v = ${V}; v.current.setQuery("bamA"); v.renderChrome(); })()`);
    await sleep(400);
    const apart = await evaluate(`(() => { const v = ${V}, lens = v.current, block = v.shadowRoot.querySelector(".mach-none-found"); return { bench: lens.layout.items.filter((item) => !item.item.unit).map((item) => item.id.slice(8)).sort(), found: lens.chrome().legend.items.find((item) => item.id === "mach-found")?.count ?? 0, open: Boolean(block?.open), rows: block ? [...block.querySelectorAll("li")].map((li) => li.textContent) : [], summary: block?.querySelector("summary")?.textContent || null }; })()`);
    check("Syn3A's bench: its file's six machines and three candidates by family; BAM complex is off it, and the card's search finds it in the list apart, with its reference, not as a machine of Syn3A", apart.bench.length === 9 && !apart.bench.includes("bam-complex") && ["ribosome", "rna-polymerase", "atp-synthase", "protein-translocon", "ftsh", "lon"].every((id) => apart.bench.includes(id)) && apart.found === 0 && apart.open && apart.rows.join() === "BAM complex: E. coli's, 5 parts looked for" && apart.summary === "Looked for by family, no candidate found · 1", JSON.stringify(apart));
    await shot(`${NAME}-syn3a-apart`);
    await evaluate(`(() => { const v = ${V}; v.current.setQuery(""); v.renderChrome(); })()`);
    await errorsAtEnd();
    // A bench that cannot be read: the card says so plainly, and the tab still works with the units.
    await evaluate(`(() => { const lens = ${L}; lens.catalogue.raw.benches.fruitfly.file = "catalogue/none-such.json"; ${V}.setSpecies("fruitfly"); })()`);
    await until(`${L}.catalogue.benchState("fruitfly")?.status === "failed"`, 80);
    await sleep(800);
    const failed = await evaluate(`(() => { const lens = ${L}; return { notice: lens.chrome().card.notice, units: lens.layout.items.filter((item) => item.item.unit).length, others: lens.layout.items.filter((item) => !item.item.unit).length }; })()`);
    check("a bench that cannot be read says so in the card, and the units stand", /^The machines of this species could not be read \(catalogue\/none-such\.json: /.test(failed.notice || "") && failed.units > 0 && failed.others === 0, JSON.stringify(failed));
    await shot(`${NAME}-failed`);
    // Cold addresses: what an address names (a machine drawn to scale, a card, a unit, a part, a chain) is chosen once its
    // species' bench is read, drawn at its level, and flown to: it stands in the room the card and the panel leave free,
    // as near as a choice on the bench already read brings it.
    const placeIn = (id) =>
      evaluate(`(() => { const v = ${V}, lens = v.current, id = ${JSON.stringify(id)}, owner = lens.partOf(id) || id.match(/^(machine:[^:]+|unit\\.[^:]+)/)[1];
        const item = lens.layout.items.find((value) => value.id === owner); if (!item) return { owner, missing: true, selected: v.state.selected };
        const r = v.canvas.getBoundingClientRect(), insets = v.stage.insets || {}, lift = lens.lifts.get(owner) || 0;
        const at = (dx) => { const p = lens.root.position.clone().set(item.x + dx, item.y + lift + item.h / 2, item.z); const q = v.stage.project(p, p.clone()); return { x: r.left + q.x, y: r.top + q.y }; };
        const mid = at(0), wide = Math.abs(at(item.w / 2).x - at(-item.w / 2).x), top = v.shadowRoot.elementFromPoint(mid.x, mid.y);
        const room = { left: r.left + (insets.left || 0), right: r.right - (insets.right || 0), top: r.top, bottom: r.bottom - (insets.bottom || 0) };
        return { owner, x: Math.round(mid.x), y: Math.round(mid.y), wide: Math.round(wide), room: Object.fromEntries(Object.entries(room).map(([k, n]) => [k, Math.round(n)])), clear: Boolean(top) && (top === v.canvas || top.tagName === "CANVAS"), over: top && top !== v.canvas ? top.tagName.toLowerCase() + (top.className ? "." + String(top.className).split(" ")[0] : "") : null,
          level: lens.built.get(owner)?.level ?? null, part: lens.selectedPart || null, selected: v.state.selected }; })()`);
    const inRoom = (seen) => !seen.missing && seen.clear && seen.x >= seen.room.left && seen.x <= seen.room.right && seen.y >= seen.room.top && seen.y <= seen.room.bottom && seen.wide >= 0.06 * (seen.room.right - seen.room.left); // at the whole bench's view a unit is some 2 per cent of it
    const logged = pageLog.length;
    // A file's or a field's name that no panel says (the dossiers' sentences reach it in plain words).
    const TOOL_WORDS = /gather\.json|\b(?:left_out|holds_more|structure_elsewhere|not_looked_for|no_structure|looked_for|by_protein|per_cell)\b|\((?:data|tools|schema|src)\//;
    for (const [species, id, what] of [
      ["human", "machine:ribosome", "a machine drawn to scale"],
      ["planarian", "machine:proteasome", "a card; the planarian is the page's first species"],
      ["mouse", "unit.U39", "a unit drawn to scale"],
      ["thalecress", "machine:rna-polymerase", "a card"],
      ["human", "machine:proteasome:chain-U", "a chain of a machine drawn to scale"],
      ["mouse", "machine:ribosome:small", "a part of a machine drawn to scale"],
      ["fruitfly", "machine:ribosome:large", "a part, with no lens named: the address opens Machines"],
    ]) {
      await open(`${/no lens/.test(what) ? "" : "lens=machines&"}${species === "planarian" ? "" : `species=${species}&`}select=${id}`, 300);
      const chosen = await until(`${V}.state.selected === ${JSON.stringify(id)} && ${L}.catalogue.hasBench(${JSON.stringify(species)}) && ${L}.layout.items.some((item) => !item.item.unit)`, 80);
      await sleep(2800);
      const cold = await placeIn(id);
      const thrown = await evaluate(`(window.__pageErrors || []).slice(0, 3)`);
      await shot(`${NAME}-cold-${species}-${id.replace(/[^a-z0-9]+/gi, "-")}`);
      // The same choice made again on the bench as it now stands: the level and the place a choice there gives.
      await evaluate(`(() => { const v = ${V}; v.select(null); v.select(${JSON.stringify(id)}, { fly: true }); })()`);
      await sleep(2800);
      const again = await placeIn(id);
      const words = (await state()).panel.match(TOOL_WORDS)?.[0] || null;
      check(`a cold address on ${species}'s ${id} (${what}): chosen, at the level a choice on the read bench gives, in the free room of the picture; its panel in plain words`, chosen && cold.selected === id && cold.level === again.level && cold.part === again.part && inRoom(cold) && inRoom(again) && thrown.length === 0 && !words, JSON.stringify({ cold, again, thrown, words }));
    }
    // While a bench is still being read (its file held back a moment and a half): a unit chosen as the List chooses it,
    // and a door from another view into Machines; each chosen at its level once the bench is in, and flown to, in the
    // picture's free room, as the same choice on the bench in hand.
    const holdBack = `(() => { const fetched = window.fetch; window.fetch = (what, ...rest) => (/\\/catalogue\\/[a-z0-9]+\\.json/.test(String(what)) ? new Promise((done) => setTimeout(done, 1500)).then(() => fetched(what, ...rest)) : fetched(what, ...rest)); return true; })()`;
    for (const [from, species, id, how] of [
      ["cell", "mouse", "unit.U39", "list"],
      ["proteins", "thalecress", "machine:ribosome", "door"],
      ["cell", "human", "machine:proteasome", "door"],
    ]) {
      await open(`lens=${from}&species=${species}`, 1500);
      const unread = await evaluate(`!${V}.lenses?.get("machines")?.catalogue?.hasBench(${JSON.stringify(species)})`).catch(() => null);
      await evaluate(holdBack);
      if (how === "list") await evaluate(`(() => { const v = ${V}; v.setLens("machines", true); v.select(${JSON.stringify(id)}, { fly: true }); })()`);
      else await evaluate(`${V}.openDoor({ lens: "machines", value: ${JSON.stringify(id)} })`);
      const chosen = await until(`${V}.state.selected === ${JSON.stringify(id)} && ${L}.catalogue.hasBench(${JSON.stringify(species)}) && ${L}.layout.items.some((item) => !item.item.unit)`, 80);
      await sleep(2800);
      const held = await placeIn(id);
      await shot(`${NAME}-held-${how}-${species}-${id.replace(/[^a-z0-9]+/gi, "-")}`);
      await evaluate(how === "list" ? `(() => { const v = ${V}; v.select(null); v.select(${JSON.stringify(id)}, { fly: true }); })()` : `(() => { const v = ${V}; v.select(null); v.stage.rig.setView(v.current.homeView()); v.openDoor({ lens: "machines", value: ${JSON.stringify(id)} }); })()`);
      await sleep(2800);
      const again = await placeIn(id);
      check(`${how === "list" ? "the List's press" : `a door from the ${from === "cell" ? "Cell view" : "Protein atlas"}`} on ${species}'s ${id} while its bench is read: chosen at its level once it is in, and flown to, in the picture's free room`, chosen && held.selected === id && held.level === again.level && inRoom(held) && inRoom(again), JSON.stringify({ unread, held, again }));
    }
    const later = pageLog.slice(logged).filter((line) => /error|exception|rejection|blocked/i.test(line));
    check("the cold addresses and the held benches logged no error", later.length === 0, later.slice(0, 3).join(" / "));
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
    const groups = await evaluate(`${V}.views.find((view) => view.id === "machines")?.textSections?.(${V}.model.raw, "ecoli")?.length ?? null`);
    check("the List holds E. coli's machines by group", listed.length === groups && listed.length >= 8 && listed.some(([label, n]) => label === "Moving, sensing and attaching" && n === 2), JSON.stringify(listed));
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
      // A part of an example shown in the tab's place (the gap-junction example's tissue line), where its runs are packaged: the same.
      await open("lens=experiments&part=gap-junction-tissue-line", 2500);
      if (await until(`${V}.state.part === "gap-junction-tissue-line" && Boolean(${V}.current)`, 30)) {
        if (await until(lettered, 40)) await evaluate(`${V}.renderChrome()`);
        const part = await barNow();
        const partList = await evaluate(`(() => { const list = ${V}.shadowRoot.querySelector(".bar-end .pill-button"), end = list.parentElement.getBoundingClientRect(), box = list.getBoundingClientRect(); return box.left >= end.left - 0.5 && box.right <= end.right + 0.5 && box.right <= innerWidth; })()`);
        check(`${width} px, a part of an example shown in the Experiments tab: its tab is in sight, the bar on one row, every button at least 44 px, the List whole and not cut by the bar's end`, part.row && part.least >= 44 && part.seen && part.list && partList && !part.sideways && part.tabs === 6, JSON.stringify({ ...part, partList }));
      } else note(`${width} px: the tissue line's runs are not packaged here, so its bar is not checked`);
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
  } else if (CASE === "vault") {
    // ---------------------------------------------------------- the vault (19 November 2026), on the benches that show it
    const idOf = "machine:vault";
    for (const species of ["human", "mouse", "planarian"]) {
      check(`the page opens on lens=machines with ${species}`, await open(`lens=machines&entry=${species}`, 3500));
      await shot(`${NAME}-${species}-bench`);
      const bench = await evaluate(`(() => { const lens = ${L}, item = lens.layout.items.find((value) => value.id === ${JSON.stringify(idOf)}); return { type: item?.type, tray: lens.layout.trays.some((tray) => tray.group === "unknown"), scale: Boolean(lens.scaleBar), cost: lens.cost(), long: item?.long_nm ?? null }; })()`);
      check(`${species}: the vault stands drawn to scale in a tray of its own group, with the 100 nm bar, within the ceiling (40 draws, 40,000 triangles)`, bench.type === "shape" && bench.tray && bench.scale && bench.cost.draws <= 40 && bench.cost.triangles <= 40000, JSON.stringify(bench));
      // At the opening view the vault hides no unit of the law inventory: its tray stands behind theirs (its group's `stands: "behind"`), and a
      // press at the middle of each unit's shape reaches that unit. The vault stood in the row before the units' tray at first, and hid them.
      await evaluate(`${V}.stage.rig.setView(${V}.current.homeView())`);
      await sleep(800);
      const clear = await evaluate(`(() => { const v = ${V}, lens = v.current, r = v.canvas.getBoundingClientRect(), tray = (group) => lens.layout.trays.find((value) => value.group === group);
        const reach = lens.layout.items.filter((item) => item.type === "shape" && item.item.unit).map((item) => { const p = lens.root.position.clone().set(item.x, item.y + item.h / 2, item.z); const q = v.stage.project(p, p.clone()); return [item.id, v.stage.pick(r.left + q.x, r.top + q.y, lens.pickRoots)?.id || null]; });
        return { behind: tray("unknown").z + tray("unknown").d / 2 < tray("ions").z - tray("ions").d / 2, reach }; })()`);
      check(`${species}: the vault's tray stands behind the units' tray, and at the opening view a press at the middle of each unit's shape reaches that unit`, clear.behind && clear.reach.length >= 5 && clear.reach.every(([id, got]) => got === id), JSON.stringify(clear));
      await evaluate(`${V}.select(${JSON.stringify(idOf)}, { fly: true })`);
      await sleep(1800);
      let s = await state();
      check(`${species}: a real choice of the vault opens its panel with the footing in its own words, and a door to the Protein atlas`, /Function not known/.test(await evaluate(`${V}.shadowRoot.querySelector("cells-panel")?.textContent || ""`)) && /Named by/.test(s.panel) && s.doors.some((door) => /^Show .* in the Protein atlas/.test(door)), s.panel.slice(0, 200));
      // Each level it has, chosen: its cost within the ceiling.
      for (const level of ["1", "2", "3", "4"]) {
        await evaluate(`${L}.setMode(${JSON.stringify(level)})`);
        await until(`Boolean(${L}.built.get(${JSON.stringify(idOf)})) && (${JSON.stringify(level)} !== "4" || Boolean(${L}.built.get(${JSON.stringify(idOf)}).surface))`, 80);
        await sleep(700);
        const cost = await evaluate(`${L}.cost()`);
        check(`${species}: the vault at level ${level}, within the ceiling`, cost.draws <= 40 && cost.triangles <= 40000, JSON.stringify(cost));
        await shot(`${NAME}-${species}-level-${level}`);
      }
    }
    // A species in which no signature was found: no vault on its bench, and the panel that names it says what was looked for.
    check("the page opens on lens=machines with E. coli", await open("lens=machines&entry=ecoli", 3000));
    const none = await evaluate(`(() => { const lens = ${L}; return { onBench: lens.layout.items.some((value) => value.id === "machine:vault"), panel: ${V}.describe ? "" : "" }; })()`);
    check("E. coli's bench holds no vault", none.onBench === false, JSON.stringify(none));
    await evaluate(`${V}.select(${JSON.stringify(idOf)})`);
    await sleep(1200);
    const away = await state();
    check("E. coli's panel for the vault says what was looked for and that a signature not found is not an absence", /What was looked for/.test(away.panel) && /not an absence/.test(away.panel), away.panel.slice(0, 200));
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
