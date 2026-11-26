"""B1 and B6 of FR-3's milestone 1: cells.operator.site_occupancy@1 runs in the face-free world at rounding.

Criteria fixed before any code (/mnt/workspaces/Cells/site-occupancy-m1-20261115-01/HANDOFF.md).
The world is D150's face-free topology with the ligand S at 1e-3 mM in the cell and its node, under
ARS(2,2,2) at 1 ms, every step observed (validation/tissue/site_occupancy_fixtures). Two
populations: an outward one on the contact (binding from ecs_0) and an inward one on the cell's wall
patch (binding from the cytosol).
* Passive-only (no internalisation) and mixed (the outward population internalises at 0.5/s): the
  runner passes every host check on every accepted row, so every ledger, @3's and the operator's
  own, is within its floor and allowance (residual/allowance <= 1), the energy ledger included.
* B6, the moiety guard: R + B = S on every row to the floor, and the ligand's system total (free in
  every node + bound) changes only by what crosses the wall... here nothing: the total is conserved
  to rounding on every row.
One compile per configuration: not tier 1.
"""

import jax
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.registry.models import get_model
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import site_occupancy_fixtures as sfx

jax.config.update("jax_enable_x64", True)

END, DT = 0.02, 1e-3


def populations(k_int):
    return [
        sfx.population("out", k_int=k_int),
        sfx.population("in", patch="wall_cell_0", face="inside", k_on=2e3, k_off=0.5),
    ]


@pytest.mark.parametrize("k_int", [None, 0.5], ids=["passive_only", "mixed"])
def test_the_face_free_world_runs_at_rounding(k_int):
    spec = parse_spec(sfx.face_free_sites(populations(k_int), end=END, dt=DT))
    result = run(spec)  # Every host check on every accepted row, the energy ledger included.
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    h = result.history
    capacity = np.asarray(p.site_capacity_fmol)
    free = np.asarray(p.site_free_anchor_fmol) + np.asarray(h.site_free_increment_fmol)
    bound = np.asarray(p.site_bound_anchor_fmol) + np.asarray(h.site_bound_increment_fmol)
    assert np.max(np.abs(free + bound - capacity)) <= 1e-18  # B6, the moiety identity.
    assert np.all(bound[-1] > 0) and np.all(np.diff(bound[:, 0]) >= -1e-21)  # Binding ran.
    s = list(spec.model.species_ids).index(fx.SPECIES)
    cells = np.asarray(p.amount_reference)[s] + np.asarray(h.amount_increment)[:, s, :]
    nodes = (
        np.asarray(p.extracellular_amount_reference)[s]
        + np.asarray(h.extracellular_amount_increment)[:, s, :]
    )
    finite = ~np.asarray([c.reservoir for c in spec.model.extracellular])
    total = cells.sum(axis=1) + nodes[:, finite].sum(axis=1) + bound.sum(axis=1)
    assert np.max(np.abs(total - total[0])) <= 1e-15 * total[0]  # B6, the system total.
    if k_int is not None:
        assert np.asarray(h.site_internalised_fmol)[-1, 0] > 0
        assert np.all(np.asarray(h.site_internalised_fmol)[:, 1] == 0)
