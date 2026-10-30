"""Independent explicit held active-temperature policy and full owner rate laws.

Original binders validate only original 298.15-K definitions. New contexts are
projected explicitly from original geometry/amounts/anchors and the named policy;
ordinary binder guards and module globals are never patched or bypassed.
"""

import math
from copy import deepcopy
from decimal import Decimal, localcontext

import numpy as np

from validation.chemistry import finite_energy_reference as chemistry
from validation.perturbations import global_controls_reference as setters
from validation.tissue import open_calcium_reference as opened
from validation.tissue import physiology_temperature_reference as original
from validation.tissue import surface_calcium_energy_reference as finite
from validation.tissue import surface_calcium_reference as calcium
from validation.tissue import surface_kinetic_reference as kinetic

POLICY = "active_uniform_isothermal_fixed_empirical_kinetics@1"
KIND = "cells.physiology_active_temperature_binding@1"
ORACLES = {key: value for key, value in original.ORACLES.items() if key != "resolved_tissue@1"}
F, R = calcium.F, calcium.R
flatten, unpack = calcium.flatten, calcium.unpack


def reconstruct(raw, binding_record, current_temperature_K, held_control, time_s, events_enabled):
    if raw["model"]["id"] not in ORACLES:
        raise ValueError(
            "Independent held policy requires one of the five active source identities"
        )
    expected = dict(
        kind=KIND,
        policy=POLICY,
        original_binding=binding_record.get("original_binding"),
        reference_temperature_K=298.15,
        temperature_domain_K=[200.0, 400.0],
        semantics="held_complete_active_rates_no_accepted_thermal_transition@1",
        standard_energy_policy="fixed_J_mol_ER_and_fuel_standard_coefficients@1",
        maintained_calcium_standard="declared_numeric_mM_standard_energy_J_mol_fixed@1",
        finite_calcium_standard="shared_1M_to_numeric_mM_deltaG0_minus_RT_ln1000@1",
        kinetics="fixed_empirical_curves_no_Q10_or_Arrhenius@1",
        native_compatibility="native_configured_runtime_split_is_separate_evidence@1",
    )
    expected["identity"] = original._digest(expected)
    if expected != binding_record:
        raise ValueError("Independent active-temperature policy/source/units mismatch")
    if type(events_enabled) is not bool or isinstance(time_s, bool) or not math.isfinite(time_s):
        raise ValueError("Independent setter requires explicit enable flag and finite label")
    if isinstance(current_temperature_K, bool) or not 200 <= current_temperature_K <= 400:
        raise ValueError("Independent active-temperature memory leaves 200-400 K")
    # The established reconstruction validates every original owner and source
    # hash; events are disabled here solely for original 298.15-K binding.
    source, _ = original.reconstruct(
        raw, binding_record["original_binding"], 298.15, held_control, time_s, False
    )
    base = ORACLES[raw["model"]["id"]].bind(source)
    program = binding_record["original_binding"]["program"]
    current = dict(
        temperature_K=current_temperature_K,
        junction_available=[1.0] * len(program["membrane_ids"]),
        pump_available=1.0,
        boundary_voltage_V=[0.0] * 4,
    )
    result = setters.evaluate(program, current, time_s, 298.15, events_enabled=events_enabled)
    target = result["temperature_K"]
    if not math.isfinite(target) or not 200 <= target <= 400:
        raise ValueError("Independent setter leaves the named held policy's process domain")
    effective = deepcopy(source)
    effective["model"].get("ionic", effective["model"])["temperature_K"] = target
    with localcontext() as precision:
        precision.prec = 100
        for row in effective["model"].get("stores", []):
            store = row["model"]
            store["temperature_K"] = target
            for species in store["species"]:
                species["standard_mu_RT"] = float(
                    Decimal.from_float(float(species["standard_mu_RT"]))
                    * Decimal.from_float(298.15)
                    / Decimal.from_float(float(target))
                )
    return source, effective, base, result


def _ionic_context(template, definition):
    result = deepcopy(template)
    result["raw"] = deepcopy(definition)
    result["layout"]["temperature"] = definition["model"]["temperature_K"]
    return result


def _calcium_context(template, definition):
    """New-policy context, never an ordinary bind of a changed-T declaration."""
    ion = dict(
        model=definition["model"]["ionic"],
        experiment=definition["experiment"],
        execution=definition["execution"],
    )
    result = _ionic_context(template, ion)
    result["full"] = deepcopy(definition)
    stores = {row["cell_id"]: row["model"] for row in definition["model"]["stores"]}
    release = {row["cell_id"]: row for row in definition["model"]["ip3_release"]}
    result["stores"] = [
        calcium.IP3Store(dict(model=stores[row["id"]]), release[row["id"]])
        for row in definition["model"]["ionic"]["cells"]
    ]
    return result


def bind(raw, binding_record, current_temperature_K, held_control, time_s, events_enabled):
    source, effective, base, setter = reconstruct(
        raw, binding_record, current_temperature_K, held_control, time_s, events_enabled
    )
    model_id = raw["model"]["id"]
    is_open, is_fuel = model_id.startswith("resolved_open"), "energy" in model_id
    equation = opened.equation_definition(effective) if is_open else effective
    if model_id == "resolved_tissue@12":
        context = _ionic_context(base, effective)
    elif not is_fuel:
        context = _calcium_context(base, equation)
    else:
        context = deepcopy(base)
        context["raw"] = deepcopy(equation)
        context["temperature"] = setter["temperature_K"]
        context["calcium_template"] = deepcopy(base["calcium"])
        context["calcium"] = _calcium_context(
            context["calcium_template"], finite._project(context, context["energy_initial"])
        )
    if is_open:
        context.update(open_definition=deepcopy(effective), equation_definition=deepcopy(equation))
    context["active_temperature"] = dict(
        source=source,
        effective=effective,
        setter=setter,
        finite_fuel=is_fuel,
        open_world=is_open,
        source_model_id=model_id,
    )
    return context


def _calcium_rates(context, state, time, *, channel_levels=None):
    return opened._calcium_rates(context, state, time, channel_levels=channel_levels)


def _cached_drives(context, fields):
    policy = context["active_temperature"]
    if policy["source_model_id"] == "resolved_tissue@12":
        definition = context["raw"]
    elif policy["finite_fuel"]:
        amount = (
            context["energy_initial"]
            + np.asarray(fields["energy_amount_increment_fmol"])[..., : len(context["cell_ids"])]
        )
        definition = finite._project(context, amount)
    else:
        definition = context["full"]
    ion = definition["model"].get("ionic", definition["model"])
    result = []
    for patch in ion["membranes"]:
        pump = patch["pump"]
        if pump is None:
            result.append(0.0)
            continue
        m = pump["metabolism"]
        with localcontext() as precision:
            precision.prec = 100
            result.append(
                float(
                    Decimal.from_float(float(m["delta_g0_J_per_mol"]))
                    + Decimal.from_float(R)
                    * Decimal.from_float(float(ion["temperature_K"]))
                    * (
                        Decimal(str(m["adp_mM"]))
                        * Decimal(str(m["pi_mM"]))
                        / (Decimal(1000) * Decimal(str(m["atp_mM"])))
                    ).ln()
                )
            )
    return result


def evaluate(
    raw, fields, binding_record, current_temperature_K, held_control, time_s, events_enabled
):
    context = bind(raw, binding_record, current_temperature_K, held_control, time_s, events_enabled)
    if set(fields) != set(context["shapes"]):
        raise ValueError("Independent held active policy requires every state field")
    policy = context["active_temperature"]
    if policy["open_world"]:
        opened.validate_padded_state(context, fields)
    packed = flatten(context, fields)
    if policy["source_model_id"] == "resolved_tissue@12":
        rate, phi, proof = kinetic.evaluate(context, packed, 0.0)
    else:
        if policy["open_world"]:
            total = opened.ionic_moieties(context, packed)
            limit = context["ionic_moiety_ceiling_fmol"]
            if limit is not None and np.any(total > limit):
                raise ValueError("Held active oracle leaves actual open ionic-moiety ceilings")
        evaluator = _fuel_rates if policy["finite_fuel"] else _calcium_rates
        rate, phi, proof = evaluator(context, packed, 0.0)
    proof = dict(
        proof,
        policy=POLICY,
        held_temperature_K=policy["setter"]["temperature_K"],
        source_definition_sha256=original._digest(raw),
        effective_coefficients_sha256=original._digest(policy["effective"]),
        stage_pump_drive_J_mol=_cached_drives(context, fields),
        full_physical_owner_reconstruction=True,
        accepted_thermal_transition=False,
        accepted_heat_pJ=None,
    )
    proof["physical_field_columns"] = field_columns(context, fields, rate, phi, proof)
    return context, rate, phi, proof


def field_columns(context, fields, rate, phi, proof):
    """Independent complete physical field outputs; solver counters are not physics."""
    policy = context["active_temperature"]
    physical = context["calcium"] if policy["finite_fuel"] else context
    state, slope = unpack(physical, flatten(physical, fields)), unpack(context, rate)
    raw = kinetic.base.stage(physical, flatten(physical, fields), 0.0)
    ion, p = physical["raw"]["model"], physical["layout"]
    n, o, nm = len(ion["cells"]), len(ion["extracellular"]), len(ion["membranes"])
    if policy["source_model_id"] != "resolved_tissue@12":
        raw["ci"] = np.stack(
            [
                (store.n0 + state["chemical_amount_increment"][i])[
                    [store.ids.index(row["id"]) for row in ion["species"]], store.cy
                ]
                / physical["vi"][i]
                for i, store in enumerate(physical["stores"])
            ],
            axis=1,
        )
    ci, co, z = np.asarray(raw["ci"]), np.asarray(raw["co"]), np.asarray(p["valence"])
    membrane = np.asarray(slope["membrane_transferred"]).copy()
    membrane_d = (
        np.asarray(slope["membrane_dissipated_energy_pJ"]).copy()
        + slope["pump_dissipated_energy_pJ"]
    )
    ids = [row["id"] for row in ion["species"]]
    patches = [row["id"] for row in ion["membranes"]]
    for j, population in enumerate(ion["channels"]):
        k = patches.index(population["membrane_id"])
        membrane[:, k] += slope["channel_transferred"][:, j]
        membrane_d[k] += np.sum(slope["channel_dissipated_energy_pJ"][:, j])
    for j, patch in enumerate(ion["membranes"]):
        pump = patch["pump"]
        if pump is not None:
            for name, coefficient in pump["stoichiometry"].items():
                membrane[ids.index(name), j] -= coefficient * slope["pump_cycles"][j]
    if "plasma_pump_cycles" in slope:
        model = policy["effective"]["model"]
        plasma = model["plasma_transport"]
        membrane[ids.index(plasma["calcium_species"])] += (
            slope["plasma_pump_cycles"]
            + slope["plasma_exchange_cycles"]
            + slope["calcium_channel_transferred"]
        )
        membrane[ids.index(plasma["sodium_species"])] -= 3 * slope["plasma_exchange_cycles"]
        membrane_d += (
            np.sum(slope["plasma_dissipated_energy_pJ"], axis=0)
            + slope["calcium_channel_dissipated_energy_pJ"]
        )
    targets = {}

    def add(name, value, atol=3e-12, rtol=3e-10):
        targets[name] = dict(value=np.asarray(value).tolist(), atol=atol, rtol=rtol)

    for name, value in (
        ("cell_rate_fmol_s", slope["amount_increment"]),
        ("outside_rate_fmol_s", slope["extracellular_amount_increment"]),
        ("reservoir_supply_fmol_s", slope["reservoir_supplied"]),
    ):
        add("rates." + name, value)
    for kind, left, right, dv, flux, diss in (
        (
            "membrane",
            ci[:, p["membrane_cell"]],
            co[:, p["membrane_outside"]],
            phi[np.asarray(p["membrane_cell"], dtype=int)]
            - phi[n + np.asarray(p["membrane_outside"], dtype=int)],
            membrane,
            membrane_d,
        ),
        (
            "junction",
            ci[:, p["junction_sender"]],
            ci[:, p["junction_receiver"]],
            phi[np.asarray(p["junction_sender"], dtype=int)]
            - phi[np.asarray(p["junction_receiver"], dtype=int)],
            slope["junction_transferred"],
            slope["junction_dissipated_energy_pJ"],
        ),
        (
            "face",
            co[:, p["face_sender"]],
            co[:, p["face_receiver"]],
            phi[n + np.asarray(p["face_sender"], dtype=int)]
            - phi[n + np.asarray(p["face_receiver"], dtype=int)],
            slope["face_transferred"],
            slope["face_dissipated_energy_pJ"],
        ),
    ):
        add("rates." + kind + "_voltage_V", dv, 3e-13)
        add("rates." + kind + "_flux_fmol_s", flux)
        add(
            "rates." + kind + "_delta_mu_J_mol",
            R * p["temperature"] * (np.log(left) - np.log(right)) + z * F * dv,
            3e-10,
        )
        add("rates." + kind + "_current_A", 1e-15 * F * np.sum(z * flux, axis=0), 3e-23)
        add("rates." + kind + "_dissipation_pJ_s", diss)
    matrix, active, reservoir, _, floating, _ = opened.electrical.topology(raw)
    capacitor_charge = matrix @ phi
    add("capacitor_node_charge_C", capacitor_charge, 3e-25, 2e-12)
    add(
        "membrane_charge_C",
        np.asarray(p["membrane_capacitance"]) * targets["rates.membrane_voltage_V"]["value"],
        3e-25,
        2e-12,
    )
    required = active & ~reservoir
    charge = np.r_[raw["cell_charge_C"], raw["outside_charge_C"]]
    add("charge_residual_C", np.where(required, capacitor_charge - charge, 0.0), 3e-25, 2e-12)
    add(
        "electrode_charge_C",
        np.where(p["reservoir"], (capacitor_charge - charge)[n:], 0.0),
        3e-25,
        2e-12,
    )
    current = (
        1e-15
        * F
        * np.sum(
            z * np.c_[slope["amount_increment"], slope["extracellular_amount_increment"]], axis=0
        )
    )
    pins = ~active | reservoir
    for members in floating:
        pins[members[0]] = True
    free = np.flatnonzero(~pins)
    dphi = np.zeros(n + o)
    dphi[free] = np.linalg.solve(matrix[np.ix_(free, free)], current[free])
    add(
        "membrane_voltage_rate_V_s",
        dphi[np.asarray(p["membrane_cell"], dtype=int)]
        - dphi[n + np.asarray(p["membrane_outside"], dtype=int)],
    )
    add("electrode_current_A", slope["electrode_charge_transferred_C"], 3e-23)
    add(
        "reservoir_supply_charge_A",
        1e-15 * F * np.sum(z * slope["reservoir_supplied"], axis=0),
        3e-23,
    )
    cap_energy, cap_power = 0.0, 0.0
    for j in range(nm):
        v = targets["rates.membrane_voltage_V"]["value"][j]
        dv = targets["membrane_voltage_rate_V_s"]["value"][j]
        cap_energy += 0.5e12 * p["membrane_capacitance"][j] * v**2
        cap_power += 1e12 * p["membrane_capacitance"][j] * v * dv
    add("capacitor_energy_pJ", cap_energy, 3e-14)
    add("capacitor_energy_rate_pJ_s", proof.get("capacitor_power_pJ_s", cap_power))
    chemical = (
        1e-3
        * R
        * p["temperature"]
        * (
            np.sum(np.log(ci) * slope["amount_increment"])
            + np.sum(np.log(co) * slope["extracellular_amount_increment"])
        )
    )
    add("chemical_energy_rate_pJ_s", proof.get("chemical_power_pJ_s", chemical))
    add("reservoir_power_pJ_s", np.sum(slope["reservoir_work_pJ"]))
    add("electrode_power_pJ_s", np.sum(slope["electrode_work_pJ"]))
    add(
        "dissipation_pJ_s",
        sum(
            float(np.sum(value))
            for name, value in slope.items()
            if name.endswith("_dissipated_energy_pJ")
        ),
    )
    add("energy_balance_pJ_s", proof.get("physical_energy_balance_pJ_s", 0.0))
    return targets


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
    current = _calcium_context(c["calcium_template"], finite._project(c, amount))
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
