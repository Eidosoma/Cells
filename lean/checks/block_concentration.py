"""Check the two FR-51 concentration bounds against the tagged synthetic reference results."""

import argparse
import json
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
from validation.fr51 import engine, judge, plants

from cells.definitions.specs import parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.laws.electrochemistry import F, R
from cells.registry.models import get_model


def compare(bound, derivative, volts):
    bound, derivative = np.asarray(bound), np.asarray(derivative)
    assert np.isfinite(bound).all() and np.isfinite(derivative).all()
    assert np.all(bound >= 0)
    passed, worst = judge.at_least(bound, derivative)
    nonzero = derivative != 0
    if not nonzero.any():
        return dict(passed=passed, min_bound_over_derivative=None)
    index = np.argmin(bound[nonzero] / np.abs(derivative[nonzero]))
    return dict(
        passed=passed,
        min_bound_over_derivative=worst,
        worst_voltage_mV=float(1000 * volts[nonzero][index]),
    )


def clamped(case):
    grid = case.voltages[case.grid]
    indices = np.flatnonzero((case.voltages >= grid.min()) & (case.voltages <= grid.max()))
    volts, unique = np.unique(case.voltages[indices], return_index=True)
    _, state, control, layout, _ = engine.world(case.case_id)
    _, _, terms = engine.program(case.case_id)(state, control, layout, volts)
    assert np.asarray(terms.block.valid).all()
    return volts, indices[unique], terms


def reversal_case(case):
    assert case.within_declared_accuracy
    volts, indices, terms = clamped(case)
    result = dict(case=case.case_id, voltages=len(volts))
    for end, key in (("inside", "i"), ("outside", "o")):
        derivative = case.q[f"dJ_blocked_dc_{key}_fmol_s_per_mM"][indices]
        bound = np.asarray(getattr(terms, end + "_term"))[:, 0]
        result[end] = compare(bound, derivative, volts)
        if case.case_id == "B1_two_modes_E1" and end == "outside":
            (at,) = np.flatnonzero(volts == 0.05)
            result["outside_at_plus_50_mV"] = dict(
                bound=float(bound[at]), absolute_derivative=float(abs(derivative[at]))
            )
    return result


def chloride_control():
    """Use a chloride reversal with signed valence and differentiate the compiled native flux."""
    raw = engine.raw_world("B4_anion_effective")
    raw["model"]["channels"][0]["block"]["reference"] = {"reversal_of": "Cl"}
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, layout = model.initial_values(spec)
    state, layout = jax.device_put((state, layout))
    control = model.Control(*(v[0] for v in control_values(spec, [0.0])))
    cl = [s["id"] for s in raw["model"]["species"]].index("Cl")

    def flux(dci, dco, voltage):
        moved = state._replace(
            amount_increment=state.amount_increment.at[cl, 0].add(dci * layout.volume[0]),
            extracellular_amount_increment=state.extracellular_amount_increment.at[cl, 0].add(
                dco * layout.extracellular_volume[0]
            ),
        )
        j, _, terms = model.clamped_channel_flux(
            moved, control, layout, voltage, xp=jnp, block=True
        )
        return j[cl, 0], (
            terms.inside_term[0],
            terms.outside_term[0],
            terms.block.reversal[0],
            terms.block.valid,
        )

    volts = np.linspace(-0.120, 0.060, 37)
    grad = jax.grad(flux, (0, 1), has_aux=True)
    (di, do), (ti, to, reversal, valid) = jax.jit(jax.vmap(grad, (None, None, 0)))(0.0, 0.0, volts)
    expected = -R * raw["model"]["temperature_K"] / F * np.log(120 / 20)
    np.testing.assert_allclose(reversal, expected, rtol=judge.REL, atol=0)
    assert np.asarray(valid).all()
    inside, outside = compare(ti, di, volts), compare(to, do, volts)
    assert inside["passed"] and outside["passed"]
    return dict(
        voltages=len(volts), reversal_mV=float(1000 * reversal[0]), inside=inside, outside=outside
    )


def run(directory):
    assert jax.config.x64_enabled and jax.default_backend() == "cpu"
    refs = judge.read_results(directory)
    spec = engine.spec_of()
    actual, absolute = [], []
    for key, ref in refs.items():
        if not ref.blocked:
            continue
        block = spec["blocks"][ref.declared["block"]]
        if block["reference"] == "membrane_voltage":
            volts, _, term = clamped(ref)
            assert all(
                np.all(np.asarray(a) == 0)
                for a in (
                    term.inside_term,
                    term.outside_term,
                    term.inside_through_e,
                    term.outside_through_e,
                )
            )
            absolute.append(dict(case=key, voltages=len(volts)))
        else:
            row = reversal_case(ref)
            assert row["inside"]["passed"] and row["outside"]["passed"], row
            actual.append(row)
    registered = set(judge.CHECKS["E"][1])
    assert registered <= {row["case"] for row in actual}
    failures = {}
    for name, (plant, criterion, keys) in plants.JUDGED.items():
        if criterion != "E":
            continue
        with plant():
            rows = [reversal_case(refs[key]) for key in keys]
        assert all(not (r["inside"]["passed"] and r["outside"]["passed"]) for r in rows), name
        failures[name] = rows
    assert len(failures) >= 2
    return dict(
        registered_cases=sorted(registered),
        reversal_cases=actual,
        membrane_voltage_controls=absolute,
        planted_controls=failures,
        chloride_autodiff=chloride_control(),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "reference_results",
        type=Path,
        help="validation/fr51/references/results from fr51-references-2026-11-24",
    )
    print(json.dumps(run(parser.parse_args().reference_results), indent=2, allow_nan=False))
