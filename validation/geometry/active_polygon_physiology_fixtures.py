"""Deferred complete synthetic active worlds with explicit polygon owners.

Every quantity is a caller declaration. These manufactured initial states and
rates are for admission/conversion/initial-flow checks, without biological fits.
No fixture is materialized by static preparation.
"""

import json
import math
from copy import deepcopy
from pathlib import Path

from validation.geometry import active_polygon_physiology_reference as independent

LAW_ID = "cells_polygon_active_physiology_preparation@1"
REQUEST_KIND = "cells.polygon_active_physiology_request@1"
CASE_MODELS = {
    "ionic-basic": "resolved_tissue@2",
    "ionic-full": "resolved_tissue@12",
    "calcium-basic": "resolved_calcium@1",
    "calcium-full": "resolved_calcium@11",
    "fuel-ionic": "resolved_energy@1",
    "fuel-ionic-ml": "resolved_energy@2",
    "fuel-calcium": "resolved_calcium_energy@1",
    "fuel-calcium-full": "resolved_calcium_energy@5",
    "open-calcium-mixed": "resolved_open_calcium@1",
    "open-fuel-mixed": "resolved_open_calcium_energy@1",
    "calcium-merged": "resolved_calcium@1",
    "full-nonuniform-reordered": "resolved_tissue@12",
    "open-fuel-all-held": "resolved_open_calcium_energy@1",
    "open-calcium-empty": "resolved_open_calcium@1",
    "fuel-calcium-depleted": "resolved_calcium_energy@5",
}
CASES = tuple(CASE_MODELS)
DOMAIN_CASES = (
    "unsupported-water-family",
    "passive-relabel",
    "wrong-nested-family",
    "wrong-law",
    "wrong-geometry-id",
    "missing-provenance",
    "non298-temperature",
    "exterior-spatial-face",
    "missing-cell",
    "wrong-patch-cell",
    "wrong-patch-bath",
    "wrong-reference-owner",
    "numeric-volume-override",
    "numeric-area-override",
    "numeric-capacitance-override",
    "numeric-channel-permeability",
    "reference-in-inventory",
    "reference-in-control",
    "negative-diffusivity",
    "zero-specific-capacitance",
    "missing-junction",
    "reversed-junction",
    "wrong-reciprocal-membranes",
    "zero-junction-path",
    "centroid-junction-path-policy",
    "missing-ER-partition",
    "zero-ER-fraction",
    "unit-ER-fraction",
    "unknown-ER-volume-policy",
    "missing-ER-geometry",
    "zero-ER-thickness",
    "wrong-ER-compartment-role",
    "wrong-free-ion-amount",
    "missing-calcium-route",
    "wrong-Cav-owner",
    "missing-IP3-binding",
    "missing-fuel-pool",
    "cross-cell-NaK-fuel",
    "cross-cell-PMCA-fuel",
    "cross-cell-ER-fuel",
    "unknown-regeneration-pool",
    "maintained-pump-in-fuel-family",
    "closed-calcium-held-bath",
    "closed-fuel-held-bath",
    "missing-open-policy",
    "open-ceiling-below-true-moiety",
    "empty-open-nonnull-ceiling",
    "missing-control",
    "unordered-control-clock",
    "existing-charge-closure-refusal",
)
MUTATION_CASES = (
    "definition-area",
    "definition-inventory",
    "definition-fuel",
    "provenance-owner",
    "returned-copy-alias",
)
CORRUPTION_CASES = (
    "volume",
    "capacitance",
    "channel-path",
    "fuel-owner",
    "reservoir-flag",
    "control-clock",
)


def geometry_case(case):
    if case == "calcium-merged":
        return "merged-square"
    return "two-baths" if case.startswith("open-") else "two-triangles"


def ref(quantity, **owners):
    return {"$geometry": quantity, **owners}


def _change(family, name, value=0.8):
    return {
        family + "_id": name,
        "schedule": [dict(time=0.0, availability=value), dict(time=5e-7, availability=0.55)],
    }


def request(case, declaration, binding):
    if case not in CASE_MODELS:
        raise ValueError(case)
    target = CASE_MODELS[case]
    calcium = "calcium" in target
    fuel = "energy" in target
    opened = "open_" in target
    g = binding.geometry
    cells, baths, patches, contacts = (
        g[key] for key in ("cells", "baths", "membranes", "contacts")
    )
    species = [dict(id=name, valence=z) for name, z in (("Na", 1), ("K", 1), ("Cl", -1), ("Ca", 2))]
    model_id = {
        "resolved_calcium@1": "resolved_tissue@2",
        "resolved_calcium@11": "resolved_tissue@12",
        "resolved_calcium_energy@1": "resolved_tissue@8",
        "resolved_calcium_energy@5": "resolved_tissue@12",
        "resolved_open_calcium@1": "resolved_tissue@12",
        "resolved_open_calcium_energy@1": "resolved_tissue@12",
    }.get(target, target)
    ionic = dict(
        id=model_id,
        temperature_K=298.15,
        species=species,
        cells=[],
        extracellular=[],
        membranes=[],
        junctions=[],
        faces=[],
        channels=[],
        closure=dict(
            law="resolved_capacitor_components_current_continuity@1",
            gauge_reference=None if opened and case != "open-calcium-empty" else baths[0]["id"],
        ),
    )
    experiment = dict(
        end_time=1e-6,
        observation_times=[0.0, 5e-7, 1e-6],
        membrane_controls=[],
        junction_controls=[],
        channel_controls=[],
        pump_controls=[],
    )
    geometric_targets = independent.polygon.evaluate(declaration)
    volumes = {row["id"]: row for row in geometric_targets["cells"]}
    edge_targets = {tuple(row["vertex_ids"]): row for row in geometric_targets["edges"]}
    total = {
        name: independent.multiply(row["exact_ratios"]["volume_m3"], independent.ratio(1e15))
        for name, row in volumes.items()
    }
    partition = 0.25
    cy_volume = {
        name: independent.rounded(
            independent.multiply(value, independent.ratio(1 - partition)) if calcium else value
        )
        for name, value in total.items()
    }
    desired_phi = {row["id"]: -0.035 - 0.02 * i for i, row in enumerate(cells)}
    bath_phi = {
        row["id"]: (-0.001 if i == 0 and opened and case != "open-calcium-empty" else 0.0)
        for i, row in enumerate(baths)
    }
    charge = dict.fromkeys([row["id"] for row in cells + baths], 0.0)
    edges = {row["id"]: row for row in g["edges"]}
    for i, patch in enumerate(patches):
        name, owner = patch["id"], patch["cell_id"]
        c = 0.01 * (1 + 0.03 * i)
        # The caller's anchors use independently derived area targets and the
        # exact product of its binary64 specific-capacitance declaration.
        squared_area = edge_targets[tuple(edges[patch["edge_id"]]["vertex_ids"])][
            "squared_targets"
        ]["area_m2"]
        cap_squared = independent.multiply(
            squared_area, independent.multiply(independent.ratio(c), independent.ratio(c))
        )
        cap = independent.rounded(cap_squared, radical=True)
        q = cap * (desired_phi[owner] - bath_phi[patch["bath_id"]])
        charge[owner] += q
        charge[patch["bath_id"]] -= q
        metabolism = (
            dict(kind="finite_energy_pool@1", pool_id="fuel_" + owner)
            if fuel
            else dict(
                kind="maintained_chemical_reservoirs@1",
                atp_mM=1.5,
                adp_mM=0.1,
                pi_mM=0.1,
                delta_g0_J_per_mol=-37000.0,
            )
        )
        pump = dict(
            id="pump_" + str(i),
            law="nak_atp_mass_action_positive@1",
            roles=dict(sodium="Na", potassium="K"),
            stoichiometry=dict(Na=-3, K=2),
            capacity_fmol_per_s=0.002 + 0.0001 * i,
            km_na_mM=12.0,
            km_k_mM=0.2,
            km_atp_mM=0.5,
            metabolism=metabolism,
        )
        diffusivities = {
            s["id"]: g["thickness_m"] * p * (1 + 0.05 * i)
            for s, p in zip(species, (1e-9, 2e-9, 8e-10, 1e-10), strict=True)
        }
        ionic["membranes"].append(
            dict(
                id=name,
                inside=owner,
                outside=patch["bath_id"],
                area_m2=ref("membrane_area_m2", membrane_id=name),
                capacitance_F=ref(
                    "membrane_capacitance_F", membrane_id=name, specific_capacitance_F_per_m2=c
                ),
                permeability_m_per_s={
                    s: ref(
                        "membrane_permeability_m_per_s", membrane_id=name, diffusivity_m2_per_s=d
                    )
                    for s, d in diffusivities.items()
                },
                law="constant_field@1",
                pump=pump,
            )
        )
        channel = dict(
            id="channel_" + str(i),
            membrane_id=name,
            kinetic_law="betse_kv1p5_mh@1",
            max_permeability_m_per_s=ref(
                "membrane_permeability_m_per_s",
                membrane_id=name,
                diffusivity_m2_per_s=g["thickness_m"] * 3e-10,
            ),
            abundance=0.5 + 0.02 * i,
            initial_gate=[0.2 + 0.01 * i, 0.7],
        )
        if model_id == "resolved_tissue@2":
            channel["species_id"] = "K"
        else:
            channel["permeant_ions"] = [dict(species_id="K", relative_permeability=1.0)]
        ionic["channels"].append(channel)
        for family, name_id in (
            ("membrane", name),
            ("pump", pump["id"]),
            ("channel", channel["id"]),
        ):
            experiment[family + "_controls"].append(_change(family, name_id))
        extra_laws = []
        if model_id == "resolved_tissue@12":
            extra_laws.append(
                (
                    "betse_hcn_leak_open@1",
                    [],
                    [("Na", 0.33), ("K", 1.0), ("Ca", 0.05)],
                )
            )
        if model_id == "resolved_tissue@12" or target == "resolved_energy@2":
            extra_laws.append(("betse_kv_ml1_dynamic_m@1", [0.2], [("K", 1.0)]))
        for law, gates, ions in extra_laws:
            population = dict(
                id="population_" + str(len(ionic["channels"])),
                membrane_id=name,
                kinetic_law=law,
                max_permeability_m_per_s=ref(
                    "membrane_permeability_m_per_s",
                    membrane_id=name,
                    diffusivity_m2_per_s=g["thickness_m"] * 2e-10,
                ),
                abundance=0.4,
                initial_gate=gates,
                permeant_ions=[
                    dict(species_id=ion, relative_permeability=weight) for ion, weight in ions
                ],
            )
            ionic["channels"].append(population)
            experiment["channel_controls"].append(_change("channel", population["id"]))
    contact_rows = []
    for i, contact in enumerate(contacts):
        name = contact["id"]
        path_length = 2.5e-8 * (1 + 0.1 * i)
        contact_rows.append(
            dict(contact_id=name, membrane_ids=contact["membrane_ids"], path_length_m=path_length)
        )
        ionic["junctions"].append(
            dict(
                id=name,
                sender=contact["sender"],
                receiver=contact["receiver"],
                area_m2=ref("contact_area_m2", contact_id=name),
                permeability_m_per_s={
                    s["id"]: ref(
                        "contact_permeability_m_per_s",
                        contact_id=name,
                        diffusivity_m2_per_s=path_length * 2e-10,
                    )
                    for s in species
                },
                law="constant_field@1",
                gate=dict(
                    law="betse_rate_junction_relaxation@1",
                    threshold_voltage_V=0.015,
                    minimum_open_fraction=0.1,
                    initial_gate=0.6,
                ),
            )
        )
        experiment["junction_controls"].append(_change("junction", name, 0.7))
    charge_per_fmol = 6.02214076e23 * 1.602176634e-19 * 1e-15
    for kind, rows in (("cells", cells), ("extracellular", baths)):
        for i, row in enumerate(rows):
            name = row["id"]
            volume = (
                cy_volume[name]
                if kind == "cells"
                else independent.rounded(
                    independent.multiply(
                        independent.ratio(row["volume_m3"]), independent.ratio(1e15)
                    )
                )
            )
            concentrations = (
                (12.0 + i, 140.0 - 5 * i, 10.0 + i, 0.002 + 0.0001 * i)
                if kind == "cells"
                else (145.0, 4.0, 120.0, 0.02)
            )
            amounts = {s["id"]: volume * c for s, c in zip(species, concentrations, strict=True)}
            part = dict(
                id=name,
                volume_pL=ref(
                    "cell_volume_pL", cell_id=name, role="cytosol" if calcium else "total"
                )
                if kind == "cells"
                else ref("bath_volume_pL", bath_id=name),
                initial_amount_fmol=amounts,
                fixed_charge_equivalent_fmol=charge[name] / charge_per_fmol
                - math.fsum(s["valence"] * amounts[s["id"]] for s in species),
                initial_charge_C=charge[name],
            )
            if kind == "extracellular":
                part.update(
                    reservoir=opened
                    and case != "open-calcium-empty"
                    and (i == 0 or case == "open-fuel-all-held"),
                    boundary_potential_V=bath_phi[name],
                )
            ionic[kind].append(part)
    execution = dict(
        dt=6.25e-8,
        capacity=len(cells) + 1,
        extracellular_capacity=len(baths) + 1,
        membrane_capacity=len(patches) + 1,
        edge_capacity=len(contacts) + 1,
        face_capacity=1,
        channel_capacity=len(ionic["channels"]) + 1,
        backend="cpu",
        jit=False,
        precision="float64",
        solver="rk4",
        field_solver="capacitive_reduction_gauged_damped_newton@1",
        max_steps=256,
        max_trace_bytes=2**26,
        material_balance_atol_fmol={s["id"]: 2e-11 for s in species},
    )
    model, er_rows, partitions = ionic, [], []
    if calcium:
        declared = json.loads(
            (Path(__file__).resolve().parents[2] / "configs/ip3_calcium_cluster.json").read_text()
        )
        source = declared["model"]
        model = dict(
            id=target,
            ionic=ionic,
            stores=[],
            plasma_transport=dict(calcium_species="Ca", sodium_species="Na", membranes=[]),
            calcium_channels=[],
            ip3_release=[],
        )
        experiment.update(store_controls=[], plasma_controls=[], calcium_channel_controls=[])
        for i, cell in enumerate(ionic["cells"]):
            name = cell["id"]
            store = deepcopy(source["stores"][0]["model"])
            er_rows.append(
                dict(
                    cell_id=name,
                    membrane_id=store["membrane"]["id"],
                    cytosol_compartment_id="cytosol",
                    ER_compartment_id="er",
                    area_m2=2e-11 * (1 + 0.1 * i),
                    thickness_m=6e-9,
                )
            )
            partitions.append(dict(cell_id=name, ER_fraction=partition))
            for part in store["compartments"]:
                role = "cytosol" if part["id"] == "cytosol" else "ER"
                volume = (
                    cy_volume[name]
                    if role == "cytosol"
                    else independent.rounded(
                        independent.multiply(total[name], independent.ratio(partition))
                    )
                )
                source_volume = part["volume_pL"]
                concentrations = {
                    s: a / source_volume for s, a in part["initial_amount_fmol"].items()
                }
                part["initial_amount_fmol"] = {s: c * volume for s, c in concentrations.items()}
                if role == "cytosol":
                    part["initial_amount_fmol"].update(cell["initial_amount_fmol"])
                part["volume_pL"] = ref("cell_volume_pL", cell_id=name, role=role)
            membrane = store["membrane"]
            membrane["area_m2"] = ref("ER_area_m2", cell_id=name, membrane_id=membrane["id"])
            membrane["initial_voltage_V"] = 0.001 * (i + 1)
            membrane["permeability_m_per_s"] = {
                s: ref(
                    "ER_permeability_m_per_s",
                    cell_id=name,
                    membrane_id=membrane["id"],
                    diffusivity_m2_per_s=p * 6e-9,
                )
                for s, p in membrane["permeability_m_per_s"].items()
            }
            membrane["release"]["permeability_m_per_s"] = ref(
                "ER_permeability_m_per_s",
                cell_id=name,
                membrane_id=membrane["id"],
                diffusivity_m2_per_s=1e-7 * 6e-9,
            )
            model["stores"].append(dict(cell_id=name, model=store))
            model["ip3_release"].append(deepcopy(source["ip3_release"][0]) | dict(cell_id=name))
            control = deepcopy(declared["experiment"]["store_controls"][0])
            control["cell_id"] = name
            experiment["store_controls"].append(control)
        for i, patch in enumerate(patches):
            name = patch["id"]
            model["plasma_transport"]["membranes"].append(
                deepcopy(source["plasma_transport"]["membranes"][0]) | dict(membrane_id=name)
            )
            ch = deepcopy(source["calcium_channels"][0]) | dict(
                id="calcium_channel_" + str(i), membrane_id=name
            )
            ch["max_permeability_m_per_s"] = ref(
                "membrane_permeability_m_per_s",
                membrane_id=name,
                diffusivity_m2_per_s=2e-8 * g["thickness_m"],
            )
            model["calcium_channels"].append(ch)
            experiment["plasma_controls"].append(
                dict(
                    membrane_id=name,
                    schedule=[
                        dict(time=0.0, pump=0.8, exchanger=0.7),
                        dict(time=5e-7, pump=0.5, exchanger=0.9),
                    ],
                )
            )
            experiment["calcium_channel_controls"].append(_change("channel", ch["id"], 0.9))
        execution.update(chemical_capacity=3, reaction_capacity=6)
    if fuel:
        model["energy_pools"], model["regeneration_ports"] = [], []
        experiment["regeneration_controls"] = []
        for i, cell in enumerate(ionic["cells"]):
            name = cell["id"]
            volume = cy_volume[name]
            levels = (0.8, 0.8, 0.8) if case == "fuel-calcium-depleted" else (1.5, 0.1, 0.1)
            model["energy_pools"].append(
                dict(
                    id="fuel_" + name,
                    cell_id=name,
                    law="finite_atp_adp_pi_transformed@1",
                    initial_amount_fmol=dict(
                        zip(("ATP", "ADP", "Pi"), (volume * c for c in levels), strict=True)
                    ),
                    delta_g0_J_per_mol=-37000.0,
                )
            )
            model["regeneration_ports"].append(
                dict(
                    id="supply_" + name,
                    pool_id="fuel_" + name,
                    law="driven_atp_regeneration_tanh@1",
                    capacity_fmol_per_s=0.001 + 0.0001 * i,
                    supplied_energy_J_per_mol=85000.0,
                )
            )
            experiment["regeneration_controls"].append(
                _change("regeneration", "supply_" + name, 0.8)
            )
        if calcium:
            owners = {patch["id"]: patch["cell_id"] for patch in patches}
            for kind, rows in (
                ("pmca", model["plasma_transport"]["membranes"]),
                ("er", model["stores"]),
            ):
                for row in rows:
                    owner = owners[row["membrane_id"]] if kind == "pmca" else row["cell_id"]
                    membrane = row if kind == "pmca" else row["model"]["membrane"]
                    pump = membrane["pump"]
                    membrane["pump"] = {
                        k: pump[k] for k in ("capacity_fmol_per_s", "km_ca_mM", "km_atp_mM")
                    } | dict(
                        law="finite_atp_pmca_betse_positive@1"
                        if kind == "pmca"
                        else "finite_atp_er_1ca_betse_positive@1",
                        metabolism=dict(kind="finite_energy_pool@1", pool_id="fuel_" + owner),
                    )
        execution["regeneration_capacity"] = len(cells) + 1
    if opened:
        has_held = any(row["reservoir"] for row in ionic["extracellular"])
        ceilings = {s["id"]: 0.0 for s in species}
        for row in ionic["extracellular"]:
            for s in ceilings:
                ceilings[s] += row["initial_amount_fmol"][s]
        for row in model["stores"]:
            for compartment in row["model"]["compartments"]:
                for chemical in row["model"]["species"]:
                    for s in ceilings:
                        ceilings[s] += (
                            chemical["moieties"][s]
                            * compartment["initial_amount_fmol"][chemical["id"]]
                        )
        model.update(
            exterior_policy="static_declared_ideal_chemical_and_voltage_reservoirs@1",
            ionic_moiety_domain_policy="hard_global_ionic_moiety_ceilings_fmol_every_stage@1",
            ionic_moiety_ceiling_fmol={s: 1.5 * v for s, v in ceilings.items()}
            if has_held
            else None,
        )
    template = dict(schema_version=1, model=model, experiment=experiment, execution=execution)
    if case == "full-nonuniform-reordered":
        for key in ("cells", "extracellular", "membranes", "junctions", "channels"):
            ionic[key].reverse()
        for key in ("membrane_controls", "junction_controls", "channel_controls", "pump_controls"):
            experiment[key].reverse()
    return dict(
        kind=REQUEST_KIND,
        opted_in_law=LAW_ID,
        geometry_identity=binding.identity,
        target_model_id=target,
        definition_template=template,
        volume_policy="polygon_total_partitioned_cytosol_ER@1"
        if calcium
        else "polygon_total_ionic_volume@1",
        cell_partitions=partitions,
        ER_geometry=er_rows,
        contact_geometry=contact_rows,
        provenance=dict(
            case=case,
            declared_source="complete synthetic caller definition; not a measured tissue",
            inventories=(
                "Explicit amounts constructed for the declared partition before preparation"
            ),
            initial_charge_recipe=(
                "sum(C_patch*(declared_cell_phi-declared_bath_phi)); explicit free-ion fixed charge"
            ),
            declared_cell_potential_V=desired_phi,
            declared_bath_potential_V=bath_phi,
            coefficients=(
                "Manufactured per-patch nonuniform specific capacitance, diffusivity, "
                "pump capacity and channel gates"
            ),
            internal_ER_geometry=(
                "Independent explicit internal area and thickness; "
                "caller declarations separate from plasma polygon edges"
            ),
            control_scope=(
                "Initial state at time zero and unchanged-state control probes; no stepping"
            ),
        ),
    )


def invalid(case, declaration, binding):
    family = "fuel-calcium-full"
    if case in ("missing-open-policy", "open-ceiling-below-true-moiety"):
        family = "open-fuel-mixed"
    if case == "empty-open-nonnull-ceiling":
        family = "open-calcium-empty"
    if case == "closed-calcium-held-bath":
        family = "calcium-basic"
    if case == "closed-fuel-held-bath":
        family = "fuel-ionic"
    value = request(family, declaration, binding)
    model = value["definition_template"]["model"]
    ion = model.get("ionic", model)
    experiment = value["definition_template"]["experiment"]
    if case == "unsupported-water-family":
        value["target_model_id"] = "resolved_calcium_energy_water@1"
    elif case == "passive-relabel":
        model["id"] = "resolved_tissue@1"
    elif case == "wrong-nested-family":
        ion["id"] = "resolved_tissue@2"
    elif case == "wrong-law":
        value["opted_in_law"] = "passive"
    elif case == "wrong-geometry-id":
        value["geometry_identity"] = "0" * 64
    elif case == "missing-provenance":
        value["provenance"] = {}
    elif case == "non298-temperature":
        ion["temperature_K"] = 310.0
    elif case == "exterior-spatial-face":
        ion["faces"] = [dict(id="unsupported")]
    elif case == "missing-cell":
        ion["cells"].pop()
    elif case == "wrong-patch-cell":
        ion["membranes"][0]["inside"] = ion["cells"][1]["id"]
    elif case == "wrong-patch-bath":
        ion["membranes"][0]["outside"] = "unowned"
    elif case == "wrong-reference-owner":
        ion["membranes"][0]["area_m2"]["membrane_id"] = ion["membranes"][1]["id"]
    elif case == "numeric-volume-override":
        ion["cells"][0]["volume_pL"] = 1.0
    elif case == "numeric-area-override":
        ion["membranes"][0]["area_m2"] = 1e-10
    elif case == "numeric-capacitance-override":
        ion["membranes"][0]["capacitance_F"] = 1e-12
    elif case == "numeric-channel-permeability":
        ion["channels"][0]["max_permeability_m_per_s"] = 1e-9
    elif case == "reference-in-inventory":
        ion["cells"][0]["initial_amount_fmol"]["Na"] = deepcopy(ion["cells"][0]["volume_pL"])
    elif case == "reference-in-control":
        experiment["membrane_controls"][0]["schedule"][0]["availability"] = deepcopy(
            ion["cells"][0]["volume_pL"]
        )
    elif case == "negative-diffusivity":
        ion["membranes"][0]["permeability_m_per_s"]["Na"]["diffusivity_m2_per_s"] = -1e-20
    elif case == "zero-specific-capacitance":
        ion["membranes"][0]["capacitance_F"]["specific_capacitance_F_per_m2"] = 0.0
    elif case == "missing-junction":
        ion["junctions"].pop()
    elif case == "reversed-junction":
        row = ion["junctions"][0]
        row["sender"], row["receiver"] = row["receiver"], row["sender"]
    elif case == "wrong-reciprocal-membranes":
        value["contact_geometry"][0]["membrane_ids"].reverse()
    elif case == "zero-junction-path":
        value["contact_geometry"][0]["path_length_m"] = 0.0
    elif case == "centroid-junction-path-policy":
        value["contact_geometry"][0]["policy"] = "centroid_distance"
    elif case == "missing-ER-partition":
        value["cell_partitions"].pop()
    elif case == "zero-ER-fraction":
        value["cell_partitions"][0]["ER_fraction"] = 0.0
    elif case == "unit-ER-fraction":
        value["cell_partitions"][0]["ER_fraction"] = 1.0
    elif case == "unknown-ER-volume-policy":
        value["volume_policy"] = "ER_extra_volume"
    elif case == "missing-ER-geometry":
        value["ER_geometry"].pop()
    elif case == "zero-ER-thickness":
        value["ER_geometry"][0]["thickness_m"] = 0.0
    elif case == "wrong-ER-compartment-role":
        value["ER_geometry"][0]["cytosol_compartment_id"] = "er"
    elif case == "wrong-free-ion-amount":
        model["stores"][0]["model"]["compartments"][0]["initial_amount_fmol"]["Na"] *= 1.01
    elif case == "missing-calcium-route":
        model["plasma_transport"]["membranes"].pop()
    elif case == "wrong-Cav-owner":
        model["calcium_channels"][0]["membrane_id"] = "wrong-owner"
    elif case == "missing-IP3-binding":
        model["ip3_release"].pop()
    elif case == "missing-fuel-pool":
        model["energy_pools"].pop()
    elif case in ("cross-cell-NaK-fuel", "cross-cell-PMCA-fuel", "cross-cell-ER-fuel"):
        pump = (
            ion["membranes"][0]["pump"]
            if case == "cross-cell-NaK-fuel"
            else model["plasma_transport"]["membranes"][0]["pump"]
            if case == "cross-cell-PMCA-fuel"
            else model["stores"][0]["model"]["membrane"]["pump"]
        )
        pump["metabolism"]["pool_id"] = model["energy_pools"][1]["id"]
    elif case == "unknown-regeneration-pool":
        model["regeneration_ports"][0]["pool_id"] = "unknown"
    elif case == "maintained-pump-in-fuel-family":
        ion["membranes"][0]["pump"]["metabolism"] = dict(
            kind="maintained_chemical_reservoirs@1",
            atp_mM=1.5,
            adp_mM=0.1,
            pi_mM=0.1,
            delta_g0_J_per_mol=-37000.0,
        )
    elif case in ("closed-calcium-held-bath", "closed-fuel-held-bath"):
        ion["extracellular"][0]["reservoir"] = True
    elif case == "missing-open-policy":
        model.pop("exterior_policy")
    elif case == "open-ceiling-below-true-moiety":
        model["ionic_moiety_ceiling_fmol"]["Ca"] = 1e-15
    elif case == "empty-open-nonnull-ceiling":
        model["ionic_moiety_ceiling_fmol"] = {s["id"]: 1000.0 for s in ion["species"]}
    elif case == "missing-control":
        experiment["pump_controls"].pop()
    elif case == "unordered-control-clock":
        experiment["pump_controls"][0]["schedule"][1]["time"] = 0.0
    elif case == "existing-charge-closure-refusal":
        ion["cells"][0]["initial_charge_C"] += 1e-12
    else:
        raise ValueError(case)
    return value
