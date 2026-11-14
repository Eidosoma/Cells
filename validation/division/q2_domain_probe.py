"""Q2's sampling rule against the engine's own checks (development; S5 design §8.3, Q2).

For Q2's two random-state samplers, 200 draws on each neighbour world (q2_rops_comparison's
seed and worlds):
* the in-domain sampler (q2_rops_comparison.perturbed, the lead's ruling);
* the disclosed out-of-domain sampler of comparisons-s5a9 (6c2b118): increments within 1e-3 of
  each amount, not compensated, on the same route-restricted histories, so only the content
  differs.
Reported per sampler: how many draws pass the composite's domain check (@3's at the view and
each operator's), its control domain check at the event's control (adding each operator's
control check and the readouts' validity, where the contact gate law's |V| <= 0.12 V domain
sits), and Q2's charge bound; the largest |V| of a live patch; the largest |Q / Q_declared| of
a live cell.

Usage: python -m validation.division.q2_domain_probe OUTPUT_JSON (NumPy only, seconds).
"""

import json
import sys

import jax
import numpy as np

from cells.models import pump_composite_adapter as adapter
from cells.processes.electrochemistry import CHARGE_PER_FMOL
from tests import partition_fixtures as fx
from validation.division import q2_rops_comparison as q2


def old_sampler(world, rng):
    """6c2b118's increments (within 1e-3 of each amount, not compensated), on the current
    sampler's route-restricted histories, so only the content differs."""
    state = q2.perturbed(world, rng)
    cells = [world.cells.index(c) for c in ("cell_0", "cell_1")]
    amounts = np.asarray(world.p.amount_reference)[:, cells]
    delta = np.array(state.amount_increment, copy=True)
    delta[:, cells] = amounts * rng.uniform(-1e-3, 1e-3, amounts.shape)
    return state._replace(amount_increment=delta)


def measure(world, state):
    p = world.p
    values = fx.cs.control_values(world.spec, [fx.EVENT])
    control = world.model.CONTROL_TYPE(*(np.asarray(x[0]) for x in values))
    domain = bool(world.model.domain_valid(state, p, p.active, xp=np))
    with np.errstate(all="ignore"):
        full = bool(world.model.domain_valid.with_control(state, control, p, p.active, xp=np))
    _, bounded = q2.admitted(world, state, fx.EVENT)
    q = world.view(state)
    phi = adapter.node_potentials(state, q, xp=np)
    n = len(world.cells)
    live = np.flatnonzero(np.asarray(q.membrane_active))
    v = [phi[int(p.membrane_cell[k])] - phi[n + int(p.membrane_outside[k])] for k in live]
    z = np.ravel(p.valence)
    cells = np.flatnonzero(np.asarray(q.active))
    charge = np.asarray(q.initial_cell_charge_C)[cells] + CHARGE_PER_FMOL * np.sum(
        z[:, None] * np.asarray(state.amount_increment)[:, cells], axis=0
    )
    ratio = np.abs(charge / np.asarray(p.initial_cell_charge_C)[cells])
    return domain, full, float(np.max(np.abs(v))), float(np.max(ratio)), bounded


def main(output):
    jax.config.update("jax_enable_x64", True)
    carriers = {"Na": 0.3, "K": 0.5, "M": 0.2}
    worlds = {
        "symmetric": fx.divided(neighbour=True),
        "asymmetric": fx.divided(neighbour=True, f=0.75, area_fraction=0.6, carriers=carriers),
    }
    report = {}
    for label, raw in worlds.items():
        world = q2.Bound(raw)
        samplers = (("in-domain (5234ba8)", q2.perturbed), ("old (6c2b118)", old_sampler))
        for name, sampler in samplers:
            rng = np.random.default_rng(20261113)
            rows = [measure(world, sampler(world, rng)) for _ in range(200)]
            report[f"{label}, {name}"] = dict(
                domain_pass=sum(r[0] for r in rows),
                control_domain_pass=sum(r[1] for r in rows),
                max_abs_V=max(r[2] for r in rows),
                max_charge_over_declared=max(r[3] for r in rows),
                charge_bound_pass=sum(r[4] for r in rows),
            )
            print(label, name, report[f"{label}, {name}"], flush=True)
    with open(output, "w") as f:
        json.dump(report, f, indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
