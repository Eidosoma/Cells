"""Synthetic saved records only; no binding/setup/source/reference execution."""

import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from validation.betse import betse_normal_ecm_molecule_material_four_call_saved as s


@pytest.fixture(autouse=True)
def blocked(tmp_path):
    with s.source_blocked() as evidence:
        yield
    s.snapshot.write_json(tmp_path / "source-blocked.json", evidence)


def readonly(value=0.0, dtype="<f8"):
    return np.frombuffer(np.array([[value]], dtype=dtype).tobytes(), dtype=dtype).reshape(1, 1)


@pytest.mark.parametrize("dtype", ["<f8", ">f8", "<f4", "<i8"])
@pytest.mark.parametrize("shared", [False, True])
def test_descriptor_bridge_preserves_dtype_endian_bits_and_repeated_positions(
    tmp_path, dtype, shared
):
    a = readonly(-0.0, dtype)
    value = (a, a if shared else readonly(-0.0, dtype))
    expected = s.q.primitive.codec.fingerprint(value)
    s.q.archive(tmp_path / "observed", value)
    restored, observations = s.q.read_archive(tmp_path / "observed", with_array_observations=True)
    before = [(v.flags.writeable, v.strides, v.tobytes()) for v in restored]
    assert s.original_fingerprint(restored, observations) == expected
    assert [(v.flags.writeable, v.strides, v.tobytes()) for v in restored] == before
    assert (restored[0] is restored[1]) is shared
    assert s.q.primitive.codec.fingerprint(restored) != expected


def test_signed_zero_and_nan_payload_bits_are_not_normalized(tmp_path):
    raw = bytes.fromhex("0000000000000080010000000000f87f")
    a = np.frombuffer(raw, dtype="<f8")
    s.q.archive(tmp_path / "bits", (a, a))
    value, observations = s.q.read_archive(tmp_path / "bits", with_array_observations=True)
    assert value[0].tobytes() == raw
    assert s.original_fingerprint(value, observations) == s.q.primitive.codec.fingerprint((a, a))
    value[0].view(np.uint8)[7] = 0
    assert s.original_fingerprint(value, observations) != s.q.primitive.codec.fingerprint((a, a))


@pytest.mark.parametrize(
    "fault", ["missing", "ambiguous", "dtype", "shape", "stride", "flags", "flag-type"]
)
def test_fingerprint_observation_refusals(tmp_path, fault):
    s.q.archive(tmp_path / "array", readonly())
    value, observations = s.q.read_archive(tmp_path / "array", with_array_observations=True)
    rows = [dict(r) for r in observations]
    at = next(i for i, r in enumerate(rows) if r["logical_snapshot"] is value)
    if fault == "missing":
        rows.pop(at)
    elif fault == "ambiguous":
        rows.append(dict(rows[at]))
    elif fault == "dtype":
        rows[at]["dtype"] = ">f8"
    elif fault == "shape":
        rows[at]["shape"] = [1]
    elif fault == "stride":
        rows[at]["strides"] = [16, 8]
    elif fault == "flags":
        rows[at].update(C=False, F=False)
    else:
        rows[at]["writable"] = 0
    with pytest.raises(ValueError, match="observation|layout"):
        s.original_fingerprint(value, rows)


def synthetic_records():
    """Passive typed data with manufactured scalars; never a live Binding owner."""
    p, m = s.q.primitive, s.q.primitive.material
    a = readonly()
    ck = m.current.CurrentKernel(*(a for _ in m.current.CurrentKernel._fields))
    cb = m.current.CurrentBinding(("cell",), ("membrane",), ("Na",), 0.5, "synthetic", ck, "")
    cb = replace(cb, identity=m.current._digest(m.current.binding_record(cb)))
    g = m.geometry_source.Geometry(
        (1, 1), 1.0, *(a for _ in m.geometry_source.Geometry._fields[2:-1]), {}
    )
    gb = m.geometry_source.Binding("{}", cb, g, m.geometry_source.Cache(a, a), "")
    gb = replace(gb, identity=m.current._digest(m.geometry_source.binding_record(gb)))
    binding = m.Binding("{}", gb, m.Kernel(*(a for _ in m.Kernel._fields)), "")
    binding = replace(binding, identity=m.current._digest(m.binding_record(binding)))
    values = m.Values(*(a for _ in m.Values._fields))
    initial = {k: a.tolist() for k in m.Values._fields}
    program = dict(definition={}, initial=initial, steps=[])
    domain = (p.KIND, ("synthetic-budget",), (3, 1, 2**30, 8 * 2**30, True), "case", "synthetic")
    input_id = p.codec.fingerprint((program["definition"], initial))
    binding_record = (p.KIND, domain, binding, input_id)
    bid = p.codec.fingerprint(binding_record)
    parent = m.State(binding.identity, 0, values, "")
    parent = replace(parent, identity=m.current._digest(m.state_record(parent)))
    current = (p.KIND, bid, parent, parent.identity, None, None, 0, "ready")
    saved = {
        "primitive-begin": dict(
            kind=p.KIND,
            domain=domain,
            binding=binding_record,
            current=current,
            original_definition={},
            original_initial=initial,
            original_input_fingerprint=input_id,
            failed=False,
            failure=None,
            failed_trial=None,
            recovery_errors=[],
        ),
        "legacy-binding": binding,
        "legacy-initial": parent,
    }
    for i in range(4):
        drive = m.Drive(0.001, 298.15, *(a for _ in m.Drive._fields[2:]))
        program["steps"].append(
            {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in drive._asdict().items()}
        )
        candidate = m.State(binding.identity, i + 1, values, "")
        candidate = replace(candidate, identity=m.current._digest(m.state_record(candidate)))
        trial = m.Trial(binding.identity, parent.identity, drive, (), (), candidate, {}, "")
        trial = replace(trial, identity=m.current._digest(m.trial_record(trial)))
        state = (
            p.KIND,
            bid,
            candidate,
            saved["legacy-initial"].identity,
            p.codec.fingerprint(current),
            p.codec.fingerprint(drive),
            i + 1,
            "exhausted" if i == 3 else "ready",
        )
        saved[f"primitive-drive-{i}"] = drive
        saved[f"primitive-step-{i}"] = (state, trial)
        if i < 3:
            saved[f"legacy-drive-{i}"] = drive
            saved[f"legacy-step-{i}"] = trial
        current, parent = state, candidate
    saved["original-four"] = dict(
        failure=None,
        warnings=[],
        RNG_unchanged=True,
        history=[dict(source_completed=True) for _ in range(4)],
    )
    for precision, ref in ((100, 1), (160, 2)):
        saved[f"Decimal{precision}"] = dict(
            precision=precision,
            fixed_budget_reference=True,
            carried_error_allowance=False,
            history=[{} for _ in range(4)],
        )
        saved[f"Decimal-raw-{ref}"] = dict(
            refinement=ref, exact=dict(precision=precision, history=[{} for _ in range(4)])
        )
    return saved, program, domain


@pytest.fixture
def bundle(tmp_path):
    saved, program, domain = synthetic_records()
    loaded, observations = {}, {}
    for name in s.STAGES:
        payload = (
            saved[name]
            if name.startswith("Decimal-raw-")
            else dict(status="returned", returned=saved[name])
        )
        s.q.archive(tmp_path / name, payload)
        value, observations[name] = s.q.read_archive(tmp_path / name, with_array_observations=True)
        loaded[name] = value if name.startswith("Decimal-raw-") else value["returned"]
    s.q.archive(tmp_path / "program", program)
    return loaded, observations, s.q.read_archive(tmp_path / "program"), domain


def test_complete_saved_lineage_uses_only_decoded_passive_records(bundle):
    args, evidence = s.validate_histories(*bundle)
    assert len(args[0]) == 4 and len(args[1]) == 3
    assert [r["index"] for r in evidence["states"]] == list(range(4))
    assert args[-1] == ("Na",)


@pytest.mark.parametrize(
    "fault",
    [
        "epoch",
        "parent",
        "binding",
        "drive",
        "trial-id",
        "initial",
        "domain",
        "native-failed",
        "raw-missing",
        "precision",
    ],
)
def test_saved_lineage_forgery_refuses(bundle, fault):
    saved, obs, program, domain = bundle
    if fault in {"epoch", "parent", "binding", "drive"}:
        state, trial = saved["primitive-step-2"]
        row = list(state)
        row[{"epoch": 6, "parent": 4, "binding": 1, "drive": 5}[fault]] = (
            9 if fault == "epoch" else "forged"
        )
        saved["primitive-step-2"] = (tuple(row), trial)
    elif fault == "trial-id":
        state, trial = saved["primitive-step-2"]
        saved["primitive-step-2"] = (state, replace(trial, identity="forged"))
    elif fault == "initial":
        program["initial"]["voltage_V"][0][0] = 1.0
    elif fault == "domain":
        domain = ("foreign",)
    elif fault == "native-failed":
        saved["original-four"]["failure"] = "source failure"
    elif fault == "raw-missing":
        del saved["Decimal-raw-2"]
    else:
        saved["Decimal160"]["precision"] = 100
    with pytest.raises(ValueError):
        s.validate_histories(saved, obs, program, domain)


@pytest.mark.parametrize(
    "name", ["begin", "bind", "state", "drive", "step", "native", "decimal", "RNG"]
)
def test_entry_guards_stop_before_source_body(name):
    q = s.q
    operations = {
        "begin": lambda: q.primitive.begin(None, None, None),
        "bind": lambda: q.primitive.material.bind(None),
        "state": lambda: q.primitive.material.state(None, None),
        "drive": lambda: q.primitive.material.drive(None, None),
        "step": lambda: q.primitive.material.step(None, None, None),
        "native": lambda: q.reference.evaluate_original(None),
        "decimal": lambda: q.reference.evaluate_decimal(None, refinement=1),
        "RNG": lambda: np.random.default_rng(),
    }
    with pytest.raises(ValueError, match="forbids scientific entry"):
        with s.source_blocked() as guard:
            operations[name]()
    assert len(guard["attempts"]) == 1


@pytest.mark.parametrize("kind", ["modified-state", "missing-array", "foreign-path", "incomplete"])
def test_archive_metadata_refuses_before_decode(tmp_path, monkeypatch, kind):
    root = tmp_path / "archive"
    s.q.archive(root, dict(synthetic=True))
    monkeypatch.setattr(s.q, "read_archive", lambda *a, **k: pytest.fail("decode reached"))
    if kind == "modified-state":
        (root / "state.json").write_text("{}")
    elif kind == "missing-array":
        (root / "arrays.npz").unlink()
    else:
        manifest = json.loads((root / "manifest.json").read_text())
        if kind == "foreign-path":
            manifest["files"]["state.json"]["path"] = str(tmp_path / "foreign")
        else:
            manifest["owner_admission"] = True
        (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises((ValueError, FileNotFoundError)):
        s._archive_pin(root)


def test_missing_stage_refuses_before_any_archive_decode(tmp_path, monkeypatch):
    monkeypatch.setattr(s.q, "read_archive", lambda *a, **k: pytest.fail("decode reached"))
    with pytest.raises(KeyError):
        s.load_histories(dict(archives={}))


def metadata_origin(tmp_path, monkeypatch):
    """A tiny declared provenance graph, not an actual source result fixture."""
    origin = tmp_path / "origin"
    packet = origin / "packet-01"
    image = packet / "source"
    image.mkdir(parents=True)
    (image / "src/cells").mkdir(parents=True)
    source = image / "src/cells/synthetic.py"
    source.write_text("# inert metadata file\n")
    patch = image / "checkout.patch"
    patch.write_text("")
    source.chmod(0o444)
    patch.chmod(0o444)
    manifest = dict(
        kind="cells.checkout_source_snapshot@1",
        status="complete",
        immutable=True,
        patch_sha256=s.snapshot.digest(patch),
        files={
            "src/cells/synthetic.py": dict(
                checkout_path="src/cells/synthetic.py",
                sha256=s.snapshot.digest(source),
                observation=dict(size=source.stat().st_size),
                snapshot_mode=0o444,
            )
        },
    )
    s.snapshot.write_json(image / "SNAPSHOT.json", manifest)
    (image / "SNAPSHOT.json").chmod(0o444)
    for directory in (image / "src/cells", image / "src", image):
        directory.chmod(0o555)
    data = dict(synthetic_metadata=True)
    for name in s.STAGES:
        s.q.archive(origin / "qualification-01" / name, data)
    s.q.archive(packet / "program", data)

    def brief(path):
        return {k: s._pin(path)[k] for k in ("path", "sha256")}

    plan = dict(native_source=dict(checkout=str(origin), source_sha256={}))
    monkeypatch.setattr(s.q, "source_plan", lambda: plan)
    s.snapshot.write_json(packet / "source-plan.json", plan)
    inputs = dict(
        kind=s.q.KIND,
        held=True,
        automatic_launch=False,
        snapshot_sha256=s.snapshot.digest(image / "SNAPSHOT.json"),
        expected_producer=dict(
            source_hashes={"synthetic.py": s.snapshot.digest(source)}, runtime_code_sha256={}
        ),
        program=brief(packet / "program/manifest.json"),
        source_plan=brief(packet / "source-plan.json"),
    )
    s.snapshot.write_json(packet / "inputs.json", inputs)
    work = dict(
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
    s.snapshot.write_json(origin / "qualification-01/work.json", work)
    executable = brief(Path(sys.executable).resolve())
    runtime = dict(
        child=dict(executable=executable),
        loaded=dict(executable=executable, loaded_files={"cells.synthetic": brief(source)}),
    )
    s.snapshot.write_json(origin / "qualification-01/runtime.json", runtime)
    (origin / "qualification-01/invocations.jsonl").write_text('{"synthetic":true}\n')
    (origin / "process").mkdir()
    s.snapshot.write_json(origin / "process/failure.json", dict(synthetic=True))
    (origin / "process/stderr.log").write_text("synthetic comparison refusal\n")
    s.snapshot.write_json(origin / "release.json", dict(synthetic=True))
    s.snapshot.write_json(origin / "terminal.json", dict(status="failed"))
    records = []
    for name in ("packet-01/program", *("qualification-01/" + n for n in s.STAGES)):
        records.append(
            dict(
                name=name,
                manifest=brief(origin / name / "manifest.json"),
                state=brief(origin / name / "state.json"),
                npz=brief(origin / name / "arrays.npz"),
            )
        )
    review = dict(
        scientific_acceptance=False,
        terminal=brief(origin / "terminal.json"),
        complete_archives=dict(output_archive_count=22, program_archive_count=1, records=records),
        source=dict(
            packet=brief(packet / "inputs.json"),
            source_plan=brief(packet / "source-plan.json"),
            snapshot=brief(image / "SNAPSHOT.json"),
        ),
        work=dict(
            receipt=brief(origin / "qualification-01/work.json"),
            invocations=brief(origin / "qualification-01/invocations.jsonl"),
        ),
        runtime=dict(receipt=brief(origin / "qualification-01/runtime.json")),
        process_failure=brief(origin / "process/failure.json"),
        stderr=brief(origin / "process/stderr.log"),
        release=brief(origin / "release.json"),
    )
    s.snapshot.write_json(origin / "root-review.json", review)
    return origin, origin / "root-review.json", s.snapshot.digest(origin / "root-review.json")


def test_origin_preflight_binds_every_declared_archive_without_decoding(tmp_path, monkeypatch):
    origin, review, digest = metadata_origin(tmp_path, monkeypatch)
    monkeypatch.setattr(
        s.q, "read_archive", lambda *a, **k: pytest.fail("metadata decoded history")
    )
    result = s.origin_inputs(origin, origin_review=review, origin_review_sha256=digest)
    assert set(result["archives"]) == set(s.STAGES)
    assert result["original_status"] == "failed"


@pytest.mark.parametrize(
    "fault",
    ["review-pin", "missing-manifest", "work", "snapshot", "runtime", "program", "review-roster"],
)
def test_origin_pin_or_roster_forgery_refuses_before_decode(tmp_path, monkeypatch, fault):
    origin, review, digest = metadata_origin(tmp_path, monkeypatch)
    monkeypatch.setattr(s.q, "read_archive", lambda *a, **k: pytest.fail("decode reached"))
    if fault == "review-pin":
        digest = "0" * 64
    elif fault == "missing-manifest":
        (origin / "qualification-01/Decimal160/manifest.json").unlink()
    elif fault == "work":
        (origin / "qualification-01/work.json").write_text("{}")
    elif fault == "snapshot":
        p = origin / "packet-01/source/src/cells/synthetic.py"
        p.chmod(0o644)
        p.write_text("# drift\n")
    elif fault == "runtime":
        (origin / "qualification-01/runtime.json").write_text("{}")
    elif fault == "program":
        (origin / "packet-01/program/state.json").write_text("{}")
    else:
        row = json.loads(review.read_text())
        row["complete_archives"]["records"].pop()
        review.write_text(json.dumps(row))
        digest = s.snapshot.digest(review)
    with pytest.raises((ValueError, FileNotFoundError)):
        s.origin_inputs(origin, origin_review=review, origin_review_sha256=digest)


@pytest.mark.parametrize("released", [False, True])
def test_worker_release_precedes_inputs(monkeypatch, tmp_path, released):
    monkeypatch.delenv(s.RELEASE, raising=False)
    monkeypatch.setattr(s, "_read", lambda *a: pytest.fail("read before release"))
    with pytest.raises(ValueError, match="remains held"):
        s.worker(
            tmp_path / "prepared", tmp_path / "output", preparation_sha256="bad", enabled=released
        )


@pytest.mark.parametrize("linked", [False, True])
def test_output_containment_and_symlinks_refuse(tmp_path, linked):
    origin = tmp_path / "origin"
    origin.mkdir()
    target = origin / "output"
    if linked:
        link = tmp_path / "link"
        link.symlink_to(origin, target_is_directory=True)
        target = link / "output"
    with pytest.raises(ValueError, match="overlaps|Linked"):
        s._disjoint(target, (origin,))


def worker_inputs(monkeypatch, tmp_path):
    prepared, origin, repository = (tmp_path / n for n in ("prepared", "origin", "repository"))
    for root in (prepared, origin, repository):
        root.mkdir()
    affinity = s.os.sched_getaffinity(0)
    assert len(affinity) == 1
    inputs = dict(
        origin=dict(root=str(origin)),
        repository=str(repository),
        resources=dict(cpu=next(iter(affinity))),
    )
    s.snapshot.write_json(prepared / "inputs.json", inputs)
    monkeypatch.setenv(s.RELEASE, "1")
    monkeypatch.setattr(s, "verify_preparation", lambda *a: inputs)
    monkeypatch.setattr(s, "load_histories", lambda *a: ((), dict(synthetic=True)))
    monkeypatch.setattr(s.q, "identity", lambda: dict(synthetic=True))
    monkeypatch.setattr(s.q, "inventory", lambda: dict(synthetic=True))
    return prepared, inputs


@pytest.mark.parametrize("secondary", [False, True])
def test_comparison_primary_and_cause_survive_writer_failure(tmp_path, monkeypatch, secondary):
    prepared, inputs = worker_inputs(monkeypatch, tmp_path)
    inputs["origin"]["archives"] = {}
    primary = AssertionError("synthetic saved field mismatch")
    cause = ValueError("original comparison cause")
    primary.__cause__ = cause

    def compare(*args):
        raise primary

    monkeypatch.setattr(s.q, "compare_history_data", compare)
    original = s.snapshot.write_json

    def writer(path, value):
        if secondary and Path(path).name == "failure.json":
            raise OSError("synthetic failure writer")
        return original(path, value)

    monkeypatch.setattr(s.snapshot, "write_json", writer)
    output = tmp_path / "assessment"
    with pytest.raises(AssertionError) as caught:
        s.worker(prepared, output, preparation_sha256="synthetic", enabled=True)
    assert caught.value is primary and primary.__cause__ is cause
    assert not (output / "result.json").exists()
    if secondary:
        assert any("persistence failed" in note for note in primary.__notes__)
    else:
        failure = json.loads((output / "failure.json").read_text())
        assert failure["stage"] == "saved-comparison"
        assert failure["error"]["exception_chain"][1]["message"] == "original comparison cause"
    assert (output / "evidence-references.json").is_file()


def test_verification_failure_never_decodes(tmp_path, monkeypatch):
    prepared, _ = worker_inputs(monkeypatch, tmp_path)
    monkeypatch.setattr(s, "load_histories", lambda *a: pytest.fail("decode reached"))

    def verify(*args):
        raise ValueError("synthetic pin drift")

    monkeypatch.setattr(s, "verify_preparation", verify)
    output = tmp_path / "assessment"
    with pytest.raises(ValueError, match="pin drift"):
        s.worker(prepared, output, preparation_sha256="synthetic", enabled=True)
    assert json.loads((output / "failure.json").read_text())["stage"] == "verification"


def test_success_is_separate_saved_postprocessing_not_source_pass(tmp_path, monkeypatch):
    prepared, inputs = worker_inputs(monkeypatch, tmp_path)
    inputs["origin"]["archives"] = {}
    monkeypatch.setattr(s.q, "compare_history_data", lambda: [dict(synthetic_only=True)])
    output = tmp_path / "assessment"
    s.worker(prepared, output, preparation_sha256="synthetic", enabled=True)
    result = json.loads((output / "result.json").read_text())
    assert result["status"] == "saved_data_comparison_passed"
    assert result["original_source_status"] == "failed" and result["scientific_source_calls"] == 0
    assert result["independent_biological_cases"] == 0
    assert not result["physical_or_coupled_or_checkpoint_admission"]


def test_terminal_runtime_failure_cannot_publish_success(tmp_path, monkeypatch):
    prepared, inputs = worker_inputs(monkeypatch, tmp_path)
    inputs["origin"]["archives"] = {}
    monkeypatch.setattr(s.q, "compare_history_data", lambda: [dict(synthetic_only=True)])

    def inventory():
        raise RuntimeError("synthetic runtime persistence")

    monkeypatch.setattr(s.q, "inventory", inventory)
    output = tmp_path / "assessment"
    with pytest.raises(RuntimeError, match="runtime persistence"):
        s.worker(prepared, output, preparation_sha256="synthetic", enabled=True)
    assert not (output / "result.json").exists()
    assert json.loads((output / "failure.json").read_text())["stage"] == "terminal-evidence"
