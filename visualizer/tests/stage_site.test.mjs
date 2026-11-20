// The site's release of the viewer (tools/stage_site.mjs; docs/HOSTING_AND_API.md, sections 9 and 10), on a made-up
// staged folder of a few small files and a page that names the two outside addresses the real page names: the page
// inside a release is the staged page but for the declared insertions and rewrites, each counted; every other file is
// the same bytes; release.json lists exactly what stands; a release is written once; the pointer step copies root.html
// and nothing else; a count other than the expected stops the staging; and no path of the machine is written. The site's
// words are the page's own (its scene's About words, its script's views), its head carries the link-preview tags and the
// structured data (no author, no publisher), its text without script stands ahead of the page, and its root files (robots.txt
// that never closes /r/, the sitemap, llms.txt) go to the root with the pointer. Also the host profile's reader
// (src/core/host.js), and the deploy example's content policy against the staging's own.
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
import { DESCRIPTION, ROOT_FILES, SHARE, SITE, TITLE, jpegSize, movePointerTo, pageWords, retain, sharePicture, siteHead, sitePolicy, siteText, stageRelease, structuredData } from "../tools/stage_site.mjs";
import { HOST_DEFAULTS, hostProfile, readHost } from "../src/core/host.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const quiet = () => {};
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
// The real page's link to Google Fonts, as src/page.html writes it.
const FONTS_LINK = readFileSync(path.join(ROOT, "src", "page.html"), "utf8").split("\n").find((line) => line.includes("fonts.googleapis.com"));
const LOCAL_THREE = "./vendor/three/0.170.0/three.module.min.js";
// The tracked About words, which a staged page's scene must carry, and a scene that carries them with the map's own record.
const ABOUT = JSON.parse(readFileSync(path.join(ROOT, "data", "site", "about.json"), "utf8"));
const REVISION = "abc12345".repeat(5);
const SCENE = (about = ABOUT) => JSON.stringify({ format: "cells.visualizer.scene@1", meta: { revision: "abc12345", dirty: false, as_of: "2026-11-19", source_base_url: `https://github.com/Eidosoma/Cells/blob/${REVISION}/`, own_source_base_url: "https://github.com/Eidosoma/Cells/blob/visualizer/" }, ...(about ? { about } : {}) });
// The page's views as its script lists them (src/ui/viewer.js, LENSES), bundled.
const VIEWS = [["cell", "Scope"], ["machines", "Machines"], ["proteins", "Proteins"], ["engine", "Engine"], ["laws", "Laws"], ["experiments", "Experiments"]];
const LENSES = (views = VIEWS) => `var LENSES = [\n${views.map(([id, label]) => `  { id: "${id}", label: "${label}", short: "${label}", make: () => null },`).join("\n")}\n];\n`;

/** A page as the export writes it (no document of its own), whose module script imports three.js twice. */
const PAGE = (scene = SCENE(), link = FONTS_LINK, lenses = LENSES()) =>
  `<title>Cells</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n${link}\n<style>\nbody { margin: 0 }\n</style>\n\n<cells-viewer id="cells-viewer">\n  <p class="boot" id="cells-boot">Loading…</p>\n  <script type="application/json">${scene}</script>\n</cells-viewer>\n\n<script>\n  setTimeout(function () {}, 9000);\n</script>\n<script type="module">\nimport * as three_star from "${THREE_CDN}";\nimport {\n  Vector3\n} from "${THREE_CDN}";\n${lenses}customElements.define("cells-viewer", class extends HTMLElement {});\n</script>\n`;
// One card in one band, with a level and a verdict, as the landing reads it (src/replay/landing.js).
const CARDS = JSON.stringify({ format: "cells.visualizer.experiment_cards@1", bands: [{ id: "judged", label: "Judged", cards: ["c1"] }], cards: [{ id: "c1", band: "judged", kind: "standing", title: "FR-1: a closed compartment", standing: { status: "qualified", level: { label: "Qualified or judged", says: "…" } }, record: [{ says: "…", verdict: { passed: true, count: { passed: 44, of: 44, unit: "judged criteria" }, day: { date: "2026-11-18" } } }] }] });

const BESIDE = {
  "runs/sheet--a.json": '{"format":"cells.visualizer.replay@1","run":"sheet--a"}',
  "runs/sheet--a.parts.json": '{"format":"cells.visualizer.replay_parts@1","parts":[]}',
  "proteins/worm/shelves.json": '{"format":"cells.visualizer.species_proteins@1"}',
  "cards.json": CARDS,
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
    const words = pageWords(page), share = await sharePicture();
    const head = siteHead("v1", words, { share }), text = siteText("v1", words);
    assert.equal(index, wrap(body, { lang: "en", head, before: text }), "the page is wrapped as the artifact host wraps it, with lang, the site's head, the text without script ahead of it, and nothing else");
    // The head, in its order: the title, the description, the site's address as canonical, a link's preview (its picture the
    // release's own, 1200 by 630, no words over it), the structured data, the text's style, the host profile.
    assert.deepEqual([...head.matchAll(/<(title|meta|link|script|style)\b([^>]*)>/g)].map((match) => (/(?:name|property|rel|type)="([^"]+)"/.exec(match[2])?.[1] || match[1])), ["title", "description", "canonical", "og:type", "og:site_name", "og:title", "og:description", "og:url", "og:image", "og:image:type", "og:image:width", "og:image:height", "og:image:alt", "twitter:card", "application/ld+json", "style", "application/json"]);
    assert.ok(head.startsWith(`<title>${TITLE}</title><meta name="description" content="${DESCRIPTION}"><link rel="canonical" href="${SITE}">`));
    for (const [name, value] of [["og:url", SITE], ["og:image", `${SITE}r/v1/${SHARE}`], ["og:image:width", "1200"], ["og:image:height", "630"], ["og:title", TITLE], ["twitter:card", "summary_large_image"]]) assert.ok(head.includes(`="${name}" content="${value}"`), name);
    assert.ok(!/twitter:(site|creator)/.test(head), "no account is named");
    // The structured data: the site and its source code, each value true of the tree; the one name in it is the credit's
    // organisation, the site's publisher and the source code's author, and nothing more.
    const data = JSON.parse(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/.exec(head)[1]);
    assert.deepEqual(data, structuredData(words));
    assert.deepEqual(data["@graph"].map((item) => [item["@type"], item.name]), [["WebSite", "Cells"], ["SoftwareSourceCode", "Cells"]]);
    assert.equal(data["@graph"][0].url, SITE);
    assert.equal(data["@graph"][1].codeRepository, "https://github.com/Eidosoma/Cells");
    assert.equal(data["@graph"][1].license, `https://github.com/Eidosoma/Cells/blob/${REVISION}/LICENSE`, "the licence at the map's revision");
    const by = { "@type": "Organization", name: ABOUT.credit.organisation };
    assert.deepEqual([data["@graph"][0].publisher, data["@graph"][1].author], [by, by]);
    assert.deepEqual([data["@graph"][0].author, data["@graph"][1].publisher], [undefined, undefined]);
    assert.ok(!/"(creator|copyrightHolder|maintainer|contributor|funder|sponsor|email|telephone|sameAs|logo)"|"Person"/.test(JSON.stringify(data)), "no other name, contact or address of anyone");
    // The text without script: the About words whole, the source code in a new tab, the six views by the page's own names.
    for (const words_ of [...ABOUT.lead, ...ABOUT.reading, ...ABOUT.views, ABOUT.credit].map((item) => item.text)) assert.ok(text.includes(words_), words_.slice(0, 40));
    assert.ok(text.startsWith('<section id="cells-text"') && text.includes('<h1 id="cells-text-title">Cells</h1>'));
    assert.ok(text.includes('<a href="https://github.com/Eidosoma/Cells" target="_blank" rel="noopener noreferrer">Source code</a>'));
    assert.ok(!/LICENSE|licence/.test(text), "no licence link, as the page's About has none");
    assert.deepEqual([...text.matchAll(/<a href="https:\/\/cells\.eidosoma\.ai\/\?lens=([a-z]+)">([^<]+)<\/a>/g)].map((match) => [match[1], match[2]]), VIEWS);
    assert.ok(text.includes("Map: As of 19 Nov 2026 · main abc12345. Release: v1."), "what the page knows of itself");
    assert.ok(!/<script/.test(text), "the text runs nothing");
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
    assert.match(listed.viewer.note, /where the site's staging ran; the page was built where its staged folder was made/, "the commit is the staging's, and the record says so");
    assert.deepEqual(listed.inline_scripts.map((script) => script.type), ["classic", "module"], "the JSON blocks are not scripts that run, nor is the structured data");
    // The share picture, the tracked one; the site's root files, made from the page's words and this release.
    assert.deepEqual(await readFile(path.join(release, SHARE)), await readFile(path.join(ROOT, "data", "site", "share.jpg")));
    assert.deepEqual(jpegSize(await readFile(path.join(release, SHARE))), { width: 1200, height: 630 });
    assert.deepEqual(listed.site.root_files, ROOT_FILES);
    const robots = await readFile(path.join(release, "robots.txt"), "utf8");
    assert.match(robots, /^User-agent: \*\nAllow: \/\n/m);
    assert.ok(!/^Disallow:\s*\S/m.test(robots), "robots.txt closes nothing, /r/ least of all");
    assert.match(robots, new RegExp(`^Sitemap: ${SITE.replace(/[.]/g, "\\.")}sitemap\\.xml$`, "m"));
    assert.equal(await readFile(path.join(release, "sitemap.xml"), "utf8"), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n  <url><loc>${SITE}</loc><lastmod>2026-11-19</lastmod></url>\n</urlset>\n`);
    const llms = await readFile(path.join(release, "llms.txt"), "utf8");
    assert.ok(llms.startsWith(`# Cells\n\n> ${DESCRIPTION}\n`));
    for (const line of [`- [Scope](${SITE}?lens=cell): `, `[release.json](${SITE}r/v1/release.json)`, `[cards.json](${SITE}r/v1/cards.json)`, "- FR-1: a closed compartment. Level: Qualified or judged. Verdict: passed, 44 of 44 judged criteria, 18 Nov 2026.", `- cells.visualizer.replay@1: [runs/sheet--a.json](${SITE}r/v1/runs/sheet--a.json)`, "- [EXPERIMENT_CARDS.md](https://github.com/Eidosoma/Cells/blob/visualizer/visualizer/schema/EXPERIMENT_CARDS.md)", "- [Source code](https://github.com/Eidosoma/Cells), under the MIT licence", `\n${ABOUT.credit.text}\n`]) assert.ok(llms.includes(line), line);
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
    assert.deepEqual(moved, { left: "v1", now: "v2", root: ROOT_FILES, removed: [] });
    assert.match(said.join("\n"), /there was no pointer before[\s\S]*wrote robots\.txt, sitemap\.xml, llms\.txt at the site's root, v2's own[\s\S]*the pointer left v1 and names v2/);
    // The pointer and its two compressed copies, which a server sends in its place, and the site's root files: the release's
    // own, and nothing else.
    const changed = Object.keys(after).filter((name) => after[name] !== before[name]).sort();
    assert.ok(changed.every((name) => ["index.html", "index.html.br", "index.html.gz", ...ROOT_FILES].includes(name)) && changed.includes("index.html.br"), `only the pointer, its copies and the root files changed (${changed})`);
    assert.equal(after["index.html"], after["r/v2/root.html"]);
    for (const kind of ["br", "gz"]) assert.equal(after[`index.html.${kind}`], after[`r/v2/root.html.${kind}`], `the pointer's ${kind} copy is the release's`);
    for (const name of ROOT_FILES) assert.equal(after[name], after[`r/v2/${name}`], `the root's ${name} is the release's`);
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
    for (const name of ROOT_FILES) assert.equal(back[name], back[`r/v3/${name}`]);
    // A release staged before the root files (an older one) still releases: the root then holds none of another release's.
    const old = path.join(site, "r", "v0");
    await mkdir(old);
    for (const name of ["root.html", "index.html", "cards.json"]) await writeFile(path.join(old, name), await readFile(path.join(site, "r", "v3", name)));
    const files = [];
    for (const name of ["root.html", "index.html", "cards.json"]) {
      const bytes = await readFile(path.join(old, name));
      files.push({ path: name, bytes: bytes.length, sha256: sha(bytes), format: null });
    }
    await writeFile(path.join(old, "root.html"), (await readFile(path.join(old, "root.html"), "utf8")).replace('"release":"v3"', '"release":"v0"'));
    files[0] = { path: "root.html", bytes: (await readFile(path.join(old, "root.html"))).length, sha256: sha(await readFile(path.join(old, "root.html"))), format: null };
    await writeFile(path.join(old, "release.json"), JSON.stringify({ format: "cells.visualizer.release@1", release: "v0", date: "2026-11-01", files }));
    const oldSaid = [];
    await movePointerTo({ site, id: "v0", log: (line) => oldSaid.push(line) });
    const gone = await snapshot(site);
    assert.ok(ROOT_FILES.every((name) => !(name in gone)), "none of the root files of the release before is left");
    assert.match(oldSaid.join("\n"), /v0 holds no robots\.txt, sitemap\.xml, llms\.txt[\s\S]*removed robots\.txt, sitemap\.xml, llms\.txt from the site's root[\s\S]*the pointer left v3 and names v0/);
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
    // A page without the About words, or with other words than the tracked file's: the site would say what its page does not.
    [{ page: PAGE(SCENE(null)) }, /carries no About words/],
    [{ page: PAGE(SCENE({ ...ABOUT, lead: ABOUT.lead.slice(1) })) }, /are not data\/site\/about\.json as it stands/],
    // A page whose script does not list its views once, or lacks a view the words name.
    [{ page: PAGE(undefined, undefined, "") }, /lists its views 0 times/],
    [{ page: PAGE(undefined, undefined, LENSES(VIEWS.slice(0, 5))) }, /name the view experiments, and the page's script lists no such view/],
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
  // A share picture that is not 1200 by 630, or whose record names another picture or says nothing of what it shows.
  const { folder, staged, three, site } = await setUp();
  try {
    const small = path.join(folder, "small.jpg"), record = path.join(folder, "share.json");
    await writeFile(small, Buffer.from([0xff, 0xd8, 0xff, 0xc0, 0, 17, 8, 0x01, 0x3b, 0x02, 0x58, 3, 1, 0x22, 0, 2, 0x11, 1, 3, 0x11, 1, 0xff, 0xd9]));
    assert.deepEqual(jpegSize(await readFile(small)), { width: 600, height: 315 });
    await writeFile(record, JSON.stringify({ sha256: sha(await readFile(small)), alt: "A picture." }));
    await assert.rejects(stageRelease({ staged, site, id: "v1", three, log: quiet, share: { file: small, record } }), /not a JPEG of 1200 by 630 \(it is 600 by 315\)/);
    await writeFile(record, JSON.stringify({ sha256: "0".repeat(64), alt: "A picture." }));
    await assert.rejects(stageRelease({ staged, site, id: "v1", three, log: quiet, share: { record } }), /record does not name this picture/);
    assert.deepEqual(await snapshot(site), {});
  } finally {
    await rm(folder, { recursive: true, force: true });
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
