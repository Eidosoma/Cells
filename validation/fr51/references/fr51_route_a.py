"""FR-51 references, route A: the closed forms of spec/LAWS.md in decimal arithmetic.

Every quantity is evaluated with Python's decimal module (libmpdec) at PREC = 120 significant
digits, rounding half-even, in the forms LAWS.md writes:
- the permeation of section 2, J = 1e15 A P r a o v (c_i B(-x) - c_o B(x)), B(x) = x/(e^x - 1)
  with e^x - 1 formed at extra precision, and its slope through B'(x);
- the block of section 3, with each 1 - theta_k = K_k/(c_B + K_k) formed directly and
  u = (sum_k w_k (1 - theta_k)) / (sum_k w_k), the sums left to right in declared mode order;
- the slopes of sections 4 and 5 in their analytic forms.

E_ion is the Nernst potential at 120 digits rounded half-even to E_DIGITS = 50 significant digits
(cases.json, extra_voltages). That 50-digit value is the E_ion of V_ref = V - E_ion and of the
voltage list, so V_ref is exactly 0 at V = E_ion (NOTES.md, reading 2).

Why 120 digits: at V = E_ion the flux is about 1e-51 of its two terms, because E_ion carries 50
digits. 120 digits leave about 69 correct digits there, against the 30 required (LAWS.md 7).
"""

from __future__ import annotations

import decimal
from decimal import Decimal

from fr51_spec import Case, Spec

PREC = 120
E_DIGITS = 50

_TRAPS = [decimal.InvalidOperation, decimal.DivisionByZero, decimal.Overflow]


def context(prec: int = PREC) -> decimal.Context:
    return decimal.Context(prec=prec, rounding=decimal.ROUND_HALF_EVEN, Emin=-999999,
                           Emax=999999, traps=_TRAPS)


ZERO = Decimal(0)
ONE = Decimal(1)
MOL_TO_FMOL = Decimal("1e15")
FMOL_TO_MOL = Decimal("1e-15")


def constants(spec: Spec) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """F (C/mol), R (J/(mol K)), T (K) and F/(R T) (1/V), at PREC digits."""
    with decimal.localcontext(context()):
        F = Decimal(spec.F_factors[0]) * Decimal(spec.F_factors[1])
        R = Decimal(spec.R_factors[0]) * Decimal(spec.R_factors[1])
        T = Decimal(spec.T_K)
        return F, R, T, F / (R * T)


def round_significant(x: Decimal, digits: int) -> Decimal:
    """x rounded half-even to `digits` significant digits; an exact zero stays Decimal(0)."""
    if x == 0:
        return ZERO
    return context(digits).plus(x)


def expm1(x: Decimal) -> Decimal:
    """e^x - 1 at PREC digits. exp is correctly rounded at a precision raised by the digits
    the subtraction cancels (about -log10|x| for small x), plus 30."""
    if x == 0:
        return ZERO
    with decimal.localcontext(context(PREC + 30 + max(0, -x.adjusted()))):
        value = x.exp() - ONE
    return context().plus(value)


def bern(x: Decimal) -> Decimal:
    """B(x) = x/(e^x - 1), B(0) = 1 (LAWS.md 2)."""
    if x == 0:
        return ONE
    with decimal.localcontext(context()):
        return x / expm1(x)


def bern_prime(x: Decimal) -> Decimal:
    """B'(x) = (e^x - 1 - x e^x)/(e^x - 1)^2, B'(0) = -1/2 (LAWS.md 2). The numerator is about
    -x^2/2, so it is formed at a precision raised by twice the digits it cancels."""
    if x == 0:
        return Decimal("-0.5")
    with decimal.localcontext(context(PREC + 30 + 2 * max(0, -x.adjusted()))):
        em1 = x.exp() - ONE
        value = (em1 - x * (em1 + ONE)) / (em1 * em1)
    return context().plus(value)


class CaseA:
    """One declared case, evaluated by route A."""

    def __init__(self, spec: Spec, case: Case):
        self.case = case
        self.F, self.R, self.T, self.q = constants(spec)
        with decimal.localcontext(context()):
            self.z = Decimal(case.z)
            self.c_i = Decimal(case.c_i_mM)
            self.c_o = Decimal(case.c_o_mM)
            if case.units_count is not None:
                # LAWS.md 6, C2: a = N/(A rho_ref)
                self.abundance = Decimal(case.units_count) / (
                    Decimal(case.area_m2) * Decimal(case.reference_density_per_m2))
            else:
                self.abundance = Decimal(case.abundance)
            self.pref = (MOL_TO_FMOL * Decimal(case.area_m2) * Decimal(case.permeability_m_per_s)
                         * Decimal(case.relative_permeability) * self.abundance
                         * Decimal(case.open_fraction) * Decimal(case.availability))
            # LAWS.md 2: E = (R T/(z F)) ln(c_o/c_i)
            self.E_full = (self.R * self.T / (self.z * self.F)) * (self.c_o / self.c_i).ln()
        self.E_ion = round_significant(self.E_full, E_DIGITS)
        self.voltages = self._voltages(spec)
        block = case.block
        self.block = block
        if block is not None:
            with decimal.localcontext(context()):
                s = ONE if block.side == "outside" else -ONE
                sign_zB = ONE if block.z_B > 0 else -ONE
                self.c_B = Decimal(block.c_B_mM)
                self.modes = []
                for mode in block.modes:
                    if mode.electrical_distance is not None:
                        m = abs(Decimal(block.z_B)) * Decimal(mode.electrical_distance)
                    else:
                        m = Decimal(mode.effective_valence)
                    a = s * sign_zB * m * self.q  # LAWS.md 3, 1/V
                    self.modes.append((Decimal(mode.weight), Decimal(mode.k0_mM), a))
                self.reversal = block.reversal_ion is not None
                # LAWS.md 5: dV_ref/dc_o = -R T/(z F c_o), dV_ref/dc_i = +R T/(z F c_i)
                if self.reversal:
                    self.dVref_dco = -(self.R * self.T) / (self.z * self.F * self.c_o)
                    self.dVref_dci = (self.R * self.T) / (self.z * self.F * self.c_i)
                else:
                    self.dVref_dco = ZERO
                    self.dVref_dci = ZERO

    def _voltages(self, spec: Spec) -> list[Decimal]:
        """The grid formed in decimal arithmetic, then E_ion, E_ion - 0.0005, E_ion + 0.0005."""
        with decimal.localcontext(context()):
            start = Decimal(spec.grid_start)
            step = Decimal(spec.grid_step)
            grid = [start + j * step for j in range(spec.grid_count)]
            half_mV = Decimal("0.0005")
            extras = [self.E_ion, self.E_ion - half_mV, self.E_ion + half_mV]
        return grid + extras

    def free(self, V: Decimal) -> dict[str, Decimal]:
        """LAWS.md 2 at voltage V."""
        with decimal.localcontext(context()):
            x = self.z * self.q * V
            Bm, Bp = bern(-x), bern(x)
            J = self.pref * (self.c_i * Bm - self.c_o * Bp)
            dJdV = self.pref * (self.z * self.q) * (-self.c_i * bern_prime(-x)
                                                    - self.c_o * bern_prime(x))
            to_amps = FMOL_TO_MOL * self.F * self.z
            return {"x": x, "B_minus": Bm, "B_plus": Bp, "J_free": J, "dJ_dV": dJdV,
                    "I_free": to_amps * J, "dI_free_dV": to_amps * dJdV}

    def blocked(self, V: Decimal, free: dict[str, Decimal]) -> dict:
        """LAWS.md 3-5 at voltage V, from the free quantities at V."""
        with decimal.localcontext(context()):
            V_ref = V - self.E_ion if self.reversal else V
            thetas, unblocked = [], []
            numerator = ZERO
            weight_sum = ZERO
            slope_numerator = ZERO
            for w, k0, a in self.modes:
                K = k0 * (a * V_ref).exp()
                total = self.c_B + K
                theta = self.c_B / total
                one_minus_theta = K / total
                thetas.append(theta)
                unblocked.append(one_minus_theta)
                numerator += w * one_minus_theta
                weight_sum += w
                slope_numerator += w * a * (theta * one_minus_theta)
            u = numerator / weight_sum
            du_dVref = slope_numerator / weight_sum
            J = free["J_free"]
            to_amps = FMOL_TO_MOL * self.F * self.z
            J_blocked = u * J
            dJb_dco = u * (-self.pref * free["B_plus"]) + J * du_dVref * self.dVref_dco
            dJb_dci = u * (self.pref * free["B_minus"]) + J * du_dVref * self.dVref_dci
            return {
                "V_ref": V_ref,
                "theta": thetas,
                "one_minus_theta": unblocked,
                "u": u,
                "du_dVref": du_dVref,
                "J_blocked": J_blocked,
                "I_blocked": to_amps * J_blocked,
                "dI_blocked_dV": to_amps * (u * free["dJ_dV"] + J * du_dVref),
                "dJ_blocked_dc_o": dJb_dco,
                "dJ_blocked_dc_i": dJb_dci,
            }

    def point(self, V: Decimal) -> dict:
        """Every quantity at one voltage (theta and one_minus_theta as lists over the modes)."""
        free = self.free(V)
        values = {key: free[key] for key in ("J_free", "I_free", "dI_free_dV")}
        if self.block is not None:
            values.update(self.blocked(V, free))
            del values["du_dVref"]
        return values

    def evaluate(self) -> dict:
        """Every quantity at every voltage, as lists of Decimal in voltage order."""
        out: dict = {key: [] for key in ("J_free", "I_free", "dI_free_dV")}
        if self.block is not None:
            for key in ("V_ref", "u", "J_blocked", "I_blocked", "dI_blocked_dV",
                        "dJ_blocked_dc_o", "dJ_blocked_dc_i"):
                out[key] = []
            out["theta"] = [[] for _ in self.modes]
            out["one_minus_theta"] = [[] for _ in self.modes]
        for V in self.voltages:
            free = self.free(V)
            for key in ("J_free", "I_free", "dI_free_dV"):
                out[key].append(free[key])
            if self.block is None:
                continue
            blocked = self.blocked(V, free)
            for key in ("V_ref", "u", "J_blocked", "I_blocked", "dI_blocked_dV",
                        "dJ_blocked_dc_o", "dJ_blocked_dc_i"):
                out[key].append(blocked[key])
            for k in range(len(self.modes)):
                out["theta"][k].append(blocked["theta"][k])
                out["one_minus_theta"][k].append(blocked["one_minus_theta"][k])
        return out
