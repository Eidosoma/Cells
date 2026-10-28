"""Manufactured finite ATP and water cases; neutral pool osmolytes are explicit."""

import json
from copy import deepcopy
from pathlib import Path

from validation.tissue import surface_energy_fixtures as energy

DT = energy.DT
END_TIME = energy.END_TIME
CHECKPOINT_TIME = energy.CHECKPOINT_TIME
STEPS = energy.STEPS
ARMS = (*energy.ARMS, "sealed")
WATER_RELEASE_TIMES = (11.3e-6, 29.1e-6)


def definition(arm="coupled", *, backend="cpu", padded=False, dt=DT):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = energy.definition(
        "coupled" if arm == "sealed" else arm, backend=backend, padded=padded, dt=dt
    )
    source = json.loads(
        (
            Path(__file__).resolve().parents[2] / "configs/resolved_energy_water_tissue.json"
        ).read_text()
    )
    m, e = raw["model"], raw["experiment"]
    m.update(
        id="resolved_energy_water@1",
        energy_osmotic_coupling="neutral_ideal_atp_adp_pi@1",
        water_compartments=deepcopy(source["model"]["water_compartments"]),
        water_membranes=[
            dict(membrane_id=p["id"], hydraulic_permeability_m_per_Pa_s=1e-10)
            for p in m["membranes"]
        ],
    )
    schedule = [dict(time=0.0, availability=0.0 if arm == "sealed" else 1.0)]
    if arm == "release":
        schedule += [
            dict(time=WATER_RELEASE_TIMES[0], availability=0.0),
            dict(time=WATER_RELEASE_TIMES[1], availability=0.8),
        ]
        e["observation_times"] = sorted(set(e["observation_times"]) | set(WATER_RELEASE_TIMES))
    e["water_controls"] = [
        dict(membrane_id=p["id"], schedule=deepcopy(schedule)) for p in m["membranes"]
    ]
    return raw


normalized = energy.normalized


def multicell(*, backend="cpu", padded=True):
    """Distinct finite pools and supply owners, shared outside and pump patches."""
    from validation.tissue import surface_water_kinetic_fixtures as active_water

    raw = active_water.multicell(backend=backend, padded=padded)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    sample = definition()
    m.update(id="resolved_energy_water@1", energy_osmotic_coupling="neutral_ideal_atp_adp_pi@1")
    m["energy_pools"], m["regeneration_ports"], e["regeneration_controls"] = [], [], []
    for i, cell in enumerate(m["cells"]):
        pool = deepcopy(sample["model"]["energy_pools"][0])
        pool.update(id=f"energy_{i}", cell_id=cell["id"])
        pool["initial_amount_fmol"] = {
            k: v * (i + 1) for k, v in pool["initial_amount_fmol"].items()
        }
        m["energy_pools"].append(pool)
        port = deepcopy(sample["model"]["regeneration_ports"][0])
        port.update(id=f"regeneration_{i}", pool_id=pool["id"])
        m["regeneration_ports"].append(port)
        e["regeneration_controls"].append(
            dict(
                regeneration_id=port["id"],
                schedule=[dict(time=0.0, availability=1 / (i + 1))],
            )
        )
    for patch in m["membranes"]:
        pool = next(pool for pool in m["energy_pools"] if pool["cell_id"] == patch["inside"])
        patch["pump"]["metabolism"] = dict(kind="finite_energy_pool@1", pool_id=pool["id"])
        patch["pump"]["capacity_fmol_per_s"] = 200.0
    x["regeneration_capacity"] = len(m["regeneration_ports"]) + int(padded)
    return raw
