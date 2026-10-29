"""Independent finite-fuel calcium cutting with physical, chemical and fuel owners.

The frozen 38-field oracle supplies every stage equation. The frozen calcium
cut oracle rebuilds chemical owners and the electrical field from free cytosol
and whole-cell external-transfer charge. Neutral transformed fuel is separately
owned; pump work is internal and only regeneration supplies external fuel work.
No production Cells/JAX imports, forced neutralization or mechanical cut law.
"""

import math
from copy import deepcopy
from numbers import Real

import numpy as np
from scipy.integrate import solve_ivp

from validation.chemistry import finite_energy_reference as fuel
from validation.tissue import calcium_excision_reference as calcium_cut
from validation.tissue import surface_calcium_energy_reference as energy

MODEL_ID, BASE_ID = "resolved_calcium_energy_excision@1", "resolved_calcium_energy@5"
CONTROL_FAMILIES = (*calcium_cut.CONTROL_FAMILIES, "regeneration")
GATES = calcium_cut.GATES
F, R = energy.F, energy.R
flatten, unpack, initial = energy.flatten, energy.unpack, energy.initial
ExcisionError, ReferenceIntegrationError = (
    calcium_cut.ExcisionError,
    calcium_cut.ReferenceIntegrationError,
)


def physical_definition(raw):
    result = deepcopy(raw)
    if result["model"]["id"] == MODEL_ID:
        result["model"] = deepcopy(result["model"]["tissue"])
    if result["model"]["id"] != BASE_ID or result["model"]["ionic"]["id"] != "resolved_tissue@12":
        raise ValueError(
            "Fuel excision requires exact resolved_calcium_energy@5 / resolved_tissue@12"
        )
    return result


def bind(raw):
    start = (
        raw["model"]["excision"]["source"]["checkpoint"]["time"]
        if raw["model"]["id"] == MODEL_ID
        else 0.0
    )
    c = energy.bind(calcium_cut._ordered(physical_definition(raw)))
    for i, store in enumerate(c["calcium"]["stores"]):
        for j, species in enumerate(c["calcium"]["raw"]["model"]["species"]):
            if store.n0[store.ids.index(species["id"]), store.cy] != c["calcium"]["ai"][j, i]:
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
            raise ValueError("Finite-fuel cut archives require all thirty-eight named fields")
        value = flatten(c, state)
    else:
        value = np.asarray(state)
    if value.shape != initial(c).shape or not np.isfinite(value).all():
        raise ValueError("Require a complete finite thirty-eight-field state")
    return value.copy()


def evaluate(c, state, time):
    value = _state(c, state)
    d = unpack(c, value)
    for i, store in enumerate(c["calcium"]["stores"]):
        if np.any(store.n0 + d["chemical_amount_increment"][i] <= 0):
            raise ValueError("Fuel excision requires positive chemical inventories")
    if np.any(d["calcium_gate"] < 0) or np.any(d["calcium_gate"] > 1):
        raise ValueError("Dedicated calcium gates must stay in [0,1]")
    minimum = np.asarray(
        [p["gate"]["minimum_open_fraction"] for p in c["raw"]["model"]["ionic"]["junctions"]]
    )
    if np.any(d["junction_gate"] < minimum) or np.any(d["junction_gate"] > 1):
        raise ValueError("Intrinsic junction gates lie outside their declared domain")
    try:
        return energy.evaluate(c, value, time)
    except (AssertionError, np.linalg.LinAlgError) as error:
        raise ValueError(
            "Finite-fuel calcium field or charge/current rates are incompatible"
        ) from error


def _calcium_now(c, state):
    """Independent live-pool scalar representation, never production projections."""
    d = unpack(c, state)
    amount = c["energy_initial"] + d["energy_amount_increment_fmol"]
    raw = energy._project(c, amount)
    calcium_cut.active._retain_clocks(raw, event_times(c["raw"]))
    context = calcium_cut.bind(raw)
    return raw, context, flatten(context, d)


def snapshot(c, state, time):
    value = _state(c, state)
    _, phi, proof = evaluate(c, value, time)
    _, current, physical = _calcium_now(c, value)
    result = calcium_cut.snapshot(current, physical, time)
    np.testing.assert_allclose(result["potential_V"], phi, rtol=2e-11, atol=3e-12)
    amount = c["energy_initial"] + unpack(c, value)["energy_amount_increment_fmol"]
    energy_pJ, drive = [], []
    for i in range(len(c["cell_ids"])):
        values = fuel.thermodynamics(
            amount[:, i], c["energy_volumes"][i], c["temperature"], c["energy_delta_g0"][i]
        )
        energy_pJ.append(values["free_energy_pJ"])
        drive.append(values["hydrolysis_free_energy_J_mol"])
    pools = {p["cell_id"]: p for p in c["raw"]["model"]["energy_pools"]}
    result.update(
        pool_ids=[pools[name]["id"] for name in c["cell_ids"]],
        fuel_species_ids=["ATP", "ADP", "Pi"],
        fuel_amount_fmol=amount,
        fuel_moiety_ids=["adenylate", "phosphorus"],
        fuel_moiety_fmol=np.array(
            [amount[0] + amount[1], [math.fsum((a, a, a, b, b, p)) for a, b, p in amount.T]]
        ),
        fuel_free_energy_pJ=np.asarray(energy_pJ),
        fuel_hydrolysis_free_energy_J_mol=np.asarray(drive),
        fuel_charge_C=np.zeros(amount.shape[1]),
        stored_energy_pJ=result["stored_energy_pJ"] + math.fsum(energy_pJ),
        field_proof=proof,
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
        raise ValueError("Cut requires an accepted absolute time in the current finite-fuel epoch")
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
            state=calcium_cut.active._json_values(
                deepcopy(state) if isinstance(state, dict) else unpack(c, value)
            ),
            layout=calcium_cut.active._json_values(
                deepcopy(c["layout"] if source_layout is None else source_layout)
            ),
        ),
    )
    prior_raw, context, physical = _calcium_now(c, value)
    try:
        result = calcium_cut.excise(
            prior_raw, physical, removed, time_s, step_index=step_index, event_index=event_index
        )
    except ExcisionError as error:
        raise ExcisionError(
            str(error),
            archive,
            dict(
                error.audit,
                before=before,
                source_state_fields=38,
                finite_atp_store=True,
                reason="Closed field is incompatible; neutral fuel cannot neutralize plasma charge",
            ),
        ) from error
    result["archive"] = archive
    audit = result["audit"]
    audit.update(
        before=before,
        source_state_fields=38,
        finite_atp_store=True,
        pump_metabolic_work_internal=True,
        maintained_atp_work_internal=True,
        fuel_charge_model="neutral_transformed_atp_adp_pi@1",
        fuel_standard_concentration_mM=1000.0,
    )
    if not removed:
        result.update(raw=deepcopy(raw), context=c, state=value)
        audit["after"] = before
        return result
    indices = [c["cell_ids"].index(name) for name in removed]
    keep = [i for i, name in enumerate(c["cell_ids"]) if name not in removed]
    removed_pool_ids = {
        c["pools"][name]["id"] for name in c["pools"] if c["pools"][name]["cell_id"] in removed
    }
    removed_ports = [
        p["id"] for p in c["raw"]["model"]["regeneration_ports"] if p["pool_id"] in removed_pool_ids
    ]
    audit.update(
        removed_pool_ids=[before["pool_ids"][i] for i in indices],
        removed_regeneration_ids=removed_ports,
        removed_fuel_amount_fmol=before["fuel_amount_fmol"][:, indices].sum(axis=1),
        removed_fuel_moiety_fmol=before["fuel_moiety_fmol"][:, indices].sum(axis=1),
        removed_fuel_free_energy_pJ=float(before["fuel_free_energy_pJ"][indices].sum()),
        removed_fuel_charge_C=0.0,
    )
    if not keep:
        return result
    after = deepcopy(result["raw"])
    original = c["raw"]["model"]
    m = after["model"]
    m["id"] = BASE_ID
    patches = {p["id"]: p for p in original["ionic"]["membranes"]}
    routes = {p["membrane_id"]: p for p in original["plasma_transport"]["membranes"]}
    stores = {p["cell_id"]: p for p in original["stores"]}
    for patch in m["ionic"]["membranes"]:
        patch["pump"] = deepcopy(patches[patch["id"]]["pump"])
    for row in m["plasma_transport"]["membranes"]:
        row["pump"] = deepcopy(routes[row["membrane_id"]]["pump"])
    for row in m["stores"]:
        row["model"]["membrane"]["pump"] = deepcopy(
            stores[row["cell_id"]]["model"]["membrane"]["pump"]
        )
    m["energy_pools"] = [
        deepcopy(p) for p in original["energy_pools"] if p["id"] not in removed_pool_ids
    ]
    for pool in m["energy_pools"]:
        i = c["cell_ids"].index(pool["cell_id"])
        pool["initial_amount_fmol"] = dict(
            zip(("ATP", "ADP", "Pi"), before["fuel_amount_fmol"][:, i].tolist(), strict=True)
        )
    m["regeneration_ports"] = [
        deepcopy(p) for p in original["regeneration_ports"] if p["id"] not in removed_ports
    ]
    after["experiment"]["regeneration_controls"] = [
        deepcopy(p)
        for p in raw["experiment"]["regeneration_controls"]
        if p["regeneration_id"] not in removed_ports
    ]
    after["execution"]["regeneration_capacity"] = raw["execution"]["regeneration_capacity"]
    calcium_cut.active._retain_clocks(after, {*event_times(raw), time_s})
    current = bind(after)
    current["origin_time"] = float(time_s)
    local = initial(current)
    post = snapshot(current, local, time_s)
    np.testing.assert_array_equal(post["fuel_amount_fmol"], before["fuel_amount_fmol"][:, keep])
    np.testing.assert_array_equal(post["fuel_free_energy_pJ"], before["fuel_free_energy_pJ"][keep])
    audit.update(
        after=post,
        unresolved_cut_energy_pJ=(
            post["stored_energy_pJ"]
            - before["stored_energy_pJ"]
            + audit["removed_chemical_energy_pJ"]
            + audit["removed_er_capacitor_energy_pJ"]
            + audit["removed_owned_capacitor_energy_pJ"]
            + audit["removed_fuel_free_energy_pJ"]
            - audit["maintained_boundary_work_pJ"]
        ),
    )
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
        raise ValueError("Invalid finite-fuel calcium reference interval, step or refinement")
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
            "Independent 38-field DOP853, full-node field roots, scalar chemistry "
            "and eight absolute clocks"
        ),
    )
