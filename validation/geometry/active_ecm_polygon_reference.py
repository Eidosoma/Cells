"""Independent active finite-ECM conversions, initial RHS and physical fields.

The conversion lane is standard-library only. Scientific references are lazy
and run behind a guard denying Cells/BETSE/JAX, with no time advancement.
"""

import importlib
import json
import math
from pathlib import Path

from validation.geometry import active_polygon_physiology_reference as active
from validation.geometry import finite_ecm_polygon_reference as ecm

ratio, multiply, subtract, divide = ecm.ratio, ecm.multiply, ecm.subtract, ecm.divide
semantic = active.semantic
REFERENCE_MODULES = active.REFERENCE_MODULES

# Actual and independently reconstructed total-energy residual limits in pJ/s.
# Unlike the active-polygon reference, this ECM reference constructs the full
# ionic identity. Its prospective 1e-10 ionic gate comes from the field protocol.
ENERGY_LIMITS = {
    "resolved_tissue@2": (1e-10, 1e-10),
    "resolved_tissue@12": (1e-10, 1e-10),
    "resolved_energy@1": (2e-8, 2e-8),
    "resolved_energy@2": (2e-8, 2e-10),
    "resolved_calcium@1": (1e-10, 1e-10),
    "resolved_calcium@11": (1e-10, 1e-10),
    "resolved_calcium_energy@1": (2e-10, 3e-10),
    "resolved_calcium_energy@5": (1e-10, 3e-10),
    "resolved_open_calcium@1": (1e-10, 1e-10),
    "resolved_open_calcium_energy@1": (1e-10, 1e-10),
}


def energy_evidence(model_id, actual, independent):
    actual_limit, reference_limit = ENERGY_LIMITS[model_id]
    return dict(
        actual_energy_balance_pJ_s=float(actual),
        actual_absolute_budget_pJ_s=actual_limit,
        independent_energy_balance_pJ_s=float(independent),
        independent_absolute_budget_pJ_s=reference_limit,
        independent_identity_available=True,
    )


def assert_energy(model_id, record):
    actual_limit, reference_limit = ENERGY_LIMITS[model_id]
    assert record["actual_absolute_budget_pJ_s"] == actual_limit
    assert record["independent_absolute_budget_pJ_s"] == reference_limit
    assert record["independent_identity_available"] is True
    actual = record["actual_energy_balance_pJ_s"]
    independent = record["independent_energy_balance_pJ_s"]
    assert math.isfinite(actual) and abs(actual) <= actual_limit
    assert math.isfinite(independent) and abs(independent) <= reference_limit


def rounded(exact, *, radical=False):
    return ecm.number(exact, root=radical)


def materialize(declaration, g, request, *, refinement=1):
    target = ecm.evaluate(declaration, refinement=refinement)
    cells = target["regions"]
    membranes = {row["id"]: row for row in target["membranes"]}
    faces = {row["id"]: row for row in target["faces"]}
    edges = {row["id"]: row for row in target["edges"]}
    partitions = {row["cell_id"]: ratio(row["ER_fraction"]) for row in request["cell_partitions"]}
    er = {row["cell_id"]: row for row in request["ER_geometry"]}
    conversions = []

    def visit(value, path=()):
        if isinstance(value, dict) and "$geometry" in value:
            name = value["$geometry"]
            root = False
            if name == "cell_volume_pL":
                cell = value["cell_id"]
                q = cells[cell]["volume"]
                if value["role"] != "total":
                    fraction = partitions[cell]
                    q = multiply(
                        q, fraction if value["role"] == "ER" else subtract(ratio(1), fraction)
                    )
                q = multiply(q, ratio(1e15))
                units = "pL"
            elif name == "bath_volume_pL":
                q = multiply(cells[value["bath_id"]]["volume"], ratio(1e15))
                units = "pL"
            elif name in ("membrane_area_m2", "membrane_capacitance_F", "face_area_m2"):
                owner = (
                    faces[value["face_id"]]
                    if name == "face_area_m2"
                    else membranes[value["membrane_id"]]
                )
                q = edges[owner["edge_id"]]["area_squared"]
                root = True
                units = "m2"
                if name == "membrane_capacitance_F":
                    c = ratio(value["specific_capacitance_F_per_m2"])
                    q = multiply(q, multiply(c, c))
                    units = "F"
            elif name == "face_length_m":
                q = faces[value["face_id"]]["length_squared"]
                root = True
                units = "m"
            elif name == "ER_area_m2":
                q = ratio(er[value["cell_id"]]["area_m2"])
                units = "m2"
            elif name.endswith("permeability_m_per_s"):
                path_length = (
                    declaration["membrane_thickness_m"]
                    if name.startswith("membrane_")
                    else er[value["cell_id"]]["thickness_m"]
                )
                q = divide(ratio(value["diffusivity_m2_per_s"]), ratio(path_length))
                units = "m/s"
            else:
                raise ValueError("Unknown active-ECM geometry reference")
            number = ecm.number(q, root=root, precision=target["precision_digits"])
            conversions.append(
                dict(
                    path=list(path),
                    reference=value,
                    exact_target=q,
                    root=root,
                    units=units,
                    value_binary64_hex=number.hex(),
                )
            )
            return number
        if isinstance(value, dict):
            return {key: visit(item, (*path, key)) for key, item in value.items()}
        if isinstance(value, list):
            return [visit(item, (*path, index)) for index, item in enumerate(value)]
        return value

    return dict(
        definition=visit(request["definition_template"]),
        conversions=conversions,
        geometry_targets=target,
    )


def compare_conversion(packet, primary, refined):
    geometry = ecm.compare_geometry(
        packet["geometry_declaration"],
        packet["geometry"],
        primary["geometry_targets"],
        refined["geometry_targets"],
    )
    assert primary["definition"] == refined["definition"]
    assert semantic(primary["definition"]) == semantic(packet["definition"])
    actual = {tuple(row["path"]): row for row in packet["provenance"]["conversions"]}
    expected = {tuple(row["path"]): row for row in primary["conversions"]}
    assert set(actual) == set(expected)
    for path, row in expected.items():
        found = actual[path]
        for key in ("reference", "units", "value_binary64_hex"):
            assert found[key] == row[key]
        assert found["certificate"]["radicand" if row["root"] else "exact"] == row["exact_target"]
    return dict(
        status="passed",
        geometry=geometry,
        conversion_count=len(expected),
        complete_inventory_chemistry_fuel_control_and_owner_declarations_preserved=True,
        production_functions_called=False,
        qualification_inherited=False,
    )


def _field_targets(raw, context, reference, expected, phi, time):
    """Assemble aggregate plasma sources from separate independent ledgers.

    Ordinary channels, Na/K, PMCA, NCX and Cav contribute once to their explicit
    patch owner. Full ER chemistry and neutral fuel remain separate energy owners.
    """
    import numpy as np

    from validation.chemistry import finite_energy_reference as fuel
    from validation.tissue import surface_dynamics_reference as dynamics
    from validation.tissue import surface_field_reference as electrical
    from validation.tissue import surface_reference as transport

    outer = raw["model"]
    ion = outer.get("ionic", outer)
    has_ca = "stores" in outer
    has_fuel = "energy_pools" in outer
    ids = [row["id"] for row in ion["species"]]
    n, o = len(ion["cells"]), len(ion["extracellular"])
    parts = reference.unpack(context, expected)
    # A separate direct declaration binding supplies only passive geometry and
    # concentrations; no production parser or state is used in this reference.
    passive = dynamics.bind(
        dict(model=ion, experiment=raw["experiment"], execution=raw["execution"])
    )
    passive_state = dynamics.initial(passive)
    stage = dynamics.stage(passive, passive_state, time)
    rates = transport.transport(stage, phi[:n], phi[n:])
    membrane = parts["membrane_transferred"].copy()
    heat = parts["membrane_dissipated_energy_pJ"].copy() + parts["pump_dissipated_energy_pJ"]
    patches = {row["id"]: i for i, row in enumerate(ion["membranes"])}
    channels = parts["channel_transferred"]
    channel_heat = parts["channel_dissipated_energy_pJ"]
    for index, row in enumerate(ion["channels"]):
        patch = patches[row["membrane_id"]]
        if channels.ndim == 1:
            membrane[ids.index(row["species_id"]), patch] += channels[index]
            heat[patch] += channel_heat[index]
        else:
            membrane[:, patch] += channels[:, index]
            heat[patch] += np.sum(channel_heat[:, index])
    for index, row in enumerate(ion["membranes"]):
        if row["pump"] is not None:
            for species, coefficient in row["pump"]["stoichiometry"].items():
                membrane[ids.index(species), index] -= coefficient * parts["pump_cycles"][index]
    if has_ca:
        ca = ids.index(outer["plasma_transport"]["calcium_species"])
        na = ids.index(outer["plasma_transport"]["sodium_species"])
        membrane[ca] += (
            parts["plasma_pump_cycles"]
            + parts["plasma_exchange_cycles"]
            + parts["calcium_channel_transferred"]
        )
        membrane[na] -= 3 * parts["plasma_exchange_cycles"]
        heat += (
            np.sum(parts["plasma_dissipated_energy_pJ"], axis=0)
            + parts["calcium_channel_dissipated_energy_pJ"]
        )
    z = np.asarray([row["valence"] for row in ion["species"]])[:, None]
    rates.update(
        cell_rate_fmol_s=parts["amount_increment"],
        outside_rate_fmol_s=parts["extracellular_amount_increment"],
        reservoir_supply_fmol_s=parts["reservoir_supplied"],
        membrane_flux_fmol_s=membrane,
        membrane_current_A=dynamics.F * 1e-15 * np.sum(z * membrane, axis=0),
        membrane_dissipation_pJ_s=heat,
    )
    cell_sources = np.zeros_like(parts["amount_increment"])
    bath_sources = np.zeros_like(parts["extracellular_amount_increment"])
    cell_ids = [row["id"] for row in ion["cells"]]
    bath_ids = [row["id"] for row in ion["extracellular"]]
    for index, row in enumerate(ion["membranes"]):
        cell_sources[:, cell_ids.index(row["inside"])] -= membrane[:, index]
        bath_sources[:, bath_ids.index(row["outside"])] += membrane[:, index]
    for index, row in enumerate(ion["faces"]):
        flux = parts["face_transferred"][:, index]
        bath_sources[:, bath_ids.index(row["sender"])] -= flux
        bath_sources[:, bath_ids.index(row["receiver"])] += flux
    source_error = max(
        float(
            np.max(
                np.abs(cell_sources - parts["amount_increment"])
                / (3e-12 + 3e-10 * np.abs(parts["amount_increment"])),
                initial=0,
            )
        ),
        float(
            np.max(
                np.abs(bath_sources - parts["extracellular_amount_increment"])
                / (3e-12 + 3e-10 * np.abs(parts["extracellular_amount_increment"])),
                initial=0,
            )
        ),
    )
    material = np.c_[parts["amount_increment"], parts["extracellular_amount_increment"]]
    charge = dynamics.F * 1e-15 * np.sum(z * material, axis=0)
    matrix, active_nodes, reservoir, _, floating, _ = electrical.topology(stage)
    pins = ~active_nodes | reservoir
    for members in floating:
        pins[members[0]] = True
    free = np.flatnonzero(~pins)
    dphi = np.zeros_like(phi)
    dphi[free] = np.linalg.solve(matrix[np.ix_(free, free)], charge[free])
    p = passive["layout"]
    mi = np.asarray(p["membrane_cell"])
    mo = np.asarray(p["membrane_outside"])
    vm = phi[mi] - phi[n + mo]
    dvm = dphi[mi] - dphi[n + mo]
    caps = np.asarray(p["membrane_capacitance"])
    cap_power = float(1e12 * np.sum(caps * vm * dvm))
    rt = dynamics.R * ion["temperature_K"]
    chemical = (
        1e-3
        * rt
        * np.sum(np.log(passive["ao"] / passive["vo"]) * parts["extracellular_amount_increment"])
    )
    er_power = 0.0
    if has_ca:
        stores = {row["cell_id"]: row["model"] for row in outer["stores"]}
        for i, cell in enumerate(ion["cells"]):
            store = stores[cell["id"]]
            names = [row["id"] for row in store["species"]]
            initial = np.asarray(
                [
                    [part["initial_amount_fmol"][name] for part in store["compartments"]]
                    for name in names
                ]
            )
            volumes = np.asarray([part["volume_pL"] for part in store["compartments"]])
            mu0 = np.asarray([row["standard_mu_RT"] for row in store["species"]])[:, None]
            chemistry = parts["chemical_amount_increment"][i]
            chemical += (
                1e-3
                * rt
                * np.sum(
                    (mu0 + np.log(initial / (volumes * store["standard_concentration_mM"])))
                    * chemistry
                )
            )
            er_index = [part["id"] for part in store["compartments"]].index(store["membrane"]["er"])
            valence = np.asarray([row["valence"] for row in store["species"]])
            er_power += (
                1e12
                * store["membrane"]["initial_voltage_V"]
                * dynamics.F
                * 1e-15
                * np.sum(valence * chemistry[:, er_index])
            )
    else:
        chemical += (
            1e-3 * rt * np.sum(np.log(passive["ai"] / passive["vi"]) * parts["amount_increment"])
        )
    dissipation = sum(
        float(np.sum(value))
        for name, value in parts.items()
        if name.endswith("_dissipated_energy_pJ")
    )
    if has_fuel:
        pools = {row["cell_id"]: row for row in outer["energy_pools"]}
        pool_power = 0.0
        for i, cell in enumerate(ion["cells"]):
            pool = pools[cell["id"]]
            amount = np.asarray([pool["initial_amount_fmol"][s] for s in ("ATP", "ADP", "Pi")])
            thermodynamics = fuel.thermodynamics(
                amount, cell["volume_pL"], ion["temperature_K"], pool["delta_g0_J_per_mol"]
            )
            pool_power += 1e-3 * np.dot(
                thermodynamics["chemical_potential_J_mol"],
                parts["energy_amount_increment_fmol"][:, i],
            )
        balance = (
            chemical
            + cap_power
            + er_power
            + pool_power
            + dissipation
            - float(np.sum(parts["regeneration_supplied_work_pJ"]))
        )
    else:
        work = sum(
            float(np.sum(value))
            for name, value in parts.items()
            if name in ("metabolic_work_pJ", "plasma_metabolic_work_pJ", "er_metabolic_work_pJ")
        )
        balance = chemical + cap_power + er_power + dissipation - work
    fields = dict(
        potential_V=phi,
        membrane_charge_C=caps * vm,
        capacitor_node_charge_C=matrix @ phi,
        electrode_charge_C=np.zeros(o),
        electrode_current_A=np.zeros(o),
        reservoir_supply_charge_A=np.zeros(o),
        membrane_voltage_rate_V_s=dvm,
        capacitor_energy_pJ=0.5e12 * np.sum(caps * vm * vm),
        capacitor_energy_rate_pJ_s=cap_power + er_power,
        chemical_energy_rate_pJ_s=chemical,
        reservoir_power_pJ_s=0.0,
        electrode_power_pJ_s=0.0,
        dissipation_pJ_s=dissipation,
        energy_balance_pJ_s=balance,
    )
    fields.update({"rates__" + name: value for name, value in rates.items()})
    return (
        fields,
        parts,
        dict(
            capacitive_components=len(floating),
            independent_energy_balance_pJ_s=float(balance),
            aggregate_membrane_flux_fmol_s=membrane.tolist(),
            aggregate_membrane_heat_pJ_s=heat.tolist(),
            source_owner_balance_error_over_budget=source_error,
        ),
    )


def compare_initial_field(packet, *, retain):
    import numpy as np

    raw = packet["definition"]
    outer = raw["model"]
    ion = outer.get("ionic", outer)
    ref = importlib.import_module("validation.tissue." + REFERENCE_MODULES[outer["id"]])
    context = ref.bind(raw)
    initial = ref.initial(context)
    retain(
        "reference-initial",
        dict(
            state=initial.tolist(),
            shapes={key: list(shape) for key, shape in context["shapes"].items()},
        ),
    )
    tolerance = json.loads(
        (Path(__file__).resolve().parents[1] / "tissue/surface_field_protocol.json").read_text()
    )["tolerances"]
    n, o = len(ion["cells"]), len(ion["extracellular"])
    nm, nf = len(ion["membranes"]), len(ion["faces"])
    node_indices = list(range(n)) + list(
        range(raw["execution"]["capacity"], raw["execution"]["capacity"] + o)
    )

    def pack(values):
        assert set(values) == set(context["shapes"])
        for name, shape in context["shapes"].items():
            array = np.asarray(values[name])
            assert array.ndim == len(shape)
            assert all(a >= b for a, b in zip(array.shape, shape, strict=True))
            mask = np.ones(array.shape, dtype=bool)
            mask[tuple(slice(0, v) for v in shape)] = False
            assert np.isfinite(array).all() and not np.any(array[mask])
        return ref.flatten(context, values)

    np.testing.assert_array_equal(pack(packet["state"]), initial)
    for name in ("face_sender", "face_receiver"):
        np.testing.assert_array_equal(
            np.asarray(packet["layout"][name])[:nf], context["layout"][name]
        )
    np.testing.assert_array_equal(
        np.asarray(packet["layout"]["face_factor"])[:, :nf], context["layout"]["face_factor"]
    )
    absolute = ref.flatten(
        context,
        {
            key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
            for key, shape in context["shapes"].items()
        },
    )
    reports = []
    for index, trial in enumerate(packet["initial_control_probes"]):
        expected, phi, proof = ref.evaluate(context, initial, trial["time_s"])
        retain(
            "reference-RHS-" + str(index),
            dict(derivative=expected.tolist(), potential_V=phi.tolist(), root=proof),
        )
        fields, parts, accounting = _field_targets(
            raw, context, ref, expected, phi, trial["time_s"]
        )
        observed = pack(trial["derivative"])
        budget = absolute + 3e-10 * np.abs(expected)
        comparisons = []
        for name, target in fields.items():
            if name.startswith("rates__"):
                key = name.removeprefix("rates__")
                value = np.asarray(trial["field"]["rates"][key])
                if key == "cell_rate_fmol_s":
                    value = value[:, :n]
                elif key in ("outside_rate_fmol_s", "reservoir_supply_fmol_s"):
                    value = value[:, :o]
                else:
                    value = value[
                        ...,
                        : nm
                        if key.startswith("membrane_")
                        else nf
                        if key.startswith("face_")
                        else 0,
                    ]
            else:
                value = np.asarray(trial["field"][name])
                if name in ("potential_V", "capacitor_node_charge_C"):
                    value = value[node_indices]
                elif name in ("membrane_charge_C", "membrane_voltage_rate_V_s"):
                    value = value[:nm]
                elif name in (
                    "electrode_charge_C",
                    "electrode_current_A",
                    "reservoir_supply_charge_A",
                ):
                    value = value[:o]
            atol = tolerance["flux_atol_fmol_s"]
            for suffix, key in (
                ("_V_s", "voltage_rate_atol_V_s"),
                ("_V", "voltage_atol_V"),
                ("_C", "charge_atol_C"),
                ("_J_mol", "chemical_potential_atol_J_mol"),
                ("_A", "current_comparison_atol_A"),
                ("_pJ_s", "power_atol_pJ_s"),
                ("_pJ", "energy_atol_pJ"),
            ):
                if name.endswith(suffix):
                    atol = tolerance[key]
                    break
            bounds = atol + tolerance["physical_rtol"] * np.abs(target)
            comparisons.append(
                dict(
                    name=name,
                    actual=value.tolist(),
                    independent=np.asarray(target).tolist(),
                    budget=np.asarray(bounds).tolist(),
                    error_over_budget=float(np.max(np.abs(value - target) / bounds, initial=0)),
                )
            )
        intended = np.asarray(
            [
                packet["request"]["provenance"]["declared_cell_potential_V"][row["id"]]
                for row in ion["cells"]
            ]
        )
        record = dict(
            time_s=trial["time_s"],
            actual_derivative=observed.tolist(),
            independent_derivative=expected.tolist(),
            derivative_budget=budget.tolist(),
            derivative_error_over_budget=float(
                np.max(np.abs(observed - expected) / budget, initial=0)
            ),
            reference_full_node_root=proof,
            physical_field_comparisons=comparisons,
            accounting=accounting,
            energy=energy_evidence(
                outer["id"],
                trial["field"]["energy_balance_pJ_s"],
                accounting["independent_energy_balance_pJ_s"],
            ),
            intended_cell_potential_error_over_budget=float(
                np.max(np.abs(phi[:n] - intended) / (3e-13 + 3e-10 * np.abs(intended)), initial=0)
            ),
            independent_face_flux_fmol_s=parts["face_transferred"].tolist(),
            production_stage_valid=trial["valid"],
            transport_valid=bool(trial["field"]["rates"]["valid"]),
        )
        retain("reference-stage-" + str(index), record)
        reports.append(record)
    return dict(
        status="compared",
        model_id=outer["id"],
        stages=reports,
        complete_state_field_count=len(context["shapes"]),
        production_functions_called=False,
        time_advanced=False,
        native_equivalence=False,
    )


def assert_initial_field(report):
    for stage in report["stages"]:
        assert stage["production_stage_valid"] and stage["transport_valid"]
        assert stage["derivative_error_over_budget"] <= 1
        assert stage["intended_cell_potential_error_over_budget"] <= 1
        assert all(row["error_over_budget"] <= 1 for row in stage["physical_field_comparisons"])
        assert_energy(report["model_id"], stage["energy"])
        assert (
            stage["energy"]["independent_energy_balance_pJ_s"]
            == stage["accounting"]["independent_energy_balance_pJ_s"]
        )
        assert stage["accounting"]["source_owner_balance_error_over_budget"] <= 1
        assert stage["accounting"]["capacitive_components"] > 1
        assert any(value != 0 for row in stage["independent_face_flux_fmol_s"] for value in row)
