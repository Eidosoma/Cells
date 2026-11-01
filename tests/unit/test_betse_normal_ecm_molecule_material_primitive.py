"""Arithmetic-blocked dispatch/state/retention controls, no fourth numerical result."""

import importlib.abc
import json
import os
import sys
from dataclasses import fields, is_dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_molecule_material_primitive as primitive
from validation.betse import betse_normal_ecm_molecule_material_primitive as validation

material = primitive.material


def plain(cls, **values):
    names = [f.name for f in fields(cls)] if is_dataclass(cls) else cls._fields
    return cls(**{name: values.get(name) for name in names})


def frozen(shape, value=0.0):
    a = np.full(shape, value, dtype=np.float64)
    return np.frombuffer(a.tobytes(), dtype=a.dtype).reshape(a.shape)


def budget(**updates):
    values = dict(
        source_calls=4,
        max_material_attempts=6,
        max_owner_verifications=100,
        max_nested_source_invocations=1_000_000,
        max_retained_bytes=2**20,
        wall_seconds=480.0,
        provenance="unowned synthetic control, not qualification",
    )
    values.update(updates)
    return primitive.contract.budget(**values)


def declared(*, cpu=0, **updates):
    return primitive.declare(
        budget(**updates),
        run_id="synthetic-standalone-4",
        provenance="Declared control inputs; no native derivation",
        policy=replace(primitive.DEFAULT_POLICY, cpu=cpu),
    )


@pytest.mark.parametrize("cpu", [0, 3])
def test_cpu_policy_accepts_explicit_index_without_changing_other_guards(cpu):
    policy = replace(primitive.DEFAULT_POLICY, cpu=cpu)
    value = primitive.declare(
        budget(), run_id="selected-cpu", provenance="software-only", policy=policy
    )
    primitive.verify_domain(value)
    assert value.policy is policy and primitive.domain_record(value)[2] == (
        cpu,
        1,
        2**30,
        8 * 2**30,
        True,
    )
    assert primitive.DEFAULT_POLICY.cpu == 0
    other = primitive.declare(
        budget(),
        run_id="selected-cpu",
        provenance="software-only",
        policy=replace(policy, cpu=cpu + 1),
    )
    assert other.identity != value.identity


@pytest.mark.parametrize("cpu", [-1, True, False, 3.0, "3"])
def test_cpu_policy_invalid_selector_refuses_without_resource_or_source_probe(monkeypatch, cpu):
    monkeypatch.setattr(
        primitive, "resources", lambda *a: pytest.fail("Declaration performed a resource probe")
    )
    with pytest.raises(ValueError):
        primitive.declare(
            budget(),
            run_id="cpu-refusal",
            provenance="software-only",
            policy=replace(primitive.DEFAULT_POLICY, cpu=cpu),
        )


@pytest.mark.parametrize("affinity", [{3}, {0}, {3, 4}])
def test_cpu_policy_keeps_exact_singleton_affinity_enforcement(monkeypatch, affinity):
    monkeypatch.setattr(primitive.os, "sched_getaffinity", lambda pid: affinity)
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        monkeypatch.setenv(name, "1")
    reads = []
    original_read = primitive.Path.read_text

    def read(path, *args, **kwargs):
        if str(path) not in ("/proc/self/status", "/proc/meminfo"):
            return original_read(path, *args, **kwargs)
        reads.append(str(path))
        if str(path) == "/proc/self/status":
            return "VmRSS: 4096 kB\n"
        assert str(path) == "/proc/meminfo"
        return "MemAvailable: 16777216 kB\n"

    monkeypatch.setattr(primitive.Path, "read_text", read)
    policy = replace(primitive.DEFAULT_POLICY, cpu=3)
    if affinity == {3}:
        assert primitive.resources(policy) == dict(rss_bytes=4 * 2**20, available_bytes=16 * 2**30)
        assert reads == ["/proc/self/status", "/proc/meminfo"]
    else:
        with pytest.raises(ValueError, match="Changed actual CPU affinity"):
            primitive.resources(policy)
        assert reads == []


@pytest.fixture(autouse=True)
def no_arithmetic(monkeypatch, tmp_path):
    previous, attempted = sys.getprofile(), []
    functions = (
        material.bind,
        material.validate_binding,
        material.drive,
        material._state_values,
        material._step_source.__wrapped__,
        material._electroflux,
        material._smooth,
        material.geometry_source.bind,
        material.geometry_source.gradient,
        material.geometry_source.source_diff,
    )
    codes = {id(f.__code__) for f in functions}

    def guard(frame, event, arg):
        if event == "call" and id(frame.f_code) in codes:
            attempted.append(frame.f_code.co_name)
            raise AssertionError("Actual material/source arithmetic forbidden in software control")
        if event == "c_call":
            module = getattr(arg, "__module__", "") or ""
            owner = getattr(arg, "__self__", None)
            if (
                module.startswith("numpy.random")
                or module == "random"
                or (owner is not None and type(owner).__module__.startswith("numpy.random"))
            ):
                attempted.append("RNG")
                raise AssertionError("Actual RNG forbidden")
        if previous is not None:
            previous(frame, event, arg)

    class NoNative(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "betse" or fullname.startswith("betse."):
                attempted.append(fullname)
                raise AssertionError("Actual native import forbidden")

    native = NoNative()
    sys.meta_path.insert(0, native)
    sys.setprofile(guard)
    monkeypatch.delenv(primitive.RELEASE, raising=False)
    yield attempted
    intact = sys.getprofile() is guard
    sys.setprofile(previous)
    sys.meta_path.remove(native)
    (tmp_path / "arithmetic-blocked.json").write_text(
        json.dumps(
            dict(
                attempted=attempted,
                profiler_intact=intact,
                actual_source_entries=0,
                synthetic_only=True,
                biological_cases=0,
            )
        )
    )
    assert attempted == [] and intact


@pytest.fixture
def fake_engine(monkeypatch):
    """Typed data and stand-in API producers; no real owner is admitted."""
    cb = plain(
        material.current.CurrentBinding,
        cell_ids=("c0", "c1"),
        membrane_ids=("m0", "m1"),
        ion_ids=("Na",),
        sharpness_cell=1.0,
        provenance="synthetic",
        identity="synthetic-current",
    )
    gb = plain(
        material.geometry_source.Binding,
        definition_json='{"synthetic":true}',
        current_binding=cb,
        geometry=plain(material.geometry_source.Geometry, shape=(2, 2)),
        identity="synthetic-geometry",
    )
    source = material.Binding(
        '{"synthetic":true}', gb, material.Kernel(*(None for _ in material.Kernel._fields)), ""
    )
    source = replace(source, identity=material.current._digest(material.binding_record(source)))
    shapes = (
        (1, 2),
        (1, 2),
        (1, 4),
        (2,),
        (1, 2),
        (1, 2),
        (1, 4),
        (1, 4),
        (2,),
        (2,),
        (2, 2),
        (2,),
    )
    initial = dict(zip(material.Values._fields, (frozen(s) for s in shapes), strict=True))
    events = []

    def binding(raw):
        assert raw is definition
        events.append(("bind", None))
        return source

    def state(owner, raw, *, step_index):
        assert owner is source
        events.append(("state", step_index))
        value = material.State(owner.identity, step_index, material.Values(**raw), "")
        return replace(value, identity=material.current._digest(material.state_record(value)))

    def verify(owner):
        assert owner is source
        events.append(("verify", None))
        return owner

    def drive(owner, raw):
        assert owner is source
        events.append(("drive", None))
        return material.Drive(**raw)

    def arithmetic(owner, parent, forcing):
        assert owner is source
        events.append(("shared-body", parent.step_index))
        value = state(
            owner,
            dict(
                zip(
                    material.Values._fields,
                    (frozen(s, parent.step_index + 1.0) for s in shapes),
                    strict=True,
                )
            ),
            step_index=parent.step_index + 1,
        )
        row = material.Trial(
            owner.identity,
            parent.identity,
            forcing,
            (
                material.Frame("synthetic-before", None, parent.values),
                material.Frame("synthetic-after", None, value.values),
            ),
            (),
            value,
            material.freeze(dict(finite=True, synthetic_only=True)),
            "",
        )
        return replace(row, identity=material.current._digest(material.trial_record(row)))

    definition = dict(synthetic_only=True)
    forcing = material.Drive(
        0.25,
        310.0,
        frozen((2,), 1),
        frozen((2,), 1),
        frozen((1, 2)),
        frozen((1, 2)),
        *(frozen((2, 2)) for _ in range(4)),
        frozen((1,), 1),
    )
    monkeypatch.setattr(material, "bind", binding)
    monkeypatch.setattr(material, "_state_values", state)
    monkeypatch.setattr(material, "validate_binding", verify)
    monkeypatch.setattr(material, "drive", drive)
    monkeypatch.setattr(material, "_step_source", arithmetic)
    monkeypatch.setenv(primitive.RELEASE, "1")
    return SimpleNamespace(
        source=source,
        definition=definition,
        initial=initial,
        forcing=forcing,
        events=events,
        arithmetic=arithmetic,
    )


def begin(engine, **limits):
    affinity = os.sched_getaffinity(0)
    assert len(affinity) == 1, "Synthetic source controls require the external single-CPU guard"
    return primitive.begin(
        declared(cpu=next(iter(affinity)), **limits), engine.definition, engine.initial
    )


def original():
    return Path(
        os.environ.get(
            "CELLS_MATERIAL_PRIMITIVE_ORIGINAL",
            "/mnt/workspaces/Cells/molecule-extended-material-primitive-development-20261101-01/source-before/betse_ecm_transport.py",
        )
    )


def test_complete_AST_extraction_correspondence_including_legacy_guards_and_handlers(tmp_path):
    report = validation.correspondence(
        original().read_bytes(), Path(material.__file__).read_bytes()
    )
    assert report["shared_arithmetic_implementations"] == 1
    assert report["unchanged_other_module_AST"] and not report["extended_arithmetic_has_legacy_cap"]
    (tmp_path / "AST-correspondence.json").write_text(json.dumps(report))


@pytest.mark.parametrize(
    "fault", ["cap", "order", "nonce", "handler", "state-guard", "dispatch", "signature"]
)
def test_whole_AST_guard_refuses_literal_order_guard_handler_or_dispatch_drift(fault):
    current = Path(material.__file__).read_text()
    edits = dict(
        cap=("MAX_STEPS = 3", "MAX_STEPS = 4"),
        order=("fm.fill(0)\n", "fg.fill(0)\n"),
        nonce=("NONCE = 1e-25", "NONCE = 1e-24"),
        handler=('stage="material_trial" if trial is not None else "source"', 'stage="source"'),
        **{
            "state-guard": ("not 0 <= step_index <= MAX_STEPS", "not 0 <= step_index < MAX_STEPS"),
            "dispatch": (
                "return _step_source(binding, parent, forcing)",
                "return step(binding, parent, forcing)",
            ),
            "signature": (
                "def _step_source(binding, parent, forcing):",
                "def _step_source(binding, parent, forcing=None):",
            ),
        },
    )
    before, after = edits[fault]
    assert before in current
    with pytest.raises(ValueError):
        validation.correspondence(
            original().read_bytes(), current.replace(before, after, 1).encode()
        )


def test_metadata_budget_does_not_create_or_import_a_numerical_owner(tmp_path):
    control = declared()
    primitive.verify_domain(control)
    assert material.MAX_STEPS == 3 and not hasattr(control, "current")
    for value in (None, {}, plain(primitive.contract.Retained)):
        with pytest.raises(ValueError, match="Separate typed numerical domain"):
            primitive.verify_domain(value)


def test_release_precedes_source_constructors_and_policy_probes(monkeypatch):
    monkeypatch.setattr(
        primitive, "resources", lambda *_: pytest.fail("Held route may not probe execution")
    )
    with pytest.raises(ValueError, match="remains held"):
        primitive.begin(declared(), {}, {})


@pytest.mark.parametrize("fault", ["cpu", "threads", "rss", "reserve", "outer", "run-id", "wall"])
def test_domain_and_actual_policy_are_explicit_finite_and_versioned(fault):
    policy, run_id, limits = primitive.Policy(), "synthetic", budget()
    if fault in {"cpu", "threads", "rss", "reserve", "outer"}:
        field, value = {
            "cpu": ("cpu", True),
            "threads": ("threads", 2),
            "rss": ("max_rss_bytes", 2**31),
            "reserve": ("min_available_bytes", 0),
            "outer": ("outer_guard_required", False),
        }[fault]
        policy = replace(policy, **{field: value})
    elif fault == "run-id":
        run_id = ""
    else:
        limits = budget(wall_seconds=481.0)
    with pytest.raises(ValueError):
        primitive.declare(limits, run_id=run_id, provenance="synthetic", policy=policy)


def test_standalone_fourth_dispatch_reaches_same_private_source_and_retains_absolute_epochs(
    fake_engine, tmp_path
):
    engine = fake_engine
    execution = begin(engine)
    initial = execution.current
    source_states, trials = [initial.source], []
    for index in range(4):
        parent = execution.current
        state, trial = execution.advance(parent, engine.forcing)
        assert state.absolute_index == index + 1 and state.previous_identity == parent.identity
        assert (
            state.initial_identity == initial.source.identity and state.attempt_ordinal == index + 1
        )
        assert trial.drive is engine.forcing and trial.candidate is state.source
        source_states.append(state.source)
        trials.append(trial)
    assert [index for label, index in engine.events if label == "shared-body"] == [0, 1, 2, 3]
    assert execution.current.status == "exhausted" and execution.current.absolute_index == 4
    assert initial.absolute_index == 0 and initial.source is source_states[0]
    assert all(entry["forcing"] is engine.forcing for entry in execution.attempts)
    assert all(
        entry["trial"] is trial for entry, trial in zip(execution.attempts, trials, strict=True)
    )
    assert execution.requests == execution.material_attempts == execution.source_requests == 4
    assert execution.owner_verifications == 14 and execution.source_entries == 0
    assert execution.nested_source_calls > 0
    path = validation.retain(tmp_path / "complete-standalone-control", execution)
    tree = primitive.codec.parse_json(
        (path / "state.json").read_bytes(), primitive.codec.DEFAULT_LIMITS
    )
    decoded = primitive.codec.decode(tree, (path / "arrays.npz").read_bytes())
    assert decoded["current"][2].step_index == 4
    assert decoded["attempts"][-1]["trial"].candidate is decoded["current"][2]
    assert decoded["attempts"][0]["trial"].candidate is decoded["attempts"][1]["parent"][2]
    assert not decoded["extended_checkpoint_or_coupled_admission"]


@pytest.mark.parametrize(
    "fault",
    [
        "old-parent",
        "copied-parent",
        "malformed-parent",
        "rebase",
        "changed-state",
        "changed-input",
        "changed-domain",
        "wrong-drive",
    ],
)
def test_missing_changed_or_rebased_absolute_authority_refuses_before_next_arithmetic(
    fake_engine, fault
):
    e = begin(fake_engine)
    old = e.current
    e.advance(old, fake_engine.forcing)
    parent, forcing = e.current, fake_engine.forcing
    if fault == "old-parent":
        parent = old
    elif fault == "copied-parent":
        parent = replace(parent)
    elif fault == "malformed-parent":
        parent = replace(parent, source=None)
    elif fault == "rebase":
        e.current = parent = old
    elif fault == "changed-state":
        wrong = replace(parent, source=replace(parent.source, step_index=3))
        e.current = parent = replace(
            wrong, identity=primitive.codec.fingerprint(primitive.state_record(wrong))
        )
    elif fault == "changed-input":
        fake_engine.definition["foreign"] = True
    elif fault == "changed-domain":
        e.domain = replace(e.domain, identity="foreign")
    else:
        forcing = {}
    with pytest.raises(primitive.PrimitiveRejected) as caught:
        e.advance(parent, forcing)
    assert len([row for row in fake_engine.events if row[0] == "shared-body"]) == 1
    assert e.requests == 2 and e.source_requests == 1 and caught.value.execution is e
    assert e.failed


@pytest.mark.parametrize(
    "fault",
    ["omitted", "duplicate", "foreign-parent", "foreign-drive", "mutable", "failed-diagnostic"],
)
def test_unaccepted_source_output_epoch_or_payload_never_commits(
    fake_engine, monkeypatch, tmp_path, fault
):
    e = begin(fake_engine)
    parent = e.current

    def wrong(owner, source, forcing):
        trial = fake_engine.arithmetic(owner, source, forcing)
        if fault in {"omitted", "duplicate"}:
            candidate = replace(
                trial.candidate, step_index=source.step_index + (2 if fault == "omitted" else 0)
            )
            candidate = replace(
                candidate, identity=material.current._digest(material.state_record(candidate))
            )
            trial = replace(trial, candidate=candidate)
        elif fault == "foreign-parent":
            trial = replace(trial, parent_identity="foreign")
        elif fault == "foreign-drive":
            trial = replace(trial, drive=material.Drive(*forcing))
        elif fault == "mutable":
            values = trial.candidate.values._replace(
                voltage_V=trial.candidate.values.voltage_V.copy()
            )
            candidate = replace(trial.candidate, values=values)
            trial = replace(
                trial,
                candidate=replace(
                    candidate, identity=material.current._digest(material.state_record(candidate))
                ),
            )
        else:
            trial = replace(trial, diagnostics=material.freeze(dict(finite=False)))
        return replace(trial, identity=material.current._digest(material.trial_record(trial)))

    monkeypatch.setattr(material, "_step_source", wrong)
    with pytest.raises(primitive.PrimitiveRejected) as caught:
        e.advance(parent, fake_engine.forcing)
    assert e.current is parent and caught.value.trial is not None and e.failed
    validation.retain(tmp_path / "unaccepted-trial", e, caught.value)


def test_shared_source_failure_keeps_primary_cause_failed_trial_original_parent_and_profiler(
    fake_engine, monkeypatch, tmp_path
):
    e = begin(fake_engine)
    parent = e.current
    previous = sys.getprofile()
    trial = fake_engine.arithmetic(fake_engine.source, parent.source, fake_engine.forcing)
    cause = TypeError("retained source cause")
    primary = material.ECMTransportRejected(
        "synthetic failed trial",
        stage="material_trial",
        parent=parent.source,
        drive=fake_engine.forcing,
        trial=trial,
    )
    primary.__cause__ = cause

    def reject(*args):
        raise primary

    monkeypatch.setattr(material, "_step_source", reject)
    with pytest.raises(primitive.PrimitiveRejected) as caught:
        e.advance(parent, fake_engine.forcing)
    assert caught.value.__cause__ is primary and primary.__cause__ is cause
    assert caught.value.accepted is parent and caught.value.trial is trial
    assert e.current is parent and e.failed and sys.getprofile() is previous
    assert e.material_attempts == e.source_requests == 1
    with pytest.raises(primitive.PrimitiveRejected, match="Failed lineage"):
        e.advance(parent, fake_engine.forcing)
    assert e.requests == 2 and e.source_requests == 1
    validation.retain(tmp_path / "failed-prefix-and-trial", e, caught.value)


@pytest.mark.parametrize("fault", ["attempts", "verify", "nested", "wall", "bytes"])
def test_actual_work_and_retained_evidence_limits_refuse_without_restarting_owner(
    fake_engine, monkeypatch, fault
):
    if fault == "nested":
        previous = sys.getprofile()
        with pytest.raises(primitive.PrimitiveRejected) as caught:
            begin(fake_engine, max_nested_source_invocations=5)
        assert caught.value.execution.nested_source_calls > 5 and sys.getprofile() is previous
        return
    if fault == "bytes":
        with pytest.raises(primitive.PrimitiveRejected) as caught:
            begin(fake_engine, max_retained_bytes=1)
        assert caught.value.execution.failed
        return
    e = begin(
        fake_engine,
        max_owner_verifications=2 if fault == "verify" else 100,
        max_material_attempts=4,
    )
    parent = e.current
    if fault == "attempts":
        for _ in range(4):
            e.advance(e.current, fake_engine.forcing)
        parent = e.current
    elif fault == "wall":
        monkeypatch.setattr(primitive.time, "monotonic", lambda: e.started + 481.0)
    with pytest.raises(primitive.PrimitiveRejected):
        e.advance(parent, fake_engine.forcing)
    assert e.current is parent and e.failed
    assert e.source_requests == (4 if fault == "attempts" else 0)


def test_legacy_state_and_step_keep_original_three_call_cap_and_rejection_chain(fake_engine):
    state = material.state(fake_engine.source, fake_engine.initial, step_index=3)
    with pytest.raises(ValueError, match=r"bounded step index \[0,3\]"):
        material.state(fake_engine.source, fake_engine.initial, step_index=4)
    with pytest.raises(material.ECMTransportRejected, match="qualified three-call cap") as caught:
        material.step(fake_engine.source, state, fake_engine.forcing)
    assert type(caught.value.__cause__) is ValueError
    assert caught.value.stage == "source" and caught.value.parent is state
    assert caught.value.drive is fake_engine.forcing and caught.value.trial is None
    assert not any(label == "shared-body" for label, _ in fake_engine.events)


def test_legacy_entry_still_dispatches_valid_parent_to_exact_shared_body(fake_engine):
    parent = material.state(fake_engine.source, fake_engine.initial)
    result = material.step(fake_engine.source, parent, fake_engine.forcing)
    assert result.parent_identity == parent.identity and result.candidate.step_index == 1
    assert fake_engine.events[-2][0] == "shared-body"


@pytest.mark.parametrize("fault", ["CPU", "threads", "wall-policy"])
def test_actual_resource_policy_drift_refuses_before_source_dispatch(
    fake_engine, monkeypatch, fault
):
    e = begin(fake_engine)
    parent = e.current
    if fault == "CPU":
        monkeypatch.setattr(primitive.os, "sched_getaffinity", lambda _: {e.domain.policy.cpu + 1})
    elif fault == "threads":
        monkeypatch.setenv("OMP_NUM_THREADS", "2")
    else:
        monkeypatch.setattr(primitive.time, "monotonic", lambda: e.started + 481.0)
    with pytest.raises(primitive.PrimitiveRejected) as caught:
        e.advance(parent, fake_engine.forcing)
    assert caught.value.stage == "admission" and e.current is parent
    assert e.source_requests == e.source_entries == 0
    assert not any(label == "shared-body" for label, _ in fake_engine.events)


@pytest.mark.parametrize("fault", ["cursor", "owner", "missing"])
def test_fresh_source_boundary_refuses_saved_owner_metadata_before_construction(fake_engine, fault):
    initial = dict(fake_engine.initial)
    if fault == "cursor":
        initial["step_index"] = 3
    elif fault == "owner":
        initial["previous_owner"] = "saved-prefix"
    else:
        initial.pop("voltage_V")
    with pytest.raises(ValueError, match="saved owner/cursor/cache"):
        primitive.begin(declared(), fake_engine.definition, initial)
    assert fake_engine.events == []


def test_absolute_domain_exhaustion_refuses_even_with_spare_attempt_budget(fake_engine):
    e = begin(fake_engine)
    for _ in range(4):
        e.advance(e.current, fake_engine.forcing)
    parent = e.current
    with pytest.raises(primitive.PrimitiveRejected, match="absolute material domain exhausted"):
        e.advance(parent, fake_engine.forcing)
    assert e.current is parent and e.current.absolute_index == 4
    assert e.requests == e.material_attempts == 5 and e.source_requests == 4


def test_resealed_larger_domain_cannot_replace_original_limits(fake_engine):
    e = begin(fake_engine)
    original = e.domain
    e.domain = primitive.declare(
        budget(source_calls=8, max_material_attempts=8),
        run_id=original.run_id,
        provenance=original.provenance,
    )
    primitive.verify_domain(e.domain)  # Valid independently; foreign to this execution.
    with pytest.raises(primitive.PrimitiveRejected, match="limits cannot be rebound"):
        e.advance(e.current, fake_engine.forcing)
    assert e.current.absolute_index == 0 and e.source_requests == e.source_entries == 0
    assert e.binding.domain is original and e.failed


@pytest.mark.parametrize("swallow", [False, True])
@pytest.mark.parametrize("via_profiler", [False, True])
def test_reentrant_source_or_inherited_profiler_never_dispatches_same_epoch_twice(
    fake_engine, monkeypatch, tmp_path, swallow, via_profiler
):
    execution = begin(fake_engine)
    baseline, _ = execution.advance(execution.current, fake_engine.forcing)
    assert baseline.absolute_index == 1 and execution.requests == execution.source_requests == 1
    previous, nested, invoked = sys.getprofile(), [], []

    def reenter():
        invoked.append("reenter")
        try:
            execution.advance(baseline, fake_engine.forcing)
        except primitive.PrimitiveRejected as error:
            nested.append(error)
            if not swallow:
                raise

    def source(owner, parent, forcing):
        reenter()
        return fake_engine.arithmetic(owner, parent, forcing)

    def inherited(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event == "call" and frame.f_code is fake_engine.arithmetic.__code__ and not invoked:
            reenter()

    if via_profiler:
        sys.setprofile(inherited)
    else:
        monkeypatch.setattr(material, "_step_source", source)
    expected_profiler = sys.getprofile()
    try:
        with pytest.raises(primitive.PrimitiveRejected) as caught:
            execution.advance(baseline, fake_engine.forcing)
        assert sys.getprofile() is expected_profiler
    finally:
        sys.setprofile(previous)
    assert invoked == ["reenter"] and len(nested) == 1
    refusal = nested[0]
    assert refusal.stage == "reentrant-admission" and refusal.accepted is baseline
    assert refusal.outer_context["accepted"] is baseline and refusal.outer_context["ordinal"] == 2
    assert refusal.attempt["ordinal"] == 3 and refusal.attempt["source_requested"] is False
    assert execution.current is baseline and execution._accepted_calls == 1
    assert execution.requests == 3 and execution.material_attempts == execution.source_requests == 2
    assert execution.source_entries == 0 and execution.failed and not execution._advance_active
    assert execution._active_context is None
    assert [e["ordinal"] for e in execution.attempts] == [1, 2, 3]
    assert [e["status"] for e in execution.attempts] == ["accepted", "failed", "refused_reentrant"]
    # If the callback swallows its refusal, the outer producer may return a
    # trial, but its failed lineage must still refuse the commit.
    if swallow:
        assert caught.value.stage == "commit-admission" and caught.value.trial is not None
        assert [i for label, i in fake_engine.events if label == "shared-body"] == [0, 1]
    else:
        assert caught.value.primary is refusal and caught.value.__cause__ is refusal
        assert [i for label, i in fake_engine.events if label == "shared-body"] == [0]
    assert caught.value.accepted is baseline
    validation.retain(tmp_path / "reentrant-refusal", execution, caught.value)


@pytest.mark.parametrize("mutation", ["current", "epoch", "parent-index"])
def test_commit_rechecks_original_live_parent_and_absolute_epoch_without_another_source_call(
    fake_engine, monkeypatch, tmp_path, mutation
):
    execution = begin(fake_engine)
    parent = execution.current

    original_retain = execution._retain

    def retain(*extra, current=None):
        original_retain(*extra, current=current)
        if current is None:
            return
        if mutation == "current":
            execution.current = replace(parent)
        elif mutation == "epoch":
            execution._accepted_calls += 1
        else:
            object.__setattr__(parent.source, "step_index", 1)

    monkeypatch.setattr(execution, "_retain", retain)
    with pytest.raises(primitive.PrimitiveRejected) as caught:
        execution.advance(parent, fake_engine.forcing)
    assert caught.value.trial is not None and caught.value.accepted is parent
    assert caught.value.stage == "commit-admission"
    assert execution.failed and not execution._advance_active
    assert execution.source_requests == execution.material_attempts == execution.requests == 1
    assert execution._accepted_calls == (1 if mutation == "epoch" else 0)
    assert execution.current is not caught.value.trial.candidate
    assert execution.attempts[0]["status"] == "failed"
    validation.retain(tmp_path / "commit-refusal", execution, caught.value)


@pytest.mark.parametrize(
    "mutation",
    [
        "private-default",
        "private-order",
        "private-extra",
        "private-decorator",
        "public-decorator",
        "public-return",
    ],
)
def test_constructor_header_and_decorator_drift_refuses_complete_correspondence(mutation):
    source = Path(material.__file__).read_text()
    before, after = {
        "private-default": (
            "def _state_values(binding, raw, *, step_index):",
            "def _state_values(binding, raw, *, step_index=0):",
        ),
        "private-order": (
            "def _state_values(binding, raw, *, step_index):",
            "def _state_values(raw, binding, *, step_index):",
        ),
        "private-extra": (
            "def _state_values(binding, raw, *, step_index):",
            "def _state_values(binding, raw, *, step_index, callback=None):",
        ),
        "private-decorator": (
            "def _state_values(",
            "@np.errstate(all='raise')\ndef _state_values(",
        ),
        "public-decorator": ("def state(", "@np.errstate(all='raise')\ndef state("),
        "public-return": (
            "def state(binding, raw, *, step_index=0):",
            "def state(binding, raw, *, step_index=0) -> object:",
        ),
    }[mutation]
    assert before in source
    with pytest.raises(ValueError, match="constructor header/decorators"):
        validation.correspondence(
            original().read_bytes(), source.replace(before, after, 1).encode()
        )


@pytest.mark.parametrize("raw", [None, {}, "receipt"])
def test_metadata_or_incomplete_owner_import_has_no_numerical_admission(fake_engine, raw):
    if raw == {}:
        raw = plain(primitive.contract.Retained)
    with pytest.raises(ValueError, match="no owner import"):
        primitive.begin(declared(), raw, fake_engine.initial)
    assert not fake_engine.events
