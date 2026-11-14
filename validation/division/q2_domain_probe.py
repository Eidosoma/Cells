"""Q2's sampling rule against the engine's own checks (development; S5 design §8.3, Q2).

On each of Q2's two neighbour worlds (q2_rops_comparison's seed and worlds), 200 draws per
sampler:
* the disclosed out-of-domain sampler of comparisons-s5a9 (6c2b118): increments within 1e-3 of
  each amount, not compensated, on the current sampler's route-restricted histories, so only
  the content differs;
* q2_rops_comparison.perturbed at net-charge spreads SPREADS (fractions of each cell's declared
  charge; 0.1 is Q2's sampler).
Reported per sampler:
* how many draws pass the composite's domain check (@3's at the view and each operator's);
* how many pass its control domain check at the event's control, which adds each operator's
  control check and the readouts' validity; and how many draws have a live patch voltage
  outside the channel gate laws' domain, (-0.120, 0.060) V (processes/voltage_gates), or the
  contact's |V_j| above the junction gate law's 0.120 V (processes/junction_gate), with the
  draws where the control domain verdict and those two disagree (expected none);
* how many lie within Q2's dropped 10% net-charge band (CHARGE_BAND);
* the largest |V| of a live patch, and the largest |Q / Q_declared| of a live cell, over the
  draws and over those the control domain check admits;
* over the draws the control domain check admits, Q2's comparison (64 eps x R-ops'
  magnitudes): the worst ratio and its key, and at the worst post-event potential the node,
  |engine - R-ops|, R-ops' value and magnitude, and the daughters' net charges against their
  increments' ionic charge content, F sum |z dn| (the scale of the engine's rounding there).
This answers whether the engine's checks alone could define Q2's domain: they could if the
worst ratio over their admitted draws stays within 64 at every spread.

Usage: python -m validation.division.q2_domain_probe OUTPUT_JSON (NumPy only, about a minute).
"""

import json
import sys

import jax
import numpy as np

from cells.models import pump_composite_adapter as adapter
from cells.processes import junction_gate, voltage_gates
from cells.processes.electrochemistry import CHARGE_PER_FMOL
from tests import partition_fixtures as fx
from validation.division import partition_reference as rops
from validation.division import q2_rops_comparison as q2

DRAWS = 200
SPREADS = (0.1, 0.3, 1.0, 3.0, 10.0)


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
    """(domain, control domain, charge bound, max |V|, max |Q / Q_declared|, a patch voltage
    outside the channel gates' domain, the contact's |V_j| outside the junction gate's) of one
    draw."""
    p = world.p
    domain = bool(world.model.domain_valid(state, p, p.active, xp=np))
    full, bounded = q2.admitted(world, state, fx.EVENT)
    q = world.view(state)
    phi = adapter.node_potentials(state, q, xp=np)
    v = q2.patch_voltages(world, state)
    low, high = voltage_gates.VOLTAGE_DOMAIN_V
    junction = abs(float(phi[world.cells.index("cell_0")] - phi[world.cells.index("cell_1")]))
    outside = (bool(np.any((v < low) | (v > high))), junction > junction_gate.MAX_ABS_VOLTAGE_V)
    cells = np.flatnonzero(np.asarray(q.active))
    z = np.ravel(p.valence)
    charge = np.asarray(q.initial_cell_charge_C)[cells] + CHARGE_PER_FMOL * (
        z @ np.asarray(state.amount_increment)[:, cells]
    )
    ratio = np.abs(charge / np.asarray(p.initial_cell_charge_C)[cells])
    return domain, full, bounded, float(np.max(np.abs(v))), float(np.max(ratio)), *outside


def summary(world, d, states):
    """The report of one sampler's draws (module docstring)."""
    rows = [measure(world, s) for s in states]
    admitted = [s for s, r in zip(states, rows, strict=True) if r[1]]
    out = dict(
        draws=len(rows),
        domain_pass=sum(r[0] for r in rows),
        control_domain_pass=sum(r[1] for r in rows),
        charge_bound_pass=sum(r[2] for r in rows),
        max_abs_V=max(r[3] for r in rows),
        max_charge_over_declared=max(r[4] for r in rows),
        admitted_max_abs_V=max((r[3] for r in rows if r[1]), default=None),
        admitted_max_charge_over_declared=max((r[4] for r in rows if r[1]), default=None),
        patch_voltage_outside_channel_gate_domain=sum(r[5] for r in rows),
        contact_voltage_outside_junction_gate_domain=sum(r[6] for r in rows),
        control_domain_fail_without_either=sum((not r[1]) and not (r[5] or r[6]) for r in rows),
        control_domain_pass_with_either=sum(r[1] and (r[5] or r[6]) for r in rows),
    )
    worst, key, detail = 0.0, None, None
    for state in admitted:
        result = rops.apply(world.snapshot(state), world.division(d, state))
        after, ok = world.event(state, (1.0,))
        if not ok:
            out["engine_refused"] = out.get("engine_refused", 0) + 1
            continue
        ratios = q2.compare(world, d, state, after, result)
        if ratios["potentials_after_V"] > (detail or {}).get("ratio", -1.0):
            detail = potential_detail(world, d, after, result) | dict(
                ratio=ratios["potentials_after_V"]
            )
        for name, value in ratios.items():
            if value > worst:
                worst, key = value, name
    out |= dict(admitted_worst_ratio=worst, admitted_worst_key=key, worst_potential=detail)
    return out


def potential_detail(world, d, after, result):
    """At the post-event potential with the worst ratio: its node, |engine - R-ops|, R-ops'
    value and magnitude; each daughter's net charge and its increment's ionic charge content."""
    p, q = world.p, world.view(after)
    phi = adapter.node_potentials(after, q, xp=np)
    n = len(world.cells)
    names = {
        **{c: k for k, c in enumerate(world.cells)},
        **{c: n + k for k, c in enumerate(world.nodes)},
    }
    rows = []
    for node, value in result.values["potentials_after_V"].items():
        magnitude = result.magnitudes["potentials_after_V"][node]
        delta = abs(float(phi[names[node]]) - value)
        scale = max(q2.EPS * magnitude, np.finfo(float).tiny)
        rows.append((delta / scale, node, delta, value, magnitude))
    _, node, delta, value, magnitude = max(rows)
    z = np.ravel(p.valence)
    daughters = {}
    for cell in d.daughters:
        i = world.cells.index(cell)
        increment = np.asarray(after.amount_increment)[:, i]
        daughters[cell] = dict(
            net_charge_C=float(q.initial_cell_charge_C[i] + CHARGE_PER_FMOL * (z @ increment)),
            increment_ionic_charge_C=float(CHARGE_PER_FMOL * np.sum(np.abs(z * increment))),
        )
    return dict(
        node=node,
        abs_difference_V=delta,
        reference_V=value,
        reference_magnitude_V=magnitude,
        daughters=daughters,
    )


def main(output):
    jax.config.update("jax_enable_x64", True)
    carriers = {"Na": 0.3, "K": 0.5, "M": 0.2}
    worlds = {
        "symmetric": fx.divided(neighbour=True),
        "asymmetric": fx.divided(neighbour=True, f=0.75, area_fraction=0.6, carriers=carriers),
    }
    report = dict(status=q2.STATUS, tolerance_eps=64, charge_band=q2.CHARGE_BAND, worlds={})
    for label, raw in worlds.items():
        world = q2.Bound(raw)
        d = next(x for x in world.partition[1].divisions if x.id == "first")
        samplers = {"out-of-domain (6c2b118's increments)": old_sampler}
        for spread in SPREADS:
            samplers[f"perturbed, spread {spread:g}"] = lambda w, r, s=spread: q2.perturbed(
                w, r, spread=s
            )
        entry = {}
        for name, sampler in samplers.items():
            rng = np.random.default_rng(20261113)
            entry[name] = summary(world, d, [sampler(world, rng) for _ in range(DRAWS)])
            print(label, name, entry[name], flush=True)
        report["worlds"][label] = entry
    with open(output, "w") as f:
        json.dump(report, f, indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
