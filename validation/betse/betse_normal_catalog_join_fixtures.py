"""Prepared explicit live ion inputs; no implicit or held calcium source."""

import json
from pathlib import Path

from validation.betse.betse_normal_pump_join_fixtures import fixture as pump_fixture


def class_entries():
    return json.loads(
        Path(__file__).with_name("betse_normal_catalog_join_inventory.json").read_text()
    )["classes"]


def fixture(class_name, *, steps=1):
    entry = class_entries()[class_name]
    data = pump_fixture()
    if type(steps) is not int or not 1 <= steps <= 3:
        raise ValueError("Prepared comparisons have one to three source calls")
    data["drives"] = data["drives"][:steps]
    definition = data["ion_definition"]
    initial = data["initial"]
    if entry["requires_live_calcium"]:
        # The earlier geometry fixture intentionally shares these lists. Give
        # the separately declared current axes their own input copies here.
        data["current_definition"]["ions"] = {
            key: list(value) for key, value in data["current_definition"]["ions"].items()
        }
        ions = definition["ions"]
        ions["ids"].append("Ca")
        ions["valence"].append(2.0)
        ions["moving_ids"].append("Ca")
        ions["membrane_diffusion_m2_s"].append([1e-16] * 9)
        ions["gap_diffusion_m2_s"].append([1e-10] * 9)
        # Explicit manufactured initial free cytosolic Ca and external Ca, mM.
        # These arrays evolve in both native and model; no per-call clamp occurs.
        calcium = [0.0001, 0.00012, 0.00009]
        initial["cell_mol_m3"].append(calcium)
        initial["membrane_mol_m3"].append([calcium[a] for a in definition["geometry"]["owner"]])
        initial["bath_mol_m3"].append(1.8)
        initial["membrane_flux_mol_m2_s"].append([0.0] * 9)
        initial["junction_flux_mol_m2_s"].append([0.0] * 9)
        for j, value in enumerate(calcium):
            initial["cell_mol_m3"][2][j] += 2 * value
        initial["membrane_mol_m3"][2] = [
            initial["cell_mol_m3"][2][a] for a in definition["geometry"]["owner"]
        ]
        data["current_definition"]["ions"]["ids"].append("Ca")
        data["current_definition"]["ions"]["valence"].append(2.0)
        data["voltage_definition"]["ions"]["free_diffusion_m2_s"].append(0.8e-9)
        calcium_handler = dict(
            alpha_Ca=0.0,
            Ca_dyn=0,
            provenance="Caller explicitly disables CaATP and ER; live free-Ca rows evolve",
        )
        data["initial_calcium_rate_proxy_mol_m2_s"] = [j * 1e-9 for j in range(9)]
    else:
        calcium_handler = None
        data["initial_calcium_rate_proxy_mol_m2_s"] = None
    data["channel_definition"] = dict(
        kind="cells.betse_normal_catalog_join_inputs@1",
        provenance="Prepared raw native population with explicit source profile indices",
        channels=[
            dict(
                id="population",
                class_name=class_name,
                targets=[8, 2, 8, 0, 4],
                maxDm_m2_s=2e-15,
                init_active=True,
            )
        ],
        calcium_handler=calcium_handler,
    )
    for drive in data["drives"]:
        drive["channels"] = dict(
            phase_kind="SIM",
            substances_affect_charge=True,
            modulators=dict(population=[0.4 + 0.02 * j for j in range(9)]),
        )
    return data


SINGULAR_NOMINAL_CASES = ("Cav_G",)
NONSINGULAR_CASES = ("Cav_G_nonsingular",)


def nonsingular_fixture(case_id):
    if case_id not in NONSINGULAR_CASES:
        raise ValueError("Require the separately declared nonsingular Cav_G case")
    data = fixture("Cav_G")
    # This is a new declared input, not a replacement for the failed nominal ID.
    # Keep the raw source equation and every acceptance budget unchanged.
    data["initial"]["voltage_V"][2] = -0.026
    return data


CASES = (
    "CaLeak",
    "Ca_L2",
    "Ca_L3",
    "CatLeak",
    "CatLeak2",
    "Cav1p2",
    "Cav1p3",
    "Cav2p1",
    "Cav2p2",
    "Cav2p3",
    "Cav3p1",
    "Cav3p3",
    "Cav_G",
    "Cav_L_ML",
    "Cav_L_ML2",
    "Cav_N_ML",
    "Cav_T_ML",
    "ClLeak",
    "HCN1",
    "HCN2",
    "HCN2_ML",
    "HCN2_cAMP",
    "HCN4",
    "HCN4_ML",
    "HCN4_cAMP",
    "HCNLeak",
    "KLeak",
    "K_Fast",
    "Kir2p1",
    "Kir_ML",
    "Kv1p1",
    "Kv1p2",
    "Kv1p3",
    "Kv1p3_ML",
    "Kv1p4",
    "Kv1p5",
    "Kv1p5S_ML",
    "Kv1p5_ML",
    "Kv1p6",
    "Kv2p1",
    "Kv2p1_ML",
    "Kv2p2",
    "Kv3p1",
    "Kv3p2",
    "Kv3p3",
    "Kv3p4",
    "Kv_ML1",
    "NaLeak",
    "Nav1p2",
    "Nav1p3",
    "Nav1p6",
    "NavRat1",
    "NavRat2",
    "NavRat3",
    "Nav_ML",
)
CARRIED_CASES = (
    "Nav1p2",
    "Kv3p3",
    "ClLeak",
    "Cav3p1",
    "HCN4_cAMP",
    "CatLeak",
    "Kv1p5S_ML",
    "HCN2_ML",
)
