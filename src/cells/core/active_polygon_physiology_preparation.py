"""Candidate complete active definitions bound to polygon physical owners.

Only identified geometric/unit references are resolved. The caller supplies the
actual family, inventories, physiology, reservoirs and every control. Each real
family parser performs its existing complete physical admission.
"""

import hashlib
import importlib
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from cells.processes import conservative_polygon_geometry as geometry

LAW_ID = "cells_polygon_active_physiology_preparation@1"
REQUEST_KIND = "cells.polygon_active_physiology_request@1"
RESULT_KIND = "cells.polygon_active_physiology_preparation@1"
BASE_GEOMETRY_SHA256 = "5d267b20cdb3a05f4f036bbc3fa6978b40780ca4394f67ac6c33a8b605af4b0d"
BASE_BUNDLE_SHA256 = "2a1182f4091761f20c8048e0bd8cf8281ff67b808410be2820dddb4531f1d95b"
SOURCES_SHA256 = "994ab1170ccdc1db32120ba1794b316e4ef0a297b7ebd23c3dda0c158edd1939"
MAX_CELLS = 16
MAX_CHANNELS = 256

# parser module, actual model module, exact model type, calcium, fuel, open,
# explicit nested ionic identity (None for a direct ionic/energy definition).
FAMILIES = {
    "resolved_tissue@2": (
        "surface_kinetic_spec",
        "surface_kinetic",
        "SurfaceKineticModel",
        False,
        False,
        False,
        None,
    ),
    "resolved_tissue@12": (
        "surface_kinetic_spec",
        "surface_hcn_extra",
        "SurfaceHCNExtraModel",
        False,
        False,
        False,
        None,
    ),
    "resolved_calcium@1": (
        "surface_calcium_spec",
        "surface_calcium",
        "SurfaceCalciumModel",
        True,
        False,
        False,
        "resolved_tissue@2",
    ),
    "resolved_calcium@11": (
        "surface_calcium_spec",
        "surface_calcium_hcn_extra",
        "SurfaceCalciumHCNExtraModel",
        True,
        False,
        False,
        "resolved_tissue@12",
    ),
    "resolved_energy@1": (
        "surface_energy_spec",
        "surface_energy",
        "SurfaceEnergyModel",
        False,
        True,
        False,
        None,
    ),
    "resolved_energy@2": (
        "surface_energy_spec",
        "surface_energy_morris_lecar",
        "SurfaceEnergyMorrisLecarModel",
        False,
        True,
        False,
        None,
    ),
    "resolved_calcium_energy@1": (
        "surface_calcium_energy_spec",
        "surface_calcium_energy",
        "SurfaceCalciumEnergyModel",
        True,
        True,
        False,
        "resolved_tissue@8",
    ),
    "resolved_calcium_energy@5": (
        "surface_calcium_energy_spec",
        "surface_calcium_energy_hcn_extra",
        "SurfaceCalciumEnergyHCNExtraModel",
        True,
        True,
        False,
        "resolved_tissue@12",
    ),
    "resolved_open_calcium@1": (
        "surface_open_calcium_spec",
        "surface_open_calcium",
        "SurfaceOpenCalciumModel",
        True,
        False,
        True,
        "resolved_tissue@12",
    ),
    "resolved_open_calcium_energy@1": (
        "surface_open_calcium_energy_spec",
        "surface_open_calcium_energy",
        "SurfaceOpenCalciumEnergyModel",
        True,
        True,
        True,
        "resolved_tissue@12",
    ),
}


class ActivePreparationRejected(ValueError):
    def __init__(self, reason, *, trial):
        super().__init__(reason)
        self.trial = trial


@dataclass(frozen=True, slots=True)
class Preparation:
    definition_json: str
    provenance_json: str
    identity: str

    @property
    def definition(self):
        return json.loads(self.definition_json)

    @property
    def provenance(self):
        return json.loads(self.provenance_json)


def _verify_sources():
    if hashlib.sha256(Path(geometry.__file__).read_bytes()).hexdigest() != BASE_GEOMETRY_SHA256:
        raise ValueError("Changed frozen polygon geometry implementation")
    path = Path(__file__).with_name("active_polygon_physiology_sources.json")
    if hashlib.sha256(path.read_bytes()).hexdigest() != SOURCES_SHA256:
        raise ValueError("Changed active physical-admission source manifest")
    pins = json.loads(path.read_text())
    root = Path(__file__).resolve().parents[3]
    for relative, expected in pins["source_sha256"].items():
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != expected:
            raise ValueError("Changed active admission source: " + relative)
    return pins


def _rows(rows, ids, key, where):
    if type(rows) is not list or len(rows) != len(ids):
        raise ValueError("Complete explicit owner rows required for " + where)
    found = {}
    for index, row in enumerate(rows):
        if (
            type(row) is not dict
            or key not in row
            or type(row[key]) is not str
            or row[key] in found
        ):
            raise ValueError("Distinct identified owner rows required for " + where)
        found[row[key]] = (index, row)
    if set(found) != set(ids):
        raise ValueError("Owner IDs disagree with polygon geometry: " + where)
    return found


def _at(value, path):
    for part in path:
        value = value[part]
    return value


def _ratio(row):
    return Fraction(int(row["numerator"]), int(row["denominator"]))


def _positive(value):
    return geometry._number(value, positive=True)


def _nonnegative(value):
    value = geometry._number(value)
    if value < 0:
        raise ValueError("Diffusivity must be nonnegative")
    return value


def _owner_manifest(bound, raw):
    geometry._keys(
        raw,
        {
            "kind",
            "opted_in_law",
            "geometry_identity",
            "target_model_id",
            "definition_template",
            "volume_policy",
            "cell_partitions",
            "ER_geometry",
            "contact_geometry",
            "provenance",
        },
        "active_request",
    )
    if (
        raw["kind"] != REQUEST_KIND
        or type(raw["opted_in_law"]) is not str
        or raw["opted_in_law"] != LAW_ID
        or raw["geometry_identity"] != bound.identity
    ):
        raise ValueError("Require explicit active-law opt-in and exact owned polygon geometry")
    target = raw["target_model_id"]
    if type(target) is not str or target not in FAMILIES:
        raise ValueError("Unsupported active polygon model identity")
    template = raw["definition_template"]
    geometry._keys(
        template, {"schema_version", "model", "experiment", "execution"}, "complete_active_template"
    )
    if (
        type(template["schema_version"]) is not int
        or template["schema_version"] != 1
        or template["model"]["id"] != target
    ):
        raise ValueError("The caller must supply its actual complete target family")
    if type(raw["provenance"]) is not dict or not raw["provenance"]:
        raise ValueError("Explicit active inventory/coefficient/control provenance required")
    _, _, _, has_calcium, has_fuel, is_open, ionic_id = FAMILIES[target]
    g = bound.geometry
    if not 1 <= len(g["cells"]) <= MAX_CELLS:
        raise ValueError("Active polygon preparation supports 1..16 physical cells")
    prefix = ("model", "ionic") if has_calcium else ("model",)
    ionic = _at(template, prefix)
    if has_calcium and ionic["id"] != ionic_id:
        raise ValueError("Calcium/fuel/open family needs its exact declared ionic identity")
    if ionic["temperature_K"] != 298.15 or type(ionic["temperature_K"]) is bool:
        raise ValueError("Existing active channel identities require explicit 298.15 K")
    if ionic["faces"] != []:
        raise ValueError("This polygon owner identity has no exterior spatial-face geometry")
    ids = [row["id"] for row in g["cells"]]
    bath_ids = [row["id"] for row in g["baths"]]
    cells = _rows(ionic["cells"], ids, "id", "ionic cells")
    baths = _rows(ionic["extracellular"], bath_ids, "id", "ionic baths")
    membranes = _rows(
        ionic["membranes"], [row["id"] for row in g["membranes"]], "id", "ionic membranes"
    )
    contacts = _rows(
        ionic["junctions"], [row["id"] for row in g["contacts"]], "id", "ionic contacts"
    )
    species = [row["id"] for row in ionic["species"]]
    if not species or len(set(species)) != len(species):
        raise ValueError("Explicit unique ordered ionic species required")
    expected = {}

    def expect(path, quantity, **owner):
        ref = _at(template, path)
        extras = (
            {"specific_capacitance_F_per_m2"}
            if quantity == "membrane_capacitance_F"
            else {"diffusivity_m2_per_s"}
            if quantity.endswith("permeability_m_per_s")
            else set()
        )
        geometry._keys(ref, {"$geometry", *owner, *extras}, "identified_geometry_reference")
        if ref["$geometry"] != quantity or any(ref[k] != v for k, v in owner.items()):
            raise ValueError("Geometry reference has the wrong physical owner or role")
        expected[path] = dict(quantity=quantity, owner=owner, reference=ref)

    policy = (
        "polygon_total_partitioned_cytosol_ER@1" if has_calcium else "polygon_total_ionic_volume@1"
    )
    if raw["volume_policy"] != policy:
        raise ValueError("Declare the actual family-specific geometric volume policy")
    partitions = {}
    if has_calcium:
        partition_rows = _rows(raw["cell_partitions"], ids, "cell_id", "cytosol/ER partitions")
        for name, (_, row) in partition_rows.items():
            geometry._keys(row, {"cell_id", "ER_fraction"}, "cell_partition")
            fraction = Fraction.from_float(_positive(row["ER_fraction"]))
            if fraction >= 1:
                raise ValueError("ER fraction must lie strictly between zero and one")
            partitions[name] = fraction
    elif raw["cell_partitions"] != [] or raw["ER_geometry"] != []:
        raise ValueError("An ionic-only family has no unresolved ER partition")
    for name, (i, _) in cells.items():
        expect(
            (*prefix, "cells", i, "volume_pL"),
            "cell_volume_pL",
            cell_id=name,
            role="cytosol" if has_calcium else "total",
        )
    for name, (i, row) in baths.items():
        if type(row["reservoir"]) is not bool:
            raise ValueError("Every actual reservoir flag must be explicit")
        expect((*prefix, "extracellular", i, "volume_pL"), "bath_volume_pL", bath_id=name)
    geom_membranes = {row["id"]: row for row in g["membranes"]}
    for name, (i, row) in membranes.items():
        actual = geom_membranes[name]
        if (row["inside"], row["outside"]) != (actual["cell_id"], actual["bath_id"]):
            raise ValueError("Membrane inside/outside IDs disagree with exact polygon owners")
        if "pump" not in row:
            raise ValueError("Every patch explicitly declares its pump or null")
        expect((*prefix, "membranes", i, "area_m2"), "membrane_area_m2", membrane_id=name)
        expect(
            (*prefix, "membranes", i, "capacitance_F"), "membrane_capacitance_F", membrane_id=name
        )
        geometry._keys(row["permeability_m_per_s"], species, "complete_membrane_diffusivities")
        for species_id in species:
            expect(
                (*prefix, "membranes", i, "permeability_m_per_s", species_id),
                "membrane_permeability_m_per_s",
                membrane_id=name,
            )
    contact_geometry = _rows(
        raw["contact_geometry"],
        [row["id"] for row in g["contacts"]],
        "contact_id",
        "junction path lengths",
    )
    geom_contacts = {row["id"]: row for row in g["contacts"]}
    for name, (i, row) in contacts.items():
        actual = geom_contacts[name]
        _, extra = contact_geometry[name]
        geometry._keys(extra, {"contact_id", "membrane_ids", "path_length_m"}, "contact_geometry")
        if extra["membrane_ids"] != actual["membrane_ids"] or (row["sender"], row["receiver"]) != (
            actual["sender"],
            actual["receiver"],
        ):
            raise ValueError("Junction orientation/partners disagree with the actual interface")
        _positive(extra["path_length_m"])
        if "gate" not in row:
            raise ValueError("Every junction needs its full intrinsic gate declaration")
        expect((*prefix, "junctions", i, "area_m2"), "contact_area_m2", contact_id=name)
        geometry._keys(row["permeability_m_per_s"], species, "complete_junction_diffusivities")
        for species_id in species:
            expect(
                (*prefix, "junctions", i, "permeability_m_per_s", species_id),
                "contact_permeability_m_per_s",
                contact_id=name,
            )
    channels = ionic["channels"]
    if type(channels) is not list or len(channels) > MAX_CHANNELS:
        raise ValueError("Declare a bounded complete channel population list")
    for i, row in enumerate(channels):
        if row["membrane_id"] not in membranes:
            raise ValueError("Channel must name its actual polygon membrane owner")
        expect(
            (*prefix, "channels", i, "max_permeability_m_per_s"),
            "membrane_permeability_m_per_s",
            membrane_id=row["membrane_id"],
        )
    er_geometry = {}
    if has_calcium:
        model = template["model"]
        stores = _rows(model["stores"], ids, "cell_id", "complete owned chemical stores")
        er_geometry = _rows(raw["ER_geometry"], ids, "cell_id", "explicit internal ER geometry")
        for name, (index, row) in stores.items():
            _, extra = er_geometry[name]
            geometry._keys(
                extra,
                {
                    "cell_id",
                    "membrane_id",
                    "cytosol_compartment_id",
                    "ER_compartment_id",
                    "area_m2",
                    "thickness_m",
                },
                "ER_geometry",
            )
            _positive(extra["area_m2"])
            _positive(extra["thickness_m"])
            store = row["model"]
            membrane = store["membrane"]
            if (membrane["id"], membrane["cytosol"], membrane["er"]) != (
                extra["membrane_id"],
                extra["cytosol_compartment_id"],
                extra["ER_compartment_id"],
            ):
                raise ValueError("ER membrane and chemical compartment roles must be explicit")
            parts = _rows(
                store["compartments"],
                [extra["cytosol_compartment_id"], extra["ER_compartment_id"]],
                "id",
                "ER chemical compartments",
            )
            for role, part_id in (
                ("cytosol", extra["cytosol_compartment_id"]),
                ("ER", extra["ER_compartment_id"]),
            ):
                j, _ = parts[part_id]
                expect(
                    ("model", "stores", index, "model", "compartments", j, "volume_pL"),
                    "cell_volume_pL",
                    cell_id=name,
                    role=role,
                )
            expect(
                ("model", "stores", index, "model", "membrane", "area_m2"),
                "ER_area_m2",
                cell_id=name,
                membrane_id=membrane["id"],
            )
            store_species = [s["id"] for s in store["species"]]
            geometry._keys(
                membrane["permeability_m_per_s"], store_species, "complete_ER_diffusivities"
            )
            for species_id in store_species:
                expect(
                    (
                        "model",
                        "stores",
                        index,
                        "model",
                        "membrane",
                        "permeability_m_per_s",
                        species_id,
                    ),
                    "ER_permeability_m_per_s",
                    cell_id=name,
                    membrane_id=membrane["id"],
                )
            if membrane["release"] is not None:
                expect(
                    (
                        "model",
                        "stores",
                        index,
                        "model",
                        "membrane",
                        "release",
                        "permeability_m_per_s",
                    ),
                    "ER_permeability_m_per_s",
                    cell_id=name,
                    membrane_id=membrane["id"],
                )
        for field in ("plasma_transport", "calcium_channels", "ip3_release"):
            if field not in model:
                raise ValueError("Complete calcium routes/buffers/control ownership required")
        _rows(
            model["plasma_transport"]["membranes"], list(membranes), "membrane_id", "plasma routes"
        )
        calcium_channels = _rows(
            model["calcium_channels"], list(membranes), "membrane_id", "owned Cav1.2 populations"
        )
        for name, (i, _) in calcium_channels.items():
            expect(
                ("model", "calcium_channels", i, "max_permeability_m_per_s"),
                "membrane_permeability_m_per_s",
                membrane_id=name,
            )
        _rows(model["ip3_release"], ids, "cell_id", "free-IP3 bindings")
    pools = {}
    if has_fuel:
        rows = template["model"]["energy_pools"]
        pools = {row["id"]: row for row in rows}
        if (
            len(pools) != len(rows)
            or len(rows) != len(ids)
            or {row["cell_id"] for row in rows} != set(ids)
        ):
            raise ValueError("Every physical cytosol needs exactly one declared finite fuel owner")

        def owned_pool(pump, cell_id):
            if pump is None:
                return
            meta = pump["metabolism"]
            geometry._keys(meta, {"kind", "pool_id"}, "actual_finite_pump_fuel")
            if (
                meta["kind"] != "finite_energy_pool@1"
                or meta["pool_id"] not in pools
                or pools[meta["pool_id"]]["cell_id"] != cell_id
            ):
                raise ValueError("Finite pumps must consume their actual cytosol's fuel pool")

        for name, (_, row) in membranes.items():
            owned_pool(row["pump"], geom_membranes[name]["cell_id"])
        if has_calcium:
            for row in template["model"]["stores"]:
                owned_pool(row["model"]["membrane"]["pump"], row["cell_id"])
            for row in template["model"]["plasma_transport"]["membranes"]:
                owned_pool(row["pump"], geom_membranes[row["membrane_id"]]["cell_id"])
        for port in template["model"]["regeneration_ports"]:
            if port["pool_id"] not in pools:
                raise ValueError("Regeneration port requires its declared finite-pool owner")
    return dict(
        target=target,
        family=FAMILIES[target],
        ionic_prefix=prefix,
        expected=expected,
        partitions=partitions,
        ER_geometry={key: row for key, (_, row) in er_geometry.items()},
        contact_geometry={key: row for key, (_, row) in contact_geometry.items()},
        pools=pools,
        reservoirs={name: row["reservoir"] for name, (_, row) in baths.items()},
        owner_projection=dict(
            cells=[row["id"] for row in ionic["cells"]],
            baths=[row["id"] for row in ionic["extracellular"]],
            membranes=[row["id"] for row in ionic["membranes"]],
            contacts=[row["id"] for row in ionic["junctions"]],
        ),
        open_family=is_open,
    )


def _materialize(bound, raw, owners):
    g = bound.geometry
    cells = {row["id"]: row for row in g["cells"]}
    baths = {row["id"]: row for row in g["baths"]}
    membranes = {row["id"]: row for row in g["membranes"]}
    edges = {row["id"]: row for row in g["edges"]}
    contacts = {row["id"]: row for row in g["contacts"]}
    conversions = []
    used = set()

    def quantity(reference):
        name = reference["$geometry"]
        if name == "cell_volume_pL":
            cell = reference["cell_id"]
            value = _ratio(cells[cell]["certificates"]["volume"]["exact"])
            role = reference["role"]
            fraction = owners["partitions"].get(cell)
            if role == "ER":
                value *= fraction
            elif role == "cytosol":
                value *= 1 - fraction
            return (*geometry._rounded(value * 10**15, name), "pL")
        if name == "bath_volume_pL":
            return (
                *geometry._rounded(
                    Fraction.from_float(baths[reference["bath_id"]]["volume_m3"]) * 10**15, name
                ),
                "pL",
            )
        if name in ("membrane_area_m2", "membrane_capacitance_F"):
            membrane = membranes[reference["membrane_id"]]
            squared = _ratio(edges[membrane["edge_id"]]["certificates"]["area"]["radicand"])
            if name == "membrane_capacitance_F":
                squared *= (
                    Fraction.from_float(_positive(reference["specific_capacitance_F_per_m2"])) ** 2
                )
            return (*geometry._root(squared, name), "F" if name.endswith("_F") else "m2")
        if name == "contact_area_m2":
            edge = edges[contacts[reference["contact_id"]]["edge_id"]]
            return (*geometry._root(_ratio(edge["certificates"]["area"]["radicand"]), name), "m2")
        if name == "ER_area_m2":
            return (
                *geometry._rounded(
                    Fraction.from_float(owners["ER_geometry"][reference["cell_id"]]["area_m2"]),
                    name,
                ),
                "m2",
            )
        if name.endswith("permeability_m_per_s"):
            diffusion = Fraction.from_float(_nonnegative(reference["diffusivity_m2_per_s"]))
            if name.startswith("membrane_"):
                thickness = g["thickness_m"]
            elif name.startswith("contact_"):
                thickness = owners["contact_geometry"][reference["contact_id"]]["path_length_m"]
            else:
                thickness = owners["ER_geometry"][reference["cell_id"]]["thickness_m"]
            return (
                *geometry._rounded(diffusion / Fraction.from_float(_positive(thickness)), name),
                "m/s",
            )
        raise ValueError("Unknown physical geometry reference")

    def visit(value, path=()):
        if type(value) is dict and "$geometry" in value:
            if path not in owners["expected"]:
                raise ValueError(
                    "A geometry reference cannot replace inventory, physiology or controls"
                )
            number, certificate, unit = quantity(value)
            used.add(path)
            conversions.append(
                dict(
                    path=list(path),
                    reference=value,
                    value_binary64_hex=number.hex(),
                    units=unit,
                    certificate=certificate,
                )
            )
            return number
        if type(value) is dict:
            return {key: visit(item, (*path, key)) for key, item in value.items()}
        if type(value) is list:
            return [visit(item, (*path, index)) for index, item in enumerate(value)]
        return value

    result = visit(raw["definition_template"])
    if used != set(owners["expected"]):
        raise ValueError("Every required geometry quantity must use its exact owned reference")
    return result, conversions


def _semantic(value, path=()):
    if type(value) is dict:
        return {key: _semantic(item, (*path, key)) for key, item in value.items()}
    if type(value) is not list:
        return value
    rows = [_semantic(item, (*path, index)) for index, item in enumerate(value)]
    name = path[-1] if path else None
    chemical_store = (
        len(path) == 5
        and path[:2] == ("model", "stores")
        and type(path[2]) is int
        and path[3] == "model"
    )
    if chemical_store and name == "moieties":
        if any(type(row) is not str for row in rows) or len(set(rows)) != len(rows):
            raise ValueError("Require distinct named chemical-store moieties")
        return sorted(rows)
    owner_lists = {
        "cells": "id",
        "extracellular": "id",
        "membranes": "id",
        "junctions": "id",
        "channels": "id",
        "stores": "cell_id",
        "calcium_channels": "membrane_id",
        "ip3_release": "cell_id",
        "energy_pools": "id",
        "regeneration_ports": "id",
    }
    if chemical_store and name in {"species", "compartments", "reactions"}:
        key = "id"
    elif name == "membranes" and rows and "membrane_id" in rows[0]:
        key = "membrane_id"
    elif type(name) is str and name.endswith("_controls"):
        key = {
            "store_controls": "cell_id",
            "plasma_controls": "membrane_id",
            "calcium_channel_controls": "channel_id",
        }.get(name, name.removesuffix("_controls") + "_id")
    else:
        key = owner_lists.get(name)
    if key is not None:
        if any(type(row) is not dict or key not in row for row in rows) or len(
            {row[key] for row in rows}
        ) != len(rows):
            raise ValueError("Duplicate or incomplete identified physiology/control rows")
        return sorted(rows, key=lambda row: row[key])
    return rows


def prepare(geometry_request, bound, request):
    geometry.validate_binding(geometry_request, bound)
    raw = json.loads(geometry._json(request))
    materialized = None
    definition = None
    conversions = []
    stage = "source_pins"
    try:
        pins = _verify_sources()
        stage = "owner_and_unit_contract"
        owners = _owner_manifest(bound, raw)
        stage = "geometric_quantities"
        materialized, conversions = _materialize(bound, raw, owners)
        stage = "existing_complete_physical_admission"
        parser = importlib.import_module("cells.core." + owners["family"][0])
        spec = parser.parse(materialized)
        expected_type = "cells.core." + owners["family"][0] + "." + owners["family"][2]
        if type(spec.model).__module__ + "." + type(spec.model).__name__ != expected_type:
            raise ValueError("The actual family parser did not return its exact model type")
        definition = parser.to_dict(spec)
        if definition["model"]["id"] != raw["target_model_id"] or _semantic(
            definition
        ) != _semantic(materialized):
            raise ValueError(
                "Physical admission changed declared inventory, physiology or controls"
            )
    except Exception as error:
        raise ActivePreparationRejected(
            str(error),
            trial=dict(
                kind=RESULT_KIND,
                status="retained_active_preparation_refusal",
                stage=stage,
                request=raw,
                geometry_identity=bound.identity,
                materialized_definition=materialized,
                admitted_definition=definition,
                conversions=conversions,
                failure_type=type(error).__name__,
                reason=str(error),
                physical_model_prepared=False,
            ),
        ) from error
    provenance = dict(
        kind=RESULT_KIND,
        law=LAW_ID,
        geometry_law=geometry.LAW_ID,
        geometry_identity=bound.identity,
        geometry_request=geometry.request_record(geometry_request),
        geometry=bound.geometry,
        base_static_bundle_sha256=BASE_BUNDLE_SHA256,
        request=raw,
        materialized_definition=materialized,
        conversions=conversions,
        target_model_id=raw["target_model_id"],
        actual_model_type=expected_type,
        parser="cells.core." + owners["family"][0] + ".parse",
        admission_source_manifest=pins,
        owner_projection=owners["owner_projection"],
        actual_reservoir_flags=owners["reservoirs"],
        volume_policy=raw["volume_policy"],
        cell_partitions=raw["cell_partitions"],
        ER_geometry=raw["ER_geometry"],
        contact_geometry=raw["contact_geometry"],
        definition_sha256=geometry._digest(definition),
        inventories_rescaled=False,
        physiology_defaults_inserted=False,
        target_identity_relabelled=False,
        physical_model_prepared=True,
        solver_trajectory_executed=False,
        native_equivalence=False,
        geometry_or_family_qualification_inherited=False,
    )
    identity = geometry._digest(dict(definition=definition, provenance=provenance))
    return Preparation(geometry._json(definition), geometry._json(provenance), identity)


def validate(geometry_request, bound, request, value):
    if type(value) is not Preparation:
        raise ValueError("Require the complete immutable active polygon preparation")
    expected = prepare(geometry_request, bound, request)
    if value != expected:
        raise ValueError("Changed active geometry, physiology, ownership, inventory or controls")
    return value
