"""FR-50 references, route B: the second route, independent of route A.

It works in exact rationals (fractions.Fraction), with this module's own binary exp and ln, and
intermediate results rounded to PB = 640 significant bits (about 192 digits). It uses no decimal
module. It shares only the parsed declarations with route A.

- **Ussing's ratio and the net (the README's cross-check).** Each one-way flux is recomputed as:
  - the net from the one-exponential GHK form, g x (c_in - c_out e^-x)/(1 - e^-x) outward, with
    its own x = 0 limit;
  - rho = backward/forward from Ussing's ratio, inward/outward = (c_out/c_in) e^-x;
  - forward = net/(1 - rho), and backward = rho forward.
  - The transporter is recomputed the same way, from rho = e^(dG/RT) and its net,
    k a S (1 - e^(dG/RT)).
- **Exactly at zero net,** rho = 1 and the recomputation is 0/0: a neutral route at equal
  concentrations, or the transporter at dG = 0 exactly. The one-way fluxes then come from their
  direct forms in exact rationals, and rho = 1 and net = 0 are reported.
- **The transporter:** dG/RT = dmu/RT + ln(P), with one logarithm of the exact product
  P = c_ADP c_Pi (c_out/c_in)^n/(c_ATP c0). S is in exact rationals.
- **u:** K = exp(ln K(0) + a V_ref), and u = 1/(1 + c_B/K).
- **E_K:** this module's ln, rounded to 50 significant digits by integer arithmetic.
- **K2:** the matrix exponential of the linear system (n_O, n_N, F, B), on each record interval,
  by its Taylor series.
"""

from __future__ import annotations

from fractions import Fraction as Q

from fr50_spec import Case, Spec

PB = 640
WB = PB + 96
E_DIGITS = 50


def _tshift(a: int, bits: int) -> int:
    return a >> bits if a >= 0 else -((-a) >> bits)


def _tdiv(a: int, b: int) -> int:
    return a // b if a >= 0 else -((-a) // b)


def rnd(value: Q, bits: int = PB) -> Q:
    """value rounded half-even to `bits` significant bits."""
    if value == 0:
        return Q(0)
    n, d = value.numerator, value.denominator
    e = n.bit_length() - d.bit_length() - bits
    m = round(Q(n, d << e)) if e >= 0 else round(Q(n << -e, d))
    return Q(m << e) if e >= 0 else Q(m, 1 << -e)


_LN2: dict[int, int] = {}


def _ln2_fixed(bits: int) -> int:
    """ln 2 x 2^bits, from ln 2 = 2 atanh(1/3)."""
    if bits not in _LN2:
        guard = 32
        power = (1 << (bits + guard)) // 3
        total, n = 0, 0
        while power:
            total += power // (2 * n + 1)
            power //= 9
            n += 1
        _LN2[bits] = (2 * total) >> guard
    return _LN2[bits]


def exp_q(x: Q) -> Q:
    """e^x to PB bits: x = k ln 2 + r, then e^(r/2^16) by Taylor series, squared 16 times."""
    W = WB
    L = _ln2_fixed(W)
    X = round(x * (1 << W))
    k = round(Q(X, L))
    R = _tshift(X - k * L, 16)
    one = 1 << W
    term = total = one
    n = 0
    while True:
        n += 1
        term = _tdiv(_tshift(term * R, W), n)
        if term == 0:
            break
        total += term
    for _ in range(16):
        total = (total * total) >> W
    return rnd(Q(total << k, one) if k >= 0 else Q(total, one << -k))


def ln_q(y: Q) -> Q:
    """ln y for y > 0: y = 2^k m with m in [2/3, 4/3], ln m = 2 atanh((m - 1)/(m + 1))."""
    if y <= 0:
        raise ValueError("ln of a non-positive number")
    W = WB
    k = y.numerator.bit_length() - y.denominator.bit_length()
    m = y / (Q(2) ** k)
    while m > Q(4, 3):
        m /= 2
        k += 1
    while m < Q(2, 3):
        m *= 2
        k -= 1
    T = round((m - 1) / (m + 1) * (1 << W))
    T2 = _tshift(T * T, W)
    total, power, n = 0, T, 0
    while power != 0:
        total += _tdiv(power, 2 * n + 1)
        power = _tshift(power * T2, W)
        n += 1
    return rnd(Q(k * _ln2_fixed(W) + 2 * total, 1 << W))


def round_sig10(value: Q, digits: int) -> Q:
    """value rounded half-even to `digits` significant decimal digits."""
    if value == 0:
        return Q(0)
    a = abs(value)
    k = len(str(a.numerator)) - len(str(a.denominator))
    while Q(10) ** k > a:
        k -= 1
    while Q(10) ** (k + 1) <= a:
        k += 1
    scale = Q(10) ** (digits - 1 - k)
    return Q(round(value * scale)) / scale


def times(case: Case) -> list[Q]:
    step = Q(case.record_times.step)
    return [step * i for i in range(case.record_times.last + 1)]


def beta(spec: Spec, T: str) -> Q:
    """F/(R T): with the same N_A in F and R, e/(k_B T)."""
    n_a, charge = Q(spec.F_factors[0]), Q(spec.F_factors[1])
    n_a_r, boltzmann = Q(spec.R_factors[0]), Q(spec.R_factors[1])
    if n_a == n_a_r:
        return charge / (boltzmann * Q(T))
    return n_a * charge / (n_a_r * boltzmann * Q(T))


def nernst(b: Q, z: int, c_in: Q, c_out: Q) -> tuple[Q, Q]:
    E = rnd(ln_q(c_out / c_in) / (z * b))
    return E, round_sig10(E, E_DIGITS)


def ussing_net(g: Q, c_in: Q, c_out: Q, x: Q, forward_outward: bool) -> dict:
    """A constant-field route's one-way fluxes from Ussing's ratio and the net."""
    if x == 0:
        e_mx = Q(1)
        J_out = g * (c_in - c_out)
    else:
        e_mx = exp_q(-x)
        J_out = rnd(g * x * (c_in - c_out * e_mx) / (1 - e_mx))
    in_over_out = rnd(c_out * e_mx / c_in)
    rho = in_over_out if forward_outward else rnd(1 / in_over_out)
    net = J_out if forward_outward else -J_out
    if rho == 1:
        raise ValueError("Ussing's recomputation is 0/0 here")
    forward = rnd(net / (1 - rho))
    return {"forward": forward, "backward": rnd(rho * forward), "rho": rho, "net": net,
            "ratio_inward_over_outward": in_over_out, "route": "ussing_and_net"}


def direct_neutral(g: Q, c_from: Q, c_to: Q) -> dict:
    """A neutral route's one-way fluxes, g c_from and g c_to, with its Ussing ratio and net."""
    forward, backward = g * c_from, g * c_to
    rho = c_to / c_from
    out = {"forward": forward, "backward": backward, "rho": rho, "net": forward - backward}
    out["route"] = "direct_exact" if rho == 1 else "direct_exact_off_zero_net"
    return out


def unblocked_fraction(block: dict, b: Q, V_ref: Q) -> Q:
    blocker = block["blocker"]
    z_B = blocker["valence"]
    side = 1 if blocker["side"] == "outside" else -1
    sign = 1 if z_B > 0 else -1
    c_B = Q(blocker["concentration_mM"])
    total, weights = Q(0), Q(0)
    for mode in block["modes"]:
        if "electrical_distance" in mode:
            a = side * z_B * Q(mode["electrical_distance"]) * b
        else:
            a = side * sign * Q(mode["effective_valence"]) * b
        K = exp_q(ln_q(Q(mode["k0_mM"])) + a * V_ref)
        w = Q(mode["weight"])
        total += w * rnd(1 / (1 + c_B / K))
        weights += w
    return rnd(total / weights)


def transporter(case: Case) -> dict:
    n = case["stoichiometry"]
    mu, fuel = case["mu0_over_RT"], case["fuel_mM"]
    c_in, c_out = Q(case["c_in_mM"]), Q(case["c_out_mM"])
    d_mu = Q(mu["ADP"]) + Q(mu["Pi"]) - Q(mu["ATP"])
    P = Q(fuel["ADP"]) * Q(fuel["Pi"]) * (c_out / c_in) ** n / (Q(fuel["ATP"]) * Q(case["c0_mM"]))
    dG = d_mu + ln_q(P)
    S = 1 / (1 + (Q(case["K_mM"]) / c_in) ** n) / (1 + Q(case["K_ATP_mM"]) / Q(fuel["ATP"]))
    scale = Q(case["capacity_fmol_cycles_per_s"]) * Q(case["availability"]) * S
    rho = exp_q(dG)
    net = rnd(scale * (1 - rho))
    if rho == 1:
        J_plus, J_minus, route = scale, scale, "direct_exact"
    else:
        J_plus = rnd(net / (1 - rho))
        J_minus, route = rnd(rho * J_plus), "ussing_and_net"
    return {"dG_cyc_over_RT": dG, "S": S, "J_plus": J_plus, "J_minus": J_minus, "net": net,
            "rho": rho, "J_minus_over_J_plus": rnd(J_minus / J_plus), "route": route,
            "forward": J_plus, "backward": J_minus}


def relaxation(case: Case) -> dict:
    """K2: exp(M dt) y on each record interval, by its Taylor series, for y = (n_O, n_N, F, B)."""
    a = Q(10) ** 15 * Q(case["P_m_per_s"]) * Q(case["A_m2"]) * Q(case["opening"])
    V_O, V_N = Q(case["V_cell_pL"]), Q(case["V_node_pL"])
    M = [[-a / V_O, a / V_N, Q(0), Q(0)],
         [a / V_O, -a / V_N, Q(0), Q(0)],
         [Q(0), a / V_N, Q(0), Q(0)],
         [a / V_O, Q(0), Q(0), Q(0)]]
    y = [V_O * Q(case["c_cell_mM_at_0"]), V_N * Q(case["c_node_mM_at_0"]), Q(0), Q(0)]
    ts = times(case)
    out: dict = {"c_cell": [], "c_node": [], "F": [], "B": []}
    t_prev = Q(0)
    for t in ts:
        dt = t - t_prev
        if dt:
            term, total = list(y), list(y)
            n = 0
            while True:
                n += 1
                term = [rnd(sum((M[i][j] * term[j] for j in range(4)), Q(0)) * dt / n)
                        for i in range(4)]
                total = [s + d for s, d in zip(total, term, strict=True)]
                scale = max(abs(v) for v in total)
                if max(abs(v) for v in term) <= scale * Q(1, 1 << (PB + 8)):
                    break
            y = [rnd(v) for v in total]
        t_prev = t
        out["c_cell"].append(y[0] / V_O)
        out["c_node"].append(y[1] / V_N)
        out["F"].append(y[2])
        out["B"].append(y[3])
    n_total = V_O * Q(case["c_cell_mM_at_0"]) + V_N * Q(case["c_node_mM_at_0"])
    out["a"] = a
    out["k"] = a * (1 / V_O + 1 / V_N)
    out["c_bar"] = n_total / (V_O + V_N)
    return out


class CaseB:
    """One case evaluated by route B; `values` mirrors route A's names."""

    def __init__(self, spec: Spec, case: Case):
        self.case = case
        kind = case.kind
        b = beta(spec, case["T_K"])
        v: dict = {}
        T15 = Q(10) ** 15
        if kind == "K1":
            g = T15 * Q(case["P_m_per_s"]) * Q(case["A_m2"]) * Q(case["opening"])
            v.update(direct_neutral(g, Q(case["c_node_mM"]), Q(case["c_cell_mM"])))
            v["g"] = g
        elif kind == "E2":
            g = (T15 * Q(case["P_m_per_s"]) * Q(case["A_m2"]) * Q(case["gate"])
                 * Q(case["availability"]))
            v.update(direct_neutral(g, Q(case["c_sender_mM"]), Q(case["c_receiver_mM"])))
            v["g"] = g
        elif kind == "E3":
            g = T15 * Q(case["D_m2_per_s"]) * Q(case["A_m2"]) / Q(case["L_m"])
            v.update(direct_neutral(g, Q(case["c_sender_mM"]), Q(case["c_receiver_mM"])))
            v["g"] = g
        elif kind in ("E1", "E4"):
            z = case["valence"]
            c_in, c_out = Q(case["c_in_mM"]), Q(case["c_out_mM"])
            self.E_full, self.E_K = nernst(b, z, c_in, c_out)
            g = T15 * Q(case["P_m_per_s"]) * Q(case["A_m2"]) * Q(case["availability"])
            if kind == "E4":
                g *= (Q(case["relative_permeability"]) * Q(case["abundance"])
                      * Q(case["open_fraction"]))
                v["u"] = unblocked_fraction(case["block"], b, self.E_K - self.E_K)
                g *= v["u"]
            v["g"] = g
            v.update(ussing_net(g, c_in, c_out, z * b * self.E_K, forward_outward=True))
        elif kind in ("K4", "K4h"):
            v.update(transporter(case))
        elif kind == "K2":
            v.update(relaxation(case))
        elif kind == "K3":
            self.evaluations = self._k3(case, b)
        elif kind == "E6":
            self.evaluations = self._e6(case, b)
        if kind in ("K1", "E1", "E2", "E3", "E4", "K4"):
            ts = times(case)
            v["F"] = [v["forward"] * t for t in ts]
            v["B"] = [v["backward"] * t for t in ts]
        self.values = v

    def _k3(self, case: Case, b: Q) -> list[dict]:
        z = case["valence"]
        g = Q(10) ** 15 * Q(case["P_m_per_s"]) * Q(case["A_m2"]) * Q(case["opening"])
        c_in, c_out = Q(case["c_in_mM"]), Q(case["c_out_mM"])
        out = []
        for text in case["voltages_V"]:
            r = ussing_net(g, c_in, c_out, z * b * Q(text), forward_outward=False)
            out.append({"V": Q(text), "forward": r["forward"], "backward": r["backward"],
                        "ratio_inward_over_outward": r["ratio_inward_over_outward"],
                        "ratio_backward_over_forward": r["rho"]})
        return out

    def _e6(self, case: Case, b: Q) -> list[dict]:
        z = case["valence"]
        c_in, c_out = Q(case["c_in_mM"]), Q(case["c_out_mM"])
        self.E_full, self.E_K = nernst(b, z, c_in, c_out)
        base = (Q(10) ** 15 * Q(case["P_m_per_s"]) * Q(case["A_m2"])
                * Q(case["relative_permeability"]) * Q(case["abundance"])
                * Q(case["open_fraction"]))
        out = []
        for availability in case["availabilities"]:
            for text in case["voltages_V"]:
                V = Q(text)
                V_ref = V - self.E_K
                u = unblocked_fraction(case["block"], b, V_ref)
                r = ussing_net(base * Q(availability) * u, c_in, c_out, z * b * V,
                               forward_outward=True)
                out.append({"V": V, "availability": availability, "V_ref": V_ref, "u": u,
                            "forward": r["forward"], "backward": r["backward"],
                            "ratio_inward_over_outward": r["ratio_inward_over_outward"],
                            "ratio_backward_over_forward": r["rho"],
                            "difference": r["net"]})
        return out
