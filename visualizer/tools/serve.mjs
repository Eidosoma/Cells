#!/usr/bin/env node
// Local preview. Rebuilds the page on every request and serves it under a policy
// close to the artifact frame's, so what works here works when published.
//
//   node tools/serve.mjs [--port 4173] [--scene PATH] [--runs DIR] [--offline] [--no-proteins]
//
// --offline loads three.js from node_modules instead of the CDN.
// --no-proteins serves none of the species' own proteins, as a page published without them finds.
// Query parameters for checking a state: ?theme=dark&lens=engine&select=ID&scale=tissue&isolate=planned&index=1

import http from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { buildPage, proteinFiles, machineFiles, modelFiles, shapeFiles, benchFiles, landingFiles, wrap, contentSecurityPolicy, ROOT, THREE_CDN, THREE_LOCAL, DEFAULT_SCENE, DEFAULT_RUNS, DEFAULT_PROTEINS, DEFAULT_MEMBERS, DEFAULT_MACHINES, DEFAULT_CARDS } from "./lib/build_page.mjs";

// Reports script errors and blocked loads back to this server, in previews only.
const REPORTER = `<script>
(function () {
  var send = function (text) { try { navigator.sendBeacon("/__log", text); } catch (error) {} };
  addEventListener("error", function (event) { send("error: " + event.message + " at " + (event.filename || "") + ":" + event.lineno); });
  addEventListener("unhandledrejection", function (event) { send("rejection: " + (event.reason && (event.reason.stack || event.reason.message) || event.reason)); });
  addEventListener("securitypolicyviolation", function (event) { send("blocked by policy: " + event.blockedURI + " (" + event.violatedDirective + ")"); });
})();
</script>`;

/**
 * `proteins` is the folder of the species' own proteins and `members` where the files of a
 * large catalogue's members are written; `proteins: null` serves none of them, as a page
 * published without those files would find.
 */
export function createServer({ scene = DEFAULT_SCENE, runs = DEFAULT_RUNS, offline = false, log = console.log, proteins = DEFAULT_PROTEINS, members = DEFAULT_MEMBERS, machines = DEFAULT_MACHINES, cards = DEFAULT_CARDS } = {}) {
  // The files beside the page, by the address the page fetches them at. Listed again with each page, so a rebuilt scene is followed.
  let beside = new Map(), machined = new Map();
  const list = async () => {
    const data = JSON.parse(await readFile(scene, "utf8"));
    // A machine's file (schema/MACHINES.md), as it is published beside the page.
    const made = machines ? await machineFiles(data, { machinesDir: machines }) : { files: [], problems: [] };
    for (const problem of made.problems) log(`[server] machines: ${problem}`);
    // And a model system's run files (schema/MODEL_SYSTEMS.md), beside the page in the same way.
    machined = new Map([...made.files, ...(await modelFiles(data)).files, ...(await shapeFiles()).files, ...(await benchFiles()).files].map((file) => [`/${file.path}`, file.source]));
    if (!proteins) return;
    const found = await proteinFiles(data, { proteinsDir: proteins, membersDir: members });
    for (const problem of found.problems) log(`[server] proteins: ${problem}`);
    beside = new Map(found.files.map((file) => [`/${file.path}`, file.source]));
  };
  return http.createServer(async (request, response) => {
    const url = new URL(request.url, "http://localhost");
    try {
      if (url.pathname === "/__log") {
        let body = "";
        request.on("data", (chunk) => (body += chunk));
        request.on("end", () => {
          log(`[page] ${body}`);
          response.writeHead(204).end();
        });
        return;
      }
      if (url.pathname === THREE_LOCAL) {
        const file = await readFile(path.join(ROOT, "node_modules", "three", "build", "three.module.min.js"));
        response.writeHead(200, { "content-type": "text/javascript", "cache-control": "max-age=3600" }).end(file);
        return;
      }
      // Replays are served beside the page, as the published artifact serves them.
      const run = /^\/runs\/([a-z0-9.-]+\.json)$/.exec(url.pathname);
      if (run) {
        const file = await readFile(path.join(runs, run[1])).catch(() => null);
        if (!file) response.writeHead(404).end("not found");
        else response.writeHead(200, { "content-type": "application/json", "cache-control": "no-store" }).end(file);
        return;
      }
      // The landing's cards (their faces and their details) and stills, beside the page as they are published.
      if (url.pathname === "/cards.json" || url.pathname === "/cards.details.json" || url.pathname.startsWith("/stills/")) {
        const source = (await landingFiles({ cardsPath: cards })).files.find((file) => `/${file.path}` === url.pathname)?.source;
        const file = source ? await readFile(source).catch(() => null) : null;
        if (!file) response.writeHead(404).end("not found");
        else response.writeHead(200, { "content-type": url.pathname.endsWith(".json") ? "application/json" : url.pathname.endsWith(".png") ? "image/png" : "image/jpeg", "cache-control": "no-store" }).end(file);
        return;
      }
      // A machine's file is served beside the page too, as it is published.
      if (url.pathname.startsWith("/machines/") || url.pathname.startsWith("/models/") || url.pathname.startsWith("/shapes/") || url.pathname.startsWith("/catalogue/")) {
        if (!machined.size) await list();
        const source = machined.get(url.pathname);
        const file = source ? await readFile(source).catch(() => null) : null;
        if (!file) response.writeHead(404).end("not found");
        else response.writeHead(200, { "content-type": "application/json", "cache-control": "no-store" }).end(file);
        return;
      }
      // The species' own proteins are served beside the page too, as they are published.
      if (url.pathname.startsWith("/proteins/")) {
        if (!beside.size) await list();
        const source = beside.get(url.pathname);
        const file = source ? await readFile(source).catch(() => null) : null;
        if (!file) response.writeHead(404).end("not found");
        else response.writeHead(200, { "content-type": "application/json", "cache-control": "no-store" }).end(file);
        return;
      }
      if (url.pathname === "/") {
        await list();
        const content = await buildPage({ scenePath: scene, runsDir: runs, three: offline ? THREE_LOCAL : THREE_CDN });
        const html = wrap(content, { theme: url.searchParams.get("theme"), head: REPORTER });
        response.writeHead(200, {
          "content-type": "text/html; charset=utf-8",
          "content-security-policy": contentSecurityPolicy({ local: true }),
          "cache-control": "no-store",
        });
        response.end(html);
        return;
      }
      response.writeHead(404).end("not found");
    } catch (error) {
      log(`[server] ${error.stack || error}`);
      response.writeHead(500, { "content-type": "text/plain" }).end(String(error.stack || error));
    }
  });
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const args = process.argv.slice(2);
  const value = (name, fallback) => (args.includes(name) ? args[args.indexOf(name) + 1] : fallback);
  const port = Number(value("--port", 4173));
  const server = createServer({ scene: value("--scene", DEFAULT_SCENE), runs: value("--runs", DEFAULT_RUNS), offline: args.includes("--offline"), proteins: args.includes("--no-proteins") ? null : DEFAULT_PROTEINS });
  server.listen(port, "127.0.0.1", () => console.log(`Cells visualizer at http://127.0.0.1:${port}/  (Ctrl+C to stop)`));
}
