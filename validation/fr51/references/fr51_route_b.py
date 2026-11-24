"""FR-51 references, route B: a second route, independent of route A.

It shares only the parsed declarations (fr51_spec) with route A: no number type, no
exponential, no logarithm and no formula.
- **Arithmetic:** exact rationals (fractions.Fraction). The only rounding is in this module's own
  binary exp and ln, and in rounding intermediate results to PB = 640 significant bits (about
  192 digits) to bound their size. The decimal module is not used.
- **Permeation:** the GHK flux in its classical one-exponential form,
  J = 1e15 A P r a o v x (c_i - c_o e^-x)/(1 - e^-x), whose x = 0 limit is
  1e15 A P r a o v (c_i - c_o), since x/(1 - e^-x) -> 1.
- **Block:** a_k = s z_B delta_k F/(R T) for an electrical distance (the second form LAWS.md 3
  writes) and s sgn(z_B) z_eff F/(R T) for an effective valence; K_k = exp(ln K_k(0) + a_k V_ref);
  theta_k = 1/(1 + K_k/c_B), 1 - theta_k = 1/(1 + c_B/K_k); and u by the literal
  1 - (sum_k w_k theta_k)/(sum_k w_k).
- **Every slope** is a central difference of route B's own values, with step H = 1e-50 V, or
  1e-50 times the concentration for the concentration slopes. Its truncation is about
  H^2 |f'''/f'|/6, below about 1e-93 here (largest next to a slope's zero), and its rounding
  about 2^-640/H, below 1e-140.
- **E_ion** is recomputed from the concentrations with this module's ln, and rounded to 50
  significant digits by integer arithmetic; route A's string must match. For a concentration
  slope under the reversal reference, E at the perturbed concentration is recomputed unrounded and
  enters as E_ion + (E(c +- h) - E(c)), so the difference is centred on route A's V_ref.
"""

from __future__ import annotations

from fractions import Fraction as Q

from fr51_spec import Case, Spec

PB = 640  # significant bits kept after a rounding
WB = PB + 96  # fixed-point bits inside exp and ln
E_DIGITS = 50
H = Q(1, 10**50)  # the central differences' step: V, or relative for a concentration
PER_MODE = ("theta", "one_minus_theta")


def _tshift(a: int, bits: int) -> int:
    """a / 2^bits, truncated toward zero."""
    return a >> bits if a >= 0 else -((-a) >> bits)


def _tdiv(a: int, b: int) -> int:
    """a / b for b > 0, truncated toward zero."""
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
    """ln 2 x 2^bits as an integer, from ln 2 = 2 atanh(1/3) = 2 sum_n 3^-(2n+1)/(2n+1)."""
    if bits not in _LN2:
        guard = 32
        power = (1 << (bits + guard)) // 3
        total = 0
        n = 0
        while power:
            total += power // (2 * n + 1)
            power //= 9
            n += 1
        _LN2[bits] = (2 * total) >> guard
    return _LN2[bits]


def exp_q(x: Q) -> Q:
    """e^x to PB significant bits: x = k ln 2 + r, e^r = (e^(r/2^16))^(2^16) by its Taylor series,
    then the exact factor 2^k."""
    W = WB
    L = _ln2_fixed(W)
    X = round(x * (1 << W))  # x 2^W
    k = round(Q(X, L))  # nearest integer to x/ln 2
    R = X - k * L  # r 2^W, |r| <= ln2/2 (+ rounding)
    halvings = 16
    R = _tshift(R, halvings)  # (r/2^16) 2^W
    one = 1 << W
    term = one
    total = one
    n = 0
    while True:
        n += 1
        term = _tdiv(_tshift(term * R, W), n)
        if term == 0:
            break
        total += term
    for _ in range(halvings):
        total = (total * total) >> W
    return rnd(Q(total << k, one) if k >= 0 else Q(total, one << -k))


def ln_q(y: Q) -> Q:
    """ln y for y > 0 to about PB bits: y = 2^k m with m in [2/3, 4/3], then
    ln m = 2 atanh(t), t = (m - 1)/(m + 1), |t| <= 1/5."""
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
    t = (m - 1) / (m + 1)
    T = round(t * (1 << W))
    T2 = _tshift(T * T, W)
    total = 0
    power = T
    n = 0
    while power != 0:
        total += _tdiv(power, 2 * n + 1)
        power = _tshift(power * T2, W)
        n += 1
    return rnd(Q(k * _ln2_fixed(W) + 2 * total, 1 << W))


def round_sig10(value: Q, digits: int) -> Q:
    """value rounded half-even to `digits` significant decimal digits, by integer arithmetic."""
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


class CaseB:
    """One declared case, evaluated by route B."""

    def __init__(self, spec: Spec, case: Case):
        self.case = case
        n_a, charge = Q(spec.F_factors[0]), Q(spec.F_factors[1])
        n_a_r, boltzmann = Q(spec.R_factors[0]), Q(spec.R_factors[1])
        self.F = n_a * charge
        T = Q(spec.T_K)
        # F/(R T); with the same N_A in F and R this is e/(k_B T)
        self.beta = charge / (boltzmann * T) if n_a == n_a_r else self.F / (n_a_r * boltzmann * T)
        self.z = case.z
        self.c_i = Q(case.c_i_mM)
        self.c_o = Q(case.c_o_mM)
        if case.units_count is not None:
            abundance = Q(case.units_count) / (Q(case.area_m2) * Q(case.reference_density_per_m2))
        else:
            abundance = Q(case.abundance)
        self.abundance = abundance
        self.pref = (Q(10) ** 15 * Q(case.area_m2) * Q(case.permeability_m_per_s)
                     * Q(case.relative_permeability) * abundance * Q(case.open_fraction)
                     * Q(case.availability))
        self.to_amps = self.F * self.z / Q(10) ** 15
        self.E_full = self.nernst(self.c_i, self.c_o)
        self.E_ion = round_sig10(self.E_full, E_DIGITS)
        start, step = Q(spec.grid_start), Q(spec.grid_step)
        half_mV = Q(5, 10000)
        self.voltages = ([start + j * step for j in range(spec.grid_count)]
                         + [self.E_ion, self.E_ion - half_mV, self.E_ion + half_mV])
        block = case.block
        self.block = block
        if block is not None:
            side = 1 if block.side == "outside" else -1
            sign_zB = 1 if block.z_B > 0 else -1
            self.c_B = Q(block.c_B_mM)
            self.modes = []
            for mode in block.modes:
                if mode.electrical_distance is not None:
                    a = side * block.z_B * Q(mode.electrical_distance) * self.beta
                else:
                    a = side * sign_zB * Q(mode.effective_valence) * self.beta
                self.modes.append((Q(mode.weight), ln_q(Q(mode.k0_mM)), a))
            self.weight_sum = sum((w for w, _, _ in self.modes), Q(0))
            self.reversal = block.reversal_ion is not None
            self.h_co = self.c_o * H
            self.h_ci = self.c_i * H
            if self.reversal:
                # E at each perturbed concentration, unrounded, as an offset from E_ion
                self.E_co = [self.E_ion + (self.nernst(self.c_i, self.c_o + d) - self.E_full)
                             for d in (self.h_co, -self.h_co)]
                self.E_ci = [self.E_ion + (self.nernst(self.c_i + d, self.c_o) - self.E_full)
                             for d in (self.h_ci, -self.h_ci)]

    def nernst(self, c_i: Q, c_o: Q) -> Q:
        return rnd(ln_q(c_o / c_i) / (self.z * self.beta))

    def flux(self, V: Q, c_i: Q, c_o: Q) -> Q:
        """The unblocked flux (fmol/s, outward), in the classical GHK form."""
        x = self.z * self.beta * V
        if x == 0:
            return self.pref * (c_i - c_o)
        e_minus = exp_q(-x)
        return rnd(self.pref * x * (c_i - c_o * e_minus) / (1 - e_minus))

    def v_ref(self, V: Q, E: Q) -> Q:
        return V - E if self.reversal else V

    def fractions(self, V_ref: Q) -> tuple[list[Q], list[Q], Q]:
        """theta_k, 1 - theta_k and the literal u at V_ref."""
        thetas, unblocked = [], []
        blocked_sum = Q(0)
        for w, ln_k0, a in self.modes:
            K = exp_q(ln_k0 + a * V_ref)
            theta = Q(0) if self.c_B == 0 else rnd(1 / (1 + K / self.c_B))
            thetas.append(theta)
            unblocked.append(rnd(1 / (1 + self.c_B / K)))
            blocked_sum += w * theta
        return thetas, unblocked, rnd(1 - blocked_sum / self.weight_sum)

    def u(self, V: Q, E: Q) -> Q:
        return self.fractions(self.v_ref(V, E))[2]

    def point(self, V: Q) -> dict:
        """Every quantity at one voltage (theta and one_minus_theta as lists over the modes)."""
        c_i, c_o, E = self.c_i, self.c_o, self.E_ion
        J = self.flux(V, c_i, c_o)
        J_up, J_down = self.flux(V + H, c_i, c_o), self.flux(V - H, c_i, c_o)
        out = {"J_free": J, "I_free": self.to_amps * J,
               "dI_free_dV": self.to_amps * (J_up - J_down) / (2 * H)}
        if self.block is None:
            return out
        V_ref = self.v_ref(V, E)
        thetas, unblocked, u = self.fractions(V_ref)
        J_blocked = rnd(u * J)
        Jb_up = rnd(self.u(V + H, E) * J_up)
        Jb_down = rnd(self.u(V - H, E) * J_down)
        E_co = self.E_co if self.reversal else [E, E]
        E_ci = self.E_ci if self.reversal else [E, E]
        Jb_co = [rnd(self.u(V, E_co[n]) * self.flux(V, c_i, c_o + d))
                 for n, d in enumerate((self.h_co, -self.h_co))]
        Jb_ci = [rnd(self.u(V, E_ci[n]) * self.flux(V, c_i + d, c_o))
                 for n, d in enumerate((self.h_ci, -self.h_ci))]
        out.update({
            "V_ref": V_ref,
            "theta": thetas,
            "one_minus_theta": unblocked,
            "u": u,
            "J_blocked": J_blocked,
            "I_blocked": self.to_amps * J_blocked,
            "dI_blocked_dV": self.to_amps * (Jb_up - Jb_down) / (2 * H),
            "dJ_blocked_dc_o": (Jb_co[0] - Jb_co[1]) / (2 * self.h_co),
            "dJ_blocked_dc_i": (Jb_ci[0] - Jb_ci[1]) / (2 * self.h_ci),
        })
        return out

    def evaluate(self) -> dict:
        """Every quantity at every voltage, as lists of Fraction in voltage order."""
        points = [self.point(V) for V in self.voltages]
        out = {key: [p[key] for p in points] for key in points[0] if key not in PER_MODE}
        if self.block is not None:
            for key in PER_MODE:
                out[key] = [[p[key][k] for p in points] for k in range(len(self.modes))]
        return out
