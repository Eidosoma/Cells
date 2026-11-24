"""FR-49 Part L's judge: World L against fr49-compartment-compositions-v1 (REGISTRATION.md §3).

The runs are World L (validation/fr49/worlds.py):
- labelled, with its unlabelled twin, at each step (dt = 2 s and 1 s by default);
- the restart: a checkpoint at 900 s, inside the pulse, at the first step.

It applies the criteria as written:
- L1: every host check on every row (a run that completes passed them);
- L2: the physics bit for bit the twin's;
- L3: nothing labelled before t1;
- L6: expression's rows at the compartment bitwise, and S1–S3;
- L7: the restart bitwise;
- with `--references` (the tagged code-blind results, read only after the lead's tag), L4's order
  and L5's size.

`--plants` also runs the registered plants (§3.2), each of which must fail L3, L4 or L7. They are
planted in this process only, never written to disk:
- (a) the label owner skips the compartment's column;
- (b) arrivals by transfer join the step's arrival label, not their source's shares;
- (c) the routes' one-way amounts halved, FR-42's own plant;
- (d) a checkpoint without `label_outside_share`.

Every number goes to OUT/verdict.json.
"""

import argparse
import contextlib
import dataclasses
import json
import subprocess
import sys
import tempfile
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.kinds import passive_routes, transporter
from cells.models import pump_composite
from cells.numerics import label_shares
from cells.operators import species_labels
from cells.records.io import load_snapshot, write_snapshot
from cells.registry import kind_registry
from cells.registry.models import get_model
from validation.fr49 import worlds
from validation.tissue import compartment_fixtures as cfx

DTS = (2.0, 1.0)
RESTART_AT = 900.0
LABEL_X = 1  # The labels' order: ["base", "x"].
FLOOR = 1e-8  # L4's floor (REGISTRATION.md §3.2).
RATIO = (3.6, 4.4)
SIZE = 1e-3  # L5.
LABELS_ONLY = {
    "label_share",
    "label_outside_share",
    "label_closure_relative",
    "label_pool_share",
    "label_removed_fmol",
    "label_pool_removed_fmol",
    # FR-44 (D327; judge erratum 1, JUDGE_ERRATUM-1.md): the label owner's record of what left at
    # liquid exchanges, zero-size without a wash, as World L is.
    "label_outside_removed_fmol",
}


def bits(value):
    value = np.asarray(value)
    return value.dtype.str, value.shape, value.tobytes()


def run_world(dt, *, labelled=True, end=None):
    spec = parse_spec(worlds.world_l(dt=dt, labelled=labelled, end=end))
    return spec, run(spec)


def references_of(spec):
    _, p = get_model(spec.model).initial_values(spec)
    return np.asarray(p.amount_reference), np.asarray(p.extracellular_amount_reference)


def quantities(spec, result, times):
    """{q: [values at `times`]} for q in n_O, n_C, x_O, x_C (fmol), from the history's rows."""
    rows, cell, node = worlds.rows(spec)
    s = rows[worlds.S]
    cell_ref, node_ref = references_of(spec)
    h = result.history
    index = [int(np.flatnonzero(np.asarray(result.times) == t)[0]) for t in times]
    n_o = cell_ref[s, cell] + np.asarray(h.amount_increment)[index, s, cell]
    n_c = node_ref[s, node] + np.asarray(h.extracellular_amount_increment)[index, s, node]
    out = dict(n_O=n_o, n_C=n_c)
    if hasattr(h, "label_share"):
        out["x_O"] = n_o * np.asarray(h.label_share)[index, 0, LABEL_X, cell]
        out["x_C"] = n_c * np.asarray(h.label_outside_share)[index, 0, LABEL_X, node]
    return {k: np.asarray(v, dtype=float) for k, v in out.items()}


def same_physics(labelled, plain):
    """L2: the twin's every history field, observation and diagnostic, bit for bit. Returns the
    names that differ, and whether the extra fields are the label owner's alone."""
    differ = [
        name
        for name in type(plain.history)._fields
        if bits(getattr(labelled.history, name)) != bits(getattr(plain.history, name))
    ]
    differ += [
        f"observations.{name}"
        for name, value in vars(plain.observations).items()
        if bits(getattr(labelled.observations, name)) != bits(value)
    ]
    if labelled.diagnostics != plain.diagnostics:
        differ.append("diagnostics")
    extra = set(type(labelled.history)._fields) - set(type(plain.history)._fields)
    return differ, extra <= LABELS_ONLY


def base_before_the_pulse(spec, result):
    """L3: every row with t < t1 has label x's share exactly 0 at the owner and the compartment."""
    t1 = float(worlds.declared("L")["pulse_s"]["t1"])
    _, cell, node = worlds.rows(spec)
    early = np.asarray(result.times) < t1
    h = result.history
    at_o = np.asarray(h.label_share)[early, 0, LABEL_X, cell]
    at_c = np.asarray(h.label_outside_share)[early, 0, LABEL_X, node]
    return dict(rows=int(early.sum()), all_zero=bool(np.all(at_o == 0.0) and np.all(at_c == 0.0)))


def silence(spec, result):
    """L6: expression's rows at the compartment bitwise their declared amounts on every row, and
    S1–S3 (compartment_fixtures.silence) at the compartment."""
    rows, _, node = worlds.rows(spec)
    (block,) = [d for d in spec.model.operators if d.law == "templated_polymerisation@1"]
    listed = [rows[s.id] for s in block.species]
    state, _ = get_model(spec.model).initial_values(spec)
    start = np.asarray(state.extracellular_amount_increment)[listed, node]
    seen = np.asarray(result.history.extracellular_amount_increment)[:, listed, node]
    expressed = bool(np.all(seen == start[None, :]))
    found = cfx.silence(
        spec, result.observations, node=worlds.NODE, patch=worlds.PATCH, owner=worlds.CELL
    )
    ok = expressed and found["s1"] and found["s2"] <= 1.0 and found["s3"] <= 1.0
    return dict(expression_rows_bitwise=expressed, **found, passed=bool(ok))


def restart(spec, result, *, plant=False):
    """L7: a checkpoint at RESTART_AT, written and loaded, resumed: bit for bit (each history field
    from the checkpoint's row on). With `plant`, the checkpoint's label_outside_share is replaced by
    its value at t = 0 first (plant (d))."""
    checkpoint = result.checkpoint_at(RESTART_AT)
    if plant:
        state = checkpoint.state._replace(
            label_outside_share=np.asarray(result.history.label_outside_share)[0].copy()
        )
        checkpoint = dataclasses.replace(checkpoint, state=state)
    with tempfile.TemporaryDirectory() as tmp:
        write_snapshot(Path(tmp) / "checkpoint", result.spec, checkpoint)
        loaded = load_snapshot(Path(tmp) / "checkpoint")
        resumed = run(loaded.spec, loaded.checkpoint)
    differ = [
        name
        for name, a, b in zip(
            type(result.history)._fields, resumed.history, result.history, strict=True
        )
        if bits(a) != bits(np.asarray(b)[checkpoint.step_index :])
    ]
    return dict(fields_differing=differ, passed=not differ)


KIND = "cells.fr49_reference_result@1"
PROTOCOL = "fr49-compartment-compositions-v1"
QUANTITIES = ("n_O", "n_C", "x_O", "x_C")
DECLARED = ("V_O_pL", "V_C_pL", "a_pL_per_s", "k_d_per_s", "P_fmol_per_s", "initial_fmol")
DECLARED += ("pulse_s", "horizon_s")


class ReaderError(ValueError):
    """A references file not in the results layout, or not answering World L's declared inputs."""


def _equal(a, b):
    """Declared values equal as decimals, objects key by key."""
    if isinstance(a, dict) or isinstance(b, dict):
        if not (isinstance(a, dict) and isinstance(b, dict) and a.keys() == b.keys()):
            return False
        return all(_equal(a[k], b[k]) for k in a)
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except InvalidOperation:
        return a == b


def _numbers(values, name):
    """A list of finite numbers (decimal strings or JSON numbers) in binary64, or ReaderError."""
    if not isinstance(values, list) or not values:
        raise ReaderError(f"{name} is missing or not a list")
    try:
        array = np.asarray([float(x) for x in values], dtype=float)
    except (TypeError, ValueError) as error:
        raise ReaderError(f"{name} holds an entry that is not a number") from error
    if not np.isfinite(array).all():
        raise ReaderError(f"{name} holds an entry that is not finite")
    return array


def read_reference(path, times, *, cases=worlds.SPEC, invented=False):
    """{q: values at `times`} for q in QUANTITIES, from a references file in the results layout
    (the spec README's "What to produce", as its format sample shows it). It checks the file's
    structure and inputs, never its values:
    - kind, protocol and world "L";
    - `inputs.invented` is `invented`, so that a format sample is never judged as the references
      and the check-reader never opens the references;
    - the declared inputs, and the sample-times rule, are World L's in `cases`, compared as
      decimals;
    - `sample_times_s` holds each of `times`;
    - each quantity is a list of finite numbers, one per sample time.
    Raises ReaderError naming what is wrong, never a value. D308 requires this reader to exist at
    a tag before it reads the references: --check-reader runs it on the format sample, against the
    invented cases the sample was made from."""
    doc = json.loads(Path(path).read_text())
    if not isinstance(doc, dict):
        raise ReaderError("the file is not a JSON object")
    for key, want in (("kind", KIND), ("protocol", PROTOCOL), ("world", "L")):
        if doc.get(key) != want:
            raise ReaderError(f"{key} is {doc.get(key)!r}, not {want!r}")
    inputs = doc.get("inputs")
    if not isinstance(inputs, dict) or bool(inputs.get("invented", False)) != invented:
        raise ReaderError(
            "inputs.invented is not true: --check-reader reads a format sample only"
            if invented
            else "inputs.invented is true: a format sample, not the references"
        )
    world = json.loads(Path(cases).read_text())["worlds"]["L"]
    declared = doc.get("declared")
    if not isinstance(declared, dict):
        raise ReaderError("declared is missing")
    for key in DECLARED:
        if key not in declared or not _equal(declared[key], world[key]):
            raise ReaderError(f"declared {key} is not World L's in {cases}")
    if declared.get("sample_times_rule") != world["sample_times_s"]["rule"]:
        raise ReaderError(f"declared sample_times_rule is not World L's in {cases}")
    t = _numbers(doc.get("sample_times_s"), "sample_times_s")
    index = []
    for target in times:
        hit = np.flatnonzero(np.abs(t - target) <= 1e-9 * max(1.0, abs(target)))
        if not hit.size:
            raise ReaderError(f"the sample time {target:g} s is not among the file's {t.size}")
        index.append(int(hit[0]))
    out = {}
    for q in QUANTITIES:
        array = _numbers(doc.get(q), q)
        if array.shape != t.shape:
            raise ReaderError(f"{q} has {array.size} entries for {t.size} sample times")
        out[q] = array[index]
    return out


def order(engine, reference, times):
    """L4 and L5: {q: e(dt), ratio, judged, passed} against the reference (read_reference's
    values at the sample times)."""
    out = {}
    for q in QUANTITIES:
        ref = np.asarray(reference[q], dtype=float)
        e = {dt: float(np.max(np.abs(engine[dt][q] - ref)) / np.max(np.abs(ref))) for dt in engine}
        coarse, fine = e[DTS[0]], e[DTS[1]]
        judged = coarse >= FLOOR
        ratio = coarse / fine if fine > 0 else float("inf")
        l4 = (RATIO[0] <= ratio <= RATIO[1]) if judged else fine < FLOOR
        out[q] = dict(e=e, ratio=ratio, judged=judged, l4=bool(l4), l5=bool(fine <= SIZE))
    return out


# ------------------------------------------------------------------ the plants (in-process only)


@contextlib.contextmanager
def plant_skip_column():
    """(a): the label owner keeps the compartment's column at its start value."""
    original = species_labels.NeutralArrivalLabels.advance_inner

    def skipped(self, start, end, transfers, p, *, xp):
        out = original(self, start, end, transfers, p, xp=xp)
        node = NODE_INDEX["node"]
        kept = out.label_outside_share.at[:, :, node].set(start.label_outside_share[:, :, node])
        return out._replace(label_outside_share=kept)

    species_labels.NeutralArrivalLabels.advance_inner = skipped
    try:
        yield "a"
    finally:
        species_labels.NeutralArrivalLabels.advance_inner = original


@contextlib.contextmanager
def plant_transfers_take_the_arrival_label():
    """(b): every arrival by transfer joins the step's arrival label, not its source's shares.
    The step's label is read from its control where the composite calls the inner step."""
    holder = {}
    original_inner = pump_composite.Composition._labelled_inner
    original_carried = label_shares.carried

    def inner(self, current, inputs, dt, process, control, p, *, xp):
        holder["arrival"] = self.label_owner.labels(control, p)[1]
        try:
            return original_inner(self, current, inputs, dt, process, control, p, xp=xp)
        finally:
            holder.pop("arrival", None)

    def carried(shares, transfers, *, xp):
        if "arrival" not in holder:
            return original_carried(shares, transfers, xp=xp)
        # The step's arrival label, one-hot [m, label], in place of every source's shares.
        one_hot = xp.broadcast_to(holder["arrival"][:, :, None], shares.shape)
        return original_carried(one_hot, transfers, xp=xp)

    pump_composite.Composition._labelled_inner = inner
    label_shares.carried = carried
    try:
        yield "b"
    finally:
        pump_composite.Composition._labelled_inner = original_inner
        label_shares.carried = original_carried


@contextlib.contextmanager
def plant_halved():
    """(c): the passive routes' one-way amounts halved in both directions (FR-42's plant)."""

    def halved(start, end, p, dt, rows, *, weight=None, xp):
        out = passive_routes.label_transfers(start, end, p, dt, rows, weight=weight, xp=xp)
        return tuple((0.5 * amount, source, destination) for amount, source, destination in out)

    kinds = kind_registry.KindRegistry()
    for kind in (passive_routes.PASSIVE_ROUTES, transporter.TRANSPORTER):
        kinds.register(
            dataclasses.replace(kind, label_transfers=halved)
            if kind is passive_routes.PASSIVE_ROUTES
            else kind
        )
    with kind_registry.scope(kinds):
        yield "c"


NODE_INDEX = {}  # The compartment's node index, set before plant (a) runs.
PLANTS = {"a": plant_skip_column, "b": plant_transfers_take_the_arrival_label, "c": plant_halved}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--end", type=float, default=None, help="the horizon (s); registered 3600")
    parser.add_argument("--references", type=Path, default=None, help="the tagged results/L.json")
    parser.add_argument("--plants", action="store_true", help="run plants (a) to (c), each alone")
    parser.add_argument("--plant", choices=sorted(PLANTS), default=None, help=argparse.SUPPRESS)
    parser.add_argument(
        "--check-reader",
        type=Path,
        default=None,
        help="parse a references format sample with read_reference, structure only, and stop",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=None,
        help="with --check-reader: the invented cases.json the format sample was made from",
    )
    args = parser.parse_args(argv)
    if (args.cases is None) != (args.check_reader is None):
        parser.error(
            "--check-reader and --cases go together; a judged run reads the registered spec"
        )
    args.out.mkdir(parents=True, exist_ok=True)
    v = worlds.declared("L")
    end = float(v["horizon_s"]) if args.end is None else args.end
    every = 60.0
    times = [every * i for i in range(int(round(end / every)) + 1)]
    if args.check_reader is not None:  # D308: the reader on a format sample, values unread.
        try:
            parsed = read_reference(args.check_reader, times, cases=args.cases, invented=True)
            report = dict(parsed=True, quantities={q: len(v) for q, v in parsed.items()},
                          times=len(times))  # fmt: skip
        except ReaderError as error:
            report = dict(parsed=False, why=str(error))
        report.update(sample=str(args.check_reader), cases=str(args.cases))
        (args.out / "reader_check.json").write_text(json.dumps(report, indent=1))
        print(json.dumps(report))
        return
    if args.plant is not None:  # One plant, in this fresh process.
        NODE_INDEX["node"] = worlds.rows(parse_spec(worlds.world_l(dt=DTS[0], end=end)))[2]
        planted, entry = {}, {}
        with PLANTS[args.plant]():
            for dt in DTS:
                spec, result = run_world(dt, labelled=True, end=end)
                planted[dt] = quantities(spec, result, times)
                if dt == DTS[0]:
                    entry["L3"] = base_before_the_pulse(spec, result)
        if args.references is not None:
            entry["L4_L5"] = order(planted, read_reference(args.references, times), times)
        (args.out / f"plant_{args.plant}.json").write_text(
            json.dumps(entry, indent=1, default=float)
        )
        return
    verdict = dict(protocol=PROTOCOL, part="L", end_s=end, dts=DTS)
    verdict["references"] = None if args.references is None else str(args.references)
    engine, started = {}, time.perf_counter()
    for dt in DTS:
        spec, labelled = run_world(dt, labelled=True, end=end)
        _, plain = run_world(dt, labelled=False, end=end)
        differ, extra_ok = same_physics(labelled, plain)
        verdict[f"dt={dt:g}"] = dict(
            L1=True,
            L2=dict(fields_differing=differ, extra_fields_are_the_labels=extra_ok,
                    passed=not differ and extra_ok),
            L3=base_before_the_pulse(spec, labelled),
            L6=silence(spec, labelled),
            seconds=time.perf_counter() - started,
        )  # fmt: skip
        engine[dt] = quantities(spec, labelled, times)
        if dt == DTS[0]:
            verdict["L7"] = restart(spec, labelled)
            verdict["L7_plant_d"] = restart(spec, labelled, plant=True)
    saved = {f"{q}@{dt:g}": engine[dt][q] for dt in engine for q in engine[dt]}
    np.savez(args.out / "engine_quantities.npz", **saved)
    if args.references is not None:
        verdict["L4_L5"] = order(engine, read_reference(args.references, times), times)
    if args.plants:
        verdict["plants"] = {}
        for name in PLANTS:  # Each in a fresh process, so no compiled program is shared.
            command = [sys.executable, "-m", "validation.fr49.judge_l", "--out", str(args.out),
                       "--end", str(end), "--plant", name]  # fmt: skip
            if args.references is not None:
                command += ["--references", str(args.references)]
            subprocess.run(command, check=True)
            verdict["plants"][name] = json.loads((args.out / f"plant_{name}.json").read_text())
        verdict["plants"]["d"] = verdict["L7_plant_d"]
    verdict["seconds"] = time.perf_counter() - started
    (args.out / "verdict.json").write_text(json.dumps(verdict, indent=1, default=float))
    print(json.dumps({k: verdict[k] for k in verdict if k != "plants"}, indent=1, default=float))


if __name__ == "__main__":
    main()
