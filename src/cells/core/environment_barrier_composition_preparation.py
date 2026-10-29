"""Static extracellular coefficients on explicitly supported complete owners.

The passive adapter supplies only geometry and diffusion coefficients. The
complete parent retains its field, channel, calcium, fuel, water and repair
equations, initial state and accounting references.
"""

import json
from copy import deepcopy
from pathlib import Path

from cells.core import environment_barrier_preparation as direct
from cells.core import tissue_profile_composition_preparation as composition
from cells.core.specs import ConfigError, digest, parse_spec
from cells.models.registry import get_model

BRIDGE_ID = "resolved_composed_static_environment_barriers@1"
REQUEST_KIND = "cells.composed_environment_barrier_preparation_request@1"
KIND = "cells.composed_environment_barrier_preparation@1"
Preparation = direct.Preparation

# Explicit full-catalog schemas; no inference from attributes or subclassing.
SCHEMAS = {
    "resolved_tissue@12": dict(family="ionic_channels", path=(), ionic_id=None),
    **{
        mid: dict(family=family, path=("ionic",), ionic_id="resolved_tissue@12")
        for mid, family in (
            ("resolved_calcium@11", "calcium_er"),
            ("resolved_calcium_energy@5", "calcium_finite_fuel"),
            ("resolved_calcium_energy_water@2", "calcium_fuel_water"),
            ("resolved_calcium_energy_water_repair@2", "calcium_fuel_water_repair"),
        )
    },
}


def _schema(definition):
    if type(definition) is not dict or type(definition.get("model")) is not dict:
        raise ConfigError("Require a complete ordinary resolved composition")
    mid = definition["model"].get("id")
    if type(mid) is not str or mid not in SCHEMAS:
        raise ConfigError(
            "Unsupported barrier owner; scheduled, cut and epoch parents are excluded"
        )
    schema = SCHEMAS[mid]
    leaf = composition._leaf(definition, schema["path"])
    if schema["ionic_id"] is not None and leaf.get("id") != schema["ionic_id"]:
        raise ConfigError("Nested ionic identity disagrees with the declared barrier owner")
    return mid, schema


def prepare(request):
    """Change only face diffusivities, then validate the complete actual model."""
    try:
        raw = direct._json(direct._keys(request, direct.REQUEST_FIELDS, "composed barrier request"))
        if raw["kind"] != REQUEST_KIND:
            raise ConfigError("Require " + REQUEST_KIND)
        mid, schema = _schema(raw["definition"])
        before = parse_spec(raw["definition"])
        source = before.to_dict()
        _schema(source)
        projected = deepcopy(raw)
        projected.update(kind=direct.REQUEST_KIND, definition=composition.parameter_view(before))
        coefficients = direct.prepare(projected)
        result = deepcopy(source)
        faces = {row["id"]: row for row in composition._leaf(result, schema["path"])["faces"]}
        for change in coefficients.provenance["changes"]:
            row = faces[change["face_id"]]["diffusivity_m2_per_s"]
            if row[change["species_id"]] != change["before_m2_s"]:
                raise ConfigError(
                    "Projected diffusion coefficient lost its complete physical owner"
                )
            row[change["species_id"]] = change["after_m2_s"]
        after = parse_spec(result)
        result = after.to_dict()
        restored = deepcopy(result)
        original_faces = {
            row["id"]: row for row in composition._leaf(restored, schema["path"])["faces"]
        }
        for change in coefficients.provenance["changes"]:
            row = original_faces[change["face_id"]]["diffusivity_m2_per_s"]
            if row[change["species_id"]] != change["after_m2_s"]:
                raise ConfigError("Complete model admission changed a selected coefficient")
            row[change["species_id"]] = change["before_m2_s"]
        if restored != source:
            raise ConfigError(
                "Barrier preparation changed an unselected property or control history"
            )
        implementation = get_model(before.model)
        initial, _ = implementation.initial_values(before)
        final, _ = get_model(after.model).initial_values(after)
        if (
            get_model(after.model) is not implementation
            or type(final) is not type(initial)
            or direct._state_identity(final) != direct._state_identity(initial)
        ):
            raise ConfigError("Barrier preparation changed the full physical initial state")
        inventory = composition.owner_inventory(source, schema["path"])
        if composition.owner_inventory(result, schema["path"]) != inventory:
            raise ConfigError("Barrier preparation changed a physical inventory or volume")
        provenance = direct._json(
            dict(
                kind=KIND,
                bridge_id=BRIDGE_ID,
                request=raw,
                parent_model_id=mid,
                schema=schema,
                source_definition_sha256=digest(source),
                prepared_definition_sha256=digest(result),
                direct_parameter_preparation=coefficients.provenance,
                initial_state_fields=list(initial._fields),
                initial_state_sha256=direct._state_identity(initial),
                initial_owner_inventory=inventory,
                owner_inventory_sha256=digest(inventory),
                control_history_sha256=digest(source["experiment"]),
                changes=coefficients.provenance["changes"],
                projection_scope=(
                    "Geometry and static coefficients only; complete parent owns physics"
                ),
                projected_clock_policy="All source clocks on an unchanged-value passive schedule",
                scope=(
                    "Initial static coefficients on sealed uniform geometry, including live-water "
                    "parents with fixed face areas/lengths. No moving geometry, dynamic barrier, "
                    "native collocated update, bath, flow, cut or inherited-epoch claim."
                ),
            )
        )
        provenance["identity"] = digest(provenance)
        return Preparation(result, provenance)
    except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError, IndexError) as error:
        raise ConfigError("Invalid complete-owner barrier preparation: " + str(error)) from error


def replay(provenance):
    try:
        record = direct._json(provenance)
        identity = record.pop("identity")
        if record["kind"] != KIND or identity != digest(record):
            raise ConfigError("Stale composed barrier identity")
        result = prepare(record["request"])
        if digest(result.provenance) != digest(provenance):
            raise ConfigError("Complete-owner barrier recipe, state or coefficients changed")
        return result
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid composed barrier replay: " + str(error)) from error


def write_preparation(directory, prepared):
    expected = replay(prepared.provenance)
    if digest(expected.definition) != digest(prepared.definition):
        raise ConfigError("Prepared composition disagrees with its complete barrier recipe")
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    for name, value in (
        ("definition.json", expected.definition),
        ("provenance.json", expected.provenance),
    ):
        (root / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    return root
