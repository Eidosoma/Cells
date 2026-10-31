# ruff: noqa: C408
import hashlib
import json
import os
from pathlib import Path

PREFIX = "betse_normal_ecm_molecule_events_execution"


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    path = Path(path)
    require(
        path.is_file() and (not path.is_symlink()), "Regular pinned file required: " + str(path)
    )
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    path = Path(path)
    require(
        path.is_file() and (not path.is_symlink()) and (path.stat().st_size <= 64 * 2**20),
        "Bounded regular JSON required",
    )

    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result

    def bad(value):
        raise ValueError("Nonfinite JSON scalar: " + value)

    return json.loads(path.read_text(), object_pairs_hook=pairs, parse_constant=bad)


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def verify_bundle(folder):
    folder = Path(folder).resolve()
    manifest = read(folder / "MANIFEST.json")
    require(not any((p.is_symlink() for p in folder.rglob("*"))), "Runner symlinks are refused")
    require(
        {str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file()}
        == set(manifest["files"]) | {"MANIFEST.json"},
        "Exact runner member set changed",
    )
    for name, pin in manifest["files"].items():
        require(sha(folder / name) == pin, "Runner bundle changed: " + name)
    return read(folder / "inputs.json")


def output_location(bundle, inputs, output):
    target = Path(output).resolve()
    require(not target.is_relative_to(Path(bundle).resolve()), "Immutable runner cannot be output")
    for packet in inputs["packets"].values():
        require(
            not target.is_relative_to(Path(packet["packet"]).resolve()),
            "Immutable source packet cannot be output",
        )


def held():
    raise ValueError(
        "Hard-held events57: Root review and explicit successor required before science."
    )


def verify_release(bundle, request):
    held()


def initial_outcomes(inputs):
    return {
        family: dict(
            status="unrun",
            family=family,
            completed_groups=[],
            passed_checks=0,
            accepted_calls=0,
            independent_accuracy_credit=0,
            inherited_accuracy_credit=0,
            prerequisites=inputs["prerequisites"][family],
            execution_hold=True,
        )
        for family in inputs["packets"]
    }


def verify_packet(row):
    packet = Path(row["packet"])
    for key in ("manifest", "inputs", "source_receipt"):
        require(sha(row[key]["path"]) == row[key]["sha256"], "Frozen family descriptor changed")
    manifest = read(packet / "MANIFEST.json")
    require(not any((p.is_symlink() for p in packet.rglob("*"))), "Frozen packet symlinks refused")
    require(
        {str(p.relative_to(packet)) for p in packet.rglob("*") if p.is_file()}
        == set(manifest["files"]) | {"MANIFEST.json"},
        "Frozen family member set changed",
    )
    for name, pin in manifest["files"].items():
        require(sha(packet / name) == pin, "Frozen family member changed: " + name)
    inputs = read(packet / "inputs.json")
    require(inputs["planned"] == row["prospective"], "Frozen family plan changed")
    require(len(inputs["groups"]) == row["checks"], "Frozen family check count changed")
    ids = [node for group in inputs["groups"].values() for node in group["node_ids"]]
    require(
        len(ids) == len(set(ids)) == row["checks"], "Exact separate unique family roster required"
    )
    require(
        set(read(packet / "tools/inputs.json")["profiles"]) == {row["capture_profile"]},
        "Exact family capture profile required",
    )
    for name, pin in inputs["source_sha256"].items():
        require(sha(packet / "source" / name) == pin, "Frozen scientific source changed")
    return inputs
