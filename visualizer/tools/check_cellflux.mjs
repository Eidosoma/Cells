#!/usr/bin/env node
// Checks flux in the Cell view (schema/QUANTITY_LAYERS.md, "Flux in the Cell view", rules 3,
// 7, 11 and 12) with real pointer input, through the DevTools protocol, in the manner of
// tools/check_layers.mjs: that the page opens with nothing flowing; that a real press on a
// part's name shows that part's flux alone, with bloom on, the look's own motion held and
// "Illustration: not a run" on the picture, in the legend and in the part's panel; that a
// real press on the legend's Flux switch shows all of it; and that switching it off leaves
// the stage as it was.
//
//   node tools/check_cellflux.mjs [OUT_DIR]
//
// Set by the environment: WIDTH and HEIGHT (1400 by 900), SPECIES (a species' id; the
// scene's own first choice otherwise), SIZE (schematic or real), SCALE (the stop the page opens at:
// molecule, for the close-up of the membrane), THEME (dark), MOVING (1:
// the page is not opened still, and the check waits to see a bead move), PART (the id of the
// capability to choose; the first the species has flux for otherwise) and NAME (what the
// pictures are called in OUT_DIR: NAME-rest.png, NAME-part.png and NAME-all.png). With ADDRESS=1 it checks
// one thing instead, on a page whose address names the part: that the part is chosen as the
// page opens and nothing flows, until a real press on the part's name or on the switch (the
// picture is NAME-address.png). With MOVING=1 it also checks that at rest the cell's own drops,
// signals and close-up ions move (the picture's own motion, which the legend says is no
// measured flow), and that they hold still while a part's flux shows. It says at its end
// whether the page's own font had arrived. One browser at a time:
// it takes the lock in tools/lib/browser_lock.mjs, whose profile folder is on disk and
// removed afterwards. One call is one short hold of the browser.

import { spawn } from "node:child_process";
import { writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { createServer } from "./serve.mjs";
import { acquireBrowser } from "./lib/browser_lock.mjs";
import { DEFAULT_RUNS, DEFAULT_SCENE } from "./lib/build_page.mjs";

const outDir = process.argv[2] ? path.resolve(process.argv[2]) : null;
if (outDir) await mkdir(outDir, { recursive: true });
const WIDTH = Number(process.env.WIDTH || 1400), HEIGHT = Number(process.env.HEIGHT || 900);
const NAME = process.env.NAME || "cellflux";
const MOVING = process.env.MOVING === "1";

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const results = [];
const check = (name, ok, detail = "") => {
  results.push(Boolean(ok));
  console.log(`${ok ? "pass" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`);
};
const note = (text) => console.log(`note  ${text}`);
const pageLog = [];
const release = await acquireBrowser({ wait: Number(process.env.WAIT_MINUTES || 20) * 60 * 1000 });
// SCENE and RUNS name another scene and another folder of runs to serve (a scratch scene whose species names its run, say).
const server = createServer({ offline: true, scene: process.env.SCENE ? path.resolve(process.env.SCENE) : DEFAULT_SCENE, runs: process.env.RUNS ? path.resolve(process.env.RUNS) : DEFAULT_RUNS, log: (line) => pageLog.push(line) });
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}/`;
const chrome = spawn(
  process.env.CHROME || "google-chrome",
  ["--headless=new", `--user-data-dir=${release.profile}`, "--disable-breakpad", "--no-first-run", "--no-sandbox", "--mute-audio", "--hide-scrollbars", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", `--window-size=${WIDTH},${HEIGHT}`, "--remote-debugging-port=0", "about:blank"],
  { stdio: ["ignore", "ignore", "pipe"] }
);
let failed = null, socket = null;
const failedLoads = [];
// Whether the page's own font had arrived by the end, once the page can be asked.
let fontOf = async () => "not known";
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
  await new Promise((resolve, reject) => {
    socket.onopen = resolve;
    socket.onerror = reject;
  });
  let nextId = 1;
  const waiting = new Map();
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    // A load the page asked for that failed in the network (with LOOP=1, where the page fetches the species' run).
    if (message.method === "Network.loadingFailed") failedLoads.push(message.params);
    if (message.method === "Network.requestWillBeSent" && /\/runs\//.test(message.params.request?.url || "")) failedLoads.push({ asked: message.params.request.url, at: message.params.timestamp });
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
  if (process.env.LOOP === "1") await page("Network.enable");
  if (process.env.THEME === "dark") await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "dark" }] });
  const evaluate = async (expression) => {
    const reply = await page("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (reply.exceptionDetails) throw new Error(reply.exceptionDetails.exception?.description || reply.exceptionDetails.text);
    return reply.result.value;
  };
  const V = "document.querySelector('cells-viewer')";
  const L = `${V}.current`;
  fontOf = () => evaluate(`document.fonts.status === "loaded" && ["Inter", "Space Grotesk"].every((family) => [...document.fonts].some((face) => face.family.includes(family) && face.status === "loaded")) ? "arrived" : "not arrived: the stand-in was shown, whose words run longer"`);
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
  const mouse = (type, x, y, extra = {}) => page("Input.dispatchMouseEvent", { type, x, y, button: "left", buttons: 1, clickCount: 1, ...extra });
  const click = async (x, y, wait = 500) => {
    await mouse("mouseMoved", x, y, { button: "none", buttons: 0 });
    await mouse("mousePressed", x, y);
    await mouse("mouseReleased", x, y, { buttons: 0 });
    await sleep(wait);
  };
  /** The middle of what a selector matches, if it is on the screen and nothing lies over it. */
  const middle = (selector) =>
    evaluate(`(() => { const root = ${V}.shadowRoot, el = root.querySelector(${JSON.stringify(selector)}); if (!el) return null; el.scrollIntoView({ block: "nearest" }); const r = el.getBoundingClientRect(); if (!r.width || !r.height) return null; const x = r.left + r.width / 2, y = r.top + r.height / 2; const top = root.elementFromPoint(x, y); return top && (top === el || el.contains(top)) ? { x, y } : null; })()`);
  const press = async (selector, wait = 600) => {
    const at = await middle(selector);
    if (!at) return false;
    await click(at.x, at.y, wait);
    return true;
  };
  const shot = async (name) => {
    if (!outDir) return;
    const { data } = await page("Page.captureScreenshot", { format: "png" });
    await writeFile(path.join(outDir, `${name}.png`), Buffer.from(data, "base64"));
    note(`wrote ${path.join(outDir, `${name}.png`)}`);
  };
  /** What the Cell view shows of flux now, as the page itself has it. */
  const state = () =>
    evaluate(`(() => {
      const v = ${V}, root = v.shadowRoot, lens = v.current, flux = lens.flux, stage = v.stage, cell = lens.cells[lens.sizeMode];
      const box = (el) => { const r = el.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)]; };
      const panel = root.querySelector("cells-panel");
      return {
        species: lens.species.id, mode: lens.sizeMode, on: flux.on, source: flux.source.kind, selected: v.state.selected, width: stage.width, height: stage.height,
        // The species' own looping run, where it names one: what was read of it, and where it stands.
        named: flux.named, pending: flux.source.kind === "pending" ? flux.source.why : null,
        loop: flux.loop ? { title: flux.loop.title, status: flux.loop.status, cell: flux.loop.cell, length: flux.loop.length, streams: flux.loop.streams.length, token: flux.loop.busiest, elapsed: flux.elapsed, slow: flux.slow } : null,
        timeRow: [...root.querySelectorAll('cells-legend .layer-row[data-channel="time"] button')].map((b) => b.textContent + (b.getAttribute("aria-pressed") === "true" ? "*" : "")),
        // The Speed slider: where it stands, its words for a screen reader, its marks, its box.
        slider: (() => { const input = root.querySelector("cells-legend .speed-slider"); if (!input) return null; const r = input.getBoundingClientRect(); return { value: Number(input.value), text: input.getAttribute("aria-valuetext"), now: root.querySelector("cells-legend .speed-now")?.textContent, marks: [...root.querySelectorAll("cells-legend .speed-marks span")].map((m) => m.textContent), words: [...root.querySelectorAll("cells-legend .speed-marks span")].filter((m) => m.textContent).map((m) => { const b = m.getBoundingClientRect(); return [Math.round(b.left), Math.round(b.right), Math.round(b.top)]; }), within: (() => { const b = root.querySelector("cells-legend").getBoundingClientRect(); return [Math.round(b.left), Math.round(b.right)]; })(), box: [r.left, r.top, r.right, r.bottom].map(Math.round) }; })(),
        plan: flux.plan.kinds.map((kind) => kind.id), withheld: flux.plan.withheld.map((item) => item.id), shown: flux.showing().kinds.map((kind) => kind.id),
        parts: flux.plan.kinds.map((kind) => lens.capabilityByPart.get(kind.part).id),
        tokens: flux.tokens.map((set) => ({ zone: set.zone.name, lanes: set.lanes.length, beads: set.tokens.drawn.beads, heads: set.tokens.drawn.heads, chevrons: set.tokens.drawn.chevrons, stream: Number(set.tokens.blend.stream.toFixed(2)), streaks: set.tokens.flow.time, visible: set.tokens.group.visible, opacity: set.tokens.materials[0].opacity, first: set.tokens.lanes[0].beads[0] ?? null })),
        bloom: stage.finish?.bloom?.strength ?? 0, shining: stage.finish?.sources?.size ?? 0, holds: [...stage.decoration.holds], moving: stage.decoration.moving, still: flux.still(),
        rows: [...root.querySelectorAll("cells-legend .layer-row")].map((row) => row.dataset.channel + ": " + [...row.querySelectorAll("button")].map((b) => b.textContent + (b.getAttribute("aria-pressed") === "true" ? "*" : "")).join(" | ")),
        notice: root.querySelector("cells-legend .layer-example")?.textContent ?? null,
        hint: root.querySelector("cells-legend .layer-hint")?.textContent ?? null,
        keys: [...root.querySelectorAll("cells-legend .legend-key")].map((p) => p.textContent),
        cannot: [...root.querySelectorAll("cells-legend .layer-cannot")].map((p) => p.textContent),
        legendBox: box(root.querySelector("cells-legend")),
        // The legend is capped and scrolls: the switch must be in sight without scrolling.
        switchBox: (() => { const button = root.querySelector('cells-legend .layer-row[data-channel="motion"] button[data-layer="flux"]'); return button && button.getBoundingClientRect().height > 0 ? box(button) : null; })(),
        legendScroll: root.querySelector("cells-legend").scrollTop,
        fonts: document.fonts.status + ", " + [...document.fonts].filter((face) => face.status === "loaded").length + " of " + document.fonts.size + " faces loaded",
        viewBox: (() => { const card = root.querySelector(".view"); return card && !card.hidden && card.getBoundingClientRect().height > 0 ? box(card) : null; })(),
        said: [...root.querySelectorAll(".label-example, .label-flow")].map((el) => ({ text: el.textContent, shown: !el.classList.contains("is-off"), box: box(el) })),
        panel: !panel || panel.hidden ? null : { title: panel.querySelector("h2")?.textContent ?? null, text: panel.textContent, box: box(panel) },
        old: { drops: cell.streams.flatMap((stream) => stream.drops).filter((drop) => drop.visible).length, signals: cell.signals.filter((bead) => bead.visible).length, ions: cell.molecule.ions.filter((ion) => ion.visible).length },
        // Where the cell's own first drop, signal and close-up ion stand now.
        oldAt: [cell.streams[0]?.drops[0], cell.signals[0], cell.molecule.ions[0]].map((item) => (item ? item.position.toArray().map((n) => Math.round(n * 1e6) / 1e6).join() : null)),
        foot: [...root.querySelectorAll(".scalebar, .look-box, .caveat")].filter((el) => !el.hidden && el.getBoundingClientRect().height > 0).map((el) => [el.className.split(" ")[0], ...box(el)]),
      };
    })()`);
  /** The notice the picture and the legend carry: the run's own status where the species plays its run, else illustration's. */
  const noticeOf = (now) => (now.source === "run" ? now.loop?.status : "Illustration: not a run");
  /**
   * Look again until the page shows what is waited for; the last look is returned either way. It waits up to 40 s:
   * drawn in software, the first frame with the bloom's passes can take many seconds, and the labels are laid out
   * only once a frame is drawn.
   */
  const until = async (test) => {
    let now = await state();
    for (let tries = 0; tries < 160 && !test(now); tries++) {
      await sleep(250);
      now = await state();
    }
    return now;
  };

  const ADDRESS = process.env.ADDRESS === "1" ? process.env.PART || "cap.pumps" : null;
  const query = ["lens=cell", MOVING ? null : "still=1", process.env.SPECIES ? `species=${process.env.SPECIES}` : null, process.env.SIZE ? `size=${process.env.SIZE}` : null, process.env.SCALE ? `scale=${process.env.SCALE}` : null, ADDRESS ? `select=${ADDRESS}` : null].filter(Boolean).join("&");
  await page("Page.navigate", { url: `${base}?${query}` });
  let drawn = false;
  for (let tries = 0; tries < 1440 && !drawn; tries++) {
    await sleep(250);
    drawn = await evaluate(`Boolean(${V} && ${V}.current && ${V}.stage && ${V}.state.lens === "cell" && ${L}.flux && ${L}.cells)`).catch(() => false);
  }
  if (!drawn) throw new Error("the Cell view was not drawn within six minutes of opening the page");
  await rest();
  await sleep(500);

  let s = await state();
  // A species that names its own run: the page fetches the run after it opens. Nothing is judged until the run is
  // read, or cannot be had: a plan read while the run was on its way was empty, and a scenario then left out its
  // presses on a part without failing (17 November 2026: 18 checks where 32 were due).
  if (s.named && process.env.LOOP !== "1") {
    s = await until((now) => now.source === "run" || (now.source === "pending" && !/being fetched/.test(now.pending || "")));
    check("the species' own run is read before its flux is judged, and it gives parts a flux", s.source === "run" && s.plan.length > 0, JSON.stringify([s.named, s.source, s.pending, s.plan]));
  }
  if (process.env.LOOP === "1") {
    // ---------------------------------------------------------- the species' own looping run (rule 7)
    s = await until((now) => now.source === "run" || (now.source === "pending" && !/being fetched/.test(now.pending || "")));
    note(`species ${s.species}, ${s.width} by ${s.height}; fonts: ${s.fonts}; it names ${s.named}; ${JSON.stringify(s.loop)}`);
    check("the species names its own run, and the page fetches and reads it: no illustration stands in", s.source === "run" && s.loop?.length > 0 && s.loop.streams > 0, JSON.stringify([s.source, s.pending, s.loop]));
    if (s.source !== "run") note(`the page's loads of runs, and the loads that failed: ${JSON.stringify(failedLoads).slice(0, 1500)}`);
    check("nothing flows as the page opens, run or no run", s.tokens.length === 0 && s.bloom === 0 && s.said.every((item) => !item.shown), JSON.stringify([s.tokens.length, s.bloom]));
    // A real press on the legend's Flux switch: all of the run that this cell draws.
    const all = 'cells-legend .layer-row[data-channel="motion"] button[data-layer="flux"]';
    let opened = false, reached = await press(all);
    if (!reached) {
      opened = await press("cells-legend .legend-toggle");
      reached = await press(all);
    }
    s = await until((now) => now.on && now.tokens.length > 0 && now.said.some((item) => item.shown));
    if (opened) await press("cells-legend .legend-toggle");
    await rest();
    s = await until((now) => now.said.some((item) => item.shown));
    const said = s.said.filter((item) => item.shown).map((item) => item.text);
    check("a real press on All draws the run's lanes, with bloom", reached && s.on && s.tokens.length > 0 && s.bloom > 0, JSON.stringify([reached, s.tokens, s.bloom]));
    check("the picture says what the run is: a development run of the engine, not judged, as the catalogue says", said.includes("Development run of the engine, not judged"), JSON.stringify(said));
    check("the picture names the run, says that it loops and how long the loop is, the token, the speed, and what the cell takes from the run", said.some((text) => /Planarian loop \(development run\)/.test(text) && /a loop of 2 s of the cell's time/.test(text) && /Streams as wide as their rates: full width is [\d,]+ ions a second( · |\n)true speed/.test(text) && /From the run's lumped cell cell_3/.test(text) && /Not a measurement of a living cell/.test(text)), JSON.stringify(said));
    check("the legend carries what the run is, and the Speed slider at true speed, its marks' words on one line inside the legend with none meeting another, and its words", s.notice === "Development run of the engine, not judged" && s.slider?.value === 0 && s.slider.now === "True" && JSON.stringify(s.slider.marks) === JSON.stringify(["True", "1/1,000", "1/1,000,000", ""]) && s.slider.words.length === 3 && s.slider.words.every((box, k, all) => box[2] === all[0][2] && (k === 0 || box[0] > all[k - 1][1]) && box[0] >= s.slider.within[0] && box[1] <= s.slider.within[1]) && /^True speed: one second here is one second of the run/.test(s.slider.text) && s.slider.box[3] - s.slider.box[1] >= 44, JSON.stringify([s.notice, s.slider]));
    check("the legend says which part takes a flux from which record, and how closely the run closes", s.keys.some((text) => /Drawn: channels from channel_transferred/.test(text)) && s.keys.some((text) => /meets its first within 2\.8e-5 \(tolerance 1\.0e-4\)/.test(text)), JSON.stringify(s.keys.filter((text) => /Drawn:|meets its first/.test(text))));
    await shot(`${NAME}-loop`);
    if (MOVING) {
      const before = s.loop.elapsed;
      const later = await until((now) => now.loop.elapsed > before + 0.2);
      check("at true speed the loop's time runs as the watching does", later.loop.elapsed > before + 0.2, JSON.stringify([before, later.loop.elapsed]));
    }
    // The cost of a frame while the loop plays: the stage's own draw with gl.finish, the whole handler, and the flux's own share.
    if (MOVING) {
      const cost = await evaluate(`(async () => {
        const v = ${V}, st = v.stage, gl = st.renderer.getContext(), flux = v.current.flux;
        const draw0 = st.draw, frame0 = st.frame, step0 = flux.frame, drawMs = [], frameMs = [], fluxMs = [];
        st.draw = function () { const t = performance.now(); draw0.call(this); gl.finish(); drawMs.push(performance.now() - t); };
        st.frame = function (time) { const t = performance.now(); frame0.call(this, time); frameMs.push(performance.now() - t); };
        flux.frame = function () { const t = performance.now(); const out = step0.call(this); fluxMs.push(performance.now() - t); return out; };
        st.invalidate();
        await new Promise((r) => setTimeout(r, 4000));
        delete st.draw; delete st.frame; delete flux.frame;
        const mid = (a) => (a.length ? Math.round(a.slice().sort((x, y) => x - y)[Math.floor(a.length / 2)] * 100) / 100 : null);
        const high = (a) => (a.length ? Math.round(a.slice().sort((x, y) => x - y)[Math.floor(a.length * 0.95)] * 100) / 100 : null);
        const info = st.renderer.info.render, ext = gl.getExtension("WEBGL_debug_renderer_info");
        return { frames: frameMs.length, draw: mid(drawMs), handler: mid(frameMs), handler95: high(frameMs), flux: mid(fluxMs), flux95: high(fluxMs), calls: info.calls, triangles: info.triangles, renderer: String(ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)) };
      })()`);
      note(`frame cost with the loop playing: ${JSON.stringify(cost)}`);
      // The flux's own work (its rates, its beads, its words) is held small; the whole frame's cost is reported, not judged here:
      // on the card it is the look's and the bloom's (see the hand-over of 16 November 2026, flux round 2).
      check("the flux's own work in a frame is small beside a frame at 60 a second", cost.flux !== null && cost.flux < 1.5, JSON.stringify(cost));
    }
    // The Speed slider, for real: a press at each mark and between, a drag along it, and the keyboard. At each place, measured in the
    // page over a few seconds: the beads set out a second on the busiest lane, how long one takes to cross, and how much of the
    // stream shows. On a narrow window the legend is folded behind its title: a real press opens it first.
    if (!(await middle("cells-legend .speed-slider"))) await press("cells-legend .legend-toggle");
    // Where the slider stands is looked up before each press: the legend's words change with the speed, and its rows move.
    let sliderBox = null;
    const findSlider = async () => (sliderBox = await evaluate(`(() => { const r = ${V}.shadowRoot.querySelector("cells-legend .speed-slider").getBoundingClientRect(); return { left: r.left, right: r.right, y: r.top + r.height / 2 }; })()`));
    await findSlider();
    // A native range's thumb travels between its two half-widths: the place of a value on the screen.
    const xAt = (position) => sliderBox.left + 8 + position * (sliderBox.right - sliderBox.left - 16);
    const measure = () => evaluate(`(async () => {
      const flux = ${L}.flux, set = flux.tokens[0], tokens = set.tokens;
      const lane = tokens.lanes.reduce((most, item) => (item.perSecond > most.perSecond ? item : most), tokens.lanes[0]);
      // Beads set out: the whole ones counted and the share of the next one on its way to setting out.
      const sent = (lane.sent || 0) + lane.due, t0 = performance.now(), seen = [];
      for (let i = 0; i < 40; i++) { await new Promise((r) => setTimeout(r, 100)); seen.push({ t: performance.now(), beads: lane.beads.slice(), sent: lane.sent || 0 }); }
      const seconds = (performance.now() - t0) / 1000, sentNow = (lane.sent || 0) + lane.due;
      // A bead's crossing, from how far the beads moved between two looks (the same bead: counted from the first set out).
      const rates = [];
      for (let k = 1; k < seen.length; k++) {
        const a = seen[k - 1], b = seen[k], dt = (b.t - a.t) / 1000, gone = (b.sent - a.sent) - (b.beads.length - a.beads.length);
        for (let i = 0; i < a.beads.length; i++) { const j = i - gone; if (j >= 0 && j < b.beads.length && b.beads[j] > a.beads[i]) rates.push((b.beads[j] - a.beads[i]) / dt); }
      }
      rates.sort((x, y) => x - y);
      return { slow: flux.slow, mode: tokens.mode, perSecond: Number(lane.perSecond.toFixed(3)), setOut: Number(((sentNow - sent) / seconds).toFixed(2)), crossing: rates.length ? Number((1 / rates[Math.floor(rates.length / 2)]).toFixed(2)) : null, stream: Number(tokens.blend.stream.toFixed(2)), stretch: Number(tokens.blend.stretch.toFixed(2)), statement: flux.said?.ways[0] || "" };
    })()`);
    const steps = [];
    for (const [name, position] of [["the start", 0], ["between the start and the middle", 0.25], ["the middle mark", 0.5], ["the three-quarter mark", 0.75], ["the end", 1]]) {
      await findSlider();
      await click(xAt(position), sliderBox.y, 400);
      s = await until((now) => Math.abs((now.slider?.value ?? -1) - position) < 0.02);
      const seen = await measure();
      steps.push({ name, position, slider: s.slider?.value, now: s.slider?.now, ...seen });
    }
    note(`along the slider: ${JSON.stringify(steps.map(({ statement, ...rest }) => rest))}`);
    const [start, , middleMark, three, end] = steps;
    check("a real press at the start, the two marks and the end puts the slider there, and the page follows", steps.every((step) => Math.abs(step.slider - step.position) < 0.02) && start.slow === 1 && Math.abs(Math.log10(middleMark.slow) - 3) < 0.05 && Math.abs(Math.log10(three.slow) - 6) < 0.05 && Math.abs(Math.log10(end.slow) - 7) < 0.05, JSON.stringify(steps.map((step) => [step.position, step.slider, step.slow, step.now])));
    check("at true speed the lanes are streams, with no bead to count; at the middle mark packets; at three quarters single beads", start.mode === "stream" && start.stream > 0.9 && middleMark.mode === "packets" && middleMark.stream < 0.05 && three.mode === "beads" && three.stretch < 1.05, JSON.stringify(steps.map((step) => [step.position, step.mode, step.stream, step.stretch])));
    // From the middle mark on, beads are counted: at each step fewer set out a second on the busiest lane and each crosses more slowly, by a factor the eye sees.
    const counted = [middleMark, three, end];
    if (MOVING) check("from mark to mark, fewer beads set out a second and each crosses more slowly, both: from the middle to three quarters one of the two halves, and on to the end it falls by half again", counted.every((step, k) => k === 0 || ((step.setOut < counted[k - 1].setOut * 0.8 && step.crossing > counted[k - 1].crossing * (k === 1 ? 1.2 : 1.1)) && Math.max(counted[k - 1].setOut / Math.max(1e-9, step.setOut), step.crossing / counted[k - 1].crossing) >= (k === 1 ? 1.9 : 1.5))) && middleMark.crossing > 2.3 && middleMark.crossing < 2.9 && three.crossing > 3.7 && three.crossing < 4.5, JSON.stringify(counted.map((step) => [step.position, step.setOut, step.perSecond, step.crossing])));
    check("the statement follows the slider: streams at true speed, a packet's and then a bead's number slowed", /Streams as wide as their rates/.test(start.statement) && /One packet is [\d,]+ ions/.test(middleMark.statement) && /One bead is [\d,]+ ions?/.test(three.statement) && /One bead is 2 ions/.test(end.statement), JSON.stringify(steps.map((step) => step.statement.split("\n")[1])));
    // A drag along it, for real: from the start to the middle mark, the picture follows the hand without a jump.
    await findSlider();
    await click(xAt(0), sliderBox.y, 300);
    await findSlider();
    const path = [];
    await mouse("mouseMoved", xAt(0), sliderBox.y, { button: "none", buttons: 0 });
    await mouse("mousePressed", xAt(0), sliderBox.y);
    for (let k = 1; k <= 10; k++) {
      await mouse("mouseMoved", xAt(k * 0.05), sliderBox.y, { buttons: 1 });
      await sleep(120);
      path.push(await evaluate(`(() => { const t = ${L}.flux.tokens[0].tokens; return [Number(${L}.flux.slow.toPrecision(3)), Number(t.blend.stream.toFixed(2)), Number(t.blend.stretch.toFixed(2))]; })()`));
    }
    await mouse("mouseReleased", xAt(0.5), sliderBox.y, { buttons: 0 });
    note(`a drag from the start to the middle: ${JSON.stringify(path)}`);
    check("dragged, the slow-down grows and the stream thins step by step, with no jump", path.length === 10 && path.every((step, k) => k === 0 || (step[0] >= path[k - 1][0] && step[1] <= path[k - 1][1] + 1e-9 && Math.abs(step[1] - path[k - 1][1]) < 0.4)) && path.at(-1)[0] > 500, JSON.stringify(path));
    // The keyboard: Home to the start, the arrows step it, End to its end; a screen reader hears the speed in words.
    await evaluate(`${V}.shadowRoot.querySelector("cells-legend .speed-slider").focus()`);
    const key = async (name) => {
      await page("Input.dispatchKeyEvent", { type: "rawKeyDown", key: name, code: name, windowsVirtualKeyCode: { Home: 36, End: 35, ArrowRight: 39, ArrowLeft: 37 }[name] });
      await page("Input.dispatchKeyEvent", { type: "keyUp", key: name, code: name, windowsVirtualKeyCode: { Home: 36, End: 35, ArrowRight: 39, ArrowLeft: 37 }[name] });
      await sleep(250);
      return state();
    };
    const home = await key("Home"), right = await key("ArrowRight"), last = await key("End");
    check("the keyboard: Home to true speed, an arrow steps it, End to its end, the speed said in words", home.loop?.slow === 1 && right.loop?.slow > 1 && Math.abs(Math.log10(last.loop?.slow) - 7) < 0.05 && /^Slowed 10,000,000 times: one second here is 100 nanoseconds of the run/.test(last.slider?.text || ""), JSON.stringify([home.loop?.slow, right.loop?.slow, last.loop?.slow, last.slider?.text]));
    // Back to the middle mark for the picture of the run slowed.
    await findSlider();
    await click(xAt(0.5), sliderBox.y, 600);
    s = await until((now) => Math.abs((now.slider?.value ?? -1) - 0.5) < 0.02 && now.said.some((item) => item.shown && /slowed 1,000 times/.test(item.text)));
    const slowed = s.said.filter((item) => item.shown).map((item) => item.text);
    check("slowed a thousand times the picture says so, with the interval's place in the loop", Math.abs(Math.log10(s.loop?.slow) - 3) < 0.02 && slowed.some((text) => /One packet is [\d,]+ ions( · |\n)slowed 1,000 times(: packets, crossing more slowly|, shown still)?( · |\n)mean of [\d.]+ s to [\d.]+ s of the loop/.test(text)), JSON.stringify([s.loop?.slow, slowed]));
    await shot(`${NAME}-loop-slowed`);
    // The panel behind all of it: what the cell takes from the run, and the run's own words for itself.
    if (opened) await press("cells-legend .legend-toggle");
    await press("cells-legend .layer-keys summary");
    if (await press("cells-legend .layer-details")) {
      s = await until((now) => now.panel?.title === "What flows in this cell");
      check("a panel says what the cell takes from the run, the run's own words for itself, its closure and its revision", /What this cell takes from the run/.test(s.panel?.text || "") && /The run's own words for itself/.test(s.panel.text) && /Made by the engine at revision b08af640/.test(s.panel.text), (s.panel?.text || "no panel").slice(0, 300));
      await shot(`${NAME}-loop-panel`);
    } else note("the door to the panel behind the flux could not be pressed at this size");
  } else if (ADDRESS) {
    // ---------------------------------------------------------- a part named in the page's address
    check(`the address names ${ADDRESS}: it is chosen as the page opens, and its panel is open`, s.selected === ADDRESS && Boolean(s.panel), JSON.stringify([s.selected, s.panel?.title]));
    check("nothing flows as the page opens: no bead, no bloom, the look's own motion free, nothing said of flux on the picture", s.tokens.length === 0 && s.bloom === 0 && !s.holds.includes("flux") && s.said.every((item) => !item.shown), JSON.stringify([s.tokens.length, s.bloom, s.holds, s.said]));
    check("the legend carries no notice while nothing shows", s.notice === null, String(s.notice));
    await shot(`${NAME}-address`);
    // A real press on the name of the very part the address chose: the visitor's own choice.
    const pressed = await press(`.label[data-label="${ADDRESS}"]`);
    if (pressed) {
      s = await until((now) => now.tokens.length > 0 && now.said.some((item) => item.shown));
      check("a real press on that part's name shows its flux", s.selected === ADDRESS && s.tokens.length > 0 && s.bloom > 0 && s.said.some((item) => item.shown), JSON.stringify([s.selected, s.tokens.length, s.bloom]));
    } else note(`the name of ${ADDRESS} could not be pressed with its panel open at this size`);
  } else {
  // ------------------------------------------------------------ at rest
  note(`species ${s.species}, ${s.mode}, ${s.width} by ${s.height}; fonts: ${s.fonts}; flux may show for ${JSON.stringify(s.plan)}; not drawn ${JSON.stringify(s.withheld)}`);
  // Where the legend stands open (a window 760 px wide or more), the switch is in sight without scrolling.
  const inSight = (now) => now.switchBox && now.legendScroll === 0 && now.switchBox[1] >= now.legendBox[1] && now.switchBox[3] <= now.legendBox[3];
  if (s.width >= 760) check("at rest the Flux switch is in sight in the legend, without scrolling", inSight(s), JSON.stringify({ switch: s.switchBox, legend: s.legendBox, scrolled: s.legendScroll }));
  check("the page opens with nothing flowing: no bead, no bloom, the look's own motion not held by flux", s.tokens.length === 0 && s.bloom === 0 && !s.holds.includes("flux") && s.on === false, JSON.stringify([s.tokens.length, s.bloom, s.holds]));
  check("nothing on the picture speaks of flux", s.said.every((item) => !item.shown), JSON.stringify(s.said));
  // The legend now carries the Flux block: it must not reach up over the view's card.
  const clear = (now) => !now.viewBox || now.legendBox[1] >= now.viewBox[3] || now.legendBox[0] >= now.viewBox[2] || now.legendBox[2] <= now.viewBox[0];
  check("at rest the legend, with its Flux switch, stands clear of the view's card", clear(s), JSON.stringify({ legend: s.legendBox, view: s.viewBox }));
  const atRest = s.old;
  await shot(`${NAME}-rest`);
  if (MOVING) {
    // At rest the cell's own tokens move: the picture's own motion, and the legend says it is no measured flow.
    const before = s.oldAt;
    const later = await until((now) => now.oldAt.some((at, k) => at !== null && at !== before[k]));
    check("at rest the cell's own drops, signals and ions move, and the legend says that motion is the picture's own", later.oldAt.some((at, k) => at !== null && at !== before[k]) && /What moves at rest is the picture's own, not a measured flow\./.test(later.hint || ""), JSON.stringify([before, later.oldAt, later.hint]));
  }

  // ------------------------------------------------------------ a part is chosen
  // A part whose name stands on the picture now, so that it can be pressed: a name may have given way to another.
  const named = await evaluate(`[...${V}.shadowRoot.querySelectorAll(".label[data-label]")].filter((el) => !el.classList.contains("is-off")).map((el) => el.dataset.label)`);
  const part = process.env.PART || s.parts.find((id) => named.includes(id)) || s.parts[0];
  if (part) {
    const kind = s.plan[s.parts.indexOf(part)];
    const pressed = await press(`.label[data-label="${part}"]`);
    if (!pressed) {
      note(`the name of ${part} could not be pressed at this size; it is chosen through the page instead`);
      await evaluate(`${V}.select(${JSON.stringify(part)})`);
    }
    s = await until((now) => now.tokens.length > 0 && now.said.some((item) => item.shown));
    await rest();
    s = await state();
    check(`${pressed ? "a real press on" : "choosing"} ${part} shows that part's flux alone`, s.selected === part && JSON.stringify(s.shown) === JSON.stringify([kind]) && s.tokens.length > 0 && s.tokens.every((set) => set.lanes > 0), JSON.stringify([s.selected, s.shown, s.tokens]));
    // The way is told by chevrons along each lane (since 17 November 2026); a run at true speed is a stream, with no bead to count.
    // Of the lanes that show where the camera stands: to scale, the cell's own lanes give way to the close-up's as it comes close, and a set faded out is not drawn.
    const seen = s.tokens.filter((set) => set.visible);
    // Where none shows (to scale, close to the membrane, a part with no lane in the close-up), the picture says where it is drawn.
    const where = s.said.some((item) => item.shown && /Seen (at the cell's stop|closer in)/.test(item.text));
    check("where the camera stands some lanes show, each with its chevrons pointing its way and beads or a stream on it; or the picture says where they are drawn", seen.length > 0 ? seen.every((set) => set.chevrons > 0 && (set.beads > 0 || set.stream > 0.9)) : where, JSON.stringify([s.tokens, where]));
    check("the bloom is on, what shines is marked, and the look's own motion is held", s.bloom > 0 && s.shining >= 2 && s.holds.includes("flux") && s.moving === false, JSON.stringify([s.bloom, s.shining, s.holds, s.moving]));
    // A species with its own run says what the run is, where one without says "Illustration: not a run" (rules 7 and 11).
    const notice = s.said.find((item) => item.text === noticeOf(s));
    if (s.source === "run") check("the picture says what the run is, and names the run", notice?.shown && s.said.some((item) => item.shown && /(a loop of|loops every) [\d.]+ (s|ms|min)/.test(item.text)), JSON.stringify(s.said));
    else check("the picture says \"Illustration: not a run\", and what form it is", s.source === "illustration" && notice?.shown && s.said.some((item) => item.shown && /^Direction only:/.test(item.text)), JSON.stringify(s.said));
    check("the statement stands on the picture, under the top bar and inside the window", s.said.filter((item) => item.shown).every((item) => item.box[1] >= 56 && item.box[0] >= 0 && item.box[2] <= s.width), JSON.stringify(s.said.map((item) => item.box)));
    check("the part's panel carries the notice and the basis", s.panel && (s.source === "run" ? s.panel.text.includes(`Flux, from the looping run. ${noticeOf(s)}`) : /Flux\. Illustration: not a run/.test(s.panel.text)), s.panel ? s.panel.title : "no panel");
    // With a panel open beside it or above it, the scale bar and its words stand clear of the caveat under the picture.
    const foot = Object.fromEntries(s.foot.map(([name, ...edges]) => [name, edges]));
    const apart = (a, b) => !a || !b || a[2] <= b[0] || b[2] <= a[0] || a[3] <= b[1] - 2 || b[3] <= a[1] - 2;
    check("with the part's panel open the scale bar and its words stand clear of the caveat", apart(foot.scalebar, foot.caveat), JSON.stringify(s.foot));
    check("the switch itself stays off: the part was chosen, not the switch", s.on === false, JSON.stringify(s.rows));
    check("the picture's own tokens of other parts stand as they stood", (kind === "water" || s.old.drops === atRest.drops) && (kind === "secretion" || s.old.signals === atRest.signals), JSON.stringify([atRest, s.old]));
    if (MOVING) {
      // While flux shows, the cell's own tokens hold still where they stood.
      const held = s.oldAt;
      await sleep(1500);
      const again = await state();
      check("while flux shows the cell's own tokens hold where they stood", JSON.stringify(again.oldAt) === JSON.stringify(held), JSON.stringify([held, again.oldAt]));
    }
    if (MOVING) {
      // A bead is somewhere else a moment later: by more than rounding, and not by a whole turn of its lane.
      // A bead moves; or, where the lanes are streams (a run at true speed), the streaks run on.
      const before = s.tokens[0].first, streaks = s.tokens[0].streaks, stream = s.tokens[0].stream > 0.9;
      const moved = (now) => (stream ? now.tokens[0]?.streaks > streaks + 0.1 : typeof now.tokens[0]?.first === "number" && Math.abs(now.tokens[0].first - before) > 1e-3);
      const later = await until(moved);
      check(stream ? "the streams' streaks run" : "a bead moves", moved(later) && later.still === false, JSON.stringify([before, streaks, later.tokens[0]?.first, later.tokens[0]?.streaks]));
    } else if (s.source === "run" && (s.width < 600 || !s.said.some((item) => item.shown && /shown still/.test(item.text)))) {
      // A phone's picture, or a short window's, keeps the run's notice and its name; the legend says that the beads stand.
      check("opened still, the beads stand and the legend says so", s.still === true && s.keys.some((text) => /Shown still here/.test(text)), JSON.stringify(s.keys));
    } else check("opened still, the beads stand and the picture says so", s.still === true && s.said.some((item) => /shown still($| · |\n)/m.test(item.text)), JSON.stringify(s.said.map((item) => item.text)));
    await shot(`${NAME}-part`);
    // With the part's panel still open, a real press reaches the Flux switch: on a narrow window the legend's title
    // stands on the top edge of the panel, which is a sheet along the bottom there, and the legend opens upward.
    const flux = 'cells-legend .layer-row[data-channel="motion"] button[data-layer="flux"]', fluxOff = 'cells-legend .layer-row[data-channel="motion"] button[data-layer=""]';
    let unfolded = false, reachedAll = await press(flux);
    if (!reachedAll) {
      unfolded = await press("cells-legend .legend-toggle");
      reachedAll = await press(flux);
    }
    s = await until((now) => now.on === true);
    const above = (now) => !now.panel || now.width >= 760 || now.legendBox[3] <= now.panel.box[1];
    check(`with the part's panel open a real press reaches the Flux switch${unfolded ? ", behind the legend's title on the panel's edge" : ""}; the part stays chosen and its panel open`, reachedAll && s.on === true && s.selected === part && Boolean(s.panel) && above(s), JSON.stringify({ reached: reachedAll, unfolded, on: s.on, selected: s.selected, legend: s.legendBox, panel: s.panel?.box }));
    // And back as it was: a real press on Off, and the legend folded again, before the part is let go.
    const reachedOff = await press(fluxOff);
    s = await until((now) => now.on === false);
    if (unfolded) await press("cells-legend .legend-toggle");
    check("and a real press on Off turns it off again, the part still chosen", reachedOff && s.on === false && s.selected === part, JSON.stringify({ reached: reachedOff, on: s.on, selected: s.selected }));
    await evaluate(`${V}.select(null)`);
    // The labels are laid out with the next frame drawn: wait for it.
    s = await until((now) => now.tokens.length === 0 && now.said.every((item) => !item.shown));
    check("with nothing chosen nothing flows again, and the stage is as it was", s.tokens.length === 0 && s.bloom === 0 && !s.holds.includes("flux") && s.said.every((item) => !item.shown), JSON.stringify([s.tokens.length, s.bloom, s.holds]));
  } else note("this species has nothing a direction or a both-ways lane is drawn for");

  // ------------------------------------------------------------ the switch
  const all = 'cells-legend .layer-row[data-channel="motion"] button[data-layer="flux"]';
  let reached = await press(all), opened = false;
  if (!reached) {
    // On a narrow window the legend is folded behind its title: a real press opens it.
    opened = await press("cells-legend .legend-toggle");
    reached = await press(all);
  }
  check(opened ? "the Flux switch stands in the legend, behind its title, and can be pressed once the legend is open" : "the Flux switch stands in the legend and can be pressed", reached, JSON.stringify(s.rows));
  s = await until((now) => now.on === true && (now.plan.length === 0 || now.tokens.length > 0));
  // The legend that was opened to reach the switch lies over the picture: a real press on its title closes it again.
  if (opened) await press("cells-legend .legend-toggle");
  await rest();
  // The labels are laid out once the frame is drawn: wait for the statement to stand on the picture.
  s = await until((now) => now.plan.length === 0 || now.said.some((item) => item.shown));
  check("the switch shows all that the species' file allows, under one legend", s.on && JSON.stringify(s.shown) === JSON.stringify(s.plan) && s.rows.some((row) => /All\*/.test(row)), JSON.stringify([s.shown, s.rows]));
  if (s.plan.length) {
    check(`the legend carries the notice for as long as the ${s.source === "run" ? "run" : "illustration"} shows`, s.notice === noticeOf(s), String(s.notice));
    if (s.source === "run") check("the legend says what is drawn and what it stands for, and whose word a direction is", s.keys.some((text) => /^(Streams as wide as their rates|One (bead|packet) is [\d,]+ )/.test(text)) && s.keys.some((text) => /by the run's own signs/.test(text)), JSON.stringify(s.keys));
    else check("the legend says what a bead stands for and whose word a direction is", s.keys.some((text) => /stand for no number/.test(text)) && s.keys.some((text) => /no direction is claimed|law of the engine/.test(text)), JSON.stringify(s.keys));
  }
  check("what is not drawn is named in the legend with its reason", s.withheld.length === 0 || s.cannot.length === s.withheld.length || /not drawn/.test(JSON.stringify(s.keys) + (await evaluate(`${V}.shadowRoot.querySelector("cells-legend .layer-cannots summary")?.textContent ?? ""`))), JSON.stringify(s.cannot));
  check("with all of it on the legend still stands clear of the view's card", clear(s), JSON.stringify({ legend: s.legendBox, view: s.viewBox }));
  if (s.width >= 760) check("and the switch is still in sight without scrolling", inSight(s), JSON.stringify({ switch: s.switchBox, legend: s.legendBox, scrolled: s.legendScroll }));
  if (s.plan.length) check("the picture says what it shows for as long as it shows it", s.said.some((item) => item.shown && item.text === noticeOf(s)), JSON.stringify(s.said));
  check("the statement on the picture lies over no card and not in the foot", s.said.filter((item) => item.shown).every((item) => item.box[3] < s.height * 0.62 && (!s.viewBox || item.box[1] >= s.viewBox[3] || item.box[0] >= s.viewBox[2])), JSON.stringify({ said: s.said.map((item) => item.box), view: s.viewBox }));
  note(`all: ${JSON.stringify({ tokens: s.tokens, bloom: s.bloom, legendBox: s.legendBox, viewBox: s.viewBox, said: s.said, foot: s.foot })}`);
  await shot(`${NAME}-all`);
  // The signs, what is not drawn and the door to the panel keep to one line: a real press opens it.
  if (opened) await press("cells-legend .legend-toggle");
  await press("cells-legend .layer-keys summary");
  if (await press("cells-legend .layer-details")) {
    s = await until((now) => now.panel?.title === "What flows in this cell");
    check("a panel says what stands behind all of it", s.panel?.title === "What flows in this cell" && /Not drawn|Drawn/.test(s.panel.text), s.panel?.title ?? "no panel");
    await evaluate(`${V}.select(null)`);
  } else note("the door to the panel behind the flux could not be pressed at this size");
  // A press that has begun must arrive even where the view asks the legend to draw itself again before the
  // press is let go: a real press on this switch was lost that way (16 November 2026, when the checks first
  // ran on a graphics card and the view's changes came between the press and its release).
  const offSwitch = 'cells-legend .layer-row[data-channel="motion"] button[data-layer=""]';
  const held = await middle(offSwitch);
  if (held) {
    await mouse("mouseMoved", held.x, held.y, { button: "none", buttons: 0 });
    await mouse("mousePressed", held.x, held.y);
    const waited = await evaluate(`(() => { const v = ${V}, legend = v.shadowRoot.querySelector("cells-legend"); legend.said = null; v.renderChrome(); return Boolean(legend.waiting); })()`);
    await mouse("mouseReleased", held.x, held.y, { buttons: 0 });
    s = await until((now) => now.on === false);
    check("a press on the Flux switch arrives although the legend was asked to draw again while it was held", s.on === false && waited, JSON.stringify([s.on, waited]));
  } else note("the Flux switch's Off could not be pressed at this size");
  await evaluate(`${L}.setLayer("flux", false)`);
  // The picture's own tokens come back with the next frame drawn: wait for it.
  s = await until((now) => now.tokens.length === 0 && now.old.drops === atRest.drops && now.old.signals === atRest.signals && now.old.ions === atRest.ions);
  check("switched off, nothing flows and the stage is as it was", s.tokens.length === 0 && s.bloom === 0 && !s.holds.includes("flux") && s.old.drops === atRest.drops && s.old.signals === atRest.signals && s.old.ions === atRest.ions, JSON.stringify([s.tokens.length, s.bloom, s.holds, s.old]));
  }
  const errors = pageLog.filter((line) => /error|exception/i.test(line));
  check("the page logged no error", errors.length === 0, errors.slice(0, 3).join(" / "));
} catch (error) {
  failed = error;
} finally {
  // Whether the page's own font had arrived by the end: with the stand-in, words run longer and cards stand
  // taller, and a miss is read against that.
  note(`the page's own font: ${await fontOf().catch(() => "not known")}`);
  socket?.close();
  // The browser is gone before the lock is given back, so that its profile folder can be removed.
  const closed = new Promise((resolve) => chrome.once("close", resolve));
  chrome.kill();
  await Promise.race([closed, sleep(4000)]);
  if (chrome.exitCode === null && chrome.signalCode === null) chrome.kill("SIGKILL");
  await Promise.race([closed, sleep(2000)]);
  server.close();
  release();
}
if (failed) {
  console.error(`check_cellflux: ${failed.stack || failed}`);
  process.exit(2);
}
const passed = results.filter(Boolean).length;
console.log(`${passed} of ${results.length} checks passed`);
process.exit(passed === results.length ? 0 : 1);
