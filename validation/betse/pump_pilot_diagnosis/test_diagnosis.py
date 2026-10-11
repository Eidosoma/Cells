"""Independent arithmetic, malformed-evidence and saved-short-fixture checks."""

import copy
import importlib
from decimal import Decimal as D
from decimal import localcontext

import diagnose as diag
import native_energy as energy
import pytest


@pytest.mark.parametrize("old,new", [(1, 1), (1, 2), (2, 1), (140, 140.000001)])
def test_convex_chemical_identity(old, new):
    with localcontext() as ctx:
        ctx.prec = 70
        old, new, volume, rt = D(old), D(new), D("0.45"), D(2500)
        change, gap = energy.chemical_change(old, new, volume, rt)
        direct = rt * volume * (new * (new.ln() - 1) - old * (old.ln() - 1)) / 1000
        assert abs(change - direct) < D("1e-60")
        assert gap >= 0
        assert abs(change - rt * volume * (new - old) * old.ln() / 1000 - gap) < D("1e-60")


@pytest.mark.parametrize("value", [0, -1])
def test_depleted_energy_state_rejected(value):
    with pytest.raises(ValueError, match="domain"):
        energy.chemical_change(D(1), D(value), D(1), D(2500))


def test_capacitor_remainder_is_quadratic():
    old, new, cap = D("-0.01"), D("-0.01001"), D("3e-12")
    change, gap = energy.capacitor_change(old, new, cap)
    assert change == cap * (new * new - old * old) * D("5e11")
    assert gap == cap * (new - old) ** 2 * D("5e11")


def test_relative_budget_and_all_failures_retained():
    result = diag.discrepancy([1.5, 2.5, 5.0], [1.0, 2.0, 3.0], 0.1, 0.1)
    assert result["comparisons"] == len(result["failures"]) == 3
    assert result["worst"]["index"] == 2
    assert result["worst"]["ratio"] == 5


@pytest.mark.parametrize("values", [[float("nan")], [float("inf")], []])
def test_bad_comparison_rejected(values):
    with pytest.raises(ValueError):
        diag.discrepancy(values, [0.0], 1e-7)


def test_signed_zero_is_not_bitwise_equal():
    assert not diag.bitwise_equal([0.0], [-0.0])
    assert diag.bitwise_equal([[1.0, -0.0]], [[1.0, -0.0]])


@pytest.mark.parametrize(
    "errors,expected", [([4, 2, 1], True), ([4, 3.9, 3.8], False), ([1e-13, 2e-13, 1e-13], True)]
)
def test_refinement_diagnostic_respects_registered_floor(errors, expected):
    assert diag.refinement(errors, 1e-12, 0.8)["passed"] == expected


def test_offgrid_or_ambiguous_samples_rejected():
    with pytest.raises(ValueError):
        diag.sample(dict(times_s=[0.0], states=[[0]], voltage_V=[[0]]), [1.0])
    with pytest.raises(ValueError):
        diag.sample(dict(times_s=[0.0, 0.0], states=[[0], [0]], voltage_V=[[0], [0]]), [0.0])


@pytest.mark.parametrize("name", ["cells", "numpy", "betse", "pilot_math", "coupled_reference"])
def test_import_fence(name):
    with diag.e.model_fence(), pytest.raises(ImportError):
        importlib.import_module(name)


@pytest.fixture(scope="module")
def saved():
    root = diag.e.ROOT / "runs/ref-005b-pump-loop-2026-09-16/capture-01"
    variants = diag.e.read(root / "registration.json")["protocol"]["variants"]
    return variants, diag.e.read(root / "betse.json")["rows"]


@pytest.mark.parametrize("index", range(6))
def test_independent_short_saved_energy(saved, index):
    variants, rows = saved
    variant = variants[index]
    row = rows[variant["id"] + "/observed"]
    result = energy.reconstruct(row, variant, [0.0, 0.0002], diag.e.Ledger())
    assert result["steps"] == 8 and len(result["states"]) == 2
    assert len(result["states"][1]) == 59
    assert result["energy"]["max_unexplained_pJ"] < 1e-10
    assert result["energy"]["final"]["convex_capacitor_pJ"] >= 0


@pytest.mark.parametrize(
    "corrupt", ["clock", "pump_stoichiometry", "applied_flux", "negative_pool"]
)
def test_corrupted_native_energy_refused(saved, corrupt):
    variants, rows = saved
    row = copy.deepcopy(rows["pump_leak/observed"])
    step, raw = row["trace"]["steps"][0], row["trace"]["raw_steps"][0]
    if corrupt == "clock":
        step["after_elapsed_s"] = 0
    elif corrupt == "pump_stoichiometry":
        raw["calls"][0]["returned"][0][0] *= -1
    elif corrupt == "applied_flux":
        step["before_ordinary"]["physical"]["ordinary_density_mol_per_m2_s"][0][0] += 1
    else:
        step["after_ordinary"]["physical"]["inside_mM"][0][0] = -1
        step["after_voltage"]["physical"]["inside_mM"][0][0] = -1
    with pytest.raises(ValueError):
        energy.reconstruct(row, variants[0], [0.0, 0.0002], diag.e.Ledger())


def test_failed_capture_sources_authenticate():
    registration, sources = diag.authenticate()
    assert len(sources) == 55 and len(registration["sources_sha256"]) == 629


def test_actual_saved_cells_arrays_and_complete_restarts():
    _, sources = diag.authenticate()
    packet = diag.e.read(diag.CAPTURE / "cells.json")
    assert len(diag.cells_records(packet, sources)) == 24
