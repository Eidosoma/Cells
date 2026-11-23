// A few headless browsers at a time, each in a place of its own. Screenshots and the click
// checks each start a Chrome with software WebGL, which is heavy; the engine's jobs share
// this machine, and several agents share this folder. So every browser run takes one of a
// few places first and waits its turn when all are taken. A place is a share of the
// processors set aside for browser runs: whole cores, both threads of a core together.
//
// The place also gives the run its browser profile folder. Left to itself, Chrome makes a
// profile under /tmp and leaves it there when it is stopped: about 130 MB a run, and /tmp
// is memory on some machines (82 of them, 11 GB, once ran this machine out of memory).
// So every run passes `--user-data-dir=<release.profile>`, a folder on disk under out/,
// which is removed when the run ends. Whoever takes a place sweeps the profiles of runs
// that died.

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, utimesSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { ROOT } from "./build_page.mjs";

// The places are one set for every checkout of the viewer on this machine. Since 16 November 2026 each agent
// works in a checkout of its own, and places kept under each checkout's out/ were several sets over the same
// processors: two checkouts' first places are the same core, two browsers then shared it, and a page took two
// minutes to open (17 November 2026, the phone agent's finding). A check that reads the keyboard's focus had
// missed once that day while other runs loaded the same processors; which load it was, was not measured.
// So where the folder that holds the agents' checkouts stands, the places are kept there; elsewhere (another
// machine, a copy with no such folder) under this checkout's out/. CELLS_BROWSER_PLACES names another folder.
const SHARED = "/mnt/workspaces/Cells/visualizer-worktrees";
export const PLACES_HOME = process.env.CELLS_BROWSER_PLACES || (existsSync(SHARED) ? path.join(SHARED, ".browser-places") : path.join(ROOT, "out"));
const LOCK = path.join(PLACES_HOME, ".browser.lock"); // place n is this folder's name with ".n" after it
// A separate disk can hold the browser profiles while every checkout still shares the same CPU slots.
const PROFILES = path.join(process.env.CELLS_BROWSER_PROFILE_HOME || path.join(ROOT, "out"), ".browser-profiles");
const gone = (folder) => {
  try {
    rmSync(folder, { recursive: true, force: true, maxRetries: 8, retryDelay: 250 });
  } catch {}
};
const STALE_MS = 3 * 60 * 1000; // a holder refreshes its place every 30 s; older than this, it is gone
/** The processors set aside for browser runs on the project's machine, unless CELLS_BROWSER_CPU names others. */
export const BROWSER_CPUS = "12-15,28-31";
/** How many browsers may run at once, unless CELLS_BROWSER_SLOTS says otherwise: one for each core set aside. */
export const BROWSER_SLOTS = 4;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// ---------------------------------------------------------------- keeping a run on its processors
//
// The affinity a run is given is inherited by the Chrome it starts, but it is no fence: a
// process may move its own threads. Chrome's software renderer does. It counts the processors
// it is allowed and pins its worker threads to that many processors counted from nought,
// so with the run on processor 3 its eight threads sat on processor 0, where an engine job
// ran (seen on 16 November 2026); allowed eight, it would take processors 0 to 7. A scope
// bound to the run's processors would hold them, but this
// user's session is given no cpuset controller. So, while a run holds its place, every thread
// of what it started is looked at once a second, and a process with a thread elsewhere is
// put back.

/** The processors a list names, as the kernel and taskset write one ("3", "0-3,7"). */
export function cpusOf(list) {
  const cpus = new Set();
  for (const part of String(list).split(",")) {
    const [from, to = from] = part.trim().split("-").map(Number);
    if (!Number.isInteger(from) || !Number.isInteger(to) || from < 0 || to < from) continue;
    for (let cpu = from; cpu <= to; cpu++) cpus.add(cpu);
  }
  return cpus;
}

/** Every process that `root` started, directly or through another, from what each process says its parent is (Linux's /proc). */
export function descendants(root, proc = "/proc") {
  const children = new Map();
  let entries = [];
  try {
    entries = readdirSync(proc);
  } catch {
    return [];
  }
  for (const name of entries) {
    if (!/^\d+$/.test(name)) continue;
    try {
      // "pid (name) state parent ...": the name may hold spaces and brackets, so read from its last bracket on.
      const stat = readFileSync(path.join(proc, name, "stat"), "utf8");
      const parent = Number(stat.slice(stat.lastIndexOf(")") + 2).split(" ")[1]);
      if (!children.has(parent)) children.set(parent, []);
      children.get(parent).push(Number(name));
    } catch {} // gone between the listing and the read
  }
  const found = [];
  for (const queue = [Number(root)]; queue.length; ) {
    for (const child of children.get(queue.shift()) || []) {
      found.push(child);
      queue.push(child);
    }
  }
  return found;
}

/** Those of `pids` with a thread that may run on a processor outside `allowed`. */
export function strays(pids, allowed, proc = "/proc") {
  const out = [];
  for (const pid of pids) {
    let tasks = [];
    try {
      tasks = readdirSync(path.join(proc, String(pid), "task"));
    } catch {
      continue; // the process has ended
    }
    for (const task of tasks) {
      try {
        const line = readFileSync(path.join(proc, String(pid), "task", task, "status"), "utf8").match(/^Cpus_allowed_list:\s*(.*)$/m);
        if (line && [...cpusOf(line[1])].some((cpu) => !allowed.has(cpu))) {
          out.push(pid);
          break;
        }
      } catch {} // the thread has ended
    }
  }
  return out;
}

/** Puts every thread of what `root` started back on the processors of `list`. Returns the processes it moved. */
export function keepOn(list, root = process.pid) {
  const moved = [];
  for (const pid of strays(descendants(root), cpusOf(list))) {
    try {
      execFileSync("taskset", ["-a", "-cp", String(list), String(pid)], { stdio: "ignore" });
      moved.push(pid);
    } catch {} // ended meanwhile, or no taskset on this machine
  }
  return moved;
}

// ---------------------------------------------------------------- places

/** Which core a processor is a thread of, as the kernel says; where it does not say, each processor is its own core. */
function coreOfCpu(cpu) {
  try {
    const at = `/sys/devices/system/cpu/cpu${cpu}/topology`;
    return `${readFileSync(`${at}/physical_package_id`, "utf8").trim()}:${readFileSync(`${at}/core_id`, "utf8").trim()}`;
  } catch {
    return `cpu${cpu}`;
  }
}

/**
 * The processors of `list` shared out among `slots` browsers at once, as lists: whole cores,
 * so that the two threads of a core stay with one browser, dealt in turn. Never more shares
 * than cores. Eight processors on four cores give four shares of one core each, two of two
 * cores each, or one of all four.
 */
export function shares(list, slots, coreOf = coreOfCpu) {
  const cores = new Map();
  for (const cpu of [...cpusOf(list)].sort((a, b) => a - b)) {
    const core = coreOf(cpu);
    if (!cores.has(core)) cores.set(core, []);
    cores.get(core).push(cpu);
  }
  const groups = [...cores.values()];
  if (!groups.length) return [];
  const count = Math.max(1, Math.min(Math.floor(slots) || 1, groups.length));
  const out = Array.from({ length: count }, () => []);
  groups.forEach((group, index) => out[index % count].push(...group));
  return out.map((group) => group.sort((a, b) => a - b).join(","));
}

/** The places browser runs take: one list of processors each, or "any" for each where the runs are left free. */
export function places(env = process.env) {
  const cpu = env.CELLS_BROWSER_CPU || BROWSER_CPUS;
  const asked = Math.max(1, Math.floor(Number(env.CELLS_BROWSER_SLOTS || BROWSER_SLOTS)) || 1);
  if (cpu === "any") return Array.from({ length: asked }, () => "any");
  const found = shares(cpu, asked);
  return found.length ? found : ["any"];
}

const alive = (pid) => {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return error.code === "EPERM";
  }
};

/**
 * Waits for a place and returns the function that gives it back. `at` is the folder the
 * places and the profiles are kept in: the project's out/ unless a test names another.
 */
export async function acquireBrowser({ wait = 20 * 60 * 1000, at = null } = {}) {
  const lock = at ? path.join(at, ".browser.lock") : LOCK, profiles = at ? path.join(at, ".browser-profiles") : PROFILES;
  mkdirSync(path.dirname(lock), { recursive: true });
  const all = places();
  const started = Date.now();
  let slot = -1;
  while (slot < 0) {
    for (let n = 0; n < all.length && slot < 0; n++) {
      const folder = `${lock}.${n}`;
      try {
        mkdirSync(folder);
        slot = n;
      } catch (error) {
        if (error.code !== "EEXIST") throw error;
        try {
          // A holder that died left its place behind: it is free again once its refreshes have stopped.
          if (Date.now() - statSync(folder).mtimeMs > STALE_MS) rmSync(folder, { recursive: true, force: true });
        } catch {} // released between the two calls
      }
    }
    if (slot >= 0) break;
    if (Date.now() - started > wait) throw new Error("the browser runs before this one have held the lock for too long");
    await sleep(1000 + Math.random() * 1000);
  }
  const folder = `${lock}.${slot}`;
  // A browser run draws in software and can take several processors, and the engine's own
  // jobs share this machine. So the run and the Chrome it starts keep to the processors of
  // their place, at the usual priority. The places share out the processors set aside for
  // browser runs (CELLS_BROWSER_CPU, a list as taskset takes one; "any" leaves the runs free;
  // CELLS_BROWSER_SLOTS, how many runs at once). Since the machine grew to 16 cores on 16
  // November 2026 those are cores 12 to 15 with both their threads, processors 12-15 and
  // 28-31 (the user: "you can use 4 cores and 8 CPUs"), one core for each of four runs; the
  // engine's jobs have the rest. CELLS_BROWSER_NICE lowers the priority when the engine's
  // jobs must come first (19 is the lowest). All of it is inherited by what the run starts.
  const nice = Number(process.env.CELLS_BROWSER_NICE || 0);
  if (nice > 0) {
    try {
      os.setPriority(Math.min(19, nice));
    } catch {}
  }
  const cpu = all[slot];
  let keep = null;
  if (cpu !== "any") {
    try {
      execFileSync("taskset", ["-a", "-cp", cpu, String(process.pid)], { stdio: "ignore" });
    } catch {}
    // The Chrome this run starts moves some of its own threads elsewhere (see keepOn): bring them
    // back. It does so as it starts, so for the run's first ten seconds they are looked for six
    // times a second, and once a second after that.
    const back = () => {
      try {
        keepOn(cpu);
      } catch {}
    };
    const first = setInterval(back, 150);
    first.unref();
    setTimeout(() => clearInterval(first), 10000).unref();
    keep = setInterval(back, 1000);
    keep.unref();
  }
  const beat = setInterval(() => {
    try {
      utimesSync(folder, new Date(), new Date());
    } catch {}
  }, 30000);
  beat.unref();
  // A profile is named by its run's process: one whose process is gone was left by a run
  // that died, and is swept. Other runs' profiles are in use and stay.
  try {
    for (const name of readdirSync(profiles)) if (!/^\d+(-\d+)?$/.test(name) || !alive(Number(name.split("-")[0]))) gone(path.join(profiles, name));
  } catch {} // no profile has been made yet
  // One process may hold several places (a test does): each has a profile of its own.
  const profile = path.join(profiles, slot === 0 ? String(process.pid) : `${process.pid}-${slot}`);
  mkdirSync(profile, { recursive: true });
  let held = true;
  const release = () => {
    if (!held) return;
    held = false;
    clearInterval(beat);
    if (keep) clearInterval(keep);
    gone(profile);
    rmSync(folder, { recursive: true, force: true });
  };
  release.profile = profile;
  release.slot = slot;
  release.cpus = cpu;
  process.once("exit", release);
  for (const signal of ["SIGINT", "SIGTERM"]) {
    process.once(signal, () => {
      release();
      process.exit(130);
    });
  }
  return release;
}
