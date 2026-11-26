"""FR-43 part 3's co-writers registration: one engine run, its record, and the launcher (the
builder's driver; the protocol's §5 and §6).

**One run** (`one`, one process each, cold): a run of an inputs file (worlds.py), at its step,
through the engine's windowed path with every host check on every accepted row (WindowPolicy's
default), one window per sample interval, so every sample, and the restart's checkpoint, ends a
window. Its record holds TABLE.md §3's entry, every key but `record` and `record_sha256`, which
the exporter (table.py) adds, formed here from the engine's own state:
- the rows at each sample, an amount being the engine's reference plus its increment; the books
  from their writers' own accumulators: `xi_1` and `xi_2` the reactions' extents of `make` and
  `spend`, `moved` the population's transfer, and the gene unit's `inits`, `exits`, `made` (its
  releases of finished chains), `lost` (its degraded molecules) and `free`; `engaged` and
  `transit` the sums of READOUTS.md §1 over its stage complexes;
- the events from the population's trace (its clock's times, its channels), and `pools_at_event`
  its recorded pools. The trace holds no counts, so `counts_after` applies each listed channel's
  declared jump to the engine's own counts at the run's first row (a resumed run: the
  checkpoint's), and the run checks that against the engine's `integer_counts` and
  `integer_channel_events` at every sample (`counts_checked`); a mismatch is not the engine's
  refusal (kind `harness`);
- `inputs` read back from the parsed definition (echo, below); `definition` the engine's own
  form of it (`to_dict`); `checks` the windows' diagnostics and the composite's ledgers at the
  last row; `source` the code's provenance (validation/gene_regulation/engine_run.provenance: the
  frozen snapshot's record, or the checkout's revision and dirty diff) with the software and
  machine.

**The kinds of refusal** (TABLE.md §3; README.md lists the mapping), from what the engine raised
and where:
- `definition`: an error raised while the definition is parsed, built or planned (before its first
  step) that is not `domain`'s;
- `domain`: a ConfigError there whose message states a bound or range that a declared value left
  (OUT_OF_RANGE), and at run time a step the engine refused (a NumericalError raised outside the
  row checks: the runner's trial/endpoint domain failure);
- `check`: a NumericalError raised by the model's host checks of accepted rows (`check_values`:
  its domain, ledgers and dissipation), and a ConfigError of the windows' diagnostics;
- `harness`: everything else: this driver, the export, a truncated trace, the counts' check.

**The restart** (`restart`): the uninterrupted run to the registered checkpoint, which ends a
window; its checkpoint written and read back through cells.records.io's snapshot files; then
resumed in this process to the end. The record lists the samples at and after the checkpoint
(the resumed part's rows, the checkpoint's own first) and the events after it.

**The Lie plant** (variant "second halves in declared order"): the honest run's definition under
lie.second_halves_in_declared_order(), with `host_patch`.

**The fault switches** (`--fault`, the format sample's runs of the kinds no registered run is
meant to reach; never a registered run): `definition`, the population's channel key `rate_per_s`
misspelt; `check`, the run to its first sample, then resumed from that checkpoint with the
co-writer's books (CHECK_FAULT_BOOKS) raised by CHECK_FAULT_RAISE of themselves, which the engine's
host checks refuse; `harness`, a trace of TRACE_FAULT events.

Run with /mnt/workspaces/Cells/venv-cpu/bin/python, PYTHONPATH=src:. and JAX_ENABLE_X64=1:
- `python -m validation.fr43_part3_cowriters.run one --inputs FILE --run NAME --out DIR`;
- `... run launch --inputs FILE --out DIR --cpus 6,7 [--runs NAME ...] [--retry]`;
- `... run parse --inputs FILE --out DIR` (parse-only: every registered definition, its echo
  against the inputs, nothing compiled).
"""

import argparse
import dataclasses
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from validation.fr43_part3_cowriters import worlds

RECORD = "fr43 part 3 co-writers engine run record, version 1"
DEFINITION, DOMAIN, CHECK, HARNESS = "definition", "domain", "check", "harness"
COMPLETED, REFUSED = "completed", "refused"
RESTART, LIE = "restart", "second halves in declared order"
THROUGH = (
    "cells.records.io snapshot files (write_snapshot, then load_snapshot), resumed in the same "
    "process"
)
SERIES = {
    "reactions": ("n_S_c", "n_S_o", "n_X", "n_Y", "n_W", "xi_1", "xi_2", "moved"),
    "gene": ("n_R_c", "n_R_o", "n_N", "n_M", "n_Pi", "free", "engaged", "transit", "inits",
             "exits", "made", "lost", "moved"),
}  # fmt: skip
EXTENTS = {"xi_1": "make", "xi_2": "spend"}  # READOUTS.md §1: the extents of make and spend.
# A ConfigError's message that states a bound or range a declared value left (domain, not
# definition): a comparison with a number, a sign or finiteness asked, a horizon or domain left.
OUT_OF_RANGE = re.compile(
    r"[<>]=? ?-?[0-9.]|\bat (?:least|most)\b|\bpositive\b|\bnon-?negative\b|\bfinite\b|"
    r"\boutside\b|\bexceeds?\b|\bdomain\b|\babove\b|\bbelow\b|\bnear miss\b|\bmisses\b"
)
FAULTS = ("definition", "check", "harness")
TRACE_FAULT = 2
CHECK_FAULT_RAISE = 1e-3  # The check fault: the co-writer's books raised by this fraction.
CHECK_FAULT_BOOKS = {"reactions": "reaction_produced_fmol", "gene": "poly_produced_fmol"}
ENTRY_KEYS = (
    "status", "world", "first", "copy", "step_s", "steps", "variant", "seed", "t", "series",
    "events", "events_total", "trace_capacity", "integer_ledger", "samples_echo", "operators",
    "inputs", "definition", "checks", "pools_at_event", "restart", "host_patch", "refusal",
    "source",
)  # fmt: skip
SOURCE_KEYS = ("engine_revision", "checkout_dirty", "snapshot", "snapshot_patch_sha256", "python",
               "numpy", "scipy", "jax", "blas_threads", "machine")  # fmt: skip


class HarnessFault(RuntimeError):
    """A fault of this driver or of the export, never the engine's refusal."""


def slug(text):
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")


def record_path(out, name):
    return Path(out) / "records" / f"{slug(name)}.json"


def dumps(value):
    """JSON text with no NaN or infinity, keys sorted: a record's or a table's bytes."""
    return json.dumps(value, sort_keys=True, indent=1, allow_nan=False) + "\n"


def plain(value):
    """value with numpy scalars and arrays as Python numbers and lists; a non-finite float in a
    recorded-only key becomes the string 'non-finite: <repr>' (TABLE.md's no NaN or infinity)."""
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, np.ndarray):
        return plain(value.tolist())
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        value = float(value)
        return value if math.isfinite(value) else f"non-finite: {value!r}"
    return value


# ------------------------------------------------------------------ provenance


def machine():
    model = ""
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                model = line.split(":", 1)[1].strip()
                break
    except OSError:
        model = platform.processor() or "unknown processor"
    cpus = ",".join(str(c) for c in sorted(os.sched_getaffinity(0)))
    return f"{platform.machine()}; {model}; {platform.system()} {platform.release()}; cpus {cpus}"


def environment():
    """The software and machine of `source`, BLAS pinned and read back at one thread (D190)."""
    import jax
    import jaxlib
    import scipy

    from cells.execution import blas_threads

    found = blas_threads.require_pinned("an FR-43 part 3 co-writers run")
    threads = sorted({int(lib["num_threads"]) for lib in found})
    if threads != [blas_threads.THREADS]:
        raise HarnessFault(f"BLAS threads read back {threads}")
    return dict(
        python=platform.python_version(),
        numpy=np.__version__,
        scipy=scipy.__version__,
        jax=f"{jax.__version__} (jaxlib {jaxlib.__version__})",
        blas_threads=threads[0],
        machine=machine(),
    )


def source(out, name):
    """TABLE.md's `source`: engine_run.provenance's identity (a frozen snapshot's record, or the
    checkout's revision and dirty diff, its untracked sources frozen under the run's folder), with
    the environment. From the checkout, `snapshot` says so and `snapshot_patch_sha256` is the
    dirty diff's sha256 (of b'' when clean)."""
    from validation.gene_regulation import engine_run

    attempt = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    folder = Path(out) / "sources" / slug(name) / attempt  # One folder per attempt of the run.
    folder.mkdir(parents=True, exist_ok=False)
    identity, patch = engine_run.provenance(folder)
    if patch is not None:
        (folder / "checkout.patch").write_text(patch)
    if "snapshot" not in identity:
        identity = dict(
            identity,
            snapshot="none: a development run from the checkout",
            snapshot_patch_sha256=hashlib.sha256((patch or "").encode()).hexdigest(),
        )
    return dict(identity, **environment())


# ------------------------------------------------------------------ the kinds of refusal


def kind_of(error, stage):
    """The kind of what was raised at `stage` ("parse", "run" or "export"; module docstring)."""
    from cells.definitions.specs import ConfigError
    from cells.execution.errors import NumericalError

    if stage == "export" or isinstance(error, HarnessFault):
        return HARNESS
    message = str(error)
    frames = [frame.name for frame in traceback.extract_tb(error.__traceback__)]
    if stage == "run":
        if isinstance(error, NumericalError):
            return CHECK if "check_values" in frames else DOMAIN
        if isinstance(error, ConfigError):
            if "merge_diagnostics" in frames:
                return CHECK
            return DOMAIN if OUT_OF_RANGE.search(message) else DEFINITION
        return HARNESS
    if isinstance(error, ConfigError):
        return DOMAIN if OUT_OF_RANGE.search(message) else DEFINITION
    if isinstance(error, (KeyError, TypeError, ValueError, IndexError, AttributeError)):
        return DEFINITION  # The engine's parser could not read the declaration.
    return HARNESS


STEP_RANGE = re.compile(r"on \[([-+0-9.eE]+), ")


def refusal(error, stage, time_s):
    """TABLE.md's `refusal`: the kind, the message as raised, and the time: a refused step's
    start as the engine's message gives it; otherwise `time_s`, the run's last accepted row
    (0.0 at parse)."""
    message = str(error) or type(error).__name__
    found = STEP_RANGE.search(message) if stage == "run" else None
    when = float(found.group(1)) if found else float(time_s)
    return dict(kind=kind_of(error, stage), message=message, time_s=when)


# ------------------------------------------------------------------ the run


def policy_for(spec, join=None):
    """One window per sample interval: the steps' gcd over the samples (and the checkpoint)."""
    from cells.execution.windows import WindowPolicy

    dt = spec.execution.dt
    steps = []
    for t in (*spec.experiment.observation_times, *(() if join is None else (join,))):
        k = round(float(t) / dt)
        if abs(k * dt - float(t)) > 1e-9 * max(1.0, abs(float(t))):
            raise HarnessFault(f"the sample {t} is not on the grid of {dt}")
        steps.append(k)
    window = 0
    for k in steps:
        window = math.gcd(window, k)
    if window < 1:
        raise HarnessFault("no window: the samples hold no positive step")
    return WindowPolicy(window_steps=window, recording="observations")


class Progress:
    """What a run has accepted so far: {step: (time, row)} at its samples, the last accepted
    checkpoint, and the windows' merged diagnostics."""

    def __init__(self):
        self.rows, self.final, self.diagnostics, self.stage = {}, None, {}, "parse"


def observe(spec, policy, progress, checkpoint=None, stop=None):
    """Run windows into `progress` (its stage "run" from the first window), stopping after the
    window that ends at `stop` (s)."""
    from cells.execution.windows import iter_windows, merge_diagnostics

    dt = spec.execution.dt
    wanted = {round(float(t) / dt) for t in spec.experiment.observation_times}
    windows = iter_windows(spec, policy, checkpoint)  # The preflight: still "parse".
    progress.stage = "run"
    for window in windows:
        merge_diagnostics(progress.diagnostics, window.diagnostics)
        for i, t in enumerate(np.asarray(window.times)):
            k = window.start_step + i
            if k in wanted:
                progress.rows[k] = (float(t), type(window.history)(
                    *(np.asarray(v)[i] for v in window.history)))  # fmt: skip
        progress.final = window.final
        if stop is not None and float(window.final.time) >= stop - 1e-9 * max(1.0, stop):
            break


# ------------------------------------------------------------------ the readouts


def layout(spec, p, kind):
    """Indices of the world's rows and books in the engine's state (module docstring)."""
    ids = list(spec.model.species_ids)
    ops = {op.law: op for op in spec.model.operators}
    out = dict(
        cell=int(np.asarray(p.integer_site_cell)[0]),
        node=int(np.asarray(p.integer_site_node)[0]),
        species={s: ids.index(s) for s in ids},
    )
    units = ops[worlds.POPULATION].populations[0]
    out["weights"] = [int(u.subunits) for u in units.unit_states]
    out["channels"] = [c.id for c in units.channels]
    states = [u.id for u in units.unit_states]
    out["jumps"] = [
        [int(dict(c.products).get(s, 0)) - int(dict(c.reactants).get(s, 0)) for s in states]
        for c in units.channels
    ]
    if kind == "reactions":
        routes = ops[worlds.REACTIONS].routes
        out["extents"] = {
            book: next(
                i for i, r in enumerate(routes) if r.reaction == rid and r.node == worlds.CELL
            )
            for book, rid in EXTENTS.items()
        }
    else:
        gene = ops[worlds.GENE]
        if len(gene.chains) != 1 or len(gene.pools) != 1 or len(gene.degradations) != 1:
            raise HarnessFault("W6's gene unit has one chain, one pool and one degradation")
        chain = gene.chains[0]
        out["stages"] = int(chain.stages)
        out["r"] = int(chain.residues) / int(chain.stages)
    return out


def amount(p, row, s, at):
    """(the cell's or the node's amount of species s): the engine's reference plus increment."""
    cell, node = at
    if node is None:
        return float(
            np.asarray(p.amount_reference)[s, cell] + np.asarray(row.amount_increment)[s, cell]
        )
    return float(
        np.asarray(p.extracellular_amount_reference)[s, node]
        + np.asarray(row.extracellular_amount_increment)[s, node]
    )


def readout(kind, lay, p, row):
    """{series name: value} at one row (module docstring)."""
    sp, cell, node = lay["species"], lay["cell"], lay["node"]
    moved = float(np.asarray(row.integer_transferred_fmol)[0, 0])
    if kind == "reactions":
        extent = np.asarray(row.reaction_extent_fmol)
        return dict(
            n_S_c=amount(p, row, sp["S"], (cell, None)),
            n_S_o=amount(p, row, sp["S"], (None, node)),
            n_X=amount(p, row, sp["X"], (cell, None)),
            n_Y=amount(p, row, sp["Y"], (cell, None)),
            n_W=amount(p, row, sp["W"], (cell, None)),
            xi_1=float(extent[lay["extents"]["xi_1"]]),
            xi_2=float(extent[lay["extents"]["xi_2"]]),
            moved=moved,
        )
    complexes = [float(c) for c in np.asarray(row.poly_complexes_fmol)[0, : lay["stages"]]]
    engaged, weighted = 0.0, 0.0
    for j, c in enumerate(complexes, start=1):
        engaged += c
        weighted += (j - 1) * c
    return dict(
        n_R_c=amount(p, row, sp["R"], (cell, None)),
        n_R_o=amount(p, row, sp["R"], (None, node)),
        n_N=amount(p, row, sp["N"], (cell, None)),
        n_M=amount(p, row, sp["M"], (cell, None)),
        n_Pi=amount(p, row, sp["Pi"], (cell, None)),
        free=float(np.asarray(row.poly_free_machines_fmol)[0]),
        engaged=engaged,
        transit=lay["r"] * weighted,
        inits=float(np.asarray(row.poly_initiated_fmol)[0]),
        exits=float(np.asarray(row.poly_stage_exits_fmol)[0]),
        made=float(np.asarray(row.poly_released_fmol)[0]),
        lost=float(np.asarray(row.poly_degraded_fmol)[0]),
        moved=moved,
    )


def events_of(lay, last, first_index, start_counts, rows):
    """(events, pools_at_event, events_total, the counts' check, faults): the trace's events from
    `first_index` at the last accepted row (as many as it holds), counts_after by the declared
    jumps from `start_counts`, checked against the engine's counts at every sample row. A
    truncated trace or a count that departs is a fault (kind harness), never raised here."""
    faults = []
    total = int(np.asarray(last.integer_events)[0])
    capacity = int(np.asarray(last.integer_trace_time_s).shape[1])
    held_events = min(total, capacity)
    if total > capacity:
        faults.append(f"the trace holds the first {capacity} of {total} events: truncated")
    if total < first_index:
        faults.append(f"{total} events in all, fewer than the first index {first_index}")
    times = [float(x) for x in np.asarray(last.integer_trace_time_s)[0, first_index:held_events]]
    index = [int(x) for x in np.asarray(last.integer_trace_channel)[0, first_index:held_events]]
    if any(j < 0 or j >= len(lay["channels"]) for j in index):
        faults.append("the trace holds an unrecorded or unknown channel")
        index = [j for j in index if 0 <= j < len(lay["channels"])][: len(times)]
        times = times[: len(index)]
    counts, after = [int(c) for c in start_counts], []
    for j in index:
        counts = [c + d for c, d in zip(counts, lay["jumps"][j], strict=True)]
        after.append(list(counts))
    compared = 0
    for t, row in rows:
        fired = int(np.asarray(row.integer_events)[0])
        held = [int(c) for c in np.asarray(row.integer_counts)[0]]
        if fired - first_index > len(after) or fired < first_index:
            continue  # Past the trace, or before the first listed event: not comparable.
        derived = after[fired - first_index - 1] if fired > first_index else list(start_counts)
        compared += 1
        if derived != held:
            faults.append(f"the counts after event {fired - 1} are {derived}; the engine holds "
                          f"{held} at {t} s")  # fmt: skip
            break
    channel_totals = [int(c) for c in np.asarray(last.integer_channel_events)[0]]
    cells = np.asarray(last.integer_trace_cell_fmol)[0, first_index : first_index + len(times), 0]
    nodes = np.asarray(last.integer_trace_node_fmol)[0, first_index : first_index + len(times), 0]
    events = dict(
        time_s=times,
        channel=[lay["channels"][j] for j in index],
        counts_after=after,
        first_index=int(first_index),
    )
    pools = dict(cell_fmol=[float(x) for x in cells], node_fmol=[float(x) for x in nodes])
    checked = dict(rows_compared=compared, channel_totals_at_end=channel_totals)
    return events, pools, total, checked, faults


def ledger(lay, row):
    """Σ_k w_k n_k at one row, in integers."""
    counts = [int(c) for c in np.asarray(row.integer_counts)[0]]
    return int(sum(w * n for w, n in zip(lay["weights"], counts, strict=True)))


def checks_of(model, p, last_row, diagnostics, counts_checked):
    balances = model.balances(last_row, p)
    return plain(
        dict(
            window_diagnostics=dict(sorted(diagnostics.items())),
            balances_at_end={k: np.asarray(v) for k, v in balances.items()},
            counts_checked=counts_checked,
        )
    )


# ------------------------------------------------------------------ the echo


def echo(definition, kind):
    """TABLE.md's `inputs`: the world's block of inputs.json, exactly echo's keys, read back from
    the definition the engine parsed (its `to_dict`), with the run's seed, step_s, first and
    copy."""
    m, e, x = definition["model"], definition["experiment"], definition["execution"]
    ops = m["operators"]
    laws = [op["law"] for op in ops]
    units = ops[laws.index(worlds.POPULATION)]
    population = units["populations"][0]
    (site,) = population["sites"]
    (transfer,) = population["transfers"]
    (cell,) = m["cells"]
    (node,) = [n for n in m["extracellular"] if not n.get("reservoir")]
    held = {c["id"]: dict(c["initial_amount_fmol"]) for c in m["cells"]}
    held[node["id"]] = dict(node["initial_amount_fmol"])
    out = dict(
        kind=kind,
        cell_pL=cell["volume_pL"],
        node_pL=node["volume_pL"],
        end_s=e["end_time"],
        samples_s=list(e["observation_times"]),
        population=dict(
            unit_states=[
                dict(id=u["id"], subunits=u["subunits"]) for u in population["unit_states"]
            ],
            initial_counts=dict(site["initial_counts"]),
            channels=[
                dict(
                    id=c["id"],
                    reactants=dict(c["reactants"]),
                    products=dict(c["products"]),
                    rate_constant=c["rate_per_s"],
                    read=None if c["read"] is None else dict(
                        at={"cell": "cell", "outside": "node"}[c["read"]["at"]],
                        species=c["read"]["species"],
                    ),
                )
                for c in population["channels"]
            ],
            transfer=dict(species=transfer["species"],
                          conductance_pL_per_s=dict(transfer["conductance_pL_per_s"])),
        ),
    )  # fmt: skip
    if kind == "reactions":
        writer = ops[laws.index(worlds.REACTIONS)]
        out["rows_fmol"] = dict(
            S_cell=held[cell["id"]]["S"],
            S_node=held[node["id"]]["S"],
            X=held[cell["id"]]["X"],
            Y=held[cell["id"]]["Y"],
            W=held[cell["id"]]["W"],
        )
        out["reactions"] = []
        for r in writer["reactions"]:
            if r["law"] != "mass_action" or r["factors"] or r["sites"] != {"cells": [cell["id"]]}:
                raise HarnessFault(f"reaction {r['id']} is not driven mass action in the cell")
            order = sum(r["reactants"].values())
            out["reactions"].append(
                dict(
                    id=r["id"],
                    reactants=dict(r["reactants"]),
                    products=dict(r["products"]),
                    rate_constant=r["rate_constant"],
                    rate_unit=worlds.UNIT[order],
                )
            )
    else:
        writer = ops[laws.index(worlds.GENE)]
        (pool,), (chain,), (degradation,) = (
            writer["pools"],
            writer["chains"],
            writer["degradations"],
        )
        schedules = {c["route_id"]: c["schedule"] for c in e["polymerisation_controls"]}

        def constant(route):
            (change,) = schedules[route]
            if change["time"] != 0.0:
                raise HarnessFault(f"{route}'s schedule does not start at 0")
            return change["value"]

        ((monomer, per_residue),) = degradation["monomers"].items()
        out["rows_fmol"] = dict(
            N=held[cell["id"]]["N"],
            M=held[cell["id"]]["M"],
            Pi=held[cell["id"]]["Pi"],
            R_cell=held[cell["id"]]["R"],
            R_node=held[node["id"]]["R"],
        )
        out["gene"] = dict(
            template_copies=chain["template"]["copies"],
            machines_copies=pool["machines"],
            product=chain["product"],
            residues=chain["residues"],
            stages=chain["stages"],
            speed_per_s=chain["speed_per_s"],
            draws=dict(chain["draws"]),
            releases=dict(chain["releases"]),
            saturation_mM=dict(chain["saturation_mM"]),
            initiation_per_mM_s=constant(chain["id"]),
            degradation=dict(
                polymer=degradation["polymer"],
                monomers={monomer: per_residue * degradation["residues"]},
                rate_per_s=constant(degradation["id"]),
            ),
            mu_RT={s["id"]: s["standard_mu_RT"] for s in writer["species"]},
            c0_mM=writer["standard_concentration_mM"],
        )
    copy_index = re.fullmatch(r"site_c([0-9]+)", site["id"])
    if copy_index is None:
        raise HarnessFault(f"the site {site['id']!r} names no copy")
    out.update(
        seed=units["seed"],
        step_s=x["dt"],
        first="population" if laws[0] == worlds.POPULATION else kind,
        copy=int(copy_index.group(1)),
    )
    return out


def echo_keys(inputs, kind):
    e = inputs["echo"]
    return set(e["world_keys"][kind]) | set(e["run_keys"])


# ------------------------------------------------------------------ the entry


def blank_entry(run, inputs, kind, raw, source_value):
    """A run's entry before anything of the engine is known (a run refused at parse keeps it)."""
    return dict(
        status=REFUSED,
        world=run["world"],
        first=run["first"],
        copy=int(run["copy"]),
        step_s=float(run["step_s"]),
        steps=0,
        variant=run.get("variant"),
        seed=worlds.seed_of(inputs, run),
        t=[],
        series={name: [] for name in SERIES[kind]},
        events=dict(time_s=[], channel=[], counts_after=[], first_index=0),
        events_total=0,
        trace_capacity=int(next(op for op in raw["model"]["operators"]
                                if op["law"] == worlds.POPULATION)["trace_events"]),
        integer_ledger=[],
        samples_echo=[float(t) for t in raw["experiment"]["observation_times"]],
        operators=[],
        inputs=None,
        definition=None,
        checks={},
        pools_at_event=None,
        restart=None,
        host_patch=None,
        refusal=None,
        source=source_value,
    )  # fmt: skip


def _number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _integer(v):
    return isinstance(v, int) and not isinstance(v, bool)


def validate(entry, kind):
    """TABLE.md §3's shape of one entry: every key, of its type, null only where allowed.
    Returns the list of faults (empty when the entry keeps the contract)."""
    faults = []
    missing = [k for k in (*ENTRY_KEYS, "record", "record_sha256") if k not in entry]
    if missing:
        return [f"missing keys {missing}"]

    def need(ok, what):
        if not ok:
            faults.append(what)

    need(entry["status"] in (COMPLETED, REFUSED), "status")
    for key in ("world", "first"):
        need(isinstance(entry[key], str), key)
    for key in ("copy", "steps", "seed", "events_total", "trace_capacity"):
        need(_integer(entry[key]), key)
    need(_number(entry["step_s"]), "step_s")
    need(entry["variant"] is None or isinstance(entry["variant"], str), "variant")
    need(isinstance(entry["t"], list) and all(_number(v) for v in entry["t"]), "t")
    series = entry["series"]
    need(isinstance(series, dict) and set(SERIES[kind]) <= set(series), "series keys")
    for name in SERIES[kind]:
        values = series.get(name)
        need(isinstance(values, list) and len(values) == len(entry["t"])
             and all(_number(v) for v in values), f"series {name}")  # fmt: skip
    ev = entry["events"]
    need(isinstance(ev, dict) and {"time_s", "channel", "counts_after", "first_index"} <= set(ev),
         "events keys")  # fmt: skip
    if isinstance(ev, dict) and not faults:
        n = len(ev["time_s"])
        need(all(_number(v) for v in ev["time_s"]), "events.time_s")
        need(len(ev["channel"]) == n and all(isinstance(v, str) for v in ev["channel"]),
             "events.channel")  # fmt: skip
        need(len(ev["counts_after"]) == n and all(
            isinstance(c, list) and all(_integer(v) for v in c) for c in ev["counts_after"]),
            "events.counts_after")  # fmt: skip
        need(_integer(ev["first_index"]), "events.first_index")
        need(entry["events_total"] == ev["first_index"] + n
             or entry["events_total"] > entry["trace_capacity"]
             or entry["status"] == REFUSED, "events_total against its list")  # fmt: skip
    ledger_values = entry["integer_ledger"]
    need(isinstance(ledger_values, list) and len(ledger_values) == len(entry["t"])
         and all(_integer(v) for v in entry["integer_ledger"]), "integer_ledger")  # fmt: skip
    need(isinstance(entry["samples_echo"], list) and all(_number(v) for v in entry["samples_echo"]),
         "samples_echo")  # fmt: skip
    operators = entry["operators"]
    need(isinstance(operators, list) and all(isinstance(v, str) for v in operators),
         "operators")  # fmt: skip
    parsed = entry["definition"] is not None
    need(isinstance(entry["inputs"], dict) if parsed else entry["inputs"] is None, "inputs")
    need(bool(entry["operators"]) == parsed, "operators against the definition")
    need(entry["definition"] is None or isinstance(entry["definition"], dict), "definition")
    need(entry["status"] == REFUSED or parsed, "a completed run's definition")
    need(isinstance(entry["checks"], dict), "checks")
    need(entry["pools_at_event"] is None or isinstance(entry["pools_at_event"], dict), "pools")
    restart = entry["restart"]
    need(restart is None or (isinstance(restart, dict) and set(restart) == {"time_s", "step_index",
         "through"} and _number(restart["time_s"]) and _integer(restart["step_index"])
         and isinstance(restart["through"], str)), "restart")  # fmt: skip
    patch = entry["host_patch"]
    need(patch is None or (isinstance(patch, dict) and set(patch) == {"id", "change"}
         and all(isinstance(v, str) for v in patch.values())), "host_patch")  # fmt: skip
    rf = entry["refusal"]
    need((rf is None) == (entry["status"] == COMPLETED), "refusal against status")
    need(rf is None or (isinstance(rf, dict) and set(rf) == {"kind", "message", "time_s"}
         and rf["kind"] in (DEFINITION, DOMAIN, CHECK, HARNESS) and isinstance(rf["message"], str)
         and _number(rf["time_s"])), "refusal")  # fmt: skip
    src = entry["source"]
    need(isinstance(src, dict) and set(SOURCE_KEYS) <= set(src), "source keys")
    if isinstance(src, dict) and set(SOURCE_KEYS) <= set(src):
        need(isinstance(src["checkout_dirty"], bool), "source.checkout_dirty")
        need(_integer(src["blas_threads"]), "source.blas_threads")
        for key in set(SOURCE_KEYS) - {"checkout_dirty", "blas_threads"}:
            need(isinstance(src[key], str) and src[key] != "", f"source.{key}")
    need(isinstance(entry["record"], str) and entry["record"] != "", "record")
    need(
        isinstance(entry["record_sha256"], str)
        and re.fullmatch(r"[0-9a-f]{64}", entry["record_sha256"]) is not None,
        "record_sha256",
    )
    return faults


# ------------------------------------------------------------------ one run, end to end


def _faulted(raw, fault):
    """The format sample's fault switches (module docstring) on a run's definition."""
    if fault is None:
        return raw
    units = next(op for op in raw["model"]["operators"] if op["law"] == worlds.POPULATION)
    if fault == "definition":
        for channel in units["populations"][0]["channels"]:
            channel["rate_per_second"] = channel.pop("rate_per_s")
    elif fault == "check":
        pass  # Run.execute raises the co-writer's books at the first sample (module docstring).
    elif fault == "harness":
        units["trace_events"] = TRACE_FAULT
    else:
        raise ValueError(f"unknown fault {fault!r}")
    return raw


def one(inputs_path, name, out, *, fault=None, name_suffix=None):
    """Make one run's record under `out` (module docstring); returns its path. name_suffix names
    a fault run's record (the format sample's: never a registered run's name)."""
    started = time.perf_counter()
    out = Path(out)
    inputs = worlds.read_inputs(inputs_path)
    run = worlds.find_run(inputs, name)
    record_name = name if name_suffix is None else f"{name} {name_suffix}"
    if (fault is None) != (name_suffix is None):
        raise ValueError("a fault run, and only a fault run, has its own record name")
    kind = inputs["worlds"][run["world"]]["kind"]
    raw = _faulted(worlds.definition(inputs, run), fault)
    entry = blank_entry(run, inputs, kind, raw, source(out, record_name))
    extra = dict(fault=fault)
    state = Run(inputs, run, kind, raw, entry, out / "snapshots" / slug(record_name), fault)
    try:
        if run.get("variant") == LIE:
            from validation.fr43_part3_cowriters import lie

            entry["host_patch"] = dict(id=lie.ID, change=lie.CHANGE)
            with lie.second_halves_in_declared_order():
                state.execute()
        else:
            state.execute()
    except Exception as error:  # The run's refusal, by its kind; what it accepted is kept.
        last = state.progress.final.time if state.progress.final is not None else 0.0
        entry["status"], entry["refusal"] = REFUSED, refusal(error, state.progress.stage, last)
        extra["traceback"] = traceback.format_exc()[-8000:]
        try:
            state.fill(refused=True)
        except Exception as again:  # Nothing more is kept; the refusal stands.
            extra["fill_after_refusal"] = f"{type(again).__name__}: {again}"
    extra.update(state.extra, wall_s=time.perf_counter() - started)
    path = record_path(out, record_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = dict(
        kind=RECORD,
        name=record_name,
        registered_name=name,
        role=run.get("role"),
        inputs_file=dict(path=str(inputs_path),
                         sha256=hashlib.sha256(Path(inputs_path).read_bytes()).hexdigest()),
        created_utc=datetime.now(UTC).isoformat(),
        entry=plain(entry),
        extra=plain(extra),
    )  # fmt: skip
    path.write_text(dumps(record))
    return path


class Run:
    """One run's engine part (module docstring): parse, run or restart, and fill the entry."""

    def __init__(self, inputs, run, kind, raw, entry, snapshots, fault=None):
        self.inputs, self.run, self.kind, self.raw, self.entry = inputs, run, kind, raw, entry
        self.snapshots, self.progress, self.extra, self.fault = snapshots, Progress(), {}, fault
        self.spec = self.model = self.p = self.lay = None
        self.first_index, self.start = 0, None

    def execute(self):
        from cells.definitions.specs import parse_spec
        from cells.records.io import load_snapshot, write_snapshot
        from cells.registry.models import get_model

        entry, kind = self.entry, self.kind
        self.spec = spec = parse_spec(self.raw)
        self.model = get_model(spec.model)
        _, self.p = self.model.initial_values(spec)
        definition = spec.to_dict()
        entry["definition"] = definition
        entry["operators"] = [op["law"] for op in definition["model"]["operators"]]
        entry["inputs"] = echo(definition, kind)
        if set(entry["inputs"]) != echo_keys(self.inputs, kind):
            raise HarnessFault(f"the echo's keys {sorted(entry['inputs'])} are not echo's")
        for key in ("first", "copy", "seed", "step_s"):
            entry[key] = entry["inputs"][key]
        entry["samples_echo"] = [float(t) for t in spec.experiment.observation_times]
        self.lay = layout(spec, self.p, kind)
        join = None
        if self.run.get("variant") == RESTART:
            join = float(self.inputs["restart"][self.run["world"]]["time_s"])
        policy = policy_for(spec, join)
        self.extra["window_steps"] = policy.window_steps
        if self.fault == "check":
            self._raised_books(spec, policy)
        elif join is None:
            observe(spec, policy, self.progress)
        else:
            observe(spec, policy, self.progress, stop=join)
            checkpoint = self.progress.final
            if abs(float(checkpoint.time) - join) > 1e-12 * join:
                raise HarnessFault(f"the checkpoint is at {checkpoint.time} s, not {join} s")
            self.snapshots.parent.mkdir(parents=True, exist_ok=True)
            write_snapshot(self.snapshots, spec, checkpoint)
            loaded = load_snapshot(self.snapshots)
            resumed = loaded.checkpoint
            entry["restart"] = dict(
                time_s=float(resumed.time), step_index=int(resumed.step_index), through=THROUGH
            )
            self.first_index = int(np.asarray(loaded.checkpoint.state.integer_events)[0])
            self.start = [int(c) for c in np.asarray(loaded.checkpoint.state.integer_counts)[0]]
            self.progress.rows = {}
            observe(loaded.spec, policy, self.progress, checkpoint=loaded.checkpoint)
        self.progress.stage = "export"
        faults = self.fill(refused=False)
        if faults:
            raise HarnessFault("; ".join(faults))
        entry["status"], entry["refusal"] = COMPLETED, None

    def _raised_books(self, spec, policy):
        """The check fault (module docstring): to the first sample after 0, then on from that
        checkpoint with the co-writer's books raised by CHECK_FAULT_RAISE of themselves, so the
        engine's host checks of the next window's rows refuse the ledger that carries them."""
        first = sorted(float(t) for t in spec.experiment.observation_times)[1]
        observe(spec, policy, self.progress, stop=first)
        at = self.progress.final
        name = CHECK_FAULT_BOOKS[self.kind]
        raised = np.asarray(getattr(at.state, name)) * (1.0 + CHECK_FAULT_RAISE)
        state = at.state._replace(**{name: raised})
        observe(spec, policy, self.progress, checkpoint=dataclasses.replace(at, state=state))

    def fill(self, *, refused):
        """The entry's rows, books, ledger and events from what the run accepted; the harness
        faults found (a truncated trace, a count that departs)."""
        entry, progress = self.entry, self.progress
        if self.lay is None or progress.final is None:
            return []  # Refused before its first window: nothing accepted.
        steps = sorted(progress.rows)
        rows = [progress.rows[k] for k in steps]
        start = self.start
        if start is None:
            if not steps or steps[0] != 0:
                return ["the run holds no t = 0 row"]
            start = [int(c) for c in np.asarray(rows[0][1].integer_counts)[0]]
        last = progress.final.state
        events, pools, total, checked, faults = events_of(
            self.lay, last, self.first_index, start, rows
        )
        values = [readout(self.kind, self.lay, self.p, row) for _, row in rows]
        entry["t"] = [t for t, _ in rows]
        entry["series"] = {name: [v[name] for v in values] for name in SERIES[self.kind]}
        entry["integer_ledger"] = [ledger(self.lay, row) for _, row in rows]
        entry["events"], entry["pools_at_event"], entry["events_total"] = events, pools, total
        entry["trace_capacity"] = int(np.asarray(last.integer_trace_time_s).shape[1])
        entry["steps"] = int(progress.final.step_index)
        if rows:
            entry["checks"] = checks_of(self.model, self.p, rows[-1][1], progress.diagnostics,
                                        checked)  # fmt: skip
        self.extra["counts_faults"] = faults
        return faults


# ------------------------------------------------------------------ parse-only: the echo's check


def same(a, b, *, path="", ordered=("channels", "unit_states", "operators")):
    """CRITERIA.md §4.1's comparison of an echo with its registered value: numbers to 1e-12
    relative (a declared zero exactly), integers and strings exactly, 4 equal to 4.0, null equal
    to an absent key, collections keyed by id in any order, a declared order as a list. Returns
    the paths that depart."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for key in sorted(set(a) | set(b)):
            x, y = a.get(key), b.get(key)
            if x is None and y is None:
                continue
            out += same(x, y, path=f"{path}.{key}", ordered=ordered)
        return out
    if isinstance(a, list) and isinstance(b, list):
        keyed = all(isinstance(v, dict) and "id" in v for v in (*a, *b))
        if keyed and path.rsplit(".", 1)[-1] not in ordered:
            ka, kb = {v["id"]: v for v in a}, {v["id"]: v for v in b}
            if set(ka) != set(kb) or len(ka) != len(a) or len(kb) != len(b):
                return [f"{path}: ids {sorted(ka)} against {sorted(kb)}"]
            return [p for k in sorted(ka) for p in same(ka[k], kb[k], path=f"{path}[{k}]")]
        if len(a) != len(b):
            return [f"{path}: {len(a)} items against {len(b)}"]
        return [p for i, (x, y) in enumerate(zip(a, b, strict=True))
                for p in same(x, y, path=f"{path}[{i}]")]  # fmt: skip
    if _number(a) and _number(b):
        if b == 0 or a == 0:
            return [] if a == b else [f"{path}: {a!r} against {b!r}"]
        return [] if abs(a - b) <= 1e-12 * abs(b) else [f"{path}: {a!r} against {b!r}"]
    return [] if a == b and type(a) is type(b) else [f"{path}: {a!r} against {b!r}"]


def registered_echo(inputs, run):
    """The echo a run must carry: its world's echo keys (with the run's `change`, the invented
    refused and stopped runs') and its run keys, from the inputs."""
    world = worlds.world_of(inputs, run)
    keys = inputs["echo"]["world_keys"][world["kind"]]
    out = {k: world[k] for k in keys}
    out.update(seed=worlds.seed_of(inputs, run), step_s=run["step_s"], first=run["first"],
               copy=run["copy"])  # fmt: skip
    return out


def parse_all(inputs_path, out):
    """Every registered and retry run's definition, parsed with nothing compiled: its refusal at
    the definition (the population's step bound among them), or its echo against the inputs."""
    from cells.definitions.specs import parse_spec

    inputs = worlds.read_inputs(inputs_path)
    rows = []
    for retry in (False, True):
        for run in worlds.runs(inputs, retry=retry).values():
            kind = inputs["worlds"][run["world"]]["kind"]
            row = dict(name=run["name"], variant=run.get("variant"))
            try:
                spec = parse_spec(worlds.definition(inputs, run))
                found = echo(spec.to_dict(), kind)
                expected = registered_echo(inputs, run)
                row.update(parsed=True, departs=same(found, expected),
                           keys_match=set(found) == echo_keys(inputs, kind))  # fmt: skip
            except Exception as error:
                row.update(parsed=False, refusal=refusal(error, "parse", 0.0))
            rows.append(row)
    summary = dict(
        inputs=str(inputs_path),
        inputs_sha256=hashlib.sha256(Path(inputs_path).read_bytes()).hexdigest(),
        runs=len(rows),
        parsed=sum(r["parsed"] for r in rows),
        refused=[r for r in rows if not r["parsed"]],
        departing=[r for r in rows if r["parsed"] and (r["departs"] or not r["keys_match"])],
    )
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / "parse.json").write_text(dumps(plain(dict(summary, rows=rows))))
    return summary


# ------------------------------------------------------------------ the launcher


def launch(inputs_path, out, cpus, names, *, faults=()):
    """Each run in its own process (cold: no compilation cache), one per CPU at a time, pinned
    to it; a run whose record exists is skipped. faults: (name, fault) pairs of the format sample.
    Logs in OUT/logs, progress in OUT/progress.json."""
    out = Path(out)
    (out / "logs").mkdir(parents=True, exist_ok=True)
    jobs = [(name, None) for name in names] + list(faults)
    pending = [j for j in jobs if not record_path(out, _record_name(*j)).exists()]
    running, done = {}, []
    env = dict(os.environ, JAX_ENABLE_X64="1", JAX_ENABLE_COMPILATION_CACHE="false",
               OPENBLAS_NUM_THREADS="1")  # fmt: skip
    env.pop("JAX_COMPILATION_CACHE_DIR", None)
    while pending or running:
        for cpu in cpus:
            if cpu in running or not pending:
                continue
            name, fault = pending.pop(0)
            log = (out / "logs" / f"{slug(_record_name(name, fault))}.log").open("w")
            command = ["taskset", "-c", str(cpu), sys.executable, "-m",
                       "validation.fr43_part3_cowriters.run", "one", "--inputs", str(inputs_path),
                       "--run", name, "--out", str(out)]  # fmt: skip
            if fault is not None:
                command += ["--fault", fault]
            proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env)
            running[cpu] = (proc, name, fault, time.time(), log)
        time.sleep(2)
        for cpu, (proc, name, fault, began, log) in list(running.items()):
            if proc.poll() is None:
                continue
            log.close()
            done.append(dict(run=name, fault=fault, cpu=cpu, exit=proc.returncode,
                             wall_s=time.time() - began))  # fmt: skip
            del running[cpu]
            (out / "progress.json").write_text(dumps(dict(done=done, pending=len(pending),
                                                          running=len(running))))  # fmt: skip
    return done


def _record_name(name, fault):
    return name if fault is None else f"{name} fault {fault}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    c = commands.add_parser("one")
    c.add_argument("--inputs", required=True, type=Path)
    c.add_argument("--run", required=True)
    c.add_argument("--out", required=True, type=Path)
    c.add_argument("--fault", choices=FAULTS)
    c = commands.add_parser("launch")
    c.add_argument("--inputs", required=True, type=Path)
    c.add_argument("--out", required=True, type=Path)
    c.add_argument("--cpus", required=True)
    c.add_argument("--runs", nargs="*")
    c.add_argument("--retry", action="store_true")
    c.add_argument("--fault-run", help="the run the fault switches apply to (format sample)")
    c.add_argument("--faults", nargs="*", choices=FAULTS, default=())
    c = commands.add_parser("parse")
    c.add_argument("--inputs", required=True, type=Path)
    c.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "one":
        suffix = None if args.fault is None else f"fault {args.fault}"
        path = one(args.inputs, args.run, args.out, fault=args.fault, name_suffix=suffix)
        entry = json.loads(path.read_text())["entry"]
        print(json.dumps(dict(record=str(path), status=entry["status"], refusal=entry["refusal"])))
        return 0
    if args.command == "launch":
        inputs = worlds.read_inputs(args.inputs)
        names = args.runs or list(worlds.runs(inputs, retry=args.retry))
        cpus = [int(c) for c in args.cpus.split(",")]
        faults = [(args.fault_run, f) for f in args.faults]
        if faults and args.fault_run is None:
            parser.error("--faults needs --fault-run")
        done = launch(args.inputs, args.out, cpus, names, faults=faults)
        return 0 if all(d["exit"] == 0 for d in done) else 1
    summary = parse_all(args.inputs, args.out)
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in summary.items()}))
    return 0 if not summary["departing"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
