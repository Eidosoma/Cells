"""Closed neutral-removal cases with live shared finite ATP/ADP/Pi pools.

The calcium geometry, inventories and physical rates are unchanged from the
frozen calcium cut fixture. Fuel concentrations, standard states and supply
rates are copied explicitly from the frozen finite-energy configuration.
The 50/150-us windows qualify transient continuation, not slow equilibration.
"""

import json
from copy import deepcopy
from pathlib import Path

from validation.tissue import calcium_excision_fixtures as calcium

DT, CUT_TIME, END_TIME = calcium.DT, calcium.CUT_TIME, calcium.END_TIME
ARMS = (*calcium.ARMS, "supply_off", "no_regeneration")


def definition(arm="open", *, catalog="compact", backend="cpu", padded=False):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = calcium.definition(
        arm if arm in calcium.ARMS else "open", catalog=catalog, backend=backend, padded=padded
    )
    source = json.loads(
        (Path(__file__).resolve().parents[2] / "configs/resolved_hcn_extra_energy.json").read_text()
    )
    m, e = raw["model"], raw["experiment"]
    m["id"] = "resolved_calcium_energy@5"
    m["energy_pools"], m["regeneration_ports"], e["regeneration_controls"] = [], [], []
    cells = sorted(m["ionic"]["cells"], key=lambda v: v["id"])
    for i, cell in enumerate(cells):
        old = source["model"]["energy_pools"][i % 2]
        old_cell = next(v for v in source["model"]["ionic"]["cells"] if v["id"] == old["cell_id"])
        pool = deepcopy(old)
        pool.update(
            id="fuel_" + cell["id"],
            cell_id=cell["id"],
            initial_amount_fmol={
                name: value * cell["volume_pL"] / old_cell["volume_pL"]
                for name, value in old["initial_amount_fmol"].items()
            },
        )
        m["energy_pools"].append(pool)
        port = deepcopy(source["model"]["regeneration_ports"][i % 2])
        port.update(id="supply_" + cell["id"], pool_id=pool["id"])
        m["regeneration_ports"].append(port)
        level = 0.0 if arm == "supply_off" else 0.8
        schedule = [dict(time=0.0, availability=level)]
        if cell["id"] == "cell_1":
            schedule += [
                dict(time=19.1e-6, availability=0.0),
                dict(time=89.3e-6, availability=level),
            ]
        if cell["id"] == "cell_0":
            schedule += [
                dict(time=67.1e-6, availability=0.0),
                dict(time=119.3e-6, availability=level),
            ]
        e["regeneration_controls"].append(dict(regeneration_id=port["id"], schedule=schedule))
    owners = {p["id"]: p["inside"] for p in m["ionic"]["membranes"]}
    for patch in m["ionic"]["membranes"]:
        if patch["pump"] is not None:
            patch["pump"]["metabolism"] = dict(
                kind="finite_energy_pool@1", pool_id="fuel_" + patch["inside"]
            )
    for is_er, rows in ((False, m["plasma_transport"]["membranes"]), (True, m["stores"])):
        for row in rows:
            owner = row["cell_id"] if is_er else owners[row["membrane_id"]]
            pump = row["model"]["membrane"]["pump"] if is_er else row["pump"]
            if pump is not None:
                converted = dict(
                    law="finite_atp_er_1ca_betse_positive@1"
                    if is_er
                    else "finite_atp_pmca_betse_positive@1",
                    **{key: pump[key] for key in ("capacity_fmol_per_s", "km_ca_mM", "km_atp_mM")},
                    metabolism=dict(kind="finite_energy_pool@1", pool_id="fuel_" + owner),
                )
                if is_er:
                    row["model"]["membrane"]["pump"] = converted
                else:
                    row["pump"] = converted
    if arm == "no_regeneration":
        m["regeneration_ports"], e["regeneration_controls"] = [], []
    if arm == "reordered":
        m["energy_pools"].reverse()
        m["regeneration_ports"].reverse()
        e["regeneration_controls"].reverse()
    times = {v["time"] for row in e["regeneration_controls"] for v in row["schedule"]}
    e["observation_times"] = sorted(set(e["observation_times"]) | times)
    raw["execution"]["regeneration_capacity"] = len(m["regeneration_ports"]) + int(padded)
    return raw


def cut_plan(arm="open"):
    if arm not in ARMS:
        raise ValueError(arm)
    return calcium.cut_plan(arm if arm in calcium.ARMS else "open")
