"""Held one-shot detached controller for the genuine public SEED demonstration.

Preparation and launch are metadata only. The fresh frozen worker alone calls
``native_seed_demo.run_demo``. Its release environment is an explicit reviewed
input, never a discovered or automatically enabled collection of source gates.
"""

import argparse
import ast
import faulthandler
import hashlib
import importlib
import json
import os
import re
import resource
import stat
import subprocess
import sys
import sysconfig
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import FunctionType, ModuleType

from validation import source_snapshot as snapshot
from validation.betse import betse_normal_ecm_molecule_qualification_resources as resources
from validation.betse import native_seed_initial_rng as initial_rng
from validation.betse import native_sim_demo_observation as sim_observation

ROOT = Path(__file__).resolve().parents[2]
BASE = Path("/mnt/workspaces/Cells")
FILE = "validation/betse/native_seed_demo_launch.py"
TEST = "tests/unit/test_native_seed_demo_launch.py"
SOFTWARE = "validation/betse/native_seed_demo_launch_software.py"
OWNED = (FILE, TEST, SOFTWARE)
DEMO = "validation/betse/native_seed_demo.py"
PARAMETER = "validation/betse/betse_native_parameter_world_ready_qualification.py"
INPUTS = "validation/betse/native_seed_demo_inputs.py"
NUMPY_ORIGIN = "src/cells/processes/betse_native_numpy_copy_origin.py"
NUMPY_ORIGIN_KIND = "cells.original_numpy_copy_import_origin@1"
INPUT_PROFILES = "validation/betse/native_seed_demo_input_profiles.py"
PRODUCERS = (*OWNED, DEMO, PARAMETER, INPUTS, NUMPY_ORIGIN, INPUT_PROFILES)
KIND = "cells.genuine_seed_demo_detached_launch@12"
RNG_DEMO_KIND = "cells.genuine_seed_core_profiles_junctions_demo@8"
SIM_KIND = "cells.genuine_seed_demo_detached_launch@13"
SIM_DEMO_KIND = "cells.genuine_seed_core_profiles_junctions_demo@9"
SIM_ENDPOINT = "sim_terminal"
SIM_FILE = "validation/betse/native_sim_demo.py"
SIM_MODULES = {
    "preparation": "cells.processes.betse_native_init_sim_preparation",
    "assembly": "cells.processes.betse_native_init_sim_assembly",
    "run": "cells.processes.betse_native_sim_run",
}
SIM_FILES = tuple("src/" + name.replace(".", "/") + ".py" for name in SIM_MODULES.values())
SIM_GATES = (
    "CELLS_NATIVE_INIT_SIM_PREPARATION_RELEASED",
    "CELLS_NATIVE_INIT_SIM_RETIREMENT_RELEASED",
    "CELLS_NATIVE_INIT_SIM_ASSEMBLY_RELEASED",
    "CELLS_NATIVE_SIM_RUN_RETIREMENT_RELEASED",
    "CELLS_NATIVE_SIM_RUN_RELEASED",
)
ACQUISITION_SEQUENCE = ("initial_world_ready", "fresh_current_world_ready")
RELEASE_KIND = "cells.genuine_seed_demo_detached_release@2"
RELEASE = "CELLS_NATIVE_SEED_DEMO_LAUNCH_RELEASED"
DEMO_RELEASE = "CELLS_NATIVE_SEED_DEMO_RELEASED"
POLICY = dict(cpu=0, threads=1, max_rss_bytes=2**30, wall_seconds=7200, reserve_bytes=8 * 2**30)
STACK_INTERVAL_SECONDS = 30
DIAGNOSTIC_WALL_SECONDS = 1800
PILLOW = BASE / "pillow-overlay-12.3.0-20261030-01"
TASKSET = Path("/usr/bin/taskset")
THREADS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "RAYON_NUM_THREADS",
)
_RAW_FAILURES = []
_WRITE_POLICIES = []
_STACK_SAMPLERS = []


def require(value, message):
    if not value:
        raise ValueError(message)


def _wall_seconds(plan):
    require(type(plan.get("stack_diagnostic")) is bool, "Explicit stack diagnostic mode required")
    return DIAGNOSTIC_WALL_SECONDS if plan["stack_diagnostic"] else POLICY["wall_seconds"]


class StackSampler:
    """Sparse C-level stacks without replacing any Python trace/profile hook.

    A failed cancellation keeps its file alive until process exit. Samples are
    locations, not method counters, successful-stage evidence or timings.
    """

    def __init__(self, output):
        self.output = output
        self.stream = None
        self.attempted = self.started = self.cancelled = self.stopped = False

    def start(self):
        require(not self.attempted and self.stream is None, "Stack sampler already used")
        self.stream = (self.output / "stacks.log").open("xb", buffering=0)
        snapshot.write_json(
            self.output / "stack-sampling-start.json",
            dict(
                interval_seconds=STACK_INTERVAL_SECONDS,
                method="faulthandler.dump_traceback_later",
                replaces_python_trace_or_profile=False,
                samples_are_not_stage_completion_or_call_counts=True,
                utc=utc(),
            ),
        )
        self.attempted = True
        faulthandler.dump_traceback_later(
            STACK_INTERVAL_SECONDS, repeat=True, file=self.stream, exit=False
        )
        self.started = True
        snapshot.write_json(self.output / "stack-sampling-armed.json", dict(armed=True, utc=utc()))

    def stop(self):
        require(not self.stopped, "Stack sampler cleanup already attempted")
        self.stopped = True
        if self.attempted:
            # If this raises, no close is safe: the C timer may still own the fd.
            faulthandler.cancel_dump_traceback_later()
            self.cancelled = True
        if self.stream is not None:
            self.stream.close()

    def record(self):
        return dict(
            timer_attempted=self.attempted,
            timer_started=self.started,
            cleanup_attempted=self.stopped,
            cancellation_confirmed=self.cancelled,
            stream_retained_open=self.stream is not None and not self.stream.closed,
            interval_seconds=STACK_INTERVAL_SECONDS,
            stage_completion_or_scientific_credit=False,
        )


def _link_record(value):
    info = value.lstat()
    return dict(
        text=os.readlink(value),
        resolved=str(value.resolve(strict=True)),
        device=info.st_dev,
        inode=info.st_ino,
        mode=info.st_mode,
        mtime_ns=info.st_mtime_ns,
        ctime_ns=info.st_ctime_ns,
    )


def _null_device():
    """The existing Linux discard device is not a filesystem output domain."""
    value = Path("/dev/null")
    info = value.lstat()
    require(
        not any(p.is_symlink() for p in (value, *value.parents))
        and stat.S_ISCHR(info.st_mode)
        and (os.major(info.st_rdev), os.minor(info.st_rdev)) == (1, 3),
        "Original null character device required",
    )
    return dict(
        path=str(value), device=info.st_dev, inode=info.st_ino, mode=info.st_mode, rdev=info.st_rdev
    )


class WritePolicy:
    """Process-lifetime writes for the declared native bootstrap and outputs.

    The one existing native-home link is authenticated, not generally followed.
    Parameter permissions allow only their original directory creations. A
    caught violation still prevents a successful worker result; evidence writes
    remain available so the original failure can be retained.
    """

    def __init__(self, output, *, native_home, native_target, native_link, directories):
        self.output = path(output)
        self.native_home = Path(native_home)
        self.native_target = path(native_target)
        require(
            self.output.is_dir() and self.native_target.is_dir(),
            "Actual write directories required",
        )
        self.native_link = native_link
        self.null_device = _null_device()
        self.temporary_directory = None
        self.directories = tuple(path(value, exists=False) for value in directories)
        self.events, self.failures = [], []
        self.first_error = None
        self.installed = False
        self.check()

    def _native_link(self):
        if self.native_link is None:
            require(
                self.native_home == self.native_target and not self.native_home.is_symlink(),
                "Native log root changed",
            )
        else:
            require(
                self.native_home.is_symlink()
                and _link_record(self.native_home) == self.native_link
                and self.native_link["resolved"] == str(self.native_target),
                "Native log link changed",
            )

    def _target(self, value):
        require(type(value) in (str, bytes), "Unowned write descriptor refused")
        value = Path(os.fsdecode(value))
        require(value.is_absolute() and ".." not in value.parts, "Absolute write path required")
        if value == self.native_home or value.is_relative_to(self.native_home):
            self._native_link()
            require(
                not any(parent.is_symlink() for parent in self.native_home.parents),
                "Native-home parent link changed",
            )
            relative = value.relative_to(self.native_home)
            value = self.native_target / relative
        return path(value, exists=False)

    def _retain(self, error, event, targets):
        if self.first_error is None:
            self.first_error = error
        if len(self.failures) < 64:
            self.failures.append((event, targets, error))

    def audit(self, event, args):
        if event == "cells.seed_demo.filesystem_installed":
            if len(args) == 1 and args[0] is self:
                self.installed = True
            return
        if event == "open":
            if type(args[2]) is not int or not args[2] & (
                os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
            ):
                return
            targets = args[:1]
        elif event in ("os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.truncate"):
            targets = args[:1]
        elif event in ("os.rename", "os.link", "os.symlink"):
            targets = args[:2]
        else:
            return
        try:
            require(len(self.events) < 4096, "Bounded diagnostic filesystem events")
            self.events.append((event, targets))
            require(event != "os.symlink", "New native links are not declared")
            for target in targets:
                if type(target) in (str, bytes) and os.fsdecode(target) == "/dev/null":
                    require(event == "open", "Only null-device opens are declared")
                    require(_null_device() == self.null_device, "Null device identity changed")
                    continue
                if type(target) in (str, bytes) and Path(os.fsdecode(target)) in (
                    self.native_home,
                    self.native_target,
                ):
                    require(event == "os.mkdir", "Native log roots cannot be replaced or removed")
                actual = self._target(target)
                output = actual == self.output or actual.is_relative_to(self.output)
                native = actual == self.native_target or actual.is_relative_to(self.native_target)
                if native:
                    self._native_link()
                mkdir = event == "os.mkdir" and actual in self.directories
                require(output or native or mkdir, "Undeclared demonstration write refused")
        except BaseException as error:
            self._retain(error, event, targets)
            raise

    def check(self):
        try:
            self._native_link()
            require(_null_device() == self.null_device, "Null device identity changed")
            if self.temporary_directory is not None:
                directory = self.temporary_directory["path"]
                require(
                    _temporary_binding(Path(directory)) == self.temporary_directory
                    and type(tempfile.tempdir) is str
                    and tempfile.tempdir == directory
                    and all(os.environ.get(key) == directory for key in ("TMPDIR", "TEMP", "TMP")),
                    "Worker temporary directory changed",
                )
        except BaseException as error:
            self._retain(error, "filesystem-binding-check", ())
            raise
        if self.first_error is not None:
            raise self.first_error

    def record(self):
        return dict(
            events=[
                dict(
                    event=event, targets=[os.fsdecode(v) if type(v) is bytes else v for v in values]
                )
                for event, values in self.events
            ],
            failures=[
                dict(event=event, error=error_record(error)) for event, _, error in self.failures
            ],
            first_error=None if self.first_error is None else error_record(self.first_error),
            lifetime="through_worker_process_exit",
            native_link=self.native_link,
            null_device=self.null_device,
            temporary_directory=self.temporary_directory,
        )


def _temporary_binding(directory):
    info = path(directory).stat()
    require(
        stat.S_ISDIR(info.st_mode) and not info.st_mode & 0o077,
        "Private temporary directory required",
    )
    return dict(path=str(directory), device=info.st_dev, inode=info.st_ino, mode=info.st_mode)


def _temporary_directory(output, policy):
    """Select and probe the declared worker directory before library bootstrap."""
    directory = path(output / "runtime-cache/tmp", exists=False)
    require(
        all(os.environ.get(key) == str(directory) for key in ("TMPDIR", "TEMP", "TMP")),
        "Exact worker temporary environment required",
    )
    require(
        tempfile.tempdir is None
        or (type(tempfile.tempdir) is str and tempfile.tempdir == str(directory)),
        "Foreign cached temporary directory refused",
    )
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    policy.temporary_directory = _temporary_binding(directory)
    require(tempfile.gettempdir() == str(directory), "Temporary selection escaped worker output")
    with tempfile.NamedTemporaryFile(prefix=".bootstrap-", dir=str(directory)) as probe:
        probe.write(b"worker temporary directory probe")
        probe.seek(0)
        require(probe.read() == b"worker temporary directory probe", "Temporary write probe failed")
    policy.check()
    return policy.temporary_directory


def _filesystem(plan, output):
    """Authenticate the existing declarations before installing the audit."""
    declaration = read(plan["demo_plan"])
    bootstrap = read(
        dict(
            path=declaration["callback_bootstrap"],
            sha256=declaration["callback_bootstrap_sha256"],
        )
    )
    inputs = read(plan["parameter_inputs"])
    home = Path.home() / ".betse"
    links = bootstrap["native_links"]
    require(type(links) is dict and set(links) <= {str(home)}, "Exact native link declaration")
    link = links.get(str(home))
    target = home if link is None else Path(link["resolved"])
    mpl = output / "runtime-cache/matplotlib"
    require(
        bootstrap["environment"]
        == dict(HOME=str(Path.home()), MPLCONFIGDIR=str(mpl), PYTHONDONTWRITEBYTECODE="1")
        and set(bootstrap["native_write_roots"]) == {str(home), str(target), str(mpl)},
        "Exact bootstrap write domains required",
    )
    policy = WritePolicy(
        output,
        native_home=home,
        native_target=target,
        native_link=link,
        directories=inputs["program"]["directories"],
    )
    _WRITE_POLICIES.append(policy)
    sys.addaudithook(policy.audit)
    sys.audit("cells.seed_demo.filesystem_installed", policy)
    require(policy.installed is True, "Actual demonstration filesystem audit required")
    return policy


def source_plan(*, endpoint="seed"):
    value = dict(
        kind=KIND,
        held=True,
        policy=POLICY,
        actual_entry="native_seed_demo.run_demo",
        release_environment="explicit exact map, no discovered gates",
        detached=True,
        automatic_retry=False,
        automatic_polling=False,
        stack_diagnostic=dict(
            default=False,
            wall_seconds=DIAGNOSTIC_WALL_SECONDS,
            interval_seconds=STACK_INTERVAL_SECONDS,
            original_source_and_guards=True,
            python_trace_profile_replacement=False,
            samples_are_not_call_counts_or_completed_stages=True,
            cancellation_failure_retains_stream_until_process_exit=True,
        ),
        fresh_process_per_flux_mode=True,
        endpoint=(
            "Exact plan choice: seed, init_setup, init_prelude, init_dynamics, init_electrical"
            " or init_first_step or init_short_history or init_terminal;"
            " original calendar and separate endpoint completion evidence"
        ),
        init_iterations="Exact int 1..64 only for init_short_history; None for other endpoints",
        complete_original_inputs="Exact pair manifest; selected mode only before consumption",
        postrun_inputs="Original selected file bytes only, never fresh directory epochs",
        filesystem="Authenticated native-home link, worker output/cache, exact parameter mkdirs",
        discard_device="Only opens of exact unlinked Linux /dev/null character device (1:3)",
        temporary_directory=(
            "Exact private worker/runtime-cache/tmp; "
            "environment/cache/identity and actual I/O checked before imports"
        ),
        filesystem_lifetime="Installed and retained through worker process exit",
        source_call_count="Stage work records; not standalone ParameterCalls aggregate credit",
        owner_hydration=False,
        source_or_independent_physical_acceptance=False,
        runtime_scope="Actual loaded file/map inventories; not a complete prelaunch library proof",
    )
    if endpoint == SIM_ENDPOINT:
        value.update(
            kind=SIM_KIND,
            sim_terminal=dict(
                demo_kind=SIM_DEMO_KIND,
                acquisition_sequence=list(ACQUISITION_SEQUENCE),
                source=SIM_FILE,
                maximum_iterations=512,
                complete_INIT_then_complete_SIM=True,
                explicit_release_flags=list(SIM_GATES),
                selected_iterations=False,
                before_native_pickle=True,
                scientific_credit=0,
                observation_release=sim_observation.RELEASE,
                history_release=sim_observation.HISTORY_RELEASE,
                observation_required_before_success=True,
                saved_binding_requires_explicit_postprocess=True,
                comparison_acceptance=False,
            ),
        )
    return value


def utc():
    return datetime.now(timezone.utc).isoformat()


def _hash(value):
    return type(value) is str and re.fullmatch("[0-9a-f]{64}", value) is not None


def path(value, *, exists=True):
    p = Path(value)
    require(p.is_absolute() and ".." not in p.parts, "Absolute canonical path required")
    require(not any(q.is_symlink() for q in (p, *p.parents)), "Linked path refused")
    require(p == p.resolve(strict=exists), "Canonical path required")
    return p


def pin(value):
    p = path(value)
    before = p.stat()
    require(
        stat.S_ISREG(before.st_mode) and before.st_nlink == 1, "Regular single-link file required"
    )
    digest = snapshot.digest(p)
    after = p.stat()
    require(
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
        "File changed while hashing",
    )
    return dict(path=str(p), sha256=digest)


def bound(row):
    require(type(row) is dict and set(row) == {"path", "sha256"}, "Exact file pin required")
    require(_hash(row["sha256"]) and pin(row["path"]) == row, "Changed bound file")
    return Path(row["path"])


def _pairs(rows):
    result = {}
    for key, value in rows:
        require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def read(row):
    p = bound(row)
    require(p.stat().st_size <= 16 * 2**20, "Bounded metadata required")
    raw = p.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == row["sha256"], "Metadata changed during read")
    return json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_pairs,
        parse_constant=lambda value: require(False, "Nonstandard JSON: " + value),
    )


def _environment_map(value):
    require(type(value) is dict and 2 <= len(value) <= 128, "Explicit release environment required")
    for key, item in value.items():
        require(
            type(key) is str
            and re.fullmatch("CELLS_[A-Z0-9_]+_RELEASED", key)
            and type(item) is str
            and item == "1",
            "Only explicit source-release flags",
        )
    require(
        value.get(RELEASE) == value.get(DEMO_RELEASE) == "1", "Two public release flags required"
    )
    return dict(value)


def _parameter():
    return importlib.import_module(
        "validation.betse.betse_native_parameter_world_ready_qualification"
    )


def _demo():
    return importlib.import_module("validation.betse.native_seed_demo")


def _numpy_origin(plan):
    """Load only the declared stdlib observer, before the first NumPy import."""
    expected = Path(plan["source"]) / NUMPY_ORIGIN
    require(
        pin(expected)["sha256"] == plan["producers"][NUMPY_ORIGIN],
        "Original NumPy construction observer producer changed",
    )
    module = importlib.import_module("cells.processes.betse_native_numpy_copy_origin")
    require(
        type(module) is ModuleType and Path(module.__file__).resolve() == expected,
        "Actual frozen NumPy construction observer required",
    )
    for name in ("capture", "record"):
        function = vars(module).get(name)
        require(
            type(function) is FunctionType and function.__globals__ is vars(module),
            "Original NumPy observer interface required: " + name,
        )
    return module


def _numpy_origin_complete(value):
    require(
        type(value) is dict
        and value.get("kind") == NUMPY_ORIGIN_KIND
        and value.get("completed") is True
        and value.get("hooks_restored") is True
        and value.get("source_error") is None
        and value.get("capture_errors") == []
        and value.get("cleanup_errors") == []
        and type(value.get("source_files")) is dict
        and bool(value["source_files"]),
        "Original NumPy copy construction proof incomplete",
    )


def _interpreter(row):
    # The invocation is the original venv symlink, the executable has a separate pin.
    require(type(row) is dict and type(row.get("entry")) is str, "Runtime entry required")
    entry = Path(row["entry"])
    require(entry.is_absolute() and entry.is_file(), "Missing interpreter invocation")
    require(pin(entry.resolve()) == row["executable"], "Changed executable")
    bound(row["venv_configuration"])
    return entry


def _input_metadata(plan):
    expected = plan["producers"][INPUTS]
    producer = ROOT / INPUTS
    require(pin(producer)["sha256"] == expected, "Frozen complete-input producer required")
    module = importlib.import_module("validation.betse.native_seed_demo_inputs")
    require(
        Path(module.__file__).resolve() == producer and pin(producer)["sha256"] == expected,
        "Actual complete-input metadata origin required",
    )
    return module


def _input_files(bundle, mode):
    """Derive only this mode's immutable file roster, without touching its sibling."""
    value = read(bundle)
    config = path(value["modes"][mode]["config"])
    result = []
    from validation.betse import native_seed_demo_input_profiles as profiles

    for name, row in sorted(profiles.selected_inventory(value)["files"].items()):
        snapshot.relative_path(name)
        require(_hash(row["sha256"]), "Exact original input digest required")
        result.append(dict(path=str(config / name), sha256=row["sha256"]))
    require(bool(result), "Complete original input roster required")
    return result


def _initial_rng_inputs(plan, declaration, bundle, inputs, manifest):
    """Bind the whole declared input tree; this does not establish RNG authority."""
    if declaration.get("kind") not in (RNG_DEMO_KIND, SIM_DEMO_KIND):
        require(
            "initial_rng_inputs" not in declaration and "initial_rng_inputs" not in plan,
            "Initial RNG observation requires the explicit demo schema",
        )
        return
    from validation.betse import native_seed_demo_input_profiles as profiles

    selected = initial_rng.validate_declaration(declaration["initial_rng_inputs"])
    initial_rng.validate_declaration(plan.get("initial_rng_inputs"))
    require(
        plan.get("initial_rng_inputs") == selected
        and selected["profile"]
        == bundle.get("configuration_profile", "original")
        == inputs["program"].get("input_profile", "original")
        and selected["inventory"] == profiles.selected_inventory(bundle),
        "Complete initial RNG input/profile binding changed",
    )
    inventory = selected["inventory"]
    directories, files = inventory["directories"], inventory["files"]
    require(
        type(directories) is list
        and all(type(name) is str for name in directories)
        and directories == sorted(set(directories))
        and type(files) is dict
        and 0 < len(files) <= 512
        and len(files) + len(directories) <= 1024,
        "Bounded complete input directory/file roster required",
    )
    for name in (*directories, *files):
        snapshot.relative_path(name)
        require(
            all(str(parent) in directories for parent in Path(name).parents if str(parent) != "."),
            "Complete input ancestor directory roster required",
        )
    require(not set(directories).intersection(files), "Input file/directory roles overlap")
    total = 0
    for name, row in files.items():
        require(
            type(row) is dict
            and set(row) == {"size_bytes", "sha256"}
            and type(row["size_bytes"]) is int
            and 0 <= row["size_bytes"] <= 8 * 2**20
            and _hash(row["sha256"]),
            "Exact original input extent/digest required",
        )
        actual = bound(dict(path=str(Path(inputs["program"]["root"]) / name), sha256=row["sha256"]))
        require(actual.stat().st_size == row["size_bytes"], "Original input extent changed")
        total += row["size_bytes"]
    require(total <= 16 * 2**20, "Complete input byte bound exceeded")
    expected = manifest["files"][initial_rng.FILE]["sha256"]
    policy = declaration.get("source_plan", {}).get("initial_rng_observation")
    require(type(policy) is dict, "Exact initial RNG policy required")
    version = policy.get("kind")
    require(version in (initial_rng.LEGACY_KIND, initial_rng.KIND), "Unknown initial RNG version")
    runtime_policy = {}
    if version == initial_rng.KIND:
        runtime_file = initial_rng.rng_runtime.FILE
        runtime_sha = manifest["files"].get(runtime_file, {}).get("sha256")
        require(
            _hash(runtime_sha) and plan["producers"].get(runtime_file) == runtime_sha,
            "Built-in RNG provenance helper missing from immutable closure",
        )
        runtime_policy = dict(
            runtime_producer="validation.betse.native_rng_runtime",
            runtime_producer_sha256=runtime_sha,
        )
    require(
        policy
        == dict(
            kind=version,
            epoch=initial_rng.EPOCH,
            boundary="after_issued_WorldReady_before_geometry_phase_construction",
            full_numpy_MT_and_python_state=True,
            complete_input_inventory_bound=True,
            reset_draw_or_replacement=False,
            common_starting_authority_established=False,
            producer="validation.betse.native_seed_initial_rng",
            producer_sha256=expected,
            **runtime_policy,
        )
        and all(
            type(policy[key]) is bool
            for key in (
                "full_numpy_MT_and_python_state",
                "complete_input_inventory_bound",
                "reset_draw_or_replacement",
                "common_starting_authority_established",
            )
        ),
        "Exact observation-only initial RNG source declaration required",
    )


def _producers(declaration):
    common = (
        (initial_rng.COMMON_FILE, initial_rng.ORIGINAL) if "common_start" in declaration else ()
    )
    runtime = (
        (initial_rng.rng_runtime.FILE,)
        if declaration.get("source_plan", {}).get("initial_rng_observation", {}).get("kind")
        == initial_rng.KIND
        else ()
    )
    if declaration.get("kind") == SIM_DEMO_KIND:
        return (
            *PRODUCERS,
            *common,
            initial_rng.FILE,
            *runtime,
            SIM_FILE,
            *SIM_FILES,
            sim_observation.FILE,
            sim_observation.OBSERVER,
            sim_observation.WRITER,
            sim_observation.HISTORY,
        )
    return (
        (*PRODUCERS, initial_rng.FILE, *runtime, *common)
        if declaration.get("kind") == RNG_DEMO_KIND
        else PRODUCERS
    )


def _sim_contract(plan, declaration, inputs, manifest):
    """Read only exact declared source constants; never import an issuer."""
    sim = plan.get("endpoint") == SIM_ENDPOINT
    require((plan["kind"] == SIM_KIND) is sim, "SIM launch schema/endpoint mismatch")
    require((declaration.get("kind") == SIM_DEMO_KIND) is sim, "SIM demo schema/endpoint mismatch")
    if not sim:
        require("acquisition_sequence" not in plan, "Legacy launch has no current acquisition")
        return
    require(
        plan.get("acquisition_sequence") == list(ACQUISITION_SEQUENCE)
        and inputs.get("acquisition_sequence") == list(ACQUISITION_SEQUENCE),
        "Exact predeclared initial/current acquisition sequence required",
    )
    require(
        all(plan["release_environment"].get(name) == "1" for name in SIM_GATES),
        "Explicit actual SIM release flags required",
    )
    policy = declaration.get("source_plan", {}).get("optional_sim_terminal", {})
    require(
        policy.get("module") == "validation.betse.native_sim_demo"
        and policy.get("source_sha256") == manifest["files"][SIM_FILE]["sha256"]
        and _hash(policy.get("review_sha256"))
        and policy.get("acquisition_sequence") == list(ACQUISITION_SEQUENCE)
        and type(policy.get("maximum_iterations")) is int
        and policy["maximum_iterations"] == 512
        and all(
            policy.get(name) is True
            for name in (
                "complete_configured_calendar",
                "same_retained_simulator_and_cells",
                "distinct_fresh_loaded_parameters_and_SIM_phase",
                "before_native_pickle",
                "imports_before_callback",
            )
        )
        and policy.get("selected_stop") is False
        and policy.get("physical_checkpoint_or_scientific_admission") is False,
        "Exact held complete SIM source policy required",
    )
    constants = {}
    for node in ast.parse((Path(plan["source"]) / SIM_FILE).read_bytes()).body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            name = node.targets[0].id
            if name in ("MODULES", "SOURCE_PINS", "REVIEW_PINS"):
                require(name not in constants, "Duplicate SIM source declaration")
                try:
                    constants[name] = ast.literal_eval(node.value)
                except (ValueError, TypeError) as error:
                    raise ValueError("SIM source/review declarations remain unadopted") from error
    require(constants.get("MODULES") == SIM_MODULES, "Exact actual SIM module roster required")
    for field in ("SOURCE_PINS", "REVIEW_PINS"):
        rows = constants.get(field)
        require(
            type(rows) is dict
            and set(rows) == set(SIM_MODULES)
            and all(_hash(value) for value in rows.values()),
            "Closed SIM producer/review pins required",
        )
    require(
        plan["release_environment"].get(sim_observation.RELEASE) == "1",
        "Explicit completed-SIM observation release required",
    )
    require(
        plan["release_environment"].get(sim_observation.HISTORY_RELEASE) == "1",
        "Explicit completed-history observation release required",
    )
    sim_observation.contract(
        plan["source"],
        policy.get("completed_observation"),
        {name: row["sha256"] for name, row in manifest["files"].items()},
        constants["SOURCE_PINS"]["run"],
    )
    sim_observation.check_original_sources(plan.get("sim_original_sources"))
    require(
        plan["sim_original_sources"]["root"] in plan["runtime_roots"],
        "Original source inventory must bind a declared runtime root",
    )
    for (name, module), relative in zip(SIM_MODULES.items(), SIM_FILES, strict=True):
        require(
            constants["SOURCE_PINS"][name] == manifest["files"][relative]["sha256"],
            "SIM stage producer differs from frozen closure: " + module,
        )


def _inputs(plan, parameter_inputs, *, initial):
    bundle = plan["input_bundle"]
    value = read(bundle)
    mode = plan["flux_operator"]
    row = value["modes"][mode]
    require(
        value.get("configuration_profile", "original")
        == parameter_inputs["program"].get("input_profile", "original")
        == read(row["program"]).get("input_profile", "original"),
        "Selected configuration profile must match actual parameter inputs",
    )
    require(
        row["program"] == parameter_inputs["program"]["manifest"]
        and row["config"] == parameter_inputs["program"]["root"],
        "Selected complete-input mode must match the exact Key input program",
    )
    require(
        plan["input_files"] == _input_files(bundle, mode),
        "Complete selected original input roster changed",
    )
    for original in plan["input_files"]:
        bound(original)
    if initial:
        checked = _input_metadata(plan).verify(
            Path(bundle["path"]).parent, bundle["sha256"], mode=mode
        )
        require(checked == value, "Complete input verification changed its declaration")


def _common_start(plan, declaration, manifest):
    """Keep an explicit program separate from the observation-only initial witness."""
    selected = "common_start" in declaration
    require(("common_start" in plan) is selected, "Explicit common-start launch association")
    if not selected:
        require(
            initial_rng.COMMON_RELEASE not in plan["release_environment"],
            "Ambient launch cannot silently request a common-start program",
        )
        return
    require(
        plan["common_start"] == declaration["common_start"]
        and declaration["source_plan"].get("common_start") == declaration["common_start"]
        and plan["release_environment"].get(initial_rng.COMMON_RELEASE) == "1",
        "Exact opt-in declaration and independent release flag required",
    )
    initial_rng.common_binding(declaration, manifest)
    for name in (initial_rng.COMMON_FILE, initial_rng.ORIGINAL):
        require(
            plan["producers"].get(name) == manifest["files"][name]["sha256"],
            "Actual common-start helper/caller missing from launch producer roster",
        )


def _immutable(plan):
    """Recheck byte provenance without reopening consumed native directory epochs."""
    declaration = read(plan["demo_plan"])
    inputs = read(plan["parameter_inputs"])
    source = Path(plan["source"])
    manifest = snapshot.verify(source, manifest_sha256=plan["source_snapshot"]["sha256"])
    _common_start(plan, declaration, manifest)
    require(bound(plan["source_snapshot"]) == source / "SNAPSHOT.json", "Snapshot association")
    require(declaration["snapshot_sha256"] == plan["source_snapshot"]["sha256"], "Demo snapshot")
    require(Path(declaration["parameter_packet"]) / "source" == source, "Demo packet association")
    require(
        Path(declaration["parameter_packet"]) / "inputs.json" == bound(plan["parameter_inputs"])
        and declaration["parameter_sha256"] == plan["parameter_inputs"]["sha256"],
        "Parameter packet association",
    )
    require(
        declaration["held"] is True
        and declaration["policy"] == POLICY
        and declaration["flux_operator"] in ("original", "disabled"),
        "Held demo domain",
    )
    require(plan["flux_operator"] == declaration["flux_operator"], "Flux binding")
    require(
        type(plan["endpoint"]) is str
        and plan["endpoint"]
        in (
            "seed",
            "init_setup",
            "init_prelude",
            "init_dynamics",
            "init_electrical",
            "init_first_step",
            "init_short_history",
            "init_terminal",
            SIM_ENDPOINT,
        )
        and plan["endpoint"] == declaration.get("endpoint", "seed"),
        "Exact demonstration endpoint binding",
    )
    if plan["endpoint"] == "init_first_step":
        require(
            declaration.get("kind")
            in (
                "cells.genuine_seed_core_profiles_junctions_demo@5",
                "cells.genuine_seed_core_profiles_junctions_demo@6",
                "cells.genuine_seed_core_profiles_junctions_demo@7",
                RNG_DEMO_KIND,
            ),
            "First-step endpoint requires its explicit demo schema",
        )
    count = plan.get("init_iterations")
    require(
        type(count) is type(declaration.get("init_iterations"))
        and count == declaration.get("init_iterations")
        and (
            type(count) is int and 1 <= count <= 64
            if plan["endpoint"] == "init_short_history"
            else count is None
        ),
        "Exact demonstration iteration count binding",
    )
    if plan["endpoint"] == "init_short_history":
        require(
            declaration.get("kind")
            in (
                "cells.genuine_seed_core_profiles_junctions_demo@6",
                "cells.genuine_seed_core_profiles_junctions_demo@7",
                RNG_DEMO_KIND,
            ),
            "Short-history endpoint requires its explicit demo schema",
        )
    if plan["endpoint"] in ("init_terminal", SIM_ENDPOINT):
        require(
            declaration.get("kind")
            in ("cells.genuine_seed_core_profiles_junctions_demo@7", RNG_DEMO_KIND, SIM_DEMO_KIND),
            "Natural terminal endpoint requires its explicit demo schema",
        )
        terminal = declaration.get("source_plan", {}).get("optional_init_terminal", {})
        require(
            type(terminal.get("maximum_iterations")) is int
            and terminal["maximum_iterations"] == 512
            and terminal.get("init_iterations") is None
            and terminal.get("full_original_calendar") is True
            and terminal.get("normal_loop_context_and_caller_return") is True
            and terminal.get("selected_stop") is False
            and terminal.get("before_native_pickle") is True,
            "Natural terminal cannot select or shorten its source calendar",
        )
    require(
        inputs["source_snapshot"] == plan["source_snapshot"]
        and inputs["runtime"] == plan["runtime"],
        "Parameter runtime/snapshot binding",
    )
    require(
        plan["producers"]
        == {name: manifest["files"][name]["sha256"] for name in _producers(declaration)},
        "Producer roster",
    )
    _sim_contract(plan, declaration, inputs, manifest)
    for row in plan["external_files"]:
        bound(row)
    _inputs(plan, inputs, initial=False)
    _initial_rng_inputs(plan, declaration, read(plan["input_bundle"]), inputs, manifest)
    _interpreter(plan["runtime"])
    require(
        _parameter().runtime_plan(plan["runtime"]["entry"]) == plan["runtime"],
        "Runtime providers changed",
    )
    return declaration, inputs, manifest


def _output_domain(value, plan, *, fresh):
    p = path(value, exists=not fresh)
    require(
        p != BASE and p.is_relative_to(BASE) and (not fresh or not p.exists()),
        "Fresh output under run root required",
    )
    protected = [
        Path(plan["source"]),
        Path(plan["demo_plan"]["path"]).parent,
        Path(plan["parameter_inputs"]["path"]).parent,
        Path(plan["input_bundle"]["path"]).parent,
        ROOT,
    ]
    protected += [Path(q) for q in plan["runtime_roots"]]
    protected += [Path(row["path"]) for row in plan["external_files"]]
    for q in protected:
        require(
            p != q and not p.is_relative_to(q) and not q.is_relative_to(p),
            "Output overlaps an input",
        )
    inputs = read(plan["parameter_inputs"])
    checked = _parameter().output_path(
        p, Path(plan["parameter_inputs"]["path"]).parent, inputs["program"]
    )
    require(checked == p, "No output rewriting")
    return p


def _safe_output(value, plan):
    return _output_domain(value, plan, fresh=True)


def prepare(
    prepared,
    destination,
    *,
    demo_plan_sha256,
    release_environment,
    input_bundle,
    stack_diagnostic=False,
):
    """Bind an already frozen demo packet; never adopt or enable its source gates."""
    require(type(stack_diagnostic) is bool, "Explicit stack diagnostic mode required")
    prepared = path(prepared)
    demo_pin = dict(path=str(prepared / "demo-plan.json"), sha256=demo_plan_sha256)
    declaration = read(demo_pin)
    inputs_pin = dict(path=str(prepared / "inputs.json"), sha256=declaration["parameter_sha256"])
    inputs = read(inputs_pin)
    source = prepared / "source"
    manifest = snapshot.verify(source, manifest_sha256=declaration["snapshot_sha256"])
    require(
        all(name in manifest["files"] for name in _producers(declaration)),
        "demo.prepare must include launch sources and the complete-input producer",
    )
    environment = _environment_map(release_environment)
    runtime = inputs["runtime"]
    _interpreter(runtime)
    # Package roots are explicit admission domains; every actual loaded file is
    # hashed before/after below. This does not claim unobserved package coverage.
    roots = [
        str(Path(sysconfig.get_path("stdlib")).resolve()),
        runtime["primary_site"],
        runtime["appended_site"],
        str(PILLOW),
        str(BASE / "betse-v1.5.0"),
    ]
    for p in roots:
        require(path(p).is_dir(), "Runtime root unavailable")
    external = [
        pin(TASKSET),
        pin(bound(inputs["source_review"])),
        pin(Path(declaration["callback_bootstrap"])),
        pin(Path(declaration["shared_writer_review"])),
    ]
    require(
        external[2]["sha256"] == declaration["callback_bootstrap_sha256"],
        "Callback bootstrap changed",
    )
    # Explicit startup exception; never grants trust to the /etc directory.
    startup = Path("/etc/python3.13/sitecustomize.py")
    if startup.is_file():
        external.append(pin(startup))
    for row in inputs["program"]["files"].values():
        external.append(pin(bound(row)))
    external.append(pin(bound(inputs["program"]["manifest"])))
    value = dict(
        kind=SIM_KIND if declaration.get("endpoint") == SIM_ENDPOINT else KIND,
        held=True,
        automatic_retry=False,
        policy=POLICY,
        stack_diagnostic=stack_diagnostic,
        demo_plan=demo_pin,
        parameter_inputs=inputs_pin,
        source=str(source),
        source_snapshot=pin(source / "SNAPSHOT.json"),
        producers={name: manifest["files"][name]["sha256"] for name in _producers(declaration)},
        input_bundle=dict(input_bundle),
        input_files=_input_files(input_bundle, declaration["flux_operator"]),
        runtime=runtime,
        runtime_roots=list(dict.fromkeys(roots)),
        external_files=list({row["path"]: row for row in external}.values()),
        release_environment=environment,
        flux_operator=declaration["flux_operator"],
        endpoint=declaration.get("endpoint", "seed"),
        init_iterations=declaration.get("init_iterations"),
        limitations=source_plan(endpoint=declaration.get("endpoint", "seed")),
        **(
            {"initial_rng_inputs": declaration["initial_rng_inputs"]}
            if declaration.get("kind") in (RNG_DEMO_KIND, SIM_DEMO_KIND)
            else {}
        ),
        **({"common_start": declaration["common_start"]} if "common_start" in declaration else {}),
    )
    if declaration.get("endpoint") == SIM_ENDPOINT:
        value["acquisition_sequence"] = list(ACQUISITION_SEQUENCE)
        value["sim_original_sources"] = sim_observation.original_sources(BASE / "betse-v1.5.0")
    _immutable(value)
    _inputs(value, inputs, initial=True)
    destination = _safe_output(destination, value)
    destination.mkdir(parents=True, exist_ok=False)
    try:
        snapshot.write_json(destination / "launch-plan.json", value)
    except BaseException as error:
        _failure(destination, error, [], "preparation", kind=value["kind"])
        raise
    return dict(plan=pin(destination / "launch-plan.json"), held=True, actual_launch=False)


def verify(plan_path, plan_sha256, *, initial=True):
    value = read(dict(path=str(plan_path), sha256=plan_sha256))
    require(
        set(value)
        == {
            "kind",
            "held",
            "automatic_retry",
            "policy",
            "stack_diagnostic",
            "demo_plan",
            "parameter_inputs",
            "source",
            "source_snapshot",
            "producers",
            "input_bundle",
            "input_files",
            "runtime",
            "runtime_roots",
            "external_files",
            "release_environment",
            "flux_operator",
            "endpoint",
            "init_iterations",
            "limitations",
        }
        | ({"initial_rng_inputs"} if "initial_rng_inputs" in value else set())
        | ({"common_start"} if "common_start" in value else set())
        | (
            {"acquisition_sequence", "sim_original_sources"}
            if value.get("endpoint") == SIM_ENDPOINT
            else set()
        ),
        "Exact launch-plan schema required",
    )
    require(
        value["kind"] == (SIM_KIND if value.get("endpoint") == SIM_ENDPOINT else KIND)
        and value["held"] is True
        and value["automatic_retry"] is False
        and value["policy"] == POLICY
        and value["limitations"] == source_plan(endpoint=value.get("endpoint", "seed")),
        "Launch domain changed",
    )
    _environment_map(value["release_environment"])
    _wall_seconds(value)
    declaration, inputs, _ = _immutable(value)
    if initial:
        _inputs(value, inputs, initial=True)
        _parameter().packet_inputs(declaration["parameter_packet"], declaration["parameter_sha256"])
    return value


def prepare_release(plan_path, output, *, plan_sha256):
    """Write a release for a verified plan without starting any computation.

    Endpoint and iteration count come from that plan, including an explicit
    None for SEED. Keep this metadata beside its plan and preserve prior files.
    """
    plan = verify(plan_path, plan_sha256)
    output = path(output, exists=False)
    require(output.parent == path(plan_path).parent, "Release must be beside its verified plan")
    snapshot.write_json(
        output,
        dict(
            kind=RELEASE_KIND,
            authorized=True,
            launch_plan_sha256=plan_sha256,
            demo_plan_sha256=plan["demo_plan"]["sha256"],
            snapshot_sha256=plan["source_snapshot"]["sha256"],
            release_environment=plan["release_environment"],
            endpoint=plan["endpoint"],
            init_iterations=plan["init_iterations"],
        ),
    )
    return pin(output)


def verify_release(plan, plan_sha256, release_path, release_sha256):
    release = read(dict(path=str(release_path), sha256=release_sha256))
    require(
        type(release.get("init_iterations")) is type(plan["init_iterations"])
        and release
        == dict(
            kind=RELEASE_KIND,
            authorized=True,
            launch_plan_sha256=plan_sha256,
            demo_plan_sha256=plan["demo_plan"]["sha256"],
            snapshot_sha256=plan["source_snapshot"]["sha256"],
            release_environment=plan["release_environment"],
            endpoint=plan["endpoint"],
            init_iterations=plan["init_iterations"],
        ),
        "Exact explicit release required",
    )
    return release


def environment(plan, output):
    require(
        not any(os.environ.get(k) for k in ("LD_PRELOAD", "LD_AUDIT", "LD_LIBRARY_PATH")),
        "Undeclared loader environment",
    )
    source = Path(plan["source"])
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("CELLS_", "BETSE_", "PYTHON", "PYTEST_"))
    }
    env.update(
        PYTHONPATH=os.pathsep.join((str(source), str(source / "src"), str(PILLOW))),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONNOUSERSITE="1",
        PYTHONOPTIMIZE="0",
        PYTHONPYCACHEPREFIX=str(source / ".unused-bytecode-cache"),
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        CUDA_VISIBLE_DEVICES="",
        JAX_PLATFORMS="cpu",
        MPLCONFIGDIR=str(output / "worker/runtime-cache/matplotlib"),
        XDG_CACHE_HOME=str(output / "worker/runtime-cache"),
        TMPDIR=str(output / "worker/runtime-cache/tmp"),
        TEMP=str(output / "worker/runtime-cache/tmp"),
        TMP=str(output / "worker/runtime-cache/tmp"),
    )
    env.update({key: "1" for key in THREADS})
    env.update(plan["release_environment"])
    return env


def _frozen(plan):
    require(
        ROOT == Path(plan["source"]) and Path(__file__).resolve() == ROOT / FILE,
        "Execute only the immutable launch producer",
    )
    require(pin(ROOT / FILE)["sha256"] == plan["producers"][FILE], "Launch producer changed")
    require(
        str(Path(sys.executable).absolute()) == plan["runtime"]["entry"]
        and pin(Path(sys.executable).resolve()) == plan["runtime"]["executable"],
        "Actual interpreter binding",
    )
    require(os.sched_getaffinity(0) == {0} and sys.flags.optimize == 0, "CPU0/assertions required")


def _entry(plan_path, plan_sha256, release_path, release_sha256, enabled, *, initial=True):
    require(enabled is True and os.environ.get(RELEASE) == "1", "Native demo launch remains held")
    plan = verify(plan_path, plan_sha256, initial=initial)
    verify_release(plan, plan_sha256, release_path, release_sha256)
    _frozen(plan)
    return plan


def error_record(error):
    """Preserve cause/context identity even when the exception formatter fails."""
    seen = {}

    def record(value):
        if value is None:
            return None
        if id(value) in seen:
            return dict(reference=seen[id(value)])
        index = len(seen)
        seen[id(value)] = index
        result = dict(identity=index, type=type(value).__module__ + "." + type(value).__qualname__)
        try:
            result["message"] = str(value)
        except BaseException as secondary:
            _keep((value, secondary))
            result["message_error_type"] = type(secondary).__name__
        result.update(
            cause=record(value.__cause__),
            context=record(value.__context__),
            suppress_context=value.__suppress_context__,
        )
        return result

    return record(error)


def _keep(value):
    try:
        _RAW_FAILURES.append(value)
    except BaseException:
        # An exhausted emergency recorder must not replace the original API error.
        pass


def _failure(output, primary, secondary, role, *, state=None, kind=KIND):
    _keep((primary, secondary, state))
    try:
        snapshot.write_json(
            output / "failure.json",
            dict(
                kind=kind,
                status="failed",
                role=role,
                primary=error_record(primary),
                secondary=[
                    dict(stage=stage, error=error_record(error)) for stage, error in secondary
                ],
                state=state,
                scientific_credit=0,
                automatic_retry=False,
                utc=utc(),
            ),
        )
    except BaseException as capture:
        _keep((primary, capture, "failure-publication"))
        try:
            primary.seed_launch_capture_error = capture
        except BaseException as attachment:
            _keep((primary, attachment, "failure-attachment"))
        try:
            os.write(
                2, b"SEED launch failure publication also failed; original exception retained\n"
            )
        except BaseException as stderr_error:
            _keep((primary, stderr_error, "failure-stderr"))


def _command(plan, role, plan_path, plan_sha256, release_path, release_sha256, output):
    return [
        str(TASKSET),
        "-c",
        "0",
        plan["runtime"]["entry"],
        "-B",
        str(Path(plan["source"]) / FILE),
        "--" + role,
        str(plan_path),
        "--plan-sha256",
        plan_sha256,
        "--release",
        str(release_path),
        "--release-sha256",
        release_sha256,
        "--output",
        str(output),
        "--enabled",
    ]


def launch(plan_path, output, *, plan_sha256, release_path, release_sha256, enabled=False):
    """Start once and return immediately. Never wait, poll, retry or kill the job."""
    plan = _entry(plan_path, plan_sha256, release_path, release_sha256, enabled)
    output = _safe_output(output, plan)
    # Protect controller metadata as well as the scientific packet.
    for p in (Path(plan_path), Path(release_path)):
        require(
            not p.is_relative_to(output) and not output.is_relative_to(p.parent),
            "Execution output overlaps launch metadata",
        )
    output.mkdir(parents=True, exist_ok=False)
    child = None
    try:
        command = _command(
            plan, "controller", plan_path, plan_sha256, release_path, release_sha256, output
        )
        snapshot.write_json(
            output / "launch-request.json",
            dict(
                plan=pin(plan_path),
                release=pin(release_path),
                command=command,
                release_environment=plan["release_environment"],
                policy=POLICY,
                worker_wall_seconds=_wall_seconds(plan),
                utc=utc(),
            ),
        )
        with (
            (output / "controller.stdout.log").open("x") as stdout,
            (output / "controller.stderr.log").open("x") as stderr,
        ):
            child = subprocess.Popen(
                command,
                cwd=plan["source"],
                env=environment(plan, output),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
                close_fds=True,
            )
        receipt = dict(
            kind=plan["kind"],
            status="launched_unobserved",
            pid=child.pid,
            plan=pin(plan_path),
            release=pin(release_path),
            policy=POLICY,
            worker_wall_seconds=_wall_seconds(plan),
            automatic_polling=False,
            automatic_retry=False,
            terminal_outcome=None,
            utc=utc(),
        )
        snapshot.write_json(output / "LAUNCH.json", receipt)
        return receipt
    except BaseException as error:
        _failure(
            output,
            error,
            [],
            "launcher",
            kind=plan["kind"],
            state=dict(
                child_pid=None if child is None else child.pid,
                child_may_be_running=child is not None,
            ),
        )
        raise


def _owned_output(output, plan, plan_path, release_path):
    output = _output_domain(output, plan, fresh=False)
    require(
        output.is_relative_to(BASE) and output.is_dir(), "Existing launch-owned output required"
    )
    request = read(pin(output / "launch-request.json"))
    require(
        request["plan"] == pin(plan_path)
        and request["release"] == pin(release_path)
        and request["policy"] == POLICY
        and request["worker_wall_seconds"] == _wall_seconds(plan)
        and request["release_environment"] == plan["release_environment"],
        "Launch ownership binding changed",
    )
    return output


def controller(plan_path, output, *, plan_sha256, release_path, release_sha256, enabled=False):
    # The launcher's durable stdout/stderr retain refusal before ownership is authenticated.
    require(enabled is True and os.environ.get(RELEASE) == "1", "Native controller remains held")
    plan = read(dict(path=str(plan_path), sha256=plan_sha256))
    output = _owned_output(output, plan, plan_path, release_path)
    # A previous claim belongs to another attempt. A duplicate must not publish
    # failure.json into that still-active or already completed attempt.
    claim = (output / "controller-started.json").open("x")
    try:
        with claim:
            json.dump(
                dict(
                    pid=os.getpid(),
                    utc=utc(),
                    policy=POLICY,
                    worker_wall_seconds=_wall_seconds(plan),
                ),
                claim,
                allow_nan=False,
            )
            claim.flush()
            os.fsync(claim.fileno())
        plan = _entry(plan_path, plan_sha256, release_path, release_sha256, enabled)
        (output / "process").mkdir()
        result = resources.run_bounded(
            _command(
                plan,
                "worker",
                plan_path,
                plan_sha256,
                release_path,
                release_sha256,
                output / "worker",
            ),
            directory=output / "process",
            cwd=plan["source"],
            env=environment(plan, output),
            timeout=_wall_seconds(plan),
            max_rss_bytes=POLICY["max_rss_bytes"],
            min_available_bytes=POLICY["reserve_bytes"],
            process_tree_memory_metric="rss",
        )
        require(
            result["status"] == "completed" and result["returncode"] == 0, "Guarded worker failed"
        )
        worker_result = read(pin(output / "worker/result.json"))
        require(
            worker_result["status"] == "source_completed_unqualified"
            and worker_result["plan_sha256"] == plan_sha256,
            "Worker terminal binding",
        )
        verify(plan_path, plan_sha256, initial=False)
        terminal = dict(
            kind=plan["kind"],
            status="source_completed_unqualified",
            process=result,
            worker=pin(output / "worker/result.json"),
            plan_sha256=plan_sha256,
            scientific_credit=0,
            automatic_retry=False,
            utc=utc(),
        )
        snapshot.write_json(output / "result.json", terminal)
        return terminal
    except BaseException as error:
        _failure(output, error, [], "controller", kind=plan["kind"])
        raise


def _maps():
    paths = set()
    for row in Path("/proc/self/maps").read_text().splitlines():
        fields = row.split(None, 5)
        if len(fields) == 6 and fields[5].startswith("/"):
            require(not fields[5].endswith(" (deleted)"), "Deleted mapped runtime file")
            paths.add(str(Path(fields[5]).resolve()))
    return [pin(p) for p in sorted(paths)]


def observe_runtime():
    from validation.betse.betse_normal_channel_join_runtime import inventory

    value = inventory()
    value["mapped_files"] = _maps()
    return value


def check_runtime(value, plan, *, before=None):
    require(
        value["executable"] == plan["runtime"]["executable"]
        and value["measured_cpu_affinity"] == [0],
        "Actual runtime/executable/CPU mismatch",
    )
    source = Path(plan["source"])
    manifest = snapshot.verify(source, manifest_sha256=plan["source_snapshot"]["sha256"])
    roots = [source, *map(Path, plan["runtime_roots"])]
    exact = {row["path"]: row["sha256"] for row in plan["external_files"]}
    loaded = value["loaded_files"]
    if plan.get("endpoint") == SIM_ENDPOINT:
        sim_observation.runtime_sources(value, plan["sim_original_sources"])
    producers = {}
    for name, row in loaded.items():
        require(set(row) == {"path", "sha256"}, "Unavailable runtime producer: " + name)
        p = Path(row["path"])
        require(pin(p) == row, "Loaded runtime file changed: " + name)
        if (
            name == "cells"
            or name.startswith(("cells.", "validation."))
            or p.is_relative_to(source)
        ):
            require(p.is_relative_to(source), "Mutable project import: " + name)
            relative = str(p.relative_to(source))
            require(
                relative in manifest["files"]
                and row["sha256"] == manifest["files"][relative]["sha256"],
                "Unbound frozen producer: " + name,
            )
            producers[relative] = row["sha256"]
        else:
            require(
                any(p.is_relative_to(root) for root in roots) or exact.get(str(p)) == row["sha256"],
                "Undeclared runtime origin: " + name,
            )
    require(
        FILE in producers and PARAMETER in producers,
        "Actual launch/parameter metadata producers missing",
    )
    for row in value["mapped_files"]:
        require(pin(row["path"]) == row, "Mapped file changed during capture")
    if before is not None:
        for name, row in before["loaded_files"].items():
            require(
                loaded.get(name) == row, "Before-source runtime producer removed/changed: " + name
            )
        for row in before["mapped_files"]:
            require(pin(row["path"]) == row, "Before-source mapped file changed")
    return producers


def _worker_environment(plan, output):
    expected = environment(plan, output.parent)
    for name in (
        *THREADS,
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONNOUSERSITE",
        "PYTHONOPTIMIZE",
        "PYTHONPYCACHEPREFIX",
        "PYTHONPATH",
        "CUDA_VISIBLE_DEVICES",
        "JAX_PLATFORMS",
        "MPLCONFIGDIR",
        "XDG_CACHE_HOME",
        "TMPDIR",
        "TEMP",
        "TMP",
    ):
        require(os.environ.get(name) == expected[name], "Worker environment mismatch: " + name)
    require(
        {k: v for k, v in os.environ.items() if k.startswith("CELLS_")}
        == plan["release_environment"],
        "Actual release environment differs from declaration",
    )
    require(not (Path(plan["source"]) / ".unused-bytecode-cache").exists(), "Stale bytecode prefix")
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    require(soft == hard == 2**30, "Exact worker address-space cap")
    require(resources.memory_available() >= POLICY["reserve_bytes"], "Host reserve unavailable")
    _parameter()._runtime_entry(plan["runtime"])


def _sim_return(returned):
    """A successful outer call still needs the complete public SIM return."""
    observation = returned.sim_observation
    require(
        observation is not None
        and observation.completed is True
        and observation.cleanup_complete is True
        and observation.primary is None
        and not observation.secondary
        and observation.record_pin is not None,
        "Completed SIM observation and typed captures required",
    )
    sim_observation.finish(
        returned, returned.sim_trial, returned.flux_operator, inherited_hooks=False
    )
    count, trial = returned.sim_time_steps_completed, returned.sim_trial
    linkage = returned.sim_linkage
    require(
        returned.sim_completed is True
        and returned.sim_imports_complete is True
        and returned.sim_cleanup_complete is True
        and returned.sim_metadata_stopped is False
        and not returned.sim_secondary
        and type(count) is int
        and 1 <= count <= 512
        and trial is not None
        and type(trial.iterations) is tuple
        and len(trial.iterations) == count
        and all(
            getattr(trial, name) is True
            for name in (
                "report_returned",
                "loop_returned",
                "context_returned",
                "before_native_pickle",
            )
        )
        and type(linkage) is dict
        and _hash(trial.identity)
        and linkage.get("trial_identity") == trial.identity
        and type(linkage.get("configured_iterations")) is int
        and linkage["configured_iterations"] == count
        and type(linkage.get("maximum_iterations")) is int
        and linkage["maximum_iterations"] == 512
        and linkage.get("selected_stop") is False
        and all(
            linkage.get(name) is True
            for name in (
                "complete_configured_calendar",
                "report_returned",
                "loop_returned",
                "context_returned",
                "before_native_pickle",
                "same_retained_simulator_and_cells",
                "distinct_current_parameters",
            )
        ),
        "Exact full SIM return/context/capture completion required",
    )


def worker(plan_path, output, *, plan_sha256, release_path, release_sha256, enabled=False):
    require(enabled is True and os.environ.get(RELEASE) == "1", "Native demo worker remains held")
    plan = read(dict(path=str(plan_path), sha256=plan_sha256))
    verify_release(plan, plan_sha256, release_path, release_sha256)
    output = _safe_output(output, plan)
    output.mkdir(parents=True, exist_ok=False)
    primary, secondary, returned, before, after = None, [], None, None, None
    filesystem = None
    numpy_origin, origin_record = None, None
    sampler = None
    entered = False
    try:
        plan = _entry(plan_path, plan_sha256, release_path, release_sha256, enabled)
        _worker_environment(plan, output)
        filesystem = _filesystem(plan, output)
        _temporary_directory(output, filesystem)
        if plan["stack_diagnostic"]:
            sampler = StackSampler(output)
            # Retain before arming; even a failed setup/cancel cannot orphan its fd.
            _STACK_SAMPLERS.append(sampler)
            sampler.start()
        numpy_origin = _numpy_origin(plan)
        before = observe_runtime()
        snapshot.write_json(output / "runtime-before.json", before)
        check_runtime(before, plan)
        # Observe the original import reached by the existing source chain;
        # do not preload NumPy or invoke copy with synthetic probe arguments.
        with numpy_origin.capture():
            try:
                module = _demo()
                require(
                    Path(module.__file__).resolve() == Path(plan["source"]) / DEMO
                    and pin(module.__file__)["sha256"] == plan["producers"][DEMO],
                    "Actual frozen public entry",
                )
                entered = True
                returned = module.run_demo(
                    plan["demo_plan"]["path"],
                    output / "demo",
                    plan_sha256=plan["demo_plan"]["sha256"],
                    enabled=True,
                )
                if "common_start" in plan:
                    initial_rng.common_return(
                        returned.common_start_raw_return, plan["common_start"]
                    )
                    require(
                        returned.common_start_record is returned.common_start_raw_return
                        and returned.common_start_capture is not None
                        and returned.common_start_capture["status"] == "saved",
                        "Missing completed common-start return/capture",
                    )
                filesystem.check()
                require(
                    returned.methods_completed is True
                    and returned.evidence_completed is True
                    and returned.primary is None
                    and not returned.secondary,
                    "Incomplete demonstration return",
                )
                if plan["endpoint"] == "init_short_history":
                    require(
                        returned.endpoint == "init_short_history"
                        and type(returned.init_iterations) is int
                        and returned.init_iterations == plan["init_iterations"]
                        and returned.init_short_history_completed is True
                        and returned.init_first_step_completed is False
                        and type(returned.init_time_steps_completed) is int
                        and returned.init_time_steps_completed == plan["init_iterations"],
                        "Exact complete short-history worker return required",
                    )
                if plan["endpoint"] in ("init_terminal", SIM_ENDPOINT):
                    require(
                        returned.endpoint == plan["endpoint"]
                        and returned.init_iterations is None
                        and returned.init_terminal_completed is True
                        and returned.init_first_step_completed is False
                        and returned.init_short_history_completed is False
                        and type(returned.init_time_steps_completed) is int
                        and 1 <= returned.init_time_steps_completed <= 512,
                        "Exact natural complete-INIT worker return required",
                    )
                if plan["endpoint"] == SIM_ENDPOINT:
                    _sim_return(returned)

            except BaseException as error:
                primary = error
                raise
    except BaseException as error:
        if primary is None:
            primary = error
        elif error is not primary:
            secondary.append(("numpy-copy-origin-exit", error))
    finally:
        if numpy_origin is not None:
            try:
                origin_record = numpy_origin.record()
                snapshot.write_json(output / "numpy-copy-origin.json", origin_record)
                if primary is None:
                    _numpy_origin_complete(origin_record)
            except BaseException as error:
                secondary.append(("numpy-copy-origin", error))
        if filesystem is not None:
            for stage, action in (
                ("filesystem-check", filesystem.check),
                ("filesystem-record", lambda: filesystem.record()),
            ):
                try:
                    value = action()
                    if stage == "filesystem-record":
                        snapshot.write_json(output / "filesystem.json", value)
                except BaseException as error:
                    secondary.append((stage, error))
        # Each independent observation is attempted; none may replace an API primary.
        for stage, action in (
            ("runtime-after", lambda: observe_runtime()),
            ("source-after", lambda: verify(plan_path, plan_sha256, initial=False)),
        ):
            try:
                value = action()
                if stage == "runtime-after":
                    after = value
                    snapshot.write_json(output / "runtime-after.json", after)
                    check_runtime(after, plan, before=before)
                else:
                    snapshot.write_json(
                        output / "source-after.json",
                        dict(
                            source_snapshot=value["source_snapshot"], producers=value["producers"]
                        ),
                    )
            except BaseException as error:
                secondary.append((stage, error))
        if filesystem is not None:
            try:
                filesystem.check()
            except BaseException as error:
                secondary.append(("filesystem-final-check", error))
        if sampler is not None:
            try:
                sampler.stop()
            except BaseException as error:
                secondary.append(("stack-sampling-stop", error))
            try:
                snapshot.write_json(output / "stack-sampling-final.json", sampler.record())
            except BaseException as error:
                secondary.append(("stack-sampling-record", error))
    observation_summary = None
    if plan["endpoint"] == SIM_ENDPOINT and returned is not None:
        try:
            if primary is None and not secondary:
                _sim_return(returned)
            if returned.sim_observation is not None and returned.sim_observation.cleanup_complete:
                observation_summary = sim_observation.summary(returned)
        except BaseException as error:
            secondary.append(("completed-SIM-observation-final", error))
            if primary is None:
                primary = error
    state = dict(
        plan_sha256=plan_sha256,
        public_entry_attempted=entered,
        public_entry_returned=returned is not None,
        runtime_before_available=before is not None,
        runtime_after_available=after is not None,
        demo_directory=str(output / "demo"),
        live_owner_serialized=False,
        filesystem_audit_installed=filesystem is not None,
        numpy_copy_origin_available=origin_record is not None,
        numpy_copy_origin_completed=(
            type(origin_record) is dict and origin_record.get("completed") is True
        ),
        stack_diagnostic=plan.get("stack_diagnostic"),
        **(dict(sim_observation=observation_summary) if plan["endpoint"] == SIM_ENDPOINT else {}),
    )
    if primary is None and secondary:
        primary = secondary[0][1]
    if primary is not None:
        _failure(output, primary, secondary, "worker", state=state, kind=plan["kind"])
        raise primary
    terminal = dict(
        kind=plan["kind"],
        status="source_completed_unqualified",
        scientific_credit=0,
        flux_operator=plan["flux_operator"],
        endpoint=plan["endpoint"],
        init_iterations=plan["init_iterations"],
        **state,
        utc=utc(),
    )
    try:
        snapshot.write_json(output / "result.json", terminal)
        filesystem.check()
    except BaseException as error:
        _failure(output, error, [], "worker-terminal", state=state, kind=plan["kind"])
        raise
    return terminal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for name in ("prepare", "launch", "controller", "worker"):
        modes.add_argument("--" + name, type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan-sha256")
    parser.add_argument("--demo-plan-sha256")
    parser.add_argument("--release-environment", type=Path)
    parser.add_argument("--release-environment-sha256")
    parser.add_argument("--input-bundle", type=Path)
    parser.add_argument("--input-bundle-sha256")
    parser.add_argument("--release", type=Path)
    parser.add_argument("--release-sha256")
    parser.add_argument("--enabled", action="store_true")
    parser.add_argument("--stack-diagnostic", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
        result = prepare(
            args.prepare,
            args.output,
            demo_plan_sha256=args.demo_plan_sha256,
            release_environment=read(
                dict(path=str(args.release_environment), sha256=args.release_environment_sha256)
            ),
            input_bundle=dict(path=str(args.input_bundle), sha256=args.input_bundle_sha256),
            stack_diagnostic=args.stack_diagnostic,
        )
    else:
        require(not args.stack_diagnostic, "Diagnostic mode must be bound during preparation")
        resource.setrlimit(
            resource.RLIMIT_AS, (2**30, 2**30) if args.worker else (512 * 2**20, 2**30)
        )
        operation = worker if args.worker else controller if args.controller else launch
        result = operation(
            args.worker or args.controller or args.launch,
            args.output,
            plan_sha256=args.plan_sha256,
            release_path=args.release,
            release_sha256=args.release_sha256,
            enabled=args.enabled,
        )
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
