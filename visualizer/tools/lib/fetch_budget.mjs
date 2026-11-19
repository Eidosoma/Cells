// What an address of the published page may fetch beside the page, and the judgement of what it did fetch
// (tools/check_fetches.mjs). The table is data (tools/references/fetches.json): each address with the files it
// must fetch, the files it may fetch (by pattern) and a bound in bytes. A row of the table's `experiments` stands
// for one experiment at its opening run's address; the tool makes its patterns from the run's id. No browser here:
// the judgement is a function of what was asked, so that it is tested on its own (tests/fetch_budget.test.mjs).

import { Catalogue } from "../../src/replay/catalogue.js";

export const BUDGETS_FORMAT = "cells.visualizer.fetch_budgets@1";

/** A pattern of published paths (`*` is any run of characters but "/") as a test of one path. */
export function matcher(pattern) {
  const expression = new RegExp(`^${pattern.split("*").map((piece) => piece.replace(/[.+?^${}()|[\]\\]/g, "\\$&")).join("[^/]*")}$`);
  return (file) => expression.test(file);
}

/** Problems with the table itself: a row with no address, no bound, or nothing it must fetch (a page that drew nothing would pass it). */
export function tableProblems(table) {
  const problems = [];
  if (table?.format !== BUDGETS_FORMAT) return [`the table is ${table?.format}, not ${BUDGETS_FORMAT}`];
  const ids = new Set();
  for (const row of table.addresses || []) {
    const name = `address ${row?.id}`;
    if (typeof row?.id !== "string" || ids.has(row.id)) problems.push(`${name}: its id is missing or repeated`);
    ids.add(row?.id);
    if (typeof row?.query !== "string" || typeof row?.says !== "string") problems.push(`${name}: it needs its query and what it says`);
    if (!(Number.isFinite(row?.bytes) && row.bytes > 0)) problems.push(`${name}: it needs a bound in bytes`);
    for (const key of ["must", "allowed"]) if (!(Array.isArray(row?.[key]) && row[key].length && row[key].every((item) => typeof item === "string" && item))) problems.push(`${name}: ${key} must list patterns`);
  }
  const named = new Set();
  for (const row of table.experiments || []) {
    if (typeof row?.experiment !== "string" || named.has(row.experiment)) problems.push(`experiment ${row?.experiment}: its id is missing or repeated`);
    named.add(row?.experiment);
    if (!(Number.isFinite(row?.bytes) && row.bytes > 0)) problems.push(`experiment ${row?.experiment}: it needs a bound in bytes`);
  }
  if (table.page_bytes !== undefined && !(Number.isFinite(table.page_bytes) && table.page_bytes > 0)) problems.push("page_bytes must be a number of bytes");
  return problems;
}

/**
 * The addresses to load for a page whose catalogue (scene.replays) is `replays`: the table's own, then one for each
 * experiment of the table at its opening run (`lens=experiments&run=<id>`): its run's own file and the files of its parts
 * (runs/<id>.json, runs/<id>.<anything>.json), and nothing else. An experiment the page does not carry is skipped, and
 * said; an experiment the page carries that the table has no row for is a problem, so that a new one gets its budget.
 */
export function addressesOf(table, replays) {
  const catalogue = new Catalogue(replays || undefined);
  const rows = (table.addresses || []).map((row) => ({ ...row, kind: "address" }));
  const skipped = [], problems = [];
  for (const row of table.experiments || []) {
    const run = catalogue.runs.some((item) => item.experiment === row.experiment) ? catalogue.openingRun(row.experiment) : null;
    if (!run) {
      skipped.push(`${row.experiment}: the page carries no run of it`);
      continue;
    }
    rows.push({
      kind: "experiment",
      id: row.experiment,
      experiment: row.experiment,
      run,
      query: `lens=experiments&run=${run}`,
      says: row.says || `${row.experiment} by its address: its opening run and the parts its opening view shows, and no other run`,
      must: [`runs/${run}.json`],
      allowed: [`runs/${run}.json`, `runs/${run}.*.json`, ...(row.also || [])],
      bytes: row.bytes,
      files: row.files,
    });
  }
  const covered = new Set((table.experiments || []).map((row) => row.experiment));
  for (const experiment of new Set(catalogue.runs.map((run) => run.experiment))) {
    if (!covered.has(experiment)) problems.push(`the page carries runs of ${experiment}, and the table gives it no budget: add a row to its experiments`);
  }
  return { rows, skipped, problems };
}

/**
 * What one address fetched, judged against its row. `asked` lists every file the page asked the server for beside the
 * page, in the order asked: { path, bytes, status }. Returns { total, problems }: each problem names the file.
 */
export function judge(row, asked) {
  const problems = [];
  const allowed = row.allowed.map(matcher);
  const seen = new Set();
  for (const file of asked) {
    if (seen.has(file.path)) problems.push(`${file.path} was fetched twice`);
    seen.add(file.path);
    if (file.status !== 200) problems.push(`${file.path} was asked for and the page does not publish it (it answered ${file.status})`);
    else if (!allowed.some((test) => test(file.path))) problems.push(`${file.path} (${file.bytes} bytes) is not one this address may fetch`);
  }
  for (const pattern of row.must) {
    const test = matcher(pattern);
    if (!asked.some((file) => file.status === 200 && test(file.path))) problems.push(`nothing that matches ${pattern} was fetched: the address did not draw what it is for`);
  }
  let total = 0;
  for (const file of asked) {
    total += file.bytes;
    if (total > row.bytes) {
      problems.push(`${file.path} took what the address fetched to ${total} bytes, past its bound of ${row.bytes}`);
      break;
    }
  }
  if (Number.isInteger(row.files) && asked.length > row.files) problems.push(`${asked[row.files].path} is file ${row.files + 1}, past the bound of ${row.files} files`);
  return { total: asked.reduce((sum, file) => sum + file.bytes, 0), problems };
}
