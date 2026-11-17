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
//   PICTURES=DIR node tools/check_species.mjs   pictures of the species dropdown into DIR, and no checks
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
// The species switch is a dropdown. Where its pill stands, and whether its list is open.
const pill = () => evaluate(`(() => { const el = [...${V}.shadowRoot.querySelectorAll(".species-pick")].find((b) => b.offsetParent); if (!el) return null; el.scrollIntoView({ block: "nearest" }); const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2, expanded: el.getAttribute("aria-expanded") }; })()`);
// What the open list shows: its rows as a visitor reads them, and where it lies in the window.
const list = () =>
  evaluate(`(() => {
    const root = ${V}.shadowRoot, box = root.querySelector(".species-list"), button = [...root.querySelectorAll(".species-pick")].find((b) => b.offsetParent);
    if (!box || box.hidden) return { open: false, expanded: button?.getAttribute("aria-expanded") ?? null };
    const r = box.getBoundingClientRect(), b = button.getBoundingClientRect();
    return {
      open: true,
      expanded: button.getAttribute("aria-expanded"),
      roles: [button.getAttribute("role"), button.getAttribute("aria-haspopup"), button.getAttribute("aria-controls"), box.getAttribute("role"), box.id].join(" "),
      active: button.getAttribute("aria-activedescendant"),
      marked: [...box.querySelectorAll(".is-active")].map((row) => row.id).join(" "),
      rows: [...box.querySelectorAll('[role="option"]')].map((row) => ({ id: row.dataset.species, selected: row.getAttribute("aria-selected"), name: row.querySelector(".species-option-name")?.textContent ?? null, organism: row.querySelector(".species-option-organism")?.textContent ?? null, italic: getComputedStyle(row.querySelector(".species-option-organism") || row).fontStyle, state: row.querySelector(".species-option-state")?.textContent ?? null, label: row.getAttribute("aria-label"), group: row.closest('[role="group"]')?.querySelector(".species-group-name")?.textContent ?? "" })),
      inside: r.left >= -0.5 && r.right <= innerWidth + 0.5 && r.top >= -0.5 && r.bottom <= innerHeight + 0.5,
      under: r.top >= b.bottom - 0.5 && r.top <= b.bottom + 12,
      box: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)],
    };
  })()`);
// Wait until the list is open or closed, as asked (at most three seconds).
const settled = async (open) => {
  for (let tries = 0; tries < 30; tries++) {
    if ((await list()).open === open) return true;
    await sleep(100);
  }
  return false;
};
const openList = async () => {
  if ((await list()).open) return;
  const at = await pill();
  if (!at) throw new Error("the species switch is not shown");
  await click(at.x, at.y);
  if (!(await settled(true))) throw new Error("the list of species did not open");
};
const rowAt = (id) => evaluate(`(() => { const el = ${V}.shadowRoot.querySelector('.species-list [data-species="${id}"]'); if (!el || !el.offsetParent) return null; el.scrollIntoView({ block: "nearest" }); const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
const pressSpecies = async (id) => {
  await openList();
  const at = await rowAt(id);
  if (!at) throw new Error(`no row for the species ${id}`);
  await click(at.x, at.y);
  if (!(await settled(false))) throw new Error("the list of species did not close");
  await sleep(150);
};
const keyCodes = { Enter: [13, "\r"], Escape: [27], ArrowDown: [40], ArrowUp: [38], Home: [36], End: [35], Tab: [9], " ": [32, " "] };
const key = async (name) => {
  const [code, text] = keyCodes[name] || [name.toUpperCase().charCodeAt(0), name];
  await page("Input.dispatchKeyEvent", { type: text ? "keyDown" : "rawKeyDown", key: name, code: name.length === 1 ? (name === " " ? "Space" : `Key${name.toUpperCase()}`) : name, windowsVirtualKeyCode: code, ...(text ? { text } : {}) });
  await page("Input.dispatchKeyEvent", { type: "keyUp", key: name, code: name.length === 1 ? (name === " " ? "Space" : `Key${name.toUpperCase()}`) : name, windowsVirtualKeyCode: code });
  await sleep(180);
};
const focused = () => evaluate(`(() => { const el = ${V}.shadowRoot.activeElement; return el ? (el.classList.contains("species-pick") ? "pill" : el.tagName.toLowerCase()) : null; })()`);
// What Cells models of an entry, in the ladder's words (schema/ENTRIES.md).
const WORDS = { generic: "Generic cell", proposed: "Proposed, not modelled", planned: "Planned, not modelled", designed: "Designed, not modelled", modelled: "Modelled" };
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
      // The dropdown's pill, where it stands, with the species it names (starred, as the pressed button was).
      inBar: [...root.querySelectorAll(".species .species-pick")].filter(shown).map((b) => b.dataset.speciesPick + "*").join(" "),
      inCard: [...root.querySelectorAll(".view .species-pick")].filter(shown).map((b) => b.dataset.speciesPick + "*").join(" "),
      pillText: [...root.querySelectorAll(".species-pick")].filter(shown).map((b) => [...b.querySelectorAll(".species-pick-name > span")].filter((span) => span.getAttribute("aria-hidden") !== "true").map((span) => span.textContent).join("|"))[0] ?? null,
      pillLabel: [...root.querySelectorAll(".species-pick")].filter(shown).map((b) => b.getAttribute("aria-label"))[0] ?? null,
      pills: [...root.querySelectorAll(".species-pick")].filter(shown).length,
      oldButtons: root.querySelectorAll(".seg [data-species]").length,
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

// PICTURES=DIR writes pictures of the dropdown into DIR and runs no checks: closed, open, a row
// under the pointer, and on a phone, in light and dark. One short hold of the browser.
if (process.env.PICTURES) {
  const { mkdir, writeFile } = await import("node:fs/promises");
  const dir = process.env.PICTURES;
  await mkdir(dir, { recursive: true });
  // A picture is taken with the page's own fonts in place, where the network gives them.
  const shot = async (name) => {
    await evaluate(`Promise.race([document.fonts.ready, new Promise((resolve) => setTimeout(resolve, 8000))]).then(() => document.fonts.status)`);
    await sleep(300);
    await writeFile(`${dir}/${name}.png`, Buffer.from((await page("Page.captureScreenshot", { format: "png" })).data, "base64"));
  };
  try {
    for (const theme of ["light", "dark"]) {
      await size(WIDTH, 800);
      await open(`lens=cell&theme=${theme}`);
      await shot(`dropdown-closed-${theme}`);
      await openList();
      await shot(`dropdown-open-${theme}`);
      const other = await evaluate(`${V}.speciesShown.rows.find((row) => row.id !== ${V}.speciesShown.active).id`);
      const at = await rowAt(other);
      await mouse("mouseMoved", at.x, at.y, { button: "none", buttons: 0 });
      await sleep(250);
      await shot(`dropdown-row-under-pointer-${theme}`);
      await size(400, 800);
      await open(`lens=cell&theme=${theme}`);
      await shot(`dropdown-phone-closed-${theme}`);
      await openList();
      await shot(`dropdown-phone-open-${theme}`);
    }
    await size(WIDTH, 800);
    await open("lens=proteins&species=syn3a");
    await openList();
    await shot("dropdown-open-in-atlas-light");
  } finally {
    socket.close();
    { const closed = new Promise((resolve) => chrome.once("close", resolve)); chrome.kill(); await Promise.race([closed, new Promise((resolve) => setTimeout(resolve, 4000))]); if (chrome.exitCode === null && chrome.signalCode === null) chrome.kill("SIGKILL"); await Promise.race([closed, new Promise((resolve) => setTimeout(resolve, 2000))]); }
    server.close();
    release();
  }
  process.exit(0);
}

// CASE=model: a model system chosen in the switch (schema/MODEL_SYSTEMS.md, src/ui/entry_views.js):
// it is shown in the Cell view's place, with its levels, its line and its word, and the page comes
// back to a species. SHOTS=DIR also writes pictures of it into DIR, never of the browser's first page.
if (process.env.CASE === "model") {
  const SHOTS = process.env.SHOTS || null;
  const shot = async (name) => {
    if (!SHOTS) return;
    const { mkdir, writeFile } = await import("node:fs/promises");
    await mkdir(SHOTS, { recursive: true });
    await evaluate(`Promise.race([document.fonts.ready, new Promise((resolve) => setTimeout(resolve, 8000))]).then(() => document.fonts.status)`);
    await sleep(400);
    await writeFile(`${SHOTS}/${name}.png`, Buffer.from((await page("Page.captureScreenshot", { format: "png" })).data, "base64"));
  };
  // What the page shows of the entry: which one, which view stands in the first tab's place, and its words.
  const more = () =>
    evaluate(`(() => {
      const v = ${V}, root = v.shadowRoot, tab = root.querySelector('.switch [data-lens="cell"]');
      return {
        model: v.state.model ?? null,
        entry: v.dataset.entry ?? null,
        current: v.current?.id ?? null,
        tab: [tab?.querySelector(".long")?.textContent, tab?.querySelector(".short")?.textContent, tab?.getAttribute("aria-pressed")].join("|"),
        railTitle: root.querySelector(".rail:not([hidden]) .rail-title")?.textContent ?? null,
        organism: root.querySelector(".view-card .card-organism")?.textContent ?? null,
        caveatShown: !root.querySelector(".caveat").hidden,
        address: location.search,
        errors: 0,
      };
    })()`);
  const lower = (word) => word.charAt(0).toLowerCase() + word.slice(1);
  const escape = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  // Where the stage keeps room clear, and what the Laws library has picked out.
  const stageNow = () => evaluate(`(() => { const v = ${V}; return { left: v.stage?.insets?.left || 0, wants: Boolean(v.current?.wantsLeftRoom), filter: v.state.lens === "laws" && v.current?.filter ? { ...v.current.filter } : null, legend: !v.shadowRoot.querySelector("cells-legend")?.hidden }; })()`);
  const until = async (test, tries = 240) => {
    for (let i = 0; i < tries; i++) {
      if (await evaluate(test).catch(() => false)) return true;
      await sleep(250);
    }
    return false;
  };
  // With the model system chosen in the first tab: each of the other four tabs, real presses throughout, and back.
  // `from` names where the tour began in the checks' words; pictures are taken on the first tour only.
  let gard = null;
  // What shows the model system, found once it is chosen: its card while no view is registered for its kind, or that
  // view (src/ui/entry_views.js), whose tab, heading and legend are its own. `shown` is that lens's id, `tab` the first
  // tab's two names ("<long>|<short>"); a registered view arrives after its run files are read, and is waited for.
  let shown = "model", tab = "Model system|Model", card = true;
  const settled = async () => {
    if (!card) await until(`${V}.state.lens !== "cell" || (${V}.current?.id !== "model")`, 240);
  };
  const tour = async (from, { pictures = false } = {}) => {
    let s = await state(), m = await more();
    const last = s.species;
    const lastLabel = await evaluate(`${V}.model.raw.species.find((item) => item.id === ${JSON.stringify(last)})?.label ?? null`);
    check(`${from}: the tour starts on the model system, shown by ${card ? "its card" : `its view (${shown})`}`, m.model === gard.id && m.current === shown && s.lens === "cell", JSON.stringify([m.model, m.current, s.lens]));
    // The Protein atlas: the species last shown, with the model system's sentence before its own caveat.
    await press('.switch [data-lens="proteins"]');
    s = await state();
    check(`${from}: the Protein atlas keeps ${lastLabel}, the pill names the model system, and its caveat's first sentence says a model system has no proteins of a species`, s.lens === "proteins" && s.species === last && `${s.inBar}${s.inCard}` === `${gard.id}*` && new RegExp(`^${escape(gard.label)} is a model system, not an organism: it has no proteins of a species\\. The atlas shows the machines Cells has laws for, as for ${escape(lastLabel)}\\.`).test(s.caveat || ""), JSON.stringify([s.lens, s.species, s.inBar, s.inCard, s.caveat]));
    // Its own proteins, where it has them: the trail, the map of the stack, the search and the Colour select.
    if ((await evaluate(`${V}.current.mode`)) !== "own" && (await evaluate(`Boolean(${V}.shadowRoot.querySelector('.view-card [data-show="own"]'))`))) await press('.view-card [data-show="own"]');
    const mounted = await until(`Boolean(${V}.current.mounted)`, 480);
    await sleep(600);
    const nav = await evaluate(`(() => { const v = ${V}, root = v.shadowRoot, lens = v.current, shelves = lens.mounted?.shelves; return { trail: root.querySelector(".atlas-trail:not([hidden])") ? (lens.trailLevels?.() || []).map((level) => level.label).join(" > ") : "", label: shelves?.label ?? null, several: Boolean(shelves?.several), map: [...root.querySelectorAll(".atlas-map:not([hidden]) .atlas-row")].map((row) => row.title) }; })()`);
    check(`${from}: the atlas shows ${lastLabel}'s own proteins, and the trail names ${lastLabel}, not the model system`, mounted && nav.trail.startsWith(`${nav.label} · `) && !nav.trail.includes(gard.label) && !new RegExp(`\\b${escape(gard.id)}\\b`, "i").test(nav.trail), JSON.stringify(nav));
    if (nav.several) check(`${from}: the map of the stack shows where ${lastLabel} has shelves`, nav.map.length >= 3 && nav.map[0].startsWith("The whole stack"), JSON.stringify(nav.map));
    if (pictures) await shot("model-atlas-light");
    if (await evaluate(`Boolean(${V}.shadowRoot.querySelector("#atlas-find"))`)) {
      await press("#atlas-find");
      await page("Input.insertText", { text: "kinase" });
      const found = await until(`Boolean(${V}.shadowRoot.querySelector(".atlas-results:not([hidden]) .atlas-hit"))`, 80);
      const hits = await evaluate(`${V}.shadowRoot.querySelectorAll(".atlas-results .atlas-hit").length`);
      check(`${from}: the trail's search finds ${lastLabel}'s proteins`, found && hits > 0, String(hits));
      await evaluate(`(() => { const input = ${V}.shadowRoot.querySelector("#atlas-find"); input.value = ""; input.dispatchEvent(new Event("input")); })()`); // (scripted: the field emptied)
      await key("Escape");
    } else check(`${from}: the trail has its search`, false, "no #atlas-find");
    if (await evaluate(`Boolean(${V}.shadowRoot.querySelector("#cells-own-colour"))`)) {
      const before = await evaluate(`${V}.current.mounted?.colourBy ?? null`);
      await press("#cells-own-colour");
      await key("Escape");
      await key("ArrowDown");
      await sleep(300);
      const after = await evaluate(`${V}.current.mounted?.colourBy ?? null`);
      check(`${from}: the legend's Colour select answers`, before !== null && after !== null && after !== before, JSON.stringify([before, after]));
    } else check(`${from}: the legend has its Colour select`, false, "no #cells-own-colour");
    // Experiments and Engine: no switch.
    if (await evaluate(`Boolean(${V}.shadowRoot.querySelector('.switch [data-lens="experiments"]'))`)) {
      await press('.switch [data-lens="experiments"]');
      s = await state();
      check(`${from}: the Experiments view shows no switch`, s.lens === "experiments" && s.inBar === "" && s.inCard === "", JSON.stringify([s.lens, s.inBar, s.inCard]));
    }
    // The Laws library, by its tab: none of the model system's card in its chrome.
    await press('.switch [data-lens="laws"]');
    await sleep(600);
    s = await state();
    m = await more();
    let at = await stageNow();
    check(`${from}: the Laws library opens with the model system chosen, with no switch, and nothing of the model system's card in its chrome`, s.lens === "laws" && m.model === gard.id && s.inBar === "" && s.inCard === "" && m.railTitle !== "Level" && s.heading !== gard.label && m.tab === `${tab}|false`, JSON.stringify([s.lens, m, s.heading, s.inBar, s.inCard]));
    if (pictures) await shot("model-laws-light");
    // The Engine view, and a door from one of its boxes into the library and back.
    await press('.switch [data-lens="engine"]');
    s = await state();
    check(`${from}: the Engine view shows no switch`, s.lens === "engine" && s.inBar === "" && s.inCard === "", JSON.stringify([s.lens, s.inBar, s.inCard]));
    const box = await evaluate(`(() => { const v = ${V}; return ["laws.pumps", ...v.model.entities.map((entity) => entity.id)].find((id) => v.model.get(id) && (v.lookup(id)?.doors || []).some((door) => /in the Laws library/.test(door.label))) || null; })()`);
    if (box) {
      await evaluate(`${V}.select(${JSON.stringify(box)})`); // (scripted: the box chosen, as tools/check_laws.mjs chooses it)
      await sleep(500);
      await evaluate(`(() => { const door = [...${V}.shadowRoot.querySelectorAll("cells-panel .panel-door button")].find((button) => /in the Laws library/.test(button.textContent)); if (door) door.dataset.lawsDoor = "1"; })()`);
      await press('cells-panel [data-laws-door="1"]');
      await until(`${V}.state.lens === "laws"`, 40);
      at = await stageNow();
      check(`${from}: the door of the Engine box ${box} opens the Laws library with its pieces picked out`, (await state()).lens === "laws" && at.filter?.box === box, JSON.stringify(at));
      const piece = await evaluate(`${V}.current.order()[0] || null`);
      if (piece) {
        await evaluate(`${V}.select(${JSON.stringify(piece)})`); // (scripted: a piece chosen)
        await sleep(800);
        const back = await evaluate(`(() => { const link = [...${V}.shadowRoot.querySelectorAll("cells-panel .panel-list")].find((list) => list.querySelector("h4")?.textContent.startsWith("On the Engine view"))?.querySelector(".link-button"); if (!link) return null; link.dataset.back = "1"; return true; })()`);
        if (back) {
          await press('cells-panel [data-back="1"]');
          await until(`${V}.state.lens === "engine"`, 40);
        }
        s = await state();
        check(`${from}: and the piece's link goes back to the Engine view, on its box`, Boolean(back) && s.lens === "engine" && s.selected === box, JSON.stringify([back, s.lens, s.selected]));
      }
      await evaluate(`${V}.select(null)`);
    } else check(`${from}: an Engine box has a door into the Laws library`, false, "none found");
    // Back on the first tab: the model system, its name, its rail and its card, and no room kept on the left.
    await press('.switch [data-lens="cell"]');
    await sleep(500);
    s = await state();
    m = await more();
    at = await stageNow();
    check(`${from}: back on the first tab it is the model system, with its tab's name, its rail under Level, ${card ? "its card and no legend" : "its view"}, and none of the library's room kept on the left (only what the view asks for itself)`, m.model === gard.id && m.current === shown && m.tab === `${tab}|true` && s.rail.replace("*", "") === gard.levels.join(" ") && m.railTitle === "Level" && (!card || (s.heading === gard.label && !at.legend)) && (!at.left || at.wants), JSON.stringify([m, s.rail, s.heading, at]));
  };
  try {
    await open("lens=cell");
    // The browser's first page is not pictured: its first context is lost and made again a few seconds in.
    if (SHOTS) {
      await sleep(6000);
      await open("lens=cell");
    }
    const models = await evaluate(`(${V}.model.raw.models || []).map((item) => ({ id: item.id, label: item.label, is: item.is, group: item.group || "", state: item.modelled.state, levels: item.levels.map((level) => level.id), labels: item.levels.map((level) => level.label), view: item.view?.kind, notes: (item.notes || []).length }))`);
    const species = await evaluate(`${V}.model.raw.species.map((item) => ({ id: item.id, group: item.group || "", state: item.modelled.state }))`);
    const syn3aState = species.find((item) => item.id === "syn3a")?.state;
    check("the scene carries a model system beside its species", models.length >= 1 && species.length >= 1, JSON.stringify(models.map((item) => item.id)));
    gard = models[0];
    const first = species.find((item) => item.id === "planarian") ? "planarian" : (await state()).species;
    await openList();
    let l = await list();
    check("the list holds each model system after the species, under a heading no species has, its line what it is (upright), with its word", JSON.stringify(l.rows.slice(-models.length).map((row) => row.id)) === JSON.stringify(models.map((item) => item.id)) && models.every((item) => { const row = l.rows.find((r) => r.id === item.id); return row && row.group === item.group && item.group && !species.some((one) => one.group === item.group) && row.organism === item.is && row.italic === "normal" && row.state === WORDS[item.state] && row.label === [item.label, item.is, WORDS[item.state]].join(", "); }), JSON.stringify(l.rows.slice(-models.length - 1)));
    await shot("model-list-open-light");
    await key("Escape");

    // Chosen with the pointer: it takes the Cell view's place.
    await pressSpecies(gard.id);
    let s = await state(), m = await more();
    check("choosing it shows it in the first tab's place: the tab takes its view's name, the pill names it", m.model === gard.id && m.entry === gard.id && s.lens === "cell" && m.tab.endsWith("|true") && !m.tab.startsWith("Cell and scales|") && `${s.inBar}${s.inCard}` === `${gard.id}*` && s.pillText === gard.label, JSON.stringify([m, s.inBar, s.inCard, s.pillText]));
    check("the statement beside the pill says what Cells models of it, in the ladder's words, and not modelled", s.state === WORDS[gard.state] && gard.state !== "modelled" && gard.state !== "generic", String(s.state));
    // The switch does not call a model system a species: its label reads "Model", and it is read out as a model system.
    const named = await evaluate(`(() => { const root = ${V}.shadowRoot, shown = (el) => Boolean(el) && el.getClientRects().length > 0; return { label: [...root.querySelectorAll(".species-label, .seg-species .seg-label")].filter(shown).map((el) => el.textContent)[0] ?? null, list: root.querySelector("#species-list")?.getAttribute("aria-label") ?? null }; })()`);
    check("the switch calls it a model, not a species, in its label and to a screen reader", named.label === "Model" && s.pillLabel === `Model system: ${gard.label}` && named.list === "Species and model systems", JSON.stringify([named, s.pillLabel]));
    check("the address names it", new URLSearchParams(m.address).get("entry") === gard.id, m.address);
    tab = m.tab.split("|").slice(0, 2).join("|");
    card = tab === "Model system|Model";
    await settled();
    s = await state();
    m = await more();
    shown = m.current;
    check("what shows it is its card where no view is registered for its kind, else that view, once its run files are read", card ? shown === "model" : shown !== "model" && shown !== "cell", JSON.stringify([tab, shown]));
    console.log(`note  ${gard.label} is shown ${card ? "by its card: no view is registered for its kind" : `by its own view (${shown}), tab ${tab}`} (view.kind ${gard.view})`);
    if (!card) {
      // A view's chrome reaches the page (src/ui/entry_views.js): its timeline bound, its legend's note shown, its other choices on its card.
      const given = await evaluate(`(() => { const v = ${V}, root = v.shadowRoot, chrome = v.current.chrome(); const caveat = root.querySelector(".caveat"), timeline = root.querySelector("cells-timeline"); return { timeline: Boolean(chrome.timeline), timelineShown: Boolean(timeline && !timeline.hidden), note: chrome.legend?.note?.text || null, noteShown: [...root.querySelectorAll("cells-legend .legend-note, cells-legend .legend-key-note")].map((p) => p.textContent).join(" "), choices: (chrome.card?.choices || []).map((item) => item.key).join(" "), selects: [...root.querySelectorAll(".view-card select[data-choice]")].map((el) => el.dataset.choice).join(" "), caveat: caveat.hidden ? null : caveat.textContent }; })()`);
      check("its view's timeline is the page's, its legend's note is shown, its other choices are on its card, and no caveat lies over the timeline", (!given.timeline || given.timelineShown) && (!given.note || given.noteShown.includes(given.note)) && given.choices === given.selects && (!given.timeline || !given.caveat), JSON.stringify(given));
    }
    if (card) {
      check("its card: the first tab is named Model system", m.tab.startsWith("Model system|Model|"), m.tab);
      check("its card: its levels are the rail, under Level", s.rail.replace("*", "").split(" ").join(" ") === gard.levels.join(" ") && m.railTitle === "Level", JSON.stringify([s.rail, m.railTitle]));
      check("its card: the caveat gives its word and says its view is not on this page yet", new RegExp(`^${gard.label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}: ${lower(WORDS[gard.state])}\\.`).test(s.caveat || "") && /not on this page yet/.test(s.caveat || "") && m.caveatShown, String(s.caveat));
      check("its card: its name and what it is, and no cell's sizes or colours", s.heading === gard.label && m.organism === gard.is && s.sizes === "", JSON.stringify([s.heading, m.organism, s.sizes]));
      // A level of the rail opens its panel.
      await press(`.rail [data-stop="${gard.levels.at(-1)}"]`);
      s = await state();
      check("a level of the rail opens what it will show", s.selected === `model:${gard.id}:level:${gard.levels.at(-1)}` && s.panel?.title === gard.labels.at(-1) && s.rail.includes(`${gard.levels.at(-1)}*`), JSON.stringify([s.selected, s.panel?.title, s.rail]));
    }
    // What it is, in the panel.
    await press(".species-state");
    s = await state();
    check("pressing the statement opens all that is said of it: a model system, its word, nothing of it in the engine, and its notes where it has any", s.selected === `model:${gard.id}` && s.panel?.title === gard.label && s.panel.eyebrow === "Model system" && s.panel.chips.includes(WORDS[gard.state]) && /nothing of \S+ is in the engine/i.test(s.panel.plain || "") && /Notes/.test(s.panel.heads || "") === gard.notes > 0, JSON.stringify(s.panel));
    await shot("model-panel-light");
    if (gard.notes) {
      await evaluate(`[...${V}.shadowRoot.querySelectorAll("cells-panel .panel-list h4")].find((h) => h.textContent.startsWith("Notes"))?.scrollIntoView({ block: "start" })`);
      await shot("model-panel-notes-light");
    }

    // The other four tabs, and back to the first (the tour is below): from the switch, with a species that has a stack of
    // shelves shown last, so that the atlas's map has shelves to show.
    if (species.some((item) => item.id === "thalecress")) {
      await pressSpecies("thalecress");
      await pressSpecies(gard.id);
    }
    await tour("from the switch", { pictures: true });

    // A species chosen again: the Cell view comes back, under its own name.
    await pressSpecies("syn3a");
    s = await state();
    m = await more();
    check("choosing a species brings the Cell view back, under its own name, with that species", m.model === null && m.entry === null && m.current === "cell" && m.tab === "Cell and scales|Cell|true" && s.species === "syn3a" && s.rail === "molecule cell*" && s.state === WORDS[syn3aState] && new URLSearchParams(m.address).get("entry") === "syn3a", JSON.stringify([m, s.species, s.rail, s.state]));
    await shot("model-then-species-light"); // the Cell view as it comes back after the model system's view
    await pressSpecies(gard.id);
    await press('.switch [data-lens="proteins"]');
    await pressSpecies(first);
    s = await state();
    m = await more();
    check("a species chosen in the atlas lets the model system go; the first tab is the Cell view again", m.model === null && s.species === first && !/model system/.test(s.caveat || "") && m.tab === "Cell and scales|Cell|false", JSON.stringify([m, s.species, s.caveat]));

    // The address.
    await open(`lens=cell&entry=${gard.id}`);
    s = await state();
    m = await more();
    await settled();
    m = await more();
    check("entry= in the address opens it", m.model === gard.id && m.current === shown && `${s.inBar}${s.inCard}` === `${gard.id}*`, JSON.stringify([m, s.inBar, s.inCard]));
    await shot("model-card-light");
    await tour("from entry= in the address");
    // An address that names a view and the model system: the view it names, with the model system chosen for the first tab.
    await open(`lens=laws&entry=${gard.id}`);
    s = await state();
    m = await more();
    check("lens=laws&entry= opens the Laws library, with no switch, and the model system chosen for the first tab", s.lens === "laws" && m.model === gard.id && m.tab === `${tab}|false` && s.inBar === "" && s.inCard === "" && m.railTitle !== "Level", JSON.stringify([s.lens, m, s.inBar, s.inCard]));
    await press('.switch [data-lens="cell"]');
    s = await state();
    m = await more();
    await settled();
    s = await state();
    m = await more();
    check("its first tab then shows the model system, its levels on the rail", m.current === shown && m.tab === `${tab}|true` && s.rail.replace("*", "") === gard.levels.join(" ") && (!card || s.heading === gard.label), JSON.stringify([m, s.rail, s.heading]));
    await tour("from lens=laws&entry= in the address");
    await open(`lens=proteins&entry=${gard.id}`);
    s = await state();
    check("entry= with the atlas: the atlas, its caveat, the pill on the model system", s.lens === "proteins" && /is a model system, not an organism/.test(s.caveat || "") && `${s.inBar}${s.inCard}` === `${gard.id}*`, JSON.stringify([s.lens, s.caveat, s.inBar]));
    await open("lens=cell&entry=no-such-entry");
    s = await state();
    m = await more();
    check("an unknown entry in the address is ignored", m.model === null && s.species === first && m.current === "cell", JSON.stringify([m.model, s.species, m.current]));
    // That Cell view is one opened alone: after the model system's view, and back by the switch, it is the same.
    const look = () => evaluate(`(() => { const v = ${V}, st = v.stage, r = st.renderer; return { sun: st.sun ? st.sun.position.toArray().map((x) => +x.toFixed(3)) : null, shadow: st.sun?.castShadow ?? null, limits: { ...st.rig.limits }, environment: Boolean(st.scene.environment), exposure: +r.toneMappingExposure.toFixed(3), toneMapping: r.toneMapping, bloom: st.finish?.bloom?.strength ?? 0, insets: st.insets || {} }; })()`);
    const alone = await look();
    await pressSpecies(gard.id);
    await settled();
    await sleep(600);
    await pressSpecies(first);
    await sleep(800);
    const after = await look();
    check("a Cell view opened after the model system's view is as one opened alone: light, shade, bloom, limits and insets", JSON.stringify(after) === JSON.stringify(alone), JSON.stringify([alone, after]));
    await open(`lens=cell&entry=${gard.id}&theme=dark`);
    await shot("model-card-dark");
    await openList();
    await shot("model-list-open-dark");
    await key("Escape");

    // A phone: the card folds to one line that names the model system (the phone's third pass, 17 November 2026); one press
    // opens it, with the switch at its head and the model system's word.
    await size(400, 800);
    await open(`lens=cell&entry=${gard.id}`);
    await settled();
    // The folded line and the rail's button: the line names the model system, whole, and the two do not meet.
    const band = () =>
      evaluate(`(() => { const root = ${V}.shadowRoot, shown = (el) => Boolean(el) && el.getClientRects().length > 0, t = root.querySelector(".view-toggle"), r = root.querySelector(".rail-toggle"), line = t?.firstChild; const a = shown(t) ? t.getBoundingClientRect() : null, b = shown(r) ? r.getBoundingClientRect() : null; return { folded: shown(t) && !shown(root.querySelector("#cells-view")), words: line?.textContent ?? null, whole: Boolean(line) && line.scrollWidth <= line.clientWidth + 1, apart: !a || !b || a.right <= b.left - 0.5 || a.bottom <= b.top + 0.5 || b.bottom <= a.top + 0.5, under: root.querySelector(".frame").classList.contains("rail-under") }; })()`);
    let folded = await band();
    check("on a phone its card folds to one line that names it, whole, and the line and the rail's button do not meet", folded.folded && folded.words === gard.label && folded.whole && folded.apart, JSON.stringify(folded));
    await press(".view-toggle");
    s = await state();
    m = await more();
    // Nothing of the bar lies under the rail's button, however many rows the bar takes (a longer first tab may take two).
    const clear = await evaluate(`(() => { const root = ${V}.shadowRoot, rail = root.querySelector(".rail-toggle"), r = rail?.getBoundingClientRect(); if (!r || !r.width) return true; return [...root.querySelectorAll(".bar .switch button, .bar .bar-end > *")].filter((el) => el.offsetParent).every((el) => { const b = el.getBoundingClientRect(); return b.bottom <= r.top + 0.5 || b.top >= r.bottom - 0.5 || b.right <= r.left + 0.5 || b.left >= r.right - 0.5; }); })()`);
    check("on a phone one press opens the card: the switch stands in it, it names the model system and gives its word, and nothing of the bar is under the rail's button", s.inBar === "" && s.inCard === `${gard.id}*` && (!card || s.heading === gard.label) && m.model === gard.id && s.state === WORDS[gard.state] && clear, JSON.stringify([s.inBar, s.inCard, s.heading, s.state, m.tab, clear]));
    await shot("model-phone-card-open-light");
    await press(".view-toggle");
    // Where the bar's parts stand on a phone, in the run's words, for reading a miss.
    console.log(`note  the bar on a phone: ${await evaluate(`(() => { const root = ${V}.shadowRoot, r = (el) => el ? [Math.round(el.getBoundingClientRect().left), Math.round(el.getBoundingClientRect().top), Math.round(el.getBoundingClientRect().right)].join(",") : "none"; return ["brand " + r(root.querySelector(".brand")), "switch " + r(root.querySelector(".switch")), ...[...root.querySelectorAll(".switch button")].map((b) => b.dataset.lens + " " + r(b)), "list " + r(root.querySelector(".bar-end")), "rail " + r(root.querySelector(".rail-toggle"))].join("; "); })()`)}`);
    await shot("model-phone-light");
    // Its rail opened there: its levels stand under its button, clear of the bar.
    await press(".rail-toggle");
    const rail = await evaluate(`(() => { const root = ${V}.shadowRoot, t = root.querySelector(".rail-toggle").getBoundingClientRect(), r = root.querySelector(".rail").getBoundingClientRect(), list = root.querySelector(".bar-end").getBoundingClientRect(); return { below: r.top >= t.bottom - 0.5, clear: t.top >= list.bottom - 0.5 || t.right <= list.left + 0.5, levels: [...root.querySelectorAll(".rail button")].map((b) => b.dataset.stop).join(" ") }; })()`);
    check("on a phone its rail opens under its button with its levels, and the button is clear of the bar", rail.below && rail.clear && rail.levels === gard.levels.join(" "), JSON.stringify(rail));
    await shot("model-phone-rail-light");
    await press(".rail-toggle");
    // The phone's second pass (17 November 2026): at 390 px the bar stands on one row with the model system's longer first
    // tab, every button of it at least 44 px, with the page's own font and with the stand-in, whose words run longer.
    await size(390, 844);
    await open(`lens=cell&entry=${gard.id}`);
    await settled();
    const barNow = () =>
      evaluate(`(() => {
        const root = ${V}.shadowRoot, shown = (el) => Boolean(el) && el.getClientRects().length > 0;
        const kids = [...root.querySelector(".bar").children].filter(shown).map((el) => el.getBoundingClientRect()).filter((r) => r.width > 1); // the page's name put out of sight is 1 px
        const presses = [...root.querySelectorAll(".bar button")].filter(shown).map((el) => { const r = el.getBoundingClientRect(); return Math.round(Math.min(r.width, r.height)); });
        return { row: kids.every((a) => kids.every((b) => a.top < b.bottom - 1 && b.top < a.bottom - 1)), least: Math.min(...presses), squeeze: root.querySelector(".bar").dataset.squeeze || "", tabs: [...root.querySelectorAll(".switch button")].map((b) => b.textContent).join(" "), sideways: document.documentElement.scrollWidth > innerWidth + 1 };
      })()`);
    let barRow = await barNow();
    check("on a 390 px phone the bar stands on one row with a model system's first tab, each of its buttons at least 44 px", barRow.row && barRow.least >= 44 && !barRow.sideways, JSON.stringify(barRow));
    await evaluate(`(async () => { document.querySelector('link[href*="fonts.googleapis"]')?.remove(); await new Promise((resolve) => setTimeout(resolve, 400)); ${V}.renderChrome(); })()`);
    barRow = await barNow();
    check("and so it does with the stand-in font, whose words run longer", barRow.row && barRow.least >= 44 && !barRow.sideways, JSON.stringify(barRow));
    await shot("model-phone-390-standin");
    // The third pass: so it does at 360 px, the narrowest phone the page is laid out for, with both fonts; and the folded
    // card's line, whole, and the rail's button keep apart there (the button steps under the line where they would meet).
    await size(360, 780);
    await open(`lens=cell&entry=${gard.id}`);
    await settled();
    // The page's own font is waited for (it may not come: then the note at the end says so, and both checks see the stand-in).
    const lettered = `document.fonts.status === "loaded" && ["Inter", "Space Grotesk"].every((family) => [...document.fonts].some((face) => face.family.includes(family) && face.status === "loaded"))`;
    if (await until(lettered, 40)) await evaluate(`${V}.renderChrome()`);
    for (const font of ["the page's own font", "the stand-in font"]) {
      if (font === "the stand-in font") await evaluate(`(async () => { document.querySelector('link[href*="fonts.googleapis"]')?.remove(); await new Promise((resolve) => setTimeout(resolve, 400)); ${V}.renderChrome(); })()`);
      else console.log(`note  at 360 px the page's own font has ${(await evaluate(lettered).catch(() => false)) ? "arrived" : "not arrived: the stand-in is shown"}`);
      barRow = await barNow();
      folded = await band();
      const first = await evaluate(`(() => { const b = ${V}.shadowRoot.querySelector('.switch [data-lens="cell"]'); return b ? b.innerText.trim() : null; })()`);
      check(`on a 360 px phone, with ${font}, the bar stands on one row with the model system's first tab (${tab.split("|")[1]}), each of its buttons at least 44 px; the card's line names it, whole, apart from the rail's button`, first === tab.split("|")[1] && barRow.row && barRow.least >= 44 && !barRow.sideways && folded.folded && folded.words === gard.label && folded.whole && folded.apart, JSON.stringify([first, barRow, folded]));
    }
    await shot("model-phone-360-standin");
    await size(WIDTH, 800);
  } catch (error) {
    check("the run completed", false, error.stack || error.message);
  } finally {
    for (const line of pageLog) console.log(line);
    console.log(`note  the page's own font: ${await evaluate(`document.fonts.status === "loaded" && ["Inter", "Space Grotesk"].every((family) => [...document.fonts].some((face) => face.family.includes(family) && face.status === "loaded")) ? "arrived" : "not arrived: the stand-in was shown, whose words run longer"`).catch(() => "not known")}`);
    check("no script errors or blocked loads were reported by the page", pageLog.length === 0, `${pageLog.length} messages`);
    socket.close();
    { const closed = new Promise((resolve) => chrome.once("close", resolve)); chrome.kill(); await Promise.race([closed, new Promise((resolve) => setTimeout(resolve, 4000))]); if (chrome.exitCode === null && chrome.signalCode === null) chrome.kill("SIGKILL"); await Promise.race([closed, new Promise((resolve) => setTimeout(resolve, 2000))]); }
    server.close();
    release();
  }
  const failed = results.filter((ok) => !ok).length;
  console.log(`${results.length - failed} of ${results.length} checks passed`);
  process.exit(failed ? 1 : 0);
}

try {
  await open("lens=cell");
  let s = await state();
  check("the page opens on the species whose file says default", s.species === "planarian" && s.attribute === "planarian" && /planarian\*/.test(s.inBar + s.inCard), JSON.stringify([s.species, s.inBar, s.inCard]));
  check(`the switch stands in the ${EXPECT} at ${WIDTH} px, and the List button is whole`, (EXPECT === "bar" ? s.inBar !== "" && s.inCard === "" : EXPECT === "card" ? s.inBar === "" && s.inCard !== "" : (s.inBar !== "") !== (s.inCard !== "")) && s.listWhole === true, JSON.stringify([s.inBar, s.inCard, s.listWhole]));
  check("planarian: five levels on the rail, both size modes, every capability of a cell drawn", s.rail === "molecule cell* tissue organ organism" && s.modes === "schematic real" && s.absent === "" && s.railNote === null, JSON.stringify([s.rail, s.modes, s.absent, s.railNote]));
  check("the bar stays on one line", s.barRows === 1, String(s.barRows));
  const planarian = s;

  // The switch is a dropdown: one pill that names the species in view, and a list of the page's own.
  // The switch's entries (schema/ENTRIES.md): the species, and the model systems after them under their own headings.
  const scene = await evaluate(`[...${V}.model.raw.species.map((item) => ({ id: item.id, label: item.label, organism: item.organism, state: item.modelled.state, group: item.group || "", model: false })), ...(${V}.model.raw.models || []).map((item) => ({ id: item.id, label: item.label, organism: item.is, state: item.modelled.state, group: item.group || "", model: true }))]`);
  const syn3aWord = WORDS[scene.find((item) => item.id === "syn3a").state];
  let l = await list();
  check("the switch is one pill that names the species in view, with its list closed", s.pills === 1 && s.oldButtons === 0 && s.pillText === "Planarian" && s.pillLabel === "Species: Planarian" && l.open === false && l.expanded === "false", JSON.stringify([s.pills, s.oldButtons, s.pillText, s.pillLabel, l]));
  await openList();
  l = await list();
  check("a press opens the list under the pill, inside the window", l.open && l.expanded === "true" && l.inside && l.under, JSON.stringify([l.open, l.expanded, l.inside, l.under, l.box]));
  check("it is announced as a combobox that owns a listbox, with the species in view its selected and active row", l.roles === "combobox listbox species-list listbox species-list" && l.active === "species-option-planarian" && l.marked === "species-option-planarian" && l.rows.filter((row) => row.selected === "true").map((row) => row.id).join() === "planarian", JSON.stringify([l.roles, l.active, l.marked]));
  check("a row for every species and model system of the scene: its name, its organism in italics (a model system's line upright), and what Cells models of it", l.rows.length === scene.length && scene.every((item) => { const row = l.rows.find((r) => r.id === item.id); return row && row.name === item.label && row.organism === item.organism && row.italic === (item.model ? "normal" : "italic") && row.state === WORDS[item.state] && row.label === [item.label, item.organism, WORDS[item.state]].join(", "); }), JSON.stringify(l.rows.map((row) => [row.id, row.name, row.organism, row.italic, row.state])));
  const headings = [...new Set(scene.map((item) => item.group).filter(Boolean))];
  check("the rows stand under the headings the species' files give, each heading once", JSON.stringify(l.rows.map((row) => row.group)) === JSON.stringify([...headings.flatMap((group) => scene.filter((item) => item.group === group)), ...scene.filter((item) => !item.group)].map((item) => item.group)) && headings.length > 0, JSON.stringify([headings, l.rows.map((row) => `${row.id}:${row.group}`)]));
  // A row under the pointer becomes the active one, and nothing is chosen yet.
  const other = scene.find((item) => item.id !== "planarian");
  const hover = await rowAt(other.id);
  await mouse("mouseMoved", hover.x, hover.y, { button: "none", buttons: 0 });
  await sleep(200);
  l = await list();
  s = await state();
  check("the row under the pointer is the active one, and nothing is chosen yet", l.active === `species-option-${other.id}` && l.marked === `species-option-${other.id}` && s.species === "planarian", JSON.stringify([l.active, l.marked, s.species]));
  // A press beside the list, inside the window, closes it and changes nothing.
  const beside = l.box[1] + l.box[3] + 70 < 790 ? [Math.min(WIDTH - 12, l.box[0] + l.box[2] / 2), l.box[1] + l.box[3] + 70] : [Math.max(12, l.box[0] - 40), l.box[1] + l.box[3] / 2];
  await click(beside[0], beside[1]);
  l = await list();
  s = await state();
  check("a press beside the list closes it and does nothing else: no species chosen, no part picked", l.open === false && l.expanded === "false" && s.species === "planarian" && s.selected === null, JSON.stringify([l, s.species, s.selected]));
  // Escape closes the list and nothing else: what is selected stays selected. (On a narrow
  // window a selection's sheet covers the card that holds the switch, so nothing is selected there.)
  const kept = /\*/.test(s.inBar) ? "cap.membrane" : null;
  if (kept) {
    await evaluate(`${V}.select("${kept}")`);
    await sleep(200);
  }
  await openList();
  await key("Escape");
  l = await list();
  s = await state();
  check("Escape closes the list and nothing else: the selection stays, and the focus is back on the pill", l.open === false && s.selected === kept && (await focused()) === "pill", JSON.stringify([l.open, s.selected, await focused()]));
  // The page's chrome is drawn again whenever a view has something new to say, and the switch's button is then
  // another one: the focus stays on it (17 November 2026: under load a late drawing took the focus away).
  await evaluate(`${V}.renderChrome()`);
  await sleep(120);
  check("the focus stays on the pill when the page's chrome is drawn again", (await focused()) === "pill", JSON.stringify(await focused()));
  await evaluate(`${V}.select(null)`);
  await sleep(200);

  await pressSpecies("syn3a");
  s = await state();
  check("a click on Syn3A shows it everywhere the page keeps a species", s.species === "syn3a" && s.attribute === "syn3a" && s.atlasAttribute === "syn3a" && /syn3a\*/.test(s.inBar + s.inCard), JSON.stringify([s.species, s.attribute, s.inBar, s.inCard]));
  check("Syn3A: two levels on the rail, and its own sentence where the others would be", s.rail === "molecule cell*" && /single-celled/.test(s.railNote || ""), JSON.stringify([s.rail, s.railNote]));
  check("Syn3A: one size mode, and the card says why", s.modes === "schematic" && !/Sizes/.test(s.sizes) && /One size mode/.test(s.viewNote || ""), JSON.stringify([s.modes, s.sizes, s.viewNote]));
  check("Syn3A: what has no place in it is not drawn", s.absent.includes("cap.junctions") && s.absent.includes("cap.mitochondria") && !s.drawn.includes("cap.junctions") && !s.drawn.includes("cap.mitochondria") && !s.drawn.includes("cap.sheet"), `absent: ${s.absent}; drawn: ${s.drawn}`);
  check("Syn3A: the bar says what Cells models of it, in the ladder's words", s.state === syn3aWord && /, not modelled$/.test(s.state), String(s.state));
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
  check("pressing the statement opens all that is said of the species", s.selected === "species:syn3a" && s.panel && s.panel.title === "Syn3A" && s.panel.eyebrow === "Species" && s.panel.chips.includes(syn3aWord) && /Not in this organism/.test(s.panel.heads), JSON.stringify(s.panel));
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
  const all = await evaluate(`${V}.model.raw.species.map((item) => ({ id: item.id, label: item.label, state: item.modelled.state, levels: item.levels.map((level) => level.id), machines: (item.machines || []).length, absent: Object.entries(item.cell.capabilities || {}).filter(([, said]) => said.place === "absent").map(([id]) => id) }))`);
  const places = [];
  for (const item of all) {
    await pressSpecies(item.id);
    s = await state();
    places.push(`${item.id}:${s.inBar ? "bar" : s.inCard ? "card" : "none"}`);
    const stops = { molecules: "molecule", cell: "cell", tissue: "tissue", organ: "organ", organism: "organism" };
    const rail = s.rail.replace("*", "").split(" ");
    const drawnAbsent = item.absent.filter((id) => s.drawn.split(" ").includes(id));
    // A machine that can be looked at closer (schema/MACHINES.md) has a stop of its own, after the molecules.
    const wanted = item.levels.flatMap((id) => (id === "molecules" ? [stops[id], ...Array(item.machines).fill("machine")] : [stops[id]]));
    check(`${item.label}: the rail has the levels of its file${item.machines ? " and a stop for its machine" : ""}, and nothing it marks absent is drawn`, s.species === item.id && JSON.stringify(rail) === JSON.stringify(wanted) && drawnAbsent.length === 0 && s.listWhole === true, JSON.stringify([s.rail, item.levels, item.machines, drawnAbsent, s.listWhole]));
    const notIn = ["proposed", "planned", "designed"].includes(item.state);
    check(`${item.label}: the caveat under the picture ${notIn ? "says nothing of it is in the engine" : "is the map's own"}`, notIn ? new RegExp(`^${item.label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}: nothing of it is in the engine`).test(s.caveat || "") : !/nothing of it is in the engine/.test(s.caveat || "") && Boolean(s.caveat), String(s.caveat));
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

  // The keyboard: open, move, choose, close, and a letter to go to a species by its name.
  const order = (await evaluate(`${V}.speciesShown.rows.map((row) => row.id)`));
  const here = order.indexOf("planarian");
  await evaluate(`[...${V}.shadowRoot.querySelectorAll(".species-pick")].find((b) => b.offsetParent).focus()`);
  await key("ArrowDown");
  let k = await list();
  check("from the keyboard: the down arrow opens the list on the species in view", k.open && k.active === "species-option-planarian" && (await focused()) === "pill", JSON.stringify([k.open, k.active, await focused()]));
  await key("ArrowDown");
  k = await list();
  check("the arrows move the active row, which the pill names to a screen reader", k.active === `species-option-${order[here + 1]}` && k.marked === k.active, JSON.stringify([k.active, k.marked]));
  await key("End");
  k = await list();
  const last = k.active;
  await key("Home");
  k = await list();
  check("Home and End go to the first and the last row", last === `species-option-${order.at(-1)}` && k.active === `species-option-${order[0]}`, JSON.stringify([last, k.active]));
  await key("s");
  k = await list();
  const byS = order.find((id) => /^s/i.test(scene.find((item) => item.id === id).label));
  check("a letter goes to the species whose name begins with it", k.active === `species-option-${byS}`, JSON.stringify([k.active, byS]));
  await key("Enter");
  s = await state();
  k = await list();
  check("Enter chooses the active row: the species changes, the list closes, and the focus stays on the pill", s.species === byS && k.open === false && (await focused()) === "pill" && s.pillLabel === `Species: ${scene.find((item) => item.id === byS).label}`, JSON.stringify([s.species, k.open, await focused(), s.pillLabel]));
  await key("h");
  k = await list();
  check("a letter typed on the closed pill opens the list at that species", k.open && k.active === "species-option-human", JSON.stringify([k.open, k.active]));
  await key(" ");
  s = await state();
  check("the space bar chooses as Enter does", s.species === "human" && (await list()).open === false, JSON.stringify([s.species]));
  await key("Enter");
  await key("Tab");
  s = await state();
  check("Tab closes the list and chooses nothing", (await list()).open === false && s.species === "human", JSON.stringify([s.species]));

  // A narrow window: the switch stands in the card.
  await size(400, 800);
  await open("lens=cell");
  s = await state();
  check("on a phone the switch stands in the card", s.inBar === "" && /planarian\*/.test(s.inCard), JSON.stringify([s.inBar, s.inCard]));
  const fits = await evaluate(`(() => { const root = ${V}.shadowRoot, card = root.querySelector(".view").getBoundingClientRect(); return [...root.querySelectorAll(".view .species-pick")].every((b) => { const r = b.getBoundingClientRect(); return r.left >= card.left - 0.5 && r.right <= card.right + 0.5; }); })()`);
  // A touch on the pill opens the list; a touch on a row chooses it.
  const touch = async (x, y) => {
    await page("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y }] });
    await page("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    await sleep(350);
  };
  const where = await pill();
  await touch(where.x, where.y);
  await settled(true);
  const phone = await list();
  check("on a phone a touch opens the list, within the window, every row whole", phone.open && phone.inside && phone.under && phone.rows.length === scene.length, JSON.stringify([phone.open, phone.inside, phone.under, phone.box]));
  const row = await rowAt("syn3a");
  await touch(row.x, row.y);
  await settled(false);
  s = await state();
  check("and a touch on a row chooses it, inside the card", s.species === "syn3a" && s.rail === "molecule cell*" && fits && (await list()).open === false, JSON.stringify([s.species, s.rail, fits]));

  // A structure's panel on a phone (the human's nucleus): its door into the Protein atlas, whose words are long, is a
  // button of its own, at least 44 px tall and inside the panel, its words whole; a touch on it opens the atlas.
  await open("lens=cell&species=human&select=cap.nucleus");
  const doorAt = () =>
    evaluate(`(() => {
      const root = ${V}.shadowRoot, el = root.querySelector("cells-panel .panel-door button"), body = root.querySelector("cells-panel .panel-body");
      if (!el || !body) return null;
      el.scrollIntoView({ block: "nearest" });
      const r = el.getBoundingClientRect(), p = body.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2, box: [r.left, r.top, r.right, r.bottom].map(Math.round), panel: [p.left, p.top, p.right, p.bottom].map(Math.round), whole: el.scrollWidth <= el.clientWidth + 1, words: el.textContent, top: root.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2) === el || el.contains(root.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2)) };
    })()`);
  let door = null;
  for (let tries = 0; tries < 240 && !door; tries++) {
    door = await doorAt();
    if (!door) await sleep(250);
  }
  check("on a phone a structure's door is a button at least 44 px tall inside the panel, its long words whole", Boolean(door) && door.box[3] - door.box[1] >= 44 && door.box[0] >= door.panel[0] && door.box[2] <= door.panel[2] && door.whole && door.top && /Protein atlas/.test(door.words), JSON.stringify(door));
  if (door) {
    await touch(door.x, door.y);
    let there = null;
    for (let tries = 0; tries < 480; tries++) {
      there = await evaluate(`({ lens: ${V}.state.lens, mode: ${V}.current.mode ?? null })`);
      if (there.lens === "proteins" && there.mode === "own") break;
      await sleep(250);
    }
    check("and a touch on it opens the Protein atlas on the species' own proteins", there?.lens === "proteins" && there.mode === "own", JSON.stringify(there));
  }
} catch (error) {
  check("the run completed", false, error.stack || error.message);
} finally {
  for (const line of pageLog) console.log(line);
  // Whether the page's own font had arrived by the end: with the stand-in, words run longer and cards stand
  // taller, and a miss is read against that.
  console.log(`note  the page's own font: ${await evaluate(`document.fonts.status === "loaded" && ["Inter", "Space Grotesk"].every((family) => [...document.fonts].some((face) => face.family.includes(family) && face.status === "loaded")) ? "arrived" : "not arrived: the stand-in was shown, whose words run longer"`).catch(() => "not known")}`);
  check("no script errors or blocked loads were reported by the page", pageLog.length === 0, `${pageLog.length} messages`);
  socket.close();
  { const closed = new Promise((resolve) => chrome.once("close", resolve)); chrome.kill(); await Promise.race([closed, new Promise((resolve) => setTimeout(resolve, 4000))]); if (chrome.exitCode === null && chrome.signalCode === null) chrome.kill("SIGKILL"); await Promise.race([closed, new Promise((resolve) => setTimeout(resolve, 2000))]); }
  server.close();
  release();
}
const failed = results.filter((ok) => !ok).length;
console.log(`${results.length - failed} of ${results.length} checks passed`);
process.exit(failed ? 1 : 0);
