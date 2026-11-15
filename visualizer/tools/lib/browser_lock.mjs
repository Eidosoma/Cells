// One headless browser at a time. Screenshots and the input check each start a Chrome
// with software WebGL, which is heavy; several agents share this folder and this machine,
// so every browser run takes this lock first and waits its turn.

import { mkdirSync, rmSync, statSync, utimesSync } from "node:fs";
import path from "node:path";
import { ROOT } from "./build_page.mjs";

const LOCK = path.join(ROOT, "out", ".browser.lock");
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
  const beat = setInterval(() => {
    try {
      utimesSync(LOCK, new Date(), new Date());
    } catch {}
  }, 30000);
  beat.unref();
  let held = true;
  const release = () => {
    if (!held) return;
    held = false;
    clearInterval(beat);
    rmSync(LOCK, { recursive: true, force: true });
  };
  process.once("exit", release);
  for (const signal of ["SIGINT", "SIGTERM"]) {
    process.once(signal, () => {
      release();
      process.exit(130);
    });
  }
  return release;
}
