#!/usr/bin/env node
// Checks the species switch with real pointer and key input, through the DevTools protocol,
// the way tools/check_input.mjs drives the viewer: the levels each species has, what its
// cell holds, what the page says Cells models of it, and that the switch is one control for
// every view that depends on a species.
//
//   node tools/check_species.mjs [SCENE_FILE]
//   WIDTH=1400 node tools/check_species.mjs     another window width (1280 by default)
//   NOFONTS=1 node tools/check_species.mjs      with the web fonts blocked, as on a slow network
//   EXPECT=card node tools/check_species.mjs    where the switch is expected to stand (bar by default)
//
// One browser at a time: it takes the lock in tools/lib/browser_lock.mjs, whose profile
// folder is on disk and removed afterwards.

import { spawn } from "node:child_process";
import { createServer } from "./serve.mjs";
import { acquireBrowser } from "./lib/browser_lock.mjs";
import { DEFAULT_SCENE } from "./lib/build_page.mjs";

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const results = [];
const check = (name, ok, detail = "") => {
  results.push(Boolean(ok));
  console.log(`${ok ? "pass" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`);
};
const pageLog = [];
const release = await acquireBrowser();
const server = createServer({ offline: true, scene: process.argv[2] || DEFAULT_SCENE, log: (line) => pageLog.push(line) });
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}/`;
const chrome = spawn(process.env.CHROME || "google-chrome", ["--headless=new", `--user-data-dir=${release.profile}`, "--disable-breakpad", "--no-first-run", "--no-sandbox", "--mute-audio", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--remote-debugging-port=0", `--window-size=${process.env.WIDTH || 1280},800`, "about:blank"], { stdio: ["ignore", "ignore", "pipe"] });
const endpoint = await new Promise((resolve, reject) => {
  let text = "";
  chrome.stderr.on("data", (chunk) => {
    text += chunk;
    const match = text.match(/DevTools listening on (ws:\/\/\S+)/);
    if (match) resolve(match[1]);
  });
  setTimeout(() => reject(new Error("Chrome did not report a DevTools address")), 20000);
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
if (process.env.NOFONTS) {
  await page("Network.enable");
  await page("Network.setBlockedURLs", { urls: ["*fonts.googleapis.com*", "*fonts.gstatic.com*"] });
}
const size = (width, height) => page("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: false });
const WIDTH = Number(process.env.WIDTH || 1280);
await size(WIDTH, 800);
const evaluate = async (expression) => {
  const reply = await page("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (reply.exceptionDetails) throw new Error(reply.exceptionDetails.exception?.description || reply.exceptionDetails.text);
  return reply.result.value;
};
const V = "document.querySelector('cells-viewer')";
const open = async (query) => {
  await page("Page.navigate", { url: `${base}?${query}&still=1` });
  for (let tries = 0; tries < 80; tries++) {
    await sleep(250);
    if (await evaluate(`Boolean(${V} && ${V}.current && ${V}.stage)`).catch(() => false)) break;
  }
  await sleep(900);
};
const mouse = (type, x, y, extra = {}) => page("Input.dispatchMouseEvent", { type, x, y, button: "left", buttons: 1, clickCount: 1, ...extra });
const click = async (x, y) => {
  await mouse("mouseMoved", x, y, { button: "none", buttons: 0 });
  await mouse("mousePressed", x, y);
  await mouse("mouseReleased", x, y, { buttons: 0 });
  await sleep(350);
};
// The middle of an element inside the viewer, found by a selector.
const middle = (selector) => evaluate(`(() => { const el = ${V}.shadowRoot.querySelector(${JSON.stringify(selector)}); if (!el) return null; el.scrollIntoView({ block: "nearest" }); const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
const press = async (selector) => {
  const at = await middle(selector);
  if (!at) throw new Error(`nothing matches ${selector}`);
  await click(at.x, at.y);
};
const pressSpecies = async (id) => {
  const at = await evaluate(`(() => { const el = [...${V}.shadowRoot.querySelectorAll('[data-species="${id}"]')].find((b) => b.offsetParent); if (!el) return null; el.scrollIntoView({ block: "nearest" }); const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
  if (!at) throw new Error(`no button for the species ${id}`);
  await click(at.x, at.y);
};
// Where the switch is expected at this width: the bar (the default) or the card.
const EXPECT = process.env.EXPECT || "bar";
// What the page shows of its species: the switch, the rail, the cell's parts, the atlas.
const state = () =>
  evaluate(`(() => {
    const v = ${V}, root = v.shadowRoot, cell = v.lenses.get("cell"), atlas = v.lenses.get("proteins");
    const text = (selector) => root.querySelector(selector)?.textContent ?? null;
    const shown = (el) => Boolean(el && el.offsetParent);
    const panel = root.querySelector("cells-panel");
    return {
      lens: v.state.lens,
      species: v.state.species,
      attribute: v.dataset.species,
      atlasAttribute: v.dataset.atlas,
      inBar: [...root.querySelectorAll(".species [data-species]")].filter(shown).map((b) => b.dataset.species + (b.getAttribute("aria-pressed") === "true" ? "*" : "")).join(" "),
      inCard: [...root.querySelectorAll(".view [data-species]")].filter(shown).map((b) => b.dataset.species + (b.getAttribute("aria-pressed") === "true" ? "*" : "")).join(" "),
      state: [...root.querySelectorAll(".species-state")].filter(shown).map((b) => b.textContent)[0] ?? null,
      rail: [...root.querySelectorAll(".rail button")].map((b) => b.dataset.stop + (b.getAttribute("aria-pressed") === "true" ? "*" : "")).join(" "),
      railNote: text(".rail-note"),
      caveat: text(".caveat"),
      listWhole: (() => { const b = root.querySelector(".bar-end .pill-button"), bar = root.querySelector(".bar").getBoundingClientRect(); if (!b) return null; const r = b.getBoundingClientRect(), end = b.parentElement.getBoundingClientRect(); return r.right <= Math.min(bar.right, end.right) + 0.5 && r.left >= end.left - 0.5; })(),
      sizes: [...root.querySelectorAll(".view .seg-row")].map((row) => row.querySelector(".seg-label")?.textContent).join(" "),
      viewNote: text(".view-note"),
      stops: cell ? cell.currentStops.map((stop) => stop.id).join(" ") : null,
      activeStop: cell ? cell.activeStop : null,
      modes: cell ? cell.modes.join(" ") : null,
      drawn: cell ? [...cell.byEntity.keys()].filter((id) => id.startsWith("cap.")).sort().join(" ") : null,
      absent: cell ? [...cell.absent.keys()].filter((id) => id.startsWith("cap.")).sort().join(" ") : null,
      distance: v.stage.rig.distance,
      maxDistance: v.stage.rig.limits.maxDistance,
      u: cell ? cell.u : null,
      selected: v.state.selected,
      heading: text(".view-card .card-title"),
      cardText: text(".view-card .card-text"),
      marks: atlas ? atlas.marks.length : null,
      stamp: text(".stamp"),
      show: v.dataset.show ?? null,
      ownMarkers: atlas?.mounted ? atlas.mounted.nodes.size : null,
      notice: text(".view-card .card-notice"),
      shows: [...root.querySelectorAll(".view-card [data-show]")].map((b) => b.dataset.show + (b.getAttribute("aria-pressed") === "true" ? "*" : "")).join(" "),
      panel: panel.hidden ? null : { title: panel.querySelector("h2")?.textContent, eyebrow: panel.querySelector(".eyebrow")?.textContent, chips: [...panel.querySelectorAll(".chip")].map((c) => c.textContent).join(" | "), plain: panel.querySelector(".panel-plain")?.textContent, heads: [...panel.querySelectorAll(".panel-list h4")].map((h) => h.textContent).join(" | ") },
      barRows: (() => { const tops = [...root.querySelector(".bar").children].filter(shown).map((el) => Math.round(el.getBoundingClientRect().top / 20)); return new Set(tops).size; })(),
    };
  })()`);
const wheelOut = async (steps) => {
  for (let i = 0; i < steps; i++) {
    await page("Input.dispatchMouseEvent", { type: "mouseWheel", x: 640, y: 420, deltaX: 0, deltaY: 400, button: "none", buttons: 0 });
    await sleep(120);
  }
  await sleep(500);
};

try {
  await open("lens=cell");
  let s = await state();
  check("the page opens on the species whose file says default", s.species === "planarian" && s.attribute === "planarian" && /planarian\*/.test(s.inBar + s.inCard), JSON.stringify([s.species, s.inBar, s.inCard]));
  check(`the switch stands in the ${EXPECT} at ${WIDTH} px, and the List button is whole`, (EXPECT === "bar" ? s.inBar !== "" && s.inCard === "" : EXPECT === "card" ? s.inBar === "" && s.inCard !== "" : (s.inBar !== "") !== (s.inCard !== "")) && s.listWhole === true, JSON.stringify([s.inBar, s.inCard, s.listWhole]));
  check("planarian: five levels on the rail, both size modes, every capability of a cell drawn", s.rail === "molecule cell* tissue organ organism" && s.modes === "schematic real" && s.absent === "" && s.railNote === null, JSON.stringify([s.rail, s.modes, s.absent, s.railNote]));
  check("the bar stays on one line", s.barRows === 1, String(s.barRows));
  const planarian = s;

  await pressSpecies("syn3a");
  s = await state();
  check("a click on Syn3A shows it everywhere the page keeps a species", s.species === "syn3a" && s.attribute === "syn3a" && s.atlasAttribute === "syn3a" && /syn3a\*/.test(s.inBar + s.inCard), JSON.stringify([s.species, s.attribute, s.inBar, s.inCard]));
  check("Syn3A: two levels on the rail, and its own sentence where the others would be", s.rail === "molecule cell*" && /single-celled/.test(s.railNote || ""), JSON.stringify([s.rail, s.railNote]));
  check("Syn3A: one size mode, and the card says why", s.modes === "schematic" && !/Sizes/.test(s.sizes) && /One size mode/.test(s.viewNote || ""), JSON.stringify([s.modes, s.sizes, s.viewNote]));
  check("Syn3A: what has no place in it is not drawn", s.absent.includes("cap.junctions") && s.absent.includes("cap.mitochondria") && !s.drawn.includes("cap.junctions") && !s.drawn.includes("cap.mitochondria") && !s.drawn.includes("cap.sheet"), `absent: ${s.absent}; drawn: ${s.drawn}`);
  check("Syn3A: the bar says what Cells models of it", s.state === "Proposed, not modelled", String(s.state));
  check("Syn3A: its cell is drawn at its own size", s.u < 0.05 && s.distance < 3, JSON.stringify([s.u, s.distance]));
  const syn = s;

  // Zooming out ends at its cell.
  await wheelOut(40);
  s = await state();
  check("Syn3A: zooming out ends near its cell, on the cell's stop", s.distance <= s.maxDistance + 1e-6 && s.maxDistance < 10 && s.activeStop === "cell", JSON.stringify([s.distance, s.maxDistance, s.activeStop]));
  const beyond = await evaluate(`(() => { const lens = ${V}.current; const zone = lens.zones.find((z) => z.name === "beyond"); return zone ? { fade: zone.fade, labels: zone.labels.length, hidden: zone.labels.map((l) => l.hidden) } : null; })()`);
  check("Syn3A: its sentence is written where the further levels would be", beyond && beyond.fade > 0.9 && beyond.labels === 1 && beyond.hidden[0] === false, JSON.stringify(beyond));

  // What the species is, in the panel.
  await press(".species-state");
  s = await state();
  check("pressing the statement opens all that is said of the species", s.selected === "species:syn3a" && s.panel && s.panel.title === "Syn3A" && s.panel.eyebrow === "Species" && /Proposed, not modelled/.test(s.panel.chips) && /Not in this organism/.test(s.panel.heads), JSON.stringify(s.panel));
  check("the panel states that nothing of it is in the engine", /engine/i.test(s.panel?.plain || ""), s.panel?.plain);

  // The panel follows the species.
  await pressSpecies("human");
  s = await state();
  check("the panel follows the species to Human", s.species === "human" && s.selected === "species:human" && s.panel?.title === "Human", JSON.stringify([s.species, s.selected, s.panel?.title]));
  await evaluate(`${V}.select(null)`);
  await sleep(200);

  // A selected part that has no place in the next species is let go.
  await pressSpecies("planarian");
  await evaluate(`${V}.select("cap.junctions")`);
  await sleep(200);
  await pressSpecies("syn3a");
  s = await state();
  check("a selected part with no place in the next species is let go", s.selected === null && s.panel === null, JSON.stringify([s.selected, s.panel]));

  // The protein atlas follows the species.
  await press('.switch [data-lens="proteins"]');
  s = await state();
  check("the species is kept when the protein atlas is opened, and its switch is the same one", s.lens === "proteins" && s.species === "syn3a" && /syn3a\*/.test(s.inBar + s.inCard), JSON.stringify([s.lens, s.species, s.inBar, s.inCard, s.heading]));
  const synAtlas = s;
  // Which species have proteins of their own beside the page (schema/SPECIES_PROTEINS.md).
  const withOwn = await evaluate(`(${V}.model.raw.proteins.shelves || []).map((item) => item.id)`);
  if (withOwn.includes("syn3a")) {
    await evaluate(`Promise.resolve(${V}.current.ready)`);
    await sleep(400);
    s = await state();
    check("Syn3A in the atlas: its own proteins, one marker each, with the switch back to Cells' machines", s.show === "own" && s.ownMarkers > 0 && s.shows === "units own*" && s.heading === "Syn3A proteins", JSON.stringify([s.show, s.ownMarkers, s.shows, s.heading]));
  }
  await pressSpecies("human");
  s = await state();
  check("Human in the atlas: the inventory's own side, with no rings", s.species === "human" && s.heading === "The proteins Cells models" && s.marks === 0, JSON.stringify([s.species, s.heading, s.marks]));
  if (withOwn.length && !withOwn.includes("human")) check("Human in the atlas: one line says its own catalogue of proteins is not made", s.show === "units" && /not made yet/.test(s.notice || "") && s.shows === "", JSON.stringify([s.show, s.notice, s.shows]));
  await pressSpecies("planarian");
  s = await state();
  check("Planarian in the atlas: its own side, with rings", s.heading === "Planarian atlas" && s.marks > 0, JSON.stringify([s.heading, s.marks]));
  if (withOwn.includes("planarian")) check("Planarian in the atlas: the machines first, with the switch to its own proteins", s.show === "units" && s.shows === "units* own", JSON.stringify([s.show, s.shows]));
  await press('.switch [data-lens="cell"]');
  s = await state();
  check("back in the cell view the species is the same, and the planarian's levels are back", s.lens === "cell" && s.species === "planarian" && s.rail.startsWith("molecule cell") && s.rail.includes("organism") && s.drawn === planarian.drawn, JSON.stringify([s.species, s.rail]));

  // Every species the scene carries, whichever they are: its own levels, its statement, and the
  // switch staying where it stands (the bar or the card) for each of them, in both views.
  const all = await evaluate(`${V}.model.raw.species.map((item) => ({ id: item.id, label: item.label, state: item.modelled.state, levels: item.levels.map((level) => level.id), absent: Object.entries(item.cell.capabilities || {}).filter(([, said]) => said.place === "absent").map(([id]) => id) }))`);
  const places = [];
  for (const item of all) {
    await pressSpecies(item.id);
    s = await state();
    places.push(`${item.id}:${s.inBar ? "bar" : s.inCard ? "card" : "none"}`);
    const stops = { molecules: "molecule", cell: "cell", tissue: "tissue", organ: "organ", organism: "organism" };
    const rail = s.rail.replace("*", "").split(" ");
    const drawnAbsent = item.absent.filter((id) => s.drawn.split(" ").includes(id));
    check(`${item.label}: the rail has the levels of its file, and nothing it marks absent is drawn`, s.species === item.id && JSON.stringify(rail) === JSON.stringify(item.levels.map((id) => stops[id])) && drawnAbsent.length === 0 && s.listWhole === true, JSON.stringify([s.rail, item.levels, drawnAbsent, s.listWhole]));
    check(`${item.label}: the caveat under the picture ${item.state === "proposed" ? "says nothing of it is in the engine" : "is the map's own"}`, item.state === "proposed" ? new RegExp(`^${item.label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}: nothing of it is in the engine`).test(s.caveat || "") : !/nothing of it is in the engine/.test(s.caveat || "") && Boolean(s.caveat), String(s.caveat));
  }
  await press('.switch [data-lens="proteins"]');
  for (const item of all) {
    await pressSpecies(item.id);
    s = await state();
    places.push(`${item.id}:${s.inBar ? "bar" : s.inCard ? "card" : "none"}`);
  }
  await press('.switch [data-lens="cell"]');
  check("the switch stands in one place for every species, in the cell view and in the atlas", new Set(places.map((place) => place.split(":")[1])).size === 1, places.join(" "));
  console.log(`note  at ${WIDTH} px the switch stands in the ${places[0].split(":")[1]} (${all.length} species; fonts as this run has them)`);

  // The other views do not depend on the species: no switch there.
  await press('.switch [data-lens="engine"]');
  s = await state();
  check("the engine view shows no species switch", s.inBar === "" && s.inCard === "", JSON.stringify([s.inBar, s.inCard]));
  if (await evaluate(`Boolean(${V}.shadowRoot.querySelector('.switch [data-lens="experiments"]'))`)) {
    await press('.switch [data-lens="experiments"]');
    s = await state();
    check("the experiments view shows no species switch", s.inBar === "" && s.inCard === "", JSON.stringify([s.inBar, s.inCard]));
  }

  // The address sets the species; atlas= is another name for it; an unknown one is ignored.
  await open("lens=cell&species=syn3a");
  s = await state();
  check("species= in the address sets the species", s.species === "syn3a" && s.rail === "molecule cell*", JSON.stringify([s.species, s.rail]));
  await open("lens=proteins&atlas=human");
  s = await state();
  check("atlas= is another name for it", s.species === "human" && s.heading === "The proteins Cells models", JSON.stringify([s.species, s.heading]));
  await open("lens=cell&species=no-such-species");
  s = await state();
  check("an unknown species in the address is ignored", s.species === "planarian", String(s.species));

  // The keyboard.
  await evaluate(`[...${V}.shadowRoot.querySelectorAll('[data-species="human"]')].find((b) => b.offsetParent).focus()`);
  await page("Input.dispatchKeyEvent", { type: "keyDown", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13, text: "\r" });
  await page("Input.dispatchKeyEvent", { type: "keyUp", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13 });
  await sleep(400);
  s = await state();
  const focus = await evaluate(`${V}.shadowRoot.activeElement?.dataset?.species ?? null`);
  check("the switch works from the keyboard, and the focus stays on the button pressed", s.species === "human" && focus === "human", JSON.stringify([s.species, focus]));

  // A narrow window: the switch stands in the card.
  await size(400, 800);
  await open("lens=cell");
  s = await state();
  check("on a phone the switch stands in the card", s.inBar === "" && /planarian\*/.test(s.inCard), JSON.stringify([s.inBar, s.inCard]));
  await press('.view [data-species="syn3a"]');
  s = await state();
  const fits = await evaluate(`(() => { const root = ${V}.shadowRoot, card = root.querySelector(".view").getBoundingClientRect(); return [...root.querySelectorAll(".view [data-species]")].every((b) => { const r = b.getBoundingClientRect(); return r.left >= card.left - 0.5 && r.right <= card.right + 0.5; }); })()`);
  check("and it works there, inside the card", s.species === "syn3a" && s.rail === "molecule cell*" && fits, JSON.stringify([s.species, s.rail, fits]));
} catch (error) {
  check("the run completed", false, error.stack || error.message);
} finally {
  for (const line of pageLog) console.log(line);
  check("no script errors or blocked loads were reported by the page", pageLog.length === 0, `${pageLog.length} messages`);
  socket.close();
  { const closed = new Promise((resolve) => chrome.once("close", resolve)); chrome.kill(); await Promise.race([closed, new Promise((resolve) => setTimeout(resolve, 4000))]); if (chrome.exitCode === null && chrome.signalCode === null) chrome.kill("SIGKILL"); await Promise.race([closed, new Promise((resolve) => setTimeout(resolve, 2000))]); }
  server.close();
  release();
}
const failed = results.filter((ok) => !ok).length;
console.log(`${results.length - failed} of ${results.length} checks passed`);
process.exit(failed ? 1 : 0);
