"""The declared values of the equation sheet, transcribed by hand from its text.

Source: docs/TEMPLATED_POLYMERISATION_LAWS.md at tag gr1-sheet-2026-11-20 (read with
`git show gr1-sheet-2026-11-20:docs/TEMPLATED_POLYMERISATION_LAWS.md`). Nothing here is read
from engine code or from the sheet's own check. Section numbers are the sheet's.

The four potential symbols (§3.3) are the only free inputs: ΔG′°_ATP, E_pd and E_pep in kJ/mol,
and E_rc/RT. Every other value is declared by the sheet and fixed here.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from decimal import Decimal, localcontext

SHEET_TAG = "gr1-sheet-2026-11-20"
SHEET_PATH = "docs/TEMPLATED_POLYMERISATION_LAWS.md"

# §0 constants, as decimal strings (exact SI 2019 values; T declared).
N_A = "6.02214076e23"
K_B = "1.380649e-23"
T_KELVIN = "310.15"
KCAL_KJ = "4.184"  # §3.3: the thermochemical kcal
C_STANDARD_mM = 1000  # §0: c° = 1 M for every potential and entry

# §5.1, A1's table (units as the sheet's: pL, copies, nt, aa, s⁻¹, mM⁻¹ s⁻¹, mM, mM/s, fmol/s, s).
A1 = {
    "V": "1.0", "T_copies": 1, "L_R": 1200, "m_tx": 8, "v_tx": "50", "L_P": 400, "m_tl": 8,
    "v_tl": "16", "M_pol": "1e4", "M_rib": "1e6", "k_I_tx": "1.2e4", "k_I_tl": "120",
    "K_N_tx": "0.02", "K_A_tl": "0.02", "K_ATP_tl": "0.02", "V_C": "0.01", "K_M_rc": "0.1",
    "K_ATP_rc": "0.1", "k_R": "3.0e-3", "k_P": "5.0e-4", "K_X": "1.0e-3", "n_X": 2,
    "b_X": "0.02", "P_on": "2.0e-6", "k_X": "2.0e-3", "t_off": 10800, "t_end": 21600,
    "c_N": "2.0", "c_M": "0.05", "c_A": "2.0", "c_ATP": "5.0", "c_ADP": "0.5", "c_Pi": "5.0",
    "c_X": "1.0e-3", "c_R": "1.0e-12", "c_P": "1.0e-12",
    "dt_out": 60,  # §5.1: outputs every 60 s, at 0, 60, …, 21,600 s
}

# §5.2, A1-M's table. Every value not here is A1's.
A1M = {
    "M_pol": "100", "k_I_tx": "2.5e6", "L_2": 2400, "T_1": 10, "T_2": 5, "c_N": "5.0",
    "M_rib": "1000", "k_I_tl": "2.4e6", "c_A": "5.0", "t_end_pol": 3600, "t_end_rib": 600,
    "window_pol": 600, "window_rib": 120,
    "dt_pol": 30, "dt_rib": 10,  # §5.2: outputs every 30 s (polymerase-limited), 10 s (ribosome)
}
SWEEP_T = (1, 2, 5, 10, 20, 50, 100)  # §5.2: copy numbers of the polymerase-limited worlds
SWEEP_NR = (1, 2, 5, 10, 20, 50, 100)  # §5.2: held mRNA copies of the ribosome-limited worlds

# §1.4: moiety weights per molecule of the row (per residue for the residues in transit).
# 'L' marks the polymer's own length (L_R for each mRNA row, L_P for the protein).
MOIETIES = {
    "adenine": {"ATP": 1, "ADP": 1},
    "phosphorus": {"N": 3, "M": 1, "ATP": 3, "ADP": 2, "Pi": 1, "R": "L", "R_res": 1},
    "nucleoside": {"N": 1, "M": 1, "R": "L", "R_res": 1},
    "amino acid": {"A": 1, "P": "L", "P_res": 1},
}

# §5.6: the measured bounds, transcribed for comparison (the references do not use them to judge).
SHEET_BOUNDS = {
    "A1 n_R": ("2.5e-4", "A1, corner −25, −30, ±E_pep, +1"),
    "A1 n_P": ("5.1e-4", "A1, corner −25, −30, 0, +1"),
    "A1 E_tx": ("4.4e-4", "corner −25, −30, −25, −1"),
    "A1 E_tl": ("3.85e-4", "corner −25, −30, −25, +1"),
    "A1-M J": ("4.6e-5", "ribosome-limited n_R = 100, corner −40, −30, 0, −1"),
    "A1-M E": ("3.1e-5", "polymerase-limited T = 1, corner −25, −30, −25, +1"),
    "A1-M F": ("5.1e-5", "ribosome-limited n_R = 100, corner −40, −30, 0, −1"),
    "A1 interior": ("5.0e-4", "A1's largest gap over the 32 interior points"),
    "A1-M interior": ("5.1e-5", "A1-M's largest gap over the 32 interior points"),
    "x_max": ("-5.21", "ribosome-limited n_R = 1, corner −40, −30, 0, +1"),
}
EPS_A1 = 2e-3  # §5.1 / §5.6
EPS_M = 2e-4  # §5.2 / §5.6
X_DOM = -1.0  # §3.5, declared, uncited

# §6: the references' own tolerances.
TOL_TRAJECTORY = 1e-9  # second solve with tolerances 100× tighter: change ≤ 1e-9 of the scale
TOL_CLOSED_FORM = 1e-12  # closed forms evaluated to 1e-12 relative
TOL_IDENTITY = 1e-12  # identity residuals within 1e-12 of the scale (readings in the README)

# §6, R-noise's declared constants.
NOISE_REPLICATES = 1000
NOISE_BAND_SE = 4.5
NOISE_FLOOR = 10  # the floor is 10/N molecules
NOISE_MASTER_SEED = 20261120  # not declared by the sheet: the references' recorded reading

# §5.3's typed values (the sheet's derived table), transcribed to check this transcription.
TYPED_DERIVED = {
    "RT_kJ_mol": "2.578730581", "c_1": "1.660539067e-9", "mu_ATP": "12.40920639",
    "mu_N": "24.86720294", "mu_R_res": "8.599269797", "mu_P_res": "5.841013447", "r_tx": "150",
    "r_tl": "50", "kappa_tx": "0.3333333333", "kappa_tl": "0.32", "x_tx": "-20.64995978",
    "x_tl": "-67.98481385", "y_R": "-18.473975036", "y_P": "-11.969274604",
    "x_rc": "-0.8675005677", "phi_tx": "0.9900990088", "phi_tl": "0.9861543923",
    "tau_tx": "24.240000026", "tau_tl": "25.35100000", "k0_R": "0.0029999999716",
    "k0_P": "0.0004999968320", "u_1": "0.51", "lambda_tx": "1.016249909e-5",
    "beta_tl": "0.1992646881", "M_phi_tx": "0.9960159358", "M_tau_1": "24.09600001",
    "M_tau_2": "48.19200002", "M_lambda_1": "0.004151347668", "M_lambda_tau_1": "0.10003087345",
    "M_phi_tl": "0.9920477453", "M_tau_rib": "25.20040000", "M_lambda_rib": "0.003985293761",
    "M_lambda_tau_rib": "0.1004309969",
}

# §3.3's ranges of the four symbols, in the sheet's order.
RANGES = (
    ("G_ATP", -40.0, -25.0),  # ΔG′°_ATP, kJ/mol
    ("E_pd", -30.0, -15.0),  # kJ/mol
    ("E_pep", -25.0, 0.0),  # kJ/mol
    ("E_rc_RT", -1.0, 1.0),  # E_rc/RT, dimensionless
)
LHS_POINTS = 32
LHS_SEED = 20261120  # §5.6, Python's random.Random


@dataclass(frozen=True)
class Potentials:
    """The four symbols of §3.3. Energies in kJ/mol; E_rc in RT units (temperature-free).

    Values are kept as decimal strings so that the closed forms can be evaluated exactly.
    """

    label: str
    G_ATP: str
    E_pd: str
    E_pep: str
    E_rc_RT: str

    def as_float(self) -> dict:
        return {k: float(getattr(self, k)) for k in ("G_ATP", "E_pd", "E_pep", "E_rc_RT")}

    def as_dict(self) -> dict:
        return {"label": self.label, "G_ATP_kJ_mol": self.G_ATP, "E_pd_kJ_mol": self.E_pd,
                "E_pep_kJ_mol": self.E_pep, "E_rc_RT": self.E_rc_RT}


def _kcal(text: str) -> str:
    with localcontext() as ctx:
        ctx.prec = 50
        return str(Decimal(text) * Decimal(KCAL_KJ))


def _ln(text: str) -> str:
    with localcontext() as ctx:
        ctx.prec = 50
        return str(Decimal(text).ln())


# §3.3: the numeric test instance. ΔG′°_ATP = −32 kJ/mol (Wiseman et al. 2023), E_pd = −5.3
# kcal/mol (Dickson et al. 2000), E_pep = −3.6 kcal/mol (Martin 1998, via BioNumbers), and
# E_rc/RT = ln K_obs with K_obs = 1.05 (Lawson and Veech 1979).
TEST_INSTANCE = Potentials("test instance", "-32", _kcal("-5.3"), _kcal("-3.6"), _ln("1.05"))
# §5.6 / §3.3: the test instance with Spirin's E_pep, about −0.5 kcal/mol.
SPIRIN = Potentials("test instance, Spirin's E_pep", "-32", _kcal("-5.3"), _kcal("-0.5"),
                    _ln("1.05"))


def corners() -> list[Potentials]:
    """The 16 corners of §3.3's ranges, in the order G_ATP, E_pd, E_pep, E_rc/RT (low first)."""
    out = []
    for g in ("-40", "-25"):
        for pd in ("-30", "-15"):
            for pep in ("-25", "0"):
                for rc in ("-1", "1"):
                    out.append(Potentials(f"corner {g}, {pd}, {pep}, {rc}", g, pd, pep, rc))
    return out


def interior_points() -> list[Potentials]:
    """§5.6's interior Latin hypercube, under the references' reading of its call order.

    Reading (recorded in the README, an erratum candidate): for each symbol in the order
    ΔG′°_ATP, E_pd, E_pep, E_rc/RT, `random.shuffle` the 32 strata, then draw one `random()` per
    point k = 0, …, 31, in order, and place point k uniformly in the k-th shuffled stratum.
    """
    rng = random.Random(LHS_SEED)
    columns = []
    for _, lo, hi in RANGES:
        strata = list(range(LHS_POINTS))
        rng.shuffle(strata)
        width = (hi - lo) / LHS_POINTS
        columns.append([lo + (strata[k] + rng.random()) * width for k in range(LHS_POINTS)])
    return [Potentials(f"interior {k}", repr(columns[0][k]), repr(columns[1][k]),
                       repr(columns[2][k]), repr(columns[3][k])) for k in range(LHS_POINTS)]


def potential_sets() -> list[Potentials]:
    """§5.6's 50 sets: the test instance, Spirin's E_pep, 16 corners, 32 interior points."""
    return [TEST_INSTANCE, SPIRIN, *corners(), *interior_points()]


def edge_sets() -> list[Potentials]:
    """§5.6's 18 edge sets: the test instance, Spirin's E_pep and the 16 corners."""
    return [TEST_INSTANCE, SPIRIN, *corners()]


# gr1-sheet-2026-11-20b, §5.6 (erratum E3): the interior sample's 32 points, transcribed from
# its marked table <!-- interior -->. Columns: k, ΔG′°_ATP (kJ/mol), E_pd (kJ/mol), E_pep (kJ/mol),
# E_rc/RT. They equal interior_points() (this file's reading 6 of the first tag) value for value.
SHEET_TAG_B = "gr1-sheet-2026-11-20b"
PUBLISHED_INTERIOR = (
    (1, "-35.13975773013145", "-21.721949644970767", "-6.154455150921102", "-0.29785693923454026"),
    (2, "-36.54127768116361", "-26.752050614913355", "-15.197128815613524", "0.5456089236861184"),
    (3, "-29.98419545462147", "-20.656194681587557", "-6.782608085493223", "0.9393137990220466"),
    (4, "-26.398980868598375", "-21.326376034149895", "-13.478648954242942", "-0.688328604169324"),
    (5, "-25.211948032063084", "-23.175481305342956", "-16.80498535207805", "0.10842504676560472"),
    (6, "-39.88709082470815", "-27.785810270606127", "-10.71569076922908", "0.727052062493216"),
    (7, "-34.73576105048531", "-22.817912967000144", "-8.128742634437494", "-0.7916963763870569"),
    (8, "-39.29915819880178", "-28.376709917662065", "-1.8194409658777353", "-0.5317967578851917"),
    (9, "-25.59576104713534", "-25.263634971808226", "-10.132243337711985", "0.18150837066666048"),
    (10, "-36.07783946658932", "-18.02855044451871", "-13.068053766947019", "-0.9985757018290943"),
    (11, "-31.74396992590819", "-23.449109197608358", "-2.460262579232918", "0.7990221973996057"),
    (12, "-38.818770011919256", "-22.327651941235295", "-22.944583228712624", "0.4746375231928559"),
    (13, "-32.82077768062364", "-17.134477571023673", "-21.772811175283096", "-0.4900775794837112"),
    (14, "-30.400201190056915", "-18.636233571472065",
     "-18.567601058254592", "0.34821280337454374"),
    (15, "-37.43184843454623", "-20.4695435165393", "-22.206065865922973", "-0.6748820516763837"),
    (16, "-33.25801364400164", "-24.47955610443804", "-19.806640451691738", "0.5704747759389279"),
    (17, "-28.09256306160669", "-19.7619482049993", "-14.547349991861914", "-0.23171275311098538"),
    (18, "-27.170068074471352", "-25.368608603832833", "-11.844509675397777", "0.2586117856991028"),
    (19, "-30.747896716082963", "-26.368168209455785", "-0.3556963607514625", "-0.588487148316746"),
    (20, "-27.470216284367794", "-24.143964711197057", "-24.51826611085221", "0.0592439110223304"),
    (21, "-28.53471717317919", "-16.67803759935929", "-3.4090880819360905", "-0.9353098140538937"),
    (22, "-38.35167277031334", "-29.110295557211266", "-1.1631102525479484", "-0.3848106094725603"),
    (23, "-33.59534129521289", "-17.39332708252359", "-8.62823037904996", "0.6496385903969242"),
    (24, "-38.075303566164216", "-16.102721391158607", "-16.271493601001797", "0.9052006162180397"),
    (25, "-29.41599242096839", "-19.054950641189638", "-11.07503804975437", "0.1986293134764361"),
    (26, "-36.83510315549935", "-27.439181310865084", "-5.354535364562921", "-0.02873635914040973"),
    (27, "-29.18931382421533", "-28.80683628037275", "-24.049319235054217", "-0.8447099262415746"),
    (28, "-35.37327110026198", "-19.48297004996434", "-7.18538087186074", "0.41859168638357036"),
    (29, "-34.22076360340182", "-15.796891350326643",
     "-17.520477441658237", "-0.10759392115213473"),
    (30, "-32.162445234122806", "-29.556871512499367",
     "-19.142178300059634", "-0.18518655548867136"),
    (31, "-31.361965190864055", "-25.93441643556984",
     "-20.718454318927154", "-0.36842791551530396"),
    (32, "-26.863928361401182", "-15.001445037212326", "-4.151703340667915", "0.8652775587762509"),
)


def published_interior_points() -> list[Potentials]:
    """The 32 interior points as gr1-sheet-2026-11-20b publishes them (§5.6, erratum E3)."""
    return [Potentials(f"published interior {k}", g, pd, pep, rc)
            for k, g, pd, pep, rc in PUBLISHED_INTERIOR]
