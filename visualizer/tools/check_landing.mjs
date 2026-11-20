#!/usr/bin/env node
// Checks the Experiments tab's landing (src/ui/landing.js) in a real browser, with real presses and keys through the
// DevTools protocol, on the page as the local server builds it with the runs folder at out/runs. What it expects is read
// from data/replays/cards.json at run time, through the landing's own model (src/replay/landing.js: its bands, which
// stand open first, each control's words): no card, band, count or level is named here, so the cards may change.
//
//   wide     1440 by 900      720      1280 by 720      phone    400 by 860      narrow   360 by 780
//   retry    1280 by 720: the cards' file held back (the landing says that it is coming), then refused (it says that it
//            could not be fetched, offers to try again, and the rest of the page works), then given on "Try again".
//
// Each size case, in the light theme and in the dark one (THEMES, "light,dark" unless set): the site's first entry fetches
// nothing of the landing. As the landing opens (nothing kept from an earlier visit) only the first band's cards stand;
// each later band shows its head (its label, its words), its count and its control (a button with aria-expanded and
// aria-controls, in the file's words), and nothing of it is drawn or fetched; the landing fetches the cards once and only
// the stills near the screen, and no run and no model; the not-run line and the cards' revisions stand at the foot, under
// the folded bands. A real press on each control shows its cards under its head (their stills fetched only near the
// screen), a second press folds them and a third shows them again (nothing fetched twice). Then, with every band open:
// every card of the file stands with its title and its standing's first words, first words (`standing.first`) before
// anything else of its standing; nothing scrolls sideways; every card's words and every control read against their
// ground (contrast 4.5 or more); on a phone every control is 44 px or more; no console error; the 3D stage draws no frame
// while the landing shows. In the first theme too: with less motion asked for nothing on the landing moves; the keyboard
// reaches the first band's cards and then each control, and no card of a folded band, and with the bands open every card
// in order, each with a visible focus; the bands a visitor opened are open again on the next visit, and where storage is
// refused the first band alone; each replay card opens its view (the one the card's rule names), the way back stands in
// one place in every view, clear of the view's other controls, and returns to the landing with the same bands open, where
// it was scrolled, with the keyboard on the card it left; a card asked for by its detail's address, from the List, and by
// the way back opens its band first, the other bands staying folded; the List lists every card, folded or not; a
// standing's detail opens by a press, with its own address, and by that address; the rows' card lists its rows; the
// not-run line opens the view it names. Last, at each size, About and the first-visit line (src/ui/about.js), on a first
// visit as every run of a check is: where the line stands (the site's first view, the landing) it covers nothing the
// page put over the picture and no name the view shows, else it waits out of sight (always on a phone); the bar's About
// button opens About in the panel's place (its heading, the focus, every view a door, the source code in a new tab),
// Escape gives the view back and the focus to the button, the name in the bar's corner and the panel's close button
// work, a door opens its view; the line once closed stays closed, `#about` opens About, where storage is refused the
// line shows again, and with less motion it does not move.
//
// Every wait is on the page's own state (what it shows, what it fetched, where it scrolled), never a fixed time after a
// load or a press. The one fixed wait is before anything is judged: a fresh browser's first page is loaded, given six
// seconds (its first graphics context is lost and made again about five seconds in) and never judged or pictured.
//
//   node tools/check_landing.mjs [OUT_DIR]
//
// Set by the environment: CASE (wide, 720, phone, narrow, retry), WIDTH, HEIGHT (by the case unless set), THEMES, NAME
// (the pictures' prefix). Chrome is what CHROME names (tools/chrome_gpu.sh for the graphics card), in a place taken
// through tools/lib/browser_lock.mjs.

import { spawn } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { acquireBrowser } from "./lib/browser_lock.mjs";
import { createServer } from "./serve.mjs";
import { DEFAULT_RUNS } from "./lib/build_page.mjs";
import { opensOf, addressOf, standingWords, landingOf, controlOf, bandHolding, CARD } from "../src/replay/landing.js";
import { Catalogue } from "../src/replay/catalogue.js";
import { STILL_MARGIN, LIST_ROOM } from "../src/ui/landing.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const CASE = process.env.CASE || "wide";
const CASES = { wide: [1440, 900], 720: [1280, 720], phone: [400, 860], narrow: [360, 780], retry: [1280, 720] };
if (!CASES[CASE]) throw new Error(`no case ${CASE}: ${Object.keys(CASES).join(", ")}`);
const WIDTH = Number(process.env.WIDTH || CASES[CASE][0]), HEIGHT = Number(process.env.HEIGHT || CASES[CASE][1]);
const THEMES = (process.env.THEMES || (CASE === "retry" ? "light" : "light,dark")).split(",").filter(Boolean);
const NAME = process.env.NAME || `landing-${CASE}`;
const OUT = path.resolve(process.argv[2] || path.join(ROOT, "out", "check-landing"));
const PHONE = WIDTH < 760;
mkdirSync(OUT, { recursive: true });
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const results = [];
const check = (name, ok, detail = "") => {
  results.push(Boolean(ok));
  console.log(`${ok ? "pass" : "FAIL"}  ${name}${detail ? `  (${String(detail).slice(0, 400)})` : ""}`);
};
const note = (text) => console.log(`note  ${text}`);
const cards = JSON.parse(readFileSync(path.join(ROOT, "data", "replays", "cards.json"), "utf8"));
const ABOUT_WORDS = JSON.parse(readFileSync(path.join(ROOT, "data", "site", "about.json"), "utf8")); // the About words (src/ui/about.js)
// The landing as its model reads the file: the first band stands open, every later band folds behind its control.
const landing = landingOf(cards);
const FIRST = landing.bands[0];
const LATER = landing.bands.slice(1);
const ALL = landing.bands.flatMap((band) => band.cards.map((card) => card.id));
const stillOfCard = new Map(cards.cards.flatMap((card) => (card.replay?.still ? [card.replay.still.light, card.replay.still.dark].filter(Boolean).map((file) => [`/${file}`, card.id]) : [])));
// The first words of a card's standing on its face: its `first`, else its words as the face starts them (after the card's
// own question, where they open with it: the face asks it once, above).
const firstWords = (card) => String(card.standing?.first || standingWords(card).face || "").slice(0, 32);

// ---------------------------------------------------------------- the page, served as the local preview serves it
const asked = [];
const server = createServer({ offline: true, runs: DEFAULT_RUNS, log: () => {} });
server.on("request", (request) => asked.push(new URL(request.url, "http://localhost").pathname));
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}/`;
const beside = (from = 0) => asked.slice(from).filter((one) => one !== "/" && !one.startsWith("/vendor/") && one !== "/__log");
const stillsAsked = (from = 0) => beside(from).filter((one) => one.startsWith("/stills/"));

const release = await acquireBrowser({ wait: 60 * 60 * 1000 });
const chrome = spawn(process.env.CHROME || "google-chrome", ["--headless=new", `--user-data-dir=${release.profile}`, "--disable-breakpad", "--no-first-run", "--no-sandbox", "--mute-audio", "--hide-scrollbars", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", `--window-size=${WIDTH},${HEIGHT}`, "--remote-debugging-port=0", "about:blank"], { stdio: ["ignore", "ignore", "pipe"] });
let failed = null;
try {
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
  await new Promise((resolve, reject) => ((socket.onopen = resolve), (socket.onerror = reject)));
  let nextId = 1;
  const waiting = new Map(), errors = [];
  let hold = null; // what to do with a request for the cards' file: null (let it through), "wait" or "refuse"
  const held = [];
  const send = (method, params = {}, sessionId) =>
    new Promise((resolve, reject) => {
      const id = nextId++;
      waiting.set(id, { resolve, reject });
      socket.send(JSON.stringify({ id, method, params, sessionId }));
    });
  let session = null;
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.method === "Runtime.exceptionThrown") errors.push(String(message.params.exceptionDetails?.exception?.description || message.params.exceptionDetails?.text).slice(0, 300));
    if (message.method === "Runtime.consoleAPICalled" && message.params.type === "error") errors.push(message.params.args.map((arg) => arg.value ?? arg.description).join(" ").slice(0, 300));
    if (message.method === "Log.entryAdded" && message.params.entry.level === "error" && !/favicon/.test(message.params.entry.url || "")) errors.push(`${message.params.entry.text} ${message.params.entry.url || ""}`.slice(0, 300));
    if (message.method === "Fetch.requestPaused") {
      const { requestId, request } = message.params;
      const cardsFile = new URL(request.url).pathname === "/cards.json";
      if (cardsFile && hold === "refuse") send("Fetch.fulfillRequest", { requestId, responseCode: 503, responseHeaders: [{ name: "content-type", value: "text/plain" }], body: Buffer.from("held back by the check").toString("base64") }, session);
      else if (cardsFile && hold === "wait") held.push(requestId);
      else send("Fetch.continueRequest", { requestId }, session);
      return;
    }
    const entry = waiting.get(message.id);
    if (!entry) return;
    waiting.delete(message.id);
    if (message.error) entry.reject(new Error(message.error.message));
    else entry.resolve(message.result);
  };
  const { targetId } = await send("Target.createTarget", { url: "about:blank" });
  ({ sessionId: session } = await send("Target.attachToTarget", { targetId, flatten: true }));
  const page = (method, params) => send(method, params, session);
  await page("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: HEIGHT, deviceScaleFactor: 1, mobile: PHONE });
  if (PHONE) await page("Emulation.setTouchEmulationEnabled", { enabled: true, maxTouchPoints: 1 });
  await page("Page.enable");
  await page("Runtime.enable");
  await page("Log.enable");
  await page("Network.enable");
  await page("Network.setCacheDisabled", { cacheDisabled: true });
  await page("Fetch.enable", { patterns: [{ urlPattern: "*cards.json*" }] });
  const evaluate = async (expression) => {
    const reply = await page("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (reply.exceptionDetails) throw new Error(reply.exceptionDetails.exception?.description || reply.exceptionDetails.text);
    return reply.result.value;
  };
  const V = "document.querySelector('cells-viewer')";
  const R = `${V}.shadowRoot`;
  const until = async (expression, ms = 30000) => {
    const start = Date.now();
    while (Date.now() - start < ms) {
      if (await evaluate(expression).catch(() => false)) return true;
      await sleep(200);
    }
    return false;
  };
  /** Until something this check holds (not the page) is so: a request held back, say. */
  const untilHere = async (holds, ms = 15000) => {
    const start = Date.now();
    while (Date.now() - start < ms) {
      if (holds()) return true;
      await sleep(100);
    }
    return false;
  };
  /** What an expression reads once it reads the same twice running (the page has stopped moving it); its last reading else. */
  const stable = async (expression, ms = 20000) => {
    const start = Date.now();
    let last = await evaluate(expression).catch(() => null);
    while (Date.now() - start < ms) {
      await sleep(250);
      const now = await evaluate(expression).catch(() => null);
      if (now !== null && JSON.stringify(now) === JSON.stringify(last)) return now;
      last = now;
    }
    return last;
  };
  /** Until the page has asked the server for nothing more for `ms` (its fetches have ended). */
  const quiet = async (ms = 1500, most = 30000) => {
    const start = Date.now();
    let count = asked.length, since = Date.now();
    while (Date.now() - start < most) {
      await sleep(150);
      if (asked.length !== count) (count = asked.length), (since = Date.now());
      else if (Date.now() - since >= ms) return true;
    }
    return false;
  };
  const navigate = async (query, theme = null) => {
    const search = new URLSearchParams(query || "");
    if (theme) search.set("theme", theme);
    await page("Page.navigate", { url: `${base}${search.size ? `?${search}` : ""}` });
    await until(`Boolean(${V}?.model)`, 60000);
  };
  /** The browser's own storage for the page emptied, by the browser (not by the page, whose storage may be made to refuse). */
  const forget = () => page("Storage.clearDataForOrigin", { origin: base.replace(/\/$/, ""), storageTypes: "local_storage" });
  /** A visit with nothing kept from an earlier one. */
  const fresh = async (query, theme = null) => {
    await forget();
    await navigate(query, theme);
  };
  const picture = async (name) => {
    const shot = await page("Page.captureScreenshot", { format: "png" });
    writeFileSync(path.join(OUT, `${NAME}-${name}.png`), Buffer.from(shot.data, "base64"));
  };
  const mouse = (type, x, y) => page("Input.dispatchMouseEvent", { type, x, y, button: "left", buttons: type === "mouseReleased" ? 0 : 1, clickCount: 1 });
  /** A real press at the middle of what `expression` finds. A tab is brought into sight in its row first, as a visitor scrolls the row of a phone to it. */
  const press = async (expression) => {
    const at = await evaluate(`(() => { const el = ${expression}; if (!el) return null; if (el.closest?.(".switch")) el.scrollIntoView({ block: "nearest", inline: "nearest" }); const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
    if (!at) return false;
    if (PHONE) {
      await page("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: at.x, y: at.y }] });
      await page("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    } else {
      await mouse("mouseMoved", at.x, at.y);
      await mouse("mousePressed", at.x, at.y);
      await mouse("mouseReleased", at.x, at.y);
    }
    return true;
  };
  const key = async (name, code = name, keyCode = 9) => {
    await page("Input.dispatchKeyEvent", { type: "keyDown", key: name, code, windowsVirtualKeyCode: keyCode });
    await page("Input.dispatchKeyEvent", { type: "keyUp", key: name, code, windowsVirtualKeyCode: keyCode });
  };
  /** On a phone, whether the head of what `element` finds stands above the panel's sheet (elsewhere the panel stands beside the cards). */
  const CLEAR_OF_SHEET = (element) => `(() => { const el = ${element}, panel = ${R}.querySelector("cells-panel"); if (!${PHONE} || !panel || panel.hidden) return true; return el.getBoundingClientRect().top + 48 <= panel.getBoundingClientRect().top; })()`;
  const IN_SIGHT = (element) => `(() => { const el = ${element}; if (!el || !el.checkVisibility()) return false; const r = el.getBoundingClientRect(), b = ${V}.landingView.box.getBoundingClientRect(); return r.top >= b.top - 1 && r.bottom <= b.bottom + 1 && r.height > 0; })()`;
  /** Scrolls the landing so that what `element` finds stands in the middle, and waits until it stands in sight. */
  const bring = async (element) => {
    await evaluate(`(() => { const el = ${element}; el?.scrollIntoView({ block: "center" }); return Boolean(el); })()`);
    return until(`(() => { const el = ${element}; if (!el || !el.checkVisibility()) return false; const r = el.getBoundingClientRect(), b = ${V}.landingView.box.getBoundingClientRect(); return r.bottom > b.top && r.top < b.bottom; })()`, 10000);
  };
  const cardEl = (id) => `${R}.querySelector('[data-card=${JSON.stringify(id)}]')`;
  const controlEl = (id) => `${R}.querySelector('[data-band=${JSON.stringify(id)}] .landing-fold')`;
  const shownCards = () => evaluate(`[...${R}.querySelectorAll(".landing-card")].filter((el) => el.checkVisibility()).map((el) => el.dataset.card)`);
  // Every band as it stands: its head, its control, and which of its cards are made and which are drawn.
  const bandsNow = () =>
    evaluate(`[...${R}.querySelectorAll(".landing-band")].map((section) => {
      const button = section.querySelector(".landing-band-head > .landing-fold"), grid = section.querySelector(":scope > .landing-grid");
      const target = button ? ${R}.getElementById(button.getAttribute("aria-controls") || "") : null;
      const head = section.querySelector(".landing-band-head").getBoundingClientRect();
      const first = [...grid.querySelectorAll(".landing-card")].find((card) => card.checkVisibility());
      return {
        id: section.dataset.band,
        label: section.querySelector(".landing-band-title")?.textContent || "",
        says: section.querySelector(".landing-band-says")?.textContent || null,
        control: button ? { tag: button.tagName, type: button.type, says: button.querySelector(".landing-fold-words")?.textContent || "", count: button.querySelector(".landing-fold-count")?.textContent || "", expanded: button.getAttribute("aria-expanded"), controls: target === grid, inHead: button.parentElement === section.querySelector(".landing-band-head") } : null,
        hidden: grid.hidden, display: getComputedStyle(grid).display, made: grid.querySelectorAll(".landing-card").length,
        shown: [...grid.querySelectorAll(".landing-card")].filter((card) => card.checkVisibility()).map((card) => card.dataset.card),
        under: first ? first.getBoundingClientRect().top >= head.bottom - 0.5 : null,
      };
    })`);
  /** Whether the bands stand as `open` says (a set of band ids): open bands with all their cards drawn, the rest folded. */
  const standAs = (state, open) =>
    state.length === landing.bands.length &&
    state.every((band, n) => {
      const model = landing.bands[n];
      if (band.id !== model.id) return false;
      const ids = model.cards.map((card) => card.id);
      if (n === 0) return band.control === null && !band.hidden && JSON.stringify(band.shown) === JSON.stringify(ids);
      const control = controlOf(model, open.has(model.id));
      const words = band.control && band.control.says === control.says && band.control.count === String(control.count) && band.control.controls && band.control.tag === "BUTTON" && band.control.type === "button" && band.control.inHead;
      return words && (open.has(model.id) ? band.control.expanded === "true" && !band.hidden && JSON.stringify(band.shown) === JSON.stringify(ids) : band.control.expanded === "false" && band.hidden && band.display === "none" && band.shown.length === 0);
    });
  const describeBands = (state) => JSON.stringify(state.map((band) => [band.id, band.control?.expanded ?? "first", band.control?.says ?? "", band.control?.count ?? "", band.hidden, band.made, band.shown.length]));
  const FIRST_DRAWN = `${V}?.state?.landing && ${R}.querySelectorAll(".landing-band").length === ${landing.bands.length} && ${JSON.stringify(FIRST.cards.map((card) => card.id))}.every((id) => ${R}.querySelector('[data-card="' + id + '"]')?.checkVisibility())`;
  // Every still of an open band that is near the screen has been asked for and has come (or failed); none waits.
  const STILLS_SETTLED = `(() => { const b = ${V}.landingView.box.getBoundingClientRect(); return [...${R}.querySelectorAll(".landing-grid:not([hidden]) .landing-still")].every((img) => { const r = img.getBoundingClientRect(); const near = r.top < b.bottom + ${STILL_MARGIN} && r.bottom > b.top - ${STILL_MARGIN}; return !near || (img.dataset.shown && img.complete); }); })()`;
  const stillsNow = () => evaluate(`(() => { const b = ${V}.landingView.box.getBoundingClientRect(); return [...${R}.querySelectorAll(".landing-still")].map((img) => { const r = img.getBoundingClientRect(); return { card: img.closest(".landing-card").dataset.card, file: img.getAttribute("src") || "", shown: Boolean(img.dataset.shown), drawn: img.checkVisibility(), near: img.checkVisibility() && r.top < b.bottom + ${STILL_MARGIN} + 4 && r.bottom > b.top - ${STILL_MARGIN} - 4, width: img.width, height: img.height }; }); })()`);
  const contrastOf = (selector) =>
    evaluate(`(() => {
      const rgb = (text) => { const m = text.match(/rgba?\\(([^)]+)\\)/); if (!m) return null; const [r, g, b, a = 1] = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return { r, g, b, a }; };
      const lum = ({ r, g, b }) => { const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
      const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
      // The ground an element's words stand on: the first ground behind it that is not see-through.
      const ground = (el) => { for (let at = el; at; at = at.parentElement || at.getRootNode()?.host) { const c = rgb(getComputedStyle(at).backgroundColor); if (c && c.a > 0.5) return c; } return null; };
      const worst = [];
      for (const el of ${R}.querySelectorAll(${JSON.stringify(selector)})) {
        if (!el.checkVisibility()) continue;
        const ink = rgb(getComputedStyle(el).color), under = ground(el);
        if (!under || !ink) { worst.push([el.closest("[data-card]")?.dataset.card || el.closest("[data-band]")?.dataset.band, el.className, "unread"]); continue; }
        const value = ratio(ink, under);
        if (value < 4.5) worst.push([el.closest("[data-card]")?.dataset.card || el.closest("[data-band]")?.dataset.band, el.className, Number(value.toFixed(2))]);
      }
      return worst;
    })()`);
  const CARD_WORDS = ".landing-card .landing-part, .landing-card .landing-title, .landing-card .landing-asks, .landing-card .landing-first, .landing-card .landing-says, .landing-card .landing-level, .landing-card .landing-answer, .landing-card .landing-verdict, .landing-card .landing-scope, .landing-card .landing-runs, .landing-card .landing-more";
  const HEAD_WORDS = ".landing-band-title, .landing-band-says, .landing-fold-words, .landing-fold-count, .landing-not-run, .landing-not-run .link-button, .landing-built";
  const THUMB = ".landing-open, .landing-more, .landing-fold, .landing-not-run .link-button, .switch button";
  const smallControls = () => evaluate(`[...${R}.querySelectorAll(${JSON.stringify(THUMB)})].filter((el) => el.checkVisibility()).map((el) => [el.className || el.textContent, Math.round(el.getBoundingClientRect().height), Math.round(el.getBoundingClientRect().width)]).filter(([, h, w]) => h < 44 || w < 44)`);
  const sidewaysNow = () => evaluate(`(() => { const box = ${V}.landingView.box; const rects = [...${R}.querySelectorAll(".landing-card, .landing-band-title, .landing-fold, .landing-not-run")].filter((el) => el.checkVisibility()).map((el) => el.getBoundingClientRect()); return { page: document.documentElement.scrollWidth - innerWidth, box: box.scrollWidth - box.clientWidth, out: rects.filter((r) => r.left < -0.5 || r.right > innerWidth + 0.5).length }; })()`);
  /** A real press on a band's control, the control brought into sight first; resolves when the band stands as asked. */
  const pressControl = async (id, open) => {
    await bring(controlEl(id));
    await press(controlEl(id));
    const count = landing.bands.find((band) => band.id === id).cards.length;
    const stands = await until(`(() => { const b = ${controlEl(id)}, grid = b && ${R}.getElementById(b.getAttribute("aria-controls")); if (!grid) return false; return b.getAttribute("aria-expanded") === ${JSON.stringify(String(open))} && (${open} ? [...grid.querySelectorAll(".landing-card")].filter((el) => el.checkVisibility()).length === ${count} : !grid.checkVisibility()); })()`, 10000);
    // And whatever the press set turning (the control's chevron) has come to rest.
    await until(`${V}.landingView.box.getAnimations({ subtree: true }).every((one) => one.playState !== "running")`, 5000);
    return stands;
  };
  /** A real press on the List's row of a card (by its title), the row brought into sight in the List first. */
  const pressRow = async (title) => {
    const row = `[...${R}.querySelectorAll("cells-index .index-row")].find((row) => row.querySelector(".index-name")?.textContent === ${JSON.stringify(title)})`;
    await evaluate(`(() => { const el = ${row}; el?.scrollIntoView({ block: "center" }); return Boolean(el); })()`);
    await until(`(() => { const el = ${row}; if (!el || !el.checkVisibility()) return false; const r = el.getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight && document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2) === ${V} && ${R}.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2)?.closest(".index-row") === el; })()`, 10000);
    return press(row);
  };
  /** The keyboard's walk from the List's button: every place on the landing it stops at, in order (a card once). */
  const walk = async (steps) => {
    await evaluate(`${V}.landingView.box.scrollTop = 0`);
    await evaluate(`${V}.indexButton.focus()`);
    const visits = [], unseen = [];
    let entered = false;
    for (let step = 0; step < steps; step++) {
      await key("Tab");
      const at = await evaluate(`(() => { const el = ${R}.activeElement; if (!el) return { out: true }; const card = el.closest?.(".landing-card"), fold = el.classList?.contains("landing-fold") ? el.closest(".landing-band") : null, line = el.closest?.(".landing-not-run"); if (!card && !fold && !line) return { out: true, what: el.tagName + "." + el.className }; const target = el.classList.contains("landing-open") ? card : el; const style = getComputedStyle(target); const r = el.getBoundingClientRect(), box = ${V}.landingView.box.getBoundingClientRect(); return { id: card ? card.dataset.card : fold ? "band:" + fold.dataset.band : "not-run", outline: style.outlineStyle !== "none" && parseFloat(style.outlineWidth) >= 2, inView: r.top >= box.top - 1 && r.bottom <= box.bottom + 1 }; })()`);
      if (at.out) {
        if (entered) break;
        continue;
      }
      entered = true;
      if (visits.at(-1) !== at.id) visits.push(at.id);
      if (at.id !== "not-run" && (!at.outline || !at.inView)) unseen.push(at.id);
    }
    return { visits, unseen };
  };
  const errorsNow = () => errors.filter((line) => !/held back by the check/.test(line));

  // A fresh browser's first page is neither judged nor pictured: its first graphics context is lost and made again
  // about five seconds after it starts (the common rule for every browser run here).
  await navigate("lens=laws");
  await sleep(6000);

  if (CASE === "retry") {
    // While the cards come, the landing says so; refused, it says that, offers to try again, and the rest of the page works.
    hold = "wait";
    await fresh("lens=experiments");
    // The cards' file asked for and held back here, and the landing's status standing.
    const asking = await untilHere(() => held.length > 0, 30000);
    await until(`${R}.querySelector(".landing-status") && !${R}.querySelector(".landing-status").hidden && /Fetching/.test(${R}.querySelector(".landing-status").textContent)`, 15000);
    const coming = await evaluate(`(() => { const s = ${R}.querySelector(".landing-status"); return { text: s?.textContent || "", hidden: s?.hidden, cards: ${R}.querySelectorAll(".landing-card").length }; })()`);
    check("while the cards' file is on its way, the landing says so", asking && /Fetching/.test(coming.text) && !coming.hidden && coming.cards === 0, JSON.stringify(coming));
    await picture("coming");
    hold = "refuse";
    for (const requestId of held.splice(0)) await page("Fetch.fulfillRequest", { requestId, responseCode: 503, responseHeaders: [{ name: "content-type", value: "text/plain" }], body: Buffer.from("held back by the check").toString("base64") });
    await until(`Boolean(${R}.querySelector(".landing-again"))`, 15000);
    const refused = await evaluate(`(() => { const s = ${R}.querySelector(".landing-status"); return { text: s?.textContent || "", again: Boolean(s?.querySelector(".landing-again")), role: s?.querySelector("[role=alert]") ? "alert" : null }; })()`);
    check("refused, the landing says that the cards could not be fetched and offers to try again", /could not be fetched/.test(refused.text) && refused.again && refused.role === "alert", JSON.stringify(refused));
    await picture("refused");
    await press(`${R}.querySelector('[data-lens="cell"]')`);
    const scope = await until(`${V}.state.lens === "cell" && Boolean(${V}.current)`, 20000);
    check("the rest of the page works: Scope opens from the bar", scope);
    await press(`${R}.querySelector('[data-lens="experiments"]')`);
    await until(`${V}.state.landing && !${V}.landingView.box.hidden`, 10000);
    // Shown again, the landing asks for the cards by itself and is refused once more: "Try again" is pressed when that
    // second answer has come and the button stands again (pressed while it was on its way, the press met no button).
    await until(`Boolean(${R}.querySelector(".landing-again")) && !${V}.landingView.fetching`, 15000);
    hold = null;
    await press(`${R}.querySelector(".landing-again")`);
    const back = await until(FIRST_DRAWN, 20000);
    const state = await bandsNow();
    check(`on "Try again" the cards come: the first band's ${FIRST.cards.length} cards, and each later band folded behind its control`, back && standAs(state, new Set()), describeBands(state));
    check("no console error but the refused file's own line", errors.every((line) => /503|cards\.json/.test(line)), errors.join(" | "));
  } else {
    // ------------------------------------------------------------ the site's first entry
    let from = asked.length;
    await fresh("");
    await until(`Boolean(${V}.current)`, 30000);
    await quiet(1500);
    const first = beside(from);
    check("the site's first entry is Scope, and fetches nothing of the landing (cards.json, stills/)", (await evaluate(`${V}.state.lens`)) === "cell" && !first.some((one) => one === "/cards.json" || one.startsWith("/stills/")), first.join(", "));

    for (const [k, theme] of THEMES.entries()) {
      // ------------------------------------------------------------ as the landing opens: the first band, and the heads of the rest
      // The visit before this one is left first, and its fetches have ended: a still it asked for late would otherwise be
      // counted with this visit's (seen on 19 November 2026 with four browsers at work: the light stills of the visit
      // before reached the server after this window had opened, ahead of this visit's own cards).
      await page("Page.navigate", { url: "about:blank" });
      await quiet(1000);
      errors.length = 0;
      from = asked.length;
      await fresh("lens=experiments", theme);
      const drawn = await until(FIRST_DRAWN, 30000);
      await until(STILLS_SETTLED, 20000);
      await quiet(1000);
      const opening = await bandsNow();
      check(`${theme}: as the landing opens only the first band's ${FIRST.cards.length} cards stand, and each later band shows its head, its count and its control, folded, none of its cards made`, drawn && standAs(opening, new Set()) && opening.slice(1).every((band) => band.made === 0) && (await shownCards()).length === FIRST.cards.length, describeBands(opening));
      check(`${theme}: each band's head says its label and its words, as the file gives them`, opening.every((band, n) => band.label === landing.bands[n].label && band.says === landing.bands[n].says), JSON.stringify(opening.map((band) => [band.label, band.says?.slice(0, 30)])));
      const got = beside(from);
      check(`${theme}: it fetched the cards once, and no run and no model`, got.filter((one) => one === "/cards.json").length === 1 && !got.some((one) => one.startsWith("/runs/") || one.startsWith("/models/")), got.join(", "));
      // The stills fetched are those near the screen of the first band's cards: none of a folded band's, none far below.
      const stills = await stillsNow();
      const firstIds = new Set(FIRST.cards.map((card) => card.id));
      check(`${theme}: the stills near the screen are fetched, and none beyond and none of a folded band (${stills.filter((still) => still.shown).length} of ${stills.length})`, stills.every((still) => still.shown === still.near && firstIds.has(still.card)) && stillsAsked(from).length === stills.filter((still) => still.shown).length && stillsAsked(from).every((one) => firstIds.has(stillOfCard.get(one))), JSON.stringify([stillsAsked(from), stills.map((still) => [still.card, still.shown, still.near])]));
      check(`${theme}: each still is the one for the theme, with its size stated`, stills.filter((still) => still.shown).every((still) => still.file.includes(`.${theme}.`) && still.width > 0 && still.height > 0), JSON.stringify(stills.map((still) => still.file)));
      // The foot (where what has not run stands, and the revisions the cards read) stays under the folded bands.
      const foot = await evaluate(`(() => { const bands = [...${R}.querySelectorAll(".landing-band")]; const last = bands.at(-1).getBoundingClientRect().bottom; const lines = [${R}.querySelector(".landing-not-run"), ${R}.querySelector(".landing-built")].filter(Boolean); return { lines: lines.length, under: lines.every((el) => el.checkVisibility() && el.getBoundingClientRect().top >= last - 0.5), after: lines.every((el) => bands.every((band) => band.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING)) }; })()`);
      check(`${theme}: the not-run line and the cards' revisions stand at the foot, under the folded bands`, foot.lines === (cards.not_run ? 2 : 1) && foot.under && foot.after, JSON.stringify(foot));
      const sideways = await sidewaysNow();
      check(`${theme}: folded, nothing scrolls sideways at ${WIDTH} by ${HEIGHT}`, sideways.page <= 0 && sideways.box <= 0 && sideways.out === 0, JSON.stringify(sideways));
      const headContrast = await contrastOf(HEAD_WORDS);
      check(`${theme}: every band's head and control read against their ground (contrast of 4.5 or more)`, !headContrast.length, JSON.stringify(headContrast.slice(0, 6)));
      if (PHONE) {
        const small = await smallControls();
        check(`${theme}: folded, on a phone every control on the landing can be pressed with a thumb (44 px or more), each band's control among them`, !small.length && opening.slice(1).every((band) => band.control), JSON.stringify(small.slice(0, 6)));
      }
      const idle = await evaluate(`(async () => { const s = ${V}.stage; if (!s) return { none: true }; await new Promise((r) => setTimeout(r, 600)); const a = s.renderer.info.render.frame; await new Promise((r) => setTimeout(r, 2500)); return { frames: s.renderer.info.render.frame - a, running: s.running, labels: ${R}.querySelectorAll(".labels .label").length, children: s.scene.children.length }; })()`);
      check(`${theme}: the stage draws no frame while the landing shows`, idle.none || (idle.frames === 0 && idle.running === false && idle.labels === 0), JSON.stringify(idle));
      await picture(`${theme}-top`);
      await evaluate(`${V}.landingView.box.scrollTop = ${V}.landingView.box.scrollHeight`);
      await until(STILLS_SETTLED, 10000);
      await picture(`${theme}-folded-end`);
      await evaluate(`${V}.landingView.box.scrollTop = 0`);

      if (k === 0) {
        // ------------------------------------------------------------ the keyboard, folded: the first band's cards, then each control
        const folded = await walk(FIRST.cards.length * 2 + LATER.length + 8);
        const expected = [...FIRST.cards.map((card) => card.id), ...LATER.map((band) => `band:${band.id}`), ...(cards.not_run?.lens ? ["not-run"] : [])];
        check("folded, the keyboard reaches the first band's cards, then each band's control in the page's order, and no card of a folded band", JSON.stringify(folded.visits) === JSON.stringify(expected), folded.visits.join(","));
        check("folded, each with a visible focus, in sight", !folded.unseen.length, folded.unseen.join(","));
      }

      // ------------------------------------------------------------ each control: a press shows its cards, a second folds them, a third shows them again
      for (const band of LATER) {
        const before = asked.length;
        const opened = await pressControl(band.id, true);
        await until(STILLS_SETTLED, 15000);
        await quiet(800);
        const state = (await bandsNow()).find((item) => item.id === band.id);
        await picture(`${theme}-shown-${band.id}`);
        const control = controlOf(band, true);
        check(`${theme}: a press on "${controlOf(band).says}" shows its ${band.cards.length} cards under its head, and the control offers to fold them ("${control.says}")`, opened && state.control.expanded === "true" && state.control.says === control.says && JSON.stringify(state.shown) === JSON.stringify(band.cards.map((card) => card.id)) && state.under === true, JSON.stringify(state));
        const own = new Set(band.cards.map((card) => card.id));
        const stills = (await stillsNow()).filter((still) => own.has(still.card));
        const fetched = stillsAsked(before);
        check(`${theme}: ${band.id}'s stills are asked for once shown and near the screen, and none beyond (${stills.filter((still) => still.shown).length} of ${stills.length})`, stills.every((still) => still.shown === still.near) && fetched.every((one) => own.has(stillOfCard.get(one))) && fetched.length === stills.filter((still) => still.shown).length, JSON.stringify([fetched, stills.map((still) => [still.card, still.shown, still.near])]));
        const shut = await pressControl(band.id, false);
        const after = (await bandsNow()).find((item) => item.id === band.id);
        check(`${theme}: a second press folds them again ("${controlOf(band).says}"), out of sight and out of reach`, shut && after.control.expanded === "false" && after.hidden && after.display === "none" && after.shown.length === 0 && after.control.says === controlOf(band).says, JSON.stringify(after));
        const reopened = await pressControl(band.id, true);
        await until(STILLS_SETTLED, 15000);
        await quiet(800);
        const twice = stillsAsked(before).filter((one, n, all) => all.indexOf(one) !== n);
        check(`${theme}: a third press shows them again, and no still is fetched twice`, reopened && !twice.length, JSON.stringify({ twice, asked: stillsAsked(before) }));
      }

      // ------------------------------------------------------------ every band open: every card with its words, read, in reach
      const allOpen = await bandsNow();
      check(`${theme}: with every band shown, every card of the file stands (${ALL.length}), each band open under its control`, standAs(allOpen, new Set(LATER.map((band) => band.id))) && (await shownCards()).length === ALL.length, describeBands(allOpen));
      const faces = await evaluate(`[...${R}.querySelectorAll(".landing-card")].map((el) => ({ id: el.dataset.card, title: el.querySelector(".landing-title")?.textContent || "", standing: el.querySelector(".landing-standing")?.textContent || "", lead: el.querySelector(".landing-standing")?.firstElementChild?.className || "", leadText: el.querySelector(".landing-standing")?.firstElementChild?.textContent || "", alt: el.querySelector(".landing-still")?.alt || null }))`);
      const byId = new Map(faces.map((face) => [face.id, face]));
      const wrong = cards.cards.filter((card) => {
        const face = byId.get(card.id);
        if (!face || face.title !== card.title) return true;
        if (card.standing?.first) return face.lead !== "landing-first" || face.leadText !== card.standing.first || (face.alt !== null && !face.alt.startsWith(card.standing.first));
        return !face.standing.replace(/\s+/g, " ").includes(firstWords(card).replace(/\s+/g, " ").replace(/…$/, "").slice(0, 24));
      });
      check(`${theme}: every card stands with its title and its standing's first words, and first words (standing.first) come before anything else of its standing and beside its still`, !wrong.length, wrong.map((card) => card.id).join(", "));
      const order = faces.map((face) => face.id);
      check(`${theme}: the cards stand in the order the file's bands give`, JSON.stringify(order) === JSON.stringify(ALL), order.join(","));
      const sidewaysOpen = await sidewaysNow();
      check(`${theme}: open, nothing scrolls sideways at ${WIDTH} by ${HEIGHT}`, sidewaysOpen.page <= 0 && sidewaysOpen.box <= 0 && sidewaysOpen.out === 0, JSON.stringify(sidewaysOpen));
      const contrast = await contrastOf(`${CARD_WORDS}, ${HEAD_WORDS}`);
      check(`${theme}: every card's words, and every band's head and control, read against their ground (contrast of 4.5 or more)`, !contrast.length, JSON.stringify(contrast.slice(0, 6)));
      if (PHONE) {
        const small = await smallControls();
        check(`${theme}: open, on a phone every control on the landing can be pressed with a thumb (44 px or more)`, !small.length, JSON.stringify(small.slice(0, 6)));
      }
      const doubled = stillsAsked(from).filter((one, n, all) => all.indexOf(one) !== n);
      const near = (await stillsNow()).filter((still) => still.near && !still.shown);
      check(`${theme}: every still near the screen has come, each fetched once, and each of a band that was shown`, !doubled.length && !near.length, JSON.stringify({ doubled, near: near.map((still) => still.card) }));
      check(`${theme}: no console error`, !errorsNow().length, errorsNow().join(" | "));
      await bring(controlEl(LATER[0].id));
      await until(STILLS_SETTLED, 10000);
      await picture(`${theme}-open-${LATER[0].id}`);
      await evaluate(`(() => { const box = ${V}.landingView.box; box.scrollTop = Math.round((box.scrollHeight - box.clientHeight) / 2); })()`);
      await until(STILLS_SETTLED, 10000);
      await picture(`${theme}-middle`);
      await evaluate(`(() => { const box = ${V}.landingView.box; box.scrollTop = box.scrollHeight; })()`);
      await until(STILLS_SETTLED, 10000);
      await picture(`${theme}-end`);
      if (k > 0) continue;

      // ------------------------------------------------------------ with less motion, nothing on the landing moves
      await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });
      const moving = await evaluate(`[...${V}.landingView.box.querySelectorAll("*")].filter((el) => { const s = getComputedStyle(el); const moves = (list) => list.split(",").some((d) => parseFloat(d) > 0); return (s.transitionProperty !== "none" && moves(s.transitionDuration)) || (s.animationName !== "none" && moves(s.animationDuration)); }).map((el) => el.className).slice(0, 8)`);
      const lastBand = LATER.at(-1).id;
      const foldedStill = await pressControl(lastBand, false);
      const reducedStill = await evaluate(`getComputedStyle(${controlEl(lastBand)}.querySelector(".landing-fold-chevron")).transitionDuration`);
      const openedStill = await pressControl(lastBand, true);
      await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "no-preference" }] });
      const turning = await evaluate(`getComputedStyle(${controlEl(lastBand)}.querySelector(".landing-fold-chevron")).transitionDuration`);
      check("with less motion asked for, nothing on the landing moves (no transition, no animation), and a control still folds and opens its band", !moving.length && foldedStill && openedStill && parseFloat(reducedStill) === 0 && parseFloat(turning) > 0, JSON.stringify({ moving, reducedStill, turning }));

      // ------------------------------------------------------------ the keyboard, open: every card in order, and each control before its band's
      const open = await walk(ALL.length * 2 + LATER.length + 8);
      const expected = [...landing.bands.flatMap((band, n) => [...(n ? [`band:${band.id}`] : []), ...band.cards.map((card) => card.id)]), ...(cards.not_run?.lens ? ["not-run"] : [])];
      check("with the bands open, the keyboard reaches every card in order, each band's control before its cards", JSON.stringify(open.visits) === JSON.stringify(expected), `${open.visits.length} of ${expected.length}: ${open.visits.slice(0, 6).join(",")}…`);
      check("each with a visible focus, in sight", !open.unseen.length, open.unseen.slice(0, 6).join(","));

      // ------------------------------------------------------------ what a visitor opened is kept for their next visit
      await page("Page.reload", {});
      await until(`Boolean(${V}?.model) && ${FIRST_DRAWN}`, 60000);
      const kept = await bandsNow();
      check("the bands a visitor opened stand open again on their next visit (the browser's own storage)", standAs(kept, new Set(LATER.map((band) => band.id))), describeBands(kept));
      await pressControl(LATER[0].id, false);
      await page("Page.reload", {});
      await until(`Boolean(${V}?.model) && ${FIRST_DRAWN}`, 60000);
      const keptFolded = await bandsNow();
      check(`a band folded again is folded on the next visit (${LATER[0].id}), the others stay open`, standAs(keptFolded, new Set(LATER.slice(1).map((band) => band.id))), describeBands(keptFolded));
      // Where the browser refuses storage (its storage throws as soon as it is touched), the page stands whole: the first band alone open.
      check("no console error through less motion, the keyboard's walk and the kept bands' visits", !errorsNow().length, errorsNow().join(" | "));
      const { identifier } = await page("Page.addScriptToEvaluateOnNewDocument", { source: `Object.defineProperty(window, "localStorage", { configurable: true, get() { throw new DOMException("refused by the check", "SecurityError"); } });` });
      errors.length = 0;
      await navigate("lens=experiments");
      const refusedDrawn = await until(FIRST_DRAWN, 30000);
      const refused = await bandsNow();
      const refusedPress = await pressControl(LATER.at(-1).id, true);
      const refusedProbe = await evaluate(`(() => { try { localStorage.length; return "storage answered"; } catch (error) { return "refused"; } })()`);
      check("where storage is refused, the page works whole: the first band alone open, each control opens its band, no error", refusedDrawn && standAs(refused, new Set()) && refusedPress && refusedProbe === "refused" && !errorsNow().length, JSON.stringify({ bands: describeBands(refused), refusedPress, refusedProbe, errors: errorsNow() }));
      await page("Page.removeScriptToEvaluateOnNewDocument", { identifier });

      // ------------------------------------------------------------ each replay card: its view, and the way back
      await fresh("lens=experiments");
      await until(FIRST_DRAWN, 30000);
      for (const band of LATER) await pressControl(band.id, true);
      const opens = new Set(LATER.map((band) => band.id));
      const catalogue = await evaluate(`(() => { const r = ${V}.model.raw.replays; return { experiments: r.experiments.map((e) => ({ id: e.id, opens: e.opens, part_of: e.part_of, tissue: e.tissue ? { walk_of: e.tissue.walk_of || null } : undefined })), runs: r.runs.map((x) => ({ id: x.id, experiment: x.experiment, arm: x.arm })), doors: r.doors || [] }; })()`);
      const replays = cards.cards.filter((card) => opensOf(card, catalogue));
      check(`every replay card the page plays has its place on the landing (${replays.length})`, (await evaluate(`${R}.querySelectorAll(".landing-card.is-replay").length`)) === replays.length);
      let place = null, deep = 0;
      for (const card of replays) {
        const opened = opensOf(card, catalogue);
        await bring(`${cardEl(card.id)}?.querySelector(".landing-open")`);
        const scrolled = await evaluate(`${V}.landingView.box.scrollTop`);
        from = asked.length;
        await press(`${cardEl(card.id)}.querySelector(".landing-open")`);
        const shown = await until(
          opened.run ? `!${V}.state.landing && ${V}.current?.run?.id === ${JSON.stringify(opened.run)} && !${V}.current.loading` : opened.part ? `!${V}.state.landing && ${V}.state.part === ${JSON.stringify(opened.part)} && ${V}.current?.runs?.length > 0 && !${V}.current.loading` : `!${V}.state.landing && ${V}.state.example === ${JSON.stringify(opened.example)} && Boolean(${V}.current?.player)`,
          60000
        );
        // The view laid out: the way back, the view's card, its folded line and its rail where they stand, read until they stop moving.
        const view = await stable(`(() => { const v = ${V}, b = v.backButton.getBoundingClientRect(), seen = (el) => el && !el.hidden && el.getClientRects().length && getComputedStyle(el).display !== "none" ? el.getBoundingClientRect() : null; const meets = (a, c) => Boolean(a && c) && a.left < c.right - 0.5 && c.left < a.right - 0.5 && a.top < c.bottom - 0.5 && c.top < a.bottom - 0.5; const others = [["the folded card", seen(v.viewToggle)], ["the rail", seen(v.railToggle)], ["the card", seen(v.viewCard)]].filter(([, r]) => r); return { back: !v.backButton.hidden, at: [Math.round(b.left), Math.round(b.top)], height: Math.round(b.height), meets: others.filter(([, r]) => meets(b, r)).map(([n]) => n), boxes: others.map(([n, r]) => [n, Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]), landingHidden: v.landingView.box.hidden, search: location.search, sideways: document.documentElement.scrollWidth - innerWidth }; })()`);
        delete view.boxes;
        const runs = beside(from).filter((one) => one.startsWith("/runs/") || one.startsWith("/models/"));
        check(`${card.id}: a press opens its view (the view's own address: ${addressOf(opened)}), and the page's address names no view and no card's detail`, shown && view.landingHidden && !/[?&](run|part|example|select)=/.test(view.search), JSON.stringify({ shown, search: view.search, runs: runs.length }));
        place ??= view.at;
        check(`${card.id}: the way back stands in its one place, clear of the view's own controls${PHONE ? ", as large as a thumb" : ""}`, view.back && Math.abs(view.at[0] - place[0]) <= 1 && Math.abs(view.at[1] - place[1]) <= 1 && !view.meets.length && (!PHONE || view.height >= 44) && view.sideways <= 0, JSON.stringify(view));
        await picture(`view-${card.id}`);
        await press(`${V}.backButton`);
        const returned = await until(`${V}.state.landing && !${V}.landingView.box.hidden && ${R}.activeElement?.closest?.(".landing-card")?.dataset.card === ${JSON.stringify(card.id)} && Math.abs(${V}.landingView.box.scrollTop - ${scrolled}) <= 2`, 10000);
        const after = await evaluate(`({ top: ${V}.landingView.box.scrollTop, focus: ${R}.activeElement?.closest?.(".landing-card")?.dataset.card || null, search: location.search })`);
        const bandsBack = await bandsNow();
        if (scrolled > 0 && bandHolding(landing, card.id) !== FIRST) deep += 1;
        check(`${card.id}: the way back returns to the landing with the same bands open, where it was scrolled (${Math.round(scrolled)} px), the keyboard on the card it left`, returned && Math.abs(after.top - scrolled) <= 2 && after.focus === card.id && !/run=|part=|example=/.test(after.search) && standAs(bandsBack, opens), JSON.stringify({ scrolled, ...after, bands: describeBands(bandsBack) }));
      }
      check(`the way back was held at a place scrolled down, on cards of later bands (${deep})`, deep > 0 || !replays.some((card) => bandHolding(landing, card.id) !== FIRST), String(deep));
      // From a part, its networks are its whole's opening run, though the runs' view last held another card's run.
      const partCard = replays.find((card) => opensOf(card, catalogue).part);
      const whole = partCard ? catalogue.experiments.find((item) => item.id === opensOf(partCard, catalogue).part)?.part_of : null;
      const runCard = replays.find((card) => opensOf(card, catalogue).run && catalogue.runs.find((run) => run.id === opensOf(card, catalogue).run)?.experiment !== whole);
      if (partCard && runCard && whole) {
        const networks = new Catalogue(catalogue).openingRun(whole);
        for (const card of [runCard, partCard]) {
          await bring(`${cardEl(card.id)}?.querySelector(".landing-open")`);
          await press(`${cardEl(card.id)}.querySelector(".landing-open")`);
          await until(`!${V}.state.landing && Boolean(${V}.current) && !${V}.current.loading && (${V}.current.run || ${V}.current.runs?.length)`, 60000);
          if (card === runCard) {
            await press(`${V}.backButton`);
            await until(`${V}.state.landing && !${V}.landingView.box.hidden`, 10000);
          }
        }
        if (PHONE && !(await evaluate(`${V}.state.viewOpen`)) && (await evaluate(`!${V}.viewToggle.hidden`))) {
          await press(`${V}.viewToggle`);
          await until(`${V}.state.viewOpen`, 10000);
        }
        await until(`Boolean(${R}.querySelector(".view .tissue-back:not(.tissue-sibling)")?.checkVisibility())`, 20000);
        await press(`${R}.querySelector(".view .tissue-back:not(.tissue-sibling)")`);
        const reached = await until(`!${V}.state.part && ${V}.current?.run?.id === ${JSON.stringify(networks)} && Boolean(${V}.current.sheet)`, 60000);
        check(`from ${partCard.id}'s part, its networks' button shows the networks' opening run (${networks}), not ${runCard.id}'s run shown before`, reached, await evaluate(`${V}.current?.run?.id || ${V}.current?.runId || null`));
        await press(`${V}.backButton`);
        await until(`${V}.state.landing && !${V}.landingView.box.hidden`, 10000);
      }
      // A replay card's detail has a door to its view: a press on it opens the view, as the card does.
      const opener = replays[0];
      if (opener) {
        await bring(`${cardEl(opener.id)}?.querySelector(".landing-more")`);
        await press(`${cardEl(opener.id)}.querySelector(".landing-more")`);
        await until(`!${R}.querySelector("cells-panel").hidden && ${R}.querySelector("cells-panel h2")?.textContent === ${JSON.stringify(opener.title)} && [...${R}.querySelectorAll("cells-panel .panel-door button")].some((b) => /Open its replay/.test(b.textContent) && b.checkVisibility())`, 10000);
        const door = await evaluate(`[...${R}.querySelectorAll("cells-panel .panel-door button")].find((b) => /Open its replay/.test(b.textContent)) ? true : false`);
        await press(`[...${R}.querySelectorAll("cells-panel .panel-door button")].find((b) => /Open its replay/.test(b.textContent))`);
        const via = await until(`!${V}.state.landing && Boolean(${V}.current) && !${V}.current.loading && ${R}.querySelector("cells-panel").hidden`, 60000);
        check(`a replay card's detail (${opener.id}) has a door to its view, and a press on it opens the view`, door && via);
        await press(`${V}.backButton`);
        await until(`${V}.state.landing && !${V}.landingView.box.hidden`, 10000);
      }
      const rested = await evaluate(`(async () => { const s = ${V}.stage; if (!s) return { none: true }; await new Promise((r) => setTimeout(r, 2500)); const a = s.renderer.info.render.frame; await new Promise((r) => setTimeout(r, 2000)); return { frames: s.renderer.info.render.frame - a, running: s.running, sheet: Boolean(${V}.lenses.get("experiments")?.sheet) }; })()`);
      check("back on the landing the stage is idle again, and the run left lets its drawing go", rested.none || (rested.frames === 0 && !rested.running && !rested.sheet), JSON.stringify(rested));

      // ------------------------------------------------------------ a card asked for: by its detail's address, from the List, by the way back
      const standing = cards.cards.find((card) => card.kind === "standing" && (card.record || []).some((entry) => entry?.verdict) && bandHolding(landing, card.id) !== FIRST);
      if (standing) {
        const holder = bandHolding(landing, standing.id);
        await fresh(`lens=experiments&select=${CARD}${standing.id}`);
        const byAddress = await until(`${R}.querySelector("cells-panel h2")?.textContent === ${JSON.stringify(standing.title)}`, 30000);
        const inSight = await until(`${IN_SIGHT(cardEl(standing.id))} && ${CLEAR_OF_SHEET(cardEl(standing.id))}`, 10000);
        const state = await bandsNow();
        const chosen = await evaluate(`${cardEl(standing.id)}?.classList.contains("is-chosen") || false`);
        check(`a card's detail asked for by its address (select=${CARD}${standing.id}) opens its band (${holder.id}) first, the card in sight${PHONE ? " above the panel's sheet" : ""} and chosen, the other bands folded`, byAddress && inSight && chosen && standAs(state, new Set([holder.id])) && (await evaluate(`${V}.state.landing`)), JSON.stringify({ byAddress, inSight, chosen, bands: describeBands(state) }));
        await picture(`asked-${standing.id}`);
        // A band opened for a card asked for is open for that visit; the next visit opens as the visitor's own presses left it.
        await navigate("lens=experiments");
        await until(FIRST_DRAWN, 30000);
        const next = await bandsNow();
        check(`a band opened for a card asked for (${holder.id}) is not kept: the next visit opens with the later bands folded`, standAs(next, new Set()), describeBands(next));
      }
      // From the List: every card of every band is listed, folded or not; a card chosen there opens its band.
      const listed = LATER.at(-1).cards[0];
      await fresh("lens=experiments");
      await until(FIRST_DRAWN, 30000);
      await press(`${V}.indexButton`);
      await until(`${R}.querySelectorAll("cells-index .index-row").length > 0 && ${R}.querySelector("cells-index").checkVisibility()`, 10000);
      const rows = await evaluate(`[...${R}.querySelectorAll("cells-index .index-row")].map((row) => row.querySelector(".index-name")?.textContent || "")`);
      const titles = landing.bands.flatMap((band) => band.cards.map((card) => card.title || card.id));
      check(`the List lists every card of every band (${titles.length}), its band folded or not`, JSON.stringify(rows) === JSON.stringify(titles), `${rows.length}: ${rows.slice(0, 4).join(" | ")}`);
      await pressRow(listed.title);
      const fromList = await until(`${R}.querySelector("cells-panel h2")?.textContent === ${JSON.stringify(listed.title)}`, 15000);
      const listInSight = await until(`${IN_SIGHT(cardEl(listed.id))} && ${CLEAR_OF_SHEET(cardEl(listed.id))}`, 10000);
      const listState = await bandsNow();
      // On a window wide enough for both, the List and the panel stand beside the cards: nothing of theirs lies over the card
      // chosen. Narrower, the List lies over the cards (as over every view), and the cards keep a column's room beside the panel.
      const roomy = WIDTH >= LIST_ROOM;
      const uncovered = !roomy || (await until(`(() => { const el = ${cardEl(listed.id)}, r = el.getBoundingClientRect(); return [[0.5, 0.5], [0.1, 0.1], [0.9, 0.9]].every(([x, y]) => ${R}.elementFromPoint(r.left + r.width * x, r.top + r.height * y)?.closest(".landing-card") === el); })()`, 10000));
      const room = await evaluate(`Math.round(${V}.landingView.box.getBoundingClientRect().width)`);
      check(`a card chosen in the List (${listed.id}) opens its band (${LATER.at(-1).id}) first, the card in sight${roomy ? ", beside the List and the panel, not under them" : PHONE ? " above the panel's sheet" : ""}, the other bands folded, and the cards keep a column's room (${room} px)`, fromList && listInSight && uncovered && room >= 296 && standAs(listState, new Set([LATER.at(-1).id])), JSON.stringify({ fromList, listInSight, uncovered, room, bands: describeBands(listState) }));
      await picture(`list-${listed.id}`);
      // By the way back: a card of a later band opened (from its detail's door), its band folded while the view stands (by
      // the landing's own call), and the way back opens its band again, with the keyboard on the card, in sight.
      const plays = replays.find((card) => bandHolding(landing, card.id) !== FIRST);
      if (plays) {
        const holder = bandHolding(landing, plays.id);
        if (!(await evaluate(`${V}.state.indexOpen`))) await press(`${V}.indexButton`);
        await until(`${R}.querySelectorAll("cells-index .index-row").length > 0 && ${R}.querySelector("cells-index").checkVisibility()`, 10000);
        await pressRow(plays.title);
        await until(`${R}.querySelector("cells-panel h2")?.textContent === ${JSON.stringify(plays.title)} && [...${R}.querySelectorAll("cells-panel .panel-door button")].some((b) => /Open its replay/.test(b.textContent) && b.checkVisibility())`, 15000);
        await press(`[...${R}.querySelectorAll("cells-panel .panel-door button")].find((b) => /Open its replay/.test(b.textContent))`);
        const viewed = await until(`!${V}.state.landing && Boolean(${V}.current) && !${V}.current.loading`, 60000);
        // The List put away (wider than a phone it stays open after a choice, and in a view it lies over the way back).
        if (await evaluate(`${V}.state.indexOpen`)) {
          await press(`${V}.indexButton`);
          await until(`!${V}.state.indexOpen`, 10000);
        }
        await evaluate(`${V}.landingView.setOpen(${JSON.stringify(holder.id)}, false)`);
        const foldedAway = await evaluate(`!${V}.landingView.isOpen(${JSON.stringify(holder.id)})`);
        // The way back laid out and nothing over it (what lies at its middle is said if the press misses).
        await until(`(() => { const b = ${V}.backButton, r = b.getBoundingClientRect(); return !b.hidden && ${R}.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2)?.closest(".exp-back") === b; })()`, 10000);
        const over = await evaluate(`(() => { const b = ${V}.backButton, r = b.getBoundingClientRect(), el = ${R}.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return { at: [Math.round(r.left), Math.round(r.top)], hit: el ? el.tagName + "." + el.className : null, list: ${V}.state.indexOpen, card: ${V}.state.viewOpen }; })()`);
        await press(`${V}.backButton`);
        const back = await until(`${V}.state.landing && !${V}.landingView.box.hidden && ${R}.activeElement?.closest?.(".landing-card")?.dataset.card === ${JSON.stringify(plays.id)}`, 10000);
        const backInSight = await until(IN_SIGHT(cardEl(plays.id)), 10000);
        const backState = await bandsNow();
        check(`the way back to a card (${plays.id}) whose band was folded meanwhile opens its band (${holder.id}) first, the keyboard on the card, in sight`, viewed && foldedAway && back && backInSight && backState.find((band) => band.id === holder.id)?.control.expanded === "true", JSON.stringify({ viewed, foldedAway, back, backInSight, over, bands: describeBands(backState) }));
      }

      // ------------------------------------------------------------ a standing's detail: by a press, and by its address
      if (standing) {
        await fresh("lens=experiments");
        await until(FIRST_DRAWN, 30000);
        await pressControl(bandHolding(landing, standing.id).id, true);
        await bring(`${cardEl(standing.id)}?.querySelector(".landing-open")`);
        await press(`${cardEl(standing.id)}.querySelector(".landing-open")`);
        await until(`!${R}.querySelector("cells-panel").hidden && ${R}.querySelector("cells-panel h2")?.textContent === ${JSON.stringify(standing.title)} && new URL(location.href).searchParams.get("select") === ${JSON.stringify(CARD + standing.id)}`, 10000);
        const panel = await evaluate(`(() => { const p = ${R}.querySelector("cells-panel"); return { title: p.querySelector("h2")?.textContent || "", text: p.textContent, links: [...p.querySelectorAll("a")].map((a) => a.href).filter((href) => /\\/blob\\/[0-9a-f]{40}\\//.test(href)).length, doors: [...p.querySelectorAll(".panel-door button")].map((b) => b.textContent), select: new URL(location.href).searchParams.get("select") }; })()`);
        const counts = (standing.record || []).filter((entry) => entry?.verdict?.count).map((entry) => `${entry.verdict.count.passed} of ${entry.verdict.count.of}`);
        check(`a standing's detail opens by a press (${standing.id}): its title, every count, its sources as links at their revisions, a door to its part on the Engine map, and an address of its own`, panel.title === standing.title && counts.every((count) => panel.text.includes(count)) && panel.links > 0 && panel.doors.some((door) => /Engine map/.test(door)) && panel.select === CARD + standing.id, JSON.stringify({ ...panel, text: panel.text.length }));
        await picture(`detail-${standing.id}`);
        await key("Escape", "Escape", 27);
        check("Escape closes the detail, and the address no longer names it", await until(`${R}.querySelector("cells-panel").hidden && !new URL(location.href).searchParams.get("select")`, 10000));
        await fresh(`lens=experiments&select=${CARD}${standing.id}`);
        const byAddress = await until(`${R}.querySelector("cells-panel h2")?.textContent === ${JSON.stringify(standing.title)}`, 30000);
        check(`and by its address (select=${CARD}${standing.id})`, byAddress && (await evaluate(`${V}.state.landing`)));
      }
      // The address when the tab is left: a detail's address goes with it, and nothing of the landing's outranks the next
      // tab's #name (the landing writes no lens=): a reload opens the tab pressed.
      if (standing) {
        await forget();
        await page("Page.navigate", { url: `${base}#experiments` });
        await until(`Boolean(${V}?.model) && ${FIRST_DRAWN}`, 30000);
        await pressControl(bandHolding(landing, standing.id).id, true);
        await bring(`${cardEl(standing.id)}?.querySelector(".landing-open")`);
        await press(`${cardEl(standing.id)}.querySelector(".landing-open")`);
        await until(`!${R}.querySelector("cells-panel").hidden && new URL(location.href).searchParams.get("select") === ${JSON.stringify(CARD + standing.id)}`, 10000);
        const named = await evaluate(`location.search`);
        await press(`${R}.querySelector('.switch [data-lens="cell"]')`);
        await until(`${V}.state.lens === "cell"`, 20000);
        const left = await evaluate(`({ search: location.search, hash: location.hash })`);
        await page("Page.reload", {});
        await until(`Boolean(${V}?.model && ${V}.current)`, 60000);
        const reloaded = await evaluate(`${V}.state.lens`);
        check("the tab left, the address keeps no card's detail and no lens= of the landing's, and a reload opens the tab pressed", new URLSearchParams(named).get("select") === CARD + standing.id && !/[?&](lens|select)=/.test(left.search) && left.hash === "#cell" && reloaded === "cell", JSON.stringify({ named, ...left, reloaded }));
      }
      const rowsCard = cards.cards.find((card) => card.kind === "rows");
      if (rowsCard) {
        await fresh(`lens=experiments&select=${CARD}${rowsCard.id}`);
        await until(`${R}.querySelector("cells-panel h2")?.textContent === ${JSON.stringify(rowsCard.title)}`, 30000);
        const items = await evaluate(`(() => { const p = ${R}.querySelector("cells-panel"); const block = [...p.querySelectorAll(".panel-list")].find((el) => /^Its rows/.test(el.querySelector("h4")?.textContent || "")); return block ? [...block.querySelectorAll("li.item")].map((li) => li.textContent) : []; })()`);
        const holder = bandHolding(landing, rowsCard.id);
        const rowsState = await bandsNow();
        check(`the rows' card lists its ${rowsCard.rows.length} rows, each with its result and its reference, its band (${holder.id}) open for it`, items.length === rowsCard.rows.length && rowsCard.rows.every((row, n) => items[n].includes(row.id) && /Passed|Failed/.test(items[n]) && items[n].includes(row.reference.path)) && standAs(rowsState, new Set(holder === FIRST ? [] : [holder.id])), JSON.stringify(items.map((text) => text.slice(0, 60))));
        await picture(`detail-${rowsCard.id}`);
      }
      // ------------------------------------------------------------ the not-run line
      if (cards.not_run?.lens) {
        await fresh("lens=experiments");
        await until(FIRST_DRAWN, 30000);
        const line = await evaluate(`${R}.querySelector(".landing-not-run")?.textContent || ""`);
        await bring(`${R}.querySelector(".landing-not-run button")`);
        await press(`${R}.querySelector(".landing-not-run button")`);
        const lens = await until(`${V}.state.lens === ${JSON.stringify(cards.not_run.lens)}`, 15000);
        check("the not-run line says where what never ran stands, in the file's words, and opens that view", line === cards.not_run.says && lens, line);
      }
      check("no console error through every view and back", !errorsNow().length, errorsNow().join(" | "));

      // ------------------------------------------------------------ About and the first-visit line (src/ui/about.js)
      // Every run of a check is a first visit (its browser's profile is new, and removed after it): the line is looked at
      // where it stands in the site's first view and on the landing, then About is opened, closed and opened again in
      // every way, and the line's closing is held last, kept and refused.
      const LINE = `${V}.about`;
      const lineState = () => evaluate(`(() => { const a = ${LINE}, l = a.line, r = l.getBoundingClientRect(), f = ${V}.frame.getBoundingClientRect(), bar = ${V}.bar.getBoundingClientRect(); const box = { left: r.left - f.left, top: r.top - f.top, right: r.right - f.left, bottom: r.bottom - f.top }; const over = a.taken().filter((t) => { const gx = t.gapX ?? 8, gy = t.gapY ?? 8; return !(box.right + gx <= t.left || box.left >= t.right + gx || box.bottom + gy <= t.top || box.top >= t.bottom + gy); }); return { open: Boolean(a.lineOpen), placed: a.placed, seen: a.lineOpen && getComputedStyle(l).visibility === "visible", inert: l.inert, box: [box.left, box.top, box.right, box.bottom].map(Math.round), under: r.top >= bar.bottom, over: over.length, words: l.textContent.replace(/\\s+/g, " ").trim() }; })()`);
      const lineHolds = (state) => state.open && (state.placed === "none" ? !state.seen && state.inert : state.seen && !state.inert && state.under && state.over === 0);
      for (const [where, query] of [["the site's first view", ""], ["the landing", "lens=experiments"]]) {
        await fresh(query);
        await until(`Boolean(${V}.current) && ${LINE}.placed !== null`, 30000);
        await stable(`${LINE}.placed`, 5000);
        const state = await lineState();
        check(`a first visit, ${where}: the line is there, and where it stands it is under the bar and covers nothing the page put over the picture (8 px clear) and no name the view shows (as clear as a name keeps of a card); where no band is free (and on a phone) it waits out of sight and out of the keyboard's reach`, lineHolds(state) && (!PHONE || state.placed === "none"), JSON.stringify(state));
        note(`  the line, ${WIDTH} by ${HEIGHT}, ${where}: ${state.placed === "none" ? (PHONE ? "waits (a phone)" : "waits (no band under the bar is free)") : `stands at ${state.box.join(", ")}`}`);
        await picture(`line-${query ? "landing" : "first"}`);
      }
      // The button: after List in the bar, its words "About", pressed as a button is pressed.
      await fresh("");
      await until(`Boolean(${V}.current) && ${LINE}.placed !== null`, 30000);
      const button = await evaluate(`(() => { const b = ${LINE}.button, list = ${V}.indexButton, r = b.getBoundingClientRect(), l = list.getBoundingClientRect(); return { words: b.textContent, pressed: b.getAttribute("aria-pressed"), after: b.previousElementSibling === list, inBar: b.closest(".bar") === ${V}.bar, row: Math.abs((r.top + r.bottom) / 2 - (l.top + l.bottom) / 2) < 2, size: [Math.round(r.width), Math.round(r.height)], inside: r.right <= innerWidth + 0.5 }; })()`);
      check("the About button stands in the bar after List, in its row and inside the window, its words About, not pressed", button.words === "About" && button.pressed === "false" && button.after && button.inBar && button.row && button.inside && (!PHONE || (button.size[0] >= 44 && button.size[1] >= 44)), JSON.stringify(button));
      const lens = await evaluate(`${V}.state.lens`);
      await press(`${LINE}.button`);
      await until(`${V}.state.about && !${R}.querySelector("cells-panel").hidden`, 10000);
      await sleep(300);
      const opened = await evaluate(`(() => { const p = ${R}.querySelector("cells-panel"), links = [...p.querySelectorAll("a")]; const source = links.find((a) => a.textContent.startsWith("Source code")); return { heading: p.querySelector("h2")?.textContent, focus: ${R}.activeElement === p.querySelector("h2"), pressed: ${LINE}.button.getAttribute("aria-pressed"), doors: [...p.querySelectorAll("[data-door]")].map((b) => b.dataset.door), source: source ? { href: source.href, target: source.target, rel: source.rel, name: source.textContent } : null, licence: links.find((a) => /licen[cs]e/i.test(a.textContent + a.href))?.href || null, credit: p.querySelector(".about-credit")?.textContent || null, line: ${LINE}.lineOpen, kept: (() => { try { return localStorage.getItem("cells-visualizer.intro.closed"); } catch { return "refused"; } })(), hasPanel: ${V}.frame.classList.contains("has-panel"), lens: ${V}.state.lens }; })()`);
      check("pressed, About opens in the panel's place: its heading, the focus on it, every view a door, the source code in a new tab (noopener noreferrer) and no licence link, the credit line; the line closes and stays closed", opened.heading === "Cells" && opened.focus && opened.pressed === "true" && opened.doors.length === (await evaluate(`${V}.views.length`)) && opened.source?.href === "https://github.com/Eidosoma/Cells" && opened.source.target === "_blank" && opened.source.rel === "noopener noreferrer" && opened.licence === null && opened.credit === ABOUT_WORDS.credit.text && !opened.line && opened.kept === "closed" && opened.hasPanel && opened.lens === lens, JSON.stringify(opened));
      await picture("about-open");
      await key("Escape", "Escape", 27);
      await until(`!${V}.state.about`, 5000);
      const closed = await evaluate(`({ about: ${V}.state.about, panel: ${R}.querySelector("cells-panel").hidden, focus: ${R}.activeElement === ${LINE}.button, lens: ${V}.state.lens, hasPanel: ${V}.frame.classList.contains("has-panel"), pressed: ${LINE}.button.getAttribute("aria-pressed") })`);
      check("Escape closes it as any panel closes, gives the view back as it was, and the focus to the About button", !closed.about && closed.panel && closed.focus && closed.lens === lens && !closed.hasPanel && closed.pressed === "false", JSON.stringify(closed));
      // The name in the bar's corner (where it is in sight), and the panel's own close button.
      const brandSeen = await evaluate(`(() => { const r = ${LINE}.brand.parentElement.getBoundingClientRect(); return r.width > 2 && r.height > 2; })()`); // the name's box, which the squeeze makes 1 px
      if (brandSeen) {
        await press(`${LINE}.brand`);
        const byName = await until(`${V}.state.about`, 5000);
        await press(`${R}.querySelector("cells-panel .about-head .icon-button")`);
        const shut = await until(`!${V}.state.about && ${R}.querySelector("cells-panel").hidden`, 5000);
        check("the name Cells in the bar's corner opens About too, and its close button closes it", byName && shut);
      } else note("  the name in the bar's corner is out of sight at this width (the bar is squeezed): About is the bar's button alone");
      // A door: the view it names opens, as its tab would, and About closes.
      await press(`${LINE}.button`);
      await until(`${V}.state.about`, 5000);
      const door = (await evaluate(`${V}.views.map((v) => v.id)`)).find((id) => id !== lens && id !== "experiments");
      await evaluate(`${R}.querySelector('cells-panel [data-door=${JSON.stringify(door)}]').scrollIntoView({ block: "center" })`);
      await press(`${R}.querySelector('cells-panel [data-door=${JSON.stringify(door)}]')`);
      const through = await until(`${V}.state.lens === ${JSON.stringify(door)} && !${V}.state.about`, 15000);
      check(`a door in About opens its view (${door}), as its tab does, and About closes`, through && (await evaluate(`location.hash`)) === `#${door}`, await evaluate(`JSON.stringify({ lens: ${V}.state.lens, about: ${V}.state.about, hash: location.hash })`));
      // Closed, the line stays closed in this browser.
      await navigate("");
      await until(`Boolean(${V}.current) && ${LINE}.about !== null`, 30000);
      check("the line, closed, stays closed on the next visit in this browser", !(await evaluate(`${LINE}.lineOpen`)));
      // The address names About: #about opens it over the site's first view, and opening it closes the line.
      await page("Page.navigate", { url: "about:blank" });
      await forget();
      await page("Page.navigate", { url: `${base}#about` });
      await until(`Boolean(${V}?.current) && ${V}.state.about`, 30000);
      const byAddress = await evaluate(`({ about: ${V}.state.about, lens: ${V}.state.lens, first: ${V}.views[0].id, line: ${LINE}.lineOpen, panel: !${R}.querySelector("cells-panel").hidden, hash: location.hash })`);
      check("#about opens About over the first view, and the line with it is closed", byAddress.about && byAddress.lens === byAddress.first && byAddress.panel && !byAddress.line && byAddress.hash === "#about", JSON.stringify(byAddress));
      // Where the browser keeps nothing, the line shows again on every visit, and closing it breaks nothing.
      errors.length = 0;
      const refusing = await page("Page.addScriptToEvaluateOnNewDocument", { source: `Object.defineProperty(window, "localStorage", { configurable: true, get() { throw new DOMException("refused by the check", "SecurityError"); } });` });
      await navigate("");
      await until(`Boolean(${V}.current) && ${LINE}.placed !== null`, 30000);
      const before = await evaluate(`${LINE}.lineOpen`);
      // Where it stands once its place has settled (the view's names come in its first frames), its × is pressed; where it waits, it is closed as its × closes it.
      if ((await stable(`${LINE}.placed`, 5000)) !== "none") await press(`${LINE}.line.querySelector(".intro-close")`);
      else await evaluate(`${LINE}.closeLine({ keep: true })`);
      const gone = await until(`!${LINE}.lineOpen`, 5000);
      await navigate("");
      await until(`Boolean(${V}.current) && ${LINE}.about !== null`, 30000);
      const again = await evaluate(`${LINE}.lineOpen`);
      check("where storage is refused, the line shows, closes without an error, and shows again on the next visit", before && gone && again && !errorsNow().length, JSON.stringify({ before, gone, again, errors: errorsNow() }));
      await page("Page.removeScriptToEvaluateOnNewDocument", { identifier: refusing.identifier });
      // With less motion asked for, the line does not move.
      await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });
      await fresh("");
      await until(`Boolean(${V}.current) && ${LINE}.placed !== null`, 30000);
      const still = await evaluate(`getComputedStyle(${LINE}.line).transitionDuration.split(",").every((d) => parseFloat(d) === 0)`);
      await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "no-preference" }] });
      check("with less motion asked for, the line does not move", still);
      check("no console error through About and the line", !errorsNow().length, errorsNow().join(" | "));
    }
  }
} catch (error) {
  failed = error;
} finally {
  chrome.kill("SIGTERM");
  await new Promise((resolve) => {
    chrome.once("exit", resolve);
    setTimeout(resolve, 8000);
  });
  release();
  server.close();
}
if (failed) {
  console.error(failed.stack || String(failed));
  check("the checks ran to their end", false, String(failed.message || failed).slice(0, 200));
}
console.log(`${results.filter(Boolean).length} of ${results.length} checks passed`);
process.exit(results.every(Boolean) ? 0 : 1);
