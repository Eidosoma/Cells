"""Independent complete 43/48-field trajectories and endpoint accounting.

No production imports or coefficient reuse: workers read the independently
prepared serialized definition. Frozen parent equations retain live free ions,
chemical stores, finite fuel, compliance and prescribed repair ownership.
"""

import numpy as np

from validation.tissue import calcium_energy_water_hcn_extra_reference as water
from validation.tissue import calcium_energy_water_repair_hcn_extra_reference as repair

EQUATIONS = {water.MODEL_ID: water, repair.MODEL_ID: repair}


def bind(raw):
    equation = EQUATIONS[raw["model"]["id"]]
    return equation, equation.bind(raw)


def integrate(raw, *, refinement=2):
    equation, _ = bind(raw)
    return equation.integrate(raw, refinement=refinement, max_step_s=0.625e-6)


def conservation(equation, context, vector, time):
    d = equation.unpack(context, vector)
    inside, outside = d["volume_increment_pL"], d["extracellular_volume_increment_pL"]
    local, external = inside.copy(), outside.copy()
    ion = context["raw"]["model"]["ionic"]
    cell_ids = [row["id"] for row in ion["cells"]]
    outside_ids = [row["id"] for row in ion["extracellular"]]
    for i, membrane in enumerate(ion["membranes"]):
        local[cell_ids.index(membrane["inside"])] += d["water_transferred_pL"][i]
        external[outside_ids.index(membrane["outside"])] -= d["water_transferred_pL"][i]
    before = context["energy_initial"]
    pools = before + d["energy_amount_increment_fmol"]
    stored = equation.free_energy_change(context, vector, float(time))
    heat = sum(
        float(np.sum(value)) for key, value in d.items() if key.endswith("_dissipated_energy_pJ")
    )
    work = sum(
        float(np.sum(d[key]))
        for key in ("regeneration_supplied_work_pJ", "reservoir_work_pJ", "electrode_work_pJ")
    )
    result = dict(
        energy_pJ=float(stored + heat - work),
        ionic_total_fmol=float(
            np.max(
                np.abs(
                    d["amount_increment"].sum(axis=1)
                    + d["extracellular_amount_increment"].sum(axis=1)
                ),
                initial=0,
            )
        ),
        water_local_pL=float(np.max(np.abs(local), initial=0)),
        water_outside_pL=float(np.max(np.abs(external), initial=0)),
        water_total_pL=float(abs(inside.sum() + outside.sum())),
        adenylate_fmol=float(
            np.max(np.abs(pools[0] + pools[1] - before[0] - before[1]), initial=0)
        ),
        phosphorus_fmol=float(
            np.max(
                np.abs(
                    3 * pools[0]
                    + 2 * pools[1]
                    + pools[2]
                    - 3 * before[0]
                    - 2 * before[1]
                    - before[2]
                ),
                initial=0,
            )
        ),
    )
    if "damage" in d:
        result["damage_ledger"] = float(
            np.max(
                np.abs(
                    d["damage"]
                    - context["initial_damage"]
                    - d["damage_opened"]
                    + d["damage_closed"]
                ),
                initial=0,
            )
        )
    return result


def assert_conservation(rows):
    maxima = {key: max(abs(row[key]) for row in rows) for key in rows[0]}
    for key, value in maxima.items():
        limit = (
            1e-9
            if key == "energy_pJ"
            else 4096 * np.finfo(float).eps
            if key == "damage_ledger"
            else 2e-12
        )
        assert value <= limit, (key, value, limit)
    return maxima
