"""Independent arithmetic, saved-data corruption and import-boundary regression."""

import ast
import copy
import importlib
import math
import shutil
import subprocess
import sys
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ctx = importlib.import_module("transport_audit_context")
ind = importlib.import_module("transport_independent")
job = importlib.import_module("transport_audit_job")
c = ctx.c


@pytest.fixture(scope="module")
def saved():
    return ctx.load_capture()


@pytest.fixture(scope="module")
def reconstructed(saved):
    return ind.rebuild(saved["registration"], saved["native"], saved["cells"])


def test_every_saved_comparison_has_an_independent_reconstruction(saved, reconstructed):
    result = ind.reconcile(
        reconstructed, saved["comparison"], saved["registration"]["protocol"]["tolerances"]
    )
    assert result["independent_comparisons"] == 37068
    assert result["failed_comparisons"] == 0, result["failures"][:8]
    assert result["definition_contracts_checked"] == 12
    assert result["hidden_state_controls_checked"] == 2


def test_original_comparison_replays_exactly(saved):
    checker = importlib.import_module("transport_check")
    replay = checker.evaluate(saved["registration"], saved["native"], saved["cells"])
    assert replay == saved["comparison"]


@pytest.mark.parametrize("voltage", [-0.12, -0.08, -0.0253, -0.006, 0.0, 0.06])
def test_independent_gate_law_matches_separate_scalar_identities(voltage):
    with localcontext() as context:
        context.prec = 80
        target, times = ind.kinetics(voltage)
        expected = [
            1 / (1 + math.exp(-(voltage + 0.006) / 0.0064)),
            1 / (1 + math.exp((voltage + 0.0253) / 0.0035)),
        ]
        assert [float(x) for x in target] == pytest.approx(expected, abs=1e-15)
        assert all(value > 0 for value in times)
        updated = ind.native_step([0.2, 0.6], target, times, 25e-6)
        for old, new, inf, tau in zip(
            [Decimal("0.2"), Decimal("0.6")], updated, target, times, strict=True
        ):
            residual = new - old - Decimal("0.000025") * (inf - new) / tau
            assert abs(residual) < Decimal("1e-78")


@pytest.mark.parametrize("voltage", [-0.08, 0.0, 0.06])
def test_independent_ghk_blocking_and_reversal(saved, voltage):
    p = saved["registration"]["protocol"]
    with localcontext() as context:
        context.prec = 80
        assert ind.inward_density(voltage, 140, 4, 0, p) == 0
        assert ind.inward_density(0, 140, 4, 1e-8, p) == Decimal("-0.00000136")
        x = (
            Decimal(str(voltage))
            * Decimal(str(p["constants"]["F"]))
            / (Decimal(str(p["constants"]["R"])) * Decimal(str(p["temperature_K"])))
        )
        equilibrium_out = Decimal(140) * x.exp()
        assert abs(ind.inward_density(voltage, 140, equilibrium_out, 1e-8, p)) < Decimal("1e-70")


def test_owner_reduction_not_face_average():
    geometry = {
        "cell_count": 2,
        "membrane_count": 3,
        "membrane_owners": [1, 0, 1],
        "membrane_areas_m2": [2.0, 3.0, 5.0],
    }
    assert ind.integrated_faces([7.0, 11.0, 13.0], geometry) == [Decimal(33), Decimal(79)]
    assert ind.by_cell([0.2, 0.6, 0.2], geometry) == [Decimal("0.6"), Decimal("0.2")]
    with pytest.raises(ValueError, match="Nonuniform"):
        ind.by_cell([0.2, 0.6, 0.3], geometry)


@pytest.mark.parametrize("value", [True, False, None, "1", float("nan"), float("inf")])
def test_nonfinite_or_untyped_arithmetic_rejected(value):
    with pytest.raises(ValueError):
        ind.d(value)


def test_tolerance_uses_expected_not_maximum_magnitude():
    assert ind.normalized(100, 1, "quantity", {"quantity": 1, "relative": 1}) == 49.5


@pytest.mark.parametrize("kind", ["missing", "duplicate", "unit", "actual", "expected", "verdict"])
def test_saved_comparison_corruptions_rejected(saved, reconstructed, kind):
    changed = copy.deepcopy(saved["comparison"])
    if kind == "missing":
        changed["comparisons"].pop()
    elif kind == "duplicate":
        changed["comparisons"][-1] = copy.deepcopy(changed["comparisons"][0])
    elif kind == "unit":
        changed["comparisons"][0]["unit"] = "gate"
    elif kind == "verdict":
        changed["comparisons"][0]["passed"] = False
    else:
        changed["comparisons"][0][kind] += 1
    if kind in ("missing", "duplicate", "unit"):
        with pytest.raises(ValueError):
            ind.reconcile(reconstructed, changed, saved["registration"]["protocol"]["tolerances"])
    else:
        assert (
            ind.reconcile(reconstructed, changed, saved["registration"]["protocol"]["tolerances"])[
                "failed_comparisons"
            ]
            > 0
        )


@pytest.mark.parametrize(
    "kind",
    [
        "post_gate",
        "open_probability",
        "flux_sign",
        "current",
        "double_transfer",
        "voltage",
        "cells_rate",
        "cells_transfer",
        "countercharge",
        "bath_volume",
        "fixed_charge",
        "capacitor",
        "channel_owner",
    ],
)
def test_raw_data_corruptions_fail_independent_path(saved, reconstructed, kind):
    baseline = ind.reconcile(
        reconstructed, saved["comparison"], saved["registration"]["protocol"]["tolerances"]
    )
    assert baseline["failed_comparisons"] == 0
    native, cells = copy.deepcopy(saved["native"]), copy.deepcopy(saved["cells"])
    key = "active_channel/prescribed_mh_a"
    row = native["rows"][key]
    result = cells["results"]["jax_jit"][key]
    definition = cells["definitions"][key]
    if kind == "post_gate":
        row["channel_after"]["m"][0] += 0.1
    elif kind == "open_probability":
        row["channel_after"]["P"][0] += 0.1
    elif kind == "flux_sign":
        row["channel_after"]["density_mol_per_m2_s"][0] *= -1
    elif kind == "current":
        row["network_current_density_A_per_m2"][0] += 1
    elif kind == "double_transfer":
        row["after_ordinary"]["inside_mM"][1][0] += 0.01
    elif kind == "voltage":
        row["after_voltage"]["voltage_V"][0] += 0.001
    elif kind == "cells_rate":
        result["rhs"]["amount_increment"][1][0] += 1
    elif kind == "cells_transfer":
        result["after"]["channel_transferred"][0] += 0.01
    elif kind == "countercharge":
        result["countercharge_C"] += 1e-15
    elif kind == "bath_volume":
        definition["model"]["extracellular"]["volume_pL"] /= 30
    elif kind == "fixed_charge":
        definition["model"]["cells"][0]["cell"]["fixed_charge_equivalent_fmol"] += 1
    elif kind == "capacitor":
        definition["model"]["cells"][0]["membrane"]["area_m2"] *= 2
    else:
        definition["model"]["cells"][0]["channel"]["membrane_id"] = "membrane_1"
    try:
        rebuilt = ind.rebuild(saved["registration"], native, cells)
        result = ind.reconcile(
            rebuilt, saved["comparison"], saved["registration"]["protocol"]["tolerances"]
        )
    except ValueError:
        return
    assert result["failed_comparisons"] > 0, kind


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "qualified"),
        ("comparison_count", 1),
        ("failed_comparisons", 1),
        ("independent_audit_complete", True),
        ("coupled_trajectory_qualified", True),
        ("production_changed", True),
        ("gpu_tested", True),
        ("elapsed_seconds", 400),
    ],
)
def test_completion_scope_and_resource_corruptions_rejected(saved, field, value):
    receipt = copy.deepcopy(saved["completion"])
    receipt[field] = value
    with pytest.raises(ValueError):
        ctx.validate_receipts(
            ctx.CAPTURE, saved["registration"], receipt, saved["native"], saved["cells"]
        )


@pytest.mark.parametrize("kind", ["extra", "missing", "modified", "symlink"])
def test_packet_membership_and_digest_corruptions_rejected(saved, tmp_path, kind):
    packet = tmp_path / "packet"
    shutil.copytree(ctx.CAPTURE, packet)
    if kind == "extra":
        c.write(packet / "extra.json", {})
    elif kind == "missing":
        (packet / "cells.json").rename(tmp_path / "retained-cells.json")
    elif kind == "modified":
        (packet / "cells.log").rename(tmp_path / "retained-cells.log")
        c.write(packet / "cells.log", {"modified": True})
    else:
        (packet / "link.json").symlink_to(packet / "cells.json")
    with pytest.raises(ValueError):
        ctx.manifest(packet, saved["completion"], saved["registration"])


def test_partial_native_and_definition_records_are_not_ignored(saved):
    native = copy.deepcopy(saved["native"])
    native["rows"]["active_channel/prescribed_mh_a"]["core_initial"]["inside_mM"][0][0] += 1
    with pytest.raises(ValueError, match="before artifact"):
        ctx.validate_partials(ctx.CAPTURE, saved["registration"], native, saved["cells"])
    cells = copy.deepcopy(saved["cells"])
    cells["definitions"]["network_off/native_initial"]["model"]["temperature_K"] += 1
    with pytest.raises(ValueError, match="definition artifact"):
        ctx.validate_partials(ctx.CAPTURE, saved["registration"], saved["native"], cells)


@pytest.mark.parametrize("replacement", ["omitted", "empty_mapping"])
def test_explicit_null_channel_is_required_for_channel_free_definition(saved, replacement):
    r = saved["registration"]
    variant = r["protocol"]["variants"][0]
    key = "network_off/native_initial"
    definition = copy.deepcopy(saved["cells"]["definitions"][key])
    geometry = saved["native"]["preparations"]["network_off"]["geometry"]
    row = saved["native"]["rows"][key]
    ind.definition_contract(definition, r["protocol"], r["base_protocol"], variant, geometry, row)
    assert definition["model"]["cells"][0]["channel"] is None
    if replacement == "omitted":
        definition["model"]["cells"][0].pop("channel")
    else:
        definition["model"]["cells"][0]["channel"] = {}
    with pytest.raises(ValueError, match="channel presence"):
        ind.definition_contract(
            definition, r["protocol"], r["base_protocol"], variant, geometry, row
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("decision", "changed"),
        ("expected_comparisons", 1),
        ("precision_digits", 40),
        ("automatic_retry", True),
        ("total_timeout_seconds", 999),
    ],
)
def test_unregistered_plan_rejected(field, value):
    plan = copy.deepcopy(c.read(ctx.PLAN))
    plan[field] = value
    with pytest.raises(ValueError, match="plan changed"):
        ctx.validate_plan(plan)


@pytest.mark.parametrize("name", ctx.FORBIDDEN)
def test_fresh_process_model_import_fence(name):
    program = (
        f"import sys; sys.path.insert(0, {str(HERE)!r}); import transport_audit_context as c\n"
        f"with c.model_fence():\n    __import__({name!r})\n"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", program], capture_output=True, text=True, timeout=5
    )
    assert result.returncode != 0 and "Model import forbidden" in result.stderr


def test_independent_module_imports_only_standard_arithmetic():
    modules = set()
    for node in ast.walk(ast.parse((HERE / "transport_independent.py").read_text())):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module.split(".")[0])
    assert modules == {"math", "decimal"}


def test_preserved_capture_and_source_scope(saved):
    assert len(saved["hashes"]) == 54
    assert len(saved["registration"]["sources_sha256"]) == 76
    assert len(ctx.sources()) == 83
    assert saved["provenance"]["installed_native_python_files"] == 332
    assert saved["completion"]["status"] == "capture_pass_pending_audit"
    assert saved["hashes"] == ctx.packet_hashes(ctx.CAPTURE)


def test_existing_or_broad_output_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="fresh audit"):
        job.register(tmp_path, tmp_path / "tests.xml")


def test_unregistered_audit_writes_failure_without_qualification(tmp_path):
    result = subprocess.run(
        [sys.executable, "-B", str(HERE / "transport_audit_job.py"), "execute", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode != 0
    receipt = c.read(tmp_path / "failure.json")
    assert receipt["status"] == "audit_failed_not_qualified" and not receipt["automatic_retry"]
    assert not (tmp_path / "completion.json").exists()
