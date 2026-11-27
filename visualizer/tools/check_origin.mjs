#!/usr/bin/env node
// Checks the origin-of-life view on the map's page (src/lenses/lineage.js, mounted by
// src/lenses/lineage_entry.js through src/ui/entry_views.js) with real pointer and key input,
// through the DevTools protocol, in the manner of tools/check_laws.mjs:
//
//   main     entry=gard shows the view in the first tab's place ("Origin of life"), playing the
//            marked example as the page opens it, after the founder has gathered. The example's
//            mark stands on the picture, uncovered, at every level chosen on the rail, and in the
//            legend's note; the page's one timeline plays and pauses by its button and by the
//            space bar, and a drag on it moves the clock; the card's Similarity select and its
//            packing answer; no select offers the two forms of the law (an example is never one of
//            a pair); a real press on a lipid's head chooses its type, and ] steps a fission. The
//            Laws library and back: the view plays again as it was, and nothing of it stays on the
//            library. The Cell view opened after it is as the Cell view opened alone.
//   physarum  the menu, 3D network and cutaway, and the linked Protein and Engine catalogues.
//   vesicle  the saved vesicle life, divided daughters, threshold crossing and released state, bilayer and molecular reference.
//   phone    the same at a phone's width: the first tab's short name keeps the bar to one row, the
//            card folds to one line that names the model system, apart from the rail's button, and
//            one press on it opens the card with the switch, the word, the packing and both selects
//            (opening the legend folds it again); the example's mark stands clear of the card,
//            folded and open; a molecule seeping in starts inside the frame; at the Lineages level
//            the names that say what the parts are stand; and at 360 px the band under the bar and
//            the mark at three levels hold. The bar's words stand on a fade of the page's ground
//            while the view is shown, at every width, and not on the Laws library.
//   address  entry=gard&scale=<level> opens the view at that level; still=1 holds it still;
//            select=assembly:fission:<run>:<k> opens on that fission with its panel; play=1;
//            lens=laws&entry=gard and back.
//   pair     on a check-only scene whose GARD lists a test's own two made-up runs of one world, one
//            of each form of the law (tests/fixtures/assembly-forms/forms.json, served to the page
//            by the check itself), the view opens on the two lineages side by side, each named by
//            its run and its form, under one clock; the card's switch shows one alone and both
//            again. The published page never carries such a scene.
//   engine   the engine's own runs: the page's, where GARD's entry names any; else a check-only
//            scene of the two runs ENGINE_RUNS names ("<evidence root>::<run>,<run>", the engine's
//            provisional set of 17 November 2026 unless set), adapted here by
//            tools/adapt_assembly_run.py and served by the check itself (it says "skip" and
//            passes nothing where they are not at hand). Wide: the pair side by side, the engine's
//            passive law first, each named; the run's standing, revision and model as the mark, on
//            the picture at every level, in the legend and in the bar, and no word of an example;
//            each run's panel with every line it states, as it states it; a fission of each with
//            its keys; one clock; the switch; less motion. With PHONE=1: one run at a time, the
//            switch in the opened card, the mark clear of it.
//
// The marked example is the cases main, phone, address, frames and pictures: the page's own where
// GARD's entry names it, else a check-only scene that names it (it stays in the repository as a
// fixture for them), so that the page going over to the engine's runs is a change of data alone.
//   frames   no checks: the stage's own frame on the card while the view plays, by turns with the
//            map's chrome shown and hidden, at the window's size; written to the log.
//
//   node tools/check_origin.mjs [OUT_DIR]
//
// Set by the environment: CASE (main, phone, address, pair, engine or frames; main unless set), PHONE, ENGINE_RUNS, THEME
// (dark), WIDTH and HEIGHT, NAME (what the pictures are called in OUT_DIR). One browser at a time:
// it takes the lock in tools/lib/browser_lock.mjs.

import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { readFile, readdir, writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { createServer } from "./serve.mjs";
import { acquireBrowser } from "./lib/browser_lock.mjs";
import { DEFAULT_RUNS, DEFAULT_SCENE, ROOT } from "./lib/build_page.mjs";

const outDir = process.argv[2] ? path.resolve(process.argv[2]) : null;
if (outDir) await mkdir(outDir, { recursive: true });
const CASE = process.env.CASE || "main";
const PHONE = CASE === "phone" || process.env.PHONE === "1";
const WIDTH = Number(process.env.WIDTH || (PHONE ? 400 : 1400)), HEIGHT = Number(process.env.HEIGHT || (PHONE ? 800 : 900));
const NAME = process.env.NAME || `origin-${CASE}`;
const EXAMPLE = "Invented numbers · no run of Cells' engine";
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const results = [];
const check = (name, ok, detail = "") => {
  results.push(Boolean(ok));
  console.log(`${ok ? "pass" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`);
};
const note = (text) => console.log(`note  ${text}`);
const pageLog = [];

// The scene: the page's own, or a check-only one written beside the pictures, never published.
const FORMS = path.join(ROOT, "tests", "fixtures", "assembly-forms", "forms.json"), FORMS_PATH = "models/gard/forms.json";
let scene = process.env.CHECK_SCENE || DEFAULT_SCENE;
const own = JSON.parse(await readFile(scene, "utf8"));
const ownRuns = own.models?.find((model) => model.id === "gard")?.runs || [];
const pageEngine = ownRuns.some((run) => run.kind !== "example");
const sceneDir = outDir || path.join(ROOT, "out", "check-origin");
/** A check-only scene: the page's own, with GARD's runs these. */
async function sceneWith(runs, name) {
  const raw = JSON.parse(JSON.stringify(own));
  raw.models.find((model) => model.id === "gard").runs = runs;
  const file = path.join(sceneDir, `${NAME}-${name}-scene.json`);
  await mkdir(sceneDir, { recursive: true });
  await writeFile(file, JSON.stringify(raw));
  return file;
}
// Files the check serves itself, by the path the page asks for: { "models/gard/<name>.json": text }.
const served = {};
// The engine's runs the engine case shows: the page's, or two adapted here from their folder.
let engineFiles = [], engineRoot = null;
if (CASE === "pair") {
  // The scene's own run stays listed (the page's server serves what it lists); the view is handed the test's file.
  served[FORMS_PATH] = await readFile(FORMS, "utf8");
  scene = await sceneWith([{ file: "data/origin/example-run.json", label: "A test's two made-up runs", kind: "development", path: FORMS_PATH }], "pair");
} else if (CASE === "engine" || (CASE === "frames" && process.env.WAYS === "pair")) {
  if (pageEngine) {
    for (const run of ownRuns.filter((one) => one.kind !== "example")) engineFiles.push(JSON.parse(await readFile(path.join(ROOT, run.file), "utf8")));
    // Where the runs' folders are, to hold each line to run.json's own text (the adapter names each folder relative to it).
    engineRoot = process.env.ENGINE_ROOT || "/mnt/workspaces/Cells";
  } else {
    const [root, list] = (process.env.ENGINE_RUNS || "/mnt/workspaces/Cells::gard-g1-part2-20261117/probes-6af93a51/probes/lineage,gard-g1-part2-20261117/probes-6af93a51/probes/lineage_single_event").split("::");
    const runs = (list || "").split(",").filter(Boolean);
    if (!runs.length || !runs.every((run) => existsSync(path.join(root, run, "run.json")))) {
      console.log(`skip  the engine's runs: GARD's entry names none, and the run folders are not at hand (${root}::${runs.join(",")})`);
      console.log("0 of 0 checks passed");
      process.exit(0);
    }
    const into = path.join(sceneDir, `${NAME}-runs`);
    await mkdir(into, { recursive: true });
    const adapted = spawnSync("python3", ["-I", path.join(ROOT, "tools", "adapt_assembly_run.py"), "--evidence", root, "--out", into, "--standing", "development", "--standing-from", "the check's own scene (tools/check_origin.mjs): the run folders' README", ...runs], { encoding: "utf8" });
    if (adapted.status !== 0) throw new Error(`the adapter refused the runs: ${adapted.stderr}`);
    const names = (await readdir(into)).filter((name) => name.endsWith(".json")).sort();
    const listed = [];
    for (const name of names) {
      const text = await readFile(path.join(into, name), "utf8");
      engineFiles.push(JSON.parse(text));
      served[`models/gard/${name}`] = text;
      listed.push({ file: `data/origin/${name}`, label: `A development run of the engine (${name})`, kind: "development", path: `models/gard/${name}` });
    }
    engineRoot = root;
    scene = await sceneWith(listed, "engine");
  }
} else if (pageEngine && ["main", "phone", "address", "frames", "pictures"].includes(CASE)) {
  // The page plays the engine's runs: the marked example is checked on a scene that names it.
  scene = await sceneWith([{ file: "data/origin/example-run.json", label: "An example of invented numbers", kind: "example", path: "models/gard/example-run.json" }], "example");
}

const release = await acquireBrowser({ wait: Number(process.env.WAIT_MINUTES || 30) * 60 * 1000 });
const server = createServer({ offline: true, scene, runs: DEFAULT_RUNS, log: (line) => pageLog.push(line) });
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}/`;
const chrome = spawn(
  process.env.CHROME || "google-chrome",
  ["--headless=new", `--user-data-dir=${release.profile}`, "--disable-breakpad", "--no-first-run", "--no-sandbox", "--mute-audio", "--hide-scrollbars", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", `--window-size=${WIDTH},${HEIGHT}`, "--remote-debugging-port=0", "about:blank"],
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
  const waiting = new Map(), events = new Set();
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.method) for (const listener of events) listener(message);
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
  await page("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: HEIGHT, deviceScaleFactor: 1, mobile: PHONE });
  if (process.env.THEME === "dark") await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "dark" }] });
  await page("Page.enable");
  await page("Page.addScriptToEvaluateOnNewDocument", {
    source: `window.__pageErrors = []; addEventListener("error", (event) => __pageErrors.push(String(event.error?.stack || event.message))); addEventListener("unhandledrejection", (event) => __pageErrors.push("rejection: " + String(event.reason?.stack || event.reason)));`,
  });
  if (Object.keys(served).length) {
    // The check's own run files, handed to the page where it asks for them.
    await page("Fetch.enable", { patterns: Object.keys(served).map((name) => ({ urlPattern: `*${name}` })) });
    events.add((message) => {
      if (message.method !== "Fetch.requestPaused" || message.sessionId !== sessionId) return;
      const name = Object.keys(served).find((one) => message.params.request.url.endsWith(one));
      const body = Buffer.from(served[name] ?? "{}").toString("base64");
      page("Fetch.fulfillRequest", { requestId: message.params.requestId, responseCode: name ? 200 : 404, responseHeaders: [{ name: "Content-Type", value: "application/json" }], body }).catch(() => {});
    });
  }
  const evaluate = async (expression) => {
    const reply = await page("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (reply.exceptionDetails) throw new Error(reply.exceptionDetails.exception?.description || reply.exceptionDetails.text);
    return reply.result.value;
  };
  const V = "document.querySelector('cells-viewer')", L = `${V}.current`;
  const mouse = (type, x, y, extra = {}) => page("Input.dispatchMouseEvent", { type, x, y, button: "left", buttons: 1, clickCount: 1, ...extra });
  const click = async (x, y, wait = 700) => {
    await mouse("mouseMoved", x, y, { button: "none", buttons: 0 });
    await mouse("mousePressed", x, y);
    await mouse("mouseReleased", x, y, { buttons: 0 });
    await sleep(wait);
  };
  const KEYS = { " ": [32, "Space"], "]": [221, "BracketRight"], Escape: [27, "Escape"] };
  const key = async (name, wait = 600) => {
    const [code, keyCode] = KEYS[name];
    await page("Input.dispatchKeyEvent", { type: "keyDown", key: name, code: keyCode, windowsVirtualKeyCode: code, text: name === " " ? " " : undefined });
    await page("Input.dispatchKeyEvent", { type: "keyUp", key: name, code: keyCode, windowsVirtualKeyCode: code });
    await sleep(wait);
  };
  /** The middle of what an expression finds in the viewer's shadow root, if it is on the screen and nothing lies over it. */
  const placeOf = (expression) =>
    evaluate(`(() => { const root = ${V}.shadowRoot, el = ${expression}; if (!el) return null; el.scrollIntoView({ block: "nearest" }); const r = el.getBoundingClientRect(); if (!r.width || !r.height) return null; const x = r.left + r.width / 2, y = r.top + r.height / 2; const top = root.elementFromPoint(x, y); return top && (top === el || el.contains(top) || top.getRootNode()?.host === el) ? { x, y, words: el.textContent } : null; })()`);
  const until = async (test, tries = 120) => {
    for (let k = 0; k < tries; k++) {
      if (await evaluate(test).catch(() => false)) return true;
      await sleep(250);
    }
    return false;
  };
  const shot = async (name) => {
    if (!outDir) return;
    await evaluate(`new Promise((done) => { ${V}.stage.invalidate(); requestAnimationFrame(() => requestAnimationFrame(done)); })`);
    await sleep(300);
    const { data } = await page("Page.captureScreenshot", { format: "png" });
    await writeFile(path.join(outDir, `${name}.png`), Buffer.from(data, "base64"));
    note(`wrote ${path.join(outDir, `${name}.png`)}`);
  };
  /** Open the page; with a model system named, wait for its own view (not the card that stands in while its run files are read). */
  const open = async (query, view = /entry=gard/.test(query) && !/lens=(?!cell)/.test(query)) => {
    await page("Page.navigate", { url: `${base}?${query}` });
    const up = await until(view ? `${L}?.id === "origin"` : `Boolean(${V}?.current)`, 240);
    await sleep(1200);
    return up;
  };
  const state = () =>
    evaluate(`(() => {
      const v = ${V}, root = v.shadowRoot, lens = v.current, panel = root.querySelector("cells-panel"), first = root.querySelector('.switch [data-lens="cell"]');
      return { lens: v.state.lens, model: v.state.model, view: lens?.id || null, level: lens?.level || null, selected: v.state.selected, playing: Boolean(lens?.player?.playing), time: lens?.player ? +lens.player.time.toFixed(3) : null,
        gathering: Boolean(lens?.sides?.[0]?.layout?.gathering), tab: first ? { words: first.textContent, pressed: first.getAttribute("aria-pressed") } : null,
        panel: panel && !panel.hidden ? panel.textContent : "", rail: [...root.querySelectorAll(".rail button, .rail [data-scale]")].map((b) => b.textContent.trim()).filter(Boolean),
        railTitle: root.querySelector(".rail-title")?.textContent || null, timeline: (() => { const t = root.querySelector("cells-timeline"); return t ? { shown: !t.hidden, bound: t.player === lens?.player } : null; })(),
        legend: root.querySelector("cells-legend")?.textContent || "", insets: v.stage?.insets || {} };
    })()`);
  /** The example's mark on the picture: shown, inside the window, under the bar, and no card of the page over it. */
  const mark = (text = EXAMPLE) =>
    evaluate(`(() => { const v = ${V}, root = v.shadowRoot, labels = [...root.querySelectorAll(".labels .label")].filter((el) => el.textContent === ${JSON.stringify(text)}); const el = labels[0]; if (!el) return { count: 0 }; const r = el.getBoundingClientRect(), o = v.getBoundingClientRect(); const box = { left: r.left - o.left + 4, top: r.top - o.top + 2, right: r.right - o.left - 4, bottom: r.bottom - o.top - 2 }; const bar = root.querySelector(".bar").getBoundingClientRect(); const cards = v.blockedRects(); const over = cards.filter((c) => box.left < c.right && box.right > c.left && box.top < c.bottom && box.bottom > c.top); return { count: labels.length, off: el.classList.contains("is-off"), inside: r.left >= o.left && r.right <= o.right && r.top >= o.top && r.bottom <= o.bottom, uncovered: over.length === 0 && r.top >= bar.bottom - 2, box: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)], over: over.map((c) => [Math.round(c.left), Math.round(c.top), Math.round(c.right), Math.round(c.bottom)]), bar: Math.round(bar.bottom) }; })()`);
  const markShows = (m) => m.count === 1 && !m.off && m.inside && m.uncovered;
  /** On a phone, the band under the bar: the card folded to its line (whole), the rail's button apart from it, both under the bar, and the bar on one row. */
  const band = () =>
    evaluate(`(() => { const root = ${V}.shadowRoot, shown = (el) => Boolean(el) && el.getClientRects().length > 0, t = root.querySelector(".view-toggle"), r = root.querySelector(".rail-toggle"), line = t?.firstChild, bar = root.querySelector(".bar"); const a = shown(t) ? t.getBoundingClientRect() : null, b = shown(r) ? r.getBoundingClientRect() : null, under = bar.getBoundingClientRect().bottom - 0.5; const kids = [...bar.children].filter(shown).map((el) => el.getBoundingClientRect()).filter((k) => k.width > 1); return { folded: Boolean(a) && !shown(root.querySelector("#cells-view")), words: line?.textContent ?? null, whole: Boolean(line) && line.scrollWidth <= line.clientWidth + 1, rail: Boolean(b), apart: !a || !b || a.right <= b.left - 0.5 || a.bottom <= b.top + 0.5 || b.bottom <= a.top + 0.5, belowBar: (!a || a.top >= under) && (!b || b.top >= under), oneRow: kids.every((p) => kids.every((q) => p.top < q.bottom - 1 && q.top < p.bottom - 1)), first: root.querySelector('.switch [data-lens="cell"]')?.innerText.trim() ?? null, railUnder: root.querySelector(".frame").classList.contains("rail-under") }; })()`);
  const bandHolds = (b) => b.folded && b.words === "GARD assembly" && b.whole && b.rail && b.apart && b.belowBar && b.oneRow;
  /** The bar's words on a ground of the page's own colour, while the view is shown (a fade in the bar's own box, no blur). */
  const ground = () => evaluate(`(() => { const s = getComputedStyle(${V}.shadowRoot.querySelector(".bar")); return { image: s.backgroundImage.slice(0, 40), blur: s.backdropFilter || "none" }; })()`);
  /** The legend's note: there, and in the legend's visible box (not below its fold, nor under the timeline). */
  const noteShows = () =>
    evaluate(`(() => { const root = ${V}.shadowRoot, legend = root.querySelector("cells-legend"), note = legend?.querySelector(".legend-note, .legend-key-note"); if (!legend || legend.hidden || !note) return { there: false }; const box = legend.getBoundingClientRect(), n = note.getBoundingClientRect(), t = root.querySelector("cells-timeline"); const tl = t && !t.hidden ? t.getBoundingClientRect() : null; let clip = box; for (let el = note.parentElement; el && el !== legend.parentElement; el = el.parentElement) { const s = getComputedStyle(el); if (/(auto|scroll|hidden)/.test(s.overflowY)) { const r = el.getBoundingClientRect(); clip = { top: Math.max(clip.top, r.top), bottom: Math.min(clip.bottom, r.bottom) }; } } const top = root.elementFromPoint(n.left + n.width / 2, n.top + Math.min(n.height - 2, 8)), bottom = root.elementFromPoint(n.left + n.width / 2, n.bottom - 4); const inView = n.top >= clip.top - 1 && n.bottom <= clip.bottom + 1 && n.height > 0 && [top, bottom].every((el) => el && (el === note || note.contains(el))); return { there: true, inView, words: note.textContent.slice(0, 60), note: [Math.round(n.top), Math.round(n.bottom)], clip: [Math.round(clip.top), Math.round(clip.bottom)] }; })()`);
  /** Choose a level by a real press on its rail button (on a phone the rail opens first). */
  const level = async (id) => {
    if (PHONE) {
      const toggle = await placeOf(`root.querySelector(".rail-toggle")`);
      if (toggle) await click(toggle.x, toggle.y, 500);
    }
    const label = await evaluate(`${L}.levels().find((item) => item.id === ${JSON.stringify(id)})?.label`);
    const at = await placeOf(`[...root.querySelectorAll(".rail button")].find((b) => b.textContent.trim() === ${JSON.stringify(label)})`);
    if (at) await click(at.x, at.y, 2200);
    return Boolean(at);
  };
  const look = () => evaluate(`(() => { const v = ${V}, st = v.stage, r = st.renderer; return { sun: st.sun.position.toArray().map((x) => +x.toFixed(3)), shadow: st.sun.castShadow, limits: { ...st.rig.limits }, environment: Boolean(st.scene.environment), exposure: +r.toneMappingExposure.toFixed(3), toneMapping: r.toneMapping, bloom: st.finish?.bloom?.strength ?? 0, insets: st.insets || {}, sky: +st.sky.intensity.toFixed(3), fog: Boolean(st.scene.fog), children: st.scene.children.length }; })()`);

  if (CASE === "physarum") {
    const root = V + ".shadowRoot";
    const press = async selector => {
      const at = await placeOf(`root.querySelector(${JSON.stringify(selector)})`);
      if (!at) throw Error("Control missing or covered: " + selector);
      await click(at.x,at.y,150);
    };
    const openCard = () => evaluate(`if(${V}.frame.classList.contains("card-folds") && !${V}.state.viewOpen) ${V}.toggleViewCard(true)`);
    await open("lens=cell&still=1", false);
    if (PHONE) await openCard();
    await press(".species-pick");
    const row = await placeOf('Array.from(root.querySelectorAll("#species-list [role=option]")).find(el=>el.textContent.includes("Physarum Lagrangian"))');
    if (row) await click(row.x,row.y,150);
    check("the Physarum menu item opens the plasmodium", await until(`${L}?.id==="physarum" && ${L}.network.visible`,40));
    check("the scene displays the illustration label",await evaluate(`${root}.querySelector(".caveat").textContent.includes("schematic")`));
    check("the three selectable network structures have real geometry",await evaluate(`${L}.network.children.filter(x=>x.userData.pick).length===3 && ${L}.has("physarum:veins")`));
    await shot(NAME+"-network");
    check("the rail opens the vein cutaway",await level("vein") && (await state()).level==="vein");
    if (PHONE) await openCard();
    const before=await evaluate(`({x:${L}.parcel.position.x,d:${L}.arrows.children[0].quaternion.toArray()})`);
    await press('[data-physarum="reverse"]');
    const after=await evaluate(`({x:${L}.parcel.position.x,d:${L}.arrows.children[0].quaternion.toArray()})`);
    check("reversal changes the arrows while keeping the same material parcel position",Math.abs(after.x-before.x)<1e-8 && JSON.stringify(before.d)!==JSON.stringify(after.d));
    if (PHONE && (await evaluate(`${V}.state.viewOpen`))) await press(".view-toggle");
    await shot(NAME+"-cutaway");
    if (PHONE) await openCard();
    await press('[data-physarum="proteins"]');
    check("the Physarum protein catalogue opens with its 43 reviewed entries",await until(`${L}.mounted?.shelves.id==="physarum" && ${L}.mounted.shelves.data.proteins.length===43`,65));
    check("the catalogue finds the organism's exact reviewed plasmodial actin",await evaluate(`${L}.searchOwn("P02576").then(x=>x.proteins.some(p=>p.id==="P02576"))`));
    await shot(NAME+"-proteins");
    await open("lens=engine&select=models.physarum&still=1",false);
    check("Engine opens the planned Physarum entry",await until(`${V}.state.selected==="models.physarum"`,40) && /Planned/.test((await state()).panel));
    const door = await placeOf('Array.from(root.querySelectorAll(".panel-door button")).find(el=>el.textContent.includes("3D organism"))');
    if (door) await click(door.x,door.y,150);
    check("Engine links back to the 3D model menu entry",await until(`${L}?.id==="physarum" && ${V}.state.model==="physarum"`,50));
    await open("entry=physarum&scale=vein&still=1",false);
    check("a shared link opens the cutaway",await until(`${L}?.id==="physarum" && ${L}.level==="vein"`,50));
  } else if (CASE === "vesicle") {
    await open("entry=origin-vesicles&still=1", false);
    const ready = await until(`${L}?.id === "vesicle"`, 90);
    check("the vesicle entry opens its own saved run", ready);
    if (!ready) throw Error(await evaluate(`${V}.shadowRoot.querySelector("#cells-view")?.textContent || "No vesicle view"`));
    const select = (label, expression) =>
      evaluate(
        `(() => {const e=${V}.shadowRoot.querySelector('select[aria-label="${label}"]');e.value=${expression};e.dispatchEvent(new Event("change",{bubbles:true}));})()`,
      );
    const lookAt = async (name) => {
      const hide = PHONE && (await evaluate(`${V}.state.viewOpen`));
      if (hide) await evaluate(`${V}.shadowRoot.querySelector(".view-toggle").click()`);
      await shot(NAME + "-" + name);
      if (hide) await evaluate(`${V}.shadowRoot.querySelector(".view-toggle").click()`);
    };
    if (PHONE) await evaluate(`if(!${V}.state.viewOpen) ${V}.shadowRoot.querySelector(".view-toggle").click()`);
    check(
      "both development runs are navigable",
      await evaluate(`${L}.entries.length>=2 && ${L}.run.file.development.says.includes("not judged.")`),
    );
    if (PHONE) {
      await evaluate(`${V}.shadowRoot.querySelector(".view-toggle").click()`);
      check("the run's full standing is visible with the phone card folded", await evaluate(`(() => { const c=${V}.shadowRoot.querySelector(".caveat");return c.getBoundingClientRect().height>0 && c.textContent===${L}.run.file.development.says; })()`));
      await evaluate(`${V}.shadowRoot.querySelector(".view-toggle").click()`);
    }
    await lookAt("life");
    await evaluate(`${L}.seek(4.78)`);
    check("the illustrated neck narrows before the recorded split while the parent keeps its contents",
      await evaluate(`${L}.scene.shearUniforms.pinch.value > 0.7 && !${L}.scene.daughter.visible && ${L}.run.at(4.78).counts[2] > 400`));
    await lookAt("neck");
    await evaluate(`${L}.seek(0)`);
    await evaluate(`${L}.player.play()`);
    check("the clock advances in recorded seconds", await until(`0 < ${L}.player.time && ${L}.player.time < 2`, 12));
    await evaluate(`${L}.seek(0)`);
    check(
      "picking the membrane explains the footprint and recorded species",
      await evaluate(
        `(() => {const part=${L}.describe("vesicle:membrane");return part.facts.some(([k,v])=>k==="Membrane counts"&&v.includes("L1"));})()`,
      ),
    );
    await select("Go to event", '"0"');
    check(
      "the first shear identifies both daughters and the continuing lineage",
      await evaluate(`${L}.player.time===5 && ${L}.eventRead.textContent.includes("continues") && ${L}.scene.daughter.visible`),
    );
    await lookAt("split");
    await evaluate(`${L}.seek(5.65)`);
    check("both labelled daughters separate and the sister has a packed membrane", await evaluate(
      `${L}.scene.daughter.position.x>0 && ${L}.scene.whole.position.x<0 && ${L}.scene.sisterLipids.heads.count>100 && ${L}.tags.shell.text.includes("continues")`));
    if (PHONE) check("the phone frames both daughter silhouettes", await evaluate(`(() => {
      const l=${L}, a=l.scene.whole.position.clone(), b=l.scene.daughter.position.clone();
      a.x-=l.scene.coat.scale.x; b.x+=l.scene.daughter.scale.x;
      return a.project(l.stage.camera).x>=-1 && b.project(l.stage.camera).x<=1;
    })()`));
    await lookAt("daughters");
    await evaluate(`${L}.seek(15)`);
    check("a refused shear retains one parent", await evaluate(`!${L}.scene.daughter.visible && ${L}.scene.shearUniforms.pinch.value===0`));
    await evaluate(`[...${V}.shadowRoot.querySelectorAll(".v-boundary button")].find(b=>b.textContent.includes("at the membrane")).click()`);
    check("the membrane shortcut opens the multispecies run at an actual inward solute transfer", await until(
      `${L}.level==="membrane" && ${L}.scene.trackedMove?.to.phase==="lumen" && ${L}.scene.trackedMove.from.species==="G"`));
    await evaluate(`${L}.goToScale("vesicle")`);
    await select("Colour by", '"tension"');
    await evaluate(`[...${V}.shadowRoot.querySelectorAll(".v-boundary button")].find(b=>b.textContent==="Last intact state").click()`);
    check(
      "the intact threshold sample has a lumen and its recorded triggering tension",
      await evaluate(
        `${L}.scene.whole.visible && ${L}.scene.liquid.visible && ${L}.run.at(${L}.player.time,0,${L}.inspectRow).sample.tension_N_per_m===${L}.run.file.releases[0].tension_N_per_m`,
      ),
    );
    await lookAt("intact");
    await select("Plot", '"lumen_volume_L"');
    check("the intact-volume plot exposes its measured range in litres", await evaluate(`${V}.shadowRoot.querySelector(".v-chart figcaption").textContent.includes("3.411e-19–3.444e-19 L")`));
    await lookAt("volume");
    await select("Plot", '"tension_N_per_m"');
    await evaluate(`[...${V}.shadowRoot.querySelectorAll(".v-boundary button")].find(b=>b.textContent==="Released state").click()`);
    check(
      "the same instant shows threshold release and the returned pool molecules",
      await evaluate(`${L}.scene.release.visible && !${L}.scene.whole.visible && ${L}.eventRead.textContent.includes("61,178")`),
    );
    await lookAt("lysis");
    await evaluate(`${L}.goToScale("membrane")`);
    check(
      "the section draws both headgroup surfaces and tails",
      await evaluate(
        `${L}.scene.patch.visible && ${L}.scene.section.heads.count>100 && ${L}.scene.section.tails.count===${L}.scene.section.heads.count`,
      ),
    );
    check("the released vesicle has no ongoing crossings", await evaluate(`!${L}.scene.flights.visible`));
    await select("Exchange route", `[...${L}.run.routes.values()].find(r=>r.from.phase==="pool" && r.to.phase==="lumen").key`);
    check("selecting inward G jumps to its recorded event and draws a solute in the membrane section",
      await evaluate(`${L}.routeTimes.includes(${L}.player.time) && ${L}.scene.travelSolutes.count===1 && ${L}.scene.travelLipids.heads.count===0`));
    await evaluate(`${L}.seek(${L}.player.time+0.41)`);
    await lookAt("permeation");
    await select("Exchange route", `[...${L}.run.routes.values()].find(r=>r.to.species==="L2" && r.to.phase==="pool").key`);
    check("the rare outward L2 event has a lipid head and tails and an outward arrow", await evaluate(
      `${L}.scene.travelLipids.heads.count===1 && ${L}.scene.travelLipids.tails.count===1 && ${L}.scene.arrows.count===1 && ${L}.eventRead.textContent.includes("membrane → pool")`));
    await evaluate(`${L}.seek(${L}.player.time+0.4)`);
    await lookAt("membrane");
    await evaluate(`${L}.goToScale("molecule")`);
    check(
      "the molecular close-up draws the reference atoms and labels the source",
      await evaluate(`${L}.scene.molecule.visible && ${V}.shadowRoot.querySelector("#cells-view").textContent.includes("wwPDB")`),
    );
    await lookAt("molecule");
    await evaluate(`${V}.shadowRoot.querySelector(".v-catalysis a").click()`);
    check("the catalysis link opens GARD's separate assembly and recorded world", await until(
      `${L}?.id==="origin" && ${L}.level==="assembly" && !${L}.mainRun.example && ${L}.sides[0].network.links.count>0`, 160));
    await evaluate(`${L}.player.pause();${V}.shadowRoot.querySelector(".origin-strengths").open=true`);
    check("the ranked links and the picked interior arrow give the same directed table coefficient", await until(
      `(() => {const l=${L},n=l.sides[0].network,k=n.linkIds[0],v=n.drawn[0].links[0]?.v;return k && l.describe(k).facts.some(([name,x])=>name==="Recorded log₁₀ β"&&x===v.toFixed(2)) && l.networkRows.textContent.includes(v.toFixed(2));})()`));
    await evaluate(`${L}.networkRows.querySelector("button").click()`);
    check("choosing a strength opens its coefficient and holds the assembly clock", await until(
      `${L}.selected?.startsWith("assembly:entry:") && !${L}.player.playing && ${V}.shadowRoot.querySelector("cells-panel")?.textContent.includes("Recorded log₁₀ β")`));
  } else if (CASE === "main" || CASE === "phone") {
    // ---------------------------------------------------------- the view in the first tab's place, playing the marked example
    check("entry=gard opens the origin-of-life view in the first tab's place", await open("entry=gard"));
    let s = await state();
    check(`the first tab names it (${PHONE ? "its short name" : "Origin of life"}), pressed`, s.tab?.pressed === "true" && (PHONE ? /Origin$/.test(s.tab.words) : /Origin of life/.test(s.tab.words)), JSON.stringify(s.tab));
    check("its levels are on the rail, under Level", s.railTitle === "Level" && (PHONE || ["Molecules", "One assembly", "Population", "Lineages"].every((name) => s.rail.includes(name))), JSON.stringify([s.railTitle, s.rail]));
    check("the page's one timeline is the view's", s.timeline?.shown && s.timeline.bound, JSON.stringify(s.timeline));
    check("at the run's start the founder gathers, and the clock stands", s.gathering && s.time === 0, JSON.stringify([s.gathering, s.time]));
    await shot(`${NAME}-gathering`);
    check("once gathered, the page plays the marked example by itself", await until(`${L}.player.playing && ${L}.player.time > 0.05`, 80), JSON.stringify(await state()));
    // The protocell, playing: the run's joins and leaves are seen coming and going, and its inside is lit from the run's table.
    const stream = await evaluate(`(async () => { const l = ${L}; let seen = 0; for (let i = 0; i < 20; i++) { await new Promise((r) => setTimeout(r, 100)); if (l.sides[0].layout.inMotion().flying > 0) seen++; } return { shape: l.shape, seen, links: l.sides[0].network.drawn[0]?.links.length ?? 0, key: l.streamWords() }; })()`);
    check("playing, the protocell's joins and leaves are seen coming and going nearly all the time, its inside lit from the run's table", stream.shape === "protocell" && stream.seen >= 16 && stream.links > 0 && /^in, out: /.test(stream.key), JSON.stringify(stream));
    s = await state();
    check("the legend's note gives the example's mark and the picture's own words", s.legend.includes(EXAMPLE) && /No law of Cells computes how the lipids move and pack/.test(s.legend), s.legend.slice(0, 200));
    check("no choice offers the two forms of the law: the example is never one of a pair", !(await evaluate(`Boolean(${V}.shadowRoot.querySelector('[data-choice="pair"]'))`)));
    if (PHONE) {
      const bar = await evaluate(`(() => { const root = ${V}.shadowRoot, bar = root.querySelector(".bar") || root.querySelector("header"); const buttons = [...root.querySelectorAll(".switch button")]; const tops = buttons.map((b) => Math.round(b.getBoundingClientRect().top)); const list = root.querySelector(".index-button, [aria-controls='cells-index']"); return { tops, list: list ? Math.round(list.getBoundingClientRect().top) : null, height: Math.round((bar || root.querySelector(".switch")).getBoundingClientRect().height), words: buttons.map((b) => b.textContent) }; })()`);
      check("the first tab's short name keeps the bar to one row", new Set([...bar.tops, ...(bar.list === null ? [] : [bar.list])]).size <= 1 || Math.max(...bar.tops, bar.list ?? 0) - Math.min(...bar.tops, bar.list ?? 0) < 20, JSON.stringify(bar));
      const b = await band();
      check("on a phone the card folds to one line under the bar that names the model system, whole, and the rail's button stands apart from it", bandHolds(b), JSON.stringify(b));
    }
    const g = await ground();
    check("the bar's words stand on a fade of the page's ground while the view is shown, with no backdrop blur", /gradient/.test(g.image) && g.blur === "none", JSON.stringify(g));

    // ---------------------------------------------------------- the example's mark, at every level, playing and still
    for (const id of ["molecules", "population", "lineage", "assembly"]) {
      const pressed = await level(id);
      await sleep(600);
      const m = await mark();
      s = await state();
      check(`the example's mark stands on the picture, uncovered, at ${id} (chosen on the rail)`, pressed && s.level === id && markShows(m), JSON.stringify([pressed, s.level, m]));
      // On a phone the legend stands folded under its title: it is opened as a visitor opens it, and closed again.
      const folded = PHONE && (await evaluate(`${V}.shadowRoot.querySelector("cells-legend .legend-toggle")?.getAttribute("aria-expanded") === "false"`));
      const fold = folded ? await placeOf(`root.querySelector("cells-legend .legend-toggle")`) : null;
      if (fold) await click(fold.x, fold.y, 700);
      const n = await noteShows();
      check(`and the legend's note, with the mark, is in the legend's view at ${id}${PHONE ? " (the legend opened)" : ""}`, n.there && n.inView && n.words.startsWith(EXAMPLE), JSON.stringify(n));
      if (fold) {
        const again = await placeOf(`root.querySelector("cells-legend .legend-toggle")`);
        if (again) await click(again.x, again.y, 600);
      }
      if (id !== "assembly") await shot(`${NAME}-${id}`);
    }
    await evaluate(`${L}.player.pause()`);
    await sleep(500);
    check("and still", markShows(await mark()), JSON.stringify(await mark()));

    // ---------------------------------------------------------- the timeline: its button, the space bar, a drag
    const play = await placeOf(`root.querySelector("cells-timeline .tl-play")`);
    if (play) await click(play.x, play.y, 900);
    const t0 = (await state()).time;
    await sleep(1500);
    s = await state();
    check("the timeline's button plays", play && s.playing && s.time > t0, JSON.stringify([Boolean(play), s.playing, t0, s.time]));
    if (play) await click(play.x, play.y, 600);
    check("and pauses", !(await state()).playing);
    await evaluate(`${V}.canvas.focus()`);
    await key(" ", 900);
    check("the space bar plays", (await state()).playing);
    await key(" ", 600);
    check("and pauses", !(await state()).playing);
    const range = await evaluate(`(() => { const r = ${V}.shadowRoot.querySelector("cells-timeline .tl-range").getBoundingClientRect(); return { left: r.left + 8, right: r.right - 8, y: r.top + r.height / 2 }; })()`);
    await mouse("mouseMoved", range.left + (range.right - range.left) * 0.2, range.y, { button: "none", buttons: 0 });
    await mouse("mousePressed", range.left + (range.right - range.left) * 0.2, range.y);
    for (let step = 1; step <= 6; step++) await mouse("mouseMoved", range.left + (range.right - range.left) * (0.2 + 0.05 * step), range.y);
    await mouse("mouseReleased", range.left + (range.right - range.left) * 0.5, range.y, { buttons: 0 });
    await sleep(1200);
    s = await state();
    check("a drag on the timeline moves the clock (to about the middle of 120 fissions)", s.time > 45 && s.time < 75, String(s.time));
    // A speed chosen in the timeline's own list: the legend's key says the stream's N at that speed.
    const speedButton = await placeOf(`root.querySelector("cells-timeline .tl-speed")`);
    if (speedButton) await click(speedButton.x, speedButton.y, 600);
    const fast = await placeOf(`[...root.querySelectorAll("cells-timeline .tl-speed-step")].find((b) => b.querySelector("b")?.textContent.trim() === "2/s")`);
    if (fast) await click(fast.x, fast.y, 900);
    const keyed = await evaluate(`(() => { const l = ${L}; return { speed: l.player.speed, key: [...${V}.shadowRoot.querySelectorAll("cells-legend .legend-item")].map((el) => el.textContent).find((t) => /^in, out/.test(t)) || null, said: l.streamWords() }; })()`);
    check("a speed chosen in the timeline's list (2 a second): the legend's key says how many of the joins and leaves are drawn in flight", Boolean(speedButton && fast) && keyed.speed === 2 && Boolean(keyed.key) && keyed.key.includes(keyed.said.replace(/^in, out: /, "")), JSON.stringify(keyed));
    await evaluate(`${L}.player.setSpeed(0.5)`);
    await shot(`${NAME}-dragged`);

    // ---------------------------------------------------------- the card's choices (on a phone, in the card a press on its folded line opens)
    if (PHONE) {
      const line = await placeOf(`root.querySelector(".view-toggle")`);
      if (line) await click(line.x, line.y, 900);
      const opened = await evaluate(`(() => { const root = ${V}.shadowRoot, shown = (el) => Boolean(el) && el.getClientRects().length > 0, card = root.querySelector("#cells-view"), r = card.getBoundingClientRect(); const big = (el) => shown(el) && Math.min(el.getBoundingClientRect().width, el.getBoundingClientRect().height) >= 44; const buttons = [...card.querySelectorAll("button")]; const selects = [card.querySelector("#cells-mark"), card.querySelector('[data-choice="compare"]')]; return { open: shown(card) && r.top >= 0 && r.bottom <= innerHeight, pick: shown(card.querySelector(".species-pick")), word: [...card.querySelectorAll(".species-state")].filter(shown).map((b) => b.textContent)[0] ?? null, packing: ["Protocell", "Micelle", "Cluster"].map((w) => big(buttons.find((b) => b.textContent.trim() === w))), selects: selects.map(big), labels: selects.map((s) => s?.closest(".card-marks")?.querySelector(".seg-label")?.textContent ?? null) }; })()`);
      check("on a phone one press on the folded line opens the card: the switch, the model system's word, Protocell, Micelle and Cluster, and the Composition and Similarity selects, each at least 44 px", Boolean(line) && opened.open && opened.pick && ["Designed, not modelled", "Modelled"].includes(opened.word) && opened.packing.every(Boolean) && opened.selects.every(Boolean) && opened.labels.join("|") === "Composition|Similarity", JSON.stringify(opened));
      await sleep(900);
      const m = await mark();
      check("and the example's mark keeps clear of the opened card", markShows(m), JSON.stringify(m));
      // The opened card says the example's mark itself: at 390 px and under, the card leaves the mark on the picture no room beside it.
      const inCard = await evaluate(`(() => { const el = ${V}.shadowRoot.querySelector("#cells-view .view-notice"); return el && el.getClientRects().length ? el.textContent : null; })()`);
      check("and the opened card carries the example's mark itself", inCard === EXAMPLE, String(inCard));
      await shot(`${NAME}-card-open`);
    }
    const similarity = await placeOf(`root.querySelector('[data-choice="compare"]')`);
    check("the card offers Similarity as a select", Boolean(similarity), JSON.stringify(similarity));
    // A select is chosen with its own keys, as a visitor does without the list open: focused, then the arrow down.
    const pick = async (selector) => {
      await evaluate(`${V}.shadowRoot.querySelector(${JSON.stringify(selector)}).focus()`);
      await page("Input.dispatchKeyEvent", { type: "keyDown", key: "ArrowDown", code: "ArrowDown", windowsVirtualKeyCode: 40 });
      await page("Input.dispatchKeyEvent", { type: "keyUp", key: "ArrowDown", code: "ArrowDown", windowsVirtualKeyCode: 40 });
      await sleep(700);
    };
    if (similarity) {
      await pick('[data-choice="compare"]');
      check("the arrow key on Similarity chooses 'the parent against the other daughter', and the view compares that", (await evaluate(`${L}.compare`)) === "other", await evaluate(`${L}.compare`));
      const composition = await placeOf(`root.querySelector("#cells-mark")`);
      if (composition) await pick("#cells-mark");
      check("the arrow key on Composition chooses the strip, and the view draws it", (await evaluate(`${L}.composition`)) === "strip", await evaluate(`${L}.composition`));
      await evaluate(`(() => { const root = ${V}.shadowRoot; for (const [selector, value] of [['[data-choice="compare"]', "carried"], ["#cells-mark", "wheel"]]) { const select = root.querySelector(selector); select.value = value; select.dispatchEvent(new Event("change", { bubbles: true })); } })()`);
      await sleep(400);
    }
    const cluster = await placeOf(`[...root.querySelectorAll("#cells-view button")].find((b) => b.textContent.trim() === "Cluster")`);
    if (cluster) await click(cluster.x, cluster.y, 900);
    check("a real press on Cluster packs the lipids loosely", (await evaluate(`${L}.shape`)) === "cluster");
    const micelle = await placeOf(`[...root.querySelectorAll("#cells-view button")].find((b) => b.textContent.trim() === "Micelle")`);
    if (micelle) await click(micelle.x, micelle.y, 900);
    check("and Micelle", (await evaluate(`${L}.shape`)) === "micelle");
    if (PHONE) {
      // Opening the legend folds the card again, as in the protein atlas; the legend is closed after.
      const legend = await placeOf(`root.querySelector("cells-legend .legend-toggle")`);
      if (legend) await click(legend.x, legend.y, 700);
      const now = await evaluate(`(() => { const root = ${V}.shadowRoot, shown = (el) => Boolean(el) && el.getClientRects().length > 0; return { legend: root.querySelector("cells-legend .legend-toggle")?.getAttribute("aria-expanded") ?? null, card: shown(root.querySelector("#cells-view")), line: shown(root.querySelector(".view-toggle")) }; })()`);
      check("on a phone opening the legend folds the card to its line again", Boolean(legend) && now.legend === "true" && !now.card && now.line, JSON.stringify(now));
      const again = await placeOf(`root.querySelector("cells-legend .legend-toggle")`);
      if (again) await click(again.x, again.y, 600);
      // The other packing: the micelle, chosen above (a phone opens with the cluster); the band and the mark hold with it too.
      await sleep(900);
      const [b, m] = [await band(), await mark()];
      check("with the micelle packed, the card folded: the band under the bar holds and the example's mark stands uncovered", (await evaluate(`${L}.shape`)) === "micelle" && bandHolds(b) && markShows(m), JSON.stringify([b, m]));
      const line = await placeOf(`root.querySelector(".view-toggle")`);
      if (line) await click(line.x, line.y, 700);
    }
    // Back to the protocell, the packing the view opens with, by a real press.
    const protocell = await placeOf(`[...root.querySelectorAll("#cells-view button")].find((b) => b.textContent.trim() === "Protocell")`);
    if (protocell) await click(protocell.x, protocell.y, 900);
    check("and Protocell back: the view's own packing", (await evaluate(`${L}.shape`)) === "protocell");
    if (PHONE) {
      const line = await placeOf(`root.querySelector(".view-toggle")`);
      if (line && (await evaluate(`${V}.shadowRoot.querySelector("#cells-view")?.getClientRects().length > 0`))) await click(line.x, line.y, 700);
    }

    // ---------------------------------------------------------- a press on a head, and a key
    await evaluate(`(() => { const l = ${L}; l.player.pause(); l.player.seek(30.55); })()`);
    await sleep(1500);
    const head = await evaluate(`(() => { const v = ${V}, l = v.current, side = l.sides[0]; const r = v.canvas.getBoundingClientRect(); const seen = side.layout.beads.filter((b) => b.pos && b.axis).map((b) => { const p = new v.stage.camera.position.constructor(...b.pos).add(side.group.position); const q = v.stage.project(p, p.clone()); return { x: r.left + q.x, y: r.top + q.y, z: q.z, type: b.type }; }).filter((b) => b.x > r.left + 20 && b.x < r.right - 20 && b.y > r.top + 80 && b.y < r.bottom - 80).sort((a, b) => a.z - b.z); return seen[0] || null; })()`);
    if (head) await click(head.x, head.y, 1200);
    s = await state();
    check("a real press on a lipid's head of the protocell (through its see-through near side) chooses its type, and the panel says what it is", (await evaluate(`${L}.shape`)) === "protocell" && /^assembly:type:\d+$/.test(s.selected || "") && /A molecule type/.test(s.panel), JSON.stringify([s.selected, s.panel.slice(0, 80)]));
    await shot(`${NAME}-type`);
    await key("Escape");
    await evaluate(`${V}.canvas.focus()`);
    await key("]", 1200);
    s = await state();
    check("] steps to the next fission and opens it", /^assembly:fission:lineage-a:3[12]$/.test(s.selected || "") && !s.playing, JSON.stringify([s.selected, s.time]));
    await key("Escape");

    // ---------------------------------------------------------- another tab and back
    await evaluate(`${L}.player.play()`);
    await sleep(500);
    const laws = await placeOf(`root.querySelector('.switch [data-lens="laws"]')`);
    if (laws) await click(laws.x, laws.y, 2500);
    s = await state();
    const left = await evaluate(`(() => { const v = ${V}, root = v.shadowRoot; return { timeline: !root.querySelector("cells-timeline").hidden, level: [...root.querySelectorAll(".rail")].some((r) => !r.hidden && /Level/.test(r.textContent)), water: v.stage.scene.children.some((c) => c === v.lenses.get("model:gard")?.water?.group), labels: [...root.querySelectorAll(".labels .label")].some((el) => el.textContent === ${JSON.stringify(EXAMPLE)}) }; })()`);
    check("on the Laws library nothing of the view stays: no timeline, no Level rail, no water, no mark", s.lens === "laws" && !left.timeline && !left.level && !left.water && !left.labels, JSON.stringify([s.lens, left]));
    const bare = await ground();
    check("nor the bar's ground: the library draws nothing under the bar", bare.image === "none", JSON.stringify(bare));
    const first = await placeOf(`root.querySelector('.switch [data-lens="cell"]')`);
    if (first) await click(first.x, first.y, 2500);
    s = await state();
    check("back on the first tab: the view again, playing as it was", s.view === "origin" && s.playing, JSON.stringify([s.view, s.playing, s.time]));

    // ---------------------------------------------------------- the Cell view after it is the Cell view opened alone
    if (!PHONE) {
      await evaluate(`${V}.setEntry("human", { user: true })`);
      await sleep(2500);
      const after = await look();
      await shot(`${NAME}-cell-after`);
      await open("lens=cell&entry=human", false);
      await sleep(1500);
      const alone = await look();
      check("the Cell view opened after the view is as it is opened alone: light, shade, bloom, limits, insets, fog and what stands in the scene", JSON.stringify(after) === JSON.stringify(alone), JSON.stringify([alone, after]));
    } else {
      // A molecule seeping in starts inside the frame on a phone.
      await open("entry=gard");
      const inside = await evaluate(`(async () => { const v = ${V}, l = v.current; l.hold(true); l.player.setSpeed(0.001); l.player.seek(30.2); l.sync(0); const events = l.mainRun.growthEvents(30); let j = 8; while (events[j] < 0) j++; l.player.seek(l.mainRun.timeOf(30, j)); l.sync(0); l.player.seek(l.mainRun.timeOf(30, j + 1)); l.sync(0); l.advance(0.05, 2); const side = l.sides[0], b = side.layout.beads.find((x) => x.flight < 1 && !x.leaving); if (!b) return null; const p = new v.stage.camera.position.constructor(...b.from).add(side.group.position); const q = v.stage.project(p, p.clone()); return { x: +q.x.toFixed(0), y: +q.y.toFixed(0), z: +q.z.toFixed(3), width: v.stage.width, height: v.stage.height }; })()`);
      check("on a phone a molecule seeping in starts inside the frame", inside && inside.x >= 0 && inside.x <= inside.width && inside.y >= 0 && inside.y <= inside.height && inside.z < 1, JSON.stringify(inside));
      await evaluate(`${L}.hold(false)`);
      await level("lineage");
      await sleep(800);
      const names = await evaluate(`[...${V}.shadowRoot.querySelectorAll(".labels .label")].filter((el) => !el.classList.contains("is-off")).map((el) => el.textContent)`);
      check("at the Lineages level on a phone, the mark and the names of the tape, the fence and the threshold stand", names.includes(EXAMPLE) && names.some((t) => /^The tape/.test(t)) && names.some((t) => /^Similarity/.test(t)) && names.some((t) => /threshold of inheritance/.test(t)), JSON.stringify(names));
      await shot(`${NAME}-lineage-names`);

      // ---------------------------------------------------------- the narrowest phone, 360 px: the band under the bar, and the mark at each level
      await page("Emulation.setDeviceMetricsOverride", { width: 360, height: 780, deviceScaleFactor: 1, mobile: true });
      check("at 360 px entry=gard opens the view", await open("entry=gard"));
      const narrow = await band();
      check(`at 360 px the bar keeps to one row with "Origin", the card folds to its line, whole, and the rail's button stands apart from it${narrow.railUnder ? " (under it)" : ""}`, narrow.first === "Origin" && bandHolds(narrow), JSON.stringify(narrow));
      for (const id of ["assembly", "lineage", "molecules"]) {
        const pressed = await level(id);
        await sleep(600);
        const m = await mark();
        check(`at 360 px the example's mark stands on the picture, uncovered, at ${id}`, pressed && markShows(m), JSON.stringify([pressed, m]));
      }
      await shot(`${NAME}-360-molecules`);

      // ---------------------------------------------------------- less motion asked for: the view stands still, and draws no frame of itself
      // The mark still finds its place clear of the card and of the rail as they are opened (the viewer asks for a frame).
      await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: process.env.THEME === "dark" ? "dark" : "light" }, { name: "prefers-reduced-motion", value: "reduce" }] });
      check("with less motion asked for, entry=gard opens the view, standing still", (await open("entry=gard")) && !(await state()).playing);
      for (const [what, toggle] of [["the card", ".view-toggle"], ["the rail", ".rail-toggle"]]) {
        const at = await placeOf(`root.querySelector(${JSON.stringify(toggle)})`);
        if (at) await click(at.x, at.y, 900);
        const m = await mark();
        check(`standing still, the example's mark finds its place clear of ${what} opened`, Boolean(at) && markShows(m), JSON.stringify([Boolean(at), m]));
      }
      await shot(`${NAME}-still-rail-open`);
    }
  } else if (CASE === "address") {
    check("entry=gard&scale=lineage opens the view at the Lineages level", (await open("entry=gard&scale=lineage")) && (await state()).level === "lineage", JSON.stringify(await state()));
    check("and its mark stands there", markShows(await mark()), JSON.stringify(await mark()));
    // A level named in the address is shown without its panel: the picture comes first (a panel would cover half a phone).
    const named = await state();
    check("a level named in the address opens no panel", named.selected === null && named.panel === "", JSON.stringify([named.selected, named.panel.slice(0, 80)]));
    check("entry=gard&scale=molecules at the Molecules level", (await open("entry=gard&scale=molecules")) && (await state()).level === "molecules");
    check("entry=gard&still=1 holds it still: it does not play by itself", (await open("entry=gard&still=1")) && (await sleep(5000), !(await state()).playing), JSON.stringify(await state()));
    check("entry=gard&select=assembly:fission:lineage-a:37 opens on that fission, held, with its panel", (await open("entry=gard&select=assembly:fission:lineage-a:37")) && (await until(`${V}.state.selected === "assembly:fission:lineage-a:37"`, 40)) && (await sleep(5000), true) && (await state()).time === 37 && !(await state()).playing && /Fission 37/.test((await state()).panel), JSON.stringify(await state()));
    await shot(`${NAME}-select`);
    check("entry=gard&still=1&play=1 plays when the address asks", (await open("entry=gard&still=1&play=1")) && (await until(`${L}.player.playing`, 40)));
    // A visitor who asks for less motion: the assembly stands gathered, the page does not play it, and the mark stands at every level.
    await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });
    await open("entry=gard");
    await sleep(5000);
    let s = await state();
    check("with less motion asked for, the founder stands gathered and the page does not play by itself", !s.gathering && !s.playing && s.time === 0, JSON.stringify([s.gathering, s.playing, s.time]));
    const marks = [];
    for (const id of ["molecules", "lineage", "population", "assembly"]) {
      await evaluate(`${L}.setLevel(${JSON.stringify(id)})`);
      // Looked for once the level has had its time, and again for a few seconds: on a busy machine its first frame can take longer.
      await sleep(1200);
      let shown = markShows(await mark());
      for (let tries = 0; tries < 12 && !shown; tries++) { await sleep(500); shown = markShows(await mark()); }
      marks.push([id, shown]);
    }
    check("and the mark stands at every level", marks.every(([, ok]) => ok), JSON.stringify(marks));
    const standing = await evaluate(`(() => { const l = ${L}; return { shape: l.shape, inWords: l.tags?.in ? !l.tags.in.hidden : null, outWords: l.tags?.out ? !l.tags.out.hidden : null, key: l.streamWords() }; })()`);
    check("and nothing comes or goes on a path: the paths' words stand down and the key says in place", standing.inWords !== true && standing.outWords !== true && /in place/.test(standing.key), JSON.stringify(standing));
    await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "no-preference" }] });
    check("lens=laws&entry=gard opens the library, with the view's name on the first tab", (await open("lens=laws&entry=gard", false)) && (await state()).lens === "laws" && /Origin of life/.test((await state()).tab?.words || ""), JSON.stringify(await state()));
    const first = await placeOf(`root.querySelector('.switch [data-lens="cell"]')`);
    if (first) await click(first.x, first.y, 400);
    check("and pressing the first tab shows the view", await until(`${L}?.id === "origin"`, 80));
    const before = await evaluate(`${V}.stage.renderer.getContext().isContextLost()`);
    await evaluate(`(async () => { const ext = ${V}.stage.renderer.getContext().getExtension("WEBGL_lose_context"); ext.loseContext(); await new Promise((r) => setTimeout(r, 600)); ext.restoreContext(); await new Promise((r) => setTimeout(r, 1500)); ${V}.stage.invalidate(); })()`);
    await sleep(1200);
    check("a lost WebGL context comes back, the view drawing again", !before && !(await evaluate(`${V}.stage.renderer.getContext().isContextLost()`)) && (await evaluate(`${V}.stage.renderer.info.render.calls`)) > 3);
  } else if (CASE === "engine") {
    // ---------------------------------------------------------- the engine's own runs: the pair, one clock, the run's own lines
    const ids = engineFiles.map((file) => file.runs[0].id);
    const lead = engineFiles.find((file) => file.runs[0].law.form === "pair-consistent") || engineFiles[0];
    const MARK = `${lead.development.says} · ${lead.runs[0].revision.slice(0, 8)} · ${lead.runs[0].provenance.model}`;
    // A first page, left six seconds, so that no picture is of a fresh browser's first page (its first context is lost and restored on the card).
    await open("entry=gard");
    await sleep(6000);
    check("entry=gard opens the view on the engine's runs", (await open("entry=gard")) && JSON.stringify((await evaluate(`${L}.runs.map((run) => run.id)`)).sort()) === JSON.stringify([...ids].sort()));
    check("the founder gathers, then the page plays by itself", await until(`${L}.player.playing && ${L}.player.time > 0.05`, 120), JSON.stringify(await state()));
    const forms = await evaluate(`${L}.sides.map((side) => side.run.form)`);
    check(PHONE ? "on a phone, one run at a time: the engine's passive law" : "wide, the two side by side: the engine's passive law first, the comparison model beside it", JSON.stringify(forms) === (PHONE ? '["pair-consistent"]' : '["pair-consistent","single-event"]'), JSON.stringify(forms));
    const said = await evaluate(`[...${V}.shadowRoot.querySelectorAll(".labels .label")].filter((el) => !el.classList.contains("is-off") && !el.hidden).map((el) => el.textContent)`);
    const named = await evaluate(`${L}.shownRuns.map((run) => (${PHONE} ? "" : run.label + ": ") + (run.form === "pair-consistent" ? "the pair-consistent form, the engine's passive law" : "the preprint's single-event form, the comparison model (D192)") + " (" + run.law.engine_name + ")")`);
    check(PHONE ? "the run shown is named on the picture by its form and the engine's name for its law" : "each run shown is named on the picture by its run, its form and the engine's name for its law", named.every((words) => said.includes(words)), JSON.stringify({ named, said }));
    check("the mark on the picture is the run's standing, its revision and the engine's model, uncovered", markShows(await mark(MARK)), JSON.stringify([MARK, await mark(MARK)]));
    let s = await state();
    const stamp = await evaluate(`${V}.shadowRoot.querySelector(".stamp")?.textContent || ""`);
    check("and it stands in the legend and in the bar", s.legend.includes(MARK) && stamp.startsWith(lead.development.says), JSON.stringify([s.legend.slice(0, 120), stamp.slice(0, 120)]));
    const words = await evaluate(`(() => { const root = ${V}.shadowRoot; return [document.body.innerText, root.textContent, ...[...root.querySelectorAll(".labels .label")].map((el) => el.textContent)].join("\\n"); })()`);
    check("no word of an example anywhere on the page", !/invented numbers|Example: /.test(words), (words.match(/.{0,60}(invented numbers|Example: ).{0,60}/) || [""])[0]);
    // Playing, under one clock; something comes or goes on each side shown.
    const playing = await evaluate(`(async () => { const l = ${L}; let seen = 0; for (let i = 0; i < 20; i++) { await new Promise((r) => setTimeout(r, 100)); if (l.sides.every((side) => side.layout.inMotion().flying > 0 || side.layout.gathering)) seen++; } return { seen, k: l.sides.map((side) => side.phase?.k ?? null), key: l.streamWords() }; })()`);
    check("playing under one clock, the run's joins and leaves seen coming and going on each side", playing.seen >= 12 && new Set(playing.k).size === 1, JSON.stringify(playing));
    await shot(`${NAME}-playing`);
    // Each run's panel: every line it states of its law's check and its ledger, as it states it.
    for (const file of engineFiles) {
      const run = file.runs[0];
      await open(`entry=gard&select=assembly:run:${run.id}`);
      await until(`${V}.state.selected === "assembly:run:${run.id}"`, 40);
      await sleep(1500);
      const facts = await evaluate(`(() => { const d = ${L}.describe("assembly:run:${run.id}"); return d ? d.facts.map(([label, value]) => label + " = " + value) : []; })()`);
      const panel = (await state()).panel;
      const lines = run.states.lines.map((line) => `${line.path} = ${line.text}${line.unit ? ` ${line.unit}` : ""}`);
      let raw = null;
      if (engineRoot && existsSync(path.join(engineRoot, run.provenance.folder, "run.json"))) raw = await readFile(path.join(engineRoot, run.provenance.folder, "run.json"), "utf8");
      const own = raw ? run.states.lines.filter((line) => !line.text.startsWith("[")).every((line) => raw.includes(`"${line.path.split(".").at(-1)}": ${/^(true|false|null|[-\d.e+]+)$/.test(line.text) ? line.text : JSON.stringify(line.text)}`)) : true;
      check(`${run.label}'s panel gives every line the run states of its law's check and its ledger, as run.json writes it${raw ? "" : " (its run.json not at hand: held to its file)"}`, lines.every((line) => facts.includes(line)) && lines.every((line) => panel.includes(line.split(" = ")[1])) && own, JSON.stringify(lines.filter((line) => !facts.includes(line)).slice(0, 3)));
      await shot(`${NAME}-panel-${run.law.form}`);
      await open(`entry=gard&select=assembly:fission:${run.id}:37`);
      await until(`${V}.state.selected === "assembly:fission:${run.id}:37"`, 40);
      await sleep(4500);
      const fission = await state();
      check(`a fission of ${run.label} opens held, with its panel and the run's carrier keys`, fission.time === 37 && /Fission 37/.test(fission.panel) && /Carrier keys/.test(fission.panel), JSON.stringify([fission.time, fission.panel.slice(0, 120)]));
      await shot(`${NAME}-fission-${run.law.form}`);
    }
    // The switch: one run alone (on a phone the other), and back.
    await open("entry=gard");
    await until(`${L}.player.playing`, 120);
    if (PHONE) {
      const toggle = await placeOf(`root.querySelector(".view-toggle")`);
      if (toggle) await click(toggle.x, toggle.y, 900);
      const offered = await evaluate(`[...(${V}.shadowRoot.querySelector('[data-choice="pair"]')?.options || [])].map((o) => o.value)`);
      check("the opened card offers the switch between the two runs, and no side by side", JSON.stringify([...offered].sort()) === JSON.stringify([...ids].sort()), JSON.stringify(offered));
      check("the mark stands clear of the opened card", markShows(await mark(MARK)), JSON.stringify(await mark(MARK)));
      await shot(`${NAME}-card-open`);
    }
    const other = engineFiles.find((file) => file !== lead).runs[0].id;
    await evaluate(`(() => { const select = ${V}.shadowRoot.querySelector('[data-choice="pair"]'); select.value = ${JSON.stringify(other)}; select.dispatchEvent(new Event("change", { bubbles: true })); })()`);
    await sleep(2500);
    if (PHONE) {
      // The card folds again, so that the picture is seen.
      const toggle = await placeOf(`root.querySelector(".view-toggle")`);
      if (toggle) await click(toggle.x, toggle.y, 1200);
    }
    const alone = await evaluate(`${L}.sides.map((side) => side.run.id)`);
    const aloneSaid = await evaluate(`[...${V}.shadowRoot.querySelectorAll(".labels .label")].filter((el) => !el.classList.contains("is-off") && !el.hidden).map((el) => el.textContent)`);
    const aloneName = await evaluate(`(() => { const run = ${L}.mainRun; return (${PHONE} ? "" : run.label + ": ") + "the preprint's single-event form, the comparison model (D192) (" + run.law.engine_name + ")"; })()`);
    check("the switch shows the comparison model alone, named on the picture, the mark still standing", JSON.stringify(alone) === JSON.stringify([other]) && aloneSaid.includes(aloneName) && markShows(await mark(MARK)), JSON.stringify([alone, aloneName, aloneSaid, await mark(MARK)]));
    await evaluate(`${L}.player.pause(); ${L}.player.seek(36.97)`);
    await sleep(1800);
    await shot(`${NAME}-alone-${engineFiles.find((file) => file !== lead).runs[0].law.form}`);
    if (!PHONE) {
      // The engine's passive law alone, for its picture, then both again.
      await evaluate(`(() => { const select = ${V}.shadowRoot.querySelector('[data-choice="pair"]'); select.value = ${JSON.stringify(lead.runs[0].id)}; select.dispatchEvent(new Event("change", { bubbles: true })); })()`);
      await evaluate(`${L}.player.pause(); ${L}.player.seek(36.97)`);
      await sleep(2200);
      await shot(`${NAME}-alone-pair-consistent`);
      await evaluate(`(() => { const select = ${V}.shadowRoot.querySelector('[data-choice="pair"]'); select.value = "pair"; select.dispatchEvent(new Event("change", { bubbles: true })); })()`);
      await sleep(1500);
      check("and both again", (await evaluate(`${L}.sides.length`)) === 2);
      const marks = [];
      for (const id of ["molecules", "lineage", "population", "assembly"]) {
        await evaluate(`${L}.setLevel(${JSON.stringify(id)})`);
        // Looked for once the level has had its time, and again for a few seconds: on a busy machine its first frame can take longer.
        await sleep(1200);
        let shown = markShows(await mark(MARK));
        for (let tries = 0; tries < 12 && !shown; tries++) { await sleep(500); shown = markShows(await mark(MARK)); }
        marks.push([id, shown]);
        if (id === "lineage") await shot(`${NAME}-lineage`);
      }
      check("the mark stands at every level", marks.every(([, ok]) => ok), JSON.stringify(marks));
      const lineage = await evaluate(`(() => { const l = ${L}; l.setLevel("lineage"); return { items: l.chrome().legend.items.map((item) => item.label), sheets: l.sides.map((side) => Boolean(side.fence.sheet?.visible)) }; })()`);
      check("at the Lineages no threshold is drawn and no mark of inheritance keyed: the runs carry no analysis", lineage.sheets.every((on) => !on) && !lineage.items.some((label) => /threshold|bead: inherited/.test(label)), JSON.stringify(lineage));
      await evaluate(`${L}.setLevel("assembly")`);
    }
    // Less motion: the pair (or the one) stands; nothing comes or goes on a path.
    await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: process.env.THEME === "dark" ? "dark" : "light" }, { name: "prefers-reduced-motion", value: "reduce" }] });
    await open("entry=gard");
    await sleep(5000);
    s = await state();
    const still = await evaluate(`(() => { const l = ${L}; return { sides: l.sides.length, key: l.streamWords(), flying: l.sides.map((side) => side.layout.inMotion().flying) }; })()`);
    check("with less motion the runs stand, nothing in flight, the key saying in place", !s.playing && !s.gathering && still.sides === (PHONE ? 1 : 2) && still.flying.every((n) => n === 0) && /in place/.test(still.key), JSON.stringify([s.playing, still]));
    await shot(`${NAME}-less-motion`);
    await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: process.env.THEME === "dark" ? "dark" : "light" }, { name: "prefers-reduced-motion", value: "no-preference" }] });
  } else if (CASE === "pair") {
    check("on the check-only scene, entry=gard opens the view on the test's two runs", (await open("entry=gard")) && (await evaluate(`${L}.runs.length`)) === 2);
    const pair = await placeOf(`root.querySelector('[data-choice="pair"]')`);
    check("the card offers the two forms of the law under one clock", Boolean(pair) && /two forms of the law/.test(await evaluate(`${V}.shadowRoot.querySelector('[data-choice="pair"]').closest("label").textContent`)), JSON.stringify(pair));
    await evaluate(`${L}.player.pause(); ${L}.player.seek(5.5)`);
    await sleep(1500);
    const labels = await evaluate(`[...${V}.shadowRoot.querySelectorAll(".labels .label")].filter((el) => !el.classList.contains("is-off")).map((el) => el.textContent)`);
    check("it opens on the two lineages side by side, the pair-consistent form first, each named by its run and its form", JSON.stringify(await evaluate(`${L}.sides.map((side) => side.run.form)`)) === '["pair-consistent","single-event"]' && labels.some((t) => /Run S: the preprint's single-event form/.test(t)) && labels.some((t) => /Run P: the pair-consistent form/.test(t)), JSON.stringify(labels));
    const choose = (value) => evaluate(`(() => { const select = ${V}.shadowRoot.querySelector('[data-choice="pair"]'); select.value = ${JSON.stringify(value)}; select.dispatchEvent(new Event("change", { bubbles: true })); })()`);
    await choose(await evaluate(`${L}.pairRuns[1].id`));
    await sleep(1200);
    const alone = await evaluate(`${L}.sides.map((side) => side.run.form)`);
    await choose("pair");
    await sleep(1200);
    check("the card's switch shows one alone, and both again", JSON.stringify(alone) === '["single-event"]' && (await evaluate(`${L}.sides.length`)) === 2, JSON.stringify(alone));
    await evaluate(`${L}.player.pause(); ${L}.player.seek(6)`);
    await sleep(1200);
    check("under one clock: both at the same fission", JSON.stringify(await evaluate(`${L}.sides.map((side) => side.phase.k)`)) === "[6,6]");
    check("no example's mark: these are no example", (await mark()).count === 0);
    await shot(`${NAME}-pair`);
  } else if (CASE === "pictures") {
    // Pictures for a hand-over (no checks): a first page left six seconds, then each level wide in both themes, held by
    // the view's own clock and a fixed step; the card's selects shown open as lists; the model system's panel at its
    // notes; the Cell view after; and a phone at each level.
    const hold = (js) => evaluate(`(async () => { const v = ${V}, l = v.current; l.hold(true); v.stage.decoration.pause("picture"); ${js}; l.sync(0); v.stage.invalidate(); await new Promise((r) => setTimeout(r, 1800)); })()`);
    await open("entry=gard");
    await sleep(6000);
    for (const theme of ["light", "dark"]) {
      await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: theme }] });
      await open("entry=gard");
      await sleep(1600);
      await shot(`wide-${theme}-gathering`);
      await sleep(2200);
      await shot(`wide-${theme}-gathering-ends`);
      // Playing, between two fissions: one protocell and the stream (fission 30's growth, at ½ a second).
      await evaluate(`(async () => { const l = ${L}; l.player.pause(); l.player.seek(30.3); l.player.setSpeed(0.5); l.player.play(); })()`);
      await sleep(1500);
      await shot(`wide-${theme}-playing-the-stream`);
      if (theme === "light") {
        for (const packing of ["micelle", "cluster"]) {
          await evaluate(`(async () => { const l = ${L}; l.setShape(${JSON.stringify(packing)}); l.player.pause(); l.player.seek(30.3); l.player.play(); })()`);
          await sleep(1800);
          await shot(`wide-${theme}-${packing}-playing`);
        }
        await evaluate(`${L}.setShape("protocell")`);
      }
      await hold(`l.setLevel("assembly"); l.player.seek(30.55)`);
      await shot(`wide-${theme}-assembly-mid-run`);
      await hold(`l.player.seek(37 - 0.15 + 0.36 * 0.3)`);
      await shot(`wide-${theme}-assembly-at-a-fission`);
      for (const level of ["molecules", "population", "lineage"]) {
        await hold(`l.setLevel(${JSON.stringify(level)}); l.player.seek(${level === "lineage" ? 96.5 : 30.55})`);
        await sleep(600);
        await shot(`wide-${theme}-${level}`);
      }
      await hold(`l.setLevel("lineage"); l.player.seek(37 - 0.15 + 0.36 * 0.3)`);
      await shot(`wide-${theme}-lineage-at-a-fission`);
      await hold(`l.setLevel("assembly"); l.player.seek(30.55)`);
      await evaluate(`(() => { const selects = [...${V}.shadowRoot.querySelectorAll("#cells-view select")]; for (const select of selects) select.size = select.options.length; selects[0]?.closest("label, .card-marks")?.scrollIntoView({ block: "start" }); })()`);
      await shot(`wide-${theme}-card-selects-open`);
      await evaluate(`(() => { for (const select of ${V}.shadowRoot.querySelectorAll("#cells-view select")) select.size = 0; })()`);
      if (theme === "light") {
        await evaluate(`${V}.select("model:gard")`);
        await sleep(1200);
        await evaluate(`(() => { const panel = ${V}.shadowRoot.querySelector("cells-panel"); const notes = [...panel.querySelectorAll("h3, h4, summary, .panel-section-title")].find((el) => /Notes/.test(el.textContent)); notes?.scrollIntoView({ block: "start" }); })()`);
        await shot(`wide-${theme}-panel-notes`);
        await evaluate(`${V}.select("assembly:assembly")`);
        await sleep(1200);
        await shot(`wide-${theme}-panel-assembly`);
        await evaluate(`${V}.select(null)`);
        await evaluate(`${V}.setEntry("human", { user: true })`);
        await sleep(3000);
        await shot(`wide-${theme}-cell-view-after`);
      }
    }
    await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "light" }] });
    await page("Emulation.setDeviceMetricsOverride", { width: 400, height: 800, deviceScaleFactor: 1, mobile: true });
    for (const theme of ["light", "dark"]) {
      await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: theme }] });
      await open("entry=gard");
      await sleep(4500);
      await shot(`phone-${theme}-playing`);
      for (const [level, time] of [["assembly", 30.55], ["molecules", 30.55], ["population", 30.55], ["lineage", 96.5]]) {
        await hold(`l.setLevel(${JSON.stringify(level)}); l.player.seek(${time})`);
        await sleep(600);
        await shot(`phone-${theme}-${level}`);
      }
      await hold(`l.setLevel("assembly"); l.player.setSpeed(0.001); l.player.seek(50.5); l.sync(0); const ev = l.mainRun.growthEvents(30); let j = 8; while (ev[j] < 0) j++; l.player.seek(l.mainRun.timeOf(30, j)); l.sync(0); l.player.seek(l.mainRun.timeOf(30, j + 1)); l.sync(0); l.advance(0.35, 6)`);
      await shot(`phone-${theme}-a-join-seeping-in`);
      await hold(`l.setLevel("assembly"); l.player.seek(37 - 0.15 + 0.45 * 0.3)`);
      await shot(`phone-${theme}-at-a-fission`);
    }
    // With less motion asked for: the protocell stands, nothing gathers or streams.
    await page("Emulation.setDeviceMetricsOverride", { width: 1400, height: 900, deviceScaleFactor: 1, mobile: false });
    await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "light" }, { name: "prefers-reduced-motion", value: "reduce" }] });
    await open("entry=gard");
    await sleep(3000);
    await shot("wide-light-less-motion");
    await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "no-preference" }] });
  } else if (CASE === "eval") {
    // For looking into the page while the view is built: QUERY opens, EXPR is evaluated (with v the viewer, l its lens), and said.
    await open(process.env.QUERY || "entry=gard");
    await sleep(Number(process.env.WAIT || 1000));
    note(JSON.stringify(await evaluate(`(async () => { const v = ${V}, l = v.current; ${process.env.EXPR || "return null;"} })()`)));
    if (process.env.SHOT) await shot(process.env.SHOT);
  } else if (CASE === "frames") {
    // The stage's own frame, waited for on the card, and the gaps between frames, while the view plays: by turns, with
    // the map's chrome shown and hidden, in one page (a single pair taken under load misled once).
    await open("entry=gard");
    await sleep(5000);
    const CHROME_PARTS = ".bar, #cells-view, cells-legend, .rail, .rail-toggle, .view-toggle, cells-timeline, .scalebar, .look-box, .caveat, .labels";
    const hide = (on) => evaluate(`(() => { const root = ${V}.shadowRoot; let style = root.querySelector("style[data-check-frames]"); if (!style) { style = document.createElement("style"); style.dataset.checkFrames = "1"; root.append(style); } style.textContent = ${JSON.stringify(`${CHROME_PARTS} { visibility: hidden !important; }`)} ; if (!${on}) style.textContent = ""; ${V}.stage.invalidate(); })()`);
    const measure = (setup) => evaluate(`(async () => { const v = ${V}, l = v.current; ${setup}
      await new Promise((r) => setTimeout(r, 800));
      const gl = v.stage.renderer.getContext(), work = [], gaps = [], own = v.stage.frame; let last = 0, going = true;
      v.stage.frame = function (time) { const t0 = performance.now(); if (last) gaps.push(t0 - last); last = t0; own.call(this, time); gl.finish(); work.push(performance.now() - t0); };
      const ask = () => { if (!going) return; v.stage.invalidate(); requestAnimationFrame(ask); }; ask();
      await new Promise((r) => setTimeout(r, 2500)); going = false; v.stage.frame = own;
      const q = (list, f) => { const a = list.slice().sort((x, y) => x - y); return +a[Math.min(a.length - 1, Math.floor(a.length * f))].toFixed(2); };
      return { frames: work.length, frameMs: q(work, 0.5), slowTenthMs: q(work, 0.9), gapMs: q(gaps, 0.5), calls: v.stage.renderer.info.render.calls, triangles: v.stage.renderer.info.render.triangles }; })()`);
    const ways = process.env.WAYS === "pair"
      ? (PHONE
        ? [["the engine's passive law alone, ½ a second", `l.setLevel("assembly"); l.setPair(l.pairRuns[0].id); l.player.seek(30.2); l.player.setSpeed(0.5); l.player.play();`], ["the comparison model alone, ½ a second", `l.setLevel("assembly"); l.setPair(l.pairRuns[1].id); l.player.seek(30.2); l.player.setSpeed(0.5); l.player.play();`]]
        : [["the engine's pair side by side, ½ a second", `l.setLevel("assembly"); l.setPair("pair"); l.player.seek(30.2); l.player.setSpeed(0.5); l.player.play();`], ["the engine's passive law alone, ½ a second", `l.setLevel("assembly"); l.setPair(l.pairRuns[0].id); l.player.seek(30.2); l.player.setSpeed(0.5); l.player.play();`]])
      : process.env.WAYS === "packing"
      ? [["the protocell, ½ a second", `l.setLevel("assembly"); l.setShape("protocell"); l.player.seek(30.2); l.player.setSpeed(0.5); l.player.play();`], ["the micelle, ½ a second", `l.setLevel("assembly"); l.setShape("micelle"); l.player.seek(30.2); l.player.setSpeed(0.5); l.player.play();`]]
      : process.env.WAYS === "contact"
      ? [["Lineages with contact shade", `l.setLevel("lineage"); v.stage.dress({ rich: true, filmic: true, exposure: 1.05, contact: true, reach: 0.5, shade: 0.5 }); l.player.seek(30.2); l.player.setSpeed(0.5); l.player.play();`], ["Lineages without contact shade", `v.stage.dress({ rich: true, filmic: true, exposure: 1.05, contact: false, reach: 0.5, shade: 0.5 }); l.player.seek(30.2); l.player.setSpeed(0.5); l.player.play();`]]
      : [["playing ½ a second", `l.setLevel("assembly"); l.player.seek(30.2); l.player.setSpeed(0.5); l.player.play();`], ["molecule by molecule", `l.player.seek(30.2); l.player.setSpeed(0.001); l.player.play();`], ["Lineages, playing ½ a second", `l.setLevel("lineage"); l.player.seek(30.2); l.player.setSpeed(0.5); l.player.play();`], ["Molecules, playing ½ a second", `l.setLevel("molecules"); l.player.seek(30.2); l.player.setSpeed(0.5); l.player.play();`]];
    if (process.env.WAYS === "pair" && process.env.CHROME_TURNS) {
      // The pair, by turns with the map's chrome (its cards and the words on the picture) shown and hidden: what the page's words cost against the drawing.
      await measure(ways[0][1]);
      for (const turn of [false, true, false, true, false, true]) {
        await hide(turn);
        note(`frames ${WIDTH}x${HEIGHT}, ${ways[0][0]}, the map's chrome ${turn ? "hidden" : "shown"}: ${JSON.stringify(await measure(ways[0][1]))}`);
      }
      await hide(false);
      note(`load average: ${(await import("node:os")).loadavg().map((x) => x.toFixed(1)).join(", ")}`);
    } else if (process.env.WAYS === "packing" || process.env.WAYS === "pair") {
      // The protocell against the micelle (or the engine's pair against one of it), by turns in one page, three turns each; with COLD unset, after one turn of each that is not counted.
      if (!process.env.COLD) for (const [, setup] of ways) await measure(setup);
      for (let turn = 0; turn < 3; turn++) for (const [what, setup] of ways) note(`frames ${WIDTH}x${HEIGHT}, ${what}: ${JSON.stringify(await measure(setup))}`);
      note(`load average: ${(await import("node:os")).loadavg().map((x) => x.toFixed(1)).join(", ")}`);
    } else if (process.env.WAYS === "molecules") {
      const base = `l.setLevel("molecules"); l.player.seek(30.2); l.player.setSpeed(0.5); l.player.play(); l.water.setTheme(l.palette.dark); l.plate.visible = true; l.table.group.visible = true; v.stage.dress(l.lookFor("molecules"));`;
      const turns = [["as drawn", base], ["no caustics", `${base} l.water.uniforms.causticStrength.value = 0;`], ["no contact shade", `${base} v.stage.dress(l.lookFor("lineage"));`], ["no plate", `${base} l.plate.visible = false;`], ["no table", `${base} l.table.group.visible = false;`]];
      for (let turn = 0; turn < 2; turn++) for (const [what, setup] of turns) note(`frames ${WIDTH}x${HEIGHT}, Molecules ${what}: ${JSON.stringify(await measure(setup))}`);
      await measure(base);
    } else if (process.env.WAYS === "contact") {
      for (let turn = 0; turn < 3; turn++) for (const [what, setup] of ways) note(`frames ${WIDTH}x${HEIGHT}, ${what}: ${JSON.stringify(await measure(setup))}`);
    } else for (const [what, setup] of ways) {
      for (const turn of [false, true, false, true]) {
        await hide(turn);
        note(`frames ${WIDTH}x${HEIGHT}, ${what}, the map's chrome ${turn ? "hidden" : "shown"}: ${JSON.stringify(await measure(setup))}`);
      }
      await hide(false);
    }
  }
  const errors = pageLog.filter((line) => /error|exception|rejection|blocked/i.test(line));
  check("the page logged no error", errors.length === 0, errors.slice(0, 3).join(" / "));
  const thrown = await evaluate(`(window.__pageErrors || []).slice(0, 3)`);
  check("the page threw no error", thrown.length === 0, thrown.join(" / "));
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
  console.error(`check_origin: ${failed.stack || failed}`);
  process.exit(2);
}
const passed = results.filter(Boolean).length;
console.log(`${passed} of ${results.length} checks passed`);
process.exit(passed === results.length ? 0 : 1);
