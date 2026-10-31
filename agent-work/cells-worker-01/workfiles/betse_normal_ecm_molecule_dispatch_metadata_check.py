"""Bounded stdlib controls for the held driver and new INIT capture profile.

Only synthetic scalar archive metadata is constructed. No scientific module,
fixture, source AST, reference, model or pytest is evaluated or collected.
"""

import argparse
import hashlib
import json
import os
import resource
import struct
import subprocess
import sys
import time
import zipfile
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def specimen(path, *, compression=zipfile.ZIP_STORED, wrong_shape=False):
    path.mkdir()
    text = b"{'descr': '<f8', 'fortran_order': False, 'shape': (), }"
    length = 128 - 10
    header = text + b" " * (length - len(text) - 1) + b"\n"
    npy = (
        b"\x93NUMPY" + bytes((1, 0)) + struct.pack("<H", length) + header + struct.pack("<d", 0.125)
    )
    with zipfile.ZipFile(path / "arrays.npz", "x", compression=compression) as archive:
        archive.writestr("a0.npy", npy)
    write(
        path / "data.json",
        dict(mapping=[["value", dict(array="a0", dtype="<f8", shape=[1] if wrong_shape else [])]]),
    )
    write(
        path / "manifest.json",
        dict(
            kind="cells.betse_normal_current_raw_evidence@1",
            complete=True,
            files={name: sha(path / name) for name in ("data.json", "arrays.npz")},
        ),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 512 * 2**20))
    package = args.prepared.resolve()
    target = args.out.resolve()
    if target.exists():
        raise ValueError("Use an exclusive metadata-evidence directory")
    target.mkdir()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(package / "tools"))
    import capture_binding

    before = sha(package / "MANIFEST.json")
    controls = []
    valid = target / "scalar"
    specimen(valid)
    result = capture_binding.bind(valid, profile="ordinary_ecm_molecule_dispatch_01")
    controls.append(
        dict(
            name="general_molecule_profile_accepts_scalar",
            passed=result["capture_profile"] == "ordinary_ecm_molecule_dispatch_01",
            result=result,
        )
    )

    def refuses(name, action):
        try:
            action()
        except ValueError as error:
            controls.append(dict(name=name, passed=True, cause=str(error)))
        else:
            raise AssertionError("Expected named metadata refusal: " + name)

    refuses(
        "catalog_profile_cannot_select_INIT_tool",
        lambda: capture_binding.bind(valid, profile="catalog05"),
    )
    compressed = target / "compressed"
    specimen(compressed, compression=zipfile.ZIP_DEFLATED)
    refuses(
        "compressed_writer_refusal",
        lambda: capture_binding.bind(compressed, profile="ordinary_ecm_molecule_dispatch_01"),
    )
    wrong = target / "wrong_shape"
    specimen(wrong, wrong_shape=True)
    refuses(
        "descriptor_shape_refusal",
        lambda: capture_binding.bind(wrong, profile="ordinary_ecm_molecule_dispatch_01"),
    )
    damaged = target / "damaged_hash"
    specimen(damaged)
    with (damaged / "arrays.npz").open("ab") as stream:
        stream.write(b"changed")
    refuses(
        "payload_hash_refusal",
        lambda: capture_binding.bind(damaged, profile="ordinary_ecm_molecule_dispatch_01"),
    )
    maximum = (64 * 2**20 - 22) // 216
    assert maximum == 310689
    for count, expected in ((310688, True), (310689, True), (310690, False)):
        accepted = count * 216 + 22 <= 64 * 2**20
        controls.append(
            dict(
                name="format_capacity_endpoint_" + str(count),
                passed=accepted is expected,
                scalar_predicate_only=True,
                full_size_archive_constructed=False,
            )
        )
    held = package / "run-positive-general_only"
    assert not held.exists()
    command = [
        sys.executable,
        "-B",
        str(package / "driver.py"),
        "--group",
        "positive-general_only",
        "--requested-round",
        "--coordinated-cpu",
        str(min(os.sched_getaffinity(0))),
    ]
    probe = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=10,
        check=False,
    )
    (target / "held-driver.log").write_text(probe.stdout)
    controls.append(
        dict(
            name="held_driver_refuses_before_run_directory",
            passed=probe.returncode != 0
            and "General-molecule source handoff is held" in probe.stdout
            and not held.exists(),
            returncode=probe.returncode,
        )
    )
    assert sha(package / "MANIFEST.json") == before
    manifest = json.loads((package / "MANIFEST.json").read_text())
    for name, pin in manifest["files"].items():
        assert sha(package / name) == pin, name
    controls.append(
        dict(name="complete_prepared_manifest_unchanged", passed=True, files=len(manifest["files"]))
    )
    assert all(row["passed"] for row in controls)
    assert not any(
        name.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "pytest"}
        for name in sys.modules
    )
    write(
        target / "result.json",
        dict(
            kind="cells.general_molecule_metadata_controls@1",
            status="passed",
            controls=controls,
            elapsed_s=time.monotonic() - started,
            max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
            cpu_limit_s=30,
            address_space_limit_bytes=512 * 2**20,
            scientific_imports=0,
            scientific_AST_executions=0,
            fixture_reference_model_evaluations=0,
            pytest_collections=0,
            numerical_runs=0,
            active_job_queries=0,
            large_capacity_archive_generated=False,
            scientific_qualification_credit=False,
        ),
    )
    print(
        json.dumps(
            dict(status="passed", controls=len(controls), elapsed_s=time.monotonic() - started)
        )
    )


if __name__ == "__main__":
    main()
