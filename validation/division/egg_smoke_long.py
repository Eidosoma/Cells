"""Egg-scale smoke test to J1's 35-min horizon (cell-division design S0b step 4; development).

Engine model: resolved_pump_tissue@3, unmodified: the stage-2 egg of
validation/tissue/egg_scale_smoke.py (its definition, anchor "consistent"), IMEX ARS(2,2,2) at
the qualified 1 ms step, now for 2100 s (2.1e6 steps). At that length host checks on every
row are impractical (stage 2: 2.5 ms per row), so the run goes through the vector-window
runner (core/vector_windows.run_vector_windowed), whose device checks
(surface_pump_v3.device_checks) test every accepted row in the compiled window and refuse
the run on the first failure. Each ledger's residual over its checked bound is computed on
the observed rows (every --observe-every s) with the bounds both checks use
(surface_pump.ledger_limits with surface_pump_v3.channel_magnitudes) and each row's true
accepted-step count; the device diagnostics are maxima over every row.

Usage: python -m validation.division.egg_smoke_long --output DIR [--end S] [--observe-every S]
       [--window STEPS]
"""

import argparse
import json
import time
import traceback
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

jax.config.update("jax_enable_x64", True)

from validation.tissue import egg_scale_smoke as smoke  # noqa: E402

DT = 1e-3


def ledger_ratios(spec, rows, steps):
    """Per-ledger max |residual| / bound over the given rows (each with its step count)."""
    from cells.models import surface_pump as first
    from cells.models import surface_pump_v3 as v3

    p = v3.initial_values(spec)[1]
    constants = v3.device_check_constants(spec)

    def one(row, count):
        b = v3.device_balances(row, p)
        _, bounds = first.ledger_limits(
            row,
            p,
            constants.material_atol,
            constants.energy_rtol,
            steps=count,
            magnitudes=v3.channel_magnitudes(row, p, xp=jnp),
            xp=jnp,
        )
        return jnp.stack(
            [
                jnp.max(jnp.abs(v) / jnp.broadcast_to(bound, jnp.shape(v)), initial=0.0)
                for v, bound in zip(b.values(), bounds, strict=True)
            ]
        )

    ratios = np.asarray(jax.jit(jax.vmap(one))(rows, jnp.asarray(steps)))
    names = list(first.LEDGERS)
    k = ratios.argmax(axis=0)
    return {
        name: dict(max_ratio=float(ratios[k[j], j]), row=int(steps[k[j]]))
        for j, name in enumerate(names)
    }


def main(argv=None):
    from cells.core.batch import BatchSpec, WorldSpec
    from cells.core.specs import parse_spec
    from cells.core.vector_windows import run_vector_windowed
    from cells.core.windows import WindowPolicy
    from cells.models import surface_pump_v3 as v3

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", required=True)
    parser.add_argument("--end", type=float, default=2100.0)
    parser.add_argument("--observe-every", type=float, default=10.0)
    parser.add_argument("--window", type=int, default=4096)
    args = parser.parse_args(argv)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    raw, inputs = smoke.egg_definition(
        end_time=args.end, dt=DT, anchor="consistent", observe_every=args.observe_every
    )
    out = dict(part="long", model=raw["model"]["id"], inputs=inputs, end_s=args.end, dt=DT)
    found = []

    def sink(window):
        for _, obs in window.observations.items():
            found.append(obs)

    try:
        spec = parse_spec(raw)
        batch = BatchSpec((WorldSpec(1, spec),), 1, 2**53 - 1, 2**53 - 1)
        result = run_vector_windowed(batch, WindowPolicy(args.window, "checkpoints"), sink=sink)
        out["device_checks"] = "passed (every accepted row, in the compiled windows)"
        out["device_diagnostics"] = dict(result.worlds[1].diagnostics)
        out["timings"] = dict(result.timings)
        out["resources"] = {k: v for k, v in result.resources.items() if np.isscalar(v)}
        times = np.concatenate([np.asarray(o.times) for o in found])
        fields = v3.STATE_TYPE._fields
        rows = v3.STATE_TYPE(
            *(
                jnp.asarray(np.concatenate([np.asarray(getattr(o, f)) for o in found]))
                for f in fields
            )
        )
        steps = np.rint(times / DT).astype(np.int64)
        out["observed_rows"] = len(times)
        out["ledger_ratio_to_bound_at_observed_rows"] = ledger_ratios(spec, rows, steps)
        vm = np.concatenate([np.asarray(o.membrane_voltage_V)[:, 0] for o in found])
        amount = np.concatenate([np.asarray(o.amount)[:, :, 0] for o in found])
        out["observed"] = dict(
            times_s=times[:: max(1, len(times) // 50)].tolist(),
            membrane_voltage_V=vm[:: max(1, len(times) // 50)].tolist(),
            vm_change_V=float(vm[-1] - vm[0]),
            amount_change_fmol=(amount[-1] - amount[0]).tolist(),
            cytosol_mM_end=(amount[-1] / smoke.WATER_VOLUME_PL).tolist(),
        )
        out["verdict"] = "accepted"
    except Exception as error:  # Kept: a refusal is the result.
        out.update(verdict="refused", refusal=repr(error), tb=traceback.format_exc())
    out["provenance"] = smoke.provenance()
    out["wall_s"] = time.perf_counter() - started
    (output / "long.json").write_text(json.dumps(out, indent=1, default=float) + "\n")
    print("long", out["verdict"], f"{out['wall_s']:.1f} s", flush=True)


if __name__ == "__main__":
    main()
