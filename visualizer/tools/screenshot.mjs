#!/usr/bin/env node
// Takes a picture of the viewer in headless Chrome with software WebGL, to check a
// change by looking at it. Starts its own preview server.
//
//   node tools/screenshot.mjs --out shot.png [--query "lens=engine&select=num.imex"]
//        [--size 1440x900] [--theme dark] [--cdn] [--wait 6000]

import { spawn } from "node:child_process";
import { createServer } from "./serve.mjs";

const args = process.argv.slice(2);
const value = (name, fallback) => (args.includes(name) ? args[args.indexOf(name) + 1] : fallback);
const out = value("--out", "shot.png");
const [width, height] = value("--size", "1440x900").split("x").map(Number);
const query = new URLSearchParams(value("--query", ""));
if (value("--theme")) query.set("theme", value("--theme"));
query.set("still", "1");
const chrome = process.env.CHROME || "google-chrome";

const messages = [];
const server = createServer({ offline: !args.includes("--cdn"), log: (line) => messages.push(line) });
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const url = `http://127.0.0.1:${server.address().port}/?${query}`;
const flags = [
  "--headless=new", "--no-sandbox", "--hide-scrollbars", "--mute-audio",
  "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
  `--window-size=${width},${height}`, `--virtual-time-budget=${value("--wait", "6000")}`,
  `--screenshot=${out}`, url,
];
const child = spawn(chrome, flags, { stdio: ["ignore", "ignore", "pipe"] });
let stderr = "";
child.stderr.on("data", (chunk) => (stderr += chunk));
const code = await new Promise((resolve) => child.on("close", resolve));
await new Promise((resolve) => setTimeout(resolve, 150));
server.close();
for (const line of messages) console.log(line);
if (code !== 0) {
  console.error(stderr.split("\n").slice(-5).join("\n"));
  process.exit(code);
}
console.log(`wrote ${out} (${width}x${height}${query.size ? ", " + query : ""})`);
