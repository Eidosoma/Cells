#!/usr/bin/env node
// Checks the Laws library on the map's page (schema/LAWS_LIBRARY.md) with real pointer and key
// input, through the DevTools protocol, in the manner of tools/check_machine.mjs:
//
//   main     lens=laws opens the fifth view, its room clear of the cards on the left; a real press
//            on a piece's bar chooses it, and the panel says "No level recorded for this piece"; ]
//            steps to the next piece and Escape lets go; typing in the card's search field finds
//            pieces and the field keeps its focus; the card's Family control goes to a family; the
//            panel's link to the piece's Engine view box opens the Engine view on that box, and the
//            box's door ("Show its N pieces in the Laws library") opens the library with them
//            picked out, and the card's Close lets them go; a lost WebGL context, and a lost GPU
//            process, leave the names written on the room as they were.
//   address  select=laws:<id> with no lens opens the library on that piece; so does it from
//            lens=engine.
//   phone    on a 360 px phone the five views' switch fits the bar; the library opens on its wall,
//            a piece chosen opens the panel as a sheet, and no room is kept on the left.
//   text     with no 3D (WebGL switched off), the page says so, and the List gives the library's
//            families and frames, and a piece's panel.
//
// The address case also opens the Cell view after the library and holds it to the Cell view
// opened alone: what the library sets on the stage (light, shade, bloom, limits, insets) is not
// left behind.
//
//   node tools/check_laws.mjs [OUT_DIR]
//
// Set by the environment: CASE (main, address or phone; main unless set), THEME (dark), NAME
// (what the pictures are called in OUT_DIR). One browser at a time: it takes the lock in
// tools/lib/browser_lock.mjs.

import { spawn } from "node:child_process";
import { writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { createServer } from "./serve.mjs";
import { acquireBrowser } from "./lib/browser_lock.mjs";
import { DEFAULT_RUNS, DEFAULT_SCENE } from "./lib/build_page.mjs";

const outDir = process.argv[2] ? path.resolve(process.argv[2]) : null;
if (outDir) await mkdir(outDir, { recursive: true });
const CASE = process.env.CASE || "main";
const PHONE = CASE === "phone";
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
    await page("Page.navigate", { url: `${base}?${query}` });
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

  if (CASE === "main") {
    // ---------------------------------------------------------- the fifth view, with its room clear of the cards
    check("the page opens on lens=laws", await open("lens=laws"));
    let s = await state();
    check("the switch offers five views, the Laws library pressed", s.views.length === 5 && s.views.find((view) => view.id === "laws")?.pressed === "true", JSON.stringify(s.views));
    const card = await evaluate(`(() => { const r = ${V}.shadowRoot.querySelector("#cells-view").getBoundingClientRect(); return { right: r.right, hidden: ${V}.shadowRoot.querySelector("#cells-view").hidden }; })()`);
    check("the room is kept clear of the view card on the left (a left inset)", s.insets.left > 0 && Math.abs(s.insets.left - (card.right + 12)) < 30, JSON.stringify([s.insets, card]));
    const corners = await evaluate(`(() => { const v = ${V}, l = v.current, b = l.layout.bounds, w = l.layout.wall; const r = v.canvas.getBoundingClientRect(); const xs = []; for (const x of [b.minX, b.maxX]) for (const y of [0, w.y + w.h]) { const p = new v.stage.camera.position.constructor(x, y, b.maxZ); v.stage.project(p, p); xs.push(r.left + p.x); } return { min: Math.min(...xs), max: Math.max(...xs) }; })()`);
    check("and the room stands right of the card, nothing cut", corners.min >= card.right - 4 && corners.max <= WIDTH + 2, JSON.stringify([corners, card.right]));
    check("the names are written on the room", (await inked()) > 1000);
    const rest = s;
    await shot(`${NAME}-rest`);

    // ---------------------------------------------------------- a real press on a bar
    const id = "nak_atp_mass_action_positive@1";
    const at = await barAt(id);
    await click(at.x, at.y, 1500);
    s = await state();
    check("a real press on a piece's bar chooses it", s.selected === `laws:${id}`, String(s.selected));
    check("its panel says no level is recorded for the piece, and its box's status as the box's", /No level recorded for this piece/.test(s.panel) && /a status of the box, not of the piece/.test(s.panel), s.panel.slice(0, 160));
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
    await evaluate(`(() => { const select = ${V}.shadowRoot.querySelector("#cells-mark"); select.value = "operators"; select.dispatchEvent(new Event("change", { bubbles: true })); })()`);
    // In software a frame of this view takes a while: the flight is waited for until it lands.
    const flew = await evaluate(`Boolean(${V}.stage.rig.flight)`);
    const landed = await until(`!${V}.stage.rig.flight`, 240);
    note(`the Family control's flight: started ${flew}, landed ${landed}`);
    s = await state();
    check("the card's Family control chooses a family, and the camera goes to its column", s.filter.family === "operators" && (s.distance < before.distance - 1 || s.target.join() !== before.target.join()), JSON.stringify([s.filter.family, before.distance, s.distance]));
    await evaluate(`(() => { const select = ${V}.shadowRoot.querySelector("#cells-mark"); select.value = "all"; select.dispatchEvent(new Event("change", { bubbles: true })); })()`);
    await sleep(1200);

    // ---------------------------------------------------------- the way back to the Engine view, and the door from it
    await evaluate(`${V}.select("laws:${id}", { fly: true })`);
    await sleep(1500);
    const back = await placeOf(`[...root.querySelectorAll("cells-panel .panel-list")].find((list) => list.querySelector("h4")?.textContent.startsWith("On the Engine view"))?.querySelector(".link-button")`);
    check("the panel's link to the piece's box can be pressed", Boolean(back));
    if (back) await click(back.x, back.y, 1800);
    s = await state();
    check("it opens the Engine view on the box that holds the piece's file", s.lens === "engine" && s.selected === "laws.pumps", JSON.stringify([s.lens, s.selected]));
    const words = await evaluate(`[...${V}.shadowRoot.querySelectorAll("cells-panel .panel-door button")].map((button) => button.textContent)`);
    const doorWords = words.find((text) => /in the Laws library/.test(text));
    check("the box's panel has a door into the Laws library, with the list's count", /Show its 4 pieces in the Laws library/.test(doorWords || ""), JSON.stringify(words));
    await shot(`${NAME}-engine-box`);
    const door = await placeOf(`[...root.querySelectorAll("cells-panel .panel-door button")].find((button) => /in the Laws library/.test(button.textContent))`);
    if (door) await click(door.x, door.y, 2000);
    s = await state();
    check("the door opens the library with the box's pieces picked out", s.lens === "laws" && s.filter.box === "laws.pumps" && (await evaluate(`${L}.order().length`)) === 4, JSON.stringify([s.lens, s.filter]));
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
  } else if (CASE === "address") {
    check("select=laws:<id> with no lens opens the library on that piece", (await open("select=laws:kir2p1_mh2@1")) && (await state()).selected === "laws:kir2p1_mh2@1" && (await state()).lens === "laws", JSON.stringify(await state()));
    await shot(`${NAME}-select`);
    check("and so it does from lens=engine", (await open("lens=engine&select=laws:resolved_pump_tissue@3")) && (await state()).lens === "laws" && (await state()).selected === "laws:resolved_pump_tissue@3", JSON.stringify(await state()));
    check("#laws in the address opens it too", (await open("x=1#laws")) && (await state()).lens === "laws");
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
    check("the list holds the library's families, frames and older families", listed.length >= 15 && listed.some(([label, n]) => label === "Frames" && n === 5), JSON.stringify(listed.slice(0, 4)));
    await evaluate(`${V}.select("laws:kir2p1_mh2@1")`);
    await sleep(800);
    const s = await state().catch(() => null);
    const panel = await evaluate(`(() => { const p = ${V}.shadowRoot.querySelector("cells-panel"); return p && !p.hidden ? p.textContent : ""; })()`);
    check("a piece chosen from the list has its panel, with no level recorded", /No level recorded for this piece/.test(panel), panel.slice(0, 120));
  } else if (CASE === "phone") {
    check("the page opens on lens=laws", await open("lens=laws"));
    const fit = await evaluate(`(() => { const root = ${V}.shadowRoot, box = root.querySelector(".switch"), buttons = [...box.querySelectorAll("button")]; const r = box.getBoundingClientRect(); return { count: buttons.length, scroll: box.scrollWidth - box.clientWidth, left: Math.min(...buttons.map((b) => b.getBoundingClientRect().left)), right: Math.max(...buttons.map((b) => b.getBoundingClientRect().right)), page: document.documentElement.scrollWidth - document.documentElement.clientWidth, words: buttons.map((b) => b.textContent) }; })()`);
    check(`the five views' switch fits a ${WIDTH} px phone`, fit.count === 5 && fit.scroll <= 0 && fit.left >= 0 && fit.right <= WIDTH && fit.page <= 0, JSON.stringify(fit));
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
    check("select=laws:<id> opens the library on a phone, with the piece chosen", (await open("select=laws:kir2p1_mh2@1")) && (await state()).selected === "laws:kir2p1_mh2@1");
    await sleep(2200);
    const named = await barAt("kir2p1_mh2@1");
    const sheet = await evaluate(`(() => { const p = ${V}.shadowRoot.querySelector("cells-panel"); const r = p && !p.hidden ? p.getBoundingClientRect() : null; return r && r.height ? Math.round(r.top) : ${HEIGHT}; })()`);
    check("the piece named in the address stands in the picture, between the bar and the panel", Boolean(named) && named.x >= 0 && named.x <= WIDTH && named.y >= 56 && named.y <= sheet, JSON.stringify([named, sheet]));
    await shot(`${NAME}-named`);
    await shot(`${NAME}-rest`);
    await evaluate(`${V}.select("laws:nak_atp_mass_action_positive@1", { fly: true })`);
    await sleep(2000);
    s = await state();
    check("a piece chosen opens the panel as a sheet, and the picture keeps room above it", s.selected === "laws:nak_atp_mass_action_positive@1" && s.insets.bottom > 0 && !s.insets.left, JSON.stringify(s.insets));
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
