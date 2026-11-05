"""Held genuine INIT-to-SIM orchestration inside the existing demonstration.

This module issues no scientific owner. Every phase, parameter and completed
run comes from the original public producers; saved evidence is never input
authority. Source/review adoption is explicit and remains separate from release.
"""

import contextlib
import importlib
import struct
import sys
from pathlib import Path
from types import CodeType, FunctionType, ModuleType

from validation import source_snapshot as snapshot
from validation.betse import native_seed_demo as demo
from validation.betse import native_sim_demo_observation as observation

ROOT = Path(__file__).resolve().parents[2]
FILE = "validation/betse/native_sim_demo.py"
ENDPOINT = "sim_terminal"
MAX_ITERATIONS = 512
MODULES = {
    "preparation": "cells.processes.betse_native_init_sim_preparation",
    "assembly": "cells.processes.betse_native_init_sim_assembly",
    "run": "cells.processes.betse_native_sim_run",
}
SOURCE_PINS = dict.fromkeys(MODULES)
REVIEW_PINS = dict.fromkeys(MODULES)
IMPORTS = (
    ("preparation", "observing_runner_import"),
    ("assembly", "observing_phase_import"),
    ("run", "observing_runtime_import"),
)
PUBLIC = {
    "preparation": ("from_init", "prepare", "trial_record", "_entry_guard"),
    "assembly": ("from_preparation", "prepare", "record_document"),
    "run": ("from_assembly", "prepare", "record_document", "completed_sim", "validate_sim"),
}
PARAMETER_PUBLIC = ("acquire_world_ready", "acquire_current_world_ready")
STAGES = ("current_parameters", "sim_preparation", "sim_assembly", "sim_run")
ACQUISITION_SEQUENCE = ("initial_world_ready", "fresh_current_world_ready")


def source_plan():
    return dict(
        kind="cells.actual_complete_INIT_to_complete_SIM_orchestration@1",
        stages=STAGES,
        modules=dict(MODULES),
        source_pins=dict(SOURCE_PINS),
        review_pins=dict(REVIEW_PINS),
        imports=IMPORTS,
        acquisition_sequence=ACQUISITION_SEQUENCE,
        maximum_iterations=MAX_ITERATIONS,
        complete_configured_calendar=True,
        selected_iteration_count=False,
        same_retained_simulator_and_cells=True,
        distinct_fresh_loaded_parameters_and_SIM_phase=True,
        original_operator_mode_retained=True,
        flux_repair=False,
        starts_after="actual complete INIT with normal loop/context return",
        stops_before="native pickle/checkpoint",
        import_observation="actual fresh callback/bootstrap import; never replayed",
        saved_objects_or_partial_loops_are_not_parent_authority=True,
        source_library_metadata_work_is_non_additive=True,
        scientific_common_start_or_physical_parity_admission=False,
        completed_observation=observation.declaration(),
    )


def preflight():
    if (
        set(SOURCE_PINS) != set(MODULES)
        or set(REVIEW_PINS) != set(MODULES)
        or not all(demo._pin(value) for value in (*SOURCE_PINS.values(), *REVIEW_PINS.values()))
    ):
        raise demo.DemoRejected(
            "Actual complete SIM producers remain unadopted", stage="sim_unbound"
        )
    files = {}
    for key, name in MODULES.items():
        relative = demo._relative(name)
        path = ROOT / relative
        if path.is_symlink() or not path.is_file() or snapshot.digest(path) != SOURCE_PINS[key]:
            raise demo.DemoRejected("Actual SIM source changed: " + key, stage="producer")
        files[relative] = SOURCE_PINS[key]
    files.update(observation.preflight(SOURCE_PINS["run"]))
    return files


def _modules():
    preflight()
    result = {}
    for key, name in MODULES.items():
        module = importlib.import_module(name)
        path = ROOT / demo._relative(name)
        if sys.modules.get(name) is not module or Path(module.__file__).resolve() != path:
            raise ValueError("Actual frozen SIM producer origin required")
        if snapshot.digest(path) != SOURCE_PINS[key]:
            raise ValueError("SIM producer changed during import")
        _original_apis(
            module, PUBLIC[key], guarded=("from_init", "prepare") if key == "preparation" else ()
        )
        result[key] = module
    return result


def _original_apis(module, names, *, guarded=()):
    """Compile metadata only; no replacement function or source body is run."""
    path = Path(module.__file__)
    raw = path.read_bytes()
    codes = {
        value.co_name: value
        for value in compile(raw, str(path), "exec", dont_inherit=True).co_consts
        if type(value) is CodeType
    }
    for name in names:
        function = demo._function(module, name)
        if name in guarded:
            factory = demo._function(module, "_entry_guard")
            nested = tuple(
                value
                for value in codes["_entry_guard"].co_consts
                if type(value) is CodeType and value.co_name == "guarded"
            )
            inner = vars(function).get("__wrapped__")
            if (
                factory.__code__ != codes["_entry_guard"]
                or factory.__closure__ is not None
                or factory.__defaults__ is not None
                or factory.__kwdefaults__ is not None
                or len(nested) != 1
                or function.__code__ != nested[0]
                or function.__defaults__ is not None
                or function.__kwdefaults__ is not None
                or type(inner) is not FunctionType
                or inner.__globals__ is not vars(module)
                or function.__closure__ is None
                or len(function.__closure__) != 1
                or function.__code__.co_freevars != ("function",)
                or function.__closure__[0].cell_contents is not inner
            ):
                raise ValueError("Original SIM entry exclusion wrapper changed: " + name)
            function = inner
        expected = {"enabled": False} if name in ("prepare", *PARAMETER_PUBLIC) else None
        if (
            function.__code__ != codes.get(name)
            or function.__closure__ is not None
            or function.__defaults__ is not None
            or function.__kwdefaults__ != expected
            or expected is not None
            and (
                type(function.__kwdefaults__) is not dict
                or function.__kwdefaults__["enabled"] is not False
            )
        ):
            raise ValueError("Original SIM public entry changed: " + name)


def _parameter_api(module):
    path = ROOT / demo._relative(demo.MODULES["parameters"])
    if (
        type(module) is not ModuleType
        or Path(module.__file__).resolve() != path
        or path.is_symlink()
        or snapshot.digest(path) != demo.SOURCE_PINS["parameters"]
        or sys.modules.get(demo.MODULES["parameters"]) is not module
    ):
        raise ValueError("Same accepted fresh-parameter public producer required")
    _original_apis(module, PARAMETER_PUBLIC)
    return module


def bind_parameters(state, module):
    _check_apis(state)
    if "parameters" in state.sim_apis:
        raise ValueError("Parameter APIs must bind before the first acquisition exactly once")
    state.sim_apis["parameters"] = _parameter_api(module)
    state.sim_api_bindings = _api_atoms(state.sim_apis)


def _api_atoms(modules):
    result = []
    roster = dict(PUBLIC)
    if "parameters" in modules:
        roster["parameters"] = PARAMETER_PUBLIC
    for key, names in roster.items():
        module = modules[key]
        if type(module) is not ModuleType:
            raise ValueError("Actual retained SIM API module required")
        result.extend((module, vars(module).get("LAW_ID")))
        for name in names:
            function = vars(module).get(name)
            if type(function) is not FunctionType:
                raise ValueError("Original SIM public function required: " + name)
            seen = set()
            while function is not None:
                if type(function) is not FunctionType or id(function) in seen or len(seen) > 1:
                    raise ValueError("Exact bounded public wrapper/delegate chain required")
                seen.add(id(function))
                result.extend(
                    (
                        function,
                        function.__code__,
                        function.__globals__,
                        function.__defaults__,
                        function.__kwdefaults__,
                        function.__closure__,
                    )
                )
                if function.__defaults__ is not None:
                    result.extend(function.__defaults__)
                if function.__kwdefaults__ is not None:
                    for key in sorted(function.__kwdefaults__):
                        result.extend((key, function.__kwdefaults__[key]))
                if function.__closure__ is not None:
                    for cell in function.__closure__:
                        result.extend((cell, cell.cell_contents))
                function = vars(function).get("__wrapped__")
                result.append(function)
    return tuple(result)


def _check_apis(state):
    current = _api_atoms(state.sim_apis)
    retained = state.sim_api_bindings
    if (
        retained is None
        or len(current) != len(retained)
        or any(a is not b for a, b in zip(current, retained, strict=True))
    ):
        raise ValueError("Actual SIM public API changed after acquisition")


def _invoke(state, role, name, label, *args, **kwargs):
    function = vars(state.sim_apis[role]).get(name)
    _check_apis(state)
    value = demo._call(state, label, function, *args, **kwargs)
    _check_apis(state)
    return value


def acquire_initial(state, plan, directory):
    return _invoke(
        state,
        "parameters",
        "acquire_world_ready",
        "parameters",
        plan["parameter_packet"],
        directory / "parameters",
        packet_sha256=plan["parameter_sha256"],
        enabled=True,
    )


def _error(state, stage, error):
    if state.primary is None:
        state.primary = error
    elif state.primary is not error:
        state.sim_secondary += ((stage, error),)


def _import_binding(module, name):
    """Authenticate the actual public contextmanager and its original body."""
    if type(module) is not ModuleType:
        raise ValueError("Actual SIM import producer module required")
    path = Path(module.__file__)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Regular SIM import source required")
    raw = path.read_bytes()
    compiled = compile(raw, str(path), "exec", dont_inherit=True)
    originals = tuple(
        value for value in compiled.co_consts if type(value) is CodeType and value.co_name == name
    )
    wrapper = vars(module).get(name)
    inner = vars(wrapper).get("__wrapped__") if type(wrapper) is FunctionType else None
    helper = next(
        value
        for value in contextlib.contextmanager.__code__.co_consts
        if type(value) is CodeType and value.co_name == "helper"
    )
    if (
        len(originals) != 1
        or type(wrapper) is not FunctionType
        or wrapper.__code__ is not helper
        or wrapper.__globals__ is not vars(contextlib)
        or wrapper.__defaults__ is not None
        or wrapper.__kwdefaults__ is not None
        or type(inner) is not FunctionType
        or inner.__globals__ is not vars(module)
        or inner.__code__ != originals[0]
        or inner.__defaults__ is not None
        or type(inner.__kwdefaults__) is not dict
        or set(inner.__kwdefaults__) != {"enabled"}
        or inner.__kwdefaults__["enabled"] is not False
        or inner.__closure__ is not None
        or wrapper.__closure__ is None
        or len(wrapper.__closure__) != 1
        or wrapper.__closure__[0].cell_contents is not inner
    ):
        raise ValueError("Exact original SIM import contextmanager required")
    return (
        wrapper,
        inner,
        inner.__code__,
        inner.__kwdefaults__,
        wrapper.__closure__,
        wrapper.__closure__[0],
        snapshot.digest(path),
    )


def _check_import_binding(row):
    current = _import_binding(row["module"], row["name"])
    retained = row["binding"]
    if any(a is not b for a, b in zip(current[:-1], retained[:-1], strict=True)) or (
        current[-1] != retained[-1]
    ):
        raise ValueError("Actual SIM import binding changed during callback")


def _restore(state, hooks, label):
    """Restore both inherited hooks independently before any further metadata."""
    failures = []
    for setter, value in ((sys.setprofile, hooks[0]), (sys.settrace, hooks[1])):
        try:
            setter(value)
        except BaseException as error:
            failures.append(error)
    samples = []
    for order in ((0, 1), (1, 0)):
        values = [None, None]
        for index in order:
            try:
                values[index] = (sys.getprofile, sys.gettrace)[index]()
            except BaseException as error:
                failures.append(error)
        samples.append(tuple(values))
    restored = all(row[0] is hooks[0] and row[1] is hooks[1] for row in samples)
    state.sim_hook_samples += ((label, tuple(samples)),)
    state.sim_cleanup_errors += tuple((label, error) for error in failures)
    if failures or not restored:
        state.sim_metadata_stopped = True
        for error in failures:
            _error(state, label, error)
        if not restored and not failures:
            _error(state, label, ValueError("Exact inherited SIM import hooks unavailable"))
    return restored and not failures


def _proof(row):
    proof = row.get("proof")
    if proof is None:
        generator = row.get("generator")
        frame = None if generator is None else generator.gi_frame
        if frame is not None:
            # These are the actual public generators' local names, not supplied
            # contexts or a forged suspended frame.
            proof = frame.f_locals.get("proof", frame.f_locals.get("context"))
            row["partial_proof"] = proof
    return proof


def _closed_import(row):
    proof = row.get("proof")
    if (
        row.get("entered") is not True
        or row.get("exited") is not True
        or row["generator"].gi_frame is not None
        or proof is None
        or proof.active is not False
        or proof.published is not True
        or proof.primary is not None
        or proof.capture_error is not None
        or proof.hooks_restored is not True
        or proof.monitor_restored is not True
    ):
        raise ValueError("Successful actual SIM import observation and cleanup required")


def bootstrap(state, molecule, callback, plan, directory, evidence):
    """Observe three distinct original import rosters around the actual callback."""
    if state.endpoint != ENDPOINT or state.sim_imports:
        raise ValueError("One explicit fresh SIM bootstrap required")
    observation.bind(state, SOURCE_PINS["run"])
    modules = state.sim_apis = _modules()
    state.sim_api_bindings = _api_atoms(modules)
    hooks = state.sim_import_hooks = (sys.getprofile(), sys.gettrace())
    state.sim_imports_complete = False
    primary, traceback = None, None
    try:
        for key, name in IMPORTS:
            api = modules[key]
            binding = _import_binding(api, name)
            factory, inner = binding[:2]
            row = dict(
                role=key,
                module=api,
                name=name,
                binding=binding,
                factory=factory,
                inner=inner,
                entered=False,
                exited=False,
            )
            state.sim_imports.append(row)
            manager = row["manager"] = demo._call(
                state, "sim_imports." + key + ".factory", factory, enabled=True
            )
            generator = row["generator"] = manager.gen
            if (
                type(manager) is not contextlib._GeneratorContextManager
                or generator.gi_code is not inner.__code__
                or generator.gi_frame is None
                or generator.gi_frame.f_globals is not vars(api)
            ):
                raise ValueError("Actual public SIM import manager required")
            row["proof"] = demo._call(
                state, "sim_imports." + key + ".enter", type(manager).__enter__, manager
            )
            row["entered"] = True
            if sys.getprofile() is not hooks[0] or sys.gettrace() is not hooks[1]:
                raise ValueError("SIM import entry changed inherited hooks")
        demo._callback_with_imports(state, molecule, callback, plan, directory, evidence)
    except BaseException as error:
        primary, traceback = error, error.__traceback__
        if state.primary is None:
            state.primary = error
        try:
            _error(state, "sim_imports", error)
        except BaseException as secondary:
            state.sim_cleanup_errors += (("error_retention", secondary),)
    finally:
        for row in reversed(state.sim_imports):
            try:
                _proof(row)
            except BaseException as error:
                state.sim_cleanup_errors += (("partial_import", error),)
                if state.primary is None:
                    state.primary = error
            manager, generator = row.get("manager"), row.get("generator")
            if manager is None or generator is None:
                continue
            try:
                restored = _restore(state, hooks, "before_exit:" + row["role"])
            except BaseException as error:
                restored = False
                state.sim_metadata_stopped = True
                state.sim_cleanup_errors += (("restore_entry", error),)
                if state.primary is None:
                    state.primary = error
            if restored and row.get("entered") is True:
                try:
                    _check_import_binding(row)
                except BaseException as error:
                    if state.primary is None:
                        state.primary = error
                    try:
                        _error(state, "sim_imports.binding", error)
                    except BaseException as secondary:
                        state.sim_cleanup_errors += (("binding_retention", secondary),)
                # Binding/error observers can themselves clear an inherited
                # hook on call/return rejection. Reconfirm at the actual exit
                # boundary, rather than relying on the earlier restoration.
                try:
                    restored = _restore(state, hooks, "at_exit:" + row["role"])
                except BaseException as error:
                    restored = False
                    state.sim_metadata_stopped = True
                    state.sim_cleanup_errors += (("exit_restore_entry", error),)
                    if state.primary is None:
                        state.primary = error
                # Cleanup errors in an inner context must also unwind the outer
                # import contexts as failures; they cannot publish successful proof.
                if primary is None and state.primary is not None:
                    primary, traceback = state.primary, state.primary.__traceback__
                if restored and not state.sim_metadata_stopped:
                    try:
                        value = type(manager).__exit__(
                            manager, None if primary is None else type(primary), primary, traceback
                        )
                        row["exit_return"] = value
                        row["exited"] = True
                        if value is not False:
                            raise ValueError("SIM import manager may not suppress source failure")
                    except BaseException as error:
                        row["exit_error"] = error
                        if state.primary is None:
                            state.primary = error
                        else:
                            state.sim_secondary += (("sim_imports.exit", error),)
            # An enter/return observer may fail after the underlying generator
            # yielded. Close that exact generator under restored hooks; no new
            # factory or source import is performed during recovery.
            try:
                restored = _restore(state, hooks, "before_close:" + row["role"])
            except BaseException as error:
                restored = False
                state.sim_metadata_stopped = True
                state.sim_cleanup_errors += (("close_restore_entry", error),)
                if state.primary is None:
                    state.primary = error
            if generator.gi_frame is not None and restored:
                try:
                    generator.close()
                except BaseException as error:
                    state.sim_cleanup_errors += (("generator_close", error),)
                    if state.primary is None:
                        state.primary = error
        try:
            restored = _restore(state, hooks, "final")
        except BaseException as error:
            restored = False
            state.sim_metadata_stopped = True
            state.sim_cleanup_errors += (("final_restore_entry", error),)
            if state.primary is None:
                state.primary = error
        state.sim_cleanup_complete = (
            restored
            and not state.sim_cleanup_errors
            and all(
                row.get("generator") is None or row["generator"].gi_frame is None
                for row in state.sim_imports
            )
        )
    demo._stop(state)
    if not state.sim_cleanup_complete or state.sim_metadata_stopped:
        raise ValueError("Incomplete SIM import cleanup")
    for row in state.sim_imports:
        _check_import_binding(row)
        _closed_import(row)
    _check_apis(state)
    state.sim_imports_complete = True
    demo._capture(
        state,
        evidence,
        "sim_imports",
        tuple(
            dict(
                role=row["role"],
                proof_identity=id(row["proof"]),
                record_identity=id(row["proof"].record),
                entered=True,
                exited=True,
                published=True,
                actual_import_not_replayed=True,
            )
            for row in state.sim_imports
        ),
    )


def _retain_trial(state, evidence, label, owner, module):
    state.owners.append((label, owner))
    trial = owner.trial
    state.last_trial = trial
    # Capture failures must not lose a successfully returned original trial.
    setattr(
        state,
        {
            "sim_preparation": "sim_preparation_trial",
            "sim_assembly": "sim_assembly_trial",
            "sim_run": "sim_trial",
        }[label],
        trial,
    )
    state.trials.append((label, trial))
    if not demo._pin(trial.identity):
        raise ValueError("Actual sealed SIM stage identity required")
    if label == "sim_preparation" and trial.source_completed is not True:
        raise ValueError("Actual successful SIM preparation/constructor required")
    if label == "sim_assembly" and trial.constructor_completed is not True:
        raise ValueError("Actual successful whole SIM constructor required")
    role = {"sim_preparation": "preparation", "sim_assembly": "assembly", "sim_run": "run"}[label]
    document = _invoke(
        state,
        role,
        "trial_record" if role == "preparation" else "record_document",
        label + ".record",
        trial,
    )
    demo._capture(state, evidence, label + ".record", dict(identity=trial.identity, **document))
    return trial


def execute(state, modules, plan, directory, evidence, init_owner):
    """Advance one actual complete INIT through genuine fresh Parameters and SIM."""
    if (
        state.endpoint != ENDPOINT
        or state.init_terminal_completed is not True
        or state.terminal_trial is None
        or state.terminal_trial.source_completed is not True
        or state.terminal_trial.loop_returned is not True
        or state.terminal_trial.context_returned is not True
        or state.terminal_trial.selected_stop is not False
        or state.sim_imports_complete is not True
        or state.sim_cleanup_complete is not True
        or state.sim_metadata_stopped
        or state.sim_completed
    ):
        raise ValueError("Actual complete INIT and fresh original import histories required")
    apis = state.sim_apis
    if apis is None or set(apis) != {*MODULES, "parameters"}:
        raise ValueError("Same retained actual SIM APIs required")
    _check_apis(state)
    state.sim_init_owner = init_owner
    state.sim_init_trial = state.terminal_trial
    old_p, cells, sim, _dyna, callbacks, _cache = state.init_links
    if state.parameters is not old_p or state.phase is not state.init_phase:
        raise ValueError("Original completed INIT phase/Parameters association required")
    if modules["parameters"] is not apis["parameters"]:
        raise ValueError("Original acquired parameter module association changed")
    pair = _invoke(
        state,
        "parameters",
        "acquire_current_world_ready",
        "current_parameters",
        plan["parameter_packet"],
        directory / "current_parameters",
        packet_sha256=plan["parameter_sha256"],
        previous_owner=state.world_ready,
        previous_parameters=old_p,
        enabled=True,
    )
    state.sim_current_pair = pair
    if type(pair) is not tuple or len(pair) != 2:
        raise ValueError("Actual distinct current parameter pair required")
    current_owner, current_p = pair
    if (
        current_owner is state.world_ready
        or current_p is old_p
        or current_owner.parameters is not current_p
    ):
        raise ValueError("Distinct genuine complete current Parameters required")
    state.sim_current_parameters = current_p
    api = apis["preparation"]
    request = _invoke(
        state,
        "preparation",
        "from_init",
        "sim_preparation_request",
        init_owner,
        current_parameters_owner=current_owner,
        law_id=api.LAW_ID,
    )
    state.requests.append(("sim_preparation", request))
    owner = _invoke(state, "preparation", "prepare", "sim_preparation", request, enabled=True)
    state.sim_preparation_trial = _retain_trial(state, evidence, "sim_preparation", owner, api)
    api = apis["assembly"]
    request = _invoke(
        state, "assembly", "from_preparation", "sim_assembly_request", owner, law_id=api.LAW_ID
    )
    state.requests.append(("sim_assembly", request))
    owner = _invoke(state, "assembly", "prepare", "sim_assembly", request, enabled=True)
    state.sim_assembly_trial = _retain_trial(state, evidence, "sim_assembly", owner, api)
    if (
        state.sim_assembly_trial.terminal_identity != state.sim_init_trial.identity
        or state.sim_assembly_trial.preparation_identity != state.sim_preparation_trial.identity
        or state.sim_assembly_trial.parameters_identity
        != state.sim_preparation_trial.parameters_identity
    ):
        raise ValueError("Actual preparation/constructor/INIT parameter lineage required")
    api = apis["run"]
    request = _invoke(
        state,
        "run",
        "from_assembly",
        "sim_run_request",
        owner,
        maximum=MAX_ITERATIONS,
        law_id=api.LAW_ID,
    )
    state.requests.append(("sim_run", request))
    count = request.iterations
    if (
        type(count) is not int
        or not 1 <= count <= MAX_ITERATIONS
        or type(current_p.sim_tsteps) is not int
        or count != current_p.sim_tsteps
        or request.maximum != MAX_ITERATIONS
        or type(request.maximum) is not int
        or request.operator_mode != demo.HISTORY_OPERATOR_MODES[state.flux_operator]
        or request.init_identity != state.sim_init_trial.identity
        or request.assembly_identity != state.sim_assembly_trial.identity
        or request.parameters_identity != state.sim_assembly_trial.parameters_identity
    ):
        raise ValueError("Entire original SIM calendar/operator/INIT lineage required")
    owner = _invoke(state, "run", "prepare", "sim_run", request, enabled=True)
    trial = state.sim_trial = _retain_trial(state, evidence, "sim_run", owner, api)
    surface = _invoke(state, "run", "completed_sim", "sim_completed", owner)
    state.sim_surface = surface
    phase = surface["phase"]
    if (
        surface["owner"] is not owner
        or surface["trial"] is not trial
        or surface["completed_INIT"] is not state.sim_init_trial
        or surface["constructor"] is not state.sim_assembly_trial
        or surface["old_p"] is not old_p
        or surface["current_p"] is not current_p
        or surface["sim"] is not sim
        or surface["cells"] is not cells
        or surface["callback"] is not callbacks
        or phase is state.init_phase
        or phase.p is not current_p
        or phase.sim is not sim
        or phase.cells is not cells
        or phase.callbacks is not callbacks
        or surface["before_native_pickle"] is not True
        or surface["operator_mode"] != request.operator_mode
        or trial.report_returned is not True
        or trial.loop_returned is not True
        or trial.context_returned is not True
        or trial.before_native_pickle is not True
        or type(trial.iterations) is not tuple
        or len(trial.iterations) != count
        or trial.request_identity != request.identity
        or trial.assembly_identity != state.sim_assembly_trial.identity
        or trial.init_identity != state.sim_init_trial.identity
        or trial.current_parameters_identity != request.parameters_identity
        or trial.operator_mode != request.operator_mode
    ):
        raise ValueError("Actual complete same-tissue/Simulator SIM lineage required")
    state.sim_phase = phase
    work_end = 0
    for ordinal, row in enumerate(trial.iterations):
        if (
            type(row.ordinal) is not int
            or row.ordinal != ordinal
            or type(row.sampled) is not bool
            or type(row.work_end) is not int
            or not work_end <= row.work_end <= len(trial.work)
        ):
            raise ValueError("Ordered original SIM iteration/time/work witness required")
        work_end = row.work_end
        demo._capture(state, evidence, f"sim_run.iteration.{ordinal:04d}.after", row.after)
        demo._capture(state, evidence, f"sim_run.iteration.{ordinal:04d}.rng", row.rng)
    for label, value in (
        ("before", trial.before),
        ("ready", trial.ready[0]),
        ("after", trial.after[0]),
        ("calendar", trial.calendar),
        ("sampled", trial.sampled),
        ("configured_dt", trial.dt),
        ("stream_before", trial.rng_before),
        ("stream_after", trial.rng_after),
    ):
        demo._capture(state, evidence, "sim_run." + label, value)
    linkage = dict(
        trial_identity=trial.identity,
        request_identity=request.identity,
        completed_INIT_identity=state.sim_init_trial.identity,
        constructor_identity=state.sim_assembly_trial.identity,
        current_parameters_identity=trial.current_parameters_identity,
        configured_iterations=count,
        maximum_iterations=MAX_ITERATIONS,
        configured_dt_bits=struct.pack("!d", trial.dt).hex(),
        operator_mode=request.operator_mode,
        complete_configured_calendar=True,
        selected_stop=False,
        report_returned=True,
        loop_returned=True,
        context_returned=True,
        before_native_pickle=True,
        same_retained_simulator_and_cells=True,
        distinct_current_parameters=True,
        source_library_metadata_work_is_non_additive=True,
        native_pickle_checkpoint_or_physical_admission=False,
    )
    state.sim_linkage = linkage
    demo._capture(state, evidence, "sim_run.linkage", linkage)
    if _invoke(state, "run", "validate_sim", "sim_final_check", owner) is not trial:
        raise ValueError("Same completed SIM trial required after final capture")
    try:
        demo._call(
            state,
            "sim_observation",
            observation.observe,
            state,
            owner,
            Path(directory) / "sim_observation",
            trial,
            state.flux_operator,
        )
    except BaseException as error:
        context = state.sim_observation
        if context is not None and context.primary is not None:
            if error is not context.primary:
                state.sim_secondary += (("observation_escape", error),)
            state.primary = state.delegate_error = context.primary
            raise context.primary  # noqa: B904 -- Original source/observer cause stays exact.
        raise
    if _invoke(state, "run", "validate_sim", "sim_observation_final_check", owner) is not trial:
        raise ValueError("Same completed SIM trial required after observation publication")
    observation.finish(state, trial, state.flux_operator)
    state.sim_time_steps_completed, state.sim_completed = count, True
    return owner


def failure_evidence(state, evidence):
    """Independent retained values only; no stale owner, fresh RNG or source read."""
    if state.primary is None or state.sim_metadata_stopped or not state.sim_cleanup_complete:
        return
    # Individual retained observations can be saved even if another field has
    # no wire encoding. Live owner graphs/frames are retained in Execution and
    # the original exception; this does not claim complete serialization.
    rows = [("linkage", state.sim_linkage)]
    for prefix, trial in (
        ("INIT", state.sim_init_trial),
        ("preparation", state.sim_preparation_trial),
        ("assembly", state.sim_assembly_trial),
        ("run", state.sim_trial),
    ):
        if trial is None:
            continue
        for field in (
            "identity",
            "before",
            "ready",
            "after",
            "calendar",
            "sampled",
            "dt",
            "rng_before",
            "rng_after",
        ):
            try:
                value = getattr(trial, field, None)
                rows.append((prefix + "." + field, value))
            except BaseException as error:
                state.sim_secondary += (("failure_field:" + prefix + "." + field, error),)
    try:
        state.sim_failure_partial = getattr(state.delegate_error, "partial", None)
    except BaseException as error:
        state.sim_secondary += (("failure_partial", error),)
    partial = state.sim_failure_partial
    if partial is not None:
        for field in (
            "before",
            "ready",
            "after",
            "calendar",
            "sampled",
            "source_error",
            "primary",
            "capture_errors",
            "cleanup_errors",
        ):
            try:
                rows.append(("partial." + field, getattr(partial, field, None)))
            except BaseException as error:
                state.sim_secondary += (("failure_partial_field:" + field, error),)
    for name, value in rows:
        if value is None:
            continue
        try:
            if not evidence.save("sim_failure." + name, value):
                raise ValueError("SIM retained failure observation unavailable: " + name)
        except BaseException as error:
            state.sim_secondary += (("failure_capture:" + name, error),)
