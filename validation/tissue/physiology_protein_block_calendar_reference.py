"""Independent native blockers, actual protein tapes and complete charged ODEs.

Only raw definitions, original named bindings/calendars and initial states enter
this reference. Both tolerance settings carry their own full histories. The
qualified charged/RNG reference supplies physics; blocker memory and every
left/right control are reconstructed here without production controls/layouts.
"""

from copy import deepcopy

import numpy as np

from validation.perturbations import physiology_calendar_reference as clocks
from validation.tissue import physiology_block_control_reference as blockers
from validation.tissue import physiology_protein_batch_loop_reference as charged
from validation.tissue.physiology_tissue_step_reference import grid


def baseline(raw, time):
    """Select original right-continuous named schedules, including padding."""
    model = raw["model"].get("ionic", raw["model"])
    experiment, execution = raw["experiment"], raw["execution"]

    def selected(family, key, owner):
        row = next(row for row in experiment[family] if row[key] == owner)
        return next(
            value
            for value in reversed(row.get("schedule", row.get("controls", [])))
            if value["time"] <= time
        )

    def vector(capacity, rows, family, owner_key, value_key="availability"):
        values = np.zeros(capacity, np.float64)
        for index, owner in rows:
            values[index] = selected(family, owner_key, owner)[value_key]
        return values

    result = {}
    for kind, capacity in (("membrane", "membrane_capacity"), ("junction", "edge_capacity")):
        result[kind] = vector(
            execution[capacity],
            enumerate(row["id"] for row in model[kind + "s"]),
            kind + "_controls",
            kind + "_id",
        )
    if "channels" in model:
        result["channel"] = vector(
            execution["channel_capacity"],
            enumerate(row["id"] for row in model["channels"]),
            "channel_controls",
            "channel_id",
        )
        result["pump"] = vector(
            execution["membrane_capacity"],
            ((i, row["pump"]["id"]) for i, row in enumerate(model["membranes"]) if row.get("pump")),
            "pump_controls",
            "pump_id",
        )
    if "stores" in raw["model"]:
        stores = {row["cell_id"]: row["model"] for row in raw["model"]["stores"]}
        rows = [selected("store_controls", "cell_id", row["id"]) for row in model["cells"]]
        for field, members, capacity in (
            ("reactions", "reactions", execution["reaction_capacity"]),
            ("passive", "species", len(next(iter(stores.values()))["species"])),
        ):
            values = np.zeros((len(rows), capacity), np.float64)
            for i, cell in enumerate(model["cells"]):
                for j, owner in enumerate(stores[cell["id"]][members]):
                    values[i, j] = rows[i][field][owner["id"]]
            result["er_" + field] = values
        for field in ("pump", "release"):
            result["er_" + field] = np.asarray([row[field] for row in rows], np.float64)
        for field, value in (("plasma_pump", "pump"), ("plasma_exchange", "exchanger")):
            result[field] = vector(
                execution["membrane_capacity"],
                enumerate(row["id"] for row in model["membranes"]),
                "plasma_controls",
                "membrane_id",
                value,
            )
        membranes = [row["id"] for row in model["membranes"]]
        result["calcium_channel"] = vector(
            execution["membrane_capacity"],
            (
                (membranes.index(row["membrane_id"]), row["id"])
                for row in raw["model"]["calcium_channels"]
            ),
            "calcium_channel_controls",
            "channel_id",
        )
    if "regeneration_ports" in raw["model"]:
        result["regeneration"] = vector(
            execution["regeneration_capacity"],
            enumerate(row["id"] for row in raw["model"]["regeneration_ports"]),
            "regeneration_controls",
            "regeneration_id",
        )
    return result


def prepare_history(raw, block_binding, block_state, calendar, budgets, *, start_call=0):
    """Derive physical intervals and setter memory from the original full clock."""
    stop = start_call + len(budgets)
    if (
        type(start_call) is not int
        or not budgets
        or not 0 <= start_call < stop <= calendar["step_count"]
        or calendar["phase"] not in ("INIT", "SIM")
    ):
        raise ValueError("Require complete bounded original-calendar charged calls")
    points, dt = grid(raw), calendar["dt_s"]
    carried, loops, metadata = deepcopy(block_state), [], []
    for index, budget in enumerate(budgets, start_call):
        start, end, label = index * dt, (index + 1) * dt, clocks.event_label(calendar, index)
        if start not in points or end not in points:
            raise ValueError("Native charged call must use exact original physical boundaries")
        carried, staged_control = blockers.prepare(
            raw,
            block_binding["program"],
            block_binding["junction_membranes"],
            carried,
            baseline(raw, start),
            label,
            calendar["phase"] == "SIM",
        )
        rows, controls = [], []
        for left, right in zip(
            points[points.index(start) : points.index(end)],
            points[points.index(start) + 1 : points.index(end) + 1],
            strict=True,
        ):
            base_left, base_right = baseline(raw, left), baseline(raw, right)
            _, effective_left = blockers.prepare(
                raw,
                block_binding["program"],
                block_binding["junction_membranes"],
                carried,
                base_left,
                left,
                False,
            )
            _, effective_right = blockers.prepare(
                raw,
                block_binding["program"],
                block_binding["junction_membranes"],
                carried,
                base_right,
                right,
                False,
            )
            rows.append(
                dict(
                    duration_s=right - left,
                    held_control=effective_left,
                    endpoint_control=effective_right,
                )
            )
            controls.append(
                dict(
                    start_s=left,
                    end_s=right,
                    base_left=base_left,
                    base_right=base_right,
                    actual_left=effective_left,
                    actual_right=effective_right,
                )
            )
        loops.append(dict(loop_index=index, intervals=rows, budget=budget))
        metadata.append(
            dict(
                call_index=index,
                event_label_s=label,
                physical_start_s=start,
                physical_end_s=end,
                block_state=deepcopy(carried),
                staged_control=staged_control,
                interval_controls=controls,
            )
        )
    return loops, metadata


def integrate(
    raw,
    fields,
    binding,
    source_component,
    charge_reference,
    block_binding,
    block_state,
    calendar,
    budgets,
    *,
    valence,
    standard_concentration_mol_m3,
    threefry_partitionable,
    padded_outside_capacity,
    start_call=0,
    refinement=1,
    schedule=None,
):
    loops, metadata = prepare_history(
        raw, block_binding, block_state, calendar, budgets, start_call=start_call
    )
    answer = charged.integrate(
        raw,
        fields,
        binding,
        source_component,
        charge_reference,
        loops,
        valence=valence,
        standard_concentration_mol_m3=standard_concentration_mol_m3,
        threefry_partitionable=threefry_partitionable,
        padded_outside_capacity=padded_outside_capacity,
        refinement=refinement,
        schedule=schedule,
    )
    answer["block_calls"] = metadata
    answer["independent_original_calendar_and_controls"] = True
    return answer


def report(answer):
    return charged.report(answer) | dict(
        block_calls=answer["block_calls"], independent_original_calendar_and_controls=True
    )
