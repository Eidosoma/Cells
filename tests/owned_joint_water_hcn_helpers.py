"""Component-only complete-owner fixtures and retained scientific arrays."""

import json
import os
from dataclasses import replace
from pathlib import Path

import numpy as np

from cells.core import surface_calcium_energy_water_hcn_extra_spec as water_spec
from cells.core import surface_calcium_energy_water_repair_hcn_extra_spec as repair_spec
from cells.core.grid import EventGrid
from cells.core.schedule import control_values
from cells.models import surface_calcium_energy_water_hcn_extra as water
from cells.models import surface_calcium_energy_water_repair_hcn_extra as repair
from cells.numerics.fixed_step import rk4_step
from validation.tissue import calcium_energy_water_hcn_extra_fixtures as water_inputs
from validation.tissue import calcium_energy_water_hcn_extra_reference as water_ref
from validation.tissue import calcium_energy_water_repair_hcn_extra_fixtures as repair_inputs
from validation.tissue import calcium_energy_water_repair_hcn_extra_reference as repair_ref

FAMILIES = dict(
    water=(water_spec, water, water_inputs, water_ref),
    repair=(repair_spec, repair, repair_inputs, repair_ref),
)


def evidence(name, value, arrays=None):
    if not (destination := os.environ.get("CELLS_COMPONENT_EVIDENCE")):
        return
    path = Path(destination) / ("joint-water-hcn-" + name)
    path.parent.mkdir(parents=True, exist_ok=True)
    if arrays is not None:
        np.savez_compressed(path.with_suffix(".npz"), **arrays)
        value = dict(value, arrays_file=path.with_suffix(".npz").name)
    path.with_suffix(".json").write_text(
        json.dumps(
            dict(value, status=value.get("status", "passed")),
            indent=2,
            allow_nan=False,
            default=lambda v: v.tolist(),
        )
        + "\n"
    )


def control(spec, time):
    table = control_values(spec, [time])
    return type(table)(*(v[0] for v in table))


def initial(family, arm=None, *, padded=True, time=0.0):
    schema, model, inputs, _ = FAMILIES[family]
    raw = inputs.definition(arm or ("open" if family == "water" else "preinjured"), padded=padded)
    spec = schema.parse(raw)
    state, layout = model.initial_values(spec)
    return raw, spec, state, layout, control(spec, time)


def changed(spec, state, p, *, water_enabled=True):
    """Manufactured in-domain stage; not a claimed integrated ledger history."""
    value = type(state)(*(v.copy() for v in state))
    names = [s.id for s in spec.model.stores[0].species]
    select = [names.index(k) for k in ("Ca", "B", "CaB")]
    value.chemical_amount_increment[0, select, int(p.er_cytosol[0])] += 1e-4 * np.asarray(
        [-1, -1, 1]
    )
    extent = 0.1 * p.energy_initial_amount_fmol[0, 0]
    value.energy_amount_increment_fmol[:, 0] = [-extent, extent, extent]
    for i, row in enumerate(spec.model.channels):
        arity = len(row.initial_gate)
        value.channel_gate[:, i] = [0.31 if arity else 0.0, 0.63 if arity == 2 else 0.0]
    if water_enabled:
        patch = int(np.flatnonzero(p.membrane_active)[0])
        value.volume_increment_pL[p.membrane_cell[patch]] += 0.08
        value.extracellular_volume_increment_pL[p.membrane_outside[patch]] -= 0.08
        value.water_transferred_pL[patch] -= 0.08
    if hasattr(value, "damage"):
        value.damage[0] += 0.15
        value.damage_opened[0] += 0.15
    return value


def score(reference, context, actual, expected, *, rhs=False):
    floors = {
        key: np.full(
            shape, (3e-23 if rhs else 3e-25) if key.endswith("_C") else (3e-12 if rhs else 2e-11)
        )
        for key, shape in context["shapes"].items()
    }
    budget = reference.flatten(context, floors) + (3e-10 if rhs else 3e-9) * np.abs(expected)
    return float(np.max(np.abs(actual - expected) / budget, initial=0))


def stage(family, raw, spec, state, layout, time):
    _, model, _, reference = FAMILIES[family]
    c = reference.bind(raw)
    expected, phi, proof = reference.evaluate(c, reference.flatten(c, state._asdict()), time)
    value = model.readouts(state, control(spec, time), layout, xp=np)
    observed = reference.flatten(c, value.derivative._asdict())
    ratio = score(reference, c, observed, expected, rhs=True)
    assert ratio <= 1, ratio
    n = layout.active.size
    actual_phi = np.r_[
        value.field.potential_V[:n][layout.active],
        value.field.potential_V[n:][layout.outside_active],
    ]
    np.testing.assert_allclose(actual_phi, phi, rtol=3e-10, atol=3e-13)
    assert value.valid and abs(value.field.energy_balance_pJ_s) < 1e-9
    assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-9
    return dict(time_s=time, error_over_budget=ratio, independent=proof), value


def integrate(spec, model):
    state, p = model.initial_values(spec)
    times = np.asarray(list(EventGrid(spec)))
    table = control_values(spec, times[:-1])
    model.check_steps(spec, np.diff(times), table)
    history = [state]
    for i, h in enumerate(np.diff(times)):
        u = type(table)(*(v[i] for v in table))
        state = rk4_step(lambda y, *args: model.rhs(y, *args, xp=np), state, h, u, p, p.active)
        history.append(state)
    values = model.STATE_TYPE(*(np.stack(v) for v in zip(*history, strict=True)))
    return times, values, p, model.check_values(values, spec)


def refinement(family):
    schema, model, inputs, reference = FAMILIES[family]
    raw = inputs.compact_probe(padded=False)
    # Resolve damage/water/control transients rather than counting endpoint
    # cancellation as a convergence result. Admission remains unchanged.
    raw["execution"].update(dt=0.625e-6, max_steps=2048)
    spec = schema.parse(raw)
    context = reference.bind(schema.to_dict(spec))
    exact = reference.integrate(schema.to_dict(spec), refinement=2, max_step_s=0.625e-6)
    expected = np.asarray(exact["state"])
    observed_times = np.asarray(exact["times"])
    arrays = dict(
        reference_flat=expected,
        times_s=observed_times,
        reference_shapes_json=np.asarray(json.dumps(context["shapes"])),
        state_fields=np.asarray(list(context["shapes"])),
    )
    rows = []
    for factor in (1, 2):
        current = replace(spec, execution=replace(spec.execution, dt=spec.execution.dt / factor))
        times, history, p, diagnostics = integrate(current, model)
        indexes = [EventGrid(current).exact_index(t) for t in observed_times]
        observed = np.stack(
            [
                reference.flatten(context, model.STATE_TYPE(*(v[i] for v in history))._asdict())
                for i in indexes
            ]
        )
        ratio = score(reference, context, observed, expected)
        arrays["production_flat_" + str(factor)] = observed
        arrays.update(
            {
                str(factor) + "__" + key: np.asarray(getattr(history, key))[indexes]
                for key in model.STATE_TYPE._fields
            }
        )
        row = dict(
            dt_s=current.execution.dt,
            error_over_budget=ratio,
            max_error=float(np.max(np.abs(observed - expected))),
            diagnostics=diagnostics,
        )
        independent_energy = []
        for time, flat in zip(observed_times, observed, strict=True):
            values = reference.unpack(context, flat)
            stored = reference.free_energy_change(context, flat, float(time))
            heat = sum(
                float(np.sum(v))
                for key, v in values.items()
                if key.endswith("_dissipated_energy_pJ")
            )
            work = sum(
                float(np.sum(values[key]))
                for key in (
                    "regeneration_supplied_work_pJ",
                    "reservoir_work_pJ",
                    "electrode_work_pJ",
                )
            )
            independent_energy.append(stored + heat - work)
        row["independent_energy_residual_pJ"] = independent_energy
        rows.append(row)
        if ratio > 1 or np.max(np.abs(independent_energy)) > 1e-9:
            evidence(
                "trajectory-" + family + "-failure",
                dict(
                    status="failed",
                    inputs=raw,
                    reason="unchanged trajectory budget",
                    refinements=rows,
                ),
                arrays,
            )
        assert ratio <= 1, ratio
        np.testing.assert_allclose(independent_energy, 0, rtol=0, atol=1e-9)
        observations = model.observe_history(times, history, p, observed_times, current)
        for key in model.STATE_TYPE._fields:
            np.testing.assert_array_equal(
                getattr(observations, key), getattr(history, key)[indexes]
            )
        assert np.any(history.volume_increment_pL[-1] != 0)
        assert np.any(history.energy_amount_increment_fmol[-1] != 0)
    assert rows[-1]["max_error"] <= max(0.3 * rows[0]["max_error"], 3e-13)
    evidence(
        "trajectory-" + family,
        dict(
            inputs=raw,
            all_observations_compared=True,
            observation_times_s=observed_times,
            refinements=rows,
            reference={k: v for k, v in exact.items() if k not in ("state", "potential_V")},
            original_material_and_work_ledgers=True,
            endpoint_only_claim=False,
            refinement_mode=(
                "precision_floor"
                if max(v["max_error"] for v in rows) <= 3e-13
                else "resolved_reduction"
            ),
            convergence_order_claim=False,
        ),
        arrays,
    )
