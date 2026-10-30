"""Complete full56 array rates, point certificates and staged CPU JAX execution."""

import json
import os
from dataclasses import replace
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells import io as numeric_io
from cells.core import physiology_active_temperature_arrays as prepared
from cells.core.state import Checkpoint
from cells.models import physiology_active_temperature_arrays as arrays
from cells.models import physiology_active_temperature_view as host
from cells.numerics.fixed_step import rk4_step
from tests.unit.test_physiology_active_temperature import KINDS, serial, setup
from validation.tissue import physiology_active_temperature_arrays_reference as reference

FAMILIES = dict(
    ionic="resolved_tissue@12",
    calcium="resolved_calcium@11",
    fuel="resolved_calcium_energy@5",
    **{"open-calcium": "resolved_open_calcium@1", "open-fuel": "resolved_open_calcium_energy@1"},
)


def fixtures(kind, *, count=3):
    cases, worlds, proposals = [], [], []
    for i in range(count):
        case = setup(kind, padded=True, temperature_K=(273.15, 298.15, 310.15)[i])
        spec, model, state, layout, control, binding, memory = case
        if i:
            state = rk4_step(
                lambda y, u, p, a, model=model: model.rhs(y, u, p, a, xp=np),
                state,
                spec.execution.dt / 16,
                control,
                layout,
                layout.active,
            )
        control = type(control)(*(value * (1 - 0.15 * i) for value in control))
        case = (spec, model, state, layout, control, binding, memory)
        cases.append(case)
        worlds.append(
            prepared.prepare_world(
                spec,
                state,
                layout,
                binding,
                temperature_K=float(memory.temperature_K),
                step_s=spec.execution.dt / 16,
                world_id=f"{kind}-world-{i}",
            )
        )
        proposals.append(
            arrays.Proposal(memory.temperature_K, control, np.asarray(spec.execution.dt / 16))
        )
    return (
        cases,
        prepared.prepare_cohort(worlds),
        jax.tree.map(lambda *values: np.stack(values), *proposals),
    )


def evidence(name, record, columns=None):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(folder) / "active-temperature-arrays"
        root.mkdir(parents=True, exist_ok=True)
        with (root / (name + ".json")).open("x") as stream:
            json.dump(
                record,
                stream,
                indent=2,
                allow_nan=False,
                default=lambda value: np.asarray(value).tolist(),
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if columns is not None:
            np.savez_compressed(root / (name + ".npz"), **columns)


def check_world(case, world, proposal, actual, name):
    spec, _, state, _, _, binding, _ = case
    inputs = dict(
        raw=spec.to_dict(),
        fields=serial(state),
        binding_record=host.contract.record(binding),
        certified_temperature_K=float(world.certificate.temperature_K),
        maximum_step_s=float(world.certificate.maximum_step_s),
        proposal=dict(
            temperature_K=float(proposal.temperature_K),
            step_s=float(proposal.step_s),
            control=serial(proposal.control),
        ),
    )
    context, target, phi, proof = reference.evaluate(**inputs)
    rate = reference.held.flatten(context, actual.derivative._asdict())
    absolute = reference.held.flatten(
        context,
        {
            key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
            for key, shape in context["shapes"].items()
        },
    )
    budget = absolute + 3e-10 * abs(target)
    rate_error = float(np.max(abs(rate - target) / budget, initial=0))
    p, field = actual.arithmetic_runtime_layout, actual.readouts.field
    n, o = (
        context["shapes"]["amount_increment"][-1],
        context["shapes"]["extracellular_amount_increment"][-1],
    )
    potential = np.r_[field.potential_V[:n], field.potential_V[p.active.size : p.active.size + o]]
    phi_budget = 3e-13 + 3e-10 * abs(phi)
    phi_error = float(np.max(abs(potential - phi) / phi_budget, initial=0))
    field_error, saved = 0.0, {}
    for key, column in proof["physical_field_columns"].items():
        value = field
        for part in key.split("."):
            value = getattr(value, part)
        value, target_value = np.asarray(value), np.asarray(column["value"])
        if key in ("capacitor_node_charge_C", "charge_residual_C"):
            value = np.r_[value[:n], value[p.active.size : p.active.size + o]]
        elif target_value.ndim:
            value = value[tuple(slice(0, size) for size in target_value.shape)]
        saved["field__" + key.replace(".", "__")] = value
        field_error = max(
            field_error,
            float(
                np.max(
                    abs(value - target_value)
                    / (column["atol"] + column["rtol"] * abs(target_value)),
                    initial=0,
                )
            ),
        )
    evidence(
        name,
        dict(
            inputs=inputs,
            reference=proof,
            rate_error_fraction=rate_error,
            potential_error_fraction=phi_error,
            physical_field_error_fraction=field_error,
            reason_mask=int(actual.reason_mask),
            valid=bool(actual.valid),
            certificate_temperature_K=float(world.certificate.temperature_K),
            backend=jax.default_backend(),
            x64=bool(jax.config.x64_enabled),
        ),
        dict(
            actual_rate=rate,
            expected_rate=target,
            rate_budget=budget,
            actual_phi=potential,
            expected_phi=phi,
            phi_budget=phi_budget,
            **saved,
        ),
    )
    assert max(rate_error, phi_error, field_error) <= 1
    assert actual.valid and int(actual.reason_mask) == 0


@pytest.mark.parametrize("kind", KINDS)
def test_numpy_full_cohort_matches_serial_host_independent_complete_fields_and_rates(kind):
    cases, cohort, proposals = fixtures(kind)
    prepared.validate_cohort(cohort)
    result = arrays.evaluate_batch(cohort.numeric, proposals, family=cohort.family, xp=np)
    for i, case in enumerate(cases):
        actual = jax.tree.map(lambda value, i=i: np.asarray(value[i]), result)
        raw = jax.tree.map(lambda value, i=i: value[i], proposals)
        check_world(case, cohort.worlds[i], raw, actual, f"numpy-{kind}-{i}")
        spec, _, state, layout, control, binding, memory = case
        expected = host.evaluate(
            spec,
            state,
            layout,
            control,
            binding,
            memory,
            time_s=0.4,
            events_enabled=False,
            step_s=spec.execution.dt / 16,
        )
        for first, second in zip(
            jax.tree.leaves(actual.readouts), jax.tree.leaves(expected.readouts), strict=True
        ):
            np.testing.assert_allclose(first, second, atol=3e-12, rtol=3e-10)


@pytest.mark.parametrize("kind", KINDS)
def test_reordered_and_partitioned_cohorts_keep_each_original_world(kind):
    _, cohort, proposal = fixtures(kind)
    forward = arrays.evaluate_batch(cohort.numeric, proposal, family=cohort.family, xp=np)
    reverse = prepared.prepare_cohort(cohort.worlds[::-1])
    reversed_values = arrays.evaluate_batch(
        reverse.numeric,
        jax.tree.map(lambda value: value[::-1], proposal),
        family=cohort.family,
        xp=np,
    )
    partitions = []
    for indices in ((0,), (1, 2)):
        part = prepared.prepare_cohort(tuple(cohort.worlds[i] for i in indices))
        partitions.append(
            arrays.evaluate_batch(
                part.numeric,
                jax.tree.map(lambda value, indices=indices: value[list(indices)], proposal),
                family=cohort.family,
                xp=np,
            )
        )
    joined = jax.tree.map(lambda *values: np.concatenate(values), *partitions)
    for a, b, c in zip(
        jax.tree.leaves(forward),
        jax.tree.leaves(reversed_values),
        jax.tree.leaves(joined),
        strict=True,
    ):
        np.testing.assert_array_equal(a, b[::-1])
        np.testing.assert_array_equal(a, c)
    evidence(
        "cohort-invariance-" + kind,
        dict(
            kind="reorder_partition",
            cohort=prepared.record(cohort),
            reversed_world_ids=[world.world_id for world in reverse.worlds],
            partitions=[
                [world.world_id for world in cohort.worlds[:1]],
                [world.world_id for world in cohort.worlds[1:]],
            ],
            all_numeric_fields_exact=True,
        ),
    )


@pytest.mark.parametrize("kind", KINDS)
def test_invalid_numeric_proposals_are_retained_and_explicitly_flagged(kind):
    _, cohort, proposal = fixtures(kind, count=1)
    n = jax.tree.map(lambda value: value[0], cohort.numeric)
    raw = jax.tree.map(lambda value: value[0], proposal)
    for i, temperature in enumerate((0.0, -1.0, float("nan"), float("inf"), 273.16)):
        changed = raw._replace(temperature_K=np.asarray(temperature))
        with np.errstate(all="ignore"):
            actual = arrays.evaluate_world(
                n.state, n.layout, n.certificate, changed, family=cohort.family, xp=np
            )
        assert not actual.valid and actual.arithmetic_substitution and int(actual.reason_mask) & 4
        np.testing.assert_array_equal(actual.raw_proposal.temperature_K, changed.temperature_K)
        assert float(actual.arithmetic_runtime_layout.temperature) == float(
            n.certificate.temperature_K
        )
        evidence(
            f"invalid-T-{kind}-{i}",
            dict(
                kind="raw_invalid_proposal",
                reason_mask=int(actual.reason_mask),
                reason_validity=actual.reason_validity.tolist(),
                proposal_retained=True,
                arithmetic_substitution=True,
            ),
            dict(
                raw_temperature_K=changed.temperature_K,
                recorded_temperature_K=actual.raw_proposal.temperature_K,
                raw_runtime_temperature=actual.raw_runtime_layout.temperature,
                **{
                    "raw_runtime__" + key: value
                    for key, value in actual.raw_runtime_layout._asdict().items()
                },
            ),
        )
    controls = raw.control._replace(membrane=np.full_like(raw.control.membrane, 2.0))
    actual = arrays.evaluate_world(
        n.state,
        n.layout,
        n.certificate,
        raw._replace(control=controls, step_s=n.certificate.maximum_step_s * 2),
        family=cohort.family,
        xp=np,
    )
    assert (
        not actual.valid
        and int(actual.reason_mask) & (1 << 3)
        and int(actual.reason_mask) & (1 << 5)
    )
    np.testing.assert_array_equal(actual.raw_proposal.control.membrane, controls.membrane)
    evidence(
        "invalid-control-" + kind,
        dict(
            kind="raw_invalid_proposal",
            reason_mask=int(actual.reason_mask),
            reason_validity=actual.reason_validity.tolist(),
            proposal_retained=True,
            arithmetic_substitution=True,
        ),
        dict(
            raw_control=controls.membrane,
            recorded_control=actual.raw_proposal.control.membrane,
            raw_step_s=actual.raw_proposal.step_s,
        ),
    )


def test_preparation_refuses_mixed_duplicate_and_resealed_numeric_cohorts():
    _, first, _ = fixtures("ionic", count=1)
    _, second, _ = fixtures("calcium", count=1)
    with pytest.raises(ValueError, match="family"):
        prepared.prepare_cohort((*first.worlds, *second.worlds))
    with pytest.raises(ValueError, match="distinct"):
        prepared.prepare_cohort(first.worlds * 2)
    changed = replace(
        first.worlds[0],
        certificate=first.worlds[0].certificate._replace(temperature_K=np.asarray(310.15)),
    )
    with pytest.raises(ValueError, match="changed"):
        prepared.prepare_cohort((changed,))


@pytest.mark.parametrize("kind", KINDS)
def test_restored_device_source_is_normalized_before_host_preparation(kind, tmp_path):
    case = setup(kind, padded=True, temperature_K=310.15)
    spec, _, state, layout, control, binding, memory = case
    path = numeric_io.write_snapshot(
        tmp_path / "original", spec, Checkpoint(state, layout, 0.0, 0, 0)
    )
    restored = numeric_io.load_snapshot(path)
    assert all(
        isinstance(value, jax.Array)
        for value in (*restored.checkpoint.state, *restored.checkpoint.layout)
    )
    world = prepared.prepare_world(
        restored.spec,
        restored.checkpoint.state,
        restored.checkpoint.layout,
        binding,
        temperature_K=310.15,
        step_s=spec.execution.dt / 16,
        world_id="restored-" + kind,
    )
    assert all(
        type(value) is np.ndarray and not value.flags.writeable
        for value in (*world.state, *world.layout)
    )
    for actual, original_value in zip(
        (*world.state, *world.layout), (*state, *layout), strict=True
    ):
        np.testing.assert_array_equal(actual, original_value, strict=True)
    proposal = arrays.Proposal(memory.temperature_K, control, np.asarray(spec.execution.dt / 16))
    actual = arrays.evaluate_world(
        world.state, world.layout, world.certificate, proposal, family=world.family, xp=np
    )
    check_world(case, world, proposal, actual, "restored-" + kind)


@pytest.mark.parametrize("kind", KINDS)
def test_exact_control_shape_protocol_refuses_broadcast_and_keeps_valid_full_rates(kind):
    cases, cohort, proposals = fixtures(kind, count=1)
    numeric = jax.tree.map(lambda value: value[0], cohort.numeric)
    proposal = jax.tree.map(lambda value: value[0], proposals)
    for name, value in proposal.control._asdict().items():
        bad_shape = (2,) if value.shape == (1,) else (1,)
        changed = proposal._replace(
            control=proposal.control._replace(**{name: np.zeros(bad_shape)})
        )
        for evaluate in (arrays.evaluate_world, arrays.evaluate_world_staged):
            with pytest.raises(ValueError, match="shape/type"):
                evaluate(
                    numeric.state,
                    numeric.layout,
                    numeric.certificate,
                    changed,
                    family=cohort.family,
                    xp=np,
                )
    actual = arrays.evaluate_world(
        numeric.state, numeric.layout, numeric.certificate, proposal, family=cohort.family, xp=np
    )
    check_world(cases[0], cohort.worlds[0], proposal, actual, "shape-valid-" + kind)


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("backend", ("numpy", "jax_shape"))
def test_complete_batch_axes_refuse_short_long_or_missing_worlds_before_any_physics(
    kind, backend, monkeypatch
):
    _, cohort, proposal = fixtures(kind)
    numeric = cohort.numeric

    def longer(value):
        return np.concatenate((value, value[:1]), axis=0)

    damaged = [
        (numeric, proposal._replace(temperature_K=proposal.temperature_K[:-1])),
        (numeric, proposal._replace(temperature_K=longer(proposal.temperature_K))),
        (numeric, proposal._replace(step_s=proposal.step_s[:-1])),
        (numeric, proposal._replace(step_s=longer(proposal.step_s))),
        (
            numeric,
            proposal._replace(control=jax.tree.map(lambda value: value[:-1], proposal.control)),
        ),
        (numeric, proposal._replace(control=jax.tree.map(longer, proposal.control))),
        (
            numeric,
            proposal._replace(
                control=proposal.control._replace(membrane=proposal.control.membrane[:-1])
            ),
        ),
        (numeric._replace(state=jax.tree.map(lambda value: value[:-1], numeric.state)), proposal),
        (numeric._replace(layout=jax.tree.map(lambda value: value[:-1], numeric.layout)), proposal),
        (
            numeric._replace(
                certificate=numeric.certificate._replace(
                    temperature_K=numeric.certificate.temperature_K[:-1]
                )
            ),
            proposal,
        ),
        (
            numeric._replace(
                state=numeric.state._replace(
                    amount_increment=longer(numeric.state.amount_increment)
                )
            ),
            proposal,
        ),
        (
            jax.tree.map(lambda value: value[:0], numeric),
            jax.tree.map(lambda value: value[:0], proposal),
        ),
    ]
    monkeypatch.setattr(
        arrays,
        "evaluate_world",
        lambda *a, **k: pytest.fail("A malformed cohort started prefix physics"),
    )
    monkeypatch.setattr(
        arrays,
        "prepare_numeric_world",
        lambda *a, **k: pytest.fail("A malformed staged cohort started prefix projection"),
    )
    declarations = []
    for bad_numeric, bad_proposal in damaged:
        declaration = dict(
            prepared_world_ids=[world.world_id for world in cohort.worlds],
            temperature_shape=list(bad_proposal.temperature_K.shape),
            step_shape=list(bad_proposal.step_s.shape),
            certificate_temperature_shape=list(bad_numeric.certificate.temperature_K.shape),
            certificate_step_shape=list(bad_numeric.certificate.maximum_step_s.shape),
            all_leaf_shapes=[
                list(value.shape) for value in jax.tree.leaves((bad_numeric, bad_proposal))
            ],
        )
        assert not reference.complete_world_axes(declaration)
        declarations.append(declaration)
        for evaluate in (arrays.evaluate_batch, arrays.evaluate_batch_staged):
            with pytest.raises(ValueError, match="batch|cohort|world"):
                if backend == "numpy":
                    evaluate(bad_numeric, bad_proposal, family=cohort.family, xp=np)
                else:
                    shaped_numeric, shaped_proposal = jax.tree.map(
                        lambda value: jax.ShapeDtypeStruct(value.shape, value.dtype),
                        (bad_numeric, bad_proposal),
                    )
                    jax.eval_shape(
                        lambda n, p, evaluate=evaluate: evaluate(
                            n, p, family=cohort.family, xp=jnp
                        ),
                        shaped_numeric,
                        shaped_proposal,
                    )
    evidence(
        "batch-axis-refusals-" + kind + "-" + backend,
        dict(
            kind="complete_batch_axis_protocol",
            family=cohort.family,
            backend=backend,
            malformed_cases=len(damaged),
            entrypoints=["evaluate_batch", "evaluate_batch_staged"],
            declarations=declarations,
            no_prefix_worlds_evaluated=True,
            array_physics_evaluated=False,
        ),
    )


def exact_tree(first, second):
    assert jax.tree.structure(first) == jax.tree.structure(second)
    for a, b in zip(jax.tree.leaves(first), jax.tree.leaves(second), strict=True):
        a, b = np.asarray(a), np.asarray(b)
        assert a.dtype == b.dtype and a.shape == b.shape
        np.testing.assert_array_equal(a, b)


def exact_staged_shared_outputs(staged, original):
    for name in arrays.Values._fields:
        if name != "readouts":
            exact_tree(getattr(staged, name), getattr(original, name))
    exact_tree(staged.readouts.field, original.readouts.field)
    exact_tree(staged.readouts.valid, original.readouts.valid)
    parent = original.readouts.parent if hasattr(original.readouts, "parent") else original.readouts
    if hasattr(staged.arithmetic_runtime_layout, "energy_initial_amount_fmol"):
        exact_tree(staged.readouts.gross_hydrolysis_fmol_s, parent.exchange.gross_hydrolysis_fmol_s)
        exact_tree(staged.readouts.gross_synthesis_fmol_s, parent.exchange.gross_synthesis_fmol_s)
    else:
        zeros = np.zeros_like(staged.arithmetic_runtime_layout.active, dtype=np.float64)
        exact_tree(staged.readouts.gross_hydrolysis_fmol_s, zeros)
        exact_tree(staged.readouts.gross_synthesis_fmol_s, zeros)


@pytest.mark.parametrize("kind", KINDS)
def test_numpy_separate_stages_keep_complete_fields_reasons_and_cohort_invariance(
    kind, monkeypatch
):
    cases, cohort, proposal = fixtures(kind)
    original = arrays.evaluate_batch(cohort.numeric, proposal, family=cohort.family, xp=np)
    for name in ("initial_values", "check_values", "check_steps"):
        monkeypatch.setattr(
            arrays.IMPLEMENTATIONS[cohort.family],
            name,
            lambda *a, **k: pytest.fail("A numeric stage invoked a host validator"),
        )
    monkeypatch.setattr(
        host, "_runtime", lambda *a, **k: pytest.fail("A numeric stage invoked host projection")
    )
    visits = []

    def inputs(p, c, v):
        visits.append("inputs")
        return arrays.prepare_numeric_world(p, c, v, family=cohort.family, xp=np)

    def physics(s, p, u):
        visits.append("physics")
        return arrays.compact_physics_world(s, p, u, family=cohort.family, xp=np)

    def checks(s, p, u, h, v):
        visits.append("checks")
        return arrays.check_physics_world(s, p, u, h, v, family=cohort.family, xp=np)

    stages = arrays.WorldStages(cohort.family, inputs, physics, checks)
    actual = arrays.evaluate_batch_staged(
        cohort.numeric, proposal, family=cohort.family, xp=np, stages=stages
    )
    assert visits == ["inputs", "physics", "checks"] * 3
    with pytest.raises(ValueError, match="family-bound"):
        arrays.evaluate_batch_staged(
            cohort.numeric,
            proposal,
            family=cohort.family,
            xp=np,
            stages=stages._replace(family="unreviewed-family"),
        )
    assert visits == ["inputs", "physics", "checks"] * 3
    exact_staged_shared_outputs(actual, original)
    assert len(jax.tree.leaves(actual)) < len(jax.tree.leaves(original))
    for i, case in enumerate(cases):
        check_world(
            case,
            cohort.worlds[i],
            jax.tree.map(lambda value, i=i: value[i], proposal),
            jax.tree.map(lambda value, i=i: value[i], actual),
            f"staged-numpy-{kind}-{i}",
        )
    reversed_values = arrays.evaluate_batch_staged(
        jax.tree.map(lambda value: value[::-1], cohort.numeric),
        jax.tree.map(lambda value: value[::-1], proposal),
        family=cohort.family,
        xp=np,
    )
    exact_tree(actual, jax.tree.map(lambda value: value[::-1], reversed_values))
    parts = []
    for indices in ((0,), (1, 2)):
        parts.append(
            arrays.evaluate_batch_staged(
                jax.tree.map(lambda value, indices=indices: value[list(indices)], cohort.numeric),
                jax.tree.map(lambda value, indices=indices: value[list(indices)], proposal),
                family=cohort.family,
                xp=np,
            )
        )
    exact_tree(actual, jax.tree.map(lambda *values: np.concatenate(values), *parts))
    evidence(
        "staged-cohort-invariance-" + kind,
        dict(
            kind="staged_complete_outputs",
            family=cohort.family,
            world_count=3,
            complete_derivative_and_field_equal=True,
            all_thirteen_reason_predicates_equal=True,
            original_and_raw_arrays_equal=True,
            actual_gross_fuel_flows_equal=True,
            separate_world_stage_calls=visits,
            reorder_partition_exact=True,
            monolithic_output_leaves=len(jax.tree.leaves(original)),
            staged_output_leaves=len(jax.tree.leaves(actual)),
            compiled_memory_measured=False,
        ),
    )


@pytest.mark.parametrize("kind", KINDS)
def test_separate_physical_checks_retain_all_seven_physical_refusal_predicates(kind):
    _, cohort, proposal = fixtures(kind, count=1)
    numeric = jax.tree.map(lambda value: value[0], cohort.numeric)
    raw = jax.tree.map(lambda value: value[0], proposal)
    inputs = arrays.prepare_numeric_world(
        numeric.layout, numeric.certificate, raw, family=cohort.family, xp=np
    )
    p, u, h = (
        inputs.arithmetic_runtime_layout,
        inputs.arithmetic_control,
        inputs.arithmetic_step_s,
    )
    physics = arrays.compact_physics_world(numeric.state, p, u, family=cohort.family, xp=np)

    def checked(v, step=h):
        checks = arrays.check_physics_world(
            numeric.state, p, u, step, v, family=cohort.family, xp=np
        )
        return arrays.assemble_staged_values(raw, inputs, v, checks, xp=np)

    baseline = checked(physics)
    assert baseline.valid
    malformed = (
        physics._replace(gross_hydrolysis_fmol_s=np.asarray(0.0)),
        physics._replace(valid=np.ones((1,), dtype=np.bool_)),
        physics._replace(
            derivative=physics.derivative._replace(
                amount_increment=physics.derivative.amount_increment[..., :-1]
            )
        ),
    )
    for changed in malformed:
        with pytest.raises(ValueError, match="axes and dtypes"):
            checked(changed)
    with pytest.raises(ValueError, match="complete typed"):
        arrays.assemble_staged_values(
            raw,
            inputs._replace(reason_validity=inputs.reason_validity.astype(np.float64)),
            physics,
            arrays.PhysicalChecks(
                baseline.passive_fraction, baseline.fuel_fraction, baseline.reason_validity[6:]
            ),
            xp=np,
        )
    nonfinite = physics.derivative.amount_increment.copy()
    nonfinite.flat[0] = np.nan
    dissipated_name = next(
        name for name, value in physics.derivative._asdict().items()
        if name.endswith("_dissipated_energy_pJ") and value.size
    )
    bad_dissipation = physics.derivative._replace(
        **{dissipated_name: np.full_like(getattr(physics.derivative, dissipated_name), -2e-12)}
    )
    faults = [
        (6, physics._replace(valid=np.asarray(False))),
        (7, physics._replace(field=physics.field._replace(converged=np.asarray(False)))),
        (8, physics._replace(derivative=physics.derivative._replace(amount_increment=nonfinite))),
        (9, physics._replace(field=physics.field._replace(energy_balance_pJ_s=np.asarray(2e-10)))),
        (10, physics._replace(derivative=bad_dissipation)),
    ]
    rows = []
    for bit, changed in faults:
        actual = checked(changed)
        assert not actual.valid and int(actual.reason_mask) & (1 << bit)
        rows.append(dict(expected_refusal_bit=bit, actual_reason_mask=int(actual.reason_mask)))
    assert baseline.passive_fraction > 0
    passive = checked(physics, h * (0.06 / baseline.passive_fraction))
    assert not passive.valid and int(passive.reason_mask) & (1 << 11)
    rows.append(dict(expected_refusal_bit=11, actual_reason_mask=int(passive.reason_mask)))
    if hasattr(p, "energy_initial_amount_fmol"):
        amount = arrays.fuel.energy_amounts(numeric.state, p)
        gross = np.where(p.active, 0.06 * np.min(amount, axis=0) / h, 0.0)
        changed = physics._replace(
            gross_hydrolysis_fmol_s=gross,
            gross_synthesis_fmol_s=np.zeros_like(gross),
        )
        fuel_limit = checked(changed)
        assert not fuel_limit.valid and int(fuel_limit.reason_mask) & (1 << 12)
        rows.append(dict(expected_refusal_bit=12, actual_reason_mask=int(fuel_limit.reason_mask)))
    else:
        assert baseline.fuel_fraction == 0 and baseline.reason_validity[12]
    evidence(
        "staged-physical-predicates-" + kind,
        dict(
            kind="separate_physical_refusal_predicates",
            family=cohort.family,
            synthetic_output_faults=True,
            malformed_stage_frames_refused=4,
            faults=rows,
            passive_turnover_ceiling=0.05,
            finite_fuel_turnover_ceiling=0.05,
            finite_fuel_owner=hasattr(p, "energy_initial_amount_fmol"),
            nonfuel_pool_predicate_true_without_fabricated_owner=True,
        ),
    )


@pytest.mark.parametrize("kind", KINDS)
def test_numpy_separate_stages_preserve_invalid_raw_buffers_and_all_reason_bits(kind):
    _, cohort, proposal = fixtures(kind, count=1)
    numeric = jax.tree.map(lambda value: value[0], cohort.numeric)
    raw = jax.tree.map(lambda value: value[0], proposal)
    damaged = [
        raw._replace(temperature_K=np.asarray(value))
        for value in (0.0, -1.0, float("nan"), float("inf"), 273.16)
    ]
    damaged.append(
        raw._replace(
            control=raw.control._replace(membrane=np.full_like(raw.control.membrane, 2.0)),
            step_s=numeric.certificate.maximum_step_s * 2,
        )
    )
    for i, changed in enumerate(damaged):
        with np.errstate(all="ignore"):
            original = arrays.evaluate_world(
                numeric.state, numeric.layout, numeric.certificate, changed,
                family=cohort.family, xp=np,
            )
            actual = arrays.evaluate_world_staged(
                numeric.state, numeric.layout, numeric.certificate, changed,
                family=cohort.family, xp=np,
            )
        exact_staged_shared_outputs(actual, original)
        assert not actual.valid and actual.arithmetic_substitution
        expected_inputs = reference.proposal_input_validity(
            float(changed.temperature_K),
            float(changed.step_s),
            changed.control._asdict(),
            float(numeric.certificate.temperature_K),
            float(numeric.certificate.maximum_step_s),
        )
        np.testing.assert_array_equal(actual.reason_validity[:6], expected_inputs)
        evidence(
            f"staged-raw-invalid-{kind}-{i}",
            dict(
                kind="staged_raw_invalid_proposal",
                family=cohort.family,
                certified_temperature_K=float(numeric.certificate.temperature_K),
                maximum_step_s=float(numeric.certificate.maximum_step_s),
                reason_mask=int(actual.reason_mask),
                reason_validity=actual.reason_validity.tolist(),
                monolithic_and_staged_equal=True,
                raw_proposal_retained=True,
                safe_arithmetic_does_not_admit_raw=True,
            ),
            dict(
                raw_temperature_K=actual.raw_proposal.temperature_K,
                raw_step_s=actual.raw_proposal.step_s,
                **{
                    "raw_control__" + key: value
                    for key, value in actual.raw_proposal.control._asdict().items()
                },
                **{
                    "raw_runtime__" + key: value
                    for key, value in actual.raw_runtime_layout._asdict().items()
                },
            ),
        )


@pytest.mark.parametrize("kind", KINDS)
def test_separate_world_stages_trace_full_outputs_without_host_callbacks(kind, monkeypatch):
    _, cohort, proposal = fixtures(kind, count=1)
    numeric = jax.tree.map(lambda value: value[0], cohort.numeric)
    raw = jax.tree.map(lambda value: value[0], proposal)
    for name in ("initial_values", "check_values", "check_steps"):
        monkeypatch.setattr(
            arrays.IMPLEMENTATIONS[cohort.family],
            name,
            lambda *a, **k: pytest.fail("Shape tracing invoked a host validator"),
        )
    monkeypatch.setattr(
        host, "_runtime", lambda *a, **k: pytest.fail("Shape tracing invoked host projection")
    )
    inputs = jax.eval_shape(
        lambda p, c, v: arrays.prepare_numeric_world(p, c, v, family=cohort.family, xp=jnp),
        numeric.layout, numeric.certificate, raw,
    )
    physics = jax.eval_shape(
        lambda s, p, u: arrays.compact_physics_world(s, p, u, family=cohort.family, xp=jnp),
        numeric.state, inputs.arithmetic_runtime_layout, inputs.arithmetic_control,
    )
    checks = jax.eval_shape(
        lambda s, p, u, h, v: arrays.check_physics_world(
            s, p, u, h, v, family=cohort.family, xp=jnp
        ),
        numeric.state, inputs.arithmetic_runtime_layout, inputs.arithmetic_control,
        inputs.arithmetic_step_s, physics,
    )
    result = jax.eval_shape(
        lambda proposal, inputs, physics, checks: arrays.assemble_staged_values(
            proposal, inputs, physics, checks, xp=jnp
        ),
        raw, inputs, physics, checks,
    )
    assert inputs.reason_validity.shape == (6,) and checks.reason_validity.shape == (7,)
    assert result.reason_validity.shape == (len(arrays.REASONS),)
    assert result.reason_mask.shape == result.valid.shape == ()
    assert result.reason_mask.dtype == np.uint32 and result.valid.dtype == np.bool_
    assert type(result.derivative) is type(numeric.state)
    assert result.readouts.gross_hydrolysis_fmol_s.shape == numeric.layout.active.shape
    assert result.readouts.gross_synthesis_fmol_s.shape == numeric.layout.active.shape
    evidence(
        "staged-shape-" + kind,
        dict(
            kind="separate_world_stage_shapes",
            family=cohort.family,
            input_predicates=6,
            physical_predicates=7,
            derivative_fields=list(result.derivative._fields),
            physical_field_tree_preserved=True,
            no_host_callbacks=True,
            compiled=False,
            numerics_executed=False,
        ),
    )


@pytest.mark.parametrize("kind", KINDS)
def test_cpu_jax_staged_complete_rates_and_projection_without_host_callbacks(kind, monkeypatch):
    cases, cohort, proposals = fixtures(kind, count=2)
    evidence(
        "jax-prepared-" + kind,
        dict(
            kind="cpu_jax_stage",
            stage="host_prepared",
            cohort=prepared.record(cohort),
            affinity=sorted(os.sched_getaffinity(0)),
            x64=bool(jax.config.x64_enabled),
            backend=jax.default_backend(),
        ),
    )
    numeric, raw = jax.tree.map(jnp.asarray, cohort.numeric), jax.tree.map(jnp.asarray, proposals)

    def function(values, proposal):
        return arrays.evaluate_batch(values, proposal, family=cohort.family, xp=jnp)

    shaped = jax.eval_shape(function, numeric, raw)
    assert shaped.valid.shape == (2,)
    evidence(
        "jax-shaped-" + kind,
        dict(kind="cpu_jax_stage", stage="complete_shape_traced", world_count=2),
    )
    for name in ("initial_values", "check_values", "check_steps"):
        monkeypatch.setattr(
            arrays.IMPLEMENTATIONS[cohort.family],
            name,
            lambda *a, **k: pytest.fail("Numeric kernel invoked a host validator"),
        )
    monkeypatch.setattr(
        host, "_runtime", lambda *a, **k: pytest.fail("Numeric kernel invoked host projection")
    )
    project = jax.jit(jax.vmap(lambda p, t: arrays.project(p, t, xp=jnp)))
    evidence(
        "jax-projection-start-" + kind,
        dict(kind="cpu_jax_stage", stage="projection_compilation_started"),
    )
    projected = project(numeric.layout, raw.temperature_K)
    jax.block_until_ready(projected)
    evidence(
        "jax-projection-complete-" + kind,
        dict(kind="cpu_jax_stage", stage="projection_compiled_executed"),
        {key: np.asarray(value) for key, value in projected._asdict().items()},
    )
    compiled = jax.jit(function)
    lowered = compiled.lower(numeric, raw)
    evidence(
        "jax-lowered-" + kind,
        dict(kind="cpu_jax_stage", stage="complete_RHS_lowered_compilation_started"),
    )
    executable = lowered.compile()
    evidence("jax-compiled-" + kind, dict(kind="cpu_jax_stage", stage="complete_RHS_compiled"))
    actual = executable(numeric, raw)
    jax.block_until_ready(actual)
    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    for i, case in enumerate(cases):
        check_world(
            case,
            cohort.worlds[i],
            jax.tree.map(lambda value, i=i: np.asarray(value[i]), proposals),
            jax.tree.map(lambda value, i=i: np.asarray(value[i]), actual),
            f"cpu-jax-{kind}-{i}",
        )
    reversed_values = executable(
        jax.tree.map(lambda value: value[::-1], numeric),
        jax.tree.map(lambda value: value[::-1], raw),
    )
    jax.block_until_ready(reversed_values)
    for forward, reverse in zip(
        jax.tree.leaves(actual), jax.tree.leaves(reversed_values), strict=True
    ):
        np.testing.assert_array_equal(np.asarray(forward), np.asarray(reverse)[::-1])
    invalid = raw._replace(temperature_K=raw.temperature_K.at[0].set(0.0))
    rejected = executable(numeric, invalid)
    jax.block_until_ready(rejected)
    assert not bool(rejected.valid[0]) and bool(rejected.valid[1])
    assert int(rejected.reason_mask[0]) & 4 and float(rejected.raw_proposal.temperature_K[0]) == 0.0
    evidence(
        "jax-raw-invalid-" + kind,
        dict(
            kind="cpu_jax_stage",
            stage="invalid_raw_retained_with_reason",
            reason_mask=np.asarray(rejected.reason_mask).tolist(),
            valid=np.asarray(rejected.valid).tolist(),
        ),
        dict(
            raw_temperature_K=np.asarray(rejected.raw_proposal.temperature_K),
            raw_runtime_temperature=np.asarray(rejected.raw_runtime_layout.temperature),
        ),
    )
    evidence(
        "compiled-" + kind,
        dict(
            kind="cpu_staged_jax",
            family=cohort.family,
            shape_staged=True,
            projection_compiled=True,
            complete_RHS_compiled=True,
            world_count=2,
            no_host_callbacks=True,
            affinity=sorted(os.sched_getaffinity(0)),
        ),
    )
