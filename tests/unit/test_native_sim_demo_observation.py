"""Real typed transport and installed-hook controls around inert public APIs."""

import ast
import hashlib
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace as NS

import pytest

from validation.betse import native_sim_demo_observation as observation
from validation.betse import native_sim_demo_software as software


@pytest.fixture(autouse=True)
def blocked(tmp_path):
    if os.environ.get(software.RELEASE) != "1":
        pytest.skip("Explicit frozen native-blocked observation software required")
    with software.blocked(tmp_path):
        yield


class Falsey(ValueError):
    def __bool__(self):
        return False


def wire(raw_hex):
    """Original typed-array grammar; no array library, owner or serializer call."""
    raw = bytes.fromhex(raw_hex)
    shape = [len(raw) // 8]
    return dict(
        tree=dict(
            type="array",
            column="column_000000",
            sha256=hashlib.sha256(raw).hexdigest(),
            layout=dict(
                dtype="<f8", shape=shape, strides_bytes=[8], C_contiguous=True, F_contiguous=True
            ),
        ),
        columns={"column_000000": dict(dtype="<f8", shape=shape, raw_bytes_hex=raw_hex)},
    )


def history_record(identity, count):
    """Producer-shaped inert closure metadata; no history or owner is issued."""
    return dict(
        law="actual_completed_SIM_read_only_complete_history_interval@1",
        status="completed_observation",
        trial_identity=identity,
        configured_rows=count,
        checked_rows=list(range(count)),
        work=[],
        full_authority_attempts=2,
        full_authority_returns=2,
        retained_payload_attempts=3 * count,
        retained_payload_returns=3 * count,
        source_metadata_operations=0,
        source_retained_cache_attempts=0,
        source_retained_cache_returns=0,
        callback_calls=[],
        native_or_scientific_credit=0,
    )


def protocol(monkeypatch, *, count=2, mode="original", fault=None):
    state = NS(sim_observation=None)
    model = NS(
        state=state,
        owner=object(),
        trial=NS(
            identity="a" * 64,
            iterations=tuple(range(count)),
            operator_mode=observation.OPERATOR_MODES[mode],
        ),
        calls=[],
        raw=[],
        record=None,
        fault=fault,
    )
    module = ModuleType(observation.MODULE)
    module.__file__ = observation.__file__
    exec(
        "def observe_completed(owner, *, enabled=False, capture):\n"
        "    return _observe(owner, enabled, capture)\n"
        "def _observe(owner, enabled, capture):\n"
        "    return _iteration(owner, enabled, capture)\n"
        "def _iteration(owner, enabled, capture):\n"
        "    return model.produce(owner, enabled, capture)\n"
        "def saved_view(request, *, accepted_observer_sha256=None):\n"
        "    raise AssertionError('No comparison during source observation')\n",
        vars(module),
    )
    module.model = model
    module.KEY_SHA256 = "c" * 64
    module.KEY_REVIEW = dict(path="/synthetic/issuer-review.json", sha256="d" * 64)
    module.WRITER_SHA256 = observation.WRITER_SHA256
    module.HISTORY_FILE, module.HISTORY_MODULE = observation.HISTORY, observation.HISTORY_MODULE
    module.HISTORY_SHA256 = "e" * 64
    module.HISTORY_REVIEW = dict(path="/synthetic/history-review.json", sha256="f" * 64)
    history, parent = ModuleType(observation.HISTORY_MODULE), ModuleType(observation.KEY_MODULE)
    history.__file__, parent.__file__ = (
        str(observation.ROOT / observation.HISTORY),
        str(observation.ROOT / observation.KEY),
    )
    history.parent = parent
    history.PARENT_SHA256, history.PARENT_REVIEW_SHA256 = "c" * 64, "d" * 64
    history.RELEASE = observation.HISTORY_RELEASE
    model.history, model.parent = history, parent
    monkeypatch.setitem(sys.modules, observation.HISTORY_MODULE, history)
    monkeypatch.setitem(sys.modules, observation.KEY_MODULE, parent)
    monkeypatch.setattr(observation, "_history_module", lambda api: (history, parent))
    model.module = module
    # Only producer issuance is synthetic; the actual consumer and writer run.
    monkeypatch.setitem(sys.modules, observation.MODULE, module)
    monkeypatch.setattr(observation, "preflight", lambda run_sha: {})
    monkeypatch.setattr(
        observation,
        "_original",
        lambda api: (
            observation._provider_atoms(
                api, ("observe_completed", "saved_view", "_observe", "_iteration")
            ),
            {
                name: vars(api)[name].__code__
                for name in ("observe_completed", "saved_view", "_observe", "_iteration")
            },
        ),
    )
    monkeypatch.setattr(observation, "OBSERVER_SHA256", "b" * 64)
    monkeypatch.setenv(observation.RELEASE, "1")
    monkeypatch.setenv(observation.HISTORY_RELEASE, "1")
    raw = wire("0000000000000080000000000000f87f")
    model.wire = raw

    def produce(owner, enabled, capture):
        assert owner is model.owner and enabled is True
        model.calls.append("entered")
        if model.fault is not None:
            model.fault(model, "entry")
        rows = []
        for i in range(1, count + 1):
            selected = capture(f"SIM.iteration_{i:04d}", raw)
            model.raw.append(selected)
            rows.append(dict(ordinal=i - 1, epoch=observation.EPOCH, files=selected))
        captures = {}
        for key, label in (
            ("before", "before_state"),
            ("ready", "ready_state"),
            ("final", "final_state"),
            ("rng_before", "rng_before"),
            ("rng_after", "rng_after"),
        ):
            captures[key] = capture("SIM." + label, raw)
        record = dict(
            kind=observation.KIND,
            status="completed_observation",
            epoch=observation.EPOCH,
            operator_mode=mode,
            source_operator_mode=observation.OPERATOR_MODES[mode],
            trial_identity=model.trial.identity,
            configured_iterations=count,
            iterations=rows,
            captures=captures,
            producer=dict(
                module="cells.processes.betse_native_sim_run",
                review=module.KEY_REVIEW,
                sha256="c" * 64,
                observer=dict(path=observation.OBSERVER, sha256="b" * 64),
                history=dict(
                    path=observation.HISTORY,
                    sha256=module.HISTORY_SHA256,
                    review=module.HISTORY_REVIEW,
                ),
            ),
            work=dict(history_interval=history_record(model.trial.identity, count)),
            numerical_parity_available=False,
            common_starting_authority_established=False,
            physical_checkpoint_credit=0,
        )
        model.record = record
        if model.fault is not None:
            model.fault(model, "return")
        return record

    model.produce = produce
    observation.bind(state, "c" * 64)
    return model


@pytest.mark.parametrize("mode", ("original", "disabled"))
def test_sim_observation_real_typed_roundtrip_preserves_same_return(monkeypatch, tmp_path, mode):
    model = protocol(monkeypatch, mode=mode)
    returned = observation.observe(
        model.state, model.owner, tmp_path / "observation", model.trial, mode
    )
    assert returned is model.record is model.state.sim_observation.raw_return
    assert model.state.sim_observation.owner is model.owner
    context = model.state.sim_observation
    assert context.completed and context.cleanup_complete and context.primary is None
    assert len(context.rows) == 7
    for row in context.rows:
        assert row["raw"] is model.wire
        assert (
            observation.evidence.read(row["pin"]["path"], expected_sha256=row["pin"]["sha256"])
            == model.wire
        )
    assert json.loads(Path(context.record_pin["path"]).read_text()) == returned
    assert observation.summary(model.state)["comparison_or_physical_credit"] is False
    with pytest.raises(ValueError, match="One prebound"):
        observation.observe(model.state, model.owner, tmp_path / "again", model.trial, mode)


@pytest.mark.parametrize("where", ("write", "record", "after_write", "callable", "record_mutation"))
@pytest.mark.parametrize("falsey", (False, True))
def test_sim_observation_raw_failures_never_publish_success(monkeypatch, tmp_path, where, falsey):
    primary = Falsey("capture") if falsey else OSError("capture")
    cause = ValueError("cause")
    primary.__cause__ = cause
    model = protocol(monkeypatch)
    publisher = observation.snapshot.write_json
    if where in ("write", "after_write"):
        original = observation.evidence.payload.write

        def underlying(path, raw, *args, **kwargs):
            if where == "after_write":
                original(path, raw, *args, **kwargs)
            raise primary

        monkeypatch.setattr(observation.evidence.payload, "write", underlying)
    elif where == "record":

        def publish(path, raw):
            if path.name == "record.json":
                path.write_text("{partial")
                raise primary
            return publisher(path, raw)

        monkeypatch.setattr(observation.snapshot, "write_json", publish)
    elif where == "callable":
        model.fault = lambda m, event: (
            setattr(m.module, "saved_view", lambda *args, **kwargs: None)
            if event == "return"
            else None
        )
    else:
        model.fault = lambda m, event: (
            m.record.update(trial_identity="d" * 64) if event == "return" else None
        )
    with pytest.raises(BaseException) as raised:
        observation.observe(
            model.state, model.owner, tmp_path / "observation", model.trial, "original"
        )
    context = model.state.sim_observation
    assert not context.completed and context.primary is not None
    assert context.cleanup_complete
    if where in ("write", "after_write", "record"):
        assert raised.value is primary and primary.__cause__ is cause
    if where == "record":
        assert context.raw_return is model.record
        assert (tmp_path / "observation/record.json").read_text() == "{partial"
    if where in ("write", "after_write"):
        assert context.raw_wire is model.wire and context.rows[0]["raw"] is model.wire
        assert len(context.rows) == 1


@pytest.mark.parametrize("hook", ("profile", "trace"))
@pytest.mark.parametrize("event", ("call", "return", "exception"))
@pytest.mark.parametrize("falsey", (False, True))
def test_sim_observation_installed_inherited_errors_keep_raw_primary(
    monkeypatch, tmp_path, hook, event, falsey
):
    model = protocol(monkeypatch)
    primary = Falsey("source") if falsey else ValueError("source")
    cause = OSError("original cause")
    primary.__cause__ = cause
    rejected = RuntimeError("observer rejected")
    if event == "exception":

        def fault(model, boundary):
            if boundary == "entry":
                raise primary

        model.fault = fault
    before = (sys.getprofile(), sys.gettrace())
    fired = []
    prior = before[0 if hook == "profile" else 1]

    def inherited(frame, observed, arg):
        if frame.f_code is model.module.observe_completed.__code__:
            target = "return" if hook == "profile" and event == "exception" else event
            if observed == target and not fired:
                fired.append(observed)
                raise rejected
        if prior is not None:
            prior(frame, observed, arg)
        return inherited

    setter = sys.setprofile if hook == "profile" else sys.settrace
    setter(inherited)
    selected = (sys.getprofile(), sys.gettrace())
    try:
        with pytest.raises(BaseException) as raised:
            observation.observe(
                model.state, model.owner, tmp_path / "observation", model.trial, "original"
            )
        assert sys.getprofile() is selected[0] and sys.gettrace() is selected[1]
    finally:
        sys.setprofile(before[0])
        sys.settrace(before[1])
    context = model.state.sim_observation
    assert fired and not context.completed and context.cleanup_complete
    if event == "exception":
        assert raised.value is primary and primary.__cause__ is cause
        assert context.raw_exception[1] is primary
    else:
        assert raised.value is rejected
    if event == "return":
        assert context.raw_return is model.record
    if event == "call":
        assert not model.calls


def test_sim_observation_binding_is_held_before_any_import(monkeypatch):
    attempted = []
    monkeypatch.setattr(observation.importlib, "import_module", lambda name: attempted.append(name))
    with pytest.raises(ValueError, match="unadopted"):
        observation.bind(NS(sim_observation=None), "c" * 64)
    assert attempted == []


def saved_policy(source, folder, run_sha):
    """Inert source declarations for saved-metadata controls; never imported."""
    folder.mkdir(parents=True, exist_ok=True)
    review = folder / "observer-review.json"
    review.write_text('{"scope":"synthetic byte binding only"}\n')
    review_pin = observation.pin(review)
    issuer = source / observation.SIM
    if issuer.exists():
        selected = observation.constants(issuer, ("SOURCE_PINS", "REVIEW_PINS"))
        assert selected["SOURCE_PINS"]["run"] == run_sha
        set_constant(issuer, "REVIEW_PINS", dict(selected["REVIEW_PINS"], run=review_pin["sha256"]))
    else:
        issuer.parent.mkdir(parents=True, exist_ok=True)
        issuer.write_text(
            "SOURCE_PINS = "
            + repr(dict(run=run_sha))
            + "\nREVIEW_PINS = "
            + repr(dict(run=review_pin["sha256"]))
            + "\n"
        )
        issuer.chmod(0o444)
    history_review = folder / "history-review.json"
    history_review.write_text('{"scope":"synthetic history byte binding only"}\n')
    history_review_pin = observation.pin(history_review)
    history = source / observation.HISTORY
    history.parent.mkdir(parents=True, exist_ok=True)
    if history.exists():
        history.chmod(0o644)
    history.write_text(
        "PARENT_SHA256 = "
        + repr(run_sha)
        + "\nPARENT_REVIEW_SHA256 = "
        + repr(review_pin["sha256"])
        + "\nRELEASE = "
        + repr(observation.HISTORY_RELEASE)
        + "\n"
    )
    history.chmod(0o444)
    provider = source / observation.OBSERVER
    provider.parent.mkdir(parents=True, exist_ok=True)
    if provider.exists():
        provider.chmod(0o644)
    provider.write_text(
        "KEY_SHA256 = "
        + repr(run_sha)
        + "\nKEY_REVIEW = "
        + repr(review_pin)
        + "\nWRITER_SHA256 = "
        + repr(observation.WRITER_SHA256)
        + "\nHISTORY_FILE = "
        + repr(observation.HISTORY)
        + "\nHISTORY_MODULE = "
        + repr(observation.HISTORY_MODULE)
        + "\nHISTORY_SHA256 = "
        + repr(observation.pin(history)["sha256"])
        + "\nHISTORY_REVIEW = "
        + repr(history_review_pin)
        + "\n"
    )
    provider.chmod(0o444)
    policy = dict(
        observation.declaration(),
        observer_sha256=observation.pin(provider)["sha256"],
        observer_review=review_pin,
    )
    helper = source / observation.FILE
    if helper.exists():
        helper.chmod(0o644)
    helper.write_text(
        "OBSERVER_SHA256 = "
        + repr(policy["observer_sha256"])
        + "\nOBSERVER_REVIEW = "
        + repr(review_pin)
        + "\n"
    )
    helper.chmod(0o444)
    writer = source / observation.WRITER
    if writer.exists():
        writer.chmod(0o644)
    writer.write_bytes(Path(observation.evidence.__file__).read_bytes())
    writer.chmod(0o444)
    return policy


def set_constant(path, name, value):
    """Rewrite only an inert fixture declaration, then explicitly reseal it."""
    lines = path.read_text().splitlines(keepends=True)
    node = next(
        n
        for n in ast.parse("".join(lines)).body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
    )
    lines[node.lineno - 1 : node.end_lineno] = [f"{name} = {value!r}\n"]
    path.chmod(0o644)
    path.write_text("".join(lines))
    path.chmod(0o444)


def history_binding_fixture(monkeypatch, tmp_path):
    source = tmp_path / "source"
    key = source / observation.KEY
    key.parent.mkdir(parents=True)
    key.write_text("# inert issuer source, never imported or invoked\n")
    key.chmod(0o444)
    run_sha = observation.pin(key)["sha256"]
    policy = saved_policy(source, tmp_path / "reviews", run_sha)
    provider = source / observation.OBSERVER
    provider.chmod(0o644)
    with provider.open("a") as stream:
        stream.write(
            "def observe_completed(owner, *, enabled=False, capture):\n"
            "    raise AssertionError('No native or issued owner in metadata binding')\n"
            "def saved_view(request, *, accepted_observer_sha256=None):\n"
            "    raise AssertionError('No model or comparison in metadata binding')\n"
        )
    provider.chmod(0o444)
    policy["observer_sha256"] = observation.pin(provider)["sha256"]
    set_constant(source / observation.FILE, "OBSERVER_SHA256", policy["observer_sha256"])
    module, history, parent = (
        ModuleType(name)
        for name in (observation.MODULE, observation.HISTORY_MODULE, observation.KEY_MODULE)
    )
    module.__file__, history.__file__, parent.__file__ = map(
        str, (provider, source / observation.HISTORY, key)
    )
    # Only this inert consumer protocol is compiled and executed. The history
    # and issuer contain literal metadata and are never imported or called.
    exec(compile(provider.read_bytes(), str(provider), "exec", dont_inherit=True), vars(module))
    vars(history).update(
        observation.constants(
            source / observation.HISTORY, ("PARENT_SHA256", "PARENT_REVIEW_SHA256", "RELEASE")
        )
    )
    history.parent = parent
    for api in (module, history, parent):
        monkeypatch.setitem(sys.modules, api.__name__, api)
    monkeypatch.setattr(observation, "ROOT", source)
    monkeypatch.setattr(observation, "OBSERVER_SHA256", policy["observer_sha256"])
    monkeypatch.setattr(observation, "OBSERVER_REVIEW", policy["observer_review"])
    monkeypatch.setattr(observation.evidence, "__file__", str(source / observation.WRITER))
    for gate in (observation.RELEASE, observation.HISTORY_RELEASE):
        monkeypatch.setenv(gate, "1")
    return NS(
        source=source,
        policy=policy,
        run_sha=run_sha,
        module=module,
        history=history,
        parent=parent,
        state=NS(sim_observation=None),
    )


def history_files(model):
    return {
        name: observation.pin(model.source / name)["sha256"]
        for name in (
            observation.FILE,
            observation.OBSERVER,
            observation.KEY,
            observation.WRITER,
            observation.HISTORY,
            observation.SIM,
        )
    }


def reseal_history_fixture(model, *, history_changed=False):
    if history_changed:
        set_constant(
            model.source / observation.OBSERVER,
            "HISTORY_SHA256",
            observation.pin(model.source / observation.HISTORY)["sha256"],
        )
    model.policy["observer_sha256"] = observation.pin(model.source / observation.OBSERVER)["sha256"]
    set_constant(
        model.source / observation.FILE, "OBSERVER_SHA256", model.policy["observer_sha256"]
    )


def test_sim_observation_history_real_metadata_binding_is_held_and_same_issuer(
    monkeypatch, tmp_path
):
    model = history_binding_fixture(monkeypatch, tmp_path)
    observed = observation.contract(model.source, model.policy, history_files(model), model.run_sha)
    assert (
        observed["HISTORY_SHA256"] == observation.pin(model.source / observation.HISTORY)["sha256"]
    )
    observation.bind(model.state, model.run_sha)
    context = model.state.sim_observation
    assert context.history is model.history and context.parent is model.parent
    assert context.history.parent is context.parent
    assert context.started is False and context.completed is False and context.owner is None
    assert not context.rows and context.raw_return is None
    assert observation.HISTORY in observation.preflight(model.run_sha)


@pytest.mark.parametrize("value", (None, "0", "true"))
def test_sim_observation_history_gate_refuses_before_any_provider_import(
    monkeypatch, tmp_path, value
):
    model = history_binding_fixture(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr(observation.importlib, "import_module", lambda name: calls.append(name))
    if value is None:
        monkeypatch.delenv(observation.HISTORY_RELEASE)
    else:
        monkeypatch.setenv(observation.HISTORY_RELEASE, value)
    with pytest.raises(ValueError, match="completed-history release"):
        observation.bind(model.state, model.run_sha)
    assert not calls and model.state.sim_observation is None


@pytest.mark.parametrize(
    "fault",
    (
        "missing_source",
        "changed_source",
        "source_pin",
        "file",
        "module",
        "review",
        "parent",
        "parent_review",
        "release",
    ),
)
def test_sim_observation_history_contract_rejects_resealed_foreign_lineage(
    monkeypatch, tmp_path, fault
):
    model = history_binding_fixture(monkeypatch, tmp_path)
    files = history_files(model)
    observation.contract(model.source, model.policy, files, model.run_sha)
    provider, history = model.source / observation.OBSERVER, model.source / observation.HISTORY
    if fault == "missing_source":
        del files[observation.HISTORY]
    elif fault == "changed_source":
        history.chmod(0o644)
        history.write_text(history.read_text() + "# changed bytes\n")
    else:
        field, value = {
            "source_pin": ("HISTORY_SHA256", "0" * 64),
            "file": ("HISTORY_FILE", "src/cells/processes/foreign.py"),
            "module": ("HISTORY_MODULE", "cells.processes.foreign"),
            "review": ("HISTORY_REVIEW", dict(model.module.HISTORY_REVIEW, sha256="0" * 64)),
            "parent": ("PARENT_SHA256", "0" * 64),
            "parent_review": ("PARENT_REVIEW_SHA256", "0" * 64),
            "release": ("RELEASE", "CELLS_FOREIGN_RELEASED"),
        }[fault]
        history_changed = fault in ("parent", "parent_review", "release")
        set_constant(history if history_changed else provider, field, value)
        reseal_history_fixture(model, history_changed=history_changed)
        files = history_files(model)
    with pytest.raises(ValueError):
        observation.contract(model.source, model.policy, files, model.run_sha)


@pytest.mark.parametrize("fault", ("parent", "parent_review", "registry", "origin", "release"))
def test_sim_observation_history_live_declarations_cannot_replace_static_issuer(
    monkeypatch, tmp_path, fault
):
    model = history_binding_fixture(monkeypatch, tmp_path)
    observation.contract(model.source, model.policy, history_files(model), model.run_sha)
    if fault == "parent":
        model.history.parent = ModuleType(observation.KEY_MODULE)
    elif fault == "parent_review":
        model.history.PARENT_REVIEW_SHA256 = "0" * 64
    elif fault == "registry":
        monkeypatch.setitem(sys.modules, observation.KEY_MODULE, ModuleType(observation.KEY_MODULE))
    elif fault == "origin":
        model.history.__file__ = str(tmp_path / "foreign.py")
    else:
        model.history.RELEASE = "CELLS_FOREIGN_RELEASED"
    with pytest.raises((ValueError, AttributeError)):
        observation.bind(model.state, model.run_sha)
    assert model.state.sim_observation is None


@pytest.mark.parametrize("hook", ("profile", "trace"))
@pytest.mark.parametrize("fault", ("parent", "review", "provider", "registry", "gate"))
def test_sim_observation_history_inherited_mutation_stops_before_delegate(
    monkeypatch, tmp_path, hook, fault
):
    model = protocol(monkeypatch)
    old = (sys.getprofile(), sys.gettrace())
    fired = []

    def inherited(frame, event, arg):
        previous = old[0 if hook == "profile" else 1]
        if previous is not None:
            previous(frame, event, arg)
        if (
            frame.f_code is model.module.observe_completed.__code__
            and event == "call"
            and not fired
        ):
            fired.append(event)
            if fault == "parent":
                model.history.parent = object()
            elif fault == "review":
                model.history.PARENT_REVIEW_SHA256 = "0" * 64
            elif fault == "provider":
                model.module.HISTORY_REVIEW["sha256"] = "0" * 64
            elif fault == "registry":
                monkeypatch.setitem(
                    sys.modules, observation.HISTORY_MODULE, ModuleType(observation.HISTORY_MODULE)
                )
            else:
                monkeypatch.setenv(observation.HISTORY_RELEASE, "0")
        return inherited

    (sys.setprofile if hook == "profile" else sys.settrace)(inherited)
    selected = (sys.getprofile(), sys.gettrace())
    try:
        with pytest.raises(ValueError):
            observation.observe(
                model.state, model.owner, tmp_path / "observation", model.trial, "original"
            )
        assert sys.getprofile() is selected[0] and sys.gettrace() is selected[1]
    finally:
        sys.setprofile(old[0])
        sys.settrace(old[1])
    context = model.state.sim_observation
    assert fired and not model.calls and not context.rows and not context.completed
    assert context.primary is not None and context.cleanup_complete


@pytest.mark.parametrize("fault", ("missing", "source", "review", "rows", "exit", "payloads"))
def test_sim_observation_history_incomplete_record_keeps_raw_return_and_all_captures(
    monkeypatch, tmp_path, fault
):
    def mutate(model, when):
        if when != "return":
            return
        record = model.record
        if fault == "missing":
            del record["producer"]["history"]
        elif fault == "source":
            record["producer"]["history"]["sha256"] = "0" * 64
        elif fault == "review":
            record["producer"]["history"]["review"] = dict(path="/foreign", sha256="0" * 64)
        elif fault == "rows":
            record["work"]["history_interval"]["checked_rows"] = [0]
        elif fault == "exit":
            record["work"]["history_interval"]["full_authority_returns"] = 1
        else:
            record["work"]["history_interval"]["retained_payload_returns"] = 0

    model = protocol(monkeypatch, fault=mutate)
    with pytest.raises(ValueError):
        observation.observe(
            model.state, model.owner, tmp_path / "observation", model.trial, "original"
        )
    context = model.state.sim_observation
    assert context.raw_return is model.record and context.record is model.record
    assert len(context.rows) == 7 and all(row["status"] == "saved" for row in context.rows)
    assert context.primary is not None and not context.completed and context.record_pin is None
    assert not (tmp_path / "observation/record.json").exists()


def saved_observation(folder, policy, run_sha, identity, *, source, count=3, mode="original"):
    folder.mkdir(parents=True)
    provider = observation.constants(source / observation.OBSERVER, observation.DECLARATIONS)
    rows, iterations, captures = [], [], {}
    raw = wire("0000000000000080" * 4096)

    def capture(label):
        target = folder / f"capture-{len(rows):04d}.json"
        observation.evidence.write(target, raw, label=label)
        selected = observation.pin(target)
        rows.append(dict(label=label, status="saved", pin=selected, attempted_path=str(target)))
        return selected

    for i in range(1, count + 1):
        iterations.append(
            dict(ordinal=i - 1, epoch=observation.EPOCH, files=capture(f"SIM.iteration_{i:04d}"))
        )
    for key, label in (
        ("before", "before_state"),
        ("ready", "ready_state"),
        ("final", "final_state"),
        ("rng_before", "rng_before"),
        ("rng_after", "rng_after"),
    ):
        captures[key] = capture("SIM." + label)
    record = dict(
        kind=observation.KIND,
        status="completed_observation",
        epoch=observation.EPOCH,
        operator_mode=mode,
        source_operator_mode=observation.OPERATOR_MODES[mode],
        trial_identity=identity,
        configured_iterations=count,
        iterations=iterations,
        captures=captures,
        producer=dict(
            module="cells.processes.betse_native_sim_run",
            sha256=run_sha,
            review=policy["observer_review"],
            observer=dict(path=observation.OBSERVER, sha256=policy["observer_sha256"]),
            history=dict(
                path=observation.HISTORY,
                sha256=provider["HISTORY_SHA256"],
                review=provider["HISTORY_REVIEW"],
            ),
        ),
        work=dict(history_interval=history_record(identity, count)),
        numerical_parity_available=False,
        common_starting_authority_established=False,
        physical_checkpoint_credit=0,
    )
    observation.snapshot.write_json(folder / "record.json", record)
    return dict(
        started=True,
        completed=True,
        record=observation.pin(folder / "record.json"),
        cleanup_complete=True,
        primary_present=False,
        capture_errors=0,
        captures=rows,
        raw_return_retained=True,
        raw_partial_retained=False,
        comparison_or_physical_credit=False,
    )


@pytest.mark.parametrize("mutation", ("keyword", "module", "writer", "record_bytes"))
def test_sim_observation_fresh_mutation_refuses_even_after_bound_entry(
    monkeypatch, tmp_path, mutation
):
    model = protocol(monkeypatch)
    if mutation == "keyword":
        model.module.observe_completed.__kwdefaults__["enabled"] = True
    elif mutation == "module":
        monkeypatch.setitem(sys.modules, observation.MODULE, ModuleType(observation.MODULE))
    elif mutation == "writer":
        monkeypatch.setattr(observation.evidence, "write", lambda *args, **kwargs: None)
    else:
        observation.observe(
            model.state, model.owner, tmp_path / "observation", model.trial, "original"
        )
        Path(model.state.sim_observation.record_pin["path"]).write_text("{}")
        with pytest.raises(ValueError):
            observation.finish(model.state, model.trial, "original")
        return
    with pytest.raises(ValueError):
        observation.observe(
            model.state, model.owner, tmp_path / "observation", model.trial, "original"
        )
    assert not model.calls and not model.state.sim_observation.completed


def test_sim_observation_caught_reentry_remains_failed(monkeypatch, tmp_path):
    model = protocol(monkeypatch)
    caught = []

    def fault(model, boundary):
        if boundary == "entry" and not caught:
            try:
                model.module.observe_completed(
                    model.owner, enabled=True, capture=lambda *args: None
                )
            except ValueError as error:
                caught.append(error)

    model.fault = fault
    with pytest.raises(ValueError) as raised:
        observation.observe(
            model.state, model.owner, tmp_path / "observation", model.trial, "original"
        )
    assert caught and raised.value is caught[0]
    assert not model.state.sim_observation.completed and not model.state.sim_observation.rows


def test_sim_observation_closed_partial_context_retained_on_provider_refusal(monkeypatch, tmp_path):
    model = protocol(monkeypatch)
    primary = Falsey("provider refused")
    primary.partial = NS(owner=model.owner, raw=object())
    primary.__cause__ = OSError("source failed")

    def fault(model, boundary):
        if boundary == "entry":
            raise primary

    model.fault = fault
    with pytest.raises(Falsey) as raised:
        observation.observe(
            model.state, model.owner, tmp_path / "observation", model.trial, "original"
        )
    assert raised.value is primary
    assert model.state.sim_observation.partial is primary.partial
    assert observation.summary(model.state)["raw_partial_retained"] is True


@pytest.mark.parametrize("hook", ("profile", "trace"))
def test_sim_observation_hook_removal_stops_capture_and_recovers_both(monkeypatch, tmp_path, hook):
    model = protocol(monkeypatch)
    before = (sys.getprofile(), sys.gettrace())

    def fault(model, boundary):
        if boundary == "entry":
            (sys.setprofile if hook == "profile" else sys.settrace)(None)

    model.fault = fault
    with pytest.raises(ValueError, match="hooks changed"):
        observation.observe(
            model.state, model.owner, tmp_path / "observation", model.trial, "original"
        )
    assert sys.getprofile() is before[0] and sys.gettrace() is before[1]
    assert not model.state.sim_observation.rows and not model.state.sim_observation.completed


@pytest.mark.parametrize("fault", ("outside", "digest", "extra"))
def test_sim_observation_original_inventory_binds_actual_runtime(tmp_path, fault):
    root = tmp_path / "original"
    (root / "betse").mkdir(parents=True)
    source = root / "betse/module.py"
    source.write_text("# inert source\n")
    declared = observation.original_sources(root)
    value = dict(loaded_files={"betse.module": observation.pin(source)})
    observation.runtime_sources(value, declared)
    if fault == "outside":
        outside = tmp_path / "outside.py"
        outside.write_text(source.read_text())
        value["loaded_files"]["betse.module"] = observation.pin(outside)
    elif fault == "digest":
        value["loaded_files"]["betse.module"]["sha256"] = "0" * 64
    else:
        value["loaded_files"]["betse.extra"] = dict(
            path=str(root / "betse/extra.py"), sha256="0" * 64
        )
    with pytest.raises(ValueError):
        observation.runtime_sources(value, declared)


@pytest.mark.parametrize("hook", ("profile", "trace"))
def test_sim_observation_unwinding_helper_return_rejection_recovers_outer_epoch(
    monkeypatch, tmp_path, hook
):
    model = protocol(monkeypatch)
    primary = Falsey("actual original source failure")
    primary.__cause__ = OSError("source cause")

    def fault(model, boundary):
        if boundary == "entry":
            raise primary

    model.fault = fault
    rejected = RuntimeError("inherited outer unwind rejection")
    before = (sys.getprofile(), sys.gettrace())
    prior = before[0 if hook == "profile" else 1]
    fired = []

    def inherited(frame, event, arg):
        if frame.f_code is observation._invoke.__code__ and event == "return" and not fired:
            fired.append(event)
            raise rejected
        if prior is not None:
            prior(frame, event, arg)
        return inherited

    (sys.setprofile if hook == "profile" else sys.settrace)(inherited)
    selected = (sys.getprofile(), sys.gettrace())
    try:
        with pytest.raises(Falsey) as caught:
            observation.observe(
                model.state, model.owner, tmp_path / "observation", model.trial, "original"
            )
        assert caught.value is primary and primary.__cause__.args == ("source cause",)
        assert sys.getprofile() is selected[0] and sys.gettrace() is selected[1]
    finally:
        sys.setprofile(before[0])
        sys.settrace(before[1])
    assert fired and model.state.sim_observation.cleanup_complete
    assert any(error is rejected for _, error in model.state.sim_observation.secondary)


@pytest.mark.parametrize("field", ("tree", "columns"))
def test_sim_observation_rejects_untyped_array_transport_before_writer(
    monkeypatch, tmp_path, field
):
    model = protocol(monkeypatch)
    model.wire[field] = []
    with pytest.raises(ValueError, match="already typed"):
        observation.observe(
            model.state, model.owner, tmp_path / "observation", model.trial, "original"
        )
    assert not model.state.sim_observation.rows
    assert model.state.sim_observation.raw_wire is model.wire
    assert list((tmp_path / "observation").iterdir()) == []


@pytest.mark.parametrize("mutation", ("function", "code", "defaults", "delegate", "moduleclass"))
def test_sim_observation_warm_helper_binding_refuses_retarget_before_body(
    monkeypatch, tmp_path, mutation
):
    model = protocol(monkeypatch)
    context = model.state.sim_observation
    observation._check(context)
    foreign_calls = []

    def foreign(owner, enabled, capture):
        foreign_calls.append(owner)

    if mutation == "function":
        model.module._iteration = foreign
    elif mutation == "code":
        # Exact globals and public exports remain intact; only helper code moves.
        exec("def foreign(owner, enabled, capture):\n    return None\n", vars(model.module))
        model.module._iteration.__code__ = model.module.foreign.__code__
    elif mutation == "defaults":
        model.module._iteration.__defaults__ = (None,)
    elif mutation == "delegate":
        model.module._iteration.__wrapped__ = foreign
    else:

        class ForeignModule(ModuleType):
            def __getattribute__(self, name):
                if name == "observe_completed":
                    foreign_calls.append(name)
                    return foreign
                return super().__getattribute__(name)

        model.module.__class__ = ForeignModule
    with pytest.raises(ValueError):
        observation.observe(
            model.state, model.owner, tmp_path / "observation", model.trial, "original"
        )
    assert not foreign_calls and not model.calls and not context.rows and not context.completed


@pytest.mark.parametrize("hook", ("profile", "trace"))
@pytest.mark.parametrize("boundary", ("observe_completed", "_observe", "_iteration"))
@pytest.mark.parametrize("target", ("_observe", "_iteration"))
def test_sim_observation_installed_callback_cannot_retarget_pinned_helper(
    monkeypatch, tmp_path, hook, boundary, target
):
    model = protocol(monkeypatch)
    expected_code = vars(model.module)[boundary].__code__
    foreign_calls, fired = [], []

    def foreign(*args, **kwargs):
        foreign_calls.append((args, kwargs))
        return model.record

    before = (sys.getprofile(), sys.gettrace())
    prior = before[0 if hook == "profile" else 1]

    def inherited(frame, event, arg):
        if frame.f_code is expected_code and event == "call" and not fired:
            fired.append(event)
            setattr(model.module, target, foreign)
        if prior is not None:
            prior(frame, event, arg)
        return inherited

    (sys.setprofile if hook == "profile" else sys.settrace)(inherited)
    selected = (sys.getprofile(), sys.gettrace())
    try:
        with pytest.raises(ValueError):
            observation.observe(
                model.state, model.owner, tmp_path / "observation", model.trial, "original"
            )
        assert sys.getprofile() is selected[0] and sys.gettrace() is selected[1]
    finally:
        sys.setprofile(before[0])
        sys.settrace(before[1])
    context = model.state.sim_observation
    assert fired and not foreign_calls and not model.calls
    assert context.primary is not None and not context.completed and context.cleanup_complete
    assert not context.rows and context.raw_return is None


@pytest.mark.parametrize("mutation", (None, "code", "default", "namespace", "delegate"))
def test_sim_observation_bootstrap_authenticates_complete_synthetic_module_without_helper_call(
    monkeypatch, tmp_path, mutation
):
    path = tmp_path / observation.OBSERVER
    path.parent.mkdir(parents=True)
    raw = (
        "KEY_SHA256 = None\nKEY_REVIEW = None\nWRITER_SHA256 = None\n"
        "HISTORY_FILE = None\nHISTORY_MODULE = None\nHISTORY_SHA256 = None\nHISTORY_REVIEW = None\n"
        "class ObservationRejected(ValueError):\n"
        "    def __init__(self, message, *, partial=None):\n"
        "        super().__init__(message)\n"
        "        self.partial = partial\n"
        "def _iteration(value, depth=0):\n"
        "    raise AssertionError('metadata body must remain uncalled')\n"
        "def _observe(owner, capture):\n"
        "    return _iteration(owner)\n"
        "def observe_completed(owner, *, enabled=False, capture):\n"
        "    return _observe(owner, capture)\n"
        "def saved_view(request, *, accepted_observer_sha256=None):\n"
        "    return _iteration(request)\n"
    )
    path.write_text(raw)
    module = ModuleType(observation.MODULE)
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec", dont_inherit=True), vars(module))
    monkeypatch.setattr(observation, "ROOT", tmp_path)
    monkeypatch.setitem(sys.modules, observation.MODULE, module)
    atoms, codes = observation._original(module)
    assert set(codes) == {
        "ObservationRejected.__init__",
        "_iteration",
        "_observe",
        "observe_completed",
        "saved_view",
    }
    assert atoms == observation._provider_atoms(module, codes)
    if mutation is None:
        return
    if mutation == "code":
        module._iteration.__code__ = module._observe.__code__
    elif mutation == "default":
        module._iteration.__defaults__ = (False,)
    elif mutation == "namespace":
        from types import FunctionType

        module._iteration = FunctionType(
            module._iteration.__code__, dict(vars(module)), argdefs=(0,)
        )
    else:
        module._iteration.__wrapped__ = module._observe
    with pytest.raises(ValueError, match="observation helper|default types"):
        observation._original(module)


def test_sim_observation_line_hook_cannot_retarget_helper_to_c_delegate(monkeypatch, tmp_path):
    model = protocol(monkeypatch)
    code = model.module.observe_completed.__code__
    before = (sys.getprofile(), sys.gettrace())
    fired, foreign_entries = [], []

    def inherited_trace(frame, event, arg):
        if frame.f_code is code and event == "line" and not fired:
            fired.append(event)
            model.module._observe = pow
        if before[1] is not None:
            before[1](frame, event, arg)
        return inherited_trace

    def inherited_profile(frame, event, arg):
        if event == "c_call" and arg is pow:
            foreign_entries.append(arg)
        if before[0] is not None:
            before[0](frame, event, arg)

    sys.setprofile(inherited_profile)
    sys.settrace(inherited_trace)
    try:
        with pytest.raises(ValueError, match="Original observation helper"):
            observation.observe(
                model.state, model.owner, tmp_path / "observation", model.trial, "original"
            )
        assert sys.getprofile() is inherited_profile and sys.gettrace() is inherited_trace
    finally:
        sys.setprofile(before[0])
        sys.settrace(before[1])
    assert fired and not foreign_entries and not model.calls
    assert not model.state.sim_observation.completed and not model.state.sim_observation.rows
