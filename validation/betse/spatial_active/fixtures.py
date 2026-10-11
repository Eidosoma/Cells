"""Active static preparation from authenticated native setup and initial state."""

import numpy as np

from cells.numerics import betse_active as model
from cells.numerics import betse_spatial as passive
from cells.processes import kinetic_pump
from validation.betse.spatial_trajectory import fixtures as spatial


def prepare(row, trace, protocol):
    p, active = row["parameters"], row["fixture"]["active"]
    assert p["molecules_enabled"] and p["alpha_NaK"] == row["case"]["pump_density_mol_m2_s"]
    assert not any(
        p[k]
        for k in (
            "alpha_Ca",
            "Ca_dyn",
            "cell_polarizability",
            "grn_enabled",
            "fluid_flow",
            "fast_update_ecm",
        )
    )
    assert active["network_inventory"] == {
        "molecules": [],
        "reactions": [],
        "reactions_env": [],
        "transporters": [],
        "channels": ["Kv1p5_spatial"],
        "modulators": [],
    }
    assert active["channel_type"] == "Kv1p5" and active["channel_initial_active"]
    assert active["substances_affect_charge"]
    tissue = spatial.static_layout(row, protocol)
    shape = tissue.membrane_area.shape
    params = active["pump_parameters"]
    pump = kinetic_pump.Parameters(
        tissue.membrane_area * p["alpha_NaK"] * 1e15,
        *(
            np.full(shape, params[k])
            for k in ("cATP", "cADP", "cPi", "KmNK_Na", "KmNK_K", "KmNK_ATP", "deltaGATP")
        ),
    )
    layout = model.validate_layout(
        model.Layout(
            tissue,
            pump,
            np.asarray(row["species"]["Na"]),
            np.asarray(row["species"]["K"]),
            np.asarray(active["pump_availability"]),
            np.full(shape, active["channel_permeability_m_s"]),
        )
    )
    state = passive.initial_state(
        trace["initial_cc_cells"], trace["initial_cc_at_mem"], trace["initial_cc_env"], tissue
    )
    return model.initial_state(
        state, layout, trace["initial_m_gate"], trace["initial_h_gate"]
    ), layout


def arrays(states, rates, observed):
    return {
        **{"state__" + k: v for k, v in states.tissue._asdict().items()},
        **{"active__" + k: v for k, v in states._asdict().items() if k != "tissue"},
        "active__pump_cycles_fmol_s": rates.pump_cycles_fmol_s,
        "active__channel_inward_fmol_s": rates.channel_inward_fmol_s,
        **{"observed__" + k: v for k, v in observed.items()},
    }


def restore(saved):
    return model.State(
        passive.State(*(saved["state__" + k] for k in passive.State._fields)),
        *(saved["active__" + k] for k in model.State._fields[1:]),
    )
