"""Independent exact byte/owner/projection/cache checks; no numeric solver."""

import argparse
import copy
import hashlib
import json
import math
import os
import struct
import sys
import traceback
from pathlib import Path

from validation.betse import betse_native_membrane_layout_reference as layout_reference

LAW = "betse_native_membrane_explicit_component_initialization_v1_5_0@1"
INITIAL_LAW = "betse_normal_ecm_prebootstrap_owner_admission_v1_5_0@1"
REVISION = "5269a714aa2593ed2a6708c4516289977d8ae1a2"
CONVERSION = "cells.native_six_to_midpoint_normal_xy@1"
GATES = dict.fromkeys(
    (
        "physical_geometry_admitted",
        "tangent_geometry_qualified",
        "native_seed_init_chain_established",
        "native_layout_qualification_inherited",
        "ordinary_ECM_loop_ready",
        "mechanics_admitted",
    ),
    False,
)


def decode_python_floats(value):
    """Decode only the exact archive Python-float tag; retain NumPy tags."""
    if type(value) is list:
        return [decode_python_floats(child) for child in value]
    if type(value) is dict:
        if "float64_bits" in value:
            raw = value["float64_bits"]
            if (
                set(value) != {"float64_bits"}
                or type(raw) is not str
                or len(raw) != 16
                or any(character not in "0123456789abcdef" for character in raw)
            ):
                raise ValueError("Malformed archived Python binary64 scalar")
            return struct.unpack("<d", bytes.fromhex(raw))[0]
        return {key: decode_python_floats(child) for key, child in value.items()}
    return value


def seal_value(value, *, legacy=False):
    if isinstance(value, list):
        return [seal_value(child, legacy=legacy) for child in value]
    if isinstance(value, dict):
        if legacy and set(value) == {"numpy_scalar_dtype", "raw_bytes_hex"}:
            forms = {"<f8": "<d", ">f8": ">d"}
            if value["numpy_scalar_dtype"] not in forms:
                raise ValueError("Unsupported legacy JSON scalar; do not invent a serializer")
            return struct.unpack(
                forms[value["numpy_scalar_dtype"]], bytes.fromhex(value["raw_bytes_hex"])
            )[0]
        if value.get("__ndarray__") is True:
            return dict(
                dtype=value["dtype"],
                shape=value["shape"],
                sha256=hashlib.sha256(bytes.fromhex(value["raw_bytes_hex"])).hexdigest(),
            )
        if set(value) == {"__indexed_items__"}:
            return {
                seal_value(key, legacy=legacy): seal_value(child, legacy=legacy)
                for key, child in value["__indexed_items__"]
            }
        return {key: seal_value(child, legacy=legacy) for key, child in value.items()}
    if type(value) is float:
        return dict(float64_bits=struct.pack("<d", value).hex())
    return value


def digest(value, *, legacy=False):
    return hashlib.sha256(
        json.dumps(
            seal_value(value, legacy=legacy), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def array(value):
    if (
        value.get("__ndarray__") is not True
        or "object_values" in value
        or set(value) != {"__ndarray__", "dtype", "shape", "strides", "raw_bytes_hex"}
    ):
        raise ValueError("Require complete numeric typed-array sidecars")
    raw = bytes.fromhex(value["raw_bytes_hex"])
    formats = {
        "<f8": "<d",
        ">f8": ">d",
        "<i8": "<q",
        ">i8": ">q",
        "<i4": "<i",
        ">i4": ">i",
        "<u8": "<Q",
        ">u8": ">Q",
        "<u4": "<I",
        ">u4": ">I",
        "|b1": "?",
    }
    if value["dtype"] not in formats:
        raise ValueError("Unsupported independent numeric owner dtype")
    form = formats[value["dtype"]]
    if len(raw) != math.prod(value["shape"]) * struct.calcsize(form):
        raise ValueError("Incomplete typed owner payload")
    return [row[0] for row in struct.iter_unpack(form, raw)], raw


def required(boundary, group, key):
    entry = boundary["owners"][group][key]
    if entry.get("present") is not True or entry.get("captured") is not True:
        raise ValueError("Missing actual source owner: " + group + "." + key)
    return entry["value"]


def cache_checks(boundary):
    cache_entry = boundary["network_cache"]
    if cache_entry.get("present") is not True or cache_entry.get("captured") is not True:
        raise ValueError("Missing complete hot cache observation")
    cached = cache_entry["value"]
    if cached["kind"] != "cells.ecm_grn_owner_cache@1":
        raise ValueError("Wrong source owner-cache kind")
    wire = cached["wire"]
    if set(wire) != {
        "owner_fields",
        "core_fields",
        "molecule_fields",
        "reaction_fields",
        "modulator_fields",
        "ion_boundary_state",
        "simulator_fields",
    }:
        raise ValueError("Incomplete native serializer wire")
    if set(wire["molecule_fields"]) != {"X", "Y"}:
        raise ValueError("Incomplete bounded molecular owner axis")
    cells = required(boundary, "cells", "cell_i")
    membranes = required(boundary, "cells", "mem_i")
    n = len(cells) if isinstance(cells, list) else cells["shape"][0]
    m = len(membranes) if isinstance(membranes, list) else membranes["shape"][0]
    e = required(boundary, "cells", "xypts")["shape"][0]
    for values in wire["molecule_fields"].values():
        for name, count in (("c_cells", n), ("cc_at_mem", m), ("c_env", e)):
            actual, _ = array(values[name])
            if values[name]["shape"] != [count] or values[name]["dtype"] not in ("<f8", ">f8"):
                raise ValueError("Changed source molecular schema/owner axis")
            if any(not math.isfinite(v) or v < 0 for v in actual):
                raise ValueError("Invalid source molecular domain")
    expected_publications = {
        "extra_rho_cells",
        "extra_rho_env",
        "extra_J_mem",
        "extra_Jenv_x",
        "extra_Jenv_y",
    }
    if set(wire["simulator_fields"]) != expected_publications:
        raise ValueError("Missing hot source publication stores")
    for name, value in wire["simulator_fields"].items():
        if value != required(boundary, "sim", name):
            raise ValueError("Hot source publication epoch differs")
    if wire["ion_boundary_state"] != required(boundary, "sim", "c_env_bound"):
        raise ValueError("Hot ionic boundary epoch differs")
    if set(cached["coefficient_fields"]) != {"D_env_weight", "D_env_weight_base", "TJ_targets"}:
        raise ValueError("Missing complete source coefficient stores")
    for name, value in cached["coefficient_fields"].items():
        if value != required(boundary, "sim", name):
            raise ValueError("Hot coefficient owner differs")
    return cached


def common_state_identity(binding, boundary):
    """Repack existing stores only; no geometry, field or material evolution."""
    endian = "<" if sys.byteorder == "little" else ">"

    def canonical(value):
        values, _ = array(value)
        if value["dtype"] not in ("<f8", ">f8"):
            raise ValueError("Common material stores must retain binary64 dtype")
        raw = b"".join(struct.pack(endian + "d", number) for number in values)
        return dict(
            __ndarray__=True,
            dtype=endian + "f8",
            shape=value["shape"],
            strides=[],
            raw_bytes_hex=raw.hex(),
        )

    pairs = (
        ("cell_mol_m3", "cc_cells"),
        ("membrane_mol_m3", "cc_at_mem"),
        ("environment_mol_m3", "cc_env"),
        ("voltage_V", "vm"),
        ("membrane_flux_mol_m2_s", "fluxes_mem"),
        ("junction_flux_mol_m2_s", "fluxes_gj"),
        ("environment_flux_x_mol_m2_s", "fluxes_env_x"),
        ("environment_flux_y_mol_m2_s", "fluxes_env_y"),
        ("junction_voltage_V", "vgj"),
        ("junction_field_source", "Egj"),
        ("gap_open", "gjopen"),
    )
    values = {key: canonical(required(boundary, "sim", field)) for key, field in pairs}
    x, y = (canonical(required(boundary, "sim", field)) for field in ("E_gj_x", "E_gj_y"))
    if x["shape"] != y["shape"] or len(x["shape"]) != 1:
        raise ValueError("Incomplete junction-vector component axes")
    a, b = bytes.fromhex(x["raw_bytes_hex"]), bytes.fromhex(y["raw_bytes_hex"])
    xy = b"".join(a[i : i + 8] + b[i : i + 8] for i in range(0, len(a), 8))
    values["junction_field_xy_source"] = dict(
        __ndarray__=True,
        dtype=endian + "f8",
        shape=[x["shape"][0], 2],
        strides=[],
        raw_bytes_hex=xy.hex(),
    )
    return digest(
        dict(binding_identity=binding["material_binding"]["identity"], step_index=0, values=values),
        legacy=True,
    )


def verify(payload):
    rows = []

    def require(condition, label):
        rows.append(dict(label=label, passed=bool(condition)))
        if not condition:
            raise ValueError("Independent membrane entry refusal: " + label)

    try:
        payload = decode_python_floats(payload)
        original, request, entry = payload["original"], payload["request"], payload["entry"]
        native, snapshot = original["boundary"], original["native_layout"]
        require(
            request["original"] == original and entry["request"] == request,
            "full_original_pair_retained",
        )
        require(
            original["identity"] == digest([LAW, native, snapshot, original["observation"]]),
            "original_pair_seal",
        )
        require(
            native["identity"]
            == digest(
                [
                    INITIAL_LAW,
                    REVISION,
                    native["declaration"],
                    native["observation_kind"],
                    native["owners"],
                    native["network_cache"],
                    native["excluded_owner_state"],
                    native["source_objects"],
                ],
                legacy=True,
            ),
            "original_native_boundary_seal",
        )
        report = layout_reference.verify(
            snapshot, request["six_column_layout"], [request["explicit_view"]]
        )
        require(report["passed"], "independent_six_column_layout_owner_and_projection_check")
        view, projected = request["explicit_view"], request["projected_boundary"]
        require(
            request["declaration"]
            == dict(
                kind="cells.betse_native_membrane_initialization_declaration@1",
                opted_in_law=LAW,
                conversion_law=CONVERSION,
                component_policy="held_single_component_bootstrap_no_ordinary_loop",
                geometry_policy="retain_unqualified_six_column_parent",
                stage="normal_SIM_after_init_dynamics_clear_storage_before_bootstrap_update_V",
            ),
            "explicit_complete_bridge_declaration",
        )
        require(
            view["conversion_law"] == CONVERSION and view["selected_columns"] == [0, 1, 2, 3],
            "explicit_midpoint_normal_convention",
        )
        for name in ("mem_vects_flat", "mem_mids_flat", "mem_to_cells"):
            actual = required(native, "cells", name)
            retained = snapshot["entries"][name]["value"]
            _, raw = array(actual)
            require(
                actual["dtype"] == retained["dtype"]
                and actual["shape"] == retained["shape"]
                and raw.hex() == retained["raw"]["bytes_hex"],
                "paired_original_store/" + name,
            )
        for name in ("cell_i", "mem_i"):
            actual = required(native, "cells", name)
            retained = snapshot["entries"][name]["value"]
            values = actual if isinstance(actual, list) else array(actual)[0]
            require(values == layout_reference._indices(retained), "paired_original_axis/" + name)
            if retained["kind"] == "array_indices":
                buffer = retained["buffer"]
                require(
                    actual["dtype"] == buffer["dtype"]
                    and actual["shape"] == buffer["shape"]
                    and array(actual)[1].hex() == buffer["raw"]["bytes_hex"],
                    "paired_original_axis_bytes/" + name,
                )
        require(
            original["observation"] in ("paired_supplied", "paired_pinned_native"),
            "paired_observation_kind",
        )
        if original["observation"] == "paired_pinned_native":
            require(
                native["observation_kind"] == "pinned_native_objects_at_declared_boundary"
                and snapshot["observation"] == "pinned_native_Cells_stores",
                "actual_pinned_capture_origins",
            )
        else:
            require(
                native["observation_kind"] == "supplied_owner_boundary"
                and snapshot["observation"] == "supplied_owner_stores",
                "actual_supplied_capture_origins",
            )
        expected_owners = copy.deepcopy(native["owners"])
        buffer = view["values"]
        projected_array = dict(
            __ndarray__=True,
            dtype=buffer["dtype"],
            shape=buffer["shape"],
            strides=[32, 8],
            raw_bytes_hex=buffer["raw"]["bytes_hex"],
        )
        expected_owners["cells"]["mem_vects_flat"] = dict(
            present=True, captured=True, value=projected_array
        )
        require(projected["owners"] == expected_owners, "only_named_membrane_store_projected")
        declaration = dict(
            native["declaration"], geometry_classification="unqualified_native_layout"
        )
        require(
            projected["declaration"] == declaration
            and projected["observation_kind"] == "supplied_owner_boundary",
            "projection_cannot_claim_native_capture",
        )
        require(
            projected["network_cache"] == native["network_cache"]
            and projected["excluded_owner_state"] == native["excluded_owner_state"],
            "hot_cache_and_exclusions_unchanged",
        )
        expected_sources = dict(
            law=LAW,
            original_observation=native["observation_kind"],
            original_source_objects=native["source_objects"],
            original_boundary_identity=native["identity"],
            original_pair_identity=original["identity"],
            native_layout_identity=snapshot["identity"],
            conversion_law=CONVERSION,
            explicit_view_identity=view["identity"],
            replaced_store="cells.mem_vects_flat",
            projected_capture_is_native=False,
        )
        require(projected["source_objects"] == expected_sources, "complete_projection_provenance")
        require(
            projected["identity"]
            == digest(
                [
                    INITIAL_LAW,
                    REVISION,
                    projected["declaration"],
                    projected["observation_kind"],
                    projected["owners"],
                    projected["network_cache"],
                    projected["excluded_owner_state"],
                    projected["source_objects"],
                ],
                legacy=True,
            ),
            "projected_boundary_seal",
        )
        cached = cache_checks(native)
        inventory = {
            group: [
                key
                for key, observation in observations.items()
                if observation.get("present") is not True or observation.get("captured") is not True
            ]
            for group, observations in projected["owners"].items()
        }
        actual_inventory = request["readiness"]["presence_inventory"]
        require(
            set(actual_inventory) == set(inventory)
            and all(
                sorted(actual_inventory[group]) == sorted(names)
                for group, names in inventory.items()
            ),
            "complete_missing_store_inventory_without_owner_axis_reordering",
        )
        controls = {key: required(native, "sim", key) for key in ("gj_block", "NaKATP_block")}
        expected_readiness = dict(
            common_owner_checks_complete=True,
            common_state_identity=common_state_identity(request["binding"], native),
            controls_digest=digest(controls, legacy=True),
            hot_cache_digest=digest(cached, legacy=True),
            presence_inventory=actual_inventory,
            native_cache_defaults_filled=False,
            optional_calcium_admission_pending="calcium" in request["binding"],
            serializer_roundtrip_pending=True,
            component_bootstrap_performed=False,
            tangent_columns_consumed=False,
        )
        require(
            request["readiness"] == expected_readiness,
            "complete_readiness_slots_epochs_and_source_state_checksum",
        )
        request_record = [
            LAW,
            request["binding"],
            original,
            request["declaration"],
            request["six_column_layout"],
            view,
            projected,
            request["readiness"],
            GATES,
        ]
        require(
            request["gates"] == GATES and request["identity"] == digest(request_record),
            "request_seal_and_closed_gates",
        )
        component = entry["component_handoff"]
        require(
            component["boundary_identity"] == projected["identity"]
            and component["binding_identity"] == request["binding"]["identity"],
            "held_component_owner_binding",
        )
        provenance = component["provenance"]
        require(
            provenance["bootstrap_calls"] == 1
            and provenance["cold_owner_calls"] == 0
            and provenance["native_init_dynamics_calls"] == 0
            and provenance["native_seed_init_load_chain_established"] is False
            and provenance["geometry_classification"] == "unqualified_native_layout",
            "held_single_component_scope",
        )
        require(
            component["parent"]["network"]["network_cache"] == cached,
            "hot_cache_retained_after_bootstrap",
        )
        require(
            component["identity"]
            == digest(
                [
                    component["boundary_identity"],
                    component["binding_identity"],
                    component["parent"],
                    component["provenance"],
                ],
                legacy=True,
            ),
            "held_component_receipt_seal",
        )
        expected_entry_provenance = dict(
            law=LAW,
            original_boundary_identity=native["identity"],
            original_native_layout_identity=snapshot["identity"],
            original_pair_identity=original["identity"],
            conversion_law=CONVERSION,
            explicit_view_identity=view["identity"],
            projected_boundary_identity=projected["identity"],
            component_handoff_identity=component["identity"],
            component_bootstrap_calls=1,
            original_hot_cache_digest=digest(cached, legacy=True),
            native_bootstrap_executed=False,
            native_seed_init_chain_established=False,
            full_six_column_parent_retained=True,
            tangent_columns_geometry_qualified=False,
        )
        require(
            entry["gates"] == GATES and entry["provenance"] == expected_entry_provenance,
            "unqualified_component_entry_scope",
        )
        require(
            entry["identity"] == digest([LAW, request, component, entry["provenance"], GATES]),
            "component_entry_seal",
        )
        return dict(
            kind="cells.native_membrane_entry_independent_checks@1",
            passed=True,
            rows=rows,
            layout_check=report,
            numerical_accuracy_credit=False,
            physical_geometry_admitted=False,
            ordinary_ECM_loop_ready=False,
        )
    except Exception as error:
        return dict(
            kind="cells.native_membrane_entry_independent_checks@1",
            passed=False,
            rows=rows,
            reason=str(error),
            traceback=traceback.format_exc(),
            numerical_accuracy_credit=False,
            physical_geometry_admitted=False,
            ordinary_ECM_loop_ready=False,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(json.loads(args.input.read_text()))
    report["original_input_path"] = str(args.input)
    report["runtime_origin"] = dict(
        pid=os.getpid(),
        parent_pid=os.getppid(),
        executable=sys.executable,
        source=str(Path(__file__).resolve()),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        input_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),
    )
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
