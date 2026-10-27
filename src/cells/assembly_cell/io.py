"""Lossless whole-world checkpoints with common clock, both components and ledgers."""

import json
import os
import zipfile
from pathlib import Path

import numpy as np

from cells.assembly.io import digest, runtime, write_json
from cells.assembly.spec import AssemblyError

FORMAT = "cells_assembly_cell_checkpoint@1"
CLUSTER_FORMAT = "cells_assembly_cluster_checkpoint@1"


def implementation(cluster):
    if cluster:
        from cells.assembly_cluster import engine, spec
    else:
        from cells.assembly_cell import engine, spec
    return engine, spec


def clock_identity(cluster, spec=None):
    if cluster and spec is not None and len(spec.ionic.experiment.changes) > 1:
        return "global_ionic_grid_split_at_union_of_cell_assembly_and_control_events@1"
    return (
        "global_ionic_grid_split_at_union_of_cell_assembly_events@1"
        if cluster
        else "global_ionic_grid_split_at_exact_assembly_events@1"
    )


def rng_identity(cluster):
    return (
        "threefry2x32_fold_in_seed_plus_cell_stream_mod32_world_event_open52@1"
        if cluster
        else "threefry2x32_fold_in_seed_world_event_open52@1"
    )


def source_identity():
    root = Path(__file__).resolve().parents[1]
    return {str(p.relative_to(root)): digest(p) for p in sorted(root.rglob("*.py"))}


def flatten(state):
    result = {"pool_" + k: v for k, v in state.pool._asdict().items()}
    result.update({"ionic_" + k: v for k, v in state.ionic._asdict().items()})
    result.update({k: v for k, v in state._asdict().items() if k not in ("pool", "ionic")})
    return result


def write_checkpoint(path, spec, state, *, backend, provenance=None):
    model = spec.to_dict()["model"]
    if model not in ("assembly_regulated_cell@1", "assembly_regulated_cluster@1"):
        raise AssemblyError("Unsupported coupled checkpoint model")
    cluster = model == "assembly_regulated_cluster@1"
    engine, _ = implementation(cluster)
    state, _ = engine.validate_state(spec, state)
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    with (path / "state.npz").open("xb") as stream:
        with zipfile.ZipFile(
            stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1
        ) as archive:
            for name, value in flatten(state).items():
                with archive.open(name + ".npy", "w", force_zip64=True) as member:
                    np.lib.format.write_array(member, value, allow_pickle=False)
        stream.flush()
        os.fsync(stream.fileno())
    write_json(
        path / "manifest.json",
        {
            "format": CLUSTER_FORMAT if cluster else FORMAT,
            "definition": spec.to_dict(),
            "definition_sha256": spec.fingerprint,
            "sources_sha256": source_identity(),
            "runtime": runtime(),
            "backend": backend,
            "state_sha256": digest(path / "state.npz"),
            "provenance": provenance,
            "clock": clock_identity(cluster, spec),
            "rng": rng_identity(cluster),
        },
    )
    return digest(path / "manifest.json")


def load_checkpoint(path, *, backend):
    path = Path(path)
    record = json.loads((path / "manifest.json").read_text())
    if record.get("format") not in (FORMAT, CLUSTER_FORMAT):
        raise AssemblyError("Unsupported assembly-cell checkpoint")
    cluster = record["format"] == CLUSTER_FORMAT
    engine, definitions = implementation(cluster)
    spec = definitions.parse_spec(record["definition"])
    for key, expected in {
        "definition_sha256": spec.fingerprint,
        "sources_sha256": source_identity(),
        "runtime": runtime(),
        "backend": backend,
        "state_sha256": digest(path / "state.npz"),
        "clock": clock_identity(cluster, spec),
        "rng": rng_identity(cluster),
    }.items():
        if record.get(key) != expected:
            raise AssemblyError(
                f"Coupled checkpoint {key} mismatch; use preserved source/backend/runtime"
            )
    template = engine.initial_state(spec)
    expected_fields = flatten(template)
    with zipfile.ZipFile(path / "state.npz") as archive:
        members = archive.infolist()
        if (
            len(members) != len(expected_fields)
            or {m.filename for m in members} != {k + ".npy" for k in expected_fields}
            or sum(m.file_size for m in members)
            > sum(v.nbytes for v in expected_fields.values()) + 65536
        ):
            raise AssemblyError("Coupled checkpoint fields or uncompressed budget mismatch")
    with np.load(path / "state.npz", allow_pickle=False) as arrays:
        components = [
            type(getattr(template, name))(
                *(arrays[name + "_" + k].copy() for k in getattr(template, name)._fields)
            )
            for name in ("pool", "ionic")
        ]
        state = type(template)(*components, *(arrays[k].copy() for k in template._fields[2:]))
    return spec, engine.validate_state(spec, state)[0], digest(path / "manifest.json")
