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


def order(engine, reference, times):
    """L4 and L5: {q: e(dt), ratio, judged, passed} against the reference at the sample times."""
    out = {}
    for q in ("n_O", "n_C", "x_O", "x_C"):
        ref = np.asarray([float(v) for v in reference[q]], dtype=float)
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
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    v = worlds.declared("L")
    end = float(v["horizon_s"]) if args.end is None else args.end
    every = 60.0
    times = [every * i for i in range(int(round(end / every)) + 1)]
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
            entry["L4_L5"] = order(planted, json.loads(args.references.read_text()), times)
        (args.out / f"plant_{args.plant}.json").write_text(
            json.dumps(entry, indent=1, default=float)
        )
        return
    verdict = dict(protocol="fr49-compartment-compositions-v1", part="L", end_s=end, dts=DTS)
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
        reference = json.loads(args.references.read_text())
        verdict["L4_L5"] = order(engine, reference, times)
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
