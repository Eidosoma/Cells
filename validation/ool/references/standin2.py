"""The OL2/OL3 stand-in: canonical records written from the references' own law and runs, honest or
with one planted form, so that every row of ``harness2`` can be exercised end to end before an
engine exists. Its draws are NumPy's (``population.HostStreams``), not the engine's threefry.

    python -m validation.ool.references.standin2 --out DIR [--planted FORM]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from . import ol2_checks as OC
from . import ol3_checks as O3
from . import population as P
from . import refusals2
from . import registered2 as R2
from .ol2 import Law2
from .records import MANIFEST

KERNEL_WORLDS = ("ol2_wa", "ol2_wa_diffusion", "ol2_closed", "ol2_two")


def _manifest(d: Path, files) -> None:
    (d / MANIFEST).write_text(json.dumps({"files": sorted(files)}) + "\n")


def write_kernel(root: Path, world: str, law_planted: str | None = None) -> Path:
    from .harness2 import registered_states

    d = root / "kernel" / world
    d.mkdir(parents=True, exist_ok=True)
    w = R2.worlds()[world]
    states = registered_states(world)
    t = OC.kernel_table(Law2(w, law_planted), states)
    flat = np.array([list(a) + list(b) + list(c) for a, b, c in states], dtype=np.int64)
    np.savez(d / "probe.npz", input_states=flat, **t)
    (d / "probe.json").write_text(json.dumps({"world": world, "steps": [c.id for c in w.vesicle_channels()]}) + "\n")
    _manifest(d, ["probe.npz", "probe.json"])
    return d


def write_run(root: Path, run: str, planted: str | None = None, law_planted: str | None = None) -> Path:
    d = root / "runs" / run
    d.mkdir(parents=True, exist_ok=True)
    spec = R2.runs()[run]
    tr = P.simulate(spec, P.HostStreams(spec.seed), planted, law_planted)
    (d / "trace.json").write_text(json.dumps(tr) + "\n")
    _manifest(d, ["trace.json"])
    return d


def write_partition(root: Path, planted: str | None = None, M: int = R2.PARTITION_ATTEMPTS) -> Path:
    d = root / "partition"
    d.mkdir(parents=True, exist_ok=True)
    arr = {}
    for i, p in enumerate(R2.OL3_PARENTS):
        att = O3.standin_attempts(p, M, 7, 100 + i, planted)
        arr[f"{p['id']}_u"] = np.array([a["u"] for a in att])
        arr[f"{p['id']}_membrane"] = np.array([a["membrane"] for a in att], dtype=np.int64)
        arr[f"{p['id']}_lumen"] = np.array([a["lumen"] for a in att], dtype=np.int64)
    np.savez(d / "partition.npz", **arr)
    _manifest(d, ["partition.npz"])
    return d


def write_refusals(root: Path, accept: str | None = None) -> Path:
    d = root / "refusals"
    d.mkdir(parents=True, exist_ok=True)
    rec = {}
    for doc in refusals2.registered_documents():
        try:
            refusals2.validate(doc)
            rec[doc["id"]] = {"refused": False, "message": ""}
        except refusals2.Refused as exc:
            rec[doc["id"]] = {"refused": doc["id"] != accept, "message": str(exc)}
    (d / "refusals.json").write_text(json.dumps(rec, indent=1) + "\n")
    _manifest(d, ["refusals.json"])
    return d


def build(root, planted: str | None = None, law_planted: str | None = None, partition_planted: str | None = None,
          runs=None) -> Path:
    root = Path(root)
    for world in KERNEL_WORLDS:
        write_kernel(root, world, law_planted)
    for run in runs or R2.runs():
        write_run(root, run, planted, law_planted)
    write_partition(root, partition_planted)
    write_refusals(root)
    return root


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--planted", default=None)
    ap.add_argument("--law-planted", default=None)
    ap.add_argument("--partition-planted", default=None)
    a = ap.parse_args(argv)
    build(a.out, a.planted, a.law_planted, a.partition_planted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
