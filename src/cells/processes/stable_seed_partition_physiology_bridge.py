"""Passive initial physiology on explicit positive cell/bath partitions.

The exact accepted upstream source review is mandatory. Numerical qualification
is separate; no integration, parameter inference or native equivalence exists.
"""

import hashlib
import json
import math
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path

from cells.core import finite_ecm_polygon_preparation as physical
from cells.processes import stable_seed_explicit_ecm_partition as constructor

LAW_ID = "cells_explicit_seed_partition_passive_initial_physiology_bridge@1"
INPUT_KIND = "cells.explicit_seed_partition_initial_physiology_declaration@1"
# Chief's immutable ECM02 source disposition; it grants no numerical pass.
UPSTREAM_SOURCE_REVIEW_SHA256 = "a8c09e4245079f55784e62d79e62d05e616dc5a665de5fb62b5235365b6078c7"
UPSTREAM_PREPARED_MANIFEST_SHA256 = (
    "5b6257f7a8f0f8a51b6903fb55aba11fe34c0934f2e10351e377a42eee81b406"
)
UPSTREAM_REFERENCE_SHA256 = "5b2240bf02166ae4bc73e03a669611d3328448fe1dd5824919ccbf59dc8f702c"
UPSTREAM_SOURCE_REVIEW_STATUS = "clear_for_prospective_guarded_qualification_preparation"
DRAFT_ONLY = False
SOURCE_PINS = {
    "src/cells/processes/stable_seed_explicit_ecm_partition.py": (
        "79c1bd6cd2f405425ad1b789515080c102a76c4e4110fc9007d0e7216e6179e9"
    ),
    "src/cells/core/finite_ecm_polygon_preparation.py": (
        "a4b94d721023b98e8acc4df935f6e7ce651ad4ad0a63a692b09d346c56fc1180"
    ),
    "src/cells/core/surface_tissue_spec.py": (
        "ca325e50b59a29ae25eaebc846cd126366e44c94ce0a931b833f26bb693db3aa"
    ),
    "src/cells/models/surface_tissue.py": (
        "a0c9993799b752913deaae7ccdab6780397e05d4e2ac30f66bd60de928eafe29"
    ),
    "src/cells/numerics/surface_field.py": (
        "6ae86409650223e5e81214ee2f57a5d6a0637c7d8ab2d3613e7dbc0d3dc26378"
    ),
    "src/cells/numerics/surface_transport.py": (
        "f64cb3c0201be098793ce916ad65a19fd607b292c143c1b91950d03758f593d9"
    ),
    "src/cells/numerics/extracellular_field.py": (
        "bb0702893a0605616fa84e7864d1e8b4409dbf3404a0b8c8195a538c2488fbbf"
    ),
    "src/cells/core/schedule.py": (
        "889eba6db8fcec06a290bc367eb1ddaaabbccec4a5b591ee35b5bc8a4e6082be"
    ),
    "src/cells/processes/electrochemistry.py": (
        "e52dc29e3514268d538b7ceff293d32fd24d36ed3e9ef6242dc2906592c112f2"
    ),
    "validation/tissue/surface_field_protocol.json": (
        "8dfaaf2390941700d2b5de6f7fc221fdeaa0fd6390af717ae1d3b88dff2109c5"
    ),
}
# Existing field-qualification accounting budgets, not caller physics defaults.
MATERIAL_RATE_ATOL_FMOL_S = 3e-14
ENERGY_BALANCE_ATOL_PJ_S = 1e-10
POWER_COMPARISON_ATOL_PJ_S = 3e-12
ACCOUNTING_RTOL = 2e-12


@dataclass(frozen=True)
class GeometryEvidence:
    source_review_json: str
    prepared_manifest_json: str
    input_json: str
    report_json: str
    caller_acceptance: object


@dataclass(frozen=True)
class Request:
    constructor_request: constructor.Request
    constructor_candidate: constructor.Candidate
    geometry_evidence: GeometryEvidence
    declaration: object
    identity: str


@dataclass(frozen=True)
class Preparation:
    request_identity: str
    physical_preparation: physical.Preparation
    conversions: object
    initial_snapshot: object
    provenance: object
    identity: str


class BridgeRejected(ValueError):
    def __init__(self, reason, *, stage, original=None, partial=None):
        super().__init__("Partition physiology bridge refused at " + stage + ": " + str(reason))
        self.stage, self.original, self.partial = stage, original, partial


plain, digest, freeze = constructor.plain, constructor.digest, constructor.freeze


def _json_record(text, limit):
    if type(text) is not str or len(text.encode("utf-8")) > limit:
        raise ValueError("Complete bounded original JSON evidence required")

    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError("Duplicate JSON evidence key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("Nonfinite JSON evidence constant: " + value)

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def _source_review(proof):
    if DRAFT_ONLY or any(
        value is None
        for value in (
            UPSTREAM_SOURCE_REVIEW_SHA256,
            UPSTREAM_PREPARED_MANIFEST_SHA256,
            UPSTREAM_REFERENCE_SHA256,
            UPSTREAM_SOURCE_REVIEW_STATUS,
        )
    ):
        raise BridgeRejected(
            (
                "Upstream explicit-ECM source disposition/successor pins are "
                "pending; draft cannot prepare physiology"
            ),
            stage="upstream_source_review",
            partial=dict(freeze_permitted=False, scientific_evaluation_permitted=False),
        )
    if type(proof) is not GeometryEvidence:
        raise ValueError("Complete accepted upstream geometry evidence required")
    if (
        hashlib.sha256(proof.source_review_json.encode("utf-8")).hexdigest()
        != UPSTREAM_SOURCE_REVIEW_SHA256
    ):
        raise ValueError("Changed upstream source review bytes")
    if (
        hashlib.sha256(proof.prepared_manifest_json.encode("utf-8")).hexdigest()
        != UPSTREAM_PREPARED_MANIFEST_SHA256
    ):
        raise ValueError("Changed explicit upstream prepared manifest bytes")
    review = _json_record(proof.source_review_json, 8 * 2**20)
    if (
        review["kind"] != "cells.source_static_review@1"
        or review["verdict"] != UPSTREAM_SOURCE_REVIEW_STATUS
        or review["blockers"] != []
        or review["packet"]["manifest_sha256"] != UPSTREAM_PREPARED_MANIFEST_SHA256
        or review["reviewed_scientific_source_sha256"][
            "source/validation/geometry/stable_seed_explicit_ecm_partition_reference.py"
        ]
        != UPSTREAM_REFERENCE_SHA256
    ):
        raise ValueError("An accepted source disposition without blockers is required")
    manifest = _json_record(proof.prepared_manifest_json, 8 * 2**20)
    if (
        manifest["file_sha256"][
            "source/validation/geometry/stable_seed_explicit_ecm_partition_reference.py"
        ]
        != UPSTREAM_REFERENCE_SHA256
    ):
        raise ValueError("Reference must be from the explicit reviewed constructor successor")
    return review


def _pins():
    root = Path(__file__).resolve().parents[3]
    for rel, pin in SOURCE_PINS.items():
        if hashlib.sha256((root / rel).read_bytes()).hexdigest() != pin:
            raise ValueError("Changed frozen passive initial-physiology source: " + rel)


def _accepted_geometry(request, candidate, proof):
    _source_review(proof)
    if type(request) is not constructor.Request or type(candidate) is not constructor.Candidate:
        raise ValueError("Complete owned positive partition request/candidate required")
    constructor.validate(request, candidate)
    incoming = _json_record(proof.input_json, 64 * 2**20)
    report = _json_record(proof.report_json, 128 * 2**20)
    if digest(incoming) != digest(dict(request=request, candidate=candidate)):
        raise ValueError(
            "Original complete positive constructor input is required, without controls"
        )
    input_sha = hashlib.sha256(proof.input_json.encode("utf-8")).hexdigest()
    report_sha = hashlib.sha256(proof.report_json.encode("utf-8")).hexdigest()
    accepted = proof.caller_acceptance
    constructor._keys(
        accepted,
        {"kind", "caller", "constructor_identity", "input_sha256", "report_sha256", "scope"},
        "explicit geometry acceptance",
    )
    if type(accepted["caller"]) is not str or not accepted["caller"]:
        raise ValueError("Named caller must accept the complete independent geometry report")
    expected = dict(
        kind="caller_accepts_complete_positive_explicit_cell_bath_geometry@1",
        caller=accepted["caller"],
        constructor_identity=candidate.identity,
        input_sha256=input_sha,
        report_sha256=report_sha,
        scope="geometry_only_no_physical_native_or_trajectory_admission",
    )
    if digest(accepted) != digest(expected):
        raise ValueError("Changed accepted geometry identity, bytes or scope")
    if (
        report["status"] != "complete"
        or report["baseline_passed"] is not True
        or report["candidate_passed"] is not True
        or report["control_detected"] is not False
        or report["controls"] != []
        or report.get("runtime_capture_failed", False) is not False
        or report["baseline"]["passed"] is not True
        or report["baseline"]["complete_constructor_and_geometry_arrays"] is not True
    ):
        raise ValueError(
            "Complete positive constructor baseline, never generic control credit, required"
        )
    truth = report["reference"]
    for field in ("construction", "owner_maps", "conservation", "provenance"):
        if digest(truth[field]) != digest(getattr(candidate, field)):
            raise ValueError(
                "Changed complete independently checked geometry/evidence field: " + field
            )
    if digest(truth["partition_input"]) != digest(candidate.partition_request.declaration):
        raise ValueError("Changed independently checked partition coordinates/owners")
    g = candidate.partition_binding.geometry
    quantities = report["baseline"]["geometry"]["full_precision_quantities"]
    if len(quantities) != 4 * len(g["regions"]) + 6 * len(g["edges"]) + 5 * len(g["faces"]):
        raise ValueError("Incomplete geometric scalar/certificate inventory")
    runtime = report["runtime_origin"]
    if (
        runtime["input_sha256"] != input_sha
        or runtime["source_sha256"] != UPSTREAM_REFERENCE_SHA256
        or runtime["files"].get(runtime["source"]) != UPSTREAM_REFERENCE_SHA256
        or runtime["production_and_scientific_imports_denied"] is not True
        or runtime["production_or_scientific_modules_loaded"] != []
        or runtime["file_errors"] != {}
        or runtime["mapped_file_errors"] != []
        or type(runtime["pid"]) is not int
        or type(runtime["parent_pid"]) is not int
        or runtime["pid"] <= 0
        or runtime["parent_pid"] <= 0
        or runtime["pid"] == runtime["parent_pid"]
    ):
        raise ValueError("Complete clean actual constructor reference-worker provenance required")
    manifest = _json_record(proof.prepared_manifest_json, 8 * 2**20)
    source_root = Path(runtime["source"]).parents[2]
    reference_sources = (
        "validation/geometry/stable_seed_explicit_ecm_partition_reference.py",
        "validation/geometry/stable_seed_explicit_ecm_partition_geometry_reference.py",
        "validation/geometry/conservative_polygon_geometry_reference.py",
        "validation/geometry/stable_geometry_primitives_reference.py",
    )
    for rel in reference_sources:
        if runtime["files"].get(str(source_root / rel)) != manifest["file_sha256"]["source/" + rel]:
            raise ValueError("Incomplete changed independent geometry runtime source: " + rel)
    return dict(
        source_review_sha256=UPSTREAM_SOURCE_REVIEW_SHA256,
        prepared_manifest_sha256=UPSTREAM_PREPARED_MANIFEST_SHA256,
        reference_sha256=UPSTREAM_REFERENCE_SHA256,
        input_sha256=input_sha,
        report_sha256=report_sha,
        accepted_geometry_identity=candidate.identity,
        public_hash_consistency_alone_is_scientific_review=False,
    )


def _number(value, *, positive=False, nonnegative=False):
    if (
        type(value) is not float
        or not math.isfinite(value)
        or (positive and value <= 0)
        or (nonnegative and value < 0)
    ):
        raise ValueError("Explicit finite binary64 physical value with required sign is needed")
    return value


def _species_values(value, species, *, positive=False):
    constructor._keys(value, species, "complete species values")
    return {
        name: _number(value[name], positive=positive, nonnegative=not positive) for name in species
    }


def _rows(value, ids, fields, label):
    if not isinstance(value, (tuple, list)) or len(value) != len(ids):
        raise ValueError("Complete caller owner rows required: " + label)
    result = {}
    for row in value:
        constructor._keys(row, fields, label)
        if row["id"] in result:
            raise ValueError("Duplicate caller owner: " + label)
        result[row["id"]] = row
    if set(result) != set(ids):
        raise ValueError("Unknown/missing caller owner: " + label)
    return result


def _declaration(value, candidate):
    constructor._keys(
        value,
        {
            "kind",
            "opted_in_law",
            "opted_in_family",
            "species",
            "temperature_K",
            "cells",
            "baths",
            "membranes",
            "faces",
            "electrical_policy",
            "concentration_policy",
            "constitutive_policy",
            "experiment",
            "execution",
            "prior_state_policy",
            "provenance",
        },
        "complete caller physiology",
    )
    if (
        value["kind"] != INPUT_KIND
        or value["opted_in_law"] != LAW_ID
        or value["opted_in_family"] != "resolved_tissue@1"
        or value["concentration_policy"]
        != "mM_times_admitted_binary64_pL_round_once_readback_defects_retained@1"
        or value["constitutive_policy"]
        != "caller_D_and_P_agree_with_existing_D_over_geometry_path@1"
    ):
        raise ValueError(
            "Explicit existing passive family and concentration/constitutive policies required"
        )
    constructor._keys(
        value["prior_state_policy"],
        {"kind", "provided_prior_state_or_operators"},
        "prior-state policy",
    )
    if (
        value["prior_state_policy"]["kind"]
        != "fresh_time_zero_no_cached_state_or_operator_adoption@1"
        or value["prior_state_policy"]["provided_prior_state_or_operators"] is not None
    ):
        raise ValueError(
            "No old state, operator, membrane, concentration or electrical cache may be adopted"
        )
    if not isinstance(value["species"], (tuple, list)) or not 2 <= len(value["species"]) <= 8:
        raise ValueError("Two to eight explicit passive species are required")
    species = []
    for row in value["species"]:
        constructor._keys(row, {"id", "valence"}, "species")
        physical.geometry.exact._id(row["id"])
        if type(row["valence"]) is not int or abs(row["valence"]) > 8:
            raise ValueError("Explicit supported integer valence required")
        species.append(row["id"])
    if len(set(species)) != len(species):
        raise ValueError("Distinct species IDs required")
    _number(value["temperature_K"], positive=True)
    if not isinstance(value["provenance"], constructor.Mapping) or not value["provenance"]:
        raise ValueError("Explicit caller physical provenance required")
    g = candidate.partition_binding.geometry
    for family, ids, extra in (
        ("cells", g["cell_ids"], set()),
        ("baths", g["bath_ids"], {"reservoir"}),
    ):
        for row in _rows(value[family], ids, {"id", "concentration_mM"} | extra, family).values():
            _species_values(row["concentration_mM"], species, positive=True)
            if family == "baths" and row["reservoir"] is not False:
                raise ValueError("The finite-ECM law requires explicitly finite baths")
    membrane_rows = _rows(
        value["membranes"],
        [row["id"] for row in g["membranes"]],
        {
            "id",
            "cell_id",
            "bath_id",
            "specific_capacitance_F_per_m2",
            "permeability_m_per_s",
            "diffusivity_m2_per_s",
        },
        "membranes",
    )
    for actual in g["membranes"]:
        row = membrane_rows[actual["id"]]
        if (row["cell_id"], row["bath_id"]) != (actual["cell_id"], actual["bath_id"]):
            raise ValueError("Membrane caller owners disagree with actual geometry")
        _number(row["specific_capacitance_F_per_m2"], positive=True)
        _species_values(row["permeability_m_per_s"], species)
        _species_values(row["diffusivity_m2_per_s"], species)
    face_rows = _rows(
        value["faces"],
        [row["id"] for row in g["faces"]],
        {"id", "sender", "receiver", "diffusivity_m2_per_s"},
        "faces",
    )
    for actual in g["faces"]:
        row = face_rows[actual["id"]]
        if (row["sender"], row["receiver"]) != (actual["sender"], actual["receiver"]):
            raise ValueError("Face caller owners disagree with actual geometry")
        _species_values(row["diffusivity_m2_per_s"], species)
    electrical = value["electrical_policy"]
    constructor._keys(
        electrical,
        {"kind", "closure_law", "cells", "baths", "gauge_reference"},
        "initial electrical policy",
    )
    if (
        electrical["kind"] != "explicit_charge_anchors_fixed_backgrounds_and_finite_bath_gauge@1"
        or electrical["closure_law"] != "resolved_capacitor_components_current_continuity@1"
        or electrical["gauge_reference"] not in g["bath_ids"]
    ):
        raise ValueError(
            (
                "Explicit existing charge/current closure, charge anchors and one "
                "finite-bath gauge required"
            )
        )
    for family, ids, extra in (
        ("cells", g["cell_ids"], set()),
        ("baths", g["bath_ids"], {"boundary_potential_V"}),
    ):
        rows = _rows(
            electrical[family],
            ids,
            {"id", "initial_charge_C", "fixed_charge_equivalent_fmol"} | extra,
            "electrical " + family,
        )
        for row in rows.values():
            _number(row["initial_charge_C"])
            _number(row["fixed_charge_equivalent_fmol"])
            if family == "baths":
                _number(row["boundary_potential_V"])
                if row["id"] != electrical["gauge_reference"] and row["boundary_potential_V"] != 0:
                    raise ValueError(
                        "Only the declared finite-bath gauge can impose a nonzero potential"
                    )
    experiment = value["experiment"]
    constructor._keys(
        experiment,
        {"end_time", "observation_times", "membrane_controls", "junction_controls"},
        "explicit existing experiment",
    )
    _number(experiment["end_time"], positive=True)
    if (
        list(experiment["observation_times"]) != [0.0]
        or list(experiment["junction_controls"]) != []
    ):
        raise ValueError("This bridge evaluates only time zero, with no direct junctions")
    controls = _rows(
        [
            dict(id=row["membrane_id"], schedule=row["schedule"])
            for row in experiment["membrane_controls"]
        ],
        [row["id"] for row in g["membranes"]],
        {"id", "schedule"},
        "initial controls",
    )
    for row in experiment["membrane_controls"]:
        constructor._keys(row, {"membrane_id", "schedule"}, "initial membrane control")
    for row in controls.values():
        if len(row["schedule"]) != 1:
            raise ValueError("Only one explicit time-zero control value is supported")
        change = row["schedule"][0]
        constructor._keys(change, {"time", "availability"}, "initial control")
        _number(change["time"])
        _number(change["availability"], nonnegative=True)
        if change["time"] != 0 or change["availability"] > 1:
            raise ValueError("Initial controls must be explicit fractions at time zero")
    execution = value["execution"]
    constructor._keys(
        execution,
        {
            "dt",
            "capacity",
            "jit",
            "max_steps",
            "max_trace_bytes",
            "backend",
            "precision",
            "solver",
            "edge_capacity",
            "membrane_capacity",
            "material_balance_atol_fmol",
            "extracellular_capacity",
            "face_capacity",
            "field_solver",
        },
        "complete caller execution declaration",
    )
    if (
        execution["backend"] != "cpu"
        or execution["precision"] != "float64"
        or execution["jit"] is not False
        or execution["solver"] != "rk4"
        or execution["field_solver"] != "capacitive_reduction_gauged_damped_newton@1"
    ):
        raise ValueError(
            "Explicit existing CPU/float64/non-JIT passive execution identity required"
        )
    for key, expected in dict(
        capacity=len(g["cell_ids"]),
        extracellular_capacity=len(g["bath_ids"]),
        membrane_capacity=len(g["membranes"]),
        face_capacity=len(g["faces"]),
        edge_capacity=0,
    ).items():
        if type(execution[key]) is not int or execution[key] != expected:
            raise ValueError("This initial bridge requires complete compact owner axes: " + key)
    return freeze(plain(value))


def request_record(value):
    return (
        LAW_ID,
        value.constructor_request,
        value.constructor_candidate,
        value.geometry_evidence,
        value.declaration,
    )


def bind(constructor_request, candidate, proof, declaration):
    _accepted_geometry(constructor_request, candidate, proof)
    _pins()
    declared = _declaration(declaration, candidate)
    accepted = GeometryEvidence(
        proof.source_review_json,
        proof.prepared_manifest_json,
        proof.input_json,
        proof.report_json,
        freeze(plain(proof.caller_acceptance)),
    )
    value = Request(constructor_request, candidate, accepted, declared, "")
    return replace(value, identity=digest(request_record(value)))


def _ratio(value):
    return Fraction(int(value["numerator"]), int(value["denominator"]))


def _materialize(request, observer):
    d = request.declaration
    g = request.constructor_candidate.partition_binding.geometry
    species = [row["id"] for row in d["species"]]
    electrical = d["electrical_policy"]
    ledger = dict(events=[], concentrations=[], constitutive=[])
    rows = {
        family: {row["id"]: row for row in d[family]}
        for family in ("cells", "baths", "membranes", "faces")
    }
    anchors = {
        family: {row["id"]: row for row in electrical[family]} for family in ("cells", "baths")
    }
    regions = {row["id"]: row for row in g["regions"]}
    model = dict(
        id="resolved_tissue@1",
        species=plain(d["species"]),
        temperature_K=d["temperature_K"],
        cells=[],
        extracellular=[],
        membranes=[],
        junctions=[],
        faces=[],
        closure=dict(law=electrical["closure_law"], gauge_reference=electrical["gauge_reference"]),
    )
    exact = physical.geometry.exact

    def project(target, label, context):
        event = dict(
            sequence=len(ledger["events"]),
            stage=label,
            input_exact=plain(target),
            context=plain(context),
            returned=None,
        )
        ledger["events"].append(event)
        observer("conversion-input-" + str(event["sequence"]), event)
        returned, certificate = exact._rounded(target, label)
        event["returned"] = dict(
            value=returned, binary64_hex=returned.hex(), certificate=certificate
        )
        observer("conversion-return-" + str(event["sequence"]), event)
        return returned, certificate

    def record(family, row):
        ledger[family].append(row)
        observer("conversion-" + family + "-" + str(len(ledger[family]) - 1), row)

    for family, axis, output in (
        ("cells", g["cell_ids"], "cells"),
        ("baths", g["bath_ids"], "extracellular"),
    ):
        for name in axis:
            volume, certificate = project(
                _ratio(regions[name]["certificates"]["volume"]["exact"]) * 10**15,
                "initial_inventory_volume_pL",
                dict(owner_id=name),
            )
            amounts = {}
            for ion in species:
                concentration = rows[family][name]["concentration_mM"][ion]
                target = Fraction.from_float(concentration) * Fraction.from_float(volume)
                amount, proof = project(
                    target,
                    "caller_concentration_to_initial_fmol",
                    dict(
                        owner_id=name,
                        species=ion,
                        requested_concentration_mM=concentration,
                        admitted_volume_pL=volume,
                    ),
                )
                represented = Fraction.from_float(amount) / Fraction.from_float(volume)
                amounts[ion] = amount
                record(
                    "concentrations",
                    dict(
                        owner_id=name,
                        species=ion,
                        requested_concentration_mM=concentration,
                        admitted_volume_pL=volume,
                        volume_certificate=certificate,
                        amount_fmol=amount,
                        amount_certificate=proof,
                        represented_concentration_mM_exact=plain(represented),
                        concentration_defect_mM_exact=plain(
                            represented - Fraction.from_float(concentration)
                        ),
                        concentration_readback_exactly_claimed=False,
                    ),
                )
            row = dict(
                plain(anchors[family][name]),
                volume_pL={"$geometry": "region_volume_pL", "region_id": name},
                initial_amount_fmol=amounts,
            )
            if family == "baths":
                row["reservoir"] = rows[family][name]["reservoir"]
            model[output].append(row)
    thickness = Fraction.from_float(g["membrane_thickness_m"])
    for patch in g["membranes"]:
        row = rows["membranes"][patch["id"]]
        permeability = {}
        for ion in species:
            diffusion = row["diffusivity_m2_per_s"][ion]
            projected, certificate = project(
                Fraction.from_float(diffusion) / thickness,
                "explicit_membrane_D_over_path",
                dict(
                    membrane_id=patch["id"],
                    species=ion,
                    caller_permeability_m_per_s=row["permeability_m_per_s"][ion],
                    diffusivity_m2_per_s=diffusion,
                    path_m=g["membrane_thickness_m"],
                ),
            )
            if projected.hex() != row["permeability_m_per_s"][ion].hex():
                raise ValueError("Explicit caller P and D disagree under the existing D/path law")
            record(
                "constitutive",
                dict(
                    membrane_id=patch["id"],
                    species=ion,
                    caller_permeability_m_per_s=projected,
                    diffusivity_m2_per_s=diffusion,
                    path_m=g["membrane_thickness_m"],
                    certificate=certificate,
                ),
            )
            permeability[ion] = {
                "$geometry": "membrane_permeability_m_per_s",
                "membrane_id": patch["id"],
                "diffusivity_m2_per_s": diffusion,
            }
        model["membranes"].append(
            dict(
                id=patch["id"],
                inside=patch["cell_id"],
                outside=patch["bath_id"],
                law="constant_field@1",
                area_m2={"$geometry": "membrane_area_m2", "membrane_id": patch["id"]},
                capacitance_F={
                    "$geometry": "membrane_capacitance_F",
                    "membrane_id": patch["id"],
                    "specific_capacitance_F_per_m2": row["specific_capacitance_F_per_m2"],
                },
                permeability_m_per_s=permeability,
            )
        )
    for face in g["faces"]:
        model["faces"].append(
            dict(
                id=face["id"],
                sender=face["sender"],
                receiver=face["receiver"],
                law="logmean_electrodiffusion@1",
                area_m2={"$geometry": "face_area_m2", "face_id": face["id"]},
                length_m={"$geometry": "face_length_m", "face_id": face["id"]},
                diffusivity_m2_per_s=plain(rows["faces"][face["id"]]["diffusivity_m2_per_s"]),
            )
        )
    raw = dict(
        kind=physical.REQUEST_KIND,
        opted_in_law=physical.LAW_ID,
        geometry_identity=request.constructor_candidate.partition_binding.identity,
        target_model_id="resolved_tissue@1",
        definition_template=dict(
            schema_version=1,
            model=model,
            experiment=plain(d["experiment"]),
            execution=plain(d["execution"]),
        ),
        provenance=dict(
            caller=plain(d["provenance"]),
            bridge_law=LAW_ID,
            parameter_defaults_inserted=False,
            charge_anchors_or_fixed_backgrounds_inferred=False,
            concentration_policy=d["concentration_policy"],
            constitutive_policy=d["constitutive_policy"],
        ),
    )
    return raw, ledger


def _initial_accounting(state, layout, values, derivative, model, np):
    from cells.numerics.extracellular_field import scatter

    r = values.rates
    n = layout.active.size
    cell = derivative.amount_increment + scatter(
        r.membrane_flux_fmol_s, derivative.amount_increment, (layout.membrane_cell,), xp=np
    )
    cell += scatter(
        r.junction_flux_fmol_s, derivative.amount_increment, (layout.junction_sender,), xp=np
    ) - scatter(
        r.junction_flux_fmol_s, derivative.amount_increment, (layout.junction_receiver,), xp=np
    )
    outside = derivative.extracellular_amount_increment - scatter(
        r.membrane_flux_fmol_s,
        derivative.extracellular_amount_increment,
        (layout.membrane_outside,),
        xp=np,
    )
    outside += (
        scatter(
            r.face_flux_fmol_s,
            derivative.extracellular_amount_increment,
            (layout.face_sender,),
            xp=np,
        )
        - scatter(
            r.face_flux_fmol_s,
            derivative.extracellular_amount_increment,
            (layout.face_receiver,),
            xp=np,
        )
        - derivative.reservoir_supplied
    )
    total = (
        derivative.amount_increment.sum(axis=1)
        + derivative.extracellular_amount_increment.sum(axis=1)
        - derivative.reservoir_supplied.sum(axis=1)
    )
    phi = values.potential_V
    q = np.r_[layout.initial_cell_charge_C, layout.initial_outside_charge_C]
    cap = layout.field_capacitor_matrix @ phi
    charge = cap - q
    charge_bound = model.field.CHARGE_ATOL_C + model.field.CHARGE_RTOL * np.maximum(
        np.abs(q), np.abs(cap)
    )
    ionic = model.CHARGE_PER_FMOL * np.sum(
        layout.valence
        * np.c_[derivative.amount_increment, derivative.extracellular_amount_increment],
        axis=0,
    )
    capacitor_rate = np.zeros_like(ionic)
    patch_rate = layout.membrane_capacitance * values.membrane_voltage_rate_V_s
    np.add.at(capacitor_rate, layout.membrane_cell, patch_rate)
    np.add.at(capacitor_rate, n + layout.membrane_outside, -patch_rate)
    local_charge_rate = capacitor_rate - ionic
    current_scale = max(
        float(np.max(np.abs(r.face_current_A), initial=0)),
        float(np.max(np.abs(r.junction_current_A), initial=0)),
    )
    current_bound = model.field.CURRENT_ATOL_A + model.field.CURRENT_RTOL * current_scale
    ci, co = model.physical_amounts(state, layout)
    ci = ci / layout.volume
    co = co / layout.extracellular_volume
    chemical = (
        1e-3
        * model.R
        * layout.temperature
        * (np.sum(np.log(ci) * r.cell_rate_fmol_s) + np.sum(np.log(co) * r.outside_rate_fmol_s))
    )
    capacitor_power = 1e12 * np.sum(
        layout.membrane_capacitance * r.membrane_voltage_V * values.membrane_voltage_rate_V_s
    )
    dissipation = sum(
        np.sum(getattr(r, name + "_dissipation_pJ_s")) for name in ("membrane", "junction", "face")
    )
    energy = (
        chemical
        + capacitor_power
        + dissipation
        - values.reservoir_power_pJ_s
        - values.electrode_power_pJ_s
    )
    checks = dict(
        local_material_rate_fmol_s=cell,
        outside_material_rate_fmol_s=outside,
        global_material_rate_fmol_s=total,
        node_charge_residual_C=charge,
        node_charge_bound_C=charge_bound,
        local_charge_rate_residual_A=local_charge_rate,
        current_constraint_bound_A=current_bound,
        all_component_current_residual_A=values.component_current_residual_A,
        global_charge_rate_residual_A=np.sum(ionic) + np.sum(values.electrode_current_A),
        chemical_energy_rate_pJ_s=chemical,
        capacitor_energy_rate_pJ_s=capacitor_power,
        dissipation_pJ_s=dissipation,
        energy_balance_pJ_s=energy,
    )
    valid = all(np.isfinite(value).all() for value in checks.values())
    valid &= all(
        np.all(np.abs(value) <= MATERIAL_RATE_ATOL_FMOL_S) for value in (cell, outside, total)
    )
    valid &= np.all(np.abs(charge) <= charge_bound) and np.all(
        np.abs(local_charge_rate) <= current_bound
    )
    valid &= (
        np.all(np.abs(values.component_current_residual_A) <= current_bound)
        and abs(checks["global_charge_rate_residual_A"]) <= current_bound
    )
    valid &= abs(energy) <= ENERGY_BALANCE_ATOL_PJ_S
    for name, expected in (
        ("chemical_energy_rate_pJ_s", chemical),
        ("capacitor_energy_rate_pJ_s", capacitor_power),
        ("dissipation_pJ_s", dissipation),
        ("energy_balance_pJ_s", energy),
    ):
        valid &= np.allclose(
            getattr(values, name), expected, rtol=ACCOUNTING_RTOL, atol=POWER_COMPARISON_ATOL_PJ_S
        )
    return checks, bool(valid)


def _initial_snapshot(admitted, observer):
    import numpy as np

    from cells.core import surface_tissue_spec as schema
    from cells.core.schedule import control_values
    from cells.models import surface_tissue as model

    def arrays(value):
        if hasattr(value, "_asdict"):
            return {key: arrays(item) for key, item in value._asdict().items()}
        if isinstance(value, dict):
            return {key: arrays(item) for key, item in value.items()}
        array = np.asarray(value)
        if array.dtype.kind not in "bif" or (array.dtype.kind == "f" and array.dtype.itemsize != 8):
            raise ValueError("Complete real/bool/integer float64 initial arrays required")
        return dict(
            kind="typed_C_order_array_bytes@1",
            dtype=array.dtype.str,
            shape=list(array.shape),
            data_hex=array.tobytes(order="C").hex(),
        )

    spec = schema.parse(admitted.definition)
    state, layout = model.initial_values(spec)
    table = control_values(spec, [0.0])
    control = type(table)(*(value[0] for value in table))
    snapshot = dict(
        time_s=0.0,
        state=arrays(state),
        layout=arrays(layout),
        control=arrays(control),
        time_advanced=False,
    )
    observer("initial_state_layout_control", snapshot)
    values = model.field_values(state, control, layout, xp=np)
    snapshot["field"] = arrays(values)
    observer("initial_field_return", snapshot["field"])
    derivative = model.derivative_from_field(values, layout, xp=np)
    snapshot["rhs"] = arrays(derivative)
    observer("initial_RHS_return", snapshot["rhs"])
    checks, valid = _initial_accounting(state, layout, values, derivative, model, np)
    snapshot["accounting"] = arrays(checks)
    observer("initial_accounting_return", snapshot["accounting"])
    diagnostics = model.check_values(state, spec)
    snapshot["state_diagnostics"] = diagnostics
    observer("initial_state_diagnostics_return", diagnostics)
    if not (
        bool(values.converged)
        and bool(values.rates.valid)
        and bool(model.domain_valid(state, layout, layout.active, xp=np))
        and valid
    ):
        raise ValueError(
            "Complete initial field/RHS/charge/material/energy domain or accounting failed"
        )
    snapshot.update(
        initial_accounting_passed=True,
        independent_physical_validation_required=True,
        solver_trajectory_executed=False,
    )
    return snapshot


def preparation_record(value):
    return (
        LAW_ID,
        value.request_identity,
        value.physical_preparation,
        value.conversions,
        value.initial_snapshot,
        value.provenance,
    )


def prepare(request, *, observer=None):
    partial = dict(stage="upstream_source_review", request=plain(request))

    def retain(stage, value):
        partial[stage] = plain(value)
        if observer is not None:
            observer(stage, plain(value))

    try:
        if type(request) is not Request:
            raise ValueError("Complete owned physiology request required")
        rebuilt = bind(
            request.constructor_request,
            request.constructor_candidate,
            request.geometry_evidence,
            request.declaration,
        )
        if digest(rebuilt) != digest(request):
            raise ValueError("Changed complete physiology request or seal")
        partial["stage"] = "explicit_physical_materialization"
        raw, ledger = _materialize(request, retain)
        retain("physical_materialization_input", raw)
        retain("concentration_and_constitutive_conversions", ledger)
        partial["stage"] = "existing_finite_ECM_physical_admission"
        candidate = request.constructor_candidate
        admitted = physical.prepare(candidate.partition_request, candidate.partition_binding, raw)
        retain("physical_preparation_return", admitted)
        partial["stage"] = "complete_time_zero_state_field_RHS_accounting"
        snapshot = _initial_snapshot(admitted, retain)
        provenance = dict(
            kind="cells.explicit_partition_initial_physiology_preparation@1",
            law=LAW_ID,
            geometry_identity=candidate.identity,
            upstream_source_review_sha256=UPSTREAM_SOURCE_REVIEW_SHA256,
            upstream_prepared_manifest_sha256=UPSTREAM_PREPARED_MANIFEST_SHA256,
            caller_physical_provenance=plain(request.declaration["provenance"]),
            source_pins=SOURCE_PINS,
            physical_model_prepared=True,
            initial_field_RHS_and_accounting_prepared=True,
            parameter_defaults_inserted=False,
            charge_or_fixed_background_inferred=False,
            native_equivalence=False,
            ordinary_ECM_loop_ready=False,
            time_advanced=False,
            solver_trajectory_executed=False,
            independent_geometry_or_physical_qualification_inherited=False,
        )
        value = Preparation(
            request.identity,
            admitted,
            freeze(plain(ledger)),
            freeze(plain(snapshot)),
            freeze(plain(provenance)),
            "",
        )
        return replace(value, identity=digest(preparation_record(value)))
    except Exception as error:
        raise BridgeRejected(
            str(error),
            stage=partial["stage"],
            original=dict(
                type=type(error).__name__,
                reason=str(error),
                stage=getattr(error, "stage", None),
                code=getattr(error, "code", None),
                detail=plain(getattr(error, "detail", None)),
                trial=plain(getattr(error, "trial", None)),
                partial=plain(getattr(error, "partial", None)),
            ),
            partial=partial,
        ) from error


def require_advancement(_value):
    raise ValueError(
        (
            "This bridge prepares time-zero physiology only; no "
            "advancing/native/ordinary-loop admission"
        )
    )
