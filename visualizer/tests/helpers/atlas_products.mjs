// What the species tests share about a product of a species atlas (schema/SPECIES_ATLAS.md, format @2):
// the families that only go with a machine, read from the table every species is asked by
// (tools/build_mpneumoniae_atlas.py, FAMILIES, and tools/lib/proteome_shelves.py, ACCESSORY), so that
// a test can say which products must be found by an accessory family's signature.

import { spawnSync } from "node:child_process";
import path from "node:path";
import { ROOT } from "../../tools/lib/build_page.mjs";

const READ = `
import json, sys
sys.path.insert(0, sys.argv[1])
import build_mpneumoniae_atlas as M
from lib import proteome_shelves as P
print(json.dumps(sorted(M.FAMILIES[key]["of"] for key in P.ACCESSORY)))
`;

/** The role words of the families that go with a machine and make none by themselves. */
export function accessoryRoles() {
  const run = spawnSync("python3", ["-I", "-c", READ, path.join(ROOT, "tools")], { encoding: "utf8" });
  if (run.status !== 0) throw new Error(run.stderr);
  return new Set(JSON.parse(run.stdout));
}
