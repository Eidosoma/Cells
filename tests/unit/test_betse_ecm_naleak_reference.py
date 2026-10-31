"""Explicit ECM leak domain; standalone and voltage-dependent domains stay bounded."""

import ast
import hashlib
import os
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from validation.betse import betse_normal_ecm_catalog_join_reference as catalog_reference
from validation.betse import betse_normal_ecm_event_join_reference as event_reference
from validation.channels import sodium_catalog_reference as sodium


@pytest.fixture(params=(catalog_reference, event_reference), ids=("catalog", "event"))
def reference(request):
    return request.param


def test_native_leak_law_has_constant_targets_times_and_zero_gate_powers():
    root = Path(os.environ.get("CELLS_BETSE_SOURCE", "/mnt/workspaces/Cells/betse-v1.5.0"))
    path = root / "betse/science/channels/vg_na.py"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "6faa67bdc4bfd0ee35dc1cc0fd8dcd73a703ff58120d1b1968da94dac1fe8831"
    )
    cls = next(n for n in ast.parse(raw).body if isinstance(n, ast.ClassDef) and n.name == "NaLeak")
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    update = methods["_calculate_state"]
    statements = update.body[1:]  # The first node is the source docstring.
    assert len(statements) == 4 and all(isinstance(n, ast.Assign) for n in statements)
    assert {ast.unparse(n.targets[0]): ast.literal_eval(n.value) for n in statements} == {
        "self._mInf": 1,
        "self._mTau": 1,
        "self._hInf": 1,
        "self._hTau": 1,
    }
    literals = {
        ast.unparse(n.targets[0]): ast.literal_eval(n.value)
        for n in methods["_init_state"].body
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
    }
    assert {k: literals[k] for k in ("self.time_unit", "self._mpower", "self._hpower")} == {
        "self.time_unit": 1.0,
        "self._mpower": 0,
        "self._hpower": 0,
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
        0.16058,
        0.37417,
        1.0,
        sys.float_info.max,
        Decimal("1e1000"),
    ),
)
def test_ecm_leak_reference_is_exact_for_finite_inputs(reference, voltage):
    for refinement in (1, 2):
        target, tau = reference.kinetics("NaLeak", voltage, refinement)
        assert target == tau == [Decimal(1), Decimal(1)]
        assert all(type(value) is Decimal for value in target + tau)


@pytest.mark.parametrize(
    "value",
    (
        float("nan"),
        float("inf"),
        float("-inf"),
        Decimal("NaN"),
        Decimal("Infinity"),
        True,
        False,
        "0.0",
        None,
        1j,
    ),
)
def test_ecm_leak_keeps_nonfinite_and_type_refusals(reference, value):
    with pytest.raises(ValueError):
        reference.kinetics("NaLeak", value, 1)


@pytest.mark.parametrize("name", tuple(name for name in sodium.CLASSES if name != "NaLeak"))
@pytest.mark.parametrize("voltage", (-0.120001, 0.060001))
def test_voltage_dependent_sodium_domain_is_explicit_per_adapter(reference, name, voltage):
    if reference is catalog_reference and voltage == 0.060001:
        # Prospectively admitted ECM computation; the event and standalone
        # contracts remain original. This does not reclassify old controls.
        target, tau = reference.kinetics(name, voltage, 1)
        assert all(value.is_finite() and 0 <= value <= 1 for value in target)
        assert all(value.is_finite() and value > 0 for value in tau)
    else:
        with pytest.raises(ValueError, match="outside declared.*computational domain"):
            reference.kinetics(name, voltage, 1)


@pytest.mark.parametrize("voltage", (-0.120001, 0.060001))
def test_standalone_leak_reference_still_has_its_original_domain(voltage):
    with pytest.raises(ValueError, match="outside declared computational domain"):
        sodium._kinetics(voltage, "NaLeak")


def test_reference_does_not_import_production_or_numerical_libraries():
    assert not {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "torch"} & set(sys.modules)
