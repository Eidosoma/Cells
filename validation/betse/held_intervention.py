"""D079: compile prescribed held inputs and probe controls, never integrate a model."""

import argparse
import ast
import copy
import importlib.abc
import io
import json
import os
import subprocess
import sys
import warnings
from contextlib import redirect_stdout
from pathlib import Path

import contact as c
import intervention_design as law
import trajectory_evidence as trajectory

PLAN = c.HERE / "held_intervention_plan.json"
PRIOR_SHA = "65a7b798bdbf81a1f1b380165154b5803580f119bbfbb29133f1a4003a063558"
CONDITIONS = ("baseline", "zero_amplitude", "static_blocked", "suppression_recovery")
FORBIDDEN = {
    "betse.science.sim",
    "betse.science.simrunner",
    "cells.core.runner",
    "cells.numerics.fixed_step",
}


class IntegrationFence(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in FORBIDDEN:
            raise AssertionError("Control-only probe imported integration entry: " + fullname)


def validate_plan(p):
    base = c.read(law.PLAN)
    law.validate_plan(base)
    expected = {
        "schema": "cells.betse_held_intervention_design@1",
        "status": "control_design_only_not_registered",
        "prior_closeout_sha256": PRIOR_SHA,
        "input_law_source": "validation/betse/intervention_plan.json",
        "duration_s": base["duration_s"],
        "control_probe_steps_s": base["native_steps_s"],
        "cells_subdivisions": [1, 2, 4],
        "conditions": list(CONDITIONS),
        "pilot": {
            "constant_profile": "matched_constants",
            "hold_step_s": base["native_steps_s"][0],
            "native_observer_modes": ["off", "on"],
            "cells_backends": ["jax_eager", "jax_jit"],
            "native_runs": 8,
            "cells_runs": 24,
            "observed_native_steps": 160,
            "profiles_enabled": True,
            "preparation": "fresh_neutral_SIM_no_INIT_restart",
        },
        "hold_policy": "left_sampled_right_continuous",
        "time_generation": "integer_index_times_hold_step",
        "terminal_control": "retain_last_interval_no_new_endpoint_event",
        "control_error_scale": "positive_unsuppressed_baseline_not_residual",
        "control_atol": base["source_control_probe_atol"],
        "criteria_source": base["criteria_source"],
        "probe_worker_timeout_seconds": 20,
        "cpu_affinity": "0-3",
    }
    expected |= dict.fromkeys(
        (
            "trajectory_run",
            "trajectory_qualified",
            "continuous_waveform_qualified",
            "controls_from_native_history",
            "relax_prior_tolerances",
            "biology_validated",
            "gpu_tested",
            "automatic_expansion",
        ),
        False,
    )
    # Serialized equality also rejects bool-for-number substitutions and extra fields.
    c.require(
        json.dumps(p, sort_keys=True, allow_nan=False)
        == json.dumps(expected, sort_keys=True, allow_nan=False),
        "Held-input design differs; version a different experiment explicitly",
    )


def held_schedule(p, condition, h):
    validate_plan(p)
    c.require(condition in CONDITIONS, "Unknown control condition")
    c.require(type(h) is float and h in p["control_probe_steps_s"], "Unregistered hold step")
    base = c.read(law.PLAN)
    count, _, _ = law.clock_parameters(base, h)
    q = base["candidate_pulse"]
    times = [k * h for k in range(count)]
    if condition == "suppression_recovery":
        values = [law.decimal_availability(t, q) for t in times]
    else:
        values = [0.0 if condition == "static_blocked" else 1.0] * count
    return [
        {"time": t, "multipliers": dict.fromkeys(q["species"], u)}
        for t, u in zip(times, values, strict=True)
    ]


def cells_definition(p, condition, h, subdivision, backend):
    schedule = held_schedule(p, condition, h)
    c.require(
        type(subdivision) is int and subdivision in p["cells_subdivisions"],
        "Unregistered Cells subdivision",
    )
    c.require(backend in p["pilot"]["cells_backends"], "Unregistered Cells backend")
    # Reuse only the declared geometry/initial conditions, never native output controls.
    d = copy.deepcopy(
        trajectory.trusted_registration()["cells_definitions"]["passive/jax_eager/0.00010000"]
    )
    for membrane in d["experiment"]["membrane_controls"]:
        membrane["leak"] = copy.deepcopy(schedule)
    count = len(schedule)
    d["execution"] |= {
        "dt": h / subdivision,
        "jit": backend == "jax_jit",
        "max_steps": count * subdivision,
    }
    d["experiment"]["observation_times"] = [r["time"] for r in schedule] + [p["duration_s"]]
    return d


def composition_contract(source):
    merge = law.method(source, "makeAllChanges")
    assignments = {
        ast.unparse(target): ast.unparse(node.value)
        for node in ast.walk(merge)
        if isinstance(node, ast.Assign)
        for target in node.targets
    }
    c.require(assignments.get("sim.Dm_cells") == "sim.Dm_scheduled + sim.Dm_base", "Merge differs")
    fire = law.method(source, "_fire_events_tissue")
    assignments = {
        ast.unparse(target): ast.unparse(node.value)
        for node in ast.walk(fire)
        if isinstance(node, ast.Assign)
        for target in node.targets
    }
    for ion in ("Na", "K", "Cl"):
        c.require(
            assignments.get(f"sim.Dm_scheduled[sim.i{ion}][self.targets_{ion}mem]")
            == f"self.mem_mult_{ion}mem * effector_{ion} * self.tissue_default.Dm_{ion}",
            "Native additive composition differs: " + ion,
        )
    return {"merge": "scheduled_plus_base", "species": ["Na", "K", "Cl"]}


def native_probe(p):
    import numpy as np
    from betse.science.math import toolbox

    registered = trajectory.trusted_registration()
    source = Path(toolbox.__file__).resolve()
    c.require(source.is_relative_to(c.REFERENCE_PYTHON.parent.parent), "Wrong native runtime")
    c.require(
        c.sha(source) == registered["upstream"]["files_sha256"]["betse/science/math/toolbox.py"],
        "Pulse source changed",
    )
    inputs = registered["base_protocol"]
    permeability = np.array(inputs["permeability_m_per_s"])
    baseline_dm = permeability * inputs["thickness_m"]
    base = c.read(law.PLAN)
    rows = []
    with warnings.catch_warnings(), np.errstate(over="raise", invalid="raise", divide="raise"):
        warnings.simplefilter("error")
        for h in p["control_probe_steps_s"]:
            count, scale, mapped = law.clock_parameters(base, h)
            raw = np.linspace(0, count * h, count)
            pulse = toolbox.pulse(raw, *mapped)
            for condition in CONDITIONS:
                expected = np.array(
                    [r["multipliers"]["Na"] for r in held_schedule(p, condition, h)]
                )
                active_dm = baseline_dm * (0 if condition == "static_blocked" else 1)
                multiplier = base["candidate_pulse"]["additive_multiplier"]
                multiplier = multiplier if condition == "suppression_recovery" else 0.0
                # Deliberate source-order arithmetic, not a call to the event handler.
                scheduled = (multiplier * pulse)[:, None] * active_dm[None, :]
                effective = scheduled + active_dm
                cells_effective = (expected[:, None] * permeability) * inputs["thickness_m"]
                errors = np.abs(effective[:, :3] - cells_effective[:, :3]) / baseline_dm[:3]
                error = float(np.max(errors))
                c.require(error <= p["control_atol"], "Additive/multiplicative controls differ")
                c.require(bool(np.all(effective >= 0)), "Negative effective permeability")
                c.require(not np.any(effective[:, 3:]), "Immobile diffusion changed")
                if condition == "static_blocked":
                    c.require(not np.any(effective), "Static blocking is not exact")
                rows.append(
                    {
                        "condition": condition,
                        "h_s": h,
                        "steps": count,
                        "yaml_time_scale": scale,
                        "mapped_yaml_on_off_transition_s": mapped,
                        "maximum_baseline_scaled_error": error,
                        "raw_labels_s": raw.tolist(),
                        "elapsed_before_s": [k * h for k in range(count)],
                        "effective_Dm_m2_per_s": effective.tolist(),
                        "cells_availability": expected.tolist(),
                    }
                )
    return {
        "engine": "pinned_pulse_plus_source_order_arithmetic_not_event_dispatch",
        "rows": rows,
        "pulse_source_sha256": c.sha(source),
        "warnings": [],
        "event_dispatch_calls": 0,
    }


def cells_probe(p):
    import numpy as np

    from cells.core.grid import EventGrid
    from cells.core.schedule import control_values
    from cells.core.specs import parse_spec

    rows = []
    for h in p["control_probe_steps_s"]:
        for condition in CONDITIONS:
            schedule = held_schedule(p, condition, h)
            starts = [s["time"] for s in schedule]
            values = np.array([s["multipliers"]["Na"] for s in schedule])
            for subdivision in p["cells_subdivisions"]:
                d = cells_definition(p, condition, h, subdivision, "jax_eager")
                spec = parse_spec(d)
                grid = list(EventGrid(spec))
                expected_grid = [k * (h / subdivision) for k in range(len(starts) * subdivision)]
                expected_grid.append(p["duration_s"])
                c.require(grid == expected_grid, "Duplicate/sliver/missing integration boundary")
                for k, start in enumerate(starts):
                    c.require(grid[k * subdivision] == start, "Held boundary is off solver grid")
                # Pre-boundary, right-boundary and final-side control checks, not physical rates.
                queries = np.array(
                    starts + [p["duration_s"]] + list(np.nextafter(starts[1:], -np.inf))
                )
                expected = np.concatenate((values, values[-1:], values[:-1]))
                control = control_values(spec, queries)
                c.require(
                    np.array_equal(
                        control.membrane[:, :3, :7],
                        np.broadcast_to(expected[:, None, None], (len(queries), 3, 7)),
                    ),
                    "Wrong control side or endpoint",
                )
                held = control_values(spec, grid[:-1]).membrane[:, :3, :7]
                c.require(
                    np.array_equal(
                        held,
                        np.broadcast_to(np.repeat(values, subdivision)[:, None, None], held.shape),
                    ),
                    "Solver refinement changes the held input",
                )
                c.require(
                    not np.any(control.membrane[:, 3:, :])
                    and not np.any(control.membrane[:, :, 7:])
                    and not np.any(control.channel)
                    and not np.any(control.junction),
                    "Disabled or padded controls changed",
                )
                rows.append(
                    {
                        "condition": condition,
                        "h_s": h,
                        "subdivision": subdivision,
                        "integration_intervals": len(grid) - 1,
                        "boundary_queries": len(queries),
                        "grid_s": grid,
                        "final_held_availability": float(values[-1]),
                        "extra_sliver_intervals": 0,
                    }
                )
    return {"engine": "unchanged_cells_parser_schedule_event_grid_only", "rows": rows}


def probe(kind):
    sys.meta_path.insert(0, IntegrationFence())
    p = c.read(PLAN)
    validate_plan(p)
    diagnostics = io.StringIO()
    with redirect_stdout(diagnostics):
        result = native_probe(p) if kind == "native" else cells_probe(p)
    c.require(not FORBIDDEN.intersection(sys.modules), "Integration entry was imported")
    result |= {
        "plan_sha256": c.sha(PLAN),
        "stdout_log": diagnostics.getvalue(),
        "integration_calls": 0,
        "trajectory_qualified": False,
    }
    print(json.dumps(result, allow_nan=False))


def run_probe(kind):
    c.require(kind in ("native", "cells"), "Unknown control probe")
    python = c.REFERENCE_PYTHON if kind == "native" else c.CELLS_PYTHON
    result = subprocess.run(
        ["taskset", "-c", "0-3", str(python), "-B", str(Path(__file__).resolve()), kind],
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("native", "cells"))
    probe(parser.parse_args().kind)
