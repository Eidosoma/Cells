"""Check finite-bath tracer recovery on a synthetic seven-molecule shell using Cells host laws."""

import itertools
import json
import math
from unittest.mock import patch

import jax
import numpy as np
from scipy.linalg import expm

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages_v2 import SHARED_POOL, balance, model, replacement, streams, transfer, withdrawal
from tests.assembly_lineage_v2_fixtures import definition
from tests.unit.test_assembly_lineages_v2_shell_interior import lumen_shell


PERMEABILITY = 4e-8  # m/s
AREA = 2e-16  # m²
POOL_LITRES, LUMEN_LITRES = 8e-20, 4e-20
DELTA = math.log(1.5)
READ_TIME, DRAW_TIME = 0.75, 2.0  # elapsed seconds since replacement
ATOL = 1e-12


def shell():
    world = lumen_shell(solution=0.4, lumen=0.4 + DELTA, n_out=5, n_in=7, P=PERMEABILITY)
    world["phases"]["pool"]["volume_L"] = POOL_LITRES
    world["phases"]["lumen"]["volume_L"] = LUMEN_LITRES
    world["geometry"]["area_m2"]["value"] = AREA
    slot = {p: n for p, n in world["founder"].items() if not p.endswith("@pool")}
    world["population"] = {"structure": SHARED_POOL, "slots": 1, "founders": [slot]}
    world["founder"].update(dict.fromkeys(slot, 0))
    raw = definition(world, molecules=32, horizon=3)
    raw["execution"]["mode"] = "population"
    raw["experiment"]["schedules"] = [
        {"kind": "replacement", "index": 1, "times_s": [0.5], "pool": [0]},
        {"kind": "withdrawal", "index": 2, "times_s": [0.5 + DRAW_TIME], "fraction": 0.5, "buffer": [0]},
    ]
    return parse_spec(raw)


def crossing_matrix(spec, counts, outside, inside):
    structure, layout = model.structure(spec), model.layout(spec)
    total = int(counts[outside] + counts[inside])
    matrix = np.zeros((total + 1, total + 1))
    for k in range(total + 1):
        state = counts.copy()
        state[outside], state[inside] = k, total - k
        log_rates = balance.host_log_rates(state, layout, structure)
        entry, leave = np.exp(log_rates[[0, structure.steps]])
        if k:
            matrix[k, k - 1] = entry
        if k < total:
            matrix[k, k + 1] = leave
        matrix[k, k] = -(entry + leave)
    np.testing.assert_allclose(matrix.sum(axis=1), 0, atol=ATOL, rtol=0)
    return matrix


def mean_half_draws(spec, schedule, outside, pool, total):
    """Supply both equally likely sides of the half-draw threshold for every molecule."""
    key = streams.base_key_data(17, 0, 0, 0)
    means = []
    for n in range(total + 1):
        state = pool.copy()
        state[outside] = n
        removed = 0
        for words in itertools.product((0.25, 0.75), repeat=n):
            with patch.object(streams, "block", return_value=words):
                taken, _ = withdrawal.draw(key, spec.model.world, schedule, 0, state)
            removed += int(taken[outside])
        means.append(removed / 2**n)
    np.testing.assert_array_equal(means, schedule.fraction * np.arange(total + 1))
    return means


def compare():
    spec = shell()
    world = spec.model.world
    full, half = spec.experiment.schedules
    places = [p.name for p in world.places]
    outside, inside = places.index("S@pool"), places.index("S@lumen")
    pool = model.founder(spec)
    fresh = transfer.replaced_pool(world, full, pool)
    removed, supplied = replacement.removed_and_supplied(world, pool, fresh)
    assert removed == {"S@pool": 5} and supplied == {"S@pool": 0}
    counts = fresh.copy()
    counts[:len(places)] += world.population["founders"][0]
    assert counts[outside] == 0 and counts[inside] == 7
    total = int(counts[inside])
    matrix = crossing_matrix(spec, counts, outside, inside)
    half_draws = mean_half_draws(spec, half, outside, fresh, total)
    entry = PERMEABILITY * AREA / (POOL_LITRES * 1e-3)
    leave = PERMEABILITY * AREA * math.exp(DELTA) / (LUMEN_LITRES * 1e-3)
    initial_rate = float(matrix[0, 1])
    np.testing.assert_allclose(initial_rate, total * leave, rtol=0, atol=ATOL)
    reads = []
    indices = np.arange(total + 1)
    for t in (READ_TIME, DRAW_TIME):
        law = expm(matrix * t)[0]
        assert np.min(law) >= -ATOL and abs(law.sum() - 1) <= ATOL
        observed = float(law @ indices)
        predicted = total * leave / (entry + leave) * -math.expm1(-(entry + leave) * t)
        np.testing.assert_allclose([observed, law @ (total - indices)], [predicted, total - predicted],
                                   atol=ATOL, rtol=0)
        row = {"elapsed_s": t, "pool_mean": observed, "pool_formula": predicted}
        if t == DRAW_TIME:
            row["removed_mean"] = float(law @ half_draws)
            np.testing.assert_allclose(row["removed_mean"], half.fraction * predicted, rtol=0, atol=ATOL)
        reads.append(row)
    irreversible = total * -math.expm1(-leave * DRAW_TIME)
    assert irreversible - reads[-1]["pool_mean"] > 0.1
    return {"initial_rate_per_s": initial_rate, "replacement_removed": removed, "reads": reads,
            "pool_if_return_to_lumen_omitted": irreversible, "atol_molecules": ATOL}


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    print(json.dumps(compare(), indent=2, allow_nan=False))
