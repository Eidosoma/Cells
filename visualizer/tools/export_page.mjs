#!/usr/bin/env node
// Writes the page to a file.
//
//   node tools/export_page.mjs [--scene PATH] [--out out/cells-architecture.html] [--standalone]
//
// Default: the page as an artifact wants it (content only; the service adds the document
// around it). --standalone writes a complete HTML document to open straight from disk.

import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { buildPage, wrap, ROOT, DEFAULT_SCENE } from "./lib/build_page.mjs";

const args = process.argv.slice(2);
const value = (name, fallback) => (args.includes(name) ? args[args.indexOf(name) + 1] : fallback);
const standalone = args.includes("--standalone");
const out = path.resolve(value("--out", path.join(ROOT, "out", standalone ? "cells-architecture.standalone.html" : "cells-architecture.html")));
const content = await buildPage({ scenePath: path.resolve(value("--scene", DEFAULT_SCENE)) });
await mkdir(path.dirname(out), { recursive: true });
await writeFile(out, standalone ? wrap(content) : content);
console.log(`wrote ${path.relative(process.cwd(), out)} (${(Buffer.byteLength(content) / 1024).toFixed(0)} KB${standalone ? ", standalone" : ", artifact content"})`);
