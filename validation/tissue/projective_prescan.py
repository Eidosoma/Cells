"""F2 pre-scan (protocol projective-c-qualification-v1, case F2-near-fold): the NaV1.2 scale.

One heredity cell (validation/tissue/surface_pump_v3_fixtures.heredity_cells)
started on the D branch, steady gates at the D voltage, with the NaV1.2
permeability scaled by s. Below the scale at which the D steady state
disappears, the trajectory lingers near the D ghost and then switches to H.
For each scale, fine steps of the definition's own IMEX step (resolved_pump_tissue@3
imex_step, jitted chunks; the per-row host checks are omitted because the scan
only selects the scale) run to the protocol's 1800 s horizon or until the
switch, the first chunk end with Vm < -50 mV (chunk resolution, CHUNK_STEPS).

Scan, from fine runs alone and before any projective run: scales descend from
--start in coarse steps until a run switches inside the horizon, then from the
last non-switching coarse scale in 1 % steps (the protocol's smallest step);
the first scale whose lingering time lies in 200-1200 s is selected. Every run
is recorded with its backend (amendment 1: the scan may run on the L4; the
judged F2 pair runs on CPU and its lingering time is taken from the CPU fine
reference).

Usage: python -m validation.tissue.projective_prescan --output DIR [--backend gpu]
"""

import argparse
import json
import time
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

jax.config.update("jax_enable_x64", True)

HORIZON_S = 1800.0  # F2-near-fold horizon_s.
LINGER_S = (200.0, 1200.0)  # F2: "the fine lingering time is 200-1200 s".
FINE_STEP = 0.01  # F2: "smallest scale step 1%".
SWITCH_V = -0.050  # near_fold_accuracy: switch at Vm < -50 mV.
CHUNK_STEPS = 1000  # 1 s at dt = 1 ms: the switch-time resolution of the scan.


def f2_definition(scale, *, end_time=HORIZON_S, backend="cpu", every=30.0):
    """F2's world: one heredity cell on the D branch, NaV1.2 scaled by scale."""
    from validation.tissue import projective_fixtures as fixtures
    from validation.tissue import surface_pump_v3_fixtures as heredity

    d = heredity.HEREDITY_STATES["D"][:4]
    return heredity.heredity_cells(
        [d],
        end_time=end_time,
        observation_times=fixtures.grid_times(1e-3, end_time, every),
        gate_voltages=[d[0]],
        nav_m_s=scale * heredity.HEREDITY_NAV_M_S,
        backend=backend,
    )


def lingering(scale, *, backend, horizon=HORIZON_S):
    """Fine steps of one scale until the switch or the horizon: its record."""
    from cells.core.schedule import control_values
    from cells.core.specs import parse_spec
    from cells.models import surface_pump_projective as readouts
    from cells.models import surface_pump_v3 as model

    spec = parse_spec(f2_definition(scale, end_time=horizon, backend=backend))
    state, p = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    control = type(controls)(*(v[0] for v in controls))
    host = readouts.host_layout(p)
    device = jax.devices("gpu" if backend == "gpu" else "cpu")[0]
    y, pd, cd = jax.device_put((state, p, control), device)
    dt = spec.execution.dt

    @jax.jit
    def advance(y):
        def body(carry, _):
            x, ok = carry
            new, valid = model.imex_step(x, dt, cd, pd)
            return (new, ok & valid), None

        return jax.lax.scan(body, (y, jnp.asarray(True)), None, length=CHUNK_STEPS)[0]

    started, steps, valid, switch = time.perf_counter(), 0, True, None
    total = round(horizon / dt)
    while steps < total:
        y, ok = advance(y)
        steps += CHUNK_STEPS
        valid &= bool(ok)
        row = model.STATE_TYPE(*(np.asarray(v) for v in jax.device_get(y)))
        vm = readouts.membrane_voltage(row, host)
        if not valid:
            break
        if np.min(vm) < SWITCH_V:
            switch = steps * dt
            break
    return dict(
        scale=round(float(scale), 6),
        backend=backend,
        device=str(device),
        switched=switch is not None,
        switch_time_s=switch,
        valid=bool(valid),
        steps=steps,
        final_vm_V=float(np.min(vm)),
        wall_s=time.perf_counter() - started,
    )


def scan(output, *, backend, start=1.0, coarse=0.1, lowest=0.05):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    runs = []

    def record(scale):
        entry = lingering(scale, backend=backend)
        runs.append(entry)
        print(json.dumps(entry), flush=True)
        (out / "prescan-runs.json").write_text(json.dumps(runs, indent=1) + "\n")
        return entry

    selected, upper = None, None
    scale = start
    while scale >= lowest:  # Coarse: bracket the disappearance of D.
        entry = record(scale)
        if not entry["valid"]:
            break
        if entry["switched"]:
            break
        upper = scale
        scale = round(scale - coarse, 6)
    else:
        entry = None
    if entry is not None and entry["valid"] and entry["switched"] and upper is not None:
        scale = round(upper - FINE_STEP, 6)
        while scale > entry["scale"] - 1e-9:  # Fine: 1 % steps below the last D scale.
            fine = record(scale)
            if fine["switched"] and LINGER_S[0] <= fine["switch_time_s"] <= LINGER_S[1]:
                selected = fine
                break
            if fine["switched"] and fine["switch_time_s"] < LINGER_S[0]:
                break  # Lingering fell below 200 s between two 1 % steps.
            scale = round(scale - FINE_STEP, 6)
    result = dict(
        kind="cells.projective_f2_prescan@1",
        protocol="projective-c-qualification-v1",
        case="F2-near-fold",
        backend=backend,
        horizon_s=HORIZON_S,
        lingering_window_s=list(LINGER_S),
        smallest_step=FINE_STEP,
        switch_resolution_s=CHUNK_STEPS * 1e-3,
        runs=runs,
        selected_scale=None if selected is None else selected["scale"],
        selected=selected,
    )
    with open(out / "prescan.json", "x") as stream:
        stream.write(json.dumps(result, indent=1) + "\n")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", required=True)
    parser.add_argument("--backend", choices=("cpu", "gpu"), default="cpu")
    parser.add_argument("--start", type=float, default=1.0)
    parser.add_argument("--coarse", type=float, default=0.1)
    args = parser.parse_args(argv)
    result = scan(args.output, backend=args.backend, start=args.start, coarse=args.coarse)
    print(json.dumps(dict(selected_scale=result["selected_scale"], runs=len(result["runs"]))))


if __name__ == "__main__":
    main()
