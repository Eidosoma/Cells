"""Exact worker environments and immutable evidence for the D091 launcher correction."""

import importlib
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / "channel_transport_setup_fix"
sys.path.insert(0, str(PREVIOUS))
setup = importlib.import_module("setup_context")
previous_job = importlib.import_module("setup_job")
c, t = setup.c, setup.t
AMENDMENT = HERE / "amendment.json"
FAILED = c.ROOT / "runs/ref-004b-setup-fix-2026-09-14/capture-01"
PRESERVED = c.ROOT / "reports/ref-004b-runtime-fix-preservation.json"
FAILURE_SHA = "1b2f3624233860fa9d3d9e720a388fa6fe3995d5dcef936bdec02eadbb94fd50"
REGISTRATION_SHA = "7b10286e2994965847fbf700ea8e5e33078a224391fd5062f62b6df63fe631e8"
LOG_SHA = "ce22ba21543f16318b7946b2620c6fe81a729fbdbe8e115906d9e173554d0f42"
NUMERICAL_NAMES = ("XLA_FLAGS", "JAX_DISABLE_JIT")


def worker_environment(registration, output, inherited=None):
    """Apply the exact registered strings/absences; never normalize runtime identity."""
    numerical = registration["cells_runtime"]["numerical_environment"]
    c.require(
        set(numerical) == set(NUMERICAL_NAMES)
        and all(value is None or isinstance(value, str) for value in numerical.values()),
        "Invalid registered numerical environment",
    )
    env = dict(os.environ if inherited is None else inherited) | {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "MPLBACKEND": "Agg",
        "MPLCONFIGDIR": str(output / "matplotlib-cache"),
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "JAX_PLATFORMS": "cpu",
        "JAX_ENABLE_X64": "true",
    }
    env.pop("PYTHONPATH", None)
    for name, value in numerical.items():
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    return env


def validate_amendment(amendment):
    c.require(amendment == c.read(AMENDMENT), "Unregistered runtime amendment")
    c.require(
        amendment["failure_sha256"] == FAILURE_SHA
        and amendment["previous_registration_sha256"] == REGISTRATION_SHA
        and amendment["cells_log_sha256"] == LOG_SHA,
        "Wrong runtime failure",
    )
    c.require(c.sha(t.PROTOCOL) == amendment["base_protocol_sha256"], "Numerical protocol changed")
    c.require(
        amendment["registered_numerical_environment"] == dict.fromkeys(NUMERICAL_NAMES),
        "Accepted numerical environment changed",
    )


def authenticate_previous():
    """Read/hash only; native results were executed but never numerically qualified."""
    for name, digest in (
        ("registration.json", REGISTRATION_SHA),
        ("failure.json", FAILURE_SHA),
        ("cells.log", LOG_SHA),
    ):
        c.require(c.sha(FAILED / name) == digest, f"Previous failure evidence changed: {name}")
    previous = previous_job.authenticate(FAILED)
    c.require(
        previous["cells_runtime"]["numerical_environment"] == dict.fromkeys(NUMERICAL_NAMES),
        "Previous registered runtime changed",
    )
    c.require(
        c.read(FAILED / "failure.json")["status"] == "failed_not_qualified",
        "Previous failure reclassified",
    )
    c.require(
        "ValueError: Accepted Cells runtime differs" in (FAILED / "cells.log").read_text(),
        "Wrong worker failure boundary",
    )
    native = c.read(FAILED / "betse.json")
    c.require(
        native["engine"] == "unmodified_betse_native_channel_single_transfer"
        and set(native["rows"]) == set(t.case_ids(previous["protocol"]))
        and native["registration_sha256"] == REGISTRATION_SHA
        and not native["full_trajectory_run"],
        "Previous native execution inventory changed",
    )
    c.require(
        not any(
            (FAILED / name).exists()
            for name in (
                "cells.json",
                "cells_definitions.json",
                "comparison.json",
                "completion.json",
            )
        ),
        "Unexpected comparison after runtime rejection",
    )
    return previous


def preserve():
    validate_amendment(c.read(AMENDMENT))
    previous = authenticate_previous()
    c.require(c.inspect_source() == previous["upstream"], "Native checkout changed")
    files = setup.packet_hashes(FAILED)
    c.write(
        PRESERVED,
        {
            "schema": "cells.betse_channel_runtime_failure_preservation@1",
            "status": "preserved",
            "created_utc": datetime.now(UTC).isoformat(),
            "failure_path": str(FAILED.relative_to(c.ROOT)),
            "failure_sha256": FAILURE_SHA,
            "registration_sha256": REGISTRATION_SHA,
            "files_sha256": files,
            "artifact_bytes": sum((FAILED / name).stat().st_size for name in files),
            "previous_sources_sha256": previous["sources_sha256"],
            "earlier_failure_preservation_sha256": c.sha(setup.PRESERVED),
            "historical_reports_sha256": {
                name: c.sha(c.ROOT / name)
                for name in (
                    "reports/REF004B_SETUP_FIX_HANDOFF.md",
                    "reports/ref-004b-setup-fix-checks-01.xml",
                )
            },
            "native_single_update_cases_executed": 12,
            "cells_transfers_executed": 0,
            "previous_capture_qualified": False,
            "simulators_rerun": False,
        },
    )
    return {"status": "preserved", "failure_files": len(files), "receipt": str(PRESERVED)}


def authenticate_preservation():
    previous = authenticate_previous()
    saved = c.read(PRESERVED)
    c.require(
        saved["status"] == "preserved" and saved["files_sha256"] == setup.packet_hashes(FAILED),
        "Runtime failure packet bytes or membership changed",
    )
    c.require(
        saved["previous_sources_sha256"] == previous["sources_sha256"]
        and saved["earlier_failure_preservation_sha256"] == c.sha(setup.PRESERVED),
        "Earlier failure/source preservation changed",
    )
    for name, digest in saved["historical_reports_sha256"].items():
        c.require(c.sha(c.ROOT / name) == digest, f"Historical report changed: {name}")
    return previous
