"""cells.operator.species_regulated_availability@1: the A4 and A5 worlds match their references at the start.

docs/INVENTORY_COUPLING_DESIGN.md §9 (A4, A5). The engine's definitions that
validation/tissue/regulated_availability_references builds from a reference World start where the
reference starts, with the factors the laws give there. The engine's side is host-side (NumPy, no
compile); the reference is validation/coupling, used through its documented API
(validation/coupling/REFERENCES_USAGE.md) only:
* A4 (R-feedback), relaxed: the cells' amounts and states at 0 are the reference's, the contact's
  gate is held at 1, and the operator's route factors at the bound state multiply to the
  reference's route factor just after 0 (the state's complement with its basal level, both sides);
* A5 (R-cell): likewise, with the Hill inhibition's factor at X's anchor.
The dt studies are validation/tissue/regulated_availability_dt_study (development and record runs
in the milestone-3 evidence).
"""

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.operators import species_regulated_availability as sra
from cells.registry.models import get_model
from validation.coupling import cells_reference as rc
from validation.tissue import regulated_availability_references as rr

END = 1.0  # The A5 regulator's schedule changes at 0.2 and 0.5 s lie inside it.


def matched(make):
    world = make()
    reference = rc.simulate(world, 0.01, record=(0.01,))
    initial = {
        c: (reference.initial[c]["V"], reference.initial[c]["background_fmol"]) for c in world.cells
    }
    raw = rr.engine_definition(world, dt=1e-3, end=END, times=[0.0, END], initial=initial)
    spec = parse_spec(raw)
    state, p = get_model(spec.model).initial_values(spec)
    return world, reference, spec, state, p


@pytest.fixture(scope="module", params=["A4", "A5"])
def case(request):
    make = rr.relaxed(rr.feedback_world, 0.05) if request.param == "A4" else rr.cell_world
    return matched(make)


def test_the_engine_starts_where_the_reference_starts(case):
    world, reference, spec, state, p = case
    cells = [c.id for c in spec.model.cells]
    assert cells == list(world.cells)
    for i, c in enumerate(cells):
        amounts = np.asarray(p.amount_reference)[:3, i] + np.asarray(state.amount_increment)[:3, i]
        expected = np.asarray(world.cells[c].mM) * world.cells[c].volume_pL
        np.testing.assert_allclose(amounts, expected, rtol=1e-14, atol=0)
    if world.contacts:
        assert np.all(np.asarray(state.junction_gate) == 1.0)
    if world.states:
        slots = list(reference.slots)
        declared = [(name, c) for name, s in world.states.items() for c in s.cells]
        assert [tuple(s) for s in slots] == declared
        initial = world.states["s1"].initial
        assert list(np.asarray(state.regulatory_state)) == [initial[c] for _, c in slots]


def test_the_factors_at_the_start_are_the_references(case):
    """The engine's routes multiply to the reference's route factor just after 0, per coupling."""
    world, reference, spec, state, p = case
    engine = np.asarray(sra.route_factors(state, p, xp=np))
    early = reference.observe(1e-9)
    k = 0
    for name, c in world.couplings.items():
        width = 2 if c.side == "both" else 1
        product = float(np.prod(engine[k : k + width]))
        expected = early["routes"][(name, c.target)]["F"]
        np.testing.assert_allclose(product, expected, rtol=1e-6, atol=0)
        k += width
    assert k == engine.shape[0]
