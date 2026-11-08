"""Scale, stiffness and step study of resolved_pump_tissue@1 at 825 nodes.

Parts (each writes <part>.json in --output):
  spectrum    Arnoldi spectra: the law's RHS (explicit RK4 limit); (G - I)/dt at
              10 us, whose leading modes are the fast ones the implicit part
              annihilates (mu ~ 0); and the step map's leading G - I modes
              against dt (explicit instability shows once |mu - 1| > 1).
  reference   explicit RK4 at 20 and 30 ns over short windows against both IMEX
              schemes under step refinement.
  refinement  INIT-like (0.256 s) and SIM-like (35 ms) refinement with observed
              orders, against a fine ARS(2,2,2) reference.
  freezing    frozen per-step face weights against per-stage Picard weights.
  cost        runner wall time per step, analysis time, Newton iterations and
              peak memory on the selected backend.
  stability   direct runs at 6-8 ms and the unstable explicit mode's localization.
The world is validation/tissue/resolved_scale_world.py (synthetic geometry,
BETSE default coefficients). Usage:
  python -m validation.tissue.resolved_scale_study PART --output DIR [--backend cpu|gpu]
"""

import argparse
import json
import resource
import time
import traceback
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

jax.config.update("jax_enable_x64", True)

from cells.core.runner import run  # noqa: E402
from cells.core.schedule import control_values  # noqa: E402
from cells.core.specs import parse_spec  # noqa: E402
from cells.models import surface_kinetic as kinetic  # noqa: E402
from cells.models import surface_pump as model  # noqa: E402
from cells.numerics import surface_imex as imex  # noqa: E402
from validation.tissue import resolved_scale_world as world  # noqa: E402

EULER, ARS = imex.EULER_ID, imex.ARS222_ID
RK4 = "rk4"


def setup(solver, backend="cpu", dt=1e-3, end_time=0.01):
    spec = parse_spec(world.definition(dt=dt, end_time=end_time, solver=solver, backend=backend))
    state, layout = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    device = jax.devices(backend)[0]
    control = type(controls)(*(v[0] for v in controls))
    return spec, *jax.device_put((state, layout, control), device)


@jax.jit
def _advance(state, layout, control, dt, steps):
    def body(_, carry):
        y, ok = carry
        updated, valid = model.checked_step(y, dt, control, layout, layout.active)
        return updated, ok & valid

    return jax.lax.fori_loop(0, steps, body, (state, jnp.asarray(True)))


def advance(state, layout, control, dt, steps):
    final, ok = _advance(state, layout, control, jnp.asarray(dt), jnp.asarray(steps))
    if not bool(ok):
        raise RuntimeError(f"Step refused within {steps} steps of {dt} s")
    return final


_law = jax.jit(kinetic.readouts)


def law(state, layout, control):
    values = _law(state, control, layout)
    if not bool(values.valid):
        raise RuntimeError("Law field invalid at a compared state")
    return values


def dynamic(layout):
    """Concrete masks of the dynamic coordinates: moving species and finite nodes."""
    moving = np.asarray(
        (np.asarray(layout.face_factor) > 0).any(axis=1)
        | (np.asarray(layout.membrane_permeability) > 0).any(axis=1)
    )
    finite = np.asarray(layout.outside_active) & ~np.asarray(layout.reservoir)
    return moving, finite


def pack(state, mask):
    moving, finite = mask
    return jnp.concatenate(
        (
            state.amount_increment[moving].ravel(),
            state.extracellular_amount_increment[moving][:, finite].ravel(),
            state.junction_gate,
        )
    )


def unpack(vector, state, mask):
    moving, finite = mask
    s, n, f = int(moving.sum()), state.amount_increment.shape[1], int(finite.sum())
    rows, columns = np.flatnonzero(moving), np.flatnonzero(finite)
    cell = vector[: s * n].reshape(s, n)
    out = vector[s * n : s * n + s * f].reshape(s, f)
    return state._replace(
        amount_increment=state.amount_increment.at[rows].set(cell),
        extracellular_amount_increment=state.extracellular_amount_increment.at[
            np.ix_(rows, columns)
        ].set(out),
        junction_gate=vector[s * n + s * f :],
    )


def law_jvp(mask):
    @jax.jit
    def apply(t, x0, state, control, layout):
        def f(v):
            y = unpack(v, state, mask)
            return pack(kinetic.rhs(y, control, layout, layout.active), mask)

        return jax.jvp(f, (x0,), (t,))[1]

    return apply


def step_jvp(mask):
    @jax.jit
    def apply(t, x0, state, control, layout, dt):
        def f(v):
            return pack(model.imex_step(unpack(v, state, mask), dt, control, layout)[0], mask)

        return jax.jvp(f, (x0,), (t,))[1]

    return apply


def arnoldi(apply, size, count=6, which="LM"):
    """Leading eigenpairs to 1e-5; non-converged runs keep the converged pairs."""
    from scipy.sparse.linalg import ArpackNoConvergence, LinearOperator, eigs

    calls = [0]

    def matvec(v):
        calls[0] += 1
        return np.asarray(apply(jnp.asarray(v)))

    operator = LinearOperator((size, size), matvec=matvec, dtype=float)
    try:
        values, vectors = eigs(operator, k=count, which=which, tol=1e-5, ncv=32, maxiter=30)
    except ArpackNoConvergence as error:
        values, vectors = error.eigenvalues, error.eigenvectors
    return values, vectors, calls[0]


def localization(vector, state, mask):
    """Share of an eigenvector's squared norm in cells, outside nodes and gates."""
    moving, finite = mask
    s, n, f = int(moving.sum()), state.amount_increment.shape[1], int(finite.sum())
    v = np.abs(vector) ** 2
    total = v.sum()
    species = [str(k) for k in np.flatnonzero(moving)]
    cell = v[: s * n].reshape(s, n).sum(axis=1)
    out = v[s * n : s * n + s * f].reshape(s, f).sum(axis=1)
    return dict(
        cells=float(cell.sum() / total),
        outside=float(out.sum() / total),
        gates=float(v[s * n + s * f :].sum() / total),
        cell_species=dict(zip(species, (cell / total).tolist(), strict=True)),
        outside_species=dict(zip(species, (out / total).tolist(), strict=True)),
    )


def part_spectrum(args):
    report = {}
    spec, state0, layout, control = setup(ARS, args.backend)
    report["gershgorin_explicit_rate_bound_per_s"] = float(model.explicit_rate_bound(spec))
    mask = dynamic(layout)
    law_apply, step_apply = law_jvp(mask), step_jvp(mask)
    layouts = {solver: setup(solver, args.backend)[2] for solver in (EULER, ARS)}
    evolved = advance(state0, layout, control, 1e-3, 50)
    labelled = (("t0", state0),) if args.quick else (("t0", state0), ("t50ms", evolved))
    for label, state in labelled:
        x0 = pack(state, mask)
        started = time.perf_counter()
        values, _, calls = arnoldi(
            lambda t, x0=x0, state=state: law_apply(t, x0, state, control, layout), x0.size
        )
        top = values[np.argsort(-np.abs(values))]
        report["law_rhs_" + label] = dict(
            eigenvalues_per_s=[[float(v.real), float(v.imag)] for v in top],
            rk4_real_axis_limit_s=float(2.785 / np.abs(top[0])),
            matvecs=calls,
            seconds=time.perf_counter() - started,
        )
        # (G - I)/dt at a small step: fast modes the implicit part annihilates.
        small = 1e-5
        values, vectors, calls = arnoldi(
            lambda t, x0=x0, state=state, h=small: (
                (step_apply(t, x0, state, control, layouts[EULER], h) - t) / h
            ),
            x0.size,
            count=8,
        )
        order = np.argsort(-np.abs(values))
        report[f"explicit_rates_{label}"] = dict(
            step_s=small,
            eigenvalues_per_s=[[float(values[i].real), float(values[i].imag)] for i in order],
            localization=[localization(vectors[:, i], state, mask) for i in order[:4]],
            euler_rk2_real_axis_limit_s=float(2.0 / np.abs(values[order[0]])),
            matvecs=calls,
        )
        if label != labelled[-1][0]:
            write(args, "spectrum", report)
            continue
        for solver in (EULER, ARS):
            radii = {}
            for dt in (1e-3, 4e-3) if args.quick else (1e-3, 4e-3, 8e-3):
                # Arnoldi on G - I: the most damped or unstable modes separate from
                # the slow cluster at mu = 1, whose members satisfy |mu| <= 1.
                values, _, calls = arnoldi(
                    lambda t, x0=x0, state=state, dt=dt, solver=solver: (
                        step_apply(t, x0, state, control, layouts[solver], dt) - t
                    ),
                    x0.size,
                    count=4,
                )
                radii[str(dt)] = dict(
                    max_abs_mu=float(np.max(np.abs(1.0 + values))),
                    mu_minus_one=[[float(v.real), float(v.imag)] for v in values],
                    matvecs=calls,
                )
            report[f"step_spectral_radius_{solver}_{label}"] = radii
        write(args, "spectrum", report)


def energy_relative(state, spec):
    """Energy-balance residual over the integrated work and dissipation flows."""
    _, p = kinetic.initial_values(spec)
    row = model.STATE_TYPE(*(np.asarray(v) for v in state))
    flows = sum(
        float(np.sum(np.abs(getattr(row, k))))
        for k in model.STATE_TYPE._fields
        if k.endswith(("_dissipated_energy_pJ", "_work_pJ"))
    )
    return float(abs(kinetic.balances(row, p)["energy"]) / max(flows, 1e-300))


def compare(a, b, layout, control):
    va, vb = law(a, layout, control), law(b, layout, control)
    vm = float(
        np.max(
            np.abs(
                np.asarray(va.field.rates.membrane_voltage_V - vb.field.rates.membrane_voltage_V)
            )
        )
    )
    result = dict(membrane_voltage_V=vm)
    for key in ("amount_increment", "extracellular_amount_increment", "junction_gate"):
        x, y = np.asarray(getattr(a, key)), np.asarray(getattr(b, key))
        result[key] = float(np.max(np.abs(x - y)) / max(np.max(np.abs(y)), 1e-300))
    return result


def part_reference(args):
    report = {}
    window = 2.4e-7 if args.quick else 2.4e-5
    _, start, rk4_layout, control = setup(RK4, args.backend)
    _, _, ars_layout, _ = setup(ARS, args.backend)
    starts = {"t0": start, "t100ms": advance(start, ars_layout, control, 1e-3, 100)}
    for label, origin in starts.items():
        entry = {}
        references = {}
        for dt in (2e-8, 3e-8):
            started = time.perf_counter()
            references[dt] = advance(origin, rk4_layout, control, dt, round(window / dt))
            entry[f"rk4_{dt}_seconds"] = time.perf_counter() - started
        entry["rk4_20ns_vs_30ns"] = compare(references[3e-8], references[2e-8], rk4_layout, control)
        change = law(references[2e-8], rk4_layout, control).field.rates.membrane_voltage_V
        entry["window_membrane_voltage_change_V"] = float(
            np.max(
                np.abs(
                    np.asarray(
                        change - law(origin, rk4_layout, control).field.rates.membrane_voltage_V
                    )
                )
            )
        )
        for solver in (EULER, ARS):
            _, _, layout, _ = setup(solver, args.backend)
            rows = []
            for k in (1, 2) if args.quick else (1, 2, 4, 8, 16, 32):
                final = advance(origin, layout, control, window / k, k)
                rows.append(
                    dict(dt_s=window / k, **compare(final, references[2e-8], layout, control))
                )
            entry[solver] = rows
        report[label] = entry
        write(args, "reference", report)


def orders(errors):
    return [
        float(np.log2(a / b)) if a > 0 and b > 0 else None
        for a, b in zip(errors, errors[1:], strict=False)
    ]


def part_refinement(args):
    report = {}
    _, start, ars_layout, control = setup(ARS, args.backend)
    horizon = 0.016 if args.quick else 0.256  # Integer steps at every compared dt.
    reference_dt = 6.25e-5
    started = time.perf_counter()
    reference = advance(start, ars_layout, control, reference_dt, round(horizon / reference_dt))
    report["init_reference"] = dict(dt_s=reference_dt, seconds=time.perf_counter() - started)
    vm = law(reference, ars_layout, control).field.rates.membrane_voltage_V
    report["init_reference"]["membrane_voltage_mean_V"] = float(np.mean(np.asarray(vm)))
    for solver in (EULER, ARS):
        spec, _, layout, _ = setup(solver, args.backend)
        rows = []
        for dt in (4e-3, 2e-3, 1e-3, 5e-4, 2.5e-4):
            started = time.perf_counter()
            final = advance(start, layout, control, dt, round(horizon / dt))
            rows.append(
                dict(
                    dt_s=dt,
                    seconds=time.perf_counter() - started,
                    **compare(final, reference, layout, control),
                    energy_relative=energy_relative(final, spec),
                )
            )
        report["init_" + solver] = dict(
            rows=rows, membrane_voltage_orders=orders([r["membrane_voltage_V"] for r in rows])
        )
        write(args, "refinement", report)
    window, sim_reference_dt = (0.0004, 1.25e-5) if args.quick else (0.035, 1.25e-5)
    sim_reference = advance(
        reference, ars_layout, control, sim_reference_dt, round(window / sim_reference_dt)
    )
    for solver in (EULER, ARS):
        _, _, layout, _ = setup(solver, args.backend)
        rows = []
        for dt in (1e-4, 5e-5, 2.5e-5):
            final = advance(reference, layout, control, dt, round(window / dt))
            rows.append(dict(dt_s=dt, **compare(final, sim_reference, layout, control)))
        report["sim_" + solver] = dict(
            rows=rows, membrane_voltage_orders=orders([r["membrane_voltage_V"] for r in rows])
        )
    write(args, "refinement", report)


def picard_step(state, dt, control, p, sweeps=3):
    """ARS(2,2,2) with stage-exact face weights: refactor until W is consistent."""
    f, s = model.tissue.field_layout(p), model.tissue.field_layout(p).surface
    a, b = p.imex_explicit, p.imex_implicit
    first = kinetic.readouts(state, control, p)
    rates, _ = model.explicit_rates(state, first.field.potential_V, control, p)
    explicit, implicit = [rates], [None]
    stage = state
    for i in range(1, a.shape[0]):
        known = model._combine(
            state,
            dt,
            [(a[i, j], explicit[j]) for j in range(i)]
            + [(b[i, j], implicit[j]) for j in range(1, i)],
        )
        charge = model.node_charge(known, p)
        guess = known
        for _ in range(sweeps):
            co = (
                p.extracellular_amount_reference + guess.extracellular_amount_increment
            ) / p.extracellular_volume
            weight, _ = imex.face_weights(jnp.where(p.outside_active, co, 1.0), s)
            operator, _ = imex.factor_operator(
                b[i, i] * dt, imex.face_laplacian(weight, s), p.boundary_V, f
            )
            potential, _ = imex.solve_operator(charge, operator)
            drift = model.implicit_rates(weight, potential, state, p)
            guess = model._combine(known, dt, [(b[i, i], drift)])
        implicit.append(drift)
        stage = guess
        if i < a.shape[0] - 1:
            rates, _ = model.explicit_rates(stage, potential, control, p)
            explicit.append(rates)
    return stage


def part_freezing(args):
    report = {}
    _, start, layout, control = setup(ARS, args.backend)
    picard = jax.jit(picard_step)
    for dt, steps in ((1e-3, 2),) if args.quick else ((1e-3, 50), (5e-4, 100)):
        frozen = advance(start, layout, control, dt, steps)
        exact = start
        for _ in range(steps):
            exact = picard(exact, dt, control, layout)
        report[str(dt)] = compare(frozen, exact, layout, control)
        write(args, "freezing", report)


def part_cost(args):
    report = {}
    device = jax.devices(args.backend)[0]
    for solver in (ARS, EULER):
        for dt, end in (
            ((1e-3, 0.004), (1e-4, 0.0004)) if args.quick else ((1e-3, 0.2), (1e-4, 0.02))
        ):
            spec = parse_spec(
                world.definition(
                    dt=dt,
                    end_time=end,
                    solver=solver,
                    backend=args.backend,
                    observation_times=[0.0, end],
                )
            )
            if args.backend == "gpu":
                device.memory_stats()  # Ensure the allocator is initialized.
            value = run(spec)
            steps = len(value.times) - 1
            layout = jax.device_put(value.final.layout, device)
            controls = control_values(spec, [0.0])
            control = jax.device_put(type(controls)(*(v[0] for v in controls)), device)
            iterations, normalized = [], []
            for i in range(0, steps + 1, max(1, steps // 20)):
                state = jax.device_put(model.STATE_TYPE(*(v[i] for v in value.history)), device)
                w = law(state, layout, control)
                iterations.append(int(w.field.iterations))
                normalized.append(float(w.field.current_normalized))
            entry = dict(
                steps=steps,
                timings=value.timings,
                execute_ms_per_step=1e3 * value.timings["execute_seconds"] / steps,
                analysis_ms_per_row=1e3 * value.timings["analysis_seconds"] / (steps + 1),
                newton_iterations=dict(
                    min=min(iterations), max=max(iterations), mean=float(np.mean(iterations))
                ),
                max_current_normalized=max(normalized),
                diagnostics=value.diagnostics,
                peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
            )
            if args.backend == "gpu":
                entry["gpu_peak_bytes"] = device.memory_stats().get("peak_bytes_in_use")
            per_step = entry["execute_ms_per_step"] + entry["analysis_ms_per_row"]
            entry["extrapolated_seconds"] = (
                dict(init_5s=5.0 / dt * per_step / 1e3)
                if dt == 1e-3
                else dict(sim_35ms=0.035 / dt * per_step / 1e3)
            )
            report[f"{solver}@{dt}"] = entry
            write(args, "cost", report)
            np.savez_compressed(
                Path(args.output) / f"cost-final-{args.backend}-{solver.split('@')[0]}-{dt}.npz",
                **{k: np.asarray(v) for k, v in value.final.state._asdict().items()},
            )


def part_stability(args):
    """Direct runs at 6, 7 and 8 ms, and the unstable Euler mode's localization."""
    report = {}
    _, start, _, control = setup(ARS, args.backend)
    for solver in (EULER, ARS):
        _, _, layout, _ = setup(solver, args.backend)
        rows = {}
        for dt in (6e-3, 7e-3, 8e-3):
            steps = int(round(0.256 / dt))
            try:
                final = advance(start, layout, control, dt, steps)
                vm = np.asarray(law(final, layout, control).field.rates.membrane_voltage_V)
                rows[str(dt)] = dict(steps=steps, status="accepted", vm_mean_V=float(vm.mean()))
            except RuntimeError as error:
                rows[str(dt)] = dict(steps=steps, status="refused", error=str(error))
        report[solver] = rows
        write(args, "stability", report)
    _, _, layout, _ = setup(EULER, args.backend)
    evolved = advance(start, layout, control, 1e-3, 50)
    mask = dynamic(layout)
    apply, x0 = step_jvp(mask), pack(evolved, mask)
    values, vectors, calls = arnoldi(
        lambda t: apply(t, x0, evolved, control, layout, 8e-3) - t, x0.size, count=4
    )
    order = np.argsort(-np.abs(values))
    report["euler_8ms_unstable_modes"] = dict(
        mu=[[float(1 + values[i].real), float(values[i].imag)] for i in order],
        rate_per_s=[float(values[i].real / 8e-3) for i in order],
        localization=[localization(vectors[:, i], evolved, mask) for i in order[:2]],
        matvecs=calls,
    )
    write(args, "stability", report)


def write(args, name, report):
    path = Path(args.output) / f"{name}-{args.backend}.json"
    path.write_text(json.dumps(report, indent=2, default=float) + "\n")


PARTS = dict(
    spectrum=part_spectrum,
    reference=part_reference,
    refinement=part_refinement,
    freezing=part_freezing,
    cost=part_cost,
    stability=part_stability,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("parts", nargs="+", choices=sorted(PARTS))
    parser.add_argument("--output", required=True)
    parser.add_argument("--backend", choices=("cpu", "gpu"), default="cpu")
    parser.add_argument("--quick", action="store_true", help="tiny windows to smoke-test parts")
    args = parser.parse_args()
    Path(args.output).mkdir(parents=True, exist_ok=True)
    status = {}
    for name in args.parts:
        started = time.perf_counter()
        try:
            PARTS[name](args)
            status[name] = dict(status="completed", seconds=time.perf_counter() - started)
        except Exception as error:  # Preserve the failure and continue with other parts.
            status[name] = dict(
                status="failed",
                seconds=time.perf_counter() - started,
                error=repr(error),
                traceback=traceback.format_exc(),
            )
        print(json.dumps({name: status[name]["status"]}), flush=True)
        if status[name]["status"] == "failed":
            print(status[name]["traceback"], flush=True)
    outcome = "failure" if any(v["status"] == "failed" for v in status.values()) else "result"
    summary = dict(
        parts=status,
        backend=args.backend,
        peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    )
    (Path(args.output) / f"{outcome}-{args.backend}.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
