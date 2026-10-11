"""D101 numeric input design; no native dispatch, simulation or reference solve."""

import ast
import copy
import importlib
import json
import math
import sys
from bisect import bisect_right
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "channel_history_audit"))
audit = importlib.import_module("history_audit_context")
audit_job = importlib.import_module("history_audit_job")
c, io, ROOT = audit.c, audit.io, audit.ROOT
PLAN = HERE / "plan.json"
PRIOR = ROOT / "runs/ref-004c-paired-history-audit-2026-09-15/audit-01"
PRIOR_SHA = "e152d806f72f2571b150eb6751c59e1a3fc34ac8accf4bfeaaf4502d30348135"
CONDITIONS = ("baseline", "no_op", "static_blocked", "suppression_release")


def validate_plan(plan):
    c.require(
        json.dumps(plan, sort_keys=True, allow_nan=False)
        == json.dumps(c.read(PLAN), sort_keys=True, allow_nan=False),
        "Unregistered release design",
    )
    c.require(
        plan["schema"] == "cells.betse_channel_release_design@1"
        and plan["decision"] == "D101"
        and plan["prerequisite_completion_sha256"] == PRIOR_SHA
        and plan["conditions"] == list(CONDITIONS),
        "Wrong release design prerequisite or scope",
    )
    c.require(
        0 < plan["block_time_s"] < plan["release_time_s"] < plan["duration_s"],
        "Unordered release design times",
    )
    for key in (
        "production_changed",
        "native_dispatch_executed",
        "new_trajectory_executed",
        "reference_integration_executed",
        "release_response_qualified",
        "biology_validated",
        "gpu_tested",
        "automatic_followup",
    ):
        c.require(plan[key] is False, "Design does not authorize execution: " + key)


def prerequisite():
    """Read-only authentication in a model-free process, not another numerical audit."""
    c.require(c.sha(PRIOR / "completion.json") == PRIOR_SHA, "Paired closeout changed")
    with audit.model_fence():
        registration = audit_job.authenticate(PRIOR)
        capture = audit.load_capture()
    done, hashes = c.read(PRIOR / "completion.json"), audit.packet_hashes(PRIOR)
    c.require(
        done["status"] == "paired_history_pilot_audit_closed"
        and done["coupled_history_qualified"] is True
        and done["independent_column_mismatches"] == 0
        and done["independent_identities"] == 8036300
        and done["preserved_coarse_diagnostic_failures"] == 21,
        "Paired numerical prerequisite is not closed",
    )
    c.require(
        set(hashes) == set(done["files_sha256"]) | audit.OPERATIONAL | {"completion.json"}
        and all(hashes[n] == h for n, h in done["files_sha256"].items())
        and done["registration_sha256"] == c.sha(PRIOR / "registration.json")
        and done["tests"] == registration["tests"],
        "Paired closeout packet changed",
    )
    return {
        "audit_files_sha256": hashes,
        "capture_files_sha256": capture["hashes"],
        "completion_sha256": PRIOR_SHA,
        "audit_tests": done["tests"],
    }


def schedule(plan, condition):
    validate_plan(plan)
    c.require(condition in CONDITIONS, "Unknown release condition")
    if condition in ("baseline", "static_blocked"):
        return [{"time": 0.0, "availability": 0.0 if condition == "static_blocked" else 1.0}]
    return [
        {"time": 0.0, "availability": 1.0},
        {
            "time": plan["block_time_s"],
            "availability": 0.0 if condition == "suppression_release" else 1.0,
        },
        {"time": plan["release_time_s"], "availability": 1.0},
    ]


def availability(plan, condition, time):
    c.require(
        type(time) in (int, float) and math.isfinite(time) and 0 <= time <= plan["duration_s"],
        "Control time outside declared elapsed domain",
    )
    rows = schedule(plan, condition)
    return rows[bisect_right([r["time"] for r in rows], time) - 1]["availability"]


def native_intervals(plan, condition, step):
    """Elapsed boundary input, deliberately not BETSE's endpoint-labelled time array."""
    validate_plan(plan)
    c.require(type(step) is float and step in plan["native_steps_s"], "Unregistered native grid")
    h = Decimal(str(step))
    count = Decimal(str(plan["duration_s"])) / h
    c.require(count == int(count), "Native duration is not a complete step")
    for row in schedule(plan, condition):
        index = Decimal(str(row["time"])) / h
        c.require(index == int(index), "Native switch does not align with its grid")
    return [
        {
            "step_index": k,
            "start_s": float(k * h),
            "end_s": float((k + 1) * h),
            "availability": availability(plan, condition, float(k * h)),
        }
        for k in range(int(count))
    ]


def native_diffusivity(baseline, value):
    """Fresh absolute input; never multiply the already suppressed native parameter."""
    c.require(
        type(baseline) in (int, float) and math.isfinite(baseline) and baseline >= 0,
        "Invalid baseline native diffusivity",
    )
    c.require(
        type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1,
        "Invalid channel availability",
    )
    result = baseline * value
    c.require(math.isfinite(result), "Invalid effective native diffusivity")
    return result


def view(history):
    c.require(history in ("a", "b"), "Unknown saved history")
    return c.read(audit.CAPTURE / "registration.json")["views"][history]


def definition(plan, history, condition, step, backend="jax_jit"):
    validate_plan(plan)
    c.require(history in plan["histories"], "Unknown release history")
    c.require(type(step) is float and step in plan["cells_steps_s"], "Unregistered Cells grid")
    c.require(backend in ("jax_eager", "jax_jit"), "Unknown execution backend")
    result = copy.deepcopy(view(history)["cells_definitions"]["active_channel/jax_jit/dt_5e-05"])
    for control in result["experiment"]["channel_controls"]:
        control["schedule"] = schedule(plan, condition)
    result["execution"].update(dt=step, jit=backend == "jax_jit")
    # Intrinsic parameters, m/h, anchors, geometry and other controls remain identical.
    return result


def method(source, cls, name):
    tree = ast.parse(source)
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    return next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == name)


def source_contract(networks, gates):
    """Fail-closed structural checks complement the fully pinned source hashes."""
    loop = method(networks, "MasterOfNetworks", "run_loop_channels")
    assignments = {
        ast.unparse(target): (ast.unparse(node.value), node.lineno)
        for node in ast.walk(loop)
        if isinstance(node, ast.Assign)
        for target in node.targets
    }
    c.require(
        assignments["DChan"][0] == "chan.channel_core.P * rel_perm * chan.maxDm * moddy",
        "Native channel transport factorization changed",
    )
    calls = {
        ast.unparse(node.func): node.lineno for node in ast.walk(loop) if isinstance(node, ast.Call)
    }
    c.require(
        calls["chan.channel_core.run"] < assignments["DChan"][1] < calls["stb.update_Co"],
        "Native gates/transport order changed",
    )
    c.require(
        assignments["moddy"][0] == "eval(chan.alpha_eval_string, globalo, localo)",
        "Native modulation provider changed",
    )
    for cls, name in (
        ("VgKABC", "run"),
        ("VgKABC", "_implement_state"),
        ("Kv1p5", "_calculate_state"),
    ):
        names = {n.attr for n in ast.walk(method(gates, cls, name)) if isinstance(n, ast.Attribute)}
        c.require(not names & {"maxDm", "modulator"}, "Kv1p5 kinetics now depend on availability")
    return {
        "native_source_boundary": "FULL network channel path; not FAST or tissue events",
        "order": ["gate_update", "effective_diffusivity", "concentration_update"],
        "input": "maxDm = immutable_baseline_maxDm * availability",
        "alpha_expression_changed": False,
        "native_dispatch_executed": False,
    }


def pinned_source_contract():
    native = c.SOURCE / "betse/science"
    return source_contract(
        (native / "chemistry/networks.py").read_text(),
        (native / "channels/vg_k.py").read_text(),
    )
