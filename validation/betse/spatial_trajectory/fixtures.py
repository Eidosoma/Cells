"""Authenticated native initial states and static inputs, never evolving forcing."""

import hashlib
import json
from pathlib import Path

import numpy as np

from cells.numerics import betse_spatial as model
from cells.processes.electrochemistry import F, R
from tests.unit.test_betse_tissue_contact import load_capture

PROTOCOL_PATH = Path(__file__).with_name("protocol.json")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture():
    binding = json.loads(PROTOCOL_PATH.read_text())["native_binding"]
    root = Path(binding["root"])
    assert digest(root / "completion.json") == binding["completion_sha256"]
    done = json.loads((root / "completion.json").read_text())
    assert done["status"] == "completed"
    assert digest(root / "result.json") == done["result_sha256"]
    name = "evidence/cpu/native/panel.json"
    assert digest(root / name) == done["evidence_sha256"][name]
    protocol = json.loads((root / name).read_text())["protocol"]
    return load_capture(root / "evidence/cpu/native", protocol), protocol


def prepare(row, trace, protocol):
    p = row["parameters"]
    assert p["F"] == F and p["R"] == R
    assert p["is_ecm"] and p["sharpness"] == 1
    assert not any(
        p[k]
        for k in (
            "Ca_dyn",
            "alpha_NaK",
            "alpha_Ca",
            "cell_polarizability",
            "fluid_flow",
            "fast_update_ecm",
            "molecules_enabled",
            "grn_enabled",
        )
    )
    layout = static_layout(row, protocol)
    initial = model.initial_state(
        trace["initial_cc_cells"],
        trace["initial_cc_at_mem"],
        trace["initial_cc_env"],
        layout,
    )
    return initial, layout


def static_layout(row, protocol):
    """Static passive geometry/transport inputs, also shared by active composition."""
    p, g, a = row["parameters"], row["geometry"], row["arrays"]
    assert p["F"] == F and p["R"] == R
    assert p["is_ecm"] and p["sharpness"] == 1
    shape = np.asarray(g["X"]).shape
    species, patches = len(a["zs"]), len(g["mem_sa"])
    boundary = np.zeros(shape)
    b = row["fixture"]["boundary_voltage_V"]
    boundary[:, 0], boundary[:, -1] = b["L"], b["R"]
    boundary[-1, :], boundary[0, :] = b["T"], b["B"]
    mem_open = np.ones(patches)
    if not p["cluster_open"]:
        mem_open[g["bflags_mems"]] = 0
    gj_open = np.asarray(row["fixture"]["after_setup"]["gj_block"]) * g["gj_default_weights"]
    gj_open[g["bflags_mems"]] = 0
    layout = model.validate_layout(
        model.Layout(
            np.asarray(g["cell_vol"]),
            np.asarray(g["mem_sa"]),
            np.asarray(g["mem_to_cells"], dtype=np.int64),
            np.asarray(g["map_mem2ecm"], dtype=np.int64),
            np.asarray(g["nn_i"], dtype=np.int64),
            np.isin(np.arange(species), row["fixture"]["moving_ions"]),
            np.asarray(a["zs"]),
            np.asarray(a["Dm_cells"]) / p["tm"],
            np.asarray(a["D_gj"]) * protocol["gj_surface_fraction"] / g["gj_len"],
            mem_open,
            gj_open,
            (np.asarray(a["D_env"]) * a["TJ_modulator"]).reshape((species, *shape)),
            np.asarray(a["c_env_bound"]),
            boundary,
            np.asarray(a["extra_rho_cells"]),
            np.asarray(a["extra_rho_env"]),
            np.asarray(g["delta"]),
            np.asarray(p["cell_height"]),
            np.asarray(p["T"]),
            np.asarray(p["cm"]),
            np.asarray(a["ko_env"]),
            np.asarray(p["eo"] * p["er"]),
            np.asarray(p["cell_radius"] / p["true_cell_size"]),
            np.asarray(p["q"] / p["kb"]),
        )
    )
    return layout


def comparison(state, rates, field, layout):
    """Native observable names, with explicit units and oriented flux conversion."""
    return dict(
        cc_cells=state.cell_concentration,
        cc_at_mem=state.membrane_concentration,
        cc_env=state.outside_concentration,
        vm=field.membrane_voltage_V,
        vm_ave=field.cell_mean_voltage_V,
        rho_cells=field.cell_charge_density,
        Phi_b=field.boundary_potential_V.ravel(),
        v_env=field.outside_potential_V.ravel(),
        E_env_x=field.outside_field_x_V_m,
        E_env_y=field.outside_field_y_V_m,
        fluxes_mem=rates.membrane_inward_fmol_s / layout.membrane_area * 1e-15,
        fluxes_gj=rates.junction_outward_fmol_s / layout.membrane_area * 1e-15,
        fluxes_env_x=rates.outside_flux_x_mol_m2_s.reshape(state.outside_concentration.shape),
        fluxes_env_y=rates.outside_flux_y_mol_m2_s.reshape(state.outside_concentration.shape),
    )
