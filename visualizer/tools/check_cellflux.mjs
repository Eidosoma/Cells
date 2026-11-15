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
// scene's own first choice otherwise), SIZE (schematic or real), THEME (dark), MOVING (1:
// the page is not opened still, and the check waits to see a bead move), PART (the id of the
// capability to choose; the first the species has flux for otherwise) and NAME (what the
// pictures are called in OUT_DIR: NAME-part.png and NAME-all.png). One browser at a time:
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
  await page("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: HEIGHT, deviceScaleFactor: 1, mobile: false });
  if (process.env.THEME === "dark") await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "dark" }] });
  const evaluate = async (expression) => {
    const reply = await page("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (reply.exceptionDetails) throw new Error(reply.exceptionDetails.exception?.description || reply.exceptionDetails.text);
    return reply.result.value;
  };
  const V = "document.querySelector('cells-viewer')";
  const L = `${V}.current`;
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
        plan: flux.plan.kinds.map((kind) => kind.id), withheld: flux.plan.withheld.map((item) => item.id), shown: flux.showing().kinds.map((kind) => kind.id),
        parts: flux.plan.kinds.map((kind) => lens.capabilityByPart.get(kind.part).id),
        tokens: flux.tokens.map((set) => ({ zone: set.zone.name, lanes: set.lanes.length, beads: set.tokens.drawn.beads, heads: set.tokens.drawn.heads, visible: set.tokens.group.visible, opacity: set.tokens.materials[0].opacity, first: set.tokens.lanes[0].beads[0] ?? null })),
        bloom: stage.finish?.bloom?.strength ?? 0, shining: stage.finish?.sources?.size ?? 0, holds: [...stage.decoration.holds], moving: stage.decoration.moving, still: flux.still(),
        rows: [...root.querySelectorAll("cells-legend .layer-row")].map((row) => row.dataset.channel + ": " + [...row.querySelectorAll("button")].map((b) => b.textContent + (b.getAttribute("aria-pressed") === "true" ? "*" : "")).join(" | ")),
        notice: root.querySelector("cells-legend .layer-example")?.textContent ?? null,
        hint: root.querySelector("cells-legend .layer-hint")?.textContent ?? null,
        keys: [...root.querySelectorAll("cells-legend .legend-key")].map((p) => p.textContent),
        cannot: [...root.querySelectorAll("cells-legend .layer-cannot")].map((p) => p.textContent),
        legendBox: box(root.querySelector("cells-legend")),
        viewBox: (() => { const card = root.querySelector(".view"); return card && !card.hidden && card.getBoundingClientRect().height > 0 ? box(card) : null; })(),
        said: [...root.querySelectorAll(".label-example, .label-flow")].map((el) => ({ text: el.textContent, shown: !el.classList.contains("is-off"), box: box(el) })),
        panel: !panel || panel.hidden ? null : { title: panel.querySelector("h2")?.textContent ?? null, text: panel.textContent, box: box(panel) },
        old: { drops: cell.streams.flatMap((stream) => stream.drops).filter((drop) => drop.visible).length, signals: cell.signals.filter((bead) => bead.visible).length, ions: cell.molecule.ions.filter((ion) => ion.visible).length },
        foot: [...root.querySelectorAll(".scalebar, .look-box, .caveat")].filter((el) => !el.hidden && el.getBoundingClientRect().height > 0).map((el) => [el.className.split(" ")[0], ...box(el)]),
      };
    })()`);
  /** Look again until the page shows what is waited for (at most 8 s); the last look is returned either way. */
  const until = async (test) => {
    let now = await state();
    for (let tries = 0; tries < 32 && !test(now); tries++) {
      await sleep(250);
      now = await state();
    }
    return now;
  };

  const query = ["lens=cell", MOVING ? null : "still=1", process.env.SPECIES ? `species=${process.env.SPECIES}` : null, process.env.SIZE ? `size=${process.env.SIZE}` : null].filter(Boolean).join("&");
  await page("Page.navigate", { url: `${base}?${query}` });
  let drawn = false;
  for (let tries = 0; tries < 1440 && !drawn; tries++) {
    await sleep(250);
    drawn = await evaluate(`Boolean(${V} && ${V}.current && ${V}.stage && ${V}.state.lens === "cell" && ${L}.flux && ${L}.cells)`).catch(() => false);
  }
  if (!drawn) throw new Error("the Cell view was not drawn within six minutes of opening the page");
  await rest();
  await sleep(500);

  // ------------------------------------------------------------ at rest
  let s = await state();
  note(`species ${s.species}, ${s.mode}, ${s.width} by ${s.height}; flux may show for ${JSON.stringify(s.plan)}; not drawn ${JSON.stringify(s.withheld)}`);
  check("the page opens with nothing flowing: no bead, no bloom, the look's own motion not held by flux", s.tokens.length === 0 && s.bloom === 0 && !s.holds.includes("flux") && s.on === false, JSON.stringify([s.tokens.length, s.bloom, s.holds]));
  check("nothing on the picture speaks of flux", s.said.every((item) => !item.shown), JSON.stringify(s.said));
  // The legend now carries the Flux block: it must not reach up over the view's card.
  const clear = (now) => !now.viewBox || now.legendBox[1] >= now.viewBox[3] || now.legendBox[0] >= now.viewBox[2] || now.legendBox[2] <= now.viewBox[0];
  check("at rest the legend, with its Flux switch, stands clear of the view's card", clear(s), JSON.stringify({ legend: s.legendBox, view: s.viewBox }));
  const atRest = s.old;

  // ------------------------------------------------------------ a part is chosen
  const part = process.env.PART || s.parts[0];
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
    check("an arrowhead ends each lane, and beads stand or travel on it", s.tokens.every((set) => set.heads === set.lanes && set.beads > 0), JSON.stringify(s.tokens));
    check("the bloom is on, what shines is marked, and the look's own motion is held", s.bloom > 0 && s.shining >= 2 && s.holds.includes("flux") && s.moving === false, JSON.stringify([s.bloom, s.shining, s.holds, s.moving]));
    const notice = s.said.find((item) => /^Illustration: not a run$/.test(item.text));
    check("the picture says \"Illustration: not a run\", and what form it is", s.source === "illustration" && notice?.shown && s.said.some((item) => item.shown && /^Direction only:/.test(item.text)), JSON.stringify(s.said));
    check("the statement stands on the picture, under the top bar and inside the window", s.said.filter((item) => item.shown).every((item) => item.box[1] >= 56 && item.box[0] >= 0 && item.box[2] <= s.width), JSON.stringify(s.said.map((item) => item.box)));
    check("the part's panel carries the notice and the basis", s.panel && /Flux\. Illustration: not a run/.test(s.panel.text), s.panel ? s.panel.title : "no panel");
    check("the switch itself stays off: the part was chosen, not the switch", s.on === false, JSON.stringify(s.rows));
    check("the picture's own tokens of other parts stand as they stood", (kind === "water" || s.old.drops === atRest.drops) && (kind === "secretion" || s.old.signals === atRest.signals), JSON.stringify([atRest, s.old]));
    if (MOVING) {
      const before = s.tokens[0].first;
      const later = await until((now) => now.tokens[0]?.first !== before);
      check("a bead moves", later.tokens[0]?.first !== before && later.still === false, JSON.stringify([before, later.tokens[0]?.first]));
    } else check("opened still, the beads stand and the picture says so", s.still === true && s.said.some((item) => /shown still$/.test(item.text)), JSON.stringify(s.said.map((item) => item.text)));
    await shot(`${NAME}-part`);
    await evaluate(`${V}.select(null)`);
    s = await until((now) => now.tokens.length === 0);
    check("with nothing chosen nothing flows again, and the stage is as it was", s.tokens.length === 0 && s.bloom === 0 && !s.holds.includes("flux") && s.said.every((item) => !item.shown), JSON.stringify([s.tokens.length, s.bloom, s.holds]));
  } else note("this species has nothing a direction or a both-ways lane is drawn for");

  // ------------------------------------------------------------ the switch
  const all = 'cells-legend .layer-row[data-channel="motion"] button[data-layer="flux"]';
  let reached = await press(all);
  if (!reached) {
    // On a narrow window the legend is folded behind its title: a real press opens it.
    await press("cells-legend .legend-toggle");
    reached = await press(all);
  }
  check("the Flux switch stands in the legend and can be pressed", reached, JSON.stringify(s.rows));
  s = await until((now) => now.on === true && (now.plan.length === 0 || now.tokens.length > 0));
  await rest();
  s = await state();
  check("the switch shows all that the species' file allows, under one legend", s.on && JSON.stringify(s.shown) === JSON.stringify(s.plan) && s.rows.some((row) => /All\*/.test(row)), JSON.stringify([s.shown, s.rows]));
  if (s.plan.length) {
    check("the legend carries the notice for as long as the illustration shows", s.notice === "Illustration: not a run", String(s.notice));
    check("the legend says what a bead stands for and whose word a direction is", s.keys.some((text) => /stand for no number/.test(text)) && s.keys.some((text) => /no direction is claimed|law of the engine/.test(text)), JSON.stringify(s.keys));
  }
  check("what is not drawn is named in the legend with its reason", s.withheld.length === 0 || s.cannot.length === s.withheld.length || /not drawn/.test(JSON.stringify(s.keys) + (await evaluate(`${V}.shadowRoot.querySelector("cells-legend .layer-cannots summary")?.textContent ?? ""`))), JSON.stringify(s.cannot));
  check("with all of it on the legend still stands clear of the view's card", clear(s), JSON.stringify({ legend: s.legendBox, view: s.viewBox }));
  check("the statement on the picture lies over no card and not in the foot", s.said.filter((item) => item.shown).every((item) => item.box[3] < s.height * 0.62 && (!s.viewBox || item.box[1] >= s.viewBox[3] || item.box[0] >= s.viewBox[2])), JSON.stringify({ said: s.said.map((item) => item.box), view: s.viewBox }));
  note(`all: ${JSON.stringify({ tokens: s.tokens, bloom: s.bloom, legendBox: s.legendBox, viewBox: s.viewBox, said: s.said, foot: s.foot })}`);
  await shot(`${NAME}-all`);
  if (await press("cells-legend .layer-details")) {
    s = await until((now) => now.panel?.title === "What flows in this cell");
    check("a panel says what stands behind all of it", s.panel?.title === "What flows in this cell" && /Not drawn|Drawn/.test(s.panel.text), s.panel?.title ?? "no panel");
    await evaluate(`${V}.select(null)`);
  } else note("the door to the panel behind the flux could not be pressed at this size");
  await evaluate(`${L}.setLayer("flux", false)`);
  s = await until((now) => now.tokens.length === 0);
  check("switched off, nothing flows and the stage is as it was", s.tokens.length === 0 && s.bloom === 0 && !s.holds.includes("flux") && s.old.drops === atRest.drops && s.old.signals === atRest.signals && s.old.ions === atRest.ions, JSON.stringify([s.tokens.length, s.bloom, s.holds, s.old]));
  const errors = pageLog.filter((line) => /error|exception/i.test(line));
  check("the page logged no error", errors.length === 0, errors.slice(0, 3).join(" / "));
} catch (error) {
  failed = error;
} finally {
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
