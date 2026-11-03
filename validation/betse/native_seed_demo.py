"""One-process genuine SEED demonstration, through core, profiles and junctions.

This is orchestration of existing public issuers, not a new scientific owner.
Every live parent is born in this process. Saved evidence cannot supply a
parameter, callback, phase, mesh, operator or material state. The selected
endpoint precedes deformation/save, INIT histories and evolving SIM.
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
INPUT_METADATA_SHA256 = "e28af58ae9f881e3887fab9b9882ba3e54826249dec60e3038163d29dfc66685"
RELEASE = "CELLS_NATIVE_SEED_DEMO_RELEASED"
KIND = "cells.genuine_seed_core_profiles_junctions_demo@1"
FLUX_MODES = ("original", "disabled")
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
SOURCE_PINS = dict.fromkeys(MODULES)
REVIEW_PINS = dict.fromkeys(MODULES)
# Root's release must coordinate all native log writers. Advisory locking alone
# cannot establish the absence of writers that do not use this protocol.
SESSION_REVIEW_SHA256 = None
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
    stage: str = "preflight"
    phase: object = None
    parameters: object = None
    input_root: object = None
    phase_links: tuple = ()
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


def source_plan():
    return dict(
        kind=KIND,
        stages=STAGES,
        endpoint="original graphLaplacian after whole init_core, init_profiles and redo_gj",
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
        native_policy=dict(POLICY),
        native_or_scientific_release=False,
        complete_seed_runner_order_claim=False,
        evolving_SIM_or_restart_claim=False,
        held_postcut_owners=11,
        held_postcut_cases=12,
    )


def _dependencies():
    """Check every producer before importing even a callback definition."""
    if (
        set(SOURCE_PINS) != set(MODULES)
        or set(REVIEW_PINS) != set(MODULES)
        or not all(_pin(p) for p in (*SOURCE_PINS.values(), *REVIEW_PINS.values()))
        or not _pin(SESSION_REVIEW_SHA256)
    ):
        raise DemoRejected("Combined producer/route/session adoption remains held", stage="unbound")
    for key, name in MODULES.items():
        path = ROOT / _relative(name)
        if path.is_symlink() or not path.is_file() or snapshot.digest(path) != SOURCE_PINS[key]:
            raise DemoRejected("Reviewed source changed: " + key, stage="producer")
    return Modules()


class Modules:
    """Lazy imports preserve native application bootstrap before parameter birth."""

    def __getitem__(self, key):
        name = MODULES[key]
        path = ROOT / _relative(name)
        if path.is_symlink() or snapshot.digest(path) != SOURCE_PINS[key]:
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
            "policy",
            "held",
        }
        or value["kind"] != KIND
        or value["source_plan"] != json.loads(json.dumps(source_plan()))
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
    state.result, state.methods_completed = owner, True
    return owner


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
    output, input_root = _validate_output(directory, declaration, modules["parameters"])
    _resources()
    state = Execution(declaration["flux_operator"])
    state.input_root = input_root
    _ATTEMPT = state
    _ACTIVE.append(state)
    try:
        callback = modules["callback"]
        session = _writer_session(callback, declaration["shared_writer_review"])
        output.mkdir(parents=True)
        from validation.betse.native_single_cell_prefix_qualification import Evidence

        result = _run(state, modules, declaration, output, Evidence(output, sidecars=True), session)
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
    modules = _dependencies()
    if Path(repository).resolve() != ROOT:
        raise DemoRejected("One-way canonical checkout preparation required", stage="checkout")
    parameter = modules["parameters"]
    extra = (
        FILE,
        TEST,
        RUNNER,
        INPUT_METADATA,
        *(_relative(name) for name in MODULES.values()),
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
            source_plan=source_plan(),
            snapshot_sha256=snapshot.digest(directory / "source/SNAPSHOT.json"),
            parameter_packet=str(directory),
            parameter_sha256=snapshot.digest(directory / "inputs.json"),
            callback_bootstrap=str(bootstrap),
            callback_bootstrap_sha256=bootstrap_sha256,
            auxiliary_configuration=auxiliary_configuration,
            shared_writer_review=str(shared_writer_review),
            flux_operator=flux_operator,
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
