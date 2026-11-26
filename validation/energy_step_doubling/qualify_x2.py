"""FR-18's X2 in the engine (execution.energy_check, D224): the qualification run on the boundary
worlds, once, against the registered harness's saved verdicts. It is not a tier file.

Each world is built as the registered run built it (harness.world, the run's own kind and
argument). It selects X2 with the cap CAP and runs through the engine's scalar windows for the
steps the registered run replayed:
- the whole horizon, decided at the run's end by the engine;
- or the first STEPS steps of the full definition, as one window of that width, with the
  whole-run conditions decided on those steps (energy_check.decide), as the registration decided
  them.
CAP, 3e-2, lies above every boundary world's saved largest integration error (FR-18's first
refused arm peaks at 2.28e-2 at row 1), so it decides no saved verdict.

Two rows have their own routes:
- **FR-3's registered plant** takes FR-3's own route (site_occupancy_acceptance_plants). The world
  runs with X2 to its 1 s row, the checkpoint's site_work_pJ[r0] is multiplied by (1 + 1e-6)
  (harness.registered_edit), and the run resumes. The record's binding must refuse the resume. The
  unplanted checkpoint resumes as a control.
- **The cap control** runs the first refused arm with the cap 2e-3, below its row-1 peak, and the
  cap must refuse it at step 1.

The judge compares each world's verdict with the saved one (results.json's worlds_detail[id]["X2"]
world_ok) and reports the engine's numbers beside the saved ones: counted steps, the median step
ratio, the out-of-band held steps, the largest check ratio and the integration error. The run
passes when every verdict is the saved one, the plant is refused by the binding while its control
resumes, and the cap control is refused at step 1 by the cap. The numbers come from different
programs (the replay evaluates its ledger on the host, the engine on the device), so they agree to
rounding, not bit for bit. A step whose |d''| or q lies at a threshold may be counted or held on
one side only.

Usage (cwd = a clean snapshot root; PYTHONPATH=src:.):
  python -B validation/energy_step_doubling/qualify_x2.py run OUT_JSON SAVED_WORLD_JSON
  python -B validation/energy_step_doubling/qualify_x2.py plant OUT_JSON
  python -B validation/energy_step_doubling/qualify_x2.py cap OUT_JSON
  python -B validation/energy_step_doubling/qualify_x2.py judge OUT_DIR RESULTS_JSON [RESULTS_JSON ...]
SAVED_WORLD_JSON is the registered run's own record of the world (its out/ID.json: kind, argument
and replayed steps). With X2_QUALIFY_SOLVER set to a time-integrator ID, every row runs with
execution.solver set to it: FR-8 rung 1's I3 (RUNG1_20261119 §5, D235), X2's rows under N2's ID.
"""

import copy
import json
import math
import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness as H  # noqa: E402  The registered harness's world builders, unchanged.

CAP = 3e-2
CAP_CONTROL = 2e-3
CHECK = "cells.execution.step_doubled_energy@1"
SOLVER_ENV = "X2_QUALIFY_SOLVER"  # Unset: each world's own solver, as registered.
WINDOW = 4096  # Whole-horizon runs; a first-STEPS run takes one window of STEPS.
REPORTED = (
    ("counted_steps", "counted_steps"),
    ("median_step_ratio", "median_step_ratio"),
    ("held_out_of_band", "held_out_of_band"),
    ("largest_ratio", "largest_ratio"),
    ("integration_error_largest", "integration_error_max"),
    ("integration_error_end", "integration_error_end"),
    ("largest_held_ratio", "held_largest_ratio_to_today"),
)


def selected(raw, cap):
    """The definition with X2 selected at `cap`; under SOLVER_ENV (FR-8 rung 1's I3, D235) with
    execution.solver set to that ID, the same rows run under a new time integrator."""
    out = copy.deepcopy(raw)
    out["execution"]["energy_check"] = dict(check=CHECK, integration_error_cap=cap)
    solver = os.environ.get(SOLVER_ENV)
    if solver:
        out["execution"]["solver"] = solver
    return out


def windows_for(raw, steps, cap):
    """(the engine's verdict, its summary, steps run, seconds) for the first `steps` steps of the
    full definition (all of them when steps is None or covers the horizon)."""
    from cells.definitions.specs import ConfigError, parse_spec
    from cells.execution import energy_check as energy
    from cells.execution.errors import NumericalError
    from cells.execution.grid import EventGrid
    from cells.execution.windows import WindowPolicy, iter_windows

    spec = parse_spec(selected(raw, cap))
    total = len(EventGrid(spec)) - 1
    whole = steps is None or steps >= total
    width = WINDOW if whole else int(steps)
    started = time.perf_counter()
    last, ran = None, 0
    try:
        for window in iter_windows(spec, WindowPolicy(width, "checkpoints")):
            last, ran = window, window.final.step_index
            if not whole and ran >= steps:
                break
        record = last.final.energy_check
        summary = energy.summary(record) if whole else energy.decide(record)
        verdict = dict(admitted=True, refusal=None)
    except (NumericalError, ConfigError) as error:
        summary = None if last is None else energy.summary(last.final.energy_check)
        verdict = dict(admitted=False, refusal=f"{type(error).__name__}: {error}")
    return verdict, summary, dict(planned=steps if not whole else total, ran=ran, whole=whole,
                                  seconds=time.perf_counter() - started)  # fmt: skip


def run_world(out_path, saved_path):
    saved = json.loads(Path(saved_path).read_text())
    raw, label, _ = H.world(saved["kind"], saved["arg"])
    verdict, summary, steps = windows_for(raw, saved["steps"], CAP)
    world_id = Path(saved_path).stem
    row = dict(id=world_id, label=label, kind=saved["kind"], arg=saved["arg"], cap=CAP,
               saved_steps=saved["steps"], steps=steps, summary=summary, **verdict)  # fmt: skip
    Path(out_path).write_text(json.dumps(row, indent=1, default=float))
    print(json.dumps(row, default=float)[:600], flush=True)


def run_plant(out_path):
    """FR-3's registered plant by its own route: run to 1 s with X2, edit, resume."""
    import dataclasses

    from cells.definitions.specs import ConfigError, parse_spec
    from cells.execution import energy_check as energy
    from cells.execution.errors import NumericalError
    from cells.execution.runner import run
    from validation.tissue import site_occupancy_acceptance_fixtures as af
    from validation.tissue import site_occupancy_acceptance_plants as plants
    from validation.tissue import site_occupancy_acceptance_qualification as generator

    started = time.perf_counter()
    raw = af.registered_world(plants.MIXED)
    head = generator._head(raw, plants.PLANT_AT_S)
    head["experiment"]["observation_times"] = [0.0, plants.PLANT_AT_S]
    first = run(parse_spec(selected(head, CAP)))
    spec = first.spec
    dt = spec.execution.dt
    resume_raw = generator._head(raw, plants.PLANT_AT_S + plants.RESUME_STEPS * dt)
    resume_raw["experiment"]["observation_times"] = [
        0.0, plants.PLANT_AT_S, plants.PLANT_AT_S + plants.RESUME_STEPS * dt]  # fmt: skip
    resume = parse_spec(selected(resume_raw, CAP))
    plant = dict(field="site_work_pJ", population="r0", at_s=plants.PLANT_AT_S)
    edit = H.registered_edit(spec, plant)
    state = type(first.final.state)(*(v for v in first.final.state))
    planted = dataclasses.replace(first.final, state=edit(state))
    size = float(abs(getattr(planted.state, plant["field"]) - getattr(state, plant["field"])).sum())

    def resumed(checkpoint):
        try:
            result = run(resume, checkpoint)
            return dict(
                admitted=True, refusal=None, summary=energy.summary(result.final.energy_check)
            )
        except (NumericalError, ConfigError) as error:
            return dict(admitted=False, refusal=f"{type(error).__name__}: {error}")

    row = dict(id="fr3plant-q1_eps_1e-1", cap=CAP, plant=plant, plant_size_pJ=size,
               first=dict(steps=int(first.final.step_index),
                          summary=energy.summary(first.final.energy_check)),
               control=resumed(first.final), planted=resumed(planted),
               seconds=time.perf_counter() - started)  # fmt: skip
    Path(out_path).write_text(json.dumps(row, indent=1, default=float))
    print(json.dumps(row, default=float)[:800], flush=True)


def run_cap(out_path):
    raw, label, _ = H.world("fr18", "fig5net100:16")
    verdict, summary, steps = windows_for(raw, 8, CAP_CONTROL)
    row = dict(id="cap-control-fr18-fig5net100-16", label=label, cap=CAP_CONTROL, steps=steps,
               summary=summary, **verdict)  # fmt: skip
    Path(out_path).write_text(json.dumps(row, indent=1, default=float))
    print(json.dumps(row, default=float)[:600], flush=True)


def _relative(a, b):
    if a is None or b is None:
        return None if a is b else math.inf
    scale = max(abs(a), abs(b))
    return 0.0 if scale == 0 else abs(a - b) / scale


def judge(out_dir, results):
    saved = {}
    for path in results:
        saved |= json.loads(Path(path).read_text())["worlds_detail"]
    rows, ok = [], True
    for path in sorted(Path(out_dir).glob("*.json")):
        if path.name == "results.json":
            continue
        row = json.loads(path.read_text())
        if row["id"] == "fr3plant-q1_eps_1e-1":
            good = (row["control"]["admitted"] and not row["planted"]["admitted"]
                    and "does not hold its state's residual" in row["planted"]["refusal"])  # fmt: skip
            rows.append(dict(id=row["id"], passed=good, plant_size_pJ=row["plant_size_pJ"],
                             control=row["control"]["admitted"],
                             planted=row["planted"]["refusal"]))  # fmt: skip
        elif row["id"].startswith("cap-control"):
            good = (not row["admitted"] and "exceeds the registration's cap at accepted step 1 "
                    in row["refusal"])  # fmt: skip
            rows.append(dict(id=row["id"], passed=good, refusal=row["refusal"]))
        else:
            reference = saved[row["id"]]["X2"]
            good = row["admitted"] == bool(reference["world_ok"])
            numbers = {}
            for mine, theirs in REPORTED:
                a = None if row["summary"] is None else row["summary"][mine]
                b = reference[theirs]
                numbers[mine] = dict(engine=a, saved=b, relative=_relative(a, b))
            rows.append(dict(id=row["id"], passed=good, admitted=row["admitted"],
                             saved_ok=reference["world_ok"], refusal=row["refusal"],
                             steps=row["steps"], numbers=numbers))  # fmt: skip
        ok = ok and good
    out = dict(passed=ok, rows=rows)
    (Path(out_dir) / "results.json").write_text(json.dumps(out, indent=1, default=float))
    for r in rows:
        print(("PASS " if r["passed"] else "FAIL ") + r["id"])
        for name, n in r.get("numbers", {}).items():
            print(f"    {name}: engine {n['engine']} saved {n['saved']} relative {n['relative']}")
    print("qualification", "passed" if ok else "FAILED")
    return 0 if ok else 1


def main(argv):
    try:
        if argv[1] == "run":
            run_world(argv[2], argv[3])
        elif argv[1] == "plant":
            run_plant(argv[2])
        elif argv[1] == "cap":
            run_cap(argv[2])
        elif argv[1] == "judge":
            return judge(argv[2], argv[3:])
        else:
            raise SystemExit(f"unknown action {argv[1]}")
    except Exception:
        traceback.print_exc()
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
