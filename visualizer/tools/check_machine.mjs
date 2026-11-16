#!/usr/bin/env node
// Checks a machine's closer view in the Cell view (schema/MACHINES.md; schema/QUANTITY_LAYERS.md,
// rule 13) with real pointer input, through the DevTools protocol, in the manner of
// tools/check_cellflux.mjs. On E. coli's flagellar motor:
//
//   main      a real press on a flagellum's foot opens its panel with "Look closer"; a real press
//             on that door flies in: the cell fades out, the motor fades in at true size, the scale
//             bar reads in nanometres, the picture says "Illustration: not a run · Cells has no model
//             of this motor". It turns at real-life speed, drawn swept with its arrowhead; the
//             legend offers the Speed row, and a real press on 1/1,000 slows it, sharp. A real press
//             on the C ring's name opens its panel (its proteins, "measured in Salmonella"). "Back
//             to the cell" flies out and the cell comes back; the rail's stop flies in again; the C
//             ring's door opens the Protein atlas on its three proteins.
//   address  `machine=flagellar-motor` in the address opens the closer view standing ("shown
//             still"); a real press on a part turns it; Escape closes the panel, a second Escape
//             goes back to the cell.
//   reduced  with less motion asked for, Look closer jumps there and the motor stands.
//
//   node tools/check_machine.mjs [OUT_DIR]
//
// Set by the environment: CASE (main, address or reduced; main unless set), WIDTH and HEIGHT
// (1400 by 900), THEME (dark), NAME (what the pictures are called in OUT_DIR), FRAMES=1 (the page
// opens with the frames readout, and the check says what it reads). It also reports the draw
// calls and triangles the renderer counted for the cell alone, the motor turning sharp and the
// motor swept. One browser at a time: it takes the lock in tools/lib/browser_lock.mjs.

import { spawn } from "node:child_process";
import { writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { createServer } from "./serve.mjs";
import { acquireBrowser } from "./lib/browser_lock.mjs";
import { DEFAULT_RUNS, DEFAULT_SCENE } from "./lib/build_page.mjs";
import { sharpness as sharpnessAt } from "../src/layers/machine_motion.js";

const outDir = process.argv[2] ? path.resolve(process.argv[2]) : null;
if (outDir) await mkdir(outDir, { recursive: true });
const WIDTH = Number(process.env.WIDTH || 1400), HEIGHT = Number(process.env.HEIGHT || 900);
const CASE = process.env.CASE || "main";
const NAME = process.env.NAME || `machine-${CASE}`;
const PHONE = WIDTH < 760;
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
  const media = [];
  if (process.env.THEME === "dark") media.push({ name: "prefers-color-scheme", value: "dark" });
  if (CASE === "reduced") media.push({ name: "prefers-reduced-motion", value: "reduce" });
  if (media.length) await page("Emulation.setEmulatedMedia", { features: media });
  // The page's own errors, and the frames it draws, are kept on the page for the checks to read.
  await page("Page.enable");
  await page("Page.addScriptToEvaluateOnNewDocument", {
    source: `window.__pageErrors = []; addEventListener("error", (event) => __pageErrors.push(String(event.error?.stack || event.message))); addEventListener("unhandledrejection", (event) => __pageErrors.push("rejection: " + String(event.reason?.stack || event.reason)));`,
  });
  const evaluate = async (expression) => {
    const reply = await page("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (reply.exceptionDetails) throw new Error(reply.exceptionDetails.exception?.description || reply.exceptionDetails.text);
    return reply.result.value;
  };
  const V = "document.querySelector('cells-viewer')", L = `${V}.current`, M = `${L}.machine`;
  const mouse = (type, x, y, extra = {}) => page("Input.dispatchMouseEvent", { type, x, y, button: "left", buttons: 1, clickCount: 1, ...extra });
  const click = async (x, y, wait = 500) => {
    await mouse("mouseMoved", x, y, { button: "none", buttons: 0 });
    await mouse("mousePressed", x, y);
    await mouse("mouseReleased", x, y, { buttons: 0 });
    await sleep(wait);
  };
  const key = async (name) => {
    await page("Input.dispatchKeyEvent", { type: "keyDown", key: name, code: name, windowsVirtualKeyCode: name === "Escape" ? 27 : 0 });
    await page("Input.dispatchKeyEvent", { type: "keyUp", key: name, code: name, windowsVirtualKeyCode: name === "Escape" ? 27 : 0 });
    await sleep(500);
  };
  /** The middle of what an expression finds, if it is on the screen and nothing lies over it; with its smaller side. */
  const placeOf = (expression) =>
    evaluate(`(() => { const root = ${V}.shadowRoot, el = ${expression}; if (!el) return null; el.scrollIntoView({ block: "nearest" }); const r = el.getBoundingClientRect(); if (!r.width || !r.height) return null; const x = r.left + r.width / 2, y = r.top + r.height / 2; const top = root.elementFromPoint(x, y); return top && (top === el || el.contains(top)) ? { x, y, least: Math.min(r.width, r.height), words: el.textContent } : null; })()`);
  const door = (words) => `[...root.querySelectorAll("cells-panel .panel-door button")].find((button) => ${JSON.stringify(words)} === button.textContent.replace(/ →$/, ""))`;
  const pressDoor = async (words) => {
    const at = await placeOf(door(words));
    if (!at) return null;
    await click(at.x, at.y, 700);
    return at;
  };
  const until = async (test, tries = 240) => {
    for (let k = 0; k < tries; k++) {
      if (await evaluate(test).catch(() => false)) return true;
      await sleep(250);
    }
    return false;
  };
  const shot = async (name) => {
    if (!outDir) return;
    await sleep(300);
    const { data } = await page("Page.captureScreenshot", { format: "png" });
    await writeFile(path.join(outDir, `${name}.png`), Buffer.from(data, "base64"));
    note(`wrote ${path.join(outDir, `${name}.png`)}`);
  };
  /** What the page shows of the closer view now. */
  const state = () =>
    evaluate(`(() => {
      const v = ${V}, root = v.shadowRoot, lens = v.current, m = lens.machine, stage = v.stage, info = stage.renderer.info.render;
      const panel = root.querySelector("cells-panel");
      const zones = Object.fromEntries(lens.zones.filter((zone) => lens.shows(zone)).map((zone) => [zone.name, Math.round(zone.fade * 100) / 100]));
      const sets = m.built ? m.built.sets.map((set) => ({ part: set.part, marks: set.objects.some((object) => object.visible), swept: set.blur.visible })) : [];
      return {
        open: m.open, leaving: m.leaving, turning: m.turning, fade: Math.round(m.fade * 100) / 100, level: m.level, angle: m.motion?.turns ?? null, slow: lens.flux.slow,
        selected: v.state.selected, distance: stage.rig.distance, frameDistance: m.distance, zones, sets, arrow: Boolean(m.built?.arrow?.visible && m.fade > 0.5),
        rail: lens.chrome().railActive, scale: root.querySelector(".scalebar-text")?.textContent ?? null,
        // What the picture says, with its line breaks read as spaces.
        said: [...root.querySelectorAll(".label-example, .label-flow")].filter((el) => !el.hidden && !el.classList.contains("is-off") && el.textContent).map((el) => el.textContent.replace(/\\s+/g, " ")),
        statement: lens.flux.said ? { notice: lens.flux.said.notice, placed: Boolean(lens.flux.fitted?.place) } : null,
        sharpness: m.motion ? { step: m.motion.step, frameMs: Math.round(m.motion.frameMs), sets: m.built.sets.map((set) => ({ part: set.part, period: set.period, sharp: Math.round((m.motion.sharp.get(set) ?? 1) * 1000) / 1000 })) } : null,
        rows: [...root.querySelectorAll("cells-legend .layer-row")].map((row) => row.dataset.channel + ": " + [...row.querySelectorAll("button")].map((b) => b.textContent + (b.getAttribute("aria-pressed") === "true" ? "*" : "")).join(" | ")),
        hint: root.querySelector("cells-legend .layer-hint")?.textContent ?? null,
        panel: !panel || panel.hidden ? null : { title: panel.querySelector("h2")?.textContent ?? null, text: panel.textContent },
        frames: root.querySelector(".frame-readout")?.textContent ?? null,
        drawn: { calls: info.calls, triangles: info.triangles },
        holds: [...stage.decoration.holds],
        drawnFrames: (stage.afterRender.has(window.__countFrame) || stage.afterRender.add((window.__countFrame ??= () => (window.__framesDrawn = (window.__framesDrawn || 0) + 1))), window.__framesDrawn || 0),
        running: stage.running,
        errors: (window.__pageErrors || []).slice(0, 3),
      };
    })()`);
  /** Some frames drawn on purpose, so that "it stands" is judged over frames and not over a picture that drew none. */
  const someFrames = async (count = 3) => {
    for (let k = 0; k < count; k++) {
      const before = (await state()).drawnFrames;
      await evaluate(`${V}.stage.invalidate()`);
      await until(`(window.__framesDrawn || 0) > ${before}`, 120);
    }
  };
  /**
   * Whether the picture says these words: on the picture, or, where the picture has no room
   * for its statement (a phone with a panel open), in the open panel in front of it, as rule 13
   * of schema/QUANTITY_LAYERS.md allows. Where it was is noted.
   */
  const says = (state, pattern) => state.said.some((text) => pattern.test(text)) || Boolean(state.statement && !state.statement.placed && pattern.test(state.panel?.text || ""));
  const whereSaid = (state) => (state.said.length ? "on the picture" : state.statement && !state.statement.placed ? "in the panel: the picture had no room" : "nowhere");
  const drawnNow = async () => {
    await evaluate(`${V}.stage.invalidate()`);
    await sleep(400);
    return (await state()).drawn;
  };
  // A flight advances at most a tenth of a second a frame, and the software renderer draws the whole cell slowly: up to five minutes.
  const arrived = () => until(`(() => { const m = ${M}; return m.open && !m.leaving && m.fade > 0.98 && !${V}.stage.rig.flight; })()`, 1200);

  const query = ["lens=cell", "species=ecoli", process.env.FRAMES === "1" ? "frames=1" : null, CASE === "address" ? "machine=flagellar-motor" : null].filter(Boolean).join("&");
  await page("Page.navigate", { url: `${base}?${query}` });
  if (!(await until(`Boolean(${V} && ${L} && ${V}.state.lens === "cell" && ${L}.cells && ${L}.machine)`, 1440))) throw new Error("the Cell view was not drawn within six minutes");
  await sleep(1500);
  note(`case ${CASE}, ${WIDTH} by ${HEIGHT}${process.env.THEME === "dark" ? ", dark" : ""}${process.env.FRAMES === "1" ? ", frames=1" : ""}`);
  const cellAlone = CASE === "address" ? null : await drawnNow();
  if (cellAlone) note(`drawn, the cell alone: ${cellAlone.calls} draw calls, ${cellAlone.triangles.toLocaleString("en-US")} triangles`);

  /** A real press on a flagellum's foot, found by projecting the feet the cell drew to the screen. */
  const pressFoot = async () => {
    const feet = await evaluate(`(() => {
      const v = ${V}, lens = v.current, root = v.shadowRoot, item = (lens.cells[lens.sizeMode].scenery || []).find((piece) => piece.kind === "base");
      if (!item) return [];
      return item.feet.map((foot) => {
        const point = foot.at.clone().addScaledVector(foot.out, 0.012 / lens.u).multiplyScalar(lens.u), out = point.clone();
        v.stage.project(point, out);
        const top = out.x > 0 && out.y > 0 && out.x < v.stage.width && out.y < v.stage.height ? root.elementFromPoint(out.x, out.y) : null;
        return { x: out.x, y: out.y, free: Boolean(top) && (top.tagName === "CANVAS" || top.closest?.(".labels")), id: item.id };
      });
    })()`);
    for (const foot of feet.filter((item) => item.free)) {
      await click(foot.x, foot.y, 800);
      if ((await evaluate(`${V}.state.selected`)) === foot.id) return foot.id;
    }
    return null;
  };
  /**
   * A foot is a few pixels wide in the whole cell, mostly under its thread: the camera is put
   * beside the drum nearest it (through the page, as a visitor would turn and zoom), and the
   * drum is pressed beside its thread, across the line of sight.
   */
  const pressFootClose = async () => {
    const aim = await evaluate(`(() => {
      const v = ${V}, lens = v.current, stage = v.stage, item = (lens.cells[lens.sizeMode].scenery || []).find((piece) => piece.kind === "base");
      if (!item) return null;
      const drums = [];
      stage.scene.traverse((object) => object.isMesh && object.userData.pick === item.id && object.geometry?.type === "CylinderGeometry" && drums.push(object));
      if (!drums.length) return null;
      const V3 = stage.camera.position.constructor, place = (drum) => drum.getWorldPosition(new V3());
      const drum = drums.reduce((best, next) => (place(next).distanceTo(stage.camera.position) < place(best).distanceTo(stage.camera.position) ? next : best));
      const centre = place(drum), turn = drum.getWorldQuaternion(new drum.quaternion.constructor()), size = drum.getWorldScale(new V3());
      const axis = new V3(0, 1, 0).applyQuaternion(turn).normalize(), radius = drum.geometry.parameters.radiusTop * size.x, height = drum.geometry.parameters.height * size.y;
      const top = centre.clone().addScaledVector(axis, height * 0.3);
      window.__viewBefore = stage.rig.view(); // put back if no press lands
      // Seen from the side, a little from outside the cell.
      const side = new V3().crossVectors(axis, Math.abs(axis.y) < 0.9 ? new V3(0, 1, 0) : new V3(1, 0, 0)).normalize();
      const look = side.clone().addScaledVector(axis, 0.5).normalize();
      stage.rig.setView({ target: top, distance: radius * 9, azimuth: Math.atan2(look.x, look.z), polar: Math.acos(Math.max(-1, Math.min(1, look.y))) });
      const across = new V3().crossVectors(look, axis).normalize();
      return { id: item.id, top: top.toArray(), across: across.toArray(), radius, asked: radius * 9 };
    })()`);
    if (!aim) return null;
    await sleep(3000);
    const tried = [];
    for (const share of [0.7, -0.7, 0.55, -0.55]) {
      const at = await evaluate(`(() => {
        const v = ${V}, aim = ${JSON.stringify(aim)}, V3 = v.stage.camera.position.constructor;
        const point = new V3(...aim.top).addScaledVector(new V3(...aim.across), ${share} * aim.radius), out = point.clone();
        v.stage.project(point, out);
        const top = out.x > 0 && out.y > 0 && out.x < v.stage.width && out.y < v.stage.height ? v.shadowRoot.elementFromPoint(out.x, out.y) : null;
        const hit = top ? v.stage.pick(out.x, out.y, v.current.pickRoots) : null;
        return { x: Math.round(out.x), y: Math.round(out.y), free: Boolean(top) && (top.tagName === "CANVAS" || Boolean(top.closest?.(".labels"))), top: top ? top.tagName + (top.className ? "." + String(top.className).split(" ")[0] : "") : null, picks: hit?.id ?? null, distance: Number(v.stage.rig.distance.toFixed(4)) };
      })()`);
      tried.push(at);
      if (!at.free) continue;
      await click(at.x, at.y, 900);
      if ((await evaluate(`${V}.state.selected`)) === aim.id) return aim.id;
    }
    note(`beside the drum (asked for ${aim.asked.toFixed(4)} away), no press chose the foot: ${JSON.stringify(tried)}`);
    await evaluate(`(() => { const v = ${V}; if (window.__viewBefore) v.stage.rig.setView(window.__viewBefore); })()`);
    await sleep(2500);
    return null;
  };

  if (CASE !== "address") {
    // ---------------------------------------------------------- the foot's panel and its door
    let foot = await pressFoot();
    if (!foot) {
      note("no foot could be pressed in the whole cell (each is a few pixels wide, under its thread): the camera is put beside one");
      foot = await pressFootClose();
    }
    if (!foot) {
      note("no foot could be pressed at this size (each is a few pixels wide): it is chosen through the page");
      foot = await evaluate(`(() => { const lens = ${L}; const item = lens.cells[lens.sizeMode].scenery.find((piece) => piece.kind === "base"); ${V}.select(item.id); return item.id; })()`);
    } else check("a real press on a flagellum's foot chooses it", true, foot);
    await sleep(600);
    const at = await placeOf(door("Look closer"));
    check("the foot's panel offers Look closer beside its door into the Protein atlas", Boolean(at) && Boolean(await placeOf(door("Show the proteins of the flagellar motor in the Protein atlas"))), JSON.stringify(at));
    if (PHONE && at) check("on a phone the door is at least 44 px in its smaller side", at.least >= 44, String(at.least));
    await shot(`${NAME}-foot`);
    await pressDoor("Look closer");
    check("a real press on Look closer flies in: the motor fades in, the cell out", await arrived(), JSON.stringify(await state()));
  } else {
    check("the address opens the closer view", await arrived(), JSON.stringify(await state()));
  }

  // A flight that arrives at once (less motion asked for) is judged after the frame that draws it.
  await someFrames(1);
  let s = await state();
  check("the cell's zones are faded out and the machine's is in", s.zones.machine > 0.98 && Object.entries(s.zones).every(([name, fade]) => name === "machine" || fade < 0.02), JSON.stringify(s.zones));
  check("the scale bar reads in nanometres and says what the picture is", /\d+ nm · drawn to scale from published sizes; simple shapes, not structures/.test(s.scale || ""), String(s.scale));
  check("the machine's own panel is open, with Back to the cell", s.panel?.title === "Flagellar motor" && /Back to the cell/.test(s.panel.text), JSON.stringify(s.panel?.title));
  check("the rail stands on the machine's stop", s.rail === "machine", String(s.rail));

  if (CASE === "main") {
    // ---------------------------------------------------------- real-life speed: swept, with its arrowhead
    const first = s.angle;
    // The software renderer may take more than a second a frame: the turn is waited for, up to half a minute.
    await until(`(${M}.motion?.turns ?? null) !== ${JSON.stringify(first)}`, 120);
    s = await state();
    check("the visitor opened it: the rotor turns at real-life speed", s.turning && s.slow === 1 && s.angle !== first, JSON.stringify([first, s.angle, s.slow, s.drawnFrames, s.running, s.errors]));
    check("at real-life speed every turning part is drawn swept, no mark sharp, with the arrowhead", s.sets.length > 0 && s.sets.every((set) => set.swept && !set.marks) && s.arrow, JSON.stringify(s.sets));
    check("the picture says it is an illustration and no run, the way, where it is seen from and the speed, and nothing of being too fast", says(s, /Illustration: not a run · Cells has no model of this motor/) && says(s, /Turning as in a run: counter-clockwise, seen from outside the cell/) && says(s, /At real-life speed: about 150 turns a second/) && !says(s, /too fast|follow/i), JSON.stringify([whereSaid(s), s.said, s.statement]));
    check("the look's own motion is held while it turns", s.holds.includes("machine"), JSON.stringify(s.holds));
    check("the legend offers the Speed row while it turns", s.rows.some((row) => /^time: True\* \| 1\/1,000 \| 1\/1,000,000$/.test(row)), JSON.stringify(s.rows));
    const swept = await drawnNow();
    note(`drawn, the motor swept at real-life speed (level ${s.level}): ${swept.calls} draw calls, ${swept.triangles.toLocaleString("en-US")} triangles`);
    if (s.frames !== null) note(`frames readout: ${s.frames}`);
    await shot(`${NAME}-real`);
    // ---------------------------------------------------------- slowed a thousand times: sharp
    const slower = await placeOf(`[...root.querySelectorAll('cells-legend .layer-row[data-channel="time"] button')].find((button) => button.textContent === "1/1,000")`);
    if (slower) await click(slower.x, slower.y, 1500);
    else {
      note("the Speed row's 1/1,000 could not be pressed at this size: it is set through the page");
      await evaluate(`${V}.current.setSlow(1000)`);
      await sleep(1500);
    }
    // The motor takes the slow-down up at its next frame, which this renderer may take more than a second to draw.
    await until(`${M}.motion?.slow === 1000 && ${M}.motion.lastMs > 0`, 120);
    await someFrames(1);
    s = await state();
    // Whether a set is sharp at a thousand times slower depends on the frames drawn: the rule (machine_motion.js) is
    // judged at this renderer's own frames, and the device's 60 a second is worked out beside it.
    const byRule = (state) => state.sharpness.sets.every((judged) => {
      const set = state.sets.find((item) => item.part === judged.part);
      return set && (judged.sharp > 0.001) === set.marks && (judged.sharp < 0.999) === set.swept;
    });
    check("slowed a thousand times, each part is drawn sharp or swept as its step a frame asks, and the statement says the slow-down", s.slow === 1000 && byRule(s) && says(s, /Slowed 1,000 times: in life about 150 turns a second/), JSON.stringify([s.slow, s.sharpness, whereSaid(s), s.said]));
    const at60 = s.sharpness.sets.map((set) => `${set.part} ${set.period.toFixed(4)} of a turn between like marks: ${sharpnessAt(150 / 1000 / 60, set.period) > 0.999 ? "sharp" : sharpnessAt(150 / 1000 / 60, set.period) < 0.001 ? "swept" : "part sharp"}`);
    note(`slowed a thousand times at ${s.sharpness.frameMs} ms a frame here: ${s.sharpness.step.toFixed(4)} of a turn a frame; at 60 frames a second, 0.0025: ${at60.join("; ")}`);
    const slowedDrawn = await drawnNow();
    note(`drawn, the motor slowed a thousand times (level ${s.level}): ${slowedDrawn.calls} draw calls, ${slowedDrawn.triangles.toLocaleString("en-US")} triangles`);
    await shot(`${NAME}-slowed`);
    const slowest = await placeOf(`[...root.querySelectorAll('cells-legend .layer-row[data-channel="time"] button')].find((button) => button.textContent === "1/1,000,000")`);
    if (slowest) await click(slowest.x, slowest.y, 1500);
    else {
      await evaluate(`${V}.current.setSlow(1000000)`);
      await sleep(1500);
    }
    await until(`${M}.motion?.slow === 1000000`, 120);
    await someFrames(1);
    s = await state();
    check("slowed a million times, every part's marks are sharp, and the statement says so", s.slow === 1000000 && s.sets.every((set) => set.marks && !set.swept) && says(s, /Slowed 1,000,000 times/), JSON.stringify([s.slow, s.sharpness, whereSaid(s), s.said]));
    const sharp = await drawnNow();
    note(`drawn, the motor turning sharp, slowed a million times (level ${s.level}): ${sharp.calls} draw calls, ${sharp.triangles.toLocaleString("en-US")} triangles`);
    await shot(`${NAME}-slowed-million`);
    // ---------------------------------------------------------- a part's panel
    const ring = await placeOf(`root.querySelector('.label[data-label="machine:flagellar-motor:c-ring"]')`);
    if (ring) await click(ring.x, ring.y, 900);
    else {
      note("the C ring's name could not be pressed at this size: it is chosen through the page");
      await evaluate(`${V}.select("machine:flagellar-motor:c-ring")`);
      await sleep(900);
    }
    s = await state();
    check("the C ring's panel names its proteins and where its size comes from", s.selected === "machine:flagellar-motor:c-ring" && /fliG/.test(s.panel?.text || "") && /fliM/.test(s.panel.text) && /fliN/.test(s.panel.text) && /measured in Salmonella/.test(s.panel.text) && /Cells has no model of this motor/.test(s.panel.text), JSON.stringify(s.panel?.title));
    // ---------------------------------------------------------- the way back
    const back = await pressDoor("Back to the cell");
    if (PHONE && back) check("on a phone Back to the cell can be pressed with the panel open, and is at least 44 px", back.least >= 44, String(back.least));
    const out = await until(`!${M}.open`, 1200);
    s = await state();
    check("Back to the cell flies out: the closer view ends and the cell comes back", out && (s.zones.cell ?? 0) > 0.98 && !s.selected, JSON.stringify([s.open, s.zones, s.selected]));
    await shot(`${NAME}-back`);
    // ---------------------------------------------------------- the rail's stop, then the door into the atlas
    const stop = await placeOf(`root.querySelector('.rail button[data-stop="machine"]')`);
    if (PHONE && !stop) {
      const fold = await placeOf(`root.querySelector(".rail-toggle")`);
      if (fold) await click(fold.x, fold.y, 600);
    }
    const stopNow = stop || (await placeOf(`root.querySelector('.rail button[data-stop="machine"]')`));
    check("the scale rail has the motor's stop", Boolean(stopNow), JSON.stringify(stopNow));
    if (stopNow) {
      await click(stopNow.x, stopNow.y, 700);
      check("the rail's stop flies in again", await arrived(), JSON.stringify(await state()));
      await evaluate(`${V}.select("machine:flagellar-motor:c-ring")`);
      await sleep(800);
      const atlas = await pressDoor("Show these 3 proteins in the Protein atlas");
      check("the C ring's door into the Protein atlas can be pressed", Boolean(atlas));
      const there = await until(`${V}.state.lens === "proteins" && ${L}.mode === "own" && Boolean(${L}.mounted?.mark?.ids)`, 240);
      const picked = await evaluate(`(() => { const lens = ${L}, mark = lens.mounted?.mark; return mark ? { name: mark.name, value: mark.value, ids: [...(mark.ids || [])].sort(), total: lens.mounted.shelves.highlightTotal(mark.name, mark.value, mark.ids) } : null; })()`);
      check("it opens the species' own proteins with the flagellum's set lit and the C ring's three picked out", there && picked?.name === "complex" && picked.value === "flagellum" && picked.total === 3 && picked.ids.join() === "P06974,P0ABZ1,P15070", JSON.stringify(picked));
    }
  } else if (CASE === "address") {
    // ---------------------------------------------------------- opened from the address: it stands until the visitor chooses
    const first = s.angle;
    await someFrames();
    s = await state();
    check("opened from the address, the motor stands, and the picture says so", !s.turning && s.angle === first && says(s, /shown still/) && s.sets.every((set) => set.marks && !set.swept) && s.arrow, JSON.stringify([s.turning, s.said, s.sets]));
    check("the legend says why it stands", /the page's address opened this view/.test(s.hint || ""), String(s.hint));
    await shot(`${NAME}-still`);
    const ring = await placeOf(`root.querySelector('.label[data-label="machine:flagellar-motor:c-ring"]')`);
    if (ring) await click(ring.x, ring.y, 1200);
    else {
      note("the C ring's name could not be pressed at this size: it is chosen through the page");
      await evaluate(`(${V}.current.chosen(), ${V}.select("machine:flagellar-motor:c-ring"))`);
    }
    s = await state();
    check("a visitor's choice of a part sets it turning", s.turning, JSON.stringify([s.selected, s.turning]));
    // The viewer hears Escape where the focus is inside it (ui/viewer.js listens on its shadow root): where it is not,
    // the picture is given the focus, as a press on it or a Tab into it would.
    const focus = await evaluate(`(() => { const v = ${V}, inside = v.shadowRoot.activeElement; return inside ? inside.tagName + (inside.className ? "." + String(inside.className).split(" ")[0] : "") : "outside the viewer (" + (document.activeElement?.tagName || "none") + ")"; })()`);
    note(`before Escape the focus is ${focus}`);
    if (/^outside/.test(focus)) await evaluate(`${V}.canvas.focus({ preventScroll: true })`);
    await key("Escape");
    s = await state();
    check("Escape closes the panel first, and stays in the closer view", !s.selected && s.open, JSON.stringify([s.selected, s.open]));
    await key("Escape");
    const out = await until(`!${M}.open`, 1200);
    check("a second Escape goes back to the cell", out, JSON.stringify(await state()));
  } else if (CASE === "reduced") {
    const first = s.angle;
    await someFrames();
    s = await state();
    check("with less motion asked for, the motor stands, with its arrowhead and sharp marks, and the picture says so", !s.turning && s.angle === first && s.arrow && s.sets.every((set) => set.marks && !set.swept) && says(s, /shown still/), JSON.stringify([s.turning, s.said]));
    check("and the legend offers no Speed row", !s.rows.some((row) => row.startsWith("time:")), JSON.stringify(s.rows));
    await shot(`${NAME}-still`);
  }
  const readout = await evaluate(`${V}.shadowRoot.querySelector(".frame-readout")?.textContent ?? null`);
  if (process.env.FRAMES === "1") check("with frames=1 the readout says the frames the device draws", /^Frames: /.test(readout || ""), String(readout));
  else check("without frames=1 nothing of a readout is on the page", readout === null);
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
  console.error(`check_machine: ${failed.stack || failed}`);
  process.exit(2);
}
const passed = results.filter(Boolean).length;
console.log(`${passed} of ${results.length} checks passed`);
process.exit(passed === results.length ? 0 : 1);
