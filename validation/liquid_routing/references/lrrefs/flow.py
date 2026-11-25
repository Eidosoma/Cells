"""Flow worlds: amounts and labels by the propagator, the total heat as a state function, and the same total by
two other routes (the ideal mixing of finite portions, and the integral of the holders' rates).
"""

from decimal import Decimal

from . import propagator as pr
from .arith import ONE, ZERO, exact, phi, x_ln_ratio
from .laws import free_energy, free_energy_density


# ---- amounts -------------------------------------------------------------------------------------------

def amounts(world, species, time, method="expm", **options):
    """{node or collector: fmol} at `time`."""
    plain = not options
    key = (species, time, method)
    if plain and key in world.cache:
        return dict(world.cache[key])
    layout = pr.Layout(world)
    y = pr.solve(world, species, time, method=method, **options)
    out = {name: y[layout.index[name]] for name in layout.nodes + layout.collectors}
    if plain:
        world.cache[key] = dict(out)
    return out


def label_starts(world):
    """{label: {node: fmol}} of the labelled species: declared shares of the start; the base label holds the rest."""
    spec = world.labels
    species, base = spec["species"], spec["base"]
    starts = {label: {} for label in spec["names"]}
    for node, n in sorted(world.start[species].items()):
        shares = {label: exact(share) for label, share in spec["start_shares"].get(node, {}).items()}
        others = sum((share for label, share in shares.items() if label != base), ZERO)
        for label in spec["names"]:
            starts[label][node] = n * ((ONE - others) if label == base else shares.get(label, ZERO))
    return starts


def label_amounts(world, label, time, method="expm"):
    """The amounts of one label: the species' equations with the label's own start (LAWS section 7)."""
    spec = world.labels
    return amounts(world, spec["species"], time, method=method, amounts=label_starts(world)[label],
                   inlet_on=(label == spec["base"]))


# ---- the total heat as a state function (LAWS sections 5 and 8) ----------------------------------------

def supplied_free_energy(world, time):
    """The integral of sum Q f(x) dt over the links that leave an inlet, over every species."""
    total = ZERO
    for a, b in pr.segments(world, ZERO, time):
        for source, _, rate in world.link_rates(a):
            if source in world.inlets:
                for x in world.species:
                    total += rate * free_energy_density(world.rt, world.inlet_level(source, x, a)) * (b - a)
    return total


def total_heat(world, time, states=None):
    """H_tot(t) over the nodes a link or a face touches and the collectors, summed over species.

    `states` is {species: {name: amount}} at `time`; computed by the propagator if not given.
    """
    if states is None:
        states = {x: amounts(world, x, time) for x in world.species}
    nodes = set(world.flow_nodes)
    for a, b, _ in world.faces:
        nodes.update((a, b))
    total = supplied_free_energy(world, time)
    volume = pr.collector_volume(world, time)
    for x in world.species:
        for node in sorted(nodes):
            total += free_energy(world.rt, world.start[x].get(node, ZERO), world.volumes[node])
            total -= free_energy(world.rt, states[x][node], world.volumes[node])
        for collector in world.collectors:
            total -= free_energy(world.rt, states[x][collector], volume)
    return total


# ---- the same total by the ideal mixing of finite portions -----------------------------------------------

def portion_heats(world, step, time):
    """{holder: heat} to `time`, with every step of `step` one ideal mixing of portions (exact propagators).

    In a step, holder i ends with a volume v_ij = P_ij V_j from each origin j (an inlet's column is already a
    volume), at the origin's concentration; they mix to y_i, and lose RT sum_j v_ij y_i phi(c_j / y_i). The sum
    over holders telescopes to the state function; the split among holders depends on `step`.
    """
    layout = pr.Layout(world)
    heats = {name: ZERO for name in world.flow_nodes + world.collectors}
    levels = {x: pr.start_vector(world, x, layout) for x in world.species}
    volumes = pr.start_vector(world, "volume", layout)
    count = time / step
    if count != count.to_integral_value():
        raise ValueError("the time is not a multiple of the step")
    cache = {}
    for index in range(int(count)):
        now = step * index
        edges = pr.segments(world, now, now + step)
        if len(edges) != 1:
            raise ValueError("a switch inside a step")
        switch = max([ZERO] + [t for t in world.switch_times() if t <= now])
        if switch not in cache:
            cache[switch] = pr.expm(pr.generator(world, "volume", switch, layout, with_faces=False), step)
        p = cache[switch]
        for x in world.species:
            levels[x] = pr.with_inlets(world, x, now, levels[x], layout)
        volumes = pr.with_inlets(world, "volume", now, volumes, layout)
        new_volumes = pr.matvec(p, volumes)
        new_levels = {x: pr.matvec(p, levels[x]) for x in world.species}
        for holder in heats:
            i = layout.index[holder]
            for x in world.species:
                if new_volumes[i] == 0:
                    continue
                y = new_levels[x][i] / new_volumes[i]
                loss = ZERO
                for j in range(layout.size):
                    v = p[i][j] * volumes[j]
                    if v == 0:
                        continue
                    origin = levels[x][j] if layout.names[j] in world.inlets else levels[x][j] / volumes[j]
                    if y == 0:
                        continue
                    loss += v * y * phi(origin / y)
                heats[holder] += world.rt * loss
        levels, volumes = new_levels, new_volumes
    return heats


# ---- the holders' rates ------------------------------------------------------------------------------------

def holder_rates(world, rates_in_force, levels):
    """{holder: r} for one species, with `levels` the concentration of every inlet, node and collector."""
    out = {}
    for holder in world.flow_nodes + world.collectors:
        y = levels[holder]
        total = ZERO
        for source, target, q in rates_in_force:
            if target != holder or q == 0:
                continue
            x = levels[source]
            total += q * (x_ln_ratio(x, x, y) - x + y)
        out[holder] = world.rt * total
    return out


def face_rate(world, species, levels):
    """Sum over faces of PA (c_A - c_B) RT ln(c_A/c_B)."""
    total = ZERO
    for a, b, table in world.faces:
        permeance = table.get(species, ZERO)
        if permeance == 0 or levels[a] == levels[b]:
            continue
        total += permeance * (levels[a] - levels[b]) * (levels[a] / levels[b]).ln()
    return world.rt * total


__all__ = ["Decimal"]
