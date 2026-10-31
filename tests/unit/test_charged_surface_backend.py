"""UNRUN qualification source. Actual Root release is required before imports.

No fabricated positive qualification receipts or local gate bypass are used.
Every case archives setup, actual inputs/returns and final-readout failures.
"""

import hashlib
import json
import math
import os
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import fields, is_dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from cells.processes import charged_surface_backend as backend
from cells.processes import charged_surface_backend_arrays as arrays
from cells.processes import charged_surface_backend_gate as gate
from cells.processes import charged_surface_backend_kernel as kernel
from cells.processes import charged_surface_backend_plan as planning
from cells.processes import charged_surface_work as scalar

RELEASE_PATH = os.environ.get("CELLS_CHARGED_BACKEND_RELEASE")
if RELEASE_PATH is None:
    pytest.skip("Charged-surface backend qualification remains held", allow_module_level=True)
gate.authorize(RELEASE_PATH, {"backend": "cpu"})

import numpy as np  # noqa: E402 - external dependency gate precedes scientific imports

from validation import charged_surface_backend_declarations as cases  # noqa: E402
from validation.charged_surface_backend_reference import reference, save  # noqa: E402

ACTIVE_METRICS = ContextVar("charged_backend_qualification_metrics", default=None)


def decode(record):
    return np.frombuffer(bytes.fromhex(record["data_hex"]), dtype=record["dtype"]).reshape(
        record["shape"]
    )


def freeze(value, *, _exception_ids=()):
    if isinstance(value, (np.ndarray, np.generic)):
        return scalar._record(value, np)
    if isinstance(value, BaseException):
        if id(value) in _exception_ids:
            return dict(type=type(value).__name__, reason=str(value), repeated_exception=True)
        seen = (*_exception_ids, id(value))
        return dict(
            type=type(value).__name__,
            reason=str(value),
            available_fields=freeze(vars(value), _exception_ids=seen),
            code=freeze(getattr(value, "code", None), _exception_ids=seen),
            stage=freeze(getattr(value, "stage", None), _exception_ids=seen),
            cause=freeze(value.__cause__, _exception_ids=seen),
            context=freeze(value.__context__, _exception_ids=seen)
            if value.__cause__ is None and (not value.__suppress_context__)
            else None,
        )
    if is_dataclass(value):
        return {
            field.name: freeze(getattr(value, field.name), _exception_ids=_exception_ids)
            for field in fields(value)
        }
    if hasattr(value, "_asdict"):
        return freeze(value._asdict(), _exception_ids=_exception_ids)
    if isinstance(value, dict):
        return {
            str(key): freeze(item, _exception_ids=_exception_ids) for key, item in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [freeze(item, _exception_ids=_exception_ids) for item in value]
    if type(value) is float and (not math.isfinite(value)):
        return scalar._record(np.asarray(value, dtype=np.float64), np)
    if value is None or type(value) in (str, bool, int, float):
        return value
    return dict(type=type(value).__name__, available_repr=repr(value))


class Case:
    def __init__(self, root, label):
        self.root, self.label = root, label
        self.available = dict(phase="before_setup")
        self.events = 0

    def __enter__(self):
        self.metrics = []
        self.metric_token = ACTIVE_METRICS.set(self.metrics)
        return self

    def __exit__(self, kind, error, traceback):
        save(self.root, self.label + "_comparison_metrics", freeze(self.metrics))
        ACTIVE_METRICS.reset(self.metric_token)
        if error is not None:
            save(
                self.root,
                self.label + "_failure",
                dict(available=freeze(self.available), failure=freeze(error)),
            )
        return False

    def observer(self, name, value):
        save(
            self.root,
            self.label + "_event_" + str(self.events),
            dict(name=name, value=freeze(value)),
        )
        self.events += 1

    def prepare(self, raw):
        self.available.update(phase="plan_setup", declaration=raw)
        save(self.root, self.label + "_declaration", raw)
        plan = planning.make_plan(raw)
        self.available.update(phase="runner_setup", plan=freeze(plan))
        runner = backend.Runner(plan, release_path=RELEASE_PATH, observer=self.observer)
        self.available["phase"] = "initial_checkpoint_setup"
        parents = runner.initial_checkpoints()
        self.available.update(
            phase="ready", parents=freeze(parents), runtime=runner.runtime_identity()
        )
        save(self.root, self.label + "_parents", freeze(parents))
        return runner, parents

    def step(self, runner, parents, label):
        self.available.update(phase="batch_interval", parents=freeze(parents), step_label=label)
        proposal = runner.advance(parents)
        self.available.update(phase="complete_raw_output", proposal=freeze(proposal))
        save(self.root, self.label + "_" + label + "_proposal", freeze(proposal))
        result = runner.checkpoints(proposal)
        self.available.update(phase="final_checkpoint_readout", children=freeze(result))
        for world_id, child in result.items():
            binding = runner.contexts[world_id][0]
            raw = {}
            self.available["current_final_readout_raw"] = raw
            actual = scalar.readout(
                binding, child, observer=lambda name, value, raw=raw: raw.__setitem__(name, value)
            )
            save(self.root, self.label + "_" + label + "_readout_" + str(world_id), actual)
        return result, proposal


@pytest.fixture
def evidence(request):
    root = Path(os.environ["CELLS_CHARGED_BACKEND_EVIDENCE_DIR"])
    assert root.is_absolute() and root.is_dir()
    path = root / hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
    path.mkdir(exist_ok=False)
    save(path, "node", dict(nodeid=request.node.nodeid, run_status="qualification_pending_checks"))
    return path


def tolerances(path, *, state=False):
    # Used for BOTH candidate accuracy and reference self-resolution.
    if path.endswith("cargo_charge_C"):
        return 3e-10, 3e-25
    if path.endswith("cargo_charge_rate_C_s"):
        return 3e-10, 3e-23
    return (3e-9, 2e-11) if state else (3e-10, 3e-12)


def compare(actual, expected, *, path="stage", decimal=False, fraction=1.0, state=False):
    if isinstance(actual, dict) and "dtype" not in actual:
        assert set(actual) == set(expected), path
        return max(
            (
                compare(
                    actual[key],
                    expected[key],
                    path=path + "/" + key,
                    decimal=decimal,
                    fraction=fraction,
                    state=state,
                )
                for key in actual
            ),
            default=0.0,
        )
    target = (
        decode(expected["binary64"])
        if decimal and "binary64" in expected
        else np.asarray(expected["raw_boolean"])
        if decimal
        else decode(expected)
    )
    value = decode(actual)
    assert value.shape == target.shape, path
    if value.dtype.kind in "bui":
        np.testing.assert_array_equal(value, target)
        return 0.0
    assert value.dtype == target.dtype == np.dtype("float64"), path
    rtol, atol = tolerances(path, state=state)
    normalized = np.abs(value - target) / (atol + rtol * np.abs(target))
    metrics = ACTIVE_METRICS.get()
    if metrics is not None:
        metrics.append(
            dict(
                path=path,
                actual_dtype=value.dtype.str,
                shape=list(value.shape),
                rtol=rtol,
                atol=atol,
                accepted_fraction=fraction,
                maximum_normalized_error=float(np.max(normalized, initial=0)),
            )
        )
    assert np.isfinite(normalized).all() and np.max(normalized, initial=0) <= fraction, path
    return float(np.max(normalized, initial=0))


def resolution(one, two, path="stage", *, state=False):
    if isinstance(one, dict) and "binary64" not in one and "raw_boolean" not in one:
        assert set(one) == set(two)
        return max(
            (resolution(one[key], two[key], path + "/" + key, state=state) for key in one),
            default=0.0,
        )
    if "raw_boolean" in one:
        assert one == two
        return 0.0
    return compare(one["binary64"], two["binary64"], path=path, fraction=0.1, state=state)


def actual_stages(row):
    raw = json.loads(row.evidence_json)["raw_array_attempt"]
    return {
        "initial": raw["initial"],
        **{"k" + str(index + 1): value for index, value in enumerate(raw["trials"])},
        "endpoint": raw["endpoint"],
    }


@pytest.mark.parametrize("mode", ["numpy", "jax_eager", "jax_jit"])
@pytest.mark.parametrize("width", [1, 2])
def test_complete_actual_stages_scalar_and_independent_decimal(mode, width, evidence):
    with Case(evidence, "complete") as case:
        runner, parents = case.prepare(cases.cohort(mode, width=width))
        children, proposal = case.step(runner, parents, "step0")
        for row in proposal.worlds:
            binding, parameters = runner.contexts[row.world_id]
            scalar_proposal = scalar.advance(binding, parents[row.world_id])
            save(evidence, "scalar_" + str(row.world_id), freeze(scalar_proposal))
            old = json.loads(scalar_proposal.evidence_json)
            expected = {
                "initial": old["initial_raw"]["complete_energetic_return"],
                **{
                    entry["role"]: entry["raw"]["complete_energetic_return"]
                    for entry in old["trials"]
                },
                "endpoint": old["endpoint_raw"]["complete_energetic_return"],
            }
            actual = actual_stages(row)
            points = []
            for role, stage in actual.items():
                assert bool(decode(stage["attempted"])) and bool(decode(stage["energetic_called"]))
                compare(stage["values"], expected[role])
                points.append(
                    dict(role=role, amounts=decode(stage["values"]["amount_fmol"]).tolist())
                )
            refs = [
                reference(
                    evidence,
                    "world_" + str(row.world_id) + "_" + str(precision),
                    scalar.parse(binding.declaration_json),
                    dict(F=float(parameters[4]).hex(), R=float(parameters[5]).hex()),
                    mode="stage_batch",
                    precision=precision,
                    points=points,
                )
                for precision in (100, 160)
            ]
            for role, stage in actual.items():
                for ref in refs:
                    compare(stage["values"], ref["points"][role]["result"], decimal=True)
                resolution(refs[0]["points"][role]["result"], refs[1]["points"][role]["result"])
            candidate = scalar.checkpoint_record(children[row.world_id])["state"]
            compare(
                candidate, scalar.checkpoint_record(scalar_proposal.candidate)["state"], state=True
            )
        assert {row.world_id for row in proposal.worlds} == set(children) == set(parents)


@pytest.mark.parametrize("mode", ["numpy", "jax_eager", "jax_jit"])
@pytest.mark.parametrize("charge", [0.0, 1.0, -1.0])
def test_full_horizon_analytic_work_independent_direct_heat(mode, charge, evidence):
    errors = []
    refs = None
    for steps in (32, 64, 128):
        with Case(evidence, "steps_" + str(steps)) as case:
            runner, state = case.prepare(cases.analytic(mode, charge, steps))
            if refs is None:
                binding, parameters = runner.contexts[317]
                refs = [
                    reference(
                        evidence,
                        "analytic_" + str(precision),
                        scalar.parse(binding.declaration_json),
                        dict(F=float(parameters[4]).hex(), R=float(parameters[5]).hex()),
                        mode="analytic_two_patch",
                        precision=precision,
                    )
                    for precision in (100, 160)
                ]
                resolution(refs[0]["result"], refs[1]["result"], state=True)
            for step in range(steps):
                state, _ = case.step(runner, state, "interval_" + str(step))
            checkpoint = state[317]
            assert checkpoint.step_index == steps and checkpoint.time_s == 4.0
            actual = scalar.checkpoint_record(checkpoint)["state"]
            compare(actual, refs[1]["result"], decimal=True, state=True)
            fields_error = {
                key: float(
                    np.max(
                        np.abs(decode(value) - decode(refs[1]["result"][key]["binary64"])),
                        initial=0,
                    )
                )
                for key, value in actual.items()
            }
            errors.append(fields_error)
    save(
        evidence,
        "per_field_refinement",
        dict(errors=errors, amount_floor_fmol=4e-13, energy_floor_pJ=4e-13),
    )
    for first, second in zip(errors, errors[1:], strict=False):
        for key in first:
            assert second[key] <= 0.2 * first[key] + 4e-13


@pytest.mark.parametrize("mode", ["numpy", "jax_eager", "jax_jit"])
def test_restart_repartition_reorder_and_ragged_terminal_worlds(mode, evidence):
    with Case(evidence, "restart") as case:
        raw = cases.cohort(mode, width=2)
        runner, initial = case.prepare(raw)
        state = initial
        for step in range(4):
            state, _ = case.step(runner, state, "prefix_" + str(step))
        wire = backend.dump_snapshot(runner.snapshot(state))
        save(evidence, "snapshot_wire", json.loads(wire))
        changed_plan = planning.make_plan(cases.reordered(raw, width=1))
        changed = backend.Runner(changed_plan, release_path=RELEASE_PATH, observer=case.observer)
        restored = changed.load_snapshot(backend.parse_snapshot(wire))
        uninterrupted = state
        for step in range(4, 64):
            uninterrupted, _ = case.step(runner, uninterrupted, "whole_" + str(step))
            restored, _ = case.step(changed, restored, "restored_" + str(step))
        assert set(restored) == set(uninterrupted) == set(initial)
        for world_id in restored:
            assert scalar.dump_checkpoint(restored[world_id]) == scalar.dump_checkpoint(
                uninterrupted[world_id]
            )
            binding = runner.contexts[world_id][0]
            assert (
                restored[world_id].time_s
                == scalar.parse(binding.declaration_json)["time_labels_s"][-1]
            )


@pytest.mark.parametrize("mode", ["numpy", "jax_eager", "jax_jit"])
def test_failed_world_retains_nan_and_all_world_identities(mode, evidence):
    with Case(evidence, "failure") as case:
        raw = cases.cohort(mode)
        raw["worlds"][1]["declaration"]["prescribed_potential_V"] = [10.0, -10.0]
        runner, parents = case.prepare(raw)
        with pytest.raises(backend.BatchRejected) as result:
            runner.advance(parents)
        save(evidence, "complete_refused_cohort", freeze(result.value))
        rows = result.value.worlds
        assert [row.world_id for row in rows] == [world["world_id"] for world in raw["worlds"]]
        failed = next(row for row in rows if row.world_id == 12)
        assert not failed.accepted and failed.candidate_checkpoint_json is None
        assert failed.source_checkpoint_json == scalar.dump_checkpoint(parents[12])
        stage = actual_stages(failed)["initial"]
        assert bool(decode(stage["kernel_called"])) and not bool(decode(stage["energetic_called"]))
        assert np.isnan(decode(stage["kernel"]["flux_fmol_s"])).all()
        assert all(
            not bool(decode(stage["attempted"]))
            for role, stage in actual_stages(failed).items()
            if role != "initial"
        )
        assert any(row.accepted for row in rows)


@pytest.mark.parametrize("mode", ["numpy", "jax_eager", "jax_jit"])
@pytest.mark.parametrize("target", [0, 1, 2, 3])
def test_internal_fault_guard_stops_at_first_failed_actual_trial(mode, target, evidence):
    with Case(evidence, "fault") as case:
        runner, parents = case.prepare(cases.analytic(mode, 1.0, 32))
        group = runner.plan.groups[0]
        packed = runner._inputs(group, parents)
        _, parameters = runner.contexts[317]
        _, _, movement, fixed, F, R, _, _, _, _ = parameters
        from cells.numerics.extracellular_field import ordered_scatter

        calls = []

        def fault_step(rhs, state, dt):
            def injected(trial):
                ordinal = len(calls)
                calls.append(ordinal)
                if ordinal == target:
                    delta = -2 * packed.parameters.anchor[0]
                    trial = trial._replace(amount_increment_fmol=runner.xp.asarray(delta))
                return rhs(trial)

            return fixed.rk4_step(injected, state, dt)

        _, mapped = kernel.build_kernel(
            xp=runner.xp,
            jax=runner.jax,
            movement=movement,
            fixed=SimpleNamespace(rk4_step=fault_step),
            F=F,
            R=R,
            ordered_scatter=ordered_scatter,
            scalar=scalar,
            dimensions=group.dimensions,
        )
        if runner.jax is None:
            observed = mapped(packed)
        else:
            arguments = runner.jax.device_put(packed, runner.device)
            if mode == "jax_jit":
                observed = runner.jax.jit(mapped)(arguments)
            else:
                with runner.jax.disable_jit():
                    observed = mapped(arguments)
            runner.jax.block_until_ready(observed)
            observed = arrays.map_tree(np.asarray, observed)
        save(
            evidence,
            "raw_fault_attempt",
            dict(
                target=target, no_numerical_accuracy_credit=True, raw=scalar._record(observed, np)
            ),
        )
        row = arrays.map_tree(lambda leaf: leaf[0], observed)
        assert not bool(row.ok) and int(row.code) == 20 + target
        assert bool(row.trials[target].attempted) and not bool(row.trials[target].kernel_called)
        assert all(not bool(item.attempted) for item in row.trials[target + 1 :])
        assert not bool(row.endpoint_formed)
        for actual, parent in zip(row.candidate, packed.state, strict=True):
            np.testing.assert_array_equal(actual, parent[0])


@pytest.mark.parametrize("field", ["max_working_bytes", "max_evidence_bytes"])
def test_shape_and_resource_admission_before_array_allocation(field, evidence):
    raw = cases.cohort("numpy")
    raw["execution"][field] = 1
    save(evidence, "declared_refusal", raw)
    with pytest.raises(ValueError):
        planning.make_plan(raw)


def test_exact_group_membership_and_no_implicit_resizing(evidence):
    raw = cases.cohort("numpy", width=1)
    plan = planning.make_plan(raw)
    save(evidence, "shape_plan", freeze(plan))
    assert sorted(identity for group in plan.groups for identity in group.world_ids) == [
        4,
        12,
        71,
        90,
    ]
    assert all(len(group.world_ids) == 1 for group in plan.groups)
    changed = deepcopy(raw)
    changed["worlds"][1]["world_id"] = changed["worlds"][0]["world_id"]
    with pytest.raises(ValueError):
        planning.make_plan(changed)


@pytest.mark.parametrize("defect", ["world_missing", "case_swapped", "state_buffer", "runtime"])
def test_complete_snapshot_refusals(defect, evidence):
    with Case(evidence, "snapshot_refusal") as case:
        runner, parents = case.prepare(cases.cohort("numpy"))
        snapshot = runner.snapshot(parents)
        record = json.loads(snapshot.record_json)
        if defect == "world_missing":
            record["worlds"].pop()
        elif defect == "case_swapped":
            record["worlds"][0]["case_id"] = record["worlds"][1]["case_id"]
        elif defect == "runtime":
            record["runtime"]["engine"] = "foreign"
        else:
            child = json.loads(record["worlds"][0]["checkpoint_json"])
            child["state"]["field_work_pJ"]["data_hex"] = "0" * len(
                child["state"]["field_work_pJ"]["data_hex"]
            )
            child["identity"] = "0" * 64
            record["worlds"][0]["checkpoint_json"] = json.dumps(child)
        corrupted = backend.BatchSnapshot(json.dumps(record), scalar.digest(record))
        save(evidence, "corrupted_snapshot", freeze(corrupted))
        with pytest.raises((ValueError, backend.BatchRejected)):
            runner.load_snapshot(corrupted)


def test_release_dependency_is_mandatory(evidence):
    save(
        evidence, "pending_dependency_control", dict(release=None, scientific_accuracy_credit=False)
    )
    with pytest.raises(gate.HeldDependencyError):
        gate.authorize(None, {"backend": "cpu"})


@pytest.mark.parametrize("phase", ["setup", "final_readout"])
def test_available_failure_evidence_is_archived(phase, evidence, monkeypatch):
    original_initial, original_readout = (scalar.initial, scalar.readout)
    count = []

    def failed_initial(binding):
        count.append(binding.identity)
        if len(count) == 2:
            raise scalar.SurfaceRejected(
                "injected_setup_refusal",
                stage="initial_setup",
                partial=dict(binding_identity=binding.identity),
            )
        return original_initial(binding)

    def failed_readout(binding, checkpoint, *, observer=None):
        value = original_readout(binding, checkpoint, observer=observer)
        raise scalar.SurfaceRejected(
            "injected_final_readout_refusal", stage="final_readout", partial=value
        )

    if phase == "setup":
        monkeypatch.setattr(scalar, "initial", failed_initial)
    else:
        monkeypatch.setattr(scalar, "readout", failed_readout)
    with pytest.raises((scalar.SurfaceRejected, backend.BatchRejected)):
        with Case(evidence, "archive") as case:
            runner, parents = case.prepare(cases.cohort("numpy"))
            case.step(runner, parents, "injected")
    record = json.loads((evidence / "archive_failure.json").read_text())
    assert record["available"]["declaration"]
    if phase == "setup":
        assert record["failure"]["available_fields"]["evidence"]["available_parents"]
    else:
        assert record["available"]["parents"] and record["available"]["children"]
        assert record["available"]["current_final_readout_raw"]["complete_energetic_return"]
    failure = record["failure"]
    if phase == "setup":
        assert failure["type"] == "BatchRejected"
        assert failure["reason"] == "Initial setup failed before any interval execution"
        cause = failure["cause"]
        assert cause["type"] == "SurfaceRejected"
        assert cause["reason"] == cause["code"] == "injected_setup_refusal"
        assert cause["stage"] == "initial_setup"
        assert cause["cause"] is None
        saved = failure["available_fields"]["evidence"]
        assert saved["failed_world_id"] == 12
        assert set(saved["available_parents"]) == {"71"}
        assert cause["available_fields"]["partial"] == saved["original_partial"]
    else:
        assert failure["type"] == "SurfaceRejected"
        assert failure["reason"] == failure["code"] == "injected_final_readout_refusal"
        assert failure["stage"] == "final_readout"
        assert failure["cause"] is None
        partial = failure["available_fields"]["partial"]
        assert partial["raw"] == record["available"]["current_final_readout_raw"]
        assert partial["stage"] and partial["balances"]


@pytest.mark.parametrize("mode", ["numpy", "jax_eager", "jax_jit"])
@pytest.mark.parametrize("exponent", [0.0, 1e-10, 49.9, -49.9])
def test_near_zero_and_exponent_boundary_actual_stages(mode, exponent, evidence):
    with Case(evidence, "exponent_boundary") as case:
        from cells.processes.electrochemistry import F, R

        raw = cases.analytic(mode, 1.0, 32)
        declaration = raw["worlds"][0]["declaration"]
        declaration["prescribed_potential_V"] = [0.0, exponent * R * 298.15 / F]
        declaration["layout"]["edge_diffusivity_um2_s"] = [[0.001]]
        runner, parents = case.prepare(raw)
        _, proposal = case.step(runner, parents, "one_original_interval")
        binding, parameters = runner.contexts[317]
        stages = actual_stages(proposal.worlds[0])
        points = [
            dict(role=role, amounts=decode(value["values"]["amount_fmol"]).tolist())
            for role, value in stages.items()
        ]
        refs = [
            reference(
                evidence,
                "boundary_" + str(precision),
                scalar.parse(binding.declaration_json),
                dict(F=float(parameters[4]).hex(), R=float(parameters[5]).hex()),
                mode="stage_batch",
                precision=precision,
                points=points,
            )
            for precision in (100, 160)
        ]
        for role, stage in stages.items():
            assert bool(decode(stage["attempted"])) and bool(decode(stage["energetic_called"]))
            for result in refs:
                compare(stage["values"], result["points"][role]["result"], decimal=True)
            resolution(refs[0]["points"][role]["result"], refs[1]["points"][role]["result"])
