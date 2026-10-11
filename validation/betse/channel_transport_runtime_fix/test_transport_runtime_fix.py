"""Real frozen-worker startup, unchanged numerical boundary and strict provenance guards."""

import ast
import copy
import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ctx = importlib.import_module("runtime_context")
job = importlib.import_module("runtime_job")
startup = importlib.import_module("startup_contract")
c, t = ctx.c, ctx.t


@pytest.fixture(scope="module")
def previous():
    return ctx.authenticate_preservation()


def test_registered_absence_removes_inherited_flags_without_changing_parent(previous, tmp_path):
    inherited = {
        "XLA_FLAGS": "unregistered",
        "JAX_DISABLE_JIT": "true",
        "PYTHONPATH": "/unregistered",
        "JAX_PLATFORMS": "cuda",
        "JAX_ENABLE_X64": "false",
        "OMP_NUM_THREADS": "8",
        "PATH": "/retained/system/path",
    }
    original = copy.deepcopy(inherited)
    result = ctx.worker_environment(previous, tmp_path, inherited)
    assert inherited == original
    assert {name: result.get(name) for name in ctx.NUMERICAL_NAMES} == dict.fromkeys(
        ctx.NUMERICAL_NAMES
    )
    assert "PYTHONPATH" not in result
    assert result["PATH"] == inherited["PATH"]
    assert result["JAX_PLATFORMS"] == "cpu" and result["JAX_ENABLE_X64"] == "true"
    assert result["OMP_NUM_THREADS"] == "1" and result["PYTHONNOUSERSITE"] == "1"
    assert result["MPLCONFIGDIR"] == str(tmp_path / "matplotlib-cache")


@pytest.mark.parametrize(
    "name,value", [("JAX_DISABLE_JIT", "false"), ("JAX_DISABLE_JIT", "0"), ("XLA_FLAGS", "")]
)
def test_explicit_registered_strings_are_not_normalized(previous, tmp_path, name, value):
    alternate = copy.deepcopy(previous)
    alternate["cells_runtime"]["numerical_environment"][name] = value
    result = ctx.worker_environment(alternate, tmp_path, {})
    assert name in result and result[name] == value
    # This helper implements serialization, not authority to amend the accepted runtime.
    assert previous["cells_runtime"]["numerical_environment"][name] is None


@pytest.mark.parametrize(
    "numerical",
    [
        {},
        {"XLA_FLAGS": None},
        {"XLA_FLAGS": None, "JAX_DISABLE_JIT": False},
        {"XLA_FLAGS": 0, "JAX_DISABLE_JIT": None},
        {"XLA_FLAGS": None, "JAX_DISABLE_JIT": None, "extra": None},
    ],
)
def test_incomplete_or_untyped_runtime_environment_rejected(previous, tmp_path, numerical):
    changed = copy.deepcopy(previous)
    changed["cells_runtime"]["numerical_environment"] = numerical
    with pytest.raises(ValueError, match="Invalid registered"):
        ctx.worker_environment(changed, tmp_path, {})


@pytest.mark.parametrize(
    "field,value",
    [
        ("decision", "D090"),
        ("failure_sha256", "changed"),
        ("previous_registration_sha256", "changed"),
        ("cells_log_sha256", "changed"),
        ("base_protocol_sha256", "changed"),
        ("registered_numerical_environment", {}),
        ("strict_runtime_check_changed", True),
        ("numerical_protocol_changed", True),
        ("automatic_retry", True),
        ("automatic_followup", True),
        ("extra", True),
    ],
)
def test_unregistered_amendment_rejected(field, value):
    changed = copy.deepcopy(c.read(ctx.AMENDMENT))
    changed[field] = value
    with pytest.raises(ValueError, match="Unregistered"):
        ctx.validate_amendment(changed)


def function_ast(path, name):
    return next(
        node
        for node in ast.parse(path.read_text()).body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def test_execution_body_only_changes_environment_and_provenance():
    old = function_ast(ctx.PREVIOUS / "setup_job.py", "execute")
    new = function_ast(HERE / "runtime_job.py", "execute")
    old_try = next(node for node in old.body if isinstance(node, ast.Try))
    new_try = next(node for node in new.body if isinstance(node, ast.Try))
    index = next(
        i
        for i, node in enumerate(old_try.body)
        if isinstance(node, ast.Assign)
        and any(isinstance(x, ast.Name) and x.id == "env" for x in node.targets)
    )
    replacement = ast.parse("env = ctx.worker_environment(r, output)").body[0]
    assert isinstance(old_try.body[index + 1], ast.Expr)
    assert ast.unparse(old_try.body[index + 1]) == "env.pop('PYTHONPATH', None)"
    old_try.body[index : index + 2] = [replacement]
    for node in ast.walk(new):
        if (
            isinstance(node, ast.Constant)
            and node.value == "cells.betse_channel_transport_preflight_capture@3"
        ):
            node.value = "cells.betse_channel_transport_preflight_capture@2"
        if isinstance(node, ast.Dict):
            kept = [
                (key, value)
                for key, value in zip(node.keys, node.values, strict=True)
                if not (
                    isinstance(key, ast.Constant)
                    and key.value in {"runtime_amendment", "runtime_failure_preservation_sha256"}
                )
            ]
            node.keys, node.values = [x[0] for x in kept], [x[1] for x in kept]
    assert ast.dump(old, include_attributes=False) == ast.dump(new, include_attributes=False)
    assert (
        sum(
            isinstance(node, ast.Assign)
            and ast.dump(node, include_attributes=False)
            == ast.dump(replacement, include_attributes=False)
            for node in new_try.body
        )
        == 1
    )


def test_numeric_workers_and_comparison_reused_without_changes(previous):
    imports = {
        (node.module, alias.name)
        for node in ast.walk(ast.parse((HERE / "runtime_job.py").read_text()))
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert {
        ("native_setup_fix", "native_worker"),
        ("transport_workers", "cells_worker"),
        ("transport_check", "evaluate"),
    } <= imports
    for relative, digest in previous["sources_sha256"].items():
        assert c.sha(c.ROOT / relative) == digest
    assert len(previous["sources_sha256"]) == 70
    assert len(job.source_hashes()) == 76


def test_both_failures_and_original_resources_are_preserved(previous):
    saved = c.read(ctx.PRESERVED)
    assert saved["files_sha256"] == ctx.setup.packet_hashes(ctx.FAILED)
    assert saved["earlier_failure_preservation_sha256"] == c.sha(ctx.setup.PRESERVED)
    assert saved["native_single_update_cases_executed"] == 12
    assert saved["cells_transfers_executed"] == 0 and not saved["previous_capture_qualified"]
    assert not saved["simulators_rerun"]
    assert previous["protocol"] == c.read(t.PROTOCOL)
    assert previous["protocol"]["resources"]["total_timeout_seconds"] == 300
    assert previous["protocol"]["resources"]["max_artifact_bytes"] == 128 * 1024**2
    assert len(t.case_ids(previous["protocol"])) == 12


@pytest.fixture(scope="module")
def actual_startup(tmp_path_factory):
    configured = os.environ.get("CELLS_REF004B_STARTUP_OUTPUT")
    packet = (
        Path(configured).resolve()
        if configured
        else tmp_path_factory.mktemp("startup-parent") / "packet"
    )
    if configured:
        c.require(
            packet.is_relative_to(c.ROOT / "reports") and packet != c.ROOT / "reports",
            "Use a fresh reports packet",
        )
    startup.capture(packet)
    return packet


@pytest.mark.parametrize("mode", startup.MODES)
def test_actual_frozen_worker_startup_controls(actual_startup, previous, mode):
    row = c.read(actual_startup / mode / "result.json")
    startup.validate_observation(row, previous, mode, actual_startup / "empty-input")
    assert row["scope"]["real_cells_worker_entered"]
    assert not row["scope"]["transport_executed"]
    assert len(row["loaded_production_sha256"]) == 51
    assert row["observed_runtime"]["packages"] == previous["cells_runtime"]["packages"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("observed_runtime", {}),
        ("scope", {"transport_executed": True}),
        ("warnings", [{"message": "unexpected"}]),
        ("device", "gpu"),
        ("jit_disabled", True),
        ("x64_enabled", False),
        ("cpu_affinity", [0]),
        ("loaded_production_sha256", {}),
        ("requested_runtime", {}),
        ("elapsed_seconds", 30),
        ("exception", {"frames": []}),
    ],
)
def test_fabricated_startup_claims_rejected(actual_startup, previous, field, value):
    row = copy.deepcopy(c.read(actual_startup / "registered/result.json"))
    row[field] = value
    with pytest.raises(ValueError):
        startup.validate_observation(row, previous, "registered", actual_startup / "empty-input")


def test_actual_startup_packet_complete_without_any_transport(actual_startup, previous):
    startup.validate_packet(actual_startup, previous)
    assert len(ctx.setup.packet_hashes(actual_startup)) == 11
    assert not any((actual_startup / "empty-input").iterdir())
    result = c.read(actual_startup / "result.json")
    assert result["status"] == "pass" and not result["automatic_retry"]


def test_guard_rejection_is_not_mistaken_for_corrected_startup(actual_startup, previous):
    row = copy.deepcopy(c.read(actual_startup / "registered/result.json"))
    row["exception"] = c.read(actual_startup / "explicit_false/result.json")["exception"]
    with pytest.raises(ValueError, match="did not reach"):
        startup.validate_observation(row, previous, "registered", actual_startup / "empty-input")


def test_missing_model_input_is_not_accepted_as_a_negative_guard(actual_startup, previous):
    row = copy.deepcopy(c.read(actual_startup / "explicit_false/result.json"))
    row["exception"] = c.read(actual_startup / "registered/result.json")["exception"]
    with pytest.raises(ValueError, match="Negative runtime control"):
        startup.validate_observation(
            row, previous, "explicit_false", actual_startup / "empty-input"
        )


def test_register_rejects_existing_or_outside_directory(tmp_path):
    with pytest.raises(ValueError, match="fresh run"):
        job.register(tmp_path, tmp_path / "tests.xml", tmp_path / "startup")


def test_job_and_context_import_without_models():
    program = (
        f"import sys; sys.path.insert(0, {str(HERE)!r}); import runtime_context, runtime_job; "
        "assert not any(n.split('.')[0] in {'cells','betse','numpy','jax','jaxlib'} "
        "for n in sys.modules)"
    )
    subprocess.run([sys.executable, "-B", "-c", program], check=True, timeout=5)


def test_unregistered_execute_records_failure_without_starting_workers(tmp_path):
    result = subprocess.run(
        [sys.executable, "-B", str(HERE / "runtime_job.py"), "execute", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode != 0
    failure = c.read(tmp_path / "failure.json")
    assert failure["status"] == "failed_not_qualified" and not failure["automatic_retry"]
    assert not (tmp_path / "betse.log").exists() and not (tmp_path / "completion.json").exists()
