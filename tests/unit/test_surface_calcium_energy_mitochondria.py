"""Conservative mitochondrial coupling and explicit native/continuous boundaries."""

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
from cells.core.surface_calcium_energy_mitochondria_spec import base_spec
from cells.ensemble import ionic
from cells.ensemble.cluster import aggregate
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import surface_calcium_energy_mitochondria as model
from cells.models.registry import get_model
from cells.processes.electrochemistry import CHARGE_PER_FMOL
from tests.unit.test_surface_calcium_energy_transport import assembly_definition as parent_assembly
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.tissue import calcium_energy_mitochondria_fixtures as fixtures
from validation.tissue import calcium_energy_mitochondria_reference as reference


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


def transferred_calcium(spec, state, p):
    changed = model.STATE_TYPE(*(v.copy() for v in state))
    calcium = spec.model.species_ids.index("Ca")
    chemical = list(s.id for s in spec.model.stores[0].species).index("Ca")
    delta = 0.01 * model.cytosol_amount(state, p, xp=np)[calcium, 0]
    changed.mitochondrial_amount_increment_fmol[calcium, 0] += delta
    changed.mitochondrial_transferred_fmol[calcium, 0] += delta
    changed.chemical_amount_increment[0, chemical, int(p.er_cytosol[0])] -= delta
    return changed


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_complete_45_field_stage_matches_independent_reference(arm, padded):
    spec, state, p, u = initial(fixtures.definition(arm, padded=padded))
    value = model.readouts(state, u, p, xp=np)
    assert value.valid and len(state) == 45
    checked = compare(spec, state, value.derivative)
    assert abs(value.field.energy_balance_pJ_s) < 1e-10
    assert model.check_values(state, spec)["max_energy_error"] == 0
    assert np.all(value.mitochondria.dissipated_power_pJ_s >= 0)
    evidence(
        f"mitochondria-stage-{arm}-{padded}",
        dict(status="passed", inputs=spec.to_dict(), **checked),
    )


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_identity_roundtrip_batch_and_organelle_event_clock(backend):
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
    times = [0, 12.7e-6, 15 * spec.execution.dt, 31.7e-6]
    assert set(times) <= {c.time for c in spec.experiment.changes}
    table = control_values(spec, times)
    np.testing.assert_array_equal(table.mitochondria[:, 0], [0.8, 0, 0, 0.6])
    np.testing.assert_array_equal(table.regeneration[:, 0], [0.8, 0.8, 0, 0])


@pytest.mark.parametrize("arm", ["blocked", "zero-diffusion"])
def test_disabled_mitochondria_preserve_parent_fields_bitwise(arm):
    spec, state, p, u = initial(fixtures.definition(arm))
    parent_spec = base_spec(spec)
    parent = get_model(parent_spec.model)
    old, q = parent.initial_values(parent_spec)
    exact(old, model.base_state(state))
    a = parent.readouts(old, model.base_control(u), q, xp=np)
    b = model.readouts(state, u, p, xp=np)
    exact(a.derivative, model.base_state(b.derivative))
    exact(jax.tree.leaves(a.field), jax.tree.leaves(b.field))
    assert not np.any(b.derivative.mitochondrial_transferred_fmol)


def test_explicit_initial_inventory_voltage_and_paired_countercharge():
    spec, state, p, _ = initial()
    parent = get_model(base_spec(spec).model)
    old, q = parent.initial_values(base_spec(spec))
    exact(old, model.base_state(state))
    exact(q, model.base_layout(p))
    for i, row in enumerate(spec.model.mitochondria):
        np.testing.assert_array_equal(
            model.mitochondrial_amount(state, p)[:, i], row.initial_amount_fmol
        )
    charge = p.mitochondrial_fixed_charge_C + CHARGE_PER_FMOL * np.sum(
        p.valence * model.mitochondrial_amount(state, p), axis=0
    )
    np.testing.assert_allclose(
        charge,
        p.mitochondrial_capacitance_F * p.mitochondrial_initial_voltage_V,
        atol=3e-25,
        rtol=3e-13,
    )
    # Check the capacitor pair before cancelling the much larger ionic/fixed
    # backgrounds; their float64 subtraction need not retain sub-ulp charge.
    np.testing.assert_array_equal(
        p.mitochondrial_capacitance_F * p.mitochondrial_initial_voltage_V
        + p.mitochondrial_initial_countercharge_C,
        0,
    )


def test_internal_charge_and_calcium_ownership_at_nonzero_transfer():
    spec, state, p, u = initial()
    changed = transferred_calcium(spec, state, p)
    a, b = (model.readouts(s, u, p, xp=np) for s in (state, changed))
    assert b.valid
    checked = compare(spec, changed, b.derivative)
    np.testing.assert_array_equal(state.amount_increment, changed.amount_increment)
    np.testing.assert_allclose(
        b.field.rates.membrane_voltage_V, a.field.rates.membrane_voltage_V, rtol=0, atol=3e-14
    )
    assert b.mitochondrial_voltage_V[0] != a.mitochondrial_voltage_V[0]
    held = u._replace(mitochondria=np.zeros_like(u.mitochondria))
    off = model.readouts(changed, held, p, xp=np)
    np.testing.assert_array_equal(b.derivative.amount_increment, off.derivative.amount_increment)
    np.testing.assert_array_equal(
        b.derivative.energy_amount_increment_fmol, off.derivative.energy_amount_increment_fmol
    )
    np.testing.assert_array_equal(
        b.derivative.extracellular_amount_increment, off.derivative.extracellular_amount_increment
    )
    exchange = b.derivative.chemical_amount_increment - off.derivative.chemical_amount_increment
    expected = model.chemical_exchange(b.derivative.mitochondrial_amount_increment_fmol, p, xp=np)
    np.testing.assert_allclose(exchange, expected, atol=3e-13, rtol=3e-12)
    assert abs(b.field.energy_balance_pJ_s) < 1e-10
    evidence("mitochondria-nonzero-owner", dict(status="passed", inputs=spec.to_dict(), **checked))


@pytest.mark.parametrize(
    "fault",
    [
        "law",
        "source_law",
        "initialization",
        "voltage",
        "cytosol_volume_role",
        "constants",
        "duplicate",
        "owner",
        "missing",
        "inventory",
        "diffusion",
        "initial_voltage",
        "volume",
        "control",
        "capacity",
    ],
)
def test_invalid_organelle_contracts_are_rejected(fault):
    raw = fixtures.definition()
    block = raw["model"]["mitochondria"]
    row = block["compartments"][0]
    if fault in ("law", "source_law", "initialization", "voltage", "cytosol_volume_role"):
        block[fault] = "undeclared@1"
    elif fault == "constants":
        block["constants"]["faraday_C_mol"] = 96485.0
    elif fault == "duplicate":
        block["compartments"][1]["id"] = row["id"]
    elif fault == "owner":
        row["cell_id"] = "unowned"
    elif fault == "missing":
        block["compartments"].pop()
    elif fault == "inventory":
        row["initial_amount_fmol"]["Ca"] = 0.0
    elif fault == "diffusion":
        row["diffusivity_m2_per_s"]["Ca"] = -1e-19
    elif fault == "initial_voltage":
        row["initial_voltage_V"] = -0.201
    elif fault == "volume":
        row["volume_pL"] = 0.0
    elif fault == "control":
        raw["experiment"]["mitochondria_controls"][0]["schedule"][0]["availability"] = -1.0
    else:
        raw["execution"]["mitochondrial_capacity"] = 100
    with pytest.raises(ConfigError):
        parse_spec(raw)


@pytest.mark.parametrize(
    "fault", ["padding", "depletion", "heat", "ledger", "ownership", "voltage"]
)
def test_invalid_mitochondrial_states_are_rejected_even_blocked(fault):
    spec, state, p, u = initial()
    if fault == "padding":
        state.mitochondrial_amount_increment_fmol[0, -1] = 1e-4
    elif fault == "depletion":
        state.mitochondrial_amount_increment_fmol[0, 0] = -p.mitochondrial_initial_amount_fmol[0, 0]
    elif fault == "heat":
        state.mitochondrial_dissipated_energy_pJ[0, 0] = -1e-4
    elif fault == "ledger":
        state.mitochondrial_transferred_fmol[0, 0] = 1e-4
    elif fault == "ownership":
        state.mitochondrial_amount_increment_fmol[0, 0] = 1e-4
        state.mitochondrial_transferred_fmol[0, 0] = 1e-4
    else:
        state.mitochondrial_amount_increment_fmol[0, 0] = 1.0
    held = u._replace(mitochondria=np.zeros_like(u.mitochondria))
    assert not model.control_domain_valid(state, held, p, p.active, xp=np)
    with pytest.raises(NumericalError):
        model.check_values(state, spec)


def test_conserved_chemical_bound_includes_initial_mitochondrial_inventory():
    spec, _, _, _ = initial(fixtures.compact_probe())
    ordinary = model.loss_bound(spec)
    raw = spec.to_dict()
    for row in raw["model"]["mitochondria"]["compartments"]:
        row["initial_amount_fmol"] = {k: v * 1e6 for k, v in row["initial_amount_fmol"].items()}
    large = parse_spec(raw)
    assert model.loss_bound(large) > ordinary
    with pytest.raises(ConfigError, match="bound"):
        timeline(large)


def test_checkpoint_keeps_all_45_fields_and_static_charge_anchors(tmp_path):
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
    raw = parent_assembly()
    raw["ionic"] = fixtures.compact_probe(padded=True)
    dt = raw["ionic"]["execution"]["dt"]
    raw["ionic"]["experiment"]["observation_times"] = [i * dt for i in (0, 10, 20, 30, 40)]
    return raw


def test_assembly_preserves_controls_owners_ledgers_and_checkpoint(tmp_path):
    spec = parse_assembly(assembly_definition())
    _, state, p, u = initial(spec.ionic.to_dict())
    levels = np.array([0.0, 1.0])
    held = modulate(u, levels, channel_owners(spec))
    np.testing.assert_array_equal(held.mitochondria, u.mitochondria)
    value = model.readouts(state, held, p, xp=np)
    assert value.valid
    compare(spec.ionic, state, value.derivative, levels=levels)
    combined = assembly.initial_state(spec)
    report = assembly.summary(spec, combined) | dict(
        arm="mitochondria", wall_start=0.0, wall_end=1.0, execute_seconds=0.0
    )
    assert aggregate([report, report])["mitochondria"]["worlds"] == 2 * spec.pool.worlds
    for key in (
        "ip3",
        "calcium",
        "finite_energy",
        "network_transport",
        "mitochondria",
        "channel_transfer_axes",
    ):
        wrong = deepcopy(report)
        wrong.pop(key)
        with pytest.raises(ValueError):
            aggregate([report, wrong])
    write_checkpoint(tmp_path / "assembly", spec, combined, backend="cpu")
    restored, newer, _ = load_checkpoint(tmp_path / "assembly", backend="cpu")
    assert restored == spec
    exact(flatten(newer).values(), flatten(combined).values())


@pytest.mark.parametrize("fault", ["background", "charge", "voltage", "material", "heat", "owner"])
def test_assembly_rejects_changed_mitochondrial_owners_and_ledgers(fault):
    spec = parse_assembly(assembly_definition())
    report = assembly.summary(spec, assembly.initial_state(spec)) | dict(
        arm="mitochondria", wall_start=0.0, wall_end=1.0, execute_seconds=0.0
    )
    value = report["mitochondria"]
    if fault == "background":
        value["fixed_charge_C"][0] += 1e-15
    elif fault == "charge":
        value["charge_C"][0][0] += 1e-15
    elif fault == "voltage":
        value["voltage_V"][0][0] += 0.01
        value["charge_C"][0][0] = value["capacitance_F"][0] * value["voltage_V"][0][0]
    elif fault == "material":
        value["transferred_fmol"][0][0][0] += 1e-4
    elif fault == "heat":
        value["dissipated_energy_pJ"][0][0][0] = -1e-4
    else:
        value["cell_ids"][0] = "unowned"
    with pytest.raises(ValueError):
        aggregate([report])


def test_compiled_two_world_45_field_stage_and_failure_isolation():
    spec, state, p, u = initial()
    changed = transferred_calcium(spec, state, p)
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
    bad = states._replace(
        mitochondrial_amount_increment_fmol=states.mitochondrial_amount_increment_fmol.copy()
    )
    bad.mitochondrial_amount_increment_fmol[1, 0, -1] = 1e-4
    failed, valid = evaluate(bad, controls, p)
    assert np.array_equal(np.asarray(valid), [True, False])
    assert all(np.isnan(v[1]).all() for v in failed)
    exact((v[0] for v in failed), (v[0] for v in got))
    evidence(
        "mitochondria-compiled-stage",
        dict(
            status="passed", inputs=spec.to_dict(), world_checks=checks, invalid_world_isolated=True
        ),
    )


def test_compiled_50us_45_field_trajectory_and_final_snapshot(tmp_path):
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
        scope=(
            "50 us full coupling at unchanged diffusivity; "
            "long organelle relaxation is separate reduced evidence"
        ),
    )
    evidence(
        "mitochondria-trajectory",
        report,
        dict(observed=actual, reference=target, signed_error=actual - target),
    )
    ratio = assert_states(c, actual, target)
    assert np.max(np.abs(result.observations.mitochondrial_transferred_fmol)) > 0
    write_run(tmp_path / "run", result)
    saved = load_snapshot(tmp_path / "run/checkpoint_final")
    assert saved.spec == result.spec and type(saved.checkpoint.layout) is model.LAYOUT_TYPE
    exact(saved.checkpoint.state, result.final.state)
    exact(saved.checkpoint.layout, result.final.layout)
    evidence(
        "mitochondria-trajectory",
        report | dict(status="passed", max_error_over_budget=ratio, complete_final_snapshot=True),
    )
