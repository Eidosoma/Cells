"""Complete common-stage pump regulation, owner views and physical accounting."""

import ast
import hashlib
import json
import os
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from cells.core import surface_calcium_energy_regulated_spec as schema
from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.models import surface_calcium_energy as base
from cells.models import surface_calcium_energy_regulated as model
from cells.numerics.fixed_step import rk4_step
from validation.regulation import integrated_network_regulation_fixtures as fixtures
from validation.regulation import integrated_network_regulation_reference as reference

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads(
    (ROOT / "validation/regulation/integrated_network_regulation_protocol.json").read_text()
)


def evidence(name, data, arrays=None):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        path = Path(folder)
        path.mkdir(parents=True, exist_ok=True)
        (path / ("integrated-network-regulation-" + name + ".json")).write_text(
            json.dumps(
                {**data, "status": "passed"},
                indent=2,
                allow_nan=False,
                default=lambda v: v.tolist(),
            )
            + "\n"
        )
        if arrays is not None:
            np.savez_compressed(path / (name + ".npz"), **arrays)


@lru_cache
def cached(arm="active", padded=False, compact=False):
    raw = fixtures.definition(arm, padded=padded, compact=compact)
    spec = schema.parse(raw)
    state, p = model.initial_values(spec)
    return spec, state, p


def initial(arm="active", padded=False, compact=False, time=0.0):
    spec, state, p = deepcopy(cached(arm, padded, compact))
    table = schema.control_values(spec, [time])
    return spec, state, p, type(table)(*(v[0] for v in table))


def compare(c, actual, expected, *, atol=3e-12, rtol=3e-10, charge_atol=3e-23):
    a = reference.flatten(c, actual._asdict()) if hasattr(actual, "_asdict") else np.asarray(actual)
    b = np.asarray(expected)
    budget = reference.flatten(
        c,
        {k: np.full(s, charge_atol if k.endswith("_C") else atol) for k, s in c["shapes"].items()},
    ) + rtol * np.abs(b)
    ratio = float(np.max(np.abs(a - b) / budget, initial=0))
    assert ratio <= 1, ratio
    return ratio


@pytest.mark.parametrize("padded", [False, True])
def test_roundtrip_38_fields_and_source_contract(padded):
    spec, state, p, u = initial(padded=padded)
    raw = schema.to_dict(spec)
    assert schema.parse(raw) == spec and len(state) == 38
    assert state._fields == base.STATE_TYPE._fields and model.STATE_AXES == base.STATE_AXES
    assert model.base_layout(p).__class__ is base.HCN_EXTRA_LAYOUT_TYPE
    assert model.working_size(spec) > base.working_size(schema.base_spec(spec))
    assert model.domain_valid.with_control is model.control_domain_valid
    assert model.control_domain_valid(state, u, p, p.active, xp=np)
    assert raw["model"]["network_regulation"]["control_composition"] == schema.COMPOSITION
    evidence(
        "contract-" + str(padded),
        dict(
            model=raw["model"]["id"],
            state_fields=list(state._fields),
            rule_capacity=spec.execution.regulation_capacity,
            source_law=PROTOCOL["law"],
            timing=schema.TIMING,
        ),
    )


def test_frozen_source_identity_and_independent_reference_imports():
    for relative, expected in PROTOCOL["readonly_source_sha256"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
    native = PROTOCOL["frozen_native_handoff"]
    path = Path(native["path"])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == native["sha256"]
    report = json.loads(path.read_text())
    assert report["status"] == "passed"
    for module in (fixtures, reference):
        for node in ast.walk(ast.parse(Path(module.__file__).read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("cells", "jax"))
    evidence(
        "source-provenance",
        dict(
            native_handoff=native,
            readonly_source_sha256=PROTOCOL["readonly_source_sha256"],
            new_native_timing_claim=False,
        ),
    )


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_independent_complete_stages(arm, padded):
    spec, state, p, u = initial(arm, padded)
    c = reference.bind(schema.to_dict(spec))
    flat = reference.flatten(c, state._asdict())
    expected, phi, proof = reference.evaluate(c, flat, 0.0)
    value = model.readouts(state, u, p, xp=np)
    ratio = compare(c, value.derivative, expected)
    assert value.valid and abs(value.field.energy_balance_pJ_s) < 3e-10
    np.testing.assert_allclose(
        value.regulation.rule_factors[: len(c["rules"])],
        proof["network_regulation"]["rule_factors"],
        rtol=8e-12,
        atol=3e-15,
    )
    np.testing.assert_allclose(
        value.regulation.samples_mM[: len(c["rules"])],
        np.asarray(proof["network_regulation"]["samples_mM"]).reshape(
            len(c["rules"]), len(spec.model.species_ids) + 3, 2
        ),
        rtol=8e-12,
        atol=3e-15,
    )
    assert abs(proof["physical_energy_balance_pJ_s"]) < 3e-10
    assert np.max(np.abs(proof["adenylate_rate_fmol_s"]), initial=0) < 3e-13
    assert np.max(np.abs(proof["phosphorus_rate_fmol_s"]), initial=0) < 3e-13
    if padded:
        assert not np.any(value.derivative.energy_amount_increment_fmol[:, -1])
        assert value.regulation.rule_factors[-1] == 0 and not np.any(
            value.regulation.samples_mM[-1]
        )
    evidence(
        "stage-" + arm + "-" + str(padded),
        dict(
            max_error_over_budget=ratio,
            independent_proof=proof,
            cell_voltages_V=phi,
            rule_factors=value.regulation.rule_factors,
        ),
        dict(slope=expected),
    )


@pytest.mark.parametrize("arm", ["empty", "identity"])
def test_exact_parent_reduction(arm):
    _, state, p, u = initial(arm)
    actual = model.readouts(state, u, p, xp=np)
    expected = base.readouts(state, u, model.base_layout(p), xp=np)
    for a, b in zip(actual.derivative, expected.derivative, strict=True):
        np.testing.assert_array_equal(a, b)
    np.testing.assert_array_equal(
        actual.field.rates.membrane_flux_fmol_s, expected.field.rates.membrane_flux_fmol_s
    )


def test_ordered_last_writer_and_schedule_multiply_exactly_once():
    _, state, p, u = initial("ordered")
    original = u.pump.copy()
    u = u._replace(pump=np.where(p.pump_present, 0.5, 0.0))
    value = model.readouts(state, u, p, xp=np)
    assert value.regulation.pump_factor[0] == 0.23
    assert value.effective_control.pump[0] == 0.115
    assert value.effective_control.pump[0] != 0.5 * np.prod(value.regulation.rule_factors[[0, 4]])
    after = model.readouts(state, u, p, xp=np)
    for a, b in zip(value.derivative, after.derivative, strict=True):
        np.testing.assert_array_equal(a, b)
    assert np.any(original != u.pump)
    evidence(
        "ordered-scheduled",
        dict(
            factors=value.regulation.rule_factors,
            final_factor=value.regulation.pump_factor,
            scheduled=u.pump,
            effective=value.effective_control.pump,
            native_sim_lag_equivalence=False,
        ),
    )


def test_free_calcium_view_tracks_binding_and_not_total_ionic_ledger():
    _, state, p, _ = initial()
    before = model.regulation_values(state, p, xp=np)
    changed = model.STATE_TYPE(*(v.copy() for v in state))
    names = ("Ca", "B", "CaB")
    # Explicit known store species IDs are resolved from the model declaration.
    spec = cached()[0]
    store = spec.model.stores[0]
    indices = [next(i for i, s in enumerate(store.species) if s.id == name) for name in names]
    cy = p.er_cytosol[0]
    available = p.er_initial_amount[0, indices[0], cy]
    extent = 0.1 * available
    changed.chemical_amount_increment[0, indices, cy] += extent * np.array([-1, -1, 1])
    after = model.regulation_values(changed, p, xp=np)
    np.testing.assert_array_equal(state.amount_increment, changed.amount_increment)
    assert after.rule_factors[0] != before.rule_factors[0]
    np.testing.assert_array_equal(after.rule_factors[1:], before.rule_factors[1:])
    ca = spec.model.species_ids.index("Ca")
    assert after.samples_mM[0, ca, 0] < before.samples_mM[0, ca, 0]
    evidence(
        "free-calcium-view",
        dict(
            binding_extent_fmol=extent,
            initial_factor=before.rule_factors,
            changed_factor=after.rule_factors,
            total_ionic_ledger_unchanged=True,
        ),
    )


def test_named_owner_fuel_and_external_views_are_live():
    spec, state, p, _ = initial()
    before = model.regulation_values(state, p, xp=np)
    changed = model.STATE_TYPE(*(v.copy() for v in state))
    changed.energy_amount_increment_fmol[:, 0] += np.array([-0.02, 0.02, 0.02])
    after = model.regulation_values(changed, p, xp=np)
    assert after.rule_factors[0] < before.rule_factors[0]
    np.testing.assert_array_equal(after.rule_factors[1:], before.rule_factors[1:])
    sodium = spec.model.species_ids.index("Na")
    exterior = int(p.regulation_outside[1])
    changed.extracellular_amount_increment[sodium, exterior] += (
        0.01 * p.extracellular_volume[exterior]
    )
    third = model.regulation_values(changed, p, xp=np)
    assert third.rule_factors[1] > after.rule_factors[1]
    assert not np.any(third.samples_mM[:, -3:, 1])
    evidence(
        "fuel-and-exterior-views",
        dict(
            before=before.rule_factors,
            fuel_changed=after.rule_factors,
            exterior_changed=third.rule_factors,
            fuel_external_view_zero=True,
        ),
    )


def test_bounded_regulation_keeps_signed_pump_fuel_transfer_once():
    _, state, p, u = initial()
    value = model.readouts(state, u, p, xp=np)
    cycles = model.pump_cycles(value.derivative)
    routes = model.pump_routes(p)
    demand = np.bincount(routes.owner, weights=cycles, minlength=p.active.size)
    regen = np.bincount(
        p.regeneration_owner,
        weights=value.derivative.regeneration_cycles_fmol,
        minlength=p.active.size,
    )
    np.testing.assert_allclose(
        value.derivative.energy_amount_increment_fmol,
        np.array([-1, 1, 1])[:, None] * (demand - regen),
        rtol=3e-13,
        atol=3e-13,
    )
    assert not any("regulat" in key for key in model.STATE_TYPE._fields)


@pytest.mark.parametrize(
    "fault",
    [
        "cross-owner",
        "missing-pool",
        "unknown-pump",
        "wrong-target",
        "negative-max",
        "large-max",
        "external-fuel",
        "unknown-species",
        "duplicate-id",
        "wrong-timing",
        "wrong-composition",
        "capacity",
        "only-direct-groups",
        "signed-direct-inhibitor",
        "unbounded-independent",
    ],
)
def test_unsupported_schema_or_initial_native_factor_is_rejected(fault):
    raw = fixtures.definition(compact=True)
    block = raw["model"]["network_regulation"]
    rule = block["rules"][0]
    conf = rule["configuration"]
    if fault == "cross-owner":
        rule["fuel_pool_id"] = "fuel_cell_1"
    if fault == "missing-pool":
        rule["fuel_pool_id"] = "missing"
    if fault == "unknown-pump":
        rule["pump_id"] = "missing"
    if fault == "wrong-target":
        conf["target"] = "GJ"
    if fault == "negative-max":
        conf["max effect"] = -0.1
    if fault == "large-max":
        conf["max effect"] = 1.1
    if fault == "external-fuel":
        conf["activator zone"] = ["env"]
    if fault == "unknown-species":
        conf["activators"] = ["absent"]
    if fault == "duplicate-id":
        block["rules"].append(deepcopy(rule))
    if fault == "wrong-timing":
        block["timing"] = "native_SIM"
    if fault == "wrong-composition":
        block["control_composition"] = "overwrite_schedule"
    if fault == "capacity":
        raw["execution"]["regulation_capacity"] = 1
    if fault in ("only-direct-groups", "signed-direct-inhibitor", "unbounded-independent"):
        conf.clear()
        conf.update(name=rule["id"], target="Na/K-ATPase", **{"max effect": 1.0})
        if fault == "only-direct-groups":
            conf.update(
                activators=["ATP&"],
                **{
                    "activator Km": [1.0],
                    "activator n": [1.0],
                    "inhibitors": ["ADP&"],
                    "inhibitor Km": [1.0],
                    "inhibitor n": [1.0],
                },
            )
        if fault == "signed-direct-inhibitor":
            conf.update(inhibitors=["ATP&"], **{"inhibitor Km": [1.0], "inhibitor n": [1.0]})
        if fault == "unbounded-independent":
            conf.update(activators=["ATP!"], **{"activator Km": [1.0], "activator n": [1.0]})
    with pytest.raises(ConfigError):
        schema.parse(raw)
    evidence("rejected-" + fault, dict(fault=fault, rejected=True, input=raw))


def test_state_dependent_factor_escape_is_refused_even_when_blocked_or_shadowed():
    raw = fixtures.definition("direct", compact=True)
    pool = raw["model"]["energy_pools"][0]
    volume = raw["model"]["ionic"]["cells"][0]["volume_pL"]
    pool["initial_amount_fmol"].update(ADP=10 * volume, Pi=10 * volume)
    raw["model"]["network_regulation"]["rules"][0]["configuration"]["max effect"] = 0.6
    spec = schema.parse(raw)
    state, p = model.initial_values(spec)
    changed = model.STATE_TYPE(*(v.copy() for v in state))
    changed.energy_amount_increment_fmol[:, 0] += volume * np.array([0.5, -0.5, -0.5])
    assert base.domain_valid(changed, model.base_layout(p), p.active, xp=np)
    value = model.regulation_values(changed, p, xp=np)
    assert value.rule_factors[0] > 1 and not value.valid
    table = schema.control_values(spec, [0.0])
    u = type(table)(*(v[0] for v in table))._replace(pump=np.zeros_like(p.pump_capacity))
    before = [v.copy() for v in changed]
    assert not model.control_domain_valid(changed, u, p, p.active, xp=np)
    assert not model.readouts(changed, u, p, xp=np).valid
    assert all(np.all(np.isnan(v)) for v in model.rhs(changed, u, p, p.active, xp=np))
    for a, b in zip(changed, before, strict=True):
        np.testing.assert_array_equal(a, b)
    with pytest.raises(NumericalError):
        model.check_values(changed, spec)
    c = reference.bind(schema.to_dict(spec))
    with pytest.raises(ValueError):
        reference.evaluate(c, reference.flatten(c, changed._asdict()), 0)
    evidence(
        "factor-escape",
        dict(
            initial_ATP_mM=float(p.energy_initial_amount_fmol[0, 0] / volume),
            changed_factor=value.rule_factors,
            blocked_schedule=True,
            refused_without_state_mutation=True,
        ),
    )


def test_observer_uses_effective_controls_and_complete_physical_readouts():
    spec, state, p, u = initial()
    time = np.asarray([0.0])
    history = model.STATE_TYPE(*(v[None, ...] for v in state))
    observed = model.observe_history(time, history, p, time, spec)
    value = model.readouts(state, u, p, xp=np)
    effective_spec = replace(
        schema.base_spec(spec),
        experiment=replace(
            spec.experiment,
            pumps=tuple(
                (schema.prior.ChannelChange(0.0, float(a)),)
                for a in value.effective_control.pump[: len(spec.model.membranes)]
            ),
        ),
    )
    parent = base.observe_history(time, history, model.base_layout(p), time, effective_spec)
    for key in base.OBSERVATION_FIELDS:
        np.testing.assert_array_equal(getattr(observed, key), getattr(parent, key))
    np.testing.assert_array_equal(
        observed.nak_effective_availability[0], value.effective_control.pump
    )
    np.testing.assert_array_equal(observed.nak_scheduled_availability[0], u.pump)
    assert len(history) == 38
    model.check_values(history, spec)
    summary = model.summarize(history, {}, spec)
    assert (
        summary["model"] == schema.MODEL_ID
        and summary["network_regulation_timing"] == schema.TIMING
    )
    empty = model.observe_history(time, history, p, np.asarray([]), spec)
    assert all(len(v) == 0 for v in vars(empty).values())


def grid(raw, refinement=1):
    knots = reference.event_times(raw)
    h = raw["execution"]["dt"] / refinement
    result = [knots[0]]
    for a, b in zip(knots[:-1], knots[1:], strict=True):
        count = max(1, int(np.ceil((b - a) / h - 2e-13)))
        result.extend(np.linspace(a, b, count + 1)[1:])
    return np.asarray(result)


def integrate_cpu(raw, refinement=1, compiled=False):
    spec = schema.parse(raw)
    state, p = model.initial_values(spec)
    times = grid(raw, refinement)
    table = schema.control_values(spec, times[:-1])
    model.check_steps(spec, np.diff(times), table)
    rhs = model.rhs
    if compiled:
        import jax

        rhs = jax.jit(model.rhs)
    else:

        def rhs(y, u, p, a):
            return model.rhs(y, u, p, a, xp=np)

    history = [state]
    factor_rows = []
    for i, step in enumerate(np.diff(times)):
        u = type(table)(*(v[i] for v in table))
        state = rk4_step(rhs, state, float(step), u, p, p.active)
        state = model.STATE_TYPE(*(np.asarray(v) for v in state))
        if not model.control_domain_valid(state, u, p, p.active, xp=np):
            raise NumericalError("Unaccepted regulated RK4 trial/end state")
        history.append(state)
        factor_rows.append(model.regulation_values(state, p, xp=np).pump_factor)
    stacked = model.STATE_TYPE(*(np.stack(v) for v in zip(*history, strict=True)))
    diagnostics = model.check_values(stacked, spec)
    return spec, p, times, stacked, diagnostics, np.asarray(factor_rows)


def test_coupled_cpu_trajectory_refinement_and_independent_adaptive_solution():
    raw = fixtures.probe(compact=False)
    # Shorten the independent manufactured window while retaining two off-grid
    # pump events and the finite supply event in the merged common-stage clock.
    e = raw["experiment"]
    e.update(end_time=10e-6, observation_times=[0.0, 3.3e-6, 6.25e-6, 7.1e-6, 10e-6])
    for name, groups in e.items():
        if name.endswith("_controls"):
            for group in groups:
                key = "controls" if "controls" in group else "schedule"
                group[key] = [r for r in group[key] if r["time"] == 0]
    e["pump_controls"][0]["schedule"].extend(
        [dict(time=3.3e-6, availability=0.0), dict(time=7.1e-6, availability=0.6)]
    )
    e["regeneration_controls"][0]["schedule"].append(dict(time=6.25e-6, availability=0.0))
    c, knots, expected, proof = reference.integrate(raw)
    records = []
    for refinement in (1, 2, 4):
        spec, p, times, history, diagnostics, factors = integrate_cpu(raw, refinement)
        observed = reference.flatten(c, history._asdict())[
            [int(np.flatnonzero(times == t)[0]) for t in knots]
        ]
        ratio = compare(c, observed, expected, atol=2e-11, rtol=3e-8, charge_atol=3e-23)
        error = float(np.max(np.abs(observed[-1] - expected[-1])))
        records.append(
            dict(
                refinement=refinement,
                max_error_over_budget=ratio,
                max_state_error=error,
                physical_diagnostics=diagnostics,
            )
        )
        assert not np.array_equal(factors[0], factors[-1])
        if refinement == 1:
            assert 3.3e-6 in times and 7.1e-6 in times and 6.25e-6 in times
            frozen = model.regulation_values(
                history._replace(**{k: v[0] for k, v in history._asdict().items()}), p, xp=np
            ).pump_factor
            assert np.max(np.abs(factors[-1] - frozen)) > 1e-10
    assert records[-1]["max_state_error"] <= records[0]["max_state_error"] + 3e-13
    evidence(
        "coupled-cpu-refinement",
        dict(inputs=raw, adaptive=proof, records=records, fields=38, native_SIM_parity=False),
        dict(times=knots, reference_state=expected),
    )


def test_jax_full_coupled_stage_matches_host_and_independent_reference():
    import jax

    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    spec, state, p, u = initial()
    host = model.readouts(state, u, p, xp=np)
    result = jax.jit(lambda y, u, p: model.readouts(y, u, p))(state, u, p)
    assert result.valid
    for actual, expected in zip(result.derivative, host.derivative, strict=True):
        np.testing.assert_allclose(actual, expected, rtol=3e-10, atol=3e-12)
    c = reference.bind(schema.to_dict(spec))
    expected, _, proof = reference.evaluate(c, reference.flatten(c, state._asdict()), 0.0)
    ratio = compare(c, result.derivative, expected)
    assert abs(result.field.energy_balance_pJ_s) < 3e-10
    evidence(
        "jax-full-stage",
        dict(
            backend=jax.default_backend(),
            state_fields=len(state),
            populations=len(spec.model.channels),
            max_error_over_budget=ratio,
            energy_balance_pJ_s=float(result.field.energy_balance_pJ_s),
            independent_proof=proof,
        ),
    )
    jax.clear_caches()


def test_jax_common_stage_rk4_matches_cpu_all_fields_and_restart():
    import jax

    raw = fixtures.probe(compact=True)
    raw["experiment"]["end_time"] = 5e-6
    raw["experiment"]["observation_times"] = [0.0, 2.5e-6, 5e-6]
    for name, groups in raw["experiment"].items():
        if name.endswith("_controls"):
            for group in groups:
                key = "controls" if "controls" in group else "schedule"
                group[key] = [r for r in group[key] if r["time"] <= 5e-6]
    spec, p, times, cpu, diagnostics, _ = integrate_cpu(raw)
    _, _, other, jit_history, jit_diagnostics, _ = integrate_cpu(raw, compiled=True)
    np.testing.assert_array_equal(times, other)
    c = reference.bind(raw)
    ratio = compare(
        c,
        reference.flatten(c, jit_history._asdict()),
        reference.flatten(c, cpu._asdict()),
        atol=2e-11,
        rtol=3e-8,
    )
    split = 2
    state = model.STATE_TYPE(*(v[split].copy() for v in jit_history))
    table = schema.control_values(spec, times[split:-1])
    kernel = jax.jit(model.rhs)
    for i, h in enumerate(np.diff(times[split:])):
        held = type(table)(*(v[i] for v in table))
        state = rk4_step(kernel, state, float(h), held, p, p.active)
    end = model.STATE_TYPE(*(v[-1] for v in jit_history))
    for a, b in zip(state, end, strict=True):
        np.testing.assert_array_equal(a, b)
    evidence(
        "jax-rk4-restart",
        dict(
            fields=38,
            times_s=times,
            split_index=split,
            exact_restart=True,
            max_cpu_error_over_budget=ratio,
            cpu_diagnostics=diagnostics,
            jax_diagnostics=jit_diagnostics,
        ),
    )
    jax.clear_caches()


def test_jax_regulator_owner_derivatives_and_invalid_worlds():
    import jax
    import jax.numpy as jnp

    _, state, p, u = initial(compact=True)
    fun = jax.jit(lambda y: model.regulation_values(y, p))
    original = fun(state)
    derivative = jax.jit(
        jax.jacfwd(
            lambda amount: fun(state._replace(energy_amount_increment_fmol=amount)).rule_factors
        )
    )(jnp.asarray(state.energy_amount_increment_fmol))
    assert np.all(np.isfinite(derivative)) and derivative[0, 0, 0] > 0
    assert derivative[0, 0, 1] == 0
    bad = p._replace(regulation_max_effect=p.regulation_max_effect.copy())
    bad.regulation_max_effect[0, 0] = -1.0
    assert not jax.jit(lambda y, p: model.regulation_values(y, p).valid)(state, bad)
    np.testing.assert_allclose(
        original.rule_factors,
        model.regulation_values(state, p, xp=np).rule_factors,
        rtol=8e-12,
        atol=3e-15,
    )
    evidence(
        "jax-owner-derivatives",
        dict(
            finite=True,
            own_ATP_response=float(derivative[0, 0, 0]),
            cross_owner_response=float(derivative[0, 0, 1]),
            negative_factor_rejected=True,
        ),
    )
