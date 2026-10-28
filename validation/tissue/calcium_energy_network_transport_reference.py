"""Independent native pure transport with owned calcium/ER and finite fuel.

The existing 80-digit native source law supplies signed configured extents.
Only reversible, species-preserving transport with nonnegative regulation is
admitted to the physical energy ledger. No Cells/JAX imports or projections.
"""

import math
from copy import deepcopy
from numbers import Real

import numpy as np
from scipy.integrate import solve_ivp

from validation.chemistry import finite_energy_reference as fuel
from validation.tissue import surface_calcium_energy_reference as energy
from validation.tissue import surface_field_reference as electrical
from validation.transport import betse_network_transport_reference as native

F, R = energy.F, energy.R
MODEL_ID = "resolved_calcium_energy_transport@1"
flatten, unpack = energy.flatten, energy.unpack
EXTRA_FIELDS = (
    "network_cycles_fmol",
    "network_transferred_fmol",
    "network_dissipated_energy_pJ",
    "network_supplied_work_pJ",
)


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
        or config.get("ignore ECM") is not False
        or config.get("apply to") != "all"
        or not _finite(config.get("standard free energy"))
        or not _finite(config.get("max rate"), nonnegative=True)
    ):
        raise ValueError("Require reversible cell-zone transport, finite exterior and all profile")
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
            or not set(names) <= set(species)
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
    if maps[0] != maps[1]:
        raise ValueError("Only identical species/coefficient maps have physical transport ledgers")
    nu = np.array([maps[0].get(s, 0) * ((s in moved[1]) - (s in moved[0])) for s in species])
    if not np.any(nu):
        raise ValueError("Require at least one net transported species")
    # Duplicate list entries were rejected: identical maps also have equal item
    # counts, so the native Q's literal 1e-3 factors cancel exactly in this subset.
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
            if name not in species or (not activating and mode == "&" and index != len(names) - 1):
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
        or group["accounting"] != "reversible_pure_transport_maintained_drive@1"
        or group["constants"] != dict(faraday_C_mol=F, gas_constant_J_mol_K=R)
    ):
        raise ValueError("Require declared source law, matching physical constants and accounting")
    base = energy.bind(projected)
    ion, routes = m["ionic"], group["routes"]
    if type(capacity) is not int or capacity < len(routes):
        raise ValueError("Network capacity must hold all explicit routes")
    ids = [row["id"] for row in ion["species"]]
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
        if (
            set(drive) != {"kind", "supplied_energy_J_per_mol"}
            or drive["kind"] != "maintained_work_per_cycle@1"
            or not _finite(drive["supplied_energy_J_per_mol"])
            or drive["supplied_energy_J_per_mol"] != -config["standard free energy"]
        ):
            raise ValueError("Signed maintained work must be exactly negative native G0")
        patch = patches[row["membrane_id"]]
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
        | dict(
            network_cycles_fmol=(len(routes),),
            network_transferred_fmol=(len(ids), len(routes)),
            network_dissipated_energy_pJ=(len(routes),),
            network_supplied_work_pJ=(len(routes),),
        ),
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
    if not np.isfinite(state).all():
        raise ValueError("Complete network/calcium/fuel state must be finite")
    d = unpack(c, state)
    if np.any(d["network_dissipated_energy_pJ"] < -2e-14):
        raise ValueError("Negative accumulated physical network dissipation")
    base_rate, phi, proof = energy.evaluate(
        c["energy"], flatten(c["energy"], d), time, channel_levels=channel_levels
    )
    result = unpack(c["energy"], base_rate)
    ci, co = _concentrations(c, d)
    ion, routes = c["raw"]["model"]["ionic"], c["raw"]["model"]["network_transport"]["routes"]
    z = {v["id"]: v["valence"] for v in ion["species"]}
    patches = {v["id"]: v for v in ion["membranes"]}
    cycles, heat, work, reaction, physical, alpha, current = (
        np.zeros(len(routes)) for _ in range(7)
    )
    transferred = np.zeros((len(z), len(routes)))
    cell_rate, outside_rate = np.zeros_like(ci), np.zeros_like(co)
    for j, row in enumerate(routes):
        i, o = c["network_owners"][j]
        voltage = float(phi[i] - phi[len(c["vi"]) + o])
        opening = next(
            v["availability"]
            for v in reversed(c["network_controls"][row["id"]])
            if v["time"] <= time
        )
        readout = native.evaluate(
            row["configuration"],
            dict(zip(c["network_species"], ci[:, i], strict=True)),
            dict(zip(c["network_species"], co[:, o], strict=True)),
            z,
            voltage_V=voltage,
            temperature_K=c["temperature"],
            area_m2=patches[row["membrane_id"]]["area_m2"],
            availability=opening,
            rho=row["density_multiplier"],
        )
        if readout["regulation"] < 0 or not all(
            np.isfinite(v) for k, v in readout.items() if k != "amount_fmol_s"
        ):
            raise ValueError(
                "Require nonnegative native regulation and finite source rates, even blocked"
            )
        cycles[j], reaction[j], alpha[j] = (
            readout["extent_fmol_s"],
            readout["source_reaction_energy_J_mol"],
            readout["regulation"],
        )
        transferred[:, j] = c["network_nu"][:, j] * cycles[j]
        current[j] = F * 1e-15 * np.dot(list(z.values()), transferred[:, j])
        chemical = R * c["temperature"] * np.log(co[:, o] / ci[:, i])
        electrical = -F * voltage * np.array(list(z.values()))
        physical[j] = np.dot(c["network_nu"][:, j], chemical + electrical)
        heat[j] = -1e-3 * cycles[j] * reaction[j]
        work[j] = 1e-3 * cycles[j] * row["drive"]["supplied_energy_J_per_mol"]
        cell_rate[:, i] -= transferred[:, j]
        outside_rate[:, o] += transferred[:, j]
        store = c["stores"][i]
        for s, name in enumerate(c["network_species"]):
            result["chemical_amount_increment"][i, store.ids.index(name), store.cy] -= transferred[
                s, j
            ]
    result["amount_increment"] += cell_rate
    result["extracellular_amount_increment"] += outside_rate
    result.update(
        network_cycles_fmol=cycles,
        network_transferred_fmol=transferred,
        network_dissipated_energy_pJ=heat,
        network_supplied_work_pJ=work,
    )
    balance = 1e-3 * physical * cycles + heat - work
    return (
        flatten(c, result),
        phi,
        proof
        | dict(
            physical_energy_balance_pJ_s=proof["physical_energy_balance_pJ_s"]
            + float(balance.sum()),
            network_energy_balance_pJ_s=balance.tolist(),
            network_physical_transfer_energy_J_mol=physical.tolist(),
            network_source_reaction_energy_J_mol=reaction.tolist(),
            network_regulation=alpha.tolist(),
            network_outward_current_C_s=current.tolist(),
            network_cell_rate_fmol_s=cell_rate.tolist(),
            network_outside_rate_fmol_s=outside_rate.tolist(),
            network_direct_atp_demand_fmol_s=[0.0] * len(c["vi"]),
        ),
    )


def _potential(c, d, time):
    calcium = c["energy"]["calcium"]
    raw = energy.calcium.kinetic.base.stage(calcium, flatten(calcium, d), time)
    raw["ci"], _ = _concentrations(c, d)
    raw["junction_open"] = np.asarray(raw["junction_open"]) * d["junction_gate"]
    return electrical.solve(raw)[0]


def _mixing_change(before, after, volume, standard=1.0, mu0=0.0, difference=None):
    if np.any(before <= 0) or np.any(after <= 0):
        raise ValueError("Stored energy requires positive species amounts")
    difference = after - before if difference is None else difference
    return np.sum(
        difference * (mu0 + np.log(before / (volume * standard)) - 1)
        + after * np.log1p(difference / before)
    )


def stored_energy_change(c, state, reference_state=None, *, time=0.0, reference_time=0.0):
    """Physical endpoint energy, counting chemical, fuel and capacitor stores once."""
    a = unpack(c, initial(c) if reference_state is None else reference_state)
    b = unpack(c, state)
    chemical, er_electric, pools = 0.0, 0.0, 0.0
    for i, store in enumerate(c["stores"]):
        before, after = (store.n0 + values["chemical_amount_increment"][i] for values in (a, b))
        chemical += (
            1e-3
            * store.rt
            * _mixing_change(
                before,
                after,
                store.volume,
                store.c0,
                store.mu0[:, None],
                b["chemical_amount_increment"][i] - a["chemical_amount_increment"][i],
            )
        )
        voltages = [
            store.membrane["initial_voltage_V"]
            + F
            * 1e-15
            / store.cap
            * math.fsum(store.z * values["chemical_amount_increment"][i, :, store.er])
            for values in (a, b)
        ]
        er_electric += (
            0.5e12 * store.cap * (voltages[1] - voltages[0]) * (voltages[1] + voltages[0])
        )
        pools += fuel.free_energy_change(
            c["energy_initial"][:, i] + a["energy_amount_increment_fmol"][:, i],
            c["energy_initial"][:, i] + b["energy_amount_increment_fmol"][:, i],
            c["energy_volumes"][i],
            c["energy_volumes"][i],
            c["temperature"],
            c["energy_delta_g0"][i],
        )
    chemical += (
        1e-3
        * R
        * c["temperature"]
        * _mixing_change(
            c["ao"] + a["extracellular_amount_increment"],
            c["ao"] + b["extracellular_amount_increment"],
            c["vo"],
            difference=b["extracellular_amount_increment"] - a["extracellular_amount_increment"],
        )
    )
    pa, pb = _potential(c, a, reference_time), _potential(c, b, time)
    electric = 0.0
    for patch in c["raw"]["model"]["ionic"]["membranes"]:
        cells = [v["id"] for v in c["raw"]["model"]["ionic"]["cells"]]
        exterior = [v["id"] for v in c["raw"]["model"]["ionic"]["extracellular"]]
        i, o = cells.index(patch["inside"]), len(cells) + exterior.index(patch["outside"])
        va, vb = pa[i] - pa[o], pb[i] - pb[o]
        electric += 0.5e12 * patch["capacitance_F"] * (vb - va) * (vb + va)
    return dict(
        chemical_pJ=float(chemical),
        membrane_capacitor_pJ=float(electric),
        er_capacitor_pJ=float(er_electric),
        pool_pJ=float(pools),
        total_pJ=float(chemical + electric + er_electric + pools),
    )


def endpoint_balance(c, state, *, time=0.0):
    values = unpack(c, state)
    stored = stored_energy_change(c, state, time=time)
    heat = math.fsum(
        float(np.sum(v)) for k, v in values.items() if k.endswith("_dissipated_energy_pJ")
    )
    work = float(
        np.sum(values["regeneration_supplied_work_pJ"]) + np.sum(values["network_supplied_work_pJ"])
    )
    return stored | dict(
        dissipated_pJ=heat, supplied_pJ=work, balance_pJ=stored["total_pJ"] + heat - work
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
