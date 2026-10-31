"""Complete passive physical admission on explicit finite-ECM polygons."""

import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from cells.processes import finite_ecm_polygon_geometry as geometry

LAW_ID = "cells_finite_ecm_polygon_passive_preparation@1"
REQUEST_KIND = "cells.finite_ecm_polygon_passive_request@1"
RESULT_KIND = "cells.finite_ecm_polygon_passive_preparation@1"
SOURCES_SHA256 = "4d6196c9332ab0353d0eb513fbae2c00c5232ac4ce6a19f2bd5ad6a7da5c86f2"


class PhysicalRejected(ValueError):
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


def _pins():
    path = Path(__file__).with_name("finite_ecm_polygon_sources.json")
    if hashlib.sha256(path.read_bytes()).hexdigest() != SOURCES_SHA256:
        raise ValueError("Changed finite-ECM physical-admission source manifest")
    pins = json.loads(path.read_text())
    root = Path(__file__).resolve().parents[3]
    for name, expected in pins["source_sha256"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Changed finite-ECM admission source: " + name)
    return pins


def _rows(rows, expected):
    if type(rows) is not list or len(rows) != len(expected):
        raise ValueError("Complete identified physical owner rows required")
    result = {}
    for index, row in enumerate(rows):
        if type(row) is not dict or type(row.get("id")) is not str or row["id"] in result:
            raise ValueError("Require distinct identified physical owner rows")
        result[row["id"]] = (index, row)
    if set(result) != set(expected):
        raise ValueError("Physical owners disagree with complete finite-ECM partition")
    return result


def _at(value, path):
    for key in path:
        value = value[key]
    return value


def _materialize(binding, raw):
    geometry.exact._keys(
        raw,
        {
            "kind",
            "opted_in_law",
            "geometry_identity",
            "target_model_id",
            "definition_template",
            "provenance",
        },
        "finite_ecm_physical_request",
    )
    if (
        raw["kind"] != REQUEST_KIND
        or type(raw["opted_in_law"]) is not str
        or raw["opted_in_law"] != LAW_ID
        or raw["geometry_identity"] != binding.identity
        or raw["target_model_id"] != "resolved_tissue@1"
    ):
        raise ValueError("Require explicit owned finite-ECM passive identity and opt-in")
    template = raw["definition_template"]
    geometry.exact._keys(
        template,
        {"schema_version", "model", "experiment", "execution"},
        "complete_passive_template",
    )
    if (
        type(template["schema_version"]) is not int
        or template["schema_version"] != 1
        or template["model"]["id"] != "resolved_tissue@1"
        or type(raw["provenance"]) is not dict
        or not raw["provenance"]
    ):
        raise ValueError("Require a complete actual passive family and caller physical provenance")
    g = binding.geometry
    model = template["model"]
    if model["junctions"] != []:
        raise ValueError("This identity has no direct cell-cell junction or inferred cleft")
    regions = {row["id"]: row for row in g["regions"]}
    membranes = {row["id"]: row for row in g["membranes"]}
    faces = {row["id"]: row for row in g["faces"]}
    edges = {row["id"]: row for row in g["edges"]}
    cells = _rows(model["cells"], g["cell_ids"])
    baths = _rows(model["extracellular"], g["bath_ids"])
    mem_rows = _rows(model["membranes"], list(membranes))
    face_rows = _rows(model["faces"], list(faces))
    species = [row["id"] for row in model["species"]]
    if not species or len(set(species)) != len(species):
        raise ValueError("Require complete ordered distinct ionic species")
    expected = {}

    def expect(path, quantity, **owner):
        marker = _at(template, path)
        extras = (
            {"specific_capacitance_F_per_m2"}
            if quantity == "membrane_capacitance_F"
            else {"diffusivity_m2_per_s"}
            if quantity == "membrane_permeability_m_per_s"
            else set()
        )
        geometry.exact._keys(
            marker, {"$geometry", *owner, *extras}, "finite_ecm_quantity_reference"
        )
        if marker["$geometry"] != quantity or any(
            marker[key] != value for key, value in owner.items()
        ):
            raise ValueError("Geometry quantity has the wrong physical owner or units")
        expected[path] = marker

    for field, rows in (("cells", cells), ("extracellular", baths)):
        for name, (index, row) in rows.items():
            expect(("model", field, index, "volume_pL"), "region_volume_pL", region_id=name)
            if field == "extracellular" and (
                type(row["reservoir"]) is not bool or row["reservoir"]
            ):
                raise ValueError("This finite sealed ECM identity requires actual finite baths")
    for name, (index, row) in mem_rows.items():
        actual = membranes[name]
        if (row["inside"], row["outside"]) != (actual["cell_id"], actual["bath_id"]):
            raise ValueError("Membrane owners disagree with the actual cell-bath interface")
        expect(("model", "membranes", index, "area_m2"), "membrane_area_m2", membrane_id=name)
        expect(
            ("model", "membranes", index, "capacitance_F"),
            "membrane_capacitance_F",
            membrane_id=name,
        )
        geometry.exact._keys(row["permeability_m_per_s"], species, "membrane_species")
        for ion in species:
            expect(
                ("model", "membranes", index, "permeability_m_per_s", ion),
                "membrane_permeability_m_per_s",
                membrane_id=name,
            )
    for name, (index, row) in face_rows.items():
        actual = faces[name]
        if (row["sender"], row["receiver"]) != (actual["sender"], actual["receiver"]):
            raise ValueError("A bath face must retain its actual ordered polygon owners")
        expect(("model", "faces", index, "area_m2"), "face_area_m2", face_id=name)
        expect(("model", "faces", index, "length_m"), "face_length_m", face_id=name)
        geometry.exact._keys(row["diffusivity_m2_per_s"], species, "face_species")
        for value in row["diffusivity_m2_per_s"].values():
            if geometry.exact._number(value) < 0:
                raise ValueError("Explicit bath-face diffusivities must be nonnegative")
    conversions = []

    def quantity(marker):
        name = marker["$geometry"]
        if name == "region_volume_pL":
            ratio = geometry._ratio(regions[marker["region_id"]]["certificates"]["volume"]["exact"])
            return (*geometry.exact._rounded(ratio * 10**15, name), "pL")
        if name in ("membrane_area_m2", "membrane_capacitance_F", "face_area_m2"):
            route = (
                faces[marker["face_id"]]
                if name == "face_area_m2"
                else membranes[marker["membrane_id"]]
            )
            squared = geometry._ratio(edges[route["edge_id"]]["certificates"]["area"]["radicand"])
            if name == "membrane_capacitance_F":
                specific = geometry.exact._number(
                    marker["specific_capacitance_F_per_m2"], positive=True
                )
                squared *= Fraction.from_float(specific) ** 2
            return (*geometry.exact._root(squared, name), "F" if name.endswith("_F") else "m2")
        if name == "face_length_m":
            squared = geometry._ratio(
                faces[marker["face_id"]]["certificates"]["length"]["radicand"]
            )
            return (*geometry.exact._root(squared, name), "m")
        diffusion = geometry.exact._number(marker["diffusivity_m2_per_s"])
        if diffusion < 0:
            raise ValueError("Explicit membrane diffusivity must be nonnegative")
        return (
            *geometry.exact._rounded(
                Fraction.from_float(diffusion) / Fraction.from_float(g["membrane_thickness_m"]),
                name,
            ),
            "m/s",
        )

    used = set()

    def visit(value, path=()):
        if type(value) is dict and "$geometry" in value:
            if path not in expected:
                raise ValueError("Geometry cannot replace inventory, constitutive law or controls")
            number, certificate, units = quantity(value)
            used.add(path)
            conversions.append(
                dict(
                    path=list(path),
                    reference=value,
                    value_binary64_hex=number.hex(),
                    units=units,
                    certificate=certificate,
                )
            )
            return number
        if type(value) is dict:
            return {key: visit(item, (*path, key)) for key, item in value.items()}
        if type(value) is list:
            return [visit(item, (*path, index)) for index, item in enumerate(value)]
        return value

    definition = visit(template)
    if used != set(expected):
        raise ValueError("Every geometric field requires an explicit identified quantity reference")
    return definition, conversions


def _semantic(value, name=None):
    if type(value) is dict:
        return {key: _semantic(item, key) for key, item in value.items()}
    if type(value) is not list:
        return value
    result = [_semantic(item) for item in value]
    key = {
        "cells": "id",
        "extracellular": "id",
        "membranes": "id",
        "faces": "id",
        "junctions": "id",
        "membrane_controls": "membrane_id",
        "junction_controls": "junction_id",
    }.get(name)
    if key is not None:
        if len({row[key] for row in result}) != len(result):
            raise ValueError("Duplicate identified physical or control rows")
        return sorted(result, key=lambda row: row[key])
    return result


def prepare(geometry_request, binding, request):
    geometry.validate_binding(geometry_request, binding)
    raw = json.loads(geometry.exact._json(request))
    definition = None
    conversions = []
    stage = "admission_source_pins"
    try:
        pins = _pins()
        stage = "complete_owner_and_unit_materialization"
        definition, conversions = _materialize(binding, raw)
        stage = "existing_complete_physical_admission"
        from cells.core import surface_tissue_spec as schema

        spec = schema.parse(definition)
        if type(spec.model) is not schema.SurfaceTissueModel:
            raise ValueError("Require the actual public passive tissue family")
        admitted = schema.to_dict(spec)
        if _semantic(admitted) != _semantic(definition):
            raise ValueError("Physical admission changed a declared owner, inventory or control")
    except Exception as error:
        raise PhysicalRejected(
            str(error),
            trial=dict(
                kind=RESULT_KIND,
                status="retained_physical_refusal",
                stage=stage,
                request=raw,
                geometry_identity=binding.identity,
                materialized_definition=definition,
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
        geometry_identity=binding.identity,
        geometry_request=geometry.request_record(geometry_request),
        geometry=binding.geometry,
        request=raw,
        materialized_definition=definition,
        conversions=conversions,
        admission_source_manifest=pins,
        physical_admission="cells.core.surface_tissue_spec.parse",
        actual_model_type="cells.core.surface_tissue_spec.SurfaceTissueModel",
        definition_sha256=geometry.exact._digest(admitted),
        finite_ECM_volumes_from_declared_polygons=True,
        outer_and_axial_boundaries="sealed_no_transport@1",
        face_distance_policy="orthogonal_volume_centroids_shared_face@1",
        membrane_excluded_volume=0,
        inventories_rescaled=False,
        physics_defaults_inserted=False,
        physical_model_prepared=True,
        native_equivalence=False,
        qualification_inherited=False,
        trajectory_executed=False,
    )
    return Preparation(
        geometry.exact._json(admitted),
        geometry.exact._json(provenance),
        geometry.exact._digest(dict(definition=admitted, provenance=provenance)),
    )


def validate(geometry_request, binding, request, value):
    if type(value) is not Preparation or prepare(geometry_request, binding, request) != value:
        raise ValueError("Changed finite-ECM geometry, distance, inventory, boundary or controls")
    return value
