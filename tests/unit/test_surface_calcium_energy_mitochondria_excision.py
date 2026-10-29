"""Cuts preserve disjoint chemical/fuel/organelle owners and paired internal charge."""

import hashlib
import json
import os
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec
from cells.core.calcium_energy_mitochondria_tissue_excision import (
    CONTROL_GROUPS,
    GATES,
    capture_source,
    decode_source,
    physical,
)
from cells.core.errors import NumericalError
from cells.core.excision import excise
from cells.core.grid import EventGrid
from cells.core.runner import validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import Checkpoint, initialise
from cells.core.surface_calcium_energy_mitochondria_excision_spec import base_spec
from cells.core.windows import WindowPolicy, iter_windows, run_windowed
from cells.excision_io import CALCIUM_ENERGY_MITOCHONDRIA_KIND, load_excision, write_excision
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import surface_calcium_energy_mitochondria as parent
from cells.models import surface_calcium_energy_mitochondria_excision as model
from cells.models import surface_calcium_energy_transport as network_parent
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_step
from cells.processes.electrochemistry import CHARGE_PER_FMOL
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.tissue import calcium_energy_mitochondria_excision_fixtures as fixtures
from validation.tissue import calcium_energy_mitochondria_excision_reference as reference

TRAJECTORY_REFINEMENT = 32


def trajectory_definition():
    raw = fixtures.definition(padded=True)
    raw["execution"].update(
        dt=fixtures.DT / TRAJECTORY_REFINEMENT, max_steps=10000, max_trace_bytes=2**32
    )
    return raw


@lru_cache(maxsize=12)
def prefix(arm):
    return reference.integrate(fixtures.definition(arm), end_time=fixtures.CUT_TIME)


@lru_cache(maxsize=24)
def prepared(arm="open", padded=True):
    raw = fixtures.definition(arm, padded=padded)
    spec = parse_spec(raw)
    c = reference.bind(raw)
    state, layout = parent.initial_values(spec)
    for key, value in reference.unpack(c, prefix(arm)["state"][-1]).items():
        getattr(state, key)[tuple(slice(0, n) for n in value.shape)] = value
    time = fixtures.CUT_TIME
    point = Checkpoint(
        state, layout, time, EventGrid(spec).exact_index(time), event_index(spec, time)
    )
    parent.check_values(state, spec)
    return spec, point


def compare_transition(spec, point, cut):
    c = reference.bind(spec.to_dict())
    expected = reference.excise(
        spec.to_dict(),
        reference.flatten(c, point.state._asdict()),
        cut.report["removed_cell_ids"],
        point.time,
    )
    if cut.spec is None:
        assert expected["raw"] is None
        return dict(terminal=True)
    c = reference.bind(cut.spec.to_dict())
    state = reference.flatten(c, cut.checkpoint.state._asdict())
    np.testing.assert_array_equal(state, expected["state"])
    controls = control_values(cut.spec, [point.time])
    u = type(controls)(*(v[0] for v in controls))
    implementation = get_model(cut.spec.model)
    actual = implementation.rhs(
        cut.checkpoint.state, u, cut.checkpoint.layout, cut.checkpoint.layout.active, xp=np
    )
    target, phi, _ = reference.evaluate(c, state, point.time)
    ratio = assert_states(
        c, reference.flatten(c, actual._asdict()), target, atol=3e-12, charge_atol=3e-23, rtol=3e-10
    )
    p = cut.checkpoint.layout
    values = physical(cut.spec, cut.checkpoint)
    got_phi = np.r_[
        values["potential"][: len(cut.spec.model.cells)],
        values["potential"][len(p.active) : len(p.active) + len(cut.spec.model.extracellular)],
    ]
    np.testing.assert_allclose(got_phi, phi, atol=3e-12, rtol=3e-10)
    if cut.report["changed"]:
        for key in ("removed_chemical_energy_pJ", "unresolved_cut_energy_pJ"):
            np.testing.assert_allclose(
                cut.report[key], expected["audit"][key], atol=2e-10, rtol=3e-9
            )
        np.testing.assert_allclose(
            np.asarray(cut.report["removed_chemical_amount_fmol"]).sum(axis=0),
            expected["audit"]["removed_chemical_amount_fmol"],
            atol=2e-11,
            rtol=3e-12,
        )
        np.testing.assert_allclose(
            np.asarray(cut.report["removed_moieties_fmol"]).sum(axis=0),
            expected["audit"]["removed_moiety_fmol"],
            atol=2e-11,
            rtol=3e-12,
        )
        np.testing.assert_allclose(
            sum(cut.report["removed_er_capacitor_energy_pJ"]),
            expected["audit"]["removed_er_capacitor_energy_pJ"],
            atol=2e-13,
            rtol=3e-10,
        )
        for report, audit in (
            ("removed_fuel_amount_fmol", "removed_fuel_amount_fmol"),
            ("removed_fuel_moieties_fmol", "removed_fuel_moiety_fmol"),
        ):
            np.testing.assert_allclose(
                np.asarray(cut.report[report]).sum(axis=-1),
                expected["audit"][audit],
                atol=2e-11,
                rtol=3e-12,
            )
        np.testing.assert_allclose(
            sum(cut.report["removed_fuel_energy_pJ"]),
            expected["audit"]["removed_fuel_free_energy_pJ"],
            atol=2e-10,
            rtol=3e-12,
        )
        assert cut.report["removed_fuel_pool_ids"] == sorted(expected["audit"]["removed_pool_ids"])
        assert (
            cut.report["removed_regeneration_port_ids"]
            == expected["audit"]["removed_regeneration_ids"]
        )
        assert (
            cut.report["removed_network_transporter_ids"]
            == expected["audit"]["removed_network_route_ids"]
        )
        assert (
            cut.report["retained_network_transporter_ids"]
            == expected["audit"]["retained_network_route_ids"]
        )
        for name in network_parent.EXTRA_AXES:
            np.testing.assert_array_equal(
                cut.report["archived_retained_state"][name],
                expected["audit"]["archived_retained_network_state"][name],
            )
            np.testing.assert_array_equal(
                cut.report["archived_removed_state"][name],
                expected["audit"]["archived_removed_network_state"][name],
            )
        for name in parent.EXTRA_AXES:
            for ownership in ("retained", "removed"):
                np.testing.assert_array_equal(
                    cut.report["archived_" + ownership + "_state"][name],
                    expected["audit"]["archived_" + ownership + "_mitochondrial_state"][name],
                )
        assert (
            cut.report["removed_mitochondrion_ids"]
            == expected["audit"]["removed_mitochondrial_ids"]
        )
        np.testing.assert_allclose(
            np.asarray(cut.report["removed_mitochondrial_amount_fmol"]).sum(axis=-1),
            expected["audit"]["removed_mitochondrial_amount_fmol"],
            atol=2e-11,
            rtol=3e-12,
        )
        for key in (
            "removed_mitochondrial_chemical_energy_pJ",
            "removed_mitochondrial_capacitor_energy_pJ",
        ):
            np.testing.assert_allclose(
                sum(cut.report[key]), expected["audit"][key], atol=2e-10, rtol=3e-12
            )
        np.testing.assert_allclose(
            values["chemical_background_C"],
            expected["audit"]["after"]["chemical_fixed_charge_C"],
            atol=5e-23,
            rtol=4e-15,
        )
    return dict(
        max_error_over_budget=ratio,
        independent=json.loads(json.dumps(expected["audit"], default=lambda v: v.tolist())),
    )


@pytest.mark.parametrize("catalog", ["compact", "full"])
@pytest.mark.parametrize(
    "arm",
    ["open", "blocked", "reordered", "empty", "single-survivor", "supply_off", "no_regeneration"],
)
def test_initial_chemical_owner_cut_and_complete_device_checkpoint(catalog, arm):
    spec = parse_spec(fixtures.definition(arm, catalog=catalog, padded=True))
    point = initialise(spec)
    source = capture_source(spec, point)
    restored_spec, restored = decode_source(source)
    assert restored_spec == spec
    exact(restored.state, point.state)
    exact(restored.layout, point.layout)
    before = physical(spec, point)
    cut = excise(spec, point, fixtures.cut_plan(arm)[0]["removed_cell_ids"])
    checked = compare_transition(spec, point, cut)
    assert get_model(cut.spec.model) is model
    assert type(cut.checkpoint.layout) is parent.LAYOUT_TYPE
    assert len(cut.checkpoint.state) == 45
    assert cut.spec == parse_spec(cut.spec.to_dict())
    retained = [
        i for i, v in enumerate(spec.model.cells) if v.id in cut.report["retained_cell_ids"]
    ]
    after = physical(cut.spec, cut.checkpoint)
    np.testing.assert_array_equal(after["chemical_amount"], before["chemical_amount"][retained])
    np.testing.assert_array_equal(after["charge"], before["charge"][retained])
    np.testing.assert_array_equal(after["er_voltage"], before["er_voltage"][retained])
    assert set(cut.report["archived_retained_state"]) == set(model.STATE_AXES)
    assert len(cut.report["local_ledger_fields"]) == 42
    for name in cut.report["local_ledger_fields"]:
        assert not np.any(getattr(cut.checkpoint.state, name))
    assert capture_source(spec, point) == source
    evidence(
        "calcium-energy-mitochondria-excision-initial-" + catalog + "-" + arm,
        dict(
            status="passed",
            source=spec.to_dict(),
            after=cut.spec.to_dict(),
            report=cut.report,
            comparison=checked,
            scope="Initial-state owner and snapshot checks; evolved comparisons are separate",
        ),
    )


def test_charged_finite_exterior_cut_rejects_without_neutralization():
    spec = parse_spec(fixtures.definition("charged"))
    point = initialise(spec)
    source = capture_source(spec, point)
    with pytest.raises((ConfigError, NumericalError)):
        excise(spec, point, fixtures.cut_plan("charged")[0]["removed_cell_ids"])
    assert capture_source(spec, point) == source


def test_every_shared_law_survives_in_a_full_catalog_owner_panel():
    # Two neutral owners permit complementary selections. Testing just cell_1
    # removal would compare only 37 retained laws, even with a 56-law source.
    spec = parse_spec(fixtures.definition("single-survivor", catalog="full", padded=True))
    point = initialise(spec)
    covered, panels = set(), []
    for removed in (["cell_0"], ["cell_1"]):
        cut = excise(spec, point, removed)
        checked = compare_transition(spec, point, cut)
        laws = {v.kinetic_law for v in cut.spec.model.channels}
        covered.update(laws)
        panels.append(dict(removed=removed, retained_laws=sorted(laws), comparison=checked))
    assert covered == {v.kinetic_law for v in spec.model.channels}
    assert len(covered) == 56
    evidence(
        "calcium-energy-mitochondria-excision-all-law-owner-panels",
        dict(
            status="passed",
            source=spec.to_dict(),
            panels=panels,
            retained_laws=sorted(covered),
            scope="Complementary owner/rate panels; not a full-catalog coupled trajectory",
        ),
    )


@pytest.mark.parametrize("selection", [["cell_1"], [], ["cell_0", "cell_1", "cell_2"]])
def test_calcium_cut_artifact_family_and_complete_roundtrip(tmp_path, selection):
    spec = parse_spec(fixtures.definition())
    point = initialise(spec)
    cut = excise(spec, point, selection)
    path = write_excision(tmp_path / "cut", cut)
    loaded = load_excision(path)
    assert loaded.spec == cut.spec and loaded.report == cut.report
    assert (
        json.loads((path / "manifest.json").read_text())["kind"] == CALCIUM_ENERGY_MITOCHONDRIA_KIND
    )
    exact(loaded.source_checkpoint.state, point.state)
    exact(loaded.source_checkpoint.layout, point.layout)
    if cut.checkpoint is not None:
        exact(loaded.checkpoint.state, cut.checkpoint.state)
        exact(loaded.checkpoint.layout, cut.checkpoint.layout)
    else:
        assert cut.report["terminal"]


@pytest.mark.parametrize(
    "arm",
    [
        "open",
        "blocked",
        "reordered",
        "empty",
        "no-op",
        "single-survivor",
        "supply_off",
        "no_regeneration",
        "network_blocked",
        "zero_routes",
        "zero_drive",
        "mitochondria_blocked",
        "zero_diffusion",
        "mitochondria_reverse",
    ],
)
@pytest.mark.parametrize("padded", [False, True])
def test_evolved_cut_preserves_all_chemical_owners_three_gates_and_rates(arm, padded):
    spec, point = prepared(arm, padded)
    original = capture_source(spec, point)
    cut = excise(spec, point, fixtures.cut_plan(arm)[0]["removed_cell_ids"])
    checked = compare_transition(spec, point, cut)
    assert capture_source(spec, point) == original
    assert cut.spec == parse_spec(cut.spec.to_dict())
    assert {v.time for v in spec.experiment.changes} <= {
        v.time for v in cut.spec.experiment.changes
    }
    assert cut.checkpoint.time == point.time
    created = initialise(cut.spec)
    if arm == "no-op":
        assert cut.checkpoint is point and cut.spec == spec
    else:
        exact(created.state, cut.checkpoint.state)
        assert created.time == point.time
        assert all(
            not np.any(getattr(cut.checkpoint.state, k)) for k in model.STATE_AXES if k not in GATES
        )
        assert (
            len(cut.report["archived_retained_state"])
            == len(cut.report["archived_removed_state"])
            == 45
        )
    assert np.max(np.abs(point.state.chemical_amount_increment)) > 1e-8
    assert np.max(np.abs(point.state.er_passive_transferred)) > 0
    evidence(
        "calcium-energy-mitochondria-excision-evolved-" + arm + "-" + str(padded),
        dict(
            status="passed",
            source=spec.to_dict(),
            after=cut.spec.to_dict(),
            report=cut.report,
            comparison=checked,
        ),
    )


def test_free_cytosol_rebase_does_not_duplicate_bound_or_er_charge():
    spec, point = prepared()
    before = physical(spec, point)
    old_free_anchor = np.array([c.initial_amount_fmol for c in spec.model.cells]).T
    external_only = old_free_anchor + point.state.amount_increment[:, : len(spec.model.cells)]
    assert np.max(np.abs(before["free_amount"] - external_only)) > 1e-8
    cut = excise(spec, point, ["cell_1"])
    old = np.asarray(cut.report["ionic_reference_fixed_charge_before_fmol"])
    new = np.asarray(cut.report["ionic_reference_fixed_charge_after_fmol"])
    assert np.max(np.abs(new - old)) > 1e-8
    error = np.abs(cut.report["chemical_background_roundoff_C"])
    assert np.all(error <= np.asarray(cut.report["chemical_background_roundoff_bound_C"]))
    for name in (
        "reaction_extent",
        "er_passive_transferred",
        "er_pump_transferred",
        "er_release_transferred",
    ):
        assert np.max(np.abs(getattr(point.state, name))) > 0


def test_live_fuel_and_internal_work_are_preserved_by_their_actual_owners():
    spec, point = prepared()
    before = physical(spec, point)
    cut = excise(spec, point, ["cell_1"])
    after = physical(cut.spec, cut.checkpoint)
    keep = [i for i, c in enumerate(spec.model.cells) if c.id != "cell_1"]
    np.testing.assert_array_equal(after["fuel_amount"], before["fuel_amount"][:, keep])
    np.testing.assert_array_equal(after["fuel_moieties"], before["fuel_moieties"][:, keep])
    np.testing.assert_array_equal(after["fuel_energy_pJ"], before["fuel_energy_pJ"][keep])
    old = {p.id: p for p in spec.model.energy_pools}
    cells = {c.id: i for i, c in enumerate(spec.model.cells)}
    for pool in cut.spec.model.energy_pools:
        assert pool.delta_g0_J_per_mol == old[pool.id].delta_g0_J_per_mol
        assert pool.law == old[pool.id].law
        np.testing.assert_array_equal(
            pool.initial_amount_fmol, before["fuel_amount"][:, cells[pool.cell_id]]
        )
    for name in (
        "energy_amount_increment_fmol",
        "regeneration_cycles_fmol",
        "regeneration_supplied_work_pJ",
        "regeneration_dissipated_energy_pJ",
    ):
        assert np.max(np.abs(getattr(point.state, name))) > 1e-16
        assert not np.any(getattr(cut.checkpoint.state, name))
        assert name in cut.report["archived_removed_state"]
    removed = cells["cell_1"]
    # The neutral removed cell still consumes internal fuel through its ER pump.
    assert np.max(np.abs(point.state.energy_amount_increment_fmol[:, removed])) > 1e-12
    assert point.state.er_metabolic_work_pJ[removed] > 0
    np.testing.assert_array_equal(after["charge"], before["charge"][keep])
    assert cut.report["removed_regeneration_port_ids"] == ["supply_cell_1"]
    assert cut.report["removed_fuel_pool_ids"] == ["fuel_cell_1"]
    evidence(
        "calcium-energy-mitochondria-excision-fuel-owners", dict(status="passed", report=cut.report)
    )


@pytest.mark.parametrize("padded", [False, True])
def test_internal_charge_rebase_preserves_both_physical_backgrounds(padded):
    spec, point = prepared(padded=padded)
    before = physical(spec, point)
    cut = excise(spec, point, ["cell_1"])
    after = physical(cut.spec, cut.checkpoint)
    kept = [0, 2]
    delta_charge = CHARGE_PER_FMOL * np.einsum(
        "s,sc->c", spec.model.valence, point.state.mitochondrial_amount_increment_fmol[:, kept]
    )
    assert np.max(np.abs(delta_charge)) > 1e-25
    coordinate_shift = (
        after["chemical_reference_background_C"] - before["chemical_reference_background_C"][kept]
    )
    counter_shift = (
        after["mitochondrial_initial_countercharge_C"]
        - before["mitochondrial_initial_countercharge_C"][kept]
    )
    selector = cut.checkpoint.layout.cytosol_selector[:, :2]
    bound = np.asarray(cut.report["chemical_background_roundoff_bound_C"])
    assert np.all(np.abs(coordinate_shift - delta_charge[:, None] * selector) <= bound)
    np.testing.assert_allclose(counter_shift, -delta_charge, atol=5e-23, rtol=4e-15)
    assert np.all(np.abs(coordinate_shift + counter_shift[:, None] * selector) <= bound)
    np.testing.assert_array_equal(after["charge"], before["charge"][kept])
    np.testing.assert_array_equal(
        after["mitochondrial_countercharge_C"], -after["mitochondrial_charge_C"]
    )
    assert np.all(
        np.abs(after["chemical_background_C"] - before["chemical_background_C"][kept]) <= bound
    )
    assert np.all(
        np.abs(cut.report["mitochondrial_fixed_background_roundoff_C"])
        <= cut.report["mitochondrial_fixed_background_roundoff_bound_C"]
    )
    for old, new in zip(
        (spec.model.mitochondria[i] for i in kept), cut.spec.model.mitochondria, strict=True
    ):
        assert (
            replace(
                new,
                initial_amount_fmol=old.initial_amount_fmol,
                initial_voltage_V=old.initial_voltage_V,
            )
            == old
        )
    assert not cut.report["mitochondrial_direct_plasma_charge"]
    assert not cut.report["mitochondrial_atp_source"]
    checked = compare_transition(spec, point, cut)
    evidence(
        "calcium-energy-mitochondria-excision-countercharge-" + str(padded),
        dict(
            status="passed",
            report=cut.report,
            comparison=checked,
            charge_shift_C=delta_charge.tolist(),
        ),
    )


def test_removed_organelle_nonzero_histories_and_future_clock_are_preserved(tmp_path):
    spec, point = prepared()
    cut = excise(spec, point, ["cell_1"])
    for name in parent.EXTRA_AXES:
        old = np.asarray(getattr(point.state, name))
        assert np.max(np.abs(old[:, 1])) > 0
        np.testing.assert_array_equal(cut.report["archived_removed_state"][name], old[:, [1]])
        np.testing.assert_array_equal(cut.report["archived_retained_state"][name], old[:, [0, 2]])
        assert not np.any(getattr(cut.checkpoint.state, name))
    assert 109.7e-6 in {v.time for v in cut.spec.experiment.changes}
    restored = load_excision(write_excision(tmp_path / "organelle-cut", cut))
    exact(restored.source_checkpoint.state, point.state)
    assert restored.report == cut.report
    evidence(
        "calcium-energy-mitochondria-excision-removed-history",
        dict(status="passed", report=cut.report),
    )


@pytest.mark.parametrize("arm", ["mitochondria_blocked", "zero_diffusion"])
def test_absent_organelle_flux_retains_actual_inventory_and_zero_history(arm):
    spec, point = prepared(arm)
    cut = excise(spec, point, ["cell_1"])
    for name in parent.EXTRA_AXES:
        assert not np.any(getattr(point.state, name))
        assert not np.any(cut.report["archived_removed_state"][name])
    old = physical(spec, point)
    np.testing.assert_array_equal(
        old["mitochondrial_amount"], point.layout.mitochondrial_initial_amount_fmol[:, :3]
    )
    compare_transition(spec, point, cut)


@pytest.mark.parametrize("padded", [False, True])
def test_empty_network_has_explicit_zero_route_axes_and_complete_cut(padded):
    raw = fixtures.definition(padded=padded)
    raw["model"]["network_transport"]["routes"] = []
    raw["experiment"]["network_transport_controls"] = []
    raw["execution"]["network_transport_capacity"] = int(padded)
    spec = parse_spec(raw)
    point = initialise(spec)
    cut = excise(spec, point, ["cell_1"])
    checked = compare_transition(spec, point, cut)
    assert len(cut.checkpoint.state) == 45
    assert not cut.report["removed_network_transporter_ids"]
    assert not cut.report["retained_network_transporter_ids"]
    for name in network_parent.EXTRA_AXES:
        assert getattr(cut.checkpoint.state, name).shape[-1] == int(padded)
        assert not np.any(getattr(cut.checkpoint.state, name))
    evidence(
        "calcium-energy-mitochondria-excision-empty-routes-" + str(padded),
        dict(status="passed", source=raw, after=cut.spec.to_dict(), comparison=checked),
    )


@pytest.mark.parametrize("arm", ["open", "reordered", "blocked"])
def test_live_network_work_and_route_histories_keep_membrane_owners(arm):
    spec, point = prepared(arm)
    cut = excise(spec, point, ["cell_1"])
    retained_membranes = {v.id for v in cut.spec.model.membranes}
    kept = [
        i
        for i, v in enumerate(spec.model.network_transporters)
        if v.membrane_id in retained_membranes
    ]
    removed = [
        i
        for i, v in enumerate(spec.model.network_transporters)
        if v.membrane_id not in retained_membranes
    ]
    original = {v.id: v for v in spec.model.network_transporters}
    assert tuple(cut.spec.model.network_transporters) == tuple(
        original[v.id] for v in cut.spec.model.network_transporters
    )
    assert cut.report["removed_network_transporter_ids"] == [
        spec.model.network_transporters[i].id for i in removed
    ]
    assert cut.report["retained_network_transporter_ids"] == [
        spec.model.network_transporters[i].id for i in kept
    ]
    for name in network_parent.EXTRA_AXES:
        value = np.asarray(getattr(point.state, name))
        np.testing.assert_array_equal(
            cut.report["archived_retained_state"][name], np.take(value, kept, axis=-1)
        )
        np.testing.assert_array_equal(
            cut.report["archived_removed_state"][name], np.take(value, removed, axis=-1)
        )
        assert not np.any(getattr(cut.checkpoint.state, name))
    if arm != "blocked":
        assert np.any(point.state.network_cycles_fmol)
        assert np.any(point.state.network_supplied_work_pJ)
    np.testing.assert_allclose(
        point.state.network_supplied_work_pJ,
        1e-3 * point.layout.network_supplied_energy_J_mol * point.state.network_cycles_fmol,
        atol=3e-12,
        rtol=0,
    )
    checked = compare_transition(spec, point, cut)
    evidence(
        "calcium-energy-mitochondria-excision-route-histories-" + arm,
        dict(
            status="passed",
            source=spec.to_dict(),
            after=cut.spec.to_dict(),
            report=cut.report,
            comparison=checked,
            scope="External route work and internal finite-ATP pump work remain distinct",
        ),
    )


def test_removed_neutral_transporter_keeps_nonzero_work_and_transfer_history(tmp_path):
    spec, point = prepared("removed_neutral_history")
    source = capture_source(spec, point)
    cut = excise(spec, point, ["cell_1"])
    checked = compare_transition(spec, point, cut)
    for name in network_parent.EXTRA_AXES:
        assert np.any(cut.report["archived_removed_state"][name]), name
    np.testing.assert_allclose(cut.report["removed_net_charge_C"], 0, atol=3e-25, rtol=0)
    assert cut.report["network_work_external"]
    assert cut.report["pump_metabolic_work_internal"]
    assert not cut.report["network_routes_store_material"]
    loaded = load_excision(write_excision(tmp_path / "cut", cut))
    exact(loaded.source_checkpoint.state, point.state)
    exact(loaded.checkpoint.state, cut.checkpoint.state)
    assert capture_source(spec, point) == source
    evidence(
        "calcium-energy-mitochondria-excision-nonzero-removed-route-history",
        dict(status="passed", source=source, report=cut.report, comparison=checked),
    )


def test_valid_live_fuel_below_constructor_range_is_retained_and_explicitly_refused():
    raw = fixtures.definition("supply_off", padded=True)
    volume = {v["id"]: v["volume_pL"] for v in raw["model"]["ionic"]["cells"]}
    for pool in raw["model"]["energy_pools"]:
        pool["initial_amount_fmol"] = {
            name: volume[pool["cell_id"]] * 1e-9 * (1 + 1e-12) for name in ("ATP", "ADP", "Pi")
        }
    spec = parse_spec(raw)
    target = reference.integrate(raw, end_time=fixtures.CUT_TIME)
    c = reference.bind(raw)
    state, layout = parent.initial_values(spec)
    for key, value in reference.unpack(c, target["state"][-1]).items():
        getattr(state, key)[tuple(slice(0, n) for n in value.shape)] = value
    point = Checkpoint(
        state,
        layout,
        fixtures.CUT_TIME,
        EventGrid(spec).exact_index(fixtures.CUT_TIME),
        event_index(spec, fixtures.CUT_TIME),
    )
    parent.check_values(state, spec)
    before = capture_source(spec, point)
    amount = physical(spec, point)["fuel_amount"]
    assert np.all(amount > 0)
    assert np.any(
        amount[0, [0, 2]] / np.array([spec.model.cells[i].volume_pL for i in (0, 2)]) < 1e-9
    )
    with pytest.raises(ConfigError, match="constructor range"):
        excise(spec, point, ["cell_1"])
    assert capture_source(spec, point) == before
    assert excise(spec, point, []).checkpoint is point
    terminal = excise(spec, point, [v.id for v in spec.model.cells])
    assert terminal.spec is None and terminal.report["terminal"]
    evidence(
        "calcium-energy-mitochondria-excision-low-fuel-refusal",
        dict(
            status="passed",
            source=before,
            terminal_report=terminal.report,
            scope="Positive live pools; inherited PMCA/ER anchor range limits runnable cuts",
        ),
    )


@pytest.mark.parametrize(
    "fault",
    [
        "chemical_amount",
        "bound_amount",
        "er_voltage",
        "free_anchor",
        "old_background",
        "calcium_gate",
        "shared_gate",
        "source_layout",
        "missing_history",
        "padding",
        "dt",
        "lost_store_clock",
        "policy",
        "ownership",
        "fuel_amount",
        "fuel_standard",
        "fuel_owner",
        "port_owner",
        "missing_fuel_history",
        "lost_regeneration_clock",
        "network_owner",
        "network_configuration",
        "network_density",
        "network_drive",
        "network_source_layout",
        "missing_network_history",
        "network_padded_history",
        "lost_network_clock",
    ],
)
def test_calcium_cut_refuses_hidden_material_gate_anchor_or_history_changes(fault):
    spec, point = prepared()
    raw = excise(spec, point, ["cell_1"]).spec.to_dict()
    record = raw["model"]["excision"]
    m = raw["model"]["tissue"]
    store = m["stores"][0]["model"]
    if fault == "chemical_amount":
        store["compartments"][1]["initial_amount_fmol"]["Ca"] += 1e-6
    elif fault == "bound_amount":
        names = {v["id"] for v in m["ionic"]["species"]}
        name = next(v["id"] for v in store["species"] if v["id"] not in names)
        store["compartments"][0]["initial_amount_fmol"][name] += 1e-6
    elif fault == "er_voltage":
        store["membrane"]["initial_voltage_V"] += 1e-5
    elif fault == "free_anchor":
        m["ionic"]["cells"][0]["initial_amount_fmol"]["Ca"] += 1e-6
    elif fault == "old_background":
        m["ionic"]["cells"][0]["fixed_charge_equivalent_fmol"] = spec.model.cells[
            0
        ].fixed_charge_equivalent_fmol
    elif fault == "calcium_gate":
        m["calcium_channels"][0]["initial_gate"]["m"] = 0.0
    elif fault == "shared_gate":
        m["ionic"]["channels"][0]["initial_gate"][0] = 0.0
    elif fault == "source_layout":
        record["source"]["checkpoint"]["layout"]["er_initial_voltage"][0] += 1e-5
    elif fault == "missing_history":
        del record["source"]["checkpoint"]["state"]["er_metabolic_work_pJ"]
    elif fault == "padding":
        record["source"]["checkpoint"]["state"]["chemical_amount_increment"][0][0][-1] = 1e-6
    elif fault == "dt":
        raw["execution"]["dt"] /= 2
    elif fault == "lost_store_clock":
        for key, (_, schedule) in CONTROL_GROUPS.items():
            for row in raw["experiment"][key]:
                row[schedule] = [v for v in row[schedule] if v["time"] != 91.7e-6]
    elif fault == "policy":
        record["reference_policy"] = "keep_old_free_anchor"
    elif fault == "fuel_amount":
        m["energy_pools"][0]["initial_amount_fmol"]["ATP"] += 1e-6
    elif fault == "fuel_standard":
        m["energy_pools"][0]["delta_g0_J_per_mol"] += 100.0
    elif fault == "fuel_owner":
        m["energy_pools"][0]["cell_id"] = m["energy_pools"][1]["cell_id"]
    elif fault == "port_owner":
        m["regeneration_ports"][0]["pool_id"] = m["energy_pools"][1]["id"]
    elif fault == "missing_fuel_history":
        del record["source"]["checkpoint"]["state"]["regeneration_supplied_work_pJ"]
    elif fault == "lost_regeneration_clock":
        for key, (_, schedule) in CONTROL_GROUPS.items():
            for row in raw["experiment"][key]:
                row[schedule] = [v for v in row[schedule] if v["time"] != 89.3e-6]
    elif fault == "network_owner":
        route = m["network_transport"]["routes"][0]
        route["membrane_id"] = next(
            v["id"] for v in m["ionic"]["membranes"] if v["id"] != route["membrane_id"]
        )
    elif fault == "network_configuration":
        m["network_transport"]["routes"][0]["configuration"]["max rate"] *= 2
    elif fault == "network_density":
        m["network_transport"]["routes"][0]["density_multiplier"] *= 2
    elif fault == "network_drive":
        route = m["network_transport"]["routes"][0]
        route["configuration"]["standard free energy"] -= 100
        route["drive"]["supplied_energy_J_per_mol"] += 100
    elif fault == "network_source_layout":
        record["source"]["checkpoint"]["layout"]["network_density"][0] *= 2
    elif fault == "missing_network_history":
        del record["source"]["checkpoint"]["state"]["network_supplied_work_pJ"]
    elif fault == "network_padded_history":
        record["source"]["checkpoint"]["state"]["network_cycles_fmol"][-1] = 1e-6
    elif fault == "lost_network_clock":
        removed_routes = {
            v.id
            for v in spec.model.network_transporters
            if v.membrane_id not in {w["id"] for w in m["ionic"]["membranes"]}
        }
        times = {
            v["time"]
            for row in spec.to_dict()["experiment"]["network_transport_controls"]
            if row["transporter_id"] in removed_routes
            for v in row["schedule"]
            if v["time"] > point.time
        }
        assert times
        lost = min(times)
        for key, (_, schedule) in CONTROL_GROUPS.items():
            for row in raw["experiment"][key]:
                row[schedule] = [v for v in row[schedule] if v["time"] != lost]
    else:
        m["stores"][0]["cell_id"] = m["stores"][1]["cell_id"]
    with pytest.raises((ConfigError, NumericalError)):
        parse_spec(raw)


@pytest.mark.parametrize(
    "fault",
    [
        "amount",
        "voltage",
        "owner",
        "volume",
        "area",
        "capacitance",
        "thickness",
        "diffusion",
        "source_countercharge",
        "missing_history",
        "padded_history",
        "lost_clock",
    ],
)
def test_organelle_cut_rejects_changed_physics_owner_countercharge_or_history(fault):
    spec, point = prepared()
    raw = excise(spec, point, ["cell_1"]).spec.to_dict()
    rows = raw["model"]["tissue"]["mitochondria"]["compartments"]
    source = raw["model"]["excision"]["source"]["checkpoint"]
    if fault == "amount":
        rows[0]["initial_amount_fmol"]["K"] += 1e-6
    elif fault == "voltage":
        rows[0]["initial_voltage_V"] += 1e-3
    elif fault == "owner":
        rows[0]["cell_id"] = rows[1]["cell_id"]
    elif fault in ("volume", "area", "capacitance", "thickness"):
        key = {
            "volume": "volume_pL",
            "area": "area_m2",
            "capacitance": "specific_capacitance_F_per_m2",
            "thickness": "membrane_thickness_m",
        }[fault]
        rows[0][key] *= 1.1
    elif fault == "diffusion":
        rows[0]["diffusivity_m2_per_s"]["K"] *= 2
    elif fault == "source_countercharge":
        source["layout"]["mitochondrial_initial_countercharge_C"][0] += 1e-14
    elif fault == "missing_history":
        del source["state"]["mitochondrial_transferred_fmol"]
    elif fault == "padded_history":
        source["state"]["mitochondrial_amount_increment_fmol"][0][-1] = 1e-6
    else:
        lost = 109.7e-6
        assert lost in {v.time for v in spec.experiment.changes}
        for key, (_, schedule) in CONTROL_GROUPS.items():
            for row in raw["experiment"][key]:
                row[schedule] = [v for v in row[schedule] if v["time"] != lost]
    with pytest.raises((ConfigError, NumericalError)):
        parse_spec(raw)


@pytest.mark.parametrize("family", list(CONTROL_GROUPS))
def test_ten_control_families_keep_their_actual_past(family):
    spec, point = prepared()
    raw = excise(spec, point, ["cell_1"]).spec.to_dict()
    _, schedule = CONTROL_GROUPS[family]
    event = raw["experiment"][family][0][schedule][0]
    if family == "store_controls":
        event["release"] = 0.5 if event["release"] != 0.5 else 0.0
    elif family == "plasma_controls":
        event["pump"] = 0.5 if event["pump"] != 0.5 else 0.0
    else:
        event["availability"] = 0.5 if event["availability"] != 0.5 else 0.0
    with pytest.raises(ConfigError, match="history"):
        parse_spec(raw)


@pytest.mark.parametrize("later", [False, True])
def test_sequential_chemical_cuts_preserve_nested_stores_and_clock(later):
    spec, point = prepared("sequential")
    first = excise(spec, point, ["cell_1"])
    evolved = first.checkpoint
    if later:
        time = fixtures.cut_plan("sequential")[1]["time_s"]
        c = reference.bind(first.spec.to_dict())
        target = reference.integrate(first.spec.to_dict(), end_time=time)
        state, layout = model.initial_values(first.spec)
        for key, value in reference.unpack(c, target["state"][-1]).items():
            getattr(state, key)[tuple(slice(0, n) for n in value.shape)] = value
        evolved = Checkpoint(
            state,
            layout,
            time,
            EventGrid(first.spec).exact_index(time),
            event_index(first.spec, time),
        )
    second = excise(first.spec, evolved, ["cell_0"])
    checked = compare_transition(first.spec, evolved, second)
    assert second.checkpoint.time == evolved.time
    assert json.loads(second.spec.model.excision_json)["source"] == capture_source(
        first.spec, evolved
    )
    if not later:
        combined = excise(spec, point, ["cell_0", "cell_1"])
        assert base_spec(second.spec).model == base_spec(combined.spec).model
        exact(second.checkpoint.state, combined.checkpoint.state)
    evidence(
        "calcium-energy-mitochondria-excision-sequential-" + str(later),
        dict(
            status="passed",
            after=second.spec.to_dict(),
            report=second.report,
            comparison=checked,
        ),
    )


def test_evolved_calcium_archive_cli_and_initial_gate_validation(tmp_path, capsys):
    from cells.__main__ import main

    spec, point = prepared()
    write_snapshot(tmp_path / "before", spec, point)
    assert (
        main(
            [
                "excise",
                str(tmp_path / "before"),
                "--remove",
                "cell_1",
                "--output",
                str(tmp_path / "cut"),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "complete"
    cut = load_excision(tmp_path / "cut")
    exact(cut.source_checkpoint.state, point.state)
    created = initialise(cut.spec)
    state = created.state._replace(calcium_gate=np.array(created.state.calcium_gate))
    state.calcium_gate[0, 0] += 1e-5
    with pytest.raises(ConfigError, match="initial state"):
        validate_checkpoint(cut.spec, replace(created, state=state))


def test_zero_remaining_calcium_epoch_and_batch_windows():
    from cells.core.batch_windows import run_batch_windowed

    spec, point = prepared()
    cut = excise(spec, point, ["cell_1"])
    raw = cut.spec.to_dict()
    raw["experiment"].update(end_time=point.time, observation_times=[point.time])
    for family, (_, schedule) in CONTROL_GROUPS.items():
        for row in raw["experiment"][family]:
            row[schedule] = [v for v in row[schedule] if v["time"] <= point.time]
    finished = parse_spec(raw)
    scalar = run_windowed(finished)
    assert scalar.start_time == scalar.final.time == point.time
    assert scalar.resources["executed_steps"] == 0
    exact(scalar.final.state, cut.checkpoint.state)
    batch = BatchSpec((WorldSpec(3, finished), WorldSpec(79, finished)), 2, 2048, 2**30)
    result = run_batch_windowed(batch)
    for world in result.worlds.values():
        assert world.start_time == world.final.time == point.time
        exact(world.final.state, cut.checkpoint.state)


def test_offline_calcium_cut_one_four_sixteen_gpu_placement():
    from cells.ensemble.families import parse_definition, population
    from cells.ensemble.plan import plan
    from tests.unit.test_hcn_extra_catalog_planning import verify
    from tests.unit.test_integrated_ensemble import experiment

    spec, point = prepared()
    cut = excise(spec, point, ["cell_1"])
    raw = experiment("ionic", backend="gpu", worlds=16, width=1)
    raw["execution"]["max_output_bytes"] = 4 * 1024**3
    after = cut.spec.to_dict()
    after["execution"]["backend"] = "gpu"
    raw["arms"][0]["definition"].update(simulation=after, window_steps=128)
    # Organelle/route histories exceed this fixture's unchanged storage budget
    # at 128 steps. Retain that refusal; 64-step windows still plan every step,
    # observation and world without raising the allowed resident storage.
    with pytest.raises(ConfigError, match="Estimated window working storage"):
        plan(raw, 1)
    raw["arms"][0]["definition"]["window_steps"] = 64
    plans = verify(raw)
    identities = []
    for task in plans["local"]["tasks"]:
        definition = parse_definition(task["definition"])
        assert definition.simulation.to_dict()["model"]["excision"] == after["model"]["excision"]
        group = population(definition)
        identities.extend(range(group.world_id_start, group.world_id_start + group.worlds))
    assert sorted(identities) == list(range(16))
    evidence(
        "calcium-energy-mitochondria-excision-offline-plans",
        dict(
            status="passed",
            inputs=raw,
            plans=plans,
            refused_window_steps=128,
            scope="Offline placement only; no GPU execution",
        ),
    )


@pytest.mark.parametrize("phase", ["before", "after"])
def test_host_calcium_transient_refines_without_changing_rates_or_tolerances(phase):
    if phase == "before":
        spec = parse_spec(fixtures.definition())
        point = initialise(spec)
        point = replace(
            point,
            state=type(point.state)(*(np.asarray(v) for v in point.state)),
            layout=type(point.layout)(*(np.asarray(v) for v in point.layout)),
        )
    else:
        source, old = prepared(padded=False)
        cut = excise(source, old, ["cell_1"])
        spec, point = cut.spec, cut.checkpoint
    c = reference.bind(spec.to_dict())
    times = [point.time, point.time + fixtures.DT, point.time + 2 * fixtures.DT]
    expected = reference.integrate(
        spec.to_dict(), start_time=point.time, end_time=times[-1], observation_times=times
    )
    impl, p = get_model(spec.model), point.layout
    table = control_values(spec, [point.time])
    control = type(table)(*(v[0] for v in table))

    def rhs(y, u, p, active):
        assert impl.control_domain_valid(y, u, p, active, xp=np)
        return impl.rhs(y, u, p, active, xp=np)

    arrays, errors = {}, []
    for refinement in (8, 16, TRAJECTORY_REFINEMENT):
        state = point.state
        saved = [reference.flatten(c, state._asdict())]
        for i in range(2 * refinement):
            state = rk4_step(rhs, state, fixtures.DT / refinement, control, p, p.active)
            if (i + 1) % refinement == 0:
                saved.append(reference.flatten(c, state._asdict()))
        actual = np.stack(saved)
        impl.check_values(state, spec)
        budgets = reference.flatten(
            c, {k: np.full(v, 3e-25 if k.endswith("_C") else 2e-11) for k, v in c["shapes"].items()}
        )
        errors.append(
            float(
                np.max(
                    np.abs(actual - expected["state"])
                    / (budgets + 3e-9 * np.abs(expected["state"]))
                )
            )
        )
        arrays[str(refinement)] = actual
    evidence(
        "calcium-energy-mitochondria-excision-transient-" + phase,
        dict(
            status="measured",
            input=spec.to_dict(),
            times=times,
            refinements=[8, 16, TRAJECTORY_REFINEMENT],
            max_error_over_budget=errors,
        ),
        dict(reference=expected["state"], **arrays),
    )
    assert errors[-1] <= 1
    assert errors[-1] < max(errors[0] / 8, 0.01)


def merge_windows(records):
    """Concatenate accepted public results; no integration step is introduced."""
    from cells.core.runner import RunResult
    from cells.core.windows import merge_diagnostics

    first = records[0]
    times = np.concatenate([r.times if i == 0 else r.times[1:] for i, r in enumerate(records)])
    history = type(first.history)(
        *(
            np.concatenate([v if i == 0 else v[1:] for i, v in enumerate(values)], axis=0)
            for values in zip(*(r.history for r in records), strict=True)
        )
    )
    observations = type(first.observations)(
        *(
            np.concatenate([getattr(r.observations, k) for r in records], axis=0)
            for k in vars(first.observations)
        )
    )
    diagnostics, timings = {}, {}
    for r in records:
        merge_diagnostics(diagnostics, r.diagnostics)
        for k, v in r.timings.items():
            timings[k] = timings.get(k, 0.0) + v
    return RunResult(
        first.spec,
        records[-1].final,
        first.start_step,
        times,
        history,
        observations,
        timings,
        diagnostics,
    )


def bounded_scalar_result(spec, window_steps, checkpoint=None, stop_time=None):
    """Keep the exact accepted grid; only partition resident execution storage."""
    records = []
    for result in iter_windows(spec, WindowPolicy(window_steps), checkpoint):
        records.append(result)
        if stop_time is not None:
            assert result.final.time <= stop_time
            if result.final.time == stop_time:
                break
    assert records
    if stop_time is not None:
        assert records[-1].final.time == stop_time
    return merge_windows(records)


def _phase_digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _save_compiled_phase(root, record, arrays):
    np.savez(root / "comparison.npz", **arrays)
    record = record | dict(
        files_sha256={
            str(p.relative_to(root)): _phase_digest(p)
            for p in sorted(root.rglob("*"))
            if p.is_file()
        }
    )
    (root / "metadata.json").write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")


def _load_compiled_phase(root):
    record = json.loads((root / "metadata.json").read_text())
    assert record["status"] == "passed"
    actual = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
    assert actual == {*record["files_sha256"], "metadata.json"}
    for relative, digest in record["files_sha256"].items():
        assert not Path(relative).is_absolute() and ".." not in Path(relative).parts
        assert _phase_digest(root / relative) == digest
    return record


def _compiled_phase_output(name, tmp_path_factory):
    destination = os.environ.get("CELLS_COMPONENT_EVIDENCE")
    if destination:
        root = Path(destination) / "cpu" / name
        root.mkdir(parents=True, exist_ok=False)
        return root
    return tmp_path_factory.mktemp(name)


@pytest.fixture(scope="module")
def compiled_calcium_energy_mitochondria_prefix(tmp_path_factory):
    supplied = os.environ.get("CELLS_CALCIUM_ENERGY_MITOCHONDRIA_EXCISION_PREFIX")
    if supplied:
        root = Path(supplied)
        _load_compiled_phase(root)
        return root
    root = _compiled_phase_output("calcium-energy-mitochondria-excision-prefix", tmp_path_factory)
    raw = trajectory_definition()
    original = parse_spec(raw)
    cut_steps = EventGrid(original).exact_index(fixtures.CUT_TIME)
    prefix_width = max(width for width in range(1, 257) if cut_steps % width == 0)
    before = bounded_scalar_result(original, prefix_width, stop_time=fixtures.CUT_TIME)
    point = before.checkpoint_at(fixtures.CUT_TIME)
    c = reference.bind(raw)
    expected = reference.integrate(raw, end_time=point.time)
    actual = reference.flatten(c, vars(before.observations))
    ratio = assert_states(c, actual, expected["state"])
    cut = excise(before.spec, point, ["cell_1"])
    loaded = load_excision(write_excision(root / "cut", cut))
    assert loaded.spec == cut.spec
    exact(loaded.source_checkpoint.state, point.state)
    exact(loaded.source_checkpoint.layout, point.layout)
    exact(loaded.checkpoint.state, cut.checkpoint.state)
    exact(loaded.checkpoint.layout, cut.checkpoint.layout)
    record = dict(
        status="passed",
        source=raw,
        after=cut.spec.to_dict(),
        report=cut.report,
        prefix_diagnostics=before.diagnostics,
        prefix_timings=before.timings,
        prefix_max_error_over_budget=ratio,
    )
    _save_compiled_phase(root, record, dict(actual=actual, reference=expected["state"]))
    evidence("calcium-energy-mitochondria-excision-prefix", record)
    # The qualified driver uses a fresh process per phase. Clear compiler caches
    # here as well for a developer selecting all three tests in one invocation.
    import jax

    jax.clear_caches()
    return root


def test_compiled_calcium_energy_mitochondria_prefix_and_durable_cut(
    compiled_calcium_energy_mitochondria_prefix,
):
    data = _load_compiled_phase(compiled_calcium_energy_mitochondria_prefix)
    cut = load_excision(compiled_calcium_energy_mitochondria_prefix / "cut")
    assert data["after"] == cut.spec.to_dict()
    assert cut.source_checkpoint.time == cut.checkpoint.time == fixtures.CUT_TIME


@pytest.fixture(scope="module")
def compiled_calcium_energy_mitochondria_scalar(
    compiled_calcium_energy_mitochondria_prefix, tmp_path_factory
):
    supplied = os.environ.get("CELLS_CALCIUM_ENERGY_MITOCHONDRIA_EXCISION_SCALAR")
    if supplied:
        root = Path(supplied)
        data = _load_compiled_phase(root)
        assert data["prefix_metadata_sha256"] == _phase_digest(
            compiled_calcium_energy_mitochondria_prefix / "metadata.json"
        )
        return root
    root = _compiled_phase_output("calcium-energy-mitochondria-excision-scalar", tmp_path_factory)
    cut = load_excision(compiled_calcium_energy_mitochondria_prefix / "cut")
    result = bounded_scalar_result(cut.spec, 256)
    assert result.times[0] == cut.checkpoint.time
    assert result.start_step == cut.checkpoint.step_index
    c = reference.bind(cut.spec.to_dict())
    expected = reference.integrate(cut.spec.to_dict())
    actual = reference.flatten(c, vars(result.observations))
    ratio = assert_states(c, actual, expected["state"])
    write_run(root / "run", result)
    loaded = load_snapshot(root / "run/checkpoint_final")
    exact(loaded.checkpoint.state, result.final.state)
    exact(loaded.checkpoint.layout, result.final.layout)
    record = dict(
        status="passed",
        after=cut.spec.to_dict(),
        diagnostics=result.diagnostics,
        timings=result.timings,
        max_error_over_budget=ratio,
        prefix_metadata_sha256=_phase_digest(
            compiled_calcium_energy_mitochondria_prefix / "metadata.json"
        ),
        complete_final_snapshot=True,
    )
    _save_compiled_phase(root, record, dict(actual=actual, reference=expected["state"]))
    evidence("calcium-energy-mitochondria-excision-scalar", record)
    import jax

    jax.clear_caches()
    return root


def test_compiled_calcium_energy_mitochondria_scalar_continuation_and_snapshot(
    compiled_calcium_energy_mitochondria_scalar,
):
    data = _load_compiled_phase(compiled_calcium_energy_mitochondria_scalar)
    loaded = load_snapshot(compiled_calcium_energy_mitochondria_scalar / "run/checkpoint_final")
    assert data["after"] == loaded.spec.to_dict()
    assert loaded.checkpoint.time == fixtures.END_TIME


def test_compiled_calcium_energy_mitochondria_windowed_fresh_process_restart(
    compiled_calcium_energy_mitochondria_prefix, compiled_calcium_energy_mitochondria_scalar
):
    prefix = _load_compiled_phase(compiled_calcium_energy_mitochondria_prefix)
    scalar = _load_compiled_phase(compiled_calcium_energy_mitochondria_scalar)
    cut = load_excision(compiled_calcium_energy_mitochondria_prefix / "cut")
    final = load_snapshot(compiled_calcium_energy_mitochondria_scalar / "run/checkpoint_final")
    assert final.spec == cut.spec
    c = reference.bind(cut.spec.to_dict())
    samples = []

    def collect(window):
        samples.append(reference.flatten(c, vars(window.observations)))

    windowed = run_windowed(cut.spec, WindowPolicy(128), cut.checkpoint, sink=collect)
    exact(windowed.final.state, final.checkpoint.state)
    exact(windowed.final.layout, final.checkpoint.layout)
    assert windowed.final.step_index == final.checkpoint.step_index
    actual = np.concatenate(samples)
    with np.load(
        compiled_calcium_energy_mitochondria_scalar / "comparison.npz", allow_pickle=False
    ) as arrays:
        np.testing.assert_array_equal(actual, arrays["actual"])
        expected = arrays["reference"]
    ratio = assert_states(c, actual, expected)
    evidence(
        "calcium-energy-mitochondria-excision-trajectory",
        dict(
            status="passed",
            source=prefix["source"],
            after=cut.spec.to_dict(),
            report=cut.report,
            prefix_diagnostics=prefix["prefix_diagnostics"],
            diagnostics=scalar["diagnostics"],
            timings=scalar["timings"],
            window_timings=windowed.timings,
            prefix_max_error_over_budget=prefix["prefix_max_error_over_budget"],
            max_error_over_budget=ratio,
            complete_final_snapshot=True,
            phase_metadata_sha256=dict(
                prefix=_phase_digest(compiled_calcium_energy_mitochondria_prefix / "metadata.json"),
                scalar=_phase_digest(compiled_calcium_energy_mitochondria_scalar / "metadata.json"),
            ),
            phase_process_scope=(
                "Fresh processes sharing one frozen source tree and checksummed state"
            ),
        ),
        dict(actual=actual, reference=expected),
    )


def test_compiled_calcium_energy_mitochondria_two_world_batch_absolute_epoch_and_resume():
    from cells.core.batch_windows import run_batch_windowed

    _, point = prepared()
    spec = parse_spec(trajectory_definition())
    point = replace(point, step_index=EventGrid(spec).exact_index(point.time))
    cut = excise(spec, point, ["cell_1"])
    batch = BatchSpec((WorldSpec(3, cut.spec), WorldSpec(79, cut.spec)), 2, 10000, 2**30)
    c = reference.bind(cut.spec.to_dict())
    expected = reference.integrate(cut.spec.to_dict())
    samples = {3: [], 79: []}

    def collect(round):
        for identity, world in round.worlds.items():
            samples[identity].append(reference.flatten(c, vars(world.observations)))

    result = run_batch_windowed(batch, WindowPolicy(128), sink=collect)
    ratios = {}
    for identity, world in result.worlds.items():
        assert world.start_time == point.time and world.start_step == point.step_index
        assert world.final.step_index == len(EventGrid(cut.spec)) - 1
        ratios[str(identity)] = assert_states(
            c, np.concatenate(samples[identity]), expected["state"]
        )
    resumed = run_batch_windowed(batch, WindowPolicy(128), result.checkpoints)
    for identity, world in resumed.worlds.items():
        exact(world.final.state, result.worlds[identity].final.state)
    evidence(
        "calcium-energy-mitochondria-excision-batch",
        dict(
            status="passed",
            world_ids=[3, 79],
            window_steps=128,
            source=spec.to_dict(),
            after=cut.spec.to_dict(),
            window_timings=result.timings,
            max_error_over_budget=ratios,
        ),
    )


def test_compiled_full_catalog_retains_static_law_dispatch_and_world_domains():
    import jax
    import jax.numpy as jnp

    spec = parse_spec(fixtures.definition(catalog="full", padded=True))
    cut = excise(spec, initialise(spec), ["cell_1"])
    y, p = cut.checkpoint.state, cut.checkpoint.layout
    table = control_values(cut.spec, [0.0])
    u = type(table)(*(v[0] for v in table))
    invalid = y._replace(channel_gate=np.array(y.channel_gate))
    invalid.channel_gate[0, 0] = 1.1
    invalid_ca = y._replace(calcium_gate=np.array(y.calcium_gate))
    invalid_ca.calcium_gate[0, 0] = 1.1
    invalid_fuel = y._replace(energy_amount_increment_fmol=np.array(y.energy_amount_increment_fmol))
    invalid_fuel.energy_amount_increment_fmol[0, 0] = -2 * p.energy_initial_amount_fmol[0, 0]
    invalid_transport = y._replace(network_transferred_fmol=np.array(y.network_transferred_fmol))
    invalid_transport.network_transferred_fmol[0, 0] += 1e-6
    invalid_mito = y._replace(
        mitochondrial_transferred_fmol=np.array(y.mitochondrial_transferred_fmol)
    )
    invalid_mito.mitochondrial_transferred_fmol[0, 0] += 1e-6
    worlds = type(y)(
        *(
            jnp.asarray(np.stack([a, b, d, f, t, m]))
            for a, b, d, f, t, m in zip(
                y, invalid, invalid_ca, invalid_fuel, invalid_transport, invalid_mito, strict=True
            )
        )
    )

    def evaluate(state, control, layout):
        valid = model.control_domain_valid(state, control, layout, layout.active)
        return model.rhs(state, control, layout, layout.active), valid

    actual, valid = jax.device_get(
        jax.jit(jax.vmap(evaluate, in_axes=(0, None, None)))(worlds, u, p)
    )
    np.testing.assert_array_equal(valid, [True, False, False, False, False, False])
    c = reference.bind(cut.spec.to_dict())
    expected, _, _ = reference.evaluate(c, reference.flatten(c, y._asdict()), 0.0)
    ratio = assert_states(
        c,
        reference.flatten(c, {k: v[0] for k, v in actual._asdict().items()}),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    evidence(
        "calcium-energy-mitochondria-excision-compiled-catalog",
        dict(
            status="passed",
            source=spec.to_dict(),
            after=cut.spec.to_dict(),
            max_error_over_budget=ratio,
            domain_valid=valid.tolist(),
            scope="Compiled stage/domain comparison; not a full-catalog long trajectory",
        ),
    )
