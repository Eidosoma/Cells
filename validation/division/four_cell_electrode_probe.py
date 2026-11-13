"""Probe for stage S5 (the lead, 13 November): the electrode ledger of a static four-cell egg.

docs/CELL_DIVISION_S5_DESIGN.md, risk 1. At four cells the held bath couples to four charged
free nodes. That is outside D148's exactness condition (no held node coupled to three or more
charged free nodes), so the electrode ledger's telescoping rests on how XLA associates the node
sum of the bath's plate charge. This probe measures that before any S5 code exists, on a static
world with no partition.

Engine models: resolved_pump_composite@1 over resolved_pump_tissue@3 with
electrode_current_injection@1 only (the Rm1 setting). There is no S5 operator, no partition and
no cleft.

The world is built from the S0 egg smoke test's declared egg (validation/tissue/egg_scale_smoke:
dL74's water volume and cytosol activities, Steinberg's bath, the old membrane's P from Rin
852 kOhm, 0.62 uF/cm2). It reads neither the J1 inputs nor the J1 record. The cells:
* each is a quarter egg: a quarter of the water volume and contents, and a quarter of the folded
  area and the capacitance, with the same permeability per area;
* each has its own patch on one held bath;
* each charge anchor is computed from its own rounded inventory (the smoke test's "consistent"
  anchor).

Pulses: 3e-8 A for 1.2 s every 10 s, alternating in sign, through one electrode per cell. The
carriers are K 0.4912 and Cl 0.5088, the injection law's default. Cell k's train starts at
2.5 k s, so the cells' states differ, and three species move in every cell: K and Cl by
injection, Na and K through the membrane.

Output: the electrode ledger's residual against its bound on every row, from the composite's
device balances and ledger_limits as cleft_egg_engine.probe evaluates them:
* the worst ratio per window and overall;
* the signed residual and its bound at each window's end. A systematic drift grows linearly
  with the steps, and so does the bound, so their per-step slopes decide the ratio at any
  horizon.
Refused steps and failing device checks are counted. --cells 1 runs the one-cell control (one
quarter egg, cell 0's train), D148's exact case. No observation is taken.

Usage: python -m validation.division.four_cell_electrode_probe --output FILE [--cells N]
       [--dt S] [--steps N] [--window N]
"""

import argparse
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    for entry in (ROOT / "src", ROOT):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))

STATUS = (
    "Development probe for S5's risk 1: the electrode ledger of a static egg-scale world "
    "(no partition, no S5 code; not judged)."
)
DT = 2.5e-4  # S3's judged step.
STEPS = 1_780_000  # S3's bounded probe: 1.78e6 steps at 0.25 ms.
WINDOW = 89_000  # 20 windows, as S3's probe.
PULSE_A = 3e-8
PULSE_S = 1.2
PERIOD_S = 10.0
STAGGER_S = 2.5
CARRIERS = {"K": 0.4912, "Cl": 0.5088}  # current_injection.DEFAULT_CARRIERS.


def provenance():
    def out(*args):
        return subprocess.run(
            ["git", "-C", str(ROOT), *args], capture_output=True, text=True
        ).stdout

    return dict(
        argv=sys.argv,
        host=platform.node(),
        revision=out("rev-parse", "HEAD").strip(),
        dirty=out("status", "--porcelain", "--untracked-files=no"),
    )


def pulse_schedule(cell, end, dt):
    """[(time, current)] of cell's train from time 0 (every time an exact multiple of dt)."""

    def grid(t):
        return round(t / dt) * dt

    rows, k = [dict(time=0.0, current_A=0.0)], 0
    while STAGGER_S * cell + PERIOD_S * k < end:
        start = grid(STAGGER_S * cell + PERIOD_S * k)
        stop = grid(start + PULSE_S)
        current = PULSE_A * (-1) ** k
        if start == 0.0:
            rows[0] = dict(time=0.0, current_A=current)
        else:
            rows.append(dict(time=start, current_A=current))
        if stop < end:
            rows.append(dict(time=stop, current_A=0.0))
        k += 1
    return rows


def definition(cells=4, dt=DT, steps=STEPS):
    """The static world of `cells` quarter eggs on one held bath, pulsed (raw definition)."""
    import copy

    from cells.core import pump_composite_spec as cs
    from cells.processes.electrochemistry import CHARGE_PER_FMOL
    from validation.tissue import egg_scale_smoke as egg

    end = steps * dt
    ids = [s for s, _ in egg.SPECIES]
    z = dict(egg.SPECIES)
    vm, permeability = egg.rest_and_permeability()
    volume = egg.WATER_VOLUME_PL / 4
    area = egg.FOLDED_AREA_M2 / 4
    capacitance = egg.CAPACITANCE_F / 4
    inside = {s: egg.CYTOSOL_mM[s] * volume for s in ids}
    background = capacitance * vm / CHARGE_PER_FMOL - math.fsum(z[s] * inside[s] for s in ids)
    anchor = CHARGE_PER_FMOL * math.fsum((background, *(z[s] * inside[s] for s in ids)))
    always = [dict(time=0.0, availability=1.0)]
    names = [f"cell{k}" for k in range(cells)]
    raw = dict(
        schema_version=1,
        model=dict(
            id="resolved_pump_tissue@3",
            temperature_K=egg.TEMPERATURE_K,
            species=[dict(id=s, valence=v) for s, v in egg.SPECIES],
            cells=[
                dict(
                    id=name,
                    volume_pL=volume,
                    initial_amount_fmol=dict(inside),
                    fixed_charge_equivalent_fmol=background,
                    initial_charge_C=anchor,
                )
                for name in names
            ],
            extracellular=[
                dict(
                    id="steinberg",
                    volume_pL=1.0,
                    initial_amount_fmol=dict(egg.BATH_mM),
                    fixed_charge_equivalent_fmol=-math.fsum(z[s] * egg.BATH_mM[s] for s in ids),
                    initial_charge_C=0.0,
                    reservoir=True,
                    boundary_potential_V=0.0,
                )
            ],
            membranes=[
                dict(
                    id=f"membrane{k}",
                    inside=name,
                    outside="steinberg",
                    area_m2=area,
                    capacitance_F=capacitance,
                    permeability_m_per_s=dict(permeability),
                    law="constant_field@1",
                    pump=None,
                    calcium_pump=None,
                )
                for k, name in enumerate(names)
            ],
            junctions=[],
            faces=[],
            closure=dict(
                law="resolved_capacitor_components_current_continuity@1", gauge_reference=None
            ),
            channels=[],
        ),
        experiment=dict(
            end_time=end,
            observation_times=[0.0, end],
            membrane_controls=[
                dict(membrane_id=f"membrane{k}", schedule=copy.deepcopy(always))
                for k in range(cells)
            ],
            junction_controls=[],
            pump_controls=[],
            calcium_pump_controls=[],
            channel_controls=[],
        ),
        execution=dict(
            dt=dt,
            capacity=cells,
            extracellular_capacity=1,
            membrane_capacity=cells,
            edge_capacity=0,
            face_capacity=0,
            channel_capacity=0,
            backend="cpu",
            jit=True,
            precision="float64",
            solver="imex_ars222_face_electromigration@1",
            field_solver="capacitive_reduction_gauged_damped_newton@2",
            max_steps=steps + 8,
            max_trace_bytes=2**33,
            material_balance_atol_fmol={s: 1e-10 for s in ids},
        ),
    )
    out = cs.frozen_definition(raw)
    out["model"]["operators"] = [
        dict(
            law="electrode_current_injection@1",
            electrodes=[dict(cell_id=name, carriers=dict(CARRIERS)) for name in names],
        )
    ]
    out["experiment"]["injection_controls"] = [
        dict(cell_id=name, schedule=pulse_schedule(k, end, dt)) for k, name in enumerate(names)
    ]
    inputs = dict(
        cells=cells,
        rest_V=vm,
        cell_volume_pL=volume,
        cell_capacitance_F=capacitance,
        cell_anchor_C=anchor,
        cell_background_fmol=background,
        bath_coupled_free_nodes=cells,
    )
    return out, inputs


def probe(cells=4, dt=DT, steps=STEPS, width=WINDOW, chunk=4096):
    """The electrode ledger on every row (module docstring), in windows of `width` steps."""
    import jax

    jax.config.update("jax_enable_x64", True)
    import jax.numpy as jnp
    import numpy as np

    from cells.core import runner
    from cells.core.schedule import control_values
    from cells.core.specs import parse_spec
    from cells.core.state import initialise
    from cells.models.registry import get_model

    started = time.perf_counter()
    raw, inputs = definition(cells, dt, steps)
    spec = parse_spec(raw)
    model = get_model(spec.model)
    times = runner.timeline(spec)
    total = len(times) - 1
    checkpoint = initialise(spec)
    state, layout = checkpoint.state, checkpoint.layout
    parameters = model.parameters(spec, layout)
    p = model.initial_values(spec)[1]
    constants = model.device_check_constants(spec)
    k_electrode = list(model.LEDGERS).index("electrode")

    def one(previous, row, count):
        failed, _ = model.device_checks(previous, row, p, constants, count)
        value = model.device_balances(row, p)["electrode"]
        _, bounds = model.ledger_limits(
            row,
            p,
            constants.material_atol,
            constants.energy_rtol,
            steps=count,
            magnitudes=model.magnitudes(row, p, xp=jnp),
            xp=jnp,
        )
        bound = jnp.ravel(jnp.broadcast_to(bounds[k_electrode], jnp.shape(value)))
        value = jnp.ravel(value)
        ratio = jnp.abs(value) / bound
        i = jnp.argmax(ratio)
        return failed, jnp.stack([ratio[i], value[i], bound[i]])

    check = jax.jit(jax.vmap(one))
    compiled, windows = {}, []
    refused, first_refused, failing, failed_checks = 0, None, 0, set()
    best, best_time = np.zeros(3), 0.0
    compile_s = 0.0
    for start in range(0, total, width):
        stop = min(total, start + width)
        window = times[start : stop + 1]
        count = runner.integration_steps(spec, window)
        args = (state, count, control_values(spec, window[:-1]), parameters, layout.active)
        if len(count) not in compiled:
            tick = time.perf_counter()
            compiled[len(count)] = runner._compiled_discrete_rollout.lower(
                *args, model.checked_step
            ).compile()
            compile_s += time.perf_counter() - tick
        final, history, valid = compiled[len(count)](*args)
        bad = np.flatnonzero(~np.asarray(valid))
        refused += len(bad)
        if len(bad) and first_refused is None:
            first_refused = float(window[bad[0]])
        history = jax.tree.map(np.asarray, history)
        previous = jax.tree.map(
            lambda s, h: np.concatenate((np.asarray(s)[None], h[:-1])), state, history
        )
        window_best, last = np.zeros(3), None
        for a in range(0, len(count), chunk):
            b = min(len(count), a + chunk)
            failed, worst = (
                np.asarray(x)
                for x in check(
                    jax.tree.map(lambda v, a=a, b=b: jnp.asarray(v[a:b]), previous),
                    jax.tree.map(lambda v, a=a, b=b: jnp.asarray(v[a:b]), history),
                    jnp.arange(start + a + 1, start + b + 1),
                )
            )
            rows = np.flatnonzero(failed.any(axis=1))
            failing += len(rows)
            for r in rows:
                failed_checks |= {
                    c for c, f in zip(model.DEVICE_CHECKS, failed[r], strict=True) if f
                }
            r = int(np.argmax(worst[:, 0]))
            if worst[r, 0] > window_best[0]:
                window_best = worst[r]
            if worst[r, 0] > best[0]:
                best, best_time = worst[r], float(window[a + r + 1])
            last = worst[-1]
        windows.append(
            dict(
                end_s=float(window[-1]),
                steps=int(stop),
                max_ratio=float(window_best[0]),
                last_row=dict(
                    ratio=float(last[0]), signed_residual_C=float(last[1]), bound_C=float(last[2])
                ),
            )
        )
        print(json.dumps(windows[-1]), flush=True)
        state = final
        if len(bad):
            break
    ends = [w for w in windows if w["steps"] > 0]
    slope = None
    if len(ends) >= 4:
        half = ends[len(ends) // 2 :]  # The later half: a systematic drift is linear there.
        x = np.array([w["steps"] for w in half], dtype=float)
        y = np.array([w["last_row"]["signed_residual_C"] for w in half])
        q = np.array([w["last_row"]["bound_C"] for w in half])
        slope = dict(
            residual_C_per_step=float(np.polyfit(x, y, 1)[0]),
            bound_C_per_step=float(np.polyfit(x, q, 1)[0]),
        )
        slope["asymptotic_ratio"] = (
            abs(slope["residual_C_per_step"]) / slope["bound_C_per_step"]
            if slope["bound_C_per_step"] > 0
            else None
        )
    return dict(
        status=STATUS,
        inputs=inputs,
        dt=dt,
        steps=total,
        end_s=float(times[-1]),
        refused_steps=refused,
        first_refused_time_s=first_refused,
        device_failing_rows=failing,
        device_failed_checks=sorted(failed_checks),
        electrode=dict(
            max_ratio=float(best[0]),
            signed_residual_C=float(best[1]),
            bound_C=float(best[2]),
            time_s=best_time,
        ),
        later_half_slopes=slope,
        windows=windows,
        compile_s=compile_s,
        wall_s=time.perf_counter() - started,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--output", required=True)
    parser.add_argument("--cells", type=int, default=4)
    parser.add_argument("--dt", type=float, default=DT)
    parser.add_argument("--steps", type=int, default=STEPS)
    parser.add_argument("--window", type=int, default=WINDOW)
    args = parser.parse_args(argv)
    result = probe(args.cells, args.dt, args.steps, args.window)
    result["provenance"] = provenance()
    Path(args.output).write_text(json.dumps(result, indent=1))
    e = result["electrode"]
    print(
        f"cells {args.cells}: electrode max |residual|/bound {e['max_ratio']:.3e} "
        f"({e['signed_residual_C']:.3e} C against {e['bound_C']:.3e} C at {e['time_s']} s); "
        f"refused {result['refused_steps']}, failing rows {result['device_failing_rows']}"
    )


if __name__ == "__main__":
    main()
