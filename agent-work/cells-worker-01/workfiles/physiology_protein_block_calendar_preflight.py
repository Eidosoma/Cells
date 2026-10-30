"""Chief-authorized single CPU3 preflights; no CPU7 access or automatic chaining."""

import argparse
import hashlib
import json
import os
import shutil
import sys
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
BASE = Path("/mnt/workspaces/Cells/physiology-protein-block-calendar-tests-20261030-02")
TEST = "tests/integration/test_physiology_protein_block_calendar.py"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open("x") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def prepare(out):
    queue = json.loads((WORK / "physiology_protein_block_calendar_workqueue.json").read_text())
    base = json.loads((BASE / "inputs.json").read_text())
    for name, expected in base["source_hashes"].items():
        assert sha(BASE / "source" / name) == expected, name
    for name, expected in queue["protected_sha256"].items():
        assert sha(ROOT / name) == expected, name
    out.mkdir(exist_ok=False)
    shutil.copytree(BASE / "source", out / "source")
    for name in queue["owned"]:
        shutil.copy2(ROOT / name, out / "source" / name)
    for name in ("tmp", "cache", "evidence"):
        (out / name).mkdir()
    for name, target in (
        ("physiology_protein_block_calendar_preflight.py", "preflight.py"),
        ("physiology_protein_block_calendar_oracle.py", "isolated_reference.py"),
    ):
        shutil.copy2(WORK / name, out / target)
    env = {key: value.replace(str(BASE), str(out)) for key, value in base["environment"].items()}
    env["CELLS_PROTEIN_BLOCK_CPU"] = "3"
    sources = {
        str(path.relative_to(out / "source")): sha(path)
        for path in sorted((out / "source").rglob("*"))
        if path.is_file()
    }
    write(
        out / "inputs.json",
        dict(
            kind="cells.charged_block_calendar_cpu3_preflight@1",
            authorization=(
                "Chief permits short CPU3 preflights, one at a time; CPU7 stays reserved"
            ),
            source_hashes=sources,
            owned_source_sha256={name: sha(ROOT / name) for name in queue["owned"]},
            protected_sha256=queue["protected_sha256"],
            base_source_capture=str(BASE),
            environment=env,
            resource_limits=dict(
                cpu=3,
                threads=1,
                max_command_seconds=480,
                max_child_tree_rss_bytes=2**30,
                min_available_host_bytes=8 * 2**30,
            ),
            helper_sha256={
                name: sha(out / name) for name in ("preflight.py", "isolated_reference.py")
            },
            full_qualification=False,
            automatic_followup=False,
            automatic_polling=False,
            no_CPU7_status_access=True,
        ),
    )
    print(
        json.dumps(
            dict(
                status="prepared", inputs=str(out / "inputs.json"), sha256=sha(out / "inputs.json")
            )
        )
    )


def run(out, label, node, oracle):
    inputs = json.loads((out / "inputs.json").read_text())
    for name, expected in inputs["source_hashes"].items():
        assert sha(out / "source" / name) == expected, name
    for name, expected in inputs["helper_sha256"].items():
        assert sha(out / name) == expected, name
    folder = out / label
    folder.mkdir()
    (folder / "process").mkdir()
    os.sched_setaffinity(0, {3})
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(out / "source/src"), str(out / "source")]
    from validation.assembly.component_process import run_bounded

    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("JAX_", "XLA_", "PYTEST_", "CELLS_"))
        and key not in {"PYTHONPATH", "PYTHONHOME", "CUDA_VISIBLE_DEVICES"}
    }
    env.update(inputs["environment"] | dict(CELLS_PROTEIN_BLOCK_PHASE=label))
    if oracle:
        command = [sys.executable, "-B", str(out / "isolated_reference.py"), node, "2"]
    else:
        command = [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "--noconftest",
            "-p",
            "no:cacheprovider",
            "-q",
            TEST + "::" + node,
            "--basetemp",
            str(out / "tmp" / label),
            "--junitxml",
            str(folder / "tests.xml"),
        ]
    write(
        folder / "inputs.json",
        dict(
            command=command,
            resource_limits=inputs["resource_limits"],
            single_bounded_preflight=True,
            automatic_followup=False,
        ),
    )
    try:
        resources = run_bounded(
            command,
            directory=folder / "process",
            cwd=out / "source",
            env=env,
            timeout=480,
            max_rss_bytes=2**30,
            min_available_bytes=8 * 2**30,
            process_tree_memory_metric="rss",
        )
        runtime = json.loads(
            (
                out / "evidence/tissue-step" / ("protein-block-calendar-runtime-" + label + ".json")
            ).read_text()
        )
        assert runtime["measured_child_cpu_affinity"] == [3]
        if oracle:
            result = json.loads((out / "evidence" / ("independence-" + node + ".json")).read_text())
            assert result["actual_reference_forms"] == 2
            check_ids = []
        else:
            rows = ET.parse(folder / "tests.xml").getroot().findall(".//testcase")
            assert len(rows) == 1
            assert all(
                all(row.find(key) is None for key in ("failure", "error", "skipped"))
                for row in rows
            )
            check_ids = [row.attrib for row in rows]
        write(
            folder / "result.json",
            dict(
                status="passed_preflight",
                check_ids=check_ids,
                resources=resources,
                measured_child_runtime=runtime,
                full_qualification=False,
                automatic_followup=False,
                no_CPU7_status_access=True,
            ),
        )
        print(
            json.dumps(
                dict(
                    status="passed_preflight",
                    result=str(folder / "result.json"),
                    seconds=resources["elapsed_seconds"],
                )
            )
        )
    except BaseException:
        write(
            folder / "failure.json",
            dict(
                status="failed_preflight",
                traceback=traceback.format_exc(),
                automatic_retry=False,
                automatic_followup=False,
                no_CPU7_status_access=True,
            ),
        )
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "run"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("--label")
    parser.add_argument("--node")
    parser.add_argument("--oracle", action="store_true")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.directory.resolve())
    else:
        if not args.label or not args.node:
            parser.error("Run exactly one explicitly selected preflight")
        run(args.directory.resolve(), args.label, args.node, args.oracle)


if __name__ == "__main__":
    main()
