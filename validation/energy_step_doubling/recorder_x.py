"""FR-18 criterion X's registered run: the recorder (docs/FR18_CRITERION_X_2026-11-18.md).

Replays one world's accepted steps exactly as the probe's harness does, using
../fr18-probe/harness.py unchanged for its worlds, ledger paths and plants. Each step is taken whole
and as two half steps from the same accepted state, with the step's held control. Every row's signed
values are recorded for evaluate_x.py:
- R, F, B: the honest ledger, its flows and today's bound;
- d_full and d_half: signed, with NaN at a held step (an operator's event step, amendment 1, or
  halves refused by the step's validity);
- the magnitude M = F + T + O, with T and O kept apart: T the tissue ledger's stored terms as
  absolute values element by element, O the model's own energy magnitude where reported plus the
  declared kinds' |stored_pJ|;
- each plant's signed contribution delta and its row's flows, and FR-3's registered plant at its
  row.
No engine code: everything is read through the engine's own functions.

Usage (cwd = the run's clean snapshot root, PYTHONPATH=src:.:<the probe's directory>):
  python -B recorder_x.py OUT_NPZ WORLD_KIND WORLD_ARG [MAX_STEPS]
"""

import json
import sys
import time
import traceback

import jax
import jax.numpy as jnp
import numpy as np

import harness as H  # The probe's harness, unchanged (its digest is in tools.sha256).

jax.config.update("jax_enable_x64", True)

from cells.definitions.specs import parse_spec  # noqa: E402
from cells.execution.runner import integration_steps, timeline  # noqa: E402
from cells.execution.schedule import control_values  # noqa: E402
from cells.execution.state import initialise  # noqa: E402
from cells.laws.electrochemistry import R as GAS_R  # noqa: E402
from cells.models import surface_pump_v3  # noqa: E402
from cells.models import surface_tissue as tissue  # noqa: E402
from cells.registry.models import get_model  # noqa: E402

PLANT_KEYS = ("P1", "P2heat", "P2work")


def stored_terms_abs(state, p):
    """T: the tissue ledger's stored terms (surface_tissue.balances) as absolute values, element
    by element: each inventory element's two chemical terms, cytosol and outside, with no
    intracellular override, and each patch's electric term. Non-finite elements count as 0."""
    with np.errstate(all="ignore"):
        _, _, dv = tissue.capacitor_change(state, p, xp=np)
        scale = 1e-3 * GAS_R * np.asarray(p.temperature)
        total = 0.0
        inventories = (
            (state.amount_increment, p.amount_reference, p.volume, p.active),
            (
                state.extracellular_amount_increment,
                p.extracellular_amount_reference,
                p.extracellular_volume,
                p.outside_active,
            ),
        )
        for delta, anchor, volume, mask in inventories:
            delta = np.asarray(delta)
            a = np.where(mask, anchor, 1.0)
            first = np.abs(scale * delta * (np.log(a / volume) - 1))
            second = np.abs(scale * (a + delta) * np.log1p(delta / a))
            total += float(np.sum(np.where(np.isfinite(first), first, 0.0)))
            total += float(np.sum(np.where(np.isfinite(second), second, 0.0)))
        electric = np.abs(
            0.5e12 * p.membrane_capacitance * dv * (2 * p.initial_membrane_voltage_V + np.asarray(dv))
        )
        total += float(np.sum(np.where(np.isfinite(electric), electric, 0.0)))
    return total


def kinds_stored_abs(structure, row, p):
    """The declared kinds' |stored_pJ| ledger terms (0 without kinds)."""
    if structure is None or not getattr(structure, "kinds", ()):
        return 0.0
    total = 0.0
    for kind in surface_pump_v3._kinds(structure):
        if kind.ledger_terms is None:
            continue
        terms = kind.ledger_terms(row, p, xp=np)
        if "stored_pJ" in terms:
            total += float(np.sum(np.abs(np.asarray(terms["stored_pJ"]))))
    return total


class MagnitudeLedger(H.Ledger):
    """The probe's host ledger path, also returning T and O for the row."""

    def __init__(self, spec, model, layout):
        super().__init__(spec, model, layout)
        inner = getattr(self.model, "inner", None)
        self.inner = inner if self.composite else None
        self.structure = getattr(inner if self.composite else self.model, "structure", None)
        self.reports_energy_magnitude = None  # Known after the first row (None, True or False).

    def extras(self, row):
        """(T, O) at the row, as the registration defines them; the energy magnitude is read as
        the probe's ledger path reads the magnitudes (a composite's retiring rows adjusted)."""
        model, p = self.model, self.p
        with np.errstate(all="ignore"):
            if self.composite:
                adjusted = model._adjusted(row, p, xp=np) if self.retiring else row
                inner_row = self.inner.inner_state(adjusted)
                inner_p = self.inner.inner_layout(p)
            else:
                adjusted, inner_row, inner_p = row, row, p
            own = None
            if self.reports_energy_magnitude is not False:
                if self.composite:
                    m = model.inner_magnitudes(adjusted, p, xp=np, adjust=False)
                else:
                    m = model.channel_magnitudes(row, p, xp=np)
                own = m[self.index]
                if self.reports_energy_magnitude is None and not self.composite:
                    # @3 alone: its energy magnitude is None by construction (ledger_magnitudes
                    # gives the energy check None); read once, not per row.
                    self.reports_energy_magnitude = own is not None
            t = stored_terms_abs(inner_row, inner_p)
            o = 0.0 if own is None else float(np.sum(np.abs(np.asarray(own))))
            o += kinds_stored_abs(self.structure, inner_row, inner_p)
        return t, o


def _scan(model, params, active):
    def advance(carry, inputs):
        x, alive = carry
        dt, c = inputs
        x1, ok1 = model.checked_step(x, dt, c, params, active)
        h1, okh1 = model.checked_step(x, 0.5 * dt, c, params, active)
        h2, okh2 = model.checked_step(h1, 0.5 * dt, c, params, active)
        go = alive & ok1
        nxt = jax.tree.map(lambda a, b: jnp.where(go, a, b), x1, x)
        return (nxt, go), (x1, h2, go, okh1 & okh2)

    return jax.jit(lambda x0, s, c: jax.lax.scan(advance, (x0, jnp.asarray(True)), (s, c)))


def _columns():
    cols = {k: [] for k in ("R", "F", "B", "T", "O", "d_full", "d_half", "dt")}
    for key in PLANT_KEYS:
        cols[f"delta_{key}"], cols[f"F_{key}"] = [], []
    return cols


def record_alone(spec, model, times, checkpoint, steps, controls, scan):
    """@3 alone: the ledger vectorized on the device (the probe's DeviceLedger), T and O on the
    host for every row."""
    p = checkpoint.layout
    ledger = H.DeviceLedger(spec, model, p)
    host = MagnitudeLedger(spec, model, p)
    heat, work = H.fields_of(checkpoint.state, "heat"), H.fields_of(checkpoint.state, "work")
    kind = type(checkpoint.state)
    x = checkpoint.state
    first = ledger(jax.tree.map(lambda v: jnp.asarray(v)[None], x), [0])
    r0 = first[0][0]
    cols, n, refusal = _columns(), len(steps), None
    for start in range(0, n, H.CHUNK):
        stop = min(n, start + H.CHUNK)
        cc = jax.tree.map(lambda v, a=start, b=stop: v[a:b], controls)
        _, (ends, halves, accepted, halved) = scan(x, jnp.asarray(steps[start:stop]), cc)
        accepted, halved = np.asarray(accepted), np.asarray(halved)
        m = stop - start
        if not accepted.all():
            m = int(np.flatnonzero(~accepted)[0])
            refusal = dict(refused_at=start + m, time=float(times[start + m]))
        if m == 0:
            break
        ends = jax.tree.map(lambda v, m=m: v[:m], ends)
        halves = jax.tree.map(lambda v, m=m: v[:m], halves)
        ks = np.arange(start + 1, start + m + 1)
        e1, f1, b1 = ledger(ends, ks)
        eh = ledger(halves, ks)[0]
        e0 = np.concatenate(([r0], e1[:-1]))
        cols["R"].append(e1)
        cols["F"].append(f1)
        cols["B"].append(b1)
        cols["d_full"].append(e1 - e0)
        cols["d_half"].append(np.where(halved[:m], eh - e0, np.nan))
        cols["dt"].append(np.asarray(steps[start : start + m], dtype=float))
        host_rows = jax.tree.map(np.asarray, ends)
        to = [host.extras(kind(*(v[j] for v in host_rows))) for j in range(m)]
        cols["T"].append(np.asarray([t for t, _ in to]))
        cols["O"].append(np.asarray([o for _, o in to]))
        for key, (_, role, size) in zip(PLANT_KEYS, H.PLANTS, strict=True):
            names = work if role == "work" else heat
            ep, fp, _ = ledger(H.scaled_rows(ends, names, 1 + size), ks)
            cols[f"delta_{key}"].append(ep - e1)
            cols[f"F_{key}"].append(fp)
        x = jax.tree.map(lambda v: np.asarray(v)[m - 1], ends)
        r0 = e1[m - 1]
        if refusal is not None:
            break
    out = {k: np.concatenate(v) if v else np.zeros(0) for k, v in cols.items()}
    out["R_initial"] = np.asarray([first[0][0]])
    return out, dict(refusal=refusal, path="device, vectorized (T and O on the host)", events=[], registered={})


def record_host(spec, model, times, checkpoint, steps, controls, scan, plant):
    """Composites, frozen families and the plant world: the probe's host ledger path."""
    p = checkpoint.layout
    ledger = MagnitudeLedger(spec, model, p)
    family = hasattr(model, "composition") and hasattr(model, "module")
    events = H.event_steps(model.module.composite(spec) if family else spec, times)
    kind = type(checkpoint.state)
    edits = {
        key: (lambda x, role=role, size=size: H.scaled(x, H.fields_of(x, role), 1 + size))
        for key, (_, role, size) in zip(PLANT_KEYS, H.PLANTS, strict=True)
    }
    registered = (H.registered_edit(spec, plant), plant["at_s"]) if plant is not None else None
    x, r0 = checkpoint.state, ledger(checkpoint.state, 0)
    initial = r0[0]
    cols, reg = _columns(), {}
    n, refusal, listed = len(steps), None, []
    for start in range(0, n, H.CHUNK):
        stop = min(n, start + H.CHUNK)
        chunk_controls = jax.tree.map(lambda v, a=start, b=stop: v[a:b], controls)
        _, (ends, halves, accepted, halved) = scan(x, jnp.asarray(steps[start:stop]), chunk_controls)
        ends, halves = jax.tree.map(np.asarray, ends), jax.tree.map(np.asarray, halves)
        accepted, halved = np.asarray(accepted), np.asarray(halved)
        for j in range(stop - start):
            k = start + j
            if not accepted[j]:
                refusal = dict(refused_at=k, time=float(times[k]))
                break
            dt = float(steps[k])
            x1 = kind(*(v[j] for v in ends))
            r1 = ledger(x1, k + 1)
            t, o = ledger.extras(x1)
            cols["R"].append(r1[0])
            cols["F"].append(r1[1])
            cols["B"].append(r1[2])
            cols["T"].append(t)
            cols["O"].append(o)
            cols["d_full"].append(r1[0] - r0[0])
            cols["dt"].append(dt)
            if k in events or not halved[j]:
                cols["d_half"].append(np.nan)
                if k in events:
                    listed.append(k)
            else:
                cols["d_half"].append(ledger(kind(*(v[j] for v in halves)), k + 1)[0] - r0[0])
            for key, edit in edits.items():
                e = ledger(edit(x1), k + 1)
                cols[f"delta_{key}"].append(e[0] - r1[0])
                cols[f"F_{key}"].append(e[1])
            if registered is not None and abs(times[k] + dt - registered[1]) < 1e-12:
                e = ledger(registered[0](x1), k + 1)
                reg = dict(step=k, delta=e[0] - r1[0], F=e[1], B=e[2])
            x, r0 = x1, r1
        if refusal is not None:
            break
    out = {k: np.asarray(v, dtype=float) for k, v in cols.items()}
    out["R_initial"] = np.asarray([initial])
    return out, dict(refusal=refusal, path="host", events=listed[:500], registered=reg)


def main(argv):
    out_path, kind, arg = argv[1], argv[2], argv[3]
    max_steps = int(argv[4]) if len(argv) > 4 else 2000
    started = time.perf_counter()
    meta = dict(kind=kind, arg=arg, max_steps=max_steps, atol_pJ=tissue.ENERGY_ATOL_PJ, eps=H.EPS)
    try:
        raw, label, plant = H.world(kind, arg)
        meta["label"] = label
        solver = raw.get("execution", {}).get("solver")
        if solver == "rk4":
            meta.update(excluded="RK4: its energy bound is absolute (rtol 0)", solver=solver)
        else:
            spec = parse_spec(raw)
            model = get_model(spec.model)
            times = timeline(spec)
            checkpoint = initialise(spec)
            steps = np.asarray(integration_steps(spec, times))[:max_steps]
            controls = jax.tree.map(
                lambda v: np.asarray(v)[: len(steps)], control_values(spec, times[:-1])
            )
            params = model.parameters(spec, checkpoint.layout)
            scan = _scan(model, params, checkpoint.layout.active)
            alone = not hasattr(model, "inner_balances") and not hasattr(model, "composition")
            base = model.composition if hasattr(model, "composition") else model
            meta.update(model=type(spec.model).__name__, solver=spec.execution.solver)
            meta["rtol"] = float(base.ENERGY_RTOL[spec.execution.solver])
            meta["planned_steps"] = int(len(steps))
            if alone and plant is None:
                arrays, facts = record_alone(spec, model, times, checkpoint, steps, controls, scan)
            else:
                arrays, facts = record_host(spec, model, times, checkpoint, steps, controls, scan, plant)
            meta.update(facts)
            meta["steps"] = int(len(arrays["R"]))
            np.savez_compressed(out_path, **arrays)
    except BaseException as error:  # noqa: BLE001
        meta["error"] = repr(error)
        meta["where"] = traceback.format_exc()[-1500:]
    meta["seconds"] = time.perf_counter() - started
    with open(out_path.replace(".npz", ".json"), "w") as handle:
        json.dump(meta, handle, indent=1, default=float)
    print(json.dumps({k: meta.get(k) for k in ("label", "steps", "seconds", "error", "excluded")}), flush=True)


if __name__ == "__main__":
    main(sys.argv)
