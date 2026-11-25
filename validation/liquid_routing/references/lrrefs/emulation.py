"""A binary64 emulation, for SPEC section 9's check 11 only: exact half-steps, explicit stages, ideal mixing.

It is this folder's own, written from LAWS.md, and it is never used to set a bound. Each routine returns the
emulated series; `checks` compares them with the decimal references (or with the decimal scheme where the model is
a scheme) and records the largest fraction of LAWS section 9's bound.
"""

import math

from . import propagator as pr
from .arith import ZERO, exact
from .laws import ars_constants


def phi_float(level, y):
    """phi(level / y) without the cancellation at level = y."""
    delta = (level - y) / y
    if abs(delta) < 0.25:
        if abs(delta) < 1e-3:
            return delta * delta * (0.5 - delta * (1.0 / 6.0 - delta * (1.0 / 12.0 - delta / 20.0)))
        return (1.0 + delta) * math.log1p(delta) - delta
    if level == 0.0:
        return 1.0
    ratio = level / y
    return ratio * math.log(ratio) - ratio + 1.0


class FlowEmulation:
    """The flow world in binary64, two exact half-steps a step (a face step between them in arm 6)."""

    def __init__(self, world, step):
        self.world = world
        self.step = float(step)
        self.layout = pr.Layout(world)
        self.rt = float(world.rt)
        self.volumes = {node: float(v) for node, v in world.volumes.items()}
        self.n = {x: {node: float(world.start[x].get(node, ZERO)) for node in world.nodes} for x in world.species}
        self.collected = {x: 0.0 for x in world.species}
        self.collector_volume = 0.0
        self.supplied = {x: 0.0 for x in world.species}
        self.heat = {name: 0.0 for name in world.flow_nodes + world.collectors}
        self.face_heat = 0.0
        self.labels = None
        if world.labels:
            spec = world.labels
            self.labels = {label: {} for label in spec["names"]}
            for node in world.nodes:
                n = self.n[spec["species"]][node]
                share = spec["start_shares"].get(node, {})
                rest = 1.0 - sum(v for k, v in share.items() if k != spec["base"])
                for label in spec["names"]:
                    self.labels[label][node] = n * (rest if label == spec["base"] else share.get(label, 0.0))
            self.collected_labels = {label: 0.0 for label in spec["names"]}
        self.half = {}
        for start in [ZERO] + world.switch_times():
            p = pr.expm(pr.generator(world, "volume", start, self.layout, with_faces=False), step / 2)
            self.half[start] = [[float(value) for value in row] for row in p]
        gamma, delta = ars_constants()
        self.gamma, self.delta = float(gamma), float(delta)
        self.time = 0.0
        self.count = 0

    def half_step(self, now):
        world, layout = self.world, self.layout
        switch = max([ZERO] + [t for t in world.switch_times() if t <= exact(now)])
        p = self.half[switch]
        inlet_rows = [layout.index[name] for name in layout.inlets]
        node_rows = [(layout.index[name], name) for name in layout.nodes]
        collector = world.collectors[0] if world.collectors else None
        levels_of_inlets = {x: [float(world.inlet_level(i, x, switch)) for i in layout.inlets] for x in world.species}

        # the volume each origin sends to the collector, and the new collector volume
        if collector is not None:
            row = p[layout.index[collector]]
            arriving_volume = 0.0
            for i in inlet_rows:
                arriving_volume += row[i]
            for j, name in node_rows:
                arriving_volume += row[j] * self.volumes[name]
            new_volume = self.collector_volume + arriving_volume

        new_n, new_collected = {}, {}
        for x in world.species:
            new_n[x] = {}
            for i, name in node_rows:
                total = 0.0
                for k, inlet_row in enumerate(inlet_rows):
                    total += p[i][inlet_row] * levels_of_inlets[x][k]
                for j, origin in node_rows:
                    total += p[i][j] * self.n[x][origin]
                new_n[x][name] = total
            if collector is not None:
                row = p[layout.index[collector]]
                arriving = 0.0
                for k, inlet_row in enumerate(inlet_rows):
                    arriving += row[inlet_row] * levels_of_inlets[x][k]
                for j, origin in node_rows:
                    arriving += row[j] * self.n[x][origin]
                new_collected[x] = self.collected[x] + arriving
            for source, _, rate in world.link_rates(switch):
                if source in world.inlets:
                    k = layout.inlets.index(source)
                    self.supplied[x] += float(rate) * (self.step / 2) * levels_of_inlets[x][k]

        # ideal mixing: the portions each holder receives, at their origins' levels
        for holder in world.flow_nodes + world.collectors:
            row = p[layout.index[holder]]
            is_collector = holder in world.collectors
            for x in world.species:
                if is_collector:
                    if new_volume == 0.0:
                        continue
                    y = new_collected[x] / new_volume
                else:
                    y = new_n[x][holder] / self.volumes[holder]
                loss = 0.0
                for k, inlet_row in enumerate(inlet_rows):
                    if row[inlet_row] != 0.0:
                        loss += row[inlet_row] * y * phi_float(levels_of_inlets[x][k], y)
                for j, origin in node_rows:
                    if row[j] != 0.0:
                        v = row[j] * self.volumes[origin]
                        loss += v * y * phi_float(self.n[x][origin] / self.volumes[origin], y)
                if is_collector and self.collector_volume > 0.0:
                    loss += self.collector_volume * y * phi_float(self.collected[x] / self.collector_volume, y)
                self.heat[holder] += self.rt * loss

        # labels: a share of the new amount
        if self.labels is not None:
            spec = world.labels
            x, base = spec["species"], spec["base"]
            new_labels = {label: {} for label in spec["names"]}
            for label in spec["names"]:
                for i, name in node_rows:
                    top = bottom = 0.0
                    for k, inlet_row in enumerate(inlet_rows):
                        piece = p[i][inlet_row] * levels_of_inlets[x][k]
                        bottom += piece
                        if label == base:
                            top += piece
                    for j, origin in node_rows:
                        top += p[i][j] * self.labels[label][origin]
                        bottom += p[i][j] * self.n[x][origin]
                    new_labels[label][name] = new_n[x][name] * (top / bottom)
                if collector is not None:
                    row = p[layout.index[collector]]
                    top = bottom = 0.0
                    for k, inlet_row in enumerate(inlet_rows):
                        piece = row[inlet_row] * levels_of_inlets[x][k]
                        bottom += piece
                        if label == base:
                            top += piece
                    for j, origin in node_rows:
                        top += row[j] * self.labels[label][origin]
                        bottom += row[j] * self.n[x][origin]
                    if bottom != 0.0:
                        self.collected_labels[label] += (new_collected[x] - self.collected[x]) * (top / bottom)
            self.labels = new_labels

        self.n = new_n
        if collector is not None:
            self.collected = new_collected
            self.collector_volume = new_volume

    def face_step(self):
        """ARS(2,2,2)'s explicit stages on every face, and the exact heat of the levels they leave."""
        h, gamma, delta = self.step, self.gamma, self.delta
        for a, b, table in self.world.faces:
            for x in self.world.species:
                permeance = float(table.get(x, ZERO))
                if permeance == 0.0:
                    continue
                self.n[x][a], self.n[x][b], heat = exact_face_step(
                    self.n[x][a], self.n[x][b], self.volumes[a], self.volumes[b], permeance, h, gamma, delta, self.rt)
                self.face_heat += heat

    def advance(self):
        start = self.count * self.step
        self.half_step(start)
        if self.world.faces:
            self.face_step()
        self.half_step(start)          # no registered switch lies inside a step
        self.count += 1
        self.time = self.count * self.step


def stage_levels(n1, n2, v1, v2, permeance, h, gamma, delta):
    """One explicit step in binary64: (n1', n2', J1, J2)."""
    j1 = permeance * (n1 / v1 - n2 / v2)
    s1 = n1 - gamma * h * j1
    s2 = n2 + gamma * h * j1
    j2 = permeance * (s1 / v1 - s2 / v2)
    moved = h * (delta * j1 + (1.0 - delta) * j2)
    return n1 - moved, n2 + moved, j1, j2, moved


def exact_face_step(n1, n2, v1, v2, permeance, h, gamma, delta, rt):
    """The step and the free energy the two wells lose between their own levels."""
    a, b, _, _, moved = stage_levels(n1, n2, v1, v2, permeance, h, gamma, delta)
    c1, c2, d1, d2 = n1 / v1, n2 / v2, a / v1, b / v2
    heat = rt * (n1 * math.log(c1 / d1) + n2 * math.log(c2 / d2) + moved * math.log(d1 / d2))
    return a, b, heat


def default_face_step(n1, n2, v1, v2, permeance, h, gamma, delta, rt):
    """The step and the default heat RT h Jbar^2 / W with the logarithmic-mean weight at the half-advanced levels."""
    a, b, j1, j2, _ = stage_levels(n1, n2, v1, v2, permeance, h, gamma, delta)
    mean_flux = delta * j1 + (1.0 - delta) * j2
    c1 = n1 / v1 - 0.5 * h * j1 / v1
    c2 = n2 / v2 + 0.5 * h * j1 / v2
    weight = permeance * (c1 - c2) / math.log(c1 / c2)
    return a, b, rt * h * mean_flux * mean_flux / weight


def portions(rt, sequence):
    """[(n, V, loss, cumulative)] of portions joining an empty collector, in binary64."""
    n = volume = total = 0.0
    rows = []
    for v, x in sequence:
        new_n, new_volume = n + v * x, volume + v
        y = new_n / new_volume
        loss = 0.0
        if volume > 0.0:
            loss += volume * y * phi_float(n / volume, y)
            loss += v * y * phi_float(x, y)
        loss *= rt
        total += loss
        n, volume = new_n, new_volume
        rows.append((n, volume, loss, total))
    return rows
