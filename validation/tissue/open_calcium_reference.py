"""Independent static open-owned calcium/fuel equations and source accounting.

Existing scalar/full-node reference laws are reused with ACTUAL reservoir
flags. New owner loops explicitly close all plasma sources and external work.
No production/JAX imports, state clamps, background changes or closed admission.
The three component functions below retain the qualified reference equations;
only the open closure, explicit reservoir admission and caller are changed.
"""

import ast
import hashlib
import math
from copy import deepcopy
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np

from validation.chemistry import finite_energy_reference as chemistry
from validation.tissue import surface_calcium_energy_reference as finite
from validation.tissue import surface_calcium_reference as calcium
from validation.tissue import surface_field_reference as electrical
from validation.tissue import surface_kinetic_reference as kinetic

F, R = calcium.F, calcium.R
flatten, unpack = calcium.flatten, calcium.unpack
ER_FIELDS = calcium.ER_FIELDS
MODEL_PROJECTIONS = finite.MODEL_PROJECTIONS
PMCA_LAW, ER_LAW = finite.PMCA_LAW, finite.ER_LAW
_number, _owner, _project = finite._number, finite._owner, finite._project
held = calcium.held
scalar_rates, scalar_kinetics, scalar_flux = (
    calcium.scalar_rates,
    calcium.scalar_kinetics,
    calcium.scalar_flux,
)


def _calcium_rates(c, state, time, *, channel_levels=None):
    d = unpack(c, state)
    ion = c["raw"]["model"]
    m = c["full"]["model"]
    p = c["layout"]
    ids = [s["id"] for s in ion["species"]]
    ca = ids.index(m["plasma_transport"]["calcium_species"])
    na = ids.index(m["plasma_transport"]["sodium_species"])
    free = np.stack(
        [
            (s.n0 + d["chemical_amount_increment"][i])[[s.ids.index(k) for k in ids], s.cy]
            for i, s in enumerate(c["stores"])
        ],
        axis=1,
    )
    dr, phi, proof = kinetic.evaluate(
        c, state, time, inside_amount=free, channel_levels=channel_levels
    )
    result = unpack(c, dr)
    ci = free / c["vi"]
    co = (c["ao"] + d["extracellular_amount_increment"]) / c["vo"]
    n = len(c["vi"])
    for j, patch in enumerate(ion["membranes"]):
        i, o = p["membrane_cell"][j], p["membrane_outside"][j]
        vm = phi[i] - phi[n + o]
        route = m["plasma_transport"]["membranes"][j]
        control = held(c, "plasma_controls", j, time)
        pmca, ncx, gp, gx, drive = scalar_rates(
            ci[na, i],
            co[na, o],
            ci[ca, i],
            co[ca, o],
            vm,
            p["temperature"],
            route["pump"],
            route["exchanger"],
            (control["pump"], control["exchanger"]),
        )
        target, tau = scalar_kinetics(vm)
        result["calcium_gate"][:, j] = (target - d["calcium_gate"][:, j]) / tau
        ch = m["calcium_channels"][j]
        opening = (
            d["calcium_gate"][0, j] ** 2
            * d["calcium_gate"][1, j]
            * held(c, "calcium_channel_controls", j, time)["availability"]
        )
        inward, diss = scalar_flux(
            ci[ca, i],
            co[ca, o],
            vm,
            p["temperature"],
            patch["area_m2"],
            ch["max_permeability_m_per_s"] * ch["abundance"] * opening,
        )
        for s, outward in ((ca, pmca + ncx - inward), (na, -3 * ncx)):
            result["amount_increment"][s, i] -= outward
            if p["reservoir"][o]:
                result["reservoir_supplied"][s, o] -= outward
            else:
                result["extracellular_amount_increment"][s, o] += outward
        result["plasma_pump_cycles"][j] = pmca
        result["plasma_exchange_cycles"][j] = ncx
        result["plasma_dissipated_energy_pJ"][:, j] = -1e-3 * np.array([pmca * gp, ncx * gx])
        result["calcium_channel_transferred"][j] = -inward
        result["calcium_channel_dissipated_energy_pJ"][j] = diss
        result["plasma_metabolic_work_pJ"][j] = -1e-3 * drive * pmca
    chemical = (
        1e-3 * R * p["temperature"] * np.sum(np.log(co) * result["extracellular_amount_increment"])
    )
    er_power = 0.0
    for i, s in enumerate(c["stores"]):
        local = np.concatenate([d[k][i].ravel() for k in ER_FIELDS])
        parts = s.unpack(s.rhs(local, held(c, "store_controls", i, time)))
        for j, k in enumerate(ids):
            parts[0][s.ids.index(k), s.cy] += result["amount_increment"][j, i]
        for k, v in zip(ER_FIELDS, parts, strict=True):
            result[k][i] = v
        pump = s.membrane["pump"]
        drive = (
            0
            if pump is None
            else pump["delta_g0_J_per_mol"]
            + s.rt * math.log(pump["adp_mM"] * pump["pi_mM"] / pump["atp_mM"])
        )
        result["er_metabolic_work_pJ"][i] = -1e-3 * drive * parts[4][0]
        chemical += (
            1e-3
            * s.rt
            * np.sum(
                (
                    s.mu0[:, None]
                    + np.log((s.n0 + d["chemical_amount_increment"][i]) / (s.volume * s.c0))
                )
                * parts[0]
            )
        )
        voltage = s.membrane["initial_voltage_V"] + F * 1e-15 / s.cap * math.fsum(
            s.z * d["chemical_amount_increment"][i, :, s.er]
        )
        er_power += 1e12 * voltage * F * 1e-15 * math.fsum(s.z * parts[0][:, s.er])
    raw = kinetic.base.stage(c, state, time)
    raw["ci"] = ci
    matrix, active, reservoir, _, floating, _ = electrical.topology(raw)
    pins = ~active | reservoir
    for members in floating:
        pins[members[0]] = True
    free_nodes = np.flatnonzero(~pins)
    current = (
        F
        * 1e-15
        * (
            np.asarray(p["valence"]).T
            @ np.c_[result["amount_increment"], result["extracellular_amount_increment"]]
        )[0]
    )
    dv = np.zeros_like(phi)
    dv[free_nodes] = np.linalg.solve(matrix[np.ix_(free_nodes, free_nodes)], current[free_nodes])
    np.testing.assert_allclose(
        (matrix @ dv)[active & ~reservoir], current[active & ~reservoir], atol=3e-23, rtol=2e-12
    )
    electrode = np.where(p["reservoir"], (matrix @ dv)[n:], 0.0)
    mu = R * p["temperature"] * np.log(co) + F * np.asarray(p["valence"]) * phi[n:]
    result["electrode_charge_transferred_C"] = electrode
    result["reservoir_work_pJ"] = 1e-3 * np.sum(mu * result["reservoir_supplied"], axis=0)
    result["electrode_work_pJ"] = 1e12 * phi[n:] * electrode
    electric = 0.0
    for j, patch in enumerate(ion["membranes"]):
        i, o = p["membrane_cell"][j], n + p["membrane_outside"][j]
        electric += 1e12 * patch["capacitance_F"] * (phi[i] - phi[o]) * (dv[i] - dv[o])
    dissipation = sum(
        float(np.sum(v)) for k, v in result.items() if k.endswith("_dissipated_energy_pJ")
    )
    work = sum(
        float(np.sum(result[k]))
        for k in ("metabolic_work_pJ", "plasma_metabolic_work_pJ", "er_metabolic_work_pJ")
    )
    return (
        flatten(c, result),
        phi,
        proof
        | dict(
            physical_energy_balance_pJ_s=chemical
            + electric
            + er_power
            + dissipation
            - work
            - result["reservoir_work_pJ"].sum()
            - result["electrode_work_pJ"].sum(),
            chemical_power_pJ_s=chemical,
            capacitor_power_pJ_s=electric + er_power,
            dissipation_pJ_s=dissipation,
            external_metabolic_power_pJ_s=work,
            reservoir_power_pJ_s=float(result["reservoir_work_pJ"].sum()),
            electrode_power_pJ_s=float(result["electrode_work_pJ"].sum()),
            reservoir_supply_fmol_s=result["reservoir_supplied"].tolist(),
            electrode_current_A=electrode.tolist(),
        ),
    )


def _fuel_components(raw):
    m = raw["model"]
    if m["id"] not in MODEL_PROJECTIONS or m["ionic"]["id"] != MODEL_PROJECTIONS[m["id"]][1]:
        raise ValueError("Require the finite-energy calcium identity's versioned shared catalog")
    ion = m["ionic"]
    if ion["temperature_K"] != 298.15:
        raise ValueError("Require unscaled 298.15-K full-catalog channels")
    cells = [v["id"] for v in ion["cells"]]
    pools = {v["id"]: v for v in m["energy_pools"]}
    by_cell = {v["cell_id"]: v for v in m["energy_pools"]}
    if (
        len(pools) != len(m["energy_pools"])
        or len(pools) != len(cells)
        or set(by_cell) != set(cells)
    ):
        raise ValueError("Require exactly one distinct finite pool per cell")
    volume = np.array([v["volume_pL"] for v in ion["cells"]])
    amounts, deltas = [], []
    for i, cell in enumerate(cells):
        pool = by_cell[cell]
        if pool["law"] != "finite_atp_adp_pi_transformed@1" or set(pool["initial_amount_fmol"]) != {
            "ATP",
            "ADP",
            "Pi",
        }:
            raise ValueError("Require explicit transformed ATP/ADP/Pi pool law and amounts")
        values = [pool["initial_amount_fmol"][k] for k in ("ATP", "ADP", "Pi")]
        chemistry.thermodynamics(
            values, volume[i], ion["temperature_K"], pool["delta_g0_J_per_mol"]
        )
        amounts.append(values)
        deltas.append(pool["delta_g0_J_per_mol"])
    c = dict(
        raw=deepcopy(raw),
        pools=pools,
        cell_ids=cells,
        energy_initial=np.asarray(amounts).T,
        energy_volumes=volume,
        energy_delta_g0=np.asarray(deltas),
        temperature=ion["temperature_K"],
    )
    patches = {p["id"]: p for p in ion["membranes"]}
    c["patch_owners"] = [cells.index(p["inside"]) for p in ion["membranes"]]
    c["plasma_owners"] = [
        cells.index(patches[p["membrane_id"]]["inside"]) for p in m["plasma_transport"]["membranes"]
    ]
    for patch in ion["membranes"]:
        if patch["pump"] is not None:
            _owner(c, patch["pump"]["metabolism"], patch["inside"])
    for is_er, rows in ((False, m["plasma_transport"]["membranes"]), (True, m["stores"])):
        for row in rows:
            pump = row["model"]["membrane"]["pump"] if is_er else row["pump"]
            if pump is None:
                continue
            if set(pump) != {
                "law",
                "capacity_fmol_per_s",
                "km_ca_mM",
                "km_atp_mM",
                "metabolism",
            } or pump["law"] != (ER_LAW if is_er else PMCA_LAW):
                raise ValueError("Require an explicit finite PMCA or one-Ca/ATP ER law")
            if not _number(pump["capacity_fmol_per_s"]) or any(
                not _number(pump[k], positive=True) for k in ("km_ca_mM", "km_atp_mM")
            ):
                raise ValueError(
                    "Require finite nonnegative pump capacity and positive half-saturation"
                )
            _owner(
                c,
                pump["metabolism"],
                row["cell_id"] if is_er else patches[row["membrane_id"]]["inside"],
            )
    ports = m["regeneration_ports"]
    names = [p["id"] for p in ports]
    if len(set(names)) != len(names):
        raise ValueError("Regeneration IDs must be unique")
    for p in ports:
        if (
            p["pool_id"] not in pools
            or p["law"] != "driven_atp_regeneration_tanh@1"
            or not _number(p["capacity_fmol_per_s"])
            or not _number(p["supplied_energy_J_per_mol"])
        ):
            raise ValueError("Invalid regeneration owner, law, capacity or supplied energy")
    controls = {}
    for row in raw["experiment"]["regeneration_controls"]:
        name, schedule = row["regeneration_id"], row["schedule"]
        if name not in names or name in controls or not schedule:
            raise ValueError("Require exactly one nonempty schedule per regeneration port")
        times = [v["time"] for v in schedule]
        if (
            any(not _number(t) for t in times)
            or times[0] != 0
            or any(b <= a for a, b in zip(times, times[1:], strict=False))
            or times[-1] > raw["experiment"]["end_time"]
            or any(not _number(v["availability"]) or v["availability"] > 1 for v in schedule)
        ):
            raise ValueError("Invalid right-continuous regeneration control")
        controls[name] = deepcopy(schedule)
    if set(controls) != set(names):
        raise ValueError("Regeneration controls must cover every declared port")
    c["regeneration_controls"] = controls
    base = calcium.bind(_project(c, c["energy_initial"]))
    return dict(
        base,
        **c,
        calcium=base,
        shapes=base["shapes"]
        | dict(
            energy_amount_increment_fmol=(3, len(cells)),
            regeneration_cycles_fmol=(len(ports),),
            regeneration_dissipated_energy_pJ=(len(ports),),
            regeneration_supplied_work_pJ=(len(ports),),
        ),
    )


def _fuel_rates(c, state, time, *, channel_levels=None):
    d = unpack(c, state)
    amount = c["energy_initial"] + d["energy_amount_increment_fmol"]
    if not np.isfinite(state).all() or np.any(amount <= 0):
        raise ValueError("Complete finite-energy calcium state must be finite with positive pools")
    values = [
        chemistry.thermodynamics(
            amount[:, i], c["energy_volumes"][i], c["temperature"], c["energy_delta_g0"][i]
        )
        for i in range(len(c["cell_ids"]))
    ]
    # Rebinding independently refreshes Na/K, PMCA AND the ER store objects.
    # Never reuse a store carrying its initial maintained ATP concentrations.
    current = calcium.bind(_project(c, amount))
    slope, phi, prior = _calcium_rates(
        current, flatten(current, d), time, channel_levels=channel_levels
    )
    result = unpack(current, slope)
    n, ports = len(c["cell_ids"]), c["raw"]["model"]["regeneration_ports"]
    hydrolysis = np.array([v["hydrolysis_free_energy_J_mol"] for v in values])
    # Check finite-pool calcium affinities even for blocked physical pumps.
    ion_ids = [s["id"] for s in current["raw"]["model"]["species"]]
    ca = ion_ids.index(c["raw"]["model"]["plasma_transport"]["calcium_species"])
    for j, row in enumerate(c["raw"]["model"]["plasma_transport"]["membranes"]):
        if row["pump"] is not None:
            i, o = c["plasma_owners"][j], current["layout"]["membrane_outside"][j]
            store = current["stores"][i]
            ci = (store.n0 + d["chemical_amount_increment"][i])[store.ca, store.cy] / store.volume[
                store.cy
            ]
            co = (current["ao"] + d["extracellular_amount_increment"])[ca, o] / current["vo"][o]
            affinity = (
                hydrolysis[i]
                + R * c["temperature"] * np.log(co / ci)
                - 2 * F * (phi[i] - phi[n + o])
            )
            if not np.isfinite(affinity) or abs(affinity / (R * c["temperature"])) > 80:
                raise ValueError("Finite PMCA affinity outside numerical domain")
    for i, store in enumerate(current["stores"]):
        if store.membrane["pump"] is not None:
            concentrations = (store.n0 + d["chemical_amount_increment"][i]) / store.volume
            voltage = store.membrane["initial_voltage_V"] + 1e-15 * F / store.cap * np.dot(
                store.z, d["chemical_amount_increment"][i, :, store.er]
            )
            affinity = (
                hydrolysis[i]
                + store.rt
                * np.log(concentrations[store.ca, store.er] / concentrations[store.ca, store.cy])
                + 2 * F * voltage
            )
            if not np.isfinite(affinity) or abs(affinity / store.rt) > 80:
                raise ValueError("Finite ER-pump affinity outside numerical domain")
    regen, heat, supply = (np.zeros(len(ports)) for _ in range(3))
    regen_owners = []
    for j, port in enumerate(ports):
        i = c["cell_ids"].index(c["pools"][port["pool_id"]]["cell_id"])
        regen_owners.append(i)
        level = next(
            v["availability"]
            for v in reversed(c["regeneration_controls"][port["id"]])
            if v["time"] <= time
        )
        rate = chemistry.regeneration(
            amount[:, i],
            c["energy_volumes"][i],
            c["temperature"],
            c["energy_delta_g0"][i],
            port["capacity_fmol_per_s"],
            port["supplied_energy_J_per_mol"],
            level,
        )
        regen[j], heat[j], supply[j] = (
            rate["synthesis_fmol_s"],
            rate["dissipated_power_pJ_s"],
            rate["supplied_power_pJ_s"],
        )
    rates = [
        *result["pump_cycles"],
        *result["plasma_pump_cycles"],
        *result["er_pump_transferred"][:, 0],
    ]
    owners = [*c["patch_owners"], *c["plasma_owners"], *range(n)]
    exchange = chemistry.exchange(rates, owners, regen.tolist(), regen_owners, n)
    pool_rate = np.asarray(exchange["amount_fmol_s"])
    result.update(
        energy_amount_increment_fmol=pool_rate,
        regeneration_cycles_fmol=regen,
        regeneration_dissipated_energy_pJ=heat,
        regeneration_supplied_work_pJ=supply,
    )
    pool_power = np.array(
        [
            1e-3 * np.dot(v["chemical_potential_J_mol"], pool_rate[:, i])
            for i, v in enumerate(values)
        ]
    )
    work = np.zeros(n)
    for i, rate in zip(
        owners,
        [
            *result["metabolic_work_pJ"],
            *result["plasma_metabolic_work_pJ"],
            *result["er_metabolic_work_pJ"],
        ],
        strict=True,
    ):
        work[i] += rate
    port_balance = np.zeros(n)
    for j, i in enumerate(regen_owners):
        port_balance[i] += heat[j] - supply[j]
    internal = pool_power + work + port_balance
    total = (
        prior["physical_energy_balance_pJ_s"]
        + work.sum()
        + pool_power.sum()
        + heat.sum()
        - supply.sum()
    )
    return (
        flatten(c, result),
        phi,
        prior
        | dict(
            physical_energy_balance_pJ_s=float(total),
            prior_maintained_balance_pJ_s=prior["physical_energy_balance_pJ_s"],
            pool_chemical_power_pJ_s=float(pool_power.sum()),
            pool_internal_transfer_balance_pJ_s=internal.tolist(),
            internal_pump_transfer_power_pJ_s=float(work.sum()),
            internal_pump_transfer_by_owner_pJ_s=work.tolist(),
            pool_hydrolysis_free_energy_J_mol=hydrolysis.tolist(),
            regeneration_dissipation_pJ_s=float(heat.sum()),
            regeneration_supply_pJ_s=float(supply.sum()),
            dissipation_pJ_s=prior["dissipation_pJ_s"] + float(heat.sum()),
            internal_chemical_power_pJ_s=float(pool_power.sum()),
            external_metabolic_power_pJ_s=float(supply.sum()),
            adenylate_rate_fmol_s=(pool_rate[0] + pool_rate[1]).tolist(),
            # Sum the actual signed floating rates without first rounding 3*a.
            # This is an invariant diagnostic, never a change to the material rates.
            phosphorus_rate_fmol_s=[
                math.fsum((a, a, a, b, b, value)) for a, b, value in pool_rate.T
            ],
            signed_pump_demand_fmol_s=exchange["pump_hydrolysis_fmol_s"],
            signed_regeneration_fmol_s=exchange["regeneration_synthesis_fmol_s"],
        ),
    )


MODEL_IDS = {
    "resolved_open_calcium@1": "resolved_calcium@11",
    "resolved_open_calcium_energy@1": "resolved_calcium_energy@5",
}
EXTRA = ("exterior_policy", "ionic_moiety_domain_policy", "ionic_moiety_ceiling_fmol")


def equation_definition(raw):
    value = deepcopy(raw)
    value["model"]["id"] = MODEL_IDS[value["model"]["id"]]
    for key in EXTRA:
        value["model"].pop(key)
    return value


def bind(raw):
    m = raw["model"]
    if (
        m.get("id") not in MODEL_IDS
        or m.get("exterior_policy") != "static_declared_ideal_chemical_and_voltage_reservoirs@1"
        or m.get("ionic_moiety_domain_policy")
        != "hard_global_ionic_moiety_ceilings_fmol_every_stage@1"
    ):
        raise ValueError("Require an explicit full-catalog static open-owned model and domain")
    equation = equation_definition(raw)
    is_fuel = equation["model"]["id"] == "resolved_calcium_energy@5"
    context = _fuel_components(equation) if is_fuel else calcium.bind(equation)
    ion = equation["model"]["ionic"]
    open_world = any(row["reservoir"] for row in ion["extracellular"])
    ceiling = m["ionic_moiety_ceiling_fmol"]
    ids = [row["id"] for row in ion["species"]]
    if open_world:
        if (
            type(ceiling) is not dict
            or set(ceiling) != set(ids)
            or any(
                isinstance(v, bool)
                or not isinstance(v, (float, int))
                or not math.isfinite(v)
                or v <= 0
                for v in ceiling.values()
            )
        ):
            raise ValueError("Declare positive finite fmol ceilings for every ionic moiety")
        limit = np.asarray([ceiling[name] for name in ids])
    elif ceiling is not None:
        raise ValueError("An empty-reservoir reduction requires null open-system ceilings")
    else:
        limit = None
    context.update(
        open_definition=deepcopy(raw),
        equation_definition=equation,
        finite_fuel=is_fuel,
        open_world=open_world,
        ionic_moiety_ceiling_fmol=limit,
    )
    if limit is not None and np.any(ionic_moieties(context, initial(context)) > limit):
        raise ValueError("Ionic ceilings do not admit the actual initial physical state")
    return context


def initial(context):
    return finite.initial(context) if context["finite_fuel"] else calcium.initial(context)


def validate_padded_state(context, values):
    """Independent complete owner-axis/padding contract before compact packing."""
    raw = context["open_definition"]
    m, execution = raw["model"], raw["execution"]
    ion = m["ionic"]
    routes = {
        "amount_increment": "capacity",
        "extracellular_amount_increment": "extracellular_capacity",
        "membrane_transferred": "membrane_capacity",
        "junction_transferred": "edge_capacity",
        "face_transferred": "face_capacity",
        "reservoir_supplied": "extracellular_capacity",
        "membrane_dissipated_energy_pJ": "membrane_capacity",
        "junction_dissipated_energy_pJ": "edge_capacity",
        "face_dissipated_energy_pJ": "face_capacity",
        "electrode_charge_transferred_C": "extracellular_capacity",
        "reservoir_work_pJ": "extracellular_capacity",
        "electrode_work_pJ": "extracellular_capacity",
        "channel_gate": "channel_capacity",
        "channel_transferred": "channel_capacity",
        "channel_dissipated_energy_pJ": "channel_capacity",
        "junction_gate": "edge_capacity",
        "pump_cycles": "membrane_capacity",
        "pump_dissipated_energy_pJ": "membrane_capacity",
        "metabolic_work_pJ": "membrane_capacity",
        "plasma_pump_cycles": "membrane_capacity",
        "plasma_exchange_cycles": "membrane_capacity",
        "plasma_dissipated_energy_pJ": "membrane_capacity",
        "calcium_gate": "membrane_capacity",
        "calcium_channel_transferred": "membrane_capacity",
        "calcium_channel_dissipated_energy_pJ": "membrane_capacity",
        "plasma_metabolic_work_pJ": "membrane_capacity",
        "energy_amount_increment_fmol": "capacity",
        "regeneration_cycles_fmol": "regeneration_capacity",
        "regeneration_dissipated_energy_pJ": "regeneration_capacity",
        "regeneration_supplied_work_pJ": "regeneration_capacity",
    }
    if set(values) != set(context["shapes"]):
        raise ValueError("Incomplete padded open-owned state")
    for name, compact in context["shapes"].items():
        if name == "chemical_amount_increment":
            shape = (*compact[:-1], execution["chemical_capacity"])
        elif name in ("reaction_extent", "reaction_dissipated_energy_pJ"):
            shape = (*compact[:-1], execution["reaction_capacity"])
        elif name in routes:
            shape = (*compact[:-1], execution[routes[name]])
        else:
            shape = compact
        value = np.asarray(values[name])
        if (
            value.shape != shape
            or value.dtype != np.dtype("float64")
            or not np.isfinite(value).all()
        ):
            raise ValueError("Open-owned array shape/dtype/value disagrees: " + name)
        mask = np.zeros(shape, dtype=bool)
        mask[tuple(slice(0, size) for size in compact)] = True
        if np.any(value[~mask] != 0):
            raise ValueError("Open-owned array padding is nonzero: " + name)
    # Reservoir integrals and increments obey distinct physical masks.
    res = np.asarray([row["reservoir"] for row in ion["extracellular"]])
    count = len(res)
    if np.any(np.asarray(values["extracellular_amount_increment"])[..., :count][..., res] != 0):
        raise ValueError("Static reservoirs cannot accumulate outside inventory increments")
    for name in (
        "reservoir_supplied",
        "electrode_charge_transferred_C",
        "reservoir_work_pJ",
        "electrode_work_pJ",
    ):
        if np.any(np.asarray(values[name])[..., :count][..., ~res] != 0):
            raise ValueError("External reservoir histories belong only to declared reservoirs")


def ionic_moieties(context, state):
    values = unpack(context, state)
    m = context["equation_definition"]["model"]
    ion = m["ionic"]
    ids = [row["id"] for row in ion["species"]]
    base = context["calcium"] if context["finite_fuel"] else context
    result = np.sum(base["ao"] + values["extracellular_amount_increment"], axis=-1)
    stores = {row["cell_id"]: row["model"] for row in m["stores"]}
    for i, cell in enumerate(ion["cells"]):
        store, owner = stores[cell["id"]], base["stores"][i]
        by_id = {row["id"]: row for row in store["species"]}
        coefficients = np.asarray(
            [[by_id[species]["moieties"][name] for species in owner.ids] for name in ids]
        )
        result += coefficients @ np.sum(owner.n0 + values["chemical_amount_increment"][i], axis=-1)
    return result


def evaluate(context, state, time, *, channel_levels=None):
    if not np.isfinite(state).all() or not math.isfinite(time) or time < 0:
        raise ValueError("Require a finite complete open-owned stage")
    values = unpack(context, state)
    physical = context["calcium"] if context["finite_fuel"] else context
    if np.any(physical["ao"] + values["extracellular_amount_increment"] <= 0):
        raise ValueError("Nonpositive exterior inventory; no floor")
    for i, store in enumerate(physical["stores"]):
        if np.any(store.n0 + values["chemical_amount_increment"][i] <= 0):
            raise ValueError("Nonpositive owned chemical inventory; no floor")
    total = ionic_moieties(context, state)
    limit = context["ionic_moiety_ceiling_fmol"]
    if limit is not None and np.any(total > limit):
        raise ValueError("Open ionic-moiety domain exceeded; no clamp")
    result = (
        _fuel_rates(context, state, time, channel_levels=channel_levels)
        if context["finite_fuel"]
        else _calcium_rates(context, state, time, channel_levels=channel_levels)
    )
    slope, phi, proof = result
    return (
        slope,
        phi,
        proof
        | dict(
            ionic_moiety_fmol=total.tolist(),
            ionic_moiety_ceiling_fmol=None if limit is None else limit.tolist(),
            domain_semantics="declared upper limits, not conserved open-system pools",
        ),
    )


def _decimal(value):
    return Decimal(str(float(value)))


def _membrane_transfers(ion, values):
    ids = [row["id"] for row in ion["species"]]
    mids = [row["id"] for row in ion["membranes"]]
    total = np.array(values["membrane_transferred"], copy=True)
    for j, population in enumerate(ion["channels"]):
        total[:, mids.index(population["membrane_id"])] += values["channel_transferred"][:, j]
    for j, membrane in enumerate(ion["membranes"]):
        if membrane["pump"] is not None:
            roles = membrane["pump"]["roles"]
            total[ids.index(roles["sodium"]), j] += 3 * values["pump_cycles"][j]
            total[ids.index(roles["potassium"]), j] -= 2 * values["pump_cycles"][j]
    return total


def conservation(context, state):
    """Original-anchor physical inventory, ER/plasma capacitor, source and fuel proof."""
    values = unpack(context, state)
    m = context["equation_definition"]["model"]
    ion = m["ionic"]
    base = context["calcium"] if context["finite_fuel"] else context
    ids, cells, outside = (
        [row["id"] for row in ion[key]] for key in ("species", "cells", "extracellular")
    )
    ca, na = (
        ids.index(m["plasma_transport"][key]) for key in ("calcium_species", "sodium_species")
    )
    total = _membrane_transfers(ion, values)
    total[ca] += (
        values["plasma_pump_cycles"]
        + values["plasma_exchange_cycles"]
        + values["calcium_channel_transferred"]
    )
    total[na] -= 3 * values["plasma_exchange_cycles"]
    local = np.array(values["amount_increment"], copy=True)
    exterior = np.array(values["extracellular_amount_increment"], copy=True)
    for j, membrane in enumerate(ion["membranes"]):
        local[:, cells.index(membrane["inside"])] += total[:, j]
        exterior[:, outside.index(membrane["outside"])] -= total[:, j]
    for kind, rows, names in (("junction", local, cells), ("face", exterior, outside)):
        for j, route in enumerate(ion[kind + "s"]):
            rows[:, names.index(route["sender"])] += values[kind + "_transferred"][:, j]
            rows[:, names.index(route["receiver"])] -= values[kind + "_transferred"][:, j]
    exterior -= values["reservoir_supplied"]
    stores = {row["cell_id"]: row["model"] for row in m["stores"]}
    chemical_ledgers, ownership, nonionic = [], [], []
    ionic_delta = values["extracellular_amount_increment"].sum(axis=-1).copy()
    with localcontext() as ctx:
        ctx.prec = 80
        chemical, er_capacitor = Decimal(0), Decimal(0)
        for i, name in enumerate(cells):
            recipe, store = stores[name], base["stores"][i]
            delta = values["chemical_amount_increment"][i]
            parts = [row["id"] for row in recipe["compartments"]]
            species = {row["id"]: row for row in recipe["species"]}
            residual = np.array(delta, copy=True)
            for j, reaction in enumerate(recipe["reactions"]):
                owner = parts.index(reaction["compartment"])
                for k, count in reaction["products"].items():
                    residual[store.ids.index(k), owner] -= count * values["reaction_extent"][i, j]
                for k, count in reaction["reactants"].items():
                    residual[store.ids.index(k), owner] += count * values["reaction_extent"][i, j]
            transfer = np.array(values["er_passive_transferred"][i], copy=True)
            transfer[store.ca] += (
                values["er_pump_transferred"][i, 0] + values["er_release_transferred"][i, 0]
            )
            residual[:, store.cy] += transfer
            residual[:, store.er] -= transfer
            for j, k in enumerate(ids):
                residual[store.ids.index(k), store.cy] -= values["amount_increment"][j, i]
            chemical_ledgers.append(residual)
            weights = np.asarray(
                [[species[k]["moieties"][ion_id] for k in store.ids] for ion_id in ids]
            )
            ownership.append(weights @ delta.sum(axis=-1) - values["amount_increment"][:, i])
            ionic_delta += weights @ delta.sum(axis=-1)
            other = [q for q in recipe["moieties"] if q not in ids]
            nonionic.append(
                np.asarray([[species[k]["moieties"][q] for k in store.ids] for q in other])
                @ delta.sum(axis=-1)
            )
            for j, species_id in enumerate(store.ids):
                for k in range(delta.shape[1]):
                    anchor, change = _decimal(store.n0[j, k]), _decimal(delta[j, k])
                    volume = _decimal(store.volume[k] * store.c0)
                    if anchor + change <= 0:
                        raise ValueError("Nonpositive physical chemical inventory")
                    mu0 = _decimal(species[species_id]["standard_mu_RT"])
                    chemical += (
                        Decimal("0.001")
                        * _decimal(R * ion["temperature_K"])
                        * (
                            (anchor + change) * (mu0 + ((anchor + change) / volume).ln() - 1)
                            - anchor * (mu0 + (anchor / volume).ln() - 1)
                        )
                    )
            cap = _decimal(
                recipe["membrane"]["area_m2"] * recipe["membrane"]["specific_capacitance_F_per_m2"]
            )
            change_q = (
                sum(
                    (
                        _decimal(species[k]["valence"]) * _decimal(delta[j, store.er])
                        for j, k in enumerate(store.ids)
                    ),
                    Decimal(0),
                )
                * _decimal(F)
                * Decimal("1e-15")
            )
            dv = change_q / cap
            er_capacitor += (
                Decimal("0.5e12")
                * cap
                * dv
                * (2 * _decimal(recipe["membrane"]["initial_voltage_V"]) + dv)
            )
        for i, species_id in enumerate(ids):
            for j, owner in enumerate(ion["extracellular"]):
                anchor = _decimal(owner["initial_amount_fmol"][species_id])
                change = _decimal(values["extracellular_amount_increment"][i, j])
                volume = _decimal(owner["volume_pL"])
                if anchor + change <= 0:
                    raise ValueError("Nonpositive exterior physical inventory")
                chemical += (
                    Decimal("0.001")
                    * _decimal(R * ion["temperature_K"])
                    * (
                        (anchor + change) * (((anchor + change) / volume).ln() - 1)
                        - anchor * ((anchor / volume).ln() - 1)
                    )
                )
        raw = kinetic.base.stage(base, flatten(base, values), 0.0)
        matrix, active, reservoir, _, floating, _ = electrical.topology(raw)
        pins = ~active | reservoir
        for group in floating:
            pins[group[0]] = True
        free = np.flatnonzero(~pins)
        n = len(cells)
        z = np.asarray([row["valence"] for row in ion["species"]])[:, None]
        charge_delta = (
            F
            * 1e-15
            * np.sum(
                z * np.c_[values["amount_increment"], values["extracellular_amount_increment"]],
                axis=0,
            )
        )
        phi0 = np.r_[np.zeros(n), [row["boundary_potential_V"] for row in ion["extracellular"]]]
        initial_q = np.r_[base["qi"], base["qo"]]
        phi0[free] = np.linalg.solve(
            matrix[np.ix_(free, free)],
            initial_q[free] - matrix[np.ix_(free, np.flatnonzero(pins))] @ phi0[pins],
        )
        dphi = np.zeros_like(phi0)
        dphi[free] = np.linalg.solve(matrix[np.ix_(free, free)], charge_delta[free])
        capacitor = Decimal(0)
        for row in ion["membranes"]:
            i, j = cells.index(row["inside"]), n + outside.index(row["outside"])
            dv = _decimal(dphi[i] - dphi[j])
            capacitor += (
                Decimal("0.5e12")
                * _decimal(row["capacitance_F"])
                * dv
                * (2 * _decimal(phi0[i] - phi0[j]) + dv)
            )
        heat = sum(
            (
                _decimal(item)
                for key, value in values.items()
                if key.endswith("_dissipated_energy_pJ")
                for item in value.flat
            ),
            Decimal(0),
        )
        external = sum(
            (
                _decimal(item)
                for key in ("reservoir_work_pJ", "electrode_work_pJ")
                for item in values[key].flat
            ),
            Decimal(0),
        )
        pool_energy, pool_material, adenylate, phosphorus = [], [], [], []
        if context["finite_fuel"]:
            internal = np.zeros(n)
            for j, row in enumerate(ion["membranes"]):
                internal[cells.index(row["inside"])] += values["metabolic_work_pJ"][j]
            for j, row in enumerate(m["plasma_transport"]["membranes"]):
                patch = next(v for v in ion["membranes"] if v["id"] == row["membrane_id"])
                internal[cells.index(patch["inside"])] += values["plasma_metabolic_work_pJ"][j]
            internal += values["er_metabolic_work_pJ"]
            demand = np.zeros(n)
            for j, row in enumerate(ion["membranes"]):
                demand[cells.index(row["inside"])] += values["pump_cycles"][j]
            for j, row in enumerate(m["plasma_transport"]["membranes"]):
                patch = next(v for v in ion["membranes"] if v["id"] == row["membrane_id"])
                demand[cells.index(patch["inside"])] += values["plasma_pump_cycles"][j]
            demand += values["er_pump_transferred"][:, 0]
            regeneration, port_balance = np.zeros(n), np.zeros(n)
            pools = {row["id"]: row for row in m["energy_pools"]}
            for j, row in enumerate(m["regeneration_ports"]):
                owner = cells.index(pools[row["pool_id"]]["cell_id"])
                regeneration[owner] += values["regeneration_cycles_fmol"][j]
                port_balance[owner] += (
                    values["regeneration_dissipated_energy_pJ"][j]
                    - values["regeneration_supplied_work_pJ"][j]
                )
            external += sum(
                (_decimal(item) for item in values["regeneration_supplied_work_pJ"].flat),
                Decimal(0),
            )
            by_cell = {row["cell_id"]: row for row in m["energy_pools"]}
            for i, name in enumerate(cells):
                recipe = by_cell[name]
                change = values["energy_amount_increment_fmol"][:, i]
                stored = Decimal(0)
                for j, species_id in enumerate(("ATP", "ADP", "Pi")):
                    anchor, delta = (
                        _decimal(recipe["initial_amount_fmol"][species_id]),
                        _decimal(change[j]),
                    )
                    volume = _decimal(ion["cells"][i]["volume_pL"]) * Decimal(1000)
                    if anchor + delta <= 0:
                        raise ValueError("Finite pool exhausted")
                    stored += _decimal(R * ion["temperature_K"]) * (
                        (anchor + delta) * (((anchor + delta) / volume).ln() - 1)
                        - anchor * ((anchor / volume).ln() - 1)
                    )
                stored = Decimal("0.001") * (
                    stored - _decimal(recipe["delta_g0_J_per_mol"]) * _decimal(change[0])
                )
                chemical += stored
                pool_energy.append(float(stored) + internal[i] + port_balance[i])
                cycle = demand[i] - regeneration[i]
                pool_material.append(change - np.asarray([-cycle, cycle, cycle]))
                adenylate.append(math.fsum((change[0], change[1])))
                phosphorus.append(
                    math.fsum((change[0], change[0], change[0], change[1], change[1], change[2]))
                )
        else:
            external += sum(
                (
                    _decimal(item)
                    for key in (
                        "metabolic_work_pJ",
                        "plasma_metabolic_work_pJ",
                        "er_metabolic_work_pJ",
                    )
                    for item in values[key].flat
                ),
                Decimal(0),
            )
        residual_energy = chemical + capacitor + er_capacitor + heat - external
    cap_delta = matrix @ dphi
    supply_charge = F * 1e-15 * np.sum(z * values["reservoir_supplied"], axis=0)
    boundary = np.asarray([row["boundary_potential_V"] for row in ion["extracellular"]])
    baseline_co = base["ao"] / base["vo"]
    mu = R * ion["temperature_K"] * np.log(baseline_co) + z * F * boundary
    return dict(
        local_material_fmol=local,
        outside_material_fmol=exterior,
        chemical_ledger_fmol=np.asarray(chemical_ledgers),
        ionic_ownership_fmol=np.asarray(ownership),
        nonionic_moiety_fmol=np.asarray(nonionic),
        ionic_global_fmol=ionic_delta - values["reservoir_supplied"].sum(axis=-1),
        capacitor_charge_C=np.where(active & ~reservoir, cap_delta - charge_delta, 0.0),
        electrode_charge_C=values["electrode_charge_transferred_C"]
        - np.where(base["layout"]["reservoir"], cap_delta[n:], 0.0),
        global_charge_C=values["electrode_charge_transferred_C"].sum() + supply_charge.sum(),
        reservoir_work_pJ=values["reservoir_work_pJ"]
        - 1e-3 * np.sum(mu * values["reservoir_supplied"], axis=0),
        electrode_work_pJ=values["electrode_work_pJ"]
        - 1e12 * boundary * values["electrode_charge_transferred_C"],
        chemical_change_pJ=float(chemical),
        plasma_capacitor_change_pJ=float(capacitor),
        er_capacitor_change_pJ=float(er_capacitor),
        dissipated_energy_pJ=float(heat),
        external_work_pJ=float(external),
        energy_residual_pJ=float(residual_energy),
        pool_energy_pJ=np.asarray(pool_energy),
        pool_material_fmol=np.asarray(pool_material),
        adenylate_fmol=np.asarray(adenylate),
        phosphorus_fmol=np.asarray(phosphorus),
    )


def loss_bound(context):
    """Independent scalar majorants on the declared open-domain ceiling box."""
    if context["finite_fuel"]:
        raw = _project(context, context["energy_initial"])
        # Same conserved neutral A/P theorem, derived from actual declared
        # neutral amounts. This is solely a bound-coefficient construction.
        ion = raw["model"]["ionic"]
        by_cell = {
            row["cell_id"]: row for row in context["equation_definition"]["model"]["energy_pools"]
        }
        upper = {}
        for cell in ion["cells"]:
            amount = by_cell[cell["id"]]["initial_amount_fmol"]
            a, d, pi = (amount[k] for k in ("ATP", "ADP", "Pi"))
            upper[cell["id"]] = (
                (a + d) / cell["volume_pL"],
                (3 * a + 2 * d + pi) / cell["volume_pL"],
            )
        patch_owner = {row["id"]: row["inside"] for row in ion["membranes"]}
        routes = [
            (row["model"]["membrane"]["pump"], row["cell_id"]) for row in raw["model"]["stores"]
        ]
        routes += [
            (row["pump"], patch_owner[row["membrane_id"]])
            for row in raw["model"]["plasma_transport"]["membranes"]
        ]
        for pump, owner in routes:
            if pump is not None:
                a, phosphorus = upper[owner]
                pump.update(
                    atp_mM=a,
                    adp_mM=a,
                    pi_mM=phosphorus * (pump["km_atp_mM"] + a) / pump["km_atp_mM"],
                )
    else:
        raw = context["equation_definition"]
    model, ion = raw["model"], raw["model"]["ionic"]
    temperature = ion["temperature_K"]
    ids = [row["id"] for row in ion["species"]]
    ceilings = context["ionic_moiety_ceiling_fmol"]
    if ceilings is None:
        ceilings = ionic_moieties(context, initial(context))
    max_chemical = 0.0
    for row in model["stores"]:
        store = row["model"]
        names = [s["id"] for s in store["species"]]
        species = {s["id"]: s for s in store["species"]}
        volumes = {part["id"]: part["volume_pL"] for part in store["compartments"]}
        totals = {
            q: math.fsum(
                s["moieties"][q] * part["initial_amount_fmol"][s["id"]]
                for part in store["compartments"]
                for s in store["species"]
            )
            for q in store["moieties"]
        }
        totals.update(dict(zip(ids, ceilings, strict=True)))
        upper = {
            name: min(
                totals[q] / count for q, count in species[name]["moieties"].items() if count > 0
            )
            for name in names
        }
        loss = {part: {name: 0.0 for name in names} for part in volumes}
        for reaction in store["reactions"]:
            owner = reaction["compartment"]
            dmu = math.fsum(
                (reaction["products"].get(name, 0) - reaction["reactants"].get(name, 0))
                * species[name]["standard_mu_RT"]
                for name in names
            )
            for side, rate in (
                (reaction["reactants"], reaction["forward_rate_per_s"]),
                (reaction["products"], reaction["forward_rate_per_s"] * math.exp(dmu)),
            ):
                for name, count in side.items():
                    coefficient = count * rate
                    for other, power in side.items():
                        exponent = power - int(other == name)
                        coefficient *= (
                            upper[other] / volumes[owner] / store["standard_concentration_mM"]
                        ) ** exponent
                    loss[owner][name] += coefficient
        membrane = store["membrane"]
        ca = membrane["calcium_species"]
        release = membrane["release"]
        for name in names:
            x = abs(species[name]["valence"]) * F * 0.15 / (R * temperature)
            bernoulli = 1.0 if x == 0 else -x / math.expm1(-x)
            permeability = membrane["permeability_m_per_s"][name]
            if name == ca and release is not None:
                permeability += release["permeability_m_per_s"]
            for part in (membrane["cytosol"], membrane["er"]):
                loss[part][name] += (
                    membrane["area_m2"] / 1e-15 * permeability * bernoulli / volumes[part]
                )
        pump = membrane["pump"]
        if pump is not None:
            saturation = pump["atp_mM"] / (pump["km_atp_mM"] + pump["atp_mM"])
            forward = pump["capacity_fmol_per_s"] * saturation / pump["km_ca_mM"]
            drive = pump["delta_g0_J_per_mol"] + R * temperature * math.log(
                pump["adp_mM"] * pump["pi_mM"] / pump["atp_mM"]
            )
            loss[membrane["cytosol"]][ca] += forward / volumes[membrane["cytosol"]]
            loss[membrane["er"]][ca] += (
                forward
                * math.exp((drive + 2 * F * 0.15) / (R * temperature))
                / volumes[membrane["er"]]
            )
        max_chemical = max(
            max_chemical, *(value for values in loss.values() for value in values.values())
        )
    cells = {row["id"]: row for row in ion["cells"]}
    outside = {row["id"]: row for row in ion["extracellular"]}
    inside = {name: {ion_id: 0.0 for ion_id in ids} for name in cells}
    exterior = {name: {ion_id: 0.0 for ion_id in ids} for name in outside}
    background_inside = deepcopy(inside)
    background_outside = deepcopy(exterior)
    plasma = {row["membrane_id"]: row for row in model["plasma_transport"]["membranes"]}
    channels = {row["membrane_id"]: row for row in model["calcium_channels"]}
    ca, na = (model["plasma_transport"][key] for key in ("calcium_species", "sodium_species"))
    for patch in ion["membranes"]:
        i, o = patch["inside"], patch["outside"]
        vi, vo = cells[i]["volume_pL"], outside[o]["volume_pL"]
        pump, exchanger = plasma[patch["id"]]["pump"], plasma[patch["id"]]["exchanger"]
        if pump is not None:
            coefficient = (
                pump["capacity_fmol_per_s"]
                * pump["atp_mM"]
                / (pump["km_atp_mM"] + pump["atp_mM"])
                / pump["km_ca_mM"]
            )
            drive = pump["delta_g0_J_per_mol"] + R * temperature * math.log(
                pump["adp_mM"] * pump["pi_mM"] / pump["atp_mM"]
            )
            inside[i][ca] += coefficient / vi
            exterior[o][ca] += (
                coefficient * math.exp((drive + 2 * F * 0.15) / (R * temperature)) / vo
            )
        ncx = (
            0.0
            if exchanger is None
            else exchanger["capacity_fmol_per_s"] * math.exp(F * 0.15 / (2 * R * temperature))
        )
        ch = channels[patch["id"]]
        cav = (
            patch["area_m2"]
            * ch["max_permeability_m_per_s"]
            * ch["abundance"]
            / 1e-15
            * (1 + 2 * F * 0.120 / (R * temperature))
        )
        for table, name, volume in ((inside, i, vi), (exterior, o, vo)):
            table[name][ca] += (
                ncx / (1 if exchanger is None else exchanger["km_ca_mM"]) + cav
            ) / volume
            table[name][na] += (
                3 * ncx / (1 if exchanger is None else exchanger["km_na_mM"]) / volume
            )
        for species in ion["species"]:
            name, z = species["id"], species["valence"]
            rate = (
                patch["permeability_m_per_s"][name]
                * patch["area_m2"]
                / 1e-15
                * (1 + abs(z) * F * 0.120 / (R * temperature))
            )
            background_inside[i][name] += rate / vi
            background_outside[o][name] += rate / vo
    max_plasma = max(
        *(
            value
            for table in (inside, exterior)
            for values in table.values()
            for value in values.values()
        )
    )
    max_background = max(
        *(
            value
            for table in (background_inside, background_outside)
            for values in table.values()
            for value in values.values()
        )
    )
    total = max_chemical + max_plasma + (max_background if context["open_world"] else 0.0)
    if not math.isfinite(total):
        raise ValueError("Open-domain majorant is not finite")
    return dict(
        chemical_s_inverse=max_chemical,
        plasma_s_inverse=max_plasma,
        background_s_inverse=max_background,
        total_s_inverse=total,
        ceiling_fmol=np.asarray(ceilings).tolist(),
        scope=(
            "chemical/plasma/background majorants plus inherited kinetic "
            "and strict per-stage transport domains"
        ),
    )


def dependency_manifest(root):
    """Hash actual reference module-import closure and audit own/legacy bodies."""
    root = Path(root).resolve()
    pending, seen = [Path(__file__).resolve()], {}
    while pending:
        path = pending.pop()
        relative = str(path.relative_to(root))
        if relative in seen:
            continue
        legacy = path.parent == root / "tests" and path.name.startswith("reference_")
        source = path.read_bytes()
        tree = ast.parse(source)
        package = path == root / "tests" / "__init__.py"
        if package and any(
            not (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            )
            for node in tree.body
        ):
            raise ValueError("Reference package initializer must contain documentation only")
        if not path.is_relative_to(root / "validation") and not legacy and not package:
            raise ValueError("Non-reference dependency: " + relative)
        seen[relative] = hashlib.sha256(source).hexdigest()
        parents = {
            child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)
        }
        for node in ast.walk(tree):
            parent, nested = parents.get(node), False
            while parent is not None:
                nested |= isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
                parent = parents.get(parent)
            if nested and path != Path(__file__).resolve() and not legacy:
                continue
            if isinstance(node, ast.Import):
                names = [value.name for value in node.names]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level:
                    parts = list(path.relative_to(root).with_suffix("").parts[:-1])
                    module = ".".join(parts[: len(parts) - node.level + 1]) + (
                        "." + module if module else ""
                    )
                names = [module, *(module + "." + value.name for value in node.names)]
            else:
                continue
            for name in names:
                if name.split(".")[0] in {"cells", "jax", "jaxlib"}:
                    raise ValueError("Production/JAX import in reference: " + relative)
                candidate = root.joinpath(*name.split("."))
                for local in (candidate.with_suffix(".py"), candidate / "__init__.py"):
                    if local.is_file():
                        pending.append(local.resolve())
    return dict(sorted(seen.items()))
