"""FR-5's source kinds through the engine and the routing door (the FR-4/FR-5 note's §16; INNER
§7.4 (l), (n)), on FR-4's development world at 1 ms, recorded every step, on the host path.

One world declares, beside FR-4's kinds:
- `damage_0` on the bounding patch at d = 0.37, unscheduled (so held), and `acid_hi`, a condition
  whose f is exactly 1 (pH50 30); FR-4's proton leak is routed through both, so its multiplier is
  0.37 x 1 (a left fold) at every stage;
- `damage_1` on the plasma patch, which no route reads, under `damage_controls` schedules that
  switch on the step grid as FR-5's arms do: off, injury alone, both, then resealing alone;
- `acid_mid`, a condition near the lumen's pH (pH50 7.19), which no route reads.
Shown:
- damage_1's d at every record equals the piecewise closed form within 8(k + 1) eps (exact at every
  step's end, across the breakpoints), and damage_0's d stays 0.37 exactly;
- acid_mid's readout is f of the observed row's read, within 1e-10 of f of B4's pH readout, and
  acid_hi's is exactly 1;
- the door end to end: every FR-4 record equals, to rounding, the world without the source kinds
  whose leak has 0.37 times the permeability.
"""

import copy
import math

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.laws.reactions import ph_condition as phc
from validation.compartment_ph_engine import definitions as defs

STEPS = 40
DT = 1e-3
HELD_D = 0.37
D0, K_INJ, K_RES = 0.25, 1.0, 0.05
INJURY_STEPS = (10, 33)  # u_inj = 1 on steps [10, 33)
RESEALING_FROM = 25  # u_res = 1 from step 25: both on over [25, 33), resealing alone after.
PH50_MID, SLOPE = 7.19, 4.0


def recorded(definition):
    """The first STEPS steps, recorded at every step (the development world)."""
    d = copy.deepcopy(definition)
    d["experiment"]["end_time"] = STEPS * DT
    d["experiment"]["observation_times"] = [k * DT for k in range(STEPS + 1)]
    d["execution"]["max_steps"] = STEPS + 8
    return defs.development_world(d)


def with_sources(definition):
    d = copy.deepcopy(definition)
    entry = dict(law="cells.damage.bounding_patch_damage@1", injury_rate_per_s=K_INJ,
                 resealing_rate_per_s=K_RES)
    d["model"]["patch_damage"] = [dict(entry, id="damage_0", patch=defs.BOUNDING,
                                       initial_damage=HELD_D),
                                  dict(entry, id="damage_1", patch=defs.PLASMA, initial_damage=D0)]
    condition = dict(node=defs.LUMEN, law="cells.transfer_factor.ph_conditioned_factor@1", slope=SLOPE)
    d["model"]["ph_conditions"] = [dict(condition, id="acid_hi", ph50=30.0),
                                   dict(condition, id="acid_mid", ph50=PH50_MID)]
    (leak,) = d["model"]["passive_routes"]
    leak["factors"] = ["damage_0", "acid_hi"]
    a, b = INJURY_STEPS
    d["experiment"]["damage_controls"] = [dict(
        damage_id="damage_1",
        injury=[dict(time=0.0, value=0.0), dict(time=a * DT, value=1.0),
                dict(time=b * DT, value=0.0)],
        resealing=[dict(time=0.0, value=0.0), dict(time=RESEALING_FROM * DT, value=1.0)])]
    return d


def scaled_leak(definition, factor):
    d = copy.deepcopy(definition)
    (leak,) = d["model"]["passive_routes"]
    leak["permeability_m_per_s"] *= factor
    return d


def piecewise_closed_form():
    """damage_1's d at every step end, from the closed form on each constant piece."""
    d, out = D0, [D0]
    for k in range(STEPS):
        a = K_INJ if INJURY_STEPS[0] <= k < INJURY_STEPS[1] else 0.0
        b = K_RES if k >= RESEALING_FROM else 0.0
        if a + b > 0:
            eq = a / (a + b)
            d = eq + (d - eq) * math.exp(-(a + b) * DT)
        out.append(d)
    return out


def test_the_source_kinds_run_exactly_and_the_door_scales_the_leak():
    base = recorded(defs.fr4_world())
    spec = parse_spec(with_sources(base))
    obs = run(spec).observations
    ref = run(parse_spec(scaled_leak(base, HELD_D))).observations
    assert len(obs.times) == STEPS + 1 and np.array_equal(np.asarray(obs.times),
                                                          np.asarray(ref.times))
    membranes = [m.id for m in spec.model.membranes]
    bounding, plasma = membranes.index(defs.BOUNDING), membranes.index(defs.PLASMA)
    eps = np.finfo(float).eps
    d = np.asarray(obs.patch_damage)
    for k, exact in enumerate(piecewise_closed_form()):  # Exact at every step's end.
        assert abs(float(d[k, plasma]) - exact) <= 8 * (k + 1) * eps, k
    assert np.all(d[:, bounding] == HELD_D)
    assert d[INJURY_STEPS[0], plasma] == D0 and d[INJURY_STEPS[1], plasma] > D0
    assert d[-1, plasma] < d[INJURY_STEPS[1], plasma]  # Resealing alone closes it.
    # The conditions: f on the observed rows' read, against B4's pH readout.
    lumen = len(spec.model.cells) + [o.id for o in spec.model.extracellular].index(defs.LUMEN)
    f = np.asarray(obs.ph_condition_factor)
    assert np.all(f[:, 0] == 1.0)
    expected = np.asarray(phc.factor(np.asarray(obs.pH)[:, lumen], PH50_MID, SLOPE, xp=np))
    assert np.max(np.abs(f[:, 1] - expected)) <= 1e-10
    assert 0.05 < f[:, 1].min() and f[:, 1].max() < 0.95 and f[-1, 1] != f[0, 1]
    # The door end to end: the leak routed through d = 0.37 and f = 1 is the leak of 0.37 P.
    moved = np.asarray(ref.passive_transferred)
    assert np.max(np.abs(moved)) > 0
    for name in ("pH", "amount", "extracellular_amount", "membrane_voltage_V", "transporter_cycles",
                 "passive_transferred", "passive_dissipated_energy_pJ",
                 "transporter_dissipated_energy_pJ", "membrane_dissipated_energy_pJ"):
        a, b = np.asarray(getattr(obs, name)), np.asarray(getattr(ref, name))
        scale = max(float(np.max(np.abs(b))), 1e-300)
        assert np.max(np.abs(a - b)) <= 1e-12 * scale, name
