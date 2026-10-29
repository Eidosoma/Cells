"""Independent mitochondrial cutting with explicit countercharge rebasing.

Let q=F*1e-15, Bp=Qplasma-Cer*Ver-q*sum(z*ncy), and Qm=Cm*Vm.
Bp is the parent chemical reference coordinate. Internal mitochondrial exchange
gives Bp(t)=Bp(0)+q*sum(z*delta_nm). The physical cytosolic fixed background is
Bp(t)-Qm(t)=Bp(0)-Cm*Vm0. Rebase BOTH the parent coordinate and its paired
countercharge; mitochondrial Cm*Vm-q*sum(z*nm) also remains fixed. No charge,
material, respiration, ATP synthesis or mechanical cut work is invented.

All dynamical laws come from the independent continuous45 reference. The
ordinary cut reference handles the instantaneous retained geometry after we
independently anchor actual inventories, fields and gates. No Cells/JAX imports.
"""

import math
from copy import deepcopy
from numbers import Real

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import calcium_energy_mitochondria_reference as mitochondria
from validation.tissue import calcium_energy_transport_excision_reference as network_cut

MODEL_ID = "resolved_calcium_energy_mitochondria_excision@1"
BASE_ID = mitochondria.MODEL_ID
REFERENCE_POLICY = (
    "free_cytosol_anchor_with_conserved_whole_cell_charge_and_organelle_countercharge@1"
)
CONTROL_FAMILIES = (*network_cut.CONTROL_FAMILIES, "mitochondria")
GATES = network_cut.GATES
F, R = mitochondria.F, mitochondria.R
flatten, unpack, initial = mitochondria.flatten, mitochondria.unpack, mitochondria.initial
ExcisionError = network_cut.ExcisionError
ReferenceIntegrationError = network_cut.ReferenceIntegrationError
calcium_cut = network_cut.energy_cut.calcium_cut
active = calcium_cut.active


def physical_definition(raw):
    result = deepcopy(raw)
    if result["model"]["id"] == MODEL_ID:
        result["model"] = deepcopy(result["model"]["tissue"])
    if result["model"]["id"] != BASE_ID or result["model"]["ionic"]["id"] != "resolved_tissue@12":
        raise ValueError("Require exact continuous45 mitochondrial and 56-law ionic identities")
    return result


def bind(raw):
    start = (
        raw["model"]["excision"]["source"]["checkpoint"]["time"]
        if raw["model"]["id"] == MODEL_ID
        else 0.0
    )
    c = mitochondria.bind(calcium_cut._ordered(physical_definition(raw)))
    for i, store in enumerate(c["stores"]):
        for j, species in enumerate(c["network_species"]):
            if store.n0[store.ids.index(species), store.cy] != c["ai"][j, i]:
                raise ValueError("The ionic initial anchor must equal actual free cytosol")
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
            raise ValueError("Mitochondrial cut archives require all forty-five named fields")
        value = flatten(c, state)
    else:
        value = np.asarray(state)
    if value.shape != initial(c).shape or not np.isfinite(value).all():
        raise ValueError("Require a complete finite forty-five-field state")
    return value.copy()


def evaluate(c, state, time):
    value = _state(c, state)
    d = unpack(c, value)
    supported = np.array(
        [
            [row["diffusivity_m2_per_s"][s] > 0 for row in c["mitochondrial_rows"]]
            for s in c["network_species"]
        ]
    )
    for name in mitochondria.EXTRA_FIELDS:
        if np.any(d[name][~supported] != 0):
            raise ValueError("Permanently absent mitochondrial routes require zero histories")
    if np.any(d["calcium_gate"] < 0) or np.any(d["calcium_gate"] > 1):
        raise ValueError("Dedicated calcium gates must stay in [0,1]")
    minimum = np.asarray(
        [p["gate"]["minimum_open_fraction"] for p in c["raw"]["model"]["ionic"]["junctions"]]
    )
    if np.any(d["junction_gate"] < minimum) or np.any(d["junction_gate"] > 1):
        raise ValueError("Intrinsic junction gates lie outside their declared domain")
    try:
        return mitochondria.evaluate(c, value, time)
    except (AssertionError, np.linalg.LinAlgError) as error:
        raise ValueError(
            "Mitochondrial/calcium field or charge/current rates incompatible"
        ) from error


def _network_view(c, state):
    raw = deepcopy(c["raw"])
    raw["model"]["id"] = network_cut.BASE_ID
    raw["model"].pop("mitochondria")
    raw["experiment"].pop("mitochondria_controls")
    active._retain_clocks(raw, event_times(c["raw"]))
    current = network_cut.bind(raw)
    return raw, current, flatten(current, unpack(c, state))


def snapshot(c, state, time):
    value = _state(c, state)
    d = unpack(c, value)
    _, phi, proof = evaluate(c, value, time)
    _, prior, physical = _network_view(c, value)
    result = network_cut.snapshot(prior, physical, time)
    np.testing.assert_allclose(result["potential_V"], phi, rtol=2e-11, atol=3e-12)
    amount = c["mitochondrial_initial"] + d["mitochondrial_amount_increment_fmol"]
    voltage = mitochondria.mitochondrial_voltage(c, d)
    cap, valence = c["mitochondrial_capacitance"], c["mitochondrial_valence"]
    charge = cap * voltage
    fixed = charge - F * 1e-15 * np.sum(valence[:, None] * amount, axis=0)
    reference = result["chemical_fixed_charge_C"].copy()
    live_reference = result["current_chemical_fixed_charge_C"].copy()
    background, live_background = reference.copy(), live_reference.copy()
    for i, store in enumerate(c["stores"]):
        background[i, store.cy] -= cap[i] * c["mitochondrial_initial_voltage"][i]
        live_background[i, store.cy] -= charge[i]
    chemical = (
        1e-3
        * R
        * c["temperature"]
        * np.sum(amount * (np.log(amount / c["mitochondrial_volume"]) - 1), axis=0)
    )
    capacitor = 0.5e12 * cap * voltage * voltage
    moieties = np.zeros((len(result["moiety_ids"]), len(c["cell_ids"])))
    for j, name in enumerate(c["network_species"]):
        moieties[result["moiety_ids"].index(name)] += amount[j]
    np.testing.assert_allclose(background, live_background, rtol=4e-15, atol=5e-23)
    np.testing.assert_allclose(fixed, c["mitochondrial_fixed_charge_C"], rtol=4e-15, atol=5e-23)
    result.update(
        chemical_reference_background_C=reference,
        current_chemical_reference_background_C=live_reference,
        chemical_fixed_charge_C=background,
        current_chemical_fixed_charge_C=live_background,
        mitochondrial_ids=[p["id"] for p in c["mitochondrial_rows"]],
        mitochondrial_amount_fmol=amount,
        mitochondrial_moiety_fmol=moieties,
        mitochondrial_voltage_V=voltage,
        mitochondrial_charge_C=charge,
        mitochondrial_countercharge_C=-charge,
        mitochondrial_initial_countercharge_C=c["mitochondrial_initial_cytosol_countercharge_C"],
        mitochondrial_fixed_charge_C=c["mitochondrial_fixed_charge_C"].copy(),
        current_mitochondrial_fixed_charge_C=fixed,
        mitochondrial_chemical_energy_pJ=chemical,
        mitochondrial_capacitor_energy_pJ=capacitor,
        mitochondrial_histories={k: d[k].copy() for k in mitochondria.EXTRA_FIELDS},
        stored_energy_pJ=result["stored_energy_pJ"] + float((chemical + capacitor).sum()),
        field_proof=proof,
    )
    return result


def _instant_network(c, state):
    """Re-express actual owners without reusing a fixed-background invariant.

    This is an instantaneous cut geometry, not a dynamical state projection:
    the full original 45-field source remains in the separate archive.
    """
    d = unpack(c, state)
    raw, _, _ = _network_view(c, state)
    m, ion = raw["model"], raw["model"]["ionic"]
    z = c["mitochondrial_valence"]
    for i, row in enumerate(ion["cells"]):
        store = c["stores"][i]
        amount = store.n0 + d["chemical_amount_increment"][i]
        free = [amount[store.ids.index(s), store.cy] for s in c["network_species"]]
        charge = c["qi"][i] + F * 1e-15 * math.fsum(z * d["amount_increment"][:, i])
        row.update(
            initial_amount_fmol=dict(zip(c["network_species"], free, strict=True)),
            initial_charge_C=charge,
            fixed_charge_equivalent_fmol=charge / (F * 1e-15) - math.fsum(z * free),
        )
        owner = next(p["model"] for p in m["stores"] if p["cell_id"] == row["id"])
        for compartment in owner["compartments"]:
            j = store.owners.index(compartment["id"])
            compartment["initial_amount_fmol"] = dict(zip(store.ids, amount[:, j], strict=True))
        owner["membrane"]["initial_voltage_V"] = store.membrane[
            "initial_voltage_V"
        ] + F * 1e-15 / store.cap * math.fsum(
            store.z * d["chemical_amount_increment"][i, :, store.er]
        )
    for i, row in enumerate(ion["extracellular"]):
        amount = c["ao"][:, i] + d["extracellular_amount_increment"][:, i]
        row["initial_amount_fmol"] = dict(zip(c["network_species"], amount, strict=True))
        row["initial_charge_C"] = c["qo"][i] + F * 1e-15 * math.fsum(
            z * d["extracellular_amount_increment"][:, i]
        )
    for j, row in enumerate(ion["channels"]):
        row["initial_gate"] = d["channel_gate"][: len(row["initial_gate"]), j].tolist()
    for j, row in enumerate(ion["junctions"]):
        row["gate"]["initial_gate"] = float(d["junction_gate"][j])
    patch = {p["id"]: j for j, p in enumerate(ion["membranes"])}
    for row in m["calcium_channels"]:
        row["initial_gate"] = dict(
            zip(("m", "h"), d["calcium_gate"][:, patch[row["membrane_id"]]], strict=True)
        )
    for pool in m["energy_pools"]:
        i = c["cell_ids"].index(pool["cell_id"])
        amount = c["energy_initial"][:, i] + d["energy_amount_increment_fmol"][:, i]
        pool["initial_amount_fmol"] = dict(zip(("ATP", "ADP", "Pi"), amount, strict=True))
    current = network_cut.bind(raw)
    return raw, current, network_cut.initial(current)


def _fuel_rebase_domain(raw):
    """Keep the inherited surviving PMCA/ER constructor range unchanged."""
    m = raw["model"]
    cells = {p["id"]: p for p in m["ionic"]["cells"]}
    for pool in m["energy_pools"]:
        concentration = (
            np.array(list(pool["initial_amount_fmol"].values()))
            / cells[pool["cell_id"]]["volume_pL"]
        )
        if np.any(concentration < 1e-9) or np.any(concentration > 1e3):
            raise ValueError("Surviving finite PMCA/ER rebase requires fuel in [1e-9,1e3] mM")


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
        raise ValueError(
            "Cut requires an accepted absolute time in the current mitochondrial epoch"
        )
    if type(removed_cell_ids) not in (list, tuple) or any(
        type(v) is not str for v in removed_cell_ids
    ):
        raise ValueError("Removal must be a list or tuple of owned cell IDs")
    removed = list(removed_cell_ids)
    if len(set(removed)) != len(removed) or not set(removed) <= set(c["cell_ids"]):
        raise ValueError("Require distinct currently owned cell IDs")
    value = _state(c, state)
    d = unpack(c, value)
    before = snapshot(c, value, time_s)
    archive = dict(
        definition=deepcopy(raw),
        checkpoint=dict(
            time=float(time_s),
            step_index=step_index,
            event_index=event_index,
            state=active._json_values(deepcopy(state) if isinstance(state, dict) else d),
            layout=active._json_values(
                deepcopy(c["layout"] if source_layout is None else source_layout)
            ),
        ),
    )
    prior_raw, _, physical = _instant_network(c, value)
    try:
        result = network_cut.excise(
            prior_raw, physical, removed, time_s, step_index=step_index, event_index=event_index
        )
    except ExcisionError as error:
        raise ExcisionError(
            str(error), archive, dict(error.audit, before=before, source_state_fields=45)
        ) from error
    result["archive"] = archive
    audit = result["audit"]
    audit.update(
        before=before,
        source_state_fields=45,
        reference_policy=REFERENCE_POLICY,
        physical_chemical_backgrounds_conserved=True,
        mitochondrial_fixed_charge_conserved=True,
        mitochondrial_direct_plasma_charge=False,
        mitochondrial_atp_source=False,
    )
    if not removed:
        result.update(raw=deepcopy(raw), context=c, state=value)
        audit["after"] = before
        return result
    indices = [i for i, name in enumerate(c["cell_ids"]) if name in removed]
    keep = [i for i, name in enumerate(c["cell_ids"]) if name not in removed]
    remove_routes = [j for j, (i, _) in enumerate(c["network_owners"]) if i in indices]
    keep_routes = [j for j, (i, _) in enumerate(c["network_owners"]) if i in keep]
    audit.update(
        archived_removed_network_state={
            k: np.take(d[k], remove_routes, axis=-1) for k in network_cut.network.EXTRA_FIELDS
        },
        archived_retained_network_state={
            k: np.take(d[k], keep_routes, axis=-1) for k in network_cut.network.EXTRA_FIELDS
        },
        archived_removed_mitochondrial_state={
            k: d[k][:, indices].copy() for k in mitochondria.EXTRA_FIELDS
        },
        archived_retained_mitochondrial_state={
            k: d[k][:, keep].copy() for k in mitochondria.EXTRA_FIELDS
        },
        removed_mitochondrial_ids=[before["mitochondrial_ids"][i] for i in indices],
        removed_mitochondrial_amount_fmol=before["mitochondrial_amount_fmol"][:, indices].sum(
            axis=1
        ),
        removed_mitochondrial_moiety_fmol=before["mitochondrial_moiety_fmol"][:, indices].sum(
            axis=1
        ),
        removed_mitochondrial_fixed_charge_C=float(
            before["mitochondrial_fixed_charge_C"][indices].sum()
        ),
        removed_mitochondrial_chemical_energy_pJ=float(
            before["mitochondrial_chemical_energy_pJ"][indices].sum()
        ),
        removed_mitochondrial_capacitor_energy_pJ=float(
            before["mitochondrial_capacitor_energy_pJ"][indices].sum()
        ),
        removed_physical_chemical_fixed_charge_C=before["chemical_fixed_charge_C"][indices].sum(
            axis=0
        ),
    )
    if not keep:
        return result
    after = deepcopy(result["raw"])
    m = after["model"]
    m["id"] = BASE_ID
    m["mitochondria"] = deepcopy(c["raw"]["model"]["mitochondria"])
    m["mitochondria"]["compartments"] = []
    for i in keep:
        row = deepcopy(c["mitochondrial_rows"][i])
        row.update(
            initial_voltage_V=float(before["mitochondrial_voltage_V"][i]),
            initial_amount_fmol=dict(
                zip(c["network_species"], before["mitochondrial_amount_fmol"][:, i], strict=True)
            ),
        )
        m["mitochondria"]["compartments"].append(row)
    after["experiment"]["mitochondria_controls"] = [
        deepcopy(p)
        for p in raw["experiment"]["mitochondria_controls"]
        if p["mitochondrion_id"] not in audit["removed_mitochondrial_ids"]
    ]
    active._retain_clocks(after, {*event_times(raw), time_s})
    _fuel_rebase_domain(after)
    current = bind(after)
    current["origin_time"] = float(time_s)
    local = initial(current)
    post = snapshot(current, local, time_s)
    np.testing.assert_array_equal(post["inside_charge_C"], before["inside_charge_C"][keep])
    np.testing.assert_array_equal(
        post["mitochondrial_amount_fmol"], before["mitochondrial_amount_fmol"][:, keep]
    )
    np.testing.assert_array_equal(
        post["mitochondrial_voltage_V"], before["mitochondrial_voltage_V"][keep]
    )
    for key in ("chemical_fixed_charge_C", "mitochondrial_fixed_charge_C"):
        np.testing.assert_allclose(post[key], before[key][keep], rtol=4e-15, atol=5e-23)
    audit.update(
        after=post,
        chemical_reference_coordinate_shift_C=post["chemical_reference_background_C"]
        - before["chemical_reference_background_C"][keep],
        mitochondrial_energy_jump_pJ=float(
            (
                post["mitochondrial_chemical_energy_pJ"] + post["mitochondrial_capacitor_energy_pJ"]
            ).sum()
            - (
                before["mitochondrial_chemical_energy_pJ"]
                + before["mitochondrial_capacitor_energy_pJ"]
            ).sum()
        ),
        unresolved_cut_energy_pJ=(
            post["stored_energy_pJ"]
            - before["stored_energy_pJ"]
            + audit["removed_chemical_energy_pJ"]
            + audit["removed_er_capacitor_energy_pJ"]
            + audit["removed_owned_capacitor_energy_pJ"]
            + audit["removed_fuel_free_energy_pJ"]
            + audit["removed_mitochondrial_chemical_energy_pJ"]
            + audit["removed_mitochondrial_capacitor_energy_pJ"]
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
        raise ValueError("Invalid mitochondrial cut reference interval, step or refinement")
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
            "Independent 45-field DOP853, full-node field roots, scalar chemistry "
            "and ten absolute clocks"
        ),
    )
