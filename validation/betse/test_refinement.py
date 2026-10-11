"""Preserved failure, versioned inputs, overlap rejection and detached-harness preflights."""

import copy
import hashlib
import json
import shutil
import struct
import subprocess
from types import SimpleNamespace

import contact as c
import pytest
import test_native_observer as observer_tests
import test_trajectory as original_tests
import trajectory_check as arithmetic
import trajectory_context as original
import trajectory_failure as prior
import trajectory_refinement as driver
import trajectory_refinement_check as checker
import trajectory_refinement_context as ctx


@pytest.fixture(scope="module")
def registration(tmp_path_factory):
    output = tmp_path_factory.mktemp("refinement") / "registered"
    value = driver.register(output)
    return output, value, c.read(prior.SESSION / "registration.json")


def replace_json(path, value):
    # Only temporary pytest-owned copies are edited, never the retained originals.
    path.unlink()
    c.write(path, value)


def test_protocol_changes_only_the_native_ladder_and_declared_storage():
    old, new = c.read(original.PROTOCOL), c.read(ctx.PROTOCOL)
    ctx.validate_protocol(new)
    assert {name for name in new if new[name] != old[name]} == set(ctx.AMENDMENT)
    assert [round(new["duration_s"] / dt) for dt in new["native_steps_s"]] == [40, 80, 160]
    assert new["worker_timeout_seconds"] == 90 and new["total_timeout_seconds"] == 180
    assert new["max_artifact_bytes"] == 128 * 1024**2


@pytest.mark.parametrize(
    "change",
    [
        "horizon",
        "case",
        "native_steps",
        "cells_steps",
        "constants",
        "observations",
        "instantaneous",
        "trajectory",
        "cumulative",
        "contraction",
        "timeout",
        "cpu",
    ],
)
def test_undeclared_protocol_change_rejected(change):
    value = c.read(ctx.PROTOCOL)
    if change == "horizon":
        value["duration_s"] *= 2
    elif change == "case":
        value["cases"][0]["availability"] = 0.5
    elif change == "native_steps":
        value["native_steps_s"][-1] *= 2
    elif change == "cells_steps":
        value["cells_steps_s"][-1] /= 2
    elif change == "constants":
        value["native_constant_profiles"].pop()
    elif change == "observations":
        value["common_times_s"].pop()
    elif change in ("instantaneous", "trajectory"):
        value[change + "_tolerances"]["amount_fmol"] *= 2
    elif change == "cumulative":
        value["cumulative_amount_atol_fmol"] *= 2
    elif change == "contraction":
        value["refinement"]["native_contraction_max"] = 1
    elif change == "timeout":
        value["worker_timeout_seconds"] *= 2
    else:
        value["cpu_affinity"] = "0-7"
    with pytest.raises(ValueError, match="Undeclared"):
        ctx.validate_protocol(value)


@pytest.mark.parametrize("case", ["passive", "blocked"])
@pytest.mark.parametrize("dt", [0.000025, 0.0000125, 0.00000625])
def test_finer_steps_use_the_unchanged_native_yaml_mapping(case, dt):
    original_tests.test_native_input_changes_are_only_declared_timing_and_permeability(case, dt)


@pytest.mark.parametrize("count", [80, 160])
def test_observer_covers_finer_synthetic_loops_without_replacing_methods(count):
    observer_tests.test_real_function_boundaries_include_unsampled_first_step(count)


def test_registration_preserves_exact_cells_definitions_and_old_sources(registration):
    output, value, parent = registration
    assert value["cells_definitions"] == parent["cells_definitions"]
    assert len(value["cells_definitions"]) == 8
    assert all(value["sources"][name] == digest for name, digest in parent["sources"].items())
    assert value["sources"] == original.sources()
    assert not (output / "started.json").exists()
    with pytest.raises(FileExistsError):
        driver.register(output)


@pytest.mark.parametrize(
    "field",
    [
        "base_protocol",
        "geometry",
        "settings",
        "cells_runtime",
        "cells_definitions",
        "upstream",
        "amendment",
        "parent_registration_sha256",
        "failure_audit_sha256",
    ],
)
def test_registration_metadata_cannot_change_jointly(registration, monkeypatch, field):
    _, value, parent = registration
    monkeypatch.setattr(ctx, "authenticate", lambda: parent)
    altered = copy.deepcopy(value)
    altered[field] = {"changed": True}
    with pytest.raises(ValueError):
        ctx.validate_registration(altered)


def test_registered_source_change_rejected(registration, monkeypatch):
    _, value, parent = registration
    monkeypatch.setattr(ctx, "authenticate", lambda: parent)
    altered = copy.deepcopy(value)
    altered["sources"]["trajectory_refinement.py"] = "0" * 64
    with pytest.raises(ValueError, match="source changed"):
        ctx.validate_registration(altered)


def test_failed_packet_replays_without_importing_models_or_array_libraries():
    code = """
import importlib.abc
import json
import sys
class Fence(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'cells', 'betse', 'numpy', 'jax'}:
            raise AssertionError('Forbidden model/numerical import: ' + fullname)
sys.meta_path.insert(0, Fence())
import trajectory_failure as prior
result = prior.audit()
assert result == prior.c.read(prior.AUDIT)
print(json.dumps({key: result[key] for key in ('status', 'qualified', 'model_calls')}))
"""
    result = subprocess.run(
        [str(c.CELLS_PYTHON), "-B", "-c", code],
        cwd=c.HERE,
        check=True,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert json.loads(result.stdout) == {
        "status": "rejection_confirmed",
        "qualified": False,
        "model_calls": 0,
    }


def test_saved_endpoint_diagnostic_explains_aggregate_error_not_mass_loss():
    registered = prior.retained()
    result = prior.diagnostic(registered, prior.SESSION)
    assert result == c.read(prior.AUDIT)["independent_endpoint_diagnostic"]
    assert all(1 < order < 1.02 for order in result["observed_endpoint_orders"])
    fine = result["endpoints"][-1]
    assert max(map(abs, fine["bath_error_vs_cells_fmol"])) > 2e-7
    assert max(map(abs, fine["material_residual_fmol"])) < 1e-12
    assert max(abs(v) for row in fine["per_cell_errors_fmol"] for v in row) < 4e-8
    assert max(map(abs, result["extrapolated_endpoint_error_fmol"])) < 1e-9
    assert result["extrapolation_is_qualification"] is False


@pytest.mark.parametrize("change", ["false_pass", "missing_payload", "changed_payload"])
def test_original_failed_packet_is_immutable(tmp_path, change):
    output = tmp_path / "failed"
    shutil.copytree(prior.SESSION, output)
    if change == "false_pass":
        c.write(output / "verification.json", {"status": "pass"})
    else:
        path = output / "native/passive/matched_constants/0.00002500/observed/result.json"
        if change == "missing_payload":
            path.unlink()
        else:
            value = c.read(path)
            value["rho_channel"] = 2
            replace_json(path, value)
    with pytest.raises(ValueError):
        prior.retained(output)


@pytest.fixture
def overlap_packet(tmp_path):
    output = tmp_path / "overlap"
    output.mkdir()
    for name in ("betse.json", "cells.json"):
        shutil.copy2(prior.SESSION / name, output / name)
    paths = list(c.read(output / "cells.json")["results"].values())
    for key, pair in c.read(output / "betse.json")["results"].items():
        if key.endswith("/0.00002500"):
            paths.extend(pair.values())
    for name in paths:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(prior.SESSION / name, target)
    return output


def test_copied_old_overlap_is_byte_equal_without_new_simulation(overlap_packet):
    result = checker.overlap({"protocol": c.read(ctx.PROTOCOL)}, overlap_packet)
    assert result == {
        "native_runs_byte_equal": 8,
        "cells_runs_byte_equal": 8,
        "timings_compared": False,
    }


@pytest.mark.parametrize(
    "field",
    [
        "native_ordinary",
        "native_final",
        "native_trace",
        "cells_history",
        "cells_observations",
        "cells_diagnostics",
    ],
)
def test_rehashed_overlap_changes_are_rejected(overlap_packet, field):
    native = field.startswith("native_")
    path = overlap_packet / (
        "native/passive/matched_constants/0.00002500/observed/result.json"
        if native
        else "cells/passive/jax_jit/0.00005000/result.json"
    )
    value = c.read(path)
    if field == "native_trace":
        value["trace"]["steps"][0]["after_elapsed_s"] = 0
    elif field == "cells_diagnostics":
        value["diagnostics"][next(iter(value["diagnostics"]))] += 1
    else:
        array = {
            "native_ordinary": lambda: value["ordinary"]["vm_time"],
            "native_final": lambda: value["final"]["vm"],
            "cells_history": lambda: value["history"]["amount_increment"],
            "cells_observations": lambda: value["observations"]["voltage_V"],
        }[field]()
        row = array["values"]
        while isinstance(row[0], list):
            row = row[0]
        row[0] += 1
        array["bytes_sha256"] = hashlib.sha256(
            b"".join(struct.pack("<d", v) for v in arithmetic.numbers(array["values"]))
        ).hexdigest()
        arithmetic.unpack(array)  # the corruption is not merely a stale array digest
    replace_json(path, value)
    with pytest.raises(ValueError, match="Repeated"):
        checker.overlap({"protocol": c.read(ctx.PROTOCOL)}, overlap_packet)


@pytest.mark.parametrize("fail", [False, True])
def test_detached_launch_and_launch_failure_receipts(registration, tmp_path, monkeypatch, fail):
    source, value, _ = registration
    output = tmp_path / "launch"
    shutil.copytree(source, output)
    monkeypatch.setattr(driver, "register", lambda target: value)

    def fake_popen(command, **kwargs):
        assert (output / "registration.json").is_file() and (output / "sources.zip").is_file()
        assert command[:3] == ["taskset", "-c", "0-3"]
        assert command[-2:] == ["execute", str(output)]
        assert kwargs["start_new_session"] is True and kwargs["stdin"] == subprocess.DEVNULL
        if fail:
            raise OSError("synthetic launch failure")
        return SimpleNamespace(pid=123456)

    monkeypatch.setattr(driver.subprocess, "Popen", fake_popen)
    if fail:
        with pytest.raises(OSError):
            driver.launch(output)
        assert c.read(output / "failure.json")["stage"] == "launch"
        assert not (output / "launch.json").exists()
    else:
        driver.launch(output)
        assert c.read(output / "launch.json")["status"] == "launched_detached"
    assert not (output / "started.json").exists()


@pytest.mark.parametrize("error", ["timeout", "worker_failure"])
def test_worker_errors_are_retained_without_retry(registration, tmp_path, monkeypatch, error):
    source, _, _ = registration
    output = tmp_path / "worker-failure"
    shutil.copytree(source, output)
    monkeypatch.setattr(ctx, "validate_registration", lambda value: None)
    calls = []

    def fail(command, **kwargs):
        calls.append(command)
        assert kwargs["timeout"] <= 90
        assert kwargs["env"]["OPENBLAS_NUM_THREADS"] == "1"
        if error == "timeout":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(driver.subprocess, "run", fail)
    with pytest.raises(subprocess.SubprocessError):
        driver.execute(output)
    assert len(calls) == 1
    assert c.read(output / "failure.json")["status"] == "failed_not_qualified"
    assert not (output / "verification.json").exists()
