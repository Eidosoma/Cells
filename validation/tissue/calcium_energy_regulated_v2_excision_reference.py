"""Independent regulation-aware cutting of the complete 38-field finite-fuel model.

Every RHS and cut field uses live Decimal @2 factors. The frozen finite-fuel cut
algebra is used only with those effective controls at the exact cut state/time.
After owner removal the original surviving schedules and ordered rules return;
factors are recomputed from actual retained concentrations at every stage.
No Cells/JAX imports, hidden energy store, lysis or mechanical cut-work law.
"""

from copy import deepcopy
from numbers import Real

import numpy as np
from scipy.integrate import solve_ivp

from validation.regulation import integrated_network_regulation_v2_reference as regulation
from validation.tissue import calcium_energy_excision_reference as fuel_cut

MODEL_ID = "resolved_calcium_energy_regulated_excision@1"
BASE_ID = "resolved_calcium_energy_regulated@2"
CONTROL_FAMILIES, GATES = fuel_cut.CONTROL_FAMILIES, fuel_cut.GATES
F, R = fuel_cut.F, fuel_cut.R
flatten, unpack, initial = regulation.flatten, regulation.unpack, regulation.initial
ExcisionError, ReferenceIntegrationError = (
    fuel_cut.ExcisionError,
    fuel_cut.ReferenceIntegrationError,
)
_state = fuel_cut._state
event_times = fuel_cut.event_times


def _targets(model):
    ionic = model["ionic"]
    return {
        "nak": {p["pump"]["id"] for p in ionic["membranes"] if p["pump"] is not None},
        "channel": {p["id"] for p in ionic["channels"]},
        "junction": {p["id"] for p in ionic["junctions"]},
    }


def physical_definition(raw):
    result = deepcopy(raw)
    if result["model"]["id"] == MODEL_ID:
        result["model"] = deepcopy(result["model"]["tissue"])
        source = physical_definition(raw["model"]["excision"]["source"]["definition"])
        targets = _targets(result["model"])
        expected = deepcopy(source["model"]["network_regulation"])
        expected["rules"] = [r for r in expected["rules"] if r["target_id"] in targets[r["kind"]]]
        if result["model"]["network_regulation"] != expected:
            raise ValueError("Cut must preserve every surviving rule, sample owner and its order")
        if result["execution"]["regulation_capacity"] != source["execution"]["regulation_capacity"]:
            raise ValueError("Cut retains the declared regulation capacity")
    if result["model"]["id"] != BASE_ID or result["model"]["ionic"]["id"] != "resolved_tissue@12":
        raise ValueError("Regulated excision requires exact regulated@2 / resolved_tissue@12")
    return result


def _owners(raw):
    model, ionic = raw["model"], raw["model"]["ionic"]
    patches = {p["id"]: p for p in ionic["membranes"]}
    pumps = {p["pump"]["id"]: p for p in patches.values() if p["pump"] is not None}
    channels = {p["id"]: p for p in ionic["channels"]}
    junctions = {p["id"]: p for p in ionic["junctions"]}
    pools = {p["id"]: p for p in model["energy_pools"]}
    seen = set()
    for row in model["network_regulation"]["rules"]:
        name, kind, target = row["id"], row["kind"], row["target_id"]
        if name in seen or kind not in ("nak", "channel", "junction"):
            raise ValueError("Require unique rule IDs and declared consumers")
        seen.add(name)
        if (
            row["fuel_pool_id"] not in pools
            or pools[row["fuel_pool_id"]]["cell_id"] != row["sample_cell_id"]
        ):
            raise ValueError("Rule fuel must belong to its explicit sample cytosol")
        if row["configuration"]["name"] != name:
            raise ValueError("Native rule name must match the declared rule ID")
        if kind == "junction":
            if (
                target not in junctions
                or row["sample_cell_id"]
                not in (junctions[target]["sender"], junctions[target]["receiver"])
                or row["sample_exterior_id"] is not None
            ):
                raise ValueError("Junction regulation requires an actual endpoint and no exterior")
        else:
            if kind == "nak":
                if target not in pumps:
                    raise ValueError("Unknown Na/K regulation target")
                patch = pumps[target]
                if patch["pump"]["metabolism"]["pool_id"] != row["fuel_pool_id"]:
                    raise ValueError("Na/K regulation must read the target pump's fuel")
            else:
                if target not in channels:
                    raise ValueError("Unknown shared-channel regulation target")
                patch = patches[channels[target]["membrane_id"]]
            if (row["sample_cell_id"], row["sample_exterior_id"]) != (
                patch["inside"],
                patch["outside"],
            ):
                raise ValueError("Membrane regulation must read its actual inside/outside owners")
    if raw["execution"]["regulation_capacity"] < len(seen):
        raise ValueError("Regulation capacity is smaller than the ordered rule set")


def bind(raw):
    actual = fuel_cut.calcium_cut._ordered(physical_definition(raw))
    _owners(actual)
    c = regulation.bind(actual)
    # The existing cut binder independently verifies free-cytosol anchors and
    # finite-pool ownership. It does not evaluate an unregulated field here.
    fuel_cut.bind(c["raw"])
    origin = (
        raw["model"]["excision"]["source"]["checkpoint"]["time"]
        if raw["model"]["id"] == MODEL_ID
        else 0.0
    )
    return dict(c, definition=deepcopy(raw), regulated_raw=actual, origin_time=float(origin))


def evaluate(c, state, time):
    value = _state(c, state)
    d = unpack(c, value)
    for i, store in enumerate(c["calcium"]["stores"]):
        if np.any(store.n0 + d["chemical_amount_increment"][i] <= 0):
            raise ValueError("Require positive actual chemical inventories")
    if np.any(d["calcium_gate"] < 0) or np.any(d["calcium_gate"] > 1):
        raise ValueError("Calcium gates must stay in [0,1]")
    minimum = np.asarray(
        [p["gate"]["minimum_open_fraction"] for p in c["raw"]["model"]["ionic"]["junctions"]]
    )
    if np.any(d["junction_gate"] < minimum) or np.any(d["junction_gate"] > 1):
        raise ValueError("Intrinsic junction gates lie outside their declared domain")
    try:
        return regulation.evaluate(c, value, time)
    except (AssertionError, np.linalg.LinAlgError) as error:
        raise ValueError("Regulated field or charge/current rates are incompatible") from error


def effective_parent(c, state, time):
    """Exact instantaneous parent controls, never an unregulated replacement RHS."""
    factors = regulation.factors(c, state, time)
    raw = deepcopy(c["raw"])
    ionic = raw["model"]["ionic"]
    ids = {
        "nak": [p["pump"]["id"] if p["pump"] is not None else None for p in ionic["membranes"]],
        "channel": [p["id"] for p in ionic["channels"]],
        "junction": [p["id"] for p in ionic["junctions"]],
    }
    for kind, family in (("nak", "pump"), ("channel", "channel"), ("junction", "junction")):
        for row in raw["experiment"][family + "_controls"]:
            level = factors["controls"][kind]["effective"][ids[kind].index(row[family + "_id"])]
            row["schedule"] = [dict(time=0.0, availability=level)]
    fuel_cut.calcium_cut.active._retain_clocks(raw, event_times(c["regulated_raw"]))
    return raw, factors


def snapshot(c, state, time):
    value = _state(c, state)
    _, phi, proof = evaluate(c, value, time)
    raw, factors = effective_parent(c, value, time)
    current = fuel_cut.bind(raw)
    result = fuel_cut.snapshot(current, value, time)
    np.testing.assert_allclose(result["potential_V"], phi, rtol=2e-11, atol=3e-12)
    result.update(network_regulation=factors, field_proof=proof, regulator_energy_store=False)
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
        raise ValueError("Cut requires an accepted absolute time in the regulated epoch")
    value = _state(c, state)
    before = snapshot(c, value, time_s)
    archive = dict(
        definition=deepcopy(raw),
        checkpoint=dict(
            time=float(time_s),
            step_index=step_index,
            event_index=event_index,
            state=fuel_cut.calcium_cut.active._json_values(
                deepcopy(state) if isinstance(state, dict) else unpack(c, value)
            ),
            layout=fuel_cut.calcium_cut.active._json_values(
                deepcopy(c["layout"] if source_layout is None else source_layout)
            ),
        ),
    )
    physical, factors = effective_parent(c, value, time_s)
    try:
        result = fuel_cut.excise(
            physical,
            state,
            removed_cell_ids,
            time_s,
            step_index=step_index,
            event_index=event_index,
        )
    except ExcisionError as error:
        raise ExcisionError(
            str(error), archive, dict(error.audit, before=before, regulated_cut_field=True)
        ) from error
    result["archive"] = archive
    audit = result["audit"]
    audit.update(
        before=before,
        source_state_fields=38,
        regulated_cut_field=True,
        regulator_energy_store=False,
    )
    if audit["no_op"]:
        result.update(raw=deepcopy(raw), context=c, state=value)
        audit.update(
            after=before,
            removed_regulator_ids=[],
            retained_regulator_ids=[r["id"] for r in c["rules"]],
        )
        return result
    kept_targets = (
        _targets(result["raw"]["model"])
        if result["raw"] is not None
        else {k: set() for k in ("nak", "channel", "junction")}
    )
    surviving = [r for r in c["rules"] if r["target_id"] in kept_targets[r["kind"]]]
    audit.update(
        removed_regulator_ids=[
            r["id"] for r in c["rules"] if r["target_id"] not in kept_targets[r["kind"]]
        ],
        retained_regulator_ids=[r["id"] for r in surviving],
    )
    if audit["terminal"]:
        return result
    after = result["raw"]
    after["model"]["id"] = BASE_ID
    after["model"]["network_regulation"] = deepcopy(
        c["regulated_raw"]["model"]["network_regulation"]
    )
    after["model"]["network_regulation"]["rules"] = deepcopy(surviving)
    after["execution"]["regulation_capacity"] = raw["execution"]["regulation_capacity"]
    # Undo only the instantaneous control view; continue original absolute
    # schedules for the surviving owners, then carry removed-only boundaries.
    for family in CONTROL_FAMILIES:
        key = (
            "cell_id"
            if family == "store"
            else "channel_id"
            if family == "calcium_channel"
            else "membrane_id"
            if family == "plasma"
            else family + "_id"
        )
        retained = {r[key] for r in after["experiment"][family + "_controls"]}
        after["experiment"][family + "_controls"] = [
            deepcopy(r)
            for r in c["regulated_raw"]["experiment"][family + "_controls"]
            if r[key] in retained
        ]
    fuel_cut.calcium_cut.active._retain_clocks(after, {*event_times(raw), time_s})
    current = bind(after)
    current["origin_time"] = float(time_s)
    local = initial(current)
    post = snapshot(current, local, time_s)
    original = dict(zip((r["id"] for r in c["rules"]), factors["rule_factors"], strict=True))
    np.testing.assert_allclose(
        post["network_regulation"]["rule_factors"],
        [original[r["id"]] for r in surviving],
        rtol=4e-15,
        atol=0.0,
    )
    # All stores/owners and effective controls match the instantaneous remap.
    np.testing.assert_allclose(
        post["potential_V"], audit["after"]["potential_V"], rtol=2e-11, atol=3e-12
    )
    audit.update(after=post, surviving_rule_factors_unchanged=True)
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
        raise ValueError("Invalid regulated reference interval, step or refinement")
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
        method="Independent regulated 38-field DOP853; live Decimal factors; eight absolute clocks",
    )
