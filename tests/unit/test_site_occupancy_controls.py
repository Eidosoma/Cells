"""B2 of FR-3's milestone 1: negative controls that must fail the runner's host checks.

Criteria fixed before any code (/mnt/workspaces/Cells/site-occupancy-m1-20261115-01/HANDOFF.md).
In the mixed face-free world of test_site_occupancy_runs.py, each control corrupts one booking the
host checks read, test-only (monkeypatch of the operator's host-side ledger methods, xp = NumPy):
* the site free-energy term dropped from the energy ledger;
* a misbooked move: the operator's material term on @3's rows scaled by 1 + 1e-6;
* the heat's sign flipped in the energy ledger.
Each must fail the runner (NumericalError), while the same world without the corruption passes
(test_site_occupancy_runs.py). One compile per control: not tier 1.
"""

import jax
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.operators import site_occupancy as so
from validation.tissue import site_occupancy_fixtures as sfx

jax.config.update("jax_enable_x64", True)

END, DT = 0.01, 1e-3
ORIGINAL = so.SiteOccupancy.ledger_terms


def world():
    pops = [
        sfx.population("out", k_int=0.5),
        sfx.population("in", patch="wall_cell_0", face="inside", k_on=2e3, k_off=0.5),
    ]
    return parse_spec(sfx.face_free_sites(pops, end=END, dt=DT))


def dropped_free_energy(self, result, row, p, *, xp):
    result, own = ORIGINAL(self, result, row, p, xp=xp)
    if xp is np:
        energy, _ = so.site_energy(row, p, xp=xp)
        result["energy"] = result["energy"] - energy
    return result, own


def misbooked_move(self, result, row, p, *, xp):
    if xp is np:
        local, outside = so.material_terms(
            row, p, result["local"].shape, result["outside"].shape, xp=xp
        )
        result["local"] = result["local"] + 1e-6 * local
        result["outside"] = result["outside"] + 1e-6 * outside
    return ORIGINAL(self, result, row, p, xp=xp)


def flipped_heat(self, result, row, p, *, xp):
    result, own = ORIGINAL(self, result, row, p, xp=xp)
    if xp is np:
        heat = xp.sum(row.site_dissipated_energy_pJ) + xp.sum(row.site_outside_dissipated_energy_pJ)
        result["energy"] = result["energy"] - 2.0 * heat
    return result, own


@pytest.mark.parametrize(
    "corrupt", [dropped_free_energy, misbooked_move, flipped_heat], ids=lambda f: f.__name__
)
def test_a_corrupted_booking_fails_the_host_checks(corrupt, monkeypatch):
    monkeypatch.setattr(so.SiteOccupancy, "ledger_terms", corrupt)
    with pytest.raises(NumericalError):
        run(world())
