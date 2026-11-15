"""A4 and A5: the engine's dt studies against the independent references (development runs).

docs/INVENTORY_COUPLING_DESIGN.md §4.4 (A4, A5), with the criterion written before any engine run
(inventory-coupling-m3-20261114-01/HANDOFF.md). The worlds and their translation are
validation/tissue/regulated_availability_references; the references are used through
validation/coupling/REFERENCES_USAGE.md's API only (rc.simulate, rc.floor and the record keys).

For each world and arm (the uncoupled baseline, the coupled world, A4's fast arm), the engine runs
at dt 1, 0.5, 0.25 and 0.125 ms through one window program, and every observable is compared at
the records with the reference (Radau, rtol 1e-10): V per cell, amounts per cell and species,
a_eff per element, and with the operator s, U and F. The orders count only where the finer error
is at least 100 times the floor. At 1 ms a tolerance is proposed (2 e, and at least 100 floors),
and a planted control (one factor parameter scaled so the reference moves by about 10 tau) must
exceed it. The gate of every contact stays at exactly 1.

Usage: python -m validation.tissue.regulated_availability_dt_study OUT.json [a4] [a5]
"""

import json
import math
import sys
import time

import jax
import numpy as np

from cells.core.specs import parse_spec
from cells.core.windows import WindowPolicy, iter_windows
from validation.coupling import cells_reference as rc
from validation.tissue import regulated_availability_references as rr

DTS = (1e-3, 5e-4, 2.5e-4, 1.25e-4)
WINDOW = 1000
FLOOR_FACTOR = 100.0
DIMENSIONLESS = ("a_eff", "F", "s", "U")
ROUNDING_FLOOR = 1e-13  # A tolerance below this on an O(1) quantity would test rounding.
OBSERVABLES = ("V", "amounts", "a_eff", "s", "U", "F")


def grid_records(end, every, dt):
    """Record times on the engine's grid (k * dt), every `every`, from the first after 0."""
    stride = round(every / dt)
    return [k * stride * dt for k in range(1, round(end / every) + 1)]


def engine_run(world, *, dt, end, every, initial):
    """{time: row} from the engine's windowed run; rows hold V, amounts, a_eff, s, U and F."""
    times = [0.0, *grid_records(end, every, dt)]
    spec = parse_spec(rr.engine_definition(world, dt=dt, end=end, times=times, initial=initial))
    m = spec.model
    cells = [c.id for c in m.cells]
    species = list(m.species_ids)
    ions = [species.index(s) for s in rr.SPECIES]
    anchor = np.asarray([[c.initial_amount_fmol[i] for c in m.cells] for i in range(len(species))])
    junctions = [j.id for j in m.junctions]
    channels = [c.id for c in m.channels]
    rows, history, gates = {}, {}, []
    started = time.perf_counter()
    for window in iter_windows(spec, WindowPolicy(WINDOW, "full")):
        h = window.history
        for i, t in enumerate(np.asarray(window.times)):
            history[round(float(t) / dt)] = (
                np.asarray(h.amount_increment)[i],
                np.asarray(h.regulatory_state)[i] if hasattr(h, "regulatory_state") else None,
                np.asarray(h.regulatory_input_integral)[i]
                if hasattr(h, "regulatory_input_integral")
                else None,
            )
        if len(junctions):
            gates.append(np.asarray(h.junction_gate))
        obs = vars(window.observations)
        for j, t in enumerate(np.asarray(obs["times"])):
            rows[float(t)] = dict(
                V=np.asarray(obs["cell_potential_V"])[j],
                junction=np.asarray(obs["junction_availability"])[j],
                channel=np.asarray(obs["channel_availability"])[j],
                F=np.asarray(obs["coupling_factor"])[j] if "coupling_factor" in obs else None,
            )
    wall = time.perf_counter() - started
    out = {}
    for t, row in rows.items():
        k = round(t / dt)
        increment, s, u = history[k]
        amounts = anchor + increment
        out[t] = dict(
            V={c: float(row["V"][i]) for i, c in enumerate(cells)},
            amounts={c: tuple(float(amounts[s_, i]) for s_ in ions) for i, c in enumerate(cells)},
            a_eff={
                **{e: float(row["junction"][i]) for i, e in enumerate(junctions)},
                **{q: float(row["channel"][i]) for i, q in enumerate(channels)},
            },
            s=s,
            U=u,
            F=row["F"],
        )
    gate_ok = all(np.all(g == 1.0) for g in gates)
    return out, dict(wall_s=wall, gate_held_at_1=bool(gate_ok), steps=round(end / dt))


def route_products(world, engine_F):
    """The engine's routes multiplied per (coupling, element), sides in order: the reference's F."""
    out, k = {}, 0
    for name, c in world.couplings.items():
        width = 2 if c.side == "both" else 1
        value = 1.0
        for j in range(width):
            value = value * float(engine_F[k + j])
        out[(name, c.target)] = value
        k += width
    return out


def errors(world, engine, reference, record, slots):
    e = dict.fromkeys(OBSERVABLES, 0.0)
    for t in record:
        a, b = engine[t], reference.at[t]
        e["V"] = max(e["V"], max(abs(a["V"][c] - b["V"][c]) for c in world.cells))
        e["amounts"] = max(
            e["amounts"],
            max(
                abs(x - y)
                for c in world.cells
                for x, y in zip(a["amounts"][c], b["amounts_fmol"][c], strict=True)
            ),
        )
        e["a_eff"] = max(
            e["a_eff"], max(abs(a["a_eff"][k] - b["elements"][k]["a_eff"]) for k in b["elements"])
        )
        if slots:
            e["s"] = max(
                e["s"], max(abs(float(a["s"][i]) - b["s"][slot]) for i, slot in enumerate(slots))
            )
            e["U"] = max(
                e["U"], max(abs(float(a["U"][i]) - b["U"][slot]) for i, slot in enumerate(slots))
            )
        if world.couplings and a["F"] is not None:
            products = route_products(world, a["F"])
            e["F"] = max(e["F"], max(abs(products[k] - b["routes"][k]["F"]) for k in products))
    return e


def orders(table, floor):
    out = {}
    for x in OBSERVABLES:
        pairs = []
        for (dt, e), (_, f) in zip(table, table[1:], strict=False):
            ea, fa = e[x], f[x]
            if fa == 0.0 and ea == 0.0:
                pairs.append(dict(dt=dt, order=None, status="exact"))
                continue
            # Resolvable only well above the reference's floor, and, for a dimensionless
            # quantity of order 1, above rounding (a reference floor of exactly 0 is a closed form).
            resolution = max(
                FLOOR_FACTOR * floor.get(x, 0.0), ROUNDING_FLOOR if x in DIMENSIONLESS else 0.0
            )
            limited = fa < max(resolution, 1e-300)
            order = math.log2(ea / fa) if fa > 0 and ea > 0 else None
            pairs.append(
                dict(
                    dt=dt,
                    order=order,
                    status="floor-limited"
                    if limited
                    else (
                        "in band" if order is not None and 1.7 <= order <= 2.3 else "OUT OF BAND"
                    ),
                )
            )
        out[x] = pairs
    return out


def study(name, world, *, end, every, label):
    record = grid_records(end, every, DTS[0])
    reference = rc.simulate(world, end, record=tuple(record))
    initial = {
        c: (reference.initial[c]["V"], reference.initial[c]["background_fmol"]) for c in world.cells
    }
    table, details = [], []
    for dt in DTS:
        engine, info = engine_run(world, dt=dt, end=end, every=every, initial=initial)
        e = errors(world, engine, reference, record, reference.slots)
        row0 = max(abs(engine[0.0]["V"][c] - initial[c][0]) for c in world.cells)
        table.append((dt, e))
        details.append(dict(dt=dt, errors=e, row0_V_difference=row0, **info))
        print(
            label,
            name,
            dt,
            {k: f"{v:.3e}" for k, v in e.items()},
            f"{info['wall_s']:.1f} s",
            flush=True,
        )
    return reference, initial, table, details


def run_world(label, make, *, end, every, baseline=None, fast=None, plant=None):
    """make(**overrides) -> World. baseline: the uncoupled arm's overrides (default: every coupling
    switched off); fast: the fast arm's; plant: (keyword, its value, the observable it moves).
    Returns the world's record."""
    baseline = dict(enabled=0) if baseline is None else baseline
    out = {}
    record = tuple(grid_records(end, every, DTS[0]))
    _, _, floor = rc.floor(make(), end, record)
    floor = {k: float(v) for k, v in floor.items() if np.isscalar(v)}
    out["floor"] = floor
    _, _, base_floor = rc.floor(make(**baseline), end, record)
    base_floor = {k: float(v) for k, v in base_floor.items() if np.isscalar(v)}
    arms = [("baseline", make(**baseline), base_floor), ("coupled", make(), floor)]
    if fast is not None:
        _, _, fast_floor = rc.floor(make(**fast), end, record)
        arms.append(
            ("fast", make(**fast), {k: float(v) for k, v in fast_floor.items() if np.isscalar(v)})
        )
    for arm, world, arm_floor in arms:
        reference, initial, table, details = study(arm, world, end=end, every=every, label=label)
        out[arm] = dict(
            details=details,
            orders=orders(table, arm_floor),
            floor=arm_floor,
        )
        if arm == "fast":
            out[arm]["error_over_dt2"] = [
                dict(dt=dt, **{x: e[x] / dt**2 for x in OBSERVABLES}) for dt, e in table
            ]
        if arm == "coupled":
            e1 = table[0][1]
            tau = {
                x: max(
                    2.0 * e1[x],
                    FLOOR_FACTOR * floor.get(x, 0.0),
                    ROUNDING_FLOOR if x in DIMENSIONLESS else 0.0,
                )
                for x in OBSERVABLES
            }
            out["proposed_tolerance_at_1ms"] = tau
            out["error_at_1ms"] = e1
            out["error_over_floor_at_1ms"] = {
                x: (e1[x] / floor[x] if floor.get(x, 0.0) > 0 else None) for x in OBSERVABLES
            }
            out["error_over_tolerance_at_1ms"] = {
                x: (e1[x] / tau[x] if tau[x] > 0 else None) for x in OBSERVABLES
            }
            coupled_reference, coupled_initial = reference, initial
    if plant is not None:
        key, value, target = plant
        probe = 1e-3
        moved = rc.simulate(make(**{key: value * (1 + probe)}), end, record=record)
        sensitivity = (
            errors(
                make(),
                _as_engine(moved, make()),
                coupled_reference,
                record,
                coupled_reference.slots,
            )[target]
            / probe
        )
        tau = out["proposed_tolerance_at_1ms"][target]
        delta = 10.0 * tau / sensitivity if sensitivity > 0 else float("nan")
        engine, info = engine_run(
            make(**{key: value * (1 + delta)}),
            dt=DTS[0],
            end=end,
            every=every,
            initial=coupled_initial,
        )
        planted = errors(make(), engine, coupled_reference, record, coupled_reference.slots)
        out["planted"] = dict(
            parameter=key,
            observable=target,
            delta=delta,
            sensitivity_per_unit=sensitivity,
            planted_error=planted[target],
            tolerance=tau,
            ratio_to_tolerance=planted[target] / tau if tau > 0 else None,
            fails_at_tolerance=bool(planted[target] > tau),
            all_errors=planted,
        )
        print(label, "planted", out["planted"], flush=True)
    return out


def _as_engine(run, world):
    """A reference run's records in the engine-row shape, so `errors` compares two references."""
    out = {}
    for t, b in run.at.items():
        F = []
        for name, c in world.couplings.items():
            route = b["routes"][(name, c.target)]
            # The engine's routes of a side-both coupling multiply to the reference's F.
            F += [route["F"], 1.0] if c.side == "both" else [route["F"]]
        out[t] = dict(
            V=b["V"],
            amounts=b["amounts_fmol"],
            a_eff={k: v["a_eff"] for k, v in b["elements"].items()},
            s=[b["s"][slot] for slot in run.slots] if run.slots else None,
            U=[b["U"][slot] for slot in run.slots] if run.slots else None,
            F=F if world.couplings else None,
        )
    return out


def main(path, which):
    jax.config.update("jax_enable_x64", True)
    result = {}
    if "a4" in which:  # Started after the contact's 50 ms voltage transient (relaxed).
        result["A4"] = run_world(
            "A4",
            rr.relaxed(rr.feedback_world, 0.05),
            end=2.0,
            every=0.1,
            fast=dict(k_on=750.0, k_off=150.0),
            plant=("basal", 0.2, "a_eff"),
        )
    if "a5" in which:  # At rest uncoupled, so its baseline steps the population's schedule.
        result["A5"] = run_world(
            "A5",
            rr.cell_world,
            end=1.0,
            every=0.05,
            baseline=dict(enabled=0, population_schedule=((0.0, 1.0), (0.2, 0.3), (0.5, 1.0))),
            plant=("basal", 0.1, "V"),
        )

    def plain(value):
        if isinstance(value, dict):
            return {str(k): plain(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [plain(v) for v in value]
        if isinstance(value, (np.floating, np.integer, np.bool_)):
            return value.item()
        return value

    with open(path, "w") as handle:
        json.dump(plain(result), handle, indent=1, sort_keys=True)
        handle.write("\n")


if __name__ == "__main__":
    main(sys.argv[1], set(sys.argv[2:]) or {"a4", "a5"})
