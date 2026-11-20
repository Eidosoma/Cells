"""Plants: candidate kernels with one deliberate error each, which the rows must catch.

Each plant is a subclass of a reference law, or a reference law run with one parameter or one
constant changed. The reference classes carry no plant switches. ``Plant.values`` returns the
plant's quantities at a state, in the keys of the reference form it is measured against.

Section 8 names two planted controls: complex I with -4u in place of +4u (C1_q_reversed), and
exchange shares that do not sum to one (ANT_shares_0.35_0.60). The rest are proposed here.
"""
from __future__ import annotations

from . import hp, laws
from .hp import DEC


def _u(C, s):
    return C["F_RT_per_mV"] * s["dpsi_mV"]


class Plant:
    def __init__(self, pid, law_key, description, kind, make, named=False, forms=None):
        self.pid = pid
        self.forms = forms  # the reference forms it is measured against (None: all)
        self.law_key = law_key
        self.description = description
        self.kind = kind
        self._make = make  # ref_form -> (law object, P, C, form)
        self.named = named

    def values(self, s, ref_form):
        law_obj, P, C, form = self._make(ref_form)
        if law_obj.key == "nadh_supply":
            return law_obj.evaluate(DEC, P, C, s)
        v = laws.evaluate(law_obj, DEC, P, C, s, form)
        if form == "printed" and ref_form != "printed":
            # A printed-structure kernel's forward term is its S, its backward term its J-.
            v["slopes_lnS"] = v.pop("slopes_lnA")
            v.pop("slopes_lnB", None)
            v.pop("lnB_over_A", None)
        return v


def _P(law, **changes):
    p = hp.parameters(law.column)
    p.update(changes)
    return p


def _same_form(law, P=None, C=None, form_map=None):
    def make(ref_form):
        form = ref_form if form_map is None else form_map[ref_form]
        return law, (P if P is not None else hp.parameters(law.column)), (
            C if C is not None else hp.constants(DEC)), form
    return make


def _const_plant(law, **const_kw):
    def make(ref_form):
        return law, hp.parameters(law.column), hp.constants(DEC, **const_kw), ref_form
    return make


# --- Section 1.1 ------------------------------------------------------------------------------
class C1QReversed(laws.ComplexI):
    """Section 8's planted control: complex I with -4u in place of +4u (q = -4)."""

    def q(self, P):
        return -4

    def printed(self, B, P, C, s):
        A, Bp = super().printed(B, P, C, s)
        return A * B.exp(8 * _u(C, s)), Bp

    def slopes_lnA(self, B, P, C, s):
        d = super().slopes_lnA(B, P, C, s)
        d["u"] = B.n(4)
        return d


class C1ScalarProtonDropped(laws.ComplexI):
    """The kind of slip Eq. 24 makes, put into complex I: dG without -RT ln(h_N/1e-7)."""

    def x_terms(self, B, P, C, s):
        return super().x_terms(B, P, C, s) + [("slip", B.ln(s["h_N"] / B.n(laws.TEN_M7)))]


def _rounded_dG0(base_cls, value):
    class Rounded(base_cls):
        def dG0_1M(self, B, P, C):
            return B.n(value)
    Rounded.__name__ = base_cls.__name__ + "RoundedDG0"
    return Rounded()


# --- Section 1.2 ------------------------------------------------------------------------------
class C3KappaOne(laws.ComplexIIIEq24):
    kappa_inv = 1


class C3PhiInverted(laws.ComplexIIIEq24):
    @staticmethod
    def phi(B, P, s):
        k3 = B.n(P["k_Pi3_mM"]) / 1000
        k4 = B.n(P["k_Pi4_mM"]) / 1000
        return (1 + s["Pi_N"] / k4) / (1 + s["Pi_N"] / k3)

    def _phi_slope(self, B, P, s):
        return -super()._phi_slope(B, P, s)


# --- Section 1.3 ------------------------------------------------------------------------------
class C4PerHalfO2(laws.ComplexIV):
    """The printed per-electron-pair flux J_C4 used as the per-O2 flux (not halved)."""

    def printed(self, B, P, C, s):
        return self.printed_per_two_electrons(B, P, C, s)


class C4KappaHalf(laws.ComplexIV):
    kappa_inv = 2


class C4CtotParameter(laws.ComplexIV):
    """c_tot taken as Table 1's cytC_tot instead of the clamped [c3+] + [c2+]."""

    def printed(self, B, P, C, s):
        ct = B.n(P["cytC_tot_mM"]) / 1000
        A9, B9 = self.printed_per_two_electrons(B, P, C, s, ctot=ct)
        return A9 / 2, B9 / 2

    def slopes_lnA(self, B, P, C, s):
        d = super().slopes_lnA(B, P, C, s)
        d["c2_P"] = B.n(2)
        d["c3_P"] = B.n(0)
        return d


# --- Section 2 --------------------------------------------------------------------------------
class F1QReversed(laws.ATPSynthase):
    """q = +n_A in place of -n_A."""

    def q(self, P):
        return int(P["n_A"])

    def printed(self, B, P, C, s):
        A, Bp = super().printed(B, P, C, s)
        nA = B.n(int(P["n_A"]))
        return A * B.exp(-2 * nA * _u(C, s)), Bp

    def slopes_lnA(self, B, P, C, s):
        d = super().slopes_lnA(B, P, C, s)
        d["u"] = -d["u"]
        return d


class F1TotalsInX(laws.ATPSynthase):
    """dG built from total ATP and ADP instead of the Mg-free forms."""

    def legs_(self, P):
        nA = int(P["n_A"])
        return (("ADPtot_N", "N", -1, -3), ("HPO4_N", "N", -1, -2), ("ATPtot_N", "N", 1, -4),
                (None, "N", 1, 0), ("h_N", "N", nA - 1, 1), ("h_P", "P", -nA, 1))


class F1TotalPiInX(laws.ATPSynthase):
    """dG built from total Pi instead of HPO4(2-), with the declared dG0_F."""

    def legs_(self, P):
        nA = int(P["n_A"])
        return (("ADP3_N", "N", -1, -3), ("Pi_N", "N", -1, -2), ("ATP4_N", "N", 1, -4),
                (None, "N", 1, 0), ("h_N", "N", nA - 1, 1), ("h_P", "P", -nA, 1))


# --- Section 3 --------------------------------------------------------------------------------
class ANTTotals(laws.NucleotideExchange):
    """Eq. 14 and its dG with total ATP and ADP instead of the Mg-free forms."""

    legs = (("ATPtot_N", "N", -1, -4), ("ATPtot_P", "P", 1, -4), ("ADPtot_P", "P", -1, -3),
            ("ADPtot_N", "N", 1, -3))

    def _abcd(self, B, P, C, s):
        t = dict(s)
        for side in ("N", "P"):
            t[f"ATP4_{side}"] = s[f"ATPtot_{side}"]
            t[f"ADP3_{side}"] = s[f"ADPtot_{side}"]
        return super()._abcd(B, P, C, t)

    def slopes_lnA(self, B, P, C, s):
        a, b, c, d, _g = self._abcd(B, P, C, s)
        km = B.n(P["k_mADP"])
        tP, tN = B.n(P["theta_P"]), B.n(P["theta_N"])
        z = B.n(0)
        return {"ADP3_P": z, "ATP4_P": z, "ADP3_N": z, "ATP4_N": z,
                "u": tN * c / (c + d) + tP * b / (a + b)}


# --- Section 4 --------------------------------------------------------------------------------
class PiHtOneProton(laws.PhosphateCarrier):
    """One proton with HPO4(2-) in dG; the kernel keeps the declared q = 0."""

    legs = (("HPO4_P", "P", -1, -2), ("HPO4_N", "N", 1, -2), ("h_P", "P", -1, 1),
            ("h_N", "N", 1, 1))

    def q(self, P):
        return 0


# --- Section 5 --------------------------------------------------------------------------------
class KHProtonSidesSwapped(laws.PotassiumProtonExchange):
    """H+ read on the wrong sides in S and dG; the kernel keeps the declared q = 0."""

    legs = (("K_P", "P", -1, 1), ("K_N", "N", 1, 1), ("h_N", "N", 1, 1), ("h_P", "P", -1, 1))

    def q(self, P):
        return 0

    def printed(self, B, P, C, s):
        X = B.n(P["X_KH"])
        return X * s["K_P"] * s["h_P"], X * s["K_N"] * s["h_N"]

    def slopes_lnA(self, B, P, C, s):
        n = B.n
        return {"K_P": n(1), "h_P": n(1), "K_N": n(0), "h_N": n(0), "u": n(0)}


# --- Section 6 --------------------------------------------------------------------------------
class DHPhiInverted(laws.NADHSupply):
    @staticmethod
    def phi(B, P, s):
        k1 = B.n(P["k_Pi1_mM"]) / 1000
        k2 = B.n(P["k_Pi2_mM"]) / 1000
        return (1 + s["Pi_N"] / k2) / (1 + s["Pi_N"] / k1)

    def evaluate(self, B, P, C, s):
        v = super().evaluate(B, P, C, s)
        k1 = B.n(P["k_Pi1_mM"]) / 1000
        k2 = B.n(P["k_Pi2_mM"]) / 1000
        Pi = s["Pi_N"]
        v["slopes_J"]["Pi_N"] = v["J"] * (Pi / (k2 + Pi) - Pi / (k1 + Pi))
        return v


class DHROnNADH(laws.NADHSupply):
    def evaluate(self, B, P, C, s):
        X = B.n(P["X_DH"])
        phi = self.phi(B, P, s)
        r = B.n(P["r"])
        Jp = X * phi * s["NAD_N"]
        Jm = X * phi * r * s["NADH_N"]
        J = Jp - Jm
        k1 = B.n(P["k_Pi1_mM"]) / 1000
        k2 = B.n(P["k_Pi2_mM"]) / 1000
        Pi = s["Pi_N"]
        return {"J": J, "J_plus": Jp, "J_minus": Jm,
                "dG_conc_J_per_mol": C["RT"] * B.ln(s["NADH_N"] * s["h_N"] / s["NAD_N"]),
                "slopes_J": {"NAD_N": Jp, "NADH_N": -Jm,
                             "Pi_N": J * (Pi / (k1 + Pi) - Pi / (k2 + Pi))}}


# --- Activities in mM (every law) ---------------------------------------------------------------
def _mM_activity(base_cls):
    class MM(base_cls):
        def x_terms(self, B, P, C, s):
            t = super().x_terms(B, P, C, s)
            shift = sum(nu for k, _sd, nu, _z in self.legs_(P) if k is not None)
            return t + [("mM", B.n(shift) * B.ln(B.n(1000)))]
    MM.__name__ = base_cls.__name__ + "MilliMolarActivity"
    return MM()


# --- The list ------------------------------------------------------------------------------------
def _other_form(law):
    return _same_form(law, form_map={"balanced": "printed", "printed": "balanced"})


L = laws.LAWS_BY_KEY
PLANTS = []


def _add(pid, law_key, desc, kind, make, named=False, forms=None):
    PLANTS.append(Plant(pid, law_key, desc, kind, make, named, forms))


_add("C1_q_reversed", "complex_I", "Section 8: complex I with -4u in place of +4u (q = -4)",
     "thermodynamic", _same_form(C1QReversed()), named=True)
_add("C1_scalar_proton_dropped", "complex_I",
     "complex I's dG without its scalar proton term -RT ln(h_N/1e-7)", "thermodynamic",
     _same_form(C1ScalarProtonDropped()))
_add("C1_dG0_display", "complex_I", "dG0 at 1 M as section 7 displays it, -110.934 kJ/mol",
     "free-energy entry", _same_form(_rounded_dG0(laws.ComplexI, "-110934")))
_add("C3_eq7_dG0_display", "complex_III_eq7",
     "dG0 at 1 M as section 7 displays it, +50.599 kJ/mol", "free-energy entry",
     _same_form(_rounded_dG0(laws.ComplexIIIEq7, "50599")))
_add("C3_eq24_other_form", "complex_III_eq24",
     "Eq. 24 printed judged against balanced, or balanced against printed", "printed vs balanced",
     _other_form(L["complex_III_eq24"]))
_add("C3_eq24_dG0_display", "complex_III_eq24",
     "dG0 at 1 M as section 7 displays it, +50.599 kJ/mol", "free-energy entry",
     _same_form(_rounded_dG0(laws.ComplexIIIEq24, "50599")))
_add("C3_eq24_kappa_one", "complex_III_eq24", "J = A (1 - e^x) in place of A (1 - e^{x/2})",
     "kinetic", _same_form(C3KappaOne()), forms=("balanced",))
_add("C3_eq24_phi_inverted", "complex_III_eq24",
     "phosphate control inverted: (1 + Pi/k_Pi4)/(1 + Pi/k_Pi3)", "kinetic",
     _same_form(C3PhiInverted()))
_add("C4_dG0_display", "complex_IV", "dG0 at 1 M as section 7 displays it, -412.137 kJ/mol",
     "free-energy entry", _same_form(_rounded_dG0(laws.ComplexIV, "-412137")))
_add("C4_per_half_O2", "complex_IV", "the per-electron-pair J_C4 used as the per-O2 flux",
     "stoichiometry", _same_form(C4PerHalfO2()))
_add("C4_kappa_half", "complex_IV", "kappa = 1/2 per O2 in place of 1/4", "kinetic",
     _same_form(C4KappaHalf()))
_add("C4_ctot_parameter", "complex_IV",
     "c_tot = Table 1's cytC_tot in place of the clamped [c3+] + [c2+]", "kinetic",
     _same_form(C4CtotParameter()))
_add("F1_other_form", "atp_synthase",
     "Eq. 11 printed judged against balanced, or balanced against printed", "printed vs balanced",
     _other_form(L["atp_synthase"]))
_add("F1_dG0_display", "atp_synthase", "dG0_F at 1 M as section 2 displays it, -6.685 kJ/mol",
     "free-energy entry", _same_form(_rounded_dG0(laws.ATPSynthase, "-6685")))
_add("F1_dG0_ATP_text_sign", "atp_synthase",
     "dG0_ATP = -36.03 kJ/mol, the text's sign under Eq. 11, in place of Table 2's +36.03",
     "free-energy entry",
     _same_form(L["atp_synthase"], P=_P(L["atp_synthase"], dG0_ATP_pH7="-36030")))
_add("F1_q_reversed", "atp_synthase", "q = +n_A in place of -n_A", "thermodynamic",
     _same_form(F1QReversed()))
_add("F1_totals_in_dG", "atp_synthase", "dG from total ATP and ADP, not the Mg-free forms",
     "binding", _same_form(F1TotalsInX()))
_add("F1_total_Pi_in_dG", "atp_synthase", "dG from total Pi, not HPO4(2-)", "binding",
     _same_form(F1TotalPiInX()))
_add("ANT_shares_0.35_0.60", "nucleotide_exchange",
     "Section 8: exchange shares that do not sum to one (theta_P 0.35, theta_N 0.60)",
     "thermodynamic",
     _same_form(L["nucleotide_exchange"], P=_P(L["nucleotide_exchange"], theta_N="0.60"),
                form_map={"declared": "printed"}), named=True)
_add("ANT_shares_swapped", "nucleotide_exchange",
     "shares swapped, theta_P 0.65 and theta_N 0.35 (they still sum to one)", "kinetic",
     _same_form(L["nucleotide_exchange"],
                P=_P(L["nucleotide_exchange"], theta_P="0.65", theta_N="0.35"),
                form_map={"declared": "printed"}))
_add("ANT_totals", "nucleotide_exchange", "total ATP and ADP in place of the Mg-free forms",
     "binding", _same_form(ANTTotals()))
_add("PiHt_other_form", "phosphate_carrier",
     "Eq. 16 printed judged against balanced, or balanced against printed", "printed vs balanced",
     _other_form(L["phosphate_carrier"]))
_add("PiHt_k_in_M", "phosphate_carrier", "k_PiHt read in M (0.45082 M), not mM", "unit",
     _same_form(L["phosphate_carrier"], P=_P(L["phosphate_carrier"], k_PiHt_mM="450.82")))
_add("PiHt_one_proton", "phosphate_carrier", "one proton in place of two with HPO4(2-)",
     "stoichiometry", _same_form(PiHtOneProton()))
_add("KH_proton_sides_swapped", "k_h_exchange", "H+ sides swapped in S and in dG",
     "stoichiometry", _same_form(KHProtonSidesSwapped()))
_add("DH_phi_inverted", "nadh_supply", "Eq. 1's phosphate factor inverted", "kinetic",
     _same_form(DHPhiInverted()))
_add("DH_r_on_NADH", "nadh_supply", "r applied to NADH in place of NAD", "kinetic",
     _same_form(DHROnNADH()))

for _law in laws.CYCLE_LAWS:
    if not _law.has_flux and _law.key != "lumped_QO":
        continue
    _add(f"RT_display/{_law.key}", _law.key, "RT = 2578.7306 J/mol, section 0's display",
         "constant", _const_plant(_law, overrides={"RT": "2578.7306"}))
    if _law.q(hp.parameters(_law.column)) != 0:
        _add(f"FRT_display/{_law.key}", _law.key, "F/RT = 0.0374158 per mV, section 0's display",
             "constant", _const_plant(_law, overrides={"F_RT_per_mV": "0.0374158"}))
    _add(f"T_298/{_law.key}", _law.key, "T = 298.15 K in place of 310.15 K", "constant",
         _const_plant(_law, T="298.15"))
    # A law whose counts sum to zero is invariant to the activity unit: no power, not listed.
    if sum(nu for k, _sd, nu, _z in _law.legs_(hp.parameters(_law.column)) if k is not None):
        _add(f"activity_mM/{_law.key}", _law.key, "activities as c/(1 mM) in dG", "unit",
             _same_form(_mM_activity(type(_law))))

PLANTS_BY_ID = {p.pid: p for p in PLANTS}
