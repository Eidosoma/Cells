// The quick sweep's own summary (npm run test:quick), beside node's own: how many tests it skipped because they had
// passed before on the same inputs (tests/lib/test_cache.mjs), each named, and that `npm test` runs them. A test
// skipped for any other reason is node's own count, not this one.
import path from "node:path";
import { ROOT, SKIP_MARK } from "./test_cache.mjs";

export default async function* quickSummary(source) {
  const skipped = [];
  for await (const event of source) {
    if (event.type !== "test:pass" || typeof event.data.skip !== "string" || !event.data.skip.startsWith(SKIP_MARK)) continue;
    skipped.push(`${event.data.file ? path.relative(ROOT, event.data.file) : "?"} › ${event.data.name}`);
  }
  if (!skipped.length) yield `ℹ ${SKIP_MARK} no test skipped (none had passed before on the same inputs)\n`;
  else {
    yield `ℹ ${SKIP_MARK} ${skipped.length} ${skipped.length === 1 ? "test" : "tests"} skipped, each passed before on the same inputs; npm test runs ${skipped.length === 1 ? "it" : "them"}:\n`;
    for (const name of skipped) yield `ℹ   ${name}\n`;
  }
}
