"""Independent time-zero reconstruction from full-node equations and scalar laws.

Imported only after the worker gate. No production parser, model or integrator.
"""

import json
import math
from types import SimpleNamespace

import numpy as np

from validation.geometry import stable_seed_explicit_ecm_partition_geometry_reference as quantity
from validation.geometry import stable_seed_partition_physiology_bridge_field_reference as field
from validation.geometry import stable_seed_partition_physiology_bridge_scalar_reference as scalar

STATE_FIELDS = (
    "amount_increment",
    "extracellular_amount_increment",
    "membrane_transferred",
    "junction_transferred",
    "face_transferred",
    "reservoir_supplied",
    "membrane_dissipated_energy_pJ",
    "junction_dissipated_energy_pJ",
    "face_dissipated_energy_pJ",
    "electrode_charge_transferred_C",
    "reservoir_work_pJ",
    "electrode_work_pJ",
)
DIAGNOSTICS = (
    "max_balance_error_fmol",
    "max_extracellular_balance_error_fmol",
    "max_global_balance_error_fmol",
    "max_capacitor_charge_error_C",
    "max_electrode_charge_error_C",
    "max_global_charge_error_C",
    "max_energy_balance_error_pJ",
    "max_reservoir_work_error_pJ",
    "max_electrode_work_error_pJ",
)
RTOL = 3e-10
VOLTAGE_ATOL = 3e-13
FLUX_ATOL = 3e-12
CURRENT_ATOL = 3e-23
POWER_ATOL = 3e-12
CHARGE_ATOL = 3e-25


class SnapshotRejected(ValueError):
    code = "physical_snapshot_contract"
    stage = "independent_complete_verification"


def require(value, label):
    if not value:
        raise SnapshotRejected(label)


def ratio(value):
    return quantity.ratio(value)


def materialize(request, geometry, truth, partial):
    """Independent caller values and exact targets; every projection retained."""
    d = request["declaration"]
    ions = [r["id"] for r in d["species"]]
    electrical = d["electrical_policy"]
    rows = {k: {r["id"]: r for r in d[k]} for k in ("cells", "baths", "membranes", "faces")}
    anchors = {k: {r["id"]: r for r in electrical[k]} for k in ("cells", "baths")}
    ledger = dict(events=[], concentrations=[], constitutive=[])
    partial["independent_conversions"] = ledger

    def project(target, label, context):
        event = dict(
            sequence=len(ledger["events"]),
            stage=label,
            input_exact=target,
            context=context,
            returned=None,
        )
        ledger["events"].append(event)
        value = quantity.number(target)
        certificate = dict(kind="correctly_rounded_binary_rational", exact=target)
        event["returned"] = dict(value=value, binary64_hex=value.hex(), certificate=certificate)
        return value, certificate

    model = dict(
        id="resolved_tissue@1",
        species=d["species"],
        temperature_K=d["temperature_K"],
        cells=[],
        extracellular=[],
        membranes=[],
        junctions=[],
        faces=[],
        closure=dict(law=electrical["closure_law"], gauge_reference=electrical["gauge_reference"]),
    )
    partial["independent_physical_model"] = model
    for family, axis, output in (
        ("cells", truth["cell_ids"], "cells"),
        ("baths", truth["bath_ids"], "extracellular"),
    ):
        for owner in axis:
            volume, volume_proof = project(
                quantity.multiply(truth["regions"][owner]["volume"], ratio(1e15)),
                "initial_inventory_volume_pL",
                dict(owner_id=owner),
            )
            amounts = {}
            for ion in ions:
                concentration = rows[family][owner]["concentration_mM"][ion]
                target = quantity.multiply(ratio(concentration), ratio(volume))
                amount, proof = project(
                    target,
                    "caller_concentration_to_initial_fmol",
                    dict(
                        owner_id=owner,
                        species=ion,
                        requested_concentration_mM=concentration,
                        admitted_volume_pL=volume,
                    ),
                )
                represented = quantity.divide(ratio(amount), ratio(volume))
                amounts[ion] = amount
                ledger["concentrations"].append(
                    dict(
                        owner_id=owner,
                        species=ion,
                        requested_concentration_mM=concentration,
                        admitted_volume_pL=volume,
                        volume_certificate=volume_proof,
                        amount_fmol=amount,
                        amount_certificate=proof,
                        represented_concentration_mM_exact=represented,
                        concentration_defect_mM_exact=quantity.subtract(
                            represented, ratio(concentration)
                        ),
                        concentration_readback_exactly_claimed=False,
                    )
                )
            row = dict(anchors[family][owner], volume_pL=volume, initial_amount_fmol=amounts)
            if family == "baths":
                row["reservoir"] = False
            model[output].append(row)
    edges = {r["id"]: r for r in truth["edges"]}
    path = geometry["membrane_thickness_m"]
    for patch in truth["membranes"]:
        row = rows["membranes"][patch["id"]]
        specific = row["specific_capacitance_F_per_m2"]
        squared_area = edges[patch["edge_id"]]["area_squared"]
        permeability = {}
        for ion in ions:
            diffusion = row["diffusivity_m2_per_s"][ion]
            projected, certificate = project(
                quantity.divide(ratio(diffusion), ratio(path)),
                "explicit_membrane_D_over_path",
                dict(
                    membrane_id=patch["id"],
                    species=ion,
                    caller_permeability_m_per_s=row["permeability_m_per_s"][ion],
                    diffusivity_m2_per_s=diffusion,
                    path_m=path,
                ),
            )
            if projected.hex() != row["permeability_m_per_s"][ion].hex():
                raise ValueError("Independent caller P/D contract failed")
            permeability[ion] = projected
            ledger["constitutive"].append(
                dict(
                    membrane_id=patch["id"],
                    species=ion,
                    caller_permeability_m_per_s=projected,
                    diffusivity_m2_per_s=diffusion,
                    path_m=path,
                    certificate=certificate,
                )
            )
        model["membranes"].append(
            dict(
                id=patch["id"],
                inside=patch["cell_id"],
                outside=patch["bath_id"],
                law="constant_field@1",
                area_m2=quantity.number(squared_area, root=True),
                capacitance_F=quantity.number(
                    quantity.multiply(
                        squared_area, quantity.multiply(ratio(specific), ratio(specific))
                    ),
                    root=True,
                ),
                permeability_m_per_s=permeability,
            )
        )
    for face in truth["faces"]:
        model["faces"].append(
            dict(
                id=face["id"],
                sender=face["sender"],
                receiver=face["receiver"],
                law="logmean_electrodiffusion@1",
                area_m2=quantity.number(edges[face["edge_id"]]["area_squared"], root=True),
                length_m=quantity.number(face["length_squared"], root=True),
                diffusivity_m2_per_s=rows["faces"][face["id"]]["diffusivity_m2_per_s"],
            )
        )
    definition = dict(
        schema_version=1, model=model, experiment=d["experiment"], execution=d["execution"]
    )
    partial["independent_definition"] = definition
    return definition, ledger


def assemble(definition, partial):
    """Own indexed arrays; topology is discovered by the full-node helper."""
    model = definition["model"]
    ions = [r["id"] for r in model["species"]]
    cells = [r["id"] for r in model["cells"]]
    baths = [r["id"] for r in model["extracellular"]]
    s, n, o, m, f = len(ions), len(cells), len(baths), len(model["membranes"]), len(model["faces"])
    p = dict(
        temperature=np.asarray(model["temperature_K"]),
        valence=np.asarray([r["valence"] for r in model["species"]], dtype=np.float64)[:, None],
        reservoir=np.zeros(o, dtype=bool),
    )
    for kind, size in (("cell", n), ("outside", o), ("membrane", m), ("junction", 0), ("face", f)):
        p[kind + "_active"] = np.ones(size, dtype=bool)
    p.update(
        membrane_cell=np.asarray(
            [cells.index(r["inside"]) for r in model["membranes"]], dtype=np.int64
        ),
        membrane_outside=np.asarray(
            [baths.index(r["outside"]) for r in model["membranes"]], dtype=np.int64
        ),
        membrane_area=np.asarray([r["area_m2"] for r in model["membranes"]]),
        membrane_capacitance=np.asarray([r["capacitance_F"] for r in model["membranes"]]),
        membrane_permeability=np.asarray(
            [[r["permeability_m_per_s"][ion] for r in model["membranes"]] for ion in ions]
        ),
        face_sender=np.asarray([baths.index(r["sender"]) for r in model["faces"]], dtype=np.int64),
        face_receiver=np.asarray(
            [baths.index(r["receiver"]) for r in model["faces"]], dtype=np.int64
        ),
        face_factor=np.asarray(
            [
                [
                    r["diffusivity_m2_per_s"][ion] * r["area_m2"] / r["length_m"]
                    for r in model["faces"]
                ]
                for ion in ions
            ]
        ),
        junction_sender=np.zeros(0, dtype=np.int64),
        junction_receiver=np.zeros(0, dtype=np.int64),
        junction_area=np.zeros(0),
        junction_permeability=np.zeros((s, 0)),
    )
    volume = np.asarray([r["volume_pL"] for r in model["cells"]])
    outside_volume = np.asarray([r["volume_pL"] for r in model["extracellular"]])
    amount = np.asarray([[r["initial_amount_fmol"][ion] for r in model["cells"]] for ion in ions])
    outside_amount = np.asarray(
        [[r["initial_amount_fmol"][ion] for r in model["extracellular"]] for ion in ions]
    )
    cell_q = np.asarray([r["initial_charge_C"] for r in model["cells"]])
    outside_q = np.asarray([r["initial_charge_C"] for r in model["extracellular"]])
    boundary = np.asarray([r["boundary_potential_V"] for r in model["extracellular"]])
    gauge = np.asarray([name == model["closure"]["gauge_reference"] for name in baths])
    controls = {
        r["membrane_id"]: r["schedule"][0]["availability"]
        for r in definition["experiment"]["membrane_controls"]
    }
    raw = dict(
        layout=p,
        ci=amount / volume,
        co=outside_amount / outside_volume,
        cell_charge_C=cell_q,
        outside_charge_C=outside_q,
        boundary_V=boundary,
        gauge_mask=gauge,
        membrane_open=np.asarray([controls[r["id"]] for r in model["membranes"]]),
        junction_open=np.zeros(0),
        seed_potential_V=np.r_[np.zeros(n), np.where(gauge, boundary, 0.0)],
    )
    partial["independent_initial_field_input"] = raw
    capacitor, active, reservoir, _, groups, _ = field.topology(raw)
    partial["independent_capacitor_topology"] = dict(capacitor=capacitor, groups=groups)
    fixed, free = ~active.copy(), []
    for members in groups:
        gauge_nodes = members[np.r_[np.zeros(n, bool), gauge][members]]
        representative = (
            int(gauge_nodes[0]) if len(gauge_nodes) else min(int(i) for i in members if i >= n)
        )
        fixed[representative] = True
        free.append(not bool(len(gauge_nodes)))
    basis = np.asarray([np.isin(np.arange(n + o), members).astype(float) for members in groups]).T
    scale = np.max(np.abs(capacitor))
    # This describes the public layout, while the field root uses all nodes.
    normalized = np.zeros_like(capacitor)
    for i in range(n + o):
        for j in range(n + o):
            normalized[i, j] = float(i == j) if fixed[i] or fixed[j] else capacitor[i, j] / scale
    layout = dict(
        p,
        field_gauge_mask=gauge,
        field_active=active,
        field_fixed=fixed,
        field_capacitor_matrix=capacitor,
        field_capacitor_scale=np.asarray(scale),
        field_capacitor_solve_matrix=normalized,
        field_floating_basis=basis,
        field_offset_free=np.asarray(free, dtype=bool),
        field_face_incidence=(basis[n + p["face_sender"]] - basis[n + p["face_receiver"]]).T,
        field_junction_incidence=np.zeros((len(groups), 0)),
        active=p["cell_active"],
        ids=np.arange(1, n + 1, dtype=np.int64),
        volume=volume,
        extracellular_volume=outside_volume,
        amount_reference=amount,
        extracellular_amount_reference=outside_amount,
        initial_cell_charge_C=cell_q,
        initial_outside_charge_C=outside_q,
        boundary_V=boundary,
    )
    partial["independent_layout_before_charge_solve"] = layout
    q, boundary_full = np.r_[cell_q, outside_q], np.r_[np.zeros(n), boundary]
    baseline, rhs = capacitor.copy() / scale, q / scale
    for i in np.flatnonzero(fixed):
        baseline[i, :] = 0
        baseline[i, i] = 1
        rhs[i] = boundary_full[i]
    base = np.linalg.solve(baseline, rhs)
    partial["independent_charge_only_return"] = base
    layout["initial_membrane_voltage_V"] = (
        base[p["membrane_cell"]] - base[n + p["membrane_outside"]]
    )
    shapes = ((s, n), (s, o), (s, m), (s, 0), (s, f), (s, o), (m,), (0,), (f,), (o,), (o,), (o,))
    state = {name: np.zeros(shape) for name, shape in zip(STATE_FIELDS, shapes, strict=True)}
    partial["independent_initial_layout_state"] = dict(layout=layout, state=state)
    return raw, layout, state, baseline, fixed


def accounting(raw, layout, values, rhs):
    p, rates = raw["layout"], values["rates"]
    cell, outside = rhs["amount_increment"].copy(), rhs["extracellular_amount_increment"].copy()
    for k, (i, j) in enumerate(zip(p["membrane_cell"], p["membrane_outside"], strict=True)):
        cell[:, i] += rates["membrane_flux_fmol_s"][:, k]
        outside[:, j] -= rates["membrane_flux_fmol_s"][:, k]
    for k, (i, j) in enumerate(zip(p["face_sender"], p["face_receiver"], strict=True)):
        outside[:, i] += rates["face_flux_fmol_s"][:, k]
        outside[:, j] -= rates["face_flux_fmol_s"][:, k]
    outside -= rhs["reservoir_supplied"]
    total = (
        rhs["amount_increment"].sum(axis=1)
        + rhs["extracellular_amount_increment"].sum(axis=1)
        - rhs["reservoir_supplied"].sum(axis=1)
    )
    q = np.r_[raw["cell_charge_C"], raw["outside_charge_C"]]
    cap = layout["field_capacitor_matrix"] @ values["potential_V"]
    ionic = (
        scalar.F
        * 1e-15
        * np.sum(
            p["valence"] * np.c_[rhs["amount_increment"], rhs["extracellular_amount_increment"]],
            axis=0,
        )
    )
    cap_rate, n = np.zeros(len(q)), len(raw["cell_charge_C"])
    for k, (i, j) in enumerate(zip(p["membrane_cell"], p["membrane_outside"], strict=True)):
        rate = p["membrane_capacitance"][k] * values["membrane_voltage_rate_V_s"][k]
        cap_rate[i] += rate
        cap_rate[n + j] -= rate
    scale = max(
        float(np.max(np.abs(rates[k + "_current_A"]), initial=0.0)) for k in ("face", "junction")
    )
    chemical = (
        1e-3
        * scalar.R
        * p["temperature"]
        * (
            np.sum(np.log(raw["ci"]) * rates["cell_rate_fmol_s"])
            + np.sum(np.log(raw["co"]) * rates["outside_rate_fmol_s"])
        )
    )
    capacitor_power = 1e12 * np.sum(
        p["membrane_capacitance"]
        * rates["membrane_voltage_V"]
        * values["membrane_voltage_rate_V_s"]
    )
    dissipated = sum(
        np.sum(rates[key + "_dissipation_pJ_s"]) for key in ("membrane", "junction", "face")
    )
    return dict(
        local_material_rate_fmol_s=cell,
        outside_material_rate_fmol_s=outside,
        global_material_rate_fmol_s=total,
        node_charge_residual_C=cap - q,
        node_charge_bound_C=CHARGE_ATOL + 2e-12 * np.maximum(np.abs(cap), np.abs(q)),
        local_charge_rate_residual_A=cap_rate - ionic,
        current_constraint_bound_A=1e-23 + 2e-12 * scale,
        all_component_current_residual_A=values["component_current_residual_A"],
        global_charge_rate_residual_A=np.sum(ionic) + np.sum(values["electrode_current_A"]),
        chemical_energy_rate_pJ_s=chemical,
        capacitor_energy_rate_pJ_s=capacitor_power,
        dissipation_pJ_s=dissipated,
        energy_balance_pJ_s=chemical + capacitor_power + dissipated,
    )


def accounting_valid(checks):
    if not all(np.isfinite(v).all() for v in checks.values()):
        return False
    material = all(
        np.all(np.abs(checks[k]) <= 3e-14)
        for k in (
            "local_material_rate_fmol_s",
            "outside_material_rate_fmol_s",
            "global_material_rate_fmol_s",
        )
    )
    charge = np.all(np.abs(checks["node_charge_residual_C"]) <= checks["node_charge_bound_C"])
    current = all(
        np.all(np.abs(checks[k]) <= checks["current_constraint_bound_A"])
        for k in (
            "local_charge_rate_residual_A",
            "all_component_current_residual_A",
            "global_charge_rate_residual_A",
        )
    )
    return bool(material and charge and current and abs(checks["energy_balance_pJ_s"]) <= 1e-10)


def solve_initial(raw, layout, state, matrix, fixed, partial):
    phi, receipt = field.solve(raw, partial)
    partial["independent_full_node_return"] = dict(potential_V=phi, solver_receipt=receipt)
    p, n = raw["layout"], len(raw["cell_charge_C"])
    rates = scalar.transport(raw, phi[:n], phi[n:])
    partial["independent_scalar_transport_return"] = rates
    rates["valid"] = np.asarray(all(np.isfinite(v).all() for v in rates.values()))
    capacitor = layout["field_capacitor_matrix"]
    q = np.r_[raw["cell_charge_C"], raw["outside_charge_C"]]
    ionic = (
        scalar.F
        * 1e-15
        * np.sum(
            p["valence"] * np.c_[rates["cell_rate_fmol_s"], rates["outside_rate_fmol_s"]], axis=0
        )
    )
    derivative_rhs = ionic / layout["field_capacitor_scale"]
    derivative_rhs[fixed] = 0
    derivative = np.linalg.solve(matrix, derivative_rhs)
    partial["independent_potential_rate_return"] = derivative
    vm_rate = derivative[p["membrane_cell"]] - derivative[n + p["membrane_outside"]]
    divergence, current_scale = field.currents(raw, phi)
    groups = [
        np.flatnonzero(layout["field_floating_basis"][:, i])
        for i in range(layout["field_floating_basis"].shape[1])
    ]
    current_residual = np.asarray(
        [math.fsum(float(divergence[i]) for i in members) for members in groups]
    )
    cap, residual = capacitor @ phi, capacitor @ phi - q
    charge_bound = CHARGE_ATOL + 2e-12 * np.maximum(np.abs(cap), np.abs(q))
    current_bound = 1e-23 + 2e-12 * current_scale
    membrane_charge = p["membrane_capacitance"] * rates["membrane_voltage_V"]
    capacitor_energy = 0.5e12 * np.sum(membrane_charge * rates["membrane_voltage_V"])
    capacitor_power = 1e12 * np.sum(membrane_charge * vm_rate)
    chemical = (
        1e-3
        * scalar.R
        * p["temperature"]
        * (
            np.sum(np.log(raw["ci"]) * rates["cell_rate_fmol_s"])
            + np.sum(np.log(raw["co"]) * rates["outside_rate_fmol_s"])
        )
    )
    dissipated = sum(
        np.sum(rates[k + "_dissipation_pJ_s"]) for k in ("membrane", "junction", "face")
    )
    values = dict(
        potential_V=phi,
        membrane_charge_C=membrane_charge,
        capacitor_node_charge_C=cap,
        charge_residual_C=residual,
        charge_normalized=np.max(np.abs(residual) / charge_bound),
        component_current_residual_A=current_residual,
        current_normalized=np.max(np.abs(current_residual), initial=0.0) / current_bound,
        electrode_charge_C=np.zeros(len(phi) - n),
        electrode_current_A=np.zeros(len(phi) - n),
        reservoir_supply_charge_A=np.zeros(len(phi) - n),
        membrane_voltage_rate_V_s=vm_rate,
        capacitor_energy_pJ=capacitor_energy,
        capacitor_energy_rate_pJ_s=capacitor_power,
        chemical_energy_rate_pJ_s=chemical,
        reservoir_power_pJ_s=0.0,
        electrode_power_pJ_s=0.0,
        dissipation_pJ_s=dissipated,
        energy_balance_pJ_s=chemical + capacitor_power + dissipated,
        rates=rates,
        iterations=None,
        converged=np.asarray(True),
    )
    partial["independent_complete_field_return"] = values
    rhs = dict(
        zip(
            STATE_FIELDS,
            (
                rates["cell_rate_fmol_s"],
                rates["outside_rate_fmol_s"],
                rates["membrane_flux_fmol_s"],
                rates["junction_flux_fmol_s"],
                rates["face_flux_fmol_s"],
                rates["reservoir_supply_fmol_s"],
                rates["membrane_dissipation_pJ_s"],
                rates["junction_dissipation_pJ_s"],
                rates["face_dissipation_pJ_s"],
                values["electrode_current_A"],
                np.zeros(len(phi) - n),
                np.zeros(len(phi) - n),
            ),
            strict=True,
        )
    )
    partial["independent_complete_RHS_return"] = rhs
    checks = accounting(raw, layout, values, rhs)
    partial["independent_accounting_return"] = checks
    if not accounting_valid(checks) or not bool(rates["valid"]):
        raise ValueError("Independent initial material/charge/energy accounting failed")
    namespace = SimpleNamespace(**dict(values, rates=SimpleNamespace(**rates)))
    partial["frozen_independent_accounting_return"] = field.check(raw, namespace)
    return dict(
        state=state,
        layout=layout,
        control=dict(membrane=raw["membrane_open"], junction=raw["junction_open"]),
        field=values,
        rhs=rhs,
        accounting=checks,
        state_diagnostics={name: 0.0 for name in DIAGNOSTICS},
    )


def derive(request, geometry, geometry_truth, partial):
    definition, ledger = materialize(request, geometry, geometry_truth, partial)
    raw, layout, state, matrix, fixed = assemble(definition, partial)
    result = solve_initial(raw, layout, state, matrix, fixed, partial)
    result.update(
        definition=definition, conversions=ledger, raw=raw, geometry_targets=geometry_truth
    )
    return result


def decode(record, *, label):
    require(
        type(record) is dict and set(record) == {"kind", "dtype", "shape", "data_hex"},
        label + ": typed fields",
    )
    require(record["kind"] == "typed_C_order_array_bytes@1", label + ": typed kind")
    require(
        type(record["dtype"]) is str and record["dtype"] in {"<f8", "<i8", "<i4", "|b1"},
        label + ": real dtype",
    )
    require(type(record["shape"]) is list and len(record["shape"]) <= 3, label + ": rank")
    require(all(type(v) is int and 0 <= v <= 256 for v in record["shape"]), label + ": shape")
    require(
        type(record["data_hex"]) is str and len(record["data_hex"]) <= 4 * 2**20,
        label + ": bytes bound",
    )
    try:
        data = bytes.fromhex(record["data_hex"])
    except ValueError as error:
        raise SnapshotRejected(label + ": invalid hexadecimal array") from error
    dtype = np.dtype(record["dtype"])
    require(len(data) == math.prod(record["shape"]) * dtype.itemsize, label + ": byte count")
    result = np.frombuffer(data, dtype=dtype).reshape(record["shape"])
    require(np.isfinite(result).all(), label + ": finite values")
    return result


def tolerance(name):
    if "voltage" in name or "potential" in name or name == "boundary_V":
        return 3e-8 if "rate" in name else VOLTAGE_ATOL
    if "delta_mu" in name:
        return 3e-8
    if "current" in name or name.endswith("_A"):
        return CURRENT_ATOL
    if "charge" in name or name.endswith("_C"):
        return CHARGE_ATOL
    if "energy" in name and "rate" not in name and "balance" not in name:
        return 3e-12
    if any(part in name for part in ("energy", "dissipation", "power", "work")):
        return POWER_ATOL
    if "capacit" in name:
        return CHARGE_ATOL
    return FLUX_ATOL


def compare_arrays(actual, expected, *, label, rows):
    require(type(actual) is dict and set(actual) == set(expected), label + ": named inventory")
    for name, target in expected.items():
        path = label + "/" + name
        if type(target) is dict:
            compare_arrays(actual[name], target, label=path, rows=rows)
            continue
        observed = decode(actual[name], label=path)
        if target is None:
            require(
                name == "iterations" and observed.shape == () and observed.dtype.kind in "iu",
                path + ": solver metadata",
            )
            require(0 <= int(observed) <= 16, path + ": existing Newton bound")
            rows.append(
                dict(
                    field=path,
                    mode="solver_metadata_domain",
                    independent_iteration_count_claimed=False,
                )
            )
            continue
        target = np.asarray(target)
        require(
            observed.shape == target.shape and observed.dtype.str == target.dtype.str,
            path + ": dtype/axes",
        )
        if target.dtype.kind in "biu":
            require(np.array_equal(observed, target), path + ": exact integer/mask/bool")
        elif name in {"charge_normalized", "current_normalized"}:
            require(
                observed.shape == () and 0 <= float(observed) <= 1.0,
                path + ": normalized residual domain",
            )
        elif label in {"state", "control"}:
            require(np.array_equal(observed, target), path + ": exact initial values")
        elif (
            label == "layout"
            and not name.startswith("field_")
            and name != "initial_membrane_voltage_V"
        ):
            require(np.array_equal(observed, target), path + ": complete physical layout")
        elif name.startswith("field_") and ("basis" in name or "incidence" in name):
            require(np.array_equal(observed, target), path + ": exact component structure")
        else:
            atol = 2e-12 if name == "field_capacitor_solve_matrix" else tolerance(name)
            require(
                np.allclose(observed, target, rtol=RTOL, atol=atol), path + ": independent target"
            )
        rows.append(
            dict(
                field=path,
                shape=list(observed.shape),
                dtype=observed.dtype.str,
                complete_field_verified=True,
            )
        )


def verify_snapshot(preparation, truth, *, exact):
    snapshot = preparation["initial_snapshot"]
    require(
        type(snapshot) is dict
        and set(snapshot)
        == {
            "time_s",
            "state",
            "layout",
            "control",
            "time_advanced",
            "field",
            "rhs",
            "accounting",
            "state_diagnostics",
            "initial_accounting_passed",
            "independent_physical_validation_required",
            "solver_trajectory_executed",
        },
        "complete initial snapshot",
    )
    for name, expected in (
        ("time_s", 0.0),
        ("time_advanced", False),
        ("initial_accounting_passed", True),
        ("independent_physical_validation_required", True),
        ("solver_trajectory_executed", False),
    ):
        require(
            type(snapshot[name]) is type(expected) and snapshot[name] == expected,
            "initial limit: " + name,
        )
    rows = []
    for name in ("state", "layout", "control", "field", "rhs", "accounting"):
        compare_arrays(snapshot[name], truth[name], label=name, rows=rows)
    exact(
        preparation["conversions"],
        truth["conversions"],
        "complete concentration/constitutive defects",
    )
    exact(snapshot["state_diagnostics"], truth["state_diagnostics"], "complete initial diagnostics")
    try:
        definition = json.loads(preparation["physical_preparation"]["definition_json"])
    except json.JSONDecodeError as error:
        raise SnapshotRejected("physical definition JSON") from error
    exact(
        definition, truth["definition"], "complete independently materialized physical definition"
    )
    values = {
        name: (
            {key: decode(value, label="field/rates/" + key) for key, value in record.items()}
            if name == "rates"
            else decode(record, label="field/" + name)
        )
        for name, record in snapshot["field"].items()
    }
    rhs = {name: decode(value, label="rhs/" + name) for name, value in snapshot["rhs"].items()}
    checks = accounting(truth["raw"], truth["layout"], values, rhs)
    require(accounting_valid(checks), "observed local/global material/charge/energy budgets")
    claimed_checks = {
        name: decode(value, label="accounting/" + name)
        for name, value in snapshot["accounting"].items()
    }
    require(accounting_valid(claimed_checks), "claimed accounting must satisfy existing budgets")
    for name in ("node_charge_bound_C", "current_constraint_bound_A"):
        require(
            np.allclose(claimed_checks[name], checks[name], rtol=2e-12, atol=0.0),
            "unchanged mathematical accounting bound: " + name,
        )
    try:
        field.check(
            truth["raw"], SimpleNamespace(**dict(values, rates=SimpleNamespace(**values["rates"])))
        )
    except AssertionError as error:
        raise SnapshotRejected("observed full-node scalar charge/current/energy checks") from error
    cap = values["capacitor_node_charge_C"]
    q = np.r_[truth["raw"]["cell_charge_C"], truth["raw"]["outside_charge_C"]]
    norm = np.max(
        np.abs(values["charge_residual_C"])
        / (CHARGE_ATOL + 2e-12 * np.maximum(np.abs(q), np.abs(cap)))
    )
    require(
        np.isclose(values["charge_normalized"], norm, rtol=RTOL, atol=1e-14),
        "charge normalized metadata link",
    )
    scale = max(
        float(np.max(np.abs(values["rates"][key + "_current_A"]), initial=0.0))
        for key in ("face", "junction")
    )
    norm = np.max(np.abs(values["component_current_residual_A"]), initial=0.0) / (
        1e-23 + 2e-12 * scale
    )
    require(
        np.isclose(values["current_normalized"], norm, rtol=RTOL, atol=1e-14),
        "current normalized metadata link",
    )
    return dict(
        passed=True,
        complete_named_array_inventory=rows,
        represented_concentration_defects_verified=True,
        full_node_physics_and_RHS_verified=True,
        accounting_passed=True,
        time_advanced=False,
        production_functions_called=False,
    )
