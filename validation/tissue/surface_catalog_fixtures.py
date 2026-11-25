"""Manufactured shared Na/K/Ca/Cl catalog on multiple tissue membrane owners (resolved_tissue@8).

The closed kinetic tissue (validation/tissue/surface_kinetic_fixtures.py) with calcium as a mobile
ion and the catalogue's 35 laws on 39 populations, spread over its four patches. Every population
has an intrinsic gate pair, the leaks too. Synthetic: no fitted physiology, and no calcium stores.
"""

from validation.tissue import surface_kinetic_fixtures as base

ARMS = ("open", "blocked", "release", "reordered")
K, NA, CA, CL = ((("K", 1.0),), (("Na", 1.0),), (("Ca", 1.0),), (("Cl", 1.0),))
HCN = (("Na", 0.2), ("K", 1.0), ("Ca", 0.05))
# (population, patch, law, permeant ions, permeability m/s, abundance, initial gate)
POPULATIONS = (
    *(
        (f"channel_{i}", i, law, K, 3e-10, 0.5 + 0.1 * i, [0.2 + 0.05 * i, 0.7])
        for i, law in enumerate(("kv1p5_mh@1", "kir2p1_mh2@1") * 2)
    ),
    ("channel_4", 0, "kir2p1_mh2@1", K, 3e-10, 0.5, [0.65, 0.35]),
    *(
        (
            f"sodium_{i}",
            patch,
            "nav1p2_m3h_regularized@1",
            NA,
            3e-10,
            0.2 + 0.1 * i,
            [0.15 + 0.2 * i, 0.8 - 0.2 * i],
        )
        for i, patch in enumerate((0, 2))
    ),
    *(
        (f"hcn_{n}", i, law, HCN, 3e-10, 0.12 + 0.08 * i, [0.35 + 0.1 * i, 0.7])
        for i, (n, law) in enumerate(((1, "hcn1_m@1"), (2, "hcn2_m@1"), (4, "hcn4_m@1")))
    ),
    *(
        (
            f"kv1_{law[4]}",
            i % 4,
            law,
            K,
            3e-10,
            0.10 + 0.04 * i,
            [0.25 + 0.1 * i, 0.65 - 0.05 * i],
        )
        for i, law in enumerate(
            ("kv1p1_mh2@1", "kv1p2_mh@1", "kv1p3_mh@1", "kv1p4_mh@1", "kv1p6_mh@1")
        )
    ),
    *(
        (
            f"cav_population_{i}",
            i % 4,
            law,
            CA,
            1e-9,
            0.10 + 0.02 * i,
            [0.2 + 0.05 * i, 0.7 - 0.04 * i],
        )
        for i, law in enumerate(
            (
                "cav1p2_m2h@1",
                "cav1p3_m2h@1",
                "cav2p1_m@1",
                "cav2p2_m2h_regularized@1",
                "cav2p3_mh@1",
                "cav3p1_mh_piecewise_tau_m@1",
                "cav3p3_mh@1",
            )
        )
    ),
    *(
        (
            f"catalog_population_{i}",
            i % 4,
            law,
            ions,
            1e-9,
            0.05 + 0.01 * (i % 4),
            [0.15 + 0.03 * (i % 7), 0.8 - 0.04 * (i % 6)],
        )
        for i, (law, ions) in enumerate(
            (
                ("nav1p3_m3h_regularized@1", NA),
                ("navrat2_m3h_regularized@1", NA),
                ("navrat1_m3h_regularized@1", NA),
                ("navrat3_m3h_regularized@1", NA),
                ("naleak_always_open@1", NA),
                ("nav1p6_persistent_m@1", NA),
                ("kv2p1_mh@1", K),
                ("kv2p2_mh@1", K),
                ("kv3p1_m@1", K),
                ("kv3p2_m2@1", K),
                ("kv3p3_m2h_long_tau@1", K),
                ("kv3p4_mh@1", K),
                ("k_fast_mh@1", K),
                ("kleak_always_open@1", K),
                ("clleak_always_open@1", CL),
                ("catleak_na_k@1", (("Na", 1.0), ("K", 1.0), ("Ca", 0.0))),
                ("catleak2_na_k_ca@1", (("Na", 1.0), ("K", 1.0), ("Ca", 1.0))),
            )
        )
    ),
)


def with_calcium(raw):
    """The closed kinetic tissue with Ca in every inventory and route, electroneutral as before."""
    m = raw["model"]
    m["species"].append(dict(id="Ca", valence=2))
    for name, concentration in (("cells", 0.002), ("extracellular", 0.02)):
        for owner in m[name]:
            calcium = concentration * owner["volume_pL"]
            owner["initial_amount_fmol"]["Ca"] = calcium
            owner["fixed_charge_equivalent_fmol"] -= 2 * calcium
    for name in ("membranes", "junctions"):
        for route in m[name]:
            route["permeability_m_per_s"]["Ca"] = 1e-9
    for face in m["faces"]:
        face["diffusivity_m2_per_s"]["Ca"] = 1e-10
    raw["execution"]["material_balance_atol_fmol"]["Ca"] = 2e-11
    return raw


def definition(arm="open", *, backend="cpu", padded=True):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = with_calcium(base.definition("closed", backend=backend, padded=padded))
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    m["id"] = "resolved_tissue@8"
    m["channels"] = [
        dict(
            id=name,
            membrane_id=f"membrane_{patch}",
            kinetic_law=law,
            permeant_ions=[dict(species_id=s, relative_permeability=w) for s, w in ions],
            max_permeability_m_per_s=permeability,
            abundance=abundance,
            initial_gate=list(gate),
        )
        for name, patch, law, ions, permeability, abundance, gate in POPULATIONS
    ]
    # Intrinsic gates evolve independently of availability, including leak gates.
    e["channel_controls"] = [
        dict(
            channel_id=channel["id"],
            schedule=[dict(time=0.0, availability=0.0 if arm == "blocked" else 0.8)],
        )
        for channel in m["channels"]
    ]
    if arm == "release":
        for i, row in enumerate(e["channel_controls"]):
            row["schedule"] += [
                dict(time=0.0005 + 0.000025 * (i % 2), availability=0.0),
                dict(time=0.001 + 0.000025 * (i % 2), availability=0.7),
            ]
    events = {c["time"] for g in e["channel_controls"] for c in g["schedule"]}
    e["observation_times"] = sorted(set(e["observation_times"]) | events)
    if arm == "reordered":
        m["species"].reverse()
        m["channels"].reverse()
        e["channel_controls"].reverse()
    # The fast CaV2.1 activation transient needs this RK4 step, over the complete 2 ms.
    x.update(
        dt=1.25e-6,
        max_steps=8192,
        max_trace_bytes=2**32,
        channel_capacity=len(m["channels"]) + int(padded),
    )
    return raw


def compact_probe():
    """Same laws/owners, early trajectory only; no slow-relaxation claim."""
    raw = definition("release", padded=False)
    e = raw["experiment"]
    dt = raw["execution"]["dt"]
    e.update(end_time=40 * dt, observation_times=[i * dt for i in (0, 10, 20, 30, 40)])
    for name, groups in e.items():
        if name.endswith("_controls"):
            for group in groups:
                group["schedule"] = [v for v in group["schedule"] if v["time"] <= e["end_time"]]
    return raw
