"""Independent46-field work/ownership stages and short event-split histories."""

import json
import os
from pathlib import Path

import numpy as np
import pytest

from cells.core import surface_calcium_energy_atp_transport_spec as schema
from cells.core.schedule import control_values
from cells.models import surface_calcium_energy_atp_transport as model
from cells.numerics.fixed_step import rk4_step
from validation.tissue import calcium_energy_atp_transport_fixtures as fixtures
from validation.tissue import calcium_energy_atp_transport_reference as reference


def evidence(name, record, arrays):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(directory) / "atp-independent"
        folder.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(folder / (name + ".npz"), **arrays)
        (folder / (name + ".json")).write_text(
            json.dumps(
                record, indent=2, allow_nan=False, default=lambda value: np.asarray(value).tolist()
            )
            + "\n"
        )


def budget(context, target):
    absolute = reference.flatten(
        context,
        {
            key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
            for key, shape in context["shapes"].items()
        },
    )
    return absolute + 3e-10 * np.abs(target)


def control(spec, time):
    table = control_values(spec, [time])
    return type(table)(*(value[0] for value in table))


def checked_step(state, step, controls, layout):
    def rhs(value, held, params, active):
        result = model.readouts(value, held, params, xp=np)
        assert result.valid and np.isfinite(result.field.energy_balance_pJ_s)
        assert abs(float(result.field.energy_balance_pJ_s)) <= 1e-10
        return result.derivative

    return rk4_step(rhs, state, step, controls, layout, layout.active)


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_complete_initial_and_evolved_stages_match_independent_scalar_owners(arm, padded):
    spec = schema.parse(fixtures.probe(arm, padded=padded))
    raw = schema.to_dict(spec)
    context = reference.bind(raw)
    state, layout = model.initial_values(spec)
    controls = control(spec, 0.0)
    for index in range(2):
        actual = model.readouts(state, controls, layout, xp=np)
        vector = reference.flatten(context, state._asdict())
        target, phi, proof = reference.evaluate(context, vector, 0.0)
        packed = reference.flatten(context, actual.derivative._asdict())
        bound = budget(context, target)
        ratio = float(np.max(np.abs(packed - target) / bound, initial=0))
        physical_phi = np.r_[
            actual.field.potential_V[: layout.active.size][layout.active],
            actual.field.potential_V[layout.active.size :][layout.outside_active],
        ]
        evidence(
            "stage-" + arm + "-" + str(padded) + "-" + str(index),
            dict(definition=raw, full_fields=len(state), ratio=ratio, independent_proof=proof),
            dict(
                state=vector,
                actual_rate=packed,
                expected_rate=target,
                budget=bound,
                signed_error=packed - target,
                actual_phi=physical_phi,
                expected_phi=phi,
            ),
        )
        assert actual.valid and len(context["shapes"]) == len(state) == 46 and ratio <= 1.0
        np.testing.assert_allclose(physical_phi, phi, rtol=3e-10, atol=3e-13)
        assert abs(float(proof["physical_energy_balance_pJ_s"])) <= 1e-10
        np.testing.assert_allclose(
            actual.network_chemical_energy_J_mol[: len(context["network_ids"])],
            proof["network_physical_chemical_energy_J_mol"],
            rtol=3e-10,
            atol=3e-12,
        )
        np.testing.assert_allclose(
            actual.network_electrical_energy_J_mol[: len(context["network_ids"])],
            proof["network_physical_electrical_energy_J_mol"],
            rtol=3e-10,
            atol=3e-12,
        )
        n = len(context["cell_ids"])
        np.testing.assert_allclose(
            actual.exchange.gross_hydrolysis_fmol_s[:n],
            proof["pool_gross_hydrolysis_fmol_s"],
            rtol=3e-10,
            atol=3e-12,
        )
        np.testing.assert_allclose(
            actual.exchange.gross_synthesis_fmol_s[:n],
            proof["pool_gross_synthesis_fmol_s"],
            rtol=3e-10,
            atol=3e-12,
        )
        np.testing.assert_allclose(
            actual.network.source_reaction_energy_J_mol[: len(context["network_ids"])],
            proof["network_physical_reaction_energy_J_mol"],
            rtol=3e-12,
            atol=3e-9,
        )
        model.check_values(state, spec)
        state = checked_step(state, spec.execution.dt / 4, controls, layout)


def evolve(spec, divisor=1):
    raw = schema.to_dict(spec)
    events = {0.0, spec.experiment.end_time, *(change.time for change in spec.experiment.changes)}
    dt = spec.execution.dt / divisor
    events.update(
        index * dt
        for index in range(int(np.ceil(spec.experiment.end_time / dt)))
        if index * dt < spec.experiment.end_time
    )
    times = sorted(events)
    state, layout = model.initial_values(spec)
    states = [state]
    for left, right in zip(times[:-1], times[1:], strict=True):
        state = checked_step(state, right - left, control(spec, left), layout)
        model.check_values(state, spec)
        states.append(state)
    context = reference.bind(raw)
    compact = np.stack([reference.flatten(context, value._asdict()) for value in states])
    return np.asarray(times), compact, states[-1]


@pytest.mark.parametrize("arm", ["active", "reverse", "mixed"])
def test_short_full46_histories_oracle_tightening_and_actual_event_boundary(arm):
    spec = schema.parse(fixtures.probe(arm))
    raw = schema.to_dict(spec)
    context = reference.bind(raw)
    standard = reference.integrate(raw, max_step_s=spec.execution.dt)
    tight = reference.integrate(raw, refinement=2, max_step_s=spec.execution.dt)
    target = tight["state"]
    bound = budget(context, target)
    uncertainty = float(np.max(np.abs(standard["state"] - target) / bound, initial=0))
    errors, arrays = {}, dict(oracle=target, standard=standard["state"], budget=bound)
    for divisor in (1, 2):
        times, values, state = evolve(spec, divisor)
        selected = [list(times).index(time) for time in raw["experiment"]["observation_times"]]
        error = values[selected] - target
        errors[str(divisor)] = float(np.max(np.abs(error) / bound, initial=0))
        arrays.update(
            {
                "dt" + str(divisor) + "_times": times,
                "dt" + str(divisor) + "_state": values,
                "dt" + str(divisor) + "_error": error,
            }
        )
        endpoint = reference.endpoint_balance(
            context, reference.flatten(context, state._asdict()), time=spec.experiment.end_time
        )
        assert abs(endpoint["balance_pJ"]) <= 1e-10
        material = reference.material_balance(context, reference.flatten(context, state._asdict()))
        assert all(np.max(np.abs(value), initial=0) <= 2e-12 for value in material.values())
    evidence(
        "short-history-" + arm,
        dict(
            definition=raw,
            full_fields=46,
            oracle_uncertainty_fraction=uncertainty,
            accuracy=errors,
            scope=(
                "two original nominal steps with exact route-only boundary; no settling/order claim"
            ),
        ),
        arrays,
    )
    assert uncertainty <= 0.1
    assert all(value <= 1.0 for value in errors.values())
    assert errors["2"] <= errors["1"] or max(errors.values()) <= 0.01
    assert 0.75 * spec.execution.dt in standard["event_times"]


@pytest.mark.parametrize("fault", ["foreign_pool", "standard_bridge", "two_atp", "external_supply"])
def test_independent_owner_stoichiometry_and_standard_refusals(fault):
    raw = fixtures.probe()
    row = raw["model"]["network_transport"]["routes"][0]
    if fault == "foreign_pool":
        row["drive"]["pool_id"] = "fuel_cell_1"
    elif fault == "standard_bridge":
        row["configuration"]["standard free energy"] -= reference.R * 298.15 * np.log(1000)
    elif fault == "two_atp":
        row["configuration"]["reactant multipliers"][-1] = 2
    else:
        row["drive"]["supplied_energy_J_per_mol"] = 37000
    with pytest.raises(ValueError):
        reference.bind(raw)


def test_independent_signed_native_rate_refuses_negative_physical_heat():
    raw = fixtures.probe()
    for row in raw["model"]["network_transport"]["routes"]:
        row["configuration"].update(
            {"transporter inhibitors": ["ATP&"], "inhibitor Km": [1.0], "inhibitor n": [1.0]}
        )
    context = reference.bind(raw)
    with pytest.raises(ValueError, match="negative physical dissipation"):
        reference.evaluate(context, reference.initial(context), 0.0)
