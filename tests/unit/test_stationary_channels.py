"""stationary_continuation_analysis@1 on a resolved_pump_tissue@3 cell with channels.

The MG0b cell (validation/morphogenesis/mg0b_domain_wall.py: the heredity cell
with NaV1.2 availability 0.4 and a Na-leak control population) at frozen
composition. Fast mode finds its three I-V states with H and D stable and U
unstable, equal to the independent reduced model (mg0b_theory, numpy only) to
rounding, and continuation in the control's availability locates both edges
of the bistable window, again equal to the reduced model's directly solved
folds. Composition and u_M are the MG0b theory record's (dev-04 theory.json).
"""

import jax
import numpy as np
import pytest

from cells.analysis import continuation as cont
from cells.analysis import stationary as sa
from cells.core.specs import parse_spec
from validation.morphogenesis import mg0b_domain_wall as wall
from validation.morphogenesis import mg0b_theory as theory
from validation.stationary import reduced

# /mnt/workspaces/Cells/morphogenesis-mg0-20261109-01/dev-04-mg0b/theory.json
U_MAXWELL = 0.5640141230484589
COMPOSITION = dict(Na=8.600146455184671, K=141.50868488470016, M=15.122218545605358)


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def world(vm):
    c = COMPOSITION
    return parse_spec(
        wall.chain_definition(
            1,
            state=(vm, c["Na"], c["K"], c["M"]),
            end_time=1.0,
            observation_times=[0.0, 1.0],
            control=((0.0, U_MAXWELL),),
            junction_m_s=0.0,
        )
    )


@pytest.fixture(scope="module")
def fast():
    p = wall.cell_parameters()
    states = theory.fast_states(p, COMPOSITION, U_MAXWELL)
    spec = world(states[0])
    q = sa.parameter(spec, "channel_availability", ["ctrl_0"])
    return sa.problem(spec, mode="fast", parameter=q), p, states


def test_fast_states_and_stability(fast):
    pb, p, states = fast
    assert pb.parameter.base == U_MAXWELL and not pb.reduction().laws
    expected = ("stable", "unstable", "stable")
    for v, kind in zip(states, expected, strict=True):
        u0 = pb.coordinates(*pb.model.initial_values(world(v)))
        solution = sa.newton(pb, u0)
        assert solution.converged and solution.error_estimate < 1e-12
        voltage = sa.describe(pb, solution.u)["membrane_voltage_V"]["membrane_0"]
        assert voltage == pytest.approx(v, abs=1e-12)
        stab = sa.stability(pb, solution.u)
        assert stab["classification"] == kind
        assert stab["unstable_count"] == (1 if kind == "unstable" else 0)


def test_continuation_finds_the_window(fast):
    pb, p, _ = fast
    diagram = cont.continue_branch(
        pb, pb.anchor, theta_start=U_MAXWELL, step=0.01, max_step=0.02, bounds=(0.0, 1.0)
    )
    assert diagram["termination"] == "parameter_bound"
    folds = sorted(s["parameter_value"] for s in diagram["special_points"] if s["kind"] == "fold")
    assert len(folds) == 2
    c = COMPOSITION
    lower = theory.fast_states(p, c, folds[0] + 0.002)
    upper = theory.fast_states(p, c, folds[1] - 0.002)
    expected = [
        reduced.fold(p, c, (folds[0] - 0.004, folds[0] + 0.004), (lower[1], lower[2]))[0],
        reduced.fold(p, c, (folds[1] - 0.004, folds[1] + 0.004), (upper[0], upper[1]))[0],
    ]
    np.testing.assert_allclose(folds, expected, rtol=0, atol=1e-9)
    stable = [pt["stable"] for pt in diagram["points"]]
    assert stable[0] and stable[-1] and not all(stable)
