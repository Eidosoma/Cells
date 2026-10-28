"""Shared finite fuel: signs, ownership, internal work, clocks and complete state."""

from copy import deepcopy
from dataclasses import replace

import jax
import numpy as np
import pytest

from cells.assembly_cell.io import flatten, load_checkpoint, write_checkpoint
from cells.assembly_cluster import engine as assembly
from cells.assembly_cluster.controls import modulate
from cells.assembly_cluster.spec import channel_owners
from cells.assembly_cluster.spec import parse_spec as parse_assembly
from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.errors import NumericalError
from cells.core.runner import branch_checkpoint, run, timeline, validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import Checkpoint
from cells.core.surface_calcium_energy_spec import initial_prior_spec
from cells.ensemble import ionic
from cells.ensemble.cluster import aggregate
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import surface_calcium_catalog as prior
from cells.models import surface_calcium_energy as model
from cells.models.registry import get_model
from cells.processes import finite_energy as energy
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.tissue import surface_calcium_energy_fixtures as fixtures
from validation.tissue import surface_calcium_energy_reference as reference


def initial(raw=None, time=0.0):
    spec = parse_spec(fixtures.definition() if raw is None else raw)
    state, p = model.initial_values(spec)
    controls = control_values(spec, [time])
    return spec, state, p, type(controls)(*(v[0] for v in controls))


def compare(spec, state, value, *, time=0.0):
    c = reference.bind(spec.to_dict())
    expected, _, proof = reference.evaluate(c, reference.flatten(c, state._asdict()), time)
    actual = reference.flatten(c, value.derivative._asdict())
    ratio = assert_states(c, actual, expected, atol=3e-12, charge_atol=3e-23, rtol=3e-10)
    assert value.valid and abs(value.field.energy_balance_pJ_s) < 2e-10
    return dict(max_error_over_budget=ratio, independent_stage=proof)


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_identity_roundtrip_and_execution_registration(backend):
    raw = fixtures.definition(backend=backend)
    spec, state, p, _ = initial(raw)
    assert get_model(spec.model) is model and type(p) is model.LAYOUT_TYPE
    assert spec == parse_spec(spec.to_dict()) and len(state) == 38
    assert get_model(initial_prior_spec(spec).model) is prior
    assert set(p.channel_laws[p.channel_active]) == set(range(35))
    assert (
        ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation == spec
    )
    batch = BatchSpec((WorldSpec(9, spec), WorldSpec(71, spec)), 2, 2048, 2**32)
    assert parse_batch(batch.to_dict()) == batch
    timeline(spec)


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_independent_complete_stages(arm, padded):
    spec, state, p, u = initial(fixtures.definition(arm, padded=padded))
    value = model.readouts(state, u, p, xp=np)
    checked = compare(spec, state, value)
    assert model.control_domain_valid(state, u, p, p.active, xp=np)
    assert model.check_values(state, spec)["max_pool_energy_error"] == 0
    stage = model.stage_layout(state, p, xp=np)
    equivalent = prior.readouts(model.prior_state(state), model.prior_control(u), stage, xp=np)
    exact(model.prior_state(value.derivative), equivalent.derivative)
    cycles = model.pump_cycles(value.derivative)
    if arm in ("blocked", "absent"):
        assert not np.any(cycles)
        assert np.any(value.derivative.plasma_exchange_cycles)  # NCX spends no ATP.
    if arm == "reverse":
        assert np.any(cycles < 0)
        with pytest.raises(ConfigError, match="chemical/transport loss"):
            timeline(spec)
    if padded:
        assert not np.any(value.derivative.energy_amount_increment_fmol[:, -1])
        assert not value.derivative.regeneration_cycles_fmol[-1]
    evidence(
        f"finite-calcium-stage-{arm}-{padded}",
        dict(
            status="passed", inputs=spec.to_dict(), scope="instantaneous complete stage", **checked
        ),
    )


@pytest.mark.parametrize("owner", [0, 1])
def test_live_owner_fuel_updates_three_families_and_excludes_ncx(owner):
    spec, state, p, u = initial()
    changed = model.STATE_TYPE(*(v.copy() for v in state))
    changed.energy_amount_increment_fmol[:, owner] = 0.2 * np.array([-1.0, 1.0, 1.0])
    before, after = (model.readouts(y, u, p, xp=np) for y in (state, changed))
    for key in ("pump_cycles", "plasma_pump_cycles"):
        first, second = getattr(before.derivative, key), getattr(after.derivative, key)
        assert np.any(first[p.membrane_cell == owner] != second[p.membrane_cell == owner])
        np.testing.assert_array_equal(
            first[p.membrane_cell != owner], second[p.membrane_cell != owner]
        )
    assert (
        before.derivative.er_pump_transferred[owner] != after.derivative.er_pump_transferred[owner]
    ).any()
    np.testing.assert_array_equal(
        before.derivative.plasma_exchange_cycles, after.derivative.plasma_exchange_cycles
    )
    rate = after.derivative
    demand = np.bincount(
        model.pump_routes(p).owner, weights=model.pump_cycles(rate), minlength=p.active.size
    )
    regen = np.bincount(
        p.regeneration_owner, weights=rate.regeneration_cycles_fmol, minlength=p.active.size
    )
    np.testing.assert_allclose(
        rate.energy_amount_increment_fmol,
        np.array([-1, 1, 1])[:, None] * (demand - regen),
        atol=1e-15,
        rtol=1e-14,
    )
    checked = compare(spec, changed, after)
    evidence(f"finite-calcium-live-owner-{owner}", dict(status="passed", **checked))


def test_regeneration_clock_and_no_port_case():
    spec, state, p, u = initial(fixtures.compact_probe())
    event = 20 * spec.execution.dt
    times = timeline(spec)
    assert event in times
    controls = control_values(spec, [event - spec.execution.dt, event])
    assert controls.regeneration[0, 0] == 0.8 and controls.regeneration[1, 0] == 0
    for key in controls._fields[:-1]:
        np.testing.assert_array_equal(getattr(controls, key)[0], getattr(controls, key)[1])
    raw = spec.to_dict()
    raw["model"]["regeneration_ports"].append(
        raw["model"]["regeneration_ports"][0] | dict(id="extra_supply")
    )
    raw["experiment"]["regeneration_controls"].append(
        dict(regeneration_id="extra_supply", schedule=[dict(time=0.0, availability=0.8)])
    )
    raw["execution"]["regeneration_capacity"] = 3
    shared, newer, layout, held = initial(raw)
    value = model.readouts(newer, held, layout, xp=np)
    np.testing.assert_array_equal(
        value.regeneration.synthesis_fmol_s[0], value.regeneration.synthesis_fmol_s[2]
    )
    compare(shared, newer, value)
    raw["model"]["regeneration_ports"] = []
    raw["experiment"]["regeneration_controls"] = []
    raw["execution"]["regeneration_capacity"] = 0
    spec, state, p, u = initial(raw)
    value = model.readouts(state, u, p, xp=np)
    assert value.valid and not value.regeneration.synthesis_fmol_s.size
    compare(spec, state, value)


@pytest.mark.parametrize(
    "fault",
    [
        "nak_owner",
        "pmca_owner",
        "er_owner",
        "maintained",
        "missing_pool",
        "duplicate_port",
        "capacity",
        "control",
        "law",
        "species",
    ],
)
def test_reject_ambiguous_fuel_schema(fault):
    raw = fixtures.definition()
    m = raw["model"]
    pumps = [
        m["ionic"]["membranes"][0]["pump"],
        m["plasma_transport"]["membranes"][0]["pump"],
        m["stores"][0]["model"]["membrane"]["pump"],
    ]
    if fault.endswith("_owner"):
        pumps[("nak_owner", "pmca_owner", "er_owner").index(fault)]["metabolism"]["pool_id"] = (
            "fuel_cell_1"
        )
    elif fault == "maintained":
        pumps[1]["atp_mM"] = 1.5
    elif fault == "missing_pool":
        m["energy_pools"].pop()
    elif fault == "duplicate_port":
        m["regeneration_ports"][1]["id"] = m["regeneration_ports"][0]["id"]
    elif fault == "capacity":
        raw["execution"]["regeneration_capacity"] = 1
    elif fault == "control":
        raw["experiment"]["regeneration_controls"][0]["schedule"][0]["availability"] = True
    elif fault == "law":
        pumps[2]["law"] = "betse_1_5_er_calcium_pump_positive@1"
    else:
        # Reserved energy owner cannot be added as another chemical species.
        for row in m["stores"]:
            row["model"]["species"][1]["id"] = "ATP"
    with pytest.raises(ConfigError):
        parse_spec(raw)


@pytest.mark.parametrize(
    "fault",
    [
        "exhaustion",
        "negative",
        "nan",
        "padding",
        "control_padding",
        "blocked_invalid",
        "regeneration_heat",
    ],
)
def test_strict_fuel_domain_even_with_blocked_pumps(fault):
    _, state, p, u = initial(fixtures.definition("blocked"))
    if fault in ("exhaustion", "negative", "nan", "blocked_invalid"):
        state.energy_amount_increment_fmol[0, 0] = (
            np.nan
            if fault == "nan"
            else -p.energy_initial_amount_fmol[0, 0] - (0.1 if fault == "negative" else 0.0)
        )
    elif fault == "padding":
        state.energy_amount_increment_fmol[0, -1] = 1e-6
    elif fault == "control_padding":
        u.regeneration[-1] = 0.1
    else:
        state.regeneration_dissipated_energy_pJ[-1] = 1.0
    assert not model.control_domain_valid(state, u, p, p.active, xp=np)


@pytest.mark.parametrize("name", model.STATE_TYPE._fields)
def test_every_state_field_keeps_accounting_guards(name):
    spec, state, _, _ = initial()
    wrong = getattr(state, name).copy()
    wrong.flat[0] += 1.1 if name.endswith("gate") else (1e-16 if name.endswith("_C") else 0.01)
    with pytest.raises(NumericalError):
        model.check_values(state._replace(**{name: wrong}), spec)


def test_conserved_calcium_loss_bound_covers_changing_fuel():
    spec, _, _, _ = initial()
    bound = prior.loss_bound(model.bounded_prior_spec(spec))
    for fraction in (1e-6, 0.1, 0.5, 0.99):
        raw = spec.to_dict()
        for pool in raw["model"]["energy_pools"]:
            a, d, pi = (pool["initial_amount_fmol"][k] for k in energy.SPECIES)
            new_a = fraction * min(a + d, a + pi)
            delta = a - new_a
            pool["initial_amount_fmol"] = dict(ATP=new_a, ADP=d + delta, Pi=pi + delta)
        current = parse_spec(raw)
        assert prior.loss_bound(initial_prior_spec(current)) <= bound
    evidence("finite-calcium-conserved-bound", dict(status="passed", loss_bound_per_s=bound))


def test_complete_snapshot_and_supply_branch(tmp_path):
    spec, state, p, _ = initial(fixtures.compact_probe())
    checkpoint = Checkpoint(state, p, 0.0, 0, event_index(spec, 0.0))
    write_snapshot(tmp_path / "initial", spec, checkpoint)
    saved = load_snapshot(tmp_path / "initial")
    assert saved.spec == spec and type(saved.checkpoint.layout) is model.LAYOUT_TYPE
    exact(saved.checkpoint.state, state)
    exact(saved.checkpoint.layout, p)
    with pytest.raises(ConfigError, match="state/layout"):
        validate_checkpoint(spec, replace(checkpoint, state=model.prior_state(state)))
    raw = spec.to_dict()
    raw["experiment"]["regeneration_controls"][0]["schedule"][-1]["availability"] = 0.5
    exact(branch_checkpoint(spec, checkpoint, parse_spec(raw)).state, state)
    raw["model"]["energy_pools"][0]["initial_amount_fmol"]["ATP"] *= 2
    with pytest.raises(ConfigError, match="model or execution"):
        branch_checkpoint(spec, checkpoint, parse_spec(raw))


def test_assembly_control_keeps_explicit_fuel_supply_and_independent_stage():
    spec = parse_assembly(fixtures.assembly_definition())
    _, state, p, control = initial(spec.ionic.to_dict())
    levels = np.array([0.0, 1.0])
    held = modulate(control, levels, channel_owners(spec))
    np.testing.assert_array_equal(control.regeneration, held.regeneration)
    value = model.readouts(state, held, p, xp=np)
    c = reference.bind(spec.ionic.to_dict())
    target, _, _ = reference.evaluate(c, reference.initial(c), 0, channel_levels=levels)
    assert value.valid
    assert_states(
        c,
        reference.flatten(c, value.derivative._asdict()),
        target,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )


def test_assembly_fuel_report_aggregation_and_complete_checkpoint(tmp_path):
    spec = parse_assembly(fixtures.assembly_definition())
    state = assembly.initial_state(spec)
    report = assembly.summary(spec, state) | dict(
        arm="finite-calcium", wall_start=0.0, wall_end=1.0, execute_seconds=0.0
    )
    assert report["physical_model"] == model.MODEL_ID
    fuel = report["finite_energy"]
    assert fuel["cell_ids"] == report["cell_ids"]
    assert fuel["species"] == ["ATP", "ADP", "Pi"]
    combined = aggregate([report, report])["finite-calcium"]
    np.testing.assert_allclose(
        combined["finite_energy"]["amount_fmol_sum_over_worlds"],
        2 * np.array(fuel["amount_fmol"]).sum(axis=0),
        rtol=0,
        atol=0,
    )
    for key in ("finite_energy", "ip3", "calcium", "channel_transfer_axes"):
        wrong = deepcopy(report)
        wrong.pop(key)
        with pytest.raises(ValueError):
            aggregate([report, wrong])
    for fault in ("owner", "port_owner", "shape", "amount", "heat"):
        wrong = deepcopy(report)
        data = wrong["finite_energy"]
        if fault == "owner":
            data["cell_ids"].reverse()
        elif fault == "port_owner":
            data["port_pool_ids"][0] = "unknown"
        elif fault == "shape":
            data["amount_fmol"] = []
        elif fault == "amount":
            data["amount_fmol"][0][0][0] = 0.0
        else:
            data["regeneration_dissipated_energy_pJ"][0][0] = -0.1
        with pytest.raises(ValueError):
            aggregate([report, wrong])
    write_checkpoint(tmp_path / "assembly", spec, state, backend="cpu")
    restored, newer, _ = load_checkpoint(tmp_path / "assembly", backend="cpu")
    assert restored == spec
    exact(flatten(newer).values(), flatten(state).values())
    evidence(
        "finite-calcium-assembly",
        dict(
            status="passed",
            inputs=spec.to_dict(),
            report=report,
            scope="Initial ownership/report/checkpoint and stage controls; no assembly trajectory",
        ),
    )


def test_compiled_full_stage_and_exhaustion_guard():
    spec, state, p, u = initial()
    evaluate = jax.jit(
        lambda y, c, q: (
            model.rhs(y, c, q, q.active),
            model.control_domain_valid(y, c, q, q.active),
        )
    )
    got, valid = evaluate(state, u, p)
    c = reference.bind(spec.to_dict())
    expected, _, proof = reference.evaluate(c, reference.initial(c), 0)
    ratio = assert_states(
        c, reference.flatten(c, got._asdict()), expected, atol=3e-12, charge_atol=3e-23, rtol=3e-10
    )
    assert valid
    changed = state._replace(energy_amount_increment_fmol=state.energy_amount_increment_fmol.copy())
    changed.energy_amount_increment_fmol[0, 0] = -p.energy_initial_amount_fmol[0, 0]
    failed, valid = evaluate(changed, u, p)
    assert not valid and all(np.isnan(v).all() for v in failed)
    evidence(
        "finite-calcium-compiled-stage",
        dict(
            status="passed",
            inputs=spec.to_dict(),
            max_error_over_budget=ratio,
            independent_stage=proof,
        ),
    )


def test_compiled_early_trajectory_and_full_snapshot(tmp_path):
    raw = fixtures.compact_probe()
    result = run(parse_spec(raw))
    c = reference.bind(raw)
    expected = reference.integrate(raw)
    actual, target = reference.flatten(c, vars(result.observations)), np.array(expected["state"])
    report = dict(
        status="captured",
        inputs=raw,
        diagnostics=result.diagnostics,
        independent_reference={
            k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in expected.items()
        },
        scope="50-us shared fuel/chemical/electrical feedback; no settling/recovery claim",
    )
    evidence(
        "finite-calcium-early-trajectory",
        report,
        dict(observed=actual, reference=target, signed_error=actual - target),
    )
    write_run(tmp_path / "early", result)
    ratio = assert_states(c, actual, target)
    saved = load_snapshot(tmp_path / "early/checkpoint_final")
    exact(saved.checkpoint.state, result.final.state)
    exact(saved.checkpoint.layout, result.final.layout)
    assert saved.spec == result.spec
    evidence(
        "finite-calcium-early-trajectory",
        report | dict(status="passed", max_error_over_budget=ratio, complete_final_snapshot=True),
    )
