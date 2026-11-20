"""The sheet's own check: docs/TEMPLATED_POLYMERISATION_LAWS.md (gene regulation's option A, D235)
against its declared algebra, in 50-digit decimal arithmetic.

It is the lane's check of its own algebra, not an independent reference: the references (G2) are
written by an agent that reads the sheet alone. It imports nothing from the engine and nothing
outside Python's standard library, and it names no potential set. What it shows:

1. The reduction is exact while pH and free Mg2+ are held (the sheet's §3.2). Each part runs over
   random symbolic instances: random base potentials, random form sets (rows with no forms, no Mg2+
   on Pi and no H+ on the nucleotides included), random pH, free Mg2+ and totals. Each part has its
   own planted error, which it must catch:
   (a) every neutral potential, mu'°/RT = mu°_base/RT - ln P(h, m) - z_base mu_H/RT, equals
       Alberty's pseudoisomer sum over the row's forms (planted: ln P dropped);
   (b) every move's free energy is the same in both forms (planted: the neutral potentials taken
       at a pH other than the state's);
   (c) every charged move conserves charge, with the residues in transit counted (planted:
       translation's four protons written as three);
   (d) a law written on a free form equals one on totals with its constant divided by the form's
       fraction (planted: the constant left undivided). A law on totals gives the same flux in both
       forms as a corollary of (b), since both forms see the same totals; it is reported, not
       counted as a separate test.
2. Every move conserves every moiety in integers, in both forms (planted: recharging with one ATP).
3. The derivation of the world's potentials (§3.3). From a source's charged base potentials and
   forms, the world's two references, and the three cited entries with their offsets, the
   transform gives neutral entries equal to the cited values, and the source's ATP hydrolysis
   transformed (planted: an offset's proton term with the wrong sign).
4. The account is a state function (§3.4). The free energy G's gradient along each move is the
   move's free energy (planted: residues in transit carried at the monomer's potential). One
   passage's stage free energies plus the release sum to the net move's (planted: the release
   left unbooked).
5. The closed forms (§5):
   - the chain's exact steady state gives J = lambda M / (1 + lambda tau) and the two-gene
     budget (planted: initiation on the total machines; a machine not returned);
   - the passage time, from the chain's generator, has mean tau and variance tau^2 / m;
   - the closed forms of n_R(t) and E(t) match a direct integration of the chain.
6. The sheet's typed numbers and its equations of motion:
   - its move matrix and moieties against this file's;
   - its motion table (§4.7) against the moves composed, and its machine, moiety and free-energy
     identities column by column. Plants 3, 4 and 6 of §5.4 (and A1-M's second), as edits of that
     table, must each break the identity they name;
   - its entries in RT units;
   - each arm's parameters, and the derived values at the numeric test instance.

Run: python validation/gene_regulation/sheet_check.py [--out FILE]. About ten seconds on one CPU.

The transform (neutral_potentials, entry_offset) is also the registration's tool (the design
note's §7.7, step 3): a world's neutral potentials are computed with it from the source that the
registration names, given as base potentials and forms.
"""

import argparse
import json
import math
import random
import re
import sys
from decimal import Decimal, getcontext, localcontext
from fractions import Fraction
from pathlib import Path
from typing import NamedTuple

getcontext().prec = 50
D = Decimal
SHEET = Path(__file__).resolve().parents[2] / "docs" / "TEMPLATED_POLYMERISATION_LAWS.md"
TOLERANCE = D("1e-40")  # Identities, in RT units or relative.
ONE = D(1)
ZERO = D(0)
C_STD_MM = D(1000)  # c° = 1 M, in mM.

# ------------------------------------------------------------------ constants (sheet §0)

N_A = D("6.02214076e23")  # 1/mol, exact (SI 2019).
K_B = D("1.380649e-23")  # J/K, exact (SI 2019).
R_GAS = N_A * K_B  # J/(mol K)
T_K = D("310.15")  # Declared.
RT = R_GAS * T_K / 1000  # kJ/mol
KCAL = D("4.184")  # kJ per thermochemical kcal, exact.
COPY_FMOL = D(10) ** 15 / N_A  # One molecule in fmol.


def ln(v):
    return D(v).ln()


def exp(v):
    return D(v).exp()


# ------------------------------------------------------------------ rows, moves, moieties (§1, §2)

# Species of the move matrix: the neutral rows, the residues in transit (R_res, P_res) and, in the
# charged form only, the proton.
SPECIES = ("N", "M", "A", "ATP", "ADP", "Pi", "R", "P", "R_res", "P_res", "H")
MOVE_IDS = ("tx", "tl", "rel_R", "rel_P", "deg_R", "deg_P", "rc")


def valences(L_R):
    """The charged form's base valences (per molecule; per residue for R_res and P_res)."""
    return dict(N=-4, M=-2, A=0, ATP=-4, ADP=-3, Pi=-2, R=-L_R, P=0, R_res=-1, P_res=0, H=1)


def moves(L_R, L_P, *, charged=True, tl_protons=4, rc_atp=2):
    """{move: {species: nu}} per unit of progress (§2). Neutral: the proton row is left out."""
    out = {
        "tx": dict(N=-1, R_res=1, Pi=2, H=1),
        "tl": dict(A=-1, ATP=-4, P_res=1, ADP=4, Pi=4, H=tl_protons),
        "rel_R": dict(R_res=-L_R, R=1),
        "rel_P": dict(P_res=-L_P, P=1),
        "deg_R": dict(R=-1, M=L_R, H=L_R),
        "deg_P": dict(P=-1, A=L_P),
        "rc": dict(M=-1, ATP=-rc_atp, N=1, ADP=rc_atp),
    }
    if not charged:
        out = {k: {s: n for s, n in v.items() if s != "H"} for k, v in out.items()}
    return {k: {s: n for s, n in v.items() if n != 0} for k, v in out.items()}


def moieties(L_R, L_P):
    """{moiety: {species: weight}}, the residues in transit included (§1.4)."""
    return {
        "adenine": dict(ATP=1, ADP=1),
        "phosphorus": dict(N=3, M=1, ATP=3, ADP=2, Pi=1, R=L_R, R_res=1),
        "nucleoside": dict(N=1, M=1, R=L_R, R_res=1),
        "amino_acid": dict(A=1, P=L_P, P_res=1),
    }


def charge_errors(L_R, L_P, **planted):
    z, out = valences(L_R), []
    for move, nu in moves(L_R, L_P, **planted).items():
        total = sum(n * z[s] for s, n in nu.items())
        if total != 0:
            out.append(f"{move}: charge sum {total}")
    return out


def moiety_errors(L_R, L_P, *, charged, **planted):
    out = []
    for move, nu in moves(L_R, L_P, charged=charged, **planted).items():
        for moiety, w in moieties(L_R, L_P).items():
            total = sum(n * w.get(s, 0) for s, n in nu.items())
            if total != 0:
                out.append(f"{move}: moiety {moiety} changes by {total}")
    return out


# ------------------------------------------------------------------ the transform (§3.2)


class Form(NamedTuple):
    """A non-base form: n_H protons and n_Mg magnesium ions on the base, with its dissociation
    constant K_d = [base] h^n_H m^n_Mg / [form] in M^(n_H + n_Mg)."""

    n_H: int
    n_Mg: int
    K_d: Decimal


def binding_polynomial(forms, h, m):
    """P(h, m) = 1 + sum_f h^n_H m^n_Mg / K_d (h, m in M)."""
    return ONE + sum((h**f.n_H * m**f.n_Mg / f.K_d for f in forms), D(0))


def neutral_potential(z, mu_base, forms, h, m, mu_H0=ZERO):
    """mu'°/RT at 1 M of a row whose base form has valence z and mu°/RT (1 M) mu_base, at free
    proton h and free Mg2+ m (M): mu_base - ln P(h, m) - z (mu_H0 + ln h)."""
    return mu_base - ln(binding_polynomial(forms, h, m)) - z * (mu_H0 + ln(h))


def pseudoisomer_potential(z, mu_base, forms, h, m, mu_H0, mu_Mg0):
    """Alberty's form: -ln sum_j exp(-g_j), g_j = mu°_j - N_H(j) mu_H - N_Mg(j) mu_Mg, with each
    form's own mu°_j = mu_base + n_H mu_H0 + n_Mg mu_Mg0 + ln K_d, its proton content counted from
    the base form's charge, N_H(j) = z + n_H, and N_Mg(j) = n_Mg."""
    mu_h, mu_m = mu_H0 + ln(h), mu_Mg0 + ln(m)
    terms = [mu_base - z * mu_h]
    for f in forms:
        mu_f = mu_base + f.n_H * mu_H0 + f.n_Mg * mu_Mg0 + ln(f.K_d)
        terms.append(mu_f - (z + f.n_H) * mu_h - f.n_Mg * mu_m)
    return -ln(sum((exp(-g) for g in terms), D(0)))


def neutral_potentials(rows, *, pH, free_Mg_M, mu_H0=ZERO, c0_mM=C_STD_MM):
    """The registration's transform: {row: mu'°/RT at c0 (mM)} from {row: (z, mu°/RT of the base
    form at 1 M, [Form, ...])} at the declared pH and free Mg2+ (M), each moved to c0 by
    ln(c0 / 1000 mM) per molecule."""
    h, m = D(10) ** (-D(pH)), D(free_Mg_M)
    shift = ln(D(c0_mM) / 1000)
    return {
        row: neutral_potential(z, D(mu), forms, h, m, D(mu_H0)) + shift
        for row, (z, mu, forms) in rows.items()
    }


def entry_offset(stoichiometry, forms, *, pH, free_Mg_M, nu_H):
    """The temperature-free dG_RT_offset that turns a cited transformed entry (on neutral rows, at
    the declared pH and free Mg2+) into the charged form's base-form entry at 1 M, whose
    stoichiometry carries the proton row (nu_H) beside the rows of `stoichiometry`:
    dG°_base/RT = dG°'/RT + offset, offset = -nu_H ln(h / 1 M) + sum_i nu_i ln P_i(h, m).
    The proton's own mu°_H cancels. `forms` is {row: [Form, ...]}."""
    h, m = D(10) ** (-D(pH)), D(free_Mg_M)
    out = -nu_H * ln(h)
    for row, nu in stoichiometry.items():
        out += nu * ln(binding_polynomial(forms.get(row, ()), h, m))
    return out


# ------------------------------------------------------------------ random symbolic instances


def random_forms(rng, row):
    """A random form set; about one row in four has none, Pi never binds Mg2+ and the nucleotides
    sometimes bind no proton (the degenerate cases)."""
    if rng.random() < 0.25:
        return []
    out = []
    for n_H, n_Mg in ((1, 0), (0, 1), (1, 1), (2, 0)):
        if row == "Pi" and n_Mg:
            continue
        if row in ("ATP", "ADP", "N", "M") and n_H and rng.random() < 0.3:
            continue
        if rng.random() < 0.6:  # pK 5-9 per proton, pK_Mg 2-5 per magnesium ion.
            log_k = -sum(rng.uniform(5, 9) for _ in range(n_H))
            log_k -= sum(rng.uniform(2, 5) for _ in range(n_Mg))
            out.append(Form(n_H, n_Mg, D(10) ** D(repr(log_k))))
    return out


CHARGED_ROWS = ("N", "M", "A", "ATP", "ADP", "Pi", "R", "P", "R_res", "P_res")
FORM_ROWS = ("N", "M", "ATP", "ADP", "Pi")  # The polymers, residues and the amino acid bind none.


def random_instance(rng, L_R=1200, L_P=400):
    """Base potentials (mu°/RT at 1 M), forms, h, m, mu_H0, mu_Mg0 and totals (M)."""
    mu = {s: D(repr(rng.uniform(-60, 60))) for s in CHARGED_ROWS}
    mu["R"] = L_R * mu["R_res"]  # The polymer's potential is per residue (§3.1).
    mu["P"] = L_P * mu["P_res"]
    forms = {s: (random_forms(rng, s) if s in FORM_ROWS else []) for s in CHARGED_ROWS}
    totals = {s: D(10) ** D(repr(rng.uniform(-9, -1))) for s in CHARGED_ROWS}
    return dict(
        mu=mu,
        forms=forms,
        h=D(10) ** D(repr(-rng.uniform(6.0, 8.5))),
        m=D(10) ** D(repr(rng.uniform(-4.5, -2.0))),
        mu_H0=D(repr(rng.uniform(-5, 5))),
        mu_Mg0=D(repr(rng.uniform(-5, 5))),
        totals=totals,
        L_R=L_R,
        L_P=L_P,
    )


IN_TRANSIT = ("R_res", "P_res")  # No concentration term: they sit in the chain (§3.1).


def charged_dG(inst, nu, *, h=None, m=None):
    """A move's dG/RT in the charged form: base forms at equilibrium with their forms,
    mu_b = mu°_b + ln(c_tot / P), the proton at mu_H0 + ln h."""
    h = inst["h"] if h is None else h
    m = inst["m"] if m is None else m
    out = D(0)
    for s, n in nu.items():
        if s == "H":
            out += n * (inst["mu_H0"] + ln(h))
        elif s in IN_TRANSIT:
            out += n * inst["mu"][s]
        else:
            p = binding_polynomial(inst["forms"][s], h, m)
            out += n * (inst["mu"][s] + ln(inst["totals"][s] / p))
    return out


def neutral_mu0(inst, s, *, h, m, drop_P=False):
    z = valences(inst["L_R"])[s]
    forms = [] if drop_P else inst["forms"][s]
    return neutral_potential(z, inst["mu"][s], forms, h, m, inst["mu_H0"])


def neutral_dG(inst, nu, *, h=None, m=None):
    """A move's dG/RT in the neutral form, from the transformed potentials at (h, m) and the
    totals; the proton row is absent."""
    h = inst["h"] if h is None else h
    m = inst["m"] if m is None else m
    out = D(0)
    for s, n in nu.items():
        if s == "H":
            continue
        term = neutral_mu0(inst, s, h=h, m=m)
        if s not in IN_TRANSIT:
            term += ln(inst["totals"][s])
        out += n * term
    return out


def sat(c, k):
    return c / (k + c)


def share_factor(x, n):
    """The per-residue (per-step) factor 1 - e^(x/n)."""
    return ONE - exp(x / n)


# The rate laws of §4 on totals, each as (kinetic part S from totals, share n) for a move; the
# flux is S (1 - e^(x/n)), x the move's dG/RT per unit of progress. Saturation constants in M.
LAWS = {
    "tx": (lambda c: sat(c["N"], D("2e-5")), 1),
    "tl": (lambda c: sat(c["A"], D("2e-5")) * sat(c["ATP"], D("2e-5")), 1),
    "rc": (lambda c: sat(c["M"], D("1e-4")) * sat(c["ATP"], D("1e-4")), 2),
    "deg_R": (lambda c: c["R"], "L_R"),
    "deg_P": (lambda c: c["P"], "L_P"),
}


def law_flux(inst, move, x):
    kinetic, share = LAWS[move]
    n = inst[share] if isinstance(share, str) else share
    return kinetic(inst["totals"]) * share_factor(x, n)


def free_form_fraction(inst, row, form_index):
    """theta = [form] / total at the instance's (h, m); -1 picks the base form."""
    forms, h, m = inst["forms"][row], inst["h"], inst["m"]
    p = binding_polynomial(forms, h, m)
    if form_index < 0:
        return ONE / p
    f = forms[form_index]
    return h**f.n_H * m**f.n_Mg / f.K_d / p


# ------------------------------------------------------------------ check 1: the reduction


def check_reduction(n_states=300, seed=20261120):
    rng = random.Random(seed)
    report, ok = {}, True
    worst = dict(a=D(0), b=D(0), d=D(0), d_free=D(0))
    planted = dict(a=D(0), b=D(0), d=D(0))
    for _ in range(n_states):
        inst = random_instance(rng, L_R=rng.choice((8, 150, 1200)), L_P=rng.choice((8, 50, 400)))
        h, m = inst["h"], inst["m"]
        # (a) the closed form against Alberty's pseudoisomer sum, every row.
        for s in CHARGED_ROWS:
            z = valences(inst["L_R"])[s]
            closed = neutral_potential(z, inst["mu"][s], inst["forms"][s], h, m, inst["mu_H0"])
            alberty = pseudoisomer_potential(
                z, inst["mu"][s], inst["forms"][s], h, m, inst["mu_H0"], inst["mu_Mg0"]
            )
            worst["a"] = max(worst["a"], abs(closed - alberty))
            dropped = neutral_mu0(inst, s, h=h, m=m, drop_P=True)
            planted["a"] = max(planted["a"], abs(dropped - alberty))
        # (b) every move's dG in both forms; planted: the neutral potentials at another pH.
        charged = moves(inst["L_R"], inst["L_P"])
        for move, nu in charged.items():
            dg_c = charged_dG(inst, nu)
            dg_n = neutral_dG(inst, nu)
            worst["b"] = max(worst["b"], abs(dg_c - dg_n))
            if "H" in nu or any(inst["forms"][s] for s in nu if s in FORM_ROWS):
                shifted = neutral_dG(inst, nu, h=h * D("1.58489319246111348520210137339"))
                planted["b"] = max(planted["b"], abs(dg_c - shifted))
            # (d) the rate laws on totals.
            if move in LAWS:
                j_c, j_n = law_flux(inst, move, dg_c), law_flux(inst, move, dg_n)
                scale = max(abs(j_c), abs(j_n), D("1e-300"))
                worst["d"] = max(worst["d"], abs(j_c - j_n) / scale)
        # (d) a law written on a free form of N (a random one, or the base form) against the
        # same law on totals with K / theta; planted: K left undivided.
        forms = inst["forms"]["N"]
        index = rng.randrange(-1, len(forms)) if forms else -1
        theta = free_form_fraction(inst, "N", index)
        k_free, c_tot = D("2e-5"), inst["totals"]["N"]
        on_free = sat(c_tot * theta, k_free)
        on_total = sat(c_tot, k_free / theta)
        worst["d_free"] = max(worst["d_free"], abs(on_free - on_total) / on_total)
        if forms:
            planted["d"] = max(planted["d"], abs(on_free - sat(c_tot, k_free)) / on_total)
    report["a_neutral_potentials_vs_alberty"] = f"{worst['a']:.3e}"
    report["a_planted_lnP_dropped"] = f"{planted['a']:.3e}"
    report["b_move_dG_charged_vs_neutral"] = f"{worst['b']:.3e}"
    report["b_planted_pH_not_held"] = f"{planted['b']:.3e}"
    report["d_flux_on_totals_corollary_of_b"] = f"{worst['d']:.3e}"
    report["d_free_form_law_vs_scaled_total_law"] = f"{worst['d_free']:.3e}"
    report["d_planted_K_undivided"] = f"{planted['d']:.3e}"
    ok &= worst["a"] < TOLERANCE and worst["b"] < TOLERANCE
    ok &= worst["d"] < TOLERANCE and worst["d_free"] < TOLERANCE
    ok &= planted["a"] > D("1e-3") and planted["b"] > D("1e-3") and planted["d"] > D("1e-3")
    # (c) charge, in integers, at the arms' lengths and at random ones.
    lengths = [(1200, 400), (2400, 400), (150, 50), (1, 1), (7, 13)]
    errors = [e for L in lengths for e in charge_errors(*L)]
    caught = all(charge_errors(*L, tl_protons=3) for L in lengths)
    report["c_charge"] = errors or "every charged move conserves charge"
    report["c_planted_three_protons"] = "caught" if caught else "NOT CAUGHT"
    ok &= not errors and caught
    return ok, report


# ------------------------------------------------------------------ check 2: moieties


def check_moieties():
    lengths = [(1200, 400), (2400, 400), (150, 50), (1, 1), (7, 13)]
    errors = []
    for charged in (True, False):
        errors += [e for L in lengths for e in moiety_errors(*L, charged=charged)]
    caught = all(moiety_errors(*L, charged=c, rc_atp=1) for L in lengths for c in (True, False))
    report = dict(
        moieties=errors or "every move conserves every moiety, in both forms",
        planted_recharging_one_ATP="caught" if caught else "NOT CAUGHT",
    )
    return not errors and caught, report


# ------------------------------------------------------------------ the cited entries (§3.3)

E_PD_KJ = D("-5.3") * KCAL  # Dickson et al. 2000: a DNA phosphodiester bond's hydrolysis.
E_PEP_KJ = D("-3.6") * KCAL  # Martin 1998 (Table I, glycylglycine), as BioNumbers 114386 reads it.
K_MYOKINASE = D("1.05")  # Lawson and Veech 1979: 2 ADP = AMP + ATP, totals, pH 7.0, 1 mM Mg2+.
G_ATP_TEST_KJ = D("-32")  # Wiseman et al. 2023, at pH 7, pMg 3, 37 °C: the test instance only.
DECLARED_PH, DECLARED_MG_M = D(7), D("1e-3")


def entries_RT():
    """Each entry's dG°'/RT at T_K: kJ/mol entries converted at T_K (temperature-independent
    basis), and the recharging entry from its cited constant, temperature-free."""
    return dict(
        E_pd=E_PD_KJ / RT,
        E_pep=E_PEP_KJ / RT,
        E_rc=ln(K_MYOKINASE),  # M + 2 ATP -> N + 2 ADP is the reverse of 2 ADP -> AMP + ATP.
        G_ATP=G_ATP_TEST_KJ / RT,
    )


# The neutral entries (§3.3): {entry: (stoichiometry on neutral rows and residues, nu_H of the
# base-form reaction)}; per residue for the two hydrolyses.
ENTRY_MOVES = {
    "E_rc": (dict(M=-1, ATP=-2, N=1, ADP=2), 0),
    "E_pd": (dict(R_res=-1, M=1), 1),
    "E_pep": (dict(P_res=-1, A=1), 0),
    "G_ATP": (dict(ATP=-1, ADP=1, Pi=1), 1),
}


def test_instance_potentials(e=None):
    """The neutral potentials of the numeric test instance (§3.3), mu'°/RT at 1 M: ADP, Pi, M and
    A at 0; the others from the entries."""
    e = entries_RT() if e is None else e
    mu = dict(ADP=D(0), Pi=D(0), M=D(0), A=D(0))
    mu["ATP"] = mu["ADP"] + mu["Pi"] - e["G_ATP"]
    mu["N"] = mu["M"] + 2 * mu["ATP"] - 2 * mu["ADP"] + e["E_rc"]
    mu["R_res"] = mu["M"] - e["E_pd"]
    mu["P_res"] = mu["A"] - e["E_pep"]
    return mu


def world_base_potentials(
    source_base, forms, *, mu_H0, pH=DECLARED_PH, free_Mg_M=DECLARED_MG_M, e=None, proton_sign=1
):
    """The charged form's base potentials (mu°/RT at 1 M) of §3.3, solved in order: the source's
    ATP, ADP and Pi (source_base); the world's references M and A at 0; then N from E_rc, the RNA
    residue from E_pd and the protein residue from E_pep, each base-form entry being its cited
    value plus its offset. forms is {row: [Form, ...]}; proton_sign = -1 plants the offset's proton
    term with the wrong sign."""
    e = entries_RT() if e is None else e
    b = {s: D(v) for s, v in source_base.items()}
    b["M"], b["A"] = D(0), D(0)
    off = {
        k: entry_offset(nu, forms, pH=pH, free_Mg_M=free_Mg_M, nu_H=proton_sign * nu_h)
        for k, (nu, nu_h) in ENTRY_MOVES.items()
    }
    # Each base-form entry is sum nu mu°_b + nu_H mu°_H: M + 2 ATP -> N + 2 ADP; R_res -> M + H+;
    # P_res -> A.
    b["N"] = e["E_rc"] + off["E_rc"] + b["M"] + 2 * b["ATP"] - 2 * b["ADP"]
    b["R_res"] = b["M"] + D(mu_H0) - (e["E_pd"] + off["E_pd"])
    b["P_res"] = b["A"] - (e["E_pep"] + off["E_pep"])
    return b


def world_potentials(
    source, *, L_R, L_P, pH=DECLARED_PH, free_Mg_M=DECLARED_MG_M, c0_mM=C_STD_MM, world_forms=None
):
    """The registration's tool (§3.3): the neutral world's mu'°/RT at c0 (mM) for ATP, ADP, Pi, N,
    M, A, R and P (whole molecules). source is the named source's {"mu_H0": mu°_H/RT, "ATP" |
    "ADP" | "Pi": (mu°/RT of the base form at 1 M, [Form, ...])}; world_forms {"N" | "M": [Form,
    ...]} is the charged arm's declaration, which leaves the neutral result unchanged (part 3)."""
    forms = {s: [] for s in CHARGED_ROWS}
    forms.update({s: list(source[s][1]) for s in ("ATP", "ADP", "Pi")})
    forms.update({s: list(f) for s, f in (world_forms or {}).items()})
    mu_H0 = D(source.get("mu_H0", 0))
    base = world_base_potentials(
        {s: source[s][0] for s in ("ATP", "ADP", "Pi")}, forms, mu_H0=mu_H0, pH=pH,
        free_Mg_M=free_Mg_M,
    )  # fmt: skip
    z = valences(L_R)
    rows = {s: (z[s], base[s], forms[s]) for s in ("ATP", "ADP", "Pi", "N", "M", "A")}
    rows["R"] = (z["R"], L_R * base["R_res"], [])
    rows["P"] = (z["P"], L_P * base["P_res"], [])
    return neutral_potentials(rows, pH=pH, free_Mg_M=free_Mg_M, mu_H0=mu_H0, c0_mM=c0_mM)


def check_derivation(n_sources=200, seed=7):
    """§3.3: base potentials from a random source, the world's references and the cited entries
    with offsets; transformed, the neutral entries are the cited values, and the source's ATP
    hydrolysis is its own transform. world_potentials, end to end, gives the same entries with or
    without the world's own forms for N and M."""
    rng = random.Random(seed)
    e = entries_RT()
    h0, m0 = D(10) ** (-DECLARED_PH), DECLARED_MG_M
    z = valences(1)
    worst, planted, worst_atp, worst_tool = D(0), D(0), D(0), D(0)
    neutral_rows = ("N", "M", "A", "ATP", "ADP", "Pi", "R_res", "P_res")
    for _ in range(n_sources):
        inst = random_instance(rng)
        forms, mu_H0 = inst["forms"], inst["mu_H0"]
        source = {s: inst["mu"][s] for s in ("ATP", "ADP", "Pi")}
        for sign in (1, -1):
            b = world_base_potentials(source, forms, mu_H0=mu_H0, e=e, proton_sign=sign)
            mu_n = {s: neutral_potential(z[s], b[s], forms[s], h0, m0, mu_H0) for s in neutral_rows}
            gap = max(
                abs(sum(n * mu_n[s] for s, n in ENTRY_MOVES[k][0].items()) - e[k])
                for k in ("E_rc", "E_pd", "E_pep")
            )
            if sign == 1:
                worst = max(worst, gap)
                nu, nu_h = ENTRY_MOVES["G_ATP"]
                base_hyd = b["ADP"] + b["Pi"] - b["ATP"] + nu_h * mu_H0
                off = entry_offset(nu, forms, pH=DECLARED_PH, free_Mg_M=m0, nu_H=nu_h)
                neutral_hyd = mu_n["ADP"] + mu_n["Pi"] - mu_n["ATP"]
                worst_atp = max(worst_atp, abs(base_hyd - off - neutral_hyd))
            else:
                planted = max(planted, gap)
        src = dict(mu_H0=mu_H0, **{s: (inst["mu"][s], forms[s]) for s in ("ATP", "ADP", "Pi")})
        for world_forms in (None, {"N": forms["N"], "M": forms["M"]}):
            w = world_potentials(src, L_R=1200, L_P=400, world_forms=world_forms)
            got = dict(
                E_rc=w["N"] + 2 * w["ADP"] - w["M"] - 2 * w["ATP"],
                E_pd=(1200 * w["M"] - w["R"]) / 1200,
                E_pep=(400 * w["A"] - w["P"]) / 400,
            )
            worst_tool = max(worst_tool, max(abs(got[k] - e[k]) for k in got))
    ok = worst < TOLERANCE and worst_atp < TOLERANCE and worst_tool < TOLERANCE
    ok &= planted > D("1e-3")
    return ok, dict(
        neutral_entries_vs_cited=f"{worst:.3e}",
        source_ATP_hydrolysis_transformed=f"{worst_atp:.3e}",
        registration_tool_with_and_without_world_forms=f"{worst_tool:.3e}",
        planted_offset_proton_sign=f"{planted:.3e}",
    )


# ------------------------------------------------------------------ check 4: the account (§3.4)


def free_energy(n, mu0, V, *, transit_mu=None):
    """G/RT (fmol x RT) of the operator's rows and the residues in transit: sum_s n_s (mu'°_s +
    ln(c_s / c°) - 1) + sum over transit residues of W mu'°_res; c in mM, c° = 1000 mM."""
    out = D(0)
    for s, amount in n.items():
        if s in IN_TRANSIT:
            out += amount * (transit_mu or mu0)[s]
        else:
            out += amount * (mu0[s] + ln(amount / V / 1000) - 1)
    return out


def move_dG(n, mu0, V, nu):
    """dG/RT of a move from the potentials at state n (c° = 1 M)."""
    out = D(0)
    for s, k in nu.items():
        out += k * (mu0[s] if s in IN_TRANSIT else mu0[s] + ln(n[s] / V / 1000))
    return out


def check_account(n_states=40, seed=11):
    """G's gradient along each move by a central difference, at 90 digits: its truncation is
    (eps^2 / 6) sum nu^3 / n^2, up to 1e-48 here with nu = 1200 and n = 1e-6 fmol."""
    with localcontext() as ctx:
        ctx.prec = 90
        return _check_account(n_states, seed)


def _check_account(n_states, seed):
    rng = random.Random(seed)
    L_R, L_P, V = 1200, 400, D(1)
    mu = test_instance_potentials()
    mu["R"], mu["P"] = L_R * mu["R_res"], L_P * mu["P_res"]
    worst_grad, planted_grad, worst_tel, planted_tel = D(0), D(0), D(0), D(0)
    bad_transit = dict(mu, R_res=mu["N"], P_res=mu["A"])
    eps = D("1e-32")
    for _ in range(n_states):
        n = {s: D(10) ** D(repr(rng.uniform(-6, 1))) for s in SPECIES if s != "H"}
        for move, nu in moves(L_R, L_P, charged=False).items():
            up = {s: n[s] + eps * k for s, k in nu.items()}
            down = {s: n[s] - eps * k for s, k in nu.items()}
            grad = (free_energy({**n, **up}, mu, V) - free_energy({**n, **down}, mu, V)) / (2 * eps)
            worst_grad = max(worst_grad, abs(grad - move_dG(n, mu, V, nu)))
            if move in ("tx", "tl", "rel_R", "rel_P"):
                g_bad = (
                    free_energy({**n, **up}, mu, V, transit_mu=bad_transit)
                    - free_energy({**n, **down}, mu, V, transit_mu=bad_transit)
                ) / (2 * eps)
                planted_grad = max(planted_grad, abs(g_bad - move_dG(n, mu, V, nu)))
        # Telescoping: m stages of r residues, then the release, against the net move.
        for route, (L, m_st) in (("tx", (L_R, 8)), ("tl", (L_P, 8))):
            r = L // m_st
            per = moves(L_R, L_P, charged=False)[route]
            rel = moves(L_R, L_P, charged=False)["rel_R" if route == "tx" else "rel_P"]
            stages = sum(r * move_dG(n, mu, V, per) for _ in range(m_st))
            net = {s: L * k for s, k in per.items() if s not in IN_TRANSIT}
            net["R" if route == "tx" else "P"] = 1
            worst_tel = max(
                worst_tel, abs(stages + move_dG(n, mu, V, rel) - move_dG(n, mu, V, net))
            )
            planted_tel = max(planted_tel, abs(stages - move_dG(n, mu, V, net)))
    ok = worst_grad < D("1e-30") and worst_tel < TOLERANCE
    ok &= planted_grad > D("1e-3") and planted_tel > D("1e-3")
    return ok, dict(
        gradient_of_G_vs_move_dG=f"{worst_grad:.3e}",
        planted_transit_at_monomer_potential=f"{planted_grad:.3e}",
        telescoping_stages_plus_release=f"{worst_tel:.3e}",
        planted_release_unbooked=f"{planted_tel:.3e}",
    )


# ------------------------------------------------------------------ check 5: closed forms (§5)


def _solve(matrix, rhs):
    """Exact Gaussian elimination over Fractions."""
    n = len(rhs)
    a = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = next(r for r in range(col, n) if a[r][col] != 0)
        a[col], a[pivot] = a[pivot], a[col]
        for r in range(n):
            if r != col and a[r][col] != 0:
                f = a[r][col] / a[col][col]
                a[r] = [x - f * y for x, y in zip(a[r], a[col], strict=True)]
    return [a[i][n] / a[i][i] for i in range(n)]


def chain_steady_state(genes, M, *, on_total=False, returned=True):
    """The exact steady state of machines shared by genes [(lambda, kappa, m), ...]: unknowns
    F and each gene's C_1..C_m; initiation lambda F (lambda M with on_total), stage exits kappa
    C_j, the last returning its machine (unless returned is False); the machine identity
    F + sum C = M closes the system (with a machine not returned, F's balance replaces it)."""
    size = 1 + sum(m for _, _, m in genes)
    rows, rhs = [], []
    # Each stage's balance.
    offset = 1
    for lam, kappa, m in genes:
        for j in range(m):
            row = [Fraction(0)] * size
            if j == 0:
                if on_total:
                    rhs_value = -lam * M
                else:
                    row[0] = lam
                    rhs_value = Fraction(0)
            else:
                row[offset + j - 1] = kappa
                rhs_value = Fraction(0)
            row[offset + j] = -kappa
            rows.append(row)
            rhs.append(rhs_value)
        offset += m
    # The machine identity, or the free machines' own balance when one is not returned.
    row = [Fraction(1)] * size
    if returned:
        rows.append(row)
        rhs.append(M)
    else:
        row = [Fraction(0)] * size
        row[0] = -sum(lam for lam, _, _ in genes)  # dF/dt = -sum lambda F, nothing returns.
        rows.append(row)
        rhs.append(Fraction(0))
    x = _solve(rows, rhs)
    out, offset = [], 1
    for _, kappa, m in genes:
        out.append(kappa * x[offset + m - 1])  # The release flux.
        offset += m
    return out


def check_closed_forms(seed=3):
    rng = random.Random(seed)
    worst, planted_total, planted_return = Fraction(0), Fraction(0), Fraction(0)
    for _ in range(60):
        M = Fraction(rng.randint(1, 500))
        genes = [
            (Fraction(rng.randint(1, 400), 1000), Fraction(rng.randint(10, 900), 1000),
             rng.choice((1, 2, 4, 8)))
            for _ in range(rng.choice((1, 2, 3)))
        ]  # fmt: skip
        budget = 1 + sum(lam * m / kappa for lam, kappa, m in genes)
        closed = [lam * M / budget for lam, _, _ in genes]
        exact = chain_steady_state(genes, M)
        worst = max(worst, max(abs(a - b) / b for a, b in zip(exact, closed, strict=True)))
        on_total = chain_steady_state(genes, M, on_total=True)
        planted_total = max(
            planted_total, max(abs(a - b) / b for a, b in zip(on_total, closed, strict=True))
        )
        lost = chain_steady_state(genes, M, returned=False)
        planted_return = max(
            planted_return, max(abs(a - b) / b for a, b in zip(lost, closed, strict=True))
        )
    # The passage time through m stages of rate kappa, from the chain's sub-generator G (G_jj =
    # -kappa, G_j,j+1 = kappa): mean e_1' (-G)^-1 1 and second moment 2 e_1' (-G)^-2 1.
    moments = []
    for m, kappa in ((8, Fraction(1, 3)), (8, Fraction(8, 25)), (3, Fraction(7, 10)), (6, 2)):
        kappa = Fraction(kappa)
        minus_g = [
            [kappa if i == j else (-kappa if j == i + 1 else Fraction(0)) for j in range(m)]
            for i in range(m)
        ]
        first = _solve(minus_g, [Fraction(1)] * m)
        second = _solve(minus_g, first)
        mean, var = first[0], 2 * second[0] - first[0] ** 2
        tau = m / kappa
        moments.append(mean == tau and var == tau**2 / m)
    mrna = mrna_closed_form_gap()
    ok = worst == 0 and planted_total > Fraction(1, 100) and planted_return > Fraction(1, 100)
    ok &= all(moments) and mrna < 1e-9
    return ok, dict(
        steady_state_vs_closed_forms=float(worst),
        planted_initiation_on_total_machines=float(planted_total),
        planted_machine_not_returned=float(planted_return),
        passage_time_mean_and_variance="exact" if all(moments) else "WRONG",
        mrna_and_engaged_closed_forms_vs_integration=f"{mrna:.3e}",
    )


def regularized_lower_gamma(m, x):
    """P(m, x) for integer m >= 1: 1 - e^(-x) sum_{k<m} x^k / k!."""
    term, total = 1.0, 1.0
    for k in range(1, m):
        term *= x / k
        total += term
    return 1.0 - math.exp(-x) * total


def mrna_closed_form(t, J, kappa, k, m, n0=0.0):
    """§5.1's n_R(t), kappa > k: n0 e^(-k t) + (J / k) [P(m, kappa t) - e^(-k t)
    (kappa / (kappa - k))^m P(m, (kappa - k) t)]."""
    return n0 * math.exp(-k * t) + J / k * (
        regularized_lower_gamma(m, kappa * t)
        - math.exp(-k * t)
        * (kappa / (kappa - k)) ** m
        * regularized_lower_gamma(m, (kappa - k) * t)
    )


def engaged_closed_form(t, J, kappa, m):
    """§5.1's E(t) = (J / kappa) sum_{j=1..m} P(j, kappa t), the chain fed from empty at t = 0."""
    return J / kappa * sum(regularized_lower_gamma(j, kappa * t) for j in range(1, m + 1))


def mrna_closed_form_gap():
    """The closed forms of n_R(t) and E(t) against RK4 on the chain (m stages, then first-order
    loss), relative to their plateaus, at A1's transcription rates."""
    J, kappa, k, m, n0 = 1.0, 1 / 3, 3e-3, 8, 0.25
    y = [0.0] * m + [n0]

    def f(y):
        d = [J - kappa * y[0]] + [kappa * (y[j - 1] - y[j]) for j in range(1, m)]
        return d + [kappa * y[m - 1] - k * y[m]]

    h, t, worst = 0.025, 0.0, 0.0
    for step in range(1, 80001):
        k1 = f(y)
        k2 = f([a + h / 2 * b for a, b in zip(y, k1, strict=True)])
        k3 = f([a + h / 2 * b for a, b in zip(y, k2, strict=True)])
        k4 = f([a + h * b for a, b in zip(y, k3, strict=True)])
        y = [
            a + h / 6 * (b + 2 * c + 2 * d + e)
            for a, b, c, d, e in zip(y, k1, k2, k3, k4, strict=True)
        ]
        t = step * h
        if step % 4000 == 0 or step == 400:
            worst = max(worst, abs(y[m] - mrna_closed_form(t, J, kappa, k, m, n0)) / (J / k))
            engaged = sum(y[:m])
            worst = max(worst, abs(engaged - engaged_closed_form(t, J, kappa, m)) / (J * m / kappa))
    return worst


# ------------------------------------------------------------------ the motion table (§4.7)

MOTION_COLUMNS = ("J_I_tx", "S_tx", "Q_tx", "D_R", "J_I_tl", "S_tl", "Q_tl", "D_P", "J_C")
TRANSIT = {"R_res": "W_tx", "P_res": "W_tl"}


def motion(L_R, L_P, r_tx, r_tl):
    """§4.7's columns composed from the move matrix: {column: {amount: coefficient}}."""
    mv = moves(L_R, L_P, charged=False)

    def scaled(move, k, extra=None):
        out = {TRANSIT.get(s, s): k * n for s, n in mv[move].items()}
        for s, n in (extra or {}).items():
            out[s] = out.get(s, 0) + n
        return {s: n for s, n in out.items() if n}

    return {
        "J_I_tx": {"F_pol": -1, "E_tx": 1},
        "S_tx": scaled("tx", r_tx),
        "Q_tx": scaled("rel_R", 1, {"F_pol": 1, "E_tx": -1}),
        "D_R": scaled("deg_R", 1),
        "J_I_tl": {"F_rib": -1, "E_tl": 1},
        "S_tl": scaled("tl", r_tl),
        "Q_tl": scaled("rel_P", 1, {"F_rib": 1, "E_tl": -1}),
        "D_P": scaled("deg_P", 1),
        "J_C": scaled("rc", 1),
    }


def motion_errors(table, L_R, L_P, r_tx, r_tl, seed=5):
    """The identities a motion table must keep, column by column: the machines (F + E per pool),
    every moiety (the residues in transit W carrying R_res's and P_res's weights), and each
    column's free energy per unit flux equal to its move's (S: r per residue; Q: the release; D,
    J_C: their moves; J_I: zero), at a random state of the test instance."""
    out = []
    weights = {
        k: {TRANSIT.get(s, s): w for s, w in v.items()} for k, v in moieties(L_R, L_P).items()
    }
    rng = random.Random(seed)
    mu = test_instance_potentials()
    mu["R"], mu["P"] = L_R * mu["R_res"], L_P * mu["P_res"]
    n = {
        s: D(10) ** D(repr(rng.uniform(-6, 1)))
        for s in ("N", "M", "A", "ATP", "ADP", "Pi", "R", "P")
    }

    def potential(amount):
        if amount in ("W_tx", "W_tl"):
            return mu["R_res" if amount == "W_tx" else "P_res"]
        if amount in ("F_pol", "E_tx", "F_rib", "E_tl"):
            return D(0)  # Machines carry no free energy.
        return mu[amount] + ln(n[amount] / 1000)  # V = 1 pL, c° = 1000 mM.

    mv = moves(L_R, L_P, charged=False)
    expected_dG = {
        "J_I_tx": D(0),
        "S_tx": r_tx * move_dG(n, mu, 1, mv["tx"]),
        "Q_tx": move_dG(n, mu, 1, mv["rel_R"]),
        "D_R": move_dG(n, mu, 1, mv["deg_R"]),
        "J_I_tl": D(0),
        "S_tl": r_tl * move_dG(n, mu, 1, mv["tl"]),
        "Q_tl": move_dG(n, mu, 1, mv["rel_P"]),
        "D_P": move_dG(n, mu, 1, mv["deg_P"]),
        "J_C": move_dG(n, mu, 1, mv["rc"]),
    }
    for column, coefficients in table.items():
        for pool in (("F_pol", "E_tx"), ("F_rib", "E_tl")):
            if sum(coefficients.get(a, 0) for a in pool) != 0:
                out.append(f"{column}: the machines {pool} are not conserved")
        for moiety, w in weights.items():
            total = sum(k * w.get(a, 0) for a, k in coefficients.items())
            if total != 0:
                out.append(f"{column}: moiety {moiety} changes by {total}")
        dg = sum((k * potential(a) for a, k in coefficients.items()), D(0))
        if abs(dg - expected_dG[column]) > TOLERANCE * (1 + abs(expected_dG[column])):
            out.append(f"{column}: its free energy is not its move's")
    return out


def motion_plants(L_R, L_P, r_tx, r_tl):
    """Plants 3, 4 and 6 of the sheet's §5.4 (4 is also A1-M's second), as edits of the motion
    table: {plant: (edited table, the words its error must contain)}."""
    base = motion(L_R, L_P, r_tx, r_tl)
    fuel = {k: dict(v) for k, v in base.items()}
    fuel["S_tl"] = {a: k for a, k in base["S_tl"].items() if a not in ("ATP", "ADP", "Pi")}
    machine = {k: dict(v) for k, v in base.items()}
    machine["Q_tx"].pop("F_pol")
    residues = {k: dict(v) for k, v in base.items()}
    residues["S_tl"]["A"] = -(r_tl - 1)  # 49 amino acids drawn per exit, while W_tl gains 50.
    return {
        "3_dropped_fuel": (fuel, "free energy"),
        "4_machine_not_returned": (machine, "machines"),
        "6_wrong_residue_count": (residues, "amino_acid"),
    }


# ------------------------------------------------------------------ the arms' numbers (§5)

A1 = dict(
    V=D("1.0"),
    T_copies=D(1),
    L_R=D(1200),
    m_tx=D(8),
    v_tx=D(50),
    L_P=D(400),
    m_tl=D(8),
    v_tl=D(16),
    M_pol=D("1e4"),
    M_rib=D("1e6"),
    k_I_tx=D("1.2e4"),
    k_I_tl=D(120),
    K_N_tx=D("0.02"),
    K_A_tl=D("0.02"),
    K_ATP_tl=D("0.02"),
    V_C=D("0.01"),
    K_M_rc=D("0.1"),
    K_ATP_rc=D("0.1"),
    k_R=D("3.0e-3"),
    k_P=D("5.0e-4"),
    K_X=D("1.0e-3"),
    n_X=D(2),
    b_X=D("0.02"),
    P_on=D("2.0e-6"),
    k_X=D("2.0e-3"),
    t_off=D(10800),
    t_end=D(21600),
    c_N=D("2.0"),
    c_M=D("0.05"),
    c_A=D("2.0"),
    c_ATP=D("5.0"),
    c_ADP=D("0.5"),
    c_Pi=D("5.0"),
    c_X=D("1.0e-3"),
    c_R=D("1.0e-12"),
    c_P=D("1.0e-12"),
)
A1M = dict(
    M_pol=D(100),
    k_I_tx=D("2.5e6"),
    L_2=D(2400),
    T_1=D(10),
    T_2=D(5),
    c_N=D("5.0"),
    M_rib=D(1000),
    k_I_tl=D("2.4e6"),
    c_A=D("5.0"),
    t_end_pol=D(3600),
    t_end_rib=D(600),
    window_pol=D(600),
    window_rib=D(120),
)
SWEEP = (1, 2, 5, 10, 20, 50, 100)


def x_values(c, mu, L_R, L_P):
    """Per-residue (or per-turnover) dG/RT of each move at concentrations c (mM), c° = 1 M."""

    def a(s):
        return c[s] / 1000

    x_tx = mu["R_res"] + 2 * (mu["Pi"] + ln(a("Pi"))) - (mu["N"] + ln(a("N")))
    x_tl = (mu["P_res"] + 4 * (mu["ADP"] + ln(a("ADP"))) + 4 * (mu["Pi"] + ln(a("Pi")))
            - (mu["A"] + ln(a("A"))) - 4 * (mu["ATP"] + ln(a("ATP"))))  # fmt: skip
    y_R = (L_R * (mu["M"] + ln(a("M"))) - (L_R * mu["R_res"] + ln(a("R")))) / L_R
    y_P = (L_P * (mu["A"] + ln(a("A"))) - (L_P * mu["P_res"] + ln(a("P")))) / L_P
    x_rc = (mu["N"] + ln(a("N")) + 2 * (mu["ADP"] + ln(a("ADP")))
            - (mu["M"] + ln(a("M"))) - 2 * (mu["ATP"] + ln(a("ATP"))))  # fmt: skip
    return dict(x_tx=x_tx, x_tl=x_tl, y_R_per_residue=y_R, y_P_per_residue=y_P, x_rc=x_rc)


def derived():
    """The derived values the sheet types (§5), at the numeric test instance."""
    p, q = A1, A1M
    mu = test_instance_potentials()
    c1 = COPY_FMOL / p["V"]  # mM per copy
    c = dict(N=p["c_N"], M=p["c_M"], A=p["c_A"], ATP=p["c_ATP"], ADP=p["c_ADP"], Pi=p["c_Pi"],
             R=p["c_R"], P=p["c_P"])  # fmt: skip
    x = x_values(c, mu, int(p["L_R"]), int(p["L_P"]))
    r_tx, r_tl = p["L_R"] / p["m_tx"], p["L_P"] / p["m_tl"]
    phi_tx = sat(c["N"], p["K_N_tx"]) * (1 - exp(x["x_tx"]))
    phi_tl = sat(c["A"], p["K_A_tl"]) * sat(c["ATP"], p["K_ATP_tl"]) * (1 - exp(x["x_tl"]))
    f_on = p["c_X"] ** p["n_X"] / (p["K_X"] ** p["n_X"] + p["c_X"] ** p["n_X"])
    u1 = p["b_X"] + (1 - p["b_X"]) * f_on
    out = dict(
        RT_kJ_mol=RT,
        c_1=c1,
        mu_ATP=mu["ATP"],
        mu_N=mu["N"],
        mu_R_res=mu["R_res"],
        mu_P_res=mu["P_res"],
        r_tx=r_tx,
        r_tl=r_tl,
        kappa_tx=p["v_tx"] / r_tx,
        kappa_tl=p["v_tl"] / r_tl,
        x_tx=x["x_tx"],
        x_tl=x["x_tl"],
        y_R=x["y_R_per_residue"],
        y_P=x["y_P_per_residue"],
        x_rc=x["x_rc"],
        phi_tx=phi_tx,
        phi_tl=phi_tl,
        tau_tx=p["L_R"] / (p["v_tx"] * phi_tx),
        tau_tl=p["L_P"] / (p["v_tl"] * phi_tl),
        k0_R=p["k_R"] * (1 - exp(x["y_R_per_residue"])),
        k0_P=p["k_P"] * (1 - exp(x["y_P_per_residue"])),
        u_1=u1,
        lambda_tx=u1 * p["k_I_tx"] * c1 * p["T_copies"],
        beta_tl=p["k_I_tl"] * p["M_rib"] * c1,
    )
    # A1-M, polymerase-limited (N 5 mM; the other rows as A1's) and ribosome-limited (A 5 mM).
    cm = dict(c, N=q["c_N"])
    xm = x_values(cm, mu, int(p["L_R"]), int(p["L_P"]))
    phi_m = sat(cm["N"], p["K_N_tx"]) * (1 - exp(xm["x_tx"]))
    tau1 = p["L_R"] / (p["v_tx"] * phi_m)
    tau2 = q["L_2"] / (p["v_tx"] * phi_m)
    lam1 = q["k_I_tx"] * c1
    cr = dict(c, A=q["c_A"])
    xr = x_values(cr, mu, int(p["L_R"]), int(p["L_P"]))
    phi_r = sat(cr["A"], p["K_A_tl"]) * sat(cr["ATP"], p["K_ATP_tl"]) * (1 - exp(xr["x_tl"]))
    tau_r = p["L_P"] / (p["v_tl"] * phi_r)
    lam_r = q["k_I_tl"] * c1
    out |= dict(
        M_phi_tx=phi_m,
        M_tau_1=tau1,
        M_tau_2=tau2,
        M_lambda_1=lam1,
        M_lambda_tau_1=lam1 * tau1,
        M_phi_tl=phi_r,
        M_tau_rib=tau_r,
        M_lambda_rib=lam_r,
        M_lambda_tau_rib=lam_r * tau_r,
    )
    return out


# ------------------------------------------------------------------ check 6: the sheet's numbers


def _number(text):
    text = text.strip().replace("−", "-").replace("+", "").replace(" ", "")
    return text


def _marked(text, name):
    try:
        return text.split(f"<!-- {name} -->")[1].split(f"<!-- /{name} -->")[0]
    except IndexError:
        return None


def _table(block):
    rows = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|") or set(line) <= set("|- "):
            continue
        rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows[0], rows[1:]


def _cell(text, L_R, L_P, r_tx=150, r_tl=50):
    t = _number(text)
    if t == "":
        return 0
    sign = -1 if t.startswith("-") else 1
    t = t.lstrip("-")
    for name, value in (("L_R", L_R), ("L_P", L_P), ("r_tx", r_tx), ("r_tl", r_tl)):
        if t.endswith(name):
            k = t[: -len(name)]
            return sign * (int(k) if k else 1) * value
    return sign * int(t)


def _id(text):
    found = re.search(r"`([^`]+)`", text)
    return found.group(1) if found else text.strip()


def _digits_ok(typed, value):
    """|typed - value| within half a unit of the typed number's last digit."""
    t = _number(typed)
    mantissa = t.lower().split("e")[0]
    decimals = len(mantissa.split(".")[1]) if "." in mantissa else 0
    exponent = int(t.lower().split("e")[1]) if "e" in t.lower() else 0
    half_ulp = D(5) * D(10) ** (exponent - decimals - 1)
    return abs(D(t) - D(value)) <= half_ulp


def sheet_errors(path=SHEET):
    text, out = path.read_text(), []
    L_R, L_P = 1200, 400
    block = _marked(text, "moves")
    if block is None:
        return ["the sheet has no marked move matrix"]
    head, rows = _table(block)
    columns = [_id(h) for h in head[2:]]
    if columns != list(MOVE_IDS):
        out.append(f"the move matrix's columns are {columns}, not {list(MOVE_IDS)}")
    typed = {mv: {} for mv in columns}
    z = valences(L_R)
    for row in rows:
        s = _id(row[0])
        if s not in SPECIES:
            out.append(f"the move matrix names {s!r}")
            continue
        if _cell(row[1], L_R, L_P) != z[s]:
            out.append(f"{s}: typed valence {row[1]}, declared {z[s]}")
        for mv, cell in zip(columns, row[2:], strict=False):
            v = _cell(cell, L_R, L_P)
            if v:
                typed[mv][s] = v
    if typed != moves(L_R, L_P):
        out.append(f"the move matrix differs from this check's moves: {typed}")
    block = _marked(text, "moieties")
    if block is None:
        out.append("the sheet has no marked moiety table")
    else:
        head, rows = _table(block)
        species = [_id(h) for h in head[1:]]
        weights = {}
        for row in rows:
            name = _id(row[0]).replace(" ", "_")
            weights[name] = {
                s: _cell(cell, L_R, L_P)
                for s, cell in zip(species, row[1:], strict=False)
                if _cell(cell, L_R, L_P)
            }
        if weights != moieties(L_R, L_P):
            out.append(f"the moiety table differs: {weights}")
    block = _marked(text, "motion")
    if block is None:
        out.append("the sheet has no marked motion table")
    else:
        head, rows = _table(block)
        columns = [_id(h) for h in head[1:]]
        if columns != list(MOTION_COLUMNS):
            out.append(f"the motion table's columns are {columns}")
        typed = {c: {} for c in columns}
        for row in rows:
            amount = _id(row[0])
            for c, cell in zip(columns, row[1:], strict=False):
                v = _cell(cell, L_R, L_P)
                if v:
                    typed[c][amount] = v
        if typed != motion(L_R, L_P, 150, 50):
            out.append(f"the motion table differs from the moves composed: {typed}")
        out += [f"motion table: {e}" for e in motion_errors(typed, L_R, L_P, 150, 50)]
    values = entries_RT()
    block = _marked(text, "entries")
    if block is None:
        out.append("the sheet has no marked entries")
    else:
        head, rows = _table(block)
        col = next(i for i, h in enumerate(head) if "RT" in h)
        seen = set()
        for row in rows:
            key = _id(row[0])
            seen.add(key)
            if key not in values:
                out.append(f"entry {key!r} is not one of this check's")
            elif not _digits_ok(row[col], values[key]):
                out.append(f"entry {key}: typed {row[col]}, computed {values[key]:.8f}")
        if seen != set(values):
            out.append(f"the entries table has {sorted(seen)}")
    for name, table in (("a1", A1), ("a1m", A1M)):
        block = _marked(text, name)
        if block is None:
            out.append(f"the sheet has no marked table {name}")
            continue
        _, rows = _table(block)
        seen = set()
        for row in rows:
            key = _id(row[0])
            seen.add(key)
            if key not in table:
                out.append(f"{name}: {key!r} is not one of this check's parameters")
            elif D(_number(row[1])) != table[key]:
                out.append(f"{name}: {key} typed {row[1]}, declared here {table[key]}")
        if seen != set(table):
            out.append(f"{name}: the sheet types {sorted(seen)}, not {sorted(table)}")
    values = derived()
    block = _marked(text, "derived")
    if block is None:
        out.append("the sheet has no marked derived values")
    else:
        _, rows = _table(block)
        seen = set()
        for row in rows:
            key = _id(row[0])
            seen.add(key)
            if key not in values:
                out.append(f"derived: {key!r} is not one of this check's")
            elif not _digits_ok(row[1], values[key]):
                out.append(f"derived {key}: typed {row[1]}, computed {values[key]:.10g}")
        if seen != set(values):
            out.append(f"derived: the sheet types {sorted(seen)}, not {sorted(values)}")
    sweep = re.search(r"<!-- sweep -->(.*?)<!-- /sweep -->", text, re.S)
    if not sweep or [int(v) for v in re.findall(r"\d+", sweep.group(1))] != list(SWEEP):
        out.append(f"the sweep is not {list(SWEEP)}")
    return out


# ------------------------------------------------------------------ main


def check():
    report, ok = {}, True
    for name, part in (
        ("1_reduction", check_reduction),
        ("2_moieties", check_moieties),
        ("3_derivation", check_derivation),
        ("4_account", check_account),
        ("5_closed_forms", check_closed_forms),
    ):
        passed, entry = part()
        report[name] = dict(passed=bool(passed), **entry)
        ok &= passed
    errors = sheet_errors()
    report["6_sheet_numbers"] = errors or "agree"
    ok &= not errors
    plants = {}
    for name, (table, words) in motion_plants(1200, 400, 150, 50).items():
        found = [e for e in motion_errors(table, 1200, 400, 150, 50) if words in e]
        plants[name] = "caught" if found else "NOT CAUGHT"
        ok &= bool(found)
    report["6_motion_plants"] = plants
    return ok, report


def print_derived():
    """The values the sheet types, for its author (not a check)."""
    for key, value in entries_RT().items():
        print(f"entry {key}: {value:.10f}")
    for key, value in derived().items():
        print(f"{key}: {value:.15g}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", help="write the report as JSON here")
    parser.add_argument("--print-derived", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.print_derived:
        print_derived()
        return 0
    ok, report = check()
    text = json.dumps(dict(passed=bool(ok), report=report), indent=1, default=str)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text + "\n")
    print(text)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
