"""The planted quantities of LAWS section 11, their sizes and their margins (CRITERIA section 6, SPEC section 5).

Every honest value, planted value, distance and expected tolerance is computed from the references alone.
A plan names the worlds, steps and times: CRITERIA section 6.1's for the registered inputs, this folder's own for the
invented ones.
"""

from decimal import Decimal

from . import flow, heats, propagator as pr, scales, splitting
from .arith import ONE, TWO, ZERO, exact, publish, short
from .laws import TwoWells, explicit_step, portion


def entry(plant, check, world, time, step, klass, honest, planted, tolerance, **extra):
    """One row of `plants`."""
    distance = abs(planted - honest)
    row = {"plant": plant, "check": check, "class": klass, "world": world,
           "time_s": None if time is None else float(time), "step_s": None if step is None else float(step),
           "honest": publish(honest), "planted": publish(planted), "distance": publish(distance)}
    if klass == "E":
        row.update({"expected_tolerance": "0", "margin": None, "no_margin": True})
    else:
        row.update({"expected_tolerance": publish(tolerance), "margin": publish(distance / tolerance),
                    "no_margin": False})
    row.update(extra)
    return row, distance


def best(candidates):
    """The entry of largest margin (distance / tolerance): [(time, honest, planted, tolerance)]."""
    return max(candidates, key=lambda c: abs(c[2] - c[1]) / c[3])


def two_wells(world):
    (a, b, table), = world.faces
    species, = world.species
    return TwoWells(world.rt, world.start[species][a], world.start[species][b], world.volumes[a], world.volumes[b],
                    table[species])


def series(times, values):
    return {"times_s": [float(t) for t in times], "value": [publish(v) for v in values]}


def key(world, step):
    return f"{world}|{float(step)!r}"


# ---- arm 1 -------------------------------------------------------------------------------------------------

def arm1(inputs, plan):
    rows, planted_series = [], {}

    # P14: k from V1 alone
    spec = plan["P14"]
    world = inputs.worlds[spec["world"]]
    wells = two_wells(world)
    amount = world.start_total("T")
    for run in inputs.runs_of(arm=1, world=world.name, role="judged", heat="exact"):
        h = inputs.step(run)
        z = wells.k * h
        honest = wells.moved(h)
        planted = wells.reach * (1 - wells.stability(h * wells.pa / wells.v1))
        tolerance = wells.reach * z ** 3 / 6 + scales.rounding(scales.M_FACE, 1, amount)
        for name, sign, start in (("n_T_1", -1, wells.n1), ("n_T_2", 1, wells.n2)):
            row, _ = entry("P14", name, world.name, h, h, "B", start + sign * honest, start + sign * planted, tolerance)
            rows.append(row)
        planted_series.setdefault("P14", {})[key(world.name, h)] = {
            "n_T_1": series([h], [wells.n1 - planted]), "n_T_2": series([h], [wells.n2 + planted])}

    # P15: a transfer that depends on the background
    for name in plan["P15"]["worlds"]:
        world = inputs.worlds[name]
        wells = two_wells(world)
        h = exact(plan["P15"]["step"])
        z = wells.k * h

        def slope(y):
            c1, c2 = y[0] / wells.v1, y[1] / wells.v2
            flux = wells.pa * ((c1 + c2) / 2) * (c1 / c2).ln()
            return [-flux, flux]

        after = explicit_step([wells.n1, wells.n2], h, slope)
        moved = wells.moved(h)
        tolerance = wells.reach * z ** 3 / 6 + scales.rounding(scales.M_FACE, 1, world.start_total("T"))
        for series_name, honest, planted in (("n_T_1", wells.n1 - moved, after[0]), ("n_T_2", wells.n2 + moved, after[1])):
            row, _ = entry("P15", series_name, name, h, h, "B", honest, planted, tolerance)
            rows.append(row)
        planted_series.setdefault("P15", {})[key(name, h)] = {
            "n_T_1": series([h], [after[0]]), "n_T_2": series([h], [after[1]])}

    # P16: the heat's weight at the step's start, m A(0), with m the scheme's transfer
    world = inputs.worlds[plan["P16"]["world"]]
    wells = two_wells(world)
    scale = scales.heat_scale(world, ZERO)
    for run in inputs.runs_of(arm=1, world=world.name, role="judged", heat="default"):
        h = inputs.step(run)
        m = wells.moved_by_scheme(h)
        tolerance = wells.default_bound(h) + scales.rounding(scales.M_DEFAULT, 1, scale)
        row, _ = entry("P16", "H_face", world.name, h, h, "B", wells.lost(m), m * wells.affinity(ZERO), tolerance,
                       heat="default")
        rows.append(row)
    run = inputs.runs_of(arm=1, world=world.name, role="judged", heat="exact")[0]
    h = inputs.step(run)
    m = wells.moved_by_scheme(h)
    row, _ = entry("P16", "H_face", world.name, h, h, "R", wells.lost(m), m * wells.affinity(ZERO),
                   scales.rounding(scales.M_T3, 1, scale), heat="exact")
    rows.append(row)
    return rows, planted_series, []


# ---- arm 2 -------------------------------------------------------------------------------------------------

def arm2(inputs, plan, exchange_heat):
    """P17's size and P8 event's missing heat. `exchange_heat` is {world: H_ev} of the exact solution."""
    rows = []
    spec = plan["P17"]
    world = inputs.worlds[spec["world"]]
    event = world.events[0]
    wells = two_wells(world)
    run = inputs.runs_of(arm=2, world=world.name, role="judged", heat="exact")[-1]
    h = inputs.step(run)
    time = exact(event["time_s"])
    fraction = exact(event["fraction"])
    honest = fraction * wells.levels(wells.moved(time))[0]
    planted = fraction * wells.levels(wells.moved(time + h))[0]
    row, _ = entry("P17", "sample", world.name, time, h, "R", honest, planted, 8 * scales.U * world.start_total("T"))
    rows.append(row)
    spec = plan["P8 event"]
    reported = [{"plant": "P8", "run": spec["run"], "world": spec["world"], "step_s": float(spec["step"]),
                 "times_s": [float(time)], "H_missing": [publish(exchange_heat[spec["world"]])]}]
    return rows, {}, reported


# ---- arm 3 -------------------------------------------------------------------------------------------------

def collected_without_mixing(world, species, time):
    """P2: n_first as honest, n_second(t) = n_second(0), n_K(t) = n_first(0) + Q x t - n_first(t)."""
    state = heats.ChainState(world, species)
    _, first, second, collector = state.names
    honest = flow.amounts(world, species, time)
    return {first: honest[first], second: state.n2,
            collector: state.n1 + state.q * state.x * time - honest[first]}


def first_order_chain(world, species, time):
    """P3: both chambers at k = Q/V_first, no volume moved: dn_B/dt = k n_A - k n_B, x as honest."""
    state = heats.ChainState(world, species)
    _, first, second, collector = state.names
    k = state.q / state.v1
    rest = state.q * state.x / k
    decay = (-(k * time)).exp()
    u1, u2 = state.n1 - rest, state.n2 - rest
    n1 = rest + u1 * decay
    n2 = rest + u2 * decay + k * u1 * time * decay
    return {first: n1, second: n2, collector: state.n1 + state.n2 + state.q * state.x * time - n1 - n2}


def outlet_share_labels(world, label, step, time):
    """P11: the label that reaches K when each half-step's portion takes the outlet node's share at its start."""
    state = heats.ChainState(world, world.labels["species"])
    _, _, outlet, collector = state.names
    species = world.labels["species"]
    half = step / 2
    total = ZERO
    t = ZERO
    while t < time:
        before = flow.amounts(world, species, t) if t > 0 else dict(world.start[species], **{collector: ZERO})
        after = flow.amounts(world, species, t + half)
        tag = flow.label_amounts(world, label, t) if t > 0 else flow.label_starts(world)[label]
        arriving = after[collector] - before[collector]
        total += arriving * (tag[outlet] / before[outlet])
        t += half
    return total


def arm3(inputs, plan):
    rows, planted_series = [], {}

    def n_tolerance(world, species, time, step):
        return scales.rounding(scales.m_flow(world), time / step, scales.total_amount(world, species, time))

    # P1: the chain in reverse order, both ways
    spec = plan["P1"]
    step, time = exact(spec["step"]), exact(spec["time"])
    one, two = (inputs.worlds[name] for name in spec["worlds"])
    value = {w.name: flow.amounts(w, "T", time)["K"] for w in (one, two)}
    for world, other in ((one, two), (two, one)):
        row, _ = entry("P1", "n_T_K", world.name, time, step, "R", value[world.name], value[other.name],
                       n_tolerance(world, "T", time, step))
        rows.append(row)

    # P2: no mixing in B
    spec = plan["P2"]
    step = exact(spec["step"])
    for name in spec["worlds"]:
        world = inputs.worlds[name]
        times = [exact(t) for t in world.output_floats()[1:] if exact(t) / step == (exact(t) / step).to_integral_value()]
        honest = {t: flow.amounts(world, "T", t) for t in times}
        planted = {t: collected_without_mixing(world, "T", t) for t in times}
        names = sorted(planted[times[0]])
        planted_series.setdefault("P2", {})[name] = {
            f"n_T_{i}": series(times, [planted[t][i] for t in times]) for i in names}
        for i in ("B", "K"):
            t, h, p, tolerance = best([(t, honest[t][i], planted[t][i], n_tolerance(world, "T", t, step)) for t in times])
            row, _ = entry("P2", f"n_T_{i}", name, t, step, "R", h, p, tolerance)
            rows.append(row)

    # P3: a first-order transfer, no volume moved
    spec = plan["P3"]
    step = exact(spec["step"])
    control = ZERO
    for name in (spec["equal"], spec["unequal"]):
        world = inputs.worlds[name]
        times = [exact(t) for t in world.output_floats()[1:] if exact(t) / step == (exact(t) / step).to_integral_value()]
        honest = {t: flow.amounts(world, "T", t) for t in times}
        planted = {t: first_order_chain(world, "T", t) for t in times}
        names = sorted(planted[times[0]])
        table = {f"n_T_{i}": series(times, [planted[t][i] for t in times]) for i in names}
        table["V_K"] = series(times, [ZERO for _ in times])
        planted_series.setdefault("P3", {})[name] = table
        if name == spec["unequal"]:
            for i in ("B", "K"):
                t, h, p, tolerance = best([(t, honest[t][i], planted[t][i], n_tolerance(world, "T", t, step))
                                           for t in times])
                row, _ = entry("P3", f"n_T_{i}", name, t, step, "R", h, p, tolerance)
                rows.append(row)
        else:
            control = max(abs(honest[t][i] - planted[t][i]) for t in times for i in names)
        end = exact(world.end)
        t, h, p, tolerance = best([
            (t, pr.collector_volume(world, t), ZERO,
             scales.rounding(scales.m_flow(world), t / step, pr.collector_volume(world, end))) for t in times])
        row, _ = entry("P3", "V_K", name, t, step, "R", h, p, tolerance)
        rows.append(row)

    # P4: a rate per species
    spec = plan["P4"]
    world, step = inputs.worlds[spec["world"]], exact(spec["step"])
    factor = ONE + TWO ** -20
    times = [exact(t) for t in world.output_floats()[1:] if exact(t) / step == (exact(t) / step).to_integral_value()]
    honest = {t: flow.amounts(world, "U", t) for t in times}
    planted = {t: flow.amounts(world, "U", t, rate_factor=factor) for t in times}
    names = sorted(planted[times[0]])
    planted_series["P4"] = {world.name: {f"n_U_{i}": series(times, [planted[t][i] for t in times]) for i in names}}
    for i in ("B", "K"):
        t, h, p, tolerance = best([(t, honest[t][i], planted[t][i], n_tolerance(world, "U", t, step)) for t in times])
        row, _ = entry("P4", f"n_U_{i}", world.name, t, step, "R", h, p, tolerance)
        rows.append(row)

    # P10: the honest rows at time 2t read at time t
    spec = plan["P10"]
    world, step, time = inputs.worlds[spec["world"]], exact(spec["step"]), exact(spec["time"])
    row, _ = entry("P10", "n_T_K", world.name, time, step, "R", flow.amounts(world, "T", time)["K"],
                   flow.amounts(world, "T", 2 * time)["K"], n_tolerance(world, "T", time, step))
    rows.append(row)

    # P11: a collector's portion at the outlet node's share
    spec = plan["P11"]
    world, step = inputs.worlds[spec["world"]], exact(spec["step"])
    labels = world.labels
    tag, = [label for label in labels["names"] if label != labels["base"]]
    times = [exact(t) for t in world.output_floats()[1:] if exact(t) / step == (exact(t) / step).to_integral_value()]
    honest = {t: flow.label_amounts(world, tag, t) for t in times}
    planted = {t: outlet_share_labels(world, tag, step, t) for t in times}
    name = f"label_{labels['species']}_{tag}"
    table = {f"{name}_K": series(times, [planted[t] for t in times])}
    for node in world.flow_nodes:
        table[f"{name}_{node}"] = series(times, [honest[t][node] for t in times])
    planted_series["P11"] = {key(world.name, step): table}
    t, h, p, tolerance = best([
        (t, honest[t]["K"], planted[t],
         scales.rounding(scales.m_label(world), t / step, scales.total_amount(world, labels["species"], t)))
        for t in times])
    row, _ = entry("P11", f"{name}_K", world.name, t, step, "R", h, p, tolerance)
    rows.append(row)

    # P8 flow: the heat missing from t = 0 to each possible stop row
    spec = plan["P8 flow"]
    world = inputs.worlds[spec["world"]]
    times = [exact(t) for t in world.output_floats()[1:]]
    reported = [{"plant": "P8", "run": spec["run"], "world": world.name, "step_s": float(spec["step"]),
                 "times_s": [float(t) for t in times],
                 "H_missing": [publish(flow.total_heat(world, t)) for t in times]}]
    return rows, planted_series, reported, control


# ---- arm 4 -------------------------------------------------------------------------------------------------

def arm4(inputs, plan):
    """P9: the collector starts as a node of 2^-10 pL at 1e-12 mM; the first portion's loss with that resident."""
    world = inputs.worlds[plan["P9"]["world"]]
    event = world.events[0]
    time = exact(event["time_s"])
    v = exact(event["volume_pL"])
    x = world.inlet_level(event["inlet"], "T", time)
    volume = TWO ** -10
    n = volume * exact(1e-12)
    loss = portion(world.rt, n, volume, v, x)[2]
    row, distance = entry("P9", "loss", world.name, time, None, "E", ZERO, loss, None)
    run = inputs.runs_of(world=world.name, role="judged")[0]
    row["step_s"] = float(inputs.step(run))
    return [row], {"P9": {world.name: {"loss": series([time], [loss])}}}, [], distance


# ---- arm 5 -------------------------------------------------------------------------------------------------

def arm5(inputs, plan, holder_heats, totals):
    """P5 and P7. `holder_heats` is {world: {holder: [heat at each output]}}, `totals` {world: [H_tot]}."""
    rows, planted_series = [], {}

    # P5: the stream's F as mu times its amount, on H_A of the chain
    world = inputs.worlds[plan["P5"]["world"]]
    outputs = [exact(t) for t in world.output_floats()[1:]]
    state = heats.ChainState(world, "T")
    _, first, second, collector = state.names
    runs = inputs.runs_of(world=world.name, role="judged")
    finest = min(inputs.step(run) for run in runs)
    u = state.n1 - state.v1 * state.x
    a = state.q / state.v1

    def extra(t):
        """RT times the integral of Q (x - y_A)."""
        return -world.rt * state.q * (u / state.v1) * (1 - (-(a * t)).exp()) / a

    def rate(t):
        y = state.x + (u / state.v1) * (-(a * t)).exp()
        return world.rt * state.q * (state.x * (state.x / y).ln() - state.x + y)

    # dr_A/dt = -RT Q a (y - x)^2 / y has one sign, so r_A is monotone and its total variation is its end change
    variation = abs(rate(ZERO) - rate(outputs[-1]))
    tolerance = 3 * (finest / 2) * variation
    honest = holder_heats[world.name][first]
    planted = [h + extra(t) for h, t in zip(honest, outputs)]
    planted_series["P5"] = {world.name: {f"H_{first}": series(outputs, planted)}}
    t, h, p, tolerance = best([(t, h, p, tolerance) for t, h, p in zip(outputs, honest, planted)])
    row, _ = entry("P5", f"H_{first}", world.name, t, finest, "S", h, p, tolerance,
                   step_error_model="3 (h/2) TV(r)", total_variation=publish(variation))
    rows.append(row)

    # P7: the heat of B as the start rate times h, at the finest step
    for name in plan["P7"]["worlds"]:
        world = inputs.worlds[name]
        outputs = [exact(t) for t in world.output_floats()[1:]]
        state = heats.ChainState(world, "T")
        inlet, first, second, collector = state.names
        finest = min(inputs.step(run) for run in inputs.runs_of(world=name, role="judged"))
        total, t, booked = ZERO, ZERO, []
        rates = world.link_rates(ZERO)
        for right in outputs:
            while t < right:
                if t == 0:
                    levels = {inlet: state.x, first: state.n1 / state.v1, second: state.n2 / state.v2,
                              collector: state.n2 / state.v2}
                else:
                    levels = state.levels(t)
                total += finest * flow.holder_rates(world, rates, levels)[second]
                t += finest
            booked.append(total)
        honest_total = totals[name]
        planted_total = [h + b - x for h, b, x in zip(honest_total, booked, holder_heats[name][second])]
        planted_series.setdefault("P7", {})[key(name, finest)] = {
            f"H_{second}": series(outputs, booked), "H_tot": series(outputs, planted_total)}
        candidates = []
        for t_out, h, p in zip(outputs, honest_total, planted_total):
            candidates.append((t_out, h, p, scales.rounding(scales.m_flow(world) + scales.m_heat(world), t_out / finest,
                                                           scales.heat_scale(world, t_out))))
        t, h, p, tolerance = best(candidates)
        row, _ = entry("P7", "H_tot", name, t, finest, "R", h, p, tolerance)
        rows.append(row)
    return rows, planted_series, []


# ---- arm 6 -------------------------------------------------------------------------------------------------

def arm6(inputs, plan):
    """P19: Lie splitting for Strang's, on n_T_A."""
    world = inputs.worlds[plan["P19"]["world"]]
    outputs = [exact(t) for t in world.output_floats()[1:]]
    steps = sorted({inputs.step(run) for run in inputs.runs_of(world=world.name, role="judged")}, reverse=True)
    reference = [flow.amounts(world, "T", t)["A"] for t in outputs]
    strang = []
    lie = {}
    for h in steps:
        rows_s = splitting.split_run(world, "T", h, outputs, "strang")
        rows_l = splitting.split_run(world, "T", h, outputs, "lie")
        strang.append([rows_s[t]["A"] for t in outputs])
        lie[h] = [rows_l[t]["A"] for t in outputs]
    d2, d1, estimate = splitting.halving_estimate(strang, 2)
    lie_d2, lie_d1, _ = splitting.halving_estimate([lie[h] for h in steps], 2)
    planted_order = splitting.order(lie_d2, lie_d1)
    strang_order = splitting.order(d2, d1)
    finest = steps[-1]
    tolerance = 3 * estimate
    t, h, p, tolerance = best([(t, r, p, tolerance) for t, r, p in zip(outputs, reference, lie[finest])])
    row, _ = entry("P19", "n_T_A", world.name, t, finest, "S", h, p, tolerance,
                   step_error_model="3 est of the decimal Strang map (p = 2)",
                   planted_order=publish(planted_order), order_limit="1.25",
                   strang_order=publish(strang_order), strang_d1=publish(d1), strang_d2=publish(d2))
    planted_series = {"P19": {key(world.name, h): {"n_T_A": series(outputs, lie[h])} for h in steps}}
    return [row], planted_series, [], planted_order


__all__ = ["Decimal", "short"]
