"""What the candidate's truncation may look like, by this runner's own arithmetic (no engine run).

    PYTHONPATH=SNAPSHOT/src:SNAPSHOT estimate2.py [WORLD ...]

The equations are the frozen snapshot's legacy right-hand sides. The scheme is this file's: Strang
halves of the reactions (RK4, so exact to this purpose) about the explicit part of ARS(2,2,2), the
fields solved at each stage. It is not the candidate's: there the faces' drift is implicit and the
channels' gates are exponential. So the numbers say which class an entry may have, and no more.

For every S entry at the first triple and the retry's: d2 and d1 over theta (`CRITERIA.md` section
4.3, with e_store), the measured order, and the class. `--stop` also prints the energy residual of
the stopped run's first steps over the flows so far (an explicit step's own quadrature).
"""

import json
import math
import sys
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

jax.config.update("jax_enable_x64", True)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import legacy_arrays2 as la  # noqa: E402
import make_inputs2 as m  # noqa: E402
import rules  # noqa: E402
import rules2  # noqa: E402

GAMMA = rules2.GAMMA
DELTA = 1 - 1 / (2 * GAMMA)


def setup(name, step):
    from cells.definitions.specs import parse_spec
    from cells.execution.schedule import control_values
    from cells.registry.models import get_model

    w = m.WORLDS[name]
    spec = parse_spec(m.legacy(w, step, observations=(0.0, w["end"])))
    model = get_model(spec.model)
    state, layout = model.initial_values(spec)
    control = control_values(spec, [0.0])
    control = type(control)(*(v[0] for v in control))
    return spec, model, state, layout, control


def scheme(name, step, n):
    """The rows after each step of the scheme, as a state of stacked arrays (row 0 the start)."""
    spec, model, state, layout, control = setup(name, step)
    from cells.legacy.models import er_calcium as er
    from cells.legacy.models import spatial_calcium as sp

    quiet = control._replace(er_reactions=jnp.zeros_like(control.er_reactions))
    stores = layout.er_initial_amount.shape[0]

    def add(y, *pairs):
        return jax.tree.map(lambda v, *ks: v + sum(a * k for a, k in zip(
            [p[0] for p in pairs], ks, strict=True)), y, *[p[1] for p in pairs])  # fmt: skip

    def react(y):
        """The reactions' right-hand side alone, on the chemical fields."""
        rates = []
        for i in range(stores):
            local = sp.store_layout(layout, i)
            rates.append(
                er.chemistry.rhs(
                    sp.store_state(y, i), sp.store_control(control, i).reactions, local,
                    local.active,
                )
            )  # fmt: skip
        zero = jax.tree.map(jnp.zeros_like, y)
        return zero._replace(
            chemical_amount_increment=jnp.stack([r.amount_increment for r in rates]),
            reaction_extent=jnp.stack([r.reaction_extent for r in rates]),
            reaction_dissipated_energy_pJ=jnp.stack([r.dissipated_energy_pJ for r in rates]),
        )

    def half(y, h):
        k1 = react(y)
        k2 = react(add(y, (h / 2, k1)))
        k3 = react(add(y, (h / 2, k2)))
        k4 = react(add(y, (h, k3)))
        return add(y, (h / 6, k1), (h / 3, k2), (h / 3, k3), (h / 6, k4))

    def transport(y):
        return model.rhs(y, quiet, layout, layout.active)

    def body(y, _):
        y = half(y, step / 2)
        k1 = transport(y)
        k2 = transport(add(y, (GAMMA * step, k1)))
        y = add(y, (DELTA * step, k1), ((1 - DELTA) * step, k2))
        y = half(y, step / 2)
        return y, y

    start = jax.tree.map(jnp.asarray, state)
    _, rows = jax.jit(lambda y: jax.lax.scan(body, y, None, length=n))(start)
    rows = jax.tree.map(
        lambda a, b: np.concatenate([np.asarray(a)[None], np.asarray(b)]), start, rows
    )
    return spec, model, layout, rows


def arrays_of(name, step):
    """The rows as the capture tool names a window's arrays, with the potentials."""
    w = m.WORLDS[name]
    n = rules.grid_steps(w["end"], step)
    spec, model, layout, rows = scheme(name, step, n)
    out = {"times": np.arange(n + 1) * step}
    out.update({f"history.{k}": getattr(rows, k) for k in rows._fields})
    times = out["times"]
    index = la.rows_at(times, w["potentials"], tolerance=1e-9)
    picked = type(rows)(*(v[index] for v in rows))
    p = type(layout)(*(np.asarray(v) for v in layout))
    from cells.legacy.models import er_calcium as er
    from cells.legacy.models import spatial_calcium as sp

    out["observations.times"] = np.array(w["potentials"])
    out["observations.plasma_voltage_V"] = model.cell_voltage(picked.amount_increment, p, xp=np)
    out["observations.er_voltage_V"] = np.stack(
        [
            er.voltage(sp.store_state(picked, i), sp.store_layout(p, i), xp=np)
            for i in range(p.er_initial_amount.shape[0])
        ],
        axis=-1,
    )
    out["observations.extracellular_potential_V"] = sp.spatial.field_values(
        picked, p, xp=np
    ).potential_V
    return out


def classify(d2, d1, theta, p=2.0):
    if d2 <= theta and d1 <= theta:
        return "unresolved"
    if d2 <= theta or d1 <= theta:
        return "mixed"
    q = math.log2(d2 / d1) if d1 > 0 else math.inf
    return "resolved" if p - 0.5 <= q <= 4.5 else "outside"


def world(name, inputs):
    w = m.WORLDS[name]
    b = inputs["worlds"][name]
    steps = [*w["candidate"], w["candidate"][-1] / 2]
    runs = [la.entries_of_windows(name, arrays_of(name, h)) for h in steps]
    out = {}
    for triple, (a, c, e) in (("first", runs[:3]), ("retry", runs[1:])):
        S = rules.grid_steps(w["end"], steps[2 if triple == "first" else 3])
        for k in e:
            if k not in b["scales"]:
                continue
            d2 = float(np.max(np.abs(c[k] - a[k]), initial=0.0))
            d1 = float(np.max(np.abs(e[k] - c[k]), initial=0.0))
            theta = 10 * (
                rules.e_round(S, b["scales"][k]) + rules.e_store(S, b["amount_refs"].get(k, 0.0))
            )
            out.setdefault(k, {})[triple] = (
                classify(d2, d1, theta), d2 / theta, d1 / theta,
                math.log2(d2 / d1) if d1 > 0 and d2 > 0 else float("nan"),
            )  # fmt: skip
    return out


def stop(name):
    """The energy residual of the scheme over the first accepted rows, beside the inner model's
    rule on the IMEX integrator: 2e-8 pJ plus 2e-3 of the heats and works so far (read in the
    snapshot's engine)."""
    step = m.WORLDS[name]["candidate"][0]
    spec, model, layout, rows = scheme(name, step, rules.grid_steps(m.WORLDS[name]["end"], step))
    p = type(layout)(*(np.asarray(v) for v in layout))
    residual = model.energy_balance(rows, p)
    heats = sum(
        np.abs(getattr(rows, k)).reshape(len(residual), -1).sum(1)
        for k in rows._fields
        if k.endswith("_dissipated_energy_pJ") or k in ("dissipated_energy_pJ",)
    )
    from cells.laws.reactions import plasma_calcium as lp
    from cells.legacy.models import er_calcium as er

    works = np.abs(1e-3 * p.pump_drive * rows.pump_cycles).sum(-1)
    drive = er.processes.chemical_drive(
        er.PumpParameters(*(getattr(p, f"er_pump_{k}")[0] for k in (
            "capacity", "km_ca", "km_atp", "atp", "adp", "pi", "dg0"))), 298.15, xp=np
    ) if hasattr(er, "PumpParameters") else er.processes.chemical_drive(
        er.pump_parameters(type("P", (), {f"pump_{k}": getattr(p, f"er_pump_{k}")[0] for k in (
            "capacity", "km_ca", "km_atp", "atp", "adp", "pi", "dg0")})), 298.15, xp=np
    )  # fmt: skip
    works = works + np.abs(1e-3 * drive * rows.er_pump_transferred).reshape(len(residual), -1).sum(
        1
    )
    q = p.pmca_dg
    plasma = lp.chemical_drive(
        lp.PumpParameters(p.pmca_capacity, p.pmca_km_ca, p.pmca_km_atp, p.pmca_atp, p.pmca_adp,
                          p.pmca_pi, q), 298.15, xp=np
    )  # fmt: skip
    works = works + np.abs(1e-3 * plasma * rows.plasma_pump_cycles).sum(-1)
    allowance = 2e-8 + 2e-3 * (heats + works)
    for i in (1, 2, 3, 4, 6, 8, 12, 20, 50):
        ratio = abs(residual[i]) / allowance[i]
        print(f"{name} row {i}: residual {residual[i]:.3e} pJ, flows {heats[i] + works[i]:.3e} pJ, "
              f"allowance {allowance[i]:.3e} pJ, ratio {ratio:.2f}")  # fmt: skip


def main(names):
    if names[:1] == ["--stop"]:
        for name in names[1:]:
            stop(name)
        return
    inputs = json.loads((m.HERE / "inputs_rehearsal_part2.json").read_text())
    for name in names or [w for w in m.WORLDS if len(m.WORLDS[w]["candidate"]) == 3]:
        rows = world(name, inputs)
        for triple in ("first", "retry"):
            count = {}
            for v in rows.values():
                count[v[triple][0]] = count.get(v[triple][0], 0) + 1
            print(f"{name} {triple}: {count}", flush=True)
        for k, v in rows.items():
            print(
                f"   {k:24s}"
                + "   ".join(
                    f"{t} {v[t][0]:10s} d2/theta {v[t][1]:9.2e} d1/theta {v[t][2]:9.2e} "
                    f"q {v[t][3]:5.2f}"
                    for t in ("first", "retry")
                ),
                flush=True,
            )


if __name__ == "__main__":
    main(sys.argv[1:])
