"""Independent complete calcium/fuel carry and combined membrane/ECM stages.

Original cytosol, ER, plasma charge and finite-fuel anchors are retained. Only
the new phase clock resets; all physical amounts, gates and histories carry.
This oracle uses the independent ordinary equations, never production models,
and supplies no trajectory or native solver-loop qualification.
"""

import ast
import hashlib
import math
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType

import numpy as np

from validation.topology import active_profile_barrier_phase_handoff_reference as ionic
from validation.transport import owned_calcium_profile_barrier_reference as scheduled

REQUEST_KIND = "cells.owned_calcium_profile_barrier_phase_handoff_request@1"
OWNERS = {
    "resolved_calcium_profile_barrier_epoch@1": "resolved_calcium_profile_barriers@1",
    "resolved_calcium_energy_profile_barrier_epoch@1": "resolved_calcium_energy_profile_barriers@1",
}
flatten, unpack = scheduled.flatten, scheduled.unpack


def target_definition(epoch):
    value = deepcopy(epoch)
    if value["model"]["id"] not in OWNERS:
        raise ValueError("Require the complete calcium or finite-fuel combined epoch")
    value["model"] = value["model"]["scheduled"]
    return value


def state_geometry(raw, context):
    """Derive padded shapes and real-owner masks from explicit declarations."""
    model, execution = raw["model"], raw["execution"]
    ion = model["ionic"]
    ion_raw = dict(model=ion, execution=execution)
    ion_counts = ionic.active_owner_counts(ion_raw)
    compact = {k: v for k, v in context["shapes"].items() if k in ion_counts}
    shapes = ionic.padded_shapes(ion_raw, dict(shapes=compact))
    masks = {}
    for name, shape in shapes.items():
        masks[name] = np.zeros(shape, dtype=bool)
        masks[name][..., : ion_counts[name]] = True
    by_cell = {row["cell_id"]: row["model"] for row in model["stores"]}
    stores = [by_cell[cell["id"]] for cell in ion["cells"]]
    nc = len(stores)
    ns = len(stores[0]["species"])
    for store in stores:
        if len(store["species"]) != ns:
            raise ValueError("Require matching chemical species axes")
        if len(store["compartments"]) > execution["chemical_capacity"]:
            raise ValueError("Chemical owner capacity is insufficient")
        if len(store["reactions"]) > execution["reaction_capacity"]:
            raise ValueError("Reaction capacity is insufficient")
    shapes.update(
        chemical_amount_increment=(nc, ns, execution["chemical_capacity"]),
        reaction_extent=(nc, execution["reaction_capacity"]),
        reaction_dissipated_energy_pJ=(nc, execution["reaction_capacity"]),
        er_passive_transferred=(nc, ns),
        er_pump_transferred=(nc, 1),
        er_release_transferred=(nc, 1),
        er_transport_dissipated_energy_pJ=(nc, 3),
        er_metabolic_work_pJ=(nc,),
    )
    nm = execution["membrane_capacity"]
    for name in (
        "plasma_pump_cycles",
        "plasma_exchange_cycles",
        "calcium_channel_transferred",
        "calcium_channel_dissipated_energy_pJ",
        "plasma_metabolic_work_pJ",
    ):
        shapes[name] = (nm,)
    for name in ("plasma_dissipated_energy_pJ", "calcium_gate"):
        shapes[name] = (2, nm)
    plasma = {
        "plasma_pump_cycles",
        "plasma_exchange_cycles",
        "plasma_dissipated_energy_pJ",
        "calcium_gate",
        "calcium_channel_transferred",
        "calcium_channel_dissipated_energy_pJ",
        "plasma_metabolic_work_pJ",
    }
    for name, shape in shapes.items():
        if name in masks:
            continue
        masks[name] = np.ones(shape, dtype=bool)
        if name in plasma:
            masks[name][..., len(ion["membranes"]) :] = False
        if name == "chemical_amount_increment":
            for i, store in enumerate(stores):
                masks[name][i, :, len(store["compartments"]) :] = False
        if name in ("reaction_extent", "reaction_dissipated_energy_pJ"):
            for i, store in enumerate(stores):
                masks[name][i, len(store["reactions"]) :] = False
    if "energy_pools" in model:
        shapes["energy_amount_increment_fmol"] = (3, execution["capacity"])
        masks["energy_amount_increment_fmol"] = np.zeros(
            shapes["energy_amount_increment_fmol"], bool
        )
        masks["energy_amount_increment_fmol"][:, :nc] = True
        for name in (
            "regeneration_cycles_fmol",
            "regeneration_dissipated_energy_pJ",
            "regeneration_supplied_work_pJ",
        ):
            shapes[name] = (execution["regeneration_capacity"],)
            masks[name] = np.arange(execution["regeneration_capacity"]) < len(
                model["regeneration_ports"]
            )
    if set(shapes) != set(context["shapes"]):
        raise ValueError("Incomplete independently derived calcium/fuel field geometry")
    return shapes, masks


def decode_state(record, shapes, masks):
    if type(record) is not dict or set(record) != set(shapes):
        raise ValueError("Require every complete calcium/fuel checkpoint field")
    result = {}
    for name, shape in shapes.items():
        row = record[name]
        if type(row) is not dict or set(row) != {"dtype", "shape", "values"}:
            raise ValueError("Require a complete typed checkpoint array: " + name)
        if (
            row["dtype"] != np.dtype("float64").str
            or type(row["shape"]) is not list
            or any(type(v) is not int for v in row["shape"])
            or row["shape"] != list(shape)
            or type(row["values"]) is not list
            or any(type(v) is not float for v in ionic._values(row["values"]))
        ):
            raise ValueError("Invalid typed array shape/precision: " + name)
        try:
            value = np.asarray(row["values"], dtype=np.float64)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("Malformed checkpoint values: " + name) from error
        if value.shape != shape or not np.isfinite(value).all():
            raise ValueError("Wrong shape or nonfinite checkpoint values: " + name)
        if np.any(value[~masks[name]] != 0.0):
            raise ValueError("History on an absent physical owner: " + name)
        result[name] = value.copy()
    return result


def bind(request):
    if request.get("kind") != REQUEST_KIND:
        raise ValueError("Require the explicit complete calcium/fuel phase request")
    source, target = request["source"]["definition"], request["simulation"]
    if (
        source["model"]["id"] not in OWNERS.values()
        or source["model"]["id"] != target["model"]["id"]
        or source["model"]["phase"] != "INIT"
        or target["model"]["phase"] != "SIM"
    ):
        raise ValueError("Require the same complete ordinary owner from INIT to SIM")
    original, context = scheduled.bind(source), scheduled.bind(target)
    if original["parent_definition"]["model"] != context["parent_definition"]["model"]:
        raise ValueError("Cannot rewrite chemical, plasma or fuel accounting anchors")
    if source["model"]["coupled_preparation"] != target["model"]["coupled_preparation"]:
        raise ValueError("Both original static recipes must remain identical")
    capacities = (*ionic.CAPACITIES, "chemical_capacity", "reaction_capacity")
    if "energy_pools" in source["model"]:
        capacities += ("regeneration_capacity",)
    if any(source["execution"][key] != target["execution"][key] for key in capacities):
        raise ValueError("Cannot remap original physical owner capacities")
    shapes, masks = state_geometry(source, original)
    checkpoint = request["source"]["checkpoint"]
    arrays = decode_state(checkpoint["state"], shapes, masks)
    time = checkpoint["time"]
    if (
        type(time) not in (int, float)
        or not math.isfinite(time)
        or not 0 <= time <= source["experiment"]["end_time"]
        or abs(arrays["phase_clock_s"][0] - time) > original["phase_clock_atol_s"]
        or any(
            type(checkpoint[k]) is not int or checkpoint[k] < 0
            for k in ("step_index", "event_index")
        )
    ):
        raise ValueError("Invalid original INIT checkpoint clock")
    carried = {name: value.copy() for name, value in arrays.items()}
    carried["phase_clock_s"] = np.zeros((1,), dtype=np.float64)
    context.update(
        source_context=original,
        source_arrays=arrays,
        carried_arrays=carried,
        padded_shapes=shapes,
        active_masks=masks,
        simulation=deepcopy(target),
        source_time_s=float(time),
    )
    return context


def initial(request):
    context = bind(request)
    return context, flatten(context, context["carried_arrays"])


def carried_arrays(request):
    return bind(request)["carried_arrays"]


def evaluate(context, vector, time):
    vector = np.asarray(vector)
    if (
        vector.shape != (sum(math.prod(s) for s in context["shapes"].values()),)
        or not np.isfinite(vector).all()
        or isinstance(time, (bool, np.bool_))
        or not isinstance(time, (int, float, np.integer, np.floating))
        or not math.isfinite(time)
        or not 0 <= time <= context["simulation"]["experiment"]["end_time"]
    ):
        raise ValueError("Require a finite complete stage at a bounded SIM time")
    return scheduled.evaluate(context, vector, float(time))


def conservation(context, vector):
    """Track chemical owners, free versus total ions and neutral finite fuel."""
    result = scheduled.conservation(context, vector)
    parent = context["parent"]
    calcium = parent.get("calcium", parent)
    model = context["parent_definition"]["model"]
    ion = model["ionic"]
    fields = unpack(context, vector)
    cells = [cell["id"] for cell in ion["cells"]]
    ions = [row["id"] for row in ion["species"]]
    stores = {row["cell_id"]: row["model"] for row in model["stores"]}
    chemical_initial, chemical_amount, free, voltage, backgrounds, material, ownership = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    for i, store in enumerate(calcium["stores"]):
        declaration = stores[cells[i]]
        delta = fields["chemical_amount_increment"][i]
        current = store.n0 + delta
        z = np.asarray(store.z)
        initial_charge = scheduled.F * 1e-15 * np.sum(z[:, None] * store.n0, axis=0)
        anchor = np.zeros(store.n0.shape[1])
        anchor[store.cy] = calcium["qi"][i] - store.cap * store.membrane["initial_voltage_V"]
        anchor[store.er] = store.cap * store.membrane["initial_voltage_V"]
        backgrounds.append(anchor - initial_charge)
        chemical_initial.append(store.n0.copy())
        chemical_amount.append(current)
        free.append([current[store.ids.index(sid), store.cy] for sid in ions])
        voltage.append(
            store.membrane["initial_voltage_V"]
            + scheduled.F * 1e-15 / store.cap * np.sum(z * delta[:, store.er])
        )
        expected = np.zeros_like(delta)
        for j, reaction in enumerate(store.reactions):
            k = store.owners.index(reaction["compartment"])
            for s, sid in enumerate(store.ids):
                coefficient = reaction["products"].get(sid, 0) - reaction["reactants"].get(sid, 0)
                expected[s, k] += coefficient * fields["reaction_extent"][i, j]
        er_transfer = fields["er_passive_transferred"][i].copy()
        er_transfer[store.ca] += (
            fields["er_pump_transferred"][i, 0] + fields["er_release_transferred"][i, 0]
        )
        expected[:, store.cy] -= er_transfer
        expected[:, store.er] += er_transfer
        for j, sid in enumerate(ions):
            expected[store.ids.index(sid), store.cy] += fields["amount_increment"][j, i]
        material.append(delta - expected)
        by_species = {row["id"]: row for row in declaration["species"]}
        content = np.asarray(
            [[by_species[sid]["moieties"].get(ion_id, 0) for sid in store.ids] for ion_id in ions]
        )
        ownership.append(content @ delta.sum(axis=1) - fields["amount_increment"][:, i])
    z = np.asarray(calcium["layout"]["valence"])
    dq_inside = scheduled.F * 1e-15 * np.sum(z * fields["amount_increment"], axis=0)
    dq_outside = scheduled.F * 1e-15 * np.sum(z * fields["extracellular_amount_increment"], axis=0)
    result.update(
        original_cell_free_amount_fmol=calcium["ai"].copy(),
        original_outside_amount_fmol=calcium["ao"].copy(),
        original_cell_charge_C=calcium["qi"].copy(),
        original_outside_charge_C=calcium["qo"].copy(),
        original_chemical_amount_fmol=np.asarray(chemical_initial),
        chemical_fixed_background_C=np.asarray(backgrounds),
        chemical_amount_fmol=np.asarray(chemical_amount),
        free_cytosol_amount_fmol=np.asarray(free).T,
        er_voltage_V=np.asarray(voltage),
        cell_charge_C=calcium["qi"] + dq_inside,
        outside_charge_C=calcium["qo"] + dq_outside,
        chemical_material_residual_fmol=np.asarray(material),
        chemical_ionic_owner_residual_fmol=np.asarray(ownership),
        global_material_residual_fmol=fields["amount_increment"].sum(axis=1)
        + fields["extracellular_amount_increment"].sum(axis=1)
        - fields["reservoir_supplied"].sum(axis=1),
        global_charge_residual_C=float(
            fields["electrode_charge_transferred_C"].sum()
            + scheduled.F * 1e-15 * np.sum(z * fields["reservoir_supplied"])
        ),
    )
    if "energy_amount_increment_fmol" in fields:
        count = len(cells)
        amount = parent["energy_initial"] + fields["energy_amount_increment_fmol"]
        hydrolysis, work = np.zeros(count), np.zeros(count)
        for j, patch in enumerate(ion["membranes"]):
            owner = cells.index(patch["inside"])
            hydrolysis[owner] += fields["pump_cycles"][j] + fields["plasma_pump_cycles"][j]
            work[owner] += fields["metabolic_work_pJ"][j] + fields["plasma_metabolic_work_pJ"][j]
        hydrolysis += fields["er_pump_transferred"][:, 0]
        work += fields["er_metabolic_work_pJ"]
        regenerated, heat, supplied = np.zeros(count), np.zeros(count), np.zeros(count)
        pools = {row["id"]: row for row in model["energy_pools"]}
        for j, port in enumerate(model["regeneration_ports"]):
            owner = cells.index(pools[port["pool_id"]]["cell_id"])
            regenerated[owner] += fields["regeneration_cycles_fmol"][j]
            heat[owner] += fields["regeneration_dissipated_energy_pJ"][j]
            supplied[owner] += fields["regeneration_supplied_work_pJ"][j]
        free_energy = np.asarray(
            [
                float(
                    scheduled.pools.free_energy_change(
                        parent["energy_initial"][:, i],
                        amount[:, i],
                        parent["vi"][i],
                        parent["vi"][i],
                        parent["temperature"],
                        parent["energy_delta_g0"][i],
                    )
                )
                for i in range(count)
            ]
        )
        turnover = hydrolysis - regenerated
        expected = np.asarray([-turnover, turnover, turnover])
        result.update(
            original_fuel_amount_fmol=parent["energy_initial"].copy(),
            original_fuel_delta_g0_J_mol=parent["energy_delta_g0"].copy(),
            fuel_amount_fmol=amount,
            pool_cycle_residual_fmol=fields["energy_amount_increment_fmol"] - expected,
            pool_internal_transfer_residual_pJ=free_energy + work + heat - supplied,
        )
    return result


def dependency_manifest(root):
    """Complete reference closure, including audited legacy scalar helpers."""
    root = Path(root).resolve()
    pending, seen, result = [sys.modules[__name__]], set(), {}
    while pending:
        module = pending.pop()
        if module.__name__ in seen:
            continue
        seen.add(module.__name__)
        path = Path(module.__file__).resolve()
        legacy = path.parent == root / "tests" and path.name.startswith("reference_")
        if not path.is_relative_to(root / "validation") and not legacy:
            raise ValueError("Non-reference project dependency: " + str(path))
        if legacy:
            for node in ast.walk(ast.parse(path.read_text())):
                imported = (
                    [a.name for a in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                    if isinstance(node, ast.ImportFrom)
                    else []
                )
                if any(name.split(".")[0] in {"cells", "jax", "jaxlib"} for name in imported):
                    raise ValueError("Production/JAX import in scalar reference: " + str(path))
        with path.open("rb") as stream:
            result[str(path.relative_to(root))] = hashlib.file_digest(stream, "sha256").hexdigest()
        for value in vars(module).values():
            name = (
                value.__name__
                if isinstance(value, ModuleType)
                else getattr(value, "__module__", "")
            )
            candidate = sys.modules.get(name)
            location = getattr(candidate, "__file__", None)
            if location and Path(location).resolve().is_relative_to(root):
                pending.append(candidate)
    return dict(sorted(result.items()))


def carried_fuel_turnover(raw, initial_state):
    """Gross live-pool consumption at every declared SIM admission clock.

    Signed Na/K, PMCA, ER and regeneration routes are counted separately before
    hydrolysis and synthesis are added.  Opposing routes must not cancel in this
    step bound.  The minimum ATP/ADP/Pi amount is the actual carried amount, not
    the original inventory or the net pool derivative.
    """
    if (
        raw["model"]["id"] != "resolved_calcium_energy_profile_barriers@1"
        or raw["model"]["phase"] != "SIM"
    ):
        raise ValueError("Require the complete finite-fuel combined SIM owner")
    context = scheduled.bind(raw)
    state = np.asarray(initial_state)
    if (
        state.shape != scheduled.initial(context).shape
        or not np.isfinite(state).all()
        or state[-1] != 0.0
    ):
        raise ValueError("Require a complete finite carried state at SIM clock zero")
    parent = context["parent"]
    fields = unpack(context, state)
    amounts = parent["energy_initial"] + fields["energy_amount_increment_fmol"]
    if not np.isfinite(amounts).all() or np.any(amounts <= 0):
        raise ValueError("Carried ATP/ADP/Pi amounts must remain positive")
    minimum = np.min(amounts, axis=0)
    count = len(parent["cell_ids"])
    pump_owners = [*parent["patch_owners"], *parent["plasma_owners"], *range(count)]
    regeneration_owners = [
        parent["cell_ids"].index(parent["pools"][port["pool_id"]]["cell_id"])
        for port in raw["model"]["regeneration_ports"]
    ]
    clocks = {0.0, float(raw["experiment"]["end_time"])}
    for name, groups in raw["experiment"].items():
        if name.endswith("_controls"):
            for group in groups:
                clocks.update(
                    float(v["time"])
                    for v in group["controls" if "controls" in group else "schedule"]
                )
    for event in (
        *raw["model"]["membrane_interventions"],
        *((raw["model"]["barrier_intervention"],) if raw["model"]["barrier_intervention"] else ()),
    ):
        clocks.update((event["on_s"], (event["on_s"] + event["off_s"]) / 2, event["off_s"]))
    rows = []
    for time in sorted(clocks):
        trial = state.copy()
        trial[-1] = time
        slope, _, _ = scheduled.evaluate(context, trial, float(time))
        rates = unpack(context, slope)
        pump_rates = [
            *rates["pump_cycles"],
            *rates["plasma_pump_cycles"],
            *rates["er_pump_transferred"][:, 0],
        ]
        regeneration_rates = rates["regeneration_cycles_fmol"].tolist()
        exchange = scheduled.pools.exchange(
            pump_rates, pump_owners, regeneration_rates, regeneration_owners, count
        )
        hydrolysis = np.asarray(exchange["gross_hydrolysis_fmol_s"])
        synthesis = np.asarray(exchange["gross_synthesis_fmol_s"])
        fractional = (hydrolysis + synthesis) / minimum
        if not np.isfinite(fractional).all():
            raise ValueError("Nonfinite carried gross-turnover rate")
        rows.append(
            dict(
                time_s=float(time),
                fractional_rate_s=float(np.max(fractional, initial=0.0)),
                fractional_rate_by_owner_s=fractional.tolist(),
                minimum_carried_amount_fmol=minimum.tolist(),
                signed_pump_cycles_fmol_s=[float(v) for v in pump_rates],
                pump_owners=pump_owners,
                signed_regeneration_cycles_fmol_s=regeneration_rates,
                regeneration_owners=regeneration_owners,
                gross_hydrolysis_fmol_s=hydrolysis.tolist(),
                gross_synthesis_fmol_s=synthesis.tolist(),
                net_pool_amount_rate_fmol_s=exchange["amount_fmol_s"],
            )
        )
    return max(row["fractional_rate_s"] for row in rows), rows
