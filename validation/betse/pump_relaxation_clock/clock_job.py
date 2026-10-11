"""One explicit label-construction correction to the frozen saved-data reviewer."""

import argparse
import json
import subprocess
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import clock_labels

HERE = Path(__file__).resolve().parent
OLD_HERE = HERE.parent / "pump_relaxation_audit"
sys.path.insert(0, str(OLD_HERE))
import review_context as previous  # noqa: E402
import review_job as original_job  # noqa: E402

c, e, util, ROOT = previous.c, previous.e, previous.util, previous.ROOT
FAILED = ROOT / "runs/ref-005e-saved-review-2026-09-18/review-01"
FAILED_REG = "950d1f029b83210eedab30a3b2098fa9772b4aca823c35b573f741a0216c90ea"
FAILED_SHA = "0755a7007be4a356ca6d9c97df090136cedab4baebd15db75c71ff930d00e27a"
NUMPY_SOURCE = "upstream/betse-venv/lib/python3.13/site-packages/numpy/_core/function_base.py"
AMENDMENT = dict(
    kind="raw_label_operation_order_only",
    original_registration_sha256=FAILED_REG,
    original_failure_sha256=FAILED_SHA,
    old_formula="(index * duration) / (count - 1)",
    corrected_formula="index * (duration / (count - 1)); final label = duration",
    label_comparison="exact float64 bits, including endpoint and signed zero",
    physical_clock_changed=False,
    scientific_tolerances_changed=False,
    failed_evidence_preserved=True,
)


def sources():
    names = set(previous.sources()) | {NUMPY_SOURCE}
    names.update(str(p.relative_to(ROOT)) for p in HERE.glob("*.py"))
    return {n: c.sha(c.child(ROOT, n)) for n in sorted(names)}


def failure_receipt(inputs):
    c.need(
        c.sha(FAILED / "registration.json") == FAILED_REG
        and c.sha(FAILED / "failure.json") == FAILED_SHA
        and not (FAILED / "completion.json").exists(),
        "Preserved failed review identity",
    )
    r = c.read(FAILED / "registration.json", None)
    c.need(
        r["scope"] == previous.SCOPE
        and r["sources_sha256"] == previous.sources()
        and r["inputs"] == inputs,
        "Preserved failed review context",
    )
    c.capsule(FAILED, r["sources_sha256"])
    c.need(
        original_job.software(c.child(ROOT, r["software"]["path"])) == r["software"],
        "Original software binding",
    )
    files, _ = c.inventory(FAILED)
    c.need(
        set(files)
        == {
            "registration.json",
            "sources.zip",
            "launch.json",
            "started.json",
            "runner.stdout.log",
            "runner.stderr.log",
            "failure.json",
        },
        "Failed review coverage",
    )
    failure = c.read(FAILED / "failure.json", None)
    c.need(
        failure["status"] == "independent_review_failed_not_qualified"
        and failure["traceback"].endswith("ValueError: Independent mismatch: raw_labels_s\n")
        and (FAILED / "runner.stdout.log").read_bytes() == b"",
        "Expected failed boundary",
    )
    return dict(
        directory=str(FAILED.relative_to(ROOT)),
        files_sha256=files,
        original_completion_present=False,
    )


def inputs():
    evidence = previous.authenticate_inputs()
    return dict(evidence=evidence, preserved_review=failure_receipt(evidence))


def receipt(path):
    result = original_job.receipt(path)
    cases = ET.parse(path).getroot().findall("testsuite/testcase")
    required = {
        "test_clock_saved_failure",
        "test_clock_numpy_grids",
        "test_clock_passthrough",
        "test_clock_corruption",
        "test_clock_private_dispatch",
        "test_clock_binding",
        "test_clock_detached",
        "test_clock_preserved_failure",
    }
    c.need(
        required <= {v.get("name", "").split("[")[0] for v in cases}, "Clock regression coverage"
    )
    return result


def controller():
    """Private module instances; no shared reviewer, physics, evidence or plan is patched."""
    job = previous.private("_clock_review_controller", OLD_HERE / "review_job.py")
    work = previous.private("_clock_saved_review", OLD_HERE / "saved_review.py")
    original = work.native_records

    def inspect(*args):
        return clock_labels.inspect(original, c.exact.Exact, *args)

    work.native_records = SimpleNamespace(**(vars(original) | {"inspect": inspect}))
    job.ctx = SimpleNamespace(
        **(
            vars(previous)
            | dict(
                HERE=HERE,
                SCOPE=previous.SCOPE | {"clock_amendment": AMENDMENT},
                sources=sources,
                authenticate_inputs=inputs,
            )
        )
    )
    job.saved_review, job.receipt = work, receipt
    return job


def launch(job, output, proof):
    # The unchanged controller launches its own frozen script. This entrypoint
    # launches the adapter script instead; process ownership and limits are identical.
    job.register(output, proof)
    try:
        digest = c.sha(output / "registration.json")
        with (
            (output / "runner.stdout.log").open("x") as out,
            (output / "runner.stderr.log").open("x") as err,
        ):
            child = subprocess.Popen(
                [
                    "taskset",
                    "-c",
                    "0-3",
                    str(ROOT / ".venv/bin/python"),
                    "-B",
                    str(Path(__file__).resolve()),
                    "execute",
                    str(output),
                    "--registration-sha",
                    digest,
                ],
                cwd=ROOT,
                env=util.environment(),
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                start_new_session=True,
            )
        ack = dict(
            status="launched_detached",
            pid=child.pid,
            registration_sha256=digest,
            launched_utc=datetime.now(UTC).isoformat(),
            automatic_polling=False,
        )
        util.write(output / "launch.json", ack)
        return ack
    except BaseException:
        util.write(
            output / "launch-failure.json",
            dict(status="not_launched", traceback=traceback.format_exc()),
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "launch", "execute"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--tests", type=Path)
    parser.add_argument("--software", type=Path)
    parser.add_argument("--registration-sha")
    args = parser.parse_args()
    key = dict(check="tests", launch="software", execute="registration_sha")[args.action]
    if getattr(args, key) is None:
        parser.error("Missing input for " + args.action)
    job = controller()
    if args.action == "check":
        print(json.dumps(job.check(args.output.absolute(), args.tests.absolute()), sort_keys=True))
    elif args.action == "launch":
        print(
            json.dumps(
                launch(job, args.output.absolute(), args.software.absolute()), sort_keys=True
            )
        )
    else:
        job.execute(args.output.absolute(), args.registration_sha)
