"""Full ordinary RHS/readout views, independent owners, controls and side effects."""

import json
import os
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.core import physiology_perturbation_step as step
from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as units
from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.models import physiology_permeability_view as view
from cells.numerics.fixed_step import rk4_step
from cells.processes import betse_perturbations as perturb
from tests.unit.test_physiology_tissue_binding import arguments, component_state, definition
from validation.tissue import physiology_permeability_view_reference as reference

KINDS = ("passive", "ionic", "calcium", "fuel")


def evidence(name, record, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(directory) / "permeability-view"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (name + ".json")).write_text(
            json.dumps(
                record, indent=2, allow_nan=False, default=lambda value: np.asarray(value).tolist()
            )
            + "\n"
        )
        if arrays is not None:
            np.savez_compressed(folder / (name + ".npz"), **arrays)


def case(kind="passive", *, padded=True, changed=True):
    spec = parse_spec(definition(kind, padded=padded, reorder=not padded))
    args = arguments(spec, reverse=True)
    # Power-of-two thicknesses give a literal, bit-exact unchanged-P case.
    args["membrane_thickness_m"] = {
        row.id: 2.0 ** (-28 - i % 3) for i, row in enumerate(spec.model.membranes)
    }
    binding = units.bind_tissue(spec, **args)
    component = component_state(binding)
    diffusion = component.diffusion.base_m2_s
    factor = 1.0
    if changed:
        factor = 1.0 + 0.07 * np.arange(1, diffusion.size + 1).reshape(diffusion.shape)
    component = replace(
        component,
        controls=replace(component.controls, phase="SIM"),
        diffusion=component.diffusion._replace(current_m2_s=diffusion * factor),
    )
    implementation = view.IMPLEMENTATIONS[type(spec.model)]
    state, layout = implementation.initial_values(spec)
    table = control_values(spec, [0.0])
    # Explicit, valid held controls need not match a scheduled clock position.
    controls = type(table)(*(value[0] * 0.67 for value in table))
    return spec, binding, component, implementation, state, layout, controls


def readouts(implementation, state, control, layout):
    if implementation is view.passive:
        field = implementation.field_values(state, control, layout, xp=np)
        return field, implementation.derivative_from_field(field, layout, xp=np)
    result = implementation.readouts(state, control, layout, xp=np)
    return result, result.derivative


def exact_tree(actual, expected):
    a, b = jax.tree.leaves(actual), jax.tree.leaves(expected)
    assert len(a) == len(b)
    for x, y in zip(a, b, strict=True):
        np.testing.assert_array_equal(x, y, strict=True)


def fingerprints(spec, state, layout, component):
    def arrays(values):
        return tuple(
            (value.dtype.str, value.shape, value.tobytes(), value.flags.writeable)
            for value in values
        )

    return (
        json.dumps(spec.to_dict(), sort_keys=True),
        arrays(state),
        arrays(layout),
        arrays((*component.protein, *component.diffusion)),
        component.controls,
        component.time_s,
        component.loop_calls,
        streams.stream_record(component.stream),
    )


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("padded", [False, True])
@pytest.mark.parametrize("changed", [False, True])
def test_full_initial_and_evolved_RHS_readouts_match_independent_physical_owners(
    kind, padded, changed
):
    spec, binding, component, implementation, state, layout, controls = case(
        kind, padded=padded, changed=changed
    )
    raw, record = spec.to_dict(), units.binding_record(binding)
    h = spec.execution.dt / 16
    for stage in range(2):
        before = fingerprints(spec, state, layout, component)
        actual = view.evaluate(spec, state, layout, controls, binding, component, step_s=h)
        context, target, phi, proof = reference.evaluate(
            raw, state._asdict(), record, component.diffusion.current_m2_s, controls._asdict()
        )
        oracle = reference.ORACLES[raw["model"]["id"]]
        packed = oracle.flatten(context, actual.derivative._asdict())
        atol = oracle.flatten(
            context,
            {
                key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
                for key, shape in context["shapes"].items()
            },
        )
        budget = atol + 3e-10 * np.abs(target)
        ratio = float(np.max(np.abs(packed - target) / budget, initial=0))
        field = actual.field
        p = actual.runtime_layout
        potential = np.r_[
            field.potential_V[: p.active.size][p.active],
            field.potential_V[p.active.size :][p.outside_active],
        ]
        evidence(
            "stage-" + kind + "-" + str(padded) + "-" + str(changed) + "-" + str(stage),
            dict(
                definition=raw,
                binding=record,
                fields=state._asdict(),
                component_current_D_m2_s=component.diffusion.current_m2_s,
                held_control=controls._asdict(),
                proposed_step_s=h,
                max_error_over_budget=ratio,
                full_state_fields=len(state),
                proof=proof,
                passive_fraction=actual.admission["passive_fraction"],
                fuel_fraction=actual.admission["fuel_fraction"],
            ),
            dict(
                actual_rate=packed,
                expected_rate=target,
                budget=budget,
                signed_error=packed - target,
                actual_phi=potential,
                expected_phi=phi,
            ),
        )
        assert ratio <= 1 and len(context["shapes"]) == len(state)
        np.testing.assert_allclose(potential, phi, rtol=3e-10, atol=3e-13)
        assert abs(float(field.energy_balance_pJ_s)) <= 1e-10
        expected, derivative = readouts(implementation, state, controls, actual.runtime_layout)
        exact_tree(actual.readouts, expected)
        exact_tree(actual.derivative, derivative)
        assert fingerprints(spec, state, layout, component) == before
        assert actual.admission["step_s"] == h
        exact_tree(actual.admission["held_control"], controls)
        for name in layout._fields:
            if name != "membrane_permeability":
                np.testing.assert_array_equal(
                    getattr(actual.runtime_layout, name), getattr(layout, name), strict=True
                )
        if not changed:
            np.testing.assert_array_equal(
                actual.runtime_layout.membrane_permeability,
                layout.membrane_permeability,
                strict=True,
            )
            expected, derivative = readouts(implementation, state, controls, layout)
            exact_tree(actual.readouts, expected)
            exact_tree(actual.derivative, derivative)
            assert dict(actual.admission["original_balance_checks"]) == (
                implementation.check_values(state, spec)
            )
        if kind == "fuel":
            values = oracle.unpack(context, target)
            owners = [
                *context["patch_owners"],
                *context["plasma_owners"],
                *range(len(context["cell_ids"])),
            ]
            cycles = [
                *values["pump_cycles"],
                *values["plasma_pump_cycles"],
                *values["er_pump_transferred"][:, 0],
            ]
            gross = np.zeros(len(context["cell_ids"]))
            for owner, cycle in zip(owners, cycles, strict=True):
                gross[owner] += abs(cycle)
            pools = {row["id"]: row["cell_id"] for row in raw["model"]["energy_pools"]}
            for port, cycle in zip(
                raw["model"]["regeneration_ports"], values["regeneration_cycles_fmol"], strict=True
            ):
                gross[context["cell_ids"].index(pools[port["pool_id"]])] += abs(cycle)
            amount = (
                context["energy_initial"]
                + oracle.unpack(context, oracle.flatten(context, state._asdict()))[
                    "energy_amount_increment_fmol"
                ]
            )
            fraction = h * np.max(gross / np.min(amount, axis=0), initial=0)
            assert actual.admission["fuel_fraction"] == pytest.approx(
                fraction, rel=3e-10, abs=3e-14
            )
        if stage == 0:
            state = rk4_step(
                lambda value, held, params, active: implementation.rhs(
                    value, held, params, active, xp=np
                ),
                state,
                h,
                controls,
                layout,
                layout.active,
            )
            implementation.check_values(state, spec)


def test_no_draw_finalization_clock_advance_checkpoint_rewrite_or_protein_charge(monkeypatch):
    spec, binding, component, _, state, layout, controls = case("fuel")
    before = fingerprints(spec, state, layout, component)

    def forbidden(*args, **kwargs):
        pytest.fail("A read-only permeability view performed a physiological update")

    with monkeypatch.context() as guard:
        for module, name in (
            (streams, "draw"),
            (perturb, "sample_native"),
            (perturb, "sample_stable"),
            (perturb, "finalize_scheduled"),
            (step, "advance"),
        ):
            guard.setattr(module, name, forbidden)
        actual = view.evaluate(
            spec, state, layout, controls, binding, component, step_s=spec.execution.dt / 16
        )
        other = replace(
            component,
            protein=perturb.ProteinState(*(value * 17 for value in component.protein)),
            time_s=0.012,
            loop_calls=6,
        )
        again = view.evaluate(
            spec, state, layout, controls, binding, other, step_s=spec.execution.dt / 16
        )
    assert fingerprints(spec, state, layout, component) == before
    exact_tree(actual.readouts, again.readouts)
    exact_tree(actual.derivative, again.derivative)
    assert again.admission["component_time_s"] == 0.012
    assert again.admission["component_loop_calls"] == 6
    assert not np.array_equal(
        actual.physical_permeability.current_m_s,
        actual.physical_permeability.base_m_s + actual.physical_permeability.scheduled_m_s,
    )


@pytest.mark.parametrize("kind", ["ionic", "calcium", "fuel"])
def test_zero_passive_P_preserves_active_channel_and_pump_parameters_and_rates(kind):
    spec, binding, component, _, state, layout, controls = case(kind)
    component = replace(
        component,
        diffusion=component.diffusion._replace(
            current_m2_s=np.zeros_like(component.diffusion.current_m2_s)
        ),
    )
    actual = view.evaluate(
        spec, state, layout, controls, binding, component, step_s=spec.execution.dt / 16
    )
    np.testing.assert_array_equal(actual.runtime_layout.membrane_permeability, 0)
    assert np.any(actual.derivative.channel_transferred != 0)
    assert np.any(actual.derivative.pump_cycles != 0)
    for key in ("channel_permeability", "channel_abundance", "pump_capacity"):
        np.testing.assert_array_equal(getattr(actual.runtime_layout, key), getattr(layout, key))


def test_zero_P_with_old_transfer_history_refuses_the_existing_structural_limitation():
    spec, binding, component, implementation, state, layout, controls = case()
    state = rk4_step(
        lambda value, held, params, active: implementation.rhs(value, held, params, active, xp=np),
        state,
        spec.execution.dt / 16,
        controls,
        layout,
        layout.active,
    )
    assert np.any(state.membrane_transferred != 0)
    component = replace(
        component,
        diffusion=component.diffusion._replace(
            current_m2_s=np.zeros_like(component.diffusion.current_m2_s)
        ),
    )
    with pytest.raises(NumericalError, match="state/ledger domain"):
        view.evaluate(
            spec, state, layout, controls, binding, component, step_s=spec.execution.dt / 16
        )


@pytest.mark.parametrize("step_s", [0.0, -1.0, np.nan, np.inf, True, 0.001])
def test_invalid_or_over_nominal_explicit_step_refuses(step_s):
    spec, binding, component, _, state, layout, controls = case()
    with pytest.raises(ValueError):
        view.evaluate(spec, state, layout, controls, binding, component, step_s=step_s)


def test_actual_gross_passive_transfer_requires_a_smaller_step_without_netting_owners():
    spec, binding, component, _, state, layout, controls = case()
    component = replace(
        component,
        diffusion=component.diffusion._replace(current_m2_s=component.diffusion.current_m2_s * 1e6),
    )
    with pytest.raises(NumericalError, match="gross-turnover"):
        view.evaluate(spec, state, layout, controls, binding, component, step_s=spec.execution.dt)


@pytest.mark.parametrize("fault", ["area", "volume", "owner", "anchor", "active_channel", "P"])
def test_mismatched_source_layout_geometry_owner_anchor_or_parameters_refuse(fault):
    spec, binding, component, _, state, layout, controls = case("fuel")
    key = {
        "area": "membrane_area",
        "volume": "volume",
        "owner": "membrane_cell",
        "anchor": "amount_reference",
        "active_channel": "channel_permeability",
        "P": "membrane_permeability",
    }[fault]
    values = np.array(getattr(layout, key), copy=True)
    values.flat[0] += 1
    bad = layout._replace(**{key: values})
    with pytest.raises(ValueError, match="mismatch"):
        view.evaluate(spec, state, bad, controls, binding, component, step_s=spec.execution.dt / 16)


@pytest.mark.parametrize(
    "fault",
    [
        "control_shape",
        "control_range",
        "state_shape",
        "state_precision",
        "component_stream",
        "component_P",
        "source_definition",
    ],
)
def test_bad_actual_control_state_component_or_complete_source_refuses(fault):
    spec, binding, component, _, state, layout, controls = case("fuel")
    if fault == "control_shape":
        controls = controls._replace(membrane=controls.membrane[:-1])
    elif fault == "control_range":
        controls = controls._replace(membrane=np.full_like(controls.membrane, 1.1))
    elif fault == "state_shape":
        state = state._replace(amount_increment=state.amount_increment.T)
    elif fault == "state_precision":
        state = state._replace(amount_increment=state.amount_increment.astype(np.float32))
    elif fault == "component_stream":
        component = replace(component, stream=replace(component.stream, layout_identity="0" * 64))
    elif fault == "component_P":
        values = component.diffusion.current_m2_s.copy()
        values.flat[0] = -1
        component = replace(component, diffusion=component.diffusion._replace(current_m2_s=values))
    else:
        spec = replace(
            spec, execution=replace(spec.execution, max_steps=spec.execution.max_steps + 1)
        )
    with pytest.raises((ValueError, ConfigError, NumericalError)):
        view.evaluate(
            spec, state, layout, controls, binding, component, step_s=spec.execution.dt / 16
        )


def test_all_runtime_readout_derivative_permeability_and_admission_arrays_are_immutable():
    spec, binding, component, _, state, layout, controls = case("fuel")
    actual = view.evaluate(
        spec, state, layout, controls, binding, component, step_s=spec.execution.dt / 16
    )
    for value in jax.tree.leaves(
        (
            actual.runtime_layout,
            actual.readouts,
            actual.derivative,
            actual.admission["held_control"],
        )
    ):
        with pytest.raises(ValueError):
            value.setflags(write=True)
    with pytest.raises(TypeError):
        actual.admission["step_s"] = 1
    with pytest.raises(FrozenInstanceError):
        actual.runtime_layout = layout


def test_independent_reference_rejects_foreign_source_units_or_component_axes():
    spec, binding, component, _, state, _, controls = case()
    record = units.binding_record(binding)
    record["geometry"]["cell_volume_m3"][0] *= 2
    record["identity"] = reference._digest({k: v for k, v in record.items() if k != "identity"})
    with pytest.raises(ValueError, match="geometry"):
        reference.evaluate(
            spec.to_dict(),
            state._asdict(),
            record,
            component.diffusion.current_m2_s,
            controls._asdict(),
        )
