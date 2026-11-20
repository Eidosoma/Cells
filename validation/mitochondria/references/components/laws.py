"""The appendix's six declared laws, written from its equations alone.

Source: docs/MITOCHONDRIA_LAWS_APPENDIX.md at tag mito-laws-appendix-2026-11-20 (sections 0-7).
Every function is generic over a backend ``B`` (``hp.DEC`` or ``hp.F64``), a parameter dict
``P`` of strings (``hp.parameters``), constants ``C`` (``hp.constants``) and a state ``s``:
a dict of concentrations in M, free h_N and h_P in M, and ``dpsi_mV`` (phi_P - phi_N).

Each law is computed along separate paths that the checks compare:
1. ``x_terms``: x = dG/RT from the turnover's table alone, (species, side, nu, z) and dG0 at
   1 M: x = dG0/RT + sum(nu ln a) + q u, with q = sum over P-side legs of nu z.
2. ``printed``: the source's printed equation, transcribed term by term in its own pH-7 form
   (each scalar proton as RT ln(h_N/1e-7 M)), returning its forward and backward terms.
3. ``dG_appendix``: the law's free energy as the appendix writes it in its section.
4. ``S_closed`` and ``backward_closed``: the appendix's stated closed forms of S and of the
   balanced backward term.
5. ``slopes_lnA`` and ``slopes_lnB``: hand-derived log-slopes, checked against numerical
   differentiation of paths 1 and 2.

The declared form is J = S (1 - e^x). With J = A (1 - e^{x/n}) for n = kappa_inv (1, 2 or 4),
S = A / sum_{j<n} e^{j x/n}. A balanced law keeps the printed forward term A.
"""
from __future__ import annotations

from . import hp

TEN_M7 = "1e-7"  # the source's pH-7 proton concentration, M


def _u(C, s):
    return C["F_RT_per_mV"] * s["dpsi_mV"]


def _sum(xs):
    it = iter(xs)
    total = next(it)
    for v in it:
        total = total + v
    return total


class Law:
    """A thermodynamic cycle law J = S (1 - e^x)."""

    key = ""
    law_id = ""
    section = ""
    title = ""
    legs: tuple = ()  # (state key or None for water at activity 1, side, nu, z)
    kappa_inv = 1
    column = "with"
    reads_S: tuple = ()  # literal "Reads" of S, without dpsi_mV
    reads_x: tuple = ()  # literal "Reads" of x, without dpsi_mV
    printed_eq = ""
    printed_fails = False
    has_flux = True
    scalar_protons = 0  # nu_H of the pH-7 conversion: dG0(1 M) = dG0(pH 7) + nu_H RT ln 1e7

    # --- stoichiometry ------------------------------------------------------------------------
    def legs_(self, P):
        return self.legs

    def nu(self, P) -> dict:
        out = {}
        for k, _side, nu, _z in self.legs_(P):
            if k is not None:
                out[k] = out.get(k, 0) + nu
        return out

    def q(self, P) -> int:
        return sum(nu * z for _k, side, nu, z in self.legs_(P) if side == "P")

    def q_N(self, P) -> int:
        return sum(nu * z for _k, side, nu, z in self.legs_(P) if side == "N")

    def reads(self):
        out = []
        for v in tuple(self.reads_S) + tuple(self.reads_x):
            if v not in out:
                out.append(v)
        return out

    def dG0_pH7(self, B, P):
        raise NotImplementedError

    def dG0_1M(self, B, P, C):
        return self.dG0_pH7(B, P) + B.n(self.scalar_protons) * C["RT_ln_1e7"]

    # --- path 1 -------------------------------------------------------------------------------
    def x_terms(self, B, P, C, s):
        terms = [("dG0", self.dG0_1M(B, P, C) / C["RT"])]
        for k, _side, nu, _z in self.legs_(P):
            if k is None:
                continue
            terms.append((k, B.n(nu) * B.ln(s[k])))
        terms.append(("u", B.n(self.q(P)) * _u(C, s)))
        return terms

    def x(self, B, P, C, s):
        return _sum(v for _k, v in self.x_terms(B, P, C, s))

    # --- forms ------------------------------------------------------------------------------
    # form -> (kind, balanced). "kappa": J = A (1 - e^{kappa x}) with S = A / sum_j e^{j kappa x};
    # "two_term": J = A - B with both terms as written (a form that fails the check).
    FORMS = {"declared": ("kappa", True)}

    def form_kind(self, form):
        if form == "printed":
            return "two_term"
        return self.FORMS[form][0]

    # Per form, what its terms read (dpsi_mV aside), where a form departs from the law's line:
    # {form: {"A": (...), "B": (...)}}. A kappa form's S also reads x's inputs when kappa < 1.
    FORM_READS: dict = {}

    def form_reads(self, form):
        if form in self.FORM_READS:
            return {k: list(v) for k, v in self.FORM_READS[form].items()}
        return {"A": list(self.reads_S)}

    def form_balanced(self, form):
        return self.FORMS.get(form, ("two_term", False))[1] if form != "printed" else (
            not self.printed_fails)

    def form_forward(self, form, B, P, C, s):
        """A kappa form's forward term A (computed from the printed terms, so that a plant's
        override of ``printed`` reaches every form)."""
        return self.printed(B, P, C, s)[0]

    def form_terms(self, form, B, P, C, s):
        """A two-term form's (A, B)."""
        return self.printed(B, P, C, s)

    def form_slopes_A(self, form, B, P, C, s):
        return self.slopes_lnA(B, P, C, s)

    def form_slopes_B(self, form, B, P, C, s):
        return self.slopes_lnB(B, P, C, s)

    def literal_terms(self, form, B, P, C, s):
        """The form's two terms transcribed literally from the appendix (an independent path)."""
        return self.printed(B, P, C, s)

    def form_d_closed(self, form, B, P, C, s):
        """A failing two-term form's mismatch d = kappa^-1 ln(B/A) - x, in closed form."""
        if form == "printed":
            return self.d_closed(B, P, C, s)
        raise ValueError(form)

    # --- the rest is per law ------------------------------------------------------------------
    def printed(self, B, P, C, s):
        raise NotImplementedError

    def dG_appendix(self, B, P, C, s):
        raise NotImplementedError

    def S_closed(self, B, P, C, s):
        raise NotImplementedError

    def slopes_lnA(self, B, P, C, s) -> dict:
        raise NotImplementedError

    def slopes_lnB(self, B, P, C, s) -> dict:
        raise NotImplementedError

    @staticmethod
    def _dGH(B, C, s):
        """dG_H = F dpsi + RT ln(h_P/h_N), J/mol, with F dpsi = RT u."""
        return C["RT"] * (_u(C, s) + B.ln(s["h_P"] / s["h_N"]))


# ============================================================================================
# Section 1: redox_driven_proton_cycle@1
# ============================================================================================
class ComplexI(Law):
    key = "complex_I"
    law_id = "redox_driven_proton_cycle@1"
    section = "1.1"
    title = "Complex I, per NADH (Eqs. 2-5)"
    legs = (
        ("NADH_N", "N", -1, -2),
        ("Q_N", "N", -1, 0),
        ("NAD_N", "N", 1, -1),
        ("QH2_N", "N", 1, 0),
        ("h_N", "N", -5, 1),
        ("h_P", "P", 4, 1),
    )
    scalar_protons = -1
    reads_S = ("NADH_N", "NAD_N", "Q_N", "QH2_N", "h_N", "h_P")
    reads_x = ("NADH_N", "NAD_N", "Q_N", "QH2_N", "h_N", "h_P")
    printed_eq = "Eq. 3"

    def dG0_pH7(self, B, P):
        return B.n(P["dG0_C1_pH7"])

    def printed(self, B, P, C, s):
        RT = C["RT"]
        dGH = self._dGH(B, C, s)
        expo = -(
            B.n(P["dG0_C1_pH7"])
            + 4 * dGH
            - RT * B.ln(s["h_N"] / B.n(TEN_M7))
            - RT * B.ln(s["Q_N"] / s["QH2_N"])
        ) / RT
        X = B.n(P["X_C1"])
        return X * B.exp(expo) * s["NADH_N"], X * s["NAD_N"]

    def dG_appendix(self, B, P, C, s):
        RT = C["RT"]
        return (
            B.n(P["dG0_C1_pH7"])
            + RT * B.ln(s["NAD_N"] * s["QH2_N"] / (s["NADH_N"] * s["Q_N"]))
            - RT * B.ln(s["h_N"] / B.n(TEN_M7))
            + 4 * self._dGH(B, C, s)
        )

    def S_closed(self, B, P, C, s):
        # S = X_C1 e^{-dG0_C1/RT} 1e7 [NADH][Q][QH2]^-1 h_N^5 h_P^-4 e^{-4u}
        return (
            B.n(P["X_C1"])
            * B.exp(-B.n(P["dG0_C1_pH7"]) / C["RT"])
            * B.n("1e7")
            * s["NADH_N"]
            * s["Q_N"]
            / s["QH2_N"]
            * s["h_N"] ** 5
            / s["h_P"] ** 4
            * B.exp(-4 * _u(C, s))
        )

    def slopes_lnA(self, B, P, C, s):
        n = B.n
        return {"NADH_N": n(1), "NAD_N": n(0), "Q_N": n(1), "QH2_N": n(-1), "h_N": n(5),
                "h_P": n(-4), "u": n(-4)}

    def slopes_lnB(self, B, P, C, s):
        n = B.n
        return {"NADH_N": n(0), "NAD_N": n(1), "Q_N": n(0), "QH2_N": n(0), "h_N": n(0),
                "h_P": n(0), "u": n(0)}


class _ComplexIII(Law):
    law_id = "redox_driven_proton_cycle@1"
    section = "1.2"
    legs = (
        ("QH2_N", "N", -1, 0),
        ("Q_N", "N", 1, 0),
        ("c3_P", "P", -2, 3),
        ("c2_P", "P", 2, 2),
        ("h_N", "N", -2, 1),
        ("h_P", "P", 4, 1),
    )
    scalar_protons = 2
    kappa_inv = 2

    def dG0_pH7(self, B, P):
        return B.n(P["dG0_C3_pH7"])

    def dG_appendix(self, B, P, C, s):
        RT = C["RT"]
        return (
            B.n(P["dG0_C3_pH7"])
            + RT * B.ln(s["Q_N"] * s["c2_P"] ** 2 / (s["QH2_N"] * s["c3_P"] ** 2))
            + 2 * RT * B.ln(s["h_N"] / B.n(TEN_M7))
            + 4 * self._dGH(B, C, s)
            - 2 * RT * _u(C, s)
        )


class ComplexIIIEq7(_ComplexIII):
    key = "complex_III_eq7"
    title = "Complex III without phosphate control, per QH2 (Eqs. 6, 7)"
    column = "without"
    reads_S = ("QH2_N", "Q_N", "c3_P", "c2_P", "h_N", "h_P")
    reads_x = ("QH2_N", "Q_N", "c3_P", "c2_P", "h_N", "h_P")
    printed_eq = "Eq. 7"

    def printed(self, B, P, C, s):
        RT = C["RT"]
        Fdpsi = RT * _u(C, s)
        expo = -(
            B.n(P["dG0_C3_pH7"])
            + 4 * self._dGH(B, C, s)
            + 2 * RT * B.ln(s["h_N"] / B.n(TEN_M7))
            - 2 * Fdpsi
            + RT * B.ln(s["Q_N"] / s["QH2_N"])
        ) / (2 * RT)
        X = B.n(P["X_C3"])
        return X * B.exp(expo) * s["c3_P"], X * s["c2_P"]

    def S_closed(self, B, P, C, s):
        A, _ = self.printed(B, P, C, s)
        return A / (1 + B.exp(self.x(B, P, C, s) / 2))

    def slopes_lnA(self, B, P, C, s):
        n = B.n
        return {"QH2_N": n("0.5"), "Q_N": n("-0.5"), "c3_P": n(1), "c2_P": n(0), "h_N": n(1),
                "h_P": n(-2), "u": n(-1)}

    def slopes_lnB(self, B, P, C, s):
        n = B.n
        return {"QH2_N": n(0), "Q_N": n(0), "c3_P": n(0), "c2_P": n(1), "h_N": n(0),
                "h_P": n(0), "u": n(0)}


class ComplexIIIEq24(_ComplexIII):
    key = "complex_III_eq24"
    title = "Complex III with phosphate control, per QH2 (Eq. 24)"
    column = "with"
    reads_S = ("QH2_N", "Q_N", "c3_P", "c2_P", "h_N", "h_P", "Pi_N")
    reads_x = ("QH2_N", "Q_N", "c3_P", "c2_P", "h_N", "h_P")
    printed_eq = "Eq. 24"
    printed_fails = True
    # "restored": Eq. 24 with its dropped term +2RT ln(h_N/1e-7) put back, i.e. phi_Pi times
    # Eq. 7 at the With column's X_C3 (the lead, 20 November). It keeps the printed backward term.
    FORMS = {"balanced": ("kappa", True), "printed": ("two_term", False),
             "restored": ("kappa", True)}
    FORM_READS = {"printed": {"A": ("QH2_N", "Q_N", "c3_P", "h_N", "h_P", "Pi_N"),
                              "B": ("c2_P", "Pi_N")}}

    def form_forward(self, form, B, P, C, s):
        A, _ = self.printed(B, P, C, s)
        if form == "restored":
            return A * B.n(TEN_M7) / s["h_N"]
        return A

    def form_slopes_A(self, form, B, P, C, s):
        d = dict(self.slopes_lnA(B, P, C, s))
        if form == "restored":
            d["h_N"] = d["h_N"] - 1
        return d

    def literal_terms(self, form, B, P, C, s):
        if form == "restored":
            RT = C["RT"]
            Fdpsi = RT * _u(C, s)
            expo = -(
                B.n(P["dG0_C3_pH7"])
                + 4 * self._dGH(B, C, s)
                + 2 * RT * B.ln(s["h_N"] / B.n(TEN_M7))
                - 2 * Fdpsi
                + RT * B.ln(s["Q_N"] / s["QH2_N"])
            ) / (2 * RT)
            Xphi = B.n(P["X_C3"]) * self.phi(B, P, s)
            return Xphi * B.exp(expo) * s["c3_P"], Xphi * s["c2_P"]
        if form == "balanced":
            return self.printed(B, P, C, s)[0], self.backward_closed(B, P, C, s)
        return self.printed(B, P, C, s)

    @staticmethod
    def phi(B, P, s):
        k3 = B.n(P["k_Pi3_mM"]) / 1000
        k4 = B.n(P["k_Pi4_mM"]) / 1000
        return (1 + s["Pi_N"] / k3) / (1 + s["Pi_N"] / k4)

    def printed(self, B, P, C, s):
        RT = C["RT"]
        Fdpsi = RT * _u(C, s)
        expo = -(
            B.n(P["dG0_C3_pH7"])
            + 4 * self._dGH(B, C, s)
            - 2 * Fdpsi
            + RT * B.ln(s["Q_N"] / s["QH2_N"])
        ) / (2 * RT)
        Xphi = B.n(P["X_C3"]) * self.phi(B, P, s)
        return Xphi * B.exp(expo) * s["c3_P"], Xphi * s["c2_P"]

    def S_closed(self, B, P, C, s):
        A, _ = self.printed(B, P, C, s)
        return A / (1 + B.exp(self.x(B, P, C, s) / 2))

    def backward_closed(self, B, P, C, s):
        """The balanced backward term as the appendix states it: X_C3 phi [c2+] h_N/1e-7."""
        return B.n(P["X_C3"]) * self.phi(B, P, s) * s["c2_P"] * s["h_N"] / B.n(TEN_M7)

    def d_closed(self, B, P, C, s):
        """Eq. 24's mismatch d = 2 ln(B/A) - x = -2 ln(h_N/1e-7)."""
        return -2 * B.ln(s["h_N"] / B.n(TEN_M7))

    def _phi_slope(self, B, P, s):
        k3 = B.n(P["k_Pi3_mM"]) / 1000
        k4 = B.n(P["k_Pi4_mM"]) / 1000
        Pi = s["Pi_N"]
        return Pi / (k3 + Pi) - Pi / (k4 + Pi)

    def slopes_lnA(self, B, P, C, s):
        n = B.n
        return {"QH2_N": n("0.5"), "Q_N": n("-0.5"), "c3_P": n(1), "c2_P": n(0), "h_N": n(2),
                "h_P": n(-2), "Pi_N": self._phi_slope(B, P, s), "u": n(-1)}

    def slopes_lnB(self, B, P, C, s):
        n = B.n
        return {"QH2_N": n(0), "Q_N": n(0), "c3_P": n(0), "c2_P": n(1), "h_N": n(0),
                "h_P": n(0), "Pi_N": self._phi_slope(B, P, s), "u": n(0)}


class ComplexIV(Law):
    key = "complex_IV"
    law_id = "redox_driven_proton_cycle@1"
    section = "1.3"
    title = "Complex IV, per O2 (Eqs. 8, 9)"
    legs = (
        ("O2_N", "N", -1, 0),
        ("c2_P", "P", -4, 2),
        ("c3_P", "P", 4, 3),
        ("h_N", "N", -8, 1),
        ("h_P", "P", 4, 1),
        (None, "N", 2, 0),  # 2 H2O at activity 1
    )
    scalar_protons = -4
    kappa_inv = 4
    reads_S = ("O2_N", "c2_P", "c3_P", "h_N", "h_P")
    reads_x = ("O2_N", "c2_P", "c3_P", "h_N", "h_P")
    printed_eq = "Eq. 9"

    def dG0_pH7(self, B, P):
        return 2 * B.n(P["dG0_C4_pH7_half_O2"])

    @staticmethod
    def _pref(B, P, s, ctot=None):
        f_O2 = 1 / (1 + B.n(P["k_O2"]) / s["O2_N"])
        c_tot = s["c3_P"] + s["c2_P"] if ctot is None else ctot
        return B.n(P["X_C4"]) * f_O2 * (s["c2_P"] / c_tot)

    def printed_per_two_electrons(self, B, P, C, s, ctot=None):
        RT = C["RT"]
        expo = -(
            B.n(P["dG0_C4_pH7_half_O2"])
            + 2 * self._dGH(B, C, s)
            - 2 * RT * B.ln(s["h_N"] / B.n(TEN_M7))
            - RT * B.ln(s["O2_N"]) / 2
        ) / (2 * RT)
        pref = self._pref(B, P, s, ctot)
        return pref * B.exp(expo) * s["c2_P"], pref * B.exp(_u(C, s)) * s["c3_P"]

    def printed(self, B, P, C, s):
        A9, B9 = self.printed_per_two_electrons(B, P, C, s)
        return A9 / 2, B9 / 2  # J = J_C4/2 per O2

    def dG_appendix(self, B, P, C, s):
        RT = C["RT"]
        return (
            2 * B.n(P["dG0_C4_pH7_half_O2"])
            + RT * B.ln(s["c3_P"] ** 4 / (s["c2_P"] ** 4 * s["O2_N"]))
            - 4 * RT * B.ln(s["h_N"] / B.n(TEN_M7))
            + 4 * self._dGH(B, C, s)
            + 4 * RT * _u(C, s)
        )

    def S_closed(self, B, P, C, s):
        A, _ = self.printed(B, P, C, s)
        x = self.x(B, P, C, s)
        return A / (1 + B.exp(x / 4) + B.exp(x / 2) + B.exp(3 * x / 4))

    def slopes_lnA(self, B, P, C, s):
        n = B.n
        c_tot = s["c2_P"] + s["c3_P"]
        kO2 = n(P["k_O2"])
        return {
            "O2_N": n("0.25") + kO2 / (s["O2_N"] + kO2),
            "c2_P": 1 + s["c3_P"] / c_tot,
            "c3_P": -s["c3_P"] / c_tot,
            "h_N": n(2),
            "h_P": n(-1),
            "u": n(-1),
        }

    def slopes_lnB(self, B, P, C, s):
        n = B.n
        c_tot = s["c2_P"] + s["c3_P"]
        kO2 = n(P["k_O2"])
        return {
            "O2_N": kO2 / (s["O2_N"] + kO2),
            "c2_P": s["c3_P"] / c_tot,
            "c3_P": s["c2_P"] / c_tot,
            "h_N": n(0),
            "h_P": n(0),
            "u": n(1),
        }


class LumpedQuinolOxygen(Law):
    """Section 1.4: stoichiometry and free energy only; the source prints no kinetics."""

    key = "lumped_QO"
    law_id = "redox_driven_proton_cycle@1"
    section = "1.4"
    title = "Lumped quinol-to-oxygen cycle, per O2 (no kinetics)"
    legs = (
        ("QH2_N", "N", -2, 0),
        ("Q_N", "N", 2, 0),
        ("O2_N", "N", -1, 0),
        ("h_N", "N", -12, 1),
        ("h_P", "P", 12, 1),
        (None, "N", 2, 0),
    )
    scalar_protons = 0
    reads_S = ()
    reads_x = ("QH2_N", "Q_N", "O2_N", "h_N", "h_P")
    has_flux = False

    def dG0_pH7(self, B, P):
        return 2 * (B.n(P["dG0_C3_pH7"]) + B.n(P["dG0_C4_pH7_half_O2"]))

    def dG_appendix(self, B, P, C, s):
        RT = C["RT"]
        return (
            self.dG0_pH7(B, P)
            + RT * B.ln(s["Q_N"] ** 2 / (s["QH2_N"] ** 2 * s["O2_N"]))
            + 12 * self._dGH(B, C, s)
        )


# ============================================================================================
# Section 2: proton_coupled_atp_synthesis_cycle@1
# ============================================================================================
class ATPSynthase(Law):
    key = "atp_synthase"
    law_id = "proton_coupled_atp_synthesis_cycle@1"
    section = "2"
    title = "ATP synthesis, per ATP (Eqs. 10, 11)"
    reads_S = ("MgADP_N", "Pi_N", "h_N", "h_P")
    reads_x = ("ATP4_N", "ADP3_N", "HPO4_N", "h_N", "h_P")
    printed_eq = "Eq. 11"
    printed_fails = True
    # "proton_restored": the matrix proton that Eq. 10 consumes put back into Eq. 11's exponent
    # (forward term times h_N/1e-7). It balances in the source's frame (total Pi as one species)
    # but not in the declared base forms, where it still fails by
    # -ln[(1 + h_N/k_dH)/(1 + 1e-7/k_dH)].
    # "base_form_restored": the forward term reads HPO4(2-) and the consumed proton, normalized
    # at pH 7. It keeps the printed backward term and balances in the declared frame.
    FORMS = {"balanced": ("kappa", True), "printed": ("two_term", False),
             "proton_restored": ("two_term", False), "base_form_restored": ("kappa", True)}
    FORM_READS = {
        "printed": {"A": ("MgADP_N", "Pi_N", "h_N", "h_P"), "B": ("MgATP_N",)},
        "proton_restored": {"A": ("MgADP_N", "Pi_N", "h_N", "h_P"), "B": ("MgATP_N",)},
        "base_form_restored": {"A": ("MgADP_N", "HPO4_N", "h_N", "h_P")},
    }

    def form_terms(self, form, B, P, C, s):
        A, Bp = self.printed(B, P, C, s)
        if form == "proton_restored":
            return A * s["h_N"] / B.n(TEN_M7), Bp
        return A, Bp

    def form_forward(self, form, B, P, C, s):
        A, _ = self.printed(B, P, C, s)
        if form == "base_form_restored":
            t = B.n(TEN_M7)
            return A * (s["h_N"] / t) * (1 + t / B.n(P["k_dH"])) * s["HPO4_N"] / s["Pi_N"]
        return A

    def form_slopes_A(self, form, B, P, C, s):
        d = dict(self.slopes_lnA(B, P, C, s))
        if form in ("proton_restored", "base_form_restored"):
            d["h_N"] = d["h_N"] + 1
        if form == "base_form_restored":
            d["Pi_N"] = d["Pi_N"] - 1
            d["HPO4_N"] = d["HPO4_N"] + 1
        return d

    def literal_terms(self, form, B, P, C, s):
        RT = C["RT"]
        nA = B.n(int(P["n_A"]))
        X = B.n(P["X_F1"])
        ratio = B.n(P["K_MgADP"]) / B.n(P["K_MgATP"])
        expo_r = -(B.n(P["dG0_ATP_pH7"]) - nA * self._dGH(B, C, s)
                   - RT * B.ln(s["h_N"] / B.n(TEN_M7))) / RT
        if form == "proton_restored":
            return X * B.exp(expo_r) * ratio * s["MgADP_N"] * s["Pi_N"], X * s["MgATP_N"]
        if form == "base_form_restored":
            norm = 1 + B.n(TEN_M7) / B.n(P["k_dH"])
            return X * B.exp(expo_r) * ratio * s["MgADP_N"] * s["HPO4_N"] * norm, X * s["MgATP_N"]
        if form == "balanced":
            return self.printed(B, P, C, s)[0], self.backward_closed(B, P, C, s)
        return self.printed(B, P, C, s)

    def form_d_closed(self, form, B, P, C, s):
        if form == "proton_restored":
            t = B.n(TEN_M7)
            k = B.n(P["k_dH"])
            return -B.ln((1 + s["h_N"] / k) / (1 + t / k))
        return super().form_d_closed(form, B, P, C, s)

    def legs_(self, P):
        nA = int(P["n_A"])
        return (
            ("ADP3_N", "N", -1, -3),
            ("HPO4_N", "N", -1, -2),
            ("ATP4_N", "N", 1, -4),
            (None, "N", 1, 0),  # H2O
            ("h_N", "N", nA - 1, 1),
            ("h_P", "P", -nA, 1),
        )

    def dG0_pH7(self, B, P):
        return B.n(P["dG0_ATP_pH7"])

    def dG0_1M(self, B, P, C):
        """dG0_F = dG0_ATP + RT ln(1e-7) - RT ln(1 + 1e-7 M/k_dH) (appendix section 2)."""
        RT = C["RT"]
        t = B.n(TEN_M7)
        return B.n(P["dG0_ATP_pH7"]) + RT * B.ln(t) - RT * B.ln(1 + t / B.n(P["k_dH"]))

    def printed(self, B, P, C, s):
        RT = C["RT"]
        nA = B.n(int(P["n_A"]))
        expo = -(B.n(P["dG0_ATP_pH7"]) - nA * self._dGH(B, C, s)) / RT
        X = B.n(P["X_F1"])
        ratio = B.n(P["K_MgADP"]) / B.n(P["K_MgATP"])
        return X * B.exp(expo) * ratio * s["MgADP_N"] * s["Pi_N"], X * B.n(1) * s["MgATP_N"]

    def dG_appendix(self, B, P, C, s):
        RT = C["RT"]
        nA = B.n(int(P["n_A"]))
        return (
            self.dG0_1M(B, P, C)
            + RT * B.ln(s["ATP4_N"] / (s["ADP3_N"] * s["HPO4_N"] * s["h_N"]))
            - nA * self._dGH(B, C, s)
        )

    def x_source_frame(self, B, P, C, s):
        """x in the source's own frame: total Pi as one species, Eq. 10's scalar proton."""
        RT = C["RT"]
        nA = B.n(int(P["n_A"]))
        return (
            B.n(P["dG0_ATP_pH7"])
            + RT * B.ln(s["ATP4_N"] / (s["ADP3_N"] * s["Pi_N"]))
            - RT * B.ln(s["h_N"] / B.n(TEN_M7))
            - nA * self._dGH(B, C, s)
        ) / RT

    def S_closed(self, B, P, C, s):
        nA = int(P["n_A"])
        return (
            B.n(P["X_F1"])
            * B.exp(-B.n(P["dG0_ATP_pH7"]) / C["RT"])
            * (B.n(P["K_MgADP"]) / B.n(P["K_MgATP"]))
            * s["MgADP_N"]
            * s["Pi_N"]
            * s["h_P"] ** nA
            / s["h_N"] ** nA
            * B.exp(B.n(nA) * _u(C, s))
        )

    def backward_closed(self, B, P, C, s):
        """X_F1 (1 M)[MgATP] (1e-7/h_N)(1 + h_N/k_dH)/(1 + 1e-7/k_dH): binding at equilibrium."""
        t = B.n(TEN_M7)
        k = B.n(P["k_dH"])
        return B.n(P["X_F1"]) * s["MgATP_N"] * (t / s["h_N"]) * (1 + s["h_N"] / k) / (1 + t / k)

    def d_closed(self, B, P, C, s):
        """Eq. 11's mismatch ln(B/A) - x = ln(h_N/1e-7) - ln[(1 + h_N/k_dH)/(1 + 1e-7/k_dH)]."""
        t = B.n(TEN_M7)
        k = B.n(P["k_dH"])
        return B.ln(s["h_N"] / t) - B.ln((1 + s["h_N"] / k) / (1 + t / k))

    def d_closed_source_frame(self, B, P, C, s):
        return B.ln(s["h_N"] / B.n(TEN_M7))

    def slopes_lnA(self, B, P, C, s):
        n = B.n
        nA = n(int(P["n_A"]))
        return {"MgADP_N": n(1), "Pi_N": n(1), "h_N": -nA, "h_P": nA, "ATP4_N": n(0),
                "ADP3_N": n(0), "HPO4_N": n(0), "u": nA}

    def slopes_lnB(self, B, P, C, s):
        n = B.n
        return {"MgATP_N": n(1), "MgADP_N": n(0), "Pi_N": n(0), "h_N": n(0), "h_P": n(0),
                "ATP4_N": n(0), "ADP3_N": n(0), "HPO4_N": n(0), "u": n(0)}


# ============================================================================================
# Section 3: electrogenic_nucleotide_exchange@1
# ============================================================================================
class NucleotideExchange(Law):
    key = "nucleotide_exchange"
    law_id = "electrogenic_nucleotide_exchange@1"
    section = "3"
    title = "Adenine nucleotide exchange, ATP out for ADP in (Eq. 14)"
    legs = (
        ("ATP4_N", "N", -1, -4),
        ("ATP4_P", "P", 1, -4),
        ("ADP3_P", "P", -1, -3),
        ("ADP3_N", "N", 1, -3),
    )
    reads_S = ("ATP4_N", "ADP3_N", "ATP4_P", "ADP3_P")
    reads_x = ("ATP4_N", "ADP3_N", "ATP4_P", "ADP3_P")
    printed_eq = "Eq. 14"

    def dG0_pH7(self, B, P):
        return B.n(0)

    def _abcd(self, B, P, C, s):
        u = _u(C, s)
        a = s["ADP3_P"]
        b = s["ATP4_P"] * B.exp(-B.n(P["theta_P"]) * u)
        c = s["ADP3_N"]
        d = s["ATP4_N"] * B.exp(B.n(P["theta_N"]) * u)
        g = 1 / (1 + B.n(P["k_mADP"]) / a)
        return a, b, c, d, g

    def printed_literal(self, B, P, C, s):
        """Eq. 14 exactly as printed: X {a/(a+b) - c/(c+d)} / (1 + k_mADP/a)."""
        a, b, c, d, g = self._abcd(B, P, C, s)
        return B.n(P["X_ANT"]) * (a / (a + b) - c / (c + d)) * g

    def printed(self, B, P, C, s):
        a, b, c, d, g = self._abcd(B, P, C, s)
        den = (a + b) * (c + d)
        X = B.n(P["X_ANT"])
        return X * g * a * d / den, X * g * b * c / den

    def dG_appendix(self, B, P, C, s):
        RT = C["RT"]
        return RT * B.ln(s["ATP4_P"] * s["ADP3_N"] / (s["ATP4_N"] * s["ADP3_P"])) - RT * _u(C, s)

    def S_closed(self, B, P, C, s):
        u = _u(C, s)
        tP, tN = B.n(P["theta_P"]), B.n(P["theta_N"])
        num = s["ADP3_P"] * s["ATP4_N"] * B.exp(tN * u)
        den = (s["ADP3_P"] + s["ATP4_P"] * B.exp(-tP * u)) * (s["ADP3_N"] + s["ATP4_N"] * B.exp(tN * u))
        return B.n(P["X_ANT"]) * num / den / (1 + B.n(P["k_mADP"]) / s["ADP3_P"])

    def slopes_lnA(self, B, P, C, s):
        a, b, c, d, _g = self._abcd(B, P, C, s)
        km = B.n(P["k_mADP"])
        tP, tN = B.n(P["theta_P"]), B.n(P["theta_N"])
        return {
            "ADP3_P": km / (a + km) + b / (a + b),
            "ATP4_P": -b / (a + b),
            "ADP3_N": -c / (c + d),
            "ATP4_N": c / (c + d),
            "u": tN * c / (c + d) + tP * b / (a + b),
        }

    def slopes_lnB(self, B, P, C, s):
        a, b, c, d, _g = self._abcd(B, P, C, s)
        km = B.n(P["k_mADP"])
        tP, tN = B.n(P["theta_P"]), B.n(P["theta_N"])
        return {
            "ADP3_P": km / (a + km) - a / (a + b),
            "ATP4_P": a / (a + b),
            "ADP3_N": d / (c + d),
            "ATP4_N": -d / (c + d),
            "u": -tP * a / (a + b) - tN * d / (c + d),
        }


# ============================================================================================
# Section 4: phosphate_proton_symport@1
# ============================================================================================
class PhosphateCarrier(Law):
    key = "phosphate_carrier"
    law_id = "phosphate_proton_symport@1"
    section = "4"
    title = "Phosphate carrier, one phosphate into N (Eqs. 15, 16)"
    legs = (
        ("HPO4_P", "P", -1, -2),
        ("HPO4_N", "N", 1, -2),
        ("h_P", "P", -2, 1),
        ("h_N", "N", 2, 1),
    )
    reads_S = ("H2PO4_P", "h_N")
    reads_x = ("HPO4_N", "HPO4_P", "h_N", "h_P")
    printed_eq = "Eq. 16"
    printed_fails = True
    # "subscripts_swapped": the stated co-transport, the IMS proton in the forward term and the
    # matrix proton in the backward term. It balances.
    FORMS = {"balanced": ("kappa", True), "printed": ("two_term", False),
             "subscripts_swapped": ("kappa", True)}
    FORM_READS = {
        "printed": {"A": ("H2PO4_P", "h_N"), "B": ("H2PO4_N", "h_P", "H2PO4_P")},
        "subscripts_swapped": {"A": ("H2PO4_P", "h_P")},
    }

    def form_forward(self, form, B, P, C, s):
        A, _ = self.printed(B, P, C, s)
        if form == "subscripts_swapped":
            return A * s["h_P"] / s["h_N"]
        return A

    def form_slopes_A(self, form, B, P, C, s):
        d = dict(self.slopes_lnA(B, P, C, s))
        if form == "subscripts_swapped":
            d["h_N"] = d["h_N"] - 1
            d["h_P"] = d["h_P"] + 1
        return d

    def literal_terms(self, form, B, P, C, s):
        if form == "subscripts_swapped":
            X = B.n(P["X_PiHt"])
            den = s["H2PO4_P"] + self._k(B, P)
            return X * s["H2PO4_P"] * s["h_P"] / den, X * s["H2PO4_N"] * s["h_N"] / den
        if form == "balanced":
            return self.printed(B, P, C, s)[0], self.backward_closed(B, P, C, s)
        return self.printed(B, P, C, s)

    def dG0_pH7(self, B, P):
        return B.n(0)

    @staticmethod
    def _k(B, P):
        return B.n(P["k_PiHt_mM"]) / 1000

    def printed(self, B, P, C, s):
        X = B.n(P["X_PiHt"])
        den = s["H2PO4_P"] + self._k(B, P)
        return X * s["H2PO4_P"] * s["h_N"] / den, X * s["H2PO4_N"] * s["h_P"] / den

    def dG_appendix(self, B, P, C, s):
        return C["RT"] * B.ln(s["HPO4_N"] * s["h_N"] ** 2 / (s["HPO4_P"] * s["h_P"] ** 2))

    def dG_appendix_H2PO4(self, B, P, C, s):
        return C["RT"] * B.ln(s["H2PO4_N"] * s["h_N"] / (s["H2PO4_P"] * s["h_P"]))

    def S_closed(self, B, P, C, s):
        return B.n(P["X_PiHt"]) * s["H2PO4_P"] * s["h_N"] / (s["H2PO4_P"] + self._k(B, P))

    def backward_closed(self, B, P, C, s):
        """X_PiHt [H2PO4]_N h_N^2/(h_P ([H2PO4]_P + k_PiHt)): binding at equilibrium."""
        return (
            B.n(P["X_PiHt"]) * s["H2PO4_N"] * s["h_N"] ** 2
            / (s["h_P"] * (s["H2PO4_P"] + self._k(B, P)))
        )

    def d_closed(self, B, P, C, s):
        """Eq. 16's mismatch ln(B/A) - x = 2 ln(h_P/h_N)."""
        return 2 * B.ln(s["h_P"] / s["h_N"])

    def slopes_lnA(self, B, P, C, s):
        k = self._k(B, P)
        n = B.n
        return {"H2PO4_P": k / (s["H2PO4_P"] + k), "h_N": n(1), "HPO4_N": n(0),
                "HPO4_P": n(0), "h_P": n(0), "u": n(0)}

    def slopes_lnB(self, B, P, C, s):
        k = self._k(B, P)
        n = B.n
        return {"H2PO4_N": n(1), "h_P": n(1), "H2PO4_P": -s["H2PO4_P"] / (s["H2PO4_P"] + k),
                "h_N": n(0), "HPO4_N": n(0), "HPO4_P": n(0), "u": n(0)}


# ============================================================================================
# Section 5: potassium_proton_exchange@1
# ============================================================================================
class PotassiumProtonExchange(Law):
    key = "k_h_exchange"
    law_id = "potassium_proton_exchange@1"
    section = "5"
    title = "K+/H+ exchange, one K+ into N (Eq. 21)"
    legs = (
        ("K_P", "P", -1, 1),
        ("K_N", "N", 1, 1),
        ("h_N", "N", -1, 1),
        ("h_P", "P", 1, 1),
    )
    reads_S = ("K_N", "K_P", "h_N", "h_P")
    reads_x = ("K_N", "K_P", "h_N", "h_P")
    printed_eq = "Eq. 21"

    def dG0_pH7(self, B, P):
        return B.n(0)

    def printed(self, B, P, C, s):
        X = B.n(P["X_KH"])
        return X * s["K_P"] * s["h_N"], X * s["K_N"] * s["h_P"]

    def dG_appendix(self, B, P, C, s):
        return C["RT"] * B.ln(s["K_N"] * s["h_P"] / (s["K_P"] * s["h_N"]))

    def S_closed(self, B, P, C, s):
        return B.n(P["X_KH"]) * s["K_P"] * s["h_N"]

    def slopes_lnA(self, B, P, C, s):
        n = B.n
        return {"K_P": n(1), "h_N": n(1), "K_N": n(0), "h_P": n(0), "u": n(0)}

    def slopes_lnB(self, B, P, C, s):
        n = B.n
        return {"K_N": n(1), "h_P": n(1), "K_P": n(0), "h_N": n(0), "u": n(0)}


# ============================================================================================
# Section 6: held_reductant_supply@1 (the balanced supply on a held pair, D236)
# ============================================================================================
class HeldReductantSupply(Law):
    key = "nadh_supply"
    law_id = "held_reductant_supply@1"
    section = "6"
    title = "NADH supply on a held neutral reductant pair, per NADH (Eq. 1)"
    legs = (
        ("S_red_N", "N", -1, 0),
        ("NAD_N", "N", -1, -1),
        ("S_ox_N", "N", 1, 0),
        ("NADH_N", "N", 1, -2),
        ("h_N", "N", 1, 1),
    )
    scalar_protons = 1
    reads_S = ("NAD_N", "Pi_N")
    reads_x = ("NAD_N", "NADH_N", "h_N", "S_red_N", "S_ox_N")
    printed_eq = "Eq. 1"
    printed_fails = True
    FORMS = {"balanced": ("kappa", True), "printed": ("two_term", False)}
    FORM_READS = {"printed": {"A": ("NAD_N", "Pi_N"), "B": ("NADH_N", "Pi_N")}}

    def dG0_pH7(self, B, P):
        return B.n(P["dG0_S_pH7"])

    @staticmethod
    def phi(B, P, s):
        k1 = B.n(P["k_Pi1_mM"]) / 1000
        k2 = B.n(P["k_Pi2_mM"]) / 1000
        return (1 + s["Pi_N"] / k1) / (1 + s["Pi_N"] / k2)

    def _phi_slope(self, B, P, s):
        k1 = B.n(P["k_Pi1_mM"]) / 1000
        k2 = B.n(P["k_Pi2_mM"]) / 1000
        Pi = s["Pi_N"]
        return Pi / (k1 + Pi) - Pi / (k2 + Pi)

    @staticmethod
    def h_ref(B, P):
        return B.exp(-B.n(P["pH_ref_supply"]) * B.ln(B.n(10)))

    def printed(self, B, P, C, s):
        Xphi = B.n(P["X_DH"]) * self.phi(B, P, s)
        return Xphi * B.n(P["r"]) * s["NAD_N"], Xphi * s["NADH_N"]

    def dG_appendix(self, B, P, C, s):
        RT = C["RT"]
        return (B.n(P["dG0_S_pH7"])
                + RT * B.ln(s["S_ox_N"] * s["NADH_N"] / (s["S_red_N"] * s["NAD_N"]))
                + RT * B.ln(s["h_N"] / B.n(TEN_M7)))

    def S_closed(self, B, P, C, s):
        return B.n(P["X_DH"]) * self.phi(B, P, s) * B.n(P["r"]) * s["NAD_N"]

    def backward_closed(self, B, P, C, s):
        """X_DH phi [NADH] h_N/10^-7.10: at the declared held ratio."""
        return B.n(P["X_DH"]) * self.phi(B, P, s) * s["NADH_N"] * s["h_N"] / self.h_ref(B, P)

    def d_closed(self, B, P, C, s):
        """Eq. 1's mismatch in frame B at the declared held ratio: -ln(h_N/10^-7.10)."""
        return -B.ln(s["h_N"] / self.h_ref(B, P))

    def literal_terms(self, form, B, P, C, s):
        if form == "balanced":
            return self.printed(B, P, C, s)[0], self.backward_closed(B, P, C, s)
        return self.printed(B, P, C, s)

    def slopes_lnA(self, B, P, C, s):
        z = B.n(0)
        return {"NAD_N": B.n(1), "Pi_N": self._phi_slope(B, P, s), "NADH_N": z, "h_N": z,
                "S_red_N": z, "S_ox_N": z, "u": z}

    def slopes_lnB(self, B, P, C, s):
        z = B.n(0)
        return {"NADH_N": B.n(1), "Pi_N": self._phi_slope(B, P, s), "NAD_N": z, "h_N": z,
                "S_red_N": z, "S_ox_N": z, "u": z}


# ============================================================================================
# Section 7: adenylate kinase in the IMS (Eqs. 17, 18), in base forms with the source's rate
# ============================================================================================
class AdenylateKinase(Law):
    key = "adenylate_kinase"
    law_id = "adenylate_kinase (section 7)"
    section = "7"
    title = "Adenylate kinase in the IMS, per 2 ADP (Eqs. 17, 18)"
    legs = (("ADP3_P", "P", -2, -3), ("ATP4_P", "P", 1, -4), ("AMP_P", "P", 1, -2))
    reads_S = ("ADP3_P", "Mg_P")
    reads_x = ("ATP4_P", "ADP3_P", "AMP_P")
    printed_eq = "Eq. 18"
    printed_fails = True
    FORMS = {"balanced": ("kappa", True), "printed": ("two_term", False)}
    FORM_READS = {"printed": {"A": ("ADPtot_P",), "B": ("AMP_P", "ATPtot_P")}}

    def dG0_pH7(self, B, P):
        raise ValueError("adenylate kinase has no pH-7 basis")

    def dG0_1M(self, B, P, C):
        _m, K_base = hp.ak_match(B, P)
        return -C["RT"] * B.ln(K_base)

    def _pref(self, B, P, s):
        """The source's rate: the ratio of total to Mg-free ATP at the IMS's free Mg2+."""
        return 1 + s["Mg_P"] / B.n(P["K_MgATP"])

    def printed(self, B, P, C, s):
        """Eq. 18 on totals: X_AK (K_AK [ADP]^2 - [AMP][ATP])."""
        X = B.n(P["X_AK"])
        return X * B.n(P["K_AK"]) * s["ADPtot_P"] ** 2, X * s["AMP_P"] * s["ATPtot_P"]

    def form_forward(self, form, B, P, C, s):
        if form == "balanced":
            _m, K_base = hp.ak_match(B, P)
            return B.n(P["X_AK"]) * self._pref(B, P, s) * K_base * s["ADP3_P"] ** 2
        return self.printed(B, P, C, s)[0]

    def form_slopes_A(self, form, B, P, C, s):
        if form == "balanced":
            z = B.n(0)
            Mg, K = s["Mg_P"], B.n(P["K_MgATP"])
            return {"ADP3_P": B.n(2), "Mg_P": Mg / (Mg + K), "ATP4_P": z, "AMP_P": z, "u": z}
        return self.slopes_lnA(B, P, C, s)

    def literal_terms(self, form, B, P, C, s):
        if form == "balanced":
            _m, K_base = hp.ak_match(B, P)
            Xp = B.n(P["X_AK"]) * self._pref(B, P, s)
            return Xp * K_base * s["ADP3_P"] ** 2, Xp * s["AMP_P"] * s["ATP4_P"]
        return self.printed(B, P, C, s)

    def dG_appendix(self, B, P, C, s):
        _m, K_base = hp.ak_match(B, P)
        RT = C["RT"]
        return -RT * B.ln(K_base) + RT * B.ln(s["ATP4_P"] * s["AMP_P"] / s["ADP3_P"] ** 2)

    def S_closed(self, B, P, C, s):
        return self.form_forward("balanced", B, P, C, s)

    def d_closed(self, B, P, C, s):
        """Eq. 18's mismatch in frame B: ln[(1 + m/K_MgATP)/(1 + m/K_MgADP)^2] + ln(K_base/K_AK),
        with m the IMS's free Mg2+; zero at the matched m."""
        _m, K_base = hp.ak_match(B, P)
        Mg = s["Mg_P"]
        return (B.ln((1 + Mg / B.n(P["K_MgATP"])) / (1 + Mg / B.n(P["K_MgADP"])) ** 2)
                + B.ln(K_base / B.n(P["K_AK"])))

    def K_tot(self, B, P, Mg):
        """The same law on totals: K_tot = K_base (1 + m/K_MgATP)/(1 + m/K_MgADP)^2."""
        _m, K_base = hp.ak_match(B, P)
        return K_base * (1 + Mg / B.n(P["K_MgATP"])) / (1 + Mg / B.n(P["K_MgADP"])) ** 2

    def slopes_lnA(self, B, P, C, s):
        z = B.n(0)
        return {"ADPtot_P": B.n(2), "ATP4_P": z, "ADP3_P": z, "AMP_P": z, "Mg_P": z, "u": z}

    def slopes_lnB(self, B, P, C, s):
        z = B.n(0)
        return {"AMP_P": B.n(1), "ATPtot_P": B.n(1), "ATP4_P": z, "ADP3_P": z, "Mg_P": z, "u": z}


# ============================================================================================
# Section 8: the outer membrane, a Fick flux for each form (the lead's design)
# ============================================================================================
class OuterMembrane:
    """J_f = gamma p_class ([f]_e - [f]_P) for each form; one permeability per class. The
    references read no potential across the outer membrane: dG_f = RT ln([f]_P/[f]_e) (a reading
    of the tag, accepted by the lead). In the declared form, S_f = gamma p [f]_e and
    x_f = ln([f]_P/[f]_e). Sides: E (the external buffer) and P (the IMS)."""

    key = "outer_membrane"
    law_id = "outer_membrane (section 8)"
    section = "8"
    title = "The outer membrane, a Fick flux per form (Eq. 13)"
    printed_eq = "Eq. 13"
    has_flux = True
    column = "with"
    OM_FORMS = (("ATP4", "A", -4), ("MgATP", "A", -2), ("ADP3", "A", -3), ("MgADP", "A", -1),
                ("AMP", "A", -2), ("HPO4", "Pi", -2), ("H2PO4", "Pi", -1))
    CLASS_TOTALS = {"ATP": (("ATP4", "MgATP"), "ATPtot"), "ADP": (("ADP3", "MgADP"), "ADPtot"),
                    "AMP": (("AMP",), "AMP"), "Pi": (("HPO4", "H2PO4"), "Pi")}
    LIGANDS = {"Mg": ("MgATP", "MgADP"), "H": ("H2PO4",)}
    FORMS = {"declared": ("kappa", True)}

    def form_kind(self, form):
        return "kappa"

    def k(self, B, P, cls):
        p = P["p_A_um_per_s"] if cls == "A" else P["p_Pi_um_per_s"]
        return B.n(P["gamma_per_um"]) * B.n(p)

    def legs_of(self, f):
        z = dict((ff, zz) for ff, _c, zz in self.OM_FORMS)[f]
        return ((f"{f}_E", "E", -1, z), (f"{f}_P", "P", 1, z))

    def form_terms(self, B, P, C, s, f, cls):
        k = self.k(B, P, cls)
        return k * s[f"{f}_E"], k * s[f"{f}_P"]

    def evaluate(self, B, P, C, s, form="declared"):
        RT = C["RT"]
        out = {k: {} for k in ("J", "S", "J_minus", "x", "dG_J_per_mol", "dissipation_W_per_L")}
        out["slopes_J"] = {}
        for f, cls, _z in self.OM_FORMS:
            S, Jm = self.form_terms(B, P, C, s, f, cls)
            x = B.ln(s[f"{f}_P"] / s[f"{f}_E"])
            J = S - Jm
            out["J"][f] = J
            out["S"][f] = S
            out["J_minus"][f] = Jm
            out["x"][f] = x
            out["dG_J_per_mol"][f] = RT * x
            out["dissipation_W_per_L"][f] = -J * RT * x
            out["slopes_J"][f"{f}_E"] = S
            out["slopes_J"][f"{f}_P"] = -Jm
        out["class_J"] = {c: _sum(out["J"][f] for f in forms)
                          for c, (forms, _tot) in self.CLASS_TOTALS.items()}
        out["eq13_J"] = {}
        for c, (_forms, tot) in self.CLASS_TOTALS.items():
            cls = "Pi" if c == "Pi" else "A"
            out["eq13_J"][c] = self.k(B, P, cls) * (s[f"{tot}_E"] - s[f"{tot}_P"])
        out["ligand_J"] = {L: _sum(out["J"][f] for f in forms) for L, forms in self.LIGANDS.items()}
        out["dissipation_total_W_per_L"] = _sum(out["dissipation_W_per_L"].values())
        return out


CYCLE_LAWS = (
    ComplexI(),
    ComplexIIIEq7(),
    ComplexIIIEq24(),
    ComplexIV(),
    LumpedQuinolOxygen(),
    ATPSynthase(),
    NucleotideExchange(),
    PhosphateCarrier(),
    PotassiumProtonExchange(),
    HeldReductantSupply(),
    AdenylateKinase(),
)
OUTER = OuterMembrane()
LAWS_BY_KEY = {law.key: law for law in CYCLE_LAWS}
LAWS_BY_KEY[OUTER.key] = OUTER


# ============================================================================================
# Evaluation of a declared, balanced or printed form
# ============================================================================================
def kappa_parts(B, n, x):
    """E_j = e^{j x/n}, Z = sum E_j, w = d ln Z/dx and dw/dx (the variance of j/n)."""
    E = [B.exp(B.n(j) * x / B.n(n)) for j in range(n)]
    Z = _sum(E)
    m1 = _sum(B.n(j) / B.n(n) * E[j] for j in range(n)) / Z
    m2 = _sum((B.n(j) / B.n(n)) ** 2 * E[j] for j in range(n)) / Z
    return E, Z, m1, m2 - m1 * m1


def evaluate(law, B, P, C, s, form="declared"):
    """All compared quantities of ``law`` at state ``s`` in ``form``.

    ``form`` is "declared" (the law passes as printed; declared = printed), "balanced" (the
    declared replacement of a failing printed equation, keeping its forward term), "printed"
    (the failing equation as printed) or one of a failing law's alternative repairs in its
    ``FORMS``. Slopes are d ln(.)/d ln(input) for concentrations and h, and d/du for u.
    """
    out = {}
    xt = law.x_terms(B, P, C, s)
    x = _sum(v for _k, v in xt)
    RT, F = C["RT"], C["F"]
    q = law.q(P)
    FRT = C["F_RT_per_mV"]
    out["x"] = x
    out["dG_J_per_mol"] = RT * x
    out["affinity_J_per_mol"] = -RT * x
    if q != 0:
        out["static_head_mV"] = s["dpsi_mV"] - x / (B.n(q) * FRT)
    if not law.has_flux:
        return out
    n = law.kappa_inv
    nu = law.nu(P)
    sA = law.form_slopes_A(form, B, P, C, s)
    reads = list(law.reads()) + ["u"]
    if law.form_kind(form) == "two_term":
        A, Bp = law.form_terms(form, B, P, C, s)
        sB = law.form_slopes_B(form, B, P, C, s)
        J = A - Bp
        # The printed terms may read forms outside "Reads" (Eq. 11's MgATP, Eq. 16's H2PO4 at N).
        reads_pr = reads + [k for k in list(sA) + list(sB) if k not in reads]
        out.update(S=A, J_minus=Bp, J=J, A_term=A, B_term=Bp)
        out["lnB_over_A"] = B.ln(Bp / A)
        out["slopes_lnA"] = {v: sA.get(v, B.n(0)) for v in reads_pr}
        out["slopes_lnB"] = {v: sB.get(v, B.n(0)) for v in reads_pr}
        dJ = {v: A * sA.get(v, B.n(0)) - Bp * sB.get(v, B.n(0)) for v in reads_pr}
    else:
        A = law.form_forward(form, B, P, C, s)
        E, Z, w, _dw = kappa_parts(B, n, x)
        S = A / Z
        Jm = S * B.exp(x)
        J = -S * B.expm1(x)
        out.update(S=S, J_minus=Jm, J=J, A_term=A, B_term=A * E[1] if n > 1 else Jm)
        nu_u = {**nu, "u": q}
        sS = {v: sA.get(v, B.n(0)) - w * B.n(nu_u.get(v, 0)) for v in reads}
        out["slopes_lnS"] = sS
        dJ = {v: J * sS[v] - Jm * B.n(nu_u.get(v, 0)) for v in reads}
    out["slopes_J"] = dJ
    out["I_A_per_L"] = B.n(q) * F * J
    out["dissipation_W_per_L"] = -J * RT * x
    out["dI_ddpsi_A_per_L_per_mV"] = B.n(q) * F * dJ["u"] * FRT
    return out
