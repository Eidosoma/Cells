"""Prospective held INIT runner; launch authority remains with the Chief.

Plan/typed-evidence operations are stdlib only. Scientific imports and pytest
are reachable only through an explicitly released successor and requested run.
"""

import argparse
import hashlib
import json
import math
import os
import sys
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 64 * 2**20:
        raise ValueError("Require a bounded regular metadata file")

    def pairs(rows):
        out = {}
        for key, value in rows:
            if key in out:
                raise ValueError("Duplicate JSON metadata key")
            out[key] = value
        return out

    def invalid(value):
        raise ValueError("Nonstandard JSON scalar: " + value)

    return json.loads(path.read_text(), object_pairs_hook=pairs, parse_constant=invalid)


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def verify(out, inputs):
    for field, base in (
        ("source_sha256", out / "source"),
        ("native_snapshot_sha256", out),
        ("tool_sha256", out),
    ):
        for name, pin in inputs[field].items():
            path = base / name
            if path.is_symlink() or not path.is_file() or sha(path) != pin:
                raise ValueError("Changed frozen " + field + ": " + name)
    if sha(out / "driver.py") != inputs["driver_sha256"]:
        raise ValueError("Changed frozen INIT driver")
    actual = {
        str(p.relative_to(out / "source")) for p in (out / "source").rglob("*") if p.is_file()
    }
    if actual != set(inputs["source_sha256"]):
        raise ValueError("Unexpected or missing files in frozen INIT source tree")
    for name, pin in inputs["live_native_source_sha256"].items():
        if (
            sha(Path(inputs["native_checkout"]) / name) != pin
            or sha(Path(inputs["installed_native_package"]) / name) != pin
        ):
            raise ValueError("Changed pinned checkout/installed native source: " + name)


def verify_ids(path, expected):
    cases = ET.parse(path).getroot().findall(".//testcase")
    actual = [
        case.attrib["classname"].replace(".", "/") + ".py::" + case.attrib["name"] for case in cases
    ]
    if len(actual) != len(set(actual)) or set(actual) != set(expected):
        raise ValueError("Require the exact unique prepared pytest IDs")
    if any(case.find(tag) is not None for case in cases for tag in ("failure", "error", "skipped")):
        raise ValueError("A prepared INIT check failed, errored or skipped")
    return actual


def reference_report(folder, mode):
    report = read(folder / "comparison.json")
    if (
        report.get("fresh_conditional_reference") is not True
        or report.get("carried_reference_forms") != 0
    ):
        raise ValueError("Missing fresh conditional reference assertion")
    for section, limit in (("fields", 1.0), ("resolutions", 0.1)):
        values = [row["normalized_max_error"] for row in report[section].values()]
        if not values or any(
            type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= limit
            for v in values
        ):
            raise ValueError("Invalid fixed budget or self-resolution report")
    for level in (1, 2):
        row = read(folder / ("reference-" + str(level) + ".json"))
        if (
            row["production_imports_denied"] is not True
            or row["loaded_production_modules"]
            or row["carried_reference_forms"] != 0
            or row["decimal_precision"] != (100 if level == 1 else 160)
            or row["source_phase"] != "INIT"
            or row["legacy_run_sim"] is not False
        ):
            raise ValueError("Wrong independent INIT reference/runtime receipt")
        if mode != "bootstrap" and row["mode"] != (
            "cold_initialization" if mode == "cold" else mode
        ):
            raise ValueError("Wrong fresh INIT reference mode")
        if mode in {"setup", "nak", "channels", "material", "mechanics"}:
            raw = folder / ("raw-reference-" + str(level))
            if not raw.is_dir() or not any(raw.glob("*.json")):
                raise ValueError("Missing complete retained Decimal source form")


def read_evidence(out, target, group):
    inputs = read(out / "inputs.json")
    spec = inputs["groups"][group]
    ids = verify_ids(target / "tests.xml", spec["node_ids"])
    sys.path.insert(0, str(out / "tools"))
    import capture_binding

    if Path(capture_binding.__file__).resolve() != out / "tools/capture_binding.py":
        raise ValueError("Wrong prospective INIT capture profile binder")
    base = target / "evidence/normal-ecm-init-phase"
    archives = []
    for manifest in sorted(base.rglob("manifest.json")):
        if (manifest.parent / "arrays.npz").is_file() and (manifest.parent / "data.json").is_file():
            result = capture_binding.bind(manifest.parent, profile="ordinary_ecm_init_phase_01")
            archives.append(
                dict(
                    path=str(manifest.parent.relative_to(target)),
                    manifest_sha256=sha(manifest),
                    metadata=result,
                )
            )
    if not archives:
        raise ValueError("No complete typed INIT evidence")
    case, category = spec["case"], spec["category"]
    forms = 0
    if category == "positive":
        completed = read(base / ("isolated-" + case) / "comparison.json")
        if (
            completed["completed"] is not True
            or completed["complete_calls"] != spec["accepted_calls"]
            or completed["independent_reference_forms"] != spec["independent_forms"]
            or completed["carried_reference_forms"] != 0
            or completed["whole_physical_initializer_credit"] is not False
        ):
            raise ValueError("Wrong complete INIT prefix/report count")
        prep = base / ("preparation-" + case)
        for mode in ("setup", "cold", "bootstrap"):
            reference_report(prep / mode, mode)
            forms += 2
        for index in range(spec["accepted_calls"]):
            for mode in ("nak", "material", "calcium", "channels", "network", "mechanics", "field"):
                reference_report(prep / ("point-" + str(index)) / mode, mode)
                forms += 2
        if (
            len(list(prep.rglob("reference-1.json"))) + len(list(prep.rglob("reference-2.json")))
            != forms
        ):
            raise ValueError("Extra or missing fresh reference forms")
    else:
        terminal = base / (
            (case + "-raw-failure-before-assertions")
            if category == "raw"
            else (case + "-exact-refusal")
            if category == "dependency"
            else (case + "-call-0-retained-exception")
        )
        if not (terminal / "manifest.json").is_file():
            raise ValueError("Missing exact named raw/observer/dependency refusal archive")
    if forms != spec["independent_forms"]:
        raise ValueError("Wrong accepted independent form count")
    write(
        target / "evidence-binding.json",
        dict(
            status="passed",
            group=group,
            exact_pytest_ids=ids,
            typed_archives=archives,
            independent_reference_forms=forms,
            inherited_qualification=False,
            whole_native_phase_completed=False,
            scientific_scope="supplied ordinary INIT source conditionals only",
        ),
    )


def run(out, group, cpu, requested):
    inputs = read(out / "inputs.json")
    # This check precedes directory creation, imports, affinity and subprocesses.
    if inputs["execution_hold"] or (out / ".execution_hold").exists():
        raise ValueError(
            "INIT source handoff is held; Chief review and a separately released "
            "successor are required"
        )
    if not requested or cpu is None or cpu not in os.sched_getaffinity(0):
        raise ValueError("Require a newly requested round and explicitly coordinated available CPU")
    if group not in inputs["groups"]:
        raise ValueError("Unknown separately bounded INIT group")
    verify(out, inputs)
    target = out / ("run-" + group)
    target.mkdir(exist_ok=False)
    stage = "setup"
    try:
        for name in ("tmp", "cache", "evidence", "process", "reader-process"):
            (target / name).mkdir()
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("JAX_", "XLA_", "CELLS_", "PYTEST_"))
            and k not in {"PYTHONPATH", "PYTHONHOME", "CUDA_VISIBLE_DEVICES"}
        }
        env.update(
            PYTHONPATH=str(out / "source/src") + os.pathsep + str(out / "source"),
            PYTHONDONTWRITEBYTECODE="1",
            PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
            OMP_NUM_THREADS="1",
            OPENBLAS_NUM_THREADS="1",
            MKL_NUM_THREADS="1",
            NUMEXPR_NUM_THREADS="1",
            BLIS_NUM_THREADS="1",
            VECLIB_MAXIMUM_THREADS="1",
            CUDA_VISIBLE_DEVICES="",
            JAX_PLATFORMS="cpu",
            JAX_ENABLE_X64="true",
            MALLOC_ARENA_MAX="2",
            TMPDIR=str(target / "tmp"),
            XDG_CACHE_HOME=str(target / "cache"),
            CELLS_COMPONENT_EVIDENCE=str(target / "evidence"),
            CELLS_INIT_PHASE_RELEASED="1",
        )
        os.sched_setaffinity(0, {cpu})
        sys.dont_write_bytecode = True
        sys.path[:0] = [str(out / "source/src"), str(out / "source")]
        from validation.assembly.component_process import run_bounded

        command = [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "--noconftest",
            "-p",
            "no:cacheprovider",
            "-q",
            *inputs["groups"][group]["node_ids"],
            "--basetemp",
            str(target / "tmp/pytest"),
            "--junitxml",
            str(target / "tests.xml"),
        ]
        write(
            target / "execution.json",
            dict(
                command=command, group=group, cpu=cpu, requested_round=True, automatic_retry=False
            ),
        )
        stage = "bounded_scientific_group"
        resources = run_bounded(
            command,
            directory=target / "process",
            cwd=out / "source",
            env=env,
            timeout=480,
            max_rss_bytes=2**30,
            min_available_bytes=8 * 2**30,
            process_tree_memory_metric="rss",
        )
        stage = "bounded_typed_evidence_validation"
        reader = run_bounded(
            [
                sys.executable,
                "-B",
                str(out / "driver.py"),
                "--read-evidence",
                str(target),
                "--group",
                group,
            ],
            directory=target / "reader-process",
            cwd=out,
            env=env,
            timeout=120,
            max_rss_bytes=2**30,
            min_available_bytes=8 * 2**30,
            process_tree_memory_metric="rss",
        )
        verify(out, inputs)
        report = read(target / "evidence-binding.json")
        write(
            target / "result.json",
            dict(
                status="passed",
                group=group,
                resources=resources,
                reader_resources=reader,
                evidence=report,
                qualification_inherited=False,
                native_full_phase_completed=False,
                whole_physical_initializer_credit=False,
                automatic_followup=False,
            ),
        )
    except BaseException as error:
        write(
            target / "failure.json",
            dict(
                status="failed",
                stage=stage,
                type=type(error).__name__,
                message=str(error),
                traceback=traceback.format_exc(),
                preserve_raw=True,
                automatic_retry=False,
            ),
        )
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--group")
    parser.add_argument("--coordinated-cpu", type=int)
    parser.add_argument("--requested-round", action="store_true")
    parser.add_argument("--read-evidence", type=Path)
    parser.add_argument("--plan", action="store_true")
    args = parser.parse_args()
    out = Path(__file__).resolve().parent
    if args.plan:
        inputs = read(out / "inputs.json")
        print(
            json.dumps(
                dict(
                    execution_hold=inputs["execution_hold"],
                    groups=inputs["groups"],
                    planned=inputs["planned"],
                ),
                indent=2,
            )
        )
    elif args.read_evidence is not None:
        read_evidence(out, args.read_evidence, args.group)
    else:
        run(out, args.group, args.coordinated_cpu, args.requested_round)


if __name__ == "__main__":
    main()
