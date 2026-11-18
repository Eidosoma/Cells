"""Door S's integration case: a bath dose, uptake, an owned compartment, then a reaction (T4).

docs/SCOPED_COMPOSITION_DESIGN.md §5 and §7 (D176): the delivery world of
validation/tissue/delivery_fixtures under ARS(2,2,2) at 1 ms, every step observed, with D152's
reactions in FR-1's compartment beside FR-10's dose, which door S admits.
* Every host check passes on every row, so every ledger of the inner model and of each operator
  closes within its floor and allowance: material across all four, by D150's and D152's own
  records, and the energy ledger.
* The dose applies at the bath at its time; the cargo reaches the node, the cell and the
  compartment; the reaction makes P in the compartment.
* T4: on every row, the view equals the bound layout bitwise everywhere but the bath's slot of
  extracellular_amount_reference, where it is the held content.
One compile: not tier 1.
"""

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.models import pump_composite_adapter as adapter
from cells.registry.models import get_model
from validation.tissue import delivery_fixtures as dfx

jax.config.update("jax_enable_x64", True)

ANCHOR = "extracellular_amount_reference"


def test_the_delivery_world_runs_and_its_view_changes_only_the_bath():
    spec = parse_spec(dfx.delivery_world())
    result = run(spec)  # Every host check on every accepted row.
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    h, times = result.history, np.asarray(result.times)
    ids, outside = list(spec.model.species_ids), [c.id for c in spec.model.extracellular]
    s, product = ids.index("S"), ids.index("P")
    bath, comp, node = (outside.index(k) for k in (dfx.BATH, dfx.COMPARTMENT, dfx.NODE))
    held = np.asarray(h.bath_held_amount_fmol)[:, s, bath]
    # The event acts in the step that starts at its time, so the first dosed row is the next one.
    before, after = times <= dfx.DOSE_TIME + 1e-12, times > dfx.DOSE_TIME + 1e-12
    declared = np.asarray(p.extracellular_amount_reference)
    assert np.all(held[before] == declared[s, bath])
    assert np.allclose(held[after], dfx.RATIO * declared[s, bath], rtol=1e-12)
    amounts = declared[None] + np.asarray(h.extracellular_amount_increment)
    assert amounts[-1, s, node] > amounts[0, s, node]  # The dose reached the node.
    assert amounts[-1, s, comp] > amounts[0, s, comp]  # Loading reached the compartment.
    assert amounts[-1, product, comp] > amounts[0, product, comp]  # The reaction ran there.
    bound = adapter.inner_layout(p)
    for i in range(len(times)):
        row = model.STATE_TYPE(*(np.asarray(getattr(h, k))[i] for k in model.STATE_TYPE._fields))
        view = model.view(p, row, xp=np)
        for name in adapter.VIEW_FIELDS:
            got, want = np.asarray(getattr(view, name)), np.asarray(getattr(bound, name))
            if name == ANCHOR:
                assert got[:, bath].tobytes() == held_row(h, i, bath).tobytes(), i
                got, want = np.delete(got, bath, axis=1), np.delete(want, bath, axis=1)
            assert got.tobytes() == want.tobytes(), (i, name)


def held_row(h, i, bath):
    return np.asarray(h.bath_held_amount_fmol)[i][:, bath]
