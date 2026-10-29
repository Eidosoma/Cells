"""Independent exact53-law water/fuel/calcium cutting and absolute continuation.

Current cytosol/exterior volumes become new initial anchors. The compliance
reference volume, bounds, K, pressure offset, impermeants and Lp remain physical
parameters. ER volume stays fixed. Chemical/fuel mixing is counted once at
current volumes; only impermeant mixing and elastic U are additional stores.
Pool volume work is an internal diagnostic ledger, not external energy supply.

The frozen 38-field cut helper is reused only for instantaneous geometry on its
exact 53-law subset. All dynamical/serialized identities remain water@1 with
ionic@11; this is not a 56-law water model. No Cells/JAX imports.
"""

from copy import deepcopy
from decimal import Decimal, localcontext
from numbers import Real

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import calcium_energy_excision_reference as energy_cut
from validation.tissue import calcium_energy_water_reference as water

MODEL_ID = "resolved_calcium_energy_water_excision@1"
BASE_ID = water.MODEL_ID
STATE_POLICY = "rebase_chemical_fuel_water_owners_preserve_gates_archive_complete_source@1"
REFERENCE_POLICY = (
    "free_cytosol_anchor_with_conserved_whole_cell_charge_and_fixed_compliance_reference@1"
)
CONTROL_FAMILIES = (*energy_cut.CONTROL_FAMILIES, "water")
GATES = energy_cut.GATES
F, R = water.F, water.R
flatten, unpack, initial = water.flatten, water.unpack, water.initial
ExcisionError = energy_cut.ExcisionError
ReferenceIntegrationError = water.ReferenceIntegrationError
active = energy_cut.calcium_cut.active


def physical_definition(raw):
    result = deepcopy(raw)
    if result["model"]["id"] == MODEL_ID:
        result["model"] = deepcopy(result["model"]["tissue"])
    if result["model"]["id"] != BASE_ID or result["model"]["ionic"]["id"] != "resolved_tissue@11":
        raise ValueError("Require exact joint43 water and 53-law ionic identities")
    return result


def _lineage(raw):
    """Immutable water ownership/constitutive data and current-volume anchors."""
    if raw["model"]["id"] != MODEL_ID:
        return
    cut = raw["model"]["excision"]
    if cut["state_policy"] != STATE_POLICY or cut["reference_policy"] != REFERENCE_POLICY:
        raise ValueError("Require explicit current-volume and fixed-compliance cut policies")
    source = physical_definition(cut["source"]["definition"])["model"]
    target = raw["model"]["tissue"]
    removed = set(cut["removed_cell_ids"])
    nodes = {
        p["id"] for p in (*source["ionic"]["cells"], *source["ionic"]["extracellular"])
    } - removed
    patches = {p["id"] for p in source["ionic"]["membranes"] if p["inside"] not in removed}
    for key, owner, keep in (
        ("water_compartments", "compartment_id", nodes),
        ("water_membranes", "membrane_id", patches),
    ):
        expected = {p[owner]: p for p in source[key] if p[owner] in keep}
        actual = {p[owner]: p for p in target[key]}
        if len(actual) != len(target[key]) or actual != expected:
            raise ValueError("A cut cannot alter or lose retained physical water declarations")
    state = cut["source"]["checkpoint"]["state"]
    for group, field in (
        ("cells", "volume_increment_pL"),
        ("extracellular", "extracellular_volume_increment_pL"),
    ):
        expected = {
            p["id"]: p["volume_pL"] + state[field][i]
            for i, p in enumerate(source["ionic"][group])
            if p["id"] not in removed
        }
        actual = {p["id"]: p["volume_pL"] for p in target["ionic"][group]}
        if actual != expected:
            raise ValueError("Current owned water volumes must be retained exactly")


def bind(raw):
    _lineage(raw)
    start = (
        raw["model"]["excision"]["source"]["checkpoint"]["time"]
        if raw["model"]["id"] == MODEL_ID
        else 0.0
    )
    ordinary = energy_cut.calcium_cut._ordered(physical_definition(raw))
    c = water.bind(ordinary)
    for i, store in enumerate(c["stores"]):
        for j, species in enumerate(c["energy"]["raw"]["model"]["ionic"]["species"]):
            if store.n0[store.ids.index(species["id"]), store.cy] != c["ai"][j, i]:
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
            raise ValueError("Water cut archives require all forty-three named fields")
        value = flatten(c, state)
    else:
        value = np.asarray(state)
    if value.shape != initial(c).shape or not np.isfinite(value).all():
        raise ValueError("Require a complete finite forty-three-field state")
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
        return water.evaluate(c, value, time)
    except (AssertionError, np.linalg.LinAlgError) as error:
        raise ValueError("Water/calcium field or charge/current rates incompatible") from error


def _energy_view(c, state):
    """Exact current-volume energy equations, plus a geometry-only catalog view."""
    current = water.current_energy_context(c, unpack(c, state))
    raw = deepcopy(current["raw"])
    assert raw["model"]["id"] == "resolved_calcium_energy@4"
    assert raw["model"]["ionic"]["id"] == "resolved_tissue@11"
    raw["model"]["id"], raw["model"]["ionic"]["id"] = energy_cut.BASE_ID, "resolved_tissue@12"
    active._retain_clocks(raw, event_times(c["raw"]))
    context = energy_cut.bind(raw)
    return raw, context, flatten(context, unpack(c, state))


def snapshot(c, state, time):
    value = _state(c, state)
    d = unpack(c, value)
    _, phi, proof = evaluate(c, value, time)
    _, prior, physical = _energy_view(c, value)
    result = energy_cut.snapshot(prior, physical, time)
    np.testing.assert_allclose(result["potential_V"], phi, rtol=2e-11, atol=3e-12)
    volume, case = water.volumes(c, d), c["water_case"]
    flow = water.water.evaluate(case, volume, water.particles(c, d))
    impermeant, elastic = [], []
    with localcontext() as precision:
        precision.prec = 80
        dec = lambda v: Decimal(str(float(v)))  # noqa: E731
        rt = dec(R) * dec(c["temperature"])
        for i, vi in enumerate(volume):
            v, vr = dec(vi), dec(case["reference_volume_pL"][i])
            n = dec(case["impermeant_amount_fmol"][i])
            impermeant.append(float(Decimal(".001") * rt * n * ((n / v).ln() - 1)) if n else 0.0)
            elastic.append(
                float(
                    Decimal(".001")
                    * (
                        dec(case["bulk_modulus_Pa"][i]) * (v - vr) ** 2 / (2 * vr)
                        + dec(case["pressure_offset_Pa"][i]) * (v - vr)
                    )
                )
            )
    impermeant, elastic = np.asarray(impermeant), np.asarray(elastic)
    n = len(c["cell_ids"])
    result.update(
        water_node_ids=[
            p["id"]
            for p in (
                *c["raw"]["model"]["ionic"]["cells"],
                *c["raw"]["model"]["ionic"]["extracellular"],
            )
        ],
        water_volume_pL=volume,
        inside_volume_pL=volume[:n],
        outside_volume_pL=volume[n:],
        er_volume_pL=np.array([s.volume[s.er] for s in c["stores"]]),
        water_initial_volume_pL=np.r_[c["vi"], c["vo"]],
        water_reference_volume_pL=case["reference_volume_pL"].copy(),
        water_impermeant_amount_fmol=case["impermeant_amount_fmol"].copy(),
        impermeant_mixing_energy_pJ=impermeant,
        compliance_energy_pJ=elastic,
        hydrostatic_pressure_Pa=flow["hydrostatic_pressure_Pa"],
        osmotic_pressure_Pa=flow["osmotic_pressure_Pa"],
        water_potential_Pa=flow["water_potential_Pa"],
        water_histories={k: d[k].copy() for k in water.EXTRA_FIELDS},
        stored_energy_pJ=result["stored_energy_pJ"] + float((impermeant + elastic).sum()),
        field_proof=proof,
    )
    return result


def _fuel_rebase_domain(raw):
    m = raw["model"]
    cells = {p["id"]: p for p in m["ionic"]["cells"]}
    patches = {p["id"]: p["inside"] for p in m["ionic"]["membranes"]}
    owners = {p["cell_id"] for p in m["stores"] if p["model"]["membrane"]["pump"] is not None}
    owners.update(
        patches[p["membrane_id"]]
        for p in m["plasma_transport"]["membranes"]
        if p["pump"] is not None
    )
    for pool in m["energy_pools"]:
        concentration = (
            np.array(list(pool["initial_amount_fmol"].values()))
            / cells[pool["cell_id"]]["volume_pL"]
        )
        if pool["cell_id"] in owners and (
            np.any(concentration < 1e-9) or np.any(concentration > 1e3)
        ):
            raise ValueError(
                "Surviving finite PMCA/ER rebase requires current-volume fuel in [1e-9,1e3] mM"
            )


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
        raise ValueError("Cut requires an accepted absolute time in the current water epoch")
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
    prior_raw, _, physical = _energy_view(c, value)
    try:
        result = energy_cut.excise(
            prior_raw, physical, removed, time_s, step_index=step_index, event_index=event_index
        )
    except ExcisionError as error:
        raise ExcisionError(
            str(error), archive, dict(error.audit, before=before, source_state_fields=43)
        ) from error
    result["archive"] = archive
    audit = result["audit"]
    audit.update(
        before=before,
        source_state_fields=43,
        reference_policy=REFERENCE_POLICY,
        compliance_reference_preserved=True,
        pool_volume_work_internal=True,
        impermeant_charge_model="neutral_ideal_additional_osmolytes@1",
    )
    if not removed:
        result.update(raw=deepcopy(raw), context=c, state=value)
        audit["after"] = before
        return result
    indices = [i for i, name in enumerate(c["cell_ids"]) if name in removed]
    keep = [i for i, name in enumerate(c["cell_ids"]) if name not in removed]
    patches = c["raw"]["model"]["ionic"]["membranes"]
    rpatch = [j for j, p in enumerate(patches) if p["inside"] in removed]
    kpatch = [j for j, p in enumerate(patches) if p["inside"] not in removed]
    audit.update(
        removed_water_volume_pL=float(before["inside_volume_pL"][indices].sum()),
        removed_fixed_er_volume_pL=float(before["er_volume_pL"][indices].sum()),
        removed_impermeant_amount_fmol=float(before["water_impermeant_amount_fmol"][indices].sum()),
        removed_impermeant_mixing_energy_pJ=float(
            before["impermeant_mixing_energy_pJ"][indices].sum()
        ),
        removed_compliance_energy_pJ=float(before["compliance_energy_pJ"][indices].sum()),
        removed_water_membrane_ids=[patches[j]["id"] for j in rpatch],
        archived_removed_water_transferred_pL=d["water_transferred_pL"][rpatch].copy(),
        archived_removed_water_dissipated_energy_pJ=d["water_dissipated_energy_pJ"][rpatch].copy(),
        archived_removed_volume_increment_pL=d["volume_increment_pL"][indices].copy(),
        archived_removed_pool_volume_work_pJ=d["pool_volume_work_pJ"][indices].copy(),
        archived_retained_water_transferred_pL=d["water_transferred_pL"][kpatch].copy(),
        archived_retained_water_dissipated_energy_pJ=d["water_dissipated_energy_pJ"][kpatch].copy(),
        archived_retained_extracellular_volume_increment_pL=d[
            "extracellular_volume_increment_pL"
        ].copy(),
    )
    if not keep:
        return result
    after = deepcopy(result["raw"])
    m = after["model"]
    m["id"], m["ionic"]["id"] = BASE_ID, "resolved_tissue@11"
    for key in ("chemical_osmotic_coupling", "energy_osmotic_coupling"):
        m[key] = c["raw"]["model"][key]
    m["water_compartments"] = [
        deepcopy(p)
        for p in c["raw"]["model"]["water_compartments"]
        if p["compartment_id"] not in removed
    ]
    retained = {p["id"] for p in m["ionic"]["membranes"]}
    m["water_membranes"] = [
        deepcopy(p) for p in c["raw"]["model"]["water_membranes"] if p["membrane_id"] in retained
    ]
    after["experiment"]["water_controls"] = [
        deepcopy(p) for p in raw["experiment"]["water_controls"] if p["membrane_id"] in retained
    ]
    active._retain_clocks(after, {*event_times(raw), time_s})
    _fuel_rebase_domain(after)
    current = bind(after)
    current["origin_time"] = float(time_s)
    local = initial(current)
    post = snapshot(current, local, time_s)
    nodes = [*keep, *range(len(c["cell_ids"]), len(before["water_volume_pL"]))]
    for key in (
        "water_volume_pL",
        "water_reference_volume_pL",
        "water_impermeant_amount_fmol",
        "impermeant_mixing_energy_pJ",
        "compliance_energy_pJ",
    ):
        np.testing.assert_array_equal(post[key], before[key][nodes])
    np.testing.assert_array_equal(post["er_volume_pL"], before["er_volume_pL"][keep])
    audit.update(
        after=post,
        water_volume_jump_pL=float(post["water_volume_pL"].sum() - before["water_volume_pL"].sum()),
        impermeant_energy_jump_pJ=float(
            post["impermeant_mixing_energy_pJ"].sum() - before["impermeant_mixing_energy_pJ"].sum()
        ),
        compliance_energy_jump_pJ=float(
            post["compliance_energy_pJ"].sum() - before["compliance_energy_pJ"].sum()
        ),
        unresolved_cut_energy_pJ=(
            post["stored_energy_pJ"]
            - before["stored_energy_pJ"]
            + audit["removed_chemical_energy_pJ"]
            + audit["removed_er_capacitor_energy_pJ"]
            + audit["removed_owned_capacitor_energy_pJ"]
            + audit["removed_fuel_free_energy_pJ"]
            + audit["removed_impermeant_mixing_energy_pJ"]
            + audit["removed_compliance_energy_pJ"]
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
        raise ValueError("Invalid calcium energy water cut reference interval, step or refinement")
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
            "Independent 43-field DOP853, full-node field roots, scalar chemistry "
            "and nine absolute clocks"
        ),
    )
