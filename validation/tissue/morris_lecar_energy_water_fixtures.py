"""53-law finite-fuel/water compositions with synthetic owner-local supplies."""

from copy import deepcopy

from validation.tissue import morris_lecar_water_fixtures as water

KINDS = ("energy", "water")
MODEL_IDS = dict(energy="resolved_energy@2", water="resolved_energy_water@2")
ARMS = (*water.ARMS, "supply_off", "inhibited")


def definition(kind="water", arm="open", *, backend="cpu", padded=True):
    if kind not in KINDS or arm not in ARMS:
        raise ValueError((kind, arm))
    raw = water.definition(arm if arm in water.ARMS else "open", backend=backend, padded=padded)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    m["id"] = MODEL_IDS[kind]
    m["energy_pools"], m["regeneration_ports"], e["regeneration_controls"] = [], [], []
    for i, cell in enumerate(m["cells"]):
        amounts = dict(ATP=0.003, ADP=0.0002, Pi=0.0002)
        if arm == "reverse":
            amounts = dict(ATP=3e-6, ADP=0.04, Pi=0.04)
        pool = dict(
            id=f"energy_{i}",
            cell_id=cell["id"],
            law="finite_atp_adp_pi_transformed@1",
            initial_amount_fmol={k: v * (i + 1) for k, v in amounts.items()},
            delta_g0_J_per_mol=-37000.0,
        )
        m["energy_pools"].append(pool)
        port = dict(
            id=f"regeneration_{i}",
            pool_id=pool["id"],
            law="driven_atp_regeneration_tanh@1",
            capacity_fmol_per_s=0.5 * (i + 1),
            supplied_energy_J_per_mol=110000.0,
        )
        m["regeneration_ports"].append(port)
        e["regeneration_controls"].append(
            dict(
                regeneration_id=port["id"],
                schedule=[
                    dict(
                        time=0.0,
                        availability=0.0 if arm in ("supply_off", "reverse") else 0.2 / (i + 1),
                    )
                ],
            )
        )
    for patch in m["membranes"]:
        if patch["pump"] is not None:
            pool = next(p for p in m["energy_pools"] if p["cell_id"] == patch["inside"])
            patch["pump"]["metabolism"] = dict(kind="finite_energy_pool@1", pool_id=pool["id"])
            patch["pump"]["capacity_fmol_per_s"] = 200.0
    if arm == "inhibited":
        for row in e["pump_controls"]:
            for change in row["schedule"]:
                change["availability"] = 0.0
    if arm == "release":
        dt = x["dt"]
        # A supply-only boundary, separate from channel, pump and water clocks.
        e["regeneration_controls"][0]["schedule"].extend(
            [dict(time=17 * dt, availability=0.0), dict(time=33 * dt, availability=0.9)]
        )
        e["observation_times"] = sorted(set(e["observation_times"]) | {17 * dt, 33 * dt})
    if arm == "reordered":
        m["energy_pools"].reverse()
        m["regeneration_ports"].reverse()
        e["regeneration_controls"].reverse()
    x["regeneration_capacity"] = len(m["regeneration_ports"]) + int(padded)
    if kind == "water":
        m["energy_osmotic_coupling"] = "neutral_ideal_atp_adp_pi@1"
    else:
        m.pop("water_compartments")
        m.pop("water_membranes")
        e.pop("water_controls")
    return raw


def compact_probe(kind="water", *, backend="cpu", padded=False):
    """50-us coupling; component fuel and water relaxation evidence is separate."""
    return definition(kind, "release", backend=backend, padded=padded)


def normalized(raw):
    result = deepcopy(raw)
    result["execution"]["backend"] = "cpu"
    return result
