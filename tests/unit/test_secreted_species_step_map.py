"""Guard: the engine's composite step is the declared scheme's linear map, to rounding (D150 v1).

The lead's review (14 November 2026): the step map's agreement with the engine is a guard, not a
judged item of the qualification protocol, since one author wrote both sides. It is a tier-2
regression guard for the landing gates, outside the protocol's Q5 (regression_guards). The
qualification's judged configuration (validation/tissue/secreted_species_qualification.py: the
held sphere on 2.5 um shells, IMEX at 1 ms and RK4 at 0.1 ms) is shortened to 500 steps per solver
and run through the runner with every host check, against the step map iterated in NumPy
(validation/tissue/secreted_species_analysis.scheme_map: the clearance's exact half-steps around
ARS(2,2,2)'s explicit stages or RK4's polynomial).

The rounding rule, fixed at that review before any judged run: max |engine - map| over shells and
records <= n_steps x eps x the scale, the largest concentration over the records. The engine's
distance from the exact discrete solution must stand far above the same bound, so the guard
resolves the scheme from the exact solution. The judged run reports the same ratio on the full
judged arms (development: 0.0055 of the bound at 4,000 IMEX steps, 0.095 at 5,000 RK4 steps).
"""

import pytest

from validation.tissue import secreted_species_analysis as analysis
from validation.tissue import secreted_species_qualification as q

CASES = (("dr2.5_dt1", 0.5, (0.25, 0.5)), ("rk4_dr2.5_dt0.1", 0.05, (0.025, 0.05)))


@pytest.mark.parametrize(("name", "end", "times"), CASES)
def test_the_engine_is_the_declared_step_map_to_rounding(name, end, times):
    arm = q.run_arm(name, end=end, times=times)
    agreement = analysis.step_map_agreement(arm)
    assert agreement["n_steps"] == 500
    assert agreement["max_abs_mM"] <= agreement["bound_mM"], agreement
    assert agreement["engine_minus_exact_over_bound"] > 1e3, agreement
