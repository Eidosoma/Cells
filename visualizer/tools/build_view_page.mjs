#!/usr/bin/env node
// Writes a page that holds ONE view standing alone, so that a view not yet on the map's page
// can be shown and checked.
//
//   node tools/build_view_page.mjs <view> [--out PATH] [--standalone]
//
// The view is named by its mount module, src/standalone/<view>.js, and a page file beside it,
// src/standalone/<view>.page.json, which says what the page carries:
//   title        two to four words, the page's <title>
//   description  one sentence, for whoever publishes the page
//   boot         what the page says while it starts
//   scene        { from, keep }: the scene the view's panel reads (its statuses, its source
//                address), keeping only the keys named ("all" keeps the whole scene)
//   data         [{ into, from }]: files carried whole, each put into the scene under `into`;
//                or [{ into, runs_of }]: the run files a carried entry names (its `runs`), each
//                carried whole as the map's page reads them ({...run, data}), as a list under `into`
//   stamp        the words under the notice, with {key.path} read from the carried data
//                (and {key.path|date} written as "16 November 2026"; {a.b||c.d} the first of
//                the two the data holds)
// Nothing in this tool knows a view: a new view needs only its two files.
//
// Default: the page as an artifact wants it, content only (the service adds the document
// around it), as tools/export_page.mjs writes the map. three.js comes from cdnjs at the page's
// pinned version; everything else is inline. --standalone writes a whole document for a look
// on this machine.

import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { ROOT, THREE_CDN, bundle, wrap } from "./lib/build_page.mjs";

export const STANDALONE = path.join(ROOT, "src", "standalone");
/** What the page says on itself, always (src/standalone/shell.js holds the same words). */
export const NOTICE = "One view of the Cells map, standing alone";
const FONTS = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap";
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

const escapeHtml = (text) => String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const json = (value) => JSON.stringify(value).replaceAll("<", "\\u003c");

/** "2026-11-16" as "16 November 2026". */
export function longDate(iso) {
  const [year, month, day] = String(iso || "").split("-").map(Number);
  return year && month && day ? `${day} ${MONTHS[month - 1]} ${year}` : String(iso || "");
}

/** The words of `template`, with each {key.path} read from `data` (a missing one is an error, not a blank). */
export function fill(template, data) {
  return String(template || "").replace(/\{([a-z0-9_.|]+?)(\|date)?\}/gi, (_, keys, date) => {
    const read = (key) => key.split(".").reduce((at, part) => (at == null ? undefined : at[part]), data);
    const value = keys.split("||").map(read).find((one) => one !== undefined && one !== null && one !== "");
    if (value === undefined) throw new Error(`the page's stamp names ${keys}, which the carried data does not hold`);
    return escapeHtml(date ? longDate(value) : value);
  });
}

/** The views that have a mount module and a page file. */
export async function views() {
  const names = await readdir(STANDALONE);
  return names.filter((name) => name.endsWith(".page.json")).map((name) => name.slice(0, -".page.json".length)).filter((view) => names.includes(`${view}.js`));
}

/** The page's content for one view: { content, page, data } (page: what its page file says; data: what it carries). */
export async function buildViewPage(view, { three = THREE_CDN } = {}) {
  if (!/^[a-z][a-z0-9_-]*$/.test(view || "")) throw new Error(`not a view's name: ${view}`);
  const page = JSON.parse(await readFile(path.join(STANDALONE, `${view}.page.json`), "utf8"));
  for (const key of ["title", "description", "scene"]) if (!page[key]) throw new Error(`src/standalone/${view}.page.json has no ${key}`);
  const words = page.title.trim().split(/\s+/).length;
  if (words < 2 || words > 4) throw new Error(`the title "${page.title}" is not two to four words`);
  // As the map's build does (tools/lib/build_page.mjs bundle): "three" is the pinned file on cdnjs.
  const script = await bundle(path.join(STANDALONE, `${view}.js`), { three });
  // The scene the panel reads, kept to the keys the page file names; the parts and relations a
  // view standing alone does not draw are left empty, so the scene stays one the model accepts.
  const whole = JSON.parse(await readFile(path.join(ROOT, page.scene.from), "utf8"));
  const scene = page.scene.keep === "all" ? whole : Object.fromEntries((page.scene.keep || []).filter((key) => key in whole).map((key) => [key, whole[key]]));
  for (const key of ["statuses", "relation_kinds", "groups", "entities", "relations"]) scene[key] ??= [];
  const data = {};
  const blocks = [];
  for (const item of page.data || []) {
    if (!/^[a-z][a-z0-9_]*$/.test(item.into || "")) throw new Error(`not a key to carry data under: ${item.into}`);
    if (item.runs_of) {
      // The run files a carried entry names, as the map's page reads them: the page follows the entry's `runs`.
      const runs = data[item.runs_of]?.runs;
      if (!Array.isArray(runs)) throw new Error(`${item.runs_of} is not carried before ${item.into}, or names no runs`);
      data[item.into] = await Promise.all(runs.map(async (run) => ({ ...run, data: JSON.parse(await readFile(path.join(ROOT, run.file), "utf8")) })));
      blocks.push(`<script type="application/json" data-standalone-into="${item.into}" data-source="${escapeHtml(runs.map((run) => run.file).join(" "))}">${json(data[item.into])}</script>`);
      continue;
    }
    const text = await readFile(path.join(ROOT, item.from), "utf8");
    data[item.into] = JSON.parse(text);
    blocks.push(`<script type="application/json" data-standalone-into="${item.into}" data-source="${escapeHtml(item.from)}">${json(data[item.into])}</script>`);
  }
  const css = (await readFile(path.join(ROOT, "src", "page.css"), "utf8")).trim();
  const frame = (await readFile(path.join(STANDALONE, "standalone.css"), "utf8")).trim();
  const stamp = page.stamp ? fill(page.stamp, data) : "";
  const content = [
    `<title>${escapeHtml(page.title)}</title>`,
    `<meta name="description" content="${escapeHtml(page.description)}">`,
    `<meta name="claude:viewport-fit-sides" content="cover">`,
    `<link rel="stylesheet" href="${FONTS}">`,
    `<style>\n${css}\n${frame}\n</style>`,
    "",
    `<p class="standalone-notice" role="note"><strong>${NOTICE}.</strong>${stamp ? ` <span class="standalone-stamp">${stamp}</span>` : ""}</p>`,
    `<cells-standalone data-view="${view}"><p class="boot" id="cells-boot">${escapeHtml(page.boot || "Loading…")}</p></cells-standalone>`,
    `<script type="application/json" data-standalone="scene" data-source="${escapeHtml(page.scene.from)}">${json(scene)}</script>`,
    ...blocks,
    "",
    "<script>",
    "  // If the view never starts (the 3D library is blocked or offline), say so.",
    "  setTimeout(function () {",
    '    if (!customElements.get("cells-standalone")) {',
    '      var boot = document.getElementById("cells-boot");',
    '      if (boot) boot.textContent = "The view could not start: its 3D library did not load. Check the connection and reload.";',
    "    }",
    "  }, 9000);",
    "</script>",
    `<script type="module">\n${script.trim()}\n</script>`,
    "",
  ].join("\n");
  return { content, page, data };
}

async function main() {
  const args = process.argv.slice(2);
  const value = (name, fallback) => (args.includes(name) ? args[args.indexOf(name) + 1] : fallback);
  const view = args.find((arg, index) => !arg.startsWith("--") && args[index - 1] !== "--out");
  if (!view) {
    console.error(`which view? one of: ${(await views()).join(", ") || "(none)"}`);
    process.exit(2);
  }
  const standalone = args.includes("--standalone");
  const out = path.resolve(value("--out", path.join(ROOT, "out", `${view}-preview${standalone ? ".standalone" : ""}.html`)));
  const { content, page } = await buildViewPage(view);
  await mkdir(path.dirname(out), { recursive: true });
  await writeFile(out, standalone ? wrap(content) : content);
  const bytes = Buffer.byteLength(content);
  console.log(`wrote ${path.relative(process.cwd(), out)} (${(bytes / 1024).toFixed(0)} KB${standalone ? ", standalone" : ", artifact content"})`);
  console.log(`title: ${page.title}`);
  console.log(`description: ${page.description}`);
}

if (process.argv[1] && pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url) await main();
