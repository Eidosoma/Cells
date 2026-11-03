"""Held one-shot detached controller for the genuine public SEED demonstration.

Preparation and launch are metadata only. The fresh frozen worker alone calls
``native_seed_demo.run_demo``. Its release environment is an explicit reviewed
input, never a discovered or automatically enabled collection of source gates.
"""

import argparse
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
from datetime import datetime, timezone
from pathlib import Path

from validation import source_snapshot as snapshot
from validation.betse import betse_normal_ecm_molecule_qualification_resources as resources

ROOT = Path(__file__).resolve().parents[2]
BASE = Path("/mnt/workspaces/Cells")
FILE = "validation/betse/native_seed_demo_launch.py"
TEST = "tests/unit/test_native_seed_demo_launch.py"
SOFTWARE = "validation/betse/native_seed_demo_launch_software.py"
OWNED = (FILE, TEST, SOFTWARE)
DEMO = "validation/betse/native_seed_demo.py"
PARAMETER = "validation/betse/betse_native_parameter_world_ready_qualification.py"
INPUTS = "validation/betse/native_seed_demo_inputs.py"
PRODUCERS = (*OWNED, DEMO, PARAMETER, INPUTS)
KIND = "cells.genuine_seed_demo_detached_launch@2"
RELEASE_KIND = "cells.genuine_seed_demo_detached_release@1"
RELEASE = "CELLS_NATIVE_SEED_DEMO_LAUNCH_RELEASED"
DEMO_RELEASE = "CELLS_NATIVE_SEED_DEMO_RELEASED"
POLICY = dict(cpu=0, threads=1, max_rss_bytes=2**30, wall_seconds=7200, reserve_bytes=8 * 2**30)
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


def require(value, message):
    if not value:
        raise ValueError(message)


def source_plan():
    return dict(
        kind=KIND,
        held=True,
        policy=POLICY,
        actual_entry="native_seed_demo.run_demo",
        release_environment="explicit exact map, no discovered gates",
        detached=True,
        automatic_retry=False,
        automatic_polling=False,
        fresh_process_per_flux_mode=True,
        complete_original_inputs="Exact pair manifest; selected mode only before consumption",
        postrun_inputs="Original selected file bytes only, never fresh directory epochs",
        owner_hydration=False,
        source_or_independent_physical_acceptance=False,
        runtime_scope="Actual loaded file/map inventories; not a complete prelaunch library proof",
    )


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
    for name, row in sorted(value["source_inventory"]["files"].items()):
        snapshot.relative_path(name)
        require(_hash(row["sha256"]), "Exact original input digest required")
        result.append(dict(path=str(config / name), sha256=row["sha256"]))
    require(bool(result), "Complete original input roster required")
    return result


def _inputs(plan, parameter_inputs, *, initial):
    bundle = plan["input_bundle"]
    value = read(bundle)
    mode = plan["flux_operator"]
    row = value["modes"][mode]
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


def _immutable(plan):
    """Recheck byte provenance without reopening consumed native directory epochs."""
    declaration = read(plan["demo_plan"])
    inputs = read(plan["parameter_inputs"])
    source = Path(plan["source"])
    manifest = snapshot.verify(source, manifest_sha256=plan["source_snapshot"]["sha256"])
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
        inputs["source_snapshot"] == plan["source_snapshot"]
        and inputs["runtime"] == plan["runtime"],
        "Parameter runtime/snapshot binding",
    )
    require(
        plan["producers"] == {name: manifest["files"][name]["sha256"] for name in PRODUCERS},
        "Producer roster",
    )
    for row in plan["external_files"]:
        bound(row)
    _inputs(plan, inputs, initial=False)
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


def prepare(prepared, destination, *, demo_plan_sha256, release_environment, input_bundle):
    """Bind an already frozen demo packet; never adopt or enable its source gates."""
    prepared = path(prepared)
    demo_pin = dict(path=str(prepared / "demo-plan.json"), sha256=demo_plan_sha256)
    declaration = read(demo_pin)
    inputs_pin = dict(path=str(prepared / "inputs.json"), sha256=declaration["parameter_sha256"])
    inputs = read(inputs_pin)
    source = prepared / "source"
    manifest = snapshot.verify(source, manifest_sha256=declaration["snapshot_sha256"])
    require(
        all(name in manifest["files"] for name in PRODUCERS),
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
        kind=KIND,
        held=True,
        automatic_retry=False,
        policy=POLICY,
        demo_plan=demo_pin,
        parameter_inputs=inputs_pin,
        source=str(source),
        source_snapshot=pin(source / "SNAPSHOT.json"),
        producers={name: manifest["files"][name]["sha256"] for name in PRODUCERS},
        input_bundle=dict(input_bundle),
        input_files=_input_files(input_bundle, declaration["flux_operator"]),
        runtime=runtime,
        runtime_roots=list(dict.fromkeys(roots)),
        external_files=list({row["path"]: row for row in external}.values()),
        release_environment=environment,
        flux_operator=declaration["flux_operator"],
        limitations=source_plan(),
    )
    _immutable(value)
    _inputs(value, inputs, initial=True)
    destination = _safe_output(destination, value)
    destination.mkdir(parents=True, exist_ok=False)
    try:
        snapshot.write_json(destination / "launch-plan.json", value)
    except BaseException as error:
        _failure(destination, error, [], "preparation")
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
            "limitations",
        },
        "Exact launch-plan schema required",
    )
    require(
        value["kind"] == KIND
        and value["held"] is True
        and value["automatic_retry"] is False
        and value["policy"] == POLICY
        and value["limitations"] == source_plan(),
        "Launch domain changed",
    )
    _environment_map(value["release_environment"])
    declaration, inputs, _ = _immutable(value)
    if initial:
        _inputs(value, inputs, initial=True)
        _parameter().packet_inputs(declaration["parameter_packet"], declaration["parameter_sha256"])
    return value


def verify_release(plan, plan_sha256, release_path, release_sha256):
    release = read(dict(path=str(release_path), sha256=release_sha256))
    require(
        release
        == dict(
            kind=RELEASE_KIND,
            authorized=True,
            launch_plan_sha256=plan_sha256,
            demo_plan_sha256=plan["demo_plan"]["sha256"],
            snapshot_sha256=plan["source_snapshot"]["sha256"],
            release_environment=plan["release_environment"],
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


def _failure(output, primary, secondary, role, *, state=None):
    _keep((primary, secondary, state))
    try:
        snapshot.write_json(
            output / "failure.json",
            dict(
                kind=KIND,
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
            kind=KIND,
            status="launched_unobserved",
            pid=child.pid,
            plan=pin(plan_path),
            release=pin(release_path),
            policy=POLICY,
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
            json.dump(dict(pid=os.getpid(), utc=utc(), policy=POLICY), claim, allow_nan=False)
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
            timeout=POLICY["wall_seconds"],
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
            kind=KIND,
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
        _failure(output, error, [], "controller")
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


def _worker_environment(plan):
    expected = environment(plan, BASE / "unused")
    for name in (
        *THREADS,
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONNOUSERSITE",
        "PYTHONOPTIMIZE",
        "PYTHONPYCACHEPREFIX",
        "PYTHONPATH",
        "CUDA_VISIBLE_DEVICES",
        "JAX_PLATFORMS",
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


def worker(plan_path, output, *, plan_sha256, release_path, release_sha256, enabled=False):
    require(enabled is True and os.environ.get(RELEASE) == "1", "Native demo worker remains held")
    plan = read(dict(path=str(plan_path), sha256=plan_sha256))
    verify_release(plan, plan_sha256, release_path, release_sha256)
    output = _safe_output(output, plan)
    output.mkdir(parents=True, exist_ok=False)
    primary, secondary, returned, before, after = None, [], None, None, None
    entered = False
    try:
        plan = _entry(plan_path, plan_sha256, release_path, release_sha256, enabled)
        _worker_environment(plan)
        before = observe_runtime()
        snapshot.write_json(output / "runtime-before.json", before)
        check_runtime(before, plan)
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
        require(
            returned.methods_completed is True
            and returned.evidence_completed is True
            and returned.primary is None
            and not returned.secondary,
            "Incomplete demonstration return",
        )
    except BaseException as error:
        primary = error
    finally:
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
    state = dict(
        plan_sha256=plan_sha256,
        public_entry_attempted=entered,
        public_entry_returned=returned is not None,
        runtime_before_available=before is not None,
        runtime_after_available=after is not None,
        demo_directory=str(output / "demo"),
        live_owner_serialized=False,
    )
    if primary is None and secondary:
        primary = secondary[0][1]
    if primary is not None:
        _failure(output, primary, secondary, "worker", state=state)
        raise primary
    terminal = dict(
        kind=KIND,
        status="source_completed_unqualified",
        scientific_credit=0,
        flux_operator=plan["flux_operator"],
        **state,
        utc=utc(),
    )
    try:
        snapshot.write_json(output / "result.json", terminal)
    except BaseException as error:
        _failure(output, error, [], "worker-terminal", state=state)
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
        )
    else:
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
