// The site's release of the viewer (tools/stage_site.mjs; docs/HOSTING_AND_API.md, sections 9 and 10), on a made-up
// staged folder of a few small files and a page that names the two outside addresses the real page names: the page
// inside a release is the staged page but for the declared insertions and rewrites, each counted; every other file is
// the same bytes; release.json lists exactly what stands; a release is written once; the pointer step copies root.html
// and nothing else; a count other than the expected stops the staging; and no path of the machine is written. Also the
// host profile's reader (src/core/host.js), and the deploy example's content policy against the staging's own.
// No browser and no world: about 1 second.
//
//   node --test tests/stage_site.test.mjs

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { chmod, mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import zlib from "node:zlib";
import { THREE_CDN, wrap } from "../tools/lib/build_page.mjs";
import { DESCRIPTION, TITLE, movePointerTo, retain, sitePolicy, stageRelease } from "../tools/stage_site.mjs";
import { HOST_DEFAULTS, hostProfile, readHost } from "../src/core/host.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const quiet = () => {};
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
// The real page's link to Google Fonts, as src/page.html writes it.
const FONTS_LINK = readFileSync(path.join(ROOT, "src", "page.html"), "utf8").split("\n").find((line) => line.includes("fonts.googleapis.com"));
const LOCAL_THREE = "./vendor/three/0.170.0/three.module.min.js";

/** A page as the export writes it (no document of its own), whose module script imports three.js twice. */
const PAGE = (scene = '{"format":"cells.visualizer.scene@1","meta":{"revision":"abc12345","dirty":false}}', link = FONTS_LINK) =>
  `<title>Cells</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n${link}\n<style>\nbody { margin: 0 }\n</style>\n\n<cells-viewer id="cells-viewer">\n  <p class="boot" id="cells-boot">Loading…</p>\n  <script type="application/json">${scene}</script>\n</cells-viewer>\n\n<script>\n  setTimeout(function () {}, 9000);\n</script>\n<script type="module">\nimport * as three_star from "${THREE_CDN}";\nimport {\n  Vector3\n} from "${THREE_CDN}";\ncustomElements.define("cells-viewer", class extends HTMLElement {});\n</script>\n`;

const BESIDE = {
  "runs/sheet--a.json": '{"format":"cells.visualizer.replay@1","run":"sheet--a"}',
  "runs/sheet--a.parts.json": '{"format":"cells.visualizer.replay_parts@1","parts":[]}',
  "proteins/worm/shelves.json": '{"format":"cells.visualizer.species_proteins@1"}',
  "cards.json": '{"format":"cells.visualizer.experiment_cards@1","cards":[]}',
  "stills/sheet.jpg": Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0, 1, 2, 3, 0xff, 0xd9]),
};

/** A made-up staged folder, a stand-in for three.js in node_modules, and an empty site. */
async function setUp({ page = PAGE(), beside = BESIDE, version = "0.170.0" } = {}) {
  const folder = await mkdtemp(path.join(os.tmpdir(), "stage-site-"));
  const staged = path.join(folder, "publish-v1");
  for (const [name, text] of Object.entries({ "cells-architecture.html": page, "upload-1.json": '[{"path":"cards.json"}]', ...beside })) {
    await mkdir(path.dirname(path.join(staged, name)), { recursive: true });
    await writeFile(path.join(staged, name), text);
  }
  const three = path.join(folder, "three");
  await mkdir(path.join(three, "build"), { recursive: true });
  await writeFile(path.join(three, "package.json"), JSON.stringify({ name: "three", version }));
  await writeFile(path.join(three, "build", "three.module.min.js"), "export const Vector3 = 1;\n");
  await writeFile(path.join(three, "LICENSE"), "The MIT License\n");
  return { folder, staged, three, site: path.join(folder, "site") };
}

/** Every file under a folder, with its hash: { "r/v1/index.html": "…" }. */
async function snapshot(folder, prefix = "") {
  const found = {};
  if (!existsSync(path.join(folder, prefix))) return found;
  for (const entry of await readdir(path.join(folder, prefix), { withFileTypes: true })) {
    const name = prefix ? `${prefix}/${entry.name}` : entry.name;
    if (entry.isDirectory()) Object.assign(found, await snapshot(folder, name));
    else found[name] = sha(await readFile(path.join(folder, name)));
  }
  return found;
}

test("a release holds the staged page but for the declared insertions and the two counted rewrites, and every other file as it was", async () => {
  const { folder, staged, three, site } = await setUp();
  try {
    const before = await snapshot(staged);
    const { record } = await stageRelease({ staged, site, id: "v1", date: "2026-11-19", three, log: quiet });
    const release = path.join(site, "r", "v1");
    const page = await readFile(path.join(staged, "cells-architecture.html"), "utf8");
    const index = await readFile(path.join(release, "index.html"), "utf8");
    // Two rewrites, each counted: three.js's address as often as the module imports it, the fonts' link once.
    assert.equal(page.split(THREE_CDN).length - 1, 2);
    const body = page.replaceAll(THREE_CDN, LOCAL_THREE).replace(FONTS_LINK, '<link rel="stylesheet" href="vendor/fonts/fonts.css">');
    const head = `<title>${TITLE}</title><meta name="description" content="${DESCRIPTION}"><link rel="canonical" href="/"><script type="application/json" id="cells-host">{"format":"cells.visualizer.host@1","release":"v1","links":"query","api":null}</script>`;
    assert.equal(index, wrap(body, { lang: "en", head }), "the page is wrapped as the artifact host wraps it, with lang, a title, a description, the canonical root and the host profile, and nothing else");
    assert.equal(index.split(LOCAL_THREE).length - 1, 2);
    assert.ok(!/cdnjs\.cloudflare\.com|fonts\.googleapis\.com|fonts\.gstatic\.com/.test(index), "no address of the two other parties is left");
    assert.deepEqual(record.rewrites.map((item) => [item.what, item.count, item.to]), [["three.js", 2, LOCAL_THREE], ["fonts", 1, "vendor/fonts/fonts.css"]]);
    // The root page is the same with its base address, and nothing more.
    assert.equal(await readFile(path.join(release, "root.html"), "utf8"), index.replace(`<title>${TITLE}`, `<base href="/r/v1/"><title>${TITLE}`));
    // Every other file of the staged folder, the same bytes at the same path; the staging's own list left out.
    for (const [name, content] of Object.entries(BESIDE)) assert.deepEqual(await readFile(path.join(release, name)), Buffer.from(content), name);
    assert.ok(!existsSync(path.join(release, "upload-1.json")));
    assert.equal(await readFile(path.join(release, "vendor/three/0.170.0/three.module.min.js"), "utf8"), "export const Vector3 = 1;\n");
    assert.ok(existsSync(path.join(release, "vendor/three/0.170.0/LICENSE")));
    for (const name of ["fonts.css", "inter/Inter-Regular.woff2", "inter/LICENSE.txt", "space-grotesk/SpaceGrotesk-Variable.woff2", "space-grotesk/OFL.txt"]) {
      assert.deepEqual(await readFile(path.join(release, "vendor/fonts", name)), await readFile(path.join(ROOT, "vendor/fonts", name)), name);
    }
    // release.json lists exactly the files that stand there, with their bytes, hashes and formats.
    const stands = await snapshot(release);
    delete stands["release.json"];
    const listed = JSON.parse(await readFile(path.join(release, "release.json"), "utf8"));
    assert.equal(listed.format, "cells.visualizer.release@1");
    assert.deepEqual(Object.fromEntries(listed.files.map((file) => [file.path, file.sha256])), stands);
    for (const file of listed.files) assert.equal(file.bytes, (await readFile(path.join(release, file.path))).length, file.path);
    assert.equal(listed.files.find((file) => file.path === "runs/sheet--a.json").format, "cells.visualizer.replay@1");
    assert.equal(listed.files.find((file) => file.path === "index.html").format, null);
    assert.deepEqual([listed.release, listed.date, listed.staged.folder, listed.engine.revision], ["v1", "2026-11-19", "publish-v1", "abc12345"]);
    assert.equal(listed.staged.page.sha256, sha(Buffer.from(page)));
    assert.ok(listed.viewer.commit === null || /^[0-9a-f]{40}$/.test(listed.viewer.commit));
    assert.deepEqual(listed.inline_scripts.map((script) => script.type), ["classic", "module"], "the JSON blocks are not scripts that run");
    // The staged folder is only read, and no path of the machine stands in any file written.
    assert.deepEqual(await snapshot(staged), before);
    const places = [folder, ROOT, os.homedir(), "/home/", "/mnt/", "/Users/"];
    for (const name of Object.keys(await snapshot(site))) {
      const text = (await readFile(path.join(site, name))).toString("latin1");
      for (const place of places) assert.ok(!text.includes(place), `${name} names ${place}`);
    }
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});

test("a release is written once: a second staging into the same id is refused and changes nothing", async () => {
  const { folder, staged, three, site } = await setUp();
  try {
    await stageRelease({ staged, site, id: "v1", three, log: quiet });
    const before = await snapshot(site);
    await assert.rejects(stageRelease({ staged, site, id: "v1", three, log: quiet }), /exists.*written once/);
    const cli = spawnSync(process.execPath, [path.join(ROOT, "tools", "stage_site.mjs"), "--staged", staged, "--site", site, "--id", "v1", "--three", three], { encoding: "utf8" });
    assert.equal(cli.status, 1);
    assert.match(cli.stderr, /^refused: the release v1 exists/);
    assert.deepEqual(await snapshot(site), before);
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});

test("the pointer step checks the release, copies its root.html over the pointer with its compressed copies and nothing else, and says which release it left", async () => {
  const { folder, staged, three, site } = await setUp();
  try {
    await stageRelease({ staged, site, id: "v1", three, log: quiet });
    await stageRelease({ staged, site, id: "v2", three, log: quiet, compress: true });
    assert.equal((await snapshot(site))["index.html"], undefined, "staging never moves the pointer");
    const said = [];
    await movePointerTo({ site, id: "v1", log: (line) => said.push(line) });
    const before = await snapshot(site);
    const moved = await movePointerTo({ site, id: "v2", log: (line) => said.push(line) });
    const after = await snapshot(site);
    assert.deepEqual(moved, { left: "v1", now: "v2" });
    assert.match(said.join("\n"), /there was no pointer before[\s\S]*the pointer left v1 and names v2/);
    // The pointer and its two compressed copies, which a server sends in its place: the release's own, and nothing else.
    assert.deepEqual(Object.keys(after).filter((name) => after[name] !== before[name]).sort(), ["index.html", "index.html.br", "index.html.gz"], "only the pointer and its copies changed");
    assert.equal(after["index.html"], after["r/v2/root.html"]);
    for (const kind of ["br", "gz"]) assert.equal(after[`index.html.${kind}`], after[`r/v2/root.html.${kind}`], `the pointer's ${kind} copy is the release's`);
    // A release whose files no longer match its release.json does not get the pointer.
    const touched = path.join(site, "r", "v1", "cards.json");
    await chmod(touched, 0o644);
    await writeFile(touched, '{"format":"cells.visualizer.experiment_cards@1","cards":["changed"]}');
    await assert.rejects(movePointerTo({ site, id: "v1", log: quiet }), /no longer matches its release\.json.*cards\.json/);
    assert.equal((await snapshot(site))["index.html"], after["index.html"]);
    assert.equal((await snapshot(site))["index.html.br"], after["index.html.br"]);
    // Back to a release staged without compressed copies: the copies beside the pointer are the other release's, and go.
    await stageRelease({ staged, site, id: "v3", three, log: quiet });
    await movePointerTo({ site, id: "v3", log: quiet });
    const back = await snapshot(site);
    assert.equal(back["index.html"], back["r/v3/root.html"]);
    assert.ok(!("index.html.br" in back) && !("index.html.gz" in back), "no compressed copy of another release's page is left beside the pointer");
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});

test("a page, a folder or node_modules other than expected stops the staging, and nothing is written", async () => {
  const cases = [
    // One more occurrence of three.js's address than the module imports (here in the scene's words).
    [{ page: PAGE(`{"format":"cells.visualizer.scene@1","note":"${THREE_CDN}"}`) }, /names three\.js's address 3 times, and its module script imports it 2 times/],
    // The fonts named twice.
    [{ page: PAGE(undefined, `${FONTS_LINK}\n<!-- https://fonts.gstatic.com -->`) }, /names Google Fonts 2 times/],
    // A weight the site's sheet does not hold.
    [{ page: PAGE(undefined, FONTS_LINK.replace("wght@400;500;600", "wght@400;700")) }, /asks for Inter at 700/],
    // A file the export does not publish.
    [{ beside: { ...BESIDE, "notes.txt": "not published" } }, /1 file\(s\) the export does not publish, for one notes\.txt/],
    // Another three.js in node_modules than the page names.
    [{ version: "0.171.0" }, /names three\.js 0\.170\.0 and node_modules holds 0\.171\.0/],
  ];
  for (const [given, refusal] of cases) {
    const { folder, staged, three, site } = await setUp(given);
    try {
      await assert.rejects(stageRelease({ staged, site, id: "v1", three, log: quiet }), refusal);
      assert.deepEqual(await snapshot(site), {}, `nothing is written (${refusal})`);
    } finally {
      await rm(folder, { recursive: true, force: true });
    }
  }
});

test("compressed copies unpack to their files, and the retention lists what lies beyond the newest, never the pointer's release", async () => {
  const { folder, staged, three, site } = await setUp();
  try {
    const { record } = await stageRelease({ staged, site, id: "v1", date: "2026-11-01", three, log: quiet, compress: true });
    const release = path.join(site, "r", "v1");
    const copies = record.files.filter((file) => file.br || file.gz);
    assert.ok(copies.some((file) => file.path === "index.html") && !copies.some((file) => /\.(jpg|woff2)$/.test(file.path)), "HTML, JSON, JavaScript and CSS, not pictures or fonts");
    for (const file of copies) {
      const raw = await readFile(path.join(release, file.path));
      if (file.br) assert.deepEqual(zlib.brotliDecompressSync(await readFile(path.join(release, `${file.path}.br`))), raw, file.path);
      if (file.gz) assert.deepEqual(zlib.gunzipSync(await readFile(path.join(release, `${file.path}.gz`))), raw, file.path);
    }
    for (const [id, date] of [["v2", "2026-11-02"], ["v3", "2026-11-03"], ["v10", "2026-11-03"]]) await stageRelease({ staged, site, id, date, three, log: quiet });
    await movePointerTo({ site, id: "v1", log: quiet });
    assert.deepEqual(await retain({ site, keep: 2, log: quiet }), { kept: ["v10", "v3"], beyond: ["v2"] });
    assert.ok(existsSync(path.join(site, "r", "v2")), "listed, not removed");
    await retain({ site, keep: 2, remove: true, log: quiet });
    assert.deepEqual((await readdir(path.join(site, "r"))).sort(), ["v1", "v10", "v3"]);
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});

test("the host profile: no block gives the artifact's defaults, a release's block is read, and a broken one gives the defaults", () => {
  const page = (element) => ({ getElementById: (id) => (id === "cells-host" ? element : null) });
  const block = (text, type = "application/json") => ({ textContent: text, getAttribute: (name) => (name === "type" ? type : null) });
  assert.equal(readHost(page(null)), HOST_DEFAULTS);
  assert.deepEqual({ ...readHost(undefined) }, { format: null, release: null, links: "hash", api: null, problem: null });
  assert.deepEqual({ ...readHost(page(block('{"format":"cells.visualizer.host@1","release":"v49","links":"query","api":null,"later":1}'))) }, { format: "cells.visualizer.host@1", release: "v49", links: "query", api: null, problem: null });
  for (const text of ["{", "[]", '{"format":"cells.visualizer.host@2"}', '{"format":"cells.visualizer.host@1","links":"all"}']) {
    const read = hostProfile(text);
    assert.deepEqual([read.release, read.links, read.api], [null, "hash", null], text);
    assert.ok(read.problem, text);
  }
  assert.ok(readHost(page(block("{}", "text/javascript"))).problem);
});

test("the deploy example sends the content policy the staging and the acceptance check name", () => {
  const site = readFileSync(path.join(ROOT, "deploy", "caddy", "site.caddy"), "utf8");
  assert.ok(site.includes(`Content-Security-Policy "${sitePolicy()}"`), "deploy/caddy/site.caddy and tools/stage_site.mjs (sitePolicy) state one policy");
  assert.ok(!/frame-ancestors/.test(sitePolicy()), "other sites may frame the viewer");
});
