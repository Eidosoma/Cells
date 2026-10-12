"""Long native-junction qualification and common-time refinement diagnostics."""

import json
from pathlib import Path

import numpy as np

from validation.betse.spatial_active import junctions, refinement

PROTOCOL_PATH = Path(__file__).with_name("junction_refinement_protocol.json")


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def baseline():
    rule = protocol()
    reports = {}
    for name in ("prior_binding", "prefix_binding"):
        binding = rule[name]
        root = Path(binding["root"])
        assert refinement.digest(root / "completion.json") == binding["completion_sha256"]
        # The old component predates ordinary runtime integration. Authenticate
        # it against its own frozen production, then bind today's complete source
        # tree to the more recent, completed runtime qualification below.
        current = junctions.ROOT if name == "prior_binding" else root / "source"
        reports[name] = refinement.completed_prior(binding, current_root=current)
    root = Path(rule["prior_binding"]["root"])
    registration = json.loads((root / "registration.json").read_text())
    for name, digest in registration["sources_sha256"].items():
        assert refinement.digest(junctions.ROOT / name) == digest, name
    production = {
        str(p.relative_to(junctions.ROOT)) for p in (junctions.ROOT / "src").rglob("*.py")
    }
    assert production == {n for n in registration["sources_sha256"] if n.startswith("src/")}
    return dict(
        status="passed",
        root=str(root),
        prerequisites=reports,
        unchanged_prior_files=len(registration["sources_sha256"]),
        unchanged_production_files=len(production),
        inherited_suites=registration["test_nodes"],
        qualification_scope="Unchanged completed CPU/L4 runtime plus longer array-component checks",
    )


def native_series(row, trace):
    result = refinement.native_series(row, trace)
    indices = np.flatnonzero((trace["method"] == 3) & trace["after"])
    result["junction_open"] = trace["gjopen"][indices]
    return result


def check(case, series, area, rule):
    """Extend the existing active-law oracle with stored junction opening.

    A fractional block multiplies stored state once per moving-ion update.
    Changing dt changes that prescription's physical-time rate, so it is not
    admitted as refinement of the same fixed physical-time intervention.
    """
    criteria = rule["refinement"]
    assert case in criteria["cases"], "Step-dependent fractional blocking is not a refinement case"
    history = [np.asarray(values["junction_open"]) for values in series]
    for opening, dt in zip(history, rule["native_steps_s"], strict=True):
        assert opening.shape == (round(rule["duration_s"] / dt), len(area)), (
            "Incomplete junction history"
        )
        assert np.isfinite(opening).all() and ((0 <= opening) & (opening <= 1)).all(), (
            "Invalid junction history"
        )
    report = refinement.check(case, series, area, rule)
    tol = rule["tolerances"]
    for checkpoint in report["checkpoints"]:
        time = checkpoint["completed_time_s"]
        values = [
            opening[round(time / dt) - 1]
            for opening, dt in zip(history, rule["native_steps_s"], strict=True)
        ]
        checkpoint["fields"]["junction_open"] = refinement.passive.differences(
            *values, tol["gate_atol"], tol["gate_rtol"], criteria
        )
    if case in criteria["required_resolved_junction_cases"]:
        assert report["checkpoints"][-1]["fields"]["junction_open"]["first_order_resolved"], (
            "Required junction refinement signal unresolved"
        )
    report["first_order_scope"] = (
        "Resolved fields in pinned per-ion clock semantics; binary blocks only; "
        "no spatial convergence or independent physical-time model claim"
    )
    return report
