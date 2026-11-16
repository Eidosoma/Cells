"""FR-5's source kinds through the engine (the FR-4/FR-5 note's §16): FR-4's development world with
cells.patch_damage@1 and cells.ph_condition@1 declared, on the host path, recorded every step.

Until the core's gap-6 schedules land, the damage's controls come from a test-local variant whose
`control_values` holds u_inj = u_res = 1 throughout (a planted kind under `tests.`, on a test-local
registry, §7.4 (k)); every other hook is the built-in kind's. Shown:
- d at every record equals the closed form d_eq + (d0 - d_eq) e^(-(a+b) t) to rounding (exact at
  every step's end), and the integrated hazards are a t and b t;
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


def constant_schedules(spec, declaration, times):
    """u_inj = u_res = 1 on every declared patch, at every step (the test's schedule)."""
    k = spec.execution.membrane_capacity
    present = np.zeros(k)
    patches = [p.id for p in spec.model.membranes]
    for d in declaration:
        present[patches.index(d.patch)] = 1.0
    rows = np.tile(present, (len(times), 1))
    return dict(patch_damage_injury=rows, patch_damage_resealing=rows.copy())


def registry():
    planted = dataclasses.replace(damage.PATCH_DAMAGE, kind_id="tests.patch_damage_constant@1",
                                  control_values=constant_schedules)
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
    a, b = K_INJ, K_RES
    eq = a / (a + b)
    for k, t in enumerate(times):  # d exact at every step's end.
        exact = eq + (D0 - eq) * math.exp(-(a + b) * float(t))
        assert abs(float(obs.patch_damage[k, bounding]) - exact) <= 8 * (k + 1) * eps
        assert abs(float(obs.patch_damage_injury_hazard[k, bounding]) - a * t) <= 4 * (k + 1) * eps
        assert abs(float(obs.patch_damage_resealing_hazard[k, bounding]) - b * t) <= 4 * (
            k + 1) * eps
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
