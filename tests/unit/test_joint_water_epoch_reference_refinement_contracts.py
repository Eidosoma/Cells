"""Mocked solver and saved-array contracts; no physical trajectory is run."""

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


@pytest.mark.parametrize("factor", (0, -1, 3, True, False, 1.0, 2.0, "2", None))
def test_undeclared_refinement_refused_before_binding(factor):
    with pytest.raises(ValueError, match="integer 1 or 2"):
        reference.integrate({}, refinement=factor)


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
