"""Deferred caller declarations for manufactured bridge tests, never defaults."""

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path

from cells.core import conservative_polygon_tissue_preparation as physical
from cells.processes import conservative_polygon_geometry as geometry
from cells.processes import stable_seed_control_volume_physical_bridge as bridge
from cells.processes import stable_seed_control_volumes as volumes
from validation.geometry import stable_mesh_physical_reconstruction_saved as saved

BASE = "manufactured-irregular-square"
SECOND = "manufactured-seed17-rectangle"
POSITIVE_CASES = (
    ("manufactured-irregular-square", False),
    ("manufactured-irregular-square", True),
    ("manufactured-seed17-rectangle", True),
)
POSITIVE_IDS = ("geometry-only-irregular", "physical-irregular", "physical-seed17-two-baths")


def catalog():
    path = Path(__file__).with_name("stable_seed_control_volume_physical_bridge_domains.json")
    return json.loads(path.read_text()), hashlib.sha256(path.read_bytes()).hexdigest()


def case_record(case):
    return next(deepcopy(row) for row in catalog()[0]["cases"] if row["id"] == case)


def constructor_declaration(case):
    row, (document, sha) = case_record(case), catalog()
    domain = dict(
        id=row["domain_id"],
        vertices_m=row["vertices_m"],
        provenance=dict(
            kind="explicit_caller_polygon@1",
            authority=document["authority"],
            document_sha256=sha,
            field="cases[" + case + "].vertices_m",
            native_tissue_equivalence=False,
        ),
        role="prospective_partition_envelope_not_native_tissue_boundary",
    )
    return dict(
        kind=volumes.INPUT_KIND,
        opted_in_law=volumes.LAW_ID,
        units=volumes.UNITS.copy(),
        domain=domain,
        seed_policy="retain_original_binary64_coordinates_and_owner_ids",
        connectivity_policy="replace_dual_and_seed_adjacency_explicitly",
        rounding_policy="shared_vertex_once_strict_domain_no_collision_or_seed_loss",
        physical_status="prospective_geometry_only_no_physical_admission",
    )


def original_request(case):
    selected = os.environ.get("CELLS_STABLE_MESH_PHYSICAL_SAVED_RUN")
    if not selected:
        raise ValueError("Explicit frozen original evidence root required for bridge qualification")
    return saved.retained_request(case_record(case)["retained_source_case"], run=Path(selected))


def declaration(case, candidate):
    row, (document, sha) = case_record(case), catalog()
    if row["bath_assignment_policy"] == "one_explicit_bath@1":
        assignment = dict(kind="one_explicit_bath@1", bath_id=row["baths"][0]["id"])
    elif (
        row["bath_assignment_policy"] == "explicit_alternating_constructor_edge_indices_test_only@1"
    ):
        names = candidate.connectivity["vertices"]
        assignment = dict(
            kind="explicit_edge_baths@1",
            rows=[
                dict(vertex_ids=[names[a], names[b]], bath_id=row["baths"][i % 2]["id"])
                for i, (a, b) in enumerate(candidate.connectivity["edges"])
            ],
        )
    else:
        raise ValueError("Caller must choose one of the explicitly recorded test bath policies")
    return dict(
        kind=bridge.INPUT_KIND,
        opted_in_law=bridge.LAW_ID,
        domain_selection=dict(
            kind="fresh_explicit_caller_domain_selection@1",
            selected_domain=constructor_declaration(case)["domain"],
            caller=document["authority"],
            document_sha256=sha,
            purpose="manufactured_prismatic_partition_geometry_only",
            native_tissue_or_bath_equivalence=False,
        ),
        extrusion=dict(
            height_m=row["height_m"],
            thickness_m=row["thickness_m"],
            baths=row["baths"],
            bath_assignment=assignment,
            axial_caps="sealed_no_transport@1",
            units=geometry.UNITS.copy(),
            cell_policy="one_manufactured_cell_per_retained_seed_no_merge",
            boundary_partner_policy="conservative_self_partner_with_explicit_bath@1",
        ),
        operator_policy=dict(
            kind="invalidate_all_and_rebuild_under_new_geometry_identity@1",
            provided_cached_operators=None,
        ),
        scope="manufactured_polygon_preparation_not_native_geometry_equivalence",
    )


def acceptance(candidate, input_json, report_json):
    return bridge.ConstructorEvidence(
        input_json,
        report_json,
        dict(
            kind="caller_accepts_complete_positive_constructor_reference@1",
            caller="explicit manufactured bridge qualification fixture",
            constructor_identity=candidate.identity,
            input_sha256=hashlib.sha256(input_json.encode("utf-8")).hexdigest(),
            report_sha256=hashlib.sha256(report_json.encode("utf-8")).hexdigest(),
            scope="constructor_geometry_only_no_native_physical_or_operator_admission",
        ),
    )


def physical_input(prepared):
    """Explicit neutral test inventories; no scientific defaults in bridge API."""
    g = prepared.geometry_binding.geometry

    def inventory(row, amount):
        return dict(
            id=row["id"],
            initial_amount_fmol=dict(Na=amount, Cl=amount),
            initial_charge_C=0.0,
            fixed_charge_equivalent_fmol=0.0,
        )

    cells = [inventory(row, 0.001) for row in g["cells"]]
    baths = [
        dict(inventory(row, 0.002), reservoir=True, boundary_potential_V=0.0) for row in g["baths"]
    ]
    membranes = [
        dict(
            id=row["id"],
            cell_id=row["cell_id"],
            bath_id=row["bath_id"],
            specific_capacitance_F_per_m2=0.01,
            diffusivity_m2_per_s=dict(Na=1e-18, Cl=1e-18),
        )
        for row in g["membranes"]
    ]
    contacts = [
        dict(
            id=row["id"],
            sender=row["sender"],
            receiver=row["receiver"],
            membrane_ids=row["membrane_ids"],
            permeability_m_per_s=dict(Na=3e-9, Cl=3e-9),
        )
        for row in g["contacts"]
    ]
    return dict(
        kind=physical.REQUEST_KIND,
        opted_in_law=physical.BRIDGE_ID,
        geometry_identity=prepared.geometry_binding.identity,
        physics=dict(
            species=[dict(id="Na", valence=1), dict(id="Cl", valence=-1)],
            temperature_K=310.0,
            cells=cells,
            baths=baths,
            membranes=membranes,
            contacts=contacts,
            closure=dict(
                law="resolved_capacitor_components_current_continuity@1", gauge_reference=None
            ),
            provenance=dict(
                classification=(
                    "Explicit manufactured neutral per-owner inventories, "
                    "uniform coefficients, held baths; no calibration"
                ),
                amounts_are_declared_per_owner_not_rescaled_from_geometry=True,
            ),
        ),
        experiment=dict(
            end_time=1e-6,
            observation_times=[0.0, 1e-6],
            membrane_controls=[
                dict(membrane_id=row["id"], schedule=[dict(time=0.0, availability=1.0)])
                for row in membranes
            ],
            junction_controls=[
                dict(junction_id=row["id"], schedule=[dict(time=0.0, availability=1.0)])
                for row in contacts
            ],
        ),
        execution=dict(
            dt=1e-7,
            jit=False,
            backend="cpu",
            precision="float64",
            solver="rk4",
            capacity=len(cells),
            extracellular_capacity=len(baths),
            membrane_capacity=len(membranes),
            edge_capacity=len(contacts),
            face_capacity=0,
            max_steps=20,
            max_trace_bytes=2**20,
            material_balance_atol_fmol=dict(Na=1e-14, Cl=1e-14),
            field_solver="capacitive_reduction_gauged_damped_newton@1",
        ),
    )
