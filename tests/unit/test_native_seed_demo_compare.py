"""Synthetic saved bytes only; use the real report/payload/pin verifiers."""

import hashlib
import json
import math
import os
import struct
from contextlib import contextmanager
from types import FunctionType

import pytest

from tests.unit import test_native_seed_demo_report as model
from validation.betse import native_seed_demo_compare as compare
from validation.betse import native_seed_demo_compare_software as software

_RAW_GUARDS = []


@pytest.fixture(autouse=True)
def blocked(request, tmp_path):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Explicit immutable paired-report metadata release required")
    scope = dict(vars(model), software=software, _RAW_GUARDS=_RAW_GUARDS)
    function = FunctionType(model.blocked.__wrapped__.__code__, scope)
    with contextmanager(function)(request, tmp_path):
        yield


def _array(raw=None, *, shape=None, strides=None, dtype="<f8"):
    return dict(
        __ndarray__=True,
        dtype=dtype,
        shape=[2] if shape is None else shape,
        strides=[8] if strides is None else strides,
        raw_bytes_hex=(struct.pack("<2d", 1.0, 2.0) if raw is None else raw).hex(),
    )


def _cache(array=None, *, source_strides=None):
    array = _array() if array is None else array
    raw = bytes.fromhex(array["raw_bytes_hex"])
    node = dict(
        kind="numeric_array",
        column="column_00000",
        sha256=hashlib.sha256(raw).hexdigest(),
        source_layout=dict(
            dtype=array["dtype"],
            shape=array["shape"],
            strides_bytes=array["strides"] if source_strides is None else source_strides,
            C_contiguous=source_strides is None or source_strides == array["strides"],
            F_contiguous=source_strides is None or source_strides == array["strides"],
        ),
    )
    result = _cache_node(node, [dict(name="column_00000", values=array)])
    if array["dtype"][-2:] == "f8":
        endian = ">" if array["dtype"].startswith(">") else "<"
        result["all_finite"] = all(
            math.isfinite(value) for (value,) in struct.iter_unpack(endian + "d", raw)
        )
    return result


def _cache_node(node, columns=()):
    descriptor = json.dumps(node, sort_keys=True, separators=(",", ":"))
    return dict(
        descriptor_json=descriptor,
        identity=hashlib.sha256(descriptor.encode()).hexdigest(),
        all_finite=True,
        columns=list(columns),
    )


def _replace(value, label, data, *, geometry=False, sidecars=False):
    folder = value.worker / "demo"
    if geometry:
        folder /= "geometry"
    outcome = model.read(folder / "outcome.json")
    row = next(row for row in outcome["captures"] if row["label"] == label)
    path = folder / row["path"]
    if sidecars:
        path.unlink()  # Newly generated synthetic fixture, never a historical run.
        compare.evidence.write(path, data)
    else:
        model.write(path, data)
    row["sha256"] = model.pin(path)["sha256"]
    model.write(folder / "outcome.json", outcome)


def _history(value):
    folder = value.worker / "demo"
    outcome = model.read(folder / "outcome.json")
    captures = {row["label"]: row for row in outcome["captures"]}
    record = model.read(folder / captures["init_short_history.record"]["path"])
    linkage = model.read(folder / captures["init_short_history.linkage"]["path"])
    replacements = dict(before=_cache(), after=_cache(_array(struct.pack("<2d", 3.0, 4.0))))
    replacements["calendar"] = _cache(
        _array(struct.pack("<5d", *(i * 0.00123456789 for i in range(5))), shape=[5])
    )
    replacements["sampled"] = _cache_node(
        dict(
            kind="tuple",
            items=[
                dict(
                    kind="numpy_scalar",
                    dtype="<f8",
                    bits=struct.pack("<d", i * 0.00123456789).hex(),
                )
                for i in (0, 2)
            ],
        )
    )
    replacements["configured_dt"] = _cache_node(
        dict(kind="float", bits=struct.pack("<d", 0.001).hex())
    )
    for name, cache in replacements.items():
        _replace(value, "init_short_history." + name, cache)
        record["dt" if name == "configured_dt" else name] = cache["identity"]
    for ordinal, row in enumerate(record["iterations"]):
        cache = replacements["after"] if ordinal == len(record["iterations"]) - 1 else _cache()
        row[3] = cache["identity"]
        linkage["iterations"][ordinal]["after_identity"] = cache["identity"]
        _replace(value, f"init_short_history.iteration.{ordinal:04d}.after", cache)
    _replace(value, "init_short_history.record", record)
    _replace(value, "init_short_history.linkage", linkage)


def _fixture(tmp_path, mode, *, endpoint="seed", iterations=3, sidecars=False):
    value = model.fixture(tmp_path, mode=mode, endpoint=endpoint, iterations=iterations)
    array = _array(b"\0" * (8192 * 8), shape=[8192]) if sidecars else _array()
    _replace(value, "profiles.after", _cache(array), sidecars=sidecars)
    _replace(value, "completed_geometry.cache", _cache(), geometry=True)
    if endpoint == "init_short_history":
        _history(value)
    return value


def _report(value):
    saved = model.inspect(value)
    pin = model.write(value.base / "saved-report.json", saved)
    return dict(report=pin, plan=model.pin(value.plan))


def _pair(tmp_path, *, endpoint="seed", sidecars=False):
    values = [
        _fixture(tmp_path, mode, endpoint=endpoint, sidecars=sidecars)
        for mode in ("original", "disabled")
    ]
    return values, [_report(value) for value in values]


@pytest.mark.parametrize("endpoint", ("seed", "init_short_history"))
def test_compare_authenticates_reports_and_available_state_without_domain_admission(
    tmp_path, endpoint
):
    _, refs = _pair(tmp_path, endpoint=endpoint)
    result = compare.compare_saved(*refs)
    assert result["paired_execution_complete"] is True
    assert all(row["authenticated"] for row in result["attempts"].values())
    assert result["status"] == "compared_completed_attempts"
    assert result["all_available_observations_equal"] is True
    assert (
        result["unavailable_observations"] > 0
    )  # Inert legacy placeholders are not numeric evidence.
    assert result["domain_diagnostics"]["original"]["support"]["maskM"]["nonzero"] == 0
    assert result["domain_diagnostics"]["original"]["domain_gate_passed"] is False
    assert result["scientific_credit"] == 0 and result["physical_parity"] is False
    assert (
        result["ordinary_checkpoint_admitted"] is result["original_flux_defect_repaired"] is False
    )
    if endpoint == "init_short_history":
        assert result["timing"]["equal"] is True
        streams = [
            row
            for row in result["observations"]
            if row["label"] == "tissue_INIT:init_short_history.stream_after"
        ]
        assert len(streams) == 1 and streams[0]["comparison"]["equal"] is True


@pytest.mark.parametrize(
    "mutation", ("value", "signed_zero", "nan_bits", "strides", "shape", "dtype")
)
def test_compare_reports_exact_data_or_layout_differences_without_tolerance(tmp_path, mutation):
    values = [_fixture(tmp_path, mode) for mode in ("original", "disabled")]
    array, strides = _array(), None
    if mutation == "value":
        array = _array(struct.pack("<2d", 1.0, 3.0))
    elif mutation == "signed_zero":
        _replace(values[0], "profiles.after", _cache(_array(struct.pack("<2d", 0.0, 2.0))))
        array = _array(struct.pack("<2d", -0.0, 2.0))
    elif mutation == "nan_bits":
        _replace(values[0], "profiles.after", _cache(_array(bytes.fromhex("010000000000f87f") * 2)))
        array = _array(bytes.fromhex("020000000000f87f") * 2)
    elif mutation == "strides":
        strides = [-8]
    elif mutation == "shape":
        array = _array(shape=[1, 2], strides=[16, 8])
    elif mutation == "dtype":
        array = _array(dtype=">f8")
    _replace(values[1], "profiles.after", _cache(array, source_strides=strides))
    result = compare.compare_saved(*[_report(value) for value in values])
    row = next(
        row for row in result["observations"] if row["label"] == "tissue_INIT:profiles.after"
    )
    assert row["comparison"]["equal"] is False and row["comparison"]["difference_count"] > 0
    assert result["paired_execution_complete"] is True
    assert result["all_available_observations_equal"] is False
    assert result["numerical_or_conservation_qualification"] is False


def test_compare_authenticates_complete_sidecars_and_detects_later_corruption(tmp_path):
    values, refs = _pair(tmp_path, sidecars=True)
    first = compare.compare_saved(*refs)
    assert first["all_available_observations_equal"] is True
    blob = next((values[1].worker / "demo").glob("*.arrays/*.bin"))
    with blob.open("r+b") as stream:
        stream.write(b"\1")
    rejected = compare.compare_saved(*refs)
    assert rejected["attempts"]["disabled"]["authenticated"] is False
    assert rejected["paired_execution_complete"] is False
    assert rejected["observations"] == []


@pytest.mark.parametrize("target", ("report", "input", "capture", "source"))
def test_compare_rejects_changed_underlying_bytes_before_state_comparison(tmp_path, target):
    values, refs = _pair(tmp_path)
    value = values[1]
    if target == "report":
        path = value.base / "saved-report.json"
    elif target == "input":
        path = value.base / "config/original.yaml"
    elif target == "source":
        path = value.source / model.report.DEMO
        path.chmod(0o644)
    else:
        row = next(
            row
            for row in model.read(value.worker / "demo/outcome.json")["captures"]
            if row["label"] == "profiles.after"
        )
        path = value.worker / "demo" / row["path"]
    with path.open("ab") as stream:
        stream.write(b" ")
    result = compare.compare_saved(*refs)
    assert result["attempts"]["disabled"]["authenticated"] is False
    assert result["attempts"]["disabled"]["error"] is not None
    assert not result["paired_execution_complete"] and result["observations"] == []


@pytest.mark.parametrize(
    "field,value", (("status", "failed"), ("scientific_credit", 1), ("extra", True))
)
def test_compare_recomputes_saved_report_instead_of_trusting_rehashed_summary(
    tmp_path, field, value
):
    _, refs = _pair(tmp_path)
    path = compare.Path(refs[1]["report"]["path"])
    saved = model.read(path)
    saved[field] = value
    refs[1]["report"] = model.write(path, saved)
    result = compare.compare_saved(*refs)
    assert result["attempts"]["disabled"]["authenticated"] is False
    assert "current authenticated inspection" in result["attempts"]["disabled"]["error"]["message"]


@pytest.mark.parametrize("mismatch", ("endpoint", "iterations", "input"))
def test_compare_refuses_incompatible_provenance_before_comparing_states(tmp_path, mismatch):
    a = _fixture(tmp_path, "original", endpoint="init_short_history", iterations=3)
    b = _fixture(
        tmp_path,
        "disabled",
        endpoint="seed" if mismatch == "endpoint" else "init_short_history",
        iterations=1 if mismatch == "iterations" else 3,
    )
    if mismatch == "input":
        path = b.base / "config/original.yaml"
        path.write_text("different-input: true\n")
        plan = model.read(b.plan)
        bundle = model.read(compare.Path(plan["input_bundle"]["path"]))
        bundle["source_inventory"]["files"]["original.yaml"]["sha256"] = model.pin(path)["sha256"]
        plan["input_bundle"] = model.write(compare.Path(plan["input_bundle"]["path"]), bundle)
        plan["input_files"] = [model.pin(path)]
        b.digest = model.write(b.plan, plan)["sha256"]
        worker = model.read(b.worker / "result.json")
        worker["plan_sha256"] = b.digest
        worker_pin = model.write(b.worker / "result.json", worker)
        terminal = model.read(b.output / "result.json")
        terminal.update(plan_sha256=b.digest, worker=worker_pin)
        model.write(b.output / "result.json", terminal)
        command = model.read(b.output / "process/process-inputs.json")
        command["command"][4] = b.digest
        model.write(b.output / "process/process-inputs.json", command)
    result = compare.compare_saved(_report(a), _report(b))
    assert all(row["authenticated"] for row in result["attempts"].values())
    assert result["status"] == "incompatible_provenance" and result["observations"] == []
    assert result["paired_execution_complete"] is False


def test_compare_retains_missing_and_failed_case_dispositions_and_partial_evidence(tmp_path):
    values = [
        _fixture(tmp_path, mode, endpoint="init_short_history") for mode in ("original", "disabled")
    ]
    outcome = model.read(values[1].worker / "demo/outcome.json")
    outcome.update(
        status="failed",
        methods_completed=False,
        primary={"type": "original source failure"},
        init_short_history_completed=False,
        init_time_steps_completed=0,
    )
    outcome["completed_stage_trials"].remove("init_short_history")
    model.write(values[1].worker / "demo/outcome.json", outcome)
    (values[1].output / "result.json").unlink()
    refs = [_report(value) for value in values]
    result = compare.compare_saved(*refs)
    assert result["attempts"]["disabled"]["authenticated"] is True
    assert result["attempts"]["disabled"]["status"] == "failed"
    assert result["attempts"]["disabled"]["saved_failure_records"] > 0
    assert result["paired_execution_complete"] is False and result["compared_observations"] > 0
    assert result["status"] == "compared_partial_or_failed_attempts"
    partial = next(
        row
        for row in result["observations"]
        if row["label"] == "tissue_INIT:init_short_history.after"
    )
    assert partial["disabled"]["stage_completed"] is False
    missing = compare.compare_saved(refs[0], None)
    assert missing["attempts"]["disabled"]["status"] == "missing_report"
    assert missing["all_available_observations_equal"] is None


@pytest.mark.parametrize("mutation", ("time", "sampled", "rng"))
def test_compare_keeps_actual_time_sample_and_RNG_differences(tmp_path, mutation):
    values = [
        _fixture(tmp_path, mode, endpoint="init_short_history") for mode in ("original", "disabled")
    ]
    value = values[1]
    folder = value.worker / "demo"
    captures = {row["label"]: row for row in model.read(folder / "outcome.json")["captures"]}
    record = model.read(folder / captures["init_short_history.record"]["path"])
    linkage = model.read(folder / captures["init_short_history.linkage"]["path"])
    if mutation == "rng":
        after = ["e" * 64, "d" * 64]
        record["rng_after"] = linkage["rng_after"] = after
        _replace(value, "init_short_history.stream_after", after)
    elif mutation == "time":
        bits = struct.pack("!d", 0.01).hex()
        record["iterations"][1][1] = linkage["iterations"][1]["source_time_bits"] = bits
        labels = [i * 0.00123456789 for i in range(5)]
        labels[1] = 0.01
        calendar = _cache(_array(struct.pack("<5d", *labels), shape=[5]))
        record["calendar"] = calendar["identity"]
        _replace(value, "init_short_history.calendar", calendar)
    else:
        record["iterations"][1][2] = linkage["iterations"][1]["sampled"] = True
        sampled = _cache_node(
            dict(
                kind="tuple",
                items=[
                    dict(
                        kind="numpy_scalar",
                        dtype="<f8",
                        bits=struct.pack("<d", i * 0.00123456789).hex(),
                    )
                    for i in range(3)
                ],
            )
        )
        record["sampled"] = sampled["identity"]
        _replace(value, "init_short_history.sampled", sampled)
    _replace(value, "init_short_history.record", record)
    _replace(value, "init_short_history.linkage", linkage)
    result = compare.compare_saved(*[_report(value) for value in values])
    assert all(row["authenticated"] for row in result["attempts"].values())
    assert result["paired_execution_complete"] is True
    assert result["all_available_observations_equal"] is False
    if mutation != "rng":
        assert result["timing"]["equal"] is False
    else:
        row = next(
            row
            for row in result["observations"]
            if row["label"] == "tissue_INIT:init_short_history.stream_after"
        )
        assert row["comparison"]["equal"] is False


def test_compare_detects_pin_drift_during_comparison_without_losing_saved_differences(
    tmp_path, monkeypatch
):
    _, refs = _pair(tmp_path)
    original = compare._differences
    once = []

    def observed(*args):
        result = original(*args)
        if not once:
            once.append(True)
            with compare.Path(refs[1]["report"]["path"]).open("ab") as stream:
                stream.write(b" ")
        return result

    monkeypatch.setattr(compare, "_differences", observed)
    result = compare.compare_saved(*refs)
    assert once and result["observations"]
    assert result["status"] == "evidence_changed_during_comparison"
    assert result["attempts"]["disabled"]["final_pin_error"]
    assert result["paired_execution_complete"] is False
    assert result["all_available_observations_equal"] is None


def test_compare_identity_only_placeholders_are_not_numeric_state_equality(tmp_path):
    values = [model.fixture(tmp_path, mode=mode) for mode in ("original", "disabled")]
    result = compare.compare_saved(*[_report(value) for value in values])
    assert result["paired_execution_complete"] is True
    assert result["compared_observations"] == 0
    assert result["all_available_observations_equal"] is None
    assert result["all_requested_observations_available"] is False


def test_compare_difference_limit_reports_exact_total_without_large_value_duplication():
    a, b = list(range(200)), list(range(1, 201))
    result = compare._differences(a, b)
    assert (
        result["difference_count"] == 200 and len(result["differences"]) == compare.MAX_DIFFERENCES
    )
    assert result["difference_list_complete"] is False
    shape = compare._differences({"data": {"big": list(range(1000))}}, {"data": None})
    assert shape["differences"][0]["original"]["container"] == "dict"
    assert len(json.dumps(shape)) < 1000


def test_compare_type_equal_boolean_and_integer_are_distinct_observations():
    result = compare._differences({"sampled": True}, {"sampled": 1})
    assert result["equal"] is False and result["difference_count"] == 1


def test_compare_refuses_changed_column_with_unchanged_descriptor(tmp_path):
    values = [_fixture(tmp_path, mode) for mode in ("original", "disabled")]
    cache = _cache()
    cache["columns"][0]["values"]["raw_bytes_hex"] = struct.pack("<2d", 9.0, 2.0).hex()
    _replace(values[1], "profiles.after", cache)
    result = compare.compare_saved(*[_report(value) for value in values])
    row = next(
        row for row in result["observations"] if row["label"] == "tissue_INIT:profiles.after"
    )
    assert row["disabled"]["status"] == "unverified_observation" and "comparison" not in row
    assert "layout/column bytes" in row["disabled"]["error"]["message"]


def test_compare_reports_expected_operator_omission_as_difference_not_repair(tmp_path):
    values = [_fixture(tmp_path, mode) for mode in ("original", "disabled")]
    template = _cache()
    array_node = json.loads(template["descriptor_json"])
    for value, mode in zip(values, ("original", "disabled"), strict=True):
        fields = [[dict(kind="str", value="lapENVinv"), array_node]]
        columns = list(template["columns"])
        flux = dict(kind="NoneType", value=None)
        if mode == "original":
            flux = dict(array_node, column="column_00001")
            columns.append(dict(name="column_00001", values=_array()))
        fields.append([dict(kind="str", value="lapENV_P_inv"), flux])
        _replace(value, "poisson.cache", _cache_node(dict(kind="dict", items=fields), columns))
    result = compare.compare_saved(*[_report(value) for value in values])
    row = next(row for row in result["observations"] if row["label"] == "tissue_INIT:poisson.cache")
    assert row["comparison"]["equal"] is False
    assert all(
        change["path"][:3] == ["descriptor", "items", 1]
        for change in row["comparison"]["differences"]
    )
    assert result["flux_modes"]["disabled"] == "only_flux_inverse_omitted"
    assert result["original_flux_defect_repaired"] is False


def _mt(*, position=624, gaussian=0.0):
    """Producer wire shape only; no RNG object, NumPy import or random draw."""
    state = ["MT19937", list(range(1, 625)), position, 0, gaussian]
    version = "synthetic-wire-fixture"
    return dict(
        state_json=json.dumps(state, separators=(",", ":")),
        numpy_version=version,
        identity=compare._seal(
            dict(rng_id=compare.NATIVE_RNG_ID, numpy_version=version, state=state)
        ),
    )


def _append(value, label, data, *, geometry=False):
    folder = value.worker / "demo"
    if geometry:
        folder /= "geometry"
    outcome = model.read(folder / "outcome.json")
    path = folder / ("producer-" + str(len(outcome["captures"])) + ".json")
    pin = model.write(path, data)
    outcome["captures"].append(
        dict(path=path.name, sha256=pin["sha256"], label=label, status="saved")
    )
    model.write(folder / "outcome.json", outcome)


def _producer_geometry(value):
    folder = value.worker / "demo/geometry"
    outcome = model.read(folder / "outcome.json")
    by_label = {row["label"]: row for row in outcome["captures"]}
    record_row = by_label["geometry.record"]
    record = model.read(folder / record_row["path"])
    stages = []
    for index, (name, _) in enumerate(record["stages"]):
        row = by_label["geometry.stage-" + name]
        row["label"] = f"geometry.stage_caches.{index}.1.cache"
        cache = _cache()
        model.write(folder / row["path"], cache)
        row["sha256"] = model.pin(folder / row["path"])["sha256"]
        stages.append([name, cache["identity"]])
    record["stages"] = stages
    record["cache"] = _cache()["identity"]
    stream = _mt()
    record.update(before_MT=stream["identity"], after_MT=stream["identity"])
    model.write(folder / record_row["path"], record)
    record_row["sha256"] = model.pin(folder / record_row["path"])["sha256"]
    phase_row = by_label["phase.record"]
    phase = model.read(folder / phase_row["path"])
    phase["stages"] = [hashlib.sha256(f"phase-stage-{i}".encode()).hexdigest() for i in range(4)]
    model.write(folder / phase_row["path"], phase)
    phase_row["sha256"] = model.pin(folder / phase_row["path"])["sha256"]
    for index in range(4):
        row = by_label[f"phase.stage_trials.{index}.cache.cache"]
        model.write(folder / row["path"], _cache())
        row["sha256"] = model.pin(folder / row["path"])["sha256"]
    model.write(folder / "outcome.json", outcome)
    _append(value, "geometry.stream_before", stream, geometry=True)
    _append(value, "geometry.stream_after", stream, geometry=True)
    lattice = model.read(folder / by_label["lattice.record"]["path"])
    lattice.update(rng_before=stream["identity"], rng_after=stream["identity"])
    _replace(value, "lattice.record", lattice, geometry=True)
    _append(value, "lattice.rng_before", stream, geometry=True)
    _append(value, "lattice.rng_after", stream, geometry=True)


def _producer_electrical(value, identities=None):
    identities = ["a" * 64, "b" * 64] if identities is None else identities
    folder = value.worker / "demo"
    rows = {row["label"]: row for row in model.read(folder / "outcome.json")["captures"]}
    record = model.read(folder / rows["init_electrical.record"]["path"])
    record.update(rng_before=identities, rng_after=identities)
    _replace(value, "init_electrical.record", record)
    _replace(value, "init_electrical.rng_before", identities)
    _replace(value, "init_electrical.rng_after", identities)
    history = model.read(folder / rows["init_short_history.record"]["path"])
    linkage = model.read(folder / rows["init_short_history.linkage"]["path"])
    history["rng_before"] = linkage["rng_before"] = identities
    _replace(value, "init_short_history.record", history)
    _replace(value, "init_short_history.linkage", linkage)
    _replace(value, "init_short_history.stream_before", identities)


def _drop(value, label, *, geometry=False):
    folder = value.worker / "demo"
    if geometry:
        folder /= "geometry"
    outcome = model.read(folder / "outcome.json")
    assert any(row["label"] == label for row in outcome["captures"])
    outcome["captures"] = [row for row in outcome["captures"] if row["label"] != label]
    model.write(folder / "outcome.json", outcome)


def test_compare_producer_labels_cover_all_intermediates_phase_caches_and_streams(tmp_path):
    values = [
        _fixture(tmp_path, mode, endpoint="init_short_history") for mode in ("original", "disabled")
    ]
    for value in values:
        _producer_geometry(value)
        _producer_electrical(value)
    result = compare.compare_saved(*[_report(value) for value in values])
    assert result["paired_execution_complete"] is True
    by_label = {row["label"]: row for row in result["observations"]}
    expected = [
        *(f"geometry:geometry.stage_caches.{i}.1.cache" for i in range(11)),
        *(f"geometry:phase.stage_trials.{i}.cache.cache" for i in range(4)),
        "geometry:geometry.stream_before",
        "geometry:geometry.stream_after",
        "geometry:lattice.rng_before",
        "geometry:lattice.rng_after",
        "tissue_INIT:init_electrical.rng_before",
        "tissue_INIT:init_electrical.rng_after",
    ]
    for key in expected:
        row = by_label[key]
        assert row["comparison"]["equal"] is True, key
        assert row["original"]["association"]["record_label"].endswith(".record")
    assert (
        by_label[expected[0]]["original"]["association"]["native_method"]
        == model.report.GEOMETRY_STAGES[0]
    )


@pytest.mark.parametrize("kind", ("intermediate", "phase_cache", "geometry_rng", "electrical_rng"))
def test_compare_producer_differences_survive_equal_final_cache(tmp_path, kind):
    values = [
        _fixture(tmp_path, mode, endpoint="init_short_history") for mode in ("original", "disabled")
    ]
    for value in values:
        _producer_geometry(value)
        _producer_electrical(value)
    value = values[1]
    folder = value.worker / "demo/geometry"
    rows = {row["label"]: row for row in model.read(folder / "outcome.json")["captures"]}
    if kind == "intermediate":
        label, cache = (
            "geometry.stage_caches.3.1.cache",
            _cache(_array(struct.pack("<2d", 9.0, 2.0))),
        )
        record = model.read(folder / rows["geometry.record"]["path"])
        record["stages"][3][1] = cache["identity"]
        _replace(value, "geometry.record", record, geometry=True)
        _replace(value, label, cache, geometry=True)
        key = "geometry:" + label
    elif kind == "phase_cache":
        label = "phase.stage_trials.2.cache.cache"
        _replace(value, label, _cache(_array(struct.pack("<2d", 9.0, 2.0))), geometry=True)
        key = "geometry:" + label
    elif kind == "geometry_rng":
        stream = _mt(position=623)
        record = model.read(folder / rows["geometry.record"]["path"])
        record["after_MT"] = stream["identity"]
        _replace(value, "geometry.record", record, geometry=True)
        _replace(value, "geometry.stream_after", stream, geometry=True)
        key = "geometry:geometry.stream_after"
    else:
        _producer_electrical(value, ["c" * 64, "d" * 64])
        key = "tissue_INIT:init_electrical.rng_after"
    result = compare.compare_saved(*[_report(value) for value in values])
    by_label = {row["label"]: row for row in result["observations"]}
    assert result["paired_execution_complete"] is True
    assert by_label["geometry:completed_geometry.cache"]["comparison"]["equal"] is True
    assert by_label[key]["comparison"]["equal"] is False
    assert result["all_available_observations_equal"] is False


@pytest.mark.parametrize(
    "label,geometry",
    (
        ("geometry.stage_caches.3.1.cache", True),
        ("phase.stage_trials.2.cache.cache", True),
        ("geometry.stream_after", True),
        ("init_electrical.rng_after", False),
    ),
)
def test_compare_producer_missing_capture_is_explicit_even_with_same_final_identity(
    tmp_path, label, geometry
):
    values = [
        _fixture(tmp_path, mode, endpoint="init_short_history") for mode in ("original", "disabled")
    ]
    for value in values:
        _producer_geometry(value)
        _producer_electrical(value)
    _drop(values[1], label, geometry=geometry)
    result = compare.compare_saved(*[_report(value) for value in values])
    key = ("geometry:" if geometry else "tissue_INIT:") + label
    row = next(row for row in result["observations"] if row["label"] == key)
    assert row["disabled"]["status"] == "missing_producer_observation"
    assert "comparison" not in row and result["all_requested_observations_available"] is False
    assert row["disabled"]["association"]["record_label"].endswith(".record")


def test_compare_producer_rng_unsupported_data_stays_an_explicit_row(tmp_path):
    values = [
        _fixture(tmp_path, mode, endpoint="init_short_history") for mode in ("original", "disabled")
    ]
    for value in values:
        _producer_electrical(value)
    _replace(values[1], "init_electrical.rng_before", {"unsupported_saved_fixture": True})
    result = compare.compare_saved(*[_report(value) for value in values])
    row = next(
        row
        for row in result["observations"]
        if row["label"] == "tissue_INIT:init_electrical.rng_before"
    )
    assert row["disabled"]["status"] == "unsupported_stream_observation"
    assert "comparison" not in row


def test_compare_producer_stage_slot_cannot_retarget_an_equal_final_cache(tmp_path):
    values = [_fixture(tmp_path, mode) for mode in ("original", "disabled")]
    for value in values:
        _producer_geometry(value)
    # A distinct valid intermediate is retained elsewhere, so the report's
    # identity-exists check still succeeds. The slot/record relation must fail.
    cache = _cache(_array(struct.pack("<2d", 8.0, 2.0)))
    _append(values[1], "geometry.helper_cache.cache", cache, geometry=True)
    folder = values[1].worker / "demo/geometry"
    row = next(
        r
        for r in model.read(folder / "outcome.json")["captures"]
        if r["label"] == "geometry.record"
    )
    record = model.read(folder / row["path"])
    record["stages"][3][1] = cache["identity"]
    _replace(values[1], "geometry.record", record, geometry=True)
    result = compare.compare_saved(*[_report(value) for value in values])
    target = next(
        r
        for r in result["observations"]
        if r["label"] == "geometry:geometry.stage_caches.3.1.cache"
    )
    assert target["disabled"]["status"] == "unverified_observation"
    assert "stage record identity" in target["disabled"]["error"]["message"]


@pytest.mark.parametrize("field", ("words", "gaussian_bits", "identity"))
def test_compare_producer_full_MT_wire_preserves_exact_bits_or_refuses_bad_identity(field):
    first = _mt()
    if field == "words":
        state = json.loads(first["state_json"])
        state[1][200] += 1
        second = dict(first, state_json=json.dumps(state, separators=(",", ":")))
        second["identity"] = compare._seal(
            dict(rng_id=compare.NATIVE_RNG_ID, numpy_version=second["numpy_version"], state=state)
        )
    elif field == "gaussian_bits":
        second = _mt(gaussian=-0.0)
    else:
        second = dict(first, identity="e" * 64)
    a = compare._observation(first, [])
    if field == "identity":
        with pytest.raises(ValueError, match="MT state identity"):
            compare._observation(second, [])
    else:
        b = compare._observation(second, [])
        assert compare._differences(a, b)["equal"] is False


def _terminal_observation_model(tmp_path, *, count=3):
    """Isolated pinned capture reader, never a completed-report or live-owner fixture."""
    folder = tmp_path / "isolated-terminal" / "worker" / "demo"
    folder.mkdir(parents=True)
    snapshots = {
        "before": _cache(),
        "after": _cache(_array(struct.pack("<2d", 5.0, 6.0))),
        "calendar": _cache(
            _array(
                struct.pack("<" + "d" * count, *(i * 0.125 for i in range(count))), shape=[count]
            )
        ),
        "sampled": _cache_node(dict(kind="tuple", items=[])),
        "configured_dt": _cache_node(dict(kind="float", bits=struct.pack("<d", 0.125).hex())),
    }
    streams = ["a" * 64, "b" * 64]
    record = dict(
        identity="c" * 64,
        **{
            ("dt" if name == "configured_dt" else name): cache["identity"]
            for name, cache in snapshots.items()
        },
        rng_before=streams,
        rng_after=streams,
        source_completed=True,
        loop_returned=True,
        context_returned=True,
        selected_stop=False,
        iterations=[
            [
                i,
                struct.pack("!d", i * 0.125).hex(),
                i % 2 == 0,
                snapshots["after"]["identity"],
                i + 1,
                i + 1,
                100 + i,
                None,
            ]
            for i in range(count)
        ],
    )
    rows = []
    observations = dict(snapshots, record=record, stream_before=streams, stream_after=streams)
    observations.update({f"iteration.{i:04d}.after": snapshots["after"] for i in range(count)})
    for name, value in observations.items():
        path = folder / (name + ".json")
        pin = model.write(path, value)
        rows.append(
            dict(
                label="init_terminal." + name, path=path.name, sha256=pin["sha256"], status="saved"
            )
        )
    model.write(
        folder / "outcome.json", dict(captures=rows, completed_stage_trials=["init_terminal"])
    )
    return folder, record


def _terminal_capture_side(folder):
    reader = compare.report.Reader()
    reader.bind(model.pin(folder / "outcome.json"))
    for row in model.read(folder / "outcome.json")["captures"]:
        reader.bind(dict(path=str(folder / row["path"]), sha256=row["sha256"]))
    return dict(authenticated=True, saved=dict(output=str(folder.parent.parent)), reader=reader)


def _terminal_replace_capture(folder, label, value):
    outcome = model.read(folder / "outcome.json")
    row = next(row for row in outcome["captures"] if row["label"] == label)
    row["sha256"] = model.write(folder / row["path"], value)["sha256"]
    model.write(folder / "outcome.json", outcome)


@pytest.mark.parametrize("count", (1, 3, 64, 500, 512))
def test_compare_terminal_pinned_observations_keep_complete_ordered_time_and_streams(
    tmp_path, count
):
    folder, record = _terminal_observation_model(tmp_path, count=count)
    side = _terminal_capture_side(folder)
    observations = compare._observations(side)
    timing = compare._load_observation(side, observations["tissue_INIT:init_terminal.record"])
    assert timing["natural_terminal"] == dict(
        source_completed=True,
        loop_returned=True,
        context_returned=True,
        selected_stop=False,
        completed_iterations=count,
    )
    assert [row["source_time_bits"] for row in timing["values"]] == [
        row[1] for row in record["iterations"]
    ]
    assert [row["sampled"] for row in timing["values"]] == [row[2] for row in record["iterations"]]
    for name in (
        "before",
        "after",
        "calendar",
        "sampled",
        "configured_dt",
        "stream_before",
        "stream_after",
        *(f"iteration.{i:04d}.after" for i in range(count)),
    ):
        item = observations["tissue_INIT:init_terminal." + name]
        assert item["association"]["record_label"] == "init_terminal.record"
        assert compare._load_observation(side, item) is not None
    assert compare.source_plan()["scientific_credit"] == 0


@pytest.mark.parametrize(
    "field", ("source_completed", "loop_returned", "context_returned", "selected_stop")
)
@pytest.mark.parametrize("fault", ("opposite", "integer", "missing"))
def test_compare_terminal_stopped_or_untyped_return_flags_never_become_normal_completion(
    tmp_path, field, fault
):
    folder, record = _terminal_observation_model(tmp_path)
    if fault == "opposite":
        record[field] = not record[field]
    elif fault == "integer":
        record[field] = int(record[field])
    else:
        del record[field]
    _terminal_replace_capture(folder, "init_terminal.record", record)
    side = _terminal_capture_side(folder)
    rows = compare._observations(side)
    item = rows["tissue_INIT:init_terminal.record"]
    assert compare._load_observation(side, item) is None
    assert item["status"] == "unverified_observation"
    assert "normal INIT returns" in item["error"]["message"]
    assert compare._load_observation(side, rows["tissue_INIT:init_terminal.before"]) is not None


@pytest.mark.parametrize(
    "label",
    (
        "before",
        "after",
        "calendar",
        "sampled",
        "configured_dt",
        "stream_before",
        "stream_after",
        "iteration.0001.after",
    ),
)
def test_compare_terminal_missing_record_referenced_capture_stays_explicit(tmp_path, label):
    folder, _ = _terminal_observation_model(tmp_path)
    outcome = model.read(folder / "outcome.json")
    outcome["captures"] = [
        row for row in outcome["captures"] if row["label"] != "init_terminal." + label
    ]
    model.write(folder / "outcome.json", outcome)
    side = _terminal_capture_side(folder)
    item = compare._observations(side)["tissue_INIT:init_terminal." + label]
    assert item["status"] == "missing_producer_observation"
    assert item["association"]["record_label"] == "init_terminal.record"
    assert compare._load_observation(side, item) is None


@pytest.mark.parametrize(
    "label", ("before", "after", "calendar", "iteration.0001.after", "stream_after")
)
def test_compare_terminal_capture_retarget_refuses_even_with_rehashed_valid_payload(
    tmp_path, label
):
    folder, _ = _terminal_observation_model(tmp_path)
    value = (
        ["d" * 64, "b" * 64]
        if label == "stream_after"
        else _cache(_array(struct.pack("<2d", 7.0, 8.0)))
    )
    _terminal_replace_capture(folder, "init_terminal." + label, value)
    side = _terminal_capture_side(folder)
    item = compare._observations(side)["tissue_INIT:init_terminal." + label]
    assert compare._load_observation(side, item) is None
    assert item["status"] == "unverified_observation"


@pytest.mark.parametrize("change", ("signed_zero", "time", "sample", "count"))
def test_compare_terminal_exact_timing_differences_remain_observations(tmp_path, change):
    _, left = _terminal_observation_model(tmp_path / "left")
    _, right = _terminal_observation_model(tmp_path / "right")
    if change == "signed_zero":
        right["iterations"][0][1] = struct.pack("!d", -0.0).hex()
    elif change == "time":
        right["iterations"][1][1] = struct.pack("!d", 0.12500000001).hex()
    elif change == "sample":
        right["iterations"][1][2] = True
    else:
        right["iterations"].pop()
    a, b = (compare._iteration_observation(value, natural_terminal=True) for value in (left, right))
    difference = compare._differences(a, b)
    assert difference["equal"] is False and difference["difference_count"] > 0
    assert left["iterations"][0][1] == "0000000000000000"


def test_compare_terminal_endpoint_does_not_relabel_legacy_selected_history(tmp_path):
    _, record = _terminal_observation_model(tmp_path)
    record.update(loop_returned=False, context_returned=False, selected_stop=True)
    legacy = compare._iteration_observation(record)
    assert set(legacy) == {"kind", "values"}
    assert len(legacy["values"]) == 3
    with pytest.raises(ValueError, match="normal INIT returns"):
        compare._iteration_observation(record, natural_terminal=True)


@pytest.mark.parametrize("count,natural", ((65, False), (513, True)))
def test_compare_terminal_count_capacity_stays_separate_from_short_history(count, natural):
    record = dict(
        iterations=[
            [i, "0000000000000000", False, "a" * 64, 0, 0, None, None] for i in range(count)
        ],
        source_completed=True,
        loop_returned=True,
        context_returned=True,
        selected_stop=False,
    )
    with pytest.raises(ValueError, match="Bounded iteration records"):
        compare._iteration_observation(record, natural_terminal=natural)


def _terminal_records(value):
    folder = value.worker / "demo"
    rows = {row["label"]: row for row in model.read(folder / "outcome.json")["captures"]}
    return tuple(
        model.read(folder / rows["init_terminal." + name]["path"]) for name in ("record", "linkage")
    )


def _terminal_sample_cache(rows):
    return _cache_node(
        dict(
            kind="tuple",
            items=[
                dict(kind="numpy_scalar", dtype="<f8", bits=bytes.fromhex(row[1])[::-1].hex())
                for row in rows
                if row[2]
            ],
        )
    )


def _terminal_report_fixture(tmp_path, mode, *, count=3):
    """Complete inert saved attempt, read by the actual report and payload verifiers."""
    value = _fixture(tmp_path, mode, endpoint="init_terminal", iterations=count)
    record, linkage = _terminal_records(value)
    replacements = dict(
        before=_cache(),
        after=_cache(_array(struct.pack("<2d", 3.0, 4.0))),
        sampled=_terminal_sample_cache(record["iterations"]),
        configured_dt=_cache_node(dict(kind="float", bits=struct.pack("<d", 0.001).hex())),
    )
    # Keep the producer fixture's complete, typed calendar and all its original
    # time labels. These state payloads are synthetic, not a live INIT replay.
    for name, cache in replacements.items():
        _replace(value, "init_terminal." + name, cache)
        record["dt" if name == "configured_dt" else name] = cache["identity"]
    for ordinal, row in enumerate(record["iterations"]):
        cache = replacements["after"] if ordinal == count - 1 else replacements["before"]
        row[3] = linkage["iterations"][ordinal]["after_identity"] = cache["identity"]
        _replace(value, f"init_terminal.iteration.{ordinal:04d}.after", cache)
    _replace(value, "init_terminal.record", record)
    _replace(value, "init_terminal.linkage", linkage)
    return value


@pytest.mark.parametrize("count", (3, 500, 512))
def test_compare_terminal_real_report_verifier_accepts_only_complete_paired_calendars(
    tmp_path, count
):
    values = [
        _terminal_report_fixture(tmp_path, mode, count=count) for mode in ("original", "disabled")
    ]
    refs = [_report(value) for value in values]
    for ref in refs:
        saved = model.read(compare.Path(ref["report"]["path"]))
        assert saved["status"] == "completed_unqualified"
        assert saved["init_iterations_requested"] is None
        terminal = saved["demonstration"]["natural_terminal"]
        assert terminal["recorded_iterations"] == terminal["configured_iterations"] == count
        assert terminal["selected_stop"] is False
    result = compare.compare_saved(*refs)
    assert result["status"] == "compared_completed_attempts"
    assert result["paired_execution_complete"] is True
    assert all(row["authenticated"] for row in result["attempts"].values())
    assert result["timing"]["equal"] is True
    assert result["all_available_observations_equal"] is True
    terminal_rows = [
        row
        for row in result["observations"]
        if row["label"].startswith("tissue_INIT:init_terminal.")
    ]
    assert len([row for row in terminal_rows if ".iteration." in row["label"]]) == count
    assert all(row["comparison"]["equal"] for row in terminal_rows)
    assert all(row["original"]["stage_completed"] for row in terminal_rows)
    assert result["domain_diagnostics"]["original"]["support"]["maskM"]["nonzero"] == 0
    assert result["physical_parity"] is result["original_flux_defect_repaired"] is False
    assert result["ordinary_checkpoint_admitted"] is False and result["scientific_credit"] == 0


@pytest.mark.parametrize("change", ("state", "signed_zero_time", "sampled", "rng"))
def test_compare_terminal_real_report_verifier_keeps_exact_mode_differences(tmp_path, change):
    values = [_terminal_report_fixture(tmp_path, mode) for mode in ("original", "disabled")]
    value = values[1]
    record, linkage = _terminal_records(value)
    label = "init_terminal.record"
    if change == "state":
        label = "init_terminal.after"
        cache = _cache(_array(struct.pack("<2d", 3.0, -0.0)))
        record["after"] = record["iterations"][-1][3] = cache["identity"]
        linkage["iterations"][-1]["after_identity"] = cache["identity"]
        _replace(value, label, cache)
        _replace(value, "init_terminal.iteration.0002.after", cache)
    elif change == "rng":
        label = "init_terminal.stream_after"
        record["rng_after"] = linkage["rng_after"] = ["e" * 64, "d" * 64]
        _replace(value, label, record["rng_after"])
    else:
        if change == "signed_zero_time":
            bits = struct.pack("!d", -0.0).hex()
            record["iterations"][0][1] = linkage["iterations"][0]["source_time_bits"] = bits
            calendar = model.terminal_calendar_cache(record["iterations"])
            record["calendar"] = calendar["identity"]
            _replace(value, "init_terminal.calendar", calendar)
        else:
            record["iterations"][1][2] = linkage["iterations"][1]["sampled"] = True
        sampled = _terminal_sample_cache(record["iterations"])
        record["sampled"] = sampled["identity"]
        _replace(value, "init_terminal.sampled", sampled)
    _replace(value, "init_terminal.record", record)
    _replace(value, "init_terminal.linkage", linkage)
    result = compare.compare_saved(*[_report(value) for value in values])
    assert all(row["authenticated"] for row in result["attempts"].values())
    assert result["paired_execution_complete"] is True
    assert result["all_available_observations_equal"] is False
    observed = next(row for row in result["observations"] if row["label"] == "tissue_INIT:" + label)
    assert observed["comparison"]["equal"] is False
    assert result["numerical_or_conservation_qualification"] is False


@pytest.mark.parametrize(
    "fault",
    ("selected_stop", "missing_calendar", "retarget_after", "short_calendar", "integer_return"),
)
def test_compare_terminal_actual_report_failure_cannot_be_promoted_by_valid_new_hashes(
    tmp_path, fault
):
    values = [_terminal_report_fixture(tmp_path, mode) for mode in ("original", "disabled")]
    value = values[1]
    record, linkage = _terminal_records(value)
    if fault == "selected_stop":
        record["selected_stop"] = linkage["selected_stop"] = True
        _replace(value, "init_terminal.record", record)
        _replace(value, "init_terminal.linkage", linkage)
    elif fault == "missing_calendar":
        _drop(value, "init_terminal.calendar")
    elif fault == "retarget_after":
        _replace(
            value,
            "init_terminal.iteration.0001.after",
            _cache(_array(struct.pack("<2d", 7.0, 8.0))),
        )
    elif fault == "short_calendar":
        calendar = model.terminal_calendar_cache(record["iterations"][:-1])
        record["calendar"] = calendar["identity"]
        _replace(value, "init_terminal.calendar", calendar)
        _replace(value, "init_terminal.record", record)
    else:
        record["context_returned"] = linkage["context_returned"] = 1
        _replace(value, "init_terminal.record", record)
        _replace(value, "init_terminal.linkage", linkage)
    refs = [_report(value) for value in values]
    rejected = model.read(compare.Path(refs[1]["report"]["path"]))
    assert rejected["source_evidence_complete"] is False and rejected["verification_issues"]
    result = compare.compare_saved(*refs)
    assert result["attempts"]["disabled"]["authenticated"] is True
    assert result["attempts"]["disabled"]["complete"] is False
    assert result["paired_execution_complete"] is False
    # A rejected whole outcome cannot establish its molecular selection. The
    # comparator retains that report and refuses before comparing partial data.
    assert result["status"] == "incompatible_provenance"
    assert result["provenance"]["init_native_molecules"] is False
    assert all(
        equal for key, equal in result["provenance"].items() if key != "init_native_molecules"
    )
    assert result["observations"] == []
    assert result["attempts"]["disabled"]["saved_verification_issues"]


def test_compare_terminal_real_report_retains_failed_source_and_partial_snapshots(tmp_path):
    values = [_terminal_report_fixture(tmp_path, mode) for mode in ("original", "disabled")]
    value = values[1]
    outcome = model.read(value.worker / "demo/outcome.json")
    outcome.update(
        status="failed",
        methods_completed=False,
        primary={"type": "OriginalSourceFailure", "message": "retained synthetic failure"},
        init_terminal_completed=False,
        init_time_steps_completed=0,
    )
    outcome["completed_stage_trials"].remove("init_terminal")
    model.write(value.worker / "demo/outcome.json", outcome)
    (value.output / "result.json").unlink()
    result = compare.compare_saved(*[_report(value) for value in values])
    assert result["attempts"]["disabled"]["authenticated"] is True
    assert result["attempts"]["disabled"]["status"] == "failed"
    assert result["attempts"]["disabled"]["saved_failure_records"] > 0
    assert result["paired_execution_complete"] is False and result["compared_observations"] > 0
    partial = next(
        row for row in result["observations"] if row["label"] == "tissue_INIT:init_terminal.after"
    )
    assert partial["disabled"]["stage_completed"] is False
    assert partial["comparison"]["equal"] is True


def test_compare_terminal_real_report_never_relabels_selected_history(tmp_path):
    terminal = _terminal_report_fixture(tmp_path, "original")
    history = _fixture(tmp_path, "disabled", endpoint="init_short_history")
    result = compare.compare_saved(_report(terminal), _report(history))
    assert all(row["authenticated"] for row in result["attempts"].values())
    assert result["status"] == "incompatible_provenance"
    assert result["provenance"]["endpoint"] is False
    assert result["paired_execution_complete"] is False and result["observations"] == []
