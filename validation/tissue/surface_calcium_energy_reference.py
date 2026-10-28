"""Independent owned calcium/ER with finite shared transformed ATP/ADP/Pi.

No Cells/JAX imports or production projections. Neutral pools have a canonical
1-M standard state and fixed cytosolic volume. Na/K uses that standard directly;
the separately reconstructed PMCA/one-Ca ER laws use the 1-mM quotient bridge.
The three retained pump work ledgers are internal transfers, not external fuel.
"""

import math
from copy import deepcopy
from numbers import Real

import numpy as np
from scipy.integrate import solve_ivp

from validation.chemistry import finite_energy_reference as chemistry
from validation.tissue import surface_calcium_reference as calcium

F, R = calcium.F, calcium.R
flatten, unpack = calcium.flatten, calcium.unpack
MODEL_ID = "resolved_calcium_energy@1"
MODEL_PROJECTIONS = {
    MODEL_ID: ("resolved_calcium@7", "resolved_tissue@8"),
    "resolved_calcium_energy@2": ("resolved_calcium@8", "resolved_tissue@9"),
    "resolved_calcium_energy@3": ("resolved_calcium@9", "resolved_tissue@10"),
    "resolved_calcium_energy@4": ("resolved_calcium@10", "resolved_tissue@11"),
    "resolved_calcium_energy@5": ("resolved_calcium@11", "resolved_tissue@12"),
}
ENERGY_FIELDS = (
    "energy_amount_increment_fmol",
    "regeneration_cycles_fmol",
    "regeneration_dissipated_energy_pJ",
    "regeneration_supplied_work_pJ",
)
PMCA_LAW = "finite_atp_pmca_betse_positive@1"
ER_LAW = "finite_atp_er_1ca_betse_positive@1"


def _number(value, *, positive=False):
    return (
        isinstance(value, Real)
        and not isinstance(value, bool)
        and np.isfinite(value)
        and (value > 0 if positive else value >= 0)
    )


def _owner(c, metabolism, cell):
    if (
        set(metabolism) != {"kind", "pool_id"}
        or metabolism["kind"] != "finite_energy_pool@1"
        or metabolism["pool_id"] not in c["pools"]
        or c["pools"][metabolism["pool_id"]]["cell_id"] != cell
    ):
        raise ValueError("Every finite pump must refer to its own cell's pool")
    return c["cell_ids"].index(cell)


def _legacy_calcium_pump(pump, concentrations, delta_g0, temperature, er):
    """Explicit standard-state conversion, independently of production adapters."""
    return dict(
        law="betse_1_5_er_calcium_pump_positive@1"
        if er
        else "betse_1_5_plasma_calcium_pump_positive@1",
        **{key: pump[key] for key in ("capacity_fmol_per_s", "km_ca_mM", "km_atp_mM")},
        metabolism="betse_1_5_maintained_mM_quotient@1",
        **dict(zip(("atp_mM", "adp_mM", "pi_mM"), map(float, concentrations), strict=True)),
        delta_g0_J_per_mol=float(delta_g0 - R * temperature * np.log(1000.0)),
    )


def _project(c, amount):
    projected = deepcopy(c["raw"])
    m, e = projected["model"], projected["experiment"]
    m["id"] = MODEL_PROJECTIONS[m["id"]][0]
    m.pop("energy_pools")
    m.pop("regeneration_ports")
    e.pop("regeneration_controls")
    projected["execution"].pop("regeneration_capacity")
    concentrations = amount / c["energy_volumes"]
    for j, patch in enumerate(m["ionic"]["membranes"]):
        pump = patch["pump"]
        if pump is not None:
            i = c["patch_owners"][j]
            pump["metabolism"] = dict(
                kind="maintained_chemical_reservoirs@1",
                **dict(
                    zip(
                        ("atp_mM", "adp_mM", "pi_mM"), map(float, concentrations[:, i]), strict=True
                    )
                ),
                delta_g0_J_per_mol=float(c["energy_delta_g0"][i]),
            )
    for j, route in enumerate(m["plasma_transport"]["membranes"]):
        if route["pump"] is not None:
            i = c["plasma_owners"][j]
            route["pump"] = _legacy_calcium_pump(
                route["pump"],
                concentrations[:, i],
                c["energy_delta_g0"][i],
                c["temperature"],
                False,
            )
    for store in m["stores"]:
        if store["model"]["membrane"]["pump"] is not None:
            i = c["cell_ids"].index(store["cell_id"])
            store["model"]["membrane"]["pump"] = _legacy_calcium_pump(
                store["model"]["membrane"]["pump"],
                concentrations[:, i],
                c["energy_delta_g0"][i],
                c["temperature"],
                True,
            )
    return projected


def bind(raw):
    m = raw["model"]
    if m["id"] not in MODEL_PROJECTIONS or m["ionic"]["id"] != MODEL_PROJECTIONS[m["id"]][1]:
        raise ValueError("Require the finite-energy calcium identity's versioned shared catalog")
    ion = m["ionic"]
    if ion["temperature_K"] != 298.15 or any(v["reservoir"] for v in ion["extracellular"]):
        raise ValueError("Require finite closed owners and unscaled 298.15-K channels")
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


def initial(c):
    d = unpack(c["calcium"], calcium.initial(c["calcium"]))
    d.update({name: np.zeros(c["shapes"][name]) for name in ENERGY_FIELDS})
    return flatten(c, d)


def evaluate(c, state, time, *, channel_levels=None):
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
    slope, phi, prior = calcium.evaluate(
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


class ReferenceIntegrationError(RuntimeError):
    def __init__(self, message, diagnostics):
        super().__init__(message)
        self.diagnostics = diagnostics


def integrate(raw, *, refinement=1, max_step_s=1.25e-6, channel_segments=None):
    """Short-window adaptive reference, holding all input families per interval."""
    if type(refinement) is not int or refinement < 1 or not _number(max_step_s, positive=True):
        raise ValueError("Require positive integer refinement and finite positive step cap")
    c, e = bind(raw), raw["experiment"]
    segments = channel_segments or [(0.0, None)]
    if (
        segments[0][0] != 0
        or any(not _number(t) or t > e["end_time"] for t, _ in segments)
        or any(b[0] <= a[0] for a, b in zip(segments, segments[1:], strict=False))
    ):
        raise ValueError("Require ordered assembly-owner levels from time zero")
    events = {0.0, e["end_time"], *(t for t, _ in segments)}
    for name, groups in e.items():
        if name.endswith("_controls"):
            events.update(
                row["time"]
                for group in groups
                for row in group.get("schedule", group.get("controls", []))
            )
    events = sorted(events)
    times, y, evaluations = e["observation_times"], initial(c), 0
    saved = {0.0: y.copy()}
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

    for left, right in zip(events, events[1:], strict=False):
        levels = next(v for t, v in reversed(segments) if t <= left)
        answer = solve_ivp(
            lambda t, state, held=left, opened=levels: rhs(t, state, held, opened),
            (left, right),
            y,
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
        for time in times:
            if left < time <= right:
                saved[time] = answer.y[:, -1].copy() if time == right else answer.sol(time)
        y = answer.y[:, -1].copy()
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
        rtol=2e-11 / refinement,
        amount_energy_gate_atol=2e-14 / refinement,
        electrode_charge_atol_C=1e-29 / refinement,
        max_step_s=max_step_s / refinement,
        event_times=events,
        method="DOP853; owned calcium, three-family finite ATP demand, Decimal supply",
    )
