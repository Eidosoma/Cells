"""Held independent original-BETSE retained-INIT -> SIM reference.

The coordinator itself creates its complete INIT predecessor. It accepts no
phase, simulator, state/cache or checkpoint input. The selected SIM caller is
the original post-load data path around those same actual objects. Full native
SimRunner.sim file/autoInit/loadSim history is expressly outside this route.
"""

import argparse
import dis
import importlib.abc
import os
import resource
import runpy
import struct
import sys
from contextlib import _GeneratorContextManager
from dataclasses import dataclass, field
from pathlib import Path
from types import FunctionType, GeneratorType, ModuleType, SimpleNamespace

from validation import source_snapshot as snapshot
from validation.betse import native_init_terminal_reference as initial
from validation.betse import native_sim_reference_source as source

ROOT = Path(__file__).resolve().parents[2]
FILE = "validation/betse/native_sim_reference.py"
LITERAL = "validation/betse/native_sim_reference_source.py"
TEST = "tests/unit/test_native_sim_reference.py"
RUNNER = "validation/betse/native_sim_reference_software.py"
OWNED = (FILE, LITERAL, TEST, RUNNER)
KIND = "cells.original_SIM_retained_INIT_reference@2"
RELEASE = "CELLS_ORIGINAL_SIM_REFERENCE_RELEASED"
REFERENCE_SHA256 = "b5f4cb50be3e107e395a9de82ed6d1edd10c52c156a3f6b73c5e86e0a4b5cdbf"
SOURCE_REVIEW_SHA256 = REFERENCE_REVIEW_SHA256 = EXECUTION_REVIEW_SHA256 = None
MAX_SIM_ITERATIONS = initial.MAX_ITERATIONS
MAX_STEP_EVENT_BOUNDARIES = 512
_ATTEMPT = None
_RAW_FAILURES = []


def preparation_starts():
    return (
        *OWNED,
        initial.FILE,
        initial.TEST,
        initial.RUNNER,
        "validation/betse/native_seed_demo.py",
        "validation/betse/native_seed_world_callback_prelude.py",
        "validation/betse/native_seed_demo_launch.py",
    )


def prepare(output, *, input_pair, input_sha256, mode):
    """One-way checkout snapshot then metadata-only original INIT preparation."""
    from validation.betse import betse_mesh_lifecycle_preparation_guard as guard

    input_pair = initial._path(input_pair)
    initial._require(input_pair.is_dir(), "Original paired-input directory required", "inputs")
    raw, _ = initial._read(input_pair / "inputs.json", 2**20)
    initial._require(
        initial._sha(raw) == input_sha256, "Exact paired-input manifest required", "inputs"
    )
    output = initial._path(output)
    initial._require(
        not output.exists() and output.is_relative_to(Path("/mnt/workspaces/Cells")),
        "Fresh contained SIM preparation required",
    )
    output.mkdir(parents=True)
    files = runpy.run_path(str(ROOT / initial.CLOSURE))["closure"](ROOT, preparation_starts())
    files[initial.CLOSURE] = snapshot.digest(ROOT / initial.CLOSURE)
    frozen = output / "source"
    snapshot.freeze(ROOT, frozen, {name: name for name in files})
    snapshot.assert_checkout_unchanged(frozen)
    environment = dict(
        os.environ,
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=os.pathsep.join((str(frozen), str(frozen / "src"))),
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
    )
    metadata = output / "metadata"
    metadata.mkdir()
    guard.run_bounded(
        [
            sys.executable,
            "-B",
            "-m",
            "validation.betse.native_sim_reference",
            "--prepare-frozen",
            str(output),
            "--input-pair",
            str(input_pair),
            "--input-sha256",
            input_sha256,
            "--mode",
            mode,
        ],
        directory=metadata,
        cwd=frozen,
        env=environment,
        timeout=120,
        max_rss_bytes=512 * 2**20,
        min_available_bytes=8 * 2**30,
    )
    snapshot.assert_checkout_unchanged(frozen)
    return output / "prepared.json"


def prepare_frozen(output, *, input_pair, input_sha256, mode):
    manifest = snapshot.verify(ROOT)
    initial._require(
        all(
            name in manifest["files"]
            for name in (*OWNED, initial.FILE, initial.TEST, initial.RUNNER)
        ),
        "Complete SIM and INIT producer roster required in the same snapshot",
    )
    initial._require(
        snapshot.digest(Path(initial.__file__)) == REFERENCE_SHA256,
        "Exact predecessor reference producer required",
    )
    prefix = output / "INIT-preparation"
    initial.prepare(prefix, input_pair=input_pair, input_sha256=input_sha256, mode=mode)
    parent = prefix / "prepared.json"
    plan = dict(
        kind=KIND,
        held=True,
        source_plan=source_plan(),
        execution_source=dict(
            root=str(ROOT),
            snapshot_sha256=snapshot.digest(ROOT / "SNAPSHOT.json"),
            owned_files={name: manifest["files"][name]["sha256"] for name in OWNED},
        ),
        INIT_prepared=dict(path=str(parent), sha256=snapshot.digest(parent)),
        source_native_reference_execution_released=False,
    )
    snapshot.write_json(output / "prepared.json", plan)
    return plan


@dataclass
class Attempt:
    stage: str = "preflight"
    primary: object = None
    secondary: list = field(default_factory=list)
    parent: object = None
    parent_result: object = None
    parent_consumed: bool = False
    raw: dict = field(default_factory=dict)
    sim: object = None
    observer: object = None
    imports: object = None
    required_hooks: object = None
    hooks_restored: bool = False
    finalization_complete: bool = False
    closed_lineage: object = None
    terminal_observation: object = None
    controls: object = None
    coverage_stop: object = field(
        default_factory=lambda: initial.ReferenceRejected(
            "Required inherited coverage changed during SIM metadata", stage="observer"
        )
    )


def source_plan():
    return dict(
        kind=KIND,
        original=source.source_plan(),
        reference_source=REFERENCE_SHA256,
        predecessor="coordinator invokes the released original INIT producer in this same process",
        external_owner_cache_phase_or_pickle_inputs=False,
        continuation=(
            "fresh full original current Parameters and SimRunner; retained actual sim/cells"
        ),
        input_config_unchanged=True,
        max_SIM_iterations=MAX_SIM_ITERATIONS,
        full_original_calendar_or_explicit_capacity_refusal=True,
        observation="streamed per-step fields and full RNG; file pins, one live row",
        observation_contract=source.observation_plan(),
        stopped_before="native SIM pickle; no full saved-pickle caller or checkpoint claim",
        native_imports=(
            "existing verified original modules only; absent dependencies explicitly refuse"
        ),
        resource_policy=dict(initial.NATIVE_POLICY),
        reviews=dict(
            source=SOURCE_REVIEW_SHA256,
            reference=REFERENCE_REVIEW_SHA256,
            execution=EXECUTION_REVIEW_SHA256,
        ),
        actual_source_native_reference_execution_released=False,
        physical_numerical_or_checkpoint_credit=0,
    )


class ExistingOriginalImports(importlib.abc.MetaPathFinder):
    """Do not reopen/reset the closed predecessor loader or fall back to BETSE."""

    def find_spec(self, fullname, path=None, target=None):
        if fullname == "betse" or fullname.startswith("betse."):
            raise initial.ReferenceRejected(
                "New original import authority unavailable: " + fullname,
                stage="missing_original_import",
            )
        return None


class SimArchive(initial.Archive):
    def save(self, label, value):
        return super().save("SIM." + label, value)


def _terminal_atom(value, depth=0):
    initial._require(depth <= 16, "Bounded original terminal delegate graph", "terminal")
    kind = type(value)
    if value is None or kind in (str, bool, int):
        return kind, value
    if kind is float:
        return kind, struct.pack("!d", value)
    if kind in (tuple, list):
        return kind, id(value), tuple(_terminal_atom(v, depth + 1) for v in value)
    if kind is dict:
        return (
            kind,
            id(value),
            tuple(
                (_terminal_atom(k, depth + 1), _terminal_atom(v, depth + 1))
                for k, v in value.items()
            ),
        )
    if kind is FunctionType:
        return (
            kind,
            id(value),
            id(value.__code__),
            id(value.__globals__),
            _terminal_atom(value.__defaults__, depth + 1),
            _terminal_atom(value.__kwdefaults__, depth + 1),
            tuple(
                (id(cell), _terminal_atom(cell.cell_contents, depth + 1))
                for cell in value.__closure__ or ()
            ),
            _terminal_atom(vars(value).get("__wrapped__"), depth + 1),
        )
    return kind, id(value)


def _fields(actual, names):
    data = {} if actual is None else vars(actual)
    return {
        name: dict(present=name in data, **({"value": data[name]} if name in data else {}))
        for name in names
    }


def _network_gates(sim, p, name):
    enabled = getattr(p, name + "_enabled")
    initial._require(
        type(enabled) is bool, "Actual native channel-enable boolean required", "capture"
    )
    if not enabled:
        return dict(enabled=False, source_branch="disabled; no channel owner substituted")
    master = getattr(sim, name)
    core = master.core
    values = []
    for key, channel in core.channels.items():
        initial._require(type(key) is str, "Actual named native channel roster required", "capture")
        channel_core = channel.channel_core
        values.append(
            dict(
                name=key,
                core_type=type(channel_core).__module__ + "." + type(channel_core).__qualname__,
                fields=dict(vars(channel_core)),
            )
        )
    return dict(enabled=True, channels=values)


class SimObserve(initial.Observe):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.observation_contract = source.observation_plan()
        self.step_events, self.event_sequence = [], 0
        self.state.raw["active_event_boundaries"] = self.step_events
        self.terminal = None

    def enable_terminal(self, attempt, mode):
        self.terminal = SimpleNamespace(
            attempt=attempt,
            mode=mode,
            frames={},
            functions={},
            events=[],
            returns=set(),
            calendar=None,
            sampled=None,
            manager=None,
            phase=None,
            context_entries=0,
            context_yield=False,
            context_return=False,
            iteration_times=[],
            raw_returns=[],
            bindings={},
        )
        self.state.raw["terminal_authority"] = self.terminal

    def _terminal_role(self, frame):
        pair = frame.f_globals.get("__name__"), frame.f_code.co_name
        if pair == ("betse.science.simrunner", source.ENTRY):
            return "caller"
        for role, (path, qualified) in source.TERMINAL_METHODS.items():
            if pair == (path[:-3].replace("/", "."), qualified.rsplit(".", 1)[-1]):
                return role
        return None

    def _terminal_function(self, frame, role):
        t = self.terminal
        module = sys.modules.get(frame.f_globals.get("__name__"))
        initial._require(
            type(module) is ModuleType
            and vars(module) is frame.f_globals
            and module.__loader__ is t.attempt.raw["original_package"],
            "Actual original terminal namespace/loader required",
            "terminal",
        )
        if role == "caller":
            fn = self.state.raw["selected_SIM_caller"]
            expected = source.selected()[0]
        else:
            _, qualified = source.TERMINAL_METHODS[role]
            parts = qualified.split(".")
            holder = module if len(parts) == 1 else vars(module)[parts[0]]
            fn = vars(holder)[parts[-1]]
            expected = source.terminal_code(role, t.mode)
        exported = fn
        binding = _terminal_atom(exported)
        if role in t.bindings:
            initial._require(
                binding == t.bindings[role], "Original terminal export/delegate changed", "terminal"
            )
        else:
            t.bindings[role] = binding
        chain = []
        while fn is not None:
            initial._require(
                type(fn) is FunctionType
                and len(chain) < 16
                and not any(fn is old for old in chain),
                "Actual terminal callable chain",
                "terminal",
            )
            chain.append(fn)
            fn = vars(fn).get("__wrapped__")
        body = chain[-1]
        initial._require(
            body.__code__ == expected
            and frame.f_code is body.__code__
            and frame.f_globals is body.__globals__,
            "Literal original terminal body/code required",
            "terminal",
        )
        caller = frame.f_back
        if role == "context":
            t.functions[role] = tuple(chain)
            return caller
        for wrapper in reversed(chain[:-1]):
            initial._require(
                caller is not None
                and caller.f_code is wrapper.__code__
                and caller.f_globals is wrapper.__globals__,
                "Actual terminal wrapper/body stack required",
                "terminal",
            )
            for key, value in (wrapper.__kwdefaults__ or {}).items():
                initial._require(
                    caller.f_locals.get(key) is value,
                    "Terminal wrapper delegate changed",
                    "terminal",
                )
            caller = caller.f_back
        t.functions[role] = tuple(chain)
        return caller

    def _terminal_entry(self, frame):
        if self.terminal is None:
            return
        t = self.terminal
        role = self._terminal_role(frame)
        if (
            frame.f_globals.get("__name__") == "betse.science.sim"
            and frame.f_code.co_name == "_run_fast_sim_core_loop"
        ):
            raise initial.ReferenceRejected(
                "FAST terminal reference is outside the full-loop boundary", stage="terminal"
            )
        if role is None:
            return
        caller = self._terminal_function(frame, role)
        t.events.append((len(t.events) + 1, role, "enter"))
        if role == "context":
            initial._require(
                t.manager is not None
                and frame is t.manager.gen.gi_frame
                and t.context_entries < 2
                and (not t.context_entries or "loop" in t.returns),
                "Original same no-animation context order required",
                "terminal",
            )
            t.context_entries += 1
            t.frames[role] = frame
            return
        initial._require(role not in t.frames, "Duplicate original terminal boundary", "terminal")
        t.frames[role] = frame
        if role == "caller":
            return
        if role == "phase":
            initial._require(
                caller is t.frames.get("caller")
                and frame.f_locals.get("p") is self.state.raw["current_parameters"],
                "Fresh original SIM phase constructor order required",
                "terminal",
            )
            return
        phase = frame.f_locals.get("phase")
        parent = self.state.raw["lineage_before"]
        initial._require(
            phase is t.phase
            and frame.f_locals.get("self") is parent["simulator"]
            and phase.p is self.state.raw["current_parameters"]
            and phase.sim is parent["simulator"]
            and phase.cells is parent["cells"],
            "Actual same simulator/cells/current parameter terminal chain required",
            "terminal",
        )
        if role == "report":
            initial._require(
                "phase" in t.returns and caller is t.frames["caller"],
                "Report after genuine phase required",
                "terminal",
            )
        elif role == "core":
            initial._require(
                "report" in t.returns and caller is t.frames["caller"],
                "Core after genuine report required",
                "terminal",
            )
        elif role == "calendar":
            initial._require(
                caller is t.frames.get("core"), "Calendar actual core caller required", "terminal"
            )
        elif role == "loop":
            initial._require(
                t.context_yield
                and caller is t.frames.get("core")
                and frame.f_locals.get("time_steps") is t.calendar
                and frame.f_locals.get("time_steps_sampled") is t.sampled
                and frame.f_locals.get("anim_cells") is None,
                "Original entered context and exact full loop axes required",
                "terminal",
            )

    def _terminal_return(self, frame, value, error):
        if self.terminal is None:
            return
        t = self.terminal
        role = self._terminal_role(frame)
        if role is None or t.frames.get(role) is not frame:
            return
        # Preserve an already caught native instability before any append or
        # inherited observation can fail. Falsey exceptions remain primary.
        self.state.raw["last_terminal_return"] = frame, value, error
        primary = (
            error
            if error is not None
            else (frame.f_locals.get("exception_instability") if role == "core" else None)
        )
        if primary is not None:
            self.state.primary = primary
        try:
            t.raw_returns.append((frame, value, error))
        except BaseException as capture:
            self.state.raw["terminal_return_capture_error"] = capture
            if self.state.capture_error is None:
                self.state.capture_error = capture
            try:
                self._capture("terminal_raw_return", capture)
            except BaseException as secondary:
                self.state.raw["terminal_return_capture_reporting_error"] = secondary
            return
        if primary is not None:
            return
        opcode = dis.opname[frame.f_code.co_code[frame.f_lasti]]
        if role == "context" and opcode == "YIELD_VALUE":
            initial._require(
                t.context_entries == 1 and not t.context_yield,
                "One genuine context yield",
                "terminal",
            )
            t.context_yield = True
            t.events.append((len(t.events) + 1, role, "yield"))
            return
        initial._require(
            opcode in ("RETURN_VALUE", "RETURN_CONST"),
            "Normal original terminal return required",
            "terminal",
        )
        if role == "phase":
            t.phase = frame.f_locals["self"]
        elif role == "calendar":
            np = frame.f_globals["np"]
            initial._require(
                type(value) is tuple and len(value) == 3,
                "Actual native three-value calendar",
                "terminal",
            )
            calendar, sampled, manager = value
            initial._require(
                type(calendar) is np.ndarray
                and calendar.ndim == 1
                and calendar.dtype.str in ("<f8", ">f8")
                and 1 <= len(calendar) <= MAX_SIM_ITERATIONS
                and type(sampled) is set
                and all(v in calendar for v in sampled)
                and type(manager) is _GeneratorContextManager
                and type(manager.gen) is GeneratorType
                and manager.gen.gi_code == source.terminal_code("context", t.mode),
                "Actual full calendar/sample/noop context return required",
                "terminal",
            )
            t.calendar, t.sampled, t.manager = value
            self.state.raw["terminal_calendar_return"] = value
        elif role == "loop":
            initial._require(
                len(t.iteration_times) == len(t.calendar) == t.phase.p.sim_tsteps,
                "Entire configured original calendar must complete",
                "terminal",
            )
        elif role == "context":
            initial._require(
                t.context_entries == 2 and "loop" in t.returns,
                "Normal original context exit after loop",
                "terminal",
            )
            t.context_return = True
        elif role == "core":
            initial._require(
                t.context_return
                and "loop" in t.returns
                and frame.f_locals.get("exception_instability") is None,
                "Full original loop/context and no hidden instability before pickle",
                "terminal",
            )
        elif role == "caller":
            initial._require(
                "core" in t.returns and value is t.phase,
                "Original selected caller normal return",
                "terminal",
            )
        t.returns.add(role)
        t.events.append((len(t.events) + 1, role, "return"))

    def _event(self, frame, boundary, error=None):
        module, name = frame.f_globals.get("__name__"), frame.f_code.co_name
        if name not in source.EVENT_METHODS.get(module, ()):
            return
        local = frame.f_locals
        raw = dict(frame=frame, locals=dict(local), error=error, boundary=boundary)
        self.state.raw["last_event_observation"] = raw
        initial._require(
            len(self.step_events) < MAX_STEP_EVENT_BOUNDARIES,
            "SIM per-step event observation capacity",
            "capture",
        )
        self.event_sequence += 1
        actual = local.get("self")
        data = {} if actual is None else vars(actual)
        self.step_events.append(
            dict(
                ordinal=self.event_sequence,
                module=module,
                method=name,
                boundary=boundary,
                source_time=local["t"] if "t" in local else local.get("time_step"),
                is_fired=dict(
                    present="_is_fired" in data,
                    **({"value": data["_is_fired"]} if "_is_fired" in data else {}),
                ),
                error_type=None
                if error is None
                else type(error).__module__ + "." + type(error).__qualname__,
                cause_type=None
                if error is None or error.__cause__ is None
                else type(error.__cause__).__module__ + "." + type(error.__cause__).__qualname__,
            )
        )

    def _entry(self, frame):
        already = id(frame) in self.admitted
        module, name = frame.f_globals.get("__name__"), frame.f_code.co_name
        initial._require(
            not (
                module == "betse.science.filehandling"
                and name in ("loadWorld", "loadSim", "saveSim")
            ),
            "Saved-source substitution is not admitted in SIM",
            "entry",
        )
        result = super()._entry(frame)
        if not already:
            self._terminal_entry(frame)
            self._event(frame, "enter")
        return result

    def _return(self, frame, value):
        admitted, error = id(frame) in self.admitted, self.pending.get(id(frame))
        if admitted:
            self._terminal_return(frame, value, error)
        super()._return(frame, value)
        if admitted:
            self._event(frame, "return" if error is None else "unwind", error)
        if (frame.f_globals.get("__name__"), frame.f_code.co_name) == (
            "betse.science.sim",
            "_plot_loop",
        ):
            initial._require(
                1 <= len(value[0]) <= MAX_SIM_ITERATIONS,
                "Complete original SIM calendar exceeds observation capacity",
                "capacity",
            )

    def _iteration(self, frame):
        local = frame.f_locals
        if "t" not in local:
            return
        ordinal = len(self.state.iterations) + 1
        initial._require(
            ordinal <= MAX_SIM_ITERATIONS, "Complete SIM observation capacity", "capture"
        )
        phase, sim = local["phase"], local["self"]
        if self.terminal is not None:
            t = self.terminal
            initial._require(
                frame is t.frames.get("loop")
                and phase is t.phase
                and len(t.iteration_times) < len(t.calendar)
                and struct.pack("!d", local["t"])
                == struct.pack("!d", t.calendar[len(t.iteration_times)]),
                "Exact completed original calendar ordinal/time required",
                "terminal",
            )
            t.iteration_times.append(struct.pack("!d", local["t"]).hex())
        p, dyna = phase.p, phase.dyna
        gates = dict(
            gap_junction=_fields(sim, source.GJ_FIELDS),
            gap_junction_core=_fields(sim.gj_funk, source.GJ_CORE_FIELDS),
            molecules=_network_gates(sim, p, "molecules"),
            grn=_network_gates(sim, p, "grn"),
        )
        events = dict(
            calls=list(self.step_events),
            global_options=p.global_options,
            scheduled_options=p.scheduled_options,
            event_cut=dict(
                present=dyna.event_cut is not None,
                **({"fields": dict(vars(dyna.event_cut))} if dyna.event_cut is not None else {}),
            ),
            voltage_event=dict(
                present=dyna._event_voltage is not None,
                **(
                    {"fields": dict(vars(dyna._event_voltage))}
                    if dyna._event_voltage is not None
                    else {}
                ),
            ),
        )
        row = dict(
            ordinal=ordinal,
            source_time=local["t"],
            sampled=local["t"] in local["time_steps_sampled"],
            configured_dt=p.dt,
            fields={
                name: vars(sim)[name] for name in initial.ITERATION_FIELDS if name in vars(sim)
            },
            numpy_random=frame.f_globals["np"].random.get_state(),
            python_random=initial.random.getstate(),
            observation_contract=source.OBSERVATION_KIND,
            gates=gates,
            electric_fields=_fields(sim, source.ELECTRIC_FIELDS),
            events=events,
        )
        self.state.raw["last_iteration"] = row
        saved = self.archive.save(f"iteration_{ordinal:04d}", row)
        self.state.iterations.append(saved)
        self.step_events.clear()


def _parent_state(result, before):
    state = initial._ATTEMPT
    initial._require(
        before is None
        and type(state) is initial.State
        and state is not before
        and result.get("kind") == initial.KIND
        and result.get("status") == "completed"
        and state.primary is None
        and state.capture_error is None
        and state.source_returned is True
        and state.hooks_restored is True,
        "Actual newly completed original INIT predecessor required",
        "INIT_parent",
    )
    phase = state.raw.get("init_phase")
    p = state.raw.get("parameters")
    modules = {}
    for name in (
        "betse.science.phase.phasecls",
        "betse.science.simrunner",
        "betse.science.sim",
        "betse.science.parameters",
        "betse.science.cells",
        "betse.science.enum.enumphase",
    ):
        module = sys.modules.get(name)
        initial._require(
            type(module) is ModuleType and type(module.__loader__) is initial.OriginalPackage,
            "Original loaded class authority unavailable: " + name,
            "INIT_parent",
        )
        modules[name] = module
    initial._require(
        type(phase) is modules["betse.science.phase.phasecls"].SimPhase
        and phase.p is p
        and type(p) is modules["betse.science.parameters"].Parameters
        and type(phase.sim) is modules["betse.science.sim"].Simulator
        and type(phase.cells) is modules["betse.science.cells"].Cells
        and phase.kind is modules["betse.science.enum.enumphase"].SimPhaseKind.INIT
        and p._run_sim is False,
        "Retained actual INIT phase/parameter/simulator chain required",
        "INIT_parent",
    )
    package = modules["betse.science.simrunner"].__loader__
    initial._require(
        all(module.__loader__ is package for module in modules.values())
        and package.used is True
        and package not in sys.meta_path,
        "Closed original package ancestry required; no re-arm",
        "INIT_parent",
    )
    package.verify()
    return state, phase, package


def _sim_execution(observer, execute):
    """Independent recovery even if a callback rejects context-manager exit."""
    state = observer.state
    required = sys.getprofile(), sys.gettrace()
    state.raw["required_inherited_hooks"] = required
    setters, getters = (sys.setprofile, sys.settrace), (sys.getprofile, sys.gettrace)
    manager = None
    try:
        manager = initial.observed(observer)
        state.raw["observed_manager"] = manager
        with manager:
            try:
                execute()
            except BaseException as error:
                # Retain the body before contextlib/observer exit can fail.
                if state.primary is None:
                    state.primary = (
                        state.native_unwind if state.native_unwind is not None else error
                    )
                elif state.primary is not error:
                    state.secondary.append(("SIM_body", error))
                raise
    except BaseException as error:
        if state.primary is None:
            state.primary = state.native_unwind if state.native_unwind is not None else error
        elif state.primary is not error:
            state.secondary.append(("SIM_observer_exit", error))
    finally:
        observer.managed = False
        if manager is not None:
            # A rejected __exit__ may never have resumed the generator. Close
            # that exact manager now, before publishing restored identities;
            # never leave its captured setters to a later GC cycle.
            try:
                manager.gen.close()
            except BaseException as error:
                state.secondary.append(("SIM_observer_context_retirement", error))
                if state.capture_error is None:
                    state.capture_error = error
            if manager.gen.gi_frame is not None:
                state.raw["unretired_observer_manager"] = manager
                state.coverage_failed = True
        for setter, previous, label in zip(
            setters, required, ("SIM_outer_profile_restore", "SIM_outer_trace_restore"), strict=True
        ):
            try:
                setter(previous)
            except BaseException as error:
                state.secondary.append((label, error))
                if state.capture_error is None:
                    state.capture_error = error
        final = []
        for getter, label in zip(
            getters, ("SIM_outer_profile_identity", "SIM_outer_trace_identity"), strict=True
        ):
            try:
                final.append(getter())
            except BaseException as error:
                final.append(object())
                state.secondary.append((label, error))
                if state.capture_error is None:
                    state.capture_error = error
        state.hooks_restored = final[0] is required[0] and final[1] is required[1]
        state.coverage_failed = state.coverage_failed or not state.hooks_restored
    if state.primary is not None:
        raise state.primary
    if "unretired_observer_manager" in state.raw:
        raise observer.coverage_stop
    if not state.hooks_restored:
        raise observer.coverage_stop
    if state.capture_error is not None:
        raise observer.capture_stop from state.capture_error


def _metadata(attempt, label, callback, *args, **kwargs):
    """Recover actual hooks at each declared callback's entry and return."""
    required = attempt.required_hooks
    setters, getters = attempt.controls
    if "metadata_coverage_unavailable" in attempt.raw:
        if attempt.primary is not None:
            raise attempt.primary
        raise attempt.coverage_stop
    result, error = None, None
    for boundary in ("before", "after"):
        actual = []
        for getter in getters:
            try:
                actual.append(getter())
            except BaseException as failure:
                actual.append(object())
                attempt.secondary.append((label + "." + boundary + ".identity", failure))
        changed = actual[0] is not required[0] or actual[1] is not required[1]
        if changed:
            attempt.secondary.append((label + "." + boundary + ".coverage", attempt.coverage_stop))
            state = attempt.sim
            if state is not None and state.capture_error is None:
                state.capture_error = attempt.coverage_stop
        for setter, prior in zip(setters, required, strict=True):
            try:
                setter(prior)
            except BaseException as failure:
                attempt.secondary.append((label + "." + boundary + ".restore", failure))
                state = attempt.sim
                if state is not None and state.capture_error is None:
                    state.capture_error = failure
        final = []
        for getter in getters:
            try:
                final.append(getter())
            except BaseException as failure:
                final.append(object())
                attempt.secondary.append((label + "." + boundary + ".final_identity", failure))
        attempt.hooks_restored = final[0] is required[0] and final[1] is required[1]
        if not attempt.hooks_restored:
            attempt.raw["metadata_coverage_unavailable"] = dict(
                label=label, boundary=boundary, actual=tuple(final), error=error
            )
            _RAW_FAILURES.append(attempt)
            primary = attempt.primary
            if primary is None and attempt.sim is not None:
                primary = attempt.sim.primary
            if primary is not None:
                raise primary
            raise error if error is not None else attempt.coverage_stop
        if boundary == "before":
            try:
                result = callback(*args, **kwargs)
            except BaseException as failure:
                error = failure
    if error is not None:
        raise error
    return result


def _continue(attempt, plan, output):
    """Only called with the predecessor created by evaluate, never supplied data."""
    phase, package = attempt.raw["INIT_phase"], attempt.raw["original_package"]
    state = attempt.sim = initial.State(stage="SIM_parameters")
    state.raw["lineage_before"] = dict(
        INIT_phase=phase, old_parameters=phase.p, simulator=phase.sim, cells=phase.cells
    )
    (output / "SIM-reference").mkdir()
    archive = SimArchive(output / "SIM-reference" / "captures", state)
    observer = attempt.observer = SimObserve(
        state, initial.NATIVE_ROOT, archive, None, initial._loop_line(initial.NATIVE_ROOT)
    )
    parent_plan = initial._json_record(
        plan["INIT_prepared"]["path"], plan["INIT_prepared"]["sha256"]
    )
    observer.enable_terminal(attempt, parent_plan["inputs"]["mode"])
    blocker = attempt.imports = ExistingOriginalImports()
    attempt.raw["SIM_archive"] = archive
    attempt.parent_consumed = True
    # Retirement precedes any current-parameter constructor or child mutation.
    attempt.stage = "SIM_continuation"

    def execute():
        module = sys.modules["betse.science.parameters"]
        config = output / "config" / initial.profiles.MAIN
        current_p = module.Parameters.make(str(config))
        state.raw["current_parameters"] = current_p
        initial._require(current_p is not phase.p, "Fresh actual current p required", "parameters")
        current_runner = sys.modules["betse.science.simrunner"].SimRunner(current_p)
        state.raw["runner"] = current_runner
        initial._require(
            current_runner._p is current_p,
            "Actual new runner/current p association",
            "parameters",
        )
        state.raw["INIT_phase"] = phase
        state.stage = "SIM"
        caller = source.bind(sys.modules["betse.science.simrunner"])
        state.raw["selected_SIM_caller"] = caller
        result = caller(current_runner, phase.sim, phase.cells, phase.p)
        state.raw["SIM_phase"] = result
        initial._stop(state)
        initial._require(
            result is not phase
            and result.sim is phase.sim
            and result.cells is phase.cells
            and result.p is current_p
            and result.kind.name == "SIM"
            and current_p._run_sim is True
            and state.source_returned is True
            and len(state.iterations) == current_p.sim_tsteps,
            "Complete genuine SIM phase/source/calendar required",
            "completion",
        )
        package.verify()

    try:
        sys.meta_path.insert(0, blocker)
        _sim_execution(observer, execute)
    except BaseException as error:
        if state.primary is None:
            state.primary = state.native_unwind if state.native_unwind is not None else error
        elif state.primary is not error:
            state.secondary.append(("SIM_continuation", error))
    finally:
        try:
            sys.meta_path[:] = [item for item in sys.meta_path if item is not blocker]
        except BaseException as error:
            state.secondary.append(("SIM_import_guard_cleanup", error))
            if state.capture_error is None:
                state.capture_error = error
    initial._stop(state)
    attempt.stage = "completed_before_SIM_pickle"


def _terminal_record(attempt):
    state = attempt.sim
    t = attempt.observer.terminal
    initial._require(
        t is not None
        and state.primary is None
        and state.capture_error is None
        and state.source_returned
        and state.hooks_restored
        and not state.coverage_failed,
        "Actual successful terminal source/coverage required",
        "terminal",
    )
    expected = {"caller", "phase", "report", "core", "calendar", "loop", "context"}
    initial._require(
        t.returns == expected
        and t.context_entries == 2
        and t.context_yield
        and t.context_return
        and len(t.iteration_times)
        == len(t.calendar)
        == len(state.iterations)
        == t.phase.p.sim_tsteps
        and t.phase is state.raw["SIM_phase"],
        "Complete original source terminal witness unavailable",
        "terminal",
    )
    initial._require(
        t.events
        == [(i + 1, *event) for i, event in enumerate(source.terminal_plan()["required_events"])],
        "Exact genuine original terminal call/return order required",
        "terminal",
    )
    for role, chain in t.functions.items():
        frame = t.frames[role]
        attempt.observer._terminal_function(frame, role)
        initial._require(
            frame.f_code is chain[-1].__code__ and frame.f_globals is chain[-1].__globals__,
            "Retained terminal body changed after return",
            "terminal",
        )
    value = dict(
        kind="cells.original_SIM_terminal_observation@1",
        epoch=source.EPOCH,
        normal_phase_return=True,
        normal_report_return=True,
        normal_core_prefix_return=True,
        normal_full_loop_return=True,
        normal_context_return=True,
        normal_selected_caller_return=True,
        context_entries=t.context_entries,
        context_yield=t.context_yield,
        before_native_pickle=True,
        native_pickle_entered=False,
        configured_iterations=t.phase.p.sim_tsteps,
        completed_iterations=len(state.iterations),
        source_time_bits=list(t.iteration_times),
        sampled_time_bits=[struct.pack("!d", v).hex() for v in t.sampled],
        dt_bits=struct.pack("!d", t.phase.p.dt).hex(),
        selected_source=source.terminal_plan(),
        events=list(t.events),
        actual_frame_identities={role: id(frame) for role, frame in t.frames.items()},
        lineage_identities={
            name: id(value)
            for name, value in dict(
                INIT_phase=state.raw["lineage_before"]["INIT_phase"],
                old_parameters=state.raw["lineage_before"]["old_parameters"],
                SIM_phase=t.phase,
                current_parameters=t.phase.p,
                simulator=t.phase.sim,
                cells=t.phase.cells,
            ).items()
        },
        physical_checkpoint_or_common_starting_authority=False,
    )
    state.raw["terminal_observation"] = value
    return value


def _closed_lineage(attempt):
    """Observe actual retained edges; this record can never hydrate an owner."""
    state, parent = attempt.sim, attempt.parent
    before = state.raw["lineage_before"]
    old_phase, old_p, sim, cells = (
        before[name] for name in ("INIT_phase", "old_parameters", "simulator", "cells")
    )
    phase, current = state.raw["SIM_phase"], state.raw["current_parameters"]
    facts = dict(
        old_and_current_p_distinct=current is not old_p,
        sim_retained=old_phase.sim is sim and phase.sim is sim,
        cells_retained=old_phase.cells is cells and phase.cells is cells,
        fresh_SIM_phase=phase is not old_phase
        and phase.kind.name == "SIM"
        and phase.p is current
        and old_phase.p is old_p
        and current._run_sim is True
        and old_p._run_sim is False,
        one_shot_INIT_consumed=attempt.parent_consumed is True
        and initial._ATTEMPT is parent
        and _ATTEMPT is attempt
        and parent.raw["init_phase"] is old_phase
        and parent.raw["parameters"] is old_p,
    )
    observed = dict(
        kind="cells.original_SIM_closed_lineage_observation@1",
        epoch="after_original_SIM_core_before_pickle_with_restored_hooks",
        facts=facts,
        process_local_identities={
            name: id(value)
            for name, value in dict(
                INIT_phase=old_phase,
                old_parameters=old_p,
                SIM_phase=phase,
                current_parameters=current,
                simulator=sim,
                cells=cells,
            ).items()
        },
        actual_edges=[
            ["INIT_phase", "p", "old_parameters"],
            ["INIT_phase", "sim", "simulator"],
            ["INIT_phase", "cells", "cells"],
            ["SIM_phase", "p", "current_parameters"],
            ["SIM_phase", "sim", "simulator"],
            ["SIM_phase", "cells", "cells"],
        ],
        source_returned=state.source_returned,
        inherited_hooks_restored=state.hooks_restored,
        observer_coverage_failed=state.coverage_failed,
        live_owner_or_checkpoint_hydration=False,
    )
    state.raw["closed_lineage_observation"] = observed
    initial._require(
        all(value is True for value in facts.values())
        and state.source_returned
        and state.hooks_restored
        and not state.coverage_failed,
        "Actual closed original SIM ancestry/coverage changed",
        "lineage",
    )
    return observed


def _finish_sim(attempt, plan, output):
    """Check the retained real authorities, keeping INIT evidence immutable."""
    from validation.betse import betse_normal_channel_join_runtime as runtime

    state, parent = attempt.sim, attempt.parent
    if state is None:
        return
    initial._require(
        attempt.hooks_restored and (not state.observer_used or state.hooks_restored),
        "Post-SIM callbacks require restored inherited coverage",
        "observer",
    )
    folder = output / "SIM-reference"
    folder.mkdir(exist_ok=True)
    checks = (
        ("original_package", attempt.raw["original_package"].verify),
        ("process_log_lease", parent.raw["shared_writer_session"].check),
        ("filesystem_final_check", parent.raw["filesystem_audit"].check),
    )
    for label, check in checks:
        try:
            _metadata(attempt, label, check)
        except BaseException as error:
            if "metadata_coverage_unavailable" in attempt.raw:
                raise
            if state.primary is None:
                state.primary = error
            else:
                state.secondary.append((label, error))
    try:
        producer = plan["execution_source"]
        manifest = _metadata(
            attempt,
            "snapshot_after",
            snapshot.verify,
            ROOT,
            manifest_sha256=producer["snapshot_sha256"],
        )
        initial._require(
            all(
                manifest["files"][name]["sha256"]
                == pin
                == _metadata(attempt, "source_digest_after", snapshot.digest, ROOT / name)
                for name, pin in producer["owned_files"].items()
            ),
            "Post-SIM immutable source bindings changed",
            "source_after",
        )
        parent_plan = _metadata(
            attempt,
            "parent_preparation_after",
            initial._json_record,
            plan["INIT_prepared"]["path"],
            plan["INIT_prepared"]["sha256"],
        )
        selected = parent_plan["inputs"]
        initial._require(
            _metadata(
                attempt, "prepared_inputs_after", initial.inputs.inventory, Path(selected["root"])
            )
            == selected["inventory"],
            "Prepared input bytes changed during SIM",
            "input_after",
        )
        copied_pin = _metadata(
            attempt, "execution_record_digest", snapshot.digest, output / "execution-inputs.json"
        )
        copied = _metadata(
            attempt,
            "execution_record_after",
            initial._json_record,
            output / "execution-inputs.json",
            copied_pin,
        )
        initial._require(
            copied["source_root"] == selected["root"]
            and copied["inventory"] == selected["inventory"]
            and len(copied["files"]) == len(selected["inventory"]["files"])
            and {row["name"] for row in copied["files"]} == set(selected["inventory"]["files"]),
            "Post-SIM execution-copy association changed",
            "input_after",
        )
        for row in copied["files"]:
            name = str(snapshot.relative_path(row["name"]))
            initial._require(
                row["sha256"]
                == selected["inventory"]["files"][name]["sha256"]
                == _metadata(
                    attempt, "execution_input_after", snapshot.digest, output / "config" / name
                ),
                "Execution input bytes changed during SIM",
                "input_after",
            )
        _metadata(
            attempt,
            "source_input_record",
            snapshot.write_json,
            folder / "source-input-binding.json",
            dict(
                execution_source=producer,
                prepared_inputs=selected,
                execution_inputs=copied,
                native_producers=attempt.raw["original_package"].loaded,
            ),
        )
    except BaseException as error:
        if "metadata_coverage_unavailable" in attempt.raw:
            raise
        if state.primary is None:
            state.primary = error
        else:
            state.secondary.append(("SIM_source_input_binding", error))
    for label, action in (
        ("SIM_partial_capture", lambda: initial._retain_native(state, attempt.raw["SIM_archive"])),
        ("SIM_runtime", lambda: snapshot.write_json(folder / "runtime.json", runtime.inventory())),
        (
            "SIM_filesystem_record",
            lambda: snapshot.write_json(
                folder / "filesystem.json", parent.raw["filesystem_audit"].record()
            ),
        ),
    ):
        try:
            _metadata(attempt, label, action)
        except BaseException as error:
            if "metadata_coverage_unavailable" in attempt.raw:
                raise
            state.secondary.append((label, error))
            if state.capture_error is None:
                state.capture_error = error
    # A library can catch an audit rejection; check the sticky authority after
    # all capture/runtime callbacks too. The actual lease stays process-live.
    for label, check in checks:
        try:
            _metadata(attempt, "after_" + label, check)
        except BaseException as error:
            if "metadata_coverage_unavailable" in attempt.raw:
                raise
            if state.primary is None:
                state.primary = error
            else:
                state.secondary.append(("after_" + label, error))
    if state.primary is None and state.capture_error is None and state.source_returned:
        try:
            terminal = _metadata(attempt, "terminal_observation", _terminal_record, attempt)
            attempt.terminal_observation = _metadata(
                attempt,
                "terminal_observation_save",
                attempt.raw["SIM_archive"].save,
                "terminal",
                terminal,
            )
            observed = _metadata(attempt, "closed_lineage", _closed_lineage, attempt)
            attempt.closed_lineage = _metadata(
                attempt,
                "closed_lineage_save",
                attempt.raw["SIM_archive"].save,
                "closed_lineage",
                observed,
            )
            for label, check in checks:
                _metadata(attempt, "closed_" + label, check)
        except BaseException as error:
            if "metadata_coverage_unavailable" in attempt.raw:
                raise
            state.secondary.append(("SIM_closed_lineage", error))
            if state.capture_error is None:
                state.capture_error = error
    attempt.finalization_complete = (
        state.primary is None
        and state.capture_error is None
        and attempt.closed_lineage is not None
        and attempt.terminal_observation is not None
    )


def _release(plan, prepared_pin, release, release_pin, output, enabled):
    initial._require(
        enabled is True
        and os.environ.get(RELEASE) == "1"
        and all(
            initial._pin(p)
            for p in (SOURCE_REVIEW_SHA256, REFERENCE_REVIEW_SHA256, EXECUTION_REVIEW_SHA256)
        ),
        "Original SIM/reference/selected-caller execution remains held",
        "release",
    )
    value = initial._json_record(release, release_pin)
    initial._require(
        set(value)
        == {
            "kind",
            "prepared_sha256",
            "worker_output",
            "reviews",
            "init_release",
            "policy",
            "enabled",
        }
        and value["kind"] == "cells.original_SIM_reference_execution_release@1"
        and value["enabled"] is True
        and value["prepared_sha256"] == prepared_pin
        and value["worker_output"] == str(output)
        and value["policy"] == initial.NATIVE_POLICY,
        "Exact SIM execution release required",
        "release",
    )
    contracts = review_contracts()
    for name, expected in (
        ("source", SOURCE_REVIEW_SHA256),
        ("reference", REFERENCE_REVIEW_SHA256),
        ("execution", EXECUTION_REVIEW_SHA256),
    ):
        pin = value["reviews"][name]
        initial._require(pin["sha256"] == expected, "Unadopted SIM review", "release")
        initial._require(
            initial._json_record(pin["path"], pin["sha256"]) == contracts[name],
            "Reviewed SIM contract differs: " + name,
            "release",
        )
    return value


def review_contracts():
    return dict(
        source=dict(
            kind="cells.original_SIM_selected_source_review@1",
            original=source.source_plan(),
            reference_source=REFERENCE_SHA256,
            no_numerical_solver_or_flux_repair=True,
        ),
        reference=dict(
            kind="cells.original_SIM_INIT_predecessor_review@1",
            reference_source=REFERENCE_SHA256,
            internally_created_complete_INIT_only=True,
            external_data_or_owner_arguments=False,
            closed_package_never_rearmed=True,
        ),
        execution=dict(
            kind="cells.original_SIM_execution_policy_review@1",
            policy=dict(initial.NATIVE_POLICY),
            one_fresh_worker=True,
            max_SIM_iterations=MAX_SIM_ITERATIONS,
            complete_calendar_or_refusal=True,
            detached_supervision_required=True,
        ),
    )


def supervise(prepared, prepared_sha256, release, release_sha256, output, *, enabled=False):
    from validation.betse import betse_mesh_lifecycle_preparation_guard as guard

    output = initial._path(output)
    plan = initial._json_record(prepared, prepared_sha256, 16 * 2**20)
    _release(plan, prepared_sha256, release, release_sha256, output / "worker", enabled)
    initial._require(
        not output.exists() and output.is_relative_to(Path("/mnt/workspaces/Cells")),
        "Fresh contained guarded SIM output required",
    )
    output.mkdir(parents=True)
    directory = output / "process"
    directory.mkdir()
    result = guard.run_bounded(
        [
            sys.executable,
            "-B",
            "-m",
            "validation.betse.native_sim_reference",
            "--prepared",
            str(prepared),
            "--prepared-sha256",
            prepared_sha256,
            "--release",
            str(release),
            "--release-sha256",
            release_sha256,
            "--output",
            str(output / "worker"),
        ],
        directory=directory,
        cwd=ROOT,
        env=dict(os.environ),
        timeout=initial.NATIVE_POLICY["wall_seconds"],
        max_rss_bytes=initial.NATIVE_POLICY["max_rss_bytes"],
        min_available_bytes=initial.NATIVE_POLICY["reserve_bytes"],
    )
    snapshot.write_json(
        output / "result.json",
        dict(
            kind=KIND,
            status="completed",
            process=result,
            prepared_sha256=prepared_sha256,
            scientific_physical_checkpoint_credit=0,
        ),
    )
    return result


def evaluate(
    prepared, expected_sha256, output, *, release=None, release_sha256=None, enabled=False
):
    global _ATTEMPT
    attempt = Attempt(
        required_hooks=(sys.getprofile(), sys.gettrace()),
        controls=((sys.setprofile, sys.settrace), (sys.getprofile, sys.gettrace)),
    )
    output = initial._path(output)
    initial._require(not output.exists(), "Fresh SIM/reference output required")
    plan, prior, parent_called = None, initial._ATTEMPT, False
    setters, getters = (sys.setprofile, sys.settrace), (sys.getprofile, sys.gettrace)
    try:
        plan = initial._json_record(prepared, expected_sha256, 16 * 2**20)
        initial._require(
            plan["kind"] == KIND and plan["held"] is True and plan["source_plan"] == source_plan(),
            "Exact held SIM preparation required",
        )
        initial._require(
            snapshot.digest(Path(initial.__file__)) == REFERENCE_SHA256,
            "Reviewed INIT reference producer differs",
            "producer",
        )
        initial._require(
            _ATTEMPT is None, "SIM reference is one attempted continuation", "consumed"
        )
        _ATTEMPT = attempt
        authority = _release(plan, expected_sha256, release, release_sha256, output, enabled)
        manifest = snapshot.verify(
            ROOT, manifest_sha256=plan["execution_source"]["snapshot_sha256"]
        )
        initial._require(
            str(ROOT) == plan["execution_source"]["root"]
            and all(
                snapshot.digest(ROOT / name) == manifest["files"][name]["sha256"] == expected
                for name, expected in plan["execution_source"]["owned_files"].items()
            ),
            "Exact SIM source required",
        )
        initial._resources()
        parent = plan["INIT_prepared"]
        prior = initial._ATTEMPT
        attempt.stage = "fresh_original_INIT"
        parent_called = True
        attempt.parent_result = initial.evaluate(
            parent["path"],
            parent["sha256"],
            output,
            release=authority["init_release"]["path"],
            release_sha256=authority["init_release"]["sha256"],
            enabled=True,
        )
        attempt.parent, phase, package = _parent_state(attempt.parent_result, prior)
        attempt.raw.update(INIT_phase=phase, original_package=package)
        _continue(attempt, plan, output)
    except BaseException as error:
        actual = initial._ATTEMPT
        if parent_called and type(actual) is initial.State and actual is not prior:
            # Failed predecessors remain evidence, never successful authority.
            attempt.parent = actual
        state = attempt.sim
        attempt.primary = (
            state.primary
            if state is not None and state.primary is not None
            else attempt.parent.primary
            if attempt.parent is not None and attempt.parent.primary is not None
            else error
        )
        if attempt.primary is not error:
            attempt.secondary.append(("outer_SIM", error))
    finally:
        if attempt.imports is not None:
            try:
                sys.meta_path[:] = [item for item in sys.meta_path if item is not attempt.imports]
            except BaseException as error:
                attempt.secondary.append(("import_guard_cleanup", error))
        # A predecessor can raise before returning its State; a context exit
        # can also be rejected before cleanup starts. Restore both original
        # hooks independently, then sample both identities after all actions.
        for setter, previous, label in zip(
            setters,
            attempt.required_hooks,
            ("coordinator_profile_restore", "coordinator_trace_restore"),
            strict=True,
        ):
            try:
                setter(previous)
            except BaseException as error:
                attempt.secondary.append((label, error))
        final = []
        for getter, label in zip(
            getters, ("coordinator_profile_identity", "coordinator_trace_identity"), strict=True
        ):
            try:
                final.append(getter())
            except BaseException as error:
                final.append(object())
                attempt.secondary.append((label, error))
        attempt.hooks_restored = (
            final[0] is attempt.required_hooks[0] and final[1] is attempt.required_hooks[1]
        )
    if not attempt.hooks_restored or (
        attempt.sim is not None and "unretired_observer_manager" in attempt.sim.raw
    ):
        _RAW_FAILURES.append(attempt)
        if attempt.primary is not None:
            raise attempt.primary  # noqa: B904 - preserve the original source cause.
        raise initial.ReferenceRejected(
            "SIM observation hooks not restored", stage="observer", partial=attempt
        )
    state = attempt.sim
    if state is not None:
        try:
            _metadata(attempt, "SIM_forensic_boundary", _finish_sim, attempt, plan, output)
        except BaseException as error:
            attempt.secondary.append(("SIM_forensic_boundary", error))
            if state.capture_error is None:
                state.capture_error = error
        if attempt.primary is None:
            attempt.primary = state.primary if state.primary is not None else state.capture_error
    if "metadata_coverage_unavailable" in attempt.raw:
        _RAW_FAILURES.append(attempt)
        if attempt.primary is not None:
            raise attempt.primary
        raise attempt.coverage_stop
    try:
        # Directory creation, error rendering, dictionary construction and
        # publication are one protected boundary, not only write_json's body.
        _metadata(attempt, "result_directory", output.mkdir, parents=True, exist_ok=True)
        result = dict(
            kind=KIND,
            status="completed"
            if attempt.primary is None
            and attempt.finalization_complete
            and state is not None
            and state.source_returned
            and state.hooks_restored
            and not state.coverage_failed
            and not attempt.secondary
            else "failed",
            stage=attempt.stage,
            primary=_metadata(attempt, "primary_render", initial._error, attempt.primary),
            capture_errors=[
                dict(stage=n, error=_metadata(attempt, "secondary_render", initial._error, e))
                for n, e in tuple(attempt.secondary)
            ],
            INIT_result=attempt.parent_result,
            INIT_parent_consumed=attempt.parent_consumed,
            SIM_work=[] if state is None else state.work,
            SIM_sites=[]
            if state is None
            else [dict(site=list(k), counts=v) for k, v in state.sites.items()],
            SIM_iterations=[] if state is None else state.iterations,
            SIM_captures=[] if state is None else state.captures,
            SIM_capture_errors=[]
            if state is None
            else [
                dict(stage=n, error=_metadata(attempt, "SIM_secondary_render", initial._error, e))
                for n, e in tuple(state.secondary)
            ],
            inherited_hooks_restored=attempt.hooks_restored,
            SIM_source_returned=state is not None and state.source_returned,
            SIM_observer_coverage_failed=state is not None and state.coverage_failed,
            SIM_finalization_complete=attempt.finalization_complete,
            SIM_closed_lineage=attempt.closed_lineage,
            SIM_terminal_observation=attempt.terminal_observation,
            initial_rng_observation=None
            if attempt.parent_result is None
            else attempt.parent_result.get("initial_rng_observation"),
            raw_failed_objects_serialized_completely=False,
            ordinary_pickle_caller_checkpoint_physical_or_numerical_credit=0,
        )
        _metadata(
            attempt,
            "terminal_write",
            snapshot.write_json,
            output / "SIM-reference-result.json",
            result,
        )
        if (
            result["status"] == "completed"
            and state is not None
            and state.capture_error is not None
        ):
            raise state.capture_error
    except BaseException as error:
        attempt.secondary.append(("result_write", error))
        _RAW_FAILURES.append(attempt)
        if attempt.primary is not None:
            raise attempt.primary  # noqa: B904 - preserve the original source cause.
        raise
    if result["status"] != "completed":
        _RAW_FAILURES.append(attempt)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path)
    parser.add_argument("--prepared-sha256")
    parser.add_argument("--prepare", type=Path)
    parser.add_argument("--prepare-frozen", type=Path)
    parser.add_argument(
        "--input-pair", type=Path, help="Pinned input-pair directory containing inputs.json"
    )
    parser.add_argument("--input-sha256")
    parser.add_argument("--mode", choices=initial.MODES, default="original")
    parser.add_argument("--release", type=Path)
    parser.add_argument("--release-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.prepare or args.prepare_frozen:
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 512 * 2**20))
        if args.input_pair is None or args.input_sha256 is None:
            parser.error("Exact original input-pair pin required")
        function = prepare if args.prepare else prepare_frozen
        function(
            args.prepare or args.prepare_frozen,
            input_pair=args.input_pair,
            input_sha256=args.input_sha256,
            mode=args.mode,
        )
        return 0
    if args.prepared is None or args.prepared_sha256 is None or args.output is None:
        parser.error("Choose held preparation or exact released worker inputs")
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    result = evaluate(
        args.prepared,
        args.prepared_sha256,
        args.output,
        release=args.release,
        release_sha256=args.release_sha256,
        enabled=os.environ.get(RELEASE) == "1",
    )
    return int(result["status"] != "completed")


if __name__ == "__main__":
    raise SystemExit(main())
