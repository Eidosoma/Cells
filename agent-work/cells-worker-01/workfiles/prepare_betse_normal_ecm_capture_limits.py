# ruff: noqa: E501
"""Prepare only new evidence helpers; preserve all frozen packets and catalog32768."""

import json
import shutil

from betse_normal_ecm_capture_limits_audit import BASE, PREFIX, WORK, row, sha

OUT = WORK / (PREFIX + "_prepared_01")
BASELINE = BASE / "ecm-catalog-archive-cardinality-repair-20261031-01"

PROFILE = '''"""Profile-scoped metadata binding for pinned uncompressed capture writers."""

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

import archive_binding as core

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_profile(profile):
    contract = json.loads((HERE / "inputs.json").read_text())
    if profile not in contract["profiles"]:
        raise ValueError("Select an explicit non-catalog capture profile")
    for name, expected in contract["tool_sha256"].items():
        if sha(HERE / name) != expected:
            raise ValueError("Changed prospective capture tool: " + name)
    if Path(core.__file__).resolve() != HERE / "archive_binding.py":
        raise ValueError("Wrong archive binder module was loaded")
    decoder = sys.modules[core.array_header.__module__]
    if sha(decoder.__file__) != contract["tool_sha256"]["qualification_typed_evidence.py"]:
        raise ValueError("Changed array header decoder")
    accounting = json.loads((HERE / "accounting.json").read_text())
    for path, expected in accounting["source_sha256"].items():
        if sha(path) != expected:
            raise ValueError("Changed pinned producer/format source: " + path)
    if core.MAX_MEMBERS != 310689 or core.MAX_BYTES != 64 * 2**20:
        raise ValueError("Unexpected fixed capture limits")
    return contract


def bind(folder, *, profile):
    verify_profile(profile)
    result = core.bind(folder)
    # The byte accounting is specific to the pinned np.savez producer. These
    # checks additionally enforce its format policy on the evidence itself.
    with zipfile.ZipFile(Path(folder) / "arrays.npz") as archive:
        if any(item.compress_type != zipfile.ZIP_STORED or item.file_size < 128
               for item in archive.infolist()):
            raise ValueError("Capture profile requires uncompressed NPY members of at least128 bytes")
    result.update(
        capture_profile=profile,
        fixed_member_limit=310689,
        source_format_capacity_bound=True,
        observed_case_maximum_claim=False,
        physical_or_numerical_qualification_credit=False,
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = bind(args.archive, profile=args.profile)
    with args.output.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\\n")
'''


def prepare():
    proof = WORK / (PREFIX + "_accounting_01.json")
    accounting = json.loads(proof.read_text())
    assert accounting["capacity_derivation"]["new_fixed_member_limit"] == 310689
    review = BASELINE / "root-review-01/REVIEW.json"
    assert sha(review) == "0f8a681b50d57e88adc3617099e2a1fc39ad269d6b72a9414c3583254fcf3744"
    before = (BASELINE / "archive_binding.py").read_bytes()
    assert (
        sha(BASELINE / "archive_binding.py")
        == "e25aaedfe6b9255740bcdb83acc36a35d5e31e1741507dd01e03488ab2e26e59"
    )
    assert before.count(b"MAX_MEMBERS=32768") == 1
    after = before.replace(b"MAX_MEMBERS=32768", b"MAX_MEMBERS=310689", 1)
    assert after.replace(b"MAX_MEMBERS=310689", b"MAX_MEMBERS=32768", 1) == before
    OUT.mkdir(exist_ok=False)
    (OUT / "archive_binding.py").write_bytes(after)
    shutil.copy2(
        BASELINE / "qualification_typed_evidence.py", OUT / "qualification_typed_evidence.py"
    )
    shutil.copy2(proof, OUT / "accounting.json")
    (OUT / "capture_binding.py").write_text(PROFILE)
    import subprocess

    subprocess.run(
        [
            "/mnt/workspaces/Cells/venv-cpu/bin/ruff",
            "format",
            "--no-cache",
            str(OUT / "capture_binding.py"),
        ],
        check=True,
        capture_output=True,
    )
    contract = dict(
        kind="cells.prospective_non_catalog_capture_capacity_tools@1",
        status="prepared_source_and_metadata_only_review_required",
        accounting=row(OUT / "accounting.json"),
        baseline_catalog_helper=row(BASELINE / "archive_binding.py"),
        baseline_catalog_review=row(review),
        tool_sha256={
            name: sha(OUT / name)
            for name in (
                "archive_binding.py",
                "qualification_typed_evidence.py",
                "capture_binding.py",
                "accounting.json",
            )
        },
        profiles=accounting["scope_profiles"],
        member_limit=310689,
        catalogue_member_limit_unchanged=32768,
        candidate_only_named_member_constant_changed=True,
        entire_helper_inverse_bytes_exact=True,
        unchanged_JSON_archive_expanded_bytes=64 * 2**20,
        unchanged_NPY_header_bytes=16384,
        unchanged_type_shape_depth_owner_hash_and_CRC_guards=True,
        wrapper_adds_pinned_source_and_uncompressed_writer_profile_checks=True,
        all_captures_fit_existing_byte_limits_claim=False,
        no_case_member_maximum_or_model_equation_claim=True,
        external_existing_CPU_memory_walltime_and_reserve_limits_required=True,
        frozen_packets_and_live_shared_helpers_modified=False,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
        new_or_retained_qualification_passes=0,
        release_authorized=False,
        automatic_launch=False,
        automatic_polling=False,
        automatic_followup=False,
    )
    with (OUT / "inputs.json").open("x") as stream:
        json.dump(contract, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                inputs=str(OUT / "inputs.json"),
                sha256=sha(OUT / "inputs.json"),
                member_limit=310689,
                scientific_imports=0,
                numerical_runs=0,
            )
        )
    )


if __name__ == "__main__":
    prepare()
