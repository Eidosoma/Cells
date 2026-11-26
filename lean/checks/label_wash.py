"""Replay tracer dilution in four isolated wells with Cells' FR-44 wash and label operators."""

import json
from pathlib import Path

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.registry.models import get_model
from validation.tissue import secreted_species_fixtures as tissue
from validation.tissue import wash_schedule_fixtures as wash

DATA = Path(__file__).with_name("data")


def tracer_world(schedules):
    # One fmol of carrier in each well. Its original material carries the tracer label.
    # Equal-volume refill at the same carrier concentration adds only unlabelled material.
    volume_pL = 1024.0
    carrier_mM = 1.0 / volume_pL
    dt = 1.0 / 64
    end_step = max(map(len, schedules.values())) + 2
    raw = tissue.world(
        nodes=[(node, volume_pL) for node in schedules],
        contacts=[(f"patch_{node}", "cell_0", node) for node in schedules],
        faces=(),
        concentrations_mM=dict.fromkeys(schedules, carrier_mM),
        dt=dt,
        end=end_step * dt,
        observation_times=[step * dt for step in range(end_step + 1)],
    )
    events = [
        (step * dt, node, fraction, {wash.TRACER: carrier_mM})
        for node, fractions in schedules.items()
        for step, fraction in enumerate(fractions, start=1)
    ]
    raw = wash.with_wash(raw, schedules, events)
    raw["model"]["operators"].append(
        dict(
            law="cells.operator.neutral_arrival_labels@1",
            species=[
                dict(
                    id=wash.TRACER,
                    labels=["base", "original"],
                    initial=[dict(node=node, shares={"original": 1.0}) for node in schedules],
                )
            ],
        )
    )
    raw["experiment"]["label_arrivals"] = [
        dict(species=wash.TRACER, schedule=[dict(time=0, label="original")])
    ]
    return parse_spec(raw)


def replay():
    durham = json.loads((DATA / "stubbington2018_wash.json").read_text())
    chips = json.loads((DATA / "vloemans2024_dilution.json").read_text())["single_exchange"]
    washes = durham["wash_numbers"]
    assert washes == list(range(len(washes)))
    observations = {"chamber": durham["normalized_intensity"]}
    schedules = {"chamber": [durham["exchange_fraction"]] * washes[-1]}
    for j, chip in enumerate(chips, start=1):
        # Effective blank volume / final plug volume. The chip diverts excess stock upstream.
        node = f"chip_{j}"
        stock, diluted = chip["measured"]
        schedules[node] = [chip["fraction"]]
        observations[node] = [1.0, diluted / stock]

    spec = tracer_world(schedules)
    history = run(spec).history
    _, params = get_model(spec.model).initial_values(spec)
    species = spec.model.species_ids.index(wash.TRACER)
    nodes = [node.id for node in spec.model.extracellular]
    results = {}
    for node, fractions in schedules.items():
        j = nodes.index(node)
        count = np.asarray(history.wash_applied)[:, j]
        rows = np.r_[0, np.flatnonzero(np.diff(count)) + 1]
        np.testing.assert_array_equal(count[rows], np.arange(len(fractions) + 1))
        n = (
            float(params.extracellular_amount_reference[species, j])
            + np.asarray(history.extracellular_amount_increment)[rows, species, j]
        )
        shares = np.asarray(history.label_outside_share)[rows, 0, :, j]
        removed = np.asarray(history.label_outside_removed_fmol)[rows, 0, :, j]
        supplied = np.asarray(history.wash_supplied_fmol)[rows, species, j]
        balance = n[:, None] * shares + removed - n[0] * shares[0]
        balance[:, 0] -= supplied

        predicted = n * shares[:, 1] / (n[0] * shares[0, 1])
        reference = np.cumprod(np.r_[1.0, 1.0 - np.asarray(fractions)])
        tolerance = 32 * np.finfo(np.float64).eps
        np.testing.assert_allclose(n, 1.0, rtol=tolerance, atol=0)
        np.testing.assert_allclose(predicted, reference, rtol=tolerance, atol=0)
        np.testing.assert_allclose(balance, 0, rtol=0, atol=tolerance * (n[0] + supplied[-1]))
        results[node] = dict(
            exchange_fractions=fractions,
            measured_normalized_signal=observations[node],
            engine_original_concentration_ratio=predicted.tolist(),
            measured_minus_engine=(np.asarray(observations[node]) - predicted).tolist(),
            max_abs_label_balance_fmol=float(np.abs(balance).max()),
        )
    return results


if __name__ == "__main__":
    assert jax.config.x64_enabled and jax.default_backend() == "cpu"
    print(json.dumps(replay(), indent=2, allow_nan=False))
