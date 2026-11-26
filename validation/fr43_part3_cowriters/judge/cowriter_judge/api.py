"""The judge's passes, as functions: the references through C0, the tables through the reader, then the scorer.

A reference refused by C0 refuses the comparison of its world: the scorer is handed None for it, and every entry
of that world is unformed (its arm inconclusive at best).
"""

from __future__ import annotations

import os
from typing import Any

from . import strictjson as sj
from .c0 import c0_reference_file
from .reference import ReferenceWorld
from .registry import Inputs
from .score import RETRY_KIND, Judge
from .table import read_folder, structure_report


def references_through_c0(inputs: Inputs, reference_paths: dict[str, str], draws_path: str,
                          invented_file: str | None = None) -> tuple[dict[str, ReferenceWorld | None], dict]:
    """Each world's reference, read and checked by C0. `reference_paths` maps world to its file; for the invented
    set give `invented_file` instead (one object, world name to layout)."""
    kept: dict[str, ReferenceWorld | None] = {}
    results: dict[str, Any] = {}
    if invented_file is not None:
        results["reference_invented.json"] = c0_reference_file(invented_file, inputs, draws_path, invented=True,
                                                               keep=kept)
    else:
        for world, path in reference_paths.items():
            results[os.path.basename(path)] = c0_reference_file(path, inputs, draws_path, invented=False, keep=kept)
    refs = {world: kept.get(world) for world in inputs.worlds}
    return refs, results


def judge_pass(inputs: Inputs, references: dict[str, ReferenceWorld | None], table_dir: str,
               operators: dict[str, list[str]], registration_revision: str | None, rehearsal: bool,
               lead_record: dict[str, str] | None = None, sample_hashes: set[str] | None = None,
               retry_dir: str | None = None, retry_owed: dict | None = None) -> dict:
    """The first pass (retry_owed None) or the retry pass (with the first pass's retry_owed.json)."""
    worlds = list(inputs.worlds)
    tables = read_folder(table_dir, worlds, lead_record, sample_hashes or set(), False, inputs.arms)
    judge = Judge(inputs, references, operators, registration_revision, rehearsal, retry_owed)
    judge.add_tables(tables)
    if retry_dir is not None and os.path.isdir(retry_dir):
        judge.add_tables(read_folder(retry_dir, worlds, lead_record, sample_hashes or set(), False, inputs.arms))
    record = judge.score()
    record["tables"] = {t.name: t.sha256 for t in judge.tables}
    record["inputs_sha256"] = inputs.sha256
    return record


def retry_owed_file(record: dict) -> dict:
    """CRITERIA.md §7: {"kind", "families", "runs"}, from the first pass alone."""
    owed = record["retry_owed"]
    return {"kind": RETRY_KIND, "families": list(owed["families"]), "runs": sorted(owed["runs"])}


def read_retry_owed(path: str) -> dict:
    data = sj.load_file(path).data
    if data.get("kind") != RETRY_KIND:
        raise ValueError(f"{path} is not a retry file of version 2")
    return data


def format_sample(folder: str, inputs: Inputs, recorded: dict[str, str] | None = None) -> dict:
    """TABLE.md §5: recompute the hashes and read every file with the registered tables' code, structure only."""
    worlds = list(inputs.worlds)
    report: dict[str, Any] = {"folders": {}}
    kinds = {name: world.kind for name, world in inputs.worlds.items()}
    for sub in ("table", "table-retry"):
        path = os.path.join(folder, sub)
        if not os.path.isdir(path):
            report["folders"][sub] = {"absent": True}
            continue
        tables = read_folder(path, worlds, None, set(), True, inputs.arms)
        rep = structure_report(tables, inputs.arms, kinds)
        if recorded is not None:
            for table in tables:
                expected = recorded.get(f"{sub}/{table.name}") or recorded.get(table.name)
                if expected is None or expected.lower() != table.sha256:
                    rep["departures"].append({"table": table.name, "row": "hash", "effect": "refused",
                                              "where": table.name, "message": "departs from the lead's note"})
            rep["passes"] = not rep["departures"]
        report["folders"][sub] = rep
    report["passes"] = all(r.get("passes", True) for r in report["folders"].values()) and any(
        not r.get("absent") for r in report["folders"].values())
    return report
