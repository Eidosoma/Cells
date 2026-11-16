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

from cells.core.runner import run
from cells.core.specs import parse_spec
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
        assert {"cells.patch_damage@1", "cells.ph_condition@1"} <= kinds
        routes = {r.id: r.factors for r in dict(spec.model.kinds)["cells.passive_routes@1"]}
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
    routes = [r.id for r in dict(spec.model.kinds)["cells.passive_routes@1"]]
    moved = np.asarray(obs.passive_transferred)  # [record, species, route], inward (to the cell).
    pore_h = moved[:, h, routes.index("proton_pore_0")]
    pore_x = moved[:, x, routes.index("cargo_pore_0")]
    assert np.all(pore_h[: WINDOW[0] + 1] == 0.0) and np.all(pore_x[: WINDOW[0] + 1] == 0.0)
    assert pore_h[-1] > 0 and pore_x[-1] > 0  # Out of the acidic, loaded lumen into the cytosol.
    assert moved[-1, x, routes.index("cargo_transfer_0")] > 0
