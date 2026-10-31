"""Prospective original-seed declarations; no source geometry is eagerly run."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from cells.processes import stable_seed_control_volumes as volumes
from validation.geometry import stable_mesh_physical_reconstruction_saved as saved

ROSTER_SHA256 = "1728bbbc2847270ac5441d2cae338d4ce845acbbb469ee5149accae6524fa622"
CONSTRUCTION_CASES = (
    "irregular-centroid-aux",
    "native-single-preset-seed17",
    "native-single-preset-seed23",
)
DOMAIN_GAPS = ("caller-single-square-cache", "caller-single-hex-cache")
BASE = "irregular-centroid-aux"


def roster():
    path = Path(__file__).with_name("stable_seed_control_volumes_domain_roster.json")
    if hashlib.sha256(path.read_bytes()).hexdigest() != ROSTER_SHA256:
        raise ValueError("Changed original source/domain proposal roster")
    return json.loads(path.read_text())


def case_record(case):
    return next(row for row in roster()["cases"] if row["case"] == case)


def declaration(case):
    row = case_record(case)
    return dict(
        kind=volumes.INPUT_KIND,
        opted_in_law=volumes.LAW_ID,
        units=volumes.UNITS.copy(),
        domain=deepcopy(row["proposed_domain"]),
        seed_policy="retain_original_binary64_coordinates_and_owner_ids",
        connectivity_policy="replace_dual_and_seed_adjacency_explicitly",
        rounding_policy="shared_vertex_once_strict_domain_no_collision_or_seed_loss",
        physical_status="prospective_geometry_only_no_physical_admission",
    )


def original_request(case):
    return saved.retained_request(case, run=saved.evidence_run())
