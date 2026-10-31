"""Source-constant CaLeak admission in the ECM reference, with bounded peers."""

import ast
import hashlib
import os
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from validation.betse import betse_normal_ecm_catalog_join_reference as reference
from validation.channels import calcium_catalog_extra_reference as calcium


def test_native_caleak_has_voltage_independent_unit_targets_and_time_constants():
    root = Path(os.environ.get("CELLS_BETSE_SOURCE", "/mnt/workspaces/Cells/betse-v1.5.0"))
    source = (root / "betse/science/channels/vg_ca.py").read_bytes()
    assert hashlib.sha256(source).hexdigest() == (
        "843d83f969ec53ba9322504f6ef0f699171c3c7c6e2caf03784de5bb17171dd6"
    )
    cls = next(
        n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == "CaLeak"
    )
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    for name in ("_init_state", "_calculate_state"):
        assert not any(
            isinstance(n, ast.Name) and n.id == "V" and isinstance(n.ctx, ast.Load)
            for n in ast.walk(methods[name])
        )
    updates = methods["_calculate_state"].body[1:]
    assert len(updates) == 4 and all(isinstance(n, ast.Assign) for n in updates)
    assert {ast.unparse(n.targets[0]): ast.literal_eval(n.value) for n in updates} == {
        "self._mInf": 1,
        "self._mTau": 1,
        "self._hInf": 1,
        "self._hTau": 1,
    }
    assignments = {
        ast.unparse(n.targets[0]): ast.unparse(n.value)
        for n in methods["_init_state"].body
        if isinstance(n, ast.Assign)
    }
    assert {
        name: assignments[name]
        for name in (
            "self.time_unit",
            "self._mpower",
            "self._hpower",
            "self.m",
            "self.h",
        )
    } == {
        "self.time_unit": "1.0",
        "self._mpower": "0",
        "self._hpower": "0",
        "self.m": "np.ones(self.data_length)",
        "self.h": "np.ones(self.data_length)",
    }


@pytest.mark.parametrize(
    "voltage",
    (
        -sys.float_info.max,
        -1.0,
        -0.120001,
        -0.120,
        -0.0,
        0.060,
        0.060001,
        0.1621468576318261,
        0.16814685763182613,
        0.1771468576318261,
        0.19381368115650896,
        0.20881368115650895,
        0.20881368115650897,
        0.3804661874926949,
        0.4,
        1.0,
        sys.float_info.max,
        Decimal("1e1000"),
    ),
)
def test_ecm_caleak_matches_source_constants_for_finite_voltages(voltage):
    for refinement in (1, 2):
        target, tau = reference.kinetics("CaLeak", voltage, refinement)
        assert target == tau == [Decimal(1), Decimal(1)]
        assert all(type(value) is Decimal for value in target + tau)


@pytest.mark.parametrize(
    "value",
    (
        float("nan"),
        float("inf"),
        float("-inf"),
        Decimal("NaN"),
        Decimal("sNaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
        True,
        False,
        "0.0",
        None,
        1j,
    ),
)
def test_ecm_caleak_preserves_finite_real_type_admission(value):
    with pytest.raises(ValueError, match="requires a real number|Nonfinite voltage"):
        reference.kinetics("CaLeak", value, 1)


@pytest.mark.parametrize("voltage", (-0.120001, 0.060001))
def test_standalone_caleak_retains_its_original_domain(voltage):
    with pytest.raises(ValueError, match="Voltage outside computational domain"):
        calcium._kinetics(voltage, "CaLeak")


@pytest.mark.parametrize("name", ("Ca_L3", "Cav_G"))
@pytest.mark.parametrize("voltage", (-0.120001, 0.060001))
def test_other_calcium_extra_laws_keep_their_original_bounds(name, voltage):
    with pytest.raises(ValueError, match="Voltage outside computational domain"):
        reference.kinetics(name, voltage, 1)


@pytest.mark.parametrize("voltage", (-0.120001, 0.400001))
def test_cal2_retains_its_separately_declared_bounds(voltage):
    with pytest.raises(
        ValueError, match="^Voltage outside declared ECM Ca_L2 computational domain$"
    ):
        reference.kinetics("Ca_L2", voltage, 1)


def test_reference_uses_no_production_or_numerical_imports():
    assert not {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "torch"} & set(sys.modules)
