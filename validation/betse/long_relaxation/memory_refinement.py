"""Authenticate the measured memory qualification for the 512k-step pilot.

The existing pilot executes and reviews the run. This module only supplies its
qualified prefix, bounded resource estimates and regression gate.
"""

import math
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pilot
from pickle_buffers import MODE

u = pilot.u
DT = 1.953125e-7
STEPS = 512000
TEST_FILES = [
    "validation/betse/long_relaxation/test_pilot.py",
    "validation/betse/long_relaxation/test_memory.py",
    "validation/betse/long_relaxation/test_memory_refinement.py",
]
EXTENSIONS = {
    "validation/betse/long_relaxation/pilot.py",
    "validation/betse/long_relaxation/streamed_review.py",
    "validation/betse/long_relaxation/memory_refinement.py",
    "validation/betse/long_relaxation/test_memory_refinement.py",
    "validation/betse/long_relaxation/test_pilot.py",
    "validation/betse/fresh_rerun/prepare.py",
    "validation/betse/pump_relaxation_clock/clock_labels.py",
}


def compatible_sources(qualified, candidate):
    """Only the declared clock, budget, working-set and runner extensions may differ."""
    old = qualified["sources_sha256"]
    changed = {
        name for name in old.keys() | candidate.keys() if old.get(name) != candidate.get(name)
    }
    u.need(
        changed <= EXTENSIONS,
        "Memory-qualified source changed outside the declared extension: "
        + str(sorted(changed - EXTENSIONS)),
    )


def authenticate(root, parent):
    r, done, result = (
        u.read(root / p) for p in ("registration.json", "completion.json", "result.json")
    )
    u.need(
        done["status"] == result["status"] == "betse_memory_prefix_qualification_completed"
        and done["registration_sha256"] == u.sha(root / "registration.json")
        and done["result_sha256"] == u.sha(root / "result.json")
        and not (root / "failure.json").exists(),
        "Require a completed memory/prefix qualification",
    )
    u.need(
        Path(r["parent"]).resolve() == parent.resolve()
        and r["parent_completion_sha256"] == u.sha(parent / "completion.json")
        and r["dt_s"] == result["dt_s"] == DT
        and r["duration_s"] == result["duration_s"] == 0.01
        and r["steps"] == result["steps"] == STEPS // 10
        and r["capacity_steps"] == STEPS
        and r["checkpoint_mode"] == MODE
        and r["protocol"] == u.plan(),
        "Memory qualification clock, parent or science changed",
    )
    u.need(
        result["prefix_qualified"] is True
        and result["failed_numeric_limits"] == []
        and result["scientific_tolerances_changed"] is False
        and result["memory"]["projected_memory_fits"] is True
        and result["actual_512000_step_capture_qualified"] is False,
        "Memory qualification did not pass its declared scope",
    )
    u.need(u.sources(root / "source") == r["sources_sha256"], "Memory qualification source changed")
    pilot.authenticate_files(root, r["inputs_sha256"])
    phases = tuple(r["phase_limits_seconds"])
    u.need(
        set(phases)
        == {
            "regression",
            "sample",
            "capacity",
            "capacity_load",
            "overlap",
            "observed",
            "unobserved",
            "checkpoints",
            "compare",
        },
        "Memory qualification phase coverage",
    )
    receipt = pilot.authenticate_simulations(root, phases)
    u.need(
        receipt["phase_completions_sha256"] == result["phase_completions_sha256"],
        "Memory phase receipt links changed",
    )
    for phase in phases:
        directory = root / phase
        stage = u.read(directory / "completion.json")
        u.need(
            stage["registration_sha256"] == u.sha(directory / "registration.json")
            and u.read(directory / "registration.json")["root_registration_sha256"]
            == u.sha(root / "registration.json"),
            "Memory phase registration changed",
        )
    for name, relative in (
        ("preparation", "prepare"),
        ("reference", "reference"),
        ("prefix", "native/pump_leak/2"),
    ):
        u.need(
            u.sha(Path(r["fresh_parent"]) / relative / "completion.json")
            == r["upstream"][name + "_completion_sha256"],
            "Memory upstream receipt changed",
        )
    u.need(
        u.read(root / "capacity/result.json")["target_steps"] == STEPS,
        "Synthetic capacity extent changed",
    )
    u.need(
        u.read(root / "capacity_load/result.json")["ordinary_betse_loader"] is True,
        "Ordinary checkpoint load was not checked",
    )
    return (
        r,
        result,
        dict(
            path=str(root.resolve()),
            registration_sha256=u.sha(root / "registration.json"),
            result_sha256=u.sha(root / "result.json"),
            completion_sha256=u.sha(root / "completion.json"),
            **receipt,
        ),
    )


def preflight(parent, qualification, result, *, available_memory, free_disk):
    """Use full-sized synthetic storage plus measured native/review prefix costs."""
    r = u.read(parent / "registration.json")
    u.need(pilot.native_controls(r) == (2, 2 * DT, STEPS // 2), "Require the quarter-step parent")
    u.need(
        result["dt_s"] == DT
        and result["steps"] == STEPS // 10
        and result["prefix_qualified"] is True,
        "Require the qualified finer prefix",
    )
    factor, stream_limit, artifact_limit = 10, 2 * 1024**3, 8 * 1024**3
    costs = {
        phase: u.read(qualification / phase / "completion.json")
        for phase in ("capacity", "observed", "unobserved", "compare")
    }
    native_peak = math.ceil(costs["capacity"]["peak_rss_bytes"] * 1.3)
    review_peak = math.ceil(costs["compare"]["peak_rss_bytes"] * factor * 1.3)
    rows = {}
    for phase in ("observed", "unobserved"):
        directory = qualification / phase
        sizes = [p.stat().st_size for p in directory.rglob("*") if p.is_file()]
        stream = sum(p.stat().st_size for p in (directory / "capture/stream").iterdir())
        rows[phase] = dict(
            projected_artifact_bytes=math.ceil(sum(sizes) * factor * 1.5),
            projected_largest_file_bytes=math.ceil(max(sizes) * factor * 1.5),
            projected_stream_bytes=math.ceil(stream * factor * 1.5),
            projected_peak_rss_bytes=native_peak,
        )
        u.need(
            max(rows[phase]["projected_largest_file_bytes"], rows[phase]["projected_stream_bytes"])
            <= stream_limit,
            "Refinement file/stream allowance",
        )
    review_output = max(
        128 * 1024**2,
        math.ceil(
            sum(p.stat().st_size for p in (qualification / "compare").rglob("*") if p.is_file())
            * factor
            * 1.5
        ),
    )
    memory = max(native_peak, review_peak)
    output = sum(v["projected_artifact_bytes"] for v in rows.values()) + review_output
    u.need(memory <= 16 * 1024**3, "Refinement process memory allowance")
    u.need(available_memory >= memory + 4 * 1024**3, "Refinement available-memory reserve")
    u.need(output <= artifact_limit, "Refinement total artifact allowance")
    u.need(free_disk >= artifact_limit + 4 * 1024**3, "Refinement disk reserve")
    return dict(
        status="refinement_resources_fit",
        native_index=3,
        dt_s=DT,
        steps=STEPS,
        native_parallel=False,
        native_stream_bytes=stream_limit,
        artifact_bytes=artifact_limit,
        process_address_space_bytes=16 * 1024**3,
        native_cost_source=str(qualification),
        step_count_factor=factor,
        memory_headroom_multiplier=1.3,
        artifact_headroom_multiplier=1.5,
        phases=rows,
        projected_review_peak_rss_bytes=review_peak,
        projected_review_artifact_bytes=review_output,
        projected_parallel_native_peak_rss_bytes=2 * native_peak,
        projected_concurrent_peak_rss_bytes=memory,
        projected_artifact_bytes=output,
        available_memory_bytes=available_memory,
        free_disk_bytes=free_disk,
        memory_reserve_bytes=4 * 1024**3,
        disk_reserve_bytes=4 * 1024**3,
        projected_seconds=factor
        * sum(costs[p]["elapsed_seconds"] for p in ("observed", "unobserved", "compare")),
        native_memory_basis=(
            "Measured full-size independent synthetic histories and inline checkpoint writer"
        ),
        review_memory_basis=(
            "Ten times measured prefix review; full histories released before prefix loading"
        ),
        scientific_tolerances_changed=False,
        native_histories_retained=True,
        native_memory_bounded=False,
        actual_512000_step_capture_qualified=False,
    )


def regression(root, registration, directory):
    import pytest

    u.need(registration["regression_tests"] == TEST_FILES, "Refinement regression coverage changed")
    scratch = Path(registration["workspace"]) / "cache" / root.name / "regression"
    arguments = [
        "-q",
        *TEST_FILES,
        "-o",
        f"cache_dir={scratch / 'pytest'}",
        "--basetemp",
        str(scratch / "tmp"),
        "--junitxml",
        str(directory / "pytest.xml"),
    ]
    u.write(
        directory / "command.json",
        dict(argv=[sys.executable, "-B", "-m", "pytest", *arguments], cwd=str(u.ROOT)),
    )
    os.chdir(u.ROOT)
    u.need(pytest.main(arguments) == 0, "Refinement regression failed")
    suites = ET.parse(directory / "pytest.xml").getroot().findall("testsuite")
    u.need(
        suites
        and all(int(s.get(k, 0)) == 0 for s in suites for k in ("errors", "failures", "skipped")),
        "Refinement regression failed",
    )
    return dict(status="regressions_passed", tests=sum(int(s.get("tests")) for s in suites))
