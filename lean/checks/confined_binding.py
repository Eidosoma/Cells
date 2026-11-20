"""Compare probabilities from the Cells pool reaction R + G ⇌ D with Shon and Cohen Fig. 4f."""

import json
import math
from pathlib import Path

import numpy as np

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages_v2 import IDEAL_MIXING
from cells.models.assembly_lineages_v2.world import AVOGADRO
from tests.assembly_lineage_v2_fixtures import CONVENTIONS, definition, species, step
from validation.assembly_lineages_v2.probes import rate_table

DATA = Path(__file__).with_name("data") / "shon2012_confined_binding.json"


def equilibrium(data, volume_L, kd_nM):
    # At a standard concentration of 1 mM, the activity-form rate is kon × 0.001 M.
    c0_M = 0.001
    counts = data["green_partners"]
    names = ["R@pool", "G@pool", "D@pool", "M@membrane"]
    world = {
        "units": {"time": "s", "temperature_K": 298.15, "standard_concentration_mM": 1.0},
        "conventions": CONVENTIONS,
        "species": [
            species("R", {"r": 1}, solution=0.0),
            species("G", {"g": 1}, solution=0.0),
            species("D", {"r": 1, "g": 1}, solution=math.log(kd_nM * 1e-9 / c0_M)),
            species("M", {"m": 1}, bilayer=0.0),
        ],
        "phases": {
            "pool": {"volume_L": volume_L, "species": [{"id": i, "kind": "finite"} for i in "RGD"]},
            "membrane": {"species": ["M"]},
        },
        "steps": [
            step(
                "bind", {"R": 1, "G": 1}, {"D": 1}, data["association_per_M_s"] * c0_M, phase="pool"
            )
        ],
        "free_energy": [{"law": IDEAL_MIXING}],
        "founder": dict(zip(names, [1, 1, 0, 1], strict=True)),
    }
    spec = parse_spec(definition(world))
    states = [state for n in counts for state in ([1, n, 0, 1], [0, n - 1, 1, 1])]
    plus, minus, _ = rate_table(spec, names, states)
    associate, release = plus[::2, 0], minus[1::2, 0]
    probability = associate / (associate + release)
    per_copy_nM = 1e9 / (AVOGADRO * volume_L)
    available = per_copy_nM * np.asarray(counts)
    np.testing.assert_allclose(probability, available / (available + kd_nM), rtol=1e-13, atol=0)
    return {"volume_aL": volume_L * 1e18, "kd_nM": kd_nM, "probability": probability.tolist()}


def main():
    data = json.loads(DATA.read_text())
    geometry_L = math.pi * data["nominal_radius_nm"] ** 2 * np.mean(data["depth_range_nm"]) * 1e-24
    loading_L = data["loading_mean_count"] / (data["loading_concentration_nM"] * 1e-9 * AVOGADRO)
    observed = data["probability_read_from_figure"]
    p1 = observed[0]
    conditional = []
    for volume in (geometry_L, loading_L):
        fitted_kd = (1 - p1) / p1 * 1e9 / (AVOGADRO * volume)
        conditional.append(equilibrium(data, volume, fitted_kd)["probability"])
    n = np.asarray(data["green_partners"])
    np.testing.assert_allclose(conditional, [n * p1 / (1 - p1 + n * p1)] * 2, rtol=1e-13, atol=0)
    bulk = data["bulk_fluorimeter_kd_nM"]
    return {
        "dataset": data["dataset_id"],
        "observed": observed,
        "one_partner_calibration": conditional[0],
        "bulk_kd_geometry": equilibrium(data, geometry_L, bulk),
        "bulk_kd_loading": equilibrium(data, loading_L, bulk),
        "kinetic_kd_nM": 1e9 * data["dissociation_per_s"] / data["association_per_M_s"],
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, allow_nan=False))
