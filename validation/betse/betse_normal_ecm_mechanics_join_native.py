"""Native source phases at the reached ECM/steady-mechanics boundary.

The complete unchanged ECM native history supplies current post-dispatch rows
and the previous field. Unchanged mechanics source bodies consume those inputs.
Static read/write auditing is required for the absent feedback into material
and fields. This is not a monolithic native solver or a seeded-geometry claim.
"""

import copy

import numpy as np

from validation.betse import betse_mechanics_join_native as mechanics
from validation.betse import betse_normal_ecm_field_join_native as field
from validation.betse import betse_normal_ecm_mechanics_join_boundaries as boundaries


def evaluate(inputs):
    rng_before = copy.deepcopy(np.random.get_state())
    fields = field.evaluate(inputs["field_inputs"])
    incoming = boundaries.native_inputs(inputs, fields)
    mechanical = mechanics.evaluate(incoming) if incoming["steps"] else None
    rng_after = copy.deepcopy(np.random.get_state())
    unchanged = (
        rng_before[0] == rng_after[0]
        and np.array_equal(rng_before[1], rng_after[1])
        and rng_before[2:] == rng_after[2:]
    )
    return dict(
        ionic_field=fields,
        mechanics_inputs=incoming,
        mechanics=mechanical,
        RNG_before=rng_before,
        RNG_after=rng_after,
        RNG_unchanged=bool(unchanged),
        native_phase_parent_conditioned=True,
        native_monolithic_coupled_solver_executed=False,
        native_physical_seed_or_display_executed=False,
        mechanics_ionic_field_write_sets_disjoint_under_disabled_flow_and_sampling=True,
        complete_source_condition_met=fields["failure"] is None
        and mechanical is not None
        and mechanical["failure"] is None,
    )
