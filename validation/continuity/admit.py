"""Admission of one resume across a source change (docs/CHECKPOINT_CONTINUITY_DESIGN.md, §4.2).

propose   runs the continuity probe (probe.py) under the checkpoint's tree S0 and the
          resuming tree S1, and compares the outputs. P, B and H run first, under both trees;
          if any differs, or a tree cannot be decided, the resume is refused (refusal.json) and
          the overlap O is not run. Otherwise O runs under both trees. All four identical: a
          proposed record (proposed.json), with the probe outputs and the comparison as its
          evidence, in the new run's folder.
finalise  admits a proposed record after review: names the admitter, seals record_sha256
          (cells.continuity.seal), verifies it (parse_record) and writes record.json. Case 1 is
          decided by the probe and recorded by the lead; any registered run is the user's.

First landing: case 1 on the vector-windows path, CPU definitions with jit: true. A runtime
change, and case 2's four-process chain, are not proposed here: the runtime rules are parked,
and a D148 record (case 2) is written by the lead (section 3.2).

Each probe is one process per tree: PYTHONPATH=<tree>/src:<tool root>, where a tree is a
source root holding src/cells (a frozen execution snapshot, validation/source_snapshot.py) and
the tool root holds validation/continuity (by default this file's checkout, or a snapshot of
it). The launcher is injectable: ``subprocess`` runs each probe in the foreground (tests, or
admit.py itself inside a detached unit); ``detached`` runs each as its own memory-capped unit
through scripts/run_detached.sh and waits for it.

Usage:
  admit.py propose --checkpoint SNAP --checkpoint-run RUN0 --from-tree S0 --to-tree S1
                   --out NEW_RUN/continuity --window-steps N --recording R
                   [--overlap-rounds N] [--saved-state SNAP ...] [--tool-root ROOT]
                   [--python PY] [--launcher subprocess|detached] [--cpus LIST] [--memory 3G]
  admit.py finalise --proposed NEW_RUN/continuity/proposed.json --admitted-by NAME --role ROLE
Exit status: 0 proposed (or finalised), 2 refused, 3 cannot decide.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from cells import continuity
from cells.core.specs import digest, read_json

ROOT = Path(__file__).resolve().parents[2]
PROBE = "validation.continuity.probe"
PROPOSED_KIND = "cells.checkpoint_continuity_proposal@1"
ENVIRONMENT = ("XLA_FLAGS", "JAX_DISABLE_JIT", "JAX_ENABLE_X64")  # Passed on to the probes.


def sha256(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write_json(path, value):
    with Path(path).open("x") as handle:
        json.dump(value, handle, indent=1, sort_keys=True, allow_nan=False)
        handle.write("\n")


def differences(a, b, path="", limit=40):
    """Paths at which two JSON values differ (at most ``limit``)."""
    found = []

    def walk(x, y, at):
        if len(found) >= limit:
            return
        if isinstance(x, dict) and isinstance(y, dict):
            for key in sorted(set(x) | set(y)):
                if key not in x or key not in y:
                    found.append(f"{at}.{key}: present on one side only")
                else:
                    walk(x[key], y[key], f"{at}.{key}")
        elif isinstance(x, list) and isinstance(y, list):
            if len(x) != len(y):
                found.append(f"{at}: length {len(x)} against {len(y)}")
            for i, (u, v) in enumerate(zip(x, y, strict=False)):  # Lengths reported above.
                walk(u, v, f"{at}[{i}]")
        elif x != y:
            found.append(at)

    walk(a, b, path)
    return found


# ---------------------------------------------------------------- launching the probe


def probe_command(python, checkpoint, out, args, parts):
    command = [
        python,
        "-B",
        "-m",
        PROBE,
        "run",
        "--checkpoint",
        str(checkpoint),
        "--out",
        str(out),
        "--window-steps",
        str(args.window_steps),
        "--recording",
        args.recording,
        "--parts",
        parts,
        "--overlap-rounds",
        str(args.overlap_rounds),
    ]
    for state in args.saved_state:
        command += ["--saved-state", str(state)]
    return command


def probe_environment(tree, tool_root):
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": f"{Path(tree) / 'src'}:{tool_root}",
        "JAX_PLATFORMS": "cpu",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    env.update({k: os.environ[k] for k in ENVIRONMENT if k in os.environ})
    return env


def launch_subprocess(command, env, log, label, args):
    """Foreground: one process, its output in log."""
    with Path(log).open("x") as stream:
        return subprocess.run(
            command, env=env, cwd=Path(log).parent, stdout=stream, stderr=subprocess.STDOUT
        ).returncode


def launch_detached(command, env, log, label, args):
    """One memory-capped unit per probe (scripts/run_detached.sh), waited for here.

    The unit is collected when it exits, so its outcome is the probe's summary.json, which
    the probe writes for every decided status; a crash leaves none.
    """
    unit = f"ccont-{label.lower()}-{int(time.time())}"
    options = [str(ROOT / "scripts" / "run_detached.sh"), unit, args.memory, "--oom-first"]
    if args.cpus:
        options += ["--cpus", args.cpus]
    for key, value in env.items():
        options += ["--env", f"{key}={value}"]
    options += ["--dir", str(Path(log).parent), "--", "/bin/bash", "-c", 'exec "$@" > "$0" 2>&1']
    subprocess.run([*options, str(log), *command], check=True)
    while (
        subprocess.run(["systemctl", "--user", "is-active", "-q", f"cells-{unit}"]).returncode == 0
    ):
        time.sleep(10)
    return 0


LAUNCHERS = {"subprocess": launch_subprocess, "detached": launch_detached}


def run_probe(args, tree, out, parts, label, launcher):
    """One probe process under one tree; returns its summary (or raises for a crash)."""
    log = Path(str(out) + ".log")
    command = probe_command(args.python, args.checkpoint, out, args, parts)
    env = probe_environment(tree, args.tool_root)
    started = time.perf_counter()
    code = launcher(command, env, log, label, args)
    path = Path(out) / "summary.json"
    if code not in (0, 3, 4) or not path.exists():  # A crash: no decided status.
        raise RuntimeError(f"probe {label} failed (exit {code}); see {log}")
    summary = json.loads(path.read_text())
    summary["_wall_seconds"] = time.perf_counter() - started
    return summary


# ---------------------------------------------------------------- comparison


def compare_texts(a, b):
    """Every saved text, byte for byte."""
    names = sorted({p.name for d in (a, b) for p in (Path(d) / "texts").glob("*.txt")})
    rows = {}
    for name in names:
        x, y = Path(a) / "texts" / name, Path(b) / "texts" / name
        rows[name] = x.exists() and y.exists() and x.read_bytes() == y.read_bytes()
    return rows


def compare_probes(s0, s1, dir0, dir1):
    """P, B and H of two probe summaries: {part: {"identical", "differences"}}."""
    report = {}
    for part, keys in (
        ("P0", ("arguments", "program", "compile_arguments")),
        ("P", None),
        ("B", ("plan", "resident", "definitions", "rounds", "rounds_sha256", "minimum_overlap")),
        ("H", ("rows", "saved_states")),
    ):
        a, b = s0.get(part), s1.get(part)
        if keys is not None and a is not None and b is not None:
            a, b = {k: a.get(k) for k in keys}, {k: b.get(k) for k in keys}
        found = differences(a, b, part)
        report[part] = dict(identical=not found and a is not None, differences=found)
    texts = compare_texts(dir0, dir1)
    report["texts"] = dict(
        identical=bool(texts) and all(texts.values()),
        differences=[n for n, same in texts.items() if not same],
    )
    rounds = [Path(d) / "rounds.jsonl" for d in (dir0, dir1)]
    lines = [p.read_text().splitlines() if p.exists() else [] for p in rounds]
    first = next(
        (i for i, (x, y) in enumerate(zip(*lines, strict=False)) if x != y),
        None if len(lines[0]) == len(lines[1]) else min(map(len, lines)),
    )
    report["B"]["first_differing_round"] = first
    for label, summary in (("S0", s0), ("S1", s1)):
        own = (summary.get("B") or {}).get("first_round_equals_P0")
        report[f"first_round_equals_P0_{label}"] = dict(identical=own is True, differences=[])
    return report


def host_replay_errors(summary):
    """H rows whose host code raised: such a replay compares nothing, so it cannot decide."""
    return [
        f"{row['state']}, world {row['world']}, step {row['step_index']}: {key} raised"
        for row in (summary.get("H") or {}).get("rows", [])
        for key, value in row.items()
        if isinstance(value, dict) and set(value) == {"raised"}
    ]


def compare_overlaps(o0, o1):
    a, b = o0.get("O") or {}, o1.get("O") or {}
    report = {
        "calls": differences(a.get("calls"), b.get("calls"), "O.calls"),
        "outputs": differences(a.get("outputs"), b.get("outputs"), "O.outputs"),
    }
    checks = dict(
        arguments_identical=not report["calls"] and bool(a.get("calls")),
        outputs_bitwise_equal=not report["outputs"] and bool(a.get("outputs")),
        completed=a.get("failure") is None
        and b.get("failure") is None
        and a.get("completed") == a.get("rounds") == b.get("completed") == b.get("rounds"),
        arguments_equal_own_rounds_S0=a.get("arguments_equal_own_rounds") is True,
        arguments_equal_own_rounds_S1=b.get("arguments_equal_own_rounds") is True,
    )
    differing = [
        k
        for k in range(min(len(a.get("outputs") or ()), len(b.get("outputs") or ())))
        if a["outputs"][k] != b["outputs"][k]
    ]
    return dict(
        checks=checks,
        differences=report,
        failures=[a.get("failure"), b.get("failure")],
        rounds=a.get("rounds"),
        first_differing_output_round=differing[0] if differing else None,
    )


# ---------------------------------------------------------------- the record


def tree_identity(tree):
    """The git revision and dirty diff of a frozen execution snapshot, if it is one."""
    marker = Path(tree) / "SNAPSHOT.json"
    if not marker.is_file():
        return None, None
    value = json.loads(marker.read_text())
    return value.get("git_revision"), str(Path(tree) / "checkout.patch")


def lineage_of(run):
    """The records that admitted earlier resumes of the run that wrote the checkpoint.

    Checked, not trusted (section 5): the run's provenance names its record, whose digest
    must match, and the new lineage repeats that record's own lineage before it.
    """
    path = Path(run) / "manifest.json"
    if not path.is_file():
        raise SystemExit(f"The checkpoint's run {run} has no manifest.json to take provenance from")
    provenance = read_json(path).get("provenance") or {}
    if provenance.get("operation") != "admitted_resume":
        return []
    path = Path(provenance["continuity_record"])
    record = continuity.parse_record(read_json(path))
    if record["record_sha256"] != provenance["record_sha256"]:
        raise ValueError(f"The run {run} names a record that differs from {path}")
    return [*record["lineage"], {"record": str(path), "record_sha256": record["record_sha256"]}]


def propose(args, launcher=None):
    """The probe under S0 and S1, compared; a proposed record or a refusal.

    launcher(command, env, log, label, args) -> exit status runs one probe process; by
    default the one --launcher names (tests inject their own).
    """
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    args.checkpoint = Path(args.checkpoint).resolve()
    args.tool_root = Path(args.tool_root).resolve()
    launcher = launcher or LAUNCHERS[args.launcher]
    manifest = read_json(args.checkpoint / "manifest.json")
    lineage = lineage_of(args.checkpoint_run)  # Before any probe runs.
    trees = {"S0": Path(args.from_tree).resolve(), "S1": Path(args.to_tree).resolve()}
    log = dict(
        kind="cells.checkpoint_continuity_admission_log@1",
        argv=sys.argv,
        checkpoint=str(args.checkpoint),
        trees={k: str(v) for k, v in trees.items()},
        tool_root=str(args.tool_root),
        started_utc=datetime.now(timezone.utc).isoformat(),
    )
    summaries = {
        label: run_probe(
            args, trees[label], out / f"probe-{label.lower()}", "P,B,H", label, launcher
        )
        for label in ("S0", "S1")
    }

    def refuse(code, reason, comparison=None):
        write_json(
            out / "refusal.json",
            {
                **log,
                "verdict": "cannot_decide" if code == 3 else "refused",
                "reason": reason,
                "comparison": comparison,
                "statuses": {k: v.get("status") for k, v in summaries.items()},
                "finished_utc": datetime.now(timezone.utc).isoformat(),
            },
        )
        print("refused:", reason, flush=True)
        return code

    for label, summary in summaries.items():
        if summary["status"] != "probed":
            code = 3 if summary["status"] == "cannot_decide" else 2
            return refuse(code, f"{label} {summary['status']}: {summary.get('reason')}")
    s0, s1 = summaries["S0"], summaries["S1"]
    if s0["checkpoint"]["manifest_sha256"] != manifest["manifest_sha256"]:
        return refuse(2, "the probes read another checkpoint manifest")
    if not s0["reproduces_manifest"]:
        changed = continuity.changed_files(manifest["source_hashes"], s0["source_hashes"])
        return refuse(2, f"S0 does not reproduce the manifest's source_hashes: {changed}")
    if not s0["checkpoint"]["children_share_cohort_identity"]:
        return refuse(2, "the cohort's children do not share its identity")
    raised = [
        f"{label}: {e}" for label in ("S0", "S1") for e in host_replay_errors(summaries[label])
    ]
    if raised:  # H would pass vacuously on a replay that raises identically under both.
        return refuse(3, f"the host replay raised, so H compares nothing: {raised[:6]}")
    comparison = compare_probes(s0, s1, out / "probe-s0", out / "probe-s1")
    differing = [part for part, row in comparison.items() if not row["identical"]]
    if differing:
        return refuse(2, f"the probe parts differ: {differing}", comparison)
    runtime = s1["runtime"]
    moved = set(continuity.differing_runtime_fields(manifest["runtime"], runtime)) - {
        "cells_version"
    }
    if moved:
        return refuse(2, f"runtime changes are parked in the first landing: {sorted(moved)}")
    host = [
        f
        for f in continuity.HOST_FIELDS
        if continuity.flatten(s0["runtime"]).get(f) != continuity.flatten(runtime).get(f)
    ]
    if host:
        return refuse(2, f"the two probes ran under different host-side runtimes: {host}")
    overlaps = {
        label: run_probe(
            args, trees[label], out / f"overlap-{label.lower()}", "O", f"{label}o", launcher
        )
        for label in ("S0", "S1")
    }
    for label, summary in overlaps.items():
        if summary["status"] != "probed":
            return refuse(2, f"{label} overlap {summary['status']}: {summary.get('reason')}")
    comparison["O"] = compare_overlaps(overlaps["S0"], overlaps["S1"])
    failed = [k for k, ok in comparison["O"]["checks"].items() if not ok]
    comparison["O"]["identical"] = not failed
    write_json(out / "compare.json", {**log, "comparison": comparison})
    if failed:
        return refuse(2, f"the overlap differs: {failed}", comparison)
    rounds, overlap_rounds = s1["horizon_rounds"], comparison["O"]["rounds"]
    evidence = [
        dict(role=role, path=str(path), sha256=sha256(path))
        for role, path in (
            ("probe S0", out / "probe-s0" / "summary.json"),
            ("probe S1", out / "probe-s1" / "summary.json"),
            ("overlap S0", out / "overlap-s0" / "summary.json"),
            ("overlap S1", out / "overlap-s1" / "summary.json"),
            ("comparison", out / "compare.json"),
        )
    ]
    residual = [
        f"host checks and observers were compared on {s1['H']['saved_states']} saved state(s); "
        "host code paths that no saved state reaches are S1's (section 3.1)"
    ]
    if overlap_rounds < rounds:
        residual.append(
            f"a driving-loop change that first acts after the overlap's {overlap_rounds} rounds "
            f"(of {rounds} remaining) is S1's (section 3.1)"
        )
    else:
        residual.append(
            f"the overlap covers the whole remaining horizon ({rounds} rounds): the resume is "
            "decided on CPU"
        )
    revisions = {label: tree_identity(trees[label]) for label in trees}
    proposed = {
        "kind": continuity.RECORD_KIND,
        "checkpoint": {
            "format": manifest["kind"],
            "path": str(args.checkpoint),
            "manifest_sha256": manifest["manifest_sha256"],
            "definitions": s0["checkpoint"]["definitions"],
            "clocks": s0["checkpoint"]["clocks"],
        },
        "from": {
            "source_hashes_sha256": digest(manifest["source_hashes"]),
            "tree": str(trees["S0"]),
            "git_revision": revisions["S0"][0],
            "dirty_diff": revisions["S0"][1],
            "tree_reproduces_manifest": True,
            "runtime": manifest["runtime"],
        },
        "to": {
            "source_hashes_sha256": s1["source_hashes_sha256"],
            "tree": str(trees["S1"]),
            "git_revision": revisions["S1"][0],
            "dirty_diff": revisions["S1"][1],
            "runtime": runtime,
        },
        "changed_files": continuity.changed_files(manifest["source_hashes"], s1["source_hashes"]),
        "probe": {"runtime": runtime, "host_fields_equal_to_runtime": True},
        "source_admission": {"case": "identical_programs"},
        "runtime_admission": {"case": "none", "fields": []},
        "scope": {
            "paths": [continuity.DECIDED_PATHS[0]],
            "policy": {"window_steps": args.window_steps, "recording": args.recording},
            "horizon_rounds": rounds,
            "overlap_rounds": overlap_rounds,
        },
        "lineage": lineage,
        "evidence": evidence,
        "residual": residual,
    }
    write_json(out / "proposed.json", {**proposed, "proposal": {**log, "kind": PROPOSED_KIND}})
    print("proposed:", out / "proposed.json", flush=True)
    return 0


def finalise(args):
    proposed = read_json(args.proposed)
    proposed.pop("proposal", None)
    for item in proposed["evidence"]:
        if sha256(item["path"]) != item["sha256"]:
            raise ValueError(f"Evidence changed since the proposal: {item['path']}")
    record = continuity.seal(
        {
            **proposed,
            "admitted_by": {"name": args.admitted_by, "role": args.role},
            "admitted_utc": datetime.now(timezone.utc).isoformat(),
        }
    )
    continuity.parse_record(record)
    path = Path(args.proposed).parent / "record.json"
    write_json(path, record)
    print("admitted:", path, record["record_sha256"], flush=True)
    return 0


def arguments(argv=None):
    """The command line of propose and finalise, parsed."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("propose", help="probe under both trees and propose a record")
    p.add_argument("--checkpoint", required=True, help="the cohort snapshot to resume")
    p.add_argument("--checkpoint-run", required=True, help="the run folder that wrote it")
    p.add_argument("--from-tree", required=True, help="S0: a source root holding src/cells")
    p.add_argument("--to-tree", required=True, help="S1: the resuming source root")
    p.add_argument("--out", required=True, help="a new folder in the new run's folder")
    p.add_argument("--window-steps", type=int, required=True)
    p.add_argument("--recording", required=True, choices=("full", "observations", "checkpoints"))
    p.add_argument("--overlap-rounds", type=int, default=0, help="at least the minimum")
    p.add_argument("--saved-state", action="append", default=[], help="more saved states for H")
    p.add_argument("--tool-root", default=str(ROOT), help="holds validation/continuity")
    p.add_argument("--python", default=sys.executable)
    p.add_argument("--launcher", choices=sorted(LAUNCHERS), default="subprocess")
    p.add_argument("--cpus", default=None, help="detached units: their CPU affinity")
    p.add_argument("--memory", default="3G", help="detached units: their memory cap")
    f = sub.add_parser("finalise", help="admit a reviewed proposal")
    f.add_argument("--proposed", required=True)
    f.add_argument("--admitted-by", required=True)
    f.add_argument("--role", required=True)
    return parser.parse_args(argv)


def main(argv=None):
    args = arguments(argv)
    return propose(args) if args.command == "propose" else finalise(args)


if __name__ == "__main__":
    sys.exit(main())
