"""Complete finite-pool state, authenticated before continuation."""

import json
import os
import zipfile
from pathlib import Path

import numpy as np

from cells.assembly.io import digest, runtime, write_json
from cells.assembly.io import source_identity as baseline_identity
from cells.assembly.spec import AssemblyError
from cells.assembly_pool.engine import validate_state
from cells.assembly_pool.kernel import PoolState
from cells.assembly_pool.spec import parse_spec

FORMAT = "cells_finite_bond_checkpoint@1"
RNG = "threefry2x32_fold_in_seed_world_event_open52@1"


def source_identity():
    # Include the reused graph, RNG, device, runtime and artifact helpers.
    result = {"../assembly/" + k: v for k, v in baseline_identity().items()}
    result.update({p.name: digest(p) for p in sorted(Path(__file__).parent.glob("*.py"))})
    return result


def write_checkpoint(path, spec, state, *, execution, provenance=None):
    values = validate_state(spec, state)
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    with (path / "state.npz").open("xb") as stream:
        with zipfile.ZipFile(
            stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1
        ) as archive:
            for name, value in values._asdict().items():
                with archive.open(f"{name}.npy", "w", force_zip64=True) as member:
                    np.lib.format.write_array(member, value, allow_pickle=False)
        stream.flush()
        os.fsync(stream.fileno())
    record = {
        "format": FORMAT,
        "definition": spec.to_dict(),
        "definition_sha256": spec.fingerprint,
        "sources_sha256": source_identity(),
        "state_sha256": digest(path / "state.npz"),
        "runtime": runtime(),
        "execution": execution,
        "provenance": provenance or {},
        "rng": RNG,
        "world_ids": {"first": spec.world_id_start, "count": spec.worlds},
        "complete_state_includes_pending_event_and_finite_material": True,
    }
    write_json(path / "manifest.json", record)
    return digest(path / "manifest.json")


def load_checkpoint(path):
    path = Path(path)
    record = json.loads((path / "manifest.json").read_text())
    if record.get("format") != FORMAT:
        raise AssemblyError("Unsupported finite-bond checkpoint")
    spec = parse_spec(record["definition"])
    expected = {
        "definition_sha256": spec.fingerprint,
        "sources_sha256": source_identity(),
        "runtime": runtime(),
        "state_sha256": digest(path / "state.npz"),
        "rng": RNG,
        "world_ids": {"first": spec.world_id_start, "count": spec.worlds},
    }
    for key, value in expected.items():
        if record.get(key) != value:
            raise AssemblyError(f"Checkpoint {key} mismatch; preserved source/runtime required")
    with zipfile.ZipFile(path / "state.npz") as archive:
        expected_files = {name + ".npy" for name in PoolState._fields}
        entries = archive.infolist()
        if (
            len(entries) != len(expected_files)
            or {item.filename for item in entries} != expected_files
        ):
            raise AssemblyError("Checkpoint fields differ from complete finite-pool state")
        if sum(item.file_size for item in entries) > spec.worlds * 2048 + 65536:
            raise AssemblyError("Checkpoint exceeds uncompressed array budget")
    with np.load(path / "state.npz", allow_pickle=False) as arrays:
        state = PoolState(*(arrays[name].copy() for name in PoolState._fields))
    return spec, validate_state(spec, state), digest(path / "manifest.json")
