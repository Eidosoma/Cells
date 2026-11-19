#!/usr/bin/env node
// Whether two runs of a scenario held the same checks: the names of the checks each log holds ("pass  NAME" or
// "FAIL  NAME", the detail in brackets after two spaces left out), with every number in a name set aside (many names
// carry what a run measured), compared as lists. A change to a check tool's waits keeps this list as it was.
//
//   node tools/check_names.mjs BEFORE.log AFTER.log [BEFORE.log AFTER.log ...]
//   node tools/check_names.mjs --dirs BEFORE_DIR AFTER_DIR [NAME ...]    (each scenario's NAME.log in both folders)
//
// Ends with 0 when every pair holds the same list, 1 otherwise, saying what differs.
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

/** The names of the checks a log holds, in order, every number set aside as "#". */
export function checkNames(text) {
  const names = [];
  for (const line of String(text).split("\n")) {
    const match = line.match(/^(?:pass|FAIL)  (.*)$/);
    if (!match) continue;
    // The detail a check prints after its name: two spaces and a bracket, to the end of the line.
    const name = match[1].replace(/ {2}\(.*$/, "");
    names.push(name.replace(/-?\d[\d,.]*(?:e[+-]?\d+)?/gi, "#"));
  }
  return names;
}

/** What differs between two lists of names: those only before, only after, and whether the order changed. */
export function compareNames(before, after) {
  const count = (list) => list.reduce((map, name) => map.set(name, (map.get(name) || 0) + 1), new Map());
  const a = count(before), b = count(after);
  const only = (x, y) => [...x].flatMap(([name, n]) => Array(Math.max(0, n - (y.get(name) || 0))).fill(name));
  return { same: JSON.stringify(before) === JSON.stringify(after), onlyBefore: only(a, b), onlyAfter: only(b, a), before: before.length, after: after.length };
}

if (import.meta.url === `file://${process.argv[1]}` || process.argv[1]?.endsWith("check_names.mjs")) {
  const args = process.argv.slice(2);
  const pairs = [];
  if (args[0] === "--dirs") {
    const [, from, to, ...names] = args;
    for (const name of names) pairs.push([path.join(from, `${name}.log`), path.join(to, `${name}.log`)]);
  } else for (let n = 0; n + 1 < args.length; n += 2) pairs.push([args[n], args[n + 1]]);
  if (!pairs.length) {
    console.error("usage: node tools/check_names.mjs BEFORE.log AFTER.log [...] | --dirs BEFORE_DIR AFTER_DIR NAME ...");
    process.exit(2);
  }
  let bad = 0;
  for (const [from, to] of pairs) {
    if (!existsSync(from) || !existsSync(to)) {
      console.log(`FAIL  ${path.basename(to)}: ${existsSync(from) ? to : from} is not there`);
      bad += 1;
      continue;
    }
    const result = compareNames(checkNames(readFileSync(from, "utf8")), checkNames(readFileSync(to, "utf8")));
    if (result.same) console.log(`same  ${path.basename(to, ".log")}: ${result.after} checks, the same names in the same order`);
    else {
      bad += 1;
      console.log(`FAIL  ${path.basename(to, ".log")}: ${result.before} checks before, ${result.after} after`);
      for (const name of result.onlyBefore) console.log(`      only before: ${name}`);
      for (const name of result.onlyAfter) console.log(`      only after:  ${name}`);
      if (!result.onlyBefore.length && !result.onlyAfter.length) console.log("      the same names in another order");
    }
  }
  process.exit(bad ? 1 : 0);
}
