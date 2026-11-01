"""Blocked recipe/comparison/observer controls; no released four-call trajectory."""

import copy
import json
import sys
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace

import numpy as np
import pytest

from tests.unit.test_betse_normal_ecm_molecule_material_four_call_reference import (
    no_reference_work as no_reference_work,
)
from validation.betse import betse_normal_ecm_molecule_material_four_call as q


@pytest.fixture(autouse=True)
def no_material_work(tmp_path):
    previous, attempted = sys.getprofile(), []
    module = q.primitive.material
    functions = (
        module.bind,
        module.state,
        module.drive,
        module._state_values,
        module.validate_binding,
        module._step_source.__wrapped__,
        q.primitive.begin,
        q.primitive.Execution.advance,
    )
    codes = {id(f.__code__) for f in functions}

    def guard(frame, event, arg):
        if event == "call" and id(frame.f_code) in codes:
            attempted.append(frame.f_code.co_name)
            raise AssertionError("Actual primitive/material body forbidden in preparation controls")
        if previous is not None:
            previous(frame, event, arg)

    sys.setprofile(guard)
    yield attempted
    sys.setprofile(previous)
    (tmp_path / "material-blocked.json").write_text(
        json.dumps(dict(attempted=attempted, actual_source_entries=0))
    )
    assert attempted == []


def test_real_existing_fixture_prefix_and_explicit_fourth_packet_are_one_sequence():
    old = q.fixtures.fixture("slow")
    value = q.program()
    assert value["definition"] == old["definition"] and value["initial"] == old["initial"]
    assert value["steps"][:3] == old["steps"] and len(value["steps"]) == 4
    assert len(old["steps"]) == 3
    for key in old["steps"][2]:
        if key not in {"junction_block", "boundary_mol_m3"}:
            assert value["steps"][3][key] == old["steps"][2][key]
    assert value["steps"][3]["junction_block"] == [0.79] * 9
    assert value["steps"][3]["boundary_mol_m3"] == [23.15, 26.15, 29.15, 32.15]
    q.validate_program(value)
    domain = q.declared_domain()
    assert domain.budget.source_calls == 4 and not hasattr(domain, "current")
    plan = q.source_plan()
    assert plan["independent_input_sequences"] == 1 and plan["independent_biological_cases"] == 0
    assert plan["historical_failed_parent"]["status"] == "failed_independent_accuracy"
    assert plan["original_failed_case_not_repaired"]
    assert sum(plan["actual_work"].values()) == 19


def test_actual_declared_fixture_graph_round_trips_without_category_or_alias_rebase(tmp_path):
    value = q.program()
    path = q.archive(tmp_path / "declared-program", value)
    restored = q.read_archive(path)
    q.validate_program(restored)
    assert q.primitive.codec.fingerprint(restored) == q.primitive.codec.fingerprint(value)


@pytest.mark.parametrize("layout", ["reshape", "fortran", "reverse", "readonly", "bytes", "empty"])
def test_array_view_evidence_preserves_bits_layout_bases_and_repeated_identity(tmp_path, layout):
    root = np.arange(12, dtype=">f8")
    root.view(">u8")[:3] = [0x8000000000000000, 0x7FF8000000000017, 0x7FF0000000000000]
    view = root.reshape(3, 4)
    if layout == "fortran":
        root = np.array(view, order="F", copy=True)
        view = root[:, :2]
    elif layout == "reverse":
        view = view[::-1, ::-1]
    elif layout == "readonly":
        root.setflags(write=False)  # The previously created view remains writable.
    elif layout == "bytes":
        root = np.frombuffer(root.tobytes(), dtype=">f8")
        view = root.reshape(3, 4)
    elif layout == "empty":
        view = view[:0]
    before = (view.base, view.strides, view.flags.writeable, view.tobytes(), root.tobytes())
    path = q.archive(tmp_path / "views", dict(view=view, repeated=view, root=root))
    restored, rows = q.read_archive(path, with_array_observations=True)
    assert restored["view"] is restored["repeated"]
    assert restored["view"].dtype.str == view.dtype.str
    assert restored["view"].shape == view.shape and restored["view"].tobytes() == before[3]
    row = next(r for r in rows if r["logical_snapshot"] is restored["view"])
    assert row["strides"] == list(view.strides) and row["writable"] == before[2]
    assert row["owns_data"] == bool(view.flags.owndata)
    assert row["base"] is not None
    base = rows[row["base"]]
    assert base["logical_snapshot"].tobytes() == view.base.tobytes()
    assert row["offset_bytes"] == (
        view.__array_interface__["data"][0] - view.base.__array_interface__["data"][0]
    )
    assert view.base is before[0] and view.strides == before[1]
    assert view.flags.writeable == before[2] and view.tobytes() == before[3]
    assert root.tobytes() == before[4]
    assert not np.shares_memory(restored["view"], view)
    assert not np.shares_memory(restored["view"], restored["root"])
    manifest = json.loads((path / "manifest.json").read_text())
    assert manifest["owner_admission"] is False
    assert manifest["live_array_aliases_reconstructed"] is False


def test_array_view_capture_does_not_relax_original_checkpoint_codec(tmp_path):
    value = np.arange(6.0).reshape(2, 3)
    with pytest.raises(ValueError, match="unowned aliasing"):
        q.primitive.codec.Encoder().capture(value)
    q.archive(tmp_path / "observation", value)
    with pytest.raises(ValueError, match="unowned aliasing"):
        q.primitive.codec.Encoder().capture(value)


def test_array_view_evidence_counts_hidden_base_bytes_before_copy(tmp_path):
    root = np.arange(24.0)
    view = root[1:2]
    limits = replace(q.primitive.codec.DEFAULT_LIMITS, expanded_bytes=16)
    with pytest.raises(ValueError, match="numeric byte bound"):
        q.EvidenceEncoder(limits).capture(view)
    assert root.size == 24 and view.base is root


def test_array_view_evidence_refuses_object_or_unknown_base_without_conversion(monkeypatch):
    objects = np.array([object()], dtype=object)
    raw = np.arange(8.0)
    outside = np.lib.stride_tricks.as_strided(raw, shape=(2,), strides=(8,))
    nested = outside[::1]
    memoryview_backed = np.frombuffer(memoryview(bytearray(16)), dtype=np.float64)
    attempted = []

    def forbidden(*args, **kwargs):
        attempted.append("array copy")
        raise AssertionError("Unsupported storage must refuse before data copy")

    monkeypatch.setattr(q.np, "array", forbidden)
    with pytest.raises(ValueError, match="dtype"):
        q.EvidenceEncoder().capture(objects)
    for value in (outside, nested, memoryview_backed):
        with pytest.raises(ValueError, match="Unsupported evidence array base"):
            q.EvidenceEncoder().capture(value)
    assert attempted == []


def test_array_view_reader_retains_original_v1_evidence(tmp_path):
    path = tmp_path / "original"
    path.mkdir()
    encoder = q.primitive.codec.Encoder()
    tree = encoder.capture(dict(original=np.array([-0.0])))
    encoder.write(path, tree)
    q.snapshot.write_json(
        path / "manifest.json",
        dict(
            kind="cells.material_four_call_evidence@1",
            owner_admission=False,
            fingerprint=encoder.seal(tree),
            files={n: q.ref(path / n) for n in ("state.json", "arrays.npz")},
        ),
    )
    value, observations = q.read_archive(path, with_array_observations=True)
    assert observations == [] and value["original"].tobytes() == np.array([-0.0]).tobytes()


@pytest.mark.parametrize(
    "fault", ["missing", "initial", "definition", "fourth", "order", "duplicate"]
)
def test_foreign_changed_or_omitted_fixture_authority_refuses(fault):
    value = q.program()
    if fault == "missing":
        value["steps"].pop()
    elif fault == "initial":
        value["initial"]["voltage_V"][0] += 1.0
    elif fault == "definition":
        value["definition"]["provenance"] = "foreign"
    elif fault == "fourth":
        value["steps"][3]["boundary_mol_m3"][0] += 1.0
    elif fault == "order":
        value["steps"][0], value["steps"][3] = value["steps"][3], value["steps"][0]
    else:
        value["steps"][3] = value["steps"][2]
    with pytest.raises(ValueError):
        q.validate_program(value)


def synthetic_histories(monkeypatch):
    """Scalar comparison controls only, never material owner/trajectory evidence."""
    m = q.primitive.material
    values = m.Values(*(np.zeros((1, 1), dtype=np.float64) for _ in m.Values._fields))
    diagnostics = {key: np.zeros(1) for key in q.checks.LEDGERS} | dict(finite=True)
    rows = []
    for index in range(4):
        candidate = m.State("synthetic", index + 1, values, "synthetic-state-" + str(index + 1))
        rows.append(
            m.Trial(
                "synthetic",
                "synthetic-state-" + str(index),
                None,
                (m.Frame("initial", None, values), m.Frame("membrane_commit", "Na", values)),
                (),
                candidate,
                copy.deepcopy(diagnostics),
                "synthetic-trial-" + str(index),
            )
        )

    def provider(row):
        return dict(
            frames=[
                dict(stage=f.stage, ion_id=f.ion_id, values=copy.deepcopy(f.values._asdict()))
                for f in row.frames
            ],
            environment_records=[],
            candidate=copy.deepcopy(row.candidate.values._asdict()),
            source_completed=True,
            ledgers=copy.deepcopy(diagnostics),
            conservative_exchange=[
                dict(
                    ion_id="Na",
                    balance_residual_mol=0.0,
                    cell_mol_m3=np.zeros(1),
                    environment_mol_m3=np.zeros(1),
                )
            ],
        )

    native = dict(
        history=[provider(r) for r in rows],
        failure=None,
        warnings=[],
        RNG_unchanged=True,
        native_source_sha256=q.source_plan()["native_source"]["source_sha256"],
        geometry=dict(synthetic=True),
    )
    first = dict(history=[provider(r) for r in rows])
    second = copy.deepcopy(first)
    geometry = SimpleNamespace(_asdict=lambda: dict(synthetic=True))
    binding = SimpleNamespace(
        source=SimpleNamespace(
            geometry_binding=SimpleNamespace(
                geometry=geometry, current_binding=SimpleNamespace(ion_ids=("Na",))
            )
        )
    )
    monkeypatch.setattr(
        q.checks,
        "geometry_compare",
        lambda a, b: a == b or pytest.fail("Synthetic geometry differs"),
    )
    return rows, copy.deepcopy(rows[:3]), native, first, second, binding


def test_comparison_distinguishes_byte_value_and_independent_diagnostic_results(
    monkeypatch, tmp_path
):
    args = synthetic_histories(monkeypatch)
    result = q.compare_histories(*args)
    assert [r["absolute_index"] for r in result] == [0, 1, 2, 3]
    assert all(
        r["byte_agreement"] and r["source_value_exact"] and r["independent_error_fraction"] == 0
        for r in result
    )
    assert all(
        r["reference_resolution_fraction"] == 0 and r["diagnostics"]["finite"] for r in result
    )
    path = q.archive(tmp_path / "synthetic-comparison", dict(synthetic_only=True, results=result))
    assert q.read_archive(path)["synthetic_only"]


def test_signed_zero_byte_difference_is_explicit_and_does_not_change_value_tolerance(monkeypatch):
    args = synthetic_histories(monkeypatch)
    args[2]["history"][3]["candidate"]["voltage_V"][0, 0] = -0.0
    result = q.compare_histories(*args)
    assert result[3]["source_value_exact"] and not result[3]["byte_agreement"]
    assert result[3]["byte_mismatches"] == ["candidate.voltage_V"]
    assert result[3]["independent_error_fraction"] == 0


@pytest.mark.parametrize(
    "fault",
    [
        "native-value",
        "native-shape",
        "metadata",
        "fourth-epoch",
        "legacy-identity",
        "native-failure",
        "RNG",
        "missing",
        "precision",
        "oracle",
        "finite",
    ],
)
def test_nonvacuous_full_history_comparison_refuses_wrong_source_precision_or_domain(
    monkeypatch, fault
):
    rows, legacy, native, first, second, binding = synthetic_histories(monkeypatch)
    if fault == "native-value":
        native["history"][3]["candidate"]["voltage_V"][0, 0] = 1.0
    elif fault == "native-shape":
        native["history"][3]["candidate"]["voltage_V"] = np.zeros(2)
    elif fault == "metadata":
        native["history"][3]["frames"][0]["stage"] = "wrong-order"
    elif fault == "fourth-epoch":
        rows[3] = replace(rows[3], candidate=replace(rows[3].candidate, step_index=1))
    elif fault == "legacy-identity":
        legacy[0] = replace(legacy[0], candidate=replace(legacy[0].candidate, identity="foreign"))
    elif fault == "native-failure":
        native["failure"] = dict(type="retained native error")
    elif fault == "RNG":
        native["RNG_unchanged"] = False
    elif fault == "missing":
        rows.pop()
    elif fault == "precision":
        second["history"][3]["candidate"]["cell_mol_m3"][0, 0] = 1.0
    elif fault == "oracle":
        first["history"][3]["conservative_exchange"][0]["balance_residual_mol"] = 1e-20
    else:
        rows[3] = replace(rows[3], diagnostics=dict(rows[3].diagnostics, finite=False))
    with pytest.raises((AssertionError, ValueError)):
        q.compare_histories(rows, legacy, native, first, second, binding)


def test_complete_decimal_coefficients_and_tuple_numpy_categories_are_retained(tmp_path):
    raw = dict(first=Decimal("-0.000"), second=Decimal("1.23456789012345678901234567890123456789"))
    path = q.archive(
        tmp_path / "Decimal-exact", dict(raw=raw, rounded=np.float64(-0.0), zero=np.array(-0.0))
    )
    restored = q.read_archive(path)
    for key, value in raw.items():
        row = restored["raw"][key]
        assert Decimal(row[1]).as_tuple() == value.as_tuple()
    assert type(restored["rounded"]) is np.float64 and restored["zero"].shape == ()


def test_four_call_sized_synthetic_Decimal160_archive_stays_within_closed_JSON_budget(tmp_path):
    # 36,000 leaves exceed the selected four-call material snapshots/local
    # buffers (~33,000). This is representation work, not a Decimal oracle run.
    value = Decimal("1." + "1234567890" * 16)
    path = q.archive(
        tmp_path / "large-Decimal160-control",
        dict(synthetic_only=True, coefficients=[value for _ in range(36_000)]),
    )
    assert (path / "state.json").stat().st_size < q.primitive.codec.DEFAULT_LIMITS.json_bytes
    restored = q.read_archive(path)
    assert len(restored["coefficients"]) == 36_000
    assert restored["coefficients"][-1][0] == "exact_Decimal"
    assert Decimal(restored["coefficients"][-1][1]).as_tuple() == value.as_tuple()


@pytest.mark.parametrize("gate", [("0", "0"), ("1", "0"), ("0", "1"), ("1", "1")])
def test_worker_requires_explicit_Root_release_before_packet_or_output(monkeypatch, tmp_path, gate):
    for n, v in zip(q.reference.RELEASES, gate, strict=True):
        monkeypatch.setenv(n, v)
    monkeypatch.setattr(q, "packet_inputs", lambda *a: pytest.fail("Held worker read packet"))
    with pytest.raises(ValueError, match="remains held"):
        q.worker(
            tmp_path / "output", packet=tmp_path / "absent", packet_sha256="none", enabled=False
        )
    assert not (tmp_path / "output").exists()


def mock_packet(monkeypatch, tmp_path):
    for name in q.reference.RELEASES:
        monkeypatch.setenv(name, "1")
    packet = tmp_path / "packet"
    packet.mkdir()
    monkeypatch.setattr(
        q, "packet_inputs", lambda *args: (q.program(), dict(repository=str(tmp_path / "repo")))
    )
    return packet


@pytest.mark.parametrize("mediated", [False, True])
def test_released_output_containment_refuses_before_any_evidence_or_model(
    monkeypatch, tmp_path, mediated
):
    packet = mock_packet(monkeypatch, tmp_path)
    target = packet / "output"
    if mediated:
        link = tmp_path / "link"
        link.symlink_to(packet, target_is_directory=True)
        target = link / "output"
    with pytest.raises(ValueError, match="Output cannot modify"):
        q.worker(target, packet=packet, packet_sha256="synthetic", enabled=True)
    assert list(packet.iterdir()) == []


def fake_work(monkeypatch, seen):
    class Work:
        def __init__(self, stream):
            self.stage = None
            self.partials = []
            self.capture_errors = []

        def start(self):
            seen.append("observer-start")

        def stop(self):
            seen.append("observer-stop")
            return dict(
                profile_intact=True, active_invocations=0, capture_errors=[], absolute_indices={}
            )

    monkeypatch.setattr(q, "Work", Work)


@pytest.mark.parametrize("secondary", [False, True])
def test_source_failure_keeps_primary_chain_partial_and_accounting_on_secondary_IO(
    monkeypatch, tmp_path, secondary
):
    packet = mock_packet(monkeypatch, tmp_path)
    seen = []
    fake_work(monkeypatch, seen)
    primary, cause = ValueError("synthetic source construction failed"), TypeError("original cause")
    primary.__cause__ = cause
    primary.partial = dict(original_input=np.array([2.0, -0.0]), failed_trial="retained")

    def fail(*args):
        seen.append("source-stub")
        raise primary

    monkeypatch.setattr(q.primitive, "begin", fail)
    old = q.archive

    def capture(path, payload):
        if secondary and path.name == "primitive-begin":
            raise OSError("secondary diagnostic I/O")
        return old(path, payload)

    monkeypatch.setattr(q, "archive", capture)
    output = tmp_path / "output"
    with pytest.raises(ValueError) as caught:
        q.worker(output, packet=packet, packet_sha256="synthetic", enabled=True)
    assert caught.value is primary and primary.__cause__ is cause
    assert seen == ["observer-start", "source-stub", "observer-stop"]
    assert not (output / "result.json").exists()
    if secondary:
        assert any("secondary diagnostic I/O" in n for n in primary.__notes__)
    else:
        row = q.read_archive(output / "primitive-begin")
        assert (
            row["available"]["source_exception_owned_fields"]["partial"]["failed_trial"]
            == "retained"
        )


def test_array_view_failure_evidence_keeps_primary_cause_and_complete_base(monkeypatch, tmp_path):
    packet = mock_packet(monkeypatch, tmp_path)
    seen = []
    fake_work(monkeypatch, seen)
    original = np.arange(12.0)
    view = original.reshape(3, 4)[:, ::-1]
    cause = TypeError("original source cause")
    primary = ValueError("synthetic failed source with array view")
    primary.__cause__ = cause
    primary.partial = dict(view=view, repeated=view)

    def fail(*args):
        raise primary

    monkeypatch.setattr(q.primitive, "begin", fail)
    output = tmp_path / "output"
    with pytest.raises(ValueError) as caught:
        q.worker(output, packet=packet, packet_sha256="synthetic", enabled=True)
    assert caught.value is primary and primary.__cause__ is cause
    value, observations = q.read_archive(output / "primitive-begin", with_array_observations=True)
    observed = value["available"]["source_exception_owned_fields"]["partial"]
    assert observed["view"] is observed["repeated"]
    row = next(r for r in observations if r["logical_snapshot"] is observed["view"])
    assert row["strides"] == list(view.strides)
    assert observations[row["base"]]["logical_snapshot"].tobytes() == original.tobytes()
    assert seen == ["observer-start", "observer-stop"]
    assert (output / "failure/manifest.json").is_file() and not (output / "result.json").exists()


def test_successful_live_return_with_evidence_IO_error_does_not_advance_or_hide_return(
    monkeypatch, tmp_path
):
    packet = mock_packet(monkeypatch, tmp_path)
    seen = []
    fake_work(monkeypatch, seen)
    marker = object()
    io = OSError("capture failure after source return")
    monkeypatch.setattr(q.primitive, "begin", lambda *a: marker)
    monkeypatch.setattr(
        q.primitive_validation, "evidence", lambda value: dict(synthetic_only=value is marker)
    )
    old = q.archive

    def capture(path, value):
        if path.name == "primitive-begin":
            raise io
        return old(path, value)

    monkeypatch.setattr(q, "archive", capture)
    with pytest.raises(q.EvidenceRejected) as caught:
        q.worker(tmp_path / "output", packet=packet, packet_sha256="synthetic", enabled=True)
    assert caught.value.returned is marker and caught.value.__cause__ is io
    assert seen == ["observer-start", "observer-stop"]
    assert q.read_archive(tmp_path / "output/failure")["available"]["last_returned"] == dict(
        synthetic_only=True
    )


@pytest.mark.parametrize("unwind", [False, True])
@pytest.mark.parametrize("capture_fails", [False, True])
def test_profiled_None_or_exception_unwind_keeps_partial_and_never_masks_primary(
    monkeypatch, tmp_path, unwind, capture_fails
):
    primary = ValueError("synthetic original unwind")
    space = dict(__name__=q.reference.native.__name__, primary=primary)
    text = "def evaluate():\n inputs={'synthetic':True}\n history=[{'candidate':[1.0]}]\n " + (
        "raise primary\n" if unwind else "return None\n"
    )
    exec(compile(text, "<synthetic profile control>", "exec"), space)
    previous = sys.getprofile()
    with (tmp_path / "profile.jsonl").open("x") as stream:
        work = q.Work(stream)
        if capture_fails:
            monkeypatch.setattr(
                q, "partial", lambda f: (_ for _ in ()).throw(OSError("capture-only error"))
            )

        def observer(frame, event, arg):
            if previous is not None:
                previous(frame, event, arg)
            work.observe(frame, event, arg)

        sys.setprofile(observer)
        try:
            if unwind:
                with pytest.raises(ValueError) as caught:
                    space["evaluate"]()
                assert caught.value is primary
            else:
                assert space["evaluate"]() is None
        finally:
            sys.setprofile(previous)
    if capture_fails:
        assert work.capture_errors and not work.partials
    else:
        assert work.partials[-1]["return_or_unwind"]
        assert work.partials[-1]["available"]["history"] == [dict(candidate=[1.0])]


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "primitive-reset",
        "legacy-extra",
        "native-missing",
        "Decimal-duplicate",
        "capture",
        "profile",
        "active",
    ],
)
def test_exact_observed_work_is_not_silently_omitted_rebased_or_counted_as_cases(fault):
    value = dict(
        profile_intact=True,
        active_invocations=0,
        capture_errors=[],
        absolute_indices=dict(
            primitive=[0, 1, 2, 3],
            legacy=[0, 1, 2],
            native=[0, 1, 2, 3],
            Decimal100=[0, 1, 2, 3],
            Decimal160=[0, 1, 2, 3],
        ),
    )
    if fault == "primitive-reset":
        value["absolute_indices"]["primitive"][-1] = 0
    elif fault == "legacy-extra":
        value["absolute_indices"]["legacy"].append(3)
    elif fault == "native-missing":
        value["absolute_indices"]["native"].pop()
    elif fault == "Decimal-duplicate":
        value["absolute_indices"]["Decimal160"][-1] = 2
    elif fault == "capture":
        value["capture_errors"] = [dict(incomplete=True)]
    elif fault == "profile":
        value["profile_intact"] = False
    elif fault == "active":
        value["active_invocations"] = 1
    if fault is None:
        q.check_work(value)
    else:
        with pytest.raises(ValueError):
            q.check_work(value)
