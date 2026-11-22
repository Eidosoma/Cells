#!/usr/bin/env node
// Pictures each replay card's opening view for the Experiments landing: one still for the light theme and one for the
// dark, JPEG, 640 by 384, each well under 60 KB, into data/replays/stills/, with a record beside them (stills.json: which
// card, which address, its size and checksum, the revision of the page they were made from, and the renderer that drew
// them). What a card opens is read from data/replays/cards.json and the runs folder's catalogue by the page's own rule
// (src/replay/landing.js, opensOf): no card is named here.
//
//   node tools/make_stills.mjs [--runs DIR] [--out DIR] [--only CARD]
//
// A still is the view's picture alone: the page's bar, cards, legend, timeline, the way back and the first-visit line are put out of sight for
// it, and the view stands as an address opens it, held still (`still=1`), at its start. It is cut from the room the page
// leaves the picture (right of the view's card, between the bar and the timeline), at the still's own proportions. One browser makes every still of
// a set, so that one renderer draws them all; its first page is never pictured (a fresh browser's first page is loaded,
// six seconds pass, and only the loads after it are pictured). Chrome is what CHROME names (tools/chrome_gpu.sh for the
// graphics card), in a place taken through tools/lib/browser_lock.mjs. Nothing is fetched from outside the page.
//
// After making them, set each card's `replay.still` in data/replays/cards.source.json to the files the record names
// ({ light, dark, width, height }) and make the cards again (python3 tools/build_cards.py).

import { spawn, execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { acquireBrowser } from "./lib/browser_lock.mjs";
import { hasChanges } from "./lib/git_state.mjs";
import { createServer } from "./serve.mjs";
import { DEFAULT_RUNS, DEFAULT_SCENE, withModelDoors } from "./lib/build_page.mjs";
import { opensOf, addressOf } from "../src/replay/landing.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const value = (name, fallback) => (args.includes(name) ? args[args.indexOf(name) + 1] : fallback);
const RUNS = path.resolve(value("--runs", DEFAULT_RUNS));
const OUT = path.resolve(value("--out", path.join(ROOT, "data", "replays", "stills")));
const ONLY = value("--only", null);
export const FORMAT = "cells.visualizer.landing_stills@1";
const VIEW = { width: 1280, height: 768 }, STILL = { width: 640, height: 384 }, MOST = 60000;
const QUALITIES = [72, 64, 56, 48];
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const cards = JSON.parse(readFileSync(path.join(ROOT, "data", "replays", "cards.json"), "utf8"));
const scene = JSON.parse(readFileSync(DEFAULT_SCENE, "utf8"));
const index = withModelDoors(JSON.parse(readFileSync(path.join(RUNS, "index.json"), "utf8")), scene, cards.listing);
const git = (...words) => execFileSync("git", ["-C", ROOT, ...words], { encoding: "utf8" }).trim();
const revision = git("rev-parse", "HEAD");
// A checkout whose node_modules is a link shows it as untracked: that is no change of the page (tools/lib/git_state.mjs).
const uncommitted = hasChanges(git("status", "--porcelain", "--", "."));

const wanted = cards.cards.filter((card) => card.kind === "replay" && opensOf(card, index) && (!ONLY || card.id === ONLY));
if (!wanted.length) throw new Error("no replay card plays with this runs folder");
mkdirSync(OUT, { recursive: true });

const server = createServer({ offline: true, runs: RUNS, log: () => {} });
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}/`;
const release = await acquireBrowser({ wait: 60 * 60 * 1000 });
const chrome = spawn(process.env.CHROME || "google-chrome", ["--headless=new", `--user-data-dir=${release.profile}`, "--disable-breakpad", "--no-first-run", "--no-sandbox", "--mute-audio", "--hide-scrollbars", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", `--window-size=${VIEW.width},${VIEW.height}`, "--remote-debugging-port=0", "about:blank"], { stdio: ["ignore", "ignore", "pipe"] });
const made = [], renderers = new Set(), problems = [];
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
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.method === "Runtime.exceptionThrown") errors.push(String(message.params.exceptionDetails?.exception?.description || message.params.exceptionDetails?.text).slice(0, 300));
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
  await page("Emulation.setDeviceMetricsOverride", { width: VIEW.width, height: VIEW.height, deviceScaleFactor: 1, mobile: false });
  await page("Page.enable");
  await page("Runtime.enable");
  const evaluate = async (expression) => {
    const reply = await page("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (reply.exceptionDetails) throw new Error(reply.exceptionDetails.exception?.description || reply.exceptionDetails.text);
    return reply.result.value;
  };
  const V = "document.querySelector('cells-viewer')";
  const until = async (expression, ms) => {
    const start = Date.now();
    while (Date.now() - start < ms) {
      if (await evaluate(expression).catch(() => false)) return true;
      await sleep(250);
    }
    return false;
  };
  // A fresh browser's first page is not pictured.
  await page("Page.navigate", { url: `${base}?lens=laws` });
  await sleep(6000);
  for (const card of wanted) {
    const opened = opensOf(card, index);
    const address = addressOf(opened);
    for (const theme of ["light", "dark"]) {
      errors.length = 0;
      await page("Page.navigate", { url: `${base}?${address}&still=1&theme=${theme}` });
      await until(`Boolean(${V}?.model && ${V}.current)`, 60000);
      const ready = await until(
        opened.run ? `${V}.current?.run?.id === ${JSON.stringify(opened.run)} && !${V}.current.loading && !${V}.current.fetching?.size` : opened.part ? `${V}.state.part === ${JSON.stringify(opened.part)} && ${V}.current?.runs?.length > 0 && !${V}.current.loading` : `${V}.state.example === ${JSON.stringify(opened.example)} && Boolean(${V}.current?.player)`,
        90000
      );
      // The room the page leaves the picture, measured before what lies over it is put out of sight.
      const room = await evaluate(`(() => { const v = ${V}, seen = (el) => (el && !el.hidden && el.getClientRects().length ? el.getBoundingClientRect() : null); const card = seen(v.viewCard), timeline = seen(v.timeline); return { left: card && card.left < innerWidth / 3 ? Math.ceil(card.right) + 8 : 0, top: Math.ceil(v.bar.getBoundingClientRect().bottom), right: innerWidth, bottom: timeline ? Math.floor(timeline.top) - 8 : innerHeight }; })()`);
      const wide = room.right - room.left, tall = room.bottom - room.top, aspect = STILL.width / STILL.height;
      const cut = wide / tall > aspect ? { width: tall * aspect, height: tall } : { width: wide, height: wide / aspect };
      const clip = { x: room.left + (wide - cut.width) / 2, y: room.top + (tall - cut.height) / 2, width: cut.width, height: cut.height, scale: STILL.width / cut.width };
      // The picture alone: what the page lays over it is put out of sight, then the picture settles.
      await evaluate(`(() => { const root = ${V}.shadowRoot; const style = document.createElement("style"); style.textContent = ".bar, .card, cells-legend, cells-timeline, cells-panel, cells-index, .hint, .caveat, .view-toggle, .rail-toggle, .scalebar, .exp-back, .sweep-card, .look-box, .fallback, .intro { visibility: hidden !important; }"; root.append(style); ${V}.stage?.invalidate(); })()`);
      await sleep(3500);
      const state = await evaluate(`(() => { const v = ${V}, gl = v.stage?.renderer.getContext(), info = gl?.getExtension("WEBGL_debug_renderer_info"); return { renderer: info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl ? gl.getParameter(gl.RENDERER) : null, status: v.current?.chrome?.()?.status || null, error: v.current?.error || null, lost: gl?.isContextLost?.() || false }; })()`);
      if (!ready || state.status || state.error || state.lost || errors.length) {
        problems.push(`${card.id} (${theme}): ${!ready ? "its view did not open" : state.status || state.error || (state.lost ? "the graphics context was lost" : errors.join(" | "))}`);
        continue;
      }
      renderers.add(state.renderer);
      let shot = null, quality = null;
      for (quality of QUALITIES) {
        shot = Buffer.from((await page("Page.captureScreenshot", { format: "jpeg", quality, clip })).data, "base64");
        if (shot.length < MOST) break;
      }
      if (shot.length >= MOST) {
        problems.push(`${card.id} (${theme}): ${shot.length} bytes even at quality ${quality}`);
        continue;
      }
      const file = `${card.id}.${theme}.jpg`;
      writeFileSync(path.join(OUT, file), shot);
      made.push({ card: card.id, theme, address, file: `stills/${file}`, width: STILL.width, height: STILL.height, cut: { x: Math.round(clip.x), y: Math.round(clip.y), width: Math.round(clip.width), height: Math.round(clip.height) }, quality, bytes: shot.length, sha256: createHash("sha256").update(shot).digest("hex") });
      console.log(`${file}: ${shot.length} bytes, quality ${quality}, ${address}`);
    }
  }
} finally {
  chrome.kill("SIGTERM");
  await new Promise((resolve) => {
    chrome.once("exit", resolve);
    setTimeout(resolve, 8000);
  });
  release();
  server.close();
}
if (renderers.size > 1) problems.push(`more than one renderer drew this set: ${[...renderers].join("; ")}`);
if (problems.length) {
  for (const problem of problems) console.error(`refused: ${problem}`);
  console.error("no record written: make the set again");
  process.exit(1);
}
const recordFile = path.join(OUT, "stills.json");
const previous = ONLY && existsSync(recordFile) ? JSON.parse(readFileSync(recordFile, "utf8")) : null;
const kept = (previous?.stills || []).filter((still) => still.card !== ONLY);
const capture = { made: new Date().toISOString().slice(0, 10), page: { revision, uncommitted }, renderer: [...renderers][0] };
// Existing images retain their original capture information when a new card is pictured separately.
const current = kept.length ? made.map((still) => ({ ...still, ...capture })) : made;
const record = {
  ...(kept.length ? previous : {
    format: FORMAT,
    note: "Light and dark stills of the opening replay, captured by tools/make_stills.mjs. The cut is in window pixels. A still captured separately records its own date, page revision and renderer.",
    ...capture,
    view: VIEW,
  }),
  stills: [...kept, ...current].sort((a, b) => cards.cards.findIndex((card) => card.id === a.card) - cards.cards.findIndex((card) => card.id === b.card) || a.theme.localeCompare(b.theme)),
};
writeFileSync(recordFile, JSON.stringify(record, null, 1) + "\n");
console.log(`wrote ${made.length} stills and ${path.relative(ROOT, recordFile)}; drawn by ${capture.renderer}`);
for (const name of new Set(record.stills.map((still) => still.card))) {
  const light = record.stills.find((still) => still.card === name && still.theme === "light"), dark = record.stills.find((still) => still.card === name && still.theme === "dark");
  console.log(`  ${name}: "still": ${JSON.stringify({ light: light?.file, dark: dark?.file, width: light?.width, height: light?.height })}`);
}
