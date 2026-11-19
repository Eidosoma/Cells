#!/usr/bin/env node
// Checks a species' life stages in the Scope view (schema/SPECIES_STAGES.md) with real pointer and key input, on a
// check-only scene: the page's own, with a made-up species (tests/fixtures/stages/species/dewkin.json) read in by the
// species and entries readers, and a check-only catalogue of runs holding one made-up run that fills one of its spans.
// The scene and the runs are written under the pictures' folder and never published.
//
//   node tools/check_stages.mjs [PICTURES_DIR]
//   CASE=wide|720|phone|360   the window: 1440 by 900, 1280 by 720, 400 by 844, 360 by 780 (wide by default)
//   THEME=dark                the dark theme (light by default)
//   NAME=...                  the name the pictures are written under (stages-<case> by default)
//
// What it holds: the species opens on the stage its block names (its egg, a cell a millimetre across), not its file's
// own; the strip stands as the page's one timeline, a stop for each stage, the one named and not drawn hollow; play
// shows where the run fills a span and only there; a press on a drawn stage's stop makes the plain change (held, through
// an empty picture, held) with "Illustration: not a run" on the picture, and the address follows (`stage=`); a press on
// the named stage opens what is known of it; the keyboard goes stage by stage; play plays the run's span and stops; the
// Protein atlas says it is the organism's; an address's stage opens it, a named one its card, an unknown one the
// opening stage; a species without stages shows no strip. Every wait is on the page's own state.
//
// One browser, through the browser lock (tools/lib/browser_lock.mjs). The first page of the fresh browser is not pictured.

import { spawn, spawnSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { createServer } from "./serve.mjs";
import { acquireBrowser } from "./lib/browser_lock.mjs";
import { DEFAULT_SCENE, ROOT } from "./lib/build_page.mjs";
import { syntheticIndex, syntheticRun } from "../tests/helpers/synthetic_replay.mjs";

const CASES = { wide: [1440, 900], 720: [1280, 720], phone: [400, 844], 360: [360, 780] };
const CASE = process.env.CASE || "wide";
const [WIDTH, HEIGHT] = CASES[CASE] || CASES.wide;
const THEME = process.env.THEME || "light";
const NAME = process.env.NAME || `stages-${CASE}`;
const PICTURES = path.resolve(process.argv[2] || path.join(ROOT, "out", "check-stages"));
const HERE = path.join(PICTURES, `${NAME}-scene`);
const RUN_ID = "e07-v1--stages-check--seed1"; // the id the made-up species' span names

const results = [];
const check = (name, ok, detail = "") => {
  results.push(Boolean(ok));
  console.log(`${ok ? "pass" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`);
};

// ------------------------------------------------------------ the check-only scene and runs

await mkdir(path.join(HERE, "runs"), { recursive: true });
const overlay = JSON.parse(await readFile(path.join(ROOT, "data", "architecture", "overlay.json"), "utf8"));
const capabilities = Object.fromEntries(overlay.capabilities.map((item) => [item.id, item.scale]));
const READER = `
import json, sys
sys.path.insert(0, sys.argv[1])
from lib import entries
request = json.load(sys.stdin)
found, shapes, models, warnings, remarks = entries.read_entries(request["species"], None, None, request["capabilities"])
print(json.dumps({"species": found, "shapes": shapes, "warnings": warnings}))
`;
const read = spawnSync("python3", ["-I", "-c", READER, path.join(ROOT, "tools")], { input: JSON.stringify({ species: path.join(ROOT, "tests", "fixtures", "stages", "species"), capabilities }), encoding: "utf8" });
if (read.status !== 0) throw new Error(`the species reader failed: ${read.stderr}`);
const fixture = JSON.parse(read.stdout);
const scene = JSON.parse(await readFile(DEFAULT_SCENE, "utf8"));
// The same animal under another id, opening on its file's own stage (its block names no other).
const own = JSON.parse(JSON.stringify(fixture.species[0]));
Object.assign(own, { id: "dewkin-own", label: "Dewkin, opening on its adult", order: 96 });
delete own.stages.opens_on;
scene.species = [...scene.species.filter((item) => !item.id.startsWith("dewkin")), ...fixture.species, own];
scene.shapes = { ...(scene.shapes || {}), ...fixture.shapes };
const sceneFile = path.join(HERE, "scene.json");
await writeFile(sceneFile, JSON.stringify(scene));
// One made-up run, a small sheet over three minutes, for the span from the egg to its first division.
const made = syntheticRun({ rings: 1, disc: 1, end: 180, interval: 30, arm: "stages-check", seed: 1 });
made.entry.file = `runs/${RUN_ID}.json`;
await writeFile(path.join(HERE, "runs", `${RUN_ID}.json`), JSON.stringify(made.file));
await writeFile(path.join(HERE, "runs", "index.json"), JSON.stringify(syntheticIndex({ label: "A made-up run for the life stages' check", plain: "Made up for tools/check_stages.mjs." }, [made.entry])));
check("the made-up species is read with its stages, and no warning but the fixture's own default", fixture.species.length === 1 && Boolean(fixture.species[0].stages) && fixture.warnings.every((line) => /default/.test(line)), JSON.stringify(fixture.warnings));
check("the made-up run carries the id its span names", made.entry.id === RUN_ID, made.entry.id);

// ------------------------------------------------------------ the browser

const release = await acquireBrowser();
const server = createServer({ offline: true, scene: sceneFile, runs: path.join(HERE, "runs"), log: () => {} });
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}/`;
const chrome = spawn(process.env.CHROME || "google-chrome", ["--headless=new", `--user-data-dir=${release.profile}`, "--disable-breakpad", "--no-first-run", "--no-sandbox", "--mute-audio", "--hide-scrollbars", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--remote-debugging-port=0", `--window-size=${WIDTH},${HEIGHT}`, "about:blank"], { stdio: ["ignore", "ignore", "pipe"] });
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
const evaluate = async (expression) => {
  const reply = await page("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (reply.exceptionDetails) throw new Error(reply.exceptionDetails.exception?.description || reply.exceptionDetails.text);
  return reply.result.value;
};
const V = "document.querySelector('cells-viewer')";
const L = `${V}.lenses.get("cell")`;
/** Wait, on the page's own state, until `expression` holds (at most `ms`): its value, or null. */
const waitFor = (expression, ms = 15000) => evaluate(`(async () => { const until = performance.now() + ${ms}; while (performance.now() < until) { try { const value = (${expression}); if (value) return value; } catch {} await new Promise((r) => setTimeout(r, 40)); } return null; })()`);
const drawn = () => evaluate(`new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve(true))))`);
const open = async (query, scope = true) => {
  await page("Page.navigate", { url: `${base}?${query}&theme=${THEME}` });
  const ready = await waitFor(`${V} && ${V}.current && ${V}.stage && !${V}.stage.rig.flight && ${scope ? L : "true"} && document.fonts.status === "loaded"`, 30000);
  await drawn();
  return ready;
};
const shot = async (name) => {
  await drawn();
  await writeFile(path.join(PICTURES, `${NAME}-${name}.png`), Buffer.from((await page("Page.captureScreenshot", { format: "png" })).data, "base64"));
};
const mouse = (type, x, y, extra = {}) => page("Input.dispatchMouseEvent", { type, x, y, button: "left", buttons: 1, clickCount: 1, ...extra });
const click = async (x, y) => {
  await mouse("mouseMoved", x, y, { button: "none", buttons: 0 });
  await mouse("mousePressed", x, y);
  await mouse("mouseReleased", x, y, { buttons: 0 });
};
const key = async (name, code) => {
  await page("Input.dispatchKeyEvent", { type: "rawKeyDown", key: name, code: name, windowsVirtualKeyCode: code });
  await page("Input.dispatchKeyEvent", { type: "keyUp", key: name, code: name, windowsVirtualKeyCode: code });
};
/** What the strip and the Scope view show. */
const strip = () =>
  evaluate(`(() => {
    const v = ${V}, root = v.shadowRoot, tl = root.querySelector("cells-timeline"), lens = ${L};
    const box = (el) => { const r = el.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)]; };
    const shown = (el) => Boolean(el && !el.hidden && el.offsetParent !== null);
    return {
      shown: shown(tl), stages: tl.classList.contains("is-stages"), box: shown(tl) ? box(tl) : null,
      stops: [...tl.querySelectorAll(".tl-stop")].map((b) => ({ stage: b.dataset.stage, named: b.classList.contains("is-named"), current: b.hasAttribute("aria-current"), label: b.getAttribute("aria-label"), box: box(b), name: b.querySelector(".tl-stop-name")?.textContent || null })),
      play: shown(tl.querySelector(".tl-play")), slider: tl.querySelector(".tl-range").getAttribute("aria-label"), value: tl.querySelector(".tl-range").getAttribute("aria-valuetext"),
      read: tl.querySelector(".tl-read")?.textContent, stage: lens.stageId, weight: lens.pictureWeight, changing: Boolean(lens.change),
      levels: lens.currentStops.map((s) => s.id).join(" "), caveat: root.querySelector(".caveat")?.hidden ? null : root.querySelector(".caveat")?.textContent,
      caveatBox: shown(root.querySelector(".caveat")) ? box(root.querySelector(".caveat")) : null,
      address: location.search, u: lens.u, playing: lens.stagePlayer.playing, time: lens.stagePlayer.time,
      panel: root.querySelector("cells-panel").hidden ? null : root.querySelector("cells-panel").textContent.slice(0, 400),
    };
  })()`);
const stopAt = async (stage) => (await strip()).stops.find((stop) => stop.stage === stage);
const pressStop = async (stage) => {
  const stop = await stopAt(stage);
  if (!stop) throw new Error(`no stop for ${stage}`);
  await click((stop.box[0] + stop.box[2]) / 2, (stop.box[1] + stop.box[3]) / 2);
};
const overlaps = (a, b) => a && b && a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];

try {
  await page("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: HEIGHT, deviceScaleFactor: 1, mobile: WIDTH < 760 });
  // The fresh browser's first page is not pictured: a stated window of up to eight seconds for a first WebGL context to be lost and come back.
  await open("lens=engine", false);
  await evaluate(`new Promise((resolve) => { const c = ${V}.shadowRoot.querySelector("canvas"); c.addEventListener("webglcontextrestored", () => resolve("restored")); setTimeout(() => resolve("none in the window"), 8000); })`);

  // It opens on the stage its block names: the egg, one cell a millimetre across, ending at its cell.
  check("the made-up species opens", await open("entry=dewkin&lens=cell"));
  let s = await strip();
  check("it opens on the stage its block names (the egg), not its file's own (the adult)", s.stage === "egg" && s.levels === "molecule cell", JSON.stringify([s.stage, s.levels]));
  check("the address names no stage for the stage it opens on", !/stage=/.test(s.address), s.address);
  check("the strip stands as the page's one timeline, a stop for each of its four stages", s.shown && s.stages && s.stops.map((stop) => stop.stage).join(" ") === "egg two-cell larva adult", JSON.stringify(s.stops.map((stop) => stop.stage)));
  check("the stage named and not drawn is hollow and says so; the others are not", s.stops.filter((stop) => stop.named).map((stop) => stop.stage).join(" ") === "two-cell" && /named, not drawn/.test(s.stops.find((stop) => stop.named).label), JSON.stringify(s.stops.map((stop) => [stop.stage, stop.named, stop.label])));
  check("the stop of the stage shown is marked", s.stops.find((stop) => stop.current)?.stage === "egg");
  check("the slider is named for the stages, and its read-out names the stage shown", s.slider === "Life stage" && /DS 1 · Egg/.test(s.read), JSON.stringify([s.slider, s.read]));
  check(WIDTH >= 760 ? "on a wide window each stop carries its short name" : "on a phone the stops carry no names", WIDTH >= 760 ? s.stops.every((stop) => stop.name) : s.stops.every((stop) => !stop.name), JSON.stringify(s.stops.map((stop) => stop.name)));
  if (WIDTH < 760) check("on a phone each stop is a target as large as a touch needs (44 px)", s.stops.every((stop) => stop.box[2] - stop.box[0] >= 44 && stop.box[3] - stop.box[1] >= 44), JSON.stringify(s.stops.map((stop) => stop.box)));
  check("the strip stands inside the window, and the picture's words do not lie over it", s.box && s.box[0] >= 0 && s.box[2] <= WIDTH && s.box[3] <= HEIGHT && !overlaps(s.box, s.caveatBox), JSON.stringify([s.box, s.caveatBox]));
  check("play shows at the egg, where a run fills the span that follows it", (await waitFor(`!${V}.shadowRoot.querySelector("cells-timeline .tl-play").hidden`, 8000)) && (await strip()).play);
  await shot("egg");

  // A press on the adult's stop: the plain change, with its words on the picture, through an empty picture.
  await pressStop("adult");
  const during = await waitFor(`${L}.change && ${L}.change.t > 0.2 && ${L}.change.t < 0.8 ? { words: ${V}.shadowRoot.querySelector(".caveat").textContent, weight: ${L}.pictureWeight } : null`, 6000);
  check("the press makes the plain change, and its words stand on the picture", during && /^Illustration: not a run\. A plain change from Egg to Adult; Two cells is named, not drawn/.test(during.words), JSON.stringify(during));
  const empty = await waitFor(`${L}.change && ${L}.pictureWeight < 0.02 ? ${L}.pictureWeight : null`, 6000);
  check("half-way, one picture has given way and the other has not come: nothing is drawn", empty !== null, String(empty));
  await shot("change-middle");
  const arrived = await waitFor(`!${L}.change && ${L}.stageId === "adult" && !${V}.stage.rig.flight`, 10000);
  s = await strip();
  check("it ends at the adult, with every level of its file", arrived && s.levels === "molecule cell tissue organ organism" && s.weight === 1, JSON.stringify([s.stage, s.levels, s.weight]));
  check("the address names the stage chosen", /stage=adult/.test(s.address), s.address);
  check("play does not show where only the viewer's own change would play", !s.play);
  check("at rest at a drawn stage the picture's words are the view's own again", !/Illustration/.test(s.caveat || ""), s.caveat);
  await shot("adult");

  // The larva: it changes only the body's outline; the cell is the file's.
  await pressStop("larva");
  const larva = await waitFor(`!${L}.change && ${L}.stageId === "larva" && !${V}.stage.rig.flight`, 10000);
  check("a press on the larva's stop enters it", larva, larva ? "" : JSON.stringify({ ...(await strip()), change: await evaluate(`${L}.change ? { to: ${L}.change.to, t: ${L}.change.t } : null`), flight: await evaluate(`Boolean(${V}.stage.rig.flight)`), hit: await evaluate(`(() => { const b = [...${V}.shadowRoot.querySelectorAll(".tl-stop")].find((x) => x.dataset.stage === "larva").getBoundingClientRect(); const el = ${V}.shadowRoot.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2); return el ? el.className + " " + (el.dataset?.stage || "") : null; })()`) }).slice(0, 900));
  s = await strip();
  check("the larva has the adult's levels, its body outline its own", s.levels === "molecule cell tissue organ organism" && /stage=larva/.test(s.address), JSON.stringify([s.levels, s.address]));
  await shot("larva");

  // The named stage: its card, and it cannot be entered.
  await pressStop("two-cell");
  const card = await waitFor(`${V}.state.selected === "stage:dewkin.two-cell" && !${V}.shadowRoot.querySelector("cells-panel").hidden`, 6000);
  s = await strip();
  check("a press on the named stage opens what is known of it, and does not enter it", card && s.stage === "larva" && /Named, not drawn/.test(s.panel || ""), JSON.stringify([s.stage, (s.panel || "").slice(0, 120)]));
  await shot("named-card");
  await evaluate(`${V}.select(null)`);

  // The keyboard: stage by stage, named ones too, read out.
  await evaluate(`${V}.shadowRoot.querySelector("cells-timeline .tl-range").focus()`);
  await key("ArrowLeft", 37);
  const onNamed = await waitFor(`(() => { const t = ${V}.shadowRoot.querySelector("cells-timeline"); return ${L}.stagePlayer.time === 1 && /named, not drawn/.test(t.querySelector(".tl-range").getAttribute("aria-valuetext") || t.querySelector(".tl-read").textContent) ? t.querySelector(".tl-read").textContent : null; })()`, 6000);
  check("Left goes to the stage before, the named one, and the read-out says it is not drawn", Boolean(onNamed), String(onNamed));
  s = await strip();
  check("there nothing is drawn, and the picture says why", s.weight === 0 && /named, not drawn/.test(s.caveat || ""), JSON.stringify([s.weight, s.caveat]));
  const hidden = await waitFor(`${L}.zones.every((zone) => !zone.root.visible) && [...${V}.shadowRoot.querySelectorAll(".labels > *")].filter((el) => el.textContent.trim()).every((el) => el.hidden || el.style.display === "none" || getComputedStyle(el).opacity === "0" || getComputedStyle(el).visibility === "hidden") ? true : null`, 6000);
  check("and no part of the cell, nor any of its names, stands on the picture there", Boolean(hidden));
  await shot("named-rest");
  await key("ArrowLeft", 37);
  check("Left again enters the egg", await waitFor(`!${L}.change && ${L}.stageId === "egg" && ${L}.pictureWeight === 1`, 10000));
  await key("PageDown", 34);
  check("Page Down goes to the next stage that can be entered, passing the named one", await waitFor(`!${L}.change && ${L}.stageId === "larva"`, 10000));
  await key("Home", 36);
  check("Home goes to the first stage", await waitFor(`!${L}.change && ${L}.stageId === "egg"`, 10000));

  // Play: the run's span, and only it.
  s = await strip();
  check("at the egg play shows again", s.play);
  const play = await evaluate(`(() => { const b = ${V}.shadowRoot.querySelector("cells-timeline .tl-play").getBoundingClientRect(); return { x: b.left + b.width / 2, y: b.top + b.height / 2 }; })()`);
  await click(play.x, play.y);
  // The picture's words follow the play's start by a frame (the page draws its words again on the next one): they are waited for
  // on the page's own state, and what stands there is read if they never come (found under load on 19 November 2026).
  const playing = (await waitFor(`${L}.stagePlayer.playing && /^Prescribed/.test(${V}.shadowRoot.querySelector(".caveat").textContent) ? ${V}.shadowRoot.querySelector(".caveat").textContent : null`, 6000)) ?? (await evaluate(`${V}.shadowRoot.querySelector(".caveat").textContent`));
  check("play plays the run's span, its words on the picture: prescribed by the run's caller, not grown, and not drawn here yet", playing && /^Prescribed by the run's caller: not grown in the run: .*Its frames are not drawn in this view yet\.$/.test(playing), String(playing));
  await shot("run-playing");
  const ended = await waitFor(`!${L}.stagePlayer.playing && ${L}.stagePlayer.time === 1`, 30000);
  s = await strip();
  check("it stops where the run's span ends, at the named two-cell stage, and does not play on into the viewer's own change", ended && !s.play && s.weight === 0, JSON.stringify([s.time, s.playing, s.play, s.weight]));

  // The Protein atlas is the organism's.
  check("the species opens again at its egg", await open("entry=dewkin&lens=proteins&stage=egg", false));
  const atlas = await waitFor(`(() => { const c = ${V}.shadowRoot.querySelector(".caveat"); return c && !c.hidden && /as an organism/.test(c.textContent) ? c.textContent : null; })()`, 8000);
  check("at a stage that is not its file's own the Protein atlas says that it shows the organism's proteins", Boolean(atlas) && /at the stage Egg \(DS 1\) is not in its data/.test(atlas), String(atlas));

  check("the Machines tab opens at the egg too", await open("entry=dewkin&lens=machines&stage=egg", false));
  const bench = await waitFor(`(() => { const c = ${V}.shadowRoot.querySelector(".caveat"); return c && !c.hidden && /as an organism/.test(c.textContent) ? c.textContent : null; })()`, 8000);
  check("and says that it shows the organism's machines, not a stage's", Boolean(bench) && /at the stage Egg \(DS 1\) is not in its data/.test(bench), String(bench));

  // The address.
  check("stage=adult opens the adult", (await open("entry=dewkin&lens=cell&stage=adult")) && (await waitFor(`${L}.stageId === "adult"`, 6000)));
  check("stage=two-cell opens its card over the stage it opens on", (await open("entry=dewkin&lens=cell&stage=two-cell")) && (await waitFor(`${L}.stageId === "egg" && ${V}.state.selected === "stage:dewkin.two-cell"`, 6000)));
  check("a stage the species does not have opens the stage it opens on", (await open("entry=dewkin&lens=cell&stage=pupa")) && (await waitFor(`${L}.stageId === "egg"`, 6000)));
  await evaluate(`${V}.setEntry("mouse", { user: true })`);
  s = await strip();
  check("another species leaves the stage behind: no strip, no stage in the address", !s.shown && !/stage=/.test(s.address), JSON.stringify([s.shown, s.address]));
  await evaluate(`${V}.setEntry("dewkin", { user: true })`);
  check("back on the made-up species, it opens on its egg again", await waitFor(`${L}.stageId === "egg" && !/stage=/.test(location.search)`, 6000));
  // A species whose block names no stage to open on opens on its file's own, its strip at that stage.
  check("a species that names no stage to open on opens on its file's own", (await open("entry=dewkin-own&lens=cell")) && (await waitFor(`${L}.stageId === "adult" && ${L}.stagePlayer.time === 3 && ${L}.pictureWeight === 1 && [...${V}.shadowRoot.querySelectorAll("cells-timeline .tl-stop")].find((b) => b.hasAttribute("aria-current"))?.dataset.stage === "adult"`, 8000)));
  await evaluate(`${V}.setEntry("dewkin", { user: true })`);
  // Every number on the picture of the egg comes from its stage: the cell a millimetre across.
  s = await strip();
  check("the egg is drawn at its own size (a millimetre: about 54 units of the reference cell)", Math.abs(s.u - 1000 / 18.3597385602301) < 1e-6, String(s.u));
} catch (error) {
  check("the check ran to its end", false, error.message);
} finally {
  socket.close();
  const closed = new Promise((resolve) => chrome.once("close", resolve));
  chrome.kill();
  await Promise.race([closed, new Promise((resolve) => setTimeout(resolve, 4000))]);
  if (chrome.exitCode === null && chrome.signalCode === null) chrome.kill("SIGKILL");
  server.close();
  release();
}
const failed = results.filter((ok) => !ok).length;
console.log(`${results.length - failed} of ${results.length} checks passed`);
process.exit(failed ? 1 : 0);
