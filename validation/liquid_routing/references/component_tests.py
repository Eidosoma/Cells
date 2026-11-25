"""Tests of the writer's own parts, each alone, against results known independently of it.

    python -B -P component_tests.py --out DIR

Writes `component_tests.json` (deterministic) and exits with 1 if any test misses its bound. The parts are the ones where
errors hide: the propagator's scaling and squaring, the equal-rate chain, the integrable singularity as a trace goes to
zero, and arm 6's linear system; and the rate laws against the limit of finite portions.
"""

import argparse
import importlib.util
import json
import os
import sys
from decimal import Decimal, getcontext

HERE = os.path.dirname(os.path.abspath(__file__))


def load_package(name="lrrefs"):
    folder = os.path.join(HERE, name)
    spec = importlib.util.spec_from_file_location(name, os.path.join(folder, "__init__.py"),
                                                  submodule_search_locations=[folder])
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)


load_package()

from lrrefs import checks, flow, heats, laws, propagator as pr, quadrature, scales, splitting  # noqa: E402
from lrrefs.arith import ONE, ZERO, exact, phi, pi, precision, set_precision, short  # noqa: E402
from lrrefs.world import World  # noqa: E402

ROWS = []


def note(name, residual, bound):
    ROWS.append({"name": name, "residual": short(abs(residual)), "bound": short(bound),
                 "passes": bool(abs(residual) <= bound)})


TEN = Decimal(10)
DIGITS_100 = TEN ** -100
DIGITS_90 = TEN ** -90


# ---- 1. the propagator -----------------------------------------------------------------------------------------------

def sine_cosine(x):
    """sin and cos by their own Taylor series after halving x (no matrix in sight)."""
    halvings = 0
    while abs(x) > Decimal("0.01"):
        x /= 2
        halvings += 1
    square = x * x
    sine, cosine, term_s, term_c, k = x, ONE, x, ONE, 0
    while True:
        k += 1
        term_c = -term_c * square / ((2 * k - 1) * (2 * k))
        term_s = -term_s * square / ((2 * k) * (2 * k + 1))
        cosine += term_c
        sine += term_s
        if abs(term_s) < TEN ** -(getcontext().prec + 3):
            break
    for _ in range(halvings):
        sine, cosine = 2 * sine * cosine, cosine * cosine - sine * sine
    return sine, cosine


def propagator_tests():
    for at in (Decimal("1e-6"), ONE, Decimal(30), Decimal(300)):
        a = Decimal("0.125")
        t = at / a
        m = 6
        g = [[(-a if i == j else (a if j == i - 1 else ZERO)) for j in range(m)] for i in range(m)]
        p = pr.expm(g, t)
        worst = ZERO
        term = (-at).exp()
        for j in range(m):
            for column in range(m - j):
                worst = max(worst, abs(p[j + column][column] / term - 1))
            term = term * at / (j + 1)
        note(f"propagator: a Jordan block of six equal rates at at = {at} (relative, every entry)", worst, DIGITS_90)
    for w in (Decimal("0.3"), Decimal(7), Decimal(200)):
        g = [[ZERO, -w], [w, ZERO]]
        p = pr.expm(g, ONE)
        sine, cosine = sine_cosine(w)
        note(f"propagator: a rotation by {w} (complex rates) against the series of sin and cos",
             max(abs(p[0][0] - cosine), abs(p[1][0] - sine), abs(p[0][1] + sine)), TEN ** -98)
    # a stiff two-node exchange, in closed form
    for fast, slow in ((Decimal(1000), Decimal("1e-6")), (Decimal("3.7"), Decimal("0.02"))):
        g = [[-fast, slow], [fast, -slow]]
        t = Decimal("2.5")
        total = fast + slow
        decay = (-(total * t)).exp()
        expected = [[(slow + fast * decay) / total, slow * (1 - decay) / total],
                    [fast * (1 - decay) / total, (fast + slow * decay) / total]]
        p = pr.expm(g, t)
        note(f"propagator: a stiff exchange {fast}, {slow} in closed form (relative)",
             max(abs(p[i][j] / expected[i][j] - 1) for i in range(2) for j in range(2)), DIGITS_90)
    # the same matrix at twice the digits
    g = [[Decimal(i * 7 - j * 3 + 1) / 19 - (Decimal(2) if i == j else ZERO) for j in range(5)] for i in range(5)]
    one = pr.expm(g, Decimal("1.7"))
    with precision(220):
        two = pr.expm(g, Decimal("1.7"))
    note("propagator: a dense matrix of both signs against itself at 220 digits",
         max(abs(one[i][j] - two[i][j]) for i in range(5) for j in range(5)) / pr.largest(two), TEN ** -100)
    left, right = Decimal("0.6180339887"), Decimal("1.1414213562")
    product = pr.matmul(pr.expm(g, left), pr.expm(g, right))
    whole = pr.expm(g, left + right)
    note("propagator: e^(G(s+t)) = e^(Gs) e^(Gt), dense, incommensurate times",
         max(abs(product[i][j] - whole[i][j]) for i in range(5) for j in range(5)) / pr.largest(whole), DIGITS_90)
    zero = [[ZERO] * 4 for _ in range(4)]
    note("propagator: a zero generator is exactly the identity", pr.largest(pr.add(pr.expm(zero, Decimal(5)),
                                                                                  pr.scaled(pr.identity(4), -ONE))), ZERO)
    # uniformization against the dense answer on a network with a loop, a drain and an inlet
    g = [[ZERO, ZERO, ZERO, ZERO], [Decimal("0.5"), Decimal("-0.75"), Decimal("0.2"), ZERO],
         [ZERO, Decimal("0.75"), Decimal("-0.6"), ZERO], [ZERO, ZERO, Decimal("0.4"), ZERO]]
    v = [Decimal("0.3"), Decimal(2), Decimal("1e-12"), ZERO]
    a = pr.matvec(pr.expm(g, Decimal(9)), v)
    b = pr.uniformized(g, Decimal(9), v)
    note("propagator: uniformization agrees with scaling and squaring (relative, every entry)",
         max(abs(x / y - 1) for x, y in zip(a, b)), DIGITS_90)


# ---- 2. equal rates ---------------------------------------------------------------------------------------------------

def confluent_tests():
    q, v = Decimal("0.5"), Decimal(4)
    t = Decimal(11)
    for k in (10, 60, 120, 200):
        near = v * (1 + Decimal(2) ** -k)
        g = [[-q / v, ZERO, ZERO], [q / v, -q / near, ZERO], [ZERO, q / near, ZERO]]
        p = pr.expm(g, t)
        e = laws.Chain(Decimal(10), ZERO, v, near, q, ZERO).difference_quotient(t)
        closed = q / v * e
        limit = laws.Chain(Decimal(10), ZERO, v, v, q, ZERO)
        confluent = limit.a * limit.difference_quotient(t)
        gap = abs(p[1][0] - confluent) / confluent
        at = q / v * t
        note(f"equal rates: the propagator at V_B = V_A (1 + 2^-{k}) is within 2^-{k} at of the confluent form (relative)",
             gap / (Decimal(2) ** -k * at), ONE)
        if k <= 120:
            note(f"equal rates: the closed form with a != b at V_B = V_A (1 + 2^-{k}) against the propagator (relative)",
                 abs(closed / p[1][0] - 1), TEN ** -(100 - k * 31 // 100 - 3))
    e = laws.Chain(Decimal(10), ZERO, v, v, q, ZERO)
    for t in (Decimal("1e-20"), Decimal("0.5"), Decimal(8), Decimal(160)):
        g = [[-q / v, ZERO, ZERO], [q / v, -q / v, ZERO], [ZERO, q / v, ZERO]]
        p = pr.expm(g, t)
        first, second, collected = e.state(t)
        note(f"equal rates: the confluent chain against the propagator at t = {t} (largest of A and B, relative)",
             max(abs(first / 10 / p[0][0] - 1), abs(second / 10 / p[1][0] - 1)), DIGITS_90)


# ---- 3. the integrable singularity ----------------------------------------------------------------------------------------

def chain_world(eps, level, start_b=None):
    """A chain with B at eps (an exact Decimal), outside the JSON reader (so that eps may be 0 or far below 5e-324)."""
    block = {"collectors": ["K"], "end_s": 16.0, "events": [], "faces_pL_per_s": [],
             "inlets_mM": {"I": {"T": [[0.0, 1.0]]}}, "labels": None,
             "links_pL_per_s": [["I", "A", [[0.0, 0.5]]], ["A", "B", [[0.0, 0.5]]], ["B", "K", [[0.0, 0.5]]]],
             "outputs_s": [2.0, 16.0], "sites": None, "start_fmol": {"T": {"A": 10.0, "B": 4.0}}, "temperature_K": 298.15,
             "volumes_pL": {"A": 4.0, "B": 4.0}}
    world = World("singular", block)
    world.start["T"]["B"] = 4 * eps if start_b is None else start_b
    world.inlets["I"]["T"] = [(ZERO, level)]
    return world


def singularity_tests():
    outputs = [Decimal(2), Decimal(16)]
    limit = {}
    for label, eps in (("0", ZERO), ("1e-60", TEN ** -60), ("1e-30", TEN ** -30), ("1e-15", TEN ** -15), ("1e-9", TEN ** -9)):
        world = chain_world(eps, eps)
        digits = 260
        depth = 10 if eps == 0 else 10 + int((-eps.log10()) * 34 / 10)
        if eps == 0:
            depth = 230
        with precision(digits):
            states = [{x: flow.amounts(world, x, t) for x in world.species} for t in outputs]
            totals = [flow.total_heat(world, t, s) for t, s in zip(outputs, states)]
            scale = world.rt * 10
        gauss = heats.by_gauss(world, outputs, depth=depth, digits=150)
        if eps == 0:
            # the double-exponential rule takes the end singularity itself; the state needs the extra digits near t = 0
            sinh, _ = heats.by_tanh_sinh(world, outputs, fine_first=48, fine_rest=24, digits=digits)
        else:
            sinh, _ = heats.by_tanh_sinh(world, outputs, fine_first=256, fine_rest=24, digits=digits)
        holders = ["A", "B", "K"]
        worst_g = max(abs(sum(gauss[h][k] for h in holders) - totals[k]) / scale for k in range(2))
        worst_s = max(abs(sum(sinh[h][k] for h in holders) - totals[k]) / scale for k in range(2))
        pair = max(abs(gauss[h][k] - sinh[h][k]) / scale for h in holders for k in range(2))
        note(f"singularity: B and the inlet at {label} mM, the holders' heats sum to H_tot, graded Gauss (over RT N)",
             worst_g, TEN ** -45)
        note(f"singularity: B and the inlet at {label} mM, the holders' heats sum to H_tot, tanh-sinh (over RT N)",
             worst_s, TEN ** -45)
        note(f"singularity: B and the inlet at {label} mM, the two quadratures on every holder (over RT N)", pair, TEN ** -45)
        limit[label] = gauss["B"][1]
    for label, eps in (("1e-9", TEN ** -9), ("1e-15", TEN ** -15), ("1e-30", TEN ** -30)):
        gap = abs(limit[label] - limit["0"])
        note(f"singularity: H_B at {label} mM tends to the limit of a zero trace, gap over RT N eps |ln eps|",
             gap / (world.rt * 10 * eps * abs(eps.ln())), Decimal(4))
    # the first instants, in closed form: r_B ~ RT Q c (ln(V/(Q t)) - 1 + ...), its integral RT Q c t ln(V/(Q t)) + ...
    world = chain_world(ZERO, ZERO)
    t = TEN ** -25
    gauss = heats.by_gauss(world, [t], depth=230, digits=200)
    q, v, c = Decimal("0.5"), Decimal(4), Decimal("2.5")
    expected = world.rt * q * c * t * (v / (q * t)).ln()
    note("singularity: H_B of the first 1e-25 s at a zero trace, against RT Q c t ln(V/(Q t)) (relative)",
         gauss["B"][0] / expected - 1, TEN ** -24)
    # the two rules on integrals known exactly
    rule = quadrature.TanhSinh(64, 120, 62)
    total = sum((w * s.ln() for s, w, _ in rule.points(ZERO, ONE)), ZERO)
    note("singularity: the double-exponential rule on the integral of ln s over (0, 1), which is -1", total + 1, TEN ** -55)
    eps = TEN ** -15
    known = (1 + eps) * (1 + eps).ln() - eps * eps.ln() - 1
    rule = quadrature.TanhSinh(192, 120, 62)
    total = sum((w * (s + eps).ln() for s, w, _ in rule.points(ZERO, ONE)), ZERO)
    note("singularity: the double-exponential rule on ln(s + 1e-15), in closed form", total - known, TEN ** -45)
    gauss_rule = quadrature.GaussRule(40, 120)
    total = sum((w * (s + eps).ln() for s, w in quadrature.gauss_points(gauss_rule, ZERO, ONE, 60)), ZERO)
    note("singularity: graded Gauss on ln(s + 1e-15), in closed form", total - known, TEN ** -55)
    worst = ZERO
    for k in (0, 1, 2, 3, 17, 40, 79):
        value = sum((w * s ** k for s, w in gauss_rule.rule), ZERO)
        worst = max(worst, abs(value * (k + 1) - 1))
    note("singularity: the Gauss rule integrates the monomials to degree 79", worst, TEN ** -100)
    value = sum((w * s ** 81 for s, w in gauss_rule.rule), ZERO)
    note("singularity: and misses degree 81 (a rule too good would hide a mistake: 1 minus the fraction is 0 if it did)",
         ONE if abs(value * 82 - 1) < TEN ** -100 else ZERO, ZERO)


# ---- 4. arm 6 -----------------------------------------------------------------------------------------------------------------

def face_world(permeance, rate, level=Decimal("0.25")):
    block = {"collectors": ["K"], "end_s": 16.0, "events": [], "faces_pL_per_s": [["A", "B", {"T": 0.25}]],
             "inlets_mM": {"I": {"T": [[0.0, 0.25]]}}, "labels": None,
             "links_pL_per_s": [["I", "A", [[0.0, 0.5]]], ["A", "B", [[0.0, 0.5]]], ["B", "K", [[0.0, 0.5]]]],
             "outputs_s": [2.0, 16.0], "sites": None, "start_fmol": {"T": {"A": 10.0, "B": 6.0}}, "temperature_K": 298.15,
             "volumes_pL": {"A": 4.0, "B": 6.0}}
    world = World("beside", block)
    world.faces = [("A", "B", {"T": permeance})]
    world.links = [(s, t, [(ZERO, rate)]) for s, t, _ in world.links]
    world.inlets["I"]["T"] = [(ZERO, level)]
    return world


def face_tests():
    times = [Decimal("0.01"), Decimal(2), Decimal(16)]
    for permeance, rate in ((Decimal("0.25"), Decimal("0.5")), (Decimal(40), Decimal("0.003")), (Decimal("1e-9"), Decimal(3)),
                            (Decimal("0.25"), ZERO), (Decimal("7.5"), Decimal("7.5"))):
        world = face_world(permeance, rate)
        state = heats.ChainState(world, "T")
        worst, jump, conserved = ZERO, ZERO, ZERO
        for t in times:
            honest = flow.amounts(world, "T", t)
            closed = state.amounts(t)
            other = flow.amounts(world, "T", t, method="uniformized")
            for name in ("A", "B"):
                worst = max(worst, abs(closed[name] / honest[name] - 1))
                jump = max(jump, abs(other[name] / honest[name] - 1))
            if rate != 0:
                worst = max(worst, abs(closed["K"] / honest["K"] - 1))
            supplied = rate * Decimal("0.25") * t
            conserved = max(conserved, abs(sum(honest.values()) - 16 - supplied))
        note(f"arm 6: PA {permeance}, Q {rate}: eigenvalues against the propagator (relative)", worst, TEN ** -70)
        note(f"arm 6: PA {permeance}, Q {rate}: uniformization against the propagator (relative)", jump, TEN ** -90)
        note(f"arm 6: PA {permeance}, Q {rate}: amounts conserved (fmol)", conserved, TEN ** -90)
    # no face: the plain chain; an enormous face: one well of V_A + V_B
    t = Decimal(5)
    bare = heats.ChainState(face_world(ZERO, Decimal("0.5")), "T").amounts(t)
    tiny = flow.amounts(face_world(TEN ** -40, Decimal("0.5")), "T", t)
    note("arm 6: PA to 0 is the chain (relative to PA)", max(abs(bare[n] / tiny[n] - 1) for n in ("A", "B", "K")) / TEN ** -40,
         Decimal(40))
    wide = flow.amounts(face_world(TEN ** 12, Decimal("0.5")), "T", t)
    one_well = Decimal("0.25") + (Decimal("1.6") - Decimal("0.25")) * (-(Decimal("0.5") * t / 10)).exp()
    note("arm 6: PA to infinity is one well of V_A + V_B (relative, times PA)",
         max(abs(wide["A"] / 4 / one_well - 1), abs(wide["B"] / 6 / one_well - 1)) * TEN ** 12, Decimal(100))
    # the split maps' orders
    world = face_world(Decimal("0.25"), Decimal("0.5"))
    reference = flow.amounts(world, "T", Decimal(8))["A"]
    errors = {"strang": [], "lie": []}
    for k in range(3, 9):
        for kind in errors:
            run = splitting.split_run(world, "T", Decimal(2) ** -k, [Decimal(8)], kind)
            errors[kind].append(abs(run[Decimal(8)]["A"] - reference))
    for kind, expected in (("strang", 4), ("lie", 2)):
        ratio = errors[kind][-2] / errors[kind][-1]
        note(f"arm 6: the {kind} split's error falls by {expected} a halving (last pair, h = 2^-7, 2^-8)", ratio - expected,
             Decimal("0.03") * expected)


# ---- 5. the rate laws as the limit of finite portions -----------------------------------------------------------------------

def richardson(values, ratio_orders):
    """Extrapolate values at h, h/2, h/4, ... whose errors go as h, h^2, h^3, ..."""
    table = list(values)
    for order in ratio_orders:
        factor = Decimal(2) ** order
        table = [(factor * b - a) / (factor - 1) for a, b in zip(table, table[1:])]
    return table[-1]


def portion_limit_tests():
    """H_A, H_B and H_K of a chain (and the face of arm 6) from the finite-portion law alone, extrapolated to h = 0."""
    world = chain_world(Decimal(1), Decimal("0.5"), start_b=Decimal(4))
    end = Decimal(2)
    honest = heats.by_gauss(world, [end], depth=20, digits=80)
    with precision(80):
        runs = [flow.portion_heats(world, Decimal(2) ** -k, end) for k in range(1, 9)]
    for holder in ("A", "B", "K"):
        value = richardson([r[holder] for r in runs], range(1, 8))
        note(f"rate law: H_{holder} of a chain as the limit of finite portions (relative)", value / honest[holder][0] - 1,
             TEN ** -9)
    # arm 6, by the Strang splitting of the same portions with the face's own free-energy loss
    world = face_world(Decimal("0.25"), Decimal("0.5"))
    honest = heats.by_gauss(world, [end], depth=20, digits=80)
    layout = pr.Layout(world)
    values = []
    with precision(80):
        g_flow = pr.generator(world, "T", ZERO, layout, with_faces=False)
        for k in range(1, 8):
            h = Decimal(2) ** -k
            half = pr.expm(g_flow, h / 2)
            y = pr.with_inlets(world, "T", ZERO, pr.start_vector(world, "T", layout), layout)
            volumes = pr.with_inlets(world, "volume", ZERO, pr.start_vector(world, "volume", layout), layout)
            totals = {"A": ZERO, "B": ZERO, "K": ZERO, "face": ZERO}
            wells = laws.TwoWells
            for _ in range(int(end / h)):
                for stage in (0, 1):
                    new, new_volumes = pr.matvec(half, y), pr.matvec(half, volumes)
                    for name in ("A", "B", "K"):
                        i = layout.index[name]
                        level = new[i] / new_volumes[i]
                        for j, origin in enumerate(layout.names):
                            v = half[i][j] * volumes[j]
                            if v == 0:
                                continue
                            x = y[j] if origin in world.inlets else y[j] / volumes[j]
                            totals[name] += world.rt * v * level * phi(x / level)
                    y, volumes = new, new_volumes
                    if stage == 0:
                        # the exact two-well relaxation over h (its own free energy is the face's heat)
                        i, j = layout.index["A"], layout.index["B"]
                        w = wells(world.rt, y[i], y[j], world.volumes["A"], world.volumes["B"], Decimal("0.25"))
                        m = w.moved(h)
                        totals["face"] += w.lost(m)
                        y[i], y[j] = y[i] - m, y[j] + m
            values.append(totals)
    for name in ("A", "B", "K", "face"):
        honest_value = honest[heats.FACE if name == "face" else name][0]
        # Strang: even powers in the trajectory, odd ones in the holders' split; extrapolate in 1, 2, 3, ...
        value = richardson([v[name] for v in values], range(1, 7))
        note(f"rate law: arm 6, {name} as the limit of split finite portions (relative)", value / honest_value - 1, TEN ** -6)


# ---- 6. small parts --------------------------------------------------------------------------------------------------------------

def small_tests():
    big_pi = pi()
    text = "3.14159265358979323846264338327950288419716939937510582097494459230781640628620899862803482534211706798214808651"
    note("pi against its digits", big_pi - Decimal(text), TEN ** -100)
    note("the dilogarithm: Li2(-1) = -pi^2/12", checks.dilogarithm(-ONE) + big_pi ** 2 / 12, TEN ** -100)
    # Li2(-x) + Li2(-1/x) = -pi^2/6 - ln^2(x)/2, with both arguments inside the two branches
    x = Decimal("2.7")
    note("the dilogarithm: the inversion relation at 2.7",
         checks.dilogarithm(-x) + checks.dilogarithm(-1 / x) + big_pi ** 2 / 6 + x.ln() ** 2 / 2, TEN ** -100)
    # its derivative, by a centred difference: Li2'(-x) = ln(1 + x)/x
    with precision(200):
        d = TEN ** -60
        x = Decimal("0.6")
        slope = (checks.dilogarithm(-(x + d)) - checks.dilogarithm(-(x - d))) / (2 * d)
        note("the dilogarithm: d/dx Li2(-x) = -ln(1 + x)/x", slope + (1 + x).ln() / x, TEN ** -100)
    gamma, delta = laws.ars_constants()
    note("ARS(2,2,2): (1 - delta) gamma = 1/2", (1 - delta) * gamma - Decimal("0.5"), TEN ** -100)
    note("phi(1) = 0 exactly", phi(ONE), ZERO)
    note("phi(0) = 1 exactly", phi(ZERO) - 1, ZERO)
    # the exact reading of a double
    note("0.1 is read as the exact value of its double",
         exact(0.1) - Decimal("0.1000000000000000055511151231257827021181583404541015625"), ZERO)
    # the emulation's phi against decimal, near and away from 1
    from lrrefs import emulation
    worst = ZERO
    for text in ("1", "1.0000000001", "0.9999999", "1.0009", "1.01", "0.8", "1.3", "3", "0.01", "1e-12"):
        r = exact(float(text))
        value = exact(emulation.phi_float(float(text), 1.0))
        true = phi(r)
        error = abs(value - true)
        worst = max(worst, error / max(true, TEN ** -24) if true > TEN ** -24 else error * TEN ** 10)
    note("the emulation's phi against decimal, near and away from 1 (relative)", worst, TEN ** -12)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--only", help="comma-separated: propagator,confluent,singularity,face,portions,small")
    arguments = parser.parse_args()
    set_precision()
    groups = {"propagator": propagator_tests, "confluent": confluent_tests, "singularity": singularity_tests,
              "face": face_tests, "portions": portion_limit_tests, "small": small_tests}
    wanted = arguments.only.split(",") if arguments.only else list(groups)
    for name in wanted:
        groups[name]()
        print(f"{name}: {sum(r['passes'] for r in ROWS)} of {len(ROWS)} pass so far", flush=True)
    os.makedirs(arguments.out, exist_ok=True)
    with open(os.path.join(arguments.out, "component_tests.json"), "w", encoding="ascii") as handle:
        json.dump({"tests": ROWS, "passed": sum(r["passes"] for r in ROWS), "total": len(ROWS)}, handle, indent=1, sort_keys=True)
        handle.write("\n")
    for row in ROWS:
        if not row["passes"]:
            print("MISS", row)
    sys.exit(0 if all(r["passes"] for r in ROWS) else 1)


if __name__ == "__main__":
    main()
