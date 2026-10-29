"""Frozen execution and retained artifacts for complete INIT/SIM refinements."""

import argparse
import hashlib
import json
import traceback
from pathlib import Path

import numpy as np

from cells.core import joint_water_profile_phase_handoff as bridge
from cells.core import surface_calcium_energy_water_profile_epoch_spec as water_epoch_spec
from cells.core import surface_calcium_energy_water_profile_interventions_spec as water_spec
from cells.core import surface_calcium_energy_water_repair_profile_epoch_spec as repair_epoch_spec
from cells.core import surface_calcium_energy_water_repair_profile_interventions_spec as repair_spec
from cells.core.grid import EventGrid
from cells.core.schedule import control_values, event_index
from cells.core.state import Checkpoint
from cells.models import surface_calcium_energy_water_profile_epoch as water_epoch
from cells.models import surface_calcium_energy_water_profile_interventions as water
from cells.models import surface_calcium_energy_water_repair_profile_epoch as repair_epoch
from cells.models import surface_calcium_energy_water_repair_profile_interventions as repair
from cells.numerics.fixed_step import rk4_step
from validation.topology import joint_water_epoch_transient_fixtures as fixtures
from validation.topology import joint_water_epoch_transient_reference as reference

OWNERS = {
    "water": (water_spec, water, water_epoch_spec, water_epoch),
    "repair": (repair_spec, repair, repair_epoch_spec, repair_epoch),
}


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, allow_nan=False, default=lambda v: v.tolist()) + "\n"
    )


def parts(dataset):
    if dataset not in fixtures.DATASETS:
        raise ValueError(dataset)
    phase, family, *tail = dataset.split("-")
    return phase, family, "-".join(tail)


def input_raw(bundle, dataset):
    return read(bundle / "inputs" / (dataset + ".json"))


def location(output, dataset, role, factor=None):
    suffix = role + ("-" + str(factor) if factor is not None else "")
    return output / "evidence" / dataset / suffix


def completed(output, dataset, role, factor=None):
    path = location(output, dataset, role, factor)
    meta = read(path.with_suffix(".json"))
    assert meta["status"] == "completed"
    assert sha(path.with_suffix(".npz")) == meta["arrays_sha256"]
    with np.load(path.with_suffix(".npz"), allow_pickle=False) as data:
        arrays = {k: data[k].copy() for k in data.files}
    return meta, arrays


def save_unit(output, dataset, role, factor, meta, arrays):
    path = location(output, dataset, role, factor)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path.with_suffix(".npz"), **arrays)
    write(
        path.with_suffix(".json"),
        dict(
            meta,
            status="completed",
            arrays_sha256=sha(path.with_suffix(".npz")),
            dataset=dataset,
            role=role,
            factor=factor,
        ),
    )


def run_reference(bundle, output, dataset):
    phase, family, _ = parts(dataset)
    raw = input_raw(bundle, dataset)
    initial = None
    dependency = None
    if phase == "SIM":
        dependency, data = completed(output, "INIT-" + family, "reference")
        initial = data["state_flat"][-1].copy()
        initial[-1] = 0.0
    times, states, proof = reference.integrate(raw, initial)
    context = reference.scheduled.bind(raw)
    save_unit(
        output,
        dataset,
        "reference",
        None,
        dict(
            inputs=raw,
            input_sha256=sha(bundle / "inputs" / (dataset + ".json")),
            proof=proof,
            initial_dependency=dependency,
        ),
        dict(
            times_s=times,
            state_flat=states,
            initial_flat=reference.scheduled.initial(context) if initial is None else initial,
            reference_shapes_json=np.asarray(json.dumps(context["parent"]["shapes"])),
        ),
    )


def table_control(table, index):
    return type(table)(*(v[index] for v in table))


def run_production(bundle, output, dataset, factor):
    phase, family, _ = parts(dataset)
    schema, ordinary, epoch_schema, epoch = OWNERS[family]
    raw = input_raw(bundle, dataset)
    raw["execution"]["dt"] /= factor
    preparation = None
    source_meta = None
    if phase == "INIT":
        spec = schema.parse(raw)
        model = ordinary
    else:
        source_meta, _ = completed(output, "INIT-" + family, "production", factor)
        request = dict(
            kind=bridge.REQUEST_KIND,
            policies=epoch_schema.POLICIES,
            source=source_meta["source_record"],
            simulation=raw,
        )
        preparation = bridge.prepare(request)
        spec = epoch_schema.parse(preparation.definition)
        model = epoch
    state, p = model.initial_values(spec)
    for key, rows in (
        ("capacity", spec.model.cells),
        ("extracellular_capacity", spec.model.extracellular),
        ("membrane_capacity", spec.model.membranes),
        ("edge_capacity", spec.model.junctions),
        ("face_capacity", spec.model.faces),
        ("channel_capacity", spec.model.channels),
    ):
        assert getattr(spec.execution, key) == len(rows), (
            key,
            "physical trajectory capacity is padded",
        )
    if source_meta is not None:
        _, point = bridge.decode_source(source_meta["source_record"])
        for a, b in zip(
            ordinary.parent_state(state), ordinary.parent_state(point.state), strict=True
        ):
            assert a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()
        for a, b in zip(
            ordinary.parent_layout(p), ordinary.parent_layout(point.layout), strict=True
        ):
            np.testing.assert_array_equal(a, b)
        np.testing.assert_array_equal(state.phase_clock_s, [0.0])
    times = np.asarray(list(EventGrid(spec)))
    table = control_values(spec, times[:-1])
    model.check_steps(spec, np.diff(times), table)
    values = [state]
    try:
        for i, step in enumerate(np.diff(times)):
            state = rk4_step(
                lambda y, *args: model.rhs(y, *args, xp=np),
                state,
                step,
                table_control(table, i),
                p,
                p.active,
            )
            values.append(state)
        history = model.STATE_TYPE(*(np.stack(v) for v in zip(*values, strict=True)))
        diagnostics = model.check_values(history, spec)
    except Exception as error:
        path = location(output, dataset, "production-failure", factor)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path.with_suffix(".npz"),
            times_s=times[: len(values)],
            **{k: np.stack([getattr(v, k) for v in values]) for k in model.STATE_TYPE._fields},
        )
        write(path.with_suffix(".json"), dict(status="failed", error=str(error), inputs=raw))
        raise
    requested = np.asarray(raw["experiment"]["observation_times"])
    indexes = [EventGrid(spec).exact_index(t) for t in requested]
    context = reference.scheduled.bind(raw)
    flat = np.stack(
        [
            reference.scheduled.flatten(
                context, model.STATE_TYPE(*(v[i] for v in history))._asdict()
            )
            for i in indexes
        ]
    )
    observed = model.observe_history(times, history, p, requested, spec)
    arrays = dict(
        times_s=requested,
        integration_times_s=times,
        state_flat=flat,
        initial_flat=reference.scheduled.flatten(context, values[0]._asdict()),
        state_fields=np.asarray(model.STATE_TYPE._fields),
    )
    for key in model.STATE_TYPE._fields:
        np.testing.assert_array_equal(getattr(observed, key), getattr(history, key)[indexes])
        arrays[key] = np.asarray(getattr(history, key))[indexes]
        arrays["grid__" + key] = np.asarray(getattr(history, key))
    arrays.update({"obs__" + k: np.asarray(v) for k, v in vars(observed).items()})
    arrays.update({"layout__" + k: np.asarray(v) for k, v in zip(p._fields, p, strict=True)})
    meta = dict(
        inputs=raw,
        dt_s=spec.execution.dt,
        diagnostics=diagnostics,
        original_origin=True,
        layout="compact physical capacities; fixed gate/store/native slots retained",
        state_fields=len(state),
        handoff_preservation=None
        if preparation is None
        else preparation.provenance["preservation"],
        epoch_definition=None if phase == "INIT" else epoch_schema.to_dict(spec),
        source_record=None,
    )
    if phase == "INIT":
        point = Checkpoint(
            state, p, float(times[-1]), len(times) - 1, event_index(spec, float(times[-1]))
        )
        meta["source_record"] = bridge.capture_source(spec, point)
    else:
        clocks = json.loads(spec.model.handoff_json)["clocks"]
        np.testing.assert_array_equal(
            observed.init_phase_clock_s,
            np.full_like(observed.phase_clock_s, clocks["init_phase_clock_s"]),
        )
        np.testing.assert_allclose(
            observed.elapsed_time_s,
            clocks["init_checkpoint_time_s"] + observed.phase_clock_s,
            rtol=0,
            atol=1e-20,
        )
        meta["clocks"] = clocks
        if dataset.endswith("close-reopen"):
            i = EventGrid(spec).exact_index(2e-6)
            trial = model.STATE_TYPE(*(v[i] for v in history))
            signal = model.signal_values(trial, p, xp=np)
            sodium = spec.model.species_ids.index("Na")
            closed = signal.permeability[sodium] == 0
            assert np.any(closed) and np.any(trial.membrane_transferred[sodium, closed] != 0)
            meta["closed_background_with_preserved_history"] = True
    # Every observable balance must use the untouched complete carried state.
    for j, i in enumerate(indexes):
        actual = ordinary.parent_state(model.STATE_TYPE(*(v[i] for v in history)))
        balance = ordinary.base.balances(actual, ordinary.accounting_layout(p, xp=np))
        np.testing.assert_array_equal(
            observed.energy_balance_pJ[j], np.atleast_1d(balance["energy"])
        )
        np.testing.assert_array_equal(
            observed.pool_internal_transfer_balance_pJ[j], balance["pool_energy"]
        )
    save_unit(output, dataset, "production", factor, meta, arrays)


def comparison(bundle, output, dataset, factors=(1, 2), require_refinement=True):
    phase, family, _ = parts(dataset)
    ref_meta, exact = completed(output, dataset, "reference")
    context = reference.scheduled.bind(ref_meta["inputs"])
    process, parent = context["process"], context["parent"]
    floors = {
        k: np.full(shape, 3e-25 if k.endswith("_C") else 2e-11)
        for k, shape in parent["shapes"].items()
    }
    budget = np.r_[process.flatten(parent, floors), 2e-11] + 3e-9 * np.abs(exact["state_flat"])
    selector = {
        k: np.ones(shape) if k == "membrane_transferred" else np.zeros(shape)
        for k, shape in parent["shapes"].items()
    }
    mask = np.r_[process.flatten(parent, selector), 0.0].astype(bool)
    rows = []
    arrays = dict(
        times_s=exact["times_s"],
        reference_flat=exact["state_flat"],
        reference_initial_flat=exact["initial_flat"],
        reference_shapes_json=exact["reference_shapes_json"],
    )
    for factor in factors:
        meta, data = completed(output, dataset, "production", factor)
        np.testing.assert_array_equal(data["times_s"], exact["times_s"])
        actual = data["state_flat"]
        error = actual - exact["state_flat"]
        ratio = float(np.max(np.abs(error) / budget, initial=0))
        energy = [reference.energy_residual(context, v) for v in actual]
        ledgers = [reference.conservation(context, v) for v in actual]
        independent = {k: max(d[k] for d in ledgers) for k in ledgers[0]}
        for k, value in independent.items():
            assert value <= (4096 * np.finfo(float).eps if k == "damage_ledger" else 2e-12), (
                k,
                value,
            )
        assert max(map(abs, energy)) <= 1e-9, energy
        increment = (actual - data["initial_flat"]) - (exact["state_flat"] - exact["initial_flat"])
        row = dict(
            dt_s=meta["dt_s"],
            error_over_budget=ratio,
            max_error=float(np.max(np.abs(error))),
            background_cumulative_error_fmol=float(np.max(np.abs(error[:, mask]), initial=0)),
            background_increment_error_fmol=float(np.max(np.abs(increment[:, mask]), initial=0)),
            independent_energy_residual_pJ=energy,
            independent_conservation=independent,
            diagnostics=meta["diagnostics"],
        )
        rows.append(row)
        arrays["production_flat_" + str(factor)] = actual
        arrays["production_initial_flat_" + str(factor)] = data["initial_flat"]
        arrays["state_fields"] = data["state_fields"]
        arrays.update({str(factor) + "__" + k: data[k] for k in data["state_fields"].tolist()})
        if ratio > 1:
            save_comparison(
                output,
                dataset,
                dict(status="failed", reason="unchanged full-state budget", refinements=rows),
                arrays,
            )
        assert ratio <= 1, ratio
    if not require_refinement:
        save_comparison(
            output,
            dataset,
            dict(
                status="passed",
                pilot_only=True,
                refinement_claim=False,
                refinements=rows,
                all_observations_and_held_boundaries=True,
                original_origin=True,
                end_to_end_independent_INIT_and_SIM=True,
            ),
            arrays,
            role="pilot-accuracy",
        )
        return
    coarse, fine = [r["background_increment_error_fmol"] for r in rows]
    if phase == "SIM":
        if not (coarse > 1e-20 and fine <= 0.35 * coarse + 1e-22):
            save_comparison(
                output,
                dataset,
                dict(
                    status="failed",
                    reason="unresolved transient increment refinement",
                    refinements=rows,
                ),
                arrays,
            )
        assert coarse > 1e-20 and fine <= 0.35 * coarse + 1e-22, (coarse, fine)
        mode = "resolved_SIM_increment_reduction"
    else:
        high, low = [r["max_error"] for r in rows]
        assert low <= max(0.35 * high, 3e-13), (high, low)
        mode = "precision_limited" if max(high, low) <= 3e-13 else "resolved_reduction"
    save_comparison(
        output,
        dataset,
        dict(
            status="passed",
            phase=phase,
            family=family,
            refinements=rows,
            refinement_mode=mode,
            reference=ref_meta["proof"],
            all_observations_and_held_boundaries=True,
            complete_state_fields=44 if family == "water" else 49,
            original_origin=True,
            end_to_end_independent_INIT_and_SIM=True,
            compact_trajectory=True,
            padding_scope="separate accepted contract stages",
            endpoint_only_claim=False,
            convergence_order_claim=False,
        ),
        arrays,
    )


def save_comparison(output, dataset, record, arrays, role="comparison"):
    path = location(output, dataset, role)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path.with_suffix(".npz"), **arrays)
    write(path.with_suffix(".json"), dict(record, arrays_sha256=sha(path.with_suffix(".npz"))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset", choices=fixtures.DATASETS, required=True)
    parser.add_argument(
        "--role", choices=("reference", "production", "pilot-accuracy"), required=True
    )
    parser.add_argument("--factor", type=int, choices=(1, 2))
    args = parser.parse_args()
    try:
        if args.role == "reference":
            run_reference(args.bundle, args.output, args.dataset)
        elif args.role == "pilot-accuracy":
            comparison(
                args.bundle, args.output, args.dataset, factors=(1,), require_refinement=False
            )
        else:
            if args.factor is None:
                parser.error("Production needs its declared factor")
            run_production(args.bundle, args.output, args.dataset, args.factor)
    except Exception as error:
        path = location(args.output, args.dataset, args.role + "-failure", args.factor)
        if isinstance(error, reference.IntegrationFailure):
            path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(path.with_suffix(".npz"), **error.arrays)
        write(
            path.with_suffix(".json"),
            dict(status="failed", error=str(error), traceback=traceback.format_exc()),
        )
        raise


if __name__ == "__main__":
    main()
