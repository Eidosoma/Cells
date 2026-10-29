"""Full 56-law manufactured active tissue with independent regional declarations."""

from copy import deepcopy

from validation.tissue import active_excision_fixtures
from validation.topology import surface_profile_interventions_fixtures as membrane
from validation.topology.tissue_profile_preparation_fixtures import inputs as static_inputs

CASES = ("SIM", "INIT", "ion-flags", "safe-negative", "close-reopen", "empty-events", "reordered")


def inputs(case="SIM", *, catalog="full"):
    if case not in CASES:
        raise ValueError(case)
    raw = static_inputs("active", "no-later-profiles", permuted=True)
    raw["definition"] = active_excision_fixtures.definition(
        "reordered" if case == "reordered" else "open", catalog=catalog, padded=True
    )
    declared = membrane.inputs("SIM", permuted=True)
    for key in (
        "default",
        "profiles",
        "ion_enabled",
        "interventions",
        "intervention_capacity",
        "intervention_target_capacity",
    ):
        raw[key] = deepcopy(declared[key])
    raw["phase"] = "INIT" if case == "INIT" else "SIM"
    m, e, x = (raw["definition"][k] for k in ("model", "experiment", "execution"))
    e.update(
        end_time=8e-6,
        observation_times=[0.0, 2e-6, 2.5e-6, 3e-6, 3.5e-6, 4e-6, 4.5e-6, 5e-6, 6e-6, 8e-6],
    )
    for kind in ("membrane", "junction", "channel", "pump"):
        for row in e[kind + "_controls"]:
            row["schedule"] = [dict(time=0.0, availability=0.8)]
            name = row[kind + "_id"]
            off, on = (
                (2e-6, 5e-6)
                if kind == "membrane"
                else (3e-6, 6e-6)
                if kind == "junction"
                else (2.5e-6, 4e-6)
                if kind == "channel"
                else (3.5e-6, 4.5e-6)
            )
            selected = (
                name == "membrane_1_bath"
                if kind == "membrane"
                else name == "junction_1_2"
                if kind == "junction"
                else True
                if kind == "channel"
                else name == "pump_membrane_0_bath"
            )
            if selected:
                row["schedule"] += [
                    dict(time=off, availability=0.0),
                    dict(time=on, availability=0.7),
                ]
    x.update(dt=0.0625e-6, jit=False, max_steps=512, max_trace_bytes=2**27)
    for event in raw["interventions"]:
        event["change_s"] = 0.5e-6
    if case == "ion-flags":
        raw["ion_enabled"] = [False] * 6
    if case == "safe-negative":
        for event in raw["interventions"]:
            event["amplitude"] = -0.2
    if case == "close-reopen":
        event = next(v for v in raw["interventions"] if v["kind"] == "Na_mem")
        event.update(
            profiles=["Selected"],
            spatial=None,
            source_function="None",
            amplitude=-2.0,
            dynamic_factor=1.0,
            on_s=1e-6,
            off_s=7e-6,
        )
        raw["interventions"] = [event]
    if case == "empty-events":
        raw["interventions"] = []
        raw["intervention_capacity"] = raw["intervention_target_capacity"] = 0
    assert len(m["channels"]) == 56 if catalog == "full" else True
    return deepcopy(raw)


def public_inputs():
    raw = inputs()
    d = raw["definition"]
    d["experiment"].update(end_time=2e-9, observation_times=[0.0, 1e-9, 2e-9])
    for kind in ("membrane", "junction", "channel", "pump"):
        for row in d["experiment"][kind + "_controls"]:
            row["schedule"] = row["schedule"][:1]
    d["execution"].update(dt=1e-9, max_steps=4)
    event = next(v for v in raw["interventions"] if v["kind"] == "Na_mem")
    event.update(
        profiles=["Selected"],
        spatial=None,
        source_function="None",
        on_s=0.5e-9,
        off_s=1.5e-9,
        change_s=8e-9,
    )
    raw["interventions"] = [event]
    raw["intervention_capacity"] = 1
    raw["intervention_target_capacity"] = len(raw["geometry"]["layout"]["cell_membrane_ids"][-1])
    return raw
