"""FR-38's second comparison: a format sample of the engine's tables for the judge (amendment 4,
§8), on invented inputs only.

**How it is made.**
- Every planned job of campaign.plan() runs as an invented world of its registered structure:
  - worlds.hold with invented Hold inputs for AF, AN, C and D (C with an invented store, D with
    invented water);
  - worlds.b with an invented B for B.

  Each is filed under its registered run name. It runs by the campaign's own code (campaign.one,
  campaign.restart_record, campaign.v0_patch for P9) and is written with its provenance as
  `campaign run` writes it. So every key the real table carries appears, from the real export.
- The retry's `table-retry/` holds family C, with the invented C run at 0.25 s as well.
- campaign.table builds the tables, with the invented windows and sample times in place of the
  registered ones (its `grids`).
- **Scrubbing.** Every number in the tables is then replaced by a meaningless one of the same
  type: an int by an int, a float by a float. Lists keep their lengths. Strings, booleans and nulls
  are kept, and so are the rungs' keys.
  - **No source's number, by construction** (the lead's ruling, 24 November 2026). Before
    scrubbing, the writer collects every number the sample must not show (forbidden_numbers):
    - each number in the work folder's JSON files (the records, the unscrubbed tables and the
      snapshot files);
    - each number in every registered definition (every rung, the retry's, and the plants);
    - each numeric literal of the spec folder's text.

    Scrubbed ints count up from INT_BASE (10^12) and floats from FLOAT_BASE (2 x 10^12 + 0.5),
    far outside every source's range. Each candidate is checked against that set and against the
    leaf's original, and the next is taken if it matches either.
  - No value of any world can be read from the sample.
  - A1's internals in B would otherwise follow registered B's own trajectory, since X's turnover
    does not depend on the release.
  - The lane's layout constants would otherwise echo SPEC.md's.
- **Paths.** Each entry's `record` path is cut to its part under the campaign folder. The records
  themselves stay in the work folder, unscrubbed, outside the sample.
- SHA256SUMS lists the scrubbed files. README.md is written from the files themselves: every key
  and its type to the leaf.

Run: PYTHONPATH=src:. JAX_ENABLE_X64=1 python -m validation.gene_regulation.fr38_v2.format_sample
--work DIR --out SAMPLE_DIR. Development, not judged; no registered world runs.
"""

import argparse
import contextlib
import hashlib
import json
import re
from dataclasses import replace
from pathlib import Path

from validation.gene_regulation import engine_run
from validation.gene_regulation.fr38_v2 import campaign, worlds

# Invented inputs, none of them SPEC.md's (and every number is scrubbed in the sample anyway).
_HOLD = dict(m0_mM=0.02, n0_mM=1.7, pi0_mM=3.0, mu_N=23.0, r0_copies=11.0, rs0_copies=7.0,
             residues=900, stages=6, speed=15.0, k_N_mM=0.04, pool_copies=2500.0, k_I=4.0e4,
             tau_s=50.0, h0_copies=25.0, k_d=0.003, k_s=0.015,
             p_sched=((0.0, 0.6), (128.0, 0.3)), window=(80.0, 240.0), horizon=480.0,
             every=8.0, samples=(240.0, 360.0, 456.0), background_mM=130.0)  # fmt: skip
INVENTED = {
    "AF": worlds.Hold("sample AF", mu_fate=6000.0, **_HOLD),  # far from equilibrium
    "AN": worlds.Hold("sample AN", mu_fate=-7500.0, **_HOLD),  # e^(y_f) about 0.09
}
INVENTED["C"] = replace(INVENTED["AN"], name="sample C",
                        store=worlds.Store(mx_mM=2.0e-6, forward_per_s=1 / 150))  # fmt: skip
INVENTED["D"] = replace(INVENTED["AN"], name="sample D",
                        water=worlds.Water(lp_m_per_Pa_s=8.0e-14, bath_fraction=0.45))  # fmt: skip
INVENTED_B = replace(worlds.ARM_B, tau_s=45.0, p=0.4, k_d=1 / 400, k_s=1 / 90,
                     window=(96.0, 288.0), horizon=480.0, every=24.0,
                     samples=(288.0, 384.0, 456.0))  # fmt: skip
GRIDS = {f: (h.window, h.samples) for f, h in INVENTED.items()} | {
    "B": (INVENTED_B.window, INVENTED_B.samples)
}
RESTART_POLICY = campaign.WindowPolicy(window_steps=240, recording="observations")
RETRY_FAMILY = "C"


def _invented_b_run(run):
    """B's registered run name to the invented B's own (its p is another), and back."""
    p, rest = run.split(" ", 1)
    return f"p={INVENTED_B.p:g} {rest}"


def _plant_edits(name):
    """The plant's registered change, on the invented inputs (CRITERIA.md §6)."""
    family, run, _, edits = worlds.PLANTS[name]
    edits = dict(edits)
    if "schedule" in edits:  # P3a and P3b: half a second late, at the invented window's edges
        (label,) = edits["schedule"]
        t1, t2 = INVENTED[family].window
        edits["schedule"] = {label: (t1 if label == "win" else t2) + worlds.H}
    return family, run, edits


def world(job):
    """(the invented definition, its record identity, the patch context) of a planned job."""
    if "plant" in job:
        family, run, edits = _plant_edits(job["plant"])
        identity = campaign.plant_identity(job["plant"])
        if family == "B":
            raw = worlds.b(_invented_b_run(run), dt=worlds.H, edits=edits, f=INVENTED_B)
        else:
            raw = worlds.hold(family, run, dt=worlds.H, f=INVENTED[family], edits=edits)
        patch = campaign.v0_patch() if job["plant"] == campaign.V0_PLANT else None
        return raw, identity, patch
    family, run, dt = job["family"], job["run"], job["dt"]
    identity = dict(family=family, run=run) | ({"restart": True} if job.get("restart") else {})
    if family == "B":
        return worlds.b(_invented_b_run(run), dt=dt, f=INVENTED_B), identity, None
    return worlds.hold(family, run, dt=dt, f=INVENTED[family]), identity, None


def run_jobs(work):
    """Every planned job (and the retry family's 0.25 s rung) as an invented world, written where
    `campaign run` writes it, with its provenance."""
    jobs = campaign.plan()
    jobs += [j for j in campaign.plan(retry=True, families=(RETRY_FAMILY,)) if j["dt"] == 0.25]
    done = []
    for job in jobs:
        path = campaign.job_path(work, job)
        if path.exists():
            done.append(str(path))
            continue
        raw, identity, patch = world(job)
        folder = path.parent / f"{path.stem}.source"
        source = campaign._source(folder)
        with patch if patch is not None else contextlib.nullcontext():
            if job.get("restart"):
                join = INVENTED["AN"].horizon / 2
                record = campaign.restart_record(raw, join, path.parent / "snapshot-files",
                                                 RESTART_POLICY, **identity)  # fmt: skip
            else:
                record = campaign.one(raw, **identity)
        if record.get("refused"):
            raise RuntimeError(f"the invented world of {job} was refused: {record['refusal']}")
        campaign._write(path, record, engine_run.late_sources(folder, source))
        done.append(str(path))
    return done


# ------------------------------------------------------------------ scrubbing


INT_BASE = 10**12  # Scrubbed ints count up from here, beyond every source's range.
FLOAT_BASE = 2.0e12 + 0.5  # Scrubbed floats likewise; each is exactly representable.
LITERAL = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?(?![\w.])")


def _numbers(x):
    """Every numeric leaf of a JSON value (booleans are not numbers)."""
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return
    if isinstance(x, (int, float)):
        yield x
    elif isinstance(x, list):
        for v in x:
            yield from _numbers(v)
    elif isinstance(x, dict):
        for v in x.values():
            yield from _numbers(v)


def forbidden_numbers(work):
    """Every number the sample must not show, as floats (the module docstring): the work folder's
    JSON files, every registered definition, and the spec folder's numeric literals."""
    found = set()
    for path in sorted(Path(work).rglob("*.json")):
        found.update(float(v) for v in _numbers(json.loads(path.read_text())))
    for dt in sorted(set(worlds.RUNGS) | set(worlds.RETRY_RUNGS)):
        for family in ("AF", "AN", "B", "C", "D"):
            for run in worlds.runs(family):
                found.update(float(v) for v in _numbers(worlds.world(family, run, dt=dt)))
    for name in worlds.PLANTS:
        found.update(float(v) for v in _numbers(worlds.plant(name)))
    for path in sorted((Path(__file__).resolve().parent / "spec").glob("*.md")):
        for match in LITERAL.finditer(path.read_text().replace("−", "-")):
            found.add(float(match.group()))
    return found


class _Scrub:
    """Every number replaced by one of its own type that no source holds and that differs from
    the original, in walk order (the module docstring)."""

    def __init__(self, forbidden):
        self.forbidden = forbidden
        self.k = 0

    def _fresh(self, original, base, kind):
        while True:
            self.k += 1
            value = kind(base + self.k)
            if float(value) not in self.forbidden and float(value) != float(original):
                return value

    def __call__(self, x):
        if isinstance(x, bool) or x is None or isinstance(x, str):
            return x
        if isinstance(x, int):
            return self._fresh(x, INT_BASE, int)
        if isinstance(x, float):
            return self._fresh(x, FLOAT_BASE, float)
        if isinstance(x, list):
            return [self(v) for v in x]
        if isinstance(x, dict):
            return {key: self(x[key]) for key in sorted(x)}
        raise TypeError(type(x))


def _cut_paths(x, work):
    """Each `record` path to its part under the campaign folder (`records/...`)."""
    if isinstance(x, dict):
        return {k: (str(Path(v).relative_to(work)) if k == "record" and isinstance(v, str)
                    else _cut_paths(v, work)) for k, v in x.items()}  # fmt: skip
    if isinstance(x, list):
        return [_cut_paths(v, work) for v in x]
    return x


def scrub_tables(work, out, forbidden):
    """The tables of `work` scrubbed into `out` (table/ and table-retry/), each folder's SHA256SUMS
    rewritten for its scrubbed files. Returns {relative file: sha256}. Refuses a scrubbed file that
    still holds a forbidden number (the guarantee, checked once more on the written text)."""
    sums = {}
    for folder in ("table", "table-retry"):
        lines = []
        (out / folder).mkdir(parents=True, exist_ok=True)
        for source in sorted((Path(work) / folder).glob("table_*.json")):
            doc = _cut_paths(json.loads(source.read_text()), Path(work))
            text = json.dumps(_Scrub(forbidden)(doc), sort_keys=True, separators=(",", ":"))
            left = [v for v in _numbers(json.loads(text)) if float(v) in forbidden]
            if left:
                raise RuntimeError(f"{source.name}: {len(left)} scrubbed numbers are a source's")
            target = out / folder / source.name
            target.write_text(text)
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            lines.append(f"{digest}  {source.name}")
            sums[f"{folder}/{source.name}"] = digest
        (out / folder / "SHA256SUMS").write_text("\n".join(lines) + "\n")
        sums[f"{folder}/SHA256SUMS"] = hashlib.sha256(
            (out / folder / "SHA256SUMS").read_bytes()).hexdigest()  # fmt: skip
    return sums


# ------------------------------------------------------------------ the README's key lists


def _type(x):
    if x is None:
        return "null"
    if isinstance(x, bool):
        return "boolean"
    if isinstance(x, int):
        return "integer"
    if isinstance(x, float):
        return "float"
    if isinstance(x, str):
        return "string"
    return type(x).__name__


# A list of objects that each carry one of these, uniquely, is described entry by entry.
IDS = ("law", "id", "route_id", "reaction_id", "compartment_id", "membrane_id")


def _key_of(dicts):
    for key in IDS:
        values = [json.dumps(d.get(key)) for d in dicts]
        if all(key in d for d in dicts) and len(set(values)) == len(values):
            return key
    return None


def _lines(x, indent, name=None):
    """Markdown bullet lines of x's keys and types, nested to the leaf."""
    pad = "  " * indent
    out = []
    if isinstance(x, dict):
        for key in sorted(x):
            v = x[key]
            if isinstance(v, (dict, list)) and v and not _scalars(v):
                out.append(f"{pad}- `{key}`: {_container(v)}")
                out += _lines(v, indent + 1, key)
            else:
                out.append(f"{pad}- `{key}`: {_describe(v)}")
        return out
    if isinstance(x, list):
        dicts = [v for v in x if isinstance(v, dict)]
        by = _key_of(dicts) if dicts and len(dicts) == len(x) else None
        if by is not None:
            for v in dicts:
                out.append(f"{pad}- the entry whose `{by}` is `{v[by]}`:")
                out += _lines(v, indent + 1)
            return out
        if dicts:
            merged = _merged(dicts)
            optional = sorted(k for k in merged if not all(k in v for v in dicts))
            out += _lines(merged, indent)
            if optional:
                out.append(
                    f"{pad}- (in some entries only: {', '.join(f'`{k}`' for k in optional)})"
                )
            return out
        lists = [v for v in x if isinstance(v, list)]
        if lists:
            out.append(f"{pad}- each entry: {_describe(lists[0])}")
        return out
    return out


def _merged(dicts):
    merged = {}
    for d in dicts:
        for k, v in d.items():
            if k not in merged or (merged[k] is None and v is not None):
                merged[k] = v
            elif isinstance(merged[k], dict) and isinstance(v, dict):
                merged[k] = {**merged[k], **v}
    return merged


def _scalars(v):
    return isinstance(v, list) and all(not isinstance(e, (dict, list)) for e in v)


def _container(v):
    if isinstance(v, dict):
        return "object"
    if all(isinstance(e, dict) for e in v):
        return f"list of {len(v)} objects"
    return f"list of {len(v)}"


def _describe(v):
    if isinstance(v, list):
        if not v:
            return "list, empty here"
        if _scalars(v):
            kinds = sorted({_type(e) for e in v})
            return f"list of {len(v)} {' or '.join(kinds)}"
        return f"list of {len(v)}"
    if isinstance(v, dict):
        return "object, empty here" if not v else "object"
    return _type(v)


def readme(out, head, sums, n_forbidden):
    """README.md: the layout, every key and its type to the leaf, and the lead's four answers."""
    tables = {p.stem.split("_", 1)[1]: json.loads(p.read_text())
              for p in sorted((out / "table").glob("table_*.json"))}  # fmt: skip
    retry = {p.stem.split("_", 1)[1]: json.loads(p.read_text())
             for p in sorted((out / "table-retry").glob("table_*.json"))}  # fmt: skip
    an, b = tables["AN"], tables["B"]
    honest = an["rungs"]["0.5"]["runs"]["p_sched returned"]
    lines = [
        "# FR-38 v2: a format sample of the engine's tables (amendment 4, §8)",
        "",
        "Written by validation/gene_regulation/fr38_v2/format_sample.py at the builder's",
        f"head `{head}`, on invented inputs only. Every record is a real engine run of an",
        "invented world with the registered structure, filed under its registered run name and",
        "built into the tables by the campaign's own code. Every number is then replaced by a",
        "meaningless one of the same type: an int by an int and a float by a float, with lists",
        "keeping their lengths. Strings, booleans and nulls are kept, and so are the rungs' keys.",
        f"Scrubbed ints count up from {INT_BASE} and floats from {FLOAT_BASE!r}. Each was checked",
        f"against the {n_forbidden} distinct numbers of the records, the unscrubbed tables, the",
        "registered definitions and the spec's text, and none equals one of them or its original.",
        "So the keys, nesting and types are the real table's, and no value of any world can be",
        "read here. Each entry's `record` is cut to its part under the campaign folder; in the",
        "real table it is the record's path as written.",
        "",
        "## Files",
        "",
        "| File | sha256 |",
        "| --- | --- |",
        *(f"| `{k}` | `{v}` |" for k, v in sums.items()),
        "",
        '- `table/` holds AF, AN, B, C and D at the rungs `"2.0"`, `"1.0"` and `"0.5"`.',
        f'- `table-retry/` holds {", ".join(sorted(retry))} at `"1.0"`, `"0.5"` and `"0.25"`; the',
        "  retry's table has no restart and no plants (`restart` absent, `plants` empty).",
        "",
        "## Where things sit (the lead's four questions)",
        "",
        "- **The bath's volume:** `definition.model.extracellular[id=bath_0].volume_pL`.",
        "- **The patch's area:** `definition.model.membranes[id=patch_0].area_m2`.",
        "- **Its solute permeabilities:**",
        "  `definition.model.membranes[id=patch_0].permeability_m_per_s`, one float per",
        "  species ID. Each run's `definition` is the engine's own declaration as run.",
        "- **A twin's definition is unlabelled** in two ways:",
        "  - `definition.model.operators` holds no object whose `law` is",
        "    `neutral_arrival_labels@1`;",
        "  - `definition.experiment` has no `label_arrivals` key.",
        "  - Its entry's `readouts` then carry no `label_*` series and no",
        "    `released_present_gross_*`, and the entry has no `survival` key.",
        "- **AN's restart checkpoint time:** `restart.checkpoint.time_s` in",
        "  `table/table_AN.json`. The `restart` key is absent from AF, B, C and D, and from",
        "  the retry's tables (amendment 4, §8.4: `restart` (AN)).",
        "- **P9's V0 patch:** `plants.P9.host_patch` in `table/table_D.json`, an object with",
        '  `id` ("V0"), `operator`, `change` and `code`. Every other plant\'s `host_patch` is',
        "  null. P9's `definition` is its honest run's: the patch is host-side, named only there.",
        "",
        "## The table: every key and its type",
        "",
        "Top level (each `table_<family>.json`):",
        *_lines({k: v for k, v in an.items() if k not in ("rungs", "plants", "restart")}, 0),
        '- `rungs`: object keyed by the step\'s repr (`"2.0"`, `"1.0"`, `"0.5"`; the retry\'s',
        '  `"1.0"`, `"0.5"`, `"0.25"`); each value holds:',
        "  - `dt_s`: float",
        "  - `runs`: object keyed by the run's name (below), each value a run entry",
        "- `restart`: a run entry with `checkpoint`, in AN only; the key is absent elsewhere",
        "- `plants`: object keyed by the plant's name, each value a run entry with `judged_as` and",
        "  `host_patch`, or null where its record is missing",
        "",
        "**Run names, by family:**",
        *(
            f"- {f}: {', '.join(f'`{r}`' for r in t['rungs']['0.5']['runs'])}"
            for f, t in tables.items()
        ),  # fmt: skip
        "",
        "**Plants, by family:**",
        *(
            f"- {f}: {', '.join(f'`{p}`' for p in t['plants']) or 'none'}"
            for f, t in tables.items()
        ),  # fmt: skip
        "",
        '**A run entry** (here AN\'s `p_sched returned` at `"0.5"`; `readouts` are listed below):',
        *_lines({k: v for k, v in honest.items() if k not in ("readouts", "definition")}, 0),
        "- `readouts`: object, one list of floats per series, one value per output (below)",
        "- `definition`: object, the engine's declaration as run (below)",
        "",
        "Which keys each kind of entry carries:",
        *(
            f"- {label}: {', '.join(f'`{k}`' for k in sorted(entry))}"
            for label, entry in (
                ("a labelled run (AN `p_sched returned`)", honest),
                ("a blank (AN `blank returned`)", an["rungs"]["0.5"]["runs"]["blank returned"]),
                (
                    "a twin (AN `p_sched returned unlabelled`)",
                    an["rungs"]["0.5"]["runs"]["p_sched returned unlabelled"],
                ),
                (
                    "B's run (no blank: `excess_over_blank` absent, `blank` null)",
                    b["rungs"]["0.5"]["runs"]["p=0.55 returned"],
                ),
                ("the restart (AN)", an["restart"]),
                ("a plant (D's P9)", tables["D"]["plants"]["P9"]),
                ("P8, with its planted blank", tables["C"]["plants"]["P8"]),
            )
        ),  # fmt: skip
        "- a refused run (none in this sample) would carry `refused` (true), `refusal` (string),",
        "  `definition` and `record` only",
        "",
        "`restart.checkpoint`:",
        *_lines(an["restart"]["checkpoint"], 0),
        "",
        "`plants.P9.host_patch` (D):",
        *_lines(tables["D"]["plants"]["P9"]["host_patch"], 0),
        "",
        "**`readouts`'s series names, by family** (each a list of floats, one value per output):",
    ]
    for f, t in tables.items():
        labelled = t["rungs"]["0.5"]["runs"][next(iter(t["rungs"]["0.5"]["runs"]))]["readouts"]
        lines.append(f"- {f} ({len(labelled)}): " + ", ".join(f"`{k}`" for k in sorted(labelled)))
    lines += ["", "**`checks`** (AN `p_sched returned`):", *_lines(honest["checks"], 0)]
    lines += ["", "**`own_ledgers_at_end`** (AN `p_sched returned`):",
              *_lines(honest["own_ledgers_at_end"], 0)]  # fmt: skip
    lines += ["", "**`source`** (AN `p_sched returned`):", *_lines(honest["source"], 0)]
    lines += ["", "## Each run's `definition`: every key and its type", ""]
    for f, label in (("AN", "the hold worlds (AF and AN alike)"),
                     ("C", "family C (the hold world with the store)"),
                     ("D", "family D (the hold world in water)"), ("B", "arm B")):  # fmt: skip
        runs = tables[f]["rungs"]["0.5"]["runs"]
        definition = runs[next(iter(runs))]["definition"]
        lines += [f"### {label}: `{f}`'s first run", "", *_lines(definition, 0), ""]
    (out / "README.md").write_text("\n".join(lines) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--work", required=True, help="the records and unscrubbed tables")
    parser.add_argument("--out", required=True, help="the sample's folder")
    args = parser.parse_args(argv)
    work, out = Path(args.work), Path(args.out)
    work.mkdir(parents=True, exist_ok=True)
    run_jobs(work)
    campaign.table(work, grids=GRIDS)
    campaign.table(work, (RETRY_FAMILY,), retry=True, grids=GRIDS)
    out.mkdir(parents=True, exist_ok=False)
    forbidden = forbidden_numbers(work)
    sums = scrub_tables(work, out, forbidden)
    head = engine_run.git("rev-parse", "HEAD").strip()
    readme(out, head, sums, len(forbidden))
    print(json.dumps(dict(out=str(out), head=head, sha256=sums), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
