"""Independent initial worker successor for explicit numerical clock controls; no advancing."""

import argparse
import ast
import hashlib
import importlib.abc
import json
import math
import os
import struct
import sys
import traceback
from copy import deepcopy
from decimal import localcontext
from pathlib import Path

PARENT_INITIAL_REVIEW_SHA256 = "e055f0ff664553e6c6fdf02fc777beb31e6206b3f99fead6835d088f8dd63249"
PARENT_INITIAL_MANIFEST_SHA256 = "92caecd20cba1973336f14a005492a144393740fae3d6cd3be32a2636a8fcf26"
REFINEMENT_CALLERS_SHA256 = "d5537d58ca38f022e30b9fb5b3471b54aa6914ac0a0f512fd4c9e9984eae3a8b"
LAW = "cells_explicit_seed_partition_passive_initial_physiology_bridge@1"
PREFIX = "validation/geometry/stable_seed_partition_physiology_bridge_"
UPSTREAM_SOURCE_REVIEW_SHA256 = "a8c09e4245079f55784e62d79e62d05e616dc5a665de5fb62b5235365b6078c7"
UPSTREAM_SOURCE_REVIEW_STATUS = "clear_for_prospective_guarded_qualification_preparation"
UPSTREAM_PREPARED_MANIFEST_SHA256 = (
    "5b6257f7a8f0f8a51b6903fb55aba11fe34c0934f2e10351e377a42eee81b406"
)
UPSTREAM_GEOMETRY_REFERENCE_SHA256 = (
    "5b2240bf02166ae4bc73e03a669611d3328448fe1dd5824919ccbf59dc8f702c"
)
DRAFT_ONLY = False
BRIDGE_CORE_SHA256 = "31959e49ec266092556dc67c755d28105e24bdf6789079fd766c7c5e4f3566ca"
CALLERS_SHA256 = "4be058c5f6211a9a489c709ee95f371d3dd7bf0ba03c8834e789c0be3554c09f"
CONTROLS_SHA256 = "762fbb40bd9121b21167cd1ab325d65beafe79542fb2e03af6dcd8b2960e5f83"
HELPER_PINS = {
    PREFIX + "scalar_reference.py": (
        "72ee58f17248dfa7592a4ff61bc564de1e769b08542648da577376400b837e75"
    ),
    PREFIX + ("field_reference.py"): (
        "84f638bd719dcf6e275a4d16da8faf80d6e8088f5c72f99a61226008f962b36b"
    ),
    PREFIX + ("initial_reference.py"): (
        "8260ceae5bea6d9a1052679845e6baffa6084f81dc2e1c1d1c497cac69da85cf"
    ),
    PREFIX + ("declarations.py"): (
        "337426949e4d8fd82f23b81c1a82830458919c34a0ef1298beda15283ed9f3b7"
    ),
    ("validation/geometry/stable_seed_explicit_ecm_partition_geometry_reference.py"): (
        "91e6d01931bb5856b2604c4b7348b3cf6d70e2737a75784b008495e6b025d251"
    ),
    ("validation/geometry/conservative_polygon_geometry_reference.py"): (
        "5b3e621e75ebf1c539315e12ab213c7e0f6a019856db55121bf0f2f95acf06f8"
    ),
    ("validation/geometry/stable_geometry_primitives_reference.py"): (
        "f0ee2a5ec330457d5e372c636dc63b7470922b100d4df00cab961c1bf4ab7569"
    ),
    ("validation/geometry/stable_seed_partition_advance_refinement_declarations.py"): (
        "909ffec06dacd701721cfa58c1d9643f1a2cdf1723c24720a9af82b3405d676e"
    ),
}
DENIED = {"cells", "betse", "jax", "jaxlib", "PIL", "torch"}


class NoProduction(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in DENIED:
            raise ImportError("Independent initial worker denies " + fullname)


if any((name.split(".")[0] in DENIED for name in sys.modules)):
    raise RuntimeError("Independent physical worker requires a fresh nonproduction process")
sys.meta_path.insert(0, NoProduction())


class ReferenceRejected(ValueError):
    def __init__(self, code, *, stage, detail=None):
        super().__init__(code)
        self.code, self.stage, self.detail = (code, stage, detail)


def require(value, reason, *, stage="complete_independent_input"):
    if not value:
        raise ReferenceRejected(reason, stage=stage)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    if type(value) is float:
        return dict(binary64_hex=value.hex())
    if type(value) is dict:
        return {k: canonical(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical(v) for v in value]
    return value


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(canonical(value)).encode()).hexdigest()


def json_digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def parse(text, *, limit=128 * 2**20):
    require(type(text) is str and len(text.encode()) <= limit, "bounded_original_JSON")

    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "duplicate_JSON_key")
            result[key] = value
        return result

    def constant(value):
        raise ReferenceRejected("nonfinite_JSON_constant", stage="JSON", detail=value)

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def keys(value, expected, label):
    require(type(value) is dict and set(value) == set(expected), "complete_fields:" + label)


def gate(request):
    if DRAFT_ONLY or any(
        (
            pin is None
            for pin in (
                UPSTREAM_SOURCE_REVIEW_SHA256,
                UPSTREAM_SOURCE_REVIEW_STATUS,
                UPSTREAM_PREPARED_MANIFEST_SHA256,
                UPSTREAM_GEOMETRY_REFERENCE_SHA256,
            )
        )
    ):
        raise ReferenceRejected(
            "upstream_source_review_pending",
            stage="upstream_source_review",
            detail=dict(freeze_permitted=False, scientific_evaluation_permitted=False),
        )
    proof = request["geometry_evidence"]
    require(
        hashlib.sha256(proof["source_review_json"].encode()).hexdigest()
        == UPSTREAM_SOURCE_REVIEW_SHA256,
        ("source_review_bytes"),
    )
    require(
        hashlib.sha256(proof["prepared_manifest_json"].encode()).hexdigest()
        == UPSTREAM_PREPARED_MANIFEST_SHA256,
        ("upstream_manifest_bytes"),
    )
    review = parse(proof["source_review_json"])
    require(
        review["kind"] == "cells.source_static_review@1"
        and review["verdict"] == UPSTREAM_SOURCE_REVIEW_STATUS
        and (review[("blockers")] == [])
        and (review[("packet")][("manifest_sha256")] == UPSTREAM_PREPARED_MANIFEST_SHA256)
        and (
            review[("reviewed_scientific_source_sha256")][
                ("source/validation/geometry/stable_seed_explicit_ecm_partition_reference.py")
            ]
            == UPSTREAM_GEOMETRY_REFERENCE_SHA256
        ),
        ("accepted_source_review_without_blockers"),
    )


def source_pins():
    root = Path(__file__).resolve().parents[2]
    require(
        sha(root / "src/cells/processes/stable_seed_partition_physiology_bridge.py")
        == BRIDGE_CORE_SHA256,
        ("changed_bridge_source_metadata"),
    )
    for rel, pin in HELPER_PINS.items():
        require(sha(root / rel) == pin, "changed_independent_helper:" + rel)
    for name, pin in (("callers", CALLERS_SHA256), ("controls", CONTROLS_SHA256)):
        require(sha(root / (PREFIX + name + ".json")) == pin, "changed_caller_control_document")
    require(
        sha(root / "validation/geometry/stable_seed_partition_advance_refinement_callers.json")
        == REFINEMENT_CALLERS_SHA256,
        ("changed_explicit_clock_control_document"),
    )
    return root


def parent_initial_review(payload, partial):
    text = payload["parent_initial_source_review_json"]
    require(
        type(text) is str
        and hashlib.sha256(text.encode()).hexdigest() == PARENT_INITIAL_REVIEW_SHA256,
        ("exact_parent_initial_source_review"),
    )
    review = parse(text)
    partial["parent_initial_source_review"] = review
    require(
        review["kind"] == "cells.source_static_review@1"
        and review["verdict"] == ("clear_for_prospective_guarded_qualification_preparation")
        and (review[("blockers")] == [])
        and (review[("packet")][("manifest_sha256")] == PARENT_INITIAL_MANIFEST_SHA256),
        ("accepted_parent_initial_source_scope"),
    )


def authenticate(payload, partial):
    keys(
        payload,
        {"case_id", "request", "preparation"}
        | ({"controls"} if "controls" in payload else set())
        | {("numerical_control_id"), ("parent_initial_source_review_json")},
        ("payload"),
    )
    request = payload["request"]
    keys(
        request,
        {
            "constructor_request",
            "constructor_candidate",
            "geometry_evidence",
            ("declaration"),
            ("identity"),
        },
        ("bridge request"),
    )
    gate(request)
    parent_initial_review(payload, partial)
    root = source_pins()
    proof = request["geometry_evidence"]
    keys(
        proof,
        {
            "source_review_json",
            "prepared_manifest_json",
            "input_json",
            "report_json",
            ("caller_acceptance"),
        },
        ("geometry proof"),
    )
    constructor = request["constructor_candidate"]
    original = parse(proof["input_json"])
    require(
        digest(original)
        == digest(dict(request=request["constructor_request"], candidate=constructor)),
        ("complete_original_positive_geometry_input"),
    )
    report = parse(proof["report_json"])
    partial["original_geometry_report"] = report
    require(
        report["status"] == "complete"
        and report["baseline_passed"] is True
        and (report[("candidate_passed")] is True)
        and (report[("control_detected")] is False)
        and (report[("controls")] == [])
        and (not report.get(("runtime_capture_failed"), False)),
        ("positive_geometry_baseline_no_control_substitution"),
    )
    require(
        report["baseline"]["complete_constructor_and_geometry_arrays"] is True,
        ("complete_independent_geometry_inventory"),
    )
    geometry = parse(constructor["partition_binding"]["geometry_json"])
    require(json_digest(geometry) == constructor["partition_binding"]["identity"], "geometry_seal")
    truth = report["reference"]
    for field in ("construction", "owner_maps", "conservation", "provenance"):
        require(digest(truth[field]) == digest(constructor[field]), "geometry_evidence:" + field)
    require(
        digest(truth["partition_input"])
        == digest(parse(constructor["partition_request"][("declaration_json")])),
        ("complete_independent_partition_input"),
    )
    require(
        len(report["baseline"]["geometry"]["full_precision_quantities"])
        == 4 * len(geometry[("regions")])
        + 6 * len(geometry[("edges")])
        + 5 * len(geometry[("faces")]),
        ("complete_geometric_scalar_certificates"),
    )
    runtime = report["runtime_origin"]
    require(
        runtime["source_sha256"] == UPSTREAM_GEOMETRY_REFERENCE_SHA256
        and runtime[("input_sha256")] == hashlib.sha256(proof[("input_json")].encode()).hexdigest()
        and (runtime[("production_and_scientific_imports_denied")] is True)
        and (runtime[("production_or_scientific_modules_loaded")] == [])
        and (runtime[("file_errors")] == {})
        and (runtime[("mapped_file_errors")] == [])
        and (type(runtime[("pid")]) is int)
        and (type(runtime[("parent_pid")]) is int)
        and (runtime[("pid")] > 0)
        and (runtime[("parent_pid")] > 0)
        and (runtime[("pid")] != runtime[("parent_pid")]),
        ("complete_actual_geometry_worker_origin"),
    )
    manifest = parse(proof["prepared_manifest_json"])
    worker_root = Path(runtime["source"]).parents[2]
    for rel in (
        "validation/geometry/stable_seed_explicit_ecm_partition_reference.py",
        ("validation/geometry/stable_seed_explicit_ecm_partition_geometry_reference.py"),
        ("validation/geometry/conservative_polygon_geometry_reference.py"),
        ("validation/geometry/stable_geometry_primitives_reference.py"),
    ):
        require(
            runtime["files"].get(str(worker_root / rel))
            == manifest["file_sha256"]["source/" + rel],
            ("complete_geometry_runtime_source:") + rel,
        )
    acceptance = proof["caller_acceptance"]
    require(
        type(acceptance["caller"]) is str and bool(acceptance["caller"]),
        ("named_geometry_acceptance"),
    )
    require(
        digest(acceptance)
        == digest(
            dict(
                kind=("caller_accepts_complete_positive_explicit_cell_bath_geometry@1"),
                caller=acceptance[("caller")],
                constructor_identity=constructor[("identity")],
                input_sha256=hashlib.sha256(proof[("input_json")].encode()).hexdigest(),
                report_sha256=hashlib.sha256(proof[("report_json")].encode()).hexdigest(),
                scope=("geometry_only_no_physical_native_or_trajectory_admission"),
            )
        ),
        ("geometry_acceptance_scope"),
    )
    require(
        request["identity"]
        == digest(
            [LAW, request["constructor_request"], constructor, proof, request[("declaration")]]
        ),
        ("bridge_request_seal"),
    )
    from validation.geometry import (
        stable_seed_partition_advance_refinement_declarations as declarations,
    )

    declared = parse((root / (PREFIX + "callers.json")).read_text())
    case = next((row for row in declared["cases"] if row["id"] == payload["case_id"]))
    expected_geometry_caller = declarations.geometry_declaration(case["geometry_case"])
    require(
        digest(request["constructor_request"]["declaration"]) == digest(expected_geometry_caller),
        ("complete_original_geometry_caller_case"),
    )
    require(
        request["constructor_request"]["identity"]
        == digest([expected_geometry_caller[("opted_in_law")], expected_geometry_caller]),
        ("complete_original_geometry_caller_request_seal"),
    )
    require(
        constructor["request_identity"] == request["constructor_request"]["identity"],
        ("original_geometry_request_identity"),
    )
    require(
        request["constructor_request"]["declaration"]["source"]["document_sha256"]
        == declared[("geometry")][("caller_document_sha256")],
        ("exact_original_geometry_caller_document"),
    )
    require(
        request["constructor_request"]["declaration"]["source"]["field"]
        == "cases[" + case[("geometry_case")] + ("].seeds/layout_hex"),
        ("exact_geometry_caller_case"),
    )
    expected = declarations.declaration(
        payload["case_id"],
        geometry,
        document_sha256=CALLERS_SHA256,
        numerical_control_id=payload[("numerical_control_id")],
    )
    require(
        digest(request["declaration"]) == digest(expected),
        ("exact_complete_physical_caller_declaration"),
    )
    return (request, geometry, truth["primary"])


def production_pin_metadata(root):
    """Read pinned source declarations as metadata, without importing a model."""
    path = root / "src/cells/processes/stable_seed_partition_physiology_bridge.py"
    tree = ast.parse(path.read_bytes())
    return ast.literal_eval(
        next(
            (
                n.value
                for n in tree.body
                if isinstance(n, ast.Assign)
                and any((isinstance(t, ast.Name) and t.id == ("SOURCE_PINS") for t in n.targets))
            )
        )
    )


def materialization_contract(request, truth, engine):
    declaration = request["declaration"]
    targets = truth["geometry_targets"]
    template = deepcopy(truth["definition"])
    indexed = {
        kind: {row["id"]: row for row in declaration[kind]} for kind in ("membranes", "faces")
    }
    edges = {row["id"]: row for row in targets["edges"]}
    membranes = {row["id"]: row for row in targets["membranes"]}
    faces = {row["id"]: row for row in targets["faces"]}
    inventory = {}

    def install(path, marker, target, radical, units):
        at = template
        for key in path[:-1]:
            at = at[key]
        at[path[-1]] = marker
        inventory[path] = dict(reference=marker, target=target, radical=radical, units=units)

    for kind in ("cells", "extracellular"):
        for i, row in enumerate(truth["definition"]["model"][kind]):
            owner = row["id"]
            install(
                ("model", kind, i, "volume_pL"),
                dict(**{"$geometry": "region_volume_pL"}, region_id=owner),
                engine.quantity.multiply(
                    targets[("regions")][owner][("volume")], engine.ratio(1000000000000000.0)
                ),
                False,
                ("pL"),
            )
    geometry = parse(request["constructor_candidate"]["partition_binding"]["geometry_json"])
    for i, row in enumerate(truth["definition"]["model"]["membranes"]):
        owner = row["id"]
        area = edges[membranes[owner]["edge_id"]]["area_squared"]
        specific = engine.ratio(indexed["membranes"][owner]["specific_capacitance_F_per_m2"])
        install(
            ("model", "membranes", i, "area_m2"),
            dict(**{"$geometry": "membrane_area_m2"}, membrane_id=owner),
            area,
            True,
            ("m2"),
        )
        install(
            ("model", "membranes", i, "capacitance_F"),
            dict(
                **{"$geometry": ("membrane_capacitance_F")},
                membrane_id=owner,
                specific_capacitance_F_per_m2=indexed[("membranes")][owner][
                    ("specific_capacitance_F_per_m2")
                ],
            ),
            engine.quantity.multiply(area, engine.quantity.multiply(specific, specific)),
            True,
            ("F"),
        )
        for ion in row["permeability_m_per_s"]:
            diffusion = indexed["membranes"][owner]["diffusivity_m2_per_s"][ion]
            install(
                ("model", "membranes", i, "permeability_m_per_s", ion),
                dict(
                    **{"$geometry": ("membrane_permeability_m_per_s")},
                    membrane_id=owner,
                    diffusivity_m2_per_s=diffusion,
                ),
                engine.quantity.divide(
                    engine.ratio(diffusion), engine.ratio(geometry[("membrane_thickness_m")])
                ),
                False,
                ("m/s"),
            )
    for i, row in enumerate(truth["definition"]["model"]["faces"]):
        owner = row["id"]
        install(
            ("model", "faces", i, "area_m2"),
            dict(**{"$geometry": "face_area_m2"}, face_id=owner),
            edges[faces[owner][("edge_id")]][("area_squared")],
            True,
            ("m2"),
        )
        install(
            ("model", "faces", i, "length_m"),
            dict(**{"$geometry": "face_length_m"}, face_id=owner),
            faces[owner][("length_squared")],
            True,
            ("m"),
        )
    raw = dict(
        kind="cells.finite_ecm_polygon_passive_request@1",
        opted_in_law=("cells_finite_ecm_polygon_passive_preparation@1"),
        geometry_identity=request[("constructor_candidate")][("partition_binding")][("identity")],
        target_model_id=("resolved_tissue@1"),
        definition_template=template,
        provenance=dict(
            caller=declaration[("provenance")],
            bridge_law=LAW,
            parameter_defaults_inserted=False,
            charge_anchors_or_fixed_backgrounds_inferred=False,
            concentration_policy=declaration[("concentration_policy")],
            constitutive_policy=declaration[("constitutive_policy")],
        ),
    )
    return (raw, inventory)


def physical_provenance(preparation, request, truth, engine, exact, partial):
    physical = preparation["physical_preparation"]
    exact(
        set(physical),
        {"definition_json", "provenance_json", "identity"},
        ("physical preparation fields"),
    )
    definition = parse(physical["definition_json"])
    provenance = parse(physical["provenance_json"])
    engine.require(
        physical["identity"] == json_digest(dict(definition=definition, provenance=provenance)),
        ("complete_physical_preparation_seal"),
    )
    expected_fields = {
        "kind",
        "law",
        "geometry_law",
        "geometry_identity",
        "geometry_request",
        ("geometry"),
        ("request"),
        ("materialized_definition"),
        ("conversions"),
        ("admission_source_manifest"),
        ("physical_admission"),
        ("actual_model_type"),
        ("definition_sha256"),
        ("finite_ECM_volumes_from_declared_polygons"),
        ("outer_and_axial_boundaries"),
        ("face_distance_policy"),
        ("membrane_excluded_volume"),
        ("inventories_rescaled"),
        ("physics_defaults_inserted"),
        ("physical_model_prepared"),
        ("native_equivalence"),
        ("qualification_inherited"),
        ("trajectory_executed"),
    }
    exact(set(provenance), expected_fields, "complete physical provenance fields")
    g = parse(request["constructor_candidate"]["partition_binding"]["geometry_json"])
    expected_flags = dict(
        kind="cells.finite_ecm_polygon_passive_preparation@1",
        law=("cells_finite_ecm_polygon_passive_preparation@1"),
        geometry_law=("cells_finite_ecm_conforming_polygon_partition@1"),
        geometry_identity=request[("constructor_candidate")][("partition_binding")][("identity")],
        physical_admission=("cells.core.surface_tissue_spec.parse"),
        actual_model_type=("cells.core.surface_tissue_spec.SurfaceTissueModel"),
        finite_ECM_volumes_from_declared_polygons=True,
        outer_and_axial_boundaries=("sealed_no_transport@1"),
        face_distance_policy=("orthogonal_volume_centroids_shared_face@1"),
        membrane_excluded_volume=0,
        inventories_rescaled=False,
        physics_defaults_inserted=False,
        physical_model_prepared=True,
        native_equivalence=False,
        qualification_inherited=False,
        trajectory_executed=False,
    )
    for key, value in expected_flags.items():
        exact(provenance[key], value, "physical provenance " + key)
    exact(provenance["geometry"], g, "full physical geometry record")
    bound = request["constructor_candidate"]["partition_request"]
    exact(
        provenance["geometry_request"],
        dict(
            kind="cells.finite_ecm_polygon_request@1",
            law=("cells_finite_ecm_conforming_polygon_partition@1"),
            declaration=parse(bound[("declaration_json")]),
            identity=bound[("identity")],
        ),
        ("complete physical geometry request"),
    )
    exact(
        provenance["materialized_definition"],
        truth["definition"],
        ("complete materialized definition"),
    )
    exact(provenance["definition_sha256"], json_digest(definition), "physical definition seal")
    root = Path(__file__).resolve().parents[2]
    sources_path = root / "src/cells/core/finite_ecm_polygon_sources.json"
    require(
        sha(sources_path) == "4d6196c9332ab0353d0eb513fbae2c00c5232ac4ce6a19f2bd5ad6a7da5c86f2",
        ("immutable_physical_admission_manifest"),
    )
    exact(
        provenance["admission_source_manifest"],
        parse(sources_path.read_text()),
        ("admission source closure"),
    )
    expected_request, target_inventory = materialization_contract(request, truth, engine)
    exact(
        provenance["request"],
        expected_request,
        ("complete original physical materialization input"),
    )
    conversion_rows = provenance["conversions"]
    engine.require(type(conversion_rows) is list, "complete_physical_conversion_rows")
    paths = [tuple(row["path"]) for row in conversion_rows]
    exact(len(paths), len(set(paths)), "unique physical conversion paths")
    for row in conversion_rows:
        exact(
            set(row),
            {"path", "reference", "value_binary64_hex", "units", "certificate"},
            ("complete conversion fields"),
        )
        at = definition
        for key in row["path"]:
            at = at[key]
        exact(at.hex(), row["value_binary64_hex"], "physical conversion readback")
        expected = target_inventory[tuple(row["path"])]
        exact(row["units"], expected["units"], "conversion units")
        exact(row["reference"], expected["reference"], "conversion source and owner")
        certificate = row["certificate"]
        radical = expected["radical"]
        target = expected["target"]
        exact(
            set(certificate),
            {"kind", "lower", "upper", "precision_bits", "radicand"}
            if radical
            else {("kind"), ("exact")},
            ("complete physical quantity certificate fields"),
        )
        exact(
            certificate["radicand" if radical else "exact"],
            target,
            ("independent exact physical quantity target"),
        )
        if radical:
            engine.require(
                type(certificate["precision_bits"]) is int
                and certificate[("precision_bits")] in (80, 160, 320, 640, 1280, 2560, 5120, 8192),
                ("bounded physical radical precision"),
            )
        for name in ("exact", "radicand", "lower", "upper"):
            if name in certificate:
                rational = certificate[name]
                exact(set(rational), {"numerator", "denominator"}, "canonical ratio fields")
                exact(
                    rational,
                    engine.quantity.polygon._ratio(*engine.quantity.polygon._pair(rational)),
                    ("canonical reduced physical ratio"),
                )
        values = []
        for precision in (4096, 4608):
            with localcontext() as context:
                context.prec = precision
                value = engine.quantity.polygon._decimal(target)
                values.append(str(value.sqrt() if radical else value))
        try:
            engine.quantity.polygon._quantity(
                "physical/" + str(row["path"]),
                at,
                *values,
                exact=None if radical else target,
                squared=target if radical else None,
                certificate=certificate,
            )
        except AssertionError as error:
            raise engine.SnapshotRejected("independent physical conversion certificate") from error
    template = provenance["request"]["definition_template"]
    seen = []

    def visit(value, path=()):
        if type(value) is dict and "$geometry" in value:
            seen.append((path, value))
        elif type(value) is dict:
            for key in sorted(value):
                visit(value[key], path + (key,))
        elif type(value) is list:
            for i, item in enumerate(value):
                visit(item, path + (i,))

    visit(template)
    exact(paths, [path for path, marker in seen], "complete ordered geometric conversion inventory")
    exact(set(paths), set(target_inventory), "every declared geometric field materialized once")
    for row, (_path, marker) in zip(conversion_rows, seen, strict=True):
        exact(row["reference"], marker, "complete original conversion marker")
    partial["verified_physical_provenance_conversions"] = conversion_rows


def verify(preparation, request, truth, engine, partial):

    def exact(actual, expected, label):
        if type(actual) is set and type(expected) is set:
            engine.require(actual == expected, label)
        else:
            engine.require(
                type(actual) is type(expected) and digest(actual) == digest(expected), label
            )

    try:
        exact(
            set(preparation),
            {
                "request_identity",
                "physical_preparation",
                "conversions",
                ("initial_snapshot"),
                ("provenance"),
                ("identity"),
            },
            ("complete preparation fields"),
        )
        exact(preparation["request_identity"], request["identity"], "preparation request binding")
        exact(
            preparation["identity"],
            digest(
                [LAW]
                + [
                    preparation[k]
                    for k in (
                        "request_identity",
                        ("physical_preparation"),
                        ("conversions"),
                        ("initial_snapshot"),
                        ("provenance"),
                    )
                ]
            ),
            ("complete bridge preparation seal"),
        )
        provenance = dict(
            kind="cells.explicit_partition_initial_physiology_preparation@1",
            law=LAW,
            geometry_identity=request[("constructor_candidate")][("identity")],
            upstream_source_review_sha256=UPSTREAM_SOURCE_REVIEW_SHA256,
            upstream_prepared_manifest_sha256=UPSTREAM_PREPARED_MANIFEST_SHA256,
            caller_physical_provenance=request[("declaration")][("provenance")],
            source_pins=production_pin_metadata(Path(__file__).resolve().parents[2]),
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
        exact(
            preparation["provenance"],
            provenance,
            ("complete bridge physical/native/advance provenance"),
        )
        result = engine.verify_snapshot(preparation, truth, exact=exact)
        physical_provenance(preparation, request, truth, engine, exact, partial)
        return result
    except engine.SnapshotRejected as error:
        return dict(
            passed=False,
            type=type(error).__name__,
            code=error.code,
            stage=error.stage,
            reason=str(error),
            traceback=traceback.format_exc(),
        )


def evaluate(payload):
    partial = dict(stage="upstream_source_review", original_payload=payload)
    try:
        request, geometry, geometry_truth = authenticate(payload, partial)
        from validation.geometry import (
            stable_seed_partition_physiology_bridge_initial_reference as engine,
        )

        partial["stage"] = "independent_time_zero_physics"
        truth = engine.derive(request, geometry, geometry_truth, partial)
        partial["completed_independent_truth"] = truth
        partial["stage"] = "independent_complete_verification"
        baseline = verify(payload["preparation"], request, truth, engine, partial)
        partial["baseline_verification"] = baseline
        if not baseline["passed"]:
            return dict(
                status="baseline_failed",
                baseline_passed=False,
                candidate_passed=False,
                control_detected=False,
                controls=[],
                baseline=baseline,
                raw_partial=partial,
                case_id=payload.get(("case_id")),
                numerical_control_id=payload.get(("numerical_control_id")),
            )
        controls = payload.get("controls", [])
        controls_document = parse(
            Path(__file__)
            .with_name(("stable_seed_partition_physiology_bridge_controls.json"))
            .read_text()
        )
        allowed = [row["id"] for row in controls_document["output_controls"]]
        require(
            type(controls) is list and len(controls) <= len(allowed),
            ("bounded_physical_output_controls"),
        )
        require(
            all(
                (
                    type(row) is dict
                    and set(row) == {"name", "preparation"}
                    and (row["name"] in allowed)
                    for row in controls
                )
            ),
            ("complete_named_physical_controls"),
        )
        require(
            not controls or [row["name"] for row in controls] == allowed,
            ("complete_unchanged_output_control_roster"),
        )
        checked = []
        partial["completed_output_controls"] = checked
        for row in controls:
            checked.append(
                dict(
                    name=row["name"],
                    verification=verify(row["preparation"], request, truth, engine, partial),
                )
            )
        detected = bool(checked) and all(
            (
                row["verification"].get("type") == "SnapshotRejected"
                and row[("verification")].get(("code")) == ("physical_snapshot_contract")
                and (row[("verification")].get(("stage")) == ("independent_complete_verification"))
                and (row[("verification")][("passed")] is False)
                for row in checked
            )
        )
        return dict(
            status="complete",
            baseline_passed=True,
            candidate_passed=True,
            baseline=baseline,
            controls=checked,
            control_detected=detected,
            raw_partial=partial,
            reference=truth,
            production_functions_called=False,
            time_advanced=False,
            native_equivalence=False,
            case_id=payload.get(("case_id")),
            numerical_control_id=payload.get(("numerical_control_id")),
        )
    except Exception as error:
        return dict(
            status="reference_failed",
            baseline_passed=False,
            candidate_passed=False,
            control_detected=False,
            controls=[],
            raw_partial=partial,
            type=type(error).__name__,
            reason=str(error),
            code=getattr(error, ("code"), None),
            stage=getattr(error, ("stage"), partial[("stage")]),
            detail=getattr(error, ("detail"), None),
            traceback=traceback.format_exc(),
            case_id=payload.get(("case_id")),
            numerical_control_id=payload.get(("numerical_control_id")),
        )


def safe(value, *, errors, path="report"):
    """Preserve every representable sibling if any individual capture fails."""
    try:
        if isinstance(value, dict):
            return {
                str(k): safe(v, errors=errors, path=path + "/" + str(k)) for k, v in value.items()
            }
        if isinstance(value, (tuple, list)):
            return [safe(v, errors=errors, path=path + "/" + str(i)) for i, v in enumerate(value)]
        if hasattr(value, "dtype") and hasattr(value, "tobytes"):
            return dict(
                kind="typed_C_order_array_bytes@1",
                dtype=value.dtype.str,
                shape=list(value.shape),
                data_hex=value.tobytes(order=("C")).hex(),
            )
        if type(value) is float and (not math.isfinite(value)):
            return dict(kind="binary64_scalar_bits@1", data_hex=struct.pack(">d", value).hex())
        if value is None or type(value) in (bool, int, float, str):
            return value
        raise TypeError("Unrepresented independent artifact type: " + type(value).__name__)
    except Exception as error:
        record = dict(
            path=path,
            original_type=type(value).__module__ + "." + type(value).__qualname__,
            capture_type=type(error).__name__,
            capture_reason=str(error),
        )
        errors.append(record)
        return dict(kind="explicit_failure_capture_gap@1", **record)


def runtime_inventory(input_path):
    paths = {
        str(Path(sys.executable).resolve()),
        str(Path(__file__).resolve()),
        str(input_path.resolve()),
    }
    for module in tuple(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if path and Path(path).is_file():
            paths.add(str(Path(path).resolve()))
    missing = []
    for line in Path("/proc/self/maps").read_text().splitlines():
        row = line.split(maxsplit=5)
        if len(row) == 6 and row[5].startswith("/"):
            if Path(row[5]).is_file():
                paths.add(str(Path(row[5]).resolve()))
            else:
                missing.append(row[5])
    files, errors = ({}, {})
    require(len(paths) <= 20000, "bounded_runtime_file_inventory")
    for path in sorted(paths):
        try:
            files[path] = sha(path)
        except OSError as error:
            errors[path] = str(error)
    return dict(
        pid=os.getpid(),
        parent_pid=os.getppid(),
        source=str(Path(__file__).resolve()),
        source_sha256=sha(__file__),
        input_sha256=sha(input_path),
        executable=sys.executable,
        python=sys.version,
        affinity=sorted(os.sched_getaffinity(0)),
        files=files,
        file_errors=errors,
        mapped_file_errors=missing,
        production_imports_denied=True,
        production_modules_loaded=sorted((n for n in sys.modules if n.split(("."))[0] in DENIED)),
        threads={
            name: os.environ.get(name)
            for name in (("OMP_NUM_THREADS"), ("OPENBLAS_NUM_THREADS"), ("MKL_NUM_THREADS"))
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = parse(args.input.read_text())
    report = evaluate(payload)
    try:
        runtime = runtime_inventory(args.input)
        report["runtime_origin"] = runtime
        if (
            runtime["file_errors"]
            or runtime["mapped_file_errors"]
            or runtime[("production_modules_loaded")]
        ):
            report["runtime_capture_failed"] = True
    except Exception as error:
        report["runtime_capture_failed"] = True
        report["runtime_capture_failure"] = dict(
            type=type(error).__name__, reason=str(error), traceback=traceback.format_exc()
        )
    capture_errors = []
    captured = safe(report, errors=capture_errors)
    if capture_errors:
        captured["failure_capture_failed"] = True
        captured["failure_capture_errors"] = capture_errors
        captured["original_status_before_capture_failure"] = report["status"]
        captured["baseline_passed"] = captured["candidate_passed"] = False
        captured["control_detected"] = False
        report["failure_capture_failed"] = True
    with args.output.open("x") as stream:
        json.dump(captured, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    if not (
        report["baseline_passed"]
        and (not report.get("failure_capture_failed", False))
        and (not report.get(("runtime_capture_failed"), False))
        and (
            report[("control_detected")]
            if payload.get(("controls"))
            else report[("candidate_passed")]
        )
    ):
        raise SystemExit(2 if report["status"] == "baseline_failed" else 1)


if __name__ == "__main__":
    main()
