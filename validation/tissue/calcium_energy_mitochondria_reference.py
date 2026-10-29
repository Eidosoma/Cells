"""Independent continuous mitochondrial transport, actual owners and energy.

The pinned native Euler/cache/nonce component is deliberately separate. This
80-digit SI law uses a fresh charge-consistent voltage and exact zero/neutral
limits. No Cells/JAX imports, production projections, or automatic ATP demand.
"""

import math
from copy import deepcopy
from decimal import Decimal, localcontext
from numbers import Real

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import calcium_energy_network_transport_reference as parent

F, R = parent.F, parent.R
MODEL_ID = "resolved_calcium_energy_mitochondria@1"
flatten, unpack = parent.flatten, parent.unpack
EXTRA_FIELDS = (
    "mitochondrial_amount_increment_fmol",
    "mitochondrial_transferred_fmol",
    "mitochondrial_dissipated_energy_pJ",
)


def _number(value, *, positive=False, nonnegative=False):
    if not isinstance(value, (Real, Decimal)) or isinstance(value, bool):
        raise ValueError("Require real mitochondrial quantities")
    value = Decimal(str(value))
    if not value.is_finite() or (positive and value <= 0) or (nonnegative and value < 0):
        raise ValueError("Invalid mitochondrial numerical domain")
    return value


def passive_exchange(
    cytosol_mM,
    mitochondria_mM,
    valence,
    voltage_V,
    diffusivity_m2_per_s,
    area_m2,
    thickness_m,
    temperature_K,
    availability=1.0,
):
    """One physical route: positive fmol/s means cytosol -> mitochondrion."""
    with localcontext() as context:
        context.prec = 80
        cy, mi = (_number(v, positive=True) for v in (cytosol_mM, mitochondria_mM))
        z, voltage = _number(valence), _number(voltage_V)
        diffusion, level = (
            _number(v, nonnegative=True) for v in (diffusivity_m2_per_s, availability)
        )
        area, thickness, temperature = (
            _number(v, positive=True) for v in (area_m2, thickness_m, temperature_K)
        )
        if abs(voltage) > Decimal(".2") or level > 1 or z != z.to_integral_value() or abs(z) > 8:
            raise ValueError(
                "Mitochondrial voltage, valence or availability outside declared domain"
            )
        rt, f = Decimal(str(R)) * temperature, Decimal(str(F))
        x = z * f * voltage / rt
        if x == 0:
            flux = (cy - mi) * diffusion * area * level / (thickness * Decimal("1e-15"))
        elif abs(x) < Decimal("1e-20"):
            # The Decimal exponential would round to one for subnormal float
            # voltages. The analytic expansion error here is below 1e-160.
            b = 1 - x / 2 + x * x / 12 - x**4 / 720 + x**6 / 30240
            flux = (
                diffusion * area * level * ((cy - mi) * b - mi * x) / (thickness * Decimal("1e-15"))
            )
        else:
            # High precision evaluates the original constant-field quotient
            # directly, independently of production's Bernoulli implementation.
            ex = x.exp()
            flux = (
                diffusion
                * area
                * level
                * x
                * (cy - mi * ex)
                / ((ex - 1) * thickness * Decimal("1e-15"))
            )
        mu = rt * (mi / cy).ln() + z * f * voltage
        return dict(
            flux_fmol_s=float(flux),
            transfer_energy_J_mol=float(mu),
            dissipated_power_pJ_s=float(-flux * mu / 1000),
        )


def bind(raw):
    if raw["model"]["id"] != MODEL_ID:
        raise ValueError("Require explicit calcium/fuel/network/mitochondria identity")
    projected = deepcopy(raw)
    projected["model"]["id"] = parent.MODEL_ID
    group = projected["model"].pop("mitochondria")
    schedules = projected["experiment"].pop("mitochondria_controls")
    required = dict(
        law="betse_mitochondrial_passive_continuous_si@1",
        source_law="betse_mitochondrial_ion_voltage_source_v1_5_0@1",
        initialization="explicit_disjoint_inventory@1",
        voltage="charge_consistent_mito_minus_cytosol@1",
        cytosol_volume_role="solvent_volume_excludes_er_and_mitochondria@1",
        constants=dict(faraday_C_mol=F, gas_constant_J_mol_K=R),
    )
    if set(group) != {*required, "compartments"} or any(group[k] != v for k, v in required.items()):
        raise ValueError(
            "Require explicit disjoint inventory, solvent volume and continuous SI law"
        )
    base = parent.bind(projected)
    ids, cells = base["network_species"], base["cell_ids"]
    rows = group["compartments"]
    if len(rows) != len(cells) or {v["cell_id"] for v in rows} != set(cells):
        raise ValueError("Exactly one mitochondrial owner is required per actual cell")
    by_owner, names = {}, set()
    for row in rows:
        if (
            set(row)
            != {
                "id",
                "cell_id",
                "volume_pL",
                "area_m2",
                "specific_capacitance_F_per_m2",
                "membrane_thickness_m",
                "initial_voltage_V",
                "initial_amount_fmol",
                "diffusivity_m2_per_s",
            }
            or not isinstance(row["id"], str)
            or not row["id"]
            or row["id"] in names
        ):
            raise ValueError("Require distinct organelle IDs and explicit physical geometry")
        for key in (
            "volume_pL",
            "area_m2",
            "specific_capacitance_F_per_m2",
            "membrane_thickness_m",
        ):
            _number(row[key], positive=True)
        if abs(_number(row["initial_voltage_V"])) > Decimal(".2"):
            raise ValueError("Initial mitochondrial voltage outside [-.2,.2] V")
        if set(row["initial_amount_fmol"]) != set(ids) or set(row["diffusivity_m2_per_s"]) != set(
            ids
        ):
            raise ValueError(
                "Every ionic species needs explicit organelle inventory and diffusivity"
            )
        for s in ids:
            _number(row["initial_amount_fmol"][s], positive=True)
            _number(row["diffusivity_m2_per_s"][s], nonnegative=True)
        by_owner[row["cell_id"]] = deepcopy(row)
        names.add(row["id"])
    controls = {}
    for row in schedules:
        name, schedule = row["mitochondrion_id"], row["schedule"]
        if name in controls or not schedule:
            raise ValueError("Duplicate or empty mitochondrial schedule")
        times = [_number(v["time"], nonnegative=True) for v in schedule]
        levels = [_number(v["availability"], nonnegative=True) for v in schedule]
        if (
            times[0] != 0
            or any(b <= a for a, b in zip(times[:-1], times[1:], strict=True))
            or times[-1] > Decimal(str(raw["experiment"]["end_time"]))
            or any(v > 1 for v in levels)
        ):
            raise ValueError("Invalid right-continuous mitochondrial controls")
        controls[name] = deepcopy(schedule)
    if set(controls) != names:
        raise ValueError("Mitochondrial controls must cover each organelle exactly once")
    ordered = [by_owner[name] for name in cells]
    initial = np.array([[row["initial_amount_fmol"][s] for row in ordered] for s in ids])
    volume = np.array([row["volume_pL"] for row in ordered])
    capacitance = np.array(
        [row["area_m2"] * row["specific_capacitance_F_per_m2"] for row in ordered]
    )
    voltage = np.array([row["initial_voltage_V"] for row in ordered])
    z = np.array([v["valence"] for v in raw["model"]["ionic"]["species"]])
    return dict(
        base,
        raw=deepcopy(raw),
        parent=base,
        mitochondrial_rows=ordered,
        mitochondrial_initial=initial,
        mitochondrial_volume=volume,
        mitochondrial_capacitance=capacitance,
        mitochondrial_initial_voltage=voltage,
        mitochondrial_valence=z,
        mitochondrial_fixed_charge_C=capacitance * voltage
        - F * 1e-15 * np.sum(z[:, None] * initial, axis=0),
        mitochondrial_initial_cytosol_countercharge_C=-capacitance * voltage,
        mitochondria_controls=controls,
        shapes=base["shapes"] | {name: initial.shape for name in EXTRA_FIELDS},
    )


def initial(c):
    d = unpack(c["parent"], parent.initial(c["parent"]))
    d.update({name: np.zeros(c["shapes"][name]) for name in EXTRA_FIELDS})
    return flatten(c, d)


def mitochondrial_voltage(c, d):
    return c["mitochondrial_initial_voltage"] + F * 1e-15 / c["mitochondrial_capacitance"] * np.sum(
        c["mitochondrial_valence"][:, None] * d["mitochondrial_amount_increment_fmol"], axis=0
    )


def evaluate(c, state, time, *, channel_levels=None):
    if not np.isfinite(state).all():
        raise ValueError("Complete mitochondrial state must be finite")
    d = unpack(c, state)
    amount = c["mitochondrial_initial"] + d["mitochondrial_amount_increment_fmol"]
    voltage = mitochondrial_voltage(c, d)
    if (
        np.any(amount <= 0)
        or np.any(np.abs(voltage) > 0.2)
        or np.any(d["mitochondrial_dissipated_energy_pJ"] < -2e-14)
    ):
        raise ValueError("Invalid positive inventory, voltage or accumulated mitochondrial heat")
    slope, phi, proof = parent.evaluate(
        c["parent"], flatten(c["parent"], d), time, channel_levels=channel_levels
    )
    result = unpack(c["parent"], slope)
    ci, _ = parent._concentrations(c["parent"], d)
    cm = amount / c["mitochondrial_volume"]
    flux, heat, mu = (np.zeros_like(amount) for _ in range(3))
    for i, row in enumerate(c["mitochondrial_rows"]):
        level = next(
            v["availability"]
            for v in reversed(c["mitochondria_controls"][row["id"]])
            if v["time"] <= time
        )
        store = c["stores"][i]
        for j, s in enumerate(c["network_species"]):
            values = passive_exchange(
                ci[j, i],
                cm[j, i],
                c["mitochondrial_valence"][j],
                voltage[i],
                row["diffusivity_m2_per_s"][s],
                row["area_m2"],
                row["membrane_thickness_m"],
                c["temperature"],
                level,
            )
            flux[j, i], heat[j, i], mu[j, i] = (
                values["flux_fmol_s"],
                values["dissipated_power_pJ_s"],
                values["transfer_energy_J_mol"],
            )
            result["chemical_amount_increment"][i, store.ids.index(s), store.cy] -= flux[j, i]
    result.update(
        mitochondrial_amount_increment_fmol=flux,
        mitochondrial_transferred_fmol=flux.copy(),
        mitochondrial_dissipated_energy_pJ=heat,
    )
    charge = F * 1e-15 * np.sum(c["mitochondrial_valence"][:, None] * flux, axis=0)
    balance = 1e-3 * mu * flux + heat
    return (
        flatten(c, result),
        phi,
        proof
        | dict(
            physical_energy_balance_pJ_s=proof["physical_energy_balance_pJ_s"]
            + float(balance.sum()),
            mitochondrial_energy_balance_pJ_s=balance.tolist(),
            mitochondrial_voltage_V=voltage.tolist(),
            mitochondrial_charge_rate_C_s=charge.tolist(),
            cytosolic_mitochondrial_countercharge_rate_C_s=(-charge).tolist(),
            mitochondrial_direct_atp_demand_fmol_s=[0.0] * len(c["cell_ids"]),
            mitochondrial_direct_plasma_charge_rate_C_s=[0.0] * len(c["cell_ids"]),
            mitochondrial_transfer_energy_J_mol=mu.tolist(),
        ),
    )


def stored_energy_change(c, state, reference_state=None, *, time=0.0, reference_time=0.0):
    a = unpack(c, initial(c) if reference_state is None else reference_state)
    b = unpack(c, state)
    base = parent.stored_energy_change(
        c["parent"],
        flatten(c["parent"], b),
        flatten(c["parent"], a),
        time=time,
        reference_time=reference_time,
    )
    chemical = (
        1e-3
        * R
        * c["temperature"]
        * parent._mixing_change(
            c["mitochondrial_initial"] + a["mitochondrial_amount_increment_fmol"],
            c["mitochondrial_initial"] + b["mitochondrial_amount_increment_fmol"],
            c["mitochondrial_volume"],
            difference=b["mitochondrial_amount_increment_fmol"]
            - a["mitochondrial_amount_increment_fmol"],
        )
    )
    va, vb = mitochondrial_voltage(c, a), mitochondrial_voltage(c, b)
    electric = float(np.sum(0.5e12 * c["mitochondrial_capacitance"] * (vb - va) * (vb + va)))
    return base | dict(
        mitochondrial_chemical_pJ=float(chemical),
        mitochondrial_capacitor_pJ=electric,
        total_pJ=base["total_pJ"] + float(chemical) + electric,
    )


def endpoint_balance(c, state, *, time=0.0):
    d = unpack(c, state)
    stored = stored_energy_change(c, state, time=time)
    heat = math.fsum(float(np.sum(v)) for k, v in d.items() if k.endswith("_dissipated_energy_pJ"))
    work = float(np.sum(d["regeneration_supplied_work_pJ"]) + np.sum(d["network_supplied_work_pJ"]))
    return stored | dict(
        dissipated_pJ=heat, supplied_pJ=work, balance_pJ=stored["total_pJ"] + heat - work
    )


ReferenceIntegrationError = parent.ReferenceIntegrationError


def integrate(raw, *, refinement=1, max_step_s=1.25e-6, channel_segments=None):
    if type(refinement) is not int or refinement < 1 or _number(max_step_s, positive=True) <= 0:
        raise ValueError("Require positive refinement and step cap")
    c, e = bind(raw), raw["experiment"]
    segments = [(0.0, None)] if channel_segments is None else channel_segments
    if (
        not segments
        or segments[0][0] != 0
        or any(not np.isfinite(t) or t < 0 or t > e["end_time"] for t, _ in segments)
        or any(b[0] <= a[0] for a, b in zip(segments[:-1], segments[1:], strict=True))
    ):
        raise ValueError("Require ordered external channel owner segments from zero")
    events = {0.0, e["end_time"], *(t for t, _ in segments)}
    for key, groups in e.items():
        if key.endswith("_controls"):
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
        levels = next(v for t, v in reversed(segments) if t <= left)
        solved = solve_ivp(
            lambda t, y, held=left, levels=levels: rhs(t, y, held, levels),
            (left, right),
            current,
            method="DOP853",
            rtol=2e-11 / refinement,
            atol=atol,
            max_step=max_step_s / refinement,
            dense_output=True,
        )
        if not solved.success:
            raise ReferenceIntegrationError(
                solved.message,
                dict(
                    time_s=float(solved.t[-1]),
                    state=solved.y[:, -1].tolist(),
                    evaluations=evaluations,
                    automatic_retry=False,
                ),
            )
        for t in times:
            if left < t <= right:
                saved[t] = solved.y[:, -1].copy() if t == right else solved.sol(t)
        current = solved.y[:, -1].copy()
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
        method="DOP853; independent continuous mito + actual cytosolic owners + parent42",
        max_step_s=max_step_s / refinement,
        rtol=2e-11 / refinement,
        amount_energy_gate_atol=2e-14 / refinement,
        electrode_charge_atol_C=1e-29 / refinement,
    )
