// The browser lock gives each browser run a place: a share of the processors set aside for
// browser runs, whole cores (tools/lib/browser_lock.mjs). It keeps the run and the Chrome it
// starts there: Chrome's software renderer pins its own worker threads elsewhere, so the
// lock looks at every thread of what the run started and puts a process with a thread
// elsewhere back.
//
//   node --test tests/browser_lock.test.mjs

import assert from "node:assert/strict";
import { execFileSync, spawn, spawnSync } from "node:child_process";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { acquireBrowser, BROWSER_CPUS, cpusOf, descendants, keepOn, places, shares, strays } from "../tools/lib/browser_lock.mjs";

test("a list of processors is read as the kernel and taskset write one", () => {
  assert.deepEqual([...cpusOf("3")], [3]);
  assert.deepEqual([...cpusOf("0-3,7")], [0, 1, 2, 3, 7]);
  assert.deepEqual([...cpusOf(" 2 , 5-6 ")], [2, 5, 6]);
  assert.deepEqual([...cpusOf("any")], [], "a word that names no processor names none");
  assert.deepEqual([...cpusOf("4-2")], [], "a range that runs backwards names none");
});

/** A stand-in for /proc: each process with its parent and the processors each of its threads may run on. */
async function proc(folder, processes) {
  for (const [pid, { name = "x", parent, threads }] of Object.entries(processes)) {
    await mkdir(path.join(folder, pid), { recursive: true });
    await writeFile(path.join(folder, pid, "stat"), `${pid} (${name}) S ${parent} ${pid} ${pid} 0 -1 4194560`);
    for (const [task, cpus] of Object.entries(threads || { [pid]: "0-7" })) {
      await mkdir(path.join(folder, pid, "task", task), { recursive: true });
      await writeFile(path.join(folder, pid, "task", task, "status"), `Name:\t${name}\nCpus_allowed:\tff\nCpus_allowed_list:\t${cpus}\nvoluntary_ctxt_switches:\t1\n`);
    }
  }
  await mkdir(path.join(folder, "self"), { recursive: true }); // entries that are no process are passed over
  await writeFile(path.join(folder, "uptime"), "1 1");
}

test("what a run started is found through each process's parent, whatever a process is called", async () => {
  const folder = await mkdtemp(path.join(os.tmpdir(), "browser-lock-"));
  try {
    await proc(folder, {
      10: { name: "node", parent: 1 },
      11: { name: "chrome", parent: 10 },
      12: { name: "chrome (gpu) x", parent: 11 }, // a name with brackets and spaces
      13: { name: "chrome", parent: 12 },
      20: { name: "other", parent: 1 },
      21: { name: "other", parent: 20 },
    });
    assert.deepEqual(descendants(10, folder).sort(), [11, 12, 13]);
    assert.deepEqual(descendants(20, folder), [21]);
    assert.deepEqual(descendants(13, folder), []);
    assert.deepEqual(descendants(10, path.join(folder, "nowhere")), [], "where /proc cannot be read nothing is found, and nothing is thrown");
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});

test("a process is a stray when any one of its threads may run outside the run's processors", async () => {
  const folder = await mkdtemp(path.join(os.tmpdir(), "browser-lock-"));
  try {
    await proc(folder, {
      11: { parent: 10, threads: { 11: "3", 111: "3" } },
      // The software renderer's case: the process on its processor, eight workers pinned to processor 0.
      12: { parent: 11, threads: { 12: "3", 121: "0", 122: "0" } },
      13: { parent: 11, threads: { 13: "2-3" } },
      14: { parent: 11, threads: { 14: "3" } },
    });
    assert.deepEqual(strays([11, 12, 13, 14], cpusOf("3"), folder), [12, 13]);
    assert.deepEqual(strays([11, 12, 13, 14], cpusOf("2-3"), folder), [12]);
    assert.deepEqual(strays([11, 99], cpusOf("3"), folder), [], "a process that has ended is passed over");
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});

const cpus = (() => {
  try {
    return [...cpusOf(execFileSync("taskset", ["-cp", String(process.pid)], { encoding: "utf8" }).split(":").pop())];
  } catch {
    return [];
  }
})();

test("a child that moved itself to another processor is put back", { skip: cpus.length < 2 ? "needs taskset and two processors this process may use" : false }, async () => {
  const [home, away] = cpus;
  const child = spawn("sleep", ["30"], { stdio: "ignore" });
  try {
    const where = () => execFileSync("taskset", ["-cp", String(child.pid)], { encoding: "utf8" }).split(":").pop().trim();
    assert.equal(spawnSync("taskset", ["-cp", String(away), String(child.pid)]).status, 0);
    assert.equal(where(), String(away));
    assert.deepEqual(keepOn(String(home)), [child.pid], "the one process that strayed is moved");
    assert.equal(where(), String(home));
    assert.deepEqual(keepOn(String(home)), [], "and nothing is done where nothing strays");
  } finally {
    child.kill();
  }
});

// The project's machine: processor n and n + 16 are the two threads of core n.
const twoThreads = (cpu) => cpu % 16;

test("the processors set aside are shared out as whole cores, both threads of a core together", () => {
  assert.deepEqual(shares("12-15,28-31", 4, twoThreads), ["12,28", "13,29", "14,30", "15,31"]);
  assert.deepEqual(shares("12-15,28-31", 2, twoThreads), ["12,14,28,30", "13,15,29,31"]);
  assert.deepEqual(shares("12-15,28-31", 1, twoThreads), ["12,13,14,15,28,29,30,31"]);
  assert.deepEqual(shares("12-15,28-31", 9, twoThreads), ["12,28", "13,29", "14,30", "15,31"], "never more shares than cores");
  assert.deepEqual(shares("3", 4, twoThreads), ["3"]);
  assert.deepEqual(shares("12-15", 3, (cpu) => cpu), ["12,15", "13", "14"], "where each processor is its own core, they are dealt in turn");
  assert.deepEqual(shares("none", 2, twoThreads), [], "a list that names no processor gives no share");
  // No processor is given twice, and none is left out.
  for (const slots of [1, 2, 3, 4]) assert.deepEqual(shares(BROWSER_CPUS, slots, twoThreads).flatMap((list) => [...cpusOf(list)]).sort((a, b) => a - b), [12, 13, 14, 15, 28, 29, 30, 31]);
});

test("the places follow the two settings, and 'any' leaves the runs free", () => {
  assert.equal(places({}).length >= 1, true);
  assert.deepEqual(places({ CELLS_BROWSER_CPU: "any", CELLS_BROWSER_SLOTS: "3" }), ["any", "any", "any"]);
  assert.deepEqual(places({ CELLS_BROWSER_CPU: "any" }).every((place) => place === "any"), true);
  assert.equal(places({ CELLS_BROWSER_CPU: "0", CELLS_BROWSER_SLOTS: "4" }).length, 1, "one processor is one place, whatever is asked");
  assert.deepEqual(places({ CELLS_BROWSER_CPU: "nothing" }), ["any"], "a list that names no processor leaves the run free and does not stop it");
});

test("two runs hold two places at once, a third waits, and a place given back is taken again", async () => {
  const before = { ...process.env };
  process.env.CELLS_BROWSER_CPU = "any"; // the places are what is tested here, not the pinning
  process.env.CELLS_BROWSER_SLOTS = "2";
  let first = null, second = null, third = null;
  // In a folder of its own, so that a real browser run going on beside the test neither helps nor hinders it.
  const at = await mkdtemp(path.join(os.tmpdir(), "browser-places-"));
  try {
    first = await acquireBrowser({ wait: 4000, at });
    second = await acquireBrowser({ wait: 4000, at });
    assert.deepEqual([first.slot, second.slot].sort(), [0, 1], "each has a place of its own");
    await assert.rejects(acquireBrowser({ wait: 1500, at }), /held the lock for too long/, "a third run waits, and says so when its wait runs out");
    assert.notEqual(first.profile, second.profile, "and a profile of its own");
    first();
    first = null;
    third = await acquireBrowser({ wait: 4000, at });
    assert.equal([0, 1].includes(third.slot), true);
    assert.notEqual(third.slot, second.slot, "the place that was given back is the one taken");
  } finally {
    for (const release of [first, second, third]) release?.();
    await rm(at, { recursive: true, force: true });
    process.env.CELLS_BROWSER_CPU = before.CELLS_BROWSER_CPU ?? "";
    process.env.CELLS_BROWSER_SLOTS = before.CELLS_BROWSER_SLOTS ?? "";
    if (before.CELLS_BROWSER_CPU === undefined) delete process.env.CELLS_BROWSER_CPU;
    if (before.CELLS_BROWSER_SLOTS === undefined) delete process.env.CELLS_BROWSER_SLOTS;
  }
});

