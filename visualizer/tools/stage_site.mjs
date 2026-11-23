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
//                 a description, the site's address as canonical, link-preview tags with the share picture, structured
//                 data for the site and its source code, the style of the text and the cover below, in the page's own
//                 light and dark colours, and what a reader with no script gets in place of the cover), the host profile
//                 (src/core/host.js), the text a reader with no script gets (the About words as HTML, ahead of the
//                 page in the body), the cover a visitor with script sees while the page loads (the page's background
//                 and one turning ring; the About words let through after 20 seconds if the page has not drawn), both
//                 put away by the page once it has drawn (src/ui/about.js), and two rewrites, each
//                 counted: every occurrence of three.js's cdnjs address becomes the release's own copy, and the one
//                 Google Fonts link becomes the release's own sheet. Nothing else of the page changes.
//                 The words are the page's own: the About words its scene carries (data/site/about.json, which they
//                 must equal) and its views' names as its script lists them, so the site's words cannot drift from it.
//   root.html     the same with <base href="/r/<id>/">: copied to SITE/index.html by --release, so that the root page
//                 fetches its own release's files, and keeps fetching them after the pointer moves on.
//   share.jpg     the picture of links shared elsewhere (og:image): the tracked data/site/share.jpg, 1200 by 630, no words.
//   robots.txt, sitemap.xml, llms.txt   the site's root files (every reader may read everything, the root page, and the
//                 site in plain Markdown for an agent, with this release's cards and files), copied to SITE/ by --release.
//   every file the staged folder holds beside the page, at the same path, the same bytes. The staging's own
//                 upload-N.json files are left out; anything the export does not publish is refused (--files LIST, the
//                 export's own cells-architecture.files.json, holds the folder to exactly that list).
//   vendor/three/<version>/   three.module.min.js and its licence, from node_modules/three, at the version the page names.
//   vendor/fonts/             the tracked vendor/fonts/: the families' own released files, their licences and fonts.css.
//   release.json  what the release is (cells.visualizer.release@1): every file with its bytes, SHA-256 and, for JSON, the
//                 format it names; no path of this machine.
//   --compress    a .br and a .gz copy beside each HTML, JSON, JavaScript and CSS file, where it is smaller, for a server
//                 to send as they are.
// --release checks every file of the release against its release.json, then copies its root files to SITE/ (robots.txt,
// sitemap.xml, llms.txt, each written beside and moved into place; a release that has none, an older one, leaves none:
// those of the release before are removed) and its root.html over SITE/index.html, with its compressed copies where the
// release has them (index.html.br, .gz), and says what it wrote and which release the pointer left. Nothing else is touched.
//
// Node's own modules only, besides the viewer's own build_page.mjs and git_state.mjs, and its page's own readers of the
// About words (src/ui/about.js) and of the landing's cards (src/replay/landing.js), which need no document.

import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { constants, existsSync, readFileSync } from "node:fs";
import { chmod, copyFile, lstat, mkdir, readFile, readdir, rename, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import zlib from "node:zlib";
import { ROOT, wrap } from "./lib/build_page.mjs";
import { changedLines } from "./lib/git_state.mjs";
import { aboutOf, licenceUrl, pageFacts, NEW_TAB, TEXT_ELEMENT, COVER_ELEMENT } from "../src/ui/about.js";
import { landingOf, levelOf, verdictsOf, answerOf, standingWords } from "../src/replay/landing.js";
import { formatDate } from "../src/ui/dom.js";

export const RELEASE_FORMAT = "cells.visualizer.release@1";
export const HOST_FORMAT = "cells.visualizer.host@1";
export const PAGE = "cells-architecture.html";
/** The site's address: the canonical of its pages, and the one place it is stated (link previews, structured data, root files). */
export const SITE = "https://cells.eidosoma.ai/";
/** The About words, tracked once (data/site/about.json): a staged page must carry the same in its scene. */
export const ABOUT_FILE = path.join(ROOT, "data", "site", "about.json");
const TRACKED = JSON.parse(readFileSync(ABOUT_FILE, "utf8"));
export const TITLE = TRACKED.title.text;
export const DESCRIPTION = TRACKED.description.text;
/** The picture of a link shared elsewhere: the tracked file and its record, and its name in a release. */
export const SHARE_FILE = path.join(ROOT, "data", "site", "share.jpg");
export const SHARE_RECORD = path.join(ROOT, "data", "site", "share.json");
export const SHARE = "share.jpg";
export const SHARE_SIZE = { width: 1200, height: 630, most: 200_000 };
/** The site's root files, written into each release and put at the site's root with the pointer (--release). */
export const ROOT_FILES = ["robots.txt", "sitemap.xml", "llms.txt"];
export const FONTS_SHEET = "vendor/fonts/fonts.css";
export const threeLocal = (version) => `./vendor/three/${version}/three.module.min.js`;
const THREE_ADDRESS = /https:\/\/cdnjs\.cloudflare\.com\/ajax\/libs\/three\.js\/([0-9][0-9a-z.-]*)\/three\.module\.min\.js/g;
const FONTS_LINK = /<link rel="stylesheet" href="(https:\/\/fonts\.googleapis\.com\/css2\?[^"]*)">/g;
const OUTSIDE_FONTS = /https:\/\/fonts\.(?:googleapis|gstatic)\.com/g;
const STAGING_OWN = /^upload-\d+\.json$/;
// What the export publishes beside the page (tools/export_page.mjs and lib/build_page.mjs), by the path it stands at.
const PUBLISHED = [
  /^runs\/[a-z0-9][a-z0-9._-]*\.json$/,
  /^proteins\/[a-z0-9][a-z0-9_-]*\/(?:shelves|names|members-\d+|unit-evidence)\.json$/,
  /^machines\/[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*\.json$/,
  /^shapes\/[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*\.json$/,
  /^catalogue\/[a-z0-9][a-z0-9_-]*\.json$/,
  /^models\/[a-z0-9-]+\/[a-z0-9_.-]+\.json$/,
  /^cards\.json$/,
  /^cards\.details\.json$/,
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
    { ".html": "text/html; charset=utf-8", ".json": "application/json", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css; charset=utf-8", ".woff2": "font/woff2", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".txt": "text/plain; charset=utf-8", ".xml": "application/xml; charset=utf-8" }[ext] ||
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

const escapeHtml = (text) => String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
/** A view's address on the site, as the page reads it (the query: `lens=`). */
export const viewAddress = (id) => `${SITE}?lens=${encodeURIComponent(id)}`;

/** The scene a page carries: its first JSON block inside the viewer's element, or null. */
function sceneIn(content) {
  try {
    return JSON.parse(/<cells-viewer[^>]*>[\s\S]*?<script type="application\/json">([\s\S]*?)<\/script>/.exec(content)?.[1] || "null");
  } catch {
    return null;
  }
}

/**
 * The words the site says, read from the staged page itself, each counted: the About words its scene carries (which must be
 * the tracked data/site/about.json), its views' ids and names as its script lists them (`LENSES`, once, holding every view
 * the words name), and the map's own record (its revision, date and source base). Returns { about, raw, views, meta }.
 */
export function pageWords(content, { tracked = TRACKED } = {}) {
  const scene = sceneIn(content);
  if (!scene) fail("the staged page carries no scene that can be read");
  if (!scene.about) fail("the staged page carries no About words (data/site/about.json, in its scene as `about`): stage a page exported with them");
  if (JSON.stringify(scene.about) !== JSON.stringify(tracked)) fail("the staged page's About words are not data/site/about.json as it stands: stage a page built from these words, or the site would say other words than its page");
  const about = aboutOf(scene);
  if (!about || !about.title || !about.description || !about.lead.length) fail(`the staged page's About words are not whole ${tracked.format}`);
  const lists = content.split("LENSES = [").length - 1;
  if (lists !== 1) fail(`the page's script lists its views ${lists} times (LENSES): once is what the staging reads`);
  const list = content.slice(content.indexOf("LENSES = ["), content.indexOf("\n];", content.indexOf("LENSES = [")));
  const views = [...list.matchAll(/\{ id: "([a-z]+)", label: "([^"]+)"/g)].map((match) => ({ id: match[1], label: match[2] }));
  for (const view of about.views) if (!views.some((item) => item.id === view.id)) fail(`the About words name the view ${view.id}, and the page's script lists no such view`);
  const meta = scene.meta || {};
  const licence = licenceUrl(about, meta);
  if (about.source.licence && !licence) fail(`the page's scene gives no source base inside ${about.source.url}: its licence cannot be linked at the map's revision`);
  const loading = /<p class="boot" id="cells-boot">([^<]+)<\/p>/.exec(content)?.[1]?.trim();
  if (!loading) fail("the page says nothing while it loads (its #cells-boot): the cover's words for a screen reader are the page's own");
  return { about, raw: scene.about, views: views.filter((view) => about.views.some((item) => item.id === view.id)), meta, licence, colours: pageColours(content), loading };
}

/**
 * The colours of the page's first paint, read from the page's own sheet (src/page.css: the first style that sets the
 * page's tokens, in a staged page or in a release's page alike): light (its :root) and dark (its :root[data-theme="dark"]).
 */
export const COLOUR_TOKENS = ["bg", "fg", "muted", "accent"];
export function pageColours(content) {
  const sheet = [...content.matchAll(/<style>([\s\S]*?)<\/style>/g)].map((match) => match[1]).find((text) => text.includes("--bg:")) || "";
  const block = (selector) => {
    const at = sheet.indexOf(`${selector} {`);
    return at < 0 ? "" : sheet.slice(at, sheet.indexOf("}", at));
  };
  const read = (text) => Object.fromEntries(COLOUR_TOKENS.map((token) => [token, new RegExp(`--${token}:\\s*(#[0-9a-f]{6})\\s*;`, "i").exec(text)?.[1]?.toLowerCase() || null]));
  const colours = { light: read(block(":root")), dark: read(block(':root[data-theme="dark"]')) };
  const lacking = Object.entries(colours).flatMap(([theme, values]) => COLOUR_TOKENS.filter((token) => !values[token]).map((token) => `${theme} --${token}`));
  if (lacking.length) fail(`the page's own sheet gives no ${lacking.join(", ")}: the site's first paint is in the page's own colours`);
  return colours;
}

/** The width and height a JPEG states in its frame header; null where the bytes are not a JPEG. */
export function jpegSize(bytes) {
  if (!(bytes?.length > 4) || bytes[0] !== 0xff || bytes[1] !== 0xd8) return null;
  for (let at = 2; at + 9 < bytes.length; ) {
    if (bytes[at] !== 0xff) return null;
    const marker = bytes[at + 1], length = bytes.readUInt16BE(at + 2);
    if (marker >= 0xc0 && marker <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(marker)) return { width: bytes.readUInt16BE(at + 7), height: bytes.readUInt16BE(at + 5) };
    at += 2 + length;
  }
  return null;
}

/** The share picture and its record, as the tracked files hold them: a JPEG of 1200 by 630 within 200 kB, with words that say what it shows. */
export async function sharePicture({ file = SHARE_FILE, record = SHARE_RECORD } = {}) {
  const bytes = await readFile(file).catch(() => null);
  if (!bytes) fail(`the share picture ${path.relative(ROOT, file)} is not there`);
  const size = jpegSize(bytes);
  if (!size || size.width !== SHARE_SIZE.width || size.height !== SHARE_SIZE.height) fail(`the share picture is not a JPEG of ${SHARE_SIZE.width} by ${SHARE_SIZE.height}${size ? ` (it is ${size.width} by ${size.height})` : ""}`);
  if (bytes.length > SHARE_SIZE.most) fail(`the share picture is ${bytes.length} bytes, more than ${SHARE_SIZE.most}`);
  let said;
  try {
    said = JSON.parse(await readFile(record, "utf8"));
  } catch {
    fail(`the share picture's record ${path.relative(ROOT, record)} cannot be read`);
  }
  if (said.sha256 !== sha256(bytes) || !/\S/.test(said.alt || "")) fail("the share picture's record does not name this picture (its SHA-256), or says nothing of what it shows (alt)");
  return { bytes, ...size, alt: said.alt.trim(), sha256: said.sha256 };
}

/**
 * The structured data of the site and of its source code (schema.org, as JSON-LD). The one name of anyone in it is the
 * credit's organisation (data/site/about.json, `credit`): the site's publisher and the source code's author, by name alone.
 */
export function structuredData(words) {
  const { about } = words;
  const by = about.credit?.organisation ? { "@type": "Organization", name: about.credit.organisation } : null;
  const graph = [
    { "@type": "WebSite", name: about.name, url: SITE, description: about.description, inLanguage: "en", ...(by ? { publisher: by } : {}) },
    { "@type": "SoftwareSourceCode", name: about.name, description: about.lead[0], codeRepository: about.source.url, url: about.source.url, ...(words.licence ? { license: words.licence } : {}), ...(by ? { author: by } : {}) },
  ];
  return { "@context": "https://schema.org", "@graph": graph };
}

/** How long the cover waits for the page before it lets the About words through, without script (seconds). */
export const COVER_WAIT = 20;

/**
 * The look of the text without script and of the cover, in the page's own colours (pageColours) from the first paint:
 * light, or dark where the visitor's system asks for it, and as the page's own sheet has it where a host names a theme
 * on the root (data-theme). The text is hidden (not seen, not reached by the keyboard) while the cover stands; the cover
 * holds the page's background and one big ring in its accent (a sixth of the window's shorter side, between 96 and 160 px:
 * the owner asked for a big one on 20 November 2026), which turns (a slow fade where less motion is asked for). After
 * COVER_WAIT seconds the cover goes and the text stands, by the sheet alone; the page puts both away once it has drawn.
 */
export function siteStyle({ light, dark }) {
  const tokens = (values) => `--site-bg:${values.bg};--site-fg:${values.fg};--site-muted:${values.muted};--site-accent:${values.accent};--site-track:${values.accent}33`;
  const T = `#${TEXT_ELEMENT}`, C = `#${COVER_ELEMENT}`;
  return [
    `:root{${tokens(light)}}`,
    `@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){${tokens(dark)};color-scheme:dark}}`,
    `:root[data-theme="dark"]{${tokens(dark)};color-scheme:dark}`,
    `body{background:var(--site-bg);color:var(--site-fg)}`,
    `${T}{position:fixed;top:0;right:0;bottom:0;left:0;z-index:10;overflow:auto;box-sizing:border-box;padding:28px max(20px,env(safe-area-inset-right,0px)) 48px max(20px,env(safe-area-inset-left,0px));background:var(--site-bg);color:var(--site-fg);font:15px/1.55 var(--font-body,system-ui,-apple-system,"Segoe UI",sans-serif);visibility:hidden;animation:cells-site-through 0s ${COVER_WAIT}s forwards}`,
    `${T}>*{max-width:42rem;margin:0 auto 12px}${T} h1{font:700 30px/1.2 var(--font-display,system-ui,sans-serif);margin-bottom:14px}${T} h2{font:600 13px/1.3 var(--font-display,system-ui,sans-serif);letter-spacing:.07em;text-transform:uppercase;color:var(--site-muted);margin-top:28px;margin-bottom:8px}${T} ul{padding-left:1.2em}${T} li{margin-bottom:8px}${T} a{color:var(--site-accent)}${T} .lead{font-size:17px}${T} .quiet{color:var(--site-muted)}`,
    `${C}{position:fixed;top:0;right:0;bottom:0;left:0;z-index:11;display:grid;place-items:center;background:var(--site-bg);animation:cells-site-gone 0s ${COVER_WAIT}s forwards}`,
    `${C} .cells-ring{box-sizing:border-box;width:clamp(96px,16vmin,160px);height:clamp(96px,16vmin,160px);border-radius:50%;border:clamp(8px,1.3vmin,13px) solid var(--site-track);border-top-color:var(--site-accent);animation:cells-site-turn 1.1s linear infinite}`,
    `${C} .cells-words{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip:rect(0 0 0 0);clip-path:inset(50%);white-space:nowrap;border:0}`,
    `@media (prefers-reduced-motion:reduce){${C} .cells-ring{border-color:var(--site-accent);animation:cells-site-fade 2.4s ease-in-out infinite alternate}}`,
    `@keyframes cells-site-turn{to{transform:rotate(360deg)}}@keyframes cells-site-fade{to{opacity:.35}}`,
    `@keyframes cells-site-through{to{visibility:visible}}@keyframes cells-site-gone{to{visibility:hidden}}`,
  ].join("");
}

/** What a reader with no script gets in place of the cover (a style inside <noscript>, read only where script is off): the text at once, no cover. */
export const NOSCRIPT_STYLE = `#${TEXT_ELEMENT}{visibility:visible;animation:none}#${COVER_ELEMENT}{display:none}`;

/** What the site's staging puts in a page's head, in this order; the root page has its base address first. */
export function siteHead(id, words, { root = false, share } = {}) {
  const { about } = words;
  const profile = JSON.stringify(hostProfileOf(id));
  const meta = (key, name, value) => `<meta ${key}="${name}" content="${escapeHtml(value)}">`;
  const image = `${SITE}r/${id}/${SHARE}`;
  const data = JSON.stringify(structuredData(words)).replaceAll("<", "\\u003c");
  return [
    root ? `<base href="/r/${id}/">` : "",
    `<title>${escapeHtml(about.title)}</title>`,
    meta("name", "description", about.description),
    `<link rel="canonical" href="${SITE}">`,
    // A link's preview: the title, the description, the address and the picture; no words over the picture.
    meta("property", "og:type", "website"),
    meta("property", "og:site_name", about.name),
    meta("property", "og:title", about.title),
    meta("property", "og:description", about.description),
    meta("property", "og:url", SITE),
    meta("property", "og:image", image),
    meta("property", "og:image:type", "image/jpeg"),
    meta("property", "og:image:width", String(share.width)),
    meta("property", "og:image:height", String(share.height)),
    meta("property", "og:image:alt", share.alt),
    meta("name", "twitter:card", "summary_large_image"),
    `<script type="application/ld+json">${data}</script>`,
    `<style>${siteStyle(words.colours)}</style>`,
    `<noscript><style>${NOSCRIPT_STYLE}</style></noscript>`,
    `<script type="application/json" id="cells-host">${profile}</script>`,
  ].join("");
}

/** A link out of the site, in a new tab (as the page's own: src/ui/about.js). */
const away = (url, words) => `<a href="${escapeHtml(url)}" target="${NEW_TAB.target}" rel="${NEW_TAB.rel}">${escapeHtml(words)}</a>`;

/** The text a reader with no script gets: the About words as HTML, ahead of the page, put away by the page once it has drawn. */
export function siteText(id, words) {
  const { about, views, meta } = words;
  const facts = pageFacts(meta, { release: id }, formatDate);
  const extra = [...about.links, ...(about.contact ? [about.contact] : [])];
  return [
    `<section id="${TEXT_ELEMENT}" aria-labelledby="${TEXT_ELEMENT}-title">`,
    `<h1 id="${TEXT_ELEMENT}-title">${escapeHtml(about.name)}</h1>`,
    ...about.lead.map((words_, k) => `<p${k ? "" : ' class="lead"'}>${escapeHtml(words_)}</p>`),
    // The source code in a new tab, as the page's About has it (its licence is not linked there).
    `<p>${away(about.source.url, about.source.label)}</p>`,
    about.credit ? `<p>${escapeHtml(about.credit.text)}</p>` : "",
    extra.length ? `<ul>${extra.map((link) => `<li>${/^mailto:/.test(link.url) ? `<a href="${escapeHtml(link.url)}">${escapeHtml(link.label)}</a>` : away(link.url, link.label)}</li>`).join("")}</ul>` : "",
    `<h2>Views</h2>`,
    `<ul>${views.map((view) => `<li><a href="${viewAddress(view.id)}">${escapeHtml(view.label)}</a>: ${escapeHtml(about.views.find((item) => item.id === view.id).text)}</li>`).join("")}</ul>`,
    about.reading.length ? `<h2>How to read it</h2>${about.reading.map((words_) => `<p>${escapeHtml(words_)}</p>`).join("")}` : "",
    facts.length ? `<h2>This page</h2><p class="quiet">${facts.map(([label, value]) => `${escapeHtml(label)}: ${escapeHtml(value)}`).join(". ")}. <a href="${SITE}llms.txt">llms.txt</a> · <a href="${SITE}r/${id}/release.json">release.json</a></p>` : "",
    `</section>`,
  ].join("");
}

/**
 * What a visitor with script sees while the page loads (siteStyle): the page's background and one ring in its middle, and
 * a status that says in the page's own words (its #cells-boot) that the 3D map is loading. No word of the About text.
 */
export const siteCover = (words) =>
  `<div id="${COVER_ELEMENT}" role="status" aria-labelledby="${COVER_ELEMENT}-words"><div class="cells-ring" aria-hidden="true"></div><span class="cells-words" id="${COVER_ELEMENT}-words">${escapeHtml(words.loading)}</span></div>`;

/** The release's page (index.html) or its root page (root.html), from the rewritten page. */
export const sitePage = (text, id, words, { root = false, share } = {}) => wrap(text, { lang: "en", head: siteHead(id, words, { root, share }), before: `${siteText(id, words)}\n${siteCover(words)}` });

/** robots.txt: every reader may read everything (the release folders under /r/ hold the page's own files), and where the sitemap is. */
export const robotsText = (id) => `# The site of the Cells viewer, release ${id} (written by tools/stage_site.mjs). Every reader may read everything:\n# the page's own files stand under /r/.\nUser-agent: *\nAllow: /\n\nSitemap: ${SITE}sitemap.xml\n`;

/** sitemap.xml: the root, the one page the site has, as of the release's day. */
export const sitemapText = (date) => `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n  <url><loc>${SITE}</loc><lastmod>${date}</lastmod></url>\n</urlset>\n`;

/**
 * llms.txt: the site for an agent, in plain Markdown (the llms.txt form: a title, a summary, then sections of links): the
 * About words, the views, the Experiments view's cards as this release's cards.json has them (each title, its level where
 * the file states one, what it found, its verdicts), the release's files by format, the contracts of the formats in the
 * repository, and the source. `files`: the release's files with their formats; `schemas`: the contracts' file names.
 */
export function llmsText(id, words, { cards = null, files = [], schemas = [] } = {}) {
  const { about, views, meta } = words;
  const md = (text) => String(text).replace(/\s+/g, " ").trim();
  const at = (name) => `${SITE}r/${id}/${name}`;
  const lines = [`# ${about.name}`, "", `> ${md(about.description)}`, "", ...about.lead.flatMap((words_) => [md(words_), ""]), ...about.reading.flatMap((words_) => [md(words_), ""])];
  if (about.credit) lines.push(md(about.credit.text), "");
  for (const [label, value] of pageFacts(meta, { release: id }, formatDate)) lines.push(`- ${label}: ${value}`);
  lines.push(`- Address: ${SITE} (the views below are addresses of it)`, "");
  lines.push("## Views", "", ...views.map((view) => `- [${view.label}](${viewAddress(view.id)}): ${md(about.views.find((item) => item.id === view.id).text)}`), "");
  if (cards) {
    const whole = files.some((file) => file.path === "cards.details.json") ? ` Each card whole (its standing's sources, the record's items, the rows' references) is in [cards.details.json](${at("cards.details.json")}).` : "";
    lines.push("## Experiments", "", `The ${views.find((view) => view.id === "experiments")?.label || "Experiments"} view's cards, band by band, as this release's [cards.json](${at("cards.json")}) has them: each card's title, its level from the Engine map where the file states one, what it found, and its verdicts.${whole}`, "");
    for (const band of landingOf(cards).bands) {
      lines.push(`### ${md(band.label)}`, "");
      if (band.says) lines.push(md(band.says), "");
      for (const card of band.cards) {
        const level = levelOf(card), answer = answerOf(card), first = standingWords(card).first;
        const verdicts = verdictsOf(card).map((verdict) => [verdict.passed === null ? null : verdict.passed ? "passed" : "failed", verdict.count, verdict.day ? formatDate(verdict.day) : null].filter(Boolean).join(", ")).filter(Boolean);
        const parts = [`Level: ${level ? level.label : "none stated"}`, first ? md(first).replace(/\.$/, "") : null, answer ? `Found: ${md(answer.label)}` : null, verdicts.length ? `${verdicts.length === 1 ? "Verdict" : "Verdicts"}: ${verdicts.join("; ")}` : null].filter(Boolean);
        lines.push(`- ${md(card.title || card.id)}. ${parts.join(". ")}.`);
      }
      lines.push("");
    }
  }
  // The files, by their format: a few listed by name; many counted, each in release.json.
  const byFormat = new Map();
  for (const file of files) if (file.format && file.path !== "release.json") byFormat.set(file.format, [...(byFormat.get(file.format) || []), file.path]);
  lines.push("## Data", "", `This release's files, by format. [release.json](${at("release.json")}) (${RELEASE_FORMAT}) lists every one, with its bytes, SHA-256 and format.`, "");
  for (const [format, paths] of [...byFormat].sort((a, b) => a[0].localeCompare(b[0]))) {
    const folders = [...new Set(paths.map((name) => (name.includes("/") ? `${name.slice(0, name.indexOf("/"))}/` : name)))].join(", ");
    lines.push(paths.length <= 12 ? `- ${format}: ${paths.map((name) => `[${name}](${at(name)})`).join(", ")}` : `- ${format}: ${paths.length} files under ${folders}, each in release.json`);
  }
  lines.push("");
  const own = meta.own_source_base_url && /\/blob\/[^/]+\/$/.test(meta.own_source_base_url) ? meta.own_source_base_url : null;
  if (own && schemas.length) {
    lines.push("## Contracts", "", `What each format holds, one page each, under [schema/](${own.replace("/blob/", "/tree/")}visualizer/schema) in the repository:`, "", ...schemas.map((name) => `- [${name}](${own}visualizer/schema/${name})`), "");
  }
  lines.push("## Source", "", `- [${about.source.label}](${about.source.url})${about.source.licence ? `, under the ${about.source.licence.name} licence` : ""}`);
  for (const link of [...about.links, ...(about.contact ? [about.contact] : [])]) lines.push(`- [${md(link.label)}](${link.url})`);
  return `${lines.join("\n")}\n`;
}

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
export async function stageRelease({ staged, site, id, compress = false, files: listPath = null, date = new Date().toISOString().slice(0, 10), three = path.join(ROOT, "node_modules", "three"), fonts = path.join(ROOT, "vendor", "fonts"), share: sharePaths = {}, log = console.log }) {
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

  // The site's words are the page's own (pageWords), and its picture the tracked one (sharePicture).
  const words = pageWords(content);
  const share = await sharePicture(sharePaths);
  const index = sitePage(rewritten.text, id, words, { share });
  const root = sitePage(rewritten.text, id, words, { root: true, share });
  // The cards the release publishes, for its llms.txt; the contracts of its formats, by the files of schema/.
  const cards = beside.includes("cards.json") ? JSON.parse(await readFile(path.join(staged, "cards.json"), "utf8")) : null;
  const schemas = (await readdir(path.join(ROOT, "schema")).catch(() => [])).filter((name) => /^[A-Za-z0-9_.-]+\.(md|json)$/.test(name)).sort();
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
    await put(SHARE, share.bytes);

    // Every file that now stands, with its bytes, hash and format; then the site's root files, made from them (llms.txt
    // lists the files by format); then the compressed copies beside them.
    const entries = [];
    const describe = async (names) => {
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
    };
    await describe(await filesUnder(writing));
    const made = { "robots.txt": robotsText(id), "sitemap.xml": sitemapText(date), "llms.txt": llmsText(id, words, { cards, files: entries, schemas }) };
    for (const name of ROOT_FILES) {
      if (machine.some((place) => made[name].includes(place))) fail(`${name} would name a path of this machine`);
      await put(name, made[name]);
    }
    await describe(ROOT_FILES);
    entries.sort((a, b) => (a.path < b.path ? -1 : 1));
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
      // What the site says of itself, and where each piece of it comes from.
      site: {
        address: SITE,
        words: "the About words the staged page's scene carries (cells.visualizer.about@1), equal to data/site/about.json, and the views' names its script lists",
        share: { path: SHARE, width: share.width, height: share.height, bytes: share.bytes.length, from: "data/site/share.jpg (its record: data/site/share.json)" },
        root_files: ROOT_FILES,
      },
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
    log(`  the site's words: the About words and ${words.views.length} views' names, read from the staged page; the share picture ${SHARE} (${share.width} by ${share.height}, ${share.bytes.length} bytes); root files ${ROOT_FILES.join(", ")} (for --release)`);
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
  // The site's root files go first, each the release's own, written beside and moved into place. A release that has none
  // (one staged before Version 53) leaves none: those of the release before would speak of another release, and are removed.
  const rooted = ROOT_FILES.filter((name) => existsSync(path.join(folder, name)));
  const removed = [];
  for (const name of ROOT_FILES) {
    if (rooted.includes(name)) {
      const writing = path.join(site, `.${name}.${process.pid}`);
      await copyFile(path.join(folder, name), writing);
      await chmod(writing, 0o644);
      await rename(writing, path.join(site, name));
    } else if (existsSync(path.join(site, name))) {
      await rm(path.join(site, name), { force: true });
      removed.push(name);
    }
  }
  const kinds = ["br", "gz"].filter((kind) => existsSync(path.join(folder, `root.html.${kind}`)));
  for (const kind of ["br", "gz"]) if (!kinds.includes(kind)) await rm(path.join(site, `index.html.${kind}`), { force: true });
  for (const suffix of [...kinds.map((kind) => `.${kind}`), ""]) {
    const writing = path.join(site, `.index.html${suffix}.${process.pid}`);
    await copyFile(path.join(folder, `root.html${suffix}`), writing);
    await chmod(writing, 0o644);
    await rename(writing, `${pointer}${suffix}`);
  }
  log(rooted.length ? `wrote ${rooted.join(", ")} at the site's root, ${id}'s own` : `${id} holds no ${ROOT_FILES.join(", ")}: none is written at the site's root`);
  if (removed.length) log(`removed ${removed.join(", ")} from the site's root: they were another release's`);
  log(`wrote index.html${kinds.length ? ` and its compressed copies (${kinds.map((kind) => `index.html.${kind}`).join(", ")})` : ""}: ${id}'s root.html`);
  log(left === undefined ? `the pointer names ${id}; there was no pointer before` : left === null ? `the pointer names ${id}; it was a page that names no release` : left === id ? `the pointer names ${id}, as it did` : `the pointer left ${left} and names ${id}`);
  return { left: left ?? null, now: id, root: rooted, removed };
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
