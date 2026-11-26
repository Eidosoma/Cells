"""cells.operator.species_regulated_availability@1 composed with cells.operator.electrode_current_injection@1 (a development run).

docs/INVENTORY_COUPLING_DESIGN.md §1.12: injection composes, and its charged carriers may be a
state's inputs (the kinetic form only, ruling 1). Making no acceptance claim. One heredity cell
facing its held bath, 20 steps at 1 ms: the electrode injects K and M; a state of K in the cell
sets its Kir population's availability (the complement, basal 1/4). One program; the arms are data:
* every host check passes on every row, at both polarities;
* the observed factors equal an independent evaluation at every saved row;
* the polarity moves K, and the state with it, in opposite directions (non-vacuous).
"""

import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from validation.tissue import pump_water_fixtures as wfx
from validation.tissue import regulated_availability_fixtures as rf
from validation.tissue import secreted_species_fixtures as sfx

END = 0.02
CARRIERS = {"K": 0.4912, "M": 0.5088}
_cache = {}


def go(current_A):
    if current_A not in _cache:
        base = wfx.heredity_cell("H", dt=1e-3, end_time=END)
        base["experiment"]["observation_times"] = list(sfx.grid_times(END, 1e-3, 0.002))
        raw = cs.frozen_definition(base)
        cell = raw["model"]["cells"][0]["id"]
        raw["model"]["operators"] = [
            dict(
                law="cells.operator.electrode_current_injection@1",
                electrodes=[dict(cell_id=cell, carriers=CARRIERS)],
            )
        ]
        raw["experiment"]["injection_controls"] = [
            dict(cell_id=cell, schedule=[dict(time=0.0, current_A=current_A)])
        ]
        plain = parse_spec(raw)  # The cell's own K level sets the half-saturation (u near 1/2).
        k_row = list(plain.model.species_ids).index("K")
        k_mM = plain.model.cells[0].initial_amount_fmol[k_row] / plain.model.cells[0].volume_pL
        kir = next(c.id for c in plain.model.channels if c.id.startswith("kir"))
        raw = rf.with_coupling(
            raw,
            species=["K"],
            states=[
                rf.state(
                    "s",
                    [cell],
                    [("hill_activation", "K", k_mM, 4.0)],
                    on=20.0,
                    off=5.0,
                    initial=0.5,
                )
            ],
            couplings=[
                rf.coupling("c", "channel", [kir], ("state", "s"), "state_complement", basal=0.25)
            ],
        )
        spec = parse_spec(raw)
        _cache[current_A] = (spec, run(spec))
    return _cache[current_A]


@pytest.mark.parametrize("current_A", [1e-12, -1e-12])
def test_the_composition_runs_and_its_factor_is_the_law(current_A):
    spec, result = go(current_A)
    times = np.asarray(result.times)
    rows = [int(np.flatnonzero(times == t)[0]) for t in spec.experiment.observation_times]
    s = np.asarray(result.history.regulatory_state)[rows, 0]
    observed = np.asarray(result.observations.coupling_factor)[:, 0]
    assert observed.tobytes() == (0.25 + 0.75 * (1.0 - s)).tobytes()


def test_the_polarity_moves_k_and_the_state_in_opposite_directions():
    spec, plus = go(1e-12)
    _, minus = go(-1e-12)
    k = list(spec.model.species_ids).index("K")
    dk_plus = np.asarray(plus.history.amount_increment)[-1, k, 0]
    dk_minus = np.asarray(minus.history.amount_increment)[-1, k, 0]
    assert dk_plus > dk_minus  # Positive current carries K in.
    s_plus = np.asarray(plus.history.regulatory_state)[-1, 0]
    s_minus = np.asarray(minus.history.regulatory_state)[-1, 0]
    assert s_plus > s_minus  # A Hill activation of K: more K, a larger fraction.
