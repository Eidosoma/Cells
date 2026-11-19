#!/usr/bin/env node
// The site's acceptance check (docs/HOSTING_AND_API.md, section 10): a visit to a release asks no host but the site's own.
//
//   node tools/check_site.mjs --site SITE [--id v49] [--out DIR]
//
// SITE is a site folder as tools/stage_site.mjs writes it (SITE/r/<id>/, and SITE/index.html, the pointer, once one is
// moved). The check comes before the pointer moves: the root page is served from r/<id>/root.html, which --release
// copies over the pointer byte for byte, with its compressed copies where the release has them. The rest of SITE is served
// on 127.0.0.1 as a plain file server serves it (deploy/caddy/site.caddy is the example): index.html for a folder's
// address whatever the query string, a release's compressed copies (.br, .gz) where the request accepts them, other
// HTML, JSON, JavaScript and CSS compressed as they are sent (gzip), the site's content policy (stage_site.mjs,
// sitePolicy) and its cache headers. Then the root page and /r/<id>/ are each opened cold in headless Chrome at three
// addresses (the opening view, ?lens=machines&species=human, ?lens=experiments), and each holds:
//   - no request goes to any host but the site's own (any other is refused in the browser and said: nothing is fetched);
//   - no file is missing (every answer of the server is 200), and the page's two fonts arrive from the site;
//   - no console error and no exception;
//   - the viewer read its host profile, and its base address is the release's folder;
//   - a press on another tab keeps the address where it was (the root at the root, not inside the release's folder);
// and the bytes as sent stand beside the raw bytes, and beside what brotli's and gzip's copies would send, for each first
// visit. The browser's own request for /favicon.ico (no page asks for it) is said apart. --id is the release the pointer
// on disk names unless given. Into DIR (out/check-site unless given) goes site-check.json.
//
// One browser: it takes a place of the lock in tools/lib/browser_lock.mjs. Start Chrome through tools/chrome_gpu.sh
// (CHROME=$PWD/tools/chrome_gpu.sh), as every browser run here; the first page of the fresh browser is not judged.

import { spawn } from "node:child_process";
import { createReadStream, existsSync } from "node:fs";
import { mkdir, readFile, stat, writeFile } from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import zlib from "node:zlib";
import { acquireBrowser } from "./lib/browser_lock.mjs";
import { ROOT } from "./lib/build_page.mjs";
import { COMPRESSIBLE, contentType, sitePolicy } from "./stage_site.mjs";

const args = process.argv.slice(2);
const value = (name, fallback) => (args.includes(name) ? args[args.indexOf(name) + 1] : fallback);
const SITE = value("--site") ? path.resolve(value("--site")) : null;
if (!SITE || !existsSync(path.join(SITE, "r"))) {
  console.error("usage: node tools/check_site.mjs --site SITE [--id ID] [--out DIR]  (SITE holds r/<id>/, and index.html once a pointer is moved)");
  process.exit(2);
}
const OUT = path.resolve(value("--out", path.join(ROOT, "out", "check-site")));
const pointer = existsSync(path.join(SITE, "index.html")) ? /<script type="application\/json" id="cells-host">([\s\S]*?)<\/script>/.exec(await readFile(path.join(SITE, "index.html"), "utf8"))?.[1] : undefined;
const pointed = pointer ? JSON.parse(pointer).release ?? null : pointer === undefined ? undefined : null;
const ID = value("--id", pointed ?? null);
if (!ID || !existsSync(path.join(SITE, "r", ID, "release.json"))) {
  console.error(`no release ${ID} in the site's r/ (give --id)`);
  process.exit(2);
}
// The root page is checked as it will stand once the pointer names this release: its root.html, which --release copies
// over SITE/index.html byte for byte, sent as its compressed copy where the release has one. So a release is checked before
// the pointer moves to it, and the pointer on disk, whatever it names, is not read.
const ROOT_PAGE = path.join(SITE, "r", ID, "root.html");
const WIDTH = 1280, HEIGHT = 720;
const QUIET_MS = 3000, LEAST_MS = 4000; // as tools/check_fetches.mjs: settled when nothing more is asked for this long
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const results = [];
const check = (name, ok, detail = "") => {
  results.push(Boolean(ok));
  console.log(`${ok ? "pass" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`);
};
const note = (text) => console.log(`note  ${text}`);
const kb = (bytes) => `${(bytes / 1e3).toFixed(1)} kB`;
const began = Date.now();

// ---------------------------------------------------------------- the site, served as a plain file server serves it
const asked = [];
const encodings = new Set();
const sizeOf = async (file) => (existsSync(file) ? (await stat(file)).size : null);
const server = http.createServer(async (request, response) => {
  const url = new URL(request.url, "http://localhost");
  let name;
  try {
    name = decodeURIComponent(url.pathname);
  } catch {
    return response.writeHead(400).end();
  }
  if (name.split("/").some((part) => part === ".." || part.startsWith(".")) || name.includes("\0")) return response.writeHead(404).end();
  if (name.endsWith("/")) name += "index.html";
  const isPointer = name === "/index.html";
  const file = isPointer ? ROOT_PAGE : path.join(SITE, name);
  const found = await stat(file).catch(() => null);
  const row = { path: url.pathname, query: url.search, status: 404, raw: 0, sent: 0, encoding: null, br: null, gz: null };
  asked.push(row);
  if (!found?.isFile()) return response.writeHead(404, { "content-type": "text/plain" }).end("not found");
  const accept = String(request.headers["accept-encoding"] || "");
  encodings.add(accept);
  const accepts = (kind) => new RegExp(`(^|[\\s,])${kind}($|[\\s,;])`).test(accept);
  const headers = {
    "content-type": contentType(file),
    "cache-control": name.startsWith("/r/") ? "public, max-age=31536000, immutable" : "no-cache",
    "x-content-type-options": "nosniff",
  };
  if (name.endsWith(".html")) headers["content-security-policy"] = sitePolicy();
  row.status = 200;
  row.raw = found.size;
  // What brotli's and gzip's copies would send: the release's own copy, or for the pointer its root.html's.
  [row.br, row.gz] = [await sizeOf(`${file}.br`), await sizeOf(`${file}.gz`)];
  if (COMPRESSIBLE.test(name)) headers.vary = "Accept-Encoding";
  for (const kind of ["br", "gz"]) {
    const copy = `${file}.${kind}`;
    // The pointer too: --release copies the release's root.html.br and .gz beside it.
    if (COMPRESSIBLE.test(name) && accepts(kind === "gz" ? "gzip" : "br") && existsSync(copy)) {
      row.encoding = kind === "gz" ? "gzip" : "br";
      row.sent = (await stat(copy)).size;
      response.writeHead(200, { ...headers, "content-encoding": row.encoding, "content-length": row.sent });
      createReadStream(copy).pipe(response);
      return;
    }
  }
  if (COMPRESSIBLE.test(name) && accepts("gzip")) {
    // No copy beside it (a release staged without --compress): compressed as it is sent, as a server's own compression does.
    const body = zlib.gzipSync(await readFile(file), { level: 6 });
    row.encoding = "gzip, as sent";
    row.sent = body.length;
    response.writeHead(200, { ...headers, "content-encoding": "gzip", "content-length": body.length }).end(body);
    return;
  }
  row.sent = found.size;
  response.writeHead(200, { ...headers, "content-length": found.size });
  createReadStream(file).pipe(response);
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
note(`serving ${path.basename(SITE)} at ${origin}/ (release ${ID}), until the check ends`);
note(`the root page is r/${ID}/root.html, as --release would copy it; the pointer on disk ${pointed === undefined ? "is not there yet" : pointed === ID ? `names ${ID} already` : `names ${pointed ?? "no release"}, and is not read`}`);

// ---------------------------------------------------------------- the browser
const release = await acquireBrowser({ wait: Number(process.env.WAIT_MINUTES || 30) * 60 * 1000 });
const chrome = spawn(
  process.env.CHROME || "google-chrome",
  ["--headless=new", `--user-data-dir=${release.profile}`, "--disable-breakpad", "--no-first-run", "--no-sandbox", "--mute-audio", "--hide-scrollbars", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", `--window-size=${WIDTH},${HEIGHT}`, "--remote-debugging-port=0", "about:blank"],
  { stdio: ["ignore", "ignore", "pipe"] }
);
const record = { format: "cells.visualizer.site_check@1", site: path.basename(SITE), release: ID, policy: sitePolicy(), visits: [] };
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
  const waiting = new Map(), hosts = [], outside = [], errors = [];
  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    // Every request is held as it starts: one to the site goes on, any other is refused here and said, never fetched.
    if (message.method === "Fetch.requestPaused") {
      const { requestId, request } = message.params;
      const own = request.url.startsWith(`${origin}/`);
      if (/^https?:/.test(request.url)) hosts.push(new URL(request.url).host);
      if (!own && /^https?:/.test(request.url)) outside.push(request.url);
      socket.send(JSON.stringify({ id: nextId++, method: own || !/^https?:/.test(request.url) ? "Fetch.continueRequest" : "Fetch.failRequest", params: own || !/^https?:/.test(request.url) ? { requestId } : { requestId, errorReason: "BlockedByClient" }, sessionId: message.sessionId }));
      return;
    }
    if (message.method === "Runtime.exceptionThrown") errors.push(`exception: ${String(message.params.exceptionDetails?.exception?.description || message.params.exceptionDetails?.text).slice(0, 300)}`);
    if (message.method === "Runtime.consoleAPICalled" && message.params.type === "error") errors.push(`console: ${message.params.args.map((arg) => arg.value ?? arg.description ?? "").join(" ").slice(0, 300)}`);
    if (message.method === "Log.entryAdded" && message.params.entry.level === "error") errors.push(`${message.params.entry.source}: ${String(message.params.entry.text).slice(0, 300)}${message.params.entry.url ? ` (${message.params.entry.url})` : ""}`);
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
  for (const domain of ["Page", "Runtime", "Network", "Log"]) await tab(`${domain}.enable`);
  await tab("Network.setCacheDisabled", { cacheDisabled: true });
  await tab("Fetch.enable", { patterns: [{ urlPattern: "*" }] });
  const evaluate = async (expression) => {
    const reply = await tab("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (reply.exceptionDetails) throw new Error(reply.exceptionDetails.exception?.description || reply.exceptionDetails.text);
    return reply.result.value;
  };
  const V = "document.querySelector('cells-viewer')";
  /** Open an address cold and wait until it has settled: its view ready, nothing fetching, and the page quiet. */
  const open = async (address) => {
    await tab("Page.navigate", { url: "about:blank" });
    await sleep(300);
    for (const list of [asked, hosts, outside, errors]) list.length = 0;
    const opened = Date.now();
    await tab("Page.navigate", { url: `${origin}${address}` });
    let ready = false;
    for (let tries = 0; tries < 480 && !ready; tries++) {
      await sleep(250);
      ready = await evaluate(`Boolean(${V}?.model && (${V}.current || !${V}.stage))`).catch(() => false);
    }
    await evaluate(`Promise.race([Promise.resolve(${V}?.current?.ready), new Promise((done) => setTimeout(done, 60000))]).then(() => true)`).catch(() => null);
    await evaluate("document.fonts.ready.then(() => true)").catch(() => null);
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
  /** A real press at the middle of what `element` finds in the viewer's shadow root. */
  const press = async (selector) => {
    const box = await evaluate(`(() => { const r = ${V}.shadowRoot.querySelector(${JSON.stringify(selector)})?.getBoundingClientRect(); return r && r.width ? { x: r.left + r.width / 2, y: r.top + r.height / 2 } : null; })()`);
    if (!box) return false;
    for (const type of ["mouseMoved", "mousePressed", "mouseReleased"]) await tab("Input.dispatchMouseEvent", { type, x: box.x, y: box.y, button: type === "mouseMoved" ? "none" : "left", clickCount: type === "mouseMoved" ? 0 : 1 });
    return true;
  };

  // The first page of a fresh browser is not judged (its first context on the card is lost and made again).
  await open(`/r/${ID}/?lens=laws`);
  await sleep(6000);
  const pages = [["the root page", "/"], ["the release's page", `/r/${ID}/`]];
  const queries = ["", "?lens=machines&species=human", "?lens=experiments"];
  for (const [which, at] of pages) {
    for (const query of queries) {
      const address = `${at}${query}`;
      const ready = await open(address);
      const rows = asked.map((row) => ({ ...row }));
      const files = rows.filter((row) => row.path !== "/favicon.ico");
      const byHost = hosts.reduce((map, host) => ({ ...map, [host]: (map[host] || 0) + 1 }), {});
      const sum = (key) => files.reduce((total, row) => total + (row[key] ?? row.raw), 0);
      const totals = { requests: files.length, raw: sum("raw"), sent: sum("sent"), br: sum("br"), gz: sum("gz") };
      const state = await evaluate(`(() => { const v = ${V}; return { lens: v?.state?.lens || null, host: v?.host ? { release: v.host.release, links: v.host.links, problem: v.host.problem } : null, base: document.baseURI, fonts: [...document.fonts].filter((face) => face.status === "loaded").map((face) => face.family.replace(/"/g, "") + " " + face.weight) }; })()`).catch(() => ({}));
      const label = `${which}, ${query || "the opening view"}`;
      check(`${label}: the page opened`, ready, JSON.stringify({ lens: state.lens }));
      check(`${label}: no request to any host but the site's own`, !outside.length && Object.keys(byHost).every((host) => host === new URL(origin).host), outside.length ? [...new Set(outside.map((url) => new URL(url).host))].join(", ") : `${hosts.length} requests`);
      const missing = files.filter((row) => row.status !== 200);
      check(`${label}: no file is missing`, !missing.length, missing.slice(0, 4).map((row) => `${row.status} ${row.path}`).join(", "));
      check(`${label}: no console error and no exception`, !errors.length, errors.slice(0, 3).join(" | "));
      const fonts = state.fonts || [];
      const fontRows = files.filter((row) => row.path.includes("/vendor/fonts/"));
      check(`${label}: the page's two fonts arrived from the site`, fonts.some((face) => face.startsWith("Inter ")) && fonts.some((face) => face.startsWith("Space Grotesk ")) && fontRows.length >= 2, `${fonts.join(", ")}; ${fontRows.length} files`);
      check(`${label}: the viewer read its host profile, and its base address is the release's folder`, state.host?.release === ID && !state.host?.problem && new URL(state.base || origin).pathname === `/r/${ID}/`, JSON.stringify({ host: state.host, base: state.base && new URL(state.base).pathname }));
      // A press on another tab: the address keeps its folder, its query, and takes the tab's name.
      const tabName = state.lens === "engine" ? "laws" : "engine";
      const pressed = await press(`.switch [data-lens="${tabName}"]`);
      let now = null;
      for (let tries = 0; tries < 80 && pressed; tries++) {
        now = await evaluate(`({ lens: ${V}.state.lens, path: location.pathname, search: location.search, hash: location.hash })`).catch(() => null);
        if (now?.lens === tabName && now.hash === `#${tabName}`) break;
        await sleep(250);
      }
      const search = query ? new URLSearchParams(query).toString() : "";
      check(`${label}: a press on ${tabName} keeps the address at ${at} and names the tab`, pressed && now?.lens === tabName && now.path === at && now.hash === `#${tabName}` && new URLSearchParams(now.search).toString() === search, JSON.stringify(now));
      if (rows.some((row) => row.path === "/favicon.ico")) note(`  the browser asked for /favicon.ico (${rows.find((row) => row.path === "/favicon.ico").status}); no page names it`);
      const copies = files.some((row) => row.br !== null || row.gz !== null);
      note(`  requests by host: ${JSON.stringify(byHost)}; first visit: ${totals.requests} files, raw ${kb(totals.raw)}, as sent ${kb(totals.sent)}; ${copies ? `with every copy brotli's ${kb(totals.br)}, gzip's ${kb(totals.gz)}` : "the release holds no compressed copies (--compress)"}`);
      for (const row of files) note(`    ${row.status} ${row.path}${row.query}  raw ${row.raw}, sent ${row.sent}${row.encoding ? ` (${row.encoding})` : ""}`);
      record.visits.push({ page: which, address, ready, hosts: byHost, outside, errors: errors.slice(0, 20), totals, files: files.map((row) => [row.path, row.status, row.raw, row.sent, row.encoding]), fonts, host: state.host, press: { tab: tabName, address: now } });
    }
  }
  record.accept_encoding = [...encodings];
  note(`the browser asked with Accept-Encoding: ${[...encodings].join(" | ")}`);
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
record.seconds = Math.round((Date.now() - began) / 1000);
await mkdir(OUT, { recursive: true });
await writeFile(path.join(OUT, "site-check.json"), JSON.stringify(record, null, 1) + "\n");
note(`wrote ${path.relative(ROOT, path.join(OUT, "site-check.json"))}; ${record.seconds} s`);
if (failed) {
  console.error(failed.stack || String(failed));
  check("the checks ran to their end", false, String(failed.message || failed).slice(0, 200));
}
console.log(`${results.filter(Boolean).length} of ${results.length} checks passed`);
process.exit(results.every(Boolean) ? 0 : 1);
