"""species_regulated_availability@1: a compiled run of every part.

docs/INVENTORY_COUPLING_DESIGN.md §1. 20 steps of the seven-cell heredity sheet with D150's turnover
clearing R in cell_0 (a moving, impermeant source read at once: a Hill inhibition on junction_0's
first side) and a regulatory state of Na in cell_0 and cell_3 (its complement, with basal 1/4, on
junction_0's two sides) with a crossing level and one write. Every host check of every row passes
(the runner), the observed factors equal an independent evaluation of the laws at each saved row,
and the state, its write, its crossing record and the step counter behave as declared.
"""

import numpy as np

from cells.core.runner import run
from cells.core.specs import parse_spec
from validation.tissue import regulated_availability_fixtures as rf


def world():
    raw = rf.with_coupling(
        rf.sheet(end=0.02),
        species=["R", "Na"],
        states=[
            rf.state(
                "s", ["cell_0", "cell_3"], [("hill_activation", "Na", 12.0, 2.0)],
                on=5.0, off=1.0, initial=0.2, level=0.5,
            )
        ],
        couplings=[
            rf.hill_coupling("c_r", "junction", ["junction_0"], "R", "hill_inhibition", 1e-3, 1.0, side="first"),
            rf.coupling(
                "c_s", "junction", ["junction_0"], ("state", "s"), "state_complement",
                side="both", basal=0.25,
            ),
        ],
        writes=[("s", "cell_3", 0.008, 0.9)],
    )
    return rf.with_turnover(raw, "cell_0", 50.0)


def test_a_run_of_every_part():
    spec = parse_spec(world())
    result = run(spec)
    history, obs = result.history, result.observations
    species = list(spec.model.species_ids)
    cells = [c.id for c in spec.model.cells]
    r_row, c0 = species.index("R"), cells.index("cell_0")
    volume = spec.model.cells[c0].volume_pL
    anchor = spec.model.cells[c0].initial_amount_fmol[r_row]
    observed = list(spec.experiment.observation_times)
    assert len(observed) >= 4
    for k, t in enumerate(observed):
        i = int(np.flatnonzero(np.asarray(result.times) == t)[0])
        x = (anchor + np.asarray(history.amount_increment)[i, r_row, c0]) / volume
        s = np.asarray(history.regulatory_state)[i]
        expected = [1e-3 / (1e-3 + x), 0.25 + 0.75 * (1.0 - s[0]), 0.25 + 0.75 * (1.0 - s[1])]
        np.testing.assert_allclose(np.asarray(obs.coupling_factor)[k], expected, rtol=1e-13, atol=0)
    r_amount = anchor + np.asarray(history.amount_increment)[:, r_row, c0]
    assert np.all(np.diff(r_amount) < 0)  # Turnover clears R; the operator never writes it.
    s_final = np.asarray(history.regulatory_state)[-1]
    assert np.all((s_final >= 0) & (s_final <= 1))
    assert list(np.asarray(history.regulatory_writes_applied)[-1]) == [0, 1]
    # The write at 8 ms lifts (s, cell_3) to 0.9 at the start of the step leaving 8 ms; the event
    # map of the next step start (9 ms, count 9) records the crossing. (s, cell_0) stays below.
    assert list(np.asarray(history.regulatory_crossing_step)[-1]) == [-1, 9]
    assert int(np.asarray(history.coupling_step_count)[-1, 0]) == len(result.times) - 1
