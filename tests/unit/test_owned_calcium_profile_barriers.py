"""Complete calcium/fuel dual schedules, independent stages and durable histories."""

import importlib
import json
import os
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from cells.core import owned_calcium_profile_barrier_preparation as preparation
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
from validation.transport import owned_calcium_profile_barrier_fixtures as fixtures
from validation.transport import owned_calcium_profile_barrier_reference as reference

FAMILIES = [pytest.param("calcium", id="chemical_owner"), pytest.param("energy", id="fuel_owner")]


def modules(family):
    stem = (
        "surface_calcium"
        + ("_energy" if family == "energy" else "")
        + "_profile_barrier_interventions"
    )
    return importlib.import_module("cells.core." + stem + "_spec"), importlib.import_module(
        "cells.models." + stem
    )


def evidence(name, record, arrays=None):
    if path := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(path) / "owned-calcium-profile-barriers"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (name + ".json")).write_text(
            json.dumps(record, indent=2, allow_nan=False, default=lambda v: np.asarray(v).tolist())
            + "\n"
        )
        if arrays is not None:
            np.savez_compressed(folder / (name + ".npz"), **arrays)


@lru_cache
def prepared(family="energy", case="joint", permuted=False, padded=True):
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
def initialized(family="energy", case="joint", permuted=False, padded=True):
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
    value = copied(state)
    i, o = p.membrane_cell[0], p.membrane_outside[0]
    for species, amount in (("K", 1e-5), ("Ca", 1e-8)):
        k = spec.model.species_ids.index(species)
        value.amount_increment[k, i] -= amount
        value.extracellular_amount_increment[k, o] += amount
        value.membrane_transferred[k, 0] += amount
        value.chemical_amount_increment[i] -= (
            amount * p.free_ion_selector[:, k, None] * p.cytosol_selector[i]
        )
    if hasattr(value, "energy_amount_increment_fmol"):
        value.energy_amount_increment_fmol[0, p.active] -= 2e-4
        value.energy_amount_increment_fmol[1, p.active] += 2e-4
        value.energy_amount_increment_fmol[2, p.active] += 2e-4
    return value


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
    assert len(state) == (35 if family == "calcium" else 39)
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
            current_fuel_scope=family == "energy",
        ),
    )


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("case", fixtures.CASES)
@pytest.mark.parametrize("changed", [False, True])
def test_full_stage_all_stores_gates_actual_fuel_and_both_coefficients(family, case, changed):
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
                "surface_calcium"
                + ("_energy" if family == "energy" else "")
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
        if family == "energy":
            actual = model.parent_state(probe)
            layout = model.parent_layout(p)
            from cells.models import surface_calcium_energy as fuel

            np.testing.assert_array_equal(
                observed.energy_amount_fmol[0], fuel.energy_amounts(actual, layout)
            )
            b = fuel.balances(actual, model.accounting_layout(p, xp=np))
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
            scope="four actual steps and manufactured clock probes; no full10us trajectory",
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
        [sys.executable, "-B", "-c", code, str(path), str(len(state))], check=True, timeout=45
    )
    for t in sorted({0.0, *(v.time for v in spec.experiment.changes)}):
        full = control_values(spec, [t])
        parent = control_values(schema.owner_spec(spec), [t])
        for a, b in zip(full, parent, strict=True):
            np.testing.assert_array_equal(a, b)
    evidence(
        f"portable-{family}-{case}",
        dict(definition=raw, fresh_process_exact=True, all_held_controls_exact=True),
    )


@pytest.mark.parametrize("family", FAMILIES)
def test_old_calcium_membrane_runtime_is_never_used(family, monkeypatch):
    from cells.models import surface_calcium_profile_interventions as old

    def forbidden(*a, **k):
        raise AssertionError("Forbidden calcium@6 membrane runtime")

    for name in ("initial_values", "rhs", "readouts", "check_definition"):
        monkeypatch.setattr(old, name, forbidden)
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
        if family == "energy":
            m["energy_pools"][0]["initial_amount_fmol"]["ATP"] *= 2
        else:
            m["plasma_transport"]["membranes"][0]["pump"]["capacity_fmol_per_s"] *= 2
    if fault == "old_parent":
        m["coupled_preparation"]["definition"]["model"]["id"] = "resolved_calcium@6"
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
        raw["model"]["id"] = fixtures.MODEL_IDS["energy" if family == "calcium" else "calcium"]
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
def test_strong_background_sum_boundary_keeps_full_chemical_and_fuel_guards(family):
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
    upper = model.accounting_layout(p, xp=np)
    # Independent owner loops evaluate the qualified GHK outflow inequality.
    # The chemical/fuel bound itself is the unchanged qualified full parent.
    inside = np.zeros_like(upper.amount_reference)
    outside = np.zeros_like(upper.extracellular_amount_reference)
    vmax = max(map(abs, calcium_gates.VOLTAGE_DOMAIN_V))
    for s, z in enumerate(complete.model.valence):
        factor = 1 + abs(z) * reference.F * vmax / (reference.R * float(upper.temperature))
        for j in np.flatnonzero(upper.membrane_active):
            rate = upper.membrane_permeability[s, j] * upper.membrane_area[j] / 1e-15 * factor
            inside[s, upper.membrane_cell[j]] += rate / upper.volume[upper.membrane_cell[j]]
            outside[s, upper.membrane_outside[j]] += (
                rate / upper.extracellular_volume[upper.membrane_outside[j]]
            )
    background = max(float(np.max(inside, initial=0)), float(np.max(outside, initial=0)))
    if family == "calcium":
        chemistry = calcium.loss_bound(complete)
    else:
        bounded = fuel.bounded_prior_spec(complete)
        # This internal bound retains the full parent's experiment/execution;
        # it is not a standalone serializable calcium simulation.
        assert type(bounded.model) is SurfaceCalciumHCNExtraModel
        assert len(bounded.model.channels) == 63
        chemistry = fuel.prior.loss_bound(bounded)
    bound = background + chemistry
    cutoff = 0.25 / bound
    below, above = cutoff * (1 - 1e-8), cutoff * (1 + 1e-8)
    controls = control_values(schema.owner_spec(strong), [0.0])
    # The omitted sum admitted this counterexample through the parent's
    # distinct ceilings and both ramp guards. Only the restored sum refuses it.
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
            full_chemical_or_bounded_fuel_bound_s=chemistry,
            sum_bound_s=bound,
            cutoff_s=cutoff,
            below_s=below,
            above_s=above,
            below_product=below * bound,
            above_product=above * bound,
            inherited_parent_guards_kept=True,
            ramp_guards_kept=True,
            limit=0.25,
        ),
    )
