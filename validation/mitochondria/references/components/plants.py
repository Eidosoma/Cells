"""Plants: candidate kernels with one deliberate error each, which the rows must catch.

Each plant is a subclass of a reference law, or a reference law run with one parameter or one
constant changed. The reference classes carry no plant switches. ``Plant.values`` returns the
plant's quantities at a state, in the keys of the reference form it is measured against.

Section 10 names two planted controls: complex I with -4u in place of +4u (C1_q_reversed), and
exchange shares that do not sum to one (ANT_shares_0.35_0.60). The rest are proposed here.
"""
from __future__ import annotations

from . import hp, laws
from .hp import DEC


def _u(C, s):
    return C["F_RT_per_mV"] * s["dpsi_mV"]


class Plant:
    def __init__(self, pid, law_key, description, kind, make, named=False, forms=None,
                 cross_form=False):
        self.pid = pid
        self.law_key = law_key
        self.description = description
        self.kind = kind
        self._make = make  # ref_form -> (law object, P, C, form)
        self.named = named
        self.forms = forms  # the reference forms it is measured against (None: all)
        self.cross_form = cross_form  # a law's other form, run as the kernel under test

    def exclude_for(self, ref_form):
        """Quantity families not compared at ``ref_form``'s rows. With kappa = 1/2, a two-term
        form's S and J- (its own two terms) and a kappa form's S and J- (the declared one-way
        fluxes) are different quantities, so they are not compared across the two kinds."""
        if not self.cross_form:
            return ()
        law = laws.LAWS_BY_KEY[self.law_key]
        cand = self._make(ref_form)[3]
        if law.kappa_inv != 1 and law.form_kind(cand) != law.form_kind(ref_form):
            return ("S", "J_minus", "slopes_lnS")
        return ()

    def values(self, s, ref_form):
        law_obj, P, C, form = self._make(ref_form)
        if law_obj.key == "outer_membrane":
            return law_obj.evaluate(DEC, P, C, s)
        v = laws.evaluate(law_obj, DEC, P, C, s, form)
        ref_law = laws.LAWS_BY_KEY[self.law_key]
        ref_kind = "two_term" if ref_form == "printed" else ref_law.form_kind(ref_form)
        if law_obj.form_kind(form) == "two_term" and ref_kind == "kappa":
            # A two-term kernel's forward term is its S, its backward term its J-.
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
    """Section 10's planted control: complex I with -4u in place of +4u (q = -4)."""

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
class SupplyHeldRatioR(laws.HeldReductantSupply):
    """Section 6's planted control: a world holding S_red/S_ox = r, without 10^-0.10. Its x is
    smaller by 0.10 ln 10 at every state."""

    def x_terms(self, B, P, C, s):
        t = dict(s)
        t["S_red_N"] = B.n(P["r"]) * s["S_ox_N"]
        return super().x_terms(B, P, C, t)


class SupplyUpkeepRatioOnly(laws.HeldReductantSupply):
    """The upkeep's work booked from the pair's ratio alone, without its standard potentials
    (only the ratio enters the flux, but the work needs the potentials)."""

    def upkeep_y(self, B, P, C, s):
        return B.ln(s["S_ox_N"] / s["S_red_N"])


class SupplyPhiInverted(laws.HeldReductantSupply):
    @staticmethod
    def phi(B, P, s):
        k1 = B.n(P["k_Pi1_mM"]) / 1000
        k2 = B.n(P["k_Pi2_mM"]) / 1000
        return (1 + s["Pi_N"] / k2) / (1 + s["Pi_N"] / k1)

    def _phi_slope(self, B, P, s):
        return -super()._phi_slope(B, P, s)


# --- Section 7 --------------------------------------------------------------------------------
class AKNoPrefactor(laws.AdenylateKinase):
    """Section 7's planted control: the form without the prefactor (1 + [Mg2+]_P/K_MgATP). The
    equilibrium is right; the rate is too small by that factor."""

    def _pref(self, B, P, s):
        return B.n(1)

    def form_slopes_A(self, form, B, P, C, s):
        d = super().form_slopes_A(form, B, P, C, s)
        if form == "balanced":
            d["Mg_P"] = B.n(0)
        return d


class AKPrefactorADP(laws.AdenylateKinase):
    """The prefactor with K_MgADP in place of K_MgATP."""

    def _pref(self, B, P, s):
        return 1 + s["Mg_P"] / B.n(P["K_MgADP"])

    def form_slopes_A(self, form, B, P, C, s):
        d = super().form_slopes_A(form, B, P, C, s)
        if form == "balanced":
            Mg, K = s["Mg_P"], B.n(P["K_MgADP"])
            d["Mg_P"] = Mg / (Mg + K)
        return d


# --- Section 8 --------------------------------------------------------------------------------
def _om_resum(om, out):
    out["class_J"] = {c: sum((out["J"][f] for f in forms), DEC.n(0))
                      for c, (forms, _tot) in om.CLASS_TOTALS.items()}
    out["ligand_J"] = {L_: sum((out["J"][f] for f in forms), DEC.n(0))
                       for L_, forms in om.LIGANDS.items()}
    out["dissipation_total_W_per_L"] = sum(out["dissipation_W_per_L"].values(), DEC.n(0))
    return out


def _om_drop_form_values(out, f, keep_x=False):
    """Drop what a plant does not compute for form f. With keep_x, the form's x and dG (set by
    the state) stay, and its dissipation is rebooked from the plant's own flux."""
    for q in ("S", "J_minus") + (() if keep_x else ("x", "dG_J_per_mol", "dissipation_W_per_L")):
        out[q].pop(f, None)
    out["slopes_J"].pop(f"{f}_E", None)
    out["slopes_J"].pop(f"{f}_P", None)


def _om_rebook_dissipation(out, f):
    out["dissipation_W_per_L"][f] = -out["J"][f] * out["dG_J_per_mol"][f]


class OMTotalAsBaseForm(laws.OuterMembrane):
    """The class total crossing in place of the forms (Eq. 13 on totals), booked as the base
    form: the bound forms move nothing, so no Mg2+ or H+ is carried."""

    BASE_OF = {"ATP4": "ATPtot", "ADP3": "ADPtot", "AMP": "AMP", "HPO4": "Pi"}

    def evaluate(self, B, P, C, s, form="declared"):
        out = super().evaluate(B, P, C, s, form)
        RT = C["RT"]
        for f, cls, _z in self.OM_FORMS:
            if f in self.BASE_OF:
                tot = self.BASE_OF[f]
                k = self.k(B, P, cls)
                S, Jm = k * s[f"{tot}_E"], k * s[f"{tot}_P"]
                x = B.ln(s[f"{tot}_P"] / s[f"{tot}_E"])
                out["J"][f], out["S"][f], out["J_minus"][f], out["x"][f] = S - Jm, S, Jm, x
                out["dG_J_per_mol"][f] = RT * x
                out["dissipation_W_per_L"][f] = -(S - Jm) * RT * x
                out["slopes_J"][f"{f}_E"] = B.n(0)  # it reads the totals, not the forms
                out["slopes_J"][f"{f}_P"] = B.n(0)
            else:
                _om_drop_form_values(out, f, keep_x=True)
                out["J"][f] = B.n(0)
                _om_rebook_dissipation(out, f)
        return _om_resum(self, out)


class OMTotalSplitUpstream(laws.OuterMembrane):
    """The class total crossing in place of the forms, split among them by the upstream side's
    fractions. Equal to the per-form fluxes only where both sides' fractions agree."""

    def evaluate(self, B, P, C, s, form="declared"):
        out = super().evaluate(B, P, C, s, form)
        for c, (forms, tot) in self.CLASS_TOTALS.items():
            Jc = out["eq13_J"][c]
            side = "E" if Jc > 0 else "P"
            for f in forms:
                out["J"][f] = Jc * s[f"{f}_{side}"] / s[f"{tot}_{side}"]
                _om_drop_form_values(out, f, keep_x=True)
                _om_rebook_dissipation(out, f)
        return _om_resum(self, out)


class OMAMPWithPPi(laws.OuterMembrane):
    """AMP crossing with p_Pi in place of p_A."""

    OM_FORMS = tuple((f, "Pi" if f == "AMP" else c, z) for f, c, z in laws.OuterMembrane.OM_FORMS)


class OMDroppedMgADP(laws.OuterMembrane):
    """A kernel that omits MgADP- from the adenine class."""

    def evaluate(self, B, P, C, s, form="declared"):
        out = super().evaluate(B, P, C, s, form)
        _om_drop_form_values(out, "MgADP")
        out["J"]["MgADP"] = B.n(0)
        return _om_resum(self, out)


class OMGammaMissing(laws.OuterMembrane):
    """gamma omitted: the permeability alone, in um per s, taken as the rate in per s."""

    def k(self, B, P, cls):
        return B.n(P["p_A_um_per_s"] if cls == "A" else P["p_Pi_um_per_s"])


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
L = laws.LAWS_BY_KEY
PLANTS = []


def _add(pid, law_key, desc, kind, make, named=False, forms=None, cross_form=False):
    PLANTS.append(Plant(pid, law_key, desc, kind, make, named, forms, cross_form))


FORM_PREFIX = {"complex_III_eq24": "C3_eq24", "atp_synthase": "F1", "phosphate_carrier": "PiHt",
               "nadh_supply": "supply", "adenylate_kinase": "AK"}


def _add_cross_forms(law):
    """Each form of a failing law, run as the kernel under test against every other form's rows
    (whichever form the user's ruling selects, the others are then its plants)."""
    for cand in law.FORMS:
        others = tuple(f for f in law.FORMS if f != cand)
        _add(f"{FORM_PREFIX[law.key]}_as_{cand}", law.key,
             f"the {cand} form judged against the law's other forms", "form",
             _same_form(law, form_map={f: cand for f in others}), forms=others, cross_form=True)


_add("C1_q_reversed", "complex_I", "Section 10: complex I with -4u in place of +4u (q = -4)",
     "thermodynamic", _same_form(C1QReversed()), named=True)
_add("C1_scalar_proton_dropped", "complex_I",
     "complex I's dG without its scalar proton term -RT ln(h_N/1e-7)", "thermodynamic",
     _same_form(C1ScalarProtonDropped()))
_add("C1_dG0_display", "complex_I", "dG0 at 1 M as section 9 displays it, -109.326 kJ/mol",
     "free-energy entry", _same_form(_rounded_dG0(laws.ComplexI, "-109326")))
_add("C3_eq7_dG0_display", "complex_III_eq7",
     "dG0 at 1 M as section 9 displays it, +47.382 kJ/mol", "free-energy entry",
     _same_form(_rounded_dG0(laws.ComplexIIIEq7, "47382")))
_add_cross_forms(L["complex_III_eq24"])
_add("C3_eq24_dG0_display", "complex_III_eq24",
     "dG0 at 1 M as section 9 displays it, +47.382 kJ/mol", "free-energy entry",
     _same_form(_rounded_dG0(laws.ComplexIIIEq24, "47382")))
_add("C3_eq24_restored_with_eq7_X_C3", "complex_III_eq24",
     "restored built with Eq. 7's own X_C3 (0.14483, the Without column) in place of 0.091737",
     "parameter", _same_form(L["complex_III_eq24"], P=_P(L["complex_III_eq24"], X_C3="0.14483")),
     forms=("restored",))
_add("C3_eq24_kappa_one", "complex_III_eq24", "J = A (1 - e^x) in place of A (1 - e^{x/2})",
     "kinetic", _same_form(C3KappaOne()), forms=("balanced", "restored"))
_add("C3_eq24_phi_inverted", "complex_III_eq24",
     "phosphate control inverted: (1 + Pi/k_Pi4)/(1 + Pi/k_Pi3)", "kinetic",
     _same_form(C3PhiInverted()))
_add("C4_dG0_display", "complex_IV", "dG0 at 1 M as section 9 displays it, -405.704 kJ/mol",
     "free-energy entry", _same_form(_rounded_dG0(laws.ComplexIV, "-405704")))
_add("C4_per_half_O2", "complex_IV", "the per-electron-pair J_C4 used as the per-O2 flux",
     "stoichiometry", _same_form(C4PerHalfO2()))
_add("C4_kappa_half", "complex_IV", "kappa = 1/2 per O2 in place of 1/4", "kinetic",
     _same_form(C4KappaHalf()))
_add("C4_ctot_parameter", "complex_IV",
     "c_tot = Table 1's cytC_tot in place of the clamped [c3+] + [c2+]", "kinetic",
     _same_form(C4CtotParameter()))
_add_cross_forms(L["atp_synthase"])
_add("F1_dG0_display", "atp_synthase", "dG0_F at 1 M as section 2 displays it, -5.032 kJ/mol",
     "free-energy entry", _same_form(_rounded_dG0(laws.ATPSynthase, "-5032")))
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
     "Section 10: exchange shares that do not sum to one (theta_P 0.35, theta_N 0.60)",
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
_add_cross_forms(L["phosphate_carrier"])
_add("PiHt_k_in_M", "phosphate_carrier", "k_PiHt read in M (0.45082 M), not mM", "unit",
     _same_form(L["phosphate_carrier"], P=_P(L["phosphate_carrier"], k_PiHt_mM="450.82")))
_add("PiHt_one_proton", "phosphate_carrier", "one proton in place of two with HPO4(2-)",
     "stoichiometry", _same_form(PiHtOneProton()))
_add("KH_proton_sides_swapped", "k_h_exchange", "H+ sides swapped in S and in dG",
     "stoichiometry", _same_form(KHProtonSidesSwapped()))
_add_cross_forms(L["nadh_supply"])
_add("supply_held_ratio_r", "nadh_supply",
     "Section 6: the held pair at S_red/S_ox = r, without 10^-0.10 (equilibrium at pH_N 7.00)",
     "thermodynamic", _same_form(SupplyHeldRatioR()), named=True)
_add("supply_upkeep_ratio_only", "nadh_supply",
     "the upkeep's work from the pair's ratio alone, without section 9's standard potentials",
     "free-energy entry", _same_form(SupplyUpkeepRatioOnly()))
_add("supply_dG0_display", "nadh_supply",
     "dG0_S at 1 M as section 9 displays it, +39.956 kJ/mol", "free-energy entry",
     _same_form(_rounded_dG0(laws.HeldReductantSupply, "39956")))
_add("supply_phi_inverted", "nadh_supply", "Eq. 1's phosphate factor inverted", "kinetic",
     _same_form(SupplyPhiInverted()))
_add("supply_X_DH_without", "nadh_supply",
     "X_DH from the Without column (0.10990) in place of 0.09183", "parameter",
     _same_form(L["nadh_supply"], P=_P(L["nadh_supply"], X_DH="0.10990")))
_add_cross_forms(L["adenylate_kinase"])
_add("AK_no_prefactor", "adenylate_kinase",
     "Section 7: the form without the prefactor (1 + [Mg2+]_P/K_MgATP)", "kinetic",
     _same_form(AKNoPrefactor()), named=True, forms=("balanced",))
_add("AK_K_base_rounded", "adenylate_kinase",
     "K_base rounded to 0.38896, which section 7 says is not the declared constant",
     "free-energy entry",
     _same_form(L["adenylate_kinase"], P=_P(L["adenylate_kinase"], K_base="0.38896")))
_add("AK_K_AK_on_base_forms", "adenylate_kinase",
     "the totals' K_AK = 0.4331 used on the base forms in place of K_base", "binding",
     _same_form(L["adenylate_kinase"], P=_P(L["adenylate_kinase"], K_base="0.4331")))
_add("AK_prefactor_MgADP", "adenylate_kinase",
     "the prefactor with K_MgADP in place of K_MgATP", "kinetic",
     _same_form(AKPrefactorADP()), forms=("balanced",))
_add("OM_total_as_base_form", "outer_membrane",
     "the class total crossing in place of the forms, booked as the base form (no ligand carried)",
     "form", _same_form(OMTotalAsBaseForm()), named=True)
_add("OM_total_split_upstream", "outer_membrane",
     "the class total crossing in place of the forms, split by the upstream side's fractions",
     "form", _same_form(OMTotalSplitUpstream()))
_add("OM_AMP_with_p_Pi", "outer_membrane", "AMP crossing with p_Pi in place of p_A", "parameter",
     _same_form(OMAMPWithPPi()))
_add("OM_MgADP_dropped", "outer_membrane", "MgADP- omitted from the adenine class", "form",
     _same_form(OMDroppedMgADP()))
_add("OM_gamma_missing", "outer_membrane", "gamma omitted from gamma p", "unit",
     _same_form(OMGammaMissing()))
_add("RT_display/outer_membrane", "outer_membrane", "RT = 2478.9570 J/mol, section 0's display",
     "constant", _const_plant(laws.OUTER, overrides={"RT": "2478.9570"}))
_add("T_310/outer_membrane", "outer_membrane", "T = 310.15 K in place of 298.15 K", "constant",
     _const_plant(laws.OUTER, T="310.15"))

for _law in laws.CYCLE_LAWS:
    if not _law.has_flux and _law.key != "lumped_QO":
        continue
    _add(f"RT_display/{_law.key}", _law.key, "RT = 2478.9570 J/mol, section 0's display",
         "constant", _const_plant(_law, overrides={"RT": "2478.9570"}))
    if _law.q(hp.parameters(_law.column)) != 0:
        _add(f"FRT_display/{_law.key}", _law.key, "F/RT = 0.0389217 per mV, section 0's display",
             "constant", _const_plant(_law, overrides={"F_RT_per_mV": "0.0389217"}))
    _add(f"T_310/{_law.key}", _law.key, "T = 310.15 K (the first tag's) in place of 298.15 K",
         "constant", _const_plant(_law, T="310.15"))
    # A law whose counts sum to zero is invariant to the activity unit: no power, not listed.
    if sum(nu for k, _sd, nu, _z in _law.legs_(hp.parameters(_law.column)) if k is not None):
        _add(f"activity_mM/{_law.key}", _law.key, "activities as c/(1 mM) in dG", "unit",
             _same_form(_mM_activity(type(_law))))

PLANTS_BY_ID = {p.pid: p for p in PLANTS}
