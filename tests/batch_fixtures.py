"""Small heterogeneous-in-data worlds for homogeneous execution checks."""

import copy
from pathlib import Path

import numpy as np

from cells.core.batch import BatchSpec, WorldSpec
from cells.core.specs import load_spec, parse_spec

ROOT = Path(__file__).resolve().parents[1]
MODELS = (
    "single_cell_pulse",
    "emt_isolated_e",
    "pair_exchange_pulse",
    "reaction_transport_chain",
    "bioelectric_baseline",
    "bioelectric_pair_baseline",
    "source_pair_controls",
)


def short_spec(name, end=0.3, *, jit=True):
    data = load_spec(ROOT / f"configs/{name}.json").to_dict()

    def trim(value):
        if isinstance(value, list):
            return [
                trim(item)
                for item in value
                if not isinstance(item, dict) or "time" not in item or item["time"] <= end
            ]
        if isinstance(value, dict):
            return {key: trim(item) for key, item in value.items()}
        return value

    data["experiment"] = trim(data["experiment"])
    data["experiment"]["end_time"] = end
    data["experiment"]["observation_times"] = [0.0, 0.113 * end, 0.613 * end, end]
    data["execution"]["jit"] = jit
    data["execution"]["dt"] = min(data["execution"]["dt"], end / 3)
    return parse_spec(data)


def definition(specs, ids=None):
    if ids is None:
        ids = [10 + i for i in range(len(specs))]
    return BatchSpec(
        tuple(WorldSpec(i, s) for i, s in zip(ids, specs, strict=True)), 64, 1000000, 536870912
    )


def assert_parity(got, expected, *, exact=False):
    np.testing.assert_array_equal(got.times, expected.times)
    for a, b in zip(got.history, expected.history, strict=True):
        if exact:
            np.testing.assert_array_equal(a, b)
        else:
            np.testing.assert_allclose(a, b, rtol=2e-12, atol=2e-12)
    assert vars(got.observations).keys() == vars(expected.observations).keys()
    for name, a in vars(got.observations).items():
        b = vars(expected.observations)[name]
        if exact or a.dtype.kind in "bUSiu":
            np.testing.assert_array_equal(a, b)
        else:
            np.testing.assert_allclose(a, b, rtol=2e-11, atol=2e-11)
    for a, b in zip(got.final.layout, expected.final.layout, strict=True):
        np.testing.assert_array_equal(a, b)


def synthetic_pair():
    a = short_spec("single_cell_pulse", 1).to_dict()
    a["experiment"]["source"]["schedule"] = [{"time": 0, "rate": 0}, {"time": 0.137, "rate": 1.5}]
    a["experiment"]["observation_times"] = [0, 0.071, 0.137, 0.5, 1]
    b = copy.deepcopy(a)
    b["model"]["parameters"]["decay_rate"] = 0.7
    b["model"]["initial_state"]["amount"] = 0.8
    b["experiment"]["source"]["schedule"][1]["time"] = 0.173
    b["experiment"]["end_time"] = 0.7
    b["experiment"]["observation_times"] = [0, 0.173, 0.5, 0.7]
    return definition([parse_spec(a), parse_spec(b)])
