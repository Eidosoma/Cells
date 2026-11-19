"""FR-18 probe harness (scratch; CRITERION-20261118.md, with its amendment 1). No engine code.

Replays one world's accepted steps through the engine's own step function (model.checked_step)
in compiled scans of CHUNK steps (each step taken whole and as two half steps, with the step's
held control, from the same accepted state), and evaluates at every accepted row the engine's own
host ledger path (the functions checked_rows reads): R_k (the energy ledger), F_k (its flows) and
today's bound. Per step:
- E2: eps2_k = 4/3 |r_k - r''_k|, r'' from the two half steps (none at an operator event step,
  amendment 1: eps2_k = 0 there, listed);
- E1 (@3 alone): sum over @3's heat and work accumulators of |dT_f - dt/2 (q_f(x_k) +
  q_f(x_k+1))|, q_f from readouts at each accepted row (the step's held control at both ends).
The candidate is A_k = ENERGY_ATOL_PJ + 16 eps F_k + c sum_(j<k) eps_j, c in (1, 2, 4), c = 2
decided. Plants (edits of the honest row at each step's end, never fed back): P1 every work
accumulator x (1 + 1e-6); P2 the heat accumulators x (1 + 1e-6) and the work x (1 + 1e-4); on
q1_eps_1e-1 also FR-3's registered plant (site_work_pJ[r0] x (1 + 1e-6) at its 1 s row).

Usage (cwd = a clean snapshot root, PYTHONPATH=src:.):
  python -B harness.py OUT_JSON WORLD_KIND WORLD_ARG [MAX_STEPS]
WORLD_KIND: g1 PATH_TO_SAVED_JSON | fr18 ARM:FACTOR | acceptance NAME | fr3plant -
"""

import json

import sys
import time
import traceback

import jax
import jax.numpy as jnp
import numpy as np

jax.config.update("jax_enable_x64", True)

from cells.definitions.specs import parse_spec  # noqa: E402
from cells.execution.runner import integration_steps, timeline  # noqa: E402
from cells.execution.schedule import control_values  # noqa: E402
from cells.execution.state import initialise  # noqa: E402
from cells.models import surface_tissue as tissue  # noqa: E402
from cells.registry.models import get_model  # noqa: E402

EPS = float(np.finfo(float).eps)
CS = (1.0, 2.0, 4.0)
DECIDED_C = 2.0
CHUNK = 4096
ESTIMATORS = ("eps2", "eps1")
PLANTS = (
    ("P1 work x (1 + 1e-6)", "work", 1e-6),
    ("P2 heat x (1 + 1e-6)", "heat", 1e-6),
    ("P2 work x (1 + 1e-4)", "work", 1e-4),
)


# ------------------------------------------------------------------ worlds


def acceptance(name):
    """The judged worlds at their registered horizons, by their protocols' own generators."""
    from validation.tissue import a5pp_acceptance_fixtures as a5pp
    from validation.tissue import bath_schedule_fixtures as bath
    from validation.tissue import compartment_acceptance_fixtures as compartment
    from validation.tissue import site_occupancy_acceptance_fixtures as occupancy

    return {
        "fr1_load_and_degrade": compartment.load_and_degrade,
        "fr1_load_and_react": compartment.load_and_react,
        "fr3_q5_inward": lambda: occupancy.registered_world("q5_inward"),
        "fr3_q5_class_switch": lambda: occupancy.registered_world("q5_class_switch"),
        "fr10_ion": bath.ion_world,
        "fr10_ledger": bath.ledger_world,
        "fr6_a5pp": a5pp.registered_world,
    }[name]()


def world(kind, arg):
    """(raw definition, label, registered plant or None)."""
    if kind == "g1":
        saved = json.loads(open(arg).read())
        return saved["definition"], saved["name"], None
    if kind == "fr18":
        from validation.gap_junction_tissue import worlds

        arm, factor = arg.split(":")
        build = {
            "fig5net100": lambda: worlds.figure5_network(100.0),
            "fig3g50": lambda: worlds.figure3(50.0),
        }[arm]
        network = build()
        cells, edges, probes = network.cells, network.edges, network.probes
        rate = worlds.explicit_rate(cells, edges, probes)
        dt = worlds.BASE_DT_S / float(factor)  # The base step halved: END_S stays exact.
        raw = worlds.linear_network(cells, edges, probes, dt=dt)
        return raw, f"{arm} dt x rate {dt * rate:.4g}", None
    if kind == "acceptance":
        return acceptance(arg), arg, None
    if kind == "fr3plant":
        from validation.tissue import site_occupancy_acceptance_fixtures as af
        from validation.tissue import site_occupancy_acceptance_plants as plants

        raw = plants.every_step(af.registered_world(plants.MIXED), plants.PLANT_AT_S + 10 * 1e-3)
        plant = dict(field="site_work_pJ", population="r0", at_s=plants.PLANT_AT_S)
        return raw, plants.MIXED, plant
    raise SystemExit(f"unknown world kind {kind}")


# ------------------------------------------------------------------ the engine's ledger path


class Ledger:
    """The energy ledger, its flows and its bound at one row, as checked_rows evaluates them."""

    def __init__(self, spec, model, layout):
        if hasattr(model, "composition") and hasattr(model, "module"):  # A frozen family.
            spec, model = model.module.composite(spec), model.composition
        self.spec, self.model, self.p = spec, model, layout
        self.composite = hasattr(model, "inner_balances")
        self.rtol = model.ENERGY_RTOL[spec.execution.solver]
        self.tol = np.asarray(spec.execution.material_balance_atol_fmol)
        self.ledgers = model.inner if self.composite else model
        self.retiring = bool(model._live_retiring(layout)) if self.composite else False
        self.index = self.ledgers.LEDGERS.index("energy")

    def __call__(self, row, steps):
        model, p = self.model, self.p
        with np.errstate(all="ignore"):
            if self.composite:
                if self.retiring:
                    row = model._adjusted(row, p, xp=np)
                    b = model.inner_balances(row, p, adjust=False)
                    m = model.inner_magnitudes(row, p, xp=np, adjust=False)
                else:
                    b, m = model.inner_balances(row, p), model.inner_magnitudes(row, p, xp=np)
            else:
                b, m = model.balances(row, p), model.channel_magnitudes(row, p, xp=np)
            flows, bounds = self.ledgers.ledger_limits(
                row, p, self.tol, self.rtol, steps=steps, magnitudes=m
            )
        return float(np.asarray(b["energy"])), float(flows), float(np.asarray(bounds[self.index]))


def fields_of(row, role):
    suffix = "_work_pJ" if role == "work" else "_dissipated_energy_pJ"
    return [k for k in type(row)._fields if k.endswith(suffix)]


def scaled(row, names, factor):
    return row._replace(**{k: np.asarray(getattr(row, k)) * factor for k in names})


def event_steps(spec, times):
    """Amendment 1: the step indices that start where an operator's record changes."""
    marks, previous = set(), None
    for change in getattr(spec.experiment, "changes", ()):
        operators = getattr(change, "operators", None)
        if operators is not None and previous is not None and operators != previous:
            marks.add(float(change.time))
        previous = operators
    return {k for k, t in enumerate(times[:-1]) if float(t) in marks}


def registered_edit(spec, plant):
    from validation.tissue import site_occupancy_acceptance_plants as plants

    _, _, k = plants._indices(spec, plant["population"])  # Its work() edit's own index.

    def edit(x):
        values = np.asarray(getattr(x, plant["field"])).copy()
        values[k] = values[k] * (1.0 + plants.WORK_RELATIVE)
        return x._replace(**{plant["field"]: values})

    return edit


# ------------------------------------------------------------------ the replay


class Tally:
    """Running sums and extrema of the candidate and the plants over the rows (streamed)."""

    def __init__(self, estimators):
        self.estimators = estimators
        self.totals = dict.fromkeys(estimators, 0.0)
        self.honest = {(e, c): [0.0, None] for e in estimators for c in CS}
        self.plants = {}
        self.today = [0.0, None]

    def allowance(self, estimator, c, flows):
        return tissue.ENERGY_ATOL_PJ + 16 * EPS * flows + c * self.totals[estimator]

    def row(self, k, energy, flows, bound, eps, planted):
        ratio = abs(energy) / bound
        if ratio > self.today[0]:
            self.today[0] = ratio
        if ratio > 1 and self.today[1] is None:
            self.today[1] = k
        for e in self.estimators:
            if eps.get(e) is not None:
                self.totals[e] += eps[e]
        for e in self.estimators:
            for c in CS:
                cell = self.honest[(e, c)]
                r = abs(energy) / self.allowance(e, c, flows)
                cell[0] = max(cell[0], r)
                if r > 1 and cell[1] is None:
                    cell[1] = k
        for label, (planted_energy, planted_flows, planted_bound) in planted.items():
            cell = self.plants.setdefault(label, dict(today=None, worst_today=0.0))
            today = abs(planted_energy) / planted_bound
            cell["worst_today"] = max(cell["worst_today"], today)
            if today > 1 and cell["today"] is None:
                cell["today"] = k
            for e in self.estimators:
                for c in CS:
                    key = f"{e} c={c:g}"
                    r = abs(planted_energy) / self.allowance(e, c, planted_flows)
                    slot = cell.setdefault(key, dict(caught_at_step=None, largest_ratio=0.0))
                    slot["largest_ratio"] = max(slot["largest_ratio"], r)
                    if r > 1 and slot["caught_at_step"] is None:
                        slot["caught_at_step"] = k

    def summary(self):
        out = dict(today_max_ratio=self.today[0], today_first_refused_step=self.today[1])
        for e in self.estimators:
            out[e] = {
                f"c={c:g}": dict(
                    honest_max_ratio=self.honest[(e, c)][0],
                    first_refused_step=self.honest[(e, c)][1],
                )
                for c in CS
            }
            out[e]["sum_eps"] = self.totals[e]
        out["plants"] = self.plants
        return out


class DeviceLedger:
    """The ledger's (energy, flows, bound) on the device, vmapped over a chunk's rows: @3 alone
    (its device_balances and channel_magnitudes, the device checks' own functions, with
    ledger_limits at xp = jax.numpy). Equal to the host path to rounding."""

    def __init__(self, spec, model, layout):
        self.p = jax.tree.map(jnp.asarray, layout)
        rtol = model.ENERGY_RTOL[spec.execution.solver]
        tol = jnp.asarray(spec.execution.material_balance_atol_fmol)
        index = model.LEDGERS.index("energy")

        def one(row, k):
            b = model.device_balances(row, self.p)
            m = model.channel_magnitudes(row, self.p, xp=jnp)
            flows, bounds = model.ledger_limits(row, self.p, tol, rtol, steps=k, magnitudes=m, xp=jnp)
            return b["energy"], flows, bounds[index]

        self.vmapped = jax.jit(jax.vmap(one))

    def __call__(self, rows, ks):
        out = self.vmapped(rows, jnp.asarray(ks))
        return tuple(np.asarray(v, dtype=float) for v in out)


def scaled_rows(rows, names, factor):
    return rows._replace(**{k: getattr(rows, k) * factor for k in names})


def replay_alone(spec, model, times, checkpoint, steps, controls, scan, plant):
    """replay for @3 alone, every evaluation vectorized over each chunk's rows."""
    p = checkpoint.layout
    params = model.parameters(spec, p)
    ledger = DeviceLedger(spec, model, p)
    derivative = jax.jit(jax.vmap(lambda y, c: model.readouts(y, c, params).derivative))
    tally = Tally(ESTIMATORS)
    n = len(steps)
    heat, work = fields_of(checkpoint.state, "heat"), fields_of(checkpoint.state, "work")
    x = checkpoint.state
    r0 = ledger(jax.tree.map(lambda v: jnp.asarray(v)[None], x), [0])[0][0]
    refusal, unavailable, accepted_steps = None, [], 0
    for start in range(0, n, CHUNK):
        stop = min(n, start + CHUNK)
        cc = jax.tree.map(lambda v, a=start, b=stop: v[a:b], controls)
        _, (ends, halves, accepted, halved) = scan(x, jnp.asarray(steps[start:stop]), cc)
        accepted, halved = np.asarray(accepted), np.asarray(halved)
        m = stop - start
        if not accepted.all():
            m = int(np.flatnonzero(~accepted)[0])
            refusal = dict(refused_at=start + m, time=float(times[start + m]), by="the step's validity")
        if m == 0:
            break
        ends = jax.tree.map(lambda v, m=m: v[:m], ends)
        halves = jax.tree.map(lambda v, m=m: v[:m], halves)
        cc = jax.tree.map(lambda v, m=m: v[:m], cc)
        starts = jax.tree.map(
            lambda a, b: jnp.concatenate((jnp.asarray(a)[None], b[:-1]), axis=0), x, ends
        )
        ks = np.arange(start + 1, start + m + 1)
        e1, f1, b1 = ledger(ends, ks)
        eh = ledger(halves, ks)[0]
        e0 = np.concatenate(([r0], e1[:-1]))
        eps2 = 4.0 / 3.0 * np.abs((e1 - e0) - (eh - e0))
        eps2 = np.where(halved[:m], eps2, np.nan)
        unavailable += [start + j for j in np.flatnonzero(~halved[:m])][:50]
        q0, q1 = derivative(starts, cc), derivative(ends, cc)
        dts = np.asarray(steps[start : start + m])
        eps1 = np.zeros(m)
        for name in (*heat, *work):
            booked = np.asarray(getattr(ends, name)) - np.asarray(getattr(starts, name))
            trap = 0.5 * dts.reshape((-1,) + (1,) * (booked.ndim - 1)) * (
                np.asarray(getattr(q0, name)) + np.asarray(getattr(q1, name))
            )
            eps1 += np.abs(booked - trap).reshape(m, -1).sum(axis=1)
        planted = {}
        for label, role, size in PLANTS:
            names = work if role == "work" else heat
            planted[label] = ledger(scaled_rows(ends, names, 1 + size), ks)
        for j in range(m):
            k = start + j
            eps = dict(eps2=None if np.isnan(eps2[j]) else float(eps2[j]), eps1=float(eps1[j]))
            rows = {label: (v[0][j], v[1][j], v[2][j]) for label, v in planted.items()}
            tally.row(k, e1[j], f1[j], b1[j], eps, rows)
        accepted_steps = start + m
        x = jax.tree.map(lambda v: np.asarray(v)[m - 1], ends)
        r0 = e1[m - 1]
        if refusal is not None:
            break
    return spec, tally, dict(
        steps=accepted_steps,
        planned_steps=n,
        refusal=refusal,
        events=[],
        eps2_unavailable=unavailable[:50],
        estimators=list(ESTIMATORS),
        path="device, vectorized",
    )


def replay(raw, max_steps, plant):
    spec = parse_spec(raw)
    model = get_model(spec.model)
    times = timeline(spec)
    checkpoint = initialise(spec)
    steps = np.asarray(integration_steps(spec, times))[:max_steps]
    n = len(steps)
    controls = jax.tree.map(lambda v: np.asarray(v)[:n], control_values(spec, times[:-1]))
    p = checkpoint.layout
    params = model.parameters(spec, p)
    active = p.active

    def advance(carry, inputs):
        x, alive = carry
        dt, c = inputs
        x1, ok1 = model.checked_step(x, dt, c, params, active)
        h1, okh1 = model.checked_step(x, 0.5 * dt, c, params, active)
        h2, okh2 = model.checked_step(h1, 0.5 * dt, c, params, active)
        go = alive & ok1
        nxt = jax.tree.map(lambda a, b: jnp.where(go, a, b), x1, x)
        return (nxt, go), (x1, h2, go, okh1 & okh2)

    scan = jax.jit(lambda x0, s, c: jax.lax.scan(advance, (x0, jnp.asarray(True)), (s, c)))
    alone = not hasattr(model, "inner_balances") and not hasattr(model, "composition")
    if alone and plant is None:
        return replay_alone(spec, model, times, checkpoint, steps, controls, scan, plant)
    ledger = Ledger(spec, model, p)
    family = hasattr(model, "composition") and hasattr(model, "module")
    events = event_steps(model.module.composite(spec) if family else spec, times)
    derivative = jax.jit(lambda y, c: model.readouts(y, c, params).derivative) if alone else None
    estimators = ESTIMATORS if alone else ("eps2",)
    tally = Tally(estimators)
    kind = type(checkpoint.state)
    edits = {
        label: (lambda x, role=role, size=size: scaled(x, fields_of(x, role), 1 + size))
        for label, role, size in PLANTS
    }
    registered = None
    if plant is not None:
        registered = (registered_edit(spec, plant), plant["at_s"])
    x, r0 = checkpoint.state, ledger(checkpoint.state, 0)
    q0 = None
    refusal, listed, unavailable, accepted_steps = None, [], [], 0
    for start in range(0, n, CHUNK):
        stop = min(n, start + CHUNK)
        chunk_controls = jax.tree.map(lambda v, a=start, b=stop: v[a:b], controls)
        _, (ends, halves, accepted, halved) = scan(x, jnp.asarray(steps[start:stop]), chunk_controls)
        ends, halves = jax.tree.map(np.asarray, ends), jax.tree.map(np.asarray, halves)
        accepted, halved = np.asarray(accepted), np.asarray(halved)
        for j in range(stop - start):
            k = start + j
            if not accepted[j]:
                refusal = dict(refused_at=k, time=float(times[k]), by="the step's validity")
                break
            c = jax.tree.map(lambda v, j=j: v[j], chunk_controls)
            dt = float(steps[k])
            x1 = kind(*(v[j] for v in ends))
            r1 = ledger(x1, k + 1)
            eps = {}
            if k in events:
                eps["eps2"] = 0.0
                listed.append(k)
            elif halved[j]:
                rh = ledger(kind(*(v[j] for v in halves)), k + 1)[0] - r0[0]
                eps["eps2"] = 4.0 / 3.0 * abs((r1[0] - r0[0]) - rh)
            else:
                eps["eps2"] = None
                unavailable.append(k)
            if alone:
                if q0 is None:
                    q0 = derivative(x, c)
                q1 = derivative(x1, c)
                total = 0.0
                for name in (*fields_of(x1, "heat"), *fields_of(x1, "work")):
                    booked = np.asarray(getattr(x1, name)) - np.asarray(getattr(x, name))
                    trapezoid = 0.5 * dt * (np.asarray(getattr(q0, name)) + np.asarray(getattr(q1, name)))
                    total += float(np.sum(np.abs(booked - trapezoid)))
                eps["eps1"] = total
                q0 = None  # The next step's start rate is taken at its own held control.
            planted = {label: ledger(edit(x1), k + 1) for label, edit in edits.items()}
            if registered is not None and abs(times[k] + dt - registered[1]) < 1e-12:
                planted["FR-3 registered: site_work_pJ[r0] x (1 + 1e-6) at 1 s"] = ledger(
                    registered[0](x1), k + 1
                )
            tally.row(k, r1[0], r1[1], r1[2], eps, planted)
            accepted_steps = k + 1
            x, r0 = x1, r1
        if refusal is not None:
            break
    return spec, tally, dict(
        steps=accepted_steps,
        planned_steps=n,
        refusal=refusal,
        events=listed[:50],
        eps2_unavailable=unavailable[:50],
        estimators=list(estimators),
    )


class _Excluded(Exception):
    pass


def main(argv):
    out_path, kind, arg = argv[1], argv[2], argv[3]
    max_steps = int(argv[4]) if len(argv) > 4 else 2000
    started = time.perf_counter()
    record = dict(kind=kind, arg=arg, max_steps=max_steps)
    try:
        raw, label, plant = world(kind, arg)
        record["label"] = label
        solver = raw.get("execution", {}).get("solver")
        if solver == "rk4":  # Out of scope (the criterion): rtol is 0 there, an absolute bound.
            record.update(excluded="RK4: its energy bound is absolute (rtol 0)", solver=solver)
            raise _Excluded
        spec, tally, facts = replay(raw, max_steps, plant)
        record["solver"] = spec.execution.solver
        record["model"] = type(spec.model).__name__
        record.update(facts)
        record.update(tally.summary())
    except _Excluded:
        pass
    except Exception as error:  # noqa: BLE001
        record["error"] = repr(error)
        record["where"] = traceback.format_exc()[-1500:]
    record["seconds"] = time.perf_counter() - started
    with open(out_path, "w") as handle:
        json.dump(record, handle, indent=1, default=float)
    print(json.dumps({k: record.get(k) for k in ("label", "steps", "seconds", "error")}), flush=True)


if __name__ == "__main__":
    main(sys.argv)
