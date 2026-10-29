"""Complete water/repair dual schedules and original physical accounting.

Stage and short-history component checks carry no full-trajectory claim.
"""

import ast
import importlib
import json
import os
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.core import joint_water_profile_barrier_preparation as preparation
from cells.core import tissue_profile_composition_preparation as profiles
from cells.core import tissue_profile_preparation as direct
from cells.core.errors import NumericalError
from cells.core.grid import EventGrid
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import initialise
from cells.io import load_snapshot, write_snapshot
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_step
from cells.processes import betse_tissue_profiles as native
from tests.owned_joint_water_hcn_helpers import changed as changed_complete_owner
from validation.transport import joint_water_profile_barrier_interventions_fixtures as fixtures
from validation.transport import joint_water_profile_barrier_interventions_reference as reference

FAMILIES = [pytest.param("water", id="water_owner"), pytest.param("repair", id="repair_owner")]


def modules(family):
    stem = (
        "surface_calcium_energy_water"
        + ("_repair" if family == "repair" else "")
        + "_profile_barrier_interventions"
    )
    return importlib.import_module("cells.core." + stem + "_spec"), importlib.import_module(
        "cells.models." + stem
    )


def evidence(name, record, arrays=None):
    if path := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(path) / "joint-water-profile-barriers"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (name + ".json")).write_text(
            json.dumps(record, indent=2, allow_nan=False, default=lambda v: np.asarray(v).tolist())
            + "\n"
        )
        if arrays is not None:
            np.savez_compressed(folder / (name + ".npz"), **arrays)


@lru_cache
def prepared(family="water", case="joint", permuted=False, padded=True):
    values = fixtures.inputs(family, case, permuted=permuted, padded=padded)
    args = deepcopy(values["profile_request"])
    geometry = args["geometry"].copy()
    layout = geometry.pop("layout")
    layout["cell_centres_m"] = np.asarray(layout["cell_centres_m"])
    parent = profiles.prepare(
        args["definition"],
        profiles.Geometry(native.Layout(**layout), **geometry),
        direct._decode_profile(args["default"]),
        [direct._decode_profile(r) for r in args["profiles"]],
        ion_enabled=args["ion_enabled"],
        enabled=args["enabled"],
        is_ecm=args["is_ecm"],
    )
    request = fixtures.preparation_request(
        values, dict(definition=parent.definition, provenance=parent.provenance)
    )
    combined = preparation.prepare(request)
    return values, request, combined


@lru_cache
def initialized(family="water", case="joint", permuted=False, padded=True):
    values, request, combined = prepared(family, case, permuted, padded)
    raw = fixtures.definition(values, combined)
    schema, model = modules(family)
    spec = schema.parse(raw)
    state, p = model.initial_values(spec)
    return raw, spec, state, p, request


def control(schema, spec, time):
    table = control_values(schema.owner_spec(spec), [time])
    return type(table)(*(v[0] for v in table))


def copied(state):
    return type(state)(*(np.array(v, copy=True) for v in state))


def manufactured(state, p, spec):
    return changed_complete_owner(spec, state, p)


def budgets(c, expected):
    return reference.flatten(
        c, {k: np.full(s, 3e-23 if k.endswith("_C") else 3e-12) for k, s in c["shapes"].items()}
    ) + 3e-10 * np.abs(expected)


@pytest.mark.parametrize("family", FAMILIES)
def test_complete_parent_identity_initialization_and_artifact(family):
    schema, model = modules(family)
    raw, spec, state, p, request = initialized(family)
    ordinary = schema.owner_spec(spec)
    assert ordinary.to_dict()["model"]["id"] == fixtures.PARENT_IDS[family]
    assert type(ordinary.model) is type(spec.model).__bases__[0]
    assert len(state) == (44 if family == "water" else 49)
    assert type(model.parent_layout(p)) is model.base.LAYOUT_TYPE
    actual, layout = model.base.initial_values(ordinary)
    for a, b in zip(model.parent_state(state), actual, strict=True):
        np.testing.assert_array_equal(a, b)
    for key in layout._fields:
        np.testing.assert_array_equal(getattr(p, key), getattr(layout, key))
    assert len(spec.model.channels) == 63 and set(p.channel_laws[p.channel_active]) == set(
        range(56)
    )
    assert schema.to_dict(spec) == raw and schema.replay(schema.artifact(spec)) == spec
    assert len(spec.model.stores) == len(spec.model.cells)
    model.check_values(state, spec)
    evidence(
        "complete-" + family,
        dict(
            definition=raw,
            preparation_request=request,
            parent_model_id=fixtures.PARENT_IDS[family],
            all_parent_state_and_layout_exact=True,
            state_fields=list(state._fields),
            current_volume_and_fuel_scope=True,
        ),
    )


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("case", fixtures.CASES)
@pytest.mark.parametrize("changed", [False, True])
def test_full_stage_actual_volume_stores_fuel_damage_and_both_coefficients(family, case, changed):
    schema, model = modules(family)
    raw, spec, initial, p, _ = initialized(family, case, permuted=changed)
    c = reference.bind(raw)
    clocks = {0.0, spec.experiment.end_time, *(v.time for v in spec.experiment.changes)}
    for event in (
        *spec.model.membrane_interventions,
        *((spec.model.barrier_intervention,) if spec.model.barrier_intervention else ()),
    ):
        clocks.update((event.on_s, (event.on_s + event.off_s) / 2, event.off_s))
    reports = []
    arrays = {}
    for n, t in enumerate(sorted(clocks)):
        state = (manufactured(initial, p, spec) if changed else copied(initial))._replace(
            phase_clock_s=np.asarray([t])
        )
        assert model.domain_valid(state, p, p.active, xp=np)
        target, phi, proof = reference.evaluate(c, reference.flatten(c, state._asdict()), t)
        u = control(schema, spec, t)
        actual = reference.flatten(c, model.rhs(state, u, p, p.active, xp=np)._asdict())
        budget = budgets(c, target)
        ratio = float(np.max(np.abs(actual - target) / budget, initial=0))
        field = model.field_values(state, u, p, xp=np)
        actual_phi = np.r_[
            field.potential_V[: p.active.size][p.active],
            field.potential_V[p.active.size :][p.outside_active],
        ]
        signal = model.signal_values(state, p, xp=np)
        np.testing.assert_allclose(
            signal.membrane.scheduled,
            proof["membrane_coefficients"]["scheduled_m2_s"],
            rtol=5e-14,
            atol=2e-30,
        )
        faces = [
            [proof["barrier_coefficients"]["face_m2_s"][sid][row.id] for row in spec.model.faces]
            for sid in spec.model.species_ids
        ]
        np.testing.assert_allclose(
            signal.barrier.face_diffusivity[:, p.face_active], faces, rtol=5e-14, atol=2e-26
        )
        reports.append(
            dict(
                time_s=t,
                error_over_budget=ratio,
                independent=proof,
                production_energy_residual_pJ_s=float(field.energy_balance_pJ_s),
            )
        )
        arrays.update(
            {
                f"{n}-{key}": v
                for key, v in dict(
                    actual=actual,
                    reference=target,
                    budget=budget,
                    state=reference.flatten(c, state._asdict()),
                    potential=actual_phi,
                    reference_potential=phi,
                ).items()
            }
        )
        evidence(
            f"stages-{family}-{case}-{changed}",
            dict(
                definition=raw,
                changed_state=changed,
                complete_fields=len(state),
                all_held_control_and_pulse_clocks=True,
                comparisons=reports,
            ),
            arrays,
        )
        assert ratio <= 1 and field.converged
        assert (
            abs(field.energy_balance_pJ_s) <= 1e-10
            and abs(proof["physical_energy_balance_pJ_s"]) <= 1e-10
        )
        assert (
            proof["max_charge_residual_C"] <= 3e-25
            and proof["max_component_current_residual_A"] <= 1e-23
        )
        np.testing.assert_allclose(actual_phi, phi, rtol=3e-10, atol=3e-13)


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("case", ["INIT", "disabled"])
def test_disabled_matches_exact_full_parent_bitwise(family, case):
    schema, model = modules(family)
    _, spec, state, p, _ = initialized(family, case)
    state = manufactured(state, p, spec)._replace(phase_clock_s=np.asarray([4.5e-6]))
    u = control(schema, spec, 4.5e-6)
    actual = model.rhs(state, u, p, p.active, xp=np)
    target = model.base.rhs(model.parent_state(state), u, model.parent_layout(p), p.active, xp=np)
    for a, b in zip(model.parent_state(actual), target, strict=True):
        np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("case", ["membrane-only", "barrier-only"])
def test_exact_single_schedule_reductions_keep_full_owner(family, case):
    schema, model = modules(family)
    raw, spec, initial, p, _ = initialized(family, case)
    c = reference.bind(raw)
    for t in (1e-6, 4.5e-6, 7.7e-6):
        state = manufactured(initial, p, spec)._replace(phase_clock_s=np.asarray([t]))
        u = control(schema, spec, t)
        actual = model.rhs(state, u, p, p.active, xp=np)
        expected, _, _ = reference.evaluate(c, reference.flatten(c, state._asdict()), t)
        assert (
            np.max(np.abs(reference.flatten(c, actual._asdict()) - expected) / budgets(c, expected))
            <= 1
        )
        if case == "barrier-only":
            stem = (
                "surface_calcium_energy_water"
                + ("_repair" if family == "repair" else "")
                + "_barrier_interventions"
            )
            bs = importlib.import_module("cells.core." + stem + "_spec")
            bm = importlib.import_module("cells.models." + stem)
            alone = deepcopy(raw)
            for key in (
                "coupled_preparation",
                "membrane_interventions",
                "barrier_intervention",
                "reset_policy",
            ):
                alone["model"].pop(key)
            alone["model"].update(
                id=bs.MODEL_ID,
                barrier_preparation=deepcopy(
                    spec.model.coupled_preparation["provenance"]["barrier_preparation"]
                ),
                intervention=None
                if spec.model.barrier_intervention is None
                else dict(
                    name=spec.model.barrier_intervention.name,
                    site_ids=list(spec.model.barrier_intervention.site_ids),
                    on_s=spec.model.barrier_intervention.on_s,
                    off_s=spec.model.barrier_intervention.off_s,
                    change_s=spec.model.barrier_intervention.change_s,
                    amplitude=spec.model.barrier_intervention.amplitude,
                ),
            )
            for key in ("intervention_capacity", "intervention_target_capacity"):
                alone["execution"].pop(key)
            ss = bs.parse(alone)
            _, q = bm.initial_values(ss)
            target = bm.rhs(bm.STATE_TYPE(*state), u, q, q.active, xp=np)
            for a, b in zip(actual, target, strict=True):
                np.testing.assert_array_equal(a, b)
        else:
            stem = (
                "surface_calcium_energy_water"
                + ("_repair" if family == "repair" else "")
                + "_profile_interventions"
            )
            ms = importlib.import_module("cells.core." + stem + "_spec")
            mm = importlib.import_module("cells.models." + stem)
            # Bind a genuine standalone membrane preparation on the already
            # static exterior faces. The disjoint static recipes commute; no
            # physical layout or sealed artifact is patched after parsing.
            args = deepcopy(prepared(family, case)[0]["profile_request"])
            args["definition"]["model"]["ionic"]["faces"] = deepcopy(raw["model"]["ionic"]["faces"])
            geometry = args["geometry"].copy()
            layout = geometry.pop("layout")
            layout["cell_centres_m"] = np.asarray(layout["cell_centres_m"])
            profile = profiles.prepare(
                args["definition"],
                profiles.Geometry(native.Layout(**layout), **geometry),
                direct._decode_profile(args["default"]),
                [direct._decode_profile(row) for row in args["profiles"]],
                ion_enabled=args["ion_enabled"],
                enabled=args["enabled"],
                is_ecm=args["is_ecm"],
            )
            alone = deepcopy(profile.definition)
            alone["model"].update(
                id=ms.MODEL_ID,
                profile_preparation=dict(
                    definition=profile.definition, provenance=profile.provenance
                ),
                interventions=deepcopy(raw["model"]["membrane_interventions"]),
                phase=spec.model.phase,
                timing_policy=ms.TIMING_POLICY,
                reset_policy=ms.RESET_POLICY,
            )
            for key in ("intervention_capacity", "intervention_target_capacity"):
                alone["execution"][key] = raw["execution"][key]
            ss = ms.parse(alone)
            _, q = mm.initial_values(ss)
            target = mm.rhs(mm.STATE_TYPE(*state), u, q, q.active, xp=np)
            for a, b in zip(actual, target, strict=True):
                np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("case", ["joint", "closed"])
def test_four_step_conservation_actual_pool_and_closed_history(family, case):
    schema, model = modules(family)
    raw, spec, state, p, _ = initialized(family, case)
    times = np.asarray(list(EventGrid(spec)))[:5]
    table = control_values(schema.owner_spec(spec), times[:-1])
    model.check_steps(spec, np.diff(times), table)
    states = [state]
    for i, dt in enumerate(np.diff(times)):
        u = type(table)(*(v[i] for v in table))
        state = rk4_step(lambda y, u=u: model.rhs(y, u, p, p.active, xp=np), state, dt)
        assert model.domain_valid(state, p, p.active, xp=np)
        states.append(state)
    history = model.STATE_TYPE(*(np.stack(v) for v in zip(*states, strict=True)))
    diagnostics = model.check_values(history, spec)
    c = reference.bind(raw)
    balances = [reference.conservation(c, reference.flatten(c, row._asdict())) for row in states]
    for row in balances:
        for key, value in row.items():
            assert abs(value) <= (1e-9 if key == "energy_pJ" else 2e-11)
    probes = {}
    for t in (2.5e-6, spec.experiment.end_time):
        probe = copied(state)._replace(phase_clock_s=np.asarray([t]))
        signal = model.signal_values(probe, p, xp=np)
        if case == "closed" and t == spec.experiment.end_time:
            k = spec.model.species_ids.index("Na")
            assert np.any(
                (signal.membrane.permeability[k] == 0) & (probe.membrane_transferred[k] != 0)
            )
            assert np.any((signal.barrier.face_factor[k] == 0) & (probe.face_transferred[k] != 0))
        model.check_values(probe, spec)
        observed = model.observe_history(
            np.asarray([t]), model.STATE_TYPE(*(v[None] for v in probe)), p, [t], spec
        )
        for key in model.base.STATE_TYPE._fields:
            np.testing.assert_array_equal(getattr(observed, key)[0], getattr(probe, key))
        if family in fixtures.FAMILIES:
            actual = model.parent_state(probe)
            layout = model.parent_layout(p)
            from cells.models import surface_calcium_energy as fuel

            np.testing.assert_array_equal(
                observed.energy_amount_fmol[0], fuel.energy_amounts(actual, layout)
            )
            np.testing.assert_array_equal(
                observed.cell_volume_pL[0], p.volume + actual.volume_increment_pL
            )
            np.testing.assert_array_equal(
                observed.extracellular_volume_pL[0],
                p.extracellular_volume + actual.extracellular_volume_increment_pL,
            )
            b = model.base.balances(actual, model.accounting_layout(p, xp=np))
            np.testing.assert_array_equal(observed.energy_balance_pJ[0], np.atleast_1d(b["energy"]))
            np.testing.assert_array_equal(
                observed.pool_internal_transfer_balance_pJ[0], b["pool_energy"]
            )
        expected, _, _ = reference.evaluate(c, reference.flatten(c, probe._asdict()), t)
        actual = reference.flatten(
            c, model.rhs(probe, control(schema, spec, t), p, p.active, xp=np)._asdict()
        )
        assert np.max(np.abs(actual - expected) / budgets(c, expected)) <= 1
        probes[str(t)] = {k: v.tolist() for k, v in probe._asdict().items()}
    evidence(
        f"conservation-{family}-{case}",
        dict(
            definition=raw,
            diagnostics=diagnostics,
            independent_conservation=balances,
            clock_probes=probes,
            scope="four actual steps and manufactured clock probes; no full50us trajectory",
        ),
        {"times_s": times} | {"state-" + k: v for k, v in history._asdict().items()},
    )


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("case", ["joint", "INIT"])
def test_portable_snapshots_full_controls_and_recipe(family, case, tmp_path):
    schema, model = modules(family)
    raw, spec, state, p, _ = initialized(family, case)
    assert (
        parse_spec(raw) == spec
        and get_model(spec.model) is model
        and spec.fingerprint == digest(raw)
    )
    checkpoint = initialise(spec)
    path = write_snapshot(tmp_path / "snapshot", spec, checkpoint)
    restored = load_snapshot(path)
    assert restored.spec == spec and type(restored.checkpoint.state) is model.STATE_TYPE
    for a, b in zip(
        checkpoint.state + checkpoint.layout,
        restored.checkpoint.state + restored.checkpoint.layout,
        strict=True,
    ):
        np.testing.assert_array_equal(a, b)
    code = (
        "from cells.io import load_snapshot; import sys; "
        "r=load_snapshot(sys.argv[1]); assert len(r.checkpoint.state)==int(sys.argv[2])"
    )
    subprocess.run(
        [sys.executable, "-B", "-c", code, str(path), str(len(state))], check=True, timeout=180
    )
    for t in sorted({0.0, *(v.time for v in spec.experiment.changes)}):
        full = control_values(spec, [t])
        parent = control_values(schema.owner_spec(spec), [t])
        for a, b in zip(full, parent, strict=True):
            np.testing.assert_array_equal(a, b)
    evidence(
        f"portable-{family}-{case}",
        dict(
            definition=raw,
            fresh_process_field_count=True,
            in_process_state_and_layout_exact=True,
            all_held_controls_exact=True,
        ),
    )


@pytest.mark.parametrize("family", FAMILIES)
def test_no_projection_or_older_water_runtime_is_used(family, monkeypatch):
    from cells.models import surface_calcium_energy_water as old_water
    from cells.models import surface_calcium_energy_water_repair as old_repair
    from cells.models import surface_calcium_profile_interventions as old_calcium

    def forbidden(*args, **kwargs):
        raise AssertionError("Forbidden projected or older water runtime")

    for module in (old_calcium, old_water, old_repair):
        for name in ("initial_values", "rhs", "readouts", "check_definition"):
            monkeypatch.setattr(module, name, forbidden)
    schema, model = modules(family)
    raw = deepcopy(initialized(family)[0])
    spec = schema.parse(raw)
    state, p = model.initial_values(spec)
    assert model.readouts(state, control(schema, spec, 0.0), p, xp=np).valid
    assert schema.owner_spec(spec).to_dict()["model"]["id"] == fixtures.PARENT_IDS[family]


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize(
    "fault",
    [
        "owner",
        "stores",
        "fuel",
        "water",
        "injury",
        "old_parent",
        "ionic_parent",
        "order",
        "stale",
        "phase",
        "reset",
        "capacity",
        "negative",
        "excess",
        "missing",
        "mixed_owner",
    ],
)
def test_mismatched_full_owner_or_schedule_refused(family, fault):
    schema, _ = modules(family)
    raw = deepcopy(initialized(family)[0])
    m = raw["model"]
    if fault == "owner":
        m["ionic"]["cells"][0]["volume_pL"] *= 2
    if fault == "stores":
        m["stores"][0]["model"]["membrane"]["specific_capacitance_F_per_m2"] *= 2
    if fault == "fuel":
        m["energy_pools"][0]["initial_amount_fmol"]["ATP"] *= 2
    if fault == "water":
        m["water_compartments"][0]["reference_volume_pL"] *= 0.9
    if fault == "injury":
        if family == "repair":
            m["injury_patches"][0]["initial_damage"] *= 0.5
        else:
            m["injury_patches"] = []
    if fault == "old_parent":
        m["coupled_preparation"]["definition"]["model"]["id"] = "resolved_calcium_energy_water@1"
    if fault == "ionic_parent":
        m["ionic"]["id"] = "resolved_tissue@7"
    if fault == "order":
        m["coupled_preparation"]["provenance"]["order"] = "implicit"
    if fault == "stale":
        m["coupled_preparation"]["provenance"]["identity"] = "stale"
    if fault == "phase":
        m["phase"] = "CARRIED"
    if fault == "reset":
        m["reset_policy"] = "rebase"
    if fault == "capacity":
        raw["execution"]["intervention_target_capacity"] = 0
    if fault == "negative":
        m["membrane_interventions"][0]["amplitude"] = -1000.0
    if fault == "excess":
        m["barrier_intervention"]["amplitude"] = 1.1
    if fault == "missing":
        raw["execution"].pop("barrier_target_capacity")
    if fault == "mixed_owner":
        raw["model"]["id"] = fixtures.MODEL_IDS["repair" if family == "water" else "water"]
    with pytest.raises(ConfigError):
        schema.parse(raw)


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("history_name", ["membrane_transferred", "face_transferred"])
def test_closed_history_corruption_and_both_step_bounds_refuse(family, history_name):
    schema, model = modules(family)
    _, spec, state, p, _ = initialized(family, "closed")
    times = np.asarray(list(EventGrid(spec)))
    table = control_values(spec, times[:-1])
    model.check_steps(spec, np.diff(times), table)
    with pytest.raises(ConfigError):
        model.check_steps(spec, np.asarray([1e-6]), table)
    state = copied(state)._replace(phase_clock_s=np.asarray([spec.experiment.end_time]))
    k = spec.model.species_ids.index("Na")
    signal = model.signal_values(state, p, xp=np)
    coeff = (
        signal.membrane.permeability
        if history_name == "membrane_transferred"
        else signal.barrier.face_factor
    )
    q = model.accounting_layout(p, xp=np)
    support = q.membrane_permeability if history_name == "membrane_transferred" else q.face_factor
    route = np.flatnonzero((coeff[k] == 0) & (support[k] > 0))[0]
    getattr(state, history_name)[k, route] = np.nan
    assert not model.domain_valid(state, p, p.active, xp=np)
    assert not model.readouts(
        state, control(schema, spec, spec.experiment.end_time), p, xp=np
    ).valid
    with pytest.raises(NumericalError):
        model.check_values(state, spec)


@pytest.mark.parametrize("family", FAMILIES)
def test_strong_background_sum_boundary_keeps_full_minimum_volume_and_injury_guards(family):
    from cells.core.surface_calcium_spec import SurfaceCalciumHCNExtraModel
    from cells.models import surface_calcium as calcium
    from cells.models import surface_calcium_energy as fuel
    from cells.processes import calcium_gates

    schema, model = modules(family)
    _, original, _, _, _ = initialized(family)
    events = tuple(
        replace(event, amplitude=1e12) if event.kind == "Na_mem" else event
        for event in original.model.membrane_interventions
    )
    strong = replace(original, model=replace(original.model, membrane_interventions=events))
    complete = model.accounting_spec(strong)
    assert complete.to_dict()["model"]["id"] == fixtures.PARENT_IDS[family]
    _, p = model.initial_values(strong)
    minimum = p.water_minimum_volume_pL
    upper = model.accounting_layout(p, xp=np)._replace(
        volume=minimum[: p.active.size], extracellular_volume=minimum[p.active.size :]
    )
    vmax = max(map(abs, calcium_gates.VOLTAGE_DOMAIN_V))

    def independent_outflow(permeability):
        inside = np.zeros_like(upper.amount_reference)
        outside = np.zeros_like(upper.extracellular_amount_reference)
        for species, z in enumerate(complete.model.valence):
            factor = 1 + abs(z) * reference.F * vmax / (reference.R * float(upper.temperature))
            for j in np.flatnonzero(upper.membrane_active):
                rate = permeability[species, j] * upper.membrane_area[j] / 1e-15 * factor
                inside[species, upper.membrane_cell[j]] += (
                    rate / upper.volume[upper.membrane_cell[j]]
                )
                outside[species, upper.membrane_outside[j]] += (
                    rate / upper.extracellular_volume[upper.membrane_outside[j]]
                )
        return max(float(np.max(inside, initial=0)), float(np.max(outside, initial=0)))

    background = independent_outflow(upper.membrane_permeability)
    bounded = fuel.bounded_prior_spec(
        model.water_owner.minimum_energy_spec(model.water_projection(complete))
    )
    # This is an internal bound view: it deliberately retains the complete
    # water/fuel controls. Check its exact physical model without serializing
    # that control-bearing view as a standalone calcium simulation.
    assert type(bounded.model) is SurfaceCalciumHCNExtraModel
    assert len(bounded.model.channels) == 63
    chemistry = calcium.loss_bound(bounded)
    injury = independent_outflow(upper.injury_permeability) if family == "repair" else 0.0
    if family == "repair":
        np.testing.assert_allclose(injury, model.base.injury_loss_bound(complete), rtol=5e-15)
    bound = background + chemistry + injury
    cutoff = 0.25 / bound
    below, above = cutoff * (1 - 1e-8), cutoff * (1 + 1e-8)
    controls = control_values(schema.owner_spec(strong), [0.0])
    model.base.check_steps(complete, np.asarray([above]), controls)
    model.binding.check_ramp_steps(strong, np.asarray([above]))
    model.check_steps(strong, np.asarray([below]), controls)
    with pytest.raises(ConfigError, match="background"):
        model.check_steps(strong, np.asarray([above]), controls)
    evidence(
        "background-boundary-" + family,
        dict(
            parent_model_id=fixtures.PARENT_IDS[family],
            background_bound_s=background,
            full_minimum_volume_chemical_bound_s=chemistry,
            minimum_volume_injury_bound_s=injury,
            sum_bound_s=bound,
            cutoff_s=cutoff,
            below_s=below,
            above_s=above,
            below_product=below * bound,
            above_product=above * bound,
            inherited_parent_guards_kept=True,
            both_ramp_guards_kept=True,
            limit=0.25,
        ),
    )


@pytest.mark.parametrize("family", FAMILIES)
def test_live_volume_drives_all_three_pumps_and_neutral_osmolytes_once(family):
    from cells.models import surface_calcium_energy as fuel

    schema, model = modules(family)
    raw, spec, initial, p, _ = initialized(family)
    time = 4.5e-6
    state = manufactured(initial, p, spec)._replace(phase_clock_s=np.asarray([time]))
    signal = model.signal_values(state, p, xp=np)
    current = model.parent_layout(p)._replace(
        membrane_permeability=signal.membrane.permeability,
        face_factor=signal.barrier.face_factor,
    )
    physical = model.water_owner.effective_layout(state, model.water_layout(current))
    stage = fuel.stage_layout(model.water_owner.prior_state(state), physical, xp=np)
    amounts = fuel.energy_amounts(state, p)
    concentration = amounts / stage.volume
    assert np.any(stage.volume[p.active] != p.volume[p.active])
    for prefix, owners in (
        ("pump_", p.membrane_cell),
        ("pmca_", p.membrane_cell),
        ("er_pump_", np.arange(p.er_pump_present.size)),
    ):
        present = getattr(p, prefix + "present")
        for i, name in enumerate(("atp", "adp", "pi")):
            key = prefix + name + ("_mM" if prefix == "pump_" else "")
            np.testing.assert_array_equal(
                getattr(stage, key)[present], concentration[i, owners[present]]
            )
    particles = model.water_owner.osmolyte_amounts(state, model.water_layout(current))
    np.testing.assert_array_equal(particles[-3:, : p.active.size], amounts)
    assert not np.any(particles[-3:, p.active.size :])
    cytosol = p.cytosol_selector.astype(bool)
    np.testing.assert_array_equal(stage.er_volume[~cytosol], p.er_volume[~cytosol])
    np.testing.assert_array_equal(
        stage.er_volume[cytosol],
        np.broadcast_to(stage.volume[: cytosol.shape[0], None], cytosol.shape)[cytosol],
    )
    context = reference.bind(raw)
    target, _, proof = reference.evaluate(
        context, reference.flatten(context, state._asdict()), time
    )
    actual = reference.flatten(
        context, model.rhs(state, control(schema, spec, time), p, p.active, xp=np)._asdict()
    )
    assert np.max(np.abs(actual - target) / budgets(context, target)) <= 1
    evidence(
        "live-owners-" + family,
        dict(
            actual_volumes_all_three_pumps=True,
            no_duplicate_fuel_particles=True,
            fixed_er=True,
            actual_damage=family == "repair",
            independent=proof,
        ),
    )


@pytest.mark.parametrize("family", FAMILIES)
def test_both_closed_routes_keep_actual_ledgers_in_observation_and_lesion_rates(family):
    schema, model = modules(family)
    raw, spec, initial, p, _ = initialized(family, "closed")
    time = spec.experiment.end_time
    state = copied(initial)._replace(phase_clock_s=np.asarray([time]))
    signal = model.signal_values(state, p, xp=np)
    upper = model.accounting_layout(p, xp=np)
    na = spec.model.species_ids.index("Na")
    moved = 1e-14
    closed_membrane = (signal.membrane.permeability[na] == 0) & (
        upper.membrane_permeability[na] > 0
    )
    membrane = int(np.flatnonzero(closed_membrane)[0])
    cell, outside = p.membrane_cell[membrane], p.membrane_outside[membrane]
    state.membrane_transferred[na, membrane] = moved
    state.amount_increment[na, cell] -= moved
    state.extracellular_amount_increment[na, outside] += moved
    state.chemical_amount_increment[cell] -= (
        moved * p.free_ion_selector[:, na, None] * p.cytosol_selector[cell]
    )
    state.membrane_dissipated_energy_pJ[membrane] = moved
    closed_face = (signal.barrier.face_factor[na] == 0) & (upper.face_factor[na] > 0)
    face = int(np.flatnonzero(closed_face)[0])
    state.face_transferred[na, face] = moved
    state.extracellular_amount_increment[na, p.face_sender[face]] -= moved
    state.extracellular_amount_increment[na, p.face_receiver[face]] += moved
    state.face_dissipated_energy_pJ[face] = moved
    before = [value.tobytes() for value in state]
    model.check_values(state, spec)
    obs = model.observe_history(
        np.asarray([time]), model.STATE_TYPE(*(value[None] for value in state)), p, [time], spec
    )
    for key in model.STATE_TYPE._fields:
        np.testing.assert_array_equal(getattr(obs, key)[0], getattr(state, key))
    balance = model.base.balances(model.parent_state(state), upper)
    np.testing.assert_array_equal(obs.energy_balance_pJ[0], np.atleast_1d(balance["energy"]))
    np.testing.assert_array_equal(obs.pool_internal_transfer_balance_pJ[0], balance["pool_energy"])
    context = reference.bind(raw)
    expected, _, proof = reference.evaluate(
        context, reference.flatten(context, state._asdict()), time
    )
    slope = model.rhs(state, control(schema, spec, time), p, p.active, xp=np)
    actual = reference.flatten(context, slope._asdict())
    assert np.max(np.abs(actual - expected) / budgets(context, expected)) <= 1
    if family == "repair":
        assert np.any(slope.injury_transferred[na, p.membrane_active] != 0)
        np.testing.assert_array_equal(obs.damage[0], state.damage)
        np.testing.assert_array_equal(obs.injury_transferred[0], state.injury_transferred)
    assert before == [value.tobytes() for value in state]
    evidence(
        "closed-history-" + family,
        dict(
            definition=raw,
            manufactured_history_not_evolved=True,
            original_energy_work_and_water_anchors=True,
            both_actual_transfer_markers_retained=True,
            independent=proof,
        ),
        {"state-" + key: value for key, value in state._asdict().items()}
        | {"observation-" + key: value for key, value in vars(obs).items()},
    )


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize(
    "fault",
    [
        "negative-clock",
        "clock-nan",
        "clock-end",
        "volume",
        "fuel",
        "padding",
        "negative-face-heat",
        "negative-membrane-heat",
        "water-ledger-nan",
    ],
)
def test_actual_volume_pool_and_original_histories_cannot_be_hidden_by_init(family, fault):
    schema, model = modules(family)
    _, spec, initial, p, _ = initialized(family, "INIT")
    state = copied(initial)
    if fault in ("negative-clock", "clock-nan", "clock-end"):
        state.phase_clock_s[0] = {
            "negative-clock": -1e-9,
            "clock-nan": np.nan,
            "clock-end": 1e-3,
        }[fault]
    elif fault == "volume":
        state.volume_increment_pL[0] = -p.volume[0]
    elif fault == "fuel":
        state.energy_amount_increment_fmol[0, 0] = -p.energy_initial_amount_fmol[0, 0]
    elif fault == "padding":
        state.volume_increment_pL[-1] = 1e-3
    elif fault == "negative-face-heat":
        state.face_dissipated_energy_pJ[0] = -0.1
    elif fault == "negative-membrane-heat":
        state.membrane_dissipated_energy_pJ[0] = -0.1
    else:
        state.water_transferred_pL[0] = np.nan
    before = [value.tobytes() for value in state]
    with np.errstate(all="ignore"):
        assert not model.control_domain_valid(state, control(schema, spec, 0.0), p, p.active, xp=np)
        with pytest.raises(NumericalError):
            model.check_values(state, spec)
    assert before == [value.tobytes() for value in state]
    evidence("state-refusal-" + family + "-" + fault, dict(fault=fault, actual_state_refused=True))


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("which", ["membrane", "barrier"])
def test_each_native_ramp_guard_keeps_all_inherited_limits(family, which):
    schema, model = modules(family)
    _, spec, _, _, _ = initialized(family)
    ceiling = spec.execution.dt / 2
    if which == "membrane":
        event, *others = spec.model.membrane_interventions
        amended = replace(
            spec.model,
            membrane_interventions=(replace(event, change_s=8 * ceiling), *others),
        )
    else:
        amended = replace(
            spec.model,
            barrier_intervention=replace(spec.model.barrier_intervention, change_s=8 * ceiling),
        )
    narrow = replace(spec, model=amended)
    controls = control_values(schema.owner_spec(narrow), [0.0])
    model.base.check_steps(model.accounting_spec(narrow), np.asarray([spec.execution.dt]), controls)
    with pytest.raises(ConfigError, match="transition"):
        model.check_steps(narrow, np.asarray([spec.execution.dt]), controls)
    evidence("ramp-refusal-" + family + "-" + which, dict(which=which, parent_guard_retained=True))


@pytest.mark.parametrize("family", FAMILIES)
def test_phase_clock_tolerance_keeps_the_actual_physical_horizon(family):
    _, model = modules(family)
    raw, spec, initial, p, _ = initialized(family)
    time = 4.5e-6
    state = copied(initial)._replace(phase_clock_s=np.asarray([time]))
    context = reference.bind(raw)
    vector = reference.flatten(context, state._asdict())
    tolerance = 64 * np.finfo(float).eps * max(spec.experiment.end_time, spec.execution.dt)
    assert tolerance == p.phase_clock_atol_s == context["phase_clock_atol_s"]
    within, outside = time + 0.5 * tolerance, time + 8 * tolerance
    reference.current_definition(context, vector, within)
    model.check_checkpoint(spec, SimpleNamespace(state=state, time=within))
    with pytest.raises(ValueError, match="clock"):
        reference.current_definition(context, vector, outside)
    with pytest.raises(ConfigError):
        model.check_checkpoint(spec, SimpleNamespace(state=state, time=outside))
    evidence(
        "clock-tolerance-" + family,
        dict(tolerance_s=tolerance, actual_horizon_s=spec.experiment.end_time),
    )


@pytest.mark.parametrize("family", FAMILIES)
def test_duplicate_occurrences_assign_without_adding_material_or_coefficients(family):
    schema, model = modules(family)
    raw, spec, initial, p, _ = initialized(family)
    duplicate = deepcopy(raw)
    for event in duplicate["model"]["membrane_interventions"]:
        event["profiles"] *= 2
        if event["spatial"] is not None:
            event["spatial"]["values"] *= 2
    duplicate["model"]["barrier_intervention"]["site_ids"] *= 2
    duplicate["execution"]["intervention_target_capacity"] *= 2
    duplicate["execution"]["barrier_target_capacity"] *= 2
    other = schema.parse(duplicate)
    other_state, q = model.initial_values(other)
    for a, b in zip(initial, other_state, strict=True):
        np.testing.assert_array_equal(a, b)
    for time in (0.0, 4.5e-6, spec.experiment.end_time):
        state = copied(initial)._replace(phase_clock_s=np.asarray([time]))
        a, b = model.signal_values(state, p, xp=np), model.signal_values(state, q, xp=np)
        for left, right in zip(a.membrane, b.membrane, strict=True):
            np.testing.assert_array_equal(left, right)
        for left, right in zip(a.barrier, b.barrier, strict=True):
            np.testing.assert_array_equal(left, right)
        u = control(schema, spec, time)
        for left, right in zip(
            model.rhs(state, u, p, p.active, xp=np),
            model.rhs(state, u, q, q.active, xp=np),
            strict=True,
        ):
            np.testing.assert_array_equal(left, right)
    evidence("duplicates-" + family, dict(ordered_assignment_not_addition=True))


def test_independent_equation_source_has_no_cells_or_jax_imports():
    tree = ast.parse(Path(reference.__file__).read_text())
    for node in ast.walk(tree):
        names = (
            [row.name for row in node.names]
            if isinstance(node, ast.Import)
            else [node.module or ""]
            if isinstance(node, ast.ImportFrom)
            else []
        )
        assert not any(name.split(".")[0] in ("cells", "jax") for name in names)
    evidence("oracle-source", dict(no_production_or_accelerator_imports=True))


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("history_name", ["membrane_transferred", "face_transferred"])
def test_finite_closed_route_corruption_fails_original_material_checks(family, history_name):
    _, model = modules(family)
    _, spec, initial, p, _ = initialized(family, "closed")
    state = copied(initial)._replace(phase_clock_s=np.asarray([spec.experiment.end_time]))
    signal = model.signal_values(state, p, xp=np)
    upper = model.accounting_layout(p, xp=np)
    na = spec.model.species_ids.index("Na")
    current, support = (
        (signal.membrane.permeability, upper.membrane_permeability)
        if history_name == "membrane_transferred"
        else (signal.barrier.face_factor, upper.face_factor)
    )
    route = int(np.flatnonzero((current[na] == 0) & (support[na] > 0))[0])
    # This is a finite, supported historical transfer. Its missing matching
    # amount change is a material error that a closed-route readout must retain.
    getattr(state, history_name)[na, route] = 1e-3
    assert model.domain_valid(state, p, p.active, xp=np)
    before = [value.tobytes() for value in state]
    with pytest.raises(NumericalError):
        model.check_values(state, spec)
    with pytest.raises(NumericalError):
        model.observe_history(
            np.asarray([spec.experiment.end_time]),
            model.STATE_TYPE(*(value[None] for value in state)),
            p,
            [spec.experiment.end_time],
            spec,
        )
    assert before == [value.tobytes() for value in state]
    evidence(
        "finite-history-corruption-" + family + "-" + history_name,
        dict(
            history=history_name,
            finite_supported_transfer=True,
            actual_material_imbalance_refused=True,
            observer_refuses_before_readout_view=True,
        ),
    )


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("history_name", ["water_transferred_pL", "pool_volume_work_pJ"])
def test_actual_water_and_pool_work_corruption_fails_original_accounting(family, history_name):
    _, model = modules(family)
    _, spec, initial, p, _ = initialized(family, "closed")
    state = copied(initial)._replace(phase_clock_s=np.asarray([spec.experiment.end_time]))
    wet = p.membrane_active & (p.water_conductance_pL_per_Pa_s > 0)
    membrane = int(np.flatnonzero(wet)[0])
    owner = membrane if history_name == "water_transferred_pL" else p.membrane_cell[membrane]
    getattr(state, history_name)[owner] = 1e-3
    assert model.domain_valid(state, p, p.active, xp=np)
    before = [value.tobytes() for value in state]
    with pytest.raises(NumericalError):
        model.check_values(state, spec)
    with pytest.raises(NumericalError):
        model.observe_history(
            np.asarray([spec.experiment.end_time]),
            model.STATE_TYPE(*(value[None] for value in state)),
            p,
            [spec.experiment.end_time],
            spec,
        )
    assert before == [value.tobytes() for value in state]
    evidence(
        "physical-work-corruption-" + family + "-" + history_name,
        dict(history=history_name, actual_original_accounting_refused=True),
    )
