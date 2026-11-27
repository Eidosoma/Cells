#!/usr/bin/env node
// The site's acceptance check (docs/HOSTING_AND_API.md, section 10): a visit to a release asks no host but the site's own.
//
//   node tools/check_site.mjs --site SITE [--id v49] [--out DIR] [--no-pictures]
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
// visit. What the site says of itself is held too, on both pages:
//   - the head: the title and description of the About words, the site's address as canonical and as og:url, the share
//     picture as og:image (the release's own, a JPEG of 1200 by 630 within 200 kB), the large-image card, and structured
//     data for the site and its source code whose one name of anyone is the About words' credit (data/site/about.json):
//     the site's publisher and the source code's author, an organisation by name;
//   - the text without script: with script switched off, the About words stand whole as HTML (a heading, the paragraphs,
//     the credit, the source code in a new tab and no licence link, each view a link), no cover stands, and nothing is
//     fetched from another host; with script, the page puts them away once it has drawn;
//   - the cover while the page loads (20 November 2026), each page loaded on a slow line (the browser's own throttling,
//     128 kB/s and 150 ms; the page is some 0.6 MB as sent), in the light theme and the dark one: looked at within the
//     first half second of the page's own clock and again at about one second, before the page has drawn, the cover
//     stands over the window in the page's own background for the theme, its ring in the window's middle (a sixth of the window's shorter side, between 96 and 160 px, in
//     the accent), a status in the page's words, and no word of the About text is seen, under the window's middle or
//     reached by a Tab press; once the page has drawn, cover and text are both put away. Where less motion is asked for
//     the ring does not turn. On a line slow enough that the page cannot draw in COVER_WAIT seconds, the cover lets the
//     About words through at that time (its links pressed and reached), and when the page then draws, both are put away.
//     Pictures of each look go to DIR/pictures (the root page also on a phone of 360 px, and with script off).
//     --no-pictures keeps every check and clock threshold when a software screenshot stalls the next sample.
//   - the root files, served as --release will put them at the root (the release's own, before the pointer moves):
//     robots.txt lets every reader read everything and never closes /r/, and names the sitemap; the sitemap lists the
//     root; llms.txt names the release's files, its cards, the contracts and the source.
// The browser's own request for /favicon.ico (no page asks for it) is said apart. --id is the release the pointer on disk
// names unless given. Into DIR (out/check-site unless given) goes site-check.json.
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
import { COMPRESSIBLE, COVER_WAIT, ROOT_FILES, SHARE, SHARE_SIZE, SITE, contentType, jpegSize, pageColours, sitePolicy } from "./stage_site.mjs";
const CREDIT = JSON.parse(await readFile(path.join(ROOT, "data", "site", "about.json"), "utf8")).credit; // what names anyone

const args = process.argv.slice(2);
const savePictures = !args.includes("--no-pictures");
const value = (name, fallback) => (args.includes(name) ? args[args.indexOf(name) + 1] : fallback);
const SITE_DIR = value("--site") ? path.resolve(value("--site")) : null;
if (!SITE_DIR || !existsSync(path.join(SITE_DIR, "r"))) {
  console.error("usage: node tools/check_site.mjs --site SITE [--id ID] [--out DIR]  (SITE holds r/<id>/, and index.html once a pointer is moved)");
  process.exit(2);
}
const OUT = path.resolve(value("--out", path.join(ROOT, "out", "check-site")));
const pointer = existsSync(path.join(SITE_DIR, "index.html")) ? /<script type="application\/json" id="cells-host">([\s\S]*?)<\/script>/.exec(await readFile(path.join(SITE_DIR, "index.html"), "utf8"))?.[1] : undefined;
const pointed = pointer ? JSON.parse(pointer).release ?? null : pointer === undefined ? undefined : null;
const ID = value("--id", pointed ?? null);
if (!ID || !existsSync(path.join(SITE_DIR, "r", ID, "release.json"))) {
  console.error(`no release ${ID} in the site's r/ (give --id)`);
  process.exit(2);
}
// The root page is checked as it will stand once the pointer names this release: its root.html, which --release copies
// over SITE/index.html byte for byte, sent as its compressed copy where the release has one. So a release is checked before
// the pointer moves to it, and the pointer on disk, whatever it names, is not read.
const ROOT_PAGE = path.join(SITE_DIR, "r", ID, "root.html");
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
  // The root files as --release will put them beside the pointer: the release's own.
  const file = isPointer ? ROOT_PAGE : ROOT_FILES.includes(name.slice(1)) ? path.join(SITE_DIR, "r", ID, name.slice(1)) : path.join(SITE_DIR, name);
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
note(`serving ${path.basename(SITE_DIR)} at ${origin}/ (release ${ID}), until the check ends`);
note(`the root page is r/${ID}/root.html, as --release would copy it; the pointer on disk ${pointed === undefined ? "is not there yet" : pointed === ID ? `names ${ID} already` : `names ${pointed ?? "no release"}, and is not read`}`);

// ---------------------------------------------------------------- what the site says of itself, as served (no browser)
const said = { pages: {}, root: {} };
const attribute = (html, key, name) => new RegExp(`<meta ${key}="${name.replace(/[.:]/g, "\\$&")}" content="([^"]*)">`).exec(html)?.[1] ?? null;
const unescape = (text) => String(text ?? "").replace(/&quot;/g, '"').replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
const releaseFiles = JSON.parse(await readFile(path.join(SITE_DIR, "r", ID, "release.json"), "utf8"));
for (const [which, at] of [["the root page", "/"], ["the release's page", `/r/${ID}/`]]) {
  const html = await (await fetch(`${origin}${at}`)).text();
  const head = html.slice(0, html.indexOf("</head>"));
  const image = attribute(head, "property", "og:image");
  const picture = await readFile(path.join(SITE_DIR, "r", ID, SHARE)).catch(() => null);
  let data = null;
  try {
    data = JSON.parse(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/.exec(head)?.[1] || "null");
  } catch {}
  const graph = data?.["@graph"] || [];
  const site = graph.find((item) => item["@type"] === "WebSite"), code = graph.find((item) => item["@type"] === "SoftwareSourceCode");
  const title = /<title>([^<]*)<\/title>/.exec(head)?.[1] ?? null, description = attribute(head, "name", "description");
  check(`${which}: its head has a title and a description, and the site's address as canonical and og:url`, title && description && head.includes(`<link rel="canonical" href="${SITE}">`) && attribute(head, "property", "og:url") === SITE && attribute(head, "property", "og:title") === title && attribute(head, "property", "og:description") === description, JSON.stringify({ title, canonical: /<link rel="canonical" href="([^"]*)">/.exec(head)?.[1] }));
  check(`${which}: its link preview is the large-image card with the release's own picture, ${SHARE_SIZE.width} by ${SHARE_SIZE.height}, within ${SHARE_SIZE.most / 1000} kB`, image === `${SITE}r/${ID}/${SHARE}` && attribute(head, "name", "twitter:card") === "summary_large_image" && picture && picture.length <= SHARE_SIZE.most && JSON.stringify(jpegSize(picture)) === JSON.stringify({ width: SHARE_SIZE.width, height: SHARE_SIZE.height }) && attribute(head, "property", "og:image:width") === String(SHARE_SIZE.width) && attribute(head, "property", "og:image:height") === String(SHARE_SIZE.height) && !/twitter:(site|creator)/.test(head), JSON.stringify({ image, bytes: picture?.length, size: picture && jpegSize(picture) }));
  const by = JSON.stringify({ "@type": "Organization", name: CREDIT?.organisation });
  check(`${which}: its structured data names the site and its source code (name, description, repository, licence, address), and its one name of anyone is the credit's organisation, the site's publisher and the code's author`, site?.name && site.url === SITE && unescape(site.description) === unescape(description) && code?.name && code.description && /^https:\/\//.test(code.codeRepository || "") && /\/LICENSE$/.test(code.license || "") && JSON.stringify(site.publisher) === by && JSON.stringify(code.author) === by && !site.author && !code.publisher && !/"(creator|copyrightHolder|maintainer|contributor|funder|sponsor|email|telephone|sameAs|logo)"|"Person"/.test(JSON.stringify(data)), JSON.stringify({ types: graph.map((item) => item["@type"]), license: code?.license, publisher: site?.publisher, author: code?.author }));
  said.pages[at] = { title, description, image, data };
}
const served = {};
for (const name of ["robots.txt", "sitemap.xml", "llms.txt"]) {
  const answer = await fetch(`${origin}/${name}`);
  served[name] = { status: answer.status, type: answer.headers.get("content-type"), text: answer.status === 200 ? await answer.text() : "" };
}
const robots = served["robots.txt"].text;
check("robots.txt: every reader may read everything, /r/ is never closed, and the sitemap is named", served["robots.txt"].status === 200 && /^text\/plain/.test(served["robots.txt"].type || "") && /^User-agent: \*$/m.test(robots) && !/^Disallow:\s*\S/m.test(robots) && robots.includes(`Sitemap: ${SITE}sitemap.xml`), JSON.stringify({ status: served["robots.txt"].status, type: served["robots.txt"].type, lines: robots.split("\n").filter((line) => line && !line.startsWith("#")) }));
check("sitemap.xml: it lists the root", served["sitemap.xml"].status === 200 && /xml/.test(served["sitemap.xml"].type || "") && served["sitemap.xml"].text.includes(`<loc>${SITE}</loc>`), served["sitemap.xml"].type || String(served["sitemap.xml"].status));
const llms = served["llms.txt"].text;
const releaseCards = await readFile(path.join(SITE_DIR, "r", ID, "cards.json"), "utf8").then(JSON.parse, () => null);
const titles = (releaseCards?.cards || []).map((card) => card.title).filter(Boolean);
check("llms.txt: the About words, the views, every card's title, the release's files and contracts, and the source", served["llms.txt"].status === 200 && llms.startsWith("# Cells\n") && llms.includes(`${SITE}r/${ID}/release.json`) && llms.includes(`${SITE}?lens=`) && titles.every((title) => llms.includes(title)) && /\]\(https:\/\/github\.com\/[^)]*\/schema\/[A-Z_]+\.md\)/.test(llms) && llms.includes("## Source"), JSON.stringify({ status: served["llms.txt"].status, bytes: llms.length, cards: titles.length, missing: titles.filter((title) => !llms.includes(title)).slice(0, 3) }));
said.root = Object.fromEntries(Object.entries(served).map(([name, item]) => [name, { status: item.status, type: item.type, bytes: Buffer.byteLength(item.text) }]));
note(`the release's files: ${releaseFiles.files.length}; the root files as served: ${JSON.stringify(said.root)}`);

// ---------------------------------------------------------------- the browser
const release = await acquireBrowser({ wait: Number(process.env.WAIT_MINUTES || 30) * 60 * 1000 });
const chrome = spawn(
  process.env.CHROME || "google-chrome",
  ["--headless=new", `--user-data-dir=${release.profile}`, "--disable-breakpad", "--no-first-run", "--no-sandbox", "--mute-audio", "--hide-scrollbars", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", `--window-size=${WIDTH},${HEIGHT}`, "--remote-debugging-port=0", "about:blank"],
  { stdio: ["ignore", "ignore", "pipe"] }
);
const record = { format: "cells.visualizer.site_check@1", site: path.basename(SITE_DIR), release: ID, pictures: savePictures, policy: sitePolicy(), said, visits: [], text: [] };
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
      const search = new URLSearchParams(query);
      search.delete("lens");
      search.delete("select");
      check(`${label}: a press on ${tabName} keeps the address at ${at} and names the tab`, pressed && now?.lens === tabName && now.path === at && now.hash === `#${tabName}` && new URLSearchParams(now.search).toString() === search.toString(), JSON.stringify(now));
      if (rows.some((row) => row.path === "/favicon.ico")) note(`  the browser asked for /favicon.ico (${rows.find((row) => row.path === "/favicon.ico").status}); no page names it`);
      const copies = files.some((row) => row.br !== null || row.gz !== null);
      note(`  requests by host: ${JSON.stringify(byHost)}; first visit: ${totals.requests} files, raw ${kb(totals.raw)}, as sent ${kb(totals.sent)}; ${copies ? `with every copy brotli's ${kb(totals.br)}, gzip's ${kb(totals.gz)}` : "the release holds no compressed copies (--compress)"}`);
      for (const row of files) note(`    ${row.status} ${row.path}${row.query}  raw ${row.raw}, sent ${row.sent}${row.encoding ? ` (${row.encoding})` : ""}`);
      record.visits.push({ page: which, address, ready, hosts: byHost, outside, errors: errors.slice(0, 20), totals, files: files.map((row) => [row.path, row.status, row.raw, row.sent, row.encoding]), fonts, host: state.host, press: { tab: tabName, address: now } });
    }
  }
  // Old shared links could carry both routes. Refreshing and moving the same element must keep the chosen tab.
  await open("/?lens=machines&species=human#engine");
  check("the fragment wins on a conflicting shared link", await evaluate(`${V}.state.lens === "engine"`));
  await tab("Page.reload");
  let restored = false;
  for (let tries = 0; tries < 80 && !restored; tries++) {
    await sleep(250);
    restored = await evaluate(`Boolean(${V}?.model && ${V}.state.lens === "engine" && performance.getEntriesByType("navigation")[0]?.type === "reload")`).catch(() => false);
  }
  check("a refresh restores the same tab", restored);
  const remounted = await evaluate(`(async () => {
    const viewer = ${V}, parent = viewer.parentNode, next = viewer.nextSibling;
    const root = viewer.shadowRoot, stage = viewer.stage;
    const ready = new Promise((done) => viewer.addEventListener("cells-ready", () => done(true), { once: true }));
    viewer.remove();
    const detached = !viewer.model && !viewer.stage;
    parent.insertBefore(viewer, next);
    const mounted = await Promise.race([ready, new Promise((done) => setTimeout(() => done(false), 5000))]);
    return mounted && detached && viewer.shadowRoot === root && (!stage || viewer.stage !== stage) &&
      viewer.shadowRoot.querySelectorAll(".frame").length === 1 && viewer.state.lens === "engine";
  })()`);
  check("the same viewer can be removed and mounted again", remounted);
  const part = await evaluate(`${V}.model.inLens("engine")[0].id`);
  await open(`/?select=${encodeURIComponent(part)}`);
  check("a link that names only a part keeps its selection when its tab opens", await evaluate(`${V}.state.lens === "engine" && ${V}.state.selected === new URL(location.href).searchParams.get("select") && ${V}.state.selected === ${JSON.stringify(part)}`));
  // ---------------------------------------------------------------- the cover while the page loads
  const pictures = path.join(OUT, "pictures");
  if (savePictures) await mkdir(pictures, { recursive: true });
  const picture = async (name) => {
    if (!savePictures) return;
    const shot = await tab("Page.captureScreenshot", { format: "png" }).catch(() => null);
    if (shot?.data) await writeFile(path.join(pictures, `${name}.png`), Buffer.from(shot.data, "base64"));
  };
  const colours = pageColours(await readFile(path.join(SITE_DIR, "r", ID, "index.html"), "utf8"));
  const rgb = (hex) => `rgb(${[1, 3, 5].map((at) => parseInt(hex.slice(at, at + 2), 16)).join(", ")})`;
  const fast = { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 };
  const slow = (bytesPerSecond) => ({ offline: false, latency: 150, downloadThroughput: bytesPerSecond, uploadThroughput: bytesPerSecond });
  const setSize = (width, height, mobile = false) => tab("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile });
  const setMedia = (dark, still = false) => tab("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: dark ? "dark" : "light" }, { name: "prefers-reduced-motion", value: still ? "reduce" : "no-preference" }] });
  // What the window shows, read in one go with the page's own clock: the cover, its ring, the text, what stands under the
  // window's middle and under the text's first link, and whether the page has drawn (it puts the cover away as it draws).
  const look = () =>
    evaluate(`(() => {
      const cover = document.getElementById("cells-cover"), text = document.getElementById("cells-text"), ring = cover?.querySelector(".cells-ring");
      const seen = (element) => { if (!element) return false; const style = getComputedStyle(element), r = element.getBoundingClientRect(); return style.display !== "none" && style.visibility === "visible" && r.width > 0 && r.height > 0; };
      const box = (element) => { const r = element?.getBoundingClientRect(); return r ? { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2), width: Math.round(r.width), height: Math.round(r.height) } : null; };
      const middle = document.elementFromPoint(innerWidth / 2, innerHeight / 2), link = text?.querySelector("a"), at = box(link);
      const under = at ? document.elementFromPoint(at.x, at.y) : null;
      const status = cover?.getAttribute("role") === "status" ? document.getElementById(cover.getAttribute("aria-labelledby") || "")?.textContent || null : null;
      return {
        here: location.origin === ${JSON.stringify(origin)}, t: Math.round(performance.now()), state: document.readyState, drawn: Boolean(cover?.hasAttribute("hidden") || text?.hasAttribute("hidden")),
        window: { width: innerWidth, height: innerHeight },
        cover: { seen: seen(cover), background: cover ? getComputedStyle(cover).backgroundColor : null, body: getComputedStyle(document.body).backgroundColor, status },
        ring: ring ? { ...box(ring), width: ring.offsetWidth, height: ring.offsetHeight, seen: seen(ring), colour: getComputedStyle(ring).borderTopColor, animation: getComputedStyle(ring).animationName } : null,
        waited: Math.round(document.getAnimations().find((item) => item.animationName === "cells-site-gone")?.startTime ?? -1),
        text: { seen: seen(text), visibility: text ? getComputedStyle(text).visibility : null, colour: text ? getComputedStyle(text).color : null },
        middle: middle ? (cover?.contains(middle) ? "cover" : text?.contains(middle) ? "text" : middle.tagName.toLowerCase()) : null,
        link: under ? (link === under || link?.contains(under) ? "the text's link" : cover?.contains(under) ? "cover" : under.tagName.toLowerCase()) : null,
      };
    })()`);
  /** A real Tab press from the top of the document: where the keyboard lands (in the text or not). */
  const tabbed = async () => {
    await evaluate("(document.activeElement?.blur?.(), true)");
    for (const type of ["rawKeyDown", "keyUp"]) await tab("Input.dispatchKeyEvent", { type, key: "Tab", code: "Tab", windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9 });
    await sleep(80);
    return evaluate(`(() => { const a = document.activeElement; return { tag: a?.tagName.toLowerCase() || null, inText: Boolean(document.getElementById("cells-text")?.contains(a)), href: a?.getAttribute?.("href") || null }; })()`);
  };
  /** Open an address on a slow line, without waiting: the navigation is under way when it returns. */
  const startSlow = async (address, conditions) => {
    await tab("Network.emulateNetworkConditions", fast);
    await tab("Page.navigate", { url: "about:blank" });
    await sleep(300);
    for (const list of [asked, hosts, outside, errors]) list.length = 0;
    await tab("Network.emulateNetworkConditions", conditions);
    tab("Page.navigate", { url: `${origin}${address}` }).catch(() => null);
  };
  /** Looks at about `ms` of the page's own clock (the first one that comes), with the page not yet drawn. */
  const lookAt = async (ms, until = 8000, elapsed = (seen) => seen.t) => {
    const start = Date.now();
    let seen = null;
    while (Date.now() - start < until) {
      seen = await look().catch(() => null);
      if (seen?.here && elapsed(seen) >= ms) return seen;
      await sleep(40);
    }
    return seen;
  };
  /** After the line is fast again: the page drawn, its view ready. */
  const drawnAfter = async () => {
    await tab("Network.emulateNetworkConditions", fast);
    let ready = false;
    for (let tries = 0; tries < 480 && !ready; tries++) {
      await sleep(250);
      ready = await evaluate(`Boolean(${V}?.model && (${V}.current || !${V}.stage) && document.getElementById("cells-cover")?.hasAttribute("hidden"))`).catch(() => false);
    }
    await evaluate(`Promise.race([Promise.resolve(${V}?.current?.ready), new Promise((done) => setTimeout(done, 30000))]).then(() => true)`).catch(() => null);
    await sleep(1500);
    return ready;
  };
  const coverRuns = [
    ["the root page", "/", "root", "wide", false, false],
    ["the root page", "/", "root", "wide", true, false],
    ["the root page", "/", "root", "phone", false, false],
    ["the root page", "/", "root", "phone", true, false],
    ["the release's page", `/r/${ID}/`, "release", "wide", false, false],
    ["the release's page", `/r/${ID}/`, "release", "wide", true, true],
  ];
  record.cover = [];
  for (const [which, at, short, size, dark, still] of coverRuns) {
    const theme = dark ? "dark" : "light", own = colours[theme];
    const label = `${which}, ${size === "phone" ? "a phone of 360 px" : `${WIDTH} by ${HEIGHT}`}, ${theme}${still ? ", less motion asked for" : ""}`;
    if (size === "phone") await setSize(360, 780, true);
    await setMedia(dark, still);
    await startSlow(at, slow(128 * 1024));
    const looks = [];
    for (const [ms, name] of [[300, "0.3s"], [1000, "1s"]]) {
      const seen = await lookAt(ms);
      const keys = name === "1s" ? await tabbed() : null;
      await picture(`cover-${short}-${size}-${theme}-${name}`);
      looks.push({ name, seen, keys });
    }
    const [first, second] = looks.map((item) => item.seen);
    const middle = (seen) => seen?.ring && Math.abs(seen.ring.x - seen.window.width / 2) <= 2 && Math.abs(seen.ring.y - seen.window.height / 2) <= 2 && seen.ring.width >= 96 && seen.ring.width <= 160 && Math.abs(seen.ring.width - Math.min(160, Math.max(96, 0.16 * Math.min(seen.window.width, seen.window.height)))) <= 2 && seen.ring.width === seen.ring.height;
    const covers = (seen) => seen && !seen.drawn && seen.cover.seen && seen.ring?.seen && middle(seen) && !seen.text.seen && seen.text.visibility === "hidden" && seen.middle === "cover" && seen.cover.status;
    check(`${label}: within the first half second, before the page has drawn, the cover stands with its ring in the window's middle and a status, and no word of the text is seen`, covers(first) && first.t <= 500, JSON.stringify(first));
    check(`${label}: at about one second, still before the page has drawn, the same, and a Tab press reaches nothing of the text`, covers(second) && second.t >= 900 && second.t <= 1600 && !looks[1].keys?.inText, JSON.stringify({ ...second, keys: looks[1].keys }));
    check(`${label}: from the first paint, the page's own ${theme} background and accent (not the light ones)`, first?.cover.background === rgb(own.bg) && first.cover.body === rgb(own.bg) && first.ring?.colour === rgb(own.accent), JSON.stringify({ background: first?.cover.background, body: first?.cover.body, ring: first?.ring?.colour, own }));
    if (still) check(`${label}: the ring does not turn (a slow fade)`, first?.ring?.animation === "cells-site-fade" && second?.ring?.animation === "cells-site-fade", JSON.stringify(first?.ring));
    const ready = await drawnAfter();
    const after = await look().catch((error) => ({ error: error.message }));
    await picture(`cover-${short}-${size}-${theme}-drawn`);
    check(`${label}: once the page has drawn, the cover and the text are both put away`, ready && after?.drawn && !after.cover.seen && !after.text.seen && after.middle !== "cover" && after.middle !== "text", JSON.stringify(after));
    record.cover.push({ page: which, size, theme, still, looks, after });
    if (size === "phone") await setSize(WIDTH, HEIGHT);
  }
  // Never a spinner for ever: on a line too slow for the page to draw in COVER_WAIT seconds, the cover lets the words
  // through at that time, by the sheet alone; then the line is fast again, the page draws, and both are put away.
  {
    const label = `the root page, on a line too slow to draw in ${COVER_WAIT} s`;
    await setMedia(false);
    await startSlow("/", slow(12 * 1024));
    // The wait is counted from the cover's first style (its animation's start, on the page's clock).
    const elapsedOnCover = (seen) => seen.waited >= 0 ? seen.t - seen.waited : -1;
    const before = await lookAt(COVER_WAIT * 1000 - 1500, (COVER_WAIT + 30) * 1000, elapsedOnCover);
    const through = await lookAt(COVER_WAIT * 1000 + 500, 15000, elapsedOnCover);
    const keys = await tabbed();
    await picture(`cover-root-wide-light-${COVER_WAIT}s`);
    check(`${label}: just before, the cover still stands, and the page has not drawn`, before && !before.drawn && before.state === "loading" && before.cover.seen && !before.text.seen && before.waited >= 0 && before.t < before.waited + COVER_WAIT * 1000, JSON.stringify(before));
    check(`${label}: after, still not drawn, the cover is gone and the About words stand, their first link under its own place and the keyboard reaching it`, through && !through.drawn && through.state === "loading" && !through.cover.seen && through.text.seen && through.link === "the text's link" && keys.inText && keys.tag === "a", JSON.stringify({ ...through, keys }));
    const ready = await drawnAfter();
    const after = await look().catch((error) => ({ error: error.message }));
    check(`${label}: when the page then draws, the text and the cover are both put away`, ready && after?.drawn && !after.cover.seen && !after.text.seen, JSON.stringify(after));
    record.cover.push({ page: "the root page", wait: COVER_WAIT, before, through, keys, after });
  }
  await tab("Network.emulateNetworkConditions", fast);
  await setMedia(false);

  // The text a reader with no script gets: whole, as HTML, with nothing fetched from another host; and with script, put away once the page has drawn.
  for (const [which, at] of pages) {
    await tab("Emulation.setScriptExecutionDisabled", { value: true });
    await tab("Page.navigate", { url: "about:blank" });
    await sleep(300);
    for (const list of [asked, hosts, outside, errors]) list.length = 0;
    await tab("Page.navigate", { url: `${origin}${at}` });
    await sleep(2500);
    const text = await evaluate(`(() => { const t = document.getElementById("cells-text"); if (!t) return null; const r = t.getBoundingClientRect(), style = getComputedStyle(t); const links = [...t.querySelectorAll("a")]; return { shown: style.display !== "none" && style.visibility !== "hidden" && r.width > 0 && r.height > 0, heading: t.querySelector("h1")?.textContent || null, paragraphs: t.querySelectorAll("p").length, words: t.textContent.length, source: links.filter((a) => a.textContent.trim() === "Source code").map((a) => ({ href: a.href, target: a.target, rel: a.rel })), licence: links.filter((a) => /licen[cs]e/i.test(a.textContent + a.href)).length, credit: t.textContent.includes(${JSON.stringify(CREDIT?.text || "")}), views: links.filter((a) => /[?]lens=/.test(a.getAttribute("href"))).map((a) => a.textContent), scrolls: t.scrollHeight > t.clientHeight ? getComputedStyle(t).overflowY : "fits" }; })()`).catch((error) => ({ error: error.message }));
    check(`${which}, with script switched off: the About words stand as HTML, a heading, the paragraphs, the credit, the source code in a new tab and no licence link, each view a link`, text?.shown && text.heading === "Cells" && text.paragraphs >= 5 && text.credit && text.licence === 0 && text.source.length === 1 && text.source[0].target === "_blank" && text.source[0].rel === "noopener noreferrer" && text.views.length === 6 && ["auto", "scroll", "fits"].includes(text.scrolls), JSON.stringify(text));
    check(`${which}, with script switched off: no request to any host but the site's own`, !outside.length, outside.slice(0, 3).join(", ") || `${hosts.length} requests`);
    const bare = await evaluate(`(() => { const c = document.getElementById("cells-cover"); return { present: Boolean(c), shown: c ? getComputedStyle(c).display !== "none" : null }; })()`).catch((error) => ({ error: error.message }));
    check(`${which}, with script switched off: no cover stands, and no spinner`, bare.present && bare.shown === false, JSON.stringify(bare));
    if (at === "/") {
      for (const [size, dark] of [["wide", false], ["wide", true], ["phone", false], ["phone", true]]) {
        if (size === "phone") await setSize(360, 780, true);
        await setMedia(dark);
        await tab("Page.reload", {});
        await sleep(2500);
        const shown = await look().catch(() => null);
        if (dark) check(`${which}, with script switched off, dark${size === "phone" ? ", a phone of 360 px" : ""}: the words in the page's own dark colours`, shown?.text.seen && shown.cover.body === rgb(colours.dark.bg) && shown.text.colour === rgb(colours.dark.fg), JSON.stringify(shown?.text));
        await picture(`noscript-root-${size}-${dark ? "dark" : "light"}`);
        if (size === "phone") await setSize(WIDTH, HEIGHT);
      }
      await setMedia(false);
    }
    await tab("Emulation.setScriptExecutionDisabled", { value: false });
    const ready = await open(at);
    const away = await evaluate(`(() => { const t = document.getElementById("cells-text"); return { present: Boolean(t), hidden: t ? getComputedStyle(t).display === "none" : null, drawn: Boolean(document.querySelector("cells-viewer")?.model) }; })()`).catch((error) => ({ error: error.message }));
    check(`${which}, with script: the page put the text away once it had drawn`, ready && away.present && away.hidden && away.drawn, JSON.stringify(away));
    record.text.push({ page: which, address: at, without_script: text, with_script: away });
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
