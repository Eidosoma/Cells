#!/usr/bin/env node
// Pictures the page's own 3D scene for links shared elsewhere (the site's og:image, tools/stage_site.mjs): 1200 by 630, a
// JPEG of at most 200 kB, with no words at all. Everything the page lays over its picture is put out of sight for the
// shot (the bar, the cards, the panel, the labels, the line, the notes: every child of the viewer's frame but its stage,
// and everything inside the stage but its canvas), the room the page keeps for its cards is given back to the picture, and the
// marks a view writes into the scene itself as text (the charge signs on a membrane, an Engine view gate's number:
// sprites painted from words, src/core/materials.js glyphSprite) are put away. A view that writes names on its shelves or
// trays (the Laws library, the Machines catalogue) is not for this picture. The camera is the address's own (`azimuth`,
// `polar`, `distance`), so that the same address makes the same picture again.
//
//   node tools/make_share.mjs --plan PLAN.json --out DIR      PLAN: [{ name, address, theme }]
//
// The page is drawn at twice the picture's size and scaled down to it. One browser makes every picture of a plan, through
// CHROME (tools/chrome_gpu.sh); its first page is never pictured. Into DIR go <name>.jpg and share-candidates.json (each
// picture's address, theme, quality, bytes, SHA-256, and the renderer that drew them all). Nothing is fetched from outside.

import { spawn, execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { acquireBrowser } from "./lib/browser_lock.mjs";
import { createServer } from "./serve.mjs";
import { ROOT } from "./lib/build_page.mjs";
import { hasChanges } from "./lib/git_state.mjs";

const args = process.argv.slice(2);
const value = (name, fallback) => (args.includes(name) ? args[args.indexOf(name) + 1] : fallback);
const PLAN = JSON.parse(readFileSync(path.resolve(value("--plan")), "utf8"));
const OUT = path.resolve(value("--out"));
export const SHARE = { width: 1200, height: 630, most: 200_000 };
const QUALITIES = [90, 86, 82, 78, 74, 70, 66, 62];
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const git = (...words) => execFileSync("git", ["-C", ROOT, ...words], { encoding: "utf8" }).trim();
mkdirSync(OUT, { recursive: true });

const server = createServer({ offline: true, log: () => {} });
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}/`;
const release = await acquireBrowser({ wait: 60 * 60 * 1000 });
const chrome = spawn(process.env.CHROME || "google-chrome", ["--headless=new", `--user-data-dir=${release.profile}`, "--disable-breakpad", "--no-first-run", "--no-sandbox", "--mute-audio", "--hide-scrollbars", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", `--window-size=${SHARE.width},${SHARE.height}`, "--remote-debugging-port=0", "about:blank"], { stdio: ["ignore", "ignore", "pipe"] });
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
  // Drawn at twice the picture's size, and scaled down to it: the edges come out smooth.
  await page("Emulation.setDeviceMetricsOverride", { width: SHARE.width, height: SHARE.height, deviceScaleFactor: 2, mobile: false });
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
  for (const shot of PLAN) {
    errors.length = 0;
    const theme = shot.theme === "dark" ? "dark" : "light";
    await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: theme }] });
    const url = new URL(shot.address, base);
    url.searchParams.set("still", "1");
    url.searchParams.set("theme", theme);
    await page("Page.navigate", { url: url.href });
    const ready = await until(`Boolean(${V}?.model && ${V}.current && ${V}.stage)`, 90000);
    // Settled: nothing loading, fetching or in flight (a view that moves by itself, as the resting look does, may go on moving).
    const settled = `${V}.busy().filter((reason) => !/moving|frame is owed/.test(reason)).length === 0`;
    await until(settled, 60000);
    await evaluate(`Promise.race([Promise.resolve(${V}.current?.ready), new Promise((done) => setTimeout(done, 30000))]).then(() => true)`).catch(() => null);
    // Everything over the picture out of sight, its room given back, and the words the scene paints put away.
    const put = await evaluate(`(() => {
      const v = ${V}, root = v.shadowRoot, style = document.createElement("style");
      style.textContent = ".frame > :not(.stage), .stage > :not(canvas) { display: none !important; }";
      root.append(style);
      document.getElementById("cells-text")?.setAttribute("hidden", "");
      v.stage.setInsets({});
      let sprites = 0;
      v.stage.scene.traverse((object) => { if (object.isSprite && object.visible) { object.visible = false; sprites++; } });
      v.current?.roomChanged?.();
      v.stage.invalidate();
      return { sprites, shown: [...root.querySelector(".frame").children].filter((el) => getComputedStyle(el).display !== "none").map((el) => el.className) };
    })()`);
    await sleep(2500);
    await until(settled, 30000);
    await sleep(1500);
    const state = await evaluate(`(() => { const v = ${V}, gl = v.stage?.renderer.getContext(), info = gl?.getExtension("WEBGL_debug_renderer_info"); const rig = v.stage?.rig; return { renderer: info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl ? gl.getParameter(gl.RENDERER) : null, lost: gl?.isContextLost?.() || false, status: v.current?.chrome?.()?.status || null, camera: rig ? { azimuth: +rig.azimuth.toFixed(3), polar: +rig.polar.toFixed(3), distance: +rig.distance.toFixed(2) } : null }; })()`);
    if (!ready || state.lost || state.status || errors.length) {
      problems.push(`${shot.name}: ${!ready ? "its view did not open" : state.lost ? "the graphics context was lost" : state.status || errors.join(" | ")}`);
      console.log(`${shot.name}: refused (${problems.at(-1)})`);
      continue;
    }
    renderers.add(state.renderer);
    let shotBytes = null, quality = null;
    for (quality of QUALITIES) {
      shotBytes = Buffer.from((await page("Page.captureScreenshot", { format: "jpeg", quality, clip: { x: 0, y: 0, width: SHARE.width, height: SHARE.height, scale: 0.5 } })).data, "base64");
      if (shotBytes.length <= SHARE.most) break;
    }
    if (shotBytes.length > SHARE.most) {
      problems.push(`${shot.name}: ${shotBytes.length} bytes even at quality ${quality}`);
      continue;
    }
    const file = `${shot.name}.jpg`;
    writeFileSync(path.join(OUT, file), shotBytes);
    made.push({ name: shot.name, file, address: shot.address, theme, width: SHARE.width, height: SHARE.height, drawn_at: 2, quality, bytes: shotBytes.length, sha256: createHash("sha256").update(shotBytes).digest("hex"), camera: state.camera, put_away: { sprites: put.sprites, left_shown: put.shown } });
    console.log(`${file}: ${shotBytes.length} bytes, quality ${quality}, ${put.sprites} sprites put away, camera ${JSON.stringify(state.camera)}, ${shot.address} (${theme})`);
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
const record = {
  format: "cells.visualizer.share_candidates@1",
  note: "Pictures of the page's own 3D scene for links shared elsewhere, made by tools/make_share.mjs: each address drawn in a window of 1200 by 630 at twice its size and scaled down, with everything over the picture put out of sight and the scene's painted words put away. Not edited by hand.",
  made: new Date().toISOString().slice(0, 10),
  page: { revision: git("rev-parse", "HEAD"), uncommitted: hasChanges(git("status", "--porcelain", "--", ".")) },
  renderer: [...renderers][0] || null,
  pictures: made,
};
writeFileSync(path.join(OUT, "share-candidates.json"), JSON.stringify(record, null, 1) + "\n");
for (const problem of problems) console.error(`refused: ${problem}`);
console.log(`wrote ${made.length} pictures and share-candidates.json; drawn by ${record.renderer}`);
process.exit(problems.length ? 1 : 0);
