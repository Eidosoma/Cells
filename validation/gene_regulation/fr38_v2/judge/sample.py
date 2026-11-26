"""The reader's check on the registered format sample (amendment 5, §5), before the judge's tag.

It recomputes the nine hashes of §1 and stops if any differs, regenerates the committed shapes from
the sample's README, and reads the six tables with the judgement's own structure pass: keys,
nesting and types to the leaf, matched by name. It takes no number, makes no echo check and
enforces no registered list length (item 8), and nothing it reads enters a judgement (§6).
"""

import hashlib
import os

from . import records, shapes, spec

KIND = "cells.fr38_v2.judge_sample_check@1"
TABLES = [("primary", f) for f in spec.REAL_FAMILIES] + [("retry", "C")]
# §5: every kind of entry the sample holds
COVERAGE = ("labelled", "blank", "twin", "B run", "B twin", "restart", "plant", "P8", "P8 blank",
            "refused")  # fmt: skip
REFUSED_ENTRY = ("D", "primary", "rungs.2.0.runs.p_sched returned unlabelled")


def check(sample_dir, table_shapes=None):
    table_shapes = table_shapes or shapes.load_shapes()
    out = {"kind": KIND, "sample_dir": sample_dir, "hashes": {}, "stopped": None, "passes": False}
    for rel, want in sorted(shapes.sample_hashes(table_shapes).items()):
        path = os.path.join(sample_dir, rel)
        got = None
        if os.path.exists(path):
            with open(path, "rb") as fh:
                got = hashlib.sha256(fh.read()).hexdigest()
        out["hashes"][rel] = {"registered": want, "recomputed": got, "equal": got == want}
    if not all(h["equal"] for h in out["hashes"].values()) or len(out["hashes"]) != 9:
        out["stopped"] = "a hash differs from amendment 5, §1's: nothing is read"
        return out
    with open(os.path.join(sample_dir, "README.md"), encoding="utf-8") as fh:
        regenerated = shapes.schema_from_readme(fh.read())
    out["shapes_equal_readme"] = all(table_shapes[k] == v for k, v in regenerated.items())
    tables = records.read_tables(sample_dir, spec.REAL_FAMILIES)
    out["index"] = tables["index"]
    found = {(t["attempt"], t["family"]): t for t in tables["tables"]}
    out["files"], faults, kinds = {}, [], {}
    faults += [f"SHA256SUMS: {x}" for x in tables["faults"] + tables["flags"]]
    for attempt, family in TABLES:
        tab = found.pop((attempt, family), None)
        if tab is None:
            faults.append(f"{attempt} {family}: the table is not there")
            continue
        rep = _table(tab, table_shapes)
        out["files"][tab["file"]] = rep
        faults += [f"{tab['file']}: {x}" for x in rep["structural_faults"] + rep["not_read"]]
        for k, names in rep["kinds"].items():
            kinds.setdefault(k, set()).update(names)
        if family == REFUSED_ENTRY[0] and attempt == REFUSED_ENTRY[1]:
            out["refused_entry"] = REFUSED_ENTRY[2] in rep["kinds"].get("refused", [])
    faults += [f"a table beyond the six: {k}" for k in found]
    out["coverage"] = {k: k in kinds for k in COVERAGE}
    out["coverage"]["the restart's checkpoint"] = any(
        f["checkpoint"] for f in out["files"].values()
    )
    out["structural_faults"] = faults
    out["unexpected_keys"] = sorted(
        {x for f in out["files"].values() for x in f["unexpected_keys"]}
    )
    out["passes"] = bool(
        not faults and out["shapes_equal_readme"] and all(out["coverage"].values())
        and out.get("refused_entry")
    )  # fmt: skip
    return out


def _table(tab, table_shapes):
    """One table's structure: every finding named by path, the entries by kind, and the raw count of
    the entries in the file beside the count read."""
    family, profile = tab["family"], spec.FAMILY_PROFILE[tab["family"]]
    inputs = spec.spec_inputs(family)
    restart = spec.RESTART.get(family)
    st = records.table_structure(tab, profile, family, inputs, restart and restart[0], table_shapes)
    faults = list(tab["faults"])
    faults += [records._finding(f) for f in st.faults + shapes.excess_faults(st)]
    if family in spec.RESTART and tab["attempt"] == "primary" and st.restart != "present":
        faults.append(f"restart: {st.restart}")
    unexpected = [f[1] for f in st.findings if f[0] == "unexpected"]
    kinds, runs, series = {}, {}, []
    checkpoint = False
    for e in st.entries:
        kinds.setdefault(e.kind, []).append(e.where)
        runs.setdefault(e.where.rpartition(".runs.")[0] or e.where.partition(".")[0], []).append(
            e.name
        )
        for f in e.findings + e.definition_findings:
            if f[0] in shapes.FAULTS:
                faults.append(records._finding(f))
            elif f[0] != shapes.ABSENT_EXCESS:
                unexpected.append(f[1])
        if isinstance(e.obj, dict) and isinstance(e.obj.get("readouts"), dict):
            want = set(table_shapes["readouts"][family])
            if e.role == "twin":
                want = {k for k in want if records.physical(k)}
            got = set(e.obj["readouts"])
            faults += [f"{e.where}.readouts.{k}: missing: a listed series"
                       for k in sorted(want - got)]  # fmt: skip
            series += [f"{e.where}.readouts.{k}" for k in sorted(got - want)]
        checkpoint = checkpoint or (e.kind == "restart" and "checkpoint" in e.obj)
    not_read = [f"{n} entries in the file, {len(st.entries)} read"
                for n in [st.present] if n != len(st.entries)]  # fmt: skip
    not_read += st.notes
    return {
        "family": family,
        "attempt": tab["attempt"],
        "sha256": tab["sha256"],
        "entries_present": st.present,
        "entries_read": len(st.entries),
        "kinds": {k: v for k, v in sorted(kinds.items())},
        "names": {k: sorted(v) for k, v in sorted(runs.items())},
        "checkpoint": checkpoint,
        "structural_faults": faults,
        "not_read": not_read,
        "unexpected_keys": unexpected + series,
    }
