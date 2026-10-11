"""Versioned acceptance resources; the scientific panel remains the unchanged v1 plan."""

from dataclasses import dataclass
from pathlib import Path

from cells.core.specs import read_json
from cells.io import _sha256 as sha
from scripts import spatial_extracellular_acceptance_plan as plan
from scripts.spatial_extracellular_production_audit import authenticate, require

ROOT = plan.ROOT
DOCUMENT_EDITS = frozenset(
    ("PROGRESS.md", "README.md", "docs/SPATIAL_EXTRACELLULAR.md", "docs/DECISIONS.md")
)
RETRY_EDITS = DOCUMENT_EDITS | {
    "scripts/verify_spatial_extracellular_build.py",
    "scripts/audit_spatial_extracellular_build.py",
    "scripts/close_core010_acceptance.py",
}
V2_DEFINITION = ROOT / "configs/acceptance/spatial_extracellular_resources_v2.json"
PROJECTION = ROOT / "reports/core-010-runtime-projection.json"
STOPPED = ROOT / "reports/core-010-stopped-preservation.json"
V2_BASELINE = ROOT / "reports/core-010-retry-workspace-baseline.json"


@dataclass(frozen=True)
class AcceptanceResources:
    name: str
    max_seconds: int
    protocol: Path
    baseline: Path
    allowed_edits: frozenset[str]

    @property
    def capture_paths(self):
        if self.name == "v1":
            return (self.protocol,)
        return (plan.PROTOCOL, self.protocol, V2_DEFINITION, PROJECTION, self.baseline)

    def registration_fields(self):
        fields = {
            "schema": f"cells.core010_registration@{self.name[1:]}",
            "protocol_sha256": sha(self.protocol),
            "max_seconds": self.max_seconds,
            "max_artifact_bytes": plan.MAX_BYTES,
        }
        if self.name == "v2":
            fields |= {"resource_plan": "v2", "resource_definition_sha256": sha(V2_DEFINITION)}
        return fields


PROFILES = {
    "v1": AcceptanceResources(
        "v1",
        plan.MAX_SECONDS,
        plan.PROTOCOL,
        ROOT / "reports/core-010-acceptance-workspace-baseline.json",
        DOCUMENT_EDITS,
    ),
    "v2": AcceptanceResources(
        "v2",
        7200,
        ROOT / "docs/SPATIAL_EXTRACELLULAR_ACCEPTANCE_V2.md",
        V2_BASELINE,
        frozenset(RETRY_EDITS),
    ),
}


def get_resources(name="v1"):
    require(type(name) is str and name in PROFILES, "Unknown acceptance resource plan")
    resources = PROFILES[name]
    if name == "v2":
        require(
            read_json(V2_DEFINITION)
            == {
                "schema": "cells.core010_acceptance_resources@2",
                "id": "v2",
                "max_seconds": resources.max_seconds,
                "max_artifact_bytes": plan.MAX_BYTES,
                "cpu_affinity": [0, 1, 2, 3],
                "thread_environment": dict.fromkeys(plan.THREADS, "1"),
                "scientific_protocol_sha256": sha(plan.PROTOCOL),
                "prior_stop_receipt_sha256": sha(STOPPED),
                "runtime_projection_sha256": sha(PROJECTION),
                "workspace_baseline_sha256": sha(V2_BASELINE),
            },
            "Resource definition or its evidence differs",
        )
    return resources


def from_registration(registration):
    require(type(registration) is dict, "Invalid acceptance registration")
    resources = get_resources(registration.get("resource_plan", "v1"))
    expected = resources.registration_fields()
    require(
        all(registration.get(k) == v for k, v in expected.items()),
        "Registered resource plan differs",
    )
    if resources.name == "v1":
        require(
            "resource_plan" not in registration
            and "resource_definition_sha256" not in registration,
            "Unexpected legacy resource metadata",
        )
    return resources


def authenticate_prior_stop(resources):
    if resources.name == "v1":
        return None
    receipt = read_json(STOPPED)
    session = ROOT / receipt["session"]
    require(
        receipt["status"] == "stopped_not_accepted"
        and receipt["preservation_status"] == "verified"
        and not (session / "verification.json").exists(),
        "Prior stopped session relabeled",
    )
    authenticate(session, receipt["files_sha256"])
    require(
        sha(session / "failure.json") == receipt["failure_sha256"]
        and sha(session / "registration.json") == receipt["registration_sha256"],
        "Prior stop identity differs",
    )
    return {"receipt_sha256": sha(STOPPED), "files": len(receipt["files_sha256"])}
