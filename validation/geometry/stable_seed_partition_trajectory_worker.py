"""Unfrozen fresh-process trajectory segment launcher; never builds fixtures."""

import argparse
import os
import sys
import traceback
from pathlib import Path

from validation.geometry import stable_seed_partition_trajectory_authority as authority_gate
from validation.geometry import stable_seed_partition_trajectory_records as records

DRAFT_ONLY = True


def runtime_inventory(input_path):
    paths = {
        str(Path(sys.executable).resolve()),
        str(Path(__file__).resolve()),
        str(input_path.resolve()),
    }
    for module in tuple(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if path and Path(path).is_file():
            paths.add(str(Path(path).resolve()))
    missing = []
    for line in Path("/proc/self/maps").read_text().splitlines():
        row = line.split(maxsplit=5)
        if len(row) == 6 and row[5].startswith("/"):
            if Path(row[5]).is_file():
                paths.add(str(Path(row[5]).resolve()))
            else:
                missing.append(row[5])
    if len(paths) > 20000:
        raise ValueError("Bounded actual runtime inventory")
    files, errors = {}, {}
    for path in sorted(paths):
        try:
            files[path] = records.sha(path)
        except OSError as error:
            errors[path] = str(error)
    return dict(
        pid=os.getpid(),
        parent_pid=os.getppid(),
        source=str(Path(__file__).resolve()),
        source_sha256=records.sha(__file__),
        executable=sys.executable,
        python=sys.version,
        input_sha256=records.sha(input_path),
        affinity=sorted(os.sched_getaffinity(0)),
        files=files,
        file_errors=errors,
        mapped_file_errors=missing,
        threads={
            name: os.environ.get(name)
            for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
        },
    )


def launch(payload, directory, *, input_path):
    directory = Path(directory)
    envelope = records.Journal(directory.with_name(directory.name + "-worker"))
    try:
        envelope.append("original_launch_input", payload)
        if DRAFT_ONLY:
            raise authority_gate.PrerequisitePending("Trajectory segment launcher is unfrozen")
        index = authority_gate.parse(Path(payload["index"]).read_text())
        authority = {name: Path(path).read_text() for name, path in index["authority"].items()}
        authority_gate.require(authority, phase="trajectory")
        # No production imports before complete prerequisite authentication.
        from cells.processes import stable_seed_partition_trajectory as trajectory

        request = trajectory.from_index(
            index, payload["case_id"], refusal_id=payload.get("refusal_id")
        )
        result = trajectory.run_segment(
            request,
            payload["control_id"],
            directory,
            stop_step=payload.get("stop_step"),
            restart_directory=payload.get("restart_directory"),
        )
        origin = runtime_inventory(input_path)
        envelope.append("actual_runtime", origin)
        if origin["file_errors"] or origin["mapped_file_errors"]:
            raise ValueError("Incomplete actual trajectory runtime inventory")
        envelope.complete(
            dict(
                segment=result,
                scientific_accuracy_qualified=False,
                restart_equality_qualified=False,
            )
        )
        return result
    except BaseException as error:
        envelope.fail(
            dict(
                type=type(error).__name__,
                reason=str(error),
                code=getattr(error, "code", None),
                stage=getattr(error, "stage", None),
                detail=getattr(error, "detail", None),
                traceback=traceback.format_exc(),
                candidate_passed=False,
            )
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    launch(authority_gate.parse(args.input.read_text()), args.directory, input_path=args.input)


if __name__ == "__main__":
    main()
