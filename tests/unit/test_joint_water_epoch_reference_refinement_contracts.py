"""Mocked solver and saved-array contracts; no physical trajectory is run."""

import ast
import importlib.util
import os
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from tests.owned_joint_water_epoch_reference_refinement_helpers import numerical_comparison
from validation.topology import joint_water_epoch_transient_reference as reference


def prior_module():
    root = Path(os.environ["CELLS_REFERENCE_BASELINE_SOURCE"])
    path = root / "validation/topology/joint_water_epoch_transient_reference.py"
    spec = importlib.util.spec_from_file_location("accepted_epoch_reference", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mocked_run(monkeypatch, module, refinement=None, supplied=False):
    shapes = {
        "membrane_transferred": (1,),
        "electrode_charge_transferred_C": (1,),
        "volume_increment_pL": (1,),
    }
    calls, held = [], []
    context = dict(
        parent=dict(shapes=shapes),
        process=SimpleNamespace(
            flatten=lambda c, values: np.concatenate([values[k].ravel() for k in shapes])
        ),
    )

    def evaluate(c, y, *, held_time):
        held.append(held_time)
        return np.r_[np.zeros(3), 1.0], None, None

    def solver(rhs, span, y, **kwargs):
        calls.append(dict(span=span, **kwargs))
        slope = rhs(span[0], y)
        end = y + (span[1] - span[0]) * slope
        return SimpleNamespace(
            success=True,
            y=np.stack([y, end], axis=1),
            nfev=1,
            sol=lambda t: y + (t - span[0]) * slope,
        )

    monkeypatch.setattr(
        module,
        "scheduled",
        SimpleNamespace(bind=lambda raw: context, initial=lambda c: np.zeros(4), evaluate=evaluate),
    )
    monkeypatch.setattr(module, "solve_ivp", solver)
    raw = dict(
        experiment=dict(
            end_time=4e-6,
            observation_times=[0, 0.5e-6, 4e-6],
            membrane_controls=[dict(schedule=[dict(time=t) for t in (0, 1e-6, 3e-6)])],
            pump_controls=[dict(schedule=[dict(time=t) for t in (0, 2e-6)])],
        )
    )
    initial = np.asarray([0.125, -0.25, 0.5, 0.0]) if supplied else None
    result = module.integrate(
        raw, initial, **({} if refinement is None else dict(refinement=refinement))
    )
    assert held == [0, 1e-6, 2e-6, 3e-6]
    return result, calls


@pytest.mark.parametrize("supplied", (False, True))
def test_default_and_explicit_one_match_accepted_reference_bitwise(monkeypatch, supplied):
    old, old_calls = mocked_run(monkeypatch, prior_module(), supplied=supplied)
    for factor in (None, 1):
        actual, calls = mocked_run(monkeypatch, reference, factor, supplied)
        for a, b in zip(actual[:2], old[:2], strict=True):
            assert a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()
        assert actual[2] == old[2]
        for call, original in zip(calls, old_calls, strict=True):
            np.testing.assert_array_equal(call.pop("atol"), original["atol"])
            assert call == {k: v for k, v in original.items() if k != "atol"}


@pytest.mark.parametrize("supplied", (False, True))
def test_refinement_two_halves_every_accuracy_setting_without_reclocking(monkeypatch, supplied):
    old, old_calls = mocked_run(monkeypatch, prior_module(), supplied=supplied)
    actual, calls = mocked_run(monkeypatch, reference, 2, supplied)
    np.testing.assert_array_equal(actual[0], old[0])
    np.testing.assert_array_equal(actual[1], old[1])
    for call, original in zip(calls, old_calls, strict=True):
        for key in ("rtol", "max_step", "atol"):
            np.testing.assert_array_equal(call[key], original[key] / 2)
        assert call["span"] == original["span"]
    for key in (
        "rtol",
        "amount_volume_energy_atol",
        "background_transfer_atol_fmol",
        "charge_atol_C",
        "clock_atol_s",
        "max_step_s",
    ):
        assert actual[2][key] == old[2][key] / 2


@pytest.mark.parametrize("factor", (0, -1, 3, True, False, 1.0, 2.0, "2", None))
def test_undeclared_refinement_refused_before_binding(factor):
    with pytest.raises(ValueError, match="integer 1 or 2"):
        reference.integrate({}, refinement=factor)


def test_exact_inverse_ast_recovers_all_accepted_equations_and_control_semantics():
    old = ast.parse(Path(prior_module().__file__).read_text())
    tree = ast.parse(Path(reference.__file__).read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "integrate")
    assert len(node.args.kwonlyargs) == 1 and node.args.kwonlyargs[0].arg == "refinement"
    node.args.kwonlyargs, node.args.kw_defaults = [], []
    guard = node.body.pop(0)
    assert isinstance(guard, ast.If) and "refinement" in ast.unparse(guard)

    class Restore(ast.NodeTransformer):
        def visit_BinOp(self, value):
            value = self.generic_visit(value)
            if (
                isinstance(value.op, ast.Div)
                and isinstance(value.right, ast.Name)
                and value.right.id == "refinement"
            ):
                return value.left
            return value

    tree = Restore().visit(tree)
    assert ast.dump(tree, include_attributes=False) == ast.dump(old, include_attributes=False)


def synthetic(phase="SIM"):
    shapes = {
        "membrane_transferred": [1],
        "electrode_charge_transferred_C": [1],
        "volume_increment_pL": [1],
    }
    old = dict(state_flat=np.zeros((2, 4)), initial_flat=np.zeros(4))
    old["state_flat"][-1] = [1e-5, 0, 1e-4, 4e-6]
    tight = deepcopy(old)
    tight["state_flat"][-1, 0] += 1e-15
    production = [deepcopy(old), deepcopy(old)]
    for record, error in zip(
        production, (5e-13, 3e-14) if phase == "SIM" else (1e-15, 2e-15), strict=True
    ):
        record["state_flat"][-1, 0] += error
    return shapes, old, tight, production


@pytest.mark.parametrize("phase", ("INIT", "SIM"))
def test_saved_array_acceptance_and_precision_labels(phase):
    report = numerical_comparison(phase, *synthetic(phase))
    assert not report["convergence_order_claim"]
    if phase == "INIT":
        assert report["refinement_mode"] == "precision_limited"
    else:
        assert report["reference_increment_change_over_fine_error"] < 0.1


@pytest.mark.parametrize(
    "fault", ("reference-state", "resolved-fine", "production-budget", "production-refinement")
)
def test_predeclared_stability_and_original_acceptance_fail_closed(fault):
    shapes, old, tight, production = synthetic()
    if fault == "reference-state":
        tight["state_flat"][-1, 2] += 4e-12
        match = "reference stability"
    elif fault == "resolved-fine":
        tight["state_flat"][-1, 0] = old["state_flat"][-1, 0] + 6e-15
        match = "reference uncertainty"
    elif fault == "production-budget":
        production[1]["state_flat"][-1, 2] += 5e-11
        match = "production state budget"
    else:
        production[1]["state_flat"][-1, 0] = old["state_flat"][-1, 0] + 3e-13
        match = None
    with pytest.raises(AssertionError, match=match):
        numerical_comparison("SIM", shapes, old, tight, production)
