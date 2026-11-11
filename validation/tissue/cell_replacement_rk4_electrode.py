"""Diagnosis: the RK4 electrode-ledger excess after a D<->H swap (development, not judged).

Question (lead, stage 2): is it a missing per-step rounding allowance or a booking error?

World: the seven-cell heredity sheet (D centre), RK4 at 2.5 us, held baths. At step 9
cell_0 (H) gets the D template and cell_3 (D) the H template, a charge displacement of
about 1e-12 C on each slot, booked by the event map (image charge into the electrode
field). Three trajectories from the same post-event state are compared, row by row,
on the electrode ledger residual r = electrode_transferred - cap_reservoir(q) at the
worst held node, and its bound:

  wrapper    resolved_pump_replacement@1's checked step (what failed)
  inner      resolved_pump_tissue@3's own checked step on the projected @3 state and
             the @3 layout: no wrapper code after the event
  reference  the same inner trajectory with cap_reservoir(q) evaluated in exact
             rational arithmetic, so r splits into the float64 evaluation error of the
             plate charge and the remainder (booking plus RK4 integration).

If inner reproduces wrapper, the excess is @3's RK4 electrode ledger at a large charge
displacement, not the wrapper's booking. If the exact-arithmetic residual stays at the booking
time's rounding while the float64 one fluctuates at kappa eps |q|, the excess is
rounding of the plate-charge evaluation (a missing allowance), not an error.

Usage: python -m validation.tissue.cell_replacement_rk4_electrode --output DIR
"""

import argparse
import json
import platform
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

jax.config.update("jax_enable_x64", True)

from cells.core.cell_replacement_spec import exact_event_times  # noqa: E402
from cells.core.specs import parse_spec  # noqa: E402
from cells.models import cell_replacement as model  # noqa: E402
from cells.models import surface_pump_v3 as ionic  # noqa: E402
from cells.models import surface_tissue as tissue  # noqa: E402
from validation.tissue import cell_replacement_fixtures as fx  # noqa: E402

DT = 2.5e-6
STEPS = 60
EVENT_STEP = 9


def exact_plate_charge(q, p):
    """cap = C S(q) at reservoir nodes in exact rational arithmetic (fractions).

    S is the field's capacitor solve: potentials of the non-fixed nodes from
    C_ff x = q_f with the fixed nodes (held baths, gauge) at zero; the inputs are
    the float64 values, so the only error left is the final rounding to float64.
    """
    layout = tissue.field_layout(p)
    fixed = np.asarray(layout.fixed)
    matrix = np.asarray(layout.capacitor_matrix)
    free = list(np.flatnonzero(~fixed))
    a = [[Fraction(float(matrix[i, j])) for j in free] for i in free]
    b = [Fraction(float(q[i])) for i in free]
    size = len(free)
    for c in range(size):  # Gaussian elimination, exact.
        pivot = next(r for r in range(c, size) if a[r][c] != 0)
        a[c], a[pivot], b[c], b[pivot] = a[pivot], a[c], b[pivot], b[c]
        for r in range(c + 1, size):
            f = a[r][c] / a[c][c]
            if f:
                a[r] = [x - f * y for x, y in zip(a[r], a[c], strict=True)]
                b[r] -= f * b[c]
    x = [Fraction(0)] * size
    for c in reversed(range(size)):
        x[c] = (b[c] - sum(a[c][k] * x[k] for k in range(c + 1, size))) / a[c][c]
    potential = [Fraction(0)] * len(q)
    for k, i in enumerate(free):
        potential[i] = x[k]
    n = p.active.size
    return np.asarray(
        [
            float(sum(Fraction(float(matrix[j, i])) * potential[i] for i in range(len(q))))
            for j in range(n, len(q))
        ]
    )


def residuals(rows, p, exact):
    n = p.active.size
    out = []
    for row in rows:
        q, cap, _ = tissue.capacitor_change(
            model.ionic_state(row), model.ionic_layout(p, xp=np), xp=np
        )
        e = np.asarray(row.electrode_charge_transferred_C)
        r64 = np.where(p.reservoir, e - cap[n:], 0.0)
        bound = 3e-25 + 2e-12 * np.abs(e)
        item = dict(
            residual_C=float(np.max(np.abs(r64))),
            ratio_to_bound=float(np.max(np.abs(r64) / bound)),
            max_abs_charge_increment_C=float(np.max(np.abs(q))),
        )
        if exact:
            r50 = np.where(p.reservoir, e - exact_plate_charge(q, p), 0.0)
            item["residual_exact_plate_charge_C"] = float(np.max(np.abs(r50)))
            item["plate_charge_float64_error_C"] = float(np.max(np.abs(r64 - r50)))
        out.append(item)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    raw = fx.heredity_sheet(1, 0, dt=DT, end_time=STEPS * DT, solver="rk4")
    raw["experiment"]["observation_times"] = [0.0, STEPS * DT]
    templates = [
        fx.template_from_cell(raw, "cell_1", "h"),
        fx.template_from_cell(raw, "cell_3", "d"),
    ]
    (t,) = exact_event_times((EVENT_STEP,), DT)
    events = [(t, "cell_0", "d", "n0"), (t, "cell_3", "h", "n1")]
    spec = parse_spec(fx.with_replacement(raw, templates, events))
    state, p = model.initial_values(spec)
    pj = jax.tree.map(jnp.asarray, p)
    step = jax.jit(lambda s, c, h: model.checked_step(s, h, c, pj, pj.active))
    inner_layout = model.ionic_layout(p, xp=np)
    inner_step = jax.jit(
        lambda s, c, h: ionic.checked_step(
            s, h, c, jax.tree.map(jnp.asarray, inner_layout), inner_layout.active
        )
    )
    controls = model.control_values(spec, [k * DT for k in range(STEPS)])
    s = jax.tree.map(jnp.asarray, state)
    for k in range(EVENT_STEP):
        s, ok = step(s, model.Control(*(jnp.asarray(v[k]) for v in controls)), DT)
        assert bool(ok)
    before = model.STATE_TYPE(*(np.asarray(v) for v in s))
    control = model.Control(*(np.asarray(v[EVENT_STEP]) for v in controls))
    after, ok = model.apply_events(before, control, p, xp=np)
    assert ok
    wrapper, inner = [after], [after]
    w, i_state = (
        jax.tree.map(jnp.asarray, after),
        jax.tree.map(jnp.asarray, model.ionic_state(after)),
    )
    for k in range(EVENT_STEP, STEPS):
        c = model.Control(*(jnp.asarray(v[k]) for v in controls))
        if k == EVENT_STEP:  # The wrapper step leaving t_e applies the event itself.
            w, ok = step(jax.tree.map(jnp.asarray, before), c, DT)
        else:
            w, ok = step(w, c, DT)
        assert bool(ok)
        wrapper.append(model.STATE_TYPE(*(np.asarray(v) for v in w)))
        i_state, ok = inner_step(i_state, model.ionic_control(c, after), DT)
        assert bool(ok)
        inner.append(
            after._replace(**{f: np.asarray(getattr(i_state, f)) for f in ionic.STATE_TYPE._fields})
        )
    out = dict(
        kind="cells.cell_replacement_rk4_electrode_diagnosis@1",
        dt_s=DT,
        event_step=EVENT_STEP,
        rows_after_event=STEPS - EVENT_STEP,
        electrode_bound="3e-25 C + 2e-12 |electrode| (surface_field.CHARGE_ATOL_C, CHARGE_RTOL)",
        before_event=residuals([before], p, exact=True)[0],
        wrapper=residuals(wrapper, p, exact=False),
        inner=residuals(inner, p, exact=True),
        inner_equals_wrapper_ionic_fields=all(
            all(
                np.array_equal(np.asarray(getattr(a, f)), np.asarray(getattr(b, f)))
                for f in ionic.STATE_TYPE._fields
            )
            for a, b in zip(wrapper[1:], inner[1:], strict=True)
        ),
        argv=sys.argv,
        host=platform.node(),
        revision=subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
        dirty=subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True
        ).stdout,
    )
    with open(args.output / "diagnosis.json", "x") as f:
        json.dump(out, f, indent=1)
    worst = lambda rows, k: max(r[k] for r in rows)  # noqa: E731
    print(
        json.dumps(
            dict(
                wrapper_max_ratio=worst(out["wrapper"], "ratio_to_bound"),
                inner_max_ratio=worst(out["inner"], "ratio_to_bound"),
                inner_max_residual_exact_plate_charge_C=worst(
                    out["inner"], "residual_exact_plate_charge_C"
                ),
                inner_max_plate_charge_float64_error_C=worst(
                    out["inner"], "plate_charge_float64_error_C"
                ),
                inner_equals_wrapper=out["inner_equals_wrapper_ionic_fields"],
            ),
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
