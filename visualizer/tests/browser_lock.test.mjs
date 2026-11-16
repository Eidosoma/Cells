// The browser lock keeps a run and the Chrome it starts on the run's processor
// (tools/lib/browser_lock.mjs). Chrome's software renderer pins its own worker threads
// elsewhere, so the lock looks at every thread of what the run started and puts a process
// with a thread elsewhere back.
//
//   node --test tests/browser_lock.test.mjs

import assert from "node:assert/strict";
import { execFileSync, spawn, spawnSync } from "node:child_process";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { cpusOf, descendants, keepOn, strays } from "../tools/lib/browser_lock.mjs";

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
