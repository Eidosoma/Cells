"""Shared CaV populations, owned free-calcium accounting and assembly controls."""

import jax
import numpy as np
import pytest

from cells.assembly_cluster.spec import channel_owners
from cells.core.specs import ConfigError, parse_spec
from cells.core.surface_calcium_spec import ionic_spec
from cells.io import load_snapshot, write_run
from cells.models import surface_calcium_cav as model
from cells.models import surface_calcium_kv1 as prior
from cells.models import surface_cav as ionic_model
from cells.models.registry import get_model
from cells.processes import cav_channels as channels
from cells.processes import kv1_channels
from cells.processes.electrochemistry import CHARGE_PER_FMOL
from tests.unit import test_surface_calcium as shared
from tests.unit import test_surface_calcium_hcn as hcn
from tests.unit import test_surface_calcium_sodium as sodium
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.tissue import surface_calcium_cav_fixtures as fixtures
from validation.tissue import surface_calcium_kv1_fixtures as prior_fixtures
from validation.tissue import surface_calcium_reference as reference
from validation.tissue import surface_kinetic_reference as ionic_reference

BACKEND, EVIDENCE = shared.BACKEND, shared.EVIDENCE
PREFIX = "resolved-calcium-cav"


@pytest.fixture(scope="module", autouse=True)
def composition_context():
    with pytest.MonkeyPatch.context() as patch:
        for module in (shared, hcn, sodium):
            patch.setattr(module, "model", model)
            patch.setattr(module, "fixtures", fixtures)
            patch.setattr(module, "PREFIX", PREFIX)
        yield


initial = shared.initial
assert_multi_ion_report = hcn.assert_multi_ion_report
test_independent_stage_rates_and_accounting = shared.test_independent_stage_rates_and_accounting
test_free_ion_ownership_and_shared_population_block = (
    hcn.test_free_ion_ownership_and_shared_population_block
)
test_species_route_dissipation_cannot_decrease = hcn.test_species_route_dissipation_cannot_decrease
test_initial_assembly_report_and_planning = hcn.test_initial_assembly_report_and_planning


def evidence(name, value, arrays=None):
    shared.evidence(PREFIX + "-" + name, value, arrays)


def test_identity_catalogs_and_rejections():
    for backend in ("cpu", "gpu"):
        spec, state, p, _ = initial(fixtures.definition(backend=backend))
        assert spec == parse_spec(spec.to_dict())
        assert get_model(spec.model) is model and type(p) is model.LAYOUT_TYPE
        assert spec.to_dict()["model"]["id"] == "resolved_calcium@6"
        assert spec.to_dict()["model"]["ionic"]["id"] == "resolved_tissue@7"
        assert state.channel_gate.shape == (2, 23)
        assert (
            state.channel_transferred.shape == state.channel_dissipated_energy_pJ.shape == (4, 23)
        )
        np.testing.assert_array_equal(
            p.channel_laws, [0, 1, 0, 1, 1, 2, 2, 3, 4, 5, *range(6, 18), 0]
        )
        np.testing.assert_array_equal(
            p.channel_relative_permeability[:, 15:22], np.tile([[0], [0], [0], [1]], (1, 7))
        )
        for index, code in ((15, 18), (22, 11)):
            invalid = p.channel_laws.copy()
            invalid[index] = code
            assert not model.domain_valid(state, p._replace(channel_laws=invalid), p.active, xp=np)
    rejected = []
    for fault in ("outer", "inner", "old_catalog", "species", "ratio", "capacity", "step"):
        raw = fixtures.definition()
        m, x = raw["model"], raw["execution"]
        if fault in ("outer", "old_catalog"):
            m["id"] = "resolved_calcium@5"
        if fault in ("inner", "old_catalog"):
            m["ionic"]["id"] = "resolved_tissue@6"
        if fault == "species":
            m["ionic"]["channels"][15]["permeant_ions"][0]["species_id"] = "Na"
        elif fault == "ratio":
            m["ionic"]["channels"][15]["permeant_ions"][0]["relative_permeability"] = 0.5
        elif fault == "capacity":
            x["channel_capacity"] = 21
        elif fault == "step":
            x["dt"] = 2.5e-6
        with pytest.raises(ConfigError):
            shared.timeline(parse_spec(raw))
        rejected.append(fault)
    evidence("design", dict(status="passed", rejected=rejected, inputs=spec.to_dict()))

    # The finer full-history grid must respect its explicit storage allowance.
    raw = fixtures.definition()
    raw["execution"]["dt"] = 0.3125e-6
    shared.timeline(parse_spec(raw))
    raw["execution"]["max_trace_bytes"] = 2**31
    with pytest.raises(ConfigError, match="trace working storage"):
        shared.timeline(parse_spec(raw))
    for budget in (0, 2**53, 4.0 * 2**30, True):
        raw["execution"]["max_trace_bytes"] = budget
        with pytest.raises(ConfigError):
            parse_spec(raw)


def test_previous_kv1_reduction():
    old, state, p, control = initial(prior_fixtures.definition())
    shared.timeline(old)  # Earlier Kv1 identity still accepts its 2.5-us grid.
    raw = old.to_dict()
    raw["model"]["id"], raw["model"]["ionic"]["id"] = "resolved_calcium@6", "resolved_tissue@7"
    new, newer, q, held = initial(raw)
    assert get_model(old.model) is prior and type(p) is prior.LAYOUT_TYPE
    first, second = prior.readouts(state, control, p, xp=np), model.readouts(newer, held, q, xp=np)
    exact(state, newer)
    exact(first.derivative, second.derivative)
    exact(jax.tree.leaves(first.field), jax.tree.leaves(second.field))
    assert parse_spec(new.to_dict()) == new
    for process in (np,):
        voltage = np.linspace(-0.12, 0.06, 61)
        for code in range(11):
            codes = np.full(voltage.shape, code, np.int64)
            exact(
                channels.kinetics(voltage, codes, xp=process),
                kv1_channels.kinetics(voltage, codes, xp=process),
            )
    evidence(
        "legacy",
        dict(status="passed", old_state_rates_fields="bitwise", old_catalog_preserved=True),
    )


def test_standalone_shared_catalog():
    spec = ionic_spec(parse_spec(fixtures.definition()))
    assert parse_spec(spec.to_dict()) == spec and get_model(spec.model) is ionic_model
    state, p = ionic_model.initial_values(spec)
    controls = shared.control_values(spec, [0.0])
    held = type(controls)(*(v[0] for v in controls))
    actual = ionic_model.readouts(state, held, p, xp=np)
    c = ionic_reference.bind(spec.to_dict())
    expected, _, proof = ionic_reference.evaluate(c, ionic_reference.initial(c), 0.0)
    ratio = assert_states(
        c,
        ionic_reference.flatten(c, actual.derivative._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    assert actual.valid and type(p) is ionic_model.LAYOUT_TYPE
    shared.timeline(spec)
    oversized = spec.to_dict()
    oversized["execution"]["dt"] = 2.5e-6
    with pytest.raises(ConfigError, match="1.25 us"):
        shared.timeline(parse_spec(oversized))
    evidence(
        "standalone-stage",
        dict(
            status="passed",
            inputs=spec.to_dict(),
            max_error_over_budget=ratio,
            independent_root=proof,
        ),
    )


def test_compiled_smoke_reference_and_checkpoint(tmp_path):
    raw = fixtures.definition(backend=BACKEND)
    raw["experiment"].update(end_time=50e-6, observation_times=[0.0, 25e-6, 50e-6])
    value = shared.run(parse_spec(raw))
    assert all(v.device.platform == BACKEND for v in value.final.state)
    c = reference.bind(value.spec.to_dict())
    expected = reference.integrate(
        value.spec.to_dict(), rtol=1e-13, state_atol=1e-16, charge_atol=5e-32
    )
    actual, target = reference.flatten(c, vars(value.observations)), np.asarray(expected["state"])
    report = dict(
        status="running",
        inputs=value.spec.to_dict(),
        diagnostics=value.diagnostics,
        independent_reference=expected,
        scope="50-us trajectory and checkpoint round trip; full qualification pending",
    )
    evidence("smoke", report, dict(observed=actual, reference=target, signed_error=actual - target))
    write_run(tmp_path / "smoke", value)
    try:
        report["max_error_over_budget"] = assert_states(c, actual, target)
        loaded = load_snapshot(tmp_path / "smoke/checkpoint_final")
        exact(loaded.checkpoint.state, value.final.state)
        assert loaded.spec == value.spec and type(loaded.checkpoint.layout) is model.LAYOUT_TYPE
        summary = model.summarize(value.history, value.diagnostics, value.spec)
        assert summary["model"] == model.MODEL_ID
        assert summary["channel_laws"] == {
            ch.id: ch.kinetic_law for ch in value.spec.model.channels
        }
    except BaseException:
        evidence("smoke", report | dict(status="failed"))
        raise
    evidence("smoke", report | dict(status="passed", checkpoint="bitwise complete state"))


def test_assembly_controls_all_cav_owners():
    spec = shared.parse_assembly(fixtures.assembly_definition())
    _, state, p, control = initial(spec.ionic.to_dict())
    owners = channel_owners(spec)
    assert set(owners[15:22]) == {0, 1}
    rows = []
    for stopped_owner in (0, 1):
        levels = np.ones(2)
        levels[stopped_owner] = 0.0
        held = control._replace(channel=control.channel * levels[owners])
        before, after = (model.readouts(state, v, p, xp=np) for v in (control, held))
        assert np.count_nonzero(before.derivative.channel_transferred[3, 15:22]) == 7
        assert not np.any(after.derivative.channel_transferred[:, owners == stopped_owner])
        exact(
            after.derivative.channel_transferred[:, owners != stopped_owner],
            before.derivative.channel_transferred[:, owners != stopped_owner],
        )
        exact(after.derivative.channel_gate, before.derivative.channel_gate)
        c = reference.bind(spec.ionic.to_dict())
        expected, _, proof = reference.evaluate(c, reference.initial(c), 0.0, channel_levels=levels)
        ratio = assert_states(
            c,
            reference.flatten(c, after.derivative._asdict()),
            expected,
            atol=3e-12,
            charge_atol=3e-23,
            rtol=3e-10,
        )
        rows.append(
            dict(stopped_owner=stopped_owner, max_error_over_budget=ratio, independent_root=proof)
        )
    evidence(
        "assembly-owner-control",
        dict(status="passed", cases=rows, channel_owner_indices=owners.tolist()),
    )


def test_cav_free_calcium_owner_and_divalent_transfer():
    spec, state, p, control = initial()
    names = [s.id for s in spec.model.stores[0].species]
    cy = int(p.er_cytosol[0])
    before = model.readouts(state, control, p, xp=np)
    changed = model.STATE_TYPE(*(np.array(v) for v in state))
    changed.chemical_amount_increment[0, [names.index(k) for k in ("Ca", "B", "CaB")], cy] += (
        1e-4 * np.array([-1, -1, 1])
    )
    assert model.domain_valid(changed, p, p.active, xp=np)
    exact(model.ensemble_voltage(state, p, spec, 0), model.ensemble_voltage(changed, p, spec, 0))
    after = model.readouts(changed, control, p, xp=np)
    assert (
        before.derivative.channel_transferred[3, 15] != after.derivative.channel_transferred[3, 15]
    )
    c = reference.bind(spec.to_dict())
    expected, _, proof = reference.evaluate(c, reference.flatten(c, changed._asdict()), 0.0)
    ratio = assert_states(
        c,
        reference.flatten(c, after.derivative._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    blocked = control._replace(channel=control.channel.copy())
    blocked.channel[15] = 0.0
    stopped = model.readouts(state, blocked, p, xp=np)
    flux = before.derivative.channel_transferred[3, 15]
    assert flux != 0 and not np.any(stopped.derivative.channel_transferred[:, 15])
    exact(stopped.derivative.channel_gate, before.derivative.channel_gate)
    patch = int(p.channel_membranes[15])
    owner, outside = int(p.membrane_cell[patch]), int(p.membrane_outside[patch])
    inside_delta = before.derivative.amount_increment - stopped.derivative.amount_increment
    outside_delta = (
        before.derivative.extracellular_amount_increment
        - stopped.derivative.extracellular_amount_increment
    )
    expected_inside, expected_outside = np.zeros_like(inside_delta), np.zeros_like(outside_delta)
    expected_inside[3, owner], expected_outside[3, outside] = -flux, flux
    np.testing.assert_allclose(inside_delta, expected_inside, rtol=3e-10, atol=3e-14)
    np.testing.assert_allclose(outside_delta, expected_outside, rtol=3e-10, atol=3e-14)
    np.testing.assert_allclose(
        CHARGE_PER_FMOL * np.sum(p.valence * inside_delta, axis=0)[owner],
        -2 * CHARGE_PER_FMOL * flux,
        rtol=3e-10,
        atol=3e-23,
    )
    expected_chemical = np.zeros_like(state.chemical_amount_increment)
    expected_chemical[owner, names.index("Ca"), cy] = -flux
    np.testing.assert_allclose(
        before.derivative.chemical_amount_increment - stopped.derivative.chemical_amount_increment,
        expected_chemical,
        rtol=3e-10,
        atol=3e-14,
    )
    evidence(
        "calcium-owner",
        dict(
            status="passed",
            max_error_over_budget=ratio,
            independent_root=proof,
            blocked_population=15,
            valence=2,
            outward_fmol_per_s=float(flux),
            unchanged_plasma_voltage_after_binding=True,
            same_free_chemical_owner=True,
        ),
    )


def test_shared_cav1p2_replaces_one_explicit_patch_route():
    """Moving one population's representation must not duplicate its current."""
    raw = prior_fixtures.definition()
    old, state, p, control = initial(raw)
    old_values = prior.readouts(state, control, p, xp=np)
    raw["model"]["id"], raw["model"]["ionic"]["id"] = "resolved_calcium@6", "resolved_tissue@7"
    source = raw["model"]["calcium_channels"][0]
    population = dict(
        id="shared_cav1p2_replacement",
        membrane_id=source["membrane_id"],
        kinetic_law=source["kinetic_law"],
        max_permeability_m_per_s=source["max_permeability_m_per_s"],
        abundance=source["abundance"],
        initial_gate=[source["initial_gate"][key] for key in ("m", "h")],
        permeant_ions=[dict(species_id="Ca", relative_permeability=1.0)],
    )
    source["abundance"] = 0.0
    raw["model"]["ionic"]["channels"].append(population)
    raw["execution"]["channel_capacity"] += 1
    raw["experiment"]["channel_controls"].append(
        dict(
            channel_id=population["id"],
            schedule=raw["experiment"]["calcium_channel_controls"][0]["schedule"],
        )
    )
    new, newer, q, held = initial(raw)
    actual = model.readouts(newer, held, q, xp=np)
    for name in (
        "amount_increment",
        "extracellular_amount_increment",
        "chemical_amount_increment",
        "reaction_extent",
        "er_passive_transferred",
        "pump_cycles",
        "plasma_pump_cycles",
        "plasma_exchange_cycles",
    ):
        np.testing.assert_allclose(
            getattr(actual.derivative, name),
            getattr(old_values.derivative, name),
            rtol=3e-10,
            atol=3e-12,
        )
    np.testing.assert_allclose(
        actual.derivative.channel_transferred[3, 15],
        old_values.derivative.calcium_channel_transferred[0],
        rtol=3e-15,
        atol=0,
    )
    assert actual.derivative.calcium_channel_transferred[0] == 0
    np.testing.assert_allclose(
        actual.derivative.channel_gate[:, 15],
        old_values.derivative.calcium_gate[:, 0],
        rtol=3e-15,
        atol=3e-15,
    )
    for name in (
        "membrane_voltage_rate_V_s",
        "chemical_energy_rate_pJ_s",
        "capacitor_energy_rate_pJ_s",
    ):
        np.testing.assert_allclose(
            getattr(actual.field, name), getattr(old_values.field, name), rtol=3e-10, atol=3e-12
        )
    evidence(
        "cav1p2-route-reduction",
        dict(
            status="passed",
            old_inputs=old.to_dict(),
            new_inputs=new.to_dict(),
            disabled_dedicated_population=True,
            same_physical_rates=True,
            separate_ledgers=True,
        ),
    )
