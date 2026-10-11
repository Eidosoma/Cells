"""Configuration correction tests; native YAML/type checking is not network preparation."""

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
setup = importlib.import_module("setup_context")
job = importlib.import_module("setup_job")
native = importlib.import_module("native_setup_fix")
c, t = setup.c, setup.t


@pytest.fixture(scope="module")
def original():
    return setup.authenticate_preservation()


@pytest.fixture(scope="module")
def template(original):
    result = {}
    for path, value in original["base_protocol"]["yaml_overrides"]:
        target = result
        for key in path[:-1]:
            target = target.setdefault(key, {})
        target[path[-1]] = value
    result["sim time settings"] = {}
    return result


@pytest.mark.parametrize("index", range(4))
def test_only_biomolecule_sequence_changes(original, template, tmp_path, index):
    p, base = original["protocol"], original["base_protocol"]
    variant = p["variants"][index]
    before = copy.deepcopy(template)
    old = t.configuration(template, base, p, variant, tmp_path)
    corrected = setup.configuration(template, base, p, variant, tmp_path)
    expected = copy.deepcopy(old)
    expected["general network"]["biomolecules"] = []
    assert corrected == expected and template == before
    assert old["general network"]["biomolecules"] is None
    assert type(corrected["general network"]["biomolecules"]) is list
    assert all(
        corrected["general network"][key] is None
        for key in ("reactions", "transporters", "modulators")
    )
    assert corrected["general network"]["channels"] == old["general network"]["channels"]


def function_ast(path, name):
    tree = ast.parse(path.read_text())
    return next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name
    )


def test_native_worker_only_changes_configuration_provider():
    previous = function_ast(setup.OLD / "transport_workers.py", "native_worker")
    current = function_ast(HERE / "native_setup_fix.py", "native_worker")
    replaced = 0
    for node in ast.walk(current):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "setup"
            and node.func.attr == "configuration"
        ):
            node.func.value.id = "t"
            replaced += 1
    assert replaced == 1
    assert ast.dump(previous, include_attributes=False) == ast.dump(
        current, include_attributes=False
    )


def test_cells_worker_and_comparator_are_reused_unmodified(original):
    for name in ("transport_workers.py", "transport_check.py", "transport_protocol.py"):
        path = setup.OLD / name
        assert c.sha(path) == original["sources_sha256"][str(path.relative_to(c.ROOT))]
    tree = ast.parse((HERE / "setup_job.py").read_text())
    imports = {
        (node.module, alias.name)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert ("transport_workers", "cells_worker") in imports
    assert ("transport_check", "evaluate") in imports
    assert ("native_setup_fix", "native_worker") in imports
    assert ("transport_workers", "native_worker") not in imports


@pytest.mark.parametrize(
    "field,value",
    [
        ("configuration_path", ["general network", "channels"]),
        ("original_value", []),
        ("corrected_value", None),
        ("corrected_value", [{}]),
        ("decision", "D089"),
        ("base_protocol_sha256", "different"),
        ("failure_sha256", "different"),
        ("original_registration_sha256", "different"),
        ("numerical_protocol_changed", True),
        ("automatic_retry", True),
        ("automatic_followup", True),
        ("extra", "unregistered"),
    ],
)
def test_amendment_mutations_rejected(field, value):
    changed = copy.deepcopy(c.read(setup.AMENDMENT))
    changed[field] = value
    with pytest.raises(ValueError, match="Unregistered"):
        setup.validate_amendment(changed)


def test_numerical_panel_resources_and_failure_are_preserved(original):
    assert original["protocol"] == c.read(t.PROTOCOL)
    assert original["protocol"]["resources"]["total_timeout_seconds"] == 300
    assert original["protocol"]["resources"]["max_artifact_bytes"] == 128 * 1024**2
    assert len(t.case_ids(original["protocol"])) == 12
    saved = c.read(setup.PRESERVED)
    assert len(saved["files_sha256"]) == 22
    assert saved["files_sha256"] == setup.packet_hashes(setup.FAILED)
    assert not saved["original_capture_qualified"] and not saved["simulators_rerun"]
    assert len(original["sources_sha256"]) == 63
    assert len(original["preserved_sources_sha256"]) == 393


@pytest.mark.parametrize("mutation", ["extra", "missing", "modified", "symlink"])
def test_failure_packet_membership_and_bytes_cannot_change(tmp_path, mutation):
    packet = tmp_path / "packet"
    packet.mkdir()
    path = packet / "a.json"
    c.write(path, {"old": True})
    original = setup.packet_hashes(packet)
    if mutation == "extra":
        c.write(packet / "b.json", {})
    elif mutation == "missing":
        path.rename(tmp_path / "retained.json")
    elif mutation == "modified":
        path.rename(tmp_path / "retained.json")
        c.write(path, {"old": False})
    else:
        (packet / "link.json").symlink_to(path)
        with pytest.raises(ValueError, match="Symlink"):
            setup.packet_hashes(packet)
        return
    assert setup.packet_hashes(packet) != original


@pytest.fixture(scope="module")
def native_contract(tmp_path_factory):
    configured = os.environ.get("CELLS_REF004B_CONTRACT_OUTPUT")
    packet = (
        Path(configured).resolve()
        if configured
        else tmp_path_factory.mktemp("contract-parent") / "packet"
    )
    if configured:
        c.require(
            packet.is_relative_to(c.ROOT / "reports") and packet != c.ROOT / "reports",
            "Contract evidence must use a fresh reports subdirectory",
        )
    packet.mkdir(exist_ok=False)
    data = packet / "data"
    data.mkdir()
    env = os.environ | {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "MPLBACKEND": "Agg",
        "MPLCONFIGDIR": str(packet / "matplotlib-cache"),
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    }
    env.pop("PYTHONPATH", None)
    try:
        with (packet / "stdout.log").open("x") as log:
            result = subprocess.run(
                [str(c.REFERENCE_PYTHON), "-B", str(HERE / "native_config_contract.py"), str(data)],
                env=env,
                cwd=c.ROOT,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=c.read(setup.AMENDMENT)["configuration_contract_timeout_seconds"],
            )
    except subprocess.TimeoutExpired:
        c.write(
            packet / "timeout.json",
            {"status": "configuration_contract_timeout", "automatic_retry": False},
        )
        raise
    assert result.returncode == 0, (packet / "stdout.log").read_text()[-6000:]
    return packet, c.read(data / "result.json")


@pytest.mark.parametrize("index", range(4))
def test_actual_native_yaml_loader_and_type_contract(native_contract, index):
    _, result = native_contract
    row = result["rows"][index]
    assert row["loaded"]["original"]["biomolecules"] is None
    assert row["loaded"]["original"]["accepted_by_tissue_init_annotation"] is False
    assert row["loaded"]["corrected"]["biomolecules"] == []
    assert row["loaded"]["corrected"]["accepted_by_tissue_init_annotation"] is True
    assert row["loaded"]["corrected"]["temperature_K"] == 298.15


def test_native_contract_scope_and_source_identity(native_contract, original):
    _, result = native_contract
    assert result["native_parameter_loader_used"]
    assert result["warnings"] == []
    assert not any(
        result[key]
        for key in ("native_world_seeded", "native_network_initialized", "transport_executed")
    )
    assert len(result["installed_python_sha256"]) == 332
    assert result["cpu_affinity"] == original["protocol"]["resources"]["cpu_affinity"]
    assert result["amendment_sha256"] == c.sha(setup.AMENDMENT)
    assert result["script_sha256"] == c.sha(HERE / "native_config_contract.py")
    assert result["configuration_provider_sha256"] == c.sha(HERE / "setup_context.py")


def test_register_rejects_existing_or_broad_directory(tmp_path):
    with pytest.raises(ValueError, match="fresh run"):
        job.register(tmp_path, tmp_path / "tests.xml", tmp_path / "contract")


def test_no_model_imports_in_context_or_job():
    program = (
        f"import sys; sys.path.insert(0, {str(HERE)!r}); import setup_context, setup_job; "
        "assert not any(n.split('.')[0] in {'cells','betse','numpy','jax','jaxlib'} "
        "for n in sys.modules)"
    )
    subprocess.run([sys.executable, "-B", "-c", program], check=True, timeout=5)


def test_failure_receipt_without_registration_has_no_automatic_retry(tmp_path):
    result = subprocess.run(
        [sys.executable, "-B", str(HERE / "setup_job.py"), "execute", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode != 0
    failure = c.read(tmp_path / "failure.json")
    assert failure["status"] == "failed_not_qualified" and not failure["automatic_retry"]
    assert not (tmp_path / "completion.json").exists() and not (tmp_path / "betse.log").exists()
