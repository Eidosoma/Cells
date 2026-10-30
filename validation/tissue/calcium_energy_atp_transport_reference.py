"""Independent native ATP substrate algebra and actual finite-pool coupling.

No Cells/JAX imports. The native rate is evaluated in 80-digit Decimal; live
pool chemistry is reconstructed independently at its transformed 1-M standard.
Exactly one ATP becomes ADP + Pi per signed cycle. Negative cycles synthesize
ATP, with independent gross directional ledgers and no external fuel supply.
"""

import math
from copy import deepcopy
from numbers import Real

import numpy as np
from scipy.integrate import solve_ivp

from validation.chemistry import finite_energy_reference as fuel
from validation.tissue import calcium_energy_irreversible_transport_reference as physical
from validation.tissue import surface_calcium_energy_reference as energy
from validation.transport import betse_network_transport_reference as native

F, R = energy.F, energy.R
MODEL_ID = "resolved_calcium_energy_atp_transport@1"
FUELS = ("ATP", "ADP", "Pi")
flatten, unpack = energy.flatten, energy.unpack
EXTRA_FIELDS = (
    "network_cycles_fmol",
    "network_transferred_fmol",
    "network_dissipated_energy_pJ",
    "network_fuel_work_pJ",
    "network_chemical_work_pJ",
    "network_electrical_work_pJ",
    "network_gross_hydrolysis_fmol",
    "network_gross_synthesis_fmol",
)
transfer_energy = physical.transfer_energy


def _finite(value, *, positive=False, nonnegative=False):
    return (
        isinstance(value, Real)
        and not isinstance(value, bool)
        and np.isfinite(value)
        and (not positive or value > 0)
        and (not nonnegative or value >= 0)
    )


def _configuration(config, species):
    if (
        config.get("reaction zone") != "cell"
        or config.get("ignore ECM", False) is not False
        or config.get("apply to", "all") != "all"
        or "standard free energy" not in config
        or not _finite(config.get("standard free energy"))
        or not _finite(config.get("max rate"), nonnegative=True)
    ):
        raise ValueError(
            "Require numeric-energy ATP cell-zone transport, finite exterior and all profile"
        )
    all_species = (*species, *FUELS)
    maps, moved = [], []
    for role, multiplier, km_key, transfer in (
        ("reactants", "reactant multipliers", "Km reactants", "transfered into cell"),
        ("products", "product multipliers", "Km products", "transfered out of cell"),
    ):
        names, coefficients, km = config[role], config[multiplier], config[km_key]
        external = config[transfer]
        external = [] if external in (None, "None") else external
        if (
            not isinstance(names, list)
            or not names
            or len(set(names)) != len(names)
            or not set(names) <= set(all_species)
            or not isinstance(coefficients, list)
            or not isinstance(km, list)
            or len(names) != len(coefficients)
            or len(names) != len(km)
            or not all(_finite(v, positive=True) for v in (*coefficients, *km))
            or not isinstance(external, list)
            or len(set(external)) != len(external)
            or not set(external) <= set(names)
        ):
            raise ValueError("Require unique ionic substrates, positive coefficients/Km and owners")
        maps.append(dict(zip(names, coefficients, strict=True)))
        moved.append(external)
    if (
        {k: v for k, v in maps[0].items() if k in FUELS} != {"ATP": 1}
        or {k: v for k, v in maps[1].items() if k in FUELS} != {"ADP": 1, "Pi": 1}
        or {k: v for k, v in maps[0].items() if k not in FUELS}
        != {k: v for k, v in maps[1].items() if k not in FUELS}
        or set(FUELS) & (set(moved[0]) | set(moved[1]))
    ):
        raise ValueError("Require exactly ATP -> ADP + Pi, preserved ions and internal fuels")
    nu = np.array([maps[0].get(s, 0) * ((s in moved[1]) - (s in moved[0])) for s in species])
    if not np.any(nu):
        raise ValueError("Require at least one net transported species")
    # Ionic terms cancel in list count and coefficients. ATP -> ADP + Pi
    # leaves one literal 1e-3, exactly the transformed 1-M hydrolysis quotient.
    modes = []
    for activating, label, km_key, power_key in (
        (True, "transporter activators", "activator Km", "activator n"),
        (False, "transporter inhibitors", "inhibitor Km", "inhibitor n"),
    ):
        names = config.get(label)
        if names in (None, "None") or names == []:
            continue
        km, powers = config.get(km_key), config.get(power_key)
        if (
            not isinstance(names, list)
            or not isinstance(km, list)
            or not isinstance(powers, list)
            or len(names) != len(km)
            or len(names) != len(powers)
            or not all(_finite(v, positive=True) for v in (*km, *powers))
        ):
            raise ValueError("Require matching native regulator/Km/exponent lists")
        for index, name in enumerate(names):
            if not isinstance(name, str):
                raise ValueError("Invalid native regulator")
            name = name[:-1] if name.endswith("*") else name
            mode = name[-1:] if name.endswith(("!", "&")) else ""
            name = name[:-1] if mode else name
            if name not in all_species or (
                not activating and mode == "&" and index != len(names) - 1
            ):
                raise ValueError("Unknown regulator or unsupported direct-inhibitor order")
            modes.append((activating, mode))
    if modes and all(mode == "&" for _, mode in modes) and {v[0] for v in modes} == {False, True}:
        raise ValueError("Native only-direct activation/inhibition combination is undefined")
    return nu


def bind(raw):
    m = raw["model"]
    if m["id"] != MODEL_ID or m["ionic"]["id"] != "resolved_tissue@12":
        raise ValueError(
            "Require the explicit calcium/energy transport and 56-law ionic identities"
        )
    projected = deepcopy(raw)
    projected["model"]["id"] = "resolved_calcium_energy@5"
    group = projected["model"].pop("network_transport")
    schedules = projected["experiment"].pop("network_transport_controls")
    capacity = projected["execution"].pop("network_transport_capacity")
    if (
        set(group) != {"law", "constants", "accounting", "routes"}
        or group["law"] != "betse_network_transporter_source_v1_5_0@1"
        or group["accounting"] != "finite_pool_atp_hydrolysis_species_transport@1"
        or group["constants"]
        != dict(
            faraday_C_mol=F,
            gas_constant_J_mol_K=R,
            ionic_standard_state_mM=1.0,
            fuel_standard_state_mM=1000.0,
        )
    ):
        raise ValueError("Require declared source law, matching physical constants and accounting")
    base = energy.bind(projected)
    ion, routes = m["ionic"], group["routes"]
    if type(capacity) is not int or capacity < len(routes):
        raise ValueError("Network capacity must hold all explicit routes")
    ids = [row["id"] for row in ion["species"]]
    if set(ids) & set(FUELS):
        raise ValueError("Neutral fuel pools cannot be duplicated as ionic species")
    cells, outside = [v["id"] for v in ion["cells"]], [v["id"] for v in ion["extracellular"]]
    patches = {v["id"]: v for v in ion["membranes"]}
    names, config_names, owners, stoich = [], [], [], []
    for row in routes:
        if (
            set(row) != {"id", "membrane_id", "density_multiplier", "configuration", "drive"}
            or not isinstance(row["id"], str)
            or not row["id"]
            or row["id"] in names
            or row["membrane_id"] not in patches
            or not _finite(row["density_multiplier"], nonnegative=True)
        ):
            raise ValueError("Require unique route IDs, physical membranes and nonnegative density")
        config, drive = row["configuration"], row["drive"]
        stoich.append(_configuration(config, ids))
        name = config.get("name")
        if not isinstance(name, str) or not name or name in config_names:
            raise ValueError("Native configuration names must be unique")
        patch = patches[row["membrane_id"]]
        pool = base["pools"].get(drive.get("pool_id"))
        if (
            set(drive) != {"kind", "pool_id", "atp_per_cycle"}
            or drive["kind"] != "finite_energy_pool_hydrolysis@1"
            or isinstance(drive["atp_per_cycle"], bool)
            or drive["atp_per_cycle"] != 1
            or pool is None
            or pool["cell_id"] != patch["inside"]
            or config["standard free energy"] != pool["delta_g0_J_per_mol"]
        ):
            raise ValueError("Require one ATP from the membrane owner's actual 1-M pool")
        owners.append((cells.index(patch["inside"]), outside.index(patch["outside"])))
        names.append(row["id"])
        config_names.append(name)
    controls = {}
    for row in schedules:
        name, schedule = row["transporter_id"], row["schedule"]
        if name in controls or not schedule:
            raise ValueError("Duplicate or empty network control schedule")
        times = [v["time"] for v in schedule]
        if (
            times[0] != 0
            or any(not _finite(v, nonnegative=True) for v in times)
            or any(b <= a for a, b in zip(times[:-1], times[1:], strict=True))
            or times[-1] > raw["experiment"]["end_time"]
            or any(
                not _finite(v["availability"], nonnegative=True) or v["availability"] > 1
                for v in schedule
            )
        ):
            raise ValueError("Require finite right-continuous network controls")
        controls[name] = deepcopy(schedule)
    if set(controls) != set(names):
        raise ValueError("Every native route requires exactly one control schedule")
    for store in base["stores"]:
        if store.c0 != 1 or any(store.mu0[store.ids.index(s)] != 0 for s in ids):
            raise ValueError(
                "Transferred ionic species require the shared 1-mM zero standard state"
            )
    return dict(
        base,
        raw=deepcopy(raw),
        energy=base,
        network_ids=names,
        network_species=ids,
        network_owners=owners,
        network_controls=controls,
        network_nu=np.asarray(stoich, dtype=float).reshape(len(routes), len(ids)).T,
        shapes=base["shapes"]
        | {
            key: ((len(ids), len(routes)) if key == "network_transferred_fmol" else (len(routes),))
            for key in EXTRA_FIELDS
        },
    )


def initial(c):
    values = unpack(c["energy"], energy.initial(c["energy"]))
    values.update({key: np.zeros(c["shapes"][key]) for key in EXTRA_FIELDS})
    return flatten(c, values)


def _concentrations(c, d):
    inside = (
        np.stack(
            [
                (store.n0 + d["chemical_amount_increment"][i])[
                    [store.ids.index(s) for s in c["network_species"]], store.cy
                ]
                for i, store in enumerate(c["stores"])
            ],
            axis=1,
        )
        / c["vi"]
    )
    outside = (c["ao"] + d["extracellular_amount_increment"]) / c["vo"]
    return inside, outside


def evaluate(c, state, time, *, channel_levels=None):
    value = np.asarray(state)
    if value.shape != initial(c).shape or not np.isfinite(value).all():
        raise ValueError("Require the complete finite46-field ATP transport state")
    d = unpack(c, value)
    if any(
        np.any(d[key] < 0)
        for key in (
            "network_dissipated_energy_pJ",
            "network_gross_hydrolysis_fmol",
            "network_gross_synthesis_fmol",
        )
    ):
        raise ValueError("Negative physical dissipation or gross fuel turnover")
    if (
        np.max(
            np.abs(
                d["network_chemical_work_pJ"]
                + d["network_electrical_work_pJ"]
                + d["network_dissipated_energy_pJ"]
                - d["network_fuel_work_pJ"]
            ),
            initial=0,
        )
        > 3e-12
    ):
        raise ValueError("Ionic/electrical/heat/internal fuel work ledger disagrees")
    if (
        np.max(
            np.abs(
                d["network_cycles_fmol"]
                - d["network_gross_hydrolysis_fmol"]
                + d["network_gross_synthesis_fmol"]
            ),
            initial=0,
        )
        > 2e-12
    ):
        raise ValueError("Gross fuel turnover disagrees with signed cycles")
    if (
        np.max(
            np.abs(d["network_transferred_fmol"] - c["network_nu"] * d["network_cycles_fmol"]),
            initial=0,
        )
        > 3e-13
    ):
        raise ValueError("Ionic transfer ledger disagrees with route cycles")
    base_rate, phi, proof = energy.evaluate(
        c["energy"], flatten(c["energy"], d), time, channel_levels=channel_levels
    )
    result = unpack(c["energy"], base_rate)
    ci, co = _concentrations(c, d)
    amount = c["energy_initial"] + d["energy_amount_increment_fmol"]
    pools = [
        fuel.thermodynamics(
            amount[:, i], c["energy_volumes"][i], c["temperature"], c["energy_delta_g0"][i]
        )
        for i in range(len(c["vi"]))
    ]
    ion, routes = c["raw"]["model"]["ionic"], c["raw"]["model"]["network_transport"]["routes"]
    ion_z = {row["id"]: row["valence"] for row in ion["species"]}
    native_z = ion_z | dict.fromkeys(FUELS, 0)
    patches = {row["id"]: row for row in ion["membranes"]}
    cycles, heat, released, source, chem, electric, hydrolysis, reaction, alpha, current = (
        np.zeros(len(routes)) for _ in range(10)
    )
    chemical_power, electrical_power = np.zeros(len(routes)), np.zeros(len(routes))
    transferred = np.zeros((len(ion_z), len(routes)))
    cell_rate, outside_rate = np.zeros_like(ci), np.zeros_like(co)
    for j, row in enumerate(routes):
        i, o = c["network_owners"][j]
        voltage = float(phi[i] - phi[len(c["vi"]) + o])
        opening = next(
            entry["availability"]
            for entry in reversed(c["network_controls"][row["id"]])
            if entry["time"] <= time
        )
        native_result = native.evaluate(
            row["configuration"],
            dict(zip(c["network_species"], ci[:, i], strict=True))
            | dict(zip(FUELS, pools[i]["concentration_mM"], strict=True)),
            dict(zip(c["network_species"], co[:, o], strict=True)) | dict.fromkeys(FUELS, 0.0),
            native_z,
            voltage_V=voltage,
            temperature_K=c["temperature"],
            area_m2=patches[row["membrane_id"]]["area_m2"],
            availability=opening,
            rho=row["density_multiplier"],
        )
        if not all(np.isfinite(v) for key, v in native_result.items() if key != "amount_fmol_s"):
            raise ValueError("Nonfinite independent native ATP rate")
        cycles[j], source[j], alpha[j] = (
            native_result["extent_fmol_s"],
            native_result["source_reaction_energy_J_mol"],
            native_result["regulation"],
        )
        chem[j], electric[j] = transfer_energy(
            ci[:, i],
            co[:, o],
            c["network_nu"][:, j],
            list(ion_z.values()),
            voltage,
            c["temperature"],
        )
        hydrolysis[j] = pools[i]["hydrolysis_free_energy_J_mol"]
        reaction[j] = hydrolysis[j] + chem[j] + electric[j]
        if abs(source[j] - reaction[j]) > 3e-9 + 3e-12 * abs(reaction[j]):
            raise ValueError("Native literal quotient disagrees with physical 1-M fuel affinity")
        chemical_power[j], electrical_power[j] = (
            1e-3 * cycles[j] * v for v in (chem[j], electric[j])
        )
        released[j] = -1e-3 * cycles[j] * hydrolysis[j]
        heat[j] = -1e-3 * cycles[j] * reaction[j]
        if not np.isfinite(heat[j]) or heat[j] < 0:
            raise ValueError("Signed native rate yields negative physical dissipation")
        transferred[:, j] = c["network_nu"][:, j] * cycles[j]
        current[j] = F * 1e-15 * np.dot(list(ion_z.values()), transferred[:, j])
        cell_rate[:, i] -= transferred[:, j]
        outside_rate[:, o] += transferred[:, j]
        store = c["stores"][i]
        for s, name in enumerate(c["network_species"]):
            result["chemical_amount_increment"][i, store.ids.index(name), store.cy] -= transferred[
                s, j
            ]
    pool_owners = [int(i) for i, _ in c["network_owners"]]
    route_exchange = fuel.exchange(cycles.tolist(), pool_owners, [], [], len(c["vi"]))
    pool_rate = np.asarray(route_exchange["amount_fmol_s"])
    pool_power = sum(
        1e-3 * np.dot(pool["chemical_potential_J_mol"], pool_rate[:, i])
        for i, pool in enumerate(pools)
    )
    result["energy_amount_increment_fmol"] += pool_rate
    result["amount_increment"] += cell_rate
    result["extracellular_amount_increment"] += outside_rate
    result.update(
        network_cycles_fmol=cycles,
        network_transferred_fmol=transferred,
        network_dissipated_energy_pJ=heat,
        network_fuel_work_pJ=released,
        network_chemical_work_pJ=chemical_power,
        network_electrical_work_pJ=electrical_power,
        network_gross_hydrolysis_fmol=np.maximum(cycles, 0),
        network_gross_synthesis_fmol=np.maximum(-cycles, 0),
    )
    combined = _combined_exchange(c, result)
    balance = chemical_power + electrical_power + heat - released
    return (
        flatten(c, result),
        phi,
        proof
        | dict(
            physical_energy_balance_pJ_s=proof["physical_energy_balance_pJ_s"]
            + float(chemical_power.sum() + electrical_power.sum() + heat.sum() + pool_power),
            network_energy_balance_pJ_s=balance.tolist(),
            network_physical_reaction_energy_J_mol=reaction.tolist(),
            network_fuel_hydrolysis_energy_J_mol=hydrolysis.tolist(),
            network_physical_chemical_energy_J_mol=chem.tolist(),
            network_physical_electrical_energy_J_mol=electric.tolist(),
            network_chemical_power_pJ_s=chemical_power.tolist(),
            network_electrical_power_pJ_s=electrical_power.tolist(),
            network_fuel_power_pJ_s=released.tolist(),
            network_source_reaction_energy_J_mol=source.tolist(),
            network_regulation=alpha.tolist(),
            network_outward_current_C_s=current.tolist(),
            network_cell_rate_fmol_s=cell_rate.tolist(),
            network_outside_rate_fmol_s=outside_rate.tolist(),
            network_pool_rate_fmol_s=pool_rate.tolist(),
            pool_gross_hydrolysis_fmol_s=combined["gross_hydrolysis_fmol_s"],
            pool_gross_synthesis_fmol_s=combined["gross_synthesis_fmol_s"],
        ),
    )


def _combined_exchange(c, values):
    n = len(c["cell_ids"])
    rates = [
        *values["pump_cycles"],
        *values["plasma_pump_cycles"],
        *values["er_pump_transferred"][:, 0],
        *values["network_cycles_fmol"],
    ]
    owners = [
        *c["patch_owners"],
        *c["plasma_owners"],
        *range(n),
        *(int(i) for i, _ in c["network_owners"]),
    ]
    ports = c["raw"]["model"]["regeneration_ports"]
    regen_owners = [c["cell_ids"].index(c["pools"][p["pool_id"]]["cell_id"]) for p in ports]
    return fuel.exchange(rates, owners, list(values["regeneration_cycles_fmol"]), regen_owners, n)


def material_balance(c, state):
    d = unpack(c, state)
    expected = np.asarray(_combined_exchange(c, d)["amount_fmol_s"])
    delta = d["energy_amount_increment_fmol"]
    return dict(
        pool_material_fmol=(delta - expected).tolist(),
        adenylate_fmol=(delta[0] + delta[1]).tolist(),
        phosphorus_fmol=(3 * delta[0] + 2 * delta[1] + delta[2]).tolist(),
    )


def stored_energy_change(c, state, reference_state=None, *, time=0.0, reference_time=0.0):
    # Reuse only independently derived physical store energies. Supplying the
    # full new reference state avoids that helper's old-model initialization.
    return physical.stored_energy_change(
        c,
        state,
        initial(c) if reference_state is None else reference_state,
        time=time,
        reference_time=reference_time,
    )


def endpoint_balance(c, state, *, time=0.0):
    values = unpack(c, state)
    stored = stored_energy_change(c, state, time=time)
    heat = math.fsum(
        float(np.sum(v)) for k, v in values.items() if k.endswith("_dissipated_energy_pJ")
    )
    supply = float(np.sum(values["regeneration_supplied_work_pJ"]))
    return stored | dict(
        dissipated_pJ=heat, supplied_pJ=supply, balance_pJ=stored["total_pJ"] + heat - supply
    )


ReferenceIntegrationError = energy.ReferenceIntegrationError


def integrate(raw, *, refinement=1, max_step_s=1.25e-6, channel_segments=None):
    if type(refinement) is not int or refinement < 1 or not _finite(max_step_s, positive=True):
        raise ValueError("Require positive integer refinement and finite positive max step")
    c, e = bind(raw), raw["experiment"]
    segments = [(0.0, None)] if channel_segments is None else channel_segments
    if (
        not segments
        or segments[0][0] != 0
        or any(not _finite(t, nonnegative=True) or t > e["end_time"] for t, _ in segments)
        or any(b[0] <= a[0] for a, b in zip(segments[:-1], segments[1:], strict=True))
    ):
        raise ValueError("Require ordered assembly owner levels from zero")
    events = {0.0, e["end_time"], *(t for t, _ in segments)}
    for kind, groups in e.items():
        if kind.endswith("_controls"):
            events.update(
                row["time"]
                for group in groups
                for row in group.get("schedule", group.get("controls", []))
            )
    events = sorted(events)
    times, current, evaluations = e["observation_times"], initial(c), 0
    saved = {0.0: current.copy()}
    atol = flatten(
        c,
        {
            name: np.full(shape, (1e-29 if name.endswith("_C") else 2e-14) / refinement)
            for name, shape in c["shapes"].items()
        },
    )

    def rhs(t, state, held, levels):
        nonlocal evaluations
        evaluations += 1
        try:
            return evaluate(c, state, held, channel_levels=levels)[0]
        except Exception as error:
            raise ReferenceIntegrationError(
                str(error),
                dict(
                    time_s=float(t),
                    held_control_time_s=float(held),
                    state=[float(v) if np.isfinite(v) else str(v) for v in state],
                    evaluations=evaluations,
                    automatic_retry=False,
                ),
            ) from error

    for left, right in zip(events[:-1], events[1:], strict=True):
        level = next(v for t, v in reversed(segments) if t <= left)
        answer = solve_ivp(
            lambda t, state, held=left, levels=level: rhs(t, state, held, levels),
            (left, right),
            current,
            method="DOP853",
            rtol=2e-11 / refinement,
            atol=atol,
            max_step=max_step_s / refinement,
            dense_output=True,
        )
        if not answer.success:
            raise ReferenceIntegrationError(
                answer.message,
                dict(
                    time_s=float(answer.t[-1]),
                    state=answer.y[:, -1].tolist(),
                    evaluations=evaluations,
                    automatic_retry=False,
                ),
            )
        for t in times:
            if left < t <= right:
                saved[t] = answer.y[:, -1].copy() if t == right else answer.sol(t)
        current = answer.y[:, -1].copy()
    potentials = [
        evaluate(
            c, saved[t], t, channel_levels=next(v for left, v in reversed(segments) if left <= t)
        )[1]
        for t in times
    ]
    return dict(
        times=times,
        state=np.stack([saved[t] for t in times]),
        potential_V=np.stack(potentials),
        evaluations=evaluations,
        refinement=refinement,
        event_times=events,
        method="DOP853; all control events, owned chemical and native extent loops",
        rtol=2e-11 / refinement,
        amount_energy_gate_atol=2e-14 / refinement,
        electrode_charge_atol_C=1e-29 / refinement,
        max_step_s=max_step_s / refinement,
    )
