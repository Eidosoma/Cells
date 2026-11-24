"""FR-38's second comparison, the code-blind references: every family's declared inputs.

Written from the spec folder alone (validation/gene_regulation/fr38_v2/spec/ at 0b771277: the
tagged 707014e4 plus AMENDMENT-2026-11-24.md) and the sheet sections LAWS.md names. Nothing here
is a result. Each value is the nearest double of the spec's decimal literal or stated expression
(SPEC.md section 0); the names carry their units.

Nothing in this package imports, runs or reads the engine.
"""

# SPEC.md section 0: constants.
N_A_PER_MOL = 6.02214076e23          # exact (SI 2019)
K_B_J_PER_K = 1.380649e-23           # exact (SI 2019)
T_K = 310.15
R_J_PER_MOL_K = N_A_PER_MOL * K_B_J_PER_K      # "their double product" (amendment 1, item 5)
RT_J_PER_MOL = R_J_PER_MOL_K * T_K             # fl(R * 310.15) (amendment 1, item 5)
COPY_FMOL = 1.6605390671738468e-09             # 10**15 / N_A, the double (SPEC.md section 0)
C_STANDARD_MM = 1000.0                         # c° = 1 M

assert COPY_FMOL == 1e15 / N_A_PER_MOL

P2_DURABLE_FRACTION = 1.0 - 2.0 ** -30         # SPEC.md section 6, P2
P5_FACTOR = 1.0 + 1e-4                         # SPEC.md section 6, P5
P8_FACTOR = 1.01                               # SPEC.md section 6, P8


def residue_potential(mu_row_rt, length):
    """A chain's residue potential: fl(mu°_row / L), in doubles (amendment 1, item 6)."""
    return mu_row_rt / length


def _constants():
    return {
        "N_A_per_mol": N_A_PER_MOL,
        "k_B_J_per_K": K_B_J_PER_K,
        "T_K": T_K,
        "R_J_per_mol_K": R_J_PER_MOL_K,
        "RT_J_per_mol": RT_J_PER_MOL,
        "copy_fmol": COPY_FMOL,
        "c_standard_mM": C_STANDARD_MM,
    }


# --------------------------------------------------------------------------------------------
# The hold worlds: families AF, AN, C and D (SPEC.md section 1)
# --------------------------------------------------------------------------------------------

_MU_ROW = {"AF": 10319.123756415122, "AN": -12442.6668, "C": -12442.6668, "D": -12442.6668}
_MU_RES_DECLARED = {"AF": 8.599269797012601, "AN": -10.368889, "C": -10.368889, "D": -10.368889}
_M_INITIAL_MM = {"AF": 0.05, "AN": 4.0e-3, "C": 4.0e-3, "D": 4.0e-3}

_HOLD_RUNS = {
    "AF": ["p=0 returned", "p=0 held", "p=1 returned", "p=1 held", "p_sched returned",
           "p_sched held"],
    "AN": ["p=0 returned", "p=1 returned", "p_sched returned", "p_sched held"],
    "C": ["p_sched returned"],
    "D": ["p_sched returned"],
}


def _p_of(run_name, p_sched):
    head = run_name.split(" ")[0]
    if head == "p=0":
        return [[0.0, 0.0]]
    if head == "p=1":
        return [[0.0, 1.0]]
    if head == "p_sched":
        return [list(x) for x in p_sched]
    raise ValueError(run_name)


def hold_family(name):
    """SPEC.md section 1, for family AF, AN, C or D, with amendment 1 applied."""
    if name not in _MU_ROW:
        raise ValueError(name)
    mu_row = _MU_ROW[name]
    length = 1200
    p_sched = [[0.0, 0.7], [2700.0, 0.25]]
    bath_fraction = 0.4 if name == "D" else 1.0
    inputs = {
        "constants": _constants(),
        "volume_pL": 1.0,
        "cell_background_mM": {"K": 140.0, "Y": 140.0},
        "bath_volume_pL": 1.0,
        "bath_mM": {"K": 140.0 * bath_fraction, "Y": 140.0 * bath_fraction},
        "bath_trace_mM": 1e-15 * bath_fraction,
        "trace_mM": 1e-15,
        "patch_area_m2": 1e-10,
        "patch_solute_permeability": 0.0,
        "initial_mM": {"N": 2.0, "M": _M_INITIAL_MM[name], "Pi": 5.0},
        "initial_copies": {"R": 20, "R_s": 15},
        "mu0_RT_at_1M": {"N": 24.8672029410015, "M": 0.0, "Pi": 0.0, "R": mu_row,
                         "R_s": mu_row},
        "mu_res_declared_RT": _MU_RES_DECLARED[name],
        "mu_res_RT": residue_potential(mu_row, length),
        "moieties": {"phosphorus": {"N": 3, "M": 1, "Pi": 1, "R": 1200, "R_s": 1200},
                     "nucleoside": {"N": 1, "M": 1, "R": 1200, "R_s": 1200}},
        "pool_machines_copies": 10000,
        "template_copies": 1,
        "L_residues": length,
        "stages": 8,
        "speed_nt_per_s": 50.0,
        "K_N_mM": 0.02,
        "N_per_residue": 1,
        "Pi_per_residue": 2,
        "k_I_per_mM_s": 3.0e3,
        "tau_s": 2400.0,
        "H0_copies": 160,
        "p_sched": p_sched,
        "k_d_per_s": 1 / 9000,
        "k_s_per_s": 1 / 1350,
        "label_schedule_s": {"pre": 0.0, "win": 1800.0, "post": 5400.0},
        "window_s": [1800.0, 5400.0],
        "initial_label_shares": {"pool0": 1.0},
        "horizon_s": 14400.0,
        "output_interval_s": 30.0,
        "samples_s": [5400.0, 9000.0, 12600.0],
        "blank": {"H0_copies": 0, "k_I_per_mM_s": 0.0},
        "runs": {},
    }
    assert inputs["k_d_per_s"] == 0.00011111111111111112
    assert inputs["k_s_per_s"] == 0.0007407407407407407
    if name == "C":
        inputs["store"] = {
            "Mx_initial_mM": 1.0e-6,
            "mu0_Mx_RT_at_1M": 0.0,
            "Mx_moieties": {"phosphorus": 1, "nucleoside": 1},
            "network_c0_mM": 1.0,
            "network_mu0_RT_at_c0": {"M": -6.907755278982137, "Mx": -6.907755278982137},
            "forward_per_s_at_c0": 1 / 3000,
            "multiplier": 1.0,
        }
        assert inputs["store"]["forward_per_s_at_c0"] == 0.0003333333333333333
    if name == "D":
        inputs["water"] = {
            "V_ref_pL": 1.0,
            "V_min_pL": 0.5,
            "V_max_pL": 3.0,
            "impermeant_fmol": 0.0,
            "bulk_modulus_Pa": 0.0,
            "pressure_offset_Pa": 0.0,
            "bath_pressure_Pa": 0.0,
            "bath_fraction_of_section_1_1": 0.4,
            "L_p_m_per_Pa_s": 2.8029294930351318e-14,
            "availability": 1.0,
        }
        assert inputs["bath_mM"]["K"] == 56.0
    for run in _HOLD_RUNS[name]:
        inputs["runs"][run] = {"p": _p_of(run, p_sched), "machine": run.split(" ")[1]}
    inputs["runs"]["blank"] = {"p": [[0.0, 0.0]], "machine": "returned", "H0_copies": 0,
                               "k_I_per_mM_s": 0.0}

    rows = []
    for run in _HOLD_RUNS[name]:
        rows.append(_hold_row(inputs, run, publish=True, blank="blank"))
    rows.append(_hold_row(inputs, "blank", publish=True, blank=None, is_blank=True))
    plants = {}
    if name == "AF":
        r = _hold_row(inputs, "P2 p=1 returned", publish=False, blank=None)
        r["p"] = [[0.0, P2_DURABLE_FRACTION]]
        r["machine"] = "returned"
        rows.append(r)
        r = _hold_row(inputs, "P5 p_sched returned", publish=False, blank=None)
        r["k_s"] = inputs["k_s_per_s"] * P5_FACTOR
        rows.append(r)
        plants = {"P1": True, "P1pp": True, "P2": "P2 p=1 returned",
                  "P5": "P5 p_sched returned", "P6": True, "P7": True}
    elif name == "AN":
        plants = {"P1": True, "P1p": True, "P1pp": True, "P3a": 1800.5, "P3b": 5400.5,
                  "P4": True}
    elif name == "C":
        kst = inputs["store"]["forward_per_s_at_c0"] * P8_FACTOR
        r = _hold_row(inputs, "P8 p_sched returned", publish=False, blank="P8 blank")
        r["k_store"] = kst
        rows.append(r)
        r = _hold_row(inputs, "P8 blank", publish=False, blank=None, is_blank=True)
        r["k_store"] = kst
        rows.append(r)
        plants = {"P8": "P8 p_sched returned"}
    elif name == "D":
        r = _hold_row(inputs, "P9 p_sched returned", publish=False, blank=None)
        r["gene_reads_V0"] = True
        rows.append(r)
        plants = {"P9": "P9 p_sched returned"}
    return {"family": name, "arm": "A", "store": name == "C", "water": name == "D",
            "inputs": inputs, "rows": rows, "plants": plants}


def _hold_row(inputs, run, publish, blank, is_blank=False):
    base = run.split(" ", 1)[1] if run.startswith("P") and not run.startswith("p") else run
    if is_blank:
        p, machine = [[0.0, 0.0]], "returned"
    else:
        p, machine = _p_of(base, inputs["p_sched"]), base.split(" ")[1]
    return {
        "name": run,
        "publish": publish,
        "is_blank": is_blank,
        "blank": blank,
        "p": p,
        "machine": machine,
        "H0_copies": 0 if is_blank else inputs["H0_copies"],
        "k_I": 0.0 if is_blank else inputs["k_I_per_mM_s"],
        "k_d": inputs["k_d_per_s"],
        "k_s": inputs["k_s_per_s"],
        "k_store": inputs.get("store", {}).get("forward_per_s_at_c0", 0.0),
        "gene_reads_V0": False,
    }


# --------------------------------------------------------------------------------------------
# Arm B: A1 with the release (SPEC.md section 2; the sheet's section 5.1 and 9.9's addendum)
# --------------------------------------------------------------------------------------------

def family_b():
    mu_r = 10319.123756415122
    mu_p = 2336.405378810971
    inputs = {
        "constants": _constants(),
        "volume_pL": 1.0,
        "template_copies": 1,
        "L_R_nt": 1200,
        "m_tx": 8,
        "v_tx_nt_per_s": 50.0,
        "L_P_aa": 400,
        "m_tl": 8,
        "v_tl_aa_per_s": 16.0,
        "M_pol_copies": 10000,
        "M_rib_copies": 1000000,
        "k_I_tx_per_mM_s": 1.2e4,
        "k_I_tl_per_mM_s": 120.0,
        "K_N_tx_mM": 0.02,
        "K_A_tl_mM": 0.02,
        "K_ATP_tl_mM": 0.02,
        "V_C_mM_per_s": 0.01,
        "K_M_rc_mM": 0.1,
        "K_ATP_rc_mM": 0.1,
        "k_P_per_s": 5.0e-4,
        "K_X_mM": 1.0e-3,
        "n_X": 2,
        "b_X": 0.02,
        "P_on_fmol_per_s": 2.0e-6,
        "k_X_per_s": 2.0e-3,
        "t_off_s": 10800.0,
        "t_end_s": 21600.0,
        "initial_mM": {"N": 2.0, "M": 0.05, "A": 2.0, "ATP": 5.0, "ADP": 0.5, "Pi": 5.0,
                       "X": 1.0e-3, "R": 1.0e-12, "P": 1.0e-12, "R_s": 1.0e-12},
        "mu0_RT_at_1M": {"ATP": 12.409206388416035, "ADP": 0.0, "Pi": 0.0,
                         "N": 24.8672029410015, "M": 0.0, "A": 0.0, "R": mu_r, "R_s": mu_r,
                         "P": mu_p},
        "mu_res_R_RT": residue_potential(mu_r, 1200),
        "mu_res_P_RT": residue_potential(mu_p, 400),
        "moieties": {
            "adenine": {"ATP": 1, "ADP": 1},
            "phosphorus": {"N": 3, "M": 1, "ATP": 3, "ADP": 2, "Pi": 1, "R": 1200, "R_s": 1200},
            "nucleoside": {"N": 1, "M": 1, "R": 1200, "R_s": 1200},
            "amino_acid": {"A": 1, "P": 400},
        },
        "tau_s": 1500.0,
        "p": 0.55,
        "H0_copies": 0,
        "k_d_per_s": 1 / 8000,
        "k_s_per_s": 1 / 1100,
        "label_schedule_s": {"pre": 0.0, "win": 2400.0, "post": 6000.0},
        "window_s": [2400.0, 6000.0],
        "initial_label_shares": {"pool0": 1.0},
        "horizon_s": 21600.0,
        "output_interval_s": 60.0,
        "samples_s": [6000.0, 9600.0, 13200.0],
        "runs": {"p=0.55 returned": {"p": [[0.0, 0.55]], "machine": "returned"},
                 "p=0.55 held": {"p": [[0.0, 0.55]], "machine": "held"}},
    }
    assert inputs["k_d_per_s"] == 0.000125
    assert inputs["k_s_per_s"] == 0.0009090909090909091
    rows = []
    for run in ("p=0.55 returned", "p=0.55 held"):
        rows.append({
            "name": run, "publish": True, "is_blank": False, "blank": None,
            "p": [[0.0, 0.55]], "machine": run.split(" ")[1], "H0_copies": 0,
            "k_I": inputs["k_I_tx_per_mM_s"], "k_d": inputs["k_d_per_s"],
            "k_s": inputs["k_s_per_s"], "k_store": 0.0, "gene_reads_V0": False,
        })
    return {"family": "B", "arm": "B", "store": False, "water": False, "inputs": inputs,
            "rows": rows, "plants": {"P4": True}}


# --------------------------------------------------------------------------------------------
# The invented family (SPEC.md section 8): every input invented, none of them this folder's
# --------------------------------------------------------------------------------------------

def family_invented():
    """Arm A's shape on invented inputs, for the writer's own test and the judge's first read."""
    mu_row = -12000.0
    length = 1200
    p_sched = [[0.0, 0.8], [150.0, 0.35]]
    inputs = {
        "constants": _constants(),
        "volume_pL": 1.0,
        "cell_background_mM": {"K": 140.0, "Y": 140.0},
        "bath_volume_pL": 1.0,
        "bath_mM": {"K": 140.0, "Y": 140.0},
        "bath_trace_mM": 1e-15,
        "trace_mM": 1e-15,
        "patch_area_m2": 1e-10,
        "patch_solute_permeability": 0.0,
        "initial_mM": {"N": 1.5, "M": 0.01, "Pi": 4.0},
        "initial_copies": {"R": 12, "R_s": 9},
        "mu0_RT_at_1M": {"N": 24.0, "M": 0.0, "Pi": 0.0, "R": mu_row, "R_s": mu_row},
        "mu_res_declared_RT": -10.0,
        "mu_res_RT": residue_potential(mu_row, length),
        "moieties": {"phosphorus": {"N": 3, "M": 1, "Pi": 1, "R": 1200, "R_s": 1200},
                     "nucleoside": {"N": 1, "M": 1, "R": 1200, "R_s": 1200}},
        "pool_machines_copies": 3000,
        "template_copies": 1,
        "L_residues": length,
        "stages": 8,
        "speed_nt_per_s": 25.0,
        "K_N_mM": 0.03,
        "N_per_residue": 1,
        "Pi_per_residue": 2,
        "k_I_per_mM_s": 5.0e4,
        "tau_s": 60.0,
        "H0_copies": 30,
        "p_sched": p_sched,
        "k_d_per_s": 1 / 400,
        "k_s_per_s": 1 / 50,
        "label_schedule_s": {"pre": 0.0, "win": 100.0, "post": 300.0},
        "window_s": [100.0, 300.0],
        "initial_label_shares": {"pool0": 1.0},
        "horizon_s": 600.0,
        "output_interval_s": 10.0,
        "samples_s": [300.0, 450.0, 570.0],
        "blank": {"H0_copies": 0, "k_I_per_mM_s": 0.0},
        "runs": {},
    }
    runs = ["p=0 returned", "p=1 returned", "p_sched returned", "p_sched held"]
    for run in runs:
        inputs["runs"][run] = {"p": _p_of(run, p_sched), "machine": run.split(" ")[1]}
    inputs["runs"]["blank"] = {"p": [[0.0, 0.0]], "machine": "returned", "H0_copies": 0,
                               "k_I_per_mM_s": 0.0}
    rows = [_hold_row(inputs, run, publish=True, blank="blank") for run in runs]
    rows.append(_hold_row(inputs, "blank", publish=True, blank=None, is_blank=True))
    r = _hold_row(inputs, "P2 p=1 returned", publish=False, blank=None)
    r["p"] = [[0.0, P2_DURABLE_FRACTION]]
    rows.append(r)
    r = _hold_row(inputs, "P5 p_sched returned", publish=False, blank=None)
    r["k_s"] = inputs["k_s_per_s"] * P5_FACTOR
    rows.append(r)
    plants = {"P1": True, "P1p": True, "P1pp": True, "P2": "P2 p=1 returned", "P3a": 100.5,
              "P3b": 300.5, "P4": True, "P5": "P5 p_sched returned", "P6": True, "P7": True}
    return {"family": "invented", "arm": "A", "store": False, "water": False,
            "inputs": inputs, "rows": rows, "plants": plants}


def family(name):
    if name in ("AF", "AN", "C", "D"):
        return hold_family(name)
    if name == "B":
        return family_b()
    if name == "invented":
        return family_invented()
    raise ValueError(name)


FAMILIES = ("AF", "AN", "B", "C", "D")
