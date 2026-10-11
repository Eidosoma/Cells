"""Real saved trajectories: anchored audit plus rehashed metadata/array corruptions."""

import copy
import hashlib
import json
import os
import shutil
import struct
import subprocess
import zipfile

import contact as c
import pytest
import trajectory_check as arithmetic
import trajectory_evidence as evidence

FINE = "native/passive/matched_constants/0.00000625/observed/result.json"


def replace_json(path, value):
    # Unlink our pytest-owned hardlink BEFORE writing. Never modify a retained inode.
    path.unlink()
    c.write(path, value)


def rehash(output):
    receipt = c.read(output / "verification.json")
    receipt["files_sha256"] = {
        str(p.relative_to(output)): c.sha(p)
        for p in output.rglob("*")
        if p.is_file()
        and str(p.relative_to(output)) not in evidence.OPERATIONAL | {"verification.json"}
    }
    receipt["artifact_bytes_before_receipt"] = sum(
        p.stat().st_size for p in output.rglob("*") if p.is_file() and p.name != "verification.json"
    )
    replace_json(output / "verification.json", receipt)
    assert all(c.sha(output / n) == h for n, h in receipt["files_sha256"].items())


def rehash_array(array):
    array["bytes_sha256"] = hashlib.sha256(
        b"".join(struct.pack("<d", v) for v in arithmetic.numbers(array["values"]))
    ).hexdigest()
    arithmetic.unpack(array)


@pytest.fixture(scope="module")
def packet_source(tmp_path_factory):
    # /tmp can be a different filesystem: stage one ordinary copy there, then
    # hardlink only between pytest-owned directories on that same filesystem.
    output = tmp_path_factory.mktemp("trajectory-source") / "packet"
    shutil.copytree(evidence.SESSION, output)
    return output


@pytest.fixture
def packet(tmp_path, packet_source):
    output = tmp_path / "trajectory"
    shutil.copytree(packet_source, output, copy_function=os.link)
    yield output
    assert all(
        c.sha(evidence.SESSION / name) == digest for name, digest in evidence.ANCHORS.items()
    )


@pytest.fixture(scope="module")
def record():
    return c.read(evidence.SESSION / FINE)


def test_actual_packet_metadata_and_auxiliary_exports():
    registered, receipt = evidence.inspect_packet(evidence.SESSION)
    assert len(receipt["files_sha256"]) == 115
    count = 0
    for case in registered["protocol"]["cases"]:
        for profile in registered["protocol"]["native_constant_profiles"]:
            for dt in registered["protocol"]["native_steps_s"]:
                name = evidence.original.key(case["id"], profile, dt)
                path = evidence.SESSION / f"native/{name}/observed/result.json"
                count += evidence.native_links(registered, c.read(path), case)
    assert count == 1120


def test_full_audit_has_no_simulator_or_array_library_imports():
    code = """
import importlib.abc
import json
import sys
class Fence(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'cells', 'betse', 'numpy', 'jax'}:
            raise AssertionError('Forbidden model/numerical import: ' + fullname)
sys.meta_path.insert(0, Fence())
import trajectory_evidence as e
result = e.audit()
assert result == e.c.read(e.c.ROOT / 'reports/ref-003d-v2-evidence-audit.json')
print(json.dumps({'status': result['status'], 'comparisons': result['comparison']['comparisons'],
                  'model_imports': result['model_imports'],
                  'production_calls': result['production_calls']}))
"""
    result = subprocess.run(
        [str(c.CELLS_PYTHON), "-B", "-c", code],
        cwd=c.HERE,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    assert json.loads(result.stdout) == {
        "status": "pass",
        "comparisons": 435144,
        "model_imports": [],
        "production_calls": 0,
    }


@pytest.mark.parametrize(
    "filename,path,value",
    [
        ("verification.json", ("status",), "failed"),
        ("verification.json", ("biological_validation",), True),
        ("verification.json", ("trajectory_run",), False),
        ("verification.json", ("seconds",), 181),
        ("verification.json", ("worker_seconds", "betse"), 91),
        ("verification.json", ("worker_seconds", "cells"), -1),
        ("verification.json", ("finished_utc",), "2026-09-11T00:00:00+00:00"),
        ("verification.json", ("preservation", "production_modules_unchanged"), 52),
        (
            "betse.json",
            ("warnings",),
            [{"category": "RuntimeWarning", "message": "invalid divide"}],
        ),
        ("betse.json", ("engine",), "synthetic_fixture"),
        ("betse.json", ("installed_python_sha256", "betse/science/sim.py"), "0" * 64),
        ("betse.json", ("environment", "packages", "numpy"), "0.0.0"),
        ("cells.json", ("device",), "gpu"),
        ("cells.json", ("x64_enabled",), False),
        ("cells.json", ("jit_disabled",), True),
        ("cells.json", ("registration_sha256",), "0" * 64),
        ("cells.json", ("results", "passive/jax_jit/0.00005000"), "../result.json"),
        ("started.json", ("pid",), 1),
    ],
)
def test_rehashed_metadata_corruption_rejected(packet, filename, path, value):
    saved = c.read(packet / filename)
    target = saved
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    replace_json(packet / filename, saved)
    rehash(packet)
    evidence.verify_manifest(packet, evidence.trusted_registration())
    with pytest.raises(ValueError):
        evidence.inspect_packet(packet)


@pytest.mark.parametrize("claim", ["geometry", "runtime", "definitions", "tolerances", "sources"])
def test_rehashed_registration_needs_an_independent_anchor(packet, claim):
    saved = c.read(packet / "registration.json")
    if claim == "geometry":
        saved["geometry"]["effective_bath_volume_m3"] *= 2
    elif claim == "runtime":
        saved["cells_runtime"]["cells_version"] = "0.0.0"
    elif claim == "definitions":
        saved["cells_definitions"].pop(next(iter(saved["cells_definitions"])))
    elif claim == "tolerances":
        saved["protocol"]["trajectory_tolerances"]["amount_fmol"] *= 2
    else:
        # The frozen validator checks new-file inclusion, not the complete 35-member set.
        saved["sources"].pop("single_cell.svg")
    replace_json(packet / "registration.json", saved)
    for name in ("verification.json", "betse.json", "cells.json", "launch.json"):
        record = c.read(packet / name)
        record["registration_sha256"] = c.sha(packet / "registration.json")
        if claim == "runtime" and name == "cells.json":
            record["accepted_runtime"] = saved["cells_runtime"]
        replace_json(packet / name, record)
    rehash(packet)
    evidence.verify_manifest(packet, evidence.trusted_registration())
    with pytest.raises(ValueError):
        evidence.inspect_packet(packet)


@pytest.mark.parametrize(
    "claim",
    ["missing_pickle", "empty_pickle", "extra_file", "unsafe_path", "stale_digest", "symlink"],
)
def test_packet_coverage_and_file_safety(packet, claim):
    path = (packet / FINE).parent / "INITS/init_1.betse.gz"
    if claim == "missing_pickle":
        path.unlink()
    elif claim == "empty_pickle":
        path.unlink()
        path.touch()
    elif claim == "extra_file":
        c.write(packet / "unregistered.json", {})
    elif claim == "symlink":
        path.unlink()
        path.symlink_to(evidence.SESSION / FINE)
    rehash(packet)
    if claim in {"unsafe_path", "stale_digest"}:
        receipt = c.read(packet / "verification.json")
        if claim == "unsafe_path":
            receipt["files_sha256"]["../outside.json"] = "0" * 64
        else:
            receipt["files_sha256"][FINE] = "0" * 64
        replace_json(packet / "verification.json", receipt)
    with pytest.raises(ValueError):
        evidence.verify_manifest(packet, evidence.trusted_registration())


@pytest.mark.parametrize("claim", ["missing", "extra", "duplicate", "bytes"])
def test_rehashed_source_capsule_corruption_rejected(packet, claim):
    path = packet / "sources.zip"
    with zipfile.ZipFile(path) as archive:
        entries = [(name, archive.read(name)) for name in archive.namelist()]
    path.unlink()
    if claim == "missing":
        entries.pop()
    elif claim == "extra":
        entries.append(("unregistered.py", b"# not registered\n"))
    elif claim == "duplicate":
        entries.append(entries[0])
    else:
        entries[0] = (entries[0][0], b"# changed\n")
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in entries:
            if claim == "duplicate" and name in archive.namelist():
                with pytest.warns(UserWarning, match="Duplicate name"):
                    archive.writestr(name, value)
            else:
                archive.writestr(name, value)
    rehash(packet)
    evidence.verify_manifest(packet, evidence.trusted_registration())
    with pytest.raises(ValueError, match="Source capsule"):
        evidence.inspect_packet(packet)


@pytest.mark.parametrize(
    "group,field",
    [
        ("final", "fluxes_mem"),
        ("final", "fluxes_gj"),
        ("final", "Phi_b"),
        ("final", "cc_at_mem"),
        ("final", "Dm_cells"),
        ("ordinary", "dd_time"),
        ("ordinary", "rate_NaKATP_time"),
        ("ordinary", "gjopen_time"),
    ],
)
def test_rehashed_auxiliary_arrays_need_cross_links(record, group, field):
    altered = copy.deepcopy(record)
    array = altered[group][field]
    target = array["values"]
    while isinstance(target[0], list):
        target = target[0]
    target[0] += 1
    rehash_array(array)
    with pytest.raises(ValueError):
        evidence.native_links(evidence.trusted_registration(), altered, {"availability": 1})


def test_auxiliary_shape_cannot_be_relabelled(record):
    altered = copy.deepcopy(record)
    array = altered["final"]["fluxes_mem"]
    array["shape"] = [180]
    array["values"] = arithmetic.numbers(array["values"])
    rehash_array(array)
    with pytest.raises(ValueError, match="shape"):
        evidence.native_links(evidence.trusted_registration(), altered, {"availability": 1})


def test_final_flux_forgery_passes_old_field_boundary_but_not_new_links(record):
    altered = copy.deepcopy(record)
    altered["final"]["fluxes_mem"]["values"][0][0] += 1
    rehash_array(altered["final"]["fluxes_mem"])
    registered = evidence.trusted_registration()
    checks = arithmetic.Checks()
    arithmetic.native_record(
        registered,
        altered,
        {"id": "passive", "availability": 1},
        "matched_constants",
        0.00000625,
        checks,
    )
    assert checks.failed_count == 0
    with pytest.raises(ValueError, match="flux/observer"):
        evidence.native_links(registered, altered, {"availability": 1})


@pytest.mark.parametrize("claim", ["clock", "density", "amount"])
def test_finer_actual_native_numerical_corruption_rejected(record, claim):
    altered = copy.deepcopy(record)
    if claim == "clock":
        altered["trace"]["steps"][10]["after_elapsed_s"] += 1e-6
    elif claim == "density":
        altered["trace"]["steps"][10]["density_mol_per_m2_s"][0][0] += 1e-3
    else:
        altered["trace"]["steps"][10]["after"]["inside_mM"][0][0] += 1
    checks = arithmetic.Checks()
    try:
        arithmetic.native_record(
            evidence.trusted_registration(),
            altered,
            {"id": "passive", "availability": 1},
            "matched_constants",
            0.00000625,
            checks,
        )
    except ValueError:
        return
    assert checks.failed_count > 0


def test_changed_summary_is_not_an_authenticated_capture(packet):
    comparison = c.read(packet / "comparison.json")
    comparison["maximum_normalized_error"] = 0
    replace_json(packet / "comparison.json", comparison)
    rehash(packet)
    evidence.inspect_packet(packet)
    with pytest.raises(ValueError, match="capture anchor"):
        evidence.audit(packet)
