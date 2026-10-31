"""Deferred literal caller/control declarations; no fixtures are evaluated here."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

LAW = "cells_explicit_seed_partition_passive_initial_physiology_bridge@1"
KIND = "cells.explicit_seed_partition_initial_physiology_declaration@1"


def read(name):
    return json.loads(
        Path(__file__)
        .with_name("stable_seed_partition_physiology_bridge_" + name + ".json")
        .read_text()
    )


def geometry_declaration(case):
    """Reconstruct the exact frozen caller input, without constructing geometry."""
    path = Path(__file__).with_name("stable_seed_explicit_ecm_partition_callers.json")
    data = json.loads(path.read_text())
    row = next(row for row in data["cases"] if row["id"] == case)
    layout = {
        key: [float.fromhex(value) for value in values] for key, values in row["layout_hex"].items()
    }
    nx, ny = len(layout["x_centres_m"]), len(layout["y_centres_m"])
    return dict(
        kind="cells.explicit_cleft_width_cell_bath_partition_declaration@1",
        opted_in_law="cells_explicit_cleft_width_tensor_grid_cell_bath_partition@1",
        source=dict(
            kind="explicit_manufactured_seed_owners@1",
            authority=data["authority"],
            document_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            field="cases[" + case + "].seeds/layout_hex",
            prior_full_domain_cells_reclassified=False,
            native_equivalence=False,
        ),
        domain=dict(
            id="explicit-manufactured-domain-" + case,
            vertices_m=[[float.fromhex(v) for v in point] for point in row["domain_vertices_hex"]],
            authority_field="cases[" + case + "].domain_vertices_hex",
        ),
        layout=layout,
        cell_owners=[
            dict(
                id=seed["id"],
                slot=seed["slot"],
                seed_xy_m=[
                    layout["x_centres_m"][seed["slot"][0]],
                    layout["y_centres_m"][seed["slot"][1]],
                ],
            )
            for seed in row["seeds"]
        ],
        bath_owners=[
            dict(id="caller-bath-" + str(i) + "-" + str(j), slot=[i, j])
            for j in range(2 * ny + 1)
            for i in range(2 * nx + 1)
            if not (i % 2 == j % 2 == 1)
        ],
        height_m=float.fromhex(data["height_m_hex"]),
        membrane_thickness_m=data["membrane_thickness_m"],
        units=dict(coordinates="m", height="m", membrane_path="m", area="m2", volume="m3"),
        membrane_geometry_policy="zero_volume_interface_explicit_path@1",
        face_distance_policy="orthogonal_volume_centroids_shared_face@1",
        boundary_policy="sealed_no_transport@1",
        rounding_policy="all_grid_lines_exact_binary64_declared_widths_exact@1",
        old_cache_policy=dict(
            kind="invalidate_all_prior_geometry_and_operators@1", provided_cached_operators=None
        ),
        scope="new_manufactured_cell_and_bath_geometry_no_native_or_prior_cell_equivalence",
    )


def declaration(case_id, geometry, *, document_sha256):
    """Expand explicit quantified caller values only when a future caller asks."""
    document = read("callers")
    case = next(row for row in document["cases"] if row["id"] == case_id)
    shared = document["shared"]
    species = [row["id"] for row in case["species"]]

    def numeric(mapping):
        return {name: float(mapping[name]) for name in species}

    electrical = shared["electrical_policy"]
    cells = [
        dict(id=name, concentration_mM=numeric(case["cell_concentration_mM"]))
        for name in geometry["cell_ids"]
    ]
    baths = []
    for name in geometry["bath_ids"]:
        # The caller explicitly declares one concentration row for every y slot.
        y_slot = int(name.rsplit("-", 1)[1])
        baths.append(
            dict(
                id=name,
                reservoir=False,
                concentration_mM=numeric(case["bath_concentration_by_slot_y_mM"][y_slot]),
            )
        )
    model = dict(
        kind=KIND,
        opted_in_law=LAW,
        opted_in_family="resolved_tissue@1",
        species=deepcopy(case["species"]),
        temperature_K=float(case["temperature_K"]),
        cells=cells,
        baths=baths,
        membranes=[
            dict(
                id=row["id"],
                cell_id=row["cell_id"],
                bath_id=row["bath_id"],
                specific_capacitance_F_per_m2=float(shared["specific_capacitance_F_per_m2"]),
                permeability_m_per_s=numeric(case["membrane_permeability_m_per_s"]),
                diffusivity_m2_per_s=numeric(case["membrane_diffusivity_m2_per_s"]),
            )
            for row in geometry["membranes"]
        ],
        faces=[
            dict(
                id=row["id"],
                sender=row["sender"],
                receiver=row["receiver"],
                diffusivity_m2_per_s=numeric(case["face_diffusivity_m2_per_s"]),
            )
            for row in geometry["faces"]
        ],
        electrical_policy=dict(
            kind=electrical["kind"],
            closure_law=electrical["closure_law"],
            gauge_reference=electrical["gauge_reference"],
            cells=[
                dict(
                    id=name,
                    initial_charge_C=float(electrical["every_cell_initial_charge_C"]),
                    fixed_charge_equivalent_fmol=float(
                        electrical["every_cell_fixed_charge_equivalent_fmol"]
                    ),
                )
                for name in geometry["cell_ids"]
            ],
            baths=[
                dict(
                    id=name,
                    initial_charge_C=float(electrical["every_bath_initial_charge_C"]),
                    fixed_charge_equivalent_fmol=float(
                        electrical["every_bath_fixed_charge_equivalent_fmol"]
                    ),
                    boundary_potential_V=float(electrical["every_bath_boundary_potential_V"]),
                )
                for name in geometry["bath_ids"]
            ],
        ),
        concentration_policy=shared["concentration_policy"],
        constitutive_policy=shared["constitutive_policy"],
        experiment=dict(
            end_time=float(shared["experiment"]["end_time"]),
            observation_times=[0.0],
            junction_controls=[],
            membrane_controls=[
                dict(
                    membrane_id=row["id"],
                    schedule=[dict(time=0.0, availability=float(shared["availability"]))],
                )
                for row in geometry["membranes"]
            ],
        ),
        execution={
            key: value
            for key, value in shared["execution"].items()
            if key != "material_balance_atol_fmol_each_species"
        },
        prior_state_policy=deepcopy(shared["prior_state_policy"]),
        provenance=dict(
            kind="explicit_manufactured_initial_physiology_caller@1",
            authority=document["authority"],
            case_id=case_id,
            document_sha256=document_sha256,
            geometry_case=case["geometry_case"],
            native_equivalence=False,
            biological_calibration=False,
        ),
    )
    model["execution"].update(case["capacities"])
    model["execution"]["material_balance_atol_fmol"] = {
        name: float(shared["execution"]["material_balance_atol_fmol_each_species"])
        for name in species
    }
    return model


def reseal(preparation):
    """Recompute complete metadata hashes without repairing a corrupted value."""

    def text(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)

    def record(value):
        if type(value) is float:
            return dict(binary64_hex=value.hex())
        if type(value) is dict:
            return {key: record(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [record(item) for item in value]
        return value

    physical = preparation["physical_preparation"]
    definition = json.loads(physical["definition_json"])
    provenance = json.loads(physical["provenance_json"])
    provenance["definition_sha256"] = hashlib.sha256(text(definition).encode()).hexdigest()
    provenance["materialized_definition"] = deepcopy(definition)
    physical["provenance_json"] = text(provenance)
    physical["identity"] = hashlib.sha256(
        text(dict(definition=definition, provenance=provenance)).encode()
    ).hexdigest()
    preparation["identity"] = hashlib.sha256(
        text(
            record(
                [LAW]
                + [
                    preparation[key]
                    for key in (
                        "request_identity",
                        "physical_preparation",
                        "conversions",
                        "initial_snapshot",
                        "provenance",
                    )
                ]
            )
        ).encode()
    ).hexdigest()
    return preparation


def changed_declaration(name, original):
    """Source-authored input controls; exact expectations live in controls.json."""
    value = deepcopy(original)
    ion = value["species"][0]["id"]
    if name == "missing-species":
        value.pop("species")
    elif name == "missing-concentration":
        value["cells"][0]["concentration_mM"].pop(ion)
    elif name == "zero-concentration":
        value["cells"][0]["concentration_mM"][ion] = 0.0
    elif name == "negative-permeability":
        value["membranes"][0]["permeability_m_per_s"][ion] = -1.0
    elif name == "missing-diffusivity":
        value["membranes"][0].pop("diffusivity_m2_per_s")
    elif name == "P-D-disagreement":
        value["membranes"][0]["permeability_m_per_s"][ion] *= 2
    elif name == "missing-capacitance":
        value["membranes"][0].pop("specific_capacitance_F_per_m2")
    elif name == "wrong-membrane-owner":
        value["membranes"][0]["cell_id"] = "unrelated-cell"
    elif name == "wrong-face-owner":
        value["faces"][0]["sender"] = "unrelated-bath"
    elif name == "reservoir-adoption":
        value["baths"][0]["reservoir"] = True
    elif name == "missing-charge-anchor":
        value["electrical_policy"]["cells"][0].pop("initial_charge_C")
    elif name == "incompatible-charge-anchor":
        value["electrical_policy"]["cells"][0]["initial_charge_C"] += 1e-10
    elif name == "missing-gauge":
        value["electrical_policy"].pop("gauge_reference")
    elif name == "old-state-adoption":
        value["prior_state_policy"]["provided_prior_state_or_operators"] = {}
    elif name == "nonzero-observation-time":
        value["experiment"]["observation_times"] = [value["experiment"]["end_time"]]
    elif name == "wrong-caller-document":
        value["provenance"]["document_sha256"] = "0" * 64
    else:
        raise ValueError("Undeclared physical input control")
    return value


def changed_preparation(name, preparation):
    """Future coherent output controls; does not build or evaluate any case."""
    expected = {row["id"] for row in read("controls")["output_controls"]}
    if name not in expected:
        raise ValueError("Undeclared physical output control")
    value = deepcopy(preparation)
    snapshot = value["initial_snapshot"]
    field = snapshot["field"]

    def perturb(array, *, amount=1.0):
        # Byte editing is a declared numeric corruption, not an image operation.
        import struct

        raw = bytearray.fromhex(array["data_hex"])
        if array["dtype"] != "<f8" or len(raw) < 8:
            raise ValueError("Expected nonempty declared little-endian float64 control target")
        number = struct.unpack_from("<d", raw)[0]
        struct.pack_into("<d", raw, 0, number + amount)
        array["data_hex"] = raw.hex()

    if name == "missing-field":
        field.pop("electrode_current_A")
    elif name == "extra-field":
        field["undeclared"] = deepcopy(field["converged"])
    elif name == "extra-potential-axis":
        field["potential_V"]["shape"].append(1)
    elif name == "wrong-array-dtype":
        field["potential_V"]["dtype"] = "<i8"
    elif name == "wrong-potential":
        perturb(field["potential_V"], amount=0.01)
    elif name in {"wrong-membrane-flux", "wrong-face-flux"}:
        perturb(field["rates"][name.split("-")[1] + "_flux_fmol_s"])
    elif name == "wrong-rhs":
        perturb(snapshot["rhs"]["amount_increment"])
    elif name == "missing-state-ledger":
        snapshot["state"].pop("face_transferred")
    elif name == "missing-rhs-ledger":
        snapshot["rhs"].pop("face_transferred")
    elif name == "wrong-node-charge":
        perturb(field["capacitor_node_charge_C"], amount=1e-18)
    elif name == "wrong-component-current":
        perturb(field["component_current_residual_A"], amount=1e-15)
    elif name == "missing-gauge-component":
        array = field["component_current_residual_A"]
        array["shape"][0] -= 1
        array["data_hex"] = array["data_hex"][:-16]
    elif name == "wrong-charge-rate":
        perturb(snapshot["accounting"]["local_charge_rate_residual_A"], amount=1e-15)
    elif name in {
        "wrong-chemical-power",
        "wrong-capacitor-power",
        "wrong-dissipation",
        "wrong-energy-balance",
    }:
        key = {
            "wrong-chemical-power": "chemical_energy_rate_pJ_s",
            "wrong-capacitor-power": "capacitor_energy_rate_pJ_s",
            "wrong-dissipation": "dissipation_pJ_s",
            "wrong-energy-balance": "energy_balance_pJ_s",
        }[name]
        perturb(field[key])
    elif name == "wrong-layout-owner":
        array = snapshot["layout"]["membrane_cell"]
        array["data_hex"] = "ff" * (len(array["data_hex"]) // 2)
    elif name == "wrong-material-inventory":
        perturb(snapshot["layout"]["amount_reference"])
    elif name == "missing-concentration-defect":
        value["conversions"]["concentrations"][0].pop("concentration_defect_mM_exact")
    elif name == "coherent-concentration-defect":
        row = value["conversions"]["concentrations"][0]
        row["concentration_defect_mM_exact"] = dict(numerator="1", denominator="1")
        row["represented_concentration_mM_exact"] = dict(numerator="1", denominator="1")
    elif name in {"changed-temperature", "species-key-loss"}:
        raw = json.loads(value["physical_preparation"]["definition_json"])
        if name == "changed-temperature":
            raw["model"]["temperature_K"] += 1.0
        else:
            raw["model"]["membranes"][0]["permeability_m_per_s"].pop(
                raw["model"]["species"][0]["id"]
            )
        value["physical_preparation"]["definition_json"] = json.dumps(
            raw, sort_keys=True, separators=(",", ":")
        )
    elif name == "native-promotion":
        value["provenance"]["native_equivalence"] = True
    elif name == "advancing-promotion":
        snapshot["time_advanced"] = True
    else:
        raise AssertionError("Complete output-control branch roster required")
    return reseal(value)
