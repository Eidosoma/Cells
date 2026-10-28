"""Manufactured shared fuel ownership; no physiological calibration claim."""

from validation.tissue import surface_calcium_catalog_fixtures as prior

ARMS = ("open", "supply_off", "blocked", "reverse", "absent", "reordered")


def definition(arm="open", *, backend="cpu", padded=True):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = prior.definition(
        "reordered" if arm == "reordered" else "open", backend=backend, padded=padded
    )
    m, e = raw["model"], raw["experiment"]
    m["id"] = "resolved_calcium_energy@1"
    m["energy_pools"], m["regeneration_ports"] = [], []
    e["regeneration_controls"] = []
    for i, cell in enumerate(m["ionic"]["cells"]):
        pool = "fuel_" + cell["id"]
        volume = cell["volume_pL"]
        m["energy_pools"].append(
            dict(
                id=pool,
                cell_id=cell["id"],
                law="finite_atp_adp_pi_transformed@1",
                initial_amount_fmol=dict(
                    ATP=volume * (1.5 - 0.4 * i), ADP=volume * (0.1 + 0.1 * i), Pi=volume * 0.1
                ),
                delta_g0_J_per_mol=17000.0 if arm == "reverse" else -37000.0,
            )
        )
        m["regeneration_ports"].append(
            dict(
                id="supply_" + cell["id"],
                pool_id=pool,
                law="driven_atp_regeneration_tanh@1",
                capacity_fmol_per_s=0.12 + 0.03 * i,
                supplied_energy_J_per_mol=85000.0,
            )
        )
        e["regeneration_controls"].append(
            dict(
                regeneration_id="supply_" + cell["id"],
                schedule=[dict(time=0.0, availability=0.0 if arm == "supply_off" else 0.8)],
            )
        )
    owners = {p["id"]: p["inside"] for p in m["ionic"]["membranes"]}

    def convert(pump, owner, kind):
        if pump is None or arm == "absent":
            return None
        meta = dict(kind="finite_energy_pool@1", pool_id="fuel_" + owner)
        if kind == "nak":
            return pump | dict(metabolism=meta)
        return {k: pump[k] for k in ("capacity_fmol_per_s", "km_ca_mM", "km_atp_mM")} | dict(
            law="finite_atp_pmca_betse_positive@1"
            if kind == "pmca"
            else "finite_atp_er_1ca_betse_positive@1",
            metabolism=meta,
        )

    for patch in m["ionic"]["membranes"]:
        patch["pump"] = convert(patch["pump"], patch["inside"], "nak")
    for route in m["plasma_transport"]["membranes"]:
        route["pump"] = convert(route["pump"], owners[route["membrane_id"]], "pmca")
    for store in m["stores"]:
        patch = store["model"]["membrane"]
        patch["pump"] = convert(patch["pump"], store["cell_id"], "er")
    if arm in ("blocked", "absent"):
        if arm == "absent":
            e["pump_controls"] = []
        for row in e["pump_controls"]:
            for c in row["schedule"]:
                c["availability"] = 0.0
        for row in e["plasma_controls"]:
            for c in row["schedule"]:
                c["pump"] = 0.0
        for row in e["store_controls"]:
            for c in row["controls"]:
                c["pump"] = 0.0
    if arm == "reordered":
        for key in ("energy_pools", "regeneration_ports", "stores"):
            m[key].reverse()
        e["regeneration_controls"].reverse()
    raw["execution"]["regeneration_capacity"] = 3 if padded else 2
    return raw


def compact_probe():
    """50 us of live coupled feedback and a supply-only control event, not settling."""
    raw = definition(padded=False)
    dt = raw["execution"]["dt"]
    e = raw["experiment"]
    e.update(end_time=40 * dt, observation_times=[i * dt for i in (0, 10, 20, 30, 40)])
    for name, groups in e.items():
        if name.endswith("_controls"):
            for group in groups:
                key = "controls" if "controls" in group else "schedule"
                group[key] = [c for c in group[key] if c["time"] <= e["end_time"]]
    e["regeneration_controls"][0]["schedule"].append(dict(time=20 * dt, availability=0.0))
    return raw


def assembly_definition(*, backend="cpu"):
    raw = prior.assembly_definition(backend=backend)
    raw["ionic"] = definition(backend=backend)
    return raw
