"""cells.operator.species_regulated_availability@1 composed with cells.operator.local_species_reactions@1 (a development run).

docs/INVENTORY_COUPLING_DESIGN.md §1.7 and §1.12: D152's reactions write rows this operator only
reads (reads are not writes). Making no acceptance claim. The seven-cell heredity sheet, 20 steps
at 1 ms: D152 makes R in cell_0 (zero-order mass action, its multiplier scheduled), and the
operator reads R at once, a Hill inhibition on junction_0's first side. One program; the arms are
data:
* every host check passes on every row; R's identity agrees between the two declarations;
* R in cell_0 rises at the reaction's rate, and the observed factor equals an independent
  evaluation at every saved row;
* with the multiplier at 0, R and the factor hold and junction_0's step differs (non-vacuous).
"""

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from validation.tissue import regulated_availability_fixtures as rf
from validation.tissue import species_reactions_fixtures as rxf

END = 0.02
RATE_mM_PER_S = 0.05  # 0 -> R in cell_0, against a 1 µM anchor: R rises twofold by 20 ms.
_cache = {}


def go(multiplier):
    if multiplier not in _cache:
        raw = rf.sheet(end=END, observation_times=[0.0, 0.005, 0.01, 0.015, 0.02])
        raw = rxf.with_reactions(
            raw,
            [rxf.species(rf.REGULATOR)],
            [
                rxf.mass_action(
                    "make_R", {"cells": ["cell_0"]}, {}, {rf.REGULATOR: 1}, RATE_mM_PER_S
                )
            ],
            [("make_R", None, [(0.0, multiplier)])],
        )
        raw = rf.with_coupling(
            raw,
            species=[rf.REGULATOR],
            couplings=[
                rf.hill_coupling(
                    "c_r",
                    "junction",
                    ["junction_0"],
                    rf.REGULATOR,
                    "hill_inhibition",
                    1e-3,
                    1.0,
                    side="first",
                )
            ],
        )
        spec = parse_spec(raw)
        _cache[multiplier] = (spec, run(spec))
    return _cache[multiplier]


def regulator_mM(spec, result, rows):
    r = list(spec.model.species_ids).index(rf.REGULATOR)
    c0 = [c.id for c in spec.model.cells].index("cell_0")
    anchor = spec.model.cells[c0].initial_amount_fmol[r]
    volume = spec.model.cells[c0].volume_pL
    return (anchor + np.asarray(result.history.amount_increment)[rows, r, c0]) / volume


@pytest.mark.parametrize("multiplier", [1.0, 0.0])
def test_the_composition_runs_and_its_factor_is_the_law(multiplier):
    spec, result = go(multiplier)
    times = np.asarray(result.times)
    rows = [int(np.flatnonzero(times == t)[0]) for t in spec.experiment.observation_times]
    x = regulator_mM(spec, result, rows)
    np.testing.assert_allclose(
        x, rf.REGULATOR_mM + multiplier * RATE_mM_PER_S * times[rows], rtol=1e-10, atol=1e-18
    )
    observed = np.asarray(result.observations.coupling_factor)[:, 0]
    np.testing.assert_allclose(observed, 1e-3 / (1e-3 + x), rtol=1e-13, atol=0)


def test_the_multiplier_moves_the_factor_and_the_step():
    spec, made = go(1.0)
    _, held = go(0.0)
    assert np.all(np.diff(np.asarray(held.observations.coupling_factor)[:, 0]) == 0)
    assert np.all(np.diff(np.asarray(made.observations.coupling_factor)[:, 0]) < 0)
    fields, _ = rf.differing(made, held)
    assert "junction_transferred" in fields
