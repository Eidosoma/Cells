"""Check the insertion half-step's strict heat sign against a one-patch fixed-charge solution."""

import argparse
import json
import math
from decimal import Decimal, localcontext
from unittest.mock import patch

import jax
import jax.numpy as jnp
import jaxlib
import numpy as np

from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.models import pump_composite_adapter as adapter
from cells.operators import membrane_insertion as insertion
from cells.operators import membrane_insertion_v2 as insertion_v2
from tests import membrane_insertion_fixtures as fixture
from tests.unit import test_membrane_insertion_v2 as binding

HALF_STEP = fixture.DT / 2
RATIOS = (0.0, 1e-6, 0.5, 1.0, 5.0, 1000.0)
STRESS_RATIO = 1.7e16
RTOL = 1e-9  # tests/unit/test_membrane_insertion.py::test_one_patch_analytic


def definition(version, ratio):
    base = fixture.one_patch(end=fixture.DT)
    patch = base["model"]["membranes"][0]
    rate = patch["area_m2"] / HALF_STEP if ratio else 0.0
    raw = fixture.with_operators(base, {patch["id"]: ({}, None, [(0.0, rate)])})
    # One half-step adds one original patch area. Vary only the inserted specific capacitance.
    inserted = raw["model"]["operators"][1]["patches"][0]
    inserted["specific_capacitance_F_per_m2"] = fixture.SPECIFIC_CAPACITANCE * (ratio or 1.0)
    return binding.as_v2(raw) if version == insertion_v2.LAW_ID else raw


def reference(params, control):
    """Energy loss at fixed Q against a bath at 0 V, from the represented model inputs."""
    assert float(params.boundary_V[0]) == 0
    with localcontext() as ctx:
        ctx.prec = 80
        c = Decimal.from_float(float(params.membrane_capacitance[0]))
        q = Decimal.from_float(float(params.initial_cell_charge_C[0]))
        rate = Decimal.from_float(float(control.insertion_rate_m2_s[0]))
        specific = Decimal.from_float(float(params.insertion_specific_capacitance[0]))
        dc = specific * rate * Decimal.from_float(HALF_STEP)
        return float(Decimal("5e11") * q**2 * dc / (c * (c + dc)))


def rollout(spec):
    try:
        final = run(spec).final.state
    except NumericalError as error:
        return {"completed": False, "reason": str(error)}
    return {"completed": True, "booked_heat_pJ": float(final.insertion_dissipated_energy_pJ[0])}


def check_version(version):
    _, model, _, _ = binding.bind(definition(version, 1.0))
    operator = binding.operator(model, version)

    @jax.jit
    def half_step(state, params, control):
        kwargs = (
            {"view": model.view(params, state, xp=jnp)} if version == insertion_v2.LAW_ID else {}
        )
        new, valid = operator.half_step(state, HALF_STEP, control, params, xp=jnp, **kwargs)
        return new.insertion_dissipated_energy_pJ[0], valid

    @jax.jit
    def field_check(state, params, control):
        view = model.view(params, state, xp=jnp)
        dc = params.insertion_specific_capacitance * (control.insertion_rate_m2_s * HALF_STEP)
        result = adapter.fixed_charge_change(state, view, dc, adapter.inner_layout(params), xp=jnp)
        before, after = result[-2:]
        squares = 0.5e12 * jnp.sum(
            view.membrane_capacitance * (after - before) ** 2 + dc * after**2
        )
        return squares, result[1][0]

    cases = []
    for ratio in (*RATIOS, STRESS_RATIO):
        spec, _, state, params = binding.bind(definition(version, ratio))
        control = binding.control_at(spec, model, 0.0)
        actual, valid = half_step(state, params, control)
        assert actual.dtype == np.float64
        actual = float(actual)
        expected = reference(params, control)
        squares, image = field_check(state, params, control)
        squares = float(squares)
        case = {
            "added_over_initial_capacitance": ratio,
            "reference_pJ": expected,
            "booked_pJ": actual,
            "half_step_valid": bool(valid),
            "heat_matches": math.isclose(actual, expected, rel_tol=RTOL),
            "squares_pJ": squares,
            "image_charge_C": float(image),
        }
        assert math.isclose(squares, expected, rel_tol=RTOL), case
        if ratio in (1.0, STRESS_RATIO):
            case["rollout"] = rollout(spec)
        cases.append(case)
    return cases


def one_patch_control(mode, versions):
    """In a separate invocation, substitute individual known terms only for the one-patch run."""
    original = adapter.fixed_charge_change

    def substituted(state, view, dc, bound, *, xp):
        updated, image, _, first, second, before, after = original(state, view, dc, bound, xp=xp)
        assert dc.shape == image.shape == (1,)
        heat = 0.5e12 * (view.membrane_capacitance * (after - before) ** 2 + dc * after**2)
        if mode == "heat-and-charge":
            image = xp.zeros_like(image)  # Fixed cell charge, one opposing bath plate.
        return updated, image, heat, first, second, before, after

    with patch.object(adapter, "fixed_charge_change", substituted):
        return {law: rollout(binding.bind(definition(law, STRESS_RATIO))[0]) for law in versions}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--one-patch-control", choices=("heat", "heat-and-charge"))
    mode = parser.parse_args().one_patch_control
    jax.config.update("jax_enable_x64", True)
    versions = (insertion.LAW_ID, insertion_v2.LAW_ID)
    with jax.default_device(jax.devices("cpu")[0]):
        if mode:
            controls = one_patch_control(mode, versions)
            print(
                json.dumps({"substituted": mode, "operators": controls}, indent=2, allow_nan=False)
            )
            raise SystemExit(0 if all(case["completed"] for case in controls.values()) else 1)
        results = {law: check_version(law) for law in versions}
    passed = all(
        case["half_step_valid"]
        and case["heat_matches"]
        and case.get("rollout", {}).get("completed", True)
        for cases in results.values()
        for case in cases
    )
    print(
        json.dumps(
            {
                "passed": passed,
                "jax": jax.__version__,
                "jaxlib": jaxlib.__version__,
                "operators": results,
            },
            indent=2,
            allow_nan=False,
        )
    )
    raise SystemExit(0 if passed else 1)
