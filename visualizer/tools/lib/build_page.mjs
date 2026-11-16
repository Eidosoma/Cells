// Builds the one page that every delivery mode uses: the local server, the
// standalone file and the artifact all get this same HTML.

import { build } from "esbuild";
import { spawn } from "node:child_process";
import { mkdir, readFile, stat } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
export const THREE_VERSION = "0.170.0";
// Published pages may load scripts only from a short list of CDNs; cdnjs is the preferred one.
export const THREE_CDN = `https://cdnjs.cloudflare.com/ajax/libs/three.js/${THREE_VERSION}/three.module.min.js`;
export const THREE_LOCAL = "/vendor/three.module.min.js";
export const DEFAULT_SCENE = path.join(ROOT, "data", "architecture", "architecture.scene.json");
// Generated replays (schema/RUN_VIEW.md, "Packaged for the viewer"). Never committed.
export const DEFAULT_RUNS = path.join(ROOT, "out", "runs");

// Each species' own proteins (schema/SPECIES_PROTEINS.md): its shelves are committed there, in a
// folder of its own; the files of a large catalogue's members are cut from its table into out/.
export const DEFAULT_PROTEINS = path.join(ROOT, "data", "proteins");
export const DEFAULT_MEMBERS = path.join(ROOT, "out", "proteins");
const SHELVES_PATH = /^proteins\/([a-z0-9][a-z0-9_-]*)\/shelves\.json$/;
const MEMBERS_NAME = /^members-\d+\.json$/;
// How a catalogue says its members' files are written: a step of one of the repository's own tools.
const MEMBERS_STEP = /^python3 (tools\/[a-z0-9_]+\.py) members --out DIR\b/;

const modified = (file) => stat(file).then((found) => found.mtimeMs, () => null);

/**
 * The files of the species' own proteins that are published beside the page: for every
 * species the scene names, its shelves, and for a large catalogue the files of its families'
 * members. Those are not kept in the repository: they are written here, by the step the
 * catalogue itself names, when they are missing or older than the catalogue.
 * Returns { files: [{ path, source, species }], problems: [text] }; `path` is the address the
 * page fetches, `source` the file on disk. A species whose files are not there is left out
 * and said in `problems`: the page then shows the atlas without its own proteins.
 */
export async function proteinFiles(scene, { proteinsDir = DEFAULT_PROTEINS, membersDir = DEFAULT_MEMBERS, make = true } = {}) {
  const files = [], problems = [];
  for (const summary of scene?.proteins?.shelves || []) {
    const id = SHELVES_PATH.exec(summary.file || "")?.[1];
    if (!id || id !== summary.id) {
      problems.push(`${summary.id}: the scene names no file of proteins for it`);
      continue;
    }
    const shelves = path.join(proteinsDir, id, "shelves.json");
    const written = await modified(shelves);
    if (written === null) {
      problems.push(`${id}: ${path.relative(ROOT, shelves)} is not there`);
      continue;
    }
    const own = [{ path: summary.file, source: shelves, species: id }];
    const names = (summary.members || []).filter((name) => MEMBERS_NAME.test(name));
    if (names.length !== (summary.members || []).length) {
      problems.push(`${id}: the scene names a file of members that is not one`);
      continue;
    }
    if (names.length) {
      const folder = path.join(membersDir, id);
      const stale = async () => (await Promise.all(names.map((name) => modified(path.join(folder, name))))).some((time) => time === null || time < written);
      if (make && (await stale())) {
        const failure = await writeMembers(shelves, folder);
        if (failure) problems.push(`${id}: ${failure}`);
      }
      if (await stale()) {
        problems.push(`${id}: the files of its families' members are not in ${path.relative(ROOT, folder)}, or are older than its catalogue`);
        continue;
      }
      for (const name of names) own.push({ path: `proteins/${id}/${name}`, source: path.join(folder, name), species: id });
    }
    files.push(...own);
  }
  return { files, problems };
}

// The machines a species' cell can show closer (schema/MACHINES.md): each file is committed under data/machines/
// and published beside the page, at the address the scene names: machines/<species>.<machine>.json.
export const DEFAULT_MACHINES = path.join(ROOT, "data", "machines");
const MACHINE_PATH = /^machines\/([a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*\.json)$/;

/**
 * The machine files published beside the page: for every species the scene names, each
 * machine its entry lists. Returns { files: [{ path, source, species }], problems: [text] }.
 * A machine whose file is not there is left out and said in `problems`: its foot then offers
 * no closer view.
 */
export async function machineFiles(scene, { machinesDir = DEFAULT_MACHINES } = {}) {
  const files = [], problems = [];
  for (const species of scene?.species || []) {
    for (const entry of species.machines || []) {
      const name = MACHINE_PATH.exec(entry.file || "")?.[1];
      if (!name) {
        problems.push(`${species.id}: the machine ${entry.id} names no file of the form machines/<species>.<machine>.json`);
        continue;
      }
      const source = path.join(machinesDir, name);
      if ((await modified(source)) === null) problems.push(`${species.id}: ${path.relative(ROOT, source)} is not there`);
      else files.push({ path: entry.file, source, species: species.id });
    }
  }
  return { files, problems };
}

/** Write a large catalogue's members into `folder`, by the step its shelves name. Returns what went wrong, or null. */
async function writeMembers(shelves, folder) {
  let step = null;
  try {
    step = JSON.parse(await readFile(shelves, "utf8")).members_from?.step;
  } catch {
    return "its shelves could not be read";
  }
  const tool = MEMBERS_STEP.exec(step || "")?.[1];
  if (!tool) return "its shelves do not say how the files of members are written";
  await mkdir(folder, { recursive: true });
  return new Promise((resolve) => {
    const child = spawn("python3", [path.join(ROOT, tool), "members", "--out", folder], { cwd: ROOT, stdio: ["ignore", "ignore", "pipe"] });
    let said = "";
    child.stderr.on("data", (chunk) => (said += chunk));
    child.on("error", (error) => resolve(`${tool} could not be started (${error.message})`));
    child.on("close", (code) => resolve(code === 0 ? null : `${tool} members ended with ${code}: ${said.trim().split("\n").at(-1) || "no message"}`));
  });
}

/** The catalogue of adapted runs, or null when there is none. */
export async function readReplays(runsDir = DEFAULT_RUNS) {
  try {
    const index = JSON.parse(await readFile(path.join(runsDir, "index.json"), "utf8"));
    return index.runs?.length ? index : null;
  } catch {
    return null;
  }
}

// The document the artifact service wraps around a published page (read back from a
// published artifact on 14 November 2026). Local previews use the same wrapper.
const SKELETON_HEAD =
  '<meta charset=utf8><meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">' +
  "<style>:root{color-scheme:light;box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}" +
  "html{scroll-padding-top:env(safe-area-inset-top,0px)}body{margin:0;padding:0;font:14px -apple-system,BlinkMacSystemFont,sans-serif;background:#fff;color:#000}" +
  "img{max-width:100%}[hidden]:not([hidden=until-found i]){display:none!important}</style>";

/** The page content, as published: no doctype, html, head or body tags of its own. */
export async function buildPage({ scenePath = DEFAULT_SCENE, three = THREE_CDN, runsDir = DEFAULT_RUNS, inlineRuns = false, proteinsDir = DEFAULT_PROTEINS, membersDir = DEFAULT_MEMBERS, machinesDir = DEFAULT_MACHINES } = {}) {
  const bundle = await build({
    entryPoints: [path.join(ROOT, "src", "main.js")],
    bundle: true,
    format: "esm",
    target: "es2022",
    write: false,
    minify: false,
    legalComments: "none",
    plugins: [
      {
        name: "three-from-url",
        setup(api) {
          api.onResolve({ filter: /^three$/ }, () => ({ path: three, external: true }));
        },
      },
    ],
  });
  const script = bundle.outputFiles[0].text.replaceAll("</script", "<\\/script");
  const data = JSON.parse(await readFile(scenePath, "utf8"));
  const replays = await readReplays(runsDir);
  if (replays) data.replays = replays;
  const scene = JSON.stringify(data).replaceAll("<", "\\u003c");
  // A page that cannot fetch (a file opened from disk) carries its runs inline.
  let inline = "";
  if (replays && inlineRuns) {
    for (const run of replays.runs) {
      const text = (await readFile(path.join(runsDir, path.basename(run.file)), "utf8")).replaceAll("<", "\\u003c");
      inline += `\n<script type="application/json" data-replay="${run.id}">${text}</script>`;
      // Its records that come in files of their own (schema/QUANTITY_LAYERS.md, rule 10) go in with it.
      for (const part of run.parts || []) {
        const more = (await readFile(path.join(runsDir, path.basename(part.file)), "utf8")).replaceAll("<", "\\u003c");
        inline += `\n<script type="application/json" data-replay-part="${run.id}/${part.id}">${more}</script>`;
      }
    }
  }
  // The same for the species' own proteins: beside the page by default, inside it for a file on disk.
  if (inlineRuns) {
    for (const file of [...(await proteinFiles(data, { proteinsDir, membersDir })).files, ...(await machineFiles(data, { machinesDir })).files]) {
      const text = (await readFile(file.source, "utf8")).replaceAll("<", "\\u003c");
      inline += `\n<script type="application/json" data-file="${file.path}">${text}</script>`;
    }
  }
  const css = await readFile(path.join(ROOT, "src", "page.css"), "utf8");
  const template = await readFile(path.join(ROOT, "src", "page.html"), "utf8");
  return template
    .replace("/*__PAGE_CSS__*/", () => css.trim())
    .replace("__SCENE__", () => scene)
    .replace("<!--__RUNS__-->", () => inline)
    .replace("/*__BUNDLE__*/", () => script.trim());
}

/** The page as a complete document, for a file on disk or the local server. */
export function wrap(content, { theme = null, head = "" } = {}) {
  const attribute = theme ? ` data-theme="${theme}"` : "";
  return `<!doctype html><html${attribute}><head>${SKELETON_HEAD}${head}</head><body>\n${content}\n</body></html>\n`;
}

/** A Content-Security-Policy close to the artifact frame's, so a blocked load shows up locally. */
export function contentSecurityPolicy({ local = false } = {}) {
  const scripts = ["'unsafe-inline'", "https://cdnjs.cloudflare.com", "https://cdn.jsdelivr.net/npm/", "https://unpkg.com", "https://cdn.tailwindcss.com", "https://code.jquery.com"];
  if (local) scripts.push("'self'");
  return [
    "default-src 'none'",
    `script-src ${scripts.join(" ")}`,
    "style-src 'unsafe-inline' https://fonts.googleapis.com",
    "font-src https://fonts.gstatic.com data:",
    "img-src 'self' data: blob:",
    "connect-src 'self'",
    "worker-src 'self' blob:",
  ].join("; ");
}
