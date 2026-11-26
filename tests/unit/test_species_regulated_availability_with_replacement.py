"""cells.operator.species_regulated_availability@1 composed with cells.operator.scheduled_cell_replacement@1 (a development run).

docs/INVENTORY_COUPLING_DESIGN.md §1.7 and §1.12 ("composes on slots it does not replace"), making
no acceptance claim. The seven-cell heredity sheet, 20 steps at 1 ms: replacement@1 replaces cell_1
at 8 ms, while D150's turnover clears R in cell_0 and the operator regulates junction_0 (cell_0 to
cell_3, a contact replacement does not touch): a Hill inhibition of R on its first side, and the
complement of a state of Na in cell_0 and cell_3 on both sides. One program; the arms are data:
* every host check passes on every row; the replacement happens (cell_1's generation is 1);
* the observed factors equal an independent evaluation of the laws at every saved row;
* junction_0's observed availability is replacement's factor (exactly 1 on a contact it does not
  form) times the operator's product, bit for bit, while cell_1's contacts show replacement's;
* switched off, the operator leaves junction_0 at its schedule and the step changes (non-vacuous).
"""

import numpy as np

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.registry.inventory_species import add_inventory_species
from validation.tissue import cell_replacement_fixtures as crfx
from validation.tissue import regulated_availability_fixtures as rf
from validation.tissue import secreted_species_fixtures as sfx

END, EVENT = 0.02, 0.008
_cache = {}


def go(enabled=1):
    if enabled not in _cache:
        raw = crfx.heredity_sheet(radius=1, disc=0, end_time=END)
        raw["experiment"]["observation_times"] = list(sfx.grid_times(END, 1e-3, 0.002))
        template = crfx.template_from_cell(raw, "cell_1", "T")
        raw = crfx.with_replacement(raw, [template], [(EVENT, "cell_1", "T", "c1_new")])
        raw = add_inventory_species(
            cs.frozen_definition(raw),
            rf.REGULATOR,
            trace_mM=rf.REGULATOR_mM,
            diffusivity_m2_per_s=rf.D_REGULATOR,
            floor_fmol=rf.FLOOR_FMOL,
        )
        raw = rf.with_coupling(
            raw,
            species=[rf.REGULATOR, "Na"],
            states=[
                rf.state(
                    "s",
                    ["cell_0", "cell_3"],
                    [("hill_activation", "Na", 12.0, 2.0)],
                    on=5.0,
                    off=1.0,
                    initial=0.2,
                )
            ],
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
                ),
                rf.coupling(
                    "c_s",
                    "junction",
                    ["junction_0"],
                    ("state", "s"),
                    "state_complement",
                    side="both",
                    basal=0.25,
                ),
            ],
            switches={"c_r": [(0.0, enabled)], "c_s": [(0.0, enabled)]},
        )
        spec = parse_spec(rf.with_turnover(raw, "cell_0", 50.0))
        _cache[enabled] = (spec, run(spec))
    return _cache[enabled]


def observed_rows(spec, result):
    times = np.asarray(result.times)
    return [int(np.flatnonzero(times == t)[0]) for t in spec.experiment.observation_times]


def test_the_composition_runs_and_its_factors_are_the_laws():
    spec, result = go()
    generation = np.asarray(result.history.generation)[-1]
    cells = [c.id for c in spec.model.cells]
    assert generation[cells.index("cell_1")] == 1 and generation.sum() == 1
    species = list(spec.model.species_ids)
    r, c0 = species.index(rf.REGULATOR), cells.index("cell_0")
    anchor = spec.model.cells[c0].initial_amount_fmol[r]
    volume = spec.model.cells[c0].volume_pL
    factors = np.asarray(result.observations.coupling_factor)
    for k, i in enumerate(observed_rows(spec, result)):
        x = (anchor + np.asarray(result.history.amount_increment)[i, r, c0]) / volume
        s = np.asarray(result.history.regulatory_state)[i]
        expected = [1e-3 / (1e-3 + x), 0.25 + 0.75 * (1.0 - s[0]), 0.25 + 0.75 * (1.0 - s[1])]
        np.testing.assert_allclose(factors[k], expected, rtol=1e-13, atol=0)


def test_junction_0_carries_both_operators_factors_bit_for_bit():
    spec, result = go()
    junctions = [j.id for j in spec.model.junctions]
    j0 = junctions.index("junction_0")
    factors = np.asarray(result.observations.coupling_factor)
    availability = np.asarray(result.observations.junction_availability)
    product = (factors[:, 0] * factors[:, 1]) * factors[:, 2]  # The declared route order.
    assert availability[:, j0].tobytes() == (1.0 * product).tobytes()
    touched = [i for i, j in enumerate(spec.model.junctions) if "cell_1" in (j.sender, j.receiver)]
    after = np.asarray(spec.experiment.observation_times) > EVENT
    assert np.all(availability[np.ix_(after, touched)] < 1.0)  # Replacement's formation factor.


def test_switched_off_the_operator_leaves_junction_0_at_its_schedule():
    spec, off = go(0)
    _, on = go(1)
    j0 = [j.id for j in spec.model.junctions].index("junction_0")
    assert np.all(np.asarray(off.observations.junction_availability)[:, j0] == 1.0)
    fields, _ = rf.differing(on, off)
    assert "junction_transferred" in fields
