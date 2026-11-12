"""Check that two run trees differ only by an explicit identifier rename.

Usage:
  python scripts/compare_renamed_runs.py BEFORE AFTER --map OLD=NEW [--map OLD=NEW ...]
      [--changed-source PATH ...] [--out REPORT.json]

BEFORE and AFTER are directories of run outputs (fresh, resumed, branched, windowed
and batch runs), written by the same commands from two source trees. The check is:

- the two trees hold the same relative files;
- every array of every .npz file has the same dtype, shape and bytes;
- every JSON document (also JSON Lines and CLI stdout) of BEFORE, after the OLD->NEW
  substring substitutions of all keys and strings, equals the AFTER document, except
  for wall-clock fields (VOLATILE) and for digests of renamed text or of the engine
  source (DERIVED), which are checked separately: digests of array files must still
  agree, and engine source hashes may differ only for the --changed-source files.

Substitutions apply in the given order, so list longer names first. No reference
digests are embedded; everything is compared between the two trees.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

VOLATILE = {"created_utc", "timings", "utc"}
# Digests of JSON text that contains the renamed strings, or of engine source.
# A cohort's snapshot_sha256 is the world snapshot's manifest_sha256; state and
# chunk digests (state_sha256, sha256) are compared like any other field.
DERIVED = {
    "definition_sha256",
    "spec_sha256",
    "manifest_sha256",
    "snapshot_sha256",
    "parent_definition_sha256",
    "parent_snapshot_sha256",
    "parent_batch_snapshot_sha256",
    "batch_definition_sha256",
    "batch_sha256",
    "fingerprint",
    "files_sha256",
    "source_hashes",
}


def substitute(value, mapping):
    if isinstance(value, str):
        for old, new in mapping:
            value = value.replace(old, new)
        return value
    if isinstance(value, list):
        return [substitute(v, mapping) for v in value]
    if isinstance(value, dict):
        return {substitute(k, mapping): substitute(v, mapping) for k, v in value.items()}
    return value


def compare(before, after, path, differences, derived):
    if isinstance(before, dict) and isinstance(after, dict):
        if before.keys() != after.keys():
            differences.append({"path": path, "keys": sorted(before.keys() ^ after.keys())})
            return
        for key in before:
            if key in VOLATILE:
                continue
            if key in DERIVED:
                derived.append((f"{path}/{key}", key, before[key], after[key]))
                continue
            compare(before[key], after[key], f"{path}/{key}", differences, derived)
    elif isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after):
            differences.append({"path": path, "lengths": [len(before), len(after)]})
            return
        for index, (a, b) in enumerate(zip(before, after, strict=True)):
            compare(a, b, f"{path}[{index}]", differences, derived)
    elif type(before) is not type(after) or before != after:
        differences.append({"path": path, "before": before, "after": after})


def load_json_document(path):
    text = path.read_text()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        lines = [line for line in text.splitlines() if line.strip()]
        try:
            return [json.loads(line) for line in lines]
        except json.JSONDecodeError:
            return None


def npz_arrays(path):
    with np.load(path, allow_pickle=False) as archive:
        return {name: archive[name] for name in archive.files}


def compare_npz(before, after):
    a, b = npz_arrays(before), npz_arrays(after)
    problems = []
    if a.keys() != b.keys():
        problems.append({"arrays": sorted(a.keys() ^ b.keys())})
    for name in sorted(a.keys() & b.keys()):
        x, y = a[name], b[name]
        if x.dtype != y.dtype or x.shape != y.shape or x.tobytes() != y.tobytes():
            problems.append({"array": name, "dtype": [str(x.dtype), str(y.dtype)]})
    return {
        "arrays": len(a),
        "elements": int(sum(v.size for v in a.values())),
        "file_bytes_identical": before.read_bytes() == after.read_bytes(),
        "problems": problems,
    }


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_derived(rows, before_root, after_root, relative, changed_source):
    """Digests of array files must agree; source hashes only for the named files."""
    problems, changed = [], []
    for path, key, a, b in rows:
        if key == "files_sha256":
            if a.keys() != b.keys():
                problems.append({"path": path, "keys": sorted(a.keys() ^ b.keys())})
                continue
            base = (before_root / relative).parent
            for name in a:
                if name.endswith(".npz") and a[name] != b[name]:
                    problems.append({"path": f"{path}/{name}"})
                if name.endswith(".npz") and a[name] != sha(base / name):
                    problems.append({"path": f"{path}/{name}", "recorded_vs_file": True})
        elif key == "source_hashes":
            if a.keys() != b.keys():
                problems.append({"path": path, "keys": sorted(a.keys() ^ b.keys())})
                continue
            differing = sorted(n for n in a if a[n] != b[n])
            changed.append(differing)
            if not set(differing) <= set(changed_source):
                problems.append(
                    {"path": path, "unexpected": sorted(set(differing) - set(changed_source))}
                )
        elif a == b:
            continue
    return problems, changed


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--map", action="append", default=[], metavar="OLD=NEW")
    parser.add_argument("--changed-source", action="append", default=[], metavar="PATH")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    mapping = [tuple(item.split("=", 1)) for item in args.map]
    if any(len(pair) != 2 or not pair[0] for pair in mapping):
        parser.error("--map needs OLD=NEW")
    files = {
        side: sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
        for side, root in (("before", args.before), ("after", args.after))
    }
    report = {
        "kind": "cells.renamed_run_comparison@1",
        "before": str(args.before.resolve()),
        "after": str(args.after.resolve()),
        "mapping": [list(pair) for pair in mapping],
        "changed_source": sorted(args.changed_source),
        "only_before": sorted(set(files["before"]) - set(files["after"])),
        "only_after": sorted(set(files["after"]) - set(files["before"])),
        "files": {},
    }
    totals = {"npz": 0, "arrays": 0, "elements": 0, "npz_bytes_identical": 0, "json": 0, "text": 0}
    occurrences = {old: 0 for old, _ in mapping}
    failures = bool(report["only_before"] or report["only_after"])
    for relative in sorted(set(files["before"]) & set(files["after"])):
        a, b = args.before / relative, args.after / relative
        if relative.endswith(".npz"):
            row = compare_npz(a, b)
            totals["npz"] += 1
            totals["arrays"] += row["arrays"]
            totals["elements"] += row["elements"]
            totals["npz_bytes_identical"] += row["file_bytes_identical"]
            ok = not row["problems"]
        else:
            first, second = load_json_document(a), load_json_document(b)
            if first is None or second is None:
                text = substitute(a.read_text(), mapping)
                ok = text == b.read_text()
                row = {"text": True}
                totals["text"] += 1
            else:
                mapped = substitute(first, mapping)
                for old in occurrences:
                    occurrences[old] += a.read_text().count(old)
                differences, derived = [], []
                compare(mapped, second, "", differences, derived)
                problems, changed = check_derived(
                    derived, args.before, args.after, relative, args.changed_source
                )
                row = {
                    "differences": differences,
                    "derived_checked": sorted({key for _, key, _, _ in derived}),
                    "derived_problems": problems,
                    "source_hashes_differing": changed,
                }
                ok = not differences and not problems
                totals["json"] += 1
        row["ok"] = ok
        failures |= not ok
        report["files"][relative] = row
    report["totals"] = totals
    report["old_string_occurrences_in_before_json"] = occurrences
    report["status"] = "fail" if failures else "pass"
    text = json.dumps(report, indent=1, sort_keys=True, default=str) + "\n"
    if args.out:
        args.out.write_text(text)
    print(json.dumps({"status": report["status"], **report["totals"]}))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
