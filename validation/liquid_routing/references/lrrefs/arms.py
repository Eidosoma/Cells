"""The published blocks, arm by arm: worlds, cases, events, plants, planted series and checks.

Every value is computed in decimal from LAWS.md; every entry's class follows SPEC section 4 and READOUTS section 3, as
Amendment 1 reads them.
"""

from decimal import Decimal

from . import checks, flow, heats, plants, propagator as pr, scales
from .arith import ONE, ZERO, accuracy, exact, publish, publish_bound
from .laws import exchange, portion
from .plants import key, two_wells


class Blocks:
    """One arm's parts of a reference file."""

    def __init__(self):
        self.worlds, self.cases, self.events = {}, {}, {}
        self.plants, self.planted_series, self.plants_reported = [], {}, []
        self.checks, self.reported = [], []

    def merge(self, other):
        for name in ("worlds", "cases", "events"):
            getattr(self, name).update(getattr(other, name))
        for plant, table in other.planted_series.items():
            self.planted_series.setdefault(plant, {}).update(table)
        for name in ("plants", "plants_reported", "checks", "reported"):
            getattr(self, name).extend(getattr(other, name))


class Series:
    """The parallel lists of one series: classes, values, accuracies."""

    def __init__(self):
        self.classes, self.values, self.bounds = [], [], []

    def add(self, klass, value, extra=ZERO):
        if klass == "E":
            if value != 0:
                raise ValueError("an E entry that is not zero")
            self.classes.append("E")
            self.values.append("0")
            self.bounds.append("0")
            return
        self.classes.append(klass)
        self.values.append(publish(value))
        self.bounds.append(publish_bound(accuracy(value, extra)))

    def block(self):
        return {"class": self.classes, "value": self.values, "accuracy": self.bounds}


def publish_world(times, table):
    return {"times_s": [float(t) for t in times], "series": {name: s.block() for name, s in sorted(table.items())}}


def with_accuracy(table):
    """A case's or event's numbers with their bounds beside them."""
    out, bounds = {}, {}
    for name, value in table.items():
        if isinstance(value, (list, tuple)):
            out[name] = [publish(v) for v in value]
            bounds[name] = [publish_bound(accuracy(v)) for v in value]
        else:
            out[name] = publish(value)
            bounds[name] = publish_bound(accuracy(value))
    out["accuracy"] = bounds
    return out


# ---- arm 1 ----------------------------------------------------------------------------------------------------------

def case_steps(inputs, name):
    """The steps of a world's arm 1 runs, and the next halving of each judged set (CRITERIA section 2's retry, j = 4).

    The exact retry's step is a default step already (or a recorded one), so only the default retry adds cases.
    """
    steps = {inputs.step(run) for run in inputs.runs_of(arm=1, world=name)}
    for heat in ("exact", "default"):
        judged = [inputs.step(run) for run in inputs.runs_of(arm=1, world=name, role="judged", heat=heat)]
        if judged:
            steps.add(min(judged) / 2)
    return sorted(steps)


def arm1(inputs, plan, label="arm 1 (explicit stages)"):
    blocks = Blocks()
    worlds = inputs.worlds_of(1)
    for name in worlds:
        world = inputs.worlds[name]
        wells = two_wells(world)
        table = {"n_T_1": Series(), "n_T_2": Series(), "H_face": Series()}
        table["n_T_1"].add("R", wells.n1)
        table["n_T_2"].add("R", wells.n2)
        table["H_face"].add("E", ZERO)
        blocks.worlds[name] = publish_world([ZERO], table)
        steps = case_steps(inputs, name)
        for h in steps:
            moved, by_scheme = wells.moved(h), wells.moved_by_scheme(h)
            blocks.cases[key(name, h)] = with_accuracy({
                "m_star": moved, "m_R": by_scheme, "levels_exact": wells.levels(moved),
                "levels_scheme": wells.levels(by_scheme), "D_star": wells.lost(moved), "D_R": wells.lost(by_scheme),
                "A0": wells.affinity(ZERO), "H_def": wells.default_heat(h), "B_def": wells.default_bound(h)})
        blocks.checks += checks.two_well_checks(inputs, world, steps, steps)
        blocks.checks += checks.two_well_network(world, steps, max(steps))
    rows, series, reported = plants.arm1(inputs, plan)
    blocks.plants += rows
    blocks.planted_series.update(series)
    blocks.plants_reported += reported
    blocks.checks += checks.stability_function("arm 1", sorted({
        two_wells(inputs.worlds[run["world"]]).k * inputs.step(run) for run in inputs.runs_of(arm=1)}))
    law, outside = checks.default_law(inputs, 1)
    blocks.checks += law
    blocks.reported += outside
    blocks.checks += checks.emulate_wells(inputs, 1, label)
    return blocks


# ---- arm 2 ----------------------------------------------------------------------------------------------------------

class TwoIntervals:
    """The exact solution of an arm 2 world: two wells, an exchange at most, two wells."""

    def __init__(self, world):
        self.world = world
        self.first = two_wells(world)
        self.event = world.events[0] if world.events else None
        if self.event is not None:
            self.time = exact(self.event["time_s"])
            before1, before2 = self.first.levels(self.first.moved(self.time))
            self.before = before1
            self.sample, self.supplied, after, self.heat = exchange(
                world.rt, before1, self.first.v1, exact(self.event["fraction"]), exact(self.event["buffer_mM"]["T"]))
            self.second = type(self.first)(world.rt, after, before2, self.first.v1, self.first.v2, self.first.pa)
            self.lost_before = self.first.lost(self.first.moved(self.time))

    def at(self, t):
        """(n1, n2, H_face) at t; at the event's time, the state before it."""
        if self.event is None or t <= self.time:
            m = self.first.moved(t)
            return (*self.first.levels(m), self.first.lost(m))
        m = self.second.moved(t - self.time)
        return (*self.second.levels(m), self.lost_before + self.second.lost(m))


def arm2(inputs, plan, label="arm 2 (explicit stages)"):
    blocks = Blocks()
    heat_of = {}
    zs = set()
    for name in inputs.worlds_of(2):
        world = inputs.worlds[name]
        solution = TwoIntervals(world)
        times = [exact(t) for t in world.output_floats()]
        table = {"n_T_1": Series(), "n_T_2": Series(), "H_face": Series()}
        for t in times:
            n1, n2, heat = solution.at(t)
            table["n_T_1"].add("S", n1)
            table["n_T_2"].add("S", n2)
            table["H_face"].add("E" if t == 0 else "S", heat)
        blocks.worlds[name] = publish_world(times, table)
        if solution.event is not None:
            block = with_accuracy({"before": solution.before, "sample": solution.sample, "supplied": solution.supplied,
                                   "heat": solution.heat})
            block["class"] = {"before": "S", "sample": "S", "supplied": "R", "heat": "S"}
            block["time_s"] = float(solution.time)
            blocks.events[name] = block
            heat_of[name] = solution.heat
            blocks.checks += checks.f_ladder(world)
        request = plan.get("request_state", {}).get(name)
        if request is not None:
            at, levels = request
            blocks.checks += checks.request_state(world, exact(at), [exact(v) for v in levels])
        blocks.checks += checks.two_well_checks(inputs, world, times[1:])
        blocks.checks += checks.two_well_network(world, sorted({inputs.step(run) for run in inputs.runs_of(arm=2, world=name)}),
                                                 exact(world.end))
        blocks.checks += checks.exchange_conservation(solution, times)
        blocks.checks += _second_interval(solution, times)
        zs.update(two_wells(world).k * inputs.step(run) for run in inputs.runs_of(arm=2, world=name))
    for run in inputs.runs_of(arm=2, role="expected stop"):
        zs.add(two_wells(inputs.worlds[run["world"]]).k * inputs.step(run))
        blocks.checks += checks.two_well_network(inputs.worlds[run["world"]], [inputs.step(run)], inputs.step(run))
    rows, series, reported = plants.arm2(inputs, plan, heat_of)
    blocks.plants += rows
    blocks.planted_series.update(series)
    blocks.plants_reported += reported
    blocks.checks += checks.stability_function("arm 2", sorted(zs))
    law, outside = checks.default_law(inputs, 2)
    blocks.checks += law
    blocks.reported += outside
    blocks.checks += checks.emulate_wells(inputs, 2, label)
    return blocks


def _second_interval(solution, times):
    """After the exchange: the closed form against the propagator, and the face's heat against its time integral."""
    if solution.event is None:
        return []
    world, wells = solution.world, solution.second
    worst_levels, worst_heat = ZERO, ZERO
    rule = heats.gauss()
    g = [[-wells.pa / wells.v1, wells.pa / wells.v2], [wells.pa / wells.v1, -wells.pa / wells.v2]]
    for t in times:
        if t <= solution.time:
            continue
        n1, n2, heat = solution.at(t)
        by_matrix = pr.matvec(pr.expm(g, t - solution.time), [wells.n1, wells.n2])
        worst_levels = max(worst_levels, abs(n1 - by_matrix[0]) / n1, abs(n2 - by_matrix[1]) / n2)
        with checks.precision(heats.QUAD_DIGITS):
            total = ZERO
            for lo, hi, w in ((ZERO, solution.time, solution.first), (solution.time, t, solution.second)):
                offset = lo
                for s, weight in heats.gauss_points(rule, lo, hi, 0):
                    n1s, n2s = w.levels(w.moved(s - offset))
                    c1, c2 = n1s / w.v1, n2s / w.v2
                    if c1 != c2:
                        total += weight * w.pa * (c1 - c2) * world.rt * (c1 / c2).ln()
        worst_heat = max(worst_heat, abs(total - heat) / heat)
    return [checks.row(f"6 two wells: {world.name}, after the exchange, the closed form against the propagator (relative)",
                       worst_levels, checks.DIGITS_50),
            checks.row(f"6 two wells: {world.name}, the face's heat over both intervals against its time integral (relative)",
                       worst_heat, checks.DIGITS_40)]


# ---- arms 3 to 6: what the flow worlds share -----------------------------------------------------------------------

def is_still(world):
    """Arm 6's world with every flow off."""
    return bool(world.faces) and bool(world.links) and all(q == 0 for _, _, schedule in world.links for _, q in schedule)


def crossing_species(world):
    out = set()
    for _, _, table in world.faces:
        out.update(x for x, p in table.items() if p != 0)
    return sorted(out)


def holder_names(world):
    return world.nodes + world.collectors


def flow_series(world, times, states, totals, arm, holder_heats=None, face_heats=None, heat_extra=None, label_states=None,
                collector_heats=None):
    """Every series of a flow world. `states[t][x][name]`, `totals[t]`; the heats as {name: {t: value}}."""
    table = {}
    still, crossing = is_still(world), crossing_species(world)
    ligand = (world.sites["ligand"], world.sites["node"]) if world.sites else None

    def put(name, t, klass, value, extra=ZERO):
        table.setdefault(name, Series()).add(klass, value, extra)

    uniform = checks.is_uniform(world)
    for t in times:
        for x in world.species:
            for name in holder_names(world):
                if ligand == (x, name):
                    continue                       # E by the twin, and LAWS has no binding law (Amendment 1, item 3)
                collector = name in world.collectors
                if collector and (t == 0 or still):
                    put(f"n_{x}_{name}", t, "E", states[t][x][name])
                else:
                    put(f"n_{x}_{name}", t, "S" if arm == 6 and x in crossing else "R", states[t][x][name])
            put(f"supplied_{x}", t, "E" if t == 0 else "R", pr.supplied(world, x, t) + _portions_supplied(world, x, t))
        if world.collectors:
            volume = pr.collector_volume(world, t) + _portions_volume(world, t)
            put("V_K", t, "E" if t == 0 or still else "R", volume)
        if arm == 6:
            put("H_tot", t, "E" if t == 0 else "S", totals[t])
            put("H_face", t, "E" if t == 0 else "S", face_heats[t], heat_extra if t != 0 and heat_extra else ZERO)
            if still:
                for name in world.flow_nodes + world.collectors:
                    put(f"H_{name}", t, "E", ZERO)
        else:
            put("H_tot", t, "E" if t == 0 else "R", totals[t])
        if arm == 4:
            for name in world.collectors:
                put(f"H_{name}", t, "E" if t == 0 else "R", collector_heats[t])
        if arm == 5:
            for name in world.flow_nodes + world.collectors:
                value = holder_heats[name][t]
                put(f"H_{name}", t, "E" if t == 0 else ("U" if uniform else "S"), value,
                    heat_extra if t != 0 and heat_extra and value != 0 else ZERO)
        if world.labels:
            spec = world.labels
            for label in spec["names"]:
                for name in holder_names(world):
                    collector = name in world.collectors
                    share_zero = label != spec["base"] and exact(
                        spec["start_shares"].get(name, {}).get(label, 0.0)) == 0
                    is_e = t == 0 and (collector or share_zero)
                    put(f"label_{spec['species']}_{label}_{name}", t, "E" if is_e else "R", label_states[t][label][name])
    return table


def _portions_supplied(world, species, t):
    total = ZERO
    for event in world.events:
        if event["kind"] == "delivery" and exact(event["time_s"]) < t:
            total += exact(event["volume_pL"]) * world.inlet_level(event["inlet"], species, exact(event["time_s"]))
    return total


def _portions_volume(world, t):
    return sum((exact(event["volume_pL"]) for event in world.events
                if event["kind"] == "delivery" and exact(event["time_s"]) < t), ZERO)


def flow_states(world, times):
    states = {}
    for t in times:
        if t == 0:
            states[t] = {x: {name: world.start[x].get(name, ZERO) for name in holder_names(world)} for x in world.species}
        else:
            states[t] = {x: flow.amounts(world, x, t) for x in world.species}
    return states


def flow_totals(world, times, states):
    totals = {}
    for t in times:
        totals[t] = ZERO if t == 0 else flow.total_heat(world, t, states[t])
    return totals


# ---- arm 3 ----------------------------------------------------------------------------------------------------------

def arm3(inputs, plan):
    blocks = Blocks()
    worlds = [inputs.worlds[name] for name in inputs.worlds_of(3)]
    for world in worlds:
        times = [exact(t) for t in world.output_floats()]
        states = flow_states(world, times)
        totals = flow_totals(world, times, states)
        label_states = None
        if world.labels:
            label_states = {}
            for t in times:
                if t == 0:
                    starts = flow.label_starts(world)
                    label_states[t] = {label: {name: starts[label].get(name, ZERO) for name in holder_names(world)}
                                       for label in world.labels["names"]}
                else:
                    label_states[t] = {label: flow.label_amounts(world, label, t) for label in world.labels["names"]}
        table = flow_series(world, times, states, totals, 3, label_states=label_states)
        blocks.worlds[world.name] = publish_world(times, table)
        blocks.checks += checks.conservation(world)
        blocks.checks += checks.reversal(inputs, world)
        blocks.checks += checks.second_propagator(world)
        outputs = times[1:]
        blocks.checks += checks.total_by_gauss(world, [totals[t] for t in outputs], outputs)
        blocks.checks += checks.total_by_portions(inputs, world, [totals[t] for t in outputs], outputs)
        if world.labels:
            blocks.checks += checks.label_sums(world)
        blocks.checks += checks.emulate_flow(inputs, world)
    spec = plan["equal_volumes"]
    forward, backward = (inputs.worlds[name] for name in spec)
    blocks.checks += checks.equal_volumes(forward, backward)
    chains = [inputs.worlds[name] for name in plan["chains"]]
    blocks.checks += checks.unequal_volumes(chains, forward)
    rows, series, reported, control = plants.arm3(inputs, plan)
    blocks.plants += rows
    blocks.planted_series.update(series)
    blocks.plants_reported += reported
    blocks.checks.append(checks.row("P3's negative control: at equal volumes its amounts are the honest ones (fmol, the largest "
                                    "gap)", control, checks.DIGITS_50))
    blocks.checks += throughput_rows(inputs, 3)
    return blocks


def throughput_rows(inputs, arm):
    """The operator's domain (SPEC section 1): every judged run's throughput is at most 1; the refusal's is above 1."""
    rows = []
    largest = ZERO
    for run in inputs.runs_of(arm=arm):
        rho, _ = inputs.worlds[run["world"]].throughput(inputs.step(run))
        if run["role"] == "expected refusal":
            rows.append(checks.row(f"domain: {run['name']}, 1 over its throughput (a refusal needs it below 1)",
                                   1 / rho, Decimal(1) - Decimal(10) ** -20))
        else:
            largest = max(largest, rho)
    rows.append(checks.row(f"domain: arm {arm}, the largest throughput of any run meant to complete", largest, ONE))
    return rows


# ---- arm 4 ----------------------------------------------------------------------------------------------------------

def entries_of(world):
    """[(time, volume, level)] of the portions of a portion-fed collector."""
    return [(exact(e["time_s"]), exact(e["volume_pL"]),
             world.inlet_level(e["inlet"], "T", exact(e["time_s"]))) for e in world.events]


def stream_entries(world, t):
    """A collector fed by one inlet: the liquid that entered to t, as one portion for each level in force."""
    out = []
    for a, b in pr.segments(world, ZERO, t):
        for source, target, q in world.link_rates(a):
            if target in world.collectors and source in world.inlets:
                out.append((q * (b - a), world.inlet_level(source, "T", a)))
    return out


def arm4(inputs, plan):
    blocks = Blocks()
    for name in inputs.worlds_of(4):
        world = inputs.worlds[name]
        times = [exact(t) for t in world.output_floats()]
        states, totals, collector_heats = {}, {}, {}
        for t in times:
            if world.events:
                joined = [(v, x) for at, v, x in entries_of(world) if at < t]
            else:
                joined = stream_entries(world, t)
            n = volume = total = ZERO
            for v, x in joined:
                n, volume, loss, _, _ = portion(world.rt, n, volume, v, x)
                total += loss
            states[t] = {"T": {world.collectors[0]: n}}
            totals[t] = collector_heats[t] = total
        table = flow_series(world, times, states, totals, 4, collector_heats=collector_heats)
        blocks.worlds[name] = publish_world(times, table)
        if world.events:
            worst = max(abs(states[t]["T"][world.collectors[0]] - _portions_supplied(world, "T", t)) for t in times)
            blocks.checks.append(checks.row(f"3 conservation: {name}, the collector holds what was supplied (fmol)", worst,
                                            checks.DIGITS_50))
            n = volume = ZERO
            portions = []
            for k, (at, v, x) in enumerate(entries_of(world)):
                n, volume, loss, resident, arriving = portion(world.rt, n, volume, v, x)
                block = with_accuracy({"volume_pL": v, "amount": v * x, "loss": loss, "resident": resident,
                                       "arriving": arriving})
                block["class"] = {"volume_pL": "R", "amount": "R", "loss": "E" if k == 0 else "R"}
                block["time_s"] = float(at)
                portions.append(block)
            blocks.events[name] = portions
            entries = [(v, x) for _, v, x in entries_of(world)]
            blocks.checks += checks.collector_total(world, entries)
            blocks.checks += checks.emulate_portions(world, entries)
            worst = ZERO
            n = volume = ZERO
            for v, x in entries:
                by_logs = checks.portion_loss_by_logs(world.rt, n, volume, v, x)
                n, volume, loss, _, _ = portion(world.rt, n, volume, v, x)
                worst = max(worst, abs(by_logs - loss) / scales.heat_scale(world, exact(world.end)))
            blocks.checks.append(checks.row(f"8 heat: {world.name}, each portion's loss by both forms (over s_F)", worst,
                                            checks.DIGITS_50))
        else:
            outputs = times[1:]
            worst = ZERO
            for t in outputs:
                by_state = flow.total_heat(world, t)
                worst = max(worst, abs(by_state - totals[t]) / scales.heat_scale(world, t))
                honest = flow.amounts(world, "T", t)[world.collectors[0]]
                worst = max(worst, abs(honest - states[t]["T"][world.collectors[0]]) / honest)
            blocks.checks.append(checks.row(f"8 heat: {world.name}, the stream's loss and amount by the portion law against the "
                                            "state function and the propagator (over s_F, relative)", worst, checks.DIGITS_50))
            blocks.checks += checks.conservation(world)
            blocks.checks += checks.reversal(inputs, world)
            blocks.checks += checks.second_propagator(world)
            blocks.checks += checks.total_by_gauss(world, [totals[t] for t in outputs], outputs)
            blocks.checks += checks.total_by_portions(inputs, world, [totals[t] for t in outputs], outputs)
            blocks.checks += checks.emulate_flow(inputs, world)
    rt = next(iter(inputs.worlds.values())).rt
    blocks.checks += checks.portion_checks(rt)
    rows, series, reported, distance = plants.arm4(inputs, plan)
    blocks.plants += rows
    blocks.planted_series.update(series)
    blocks.plants_reported += reported
    blocks.checks.append(checks.row("P9: the planted first loss is not zero (1 over the distance, pJ, against 1e6)",
                                    1 / distance, Decimal(10) ** 6))
    blocks.checks += throughput_rows(inputs, 4)
    return blocks


# ---- arm 5 ----------------------------------------------------------------------------------------------------------

def arm5(inputs, plan):
    blocks = Blocks()
    honest_heats, honest_totals = {}, {}
    for name in inputs.worlds_of(5):
        world = inputs.worlds[name]
        times = [exact(t) for t in world.output_floats()]
        outputs = times[1:]
        states = flow_states(world, times)
        totals = flow_totals(world, times, states)
        uniform = checks.is_uniform(world)
        values, spread = heats.by_tanh_sinh(world, outputs)
        gauss_values = heats.by_gauss(world, outputs)
        holders = world.flow_nodes + world.collectors
        if uniform:
            # a uniform stream loses nothing, exactly; the computed sums and integrals are checked against zero
            blocks.checks += checks.uniform_stream(world, values, [totals[t] for t in outputs])
            blocks.checks += checks.uniform_stream_gauss(world, gauss_values)
            totals = {t: ZERO for t in times}
            holder_heats = {h: {t: ZERO for t in times} for h in holders}
            extra = ZERO
        else:
            disagreement = max(abs(values[h][k] - gauss_values[h][k]) for h in holders for k in range(len(outputs)))
            extra = 4 * disagreement
            holder_heats = {h: dict(zip(times, [ZERO] + values[h])) for h in holders}
            blocks.checks += checks.holder_sums(world, {h: values[h] for h in holders},
                                                {h: gauss_values[h] for h in holders}, [totals[t] for t in outputs], outputs)
            blocks.checks += checks.first_holder_by_dilogarithm(world, {h: values[h] for h in holders}, outputs)
        table = flow_series(world, times, states, totals, 5, holder_heats=holder_heats, heat_extra=extra)
        blocks.worlds[name] = publish_world(times, table)
        honest_heats[name] = {h: [holder_heats[h][t] for t in outputs] for h in holders}
        honest_totals[name] = [totals[t] for t in outputs]
        blocks.checks += checks.conservation(world)
        blocks.checks += checks.reversal(inputs, world)
        blocks.checks += checks.second_propagator(world)
        blocks.checks += checks.total_by_portions(inputs, world, [totals[t] for t in outputs], outputs)
        blocks.checks += checks.emulate_flow(inputs, world)
    rows, series, reported = plants.arm5(inputs, plan, honest_heats, honest_totals)
    blocks.plants += rows
    blocks.planted_series.update(series)
    blocks.plants_reported += reported
    blocks.checks += throughput_rows(inputs, 5)
    return blocks


# ---- arm 6 ----------------------------------------------------------------------------------------------------------

def arm6(inputs, plan):
    blocks = Blocks()
    zs = set()
    for name in inputs.worlds_of(6):
        world = inputs.worlds[name]
        times = [exact(t) for t in world.output_floats()]
        outputs = times[1:]
        states = flow_states(world, times)
        totals = flow_totals(world, times, states)
        values, spread = heats.by_tanh_sinh(world, outputs)
        gauss_values = heats.by_gauss(world, outputs)
        everything = world.flow_nodes + world.collectors + [heats.FACE]
        extra = 4 * max(abs(values[h][k] - gauss_values[h][k]) for h in everything for k in range(len(outputs)))
        blocks.checks += checks.holder_sums(world, values, gauss_values, [totals[t] for t in outputs], outputs)
        if is_still(world):
            (a, b, _), = world.faces
            wells = {x: plants.TwoWells(world.rt, world.start[x][a], world.start[x][b], world.volumes[a],
                                        world.volumes[b], table[x])
                     for _, _, table in world.faces for x in crossing_species(world)}
            face = {t: sum((w.lost(w.moved(t)) for w in wells.values()), ZERO) for t in times}
            worst = max(abs(face[t] - v) / scales.heat_scale(world, t) for t, v in zip(outputs, values[heats.FACE]))
            blocks.checks.append(checks.row(f"9 arm 6 at Q = 0: {name}, the face's heat by D(m*) against its integral (over s_F)",
                                            worst, checks.DIGITS_40))
            extra = ZERO
            totals = face                    # LAWS section 8: the total is H_face alone
            blocks.checks += checks.still_face(world)
        else:
            face = dict(zip(times, [ZERO] + values[heats.FACE]))
        table = flow_series(world, times, states, totals, 6, face_heats=face, heat_extra=extra)
        blocks.worlds[name] = publish_world(times, table)
        blocks.checks += checks.conservation(world)
        blocks.checks += checks.reversal(inputs, world)
        blocks.checks += checks.second_propagator(world)
        blocks.checks += checks.closed_form_face(world)
        blocks.checks += checks.emulate_flow(inputs, world)
        for run in inputs.runs_of(arm=6, world=name):
            for x in crossing_species(world):
                (a, b, faces_table), = world.faces
                zs.add(faces_table[x] * (1 / world.volumes[a] + 1 / world.volumes[b]) * inputs.step(run))
    rows, series, reported, planted_order = plants.arm6(inputs, plan)
    blocks.plants += rows
    blocks.planted_series.update(series)
    blocks.plants_reported += reported
    blocks.checks.append(checks.row("P19: the planted order is at most p - 3/4", planted_order, Decimal("1.25")))
    blocks.checks += checks.stability_function("arm 6's face step", sorted(zs))
    blocks.checks += throughput_rows(inputs, 6)
    return blocks


__all__ = ["Decimal"]
