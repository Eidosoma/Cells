# ruff: noqa: C408
"""Profile-scoped metadata binding for pinned uncompressed capture writers."""

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

if __package__:
    from . import archive_binding as core
else:
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
        if sha(Path(path) if Path(path).is_absolute() else HERE.parent / path) != expected:
            raise ValueError("Changed pinned producer/format source: " + path)
    if core.MAX_MEMBERS != 310689 or core.MAX_BYTES != 64 * 2**20:
        raise ValueError("Unexpected fixed capture limits")
    return contract


def bind(folder, *, profile):
    verify_profile(profile)
    result = core.bind(folder)
    with zipfile.ZipFile(Path(folder) / "arrays.npz") as archive:
        if any(
            (
                item.compress_type != zipfile.ZIP_STORED or item.file_size < 128
                for item in archive.infolist()
            )
        ):
            raise ValueError(
                "Capture profile requires uncompressed NPY members of at least128 bytes"
            )
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
        stream.write("\n")
