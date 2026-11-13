"""Small @3 worlds for membrane_entity_state@1 and scheduled_membrane_insertion@1 (v2 design §3).

All values are synthetic, around one heredity cell (validation/tissue/surface_pump_v3_fixtures):
* one_patch: the heredity cell facing its held bath (one patch, one clamp);
* two_clamps: the cell with a second patch on a second held bath at another potential, so a
  capacitance change moves image charge between the clamps;
* cleft_cell: the cell with a furrow patch on a finite cleft node (zero charge anchor, bath
  composition) joined to the bath by an access face. The access is narrow, so the cleft's RC
  time through it (about 0.5 s) is resolved by a 1 ms IMEX step; a wide access makes the
  onset a transient faster than the step, which IMEX books to its own tolerance only.
with_operators adds the membrane state (every population declared) and an insertion.
"""

import copy
import math

from cells.core import pump_composite_spec as cs
from validation.tissue import pump_water_fixtures as wfx
from validation.tissue import surface_pump_v3_fixtures as v3fx

STATE = "membrane_entity_state@1"
INSERTION = "scheduled_membrane_insertion@1"
DT = 1e-3
DENSITY = 1e13  # Reference density of every population (units/m^2).
SPECIFIC_CAPACITANCE = 0.05  # F/m^2, the heredity patch's.


def one_patch(*, end=0.004, observation_times=None):
    base = wfx.heredity_cell("H", dt=DT, end_time=end)
    base["experiment"]["observation_times"] = observation_times or [0.0, end]
    return base


def two_clamps(*, potential_V=0.02, end=0.004):
    base = one_patch(end=end)
    m = base["model"]
    bath = copy.deepcopy(m["extracellular"][0])
    bath.update(id="bath_b", boundary_potential_V=potential_V)
    m["extracellular"].append(bath)
    patch = copy.deepcopy(m["membranes"][0])
    patch.update(id="membrane_b", outside="bath_b", pump=None)
    patch["area_m2"] *= 0.5
    patch["capacitance_F"] *= 0.5
    m["membranes"].append(patch)
    base["experiment"]["membrane_controls"].append(
        dict(membrane_id="membrane_b", schedule=[dict(time=0.0, availability=1.0)])
    )
    base["execution"].update(extracellular_capacity=2, membrane_capacity=2)
    return base


def cleft_cell(*, end=0.006, observation_times=None, access_area_m2=1e-14, cleft_pL=0.01):
    base = one_patch(end=end, observation_times=observation_times)
    m = base["model"]
    ids = [s["id"] for s in m["species"]]
    z = {s["id"]: s["valence"] for s in m["species"]}
    amounts = {s: v3fx.HEREDITY_BATH_mM[s] * cleft_pL for s in ids}
    m["extracellular"].append(
        dict(
            id="cleft",
            volume_pL=cleft_pL,
            initial_amount_fmol=amounts,
            fixed_charge_equivalent_fmol=-math.fsum(z[s] * amounts[s] for s in ids),
            initial_charge_C=0.0,
            reservoir=False,
            boundary_potential_V=0.0,
        )
    )
    furrow = copy.deepcopy(m["membranes"][0])
    area = 1e-11
    furrow.update(
        id="furrow",
        outside="cleft",
        pump=None,
        area_m2=area,
        capacitance_F=SPECIFIC_CAPACITANCE * area,
    )
    m["membranes"].append(furrow)
    m["faces"].append(
        dict(
            id="access",
            sender="cleft",
            receiver="bath_0",
            area_m2=access_area_m2,
            length_m=1e-2,
            diffusivity_m2_per_s={s: 1e-9 for s in ids},
            law="logmean_electrodiffusion@1",
        )
    )
    base["experiment"]["membrane_controls"].append(
        dict(membrane_id="furrow", schedule=[dict(time=0.0, availability=1.0)])
    )
    base["execution"].update(extracellular_capacity=2, membrane_capacity=2, face_capacity=1)
    return base


def membrane_state(raw, catalogue=None):
    """The membrane_entity_state@1 block declaring every population of raw."""
    return dict(
        law=STATE,
        populations=[
            dict(
                channel_id=c["id"],
                functional_unit=c["id"].split("_")[0],
                catalogue=None if catalogue is None else dict(catalogue[c["id"]]),
                reference_density_per_m2=DENSITY,
            )
            for c in raw["model"]["channels"]
        ],
    )


def with_operators(base, insertion=None, *, catalogue=None):
    """base (@3) as a composition with the membrane state and, given
    insertion = {membrane_id: (densities, onset_time, [(time, rate), ...])}, the insertion."""
    raw = cs.frozen_definition(base)
    raw["model"]["operators"] = [membrane_state(raw, catalogue)]
    if insertion is not None:
        raw["model"]["operators"].append(
            dict(
                law=INSERTION,
                patches=[
                    dict(
                        membrane_id=k,
                        specific_capacitance_F_per_m2=SPECIFIC_CAPACITANCE,
                        population_densities_per_m2=dict(densities),
                    )
                    for k, (densities, _, _) in insertion.items()
                ],
            )
        )
        raw["experiment"]["insertion_controls"] = [
            dict(
                membrane_id=k,
                onset_time=onset,
                schedule=[dict(time=t, rate_m2_per_s=r) for t, r in changes],
            )
            for k, (_, onset, changes) in insertion.items()
        ]
    return raw


def furrow_insertion(rate=1e-11, onset=0.002):
    """The cleft cell's furrow: closed until onset, then inserted at a constant rate."""
    return {"furrow": ({}, onset, [(0.0, 0.0), (onset, rate)])}
