"""Candidate polygon-owner geometry to the existing passive tissue admission.

Every inventory, constitutive coefficient, bath and control remains explicitly
declared. The existing resolved_tissue parser performs physical admission.
"""

import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from cells.processes import conservative_polygon_geometry as geometry

BRIDGE_ID = "cells_polygon_physical_owners_passive_tissue@1"
REQUEST_KIND = "cells.polygon_physical_owners_tissue_request@1"
RESULT_KIND = "cells.polygon_physical_owners_tissue_preparation@1"
ADMISSION_SOURCE_SHA256 = {
    "core/surface_tissue_spec.py": (
        "ca325e50b59a29ae25eaebc846cd126366e44c94ce0a931b833f26bb693db3aa"
    ),
    "models/surface_tissue.py": "a0c9993799b752913deaae7ccdab6780397e05d4e2ac30f66bd60de928eafe29",
    "numerics/surface_field.py": "6ae86409650223e5e81214ee2f57a5d6a0637c7d8ab2d3613e7dbc0d3dc26378",
    "numerics/surface_transport.py": (
        "f64cb3c0201be098793ce916ad65a19fd607b292c143c1b91950d03758f593d9"
    ),
    "processes/electrochemistry.py": (
        "e52dc29e3514268d538b7ceff293d32fd24d36ed3e9ef6242dc2906592c112f2"
    ),
}


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


class PhysicalRejected(ValueError):
    def __init__(self, reason, *, trial):
        super().__init__(reason)
        self.trial = trial


def _rows(rows, expected, fields, where):
    if type(rows) is not list or len(rows) != len(expected):
        raise ValueError("Complete exact physical owner rows required for " + where)
    result = {}
    for row in rows:
        geometry._keys(row, fields, where)
        name = geometry._id(row["id"])
        if name in result:
            raise ValueError("Duplicate physical owner: " + name)
        result[name] = row
    if set(result) != set(expected):
        raise ValueError("Physical owner IDs disagree with admitted geometry: " + where)
    return result


def _coefficient(value, *, positive=False):
    value = geometry._number(value, positive=positive)
    if value < 0:
        raise ValueError("Physical coefficient must be nonnegative")
    return value


def _species_values(row, names):
    geometry._keys(row, names, "species_coefficients")
    return {name: _coefficient(row[name]) for name in names}


def _ratio(row):
    return Fraction(int(row["numerator"]), int(row["denominator"]))


def _definition(bound, raw):
    geometry._keys(
        raw,
        {"kind", "opted_in_law", "geometry_identity", "physics", "experiment", "execution"},
        "physical_request",
    )
    if (
        raw["kind"] != REQUEST_KIND
        or raw["opted_in_law"] != BRIDGE_ID
        or type(raw["opted_in_law"]) is not str
        or raw["geometry_identity"] != bound.identity
    ):
        raise ValueError("Require explicit polygon physical-law opt-in and exact geometry identity")
    g = bound.geometry
    physics = raw["physics"]
    geometry._keys(
        physics,
        {
            "species",
            "temperature_K",
            "cells",
            "baths",
            "membranes",
            "contacts",
            "closure",
            "provenance",
        },
        "physical_declarations",
    )
    if (
        type(physics["provenance"]) is not dict
        or not physics["provenance"]
        or type(physics["species"]) is not list
        or not 1 <= len(physics["species"]) <= 8
    ):
        raise ValueError("Require explicit physical provenance and 1..8 species")
    species = []
    for row in physics["species"]:
        geometry._keys(row, {"id", "valence"}, "species")
        species.append(geometry._id(row["id"]))
    if len(set(species)) != len(species):
        raise ValueError("Duplicate species")
    inventory = {"id", "initial_amount_fmol", "initial_charge_C", "fixed_charge_equivalent_fmol"}
    cells = _rows(physics["cells"], [row["id"] for row in g["cells"]], inventory, "cells")
    baths = _rows(
        physics["baths"],
        [row["id"] for row in g["baths"]],
        inventory | {"reservoir", "boundary_potential_V"},
        "baths",
    )
    membranes = _rows(
        physics["membranes"],
        [row["id"] for row in g["membranes"]],
        {"id", "cell_id", "bath_id", "specific_capacitance_F_per_m2", "diffusivity_m2_per_s"},
        "membranes",
    )
    contacts = _rows(
        physics["contacts"],
        [row["id"] for row in g["contacts"]],
        {"id", "sender", "receiver", "membrane_ids", "permeability_m_per_s"},
        "contacts",
    )
    model = dict(
        id="resolved_tissue@1",
        species=physics["species"],
        temperature_K=geometry._number(physics["temperature_K"], positive=True),
        cells=[],
        extracellular=[],
        membranes=[],
        junctions=[],
        faces=[],
        closure=physics["closure"],
    )
    for row in g["cells"]:
        volume, _ = geometry._rounded(
            _ratio(row["certificates"]["volume"]["exact"]) * 10**15, "cell_volume_pL"
        )
        model["cells"].append(dict(cells[row["id"]], volume_pL=volume))
    for row in g["baths"]:
        volume, _ = geometry._rounded(
            Fraction.from_float(row["volume_m3"]) * 10**15, "bath_volume_pL"
        )
        model["extracellular"].append(dict(baths[row["id"]], volume_pL=volume))
    edges = {row["id"]: row for row in g["edges"]}
    for patch in g["membranes"]:
        row = membranes[patch["id"]]
        if (row["cell_id"], row["bath_id"]) != (patch["cell_id"], patch["bath_id"]):
            raise ValueError("Membrane physical owners disagree with exact polygon owners")
        specific = _coefficient(row["specific_capacitance_F_per_m2"], positive=True)
        diffusion = _species_values(row["diffusivity_m2_per_s"], species)
        area_squared = _ratio(edges[patch["edge_id"]]["certificates"]["area"]["radicand"])
        capacitance, _ = geometry._root(
            area_squared * Fraction.from_float(specific) ** 2, "membrane_capacitance_F"
        )
        permeability = {
            name: geometry._rounded(
                Fraction.from_float(value) / Fraction.from_float(patch["thickness_m"]),
                "membrane_permeability_m_per_s",
            )[0]
            for name, value in diffusion.items()
        }
        model["membranes"].append(
            dict(
                id=patch["id"],
                inside=patch["cell_id"],
                outside=patch["bath_id"],
                area_m2=patch["area_m2"],
                capacitance_F=capacitance,
                permeability_m_per_s=permeability,
                law="constant_field@1",
            )
        )
    for contact in g["contacts"]:
        row = contacts[contact["id"]]
        if any(row[key] != contact[key] for key in ("sender", "receiver", "membrane_ids")):
            raise ValueError("Physical junction must match the exact ordered reciprocal contact")
        model["junctions"].append(
            dict(
                id=contact["id"],
                sender=contact["sender"],
                receiver=contact["receiver"],
                area_m2=contact["area_m2"],
                permeability_m_per_s=_species_values(row["permeability_m_per_s"], species),
                law="constant_field@1",
            )
        )
    return dict(
        schema_version=1, model=model, experiment=raw["experiment"], execution=raw["execution"]
    )


def prepare(geometry_request, bound, raw):
    geometry.validate_binding(geometry_request, bound)
    # JSON round-trip owns all supplied inventories, coefficients and controls.
    raw = json.loads(geometry._json(raw))
    try:
        definition = _definition(bound, raw)
        package = Path(__file__).resolve().parents[1]
        for relative, expected in ADMISSION_SOURCE_SHA256.items():
            if hashlib.sha256((package / relative).read_bytes()).hexdigest() != expected:
                raise ValueError("Changed pinned physical admission source: " + relative)
        from cells.core.surface_tissue_spec import parse

        # This is the existing physical admission, including its complete
        # initial charge/current field checks. No solver trajectory is run.
        definition = parse(definition).to_dict()
    except Exception as error:
        raise PhysicalRejected(
            str(error),
            trial=dict(
                kind=RESULT_KIND,
                status="retained_physical_admission_refusal",
                geometry_identity=bound.identity,
                request=raw,
                failure_type=type(error).__name__,
                reason=str(error),
                physical_model_prepared=False,
            ),
        ) from error
    provenance = dict(
        kind=RESULT_KIND,
        bridge_id=BRIDGE_ID,
        geometry_identity=bound.identity,
        geometry_law=geometry.LAW_ID,
        geometry_request=geometry.request_record(geometry_request),
        geometry=bound.geometry,
        request=raw,
        definition_sha256=geometry._digest(definition),
        unit_policy=dict(
            cell_volume="Exact polygon extrusion rational converted to pL before rounding",
            bath_volume="Explicit binary64 physical m3 converted to pL before rounding",
            membrane_area="One exact shared-edge length times uniform height, rounded once",
            capacitance="Exact geometric area times declared specific capacitance, rounded once",
            permeability="Explicit diffusivity divided by explicit membrane thickness",
            contacts="One physical interface surface per exact shared edge; no doubled area",
            axial_caps="sealed_no_transport@1",
        ),
        exact_owner_axes=dict(
            cells=[row["id"] for row in definition["model"]["cells"]],
            baths=[row["id"] for row in definition["model"]["extracellular"]],
            membranes=[row["id"] for row in definition["model"]["membranes"]],
            contacts=[row["id"] for row in definition["model"]["junctions"]],
        ),
        inventories_rescaled=False,
        physical_model_prepared=True,
        physical_admission="Existing resolved_tissue@1 parser and initial definition checks",
        physical_admission_source_sha256=ADMISSION_SOURCE_SHA256,
        native_equivalence=False,
        B09_admission_inherited=False,
        scientific_qualification_inherited=False,
        solver_trajectory_executed=False,
    )
    identity = geometry._digest(dict(definition=definition, provenance=provenance))
    return Preparation(geometry._json(definition), geometry._json(provenance), identity)


def validate(geometry_request, bound, raw, prepared):
    if type(prepared) is not Preparation:
        raise ValueError("Require owned polygon physical preparation")
    expected = prepare(geometry_request, bound, raw)
    if prepared != expected:
        raise ValueError("Changed geometry, physical inventory, controls or owner mapping")
    return prepared
