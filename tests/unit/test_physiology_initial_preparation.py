"""Initial shared tapes, actual physical admission, full restoration and first interval."""

import json
import math
import os
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells import physiology_initial_preparation_io as public
from cells.core import physiology_initial_preparation as core
from cells.core import physiology_tissue_step as tissue
from cells.core.specs import ConfigError, digest, parse_spec
from tests.unit.test_random_tissue_profile_preparation import compare_definition
from tests.unit.test_random_tissue_profile_preparation import request as profile_request
from validation.tissue import physiology_initial_preparation_reference as reference
from validation.tissue import physiology_tissue_step_reference as intervals

FAMILIES = ("passive", "ionic", "calcium", "fuel")


def evidence(name, value, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(directory) / "initial-physiology"
        root.mkdir(parents=True, exist_ok=True)
        with (root / (name + ".json")).open("x") as stream:
            json.dump(core._json(value), stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        if arrays is not None:
            np.savez_compressed(root / (name + ".npz"), **arrays)


def interval_arrays(point, checkpoint, trial, *, runtime_layout=None, held_control=None):
    """Archive actual parent/trial values, including invalid/nonfinite arrays."""
    arrays = {}
    for label, value in (
        ("source_state", checkpoint.state),
        ("source_layout", checkpoint.layout),
        ("protein", point.component.protein),
        ("diffusion", point.component.diffusion),
        ("runtime_layout", runtime_layout),
        ("held_control", held_control),
    ):
        if value is not None:
            arrays.update({label + "_" + k: np.asarray(v) for k, v in value._asdict().items()})
    if trial is not None:
        for label, values in (
            ("stage", trial.stages),
            ("derivative", trial.derivatives),
            ("status", trial.status),
        ):
            for i, value in enumerate(values):
                arrays.update(
                    {f"{label}{i}_{k}": np.asarray(v) for k, v in value._asdict().items()}
                )
    return arrays


def request(family="passive", *, reverse=False, level=0.2, profile="normal"):
    raw = profile_request(family, permuted=reverse)
    model = raw["definition"]["model"].get("ionic", raw["definition"]["model"])
    for row in model["extracellular"]:
        row["volume_pL"] = 4.0
    h = 6.25e-6 if family == "passive" else 1.953125e-8
    raw["definition"]["execution"]["dt"] = h
    raw["definition"]["execution"]["max_steps"] = max(
        raw["definition"]["execution"]["max_steps"],
        math.ceil(raw["definition"]["experiment"]["end_time"] / h) + 100,
    )
    raw["definition"] = parse_spec(raw["definition"]).to_dict()
    axes = raw["geometry"]["layout"]
    ions = [row["id"] for row in model["species"]]
    if reverse:
        ions.reverse()
    controls = dict(
        phase="INIT" if profile == "INIT" else "SIM",
        solver="fast" if profile == "fast" else "normal",
        dynamic_enabled=profile != "dynamic-off",
        protein_enabled=profile != "protein-off",
        static_level=level,
        dynamic_level_mol_m2_s=1e-9,
        dt_s=16 * h,
    )
    protein = {
        kind: {name: 0.01 * (i + 1) for i, name in enumerate(axes[kind + "_ids"])}
        for kind in ("cell", "membrane", "environment")
    }
    return dict(
        schema_version=1,
        kind=core.REQUEST_KIND,
        preparation=raw,
        component=dict(
            controls=controls,
            protein_mol_m3=protein,
            ion_ids=ions,
            boundary_cell_occurrences=[
                axes["cell_ids"][-1],
                axes["cell_ids"][0],
                axes["cell_ids"][-1],
            ],
            provenance={"source": "Explicit manufactured initialization owners"},
            stream_id="component-after-selection",
            next_tick=23,
        ),
    )


def compare(raw, actual):
    expected = reference.evaluate(raw, actual.spec.to_dict())
    compare_definition(actual.spec.to_dict(), expected["selection"]["physical"]["definition"])
    component = actual.component
    assert (
        core._json(core.perturb.native_stream_manifest(component.stream.rng)["state"])
        == expected["numpy_successor"]
    )
    assert actual.provenance["parked_python"]["state"] == expected["python_successor"]
    assert (
        actual.provenance["source_component_stream"]["rng"]["state"]
        == expected["selection"]["native"]["numpy_state"]
    )
    for name in ("base_m2_s", "current_m2_s", "scheduled_m2_s"):
        np.testing.assert_array_equal(getattr(component.diffusion, name), expected[name])
    np.testing.assert_allclose(
        component.diffusion.current_m2_s,
        expected["independent_current_m2_s"],
        rtol=5e-14,
        atol=1e-30,
    )
    assert component.stream.next_tick == 24 and component.time_s == 0 and component.loop_calls == 0
    assert actual.checkpoint.time == 0 and actual.checkpoint.step_index == 0
    assert actual.binding.component.cell_ids == tuple(
        raw["preparation"]["geometry"]["layout"]["cell_ids"]
    )
    fields = actual.checkpoint.state._asdict()
    context, expected_rate, phi, proof = reference.physical.evaluate(
        actual.spec.to_dict(),
        fields,
        core.units.binding_record(actual.binding),
        component.diffusion.current_m2_s,
    )
    oracle = reference.physical.ORACLES[actual.spec.to_dict()["model"]["id"]]
    target = actual.provenance["physical_admission"]
    observed = oracle.flatten(context, target["derivative"])
    atol = oracle.flatten(
        context,
        {k: np.full(s, 3e-23 if k.endswith("_C") else 3e-12) for k, s in context["shapes"].items()},
    )
    ratio = float(np.max(np.abs(observed - expected_rate) / (atol + 3e-10 * np.abs(expected_rate))))
    p = actual.checkpoint.layout
    potential = np.asarray(target["potential_V"])
    potential = np.r_[
        potential[: p.active.size][p.active], potential[p.active.size :][p.outside_active]
    ]
    phi_ratio = float(np.max(np.abs(potential - phi) / (3e-13 + 3e-10 * np.abs(phi))))
    assert ratio <= 1 and phi_ratio <= 1 and abs(target["energy_rate_residual_pJ_s"]) <= 1e-10
    return dict(
        reference=expected,
        fields=fields,
        binding=core.units.binding_record(actual.binding),
        independent_rate=expected_rate,
        independent_potential_V=phi,
        independent_proof=proof,
        actual_rate=observed,
        actual_potential_V=potential,
        rate_atol=atol,
        max_rate_error_over_budget=ratio,
        max_potential_error_over_budget=phi_ratio,
    )


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("reverse,level", ((False, 0.0), (True, 0.2)))
def test_selected_native_successor_full_static_initialization_and_physical_RHS(
    family, reverse, level
):
    raw = request(family, reverse=reverse, level=level)
    before = deepcopy(raw)
    actual = core.initialize(raw)
    core.validate(actual)
    expected = compare(raw, actual)
    assert raw == before
    assert core.replay(actual.provenance).provenance == actual.provenance
    evidence(
        f"initial-{family}-{reverse}",
        dict(
            request=raw,
            provenance=actual.provenance,
            comparison=expected,
            physical_time_elapsed_s=0.0,
            additional_biological_cases=0,
        ),
    )


@pytest.mark.parametrize("profile", ("INIT", "fast", "dynamic-off", "protein-off"))
def test_static_draw_ignores_dynamic_guards(profile):
    raw = request(profile=profile, level=0.0)
    result = core.initialize(raw)
    expected = compare(raw, result)
    np.testing.assert_array_equal(
        result.component.diffusion.current_m2_s, result.component.diffusion.base_m2_s
    )
    evidence(
        "guard-" + profile, dict(request=raw, provenance=result.provenance, comparison=expected)
    )


@pytest.mark.parametrize("family", FAMILIES)
def test_initialized_pair_advances_an_original_interval_with_independent_refinement(family):
    raw = request(family, reverse=True, profile="INIT")
    original_execution = deepcopy(raw["preparation"]["definition"]["execution"])
    horizon = original_execution["dt"]
    # Fixed-horizon diagnostics found a fast extracellular capacitive mode in
    # the passive 4-pL geometry. Declare the finer original grid before binding;
    # every endpoint must pass the unchanged physical and energy acceptance.
    substeps = 256 if family == "passive" else 1
    raw["preparation"]["definition"]["execution"]["dt"] /= substeps
    raw["preparation"]["definition"]["execution"]["max_steps"] *= substeps
    point = core.initialize(raw)
    initial_record = deepcopy(point.provenance)
    reference_definition = point.spec.to_dict()
    reference_definition["execution"] = original_execution
    reference_binding = core.units.binding_record(
        core._inputs(raw, parse_spec(reference_definition))[0]
    )
    production_binding = core.units.binding_record(point.binding)
    source_dependent = {"identity", "source_definition_sha256", "component_identity"}
    assert {k: v for k, v in reference_binding.items() if k not in source_dependent} == {
        k: v for k, v in production_binding.items() if k not in source_dependent
    }
    # Both independent paths span the complete original coarse interval, from
    # the same initial state. Neither starts from a production endpoint.
    checkpoint, accepted = point.checkpoint, []
    for i in range(substeps):
        last_source = checkpoint
        try:
            actual = tissue.advance(point.spec, checkpoint, point.binding, point.component)
        except tissue.TissueStepRejected as error:
            evidence(
                f"failed-interval-{family}-{i}",
                dict(
                    request=raw,
                    provenance=point.provenance,
                    reference_definition=reference_definition,
                    reference_binding=reference_binding,
                    failure=str(error),
                    failure_stage=error.stage,
                    source_time_s=checkpoint.time,
                    source_step_index=checkpoint.step_index,
                    source_event_index=checkpoint.event_index,
                    diagnostics=dict(error.diagnostics),
                    accepted_prefix=accepted,
                    automatic_retry=False,
                ),
                interval_arrays(
                    point,
                    checkpoint,
                    error.trial,
                    runtime_layout=error.runtime_layout,
                    held_control=error.held_control,
                ),
            )
            raise
        accepted.append(
            dict(
                time_s=actual.checkpoint.time,
                step_index=actual.checkpoint.step_index,
                event_index=actual.checkpoint.event_index,
                state=actual.checkpoint.state._asdict(),
                ordinary_balance_checks=dict(actual.admission["ordinary_balance_checks"]),
                runtime_balance_checks=dict(actual.admission["runtime_balance_checks"]),
                stage_status=[value._asdict() for value in actual.trial.status],
            )
        )
        checkpoint = actual.checkpoint
    assert checkpoint.time == horizon and checkpoint.step_index == substeps
    # Seal the accepted production prefix before independent reference work.
    # A later reference refusal must not discard the actual trajectory.
    evidence(
        "accepted-prefix-" + family,
        dict(
            request=raw,
            provenance=point.provenance,
            reference_definition=reference_definition,
            reference_binding=reference_binding,
            production_substeps=substeps,
            original_interval_s=horizon,
            accepted=accepted,
            reference_comparison_complete=False,
        ),
        interval_arrays(point, last_source, actual.trial),
    )
    traces = [
        intervals.integrate(
            reference_definition,
            point.checkpoint.state._asdict(),
            reference_binding,
            point.component.diffusion.current_m2_s,
            start_time_s=0.0,
            end_time_s=actual.checkpoint.time,
            refinement=refinement,
        )
        for refinement in (1, 2)
    ]
    oracle = reference.physical.ORACLES[point.spec.to_dict()["model"]["id"]]
    context = traces[1]["context"]
    observed = oracle.flatten(context, actual.checkpoint.state._asdict())
    atol = oracle.flatten(
        context,
        {k: np.full(s, 3e-23 if k.endswith("_C") else 3e-12) for k, s in context["shapes"].items()},
    )
    budget = atol + 3e-10 * np.abs(traces[1]["state"])
    error = float(np.max(np.abs(observed - traces[1]["state"]) / budget))
    uncertainty = float(np.max(np.abs(traces[0]["state"] - traces[1]["state"]) / budget))
    table = core.control_values(point.spec, [actual.checkpoint.time])
    held = type(table)(*(value[0] for value in table))
    endpoint = core.view.evaluate(
        point.spec,
        actual.checkpoint.state,
        actual.checkpoint.layout,
        held,
        point.binding,
        point.component,
        step_s=point.spec.execution.dt,
    )
    p = actual.checkpoint.layout
    potential = np.r_[
        endpoint.field.potential_V[: p.active.size][p.active],
        endpoint.field.potential_V[p.active.size :][p.outside_active],
    ]
    phi_budget = 3e-13 + 3e-10 * np.abs(traces[1]["endpoint_potential_V"])
    phi_error = float(np.max(np.abs(potential - traces[1]["endpoint_potential_V"]) / phi_budget))
    phi_uncertainty = float(
        np.max(
            np.abs(traces[0]["endpoint_potential_V"] - traces[1]["endpoint_potential_V"])
            / phi_budget
        )
    )
    assert point.provenance == initial_record
    assert actual.component is point.component
    evidence(
        "interval-" + family,
        dict(
            request=raw,
            provenance=point.provenance,
            reference_definition=reference_definition,
            reference_binding=reference_binding,
            production_substeps=substeps,
            original_interval_s=horizon,
            accepted=accepted,
            initial_fields=point.checkpoint.state._asdict(),
            observed_fields=actual.checkpoint.state._asdict(),
            observed=observed,
            state_atol=atol,
            end_time_s=actual.checkpoint.time,
            references=[{k: v for k, v in trace.items() if k != "context"} for trace in traces],
            error_over_budget=error,
            reference_uncertainty_fraction=uncertainty,
            observed_potential_V=potential,
            potential_error_over_budget=phi_error,
            potential_reference_uncertainty_fraction=phi_uncertainty,
            component_and_tape_held=True,
        ),
    )
    assert error <= 1 and uncertainty <= 0.1
    assert phi_error <= 1 and phi_uncertainty <= 0.1


def test_load_restores_full_pair_with_all_initialization_and_draw_calls_forbidden(
    tmp_path, monkeypatch
):
    value = core.initialize(request("fuel", reverse=True))
    root = public.write_initialization(tmp_path / "initial", value)

    def forbidden(*args, **kwargs):
        raise AssertionError("Restore must not prepare, initialize or draw")

    for module, name in (
        (core, "initialize"),
        (core, "replay"),
        (core.profiles, "prepare"),
        (core.streams, "draw"),
        (core.step, "initialise"),
        (core.perturb, "sample_native"),
        (core.perturb, "sample_stable"),
    ):
        monkeypatch.setattr(module, name, forbidden)
    loaded = public.load_initialization(root)
    assert loaded.provenance == value.provenance
    assert core._arrays(loaded.checkpoint) == core._arrays(value.checkpoint)
    assert core.streams.stream_record(loaded.component.stream) == core.streams.stream_record(
        value.component.stream
    )
    evidence("draw-free-load", dict(bundle=str(root), exact_full_restore=True, draws=0))


@pytest.mark.parametrize("fault", ("counter", "negative-static", "physical"))
def test_late_refusal_retains_selection_and_full_proposed_component(fault):
    raw = request()
    if fault == "counter":
        raw["component"]["next_tick"] = 2**64 - 1
    else:
        raw["component"]["controls"]["static_level"] = -10.0 if fault == "negative-static" else 1e12
    original = deepcopy(raw)
    with pytest.raises(core.InitializationRejected) as failed:
        core.initialize(raw)
    error = failed.value
    assert error.preparation is not None and raw == original
    assert error.source_stream.rng == error.preparation.stream.numpy
    if fault != "counter":
        assert error.proposed_stream.next_tick == raw["component"]["next_tick"] + 1
        assert error.component_trial is not None
    arrays = None
    if error.component_trial is not None:
        arrays = {
            group + "." + name: value
            for group in ("protein", "diffusion")
            for name, value in getattr(error.component_trial, group)._asdict().items()
        }
    if error.checkpoint is not None:
        arrays.update(
            {
                group + "." + name: value
                for group in ("state", "layout")
                for name, value in getattr(error.checkpoint, group)._asdict().items()
            }
        )
    evidence(
        "refusal-" + fault,
        dict(
            request=raw,
            stage=error.stage,
            error=str(error),
            preparation=error.preparation.provenance,
            source_stream=core.streams.stream_record(error.source_stream),
            proposed_stream=core.streams.stream_record(error.proposed_stream),
            trial_time_s=None if error.component_trial is None else error.component_trial.time_s,
            trial_loop_calls=None
            if error.component_trial is None
            else error.component_trial.loop_calls,
            packet=None
            if error.packet is None
            else core.perturb.draw_manifest(
                error.packet,
                core._inputs(raw, parse_spec(error.preparation.definition))[0].component,
            ),
            parent_unchanged=True,
        ),
        arrays=arrays,
    )


@pytest.mark.parametrize("fault", ("owner", "protein", "ion", "extra", "source"))
def test_invalid_declarations_refuse_without_modifying_input(fault):
    raw = request()
    if fault == "owner":
        raw["component"]["boundary_cell_occurrences"].append("foreign")
    elif fault == "protein":
        raw["component"]["protein_mol_m3"]["cell"]["foreign"] = 1.0
    elif fault == "ion":
        raw["component"]["ion_ids"].append("ATP")
    elif fault == "extra":
        raw["extra"] = True
    else:
        raw["preparation"]["world_id"] += 1
    before = deepcopy(raw)
    with pytest.raises(ConfigError):
        core.initialize(raw)
    assert raw == before


@pytest.mark.parametrize(
    "fault",
    (
        "clock",
        "component",
        "binding",
        "recipe",
        "historical-source",
        "static-source",
        "static-result",
    ),
)
def test_modified_initial_association_refuses(fault):
    value = core.initialize(request())
    if fault == "clock":
        value = replace(value, checkpoint=replace(value.checkpoint, time=1e-9))
    elif fault == "component":
        value = replace(value, component=replace(value.component, time_s=1e-9))
    elif fault == "binding":
        value = replace(value, binding=replace(value.binding, identity="0" * 64))
    else:
        p = deepcopy(value.provenance)

        def seal(record):
            record["identity"] = digest({k: v for k, v in record.items() if k != "identity"})

        if fault == "recipe":
            p["source_component_stream"]["next_tick"] += 1
        elif fault == "historical-source":
            source = p["preparation"]["selection"]["source"]
            source["next_call"] += 1
            seal(source)
            seal(p["preparation"]["selection"])
            seal(p["preparation"])
        else:
            static = p["preparation"]["static_preparation"]
            if fault == "static-source":
                static["source_definition"]["model"]["cells"][0]["volume_pL"] *= 1.1
                static["source_definition_sha256"] = digest(static["source_definition"])
            else:
                static["prepared_definition_sha256"] = "0" * 64
            seal(static)
            seal(p["preparation"])
        p["identity"] = digest({k: v for k, v in p.items() if k != "identity"})
        value = replace(value, provenance=p)
    with pytest.raises((ConfigError, ValueError)):
        core.validate(value)


def test_publication_failure_is_retained_and_parent_directory_unchanged(tmp_path, monkeypatch):
    value = core.initialize(request())
    parent = public.write_initialization(tmp_path / "parent", value)
    before = {str(p.relative_to(parent)): p.read_bytes() for p in parent.rglob("*") if p.is_file()}
    with pytest.raises(FileExistsError):
        public.write_initialization(parent, value)
    original = public.paired._write_json

    def fail(path, payload):
        if path.name == "initialization.json":
            raise OSError("injected publication failure")
        original(path, payload)

    monkeypatch.setattr(public.paired, "_write_json", fail)
    failed = tmp_path / "failed"
    with pytest.raises(OSError):
        public.write_initialization(failed, value)
    assert (failed / "failure.json").exists() and not (failed / "manifest.json").exists()
    with pytest.raises(ConfigError):
        public.load_initialization(failed)
    assert before == {
        str(p.relative_to(parent)): p.read_bytes() for p in parent.rglob("*") if p.is_file()
    }
    evidence(
        "publication-refusal",
        dict(
            failed_bundle=str(failed),
            parent_bundle=str(parent),
            parent_unchanged=True,
            injected=True,
        ),
    )


@pytest.mark.parametrize("fault", ("numeric", "initialization", "extra", "source"))
def test_corrupt_public_bundle_refuses(tmp_path, monkeypatch, fault):
    root = public.write_initialization(tmp_path / "initial", core.initialize(request()))
    if fault == "numeric":
        path = root / "physiology/snapshot/state.npz"
        path.write_bytes(path.read_bytes() + b"changed")
    elif fault == "initialization":
        path = root / "initialization.json"
        raw = json.loads(path.read_text())
        raw["active_stream"]["next_tick"] += 1
        path.write_text(json.dumps(raw))
    elif fault == "extra":
        (root / "extra.json").write_text("{}")
    else:
        monkeypatch.setattr(public, "source_hashes", lambda: {"changed": "source"})
    with pytest.raises(ConfigError):
        public.load_initialization(root)


def test_fresh_public_prepare_load_and_explicit_private_replay(tmp_path):
    raw = request("calcium", reverse=True)
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(raw))
    a, b = tmp_path / "initial", tmp_path / "replayed"
    commands = [
        ["prepare", str(request_path), "--output", str(a)],
        ["validate", str(a)],
        ["replay", str(a / "initialization.json"), "--output", str(b)],
    ]
    outputs = []
    for arguments in commands:
        process = subprocess.run(
            [sys.executable, "-B", "-m", "cells.physiology_initial_preparation_io", *arguments],
            text=True,
            capture_output=True,
            timeout=90,
        )
        outputs.append(
            dict(
                arguments=arguments,
                returncode=process.returncode,
                stdout=process.stdout,
                stderr=process.stderr,
            )
        )
        assert process.returncode == 0, process.stderr
    assert public.load_initialization(a).provenance == public.load_initialization(b).provenance
    evidence("public-cli", dict(request=raw, processes=outputs, bundles=[str(a), str(b)]))
