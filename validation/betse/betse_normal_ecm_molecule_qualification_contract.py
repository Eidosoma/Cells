# ruff: noqa: C408
"""Exact reviewed source/profile pins and admission for held future runners."""

import hashlib
import json
import os
import re
import sys
from pathlib import Path

PREFIX = "betse_normal_ecm_molecule_qualification"
HANDOFF = Path("/mnt/workspaces/Cells/ecm-molecule03-successors-20261031-01/SOURCE_SUCCESSORS.json")
HANDOFF_SHA = "5a35937f13d276d6b009ed739ec16d4f33c1d82b95474a27175ac3a933c5e0ed"
REVIEW_SHA = "324301303c8ef5931afa28462a6ac34eb429897d6cd22cf0f2bbea6ac7de2c7d"


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


def verify_packet(row):
    packet = Path(row["packet"])
    for key in ("manifest", "inputs", "source_receipt"):
        require(sha(row[key]["path"]) == row[key]["sha256"], "Reviewed packet descriptor changed")
    manifest = read(packet / "MANIFEST.json")
    require(not any((p.is_symlink() for p in packet.rglob("*"))), "Packet symlinks are refused")
    require(
        set((p.relative_to(packet).as_posix() for p in packet.rglob("*") if p.is_file()))
        == set(manifest["files"]) | {"MANIFEST.json"},
        "Packet member set changed",
    )
    for name, pin in manifest["files"].items():
        require(sha(packet / name) == pin, "Packet member changed: " + name)
    inputs = read(packet / "inputs.json")
    family = row["family"]
    require(family in ("dispatch", "transport"), "Separate reviewed family required")
    require(
        inputs["capture_profile"]
        == row["capture_profile"]
        == "ordinary_ecm_molecule_" + family + "_03",
        "Exact profile03 required",
    )
    tools = read(packet / "tools/inputs.json")
    require(set(tools["profiles"]) == {row["capture_profile"]}, "Wrong capture profile family")
    for name, pin in inputs["source_sha256"].items():
        require(sha(packet / "source" / name) == pin, "Frozen source changed")
    require(inputs["planned"] == row["prospective"], "Frozen prospective counts changed")
    require(
        len(inputs["groups"]) == (44 if family == "dispatch" else 60),
        "Exact family roster required",
    )
    ids = [node for group in inputs["groups"].values() for node in group["node_ids"]]
    require(len(ids) == len(set(ids)) == len(inputs["groups"]), "Exact unique node IDs required")
    return inputs


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


def verify_release(bundle, request):
    """Admission is checked before any run directory, subprocess or science import."""
    require(request.get("requested_round") is True, "Held: explicit requested round required")
    release_path = request.get("release_path")
    require(
        isinstance(release_path, str) and release_path,
        "Held: separate Chief release contract required",
    )
    require(
        not Path(release_path).resolve().is_relative_to(Path(bundle).resolve()),
        "External release must not modify the held bundle",
    )
    require(sha(release_path) == request.get("release_sha256"), "Changed explicit release contract")
    release = read(release_path)
    require(
        release.get("kind") == "cells.explicit_molecule_scientific_round_release@1"
        and release.get("status") == "explicitly_released",
        "Held: source preparation is not release",
    )
    require(
        release.get("runner_manifest_sha256") == sha(Path(bundle) / "MANIFEST.json"),
        "Release is for another runner",
    )
    require(
        isinstance(release.get("user_request"), str) and release["user_request"].strip(),
        "Release requires actual user request provenance",
    )
    require(
        request["families"]
        and len(request["families"]) == len(set(request["families"]))
        and (set(request["families"]) <= {"dispatch", "transport"}),
        "Distinct explicit families required",
    )
    for key in ("families", "cpu", "output", "round_id"):
        require(request.get(key) == release.get(key), "Release differs from exact requested " + key)
    require(
        type(request["cpu"]) is int and request["cpu"] in os.sched_getaffinity(0),
        "Coordinated allowed CPU required",
    )
    require(
        isinstance(request["round_id"], str)
        and re.fullmatch("[a-zA-Z0-9_-]{1,80}", request["round_id"]),
        "Bounded explicit round ID required",
    )
    require(Path(request["output"]).is_absolute(), "Explicit absolute output required")
    require(
        Path(request["output"]).resolve() != Path(bundle).resolve()
        and (not Path(request["output"]).resolve().is_relative_to(Path(bundle).resolve())),
        "Immutable runner cannot be output",
    )
    inputs = verify_bundle(bundle)
    output_location(bundle, inputs, request["output"])
    require(
        Path(bundle).resolve() == Path(inputs["bundle_destination"]).resolve(),
        "Release must select the exact frozen runner location",
    )
    require(
        release.get("packet_manifests")
        == {f: inputs["packets"][f]["manifest"]["sha256"] for f in request["families"]},
        "Release packet/profile association differs",
    )
    require(
        sha(Path(sys.executable).resolve()) == inputs["interpreter"]["sha256"],
        "Runner interpreter changed",
    )
    return inputs
