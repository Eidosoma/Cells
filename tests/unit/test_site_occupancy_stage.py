"""B5 of FR-3's milestone 1, the runner's arm: dt L > 1 is refused at run time (§4.2).

Criteria fixed before any code (/mnt/workspaces/Cells/site-occupancy-m1-20261115-01/HANDOFF.md):
a world whose binding rate makes h max L exceed 1/2 (dt L > 1) fails the runner, and the model's
own checked step refuses the step and returns its start state bit for bit; the same world with a
slower k_on is admitted by the checked step. This file holds the runner's refusal; the checked
step's arm is test_site_occupancy_stage_step.py (split from this file for the 90 s cap). One
compile: not tier 1.
"""

import jax
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from validation.tissue import site_occupancy_fixtures as sfx

jax.config.update("jax_enable_x64", True)

DT = 1e-3


def world(k_on):
    # Free sites R ~ 8e-5 fmol in a 1 pL node: L_n = k_on R / V and L_R = k_on c; with c = 1e-3 mM
    # a k_on of 2e6 /mM/s gives dt L_R = 2.
    pops = [sfx.population("out", k_on=k_on, k_off=k_on * 1e-6)]
    return parse_spec(sfx.face_free_sites(pops, end=0.005, dt=DT))


def test_dt_L_above_one_is_refused_at_run_time():
    with pytest.raises(NumericalError):
        run(world(2e6))
