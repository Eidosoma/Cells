"""Independent coupled 38-field reference using actual free-owner sample views.

No production/JAX imports. Frozen independent Decimal source-factor arithmetic
and complete calcium/fuel/field/ledger references remain the equation owners.
"""

from copy import deepcopy
from decimal import localcontext

import numpy as np
from scipy.integrate import solve_ivp

from validation.regulation.betse_network_modulation_reference import alpha, d
from validation.regulation.integrated_network_regulation_fixtures import parent_definition
from validation.tissue import surface_calcium_energy_reference as energy

flatten, unpack, initial = energy.flatten, energy.unpack, energy.initial


def bind(raw):
    parent = parent_definition(raw)
    c = energy.bind(parent)
    rules = deepcopy(raw["model"]["network_regulation"]["rules"])
    return dict(c, energy=c, integrated_raw=deepcopy(raw), rules=rules)


def samples(c, state):
    values = unpack(c, state)
    species = [r["id"] for r in c["raw"]["model"]["ionic"]["species"]]
    free = np.stack(
        [
            (store.n0 + values["chemical_amount_increment"][i])[
                [store.ids.index(s) for s in species], store.cy
            ]
            / store.volume[store.cy]
            for i, store in enumerate(c["stores"])
        ],
        axis=1,
    )
    outer = (c["ao"] + values["extracellular_amount_increment"]) / c["vo"]
    fuel = (c["energy_initial"] + values["energy_amount_increment_fmol"]) / c["energy_volumes"]
    pumps = {
        patch["pump"]["id"]: j
        for j, patch in enumerate(c["raw"]["model"]["ionic"]["membranes"])
        if patch["pump"] is not None
    }
    result = []
    for rule in c["rules"]:
        j = pumps[rule["pump_id"]]
        inside, outside = c["patch_owners"][j], c["layout"]["membrane_outside"][j]
        cell = c["pools"][rule["fuel_pool_id"]]["cell_id"]
        owner = c["cell_ids"].index(cell)
        if inside != owner:
            raise ValueError("Cross-owner fuel regulation")
        ci = [*free[:, inside], *fuel[:, owner]]
        co = [*outer[:, outside], 0.0, 0.0, 0.0]
        result.append([[float(a), float(b)] for a, b in zip(ci, co, strict=True)])
    return np.asarray(result).reshape(len(result), len(species) + 3, 2)


def factors(c, state, time):
    sample = samples(c, state)
    m = c["raw"]["model"]
    patches = m["ionic"]["membranes"]
    by_pump = {
        patch["pump"]["id"]: j for j, patch in enumerate(patches) if patch["pump"] is not None
    }
    multiplier = np.asarray([1.0 if patch["pump"] is not None else 0.0 for patch in patches])
    rule_factors = []
    with localcontext() as context:
        context.prec = 80
        for i, rule in enumerate(c["rules"]):
            configuration = rule["configuration"]
            raw = dict(
                sample_mM=sample[i].tolist(),
                membrane_to_environment=[0],
                species_ids=[*[s["id"] for s in m["ionic"]["species"]], "ATP", "ADP", "Pi"],
            )
            factor = float(d(configuration["max effect"]) * alpha(configuration, raw, 0))
            if not np.isfinite(factor) or not 0 <= factor <= 1:
                raise ValueError("Unsupported signed/unbounded native pump factor")
            rule_factors.append(factor)
            multiplier[by_pump[rule["pump_id"]]] = factor
    scheduled = np.zeros(len(patches))
    for row in c["raw"]["experiment"]["pump_controls"]:
        scheduled[by_pump[row["pump_id"]]] = next(
            v["availability"] for v in reversed(row["schedule"]) if v["time"] <= time
        )
    return dict(
        rule_factors=rule_factors,
        pump_factor=multiplier.tolist(),
        scheduled=scheduled.tolist(),
        effective=(scheduled * multiplier).tolist(),
        samples_mM=sample.tolist(),
    )


def evaluate(c, state, time):
    regulation = factors(c, state, time)
    projected = deepcopy(c["raw"])
    by_pump = {
        patch["pump"]["id"]: j
        for j, patch in enumerate(projected["model"]["ionic"]["membranes"])
        if patch["pump"] is not None
    }
    for row in projected["experiment"]["pump_controls"]:
        row["schedule"] = [
            dict(time=0.0, availability=regulation["effective"][by_pump[row["pump_id"]]])
        ]
    current = energy.bind(projected)
    slope, phi, proof = energy.evaluate(current, state, time)
    return slope, phi, proof | dict(network_regulation=regulation)


def event_times(raw):
    events = {0.0, raw["experiment"]["end_time"], *raw["experiment"]["observation_times"]}
    for name, groups in raw["experiment"].items():
        if name.endswith("_controls"):
            for group in groups:
                events.update(
                    row["time"] for row in group.get("schedule", group.get("controls", []))
                )
    return sorted(events)


def integrate(raw, *, rtol=2e-11, max_step_s=1.25e-6):
    c = bind(raw)
    state = initial(c)
    knots = event_times(raw)
    rows = [state.copy()]
    failures = []
    for left, right in zip(knots[:-1], knots[1:], strict=True):

        def fun(time, state, held_time=left):
            # All declared input families remain at their right-continuous
            # left-endpoint level; state-dependent factors read every trial.
            return evaluate(c, state, held_time)[0]

        result = solve_ivp(
            fun, (left, right), state, method="DOP853", rtol=rtol, atol=1e-15, max_step=max_step_s
        )
        if not result.success:
            failures.append(dict(left=left, right=right, message=result.message))
            raise RuntimeError(str(failures))
        state = result.y[:, -1]
        rows.append(state.copy())
    return (
        c,
        np.asarray(knots),
        np.stack(rows),
        dict(status="passed", failures=failures, rtol=rtol, atol=1e-15, max_step_s=max_step_s),
    )
