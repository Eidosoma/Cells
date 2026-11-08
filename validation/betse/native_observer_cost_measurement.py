"""Paired stdlib metadata timing under exact before/current observer code.

No production module, owner, numerical body or native package is imported.
The immutable software controls establish correctness separately; these local
timings are not a SEED, INIT, SIM or GPU performance qualification.
"""

import argparse
import ast
import hashlib
import json
import os
import resource
import statistics
import struct
import sys
import time
from pathlib import Path

from validation import source_snapshot as snapshot
from validation.betse import betse_mesh_lifecycle_preparation_guard as guard
from validation.betse import betse_native_seed_metadata_software as software
from validation.betse import betse_normal_channel_join_runtime as runtime

ROOT = Path(__file__).resolve().parents[2]
FILE = "validation/betse/native_observer_cost_measurement.py"
TREE = "src/cells/processes/betse_native_parameter_record_digest.py"
FILES = (*software.OBSERVER_FILES, FILE, TREE)


def child(output):
    inputs = json.loads((output / "inputs.json").read_text())
    snapshot.verify(ROOT, manifest_sha256=inputs["manifest_sha256"])
    before = Path(inputs["before_source"])
    for name, expected in inputs["before_pins"].items():
        if snapshot.digest(before / name) != expected:
            raise ValueError("Before-source metadata bytes changed")
    from tests.unit import test_betse_native_observer_code_filter as controls

    node = next(
        node
        for node in ast.parse((ROOT / TREE).read_text()).body
        if isinstance(node, ast.FunctionDef) and node.name == "_metadata_tree"
    )
    space = dict(
        __name__="observer_measurement_metadata",
        _EXIT=object(),
        _FALLBACK=object(),
        _PACK=struct.pack,
    )
    exec(compile(ast.Module(body=[node], type_ignores=[]), "observer_metadata_tree", "exec"), space)
    walk = space["_metadata_tree"]
    corpora = {
        "nested": {
            f"row{i}": [(i, j, -0.0, {"name": str(j)}) for j in range(16)] for i in range(32)
        },
        "wide": [{"id": i, "labels": ("cell", "membrane", "environment")} for i in range(1024)],
    }
    prior_profile, prior_trace = sys.getprofile(), sys.gettrace()
    attempted, counts, rows = [], {}, []
    blocker = software._BlockImports(attempted)

    def profile(frame, event, arg):
        if event == "call" and (
            frame.f_globals.get("__name__", "").split(".")[0] in software.BLOCKED_IMPORTS
            or frame.f_code.co_filename.startswith(software.NATIVE_ROOT)
        ):
            attempted.append(frame.f_code.co_qualname)
            raise AssertionError("Actual production/native/numerical entry forbidden")
        if prior_profile is not None:
            prior_profile(frame, event, arg)
        if frame.f_code is walk.__code__:
            counts[event] = counts.get(event, 0) + 1

    def trace(frame, event, arg):
        if frame.f_code is walk.__code__:
            counts["trace_" + event] = counts.get("trace_" + event, 0) + 1
            return trace
        return None

    if prior_trace is not None:
        raise ValueError("Dedicated measurement child must have no inherited trace")
    if any(name.split(".")[0] in software.BLOCKED_IMPORTS for name in sys.modules):
        raise ValueError("Production/numerical import before metadata blockade")
    sys.meta_path.insert(0, blocker)
    try:
        sys.setprofile(profile)
        for role in controls.SOURCES:
            body = controls.helpers._body()
            accounts = {
                label: controls.controller(role, body, root=path)
                for label, path in (("before", before), ("current", ROOT))
            }
            for tracing in (False, True):
                sys.settrace(trace if tracing else None)
                for corpus, value in corpora.items():
                    expected = walk(value, (131072, 128, 8 * 2**20))
                    digest = hashlib.sha256(
                        json.dumps(expected, sort_keys=True).encode()
                    ).hexdigest()
                    for repeat in range(7):
                        pair = []
                        for label in (
                            ("before", "current") if repeat % 2 == 0 else ("current", "before")
                        ):
                            account, context = accounts[label]
                            counts.clear()
                            wall, cpu = time.perf_counter_ns(), time.process_time_ns()
                            with account(context):
                                actual = walk(value, (131072, 128, 8 * 2**20))
                            elapsed, cpu = (
                                time.perf_counter_ns() - wall,
                                time.process_time_ns() - cpu,
                            )
                            if actual != expected:
                                raise ValueError("Observer changed metadata projection")
                            if sys.getprofile() is not profile or sys.gettrace() is not (
                                trace if tracing else None
                            ):
                                raise ValueError("Observer failed exact inherited hook restoration")
                            row = dict(
                                role=role,
                                tracing=tracing,
                                corpus=corpus,
                                repeat=repeat,
                                version=label,
                                wall_ns=elapsed,
                                cpu_ns=cpu,
                                inherited_events=dict(counts),
                                projection_sha256=digest,
                            )
                            pair.append(row)
                            rows.append(row)
                        if pair[0]["inherited_events"] != pair[1]["inherited_events"]:
                            raise ValueError("Observer dropped inherited metadata events")
    finally:
        try:
            sys.settrace(prior_trace)
        finally:
            sys.setprofile(prior_profile)
            sys.meta_path.remove(blocker)
        snapshot.write_json(
            output / "guard.json",
            dict(
                attempted=attempted,
                hooks_restored=sys.getprofile() is prior_profile and sys.gettrace() is prior_trace,
                imports_restored=blocker not in sys.meta_path,
            ),
        )
    summaries = []
    for role in controls.SOURCES:
        for tracing in (False, True):
            for corpus in corpora:
                times = {
                    label: statistics.median(
                        row["wall_ns"]
                        for row in rows
                        if (row["role"], row["tracing"], row["corpus"], row["version"])
                        == (role, tracing, corpus, label)
                    )
                    for label in ("before", "current")
                }
                summaries.append(
                    dict(
                        role=role,
                        tracing=tracing,
                        corpus=corpus,
                        before_median_ms=times["before"] / 1e6,
                        current_median_ms=times["current"] / 1e6,
                        speed_ratio=times["before"] / times["current"],
                    )
                )
    snapshot.write_json(output / "runtime.json", runtime.inventory())
    snapshot.write_json(
        output / "measurement.json",
        dict(
            scope=(
                "isolated observer code and unchanged metadata walker; "
                "not full-phase or scientific work"
            ),
            full_native_imports=False,
            actual_owner_credit=False,
            before_pins=inputs["before_pins"],
            current_manifest=inputs["manifest_sha256"],
            inherited_counts_and_projections_identical=True,
            rows=rows,
            summaries=summaries,
        ),
    )


def run(output, before):
    output.mkdir()
    (output / "process").mkdir()
    declared = json.loads((before.parent / "before.json").read_text())["files"]
    before_pins = {
        name: declared[name] for name in software.OBSERVER_FILES if name.startswith("src/")
    }
    for name, expected in before_pins.items():
        if snapshot.digest(before / name) != expected:
            raise ValueError("Before-source bytes differ from saved baseline")
    snapshot.freeze(ROOT, output / "source", {name: name for name in FILES})
    snapshot.write_json(
        output / "inputs.json",
        dict(
            before_source=str(before),
            before_pins=before_pins,
            manifest_sha256=snapshot.digest(output / "source/SNAPSHOT.json"),
            cpu=6,
            threads=1,
            wall_seconds=480,
            rss_bytes=2**30,
            reserve_bytes=8 * 2**30,
            actual_native_source_or_scientific_release=False,
        ),
    )
    env = dict(
        os.environ,
        PYTHONPATH=str(output / "source"),
        PYTHONDONTWRITEBYTECODE="1",
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
    )
    outcome = guard.run_bounded(
        [sys.executable, "-B", str(output / "source" / FILE), "--child", str(output)],
        directory=output / "process",
        cwd=output / "source",
        env=env,
        timeout=480,
        max_rss_bytes=2**30,
        min_available_bytes=8 * 2**30,
    )
    snapshot.verify(output / "source")
    snapshot.write_json(
        output / "result.json",
        dict(status="completed", process=outcome, complete_phase_or_scientific_credit=False),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--run", type=Path)
    modes.add_argument("--child", type=Path)
    parser.add_argument("--before", type=Path)
    args = parser.parse_args()
    os.sched_setaffinity(0, {6})
    resource.setrlimit(resource.RLIMIT_AS, (2**30 if args.child else 512 * 2**20, 2**30))
    if args.child:
        child(args.child.resolve())
    else:
        if args.before is None:
            parser.error("--run requires the exact saved --before source")
        run(args.run.resolve(), args.before.resolve())


if __name__ == "__main__":
    main()
