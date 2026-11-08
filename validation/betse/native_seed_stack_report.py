"""Summarize saved C-level stack samples without importing simulation code.

Counts are sample presence, never call counts, exclusive CPU time, successful
stages or numerical evidence. Read only saved files; do not attach to a worker.
"""

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from validation import source_snapshot as snapshot

MAX_BYTES = 16 * 2**20
MAX_SAMPLES = 10000
HEADER = re.compile(r"Timeout \((\d+):(\d\d):(\d\d)\)!")
THREAD = re.compile(r"(?:Current thread|Thread) (0x[0-9a-f]+) \(most recent call first\):")
FRAME = re.compile(r'  File "([^"\n]+)", line ([1-9][0-9]*) in (.+)')
PHASE_FILES = frozenset(
    "src/cells/processes/betse_native_" + name + ".py"
    for name in (
        "world_phase_construction",
        "phase_assembly",
        "phase_caches",
        "phase_dyna",
        "phase_tail",
    )
)


def parse(text):
    samples, current, thread = [], None, None
    for number, line in enumerate(text.splitlines(), 1):
        header = HEADER.fullmatch(line)
        if header:
            if len(samples) >= MAX_SAMPLES:
                raise ValueError("Stack sample capacity exceeded")
            hours, minutes, seconds = map(int, header.groups())
            if minutes >= 60 or seconds >= 60 or hours * 3600 + minutes * 60 + seconds <= 0:
                raise ValueError("Invalid stack timer interval")
            current = dict(
                line=number,
                interval_seconds=hours * 3600 + minutes * 60 + seconds,
                threads=[],
                unparsed_lines=[],
            )
            samples.append(current)
            thread = None
        elif not line:
            continue
        elif current is None:
            raise ValueError("Stack log must begin with a timer sample")
        elif match := THREAD.fullmatch(line):
            thread = dict(thread=match[1], frames=[], truncated=False)
            current["threads"].append(thread)
        elif thread is not None and (match := FRAME.fullmatch(line)):
            thread["frames"].append((match[1], int(match[2]), match[3]))
        elif thread is not None and line.strip() == "...":
            thread["truncated"] = True
        else:
            current["unparsed_lines"].append(dict(line=number, text=line))
    if not samples:
        raise ValueError("No saved stack samples")
    return samples


def summarize(text, source, files):
    """Attribute exact saved paths to the supplied frozen source manifest."""
    samples = parse(text)
    prefix = str(source).rstrip("/") + "/"
    inclusive, leaves, phases = Counter(), Counter(), Counter()
    project_samples = project_threads = 0
    missing, incomplete = set(), []
    for ordinal, sample in enumerate(samples, 1):
        present, phase = set(), set()
        if not sample["threads"] or sample["unparsed_lines"]:
            incomplete.append(ordinal)
        for thread in sample["threads"]:
            project = []
            if thread["truncated"] or not thread["frames"]:
                incomplete.append(ordinal)
            for filename, line, function in thread["frames"]:
                if not filename.startswith(prefix):
                    continue
                relative = filename[len(prefix) :]
                if relative not in files:
                    missing.add(relative)
                    continue
                project.append((relative, line, function))
                present.add((relative, function))
                if relative in PHASE_FILES:
                    phase.add(relative)
            if project:
                project_threads += 1
                leaves[project[0]] += 1
        if present:
            project_samples += 1
        inclusive.update(present)  # Recursive frames count once per sample.
        phases.update(phase)
    return dict(
        samples=len(samples),
        samples_with_project_frames=project_samples,
        project_thread_observations=project_threads,
        intervals_seconds=sorted({s["interval_seconds"] for s in samples}),
        incomplete_samples=sorted(set(incomplete)),
        unbound_source_paths=sorted(missing),
        project_functions=[
            dict(path=p, function=f, samples=count, sha256=files[p]["sha256"])
            for (p, f), count in inclusive.most_common()
        ],
        first_project_frames=[
            dict(
                path=p, line=line, function=f, thread_observations=count, sha256=files[p]["sha256"]
            )
            for (p, line, f), count in leaves.most_common()
        ],
        phase_files=[dict(path=p, samples=count) for p, count in phases.most_common()],
        observations=samples,
        limitations=[
            "Samples are locations, not call counts or exclusive timings.",
            "Multiple functions or threads can appear in the same sample.",
            "First project frame may be below a library call or an observer.",
            "Missing and truncated frames are explicit; no completion is inferred.",
            "Historical source observations do not establish current-run bottlenecks.",
        ],
        source_or_numerical_execution=False,
        stage_completion_or_scientific_credit=False,
    )


def _read(path):
    before = path.stat()
    if before.st_size > MAX_BYTES:
        raise ValueError("Bounded saved file required")
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    after = path.stat()
    if len(raw) > MAX_BYTES or (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError("Saved input changed during read")
    return raw


def report(run, output):
    run, output = run.resolve(strict=True), output.absolute()
    launch_raw = _read(run / "LAUNCH.json")
    launch = json.loads(launch_raw)
    plan_path = Path(launch["plan"]["path"])
    plan_raw = _read(plan_path)
    if hashlib.sha256(plan_raw).hexdigest() != launch["plan"]["sha256"]:
        raise ValueError("Saved launch plan changed")
    plan = json.loads(plan_raw)
    source = Path(plan["source"])
    if output.exists() or output.is_relative_to(run) or output.is_relative_to(source):
        raise ValueError("Fresh report destination outside saved run/source required")
    manifest = snapshot.verify(source, manifest_sha256=plan["source_snapshot"]["sha256"])
    stack_path = run / "worker/stacks.log"
    raw = _read(stack_path)
    value = summarize(raw.decode("utf-8"), source, manifest["files"])
    value.update(
        run=str(run),
        source=str(source),
        source_snapshot=plan["source_snapshot"],
        launch=dict(path=str(run / "LAUNCH.json"), sha256=hashlib.sha256(launch_raw).hexdigest()),
        launch_plan=launch["plan"],
        stack_log=dict(path=str(stack_path), sha256=hashlib.sha256(raw).hexdigest()),
        report_source=dict(path=str(Path(__file__).resolve()), sha256=snapshot.digest(__file__)),
    )
    output.mkdir(parents=True)
    snapshot.write_json(output / "report.json", value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = report(args.run, args.output)
    print(json.dumps(dict(samples=value["samples"], report=str(args.output / "report.json"))))


if __name__ == "__main__":
    main()
