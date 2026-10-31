"""Focused prospective qualification; UNRUN and uncollected in source preparation.

Future qualification must supply a new durable evidence root. Every actual
reference request/return and every production RK trial is saved before checks.
Fault injection cases test refusal behavior and receive no numerical credit.
"""

import dataclasses
import hashlib
import json
import math
import os
import struct
import subprocess
import sys
import traceback
from copy import deepcopy
from pathlib import Path

import pytest

if os.environ.get("CELLS_CHARGED_SURFACE_RELEASED") != "1":
    pytest.skip("Charged-surface scalar qualification remains held", allow_module_level=True)

import numpy as np  # noqa: E402 - explicit qualification release precedes scientific imports

from cells.processes import charged_surface_work as owner  # noqa: E402
from cells.processes.electrochemistry import F, R  # noqa: E402
from validation import charged_surface_work_declarations as cases  # noqa: E402

STAGE_RTOL = 3e-10
STAGE_ATOL = 3e-12
STATE_RTOL = 3e-9
STATE_ATOL = 2e-11
REFINEMENT_FLOORS = dict(
    amount_increment_fmol=4e-13,
    transferred_fmol=4e-13,
    dissipated_energy_pJ=4e-13,
    field_work_pJ=4e-13,
)


def save(root, name, value):
    path = root / (name + ".json")
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return path


def _evidence_value(value):
    """Serialize owner records without running owner methods or losing raw float bits."""
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float:
        return value if math.isfinite(value) else dict(float64_bits=struct.pack("<d", value).hex())
    if type(value) is bytes:
        return dict(bytes_hex=value.hex())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dict(
            dataclass_type=type(value).__module__ + "." + type(value).__qualname__,
            fields={
                field.name: _evidence_value(getattr(value, field.name))
                for field in dataclasses.fields(value)
            },
        )
    if type(value) is tuple:
        return dict(tuple_items=[_evidence_value(item) for item in value])
    if type(value) is list:
        return [_evidence_value(item) for item in value]
    if type(value) is dict and all(type(key) is str for key in value):
        return {key: _evidence_value(item) for key, item in value.items()}
    raise TypeError(
        "Unsupported evidence value: " + type(value).__module__ + "." + type(value).__qualname__
    )


def _evidence_exception(error, seen=None):
    seen = set() if seen is None else seen
    if id(error) in seen:
        return dict(exception_cycle=True, type=type(error).__qualname__)
    seen.add(id(error))
    return dict(
        type=type(error).__module__ + "." + type(error).__qualname__,
        message=str(error),
        code=_evidence_value(getattr(error, "code", None)),
        stage=_evidence_value(getattr(error, "stage", None)),
        partial=_evidence_value(getattr(error, "partial", None)),
        traceback="".join(traceback.format_exception(error)),
        suppress_context=error.__suppress_context__,
        cause=_evidence_exception(error.__cause__, seen.copy()) if error.__cause__ else None,
        context=_evidence_exception(error.__context__, seen.copy()) if error.__context__ else None,
    )


def _evidence_call(evidence, operation, invoke, *args, **kwargs):
    """Call once with the original objects; save outcomes before classification/assertions."""
    index = len(list(evidence.glob("owner_call_*")))
    leaf = evidence / ("owner_call_" + str(index).zfill(5) + "_" + operation)
    leaf.mkdir(exist_ok=False)
    save(
        leaf,
        "input",
        dict(
            operation=operation, arguments=_evidence_value(args), keywords=_evidence_value(kwargs)
        ),
    )
    try:
        result = invoke(*args, **kwargs)
    except BaseException as error:
        try:
            save(leaf, "failure", _evidence_exception(error))
        except BaseException as capture_error:
            # An archive failure is not an expected scientific refusal. Keep the
            # original exception as its cause rather than allowing pytest.raises
            # to credit a refusal whose complete failure artifact is missing.
            raise RuntimeError(
                "Owner failure evidence could not be retained: "
                + type(capture_error).__name__
                + ": "
                + str(capture_error)
            ) from error
        raise
    save(leaf, "return", _evidence_value(result))
    return result


@pytest.fixture
def evidence(request):
    root = Path(os.environ["CELLS_CHARGED_SURFACE_EVIDENCE_DIR"])
    assert root.is_absolute() and root.is_dir()
    leaf = root / hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
    leaf.mkdir(exist_ok=False)
    save(
        leaf,
        "case",
        dict(nodeid=request.node.nodeid, scientific_status="unqualified_until_checks_pass"),
    )
    return leaf


def array(record):
    return np.frombuffer(bytes.fromhex(record["data_hex"]), dtype=record["dtype"]).reshape(
        record["shape"]
    )


def _reference(evidence, label, raw, mode, precision, *, amounts=None, points=None):
    source = (
        Path(__file__).resolve().parents[2] / "validation" / "charged_surface_work_reference.py"
    )
    request = dict(
        mode=mode,
        declaration=raw,
        precision=precision,
        constants_binary64_hex=dict(F=float(F).hex(), R=float(R).hex()),
    )
    if amounts is not None:
        request["amounts"] = amounts.tolist()
    if points is not None:
        request["points"] = points
    text = json.dumps(request, sort_keys=True, allow_nan=False)
    save(evidence, label + "_input", request)
    command = [sys.executable, "-I", "-S", "-B", str(source)]
    process = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    try:
        stdout, stderr = process.communicate(text, timeout=60)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        save(
            evidence,
            label + "_failure",
            dict(
                pid=process.pid,
                command=command,
                reason="declared_60_second_reference_limit",
                stdout=stdout,
                stderr=stderr,
            ),
        )
        raise
    save(
        evidence,
        label + "_process",
        dict(
            pid=process.pid,
            ppid=os.getpid(),
            command=command,
            returncode=process.returncode,
            stdout=stdout,
            stderr=stderr,
            input_sha256=hashlib.sha256(text.encode()).hexdigest(),
        ),
    )
    assert process.returncode == 0, stderr
    result = json.loads(stdout)
    save(evidence, label + "_return", result)
    runtime = result["independent_runtime"]
    assert runtime["pid"] == process.pid and runtime["ppid"] == os.getpid()
    assert (
        runtime["isolated"] == 1
        and runtime["no_site"] == 1
        and runtime["science_modules_loaded"] == []
    )
    return result


def _compare_stage(actual, expected, path="stage"):
    if isinstance(actual, dict) and "dtype" not in actual:
        assert set(actual) == set(expected), path
        return max(
            (_compare_stage(actual[key], expected[key], path + "/" + key) for key in actual),
            default=0.0,
        )
    if "raw_boolean" in expected:
        assert bool(array(actual)) == expected["raw_boolean"] is expected["binary_boolean"]
        return 0.0
    target = array(expected["binary64"])
    value = array(actual)
    assert value.shape == target.shape and value.dtype == target.dtype, path
    assert len(expected["decimal"]) == value.size
    # Charge inventories and rates keep the inherited Coulomb/ampere budgets.
    atol = (
        3e-25
        if path.endswith("cargo_charge_C")
        else 3e-23
        if path.endswith("cargo_charge_rate_C_s")
        else STAGE_ATOL
    )
    norm = np.abs(value - target) / (atol + STAGE_RTOL * np.abs(target))
    assert np.isfinite(norm).all() and np.max(norm, initial=0.0) <= 1.0, path
    return float(np.max(norm, initial=0.0))


def _compare_reference_resolution(one, two, path="stage"):
    if isinstance(one, dict) and "binary64" not in one and "raw_boolean" not in one:
        assert set(one) == set(two), path
        return max(
            (_compare_reference_resolution(one[key], two[key], path + "/" + key) for key in one),
            default=0.0,
        )
    if "raw_boolean" in one:
        assert one == two, path
        return 0.0
    a, b = array(one["binary64"]), array(two["binary64"])
    assert a.shape == b.shape and a.dtype == b.dtype, path
    atol = (
        3e-25
        if path.endswith("cargo_charge_C")
        else 3e-23
        if path.endswith("cargo_charge_rate_C_s")
        else STAGE_ATOL
    )
    error = np.abs(a - b) / (atol + STAGE_RTOL * np.abs(b))
    assert np.isfinite(error).all() and np.max(error, initial=0.0) <= 0.1, path
    return float(np.max(error, initial=0.0))


def _walk(raw, evidence, label, *, stop=None, checkpoint=None, binding=None):
    binding = _evidence_call(evidence, "bind", owner.bind, raw) if binding is None else binding
    state = (
        _evidence_call(evidence, "initial", owner.initial, binding)
        if checkpoint is None
        else checkpoint
    )
    save(
        evidence,
        label + "_binding",
        dict(declaration=raw, source_pins=owner.SOURCE_PINS, identity=binding.identity),
    )
    save(evidence, label + "_initial", json.loads(owner.dump_checkpoint(state)))
    limit = len(raw["time_labels_s"]) - 1 if stop is None else stop
    while state.step_index < limit:
        try:
            proposal = _evidence_call(evidence, "advance", owner.advance, binding, state)
        except owner.SurfaceRejected as error:
            save(
                evidence,
                label + "_failure",
                dict(code=error.code, stage=error.stage, partial=error.partial),
            )
            raise
        save(
            evidence,
            label + "_step_" + str(state.step_index),
            dict(
                binding_identity=proposal.binding_identity,
                parent_identity=proposal.parent_identity,
                proposal_identity=proposal.identity,
                candidate=json.loads(owner.dump_checkpoint(proposal.candidate)),
                complete_raw_evidence=json.loads(proposal.evidence_json),
            ),
        )
        state = proposal.candidate
    readout = _evidence_call(evidence, "readout", owner.readout, binding, state)
    save(evidence, label + "_readout", readout)
    return binding, state, readout


def _state_arrays(checkpoint):
    return {
        key: array(dict(dtype=value.dtype, shape=value.shape, data_hex=value.data_hex))
        for key, value in zip(owner.STATE_FIELDS, checkpoint.state, strict=True)
    }


def test_complete_stage_independent_decimal_pair(evidence):
    raw = cases.multi_owner()
    binding, checkpoint, actual = _walk(raw, evidence, "one_step", stop=1)
    saved = json.loads((evidence / "one_step_step_0.json").read_text())["complete_raw_evidence"]
    stages = {"initial": saved["initial_raw"]["complete_energetic_return"]}
    stages.update(
        {entry["role"]: entry["raw"]["complete_energetic_return"] for entry in saved["trials"]}
    )
    stages["endpoint"] = saved["endpoint_raw"]["complete_energetic_return"]
    assert list(stages) == ["initial", "k1", "k2", "k3", "k4", "endpoint"]
    assert stages["endpoint"] == actual["stage"]
    points = [
        dict(role=role, amounts=array(value["amount_fmol"]).tolist())
        for role, value in stages.items()
    ]
    references = [
        _reference(
            evidence, "stage_" + str(precision), raw, "stage_batch", precision, points=points
        )
        for precision in (100, 160)
    ]
    errors = {
        role: [_compare_stage(value, result["points"][role]["result"]) for result in references]
        for role, value in stages.items()
    }
    resolution = {
        role: _compare_reference_resolution(
            references[0]["points"][role]["result"], references[1]["points"][role]["result"]
        )
        for role in stages
    }
    save(
        evidence,
        "metrics",
        dict(normalized_stage_errors=errors, normalized_reference_self_resolution=resolution),
    )
    assert checkpoint.binding_identity == binding.identity


@pytest.mark.parametrize(
    "kind",
    ["potential_gauge", "reference_density_gauge", "charge_and_field_reversal", "edge_orientation"],
)
def test_physical_gauges_and_orientation(kind, evidence):
    raw = cases.multi_owner()
    other = cases.transformed(raw, kind)
    _, left, left_readout = _walk(raw, evidence, "base", stop=4)
    _, right, right_readout = _walk(other, evidence, "transformed", stop=4)
    one, two = _state_arrays(left), _state_arrays(right)
    for key in owner.STATE_FIELDS:
        target = -one[key] if kind == "edge_orientation" and key == "transferred_fmol" else one[key]
        np.testing.assert_allclose(two[key], target, rtol=3e-12, atol=3e-15)
    for key in ("chemical_energy_change_pJ", "energy_balance_pJ"):
        np.testing.assert_allclose(
            array(left_readout["balances"][key]),
            array(right_readout["balances"][key]),
            rtol=3e-12,
            atol=3e-15,
        )


def test_neutral_reduction_and_signed_heat(evidence):
    raw = cases.two_patch(charge=0.0)
    binding = _evidence_call(evidence, "bind", owner.bind, raw)
    value = _evidence_call(
        evidence,
        "readout",
        owner.readout,
        binding,
        _evidence_call(evidence, "initial", owner.initial, binding),
    )["stage"]
    save(evidence, "neutral_stage", value)
    density = array(value["kernel"]["density_fmol_um2"])
    J = array(value["kernel"]["flux_fmol_s"])
    expected = (
        1e-3 * R * raw["layout"]["temperature_K"] * J * np.log(density[:, :1] / density[:, 1:])
    )
    np.testing.assert_allclose(
        array(value["dissipation_edge_pJ_s"]), expected, rtol=3e-12, atol=3e-15
    )
    assert np.all(array(value["field_power_edge_pJ_s"]) == 0)
    assert np.all(array(value["dissipation_edge_pJ_s"]) >= 0)


@pytest.mark.parametrize("case", ["no_edges", "zero_diffusivity", "absent_population"])
def test_exact_null_material_and_energy_controls(case, evidence):
    raw = cases.no_edges() if case == "no_edges" else cases.two_patch()
    if case == "zero_diffusivity":
        raw["layout"]["edge_diffusivity_um2_s"] = [[0.0]]
    if case == "absent_population":
        raw["initial_amount_fmol"] = [[0.0, 0.0]]
    _, checkpoint, _ = _walk(raw, evidence, "null", stop=2)
    assert all(np.all(value == 0) for value in _state_arrays(checkpoint).values())


def test_prescribed_field_pays_for_chemical_energy_increase(evidence):
    raw = cases.two_patch(potential=(0.02, -0.02), initial=(0.0001, 0.00025))
    _, checkpoint, readout = _walk(raw, evidence, "field_paid")
    state = _state_arrays(checkpoint)
    change = array(readout["balances"]["chemical_energy_change_pJ"])
    assert np.all(change > 0) and np.all(state["field_work_pJ"] > 0)
    assert np.all(state["dissipated_energy_pJ"] > 0)
    assert np.max(np.abs(array(readout["balances"]["energy_balance_pJ"]))) <= owner.ENERGY_ATOL_PJ
    assert readout["closed_system_or_biological_claim"] is False


@pytest.mark.parametrize("charge", [0.0, 1.0, -1.0])
def test_analytic_amount_work_direct_heat_and_full_horizon_refinement(charge, evidence):
    raw = cases.two_patch(charge=charge)
    refs = [
        _reference(evidence, "analytic_" + str(precision), raw, "analytic_two_patch", precision)
        for precision in (100, 160)
    ]
    targets = refs[1]["result"]
    errors = []
    for steps in (32, 64, 128):
        arm = cases.two_patch(charge=charge, steps=steps)
        _, endpoint, _ = _walk(arm, evidence, "steps_" + str(steps))
        assert endpoint.time_s == 4.0 and endpoint.step_index == steps
        state = _state_arrays(endpoint)
        worst = 0.0
        fields = {}
        for key in owner.STATE_FIELDS:
            target = array(targets[key]["binary64"])
            reference_coarse = array(refs[0]["result"][key]["binary64"])
            budget = STATE_ATOL + STATE_RTOL * np.abs(target)
            assert np.max(np.abs(target - reference_coarse) / budget, initial=0.0) <= 0.1
            difference = np.abs(state[key] - target)
            norm = difference / budget
            assert np.max(norm, initial=0.0) <= 1.0
            worst = max(worst, float(np.max(norm, initial=0.0)))
            fields[key] = dict(
                normalized_error=float(np.max(norm, initial=0.0)),
                absolute_error=float(np.max(difference, initial=0.0)),
            )
        errors.append(dict(steps=steps, normalized_error=worst, fields=fields))
    save(
        evidence,
        "refinement_metrics",
        dict(
            arms=errors,
            relative_reduction_bound=0.2,
            binary64_floors_by_owned_unit=REFINEMENT_FLOORS,
        ),
    )
    for coarse, fine in zip(errors, errors[1:], strict=False):
        for key in owner.STATE_FIELDS:
            assert (
                fine["fields"][key]["absolute_error"]
                <= 0.2 * coarse["fields"][key]["absolute_error"] + REFINEMENT_FLOORS[key]
            )
    assert all(result["heat_defined_from_energy_residual"] is False for result in refs)


def test_complete_checkpoint_restart_bit_identity(evidence):
    raw = cases.two_patch()
    binding, full, _ = _walk(raw, evidence, "full")
    _, split, _ = _walk(raw, evidence, "split", stop=16, binding=binding)
    wire = owner.dump_checkpoint(split)
    save(evidence, "portable_checkpoint", json.loads(wire))
    loaded = _evidence_call(evidence, "load_checkpoint", owner.load_checkpoint, binding, wire)
    _, continued, _ = _walk(raw, evidence, "restart", binding=binding, checkpoint=loaded)
    assert full == continued


@pytest.mark.parametrize(
    "defect",
    [
        "partial_zero",
        "negative",
        "nonfinite",
        "amount_dtype",
        "mask_dtype",
        "fractional_index",
        "cross_cell",
        "duplicate_edge",
        "padding",
        "clock",
    ],
)
def test_explicit_declaration_refusals(defect, evidence):
    raw = cases.multi_owner()
    if defect == "partial_zero":
        raw["initial_amount_fmol"][0][0] = 0.0
    elif defect == "negative":
        raw["initial_amount_fmol"][0][0] = -0.0001
    elif defect == "nonfinite":
        raw["initial_amount_fmol"][0][0] = float("nan")
    elif defect == "amount_dtype":
        raw["initial_amount_fmol"][0][0] = "0.0001"
    elif defect == "mask_dtype":
        raw["layout"]["cell_active"] = [1, 1, 0]
    elif defect == "fractional_index":
        raw["layout"]["patch_cell"][0] = 0.5
    elif defect == "cross_cell":
        raw["layout"]["edge_receiver"][0] = 2
    elif defect == "duplicate_edge":
        raw["layout"]["edge_sender"][1], raw["layout"]["edge_receiver"][1] = 1, 0
    elif defect == "padding":
        raw["initial_amount_fmol"][0][-1] = 0.0001
    elif defect == "clock":
        raw["time_labels_s"][1] = 0.0
    # Typed raw input preserves nonfinite bits without non-standard JSON.
    record = deepcopy(raw)
    if defect == "nonfinite":
        record["initial_amount_fmol"][0][0] = dict(
            binary64_hex=np.asarray(float("nan"), dtype="<f8").tobytes().hex()
        )
    save(evidence, "refused_declaration", record)
    with pytest.raises((owner.SurfaceRejected, ValueError)) as result:
        _evidence_call(evidence, "bind", owner.bind, raw)
    save(evidence, "refusal", dict(type=type(result.value).__name__, reason=str(result.value)))


def test_outside_exponent_domain_keeps_complete_nan_return(evidence):
    raw = cases.two_patch(potential=(10.0, -10.0))
    binding = _evidence_call(evidence, "bind", owner.bind, raw)
    with pytest.raises(owner.SurfaceRejected) as result:
        _evidence_call(
            evidence,
            "readout",
            owner.readout,
            binding,
            _evidence_call(evidence, "initial", owner.initial, binding),
        )
    partial = result.value.partial
    save(
        evidence,
        "raw_domain_failure",
        dict(code=result.value.code, stage=result.value.stage, partial=partial),
    )
    kernel = partial["raw"]["unchanged_flux_kernel_return"]
    assert bool(array(kernel["valid"])) is False
    assert np.isnan(array(kernel["flux_fmol_s"])).all()


@pytest.mark.parametrize("exponent", [0.0, 1e-10, 49.9, -49.9])
def test_exponent_boundary_controls(exponent, evidence):
    raw = cases.two_patch(potential=(0.0, exponent * R * 298.15 / F))
    binding = _evidence_call(evidence, "bind", owner.bind, raw)
    value = _evidence_call(
        evidence,
        "readout",
        owner.readout,
        binding,
        _evidence_call(evidence, "initial", owner.initial, binding),
    )
    save(evidence, "boundary_stage", value)
    refs = [
        _reference(
            evidence,
            "boundary_" + str(precision),
            raw,
            "stage",
            precision,
            amounts=array(value["stage"]["amount_fmol"]),
        )
        for precision in (100, 160)
    ]
    for result in refs:
        _compare_stage(value["stage"], result["result"])
    _compare_reference_resolution(refs[0]["result"], refs[1]["result"])
    assert bool(array(value["stage"]["kernel"]["valid"]))
    assert np.all(array(value["stage"]["dissipation_edge_pJ_s"]) >= -owner.DISSIPATION_ATOL_PJ)


def test_boltzmann_equilibrium_is_stationary(evidence):
    raw = cases.two_patch()
    p = raw["layout"]
    ratio = np.exp(
        -F
        * (raw["prescribed_potential_V"][1] - raw["prescribed_potential_V"][0])
        / (R * p["temperature_K"])
    )
    raw["initial_amount_fmol"][0][1] = (
        raw["initial_amount_fmol"][0][0]
        / p["patch_area_um2"][0]
        * p["patch_area_um2"][1]
        * float(ratio)
    )
    binding = _evidence_call(evidence, "bind", owner.bind, raw)
    result = _evidence_call(
        evidence,
        "readout",
        owner.readout,
        binding,
        _evidence_call(evidence, "initial", owner.initial, binding),
    )
    save(evidence, "boltzmann_equilibrium_stage", result)
    assert np.max(np.abs(array(result["stage"]["kernel"]["flux_fmol_s"]))) <= 2e-18
    assert np.max(np.abs(array(result["stage"]["dissipation_edge_pJ_s"]))) <= 1e-25


@pytest.mark.parametrize(
    "defect", ["foreign_binding", "dtype", "clock", "material_ledger", "field_work_ledger", "seal"]
)
def test_complete_checkpoint_refusals(defect, evidence):
    raw = cases.two_patch()
    binding, checkpoint, _ = _walk(raw, evidence, "checkpoint", stop=1)
    record = json.loads(owner.dump_checkpoint(checkpoint))
    if defect == "foreign_binding":
        changed = cases.two_patch(charge=-1.0)
        binding = _evidence_call(evidence, "bind", owner.bind, changed)
    elif defect == "dtype":
        record["state"]["amount_increment_fmol"]["dtype"] = "<f4"
    elif defect == "clock":
        record["time_s"] += 0.001
    elif defect in ("material_ledger", "field_work_ledger"):
        key = "amount_increment_fmol" if defect == "material_ledger" else "field_work_pJ"
        value = array(record["state"][key]).copy()
        value.flat[0] += 1e-5
        record["state"][key]["data_hex"] = value.tobytes().hex()
    else:
        record["identity"] = "0" * 64
    if defect != "seal":
        record["identity"] = owner.digest(
            {key: record[key] for key in ("binding_identity", "state", "time_s", "step_index")}
        )
    save(evidence, "refused_checkpoint", record)
    with pytest.raises(owner.SurfaceRejected) as result:
        _evidence_call(
            evidence, "load_checkpoint", owner.load_checkpoint, binding, json.dumps(record)
        )
    save(
        evidence,
        "checkpoint_refusal",
        dict(code=result.value.code, stage=result.value.stage, partial=result.value.partial),
    )


@pytest.mark.parametrize("target", ["initial", "k1", "k2", "k3", "k4", "endpoint"])
def test_unmasked_trial_failure_retention(target, evidence, monkeypatch):
    raw = cases.two_patch()
    binding = _evidence_call(evidence, "bind", owner.bind, raw)
    checkpoint = _evidence_call(evidence, "initial", owner.initial, binding)
    original = owner._stage
    calls = []
    roles = ("initial", "k1", "k2", "k3", "k4", "endpoint")

    def injected(vector, params, retain):
        role = roles[len(calls)]
        calls.append(role)
        if role == target:
            delta = vector.amount_increment_fmol.copy()
            delta[0, 0] = -2 * raw["initial_amount_fmol"][0][0]
            vector = vector._replace(amount_increment_fmol=delta)
        return original(vector, params, retain)

    monkeypatch.setattr(owner, "_stage", injected)
    with pytest.raises(owner.SurfaceRejected) as result:
        _evidence_call(evidence, "advance", owner.advance, binding, checkpoint)
    partial = result.value.partial
    save(
        evidence,
        "fault_injection_failure",
        dict(
            target=target, evaluated_roles=calls, no_numerical_accuracy_credit=True, partial=partial
        ),
    )
    assert calls[-1] == target and len(calls) == roles.index(target) + 1
    assert partial["evidence"]["candidate_accepted"] is False
    if target == "initial":
        failed = partial["evidence"]["initial_raw"]
    elif target == "endpoint":
        failed = partial["evidence"]["endpoint_raw"]
    else:
        failed = partial["evidence"]["trials"][-1]["raw"]
    assert "unmasked_state" in failed and "unchanged_flux_kernel_return" not in failed
    assert np.min(array(failed["unmasked_state"]["amount_increment_fmol"])) < 0
    assert checkpoint == _evidence_call(evidence, "initial", owner.initial, binding)


def test_declared_loss_bound_refusal_without_subdivision(evidence):
    raw = cases.two_patch(steps=1)
    raw["layout"]["edge_diffusivity_um2_s"] = [[20.0]]
    binding = _evidence_call(evidence, "bind", owner.bind, raw)
    checkpoint = _evidence_call(evidence, "initial", owner.initial, binding)
    with pytest.raises(owner.SurfaceRejected) as result:
        _evidence_call(evidence, "advance", owner.advance, binding, checkpoint)
    save(
        evidence,
        "loss_admission_failure",
        dict(code=result.value.code, partial=result.value.partial),
    )
    assert result.value.code == "existing_integrated_surface_loss_bound"
    assert result.value.partial["evidence"]["trials"] == []
    assert result.value.partial["evidence"]["candidate_accepted"] is False
    assert checkpoint == _evidence_call(evidence, "initial", owner.initial, binding)
