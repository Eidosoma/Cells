"""Independent scalar/Decimal kinetics, full-node roots and adaptive trajectories.

No Cells/JAX imports. The full-node root, capacitor derivative and material
assembly differ from the production reduced solver and scatter implementation.
"""

from decimal import Decimal, localcontext
from numbers import Real

import numpy as np
from scipy.integrate import solve_ivp

from validation.betse.pump_contact.pump_reference import oracle as pump_oracle
from validation.betse.voltage_gate_audit.gate_independent import kinetics as channel_kinetics
from validation.channels import (
    calcium_activated_potassium_reference,
    calcium_catalog_extra_reference,
    hcn_extra_reference,
    leak_channels_reference,
    morris_lecar_channels_reference,
    potassium_catalog_reference,
    sodium_catalog_reference,
)
from validation.tissue import (
    cav_reference,
    hcn_reference,
    kir_reference,
    kv1_reference,
    sodium_reference,
)
from validation.tissue import surface_dynamics_reference as base
from validation.tissue import surface_field_reference as electrical
from validation.tissue import surface_reference as transport

F, R = transport.F, transport.R
flatten, unpack = base.flatten, base.unpack
SHARED_MODELS = (
    "resolved_tissue@5",
    "resolved_tissue@6",
    "resolved_tissue@7",
    "resolved_tissue@8",
    "resolved_tissue@9",
    "resolved_tissue@10",
    "resolved_tissue@11",
    "resolved_tissue@12",
)
CATALOG_MODEL = "resolved_tissue@8"
CATALOG_V2_MODEL = "resolved_tissue@9"
CATALOG_V3_MODEL = "resolved_tissue@10"
CATALOG_V4_MODEL = "resolved_tissue@11"
CATALOG_V5_MODEL = "resolved_tissue@12"
CATALOG_MODELS = (
    CATALOG_MODEL,
    CATALOG_V2_MODEL,
    CATALOG_V3_MODEL,
    CATALOG_V4_MODEL,
    CATALOG_V5_MODEL,
)
HCN_EXTRA_LAWS = {
    "betse_hcn_leak_open@1": "HCNLeak",
    "betse_hcn2_camp_m@1": "HCN2_cAMP",
    "betse_hcn4_camp_m@1": "HCN4_cAMP",
}
HCN_LEAK_LAW = "betse_hcn_leak_open@1"
CALCIUM_ACTIVATED_LAW = "betse_cagpotassium_numeric_mM_scale@1"
# Literal law correspondence, independent of the production numeric dispatcher.
ADDED_SODIUM_LAWS = {
    "betse_nav1p3_m3h_regularized@1": "Nav1p3",
    "betse_navrat2_m3h_regularized@1": "NavRat2",
    "betse_navrat1_m3h_regularized@1": "NavRat1",
    "betse_navrat3_m3h_regularized@1": "NavRat3",
    "betse_naleak_always_open@1": "NaLeak",
    "betse_nav1p6_persistent_m@1": "Nav1p6",
}
ADDED_POTASSIUM_LAWS = {
    "betse_kv2p1_mh@1": "Kv2p1",
    "betse_kv2p2_mh@1": "Kv2p2",
    "betse_kv3p1_m@1": "Kv3p1",
    "betse_kv3p2_m2@1": "Kv3p2",
    "betse_kv3p3_m2h_source_tau@1": "Kv3p3",
    "betse_kv3p4_mh@1": "Kv3p4",
    "betse_k_fast_mh@1": "K_Fast",
    "betse_kleak_always_open@1": "KLeak",
}
ADDED_LEAK_LAWS = {
    "betse_clleak_always_open@1": "ClLeak",
    "betse_catleak_na_k@1": "CatLeak",
    "betse_catleak2_na_k_ca@1": "CatLeak2",
}
ADDED_CALCIUM_LAWS = {
    "betse_ca_l2_m2h@1": "Ca_L2",
    "betse_ca_l3_shift15_m2h@1": "Ca_L3",
    "betse_cav_g_m2h_regularized@1": "Cav_G",
    "betse_caleak_always_open@1": "CaLeak",
}
MORRIS_LECAR_LAWS = {
    "betse_kv_ml1_dynamic_m@1": "Kv_ML1",
    "betse_kv2p1_ml_dynamic_m@1": "Kv2p1_ML",
    "betse_kv1p3_ml_dynamic_m@1": "Kv1p3_ML",
    "betse_kv1p5_ml_dynamic_m@1": "Kv1p5_ML",
    "betse_kv1p5s_ml_slow_dynamic_m@1": "Kv1p5S_ML",
    "betse_nav_ml_instantaneous@1": "Nav_ML",
    "betse_cav_l_ml_instantaneous@1": "Cav_L_ML",
    "betse_cav_l_ml2_instantaneous@1": "Cav_L_ML2",
    "betse_cav_n_ml_instantaneous@1": "Cav_N_ML",
    "betse_cav_t_ml_instantaneous@1": "Cav_T_ML",
    "betse_kir_ml_instantaneous@1": "Kir_ML",
    "betse_hcn2_ml_source_sign_instantaneous@1": "HCN2_ML",
    "betse_hcn4_ml_source_sign_instantaneous@1": "HCN4_ML",
}
ML_DYNAMIC_LAWS = frozenset(
    law
    for law, name in MORRIS_LECAR_LAWS.items()
    if name in morris_lecar_channels_reference.KINETIC
)
CATALOG_PERMEABILITIES = (
    {law: (("K", 1.0),) for law in (*kv1_reference.LAWS, "betse_kir2p1_mh2@1")}
    | {"betse_nav1p2_m3h_regularized@1": (("Na", 1.0),)}
    | {f"betse_hcn{i}_m@1": (("Na", 0.2), ("K", 1.0), ("Ca", 0.05)) for i in (1, 2, 4)}
    | {law: (("Ca", 1.0),) for law in cav_reference.LAWS}
    | {law: (("Na", 1.0),) for law in ADDED_SODIUM_LAWS}
    | {law: (("K", 1.0),) for law in ADDED_POTASSIUM_LAWS}
    | {
        law: leak_channels_reference.ORDERED_PERMEABILITIES[name]
        for law, name in ADDED_LEAK_LAWS.items()
    }
)
CATALOG_V2_PERMEABILITIES = CATALOG_PERMEABILITIES | {
    law: (("Ca", 1.0),) for law in ADDED_CALCIUM_LAWS
}
CATALOG_V3_PERMEABILITIES = CATALOG_V2_PERMEABILITIES | {CALCIUM_ACTIVATED_LAW: (("K", 1.0),)}
CATALOG_V4_PERMEABILITIES = CATALOG_V3_PERMEABILITIES | {
    law: morris_lecar_channels_reference.PERMEABILITIES[name]
    for law, name in MORRIS_LECAR_LAWS.items()
}
CATALOG_V5_PERMEABILITIES = CATALOG_V4_PERMEABILITIES | {
    "betse_hcn_leak_open@1": (("Na", 0.33), ("K", 1.0), ("Ca", 0.05)),
    "betse_hcn2_camp_m@1": (("Na", 0.2), ("K", 1.0), ("Ca", 0.05)),
    "betse_hcn4_camp_m@1": (("Na", 0.2), ("K", 1.0), ("Ca", 0.05)),
}


def _finite_real(value):
    return isinstance(value, Real) and not isinstance(value, bool) and np.isfinite(value)


def _catalog_binding(raw):
    """Versioned channel contracts; @8 retains exactly its original 35 laws."""
    m, e = raw["model"], raw["experiment"]
    catalog = {
        CATALOG_MODEL: CATALOG_PERMEABILITIES,
        CATALOG_V2_MODEL: CATALOG_V2_PERMEABILITIES,
        CATALOG_V3_MODEL: CATALOG_V3_PERMEABILITIES,
        CATALOG_V4_MODEL: CATALOG_V4_PERMEABILITIES,
        CATALOG_V5_MODEL: CATALOG_V5_PERMEABILITIES,
    }[m["id"]]
    if m["temperature_K"] != 298.15:
        raise ValueError("Expanded catalog requires 298.15 K without temperature scaling")
    species = {row["id"]: row["valence"] for row in m["species"]}
    patches = {row["id"] for row in m["membranes"]}
    expected_valence = {"Na": 1, "K": 1, "Cl": -1, "Ca": 2}
    names = set()
    for ch in m["channels"]:
        law, name = ch["kinetic_law"], ch["id"]
        if (
            law not in catalog
            or not isinstance(name, str)
            or not name
            or name in names
            or ch["membrane_id"] not in patches
        ):
            raise ValueError("Require a known channel law, unique population and declared patch")
        names.add(name)
        for key in ("max_permeability_m_per_s", "abundance"):
            if not _finite_real(ch[key]) or ch[key] < 0:
                raise ValueError(
                    "Channel permeability and abundance must be finite and nonnegative"
                )
        gates = ch["initial_gate"]
        if law == CALCIUM_ACTIVATED_LAW:
            if type(gates) is not list or gates or species.get("Ca") != 2:
                raise ValueError(
                    "Instantaneous calcium-sensitive K requires initial_gate=[] and Ca+2"
                )
        elif law == HCN_LEAK_LAW:
            if type(gates) is not list or gates:
                raise ValueError("HCNLeak requires no dynamic gates")
        elif law in MORRIS_LECAR_LAWS:
            count = 1 if law in ML_DYNAMIC_LAWS else 0
            if (
                type(gates) is not list
                or len(gates) != count
                or any(not _finite_real(g) or not 0 <= g <= 1 for g in gates)
            ):
                raise ValueError(
                    "Morris–Lecar requires its declared zero or one initial gate state"
                )
        elif len(gates) != 2 or any(not _finite_real(g) or not 0 <= g <= 1 for g in gates):
            raise ValueError("Require two finite initial gates in [0,1]")
        routes = ch["permeant_ions"]
        if (
            any(
                not _finite_real(row["relative_permeability"])
                or species.get(row["species_id"]) != expected_valence.get(row["species_id"])
                for row in routes
            )
            or tuple((row["species_id"], row["relative_permeability"]) for row in routes)
            != catalog[law]
        ):
            raise ValueError("Require the law's exact ordered ion routes, weights and valences")
    controls = set()
    for group in e["channel_controls"]:
        name, schedule = group["channel_id"], group["schedule"]
        if name not in names or name in controls or not schedule:
            raise ValueError("Require one nonempty control schedule per declared population")
        controls.add(name)
        times = [row["time"] for row in schedule]
        levels = [row["availability"] for row in schedule]
        if (
            any(not _finite_real(v) for v in (*times, *levels))
            or times[0] != 0
            or any(b <= a for a, b in zip(times, times[1:], strict=False))
            or times[-1] > e["end_time"]
            or any(not 0 <= level <= 1 for level in levels)
        ):
            raise ValueError("Require ordered right-continuous controls in the declared interval")
    if controls != names:
        raise ValueError("Channel controls must cover every population exactly once")


def bind(raw):
    if raw["model"]["id"] in CATALOG_MODELS:
        _catalog_binding(raw)
    c = base.bind(raw)
    m = raw["model"]
    nc, ne, nm = len(m["channels"]), len(m["junctions"]), len(m["membranes"])
    transfer = (len(m["species"]), nc) if m["id"] in SHARED_MODELS else (nc,)
    c["shapes"].update(
        channel_gate=(2, nc),
        channel_transferred=transfer,
        channel_dissipated_energy_pJ=transfer,
        junction_gate=(ne,),
        pump_cycles=(nm,),
        pump_dissipated_energy_pJ=(nm,),
        metabolic_work_pJ=(nm,),
    )
    return c


def initial(c):
    d = unpack(c, base.initial(c))
    channels = c["raw"]["model"]["channels"]
    d["channel_gate"] = (
        np.asarray(
            [
                ([v["initial_gate"][0], 0.0] if v["kinetic_law"] in ML_DYNAMIC_LAWS else [0.0, 0.0])
                if v["kinetic_law"] in MORRIS_LECAR_LAWS
                else [0.0, 0.0]
                if v["kinetic_law"] in (CALCIUM_ACTIVATED_LAW, HCN_LEAK_LAW)
                else v["initial_gate"]
                for v in channels
            ]
        )
        .reshape(-1, 2)
        .T
    )
    d["junction_gate"] = np.asarray(
        [v["gate"]["initial_gate"] for v in c["raw"]["model"]["junctions"]]
    )
    return flatten(c, d)


def availability(c, kind, name, time):
    group = next(g for g in c["raw"]["experiment"][kind + "_controls"] if g[kind + "_id"] == name)
    return next(v["availability"] for v in reversed(group["schedule"]) if v["time"] <= time)


def evaluate(
    c,
    state,
    time,
    *,
    inside_amount=None,
    channel_levels=None,
    charge_equivalent_increment_fmol=None,
):
    raw = base.stage(
        c, state, time, charge_equivalent_increment_fmol=charge_equivalent_increment_fmol
    )
    d, m, p = unpack(c, state), c["raw"]["model"], c["layout"]
    if inside_amount is not None:
        raw["ci"] = np.asarray(inside_amount) / c["vi"]
    if m["id"] in CATALOG_MODELS:
        gates = d["channel_gate"]
        if (
            not np.isfinite(state).all()
            or not _finite_real(time)
            or time < 0
            or not np.isfinite(raw["ci"]).all()
            or not np.isfinite(raw["co"]).all()
            or np.any(raw["ci"] <= 0)
            or np.any(raw["co"] <= 0)
            or np.any((gates < 0) | (gates > 1))
        ):
            raise ValueError(
                "Expanded catalog requires finite state, positive ions and strict gates"
            )
        if channel_levels is not None and (
            np.shape(channel_levels) != np.shape(c["vi"])
            or not np.isfinite(channel_levels).all()
            or np.any(np.asarray(channel_levels) < 0)
            or np.any(np.asarray(channel_levels) > 1)
        ):
            raise ValueError("External channel levels require one finite [0,1] value per cell")
        if m["id"] in (CATALOG_V3_MODEL, CATALOG_V4_MODEL, CATALOG_V5_MODEL):
            stateless = [
                v["kinetic_law"] in (CALCIUM_ACTIVATED_LAW, HCN_LEAK_LAW) for v in m["channels"]
            ]
            if np.any(gates[:, stateless] != 0):
                raise ValueError(
                    "Instantaneous calcium-sensitive K packed gate slots must stay zero"
                )
        if m["id"] in (CATALOG_V4_MODEL, CATALOG_V5_MODEL):
            for j, ch in enumerate(m["channels"]):
                law = ch["kinetic_law"]
                if law in MORRIS_LECAR_LAWS:
                    count = 1 if law in ML_DYNAMIC_LAWS else 0
                    if np.any(gates[count:, j] != 0):
                        raise ValueError("Absent Morris–Lecar packed gate slots must stay zero")
    raw["junction_open"] = np.asarray(raw["junction_open"]) * d["junction_gate"]
    phi, proof = electrical.solve(raw)
    n = len(c["qi"])
    rates = transport.transport(raw, phi[:n], phi[n:])
    result = {k: np.zeros(shape) for k, shape in c["shapes"].items()}
    for kind in ("membrane", "junction", "face"):
        result[kind + "_transferred"] = rates[kind + "_flux_fmol_s"].copy()
        result[kind + "_dissipated_energy_pJ"] = rates[kind + "_dissipation_pJ_s"].copy()
    cell, outside = rates["cell_rate_fmol_s"].copy(), rates["outside_rate_fmol_s"].copy()
    supply = rates["reservoir_supply_fmol_s"].copy()
    ids, mids = [v["id"] for v in m["species"]], [v["id"] for v in m["membranes"]]

    def transfer(species, patch, outward):
        i, o = p["membrane_cell"][patch], p["membrane_outside"][patch]
        cell[species, i] -= outward
        if p["reservoir"][o]:
            supply[species, o] -= outward
        else:
            outside[species, o] += outward

    for k, ch in enumerate(m["channels"]):
        j = mids.index(ch["membrane_id"])
        i, o = p["membrane_cell"][j], p["membrane_outside"][j]
        voltage = phi[i] - phi[n + o]
        if m["id"] in CATALOG_MODELS and not -0.120 <= voltage <= 0.060:
            raise ValueError("Channel voltage outside the declared [-0.120,0.060] V domain")
        with localcontext() as context:
            context.prec = 65
            if m["id"] == CATALOG_V5_MODEL and ch["kinetic_law"] in HCN_EXTRA_LAWS:
                family = HCN_EXTRA_LAWS[ch["kinetic_law"]]
                target, tau = hcn_extra_reference.kinetics(float(voltage), family)
                opened = hcn_extra_reference.opening(d["channel_gate"][:, k], family)
            elif (
                m["id"] in (CATALOG_V4_MODEL, CATALOG_V5_MODEL)
                and ch["kinetic_law"] in MORRIS_LECAR_LAWS
            ):
                family = MORRIS_LECAR_LAWS[ch["kinetic_law"]]
                opened = morris_lecar_channels_reference.opening(
                    float(d["channel_gate"][0, k]), float(voltage), family
                )
                result["channel_gate"][0, k] = morris_lecar_channels_reference.rhs(
                    float(d["channel_gate"][0, k]), float(voltage), family
                )
            elif (
                m["id"] in (CATALOG_V3_MODEL, CATALOG_V4_MODEL, CATALOG_V5_MODEL)
                and ch["kinetic_law"] == CALCIUM_ACTIVATED_LAW
            ):
                opened = calcium_activated_potassium_reference.evaluate(
                    float(voltage), float(raw["ci"][ids.index("Ca"), i]), p["temperature"]
                )["opening"]
            elif ch["kinetic_law"] == "betse_kv1p5_mh@1":
                target, tau = channel_kinetics(float(voltage))
                opened = np.prod(d["channel_gate"][:, k])
            elif ch["kinetic_law"] == "betse_kir2p1_mh2@1":
                target, tau = kir_reference.kinetics(float(voltage))
                opened = float(kir_reference.opening(d["channel_gate"][:, k]))
            elif ch["kinetic_law"] == "betse_nav1p2_m3h_regularized@1":
                target, tau = sodium_reference.kinetics(float(voltage))
                opened = float(sodium_reference.opening(d["channel_gate"][:, k]))
            elif ch["kinetic_law"] in ("betse_hcn1_m@1", "betse_hcn2_m@1", "betse_hcn4_m@1"):
                family = int(ch["kinetic_law"][9])
                target, tau = hcn_reference.kinetics(float(voltage), family)
                opened = float(hcn_reference.opening(d["channel_gate"][:, k]))
            elif ch["kinetic_law"] in kv1_reference.LAWS:
                family = kv1_reference.LAWS[ch["kinetic_law"]]
                target, tau = kv1_reference.kinetics(float(voltage), family)
                opened = float(kv1_reference.opening(d["channel_gate"][:, k], family))
            elif ch["kinetic_law"] in cav_reference.LAWS:
                family = cav_reference.LAWS[ch["kinetic_law"]]
                target, tau = cav_reference.kinetics(float(voltage), family)
                opened = float(cav_reference.opening(d["channel_gate"][:, k], family))
            elif m["id"] in CATALOG_MODELS and ch["kinetic_law"] in ADDED_SODIUM_LAWS:
                family = ADDED_SODIUM_LAWS[ch["kinetic_law"]]
                values = sodium_catalog_reference.kinetics(float(voltage), family)
                target, tau = values["target"], values["tau_s"]
                opened = sodium_catalog_reference.opening(d["channel_gate"][:, k], family)
            elif m["id"] in CATALOG_MODELS and ch["kinetic_law"] in ADDED_POTASSIUM_LAWS:
                family = ADDED_POTASSIUM_LAWS[ch["kinetic_law"]]
                values = potassium_catalog_reference.kinetics(float(voltage), family)
                target, tau = values["target"], values["tau_s"]
                opened = potassium_catalog_reference.opening(d["channel_gate"][:, k], family)
            elif m["id"] in CATALOG_MODELS and ch["kinetic_law"] in ADDED_LEAK_LAWS:
                family = ADDED_LEAK_LAWS[ch["kinetic_law"]]
                values = leak_channels_reference.kinetics(float(voltage), family)
                target, tau = values["target"], values["tau_s"]
                opened = leak_channels_reference.opening(d["channel_gate"][:, k], family)
            elif (
                m["id"] in (CATALOG_V2_MODEL, CATALOG_V3_MODEL, CATALOG_V4_MODEL, CATALOG_V5_MODEL)
                and ch["kinetic_law"] in ADDED_CALCIUM_LAWS
            ):
                family = ADDED_CALCIUM_LAWS[ch["kinetic_law"]]
                values = calcium_catalog_extra_reference.kinetics(float(voltage), family)
                target, tau = values["target"], values["tau_s"]
                opened = calcium_catalog_extra_reference.opening(d["channel_gate"][:, k], family)
            else:
                raise ValueError("Unsupported independent channel law")
            if (
                ch["kinetic_law"] != CALCIUM_ACTIVATED_LAW
                and ch["kinetic_law"] != HCN_LEAK_LAW
                and ch["kinetic_law"] not in MORRIS_LECAR_LAWS
            ):
                result["channel_gate"][:, k] = [
                    (float(a) - g) / float(t)
                    for a, t, g in zip(target, tau, d["channel_gate"][:, k], strict=True)
                ]
        routes = ch.get("permeant_ions")
        if routes is None:
            routes = [dict(species_id=ch["species_id"], relative_permeability=1.0)]
        for route in routes:
            s = ids.index(route["species_id"])
            flux = transport.decimal_flux(
                raw["ci"][s, i],
                raw["co"][s, o],
                voltage,
                p["valence"][s][0],
                p["temperature"],
                p["membrane_area"][j],
                ch["max_permeability_m_per_s"] * ch["abundance"] * route["relative_permeability"],
                1.0,
                opened
                * availability(c, "channel", ch["id"], time)
                * (1.0 if channel_levels is None else channel_levels[i]),
                {"F": F, "R": R},
            )
            index = (s, k) if m["id"] in SHARED_MODELS else k
            result["channel_transferred"][index] = flux
            result["channel_dissipated_energy_pJ"][index] = (
                1e-3 * flux * rates["membrane_delta_mu_J_mol"][s, j]
            )
            transfer(s, j, flux)
    for j, membrane in enumerate(m["membranes"]):
        pump = membrane["pump"]
        if pump is None:
            continue
        i, o = p["membrane_cell"][j], p["membrane_outside"][j]
        na, k = (ids.index(pump["roles"][r]) for r in ("sodium", "potassium"))
        meta = pump["metabolism"]
        case = dict(
            id=pump["id"],
            na_in_mM=float(raw["ci"][na, i]),
            na_out_mM=float(raw["co"][na, o]),
            k_in_mM=float(raw["ci"][k, i]),
            k_out_mM=float(raw["co"][k, o]),
            temperature_K=p["temperature"],
            area_m2=membrane["area_m2"],
            alpha_mol_m2_s=pump["capacity_fmol_per_s"] * 1e-15 / membrane["area_m2"],
            availability=availability(c, "pump", pump["id"], time),
            voltage_V=float(phi[i] - phi[n + o]),
            delta_g0_J_mol=meta["delta_g0_J_per_mol"],
            **{key: meta[key] for key in ("atp_mM", "adp_mM", "pi_mM")},
            **{key: pump[key] for key in ("km_na_mM", "km_k_mM", "km_atp_mM")},
        )
        value = pump_oracle(case, {"F": F, "R": R})
        result["pump_cycles"][j] = -value["na_in_fmol_s"] / 3
        result["pump_dissipated_energy_pJ"][j] = value["dissipation_pJ_s"]
        result["metabolic_work_pJ"][j] = value["chemical_input_power_pJ_s"]
        transfer(na, j, -value["na_in_fmol_s"])
        transfer(k, j, -value["k_in_fmol_s"])
    for j, route in enumerate(m["junctions"]):
        with localcontext() as context:
            context.prec = 65
            shift = Decimal(str(abs(rates["junction_voltage_V"][j]))) - Decimal(
                str(route["gate"]["threshold_voltage_V"])
            )
            alpha = Decimal("1.3") * (-77 * shift).exp()
            b = Decimal("0.0013") * (140 * shift).exp()
            beta = 1000 * b / (1 + 50 * b)
            g, minimum = (
                Decimal(str(d["junction_gate"][j])),
                Decimal(str(route["gate"]["minimum_open_fraction"])),
            )
            result["junction_gate"][j] = float(alpha * (1 - g) - beta * (g - minimum))
    matrix, active, reservoir, fixed, floating, _ = electrical.topology(raw)
    pins = ~active | reservoir
    for members in floating:
        pins[members[0]] = True
    free = np.flatnonzero(~pins)
    ionic = 1e-15 * F * (np.asarray(p["valence"]).T @ np.c_[cell, outside])[0]
    derivative = np.zeros_like(phi)
    derivative[free] = np.linalg.solve(matrix[np.ix_(free, free)], ionic[free])
    np.testing.assert_allclose(
        (matrix @ derivative)[active & ~reservoir],
        ionic[active & ~reservoir],
        rtol=2e-12,
        atol=2e-23,
    )
    electrode = np.where(p["reservoir"], (matrix @ derivative)[n:], 0.0)
    mu = R * p["temperature"] * np.log(raw["co"]) + F * np.asarray(p["valence"]) * phi[n:]
    result.update(
        amount_increment=cell,
        extracellular_amount_increment=outside,
        reservoir_supplied=supply,
        electrode_charge_transferred_C=electrode,
        reservoir_work_pJ=1e-3 * np.sum(mu * supply, axis=0),
        electrode_work_pJ=1e12 * phi[n:] * electrode,
    )
    return flatten(c, result), phi, proof


def integrate(raw, *, rtol=2e-11, state_atol=2e-14, charge_atol=1e-29):
    """Expose independent accuracy while retaining earlier panels' default settings."""
    c, e = bind(raw), raw["experiment"]
    events = sorted(
        {
            0.0,
            e["end_time"],
            *(
                p["time"]
                for kind in ("membrane", "junction", "channel", "pump")
                for group in e[kind + "_controls"]
                for p in group["schedule"]
            ),
        }
    )
    times, state, evaluations = e["observation_times"], initial(c), 0
    result = {0.0: state.copy()}
    atols = flatten(
        c,
        {
            k: np.full(shape, charge_atol if k.endswith("_C") else state_atol)
            for k, shape in c["shapes"].items()
        },
    )
    for left, right in zip(events, events[1:], strict=False):
        sol = solve_ivp(
            lambda t, y, held=left: evaluate(c, y, held)[0],
            (left, right),
            state,
            method="DOP853",
            rtol=rtol,
            atol=atols,
            max_step=0.0001,
            dense_output=True,
        )
        assert sol.success, sol.message
        evaluations += sol.nfev
        for t in times:
            if left < t <= right:
                result[t] = sol.sol(t)
        state = sol.y[:, -1]
    return dict(
        times=times,
        state=np.stack([result[t] for t in times]).tolist(),
        potential_V=np.stack([evaluate(c, result[t], t)[1] for t in times]).tolist(),
        rhs_evaluations=evaluations,
        method="DOP853, full-node roots, Decimal transport/gates/pumps",
        rtol=rtol,
        amount_energy_gate_atol=state_atol,
        electrode_charge_atol_C=charge_atol,
    )
