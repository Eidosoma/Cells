"""One-process genuine SEED demonstration, through core, profiles and junctions.

This is orchestration of existing public issuers, not a new scientific owner.
Every live parent is born in this process. Saved evidence cannot supply a
parameter, callback, phase, mesh, operator or material state. Optional INIT setup
retains the actual Cells and parameters in a fresh INIT phase. Its optional
dynamics prelude continues on that same phase, stopping before profile remapping
and random draws. None of these endpoints claims time evolution or restart parity.
"""

import argparse
import fcntl
import importlib
import json
import os
import resource
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import FunctionType

from validation import source_snapshot as snapshot

ROOT = Path(__file__).resolve().parents[2]
BASE = Path("/mnt/workspaces/Cells")
FILE = "validation/betse/native_seed_demo.py"
TEST = "tests/unit/test_native_seed_demo.py"
RUNNER = "validation/betse/native_seed_demo_software.py"
INPUT_METADATA = "validation/betse/native_seed_demo_inputs.py"
INPUT_METADATA_SHA256 = "4f6c5f5ec30825484fe3ec8fbae1da9ea217b8368bf3d27619f298486ba0a053"
EVIDENCE_MODULE = "validation.betse.native_seed_demo_evidence"
EVIDENCE_SOURCE_SHA256 = "e3b5228e3622b6baeaa27fd322008ec61c251f477f406dfe38f26f1f875ab4b6"
RELEASE = "CELLS_NATIVE_SEED_DEMO_RELEASED"
KIND = "cells.genuine_seed_core_profiles_junctions_demo@3"
FLUX_MODES = ("original", "disabled")
ENDPOINTS = ("seed", "init_setup", "init_prelude")
INIT_MODULES = {
    "init_setup": "cells.processes.betse_native_init_retained_world",
    "init_parameters": "cells.processes.betse_native_parameter_seed_init_transition",
}
INIT_SOURCE_PINS = dict.fromkeys(INIT_MODULES)
INIT_REVIEW_PINS = dict.fromkeys(INIT_MODULES)
PRELUDE_MODULES = {"init_prelude": "cells.processes.betse_native_init_dynamics_prelude"}
PRELUDE_SOURCE_PINS = dict.fromkeys(PRELUDE_MODULES)
PRELUDE_REVIEW_PINS = dict.fromkeys(PRELUDE_MODULES)
POLICY = dict(cpu=0, threads=1, max_rss_bytes=2**30, wall_seconds=7200, reserve_bytes=8 * 2**30)
MODULES = {
    "callback": "validation.betse.native_seed_world_callback_prelude",
    "parameters": "validation.betse.betse_native_parameter_world_ready_qualification",
    "geometry": "validation.betse.native_seed_world_geometry_qualification",
    "poisson": "cells.processes.betse_native_seed_world_poisson",
    "core": "cells.processes.betse_native_seed_init_core",
    "profiles": "cells.processes.betse_native_seed_init_profiles",
    "junctions": "cells.processes.betse_native_seed_junctions",
}
SOURCE_PINS = {
    "callback": "267cd6fe57807468128bd684b9fbc7af75770e66f1aa1cfc7c66bf71684c62ee",
    "parameters": "9ab32160019edaa0ab0fa49bf8ae64fbe1cb4baba87ff1bd99d16e9f978b07a7",
    "geometry": "d1e6d47e684e0b413689b4899bbd912b13fd7499fa3907d29928205f11746e2f",
    "poisson": "39539d52b750fd75787a2897efc564ad4ca886381ab09acf1560159aa815ba33",
    "core": "96ebd0104a4a5ba2a05f3ab959c25a3046ef6e1019f08e4e9f7fef2240e8e419",
    "profiles": "3d1b0987ec7c823a61e3d0baa343f5a6ab9c93f513a0f7deea58362cffda4c29",
    "junctions": "862ecdd970034b6e039b4038ca768266faa74e07e0154e4f55dba27e987457c0",
}
REVIEW_PINS = {
    "callback": "cc2ba3a07cb2177e6b6ba6c0190009f9f03086bdb4a33bd3c7d2f4ef00f9d967",
    "parameters": "e0e3a4270321ffbd08f2ce14dfdb2c39b7d0108d0e90741c7a509586fd3f0604",
    "geometry": "aa5cddf4c36998d3a99bcc576af94ba6fb4993c020de402bdd6ae8b134613f6e",
    "poisson": "a4fd24cebcb04930a7d4d884a18b0e2368020510d7d57e6be72f4b213cad1bbb",
    "core": "b3d3aa390a6238d8eb0236dac6ee29af6f3877fd4d4e80df19d48ba62acc882d",
    "profiles": "b3d3aa390a6238d8eb0236dac6ee29af6f3877fd4d4e80df19d48ba62acc882d",
    "junctions": "a9f6d6fa62d2eb5e46cf903546f754b2c8eb204b216343f8cb7bf4752ac85bba",
}
# Root's release must coordinate all native log writers. Advisory locking alone
# cannot establish the absence of writers that do not use this protocol.
SESSION_REVIEW_SHA256 = "2f6b64bb8cfb7a7eb70f203e51f1444849d7c0ed19adc580b02d044b1c799af0"
STAGES = ("callback", "parameters", "geometry", "poisson", "core", "profiles", "junctions")
_ACTIVE = []
_ATTEMPT = None
_PROCESS_LEASES = []


class DemoRejected(ValueError):
    def __init__(self, message, *, stage, partial=None):
        super().__init__(message)
        self.stage, self.partial = stage, partial


@dataclass(slots=True)
class Execution:
    flux_operator: str
    endpoint: str = "seed"
    stage: str = "preflight"
    phase: object = None
    parameters: object = None
    input_root: object = None
    phase_links: tuple = ()
    seed_phase: object = None
    seed_links: tuple = ()
    seed_trial: object = None
    init_phase: object = None
    init_trial: object = None
    init_links: tuple = ()
    prelude_phase: object = None
    prelude_trial: object = None
    init_setup_completed: bool = False
    init_prelude_completed: bool = False
    callback: object = None
    session: object = None
    world_ready: object = None
    owners: list = field(default_factory=list)
    requests: list = field(default_factory=list)
    trials: list = field(default_factory=list)
    operations: list = field(default_factory=list)
    captures: list = field(default_factory=list)
    primary: object = None
    delegate_error: object = None
    secondary: list = field(default_factory=list)
    last_return: object = None
    last_trial: object = None
    result: object = None
    methods_completed: bool = False
    evidence_completed: bool = False

    def __reduce_ex__(self, protocol):
        raise TypeError("Live demonstration state is not checkpoint or hydration authority")


def _pin(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _relative(module):
    return ("" if module.startswith("validation.") else "src/") + module.replace(".", "/") + ".py"


def source_plan(*, endpoint="seed"):
    if type(endpoint) is not str or endpoint not in ENDPOINTS:
        raise DemoRejected("Choose exactly seed or init_setup or init_prelude", stage="endpoint")
    return dict(
        kind=KIND,
        stages=(
            STAGES
            if endpoint == "seed"
            else (*STAGES, "init_setup")
            if endpoint == "init_setup"
            else (*STAGES, "init_setup", "init_prelude")
        ),
        selected_endpoint=endpoint,
        endpoint=(
            "original graphLaplacian after whole init_core, init_profiles and redo_gj"
            if endpoint == "seed"
            else "fresh retained-world INIT phase and whole init_core; before run_sim_core"
            if endpoint == "init_setup"
            else "same INIT phase dynamics prelude; before profile remapping and RNG"
        ),
        optional_init_setup=dict(
            modules=dict(INIT_MODULES),
            source_pins=dict(INIT_SOURCE_PINS),
            review_pins=dict(INIT_REVIEW_PINS),
            same_process=True,
            same_parameters_cells_callbacks=True,
            new_phase_simulator_cache_handler=True,
            checkpoint_or_time_loop_admission=False,
        ),
        optional_init_prelude=dict(
            modules=dict(PRELUDE_MODULES),
            source_pins=dict(PRELUDE_SOURCE_PINS),
            review_pins=dict(PRELUDE_REVIEW_PINS),
            entry="from_init(actual InitOwner, law_id=LAW_ID) -> prepare(enabled=True)",
            same_phase_parameters_cells_simulator_handler_callbacks_cache=True,
            parent_trial_retained_before_consumption=True,
            original_prefix="Simulator.init_dynamics 758-806 with original reached helpers",
            stops_before="init_profiles, channel_noise_factor RNG and INIT timesteps",
            checkpoint_or_time_loop_admission=False,
        ),
        source_pins=dict(SOURCE_PINS),
        review_pins=dict(REVIEW_PINS),
        shared_log_session_api="Root process-lifetime canonical log-target lease",
        shared_log_session_review=SESSION_REVIEW_SHA256,
        shared_log_scope="callback bootstrap and every later native stage in this process",
        flux_modes=FLUX_MODES,
        flux_policy={
            "original": "retain the original flux inverse and its known numerical defect",
            "disabled": (
                "omit only that inverse; retain value inverse and membrane/junction transport"
            ),
        },
        one_mode_per_fresh_process=True,
        no_retry_or_fallback=True,
        stage_trials="non-additive work and retained evidence, not independent cases",
        profile_images="Actual retained picker filenames, issued immutable original input files",
        input_metadata_sha256=INPUT_METADATA_SHA256,
        evidence_profile="seed_demo",
        evidence_source=EVIDENCE_SOURCE_SHA256,
        evidence_reader=EVIDENCE_MODULE + ".read/files with capture root SHA",
        evidence_scope="lossless bounded transport; partial captures never establish completion",
        native_policy=dict(POLICY),
        native_or_scientific_release=False,
        complete_seed_runner_order_claim=False,
        evolving_SIM_or_restart_claim=False,
        held_postcut_owners=11,
        held_postcut_cases=12,
    )


def _dependencies(endpoint="seed"):
    """Check every producer before importing even a callback definition."""
    if type(endpoint) is not str or endpoint not in ENDPOINTS:
        raise DemoRejected("Choose exactly seed or init_setup or init_prelude", stage="endpoint")
    if (
        set(SOURCE_PINS) != set(MODULES)
        or set(REVIEW_PINS) != set(MODULES)
        or not all(_pin(p) for p in (*SOURCE_PINS.values(), *REVIEW_PINS.values()))
        or not _pin(SESSION_REVIEW_SHA256)
        or not _pin(EVIDENCE_SOURCE_SHA256)
    ):
        raise DemoRejected("Combined producer/route/session adoption remains held", stage="unbound")
    if endpoint != "seed" and (
        set(INIT_SOURCE_PINS) != set(INIT_MODULES)
        or set(INIT_REVIEW_PINS) != set(INIT_MODULES)
        or not all(_pin(p) for p in (*INIT_SOURCE_PINS.values(), *INIT_REVIEW_PINS.values()))
    ):
        raise DemoRejected("Retained-world INIT producers remain unadopted", stage="init_unbound")
    if endpoint == "init_prelude" and (
        set(PRELUDE_SOURCE_PINS) != set(PRELUDE_MODULES)
        or set(PRELUDE_REVIEW_PINS) != set(PRELUDE_MODULES)
        or not all(_pin(p) for p in (*PRELUDE_SOURCE_PINS.values(), *PRELUDE_REVIEW_PINS.values()))
    ):
        raise DemoRejected("INIT prelude producers remain unadopted", stage="prelude_unbound")
    for key, name in MODULES.items():
        path = ROOT / _relative(name)
        if path.is_symlink() or not path.is_file() or snapshot.digest(path) != SOURCE_PINS[key]:
            raise DemoRejected("Reviewed source changed: " + key, stage="producer")
    path = ROOT / _relative(EVIDENCE_MODULE)
    if path.is_symlink() or not path.is_file() or snapshot.digest(path) != EVIDENCE_SOURCE_SHA256:
        raise DemoRejected("Reviewed evidence source changed", stage="producer")
    if endpoint != "seed":
        for key, name in INIT_MODULES.items():
            path = ROOT / _relative(name)
            if (
                path.is_symlink()
                or not path.is_file()
                or snapshot.digest(path) != INIT_SOURCE_PINS[key]
            ):
                raise DemoRejected("Reviewed INIT source changed: " + key, stage="producer")
    if endpoint == "init_prelude":
        for key, name in PRELUDE_MODULES.items():
            path = ROOT / _relative(name)
            if (
                path.is_symlink()
                or not path.is_file()
                or snapshot.digest(path) != PRELUDE_SOURCE_PINS[key]
            ):
                raise DemoRejected("Reviewed INIT prelude source changed: " + key, stage="producer")
    return Modules(endpoint)


def _evidence_writer():
    path = ROOT / _relative(EVIDENCE_MODULE)
    if (
        not _pin(EVIDENCE_SOURCE_SHA256)
        or path.is_symlink()
        or not path.is_file()
        or snapshot.digest(path) != EVIDENCE_SOURCE_SHA256
    ):
        raise DemoRejected("Exact evidence transport unavailable", stage="evidence")
    module = importlib.import_module(EVIDENCE_MODULE)
    if sys.modules.get(EVIDENCE_MODULE) is not module or Path(module.__file__).resolve() != path:
        raise DemoRejected("Actual frozen evidence origin required", stage="evidence")
    return _function(module, "capture_writer")


class Modules:
    """Lazy imports preserve native application bootstrap before parameter birth."""

    def __init__(self, endpoint="seed"):
        self.endpoint = endpoint

    def __getitem__(self, key):
        if key in INIT_MODULES:
            if self.endpoint not in ("init_setup", "init_prelude") or not _pin(
                INIT_SOURCE_PINS[key]
            ):
                raise DemoRejected(
                    "INIT producer unavailable in this endpoint", stage="init_unbound"
                )
            name, expected = INIT_MODULES[key], INIT_SOURCE_PINS[key]
        elif key in PRELUDE_MODULES:
            if self.endpoint != "init_prelude" or not _pin(PRELUDE_SOURCE_PINS[key]):
                raise DemoRejected("INIT prelude producer unavailable", stage="prelude_unbound")
            name, expected = PRELUDE_MODULES[key], PRELUDE_SOURCE_PINS[key]
        else:
            name, expected = MODULES[key], SOURCE_PINS[key]
        path = ROOT / _relative(name)
        if path.is_symlink() or snapshot.digest(path) != expected:
            raise DemoRejected("Selected producer changed: " + key, stage="producer")
        module = importlib.import_module(name)
        if sys.modules.get(name) is not module or Path(module.__file__).resolve() != path:
            raise DemoRejected("Actual frozen producer origin required", stage="producer")
        return module


def _function(module, name):
    value = getattr(module, name, None)
    if type(value) is not FunctionType or value.__globals__ is not vars(module):
        raise DemoRejected("Actual public producer function required: " + name, stage="interface")
    return value


def _output(path):
    path = Path(path)
    if (
        not path.is_absolute()
        or ".." in path.parts
        or path == BASE
        or not path.resolve().is_relative_to(BASE.resolve())
        or path.exists()
        or any(p.is_symlink() for p in (path, *path.parents))
        or path == ROOT
        or path.is_relative_to(ROOT)
        or ROOT.is_relative_to(path)
    ):
        raise DemoRejected(
            "Fresh unlinked output contained in the run root required", stage="output"
        )
    return path


def _validate_output(path, declaration, parameter):
    """Use Key's exact metadata-only packet/input protection before any work."""
    output = _output(path)
    inputs = _function(parameter, "packet_inputs")(
        declaration["parameter_packet"], declaration["parameter_sha256"]
    )
    checked = _function(parameter, "output_path")(
        output, declaration["parameter_packet"], inputs["program"]
    )
    if checked != output:
        raise DemoRejected("No output rewrite permitted", stage="output")
    return output, inputs["program"]["root"]


def _read_plan(path, expected):
    path = Path(path)
    if (
        not _pin(expected)
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > 2**20
        or snapshot.digest(path) != expected
    ):
        raise DemoRejected("Exact bounded demonstration plan required", stage="plan")
    value = json.loads(path.read_text())
    if (
        set(value)
        != {
            "kind",
            "source_plan",
            "snapshot_sha256",
            "parameter_packet",
            "parameter_sha256",
            "callback_bootstrap",
            "callback_bootstrap_sha256",
            "auxiliary_configuration",
            "shared_writer_review",
            "flux_operator",
            "endpoint",
            "policy",
            "held",
        }
        or value["kind"] != KIND
        or type(value["endpoint"]) is not str
        or value["endpoint"] not in ENDPOINTS
        or value["source_plan"] != json.loads(json.dumps(source_plan(endpoint=value["endpoint"])))
        or value["flux_operator"] not in FLUX_MODES
        or type(value["flux_operator"]) is not str
        or value["policy"] != POLICY
        or value["held"] is not True
        or type(value["auxiliary_configuration"]) is not dict
        or not all(
            _pin(value[k])
            for k in ("snapshot_sha256", "parameter_sha256", "callback_bootstrap_sha256")
        )
    ):
        raise DemoRejected("Declared complete single-mode plan changed", stage="plan")
    snapshot.verify(ROOT, manifest_sha256=value["snapshot_sha256"])
    return value


def _resources():
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    if (
        os.sched_getaffinity(0) != {POLICY["cpu"]}
        or not 0 < soft <= hard <= POLICY["max_rss_bytes"]
        or any(
            os.environ.get(k) != "1"
            for k in (
                "OPENBLAS_NUM_THREADS",
                "OMP_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        )
        or os.environ.get("CUDA_VISIBLE_DEVICES") != ""
    ):
        raise DemoRejected("Declared native CPU/thread/memory envelope required", stage="resources")
    available = next(
        int(s.split()[1]) * 1024
        for s in Path("/proc/meminfo").read_text().splitlines()
        if s.startswith("MemAvailable:")
    )
    if available < POLICY["reserve_bytes"]:
        raise DemoRejected("Host reserve unavailable", stage="resources")


class ProcessLogLease:
    """Keep the actual descriptor locked until worker exit, including shutdown."""

    def __init__(self, path):
        self.path, self.fd, self.identity = Path(path), None, None
        self.entry_error, self.cleanup_errors = None, ()

    def __enter__(self):
        if self.fd is not None or any(p.is_symlink() for p in (self.path, *self.path.parents)):
            raise DemoRejected("One canonical log lease required", stage="shared_log")
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            value = os.fstat(fd)
            if (
                not stat.S_ISREG(value.st_mode)
                or stat.S_IMODE(value.st_mode) != 0o600
                or value.st_nlink != 1
                or value.st_uid != os.getuid()
            ):
                raise DemoRejected("Private regular stable log lease required", stage="shared_log")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.fd, self.identity = fd, (value.st_dev, value.st_ino)
            self.check()
            _PROCESS_LEASES.append(self)
            return self
        except BaseException as primary:
            self.entry_error = primary
            try:
                os.close(fd)
            except BaseException as cleanup:
                # Retain the descriptor number and cleanup error as forensic
                # state; do not guess whether a failing close completed.
                self.fd = fd
                self.cleanup_errors = (*self.cleanup_errors, cleanup)
            else:
                self.fd = None
            raise

    def check(self):
        value, named = os.fstat(self.fd), self.path.lstat()
        if self.identity != (value.st_dev, value.st_ino) or self.identity != (
            named.st_dev,
            named.st_ino,
        ):
            raise DemoRejected("Retained log lease descriptor/path changed", stage="shared_log")

    def __exit__(self, kind, error, tb):
        self.check()
        # Deliberately do not close or unlock here. Native logging teardown and
        # later atexit handlers still run in this worker. The kernel releases
        # this fd on process exit; the runner never forks scientific children.
        return False


def _writer_session(callback, review_path):
    path = Path(review_path)
    if (
        not _pin(SESSION_REVIEW_SHA256)
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > 2**20
        or snapshot.digest(path) != SESSION_REVIEW_SHA256
    ):
        raise DemoRejected(
            "Explicit shared native writer coordination required", stage="shared_log"
        )
    review = json.loads(path.read_text())
    policy = _function(callback, "source_plan")()["filesystem_conflicts"]["shared_writer_lease"]
    lock = Path(policy["stable_lock_path"])
    if (
        set(review) != {"kind", "lock_path", "all_native_writers_coordinated", "lifetime"}
        or review["kind"] != "cells.seed_demo_shared_log_release@1"
        or review["lock_path"] != str(lock)
        or review["all_native_writers_coordinated"] is not True
        or review["lifetime"] != "through_worker_process_exit"
        or policy["required"] is not True
        or policy["release_at_acquire_callback_return"] is not False
        or lock != (Path.home() / ".betse").resolve() / ".cells-seed-world-writer.lock"
    ):
        raise DemoRejected("Full native writer lifetime coordination changed", stage="shared_log")
    return ProcessLogLease(lock)


def _fail(state, label, error):
    if state.primary is None:
        state.primary = error
    elif state.primary is not error:
        state.secondary.append((label, error))


def _stop(state):
    if state.primary is not None:
        raise state.primary


def _call(state, label, function, *args, **kwargs):
    _stop(state)
    state.stage = label
    row = dict(name=label, status="attempted")
    state.operations.append(row)
    try:
        value = function(*args, **kwargs)
    except BaseException as error:
        # This is a delegated API failure. Its own source/capture classification
        # and raw partials remain on the exact original exception.
        state.delegate_error = error
        _fail(state, label, error)
        row["status"] = "failed"
        raise
    state.last_return = value  # Preserve a raw return before fallible registration.
    row["status"] = "returned"
    _stop(state)
    return value


def _capture(state, evidence, label, value):
    _stop(state)
    try:
        if not evidence.save(label, value):
            raise ValueError("Typed observation refused: " + label)
        state.captures.append(label)
    except BaseException as error:
        _fail(state, label, error)
        raise
    _stop(state)


def _retain(state, evidence, name, owner, module):
    state.owners.append((name, owner))
    trial = owner.trial  # Exactly before the next issuer consumes this owner.
    state.last_trial = trial
    state.trials.append((name, trial))
    phase = owner.phase
    if state.phase is None:
        if phase.p is not state.parameters:
            raise ValueError("Fresh phase must use the actual acquired parameters")
        state.phase = phase
        state.phase_links = (phase.p, phase.cells, phase.sim, phase.dyna, phase.callbacks)
    if phase is not state.phase or any(
        actual is not expected
        for actual, expected in zip(
            (phase.p, phase.cells, phase.sim, phase.dyna, phase.callbacks),
            state.phase_links,
            strict=True,
        )
    ):
        raise ValueError("Demonstration changed its actual phase/parameter/Cells/Simulator/handler")
    if trial.source_completed is not True:
        raise ValueError("Only completed issued stage trials can advance")
    if name in ("poisson", "core", "junctions") and trial.flux_operator != state.flux_operator:
        raise ValueError("Original/disabled inverse mode changed during continuation")
    _capture(state, evidence, name + ".record", module.trial_record(trial))
    for field_name in ("cache", "after"):
        if hasattr(trial, field_name):
            _capture(state, evidence, name + "." + field_name, getattr(trial, field_name))
    return owner


def _execute(state, modules, plan, directory, evidence):
    """One complete source chain; private adapters are used only by blocked tests."""
    if (
        type(state.endpoint) is not str
        or state.endpoint not in ENDPOINTS
        or state.endpoint != plan.get("endpoint", "seed")
    ):
        raise ValueError("Exact declared demonstration endpoint required")
    callback = modules["callback"]
    state.callback = _call(
        state,
        "callback",
        callback.acquire_callback,
        plan["auxiliary_configuration"],
        directory / "callback",
        bootstrap=plan["callback_bootstrap"],
        bootstrap_sha256=plan["callback_bootstrap_sha256"],
        enabled=True,
    )
    parameter = modules["parameters"]
    pair = _call(
        state,
        "parameters",
        parameter.acquire_world_ready,
        plan["parameter_packet"],
        directory / "parameters",
        packet_sha256=plan["parameter_sha256"],
        enabled=True,
    )
    if type(pair) is not tuple or len(pair) != 2:
        raise ValueError("Exact actual WorldReady/parameter pair required")
    state.world_ready, state.parameters = pair
    if state.world_ready.parameters is not state.parameters:
        raise ValueError("Actual WorldReady owner and parameter instance disagree")
    geometry = modules["geometry"]
    owner = _call(
        state,
        "geometry",
        geometry.evaluate_live,
        state.world_ready,
        state.callback,
        directory / "geometry",
        enabled=True,
        evidence_profile="seed_demo",
    )
    # The qualifier retains its own six-stage records. Its final GeometryOwner
    # is authenticated by the actual next public issuer, never by JSON.
    trial = owner.trial
    state.last_trial = trial
    state.trials.append(("geometry", trial))
    state.owners.append(("geometry", owner))
    state.phase = owner.phase
    if state.phase.p is not state.parameters or trial.source_completed is not True:
        raise ValueError("Completed genuine same-p geometry required")
    state.phase_links = (
        state.phase.p,
        state.phase.cells,
        state.phase.sim,
        state.phase.dyna,
        state.phase.callbacks,
    )
    for name, factory in (
        ("poisson", "from_geometry"),
        ("core", "from_world"),
        ("profiles", "from_core"),
        ("junctions", "from_profiles"),
    ):
        module = modules[name]
        keywords = dict(law_id=module.LAW_ID)
        if name == "poisson":
            keywords["flux_operator"] = state.flux_operator
        elif name == "profiles":
            keywords["image_inputs"] = _profile_image_inputs(state, module)
        request = _call(state, name + "_request", getattr(module, factory), owner, **keywords)
        state.requests.append((name, request))
        owner = _call(state, name, module.prepare, request, enabled=True)
        _retain(state, evidence, name, owner, module)
    if state.endpoint != "seed":
        owner = _init_setup(state, modules["init_setup"], owner, evidence)
    if state.endpoint == "init_prelude":
        owner = _init_prelude(state, modules["init_prelude"], owner, evidence)
    state.result, state.methods_completed = owner, True
    return owner


def _init_setup(state, module, owner, evidence):
    """Consume the issued endpoint once; keep raw history without rereading it."""
    state.seed_phase = state.phase
    state.seed_links = (*state.phase_links, state.phase.cache)
    state.seed_trial = state.last_trial
    request = _call(state, "init_setup_request", module.from_seed, owner, law_id=module.LAW_ID)
    state.requests.append(("init_setup", request))
    child = _call(state, "init_setup", module.prepare, request, enabled=True)
    state.owners.append(("init_setup", child))
    trial = child.trial
    state.init_trial = trial
    state.last_trial = trial
    state.trials.append(("init_setup", trial))
    phase = child.phase
    state.init_phase = phase
    old_p, old_cells, old_sim, old_dyna, old_callbacks, old_cache = state.seed_links
    if (
        phase is state.seed_phase
        or phase.p is not state.parameters
        or phase.p is not old_p
        or phase.cells is not old_cells
        or phase.callbacks is not old_callbacks
        or phase.sim is old_sim
        or phase.dyna is old_dyna
        or phase.cache is old_cache
        or any(value is None for value in (phase.sim, phase.dyna, phase.cache))
        or trial.source_completed is not True
        or trial.parent_identity != state.seed_trial.identity
        or trial.parameter_record is None
    ):
        raise ValueError("Completed fresh INIT phase must retain exact p/Cells/callback/parent")
    state.phase = phase
    state.phase_links = (phase.p, phase.cells, phase.sim, phase.dyna, phase.callbacks)
    state.init_links = (*state.phase_links, phase.cache)
    _capture(state, evidence, "init_setup.record", module.trial_record(trial))
    _capture(state, evidence, "init_setup.before", trial.before)
    _capture(state, evidence, "init_setup.after", trial.after)
    state.init_setup_completed = True
    return child


def _init_prelude(state, module, owner, evidence):
    """Continue the issued INIT owner; never reopen it after its retirement."""
    parent_trial = state.init_trial
    request = _call(state, "init_prelude_request", module.from_init, owner, law_id=module.LAW_ID)
    state.requests.append(("init_prelude", request))
    child = _call(state, "init_prelude", module.prepare, request, enabled=True)
    state.owners.append(("init_prelude", child))
    trial = child.trial
    state.prelude_trial = state.last_trial = trial
    state.trials.append(("init_prelude", trial))
    phase = child.phase
    state.prelude_phase = phase
    if (
        not state.init_setup_completed
        or phase is not state.init_phase
        or phase is not state.phase
        or any(
            actual is not expected
            for actual, expected in zip(
                (phase.p, phase.cells, phase.sim, phase.dyna, phase.callbacks, phase.cache),
                state.init_links,
                strict=True,
            )
        )
        or trial.source_completed is not True
        or trial.parent_identity != parent_trial.identity
    ):
        raise ValueError("Completed INIT prelude must retain the exact phase, objects and parent")
    _capture(state, evidence, "init_prelude.record", module.trial_record(trial))
    _capture(state, evidence, "init_prelude.before", trial.before)
    _capture(state, evidence, "init_prelude.after", trial.after)
    # Trial retains the actual frames. The record names their identities;
    # persist the original returned values without trying to serialize frames.
    _capture(
        state, evidence, "init_prelude.raw_returns", tuple(raw for _, raw in trial.raw_returns)
    )
    state.init_prelude_completed = True
    return child


def _profile_image_inputs(state, module):
    """Declare bytes for observed filenames; from_core authenticates picker ancestry."""
    selected = []
    for profile in state.phase.dyna.tissue_name_to_profile.values():
        filename = getattr(profile.picker, "filename", None)
        if filename is not None:
            if type(filename) is not str:
                raise ValueError("Original native picker filename required")
            if filename in selected:
                continue  # Multiple actual profiles may share the same original image.
            selected.append(filename)
    if not selected:
        return ()
    producer = ROOT / INPUT_METADATA
    if producer.is_symlink() or snapshot.digest(producer) != INPUT_METADATA_SHA256:
        raise ValueError("Reviewed original input metadata producer changed")
    metadata = importlib.import_module("validation.betse.native_seed_demo_inputs")
    if Path(metadata.__file__).resolve() != producer:
        raise ValueError("Actual frozen original input metadata required")
    original = _function(metadata, "_source")()
    root = Path(state.input_root)
    if not root.is_absolute() or root.resolve() != root:
        raise ValueError("Original acquired parameter input root required")
    result = []
    for filename in selected:
        path = Path(filename)
        if not path.is_absolute() or not path.is_relative_to(root):
            raise ValueError("Profile image is outside the actual parameter input tree")
        name = str(path.relative_to(root))
        row = original["files"].get(name)
        if row is None:
            raise ValueError("Profile image is absent from the original data bundle")
        value = _call(
            state,
            "profile_image_file",
            _function(module.files, "input_file"),
            filename,
            sha256=row["sha256"],
            origin="original BETSE input bundle: " + metadata.BUNDLE_SHA256 + "/" + name,
        )
        result.append(value)
    return tuple(result)


def _finish(state, evidence, directory):
    if state.primary is not None:
        try:
            evidence.failure(state.primary)
        except BaseException as error:
            _fail(state, "failure_forensics", error)
    try:
        snapshot.write_json(
            directory / "outcome.json",
            dict(
                kind=KIND,
                status="completed"
                if state.methods_completed and state.primary is None
                else "failed",
                flux_operator=state.flux_operator,
                endpoint=state.endpoint,
                init_setup_completed=state.init_setup_completed,
                init_prelude_completed=state.init_prelude_completed,
                init_time_steps_completed=0,
                original_flux_defect_repaired=False,
                methods_completed=state.methods_completed,
                stage=state.stage,
                completed_stage_trials=[name for name, _ in state.trials],
                operations=[dict(name=r["name"], status=r["status"]) for r in state.operations],
                primary=None if state.primary is None else type(state.primary).__qualname__,
                secondary=[dict(stage=n, error=type(e).__qualname__) for n, e in state.secondary],
                captures=evidence.rows,
                stage_work_is_non_additive=True,
                live_failed_owner_serialization_claimed=False,
                complete_seed_runner_or_INIT_SIM_restart_claim=False,
                scientific_or_physical_credit=0,
            ),
        )
        state.evidence_completed = True
    except BaseException as error:
        _fail(state, "outcome", error)


def _run(state, modules, plan, directory, evidence, session):
    """Protected execution; source failures cannot be hidden by logging or capture."""
    state.session = session
    try:
        with session:
            try:
                _execute(state, modules, plan, directory, evidence)
                _stop(state)
            except BaseException as error:
                # Even an erroneous suppressing session must not erase the
                # original failure or make a partial chain look completed.
                _fail(state, "execution", error)
                raise
    except BaseException as error:
        _fail(state, "execution_or_session", error)
    finally:
        _finish(state, evidence, directory)
    _stop(state)
    if not state.methods_completed or not state.evidence_completed:
        raise ValueError("No complete source/evidence endpoint")
    return state


def run_demo(plan, directory, *, plan_sha256, enabled=False):
    global _ATTEMPT
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise DemoRejected("Combined actual demonstration remains held", stage="release")
    if _ACTIVE:
        error = DemoRejected("A fresh process is required for another demonstration", stage="entry")
        _fail(_ACTIVE[-1], "reentry", error)
        raise error
    if _ATTEMPT is not None:
        raise DemoRejected("Each mode/attempt requires a fresh worker", stage="consumed")
    modules = _dependencies()
    declaration = _read_plan(plan, plan_sha256)
    if declaration["endpoint"] != "seed":
        modules = _dependencies(declaration["endpoint"])
    output, input_root = _validate_output(directory, declaration, modules["parameters"])
    _resources()
    state = Execution(declaration["flux_operator"], endpoint=declaration["endpoint"])
    state.input_root = input_root
    _ATTEMPT = state
    _ACTIVE.append(state)
    try:
        callback = modules["callback"]
        session = _writer_session(callback, declaration["shared_writer_review"])
        output.mkdir(parents=True)
        from validation.betse.native_single_cell_prefix_qualification import Evidence

        evidence = Evidence(output, sidecars=True, capture_writer=_evidence_writer())
        result = _run(state, modules, declaration, output, evidence, session)
    except BaseException as error:
        _fail(state, "run", error)
        result = None
    finally:
        try:
            if _ACTIVE and _ACTIVE[-1] is state:
                _ACTIVE.pop()
            else:
                raise ValueError("Original demonstration reservation changed")
        except BaseException as error:
            _fail(state, "reservation", error)
    if state.primary is not None or result is None:
        cause = state.primary if state.primary is not None else ValueError("No issued endpoint")
        raise DemoRejected(
            "Genuine SEED demonstration failed", stage=state.stage, partial=state
        ) from cause
    return result


def prepare(
    repository,
    directory,
    *,
    inputs,
    inputs_sha256,
    python,
    bootstrap,
    bootstrap_sha256,
    auxiliary_configuration,
    flux_operator,
    endpoint="seed",
    shared_writer_review=None,
    extra_sources=(),
):
    """Freeze the full closure once via Key's existing current-checkout prepare."""
    if type(flux_operator) is not str or flux_operator not in FLUX_MODES:
        raise DemoRejected("Choose exactly original or disabled flux inverse", stage="mode")
    if type(extra_sources) is not tuple:
        raise DemoRejected("Explicit immutable extra source roster required", stage="source_roster")
    for name in extra_sources:
        snapshot.relative_path(name)
        if Path(name).parts[0] not in ("src", "validation", "scripts", "tests"):
            raise DemoRejected(
                "Only checkout execution sources may extend the image", stage="source_roster"
            )
    modules = _dependencies(endpoint)
    if Path(repository).resolve() != ROOT:
        raise DemoRejected("One-way canonical checkout preparation required", stage="checkout")
    parameter = modules["parameters"]
    extra = (
        FILE,
        TEST,
        RUNNER,
        INPUT_METADATA,
        _relative(EVIDENCE_MODULE),
        *(_relative(name) for name in MODULES.values()),
        *(_relative(name) for name in INIT_MODULES.values() if endpoint != "seed"),
        *(_relative(name) for name in PRELUDE_MODULES.values() if endpoint == "init_prelude"),
        *extra_sources,
    )
    value = _function(parameter, "prepare")(
        repository,
        directory,
        inputs=inputs,
        inputs_sha256=inputs_sha256,
        python=python,
        extra_sources=extra,
    )
    directory = Path(directory)
    snapshot.write_json(
        directory / "demo-plan.json",
        dict(
            kind=KIND,
            source_plan=source_plan(endpoint=endpoint),
            snapshot_sha256=snapshot.digest(directory / "source/SNAPSHOT.json"),
            parameter_packet=str(directory),
            parameter_sha256=snapshot.digest(directory / "inputs.json"),
            callback_bootstrap=str(bootstrap),
            callback_bootstrap_sha256=bootstrap_sha256,
            auxiliary_configuration=auxiliary_configuration,
            shared_writer_review=str(shared_writer_review),
            flux_operator=flux_operator,
            endpoint=endpoint,
            policy=dict(POLICY),
            held=True,
        ),
    )
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-plan", action="store_true")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--plan-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.source_plan:
        print(json.dumps(source_plan(), indent=2))
        return 0
    if args.plan is not None and args.output is not None and args.plan_sha256:
        run_demo(args.plan, args.output, plan_sha256=args.plan_sha256, enabled=True)
        return 0
    parser.error("Use source-plan or an exactly released plan in a bounded fresh worker")


if __name__ == "__main__":
    raise SystemExit(main())
