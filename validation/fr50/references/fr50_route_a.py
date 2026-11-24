"""FR-50 references, route A: LAWS.md's forms in decimal arithmetic at 120 digits.

- One-way fluxes by LAWS.md 2's table, with B(x) = x/(e^x - 1) and e^x - 1 formed at raised
  precision.
- The transporter by LAWS.md 3: dG_cyc/(R T) as the sum the law writes, S, J+ = k a S and
  J- = J+ exp(dG_cyc/(R T)).
- FR-51's unblocked fraction by LAWS.md 4, with each 1 - theta formed directly.
- K2's trajectory and records by LAWS.md 5's closed form.
- E_K is the Nernst potential at 120 digits, rounded half-even to 50 significant digits. That
  50-digit value is both the voltage of E1 and E4 and the E_K of V_ref = V - E_K, so V_ref is
  exactly 0 at V = E_K.

Why 120 digits: at V = E_K the net is about 1e-50 of each one-way flux, and route B recovers each
flux from the net there. 120 digits keep every reported value correct far past its 30 digits.
"""

from __future__ import annotations

import decimal
from decimal import Decimal

from fr50_spec import Case, Samples, Spec

PREC = 120
E_DIGITS = 50
_TRAPS = [decimal.InvalidOperation, decimal.DivisionByZero, decimal.Overflow]
ONE = Decimal(1)
TO_FMOL = Decimal("1e15")  # m^3 -> pL, and mol -> fmol


def context(prec: int = PREC) -> decimal.Context:
    return decimal.Context(prec=prec, rounding=decimal.ROUND_HALF_EVEN, Emin=-999999,
                           Emax=999999, traps=_TRAPS)


def times(samples: Samples) -> list[Decimal]:
    with decimal.localcontext(context()):
        step = Decimal(samples.step)
        return [step * i for i in range(samples.last + 1)]


def F_over_RT(spec: Spec, T: str) -> tuple[Decimal, Decimal]:
    """F (C/mol) and F/(R T) (1/V)."""
    with decimal.localcontext(context()):
        F = Decimal(spec.F_factors[0]) * Decimal(spec.F_factors[1])
        R = Decimal(spec.R_factors[0]) * Decimal(spec.R_factors[1])
        return F, F / (R * Decimal(T))


def bern(x: Decimal) -> Decimal:
    """B(x) = x/(e^x - 1), B(0) = 1, with e^x - 1 at a precision raised by its cancellation."""
    if x == 0:
        return ONE
    with decimal.localcontext(context(PREC + 30 + max(0, -x.adjusted()))):
        em1 = x.exp() - ONE
    with decimal.localcontext(context()):
        return x / em1


def nernst_50(q: Decimal, z: int, c_in: str, c_out: str) -> tuple[Decimal, Decimal]:
    """E = (R T/(z F)) ln(c_out/c_in) at 120 digits, and its 50-digit rounding."""
    with decimal.localcontext(context()):
        E = (Decimal(c_out) / Decimal(c_in)).ln() / (z * q)
    E50 = Decimal(0) if E == 0 else context(E_DIGITS).plus(E)
    return E, E50


def unblocked_fraction(block: dict, q: Decimal, V_ref: Decimal) -> Decimal:
    """FR-51's u (LAWS.md 4): u = sum_k w_k K_k/(c_B + K_k) / sum_k w_k,
    K_k = K_k(0) exp(a_k V_ref), a_k = s sgn(z_B) m_k F/(R T)."""
    with decimal.localcontext(context()):
        blocker = block["blocker"]
        z_B = blocker["valence"]
        s = ONE if blocker["side"] == "outside" else -ONE
        sign = ONE if z_B > 0 else -ONE
        c_B = Decimal(blocker["concentration_mM"])
        numerator = Decimal(0)
        weights = Decimal(0)
        for mode in block["modes"]:
            if "electrical_distance" in mode:
                m = abs(Decimal(z_B)) * Decimal(mode["electrical_distance"])
            else:
                m = Decimal(mode["effective_valence"])
            K = Decimal(mode["k0_mM"]) * (s * sign * m * q * V_ref).exp()
            w = Decimal(mode["weight"])
            numerator += w * (K / (c_B + K))
            weights += w
        return numerator / weights


def patch_ghk(g: Decimal, c_in: Decimal, c_out: Decimal, x: Decimal) -> tuple[Decimal, Decimal]:
    """(outward, inward) one-way fluxes of a constant-field route: g c_in B(-x), g c_out B(x)."""
    with decimal.localcontext(context()):
        return g * c_in * bern(-x), g * c_out * bern(x)


def transporter(case: Case) -> dict:
    """LAWS.md 3 at the case's state."""
    with decimal.localcontext(context()):
        n = case["stoichiometry"]
        mu = case["mu0_over_RT"]
        fuel = case["fuel_mM"]
        c_in, c_out = Decimal(case["c_in_mM"]), Decimal(case["c_out_mM"])
        d_mu = Decimal(mu["ADP"]) + Decimal(mu["Pi"]) - Decimal(mu["ATP"])
        dG = (d_mu
              + (Decimal(fuel["ADP"]) * Decimal(fuel["Pi"])
                 / (Decimal(fuel["ATP"]) * Decimal(case["c0_mM"]))).ln()
              + n * (c_out / c_in).ln())
        S = (ONE / (ONE + (Decimal(case["K_mM"]) / c_in) ** n)
             / (ONE + Decimal(case["K_ATP_mM"]) / Decimal(fuel["ATP"])))
        J_plus = Decimal(case["capacity_fmol_cycles_per_s"]) * Decimal(case["availability"]) * S
        J_minus = J_plus * dG.exp()
        return {"dG_cyc_over_RT": dG, "S": S, "J_plus": J_plus, "J_minus": J_minus,
                "net": J_plus - J_minus, "J_minus_over_J_plus": J_minus / J_plus}


def records(flux_forward: Decimal, flux_backward: Decimal, ts: list[Decimal]) -> dict:
    with decimal.localcontext(context()):
        return {"F": [flux_forward * t for t in ts], "B": [flux_backward * t for t in ts]}


def relaxation(case: Case) -> dict:
    """K2 by LAWS.md 5's closed form: a neutral route between a cell and a finite node."""
    ts = times(case.record_times)
    with decimal.localcontext(context()):
        a = TO_FMOL * Decimal(case["P_m_per_s"]) * Decimal(case["A_m2"]) * Decimal(case["opening"])
        V_O, V_N = Decimal(case["V_cell_pL"]), Decimal(case["V_node_pL"])
        c_O0, c_N0 = Decimal(case["c_cell_mM_at_0"]), Decimal(case["c_node_mM_at_0"])
        k = a * (ONE / V_O + ONE / V_N)
        c_bar = (V_O * c_O0 + V_N * c_N0) / (V_O + V_N)
        d0 = c_O0 - c_bar
        out: dict = {"c_cell": [], "c_node": [], "F": [], "B": []}
        for t in ts:
            if t == 0:
                decay, integral = ONE, Decimal(0)
            else:
                with decimal.localcontext(context(PREC + 30)):
                    em1 = (-k * t).exp() - ONE  # e^(-kt) - 1
                decay = ONE + em1
                integral = -em1 / k  # integral of e^(-k t') from 0 to t
            out["c_cell"].append(c_bar + d0 * decay)
            out["c_node"].append(c_bar - (V_O / V_N) * d0 * decay)
            out["F"].append(a * (c_bar * t - (V_O / V_N) * d0 * integral))
            out["B"].append(a * (c_bar * t + d0 * integral))
        out["a"], out["k"], out["c_bar"] = a, k, c_bar
        return out


class CaseA:
    """One case evaluated by route A; `values` holds every reported quantity (Decimal)."""

    def __init__(self, spec: Spec, case: Case):
        self.case = case
        kind = case.kind
        T = case["T_K"]
        self.F, self.q = F_over_RT(spec, T)
        v: dict = {}
        with decimal.localcontext(context()):
            if kind in ("K1",):
                a = TO_FMOL * Decimal(case["P_m_per_s"]) * Decimal(case["A_m2"]) \
                    * Decimal(case["opening"])
                v["g"] = a
                v["forward"] = a * Decimal(case["c_node_mM"])  # inward: a c_out
                v["backward"] = a * Decimal(case["c_cell_mM"])
            elif kind == "E2":
                g = (TO_FMOL * Decimal(case["P_m_per_s"]) * Decimal(case["A_m2"])
                     * Decimal(case["gate"]) * Decimal(case["availability"]))
                v["g"] = g
                v["forward"] = g * Decimal(case["c_sender_mM"])  # neutral: B = 1
                v["backward"] = g * Decimal(case["c_receiver_mM"])
            elif kind == "E3":
                g = (TO_FMOL * Decimal(case["D_m2_per_s"]) * Decimal(case["A_m2"])
                     / Decimal(case["L_m"]))
                v["g"] = g
                v["forward"] = g * Decimal(case["c_sender_mM"])
                v["backward"] = g * Decimal(case["c_receiver_mM"])
            elif kind in ("E1", "E4"):
                z = case["valence"]
                self.E_full, self.E_K = nernst_50(self.q, z, case["c_in_mM"], case["c_out_mM"])
                V = self.E_K
                g = TO_FMOL * Decimal(case["P_m_per_s"]) * Decimal(case["A_m2"])
                g *= Decimal(case["availability"])
                if kind == "E4":
                    g *= (Decimal(case["relative_permeability"]) * Decimal(case["abundance"])
                          * Decimal(case["open_fraction"]))
                    v["u"] = unblocked_fraction(case["block"], self.q, V - self.E_K)
                    g *= v["u"]
                v["g"] = g
                x = z * self.q * V
                v["forward"], v["backward"] = patch_ghk(g, Decimal(case["c_in_mM"]),
                                                        Decimal(case["c_out_mM"]), x)
            elif kind in ("K4", "K4h"):
                v.update(transporter(case))
                v["forward"], v["backward"] = v["J_plus"], v["J_minus"]
            elif kind == "K2":
                v.update(relaxation(case))
            elif kind == "K3":
                self.evaluations = self._k3(case)
            elif kind == "E6":
                self.evaluations = self._e6(case)
            if kind in ("K1", "E1", "E2", "E3", "E4", "K4"):
                v["net"] = v["forward"] - v["backward"]
                v.update(records(v["forward"], v["backward"], times(case.record_times)))
        self.values = v

    def _k3(self, case: Case) -> list[dict]:
        z = case["valence"]
        g = TO_FMOL * Decimal(case["P_m_per_s"]) * Decimal(case["A_m2"]) * Decimal(case["opening"])
        c_in, c_out = Decimal(case["c_in_mM"]), Decimal(case["c_out_mM"])
        out = []
        for text in case["voltages_V"]:
            V = Decimal(text)
            outward, inward = patch_ghk(g, c_in, c_out, z * self.q * V)
            out.append({"V": V, "forward": inward, "backward": outward,
                        "ratio_inward_over_outward": inward / outward,
                        "ratio_backward_over_forward": outward / inward})
        return out

    def _e6(self, case: Case) -> list[dict]:
        z = case["valence"]
        self.E_full, self.E_K = nernst_50(self.q, z, case["c_in_mM"], case["c_out_mM"])
        c_in, c_out = Decimal(case["c_in_mM"]), Decimal(case["c_out_mM"])
        base = (TO_FMOL * Decimal(case["P_m_per_s"]) * Decimal(case["A_m2"])
                * Decimal(case["relative_permeability"]) * Decimal(case["abundance"])
                * Decimal(case["open_fraction"]))
        out = []
        for availability in case["availabilities"]:
            for text in case["voltages_V"]:
                V = Decimal(text)
                V_ref = V - self.E_K
                u = unblocked_fraction(case["block"], self.q, V_ref)
                g = base * Decimal(availability) * u
                outward, inward = patch_ghk(g, c_in, c_out, z * self.q * V)
                out.append({"V": V, "availability": availability, "V_ref": V_ref, "u": u,
                            "forward": outward, "backward": inward,
                            "ratio_inward_over_outward": inward / outward,
                            "ratio_backward_over_forward": inward / outward,
                            "difference": outward - inward})
        return out
