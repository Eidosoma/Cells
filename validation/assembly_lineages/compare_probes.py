"""Compare a regenerated probe set with a frozen one, file by file: the invariance gate's comparison
for cells.model.assembly_lineages@1 (against probes-c6dd5956) and @2 (OL1's, against probes-48c8d2a9,
renewed from probes-3e39bcc5 by D281), moved into the checkout with OL2's invariance gate
(docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md §0.2c rule 16; scripts/assembly_lineages_invariance.sh). It
was frozen at
/mnt/workspaces/Cells/ol1-laws-20261117/tools/compare_probes.py; the one change is the exemption of
roles.json's checksums of JSON files (below).

Every array of every .npz must be bitwise equal (name, dtype, shape, values; NaN equal to NaN).
Every .json is compared leaf by leaf, a string that names a path inside its set compared relative
to the set's root (the sets live in different folders); each differing key path is listed. A path
is exempt only if
it is in EXEMPT (provenance: where and when the engine ran, never what it computed) or, with
--exempt-json FILE, in that file's list. Any other difference, any array difference and any file
present on one side only fail the comparison. The list of every JSON difference is written
whatever the verdict, so the exemptions are read off the first diff, not assumed.

Usage: python -I compare_probes.py FINAL_PROBES NEW_PROBES OUT_JSON [--exempt-json FILE]
"""

import json
import re
import sys
from pathlib import Path

import numpy as np

# Provenance only: the engine's revision and snapshot, the runtime and machine, and timings; the
# checksums of files that hold them; and the lead's annotations added to roles.json after the run.
EXEMPT = (
    r"(^|\.)source(\.|$)",
    r"(^|\.)source_hashes(\.|$)",
    r"(^|\.)runtime(\.|$)",
    r"(^|\.)created_utc$",
    r"(^|\.)timings(\.|$)",
    r"(^|\.)cpu_affinity(\.|\[|$)",
    r"(^|\.)device$",
    r"(^|\.)blas(\.|$)",
    r"^files_sha256\.",
    r"^(status|standing|final_at|annotations)(\.|$)",
    r"^cells$",  # roles.json: the path of the engine package the run imported (its snapshot).
    # OL1's roles.json names its checksums `files` (@1's names them files_sha256): a JSON file's
    # checksum changes with the provenance it holds, and the file itself is compared leaf by leaf
    # here, so only a JSON file's is exempt. An array file's checksum stays compared.
    r"^files\..*\.json$",
)


def relocated(value, root):
    """Every string leaf with the set's own root replaced by <set>."""
    if isinstance(value, dict):
        return {k: relocated(v, root) for k, v in value.items()}
    if isinstance(value, list):
        return [relocated(v, root) for v in value]
    if isinstance(value, str):
        return value.replace(str(root), "<set>")
    return value


def leaves(value, prefix=""):
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            out.update(leaves(v, f"{prefix}.{k}" if prefix else str(k)))
        if not value:
            out[prefix] = {}
        return out
    if isinstance(value, list):
        out = {}
        for i, v in enumerate(value):
            out.update(leaves(v, f"{prefix}[{i}]"))
        if not value:
            out[prefix] = []
        return out
    return {prefix: value}


def compare_json(a, b):
    la, lb = leaves(a), leaves(b)
    return sorted(k for k in set(la) | set(lb) if la.get(k, KeyError) != lb.get(k, KeyError))


def compare_npz(a, b):
    out = []
    with np.load(a, allow_pickle=False) as x, np.load(b, allow_pickle=False) as y:
        if set(x.files) != set(y.files):
            out.append(f"array names differ: {sorted(set(x.files) ^ set(y.files))}")
        for name in sorted(set(x.files) & set(y.files)):
            u, v = x[name], y[name]
            same = u.dtype == v.dtype and u.shape == v.shape
            same = same and np.array_equal(u, v, equal_nan=u.dtype.kind in "fc")
            if not same:
                out.append(name)
    return out


def main(final, new, out, exempt_file=None):
    final, new, out = Path(final), Path(new), Path(out)
    patterns = [re.compile(p) for p in EXEMPT]
    if exempt_file:
        patterns += [
            re.compile(re.escape(p) + "$") for p in json.loads(Path(exempt_file).read_text())
        ]
    files_a = {p.relative_to(final) for p in final.rglob("*") if p.is_file()}
    files_b = {p.relative_to(new) for p in new.rglob("*") if p.is_file()}
    report = {"only_final": sorted(map(str, files_a - files_b)),
              "only_new": sorted(map(str, files_b - files_a)),
              "arrays": {}, "json": {}, "other": {}}  # fmt: skip
    for rel in sorted(files_a & files_b):
        a, b = final / rel, new / rel
        if rel.suffix == ".npz":
            found = compare_npz(a, b)
            if found:
                report["arrays"][str(rel)] = found
        elif rel.suffix == ".json":
            found = compare_json(
                relocated(json.loads(a.read_text()), final),
                relocated(json.loads(b.read_text()), new),
            )
            if found:
                report["json"][str(rel)] = found
        elif a.read_bytes() != b.read_bytes():
            report["other"][str(rel)] = "bytes differ"
    unexempt = {
        f: [k for k in keys if not any(p.search(k) for p in patterns)]
        for f, keys in report["json"].items()
    }
    unexempt = {f: k for f, k in unexempt.items() if k}
    report["json_not_exempt"] = unexempt
    exempted = sorted(
        {
            re.sub(r"\[\d+\]", "[i]", k)
            for keys in report["json"].values()
            for k in keys
            if any(p.search(k) for p in patterns)
        }
    )
    report["exempted_paths"] = exempted
    report["exempt_patterns"] = [p.pattern for p in patterns]
    passed = not (report["only_final"] or report["only_new"] or report["arrays"] or unexempt
                  or report["other"])  # fmt: skip
    report["verdict"] = "identical but for provenance" if passed else "DIFFERS"
    report["counts"] = {
        "files": len(files_a & files_b),
        "json_files_with_differences": len(report["json"]),
        "array_files_differing": len(report["arrays"]),
    }
    out.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"verdict": report["verdict"], **report["counts"]}))
    return 0 if passed else 1


if __name__ == "__main__":
    args = sys.argv[1:]
    exempt = None
    if "--exempt-json" in args:
        i = args.index("--exempt-json")
        exempt = args[i + 1]
        del args[i : i + 2]
    sys.exit(main(*args, exempt_file=exempt))
