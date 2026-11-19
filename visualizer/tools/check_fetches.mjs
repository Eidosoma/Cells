#!/usr/bin/env node
// What each address of the published page fetches beside the page, each loaded cold, held to the budgets in
// tools/references/fetches.json (judged by tools/lib/fetch_budget.mjs): the files it must fetch, the files it may
// fetch (by pattern) and a bound in bytes. A visitor's browser loads the page itself at every address; beside it,
// an address fetches only what it draws. The page must never load every experiment at once.
//
//   node tools/check_fetches.mjs [OUT_DIR]
//
// Set by the environment:
//   CASE   listed (the only case since 18 November 2026): the page exported as the Experiments landing lists its
//          experiments (the cards' `listing`), which is every experiment the landing has a card for. Until then a second
//          case (`all`) exported with every experiment listed; the export now keys on the cards, so the two were one.
//   RUNS   the runs folder to export from (the export's own default unless given).
//   OVERLAY  the catalogue's overlay the export reads for how the runs' parts are published (its own default unless given).
//   PAGE   a page already exported (artifact content), checked in place of a new export, with the list of files its
//          export wrote beside it (cells-architecture.files.json in the same folder).
//   NAME   what its files in OUT_DIR are called (fetches-<case> unless given).
//   TABLE  another table of budgets, in the same form (to try new rows before they go into the tracked one).
//   KEEP   1 keeps the export's files of several parts in OUT_DIR (else removed at the end).
//
// The page is served as it is published: wrapped in the artifact's document, under a policy close to its frame's,
// each file the export lists at its published path. three.js comes from node_modules in place of its CDN, and every
// other address outside this server is blocked in the browser: nothing is downloaded. Into OUT_DIR go the export and
// NAME.json: for each address, every file it fetched with its size.
//
// One browser: it takes a place of the lock in tools/lib/browser_lock.mjs. Start Chrome through tools/chrome_gpu.sh
// (CHROME=$PWD/tools/chrome_gpu.sh), as every browser run here.

import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { acquireBrowser } from "./lib/browser_lock.mjs";
import { ROOT, DEFAULT_RUNS, THREE_CDN, THREE_LOCAL, contentSecurityPolicy, wrap } from "./lib/build_page.mjs";
import { addressesOf, judge, tableProblems } from "./lib/fetch_budget.mjs";

const OUT = path.resolve(process.argv[2] || path.join(ROOT, "out", "check-fetches"));
const CASE = process.env.CASE || "listed";
if (CASE !== "listed") throw new Error(`no case ${CASE}: listed (the export publishes what the landing's cards list)`);
const NAME = process.env.NAME || `fetches-${CASE}`;
const TABLE = process.env.TABLE ? path.resolve(process.env.TABLE) : path.join(ROOT, "tools", "references", "fetches.json");
const WIDTH = 1280, HEIGHT = 720;
const QUIET_MS = 3000; // an address has settled when the page has asked for nothing more for this long
const LEAST_MS = 4000; // and not before this long after it was opened
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const results = [];
const check = (name, ok, detail = "") => {
  results.push(Boolean(ok));
  console.log(`${ok ? "pass" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`);
};
const note = (text) => console.log(`note  ${text}`);
const megabytes = (bytes) => `${(bytes / 1e6).toFixed(2)} MB`;

// ---------------------------------------------------------------- the page, exported
const folder = path.join(OUT, NAME);
await mkdir(folder, { recursive: true });
let pagePath = process.env.PAGE ? path.resolve(process.env.PAGE) : path.join(folder, "cells-architecture.html");
if (!process.env.PAGE) {
  const runs = process.env.RUNS ? path.resolve(process.env.RUNS) : DEFAULT_RUNS;
  if (!existsSync(path.join(runs, "index.json"))) {
    // A fresh checkout has no runs until they are adapted (README, "Experiment replays"): nothing to check, said as such.
    console.log(`skip  the runs folder holds no catalogue (${path.basename(runs)}/index.json): make the replays first`);
    console.log("0 of 0 checks passed");
    process.exit(0);
  }
  const made = spawnSync(process.execPath, [path.join(ROOT, "tools", "export_page.mjs"), "--out", pagePath, "--runs", runs, ...(process.env.OVERLAY ? ["--overlay", path.resolve(process.env.OVERLAY)] : [])], { cwd: ROOT, encoding: "utf8" });
  const said = `${made.stdout || ""}${made.stderr || ""}`;
  await writeFile(path.join(folder, "export.log"), said);
  if (made.status !== 0) {
    console.log(said.split("\n").slice(-12).join("\n"));
    check("the page is exported", false, `the export ended with ${made.status}`);
    console.log(`0 of 1 checks passed`);
    process.exit(1);
  }
  note(said.split("\n").filter((line) => /^wrote /.test(line)).join("; "));
}
const content = await readFile(pagePath, "utf8");
const listPath = path.join(path.dirname(pagePath), "cells-architecture.files.json");
const beside = existsSync(listPath) ? JSON.parse(await readFile(listPath, "utf8")) : {};
const sources = new Map(Object.entries(beside).map(([published, source]) => [published, path.resolve(ROOT, source)]));
const sizes = new Map();
for (const [published, source] of sources) sizes.set(published, (await stat(source)).size);
const pageBytes = Buffer.byteLength(content);
const besideBytes = [...sizes.values()].reduce((sum, bytes) => sum + bytes, 0);
note(`the published page holds ${sources.size + 1} files, the page among them, and ${megabytes(pageBytes + besideBytes)} (the page ${megabytes(pageBytes)})`);
// The page's scene, as the viewer reads it: the first script of JSON inside the viewer's element.
const scene = JSON.parse(/<cells-viewer[^>]*>[\s\S]*?<script type="application\/json">([\s\S]*?)<\/script>/.exec(content)?.[1] || "{}");

// ---------------------------------------------------------------- the table
const table = JSON.parse(await readFile(TABLE, "utf8"));
const wrong = tableProblems(table);
check("the table of budgets is whole", !wrong.length, wrong.slice(0, 4).join("; "));
if (table.page_bytes) check(`the page itself is within its bound (${megabytes(table.page_bytes)})`, pageBytes <= table.page_bytes, megabytes(pageBytes));
const { rows, skipped, problems } = addressesOf(table, scene.replays);
check("every experiment the page carries has a budget", !problems.length, problems.join("; "));
for (const line of skipped) note(`not loaded: ${line}`);

// ---------------------------------------------------------------- served as published
const page = wrap(content.replaceAll(THREE_CDN, THREE_LOCAL));
const asked = [];
const server = http.createServer(async (request, response) => {
  const url = new URL(request.url, "http://localhost");
  if (url.pathname === "/") {
    response.writeHead(200, { "content-type": "text/html; charset=utf-8", "content-security-policy": contentSecurityPolicy({ local: true }), "cache-control": "no-store" }).end(page);
    return;
  }
  if (url.pathname === THREE_LOCAL) {
    response.writeHead(200, { "content-type": "text/javascript", "cache-control": "no-store" }).end(await readFile(path.join(ROOT, "node_modules", "three", "build", "three.module.min.js")));
    return;
  }
  if (url.pathname === "/favicon.ico") return response.writeHead(404).end();
  const published = decodeURIComponent(url.pathname.slice(1));
  const source = sources.get(published);
  if (!source) {
    asked.push({ path: published, bytes: 0, status: 404 });
    response.writeHead(404).end("not found");
    return;
  }
  asked.push({ path: published, bytes: sizes.get(published), status: 200 });
  response.writeHead(200, { "content-type": published.endsWith(".json") ? "application/json" : /\.jpe?g$/.test(published) ? "image/jpeg" : published.endsWith(".png") ? "image/png" : "application/octet-stream", "cache-control": "no-store" }).end(await readFile(source));
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}/`;

// ---------------------------------------------------------------- the browser
const release = await acquireBrowser({ wait: Number(process.env.WAIT_MINUTES || 30) * 60 * 1000 });
const chrome = spawn(
  process.env.CHROME || "google-chrome",
  ["--headless=new", `--user-data-dir=${release.profile}`, "--disable-breakpad", "--no-first-run", "--no-sandbox", "--mute-audio", "--hide-scrollbars", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", `--window-size=${WIDTH},${HEIGHT}`, "--remote-debugging-port=0", "about:blank"],
  { stdio: ["ignore", "ignore", "pipe"] }
);
const record = { format: "cells.visualizer.fetch_record@1", case: CASE, page_bytes: pageBytes, published_files: sources.size + 1, published_bytes: pageBytes + besideBytes, addresses: [] };
let failed = null, socket = null;
try {
  const endpoint = await new Promise((resolve, reject) => {
    let text = "";
    chrome.stderr.on("data", (chunk) => {
      text += chunk;
      const match = text.match(/DevTools listening on (ws:\/\/\S+)/);
      if (match) resolve(match[1]);
    });
    setTimeout(() => reject(new Error("Chrome did not report a DevTools address")), 60000);
  });
  socket = new WebSocket(endpoint);
  await new Promise((resolve, reject) => ((socket.onopen = resolve), (socket.onerror = reject)));
  let nextId = 1;
  const waiting = new Map(), outside = [], errors = [];
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    // Every request is held as it starts: one to this server goes on, any other is refused here and said, never fetched.
    if (message.method === "Fetch.requestPaused") {
      const { requestId, request } = message.params;
      const local = request.url.startsWith(base) || !/^https?:/.test(request.url);
      if (!local) outside.push(request.url);
      socket.send(JSON.stringify({ id: nextId++, method: local ? "Fetch.continueRequest" : "Fetch.failRequest", params: local ? { requestId } : { requestId, errorReason: "BlockedByClient" }, sessionId: message.sessionId }));
      return;
    }
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
  const tab = (method, params) => send(method, params, sessionId);
  await tab("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: HEIGHT, deviceScaleFactor: 1, mobile: false });
  await tab("Page.enable");
  await tab("Runtime.enable");
  await tab("Network.enable");
  await tab("Network.setCacheDisabled", { cacheDisabled: true });
  await tab("Fetch.enable", { patterns: [{ urlPattern: "*" }] });
  const evaluate = async (expression) => {
    const reply = await tab("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (reply.exceptionDetails) throw new Error(reply.exceptionDetails.exception?.description || reply.exceptionDetails.text);
    return reply.result.value;
  };
  const V = "document.querySelector('cells-viewer')";
  /** Open an address cold and wait until it has settled: its view ready, nothing fetching, and the page quiet. */
  const open = async (query) => {
    await tab("Page.navigate", { url: "about:blank" });
    await sleep(300);
    asked.length = 0;
    outside.length = 0;
    errors.length = 0;
    const opened = Date.now();
    await tab("Page.navigate", { url: query ? `${base}?${query}` : base });
    let ready = false;
    for (let tries = 0; tries < 480 && !ready; tries++) {
      await sleep(250);
      ready = await evaluate(`Boolean(${V}?.model && (${V}.current || !${V}.stage))`).catch(() => false);
    }
    await evaluate(`Promise.race([Promise.resolve(${V}?.current?.ready), new Promise((done) => setTimeout(done, 60000))]).then(() => true)`).catch(() => null);
    let count = -1, since = Date.now();
    while (Date.now() - opened < 120000) {
      const busy = await evaluate(`Boolean(${V}?.current?.loading || ${V}?.current?.fetching?.size)`).catch(() => false);
      if (asked.length !== count || busy) {
        count = asked.length;
        since = Date.now();
      } else if (Date.now() - since >= QUIET_MS && Date.now() - opened >= LEAST_MS) break;
      await sleep(250);
    }
    return ready;
  };
  // A first page of a fresh browser is not judged (a fresh browser's first context on the card is lost and made again).
  await open("lens=laws");
  await sleep(2000);
  for (const row of rows) {
    const ready = await open(row.query);
    const files = asked.map((file) => ({ ...file }));
    const { total, problems: found } = judge(row, files);
    const shown = await evaluate(`(() => { const v = ${V}, lens = v?.current; return { lens: v?.state?.lens || null, run: lens?.run?.id || null, part: v?.state?.part || null, example: v?.state?.example || null }; })()`).catch(() => ({}));
    check(`${row.id} (${row.query || "no query"}): only files it may fetch, and its bound of ${megabytes(row.bytes)} held (${files.length} files, ${megabytes(total)})`, ready && !found.length, [ready ? null : "the page did not open", ...found].filter(Boolean).join("; "));
    for (const file of files) note(`  ${file.status === 200 ? "" : `${file.status} `}${file.path}  ${file.bytes} bytes`);
    if (row.kind === "experiment") check(`${row.id}: the address shows the run it names`, shown.run === row.run, JSON.stringify(shown));
    if (outside.length) note(`  asked outside this server (blocked here): ${[...new Set(outside.map((url) => new URL(url).host))].join(", ")}`);
    if (errors.length) note(`  page errors: ${errors.slice(0, 3).join(" | ")}`);
    record.addresses.push({ id: row.id, kind: row.kind, query: row.query, bound: row.bytes, files: files.length, bytes: total, shown, list: files.map((file) => [file.path, file.bytes, file.status]), problems: found });
  }
} catch (error) {
  failed = error;
} finally {
  try {
    socket?.close();
  } catch {}
  chrome.kill("SIGTERM");
  await new Promise((resolve) => {
    chrome.once("exit", resolve);
    setTimeout(resolve, 8000);
  });
  release();
  server.close();
}
await writeFile(path.join(OUT, `${NAME}.json`), JSON.stringify(record, null, 1) + "\n");
// What the export wrote beside the page (the runs' parts, tens of MB with every experiment listed) is not kept, unless KEEP=1.
if (!process.env.PAGE && !process.env.KEEP) for (const name of ["cells-architecture.runs"]) await rm(path.join(folder, name), { recursive: true, force: true });
note(`wrote ${path.relative(ROOT, path.join(OUT, `${NAME}.json`))}`);
if (failed) {
  console.error(failed.stack || String(failed));
  check("the checks ran to their end", false, String(failed.message || failed).slice(0, 200));
}
console.log(`${results.filter(Boolean).length} of ${results.length} checks passed`);
process.exit(results.every(Boolean) ? 0 : 1);
