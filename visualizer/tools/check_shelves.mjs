#!/usr/bin/env node
// Checks the protein atlas's shelves with real pointer and key input, through the DevTools
// protocol, the way tools/check_species.mjs drives the viewer: a species' own proteins, a
// family opening to its members, closing, the legend, the list and the keyboard, and the
// page when the proteins' files are not beside it.
//
//   node tools/check_shelves.mjs [SCENARIO] [SCENE_FILE] [OUT_DIR]
//
// SCENARIO is syn3a (the default), planarian, human, ecoli, stack, nofiles, resize, units-small, shots or
// pictures. stack checks any species with several shelves against its own file (SPECIES names it; thale
// cress by default): a frame and a legend line for every shelf, a shelf in focus, the stack back. human checks a species with several shelves, on the human's file: the stack,
// a shelf in focus, a family over its own shelf, the same family on another shelf, the
// families of one, what is set apart, the list, the keyboard and a phone-sized window; with
// OUT_DIR it also writes pictures of what it reaches (the whole stack and a shelf, wide and
// phone-sized, in both themes), so that these need no further browser runs. The
// last three are aids: units-small gives three proteins a unit in the page's
// own copy of the data, shots writes pictures into OUT_DIR, and pictures writes there the
// pictures that the JSON file named by PICTURES asks for, one by one: each
// { name, query, size: [width, height], run, wait }, where `run` is a script for the page
// once it has settled (with `viewer` and `lens` at hand). One browser at a time: it takes the lock in
// tools/lib/browser_lock.mjs, whose profile folder is on disk and removed afterwards.

import { spawn } from "node:child_process";
import { readFile, writeFile, mkdir } from "node:fs/promises";
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
  // The species' own proteins are fetched once the species is shown, which on a busy machine
  // comes after the lens says it is ready: wait until the species asked for is the one shown
  // and its file is in or could not be read, so that no check looks at the page before then.
  const wanted = new URLSearchParams(query).get("species") || new URLSearchParams(query).get("atlas");
  for (let tries = 0; tries < 120; tries++) {
    const settled = await evaluate(`(() => {
      const viewer = ${V}, lens = viewer.current;
      if (${JSON.stringify(wanted)} && viewer.state?.species !== ${JSON.stringify(wanted)}) return false;
      if (typeof lens?.ownState !== "function") return true;
      if (${JSON.stringify(wanted)} && lens.page !== ${JSON.stringify(wanted)}) return false;
      const state = lens.ownState(lens.page);
      return !state || state.status !== "loading";
    })()`).catch(() => false);
    if (settled) break;
    await sleep(250);
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
// The species switch. It is a dropdown since 15 November 2026 (one pill, and a list of the
// species while it is open): press the pill, wait for the list, press the species' row and
// wait for the list to close, as pickSpecies() of tools/check_input.mjs does.
const pickSpecies = async (id, wait = 400) => {
  const listOpen = () => evaluate(`(() => { const box = ${V}.shadowRoot.querySelector(".species-list"); return Boolean(box && !box.hidden); })()`);
  if (!(await listOpen())) await press(".species-pick", 250);
  for (let tries = 0; tries < 30 && !(await listOpen()); tries++) await sleep(100);
  await press(`.species-list [data-atlas="${id}"]`, 250);
  for (let tries = 0; tries < 30 && (await listOpen()); tries++) await sleep(100);
  await sleep(wait);
};
const shot = async (name) => {
  if (!outDir) return; // pictures are written only when a folder is given
  const { data } = await page("Page.captureScreenshot", { format: "png" });
  await writeFile(path.join(outDir, `${name}.png`), Buffer.from(data, "base64"));
  note(`wrote ${path.join(outDir, `${name}.png`)}`);
};
// On a busy machine the camera, or a family on its way up or down, may still be moving when a
// fixed wait is over: a place on the screen is read only once nothing moves any more.
const still = async () => {
  for (let tries = 0; tries < 120; tries++) {
    if (await evaluate(`(() => { const v = ${V}, view = v.current.mounted; return !v.stage.rig.flight && !(view && (view.dish?.tween || view.leaving || view.opening)); })()`)) break;
    await sleep(150);
  }
  await sleep(450);
};
// Where a marker of the shelves is on the screen, if a click there picks it and nothing lies over it.
const atNow = (keyOrFn) =>
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
// The camera glides when a panel opens or a family closes, and the members of a family glide to
// their places. A marker's place on the screen is read only once the view holds still: three
// looks in a row with the camera, the stage and the first member where they were (at most 6 s).
// On a larger scene the glide ends a little later, and a click aimed during it missed its marker.
const rest = async () => {
  let before = null, same = 0;
  for (let tries = 0; tries < 60 && same < 3; tries++) {
    const now = await evaluate(`(() => {
      const v = ${V}, s = v.stage, c = s.camera, dish = v.current?.mounted?.dish;
      const first = dish?.nodes ? [...dish.nodes.values()][0]?.position?.toArray() ?? [] : [];
      return JSON.stringify([c.position.toArray(), c.quaternion.toArray(), c.zoom, s.width, s.height, first].flat().map((n) => Math.round(n * 1000) / 1000));
    })()`).catch(() => null);
    same = now !== null && now === before ? same + 1 : 0;
    before = now;
    await sleep(100);
  }
};
const at = async (keyOrFn) => {
  await rest();
  return atNow(keyOrFn);
};
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
// The page's state once it shows what a press should bring, or as it stands when a generous wait has run out.
// A busy machine answers a press late: a fixed wait would then read the page before it has answered, and a
// check would miss for no fault of the page's. What each check requires is unchanged.
const until = async (test, ms = 20000) => {
  for (const began = Date.now(); ; ) {
    const now = await state();
    if (test(now) || Date.now() - began > ms) return now;
    await sleep(150);
  }
};
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
    // How many the legend says that side holds: the data's own number, not one written here.
    const alone = Number(((/=([\d,]+)\*/.exec(s.legend || "") || [])[1] || "").replace(/,/g, ""));
    check("the legend shows one side alone", alone > 0 && alone < 455 && s.lit === alone, `${s.lit} lit; ${s.legend}`);
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
    await pickSpecies("human");
    // Whether the scene names a catalogue for the human decides what is right here: with one, the
    // choice is kept and its own proteins are shown once they are in; without, the machines and one line.
    const humanHas = await evaluate(`Boolean(${L}.atlas.shelves?.some((item) => item.id === "human"))`);
    for (let tries = 0; humanHas && tries < 120 && (await evaluate(`${L}.ownState("human")?.status`)) === "loading"; tries++) await sleep(250);
    if (humanHas) await sleep(900);
    s = await state();
    if (humanHas) check("Human: the choice is kept, and its own proteins are shown", s.show === "own" && s.heading === "Human proteins" && s.drawn?.markers > 0, JSON.stringify([s.show, s.heading, s.notice, s.drawn?.markers]));
    else check("Human: the machines, with one line that its own catalogue is not made", s.show === "units" && s.heading === "The proteins Cells models" && /not made yet/.test(s.notice || "") && s.modes === "", JSON.stringify([s.show, s.heading, s.notice, s.modes]));
    await pickSpecies("mpneumoniae");
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
    await still(); // the family is up and the camera has framed it
    const member = await at("(key) => true");
    await click(member.x, member.y);
    s = await until((now) => now.selected === member.key);
    check("a click on a member selects that protein", s.selected === member.key && /protein$/.test(s.panel?.eyebrow || ""), JSON.stringify([s.selected, s.panel?.title, s.panel?.eyebrow]));
    note(`panel: ${JSON.stringify(s.panel)}`);
    await shot("planarian-member-selected");
    await click(330, 700);
    s = await until((now) => now.selected === null);
    check("a click on nothing lets go of the member and leaves the family open", s.selected === null && s.opened === "own:planarian:f:IPR000990", JSON.stringify([s.selected, s.opened]));
    await click(330, 700);
    s = await until((now) => now.opened === null && now.open === null);
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
    // A gathering of smaller families. The camera glides back after a family closes, so the marker's
    // place is read once the view rests; and the gathering is looked at once it is open, not after
    // a fixed wait (its members' file may still be on its way).
    await evaluate(`Promise.resolve(${V}.current.ready)`);
    await sleep(1300);
    // On a busy machine the view may move once more after it seemed to rest, and a press then meets the place the
    // marker has left. So the marker's place is read and pressed again, up to three times, each a real press; the
    // log says when the first press did not take, so that a page that needs two presses would show here.
    let gathered = null, presses = 0;
    for (; presses < 3; ) {
      await still(); // the camera may still be on its way home after the last thing closed
      gathered = await at("(key) => key.includes(':m:channels|in')");
      const before = await evaluate(`JSON.stringify(${V}.stage.rig.view())`);
      await click(gathered.x, gathered.y, 300);
      presses += 1;
      await evaluate(`new Promise((resolve) => { const lens = ${L}, began = performance.now(); const wait = () => (lens.mounted?.opened || performance.now() - began > 12000 ? resolve() : setTimeout(wait, 30)); wait(); })`);
      s = await until((now) => now.opened === gathered.key && now.drawn.open?.members > 0, 6000);
      if (s.opened === gathered.key) break;
      note(`press ${presses} on the gathering did not open it${before === (await evaluate(`JSON.stringify(${V}.stage.rig.view())`)) ? "" : ": the view had moved"}`);
    }
    if (presses > 1) note(`the gathering opened at press ${presses}`);
    await sleep(900);
    s = await until((now) => now.opened === gathered.key && now.drawn.open?.members > 0);
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

  if (scenario === "human") {
    // A species with several shelves, on the human's file. The scene must name its catalogue.
    const S = "own:human:s@"; // a shelf's key: this, its id, and ":shelf"
    const stack = () =>
      evaluate(`(() => {
        const v = ${V}, lens = v.current, view = lens.mounted;
        if (!view) return null;
        const shown = (el) => !el.classList.contains("is-off") && !el.hidden && el.textContent;
        const rig = v.stage.rig, frame = view.focusFrame();
        return {
          several: view.shelves.several, total: view.shelves.total, columns: view.arranged.columns, opens: view.opens,
          frames: view.frames.map((item) => [item.id, item.proteins]),
          focused: view.focused === undefined ? "stack" : view.focused,
          names: [...v.shadowRoot.querySelectorAll('[data-label^="${S}"]')].filter(shown).map((el) => el.textContent),
          districts: view.districts.filter((item) => item.tag && !item.tag.hidden).map((item) => item.frame.id),
          distance: Math.round(rig.flight ? rig.flight.to.distance : rig.distance),
          // Whether the shelf in focus lies within the picture: the middle of its membrane, and its two far corners.
          within: frame ? [[(frame.bounds.minX + frame.bounds.maxX) / 2, frame.origin.y, (frame.bounds.minZ + frame.bounds.maxZ) / 2], [frame.bounds.minX, frame.origin.y, frame.bounds.minZ], [frame.bounds.maxX, frame.origin.y, frame.bounds.maxZ]].every((at) => { const point = new view.group.position.constructor(...at), out = point.clone(); v.stage.project(point, out); return out.x > 0 && out.x < v.stage.width && out.y > 0 && out.y < v.stage.height; }) : null,
          dish: view.dish ? { above: Math.round(view.dish.to.y - view.nodeOf(view.dish.item.key).base), frame: view.nodeOf(view.dish.item.key).frame.id, members: view.dish.count } : null,
          // The legend's own heading (its first block's, shown on a narrow window) and the headings of its further blocks.
          legend: [v.shadowRoot.querySelector("cells-legend .legend-toggle span")?.textContent, ...[...v.shadowRoot.querySelectorAll("cells-legend .legend-title")].map((el) => el.textContent)].join(" | "),
        };
      })()`);
    const opened = (key) => evaluate(`new Promise((resolve) => { const lens = ${L}, began = performance.now(); const wait = () => (lens.mounted?.opened?.key === ${JSON.stringify(key)} || performance.now() - began > 20000 ? resolve(lens.mounted?.opened?.key ?? null) : setTimeout(wait, 40)); wait(); })`);
    // Names are laid out with the first frame drawn after they are made, which on a busy machine comes late: wait until one is shown.
    const named = async (id = "") => {
      for (let tries = 0; tries < 80; tries++) {
        if (await evaluate(`[...${V}.shadowRoot.querySelectorAll('[data-label^="${S}${id}"]')].some((el) => !el.classList.contains("is-off"))`)) break;
        await sleep(250);
      }
      await sleep(300);
    };
    const pick = (expression) => evaluate(`(() => { const v = ${V}, view = v.current.mounted, shelves = view.shelves; return (${expression}); })()`);
    const button = async (pattern) => {
      const at = await evaluate(`(() => { const found = [...${V}.shadowRoot.querySelectorAll("cells-panel .link-button")].find((el) => new RegExp(${JSON.stringify(pattern)}).test(el.textContent)); if (!found) return null; found.scrollIntoView({ block: "nearest" }); const r = found.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
      if (!at) throw new Error(`no link in the panel matches ${pattern}`);
      await click(at.x, at.y, 500);
    };
    // With a folder for pictures: one of the state the scenario has reached, in the page's
    // light theme and, switched in the page and back, in its dark one.
    const both = async (name) => {
      if (!outDir) return;
      await still();
      await shot(name);
      await evaluate(`(document.documentElement.dataset.theme = "dark")`);
      await sleep(1200);
      await shot(`${name}-dark`);
      await evaluate(`delete document.documentElement.dataset.theme`);
      await sleep(900);
    };

    await open("lens=proteins&species=human");
    let s = await state();
    const has = await evaluate(`Boolean(${L}.atlas.shelves?.some((item) => item.id === "human"))`);
    check("the scene names a catalogue for the human", has, "build the scene with data/proteins/human in place");
    check("the human opens on Cells' machines, and the switch offers its own proteins", s.show === "units" && s.heading === "The proteins Cells models" && /units\*/.test(s.modes) && /own:Its [\d,]+ proteins/.test(s.modes), JSON.stringify([s.show, s.heading, s.modes]));
    await press('.view-card [data-show="own"]');
    for (let tries = 0; tries < 160 && !(await evaluate(`Boolean(${L}.mounted)`)); tries++) await sleep(250);
    await still();
    await named();
    s = await state();
    let k = await stack();
    check("its own proteins stand on six shelves and apart from them, each named with what stands on it", k?.several && k.frames.length === 7 && k.frames.at(-1)[0] === null && k.names.length === 7 && k.names.every((name) => /· [\d,]+$/.test(name)) && k.frames.reduce((sum, item) => sum + item[1], 0) === k.total, JSON.stringify([k?.frames, k?.names]));
    check("a wide window shows the whole stack, as two staircases side by side, with no district named", k.focused === "stack" && k.columns === 2 && k.opens === "stack" && k.districts.length === 0, JSON.stringify([k.focused, k.columns, k.opens, k.districts.length]));
    check("the card counts the families that open beside the families in all, and the legend lists the shelves and no side", /families that open/.test(s.stats) && /families in all/.test(s.stats) && /^Shelves \|/.test(k.legend) && /The whole stack=[\d,]+\*/.test(s.legend) && /Nuclear envelope=[\d,]+(,|$)/.test(s.legend) && /No place known=[\d,]+/.test(s.legend) && !/In the cell membrane=/.test(s.legend), JSON.stringify([s.stats, k.legend, s.legend]));
    note(`whole stack: ${JSON.stringify(await frame())}, ${s.drawn.markers} markers`);
    await both("human-stack-wide");

    // Pressing a shelf's name brings it near: its districts are named, the legend speaks of it, the panel describes it.
    const far = k.distance;
    await press(`[data-label="${S}nucleus:shelf"]`, 600);
    await still();
    s = await state();
    k = await stack();
    check("pressing a shelf's name frames that shelf and names its districts", k.focused === "nucleus" && k.within === true && k.distance < far && k.districts.length > 0 && k.districts.every((id) => id === "nucleus"), JSON.stringify([k.focused, k.within, k.distance, far, k.districts.length]));
    check("the panel describes the shelf, and the legend counts its sides in its own words", s.panel?.title === "Nuclear envelope" && /one of 6 shelves/i.test(s.panel?.eyebrow || "") && /Nuclear envelope: sides/.test(k.legend) && /In the nucleus=[\d,]+/.test(s.legend) && /Nuclear envelope=[\d,]+\*/.test(s.legend), JSON.stringify([s.panel?.title, s.panel?.eyebrow, k.legend, s.legend]));
    await shot("human-shelf-with-its-panel-wide");

    // A family opens over its own shelf, a lower one, and closes back to that shelf.
    const family = await pick(`(() => { const node = [...view.nodes.values()].filter((n) => n.frame.id === "mito" && n.item.type === "f").sort((a, b) => b.item.count - a.item.count)[0]; return { key: node.item.key, count: node.item.count, label: node.item.label }; })()`);
    await evaluate(`${V}.select(${JSON.stringify(family.key)}, { fly: true })`);
    await opened(family.key);
    await still();
    s = await state();
    k = await stack();
    check("a family opens over its own shelf", s.opened === family.key && k.dish?.frame === "mito" && k.dish.members === family.count && k.dish.above >= 20 && k.focused === "mito" && /Open/.test(s.open || ""), JSON.stringify([s.opened, k.dish, k.focused, s.open]));
    await shot("human-family-open-wide");
    if (outDir) {
      // The same from a low angle and further back, where a veil that lay wrong would leave its own area bare and hang over the next.
      await evaluate(`(() => { const rig = ${V}.stage.rig; rig.flight = null; window.wasAt = { polar: rig.polar, distance: rig.distance }; rig.polar = 1.2; rig.distance *= 1.6; rig.apply(); ${V}.stage.invalidate(); })()`);
      await sleep(900);
      await shot("human-family-open-low-angle-wide");
      await evaluate(`(() => { const rig = ${V}.stage.rig; rig.polar = window.wasAt.polar; rig.distance = window.wasAt.distance; rig.apply(); ${V}.stage.invalidate(); })()`);
      await sleep(600);
    }
    await evaluate(`${V}.canvas.focus()`);
    await key("Escape", "Escape", 27); // letting go of the family that is open closes it
    await still();
    s = await state();
    k = await stack();
    check("Escape closes it, back to its shelf", s.selected === null && s.opened === null && s.open === null && k.focused === "mito" && k.within === true, JSON.stringify([s.selected, s.opened, s.open, k.focused, k.within]));

    // The same family on another shelf: the panel's link goes to that shelf and selects the line there.
    const split = await pick(`(() => { const line = shelves.families.find((item) => item.shelf === "cell" && !item.within && shelves.sameFamily(item).some((other) => other.shelf && !other.within)); const other = shelves.sameFamily(line).find((item) => item.shelf && !item.within); return { key: line.key, id: line.id, other: other.key, shelf: other.shelf, label: shelves.shelfOf(other).label, count: other.count }; })()`);
    await evaluate(`${V}.select(${JSON.stringify(split.key)}, { fly: true })`);
    await opened(split.key);
    await still();
    s = await state();
    check("a family's panel lists its lines on the other shelves", /same family on other shelves/i.test(s.panel?.heads || ""), JSON.stringify(s.panel?.heads));
    await button(`^${split.label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")} · ${split.count}$`);
    await opened(split.other);
    await still();
    s = await state();
    k = await stack();
    check("its link goes to that shelf and selects the family's line there", s.selected === split.other && s.opened === split.other && k.focused === split.shelf, JSON.stringify([s.selected, s.opened, k.focused, split]));
    // A key that names the family and no shelf (an address, a link from elsewhere) lands on its line with the most members.
    await evaluate(`${V}.select(null)`);
    await evaluate(`${V}.current.back()`);
    await still();
    const largest = await pick(`(() => { const line = shelves.families.reduce((best, item) => (item.count > best.count ? item : best)); return { key: line.key, bare: "own:human:f:" + line.id, count: line.count, shelf: line.shelf }; })()`);
    await evaluate(`${V}.select(${JSON.stringify(largest.bare)}, { fly: true })`);
    await opened(largest.key);
    await still();
    s = await state();
    k = await stack();
    check("a key that names no shelf lands on the family's largest line", s.opened === largest.key && k.dish?.members === largest.count && k.focused === largest.shelf && Boolean(s.panel?.title), JSON.stringify([s.opened, k.dish, k.focused, s.panel?.title]));
    note(`the largest line open (${largest.count} members): ${JSON.stringify(await frame())}`);
    await evaluate(`${V}.select(null)`);
    await evaluate(`${V}.current.back()`);
    await still();

    // Families of one: the part opens straight to its proteins, and each names its family.
    const lone = await pick(`(() => { const node = [...view.nodes.values()].filter((n) => n.frame.id === "er" && n.item.type === "l").sort((a, b) => b.item.count - a.item.count)[0]; return { key: node.item.key, count: node.item.count }; })()`);
    await evaluate(`${V}.select(${JSON.stringify(lone.key)}, { fly: true })`);
    await opened(lone.key);
    await still();
    s = await state();
    k = await stack();
    check("a gathering of families of one opens to its proteins, and is not called a family", s.opened === lone.key && k.dish?.members === lone.count && k.dish.frame === "er" && /only one of its family/i.test(s.panel?.eyebrow || "") && /This is not a family/.test(s.panel?.plain || ""), JSON.stringify([s.opened, k.dish, s.panel?.eyebrow]));
    const member = await at("(key) => true");
    await click(member.x, member.y, 500);
    s = await state();
    const facts = await evaluate(`[...${V}.shadowRoot.querySelectorAll("cells-panel .facts dt")].map((dt) => dt.textContent + ": " + dt.nextElementSibling.textContent).join(" | ")`);
    check("each of its proteins names its own family", s.selected === member.key && /Family: .+: its only member in this catalogue/.test(facts) && /Shelf: Endoplasmic reticulum membrane/.test(facts), facts);
    await shot("human-families-of-one-open-wide");
    await evaluate(`${V}.select(null)`);
    await evaluate(`${V}.current.back()`);
    await still();
    // What a frame costs with the largest thing that opens to proteins: a gathering of families of one.
    const most = await pick(`(() => { const item = shelves.markers.filter((one) => one.type !== "m" && one.type !== "n").reduce((best, one) => (one.count > best.count ? one : best)); return { key: item.key, count: item.count }; })()`);
    await evaluate(`${V}.select(${JSON.stringify(most.key)}, { fly: true })`);
    await opened(most.key);
    await still();
    k = await stack();
    note(`the largest that opens to proteins (${most.count}, ${most.key}), ${k.dish?.members} drawn: ${JSON.stringify(await frame())}`);
    await evaluate(`${V}.select(null)`);
    await evaluate(`${V}.current.back()`);
    await still();

    // What is set apart: beside a shelf, the proteins of that shelf with no side known; in front of all, those with no place.
    const apart = await pick(`(() => {
      const frame = view.frames.find((item) => item.id === "mito"), area = frame.areas.find((item) => item.id === "apart");
      const beside = area.blocks.flatMap((block) => block.places.map((place) => place.item));
      const none = view.frames.find((item) => item.id === null), loose = none.areas[0].blocks.flatMap((block) => block.places.map((place) => place.item));
      const entry = (id) => shelves.byShelf.find((item) => item.id === id);
      return { beside: beside.length, besideSides: [...new Set(beside.map((item) => item.side))], besideShelves: [...new Set(beside.map((item) => item.shelf))], lower: area.centre.y < frame.origin.y, counted: entry("mito").counts["not known"],
        none: loose.length, noneShelves: [...new Set(loose.map((item) => item.shelf))], noneProteins: none.proteins, noneCounted: entry(null).proteins, lowest: view.frames.every((item) => item.id === null || item.origin.y > none.origin.y), inFront: view.frames.every((item) => item.id === null || item.bounds.maxZ < none.bounds.minZ) };
    })()`);
    check("beside a shelf stand its proteins with no side known, lower than its membrane", apart.beside > 0 && apart.besideSides.join() === "not known" && apart.besideShelves.join() === "mito" && apart.lower && apart.counted > 0, JSON.stringify(apart));
    check("what has no place stands apart from every shelf, in front of all and lowest", apart.none > 0 && apart.noneShelves.length === 1 && apart.noneShelves[0] === null && apart.noneProteins === apart.noneCounted && apart.lowest && apart.inFront, JSON.stringify(apart));
    // Its name is pressed from the whole stack, where it is in the picture.
    await evaluate(`${V}.current.setFinding("stack")`);
    await still();
    await named(":shelf");
    await press(`[data-label="${S}:shelf"]`, 600);
    await still();
    s = await state();
    k = await stack();
    check("its name brings it near like a shelf's, and the panel says what it is", k.focused === null && k.within === true && s.panel?.title === "No place known" && /on no shelf/i.test(s.panel?.eyebrow || ""), JSON.stringify([k.focused, k.within, s.panel?.title, s.panel?.eyebrow]));
    await evaluate(`${V}.select(null)`);

    // The list: the shelves first, then each shelf's districts; a search finds a family on each shelf it stands on.
    await evaluate(`${V}.toggleIndex(true)`);
    await sleep(500);
    const heads = await evaluate(`[...${V}.shadowRoot.querySelectorAll("cells-index h3")].map((h) => h.textContent)`);
    check("the list has the shelves first and then each shelf's districts", /^Shelves/.test(heads[0] || "") && heads.some((head) => /^Cell membrane · /.test(head)) && heads.some((head) => /^Nuclear envelope · /.test(head)), JSON.stringify(heads.slice(0, 4)));
    await shot("human-list-wide");
    // A family with a line on more than one shelf, each on a shelf: one whose lines stand on
    // their own, and a smaller one whose lines stand gathered. Each with the shelves it is on.
    const twice = (gathered, long) =>
      pick(`(() => { const all = (item) => [item, ...shelves.sameFamily(item)]; const line = shelves.families.find((item) => all(item).length > 1 && all(item).every((one) => one.shelf != null && Boolean(one.within) === ${gathered}) && item.label.length > ${long} && !/[^A-Za-z -]/.test(item.label)); return line ? { label: line.label, on: all(line).map((one) => shelves.shelfOf(one).label).sort() } : null; })()`);
    // The rows a search for a name finds, each with the heading it stands under.
    const found = async (label) => {
      await evaluate(`(() => { const input = ${V}.shadowRoot.querySelector("cells-index input"); input.value = ${JSON.stringify(label.toLowerCase())}; input.dispatchEvent(new Event("input")); })()`);
      await sleep(400);
      return evaluate(`[...${V}.shadowRoot.querySelectorAll("cells-index section")].flatMap((section) => [...section.querySelectorAll(".index-row")].map((row) => row.textContent.replace(/\\s+/g, " ").trim()).filter((row) => row.startsWith(${JSON.stringify(label + " ·")})).map((row) => [section.querySelector("h3").textContent, row]))`);
    };
    const under = (rows, on, tail) => rows.length === on.length && JSON.stringify(rows.map(([head]) => on.find((label) => (tail ? head === label + tail : head.startsWith(label + " · "))) || "").sort()) === JSON.stringify(on);
    const small = await twice(true, 12);
    const smallRows = small ? await found(small.label) : [];
    check("a smaller family, which stands gathered, is found under each shelf it is gathered on", Boolean(small) && under(smallRows, small.on, " · Smaller families and groups"), JSON.stringify([small, smallRows]));
    const term = await twice(false, 6);
    const rows = term ? await found(term.label) : [];
    check("a search finds a family on each shelf it stands on, under that shelf's heading", Boolean(term) && under(rows, term.on), JSON.stringify([term, rows]));
    await shot("human-list-search-wide");
    await evaluate(`${V}.shadowRoot.querySelector("cells-index .index-row").focus()`);
    await key("Enter", "Enter", 13);
    await still();
    s = await state();
    check("Enter on a row chooses it", Boolean(s.selected) && /^own:human:/.test(s.selected), String(s.selected));
    await evaluate(`${V}.toggleIndex(false)`);
    await evaluate(`${V}.select(null)`);
    await evaluate(`${V}.current.back()`);
    await evaluate(`${V}.current.back()`);
    await still();

    // The keyboard: Page Down and Page Up move between the shelves, Home shows the whole stack, Escape leaves a shelf.
    await evaluate(`${V}.canvas.focus()`);
    k = await stack();
    const start = k.focused;
    await key("PageDown", "PageDown", 34);
    await still();
    const first = (await stack()).focused;
    await key("PageDown", "PageDown", 34);
    await still();
    const second = (await stack()).focused;
    await key("PageUp", "PageUp", 33);
    await still();
    const back = (await stack()).focused;
    await key("Home", "Home", 36);
    await still();
    const home = (await stack()).focused;
    check("Page Down and Page Up move between the shelves, and Home shows the whole stack", start === "stack" && first === "cell" && second === "er" && back === "cell" && home === "stack", JSON.stringify([start, first, second, back, home]));
    await key("PageDown", "PageDown", 34);
    await still();
    await both("human-shelf-wide");
    await key("Escape", "Escape", 27);
    await still();
    k = await stack();
    s = await state();
    check("Escape leaves the shelf for the whole stack, and the legend follows", k.focused === "stack" && /The whole stack=[\d,]+\*/.test(s.legend), JSON.stringify([k.focused, s.legend]));

    // A phone-sized window: one staircase, and the page opens on the first shelf.
    await size(390, 844);
    await open("lens=proteins&species=human&show=own");
    for (let tries = 0; tries < 160 && !(await evaluate(`Boolean(${L}.mounted)`)); tries++) await sleep(250);
    await still();
    k = await stack();
    check("a phone-sized window opens on the first shelf, of one staircase", k?.columns === 1 && k.opens === "shelf" && k.focused === "cell" && k.districts.length > 0 && k.districts.every((id) => id === "cell"), JSON.stringify([k?.columns, k?.opens, k?.focused, k?.districts.length]));
    if (outDir) {
      await named("cell");
      await both("human-shelf-phone");
      // The whole stack on the phone, as Home or the legend's row brings it.
      await evaluate(`${L}.mounted.focusOn(undefined)`);
      await still();
      await sleep(600);
      await both("human-stack-phone");
    }
    await size(WIDTH, HEIGHT);
  }

  if (scenario === "ecoli") {
    // A catalogue in families whose file lists sets to pick out (`highlights`): "show by" offers
    // them, the markers that hold the set are lit and say how many, and an open one shows which
    // of its members they are.
    await open("lens=proteins&species=ecoli&show=own");
    for (let tries = 0; tries < 160 && !(await evaluate(`Boolean(${L}.mounted)`)); tries++) await sleep(250);
    await still();
    const options = await evaluate(`[...${V}.shadowRoot.querySelectorAll("#cells-mark option")].map((option) => option.value + "=" + option.textContent + (option.selected ? "*" : ""))`);
    check("show by offers the shelves first, then the sets the file lists", options[0] === "=Shelves*" && options.includes("chemotaxis=Chemotaxis") && options.some((option) => option.startsWith("complex=")), JSON.stringify(options));
    await evaluate(`(() => { const select = ${V}.shadowRoot.querySelector("#cells-mark"); select.value = "chemotaxis"; select.dispatchEvent(new Event("change")); })()`);
    await sleep(800);
    await still();
    let s = await state();
    const set = await evaluate(`(() => { const view = ${L}.mounted, shelves = view.shelves, lit = [...view.nodes.values()].filter((node) => view.lit(node.item)); return { mark: view.mark, lit: lit.length, holding: lit.reduce((sum, node) => sum + shelves.highlightOf(node.item, "chemotaxis", "true").length, 0), tags: (view.setTags || []).length, shown: [...${V}.shadowRoot.querySelectorAll(".label-unit")].filter((el) => !el.classList.contains("is-off") && !el.hidden && / of the 22 · /.test(el.textContent)).length }; })()`);
    check("a set of one value is picked out when chosen: the markers that hold it are lit, and each says how many of the 22", set.mark?.name === "chemotaxis" && set.lit === 14 && set.holding === 22 && set.tags === 14 && set.shown > 0 && /Yes=22\*/.test(s.legend), JSON.stringify([set, s.legend]));
    await shot("ecoli-chemotaxis");
    // The marker, not a gathering, that holds the most of the set: opened, it shows which members they are.
    const most = await evaluate(`(() => { const view = ${L}.mounted, shelves = view.shelves, held = (node) => shelves.highlightOf(node.item, "chemotaxis", "true").length; const node = [...view.nodes.values()].filter((entry) => !entry.item.holds && held(entry)).sort((a, b) => held(b) - held(a))[0]; return { key: node.item.key, held: held(node), count: node.item.count }; })()`);
    await evaluate(`${V}.select(${JSON.stringify(most.key)}, { fly: true })`);
    await evaluate(`new Promise((resolve) => { const lens = ${L}, began = performance.now(); const wait = () => (lens.mounted?.opened?.key === ${JSON.stringify(most.key)} || performance.now() - began > 20000 ? resolve() : setTimeout(wait, 40)); wait(); })`);
    await still();
    const shown = await evaluate(`(() => { const view = ${L}.mounted; return { opened: view.opened?.key ?? null, members: view.dish?.count ?? null, lit: view.dish ? [...view.dish.nodes.values()].filter((entry) => view.lit(entry.item)).length : null, facts: [...${V}.shadowRoot.querySelectorAll("cells-panel .facts dt")].map((dt) => dt.textContent + ": " + dt.nextElementSibling.textContent).join(" | ") }; })()`);
    check("opened, it lights the members that are of the set, and its panel says how many and which", shown.opened === most.key && shown.members === most.count && shown.lit === most.held && new RegExp(`Chemotaxis: ${most.held} of the 22 proteins: `).test(shown.facts), JSON.stringify([most, shown]));
    await shot("ecoli-chemotaxis-open");
    await evaluate(`${V}.select(null)`);
    await evaluate(`${V}.current.back()`);
    await still();
    // Back to the plain view: nothing is picked out, and the legend lists the shelves again.
    await evaluate(`(() => { const select = ${V}.shadowRoot.querySelector("#cells-mark"); select.value = ""; select.dispatchEvent(new Event("change")); })()`);
    await sleep(600);
    s = await state();
    const plain = await evaluate(`(() => { const view = ${L}.mounted; return { mark: view.mark, lit: [...view.nodes.values()].filter((node) => view.lit(node.item)).length, markers: view.nodes.size, tags: (view.setTags || []).length }; })()`);
    check("show by the shelves again: every marker is lit, and the legend lists the shelves", plain.mark === null && plain.lit === plain.markers && plain.tags === 0 && /The whole stack=[\d,]+\*/.test(s.legend), JSON.stringify([plain, s.legend]));
  }

  if (scenario === "stack") {
    // A species with several shelves, held to its own file (SPECIES names it; thale cress by default):
    // every shelf of the file has a frame with its proteins and a line in the legend, a press on a
    // shelf's line brings that shelf into focus, and a press on "The whole stack" brings the stack back.
    const id = process.env.SPECIES || "thalecress";
    const file = JSON.parse(await readFile(new URL(`../data/proteins/${id}/shelves.json`, import.meta.url), "utf8"));
    await open(`lens=proteins&species=${id}&show=own`);
    for (let tries = 0; tries < 480 && !(await evaluate(`Boolean(${L}.mounted)`)); tries++) await sleep(250);
    await still();
    const drawn = () => evaluate(`(() => { const view = ${L}.mounted; if (!view) return null; return { species: view.shelves.id, frames: view.frames.map((item) => [item.id, item.proteins]), focused: view.focused === undefined ? "stack" : view.focused, ...view.drawn() }; })()`);
    const line = async (label) => {
      const at = await evaluate(`(() => { const el = [...${V}.shadowRoot.querySelectorAll("cells-legend .legend-item")].find((item) => item.querySelector(".legend-label")?.textContent === ${JSON.stringify(label)}); if (!el) return null; el.scrollIntoView({ block: "nearest" }); const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
      if (!at) throw new Error(`no line in the legend is called ${label}`);
      await click(at.x, at.y, 500);
      await still();
    };
    let d = await drawn();
    let s = await state();
    const has = (frames, shelf) => frames.some(([frame, proteins]) => frame === shelf.id && proteins === shelf.proteins);
    check("every shelf of the file has a frame with its proteins, one more holds what has no place, and markers stand on them", Boolean(d) && d.species === id && file.shelves.every((shelf) => has(d.frames, shelf)) && d.frames.length === file.shelves.length + 1 && d.markers > 0 && d.instances > 0 && d.focused === "stack", JSON.stringify(d));
    check("the legend lists the whole stack, pressed, and every shelf with its count", /(^|, )The whole stack=\d+\*/.test(s.legend) && file.shelves.every((shelf) => s.legend.includes(`${shelf.label}=${shelf.proteins}`)), s.legend);
    const one = file.shelves[Math.min(3, file.shelves.length - 1)];
    await line(one.label);
    d = await drawn();
    s = await state();
    check("a press on a shelf's line brings that shelf into focus", d.focused === one.id && s.legend.includes(`${one.label}=${one.proteins}*`), JSON.stringify([d.focused, s.legend]));
    await shot(`stack-${id}-shelf`);
    await line("The whole stack");
    d = await drawn();
    s = await state();
    check("a press on the whole stack brings the stack back", d.focused === "stack" && /(^|, )The whole stack=\d+\*/.test(s.legend), JSON.stringify([d.focused, s.legend]));
    await shot(`stack-${id}`);
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

  if (scenario === "pictures") {
    // Pictures asked for one by one, in real time, with what each shows and how long a frame of it takes to draw.
    const list = JSON.parse(await readFile(process.env.PICTURES, "utf8"));
    for (const item of list) {
      await size(...(item.size || [WIDTH, HEIGHT]));
      await open(item.query);
      await sleep(600);
      if (item.run) await evaluate(`(async () => { const viewer = ${V}, lens = viewer.current; ${item.run} })()`);
      await sleep(item.wait ?? 1500);
      const facts = await evaluate(`(() => {
        const viewer = ${V}, lens = viewer.current, view = lens.mounted, stage = viewer.stage;
        if (!view) return { mode: lens.mode, notice: viewer.shadowRoot.querySelector(".card-notice")?.textContent || null };
        // How long a frame takes to draw: the scene drawn twenty times, as the stage draws it.
        const began = performance.now();
        for (let index = 0; index < 20; index++) stage.renderer.render(stage.scene, stage.camera);
        const frame = (performance.now() - began) / 20;
        return { species: view.shelves.id, stands: view.shelves.stands, columns: view.arranged?.columns, frames: view.frames?.length, focused: view.focused === undefined ? "the whole stack" : view.focused, ...view.drawn(), labels: viewer.shadowRoot.querySelectorAll(".label:not([hidden])").length, frame_ms: Number(frame.toFixed(1)), calls: stage.renderer.info.render.calls, opened: view.opened?.key || null, status: view.status || null };
      })()`);
      note(`${item.name}: ${JSON.stringify(facts)}`);
      await shot(item.name);
    }
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
      for (const [side, unit] of [["in", "U01"], ["outside", "U39"], ["inside", "U47"]]) {
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
    await pickSpecies("planarian", 900);
    const worm = await state();
    check("the planarian's machines are drawn as before, with the same line", worm.show === "units" && worm.heading === "Planarian atlas" && /could not be loaded/.test(worm.notice || ""), JSON.stringify([worm.show, worm.heading, worm.notice]));
    await pickSpecies("human", 600);
    for (let tries = 0; tries < 60 && (await evaluate(`${L}.ownState("human")?.status`)) === "loading"; tries++) await sleep(250);
    const human = await state();
    // With a catalogue named in the scene, the human is like the others here: its files are not beside the page.
    if (await evaluate(`Boolean(${L}.atlas.shelves?.some((item) => item.id === "human"))`)) check("Human says its own proteins could not be loaded", /could not be loaded/.test(human.notice || ""), String(human.notice));
    else check("Human says its own catalogue is not made", /not made yet/.test(human.notice || ""), String(human.notice));
  }
} catch (error) {
  check("the run completed", false, error.stack || error.message);
} finally {
  for (const line of pageLog) console.log(line);
  // Whether the page's own font had arrived by the end: with the stand-in, words run longer and cards stand
  // taller, and a miss is read against that.
  note(`the page's own font: ${await evaluate(`document.fonts.status === "loaded" && ["Inter", "Space Grotesk"].every((family) => [...document.fonts].some((face) => face.family.includes(family) && face.status === "loaded")) ? "arrived" : "not arrived: the stand-in was shown, whose words run longer"`).catch(() => "not known")}`);
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
