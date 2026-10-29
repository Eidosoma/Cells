"""Durable, non-overwriting excision events with both complete checkpoints."""

import hashlib
import json
from pathlib import Path

import numpy as np

from cells.core.excision import (
    excise,
    is_active,
    is_calcium,
    is_calcium_energy,
    is_calcium_energy_mitochondria,
    is_calcium_energy_regulated_v2,
    is_calcium_energy_transport,
    is_calcium_energy_water,
)
from cells.core.specs import ConfigError
from cells.io import load_snapshot, write_snapshot

KIND = "cells.passive_tissue_excision@1"
ACTIVE_KIND = "cells.active_tissue_excision@1"
CALCIUM_KIND = "cells.calcium_tissue_excision@1"
CALCIUM_ENERGY_KIND = "cells.calcium_energy_tissue_excision@1"
CALCIUM_ENERGY_REGULATED_V2_KIND = "cells.calcium_energy_regulated_v2_tissue_excision@1"
CALCIUM_ENERGY_TRANSPORT_KIND = "cells.calcium_energy_transport_tissue_excision@1"
CALCIUM_ENERGY_MITOCHONDRIA_KIND = "cells.calcium_energy_mitochondria_tissue_excision@1"
CALCIUM_ENERGY_WATER_KIND = "cells.calcium_energy_water_tissue_excision@1"


def _kind(spec):
    if is_calcium_energy_regulated_v2(spec):
        return CALCIUM_ENERGY_REGULATED_V2_KIND
    if is_calcium_energy_water(spec):
        return CALCIUM_ENERGY_WATER_KIND
    if is_calcium_energy_mitochondria(spec):
        return CALCIUM_ENERGY_MITOCHONDRIA_KIND
    if is_calcium_energy_transport(spec):
        return CALCIUM_ENERGY_TRANSPORT_KIND
    if is_calcium_energy(spec):
        return CALCIUM_ENERGY_KIND
    return CALCIUM_KIND if is_calcium(spec) else ACTIVE_KIND if is_active(spec) else KIND


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _same_point(a, b):
    return (
        (a.time, a.step_index, a.event_index) == (b.time, b.step_index, b.event_index)
        and type(a.state) is type(b.state)
        and type(a.layout) is type(b.layout)
        and all(
            np.array_equal(x, y)
            for x, y in zip((*a.state, *a.layout), (*b.state, *b.layout), strict=True)
        )
    )


def _validate(actual, expected):
    if actual.spec != expected.spec or actual.report != expected.report:
        raise ConfigError("Excision output disagrees with its complete source checkpoint")
    if (actual.checkpoint is None) != (expected.checkpoint is None) or (
        actual.checkpoint is not None and not _same_point(actual.checkpoint, expected.checkpoint)
    ):
        raise ConfigError("Excision continuation checkpoint disagrees with physical survivors")


def write_excision(directory, result):
    expected = excise(
        result.source_spec, result.source_checkpoint, result.report["removed_cell_ids"]
    )
    _validate(result, expected)
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    try:
        write_snapshot(root / "before", result.source_spec, result.source_checkpoint)
        if result.spec is not None:
            write_snapshot(root / "after", result.spec, result.checkpoint)
        (root / "transition.json").write_text(
            json.dumps(result.report, indent=2, allow_nan=False) + "\n"
        )
        files = {str(p.relative_to(root)): _hash(p) for p in sorted(root.rglob("*")) if p.is_file()}
        manifest = dict(
            kind=_kind(result.source_spec),
            complete=True,
            source_fingerprint=result.source_spec.fingerprint,
            after_fingerprint=result.spec.fingerprint if result.spec is not None else None,
            absolute_time_s=result.source_checkpoint.time,
            files=files,
        )
        (root / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    except Exception as error:
        (root / "failure.json").write_text(
            json.dumps(dict(type=type(error).__name__, message=str(error)), indent=2) + "\n"
        )
        raise
    return root


def load_excision(directory):
    root = Path(directory)
    manifest = json.loads((root / "manifest.json").read_text())
    if (
        manifest.get("kind")
        not in (
            KIND,
            ACTIVE_KIND,
            CALCIUM_KIND,
            CALCIUM_ENERGY_KIND,
            CALCIUM_ENERGY_REGULATED_V2_KIND,
            CALCIUM_ENERGY_TRANSPORT_KIND,
            CALCIUM_ENERGY_MITOCHONDRIA_KIND,
            CALCIUM_ENERGY_WATER_KIND,
        )
        or manifest.get("complete") is not True
    ):
        raise ConfigError("Require a complete declared tissue excision artifact")
    files = manifest.get("files")
    if not isinstance(files, dict) or "transition.json" not in files:
        raise ConfigError("Excision artifact has no complete file inventory")
    actual = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
    if actual != {*files, "manifest.json"}:
        raise ConfigError("Excision artifact file inventory changed")
    for name, value in files.items():
        if Path(name).is_absolute() or ".." in Path(name).parts or _hash(root / name) != value:
            raise ConfigError("Excision artifact checksum or path disagrees")
    before = load_snapshot(root / "before")
    if manifest["kind"] != _kind(before.spec):
        raise ConfigError("Excision artifact family disagrees with its source")
    report = json.loads((root / "transition.json").read_text())
    result = excise(before.spec, before.checkpoint, report["removed_cell_ids"])
    if (
        result.report != report
        or manifest.get("source_fingerprint") != before.spec.fingerprint
        or manifest.get("after_fingerprint")
        != (result.spec.fingerprint if result.spec is not None else None)
        or manifest.get("absolute_time_s") != result.source_checkpoint.time
    ):
        raise ConfigError("Excision manifest/transition does not match its source")
    if result.spec is not None:
        after = load_snapshot(root / "after")
        if after.spec != result.spec or not _same_point(after.checkpoint, result.checkpoint):
            raise ConfigError("Saved post-cut checkpoint changed physical state or clock")
    return result
