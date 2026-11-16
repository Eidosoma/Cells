#!/usr/bin/env node
// Checks the resting look of the Cell view (src/core/look.js) with real pointer input,
// through the DevTools protocol, in the manner of tools/check_shelves.mjs: that the Cell
// view wears the seven effects and the other views do not, that the switch by the scale
// bar gives the look as it was, that a device which cannot keep up gives up contact shade
// first and says so, that decoration stands still for reduced motion and when it is held,
// that bloom is off at rest and shines only from what was marked, and that the readout for
// judging on a device switches each effect.
//
//   node tools/check_look.mjs [SCENARIO] [OUT_DIR]
//
// Each scenario is one short hold of the one browser (tools/lib/browser_lock.mjs), with one
// load of the page. Several may be named, with commas between, to share one hold where the
// browser is much in demand (look,switch):
//   look      the seven effects, the page's words, contact shade, bloom, what a frame costs here (the default)
//   switch    the word in the address, the switch pressed, the fallback, status colours
//   views     to scale, close to the membrane, the other views, a small species, a phone
//   motion    decoration: its clock, held from outside, and reduced motion
//   trial     the readout behind "fps=1"
//   pictures  for looking, not a check: one load, then one picture for each step that the
//             file named by STEPS lists as JSON, [{ name, run, size: [width, height, pixel ratio], clip: [x, y, width, height] }];
//             QUERY is the address's words, WIDTH and HEIGHT the window, MOTION=1 lets it move,
//             JPEG=1 writes smaller pictures
// With OUT_DIR a scenario also writes pictures of what it saw.
//
// The server here draws in software: nothing this check measures says how fast a graphics
// card draws the look. It never waits on a frame rate. Where it compares two pictures, the
// page is held still (it asks for reduced motion), so that they differ only by what was changed.

import { spawn } from "node:child_process";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { createServer } from "./serve.mjs";
import { acquireBrowser } from "./lib/browser_lock.mjs";
import { DEFAULT_SCENE } from "./lib/build_page.mjs";

const scenarios = (process.argv[2] || "look").split(",");
const outDir = process.argv[3] ? path.resolve(process.argv[3]) : null;
const unknown = scenarios.find((name) => !["look", "switch", "views", "motion", "trial", "pictures"].includes(name));
if (unknown !== undefined) {
  console.error(`unknown scenario "${unknown}": look, switch, views, motion, trial or pictures`);
  process.exit(2);
}
const looking = scenarios.includes("pictures");
if (outDir) await mkdir(outDir, { recursive: true });

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const results = [];
const check = (name, ok, detail = "") => {
  results.push(Boolean(ok));
  console.log(`${ok ? "pass" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`);
};
const note = (text) => console.log(`note  ${text}`);
const started = Date.now();
const pageLog = [];
const release = await acquireBrowser({ wait: 3 * 60 * 60 * 1000 });
const held = Date.now();
const server = createServer({ offline: true, scene: process.env.CHECK_SCENE || DEFAULT_SCENE, log: (line) => pageLog.push(line) });
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}/`;
// A check's window is small, since each picture is drawn in software; it is still wide enough for
// the labels' columns, and for the species switch to stand in the bar and not in the view's card.
const WIDTH = Number(process.env.WIDTH || (looking ? 1440 : 1040)), HEIGHT = Number(process.env.HEIGHT || (looking ? 900 : 640));
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
  setTimeout(() => reject(new Error("Chrome did not report a DevTools address")), 120000);
});
const socket = new WebSocket(endpoint);
await new Promise((resolve, reject) => {
  socket.onopen = resolve;
  socket.onerror = reject;
});
let nextId = 1;
const waiting = new Map();
// What the page's own console calls an error: a shader that does not compile is said there, and nowhere else.
const consoleErrors = [];
socket.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (message.method === "Runtime.consoleAPICalled" && message.params.type === "error") consoleErrors.push(message.params.args.map((arg) => arg.value ?? arg.description ?? "").join(" ").slice(0, 600));
  if (message.method === "Runtime.exceptionThrown") consoleErrors.push(String(message.params.exceptionDetails?.exception?.description || message.params.exceptionDetails?.text).slice(0, 600));
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
await page("Runtime.enable");
await page("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: HEIGHT, deviceScaleFactor: 1, mobile: false });
const evaluate = async (expression) => {
  const reply = await page("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (reply.exceptionDetails) throw new Error(reply.exceptionDetails.exception?.description || reply.exceptionDetails.text);
  return reply.result.value;
};
const V = "document.querySelector('cells-viewer')";
const S = `${V}.stage`;
/** Whether the page asks for less motion. Asked before a load, the page starts still: nothing in it moves by itself. */
const lessMotion = (on) => page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: on ? "reduce" : "no-preference" }] });

/** The view holds still: three looks in a row with the camera and the stage where they were (at most a minute). */
const rest = async () => {
  let before = null, same = 0;
  for (let tries = 0; tries < 240 && same < 3; tries++) {
    const now = await evaluate(`(() => { const s = ${S}, c = s.camera; return JSON.stringify([c.position.toArray(), c.quaternion.toArray(), s.width, s.height].flat().map((n) => Math.round(n * 1000) / 1000)); })()`).catch(() => null);
    same = now !== null && now === before ? same + 1 : 0;
    before = now;
    await sleep(250);
  }
};
/** Open the page and wait until the view asked for is drawn and holds still. The machine may be busy: it waits long. */
const open = async (query) => {
  await page("Page.navigate", { url: `${base}?${query}&still=1` });
  let drawn = false;
  for (let tries = 0; tries < 2400 && !drawn; tries++) {
    await sleep(250);
    drawn = await evaluate(`Boolean(${V} && ${V}.current && ${S} && ${V}.current.active !== false)`).catch(() => false);
  }
  if (!drawn) throw new Error("the page did not draw its view within ten minutes");
  await evaluate(`Promise.resolve(${V}.current.ready)`);
  // The page's letters come over the network. Until they are there a wider stand-in is shown, and
  // cards and labels have other sizes: a picture waits for them (up to a minute and a half).
  if (outDir) {
    let lettered = false;
    for (let tries = 0; tries < 360 && !lettered; tries++) {
      lettered = await evaluate(`document.fonts.status === "loaded" && ["Inter", "Space Grotesk"].every((family) => [...document.fonts].some((face) => face.family.includes(family) && face.status === "loaded"))`).catch(() => false);
      if (!lettered) await sleep(250);
    }
    if (lettered) await evaluate(`(() => { ${V}.labels?.measure(); ${V}.renderChrome(); ${S}.invalidate(); })()`);
    else note("the page's own fonts did not arrive: cards and labels in the pictures are not the sizes a visitor sees");
  }
  await rest();
  await sleep(400);
};
const mouse = (type, x, y, extra = {}) => page("Input.dispatchMouseEvent", { type, x, y, button: "left", buttons: 1, clickCount: 1, ...extra });
const click = async (x, y, wait = 500) => {
  await mouse("mouseMoved", x, y, { button: "none", buttons: 0 });
  await mouse("mousePressed", x, y);
  await mouse("mouseReleased", x, y, { buttons: 0 });
  await sleep(wait);
};
/** The middle of something on the page, found by a script that is given the viewer's own root. */
const middle = (find) => evaluate(`(() => { const el = (${find})(${V}.shadowRoot); if (!el) return null; el.scrollIntoView({ block: "nearest" }); const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
const press = async (find, what, wait = 600) => {
  const at = await middle(find);
  if (!at) throw new Error(`nothing to press: ${what}`);
  await click(at.x, at.y, wait);
};
// A button of a row of buttons, by the row's name and the button's words: on the view's card, or by the scale bar.
const button = (row, words) => `(root) => [...[...root.querySelectorAll(".seg-row")].find((item) => item.querySelector(".seg-label")?.textContent === ${JSON.stringify(row)})?.querySelectorAll("button") || []].find((item) => item.textContent === ${JSON.stringify(words)})`;
/** One more frame drawn and shown, labels and all. */
const frame = () => evaluate(`new Promise((done) => { ${S}.invalidate(); requestAnimationFrame(() => requestAnimationFrame(() => done(true))); })`);
const shot = async (name, clip = null) => {
  if (!outDir) return;
  await frame();
  const small = Boolean(process.env.JPEG);
  const { data } = await page("Page.captureScreenshot", { format: small ? "jpeg" : "png", ...(small ? { quality: 88 } : {}), ...(clip ? { clip: { x: clip[0], y: clip[1], width: clip[2], height: clip[3], scale: 1 } } : {}) });
  const file = path.join(outDir, `${name}.${small ? "jpg" : "png"}`);
  await writeFile(file, Buffer.from(data, "base64"));
  note(`wrote ${file}`);
};

// The look as the page itself has it: written to run in the page, so that it can be read in the same breath as a change.
const STATE = `(() => {
  const v = ${V}, s = v.stage, look = s.look, root = v.shadowRoot, finish = s.finish, lens = v.current;
  const rows = (box) => [...(box?.querySelectorAll(".seg-row") || [])].map((row) => row.querySelector(".seg-label").textContent + ": " + [...row.querySelectorAll("button")].map((b) => b.textContent + (b.getAttribute("aria-pressed") === "true" ? "*" : "")).join(" | "));
  const box = root.querySelector(".look-box");
  return {
    lens: v.state.lens, rich: look.rich, choice: look.choice, held: look.held, step: look.step, drawn: look.drawn(), contact: look.contact,
    tone: s.renderer.toneMapping, exposure: s.renderer.toneMappingExposure,
    numbers: Object.fromEntries(Object.entries(s.numbers).filter(([name]) => name !== "time").map(([name, item]) => [name, item.value])),
    passes: Boolean(finish?.active), contactSize: finish?.contact.size ?? 0, picture: finish?.contact.picture ? [finish.contact.picture.width, finish.contact.picture.height] : null,
    bloom: finish?.bloom.strength ?? 0, studio: Boolean(lens.studio) && s.scene.environment === lens.studio, plainRoom: Boolean(lens.environment) && s.scene.environment === lens.environment,
    reach: s.fit.reach, unit: lens.u ?? null, filmicFits: s.fit.filmic, width: s.width, height: s.height,
    box: box && !box.hidden && box.getClientRects().length ? rows(box) : null,
    notes: box && !box.hidden ? [...box.querySelectorAll(".look-note")].map((p) => p.textContent) : [],
    card: rows(root.querySelector(".view.card")),
    legend: root.querySelector("cells-legend .legend-note")?.textContent ?? null,
    callouts: [...root.querySelectorAll(".label.is-callout:not(.is-off)")].length,
    still: s.decoration.still, moving: s.decoration.moving, clock: s.decoration.time, shared: s.numbers.time.value,
  };
})()`;
const state = () => evaluate(STATE);
/**
 * Draw the picture once as it stands and add up what is on the canvas: how bright, and how
 * much of it is covered. `prepare` is run first in the page, with the viewer as v and the
 * stage as s. Meant for a page that holds still.
 */
const picture = (prepare = "") =>
  evaluate(`(() => {
    const v = ${V}, s = v.stage, gl = s.renderer.getContext();
    ${prepare}
    s.draw();
    const w = gl.drawingBufferWidth, h = gl.drawingBufferHeight, data = new Uint8Array(w * h * 4);
    gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, data);
    let light = 0, cover = 0, lit = 0;
    for (let i = 0; i < data.length; i += 4) { light += data[i] + data[i + 1] + data[i + 2]; cover += data[i + 3]; if (data[i + 3] > 0) lit += 1; }
    return { light, cover, lit, pixels: w * h };
  })()`);
/**
 * Tell the look of so many windows of frames, each frame this long, as a device would: in
 * one breath, with the look free to step down for that while and held again after, so that
 * the frames this slow server really draws have no say. Returns how often it stepped, and
 * the look as the page then shows it.
 */
const feed = (milliseconds, windows = 1) =>
  evaluate(`(() => {
    const v = ${V}, look = v.stage.look;
    look.held = false;
    let stepped = 0;
    for (let i = 0; i < 30 + 45 * ${windows}; i++) if (look.frame(${milliseconds})) stepped += 1;
    v.renderChrome();
    const seen = ${STATE};
    look.held = true;
    return { stepped, ...seen };
  })()`);
/** How long one picture takes to draw here, in milliseconds: the mean of a few, each waited for (the first is not counted: shaders compile). */
const timed = (prepare = "", count = 2) =>
  evaluate(`(() => {
    const v = ${V}, s = v.stage, gl = s.renderer.getContext(), one = new Uint8Array(4);
    ${prepare}
    const draw = () => { s.draw(); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, one); };
    draw();
    const from = performance.now();
    for (let i = 0; i < ${count}; i++) draw();
    return Math.round((performance.now() - from) / ${count});
  })()`);
const SEVEN = "reflections,filmic,translucency,contact,texture,drift,shimmer";
/**
 * Two pictures of a page that holds still, by the light added up over the canvas. The software
 * renderer draws the same picture to the last count, and is held to that. A graphics card does
 * not: the same still page drawn twice differed by 2 to 4 counts in 70 million there (an NVIDIA
 * L4, 16 November 2026), so on a card two pictures are the same within one part in a million.
 */
let exact = true;
const same = (a, b) => (exact ? a === b : Math.abs(a - b) <= Math.max(a, b) * 1e-6);
/** How many pixels are covered: to the pixel in software, within two on a card. */
const sameCount = (a, b) => (exact ? a === b : Math.abs(a - b) <= 2);
/**
 * The picture of a page that has come to rest: drawn again until two in a row are the same.
 * The view's first fades and the camera's last move are over long before a software-drawn
 * check gets here; on a graphics card the checks arrive while they are still under way
 * (16 November 2026: the first picture then differed from the later ones by half a percent).
 */
const atRest = async () => {
  let before = await picture();
  for (let tries = 0; tries < 80; tries++) {
    await sleep(250);
    const now = await picture();
    if (same(now.light, before.light) && same(now.cover, before.cover) && sameCount(now.lit, before.lit)) return now;
    before = now;
  }
  return before;
};
const zero = (numbers) => Object.values(numbers).every((value) => value === 0);
// Since 16 November 2026 every part is drawn whole where colour shows the kind of part (the user; docs/CELL_STRUCTURES.md).
const HEAD_LEGEND = "Colour shows the kind of part, and every part is drawn whole. The dot beside each name is its status; Colour: Status shows what is not built as grey sketches. Clear glass shapes and grey outlines are scenery.";

try {
 for (const scenario of scenarios) {
  note(`scenario: ${scenario}`);
  await lessMotion(false);
  if (scenario === "look") {
    // The page is asked for less motion before it loads: nothing in it moves, so pictures can be compared.
    await lessMotion(true);
    await open("lens=cell&look=full");
    const drawnBy = await evaluate(`(() => { const gl = ${V}.stage.renderer.getContext(), info = gl.getExtension("WEBGL_debug_renderer_info"); return String(info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)); })()`);
    exact = /swiftshader/i.test(drawnBy);
    note(`drawn by: ${drawnBy}; two pictures of the still page are compared ${exact ? "to the last count" : "within one part in a million"}`);
    let s = await state();
    check("the Cell view wears the seven effects", s.rich && s.drawn.join() === SEVEN, JSON.stringify(s.drawn));
    check("filmic light is on, with the studio to reflect", s.tone !== 0 && s.exposure > 1 && s.studio && !s.plainRoom, JSON.stringify([s.tone, s.exposure, s.studio]));
    check("light through thin parts, texture, shimmer and drift are switched on for the scene", Object.values(s.numbers).every((value) => value === 1), JSON.stringify(s.numbers));
    check("contact shade is worked out at the page's own size", s.passes && s.contactSize === 1 && s.picture?.[0] === s.width && s.picture?.[1] === s.height, JSON.stringify([s.contactSize, s.picture, s.width, s.height]));
    check("its reach is under a micrometre in a cell of twenty", s.reach > 0 && s.reach < s.unit, JSON.stringify([s.reach, s.unit]));
    check("the look's switch stands by the scale bar, with Rich pressed", s.box?.join() === "Look: Rich* | Plain", JSON.stringify(s.box));
    check("the view's card is as it was: colour and sizes, and no row for the look", s.card.filter((row) => !row.startsWith("Species")).join() === "Colour: Biology* | Status,Sizes: Schematic* | To scale", JSON.stringify(s.card));
    check("the legend's note is as it was", s.legend === HEAD_LEGEND, String(s.legend));
    check("the page says the texture is scenery, and that the motion is held still for this visitor", s.notes.length === 2 && s.notes[0] === "Surface texture is scenery." && /held still: this device asks for less motion/.test(s.notes[1]), JSON.stringify(s.notes));
    check("less motion was asked for: decoration stands still", s.still && !s.moving, JSON.stringify([s.still, s.moving]));
    const richLabels = s.callouts;
    await shot("look-rich");

    // Contact shade: gentle, on the picture only, and gone when switched off.
    const on = await atRest();
    const off = await picture(`s.finish.setContact(0);`);
    const again = await picture(`s.applyLook();`);
    const darker = 1 - on.light / off.light;
    check("contact shade darkens the picture, gently", darker > 0.0003 && darker < 0.05, `${(darker * 100).toFixed(2)}% less light with it than without`);
    check("it leaves the canvas as covered as it was", same(on.cover, off.cover) && sameCount(on.lit, off.lit), JSON.stringify([on.cover, off.cover]));
    check("switched on again it draws the same picture", same(again.light, on.light), JSON.stringify([again.light, on.light]));

    // Bloom: off at rest; on, it shines only from what was marked.
    const marked = await evaluate(`(${V}.current.byEntity.get("cap.energy") || []).filter((part) => ${V}.current.shows(part.zone)).length`);
    const mark = (flag) => `for (const part of (v.current.byEntity.get("cap.energy") || [])) s.glow(part.group${flag ? "" : ", false"});`;
    check("bloom is off at rest", s.bloom === 0, String(s.bloom));
    const unmarked = await picture(`s.setBloom(0.9);`);
    const shining = await picture(mark(true));
    const unmarkedAgain = await picture(mark(false));
    await evaluate(`${S}.setBloom(0)`);
    s = await state();
    check("switched on with nothing marked, nothing shines", same(unmarked.light, on.light), JSON.stringify([unmarked.light, on.light]));
    check("it shines from what was marked, and from nothing else", marked > 0 && shining.light > on.light && shining.light < on.light * 1.2, `${marked} part(s) marked; ${((shining.light / on.light - 1) * 100).toFixed(3)}% more light`);
    check("and with the mark taken away the picture is as it was", same(unmarkedAgain.light, on.light) && s.bloom === 0, JSON.stringify([unmarkedAgain.light, on.light, s.bloom]));

    // What a frame costs here, said with the renderer that drew it: in software the numbers say
    // what the look costs a software-drawn check, and nothing of a graphics card.
    const cost = { rich: await timed(), none: await timed(`s.finish.setContact(0);`) };
    await evaluate(`${S}.applyLook()`);

    // The plain look draws another picture, and no label is lost to the look either way.
    const plain = await evaluate(`(async () => { const v = ${V}; v.current.setLook("plain"); await new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))); return ${STATE}; })()`);
    const plainPicture = await picture();
    check("the two looks are two pictures", plainPicture.light !== on.light, JSON.stringify([plainPicture.light, on.light]));
    check("the labels' columns hold as many names with either look", plain.callouts === richLabels && richLabels > 0, JSON.stringify([richLabels, plain.callouts]));
    cost.plain = await timed();
    note(`one frame drawn ${exact ? "in software" : "on this machine's graphics card"} here, at ${s.width} by ${s.height}: plain ${cost.plain} ms; rich ${cost.rich} ms; rich without contact shade ${cost.none} ms`);
    await evaluate(`${V}.current.setLook("full")`);
  }

  if (scenario === "switch") {
    await lessMotion(true); // nothing here needs the page to move, and a still page draws only when asked
    await open("lens=cell&look=plain");
    let s = await state();
    check("look=plain in the address opens the look as it was", s.choice === "plain" && !s.rich && s.drawn.length === 0 && s.tone === 0 && s.exposure === 1 && !s.passes && s.plainRoom && zero(s.numbers), JSON.stringify([s.choice, s.drawn, s.tone, s.passes, s.plainRoom, s.numbers]));
    check("the switch shows Plain pressed, and the page says nothing of scenery it does not draw", s.box?.join() === "Look: Rich | Plain*" && s.notes.length === 0, JSON.stringify([s.box, s.notes]));
    await shot("switch-plain");
    await press(button("Look", "Rich"), "Rich by the scale bar");
    await evaluate(`${S}.look.held = true`); // from here the slow frames of this server have no say
    s = await state();
    check("Rich, pressed: the seven effects", s.choice === "rich" && s.drawn.join() === SEVEN && s.tone !== 0 && s.studio && s.passes, JSON.stringify([s.choice, s.drawn, s.tone, s.studio, s.passes]));
    await evaluate(`${V}.renderChrome()`);
    s = await state();
    check("the switch shows Rich pressed", s.box?.join() === "Look: Rich* | Plain", JSON.stringify(s.box));
    await press(button("Look", "Plain"), "Plain by the scale bar");
    s = await state();
    check("Plain, pressed: nothing of the look is drawn", s.choice === "plain" && s.drawn.length === 0 && s.tone === 0 && !s.passes && s.plainRoom && zero(s.numbers), JSON.stringify([s.choice, s.drawn, s.tone, s.passes, s.numbers]));
    await press(button("Look", "Rich"), "Rich by the scale bar, again");
    await evaluate(`${S}.look.held = true`);

    // A device that cannot keep up: contact shade at half size, then off, then the rest. Fast frames bring nothing back.
    let f = await feed(12, 3);
    check("smooth frames: nothing is given up, and nothing is said of it", f.stepped === 0 && f.step === 0 && f.contact === 1 && !f.notes.some((text) => /could not keep/.test(text)), JSON.stringify([f.stepped, f.step, f.notes]));
    f = await feed(60);
    check("slow frames: first, contact shade at half size", f.stepped === 1 && f.step === 1 && f.contact === 0.5 && f.contactSize === 0.5 && f.drawn.join() === SEVEN, JSON.stringify([f.stepped, f.step, f.contact, f.contactSize]));
    check("and the page says so", f.notes.some((text) => /^Contact shade is drawn at half size: this device could not keep/.test(text)), JSON.stringify(f.notes));
    await evaluate(`${S}.draw()`);
    s = await state();
    check("its picture is then half the page's size each way", s.picture?.[0] === Math.round(s.width * 0.5) && s.picture?.[1] === Math.round(s.height * 0.5), JSON.stringify([s.picture, s.width, s.height]));
    f = await feed(60);
    check("still slow: contact shade off, the passes at rest", f.step === 2 && f.contact === 0 && !f.passes && !f.drawn.includes("contact") && f.drawn.length === 6, JSON.stringify([f.step, f.contact, f.passes, f.drawn]));
    check("and the page says so", f.notes.some((text) => /^Contact shade is off: this device could not keep/.test(text)), JSON.stringify(f.notes));
    f = await feed(60);
    check("still slow: only what costs nothing in a frame is left", f.step === 3 && f.drawn.join() === "reflections,filmic" && f.numbers.texture === 0 && f.numbers.drift === 0 && f.numbers.shimmer === 0 && f.numbers.translucency === 0, JSON.stringify([f.step, f.drawn, f.numbers]));
    check("and the page says so, and no longer calls a texture scenery that it does not draw", f.notes.length === 1 && /^Only studio reflections and filmic light are on: this device could not keep/.test(f.notes[0]), JSON.stringify(f.notes));
    f = await feed(5, 6);
    check("fast frames bring nothing back by themselves", f.stepped === 0 && f.step === 3, JSON.stringify([f.stepped, f.step]));
    await press(button("Look", "Rich"), "Rich by the scale bar, once more");
    await evaluate(`${S}.look.held = true`);
    s = await state();
    check("choosing Rich again tries all of it once more", s.step === 0 && s.drawn.join() === SEVEN, JSON.stringify([s.step, s.drawn]));

    // Status colours carry a meaning: filmic light is left out of them.
    // The look was switched on again a moment ago, and its first frames are slow where the picture is drawn in
    // software. The cards may be rebuilt after such a frame; a press that falls across that loses its release.
    // So one frame is let through first, and the press is made again if it was lost.
    await frame();
    for (let tries = 0; tries < 3; tries++) {
      await press(button("Colour", "Status"), "Colour: Status");
      if (await evaluate(`${V}.current.colourBy === "status"`)) break;
    }
    s = await state();
    check("with Colour: Status, filmic light is left out, so each status keeps its colour", s.tone === 0 && s.exposure === 1 && s.filmicFits === false && s.drawn.includes("filmic") && s.studio, JSON.stringify([s.tone, s.exposure, s.filmicFits]));
    await shot("switch-status");
    await press(button("Colour", "Biology"), "Colour: Biology");
    s = await state();
    check("with Colour: Biology it is back", s.tone !== 0 && s.exposure > 1, JSON.stringify([s.tone, s.exposure]));
  }

  if (scenario === "views") {
    await lessMotion(true);
    await open("lens=cell&look=full");
    let s = await state();
    const farReach = s.reach;
    await press(button("Sizes", "To scale"), "Sizes: To scale");
    await rest();
    s = await state();
    const scale = await picture();
    check("to scale: the same look, and the picture draws", s.drawn.join() === SEVEN && s.passes && scale.lit > scale.pixels * 0.05, JSON.stringify([s.drawn.length, s.passes, scale.lit]));
    await shot("views-to-scale");
    await evaluate(`${V}.current.goToScale("molecule", true)`);
    await rest();
    await sleep(600);
    s = await state();
    check("close to the membrane, contact shade reaches less far", s.reach < farReach * 0.2 && s.reach > 0, JSON.stringify([s.reach, farReach]));
    await shot("views-close");

    // The other views keep the look they had.
    for (const lens of ["engine", "proteins", "experiments"]) {
      await evaluate(`${V}.setLens(${JSON.stringify(lens)})`);
      await sleep(900);
      s = await state();
      check(`the ${lens} view keeps the look it had: no switch, no passes, no filmic light`, s.lens === lens && !s.rich && s.tone === 0 && s.exposure === 1 && !s.passes && s.contactSize === 0 && zero(s.numbers) && s.box === null, JSON.stringify([s.lens, s.rich, s.tone, s.passes, s.numbers, s.box]));
    }
    await evaluate(`${V}.setLens("cell")`);
    await rest();
    await frame(); // the scale bar, and the switch over it, come back with the first frame drawn
    s = await state();
    check("back in the Cell view the look is back, and its switch with the scale bar", s.rich && s.tone !== 0 && s.passes && s.box?.join() === "Look: Rich* | Plain", JSON.stringify([s.rich, s.tone, s.passes, s.box]));

    // A small cell: one membrane, a free chromosome, ribosomes from a count.
    await evaluate(`${V}.setSpecies("syn3a")`);
    await rest();
    await sleep(600);
    s = await state();
    const small = await picture();
    check("a small species' cell wears the look too, and draws", s.rich && s.drawn.join() === SEVEN && s.passes && small.lit > small.pixels * 0.02, JSON.stringify([s.drawn.length, s.passes, small.lit, small.pixels]));
    check("its contact shade reaches a share of its own small size", s.reach > 0 && s.reach < s.unit && s.unit < 0.2, JSON.stringify([s.reach, s.unit]));
    await shot("views-syn3a");

    // A phone: the switch stands over the scale bar there too, within the screen, and takes a press.
    await evaluate(`${V}.setSpecies("planarian")`);
    await page("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: false });
    await rest();
    await sleep(800);
    const phone = await evaluate(`(() => {
      const root = ${V}.shadowRoot, box = (name) => { const r = root.querySelector(name)?.getBoundingClientRect(); return r && r.width ? [r.left, r.top, r.right, r.bottom].map(Math.round) : null; };
      return { width: innerWidth, height: innerHeight, look: box(".look-switch"), bar: box(".scalebar-text"), card: box(".view.card"), rail: box(".rail"), legend: box("cells-legend"), caveat: box(".caveat") };
    })()`);
    const apart = (a, b) => !a || !b || a[2] <= b[0] || b[2] <= a[0] || a[3] <= b[1] || b[3] <= a[1];
    check("on a phone the switch is within the screen, over the scale bar, and clear of the card, the scale's list, the legend and the note", Boolean(phone.look) && phone.look[0] >= 0 && phone.look[2] <= phone.width && phone.look[1] >= 56 && (!phone.bar || phone.look[3] <= phone.bar[1] + 1) && ["card", "rail", "legend", "caveat"].every((name) => apart(phone.look, phone[name])), JSON.stringify(phone));
    await press(button("Look", "Plain"), "Plain, on a phone");
    s = await state();
    check("and it takes a press there", s.choice === "plain" && s.box?.join() === "Look: Rich | Plain*", JSON.stringify([s.choice, s.box]));
    await press(button("Look", "Rich"), "Rich, on a phone");
    // The scale rail folds behind one button on a phone, so that the top of the view is not crowded: a real press
    // opens its levels, and a real press on one goes there and folds it again.
    const railState = () =>
      evaluate(`(() => {
        const root = ${V}.shadowRoot, box = (el) => { const r = el?.getBoundingClientRect(); return r && r.width ? [r.left, r.top, r.right, r.bottom].map(Math.round) : null; };
        const toggle = root.querySelector(".rail-toggle");
        return { toggle: box(toggle), rail: box(root.querySelector(".rail")), card: box(root.querySelector(".view.card")), bar: box(root.querySelector(".bar .switch")), expanded: toggle?.getAttribute("aria-expanded") ?? null, active: ${V}.current.activeStop, says: toggle?.textContent ?? null, level: root.querySelector('.rail button[aria-pressed="true"]')?.textContent ?? null,
          stops: [...root.querySelectorAll(".rail button")].map((b) => [b.dataset.stop, Math.round(b.getBoundingClientRect().height)]) };
      })()`);
    let rail = await railState();
    check("on a phone the scale rail stands folded behind one button under the bar, at least 44 px tall, naming the level shown, clear of the view's card", Boolean(rail.toggle) && rail.rail === null && rail.toggle[1] >= (rail.bar?.[3] ?? 56) && rail.toggle[3] - rail.toggle[1] >= 44 && apart(rail.toggle, rail.card) && Boolean(rail.level) && (rail.says || "").endsWith(rail.level), JSON.stringify(rail));
    await press(`(root) => root.querySelector(".rail-toggle")`, "the rail's button");
    rail = await railState();
    check("a real press opens it under its button: every level a button at least 44 px tall, within the screen", rail.expanded === "true" && Boolean(rail.rail) && rail.rail[1] >= rail.toggle[3] && rail.rail[3] <= phone.height && rail.stops.length >= 2 && rail.stops.every(([, height]) => height >= 44), JSON.stringify(rail));
    await press(`(root) => root.querySelector('.rail button[data-stop="tissue"]')`, "the rail's tissue level");
    await rest();
    rail = await railState();
    check("a real press on a level goes there and folds the rail again", rail.active === "tissue" && rail.rail === null && rail.expanded === "false", JSON.stringify(rail));
    await evaluate(`${V}.current.goToScale("cell", true)`);
    await rest();
    // With a part's panel open (a sheet along the bottom of a phone) the view's card folds behind one button under the
    // bar, and the look's switch stands on the sheet's top edge: a real press on each still reaches its switch.
    await evaluate(`${V}.select("cap.pumps")`);
    await sleep(800);
    const folded = () =>
      evaluate(`(() => {
        const root = ${V}.shadowRoot, box = (el) => { const r = el?.getBoundingClientRect(); return r && r.width ? [r.left, r.top, r.right, r.bottom].map(Math.round) : null; };
        const said = [...root.querySelectorAll(".label-example")].some((el) => !el.classList.contains("is-off"));
        return { toggle: box(root.querySelector(".view-toggle")), card: box(root.querySelector(".view.card")), panel: box(root.querySelector("cells-panel")), look: box(root.querySelector(".look-switch")), colour: ${V}.current.colourBy, selected: ${V}.state.selected,
          flux: ${V}.current.flux?.tokens.length > 0, said, notice: box(root.querySelector(".view-notice")) ? root.querySelector(".view-notice").textContent : null };
      })()`);
    let fold = await folded();
    check("on a phone with a panel open the view's card folds behind a button at least 44 px tall under the bar, and the look's switch stands on the panel's edge", Boolean(fold.toggle) && fold.card === null && fold.toggle[3] - fold.toggle[1] >= 44 && Boolean(fold.look) && Boolean(fold.panel) && fold.look[3] <= fold.panel[1], JSON.stringify(fold));
    await press(`(root) => root.querySelector(".view-toggle")`, "the folded card's button");
    await press(button("Colour", "Status"), "Colour: Status, over the panel");
    fold = await folded();
    check("a real press opens the card over the picture, and a real press on Colour: Status takes it, the part still chosen", Boolean(fold.card) && fold.colour === "status" && fold.selected === "cap.pumps", JSON.stringify(fold));
    // The part's flux shows: where the opened card leaves the picture's statement no room, the card carries its notice (rule 11).
    check("while the part's flux shows, the words \"Illustration: not a run\" stay in sight: on the picture, or in the opened card", !fold.flux || fold.said || fold.notice === "Illustration: not a run", JSON.stringify(fold));
    await press(button("Colour", "Biology"), "Colour: Biology, over the panel");
    await press(button("Look", "Plain"), "Plain, on the panel's edge");
    s = await state();
    check("and the look's switch on the panel's edge takes a press", s.choice === "plain", JSON.stringify([s.choice, s.box]));
    await press(button("Look", "Rich"), "Rich, on the panel's edge");
    await evaluate(`${V}.select(null)`);
    await rest();
    fold = await folded();
    check("letting go of the part folds nothing away: the card stands as before, and its button is gone", Boolean(fold.card) && fold.toggle === null && fold.colour === "biology", JSON.stringify(fold));
    await evaluate(`${S}.look.held = true`);
    await shot("views-phone");
    await page("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: HEIGHT, deviceScaleFactor: 1, mobile: false });
  }

  if (scenario === "motion") {
    // Decoration: its clock runs while the view moves, stops when held from outside, and stops for
    // a visitor who asks for less motion. Time is counted in frames drawn, and every change is
    // waited for until the page has taken it: this server draws slowly, and takes seconds to notice.
    await open("lens=cell&look=full");
    await evaluate(`(() => { window.__frames = 0; ${S}.afterRender.add(() => { window.__frames += 1; }); })()`);
    /** How far the decoration's clock went while so many frames were drawn (it waits up to two minutes for them). */
    const run = async (frames) => {
      const before = await evaluate(`[${S}.decoration.time, window.__frames]`);
      let now = before;
      for (let tries = 0; tries < 480 && now[1] - before[1] < frames; tries++) {
        await sleep(250);
        now = await evaluate(`[${S}.decoration.time, window.__frames]`);
      }
      return { went: now[0] - before[0], frames: now[1] - before[1] };
    };
    /** Wait until the page has taken a change (up to two minutes). */
    const taken = async (expression) => {
      for (let tries = 0; tries < 480; tries++) {
        if (await evaluate(expression).catch(() => false)) return true;
        await sleep(250);
      }
      return false;
    };
    const moved = await run(3);
    let s = await state();
    check("the decoration's clock runs with the view, and the materials share it", !s.still && s.moving && moved.frames >= 3 && moved.went > 0 && s.shared === s.clock, JSON.stringify([s.still, moved, s.shared, s.clock]));
    check("the page names what moves as scenery, with the texture", s.notes.length === 1 && s.notes[0] === "Surface texture, the crowd's slow jostling and the membrane's shimmer are scenery.", JSON.stringify(s.notes));
    await evaluate(`${S}.decoration.pause("flux")`);
    const heldStill = await run(3);
    check("held from outside (as flux will hold it), it stands still while the view goes on moving", heldStill.frames >= 3 && heldStill.went === 0, JSON.stringify(heldStill));
    await evaluate(`${S}.decoration.resume("flux")`);
    const resumed = await run(3);
    check("released, it runs again", resumed.frames >= 3 && resumed.went > 0, JSON.stringify(resumed));
    // Less motion, asked for while the page is open.
    await lessMotion(true);
    const noticed = await taken(`${S}.decoration.still === true`);
    const before = await evaluate(`${S}.decoration.time`);
    await sleep(2500);
    const stilled = (await evaluate(`${S}.decoration.time`)) - before;
    s = await state();
    check("a visitor who asks for less motion while the page is open gets none of it", noticed && s.still && !s.moving && stilled === 0, JSON.stringify([noticed, s.still, stilled]));
    check("and is told, in place of being told that motion is scenery", s.notes.length === 2 && s.notes[0] === "Surface texture is scenery." && /held still: this device asks for less motion/.test(s.notes[1]), JSON.stringify(s.notes));
    await lessMotion(false);
    const back = await taken(`${S}.decoration.still === false`);
    const again = await run(3);
    s = await state();
    check("asked for motion again, it moves again", back && !s.still && again.frames >= 3 && again.went > 0 && s.notes.length === 1, JSON.stringify([back, s.still, again, s.notes]));
  }

  if (scenario === "trial") {
    await open("lens=cell&fps=1");
    const panel = () =>
      evaluate(`(() => {
        const box = ${V}.shadowRoot.querySelector(".look-trial");
        if (!box) return null;
        return { rate: box.querySelector(".rate").textContent, drawn: box.querySelector(".drawn").textContent, says: box.querySelector(".says").textContent, switches: [...box.querySelectorAll("label")].map((label) => label.textContent + (label.querySelector("input").checked ? "*" : "")) };
      })()`);
    let s = await state();
    let p = await panel();
    check("with no word in the address the look is rich", s.choice === "rich" && s.rich && s.drawn.includes("reflections") && s.drawn.includes("filmic"), JSON.stringify([s.choice, s.drawn]));
    check("fps=1 shows the readout in the Cell view, with a switch for each of the seven effects", p?.switches.length === 7 && p.switches.map((item) => item.replace("*", "")).join() === "Studio reflections,Filmic light,Soft translucency,Contact shade,Surface texture,Crowd drift,Membrane shimmer", JSON.stringify(p?.switches));
    await evaluate(`${V}.current.setLook("rich")`); // judged afresh from here, whatever this slow server gave up while the page loaded
    await press(`(root) => [...root.querySelectorAll(".look-trial label")].find((label) => label.textContent === "Contact shade")?.querySelector("input")`, "the contact shade switch");
    s = await state();
    p = await panel();
    check("switching one by hand turns that effect off, and no other", !s.drawn.includes("contact") && s.drawn.length === 6 && !s.passes, JSON.stringify(s.drawn));
    check("and rests the device's own fallback while the visitor judges", s.held && /fallback rests while you judge/.test(p.says), JSON.stringify([s.held, p.says]));
    check("the switches show it", p.switches.filter((item) => item.endsWith("*")).length === 6 && p.switches.includes("Contact shade"), JSON.stringify(p.switches));
    const stepped = await evaluate(`(() => { const look = ${S}.look; let n = 0; for (let i = 0; i < 300; i++) if (look.frame(200)) n += 1; return n; })()`);
    s = await state();
    check("slow frames then change nothing", stepped === 0 && s.drawn.length === 6, JSON.stringify([stepped, s.drawn]));
    await press(`(root) => [...root.querySelectorAll(".look-trial label")].find((label) => label.textContent === "Crowd drift")?.querySelector("input")`, "the crowd drift switch");
    s = await state();
    check("each switch is its own", !s.drawn.includes("drift") && s.numbers.drift === 0 && s.numbers.shimmer === 1 && s.drawn.length === 5, JSON.stringify([s.drawn, s.numbers]));
    // The readout writes twice a second; the view moves by itself, so frames follow one another.
    let rate = "";
    for (let tries = 0; tries < 120 && !/^Frame: [0-9.]+ ms/.test(rate); tries++) {
      await sleep(500);
      rate = (await panel()).rate;
    }
    p = await panel();
    check("it says how long a frame takes on this device", /^Frame: [0-9.]+ ms · [0-9.]+ a second$/.test(p.rate), String(p.rate));
    check("and what was drawn in the frame", /^[0-9,]+ draws · [0-9,]+ triangles$/.test(p.drawn) && Number(p.drawn.split(" ")[0].replace(/,/g, "")) > 20, String(p.drawn));
    await shot("trial");
    await evaluate(`${V}.setLens("engine")`);
    await sleep(600);
    check("the readout leaves with the Cell view", (await panel()) === null);
    await evaluate(`${V}.setLens("cell")`);
    await sleep(600);
    check("and comes back with it", (await panel()) !== null);
    await frame(); // the scale bar, and the look's switch over it, come back with the first frame drawn
    s = await state();
    check("back in the Cell view the look is back, and its switch with the scale bar", s.rich && s.tone !== 0 && s.box?.length === 1 && s.box[0].startsWith("Look: Rich"), JSON.stringify([s.rich, s.tone, s.box]));
  }

  if (scenario === "pictures") {
    const steps = JSON.parse(await readFile(process.env.STEPS, "utf8"));
    if (!process.env.MOTION) await lessMotion(true);
    await open(process.env.QUERY || "lens=cell&look=full");
    for (const step of steps) {
      if (step.size) {
        await page("Emulation.setDeviceMetricsOverride", { width: step.size[0], height: step.size[1], deviceScaleFactor: step.size[2] || 1, mobile: false });
        await sleep(500);
      }
      const told = step.run ? await evaluate(`(async () => { const viewer = ${V}, stage = viewer.stage, lens = viewer.current; ${step.run} })()`) : undefined;
      if (step.rest) await rest();
      await sleep(step.wait ?? 300);
      if (told !== undefined) note(`${step.name}: ${JSON.stringify(told)}`);
      if (step.name && !step.quiet) await shot(step.name, step.clip || null);
    }
  }
 }
} catch (error) {
  check("the run completed", false, error.stack || error.message);
} finally {
  for (const line of [...pageLog, ...consoleErrors]) console.log(line);
  if (scenarios.some((name) => name !== "pictures") || pageLog.length || consoleErrors.length) {
    // Whether the page's own font had arrived by the end: with the stand-in, words run longer and cards stand
    // taller, and a miss is read against that.
    note(`the page's own font: ${await evaluate(`document.fonts.status === "loaded" && ["Inter", "Space Grotesk"].every((family) => [...document.fonts].some((face) => face.family.includes(family) && face.status === "loaded")) ? "arrived" : "not arrived: the stand-in was shown, whose words run longer"`).catch(() => "not known")}`);
    check("no script errors or blocked loads were reported by the page", pageLog.length === 0, `${pageLog.length} messages`);
    check("the page's console reported no error (a shader that does not compile is said there)", consoleErrors.length === 0, `${consoleErrors.length} errors`);
  }
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
note(`waited ${Math.round((held - started) / 1000)} s for the browser, held it ${Math.round((Date.now() - held) / 1000)} s`);
if (results.length) console.log(`${results.length - failed} of ${results.length} checks passed`);
process.exit(failed ? 1 : 0);
