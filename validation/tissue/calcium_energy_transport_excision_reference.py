"""Independent 42-field configured-transport cut with chemical/fuel owners.

Network routes own histories, not a second material inventory. Their ionic
transport is already in actual free cytosol, finite exterior and plasma charge.
Configured supplied work is external; finite ATP pump work remains internal.
No production Cells/JAX imports, forced neutralization or mechanical cutting law.
"""

from copy import deepcopy
from numbers import Real

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import calcium_energy_excision_reference as energy_cut
from validation.tissue import calcium_energy_network_transport_reference as network

MODEL_ID = "resolved_calcium_energy_transport_excision@1"
BASE_ID = "resolved_calcium_energy_transport@1"
CONTROL_FAMILIES = (*energy_cut.CONTROL_FAMILIES, "network_transport")
GATES = energy_cut.GATES
F, R = network.F, network.R
flatten, unpack, initial = network.flatten, network.unpack, network.initial
ExcisionError, ReferenceIntegrationError = (
    energy_cut.ExcisionError,
    energy_cut.ReferenceIntegrationError,
)


def physical_definition(raw):
    result = deepcopy(raw)
    if result["model"]["id"] == MODEL_ID:
        result["model"] = deepcopy(result["model"]["tissue"])
    if result["model"]["id"] != BASE_ID or result["model"]["ionic"]["id"] != "resolved_tissue@12":
        raise ValueError(
            "Transport excision requires exact resolved_calcium_energy_transport@1 / "
            "resolved_tissue@12"
        )
    return result


def bind(raw):
    start = (
        raw["model"]["excision"]["source"]["checkpoint"]["time"]
        if raw["model"]["id"] == MODEL_ID
        else 0.0
    )
    normalized = energy_cut.calcium_cut._ordered(physical_definition(raw))
    c = network.bind(normalized)
    # Independently enforce the free-only chemical/ionic initial anchor.
    for i, store in enumerate(c["stores"]):
        for j, species in enumerate(c["network_species"]):
            if store.n0[store.ids.index(species), store.cy] != c["ai"][j, i]:
                raise ValueError("The ionic anchor must equal actual free chemical cytosol")
    return dict(c, definition=deepcopy(raw), origin_time=float(start))


def event_times(raw):
    e = raw["experiment"]
    return sorted(
        {
            0.0,
            e["end_time"],
            *(
                v["time"]
                for kind in CONTROL_FAMILIES
                for row in e[kind + "_controls"]
                for v in row.get("schedule", row.get("controls", []))
            ),
        }
    )


def _state(c, state):
    if isinstance(state, dict):
        if set(state) != set(c["shapes"]):
            raise ValueError("Transport cut archives require all forty-two named fields")
        value = flatten(c, state)
    else:
        value = np.asarray(state)
    if value.shape != initial(c).shape or not np.isfinite(value).all():
        raise ValueError("Require a complete finite forty-two-field state")
    return value.copy()


def evaluate(c, state, time):
    value = _state(c, state)
    d = unpack(c, value)
    if np.any(d["calcium_gate"] < 0) or np.any(d["calcium_gate"] > 1):
        raise ValueError("Dedicated calcium gates must stay in [0,1]")
    minimum = np.asarray(
        [p["gate"]["minimum_open_fraction"] for p in c["raw"]["model"]["ionic"]["junctions"]]
    )
    if np.any(d["junction_gate"] < minimum) or np.any(d["junction_gate"] > 1):
        raise ValueError("Intrinsic junction gates lie outside their declared domain")
    try:
        return network.evaluate(c, value, time)
    except (AssertionError, np.linalg.LinAlgError) as error:
        raise ValueError(
            "Configured transport/calcium field or charge/current rates are incompatible"
        ) from error


def _energy_view(c, state):
    raw = deepcopy(c["raw"])
    raw["model"]["id"] = energy_cut.BASE_ID
    raw["model"].pop("network_transport")
    raw["experiment"].pop("network_transport_controls")
    raw["execution"].pop("network_transport_capacity")
    energy_cut.calcium_cut.active._retain_clocks(raw, event_times(c["raw"]))
    current = energy_cut.bind(raw)
    return raw, current, flatten(current, unpack(c, state))


def snapshot(c, state, time):
    value = _state(c, state)
    _, phi, proof = evaluate(c, value, time)
    _, context, physical = _energy_view(c, value)
    result = energy_cut.snapshot(context, physical, time)
    np.testing.assert_allclose(result["potential_V"], phi, rtol=2e-11, atol=3e-12)
    result.update(
        field_proof=proof,
        network_route_ids=list(c["network_ids"]),
        network_route_cell_ids=[c["cell_ids"][owner[0]] for owner in c["network_owners"]],
        network_histories={
            k: v.copy() for k, v in unpack(c, value).items() if k in network.EXTRA_FIELDS
        },
    )
    return result


def excise(
    raw, state, removed_cell_ids, time_s, *, step_index=None, event_index=None, source_layout=None
):
    c = bind(raw)
    if (
        not isinstance(time_s, Real)
        or isinstance(time_s, bool)
        or not np.isfinite(time_s)
        or not c["origin_time"] <= time_s <= raw["experiment"]["end_time"]
    ):
        raise ValueError("Cut requires an accepted absolute time in the current transport epoch")
    if type(removed_cell_ids) not in (list, tuple) or any(
        type(v) is not str for v in removed_cell_ids
    ):
        raise ValueError("Removal must be a list or tuple of owned cell IDs")
    removed = list(removed_cell_ids)
    if len(set(removed)) != len(removed) or not set(removed) <= set(c["cell_ids"]):
        raise ValueError("Require distinct currently owned cell IDs")
    value = _state(c, state)
    before = snapshot(c, value, time_s)
    archive = dict(
        definition=deepcopy(raw),
        checkpoint=dict(
            time=float(time_s),
            step_index=step_index,
            event_index=event_index,
            state=energy_cut.calcium_cut.active._json_values(
                deepcopy(state) if isinstance(state, dict) else unpack(c, value)
            ),
            layout=energy_cut.calcium_cut.active._json_values(
                deepcopy(c["layout"] if source_layout is None else source_layout)
            ),
        ),
    )
    prior_raw, _, physical = _energy_view(c, value)
    try:
        result = energy_cut.excise(
            prior_raw, physical, removed, time_s, step_index=step_index, event_index=event_index
        )
    except ExcisionError as error:
        raise ExcisionError(
            str(error), archive, dict(error.audit, before=before, source_state_fields=42)
        ) from error
    result["archive"] = archive
    audit = result["audit"]
    audit.update(
        before=before,
        source_state_fields=42,
        network_work_external=True,
        network_routes_store_material=False,
        network_material_policy=(
            "Network transfers already belong to chemical/ionic owners; "
            "route ledgers add no material"
        ),
    )
    if not removed:
        result.update(raw=deepcopy(raw), context=c, state=value)
        audit["after"] = before
        return result
    routes = c["raw"]["model"]["network_transport"]["routes"]
    remove_route = np.array(
        [i for i, p in enumerate(c["network_owners"]) if c["cell_ids"][p[0]] in removed], dtype=int
    )
    keep_route = np.array(
        [i for i, p in enumerate(c["network_owners"]) if c["cell_ids"][p[0]] not in removed],
        dtype=int,
    )
    fields = unpack(c, value)
    removed_ids = {routes[i]["id"] for i in remove_route}
    audit.update(
        removed_network_route_ids=[routes[i]["id"] for i in remove_route],
        retained_network_route_ids=[routes[i]["id"] for i in keep_route],
        archived_removed_network_state={
            k: np.take(fields[k], remove_route, axis=-1) for k in network.EXTRA_FIELDS
        },
        archived_retained_network_state={
            k: np.take(fields[k], keep_route, axis=-1) for k in network.EXTRA_FIELDS
        },
    )
    if audit["terminal"]:
        return result
    after = deepcopy(result["raw"])
    m = after["model"]
    m["id"] = BASE_ID
    m["network_transport"] = deepcopy(c["raw"]["model"]["network_transport"])
    m["network_transport"]["routes"] = [deepcopy(p) for p in routes if p["id"] not in removed_ids]
    after["experiment"]["network_transport_controls"] = [
        deepcopy(p)
        for p in raw["experiment"]["network_transport_controls"]
        if p["transporter_id"] not in removed_ids
    ]
    after["execution"]["network_transport_capacity"] = raw["execution"][
        "network_transport_capacity"
    ]
    energy_cut.calcium_cut.active._retain_clocks(after, {*event_times(raw), time_s})
    current = bind(after)
    current["origin_time"] = float(time_s)
    local = initial(current)
    post = snapshot(current, local, time_s)
    audit["after"] = post
    # No new material or energy store belongs to a route. All historical work
    # stays in the source archive; the inherited instantaneous cut diagnostic
    # already includes all retained/removed chemical, fuel and capacitor energy.
    result.update(raw=after, context=current, state=local)
    return result


def integrate(
    raw,
    *,
    state=None,
    start_time=None,
    end_time=None,
    observation_times=None,
    refinement=1,
    max_step_s=5e-6,
    first_step_s=1e-7,
):
    c = bind(raw)
    start = c["origin_time"] if start_time is None else float(start_time)
    end = raw["experiment"]["end_time"] if end_time is None else float(end_time)
    if (
        type(refinement) is not int
        or refinement < 1
        or not np.isfinite([start, end, max_step_s, first_step_s]).all()
        or start < c["origin_time"]
        or end < start
        or min(max_step_s, first_step_s) <= 0
    ):
        raise ValueError("Invalid configured-transport cut reference interval, step or refinement")
    times = (
        sorted(
            {start, end, *(t for t in raw["experiment"]["observation_times"] if start <= t <= end)}
        )
        if observation_times is None
        else list(observation_times)
    )
    if (
        not times
        or times[0] != start
        or times[-1] != end
        or any(b <= a for a, b in zip(times[:-1], times[1:], strict=True))
    ):
        raise ValueError("Observations must cover the ordered absolute interval")
    current = initial(c) if state is None else _state(c, state)
    saved, evaluations = {start: current.copy()}, 0
    events = sorted({start, end, *(t for t in event_times(raw) if start < t < end)})
    atol = flatten(
        c,
        {
            k: np.full(shape, (1e-29 if k.endswith("_C") else 2e-14) / refinement)
            for k, shape in c["shapes"].items()
        },
    )

    def rhs(t, y, held):
        nonlocal evaluations
        evaluations += 1
        try:
            return evaluate(c, y, held)[0]
        except Exception as error:
            raise ReferenceIntegrationError(
                str(error),
                dict(
                    time_s=float(t),
                    held_control_time_s=float(held),
                    state=y.tolist(),
                    evaluations=evaluations,
                    automatic_retry=False,
                ),
            ) from error

    for left, right in zip(events[:-1], events[1:], strict=True):
        solved = solve_ivp(
            lambda t, y, held=left: rhs(t, y, held),
            (left, right),
            current,
            method="DOP853",
            rtol=2e-11 / refinement,
            atol=atol,
            max_step=max_step_s / refinement,
            first_step=min(first_step_s / refinement, max_step_s / refinement, right - left),
            dense_output=True,
        )
        if not solved.success:
            raise ReferenceIntegrationError(
                solved.message, dict(time_s=float(solved.t[-1]), state=solved.y[:, -1].tolist())
            )
        for time in times:
            if left < time <= right:
                saved[time] = solved.y[:, -1].copy() if time == right else solved.sol(time)
        current = solved.y[:, -1].copy()
    return dict(
        times=times,
        state=np.stack([saved[t] for t in times]),
        potential_V=np.stack([evaluate(c, saved[t], t)[1] for t in times]),
        evaluations=evaluations,
        event_times=events,
        start_time=start,
        end_time=end,
        refinement=refinement,
        rtol=2e-11 / refinement,
        amount_energy_gate_atol=2e-14 / refinement,
        electrode_charge_atol_C=1e-29 / refinement,
        max_step_s=max_step_s / refinement,
        first_step_s=first_step_s / refinement,
        method=(
            "Independent 42-field DOP853, full-node field roots, scalar chemistry "
            "and nine absolute clocks"
        ),
    )
