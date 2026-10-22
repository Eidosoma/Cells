"""Shared multi-ion populations must use one owned cytosol and complete ledgers."""

from copy import deepcopy

import jax
import numpy as np
import pytest

from cells.assembly_cluster.spec import channel_owners
from cells.core.errors import NumericalError
from cells.core.runner import timeline
from cells.core.specs import ConfigError, parse_spec
from cells.ensemble.cluster import aggregate
from cells.models import surface_calcium_hcn as model
from cells.models import surface_calcium_sodium as prior
from cells.models.registry import get_model
from tests.unit import test_surface_calcium as shared
from tests.unit import test_surface_calcium_sodium as sodium
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.tissue import surface_calcium_hcn_fixtures as fixtures
from validation.tissue import surface_calcium_reference as reference
from validation.tissue import surface_calcium_sodium_fixtures as prior_fixtures
from validation.tissue import surface_hcn_fixtures as hcn

BACKEND, EVIDENCE = shared.BACKEND, shared.EVIDENCE
PREFIX = "resolved-calcium-hcn"


@pytest.fixture(scope="module", autouse=True)
def composition_context():
    with pytest.MonkeyPatch.context() as patch:
        for module in (shared, sodium):
            patch.setattr(module, "model", model)
            patch.setattr(module, "fixtures", fixtures)
            patch.setattr(module, "PREFIX", PREFIX)
        yield


initial = shared.initial


def evidence(name, value):
    shared.evidence(PREFIX + "-" + name, value)


def test_identity_catalogs_and_rejections():
    for backend in ("cpu", "gpu"):
        raw = fixtures.definition(backend=backend)
        spec, state, p, _ = initial(raw)
        assert parse_spec(spec.to_dict()) == spec
        assert get_model(spec.model) is model and type(p) is model.LAYOUT_TYPE
        assert spec.to_dict()["model"]["id"] == "resolved_calcium@4"
        assert spec.to_dict()["model"]["ionic"]["id"] == "resolved_tissue@5"
        assert state.channel_gate.shape == (2, 11)
        assert (
            state.channel_transferred.shape == state.channel_dissipated_energy_pJ.shape == (4, 11)
        )
        assert model.STATE_AXES["channel_transferred"] == ["species", "channel_slot"]
        view = model.ionic_layout(state, p, xp=np)
        np.testing.assert_array_equal(view.channel_laws, [0, 1, 0, 1, 1, 2, 2, 3, 4, 5, 0])
        np.testing.assert_array_equal(view.channel_relative_permeability[:, 7], [0.2, 1, 0, 0.05])
        for index, code in ((7, 6), (10, 3)):
            laws = p.channel_laws.copy()
            laws[index] = code
            assert not model.domain_valid(state, p._replace(channel_laws=laws), p.active, xp=np)
    faults = (
        "outer",
        "inner",
        "old_catalog",
        "ratio",
        "missing_route",
        "step",
        "capacity",
        "control",
    )
    for fault in faults:
        raw = fixtures.definition()
        m, x = raw["model"], raw["execution"]
        if fault == "outer":
            m["id"] = "resolved_calcium@3"
        elif fault == "inner":
            m["ionic"]["id"] = "resolved_tissue@4"
        elif fault == "old_catalog":
            m["id"], m["ionic"]["id"] = "resolved_calcium@3", "resolved_tissue@4"
        elif fault == "ratio":
            m["ionic"]["channels"][7]["permeant_ions"][2]["relative_permeability"] = 0.1
        elif fault == "missing_route":
            m["ionic"]["channels"][7]["permeant_ions"].pop()
        elif fault == "step":
            x["dt"] = 5e-6
        elif fault == "capacity":
            x["channel_capacity"] = 9
        else:
            raw["experiment"]["channel_controls"][7]["schedule"][0]["availability"] = -0.1
        with pytest.raises(ConfigError):
            timeline(parse_spec(raw))
    evidence("design", dict(status="passed", rejected=list(faults), inputs=spec.to_dict()))


test_independent_stage_rates_and_accounting = shared.test_independent_stage_rates_and_accounting


def test_free_ion_ownership_and_shared_population_block():
    spec, state, p, control = initial()
    names = [s.id for s in spec.model.stores[0].species]
    cy, er = int(p.er_cytosol[0]), int(p.er_er[0])
    before = model.readouts(state, control, p, xp=np)
    cases = []
    for kind in ("calcium_binding", "calcium_er", "sodium_er"):
        changed = model.STATE_TYPE(*(np.array(v) for v in state))
        if kind == "calcium_binding":
            indices = [names.index(k) for k in ("Ca", "B", "CaB")]
            changed.chemical_amount_increment[0, indices, cy] += 1e-4 * np.array([-1, -1, 1])
        else:
            index = names.index("Ca" if kind == "calcium_er" else "Na")
            changed.chemical_amount_increment[0, index, [cy, er]] += 1e-4 * np.array([-1, 1])
        assert model.domain_valid(changed, p, p.active, xp=np)
        exact(
            model.ensemble_voltage(state, p, spec, 0), model.ensemble_voltage(changed, p, spec, 0)
        )
        after = model.readouts(changed, control, p, xp=np)
        species = spec.model.species_ids.index("Na" if kind == "sodium_er" else "Ca")
        assert (
            before.derivative.channel_transferred[species, 7]
            != after.derivative.channel_transferred[species, 7]
        )
        other_species = [i for i in range(4) if i != species]
        np.testing.assert_allclose(
            after.derivative.channel_transferred[other_species, 7],
            before.derivative.channel_transferred[other_species, 7],
            rtol=3e-10,
            atol=3e-12,
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
        cases.append(dict(kind=kind, max_error_over_budget=ratio, independent_root=proof))
    blocked = control._replace(channel=control.channel.copy())
    blocked.channel[7] = 0.0
    stopped = model.readouts(state, blocked, p, xp=np)
    flux = before.derivative.channel_transferred[:, 7]
    assert np.count_nonzero(flux) == 3
    assert not np.any(stopped.derivative.channel_transferred[:, 7])
    exact(stopped.derivative.channel_gate, before.derivative.channel_gate)
    selected = [i for i in range(11) if i != 7]
    exact(
        stopped.derivative.channel_transferred[:, selected],
        before.derivative.channel_transferred[:, selected],
    )
    expected_chemical = np.zeros_like(state.chemical_amount_increment)
    expected_chemical[0, p.ionic_species, cy] = -flux
    np.testing.assert_allclose(
        before.derivative.chemical_amount_increment - stopped.derivative.chemical_amount_increment,
        expected_chemical,
        atol=3e-14,
        rtol=3e-10,
    )
    for ledger in ("channel_transferred", "channel_dissipated_energy_pJ"):
        corrupt = model.STATE_TYPE(*(np.array(v) for v in state))
        getattr(corrupt, ledger)[2, 7] = 1e-5  # No chloride route in this HCN population.
        assert not model.domain_valid(corrupt, p, p.active, xp=np)
    # Opposing equal-valence species transfers must not hide a material error.
    corrupt = model.STATE_TYPE(*(np.array(v) for v in state))
    corrupt.channel_transferred[[0, 1], 7] = [1e-5, -1e-5]
    with pytest.raises(NumericalError, match="accounting"):
        model.check_values(corrupt, spec)
    evidence(
        "ownership",
        dict(
            status="passed",
            cases=cases,
            selected_population=7,
            all_three_routes_blocked=True,
            unchanged_intrinsic_gates=True,
        ),
    )


def test_species_route_dissipation_cannot_decrease():
    spec, state, _, _ = initial()
    history = model.STATE_TYPE(*(np.stack((v, v)) for v in state))
    # Both rows pass absolute balance tolerance and summed heat is unchanged.
    # The per-route time check must still detect the 1e-11 pJ decrease.
    history.channel_dissipated_energy_pJ[0, 0, 7] = 1e-11
    history.channel_dissipated_energy_pJ[1, 1, 7] = 1e-11
    for i in (0, 1):
        model.check_values(model.STATE_TYPE(*(v[i] for v in history)), spec)
    with pytest.raises(NumericalError, match="dissipation decreased"):
        model.check_values(history, spec)
    evidence(
        "route-heat", dict(status="passed", equal_total_heat=True, decreasing_route_rejected=True)
    )


def test_previous_sodium_calcium_reduction():
    raw = prior_fixtures.definition()
    old, state, p, control = initial(raw)
    assert get_model(old.model) is prior and type(p) is prior.LAYOUT_TYPE
    raw["model"]["id"] = model.MODEL_ID
    raw["model"]["ionic"] = hcn.convert({"model": raw["model"]["ionic"]})["model"]
    new, newer, q, held = initial(raw)
    first, second = prior.readouts(state, control, p, xp=np), model.readouts(newer, held, q, xp=np)
    for old_values, new_values in ((state, newer), (first.derivative, second.derivative)):
        for name in model.STATE_TYPE._fields:
            previous, current = getattr(old_values, name), getattr(new_values, name)
            if name in ("channel_transferred", "channel_dissipated_energy_pJ"):
                expected = np.zeros_like(current)
                expected[p.channel_species, np.arange(len(p.channel_species))] = previous
                np.testing.assert_array_equal(current, expected)
            else:
                np.testing.assert_array_equal(current, previous)
    exact(jax.tree.leaves(first.field), jax.tree.leaves(second.field))
    assert parse_spec(old.to_dict()) == old and parse_spec(new.to_dict()) == new
    evidence(
        "legacy",
        dict(status="passed", reindexed_initial_rates="bitwise", old_catalog_preserved=True),
    )


def test_assembly_controls_shared_populations():
    spec = shared.parse_assembly(fixtures.assembly_definition())
    _, state, p, control = initial(spec.ionic.to_dict())
    owners = channel_owners(spec)
    np.testing.assert_array_equal(owners, [0, 0, 1, 1, 0, 0, 1, 0, 0, 1, 0])
    levels = np.array([0.0, 1.0])
    held = control._replace(channel=control.channel * levels[owners])
    before, after = (model.readouts(state, c, p, xp=np) for c in (control, held))
    assert np.count_nonzero(before.derivative.channel_transferred[:, 7]) == 3
    assert not np.any(after.derivative.channel_transferred[:, owners == 0])
    np.testing.assert_array_equal(
        after.derivative.channel_transferred[:, owners == 1],
        before.derivative.channel_transferred[:, owners == 1],
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
    evidence(
        "assembly-owner-control",
        dict(
            status="passed",
            channel_owner_indices=owners.tolist(),
            max_error_over_budget=ratio,
            independent_root=proof,
        ),
    )


def assert_multi_ion_report(spec, state, report):
    shared.assert_owned_assembly_readouts(spec, state, report)
    ids = list(spec.ionic.model.species_ids)
    n = len(spec.ionic.model.channels)
    assert report["channel_transfer_axes"] == ["world", "species", "channel"]
    assert report["channel_species_ids"] == ids
    np.testing.assert_array_equal(
        report["channel_transferred_fmol"], state.ionic.channel_transferred[..., :n]
    )
    matrix = np.zeros((len(ids), n))
    for i, population in enumerate(spec.ionic.model.channels):
        for route in population.permeant_ions:
            matrix[ids.index(route.species_id), i] = route.relative_permeability
    np.testing.assert_array_equal(report["channel_relative_permeability"], matrix)
    row = report | dict(arm="tissue", wall_start=0.0, wall_end=1.0)
    result = aggregate([row, row])["tissue"]
    np.testing.assert_allclose(
        result["channel_transferred_fmol_sum_by_owner"],
        2 * np.sum(state.ionic.channel_transferred[..., :n], axis=0),
        rtol=2e-15,
        atol=0,
    )
    for key in ("channel_transfer_axes", "channel_species_ids", "channel_relative_permeability"):
        missing = deepcopy(row)
        missing.pop(key)
        with pytest.raises(ValueError, match="channel"):
            aggregate([row, missing])
    for key in ("channel_species_ids", "channel_relative_permeability", "channel_transferred_fmol"):
        invalid = deepcopy(row)
        invalid[key] = invalid[key][:-1]
        with pytest.raises(ValueError, match="channel"):
            aggregate([invalid])


def test_initial_assembly_report_and_planning():
    sodium.test_initial_assembly_report_and_planning()
    spec = shared.parse_assembly(fixtures.assembly_definition(backend=BACKEND))
    state = shared.assembly.initial_state(spec)
    report = shared.assembly.summary(spec, state) | dict(execute_seconds=0.0)
    assert_multi_ion_report(spec, state, report)


test_compiled_smoke_reference_and_checkpoint = sodium.test_compiled_smoke_reference_and_checkpoint
