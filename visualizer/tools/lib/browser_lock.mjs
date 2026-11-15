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
import { mkdirSync, rmSync, statSync, utimesSync } from "node:fs";
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
  // A browser run draws in software and can take a whole processor or more. The engine's own
  // jobs share this machine and come first (the lead's request, 15 November 2026): the run and
  // the Chrome it starts take the lowest priority and keep to one processor (CELLS_BROWSER_CPU,
  // 3 by default; "any" leaves them free). Both are inherited by what the run starts.
  try {
    os.setPriority(19);
  } catch {}
  const cpu = process.env.CELLS_BROWSER_CPU || "3";
  if (cpu !== "any") {
    try {
      execFileSync("taskset", ["-a", "-cp", cpu, String(process.pid)], { stdio: "ignore" });
    } catch {}
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
