"""Check the FR-42 label update in binary64 and in the compiled labelled/unlabelled tissue pair."""

import json
import math
from pathlib import Path
from statistics import mean, stdev

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.numerics import label_shares
from tests.unit import test_neutral_arrival_labels as fixture


def step_comparison():
    # (starting amount, gross arrivals, known loss exponent); amounts in fmol.
    cases = [
        (1.0, 0.2, 0.5),
        (3.0, 0.25, 1e-10),
        (1e-9, 1e-9, 3.0),
        (1.0, 5.0, 1000.0),
        (0.0, 1.0, 1.5),
        (2.0, 0.0, 0.7),
        (2.0, 0.25, 0.0),
        (0.0, 0.75, 0.0),
    ]
    old, arrived, exponent = np.array(cases).T
    phi = np.array([1.0 if u == 0 else -math.expm1(-u) / u for u in exponent])
    surviving = old * np.array([math.exp(-u) for u in exponent])
    target = surviving + arrived * phi
    # Two old labels, one receiving all arrivals, one empty. Shape [species, label, node].
    initial = np.array([[[0.625], [0.375], [0.0], [0.0]]])
    shares = np.broadcast_to(initial, (1, 4, len(cases)))
    gains = np.zeros_like(shares)
    gains[0, 2] = arrived
    present = np.ones((1, 4), dtype=bool)
    expected = (surviving * shares + phi * gains) / target
    results = {}
    for name, xp in (("numpy", np), (f"jax_{jax.default_backend()}", jnp)):
        fitted = np.asarray(
            label_shares.survival_exponent(
                xp.asarray(old), xp.asarray(target), xp.asarray(arrived), xp=xp
            )
        )
        actual = np.asarray(
            label_shares.advance(
                xp.asarray(shares),
                xp.asarray(old[None]),
                xp.asarray(target[None]),
                xp.asarray(gains),
                xp.asarray(present),
                xp=xp,
            )
        )
        np.testing.assert_allclose(fitted, exponent, rtol=2e-13, atol=2e-14)
        np.testing.assert_allclose(actual, expected, rtol=2e-13, atol=0)
        assert np.all(actual >= 0) and np.all(actual <= 1)
        assert np.array_equal(actual[:, :, arrived == 0], shares[:, :, arrived == 0])
        assert np.all(fitted[exponent == 0] == 0)
        assert np.all(actual[0, 3] == 0)
        # An empty row retains its stored shares. The physical total cannot identify its exponent.
        empty = xp.zeros((1, 1))
        kept = label_shares.advance(
            xp.asarray(initial), empty, empty, xp.zeros_like(initial), xp.asarray(present), xp=xp
        )
        assert fixture.bits(kept) == fixture.bits(initial)
        closure = float(np.max(np.abs(actual.sum(axis=1) - 1)))
        assert closure <= 8 * math.ulp(1.0)
        results[name] = dict(
            fitted_exponents=fitted.tolist(),
            max_share_sum_error=closure,
            max_absolute_share_error=float(np.max(np.abs(actual - expected))),
        )
    return dict(inputs=cases, target_fmol=target.tolist(), backends=results)


def compiled_tissue():
    raw = fixture.world()
    spec = parse_spec(fixture.labelled(raw))
    labelled, plain = run(spec), run(parse_spec(raw))
    pair = spec, labelled, plain
    fixture.same_physics(labelled, plain)
    fixture.test_minus_n_squared_keeps_the_shares_and_the_cohort_is_a_quarter(pair)
    fixture.test_a_window_follows_its_cohort_exactly_at_both_boundaries(pair)

    obs = labelled.observations
    species = list(spec.model.species_ids)
    shares = np.asarray(obs.label_share)
    a2 = float(np.asarray(obs.amount)[-1, species.index("A2"), 0])
    j = list(fixture.POOLS).index("A2")
    new = float(a2 * shares[-1, j, fixture.POOLS["A2"][1].index("new"), 0])
    s, j = species.index("S"), len(fixture.POOLS)
    cell = np.asarray(obs.amount)[:, s, 0] * shares[:, j, 1, 0]
    node = (
        np.asarray(obs.extracellular_amount)[:, s, 1]
        * np.asarray(obs.label_outside_share)[:, j, 1, 1]
    )
    times = fixture.OBSERVE
    closure = float(np.max(obs.label_closure_relative))
    assert closure <= 64 * math.ulp(1.0)
    return dict(
        model=raw["model"]["id"],
        compared_history_fields=len(plain.history._fields),
        compared_observations=len(vars(plain.observations)),
        diagnostics_equal=True,
        max_relative_report_closure=closure,
        physical_pool_fmol=a2,
        new_cohort_fmol=new,
        sample_times_s=times,
        cell_cohort_fmol=cell.tolist(),
        outside_cohort_fmol=node.tolist(),
        cell_max_absolute_error_fmol=float(
            np.max(np.abs(cell - [fixture.cell_cohort(t) for t in times]))
        ),
        outside_max_absolute_error_fmol=float(
            np.max(np.abs(node - [fixture.node_cohort(t) for t in times]))
        ),
    )


def actn1_readout():
    path = Path(__file__).with_name("data") / "jovanovic2015_actn1.json"
    rows = json.loads(path.read_text())["replicates"]
    totals = [row["medium"] + row["heavy"] for row in rows]
    fractions = [row["heavy"] / total for row, total in zip(rows, totals, strict=True)]
    return dict(
        paired_signal=totals,
        heavy_fractions=fractions,
        mean=mean(fractions),
        sample_sd=stdev(fractions),
        replicates=len(rows),
    )


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    print(
        json.dumps(
            dict(step=step_comparison(), tissue=compiled_tissue(), actn1=actn1_readout()),
            indent=2,
            allow_nan=False,
        )
    )
