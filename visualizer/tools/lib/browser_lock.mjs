// One headless browser at a time. Screenshots and the input check each start a Chrome
// with software WebGL, which is heavy; several agents share this folder and this machine,
// so every browser run takes this lock first and waits its turn.
//
// The lock also gives the run its browser profile folder. Left to itself, Chrome makes a
// profile under /tmp and leaves it there when it is stopped: about 130 MB a run, and /tmp
// is memory on some machines (82 of them, 11 GB, once ran this machine out of memory).
// So every run passes `--user-data-dir=<release.profile>`, a folder on disk under out/,
// which is removed when the run ends. Whoever takes the lock first sweeps what a run
// that died left behind.

import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync, readFileSync, rmSync, statSync, utimesSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { ROOT } from "./build_page.mjs";

const LOCK = path.join(ROOT, "out", ".browser.lock");
const PROFILES = path.join(ROOT, "out", ".browser-profiles");
const gone = (folder) => {
  try {
    rmSync(folder, { recursive: true, force: true, maxRetries: 8, retryDelay: 250 });
  } catch {}
};
const STALE_MS = 3 * 60 * 1000; // a holder refreshes the lock every 30 s; older than this, it is gone
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// ---------------------------------------------------------------- keeping a run on its processor
//
// The affinity a run is given is inherited by the Chrome it starts, but it is no fence: a
// process may move its own threads. Chrome's software renderer does. It counts the processors
// it is allowed (one) and pins its worker threads to that many processors counted from nought,
// so with the run on processor 3 its eight threads sat on processor 0, where an engine job
// ran (seen on 16 November 2026). A scope bound to a processor would hold them, but this
// user's session is given no cpuset controller. So, while a run holds the lock, every thread
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

/** Waits for the lock and returns the function that gives it back. */
export async function acquireBrowser({ wait = 20 * 60 * 1000 } = {}) {
  mkdirSync(path.dirname(LOCK), { recursive: true });
  const started = Date.now();
  for (;;) {
    try {
      mkdirSync(LOCK);
      break;
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
      let age = 0;
      try {
        age = Date.now() - statSync(LOCK).mtimeMs;
      } catch {
        continue; // released between the two calls
      }
      if (age > STALE_MS) {
        rmSync(LOCK, { recursive: true, force: true });
        continue;
      }
      if (Date.now() - started > wait) throw new Error("another browser run has held the lock for too long");
      await sleep(1000 + Math.random() * 1000);
    }
  }
  // A browser run draws in software and can take a whole processor or more, and the engine's
  // own jobs share this machine. So the run and the Chrome it starts keep to one processor
  // (CELLS_BROWSER_CPU, 3 by default; "any" leaves them free), at the usual priority (the
  // user, 15 November 2026: more priority again, but still just on one). CELLS_BROWSER_NICE
  // lowers the priority when the engine's jobs must come first (19 is the lowest). Both are
  // inherited by what the run starts.
  const nice = Number(process.env.CELLS_BROWSER_NICE || 0);
  if (nice > 0) {
    try {
      os.setPriority(Math.min(19, nice));
    } catch {}
  }
  const cpu = process.env.CELLS_BROWSER_CPU || "3";
  let keep = null;
  if (cpu !== "any") {
    try {
      execFileSync("taskset", ["-a", "-cp", cpu, String(process.pid)], { stdio: "ignore" });
    } catch {}
    // The Chrome this run starts moves some of its own threads elsewhere (see keepOn): bring them back, once a second.
    keep = setInterval(() => {
      try {
        keepOn(cpu);
      } catch {}
    }, 1000);
    keep.unref();
  }
  const beat = setInterval(() => {
    try {
      utimesSync(LOCK, new Date(), new Date());
    } catch {}
  }, 30000);
  beat.unref();
  // Holding the lock, no other run's browser is alive: whatever is in the profiles
  // folder was left by a run that died.
  gone(PROFILES);
  const profile = path.join(PROFILES, String(process.pid));
  mkdirSync(profile, { recursive: true });
  let held = true;
  const release = () => {
    if (!held) return;
    held = false;
    clearInterval(beat);
    if (keep) clearInterval(keep);
    gone(profile);
    rmSync(LOCK, { recursive: true, force: true });
  };
  release.profile = profile;
  process.once("exit", release);
  for (const signal of ["SIGINT", "SIGTERM"]) {
    process.once(signal, () => {
      release();
      process.exit(130);
    });
  }
  return release;
}
