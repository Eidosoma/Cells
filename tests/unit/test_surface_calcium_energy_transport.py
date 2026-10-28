"""Native transporter coupling: physical owners, explicit work and complete state."""

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
from cells.core.runner import run, timeline, validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import Checkpoint
from cells.core.surface_calcium_energy_transport_spec import base_spec
from cells.ensemble import ionic
from cells.ensemble.cluster import aggregate
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import surface_calcium_energy_transport as model
from cells.models.registry import get_model
from tests.unit.test_morris_lecar_catalog import perturb_free_calcium
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.tissue import calcium_energy_network_transport_fixtures as fixtures
from validation.tissue import calcium_energy_network_transport_reference as reference
from validation.tissue import hcn_extra_catalog_fixtures as hcn


def initial(raw=None):
    spec = parse_spec(fixtures.definition() if raw is None else raw)
    state, p = model.initial_values(spec)
    table = control_values(spec, [0.0])
    return spec, state, p, type(table)(*(v[0] for v in table))


def compare(spec, state, derivative, *, time=0.0, levels=None):
    c = reference.bind(spec.to_dict())
    target, _, proof = reference.evaluate(
        c, reference.flatten(c, state._asdict()), time, channel_levels=levels
    )
    ratio = assert_states(
        c,
        reference.flatten(c, derivative._asdict()),
        target,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    return dict(max_error_over_budget=ratio, independent_stage=proof)


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_all_42_stage_rates_match_independent_source(arm, padded):
    spec, state, p, u = initial(fixtures.definition(arm, padded=padded))
    value = model.readouts(state, u, p, xp=np)
    assert value.valid
    checked = compare(spec, state, value.derivative)
    assert abs(value.field.energy_balance_pJ_s) < 1e-10
    assert len(state) == 42 and type(p) is model.LAYOUT_TYPE
    assert model.check_values(state, spec)["max_energy_error"] == 0
    if arm in ("empty", "blocked"):
        assert not np.any(value.derivative.network_transferred_fmol)
    evidence(
        f"network-stage-{arm}-{padded}", dict(status="passed", inputs=spec.to_dict(), **checked)
    )


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_roundtrip_registry_batch_and_full_clock(backend):
    raw = fixtures.compact_probe(backend=backend, padded=True)
    spec, _, _, _ = initial(raw)
    assert parse_spec(spec.to_dict()) == spec
    assert get_model(spec.model) is model
    assert (
        ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation == spec
    )
    batch = BatchSpec((WorldSpec(3, spec), WorldSpec(79, spec)), 2, 2048, 2**32)
    assert parse_batch(batch.to_dict()) == batch
    timeline(spec)
    times = [0, 13.3e-6, 15 * raw["execution"]["dt"], 31.1e-6]
    assert set(times) <= {c.time for c in spec.experiment.changes}
    table = control_values(spec, times)
    np.testing.assert_array_equal(table.network_transport[:, 2], [0.8, 0.0, 0.0, 0.6])
    np.testing.assert_array_equal(table.regeneration[:, 0], [0.8, 0.8, 0.0, 0.0])


@pytest.mark.parametrize("arm", ["empty", "blocked"])
def test_absent_or_blocked_transport_preserves_parent_bitwise(arm):
    spec, state, p, u = initial(fixtures.definition(arm))
    parent_spec = base_spec(spec)
    parent = get_model(parent_spec.model)
    old, q = parent.initial_values(parent_spec)
    exact(old, model.base_state(state))
    a = parent.readouts(old, model.base_control(u), q, xp=np)
    b = model.readouts(state, u, p, xp=np)
    exact(a.derivative, model.base_state(b.derivative))
    exact(jax.tree.leaves(a.field), jax.tree.leaves(b.field))


def test_transport_reaches_actual_chemical_owner_without_direct_atp_demand():
    spec, state, p, u = initial()
    held = u._replace(network_transport=np.zeros_like(u.network_transport))
    on, off = (model.readouts(state, c, p, xp=np) for c in (u, held))
    difference = type(state)(*(a - b for a, b in zip(on.derivative, off.derivative, strict=True)))
    np.testing.assert_array_equal(difference.energy_amount_increment_fmol, 0)
    for key in ("er_passive_transferred", "er_pump_transferred", "er_release_transferred"):
        np.testing.assert_array_equal(getattr(difference, key), 0)
    for i in range(len(spec.model.cells)):
        expected = p.free_ion_selector @ difference.amount_increment[:, i]
        np.testing.assert_allclose(
            difference.chemical_amount_increment[i, :, int(p.er_cytosol[i])],
            expected,
            atol=3e-13,
            rtol=3e-12,
        )
    np.testing.assert_allclose(
        difference.amount_increment.sum(axis=-1)
        + difference.extracellular_amount_increment.sum(axis=-1),
        0,
        atol=3e-13,
    )
    assert on.derivative.network_supplied_work_pJ[2] != 0
    assert np.all(on.network_heat_pJ_s >= 0)


@pytest.mark.parametrize(
    "fault",
    [
        "constant",
        "law",
        "accounting",
        "drive",
        "irreversible",
        "conversion",
        "duplicate",
        "owner",
        "ignore_ecm",
        "profile",
        "no_transfer",
        "capacity",
        "negative_density",
        "control",
        "negative_regulation",
    ],
)
def test_inconsistent_physical_contracts_are_rejected(fault):
    raw = fixtures.definition()
    block = raw["model"]["network_transport"]
    route = block["routes"][0]
    cfg = route["configuration"]
    if fault == "constant":
        block["constants"]["faraday_C_mol"] = 96485.0
    elif fault in ("law", "accounting"):
        block[fault] = "unqualified@1"
    elif fault == "drive":
        route["drive"]["supplied_energy_J_per_mol"] = 123.0
    elif fault == "irreversible":
        cfg["standard free energy"] = None
    elif fault == "conversion":
        cfg["products"] = ["Na", "Cl"]
    elif fault == "duplicate":
        cfg["reactants"] = ["K", "K"]
    elif fault == "owner":
        route["membrane_id"] = "unowned"
    elif fault == "ignore_ecm":
        cfg["ignore ECM"] = True
    elif fault == "profile":
        cfg["apply to"] = ["tissue"]
    elif fault == "no_transfer":
        cfg["transfered out of cell"] = cfg["transfered into cell"][:]
    elif fault == "capacity":
        raw["execution"]["network_transport_capacity"] = 1
    elif fault == "negative_density":
        route["density_multiplier"] = -1.0
    elif fault == "control":
        raw["experiment"]["network_transport_controls"][0]["schedule"][0]["availability"] = -1.0
    else:
        cfg.update({"transporter inhibitors": ["K&"], "inhibitor Km": [1.0], "inhibitor n": [1.0]})
        raw["experiment"]["network_transport_controls"][0]["schedule"][0]["availability"] = 0.0
    with pytest.raises(ConfigError):
        parse_spec(raw)


@pytest.mark.parametrize(
    "fault", ["padding", "heat", "cycles", "work", "ownership", "unsupported_transfer"]
)
def test_corrupted_state_is_rejected(fault):
    spec, state, p, u = initial()
    if fault == "padding":
        state.network_cycles_fmol[-1] = 1e-4
    elif fault == "heat":
        state.network_dissipated_energy_pJ[0] = -1e-4
    elif fault == "cycles":
        state.network_cycles_fmol[0] = 1e-4
    elif fault == "work":
        state.network_supplied_work_pJ[2] = 1e-4
    elif fault == "ownership":
        state.amount_increment[0, 0] = 1e-3
    else:
        state.network_transferred_fmol[spec.model.species_ids.index("Ca"), 0] = 1e-4
    with pytest.raises(NumericalError):
        model.check_values(state, spec)
    if fault != "ownership":
        assert not model.control_domain_valid(state, u, p, p.active, xp=np)


def test_snapshot_retains_all_fields_and_rejects_parent_layout(tmp_path):
    spec, state, p, _ = initial(fixtures.compact_probe())
    point = Checkpoint(state, p, 0.0, 0, event_index(spec, 0.0))
    write_snapshot(tmp_path / "initial", spec, point)
    saved = load_snapshot(tmp_path / "initial")
    assert saved.spec == spec and type(saved.checkpoint.layout) is model.LAYOUT_TYPE
    exact(saved.checkpoint.state, state)
    exact(saved.checkpoint.layout, p)
    with pytest.raises(ConfigError, match="state/layout"):
        validate_checkpoint(spec, replace(point, layout=model.base_layout(p)))


def assembly_definition():
    raw = hcn.assembly_definition("energy")
    raw["ionic"] = fixtures.compact_probe(padded=True)
    dt = raw["ionic"]["execution"]["dt"]
    raw["ionic"]["experiment"]["observation_times"] = [i * dt for i in (0, 10, 20, 30, 40)]
    for binding in raw["pools"]:
        binding["pool"]["end_time_s"] = raw["ionic"]["experiment"]["end_time"]
    return raw


def test_assembly_controls_owners_reports_and_complete_checkpoint(tmp_path):
    spec = parse_assembly(assembly_definition())
    _, state, p, u = initial(spec.ionic.to_dict())
    levels = np.array([0.0, 1.0])
    held = modulate(u, levels, channel_owners(spec))
    np.testing.assert_array_equal(held.network_transport, u.network_transport)
    value = model.readouts(state, held, p, xp=np)
    assert value.valid
    compare(spec.ionic, state, value.derivative, levels=levels)
    combined = assembly.initial_state(spec)
    report = assembly.summary(spec, combined) | dict(
        arm="transport", wall_start=0.0, wall_end=1.0, execute_seconds=0.0
    )
    assert aggregate([report, report])["transport"]["worlds"] == 2 * spec.pool.worlds
    for key in ("ip3", "calcium", "finite_energy", "network_transport", "channel_transfer_axes"):
        wrong = deepcopy(report)
        wrong.pop(key)
        with pytest.raises(ValueError):
            aggregate([report, wrong])
    write_checkpoint(tmp_path / "assembly", spec, combined, backend="cpu")
    restored, newer, _ = load_checkpoint(tmp_path / "assembly", backend="cpu")
    assert restored == spec
    exact(flatten(newer).values(), flatten(combined).values())


def test_compiled_two_world_full_42_field_stage_and_failure_isolation():
    spec, state, p, u = initial()
    changed = perturb_free_calcium("energy", spec, state, p)
    changed.channel_gate[:, p.channel_laws == 55] = [[0.51], [0.8]]
    states = model.STATE_TYPE(*(np.stack((a, b)) for a, b in zip(state, changed, strict=True)))
    controls = type(u)(*(np.stack((v, v)) for v in u))
    evaluate = jax.jit(
        jax.vmap(
            lambda y, c, q: (
                model.rhs(y, c, q, q.active),
                model.control_domain_valid(y, c, q, q.active),
            ),
            in_axes=(0, 0, None),
        )
    )
    got, valid = evaluate(states, controls, p)
    assert np.all(valid)
    checks = [
        compare(
            spec, model.STATE_TYPE(*(v[i] for v in states)), model.STATE_TYPE(*(v[i] for v in got))
        )
        for i in (0, 1)
    ]
    bad = states._replace(network_cycles_fmol=states.network_cycles_fmol.copy())
    bad.network_cycles_fmol[1, -1] = 1e-4
    failed, valid = evaluate(bad, controls, p)
    assert np.array_equal(np.asarray(valid), [True, False])
    assert all(np.isnan(v[1]).all() for v in failed)
    exact((v[0] for v in failed), (v[0] for v in got))
    evidence(
        "network-compiled-stage",
        dict(
            status="passed", inputs=spec.to_dict(), world_checks=checks, invalid_world_isolated=True
        ),
    )


def test_compiled_50us_42_field_trajectory_and_final_snapshot(tmp_path):
    raw = fixtures.compact_probe()
    result = run(parse_spec(raw))
    c = reference.bind(raw)
    expected = reference.integrate(raw)
    actual = reference.flatten(c, vars(result.observations))
    target = np.asarray(expected["state"])
    report = dict(
        status="captured",
        inputs=raw,
        diagnostics=result.diagnostics,
        independent_reference={
            k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in expected.items()
        },
        scope="50 us full coupling; long transport settling is separate reduced evidence",
    )
    evidence(
        "network-trajectory",
        report,
        dict(observed=actual, reference=target, signed_error=actual - target),
    )
    ratio = assert_states(c, actual, target)
    write_run(tmp_path / "run", result)
    saved = load_snapshot(tmp_path / "run/checkpoint_final")
    assert saved.spec == result.spec and type(saved.checkpoint.layout) is model.LAYOUT_TYPE
    exact(saved.checkpoint.state, result.final.state)
    exact(saved.checkpoint.layout, result.final.layout)
    evidence(
        "network-trajectory",
        report | dict(status="passed", max_error_over_budget=ratio, complete_final_snapshot=True),
    )
