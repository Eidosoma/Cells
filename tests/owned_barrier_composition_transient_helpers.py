"""Complete static-barrier histories, independent targets and durable failures."""

import argparse
import hashlib
import json
import time
import traceback
from copy import deepcopy
from pathlib import Path

import numpy as np

from validation.transport import environment_barrier_composition_transient_fixtures as fixtures
from validation.transport import environment_barrier_composition_transient_reference as reference


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    with Path(path).open() as stream:
        return json.load(stream)


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, allow_nan=False, default=lambda v: v.tolist()) + "\n"
    )


def save(stem, record, arrays):
    stem.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(stem.with_suffix(".npz"), **arrays)
    write(stem.with_suffix(".json"), dict(record, arrays_sha256=sha(stem.with_suffix(".npz"))))


def load(stem):
    meta = read(stem.with_suffix(".json"))
    assert meta["status"] == "completed"
    assert sha(stem.with_suffix(".npz")) == meta["arrays_sha256"]
    with np.load(stem.with_suffix(".npz"), allow_pickle=False) as handle:
        arrays = {k: handle[k].copy() for k in handle.files}
    return meta, arrays


def prepare_inputs(bundle):
    from cells.core import environment_barrier_composition_preparation as bridge
    from cells.core.specs import parse_spec
    from validation.transport import environment_barrier_composition_fixtures as coefficients

    records = {}
    for dataset in fixtures.DATASETS:
        values = fixtures.inputs(dataset)
        source, request = values["source_request"], values["request"]
        fixtures.assert_same_physics_and_control_history(
            source["definition"], request["definition"]
        )
        prepared = bridge.prepare(request)
        # Canonical owner ordering is shared input data, not shared equations.
        canonical = deepcopy(request)
        canonical["definition"] = parse_spec(request["definition"]).to_dict()
        independent, maps = coefficients.independent_coefficients(canonical)
        production = deepcopy(prepared.definition)
        actual_faces = {v["id"]: v for v in production["model"]["ionic"]["faces"]}
        for face in independent["model"]["ionic"]["faces"]:
            actual = actual_faces[face["id"]]
            for species, value in face["diffusivity_m2_per_s"].items():
                np.testing.assert_allclose(
                    actual["diffusivity_m2_per_s"][species], value, rtol=5e-14, atol=0
                )
            actual["diffusivity_m2_per_s"] = face["diffusivity_m2_per_s"]
        assert production == independent
        rows = {
            "source-request": source,
            "request": request,
            "production": prepared.definition,
            "independent": independent,
            "provenance": prepared.provenance,
            "independent-coefficients": maps,
        }
        records[dataset] = {}
        for role, row in rows.items():
            path = bundle / "inputs" / f"{dataset}-{role}.json"
            write(path, row)
            records[dataset][role] = dict(path=str(path.relative_to(bundle)), sha256=sha(path))
    write(bundle / "input-manifest.json", records)
    return records


def input_raw(bundle, dataset, role):
    record = read(bundle / "input-manifest.json")[dataset][role]
    path = bundle / record["path"]
    assert sha(path) == record["sha256"]
    return read(path)


def location(output, dataset, role, factor):
    return output / "evidence" / dataset / f"{role}-{factor}"


def run_reference(bundle, output, dataset, factor):
    raw = input_raw(bundle, dataset, "independent")
    began = time.monotonic()
    result = reference.integrate(raw, refinement=factor)
    equation, context = reference.bind(raw)
    states, times = result["state"], np.asarray(result["times"])
    try:
        ledgers = [
            reference.conservation(equation, context, y, t)
            for t, y in zip(times, states, strict=True)
        ]
        maxima = reference.assert_conservation(ledgers)
    except Exception as error:
        save(
            location(output, dataset, "reference-accounting-failure", factor),
            dict(status="failed", error=str(error), inputs=raw),
            dict(times_s=times, state_flat=states, potential_V=result["potential_V"]),
        )
        raise
    save(
        location(output, dataset, "reference", factor),
        dict(
            status="completed",
            dataset=dataset,
            factor=factor,
            elapsed_seconds=time.monotonic() - began,
            proof={k: v for k, v in result.items() if k not in ("state", "potential_V")},
            conservation=ledgers,
            maximum_conservation_errors=maxima,
            state_fields=list(context["shapes"]),
            original_full_horizon_s=raw["experiment"]["end_time"],
        ),
        dict(
            times_s=times,
            state_flat=states,
            potential_V=result["potential_V"],
            initial_flat=equation.initial(context),
            reference_shapes_json=np.asarray(json.dumps(context["shapes"])),
        ),
    )


def run_production(bundle, output, dataset, factor):
    from cells.core.grid import EventGrid
    from cells.core.schedule import control_values
    from cells.core.specs import parse_spec
    from cells.models.registry import get_model
    from cells.numerics.fixed_step import rk4_step

    raw = input_raw(bundle, dataset, "production")
    raw["execution"]["dt"] /= factor
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, layout = model.initial_values(spec)
    assert len(state) == (43 if dataset.startswith("water-") else 48)
    assert set(layout.channel_laws[layout.channel_active]) == set(range(56))
    times = np.asarray(list(EventGrid(spec)))
    assert len(times) - 1 <= spec.execution.max_steps
    table = control_values(spec, times[:-1])
    model.check_steps(spec, np.diff(times), table)
    values = [state]
    began = time.monotonic()
    stem = location(output, dataset, "production", factor)
    try:
        for i, step in enumerate(np.diff(times)):
            control = type(table)(*(v[i] for v in table))
            state = rk4_step(
                lambda y, *args: model.rhs(y, *args, xp=np),
                state,
                step,
                control,
                layout,
                layout.active,
            )
            values.append(state)
            if not model.domain_valid(state, layout, layout.active, xp=np):
                raise ValueError(f"Invalid accepted state at {times[i + 1]:.17g} s")
        history = model.STATE_TYPE(*(np.stack(v) for v in zip(*values, strict=True)))
        diagnostics = model.check_values(history, spec)
        requested = np.asarray(raw["experiment"]["observation_times"])
        indices = [EventGrid(spec).exact_index(t) for t in requested]
        assert set(fixtures.event_times(raw)) <= set(requested)
        observed = model.observe_history(times, history, layout, requested, spec)
        equation, context = reference.bind(input_raw(bundle, dataset, "independent"))
        flat = np.stack(
            [
                equation.flatten(context, model.STATE_TYPE(*(v[i] for v in history))._asdict())
                for i in indices
            ]
        )
        arrays = dict(
            times_s=requested,
            integration_times_s=times,
            state_flat=flat,
            state_fields=np.asarray(state._fields),
            initial_flat=equation.flatten(context, values[0]._asdict()),
        )
        for key in state._fields:
            np.testing.assert_array_equal(getattr(observed, key), getattr(history, key)[indices])
            arrays[key] = getattr(history, key)[indices]
            arrays["grid__" + key] = getattr(history, key)
        arrays.update({"obs__" + k: np.asarray(v) for k, v in vars(observed).items()})
        arrays.update({"layout__" + k: v for k, v in zip(layout._fields, layout, strict=True)})
        arrays.update({"control__" + k: v for k, v in zip(table._fields, table, strict=True)})
        zero_faces = layout.face_factor == 0
        assert not np.any(history.face_transferred[:, zero_faces])
        assert np.any(history.face_transferred[-1] != 0)
        assert np.any(history.volume_increment_pL[-1] != 0)
        assert np.any(history.energy_amount_increment_fmol[-1] != 0)
        n = layout.active.size
        potential = np.c_[
            observed.cell_potential_V[:, layout.active],
            observed.extracellular_potential_V[:, layout.outside_active],
        ]
        proofs = []
        for t, vector, phi in zip(requested, flat, potential, strict=True):
            _, independent_phi, proof = equation.evaluate(context, vector, float(t))
            np.testing.assert_allclose(phi, independent_phi, rtol=3e-10, atol=3e-13)
            assert proof["max_charge_residual_C"] <= 3e-25
            assert proof["max_component_current_residual_A"] <= 1e-23
            assert abs(proof["physical_energy_balance_pJ_s"]) <= 1e-10
            proofs.append(proof)
        arrays["potential_V"] = potential
        assert np.array_equal(
            observed.cell_volume_pL, layout.volume + history.volume_increment_pL[indices]
        )
        assert np.array_equal(
            observed.extracellular_volume_pL,
            layout.extracellular_volume + history.extracellular_volume_increment_pL[indices],
        )
        assert n == len(context["cell_ids"])
        save(
            stem,
            dict(
                status="completed",
                dataset=dataset,
                factor=factor,
                dt_s=spec.execution.dt,
                integration_steps=len(times) - 1,
                observation_count=len(requested),
                diagnostics=diagnostics,
                elapsed_seconds=time.monotonic() - began,
                control_boundaries_s=fixtures.event_times(raw),
                complete_physical_fields=len(state),
                no_op_carriers_only=True,
                original_full_horizon_s=spec.experiment.end_time,
                evolved_stage_proofs=proofs,
            ),
            arrays,
        )
    except Exception as error:
        failed = stem.with_name(stem.name + "-failure")
        save(
            failed,
            dict(
                status="failed",
                error=str(error),
                traceback=traceback.format_exc(),
                elapsed_seconds=time.monotonic() - began,
                inputs=raw,
            ),
            dict(
                integration_times_s=times[: len(values)],
                **{k: np.stack([getattr(v, k) for v in values]) for k in model.STATE_TYPE._fields},
            ),
        )
        raise


def budget(equation, context, expected):
    floors = {
        k: np.full(shape, 3e-25 if k.endswith("_C") else 2e-11)
        for k, shape in context["shapes"].items()
    }
    return equation.flatten(context, floors) + 3e-9 * np.abs(expected)


def comparison(bundle, output, dataset):
    coarse_meta, coarse_ref = load(location(output, dataset, "reference", 1))
    fine_meta, exact = load(location(output, dataset, "reference", 2))
    raw = input_raw(bundle, dataset, "independent")
    equation, context = reference.bind(raw)
    expected, times = exact["state_flat"], exact["times_s"]
    np.testing.assert_array_equal(coarse_ref["times_s"], times)
    bounds = budget(equation, context, expected)
    uncertainty = float(np.max(np.abs(coarse_ref["state_flat"] - expected) / bounds, initial=0))
    assert uncertainty <= 0.1, ("reference refinement unresolved", uncertainty)
    rows = []
    arrays = dict(
        times_s=times,
        reference_flat=expected,
        coarse_reference_flat=coarse_ref["state_flat"],
        budget=bounds,
    )
    for factor in (1, 2):
        meta, data = load(location(output, dataset, "production", factor))
        np.testing.assert_array_equal(data["times_s"], times)
        np.testing.assert_array_equal(data["initial_flat"], exact["initial_flat"])
        actual = data["state_flat"]
        error = actual - expected
        ratio = float(np.max(np.abs(error) / bounds, initial=0))
        ledgers = [
            reference.conservation(equation, context, v, t)
            for t, v in zip(times, actual, strict=True)
        ]
        maxima = reference.assert_conservation(ledgers)
        row = dict(
            factor=factor,
            dt_s=meta["dt_s"],
            error_over_budget=ratio,
            maximum_absolute_error=float(np.max(np.abs(error), initial=0)),
            independent_conservation=maxima,
            production_diagnostics=meta["diagnostics"],
        )
        rows.append(row)
        arrays[f"production_flat_{factor}"] = actual
        arrays[f"potential_V_{factor}"] = data["potential_V"]
        arrays.update({f"{factor}__" + k: data[k] for k in data["state_fields"].tolist()})
        save(
            output / "evidence" / dataset / "comparison-progress",
            dict(status="incomplete", refinements=rows),
            arrays,
        )
        assert ratio <= 1, (dataset, factor, ratio)
    high, low = [r["maximum_absolute_error"] for r in rows]
    assert low <= max(0.3 * high, 3e-13), ("unchanged parent refinement criterion", high, low)
    save(
        output / "evidence" / dataset / "comparison",
        dict(
            status="passed",
            dataset=dataset,
            complete_physical_fields=len(context["shapes"]),
            independent_biological_cases=0,
            manufactured_conditions=1,
            numerical_resolutions=2,
            original_full_horizon_s=raw["experiment"]["end_time"],
            all_observations_and_control_boundaries=True,
            observation_count=len(times),
            reference_uncertainty_over_trajectory_budget=uncertainty,
            reference_refinements=[coarse_meta["proof"], fine_meta["proof"]],
            refinements=rows,
            refinement_mode="precision_floor" if max(high, low) <= 3e-13 else "resolved_reduction",
            convergence_order_claim=False,
            native_full_loop_claim=False,
            fixed_geometry_live_volume=True,
            padding_and_permutation_scope="retained separate initial-stage contracts",
        ),
        arrays,
    )


def qualify(bundle, output, dataset):
    output = Path(output)
    log = output / "evidence" / dataset / "progress.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    for role, function in (("reference", run_reference), ("production", run_production)):
        for factor in (1, 2):
            began = time.monotonic()
            with log.open("a") as handle:
                handle.write(json.dumps(dict(event="start", role=role, factor=factor)) + "\n")
            try:
                function(bundle, output, dataset, factor)
            except Exception as error:
                details = getattr(error, "diagnostics", {})
                write(
                    location(output, dataset, role + "-exception", factor).with_suffix(".json"),
                    dict(
                        status="failed",
                        error=str(error),
                        traceback=traceback.format_exc(),
                        details=details,
                    ),
                )
                raise
            with log.open("a") as handle:
                handle.write(
                    json.dumps(
                        dict(
                            event="complete",
                            role=role,
                            factor=factor,
                            elapsed_seconds=time.monotonic() - began,
                        )
                    )
                    + "\n"
                )
    comparison(bundle, output, dataset)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    if args.prepare:
        prepare_inputs(args.bundle)


if __name__ == "__main__":
    main()
