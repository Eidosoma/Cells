#!/usr/bin/env node
// Checks the Laws library on the map's page (schema/LAWS_LIBRARY.md) with real pointer and key
// input, through the DevTools protocol, in the manner of tools/check_machine.mjs:
//
//   stars, stars-phone    Fly a recorded dependency to its field, restore the shared path,
//            highlight model membership and open the matrix on a desktop or phone.
//   atlas, atlas-phone    Check the earlier model-and-family bridge layout.
//   main     The shelf layout opens, its room clear of the cards on the left, the model
//            families with no rows standing as cases; a real press on a piece's bar chooses it,
//            and the panel says where the engine declares it and that no level is stated; ]
//            steps to the next piece and Escape lets go; a press on a case chooses that model,
//            the List's search finds the cases, and the List names the legacy model IDs as not
//            shown; typing in the card's search field finds pieces and the field keeps its focus;
//            the card's Family control goes to a family; the panel's link to the piece's Engine
//            view box opens the Engine view on that box, and the box's door ("Show its N
//            declared pieces in the Laws library") opens the library with them picked out, and
//            the card's Close lets them go; a lost WebGL context, and a lost GPU process, leave
//            the names written on the room as they were.
//   address  select=laws:<id> with no lens opens the library on that piece, in either spelling;
//            so does it from lens=engine. A legacy model ID opens a notice in the manifest's
//            words; an ID the manifest does not list, one that says so; the fuel kind, its row.
//            A piece links where it is declared at the manifest's revision. A unit of the
//            Protein atlas opens a declared law through its door, and says of an undeclared one
//            that no active model declares it, with no door; a unit of each mark of the law-port
//            inventory (U42, U47, U37, and for "port as is" the first unit whose every law has a
//            row of that mark and is undeclared, found from the data) says its law and that mark's
//            words, in one line with no door; and a law the table marks that the manifest now
//            declares opens its door, with no mark's words.
//   phone    on a 360 px phone the six views' switch fits the bar (its row scrolls, the library's tab in sight); the library opens on its wall,
//            a piece chosen opens the panel as a sheet, and no room is kept on the left.
//   gone     on a check-only scene without the Engine view's box that holds the declared laws'
//            files: no panel links it, and no level of a box is said.
//   text     with no 3D (WebGL switched off), the page says so, and the List gives the library's
//            families, models and cases, and a piece's panel.
//
// The address case also opens the Cell view after the library and holds it to the Cell view
// opened alone: what the library sets on the stage (light, shade, bloom, limits, insets) is not
// left behind.
//
//   node tools/check_laws.mjs [OUT_DIR]
//
// CASE defaults to stars. THEME and NAME control the palette and screenshot filenames.
// Each software-rendered browser takes an assigned CPU slot in tools/lib/browser_lock.mjs.

import { spawn } from "node:child_process";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { createServer } from "./serve.mjs";
import { acquireBrowser } from "./lib/browser_lock.mjs";
import { DEFAULT_RUNS, DEFAULT_SCENE, ROOT } from "./lib/build_page.mjs";
import { phraseOf } from "../src/lenses/law_port.js";
import { fieldKey } from "../src/lenses/laws_connections.js";
import { unitLaws } from "../src/lenses/laws_card.js";

const outDir = process.argv[2] ? path.resolve(process.argv[2]) : null;
if (outDir) await mkdir(outDir, { recursive: true });
const CASE = process.env.CASE || "stars";
const ATLAS = CASE === "atlas" || CASE === "atlas-phone";
const STARS = CASE === "stars" || CASE === "stars-phone";
const PHONE = CASE === "phone" || CASE === "atlas-phone" || CASE === "stars-phone";
const WIDTH = Number(process.env.WIDTH || (PHONE ? 360 : 1440)), HEIGHT = Number(process.env.HEIGHT || (PHONE ? 780 : 900));
const NAME = process.env.NAME || `laws-${CASE}`;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const results = [];
const check = (name, ok, detail = "") => {
  results.push(Boolean(ok));
  console.log(`${ok ? "pass" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`);
};
const note = (text) => console.log(`note  ${text}`);
const pageLog = [];
const release = await acquireBrowser({ wait: Number(process.env.WAIT_MINUTES || 30) * 60 * 1000 });
// "gone": a check-only scene without the Engine view's box of the declared laws, as when the Engine view no longer draws a box a
// piece of the list was read under (CHECK_SCENE names another file to draw instead).
let scene = process.env.CHECK_SCENE || DEFAULT_SCENE;
// The Engine view's box that holds the files the inner model's own laws are declared in (each law's own module since
// seam F's laws as modules), and its door's piece.
const GONE_BOX = "laws.declarations";
const MANIFEST = JSON.parse(await readFile(path.join(ROOT, "data", "engine", "declarations.json"), "utf8"));
// The law-port inventory's table: the mark of each law a unit names that no active model declares.
const PORT = JSON.parse(await readFile(path.join(ROOT, "data", "laws", "law_port.json"), "utf8"));
// What the checks expect is counted from the manifest, never fixed here: it gains pieces at later merges, and a
// piece's file and line are the manifest's own, which the engine's moves change.
const lineOf = (id) => MANIFEST.pieces.find((piece) => piece.declared_id === id)?.line;
const fileOf = (id) => MANIFEST.pieces.find((piece) => piece.declared_id === id)?.module_path;
const literally = (text) => String(text).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
// The units the law-port cases open are found from the data too: a law the table marks may be declared at a later
// merge (the five Kv1 laws of U05–U08 and U10 were, at 1ca5eada), and then its unit opens a door instead.
const DECLARED = new Set(MANIFEST.pieces.flatMap((piece) => [piece.id, piece.declared_id]));
const aliases = JSON.parse(await readFile(path.join(ROOT, "data/engine/viewer-ids.json"), "utf8")).aliases;
const currentID = id => aliases[id] || id;
const declaredLaw = law => DECLARED.has(currentID(law));
const UNITS = JSON.parse(await readFile(DEFAULT_SCENE, "utf8")).entities.filter((entity) => entity.kind === "unit");
const PORT_AS_IS = (() => {
  for (const unit of UNITS) {
    const code = unit.id.replace(/^unit\./, ""), laws = unitLaws(unit);
    const rows = laws.map((law) => PORT.rows.find((row) => row.has_id && row.law === law && row.units.includes(code)));
    if (laws.length && rows.every((row) => row?.mark === "port as is") && !laws.some(declaredLaw)) return [code, laws[0]];
  }
  return null;
})();
const PORT_DECLARED = PORT.rows.find((row) => row.has_id && declaredLaw(row.law)) || null;
const CASES = MANIFEST.models.filter((model) => !model.rows.length).length, RACKS = MANIFEST.models.length - CASES;
if (CASE === "gone" && !process.env.CHECK_SCENE) {
  const whole = JSON.parse(await readFile(DEFAULT_SCENE, "utf8"));
  whole.entities = whole.entities.filter((entity) => entity.id !== GONE_BOX);
  whole.relations = whole.relations.filter((relation) => relation.from !== GONE_BOX && relation.to !== GONE_BOX);
  scene = path.join(outDir || path.join(ROOT, "out"), "laws-gone.scene.json");
  await writeFile(scene, JSON.stringify(whole));
}
const server = createServer({ offline: true, scene, runs: DEFAULT_RUNS, log: (line) => pageLog.push(line) });
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
  await page("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: HEIGHT, deviceScaleFactor: 1, mobile: PHONE });
  if (process.env.THEME === "dark") await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "dark" }] });
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
  const click = async (x, y, wait = 700) => {
    await mouse("mouseMoved", x, y, { button: "none", buttons: 0 });
    await mouse("mousePressed", x, y);
    await mouse("mouseReleased", x, y, { buttons: 0 });
    await sleep(wait);
  };
  const KEYS = { Escape: 27, PageDown: 34, PageUp: 33, "]": 221, "[": 219 };
  const key = async (name) => {
    await page("Input.dispatchKeyEvent", { type: "keyDown", key: name, code: name.length === 1 ? (name === "]" ? "BracketRight" : "BracketLeft") : name, windowsVirtualKeyCode: KEYS[name] || 0 });
    await page("Input.dispatchKeyEvent", { type: "keyUp", key: name, code: name.length === 1 ? (name === "]" ? "BracketRight" : "BracketLeft") : name, windowsVirtualKeyCode: KEYS[name] || 0 });
    await sleep(600);
  };
  /** The middle of what an expression finds, if it is on the screen and nothing lies over it. */
  const placeOf = (expression) =>
    evaluate(`(() => { const root = ${V}.shadowRoot, el = ${expression}; if (!el) return null; el.scrollIntoView({ block: "nearest" }); const r = el.getBoundingClientRect(); if (!r.width || !r.height) return null; const x = r.left + r.width / 2, y = r.top + r.height / 2; const top = root.elementFromPoint(x, y); return top && (top === el || el.contains(top)) ? { x, y, words: el.textContent } : null; })()`);
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
  const open = async (query) => {
    await page("Page.navigate", { url: `${process.env.CHECK_BASE || base}?${STARS ? "" : ATLAS ? "lawLayout=atlas&" : "lawLayout=shelves&"}${query}` });
    const up = await until(CASE === "text" ? `Boolean(${V}?.model)` : `Boolean(${V}?.current)`, 240);
    await sleep(1500);
    return up;
  };
  const state = () =>
    evaluate(`(() => {
      const v = ${V}, root = v.shadowRoot, lens = v.current, panel = root.querySelector("cells-panel");
      return { lens: v.state.lens, selected: v.state.selected, insets: v.stage?.insets || {}, filter: lens?.filter ? { ...lens.filter } : null,
        panel: panel && !panel.hidden ? panel.textContent : "", views: [...root.querySelectorAll(".switch button")].map((b) => ({ id: b.dataset.lens, pressed: b.getAttribute("aria-pressed") })),
        target: v.stage ? v.stage.rig.target.toArray().map((x) => +x.toFixed(2)) : null, distance: v.stage ? +v.stage.rig.distance.toFixed(2) : null, focus: root.activeElement?.id || null };
    })()`);
  /** The names written on the room: how much of their canvas holds ink (0 when it came back blank). */
  const inked = () =>
    evaluate(`(() => { const c = ${L}.plaqueMesh?.material?.map?.image; if (!c) return null; const d = c.getContext("2d").getImageData(0, 0, c.width, Math.min(c.height, 256)).data; let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i]) n++; return n; })()`);
  const barAt = (id) =>
    evaluate(`(() => { const v = ${V}, p = v.current.barPoint(${JSON.stringify(id)}).clone(); const q = v.stage.project(p, p.clone()); const r = v.canvas.getBoundingClientRect(); return { x: r.left + q.x, y: r.top + q.y }; })()`);

  if (STARS) {
    const root = V + ".shadowRoot";
    const press = async (selector) => {
      const point = await placeOf("root.querySelector("+JSON.stringify(selector)+")");
      if (!point) throw new Error("The control is covered or missing: "+selector);
      await click(point.x, point.y, 80);
    };
    const choose = (key,value) => evaluate(`(()=>{const el=${root}.querySelector('[data-atlas-control="${key}"]'); el.value=${JSON.stringify(value)};el.dispatchEvent(new Event("change",{bubbles:true}));})()`);
    const settled = () => until("!"+V+".stage.rig.flight");
    await open("lens=laws");
    check("every catalogue piece has a star at its own address", await evaluate(`${L}.map.stars.size===${L}.library.pieces.length && ${L}.light.root.parent===${V}.stage.scene`));
    await shot(NAME+"-overview");
    const position = await state();
    await choose("model","cells.model.resolved_pump_composite@1");
    check("model membership lights the catalogue in place", await evaluate(`${L}.overviewCount().pieces===${L}.graph.members.get(${L}.primary).size`) &&
      JSON.stringify((await state()).target)===JSON.stringify(position.target));
    await shot(NAME+"-model");
    await choose("family","operator"); await settled();
    check("a family outside the model has no membership link", await evaluate(`!${root}.querySelector('[data-atlas-action="memberships"]') && ${L}.overviewCount().pieces===0`));
    await choose("family","channel"); await settled();
    await evaluate(`${root}.querySelector('[data-atlas-action="memberships"]').click()`);
    check("the selected family opens its recorded model memberships", await evaluate(`${L}.graph.bundles.get(${L}.selected)?.family==="channel" && ${L}.overviewCount().pieces===${L}.graph.bundles.get(${L}.selected).entries.length`));
    await choose("family",""); await settled();
    await press('[data-atlas-action="example"]'); await settled();
    check("the example shows the two real requirements",await evaluate(`${L}.relation==="requires" && ${L}.links.size===2`));
    await shot(NAME+"-requires");
    const destination="laws:cells.operator.scheduled_cell_replacement@1";
    const targetSelector='.label-star-target[data-label="'+destination+'"]:not(.is-off)';
    const target=await placeOf("root.querySelector("+JSON.stringify(targetSelector)+")");
    if (target) await click(target.x,target.y,30);
    else {
      if (PHONE && !(await evaluate(V+".state.viewOpen"))) await press(".view-toggle");
      await press('[data-atlas-action="follow"]');
      if (PHONE && (await evaluate(V+".state.viewOpen"))) await press(".view-toggle");
    }
    check("Follow takes the camera along the drawn curve",await evaluate(`${L}.path[0]?.edge.id===${JSON.stringify(destination)} && ${V}.stage.rig.flight?.path===${L}.path[0].curve`));
    await settled();
    await choose("relation","reads");await settled();
    check("the next stop has the three recorded read fields",await evaluate(`Array.from(${L}.links.values()).map(e=>e.edge.name).join(",")==="volume,extracellular_volume,membrane_area"`));
    await shot(NAME+"-reads");
    const fieldSelector='.label-star-target[data-label*="membrane_area"]:not(.is-off)';
    const field=await placeOf("root.querySelector("+JSON.stringify(fieldSelector)+")");
    if (field) await click(field.x,field.y,20);
    else {
      if (PHONE && !(await evaluate(V+".state.viewOpen"))) await press(".view-toggle");
      await press('.star-destinations button:last-child');
      if (PHONE && (await evaluate(V+".state.viewOpen"))) await press(".view-toggle");
    }
    await settled();
    check("the endpoint and both travelled links stay visible",await evaluate(`${L}.terminal && ${L}.path.length===2 && ${L}.path[1].edge.name==="membrane_area" && ${root}.querySelectorAll("[data-star-stop]").length===3`));
    const query=await evaluate("location.search.slice(1)");
    await open(query);
    check("a shared flight restores the endpoint and its path",await evaluate(`${L}.terminal && ${L}.path.at(-1).edge.name==="membrane_area" && ${L}.path.length===2`));
    await evaluate(`${root}.querySelector('[data-star-stop="0"]').click()`);
    check("a breadcrumb returns to that piece and relation",await evaluate(`${L}.trace==="cells.operator.site_occupant_replacement@1" && ${L}.relation==="requires" && !${L}.path.length`));
    await press('[data-atlas-action="overview"]');
    await press('[data-atlas-action="open-matrix"]');
    check("the matrix compares actual memberships",await evaluate(`${L}.mode==="compare" && ${root}.querySelectorAll(".star-matrix tbody tr").length>0 && ${root}.querySelector(".star-matrix [data-star-group='1']").textContent.includes(String(${L}.graph.compare(${L}.primary,${L}.other)[1].length))`));
    await press('.star-matrix [data-star-group="1"]');
    await shot(NAME+"-matrix");
    await press('[data-atlas-action="close-matrix"]');
    await page("Emulation.setEmulatedMedia",{features:[{name:"prefers-reduced-motion",value:"reduce"}]});
    await press('[data-atlas-action="example"]');
    await evaluate(`${L}.follow(${JSON.stringify(destination)})`);
    check("reduced motion lands immediately without a pulse",await evaluate(`!${V}.stage.rig.flight && !${L}.light.pulse.visible && ${L}.trace==="cells.operator.scheduled_cell_replacement@1"`));
    await open("lens=laws&lawFamily=cycle&still=1");
    check("families are grouped in the catalogue control", await evaluate(`${root}.querySelectorAll('[data-atlas-control="family"] optgroup').length >= 4`));
    await evaluate(`${root}.querySelector('[data-atlas-action="family-routes"]').click()`);
    await settled();
    check("the cycle family maps declared reads to the Binding family", await evaluate(`${L}.showFamilyRoutes && ${L}.familyBounds && ${L}.familyRoutes().get("binding").some(({source,edge})=>source.id==="cells.cycle.atp_driven_transporter_mass_action_positive@2" && edge.verb==="reads")`));
    await shot(NAME+"-family-connections");
    const legacy = new URLSearchParams({
      lens: "laws", trace: "scheduled_cell_replacement@1", lawRelation: "reads",
      lawModel: "resolved_pump_composite@1",
      lawTrail: JSON.stringify(["site_occupant_replacement@1", ["requires","laws:scheduled_cell_replacement@1"],
        ["reads","laws:field/scheduled_cell_replacement%401/reads/membrane_area"]]),
    });
    await open(legacy.toString());
    const currentField = fieldKey(currentID("scheduled_cell_replacement@1"),"reads","membrane_area");
    check("a v58 flight restores the field and both links under canonical IDs", await evaluate(`${L}.terminal && ${L}.path.length===2 && ${L}.path.at(-1).edge.id===${JSON.stringify(currentField)}`));
    await evaluate(`${V}.setLens("engine",true)`);
    check("leaving the atlas releases its sky and controls",await evaluate(`!${root}.querySelector(".laws-space,.star-overlay") && !${V}.stage.scene.children.includes(${V}.lenses.get("laws").light.root)`));
    await open("lens=engine&select=op.site_occupant_replacement@1");
    check("a v58 Engine operator link opens the canonical operator", (await state()).selected==="op.cells.operator.site_occupant_replacement@1");
  } else if (ATLAS) {
    await open("lens=laws&still=1");
    const root = V + ".shadowRoot";
    const choose = (name, value) =>
      evaluate(
        `(() => { const el=${root}.querySelector('[data-atlas-control="${name}"]'); el.value=${JSON.stringify(value)}; el.dispatchEvent(new Event("change",{bubbles:true})); })()`,
      );
    const tap = (selector) => evaluate(`${root}.querySelector(${JSON.stringify(selector)}).click()`);
    const phoneMenu = async () => {
      if (PHONE && !(await evaluate(V + ".state.viewOpen"))) await tap(".view-toggle");
    };
    check(
      "the Laws tab opens the family atlas",
      await evaluate(L + '.mode==="atlas" && ' + L + ".drawing.anchors.size > " + L + ".library.pieces.length"),
    );
    await shot(NAME + "-map");
    const bridge = await evaluate(
      `(()=>{const v=${V},l=v.current,r=v.canvas.getBoundingClientRect();for(const b of l.graph.bundles.values()){const p=l.drawing.anchors.get(b.id);if(!p)continue;const q=v.stage.project(p,p.clone()),x=q.x+r.left,y=q.y+r.top;if(v.shadowRoot.elementFromPoint(x,y)===v.canvas && v.stage.pick(x,y,l.pickRoots)?.id===b.id)return {x,y,id:b.id};}return null;})()`,
    );
    check("a bridge can be picked in the rendered viewport", Boolean(bridge));
    if (bridge) {
      await click(bridge.x, bridge.y);
      check(
        "a pointer press opens the bridge membership groups",
        await evaluate(`${V}.state.selected===${JSON.stringify(bridge.id)} && ${L}.describe(${JSON.stringify(bridge.id)}).opens.some(g=>g.count>0)`),
      );
      await tap(".exp-back");
    }
    await phoneMenu();
    await choose("model", "");
    check(
      "the overview counts every nonempty model–family bridge",
      await evaluate(root + '.querySelector(".laws-tally").textContent.startsWith(' + L + '.graph.bundles.size+" bridges")'),
    );
    await choose("origin", "design");
    check(
      "the design-note filter has its own URL and shows only design entries",
      await evaluate(`new URL(location.href).searchParams.get("lawWhere")==="design" && ${L}.filtered().length===${L}.library.counts().where.design && ${L}.filtered().every(p=>!p.declared)`),
    );
    await choose("origin", "all");
    await tap('[data-atlas-action="example"]');
    check(
      "the example opens the declared piece with its own URL",
      await evaluate(L + '.mode==="wiring" && new URL(location.href).searchParams.get("trace")===' + L + ".trace"),
    );
    await phoneMenu();
    await choose("relation", "writes");
    check(
      "the write filter only draws declared targets",
      await evaluate("Object.values(" + L + '.traceLayers()).flat().every(e=>e.verb==="writes") && ' + L + ".traceLayers().fields.length>0"),
    );
    await choose("relation", "main");
    if (PHONE && (await evaluate(V + ".state.viewOpen"))) await tap(".view-toggle");
    await shot(NAME + "-wiring");
    await phoneMenu();
    await choose("neighbour", "laws:field/site_occupant_replacement%401/writes/site_bound_increment_fmol");
    check(
      "the written field points to its receiving operator",
      await evaluate(
        L + ".describe(" + L + '.selected)?.opens.some(g=>g.title.includes("Engine map")&&g.items.some(e=>e.id==="laws:cells.operator.site_occupancy@1"))',
      ),
    );
    await tap(".exp-back");
    await phoneMenu();
    await choose("model", "cells.model.resolved_pump_water@2");
    await choose("compare", "cells.model.resolved_pump_replacement@1");
    check(
      "comparison displays each of the two models’ pieces once",
      await evaluate(
        `(()=>{const l=${L}, g=l.graph.compare(l.primary,l.other);return l.mode==="compare" && g.flat().length===new Set(g.flat().map(p=>p.id)).size && [...${root}.querySelectorAll(".laws-sets strong")].every((n,i)=>+n.textContent===g[i].length)})()`,
      ),
    );
    if (PHONE && (await evaluate(V + ".state.viewOpen"))) await tap(".view-toggle");
    await shot(NAME + "-compare");
    const url = await evaluate("location.search.slice(1)");
    await open(url);
    check(
      "reloading the comparison preserves the pair",
      await evaluate(L + '.mode==="compare" && ' + L + '.primary==="cells.model.resolved_pump_water@2" && ' + L + '.other==="cells.model.resolved_pump_replacement@1"'),
    );
    await phoneMenu();
    await choose("piece", "cells.operator.scheduled_cell_replacement@1");
    await phoneMenu();
    await tap('[data-atlas-action="trace"]');
    await tap(".exp-back");
    check(
      "returning to the pair restores the inspected piece",
      await evaluate(L + '.mode==="compare" && ' + L + '.selected==="laws:cells.operator.scheduled_cell_replacement@1"'),
    );
    await open("lens=cell&select=cap.channels&still=1");
    const mapped = await evaluate(
      `[...${root}.querySelectorAll(".panel-door button")].find(b=>b.textContent.includes("mapped")&&b.textContent.includes("Laws atlas"))?.textContent`,
    );
    check("the cell view offers its inventory mapping", Boolean(mapped));
    if (mapped)
      await evaluate(
        `[...${root}.querySelectorAll(".panel-door button")].find(b=>b.textContent.includes("mapped")&&b.textContent.includes("Laws atlas")).click()`,
      );
    check(
      "the cell opens exactly its mapped pieces",
      await until(L + '.anatomy==="cap.channels" && ' + L + ".filtered().length===" + L + '.cellMap.get("cap.channels").size'),
    );
  } else if (CASE === "main") {
    // ---------------------------------------------------------- the fifth view, with its room clear of the cards
    check("the page opens on lens=laws", await open("lens=laws"));
    let s = await state();
    check("the switch offers six views, the Laws library pressed", s.views.length === 6 && s.views.find((view) => view.id === "laws")?.pressed === "true", JSON.stringify(s.views));
    const card = await evaluate(`(() => { const r = ${V}.shadowRoot.querySelector("#cells-view").getBoundingClientRect(); return { right: r.right, hidden: ${V}.shadowRoot.querySelector("#cells-view").hidden }; })()`);
    check("the room is kept clear of the view card on the left (a left inset)", s.insets.left > 0 && Math.abs(s.insets.left - (card.right + 12)) < 30, JSON.stringify([s.insets, card]));
    const corners = await evaluate(`(() => { const v = ${V}, l = v.current, b = l.layout.bounds, w = l.layout.wall; const r = v.canvas.getBoundingClientRect(); const xs = []; for (const x of [b.minX, b.maxX]) for (const y of [0, w.y + w.h]) { const p = new v.stage.camera.position.constructor(x, y, b.maxZ); v.stage.project(p, p); xs.push(r.left + p.x); } return { min: Math.min(...xs), max: Math.max(...xs) }; })()`);
    check("and the room stands right of the card, nothing cut", corners.min >= card.right - 4 && corners.max <= WIDTH + 2, JSON.stringify([corners, card.right]));
    check("the names are written on the room", (await inked()) > 1000);
    const cases = await evaluate(`({ drawn: ${L}.cases.mesh.count, listed: ${L}.library.cases.length, legend: [...${V}.shadowRoot.querySelectorAll("cells-legend .legend-label")].map((label) => label.textContent) })`);
    check("the model families with no rows stand as closed cases, named in the legend", cases.drawn === CASES && cases.listed === CASES && cases.legend.some((text) => /^A closed case: a model family with no rows/.test(text)), JSON.stringify(cases));
    const rest = s;
    await shot(`${NAME}-rest`);

    // ---------------------------------------------------------- a real press on a bar
    const id = "cells.cycle.nak_atp_mass_action_positive@1";
    const at = await barAt(id);
    await click(at.x, at.y, 1500);
    s = await state();
    check("a real press on a piece's bar chooses it", s.selected === `laws:${id}`, String(s.selected));
    check("its panel says where the engine declares it", new RegExp(`Declared in\\s*${literally(fileOf(id))}, line ${lineOf(id)}(?!\\d)`).test(s.panel), (s.panel.match(/Declared in.{0,80}/) || [""])[0]);
    check("and that no level is stated, and says none", /not stated: the engine's declarations give no level for it/.test(s.panel) && !/\b(established|qualified|landed)\b/i.test(s.panel), (s.panel.match(/.{0,60}(Status|established|qualified|landed).{0,80}/i) || [""])[0]);
    check("the panel links its Engine view box", /On the Engine view/.test(s.panel));
    await shot(`${NAME}-piece`);
    const order = await evaluate(`${L}.order()`);
    await evaluate(`${V}.canvas.focus({ preventScroll: true })`);
    await key("]");
    s = await state();
    check("] steps to the next piece of the wall's order", s.selected === order[(order.indexOf(`laws:${id}`) + 1) % order.length], String(s.selected));
    await key("Escape");
    s = await state();
    check("Escape lets go", !s.selected, String(s.selected));

    // ---------------------------------------------------------- a model family: chosen by a press, found in the List; no word says older
    const family = "cells.model.resolved_pump_tissue@2";
    const caseAt = await evaluate(`(() => { const v = ${V}, item = v.current.layout.cases.find((c) => c.id === ${JSON.stringify(family)}); const p = new v.stage.camera.position.constructor(item.x, item.y, item.z + item.d / 2); v.stage.project(p, p); const r = v.canvas.getBoundingClientRect(); return { x: r.left + p.x, y: r.top + p.y }; })()`);
    await click(caseAt.x, caseAt.y, 1500);
    s = await state();
    check("a real press on a model family's case chooses it, and its panel says what it is", s.selected === `laws:${family}` && /A model family with no rows/.test(s.panel) && /its laws are tables inside it/.test(s.panel), JSON.stringify([s.selected, s.panel.slice(0, 120)]));
    await shot(`${NAME}-family`);
    await evaluate(`${V}.toggleIndex(true)`);
    await sleep(400);
    const listed = await evaluate(`(() => { const root = ${V}.shadowRoot, search = root.querySelector("#cells-index-search"); search.value = "resolved_pump_tissue"; search.dispatchEvent(new Event("input")); return [...root.querySelectorAll("cells-index section")].map((section) => [section.querySelector("h3").textContent, [...section.querySelectorAll(".index-name")].map((name) => name.textContent)]); })()`);
    check("the List's search finds the model families by name, under Model families with no rows", JSON.stringify(listed.find(([label]) => label === "Model families with no rows")?.[1]) === JSON.stringify(["cells.model.resolved_pump_tissue@1", "cells.model.resolved_pump_tissue@2"]), JSON.stringify(listed));
    await evaluate(`(() => { const search = ${V}.shadowRoot.querySelector("#cells-index-search"); search.value = ""; search.dispatchEvent(new Event("input")); })()`);
    if (!(await evaluate(`${V}.state.legendOpen`))) await evaluate(`${V}.shadowRoot.dispatchEvent(new CustomEvent("cells-legend-toggle"))`);
    await sleep(400);
    await sleep(400);
    // The List names what the wall does not show: the manifest's legacy model IDs, in its own words.
    const legacy = await evaluate(`(() => { const section = [...${V}.shadowRoot.querySelectorAll("cells-index section")].find((item) => item.querySelector("h3").textContent.startsWith("Not shown")); return section ? [section.querySelector("h3").textContent, section.querySelectorAll(".index-row").length, section.querySelector(".index-more")?.textContent || ""] : null; })()`);
    check("the List names the legacy model IDs as not shown, in the manifest's words", legacy && legacy[0] === "Not shown: the older model families (legacy code, to be dropped)" && legacy[1] === 12 && new RegExp(`and ${MANIFEST.legacy.length - 12} more`).test(legacy[2]), JSON.stringify(legacy));
    // A cited law's panel: its citation as the manifest states it.
    await evaluate(`${V}.select("laws:cells.route.proton_constant_field_leak@1")`);
    await sleep(1500);
    s = await state();
    check("a cited law's panel says its citation, where in it, its licence and how it departs", /Provenance\s*cited/.test(s.panel) && /Goldman-Hodgkin-Katz/.test(s.panel) && /Where in it\s*docs\/COMPARTMENT_PH_TRANSFER_DESIGN\.md/.test(s.panel) && /Licence\s*no numbers taken/.test(s.panel) && /Departs from it\s*it reads free h/.test(s.panel), s.panel.slice(0, 300));
    await evaluate(`${V}.shadowRoot.dispatchEvent(new CustomEvent("cells-legend-toggle"))`);
    await evaluate(`${V}.toggleIndex(false)`);
    await evaluate(`${V}.canvas.focus({ preventScroll: true })`);
    await key("Escape");
    s = await state();
    check("and Escape lets go of it", !s.selected && !(await evaluate(`${V}.state.legendOpen || ${V}.state.indexOpen`)), String(s.selected));

    // ---------------------------------------------------------- the card's search and its Family control
    const field = await placeOf(`root.querySelector("#cells-find")`);
    check("the card has a search field", Boolean(field));
    if (field) {
      await click(field.x, field.y, 300);
      for (const letter of "calcium") {
        await page("Input.dispatchKeyEvent", { type: "keyDown", key: letter, text: letter });
        await page("Input.dispatchKeyEvent", { type: "keyUp", key: letter });
        await sleep(60);
      }
      await sleep(600);
      s = await state();
      const typed = await evaluate(`${V}.shadowRoot.querySelector("#cells-find")?.value`);
      check("typing finds pieces, and the field keeps its focus and every letter", s.filter.query === "calcium" && typed === "calcium" && s.focus === "cells-find", JSON.stringify([s.filter.query, typed, s.focus]));
      check("and the legend names what the search finds", await evaluate(`[...${V}.shadowRoot.querySelectorAll("cells-legend .legend-label")].some((label) => /^Forward: found/.test(label.textContent))`));
      await shot(`${NAME}-search`);
      await evaluate(`(() => { const f = ${V}.shadowRoot.querySelector("#cells-find"); f.value = ""; f.dispatchEvent(new Event("input", { bubbles: true })); })()`);
    }
    const before = await state();
    await evaluate(`(() => { const select = ${V}.shadowRoot.querySelector("#cells-mark"); select.value = "split"; select.dispatchEvent(new Event("change", { bubbles: true })); })()`);
    // In software a frame of this view takes a while: the flight is waited for until it lands.
    const flew = await evaluate(`Boolean(${V}.stage.rig.flight)`);
    const landed = await until(`!${V}.stage.rig.flight`, 240);
    note(`the Family control's flight: started ${flew}, landed ${landed}`);
    s = await state();
    check("the card's Family control chooses a family, and the camera goes to its column", s.filter.family === "split" && (s.distance < before.distance - 1 || s.target.join() !== before.target.join()), JSON.stringify([s.filter.family, before.distance, s.distance]));
    await evaluate(`(() => { const select = ${V}.shadowRoot.querySelector("#cells-mark"); select.value = "all"; select.dispatchEvent(new Event("change", { bubbles: true })); })()`);
    await sleep(1200);

    // ---------------------------------------------------------- the way back to the Engine view, and the door from it
    await evaluate(`${V}.select("laws:${id}", { fly: true })`);
    await sleep(1500);
    const back = await placeOf(`[...root.querySelectorAll("cells-panel .panel-list")].find((list) => list.querySelector("h4")?.textContent.startsWith("On the Engine view"))?.querySelector(".link-button")`);
    check("the panel's link to the piece's box can be pressed", Boolean(back));
    if (back) await click(back.x, back.y, 1800);
    s = await state();
    check("it opens the Engine view on the box that holds the piece's file", s.lens === "engine" && s.selected === GONE_BOX, JSON.stringify([s.lens, s.selected]));
    const words = await evaluate(`[...${V}.shadowRoot.querySelectorAll("cells-panel .panel-door button")].map((button) => button.textContent)`);
    const doorWords = words.find((text) => /in the Laws library/.test(text));
    const inPumps = await evaluate(`${V}.lenses.get("laws").library.inBox("${GONE_BOX}").length`);
    check("the box's panel has a door into the Laws library, with the declared pieces' count", new RegExp(`Show its ${inPumps} declared pieces? in the Laws library`).test(doorWords || ""), JSON.stringify([words, inPumps]));
    await shot(`${NAME}-engine-box`);
    const door = await placeOf(`[...root.querySelectorAll("cells-panel .panel-door button")].find((button) => /in the Laws library/.test(button.textContent))`);
    if (door) await click(door.x, door.y, 2000);
    s = await state();
    check("the door opens the library with the box's pieces picked out", s.lens === "laws" && s.filter.box === GONE_BOX && (await evaluate(`${L}.order().length`)) === inPumps, JSON.stringify([s.lens, s.filter]));
    await until(`!${V}.stage.rig.flight`, 240);
    s = await state();
    check("and the camera goes to them, away from the opening view", s.distance < rest.distance - 1 && s.target.join() !== rest.target.join(), JSON.stringify([rest.distance, s.distance, rest.target, s.target]));
    await shot(`${NAME}-door`);
    const close = await placeOf(`root.querySelector('[data-close="open"]')`);
    check("the card says what is picked out, with a Close", Boolean(close));
    if (close) await click(close.x, close.y, 900);
    s = await state();
    check("Close lets them go", !s.filter.box, JSON.stringify(s.filter));

    // ---------------------------------------------------------- a lost context, and a lost GPU process
    const ink = await inked();
    const lost = await evaluate(`(async () => { const v = ${V}, gl = v.stage.renderer.getContext(), ext = gl.getExtension("WEBGL_lose_context"); if (!ext) return { asked: false };
      const back = new Promise((done) => v.canvas.addEventListener("webglcontextrestored", () => done(true), { once: true }));
      ext.loseContext(); await new Promise((r) => setTimeout(r, 500)); const lostNow = gl.isContextLost(); ext.restoreContext();
      const came = await Promise.race([back, new Promise((r) => setTimeout(() => r(false), 5000))]); return { asked: true, lostNow, came }; })()`);
    await sleep(1500);
    const afterLoss = await inked();
    check("a lost WebGL context that comes back leaves the names written on the room", lost.asked && lost.lostNow && lost.came && afterLoss > 0 && Math.abs(afterLoss - ink) <= ink * 0.01, JSON.stringify([lost, ink, afterLoss]));
    await send("Browser.crashGpuProcess", {});
    await sleep(6000);
    await evaluate(`${V}.stage.invalidate()`);
    await sleep(1500);
    const afterCrash = await inked();
    check("so does a lost GPU process, which takes the 2D canvases on the card with it", afterCrash > 0 && Math.abs(afterCrash - ink) <= ink * 0.01, JSON.stringify([ink, afterCrash]));
    await shot(`${NAME}-after-loss`);
  } else if (CASE === "gone") {
    // ---------------------------------------------------------- a box the Engine view does not draw
    check("the page opens on a piece whose box is not drawn", await open("lens=laws&select=laws:cells.cycle.nak_atp_mass_action_positive@1"));
    const s = await state();
    check("its panel quotes no level of any box", !/established|qualified|landed|planned/i.test(s.panel), s.panel.slice(0, 200));
    check("and offers no link to the box the page does not draw", !/On the Engine view/.test(s.panel));
    const links = await evaluate(`(() => { const v = ${V}, lens = v.current, bad = []; for (const id of [...lens.library.pieces.map((p) => "laws:" + p.id), ...lens.library.frames.map((f) => "laws:" + f.id)]) for (const group of lens.describe(id).related || []) for (const box of group.ids) { const part = v.model.get(box); if (!part || v.model.lensOf(part) !== "engine") bad.push(id + " -> " + box); } return bad; })()`);
    check("no panel of the library links a box the page does not draw", links.length === 0, links.slice(0, 3).join(", "));
    await shot(`${NAME}-piece`);
    check("the Engine view has no such box to open", (await open(`lens=engine&select=${GONE_BOX}`)) && !(await state()).selected);
  } else if (CASE === "address") {
    check("select=laws:<id> with no lens opens the library on that piece", (await open("select=laws:cells.channel.kir2p1_mh2@1")) && (await state()).selected === "laws:cells.channel.kir2p1_mh2@1" && (await state()).lens === "laws", JSON.stringify(await state()));
    await shot(`${NAME}-select`);
    check("and so it does from lens=engine", (await open("lens=engine&select=laws:cells.model.resolved_pump_tissue@3")) && (await state()).lens === "laws" && (await state()).selected === "laws:cells.model.resolved_pump_tissue@3", JSON.stringify(await state()));
    check("#laws in the address opens it too", (await open("x=1#laws")) && (await state()).lens === "laws");
    // Either spelling of a declared ID opens the one piece (the manifest's ID rule).
    await open("select=laws:cells.channel.kv1p5_mh@1");
    check("select=laws:cells.channel.kv1p5_mh@1 opens cells.channel.kv1p5_mh@1, the spelling it is declared with", (await evaluate(`${L}.selected`)) === "laws:cells.channel.kv1p5_mh@1" && /cells.channel.kv1p5_mh@1/.test((await state()).panel), String(await evaluate(`${L}.selected`)));
    // An old link in the other spelling: its piece is chosen, and the camera goes to it as for its own spelling.
    await open("lens=laws");
    const home = await state();
    await open("select=laws:cells.cycle.atp_driven_transporter_mass_action_positive@1");
    await until(`!${V}.stage.rig.flight`, 240);
    const there = await state();
    check("an old link in the other spelling chooses its piece, and the camera goes to it", (await evaluate(`${L}.selected`)) === "laws:cells.cycle.atp_driven_transporter_mass_action_positive@1" && (there.distance < home.distance - 1 || there.target.join() !== home.target.join()), JSON.stringify([home.distance, there.distance, home.target, there.target]));
    // An address naming what the wall does not show: the library opens and says so plainly.
    const said = {
      // A legacy model ID: the manifest's own words for what it is.
      "cells.model.resolved_tissue@1": (text) => /Legacy code; not shown/.test(text) && /The engine's declarations list cells.model.resolved_tissue@1 among the older model families: legacy code, to be dropped, with no page of its own\./.test(text),
      // IDs the manifest does not list at all, an old piece and an old model family among them: never called legacy.
      "assembly_regulated_cell@1": (text) => /Not declared/.test(text) && /The engine's declarations do not list assembly_regulated_cell@1: no active registry declares it/.test(text) && !/legacy/.test(text),
      "cells.channel.cav1p2_m2h@1": (text) => /The engine's declarations do not list cells.channel.cav1p2_m2h@1/.test(text),
    };
    for (const [id, says] of Object.entries(said)) {
      await open(`select=laws:${id}`);
      const s = await state();
      check(`select=laws:${id} opens the library and says plainly it is not shown`, s.lens === "laws" && s.selected === `laws:${id}` && says(s.panel) && (await evaluate(`${L}.litSlots.mesh.count + ${L}.litBars.mesh.count`)) === 0, s.panel.slice(0, 260));
    }
    await shot(`${NAME}-not-shown`);
    // A model family with no rows: its own panel, its case lit.
    await open("select=laws:cells.model.apical_vertex_mechanics@1");
    const family = await state();
    const lit = await evaluate(`${L}.litSlots.mesh.count`);
    check("select=laws:cells.model.apical_vertex_mechanics@1 opens a model family's panel, its case lit", family.selected === "laws:cells.model.apical_vertex_mechanics@1" && /A model family with no rows/.test(family.panel) && /its laws are tables inside it/.test(family.panel) && lit === 1, JSON.stringify([family.panel.slice(0, 200), lit]));
    // The fuel kind: a row of the inner model with no piece of its own; its socket lit, and the cycle laws that run on it.
    await open("select=laws:cells.fuel_kind.maintained_chemical_reservoirs@1");
    const fuel = await state();
    check("select=laws:cells.fuel_kind.maintained_chemical_reservoirs@1 opens the inner model's row with no piece, its socket lit", /A row of cells.model.resolved_pump_tissue@3 · fuel kind/.test(fuel.panel) && /cells.cycle.nak_atp_mass_action_positive@1/.test(fuel.panel) && (await evaluate(`${L}.litSlots.mesh.count`)) === 1, fuel.panel.slice(0, 200));
    // A piece links where it is declared at the manifest's revision, and the words beside the link say so where the map's is another.
    await open("select=laws:cells.channel.kv1p5_mh@1");
    const links = await evaluate(`[...${V}.shadowRoot.querySelectorAll("cells-panel .sources li")].map((item) => ({ href: item.querySelector("a")?.href || null, text: item.textContent }))`);
    const meta = await evaluate(`${V}.model.meta`);
    const declared = links.find((link) => link.text.startsWith(fileOf("cells.channel.kv1p5_mh@1")) && new RegExp(`line ${lineOf("cells.channel.kv1p5_mh@1")}(?!\\d)`).test(link.text));
    const other = !meta.source_base_url.includes(MANIFEST.revision);
    check("a piece links the file it is declared in at the manifest's revision, with its line, and says so where the map's is another", Boolean(declared?.href?.includes(`/blob/${MANIFEST.revision}/${fileOf("cells.channel.kv1p5_mh@1")}`)) && (!other || new RegExp(`as declared at main ${MANIFEST.revision.slice(0, 8)}`).test(declared.text)) && links.every((link) => link.href?.includes(`/blob/${MANIFEST.revision}/`)), JSON.stringify([links, meta.revision]));
    // A unit of the Protein atlas: a door onto its declared law, and words with no door for a law the manifest does not list.
    await open("select=unit.U09");
    let unit = await state();
    const unitDoors = await evaluate(`[...${V}.shadowRoot.querySelectorAll("cells-panel .panel-door")].map((door) => ({ text: door.textContent, button: Boolean(door.querySelector("button")) }))`);
    check("a unit's panel has a door onto its declared law, and says of each other law that no active model declares it, with no door", unitDoors.some((door) => door.button && /^Explore cells.channel.kv1p5_mh@1 in the Laws atlas/.test(door.text)) && unitDoors.filter((door) => !door.button).length === 1 && /^No active model declares these laws of this unit: cells.channel.kv1p5_ml_dynamic_m@1, cells.channel.kv1p5s_ml_slow_dynamic_m@1\./.test(unitDoors.find((door) => !door.button).text), JSON.stringify([unit.lens, unitDoors]));
    await shot(`${NAME}-unit-doors`);
    const unitDoor = await placeOf(`[...root.querySelectorAll("cells-panel .panel-door button")].find((button) => /^Explore cells.channel.kv1p5_mh@1 in the Laws atlas/.test(button.textContent))`);
    if (unitDoor) await click(unitDoor.x, unitDoor.y, 2200);
    unit = await state();
    check("the unit's door opens the library on that law, chosen", unit.lens === "laws" && (await evaluate(`${L}.selected`)) === "laws:cells.channel.kv1p5_mh@1" && /cells.channel.kv1p5_mh@1/.test(unit.panel), JSON.stringify([unit.lens, unit.selected]));
    // A unit of each mark of the law-port inventory: its law, a colon, and that mark's words, in one line that opens nothing.
    check(`a unit whose every law the law-port table marks "port as is", none of them declared, is found (${PORT_AS_IS?.join(" ")})`, Boolean(PORT_AS_IS));
    for (const [id, law] of [...(PORT_AS_IS ? [PORT_AS_IS] : []), ["U42", "ncx_3na_1ca_symmetric_barrier@1"], ["U47", "mitochondrial_passive_continuous_si@1"], ["U37", "junction_flux() in the nominal profile"]]) {
      const row = PORT.rows.find((item) => item.units.includes(id) && (item.has_id ? item.law === law : true));
      await open(`select=unit.${id}`);
      const doors = await evaluate(`[...${V}.shadowRoot.querySelectorAll("cells-panel .panel-door")].map((door) => ({ text: door.textContent, button: Boolean(door.querySelector("button")) }))`);
      const words = doors.filter((door) => !door.button);
      check(`unit.${id}: one line, ${law} and the words for "${row?.mark}", and no door into the Laws library`, Boolean(row) && words.length === 1 && words[0].text.trim().startsWith(law) && words[0].text.trim().endsWith(`: ${phraseOf(row)}`) && !doors.some((door) => door.button && /Laws library/.test(door.text)), JSON.stringify(doors));
      await evaluate(`${V}.shadowRoot.querySelector("cells-panel .panel-door.quiet")?.scrollIntoView({ block: "center" })`);
      await sleep(300);
      await shot(`${NAME}-unit-${id}`);
    }
    // A law the table marks that the manifest now declares is a door, whatever the table says (schema/LAWS_LIBRARY.md).
    if (PORT_DECLARED) {
      const id = PORT_DECLARED.units[0];
      await open(`select=unit.${id}`);
      const doors = await evaluate(`[...${V}.shadowRoot.querySelectorAll("cells-panel .panel-door")].map((door) => ({ text: door.textContent, button: Boolean(door.querySelector("button")) }))`);
      check(`unit.${id}: ${PORT_DECLARED.law}, which the table marks "${PORT_DECLARED.mark}" and the manifest declares, opens its door, and the mark's words are not said`, doors.some((door) => door.button && new RegExp(`^Explore ${literally(currentID(PORT_DECLARED.law))} in the Laws atlas`).test(door.text.trim())) && !doors.some((door) => !door.button && door.text.includes(PORT_DECLARED.law)), JSON.stringify(doors));
      await shot(`${NAME}-unit-${id}-declared`);
    }
    // What the view leaves behind: the Cell view opened after it is as the Cell view opened alone.
    const look = () => evaluate(`(() => { const v = ${V}, st = v.stage, r = st.renderer; return { sun: st.sun.position.toArray().map((x) => +x.toFixed(3)), shadow: st.sun.castShadow, limits: { ...st.rig.limits }, environment: Boolean(st.scene.environment), exposure: +r.toneMappingExposure.toFixed(3), toneMapping: r.toneMapping, bloom: st.finish?.bloom?.strength ?? 0, insets: st.insets || {}, sky: +st.sky.intensity.toFixed(3) }; })()`);
    await open("lens=cell");
    const alone = await look();
    await open("lens=laws");
    await evaluate(`${V}.setLens("cell", true)`);
    await sleep(2500);
    const after = await look();
    check("the Cell view opened after the library is as it is opened alone: light, shade, bloom, limits and insets", JSON.stringify(after) === JSON.stringify(alone), JSON.stringify([alone, after]));
  } else if (CASE === "text") {
    // Where no 3D can be drawn, the page gives the same content as text: the library's list and panel too.
    check("the page opens on lens=laws without 3D", await open("lens=laws"));
    const said = await evaluate(`${V}.shadowRoot.querySelector(".fallback")?.textContent || ""`);
    check("it says that 3D is not available", /3D drawing is not available/.test(said), said);
    const listed = await evaluate(`${V}.sections().map((section) => [section.label, section.entities.length])`);
    check("the list holds the library's families, models, cases and what it does not show", listed.length >= 15 && listed.some(([label, n]) => label === "Models" && n === RACKS) && listed.some(([label, n]) => label === "Model families with no rows" && n === CASES) && listed.some(([label, n]) => label.startsWith("Not shown") && n === MANIFEST.legacy.length), JSON.stringify(listed.slice(-4)));
    await evaluate(`${V}.select("laws:cells.channel.kir2p1_mh2@1")`);
    await sleep(800);
    const s = await state().catch(() => null);
    const panel = await evaluate(`(() => { const p = ${V}.shadowRoot.querySelector("cells-panel"); return p && !p.hidden ? p.textContent : ""; })()`);
    check("a piece chosen from the list has its panel, with no level stated", /not stated: the engine's declarations give no level for it/.test(panel), panel.slice(0, 120));
  } else if (CASE === "phone") {
    check("the page opens on lens=laws", await open("lens=laws"));
    // Six tabs may not all fit a narrow phone: the row then scrolls inside the bar, and the tab of the view shown is in sight (viewer.js showPressedTab).
    const fit = await evaluate(`(() => { const root = ${V}.shadowRoot, box = root.querySelector(".switch"), buttons = [...box.querySelectorAll("button")]; const r = box.getBoundingClientRect(), pressed = box.querySelector('[aria-pressed="true"]').getBoundingClientRect(); return { count: buttons.length, scroll: box.scrollWidth - box.clientWidth, left: r.left, right: r.right, seen: pressed.left >= r.left - 0.5 && pressed.right <= r.right + 0.5, page: document.documentElement.scrollWidth - document.documentElement.clientWidth, words: buttons.map((b) => b.textContent) }; })()`);
    check(`the six views' switch fits a ${WIDTH} px phone, the library's tab in sight`, fit.count === 6 && fit.left >= 0 && fit.right <= WIDTH && fit.seen && fit.page <= 0, JSON.stringify(fit));
    let s = await state();
    check("no room is kept on the left on a phone", !s.insets.left, JSON.stringify(s.insets));
    // The phone's second pass (17 November 2026): the bar on one row, every switch of it at least 44 px; the library's card
    // folded to one line under the bar, so that the wall is the picture; a real press opens the card with its search, and folds it.
    const phone = () =>
      evaluate(`(() => {
        const root = ${V}.shadowRoot, shown = (el) => Boolean(el) && el.getClientRects().length > 0, edges = (el) => { const r = el.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom].map(Math.round); };
        const kids = [...root.querySelector(".bar").children].filter(shown).map((el) => el.getBoundingClientRect()).filter((r) => r.width > 1); // the page's name put out of sight is 1 px
        const presses = [...root.querySelectorAll(".bar button")].filter(shown).map((el) => { const r = el.getBoundingClientRect(); return Math.round(Math.min(r.width, r.height)); });
        const toggle = root.querySelector(".view-toggle"), card = root.querySelector(".view");
        return { barRow: kids.every((a) => kids.every((b) => a.top < b.bottom - 1 && b.top < a.bottom - 1)), least: Math.min(...presses), squeeze: root.querySelector(".bar").dataset.squeeze || "",
          toggle: shown(toggle) ? { box: edges(toggle), says: toggle.textContent, expanded: toggle.getAttribute("aria-expanded") } : null, card: shown(card) ? edges(card) : null, find: shown(root.querySelector("#cells-find")) };
      })()`);
    let p = await phone();
    check(`on a ${WIDTH} px phone the bar stands on one row, each of its buttons at least 44 px`, p.barRow && p.least >= 44, JSON.stringify(p));
    check("the library's card is folded to one line under the bar, at least 44 px tall, naming the library", Boolean(p.toggle) && p.card === null && p.toggle.box[3] - p.toggle.box[1] >= 44 && /Laws library/.test(p.toggle.says) && p.toggle.expanded === "false", JSON.stringify(p));
    const fold = await placeOf(`root.querySelector(".view-toggle")`);
    if (fold) await click(fold.x, fold.y, 600);
    p = await phone();
    check("a real press opens the card under its line, with its search", Boolean(fold) && Boolean(p.card) && p.toggle.expanded === "true" && p.card[1] >= p.toggle.box[3] && p.find, JSON.stringify(p));
    if (fold) await click(fold.x, fold.y, 600);
    p = await phone();
    check("and a real press on the line folds it again", p.card === null && p.toggle?.expanded === "false", JSON.stringify(p));
    // A piece named in the address on a phone: the room is laid out again for the tall screen after the piece was chosen,
    // and the piece is framed in the new room, in the picture above the panel's sheet (17 November 2026: it stood far above the screen).
    check("select=laws:<id> opens the library on a phone, with the piece chosen", (await open("select=laws:cells.channel.kir2p1_mh2@1")) && (await state()).selected === "laws:cells.channel.kir2p1_mh2@1");
    await sleep(2200);
    const named = await barAt("cells.channel.kir2p1_mh2@1");
    const sheet = await evaluate(`(() => { const p = ${V}.shadowRoot.querySelector("cells-panel"); const r = p && !p.hidden ? p.getBoundingClientRect() : null; return r && r.height ? Math.round(r.top) : ${HEIGHT}; })()`);
    check("the piece named in the address stands in the picture, between the bar and the panel", Boolean(named) && named.x >= 0 && named.x <= WIDTH && named.y >= 56 && named.y <= sheet, JSON.stringify([named, sheet]));
    await shot(`${NAME}-named`);
    await shot(`${NAME}-rest`);
    await evaluate(`${V}.select("laws:cells.cycle.nak_atp_mass_action_positive@1", { fly: true })`);
    await sleep(2000);
    s = await state();
    check("a piece chosen opens the panel as a sheet, and the picture keeps room above it", s.selected === "laws:cells.cycle.nak_atp_mass_action_positive@1" && s.insets.bottom > 0 && !s.insets.left, JSON.stringify(s.insets));
    await shot(`${NAME}-piece`);
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
  console.error(`check_laws: ${failed.stack || failed}`);
  process.exit(2);
}
const passed = results.filter(Boolean).length;
console.log(`${passed} of ${results.length} checks passed`);
process.exit(passed === results.length ? 0 : 1);
