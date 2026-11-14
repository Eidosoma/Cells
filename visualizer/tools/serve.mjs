#!/usr/bin/env node
// Local preview. Rebuilds the page on every request and serves it under a policy
// close to the artifact frame's, so what works here works when published.
//
//   node tools/serve.mjs [--port 4173] [--scene PATH] [--offline]
//
// --offline loads three.js from node_modules instead of the CDN.
// Query parameters for checking a state: ?theme=dark&lens=engine&select=ID&scale=tissue&isolate=planned&index=1

import http from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { buildPage, wrap, contentSecurityPolicy, ROOT, THREE_CDN, THREE_LOCAL, DEFAULT_SCENE } from "./lib/build_page.mjs";

// Reports script errors and blocked loads back to this server, in previews only.
const REPORTER = `<script>
(function () {
  var send = function (text) { try { navigator.sendBeacon("/__log", text); } catch (error) {} };
  addEventListener("error", function (event) { send("error: " + event.message + " at " + (event.filename || "") + ":" + event.lineno); });
  addEventListener("unhandledrejection", function (event) { send("rejection: " + (event.reason && (event.reason.stack || event.reason.message) || event.reason)); });
  addEventListener("securitypolicyviolation", function (event) { send("blocked by policy: " + event.blockedURI + " (" + event.violatedDirective + ")"); });
})();
</script>`;

export function createServer({ scene = DEFAULT_SCENE, offline = false, log = console.log } = {}) {
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
      if (url.pathname === "/") {
        const content = await buildPage({ scenePath: scene, three: offline ? THREE_LOCAL : THREE_CDN });
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
  const server = createServer({ scene: value("--scene", DEFAULT_SCENE), offline: args.includes("--offline") });
  server.listen(port, "127.0.0.1", () => console.log(`Cells visualizer at http://127.0.0.1:${port}/  (Ctrl+C to stop)`));
}
