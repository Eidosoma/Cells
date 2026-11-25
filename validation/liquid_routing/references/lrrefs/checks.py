"""SPEC section 9's checks (as Amendment 1 reads check 10), every one in decimal, with its residual and its bound.

A row is {"name", "residual", "bound", "passes"}. A check that compares two decimals asks for agreement to 1e-50 of the
quantity's scale; an integral's bound is 1e-40 of s_F, far inside the 1e-12 that SPEC section 3 asks for.
"""

import decimal
import math
from decimal import Decimal

from . import emulation, flow, heats, propagator as pr, scales, splitting
from .arith import DEEP_DIGITS, HALF, ONE, TWO, U, ZERO, exact, phi, pi, precision, short
from .laws import (Chain, TwoWells, ars_constants, exchange, exchange_heat_by_phi, explicit_step, free_energy, portion,
                   portion_loss_by_logs)
from .plants import two_wells
from .quadrature import gauss_points

DIGITS_50 = Decimal(10) ** -50
DIGITS_40 = Decimal(10) ** -40


def row(name, residual, bound):
    return {"name": name, "residual": short(abs(residual)), "bound": short(bound), "passes": bool(abs(residual) <= bound)}


def at_steps(world, step):
    """The outputs of a world that `step` divides (t = 0 excluded)."""
    return [exact(t) for t in world.output_floats()[1:] if (exact(t) / step) == (exact(t) / step).to_integral_value()]


# ---- 1 and 2: the chain --------------------------------------------------------------------------------------

def equal_volumes(forward, backward):
    """Check 1. `forward` and `backward` are the equal-volume chain and its reverse; T starts in the same chamber."""
    rows = []
    chain = heats.ChainState(forward, "T")
    inlet, first, second, collector = chain.names
    volume, q = chain.v1, chain.q
    if chain.v1 != chain.v2:
        raise ValueError("not the equal-volume chain")
    t = volume / q
    e = ONE.exp()
    n = chain.n1
    for world, expected, label in ((forward, 1 - 2 / e, "forward, 1 - 2/e"), (backward, 1 - 1 / e, "reversed, 1 - 1/e")):
        state = pr.solve(world, "T", t, amounts={first: n}, inlet_on=False)
        collected = state[pr.Layout(world).index[collector]] / n
        rows.append(row(f"1 equal volumes: {world.name} {label}, by the propagator", collected - expected, DIGITS_50))
        if world is forward:
            closed = Chain(n, ZERO, volume, volume, q, ZERO).state(t)[2] / n
        else:
            closed = Chain(ZERO, n, volume, volume, q, ZERO).state(t)[2] / n
        rows.append(row(f"1 equal volumes: {world.name} {label}, by the closed form", closed - expected, DIGITS_50))
    worst = ZERO
    a = q / volume
    for m in range(1, 9):
        g = [[ZERO] * m for _ in range(m)]
        for i in range(m):
            g[i][i] = -a
            if i:
                g[i][i - 1] = a
        for factor in (HALF, ONE, 2 * ONE, 4 * ONE):
            time = factor * t
            p = pr.expm(g, time)
            at = a * time
            term = (-at).exp()
            for j in range(m):
                worst = max(worst, abs(p[j][0] - term))
                term = term * at / (j + 1)
    rows.append(row("1 equal volumes: m = 1 to 8 equal chambers in series, by the propagator", worst, DIGITS_50))
    return rows


def unequal_volumes(chains, base):
    """Check 2. `chains` are chain worlds (any volumes); `base` the equal-volume chain whose limit is taken."""
    rows = []
    for world in chains:
        worst = ZERO
        for x in world.species:
            state = heats.ChainState(world, x)
            for t in [exact(v) for v in world.output_floats()[1:]]:
                _, first, second, collector = state.names
                closed = dict(zip((first, second, collector), state.chain.state(t)))
                honest = flow.amounts(world, x, t)
                for name, value in closed.items():
                    worst = max(worst, abs(value - honest[name]) / abs(honest[name]))
        rows.append(row(f"2 unequal volumes: closed form against the propagator, {world.name}, every entry (relative)",
                        worst, DIGITS_50))
    chain = heats.ChainState(base, "T")
    worst_ratio, worst_slope, worst_state = ZERO, ZERO, ZERO
    for t in (chain.v1 / chain.q / 2, chain.v1 / chain.q, 2 * chain.v1 / chain.q):
        confluent = Chain(chain.n1, chain.n2, chain.v1, chain.v1, chain.q, chain.x)
        limit = confluent.difference_quotient(t)
        at = confluent.a * t
        previous = None
        for k in range(10, 41):
            eps = TWO ** -k
            near = Chain(chain.n1, chain.n2, chain.v1, chain.v1 * (1 + eps), chain.q, chain.x)
            gap = near.difference_quotient(t) / limit - 1
            # E = e^(-at) (e^(eta t) - 1)/eta with eta = a eps/(1 + eps): the relative gap is eta t/2 + (eta t)^2/6 + ...
            worst_slope = max(worst_slope, abs(gap / eps - at / 2) / (eps * (1 + at) ** 2))
            if previous is not None:
                worst_ratio = max(worst_ratio, abs(previous / gap - 2) / (2 * eps))
            previous = gap
            state = [abs(a - b) for a, b in zip(near.state(t), confluent.state(t))]
            worst_state = max(worst_state, max(state) / (eps * (chain.n1 + chain.n2)))
    rows.append(row("2 unequal volumes: E's gap over 2^-k tends to at/2 (k = 10 to 40), error over 2^-k (1 + at)^2",
                    worst_slope, ONE))
    rows.append(row("2 unequal volumes: successive gaps fall by 2 (k = 10 to 40), error over 2^(1 - k)", worst_ratio, ONE))
    rows.append(row("2 unequal volumes: the chain's amounts tend to the confluent form at first order, gap over 2^-k N",
                    worst_state, ONE))
    return rows


# ---- 3 and 4: the generators -----------------------------------------------------------------------------------

def conservation(world):
    """Check 3 for one network."""
    rows = []
    layout = pr.Layout(world)
    worst_column, worst_supply = ZERO, ZERO
    for start in [ZERO] + world.switch_times():
        for x in world.species:
            g = pr.generator(world, x, start, layout)
            for j, name in enumerate(layout.names):
                total = sum((g[i][j] for i in range(layout.size)), ZERO)
                if name in world.inlets:
                    supply = sum((q for s, _, q in world.link_rates(start) if s == name), ZERO)
                    worst_supply = max(worst_supply, abs(total - supply))
                else:
                    worst_column = max(worst_column, abs(total))
        for node in world.flow_nodes:
            inflow = sum((q for _, t, q in world.link_rates(start) if t == node), ZERO)
            outflow = sum((q for s, _, q in world.link_rates(start) if s == node), ZERO)
            worst_supply = max(worst_supply, abs(inflow - outflow))
    rows.append(row(f"3 conservation: {world.name}, the nodes' columns sum to zero", worst_column, Decimal(10) ** -100))
    rows.append(row(f"3 conservation: {world.name}, an inlet's column is its supply and each node's flows balance",
                    worst_supply, Decimal(10) ** -100))
    worst_amount, worst_volume = ZERO, ZERO
    for t in [exact(v) for v in world.output_floats()[1:]]:
        for x in world.species:
            state = flow.amounts(world, x, t)
            total = sum(state.values(), ZERO)
            expected = world.start_total(x) + pr.supplied(world, x, t)
            worst_amount = max(worst_amount, abs(total - expected) / expected)
        volumes = flow.amounts(world, "volume", t)
        expected = sum(world.volumes.values(), ZERO) + pr.supplied(world, "volume", t)
        if expected != 0:
            worst_volume = max(worst_volume, abs(sum(volumes.values(), ZERO) - expected) / expected)
        for node in world.nodes:
            worst_volume = max(worst_volume, abs(volumes[node] - world.volumes[node]))
        for collector in world.collectors:
            worst_volume = max(worst_volume, abs(volumes[collector] - pr.collector_volume(world, t)))
    rows.append(row(f"3 conservation: {world.name}, amounts sum to the start plus the supplied (relative)",
                    worst_amount, DIGITS_50))
    rows.append(row(f"3 conservation: {world.name}, volumes sum to the start plus the supplied", worst_volume, DIGITS_50))
    return rows


def reversal(inputs, world):
    """Check 4 for one network: e^(-Gt) e^(Gt) = 1, and the registered steps compose."""
    rows = []
    layout = pr.Layout(world)
    worst_back, worst_steps = ZERO, ZERO
    steps = sorted({inputs.step(run) for run in inputs.runs if run["world"] == world.name and run["role"] != "expected refusal"})
    end = exact(world.end)
    seen = []
    for start in [ZERO] + world.switch_times():
        for x in world.species:
            g = pr.generator(world, x, start, layout)
            if g in seen:
                continue
            seen.append(g)
            for t in sorted({end, end / 2} | set(steps)):
                product = pr.matmul(pr.expm(g, -t), pr.expm(g, t))
                for i in range(layout.size):
                    for j in range(layout.size):
                        worst_back = max(worst_back, abs(product[i][j] - (ONE if i == j else ZERO)))
            whole = pr.expm(g, end)
            size = pr.largest(whole)
            for h in steps:
                one = pr.expm(g, h)
                halves = pr.matmul(pr.expm(g, h / 2), pr.expm(g, h / 2))
                worst_steps = max(worst_steps, max(abs(one[i][j] - halves[i][j]) for i in range(layout.size)
                                                   for j in range(layout.size)) / size)
                power = pr.identity(layout.size)
                for _ in range(int(end / h)):
                    power = pr.matmul(power, one)
                worst_steps = max(worst_steps, max(abs(whole[i][j] - power[i][j]) for i in range(layout.size)
                                                   for j in range(layout.size)) / size)
    rows.append(row(f"4 time reversal: {world.name}, e^(-Gt) e^(Gt) is the identity", worst_back, DIGITS_50))
    rows.append(row(f"4 time reversal: {world.name}, P(h)^S = P(Sh) for every registered h, and two halves make a step",
                    worst_steps, DIGITS_50))
    return rows


def second_propagator(world):
    """Every published amount by uniformization and by Taylor continuation, against scaling and squaring."""
    worst_uniform, worst_taylor = ZERO, ZERO
    for t in [exact(v) for v in world.output_floats()[1:]]:
        for x in world.species:
            honest = flow.amounts(world, x, t)
            jump = flow.amounts(world, x, t, method="uniformized")
            series = heats.chain_taylor_end(world, x, t)
            for name, value in honest.items():
                if value == 0:
                    if jump[name] != 0 or series[name] != 0:
                        worst_uniform = worst_taylor = ONE
                    continue
                worst_uniform = max(worst_uniform, abs(jump[name] - value) / abs(value))
                worst_taylor = max(worst_taylor, abs(series[name] - value) / abs(value))
    return [row(f"4 second method: {world.name}, every amount by uniformization (relative)", worst_uniform, DIGITS_50),
            row(f"4 second method: {world.name}, every amount by Taylor continuation (relative)", worst_taylor, DIGITS_50)]


# ---- 5: the f-ladder -----------------------------------------------------------------------------------------------

def f_ladder(world):
    """Check 5 at the exchange of `world`, with the exact state just before it."""
    event = world.events[0]
    wells = two_wells(world)
    n = wells.levels(wells.moved(exact(event["time_s"])))[0]
    volume = wells.v1
    level = exact(event["buffer_mM"]["T"])
    c = n / volume
    previous = None
    worst = ZERO
    for k in range(4, 13):
        f = TWO ** -k
        heat = exchange(world.rt, n, volume, f, level)[3]
        rest = heat - world.rt * volume * f * c * phi(level / c)
        if previous is not None:
            ratio = previous / rest
            last = abs(ratio - 4)
        previous = rest
        leading = -world.rt * volume * f * f * (level - c) ** 2 / (2 * c)
        worst = max(worst, abs(rest / leading - 1) / f)
    two_forms = ZERO
    for k in range(1, 13):
        f = TWO ** -k
        one = exchange(world.rt, n, volume, f, level)[3]
        other = exchange_heat_by_phi(world.rt, n, volume, f, level)
        two_forms = max(two_forms, abs(one - other) / one)
    return [row(f"5 f-ladder: {world.name}, the remainder falls by 4 (the last halving), to within 2^-4", last, TWO ** -4),
            row(f"5 f-ladder: {world.name}, the remainder over -RT V f^2 (x - c)^2/(2c) is 1 to first order in f, error over f",
                worst, ONE),
            row(f"5 f-ladder: {world.name}, the two forms of H_ev (relative)", two_forms, DIGITS_50)]


# ---- 6, 7 and 10: two wells -------------------------------------------------------------------------------------------

def wells_by_propagator(world, t):
    """The two-well levels at t by the propagator of the linear system."""
    wells = two_wells(world)
    g = [[-wells.pa / wells.v1, wells.pa / wells.v2], [wells.pa / wells.v1, -wells.pa / wells.v2]]
    return pr.matvec(pr.expm(g, t), [wells.n1, wells.n2])


def affinity_integral(wells, m):
    """The integral of the affinity over the moved amount by two quadratures: (tanh-sinh, graded Gauss).

    A(s) is singular at s = -n2 (and s = n1): the rules are refined only where that lies close to the interval.
    """
    with precision(heats.QUAD_DIGITS):
        near = m / min(wells.n2, wells.n1)
        steps, depth = (24, 4) if near <= 1 else (128, 8)
        while near > 1:
            near /= 2
            depth += 1
        one = sum((w * wells.affinity(s) for s, w, _ in heats.tanh_sinh(steps).points(ZERO, m)), ZERO)
        two = sum((w * wells.affinity(s) for s, w in gauss_points(heats.gauss(), ZERO, m, depth)), ZERO)
    return one, two


def affinity_slope_at_zero(wells):
    """dD/dm at m = 0 by a centred difference of D."""
    with precision(DEEP_DIGITS):
        step = min(wells.n1, wells.n2) * Decimal(10) ** -45
        return (wells.lost(step) - wells.lost(-step)) / (2 * step)


def two_well_checks(inputs, world, times, steps_of_scheme=()):
    """Check 6 for one two-well world at `times` (the steps of arm 1, the compare times of arm 2)."""
    wells = two_wells(world)
    worst_levels, worst_integral, worst_gauss = ZERO, ZERO, ZERO
    for t in times:
        closed = wells.levels(wells.moved(t))
        by_matrix = wells_by_propagator(world, t)
        worst_levels = max(worst_levels, max(abs(a - b) / a for a, b in zip(closed, by_matrix)))
        one, two = affinity_integral(wells, wells.moved(t))
        honest = wells.lost(wells.moved(t))
        worst_integral = max(worst_integral, abs(one - honest) / honest)
        worst_gauss = max(worst_gauss, abs(two - honest) / honest)
    for h in steps_of_scheme:
        m = wells.moved_by_scheme(h)
        one, two = affinity_integral(wells, m)
        honest = wells.lost(m)
        worst_integral = max(worst_integral, abs(one - honest) / honest)
        worst_gauss = max(worst_gauss, abs(two - honest) / honest)
        stepped = explicit_step([wells.n1, wells.n2], h,
                                lambda y: [-wells.pa * (y[0] / wells.v1 - y[1] / wells.v2),
                                           wells.pa * (y[0] / wells.v1 - y[1] / wells.v2)])
        worst_levels = max(worst_levels, max(abs(a - b) / a for a, b in zip(stepped, wells.levels(m))))
    slope = affinity_slope_at_zero(wells)
    return [row(f"6 two wells: {world.name}, the closed form against the propagator, and one scheme step by its stages "
                "(relative)", worst_levels, DIGITS_50),
            row(f"6 two wells: {world.name}, D(m) is the integral of the affinity, by tanh-sinh (relative)",
                worst_integral, DIGITS_40),
            row(f"6 two wells: {world.name}, D(m) is the integral of the affinity, by graded Gauss (relative)",
                worst_gauss, DIGITS_40),
            row(f"6 two wells: {world.name}, D'(0) = A(0) (relative)", slope / wells.affinity(ZERO) - 1,
                Decimal(10) ** -60)]


def request_state(world, time, expected):
    """Check 6's last clause: the exact solution holds `expected` at `time` to the declared doubles' rounding."""
    wells = two_wells(world)
    levels = wells.levels(wells.moved(time))
    half_ulps = sum(exact(math.ulp(float(n))) / 2 for n in (wells.n1, wells.n2))
    bound = half_ulps * (1 + (-(wells.k * time)).exp()) / 2
    worst = max(abs(a - b) for a, b in zip(levels, expected))
    return [row(f"6 two wells: {world.name} holds {expected[0]} and {expected[1]} fmol at {time} s, to the declared doubles' "
                "rounding", worst, bound)]


def stability_function(name, zs):
    """Check 7 at every registered z: 0 <= R(z) - e^(-z) <= z^3/6."""
    worst_low, worst_high = None, ZERO
    for z in zs:
        gap = TwoWells.stability(z) - (-z).exp()
        worst_low = gap if worst_low is None else min(worst_low, gap)
        worst_high = max(worst_high, gap / (z ** 3 / 6))
    return [row(f"7 R(z): {name}, R(z) - e^(-z) is not negative (its most negative value)", min(worst_low, ZERO), ZERO),
            row(f"7 R(z): {name}, R(z) - e^(-z) over z^3/6, the largest", worst_high, ONE)]


def default_law(inputs, arm):
    """Check 10 (Amendment 1, item 1): (rows of `checks`, rows of `reported`)."""
    checks, reported = [], []
    for run in inputs.runs:
        if run["heat"] != "default" or run["arm"] != arm or run["variant"] is not None:
            continue
        world = inputs.worlds[run["world"]]
        wells = two_wells(world)
        h = inputs.step(run)
        z = wells.k * h
        label = f"{world.name}|{float(h)!r}"
        by_weight = wells.default_heat_by_weight(h)
        two_well = wells.default_heat(h)
        m = wells.moved_by_scheme(h)
        lost = wells.lost(m)
        ratio = (two_well - lost) / (-wells.leading_constant() * z * z * lost)
        forms = row(f"10 the default heat's law: {label}, the J^2/W form equals the two-well form (relative)",
                    by_weight / two_well - 1, DIGITS_50)
        remainder = row(f"10 the default heat's law: {label}, |H_def - D(m_R)| within B_def", abs(two_well - lost),
                        wells.default_bound(h))
        leading = row(f"10 the default heat's law: {label}, (H_def - D) over -C2 z^2 D, within 8z of 1", ratio - 1, 8 * z)
        inside = run["role"] == "judged"
        if run["role"] == "expected stop" and arm == 2 and _is_small_stop(wells, h):
            # Amendment 1, item 1: the `eq-mid` stop is asked for by neither list.
            continue
        checks.extend([forms, remainder])
        if inside and arm == 1:
            checks.append(leading)
        if not inside:
            reported.extend([forms, remainder, leading])
    return checks, reported


def _is_small_stop(wells, h):
    """A stop whose start lies inside the expansion's domain (the moved amount is small against the lower well's)."""
    m = wells.moved_by_scheme(h)
    return m / min(wells.n1, wells.n2) <= Decimal("0.25")


# ---- 8: heats ------------------------------------------------------------------------------------------------------------

def portion_checks(rt):
    """Check 8's portions: 1 mM then 3 mM, 1 pL each, and the reverse order."""
    one = portion(rt, ZERO, ZERO, ONE, ONE)
    two = portion(rt, one[0], one[1], ONE, 3 * ONE)
    back_one = portion(rt, ZERO, ZERO, ONE, 3 * ONE)
    back_two = portion(rt, back_one[0], back_one[1], ONE, ONE)
    expected = rt * (3 * (3 * ONE).ln() - 4 * (2 * ONE).ln())
    by_logs = portion_loss_by_logs(rt, one[0], one[1], ONE, 3 * ONE)
    return [row("8 heat: the second portion (1 mM then 3 mM, 1 pL each) loses RT (3 ln 3 - 4 ln 2) (relative)",
                two[2] / expected - 1, DIGITS_50),
            row("8 heat: the same loss by the first form (relative)", by_logs / expected - 1, DIGITS_50),
            row("8 heat: the first portion loses 0", abs(one[2]) + abs(back_one[2]), ZERO),
            row("8 heat: the order of two portions leaves the second's loss unchanged (relative)",
                back_two[2] / two[2] - 1, DIGITS_50)]


def collector_total(world, entries):
    """Check 8, arm 4: the cumulative loss of a portion-fed collector is its state function.

    `entries` is [(volume, level)] in order of arrival.
    """
    n = volume = total = ZERO
    supplied = ZERO
    for v, x in entries:
        n, volume, loss, _, _ = portion(world.rt, n, volume, v, x)
        total += loss
        supplied += v * (world.rt * x * (x.ln() - 1))
    state_function = supplied - free_energy(world.rt, n, volume)
    scale = scales.heat_scale(world, exact(world.end))
    return [row(f"8 heat: {world.name}, the portions' losses sum to the state function (over s_F)",
                (total - state_function) / scale, DIGITS_50)]


def holder_sums(world, values, gauss_values, totals, outputs):
    """Check 8, arms 5 and 6: Sigma H_holder (+ H_face) = H_tot, and the two quadratures agree (over s_F)."""
    worst_sum, worst_gauss_sum, worst_pair = ZERO, ZERO, ZERO
    for k, t in enumerate(outputs):
        scale = scales.heat_scale(world, t)
        worst_sum = max(worst_sum, abs(sum((v[k] for v in values.values()), ZERO) - totals[k]) / scale)
        worst_gauss_sum = max(worst_gauss_sum, abs(sum((v[k] for v in gauss_values.values()), ZERO) - totals[k]) / scale)
        for name in values:
            worst_pair = max(worst_pair, abs(values[name][k] - gauss_values[name][k]) / scale)
    return [row(f"8 heat: {world.name}, the holders' (and the face's) heats sum to H_tot, tanh-sinh (over s_F)",
                worst_sum, DIGITS_40),
            row(f"8 heat: {world.name}, the holders' (and the face's) heats sum to H_tot, graded Gauss (over s_F)",
                worst_gauss_sum, DIGITS_40),
            row(f"8 heat: {world.name}, the two quadratures agree on every holder (over s_F)", worst_pair, DIGITS_40)]


def total_by_gauss(world, totals, outputs):
    """H_tot of a flow world by the integral of the holders' rates (an independent route to the state function).

    At the first output and at each output that at least doubles the last one used, and at the end.
    """
    chosen = [outputs[0]]
    for t in outputs[1:]:
        if t >= 2 * chosen[-1]:
            chosen.append(t)
    if chosen[-1] != outputs[-1]:
        chosen.append(outputs[-1])
    values = heats.by_gauss(world, chosen)
    worst = ZERO
    for k, t in enumerate(chosen):
        scale = scales.heat_scale(world, t)
        worst = max(worst, abs(sum((v[k] for v in values.values()), ZERO) - totals[outputs.index(t)]) / scale)
    return [row(f"8 heat: {world.name}, H_tot by the integral of every holder's rate, at {len(chosen)} outputs (over s_F)",
                worst, DIGITS_40)]


def total_by_portions(inputs, world, totals, outputs):
    """H_tot of a flow world by the ideal mixing of finite portions, at every registered step (decimal)."""
    worst = ZERO
    for step in sorted({inputs.step(run) for run in inputs.runs
                        if run["world"] == world.name and run["role"] != "expected refusal"}):
        for t in at_steps(world, step)[-1:]:
            heat = sum(flow.portion_heats(world, step, t).values(), ZERO)
            worst = max(worst, abs(heat - totals[outputs.index(t)]) / scales.heat_scale(world, t))
    return [row(f"8 heat: {world.name}, H_tot by finite portions at every registered step (over s_F)", worst, DIGITS_50)]


def uniform_stream(world, values, totals):
    """Check 8: a uniform stream loses nothing."""
    worst = max([abs(v) for v in totals] + [abs(v) for series in values.values() for v in series])
    return [row(f"8 heat: {world.name}, a uniform stream loses nothing (the largest |H|, pJ)", worst, Decimal(10) ** -60)]


def uniform_stream_gauss(world, values):
    worst = max([ZERO] + [abs(v) for series in values.values() for v in series])
    return [row(f"8 heat: {world.name}, a uniform stream loses nothing, by the other quadrature (the largest |H|, pJ)",
                worst, Decimal(10) ** -60)]


def dilogarithm(z):
    """Li2(z) for z <= 0, by the series after Landen's transformation and the inversion."""
    if z == 0:
        return ZERO
    if z < -1:
        return -pi() ** 2 / 6 - (-z).ln() ** 2 / 2 - dilogarithm(1 / z)
    if z > 0:
        raise ValueError("z <= 0 only")
    w = z / (z - 1)                 # in (0, 1/2]
    total, power, k = ZERO, ONE, 0
    tiny = Decimal(10) ** -(decimal.getcontext().prec + 2)
    while True:
        k += 1
        power *= w
        term = power / (k * k)
        total += term
        if term <= tiny:
            break
    return -total - (1 - z).ln() ** 2 / 2


def first_holder_by_dilogarithm(world, values, outputs):
    """H of the first chamber of a chain in closed form: RT V [w (1 - e^(-at)) + x (Li2(-q) - Li2(-q e^(-at)))].

    w = c(0) - x and q = w/x. It is the integral of RT Q (x ln(x/y) - x + y) with y = x + w e^(-at): a third method for
    one of the holders, which knows nothing of the quadratures.
    """
    (species,) = world.species if len(world.species) == 1 else (None,)
    if species is None:
        return []
    state = heats.ChainState(world, species)
    if state.permeance != 0 or state.x == 0:
        return []
    _, first, _, _ = state.names
    a = state.q / state.v1
    w = state.n1 / state.v1 - state.x
    if w <= 0:
        return []
    worst = ZERO
    with precision(heats.QUAD_DIGITS):
        q = w / state.x
        start = dilogarithm(-q)
        for k, t in enumerate(outputs):
            decay = (-(a * t)).exp()
            closed = world.rt * state.v1 * (w * (1 - decay) + state.x * (start - dilogarithm(-q * decay)))
            worst = max(worst, abs(closed - values[first][k]) / scales.heat_scale(world, t))
    return [row(f"8 heat: {world.name}, H_{first} in closed form by the dilogarithm (over s_F)", worst, DIGITS_40)]


# ---- 9: labels, and arm 6 without flow ---------------------------------------------------------------------------------

def label_sums(world):
    worst = ZERO
    spec = world.labels
    for t in [exact(v) for v in world.output_floats()[1:]]:
        honest = flow.amounts(world, spec["species"], t)
        labels = {label: flow.label_amounts(world, label, t) for label in spec["names"]}
        for name, value in honest.items():
            worst = max(worst, abs(sum((labels[label][name] for label in spec["names"]), ZERO) - value) / abs(value))
    return [row(f"9 labels: {world.name}, the labels of every holder sum to its species (relative)", worst, DIGITS_50)]


def still_face(world):
    """Arm 6 at Q = 0 is the two wells of LAWS section 1."""
    (a, b, table), = world.faces
    worst = ZERO
    for x in world.species:
        permeance = table[x]
        wells = TwoWells(world.rt, world.start[x][a], world.start[x][b], world.volumes[a], world.volumes[b], permeance) \
            if permeance != 0 else None
        for t in [exact(v) for v in world.output_floats()[1:]]:
            honest = flow.amounts(world, x, t)
            if wells is None:
                expected = (world.start[x][a], world.start[x][b])
            else:
                expected = wells.levels(wells.moved(t))
            worst = max(worst, abs(honest[a] - expected[0]) / expected[0], abs(honest[b] - expected[1]) / expected[1])
    return [row(f"9 arm 6 at Q = 0: {world.name} is the two wells (relative)", worst, DIGITS_50)]


def closed_form_face(world):
    """Arm 6's linear system by its eigenvalues (a closed form) against the propagator."""
    worst = ZERO
    for x in world.species:
        state = heats.ChainState(world, x)
        for t in [exact(v) for v in world.output_floats()[1:]]:
            honest = flow.amounts(world, x, t)
            for name, value in state.amounts(t).items():
                gap = abs(value - honest[name])
                worst = max(worst, gap / abs(honest[name]) if honest[name] != 0 else gap)
    return [row(f"9 arm 6: {world.name}, every amount by the eigenvalues of the two-node system (relative)", worst,
                DIGITS_50)]


# ---- 11: the rounding counts ----------------------------------------------------------------------------------------------

class Fractions:
    """The largest fraction of a bound, by quantity."""

    def __init__(self):
        self.table = {}

    def note(self, quantity, error, bound):
        fraction = abs(error) / bound if bound != 0 else (ZERO if error == 0 else Decimal(10) ** 9)
        self.table[quantity] = max(self.table.get(quantity, ZERO), fraction)

    def rows(self, name):
        return [row(f"11 rounding counts: {name}, {quantity}, the largest fraction of the bound", value, ONE)
                for quantity, value in sorted(self.table.items())]


def emulate_flow(inputs, world):
    """The emulated flow world at every registered step against the references (and arm 6's decimal Strang map)."""
    fractions = Fractions()
    steps = sorted({inputs.step(run) for run in inputs.runs
                    if run["world"] == world.name and run["role"] not in ("expected refusal",)})
    m_n, m_h, m_q = scales.m_flow(world), scales.m_heat(world), scales.m_label(world)
    has_face = bool(world.faces)
    outputs = [exact(t) for t in world.output_floats()[1:]]
    references = {t: {x: flow.amounts(world, x, t) for x in world.species} for t in outputs}
    totals = {t: flow.total_heat(world, t, references[t]) for t in outputs}
    crossing = sorted({x for _, _, table in world.faces for x, p in table.items() if p != 0})
    uniform = is_uniform(world)
    end_volume = pr.collector_volume(world, exact(world.end))
    for step in steps:
        run = emulation.FlowEmulation(world, step)
        wanted = {t: int(t / step) for t in at_steps(world, step)}
        splits = {x: splitting.split_run(world, x, step, list(wanted), "strang") for x in crossing}
        labels = {}
        if world.labels:
            labels = {t: {label: flow.label_amounts(world, label, t) for label in world.labels["names"]} for t in wanted}
        for t, count in sorted(wanted.items()):
            while run.count < count:
                run.advance()
            steps_taken = count
            count_n = m_n + (scales.M_FACE if has_face else 0)
            for x in world.species:
                total = scales.total_amount(world, x, t)
                expected = splits[x][t] if x in crossing else references[t][x]
                bound = scales.rounding(count_n, steps_taken, total)
                for node in world.nodes:
                    if world.sites and x == world.sites["ligand"] and node == world.sites["node"]:
                        continue
                    fractions.note("amounts", exact(run.n[x][node]) - expected[node], bound)
                for collector in world.collectors:
                    fractions.note("amounts", exact(run.collected[x]) - expected[collector], bound)
                fractions.note("supplied", exact(run.supplied[x]) - pr.supplied(world, x, t), bound)
                sums = sum((exact(v) for v in run.n[x].values()), ZERO) + exact(run.collected[x]) - exact(run.supplied[x])
                fractions.note("sums", sums - world.start_total(x), bound)
            if end_volume != 0:
                fractions.note("volume", exact(run.collector_volume) - pr.collector_volume(world, t),
                               scales.rounding(count_n, steps_taken, end_volume))
            heat = sum((exact(v) for v in run.heat.values()), ZERO) + exact(run.face_heat)
            scale = scales.heat_scale(world, t)
            if not has_face:
                fractions.note("H_tot", heat - totals[t], scales.rounding(m_n + m_h, steps_taken, scale))
                if uniform:
                    eta = scales.rounding(m_n, steps_taken, max(
                        scales.total_amount(world, x, t) / world.start[x][node] for x in world.species
                        for node in world.start[x]))
                    total_n = sum((scales.total_amount(world, x, t) for x in world.species), ZERO)
                    fractions.note("H_tot against the uniform bound (U)", heat,
                                   8 * world.rt * total_n * (steps_taken + 1) * eta * eta)
            else:
                # the energy identity on the run's own rows
                lost = flow.supplied_free_energy(world, t)
                volume = exact(run.collector_volume)
                for x in world.species:
                    for node in world.nodes:
                        lost += free_energy(world.rt, world.start[x][node], world.volumes[node])
                        lost -= free_energy(world.rt, exact(run.n[x][node]), world.volumes[node])
                    if volume != 0:
                        lost -= free_energy(world.rt, exact(run.collected[x]), volume)
                fractions.note("energy identity", heat - lost,
                               scales.rounding(m_n + scales.M_FACE + m_h, steps_taken, scale))
            if labels:
                spec = world.labels
                bound = scales.rounding(m_q, steps_taken, scales.total_amount(world, spec["species"], t))
                for label in spec["names"]:
                    for node in world.nodes:
                        fractions.note("labels", exact(run.labels[label][node]) - labels[t][label][node], bound)
                    for collector in world.collectors:
                        fractions.note("labels", exact(run.collected_labels[label]) - labels[t][label][collector], bound)
                for node in world.nodes:
                    total = sum((exact(run.labels[label][node]) for label in spec["names"]), ZERO)
                    fractions.note("label sums", total - exact(run.n[spec["species"]][node]), bound)
                total = sum((exact(v) for v in run.collected_labels.values()), ZERO)
                fractions.note("label sums", total - exact(run.collected[spec["species"]]), bound)
    return fractions.rows(world.name)


def is_uniform(world):
    """Every node of a flow world at its inlet's level, for every species: a uniform stream."""
    if len(world.inlets) != 1 or not world.flow_nodes or world.faces or world.switch_times():
        return False
    inlet, = world.inlets
    return all(world.start[x].get(node, ZERO) == world.inlet_level(inlet, x, ZERO) * world.volumes[node]
               for x in world.species for node in world.nodes)


def emulate_wells(inputs, arm, label):
    """Arms 1 and 2 in binary64: one explicit step (or many), the exact and the default heat, the exchange."""
    fractions = Fractions()
    gamma, delta = (float(v) for v in ars_constants())
    for run in inputs.runs:
        if run["arm"] != arm or run["role"] not in ("judged", "recorded"):
            continue
        world = inputs.worlds[run["world"]]
        wells = two_wells(world)
        h = inputs.step(run)
        z = wells.k * h
        count = 1 if world.end == "one step" else int(exact(world.end) / h)
        n1, n2 = float(wells.n1), float(wells.n2)
        e1, e2 = wells.n1, wells.n2                    # the same scheme in decimal
        v1, v2, pa, rt, step = float(wells.v1), float(wells.v2), float(wells.pa), float(world.rt), float(h)
        heat, own, law = 0.0, ZERO, ZERO
        event = world.events[0] if world.events else None
        amount = world.start_total("T")
        scale = scales.heat_scale(world, ZERO)
        extra = ZERO
        for index in range(count):
            if event is not None and exact(event["time_s"]) == h * index:
                f, x = float(event["fraction"]), float(event["buffer_mM"]["T"])
                sample, supplied = f * n1, f * v1 * x
                after = n1 - sample + supplied
                c, c_after = n1 / v1, after / v1
                heat_ev = rt * v1 * c_after * ((1.0 - f) * emulation.phi_float(c, c_after)
                                               + f * emulation.phi_float(x, c_after))
                own_ev = exchange(world.rt, exact(n1), wells.v1, exact(f), exact(x))
                event_amount = amount + own_ev[1]
                fractions.note("exchange: sample, supplied", max(abs(exact(sample) - own_ev[0]), abs(exact(supplied) - own_ev[1])),
                               8 * U * event_amount)
                fractions.note("exchange: heat", exact(heat_ev) - own_ev[3], 32 * U * scale)
                n1 = after
                e1 = exchange(world.rt, e1, wells.v1, exact(event["fraction"]), exact(event["buffer_mM"]["T"]))[2]
                extra = 8 * U
                amount = event_amount
            before1, before2 = exact(n1), exact(n2)
            if run["heat"] == "exact":
                n1, n2, piece = emulation.exact_face_step(n1, n2, v1, v2, pa, step, gamma, delta, rt)
            else:
                n1, n2, piece = emulation.default_face_step(n1, n2, v1, v2, pa, step, gamma, delta, rt)
            heat += piece
            stage = TwoWells(world.rt, e1, e2, wells.v1, wells.v2, wells.pa)
            law += stage.default_heat(h)
            m = stage.moved_by_scheme(h)
            e1, e2 = e1 - m, e2 + m
            own += (free_energy(world.rt, before1, wells.v1) + free_energy(world.rt, before2, wells.v2)
                    - free_energy(world.rt, exact(n1), wells.v1) - free_energy(world.rt, exact(n2), wells.v2))
            s = index + 1
            bound = scales.rounding(scales.M_FACE, s, amount) + extra * amount
            fractions.note("amounts against the scheme", max(abs(exact(n1) - e1), abs(exact(n2) - e2)), bound)
            fractions.note("sum", exact(n1) + exact(n2) - (e1 + e2), bound)
            if run["heat"] == "exact":
                fractions.note("exact heat against its own rows", exact(heat) - own,
                               scales.rounding(scales.M_T3, s, scale) + extra * scale)
            else:
                fractions.note("default heat against its law", exact(heat) - law,
                               scales.rounding(scales.M_DEFAULT, s, scale) + extra * scale)
    return fractions.rows(label)


def emulate_portions(world, entries):
    """Arm 4's portions in binary64."""
    fractions = Fractions()
    rows = emulation.portions(float(world.rt), [(float(v), float(x)) for v, x in entries])
    n = volume = total = ZERO
    end_volume = sum((v for v, _ in entries), ZERO)
    amount, supplied = ZERO, ZERO
    m_n, m_h = scales.m_flow(world), scales.m_heat(world)
    log = world.largest_log() + 1
    for k, ((v, x), (fn, fv, loss, cumulative)) in enumerate(zip(entries, rows)):
        n, volume, honest, _, _ = portion(world.rt, n, volume, v, x)
        total += honest
        amount += v * x
        steps = k + 1
        fractions.note("amounts", exact(fn) - n, scales.rounding(m_n, steps, amount))
        fractions.note("volume", exact(fv) - volume, scales.rounding(m_n, steps, end_volume))
        scale = world.rt * log * amount
        fractions.note("losses", exact(loss) - honest, scales.rounding(m_n + m_h, steps, scale))
        fractions.note("H_tot", exact(cumulative) - total, scales.rounding(m_n + m_h, steps, scale))
    return fractions.rows(world.name)

