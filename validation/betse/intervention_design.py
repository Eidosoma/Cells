"""Source-bound intervention design and control-only probes; never integrate a model."""

import argparse
import ast
import copy
import io
import json
import math
import os
import subprocess
import sys
import warnings
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from pathlib import Path

import cluster_closeout as files
import contact as c
import trajectory_evidence as trajectory
import trajectory_failure as prior

PLAN = c.HERE / "intervention_plan.json"
PREVIOUS = c.ROOT / "reports/ref-003d-closeout.json"
PREVIOUS_SHA = "4caaa0485d971821ebccc7fa255323bb3e38708531503c4cb8838ef97bd197b9"
PRESERVATION = c.ROOT / "reports/ref-003e-design-preservation.json"
RECEIPT = c.ROOT / "reports/ref-003e-design-review.json"
TESTS = c.ROOT / "reports/ref-003e-design-checks-02.xml"
NEW_FILES = {
    "validation/betse/" + name
    for name in ("intervention_design.py", "intervention_plan.json", "test_intervention_design.py")
}
NATIVE_FILES = (
    "betse/science/sim.py",
    "betse/science/simrunner.py",
    "betse/science/parameters.py",
    "betse/science/phase/phasecls.py",
    "betse/science/tissue/tishandler.py",
    "betse/science/math/toolbox.py",
)
CELLS_FILES = (
    "src/cells/core/schedule.py",
    "src/cells/core/grid.py",
    "src/cells/core/runner.py",
    "src/cells/models/finite_extracellular.py",
    "src/cells/numerics/fixed_step.py",
)


def validate_plan(p):
    c.require(
        p["schema"] == "cells.betse_intervention_design@1"
        and p["status"] == "design_only_not_registered"
        and p["prior_closeout_sha256"] == PREVIOUS_SHA,
        "Design identity differs",
    )
    c.require(
        all(
            p[k] is False
            for k in (
                "trajectory_run",
                "trajectory_qualified",
                "biology_validated",
                "gpu_tested",
                "relax_prior_tolerances",
            )
        ),
        "Design overclaims execution/qualification",
    )
    c.require(
        p["criteria_source"] == "validation/betse/trajectory_refinement_protocol.json"
        and p["source_control_probe_atol"] == 2e-14
        and p["probe_worker_timeout_seconds"] == 20
        and p["cpu_affinity"] == "0-3",
        "Design criteria/resource contract differs",
    )
    base = c.read(c.ROOT / p["criteria_source"])
    c.require(
        p["duration_s"] == base["duration_s"] == 0.001
        and p["native_steps_s"] == base["native_steps_s"],
        "Candidate horizon/ladder differs",
    )
    q = p["candidate_pulse"]
    c.require(
        all(
            type(q[k]) in (int, float) and math.isfinite(q[k])
            for k in ("on_s", "off_s", "transition_s", "additive_multiplier")
        ),
        "Nonfinite pulse parameter",
    )
    c.require(
        0 < q["on_s"] < q["off_s"] < p["duration_s"]
        and q["transition_s"] > 0
        and -1 <= q["additive_multiplier"] <= 0,
        "Invalid suppression pulse",
    )
    c.require(
        q["species"] == ["Na", "K", "Cl"]
        and q["modulator"] == "None"
        and q["exact_zero_interval"] is False,
        "Pulse is not an exact square block",
    )
    c.require(
        p["clock"]["primary"] == "elapsed_update_time"
        and p["clock"]["scale_fields"] == ["change start", "change finish", "change rate"]
        and p["clock"]["rewrite_native_clock"] is False,
        "Incomplete explicit clock mapping",
    )
    d = p["drive_comparison"]
    c.require(
        d["cells_step_subdivisions_per_native_interval"] == [1, 2, 4]
        and d["separate_forcing_and_solver_refinement"] is True
        and d["continuous_waveform_qualified"] is False
        and d["controls_derived_from_native_trajectory_output"] is False,
        "Forcing and solver refinement must remain independent",
    )


def authenticate():
    c.require(c.sha(PREVIOUS) == PREVIOUS_SHA, "Prior trajectory closeout changed")
    closed = c.read(PREVIOUS)
    c.require(
        closed["status"] == "pass" and closed["trajectory_qualified"] is True,
        "Missing qualified predecessor",
    )
    for name, digest in closed["new_files_sha256_before_closeout"].items():
        c.require(c.sha(c.ROOT / name) == digest, "Prior audit tooling/evidence changed")
    registered = trajectory.trusted_registration()
    for name, digest in registered["sources"].items():
        c.require(c.sha(c.HERE / name) == digest, "Captured adapter source changed")
    for name, digest in trajectory.ANCHORS.items():
        c.require(c.sha(trajectory.SESSION / name) == digest, "Trajectory anchor changed")
    original = c.read(c.ROOT / "reports/ref-003d-closeout-preservation.json")
    for key, path in (("v1", prior.SESSION), ("v2", trajectory.SESSION)):
        c.require(
            prior.files(path) == original[key + "_files_sha256"], "Old trajectory packet changed"
        )
    accepted = c.authenticate_cells()
    installed = c.REFERENCE_PYTHON.parent.parent / "lib/python3.13/site-packages"
    for name in NATIVE_FILES:
        digest = registered["upstream"]["files_sha256"][name]
        c.require(
            c.sha(c.SOURCE / name) == c.sha(installed / name) == digest,
            "Reviewed native source differs from captured upstream",
        )
    return accepted


def preserve():
    accepted = authenticate()
    baseline = {n: h for n, h in files.worktree().items() if n not in NEW_FILES}
    c.write(
        PRESERVATION,
        {
            "schema": "cells.betse_intervention_design_preservation@1",
            "status": "pass",
            "created_utc": datetime.now(UTC).isoformat(),
            "prior_closeout_sha256": PREVIOUS_SHA,
            "baseline_sha256": baseline,
            "accepted_sources": accepted["implementation_files_sha256"],
        },
    )
    print(json.dumps({"status": "preserved", "baseline_files": len(baseline)}))


def method(source, name):
    matches = [
        n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == name
    ]
    c.require(len(matches) == 1, "Missing or ambiguous source method")
    return matches[0]


def native_phase_contract(source):
    loop = method(source, "_run_sim_core_loop")
    guards = [
        n
        for n in ast.walk(loop)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "phase.kind is SimPhaseKind.SIM"
    ]
    c.require(len(guards) == 1, "Native event phase guard differs")
    calls = [n for n in ast.walk(loop) if isinstance(n, ast.Call)]
    events = [n for n in calls if ast.unparse(n.func) == "phase.dyna.fire_events"]
    c.require(
        len(events) == 1
        and events[0] in list(ast.walk(guards[0]))
        and {k.arg: ast.unparse(k.value) for k in events[0].keywords}
        == {"phase": "phase", "t": "t"},
        "Native event dispatch/timing differs",
    )
    fluxes = [n.lineno for n in calls if ast.unparse(n.func) == "stb.electroflux"]
    updates = [n.lineno for n in calls if ast.unparse(n.func) == "self.update_all_concs"]
    c.require(
        fluxes and updates and events[0].lineno < min(fluxes) < min(updates),
        "Native event/flux/update order differs",
    )
    clock = method(source, "_plot_loop")
    c.require(
        any(
            isinstance(n, ast.Call)
            and ast.unparse(n) == "np.linspace(0, phase_time_len, phase_time_step_count)"
            for n in ast.walk(clock)
        ),
        "Native raw clock construction differs",
    )
    return {
        "event_line": events[0].lineno,
        "first_flux_line": min(fluxes),
        "update_line": min(updates),
        "events_in_init": False,
        "events_in_sim": True,
    }


def clock_parameters(p, dt):
    c.require(type(dt) in (int, float) and math.isfinite(dt) and dt > 0, "Invalid native step")
    count = int(p["duration_s"] / dt)
    c.require(
        count > 1 and math.isclose(count * dt, p["duration_s"], rel_tol=0, abs_tol=1e-18),
        "Invalid native step count",
    )
    scale = count / (count - 1)
    q = p["candidate_pulse"]
    return count, scale, [scale * q[k] for k in ("on_s", "off_s", "transition_s")]


def decimal_availability(t, q):
    with localcontext() as context:
        context.prec = 70
        value = Decimal(str(t))
        gain = Decimal(10) / Decimal(str(q["transition_s"]))
        on, off = (Decimal(str(q[k])) for k in ("on_s", "off_s"))
        a = 1 / (1 + (-gain * (value - on)).exp())
        b = 1 / (1 + (-gain * (value - off)).exp())
        return float(1 + Decimal(str(q["additive_multiplier"])) * (a - b))


def native_probe(p):
    import betse
    import numpy as np
    from betse.science.math import toolbox

    c.require(
        Path(betse.__file__).resolve().parent.is_relative_to(c.REFERENCE_PYTHON.parent.parent),
        "Wrong native control runtime",
    )
    registered = trajectory.trusted_registration()
    native_file = "betse/science/math/toolbox.py"
    c.require(
        c.sha(toolbox.__file__) == registered["upstream"]["files_sha256"][native_file],
        "Not the pinned control function",
    )
    rows = []
    q = p["candidate_pulse"]
    with warnings.catch_warnings(), np.errstate(over="raise", invalid="raise", divide="raise"):
        warnings.simplefilter("error")
        for dt in p["native_steps_s"]:
            count, scale, mapped = clock_parameters(p, dt)
            raw = np.linspace(0, count * dt, count)
            elapsed = np.arange(count) * dt
            controls = 1 + q["additive_multiplier"] * toolbox.pulse(raw, *mapped)
            unscaled = 1 + q["additive_multiplier"] * toolbox.pulse(
                raw, q["on_s"], q["off_s"], q["transition_s"]
            )
            expected = [decimal_availability(float(t), q) for t in elapsed]
            error = float(np.max(np.abs(controls - expected)))
            c.require(error <= p["source_control_probe_atol"], "Mapped native control differs")
            c.require(bool(np.all((controls >= 0) & (controls <= 1))), "Control leaves domain")
            rows.append(
                {
                    "dt_s": dt,
                    "steps": count,
                    "yaml_time_scale": scale,
                    "mapped_yaml_on_off_transition_s": mapped,
                    "maximum_control_error": error,
                    "unscaled_maximum_control_difference": float(
                        np.max(np.abs(unscaled - expected))
                    ),
                    "raw_labels_s": raw.tolist(),
                    "before_elapsed_s": elapsed.tolist(),
                    "applied_availability": controls.tolist(),
                }
            )
    midpoint = (q["on_s"] + q["off_s"]) / 2
    return {
        "engine": "pinned_betse_toolbox_pulse_only",
        "rows": rows,
        "midpoint_availability_decimal": decimal_availability(midpoint, q),
        "source_sha256": c.sha(toolbox.__file__),
        "warnings": [],
        "integration_calls": 0,
    }


def cells_probe():
    import numpy as np

    from cells.core.grid import EventGrid
    from cells.core.schedule import control_values
    from cells.core.specs import parse_spec

    definition = copy.deepcopy(
        trajectory.trusted_registration()["cells_definitions"]["passive/jax_eager/0.00010000"]
    )
    # A control-contract unit probe, not the proposed smooth native pulse.
    on, off = 0.00035, 0.00075
    for membrane in definition["experiment"]["membrane_controls"]:
        membrane["leak"] = [
            {"time": t, "multipliers": dict.fromkeys(("Na", "K", "Cl"), u)}
            for t, u in ((0.0, 1.0), (on, 0.0), (off, 1.0))
        ]
    spec = parse_spec(definition)
    times = [0.0, np.nextafter(on, -np.inf), on, 0.0005, np.nextafter(off, -np.inf), off, 0.001]
    expected = [1, 1, 0, 0, 0, 1, 1]
    control = control_values(spec, times)
    c.require(
        np.array_equal(
            control.membrane[:, :3, :7],
            np.broadcast_to(np.array(expected)[:, None, None], (7, 3, 7)),
        ),
        "Cells right-continuous control differs",
    )
    c.require(
        not np.any(control.membrane[:, 3:, :])
        and not np.any(control.membrane[:, :, 7:])
        and not np.any(control.channel)
        and not np.any(control.junction),
        "Inactive or disabled controls changed",
    )
    grid = list(EventGrid(spec))
    c.require(
        on in grid and off in grid and len(grid) - 1 == 12,
        "Cells grid does not split at off-grid controls",
    )
    return {
        "engine": "unchanged_cells_schedule_and_event_grid_only",
        "times_s": [float(t) for t in times],
        "availability": expected,
        "event_split_grid_s": grid,
        "integration_calls": 0,
    }


def probe(kind):
    # Fence actual stepping entry modules before importing either control implementation.
    import importlib.abc

    class Fence(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname in {"betse.science.sim", "betse.science.simrunner", "cells.core.runner"}:
                raise AssertionError("Control probe imported integration entry: " + fullname)

    sys.meta_path.insert(0, Fence())
    p = c.read(PLAN)
    validate_plan(p)
    diagnostics = io.StringIO()
    with redirect_stdout(diagnostics):
        result = native_probe(p) if kind == "native" else cells_probe()
    result["stdout_log"] = diagnostics.getvalue()
    result["plan_sha256"] = c.sha(PLAN)
    print(json.dumps(result, allow_nan=False))


def run_probe(kind):
    python = c.REFERENCE_PYTHON if kind == "native" else c.CELLS_PYTHON
    result = subprocess.run(
        ["taskset", "-c", "0-3", str(python), "-B", str(Path(__file__).resolve()), "probe", kind],
        cwd=c.ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
        env=os.environ
        | {
            "PYTHONDONTWRITEBYTECODE": "1",
            "JAX_PLATFORMS": "cpu",
            "JAX_ENABLE_X64": "true",
            "OPENBLAS_NUM_THREADS": "1",
        },
    )
    c.require(not result.stderr.strip(), "Control probe emitted stderr")
    return json.loads(result.stdout)


def review():
    c.require(not RECEIPT.exists(), "Design review exists; do not overwrite")
    p = c.read(PLAN)
    validate_plan(p)
    accepted = authenticate()
    preserved = c.read(PRESERVATION)
    c.require(
        preserved["accepted_sources"] == accepted["implementation_files_sha256"]
        and preserved["prior_closeout_sha256"] == PREVIOUS_SHA,
        "Preserved predecessor differs",
    )
    changes = {
        n: {"before": h, "after": c.sha(c.ROOT / n)}
        for n, h in preserved["baseline_sha256"].items()
        if c.sha(c.ROOT / n) != h
    }
    c.require(set(changes) <= prior.ALLOWED_DOCUMENT_EDITS, "Unexpected pre-existing edit")
    sources = {name: c.sha(c.SOURCE / name) for name in NATIVE_FILES}
    sources |= {name: c.sha(c.ROOT / name) for name in CELLS_FILES}
    contract = native_phase_contract((c.SOURCE / "betse/science/sim.py").read_text())
    native, local = run_probe("native"), run_probe("cells")
    c.require(
        all(
            record["integration_calls"] == 0 and record["plan_sha256"] == c.sha(PLAN)
            for record in (native, local)
        ),
        "Control probe provenance differs",
    )
    suites = list(ET.parse(TESTS).getroot().iter("testsuite"))
    counts = {
        k: sum(int(s.get(k, 0)) for s in suites) for k in ("tests", "failures", "errors", "skipped")
    }
    c.require(
        counts == {"tests": 38, "failures": 0, "errors": 0, "skipped": 0}
        and sum(len(s.findall("testcase")) for s in suites) == 38
        and {case.get("classname") for s in suites for case in s.findall("testcase")}
        == {"validation.betse.test_intervention_design"},
        "Incomplete design checks",
    )
    quality = {}
    for name, arguments in (("lint", ["check"]), ("format", ["format", "--check"])):
        quality[name] = subprocess.check_output(
            [str(c.ROOT / ".venv/bin/ruff"), *arguments, "src", "tests", "scripts", "validation"],
            cwd=c.ROOT,
            text=True,
            timeout=20,
        ).strip()
    current = files.worktree()
    result = {
        "schema": "cells.betse_intervention_design_review@1",
        "status": "design_checks_pass",
        "finished_utc": datetime.now(UTC).isoformat(),
        "prior_closeout_sha256": PREVIOUS_SHA,
        "plan_sha256": c.sha(PLAN),
        "reviewed_sources_sha256": sources,
        "native_phase_contract": contract,
        "native_control_probe": native,
        "cells_control_probe": local,
        "tests": counts | {"junit_sha256": c.sha(TESTS)},
        "preservation_sha256": c.sha(PRESERVATION),
        "baseline_files": len(preserved["baseline_sha256"]),
        "unchanged_baseline_files": len(preserved["baseline_sha256"]) - len(changes),
        "changed_documents": changes,
        "new_files_sha256_before_review": {
            n: h for n, h in current.items() if n not in preserved["baseline_sha256"]
        },
        "quality": quality,
        "accepted_implementation_files_unchanged": len(accepted["implementation_files_sha256"]),
        "production_modules_unchanged": 51,
        "v1_and_v2_packet_files_unchanged": 238,
        "captured_v2_adapter_sources_unchanged": 35,
        "new_tools_sha256": {n: c.sha(c.ROOT / n) for n in NEW_FILES},
        "simulation_launched": False,
        "integration_calls": 0,
        "trajectory_qualified": False,
        "biology_validated": False,
        "gpu_tested": False,
        "prior_adapter_tests": 325,
        "prior_production_matrix_tests": 4190,
        "prior_suites_rerun": False,
        "next_step": "Implement and preflight the separately registered REF-003e0 SIM phase bridge",
    }
    c.write(RECEIPT, result)
    print(
        json.dumps({"status": result["status"], "tests": counts["tests"], "integration_calls": 0})
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preserve", "probe", "review"))
    parser.add_argument("kind", nargs="?", choices=("native", "cells"))
    args = parser.parse_args()
    if args.action == "preserve":
        preserve()
    elif args.action == "probe":
        c.require(args.kind is not None, "Choose a probe engine")
        probe(args.kind)
    else:
        review()
