// The quick sweep's record of passes: a test that makes tracked files again from saved downloads ("the same bytes
// every time") is skipped by `npm run test:quick` where a run with the same fingerprint of everything it rests on has
// passed before. `npm test` never asks: there every such test runs, every time.
//
// What a fingerprint covers (coarse on purpose: too much costs one more run, too little is a false pass shared between
// checkouts), read when the test runs, from contents and never from times:
//   - every file under tools/ and under tests/lib/, and the test's own file (each by its path in the tree); every file
//     under src/scene/, and every other file under src/ that a file under tools/ imports, with what it imports in turn
//     (pageModules below);
//   - every file under data/, the tracked folders the rebuilds read and compare against (a hand edit of an output
//     runs the test again);
//   - the saved downloads the test reads: each folder's MANIFEST.json as it stands, the size of each file it lists
//     (one it lists as not fetched, `ok: false`, and that is absent, as absent), and the name and size of each other
//     file beside it; an evidence folder (spec.evidence) by its requests.json and the path and size of every file in
//     it; a file named alone (spec.files) by its size;
//   - node's version and the versions of the installed node packages (node_modules/.package-lock.json); python3's
//     version and place, and the version of every library outside Python's own that a tool under tools/ imports;
//   - each environment variable the test reads (spec.env), every PYTHON* variable, and CELLS_ENGINE_REPO with the
//     revision of the checkout it names and what is uncommitted there.
// A missing input (a folder, a manifest, a file a manifest lists as fetched, a library, the engine's checkout) is a
// miss, never a pass: the test runs.
//
// The records are small files in CELLS_TEST_CACHE (out/test-cache under the checkout unless set), each written whole
// and moved into place, so that several checkouts may share one folder. A record says which test, which fingerprint
// and when; it holds no result but "passed". It is a cache of test results on one machine, never a statement about a
// run, and is never tracked.
//
// Switched on by CELLS_TEST_QUICK=1 (what `npm run test:quick` sets) and never under `npm test`, whatever the shell
// has exported. CELLS_TEST_FORCE=1 runs every such test (and records its pass anew).
//
// In a test, at the head of its body (the test takes its context, `t`):
//   const { passedBefore } = await import("./lib/test_cache.mjs");
//   if (await passedBefore(t, { downloads: [path.join(DATASETS, "*", "*")], env: ["GATHER_DATASETS"] })) return;

import { createHash, randomBytes } from "node:crypto";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, readFileSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
export const FORMAT = "cells.visualizer.test_pass@1";
/** How a skip by the quick sweep starts its line: tests/lib/quick_summary.mjs counts the skips by it. */
export const SKIP_MARK = "quick sweep:";
const SKIPPED_NAMES = new Set(["__pycache__", ".pytest_cache", ".DS_Store"]);

/** Thrown where an input the fingerprint names is not there: the test runs. */
export class Missing extends Error {}

/** Whether the cache was asked for: CELLS_TEST_QUICK set, and not under `npm test`. */
export function asked(env = process.env) {
  if (env.npm_lifecycle_event === "test") return false;
  return Boolean(env.CELLS_TEST_QUICK) && env.CELLS_TEST_QUICK !== "0";
}

/** The folder the records are kept in. */
export function cacheFolder(env = process.env, root = ROOT) {
  return path.resolve(env.CELLS_TEST_CACHE || path.join(root, "out", "test-cache"));
}

const sha = (data) => createHash("sha256").update(data).digest("hex");

/** Every file under `folder` (its path from `base`, its bytes' hash), in a fixed order; Python's byte code left out. */
function tree(folder, base, lines, kind) {
  let entries;
  try {
    entries = readdirSync(folder, { withFileTypes: true });
  } catch {
    throw new Missing(`${kind} ${path.relative(base, folder) || folder} is not there`);
  }
  for (const entry of entries.sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0))) {
    if (SKIPPED_NAMES.has(entry.name) || entry.name.endsWith(".pyc")) continue;
    const at = path.join(folder, entry.name);
    let stats;
    try {
      stats = statSync(at); // follows a link to what it names
    } catch {
      continue; // a link to nothing, or gone meanwhile: not read by anything
    }
    if (stats.isDirectory()) tree(at, base, lines, kind);
    else if (stats.isFile()) lines.push(`${kind}\t${path.relative(base, at)}\t${sha(readFileSync(at))}`);
  }
}

/** The folders a pattern names: `*` stands for any one name in its place ("/data/*\/*" is every folder two below). */
function expand(pattern) {
  const parts = path.resolve(pattern).split(path.sep);
  let found = [parts[0] || path.sep];
  for (const part of parts.slice(1)) {
    if (!part) continue;
    const next = [];
    for (const at of found) {
      if (part !== "*") next.push(path.join(at, part));
      else {
        try {
          for (const entry of readdirSync(at, { withFileTypes: true }).sort((a, b) => (a.name < b.name ? -1 : 1))) if (entry.isDirectory() || entry.isSymbolicLink()) next.push(path.join(at, entry.name));
        } catch {}
      }
    }
    found = next;
  }
  return found;
}

/** A folder of saved downloads: its MANIFEST.json, the size of each file it lists, and the name and size of each other file beside it. */
function downloadsOf(folder, lines) {
  const manifestFile = path.join(folder, "MANIFEST.json");
  let text;
  try {
    text = readFileSync(manifestFile);
  } catch {
    throw new Missing(`no MANIFEST.json in ${folder}`);
  }
  lines.push(`manifest\t${folder}\t${sha(text)}`);
  let manifest;
  try {
    manifest = JSON.parse(text);
  } catch {
    throw new Missing(`the MANIFEST.json in ${folder} cannot be read`);
  }
  const listed = new Set();
  for (const item of Array.isArray(manifest.files) ? manifest.files : []) {
    const name = item?.name;
    if (typeof name !== "string" || !name) continue;
    listed.add(name);
    let size = null;
    try {
      size = statSync(path.join(folder, name)).size;
    } catch {}
    if (size === null && item.ok !== false) throw new Missing(`${path.join(folder, name)}, which its MANIFEST lists, is not there`);
    lines.push(`listed\t${folder}\t${name}\t${size === null ? "absent, as listed" : size}`);
  }
  for (const entry of readdirSync(folder, { withFileTypes: true }).sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0))) {
    if (entry.name === "MANIFEST.json" || listed.has(entry.name)) continue;
    let size = "?";
    try {
      const stats = statSync(path.join(folder, entry.name));
      size = stats.isDirectory() ? "folder" : stats.size;
    } catch {}
    lines.push(`beside\t${folder}\t${entry.name}\t${size}`);
  }
}

/** An evidence folder: its requests.json as it stands, and the path and size of every file in it. */
function evidenceOf(folder, lines) {
  let text;
  try {
    text = readFileSync(path.join(folder, "requests.json"));
  } catch {
    throw new Missing(`no requests.json in ${folder}`);
  }
  lines.push(`requests\t${folder}\t${sha(text)}`);
  const walk = (at) => {
    for (const entry of readdirSync(at, { withFileTypes: true }).sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0))) {
      const inner = path.join(at, entry.name);
      if (entry.isDirectory()) walk(inner);
      else {
        let size = "?";
        try {
          size = statSync(inner).size;
        } catch {}
        lines.push(`evidence\t${folder}\t${path.relative(folder, inner)}\t${size}`);
      }
    }
  };
  walk(folder);
}

// ---------------------------------------------------------------- the page's modules the tools reach
// A tool may run a module of the page (the scene's build reads src/scene/ through node, from 19 November 2026): every
// file under src/scene/ is taken whole, and every other file under src/ that a file under tools/ imports, with what that
// imports in turn, is found by reading the import lines. A tool's import whose target cannot be read from its line (a
// computed one) is a miss; inside src/ such an import takes all of src/. A Python tool that names a folder of src/ by
// its words ("src" / "scene", "src/ui/…") takes that folder whole; one that joins "src" to a name it computes is a miss.
const JS_IMPORT = /\b(?:import|export)\b[^;'"`]*?\bfrom\s*(["'])([^"'\n]+)\1|\bimport\s*(["'])([^"'\n]+)\3|\bimport\(\s*(["'])([^"'\n]+)\5\s*\)/g;
const JS_COMPUTED = /\bimport\(\s*(?![\s"'])|\bimport\(\s*`/;
const strip = (text) => text.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`\\])\/\/.*$/gm, "$1");

function filesUnder(folder, out = []) {
  let entries = [];
  try {
    entries = readdirSync(folder, { withFileTypes: true });
  } catch {
    return out;
  }
  for (const entry of entries) {
    if (SKIPPED_NAMES.has(entry.name) || entry.name.endsWith(".pyc")) continue;
    const at = path.join(folder, entry.name);
    if (entry.isDirectory()) filesUnder(at, out);
    else out.push(at);
  }
  return out;
}

/** The files under src/ the tools reach: src/scene/ whole, and what tools/ imports from src/, through its own imports. */
export function pageModules(root) {
  const src = path.join(root, "src"), inSrc = (file) => file.startsWith(src + path.sep);
  const reached = new Set(filesUnder(path.join(src, "scene")));
  const folders = new Set();
  let everything = false;
  const queue = [];
  const follow = (from, specifier) => {
    if (!specifier.startsWith(".")) return; // a package (covered by its version) or node's own
    const target = path.resolve(path.dirname(from), specifier.split("?")[0]);
    if (!inSrc(target)) return;
    if (!existsSync(target)) throw new Missing(`${path.relative(root, from)} imports ${specifier}, which is not there`);
    if (!reached.has(target)) (reached.add(target), queue.push(target));
  };
  for (const file of filesUnder(path.join(root, "tools"))) {
    if (/\.m?js$/.test(file)) {
      const text = strip(readFileSync(file, "utf8"));
      if (JS_COMPUTED.test(text)) throw new Missing(`${path.relative(root, file)} imports a module it computes, which cannot be read from its line`);
      for (const match of text.matchAll(JS_IMPORT)) follow(file, match[2] || match[4] || match[6]);
    } else if (file.endsWith(".py")) {
      const text = readFileSync(file, "utf8");
      for (const match of text.matchAll(/["']src["']\s*[,/]\s*([^\s,)]+)/g)) {
        const named = match[1].match(/^["']([A-Za-z0-9_.-]+)["']/);
        if (!named) throw new Missing(`${path.relative(root, file)} joins "src" to a name it computes`);
        if (existsSync(path.join(src, named[1]))) folders.add(path.join(src, named[1]));
      }
      for (const match of text.matchAll(/["'`/]src\/([A-Za-z0-9_.-]+)/g)) if (existsSync(path.join(src, match[1]))) folders.add(path.join(src, match[1]));
    }
  }
  while (queue.length) {
    const file = queue.shift();
    if (!/\.m?js$/.test(file)) continue;
    const text = strip(readFileSync(file, "utf8"));
    if (JS_COMPUTED.test(text)) everything = true;
    for (const match of text.matchAll(JS_IMPORT)) follow(file, match[2] || match[4] || match[6]);
  }
  if (everything) folders.add(src);
  for (const folder of folders) for (const file of statSync(folder).isDirectory() ? filesUnder(folder) : [folder]) reached.add(file);
  return [...reached].sort();
}

/** python3's version and place, and the version of each library outside Python's own that a tool under tools/ imports. */
function pythonOf(root, python = "python3") {
  // Every import a tool's text holds (a line of prose that reads like one only adds a name, and costs a run).
  const script = [
    "import ast, importlib.metadata as M, json, pathlib, re, sys",
    "tools = pathlib.Path(sys.argv[1])",
    "local = {p.stem for p in tools.rglob('*.py')} | {p.name for p in tools.rglob('*') if p.is_dir()}",
    "FROM = re.compile(r'^[ \\t]*from[ \\t]+([A-Za-z_]\\w*)[\\w.]*[ \\t]+import\\b', re.M)",
    "IMPORT = re.compile(r'^[ \\t]*import[ \\t]+[^\\n]+', re.M)",
    "found = set()",
    "for p in sorted(tools.rglob('*.py')):",
    "    if '__pycache__' in p.parts: continue",
    "    text = p.read_text(encoding='utf-8', errors='replace')",
    "    found.update(FROM.findall(text))",
    "    for line in IMPORT.findall(text):",
    "        try: node = ast.parse(line.strip()).body[0]",
    "        except Exception: continue",
    "        if isinstance(node, ast.Import): found.update(a.name.split('.')[0] for a in node.names)",
    "outside = sorted(n for n in found if n not in sys.stdlib_module_names and n not in local and n != '__future__')",
    "versions = {}",
    "for n in outside:",
    "    try: versions[n] = M.version(n)",
    "    except Exception:",
    "        try: versions[n] = str(__import__(n).__version__)",
    "        except Exception: versions[n] = None",
    "print(json.dumps({'version': sys.version, 'executable': sys.executable, 'libraries': versions}))",
  ].join("\n");
  const run = spawnSync(python, ["-I", "-c", script, path.join(root, "tools")], { encoding: "utf8" });
  if (run.status !== 0) throw new Missing(`python3 did not say its version (${(run.stderr || run.error?.message || "").trim().slice(0, 200)})`);
  const found = JSON.parse(run.stdout);
  const none = Object.entries(found.libraries).filter(([, version]) => version === null).map(([name]) => name);
  if (none.length) throw new Missing(`a library a tool imports is not installed (${none.join(", ")})`);
  return found;
}

/** The engine's checkout CELLS_ENGINE_REPO names: its revision and what is uncommitted there (not its place, so that
 *  two checkouts of the viewer that name copies of one revision share their records). */
function engineOf(env) {
  const repo = env.CELLS_ENGINE_REPO;
  if (repo === undefined) return "unset";
  const git = (...words) => spawnSync("git", ["-C", repo, ...words], { encoding: "utf8" });
  const head = git("rev-parse", "HEAD");
  if (head.status !== 0) throw new Missing(`CELLS_ENGINE_REPO names no checkout git can read (${repo})`);
  const status = git("status", "--porcelain");
  if (status.status !== 0) throw new Missing(`git cannot say what is uncommitted in ${repo}`);
  return `set\t${head.stdout.trim()}\t${sha(status.stdout)}`;
}

/**
 * The fingerprint of what a rebuild test rests on, as `{ hash, lines }`; throws Missing where an input is not there.
 * spec: { file (the test's own file), downloads (folders, `*` for any one name), evidence (folders), files, env (names) };
 * `root`, `env`, `runtime` and `python` stand in for the checkout, the environment and the interpreters in a test.
 */
export function fingerprint(spec, { root = ROOT, env = process.env, runtime = null, python = "python3" } = {}) {
  const lines = [];
  tree(path.join(root, "tools"), root, lines, "tool");
  tree(path.join(root, "tests", "lib"), root, lines, "helper");
  tree(path.join(root, "data"), root, lines, "data");
  for (const file of pageModules(root)) lines.push(`page\t${path.relative(root, file)}\t${sha(readFileSync(file))}`);
  if (!spec.file || !existsSync(spec.file)) throw new Missing(`the test's own file is not there (${spec.file})`);
  lines.push(`test\t${path.relative(root, spec.file)}\t${sha(readFileSync(spec.file))}`);
  for (const pattern of spec.downloads || []) {
    const folders = expand(pattern).filter((folder) => existsSync(path.join(folder, "MANIFEST.json")));
    if (!folders.length) throw new Missing(`no saved downloads where ${pattern} points`);
    lines.push(`downloads\t${pattern}\t${folders.length}`);
    for (const folder of folders) downloadsOf(folder, lines);
  }
  for (const folder of spec.evidence || []) evidenceOf(folder, lines);
  for (const file of spec.files || []) {
    let size;
    try {
      size = statSync(file).size;
    } catch {
      throw new Missing(`${file} is not there`);
    }
    lines.push(`file\t${file}\t${size}`);
  }
  const names = new Set([...(spec.env || []), ...Object.keys(env).filter((name) => name.startsWith("PYTHON"))]);
  for (const name of [...names].sort()) lines.push(`env\t${name}\t${env[name] === undefined ? "unset" : JSON.stringify(env[name])}`);
  lines.push(`engine\t${engineOf(env)}`);
  let packages;
  try {
    packages = sha(readFileSync(path.join(root, "node_modules", ".package-lock.json")));
  } catch {
    throw new Missing("node_modules/.package-lock.json is not there (the node packages are not installed)");
  }
  lines.push(`packages\t${packages}`);
  lines.push(`runtime\t${JSON.stringify(runtime ? runtime() : { node: process.version, python: pythonOf(root, python) })}`);
  return { hash: sha(lines.join("\n")), lines };
}

/** The first input that differs between two readings of a fingerprint, in words: its kind and its name. */
export function changedPart(before, after) {
  const was = new Set(before), now = new Set(after);
  const line = after.find((one) => !was.has(one)) ?? before.find((one) => !now.has(one));
  if (!line) return "the same inputs in another order";
  const [kind, ...rest] = line.split("\t");
  return `${kind} ${rest.slice(0, kind === "listed" || kind === "beside" || kind === "evidence" ? 2 : 1).join(" ")}`.slice(0, 200);
}

/** The test's name as records keep it: its file in the tree and its name. */
export const testId = (file, name, root = ROOT) => `${path.relative(root, file).split(path.sep).join("/")} › ${name}`;

/** Where the record of a test's pass on a fingerprint is kept. */
export const recordPath = (folder, id, hash) => path.join(folder, `${sha(id).slice(0, 16)}-${hash.slice(0, 32)}.json`);

/** The record of a pass of `id` on `hash`, or null: a record that cannot be read, or says anything else, is no record. */
export function readRecord(folder, id, hash) {
  try {
    const record = JSON.parse(readFileSync(recordPath(folder, id, hash), "utf8"));
    if (record?.format === FORMAT && record.test === id && record.fingerprint === hash && record.result === "passed" && typeof record.when === "string") return record;
  } catch {}
  return null;
}

/** Writes the record of a pass whole and moves it into place. */
export function writeRecord(folder, id, hash, when = new Date()) {
  mkdirSync(folder, { recursive: true });
  const final = recordPath(folder, id, hash);
  const part = `${final}.${process.pid}.${randomBytes(4).toString("hex")}.part`;
  try {
    writeFileSync(part, JSON.stringify({ format: FORMAT, test: id, fingerprint: hash, when: when.toISOString(), result: "passed" }, null, 1) + "\n");
    renameSync(part, final);
  } finally {
    rmSync(part, { force: true });
  }
  return final;
}

/**
 * At the head of a rebuild test: true where the quick sweep skips it (it has said so, through `t.skip`, and the test
 * returns); false where it runs. Where the cache was asked for and the test runs, its pass is recorded when it ends
 * passed and nothing it rests on changed while it ran. Where the cache was not asked for, nothing is read or written.
 * `options` (root, env, runtime, python) stand in for the checkout, the environment and the interpreters in a test.
 */
export async function passedBefore(t, spec = {}, options = {}) {
  const env = options.env || process.env;
  if (!asked(env)) return false;
  const root = options.root || ROOT;
  const file = spec.file || t.filePath;
  const id = testId(file, t.name, root);
  const folder = cacheFolder(env, root);
  const say = (text) => {
    try {
      t.diagnostic(`${SKIP_MARK} ${text}`);
    } catch {}
  };
  let first;
  try {
    first = fingerprint({ ...spec, file }, { ...options, root, env });
  } catch (error) {
    if (!(error instanceof Missing)) throw error;
    say(`runs, and records nothing: ${error.message}`);
    return false;
  }
  const force = Boolean(env.CELLS_TEST_FORCE) && env.CELLS_TEST_FORCE !== "0";
  const record = force ? null : readRecord(folder, id, first.hash);
  if (record) {
    t.skip(`${SKIP_MARK} passed before on these same inputs (fingerprint ${first.hash.slice(0, 12)}, recorded ${record.when}); npm test runs it`);
    return true;
  }
  say(force ? "runs (CELLS_TEST_FORCE)" : `runs: no pass recorded on these inputs (fingerprint ${first.hash.slice(0, 12)})`);
  t.after(() => {
    if (!t.passed) return;
    try {
      const last = fingerprint({ ...spec, file }, { ...options, root, env });
      if (last.hash !== first.hash) return say(`passed, and records nothing: what it rests on changed while it ran (${changedPart(first.lines, last.lines)})`);
      writeRecord(folder, id, first.hash);
      say(`passed; its pass is recorded (fingerprint ${first.hash.slice(0, 12)})`);
    } catch (error) {
      say(`passed, and records nothing: ${error.message}`);
    }
  });
  return false;
}
