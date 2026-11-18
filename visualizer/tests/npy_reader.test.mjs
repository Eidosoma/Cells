// tools/lib/npy_reader.py on fixed-width Unicode text ('<U<n>'), which the engine's relationship
// tables (cells.relations@1, relations.npz) use for their string ids: such a column reads as str,
// and text in any other byte order is refused with a plain error, never misread. The .npy files
// are built by hand in NumPy's format 1.0, since the reader's own Python has no numpy.
//
//   node --test tests/npy_reader.test.mjs

import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const LIB = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "tools", "lib");

// argv: the library folder, the element type, the shape and the elements (JSON), the encoding the
// elements are written in, and how many bytes to cut from the file's end. Prints the Array read,
// or the reader's ValueError.
const READ = String.raw`
import json, struct, sys
sys.path.insert(0, sys.argv[1])
from npy_reader import read_npy
descr, shape, items = sys.argv[2], tuple(json.loads(sys.argv[3])), json.loads(sys.argv[4])
codec, cut = sys.argv[5], int(sys.argv[6])
width = int(descr[2:])
header = "{'descr': %r, 'fortran_order': False, 'shape': %r, }" % (descr, shape)
header += " " * (63 - (10 + len(header)) % 64) + "\n"
body = b"".join(s.encode(codec) + b"\0" * 4 * (width - len(s)) for s in items)
raw = b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header.encode("latin1") + body
raw = raw[: len(raw) - cut]
try:
    a = read_npy(raw, "ids")
except ValueError as error:
    print(json.dumps({"error": str(error)}))
else:
    print(json.dumps({"descr": a.descr, "shape": list(a.shape), "values": list(a.values), "text": a.text, "boolean": a.boolean}))
`;

/** JSON with every non-ASCII code unit escaped, so the elements reach Python as written. */
const ascii = (value) => JSON.stringify(value).replace(/[\u0080-\uffff]/g, (c) => `\\u${c.charCodeAt(0).toString(16).padStart(4, "0")}`);

function read(descr, shape, items, { codec = "utf-32-le", cut = 0 } = {}) {
  const done = spawnSync("python3", ["-c", READ, LIB, descr, ascii(shape), ascii(items), codec, String(cut)], { encoding: "utf8" });
  assert.equal(done.status, 0, `python3 failed:\n${done.stderr}`);
  return JSON.parse(done.stdout);
}

test("'<U' text reads as str in C order, its NUL padding dropped", () => {
  // Ids as the relationship tables write them, an empty one, and text beyond ASCII and beyond
  // the Basic Multilingual Plane (one code point, four bytes, in UTF-32).
  const items = ["carrier:a0", "", "slot:0", "αβγ", "x\u{1D538}", "sink:discard"];
  const got = read("<U12", [2, 3], items);
  assert.deepEqual(got, { descr: "<U12", shape: [2, 3], values: items, text: true, boolean: false });
  assert.deepEqual(read("<U1", [0], []).values, []);
});

test("text in any other byte order is refused, never misread", () => {
  for (const [descr, codec] of [[">U4", "utf-32-be"], ["|U4", "utf-32-le"], ["=U4", "utf-32-le"]]) {
    const got = read(descr, [2], ["ab", "cd"], { codec });
    assert.equal(got.values, undefined, `${descr} was read`);
    assert.ok(got.error.startsWith(`ids: element type ${descr} is not supported`), got.error);
  }
});

test("a text file shorter than its shape says is refused", () => {
  const got = read("<U4", [2], ["ab", "cd"], { cut: 1 });
  assert.ok(got.error.startsWith("ids: the file is shorter than its shape"), got.error);
});
