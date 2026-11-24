"""The judge's transcription of the spec folder (tag `fr38-v2-amendment-3-2026-11-24`).

Every value here is read from SPEC.md, its amendments, or the sheet sections LAWS.md names (the
sheet's §1.4 moieties and §5.1 table for arm B). None is taken from a reference file, so C0's
check of the references' echoed inputs is not circular.

- **The key names** of the expected inputs follow the references' echo (SPEC.md §7 shows only
  seven of them; the others are the references' own naming). The engine export's run definitions
  use the same vocabulary (`records.py`).
- **Profiles.** A family's rule set is its profile: `A` (AF, AN and the invented family), `B`, `C`
  and `D`. The tests pass invented families of each profile.
"""

import copy
import math

# ------------------------------------------------------------------ constants (SPEC.md §0)

N_A = 6.02214076e23  # mol⁻¹, exact (SI 2019)
K_B = 1.380649e-23  # J K⁻¹, exact (SI 2019)
R_GAS = N_A * K_B  # J mol⁻¹ K⁻¹, their double product (amendment 1, item 5)
T_K = 310.15
RT_J = R_GAS * T_K  # J/mol, fl(R · 310.15)
RT_KJ = RT_J / 1000.0  # kJ/mol: pJ per fmol
COPY_FMOL = 1e15 / N_A  # fmol per copy
C_STANDARD_MM = 1000.0  # c° = 1 M
EPS = 2.0**-52  # CRITERIA.md C2's ε
FLOOR_FMOL = 1e-22  # the operator's own ledger floor (CRITERIA.md C4)
REL_INPUT = 1e-12  # C0: definitions and echoed inputs, checked to 10⁻¹² relative
ACCURACY_FACTOR = 1e-11  # SPEC.md §3: accuracy ≤ 10⁻¹¹ s_y for judged values
SCALE_REL = 1e-12  # the reader's check of a stated scale against READOUTS.md §3
ULP_REL = 1e-14  # the reader's check of values the references publish twice (amendment 1)

assert COPY_FMOL == 1.6605390671738468e-09, "SPEC.md §0 states the double 1.6605390671738468e-09"

FATES = ("durable", "short_lived")
FATE_ROW = {"durable": "R", "short_lived": "R_s"}
CLASSES = ("resyn", "pool0", "pre", "win", "post")
H_STEP_S = 0.5  # the judged step h (CRITERIA.md §1); P3a/P3b are one such step late
PRIMARY_RUNGS = (2.0, 1.0, 0.5)  # 4h, 2h, h
RETRY_RUNGS = (1.0, 0.5, 0.25)  # the retry, judged at 0.25 s
PROFILES = ("A", "B", "C", "D")
FAMILY_PROFILE = {"AF": "A", "AN": "A", "B": "B", "C": "C", "D": "D"}
ARM_OF = {"AF": "A", "AN": "A", "B": "B"}  # C and D carry their own verdicts
REAL_FAMILIES = ("AF", "AN", "B", "C", "D")

# ------------------------------------------------------------------ the hold worlds (§1)

P_SCHED = [[0.0, 0.7], [2700.0, 0.25]]
P_BY_NAME = {"p=0": [[0.0, 0.0]], "p=1": [[0.0, 1.0]], "p_sched": P_SCHED}

_HOLD_RUNS = {
    "AF": [(p, m) for p in ("p=0", "p=1", "p_sched") for m in ("returned", "held")],
    "AN": [("p=0", "returned"), ("p=1", "returned"), ("p_sched", "returned"), ("p_sched", "held")],
    "C": [("p_sched", "returned")],
    "D": [("p_sched", "returned")],
}


def _constants():
    return {
        "N_A_per_mol": N_A,
        "k_B_J_per_K": K_B,
        "R_J_per_mol_K": R_GAS,
        "T_K": T_K,
        "RT_J_per_mol": RT_J,
        "c_standard_mM": C_STANDARD_MM,
        "copy_fmol": COPY_FMOL,
    }


def _hold_inputs(family):
    """SPEC.md §1.1 to §1.6 for AF, AN, C and D, as the references echo them."""
    an_like = family in ("AN", "C", "D")
    mu_res_declared = -10.368889 if an_like else 8.599269797012601  # §1.1
    mu_fate = -12442.6668 if an_like else 10319.123756415122  # §1.1: the literals, not products
    inp = {
        "H0_copies": 160,
        "K_N_mM": 0.02,
        "L_residues": 1200,
        "N_per_residue": 1,
        "Pi_per_residue": 2,
        "bath_mM": {"K": 140.0, "Y": 140.0},
        "bath_trace_mM": 1e-15,
        "bath_volume_pL": 1.0,
        "blank": {"H0_copies": 0, "k_I_per_mM_s": 0.0},
        "cell_background_mM": {"K": 140.0, "Y": 140.0},
        "constants": _constants(),
        "horizon_s": 14400.0,
        "initial_copies": {"R": 20, "R_s": 15},
        "initial_label_shares": {"pool0": 1.0},
        "initial_mM": {"N": 2.0, "M": 4.0e-3 if an_like else 0.05, "Pi": 5.0},
        "k_I_per_mM_s": 3.0e3,
        "k_d_per_s": 1 / 9000,  # the double 0.00011111111111111112
        "k_s_per_s": 1 / 1350,  # the double 0.0007407407407407407
        "label_schedule_s": {"pre": 0.0, "win": 1800.0, "post": 5400.0},
        "moieties": {
            "phosphorus": {"N": 3, "M": 1, "Pi": 1, "R": 1200, "R_s": 1200},
            "nucleoside": {"N": 1, "M": 1, "R": 1200, "R_s": 1200},
        },
        "mu0_RT_at_1M": {
            "N": 24.8672029410015,
            "M": 0.0,
            "Pi": 0.0,
            "R": mu_fate,
            "R_s": mu_fate,
        },
        "mu_res_RT": mu_fate / 1200,  # amendment 1, item 6: fl(μ°_R/L)
        "mu_res_declared_RT": mu_res_declared,
        "output_interval_s": 30.0,
        "p_sched": copy.deepcopy(P_SCHED),
        "patch_area_m2": 1e-10,
        "patch_solute_permeability": 0.0,
        "pool_machines_copies": 10000,
        "runs": {
            f"{p} {m}": {"machine": m, "p": copy.deepcopy(P_BY_NAME[p])}
            for p, m in _HOLD_RUNS[family]
        },
        "samples_s": [5400.0, 9000.0, 12600.0],
        "speed_nt_per_s": 50.0,
        "stages": 8,
        "tau_s": 2400.0,
        "template_copies": 1,
        "trace_mM": 1e-15,
        "volume_pL": 1.0,
        "window_s": [1800.0, 5400.0],
    }
    inp["runs"]["blank"] = {"H0_copies": 0, "k_I_per_mM_s": 0.0}  # its p and machine: no input
    if family == "C":  # §1.5
        inp["store"] = {
            "Mx_initial_mM": 1.0e-6,
            "Mx_moieties": {"nucleoside": 1, "phosphorus": 1},
            "forward_per_s_at_c0": 1 / 3000,  # the double 0.0003333333333333333
            "mu0_Mx_RT_at_1M": 0.0,
            "multiplier": 1.0,
            "network_c0_mM": 1.0,
            "network_mu0_RT_at_c0": {"M": math.log(1 / 1000), "Mx": math.log(1 / 1000)},
        }
    if family == "D":  # §1.6: the bath at 0.4 of §1.1's amounts
        inp["bath_mM"] = {"K": 56.0, "Y": 56.0}
        inp["bath_trace_mM"] = 4e-16
        inp["water"] = {
            "L_p_m_per_Pa_s": 2.8029294930351318e-14,
            "V_max_pL": 3.0,
            "V_min_pL": 0.5,
            "V_ref_pL": 1.0,
            "availability": 1.0,
            "bath_fraction_of_section_1_1": 0.4,
            "bath_pressure_Pa": 0.0,
            "bulk_modulus_Pa": 0.0,
            "impermeant_fmol": 0.0,
            "pressure_offset_Pa": 0.0,
        }
    return inp


def _b_inputs():
    """SPEC.md §2, with the sheet's §5.1 table and §1.4 moieties (A1 at its test instance)."""
    mu_r, mu_p = 10319.123756415122, 2336.405378810971
    return {
        "H0_copies": 0,
        "K_ATP_rc_mM": 0.1,
        "K_ATP_tl_mM": 0.02,
        "K_A_tl_mM": 0.02,
        "K_M_rc_mM": 0.1,
        "K_N_tx_mM": 0.02,
        "K_X_mM": 1.0e-3,
        "L_P_aa": 400,
        "L_R_nt": 1200,
        "M_pol_copies": 10000,
        "M_rib_copies": 1000000,
        "P_on_fmol_per_s": 2.0e-6,
        "V_C_mM_per_s": 0.01,
        "b_X": 0.02,
        "constants": _constants(),
        "horizon_s": 21600.0,
        "initial_label_shares": {"pool0": 1.0},
        "initial_mM": {
            "X": 1.0e-3,
            "N": 2.0,
            "M": 0.05,
            "A": 2.0,
            "ATP": 5.0,
            "ADP": 0.5,
            "Pi": 5.0,
            "R": 1.0e-12,
            "R_s": 1.0e-12,
            "P": 1.0e-12,
        },
        "k_I_per_mM_s": 1.2e4,  # transcription's, as SPEC.md §7's sample key
        "k_I_tl_per_mM_s": 120.0,
        "k_I_tx_per_mM_s": 1.2e4,
        "k_P_per_s": 5.0e-4,
        "k_X_per_s": 2.0e-3,
        "k_d_per_s": 1 / 8000,  # the double 0.000125
        "k_s_per_s": 1 / 1100,  # the double 0.0009090909090909091
        "label_schedule_s": {"pre": 0.0, "win": 2400.0, "post": 6000.0},
        "m_tl": 8,
        "m_tx": 8,
        "moieties": {
            "adenine": {"ATP": 1, "ADP": 1},
            "amino_acid": {"A": 1, "P": 400},
            "nucleoside": {"N": 1, "M": 1, "R": 1200, "R_s": 1200},
            "phosphorus": {"N": 3, "M": 1, "ATP": 3, "ADP": 2, "Pi": 1, "R": 1200, "R_s": 1200},
        },
        "mu0_RT_at_1M": {
            "ATP": 12.409206388416035,
            "ADP": 0.0,
            "Pi": 0.0,
            "N": 24.8672029410015,
            "M": 0.0,
            "A": 0.0,
            "R": mu_r,
            "R_s": mu_r,
            "P": mu_p,
        },
        "mu_res_P_RT": mu_p / 400,  # amendment 1, item 6
        "mu_res_R_RT": mu_r / 1200,
        "n_X": 2,
        "output_interval_s": 60.0,
        "p": 0.55,
        "p_sched": [[0.0, 0.55]],
        "runs": {f"p=0.55 {m}": {"machine": m, "p": [[0.0, 0.55]]} for m in ("held", "returned")},
        "samples_s": [6000.0, 9600.0, 13200.0],
        "t_end_s": 21600.0,
        "t_off_s": 10800.0,
        "tau_s": 1500.0,
        "template_copies": 1,
        "v_tl_aa_per_s": 16.0,
        "v_tx_nt_per_s": 50.0,
        "volume_pL": 1.0,
        "window_s": [2400.0, 6000.0],
    }


def spec_inputs(family):
    """SPEC.md's inputs for a registered family, in the references' echo vocabulary."""
    if family == "B":
        return _b_inputs()
    if family in _HOLD_RUNS:
        return _hold_inputs(family)
    raise KeyError(f"no registered family {family!r}")


# SPEC.md inputs the references' echo does not carry: structure, not numbers (reported, not
# a fault): one release class marked at release, the five labels, and the species' own label.
UNECHOED_STRUCTURE = (
    "the release's one class, marked at release",
    "the five label names",
    "the species' own label in force, resyn",
)


# ------------------------------------------------------------------ inputs, per family


def grid(inputs):
    """The output times t_i = Δ i, i = 0, …, horizon/Δ, as the inputs' doubles."""
    dt, horizon = float(inputs["output_interval_s"]), float(inputs["horizon_s"])
    n = int(round(horizon / dt))
    if n * dt != horizon:
        raise ValueError("the horizon is not a whole number of output intervals")
    return [dt * i for i in range(n + 1)]


def fate_rate(inputs, fate):
    return float(inputs["k_d_per_s"] if fate == "durable" else inputs["k_s_per_s"])


def residue_potential(inputs):
    """The residue's μ°/RT for transcription, fl(μ°_R/L) (amendment 1, item 6)."""
    return float(inputs["mu_res_R_RT"] if "mu_res_R_RT" in inputs else inputs["mu_res_RT"])


def chain_length(inputs):
    return int(inputs["L_R_nt"] if "L_R_nt" in inputs else inputs["L_residues"])


def pool_fmol(inputs, pool="pol"):
    key = {"pol": ("M_pol_copies", "pool_machines_copies"), "rib": ("M_rib_copies",)}[pool]
    for k in key:
        if k in inputs:
            return float(inputs[k]) * COPY_FMOL
    raise KeyError(f"no machine total for pool {pool}")


def run_p(inputs, run):
    """The run's durable-fraction schedule [[t, p], ...] from the inputs' run table."""
    return inputs["runs"][run].get("p")


def idle_fate(p_schedule):
    """SPEC.md §4: p = 0 idles the durable fate, p = 1 the short-lived one."""
    if p_schedule is None:
        return None
    ps = [float(p) for _, p in p_schedule]
    if all(p == 0.0 for p in ps):
        return "durable"
    if all(p == 1.0 for p in ps):
        return "short_lived"
    return None


# ------------------------------------------------------------------ the classes (SPEC.md §4)

BLANK_CONSTANT = [
    "H_tx_release",
    "int_Q_tx_release_durable",
    "int_Q_tx_release_short_lived",
    "H_rel_tx_release_durable",
    "H_rel_tx_release_short_lived",
    "int_Q_tx",
    "int_J_I_tx",
    "int_S_tx",
    "E_tx",
    "W_tx",
    "H_tx",
] + [f"C_tx_{j}" for j in range(1, 9)]


def constant_mask(name, times, window, *, blank, idle):
    """Where the reference's model is exactly +0.0 by its structure (SPEC.md §4, with amendment
    1's `released_present_gross`). `idle` is the run's idle fate, or None."""
    t = list(times)
    t1, t2 = window
    false = [False] * len(t)
    true = [True] * len(t)

    def class_mask(row, c):
        fate = "durable" if row == "R" else "short_lived"
        if blank or idle == fate:
            return true
        if c == "pre":
            return [x == 0.0 for x in t]
        if c == "win":
            return [x <= t1 for x in t]
        if c == "post":
            return [x <= t2 for x in t]
        return false

    if name.startswith("label_"):
        row, c = name[len("label_") :].rsplit("_", 1)
        if c in ("pre", "win", "post"):
            return class_mask(row, c)
        return false
    if name.startswith("released_present_gross_"):
        row = FATE_ROW[name[len("released_present_gross_") :]]
        masks = [class_mask(row, c) for c in ("pre", "win", "post")]
        return [a and b and c for a, b, c in zip(*masks, strict=True)]
    if blank and name in BLANK_CONSTANT:
        return true
    if idle is not None and name in (f"int_Q_tx_release_{idle}", f"H_rel_tx_release_{idle}"):
        return true
    return false


# ------------------------------------------------------------------ orders (CRITERIA.md C2)


def declared_order(profile, order_class):
    """p by profile and readout class. A: amounts, the hold, occupancies, extents, the excess and
    G at 3 (SSPRK(3,3)); heats at 2; labels, `released_present_gross` and survival at 2. B, C
    and D: every readout at 2 (Strang's split)."""
    if order_class == "none":
        return None
    if profile == "A":
        return 3 if order_class == "state" else 2
    return 2


ORDER_WINDOW_TOP = 3.5  # D271's window [p − 0.5, 3.5]

# ------------------------------------------------------------------ run requirements (§1)


def honest_runs(family_inputs):
    return [r for r in family_inputs["runs"] if r != "blank"]


def has_blank(profile):
    return profile != "B"


def blank_machines(family):
    """AF has a blank per machine option (CRITERIA.md §1); the others one blank, `returned`."""
    return ("returned", "held") if family == "AF" else ("returned",)


def twin_runs(family, family_inputs):
    """The unlabelled twins: of p_sched `returned` in the hold worlds, of each run in B."""
    if FAMILY_PROFILE.get(family) == "B":
        return honest_runs(family_inputs)
    return [r for r in honest_runs(family_inputs) if r == "p_sched returned"]


RESTART = {"AN": ("p_sched returned", 7200.0)}  # at h only

# ------------------------------------------------------------------ the plants (CRITERIA §6)

CORE_PLANTS = ("P1", "P1′", "P1″", "P2", "P3a", "P3b", "P4", "P5", "P6", "P7")
FAMILY_PLANTS = {"C": ("P8",), "D": ("P9",)}
PLANT_KIND = {
    "P1": "mapping",
    "P1′": "host",
    "P1″": "mapping",
    "P2": "world",
    "P3a": "world",
    "P3b": "world",
    "P4": "world",
    "P5": "world",
    "P6": "record",
    "P7": "world",
    "P8": "world",
    "P9": "host_record",
}

# Where each engine-record plant runs (family, run), and what it changes in the definition.
PLANT_RUNS = {
    "P2": [("AF", "p=1 returned")],
    "P3a": [("AN", "p_sched returned")],
    "P3b": [("AN", "p_sched returned")],
    "P4": [("AN", "p_sched returned"), ("B", "p=0.55 returned")],
    "P5": [("AF", "p_sched returned")],
    "P7": [("AF", "p_sched held")],
    "P8": [("C", "p_sched returned"), ("C", "blank")],
    "P9": [("D", "p_sched returned")],
}
# The judge's own plants and where they act: P1 and P1″ on the mapping, P6 and P1′ on copies of
# the honest records at h.
JUDGE_PLANT_FAMILIES = {"P1": ("AF", "AN"), "P1″": ("AF", "AN"), "P1′": ("AN",), "P6": ("AF",)}
P6_RUN = "p_sched returned"


# The "By" readouts of each plant (CRITERIA.md §6), with P8's negative control.
def plant_readouts(plant):
    rows = ("R", "R_s")
    if plant == "P1":
        return [f"label_{r}_win" for r in rows]
    if plant == "P1′":
        return [f"route2_{f}" for f in FATES]
    if plant == "P1″":
        return [f"excess_over_blank_{f}" for f in FATES]
    if plant == "P2":
        return ["int_Q_tx_release_short_lived", "H_rel_tx_release_short_lived"] + [
            f"label_R_s_{c}" for c in ("pre", "win", "post")
        ]
    if plant in ("P3a", "P3b", "P4"):
        return [f"label_{r}_win" for r in rows]
    if plant == "P5":
        return ["n_R_s", "int_D_R_s"] + [f"label_R_s_{c}" for c in CLASSES]
    if plant == "P6":
        return ["G_minus_G0"]
    if plant == "P7":
        return ["F_pol", "E_tx"]
    if plant == "P8":
        return [
            "n_M",
            "n_Mx",
            "excess_over_blank_durable",
            "excess_over_blank_short_lived",
            "label_R_resyn",
            "label_R_s_resyn",
        ]
    if plant == "P9":
        return (
            ["n_R", "n_R_s"]
            + [f"label_{r}_{c}" for r in rows for c in CLASSES]
            + ["H_rel_tx_release_durable", "H_rel_tx_release_short_lived", "G_minus_G0"]
        )
    raise KeyError(plant)


P8_NEGATIVE_CONTROL = [
    f"label_{r}_{c}" for r in ("R", "R_s") for c in ("pool0", "pre", "win", "post")
]

# The plants each family's reference must size (SPEC.md §6), checked by the reader.
REFERENCE_PLANTS = {
    "AF": ("P1", "P1″", "P2", "P5", "P6", "P7"),
    "AN": ("P1", "P1′", "P1″", "P3a", "P3b", "P4"),
    "B": ("P4",),
    "C": ("P8",),
    "D": ("P9",),
}

# The sizing expectations (CRITERIA.md §6), relative to s_y, reported beside the references.
SIZING_EXPECTATION = {"label": 2e-8, "amount": 1e-9, "G": 1e-8, "heat": 5e-8, "route2": 1e-5}
