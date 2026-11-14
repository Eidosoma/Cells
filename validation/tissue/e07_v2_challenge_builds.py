"""E07-v2's challenge pairings: definition-time builds only; nothing is stepped (D151).

E07-v2's write-clear-challenge line challenges a sheet after release. This check asks
whether the composite admits each challenge alongside scheduled replacement, before that
line is relied on. Both pairings use the E07-v1 sheet world: resolved_pump_replacement@1
(scheduled_cell_replacement@1 over resolved_pump_tissue@3), with the sheet70 start and the
37-cell disc. The replacement schedule is the arm a-donor-fast-k1-d37-s1.0 at development
seed 101; it is used only as a schedule, and nothing runs.

1. second cue: sheet70's cue populations (Na leak x CUE_FACTOR on the 37-cell disc's
   membranes, as heredity_pilot.sheet_definition declares them), with a schedule that
   opens them on [CHALLENGE_ON_S, CHALLENGE_OFF_S), after replacement has begun. The check
   covers the replacement identity and its composite form
   (pump_composite_spec.frozen_definition).
2. injected current: resolved_pump_composite@1 with the operators
   [scheduled_cell_replacement@1, electrode_current_injection@1], and in the reverse order.
   It has one electrode in the disc's centre cell, carrying the 3 M KCl fractions with M
   (the sheet's monovalent anion) in place of Cl. The current step is on the same interval.

Each build goes as far as a run goes before its first step, then stops:
  definition   parse_spec: the composite's parse and check_definition, with each
               operator's checks;
  binding      initial values;
  step checks  check_steps at dt (the operators' worst-case inner definition);
  trace        one checked step traced at the challenge's control (jax.jit(...).lower);
               it is not compiled and not run.
The first refusal is recorded with its stage, its type and its exact message.

Usage: python -m validation.tissue.e07_v2_challenge_builds --output DIR
"""

import argparse
import copy
import sys
import time
import traceback
from pathlib import Path

import jax

jax.config.update("jax_enable_x64", True)

import jax.numpy as jnp  # noqa: E402
import numpy as np  # noqa: E402

from cells.core import pump_composite_spec as composite_spec  # noqa: E402
from cells.core.specs import parse_spec  # noqa: E402
from cells.models import cell_replacement as replacement_model  # noqa: E402
from cells.models import pump_composite  # noqa: E402
from validation.stationary import worlds  # noqa: E402
from validation.tissue import e07_v1_run as run  # noqa: E402
from validation.tissue import e07_v1_turnover as e7  # noqa: E402
from validation.tissue import heredity_pilot as pilot  # noqa: E402
from validation.tissue import surface_pump_v3_fixtures as fixtures  # noqa: E402

BASE_ARM, BASE_SEED = "a-donor-fast-k1-d37-s1.0", 101  # A development seed: a schedule only.
CHALLENGE_ON_S, CHALLENGE_OFF_S = 600.0, 602.0  # After replacement has begun; sheet70's 2 s.
CURRENT_A = -2e-11  # A hyperpolarizing step (the sign convention of current_injection).
CARRIERS = {"K": 0.4912, "M": 0.5088}  # current_injection.DEFAULT_CARRIERS, M for Cl.
INJECTION = "electrode_current_injection@1"


def base():
    record = run.schedule(run.find_arm(BASE_ARM), BASE_SEED, dt=e7.DT)
    raw, checks = run.build(record)
    return raw, record, checks


def disc_cells():
    cells, _ = worlds.hexagon(pilot.SHEET_RADIUS)
    return [i for i, c in enumerate(cells) if worlds.ring(c) <= pilot.DISCS[37]]


def centre_cell():
    cells, _ = worlds.hexagon(pilot.SHEET_RADIUS)
    return next(i for i, c in enumerate(cells) if worlds.ring(c) == 0)


def with_second_cue(raw):
    raw = copy.deepcopy(raw)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    for i in disc_cells():
        leak = m["membranes"][i]["permeability_m_per_s"]["Na"]
        m["channels"].append(fixtures.channel(f"cue_{i}", i, pilot.NALEAK_LAW_ID, "Na",
                                              (pilot.CUE_FACTOR - 1) * leak, 1.0, []))  # fmt: skip
        e["channel_controls"].append(dict(channel_id=f"cue_{i}", schedule=[
            dict(time=0.0, availability=0.0), dict(time=CHALLENGE_ON_S, availability=1.0),
            dict(time=CHALLENGE_OFF_S, availability=0.0)]))  # fmt: skip
    x["channel_capacity"] = len(m["channels"])
    return raw


def with_injection(raw, replacement_first):
    comp = composite_spec.frozen_definition(raw)
    cell = f"cell_{centre_cell()}"
    block = dict(law=INJECTION, electrodes=[dict(cell_id=cell, carriers=dict(CARRIERS))])
    ops = comp["model"]["operators"]
    comp["model"]["operators"] = [*ops, block] if replacement_first else [block, *ops]
    comp["experiment"]["injection_controls"] = [dict(cell_id=cell, schedule=[
        dict(time=0.0, current_A=0.0), dict(time=CHALLENGE_ON_S, current_A=CURRENT_A),
        dict(time=CHALLENGE_OFF_S, current_A=0.0)])]  # fmt: skip
    return comp


def build(raw):
    """Definition, binding, step checks and one traced step; the first refusal stops it."""
    out, tick = dict(stages={}), time.perf_counter()

    def refused(stage, error):
        out.update(admitted=False, refused_at=stage, error_type=type(error).__name__,
                   message=str(error), traceback_tail=traceback.format_exc().splitlines()[-8:],
                   seconds=time.perf_counter() - tick)  # fmt: skip
        return out

    try:
        spec = parse_spec(raw)
    except Exception as error:  # noqa: BLE001  (every refusal is the finding)
        return refused("definition", error)
    out["stages"]["definition"] = "admitted"
    out["model"] = raw["model"]["id"]
    try:
        if raw["model"]["id"] == replacement_model.MODEL_ID:
            model, controls = replacement_model, replacement_model.control_values
        else:
            model, controls = pump_composite.model_for(spec.model), composite_spec.control_values
            out["identity"] = composite_spec.identity(spec.model)
        state, p = model.initial_values(spec)
    except Exception as error:  # noqa: BLE001
        return refused("binding", error)
    out["stages"]["binding"] = "admitted"
    dt = spec.execution.dt
    try:
        model.check_steps(spec, np.array([dt]), None)
    except Exception as error:  # noqa: BLE001
        return refused("step checks", error)
    out["stages"]["step checks"] = "admitted"
    try:
        c = controls(spec, [CHALLENGE_ON_S])
        row = type(c)(*(jnp.asarray(np.asarray(v)[0]) for v in c))
        q, y = jax.tree.map(jnp.asarray, p), jax.tree.map(jnp.asarray, state)
        jax.jit(lambda y_, c_, q_: model.checked_step(y_, dt, c_, q_, q_.active)).lower(y, row, q)
    except Exception as error:  # noqa: BLE001
        return refused("trace", error)
    out["stages"]["trace"] = "admitted"
    out.update(admitted=True, seconds=time.perf_counter() - tick)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    raw, record, checks = base()
    first_event_s = min(k for k, *_ in record["events"]) * record["dt"]
    cases = {
        "second cue, replacement identity": with_second_cue(raw),
        "second cue, composite form": composite_spec.frozen_definition(with_second_cue(raw)),
        "injection after replacement (operators: replacement, injection)": with_injection(
            raw, True
        ),
        "injection before replacement (operators: injection, replacement)": with_injection(
            raw, False
        ),
    }
    results = {name: build(case) for name, case in cases.items()}
    value = dict(
        kind="cells.e07_v2_challenge_builds@1",
        note="definition-time builds only; nothing was stepped",
        base=dict(
            arm=BASE_ARM,
            seed=BASE_SEED,
            dt=record["dt"],
            end_s=record["planned_end_s"],
            first_replacement_event_s=first_event_s,
            events=len(record["events"]),
            driver_checks=checks,
        ),  # fmt: skip
        challenge=dict(
            on_s=CHALLENGE_ON_S,
            off_s=CHALLENGE_OFF_S,
            cue_cells=disc_cells(),
            cue_factor=pilot.CUE_FACTOR,
            electrode_cell=f"cell_{centre_cell()}",
            current_A=CURRENT_A,
            carriers=CARRIERS,
        ),  # fmt: skip
        results=results,
    )
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    run.write_json(out / "builds.json", value)
    for name, r in results.items():
        verdict = "admitted" if r["admitted"] else f"REFUSED at {r['refused_at']}: {r['message']}"
        print(f"{name}: {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
