"""Actual immutable packets, rehashed corruptions and a model-import-free audit."""

import json
import os
import shutil
import subprocess

import cluster_alignment as cluster
import cluster_evidence as evidence
import contact as c
import pytest


def replace_json(path, value):
    # These writes/deletions are exclusively in pytest-owned copied packets.
    path.unlink()
    c.write(path, value)


def rehash(output, receipt_name="verification.json"):
    receipt = c.read(output / receipt_name)
    receipt["files_sha256"] = {
        str(p.relative_to(output)): c.sha(p)
        for p in output.rglob("*")
        if p.is_file() and p.name != receipt_name
    }
    replace_json(output / receipt_name, receipt)
    # Confirm the forthcoming rejection is not a stale payload digest.
    assert all(c.sha(output / name) == digest for name, digest in receipt["files_sha256"].items())


@pytest.fixture
def packet(tmp_path):
    assert c.sha(evidence.SESSION / "verification.json") == evidence.CAPTURE_SHA
    output = tmp_path / "cluster"
    shutil.copytree(evidence.SESSION, output)
    return output


@pytest.fixture
def geometry_packet(tmp_path):
    assert c.sha(cluster.GEOMETRY_PROBE / "completion.json") == evidence.GEOMETRY_SHA
    output = tmp_path / "geometry"
    shutil.copytree(cluster.GEOMETRY_PROBE, output)
    return output


def test_actual_cluster_matches_saved_replay_and_prior_identity():
    assert c.sha(evidence.SESSION / "verification.json") == evidence.CAPTURE_SHA
    assert cluster.audit(evidence.SESSION) == c.read(c.ROOT / "reports/ref-003c-audit-01.json")
    result = evidence.audit(evidence.SESSION)
    assert result["status"] == "pass" and result["comparisons"] == 19691
    assert result["cells"] == 7 and result["native_faces"] == 30
    assert result["accepted_implementation_files"] == 352
    assert result["geometry_diagnostic"]["alignment_qualified"] is False


@pytest.mark.parametrize(
    "filename,path,value",
    [
        (
            "betse.json",
            ("profiles", "matched_constants", "cases", 0, "density_mol_per_m2_s", 0, 0),
            -1e-7,
        ),
        (
            "betse.json",
            ("profiles", "matched_constants", "cases", 1, "before", "voltage_V", 29),
            0.0,
        ),
        (
            "betse.json",
            ("profiles", "source_constants", "cases", 0, "after", "inside_mM", 0, 0),
            12.0,
        ),
        (
            "betse.json",
            ("profiles", "matched_constants", "cases", 0, "after", "outside_mM", 0, 0),
            145.0,
        ),
        (
            "betse.json",
            ("profiles", "matched_constants", "cases", 0, "after", "inward_current_A", 0),
            1e-6,
        ),
        ("betse.json", ("geometry", "effective_bath_volume_m3"), 2.25e-16),
        ("betse.json", ("geometry", "membrane_owners", 29), 0),
        ("betse.json", ("settings", "alpha_NaK"), 1e-7),
        ("betse.json", ("profiles", "source_constants", "constants", "F"), 96485.33212331001),
        (
            "betse.json",
            ("profiles", "matched_constants", "cases", 7, "density_mol_per_m2_s", 0, 0),
            1e-30,
        ),
        (
            "betse.json",
            ("profiles", "matched_constants", "cases", 0, "junction_density_mol_per_m2_s", 0, 0),
            1e-30,
        ),
        (
            "betse.json",
            ("profiles", "source_constants", "cases", 0, "density_mol_per_m2_s", 3, 0),
            1e-30,
        ),
        ("betse.json", ("profiles", "matched_constants", "clock", "labels_s", 1), 0.0001),
        (
            "betse.json",
            ("profiles", "source_constants", "clock", "sampled_indices"),
            list(range(10)),
        ),
        (
            "betse.json",
            ("warnings",),
            [{"category": "RuntimeWarning", "message": "invalid divide"}],
        ),
        ("betse.json", ("installed_python_sha256", "betse/science/sim.py"), "0" * 64),
        ("betse.json", ("environment", "packages", "numpy"), "0.0.0"),
        ("cells.json", ("x64_enabled",), False),
        ("cells.json", ("jit_disabled",), True),
        ("cells.json", ("results", "jax_jit"), []),
        ("cells.json", ("results", "jax_eager", 0, "outside_rate_fmol_per_s", 0), 0.0),
        ("cells.json", ("results", "numpy", 1, "increment_voltage_V", 6), 0.0),
        ("cells.json", ("results", "jax_jit", 0, "inactive_slots_zero"), False),
        (
            "cells.json",
            ("probe_definitions", "neutral_initial", "model", "extracellular", "volume_pL"),
            1.0,
        ),
        ("comparison.json", ("maximum_normalized_error",), 0.0),
    ],
)
def test_rehashed_actual_cluster_corruption_rejected(packet, filename, path, value):
    saved = c.read(packet / filename)
    target = saved
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    replace_json(packet / filename, saved)
    rehash(packet)
    with pytest.raises(ValueError):
        evidence.audit(packet)


@pytest.mark.parametrize("claim", ("centres", "runtime", "trajectory_receipt"))
def test_joint_metadata_forgery_needs_independent_anchor(packet, claim):
    registered = c.read(packet / "registration.json")
    native, local = c.read(packet / "betse.json"), c.read(packet / "cells.json")
    if claim == "centres":
        registered["expected_geometry"]["cell_centres_m"][0][0] += 1e-5
        native["geometry"]["cell_centres_m"][0][0] += 1e-5
    elif claim == "runtime":
        registered["cells_runtime"]["cells_version"] = "0.0.0"
        local["accepted_runtime"]["cells_version"] = "0.0.0"
    else:
        receipt = c.read(packet / "verification.json")
        receipt["trajectory_run"] = True
        replace_json(packet / "verification.json", receipt)
    replace_json(packet / "registration.json", registered)
    for filename, value in (("betse.json", native), ("cells.json", local)):
        value["registration_sha256"] = c.sha(packet / "registration.json")
        replace_json(packet / filename, value)
    rehash(packet)
    # Preserve and document the frozen auditor's narrower metadata boundary.
    assert cluster.audit(packet)["status"] == "pass"
    with pytest.raises(ValueError, match="Registered|overclaims"):
        evidence.audit(packet)


def test_actual_geometry_is_a_diagnostic_not_one_cell_acceptance():
    assert c.sha(cluster.GEOMETRY_PROBE / "completion.json") == evidence.GEOMETRY_SHA
    result = evidence.geometry_audit(cluster.GEOMETRY_PROBE)
    assert result["status"] == "native_one_centre_rejection_confirmed"
    assert result["explicit_svg_centres"] == 1 and result["installed_python_files"] == 332
    assert result["one_cell_seed_succeeded"] is result["alignment_qualified"] is False


@pytest.mark.parametrize(
    "filename,path,value",
    [
        ("completion.json", ("one_cell_seed_succeeded",), True),
        ("native_result.json", ("native_seed_completed",), True),
        ("native_result.json", ("requested_explicit_centres",), 7),
        ("native_result.json", ("exception_type",), "ImportError"),
        ("native_result.json", ("exception",), "not enough points(7)"),
        ("native_result.json", ("traceback",), "unrelated adapter failure"),
        ("native_result.json", ("warnings",), []),
        ("native_result.json", ("installed_python_sha256", "betse/science/math/mesh.py"), "0" * 64),
        ("native_result.json", ("environment", "packages", "scipy"), "0.0.0"),
        ("completion.json", ("seconds",), 31),
    ],
)
def test_rehashed_geometry_cannot_support_false_claim(geometry_packet, filename, path, value):
    record = c.read(geometry_packet / filename)
    target = record
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    replace_json(geometry_packet / filename, record)
    rehash(geometry_packet, "completion.json")
    with pytest.raises(ValueError):
        evidence.geometry_audit(geometry_packet)


def test_rehashed_geometry_svg_must_match_registered_one_point(geometry_packet):
    svg = geometry_packet / "single_cell.svg"
    svg.write_text(svg.read_text().replace("</svg>", '<circle cx="1" cy="1" /></svg>'))
    rehash(geometry_packet, "completion.json")
    with pytest.raises(ValueError, match="SVG"):
        evidence.geometry_audit(geometry_packet)


def test_audits_reject_linked_evidence(packet):
    extra = packet / "linked-copy.json"
    extra.symlink_to(packet / "betse.json")
    with pytest.raises(ValueError, match="symbolic link"):
        evidence.audit(packet)


def test_fresh_process_audit_cannot_import_either_simulator():
    source = """
import json
import sys
sys.path.insert(0, "validation/betse")
class RejectModels:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"cells", "betse", "jax", "numpy", "scipy"}:
            raise AssertionError("Model/numerical import in read-only audit: " + fullname)
sys.meta_path.insert(0, RejectModels())
import cluster_evidence as e
result = e.audit(e.SESSION)
assert result["upstream_calls"] == result["production_calls"] == result["trajectory_calls"] == 0
print(json.dumps(result))
"""
    env = os.environ | {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"}
    env.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [str(c.CELLS_PYTHON), "-B", "-c", source],
        cwd=c.ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    assert json.loads(completed.stdout)["status"] == "pass"
