#!/usr/bin/env node
// Checks the protein atlas's shelves with real pointer and key input, through the DevTools
// protocol, the way tools/check_species.mjs drives the viewer: a species' own proteins, a
// family opening to its members, closing, the legend, the list and the keyboard, and the
// page when the proteins' files are not beside it.
//
//   node tools/check_shelves.mjs [SCENARIO] [SCENE_FILE] [OUT_DIR]
//
// SCENARIO is syn3a (the default), planarian, nofiles, resize, units-small or shots. The
// last two are aids: units-small gives three proteins a unit in the page's own copy of the
// data, and shots writes pictures into OUT_DIR. One browser at a time: it takes the lock in
// tools/lib/browser_lock.mjs, whose profile folder is on disk and removed afterwards.

import { spawn } from "node:child_process";
import { writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { createServer } from "./serve.mjs";
import { acquireBrowser } from "./lib/browser_lock.mjs";
import { DEFAULT_SCENE } from "./lib/build_page.mjs";

const scenario = process.argv[2] || "syn3a";
const scene = path.resolve(process.argv[3] || DEFAULT_SCENE);
const outDir = process.argv[4] ? path.resolve(process.argv[4]) : null;
if (outDir) await mkdir(outDir, { recursive: true });

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const results = [];
const check = (name, ok, detail = "") => {
  results.push(Boolean(ok));
  console.log(`${ok ? "pass" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`);
};
const note = (text) => console.log(`note  ${text}`);
const pageLog = [];
const release = await acquireBrowser();
const server = createServer({ offline: true, scene, log: (line) => pageLog.push(line), ...(scenario === "nofiles" ? { proteins: null } : {}) });
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}/`;
const WIDTH = Number(process.env.WIDTH || 1400), HEIGHT = Number(process.env.HEIGHT || 900);
const chrome = spawn(process.env.CHROME || "google-chrome", ["--headless=new", `--user-data-dir=${release.profile}`, "--disable-breakpad", "--no-first-run", "--no-sandbox", "--mute-audio", "--hide-scrollbars", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--remote-debugging-port=0", `--window-size=${WIDTH},${HEIGHT}`, "about:blank"], { stdio: ["ignore", "ignore", "pipe"] });
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
const size = (width, height) => page("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: false });
await size(WIDTH, HEIGHT);
const evaluate = async (expression) => {
  const reply = await page("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (reply.exceptionDetails) throw new Error(reply.exceptionDetails.exception?.description || reply.exceptionDetails.text);
  return reply.result.value;
};
const V = "document.querySelector('cells-viewer')";
const L = `${V}.lenses.get("proteins")`;
const open = async (query, still = true) => {
  await page("Page.navigate", { url: `${base}?${query}${still ? "&still=1" : ""}` });
  for (let tries = 0; tries < 80; tries++) {
    await sleep(250);
    if (await evaluate(`Boolean(${V} && ${V}.current && ${V}.stage)`).catch(() => false)) break;
  }
  await evaluate(`Promise.resolve(${V}.current.ready)`);
  await sleep(700);
};
const mouse = (type, x, y, extra = {}) => page("Input.dispatchMouseEvent", { type, x, y, button: "left", buttons: 1, clickCount: 1, ...extra });
const move = async (x, y) => {
  await mouse("mouseMoved", x, y, { button: "none", buttons: 0 });
  await sleep(250);
};
const click = async (x, y, wait = 400) => {
  await mouse("mouseMoved", x, y, { button: "none", buttons: 0 });
  await mouse("mousePressed", x, y);
  await mouse("mouseReleased", x, y, { buttons: 0 });
  await sleep(wait);
};
const key = async (name, code, virtual) => {
  await page("Input.dispatchKeyEvent", { type: "keyDown", key: name, code, windowsVirtualKeyCode: virtual, ...(name === "Enter" ? { text: "\r" } : {}) });
  await page("Input.dispatchKeyEvent", { type: "keyUp", key: name, code, windowsVirtualKeyCode: virtual });
  await sleep(350);
};
const middle = (selector) => evaluate(`(() => { const el = ${V}.shadowRoot.querySelector(${JSON.stringify(selector)}); if (!el) return null; el.scrollIntoView({ block: "nearest" }); const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
const press = async (selector, wait = 400) => {
  const at = await middle(selector);
  if (!at) throw new Error(`nothing matches ${selector}`);
  await click(at.x, at.y, wait);
};
const shot = async (name) => {
  if (!outDir) return; // pictures are written only when a folder is given
  const { data } = await page("Page.captureScreenshot", { format: "png" });
  await writeFile(path.join(outDir, `${name}.png`), Buffer.from(data, "base64"));
  note(`wrote ${path.join(outDir, `${name}.png`)}`);
};
// Where a marker of the shelves is on the screen, if a click there picks it and nothing lies over it.
const at = (keyOrFn) =>
  evaluate(`(() => {
    const v = ${V}, lens = v.current, view = lens.mounted;
    const keys = ${typeof keyOrFn === "string" && !keyOrFn.startsWith("(") ? `[${JSON.stringify(keyOrFn)}]` : `[...(view.dish ? view.dish.nodes.keys() : view.nodes.keys())].filter(${keyOrFn})`};
    for (const key of keys) {
      const node = view.nodeOf(key);
      if (!node) continue;
      for (const lift of [0, 0.6, -0.6]) {
        const point = node.position.clone(); point.y = (node.top + node.position.y) / 2 + lift;
        const out = point.clone();
        v.stage.project(point, out);
        if (out.x < 300 || out.x > v.stage.width - 20 || out.y < 80 || out.y > v.stage.height - 110) continue;
        const hit = v.stage.pick(out.x, out.y, lens.pickRoots);
        if (hit && hit.id === key && v.shadowRoot.elementFromPoint(out.x, out.y) === v.canvas) return { key, x: out.x, y: out.y };
      }
    }
    return null;
  })()`);
const state = () =>
  evaluate(`(() => {
    const v = ${V}, root = v.shadowRoot, lens = v.lenses.get("proteins"), view = lens?.mounted;
    const text = (selector) => root.querySelector(selector)?.textContent ?? null;
    const panel = root.querySelector("cells-panel");
    const info = v.stage.renderer.info;
    return {
      show: v.dataset.show ?? null, mode: lens?.mode, species: v.state.species, selected: v.state.selected,
      heading: text(".view-card .card-title"), notice: text(".card-notice"), open: text(".card-open-name"), caveat: text(".caveat"), stamp: text(".stamp"),
      modes: [...root.querySelectorAll(".view-card [data-show]")].map((b) => b.dataset.show + (b.getAttribute("aria-pressed") === "true" ? "*" : "") + ":" + b.textContent).join(" | "),
      stats: [...root.querySelectorAll(".view-card .stat")].map((item) => item.textContent).join(" | "),
      legend: [...root.querySelectorAll("cells-legend .legend-item")].map((b) => b.querySelector(".legend-label").textContent + "=" + (b.querySelector(".legend-count")?.textContent ?? "") + (b.getAttribute("aria-pressed") === "true" ? "*" : "")).join(", "),
      drawn: view ? view.drawn() : null,
      lit: view ? [...view.nodes.values()].filter((node) => view.lit(node.item)).length : null,
      opened: view?.opened?.key ?? null,
      hot: [...root.querySelectorAll(".label-hot")].filter((el) => !el.classList.contains("is-off") && el.textContent).map((el) => el.textContent).join(" | "),
      calls: info.render.calls, triangles: info.render.triangles,
      panel: panel.hidden ? null : { title: panel.querySelector("h2")?.textContent, eyebrow: panel.querySelector(".eyebrow")?.textContent, chips: [...panel.querySelectorAll(".chip")].map((c) => c.textContent).join(" | "), plain: panel.querySelector(".panel-plain")?.textContent, facts: [...panel.querySelectorAll(".facts dt")].map((d) => d.textContent + ": " + d.nextSibling.textContent).join(" | "), heads: [...panel.querySelectorAll(".panel-list h4")].map((h) => h.textContent).join(" | "), hosts: [...new Set([...panel.querySelectorAll(".item-links a")].map((a) => new URL(a.href).hostname))].join(" "), tags: [...panel.querySelectorAll(".tag")].map((t) => t.textContent).join(" | ") },
    };
  })()`);
// How long a frame takes to draw as the scene stands (software GL here: for comparison only).
const frame = () =>
  evaluate(`(() => { const v = ${V}; const times = []; for (let i = 0; i < 5; i++) { const t = performance.now(); v.stage.renderer.render(v.stage.scene, v.stage.camera); v.stage.renderer.getContext().finish(); times.push(performance.now() - t); } times.sort((a, b) => a - b); return { ms: Math.round(times[2] * 10) / 10, calls: v.stage.renderer.info.render.calls, triangles: v.stage.renderer.info.render.triangles }; })()`);

try {
  if (scenario === "syn3a") {
    await open("lens=proteins&species=syn3a");
    let s = await state();
    check("Syn3A opens on its own proteins", s.show === "own" && s.heading === "Syn3A proteins" && /own\*/.test(s.modes), JSON.stringify([s.show, s.heading, s.modes]));
    check("one marker for each of its 455 proteins", s.drawn?.markers === 455 && s.lit === 455, JSON.stringify(s.drawn));
    note(`legend: ${s.legend}`);
    note(`stats: ${s.stats}`);
    note(`caveat: ${s.caveat}`);
    note(`at rest: ${JSON.stringify(await frame())}`);
    const bead = await at("(key) => true");
    // The name appears with the frame after the pointer's: wait for it, up to three seconds, and say how long it took.
    // A move that arrives before the shelves can be picked names nothing, so the pointer is moved again, up to three times.
    let named = -1;
    for (let attempt = 0; attempt < 3 && named < 0; attempt++) {
      await move(bead.x + attempt, bead.y);
      named = await evaluate(`new Promise((resolve) => { const root = ${V}.shadowRoot, t = performance.now(); const wait = () => { const shown = [...root.querySelectorAll(".label-hot")].some((el) => !el.classList.contains("is-off") && el.textContent); shown || performance.now() - t > 3000 ? resolve(shown ? Math.round(performance.now() - t) : -1) : setTimeout(wait, 30); }; wait(); })`);
    }
    s = await state();
    check("the pointer names the protein under it", Boolean(s.hot) && named >= 0, `${s.hot} (${named} ms after the pointer came to rest, beyond the first 250)`);
    note(`hovered: ${await evaluate(`${L}.mounted.hovered`)}; at the pointer: ${JSON.stringify(bead)}`);
    await click(bead.x, bead.y);
    s = await state();
    check("a click on a marker selects its protein and opens the panel", s.selected === bead.key && s.panel && /protein$/.test(s.panel.eyebrow), JSON.stringify([s.selected, s.panel?.title, s.panel?.eyebrow]));
    note(`panel: ${JSON.stringify(s.panel)}`);
    check("the panel says Cells has no law for it, and how its side is known", /No law in Cells/.test(s.panel?.chips || "") && /Predicted|Stated|By function|Not known/.test(s.panel?.chips || ""), s.panel?.chips);
    check("it links out to look the protein up", /ncbi/.test(s.panel?.hosts || ""), s.panel?.hosts);
    await shot("syn3a-protein-selected");
    await key("Escape", "Escape", 27);
    s = await state();
    check("Escape lets go of it", s.selected === null && s.panel === null, JSON.stringify(s.selected));
    // The legend: a side alone, then a basis, then a value of a mark.
    await press("cells-legend .legend-body > .legend-item:nth-of-type(2)");
    s = await state();
    check("the legend shows one side alone", s.lit === 86, `${s.lit} lit; ${s.legend}`);
    await press("cells-legend .legend-body > .legend-item:nth-of-type(2)");
    await evaluate(`${V}.shadowRoot.querySelector("cells-legend .legend-fold")?.setAttribute("open", "")`);
    await press('cells-legend [data-finding="essential"]');
    s = await state();
    check("a value of a mark shows its proteins alone", s.lit === 270, `${s.lit} lit`);
    await shot("syn3a-essential");
    await press('cells-legend [data-finding="essential"]');
    // The other mode and back.
    await press('.view-card [data-show="units"]');
    s = await state();
    check("the switch shows the machines Cells has laws for", s.show === "units" && s.heading === "Syn3A atlas" && /units\*/.test(s.modes), JSON.stringify([s.show, s.heading, s.modes]));
    await press('.view-card [data-show="own"]');
    s = await state();
    check("and back to its own proteins", s.show === "own" && s.drawn?.markers === 455, JSON.stringify([s.show]));
    // The choice is kept for the next species; a species without proteins of its own shows the machines and says so.
    await press('[data-species="human"]');
    s = await state();
    check("Human: the machines, with one line that its own catalogue is not made", s.show === "units" && s.heading === "The proteins Cells models" && /not made yet/.test(s.notice || "") && s.modes === "", JSON.stringify([s.show, s.heading, s.notice, s.modes]));
    await press('[data-species="mpneumoniae"]');
    await sleep(600);
    s = await state();
    check("M. pneumoniae: its own 688 proteins", s.show === "own" && s.drawn?.markers === 688, JSON.stringify([s.show, s.drawn]));
    note(`M. pneumoniae at rest: ${JSON.stringify(await frame())}`);
    note(`legend: ${s.legend}`);
    // The list reaches every protein.
    await evaluate(`${V}.toggleIndex(true)`);
    await sleep(300);
    const rows = await evaluate(`${V}.shadowRoot.querySelectorAll("cells-index .index-row").length`);
    check("the list holds every protein of the species", rows === 688, String(rows));
    await evaluate(`(() => { const input = ${V}.shadowRoot.querySelector("cells-index input"); input.value = "MPN_142"; input.dispatchEvent(new Event("input")); })()`);
    await sleep(200);
    const found = await evaluate(`[...${V}.shadowRoot.querySelectorAll("cells-index .index-row")].map((row) => row.textContent).join(" | ")`);
    check("and finds one by its identifier", /P40|P90|Adhesin/i.test(found), found);
    await evaluate(`${V}.shadowRoot.querySelector("cells-index .index-row").focus()`);
    await key("Enter", "Enter", 13);
    s = await state();
    check("from the keyboard, the list selects it", Boolean(s.selected) && /MPN_142/.test(s.selected), String(s.selected));
  }

  if (scenario === "planarian") {
    await open("lens=proteins&species=planarian");
    let s = await state();
    check("the planarian opens on the machines Cells has laws for, with the switch to its own proteins", s.show === "units" && s.heading === "Planarian atlas" && /own:Its 18,882 proteins/.test(s.modes), JSON.stringify([s.show, s.heading, s.modes]));
    const started = Date.now();
    await press('.view-card [data-show="own"]', 0);
    await evaluate(`Promise.resolve(${L}.ready)`);
    const took = Date.now() - started;
    await sleep(500);
    s = await state();
    check("its own proteins: 473 markers for 18,882 proteins", s.show === "own" && s.drawn?.markers === 473, JSON.stringify(s.drawn));
    note(`from the press to the shelves: ${took} ms (fetching the file, laying it out and building it)`);
    note(`built in: ${JSON.stringify(await evaluate(`(() => { const lens = ${L}; const state = lens.own.get("planarian"); const t = performance.now(); const { ShelvesView } = { ShelvesView: lens.mounted.constructor }; const view = new ShelvesView(lens, state.shelves, { shape: lens.mounted.shape }); const ms = performance.now() - t; view.dispose(); return Math.round(ms); })()`))} ms for a second copy of the shelves (layout and meshes)`);
    note(`at rest: ${JSON.stringify(await frame())}`);
    note(`legend: ${s.legend}`);
    note(`the switch alone, with the file already in and no layout kept: ${JSON.stringify(await evaluate(`(() => { const lens = ${L}; const state = lens.own.get("planarian"); const times = []; for (let i = 0; i < 3; i++) { lens.setMode("units", { user: true }); for (const view of state.views.values()) view.dispose(); state.views.clear(); const t = performance.now(); lens.setMode("own", { user: true }); times.push(Math.round(performance.now() - t)); } return times; })()`))} ms, three times (layout, meshes, labels and the card)`);
    await sleep(400);
    await shot("planarian-rest");
    // Open a family that holds a machine Cells has a law for.
    const innexin = await at("own:planarian:f:IPR000990");
    check("the Innexin family is under the pointer", Boolean(innexin), JSON.stringify(innexin));
    await move(innexin.x, innexin.y);
    s = await state();
    note(`hover: ${s.hot}`);
    const t0 = Date.now();
    await click(innexin.x, innexin.y, 0);
    await evaluate(`new Promise((resolve) => { const lens = ${L}; const wait = () => (lens.mounted.opened ? resolve() : setTimeout(wait, 20)); wait(); })`);
    note(`from the click to the open family: ${Date.now() - t0} ms`);
    await sleep(600);
    s = await state();
    check("a click on a family opens it to every member", s.opened === "own:planarian:f:IPR000990" && s.drawn.open?.members === 70 && /Innexin · 70 proteins/.test(s.open || ""), JSON.stringify([s.opened, s.drawn.open, s.open]));
    check("its members are drawn as the machine Cells has a law for", s.drawn.open?.forms === 70, JSON.stringify(s.drawn.open));
    check("the panel describes the family", s.panel?.title === "Innexin" && /family/.test(s.panel?.eyebrow || "") && /Its proteins/.test(s.panel?.heads || ""), JSON.stringify(s.panel));
    note(`panel: ${JSON.stringify(s.panel)}`);
    await shot("planarian-innexin-open");
    const member = await at("(key) => true");
    await click(member.x, member.y);
    s = await state();
    check("a click on a member selects that protein", s.selected === member.key && /protein$/.test(s.panel?.eyebrow || ""), JSON.stringify([s.selected, s.panel?.title, s.panel?.eyebrow]));
    note(`panel: ${JSON.stringify(s.panel)}`);
    await shot("planarian-member-selected");
    await click(330, 700);
    s = await state();
    check("a click on nothing lets go of the member and leaves the family open", s.selected === null && s.opened === "own:planarian:f:IPR000990", JSON.stringify([s.selected, s.opened]));
    await click(330, 700);
    s = await state();
    check("a second one closes the family", s.opened === null && s.open === null, JSON.stringify([s.opened, s.open]));
    // The largest thing that opens.
    const t1 = Date.now();
    await evaluate(`${V}.select("own:planarian:g:" + ${L}.mounted.shelves.parts.find((part) => part.kind === "no signature").id)`);
    await evaluate(`new Promise((resolve) => { const lens = ${L}; const wait = () => (lens.mounted.opened ? resolve() : setTimeout(wait, 20)); wait(); })`);
    note(`the largest: opened in ${Date.now() - t1} ms`);
    await sleep(800);
    s = await state();
    check("the largest group opens to its 3,887 proteins", s.drawn.open?.members === 3887, JSON.stringify(s.drawn.open));
    note(`with the largest open: ${JSON.stringify(await frame())}`);
    note(`building the largest again, its file already in: ${JSON.stringify(await evaluate(`(async () => { const view = ${L}.mounted; const key = view.opened.key; const times = []; for (let i = 0; i < 3; i++) { view.close({ quiet: true }); const t = performance.now(); await view.open(key); times.push(Math.round(performance.now() - t)); } return times; })()`))} ms, three times`);
    await sleep(600);
    await shot("planarian-largest-open");
    await evaluate(`${V}.toggleIndex(true)`);
    await sleep(400);
    const index = await evaluate(`(() => { const root = ${V}.shadowRoot; return { rows: root.querySelectorAll("cells-index .index-row").length, more: [...root.querySelectorAll("cells-index .index-more")].map((p) => p.textContent).join(" | "), heads: [...root.querySelectorAll("cells-index h3")].map((h) => h.textContent).slice(0, 3).join(" | ") }; })()`);
    note(`list: ${JSON.stringify(index)}`);
    await evaluate(`(() => { const input = ${V}.shadowRoot.querySelector("cells-index input"); input.value = "innexin"; input.dispatchEvent(new Event("input")); })()`);
    await sleep(300);
    const found = await evaluate(`[...${V}.shadowRoot.querySelectorAll("cells-index .index-row")].map((row) => row.textContent).slice(0, 6).join(" | ")`);
    check("the list finds a family by name", /Innexin/.test(found), found);
    await evaluate(`${V}.toggleIndex(false)`);
    await evaluate(`${V}.canvas.focus()`);
    await key("Escape", "Escape", 27);
    await key("Escape", "Escape", 27);
    s = await state();
    check("Escape closes what is open", s.opened === null, JSON.stringify([s.selected, s.opened]));
    // A gathering of smaller families.
    const gathered = await at("(key) => key.includes(':m:channels|in')");
    await click(gathered.x, gathered.y, 900);
    s = await state();
    check("a gathering opens to the proteins of all its families", s.opened === gathered.key && s.drawn.open?.members > 0, JSON.stringify([s.opened, s.drawn.open, s.open]));
    note(`panel: ${JSON.stringify(s.panel)}`);
    await shot("planarian-gathering-open");
    // From a family to the machine Cells has a law for, and back from the machine to its families.
    await press("cells-panel .connection .link-button");
    await sleep(500);
    s = await state();
    check("a family's machine opens on the board of Cells' machines", s.show === "units" && /^unit\./.test(s.selected || "") && s.opened === null, JSON.stringify([s.show, s.selected, s.panel?.title, s.panel?.heads]));
    check("and the machine names the families that hold its products", /Among Planarian's own proteins: the families/.test(s.panel?.heads || ""), s.panel?.heads);
    await press("cells-panel .opens .link-button", 900);
    s = await state();
    check("one of them opens among its own proteins", s.show === "own" && /:f:|:m:/.test(s.opened || "") && s.drawn.open?.members > 0, JSON.stringify([s.show, s.selected, s.opened, s.drawn?.open]));
    await shot("planarian-from-unit");
    // The legend's toggle: families that hold a machine with a law.
    await press('[data-close="open"]');
    await press("cells-legend .legend-group");
    s = await state();
    check("the legend shows the families holding a machine with a law alone", s.lit > 0 && s.lit < 60, `${s.lit} lit; ${s.legend}`);
    await shot("planarian-units-only");
  }

  if (scenario === "motion") {
    // Not still: the opening as it moves.
    await open("lens=proteins&species=planarian&show=own", false);
    await sleep(600);
    const innexin = await at("own:planarian:f:IPR000990");
    await click(innexin.x, innexin.y, 0);
    await evaluate(`new Promise((resolve) => { const lens = ${L}; const wait = () => (lens.mounted.dish ? resolve() : setTimeout(wait, 10)); wait(); })`);
    await sleep(230);
    await shot("planarian-opening");
    await sleep(1500);
    await shot("planarian-opened");
    const s = await state();
    check("the family is open after the motion", s.opened === "own:planarian:f:IPR000990", String(s.opened));
  }

  if (scenario === "phone") {
    await open("lens=proteins&species=planarian&show=own&select=own:planarian:f:IPR000990");
    await sleep(1200);
    const probe = () => evaluate(`(() => { const v = ${V}, lens = v.current, view = lens.mounted, rig = v.stage.rig; const dish = view.dish; const out = new (dish ? dish.to.constructor : Object)(); if (dish) v.stage.project(dish.to, out); return { size: [v.stage.width, v.stage.height], insets: v.stage.insets, rig: { d: rig.distance, polar: rig.polar, az: rig.azimuth, target: rig.target.toArray().map((n) => Math.round(n)) }, limits: rig.limits, framing: view.framing && { of: view.framing.of, key: view.framing.key, d: view.framing.view?.distance, target: view.framing.view?.target.toArray().map((n) => Math.round(n)) }, dish: dish && { to: dish.to.toArray().map((n) => Math.round(n)), reach: dish.reach, high: dish.high, grown: dish.grown, at: [Math.round(out.x), Math.round(out.y), out.z], pos: dish.group.position.toArray().map((n) => Math.round(n)), scale: dish.group.scale.x, parent: Boolean(dish.group.parent), veil: [view.veil.visible, view.veilMaterial.opacity, view.veil.position.y] }, opened: view.opened?.key }; })()`);
    note(JSON.stringify(await probe()));
    await shot("phone-open-probe");
    const s2 = await state();
    note(JSON.stringify({ selected: s2.selected, opened: s2.opened, open: s2.open, drawn: s2.drawn }));
  }

  if (scenario === "held") {
    await open("lens=proteins&species=planarian&show=own");
    await evaluate(`${V}.select("own:planarian:f:IPR002077")`);
    await sleep(2500);
    note(JSON.stringify(await evaluate(`(() => { const view = ${V}.current.mounted; return { status: view?.status, wanted: view?.wanted?.key, opened: view?.opened?.key, selected: ${V}.state.selected, mode: ${V}.current.mode, own: [...${V}.current.own].map(([id, state]) => id + ":" + state.status + ":" + (state.error || "")) }; })()`)));
    note(JSON.stringify(await evaluate(`(() => { const v = ${V}, lens = v.current, view = lens.mounted, dish = view.dish; const chosen = view.shelves.get(view.selected); const out = { selected: view.selected, opened: view.opened?.key, within: chosen?.within === dish?.item, entries: 0, forms: [], underChosen: 0 }; for (const entry of dish.nodes.values()) { out.entries++; if (entry.item.under === chosen) out.underChosen++; if (entry.form) out.forms.push([entry.item.under.label.slice(0, 22), entry.item.under === chosen, entry.form.meshes.map((mesh) => mesh.userData.tone + ":" + mesh.material.opacity.toFixed(2) + (mesh.visible ? "" : " hidden")).join(","), entry.form.group.parent === dish.group, entry.form.group.position.toArray().map((n) => Math.round(n * 10) / 10).join(" "), entry.form.group.scale.x.toFixed(2)]); } return out; })()`)));
    await shot("held-probe");
  }

  if (scenario === "shots") {
    // The pictures for the report, in real time (an open family needs its file fetched and a frame drawn).
    const settle = async () => { await evaluate(`Promise.resolve(${V}.current.ready)`); await sleep(1300); };
    const opened = () => evaluate(`new Promise((resolve) => { const lens = ${L}; const wait = () => (lens.mounted?.opened ? resolve() : setTimeout(wait, 30)); wait(); })`);
    for (const [name, query] of [["shelves-syn3a", "lens=proteins&species=syn3a"], ["shelves-mpneumoniae", "lens=proteins&species=mpneumoniae"], ["shelves-planarian", "lens=proteins&species=planarian&show=own"], ["atlas-planarian", "lens=proteins&species=planarian"], ["atlas-human", "lens=proteins&species=human"], ["shelves-planarian-dark", "lens=proteins&species=planarian&show=own&theme=dark"], ["shelves-syn3a-dark", "lens=proteins&species=syn3a&theme=dark"]]) {
      await open(query);
      await settle();
      await shot(name);
    }
    // A family open, light and dark; the largest; a gathering with one of its families chosen; a protein chosen.
    for (const [name, query, key] of [["family-open", "lens=proteins&species=planarian&show=own", "own:planarian:f:IPR000990"], ["family-open-dark", "lens=proteins&species=planarian&show=own&theme=dark", "own:planarian:f:IPR000990"], ["gathering-open-family-chosen", "lens=proteins&species=planarian&show=own", "own:planarian:f:IPR002077"]]) {
      await open(query);
      await settle();
      await evaluate(`${V}.select(${JSON.stringify(key)})`);
      await opened();
      await sleep(1300);
      await shot(name);
    }
    await evaluate(`${V}.select("own:planarian:g:" + ${L}.mounted.shelves.parts.find((part) => part.kind === "no signature").id)`);
    await opened();
    await sleep(1500);
    await shot("largest-open");
    await open("lens=proteins&species=mpneumoniae&select=own:mpneumoniae:p:MPN_142");
    await settle();
    await shot("protein-chosen");
    // A narrow window.
    await size(400, 800);
    for (const [name, query] of [["phone-syn3a", "lens=proteins&species=syn3a"], ["phone-mpneumoniae", "lens=proteins&species=mpneumoniae"], ["phone-planarian", "lens=proteins&species=planarian&show=own"], ["phone-human", "lens=proteins&species=human"]]) {
      await open(query);
      await settle();
      await shot(name);
    }
    await open("lens=proteins&species=planarian&show=own");
    await settle();
    await evaluate(`${V}.select("own:planarian:f:IPR000990")`);
    await opened();
    await sleep(1300);
    await shot("phone-family-open");
    // The opening as it moves, on a wide window again.
    await size(WIDTH, HEIGHT);
    await open("lens=proteins&species=planarian&show=own", false);
    await settle();
    const innexin = await at("own:planarian:f:IPR000990");
    await click(innexin.x, innexin.y, 0);
    await evaluate(`new Promise((resolve) => { const lens = ${L}; const wait = () => (lens.mounted.dish ? resolve() : setTimeout(wait, 10)); wait(); })`);
    await sleep(260);
    await shot("family-opening");
    await sleep(1600);
    await shot("family-opened");
  }

  if (scenario === "resize") {
    // A window turned from wide to narrow with a family open: the shelves are laid out again and the family is open on them.
    await open("lens=proteins&species=planarian&show=own");
    await evaluate(`${V}.select("own:planarian:f:IPR000990")`);
    await evaluate(`new Promise((resolve) => { const lens = ${L}; const wait = () => (lens.mounted?.opened ? resolve() : setTimeout(wait, 30)); wait(); })`);
    await sleep(800);
    const before = await evaluate(`({ shape: ${L}.mounted.shape, opened: ${L}.mounted.opened?.key, views: ${L}.own.get("planarian").views.size })`);
    await size(400, 800);
    // The window's new size reaches the page with its next frames: wait for the shelves laid out for it, and the family opened on them.
    const waited = await evaluate(`new Promise((resolve) => { const lens = ${L}, t = performance.now(); const wait = () => (lens.mounted.shape !== ${before.shape} && lens.mounted.opened ? resolve(Math.round(performance.now() - t)) : performance.now() - t > 20000 ? resolve(-1) : setTimeout(wait, 50)); wait(); })`);
    note(`laid out again and opened ${waited} ms after the window was turned`);
    await sleep(900);
    const after = await evaluate(`({ shape: ${L}.mounted.shape, opened: ${L}.mounted.opened?.key, views: ${L}.own.get("planarian").views.size, selected: ${V}.state.selected, markers: ${L}.mounted.nodes.size })`);
    check("turned to a narrow window, the shelves are laid out for it and the family is open on them", before.shape !== after.shape && after.opened === before.opened && after.selected === before.opened && after.views === 2, JSON.stringify([before, after]));
    await shot("resize-narrow");
    await size(WIDTH, HEIGHT);
    await evaluate(`new Promise((resolve) => { const lens = ${L}, t = performance.now(); const wait = () => ((lens.mounted.shape === ${before.shape} && lens.mounted.opened) || performance.now() - t > 20000 ? resolve() : setTimeout(wait, 50)); wait(); })`);
    await sleep(600);
    const back = await evaluate(`({ shape: ${L}.mounted.shape, opened: ${L}.mounted.opened?.key, views: ${L}.own.get("planarian").views.size })`);
    check("and back on a wide one, the first layout is used again", back.shape === before.shape && back.opened === before.opened && back.views === 2, JSON.stringify(back));
    // The other views are not touched by any of it.
    await press('.switch [data-lens="cell"]');
    const cell = await evaluate(`({ show: ${V}.dataset.show ?? null, lens: ${V}.state.lens })`);
    check("the cell view carries nothing of the atlas's two drawings", cell.show === null && cell.lens === "cell", JSON.stringify(cell));
    await press('.switch [data-lens="proteins"]');
    await sleep(900);
    const again = await state();
    check("back in the atlas, its own proteins are shown at rest: the family closed with the view, as the selection did", again.show === "own" && again.opened === null && again.selected === null && again.drawn?.markers === 473, JSON.stringify([again.show, again.opened, again.selected, again.drawn]));
  }

  if (scenario === "units-small") {
    // No small catalogue names a unit today. To see that path drawn, three of Syn3A's proteins are
    // given one in the page's own copy of the file (nothing on disk is touched): in, outside and inside.
    await open("lens=proteins&species=syn3a");
    const made = await evaluate(`(() => {
      const lens = ${L}, state = lens.own.get("syn3a"), old = state.shelves;
      const data = JSON.parse(JSON.stringify(old.data));
      const at = Object.fromEntries(data.columns.map((name, index) => [name, index]));
      const given = [];
      for (const [side, unit] of [["in", "U01"], ["outside", "U39"], ["inside", "U48"]]) {
        const line = data.proteins.find((row) => row[at.side] === side && !row[at.unit]);
        line[at.unit] = unit;
        given.push(line[at.id]);
      }
      state.shelves = new old.constructor(data, { label: old.label, organism: old.organism, links: old.links, units: old.units });
      for (const view of state.views.values()) view.dispose();
      state.views.clear();
      lens.setMode("units", { user: true });
      lens.setMode("own", { user: true });
      return { given, drawn: lens.mounted.drawn(), feet: [...lens.mounted.nodes.values()].filter((node) => node.foot).length };
    })()`);
    await sleep(900);
    check("a protein of a small catalogue that has a unit is drawn as that unit, on a base of the units' colour", made.drawn.forms === 3 && made.feet === 3 && made.drawn.markers === 455, JSON.stringify(made));
    let s = await state();
    note(`card: ${s.stats}; caveat: ${s.caveat}`);
    check("the page then says how many are drawn as a machine Cells has a law for", /3with a law in Cells/.test(s.stats) && /A drawn shape is a machine Cells has a law for/.test(s.caveat || ""), JSON.stringify([s.stats, s.caveat]));
    const spot = await at(`own:syn3a:p:${made.given[0]}`);
    check("its form can be found under the pointer", Boolean(spot), JSON.stringify(spot));
    if (spot) {
      await click(spot.x, spot.y);
      s = await state();
      check("a click on the form selects the protein, and the panel ties it to the machine", s.selected === spot.key && /Would make a machine Cells has a law for/.test(s.panel?.chips || "") && /Drawn in the atlas as/.test(s.panel?.heads || ""), JSON.stringify([s.selected, s.panel?.chips, s.panel?.heads]));
    }
    await shot("small-with-units");
  }

  if (scenario === "nofiles") {
    await open("lens=proteins&species=syn3a");
    const s = await state();
    check("without the files beside the page, the atlas is drawn as before", s.show === "units" && s.heading === "Syn3A atlas", JSON.stringify([s.show, s.heading]));
    check("and the card says its own proteins could not be loaded", /could not be loaded/.test(s.notice || ""), String(s.notice));
    note(`notice: ${s.notice}`);
    await shot("syn3a-without-files");
    await press('.view-card [data-show="own"]', 900);
    const again = await state();
    check("asking for them again asks the page again, and the atlas stays", again.show === "units" && /could not be loaded/.test(again.notice || ""), JSON.stringify([again.show, again.notice]));
    await press('[data-species="planarian"]', 900);
    const worm = await state();
    check("the planarian's machines are drawn as before, with the same line", worm.show === "units" && worm.heading === "Planarian atlas" && /could not be loaded/.test(worm.notice || ""), JSON.stringify([worm.show, worm.heading, worm.notice]));
    await press('[data-species="human"]', 600);
    const human = await state();
    check("Human says its own catalogue is not made", /not made yet/.test(human.notice || ""), String(human.notice));
  }
} catch (error) {
  check("the run completed", false, error.stack || error.message);
} finally {
  for (const line of pageLog) console.log(line);
  check("no script errors or blocked loads were reported by the page", pageLog.length === 0, `${pageLog.length} messages`);
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
console.log(`${results.length - failed} of ${results.length} checks passed`);
process.exit(failed ? 1 : 0);
