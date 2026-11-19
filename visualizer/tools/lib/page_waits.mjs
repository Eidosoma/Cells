// Waits on the page's own state, for the check tools: never a fixed time after a load or a press.
//
//   const { settled, until, stable, quiet, bring } = pageWaits({ evaluate, asked });
//
// `evaluate(expression)` is the tool's own (Runtime.evaluate with awaitPromise and returnByValue); `asked` is the list of
// paths the tool's server has been asked for, where the tool keeps one (for `quiet`).
//
//   settled()      until the page is at rest for two frames running: the viewer's busy() (src/core/busy.js) says
//                  nothing on two animation frames in a row. Its time run out, it fails with the reasons still held,
//                  so that a hang says what hung. Whether the page's own fonts have arrived is said beside it
//                  (`fonts`), never waited on. Never before a check that something did not happen, nor before a count
//                  of what was fetched, logged or drawn: there the pause is the window the check watches over (stated
//                  where it stands, or `quiet`).
//   until(e)       until the expression `e` reads true in the page (false when its time runs out)
//   stable(e)      what `e` reads once it reads the same twice running (the page has stopped moving it)
//   quiet(ms)      until the server has been asked for nothing more for `ms`: the page's fetches have ended
//   bring(e)       scrolls what `e` finds to the middle of its scroller and waits until it stands in the window
//
// Proved first in tools/check_landing.mjs (19 November 2026), whose own copies these are.

export const VIEWER = "document.querySelector('cells-viewer')";
export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export function pageWaits({ evaluate, asked = null, viewer = VIEWER } = {}) {
  if (typeof evaluate !== "function") throw new Error("pageWaits needs the tool's evaluate");

  /**
   * Until the page is at rest for `frames` animation frames running (two unless said); fails, saying why, after `most` ms.
   * With `moving`, for a view that plays on (a replay playing, a picture of it): its motion and the frames it owes for it
   * are let be, and the rest must hold while the stage draws `frames` frames. `moving: "auto"` lets them be only while the
   * view's player is playing (after a press that may start a play, or not), or once the view has moved with nothing else
   * held for `self` ms (1500 unless said): a view that moves by itself (the origin's assembly, a machine's turn) has no rest
   * but its motion, and is read once nothing of it loads, flies or is on its way.
   */
  const settled = async ({ most = 30000, frames = 2, moving = false, self = 1500 } = {}) => {
    const result = await evaluate(`new Promise((resolve) => {
      const v = ${viewer}, began = performance.now(), drawn = () => v?.stage?.renderer?.info?.render?.frame ?? 0, first = drawn();
      const MOTION = new Set(["a view is moving", "a frame is owed"]), mode = ${JSON.stringify(moving)};
      let onlyMotion = null; // since when the view has moved with nothing else held
      const allowed = () => mode === true || (mode === "auto" && (Boolean(v?.current?.player?.playing) || (onlyMotion !== null && performance.now() - onlyMotion >= ${Number(self)})));
      let calm = 0, done = false, reasons = [];
      const end = (rested) => { if (done) return; done = true; resolve({ rested, reasons, fonts: document.fonts?.status ?? null, ms: Math.round(performance.now() - began) }); };
      const look = () => {
        if (done) return;
        if (mode === "auto" && v && typeof v.busy === "function") {
          const held = v.busy();
          const motion = held.length > 0 && held.every((reason) => MOTION.has(reason));
          onlyMotion = motion ? (onlyMotion ?? performance.now()) : null;
        }
        const allow = allowed();
        reasons = !v ? ["the page has no viewer"] : typeof v.busy !== "function" ? ["the page says nothing of what it is busy with (no busy())"] : v.busy().filter((reason) => !(allow && MOTION.has(reason)));
        calm = reasons.length ? 0 : calm + 1;
        if (calm >= ${Number(frames)} && (!allow || drawn() - first >= ${Number(frames)})) return end(true);
        requestAnimationFrame(look);
      };
      setTimeout(() => end(false), ${Number(most)});
      requestAnimationFrame(look);
    })`);
    if (!result?.rested) throw new Error(`the page did not come to rest within ${most} ms: ${(result?.reasons || ["no answer"]).join("; ") || "no frame was drawn to look at"}`);
    return result;
  };

  /** Until `expression` reads true in the page; false when `ms` runs out. */
  const until = async (expression, ms = 30000, every = 200) => {
    const start = Date.now();
    while (Date.now() - start < ms) {
      if (await evaluate(expression).catch(() => false)) return true;
      await sleep(every);
    }
    return false;
  };

  /** What `expression` reads once it reads the same twice running; its last reading when `ms` runs out. */
  const stable = async (expression, ms = 20000, every = 250) => {
    const start = Date.now();
    let last = await evaluate(expression).catch(() => null);
    while (Date.now() - start < ms) {
      await sleep(every);
      const now = await evaluate(expression).catch(() => null);
      if (now !== null && JSON.stringify(now) === JSON.stringify(last)) return now;
      last = now;
    }
    return last;
  };

  /** Until the server has been asked for nothing more for `ms` (the page's fetches have ended); false after `most`. */
  const quiet = async (ms = 1500, most = 30000) => {
    if (!Array.isArray(asked)) throw new Error("quiet needs the list of what the server was asked for");
    const start = Date.now();
    let count = asked.length, since = Date.now();
    while (Date.now() - start < most) {
      await sleep(150);
      if (asked.length !== count) (count = asked.length), (since = Date.now());
      else if (Date.now() - since >= ms) return true;
    }
    return false;
  };

  /** Scrolls what `element` finds to the middle of its scroller and waits until it stands in the window (or in `box`). */
  const bring = async (element, { box = null, ms = 10000 } = {}) => {
    await evaluate(`(() => { const el = ${element}; el?.scrollIntoView({ block: "center" }); return Boolean(el); })()`);
    const within = box ? `(() => { const b = (${box}).getBoundingClientRect(); return r.bottom > b.top && r.top < b.bottom; })()` : "r.bottom > 0 && r.top < innerHeight";
    return until(`(() => { const el = ${element}; if (!el || !el.checkVisibility()) return false; const r = el.getBoundingClientRect(); return ${within}; })()`, ms);
  };

  return { settled, until, stable, quiet, bring };
}
