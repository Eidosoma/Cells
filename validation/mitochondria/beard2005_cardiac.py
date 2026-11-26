"""Isolated cardiac mitochondria: the cited parameter sets of Beard 2005 and its 2006 correction.

An organism definition (D144; MITOCHONDRIA_DESIGN §3.5): species-specific numbers live here, never
in src/cells. Its consumers are the mitochondrial laws' declared equations
(docs/MITOCHONDRIA_LAWS_APPENDIX.md, which cites this file for every number), the appendix's own
check (appendix_check.py) and, later, MT-1's worlds.

Sources (both CC BY; read from the PDFs of record on 19-20 November 2026):
- Beard DA (2005), "A biophysical model of the mitochondrial respiratory system and oxidative
  phosphorylation", PLoS Comput Biol 1(4):e36, doi:10.1371/journal.pcbi.0010036. The mitochondria
  were isolated from rat heart (the data of Bose et al. 2003, which the paper fits).
- Beard DA (2006), "Correction: ...", PLoS Comput Biol 2(1):e8, doi:10.1371/journal.pcbi.0020008:
  a corrected Table 1, nothing else.

Only bare numbers with their place in the source are kept (D186, D227); the descriptions are ours.
The PDFs, their identities and our renders stay in the workspace (mito-lane-20261119: sources,
render and out/sources.json), never in the repository.

Reading notes (each checked at the typeset image, not a text layer):
- Table 1 in the 2005 PDF is the uncorrected table. The 2006 correction changes nine values
  (TABLE_1's `printed_2005` keeps the old one for each). The PDF of record therefore does not carry
  the corrected values, contrary to MITOCHONDRIA_DESIGN's correction note of 17 November.
- The sign of the ATP synthesis standard free energy: the text under Eq. 11 prints -36.03 kJ/mol,
  Table 2 prints +36.03 kJ/mol for H+ + ADP + Pi -> ATP. Eq. 11 uses it with the synthesis sign,
  which needs Table 2's +36.03 (a standard state that favours hydrolysis); the text's minus sign is
  the slip.
- Eq. 22's matrix proton balance in the PDF has -(4+1) J_C1, -(4-2) J_C3, -(2+2) J_C4,
  +(n_A - 1) J_F1, +2 J_PiHt, +J_Hle, -J_KH and +J_DH, consistent with Eqs. 2, 6, 8 and 10. The
  sentence after it still says complex III "consumes ... three" matrix protons, a leftover; the
  printed coefficients are the ones that agree with the reactions.
- Table 1 describes V_i as a fraction "per total cell volume"; with footnote f (matrix 90%, IMS 10%
  of the water) and V_x = 0.6435 it reads as per total mitochondrial volume.
- K_AK (Eqs. 17 and 18, IMS only) is on totals: the source's unprefixed [ATP]_i, [ADP]_i and
  [AMP]_i are totals (its f and m prefixes mark the Mg-free and Mg-bound parts; Eq. 22 moves the
  totals by J_AKi), and AMP binds nothing in the source. It is the equilibrium constant of the
  direction written, 2 ADP -> ATP + AMP: J_AKi = X_AK (K_AK [ADP]_i^2 - [AMP]_i [ATP]_i) > 0 makes
  ATP and AMP (Eq. 22: ATP_i +1, ADP_i -2, AMP_i +1 per J_AKi), so K_AK = [ATP][AMP]/[ADP]^2 at
  equilibrium; dimensionless, so free of any standard state. Table 1 footnote c: computed from
  Alberty 2003's tables, at conditions the source does not print. In base forms (ATP4-, ADP3-,
  AMP2-; no proton in the reaction) under the source's binding set it is K_AK (1 + [Mg]_i/K_MgADP)^2
  / (1 + [Mg]_i/K_MgATP), which depends on the free Mg2+ it is matched at: 0.153 at 1 mM, 0.389 at
  3.81 mM (a 5 mM Mg, 1.3 mM ADP buffer), 0.491 at 5 mM. The lead's ruling (D236) matches it at
  the state-3 buffer's free Mg2+, 3.808553529 mM (ak_match_free_Mg_mM), so K_base = 0.388964538
  (ak_base_constant), used at full precision: the binding owner's seam-E check admits that derived
  value only, not a rounded one.
- No temperature, gas constant or Faraday constant is printed. DECLARED below holds ours. The
  temperature is 298.15 K by the lead's ruling of 20 November 2026 (isolated-organelle worlds):
  the code-blind whole-organelle reference (MR1) reproduces the source's published curves at
  298.15 K (rms z 1.98) and not at 310.15 K (rms z 25.9). The appendix's first tag,
  mito-laws-appendix-2026-11-20, stated 310.15 K; the appendix now states 298.15 K.
- The user's repairs ruling (D236) is in RULED: frame B, Eq. 24 as phi_Pi x Eq. 7, the supply on
  a held neutral reductant pair at reference matrix pH 7.10, and the kinase in base forms.

Units are the source's: concentrations in M (mol per litre of the compartment's water) unless a
row says mM; fluxes in mol s^-1 per litre of total mitochondrial volume; potentials in mV with
Delta Psi = phi(outside of the inner membrane) - phi(matrix), positive at the operating point.
"""

import math
from typing import NamedTuple

SOURCES = {
    "beard2005": dict(
        authors=("Beard DA",),
        year=2005,
        title="A biophysical model of the mitochondrial respiratory system and oxidative "
        "phosphorylation",
        journal="PLoS Comput Biol 1(4):e36",
        doi="10.1371/journal.pcbi.0010036",
        licence="CC BY (as printed on the article)",
    ),
    "beard2006": dict(
        authors=("Beard DA",),
        year=2006,
        title="Correction: A biophysical model of the mitochondrial respiratory system and "
        "oxidative phosphorylation",
        journal="PLoS Comput Biol 2(1):e8",
        doi="10.1371/journal.pcbi.0020008",
        licence="CC BY (as printed on the article)",
    ),
}


class Value(NamedTuple):
    """One Table 1 parameter: the corrected values without and with the phosphate control of
    complex III (None where the column prints a dash), its printed unit, the equation(s) that use
    it, the source's class (A fitted, B literature, C set large), and the 2005 PDF's value where
    the correction changed it."""

    without_pi_control: float | None
    with_pi_control: float | None
    unit: str
    equations: str
    klass: str
    printed_2005: float | None = None


# Table 1 as corrected (beard2006, Table 1), checked against the image at 300 dpi.
TABLE_1 = {
    "r": Value(4.2530, 4.5807, "1", "1", "A"),
    "k_Pi1": Value(0.13890, 0.13413, "mM", "1", "A"),
    "k_Pi2": Value(0.62396, 0.67668, "mM", "1", "A"),
    "X_DH": Value(0.10990, 0.09183, "mol s-1 M-1 (L mito)-1", "1", "A"),
    "X_C1": Value(0.54088, 0.36923, "mol s-1 M-1 (L mito)-1", "3", "A"),
    "X_C3": Value(0.14483, 0.091737, "mol s-1 M-1 (L mito)-1", "7, 24", "A"),
    "X_C4": Value(2.2669e-5, 3.2562e-5, "mol s-1 M-1 (L mito)-1", "9", "A"),
    "X_F1": Value(154.82, 150.93, "mol s-1 M-2 (L mito)-1", "11", "A"),
    "X_ANT": Value(0.010723, 0.0079204, "mol s-1 (L mito)-1", "14", "A"),
    "X_PiHt": Value(3.7442e5, 3.3943e5, "mol s-1 M-1 (L mito)-1", "16", "A"),
    "k_PiHt": Value(0.72911, 0.45082, "mM", "16", "A"),
    "X_KH": Value(3.1775e7, 2.9802e7, "mol s-1 M-2 (L mito)-1", "21", "A", printed_2005=2.9802e-6),
    "X_K": Value(0.0, 0.0, "mol s-1 mV-1 M-1 (L mito)-1", "20", "A"),
    "X_Hle": Value(250.02, 250.00, "mol s-1 mV-1 M-1 (L mito)-1", "19", "A"),
    "k_Pi3": Value(None, 0.19172, "mM", "24", "A"),
    "k_Pi4": Value(None, 25.310, "mM", "24", "A"),
    "n_A": Value(3, 3, "1", "11, 22", "B"),
    "K_MgATP": Value(24.0e-6, 24.0e-6, "M", "11, 12", "B", printed_2005=1.0e-6),
    "K_MgADP": Value(347.0e-6, 347.0e-6, "M", "11, 12", "B", printed_2005=1.0e-6),
    "k_dH": Value(1.7783e-7, 1.7783e-7, "M", "15", "B", printed_2005=1.0e-6),
    "p_Pi": Value(327.0, 327.0, "um s-1", "13", "B"),
    "p_A": Value(85.0, 85.0, "um s-1", "13", "B"),
    "K_AK": Value(0.4331, 0.4331, "1", "18", "B"),
    "k_mADP": Value(3.5e-6, 3.5e-6, "M", "14", "B", printed_2005=1.0e-6),
    "k_O2": Value(1.20e-4, 1.20e-4, "M", "9", "B", printed_2005=1.0e-6),
    "NAD_tot": Value(2.97, 2.97, "mM", "23", "B"),
    "Q_tot": Value(1.35, 1.35, "mM", "23", "B"),
    "cytC_tot": Value(2.70, 2.70, "mM", "9, 23", "B"),
    "A_tot": Value(10.0, 10.0, "mM", "23", "B"),
    "V_x": Value(0.6435, 0.6435, "1", "22", "B"),
    "V_i": Value(0.0715, 0.0715, "1", "22", "B"),
    "gamma": Value(5.99, 5.99, "um-1", "13", "B"),
    "C_IM": Value(6.75e-6, 6.75e-6, "mol (L mito)-1 mV-1", "22", "B", printed_2005=1.0e-6),
    "X_AK": Value(1.0e6, 1.0e6, "mol s-1 M-2 (L mito)-1", "18", "C", printed_2005=1.0e-6),
    "X_MgA": Value(1.0e6, 1.0e6, "mol s-1 M-2 (L mito)-1", "12", "C", printed_2005=1.0e-6),
}
CORRECTED_BY_2006 = tuple(name for name, v in TABLE_1.items() if v.printed_2005 is not None)


def parameter(name, *, pi_control=True):
    """A Table 1 value in its printed unit: the column with complex III's phosphate control (the
    source's final model, Eq. 24) unless pi_control is False (Eq. 7)."""
    v = TABLE_1[name]
    return v.with_pi_control if pi_control else v.without_pi_control


class Reaction(NamedTuple):
    """A Table 2 reaction: its standard free energy (kJ/mol) at the source's reference (every
    species at 1 M, except H+ at 1e-7 M: "at pH = 7"), the source's scalar proton count (+:
    produced) and the turnover the value refers to."""

    dG0_kJ_mol: float
    scalar_protons: int
    turnover: str


# Table 2 (beard2005, p. 0258), read at 400 dpi. The C4 value is per 1/2 O2 (two electrons).
TABLE_2 = {
    "C1": Reaction(-69.37, -1, "H+ + NADH + Q -> NAD+ + QH2"),
    "C3": Reaction(-32.53, +2, "QH2 + 2 cytc(ox) -> Q + 2 cytc(red) + 2 H+"),
    "C4": Reaction(-122.94, -2, "2 H+ + 2 cytc(red) + 1/2 O2 -> 2 cytc(ox) + H2O"),
    "ATP": Reaction(+36.03, -1, "H+ + ADP + Pi -> ATP (Pi the sum of H2PO4- and HPO4 2-)"),
}
TEXT_SIGN_SLIP = {"ATP": -36.03}  # The text under Eq. 11 (p. 0255); see the module docstring.

# Stoichiometric facts the source prints (Eqs. 2, 6, 8, 10 and 22, and the text beside them).
PUMPED_PROTONS = {"C1": 4, "C3": 4, "C4": 2}  # Delta H+ per turnover of Table 2's reaction.
# Charges moved N to P per printed turnover, from dPsi/dt in Eq. 22.
CHARGES_MOVED = {"C1": 4, "C3": 2, "C4": 4, "F1": -3, "ANT": -1, "Hle": -1, "K": -1}
VOLTAGE_SHARES_ANT = (0.35, 0.65)  # Eq. 14: the exponents' shares on the IMS and matrix sides.
BUFFER_PER_M = 100.0  # Eq. 22's text: 1/r_buff = (100 M^-1) [H+]_x.

# The protocols the source simulates (beard2005 pp. 0258 and 0260).
PROTOCOL = dict(
    pH_external=7.1,  # [H+]_e = 10^-7.1 M
    K_external_mM=150.0,
    Mg_total_external_mM=5.0,
    ATP_external_mM=0.0,
    AMP_external_mM=0.0,
    ADP_external_mM=(0.0, 1.3),  # state 4, state 3
    Pi_external_mM=(0.0, 10.0),  # the swept range
    O2_matrix_M=2.6e-5,  # 20 mmHg, as the source states it for the matrix
    passive_K_and_Mg_fluxes=0.0,  # its best fits set them to zero
    low_O2_state3=dict(ADP_external_mM=1.0, ATP_external_mM=0.0, P50_uM=0.373, P50_mmHg=0.287),
    low_O2_cytc=dict(ADP_external_mM=0.5, ATP_external_mM=0.87, reduced_at_50uM_O2=0.14),
)

# Declared, uncited: what the equations need and the source does not print.
DECLARED = dict(
    # Not printed in the source. The lead's ruling (20 November 2026): 298.15 K, where the
    # code-blind reference reproduces the published curves (rms z 1.98; 25.9 at 310.15 K).
    temperature_K=298.15,
    gas_constant_J_mol_K=6.02214076e23 * 1.380649e-23,  # exact SI (N_A k_B)
    faraday_C_mol=6.02214076e23 * 1.602176634e-19,  # exact SI (N_A e)
    standard_concentration_M=1.0,  # every activity a = c / 1 M, H+ included
    # Valences (net charge at pH 7 of the forms the source names; only differences enter a law).
    valence=dict(
        H=1,
        K=1,
        Mg=2,
        ATP=-4,
        MgATP=-2,
        ADP=-3,
        MgADP=-1,
        AMP=-2,
        HPO4=-2,
        H2PO4=-1,
        NAD=-1,
        NADH=-2,
        Q=0,
        QH2=0,
        O2=0,
        cytc_ox=3,
        cytc_red=2,
        S_red=0,
        S_ox=0,
    ),  # fmt: skip
)

# The user's repairs ruling, D236 (20 November 2026), and the lead's rulings it carries.
RULED = dict(
    decision="D236",
    frame="B",  # base forms, every proton counted, phosphate's protons included in Eq. 22's row
    supply_reference_pH_N=7.10,  # the held reductant pair puts Eq. 1's target r at this matrix pH
    matrix_Mg_total_mM=5.0,
    ak_buffer=dict(Mg_total_mM=5.0, ADP_total_mM=1.3),  # the state-3 buffer K_AK is matched at
)

# Declared reactions beside Table 2's (pH-7 basis, kJ/mol, scalar protons produced).
DECLARED_REACTIONS = {
    # The supply's held neutral reductant pair (D236; the binding owner's set cells.potential_set.beard2005@1).
    "S": Reaction(0.0, +1, "S_red + NAD -> S_ox + NADH + H+ (declared)"),
}


def RT_J_mol(temperature_K=None):
    T = DECLARED["temperature_K"] if temperature_K is None else temperature_K
    return DECLARED["gas_constant_J_mol_K"] * T


def F_over_RT_per_mV(temperature_K=None):
    return DECLARED["faraday_C_mol"] / RT_J_mol(temperature_K) * 1e-3


def standard_free_energy_1M_kJ_mol(reaction, temperature_K=None):
    """A Table 2 value moved to every species at 1 M, H+ included: the source writes each scalar
    proton as RT ln([H+]/1e-7 M), so dG°(1 M) = dG°(pH 7) + nu_H RT ln(1e7), nu_H its scalar
    protons (+: produced). Exact for C1, C3 and C4, whose species bind no proton in the source."""
    r = TABLE_2[reaction]
    return r.dG0_kJ_mol + r.scalar_protons * RT_J_mol(temperature_K) * math.log(1e7) * 1e-3


def synthesis_base_form_1M_kJ_mol(temperature_K=None):
    """The synthesis free energy in base forms, ADP3- + HPO4 2- + H+ -> ATP4- + H2O, every species
    at 1 M: Table 2's value refers to total Pi, so it is matched to the base form at the source's
    reference pH 7 with the source's own k_dH: dG°(base) = dG°_ATP + RT ln(1e-7) -
    RT ln(1 + 1e-7 M / k_dH). A declared conversion (the appendix, law 2)."""
    rt = RT_J_mol(temperature_K)
    matched = rt * math.log(1e-7) - rt * math.log1p(1e-7 / parameter("k_dH"))
    return (TABLE_2["ATP"].dG0_kJ_mol * 1e3 + matched) * 1e-3


def per_oxygen_1M_kJ_mol(temperature_K=None):
    """Complex IV per O2 (four electrons): twice Table 2's per-1/2-O2 value at 1 M."""
    return 2.0 * standard_free_energy_1M_kJ_mol("C4", temperature_K)


def quinol_oxygen_per_O2_kJ_mol():
    """The lumped QH2:O2 cycle per O2 (host C's reduction): 2 QH2 + O2 -> 2 Q + 2 H2O. Twice
    (C3 + C4); its scalar protons cancel, so the pH-7 and 1 M values agree."""
    return 2.0 * (TABLE_2["C3"].dG0_kJ_mol + TABLE_2["C4"].dG0_kJ_mol)


def held_pair_ratio(*, pi_control=True):
    """[S_ox]/[S_red] of the supply's held pair (D236): the balanced supply's equilibrium is the
    source's [NADH]/[NAD] = r at the reference matrix pH, so with dG°(pH 7) = 0 it is
    10^(pH_ref - 7) / r."""
    return 10.0 ** (RULED["supply_reference_pH_N"] - 7.0) / parameter("r", pi_control=pi_control)


def ak_match_free_Mg_mM():
    """The free Mg2+ at which K_AK (on totals) is matched to base forms (the lead's ruling,
    D236): that of the source's state-3 buffer, 5.0 mM total Mg with 1.3 mM ADP and no ATP, ADP
    binding Mg with K_MgADP (the only Mg binder there): m + A m/(K + m) = M_tot, the positive
    root of m^2 + (K + A - M_tot) m - K M_tot = 0, in mM."""
    k = parameter("K_MgADP") * 1e3
    total, adp = RULED["ak_buffer"]["Mg_total_mM"], RULED["ak_buffer"]["ADP_total_mM"]
    b = k + adp - total
    return (-b + math.sqrt(b * b + 4.0 * k * total)) / 2.0


def ak_base_constant(free_Mg_mM=None):
    """Eq. 18's constant in base forms, [ATP4-][AMP2-]/[ADP3-]^2 at equilibrium, from K_AK on
    totals under the source's binding set (Mg on ATP and ADP only): K_AK (1 + m/K_MgADP)^2 /
    (1 + m/K_MgATP), at the matched free Mg2+ unless another is given."""
    m = (ak_match_free_Mg_mM() if free_Mg_mM is None else free_Mg_mM) * 1e-3
    return parameter("K_AK") * (1 + m / parameter("K_MgADP")) ** 2 / (1 + m / parameter("K_MgATP"))


ZERO_REFERENCES = ("H", "K", "Mg", "O2", "NAD", "Q", "cytc_ox", "ADP", "HPO4", "S_ox")


def standard_potentials_RT(temperature_K=None):
    """mu°/RT at 1 M of every species and form (the binding owner's convention for the named set
    cells.potential_set.beard2005@1, extended with AMP for @2): ZERO_REFERENCES at 0, water never a row; then each
    reaction determines one species, in this order, from its pH-7 value moved to 1 M:
    complex IV per O2 -> cytc_red, III -> QH2, I -> NADH, synthesis (total Pi's term included)
    -> ATP, the supply's declared reaction -> S_red, adenylate kinase (K_base) -> AMP; the forms
    from their dissociation constants, mu°_f = mu°_base + sum n mu°_L + ln K_d (K_d in M)."""
    rt = RT_J_mol(temperature_K)
    ln7 = math.log(1e7)

    def x(reaction, table=TABLE_2, multiple=1.0):
        r = table[reaction]
        return multiple * (1000.0 * r.dG0_kJ_mol / rt + r.scalar_protons * ln7)

    mu = dict.fromkeys(ZERO_REFERENCES, 0.0)
    mu["cytc_red"] = -x("C4", multiple=2.0) / 4.0
    mu["QH2"] = 2.0 * mu["cytc_red"] - x("C3")
    mu["NADH"] = mu["QH2"] - x("C1")
    mu["ATP"] = x("ATP") - math.log1p(1e-7 / parameter("k_dH"))
    mu["S_red"] = mu["NADH"] - x("S", DECLARED_REACTIONS)
    mu["AMP"] = -math.log(ak_base_constant()) - mu["ATP"]
    mu["MgATP"] = mu["ATP"] + math.log(parameter("K_MgATP"))
    mu["MgADP"] = mu["ADP"] + math.log(parameter("K_MgADP"))
    mu["H2PO4"] = mu["HPO4"] + math.log(parameter("k_dH"))
    return mu


def matrix_buffer_capacity_M():
    """Eq. 22's buffering, d[H+]_bound / d ln[H+]_free = [H+] r_buff = 1 / (100 M^-1) = 0.01 M,
    independent of pH: a constant capacity per ln unit. A single declared buffer species of total
    B_T at pK = pH matches it at its centre when B_T / 4 = 0.01 M (departure D2: the species'
    capacity falls away from its pK)."""
    return 1.0 / BUFFER_PER_M


def capacity_fmol_s(flux_mol_s_per_L_mito, mito_volume_L):
    """A population's capacity (fmol cycles/s) from a source flux scale in mol s^-1 (L mito)^-1
    and the mitochondrial volume it represents (L): the world supplies the volume."""
    return flux_mol_s_per_L_mito * mito_volume_L * 1e15
