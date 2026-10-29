"""Owned channel/junction regulation, independent physical stages and guards."""

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

from cells.core import surface_calcium_energy_regulated_v2_spec as schema
from cells.core.errors import NumericalError
from cells.core.specs import ChannelChange, ConfigError
from cells.models import surface_calcium_energy as base
from cells.models import surface_calcium_energy_regulated_v2 as model
from cells.numerics.fixed_step import rk4_step
from validation.regulation import integrated_network_regulation_v2_fixtures as fixtures
from validation.regulation import integrated_network_regulation_v2_reference as reference

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads(
    (ROOT / "validation/regulation/integrated_network_regulation_v2_protocol.json").read_text()
)


def evidence(name, data, arrays=None):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        p = Path(folder)
        p.mkdir(parents=True, exist_ok=True)
        (p / ("regulation-v2-" + name + ".json")).write_text(
            json.dumps(
                dict(data, status="passed"), indent=2, allow_nan=False, default=lambda v: v.tolist()
            )
            + "\n"
        )
        if arrays is not None:
            np.savez_compressed(p / (name + ".npz"), **arrays)


@lru_cache
def cached(arm="active", padded=False):
    spec = schema.parse(fixtures.definition(arm, padded=padded))
    state, p = model.initial_values(spec)
    return spec, state, p


def initial(arm="active", padded=False):
    spec, state, p = deepcopy(cached(arm, padded))
    table = schema.control_values(spec, [0.0])
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
def test_strict_roundtrip_and_inherited_38_field_contract(padded):
    spec, state, p, u = initial(padded=padded)
    assert schema.parse(schema.to_dict(spec)) == spec
    assert len(state) == 38 and state._fields == base.STATE_TYPE._fields
    assert model.STATE_AXES == base.STATE_AXES
    assert type(model.base_layout(p)) is base.HCN_EXTRA_LAYOUT_TYPE
    assert model.domain_valid.with_control is model.control_domain_valid
    assert model.control_domain_valid(state, u, p, p.active, xp=np)
    assert model.working_size(spec) > base.working_size(schema.base_spec(spec))
    assert len(spec.model.channels) == 63
    if padded:
        value = model.regulation_values(state, p, xp=np)
        assert value.rule_factors[-1] == 0 and not np.any(value.samples_mM[-1])
        assert value.channel_factor[-1] == 0 and value.junction_factor[-1] == 0
    evidence(
        "contract-" + str(padded),
        dict(
            model=schema.MODEL_ID,
            state_fields=list(state._fields),
            capacity=spec.execution.regulation_capacity,
            shared_channel_populations=len(spec.model.channels),
        ),
    )


def test_frozen_equation_sources_and_independent_imports():
    for name, sha in PROTOCOL["readonly_source_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha
    native = PROTOCOL["frozen_native_handoff"]
    assert hashlib.sha256(Path(native["path"]).read_bytes()).hexdigest() == native["sha256"]
    for module in (fixtures, reference):
        for node in ast.walk(ast.parse(Path(module.__file__).read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("cells", "jax"))
    evidence(
        "provenance",
        dict(
            readonly_source_sha256=PROTOCOL["readonly_source_sha256"],
            native=native,
            native_full_solver_parity=False,
        ),
    )


@pytest.mark.parametrize("arm", fixtures.ARMS)
def test_independent_complete_physical_stages(arm):
    spec, state, p, u = initial(arm)
    c = reference.bind(schema.to_dict(spec))
    expected, phi, proof = reference.evaluate(c, reference.flatten(c, state._asdict()), 0.0)
    actual = model.readouts(state, u, p, xp=np)
    ratio = compare(c, actual.derivative, expected)
    assert actual.valid
    regulation = proof["network_regulation"]
    np.testing.assert_allclose(
        actual.regulation.rule_factors, regulation["rule_factors"], rtol=8e-12, atol=3e-15
    )
    np.testing.assert_allclose(
        actual.regulation.samples_mM,
        np.asarray(regulation["samples_mM"]).reshape(
            len(c["rules"]), len(spec.model.species_ids) + 3, 2
        ),
        rtol=8e-12,
        atol=3e-15,
    )
    for kind, key in (("nak", "pump"), ("channel", "channel"), ("junction", "junction")):
        np.testing.assert_allclose(
            getattr(actual.effective_control, key),
            regulation["controls"][kind]["effective"],
            rtol=8e-12,
            atol=3e-15,
        )
    assert abs(actual.field.energy_balance_pJ_s) < 3e-10
    assert abs(proof["physical_energy_balance_pJ_s"]) < 3e-10
    assert np.max(np.abs(proof["adenylate_rate_fmol_s"]), initial=0) < 3e-13
    assert np.max(np.abs(proof["phosphorus_rate_fmol_s"]), initial=0) < 3e-13
    evidence(
        "stage-" + arm,
        dict(max_error_over_budget=ratio, independent_proof=proof, cell_voltages_V=phi),
        dict(slope=expected),
    )


@pytest.mark.parametrize("arm", ["empty", "identity"])
def test_exact_parent_reduction(arm):
    _, state, p, u = initial(arm)
    actual = model.readouts(state, u, p, xp=np)
    expected = base.readouts(state, u, model.base_layout(p), xp=np)
    for a, b in zip(actual.derivative, expected.derivative, strict=True):
        np.testing.assert_array_equal(a, b)


def test_rule_order_and_held_schedule_are_applied_once_per_consumer():
    _, state, p, u = initial("ordered")
    u = u._replace(pump=0.5 * u.pump, channel=0.5 * u.channel, junction=0.5 * u.junction)
    value = model.readouts(state, u, p, xp=np)
    assert value.regulation.pump_factor[0] == 0.23
    assert value.regulation.junction_factor[0] == 0.23
    assert value.regulation.channel_factor[0] == p.energy_initial_amount_fmol[2, 0] / p.volume[0]
    for key in ("pump", "channel", "junction"):
        factor = getattr(value.regulation, key + "_factor")
        np.testing.assert_array_equal(
            getattr(value.effective_control, key), getattr(u, key) * factor
        )
    _, state2, p2, u2 = initial("reordered")
    v2 = model.readouts(state2, u2, p2, xp=np)
    _, state3, p3, u3 = initial()
    v3 = model.readouts(state3, u3, p3, xp=np)
    assert v2.regulation.junction_factor[0] != v3.regulation.junction_factor[0]
    evidence(
        "ordered",
        dict(
            factors=value.regulation.rule_factors,
            effective={
                k: getattr(value.effective_control, k) for k in ("pump", "channel", "junction")
            },
            reversing_endpoint_rule_order_changes_edge=True,
        ),
    )


def test_batch_signature_tracks_channel_influencer_shapes():
    spec, _, _ = cached()
    rules = list(spec.model.network_regulators)
    original = rules[4]
    conf = deepcopy(original.configuration)
    conf["channel activators"].append("ADP")
    conf["activator Km"].append(0.4)
    conf["activator n"].append(1.0)
    rules[4] = replace(original, configuration=conf)
    different = replace(spec.model, network_regulators=tuple(rules))
    assert model.batch_signature(spec.model) != model.batch_signature(different)
    _, p = model.initial_values(replace(spec, model=different))
    assert p.regulation_influencer_mode.shape[1] >= 3
    evidence("batch-shapes", dict(channel_term_count_change_detected=True))


def test_live_fuel_free_calcium_exterior_and_explicit_junction_endpoint():
    spec, state, p, _ = initial()
    before = model.regulation_values(state, p, xp=np)
    changed = model.STATE_TYPE(*(v.copy() for v in state))
    changed.energy_amount_increment_fmol[:, 0] += [-0.02, 0.02, 0.02]
    fuel = model.regulation_values(changed, p, xp=np)
    assert fuel.rule_factors[4] != before.rule_factors[4]
    assert fuel.rule_factors[6] != before.rule_factors[6]
    assert fuel.rule_factors[7] == before.rule_factors[7]
    assert fuel.junction_factor[0] == before.junction_factor[0]
    changed.energy_amount_increment_fmol[:, 1] += [0.01, -0.01, -0.01]
    other = model.regulation_values(changed, p, xp=np)
    assert other.junction_factor[0] != fuel.junction_factor[0]
    store = spec.model.stores[0]
    indices = [
        next(i for i, s in enumerate(store.species) if s.id == k) for k in ("Ca", "B", "CaB")
    ]
    cy = p.er_cytosol[0]
    extent = 0.1 * p.er_initial_amount[0, indices[0], cy]
    changed.chemical_amount_increment[0, indices, cy] += extent * np.array([-1, -1, 1])
    chemical = model.regulation_values(changed, p, xp=np)
    assert chemical.rule_factors[4] != other.rule_factors[4]
    np.testing.assert_array_equal(changed.amount_increment, state.amount_increment)
    sodium = spec.model.species_ids.index("Na")
    changed.extracellular_amount_increment[sodium, 2] += 0.01 * p.extracellular_volume[2]
    outer = model.regulation_values(changed, p, xp=np)
    assert outer.rule_factors[5] != chemical.rule_factors[5]
    np.testing.assert_array_equal(outer.rule_factors[6:8], chemical.rule_factors[6:8])
    assert not np.any(outer.samples_mM[6:8, :, 1])
    assert not np.any(outer.samples_mM[:, -3:, 1])
    evidence(
        "owner-views",
        dict(
            initial=before.rule_factors,
            fuel=fuel.rule_factors,
            other_endpoint=other.rule_factors,
            free_calcium=chemical.rule_factors,
            exterior=outer.rule_factors,
            junction_exterior_absent=True,
        ),
    )


def test_existing_gates_and_energy_laws_consume_effective_availability():
    _, state, p, u = initial()
    actual = model.readouts(state, u, p, xp=np)
    expected = base.readouts(state, actual.effective_control, model.base_layout(p), xp=np)
    for a, b in zip(actual.derivative, expected.derivative, strict=True):
        np.testing.assert_array_equal(a, b)
    cycles = model.pump_cycles(actual.derivative)
    demand = np.bincount(model.pump_routes(p).owner, weights=cycles, minlength=p.active.size)
    expected_fuel = np.stack((-demand, demand, demand))
    # Regeneration is already an independent physical supply route.
    supply = np.bincount(
        p.regeneration_owner, weights=actual.regeneration.synthesis_fmol_s, minlength=p.active.size
    )
    expected_fuel += np.stack((supply, -supply, -supply))
    np.testing.assert_allclose(
        actual.derivative.energy_amount_increment_fmol, expected_fuel, rtol=1e-13, atol=3e-14
    )
    off = model.readouts(
        state,
        u._replace(channel=np.zeros_like(u.channel), junction=np.zeros_like(u.junction)),
        p,
        xp=np,
    )
    # Availability does not directly freeze the intrinsic ODEs; altered field
    # values can still change their target rates through the existing solver.
    off_parent = base.readouts(state, off.effective_control, model.base_layout(p), xp=np)
    np.testing.assert_array_equal(off.derivative.channel_gate, off_parent.derivative.channel_gate)
    np.testing.assert_array_equal(off.derivative.junction_gate, off_parent.derivative.junction_gate)
    assert np.any(off.derivative.junction_gate != 0)
    evidence(
        "physical-consumers",
        dict(
            no_added_state=True,
            no_added_ATP_cost=True,
            fuel_slope=expected_fuel,
            energy_balance_pJ_s=actual.field.energy_balance_pJ_s,
        ),
    )


FAULTS = (
    "wrong-membrane-owner",
    "wrong-exterior",
    "cross-fuel",
    "junction-not-endpoint",
    "junction-exterior",
    "junction-env-term",
    "channel-fuel-env",
    "voltage-feedback",
    "native-Dm",
    "native-conductance",
    "profile",
    "init-override",
    "negative-floor",
    "large-floor",
    "dedicated-calcium-target",
    "wrong-native-target",
    "unknown-kind",
    "malformed-kind",
    "duplicate-id",
    "unknown-species",
    "wrong-scope",
    "negative-max",
    "large-max",
)


@pytest.mark.parametrize("fault", FAULTS)
def test_unsupported_ownership_controls_and_native_scopes_refuse(fault):
    raw = fixtures.definition()
    block = raw["model"]["network_regulation"]
    ch, gj, nak = block["rules"][4], block["rules"][7], block["rules"][0]
    conf = ch["configuration"]
    if fault == "wrong-membrane-owner":
        ch["sample_cell_id"] = "cell_1"
        ch["fuel_pool_id"] = "fuel_cell_1"
    if fault == "wrong-exterior":
        ch["sample_exterior_id"] = "outside_1"
    if fault == "cross-fuel":
        ch["fuel_pool_id"] = "fuel_cell_1"
    if fault == "junction-not-endpoint":
        gj["sample_cell_id"] = "absent"
    if fault == "junction-exterior":
        gj["sample_exterior_id"] = "outside_0"
    if fault == "junction-env-term":
        gj["configuration"]["activator zone"] = ["env"]
    if fault == "channel-fuel-env":
        conf["activator zone"] = ["env"]
    if fault == "voltage-feedback":
        conf["channel activators"] = ["Na*"]
    if fault == "native-Dm":
        conf["max Dm"] = 1e-18
    if fault == "native-conductance":
        conf["max conductivity"] = 0.0
    if fault == "profile":
        conf["apply to"] = ["some_profile"]
    if fault == "init-override":
        conf["init active"] = False
    if fault == "negative-floor":
        conf["inhibitor max"] = [-0.1]
    if fault == "large-floor":
        conf["inhibitor max"] = [1.1]
    if fault == "dedicated-calcium-target":
        ch["target_id"] = raw["model"]["calcium_channels"][0]["id"]
    if fault == "wrong-native-target":
        gj["configuration"]["target"] = "Na/K-ATPase"
    if fault == "unknown-kind":
        ch["kind"] = "new-physics"
    if fault == "malformed-kind":
        ch["kind"] = []
    if fault == "duplicate-id":
        block["rules"].append(deepcopy(ch))
    if fault == "unknown-species":
        conf["channel activators"] = ["missing"]
    if fault == "wrong-scope":
        block["channel_scope"] = "native_core_equivalence"
    if fault == "negative-max":
        nak["configuration"]["max effect"] = -0.1
    if fault == "large-max":
        gj["configuration"]["max effect"] = 1.1
    # Exercise the exact boundary validator against the already parsed parent;
    # the roundtrip tests separately execute the complete public @2 parser.
    with pytest.raises(ConfigError):
        schema._rules(block, cached()[0].model)
    evidence("rejected-" + fault, dict(fault=fault, input=raw))


def test_unbounded_rule_refuses_even_when_shadowed_and_consumer_is_off():
    raw = fixtures.definition("ordered", compact=True)
    raw["model"]["energy_pools"][0]["initial_amount_fmol"].update(ATP=0.2, ADP=20.0, Pi=20.0)
    # The shadowed channel direct factor starts in [0,1] and later leaves it.
    conf = raw["model"]["network_regulation"]["rules"][4]["configuration"]
    for k in list(conf):
        if k.startswith(("channel activator", "channel inhibitor", "activator ", "inhibitor ")):
            conf.pop(k)
    conf.update({"channel activators": ["ATP&"], "activator Km": [1.0], "activator n": [1.0]})
    # Leave an identity final write so only the shadowed rule escapes.
    last = raw["model"]["network_regulation"]["rules"][-2]["configuration"]
    for k in list(last):
        if k.startswith(("channel activator", "activator ")):
            last.pop(k)
    spec = schema.parse(raw)
    state, p = model.initial_values(spec)
    changed = model.STATE_TYPE(*(v.copy() for v in state))
    changed.energy_amount_increment_fmol[:, 0] += p.volume[0] * np.array([1.1, -1.1, -1.1])
    assert base.domain_valid(changed, model.base_layout(p), p.active, xp=np)
    table = schema.control_values(spec, [0.0])
    u = type(table)(*(v[0] for v in table))._replace(channel=np.zeros(p.channel_active.size))
    value = model.regulation_values(changed, p, xp=np)
    assert value.rule_factors[4] > 1 and not value.valid
    assert not model.control_domain_valid(changed, u, p, p.active, xp=np)
    assert not model.readouts(changed, u, p, xp=np).valid
    assert all(np.all(np.isnan(v)) for v in model.rhs(changed, u, p, p.active, xp=np))
    with pytest.raises(NumericalError):
        model.check_values(changed, spec)
    c = reference.bind(schema.to_dict(spec))
    with pytest.raises(ValueError):
        reference.evaluate(c, reference.flatten(c, changed._asdict()), 0.0)
    evidence(
        "factor-escape",
        dict(raw=raw, factors=value.rule_factors, shadowed=True, consumer_off=True, clipping=False),
    )


def test_observer_uses_all_three_effective_control_families():
    spec, state, p, u = initial()
    times = np.asarray([0.0])
    history = model.STATE_TYPE(*(v[None, ...] for v in state))
    actual = model.observe_history(times, history, p, times, spec)
    value = model.readouts(state, u, p, xp=np)
    parent = schema.base_spec(spec)
    controls = {
        key: tuple(
            (ChannelChange(0.0, float(a)),)
            for a in getattr(value.effective_control, key)[
                : len(
                    getattr(
                        parent.model,
                        "membranes"
                        if key == "pump"
                        else "channels"
                        if key == "channel"
                        else "junctions",
                    )
                )
            ]
        )
        for key in ("pump", "channel", "junction")
    }
    parent = replace(
        parent,
        experiment=replace(
            parent.experiment,
            pumps=controls["pump"],
            channels=controls["channel"],
            junctions=controls["junction"],
        ),
    )
    expected = base.observe_history(times, history, model.base_layout(p), times, parent)
    for key in base.OBSERVATION_FIELDS:
        np.testing.assert_array_equal(getattr(actual, key), getattr(expected, key))
    for key in ("pump", "channel", "junction"):
        prefix = "nak" if key == "pump" else key
        np.testing.assert_array_equal(
            getattr(actual, prefix + "_effective_availability")[0],
            getattr(value.effective_control, key),
        )
    evidence(
        "observation",
        dict(inherited_fields=len(base.OBSERVATION_FIELDS), all_effective_control_families=True),
    )


def integrate_cpu(raw, refinement):
    spec = schema.parse(raw)
    state, p = model.initial_values(spec)
    knots = reference.event_times(raw)
    times = [knots[0]]
    for a, b in zip(knots[:-1], knots[1:], strict=True):
        count = max(1, int(np.ceil((b - a) / (0.625e-6 / refinement) - 2e-13)))
        times.extend(np.linspace(a, b, count + 1)[1:])
    times = np.asarray(times)
    table = schema.control_values(spec, times[:-1])
    model.check_steps(spec, np.diff(times), table)
    history = [state]
    for i, step in enumerate(np.diff(times)):
        u = type(table)(*(v[i] for v in table))

        def rhs(y, u, p, a):
            assert model.control_domain_valid(y, u, p, a, xp=np)
            return model.rhs(y, u, p, a, xp=np)

        state = rk4_step(rhs, state, float(step), u, p, p.active)
        assert model.control_domain_valid(state, u, p, p.active, xp=np)
        history.append(state)
    stacked = model.STATE_TYPE(*(np.stack(v) for v in zip(*history, strict=True)))
    return spec, p, times, stacked, model.check_values(stacked, spec)


def test_coupled_refinement_events_all_fields_and_exact_split():
    raw = fixtures.probe()
    folder = os.environ.get("CELLS_REGULATION_V2_OUTPUT")
    if folder:
        capture = json.loads((Path(folder) / "evidence/independent-v2.json").read_text())
        assert capture["inputs"] == raw and capture["production_imported"] is False
        assert not capture["execution"]["pytest_imported"]
        with np.load(Path(folder) / "references/v2.npz") as data:
            knots, expected = data["times"], data["state"]
        c, proof = reference.bind(raw), capture["solver"]
    else:
        c, knots, expected, proof = reference.integrate(raw)
    records = []
    for refinement in (1, 2, 4):
        spec, p, times, history, diagnostics = integrate_cpu(raw, refinement)
        actual = reference.flatten(c, history._asdict())[
            [int(np.flatnonzero(times == t)[0]) for t in knots]
        ]
        ratio = compare(c, actual, expected, atol=2e-11, rtol=3e-8)
        error = float(np.max(np.abs(actual[-1] - expected[-1])))
        records.append(
            dict(
                refinement=refinement,
                error=error,
                max_error_over_budget=ratio,
                physical_diagnostics=diagnostics,
            )
        )
        start = model.regulation_values(model.STATE_TYPE(*(v[0] for v in history)), p, xp=np)
        end = model.regulation_values(model.STATE_TYPE(*(v[-1] for v in history)), p, xp=np)
        assert np.any(start.channel_factor != end.channel_factor)
        assert np.any(start.junction_factor != end.junction_factor)
        if refinement == 1:
            split = int(np.flatnonzero(times == 2.5e-6)[0])
            restored = model.STATE_TYPE(*(v[split].copy() for v in history))
            table = schema.control_values(spec, times[split:-1])
            for j, step in enumerate(np.diff(times[split:])):
                u = type(table)(*(v[j] for v in table))
                restored = rk4_step(
                    lambda y, u, p, a: model.rhs(y, u, p, a, xp=np),
                    restored,
                    float(step),
                    u,
                    p,
                    p.active,
                )
            for a, b in zip(restored, history, strict=True):
                np.testing.assert_array_equal(a, b[-1])
    assert records[-1]["error"] < records[0]["error"]
    evidence(
        "coupled-refinement",
        dict(
            inputs=raw,
            adaptive=proof,
            records=records,
            fields=38,
            exact_in_memory_split=True,
            compiled_dispatch_qualified=False,
        ),
        dict(times=knots, reference=expected),
    )
