"""Independent closed calcium/ER excision with complete chemical ownership.

All 34 equations come from the frozen independent calcium oracle. The current
free cytosol sets concentrations, while the external-transfer ledger sets plasma
charge. Internal binding/ER movement cannot change that charge. Cutting rebuilds
the full-node field and records an energy jump without a mechanical work law.
No production Cells/JAX imports, repair or neutralization are used.
"""

import math
from copy import deepcopy
from numbers import Real

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import active_excision_reference as active
from validation.tissue import surface_calcium_reference as calcium

MODEL_ID, BASE_ID = "resolved_calcium_excision@1", "resolved_calcium@11"
CONTROL_FAMILIES = (*active.CONTROL_FAMILIES, "store", "plasma", "calcium_channel")
GATES = (*active.GATES, "calcium_gate")
F, R = calcium.F, calcium.R
flatten, unpack, initial = calcium.flatten, calcium.unpack, calcium.initial
ExcisionError, ReferenceIntegrationError = active.ExcisionError, active.ReferenceIntegrationError


def physical_definition(raw):
    result = deepcopy(raw)
    if result["model"]["id"] == MODEL_ID:
        result["model"] = deepcopy(result["model"]["tissue"])
    if result["model"]["id"] != BASE_ID or result["model"]["ionic"]["id"] != "resolved_tissue@12":
        raise ValueError("Calcium excision requires exact resolved_calcium@11 / resolved_tissue@12")
    if any(row["reservoir"] for row in result["model"]["ionic"]["extracellular"]):
        raise ValueError("This calcium parent requires finite extracellular ownership")
    return result


def _ordered(raw):
    """Bind owner-indexed scalar calcium rows by IDs, independently of list order."""
    model, experiment = raw["model"], raw["experiment"]
    ionic = model["ionic"]
    cells = [v["id"] for v in ionic["cells"]]
    membranes = [v["id"] for v in ionic["membranes"]]
    for name in ("stores", "ip3_release"):
        rows = {v["cell_id"]: v for v in model[name]}
        model[name] = [rows[name] for name in cells]
    rows = {v["membrane_id"]: v for v in model["plasma_transport"]["membranes"]}
    model["plasma_transport"]["membranes"] = [rows[name] for name in membranes]
    rows = {v["membrane_id"]: v for v in model["calcium_channels"]}
    model["calcium_channels"] = [rows[name] for name in membranes]
    for family, key, ids in (
        ("store", "cell_id", cells),
        ("plasma", "membrane_id", membranes),
        ("calcium_channel", "channel_id", [v["id"] for v in model["calcium_channels"]]),
    ):
        rows = {v[key]: v for v in experiment[family + "_controls"]}
        experiment[family + "_controls"] = [rows[name] for name in ids]
    return raw


def bind(raw):
    start = (
        raw["model"]["excision"]["source"]["checkpoint"]["time"]
        if raw["model"]["id"] == MODEL_ID
        else 0.0
    )
    c = calcium.bind(_ordered(physical_definition(raw)))
    for i, store in enumerate(c["stores"]):
        for j, species in enumerate(c["raw"]["model"]["species"]):
            if store.n0[store.ids.index(species["id"]), store.cy] != c["ai"][j, i]:
                raise ValueError("The ionic anchor must equal actual free cytosol inventory")
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
            raise ValueError("Calcium cut archives require all thirty-four named fields")
        value = flatten(c, state)
    else:
        value = np.asarray(state)
    if value.shape != initial(c).shape or not np.isfinite(value).all():
        raise ValueError("Require a complete finite thirty-four-field state")
    return value.copy()


def evaluate(c, state, time):
    value = _state(c, state)
    d = unpack(c, value)
    for i, store in enumerate(c["stores"]):
        if np.any(store.n0 + d["chemical_amount_increment"][i] <= 0):
            raise ValueError("Calcium excision requires positive chemical inventories")
    if np.any(d["calcium_gate"] < 0) or np.any(d["calcium_gate"] > 1):
        raise ValueError("Dedicated calcium gates must stay in [0,1]")
    minimum = np.asarray(
        [v["gate"]["minimum_open_fraction"] for v in c["raw"]["model"]["junctions"]]
    )
    if np.any(d["junction_gate"] < minimum) or np.any(d["junction_gate"] > 1):
        raise ValueError("Intrinsic junction gates lie outside their declared domain")
    try:
        return calcium.evaluate(c, value, time)
    except (AssertionError, np.linalg.LinAlgError) as error:
        raise ValueError("Calcium tissue field or charge/current rates are incompatible") from error


def _ionic_now(c, state):
    """Exact physical ionic field view; external-transfer charge is not free charge."""
    d = unpack(c, state)
    raw = deepcopy(c["raw"])
    m = raw["model"]
    z = np.asarray(c["layout"]["valence"])[:, 0]
    for i, row in enumerate(m["cells"]):
        store = c["stores"][i]
        amount = store.n0 + d["chemical_amount_increment"][i]
        free = [amount[store.ids.index(s["id"]), store.cy] for s in m["species"]]
        q = c["qi"][i] + F * 1e-15 * math.fsum(z * d["amount_increment"][:, i])
        row.update(
            initial_amount_fmol=dict(zip((s["id"] for s in m["species"]), free, strict=True)),
            initial_charge_C=q,
            fixed_charge_equivalent_fmol=q / (F * 1e-15) - math.fsum(z * free),
        )
    for i, row in enumerate(m["extracellular"]):
        amount = c["ao"][:, i] + d["extracellular_amount_increment"][:, i]
        row["initial_amount_fmol"] = dict(zip((s["id"] for s in m["species"]), amount, strict=True))
        row["initial_charge_C"] = c["qo"][i] + F * 1e-15 * math.fsum(
            z * d["extracellular_amount_increment"][:, i]
        )
        # Exterior fixed backgrounds are physical and are not re-expressed.
    for j, row in enumerate(m["channels"]):
        row["initial_gate"] = d["channel_gate"][: len(row["initial_gate"]), j].tolist()
    for j, row in enumerate(m["junctions"]):
        row["gate"]["initial_gate"] = float(d["junction_gate"][j])
    for name in ("store_controls", "plasma_controls", "calcium_channel_controls"):
        raw["experiment"].pop(name, None)
    for name in ("chemical_capacity", "reaction_capacity"):
        raw["execution"].pop(name, None)
    active._retain_clocks(raw, event_times(c["full"]))
    return raw


def snapshot(c, state, time):
    value = _state(c, state)
    d = unpack(c, value)
    _, phi, proof = evaluate(c, value, time)
    ionic = _ionic_now(c, value)
    ic = active.bind(ionic)
    result = active.snapshot(ic, active.initial(ic), time)
    np.testing.assert_allclose(result["potential_V"], phi, atol=3e-12, rtol=2e-11)
    amounts, energies, voltages, er_energy, fixed, live_fixed, moieties = [], [], [], [], [], [], []
    names = c["full"]["model"]["stores"][0]["model"]["moieties"]
    for i, store in enumerate(c["stores"]):
        amount = store.n0 + d["chemical_amount_increment"][i]
        voltage = store.membrane["initial_voltage_V"] + F * 1e-15 / store.cap * math.fsum(
            store.z * d["chemical_amount_increment"][i, :, store.er]
        )
        chemical = (
            1e-3
            * store.rt
            * np.sum(amount * (store.mu0[:, None] + np.log(amount / (store.volume * store.c0)) - 1))
        )
        initial_background = -F * 1e-15 * (store.z @ store.n0)
        initial_background[store.cy] += c["qi"][i] - store.cap * store.membrane["initial_voltage_V"]
        initial_background[store.er] += store.cap * store.membrane["initial_voltage_V"]
        current_background = -F * 1e-15 * (store.z @ amount)
        current_background[store.cy] += result["inside_charge_C"][i] - store.cap * voltage
        current_background[store.er] += store.cap * voltage
        moiety_matrix = np.asarray(
            [[s["moieties"].get(name, 0) for s in store.species] for name in names]
        )
        amounts.append(amount)
        energies.append(float(chemical))
        voltages.append(voltage)
        er_energy.append(0.5e12 * store.cap * voltage * voltage)
        fixed.append(initial_background)
        live_fixed.append(current_background)
        moieties.append(moiety_matrix @ amount)
    er_energy, chemical_inside = np.asarray(er_energy), np.asarray(energies)
    result.update(
        chemical_species_ids=c["stores"][0].ids,
        chemical_compartment_ids=c["stores"][0].owners,
        chemical_amount_fmol=np.stack(amounts),
        moiety_ids=names,
        chemical_moiety_fmol=np.stack(moieties),
        chemical_fixed_charge_C=np.stack(fixed),
        current_chemical_fixed_charge_C=np.stack(live_fixed),
        er_voltage_V=np.asarray(voltages),
        er_energy_pJ=er_energy,
        free_cytosol_amount_fmol=result["inside_amount_fmol"].copy(),
        external_transfer_amount_increment_fmol=d["amount_increment"].copy(),
        chemical_inside_pJ=chemical_inside,
        chemical_energy_pJ=float(chemical_inside.sum() + result["chemical_outside_pJ"].sum()),
        stored_energy_pJ=float(
            chemical_inside.sum()
            + result["chemical_outside_pJ"].sum()
            + result["capacitor_energy_pJ"]
            + er_energy.sum()
        ),
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
        raise ValueError("Cut requires an accepted absolute time within the current epoch")
    if time_s != round(time_s / raw["execution"]["dt"]) * raw["execution"][
        "dt"
    ] and time_s not in event_times(raw):
        raise ValueError("Cut must lie on the original nominal grid or an absolute control event")
    if type(removed_cell_ids) not in (list, tuple) or any(
        type(v) is not str for v in removed_cell_ids
    ):
        raise ValueError("Removal must be a list or tuple of owned cell IDs")
    value = _state(c, state)
    before = snapshot(c, value, time_s)
    names, removed = before["cell_ids"], list(removed_cell_ids)
    if len(set(removed)) != len(removed) or not set(removed) <= set(names):
        raise ValueError("Require distinct currently owned cell IDs")
    archive = dict(
        definition=deepcopy(raw),
        checkpoint=dict(
            time=float(time_s),
            step_index=step_index,
            event_index=event_index,
            state=active._json_values(
                deepcopy(state) if isinstance(state, dict) else unpack(c, value)
            ),
            layout=active._json_values(
                deepcopy(c["layout"] if source_layout is None else source_layout)
            ),
        ),
    )
    indices = [names.index(name) for name in removed]
    keep = [i for i, name in enumerate(names) if name not in removed]
    ionic = _ionic_now(c, value)
    ic = active.bind(ionic)
    try:
        result = active.excise(
            ionic,
            active.initial(ic),
            removed,
            time_s,
            step_index=step_index,
            event_index=event_index,
        )
    except ExcisionError as error:
        audit = dict(
            error.audit,
            before=before,
            source_state_fields=34,
            reason="Closed retained field is incompatible; no ionic or chemical neutralization",
        )
        raise ExcisionError(str(error), archive, audit) from error
    result["archive"] = archive
    audit = result["audit"]
    audit.update(
        before=before,
        source_state_fields=34,
        preserved_gate_fields=list(GATES),
        free_cytosol_charge_anchor=True,
        physical_chemical_backgrounds_conserved=True,
        gate_energy_store=False,
        finite_atp_store=False,
        mechanical_work_model=False,
    )
    if not removed:
        result.update(raw=deepcopy(raw), context=c, state=value)
        audit["after"] = before
        return result
    removed_chemical = float(before["chemical_inside_pJ"][indices].sum())
    removed_er = float(before["er_energy_pJ"][indices].sum())
    audit.update(
        removed_chemical_amount_fmol=before["chemical_amount_fmol"][indices].sum(axis=0),
        removed_moiety_fmol=before["chemical_moiety_fmol"][indices].sum(axis=(0, 2)),
        removed_physical_chemical_fixed_charge_C=before["chemical_fixed_charge_C"][indices].sum(
            axis=0
        ),
        removed_chemical_energy_pJ=removed_chemical,
        removed_er_capacitor_energy_pJ=removed_er,
    )
    if not keep:
        return result
    after = physical_definition(raw)
    m, e = after["model"], after["experiment"]
    m["ionic"] = result["raw"]["model"]
    # The independent ionic remap uses free inventories with the conserved
    # whole-cell Q anchor, so no bound/ER calcium is assigned to a free pool.
    d = unpack(c, value)
    m["stores"] = []
    for i in keep:
        store = deepcopy(c["full"]["model"]["stores"][i])
        s = c["stores"][i]
        for compartment in store["model"]["compartments"]:
            j = s.owners.index(compartment["id"])
            compartment["initial_amount_fmol"] = dict(
                zip(s.ids, before["chemical_amount_fmol"][i, :, j].tolist(), strict=True)
            )
        store["model"]["membrane"]["initial_voltage_V"] = float(before["er_voltage_V"][i])
        m["stores"].append(store)
    m["ip3_release"] = [v for v in m["ip3_release"] if v["cell_id"] not in removed]
    patches = {p["id"] for p in m["ionic"]["membranes"]}
    m["plasma_transport"]["membranes"] = [
        p for p in m["plasma_transport"]["membranes"] if p["membrane_id"] in patches
    ]
    old_patches = {p["id"]: j for j, p in enumerate(c["raw"]["model"]["membranes"])}
    m["calcium_channels"] = [p for p in m["calcium_channels"] if p["membrane_id"] in patches]
    for p in m["calcium_channels"]:
        p["initial_gate"] = dict(
            zip(
                ("m", "h"),
                d["calcium_gate"][:, old_patches[p["membrane_id"]]].tolist(),
                strict=True,
            )
        )
    for family in active.CONTROL_FAMILIES:
        e[family + "_controls"] = deepcopy(result["raw"]["experiment"][family + "_controls"])
    for family, key, owners in (
        ("store", "cell_id", {names[i] for i in keep}),
        ("plasma", "membrane_id", patches),
        ("calcium_channel", "channel_id", {p["id"] for p in m["calcium_channels"]}),
    ):
        e[family + "_controls"] = [p for p in e[family + "_controls"] if p[key] in owners]
    active._retain_clocks(after, {*event_times(raw), time_s})
    e["observation_times"] = sorted(
        {float(time_s), *(t for t in raw["experiment"]["observation_times"] if t >= time_s)}
    )
    context = bind(after)
    context["origin_time"] = float(time_s)
    local = initial(context)
    post = snapshot(context, local, time_s)
    np.testing.assert_allclose(
        post["chemical_fixed_charge_C"],
        before["chemical_fixed_charge_C"][keep],
        rtol=4e-15,
        atol=5e-23,
    )
    impulse = post["electrode_charge_C"] - before["electrode_charge_C"]
    work = 1e12 * math.fsum(
        p["boundary_potential_V"] * q
        for p, q in zip(m["ionic"]["extracellular"], impulse, strict=True)
    )
    audit.update(
        after=post,
        electrode_charge_impulse_C=impulse,
        maintained_boundary_work_pJ=work,
        chemical_energy_jump_pJ=post["chemical_energy_pJ"] - before["chemical_energy_pJ"],
        capacitor_energy_jump_pJ=post["capacitor_energy_pJ"] - before["capacitor_energy_pJ"],
        er_energy_jump_pJ=float(post["er_energy_pJ"].sum() - before["er_energy_pJ"].sum()),
        unresolved_cut_energy_pJ=(
            post["stored_energy_pJ"]
            - before["stored_energy_pJ"]
            + removed_chemical
            + removed_er
            + audit["removed_owned_capacitor_energy_pJ"]
            - work
        ),
    )
    result.update(raw=after, context=context, state=local)
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
        raise ValueError("Invalid calcium reference interval, step or refinement")
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
            "Independent 34-field DOP853, full-node field roots, scalar chemistry "
            "and seven absolute clocks"
        ),
    )
