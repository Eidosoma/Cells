"""Linear-mode analysis of projective_forward_euler@1 around a fine-engine state.

The Jacobian of one fine checked step (the model's own checked_step, by
jax.jacfwd) at a state gives each mode's per-step amplification rho and rate
log(rho)/dt. For a burst of K steps, chord m and jump ratio r, a mode's cycle
growth is numerics/projective.cycle_amplification(rho, K, m, r). Accumulator
fields (transfers, dissipation, work) are integrators with rho = 1 exactly and
do not feed back; they are reported as neutral. The analysis is local and
linear: it states which jumps the spectrum at that state admits, not a bound
for the nonlinear run.
"""

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.schedule import control_values
from cells.models.registry import get_model
from cells.numerics import projective as method


def step_jacobian(spec, state, time=0.0):
    """(Jacobian of the flattened checked step, field slices, valid) at a host state."""
    model = get_model(spec.model)
    _, layout = model.initial_values(spec)
    controls = control_values(spec, [time])
    control = type(controls)(*(v[0] for v in controls))
    params = model.parameters(spec, layout)
    shapes = [np.shape(v) for v in state]
    sizes = [int(np.prod(s)) for s in shapes]
    offsets = np.cumsum([0, *sizes])
    dt = spec.execution.dt

    def unflatten(x):
        return model.STATE_TYPE(
            *(x[a:b].reshape(s) for a, b, s in zip(offsets[:-1], offsets[1:], shapes, strict=True))
        )

    def step(x):
        new, valid = model.checked_step(unflatten(x), dt, control, params, layout.active)
        return jnp.concatenate([jnp.ravel(v) for v in new]), valid

    x0 = jnp.concatenate([jnp.ravel(jnp.asarray(v, dtype=jnp.float64)) for v in state])
    _, valid = jax.jit(step)(x0)
    jacobian = jax.jit(jax.jacfwd(lambda x: step(x)[0]))(x0)
    slices = {
        name: (int(a), int(b))
        for name, a, b in zip(model.STATE_TYPE._fields, offsets[:-1], offsets[1:], strict=True)
    }
    return np.asarray(jacobian), slices, bool(valid)


DYNAMIC_FIELDS = (
    "amount_increment",
    "extracellular_amount_increment",
    "channel_gate",
    "junction_gate",
)


def modes(spec, state, time=0.0):
    """Eigenvalues of the step map restricted to the dynamic fields (inventories, gates).

    Accumulators do not enter any rate, so the dynamic block's spectrum is the
    whole non-neutral spectrum. Returns (rho, rate 1/s), sorted from slowest.
    """
    jacobian, slices, valid = step_jacobian(spec, state, time)
    if not valid:
        raise ValueError("The fine step refused the analysed state")
    index = np.concatenate([np.arange(*slices[k]) for k in DYNAMIC_FIELDS if k in slices])
    block = jacobian[np.ix_(index, index)]
    rho = np.linalg.eigvals(block)
    rate = np.log(rho.astype(np.complex128)) / spec.execution.dt
    order = np.argsort(np.abs(rate.real))
    return rho[order], rate[order]


def heredity_modes(output, *, burst=2000, slope=250, jumps=(2.0, 10.0, 30.0, 60.0, 120.0)):
    """Modes of the @3 heredity H and D steady states (surface_pump_v3_fixtures) and cycles.

    Writes spectrum.json: per state, the rates (1/s) of every non-neutral mode
    and, per jump duration, the largest cycle growth over the fast modes (rate
    magnitude above 1/s) and the slow-mode cycle factor against exact decay.
    """
    import json
    from pathlib import Path

    from cells.core.specs import parse_spec
    from cells.core.state import initialise
    from validation.tissue import surface_pump_v3_fixtures as heredity

    report = dict(burst_steps=burst, slope_steps=slope, states={})
    for name in ("H", "D"):
        state = heredity.HEREDITY_STATES[name]
        spec = parse_spec(heredity.heredity_cells([state[:4]], end_time=1.0))
        initial = initialise(spec)
        rho, rate = modes(spec, tuple(np.asarray(v) for v in initial.state))
        dt = spec.execution.dt
        keep = np.abs(rate) > 1e-9
        fast = keep & (np.abs(rate.real) > 1.0)
        slow = keep & ~fast
        cycles = []
        for duration in jumps:
            ratio = duration / (slope * dt)
            growth = np.abs(method.cycle_amplification(rho, burst, slope, ratio))
            exact = np.abs(np.exp(rate * dt * (burst + ratio * slope)))
            cycles.append(
                dict(
                    jump_s=duration,
                    fast_max_growth=float(np.max(growth[fast], initial=0.0)),
                    slow_growth=growth[slow].tolist(),
                    slow_exact=exact[slow].tolist(),
                )
            )
        report["states"][name] = dict(
            rates_per_s=[[float(r.real), float(r.imag)] for r in rate[keep]],
            neutral_modes=int(np.count_nonzero(~keep)),
            cycles=cycles,
        )
    Path(output).mkdir(parents=True, exist_ok=True)
    (Path(output) / "spectrum.json").write_text(json.dumps(report, indent=1) + "\n")
    return report


def cycle_report(rho, rate, *, burst, slope, ratios, neutral_rate=1e-9):
    """Per jump ratio: the largest cycle growth over non-neutral modes and its mode."""
    keep = np.abs(rate) > neutral_rate
    rows = []
    for ratio in ratios:
        growth = np.abs(method.cycle_amplification(rho[keep], burst, slope, ratio))
        # Slow modes: compare with the exact decay over the cycle.
        k = int(np.argmax(growth))
        rows.append(
            dict(
                ratio=float(ratio),
                max_growth=float(growth[k]),
                max_growth_rate_per_s=complex(rate[keep][k]),
            )
        )
    return rows


if __name__ == "__main__":
    import argparse

    jax.config.update("jax_enable_x64", True)
    parser = argparse.ArgumentParser(description=heredity_modes.__doc__.splitlines()[0])
    parser.add_argument("output")
    parser.add_argument("--burst", type=int, default=2000)
    parser.add_argument("--slope", type=int, default=250)
    args = parser.parse_args()
    heredity_modes(args.output, burst=args.burst, slope=args.slope)
