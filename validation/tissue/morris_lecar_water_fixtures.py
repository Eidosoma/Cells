"""53-law compliant-water compositions; synthetic fixed-interface parameters."""

from copy import deepcopy

from validation.tissue import morris_lecar_catalog_fixtures as channels

MODEL_ID = "resolved_water@3"
ARMS = (*channels.ARMS, "sealed", "reverse", "release")


def definition(arm="open", *, backend="cpu", padded=True):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = channels.definition(
        "ionic", arm if arm in channels.ARMS else "open", backend=backend, padded=False
    )
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    m["id"] = MODEL_ID
    m["water_compartments"] = [
        dict(
            compartment_id=p["id"],
            reference_volume_pL=p["volume_pL"],
            minimum_volume_pL=0.5 * p["volume_pL"],
            maximum_volume_pL=1.5 * p["volume_pL"],
            impermeant_amount_fmol=7.0 + i,
            bulk_modulus_Pa=500000.0,
            pressure_offset_Pa=-500.0 + i,
        )
        for i, p in enumerate(m["cells"] + m["extracellular"])
    ]
    m["water_membranes"] = [
        dict(
            membrane_id=p["id"],
            hydraulic_permeability_m_per_Pa_s=0.0 if arm == "sealed" else (i + 1) * 1e-10,
        )
        for i, p in enumerate(m["membranes"])
    ]
    e["water_controls"] = [
        dict(membrane_id=p["id"], schedule=[dict(time=0.0, availability=0.8)])
        for p in m["membranes"]
    ]
    for kind, key in (
        ("cells", "capacity"),
        ("extracellular", "extracellular_capacity"),
        ("membranes", "membrane_capacity"),
        ("junctions", "edge_capacity"),
        ("faces", "face_capacity"),
        ("channels", "channel_capacity"),
    ):
        x[key] = len(m[kind]) + int(padded)
    if arm == "reverse":
        for patch in m["membranes"]:
            if patch["pump"] is not None:
                patch["pump"]["metabolism"].update(atp_mM=1e-4, adp_mM=10.0, pi_mM=10.0)
    if arm == "reordered":
        m["water_compartments"].reverse()
        m["water_membranes"].reverse()
        e["water_controls"].reverse()
    if arm == "release":
        _probe_events(raw)
    return raw


def _probe_events(raw):
    e, dt = raw["experiment"], raw["execution"]["dt"]
    e.update(end_time=40 * dt, observation_times=[i * dt for i in (0, 10, 15, 20, 25, 30, 35, 40)])
    for name, groups in e.items():
        if name.endswith("_controls"):
            for row in groups:
                row["schedule"] = [c for c in row["schedule"] if c["time"] <= e["end_time"]]
    for row in e["channel_controls"]:
        if row["channel_id"] in ("morris_lecar_0", "morris_lecar_5"):
            first = 10 if row["channel_id"] == "morris_lecar_0" else 20
            row["schedule"].extend(
                [dict(time=first * dt, availability=0.0), dict(time=30 * dt, availability=0.6)]
            )
    e["water_controls"][0]["schedule"].extend(
        [dict(time=15 * dt, availability=0.0), dict(time=35 * dt, availability=0.7)]
    )
    e["pump_controls"][0]["schedule"].append(dict(time=25 * dt, availability=0.0))


def compact_probe(*, backend="cpu", padded=False):
    """Early 50-us coupling; independent water/gate relaxations are separate."""
    return definition("release", backend=backend, padded=padded)


def normalized(raw):
    result = deepcopy(raw)
    result["execution"]["backend"] = "cpu"
    return result
