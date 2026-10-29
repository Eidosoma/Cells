"""Synthetic factor-only examples on real parent membrane and edge owners."""

from copy import deepcopy

from validation.regulation import integrated_network_regulation_fixtures as v1

MODEL_ID = "resolved_calcium_energy_regulated@2"
ARMS = ("active", "empty", "identity", "blocked", "ordered", "reordered")


def definition(arm="active", *, padded=False, compact=False):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = v1.definition("active", padded=padded)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    ion = m["ionic"]
    pumps = {p["pump"]["id"]: p for p in ion["membranes"] if p["pump"] is not None}
    rules = []
    for old in m["network_regulation"]["rules"]:
        patch = pumps[old["pump_id"]]
        rules.append(
            dict(
                id=old["id"],
                kind="nak",
                target_id=old["pump_id"],
                sample_cell_id=patch["inside"],
                sample_exterior_id=patch["outside"],
                fuel_pool_id=old["fuel_pool_id"],
                configuration=old["configuration"],
            )
        )
    for index in (0, 2):
        patch = ion["membranes"][index]
        name = "channel_rule_" + str(index)
        conf = dict(
            name=name,
            **{
                "channel class": "K",
                "channel type": "Kv1p5",
                "max Dm": 0.0,
                "max conductivity": None,
                "apply to": "all",
                "init active": True,
            },
        )
        if index == 0:
            conf.update(
                {
                    "channel activators": ["ATP"],
                    "activator Km": [0.6],
                    "activator n": [2.0],
                    "channel inhibitors": ["Ca"],
                    "inhibitor Km": [0.0006],
                    "inhibitor n": [1.0],
                    "inhibitor max": [0.1],
                }
            )
        else:
            # Multiple floors exercise the actual native unparenthesized sum.
            conf.update(
                {
                    "channel activators": ["Na"],
                    "activator Km": [90.0],
                    "activator n": [1.0],
                    "activator zone": ["env"],
                    "channel inhibitors": ["ADP", "Pi"],
                    "inhibitor Km": [0.4, 0.3],
                    "inhibitor n": [1.0, 2.0],
                    "inhibitor max": [0.1, 0.2],
                }
            )
        rules.append(
            dict(
                id=name,
                kind="channel",
                target_id="channel_" + str(index),
                sample_cell_id=patch["inside"],
                sample_exterior_id=patch["outside"],
                fuel_pool_id="fuel_" + patch["inside"],
                configuration=conf,
            )
        )
    for endpoint in ("cell_0", "cell_1"):
        name = "junction_rule_" + endpoint
        conf = dict(
            name=name,
            target="GJ",
            **{
                "max effect": 0.8,
                "target ion": None,
                "activators": ["ATP" if endpoint == "cell_0" else "Pi"],
                "activator Km": [0.8 if endpoint == "cell_0" else 0.1],
                "activator n": [1.0],
            },
        )
        rules.append(
            dict(
                id=name,
                kind="junction",
                target_id="junction_0",
                sample_cell_id=endpoint,
                sample_exterior_id=None,
                fuel_pool_id="fuel_" + endpoint,
                configuration=conf,
            )
        )
    if arm in ("identity", "blocked"):
        for row in rules:
            old = row["configuration"]
            if row["kind"] == "channel":
                row["configuration"] = {
                    k: v
                    for k, v in old.items()
                    if k
                    in (
                        "name",
                        "channel class",
                        "channel type",
                        "max Dm",
                        "max conductivity",
                        "apply to",
                        "init active",
                    )
                }
                if arm == "blocked":
                    row["configuration"].update(
                        {
                            "channel activators": ["ATP", "ATP&"],
                            "activator Km": [1.0, 1.0],
                            "activator n": [1.0, 1.0],
                            "channel inhibitors": ["ATP&"],
                            "inhibitor Km": [1.0],
                            "inhibitor n": [1.0],
                        }
                    )
            else:
                row["configuration"] = dict(
                    name=row["id"],
                    target=old["target"],
                    **{"max effect": float(arm == "identity"), "target ion": None},
                )
    if arm == "ordered":
        for kind, target, cell, outer in (
            ("nak", "pump_0", "cell_0", "outside_0"),
            ("channel", "channel_0", "cell_0", "outside_0"),
            ("junction", "junction_0", "cell_0", None),
        ):
            name = "last_" + kind
            conf = dict(
                name=name,
                target="Na/K-ATPase" if kind == "nak" else "GJ",
                **{"max effect": 0.23, "target ion": None},
            )
            if kind == "channel":
                conf = dict(
                    name=name,
                    **{
                        "channel class": "K",
                        "channel type": "Kv1p5",
                        "max Dm": 0.0,
                        "max conductivity": None,
                        "apply to": "all",
                        "channel activators": ["Pi&"],
                        "activator Km": [1.0],
                        "activator n": [1.0],
                    },
                )
            rules.append(
                dict(
                    id=name,
                    kind=kind,
                    target_id=target,
                    sample_cell_id=cell,
                    sample_exterior_id=outer,
                    fuel_pool_id="fuel_" + cell,
                    configuration=conf,
                )
            )
    if arm == "empty":
        rules = []
    m.update(
        id=MODEL_ID,
        network_regulation=dict(
            law="betse_network_modulation_source_v1_5_0@1",
            timing="common_stage_free_cytosol_exterior_fuel@1",
            control_composition="scheduled_times_ordered_nak_channel_junction_factor@2",
            channel_scope="native_voltage_independent_sim_factor_only@1",
            junction_scope="explicit_endpoint_cytosol_no_exterior@1",
            rules=rules,
        ),
    )
    if compact:
        ion["channels"] = [r for r in ion["channels"] if r["id"] in ("channel_0", "channel_2")]
        e["channel_controls"] = [
            r for r in e["channel_controls"] if r["channel_id"] in ("channel_0", "channel_2")
        ]
        x["channel_capacity"] = 2 + int(padded)
    x["regulation_capacity"] = len(rules) + int(padded)
    if arm == "reordered":
        ion["species"].reverse()
        ion["channels"].reverse()
        m["energy_pools"].reverse()
        m["stores"].reverse()
        rules.reverse()
    return raw


def parent_definition(raw):
    result = deepcopy(raw)
    result["model"]["id"] = "resolved_calcium_energy@5"
    result["model"].pop("network_regulation")
    result["execution"].pop("regulation_capacity")
    return result


def probe():
    raw = definition(compact=False)
    e = raw["experiment"]
    e.update(end_time=5e-6, observation_times=[0.0, 1.3e-6, 2.5e-6, 3.1e-6, 5e-6])
    for name, groups in e.items():
        if name.endswith("_controls"):
            for group in groups:
                field = "controls" if "controls" in group else "schedule"
                group[field] = [r for r in group[field] if r["time"] <= e["end_time"]]
    for name in ("channel_controls", "junction_controls", "pump_controls"):
        e[name][0]["schedule"].extend(
            [dict(time=1.3e-6, availability=0.0), dict(time=3.1e-6, availability=0.6)]
        )
    return raw
