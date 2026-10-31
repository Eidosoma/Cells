"""Prepare and run bounded real single-cell prefix diagnostics.

This runner exercises the owned-image request, its authentication replays and
the ordinary caller through near_neigh. It is NOT an independent geometry
oracle: even a completed prefix receives no qualification or physical credit.
Preparation imports no model. Execution requires a separate, exact-plan release
and runs one declared case per guarded process; it never retries a failure.
"""

import argparse
import ast
import json
import os
import resource
import runpy
import sys
import traceback
from contextlib import contextmanager
from pathlib import Path

from validation import source_snapshot
from validation.betse import betse_mesh_lifecycle_preparation_guard as guard
from validation.betse import betse_native_membrane_initialization_archive as archive

ROOT = Path(__file__).resolve().parents[2]
BASE = Path("/mnt/workspaces/Cells")
OWN = "validation/betse/native_single_cell_prefix_qualification.py"
TEST = "tests/unit/test_native_single_cell_prefix_qualification.py"
CLOSURE = "agent-work/cells-worker-01/workfiles/betse_normal_ecm_reviewed_successors_resources.py"
CASES = ("caller-single-square-cache", "caller-single-hex-cache")
KINDS = ("cells.single_cell_prefix_diagnostic_plan@1", "cells.single_cell_prefix_release@1")
STAGES = ("owned_image_request", "initial_pre_mesh", "core_request", "geometry_request", "geometry")
LIMITS = dict(timeout=480, max_rss_bytes=2**30, min_available_bytes=8 * 2**30)
NATIVE = BASE / "betse-v1.5.0"
DEFAULTS = NATIVE / "betse/data/yaml/sim_config.yaml"
DEFAULTS_SHA256 = "7ed5a32f9fc256c541db63090aeed6d0207bf706d2847b27269d6bc8c9e85415"
CONFIGURATION = {"world options": {"cell height": 1e-5, "cell spacing": 2.6e-8}}
NO_CREDIT = dict(
    independent_comparison_performed=False,
    scientific_qualification=False,
    physical_geometry_admitted=False,
    ordinary_checkpoint_admitted=False,
    invalidated_postcut_owners_cleared=0,
)


def read(path):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > 16 * 2**20:
        raise ValueError("Require bounded unlinked metadata")
    return json.loads(path.read_text())


def write(path, value):
    source_snapshot.write_json(Path(path), value)


def output_path(path):
    path = Path(path).absolute()
    if not path.is_relative_to(BASE) or path == BASE or ".." in path.parts:
        raise ValueError("Outputs must be below /mnt/workspaces/Cells")
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Linked output directory")
    return path


def pin(path):
    path = Path(path).absolute()
    if path.is_symlink() or not path.is_file():
        raise ValueError("Require a regular input file: " + str(path))
    return dict(path=str(path), sha256=source_snapshot.digest(path))


def execution_output(path, prepared, plan):
    path = output_path(path)
    for protected in (Path(prepared), NATIVE, *(Path(p) for p in plan["runtime_paths"])):
        if path.is_relative_to(protected) or protected.is_relative_to(path):
            raise ValueError("Execution output overlaps prepared source or runtime inputs")
    return path


def verify_pins(rows):
    for row in rows:
        if pin(row["path"]) != row:
            raise ValueError("Changed external input: " + row["path"])


def prepare(destination, *, repository=ROOT, cpu=3, runtime_paths=()):
    """Freeze current Git source, never restore a historical implementation.

    runtime_paths explicitly names required overlays, e.g. the existing Pillow
    overlay. Inherited PYTHONPATH is not forwarded. These are recorded runtime
    dependencies, not a claim of hermetic scientific qualification.
    """
    destination = execution_output(destination, repository, {"runtime_paths": runtime_paths})
    if type(cpu) is not int or cpu not in os.sched_getaffinity(0):
        raise ValueError("Select an available CPU")
    destination.mkdir(parents=True, exist_ok=False)
    try:
        closure = runpy.run_path(str(repository / CLOSURE))["closure"]
        files = closure(repository, [OWN, TEST])
        files[CLOSURE] = source_snapshot.digest(repository / CLOSURE)
        # Include declared JSON sidecars alongside imported Python modules.
        # This is intentionally not described as a general resource resolver.
        for parent in {Path(name).parent for name in files}:
            for path in (repository / parent).glob("*.json"):
                files[str(path.relative_to(repository))] = source_snapshot.digest(path)
        external = {str(DEFAULTS): DEFAULTS_SHA256}
        # Literal native authority tables already used by the model retain
        # their original paths and pins. No native source is rewritten here.
        for module in ("caller_lattice", "image_mask"):
            name = f"src/cells/processes/betse_native_single_cell_{module}_source.py"
            tree = ast.parse((repository / name).read_text())
            pins = next(
                ast.literal_eval(node.value)
                for node in tree.body
                if isinstance(node, ast.Assign)
                and any(isinstance(n, ast.Name) and n.id == "NATIVE_PINS" for n in node.targets)
            )
            for relative, expected in pins.items():
                path = str(NATIVE / source_snapshot.relative_path(relative))
                if path in external and external[path] != expected:
                    raise ValueError("Conflicting native authority pins")
                external[path] = expected
        overlays = []
        for raw in runtime_paths:
            path = Path(raw).absolute()
            if not path.is_dir() or path.is_relative_to(repository) or path.is_symlink():
                raise ValueError("Require an explicit external runtime overlay")
            overlays.append(str(path))
            for file in path.rglob("*"):
                if file.is_file() and "__pycache__" not in file.parts:
                    row = pin(file)
                    external[row["path"]] = row["sha256"]
        pins = [dict(path=name, sha256=value) for name, value in sorted(external.items())]
        verify_pins(pins)
        frozen = destination / "source"
        snap = source_snapshot.freeze(repository, frozen, {name: name for name in files})
        plan = dict(
            kind=KINDS[0],
            purpose="source_prefix_diagnostic_only",
            cases=list(CASES),
            configuration=CONFIGURATION,
            scalar_provenance=dict(path=str(DEFAULTS), sha256=DEFAULTS_SHA256, lines=[160, 164]),
            snapshot_sha256=source_snapshot.digest(frozen / "SNAPSHOT.json"),
            git_revision=snap["git_revision"],
            runner_sha256=source_snapshot.digest(frozen / OWN),
            external_inputs=pins,
            runtime_paths=overlays,
            interpreter=str(Path(sys.executable).absolute()),
            cpu=cpu,
            limits=LIMITS,
            stop_after="near_neigh",
            source_review_required_before_release=True,
            full_prefix_independent_oracle="unavailable; completion cannot grant qualification",
            automatic_retry=False,
            **NO_CREDIT,
        )
        source_snapshot.assert_checkout_unchanged(frozen)
        verify_pins(pins)
        write(destination / "plan.json", plan)
        (destination / "plan.json").chmod(0o444)
        return plan
    except BaseException:
        write(
            destination / "preparation-failure.json",
            dict(traceback=traceback.format_exc(), **NO_CREDIT),
        )
        raise


def verify_plan(prepared, expected_sha256):
    prepared = output_path(prepared)
    if source_snapshot.digest(prepared / "plan.json") != expected_sha256:
        raise ValueError("Changed diagnostic plan")
    plan = read(prepared / "plan.json")
    if (
        (prepared / "preparation-failure.json").exists()
        or plan.get("kind") != KINDS[0]
        or plan.get("purpose") != "source_prefix_diagnostic_only"
        or plan.get("cases") != list(CASES)
        or plan.get("configuration") != CONFIGURATION
        or plan.get("limits") != LIMITS
        or plan.get("stop_after") != "near_neigh"
        or any(plan.get(key) != value for key, value in NO_CREDIT.items())
        or type(plan.get("cpu")) is not int
    ):
        raise ValueError("Incomplete or widened diagnostic plan")
    source = prepared / "source"
    source_snapshot.verify(source, manifest_sha256=plan["snapshot_sha256"])
    if source_snapshot.digest(source / OWN) != plan["runner_sha256"]:
        raise ValueError("Changed diagnostic worker")
    verify_pins(plan["external_inputs"])
    return plan


def verify_release(prepared, expected_sha256, release_path, case):
    plan = verify_plan(prepared, expected_sha256)
    release = read(release_path)
    review = release.get("source_review")
    if (
        release.get("kind") != KINDS[1]
        or release.get("plan_sha256") != expected_sha256
        or release.get("snapshot_sha256") != plan["snapshot_sha256"]
        or release.get("case") != case
        or case not in CASES
        or release.get("allow_actual_source_diagnostic") is not True
        or release.get("scientific_qualification") is not False
        or type(review) is not dict
        or set(review) != {"path", "sha256"}
    ):
        raise ValueError("An exact-case, exact-source diagnostic release is required")
    verify_pins([review])
    if os.sched_getaffinity(0) != {plan["cpu"]}:
        raise ValueError("Require the declared single CPU")
    return plan


def environment(source, plan):
    env = dict(os.environ)
    for name in ("PYTHONHOME", "PYTHONSTARTUP", "PYTHONINSPECT", "CELLS_BETSE_SOURCE"):
        env.pop(name, None)
    env.update(
        PYTHONPATH=os.pathsep.join([str(source), str(source / "src"), *plan["runtime_paths"]]),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPYCACHEPREFIX=str(source / ".unused-bytecode-cache"),
        PYTHONNOUSERSITE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
        JAX_PLATFORMS="cpu",
    )
    return env


def exception_record(error):
    """Retain both cause and context edges, including cycles and suppression."""
    nodes, seen = [], {}

    def visit(value):
        if value is None:
            return None
        if id(value) in seen:
            return seen[id(value)]
        index = len(nodes)
        seen[id(value)] = index
        nodes.append(None)
        nodes[index] = dict(
            type=type(value).__module__ + "." + type(value).__qualname__,
            message=str(value),
            stage=getattr(value, "stage", None),
            traceback="".join(traceback.format_tb(value.__traceback__)),
            suppressed_context=value.__suppress_context__,
            cause=visit(value.__cause__),
            context=visit(value.__context__),
            source_error=visit(getattr(value, "source_error", None)),
            capture_error=visit(getattr(value, "capture_error", None)),
        )
        return index

    return dict(root=visit(error), nodes=nodes)


class Evidence:
    """Separate typed capture failures from source failures; never repair data."""

    def __init__(self, output):
        self.output, self.rows = output, []

    def save(self, label, value):
        name = f"capture-{len(self.rows):04d}.json"
        row = dict(label=label, path=name)
        try:
            write(self.output / name, archive.snapshot(value))
            row.update(status="saved", sha256=source_snapshot.digest(self.output / name))
        except Exception as error:
            # A partial JSON file, if any, is retained and never overwritten.
            row.update(status="capture_failed", error=exception_record(error))
        self.rows.append(row)
        return row["status"] == "saved"

    def failure(self, error):
        pending, seen = [error], set()
        while pending:
            value = pending.pop()
            if value is None or id(value) in seen:
                continue
            seen.add(id(value))
            for name in ("request", "trial", "parent_request", "parent_state", "upstream_trial"):
                if getattr(value, name, None) is not None:
                    self.save(type(value).__name__ + "." + name, getattr(value, name))
            # Live owner graphs cannot be serialized as executable authority.
            # Preserve each available field independently and disclose gaps.
            partial = getattr(value, "partial", None)
            if type(partial) is dict:
                for key, field in partial.items():
                    self.save(type(value).__name__ + ".partial." + str(key), field)
            elif partial is not None:
                self.save(type(value).__name__ + ".partial", partial)
            pending.extend(
                (
                    value.__cause__,
                    value.__context__,
                    getattr(value, "source_error", None),
                    getattr(value, "capture_error", None),
                )
            )


class WorkLog:
    """Observed Python entries and profile-visible C entries, never case counts.

    Native extensions can do more work than sys.setprofile exposes. The log
    explicitly records entry attempts, not successful returns. Existing source
    ledgers remain non-additive observations of the same execution.
    """

    def __init__(self, output, source):
        self.path, self.source = output / "work.jsonl", str(source) + os.sep
        self.phase, self.count = "imports", 0
        self.trace_count = 0
        self.counts = {}
        self.failure = None

    def record(self, stream, row):
        """Count recursive codec work without emitting a line per scalar.

        Keep every literal source/kernel entry in order, plus the first entry
        at each other call site and phase. All repetitions remain in exact
        counters; these are computational attempts, not independent cases.
        """
        key = tuple(row[k] for k in ("phase", "event", "source", "function", "line", "c_callable"))
        new = key not in self.counts
        if new:
            if len(self.counts) >= 4096:
                raise RuntimeError("Source work log exceeded its distinct-call-site allowance")
            self.counts[key] = dict(**row, attempts=0, first_sequence=self.count)
        counter = self.counts[key]
        counter["attempts"] += 1
        counter["last_sequence"] = self.count
        self.count += 1
        literal = row["source"].endswith(("_source.py", "_kernel.py"))
        if new or literal:
            if self.trace_count >= 100000:
                raise RuntimeError("Source entry log exceeded its diagnostic allowance")
            stream.write(json.dumps(row) + "\n")
            stream.flush()
            self.trace_count += 1

    def summary(self):
        return dict(
            observed_entry_attempts=self.count,
            ordered_trace_entries=self.trace_count,
            call_sites=list(self.counts.values()),
            aggregation=(
                "All calls counted by site and phase; ordered trace keeps first occurrences "
                "and literal source/kernel entries"
            ),
            complete_native_operation_count=False,
            independent_case_credit=0,
        )

    @contextmanager
    def active(self):
        previous = sys.getprofile()
        with self.path.open("x") as stream:

            def profile(frame, event, arg):
                if previous is not None:
                    previous(frame, event, arg)
                filename = frame.f_code.co_filename
                if event not in ("call", "c_call") or not filename.startswith(self.source):
                    return
                relative = filename[len(self.source) :]
                if not relative.startswith(("src/cells/", "validation/betse/")) or relative == OWN:
                    return
                row = dict(
                    sequence=self.count,
                    phase=self.phase,
                    event=event,
                    source=relative,
                    function=frame.f_code.co_qualname,
                    line=frame.f_code.co_firstlineno,
                    c_callable=getattr(arg, "__qualname__", None) if event == "c_call" else None,
                    entry_is_success_or_independent_case=False,
                )
                try:
                    self.record(stream, row)
                except Exception as error:
                    self.failure = exception_record(error)
                    raise

            sys.setprofile(profile)
            try:
                yield
            finally:
                primary = sys.exception()
                sys.setprofile(previous)
                try:
                    stream.flush()
                    os.fsync(stream.fileno())
                    write(self.path.with_name("work-counts.json"), self.summary())
                except Exception as error:
                    self.failure = exception_record(error)
                    if primary is None:
                        raise


def _steps(case, output, configuration):
    # Lazy scientific imports are below the worker's release/source/resource
    # gates. No fixture helper, validator or exporter runs during preparation.
    from cells.processes import betse_initial_mesh_preparation as initial
    from cells.processes import betse_native_single_cell_core_preparation as core
    from cells.processes import betse_native_single_cell_initial_geometry as geometry
    from validation.betse import betse_initial_mesh_preparation_fixtures as fixtures

    values = {}

    def fixture():
        values["initial_request"], raw = fixtures.caller(case, output)
        return dict(request=values["initial_request"], native_comparison_inputs=raw)

    def pre_mesh():
        values["initial_state"] = initial.prepare(values["initial_request"])
        return values["initial_state"]

    def core_request():
        values["core_request"] = core.from_initial(
            values["initial_request"], values["initial_state"], law_id=core.LAW_ID
        )
        return values["core_request"]

    def geometry_request():
        values["geometry_request"] = geometry.from_core(
            values["core_request"], configuration, law_id=geometry.LAW_ID
        )
        return values["geometry_request"]

    def execute():
        values["owner"] = geometry.prepare(values["geometry_request"])
        # Inspection of the sealed trial does not call validate_state/export
        # helpers that would silently launch another authentication replay.
        return values["owner"].trial

    return tuple(
        zip(STAGES, (fixture, pre_mesh, core_request, geometry_request, execute), strict=True)
    )


def run_stages(steps, evidence, work):
    completed, failed, error = [], None, None
    for stage, action in steps:
        work.phase = stage
        try:
            value = action()
        except Exception as primary:
            failed, error = stage, exception_record(primary)
            evidence.failure(primary)
            break
        # CPython disables a profiling hook after its exception. A source
        # helper can catch that error and return normally; that return must
        # never turn an interrupted observation into a completed diagnostic.
        if getattr(work, "failure", None):
            evidence.save(stage + ":interrupted-return", value)
            failed = stage + ":observer"
            break
        # Capture before taking the next step. A failed capture ends the case
        # without treating the completed source call as a scientific failure.
        if not evidence.save(stage, value):
            failed = stage + ":capture"
            break
        completed.append(stage)
    return dict(
        status="source_completed_unqualified" if failed is None else "diagnostic_failed",
        completed_stages=completed,
        failed_stage=failed,
        source_error=None if getattr(work, "failure", None) else error,
        observer_error=getattr(work, "failure", None),
        interrupted_exception_graph=error if getattr(work, "failure", None) else None,
        captures=evidence.rows,
        observed_source_entry_attempts=work.count,
        work_log_is_complete_native_operation_count=False,
        independent_cases=1,
        accepted_cases=0,
        **NO_CREDIT,
    )


def runtime_inventory(source):
    rows = {}
    for name, module in list(sys.modules.items()):
        raw = getattr(module, "__file__", None)
        if not raw or not Path(raw).is_file():
            continue
        path = Path(raw).resolve()
        if name == "cells" or name.startswith(("cells.", "validation.")):
            if not path.is_relative_to(source):
                raise ValueError("Runtime Cells source escaped the frozen snapshot: " + name)
        rows[name] = pin(path)
    return rows


def worker(prepared, plan_sha256, release, case, output):
    plan = verify_release(prepared, plan_sha256, release, case)
    source = Path(prepared) / "source"
    if ROOT != source or str(Path(sys.executable).absolute()) != plan["interpreter"]:
        raise ValueError("Worker must use the declared interpreter and immutable source")
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    output = execution_output(output, prepared, plan)
    evidence, work = Evidence(output), WorkLog(output, source)
    result = None
    try:
        with work.active():
            result = run_stages(_steps(case, output, plan["configuration"]), evidence, work)
        write(output / "runtime-producers.json", runtime_inventory(source))
        verify_plan(prepared, plan_sha256)
    except Exception as error:
        evidence.failure(error)
        result = dict(
            status="diagnostic_failed",
            failed_stage=work.phase,
            source_error=None if work.failure else exception_record(error),
            observer_error=work.failure,
            interrupted_exception_graph=exception_record(error) if work.failure else None,
            prior_result=result,
            captures=evidence.rows,
            observed_source_entry_attempts=work.count,
            accepted_cases=0,
            **NO_CREDIT,
        )
    write(output / "diagnostic.json", dict(case=case, plan_sha256=plan_sha256, **result))
    return 0 if result["status"] == "source_completed_unqualified" else 1


def launch(prepared, plan_sha256, release, case, output):
    plan = verify_release(prepared, plan_sha256, release, case)
    output = execution_output(output, prepared, plan)
    output.mkdir(parents=True, exist_ok=False)
    source = Path(prepared) / "source"
    command = [
        plan["interpreter"],
        "-B",
        "-m",
        "validation.betse.native_single_cell_prefix_qualification",
        "worker",
        "--prepared",
        str(prepared),
        "--plan-sha256",
        plan_sha256,
        "--release",
        str(release),
        "--case",
        case,
        "--output",
        str(output),
    ]
    failure = None
    result = None
    try:
        (output / "process").mkdir()
        write(
            output / "inputs.json",
            dict(case=case, plan_sha256=plan_sha256, release=pin(release), **NO_CREDIT),
        )
        if guard.memory_available() < 12 * 2**30:
            raise RuntimeError("Diagnostic launch requires 12 GiB available host memory")
        result = guard.run_bounded(
            command,
            directory=output / "process",
            cwd=source,
            env=environment(source, plan),
            **plan["limits"],
        )
        diagnostic = read(output / "diagnostic.json")
        if diagnostic["status"] != "source_completed_unqualified":
            raise RuntimeError("Worker did not complete the declared prefix")
    except Exception as error:
        failure = exception_record(error)
    record = dict(
        status="failed" if failure else "completed_unqualified",
        case=case,
        process=result,
        failure=failure,
        diagnostic=pin(output / "diagnostic.json")
        if (output / "diagnostic.json").is_file()
        else None,
        process_receipts=[
            pin(path)
            for name in ("result.json", "failure.json", "resource-stop.json")
            if (path := output / "process" / name).is_file()
        ],
        automatic_retry=False,
        accepted_cases=0,
        **NO_CREDIT,
    )
    write(output / ("failure.json" if failure else "result.json"), record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    preparation = sub.add_parser("prepare")
    preparation.add_argument("--output", type=Path, required=True)
    preparation.add_argument("--cpu", type=int, default=3)
    preparation.add_argument("--runtime-path", type=Path, action="append", default=[])
    for action in ("run", "worker"):
        p = sub.add_parser(action)
        p.add_argument("--prepared", type=Path, required=True)
        p.add_argument("--plan-sha256", required=True)
        p.add_argument("--release", type=Path, required=True)
        p.add_argument("--case", choices=CASES, required=True)
        p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
        prepare(args.output, cpu=args.cpu, runtime_paths=args.runtime_path)
        return 0
    if args.command == "worker":
        return worker(args.prepared, args.plan_sha256, args.release, args.case, args.output)
    result = launch(args.prepared, args.plan_sha256, args.release, args.case, args.output)
    return int(result["status"] == "failed")


if __name__ == "__main__":
    raise SystemExit(main())
