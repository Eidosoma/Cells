// Builds the one page that every delivery mode uses: the local server, the
// standalone file and the artifact all get this same HTML.

import { build } from "esbuild";
import { spawn } from "node:child_process";
import { mkdir, mkdtemp, readdir, readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { PARTS_FORMAT, validatePart } from "../../src/replay/run.js";
import { UNIT_EVIDENCE_FORMAT } from "../../src/scene/model.js";

import { canonicalAddress } from "../../src/lenses/laws_data.js";

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

/** Keep the fields the atlas draws and searches in the scene. A unit's detailed evidence
 * is read on selection, one file per species, shared by the Proteins and Machines views. */
export function splitUnitEvidence(scene) {
  if (!scene.proteins || !scene.entities) return { scene, files: [] };
  const bySpecies = new Map();
  const entities = scene.entities.map((entity) => {
    if (entity.kind !== "unit" || !entity.species) return entity;
    const species = { ...entity.species };
    for (const [id, record] of Object.entries(species)) {
      if (!Array.isArray(record?.items)) continue;
      if (!/^[a-z0-9][a-z0-9_-]*$/.test(id)) throw new Error("Invalid unit evidence species: " + id);
      const { items, note, ...summary } = record;
      if (!bySpecies.has(id)) bySpecies.set(id, {});
      bySpecies.get(id)[entity.id] = { items, note };
      species[id] = summary;
    }
    return { ...entity, species };
  });
  if (!bySpecies.size) return { scene, files: [] };
  const evidence_files = {};
  const files = [];
  for (const [species, units] of bySpecies) {
    const path = `proteins/${species}/unit-evidence.json`;
    evidence_files[species] = path;
    files.push({ path, text: JSON.stringify({ format: UNIT_EVIDENCE_FORMAT, species, units }) });
  }
  return { scene: { ...scene, entities, proteins: { ...scene.proteins, evidence_files } }, files };
}

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
      // Every protein's name, beside its members (schema/SPECIES_PROTEINS.md, "The names file"): so that the page's
      // search finds a protein whose family is not open. Written from the members' files whenever they are newer.
      // A names file older than the members is left out (and, where the builder may write, made again): the search
      // then finds the families and not their members, and the page says so.
      const list = path.join(folder, NAMES_FILE);
      const newest = Math.max(...(await Promise.all(names.map((name) => modified(path.join(folder, name))))));
      if (make && !((await modified(list)) >= newest)) {
        const failure = await writeNames(id, folder, names, await searchedMarks(shelves)).catch((error) => error.message);
        if (failure) problems.push(`${id}: its proteins' names could not be written (${failure})`);
      }
      if ((await modified(list)) >= newest) own.push({ path: `proteins/${id}/${NAMES_FILE}`, source: list, species: id });
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

// A machine's shape (schema/MACHINE_SHAPES.md): one file a machine under data/catalogue/shapes/, published beside the page
// at shapes/<species>.<machine>.json, where a view fetches it. Returns { files: [{ path, source }], problems: [] }.
export const DEFAULT_SHAPES = path.join(ROOT, "data", "catalogue", "shapes");
const SHAPE_FILE = /^[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*\.json$/;
export async function shapeFiles({ shapesDir = DEFAULT_SHAPES } = {}) {
  const names = (await readdir(shapesDir).catch(() => [])).filter((name) => SHAPE_FILE.test(name)).sort();
  return { files: names.map((name) => ({ path: `shapes/${name}`, source: path.join(shapesDir, name) })), problems: [] };
}

// Each species' bench of the Machines catalogue (schema/MACHINE_CATALOGUE.md): one file a species under
// data/catalogue/benches/, published beside the page at catalogue/<species>.json and read when that bench is shown; the
// page carries the catalogue's core (data/catalogue/catalogue.json). Returns { files: [{ path, source }], problems: [] }.
export const DEFAULT_BENCHES = path.join(ROOT, "data", "catalogue", "benches");
const BENCH_FILE = /^[a-z0-9][a-z0-9_-]*\.json$/;
export async function benchFiles({ benchesDir = DEFAULT_BENCHES } = {}) {
  const names = (await readdir(benchesDir).catch(() => [])).filter((name) => BENCH_FILE.test(name)).sort();
  return { files: names.map((name) => ({ path: `catalogue/${name}`, source: path.join(benchesDir, name) })), problems: [] };
}

export const NAMES_FILE = "names.json";
export const NAMES_FORMAT = "cells.visualizer.species_protein_names@1";

/** The marks a catalogue declares the page's search finds its members by (`search: true`, schema/SPECIES_PROTEINS.md), in its order. */
async function searchedMarks(shelves) {
  try {
    return Object.entries(JSON.parse(await readFile(shelves, "utf8")).marks || {}).filter(([, mark]) => mark?.search === true).map(([name]) => name);
  } catch {
    return [];
  }
}

/**
 * The names file of a large catalogue: one row for each member, in the members' own order, with
 * its identifier, its gene, its name and its side, in the members' files' order (`files`, with how
 * many each holds in `counts`), so that the page knows each row's file and its place there and finds
 * its line by the same `file` and `at` as the shelves give. `searched`: the marks the catalogue says the
 * search finds a member by, each a column more after the four, with the mark's values joined by ", "
 * (none for a catalogue that declares none, whose file is as before). Returns what went wrong, or null.
 */
export async function writeNames(species, folder, files, searched = []) {
  const columns = ["id", "gene", "label", "side", ...searched];
  const rows = [], counts = [];
  for (const name of files) {
    const file = JSON.parse(await readFile(path.join(folder, name), "utf8"));
    const at = Object.fromEntries((file.columns || []).map((column, i) => [column, i]));
    if (!("id" in at) || !("label" in at)) return `${name} has no column of identifiers or names`;
    const more = (member) => searched.map((mark) => [].concat(member[at.marks]?.[mark] ?? []).join(", "));
    for (const member of file.members) rows.push([member[at.id], member[at.gene] || "", member[at.label] || "", member[at.side] || "not known", ...more(member)]);
    counts.push(file.members.length);
  }
  // The rows are the members in their files' order: `counts` says how many each file holds, so where a row is needs no column.
  const text = JSON.stringify({ format: NAMES_FORMAT, species, files, counts, columns, names: rows });
  // Moved into place whole, as the members are.
  const writing = path.join(folder, `.${NAMES_FILE}.${process.pid}`);
  await writeFile(writing, text);
  await rename(writing, path.join(folder, NAMES_FILE));
  return null;
}

/**
 * The run files of the model systems the scene names (schema/MODEL_SYSTEMS.md, `runs`), published beside the
 * page at the path the scene gives each (models/<id>/<name>), from its file under the viewer's folder.
 * Returns { files: [{ path, source, model }], problems: [text] }; a run whose file is not there is left out.
 */
export async function modelFiles(scene, { root = ROOT } = {}) {
  const files = [], problems = [];
  for (const model of scene?.models || []) {
    for (const run of model.runs || []) {
      const source = path.join(root, run.file || "");
      if (!/^models\/[a-z0-9-]+\/[a-z0-9_.-]+\.json$/.test(run.path || "") || !String(run.file || "").startsWith("data/")) problems.push(`${model.id}: the run ${run.label} names no file of the form models/<id>/<name>.json`);
      else if ((await modified(source)) === null) problems.push(`${model.id}: ${run.file} is not there`);
      else files.push({ path: run.path, source, model: model.id });
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
  // Written into a folder of their own beside, then each moved into place whole: a page that fetches a file while it
  // is being written reads the old one or the new one, never half of one. (Until 16 November 2026 several checkouts
  // shared one folder of members and rewrote it in place; that is the likeliest cause, not confirmed, of a press on a
  // family that sometimes did not open it while a second press did.)
  const writing = await mkdtemp(`${folder}.writing-`);
  const failure = await new Promise((resolve) => {
    const child = spawn("python3", [path.join(ROOT, tool), "members", "--out", writing], { cwd: ROOT, stdio: ["ignore", "ignore", "pipe"] });
    let said = "";
    child.stderr.on("data", (chunk) => (said += chunk));
    child.on("error", (error) => resolve(`${tool} could not be started (${error.message})`));
    child.on("close", (code) => resolve(code === 0 ? null : `${tool} members ended with ${code}: ${said.trim().split("\n").at(-1) || "no message"}`));
  });
  if (!failure) for (const name of await readdir(writing)) await rename(path.join(writing, name), path.join(folder, name));
  await rm(writing, { recursive: true, force: true });
  return failure;
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

/**
 * One script for a page, bundled from `entry` with everything it imports, as the page carries
 * it inline; "three" is `three` (the pinned file on cdnjs, or the local copy). The map's page
 * and a view standing alone (tools/build_view_page.mjs) are both made by it.
 */
export async function bundle(entry, { three = THREE_CDN } = {}) {
  const made = await build({
    entryPoints: [entry],
    // Each module's path is written from this folder, wherever the build is started from: the same script from the same files.
    absWorkingDir: ROOT,
    bundle: true,
    format: "esm",
    target: "es2022",
    write: false,
    minify: false,
    legalComments: "none",
    // A checkout whose node_modules is a link to another folder's: a module is named by the path it is reached by, inside
    // this folder, never by the folder the link leads to. The bundler writes each module's path above it as a comment, and
    // by the link's target that comment held a path of the machine the page was built on (found on 19 November 2026).
    preserveSymlinks: true,
    plugins: [
      {
        name: "three-from-url",
        setup(api) {
          api.onResolve({ filter: /^three$/ }, () => ({ path: three, external: true }));
        },
      },
    ],
  });
  const text = made.outputFiles[0].text;
  // No module of the page is named by a path that leaves the folder it is built in, or by a path from the machine's root.
  const outside = text.match(/^\/\/ (?:\.\.\/|\/|[A-Za-z]:[\\/]).*$/m);
  if (outside) throw new Error(`the page's script names a file outside the folder it is built in: ${outside[0].slice(0, 200)}`);
  return text.replaceAll("</script", "<\\/script");
}

/** The Laws library's list (schema/LAWS_LIBRARY.md), carried in the scene as `laws`: the view is offered only with it. */
export const DEFAULT_LAWS = path.join(ROOT, "data", "laws", "pieces.json");
/** The law-port inventory's table (schema/LAWS_LIBRARY.md), carried in the scene as `law_port`: what a unit says of a law no active model declares. */
export const DEFAULT_LAW_PORT = path.join(ROOT, "data", "laws", "law_port.json");
/** The Machines catalogue (schema/MACHINE_CATALOGUE.md), carried in the scene as `catalogue`: the view is offered only with it. */
export const DEFAULT_CATALOGUE = path.join(ROOT, "data", "catalogue", "catalogue.json");
/** The About words (cells.visualizer.about@1, src/ui/about.js), carried in the scene as `about`: the page's About and first-visit line, and the site's words (tools/stage_site.mjs). */
export const DEFAULT_ABOUT = path.join(ROOT, "data", "site", "about.json");

// The catalogue's overlay, where an experiment's entry may say that the parts of each of its runs are published together
// (`parts_together`, read by the export: packageParts).
export const DEFAULT_OVERLAY = path.join(ROOT, "data", "replays", "overlay.json");
// A published file of a run stays under 1 MB, as the adapter keeps each one it writes (tools/adapt_run.py, LIMIT_BYTES).
export const RUN_FILE_LIMIT = 1_000_000;

/** The experiments whose overlay entry says that their runs' parts are published together. A word that is not true or false is refused. */
export function partsTogether(overlay) {
  const together = new Set();
  for (const [id, entry] of Object.entries(overlay?.experiments || {})) {
    if (entry?.parts_together === undefined) continue;
    if (typeof entry.parts_together !== "boolean") throw new Error(`the overlay's ${id}: parts_together is true or false, not ${JSON.stringify(entry.parts_together)}`);
    if (entry.parts_together) together.add(id);
  }
  return together;
}

/**
 * Where to cut a run's parts, kept in their order, into files that each stay under `limit` (a file is `overhead` bytes, its
 * parts' sizes, and one byte between two): as few files as can hold them, and of those cuts the one whose largest file is
 * the smallest, so that the first part asked for brings as little else with it as can be. Returns the files as lists of
 * the parts' places in the order; null where one part alone would reach the limit.
 */
export function cutInOrder(sizes, { overhead = 0, limit = RUN_FILE_LIMIT } = {}) {
  const size = (from, to) => overhead + sizes.slice(from, to).reduce((sum, bytes) => sum + bytes, 0) + (to - from - 1);
  if (!sizes.length || sizes.some((_, k) => size(k, k + 1) >= limit)) return null;
  // The fewest files: each filled in order as far as it holds.
  let fewest = 0;
  for (let from = 0; from < sizes.length; fewest++) {
    let to = from + 1;
    while (to < sizes.length && size(from, to + 1) < limit) to++;
    from = to;
  }
  // Of the cuts into that many files, the one whose largest file is the smallest (the first such, where several are).
  const memo = new Map();
  const best = (from, left) => {
    const key = `${from}/${left}`;
    if (memo.has(key)) return memo.get(key);
    let found = null;
    if (left === 1) found = size(from, sizes.length) < limit ? { largest: size(from, sizes.length), cuts: [[from, sizes.length]] } : null;
    else {
      for (let to = from + 1; to <= sizes.length - (left - 1) && size(from, to) < limit; to++) {
        const rest = best(to, left - 1);
        const largest = rest ? Math.max(size(from, to), rest.largest) : Infinity;
        if (rest && (!found || largest < found.largest)) found = { largest, cuts: [[from, to], ...rest.cuts] };
      }
    }
    memo.set(key, found);
    return found;
  };
  return best(0, fewest).cuts.map(([from, to]) => Array.from({ length: to - from }, (_, k) => from + k));
}

/**
 * The published layout of the runs' parts (schema/RUN_VIEW.md, "Parts published together"). The runs folder holds a run's
 * own file and one file a part, as the adapter writes them, and is only read. For each run of an experiment in `together`,
 * its parts are published in files of several parts (cells.visualizer.replay_parts@1), each part file in it as it is, in
 * the run's order of parts: one file for the run, `runs/<run-id>.parts.json`, or where that would reach `limit`, as few as
 * stay under it (`.parts-2.json` and on), cut where the largest of them is the smallest (cutInOrder). The runs of other
 * experiments keep one file a part.
 * Returns { replays, files }: the catalogue with, for each part so published, `file` the file that holds it and `bytes`
 * that file's size; and the files to write beside the page, [{ path, run, parts: [part ids], text }].
 */
export async function packageParts(replays, { runsDir = DEFAULT_RUNS, together = new Set(), limit = RUN_FILE_LIMIT } = {}) {
  if (!replays?.runs) return { replays, files: [] };
  const files = [];
  const runs = [];
  for (const run of replays.runs) {
    if (!together.has(run.experiment) || !(run.parts || []).length) {
      runs.push(run);
      continue;
    }
    const head = `{"format":${JSON.stringify(PARTS_FORMAT)},"run":${JSON.stringify(run.id)},"parts":[`, tail = "]}\n";
    const texts = [];
    for (const part of run.parts) {
      if (/^parts(-\d+)?$/.test(part.id)) throw new Error(`${run.id}: its part ${part.id} would have the name of the file of its parts`);
      const text = (await readFile(path.join(runsDir, path.basename(part.file)), "utf8")).trim();
      const problems = validatePart(JSON.parse(text), run.id, part.id);
      if (problems.length) throw new Error(`${path.basename(part.file)}: ${problems[0]}`);
      texts.push(text);
    }
    const sizes = texts.map((text) => Buffer.byteLength(text));
    const cuts = cutInOrder(sizes, { overhead: Buffer.byteLength(head) + Buffer.byteLength(tail), limit });
    if (!cuts) throw new Error(`${run.id}: one of its parts alone would reach ${limit} bytes in a file of its parts; a file of a run stays under it`);
    const placed = new Map();
    cuts.forEach((places, k) => {
      const name = `runs/${run.id}.${k === 0 ? "parts" : `parts-${k + 1}`}.json`;
      const text = `${head}${places.map((at) => texts[at]).join(",")}${tail}`;
      files.push({ path: name, run: run.id, parts: places.map((at) => run.parts[at].id), text });
      for (const at of places) placed.set(run.parts[at].id, { file: name, bytes: Buffer.byteLength(text) });
    });
    runs.push({ ...run, parts: run.parts.map((part) => ({ ...part, ...placed.get(part.id) })) });
  }
  return { replays: { ...replays, runs }, files };
}

// The Experiments landing's cards (schema/EXPERIMENT_CARDS.md) and their stills, published beside the page as cards.json (the
// cards' faces, fetched when the landing first opens), cards.details.json (each card whole, fetched the first time a card's
// detail is asked for) and stills/<name>. The cards' `listing` is what the page lists and publishes.
export const DEFAULT_CARDS = path.join(ROOT, "data", "replays", "cards.json");
export const CARD_DETAILS = "cards.details.json"; // beside the cards, in the data folder as beside the page
export const DEFAULT_STILLS = path.join(ROOT, "data", "replays", "stills");
const STILL_PATH = /^stills\/([a-z0-9][a-z0-9._-]*\.(jpg|jpeg|png|webp))$/;

/** The cards' file as read, or null where there is none. */
export async function readCards(cardsPath = DEFAULT_CARDS) {
  try {
    return JSON.parse(await readFile(cardsPath, "utf8"));
  } catch {
    return null;
  }
}

/**
 * The landing's files beside the page: the cards' faces, their details (the file beside the faces that they name), and every
 * still a card names (for each theme). Returns { files: [{ path, source }], problems: [text] }; a still whose file is not there
 * is left out and said (its card then stands without a picture), and so are details that are not there (a card's detail
 * then says what its face says, and that its detail could not be fetched).
 */
export async function landingFiles({ cardsPath = DEFAULT_CARDS, stillsDir = DEFAULT_STILLS } = {}) {
  const cards = await readCards(cardsPath);
  if (!cards) return { files: [], problems: [`${path.relative(ROOT, cardsPath)} could not be read: the landing says so and offers to try again`] };
  const files = [{ path: "cards.json", source: cardsPath }], problems = [], named = new Set();
  const details = path.join(path.dirname(cardsPath), CARD_DETAILS);
  if ((await modified(details)) !== null) files.push({ path: CARD_DETAILS, source: details });
  else problems.push(`${path.relative(ROOT, details)} is not there: a card's detail then says what its face says`);
  for (const card of cards.cards || []) {
    const still = card?.replay?.still;
    if (!still || typeof still !== "object") continue;
    for (const theme of ["light", "dark"]) {
      const name = STILL_PATH.exec(still[theme] || "")?.[1];
      if (!still[theme]) continue;
      if (!name) problems.push(`${card.id}: its ${theme} still is not of the form stills/<name>`);
      else if (!named.has(name)) {
        named.add(name);
        const source = path.join(stillsDir, name);
        if ((await modified(source)) === null) problems.push(`${card.id}: ${path.relative(ROOT, source)} is not there`);
        else files.push({ path: `stills/${name}`, source });
      }
    }
  }
  return { files, problems };
}

/** The page content, as published: no doctype, html, head or body tags of its own. */
/** Model replays ship with the scene. A saved run index can predate the model links on today's experiment cards. */
export function withModelDoors(index, scene, listing) {
  if (!index || !listing?.entries?.length) return index;
  const existing = new Set((index.doors || []).map((door) => door.entry));
  const available = new Set((scene.models || []).filter((model) => model.view && model.runs?.length).map((model) => model.id));
  const additions = listing.entries.filter((id) => available.has(id) && !existing.has(id));
  return additions.length ? { ...index, doors: [...(index.doors || []), ...additions.map((entry) => ({ entry }))] } : index;
}

/**
 * The replays a published page carries: the experiments the landing lists (`listing.experiments` of the cards' file:
 * schema/EXPERIMENT_CARDS.md, since 18 November 2026) and their parts, and the runs the scene itself names (a species'
 * looping run, which its flux reads), with their experiments' entries. Everything else the folder holds is packaged for
 * the checks and never exported. Without a listing, the catalogue's own `listed` says which, as before; a catalogue that
 * says nothing of listing is then carried whole.
 */
export function publishedReplays(index, scene, listing = null) {
  index = withModelDoors(index, scene, listing);
  const byCards = Array.isArray(listing?.experiments);
  if (!index || (!byCards && !index.experiments?.some((item) => "listed" in item))) return index;
  const text = JSON.stringify(scene);
  const listed = new Set(byCards ? listing.experiments : index.experiments.filter((item) => item.listed === true).map((item) => item.id));
  // A part of a listed example (its tissue line: `part_of`) is published with it, though it is not listed itself.
  for (const item of index.experiments) if (listed.has(item.part_of)) listed.add(item.id);
  const runs = index.runs.filter((run) => listed.has(run.experiment) || text.includes(`"${run.id}"`));
  const kept = new Set(runs.map((run) => run.experiment));
  return { ...index, experiments: index.experiments.filter((item) => listed.has(item.id) || kept.has(item.id)), runs };
}

/**
 * `replays` is the catalogue the page carries where the caller has made it (the export, which packages the parts first:
 * packageParts); else it is read from `runsDir`, as `published` says.
 */
export async function buildPage({ scenePath = DEFAULT_SCENE, preparedScene, three = THREE_CDN, runsDir = DEFAULT_RUNS, inlineRuns = false, published = false, hideExperiments = false, proteinsDir = DEFAULT_PROTEINS, membersDir = DEFAULT_MEMBERS, machinesDir = DEFAULT_MACHINES, lawsPath = DEFAULT_LAWS, lawPortPath = DEFAULT_LAW_PORT, cataloguePath = DEFAULT_CATALOGUE, aboutPath = DEFAULT_ABOUT, cardsPath = DEFAULT_CARDS, stillsDir = DEFAULT_STILLS, replays: made = undefined } = {}) {
  const script = await bundle(path.join(ROOT, "src", "main.js"), { three });
  const prepared = preparedScene ?? splitUnitEvidence(JSON.parse(await readFile(scenePath, "utf8")));
  const data = { ...prepared.scene };
  if (lawsPath && !data.laws && (await modified(lawsPath)) !== null) data.laws = JSON.parse(await readFile(lawsPath, "utf8"));
  if (lawPortPath && !data.law_port && (await modified(lawPortPath)) !== null) data.law_port = JSON.parse(await readFile(lawPortPath, "utf8"));
  if (cataloguePath && !data.catalogue && (await modified(cataloguePath)) !== null) data.catalogue = JSON.parse(await readFile(cataloguePath, "utf8"));
  if (aboutPath && !data.about && (await modified(aboutPath)) !== null) data.about = JSON.parse(await readFile(aboutPath, "utf8"));
  const listing = (await readCards(cardsPath))?.listing;
  const index = made !== undefined ? made : await readReplays(runsDir);
  const replays = published && made === undefined ? publishedReplays(index, data, listing) : withModelDoors(index, data, listing);
  // A page without the Experiments view (hideExperiments) keeps its replays and says the view is hidden: the cell view's flux
  // finds a species' looping run among them.
  if (replays) {
    const aliases = data.laws?.viewer_ids?.aliases;
    const experiments = replays.experiments?.map(experiment => experiment.engine_entities?.length ? {
      ...experiment,
      engine_entities: experiment.engine_entities.map(id => canonicalAddress(id, aliases)),
    } : experiment);
    data.replays = { ...replays, experiments, ...(hideExperiments ? { hidden: true } : {}) };
  }
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
  // The landing's cards and stills, for a file on disk: the cards as they are, each still as a data address (a JSON string).
  if (inlineRuns && replays && !hideExperiments) {
    for (const file of (await landingFiles({ cardsPath, stillsDir })).files) {
      const raw = await readFile(file.source);
      const text = file.path.endsWith(".json") ? raw.toString("utf8") : JSON.stringify(`data:image/${file.path.endsWith(".png") ? "png" : file.path.endsWith(".webp") ? "webp" : "jpeg"};base64,${raw.toString("base64")}`);
      inline += `\n<script type="application/json" data-file="${file.path}">${text.replaceAll("<", "\\u003c")}</script>`;
    }
  }
  // The same for the species' own proteins: beside the page by default, inside it for a file on disk.
  if (inlineRuns) {
    for (const file of prepared.files) {
      inline += `\n<script type="application/json" data-file="${file.path}">${file.text.replaceAll("<", "\\u003c")}</script>`;
    }
    for (const file of [...(await proteinFiles(data, { proteinsDir, membersDir })).files, ...(await machineFiles(data, { machinesDir })).files, ...(await modelFiles(data)).files, ...(await shapeFiles()).files, ...(await benchFiles()).files]) {
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

/**
 * The page as a complete document, for a file on disk, the local server or the site's release (`lang`, and `before`, what
 * stands in the body ahead of the page: the site's text without script, tools/stage_site.mjs).
 */
export function wrap(content, { theme = null, head = "", lang = null, before = "" } = {}) {
  const attribute = `${lang ? ` lang="${lang}"` : ""}${theme ? ` data-theme="${theme}"` : ""}`;
  return `<!doctype html><html${attribute}><head>${SKELETON_HEAD}${head}</head><body>\n${before ? `${before}\n` : ""}${content}\n</body></html>\n`;
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
