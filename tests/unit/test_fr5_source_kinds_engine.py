"""FR-5's source kinds through the engine (the FR-4/FR-5 note's §16): FR-4's development world with
cells.patch_damage@1 and cells.ph_condition@1 declared, on the host path, recorded every step.

Until the core's gap-6 schedules land, the damage's controls come from a test-local variant whose
`control_values` gives piecewise-constant schedules with breakpoints on the step grid, as FR-5's
arms do (a planted kind under `tests.`, on a test-local registry, §7.4 (k)); every other hook is
the built-in kind's. The runner samples the controls at each step's start. Shown:
- d at every record equals the piecewise closed form to rounding (exact at every step's end,
  across the breakpoints): unchanged before the injury, then injury alone, both, and resealing
  alone, each piece d_eq + (d_k - d_eq) e^(-(a+b)(t - t_k)); the integrated hazards are the
  integrals of a and b;
- the condition's readout is f of the observed row's read, which agrees with B4's pH readout;
- the two kinds move nothing: every FR-4 record (pH, V_b, every amount, the pump's cycles and the
  heats) is bitwise the world's without them.
"""

import copy
import dataclasses
import math

import numpy as np

from cells.core import kind_registry
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models.inner_kinds import patch_damage as damage
from cells.processes import ph_condition as phc
from validation.compartment_ph_engine import definitions as defs

STEPS = 40
D0, K_INJ, K_RES = 0.25, 1.0, 0.05
PH50, SLOPE = 7.19, 4.0  # Near the start's pH 7.2, so f is mid-range and moves.


def recorded(definition):
    """The first STEPS steps, recorded at every step."""
    d = copy.deepcopy(definition)
    dt = d["execution"]["dt"]
    d["experiment"]["end_time"] = STEPS * dt
    d["experiment"]["observation_times"] = [k * dt for k in range(STEPS + 1)]
    d["execution"]["max_steps"] = STEPS + 8
    return defs.development_world(d)


def with_sources(definition):
    d = copy.deepcopy(definition)
    d["model"]["patch_damage"] = [dict(id="damage_0", patch=defs.BOUNDING,
                                       law="bounding_patch_damage@1", initial_damage=D0,
                                       injury_rate_per_s=K_INJ, resealing_rate_per_s=K_RES)]
    d["model"]["ph_conditions"] = [dict(id="acid_0", node=defs.LUMEN,
                                        law="ph_conditioned_factor@1", ph50=PH50, slope=SLOPE)]
    return d


INJURY_STEPS = (10, 33)  # u_inj = 1 on steps [10, 33)
RESEALING_FROM = 25  # u_res = 1 from step 25: both on over [25, 33), resealing alone after.


def schedules(u_inj_on, u_res_on, times, dt):
    """The test's schedules at step starts, from step indices (breakpoints on the grid)."""
    steps = np.rint(np.asarray(times) / dt).astype(int)
    injury = ((steps >= u_inj_on[0]) & (steps < u_inj_on[1])).astype(float)
    resealing = (steps >= u_res_on).astype(float)
    return injury, resealing


def piecewise_schedules(spec, declaration, times):
    """u_inj and u_res on every declared patch: off, injury, both, then resealing alone."""
    k = spec.execution.membrane_capacity
    present = np.zeros(k)
    patches = [p.id for p in spec.model.membranes]
    for d in declaration:
        present[patches.index(d.patch)] = 1.0
    injury, resealing = schedules(INJURY_STEPS, RESEALING_FROM, times, spec.execution.dt)
    return dict(patch_damage_injury=injury[:, None] * present[None, :],
                patch_damage_resealing=resealing[:, None] * present[None, :])


def piecewise_closed_form(dt):
    """d and the hazards at every step end, from the closed form on each constant piece."""
    d, a_sum, b_sum, out = D0, 0.0, 0.0, [(D0, 0.0, 0.0)]
    injury, resealing = schedules(INJURY_STEPS, RESEALING_FROM, [k * dt for k in range(STEPS)], dt)
    for k in range(STEPS):  # Each step lies in one piece; its closed form from the step's start.
        a, b = K_INJ * injury[k], K_RES * resealing[k]
        if a + b > 0:
            eq = a / (a + b)
            d = eq + (d - eq) * math.exp(-(a + b) * dt)
        a_sum, b_sum = a_sum + a * dt, b_sum + b * dt
        out.append((d, a_sum, b_sum))
    return out


def registry():
    planted = dataclasses.replace(damage.PATCH_DAMAGE, kind_id="tests.patch_damage_piecewise@1",
                                  control_values=piecewise_schedules)
    out = kind_registry.KindRegistry()
    for kind in kind_registry.active().model_keys().values():
        out.register(planted if kind is damage.PATCH_DAMAGE else kind)
    return out


def test_the_source_kinds_run_exactly_and_move_nothing():
    base = recorded(defs.fr4_world())
    with kind_registry.scope(registry()):
        spec = parse_spec(with_sources(base))
        result = run(spec)
    plain = run(parse_spec(base))
    obs, ref = result.observations, plain.observations
    times = np.asarray(obs.times)
    assert len(times) == STEPS + 1 and np.array_equal(times, np.asarray(ref.times))
    bounding = [m.id for m in spec.model.membranes].index(defs.BOUNDING)
    eps = np.finfo(float).eps
    expected = piecewise_closed_form(spec.execution.dt)
    for k, (d, a_sum, b_sum) in enumerate(expected):  # d exact at every step's end.
        assert abs(float(obs.patch_damage[k, bounding]) - d) <= 8 * (k + 1) * eps, k
        assert abs(float(obs.patch_damage_injury_hazard[k, bounding]) - a_sum) <= 4 * (
            k + 1) * eps, k
        assert abs(float(obs.patch_damage_resealing_hazard[k, bounding]) - b_sum) <= 4 * (
            k + 1) * eps, k
    d = np.asarray(obs.patch_damage)[:, bounding]
    assert d[INJURY_STEPS[0]] == D0 and d[INJURY_STEPS[1]] > d[INJURY_STEPS[0]] > 0  # Opened.
    assert d[-1] < d[INJURY_STEPS[1]]  # Resealing alone closes it.
    assert np.count_nonzero(np.asarray(obs.patch_damage)[:, np.arange(
        len(spec.model.membranes)) != bounding]) == 0
    # The condition's f on the observed rows' read, against B4's pH readout.
    lumen = len(spec.model.cells) + [o.id for o in spec.model.extracellular].index(defs.LUMEN)
    f = np.asarray(obs.ph_condition_factor)[:, 0]
    expected = np.asarray(phc.factor(np.asarray(obs.pH)[:, lumen], PH50, SLOPE, xp=np))
    assert np.max(np.abs(f - expected)) <= 1e-10
    assert 0.05 < f.min() and f.max() < 0.95 and f[-1] != f[0]
    # They move nothing: FR-4's records are bitwise the world's without them.
    for name in ("pH", "amount", "extracellular_amount", "membrane_voltage_V", "transporter_cycles",
                 "passive_dissipated_energy_pJ", "transporter_dissipated_energy_pJ",
                 "membrane_dissipated_energy_pJ"):
        assert np.array_equal(np.asarray(getattr(obs, name)), np.asarray(getattr(ref, name))), name
