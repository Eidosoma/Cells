"""Two caches' independent compiles of the same programs, compared program by program.

The cache qualification's offline step (cache_qualify.sh; the testing plan's section 10.6). It
gives information, not a pass criterion. JAX's own byte check (jax_compilation_cache_check_contents)
cannot pass on XLA:CPU, as the rehearsal of 19 November 2026 found:
- a serialized executable holds its kernels in an order that varies between processes;
- it embeds paths (the cache folder's, and the compiling tree's in its metadata);
- a few programs compile to different machine code depending on the compiling process's history or
  tree (three threefry kernels there), with bitwise-identical results.
If a result ever differs under the cache, the programs listed here as different machine code are the
first place to look.

Per program present in both caches, after the second cache's own path and each SAME pair of
equal-purpose paths (A=B: B is written as A) are made equal in the second one's bytes:
  equal bytes;
  same objects, another order: the same embedded ELF objects (hashed, as a multiset) and the same
      other bytes (as a multiset);
  same objects, other bytes: the same ELF objects, with other bytes elsewhere (metadata);
  different machine code: the ELF objects differ.
Usage (the venv's interpreter, which reads JAX's cache format):
  cache_compare.py ONE TWO OUT [--same A=B ...]
"""

import argparse
import collections
import hashlib
import json
from pathlib import Path

KINDS = ("equal bytes", "same objects, another order", "same objects, other bytes",
         "different machine code")


def executable(path):
    """A cache entry's serialized executable, JAX's compile-time prefix removed."""
    from jax._src import compilation_cache as cc
    return cc.extract_executable_and_time(cc.decompress_executable(Path(path).read_bytes()))[0]


def objects(data):
    """(sorted hashes of the embedded ELF objects, the bytes left once they are cut out).

    Each object is a length-delimited protobuf field: its length is the varint just before the
    object's ELF magic."""
    hashes, rest, last, i = [], bytearray(), 0, data.find(b"\x7fELF")
    while i >= 0:
        k = i - 1
        while k > 0 and data[k - 1] & 0x80:
            k -= 1
        n = sum((b & 0x7F) << (7 * j) for j, b in enumerate(data[k:i]))
        hashes.append(hashlib.sha256(data[i:i + n]).hexdigest())
        rest += data[last:i]
        last = i + n
        i = data.find(b"\x7fELF", last)
    rest += data[last:]
    return sorted(hashes), bytes(rest)


def classify(a, b):
    if a == b:
        return "equal bytes"
    (ha, ra), (hb, rb) = objects(a), objects(b)
    if ha != hb:
        return "different machine code"
    if collections.Counter(ra) == collections.Counter(rb):
        return "same objects, another order"
    return "same objects, other bytes"


def compare(one, two, same=(), read=executable):
    one, two = Path(one), Path(two)
    a_names = {p.name for p in one.glob("*-cache")}
    b_names = {p.name for p in two.glob("*-cache")}
    kinds = collections.Counter({k: 0 for k in KINDS})
    listed = {"different machine code": [], "same objects, other bytes": []}
    for name in sorted(a_names & b_names):
        a = read(one / name)
        b = read(two / name).replace(str(two).encode(), str(one).encode())
        for x, y in same:
            b = b.replace(y.encode(), x.encode())
        kind = classify(a, b)
        kinds[kind] += 1
        if kind in listed:
            listed[kind].append(name)
    return {"one": str(one), "two": str(two), "same": [f"{x}={y}" for x, y in same],
            "common_programs": len(a_names & b_names), "only_in_one": len(a_names - b_names),
            "only_in_two": len(b_names - a_names), "kinds": dict(kinds), **listed}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("one")
    p.add_argument("two")
    p.add_argument("out")
    p.add_argument("--same", nargs="*", default=[], help="A=B: write path B as A in TWO's bytes")
    a = p.parse_args(argv)
    doc = compare(a.one, a.two, [tuple(s.split("=", 1)) for s in a.same])
    Path(a.out).write_text(json.dumps(doc, indent=1) + "\n")
    print(json.dumps({k: doc[k] for k in ("common_programs", "kinds")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
