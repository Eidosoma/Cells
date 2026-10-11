"""Fresh-process contract probes stop at real worker startup, before any model step."""

import argparse
import copy
import os
import subprocess
import sys
import time
import traceback
import warnings
from pathlib import Path

import runtime_context as ctx

c, t = ctx.c, ctx.t
MODES = ("registered", "explicit_false", "empty_xla", "disabled_jit", "wrong_package")
SCOPE = {
    "real_cells_worker_entered": True,
    "runtime_check_modified": False,
    "transport_executed": False,
    "native_simulator_run": False,
    "production_integrator_run": False,
    "gpu_tested": False,
}


def validate_observation(row, registration, mode, missing_input):
    c.require(mode in MODES and row["mode"] == mode, "Wrong startup probe")
    c.require(row["scope"] == SCOPE and row["warnings"] == [], "Startup probe scope/warnings")
    c.require(
        row["amendment_sha256"] == c.sha(ctx.AMENDMENT)
        and row["script_sha256"] == c.sha(Path(__file__))
        and row["environment_provider_sha256"] == c.sha(ctx.HERE / "runtime_context.py")
        and row["previous_registration_sha256"] == ctx.REGISTRATION_SHA,
        "Startup probe source identity changed",
    )
    c.require(
        Path(row["executable"]) == c.CELLS_PYTHON
        and Path(row["cells_package_path"]) == c.ROOT / "src/cells/__init__.py"
        and row["cpu_affinity"] == registration["protocol"]["resources"]["cpu_affinity"],
        "Wrong startup interpreter/source/CPUs",
    )
    expected_sources = {
        name.removeprefix("src/cells/"): digest
        for name, digest in registration["sources_sha256"].items()
        if name.startswith("src/cells/") and name.endswith(".py")
    }
    c.require(row["loaded_production_sha256"] == expected_sources, "Loaded production changed")
    expected_runtime = copy.deepcopy(registration["cells_runtime"])
    if mode == "explicit_false":
        expected_runtime["numerical_environment"]["JAX_DISABLE_JIT"] = "false"
    elif mode == "empty_xla":
        expected_runtime["numerical_environment"]["XLA_FLAGS"] = ""
    elif mode == "disabled_jit":
        expected_runtime["numerical_environment"]["JAX_DISABLE_JIT"] = "true"
    c.require(row["observed_runtime"] == expected_runtime, "Unexpected actual startup runtime")
    expected_input = copy.deepcopy(registration["cells_runtime"])
    if mode == "wrong_package":
        expected_input["packages"]["numpy"] = "deliberately-mismatched-test-version"
    c.require(row["requested_runtime"] == expected_input, "Wrong negative-control registration")
    c.require(
        row["device"] == "cpu"
        and row["x64_enabled"] is True
        and row["jit_disabled"] is (mode == "disabled_jit"),
        "Unexpected actual JAX startup configuration",
    )
    error = row["exception"]
    worker = str(ctx.setup.OLD / "transport_workers.py")
    c.require(
        any(
            frame["path"] == worker and frame["function"] == "cells_worker"
            for frame in error["frames"]
        ),
        "Actual frozen worker was not entered",
    )
    if mode == "registered":
        c.require(
            error["type"] == "FileNotFoundError"
            and error["filename"] == str(missing_input / "betse.json"),
            "Corrected worker did not reach native-input read",
        )
    else:
        message = (
            "Require CPU float64 with JIT enabled"
            if mode == "disabled_jit"
            else "Accepted Cells runtime differs"
        )
        c.require(
            error["type"] == "ValueError" and error["message"] == message,
            "Negative runtime control was not rejected at the expected guard",
        )
    c.require(
        isinstance(row["elapsed_seconds"], (int, float))
        and 0 < row["elapsed_seconds"] < c.read(ctx.AMENDMENT)["startup_probe_timeout_seconds"],
        "Startup probe resource bound exceeded",
    )


def probe(mode, packet):
    began = time.monotonic()
    registration = c.read(ctx.FAILED / "registration.json")
    c.require(c.sha(ctx.FAILED / "registration.json") == ctx.REGISTRATION_SHA, "Wrong registration")
    missing_input = packet / "empty-input"
    c.require(missing_input.is_dir() and not any(missing_input.iterdir()), "Probe input not empty")
    requested = copy.deepcopy(registration)
    if mode == "wrong_package":
        requested["cells_runtime"]["packages"]["numpy"] = "deliberately-mismatched-test-version"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        import jax
        from transport_workers import cells_worker

        import cells
        from cells.io import runtime_identity, source_hashes

        try:
            cells_worker(requested, missing_input)
        except (FileNotFoundError, ValueError) as error:
            observed_error = {
                "type": type(error).__name__,
                "message": str(error),
                "filename": getattr(error, "filename", None),
                "frames": [
                    {"path": frame.filename, "function": frame.name, "line": frame.lineno}
                    for frame in traceback.extract_tb(error.__traceback__)
                ],
            }
        else:
            raise AssertionError("Worker unexpectedly completed without native input")
        row = {
            "mode": mode,
            "scope": SCOPE,
            "amendment_sha256": c.sha(ctx.AMENDMENT),
            "script_sha256": c.sha(Path(__file__)),
            "environment_provider_sha256": c.sha(ctx.HERE / "runtime_context.py"),
            "previous_registration_sha256": ctx.REGISTRATION_SHA,
            "executable": sys.executable,
            "cells_package_path": str(Path(cells.__file__).resolve()),
            "cpu_affinity": sorted(os.sched_getaffinity(0)),
            "loaded_production_sha256": source_hashes(),
            "observed_runtime": runtime_identity(),
            "requested_runtime": requested["cells_runtime"],
            "device": jax.default_backend(),
            "x64_enabled": bool(jax.config.x64_enabled),
            "jit_disabled": bool(jax.config.jax_disable_jit),
            "exception": observed_error,
            "elapsed_seconds": time.monotonic() - began,
        }
    row["warnings"] = [{"category": w.category.__name__, "message": str(w.message)} for w in caught]
    c.write(packet / mode / "result.json", row)
    validate_observation(row, registration, mode, missing_input)


def capture(packet):
    registration = ctx.authenticate_preservation()
    ctx.validate_amendment(c.read(ctx.AMENDMENT))
    packet.mkdir(parents=True, exist_ok=False)
    (packet / "empty-input").mkdir()
    began = time.monotonic()
    amendment = c.read(ctx.AMENDMENT)
    try:
        rows = {}
        for mode in MODES:
            directory = packet / mode
            directory.mkdir()
            inherited = os.environ | {
                "JAX_DISABLE_JIT": "true",
                "XLA_FLAGS": "--unregistered-probe-value-must-be-removed",
                "PYTHONPATH": "/unregistered/probe/import/path",
            }
            env = ctx.worker_environment(registration, packet, inherited)
            if mode == "explicit_false":
                env["JAX_DISABLE_JIT"] = "false"
            elif mode == "empty_xla":
                env["XLA_FLAGS"] = ""
            elif mode == "disabled_jit":
                env["JAX_DISABLE_JIT"] = "true"
            remaining = amendment["startup_contract_timeout_seconds"] - (time.monotonic() - began)
            c.require(remaining > 0, "Worker startup contract deadline exceeded")
            with (directory / "stdout.log").open("x") as log:
                subprocess.run(
                    [
                        "taskset",
                        "-c",
                        ",".join(map(str, registration["protocol"]["resources"]["cpu_affinity"])),
                        str(c.CELLS_PYTHON),
                        "-B",
                        str(Path(__file__).resolve()),
                        "probe",
                        mode,
                        str(packet),
                    ],
                    cwd=c.ROOT,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                    timeout=min(remaining, amendment["startup_probe_timeout_seconds"]),
                )
            row = c.read(directory / "result.json")
            validate_observation(row, registration, mode, packet / "empty-input")
            rows[mode] = c.sha(directory / "result.json")
        c.write(
            packet / "result.json",
            {
                "schema": "cells.betse_channel_worker_startup_contract@1",
                "status": "pass",
                "scope": SCOPE,
                "rows_sha256": rows,
                "amendment_sha256": c.sha(ctx.AMENDMENT),
                "previous_registration_sha256": ctx.REGISTRATION_SHA,
                "elapsed_seconds": time.monotonic() - began,
                "automatic_retry": False,
            },
        )
        validate_packet(packet, registration)
    except BaseException:
        c.write(
            packet / "failure.json",
            {
                "status": "startup_contract_failed",
                "traceback": traceback.format_exc(),
                "automatic_retry": False,
            },
        )
        raise
    return packet


def validate_packet(packet, registration):
    expected = {"result.json"} | {
        f"{mode}/{name}" for mode in MODES for name in ("stdout.log", "result.json")
    }
    c.require(set(ctx.setup.packet_hashes(packet)) == expected, "Startup packet membership changed")
    result = c.read(packet / "result.json")
    c.require(
        result["schema"] == "cells.betse_channel_worker_startup_contract@1"
        and result["status"] == "pass"
        and result["scope"] == SCOPE
        and result["automatic_retry"] is False,
        "Worker startup contract did not pass",
    )
    c.require(
        result["amendment_sha256"] == c.sha(ctx.AMENDMENT)
        and result["previous_registration_sha256"] == ctx.REGISTRATION_SHA
        and set(result["rows_sha256"]) == set(MODES),
        "Wrong worker startup contract identity/coverage",
    )
    c.require(
        0 < result["elapsed_seconds"] < c.read(ctx.AMENDMENT)["startup_contract_timeout_seconds"],
        "Worker startup contract exceeded time limit",
    )
    c.require(
        (packet / "empty-input").is_dir() and not any((packet / "empty-input").iterdir()),
        "Worker startup probe consumed unexpected input",
    )
    for mode in MODES:
        path = packet / mode / "result.json"
        c.require(result["rows_sha256"][mode] == c.sha(path), "Startup result bytes changed")
        validate_observation(c.read(path), registration, mode, packet / "empty-input")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("capture").add_argument("packet", type=Path)
    child = sub.add_parser("probe")
    child.add_argument("mode", choices=MODES)
    child.add_argument("packet", type=Path)
    args = parser.parse_args()
    if args.action == "capture":
        print(capture(args.packet.resolve()))
    else:
        probe(args.mode, args.packet.resolve())
