#!/usr/bin/env node
// The site's own release of the viewer (docs/HOSTING_AND_API.md, sections 9 and 10), made from the folder staged for the
// artifact (tools/stage_publish.py), which it only reads. One build, two targets: the artifact's page stays as it is.
//
//   node tools/stage_site.mjs --staged out/publish-v49 --site SITE --id v49 [--compress] [--files LIST] [--date YYYY-MM-DD]
//   node tools/stage_site.mjs --site SITE --id v49 --release     the pointer (SITE/index.html) is moved to that release
//   node tools/stage_site.mjs --site SITE --retain 3 [--remove]  the releases beyond the newest three, never the pointer's
//
// Staging writes SITE/r/<id>/ and nothing else, once: a release folder that exists is refused, and the folder is written
// beside under another name and moved into place whole, so it is there complete or not at all. In it:
//   index.html    the staged page wrapped in a document (build_page.mjs, wrap), with a head for a site (lang, a title,
//                 a description, the root as canonical), the host profile (src/core/host.js) and two rewrites, each
//                 counted: every occurrence of three.js's cdnjs address becomes the release's own copy, and the one
//                 Google Fonts link becomes the release's own sheet. Nothing else of the page changes.
//   root.html     the same with <base href="/r/<id>/">: copied to SITE/index.html by --release, so that the root page
//                 fetches its own release's files, and keeps fetching them after the pointer moves on.
//   every file the staged folder holds beside the page, at the same path, the same bytes. The staging's own
//                 upload-N.json files are left out; anything the export does not publish is refused (--files LIST, the
//                 export's own cells-architecture.files.json, holds the folder to exactly that list).
//   vendor/three/<version>/   three.module.min.js and its licence, from node_modules/three, at the version the page names.
//   vendor/fonts/             the tracked vendor/fonts/: the families' own released files, their licences and fonts.css.
//   release.json  what the release is (cells.visualizer.release@1): every file with its bytes, SHA-256 and, for JSON, the
//                 format it names; no path of this machine.
//   --compress    a .br and a .gz copy beside each HTML, JSON, JavaScript and CSS file, where it is smaller, for a server
//                 to send as they are.
// --release checks every file of the release against its release.json, then copies its root.html over SITE/index.html
// (written beside and moved into place), with its compressed copies where the release has them (index.html.br, .gz),
// and says which release the pointer left. Nothing else is touched.
//
// Node's own modules only, besides the viewer's own build_page.mjs and git_state.mjs.

import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { constants, existsSync } from "node:fs";
import { chmod, copyFile, lstat, mkdir, readFile, readdir, rename, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import zlib from "node:zlib";
import { ROOT, wrap } from "./lib/build_page.mjs";
import { changedLines } from "./lib/git_state.mjs";

export const RELEASE_FORMAT = "cells.visualizer.release@1";
export const HOST_FORMAT = "cells.visualizer.host@1";
export const PAGE = "cells-architecture.html";
export const TITLE = "Cells: a map of a physics simulator for biology";
export const DESCRIPTION = "A 3D map of Cells, a physics simulator for biology: the parts and laws of its engine, the species, proteins and machines it draws, and replays of its experiments' runs.";
export const FONTS_SHEET = "vendor/fonts/fonts.css";
export const threeLocal = (version) => `./vendor/three/${version}/three.module.min.js`;
const THREE_ADDRESS = /https:\/\/cdnjs\.cloudflare\.com\/ajax\/libs\/three\.js\/([0-9][0-9a-z.-]*)\/three\.module\.min\.js/g;
const FONTS_LINK = /<link rel="stylesheet" href="(https:\/\/fonts\.googleapis\.com\/css2\?[^"]*)">/g;
const OUTSIDE_FONTS = /https:\/\/fonts\.(?:googleapis|gstatic)\.com/g;
const STAGING_OWN = /^upload-\d+\.json$/;
// What the export publishes beside the page (tools/export_page.mjs and lib/build_page.mjs), by the path it stands at.
const PUBLISHED = [
  /^runs\/[a-z0-9][a-z0-9._-]*\.json$/,
  /^proteins\/[a-z0-9][a-z0-9_-]*\/(?:shelves|names|members-\d+)\.json$/,
  /^machines\/[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*\.json$/,
  /^shapes\/[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*\.json$/,
  /^catalogue\/[a-z0-9][a-z0-9_-]*\.json$/,
  /^models\/[a-z0-9-]+\/[a-z0-9_.-]+\.json$/,
  /^cards\.json$/,
  /^stills\/[a-z0-9][a-z0-9._-]*\.(?:jpg|jpeg|png|webp)$/,
];
const ID = /^[a-z0-9][a-z0-9.-]{0,63}$/;
/** The files worth a compressed copy: HTML, JSON, JavaScript and CSS (not pictures or fonts, which are compressed already). */
export const COMPRESSIBLE = /\.(?:html|json|js|mjs|css)$/;

/**
 * The content policy the site's server sends with every page (deploy/caddy/site.caddy holds the same line, and the
 * test holds the two equal): scripts, styles, fonts, pictures and connections from the site itself, and no limit on who
 * may frame it. Inline scripts are allowed, because the page is one document with its script inside it; each release's
 * inline scripts are named by their hashes in its release.json, for a policy that allows only those.
 */
export function sitePolicy() {
  return [
    "default-src 'none'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    "font-src 'self'",
    "img-src 'self' data: blob:",
    "connect-src 'self'",
    "worker-src 'self' blob:",
    "base-uri 'self'",
  ].join("; ");
}

/** The content type a file is served with, by its name. */
export function contentType(name) {
  const ext = path.extname(name).toLowerCase();
  return (
    { ".html": "text/html; charset=utf-8", ".json": "application/json", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css; charset=utf-8", ".woff2": "font/woff2", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".txt": "text/plain; charset=utf-8" }[ext] ||
    (path.basename(name) === "LICENSE" ? "text/plain; charset=utf-8" : "application/octet-stream")
  );
}

const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");
const count = (text, pattern) => (text.match(pattern) || []).length;
const escapeRegExp = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const fail = (message) => {
  throw Object.assign(new Error(message), { refused: true });
};

/** Every regular file under `folder`, as paths relative to it with "/"; a link or anything else that is not a file is refused. */
async function filesUnder(folder, prefix = "") {
  const found = [];
  for (const entry of (await readdir(path.join(folder, prefix), { withFileTypes: true })).sort((a, b) => (a.name < b.name ? -1 : 1))) {
    const name = prefix ? `${prefix}/${entry.name}` : entry.name;
    if (entry.isDirectory()) found.push(...(await filesUnder(folder, name)));
    else if (entry.isFile()) found.push(name);
    else fail(`${name} is neither a file nor a folder (a link?): a release holds files only`);
  }
  return found;
}

/** The families and weights a Google Fonts css2 address asks for: [{ family, weights: [400, …] }]; a style it cannot serve is refused. */
export function fontsAsked(address) {
  const asked = [];
  for (const spec of new URL(address).searchParams.getAll("family")) {
    const [family, axes = ""] = spec.split(":");
    if (axes && !/^wght@\d+(?:;\d+)*$/.test(axes)) fail(`the page asks Google Fonts for ${spec}: only upright weights (wght@…) are served by the site's sheet`);
    asked.push({ family, weights: axes ? axes.slice(5).split(";").map(Number) : [400] });
  }
  if (!asked.length) fail("the page's Google Fonts link names no family");
  return asked;
}

/** The faces a sheet of @font-face rules declares: [{ family, style, from, to, files: [relative address] }]. */
export function fontFaces(css) {
  const faces = [];
  for (const [, body] of css.matchAll(/@font-face\s*\{([^}]*)\}/g)) {
    const family = /font-family:\s*"([^"]+)"/.exec(body)?.[1];
    const weight = /font-weight:\s*(\d+)(?:\s+(\d+))?/.exec(body);
    const style = /font-style:\s*([a-z]+)/.exec(body)?.[1] || "normal";
    const files = [...body.matchAll(/url\("([^"]+)"\)/g)].map((match) => match[1]);
    if (!family || !weight || !files.length) fail(`a rule of the fonts' sheet names no family, weight or file: ${body.trim().slice(0, 120)}`);
    faces.push({ family, style, from: Number(weight[1]), to: Number(weight[2] || weight[1]), files });
  }
  return faces;
}

/**
 * The page as the site serves it, before its document is wrapped around it: every occurrence of three.js's cdnjs address
 * rewritten to the release's own copy, and the Google Fonts link to the release's sheet. Each is counted, and the page is
 * refused where a count is not what it must be: the address of three.js must stand exactly as often as the page's module
 * script imports it (one occurrence missed would load a second copy of three.js), and the fonts' address exactly once,
 * in its link. Returns { text, three: { version, from, to, count }, fonts: { from, to, count, asked } }.
 */
export function rewritePage(content, { faces = null } = {}) {
  const versions = new Set([...content.matchAll(THREE_ADDRESS)].map((match) => match[1]));
  if (versions.size !== 1) fail(versions.size ? `the page names three.js at more than one version (${[...versions].join(", ")})` : "the page names no three.js on cdnjs");
  const version = [...versions][0];
  const from = `https://cdnjs.cloudflare.com/ajax/libs/three.js/${version}/three.module.min.js`;
  const to = threeLocal(version);
  const found = count(content, new RegExp(escapeRegExp(from), "g"));
  const modules = [...content.matchAll(/<script type="module">([\s\S]*?)<\/script>/g)].map((match) => match[1]);
  const imports = modules.reduce((sum, code) => sum + count(code, new RegExp(`(?:\\bfrom\\s*|\\bimport\\s*\\(\\s*|\\bimport\\s+)(["'])${escapeRegExp(from)}\\1`, "g")), 0);
  if (!imports) fail("the page's module script does not import three.js from its cdnjs address");
  if (found !== imports) fail(`the page names three.js's address ${found} times, and its module script imports it ${imports} times: every occurrence must be an import, or the page could load two copies of three.js`);
  const elsewhere = count(content, /cdnjs\.cloudflare\.com/g) - found;
  if (elsewhere) fail(`the page names cdnjs ${elsewhere} more times, for something other than three.js ${version}`);
  if (content.includes(to)) fail(`the page already names ${to}`);

  const links = [...content.matchAll(FONTS_LINK)];
  const outside = count(content, OUTSIDE_FONTS);
  if (links.length !== 1 || outside !== 1) fail(`the page names Google Fonts ${outside} times and links its style sheet ${links.length} times: one link, and no other mention, is what the site's staging rewrites`);
  const fontsFrom = links[0][1];
  const asked = fontsAsked(fontsFrom);
  if (faces) {
    for (const { family, weights } of asked) {
      for (const weight of weights) {
        if (!faces.some((face) => face.family === family && face.style === "normal" && face.from <= weight && weight <= face.to)) fail(`the page asks for ${family} at ${weight}, and the site's fonts hold no such face`);
      }
    }
  }
  let text = content.replaceAll(from, to);
  text = text.replace(links[0][0], `<link rel="stylesheet" href="${FONTS_SHEET}">`);
  // What was rewritten is all that changed, and nothing of the two other parties is left.
  if (count(text, /cdnjs\.cloudflare\.com/g) || count(text, OUTSIDE_FONTS)) fail("an address of cdnjs or Google Fonts is left after the rewrites");
  if (count(text, new RegExp(escapeRegExp(to), "g")) !== found) fail("the release's address of three.js does not stand where cdnjs's stood");
  if (text.replaceAll(to, from).replace(`<link rel="stylesheet" href="${FONTS_SHEET}">`, links[0][0]) !== content) fail("undoing the two rewrites does not give back the staged page");
  return { text, three: { version, from, to, count: found }, fonts: { from: fontsFrom, to: FONTS_SHEET, count: 1, asked } };
}

/** The host profile a release's pages carry (src/core/host.js reads it). */
export const hostProfileOf = (id) => ({ format: HOST_FORMAT, release: id, links: "query", api: null });

/** What the site's staging puts in a page's head, in this order; the root page has its base address first. */
export function siteHead(id, { root = false } = {}) {
  const profile = JSON.stringify(hostProfileOf(id));
  return `${root ? `<base href="/r/${id}/">` : ""}<title>${TITLE}</title><meta name="description" content="${DESCRIPTION}"><link rel="canonical" href="/"><script type="application/json" id="cells-host">${profile}</script>`;
}

/** The release's page (index.html) or its root page (root.html), from the rewritten page. */
export const sitePage = (text, id, { root = false } = {}) => wrap(text, { lang: "en", head: siteHead(id, { root }) });

/** The SHA-256 of each inline script a page runs (not its JSON blocks), as a content policy names them. */
export function inlineScripts(html) {
  const found = [];
  for (const [, attributes = "", code] of html.matchAll(/<script(\s[^>]*)?>([\s\S]*?)<\/script>/g)) {
    const type = /type="([^"]+)"/.exec(attributes)?.[1] || "";
    if (type && type !== "module" && type !== "text/javascript") continue;
    found.push({ type: type === "module" ? "module" : "classic", bytes: Buffer.byteLength(code), csp: `'sha256-${createHash("sha256").update(code).digest("base64")}'` });
  }
  return found;
}

/** The scene the page carries (its first JSON block inside the viewer's element): its engine revision and whether that tree was clean. */
function sceneOf(content) {
  try {
    const meta = JSON.parse(/<cells-viewer[^>]*>[\s\S]*?<script type="application\/json">([\s\S]*?)<\/script>/.exec(content)?.[1] || "{}").meta || {};
    return { revision: meta.revision || null, dirty: typeof meta.dirty === "boolean" ? meta.dirty : null };
  } catch {
    return { revision: null, dirty: null };
  }
}

/** The viewer's commit, where the staging ran, and whether its folder held no uncommitted change of the page. */
function viewerState() {
  try {
    const commit = execFileSync("git", ["-C", ROOT, "rev-parse", "HEAD"], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
    const status = execFileSync("git", ["-C", ROOT, "status", "--porcelain", "--", "."], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
    return { commit, clean: changedLines(status).length === 0 };
  } catch {
    return { commit: null, clean: null };
  }
}

/** A release's ids in order: by the numbers in them, so that v9 comes before v10. */
const byId = (a, b) => a.localeCompare(b, "en", { numeric: true });

/** The release the page at `file` names in its host profile; null where it names none, undefined where there is no file. */
async function releaseNamed(file) {
  if (!existsSync(file)) return undefined;
  const block = /<script type="application\/json" id="cells-host">([\s\S]*?)<\/script>/.exec(await readFile(file, "utf8"))?.[1];
  try {
    return block ? JSON.parse(block).release ?? null : null;
  } catch {
    return null;
  }
}

/** Whether a release's files are still what its release.json says: every file listed, the same bytes, and nothing more. Returns the problems. */
export async function verifyRelease(folder) {
  const problems = [];
  let record;
  try {
    record = JSON.parse(await readFile(path.join(folder, "release.json"), "utf8"));
  } catch {
    return ["its release.json cannot be read"];
  }
  if (record.format !== RELEASE_FORMAT) return [`its release.json is not ${RELEASE_FORMAT}`];
  const expected = new Map();
  for (const file of record.files || []) {
    expected.set(file.path, file);
    for (const kind of ["br", "gz"]) if (file[kind]) expected.set(`${file.path}.${kind}`, file[kind]);
  }
  const standing = new Set((await filesUnder(folder)).filter((name) => name !== "release.json"));
  for (const name of standing) if (!expected.has(name)) problems.push(`${name} stands in the release and its release.json does not list it`);
  for (const [name, file] of expected) {
    if (!standing.has(name)) {
      problems.push(`${name} is listed and not there`);
      continue;
    }
    const bytes = await readFile(path.join(folder, name));
    if (bytes.length !== file.bytes || sha256(bytes) !== file.sha256) problems.push(`${name} is not the file its release.json lists`);
  }
  return problems;
}

/** Compressed copies of `bytes`: gzip at level 9, brotli at quality 11, each kept only where it is smaller. */
async function compressed(bytes, name) {
  const gzip = await promisify(zlib.gzip)(bytes, { level: 9 });
  const brotli = await promisify(zlib.brotliCompress)(bytes, {
    params: { [zlib.constants.BROTLI_PARAM_QUALITY]: 11, [zlib.constants.BROTLI_PARAM_SIZE_HINT]: bytes.length, [zlib.constants.BROTLI_PARAM_MODE]: name.endsWith(".json") || name.endsWith(".html") || name.endsWith(".css") || name.endsWith(".js") ? zlib.constants.BROTLI_MODE_TEXT : zlib.constants.BROTLI_MODE_GENERIC },
  });
  return { gz: gzip.length < bytes.length ? gzip : null, br: brotli.length < bytes.length ? brotli : null };
}

/** Run `work` over `items`, `width` at a time. */
async function pool(items, width, work) {
  let next = 0;
  await Promise.all(Array.from({ length: Math.min(width, items.length) }, async () => {
    while (next < items.length) await work(items[next++]);
  }));
}

const megabytes = (bytes) => `${(bytes / 1e6).toFixed(2)} MB`;

/** Stage one release; returns what it wrote. */
export async function stageRelease({ staged, site, id, compress = false, files: listPath = null, date = new Date().toISOString().slice(0, 10), three = path.join(ROOT, "node_modules", "three"), fonts = path.join(ROOT, "vendor", "fonts"), log = console.log }) {
  if (!ID.test(id || "")) fail(`a release's id is a short name of small letters, digits, dots and dashes (v49), not ${JSON.stringify(id)}`);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) fail(`--date is a day (YYYY-MM-DD), not ${date}`);
  const releases = path.join(site, "r");
  const target = path.join(releases, id);
  if (existsSync(target)) fail(`the release ${id} exists (${path.relative(site, target)}): a release is written once and never written into again`);
  if (!existsSync(path.join(staged, PAGE))) fail(`the staged folder holds no ${PAGE}`);

  // What the staged folder holds: the page, the staging's own lists, and the files the export publishes, nothing else.
  const held = await filesUnder(staged);
  const beside = held.filter((name) => name !== PAGE && !STAGING_OWN.test(name));
  const unknown = beside.filter((name) => !PUBLISHED.some((pattern) => pattern.test(name)));
  if (unknown.length) fail(`the staged folder holds ${unknown.length} file(s) the export does not publish, for one ${unknown[0]}: a staged folder holds the page, its files and the staging's own upload-N.json, and nothing else`);
  if (listPath) {
    const listed = new Set(Object.keys(JSON.parse(await readFile(listPath, "utf8"))));
    const extra = beside.filter((name) => !listed.has(name)), missing = [...listed].filter((name) => !beside.includes(name));
    if (extra.length || missing.length) fail(`the staged folder is not the export's list: ${extra.length} more (${extra.slice(0, 2).join(", ")}), ${missing.length} missing (${missing.slice(0, 2).join(", ")})`);
  }

  const content = await readFile(path.join(staged, PAGE), "utf8");
  if (/^\s*<!doctype/i.test(content)) fail("the staged page is a whole document: a staged page is the artifact's content, which the site's staging wraps");
  const sheet = await readFile(path.join(fonts, "fonts.css"), "utf8");
  const faces = fontFaces(sheet);
  const fontFiles = await filesUnder(fonts);
  for (const face of faces) for (const file of face.files) if (!fontFiles.includes(file)) fail(`the fonts' sheet names ${file}, which vendor/fonts does not hold`);
  const rewritten = rewritePage(content, { faces });
  const version = JSON.parse(await readFile(path.join(three, "package.json"), "utf8")).version;
  if (version !== rewritten.three.version) fail(`the page names three.js ${rewritten.three.version} and node_modules holds ${version}: the release serves the version the page was built for`);

  const index = sitePage(rewritten.text, id);
  const root = sitePage(rewritten.text, id, { root: true });
  // No path of this machine in what the release says of itself.
  const machine = [ROOT, path.resolve(staged), path.resolve(site), os.homedir()].filter((text) => text.length > 1);
  for (const [name, text] of [["the page", index], ["the fonts' sheet", sheet]]) {
    const found = machine.find((text_) => text.includes(text_));
    if (found) fail(`${name} names a path of this machine`);
  }

  await mkdir(releases, { recursive: true });
  const writing = path.join(releases, `.${id}.writing-${process.pid}`);
  await rm(writing, { recursive: true, force: true });
  await mkdir(writing);
  try {
    const put = async (name, bytes) => {
      await mkdir(path.dirname(path.join(writing, name)), { recursive: true });
      await writeFile(path.join(writing, name), bytes, { flag: "wx" });
    };
    const copy = async (name, source) => {
      await mkdir(path.dirname(path.join(writing, name)), { recursive: true });
      await copyFile(source, path.join(writing, name), constants.COPYFILE_EXCL);
    };
    await put("index.html", index);
    await put("root.html", root);
    for (const name of beside) await copy(name, path.join(staged, name));
    const threeAt = `vendor/three/${version}`;
    await copy(`${threeAt}/three.module.min.js`, path.join(three, "build", "three.module.min.js"));
    await copy(`${threeAt}/LICENSE`, path.join(three, "LICENSE"));
    for (const name of fontFiles) await copy(`vendor/fonts/${name}`, path.join(fonts, name));

    // Every file that now stands, with its bytes, hash and format; then the compressed copies beside them.
    const names = await filesUnder(writing);
    const entries = [];
    for (const name of names) {
      const bytes = await readFile(path.join(writing, name));
      let format = null;
      if (name.endsWith(".json")) {
        try {
          const parsed = JSON.parse(bytes.toString("utf8"));
          format = typeof parsed?.format === "string" ? parsed.format : null;
        } catch {
          fail(`${name} is not JSON`);
        }
      }
      entries.push({ path: name, bytes: bytes.length, sha256: sha256(bytes), format });
    }
    let added = { gz: 0, br: 0 };
    if (compress) {
      const began = Date.now();
      const worth = entries.filter((entry) => COMPRESSIBLE.test(entry.path));
      await pool(worth, Math.max(1, Math.min(4, os.availableParallelism?.() || 4)), async (entry) => {
        const made = await compressed(await readFile(path.join(writing, entry.path)), entry.path);
        for (const kind of ["br", "gz"]) {
          if (!made[kind]) continue;
          await put(`${entry.path}.${kind}`, made[kind]);
          entry[kind] = { bytes: made[kind].length, sha256: sha256(made[kind]) };
          added[kind] += made[kind].length;
        }
      });
      log(`compressed copies beside ${worth.length} files: brotli ${megabytes(added.br)}, gzip ${megabytes(added.gz)} more on disk (${((Date.now() - began) / 1000).toFixed(0)} s)`);
    }
    const scene = sceneOf(content);
    const record = {
      format: RELEASE_FORMAT,
      release: id,
      date,
      // The viewer's commit where the site's staging ran. The page itself was built where the staged folder was made,
      // which may be an earlier commit: the record says so beside the commit, so that nobody takes one for the other.
      viewer: { ...viewerState(), note: "the viewer's commit where the site's staging ran; the page was built where its staged folder was made, at that commit or an earlier one" },
      engine: { revision: scene.revision, dirty: scene.dirty, note: "the engine revision the page's scene states" },
      staged: { folder: path.basename(path.resolve(staged)), page: { bytes: Buffer.byteLength(content), sha256: sha256(Buffer.from(content)) } },
      host: hostProfileOf(id),
      rewrites: [
        { what: "three.js", from: rewritten.three.from, to: rewritten.three.to, count: rewritten.three.count },
        { what: "fonts", from: rewritten.fonts.from, to: rewritten.fonts.to, count: rewritten.fonts.count },
      ],
      inline_scripts: inlineScripts(index),
      totals: { files: entries.length, bytes: entries.reduce((sum, entry) => sum + entry.bytes, 0), br_bytes: added.br, gz_bytes: added.gz },
      files: entries,
    };
    const text = JSON.stringify(record, null, 1) + "\n";
    if (machine.some((place) => text.includes(place))) fail("release.json would name a path of this machine");
    await put("release.json", text);
    for (const name of await filesUnder(writing)) await chmod(path.join(writing, name), 0o444);
    const problems = await verifyRelease(writing);
    if (problems.length) fail(`the release does not match its own release.json: ${problems[0]}`);
    if (existsSync(target)) fail(`the release ${id} appeared while it was being written`);
    await rename(writing, target);
    log(`wrote ${path.relative(site, target)}/: ${entries.length} files, ${megabytes(record.totals.bytes)} (the page ${megabytes(Buffer.byteLength(index))}; ${beside.length} files of the staged folder, as they are)`);
    log(`  three.js: ${rewritten.three.count} occurrences of ${rewritten.three.from} -> ${rewritten.three.to}`);
    log(`  fonts: ${rewritten.fonts.count} link to Google Fonts -> ${FONTS_SHEET} (${rewritten.fonts.asked.map((item) => `${item.family} ${item.weights.join("/")}`).join("; ")})`);
    log(`  the pointer is not moved: node tools/stage_site.mjs --site SITE --id ${id} --release`);
    return { target, record };
  } catch (error) {
    await rm(writing, { recursive: true, force: true });
    throw error;
  }
}

/** Move the pointer: the release's root.html over SITE/index.html, once its files are checked against its release.json. */
export async function movePointerTo({ site, id, log = console.log }) {
  const folder = path.join(site, "r", id || "");
  if (!ID.test(id || "") || !existsSync(path.join(folder, "release.json"))) fail(`no release ${id} in ${path.basename(site)}/r/`);
  const problems = await verifyRelease(folder);
  if (problems.length) fail(`the release ${id} no longer matches its release.json (${problems.length}: ${problems.slice(0, 3).join("; ")}): the pointer is not moved`);
  if ((await releaseNamed(path.join(folder, "root.html"))) !== id) fail(`the release's root.html does not name ${id}`);
  // A server sends a compressed copy where one stands (deploy/caddy/site.caddy), so the pointer's copies are the release's
  // own: its root.html.br and root.html.gz go with it, each written beside and moved into place, the compressed ones first
  // and the pointer last. Whichever of the three a visitor is sent meanwhile is a whole page of a release that stands.
  // Where the release has no copy of a kind (staged without --compress), one that stands beside the pointer is an older
  // page's, and is removed before the pointer moves.
  const pointer = path.join(site, "index.html");
  const left = await releaseNamed(pointer);
  const kinds = ["br", "gz"].filter((kind) => existsSync(path.join(folder, `root.html.${kind}`)));
  for (const kind of ["br", "gz"]) if (!kinds.includes(kind)) await rm(path.join(site, `index.html.${kind}`), { force: true });
  for (const suffix of [...kinds.map((kind) => `.${kind}`), ""]) {
    const writing = path.join(site, `.index.html${suffix}.${process.pid}`);
    await copyFile(path.join(folder, `root.html${suffix}`), writing);
    await chmod(writing, 0o644);
    await rename(writing, `${pointer}${suffix}`);
  }
  log(left === undefined ? `the pointer names ${id}; there was no pointer before` : left === null ? `the pointer names ${id}; it was a page that names no release` : left === id ? `the pointer names ${id}, as it did` : `the pointer left ${left} and names ${id}`);
  return { left: left ?? null, now: id };
}

/** The releases beyond the newest `keep`, never the one the pointer names; with `remove`, they are removed. */
export async function retain({ site, keep, remove = false, log = console.log }) {
  if (!Number.isInteger(keep) || keep < 1) fail("--retain takes how many releases to keep, one or more");
  const releases = path.join(site, "r");
  const pointer = await releaseNamed(path.join(site, "index.html"));
  const found = [];
  for (const entry of existsSync(releases) ? await readdir(releases, { withFileTypes: true }) : []) {
    if (!entry.isDirectory()) continue;
    if (entry.name.startsWith(".")) {
      log(`  ${entry.name}: left by a staging that did not finish (not a release; remove it by hand)`);
      continue;
    }
    let date = null;
    try {
      date = JSON.parse(await readFile(path.join(releases, entry.name, "release.json"), "utf8")).date || null;
    } catch {
      log(`  ${entry.name}: no release.json, not a release: left as it is`);
      continue;
    }
    found.push({ id: entry.name, date });
  }
  found.sort((a, b) => (a.date === b.date ? byId(b.id, a.id) : a.date < b.date ? 1 : -1));
  const kept = found.slice(0, keep).map((item) => item.id);
  const beyond = found.slice(keep).filter((item) => item.id !== pointer);
  log(`releases, newest first: ${found.map((item) => `${item.id} (${item.date})`).join(", ") || "none"}; the pointer names ${pointer ?? "none"}`);
  log(`kept: ${[...new Set([...kept, ...(pointer && found.some((item) => item.id === pointer) ? [pointer] : [])])].join(", ") || "none"}`);
  log(beyond.length ? `beyond the newest ${keep}: ${beyond.map((item) => item.id).join(", ")}${remove ? "" : " (--remove removes them)"}` : `nothing beyond the newest ${keep}`);
  if (remove) {
    for (const item of beyond) {
      await rm(path.join(releases, item.id), { recursive: true, force: true });
      log(`  removed ${item.id}`);
    }
  }
  return { kept, beyond: beyond.map((item) => item.id) };
}

if (import.meta.url === `file://${process.argv[1]}` || process.argv[1]?.endsWith("stage_site.mjs")) {
  const args = process.argv.slice(2);
  const value = (name) => (args.includes(name) ? args[args.indexOf(name) + 1] : undefined);
  const site = value("--site");
  try {
    if (!site) fail("--site names the site's folder");
    if (value("--staged") && (args.includes("--release") || args.includes("--retain"))) fail("--release and --retain are steps of their own, never run with a staging");
    const began = Date.now();
    if (args.includes("--retain")) await retain({ site: path.resolve(site), keep: Number(value("--retain")), remove: args.includes("--remove") });
    else if (args.includes("--release")) await movePointerTo({ site: path.resolve(site), id: value("--id") });
    else {
      if (!value("--staged")) fail("--staged names the folder staged for the artifact (tools/stage_publish.py)");
      await stageRelease({
        staged: path.resolve(value("--staged")),
        site: path.resolve(site),
        id: value("--id"),
        compress: args.includes("--compress"),
        files: value("--files") ? path.resolve(value("--files")) : null,
        date: value("--date") || undefined,
        three: value("--three") ? path.resolve(value("--three")) : undefined,
        fonts: value("--fonts") ? path.resolve(value("--fonts")) : undefined,
      });
      console.log(`(${((Date.now() - began) / 1000).toFixed(1)} s)`);
    }
  } catch (error) {
    console.error(error.refused ? `refused: ${error.message}` : error.stack || String(error));
    process.exit(1);
  }
}
