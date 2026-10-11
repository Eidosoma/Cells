"""D128: fixed output ownership, preserved failures and unchanged native reuse."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "live_recording_resume"))
import resume_context as reuse  # noqa: E402
import resume_job as previous  # noqa: E402
from resume_context import ctx, original  # noqa: E402

STOPPED = ctx.ROOT / "runs/ref-005d-live-continuation-2026-09-17/continuation-01"
STOPPED_IDENTITIES = {
    "registration.json": "0c06e8390acf07e0fbea47ebd2dd9a5d9dfbb63986f6534838d38fdcc735604b",
    "failure.json": "7cd3c3d8cc4aa18b0ea6740adaf020b333fbc5619ff7c40d877bdd6c2e3ea070",
    "cells-failure.json": "9e94cc43a83ca03eb90345afc23d28bdcdc20eef26c135db6d42b4d55ee0bb40",
}
PROBE_KEY = "pump_leak/dt_2.5e-05/jax_jit"
LAYOUT_VERSION = "cells.matched_window_outputs@2"
LAYOUT = {
    "baseline": "baseline",
    "recording_full": "recordings/full",
    "recording_observations": "recordings/observations",
    "recording_checkpoints": "recordings/checkpoints",
    "resumed": "resumed",
}
COUNTS = {
    "probe": dict(
        full_trajectories=1,
        window_runs=3,
        disk_recordings=3,
        restart_suffixes=1,
        restart_window_runs=1,
        zero_length_runs=1,
        sparse_schedule_controls=0,
    ),
    "matrix": dict(
        full_trajectories=24,
        window_runs=72,
        disk_recordings=18,
        restart_suffixes=6,
        restart_window_runs=6,
        zero_length_runs=6,
        sparse_schedule_controls=2,
    ),
}
STATUS = {
    "probe": "matched_window_output_probe_pass",
    "matrix": "matched_windows_pass_pending_independent_review",
}
PHASE_TIMEOUTS = {"probe": 120, "matrix": ctx.BOUNDS["cells_timeout_seconds"]}


def selected_keys(registration, phase):
    expected = sorted(ctx.read(ctx.LEGACY / "cells.json")["records"])
    ctx.need(phase in COUNTS and registration["cells_keys"] == expected, "Cells selection changed")
    return [PROBE_KEY] if phase == "probe" else expected


def case_paths(output, key):
    """Every producer owns a fresh, disjoint leaf; check before running any model."""
    directory = ctx.path_for(output, "cells/" + key)
    ctx.need(not directory.exists(), "Case output already exists")
    paths = {name: ctx.path_for(directory, relative) for name, relative in LAYOUT.items()}
    values = list(paths.values())
    ctx.need(
        len(values) == len(set(values))
        and all(not a.is_relative_to(b) for a in values for b in values if a != b),
        "Output roles overlap",
    )
    ctx.need(all(not p.exists() for p in values), "Output role already exists")
    return dict(directory=directory, **paths)


def gate(phase, result, registration):
    keys = selected_keys(registration, phase)
    ctx.need(
        result["status"] == STATUS[phase]
        and result["output_layout_version"] == LAYOUT_VERSION
        and sorted(result["records"]) == keys
        and result["production_changed"] is False,
        "Output qualification scope changed",
    )
    for name, expected in COUNTS[phase].items():
        ctx.need(result[name] == expected, "Output qualification count: " + name)
    ctx.need(len(result["records"]) == result["full_trajectories"], "Full trajectory coverage")
    for field, total in (
        ("windows", "window_runs"),
        ("recordings", "disk_recordings"),
        ("restarts", "restart_suffixes"),
        ("restart_windows", "restart_window_runs"),
        ("zero_length", "zero_length_runs"),
        ("sparse", "sparse_schedule_controls"),
    ):
        ctx.need(
            sum(row[field] for row in result["records"].values()) == result[total], "Row coverage"
        )
    for key, row in result["records"].items():
        checkpoint_case = key.endswith("/dt_2.5e-05/jax_jit")
        sparse_case = key.startswith("pump_leak/dt_5e-05/")
        ctx.need(
            row["directory"] == "cells/" + key
            and row["windows"] == 3
            and row["recordings"] == (3 if checkpoint_case else 0)
            and row["restarts"]
            == row["restart_windows"]
            == row["zero_length"]
            == int(checkpoint_case)
            and row["sparse"] == int(sparse_case)
            and row["baseline_preserved"] is True,
            "Per-case output coverage",
        )
    if phase == "matrix":
        original.gate("cells", result, registration)


def prerequisites():
    """Authenticate both stopped attempts; never promote/reuse partial Cells results."""
    ctx.hashes(STOPPED, STOPPED_IDENTITIES)
    stopped = previous.authenticate(STOPPED, STOPPED_IDENTITIES["registration.json"])
    ctx.need(
        not (STOPPED / "completion.json").exists()
        and ctx.read(STOPPED / "launch.json")["registration_sha256"]
        == STOPPED_IDENTITIES["registration.json"],
        "Stopped continuation changed",
    )
    files = ctx.inventory(STOPPED)
    ctx.need(len(files) == 24, "Stopped continuation inventory")
    native = ctx.read(STOPPED / "native-reuse.json")
    ctx.need(
        {k: v for k, v in native.items() if k != "status"} == stopped["reused_native"],
        "Stopped native reuse changed",
    )
    prior = ctx.prerequisite()
    ctx.need(prior == stopped["prior"], "Accepted prerequisite changed")
    return dict(
        accepted=prior,
        reused_native=stopped["reused_native"],
        stopped_continuation=dict(
            directory=str(STOPPED.relative_to(ctx.ROOT)),
            identities=STOPPED_IDENTITIES,
            files_sha256=files,
        ),
        partial_cells_reused=False,
    )


def sources():
    names = set(reuse.sources())
    names.update(str(p.relative_to(ctx.ROOT)) for p in HERE.iterdir() if p.suffix in (".py", ".md"))
    names.add("reports/REF005D_OUTPUT_LAYOUT_HANDOFF.md")
    return {name: ctx.sha(ctx.ROOT / name) for name in sorted(names)}


def authenticate_prior(saved):
    ctx.hashes(STOPPED, STOPPED_IDENTITIES)
    stopped = previous.authenticate(STOPPED, STOPPED_IDENTITIES["registration.json"])
    ctx.need(
        saved["stopped_continuation"]["directory"] == str(STOPPED.relative_to(ctx.ROOT))
        and saved["stopped_continuation"]["identities"] == STOPPED_IDENTITIES
        and ctx.inventory(STOPPED) == saved["stopped_continuation"]["files_sha256"]
        and stopped["reused_native"] == saved["reused_native"]
        and stopped["prior"] == saved["accepted"]
        and saved["partial_cells_reused"] is False,
        "Preserved prerequisite packet changed",
    )
