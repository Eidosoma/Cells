"""Held pregeometry cost attribution; never parameter/phase or science authority.

Reuse the existing authority observer unchanged. Its journal is opened before
validation, so periodic samples need no filesystem opens during read-only p
checks. Root must supply the genuine in-process inputs and coordinate execution.
"""

import ast
import dis
import hashlib
import importlib
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from types import FunctionType, ModuleType, SimpleNamespace

RELEASE = "CELLS_PREGEOMETRY_COST_DIAGNOSTIC_RELEASED"
TIMING_MODULE = "validation.betse.native_multi_cell_environment_qualification"
TIMING_FILE = "validation/betse/native_multi_cell_environment_qualification.py"
TIMING_SHA256 = "b54b9b59af0c8891008f2df3f9bc6ad12ea06c0fa65b6db039e8b8a96d3bb013"
SITES = (
    (
        "validation.betse.native_seed_world_geometry_qualification",
        ("evaluate_live", "_execute_chain"),
    ),
    (
        "cells.processes.betse_native_phase_callbacks",
        ("_validate", "_check", "_acquire", "_runtime", "_source_function", "_graph"),
    ),
    ("cells.processes.betse_native_simulator_construction", ("_validate", "_check")),
    (
        "cells.processes.betse_native_tissue_configuration",
        ("_validate", "_check", "_native_bindings", "_namespace_bindings"),
    ),
    (
        "cells.processes.betse_native_single_cell_grid_alias",
        ("_check_modules", "_module_records", "_module_bindings", "_atoms"),
    ),
    (
        "cells.processes.betse_native_parameter_load_remainder",
        ("_validate", "validate_completed_history", "_history", "_capture", "_native"),
    ),
    (
        "cells.processes.betse_native_parameter_initializer_constants",
        ("validate_remainder_history", "_remainder_history", "source_plan"),
    ),
    ("ast", ("parse",)),
    ("dis", ("get_instructions",)),
)


class PrephaseBoundaryReached(RuntimeError):
    """An expected failed diagnostic prefix, never successful model execution."""


def source_plan():
    return dict(
        kind="cells.pregeometry_validation_cost@1",
        timing_source=TIMING_SHA256,
        actual_entry="observe(directory,*,enabled=False)",
        selected_sites=SITES,
        stop_before="geometry._execute_chain CALL, before phase request/allocation",
        suggested_guard=dict(
            cpu=6, threads=1, bytes=2**30, wall_seconds=120, reserve_bytes=8 * 2**30
        ),
        inputs="actual current same-process WorldReady+callback via existing evaluate_live",
        no_owner_hydration_or_authority=True,
        native_or_scientific_admission=False,
    )


def _timing():
    root = Path(__file__).resolve().parents[2]
    path = root / TIMING_FILE
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != TIMING_SHA256:
        raise ValueError("Exact existing authority observer producer required")
    module = importlib.import_module(TIMING_MODULE)
    if Path(module.__file__).resolve() != path:
        raise ValueError("Authority observer must belong to the same frozen source")
    return module


def _sites():
    result = []
    for module_name, names in SITES:
        module = sys.modules.get(module_name)
        if type(module) is not ModuleType:
            raise ValueError("Pregeometry dependency must already be loaded: " + module_name)
        namespace = vars(module)
        for name in names:
            if type(namespace.get(name)) is not FunctionType:
                raise ValueError(
                    "Exact Python diagnostic site required: " + module_name + "." + name
                )
            result.append((module_name + "." + name, namespace, name))
    return tuple(result)


def _observer(output, work, targets):
    timing = _timing()

    class JournalTimings(timing.AuthorityTimings):
        # A fresh explicit subclass, not a patch to the shared timing writer,
        # observer, native namespaces or issued owners.
        def _snapshot_record(self, reason, now):
            if self.sequence >= self.policy["max_snapshots"]:
                raise ValueError("Bounded timing snapshots exhausted")
            self._verify()
            wall, cpu = self._clock() if now is None else now
            active = [
                dict(
                    target=self.rows[index]["target"],
                    event=event,
                    elapsed_wall_ns=wall - start[0],
                    elapsed_process_cpu_ns=cpu - start[1],
                )
                for _frame, index, event, start in self.stack
            ]
            record = dict(
                kind="cells.pregeometry_cost_journal@1",
                sequence=self.sequence,
                reason=reason,
                monotonic_ns=wall,
                process_cpu_ns=cpu,
                targets=self.rows,
                active_frames=active,
                observed_profile_events=self.events,
                observation_failed=self.failure is not None,
                return_event_is_success=False,
                inclusive_times_are_additive=False,
                includes_observer_and_guard_cost=True,
                prephase_hook_recovery=getattr(self, "prephase_hook_recovery", None),
                independent_case_credit=0,
            )
            raw = (json.dumps(record, allow_nan=False, separators=(",", ":")) + "\n").encode()
            if len(raw) > self.policy["max_snapshot_bytes"]:
                raise ValueError("Timing journal record exceeds original byte allowance")
            cursor = 0
            while cursor < len(raw):
                written = os.write(self.journal_fd, raw[cursor:])
                if written <= 0:
                    raise OSError("Incomplete timing journal write")
                cursor += written
            os.fsync(self.journal_fd)
            self.sequence += 1
            self.last_checkpoint = wall

    observer = JournalTimings(output, work, targets)
    observer.journal_path = observer.folder / "events.jsonl"
    observer.journal_fd = os.open(
        observer.journal_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
    )
    return observer


def _stop_site(evaluate, chain):
    # Identify the actual CALL source position, not the called function's
    # current __code__: a late retarget must still stop before its body.
    path = Path(evaluate.__code__.co_filename)
    tree = ast.parse(path.read_bytes())
    nodes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_execute_chain"
    ]
    if len(nodes) != 1 or evaluate.__globals__.get("_execute_chain") is not chain:
        raise ValueError("One exact original prephase dispatch required")
    node = nodes[0]
    offsets = set()
    instructions = tuple(dis.get_instructions(evaluate))
    for index, item in enumerate(instructions):
        if (
            item.opname.startswith("CALL")
            and item.positions.lineno == node.lineno
            and item.positions.col_offset == node.col_offset
        ):
            end = (
                instructions[index + 1].offset
                if index + 1 < len(instructions)
                else len(evaluate.__code__.co_code)
            )
            offsets.update(range(item.offset, end))
    if not offsets:
        raise ValueError("Original prephase CALL instruction unavailable")
    return frozenset(offsets)


@contextmanager
def observe(directory, *, enabled=False):
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise ValueError("Pregeometry cost execution remains held")
    directory = Path(directory)
    if (
        not directory.is_absolute()
        or directory.exists()
        or not directory.is_relative_to("/mnt/workspaces/Cells")
        or any(p.is_symlink() for p in (directory, *directory.parents))
    ):
        raise ValueError("Fresh unlinked diagnostic output required")
    targets = _sites()
    geometry = sys.modules[SITES[0][0]]
    evaluate, chain = geometry.evaluate_live, geometry._execute_chain
    code, offsets = evaluate.__code__, _stop_site(evaluate, chain)
    directory.mkdir(parents=True)
    work = SimpleNamespace(phase="pregeometry-validation", failure=None, count=0)
    observer = _observer(directory, work, targets)
    prior, trace = sys.getprofile(), sys.gettrace()
    get_profile, get_trace = sys.getprofile, sys.gettrace
    set_profile, set_trace = sys.setprofile, sys.settrace
    stop = PrephaseBoundaryReached("Measured prefix stopped before phase construction")
    interrupted = [None]
    observer.prephase_hook_recovery = dict(attempted=False, complete=False)
    manager = generator = None
    primary = None

    def stopping(frame, event, arg):
        try:
            if prior is not None:
                prior(frame, event, arg)
            caller = frame.f_back
            if (
                event == "call"
                and caller is not None
                and caller.f_code is code
                and caller.f_lasti in offsets
            ):
                observer._snapshot("prephase-stop")
                raise stop
        except BaseException as error:
            interrupted[0] = error
            raise

    def recovery_trace(frame, event, arg):
        local = None if trace is None else trace(frame, event, arg)
        if (
            event != "call"
            or frame.f_code is not code
            or frame.f_globals is not evaluate.__globals__
        ):
            return local

        def in_evaluate(current, kind, value):
            nonlocal local
            recovered = kind == "exception" and value[1] is interrupted[0]
            if recovered:
                # CPython cleared the profile that raised. Its exception trace
                # event precedes evaluate_live's catch/finally and all final
                # evidence. Restore the actual inherited hooks here, not only
                # after the entire evaluator has already unwound.
                observer.prephase_hook_recovery["attempted"] = True
                set_profile(prior)
                set_trace(trace)
                current.f_trace = local
                observer.prephase_hook_recovery["complete"] = (
                    get_profile() is prior and get_trace() is trace
                )
            if local is not None:
                replacement = local(current, kind, value)
                # CPython retains a local tracer when it returns None.
                if replacement is not None:
                    local = replacement
            if recovered:
                current.f_trace = local
                return local
            return in_evaluate

        return in_evaluate

    try:
        set_trace(recovery_trace)
        sys.setprofile(stopping)
        manager = observer.active()
        generator = manager.gen
        with manager:
            yield observer
    except BaseException as error:
        primary = error
        raise
    finally:
        # Also protected against rejected contextlib exit admission.
        if generator is not None and generator.gi_frame is not None:
            try:
                generator.close()
            except BaseException as error:
                observer.pending_cleanup_errors.append(("outer_generator_close", error))
        for setter, getter, expected in (
            (sys.settrace, sys.gettrace, trace),
            (sys.setprofile, sys.getprofile, prior),
        ):
            for _ in range(3):
                try:
                    setter(expected)
                    if getter() is expected:
                        break
                except BaseException as error:
                    observer.pending_cleanup_errors.append(("outer_hook_recovery", error))
        try:
            os.close(observer.journal_fd)
        except BaseException as error:
            observer.pending_cleanup_errors.append(("outer_journal_close", error))
        try:
            if sys.getprofile() is not prior or sys.gettrace() is not trace:
                raise RuntimeError("Diagnostic hooks not restored")
        except BaseException as error:
            observer.pending_cleanup_errors.append(("outer_final_hooks", error))
        if primary is None and observer.pending_cleanup_errors:
            raise RuntimeError("Diagnostic cleanup failed; raw errors retained") from (
                observer.pending_cleanup_errors[0][1]
            )
