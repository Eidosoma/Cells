"""Static profile preparation for explicitly mapped resolved compositions.

The qualified direct bridge stays unchanged. Its passive parameter view owns
unit conversion and stable target selection only; it is never the composed
field/flux/state. Only selected permeability entries return to the complete
parent, which retains every other property and is validated again.
"""

import json
from bisect import bisect_right
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cells.core import surface_kinetic_spec
from cells.core import tissue_profile_preparation as direct
from cells.core.specs import ConfigError, digest, parse_spec
from cells.models.registry import get_model

BRIDGE_ID = "resolved_composed_static_profiles@1"
KIND = "cells.resolved_composed_profile_preparation@1"
Geometry = direct.Geometry

# Exact serialized parent-to-physical-schema contracts. Unknown families and
# existing cut epochs require their own provenance, rather than duck typing.
SCHEMAS = {
    **{
        f"resolved_tissue@{i}": dict(family="ionic_channels", path=(), ionic_id=None)
        for i in range(2, 12)
    },
    **{
        f"resolved_calcium@{i}": dict(
            family="calcium_er", path=("ionic",), ionic_id=f"resolved_tissue@{i + 1}"
        )
        for i in range(1, 12)
    },
    **{
        f"resolved_calcium_energy@{i}": dict(
            family="calcium_finite_fuel", path=("ionic",), ionic_id=f"resolved_tissue@{i + 7}"
        )
        for i in range(1, 6)
    },
    "resolved_calcium_energy_transport@1": dict(
        family="configured_transport", path=("ionic",), ionic_id="resolved_tissue@12"
    ),
    "resolved_calcium_energy_mitochondria@1": dict(
        family="mitochondria", path=("ionic",), ionic_id="resolved_tissue@12"
    ),
    "resolved_calcium_water@1": dict(
        family="calcium_water", path=("ionic",), ionic_id="resolved_tissue@11"
    ),
    "resolved_calcium_energy_water@1": dict(
        family="calcium_fuel_water", path=("ionic",), ionic_id="resolved_tissue@11"
    ),
    "resolved_calcium_energy_water@2": dict(
        family="calcium_fuel_water", path=("ionic",), ionic_id="resolved_tissue@12"
    ),
    "resolved_calcium_energy_water_repair@2": dict(
        family="calcium_fuel_water_repair", path=("ionic",), ionic_id="resolved_tissue@12"
    ),
    "resolved_calcium_energy_regulated@1": dict(
        family="regulation_v1", path=("ionic",), ionic_id="resolved_tissue@12"
    ),
    "resolved_calcium_energy_regulated@2": dict(
        family="regulation_v2", path=("ionic",), ionic_id="resolved_tissue@12"
    ),
    **{
        f"resolved_water@{i}": dict(family="compliant_water", path=(), ionic_id=None)
        for i in (1, 2, 3)
    },
    **{f"resolved_energy@{i}": dict(family="finite_fuel", path=(), ionic_id=None) for i in (1, 2)},
    **{
        f"resolved_energy_water@{i}": dict(family="fuel_water", path=(), ionic_id=None)
        for i in (1, 2)
    },
}


@dataclass(frozen=True)
class Preparation:
    definition: dict
    provenance: dict


def _schema(definition):
    if type(definition) is not dict or type(definition.get("model")) is not dict:
        raise ConfigError("Require a complete ordinary resolved composition definition")
    mid = definition["model"].get("id")
    if type(mid) is not str or mid not in SCHEMAS:
        raise ConfigError(
            "Unsupported composition; cut epochs and assembly need a new provenance contract"
        )
    if any(key in definition["model"] for key in ("excision", "epoch_start_time", "tissue")):
        raise ConfigError("Existing cut epochs cannot be silently prepared as ordinary parents")
    schema = SCHEMAS[mid]
    leaf = definition["model"]
    for key in schema["path"]:
        if type(leaf.get(key)) is not dict:
            raise ConfigError("Missing declared nested physical schema")
        leaf = leaf[key]
    if schema["ionic_id"] is not None and leaf.get("id") != schema["ionic_id"]:
        raise ConfigError("Nested ionic identity does not match the explicit parent schema")
    return mid, schema


def _leaf(definition, path):
    result = definition["model"]
    for key in path:
        result = result[key]
    return result


def parameter_view(spec):
    """Qualified geometry projection, with every original clock carried.

    Intrinsic gates, live regulation and added processes remain owned by the
    complete model. No composed physical readout is computed from this view.
    """
    view = surface_kinetic_spec.passive_spec(spec).to_dict()
    clocks = sorted({change.time for change in spec.experiment.changes})
    if not view["experiment"]["membrane_controls"]:
        raise ConfigError("Static parameter projection needs an actual membrane clock carrier")
    carrier = view["experiment"]["membrane_controls"][0]
    schedule = carrier["schedule"]
    times = [row["time"] for row in schedule]
    carrier["schedule"] = [
        dict(time=t, availability=schedule[bisect_right(times, t) - 1]["availability"])
        for t in sorted({*times, *clocks})
    ]
    return view


def _state_identity(state):
    return digest(
        {
            key: dict(
                dtype=str(np.asarray(value).dtype),
                shape=list(np.asarray(value).shape),
                values=np.asarray(value).tolist(),
            )
            for key, value in state._asdict().items()
        }
    )


def owner_inventory(definition, path):
    """Declared physical inventories/volumes and stable ownership, not flux."""
    model = definition["model"]
    leaf = _leaf(definition, path)

    def rows(key, fields):
        return [{field: deepcopy(row[field]) for field in fields} for row in leaf[key]]

    return dict(
        species=deepcopy(leaf["species"]),
        cytosol=rows(
            "cells",
            (
                "id",
                "volume_pL",
                "initial_amount_fmol",
                "initial_charge_C",
                "fixed_charge_equivalent_fmol",
            ),
        ),
        exterior=rows(
            "extracellular",
            (
                "id",
                "volume_pL",
                "initial_amount_fmol",
                "initial_charge_C",
                "fixed_charge_equivalent_fmol",
                "reservoir",
                "boundary_potential_V",
            ),
        ),
        chemical_stores=deepcopy(model.get("stores", [])),
        finite_fuel=deepcopy(model.get("energy_pools", [])),
        mitochondrial_compartments=deepcopy(model.get("mitochondria", {}).get("compartments", [])),
        water_compartments=deepcopy(model.get("water_compartments", [])),
        water_membranes=deepcopy(model.get("water_membranes", [])),
    )


def prepare(definition, geometry, default, profiles, *, ion_enabled, enabled=True, is_ecm=False):
    mid, schema = _schema(definition)
    before = parse_spec(deepcopy(definition))
    source = before.to_dict()
    _schema(source)
    view = parameter_view(before)
    prepared = direct.prepare(
        view, geometry, default, profiles, ion_enabled=ion_enabled, enabled=enabled, is_ecm=is_ecm
    )
    result = deepcopy(source)
    leaf = _leaf(result, schema["path"])
    # Do not copy projected pump/gate/volume fields back into the complete
    # parent. The selected coefficient record is the entire write capability.
    for change in prepared.provenance["changes"]:
        matches = [r for r in leaf[change["domain"] + "s"] if r["id"] == change["id"]]
        if (
            len(matches) != 1
            or matches[0]["permeability_m_per_s"][change["species_id"]] != change["before"]
        ):
            raise ConfigError("Selected static coefficient lost its actual composed owner")
        matches[0]["permeability_m_per_s"][change["species_id"]] = change["after"]
    after = parse_spec(result)
    result = after.to_dict()
    restored = deepcopy(result)
    target = _leaf(restored, schema["path"])
    for change in prepared.provenance["changes"]:
        row = next(r for r in target[change["domain"] + "s"] if r["id"] == change["id"])
        if row["permeability_m_per_s"][change["species_id"]] != change["after"]:
            raise ConfigError("Composed validation changed the selected coefficient")
        row["permeability_m_per_s"][change["species_id"]] = change["before"]
    if restored != source:
        raise ConfigError("Preparation changed a nonselected composed property or control history")
    implementation = get_model(before.model)
    state, p = implementation.initial_values(before)
    final, q = get_model(after.model).initial_values(after)
    if (
        get_model(after.model) is not implementation
        or type(state) is not type(final)
        or any(
            np.asarray(a).dtype != np.asarray(b).dtype or not np.array_equal(a, b)
            for a, b in zip(state, final, strict=True)
        )
    ):
        raise ConfigError(
            "Static composition changed an initial gate, volume, fuel or physical state"
        )
    inventories = owner_inventory(source, schema["path"])
    if owner_inventory(result, schema["path"]) != inventories:
        raise ConfigError("Static composition changed a physical inventory, volume or owner")
    regulation = None
    if schema["family"] in ("regulation_v1", "regulation_v2"):
        a = implementation.regulation_values(state, p, xp=np)
        b = implementation.regulation_values(final, q, xp=np)
        if not np.array_equal(a.rule_factors, b.rule_factors) or not np.array_equal(
            a.samples_mM, b.samples_mM
        ):
            raise ConfigError("Preparation changed initial owned regulation samples or factors")
        regulation = dict(
            rule_factors=np.asarray(a.rule_factors).tolist(),
            samples_mM=np.asarray(a.samples_mM).tolist(),
        )
    provenance = dict(
        kind=KIND,
        bridge_id=BRIDGE_ID,
        parent_model_id=mid,
        schema=direct._json(schema),
        source_definition=source,
        source_definition_sha256=digest(source),
        prepared_definition_sha256=digest(result),
        direct_parameter_preparation=prepared.provenance,
        projection_scope=(
            "Geometry/coefficient view only; never the composed physical field or flux"
        ),
        projected_clock_policy="All source clocks carried on an unchanged-value passive schedule",
        initial_state_fields=list(state._fields),
        initial_state_sha256=_state_identity(state),
        initial_owner_inventory=inventories,
        owner_inventory_sha256=digest(inventories),
        control_history_sha256=digest(source["experiment"]),
        initial_regulation=regulation,
        changes=prepared.provenance["changes"],
        physical_scope=(
            "Full parent validation and state preservation; other processes remain parent-owned"
        ),
        unsupported_scope=(
            "Existing cut epochs, assembly, unknown nested schemas and new intervention laws"
        ),
    )
    provenance = direct._json(provenance)
    provenance["identity"] = digest(provenance)
    return Preparation(result, provenance)


def replay(provenance):
    try:
        record = deepcopy(provenance)
        identity = record.pop("identity")
        if record["kind"] != KIND or identity != digest(record):
            raise ConfigError("Stale composed preparation identity")
        inner = record["direct_parameter_preparation"]
        geometry = deepcopy(inner["geometry"])
        layout = geometry.pop("layout")
        layout["cell_centres_m"] = np.asarray(layout["cell_centres_m"], dtype=float)
        geometry = Geometry(direct.native.Layout(**layout), **geometry)
        rows = inner["profile_declarations"]
        result = prepare(
            record["source_definition"],
            geometry,
            direct._decode_profile(rows["default"]),
            [direct._decode_profile(row) for row in rows["profiles"]],
            ion_enabled=rows["ion_enabled"],
            enabled=rows["enabled"],
            is_ecm=rows["is_ecm"],
        )
        if result.provenance != provenance:
            raise ConfigError("Composed owner/state/control or static recipe changed")
        return result
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid complete composed preparation: " + str(error)) from error


def write_preparation(directory, prepared):
    expected = replay(prepared.provenance)
    if prepared.definition != expected.definition:
        raise ConfigError("Composed definition disagrees with its recipe")
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=False)
    for name, value in (
        ("definition.json", expected.definition),
        ("provenance.json", expected.provenance),
    ):
        (path / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    return path


def read_preparation(directory):
    path = Path(directory)
    result = replay(json.loads((path / "provenance.json").read_text()))
    if json.loads((path / "definition.json").read_text()) != result.definition:
        raise ConfigError("Composed definition changed relative to its owner/state recipe")
    return result
