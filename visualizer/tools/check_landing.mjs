#!/usr/bin/env node
// Checks the Experiments tab's landing (src/ui/landing.js) in a real browser, with real presses and keys through the
// DevTools protocol, on the page as the local server builds it with the runs folder at out/runs. What it expects is read
// from data/replays/cards.json at run time: no card, band, count or level is named here, so the cards may change.
//
//   wide     1440 by 900      720      1280 by 720      phone    400 by 860      narrow   360 by 780
//   retry    1280 by 720: the cards' file held back (the landing says that it is coming), then refused (it says that it
//            could not be fetched, offers to try again, and the rest of the page works), then given on "Try again".
//
// Each size case, in the light theme and in the dark one (THEMES, "light,dark" unless set): the site's first entry fetches
// nothing of the landing; the landing fetches the cards once and only the stills near the screen, and no run and no model;
// every card of the file stands on the page with its title and its standing's first words, first words (`standing.first`)
// before anything else of its standing; nothing scrolls sideways; no console error; every card's words read against its
// ground (contrast 4.5 or more); on a phone every control is 44 px or more; the 3D stage draws no frame while the landing
// shows. Then, in the first theme: the keyboard reaches every card in order, with a visible focus; each replay card opens
// its view (the one the card's rule names), the way back stands in one place in every view, clear of the view's other
// controls, and returns to the landing where it was scrolled, with the keyboard on the card it left; a standing's detail
// opens by a press, with its own address, and by that address; the rows' card lists its rows; the not-run line opens the
// view it names.
//
//   node tools/check_landing.mjs [OUT_DIR]
//
// Set by the environment: CASE (wide, 720, phone, narrow, retry), WIDTH, HEIGHT (by the case unless set), THEMES, NAME
// (the pictures' prefix). Chrome is what CHROME names (tools/chrome_gpu.sh for the graphics card), in a place taken
// through tools/lib/browser_lock.mjs; its first page is never judged or pictured.

import { spawn } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { acquireBrowser } from "./lib/browser_lock.mjs";
import { createServer } from "./serve.mjs";
import { DEFAULT_RUNS } from "./lib/build_page.mjs";
import { opensOf, addressOf, standingWords, CARD } from "../src/replay/landing.js";
import { Catalogue } from "../src/replay/catalogue.js";
import { STILL_MARGIN } from "../src/ui/landing.js";

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
  const navigate = async (query, theme = null) => {
    const search = new URLSearchParams(query || "");
    if (theme) search.set("theme", theme);
    await page("Page.navigate", { url: `${base}${search.size ? `?${search}` : ""}` });
    await until(`Boolean(${V}?.model)`, 60000);
  };
  const picture = async (name) => {
    const shot = await page("Page.captureScreenshot", { format: "png" });
    writeFileSync(path.join(OUT, `${NAME}-${name}.png`), Buffer.from(shot.data, "base64"));
  };
  const mouse = (type, x, y) => page("Input.dispatchMouseEvent", { type, x, y, button: "left", buttons: type === "mouseReleased" ? 0 : 1, clickCount: 1 });
  /** A real press at the middle of what `selector` finds in the viewer (its first match, or the one `pick` chooses). */
  const press = async (expression) => {
    const at = await evaluate(`(() => { const el = ${expression}; if (!el) return null; const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
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
  const cardsShown = () => evaluate(`${R}.querySelectorAll(".landing-card").length`);

  // A fresh browser's first page is neither judged nor pictured.
  await navigate("lens=laws");
  await sleep(6000);

  if (CASE === "retry") {
    // While the cards come, the landing says so; refused, it says that, offers to try again, and the rest of the page works.
    hold = "wait";
    await navigate("lens=experiments");
    await sleep(1500);
    const coming = await evaluate(`(() => { const s = ${R}.querySelector(".landing-status"); return { text: s?.textContent || "", hidden: s?.hidden, cards: ${R}.querySelectorAll(".landing-card").length }; })()`);
    check("while the cards' file is on its way, the landing says so", /Fetching/.test(coming.text) && !coming.hidden && coming.cards === 0, JSON.stringify(coming));
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
    const back = await until(`${R}.querySelectorAll(".landing-card").length === ${cards.cards.length}`, 20000);
    check(`on "Try again" the cards come: all ${cards.cards.length} of the file`, back, String(await cardsShown()));
    check("no console error but the refused file's own line", errors.every((line) => /503|cards\.json/.test(line)), errors.join(" | "));
  } else {
    // ------------------------------------------------------------ the site's first entry
    let from = asked.length;
    await navigate("");
    await until(`Boolean(${V}.current)`, 30000);
    await sleep(3000);
    const first = beside(from);
    check("the site's first entry is Scope, and fetches nothing of the landing (cards.json, stills/)", (await evaluate(`${V}.state.lens`)) === "cell" && !first.some((one) => one === "/cards.json" || one.startsWith("/stills/")), first.join(", "));

    for (const [k, theme] of THEMES.entries()) {
      errors.length = 0;
      from = asked.length;
      await navigate("lens=experiments", theme);
      const drawn = await until(`${R}.querySelectorAll(".landing-card").length === ${cards.cards.length}`, 30000);
      await sleep(1500);
      const got = beside(from);
      check(`${theme}: the landing draws every card of the file (${cards.cards.length})`, drawn, String(await cardsShown()));
      check(`${theme}: it fetched the cards once, and no run and no model`, got.filter((one) => one === "/cards.json").length === 1 && !got.some((one) => one.startsWith("/runs/") || one.startsWith("/models/")), got.join(", "));
      // The stills fetched are those near the screen: none whose card lies far below what is in sight.
      const stills = await evaluate(`(() => { const box = ${V}.landingView.box, h = box.clientHeight, top = box.getBoundingClientRect().top; return [...${R}.querySelectorAll(".landing-still")].map((img) => { const r = img.getBoundingClientRect(); return { file: (img.getAttribute("src") || ""), shown: Boolean(img.dataset.shown), top: r.top - top, bottom: r.bottom - top, h, width: img.width, height: img.height, natural: img.naturalWidth }; }); })()`);
      const near = (still) => still.top < still.h + STILL_MARGIN + 4 && still.bottom > -STILL_MARGIN - 4;
      check(`${theme}: the stills near the screen are fetched, and none beyond (${stills.filter((still) => still.shown).length} of ${stills.length})`, stills.every((still) => still.shown === near(still)) && got.filter((one) => one.startsWith("/stills/")).length === stills.filter((still) => still.shown).length, JSON.stringify(stills.map((still) => [still.file, still.shown, Math.round(still.top)])));
      check(`${theme}: each still is the one for the theme, with its size stated`, stills.filter((still) => still.shown).every((still) => still.file.includes(`.${theme}.`) && still.width > 0 && still.height > 0), JSON.stringify(stills.map((still) => still.file)));
      // Every card with its title and its standing's first words; the first words before anything else of its standing.
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
      const expected = cards.bands.flatMap((band) => band.cards).filter((id) => order.includes(id));
      check(`${theme}: the cards stand in the order the file's bands give`, JSON.stringify(order.slice(0, expected.length)) === JSON.stringify(expected), order.join(","));
      // Nothing scrolls sideways; every card inside the window.
      const sideways = await evaluate(`(() => { const box = ${V}.landingView.box; const rects = [...${R}.querySelectorAll(".landing-card, .landing-band-title, .landing-not-run")].map((el) => el.getBoundingClientRect()); return { page: document.documentElement.scrollWidth - innerWidth, box: box.scrollWidth - box.clientWidth, out: rects.filter((r) => r.left < -0.5 || r.right > innerWidth + 0.5).length }; })()`);
      check(`${theme}: nothing scrolls sideways at ${WIDTH} by ${HEIGHT}`, sideways.page <= 0 && sideways.box <= 0 && sideways.out === 0, JSON.stringify(sideways));
      // Every card's words read against its ground.
      const contrast = await evaluate(`(() => {
        const rgb = (text) => { const m = text.match(/rgba?\\(([^)]+)\\)/); if (!m) return null; const [r, g, b, a = 1] = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return { r, g, b, a }; };
        const lum = ({ r, g, b }) => { const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
        const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
        const worst = [];
        for (const card of ${R}.querySelectorAll(".landing-card")) {
          const ground = rgb(getComputedStyle(card).backgroundColor);
          for (const el of card.querySelectorAll(".landing-title, .landing-asks, .landing-first, .landing-says, .landing-level, .landing-answer, .landing-verdict, .landing-scope, .landing-runs, .landing-more")) {
            const ink = rgb(getComputedStyle(el).color);
            if (!ground || !ink) { worst.push([card.dataset.card, el.className, "unread"]); continue; }
            const value = ratio(ink, ground);
            if (value < 4.5) worst.push([card.dataset.card, el.className, Number(value.toFixed(2))]);
          }
        }
        return worst;
      })()`);
      check(`${theme}: every card's words read against its ground (contrast of 4.5 or more)`, !contrast.length, JSON.stringify(contrast.slice(0, 6)));
      if (PHONE) {
        const small = await evaluate(`[...${R}.querySelectorAll(".landing-open, .landing-more, .landing-not-run .link-button, .switch button")].map((el) => [el.className || el.textContent, Math.round(el.getBoundingClientRect().height), Math.round(el.getBoundingClientRect().width)]).filter(([, h, w]) => h < 44 || w < 44)`);
        check(`${theme}: on a phone every control on the landing can be pressed with a thumb (44 px or more)`, !small.length, JSON.stringify(small.slice(0, 6)));
      }
      // The 3D stage draws nothing new while the landing shows.
      const idle = await evaluate(`(async () => { const s = ${V}.stage; if (!s) return { none: true }; await new Promise((r) => setTimeout(r, 600)); const a = s.renderer.info.render.frame; await new Promise((r) => setTimeout(r, 2500)); return { frames: s.renderer.info.render.frame - a, running: s.running, labels: ${R}.querySelectorAll(".labels .label").length, children: s.scene.children.length }; })()`);
      check(`${theme}: the stage draws no frame while the landing shows`, idle.none || (idle.frames === 0 && idle.running === false && idle.labels === 0), JSON.stringify(idle));
      check(`${theme}: no console error`, !errors.length, errors.join(" | "));
      await picture(`${theme}-top`);
      await evaluate(`(() => { const box = ${V}.landingView.box; box.scrollTop = Math.round((box.scrollHeight - box.clientHeight) / 2); })()`);
      await sleep(1500);
      await picture(`${theme}-middle`);
      await evaluate(`(() => { const box = ${V}.landingView.box; box.scrollTop = box.scrollHeight; })()`);
      await sleep(1200);
      await picture(`${theme}-end`);
      if (k > 0) continue;

      // ------------------------------------------------------------ the keyboard, in the first theme
      await evaluate(`${V}.landingView.box.scrollTop = 0`);
      await evaluate(`${V}.indexButton.focus()`);
      const visits = [], unseen = [];
      for (let step = 0; step < cards.cards.length * 2 + 2; step++) {
        await key("Tab");
        const at = await evaluate(`(() => { const el = ${R}.activeElement; const card = el?.closest?.(".landing-card"); if (!card) return null; const target = el.classList.contains("landing-open") ? card : el; const style = getComputedStyle(target); const r = el.getBoundingClientRect(), box = ${V}.landingView.box.getBoundingClientRect(); return { id: card.dataset.card, outline: style.outlineStyle !== "none" && parseFloat(style.outlineWidth) >= 2, inView: r.top >= box.top - 1 && r.bottom <= box.bottom + 1 }; })()`);
        if (!at) continue;
        if (visits.at(-1) !== at.id) visits.push(at.id);
        if (!at.outline || !at.inView) unseen.push(at.id);
      }
      const domOrder = faces.map((face) => face.id);
      check("the keyboard reaches every card in order", JSON.stringify(visits) === JSON.stringify(domOrder), `${visits.length} of ${domOrder.length}: ${visits.slice(0, 6).join(",")}…`);
      check("each with a visible focus, in sight", !unseen.length, unseen.slice(0, 6).join(","));

      // ------------------------------------------------------------ each replay card: its view, and the way back
      const catalogue = await evaluate(`(() => { const r = ${V}.model.raw.replays; return { experiments: r.experiments.map((e) => ({ id: e.id, opens: e.opens, part_of: e.part_of, tissue: e.tissue ? { walk_of: e.tissue.walk_of || null } : undefined })), runs: r.runs.map((x) => ({ id: x.id, experiment: x.experiment, arm: x.arm })), doors: r.doors || [] }; })()`);
      const replays = cards.cards.filter((card) => opensOf(card, catalogue));
      check(`every replay card the page plays has its place on the landing (${replays.length})`, replays.every((card) => byId.has(card.id)) && (await evaluate(`${R}.querySelectorAll(".landing-card.is-replay").length`)) === replays.length);
      let place = null;
      for (const card of replays) {
        const opened = opensOf(card, catalogue);
        await evaluate(`${R}.querySelector('[data-card="${card.id}"]').scrollIntoView({ block: "center" })`);
        await sleep(400);
        const scrolled = await evaluate(`${V}.landingView.box.scrollTop`);
        from = asked.length;
        await press(`${R}.querySelector('[data-card="${card.id}"] .landing-open')`);
        const shown = await until(
          opened.run ? `!${V}.state.landing && ${V}.current?.run?.id === ${JSON.stringify(opened.run)} && !${V}.current.loading` : opened.part ? `!${V}.state.landing && ${V}.state.part === ${JSON.stringify(opened.part)} && ${V}.current?.runs?.length > 0 && !${V}.current.loading` : `!${V}.state.landing && ${V}.state.example === ${JSON.stringify(opened.example)} && Boolean(${V}.current?.player)`,
          60000
        );
        await sleep(1500);
        const view = await evaluate(`(() => { const v = ${V}, root = v.shadowRoot, b = v.backButton.getBoundingClientRect(), seen = (el) => el && !el.hidden && el.getClientRects().length && getComputedStyle(el).display !== "none" ? el.getBoundingClientRect() : null; const meets = (a, c) => Boolean(a && c) && a.left < c.right - 0.5 && c.left < a.right - 0.5 && a.top < c.bottom - 0.5 && c.top < a.bottom - 0.5; const others = [["the folded card", seen(v.viewToggle)], ["the rail", seen(v.railToggle)], ["the card", seen(v.viewCard)]].filter(([, r]) => r); return { back: !v.backButton.hidden, at: [Math.round(b.left), Math.round(b.top)], height: Math.round(b.height), meets: others.filter(([, r]) => meets(b, r)).map(([n]) => n), landingHidden: v.landingView.box.hidden, search: location.search, sideways: document.documentElement.scrollWidth - innerWidth }; })()`);
        const runs = beside(from).filter((one) => one.startsWith("/runs/") || one.startsWith("/models/"));
        check(`${card.id}: a press opens its view (the view's own address: ${addressOf(opened)}), and the page's address names no view and no card's detail`, shown && view.landingHidden && !/[?&](run|part|example|select)=/.test(view.search), JSON.stringify({ shown, search: view.search, runs: runs.length }));
        place ??= view.at;
        check(`${card.id}: the way back stands in its one place, clear of the view's own controls${PHONE ? ", as large as a thumb" : ""}`, view.back && Math.abs(view.at[0] - place[0]) <= 1 && Math.abs(view.at[1] - place[1]) <= 1 && !view.meets.length && (!PHONE || view.height >= 44) && view.sideways <= 0, JSON.stringify(view));
        await picture(`view-${card.id}`);
        await press(`${V}.backButton`);
        const returned = await until(`${V}.state.landing && !${V}.landingView.box.hidden`, 10000);
        await sleep(500);
        const after = await evaluate(`({ top: ${V}.landingView.box.scrollTop, focus: ${R}.activeElement?.closest?.(".landing-card")?.dataset.card || null, search: location.search })`);
        check(`${card.id}: the way back returns to the landing where it was scrolled, the keyboard on the card it left`, returned && Math.abs(after.top - scrolled) <= 2 && after.focus === card.id && !/run=|part=|example=/.test(after.search), JSON.stringify({ scrolled, ...after }));
      }
      // From a part, its networks are its whole's opening run, though the runs' view last held another card's run.
      const partCard = replays.find((card) => opensOf(card, catalogue).part);
      const whole = partCard ? catalogue.experiments.find((item) => item.id === opensOf(partCard, catalogue).part)?.part_of : null;
      const runCard = replays.find((card) => opensOf(card, catalogue).run && catalogue.runs.find((run) => run.id === opensOf(card, catalogue).run)?.experiment !== whole);
      if (partCard && runCard && whole) {
        const networks = new Catalogue(catalogue).openingRun(whole);
        for (const card of [runCard, partCard]) {
          await evaluate(`${R}.querySelector('[data-card="${card.id}"]').scrollIntoView({ block: "center" })`);
          await sleep(300);
          await press(`${R}.querySelector('[data-card="${card.id}"] .landing-open')`);
          await until(`!${V}.state.landing && Boolean(${V}.current) && !${V}.current.loading`, 60000);
          await sleep(1200);
          if (card === runCard) {
            await press(`${V}.backButton`);
            await until(`${V}.state.landing && !${V}.landingView.box.hidden`, 10000);
          }
        }
        if (PHONE && !(await evaluate(`${V}.state.viewOpen`)) && (await evaluate(`!${V}.viewToggle.hidden`))) await press(`${V}.viewToggle`);
        await sleep(500);
        await press(`${R}.querySelector(".view .tissue-back:not(.tissue-sibling)")`);
        const reached = await until(`!${V}.state.part && ${V}.current?.run?.id === ${JSON.stringify(networks)} && Boolean(${V}.current.sheet)`, 60000);
        check(`from ${partCard.id}'s part, its networks' button shows the networks' opening run (${networks}), not ${runCard.id}'s run shown before`, reached, await evaluate(`${V}.current?.run?.id || ${V}.current?.runId || null`));
        await press(`${V}.backButton`);
        await until(`${V}.state.landing && !${V}.landingView.box.hidden`, 10000);
      }
      // A replay card's detail has a door to its view: a press on it opens the view, as the card does.
      const opener = replays[0];
      if (opener) {
        await evaluate(`${R}.querySelector('[data-card="${opener.id}"]').scrollIntoView({ block: "center" })`);
        await sleep(300);
        await press(`${R}.querySelector('[data-card="${opener.id}"] .landing-more')`);
        await until(`!${R}.querySelector("cells-panel").hidden && ${R}.querySelector("cells-panel h2")?.textContent === ${JSON.stringify(opener.title)}`, 10000);
        await sleep(400);
        const door = await evaluate(`[...${R}.querySelectorAll("cells-panel .panel-door button")].find((b) => /Open its replay/.test(b.textContent)) ? true : false`);
        await press(`[...${R}.querySelectorAll("cells-panel .panel-door button")].find((b) => /Open its replay/.test(b.textContent))`);
        const via = await until(`!${V}.state.landing && Boolean(${V}.current) && !${V}.current.loading && ${R}.querySelector("cells-panel").hidden`, 60000);
        check(`a replay card's detail (${opener.id}) has a door to its view, and a press on it opens the view`, door && via);
        await press(`${V}.backButton`);
        await until(`${V}.state.landing && !${V}.landingView.box.hidden`, 10000);
      }
      const rested = await evaluate(`(async () => { const s = ${V}.stage; if (!s) return { none: true }; await new Promise((r) => setTimeout(r, 2500)); const a = s.renderer.info.render.frame; await new Promise((r) => setTimeout(r, 2000)); return { frames: s.renderer.info.render.frame - a, running: s.running, sheet: Boolean(${V}.lenses.get("experiments")?.sheet) }; })()`);
      check("back on the landing the stage is idle again, and the run left lets its drawing go", rested.none || (rested.frames === 0 && !rested.running && !rested.sheet), JSON.stringify(rested));

      // ------------------------------------------------------------ a standing's detail: by a press, and by its address
      const standing = cards.cards.find((card) => card.kind === "standing" && byId.has(card.id) && (card.record || []).some((entry) => entry?.verdict));
      if (standing) {
        await evaluate(`${R}.querySelector('[data-card="${standing.id}"]').scrollIntoView({ block: "center" })`);
        await sleep(400);
        await press(`${R}.querySelector('[data-card="${standing.id}"] .landing-open')`);
        await until(`!${R}.querySelector("cells-panel").hidden`, 10000);
        await sleep(600);
        const panel = await evaluate(`(() => { const p = ${R}.querySelector("cells-panel"); return { title: p.querySelector("h2")?.textContent || "", text: p.textContent, links: [...p.querySelectorAll("a")].map((a) => a.href).filter((href) => /\\/blob\\/[0-9a-f]{40}\\//.test(href)).length, doors: [...p.querySelectorAll(".panel-door button")].map((b) => b.textContent), select: new URL(location.href).searchParams.get("select") }; })()`);
        const counts = (standing.record || []).filter((entry) => entry?.verdict?.count).map((entry) => `${entry.verdict.count.passed} of ${entry.verdict.count.of}`);
        check(`a standing's detail opens by a press (${standing.id}): its title, every count, its sources as links at their revisions, a door to its part on the Engine map, and an address of its own`, panel.title === standing.title && counts.every((count) => panel.text.includes(count)) && panel.links > 0 && panel.doors.some((door) => /Engine map/.test(door)) && panel.select === CARD + standing.id, JSON.stringify({ ...panel, text: panel.text.length }));
        await picture(`detail-${standing.id}`);
        await key("Escape", "Escape", 27);
        await sleep(400);
        check("Escape closes the detail, and the address no longer names it", (await evaluate(`${R}.querySelector("cells-panel").hidden && !new URL(location.href).searchParams.get("select")`)) === true);
        await navigate(`lens=experiments&select=${CARD}${standing.id}`);
        const byAddress = await until(`${R}.querySelector("cells-panel h2")?.textContent === ${JSON.stringify(standing.title)}`, 30000);
        check(`and by its address (select=${CARD}${standing.id})`, byAddress && (await evaluate(`${V}.state.landing`)));
      }
      // The address when the tab is left: a detail's address goes with it, and nothing of the landing's outranks the next
      // tab's #name (the landing writes no lens=): a reload opens the tab pressed.
      if (standing) {
        await page("Page.navigate", { url: `${base}#experiments` });
        await until(`${V}?.state?.landing && ${R}.querySelectorAll(".landing-card").length > 0`, 30000);
        await evaluate(`${R}.querySelector('[data-card="${standing.id}"]').scrollIntoView({ block: "center" })`);
        await sleep(300);
        await press(`${R}.querySelector('[data-card="${standing.id}"] .landing-open')`);
        await until(`!${R}.querySelector("cells-panel").hidden`, 10000);
        const named = await evaluate(`location.search`);
        await press(`${R}.querySelector('.switch [data-lens="cell"]')`);
        await until(`${V}.state.lens === "cell"`, 20000);
        const left = await evaluate(`({ search: location.search, hash: location.hash })`);
        await page("Page.reload", {});
        await until(`Boolean(${V}?.model && ${V}.current)`, 60000);
        const reloaded = await evaluate(`${V}.state.lens`);
        check("the tab left, the address keeps no card's detail and no lens= of the landing's, and a reload opens the tab pressed", new URLSearchParams(named).get("select") === CARD + standing.id && !/[?&](lens|select)=/.test(left.search) && left.hash === "#cell" && reloaded === "cell", JSON.stringify({ named, ...left, reloaded }));
      }
      const rows = cards.cards.find((card) => card.kind === "rows" && byId.has(card.id));
      if (rows) {
        await navigate(`lens=experiments&select=${CARD}${rows.id}`);
        await until(`${R}.querySelector("cells-panel h2")?.textContent === ${JSON.stringify(rows.title)}`, 30000);
        const listed = await evaluate(`(() => { const p = ${R}.querySelector("cells-panel"); const block = [...p.querySelectorAll(".panel-list")].find((el) => /^Its rows/.test(el.querySelector("h4")?.textContent || "")); return block ? [...block.querySelectorAll("li.item")].map((li) => li.textContent) : []; })()`);
        check(`the rows' card lists its ${rows.rows.length} rows, each with its result and its reference`, listed.length === rows.rows.length && rows.rows.every((row, n) => listed[n].includes(row.id) && /Passed|Failed/.test(listed[n]) && listed[n].includes(row.reference.path)), JSON.stringify(listed.map((text) => text.slice(0, 60))));
        await picture(`detail-${rows.id}`);
      }
      // ------------------------------------------------------------ the not-run line
      if (cards.not_run?.lens) {
        await navigate("lens=experiments");
        await until(`${R}.querySelectorAll(".landing-card").length > 0`, 30000);
        const line = await evaluate(`${R}.querySelector(".landing-not-run")?.textContent || ""`);
        await evaluate(`${R}.querySelector(".landing-not-run button")?.scrollIntoView({ block: "center" })`);
        await sleep(300);
        await press(`${R}.querySelector(".landing-not-run button")`);
        const lens = await until(`${V}.state.lens === ${JSON.stringify(cards.not_run.lens)}`, 15000);
        check("the not-run line says where what never ran stands, in the file's words, and opens that view", line === cards.not_run.says && lens, line);
      }
      check("no console error through every view and back", !errors.length, errors.join(" | "));
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
