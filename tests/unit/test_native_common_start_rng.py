"""Blocked synthetic RNG-program controls, never a replacement RNG or parent.

Positive providers exist only in private copied module namespaces. No actual
seed, draw, generator construction, getstate or native body is called here.
"""

import ast
import contextlib
import copy
import json
import os
import random
import struct
import subprocess
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


@pytest.mark.parametrize(
    "drift", (None, "state_type", "owner", "parameters", "phase", "order", "inputs")
)
def test_common_rng_cells_execution_declaration_reaches_real_boundary_shape(
    monkeypatch, tmp_path, drift
):
    # Copy the actual current Cells dataclass declaration only. The wrapper,
    # WorldReady authority and caller file are explicitly private metadata
    # models; no real driver, world owner, or parameter constructor executes.
    actual_path = Path(stage.__file__).with_name("native_seed_demo.py")
    original = actual_path.read_text()
    declaration = next(
        node
        for node in ast.parse(original).body
        if isinstance(node, ast.ClassDef) and node.name == "Execution"
    )
    lines = original.splitlines(keepends=True)
    first = min([declaration.lineno] + [node.lineno for node in declaration.decorator_list])
    class_source = "".join(lines[first - 1 : declaration.end_lineno])
    root = tmp_path / "cells-metadata-image"
    folder = root / "validation/betse"
    folder.mkdir(parents=True)
    path = folder / "metadata_cells_consumer.py"
    raw = (
        "from dataclasses import dataclass, field\n" + class_source + "\n"
        "def _call(state, program, check):\n return check(program, state, sys._getframe())\n"
        "def _execute(state, plan, program, check):\n return _call(state, program, check)\n"
    )
    path.write_text(raw)
    module = ModuleType("validation.betse.metadata_cells_consumer")
    module.__file__, module.sys = str(path), sys
    monkeypatch.setitem(sys.modules, module.__name__, module)
    exec(compile(raw, str(path), "exec", dont_inherit=True), vars(module))
    assert "State" not in vars(module)
    copied = next(n for n in ast.parse(raw).body if isinstance(n, ast.ClassDef))
    assert ast.dump(copied) == ast.dump(declaration)
    state = module.Execution(flux_operator="original")
    p = object()

    class SyntheticWorldReady:
        def __init__(self, actual):
            self.parameters = actual

    owner = SyntheticWorldReady(p)
    # No canonical owner class/registry or module is changed. Only this copied
    # boundary's sys lookup sees a declared synthetic provider.
    world = ModuleType("metadata_world_ready_provider")
    world.WorldReadyParametersOwner = SyntheticWorldReady
    state.world_ready, state.parameters, state.callback = owner, p, object()
    state.operations = [
        dict(name="parameters", status="returned"),
        dict(name="common_start_rng", status="attempted"),
    ]
    inputs, packet = tmp_path / "input-files", tmp_path / "parameter-packet"
    inputs.mkdir()
    packet.mkdir()
    state.input_root = inputs
    inventory = dict(directories=[], files={})
    software.snapshot.write_json(
        packet / "inputs.json",
        dict(program=dict(root=str(inputs), input_profile="original", directories=[])),
    )
    plan = dict(
        parameter_packet=str(packet),
        parameter_sha256=software.snapshot.digest(packet / "inputs.json"),
        flux_operator="original",
        initial_rng_inputs=dict(
            profile="original", inventory=inventory, inventory_sha256=stage._digest(inventory)
        ),
    )
    helper = folder / "native_common_start_rng.py"
    helper.write_text("# metadata source witness, never executable model authority\n")
    software.snapshot.write_json(
        root / "SNAPSHOT.json",
        dict(
            files={
                "validation/betse/metadata_cells_consumer.py": {
                    "sha256": software.snapshot.digest(path)
                },
                stage.FILE: {"sha256": software.snapshot.digest(helper)},
            }
        ),
    )
    program = _program(
        input_identity=stage._digest(inventory),
        consumer_sources=dict(cells=software.snapshot.digest(path), original="c" * 64),
    )
    proxy = NS(
        **dict(
            vars(sys),
            modules=dict(
                sys.modules, **{"cells.processes.betse_native_parameter_load_remainder": world}
            ),
        )
    )
    boundary = FunctionType(
        stage._boundary.__code__,
        dict(
            stage._boundary.__globals__,
            __file__=str(helper),
            sys=proxy,
            CONSUMERS={"cells": (module.__name__, "_execute", "_call")},
        ),
    )
    if drift == "state_type":
        state = type("State", (), {})()
    elif drift == "owner":
        state.world_ready = NS(parameters=p)
    elif drift == "parameters":
        state.parameters = object()
    elif drift == "phase":
        state.phase = object()
    elif drift == "order":
        state.operations.reverse()
    elif drift == "inputs":
        program = _program(
            consumer_sources=dict(cells=software.snapshot.digest(path), original="c" * 64)
        )

    def check(program, actual, frame):
        return boundary(program, actual, "cells", frame)

    if drift is None:
        result = module._execute(state, plan, program, check)
        assert result[0] is state and result[1] is owner and result[2] is p
        assert result[4] is module._execute
    else:
        with pytest.raises(ValueError):
            module._execute(state, plan, program, check)
    software.snapshot.write_json(
        tmp_path / "Cells-Execution-boundary.json",
        dict(
            actual_declaration_source=software.snapshot.digest(actual_path),
            private_consumer_type="Execution",
            fabricated_State_alias=False,
            actual_class_AST_preserved=True,
            drift=drift,
            actual_world_parameter_or_driver_calls=0,
            native_RNG_work=0,
        ),
    )
    assert stage._ATTEMPT is None


@pytest.mark.parametrize("observer", ("profile", "trace"))
@pytest.mark.parametrize("point", ("enter_call", "enter_return", "exit_call"))
@pytest.mark.parametrize("source_failure", (False, True))
def test_common_rng_scope_caller_cleanup_preserves_falsey_primary_before_reporters(
    observer, point, source_failure, monkeypatch, tmp_path
):
    model = _model(monkeypatch, tmp_path)
    before, traces, refused, reports = (sys.getprofile(), sys.gettrace()), {}, [], []
    truthiness_calls = []

    class FalseySource(ValueError):
        def __bool__(self):
            truthiness_calls.append(self)
            return False

    primary, cause, capture = (
        FalseySource("original source"),
        OSError("source cause"),
        RuntimeError("scope hook"),
    )
    primary.__cause__ = cause
    if source_failure:
        model.py.failure = primary
    enter = contextlib._GeneratorContextManager.__enter__.__code__
    exit_ = contextlib._GeneratorContextManager.__exit__.__code__
    original_save = model.api._save
    inherited = None

    def save(attempt, name, value):
        if name in ("failure.json", "COMPLETED.json"):
            reports.append(name)
            assert attempt["observer_cleanup_complete"]
            assert attempt["observer_generator"].gi_frame is None
            assert sys.getprofile() is inherited[0] and sys.gettrace() is inherited[1]
        return original_save(attempt, name, value)

    model.api._save = save

    def observe(frame, event, arg):
        attempt = model.api._ATTEMPT
        if attempt is None or refused:
            return
        manager = attempt.get("observer_manager")
        match = frame.f_locals.get("self") is manager and manager is not None
        expected = enter if point.startswith("enter_") else exit_
        event_ = "return" if point == "enter_return" else "call"
        if match and frame.f_code is expected and event == event_:
            refused.append((frame, event, arg))
            raise capture

    def profile(frame, event, arg):
        if before[0] is not None:
            before[0](frame, event, arg)
        observe(frame, event, arg)

    def trace(frame, event, arg):
        fn = before[1] if event == "call" else traces.get(id(frame))
        result = None if fn is None else fn(frame, event, arg)
        if event == "return":
            traces.pop(id(frame), None)
        elif result is not None:
            traces[id(frame)] = result
        observe(frame, event, arg)
        return trace

    try:
        if observer == "profile":
            sys.setprofile(profile)
        else:
            sys.settrace(trace)
        inherited = sys.getprofile(), sys.gettrace()
        with pytest.raises(BaseException) as caught:
            model.api.initialize(
                model.program, model.state, role="cells", output=model.output, enabled=True
            )
        assert sys.getprofile() is inherited[0] and sys.gettrace() is inherited[1]
    finally:
        sys.settrace(before[1])
        sys.setprofile(before[0])
    attempt = model.api._ATTEMPT
    expected = primary if source_failure and point == "exit_call" else capture
    software.snapshot.write_json(
        tmp_path / "caller-cleanup.json",
        dict(
            observer=observer,
            point=point,
            source_failure=source_failure,
            refused_events=len(refused),
            exact_primary=caught.value is expected,
            exact_cause=primary.__cause__ is cause,
            closed=attempt["observer_closed"],
            hooks_restored=attempt["hooks_restored"],
            cleanup_complete=attempt["observer_cleanup_complete"],
            operations=[r["label"] for r in attempt["operations"]],
            reports=reports,
            actual_native_RNG_calls=0,
        ),
    )
    assert len(refused) == 1 and caught.value is expected
    assert not truthiness_calls
    assert attempt["primary"] is expected and primary.__cause__ is cause
    assert attempt["observer_generator"].gi_frame is None
    assert attempt["observer_cleanup_complete"] and attempt["hooks_restored"]
    assert attempt["record"] is None and not (model.output / "COMPLETED.json").exists()
    assert reports == ["failure.json"]
    if point.startswith("enter_"):
        assert not model.events and not attempt["operations"]
    elif source_failure:
        assert model.events == [("python_get",), ("numpy_get",), ("python_seed", 2437, 2)]
        assert any(error is capture for _, error in attempt["secondary"])


def test_common_rng_unresolved_outer_recovery_holds_all_reporters_and_keeps_raw_primary(
    monkeypatch, tmp_path
):
    model = _model(monkeypatch, tmp_path)
    before = sys.getprofile(), sys.gettrace()
    primary, cause = ValueError("source before failed recovery"), OSError("cause")
    primary.__cause__ = cause
    model.py.failure = primary
    reports, original_save = [], model.api._save

    def save(attempt, name, value):
        if name in ("failure.json", "COMPLETED.json"):
            reports.append(name)
            raise AssertionError("Unsafe reporters must remain held")
        return original_save(attempt, name, value)

    def set_profile(value):
        if value is before[0]:
            raise OSError("profile restore refused")
        return sys.setprofile(value)

    def set_trace(value):
        if value is before[1]:
            raise OSError("trace restore refused")
        return sys.settrace(value)

    model.api.sys = NS(**dict(vars(sys), setprofile=set_profile, settrace=set_trace))
    model.api._save = save
    try:
        with pytest.raises(ValueError) as caught:
            model.api.initialize(
                model.program, model.state, role="cells", output=model.output, enabled=True
            )
    finally:
        sys.settrace(before[1])
        sys.setprofile(before[0])
    attempt = model.api._ATTEMPT
    assert caught.value is primary and primary.__cause__ is cause
    assert not attempt["observer_cleanup_complete"] and not attempt["hooks_restored"]
    assert attempt["reporting_held"] and not reports
    assert attempt["primary"] is primary and attempt["record"] is None
    assert not hasattr(primary, "common_start_attempt")


@pytest.mark.parametrize("kind", ("profile", "trace"))
def test_common_rng_recovered_outer_setter_failure_still_refuses_publication(
    kind, monkeypatch, tmp_path
):
    model = _model(monkeypatch, tmp_path)
    before, refused = (sys.getprofile(), sys.gettrace()), []
    primary = OSError("outer " + kind + " transient recovery refusal")
    original_setter = sys.setprofile if kind == "profile" else sys.settrace

    def setter(value):
        attempt = model.api._ATTEMPT
        if attempt is not None and attempt.get("outer_cleanup_started") and not refused:
            refused.append(value)
            raise primary
        return original_setter(value)

    model.api.sys = NS(**dict(vars(sys), **{"set" + kind: setter}))
    try:
        with pytest.raises(OSError) as caught:
            model.api.initialize(
                model.program, model.state, role="cells", output=model.output, enabled=True
            )
        assert sys.getprofile() is before[0] and sys.gettrace() is before[1]
    finally:
        sys.settrace(before[1])
        sys.setprofile(before[0])
    attempt = model.api._ATTEMPT
    assert caught.value is primary and refused
    assert attempt["observer_cleanup_complete"] and attempt["hooks_restored"]
    assert attempt["record"] is None and not (model.output / "COMPLETED.json").exists()
    assert any(error is primary for _, error in attempt["observer_cleanup_errors"])


@pytest.mark.parametrize("hook", ("profile", "trace"))
def test_common_rng_program_write_primary_precedes_transient_outer_cleanup_error(
    hook, monkeypatch, tmp_path
):
    model = _model(monkeypatch, tmp_path)
    before, calls = (sys.getprofile(), sys.gettrace()), []

    class FalseyError(OSError):
        def __bool__(self):
            return False

    primary, cause, recovery = (
        FalseyError("program evidence failure"),
        ValueError("I/O cause"),
        RuntimeError("cleanup"),
    )
    primary.__cause__ = cause
    original_save = model.api._save
    original_setter = sys.setprofile if hook == "profile" else sys.settrace

    def save(attempt, name, value):
        if name == "program.json":
            raise primary
        return original_save(attempt, name, value)

    def setter(value):
        if model.api._ATTEMPT.get("outer_cleanup_started") and not calls:
            calls.append(value)
            raise recovery
        return original_setter(value)

    model.api._save = save
    model.api.sys = NS(**dict(vars(sys), **{"set" + hook: setter}))
    try:
        with pytest.raises(FalseyError) as caught:
            model.api.initialize(
                model.program, model.state, role="cells", output=model.output, enabled=True
            )
        assert sys.getprofile() is before[0] and sys.gettrace() is before[1]
    finally:
        sys.settrace(before[1])
        sys.setprofile(before[0])
    attempt = model.api._ATTEMPT
    assert caught.value is primary and primary.__cause__ is cause
    assert attempt["outer_body_primary"][0] is primary
    assert any(error is recovery for _, error in attempt["observer_cleanup_errors"])
    assert attempt["observer_cleanup_complete"] and not attempt["record"]
    assert not model.events and attempt["observer_generator"] is None


@pytest.mark.parametrize("change", ("clear_trace", "replace_trace"))
def test_common_rng_final_getprofile_mutation_cannot_certify_stale_trace_sample(
    change, monkeypatch, tmp_path
):
    model = _model(monkeypatch, tmp_path)
    before, changed, reports, local_traces = (sys.getprofile(), sys.gettrace()), [], [], {}
    original_save = model.api._save

    def other(frame, event, arg):
        return other

    def baseline(frame, event, arg):
        fn = before[1] if event == "call" else local_traces.get(id(frame))
        result = None if fn is None else fn(frame, event, arg)
        if event == "return":
            local_traces.pop(id(frame), None)
        elif result is not None:
            local_traces[id(frame)] = result
        return baseline

    def save(attempt, name, value):
        if name in ("failure.json", "COMPLETED.json"):
            reports.append(name)
        return original_save(attempt, name, value)

    def profile(frame, event, arg):
        if before[0] is not None:
            before[0](frame, event, arg)
        if event == "c_return" and arg is sys.getprofile and model.api._SAMPLING and not changed:
            changed.append(True)
            sys.settrace(None if change == "clear_trace" else other)

    model.api._save = save
    try:
        sys.settrace(baseline)
        sys.setprofile(profile)
        with pytest.raises(ValueError, match="cleanup unresolved"):
            model.api.initialize(
                model.program, model.state, role="cells", output=model.output, enabled=True
            )
    finally:
        sys.settrace(before[1])
        sys.setprofile(before[0])
    attempt = model.api._ATTEMPT
    assert changed and attempt["outer_hook_sample"]["changed"]
    assert not attempt["hooks_restored"] and not attempt["observer_cleanup_complete"]
    assert attempt["reporting_held"] and not reports and attempt["record"] is None
    assert not (model.output / "COMPLETED.json").exists()


_AUDIT_SUBPROCESS = r"""
import json
import os
import sys
from validation.betse import native_common_start_rng as stage

mode = sys.argv[1]
prior = sys.getprofile(), sys.gettrace()
attempted, vetoed, downstream = [], [], []

def guard(frame, event, arg):
    module = frame.f_globals.get("__name__", "")
    owner = getattr(arg, "__self__", None) if event == "c_call" else None
    c_module = getattr(arg, "__module__", "") or ""
    owner_module = type(owner).__module__
    if (event == "call" and (
        module.startswith("betse.") or module == "random"
        and frame.f_code.co_name in ("seed", "getstate", "setstate", "__init__")
    )) or (event == "c_call" and (
        c_module.startswith(("numpy.random", "_random"))
        or owner_module.startswith(("numpy.random", "_random"))
    )):
        attempted.append((module, event, frame.f_code.co_name))
        raise AssertionError("Actual native/RNG entry forbidden")

def veto(event, args):
    if event == "sys.addaudithook":
        vetoed.append(True)
        raise RuntimeError("Deliberate CPython silent installation veto")

def forbidden(*args, **kwargs):
    downstream.append(True)
    raise AssertionError("No downstream source or reporter after failed acknowledgement")

sys.setprofile(guard)
try:
    if mode == "normal":
        stage._install_sampling_audit()
        assert stage._AUDIT_READY and stage._AUDIT_PROBE is None
        stage._install_sampling_audit()
        assert stage._AUDIT_READY and stage._AUDIT_PROBE is None
        sample = dict(changed=False, last_mutation=None)
        stage._SAMPLING.append(sample)
        try:
            sys.settrace(prior[1])
        finally:
            stage._SAMPLING.remove(sample)
        assert sample["changed"] and stage._ATTEMPT is None
        result = dict(mode=mode, acknowledged=True, repeat_acknowledged=True,
                      sampling_mutation_observed=True)
    else:
        if mode == "veto":
            sys.addaudithook(veto)
        elif mode == "stale_ready":
            stage._AUDIT_READY = True
        else:
            raise AssertionError("Unknown metadata control")
        stage.program_document = stage._boundary = stage._runtime = stage._save = forbidden
        stage._execute_program = forbidden
        os.environ[stage.RELEASE] = "1"
        try:
            stage.initialize(object(), object(), role="cells", output=object(), enabled=True)
        except ValueError as primary:
            assert str(primary) == "Sampling audit hook acknowledgement missing"
            state = stage._ATTEMPT
            assert state["primary"] is state["pending_primary"] is primary
            assert state["outer_body_primary"][0] is primary
            assert state["stage"] == "declaration"
            assert not state["sampling_audit_acknowledged"]
            assert not stage._AUDIT_READY and stage._AUDIT_PROBE is None
            assert not state["hooks_restored"] and not state["observer_cleanup_complete"]
            assert state["reporting_held"] and state["record"] is None
            assert not state["operations"] and state["output"] is None
            assert not downstream
            assert bool(vetoed) is (mode == "veto")
            result = dict(mode=mode, acknowledged=False, exact_primary_retained=True,
                          actual_delegates=0, reporters_held=True, operations=0,
                          intended_stage=state["stage"], intended_reason=str(primary),
                          veto_events=len(vetoed))
        else:
            raise AssertionError("An unacknowledged audit hook was accepted")
    assert sys.getprofile() is guard and sys.gettrace() is prior[1]
finally:
    sys.settrace(prior[1])
    sys.setprofile(prior[0])
assert not attempted
result.update(attempted=attempted, hooks_restored=True, actual_RNG_native_calls=0)
from validation.betse import betse_normal_channel_join_runtime as runtime
result.update(pid=os.getpid(), parent_pid=os.getppid(), runtime=runtime.inventory())
print(json.dumps(result))
"""


@pytest.mark.parametrize("mode", ("normal", "veto", "stale_ready"))
def test_common_rng_sampling_audit_requires_real_callback_acknowledgement(tmp_path, mode):
    # Audit hooks are irreversible: both the deliberately vetoing hook and
    # the successful callback live only in this short isolated interpreter.
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("CELLS_") and key != "PYTEST_CURRENT_TEST"
    }
    result = subprocess.run(
        [sys.executable, "-B", "-c", _AUDIT_SUBPROCESS, mode],
        cwd=Path(stage.__file__).resolve().parents[2],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    software.snapshot.write_json(
        tmp_path / "isolated-audit-ack.json",
        dict(
            mode=mode,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            timeout_seconds=30,
            irreversible_hooks_isolated=True,
            actual_RNG_or_native_work_requested=False,
        ),
    )
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["mode"] == mode and not receipt["attempted"]
    assert receipt["hooks_restored"] and receipt["actual_RNG_native_calls"] == 0
    assert receipt["acknowledged"] is (mode == "normal")
