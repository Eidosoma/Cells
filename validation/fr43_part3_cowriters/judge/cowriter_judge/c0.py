"""C0 (CRITERIA.md §4.2), the driver: `reference_invented.json` first, then each reference file, then `draws_check`,
`inputs_sha256` and the protocol's hashes. A duplicate key or a non-finite number in a reference file refuses that
file (CRITERIA.md §4). A fault refuses the reference, and a refused reference refuses the comparison of its world.

The invented pair (SPEC.md §8) is checked besides for its own rules: no number equal to a registered number of the
same kind, the retry runs named by the rule, the invented worlds' kinds.
"""

from __future__ import annotations

import os
from typing import Any

from . import strictjson as sj
from .reference import Collector, c0_world, load_draws, read_world
from .registry import Inputs

C0_KIND = "fr43 part 3 co-writers judge C0, version 1"


def _world_result(coll: Collector, summary: dict | None) -> dict:
    disagreements = [c for c in coll.comparisons if not c["agree"]]
    return {
        "refused": bool(coll.faults),
        "faults": [f.as_dict() for f in coll.faults],
        "flags": [f.as_dict() for f in coll.flags],
        "comparisons": len(coll.comparisons),
        "disagreements": disagreements,
        "summary": summary or {},
    }


def c0_reference_file(path: str, inputs: Inputs, draws_path: str, invented: bool,
                      keep: dict | None = None) -> dict:
    """One reference file: the invented file holds world name to layout; a registered file is one world.
    `keep`, where given, receives each world's ReferenceWorld that C0 passed (a refused one is None)."""
    result: dict[str, Any] = {"file": os.path.basename(path), "sha256": None, "refused": False, "file_faults": [],
                              "worlds": {}}
    try:
        loaded = sj.load_file(path)
    except (OSError, sj.StrictJSONError) as exc:
        result["refused"] = True
        result["file_faults"].append({"code": "unreadable", "where": path, "message": str(exc)})
        return result
    result["sha256"] = loaded.sha256
    found = list(sj.problems(loaded.data))
    for where, kind in found:
        result["file_faults"].append({"code": kind, "where": sj.path_text(where),
                                      "message": f"a {kind} in a reference file refuses the file"})
    if found:
        result["refused"] = True
        return result
    data = loaded.data
    if invented:
        if not isinstance(data, dict):
            result["refused"] = True
            result["file_faults"].append({"code": "missing registered key", "where": "<top>",
                                          "message": "the invented file is not an object of worlds"})
            return result
        names = list(inputs.worlds)
        for name in data:
            if name not in inputs.worlds:
                result["file_faults"].append({"code": "unregistered world", "where": name,
                                              "message": "a world the invented inputs do not hold"})
        layouts = [(name, data.get(name)) for name in names]
    else:
        world_name = data.get("world") if isinstance(data, dict) else None
        if world_name not in inputs.worlds:
            result["refused"] = True
            result["file_faults"].append({"code": "unregistered world", "where": "world",
                                          "message": f"{world_name!r} is not a registered world"})
            return result
        layouts = [(world_name, data)]
    for name, obj in layouts:
        coll = Collector()
        where = name
        if obj is None:
            coll.fault("missing registered key", name, "the world is not in the file")
            result["worlds"][name] = _world_result(coll, None)
            continue
        ref = read_world(coll, obj, inputs, name, where)
        summary = None
        if ref is not None:
            draws = load_draws(draws_path, inputs.worlds[name], coll, f"{where}/draws")
            summary = c0_world(coll, ref, inputs, draws, where)
        result["worlds"][name] = _world_result(coll, summary)
        if keep is not None:
            keep[name] = ref if (ref is not None and not coll.faults) else None
    if result["file_faults"] or any(w["refused"] for w in result["worlds"].values()):
        result["refused"] = True
        if keep is not None and result["file_faults"]:
            for name in keep:
                keep[name] = None
    return result


# ---- SPEC.md §8: the invented set's own rules ----

def _numbers_by_kind(data: dict) -> dict[str, list[tuple[str, float]]]:
    """Every registered number of the kinds SPEC.md §8 names (a zero, c0_mM and structural integers are not)."""
    out: dict[str, list[tuple[str, float]]] = {}

    def add(kind: str, where: str, value: Any) -> None:
        if sj.is_number(value) and value != 0:
            out.setdefault(kind, []).append((where, float(value)))

    for name, block in data["worlds"].items():
        w = f"worlds/{name}"
        add("volume", f"{w}/cell_pL", block.get("cell_pL"))
        add("volume", f"{w}/node_pL", block.get("node_pL"))
        add("horizon", f"{w}/end_s", block.get("end_s"))
        for i, h in enumerate(block.get("rungs_s", [])):
            add("rung", f"{w}/rungs_s/{i}", h)
        add("rung", f"{w}/retry_rung_s", block.get("retry_rung_s"))
        for i, t in enumerate(block.get("samples_s", [])):
            add("sample time", f"{w}/samples_s/{i}", t)
        for i, s in enumerate(block.get("seeds", [])):
            add("seed", f"{w}/seeds/{i}", s)
        for key, value in block.get("rows_fmol", {}).items():
            add("amount", f"{w}/rows_fmol/{key}", value)
        for reaction in block.get("reactions", []) or []:
            add("rate", f"{w}/reactions/{reaction.get('id')}/rate_constant", reaction.get("rate_constant"))
        pop = block.get("population", {})
        for channel in pop.get("channels", []):
            add("rate", f"{w}/population/channels/{channel.get('id')}/rate_constant", channel.get("rate_constant"))
        for key, value in pop.get("transfer", {}).get("conductance_pL_per_s", {}).items():
            add("conductance", f"{w}/population/transfer/conductance_pL_per_s/{key}", value)
        gene = block.get("gene")
        if isinstance(gene, dict):
            for key in ("initiation_per_mM_s", "speed_per_s"):
                add("rate", f"{w}/gene/{key}", gene.get(key))
            add("rate", f"{w}/gene/degradation/rate_per_s", gene.get("degradation", {}).get("rate_per_s"))
            for key in ("template_copies", "machines_copies"):
                add("count", f"{w}/gene/{key}", gene.get(key))
    for name, block in data.get("start", {}).items():
        for key, value in block.items():
            add("amount", f"start/{name}/{key}", value)
    for name, block in (data.get("restart") or {}).items():
        add("sample time", f"restart/{name}/time_s", block.get("time_s"))
    return out


def invented_rules(invented: Inputs, registered: Inputs) -> dict:
    coll = Collector()
    for where, kind in invented.problems:
        coll.fault(kind, sj.path_text(where), "in the invented inputs")
    reg = _numbers_by_kind(registered.data)
    inv = _numbers_by_kind(invented.data)
    for kind, items in inv.items():
        registered_values = {v: w for w, v in reg.get(kind, [])}
        for where, value in items:
            if value in registered_values:
                coll.fault("invented number equals a registered one", where,
                           f"{value!r} ({kind}) equals {registered_values[value]}")
    for name, world in invented.worlds.items():
        if name not in registered.worlds or world.kind != registered.worlds[name].kind:
            coll.fault("invented world", name, "not a world of a registered kind")
    for raw in invented.listed_retry_runs:
        fam_id = f"{raw.get('world')} {raw.get('first')}-first"
        fam = invented.families.get(fam_id)
        if fam is None or fam.retry_rung is None:
            coll.fault("invented retry", raw.get("name", "?"), "no family with a retry rung")
            continue
        expected = Inputs.retry_name(fam, int(raw.get("copy", -1)))
        if raw.get("name") != expected or raw.get("step_s") != fam.retry_rung or raw.get("role") != "judged":
            coll.fault("invented retry", raw.get("name", "?"), f"not the rule's run {expected!r}")
    if not invented.listed_retry_runs:
        coll.fault("invented retry", "retry/runs", "no retry run is listed (SPEC.md §8: the retry is reachable)")
    return {"faults": [f.as_dict() for f in coll.faults], "refused": bool(coll.faults),
            "numbers_compared": sum(len(v) for v in inv.values())}


def compare_hashes(record: dict[str, str] | None, files: dict[str, str]) -> dict:
    """The protocol's hashes: each file's sha256 against the lead's record, where a record is supplied."""
    if record is None:
        return {"record": None, "note": "no record of the lead's was supplied; the computed sha256 are reported",
                "computed": files, "faults": []}
    faults = []
    for name, digest in files.items():
        expected = record.get(name)
        if expected is None:
            faults.append({"code": "hash", "where": name, "message": "no line in the lead's record"})
        elif expected.lower() != digest:
            faults.append({"code": "hash", "where": name, "message": f"{digest} is not the recorded {expected}"})
    return {"record": record, "computed": files, "faults": faults}


def run_c0(spec_dir: str, references_out: str, hashes: dict[str, str] | None = None) -> dict:
    """C0 in the order of CRITERIA.md §4.2."""
    registered = Inputs(os.path.join(spec_dir, "inputs.json"))
    invented_inputs_path = os.path.join(references_out, "inputs_invented.json")
    invented = Inputs(invented_inputs_path)
    out: dict[str, Any] = {"kind": C0_KIND, "files": {}}
    files_sha = {
        "inputs.json": registered.sha256,
        "draws.json": sj.sha256_file(os.path.join(spec_dir, "draws.json")),
        "inputs_invented.json": invented.sha256,
        "draws_invented.json": sj.sha256_file(os.path.join(references_out, "draws_invented.json")),
    }
    registered_problems = [{"code": kind, "where": sj.path_text(w)} for w, kind in registered.problems]
    out["registered_inputs_problems"] = registered_problems
    out["invented"] = c0_reference_file(os.path.join(references_out, "reference_invented.json"), invented,
                                        os.path.join(references_out, "draws_invented.json"), invented=True)
    out["invented_rules"] = invented_rules(invented, registered)
    files_sha["reference_invented.json"] = out["invented"]["sha256"]
    for world in registered.worlds:
        name = f"reference_{world}.json"
        result = c0_reference_file(os.path.join(references_out, name), registered,
                                   os.path.join(spec_dir, "draws.json"), invented=False)
        out["files"][name] = result
        files_sha[name] = result["sha256"]
    out["hashes"] = compare_hashes(hashes, files_sha)
    refused = {name: r["refused"] for name, r in out["files"].items()}
    refused["reference_invented.json"] = out["invented"]["refused"] or out["invented_rules"]["refused"]
    out["refused"] = refused
    out["passes"] = (not any(refused.values()) and not out["hashes"]["faults"] and not registered_problems)
    return out
