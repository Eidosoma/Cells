"""Synthetic typed buffers/API seam controls, never an issued native owner."""

import ast
import hashlib
import json
import os
import struct
import sys
from contextlib import contextmanager
from pathlib import Path
from types import CodeType, FunctionType, ModuleType
from types import SimpleNamespace as NS

import pytest

from tests.unit import test_native_sim_reference_compare as old
from validation.betse import native_sim_result_observation as stage
from validation.betse import native_sim_result_observation_software as software


@pytest.fixture(autouse=True)
def blocked(tmp_path):
    if os.environ.get(software.RELEASE) != "1":
        pytest.skip("Explicit immutable native-blocked observation software required")
    with software.blocked(tmp_path):
        yield
    assert not stage._ACTIVE


class Buffer:
    """Inert stdlib bytes, not a NumPy array or live source object."""

    def __init__(self, raw, dtype, shape):
        self.raw, self.dtype, self.shape = raw, NS(str=dtype), shape

    def tobytes(self, order="C"):
        assert order == "C"
        return self.raw


def _array(values, *, dtype="<f8", shape=None, strides=None):
    fmt = {"<f8": "<d", ">f8": ">d", "<u4": "<I"}[dtype]
    raw = b"".join(struct.pack(fmt, v) for v in values)
    shape = [len(values)] if shape is None else shape
    return NS(
        array=True,
        raw=raw,
        dtype=dtype,
        shape=shape,
        strides=[int(dtype[2:])] if strides is None else strides,
    )


def _cache(value, *, finite=True):
    columns = []

    def visit(item):
        if type(item) is NS and getattr(item, "array", False):
            name = f"c{len(columns)}"
            columns.append(NS(name=name, values=Buffer(item.raw, item.dtype, item.shape)))
            return dict(
                kind="numeric_array",
                source_layout=dict(
                    dtype=item.dtype,
                    shape=item.shape,
                    strides_bytes=item.strides,
                    C_contiguous=item.strides == [int(item.dtype[2:])],
                    F_contiguous=item.strides == [int(item.dtype[2:])],
                ),
                column=name,
                sha256=hashlib.sha256(item.raw).hexdigest(),
            )
        if type(item) is dict:
            return dict(kind="dict", items=[[visit(k), visit(v)] for k, v in item.items()])
        if type(item) in (list, tuple, set):
            return dict(kind=type(item).__name__, items=[visit(v) for v in item])
        if type(item) is float:
            return dict(kind="float", bits=struct.pack("<d", item).hex())
        assert item is None or type(item) in (str, bool, int)
        return dict(kind=type(item).__name__, value=item)

    raw = json.dumps(visit(value), sort_keys=True, separators=(",", ":"))
    return NS(
        descriptor_json=raw,
        identity=hashlib.sha256(raw.encode()).hexdigest(),
        columns=tuple(columns),
        all_finite=finite,
    )


def _metadata_method(name, module):
    code = compile(
        f"def {name}(self, phase=None, t=None):\n"
        '    raise AssertionError("metadata body forbidden")\n',
        "tests.synthetic_event_metadata",
        "exec",
        dont_inherit=True,
    )
    return FunctionType(
        next(v for v in code.co_consts if type(v) is CodeType), {"__name__": module}
    )


def _model(count=2, *, molecules=False, nonfinite=False, wrapped=False):
    # This private API-shaped model is never placed in a production registry.
    # Public producer gates remain None; software records grant no owner credit.
    class MetadataOwner:
        pass

    class ChannelCore:
        pass

    class Handler:
        pass

    class Simulator:
        pass

    owner = MetadataOwner()
    old_p, current_p, cells, callback, gap = (NS() for _ in range(5))
    handler = Handler()
    current_p.sim_tsteps = count
    sim = Simulator()
    sim.dyna = handler
    phase = NS(p=current_p, sim=sim, cells=cells, dyna=handler, callbacks=callback)
    master, core, channel, channel_core = NS(), NS(), NS(), ChannelCore()
    objects = (
        ("old_parameters", old_p),
        ("SIM_parameters", current_p),
        ("simulator", sim),
        ("SIM_phase", phase),
        ("cells", cells),
        ("handler", handler),
        ("gap", gap),
        ("molecules", master),
        ("network_core", core),
        ("channel", channel),
        ("channel_core", channel_core),
    )

    def ref(obj):
        return dict(owned_reference=next(i for i, (_, v) in enumerate(objects) if v is obj))

    times = [i * 0.125 for i in range(count)]
    calendar, sampled = _cache(_array(times)), _cache(set(times[::2]))
    rng = (
        _cache(("MT19937", _array(range(624), dtype="<u4"), 624, 0, -0.0)),
        _cache((3, tuple(range(624)) + (624,), None)),
    )
    raw_returns = []
    functions = {
        name: _metadata_method(name, "betse.science.tissue.tishandler")
        for name in (*stage.EVENT_METHODS, "makeAllChanges")
    }
    for name, fn in functions.items():
        exported = fn
        if wrapped:
            code = compile(
                "def wrapper(*args, __beartype_func=None, **kwargs):\n"
                "    return __beartype_func(*args, **kwargs)\n",
                "tests.synthetic_wrapper_metadata",
                "exec",
                dont_inherit=True,
            )
            exported = FunctionType(
                next(v for v in code.co_consts if type(v) is CodeType), fn.__globals__
            )
            exported.__kwdefaults__ = {"__beartype_func": fn}
            exported.__wrapped__ = fn
        setattr(Handler, name, exported)
    loop_fn = _metadata_method("_run_sim_core_loop", "betse.science.sim")
    Simulator._run_sim_core_loop = loop_fn
    loop = NS(
        f_code=loop_fn.__code__,
        f_globals=loop_fn.__globals__,
        f_back=None,
        f_locals=dict(self=sim, phase=phase),
    )
    work = [(loop, loop.f_code, loop.f_globals)]
    rows = []
    for i, time in enumerate(times):
        buffers = {
            name: _array([float("nan") if nonfinite and name == "vm" else i + 0.25, -0.0])
            for name in stage.comparison.codec.FIELDS
        }
        buffers.update(gjopen=_array([i + 0.1]), gj_funk=ref(gap), molecules=ref(master))
        values = {
            id(old_p): {},
            id(current_p): dict(
                molecules_enabled=molecules,
                grn_enabled=False,
                global_options={},
                scheduled_options={},
            ),
            id(sim): buffers,
            id(phase): dict(p=ref(current_p), sim=ref(sim), cells=ref(cells)),
            id(cells): {},
            id(handler): dict(event_cut=None, _event_voltage=None),
            id(gap): dict(
                alpha=_array([i + 0.2]), beta=_array([i + 0.3]), gjopen=_array([i + 0.4])
            ),
            id(master): dict(core=ref(core)),
            id(core): dict(channels={"channelA": ref(channel)}),
            id(channel): dict(channel_core=ref(channel_core)),
            id(channel_core): dict(alpha=_array([i + 0.75])),
        }
        cache = _cache(
            (
                tuple((role, values[id(obj)]) for role, obj in objects),
                ("actual_runtime_calendar", _array(times), set(times[::2]), 0.125),
            ),
            finite=not nonfinite,
        )
        frames = []
        for name in ("fire_events", "_fire_events_global", "_fire_events_tissue", "makeAllChanges"):
            frames.append(
                NS(
                    f_code=functions[name].__code__,
                    f_globals=functions[name].__globals__,
                    f_back=None,
                    f_locals=dict(self=handler, phase=phase, t=time),
                )
            )
        wrappers = []
        for index, frame in enumerate(frames):
            parent = loop if index == 0 else frames[0]
            if wrapped:
                exported = vars(Handler)[frame.f_code.co_name]
                wrapper = NS(
                    f_code=exported.__code__,
                    f_globals=exported.__globals__,
                    f_back=parent,
                    f_locals=dict(__beartype_func=functions[frame.f_code.co_name]),
                )
                frame.f_back = wrapper
                wrappers.append(wrapper)
                work.append((wrapper, wrapper.f_code, wrapper.f_globals))
            else:
                frame.f_back = parent
            work.append((frame, frame.f_code, frame.f_globals))
        for index in (1, 2, 3, 0):
            raw_returns.append((frames[index], "return", None))
            if wrapped:
                raw_returns.append((wrappers[index], "return", None))
        rows.append(
            NS(
                ordinal=i,
                source_time=time,
                sampled=time in times[::2],
                after=cache,
                rng=rng,
                event_calls=tuple(
                    (role, frame, time)
                    for role, frame in zip(stage.EVENT_ROLES, frames, strict=True)
                ),
                callback_calls=(),
                work_end=i + 1,
            )
        )
    before = _cache(dict(stage="before_SIM"))
    raw_returns.append((loop, "return", None))
    trial = NS(
        identity="trial-complete",
        assembly_identity="constructor",
        init_identity="INIT",
        report_returned=True,
        loop_returned=True,
        context_returned=True,
        before_native_pickle=True,
        iterations=tuple(rows),
        calendar=calendar,
        sampled=sampled,
        dt=0.125,
        operator_mode="original_value_and_flux",
        raw_returns=tuple(raw_returns),
        exceptions=(),
        work=tuple(work),
        before=before,
        ready=(before, None, rng),
        after=(rows[-1].after, None, rng),
        rng_before=rng,
        rng_after=rng,
    )
    view = dict(
        owner=owner,
        trial=trial,
        phase=phase,
        sim=sim,
        cells=cells,
        old_p=old_p,
        current_p=current_p,
        handler=handler,
        callback=callback,
        constructor=NS(identity="constructor"),
        completed_INIT=NS(identity="INIT"),
        iterations=trial.iterations,
        before=trial.before,
        after=trial.after,
        calendar=calendar,
        sampled=sampled,
        dt=0.125,
        operator_mode="original_value_and_flux",
        before_native_pickle=True,
        native_pickle_or_checkpoint_or_physical_admission=False,
        observation_objects=objects,
        observation_field_objects=objects,
    )
    calls = []

    def validate(actual):
        assert actual is owner
        calls.append("validate")
        return trial

    def completed(actual):
        assert actual is owner
        calls.append("completed")
        return view

    api = NS(SimRunOwner=MetadataOwner, validate_sim=validate, completed_sim=completed)
    return NS(owner=owner, api=api, view=view, trial=trial, calls=calls)


def _capture(tmp_path):
    rows = []

    def save(label, wire):
        pin = stage.evidence.write(tmp_path / f"capture-{len(rows):04d}.json", wire, label=label)[0]
        rows.append((label, pin, wire))
        return pin

    return save, rows


def _observe(tmp_path, model):
    capture, rows = _capture(tmp_path)
    result = stage._observe(model.owner, model.api, capture, lambda: None)
    old._save(tmp_path / "synthetic-observation.json", result)
    return result, rows


def _history_model(model, *, close_error=None, record_error=None):
    """Inert protocol fixture, never a Key token or an issued model owner."""
    state = NS(
        active=False,
        entries=0,
        exits=0,
        checks=[],
        callbacks=[],
        selected=0,
        checked=set(),
        record=None,
    )

    class Record(NS):
        pass

    class Rejected(ValueError):
        pass

    class Interval:
        def validate_sim(self, *, row=None, caches=()):
            assert state.active
            if row is not None:
                assert model.trial.iterations[row.ordinal] is row
                state.checked.add(row.ordinal)
            state.selected += (3 if row is not None else 0) + len(caches)
            state.checks.append((row, caches))
            return model.trial

        def completed_sim(self):
            self.validate_sim()
            return dict(model.view)

        def call(self, callback, *args, row=None, caches=(), **kwargs):
            self.validate_sim(row=row, caches=caches)
            raw = dict(
                callback=callback, args=args, row=row, caches=caches, result=None, error=None
            )
            state.callbacks.append(raw)
            try:
                raw["result"] = callback(*args, **kwargs)
            except BaseException as error:
                raw["error"] = error
                raise
            self.validate_sim(row=row, caches=caches)
            return raw["result"]

        @property
        def record(self):
            assert not state.active
            if record_error is not None:
                raise record_error
            return state.record

    @contextmanager
    def observing(owner, *, enabled=False):
        assert owner is model.owner and enabled is True and not state.active
        state.entries += 1
        model.api.completed_sim(owner)
        state.active = True
        primary = None
        try:
            yield Interval()
        except BaseException as error:
            primary = error
        finally:
            state.exits += 1
            state.active = False
            model.api.validate_sim(owner)
        if primary is None:
            primary = close_error
        state.record = Record(
            law="actual_completed_SIM_read_only_complete_history_interval@1",
            status=("completed_observation" if primary is None else "failed_observation"),
            trial_identity=model.trial.identity,
            configured_rows=len(model.trial.iterations),
            checked_rows=tuple(sorted(state.checked)),
            work=(),
            full_authority_attempts=2,
            full_authority_returns=2,
            retained_payload_attempts=state.selected,
            retained_payload_returns=state.selected,
            source_metadata_operations=len(state.checks),
            source_retained_cache_attempts=2 * (9 + 3 * len(model.trial.iterations)),
            source_retained_cache_returns=2 * (9 + 3 * len(model.trial.iterations)),
            callback_calls=tuple(
                (i, "returned" if r["error"] is None else "failed")
                for i, r in enumerate(state.callbacks)
            ),
            native_or_scientific_credit=0,
        )
        if primary is not None:
            raise Rejected("retained synthetic interval failure") from primary

    api = NS(
        CompletedHistoryObservation=Interval,
        ObservationRecord=Record,
        HistoryObservationRejected=Rejected,
        observing_completed=observing,
        LAW_ID="actual_completed_SIM_read_only_complete_history_interval@1",
    )
    return api, state


def _history_observe(
    tmp_path, model, *, capture=None, check=None, close_error=None, record_error=None
):
    api, state = _history_model(model, close_error=close_error, record_error=record_error)
    save, rows = _capture(tmp_path)
    result = stage._observe(
        model.owner,
        model.api,
        capture or save,
        lambda: None,
        history_api=api,
        history_check=check or (lambda: None),
    )
    return result, rows, state


@pytest.mark.parametrize("count", [1, 4, 350])
def test_sim_observation_history_protocol_preserves_each_actual_row_and_two_full_sweeps(
    tmp_path, count
):
    model = _model(count=count)
    record, captures, state = _history_observe(tmp_path, model)
    assert model.calls == ["completed", "validate"] and state.entries == state.exits == 1
    assert state.checked == set(range(count)) and len(captures) == count + 5
    assert record["work"]["history_interval"]["full_authority_returns"] == 2
    assert state.selected == 12 * count + 21
    assert all(
        row["row"] is model.trial.iterations[i] for i, row in enumerate(state.callbacks[:count])
    )
    assert [row["caches"] for row in state.callbacks[count:]] == [
        (model.trial.before,),
        (model.trial.ready[0],),
        (model.trial.after[0],),
        model.trial.rng_before,
        model.trial.rng_after,
    ]
    assert record["configured_iterations"] == count and record["physical_checkpoint_credit"] == 0
    parsed = stage.comparison._read_row(
        stage.comparison.report.Reader(),
        record["iterations"][-1]["files"],
        count - 1,
        required_observation=True,
    )
    assert parsed["source_time_bits"] == struct.pack("!d", (count - 1) * 0.125).hex()


@pytest.mark.parametrize("where", ["capture", "close", "record"])
def test_sim_observation_history_failure_preserves_original_primary_and_partial_token(
    tmp_path, where
):
    model = _model()
    primary, cause = ValueError("original interval/capture failure"), OSError("original cause")
    primary.__cause__ = cause
    api, state = _history_model(
        model,
        close_error=primary if where == "close" else None,
        record_error=primary if where == "record" else None,
    )
    save, rows = _capture(tmp_path)

    def capture(label, wire):
        if where == "capture":
            raise primary
        return save(label, wire)

    with pytest.raises(stage.ObservationRejected) as caught:
        stage._observe(
            model.owner,
            model.api,
            capture,
            lambda: None,
            history_api=api,
            history_check=lambda: None,
        )
    assert caught.value.__cause__ is primary and primary.__cause__ is cause
    assert caught.value.partial.interval is not None and not state.active
    assert state.entries == state.exits == 1 and model.calls == ["completed", "validate"]
    assert len(rows) == (0 if where == "capture" else 7)


def _history_code_only_api():
    """Bind original code metadata without executing/importing model bodies."""
    filename = str(software.ROOT / stage.HISTORY_FILE)
    raw = Path(filename).read_bytes()
    module = ModuleType(stage.HISTORY_MODULE)
    module.__file__ = filename
    module.parent = object()
    tree = ast.parse(raw)
    pending, codes = [compile(raw, filename, "exec", dont_inherit=True)], {}
    while pending:
        code = pending.pop()
        codes[code.co_qualname] = code
        pending.extend(c for c in code.co_consts if type(c) is CodeType)

    def function(node, qualified):
        code = codes[qualified]
        cells = (
            tuple((lambda value: lambda: value)(None).__closure__[0] for _ in code.co_freevars)
            or None
        )
        fn = FunctionType(code, vars(module), closure=cells)
        fn.__defaults__ = tuple(ast.literal_eval(v) for v in node.args.defaults) or None
        fn.__kwdefaults__ = {
            a.arg: ast.literal_eval(v)
            for a, v in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True)
            if v is not None
        } or None
        return fn

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            fn = function(node, node.name)
            setattr(
                module, node.name, contextmanager(fn) if node.name == "observing_completed" else fn
            )
        elif isinstance(node, ast.ClassDef):
            values = {
                n.name: (
                    property(function(n, node.name + "." + n.name))
                    if any(isinstance(d, ast.Name) and d.id == "property" for d in n.decorator_list)
                    else function(n, node.name + "." + n.name)
                )
                for n in node.body
                if isinstance(n, ast.FunctionDef)
            }
            values["__module__"] = stage.HISTORY_MODULE
            cls = type(
                node.name,
                (ValueError,) if node.name == "HistoryObservationRejected" else (object,),
                values,
            )
            for value in values.values():
                fn = value.fget if type(value) is property else value
                if type(fn) is FunctionType:
                    for name, cell in zip(
                        fn.__code__.co_freevars, fn.__closure__ or (), strict=True
                    ):
                        if name == "__class__":
                            cell.cell_contents = cls
            setattr(module, node.name, cls)
    return module, raw, filename


@pytest.mark.parametrize(
    "drift",
    [None, "wrapper", "closure", "keyword", "method_code", "parent_global", "record_getter"],
)
def test_sim_observation_history_authenticates_real_wrapper_method_and_namespace_metadata(monkeypatch, drift):
    api, raw, filename = _history_code_only_api()
    # Authenticate the exact raw code fixture in this immutable image. This
    # does not fill the held public review gate or adopt a live provider.
    monkeypatch.setattr(stage, "HISTORY_SHA256", hashlib.sha256(raw).hexdigest())
    bindings = stage._history_bindings(api, raw, filename)
    if drift == "wrapper":
        api.observing_completed.__wrapped__ = lambda: None
    elif drift == "closure":
        api.observing_completed.__closure__[0].cell_contents = lambda: None
    elif drift == "keyword":
        api.observing_completed.__wrapped__.__kwdefaults__["enabled"] = 0
    elif drift == "method_code":
        api.CompletedHistoryObservation.validate_sim.__code__ = (
            api.CompletedHistoryObservation.validate_sim.__code__.replace()
        )
    elif drift == "parent_global":
        api.parent = object()
    elif drift == "record_getter":
        getter = api.CompletedHistoryObservation.record.fget
        getter.__code__ = getter.__code__.replace()
    if drift is None:
        stage._history_unchanged(api, bindings)
    else:
        with pytest.raises(ValueError):
            stage._history_unchanged(api, bindings)


def test_sim_observation_history_gate_refuses_before_source_import_or_parent_read(monkeypatch):
    imported = []
    monkeypatch.setattr(stage.importlib, "import_module", lambda name: imported.append(name))
    with pytest.raises(ValueError, match="history producer held"):
        stage._history_api(object())
    assert imported == []


def _accepted_observer():
    return stage.snapshot.digest(software.ROOT / stage.FILE)


def _saved_view(request):
    return stage.saved_view(request, accepted_observer_sha256=_accepted_observer())


def _terminal_view():
    value = old._view()
    value["input_provenance"] = stage.comparison.complete_input_provenance(
        dict(directories=[], files={"sim_config.yaml": dict(size_bytes=1, sha256="a" * 64)})
    )
    return value


@pytest.mark.parametrize(
    "native,canonical",
    [
        ("original_value_and_flux", "original"),
        ("original_value_only_flux_omitted", "disabled"),
    ],
)
def test_sim_observation_mode_surface_keeps_native_provenance(tmp_path, native, canonical):
    model = _model()
    model.trial.operator_mode = model.view["operator_mode"] = native
    record, _ = _observe(tmp_path, model)
    assert record["operator_mode"] == canonical
    assert record["source_operator_mode"] == native
    assert model.view["operator_mode"] == model.trial.operator_mode == native
    assert "source_operator_mode" not in model.view


@pytest.mark.parametrize("native", ["original", "disabled", "supplied", None])
def test_sim_observation_mode_surface_refuses_non_Key_modes_before_capture(tmp_path, native):
    model = _model()
    model.trial.operator_mode = model.view["operator_mode"] = native
    capture, rows = _capture(tmp_path)
    with pytest.raises(stage.ObservationRejected) as failure:
        stage._observe(model.owner, model.api, capture, lambda: None)
    assert rows == [] and failure.value.__cause__ is not None


def test_sim_observation_source_plan_and_public_gates_precede_foreign_input(monkeypatch):
    class Foreign:
        def __getattribute__(self, name):
            raise AssertionError("foreign owner read")

    plan = stage.source_plan()
    assert plan["public_Key"]["source_sha256"] is None and plan["public_Key"]["review"] is None
    assert (
        plan["saved_writer"]["sha256"] == stage.snapshot.digest(software.ROOT / stage.WRITER_FILE)
        and plan["scientific_physical_checkpoint_credit"] == 0
    )
    with pytest.raises(stage.ObservationRejected) as release:
        stage.observe_completed(Foreign(), capture=lambda *a: None)
    assert release.value.stage == "release"
    monkeypatch.setenv(stage.RELEASE, "1")
    with pytest.raises(stage.ObservationRejected) as source:
        stage.observe_completed(Foreign(), enabled=True, capture=lambda *a: None)
    assert source.value.stage == "producer"
    assert not any(n.startswith("cells.processes.") for n in sys.modules)
    assert stage.saved_view(Foreign())["error"]["type"] == "ProducerPrerequisiteUnavailable"


@pytest.mark.parametrize("molecules", [False, True])
def test_sim_observation_historical_rows_full_rng_and_real_tail_relationships(tmp_path, molecules):
    model = _model(molecules=molecules)
    # Live final state cannot substitute for an earlier historical snapshot.
    model.view["sim"].vm = "unrelated final metadata sentinel"
    result, captures = _observe(tmp_path, model)
    assert result["status"] == "completed_observation" and result["configured_iterations"] == 2
    assert len(captures) == 7 and len(result["iterations"]) == 2
    assert result["common_starting_authority_established"] is False
    assert (
        result["numerical_parity_available"] is False and result["physical_checkpoint_credit"] == 0
    )
    parsed = [
        stage.comparison._read_row(
            stage.comparison.report.Reader(), row["files"], i, required_observation=True
        )
        for i, row in enumerate(result["iterations"])
    ]
    assert parsed[0]["groups"]["voltage"] != parsed[1]["groups"]["voltage"]
    gates = stage.comparison.codec._mapping(parsed[0]["groups"]["gates"])
    network = stage.comparison.codec._mapping(gates["molecules"])
    assert network["enabled"] == dict(kind="bool", value=molecules)
    if molecules:
        channel = stage.comparison.codec._mapping(network["channels"]["items"][0])
        assert channel["name"]["value"] == "channelA"
    else:
        assert "channels" not in network
    assert model.calls.count("completed") == 1 and model.calls.count("validate") > 2


def test_sim_observation_nonfinite_is_retained_not_repaired_or_domain_admitted(tmp_path):
    model = _model(nonfinite=True)
    result, _ = _observe(tmp_path, model)
    assert result["domain"]["all_retained_step_caches_finite"] is False
    assert result["domain"]["physical_domain_or_conservation_admitted"] is False
    first = stage.comparison._read_row(
        stage.comparison.report.Reader(),
        result["iterations"][0]["files"],
        0,
        required_observation=True,
    )
    assert first["groups"]["voltage"]["vm"]["bytes"]["size"] == 16


@pytest.mark.parametrize("bits", ["0000000000000080", "010000000000f87f", "020000000000f87f"])
def test_sim_observation_rng_gaussian_bits_are_never_reconstructed_from_JSON(tmp_path, bits):
    model = _model()
    gaussian = struct.unpack("<d", bytes.fromhex(bits))[0]
    row = model.trial.iterations[0]
    row.rng = (_cache(("MT19937", _array(range(624), dtype="<u4"), 623, 1, gaussian)), row.rng[1])
    result, _ = _observe(tmp_path, model)
    parsed = stage.comparison._read_row(
        stage.comparison.report.Reader(),
        result["iterations"][0]["files"],
        0,
        required_observation=True,
    )
    assert parsed["groups"]["rng"]["numpy"]["items"][-1]["bits"] == bits


@pytest.mark.parametrize(
    "defect",
    [
        "owner",
        "trial",
        "old_p",
        "phase_sim",
        "phase_cells",
        "phase_p",
        "handler",
        "callback",
        "constructor",
        "INIT",
        "report",
        "loop",
        "context",
        "pickle",
        "mode",
        "calendar",
        "roster",
        "ordinal",
        "time",
        "sample",
        "count",
    ],
)
def test_sim_observation_rejects_source_surface_or_calendar_drift_before_capture(tmp_path, defect):
    model = _model()
    view = model.view
    if defect == "owner":
        view["owner"] = object()
    elif defect == "trial":
        view["trial"] = NS()
    elif defect == "old_p":
        view["old_p"] = view["current_p"]
    elif defect.startswith("phase_"):
        setattr(view["phase"], defect[6:], object())
    elif defect == "handler":
        view["sim"].dyna = object()
    elif defect == "callback":
        view["callback"] = object()
    elif defect in ("constructor", "INIT"):
        view["constructor" if defect == "constructor" else "completed_INIT"] = NS(
            identity="changed"
        )
    elif defect in ("report", "loop", "context", "pickle"):
        setattr(
            model.trial,
            dict(
                report="report_returned",
                loop="loop_returned",
                context="context_returned",
                pickle="before_native_pickle",
            )[defect],
            False,
        )
    elif defect == "mode":
        view["operator_mode"] = "supplied"
    elif defect == "calendar":
        view["calendar"] = _cache(_array([0.0]))
    elif defect == "roster":
        view["observation_field_objects"] = view["observation_field_objects"][1:]
    elif defect == "ordinal":
        model.trial.iterations[0].ordinal = 1
    elif defect == "time":
        model.trial.iterations[0].source_time = 0.0625
    elif defect == "sample":
        model.trial.iterations[0].sampled = False
    else:
        view["current_p"].sim_tsteps = 3
    capture, rows = _capture(tmp_path)
    with pytest.raises(stage.ObservationRejected) as rejected:
        stage._observe(model.owner, model.api, capture, lambda: None)
    assert rows == []
    assert rejected.value.partial.owner is model.owner
    assert rejected.value.__cause__ is rejected.value.partial.primary


@pytest.mark.parametrize(
    "defect", ["missing_return", "duplicate_return", "exception", "nesting", "time", "order"]
)
def test_sim_observation_requires_actual_event_return_and_nesting_evidence(tmp_path, defect):
    model = _model()
    row = model.trial.iterations[0]
    frame = row.event_calls[1][1]
    if defect == "missing_return":
        model.trial.raw_returns = tuple(r for r in model.trial.raw_returns if r[0] is not frame)
    elif defect == "duplicate_return":
        model.trial.raw_returns += ((frame, "return", None),)
    elif defect == "exception":
        model.trial.exceptions = ((frame, ValueError("original event error")),)
    elif defect == "nesting":
        frame.f_back = None
    elif defect == "time":
        row.event_calls = tuple((role, f, 1.0) for role, f, _ in row.event_calls)
    else:
        row.event_calls = tuple(reversed(row.event_calls))
    capture, rows = _capture(tmp_path)
    with pytest.raises(stage.ObservationRejected):
        stage._observe(model.owner, model.api, capture, lambda: None)
    assert rows == []


@pytest.mark.parametrize("where", [0, 1, 2, 4, 6])
def test_sim_observation_capture_failure_retains_actual_wire_and_previous_pins(tmp_path, where):
    model = _model()
    delegate, rows = _capture(tmp_path)
    primary = OSError("original capture")
    cause = ValueError("capture cause")

    def capture(label, wire):
        if len(rows) == where:
            raise primary from cause
        return delegate(label, wire)

    with pytest.raises(stage.ObservationRejected) as caught:
        stage._observe(model.owner, model.api, capture, lambda: None)
    context = caught.value.partial
    assert caught.value.__cause__ is primary and primary.__cause__ is cause
    assert context.primary is primary and context.raw_observation is not None
    assert context.capture_errors[0][1] is primary and len(rows) == where
    assert context.result is None
    old._save(
        tmp_path / "capture-refusal.json",
        dict(
            primary_identity=id(primary),
            cause_identity=id(cause),
            previous_pins=[pin for _, pin, _ in rows],
        ),
    )


def test_sim_observation_reentry_is_sticky_even_if_capture_catches_then_fails(tmp_path):
    model = _model()
    called = []
    capture_error = OSError("secondary capture")

    def capture(label, wire):
        with pytest.raises(stage.ObservationRejected) as nested:
            stage._observe(model.owner, model.api, lambda *a: None, lambda: None)
        called.append(nested.value)
        raise capture_error

    with pytest.raises(stage.ObservationRejected) as caught:
        stage._observe(model.owner, model.api, capture, lambda: None)
    context = caught.value.partial
    assert caught.value.__cause__ is called[0] and context.capture_errors[0][1] is capture_error
    assert context.result is None and len(called) == 1


@pytest.mark.parametrize(
    "defect", ["raw_mutation", "wrong_saved_value", "wrong_pin", "late_file_drift"]
)
def test_sim_observation_saved_callback_cannot_replace_actual_evidence(tmp_path, defect):
    model = _model()
    delegate, rows = _capture(tmp_path)

    def capture(label, wire):
        if defect == "wrong_saved_value":
            changed = dict(tree=dict(type="str", value="supplied observation"), columns={})
            return delegate(label, changed)
        pin = delegate(label, wire)
        if defect == "raw_mutation":
            wire["tree"] = dict(type="str", value="changed original metadata")
        elif defect == "wrong_pin":
            pin = dict(pin, sha256="0" * 64)
        elif defect == "late_file_drift" and len(rows) == 2:
            Path(rows[0][1]["path"]).write_text("{}")
        return pin

    with pytest.raises(stage.ObservationRejected) as caught:
        stage._observe(model.owner, model.api, capture, lambda: None)
    assert caught.value.partial.result is None
    assert caught.value.partial.raw_row is not None


@pytest.mark.parametrize("defect", [None, "code", "default", "keyword", "globals"])
def test_sim_observation_public_validation_dependencies_are_bound_before_use(tmp_path, defect):
    source = "\n".join(
        f"def {name}(*args, **kwargs):\n    calls.append({name!r})\n"
        for name in stage.KEY_VALIDATORS
    )
    code = compile(source, "tests.synthetic_sim_metadata", "exec", dont_inherit=True)
    module = ModuleType("tests.synthetic_sim_metadata")
    module.calls = []
    for item in code.co_consts:
        if type(item) is CodeType:
            vars(module)[item.co_name] = FunctionType(item, vars(module))
    target = module._authority
    if defect == "code":
        target.__code__ = (lambda *a, **k: None).__code__
    elif defect == "default":
        target.__defaults__ = ("changed",)
    elif defect == "keyword":
        target.__kwdefaults__ = dict(hidden="changed")
    elif defect == "globals":
        module._authority = FunctionType(target.__code__, dict(vars(module)))
    if defect is None:
        assert len(stage._key_functions(module, source, "tests.synthetic_sim_metadata")) == len(
            stage.KEY_VALIDATORS
        )
    else:
        with pytest.raises(ValueError):
            stage._key_functions(module, source, "tests.synthetic_sim_metadata")
    assert module.calls == []
    old._save(
        tmp_path / "public-validation-metadata.json",
        dict(defect=defect, delegate_calls=module.calls),
    )


@pytest.mark.parametrize("hook", ["profile", "trace"])
def test_sim_observation_lost_inherited_hook_is_restored_before_any_later_callback(tmp_path, hook):
    model = _model()
    delegate, rows = _capture(tmp_path)
    before = (sys.getprofile(), sys.gettrace())

    def capture(label, wire):
        pin = delegate(label, wire)
        (sys.setprofile if hook == "profile" else sys.settrace)(None)
        return pin

    with pytest.raises(stage.ObservationRejected) as rejected:
        stage._observe(model.owner, model.api, capture, lambda: None)
    assert (sys.getprofile(), sys.gettrace()) == before and len(rows) == 1
    assert rejected.value.partial.result is None


@pytest.mark.parametrize("failed", ["profile", "trace"])
def test_sim_observation_failed_restoration_attempts_both_hooks_and_keeps_primary(
    tmp_path, monkeypatch, failed
):
    model = _model()
    primary = OSError("original capture")
    cause = ValueError("cause")
    tokens = dict(profile=object(), trace=object())
    state = dict(tokens)
    restores = []

    def setter(name, value):
        restores.append(name)
        if name == failed:
            raise RuntimeError("secondary restore")
        state[name] = value

    fake = NS(
        getprofile=lambda: state["profile"],
        gettrace=lambda: state["trace"],
        setprofile=lambda value: setter("profile", value),
        settrace=lambda value: setter("trace", value),
    )
    monkeypatch.setattr(stage, "sys", fake)

    def capture(label, wire):
        state.update(profile=None, trace=None)
        raise primary from cause

    with pytest.raises(stage.ObservationRejected) as caught:
        stage._observe(model.owner, model.api, capture, lambda: None)
    assert restores == ["profile", "trace"] and caught.value.__cause__ is primary
    assert primary.__cause__ is cause and caught.value.partial.result is None
    assert any(row[0] == "hook_restore" for row in caught.value.partial.capture_errors)


@pytest.mark.parametrize("kind", ["file", "directory"])
@pytest.mark.parametrize("side", ["demo", "reference"])
def test_sim_observation_starting_final_inventory_detects_late_added_paths(
    tmp_path, monkeypatch, kind, side
):
    demo, reference = old._rng_pair_files(tmp_path)
    function = stage.comparison.compare_initial_rng_records

    def changed(*args, **kwargs):
        value = function(*args, **kwargs)
        source = demo["plan"] if side == "demo" else reference["prepared"]
        plan = json.loads(Path(source["path"]).read_text())
        if side == "demo":
            parameters = json.loads(Path(plan["parameter_inputs"]["path"]).read_text())
            root = Path(parameters["program"]["root"])
        else:
            root = Path(plan["inputs"]["root"])
        if kind == "file":
            (root / "late.dat").write_bytes(b"new unlisted bytes")
        else:
            (root / "late-directory").mkdir()
        return value

    monkeypatch.setattr(stage.comparison, "compare_initial_rng_records", changed)
    result = stage.comparison.compare_starting_rng_saved(demo, reference)
    assert result["status"] == "evidence_changed_during_starting_rng_authentication"
    assert result["observations_match"] is None and result["numerical_parity_available"] is False
    old._save(tmp_path / "late-inventory-refusal.json", result)


@pytest.mark.parametrize("allocation", ["normal", "foreign"])
def test_sim_observation_starting_reader_allocator_is_checked_before_constructor(
    monkeypatch, allocation
):
    touched = []
    reader = stage.comparison.report.Reader

    def allocator(cls):
        touched.append("allocated")
        return object.__new__(cls) if allocation == "normal" else NS()

    monkeypatch.setattr(reader, "__new__", staticmethod(allocator), raising=False)
    result = stage.comparison.compare_starting_rng_saved({}, {})
    assert touched == [] and result["status"] == "unavailable"
    assert not any(v["authenticated"] for v in result["sides"].values())


@pytest.mark.parametrize("group", stage.comparison.GROUPS)
def test_sim_observation_paired_terminal_groups_are_exact_without_common_start_claim(group):
    left, right = _terminal_view(), _terminal_view()
    left["files_bound"] = right["files_bound"] = True
    result = stage.comparison.compare_terminal_views(left, right)
    assert result["exact_observation_comparison_available"] and result["exact_observations_equal"]
    assert result["numerical_parity_available"] is False
    right["rows"][0]["groups"][group] = dict(changed_exact_observation=True)
    result = stage.comparison.compare_terminal_views(left, right)
    assert (
        result["exact_observation_comparison_available"]
        and result["exact_observations_equal"] is False
    )


@pytest.mark.parametrize(
    "defect", ["mode", "missing_group", "clock", "partial", "unknown_producer"]
)
def test_sim_observation_paired_terminal_incomplete_or_different_epochs_stay_separate(defect):
    left, right = _terminal_view(), _terminal_view()
    left["files_bound"] = right["files_bound"] = True
    if defect == "mode":
        right["mode"] = "disabled"
    elif defect == "missing_group":
        right["rows"][1]["groups"]["events"] = None
    elif defect == "clock":
        right["rows"][1]["dt_bits"] = "ff" * 8
    elif defect == "partial":
        right["rows"].pop()
        right["calendar"].pop()
        right["endpoint_complete"] = False
    else:
        right["files_bound"] = False
    result = stage.comparison.compare_terminal_views(left, right)
    assert result["exact_observation_comparison_available"] is False
    assert (
        result["exact_observations_equal"] is None and result["numerical_parity_available"] is False
    )


def _saved_binding(tmp_path, monkeypatch):
    """Synthetic file graph; never actual adoption or native execution."""
    record, _, _ = _history_observe(tmp_path, _model())
    source = tmp_path / "source"
    source.mkdir()
    files = {}
    for name in (stage.KEY_FILE, stage.FILE, stage.WRITER_FILE, stage.HISTORY_FILE):
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((software.ROOT / name).read_bytes())
        target.chmod(0o444)
        files[name] = dict(
            checkout_path=name,
            sha256=stage.snapshot.digest(target),
            observation=dict(size=target.stat().st_size),
            snapshot_mode=0o444,
        )
    (source / "checkout.patch").write_bytes(b"")
    (source / "checkout.patch").chmod(0o444)
    old._save(
        source / "SNAPSHOT.json",
        dict(
            kind="cells.checkout_source_snapshot@1",
            status="complete",
            immutable=True,
            files=files,
            patch_sha256=stage.snapshot.digest(source / "checkout.patch"),
        ),
    )
    for path in source.rglob("*"):
        path.chmod(0o555 if path.is_dir() else 0o444)
    source.chmod(0o555)
    review = old._save(
        tmp_path / "synthetic-review.json", dict(kind="synthetic_saved_graph_only", native_credit=0)
    )
    expected = files[stage.KEY_FILE]["sha256"]
    monkeypatch.setattr(stage, "KEY_SHA256", expected)
    monkeypatch.setattr(stage, "KEY_REVIEW", review)
    monkeypatch.setattr(stage, "HISTORY_SHA256", files[stage.HISTORY_FILE]["sha256"])
    monkeypatch.setattr(stage, "HISTORY_REVIEW", review)
    record["producer"].update(sha256=expected, review=review)
    record["producer"]["history"].update(sha256=files[stage.HISTORY_FILE]["sha256"], review=review)
    record_pin = old._save(tmp_path / "observation-record.json", record)
    executable = old._save(tmp_path / "executable.fixture", dict(inert=True))
    runtime = old._save(
        tmp_path / "runtime.json",
        dict(
            python="3.13.synthetic",
            executable=executable,
            loaded_files={
                name.removesuffix(".py").replace("/", ".").removeprefix("src."): dict(
                    path=str(source / name), sha256=row["sha256"]
                )
                for name, row in files.items()
            },
        ),
    )
    process = old._save(
        tmp_path / "process.json",
        dict(
            status="completed",
            returncode=0,
            elapsed_seconds=1.0,
            samples=1,
            sampled_peak_process_tree_rss_bytes=128 * 2**20,
            minimum_available_host_memory_bytes=16 * 2**30,
            limits=dict(
                max_wall_seconds=480,
                max_process_tree_rss_bytes=2**30,
                min_available_host_memory_bytes=8 * 2**30,
            ),
        ),
    )
    terminal = old._save(
        tmp_path / "terminal.json",
        dict(status="completed", observation=record_pin, trial_identity=record["trial_identity"]),
    )
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "sim_config.yaml").write_bytes(b"synthetic inert bytes\n")
    binding = old._save(
        tmp_path / "saved-binding.json",
        dict(
            kind=stage.BINDING_KIND,
            execution_source=dict(
                root=str(source),
                snapshot_sha256=stage.snapshot.digest(source / "SNAPSHOT.json"),
                owned_files={n: r["sha256"] for n, r in files.items()},
            ),
            reviews=[review],
            runtime=runtime,
            process=process,
            terminal=terminal,
            inputs=dict(
                root=str(inputs),
                inventory=stage.comparison.input_files.inventory(inputs),
                mode="original",
                profile="headless",
            ),
            original_sources="synthetic exact native source roster",
            observation_record=record_pin,
        ),
    )
    return dict(record=record_pin, binding=binding)


def test_sim_observation_saved_graph_roundtrip_is_data_not_owner_or_common_start(
    tmp_path, monkeypatch
):
    request = _saved_binding(tmp_path, monkeypatch)
    side = _saved_view(request)
    assert side["authenticated"] and side["files_bound"] and side["endpoint_complete"], side[
        "error"
    ]
    assert len(side["rows"]) == 2 and side["initial_rng"] == dict(available=False)
    paired = stage.comparison.compare_terminal_views(side, side)
    assert paired["exact_observation_comparison_available"] and paired["exact_observations_equal"]
    assert paired["common_starting_authority_established"] is False
    assert paired["numerical_parity_available"] is False
    old._save(tmp_path / "synthetic-saved-report.json", paired)


@pytest.mark.parametrize("native", ["original_value_only_flux_omitted", "original"])
def test_sim_observation_mode_saved_native_provenance_cannot_be_relabelled(
    tmp_path, monkeypatch, native
):
    request = _saved_binding(tmp_path, monkeypatch)
    record = json.loads(Path(request["record"]["path"]).read_text())
    record["source_operator_mode"] = native
    old._replace(request["record"], record)
    binding = json.loads(Path(request["binding"]["path"]).read_text())
    terminal = json.loads(Path(binding["terminal"]["path"]).read_text())
    terminal["observation"] = request["record"]
    old._replace(binding["terminal"], terminal)
    binding["observation_record"] = request["record"]
    old._replace(request["binding"], binding)
    side = _saved_view(request)
    assert not side["authenticated"] and not side["endpoint_complete"]
    assert side["error"]["message"] == "Exact completed observation record"


@pytest.mark.parametrize(
    "defect",
    [
        "record_pin",
        "snapshot",
        "review",
        "runtime",
        "source_origin",
        "process",
        "terminal",
        "terminal_trial",
        "missing_row",
        "row_order",
        "clock",
        "sampled",
        "lineage",
        "roots",
        "edge",
        "input_file",
        "input_dir",
        "input_mode",
        "capture",
        "RNG_boundary",
        "producer",
        "observer",
        "extra_binding",
    ],
)
def test_sim_observation_saved_graph_refuses_resealed_drift(tmp_path, monkeypatch, defect):
    request = _saved_binding(tmp_path, monkeypatch)
    binding = json.loads(Path(request["binding"]["path"]).read_text())
    record = json.loads(Path(request["record"]["path"]).read_text())
    if defect == "record_pin":
        request["record"]["sha256"] = "0" * 64
    elif defect == "snapshot":
        p = Path(binding["execution_source"]["root"]) / "SNAPSHOT.json"
        p.chmod(0o644)
        p.write_text("{}")
    elif defect == "review":
        Path(stage.KEY_REVIEW["path"]).write_text("{}")
    elif defect in ("runtime", "source_origin"):
        pin = binding["runtime"]
        value = json.loads(Path(pin["path"]).read_text())
        if defect == "runtime":
            value["loaded_files"].pop(stage.KEY_MODULE)
        else:
            value["loaded_files"][stage.KEY_MODULE] = value["loaded_files"][
                stage.FILE[:-3].replace("/", ".")
            ]
        old._replace(pin, value)
    elif defect == "process":
        value = json.loads(Path(binding["process"]["path"]).read_text())
        value["elapsed_seconds"] = 481
        old._replace(binding["process"], value)
    elif defect in ("terminal", "terminal_trial"):
        value = json.loads(Path(binding["terminal"]["path"]).read_text())
        value["status" if defect == "terminal" else "trial_identity"] = "failed or changed"
        old._replace(binding["terminal"], value)
    elif defect == "missing_row":
        record["iterations"].pop()
    elif defect == "row_order":
        record["iterations"].reverse()
    elif defect == "clock":
        record["dt_bits"] = "ff" * 8
    elif defect == "sampled":
        record["sampled"] = stage._cache(_cache(set()))
    elif defect == "lineage":
        record["lineage"]["facts"]["sim_retained"] = False
    elif defect == "roots":
        record["lineage"]["process_local_identities"]["current_p"] = record["lineage"][
            "process_local_identities"
        ]["old_p"]
    elif defect == "edge":
        record["lineage"]["actual_edges"][0][-1] = "cells"
    elif defect == "input_file":
        (Path(binding["inputs"]["root"]) / "new.dat").write_bytes(b"new")
    elif defect == "input_dir":
        (Path(binding["inputs"]["root"]) / "newdir").mkdir()
    elif defect == "input_mode":
        binding["inputs"]["mode"] = "disabled"
    elif defect == "capture":
        Path(record["iterations"][0]["files"]["path"]).write_text("{}")
    elif defect == "RNG_boundary":
        record["captures"].pop("rng_after")
    elif defect == "producer":
        record["producer"]["sha256"] = "0" * 64
    elif defect == "observer":
        record["producer"]["observer"]["sha256"] = "0" * 64
    else:
        binding["additional_unreviewed_authority"] = True
    if defect != "record_pin":
        old._replace(request["record"], record)
        binding["observation_record"] = dict(request["record"])
        terminal = json.loads(Path(binding["terminal"]["path"]).read_text())
        terminal["observation"] = dict(request["record"])
        old._replace(binding["terminal"], terminal)
        old._replace(request["binding"], binding)
    side = _saved_view(request)
    assert not side["authenticated"] and not side["endpoint_complete"] and side["error"] is not None
    old._save(
        tmp_path / "saved-file-refusal.json", dict(defect=defect, error=side["error"], credit=0)
    )


def test_sim_observation_terminal_saved_rebind_revokes_success_after_late_input_addition(
    tmp_path, monkeypatch
):
    request = _saved_binding(tmp_path, monkeypatch)
    function = stage.comparison.compare_terminal_views

    def compared(left, right):
        result = function(left, right)
        if right.get("input_tree") is not None:
            (Path(right["input_tree"]["root"]) / "late-added-directory").mkdir()
        return result

    monkeypatch.setattr(stage.comparison, "reference_side", _saved_view)
    monkeypatch.setattr(stage.comparison, "compare_terminal_views", compared)
    result = stage.comparison.compare_terminal_saved(
        request, request, accepted_observer_sha256=_accepted_observer()
    )
    assert result["status"] == "evidence_changed_during_comparison"
    assert result["exact_observation_comparison_available"] is False
    assert result["unverified_forensics"]["exact_observations_equal"] is True
    old._save(tmp_path / "late-paired-input-refusal.json", result)


@pytest.mark.parametrize("wrapped", [False, True])
def test_sim_observation_repair_wrapped_event_work_and_returns_are_actual(tmp_path, wrapped):
    result, _ = _observe(tmp_path, _model(wrapped=wrapped))
    assert len(result["iterations"]) == 2


@pytest.mark.parametrize("defect", ["unretained", "delegate", "receiver", "outer", "work_code"])
def test_sim_observation_repair_event_wrapper_substitution_refuses_before_capture(tmp_path, defect):
    model = _model(wrapped=True)
    body = model.trial.iterations[0].event_calls[1][1]
    wrapper = body.f_back
    if defect == "unretained":
        body.f_back = NS(**vars(wrapper))
    elif defect == "delegate":
        wrapper.f_locals["__beartype_func"] = object()
    elif defect == "receiver":
        body.f_locals["self"] = object()
    elif defect == "outer":
        wrapper.f_back = object()
    else:
        model.trial.work = tuple(
            (frame, model.trial.work[0][1], namespace)
            if frame is wrapper
            else (frame, code, namespace)
            for frame, code, namespace in model.trial.work
        )
    capture, rows = _capture(tmp_path)
    with pytest.raises(stage.ObservationRejected):
        stage._observe(model.owner, model.api, capture, lambda: None)
    assert rows == []


def _paired_real_readers(tmp_path, monkeypatch, *, calendar_count=2):
    issued_root, reference_root = tmp_path / "issued", tmp_path / "reference"
    issued_root.mkdir()
    reference_root.mkdir()
    issued = _saved_binding(issued_root, monkeypatch)
    reference = old._saved_reference(reference_root, count=2)
    binding = json.loads(Path(issued["binding"]["path"]).read_text())
    plan = json.loads(Path(reference["prepared"]["path"]).read_text())
    parent = json.loads(Path(plan["INIT_prepared"]["path"]).read_text())
    root = Path(parent["inputs"]["root"])
    (root / "sim_config.yaml").write_bytes(
        (Path(binding["inputs"]["root"]) / "sim_config.yaml").read_bytes()
    )
    parent["inputs"]["inventory"] = stage.comparison.input_files.inventory(root)
    old._replace(plan["INIT_prepared"], parent)
    old._replace(reference["prepared"], plan)
    release = json.loads(Path(reference["release"]["path"]).read_text())
    release["prepared_sha256"] = reference["prepared"]["sha256"]
    old._replace(reference["release"], release)
    worker = json.loads(Path(reference["worker"]["path"]).read_text())
    output = Path(reference["worker"]["path"]).parent
    label = "SIM.original_calendar"
    pins = stage.evidence.write(
        output / "SIM-reference/captures/calendar.json",
        stage._cache(_cache((_array([i * 0.125 for i in range(calendar_count)]), {0.0}))),
        label=label,
    )
    worker["SIM_captures"].append(dict(label=label, status="saved", files=pins))
    old._replace(reference["worker"], worker)
    binding["original_sources"] = parent["native_inventory_sha256"]
    old._replace(issued["binding"], binding)
    return reference, issued


def test_sim_observation_repair_real_reference_and_issued_input_provenance_match(
    tmp_path, monkeypatch
):
    reference, issued = _paired_real_readers(tmp_path, monkeypatch)
    result = stage.comparison.compare_terminal_saved(
        reference, issued, accepted_observer_sha256=_accepted_observer()
    )
    assert result["status"] == "compared_saved_observations", result
    assert result["provenance"]["input_provenance"] is True
    assert result["exact_observation_comparison_available"] is True
    assert result["numerical_parity_available"] is False
    old._save(tmp_path / "real-reader-pair.json", result)


@pytest.mark.parametrize("primary", [0, False, {}])
def test_sim_observation_repair_terminal_compare_preserves_failed_source_and_cause(
    tmp_path, monkeypatch, primary
):
    reference, issued = _paired_real_readers(tmp_path, monkeypatch, calendar_count=3)
    worker = json.loads(Path(reference["worker"]["path"]).read_text())
    worker.update(
        primary=primary,
        capture_errors=[dict(identity=3, cause=dict(identity=2))],
        SIM_capture_errors=[dict(identity=4)],
    )
    old._replace(reference["worker"], worker)
    result = stage.comparison.compare_terminal_saved(
        reference, issued, accepted_observer_sha256=_accepted_observer()
    )
    failure = result["failures"]["reference"]
    assert type(failure["primary"]) is type(primary) and failure["primary"] == primary
    assert failure["capture_errors"] == worker["capture_errors"]
    assert failure["SIM_capture_errors"] == worker["SIM_capture_errors"]
    assert result["errors"]["comparison"]["type"] == "ValueError"
    assert result["exact_observation_comparison_available"] is False
    old._save(tmp_path / "retained-source-failure.json", result)


def test_sim_observation_repair_observer_anchor_is_independent_of_supplied_graph(
    tmp_path, monkeypatch
):
    request = _saved_binding(tmp_path, monkeypatch)
    binding = json.loads(Path(request["binding"]["path"]).read_text())
    record = json.loads(Path(request["record"]["path"]).read_text())
    source = Path(binding["execution_source"]["root"])
    path = source / stage.FILE
    path.chmod(0o644)
    path.write_text(
        path.read_text()
        + "\n# coherently resealed foreign observer body\ndef foreign_observer():\n"
        '    return "supplied"\n'
    )
    path.chmod(0o444)
    digest = stage.snapshot.digest(path)
    manifest = json.loads((source / "SNAPSHOT.json").read_text())
    manifest["files"][stage.FILE].update(sha256=digest, observation=dict(size=path.stat().st_size))
    (source / "SNAPSHOT.json").chmod(0o644)
    old._replace(dict(path=str(source / "SNAPSHOT.json")), manifest)
    (source / "SNAPSHOT.json").chmod(0o444)
    binding["execution_source"]["snapshot_sha256"] = stage.snapshot.digest(source / "SNAPSHOT.json")
    binding["execution_source"]["owned_files"][stage.FILE] = digest
    runtime = json.loads(Path(binding["runtime"]["path"]).read_text())
    runtime["loaded_files"][stage.FILE[:-3].replace("/", ".")]["sha256"] = digest
    old._replace(binding["runtime"], runtime)
    record["producer"]["observer"]["sha256"] = digest
    old._replace(request["record"], record)
    binding["observation_record"] = dict(request["record"])
    terminal = json.loads(Path(binding["terminal"]["path"]).read_text())
    terminal["observation"] = dict(request["record"])
    old._replace(binding["terminal"], terminal)
    old._replace(request["binding"], binding)
    side = _saved_view(request)
    assert not side["authenticated"] and side["error"] is not None
    old._save(tmp_path / "independent-anchor-refusal.json", side["error"])


def test_sim_observation_repair_final_manifest_rebind_revokes_success(tmp_path, monkeypatch):
    request = _saved_binding(tmp_path, monkeypatch)
    binding = json.loads(Path(request["binding"]["path"]).read_text())
    function = stage.comparison.compare_terminal_views

    def compare(left, right):
        value = function(left, right)
        if right.get("input_tree") is not None:
            path = Path(binding["execution_source"]["root"]) / "SNAPSHOT.json"
            path.chmod(0o644)
            path.write_text("{}")
        return value

    monkeypatch.setattr(stage.comparison, "reference_side", _saved_view)
    monkeypatch.setattr(stage.comparison, "compare_terminal_views", compare)
    result = stage.comparison.compare_terminal_saved(
        request, request, accepted_observer_sha256=_accepted_observer()
    )
    assert result["status"] == "evidence_changed_during_comparison"
    assert result["exact_observation_comparison_available"] is False


_FOREIGN_VERIFY_CALLS = []


def _foreign_verify(*args, **kwargs):
    _FOREIGN_VERIFY_CALLS.append("foreign verification entered")
    return None


@pytest.mark.parametrize(
    "defect", ["read_slot", "read_code", "read_defaults", "read_helper", "payload_helper"]
)
def test_sim_observation_repair_transport_retarget_stops_before_foreign_verifier(
    tmp_path, monkeypatch, defect
):
    model = _model()
    captured = []
    monkeypatch.setattr(stage.evidence, "_FOREIGN_VERIFY_CALLS", captured, raising=False)
    monkeypatch.setattr(stage.evidence.payload, "_FOREIGN_VERIFY_CALLS", captured, raising=False)

    def capture(label, raw):
        wrong = dict(tree=dict(type="str", value="not observed"), columns={})
        pin = stage.evidence.write(tmp_path / "wrong.json", wrong, label=label)[0]
        if defect == "read_slot":
            monkeypatch.setattr(stage.evidence, "read", _foreign_verify)
        elif defect == "read_code":
            monkeypatch.setattr(stage.evidence.read, "__code__", _foreign_verify.__code__)
        elif defect == "read_defaults":
            monkeypatch.setattr(
                stage.evidence.read, "__kwdefaults__", dict(expand=False, expected_sha256=None)
            )
        elif defect == "read_helper":
            monkeypatch.setattr(stage.evidence, "_read", _foreign_verify)
        else:
            monkeypatch.setattr(stage.evidence.payload, "_metadata", _foreign_verify)
        return pin

    with pytest.raises(stage.ObservationRejected) as caught:
        stage._observe(model.owner, model.api, capture, lambda: None)
    context = caught.value.partial
    assert captured == [] and context.raw_observation is not None
    assert context.returned_capture_pin["path"] == str(tmp_path / "wrong.json")
    assert context.capture_errors and context.result is None
    old._save(
        tmp_path / "transport-drift-refusal.json",
        dict(error=type(context.primary).__name__, foreign_calls=captured),
    )


@pytest.mark.parametrize("observer", ["profile", "trace"])
@pytest.mark.parametrize("defect", ["profile_lost", "trace_lost", "next_retarget"])
def test_sim_observation_repair_first_validator_return_checks_before_second_delegate(
    tmp_path, monkeypatch, observer, defect
):
    model = _model()
    prior = (sys.getprofile(), sys.gettrace())
    fired = []
    foreign = []
    original = {
        name: (getattr(model.api, name), getattr(model.api, name).__code__)
        for name in ("validate_sim", "completed_sim")
    }

    def check():
        for name, (fn, code) in original.items():
            assert getattr(model.api, name) is fn and fn.__code__ is code, (
                "public validator retarget"
            )

    def probe(frame, event, arg):
        if frame.f_code is original["validate_sim"][1] and event == "return" and not fired:
            fired.append(arg)
            if defect == "profile_lost":
                sys.setprofile(None)
            elif defect == "trace_lost":
                sys.settrace(None)
            else:
                monkeypatch.setattr(model.api, "completed_sim", lambda owner: foreign.append(owner))

    def profile(frame, event, arg):
        if prior[0] is not None:
            prior[0](frame, event, arg)
        probe(frame, event, arg)

    local = {}

    def trace(frame, event, arg):
        delegate = prior[1] if event == "call" else local.get(id(frame))
        if delegate is not None:
            child = delegate(frame, event, arg)
            if child is not None:
                local[id(frame)] = child
        probe(frame, event, arg)
        if event == "return":
            local.pop(id(frame), None)
        return trace

    try:
        (sys.setprofile(profile) if observer == "profile" else sys.settrace(trace))
        expected = (sys.getprofile(), sys.gettrace())
        with pytest.raises(stage.ObservationRejected) as caught:
            stage._observe(model.owner, model.api, lambda *a: None, check)
        assert model.calls == ["validate"] and foreign == []
        assert fired == [model.trial]
        assert caught.value.partial.public_returns[0][1] is model.trial
        assert (sys.getprofile(), sys.gettrace()) == expected
    finally:
        sys.setprofile(prior[0])
        sys.settrace(prior[1])
