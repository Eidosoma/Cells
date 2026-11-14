"""Q2's rounding cause: |engine - R-ops| against the increments' ionic content (development).

The lead's probe (14 November). Q2's asymmetric draws differ from R-ops by 2.4-3.0e-16 V in the
post-event potentials whatever their net charge (q2_domain_probe). The reading under test: a
node charge is formed from amounts (Appendix A.1: Q_i = 1e-15 F (sum_s z_s n_si + X_i)), so its
rounding scales with the increments' ionic content, sum_s |z_s dn_s|, which R-ops' charge-form
magnitudes omit.

On each of Q2's neighbour worlds, the draws of q2_domain_probe's samplers (its seed; net-charge
spreads SPREADS) that the composite's control domain check admits are compared with R-ops as
drawn, and again with every live cell's increments at FACTORS times their ionic content and the
same net charge: one amount a is added to K (z = +1) and to M (z = -1), so sum z dn does not
change, and with both increments then non-negative sum |z dn| becomes the factor times its
drawn value. In exact arithmetic the charges, the potentials and the image charge are then the
drawn state's; only their rounding can move. Compared after the event, as absolute differences
engine - R-ops: the largest over the post-event potentials, each daughter's charge, and the
largest over the clamps' image charges.

Reported per world and spread: A.1's whole ionic content against the increments', (sum_s
|z_s n_s| + |X|) / sum_s |z_s dn_s| over the live cells of the drawn states (median, min, max),
the factor by which a term built from the whole content would exceed one built from the
increments. Per world, spread and factor: the admitted draws and how many stay admitted when
scaled; the content ratio achieved (min, max); each quantity's median and largest difference;
per draw, its difference over the drawn (factor 1) one: median, min and max where the drawn one
is non-zero. And the draw with Q2's worst potential ratio at factor 1, at every factor. A ratio
near the factor confirms the content's rounding as the cause; a ratio near 1 points elsewhere
(the capacitor solve's forward error, for example).

Usage: python -m validation.division.q2_rounding_cause OUTPUT_JSON (NumPy only, about a minute).
"""

import json
import sys

import jax
import numpy as np

from cells.models import pump_composite_adapter as adapter
from cells.processes.electrochemistry import CHARGE_PER_FMOL
from tests import partition_fixtures as fx
from validation.division import partition_reference as rops
from validation.division import q2_domain_probe as probe
from validation.division import q2_rops_comparison as q2

SPREADS = (0.1, 1.0)
FACTORS = (1, 10, 100)
SEED = 20261113  # q2_domain_probe's, reseeded per spread: the same draws.


def scaled(world, state, factor):
    """(state with each live cell's increments at factor times their ionic content and the same
    net charge, the content ratio achieved per cell) (module docstring)."""
    species = list(world.spec.model.species_ids)
    k, m = species.index("K"), species.index("M")
    z = np.ravel(world.p.valence)
    assert z[k] == 1 and z[m] == -1
    delta = np.array(state.amount_increment, copy=True)
    ratios = []
    for i in np.flatnonzero(np.asarray(world.view(state).active)):
        d = delta[:, i]
        content = float(np.sum(np.abs(z * d)))
        if factor == 1:
            ratios.append(1.0)
            continue
        rest = content - abs(d[k]) - abs(d[m])
        a = (factor * content - rest - d[k] - d[m]) / 2.0
        assert a >= max(-d[k], -d[m], 0.0), (factor, a, d[k], d[m])
        d[k] += a
        d[m] += a
        ratios.append(float(np.sum(np.abs(z * d))) / content)
    return state._replace(amount_increment=delta), ratios


def differences(world, d, before, after, result):
    """|engine - R-ops| after the event: potentials (largest), daughters' charges, image charge
    (largest), formed as q2_rops_comparison.compare forms them."""
    z = np.ravel(world.p.valence)
    q1 = world.view(after)
    phi = adapter.node_potentials(after, q1, xp=np)
    n = len(world.cells)
    nodes = {
        **{c: k for k, c in enumerate(world.cells)},
        **{c: n + k for k, c in enumerate(world.nodes)},
    }
    v = result.values
    out = dict(
        potentials_after_V=max(
            abs(float(phi[nodes[node]]) - value) for node, value in v["potentials_after_V"].items()
        )
    )
    for tag, cell in zip(("D1", "D2"), d.daughters, strict=True):
        i = world.cells.index(cell)
        delta = np.asarray(after.amount_increment)[:, i]
        charge = q1.initial_cell_charge_C[i] + CHARGE_PER_FMOL * np.sum(z * delta)
        out[f"charge_{tag}_C"] = abs(float(charge) - v[f"charge_{tag}_C"])
    image = np.asarray(after.electrode_charge_transferred_C) - np.asarray(
        before.electrode_charge_transferred_C
    )
    out["image_charge_C"] = max(
        abs(float(image[world.nodes.index(b)]) - value) for b, value in v["image_charge_C"].items()
    )
    return out


def measured(world, d, state, factor):
    """(differences, content ratios, still admitted, Q2's potential ratio) at one factor."""
    state, ratios = scaled(world, state, factor)
    domain, _ = q2.admitted(world, state, fx.EVENT)
    result = rops.apply(world.snapshot(state), world.division(d, state))
    after, ok = world.event(state, (1.0,))
    assert ok
    ratio = q2.compare(world, d, state, after, result)["potentials_after_V"]
    return differences(world, d, state, after, result), ratios, domain, ratio


def contents(world, state):
    """(sum |z n| + |X|) / sum |z dn| for each live cell (module docstring)."""
    p, z = world.p, np.ravel(world.p.valence)
    out = []
    for i in np.flatnonzero(np.asarray(world.view(state).active)):
        delta = np.asarray(state.amount_increment)[:, i]
        amounts = np.asarray(p.amount_reference)[:, i] + delta
        whole = np.sum(np.abs(z * amounts)) + abs(world.background[world.cells[i]])
        out.append(float(whole / np.sum(np.abs(z * delta))))
    return out


def summarise(rows):
    """The report of one spread's admitted draws (module docstring)."""
    out = dict(admitted=len(rows))
    for factor in FACTORS:
        achieved = [x for row in rows for x in row[factor][1]]
        entry = dict(
            still_admitted=sum(row[factor][2] for row in rows),
            content_ratio_min=min(achieved),
            content_ratio_max=max(achieved),
        )
        for key in rows[0][factor][0]:
            values = np.array([row[factor][0][key] for row in rows])
            drawn = np.array([row[1][0][key] for row in rows])
            nonzero = drawn > 0
            over = values[nonzero] / drawn[nonzero]
            entry[key] = dict(
                median=float(np.median(values)),
                max=float(np.max(values)),
                drawn_nonzero=int(np.sum(nonzero)),
                over_drawn_median=float(np.median(over)) if over.size else None,
                over_drawn_min=float(np.min(over)) if over.size else None,
                over_drawn_max=float(np.max(over)) if over.size else None,
            )
        out[f"factor {factor}"] = entry
    worst = max(rows, key=lambda row: row[1][3])
    out["worst_draw"] = {
        f"factor {factor}": dict(differences=worst[factor][0], q2_potential_ratio=worst[factor][3])
        for factor in FACTORS
    }
    return out


def main(output):
    jax.config.update("jax_enable_x64", True)
    carriers = {"Na": 0.3, "K": 0.5, "M": 0.2}
    worlds = {
        "symmetric": fx.divided(neighbour=True),
        "asymmetric": fx.divided(neighbour=True, f=0.75, area_fraction=0.6, carriers=carriers),
    }
    report = dict(status=q2.STATUS, factors=list(FACTORS), spreads=list(SPREADS), worlds={})
    for label, raw in worlds.items():
        world = q2.Bound(raw)
        d = next(x for x in world.partition[1].divisions if x.id == "first")
        entry = {}
        for spread in SPREADS:
            rng = np.random.default_rng(SEED)
            draws = [q2.perturbed(world, rng, spread=spread) for _ in range(probe.DRAWS)]
            admitted = [s for s in draws if q2.admitted(world, s, fx.EVENT)[0]]
            rows = [{f: measured(world, d, s, f) for f in FACTORS} for s in admitted]
            ratios = [x for s in admitted for x in contents(world, s)]
            entry[f"spread {spread:g}"] = summarise(rows) | dict(
                whole_over_increment_content=dict(
                    median=float(np.median(ratios)), min=min(ratios), max=max(ratios)
                )
            )
            print(label, spread, json.dumps(entry[f"spread {spread:g}"]), flush=True)
        report["worlds"][label] = entry
    with open(output, "w") as f:
        json.dump(report, f, indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
