"""FR-5's world through the engine (validation/compartment_ph_engine/definitions.fr5_world; the
FR-4/FR-5 note's §13.2 and §16): the declared world, FR-1's compartment operator included
(refusal 4 version 1.2 admits the routing door's source kinds), parsed and run a few steps on the
host path from FR-4's pH 7.2 start, its damage schedule moved inside the short horizon.

Shown: both arms and both controls parse in the declared world, with the three factored routes
(the conditioned transfer through acid_0, the cargo and proton pores through damage_0) and the
sink's multiplier; arm R runs with the damage opening during the window, X conserved between the
cytosol and the lumen (the only nodes its routes join), every route's transfer of the right sign,
and the pores moving only once d > 0.
"""

import copy

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from validation.compartment_ph_engine import definitions as defs
from validation.compartment_ph_engine.parameters import ARM_R, ARM_T

STEPS = 12
WINDOW = (2, 8)  # The injury on steps [2, 8), resealing from step 8.


def short(definition, dt):
    d = copy.deepcopy(definition)
    d["experiment"]["end_time"] = STEPS * dt
    d["experiment"]["observation_times"] = [k * dt for k in range(STEPS + 1)]
    d["execution"]["max_steps"] = STEPS + 8
    (entry,) = d["experiment"]["damage_controls"]
    a, b = WINDOW
    if any(step["value"] for step in entry["injury"]):  # Not arm R's control (d = 0).
        entry["injury"] = [dict(time=0.0, value=0.0), dict(time=a * dt, value=1.0),
                           dict(time=b * dt, value=0.0)]
    entry["resealing"] = [dict(time=0.0, value=0.0), dict(time=b * dt, value=1.0)]
    return d


def test_both_arms_and_their_controls_parse_in_the_declared_world():
    for arm, control in ((ARM_T, None), (ARM_T, "f_equals_1"), (ARM_R, None),
                         (ARM_R, "d_equals_0")):
        d = defs.fr5_world(arm, control=control)
        spec = parse_spec(defs.declared_world(short(d, d["execution"]["dt"])))
        kinds = {k for k, _ in spec.model.kinds}
        assert {"cells.kind.patch_damage@1", "cells.kind.ph_condition@1"} <= kinds
        routes = {r.id: r.factors for r in dict(spec.model.kinds)["cells.kind.passive_routes@1"]}
        assert routes["proton_pore_0"] == ("damage_0",)
        assert routes["cargo_transfer_0"] == (() if control == "f_equals_1" else ("acid_0",))
        assert ("cargo_pore_0" in routes) == (arm is ARM_R)


def test_arm_r_runs_with_the_pores_opening_and_x_conserved():
    d = defs.fr5_world(ARM_R)
    dt = d["execution"]["dt"]
    spec = parse_spec(defs.development_world(short(d, dt)))
    obs = run(spec).observations
    ids = list(spec.model.species_ids)
    x, h = ids.index("X"), ids.index("H")
    cell = 0
    lumen = [o.id for o in spec.model.extracellular].index(defs.LUMEN)
    total = np.asarray(obs.amount)[:, x, cell] + np.asarray(obs.extracellular_amount)[:, x, lumen]
    assert np.max(np.abs(total - total[0])) <= 1e-12 * total[0]
    bounding = [m.id for m in spec.model.membranes].index(defs.BOUNDING)
    damage = np.asarray(obs.patch_damage)[:, bounding]
    assert np.all(damage[: WINDOW[0] + 1] == 0.0) and damage[WINDOW[1]] > 0
    routes = [r.id for r in dict(spec.model.kinds)["cells.kind.passive_routes@1"]]
    moved = np.asarray(obs.passive_transferred)  # [record, species, route], inward (to the cell).
    pore_h = moved[:, h, routes.index("proton_pore_0")]
    pore_x = moved[:, x, routes.index("cargo_pore_0")]
    assert np.all(pore_h[: WINDOW[0] + 1] == 0.0) and np.all(pore_x[: WINDOW[0] + 1] == 0.0)
    assert pore_h[-1] > 0 and pore_x[-1] > 0  # Out of the acidic, loaded lumen into the cytosol.
    assert moved[-1, x, routes.index("cargo_transfer_0")] > 0


def test_the_engine_records_give_fr5s_readouts():
    """engine_records on arm R's short world: the judge's FR-5 series (the generator's
    ENGINE_READOUTS: X at both nodes, d, f, each route's cumulative transfer cytosol to lumen and
    its heat), and the cargo's route ledger: the lumen's X changes by the cargo routes'
    transfers."""
    from validation.compartment_ph_engine import engine_records

    d = defs.fr5_world(ARM_R)
    record = engine_records.run(short(d, d["execution"]["dt"]), path="host")
    assert record["completed"], record["refusal"]
    s = record["series"]
    for name in ("X_L", "X_c", "d", "f", "moved_H_pump", "moved_H_leak", "moved_H_pore",
                 "moved_X_transfer", "moved_X_pore", "heat_proton_leak_0_pJ",
                 "heat_proton_pore_0_pJ", "heat_cargo_transfer_0_pJ", "heat_cargo_pore_0_pJ",
                 "heat_bounding_0_K_pJ", "heat_pump_pJ"):
        assert len(s[name]) == STEPS + 1, name
    assert s["d"][0] == 0.0 and s["d"][-1] > 0 and all(0 <= f <= 1 for f in s["f"])
    assert s["moved_X_pore"][-1] < 0 and s["moved_X_transfer"][-1] < 0  # Lumen to cytosol.
    for k in range(STEPS + 1):  # The lumen's X changes by exactly what its routes moved.
        change = s["X_L"][k] - s["X_L"][0]
        moved = s["moved_X_transfer"][k] + s["moved_X_pore"][k]
        assert abs(change - moved) <= 1e-15 * s["X_L"][0], k
    assert all(b >= a for a, b in zip(s["heat_cargo_pore_0_pJ"], s["heat_cargo_pore_0_pJ"][1:],
                                      strict=False))
