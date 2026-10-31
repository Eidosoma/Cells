"""Transitioned SIM NaK producer before movers, using the existing exact arithmetic.

The material seam receives this producer's flux, never arbitrary supplied pump
flux. Maintained-pool kinetics and raw rate proxy retain the native convention.
"""

from types import SimpleNamespace

import numpy as np

from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_normal_pump_join as common

PARAMETERS = dict(
    cATP=1.5, cADP=0.1, cPi=0.1, KmNK_Na=12.0, KmNK_K=0.2, KmNK_ATP=0.5, deltaGATP=-37000.0
)


def view(binding):
    mb = binding.material_binding
    cb = mb.geometry_binding.current_binding
    names = list(cb.ion_ids)
    kernel = common.Kernel(
        names.index("Na"),
        names.index("K"),
        *(
            PARAMETERS[key]
            for key in ("cATP", "cADP", "cPi", "KmNK_Na", "KmNK_K", "KmNK_ATP", "deltaGATP")
        ),
    )
    constants = SimpleNamespace(R_J_mol_K=mb.kernel.R_J_mol_K, F_C_mol=cb.kernel.F_C_mol)
    return SimpleNamespace(
        kernel=kernel,
        gated_binding=SimpleNamespace(material_binding=SimpleNamespace(kernel=constants)),
    )


def produce(binding, parent, stores, incoming_rate, observer=None):
    mb = binding.material_binding
    cb, g = mb.geometry_binding.current_binding, mb.geometry_binding.geometry
    names = list(cb.ion_ids)
    na, potassium = names.index("Na"), names.index("K")
    v = parent.values
    m = len(cb.membrane_ids)
    packet = common.Packet(
        binding.inputs_raw["flags"]["alpha_NaK"],
        np.broadcast_to(stores["NaKATP_block"], (m,)).copy(),
        np.broadcast_to(stores["rho_pump"], (m,)).copy(),
        None,
    )
    reset_values = {key: np.array(value, copy=True) for key, value in v._asdict().items()}
    for key in (
        "membrane_flux_mol_m2_s",
        "junction_flux_mol_m2_s",
        "environment_flux_x_mol_m2_s",
        "environment_flux_y_mol_m2_s",
    ):
        reset_values[key].fill(0)
    before = dict(
        mode="nak",
        definition=ions.data(binding.inputs["definition"]),
        values_before=reset_values,
        parameters=PARAMETERS,
        packet=packet._asdict(),
        incoming_rate=ions.data(incoming_rate),
        runtime_temperature_K=stores["T"],
        boundary=mb.kernel.boundary,
        cluster_open=mb.kernel.cluster_open,
        source_phase="SIM",
        legacy_run_sim=True,
    )
    if observer is not None:
        observer(ions.freeze(before))
    flux = np.zeros_like(v.membrane_flux_mol_m2_s)
    arithmetic = None
    proxy = np.zeros(m)
    with np.errstate(all="ignore"):
        if packet.alpha_NaK > 0:
            arithmetic = common._arithmetic(
                view(binding),
                v.membrane_mol_m3[na],
                v.environment_mol_m3[na][g.membrane_to_grid],
                v.membrane_mol_m3[potassium],
                v.environment_mol_m3[potassium][g.membrane_to_grid],
                v.voltage_V,
                stores["T"],
                packet,
            )
            proxy = arithmetic.raw_rate_proxy_mol_m2_s
            flux[na] = packet.rho_pump * arithmetic.raw_sodium_flux_mol_m2_s
            flux[potassium] = packet.rho_pump * arithmetic.raw_potassium_flux_mol_m2_s
            if not mb.kernel.cluster_open:
                flux[na, mb.kernel.boundary] = 0
                flux[potassium, mb.kernel.boundary] = 0
    result = ions.freeze(
        dict(
            before=before,
            arithmetic=None if arithmetic is None else arithmetic._asdict(),
            applied_flux=flux,
            raw_rate_proxy=proxy,
            source_completed=True,
        )
    )
    return result, ions.freeze(flux), ions.freeze(proxy)


def finite(result):
    groups = [result["applied_flux"], result["raw_rate_proxy"]]
    if result["arithmetic"] is not None:
        groups.extend(result["arithmetic"].values())
    return all(np.isfinite(np.asarray(v)).all() for v in groups)
