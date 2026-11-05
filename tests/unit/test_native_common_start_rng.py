"""Blocked synthetic RNG-program controls, never a replacement RNG or parent.

Positive providers exist only in private copied module namespaces. No actual
seed, draw, generator construction, getstate or native body is called here.
"""

import contextlib
import copy
import json
import random
import struct
import sys
from pathlib import Path
from types import FunctionType, ModuleType
from types import SimpleNamespace as NS

import numpy as np
import pytest

from tests.unit import test_betse_native_world_phase_construction as inherited
from validation.betse import native_common_start_rng as stage
from validation.betse import native_common_start_rng_software as software


@pytest.fixture(autouse=True)
def blocked(request, tmp_path):
    scope = dict(
        vars(inherited),
        software=NS(**dict(vars(software), reuse=software.base.reuse.reuse)),
        _BLOCKADE_FAILURES=(),
    )
    function = FunctionType(inherited._blockade.__wrapped__.__code__, scope)
    attempted = []
    py = random._inst
    ng = np.random.mtrand._rand

    def profile(frame, event, arg):
        owner = getattr(arg, "__self__", None) if event == "c_call" else frame.f_locals.get("self")
        python_entry = (
            event == "call"
            and frame.f_globals.get("__name__") == "random"
            and (frame.f_code.co_name in ("seed", "getstate", "setstate", "__init__"))
        )
        c_entry = event == "c_call" and (owner is py or owner is ng or owner is np.random.mtrand)
        if python_entry or c_entry:
            attempted.append((frame.f_code.co_qualname, event, getattr(arg, "__name__", None)))
            raise AssertionError("Actual global RNG state/seed/draw/constructor held")

    with contextlib.contextmanager(function)(request, tmp_path):
        old = sys.getprofile()

        def chained(frame, event, arg):
            if old is not None:
                old(frame, event, arg)
            profile(frame, event, arg)

        try:
            sys.setprofile(chained)
            yield
            assert attempted == []
        finally:
            sys.setprofile(old)
            software.snapshot.write_json(
                tmp_path / "RNG-program-blocked.json", dict(attempted=attempted)
            )


def _program(module=stage, **changes):
    values = dict(
        python_seed=2437,
        numpy_seed=5211,
        input_identity="a" * 64,
        consumer_sources=dict(cells="b" * 64, original="c" * 64),
    )
    values.update(changes)
    return module.declare(**values)


def _model(monkeypatch, tmp_path):
    name = "metadata_common_start_" + str(id(tmp_path))
    module = ModuleType(name)
    module.__file__ = stage.__file__
    monkeypatch.setitem(sys.modules, name, module)
    exec(compile(Path(stage.__file__).read_bytes(), stage.__file__, "exec"), vars(module))
    events = []

    class Python:
        def __init__(self):
            self.state = (3, tuple([2] * 624 + [5]), -0.0)
            self.failure = None

        def seed(self, a, version=2):
            events.append(("python_seed", a, version))
            if self.failure is not None:
                raise self.failure
            self.state = (3, tuple([a] * 624 + [624]), None)

        def getstate(self):
            events.append(("python_get",))
            return self.state

    class Numpy:
        def __init__(self):
            self.state = ("MT19937", np.full(624, 7, dtype=np.uint32), 9, 1, -0.0)
            self.failure = None

        def seed(self, seed):
            events.append(("numpy_seed", seed))
            if self.failure is not None:
                raise self.failure
            self.state = ("MT19937", np.full(624, seed, dtype=np.uint32), 624, 0, 0.0)

        def get_state(self):
            events.append(("numpy_get",))
            value = self.state
            return (value[0], value[1].copy(), *value[2:])

    py, ng = Python(), Numpy()
    binding = dict(
        python=py,
        numpy=ng,
        delegates=dict(
            python_seed=py.seed, python_get=py.getstate, numpy_seed=ng.seed, numpy_get=ng.get_state
        ),
    )

    def consumer():
        raise AssertionError("Synthetic boundary never executes a consumer")

    state = object()
    module._boundary = lambda program, actual, role, frame: (
        actual,
        object(),
        object(),
        frame,
        consumer,
        module._function(consumer),
    )
    module._runtime = lambda: binding
    module._check_runtime = lambda actual: None
    module.provenance = NS(
        FILE=stage.provenance.FILE,
        binding=lambda: dict(kind="synthetic_runtime_only", sha256="d" * 64),
    )
    monkeypatch.setenv(module.RELEASE, "1")
    return NS(
        api=module,
        program=_program(module),
        state=state,
        py=py,
        ng=ng,
        binding=binding,
        events=events,
        output=tmp_path / "evidence",
    )


@pytest.mark.parametrize(
    "field,value",
    (
        ("python_seed", None),
        ("python_seed", True),
        ("python_seed", -1),
        ("python_seed", 2**256),
        ("numpy_seed", True),
        ("numpy_seed", -1),
        ("numpy_seed", 2**32),
        ("numpy_seed", 1.0),
        ("input_identity", "bad"),
        ("consumer_sources", {"cells": "b" * 64}),
    ),
)
def test_common_rng_declaration_rejects_unowned_or_unbounded_inputs_without_call(field, value):
    with pytest.raises((ValueError, TypeError)):
        _program(**{field: value})
    assert stage._ATTEMPT is None


def test_common_rng_declaration_is_data_not_an_RNG_or_phase_owner():
    program = _program()
    doc = stage.program_document(program)
    assert program.identity == stage._digest(doc)
    assert doc["operations"] == [list(row) for row in stage.STEPS]
    assert doc["draws"] == 0 and doc["setstate_or_generator_replacement"] is False
    assert stage.source_plan()["default"].startswith("ambient mode untouched")
    assert stage._ATTEMPT is None


@pytest.mark.parametrize("enabled,flag", ((False, None), (True, None), (1, "1")))
def test_common_rng_release_gate_precedes_any_foreign_state_or_output_read(
    monkeypatch, enabled, flag
):
    class Foreign:
        def __getattribute__(self, name):
            raise AssertionError("Foreign value read before release")

    if flag is None:
        monkeypatch.delenv(stage.RELEASE, raising=False)
    else:
        monkeypatch.setenv(stage.RELEASE, flag)
    with pytest.raises(stage.CommonStartRejected) as caught:
        stage.initialize(Foreign(), Foreign(), role="cells", output=Foreign(), enabled=enabled)
    assert caught.value.stage == "release" and stage._ATTEMPT is None


def test_common_rng_actual_runtime_identity_inspection_never_calls_a_generator(tmp_path):
    software.snapshot.write_json(
        tmp_path / "actual-RNG-dispatch.json",
        {
            name: dict(
                type=type(fn).__module__ + "." + type(fn).__qualname__,
                module=getattr(fn, "__module__", None),
                name=getattr(fn, "__name__", None),
                receiver_type=type(getattr(fn, "__self__", None)).__qualname__,
                receiver_is_numpy=getattr(fn, "__self__", None) is np.random.mtrand._rand,
                receiver_is_module=getattr(fn, "__self__", None) is np.random.mtrand,
                mtrand_export=fn is vars(np.random.mtrand)[name],
                actual_calls=0,
            )
            for name, fn in (("seed", np.random.seed), ("get_state", np.random.get_state))
        },
    )
    binding = stage._runtime()
    stage._check_runtime(binding)
    assert binding["python"] is random._inst and binding["numpy"] is np.random.mtrand._rand
    software.snapshot.write_json(
        tmp_path / "actual-RNG-metadata.json",
        dict(
            scope="metadata only; no state getter, setter, seed, draw or constructor",
            python=id(binding["python"]),
            numpy=id(binding["numpy"]),
            python_seed_type=type(binding["delegates"]["python_seed"]).__name__,
            numpy_seed_type=type(binding["delegates"]["numpy_seed"]).__name__,
            numpy_seed_receiver=type(
                getattr(binding["delegates"]["numpy_seed"], "__self__", None)
            ).__name__,
            actual_RNG_calls=0,
        ),
    )


@pytest.mark.parametrize("kind", ("python", "numpy"))
def test_common_rng_bits_keep_gaussian_signed_zero_and_nan_payloads(kind):
    for bits in (0x8000000000000000, 0x7FF8000000000001, 0xFFF8000000000002):
        value = struct.unpack("<d", bits.to_bytes(8, "little"))[0]
        raw = (
            (3, tuple([5] * 624 + [624]), value)
            if kind == "python"
            else ("MT19937", np.full(624, 5, dtype=np.uint32), 624, 1, value)
        )
        result = stage._state(raw, kind)
        assert result[-1]["float64_bits"] == bits.to_bytes(8, "little").hex()
        assert json.loads(json.dumps(result)) == result


@pytest.mark.parametrize(
    "kind,raw",
    (
        ("python", (True, (), None)),
        ("python", [3, (), None]),
        ("numpy", ("MT19937", np.zeros(3), 0, 0, 0.0)),
    ),
)
def test_common_rng_missing_state_words_or_categories_refuse_without_regeneration(kind, raw):
    with pytest.raises(ValueError, match="Exact"):
        stage._state(raw, kind)


def test_common_rng_synthetic_program_keeps_exact_order_and_independent_readbacks(
    monkeypatch, tmp_path
):
    model = _model(monkeypatch, tmp_path)
    prior = sys.getprofile(), sys.gettrace()
    receipt = model.api.initialize(
        model.program, model.state, role="cells", output=model.output, enabled=True
    )
    assert (sys.getprofile(), sys.gettrace()) == prior
    assert len(model.events) == 8
    assert [row[0] for row in model.events] == [name for _, name, _ in stage.STEPS]
    assert model.events[2] == ("python_seed", 2437, 2) and model.events[4] == ("numpy_seed", 5211)
    assert len(model.api._ATTEMPT["states"]) == 6
    assert receipt["state"]["python_after"] == receipt["state"]["python_readback"]
    assert receipt["state"]["numpy_after"] == receipt["state"]["numpy_readback"]
    assert receipt["work"]["program_API_calls"] == 8 and model.api._ATTEMPT["hooks_restored"]
    assert receipt["biological_or_phase_admission"] is False and stage._ATTEMPT is None
    assert (model.output / "COMPLETED.json").is_file()
    with pytest.raises(model.api.CommonStartRejected) as caught:
        model.api.initialize(
            model.program, model.state, role="cells", output=tmp_path / "again", enabled=True
        )
    assert caught.value.stage == "once" and len(model.events) == 8


@pytest.mark.parametrize("target", ("python", "numpy"))
def test_common_rng_failed_program_preserves_primary_partial_state_and_irreversible_attempt(
    monkeypatch, tmp_path, target
):
    model = _model(monkeypatch, tmp_path)
    primary, cause = ValueError("original synthetic seed error"), OSError("original cause")
    primary.__cause__ = cause
    getattr(model, "py" if target == "python" else "ng").failure = primary
    prior = sys.getprofile(), sys.gettrace()
    with pytest.raises(ValueError) as caught:
        model.api.initialize(
            model.program, model.state, role="cells", output=model.output, enabled=True
        )
    assert caught.value is primary and primary.__cause__ is cause
    attempt = model.api._ATTEMPT
    assert primary.common_start_attempt is attempt and attempt["record"] is None
    assert (sys.getprofile(), sys.gettrace()) == prior and attempt["hooks_restored"]
    assert set(attempt["states"]) == (
        {"python_before", "numpy_before"}
        if target == "python"
        else {"python_before", "numpy_before", "python_after"}
    )
    assert json.loads((model.output / "failure.json").read_text())["rng_restore_attempted"] is False
    with pytest.raises(model.api.CommonStartRejected, match="irreversible"):
        model.api.initialize(
            model.program, model.state, role="cells", output=tmp_path / "again", enabled=True
        )


def test_common_rng_secondary_failure_writer_does_not_mask_original_seed_error(
    monkeypatch, tmp_path
):
    model = _model(monkeypatch, tmp_path)
    primary, secondary = ValueError("original seed failure"), OSError("failure writer")
    model.ng.failure = primary
    save = model.api._save

    def writer(attempt, name, value):
        if name == "failure.json":
            raise secondary
        return save(attempt, name, value)

    model.api._save = writer
    with pytest.raises(ValueError) as caught:
        model.api.initialize(
            model.program, model.state, role="cells", output=model.output, enabled=True
        )
    assert caught.value is primary
    assert any(error is secondary for _, error in model.api._ATTEMPT["secondary"])
    assert "python_after" in model.api._ATTEMPT["states"] and model.api._ATTEMPT["record"] is None


@pytest.mark.parametrize("drift", ("ambient", "runtime", "program", "pid", "bits"))
def test_common_rng_pair_comparison_refuses_non_common_evidence(monkeypatch, tmp_path, drift):
    model = _model(monkeypatch, tmp_path)
    cells = model.api.initialize(
        model.program, model.state, role="cells", output=model.output, enabled=True
    )
    original = copy.deepcopy(cells)
    original.update(role="original", pid=cells["pid"] + 1)
    assert model.api.compare(cells, original)["shared_start_bits_match"] is True
    if drift == "ambient":
        original["kind"] = "cells.common_initial_rng_observation@2"
    elif drift == "runtime":
        original["runtime"] = {}
    elif drift == "program":
        original["program"]["python_seed"] = 4
    elif drift == "pid":
        original["pid"] = cells["pid"]
    else:
        original["state"]["numpy_after"][1]["raw_bytes_hex"] = "00"
    with pytest.raises(ValueError):
        model.api.compare(cells, original)


def test_common_rng_foreign_source_frame_cannot_claim_completed_parameter_boundary(
    monkeypatch, tmp_path
):
    program = _program()
    module = ModuleType("validation.betse.native_seed_demo")
    module.__file__ = str(tmp_path / "native_seed_demo.py")
    Path(module.__file__).write_text("# incomplete consumer; no phase or parameters\n")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    with pytest.raises(ValueError, match="producer changed"):
        stage._boundary(program, object(), "cells", sys._getframe())
    assert stage._ATTEMPT is None


@pytest.mark.parametrize("constant", (complex(3, 0), -0.0))
def test_common_rng_source_guard_preserves_constant_type_and_signed_bits(tmp_path, constant):
    value = "3" if type(constant) is complex else "0.0"
    path = tmp_path / "metadata-source.py"
    path.write_text("def probe():\n    return " + value + "\n")
    unit = compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
    code = next(c for c in unit.co_consts if type(c) is stage.CodeType)
    function = FunctionType(code, dict(__builtins__=__builtins__))
    stage._source_code(function, path, "probe")
    function.__code__ = code.replace(co_consts=(None, constant))
    assert function.__code__.co_consts == code.co_consts
    with pytest.raises(ValueError, match="full source code/constants"):
        stage._source_code(function, path, "probe")


@pytest.mark.parametrize("drift", (None, "stage", "runner", "phase", "inputs", "source"))
def test_common_rng_real_metadata_frame_reaches_exact_original_boundary_guard(
    monkeypatch, tmp_path, drift
):
    # A private source-shaped consumer, not the real original workflow. The
    # canonical helper's consumers, registries and generator globals stay fixed.
    root = tmp_path / "metadata-image"
    folder = root / "validation/betse"
    folder.mkdir(parents=True)
    path = folder / "metadata_consumer.py"
    raw = (
        "def _attempt(state):\n    raise AssertionError('metadata recorder is not executed')\n"
        "def _workflow(state, plan, p, runner, check):\n    return check(state, sys._getframe())\n"
    )
    path.write_text(raw)
    module = ModuleType("validation.betse.metadata_consumer")
    module.__file__ = str(path)
    module.sys = sys
    exec(compile(raw, str(path), "exec", dont_inherit=True), vars(module))
    module.State = type("State", (), {})
    monkeypatch.setitem(sys.modules, module.__name__, module)
    helper = folder / "native_common_start_rng.py"
    helper.write_text("# synthetic source binding; no executable model\n")
    files = {
        "validation/betse/metadata_consumer.py": {"sha256": software.snapshot.digest(path)},
        stage.FILE: {"sha256": software.snapshot.digest(helper)},
    }
    software.snapshot.write_json(root / "SNAPSHOT.json", dict(files=files))
    inputs = tmp_path / "config"
    inputs.mkdir()
    inventory = dict(directories=[], files={})
    program = _program(
        input_identity=stage._digest(inventory),
        consumer_sources=dict(cells="b" * 64, original=software.snapshot.digest(path)),
    )
    state = module.State()
    p, runner = object(), NS()
    runner._p = p
    state.stage, state.raw, state.work = "original_runner", dict(parameters=p, runner=runner), []
    plan = dict(inputs=dict(root=str(inputs), inventory=inventory))
    fn = stage._boundary
    namespace = dict(
        fn.__globals__,
        __file__=str(helper),
        CONSUMERS={"original": (module.__name__, "_workflow", "_attempt")},
    )
    check = FunctionType(fn.__code__, namespace)
    if drift == "stage":
        state.stage = "SEED"
    elif drift == "runner":
        runner._p = object()
    elif drift == "phase":
        state.raw["seed_phase"] = object()
    elif drift == "inputs":
        program = _program(
            consumer_sources=dict(cells="b" * 64, original=software.snapshot.digest(path))
        )
    elif drift == "source":
        path.write_text(raw + "# changed after issuance\n")
    if drift is None:
        result = module._workflow(
            state, plan, p, runner, lambda s, f: check(program, s, "original", f)
        )
        assert result[0] is state and result[1] is runner and result[2] is p
        assert type(result[3]) is stage.FrameType and result[4] is module._workflow
    else:
        with pytest.raises(ValueError) as caught:
            module._workflow(state, plan, p, runner, lambda s, f: check(program, s, "original", f))
        reason = (
            "producer changed"
            if drift == "source"
            else "input inventory"
            if drift == "inputs"
            else "same-p runner"
        )
        assert reason in str(caught.value)
    assert stage._ATTEMPT is None


def test_common_rng_saved_json_roundtrip_keeps_complete_shared_start_data(monkeypatch, tmp_path):
    model = _model(monkeypatch, tmp_path)
    model.api.initialize(
        model.program, model.state, role="cells", output=model.output, enabled=True
    )
    cells = json.loads((model.output / "COMPLETED.json").read_text())
    original = copy.deepcopy(cells)
    original.update(role="original", pid=cells["pid"] + 1)
    assert model.api.compare(cells, original)["shared_start_bits_match"]
    for receipt in (cells, original):
        receipt["state"]["python_after"] = []
        receipt["state"]["python_readback"] = []
    with pytest.raises(ValueError, match="saved Python"):
        model.api.compare(cells, original)


def test_common_rng_reentrant_attempt_stops_before_next_seed_and_never_rearms(
    monkeypatch, tmp_path
):
    model = _model(monkeypatch, tmp_path)
    before = sys.getprofile()
    changed = []
    code = model.py.getstate.__func__.__code__

    def profile(frame, event, arg):
        if before is not None:
            before(frame, event, arg)
        if event == "return" and frame.f_code is code and not changed:
            changed.append(True)
            with pytest.raises(model.api.CommonStartRejected, match="irreversible"):
                model.api.initialize(
                    model.program,
                    model.state,
                    role="cells",
                    output=tmp_path / "again",
                    enabled=True,
                )

    try:
        sys.setprofile(profile)
        with pytest.raises(ValueError, match="Incomplete"):
            model.api.initialize(
                model.program, model.state, role="cells", output=model.output, enabled=True
            )
    finally:
        sys.setprofile(before)
    assert changed and model.events == [("python_get",)]
    assert model.api._ATTEMPT["record"] is None and not (model.output / "COMPLETED.json").exists()


def test_common_rng_primary_seed_unwind_survives_return_observer_refusal(monkeypatch, tmp_path):
    model = _model(monkeypatch, tmp_path)
    primary, cause, capture = (
        ValueError("source"),
        OSError("cause"),
        RuntimeError("return observer"),
    )
    primary.__cause__ = cause
    model.py.failure = primary
    before = sys.getprofile()
    code = model.py.seed.__func__.__code__

    def profile(frame, event, arg):
        if before is not None:
            before(frame, event, arg)
        if event == "return" and frame.f_code is code:
            raise capture

    try:
        sys.setprofile(profile)
        with pytest.raises(ValueError) as caught:
            model.api.initialize(
                model.program, model.state, role="cells", output=model.output, enabled=True
            )
    finally:
        sys.setprofile(before)
    assert caught.value is primary and primary.__cause__ is cause
    assert any(error is capture for _, error in model.api._ATTEMPT["secondary"])
    assert model.api._ATTEMPT["hooks_restored"]


def test_common_rng_post_link_fsync_failure_retains_visible_uncertain_marker(monkeypatch, tmp_path):
    model = _model(monkeypatch, tmp_path)
    original = model.api.os.fsync
    primary = OSError("directory fsync")

    def fsync(descriptor):
        if (model.output / "COMPLETED.json").exists():
            raise primary
        return original(descriptor)

    # Patch only the copied module's os provider; do not replace global os.
    model.api.os = NS(**dict(vars(model.api.os), fsync=fsync))
    with pytest.raises(OSError) as caught:
        model.api.initialize(
            model.program, model.state, role="cells", output=model.output, enabled=True
        )
    assert caught.value is primary and model.api._ATTEMPT["record"] is None
    row = next(row for row in model.api._ATTEMPT["writes"] if row["name"] == "COMPLETED.json")
    assert row["visible"] and row["durability"] == "unconfirmed"
    assert (model.output / "COMPLETED.json").is_file()
    assert model.api._ATTEMPT["primary"] is primary
