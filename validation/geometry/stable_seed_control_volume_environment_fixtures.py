"""Explicit deferred caller selections for prerequisite correspondence tests."""

import hashlib
import json
from pathlib import Path

from cells.processes import stable_seed_control_volume_environment as environment
from validation.geometry import stable_seed_control_volume_physical_bridge_fixtures as upstream

POSITIVE_CASES = (
    ("manufactured-irregular-square", "held-compartments"),
    ("manufactured-irregular-square", "finite-compartments"),
    ("manufactured-seed17-rectangle", "finite-compartments"),
)
POSITIVE_IDS = ("held-one-bath", "finite-one-bath", "finite-two-baths")


def caller():
    path = Path(__file__).with_name("stable_seed_control_volume_environment_callers.json")
    return json.loads(path.read_text()), hashlib.sha256(path.read_bytes()).hexdigest()


def physical_input(geometry, case, profile):
    declaration, sha = caller()
    if profile not in declaration["profiles"]:
        raise ValueError(
            "Caller must explicitly choose a recorded manufactured compartment profile"
        )
    raw = upstream.physical_input(geometry)
    if profile == "finite-compartments":
        for row in raw["physics"]["baths"]:
            row["reservoir"] = False
        raw["physics"]["closure"]["gauge_reference"] = declaration["finite_profile_gauge_by_case"][
            case
        ]
    raw["physics"]["provenance"]["explicit_environment_inspection_profile"] = dict(
        profile=profile, declaration_sha256=sha, finite_ECM_geometry_claimed=False
    )
    return raw


def acceptance(request, geometry, physical, input_json, report_json):
    return environment.BridgeEvidence(
        input_json,
        report_json,
        dict(
            kind="caller_accepts_complete_positive_manufactured_physical_bridge@1",
            caller=caller()[0]["authority"],
            bridge_request_identity=request.identity,
            geometry_preparation_identity=geometry.identity,
            physical_preparation_identity=physical.identity,
            input_sha256=hashlib.sha256(input_json.encode("utf-8")).hexdigest(),
            report_sha256=hashlib.sha256(report_json.encode("utf-8")).hexdigest(),
            scope="initial_manufactured_physical_bridge_only_no_ECM_or_native_environment_admission",
        ),
    )


def declaration(request, geometry, physical):
    declared, sha = caller()
    g = geometry.geometry_binding.geometry
    compartments = {
        row["id"]: row for row in physical.physical_preparation.definition["model"]["extracellular"]
    }
    return dict(
        kind=environment.INPUT_KIND,
        opted_in_law=environment.LAW_ID,
        scope="prerequisite_correspondence_only_no_finite_ECM_or_native_environment_admission",
        domain_selection=dict(
            caller=declared["authority"],
            document_sha256=sha,
            selected_domain=environment.plain(
                request.declaration["domain_selection"]["selected_domain"]
            ),
            native_equivalence=False,
        ),
        baths=[
            dict(
                id=row["id"],
                volume_m3=row["volume_m3"],
                reservoir=compartments[row["id"]]["reservoir"],
                boundary_potential_V=compartments[row["id"]]["boundary_potential_V"],
                geometry_role="declared_compartment_without_polygon_geometry@1",
            )
            for row in g["baths"]
        ],
        membrane_baths=[
            dict(
                membrane_id=row["id"],
                cell_id=row["cell_id"],
                bath_id=row["bath_id"],
                directed_vertex_ids=row["vertex_ids"],
            )
            for row in g["membranes"]
        ],
        outer_boundary=dict(
            kind="prospective_same_ring_ECM_boundary_not_admitted@1",
            condition=declared["boundary_selection"],
            rows=[
                dict(
                    membrane_id=row["id"],
                    cell_id=row["cell_id"],
                    assigned_bath_id=row["bath_id"],
                    directed_vertex_ids=row["vertex_ids"],
                )
                for row in g["membranes"]
                if row["partner_id"] == row["id"]
            ],
        ),
        operator_policy=dict(
            kind="invalidate_all_environment_indices_and_operators@1",
            provided_cached_operators=None,
        ),
    )
