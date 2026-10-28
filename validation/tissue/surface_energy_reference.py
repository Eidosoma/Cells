"""Independent full-node ionic and Decimal finite-energy reference equations.

No production Cells/JAX imports or production schema/model projections. The
initial maintained-pool representation is reconstructed here from raw owners;
every subsequent pump stage receives the current finite pool concentrations.
"""

from copy import deepcopy

import numpy as np
from scipy.integrate import solve_ivp

from validation.chemistry import finite_energy_reference as chemistry
from validation.tissue import surface_kinetic_reference as ionic

F, R = ionic.F, ionic.R
flatten, unpack = ionic.flatten, ionic.unpack
CONTROL_KINDS = ("membrane", "junction", "channel", "pump", "regeneration")
ENERGY_FIELDS = (
    "energy_amount_increment_fmol",
    "regeneration_cycles_fmol",
    "regeneration_dissipated_energy_pJ",
    "regeneration_supplied_work_pJ",
)


def bind(raw):
    if raw["model"]["id"] != "resolved_energy@1" or raw["model"]["temperature_K"] != 298.15:
        raise ValueError("Require resolved_energy@1 and unscaled 298.15-K shared channels")
    model = raw["model"]
    if any(row["reservoir"] for row in model["extracellular"]):
        raise ValueError("Finite-energy reference requires closed outside owners")
    cells = [cell["id"] for cell in model["cells"]]
    pools = {pool["id"]: pool for pool in model["energy_pools"]}
    by_cell = {pool["cell_id"]: pool for pool in pools.values()}
    if len(pools) != len(cells) or set(by_cell) != set(cells):
        raise ValueError("Each cell requires exactly one independent finite energy pool")
    volumes = np.array([cell["volume_pL"] for cell in model["cells"]])
    initial_amount = np.array(
        [
            [by_cell[cell]["initial_amount_fmol"][species] for cell in cells]
            for species in ("ATP", "ADP", "Pi")
        ]
    )
    delta = np.array([by_cell[cell]["delta_g0_J_per_mol"] for cell in cells])
    for i, cell in enumerate(cells):
        if by_cell[cell]["law"] != "finite_atp_adp_pi_transformed@1":
            raise ValueError("Unsupported finite pool law")
        chemistry.thermodynamics(initial_amount[:, i], volumes[i], model["temperature_K"], delta[i])
    projected = deepcopy(raw)
    m = projected["model"]
    m["id"] = "resolved_tissue@7"
    m.pop("energy_pools")
    ports = m.pop("regeneration_ports")
    projected["experiment"].pop("regeneration_controls")
    projected["execution"].pop("regeneration_capacity")
    for patch in m["membranes"]:
        pump = patch["pump"]
        if pump is None:
            continue
        meta = pump["metabolism"]
        if set(meta) != {"kind", "pool_id"} or meta["kind"] != "finite_energy_pool@1":
            raise ValueError("Require explicit finite-pool pump references")
        pool = pools[meta["pool_id"]]
        if pool["cell_id"] != patch["inside"]:
            raise ValueError("Pump consumes its inside cell's pool")
        i = cells.index(pool["cell_id"])
        pump["metabolism"] = dict(
            kind="maintained_chemical_reservoirs@1",
            **dict(
                zip(
                    ("atp_mM", "adp_mM", "pi_mM"),
                    (float(v) for v in initial_amount[:, i] / volumes[i]),
                    strict=True,
                )
            ),
            delta_g0_J_per_mol=float(delta[i]),
        )
    base = ionic.bind(projected)
    shape = base["shapes"] | dict(
        energy_amount_increment_fmol=(3, len(cells)),
        regeneration_cycles_fmol=(len(ports),),
        regeneration_dissipated_energy_pJ=(len(ports),),
        regeneration_supplied_work_pJ=(len(ports),),
    )
    for port in ports:
        if port["pool_id"] not in pools or port["law"] != "driven_atp_regeneration_tanh@1":
            raise ValueError("Regeneration requires its declared owner and law")
    return dict(
        base,
        raw=deepcopy(raw),
        ionic=base,
        shapes=shape,
        energy_initial=initial_amount,
        energy_delta_g0=delta,
        cell_ids=cells,
        pools=pools,
        energy_volumes=volumes,
    )


def initial(c):
    d = unpack(c["ionic"], ionic.initial(c["ionic"]))
    d.update({name: np.zeros(c["shapes"][name]) for name in ENERGY_FIELDS})
    return flatten(c, d)


def evaluate(c, state, time):
    d = unpack(c, state)
    amount = c["energy_initial"] + d["energy_amount_increment_fmol"]
    if not np.isfinite(amount).all() or np.any(amount <= 0):
        raise ValueError("Independent finite-energy stage exhausted its positive pools")
    stage_raw = deepcopy(c["ionic"]["raw"])
    m = stage_raw["model"]
    temperature = m["temperature_K"]
    for patch in m["membranes"]:
        pump = patch["pump"]
        if pump is None:
            continue
        owner = c["cell_ids"].index(patch["inside"])
        pump["metabolism"].update(
            dict(
                zip(
                    ("atp_mM", "adp_mM", "pi_mM"),
                    (float(v) for v in amount[:, owner] / c["energy_volumes"][owner]),
                    strict=True,
                )
            )
        )
    current = dict(c["ionic"], raw=stage_raw)
    slope, phi, proof = ionic.evaluate(current, flatten(current, d), time)
    result = unpack(current, slope)
    pool_rate = np.zeros_like(amount)
    for j, patch in enumerate(m["membranes"]):
        if patch["pump"] is not None:
            owner = c["cell_ids"].index(patch["inside"])
            cycles = result["pump_cycles"][j]
            pool_rate[:, owner] += np.array([-cycles, cycles, cycles])
    port_count = c["shapes"]["regeneration_cycles_fmol"][0]
    cycles, heat, supply = (np.zeros(port_count) for _ in range(3))
    for j, port in enumerate(c["raw"]["model"]["regeneration_ports"]):
        pool = c["pools"][port["pool_id"]]
        owner = c["cell_ids"].index(pool["cell_id"])
        level = ionic.availability(c, "regeneration", port["id"], time)
        value = chemistry.regeneration(
            amount[:, owner],
            c["energy_volumes"][owner],
            temperature,
            c["energy_delta_g0"][owner],
            port["capacity_fmol_per_s"],
            port["supplied_energy_J_per_mol"],
            level,
        )
        cycles[j] = value["synthesis_fmol_s"]
        heat[j], supply[j] = value["dissipated_power_pJ_s"], value["supplied_power_pJ_s"]
        pool_rate[:, owner] += np.array([cycles[j], -cycles[j], -cycles[j]])
    result.update(
        energy_amount_increment_fmol=pool_rate,
        regeneration_cycles_fmol=cycles,
        regeneration_dissipated_energy_pJ=heat,
        regeneration_supplied_work_pJ=supply,
    )
    pool_power = 0.0
    for i in range(amount.shape[-1]):
        values = chemistry.thermodynamics(
            amount[:, i], c["energy_volumes"][i], temperature, c["energy_delta_g0"][i]
        )
        pool_power += 1e-3 * np.dot(values["chemical_potential_J_mol"], pool_rate[:, i])
    material_rate = np.c_[result["amount_increment"], result["extracellular_amount_increment"]]
    ionic_amount = np.c_[
        c["ai"] + d["amount_increment"], c["ao"] + d["extracellular_amount_increment"]
    ]
    volumes = np.r_[c["vi"], c["vo"]]
    chemical = 1e-3 * R * temperature * np.sum(np.log(ionic_amount / volumes) * material_rate)
    charge_rate = 1e-15 * F * np.sum(np.asarray(c["layout"]["valence"]) * material_rate, axis=0)
    capacitor = 1e12 * np.dot(phi, charge_rate)
    ionic_heat = sum(
        np.sum(result[key + "_dissipated_energy_pJ"])
        for key in ("membrane", "junction", "face", "channel", "pump")
    )
    total = chemical + capacitor + pool_power + ionic_heat + np.sum(heat) - np.sum(supply)
    return (
        flatten(c, result),
        phi,
        proof
        | dict(
            physical_energy_balance_pJ_s=float(total),
            ionic_chemical_power_pJ_s=float(chemical),
            capacitor_power_pJ_s=float(capacitor),
            pool_chemical_power_pJ_s=float(pool_power),
            ionic_dissipation_pJ_s=float(ionic_heat),
            regeneration_dissipation_pJ_s=float(np.sum(heat)),
            regeneration_supply_pJ_s=float(np.sum(supply)),
            internal_pump_transfer_power_pJ_s=float(np.sum(result["metabolic_work_pJ"])),
            adenylate_rate_fmol_s=(pool_rate[0] + pool_rate[1]).tolist(),
            phosphorus_rate_fmol_s=(3 * pool_rate[0] + 2 * pool_rate[1] + pool_rate[2]).tolist(),
        ),
    )


def integrate(raw, *, refinement=1):
    """Independent segmented adaptive reference for coordinated trajectory checks."""
    if type(refinement) is not int or refinement < 1:
        raise ValueError("Reference refinement must be a positive integer")
    c, e = bind(raw), raw["experiment"]
    events = sorted(
        {
            0.0,
            e["end_time"],
            *(
                change["time"]
                for kind in CONTROL_KINDS
                for group in e[kind + "_controls"]
                for change in group["schedule"]
            ),
        }
    )
    state = initial(c)
    saved, evaluations = {0.0: state.copy()}, 0
    tolerance = flatten(
        c,
        {
            name: np.full(shape, (1e-29 if name.endswith("_C") else 2e-14) / refinement)
            for name, shape in c["shapes"].items()
        },
    )
    for left, right in zip(events, events[1:], strict=False):
        solution = solve_ivp(
            lambda t, y, held=left: evaluate(c, y, held)[0],
            (left, right),
            state,
            method="DOP853",
            rtol=2e-11 / refinement,
            atol=tolerance,
            max_step=1.25e-6 / refinement,
            dense_output=True,
        )
        if not solution.success:
            raise RuntimeError(solution.message)
        evaluations += solution.nfev
        for time in e["observation_times"]:
            if left < time <= right:
                saved[time] = solution.sol(time)
        state = solution.y[:, -1]
    return dict(
        times=e["observation_times"],
        state=np.stack([saved[t] for t in e["observation_times"]]),
        potential_V=np.stack([evaluate(c, saved[t], t)[1] for t in e["observation_times"]]),
        evaluations=evaluations,
        refinement=refinement,
        rtol=2e-11 / refinement,
        amount_energy_gate_atol=2e-14 / refinement,
        electrode_charge_atol_C=1e-29 / refinement,
        max_step_s=1.25e-6 / refinement,
        event_times=events,
        method="DOP853; full-node roots, Decimal gates/pumps and 80-digit finite-energy port",
    )
