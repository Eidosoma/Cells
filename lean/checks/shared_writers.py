"""Audit FR-43 split-writer accounts, disk restart and each writer's current-volume read."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.operators.species_reactions import LocalSpeciesReactions
from cells.operators.templated_polymerisation import TemplatedPolymerisation
from cells.records.io import load_snapshot, write_run
from validation.tissue import shared_inventory_fixtures as fixtures

EPS = np.finfo(np.float64).eps
COPY_FMOL = 1e15 / 6.02214076e23


def accounts(rows, ids, reserve_sign):
    """X belongs only to the network. Its change independently fixes the network's share of N."""
    n, x = (ids.index(name) for name in ("N", "X"))
    stocks = rows["amount_reference"][:, 0] + rows["amount_increment"][:, :, 0]
    stock_change = stocks[:, n] - stocks[0, n]
    reserve = reserve_sign * (stocks[:, x] - stocks[0, x])
    gene = rows["poly_produced_fmol"][:, n, 0] - rows["poly_consumed_fmol"][:, n, 0]
    network = rows["reaction_produced_fmol"][:, n, 0] - rows["reaction_consumed_fmol"][:, n, 0]
    # Each writer can have nonzero cumulative accounts at restart.
    a = gene - gene[0]
    b = network - network[0]
    scale = np.abs(stocks[:, [n, x]]).max() + np.abs(gene).max() + np.abs(network).max()
    tolerance = float(64 * EPS * len(gene) * scale)
    total_error = float(np.max(np.abs(stock_change - (a + b))))
    network_error = float(np.max(np.abs(b - reserve)))
    gene_error = float(np.max(np.abs(a - (stock_change - reserve))))
    assert max(total_error, network_error, gene_error) <= tolerance
    assert abs(a[-1]) > tolerance and abs(b[-1]) > tolerance
    # Move 1% of the network's net booking to the other writer. The total still closes.
    shifted_a, shifted_b = a + 0.01 * b, b - 0.01 * b
    assert np.max(np.abs(stock_change - (shifted_a + shifted_b))) <= tolerance
    shifted_error = float(np.max(np.abs(shifted_b - reserve)))
    assert shifted_error > tolerance
    return dict(
        rows=len(gene),
        stock_change_fmol=float(stock_change[-1]),
        gene_net_fmol=float(a[-1]),
        network_net_fmol=float(b[-1]),
        starting_net_books_fmol=[float(gene[0]), float(network[0])],
        max_total_error_fmol=total_error,
        max_gene_error_fmol=gene_error,
        max_network_error_fmol=network_error,
        allowance_fmol=tolerance,
        misattributed_network_error_fmol=shifted_error,
    )


def fixed(directory):
    spec = parse_spec(fixtures.pair("source", end=10.0, every=0.5))
    result = run(spec)
    bundle = directory / "fixed"
    write_run(bundle, result, checkpoint_times=(5.0,))
    manifest = json.loads((bundle / "manifest.json").read_text())
    loaded = load_snapshot(bundle / manifest["snapshots"][0])
    resumed = run(loaded.spec, loaded.checkpoint)
    write_run(directory / "restart", resumed)
    start = loaded.checkpoint.step_index
    np.testing.assert_array_equal(resumed.times, result.times[start:])
    for name in result.history._fields:
        original = np.asarray(getattr(result.history, name))[start:]
        replay = np.asarray(getattr(resumed.history, name))
        assert (original.dtype, original.shape, original.tobytes()) == (
            replay.dtype,
            replay.shape,
            replay.tobytes(),
        ), name
    ids = list(spec.model.species_ids)
    with np.load(bundle / "trajectory.npz") as rows:
        whole = accounts(rows, ids, -1)  # X supplies N.
    with np.load(directory / "restart" / "trajectory.npz") as rows:
        tail = accounts(rows, ids, -1)
    assert all(value != 0 for value in tail["starting_net_books_fmol"])
    return dict(
        whole=whole,
        restarted=tail,
        checkpoint_s=loaded.checkpoint.time,
        matching_state_fields=len(result.history._fields),
    )


def rate_check(times, counter, i, numerator, volume, initial_volume, planted):
    """Read rates from two centered time intervals on the saved trajectory, in fmol/s."""
    current, stale = numerator / volume, numerator / initial_volume
    measured = [(counter[i + h] - counter[i - h]) / (times[i + h] - times[i - h]) for h in (1, 2)]
    assert current > 0
    errors = {
        key: [abs(value / reference - 1) for value in measured]
        for key, reference in (("current", current), ("initial", stale))
    }
    # A 0.2% local rate comparison at both widths, with at least 5% separation from V0.
    target, other = ("initial", "current") if planted else ("current", "initial")
    assert max(errors[target]) <= 0.002 and min(errors[other]) > 0.05, (measured, current, stale)
    return dict(
        estimated_fmol_s=[float(v) for v in measured],
        current_fmol_s=float(current),
        at_initial_volume_fmol_s=float(stale),
        matched_volume=target,
        max_matched_relative_error=float(max(errors[target])),
        min_other_relative_error=float(min(errors[other])),
    )


def swelling(directory, case):
    raw = fixtures.swelling_pair("sink", dt=0.01, end=4.0, every=1.0)
    spec = parse_spec(raw)
    if case == "swelling":
        result = run(spec)
    else:
        # Run each plant in isolation. Only one native half-step loses its current-volume view.
        writer = {
            "gene-at-initial": TemplatedPolymerisation,
            "network-at-initial": LocalSpeciesReactions,
        }[case]
        original = writer.half_step

        def use_initial(self, *args, view=None, **kwargs):
            return original(self, *args, **kwargs)

        jax.clear_caches()
        try:
            with patch.object(writer, "half_step", use_initial):
                result = run(spec)
        except NumericalError as error:
            if "energy" not in str(error).lower():
                raise
            return dict(planted=case, native_energy_refusal=str(error))
        finally:
            jax.clear_caches()
    bundle = directory / case
    write_run(bundle, result)
    ids = list(spec.model.species_ids)
    n, x = (ids.index(name) for name in ("N", "X"))
    (gene,) = [op for op in raw["model"]["operators"] if "chains" in op]
    (chain,) = gene["chains"]
    (init,) = [
        row["schedule"]
        for row in raw["experiment"]["polymerisation_controls"]
        if row["route_id"] == chain["id"]
    ]
    (init_control,) = init
    (network,) = [op for op in raw["model"]["operators"] if "reactions" in op]
    (sink,) = network["reactions"]
    (control,) = raw["experiment"]["reaction_controls"]
    (multiplier,) = control["schedule"]
    assert multiplier["time"] == init_control["time"] == 0 and control["reaction_id"] == sink["id"]
    k = sink["rate_constant"] * multiplier["multiplier"]
    copies = chain["template"]["copies"]
    with np.load(bundle / "trajectory.npz") as rows:
        balance = accounts(rows, ids, 1)  # Each extent consumes one N and one X.
        stocks = rows["amount_reference"][:, 0] + rows["amount_increment"][:, :, 0]
        volumes = rows["volume"][0] + rows["volume_increment_pL"][:, 0]
        t = rows["accepted_times"]
        probes = []
        for time in (2.0, 3.0):
            (i,) = np.flatnonzero(t == time)
            # From the world's two constitutive laws at the actual stock and free-machine count.
            gene_numerator = (
                init_control["value"] * copies * COPY_FMOL * rows["poly_free_machines_fmol"][i, 0]
            )
            gene_rate = rate_check(
                t,
                rows["poly_initiated_fmol"][:, 0],
                i,
                gene_numerator,
                volumes[i],
                volumes[0],
                case == "gene-at-initial",
            )
            network_rate = rate_check(
                t,
                rows["reaction_extent_fmol"][:, 0],
                i,
                k * stocks[i, n] * stocks[i, x],
                volumes[i],
                volumes[0],
                case == "network-at-initial",
            )
            probes.append(
                dict(
                    time_s=time,
                    volume_pL=float(volumes[i]),
                    initiation=gene_rate,
                    network=network_rate,
                )
            )
        return dict(
            balance=balance,
            initial_volume_pL=float(volumes[0]),
            final_volume_pL=float(volumes[-1]),
            rates=probes,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "case", choices=("fixed", "swelling", "gene-at-initial", "network-at-initial")
    )
    parser.add_argument("--bundles", type=Path, help="keep the native run bundles for this case")
    args = parser.parse_args()
    jax.config.update("jax_enable_x64", True)
    with TemporaryDirectory() as tmp:
        directory = args.bundles or Path(tmp)
        value = fixed(directory) if args.case == "fixed" else swelling(directory, args.case)
        print(json.dumps(value, indent=2, allow_nan=False))
