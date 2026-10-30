"""Charged trajectories, carried independent references and complete restart."""

import hashlib
import json
from dataclasses import replace

import numpy as np
import pytest

from cells import physiology_protein_checkpoint as persistence
from cells.core import physiology_perturbation_step as component_step
from cells.core import physiology_protein_charge_interval as interval
from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as units
from cells.core import physiology_tissue_step as ordinary
from cells.core.grid import EventGrid
from cells.core.specs import digest, parse_spec
from cells.core.state import Checkpoint
from cells.models import physiology_permeability_view as view
from cells.models import physiology_protein_charge_rhs as charged
from cells.processes import betse_perturbations as perturb
from tests.integration.test_physiology_protein_charge_view import active_nodes, changed_protein
from tests.unit.test_physiology_permeability_view import exact_tree, fingerprints
from tests.unit.test_physiology_tissue_binding import arguments, component_state, definition
from tests.unit.test_physiology_tissue_step import KINDS, control, evidence
from validation.tissue import physiology_protein_charge_interval_reference as reference


def inputs(kind="passive", *, zero=False):
    raw = definition(kind, padded=True, reorder=True)
    raw["execution"]["dt"] *= 0.125
    # Preserve the original physical horizon while declaring the finer grid's
    # bookkeeping capacity. The qualification evolves only its first intervals.
    raw["execution"]["max_steps"] *= 8
    event = 0.75 * raw["execution"]["dt"]
    raw["experiment"]["membrane_controls"][0]["schedule"].append(
        dict(time=event, availability=0.35)
    )
    spec = parse_spec(raw)
    args = arguments(spec, reverse=True)
    args["membrane_thickness_m"] = {
        row.id: 2.0 ** (-28 - i % 3) for i, row in enumerate(spec.model.membranes)
    }
    binding = units.bind_tissue(spec, **args)
    anchor = component_state(binding)
    if kind in ("calcium", "fuel"):
        rng = np.random.RandomState(17)
        rng.normal()  # Explicit fixture with a pending native normal cache.
        rng = perturb._native_stream(rng.get_state(), np.__version__)
    else:
        rng = perturb.StableCoordinates(17, 7)
    stream = streams.new_stream(
        binding.component, rng, stream_id="held-protein", world_id=7, next_tick=31
    )
    anchor = replace(anchor, stream=stream)
    component = anchor if zero else changed_protein(binding, anchor)
    implementation = view.IMPLEMENTATIONS[type(spec.model)]
    state, layout = implementation.initial_values(spec)
    seed = Checkpoint(state, layout, 0.0, 0, 0)
    point = interval.initialise(
        spec,
        seed,
        binding,
        anchor,
        component,
        protein_species_id="held-test-protein",
        valence=-1,
    )
    return spec, point, implementation


def parameters(spec, point, count):
    grid = EventGrid(spec)
    return dict(
        raw=spec.to_dict(),
        fields=point.state._asdict(),
        binding=units.binding_record(point.binding),
        current_diffusion=point.component.diffusion.current_m2_s,
        before=point.charge_reference.protein._asdict(),
        after=point.component.protein._asdict(),
        valence=point.valence,
        intervals=[
            dict(
                duration_s=grid[i + 1] - grid[i],
                held_control=control(spec, grid[i])._asdict(),
                endpoint_control=control(spec, grid[i + 1])._asdict(),
            )
            for i in range(point.step_index, point.step_index + count)
        ],
    )


@pytest.mark.parametrize("kind", KINDS)
def test_carried_charged_trajectory_restarts_at_control_boundary_against_independent_ODE(
    tmp_path,
    kind,
):
    spec, initial, implementation = inputs(kind)
    before = fingerprints(spec, initial.state, initial.layout, initial.component)
    first = interval.advance(spec, initial)
    assert first.checkpoint.time == 0.75 * spec.execution.dt
    assert first.checkpoint.event_index != initial.event_index
    path = persistence.write_held_protein_checkpoint(tmp_path / "held", spec, first.checkpoint)
    loaded = persistence.load_held_protein_checkpoint(path)
    assert loaded.checkpoint.identity == first.checkpoint.identity
    exact_tree(loaded.checkpoint.state, first.checkpoint.state)
    exact_tree(loaded.checkpoint.layout, initial.layout)
    resumed = interval.advance(loaded.spec, loaded.checkpoint)
    continuous = interval.advance(spec, first.checkpoint)
    exact_tree(resumed.checkpoint.state, continuous.checkpoint.state)
    assert resumed.checkpoint.identity == continuous.checkpoint.identity
    params = parameters(spec, initial, 2)
    standard = reference.integrate(**params)
    tight = reference.integrate(**params, refinement=2)
    saved, errors = {}, []
    for index, result in enumerate((first, resumed)):
        target, less = tight["endpoints"][index], standard["endpoints"][index]
        context = target["context"]
        oracle = reference.local.rates.permeability.ORACLES[spec.to_dict()["model"]["id"]]
        budget = oracle.flatten(
            context,
            {
                name: np.full(shape, 3e-23 if name.endswith("_C") else 3e-12)
                for name, shape in context["shapes"].items()
            },
        ) + 3e-10 * abs(target["state"])
        state = oracle.flatten(context, result.checkpoint.state._asdict())
        prepared = charged.evaluate(
            spec,
            initial.seed,
            initial.binding,
            initial.charge_reference,
            initial.component,
            protein_species_id=initial.protein_species_id,
            valence=-1,
            step_s=params["intervals"][0]["duration_s"],
        )
        actual_phi = active_nodes(
            initial.seed,
            charged.array_readouts(
                result.checkpoint.state,
                control(spec, result.checkpoint.time),
                prepared.original.runtime_layout,
                prepared.rates.protein_charge_increment_C,
                implementation=implementation,
                xp=np,
            ).field.potential_V,
        )
        phi_budget = 3e-13 + 3e-10 * abs(target["endpoint_potential_V"])
        error = dict(
            state=float(np.max(abs(state - target["state"]) / budget)),
            reference=float(np.max(abs(less["state"] - target["state"]) / budget)),
            potential=float(np.max(abs(actual_phi - target["endpoint_potential_V"]) / phi_budget)),
            reference_potential=float(
                np.max(
                    abs(less["endpoint_potential_V"] - target["endpoint_potential_V"]) / phi_budget
                )
            ),
        )
        errors.append(error)
        assert max(error.values()) <= 1
        assert max(error["reference"], error["reference_potential"]) <= 0.1
        for label, value in dict(
            actual=state,
            expected=target["state"],
            standard=less["state"],
            budget=budget,
            actual_phi=actual_phi,
            expected_phi=target["endpoint_potential_V"],
            standard_phi=less["endpoint_potential_V"],
            phi_budget=phi_budget,
        ).items():
            saved[str(index) + "_" + label] = value
        assert result.interval_accounting.valid and result.cumulative_accounting.valid
        assert result.checkpoint.component is loaded.checkpoint.component or index == 0
        assert streams.stream_record(result.checkpoint.component.stream) == streams.stream_record(
            initial.component.stream
        )
    evidence(
        "held-protein-trajectory-" + kind,
        dict(
            **params,
            errors=errors,
            accepted_steps=2,
            exact_restart=True,
            source_identity=initial.identity,
            final_identity=resumed.checkpoint.identity,
            complete_fields=len(initial.state),
            conditioned_initial_state=True,
            protein_transitions=0,
            additional_biological_cases=0,
            accounting=[
                dict(
                    local_balances=dict(result.interval_accounting.balances),
                    cumulative_balances=dict(result.cumulative_accounting.balances),
                    energy_terms=dict(result.cumulative_accounting.energy_terms),
                )
                for result in (first, resumed)
            ],
        ),
        saved,
    )
    assert fingerprints(spec, initial.state, initial.layout, initial.component) == before


@pytest.mark.parametrize("kind", ("passive", "fuel"))
def test_zero_charge_continuation_is_bit_exact_ordinary_tissue_step(kind):
    spec, point, _ = inputs(kind, zero=True)
    original = point.seed
    for _ in range(2):
        expected = ordinary.advance(spec, original, point.binding, point.component)
        result = interval.advance(spec, point)
        exact_tree(result.checkpoint.state, expected.checkpoint.state)
        original, point = expected.checkpoint, result.checkpoint


@pytest.mark.parametrize("defect", ("identity", "time", "index", "event", "dtype", "material"))
def test_resealed_invalid_endpoint_refuses_without_modifying_source(defect):
    spec, point, _ = inputs()
    point = interval.advance(spec, point).checkpoint
    before = point.identity
    if defect in ("time", "index", "event"):
        name = dict(time="time", index="step_index", event="event_index")[defect]
        changed = replace(point, **{name: getattr(point, name) + 1})
    elif defect in ("dtype", "material"):
        value = np.array(point.state.amount_increment, copy=True)
        if defect == "dtype":
            value = value.astype(np.float32)
        else:
            value[0, 0] += 0.001
        changed = replace(point, state=point.state._replace(amount_increment=value))
    else:
        changed = replace(point, identity="0" * 64)
    if defect != "identity":
        changed = interval._seal(changed)
    with pytest.raises(interval.HeldProteinRejected) as caught:
        interval.advance(spec, changed)
    assert caught.value.stage == "source_admission"
    assert caught.value.trial is None and point.identity == before


@pytest.mark.parametrize("defect", ("missing", "bytes", "clock", "state", "component", "runtime"))
def test_checkpoint_damage_and_resealed_wrong_pairs_refuse(tmp_path, defect):
    spec, point, _ = inputs()
    point = interval.advance(spec, point).checkpoint
    path = persistence.write_held_protein_checkpoint(tmp_path / "held", spec, point)
    if defect == "missing":
        (path / "manifest.json").unlink()
    elif defect == "bytes":
        with (path / "state.npz").open("ab") as handle:
            handle.write(b"damage")
    else:
        manifest = json.loads((path / "manifest.json").read_text())
        if defect == "clock":
            changed = interval._seal(replace(point, event_index=point.event_index + 1))
            manifest["checkpoint"] = interval.checkpoint_record(changed)
        elif defect == "state":
            amount = np.array(point.state.amount_increment, copy=True)
            amount[0, 0] += 0.001
            changed = interval._seal(
                replace(
                    point,
                    state=point.state._replace(amount_increment=amount),
                )
            )
            np.savez(path / "state.npz", **changed.state._asdict())
            manifest["checkpoint"] = interval.checkpoint_record(changed)
        elif defect == "component":
            changed = replace(point, component=replace(point.component, time_s=17.0))
            (path / "components.json").write_text(json.dumps(persistence._components(changed)))
        else:
            inner = json.loads((path / "seed/manifest.json").read_text())
            inner["runtime"]["python"] = "0.0.0"
            inner["manifest_sha256"] = digest(
                {k: v for k, v in inner.items() if k != "manifest_sha256"}
            )
            (path / "seed/manifest.json").write_text(json.dumps(inner))
        manifest["files"] = {
            name: hashlib.sha256((path / name).read_bytes()).hexdigest()
            for name in persistence.FILES
        }
        manifest["identity"] = digest({k: v for k, v in manifest.items() if k != "identity"})
        (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises((ValueError, OSError)):
        persistence.load_held_protein_checkpoint(path)


def test_prepare_save_restore_and_advance_never_draw_or_update_component(tmp_path, monkeypatch):
    spec, point, _ = inputs()

    def forbidden(*args, **kwargs):
        raise AssertionError("Held trajectory must not advance component or RNG")

    monkeypatch.setattr(component_step, "advance", forbidden)
    monkeypatch.setattr(streams, "draw", forbidden)
    result = interval.advance(spec, point)
    path = persistence.write_held_protein_checkpoint(tmp_path / "held", spec, result.checkpoint)
    loaded = persistence.load_held_protein_checkpoint(path)
    assert interval.checkpoint_record(loaded.checkpoint) == interval.checkpoint_record(
        result.checkpoint
    )
    with pytest.raises(ValueError):
        result.checkpoint.state.amount_increment.setflags(write=True)


def test_late_accounting_failure_retains_trial_and_no_endpoint(tmp_path, monkeypatch):
    spec, point, _ = inputs()
    original = interval._account
    calls = []

    def fail_late(*args):
        calls.append(args)
        if len(calls) == 3:
            raise ValueError("injected cumulative balance failure")
        return original(*args)

    monkeypatch.setattr(interval, "_account", fail_late)
    with pytest.raises(interval.HeldProteinRejected) as caught:
        interval.advance(spec, point)
    assert caught.value.stage == "cumulative_accounting"
    assert caught.value.trial is not None and caught.value.accounting.valid
    assert caught.value.source is point
    assert point.step_index == 0 and point.component.stream.next_tick == 31


def test_manifest_write_failure_leaves_uncommitted_payload(tmp_path, monkeypatch):
    spec, point, _ = inputs()
    original = persistence._write_json

    def interrupted(path, data):
        if path.name == "manifest.json":
            raise OSError("injected publication failure")
        return original(path, data)

    monkeypatch.setattr(persistence, "_write_json", interrupted)
    with pytest.raises(OSError):
        persistence.write_held_protein_checkpoint(tmp_path / "partial", spec, point)
    assert (tmp_path / "partial/state.npz").is_file()
    assert not (tmp_path / "partial/manifest.json").exists()
    with pytest.raises(OSError):
        persistence.load_held_protein_checkpoint(tmp_path / "partial")


def test_stage_energy_rate_refusal_retains_all_raw_stages(monkeypatch):
    spec, point, _ = inputs()
    original = interval.step.array_rk4_step

    def invalid_rate(*args, **kwargs):
        trial = original(*args, **kwargs)
        statuses = list(trial.status)
        statuses[2] = statuses[2]._replace(energy_rate_residual_pJ_s=np.asarray(2e-10))
        return trial._replace(status=tuple(statuses))

    monkeypatch.setattr(interval.step, "array_rk4_step", invalid_rate)
    with pytest.raises(interval.HeldProteinRejected) as caught:
        interval.advance(spec, point)
    assert caught.value.trial.valid
    assert len(caught.value.trial.stages) == 5
    assert caught.value.trial.status[2].energy_rate_residual_pJ_s == 2e-10
    assert caught.value.source is point


@pytest.mark.parametrize("end", (True, -1.0, 0.0))
def test_interval_cannot_skip_or_invent_grid_boundaries(end):
    spec, point, _ = inputs()
    with pytest.raises(interval.HeldProteinRejected) as caught:
        interval.advance(spec, point, end_time_s=end)
    assert caught.value.trial is None
