"""Check a resumed run against the continuity record that admitted it (design section 4.2).

For a run folder written by validation/continuity/dev_run.py (no engine writer records a
vector-window run; dev_run.py defines the folder), verify that:
  record     the run's provenance names a record in the run's own folder, whose
             record_sha256 matches and which parse_record accepts; the run's inputs name it
  scope      the run's path and window policy are the ones declared at load, and the
             record's scope covers them
  checkpoint the record binds the checkpoint the run resumed from (its manifest digest)
  identity   the run's source and runtime are the record's ``to``
  evidence   every evidence file still has its recorded digest
  schedule   the run's rounds (windows.jsonl) are the rounds the probe's builders iterated
             under S1 (its rounds.jsonl): each live world's start, end and step count
  lineage    the chain of runs back to a fresh one: each admitted run's record repeats the
             lineage of the record before it, ending with it (section 5)
A fresh run, or a plain resume under the checkpoint's own source, passes with nothing to check
but its lineage.

Usage: verify_run.py RUN [--out REPORT.json]
Exit status: 0 all checks pass, 1 otherwise.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from cells import continuity
from cells.core.specs import digest, read_json


def sha256(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


class Report:
    def __init__(self):
        self.checks = []

    def check(self, name, ok, detail=None):
        self.checks.append(dict(check=name, ok=bool(ok), detail=detail))
        return bool(ok)

    @property
    def ok(self):
        return all(c["ok"] for c in self.checks)


def schedule(run, record, report):
    """The run's rounds against the rounds the S1 probe's builders iterated."""
    probe = next((e for e in record["evidence"] if e["role"] == "probe S1"), None)
    if not report.check("schedule.probe_named", probe is not None, "evidence role 'probe S1'"):
        return
    path = Path(probe["path"]).parent / "rounds.jsonl"
    rounds = [json.loads(x) for x in path.read_text().splitlines()]
    windows = [json.loads(x) for x in (Path(run) / "windows.jsonl").read_text().splitlines()]
    order = sorted(record["checkpoint"]["definitions"], key=int)
    mismatched = []
    for k, line in enumerate(windows):
        if k >= len(rounds):
            mismatched.append(f"round {k}: beyond the probe's {len(rounds)} rounds")
            continue
        for i, world in enumerate(order):
            ran, built = line["worlds"][world], rounds[k]["clocks"][i]
            steps = ran["end_step"] - ran["start_step"]
            if (steps > 0) != built["live"] or (
                built["live"]
                and (ran["start_time"], ran["end_time"], steps)
                != (built["start"], built["end"], built["steps"])
            ):
                mismatched.append(f"round {k}, world {world}")
    report.check("schedule.rounds", not mismatched, mismatched[:20] or f"{len(windows)} rounds")
    report.check(
        "schedule.horizon",
        len(windows) == record["scope"]["horizon_rounds"],
        f"{len(windows)} rounds run, {record['scope']['horizon_rounds']} in the record's scope",
    )


def admitted(run, manifest, inputs, report):
    provenance = manifest["provenance"]
    path = Path(provenance["continuity_record"])
    inside = path.resolve().is_relative_to(Path(run).resolve())
    report.check("record.in_run_folder", inside, str(path))
    try:
        record = continuity.parse_record(read_json(path))
    except Exception as exc:  # noqa: BLE001  (reported)
        report.check("record.verified", False, f"{type(exc).__name__}: {exc}")
        return None
    report.check("record.verified", True)
    report.check("record.digest", record["record_sha256"] == provenance["record_sha256"], str(path))
    report.check(
        "inputs.name_record",
        inputs.get("continuity_record") == str(path)
        and inputs.get("continuity_record_sha256") == sha256(path),
    )
    scope = record["scope"]
    report.check(
        "scope.declared",
        provenance["declared_path"] in scope["paths"]
        and provenance["declared_policy"] == scope["policy"],
        dict(declared=[provenance["declared_path"], provenance["declared_policy"]], scope=scope),
    )
    report.check(
        "scope.run",
        manifest["path"] == provenance["declared_path"]
        and manifest["policy"] == provenance["declared_policy"],
        dict(run=[manifest["path"], manifest["policy"]]),
    )
    checkpoint = Path(record["checkpoint"]["path"])
    saved = read_json(checkpoint / "manifest.json")
    fingerprint = saved.pop("manifest_sha256")
    report.check(
        "checkpoint.bound",
        record["checkpoint"]["manifest_sha256"]
        == provenance["parent_checkpoint_sha256"]
        == fingerprint
        == digest(saved)
        == inputs.get("checkpoint_manifest_sha256"),
        str(checkpoint),
    )
    report.check(
        "identity.source",
        digest(manifest["source_hashes"]) == record["to"]["source_hashes_sha256"],
    )
    report.check("identity.runtime", manifest["runtime"] == record["to"]["runtime"])
    stale = [e["path"] for e in record["evidence"] if sha256(e["path"]) != e["sha256"]]
    report.check("evidence.digests", not stale, stale or f"{len(record['evidence'])} files")
    schedule(run, record, report)
    return record


def lineage(run, record, report, depth=0):
    """Walk the runs back to a fresh one; each record's lineage repeats its parent's."""
    inputs = read_json(Path(run) / "inputs.json")
    parent = inputs.get("checkpoint_run")
    if parent is None:
        operation = read_json(Path(run) / "manifest.json")["provenance"]["operation"]
        return report.check(f"lineage[{depth}].fresh", operation == "fresh", str(run))
    provenance = read_json(Path(parent) / "manifest.json")["provenance"]
    expected = []
    if provenance["operation"] == "admitted_resume":
        before = continuity.parse_record(read_json(provenance["continuity_record"]))
        expected = [
            *before["lineage"],
            {"record": provenance["continuity_record"], "record_sha256": before["record_sha256"]},
        ]
    if record is not None:
        report.check(f"lineage[{depth}].record", record["lineage"] == expected, str(parent))
    parent_record = (
        continuity.parse_record(read_json(provenance["continuity_record"]))
        if provenance["operation"] == "admitted_resume"
        else None
    )
    return lineage(parent, parent_record, report, depth + 1)


def verify(run):
    run = Path(run)
    report = Report()
    manifest = read_json(run / "manifest.json")
    inputs = read_json(run / "inputs.json")
    report.check("run.complete", manifest.get("status") == "complete", manifest.get("kind"))
    stale = [n for n, d in manifest["files_sha256"].items() if sha256(run / n) != d]
    report.check("run.files", not stale, stale or f"{len(manifest['files_sha256'])} files")
    record = None
    if manifest["provenance"]["operation"] == "admitted_resume":
        record = admitted(run, manifest, inputs, report)
    lineage(run, record, report)
    return dict(
        run=str(run),
        operation=manifest["provenance"]["operation"],
        verdict="verified" if report.ok else "failed",
        checks=report.checks,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("run")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    result = verify(args.run)
    if args.out:
        with Path(args.out).open("x") as handle:
            json.dump(result, handle, indent=1, sort_keys=True)
            handle.write("\n")
    print(result["verdict"], *(c["check"] for c in result["checks"] if not c["ok"]), flush=True)
    return 0 if result["verdict"] == "verified" else 1


if __name__ == "__main__":
    sys.exit(main())
