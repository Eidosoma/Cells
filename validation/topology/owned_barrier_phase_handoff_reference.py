"""Independent full ionic/ionic/calcium/fuel ECM-only INIT-to-SIM carry.

No membrane-profile recipe is synthesized. Original physical amounts, charges,
chemical stores, gates, neutral fuel and every work/transfer history are kept.
Only the ECM phase clock resets; complete independent parent equations use the
current native face coefficients. No Cells/JAX imports or trajectory claim.
"""

import ast
import hashlib
import math
import sys
from copy import deepcopy
from decimal import Decimal, localcontext
from pathlib import Path
from types import ModuleType

import numpy as np

from validation.chemistry import finite_energy_reference as energy_chemistry
from validation.transport import owned_barrier_interventions_reference as scheduled

REQUEST_KIND = "cells.owned_extracellular_barrier_phase_handoff_request@1"
OWNERS = {
    "resolved_active_extracellular_barrier_epoch@1": "resolved_active_extracellular_barriers@1",
    "resolved_calcium_extracellular_barrier_epoch@1": "resolved_calcium_extracellular_barriers@1",
    "resolved_calcium_energy_extracellular_barrier_epoch@1": (
        "resolved_calcium_energy_extracellular_barriers@1"
    ),
}
CAPACITIES = (
    "capacity",
    "extracellular_capacity",
    "membrane_capacity",
    "edge_capacity",
    "face_capacity",
    "channel_capacity",
)
F, R = scheduled.ionic.F, scheduled.ionic.R
flatten, unpack = scheduled.flatten, scheduled.unpack


def target_definition(epoch):
    result = deepcopy(epoch)
    model = result["model"]
    if model["id"] not in OWNERS or model["scheduled"]["id"] != OWNERS[model["id"]]:
        raise ValueError("Require a complete standalone ionic/ionic/calcium/fuel ECM epoch")
    result["model"] = result["model"]["scheduled"]
    return result


def active_owner_counts(raw):
    """Count declared owners independently of packed or padded array shapes."""
    model = raw["model"]
    families = {
        "cells": ("amount_increment",),
        "extracellular": (
            "extracellular_amount_increment",
            "reservoir_supplied",
            "electrode_charge_transferred_C",
            "reservoir_work_pJ",
            "electrode_work_pJ",
        ),
        "membranes": (
            "membrane_transferred",
            "membrane_dissipated_energy_pJ",
            "pump_cycles",
            "pump_dissipated_energy_pJ",
            "metabolic_work_pJ",
        ),
        "junctions": ("junction_transferred", "junction_dissipated_energy_pJ", "junction_gate"),
        "faces": ("face_transferred", "face_dissipated_energy_pJ"),
        "channels": ("channel_gate", "channel_transferred", "channel_dissipated_energy_pJ"),
    }
    return {name: len(model[family]) for family, names in families.items() for name in names} | {
        "phase_clock_s": 1
    }


def padded_shapes(raw, context):
    """Derive every padded owner axis from the declared physical capacities."""
    x = raw["execution"]
    species = len(raw["model"]["species"])
    counts = active_owner_counts(raw)
    owners = {
        "amount_increment": "capacity",
        "extracellular_amount_increment": "extracellular_capacity",
        "membrane_transferred": "membrane_capacity",
        "junction_transferred": "edge_capacity",
        "face_transferred": "face_capacity",
        "reservoir_supplied": "extracellular_capacity",
        "membrane_dissipated_energy_pJ": "membrane_capacity",
        "junction_dissipated_energy_pJ": "edge_capacity",
        "face_dissipated_energy_pJ": "face_capacity",
        "electrode_charge_transferred_C": "extracellular_capacity",
        "reservoir_work_pJ": "extracellular_capacity",
        "electrode_work_pJ": "extracellular_capacity",
        "channel_gate": "channel_capacity",
        "channel_transferred": "channel_capacity",
        "channel_dissipated_energy_pJ": "channel_capacity",
        "junction_gate": "edge_capacity",
        "pump_cycles": "membrane_capacity",
        "pump_dissipated_energy_pJ": "membrane_capacity",
        "metabolic_work_pJ": "membrane_capacity",
    }
    result = {}
    for name, active_shape in context["shapes"].items():
        if name == "phase_clock_s":
            result[name] = (1,)
            continue
        capacity = x[owners[name]]
        if type(capacity) is not int or capacity < counts[name]:
            raise ValueError("Insufficient physical owner capacity: " + name)
        result[name] = (
            (2, capacity)
            if name == "channel_gate"
            else (species, capacity)
            if len(active_shape) == 2
            else (capacity,)
        )
    return result


def _values(value):
    if type(value) is list:
        for child in value:
            yield from _values(child)
    else:
        yield value


def state_geometry(raw, context):
    """Derive padded shapes and real-owner masks from explicit declarations."""
    model, execution = raw["model"], raw["execution"]
    ion = scheduled.leaf(context["parent_definition"])
    ion_raw = dict(model=ion, execution=execution)
    ion_counts = active_owner_counts(ion_raw)
    compact = {k: v for k, v in context["shapes"].items() if k in ion_counts}
    shapes = padded_shapes(ion_raw, dict(shapes=compact))
    masks = {}
    for name, shape in shapes.items():
        masks[name] = np.zeros(shape, dtype=bool)
        masks[name][..., : ion_counts[name]] = True
    if "stores" not in model:
        if set(shapes) != set(context["shapes"]):
            raise ValueError("Incomplete independently derived ionic geometry")
        return shapes, masks
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
        raise ValueError("Incomplete independently derived ionic/ionic/calcium/fuel field geometry")
    return shapes, masks


def decode_state(record, shapes, masks):
    if type(record) is not dict or set(record) != set(shapes):
        raise ValueError("Require every complete ionic/ionic/calcium/fuel checkpoint field")
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
            or any(type(v) is not float for v in _values(row["values"]))
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
        raise ValueError("Require the explicit complete ionic/ionic/calcium/fuel phase request")
    source, target = request["source"]["definition"], request["simulation"]
    forbidden = {"profile_preparation", "coupled_preparation", "membrane_interventions"}
    if any(forbidden & value["model"].keys() for value in (source, target)):
        raise ValueError("Standalone ECM epochs cannot contain membrane-profile recipes")
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
    if source["model"]["barrier_preparation"] != target["model"]["barrier_preparation"]:
        raise ValueError("The original standalone ECM recipe must remain identical")
    capacities = CAPACITIES
    if "stores" in source["model"]:
        capacities += ("chemical_capacity", "reaction_capacity")
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


def parent_conservation(context, vector):
    """Direct 80-digit molecular energy, ion ownership and neutral-pool invariants."""
    parent = context["parent"]
    fields = unpack(context, vector)
    clock = float(fields["phase_clock_s"][0])
    _, potential, _ = scheduled.evaluate(context, vector, clock)
    if "initial_phi" not in context:
        zero = scheduled.initial(context)
        context["initial_phi"] = scheduled.evaluate(context, zero, 0.0)[1]
    calcium = parent.get("calcium", parent)
    ion = scheduled.leaf(context["parent_definition"])
    before_phi = context["initial_phi"]
    with localcontext() as precision:
        precision.prec = 80

        def dec(value):
            return Decimal(str(float(value)))

        rt = dec(R) * dec(parent["layout"]["temperature"]) * Decimal("0.001")
        stored = Decimal(0)
        if "chemical_amount_increment" in fields:
            for i, store in enumerate(calcium["stores"]):
                for s in range(len(store.ids)):
                    for k in range(store.n0.shape[1]):
                        a0 = dec(store.n0[s, k])
                        amount = a0 + dec(fields["chemical_amount_increment"][i, s, k])
                        denominator = dec(store.volume[k]) * dec(store.c0)
                        stored += rt * (
                            amount * (dec(store.mu0[s]) + (amount / denominator).ln() - 1)
                            - a0 * (dec(store.mu0[s]) + (a0 / denominator).ln() - 1)
                        )
                change = (
                    Decimal("1e-15")
                    * dec(F)
                    / dec(store.cap)
                    * sum(
                        dec(z) * dec(a)
                        for z, a in zip(
                            store.z,
                            fields["chemical_amount_increment"][i, :, store.er],
                            strict=True,
                        )
                    )
                )
                stored += (
                    Decimal("0.5e12")
                    * dec(store.cap)
                    * change
                    * (2 * dec(store.membrane["initial_voltage_V"]) + change)
                )
        else:
            for s in range(parent["ai"].shape[0]):
                for i in range(len(parent["vi"])):
                    a0 = dec(parent["ai"][s, i])
                    amount = a0 + dec(fields["amount_increment"][s, i])
                    volume = dec(parent["vi"][i])
                    stored += rt * (
                        amount * ((amount / volume).ln() - 1) - a0 * ((a0 / volume).ln() - 1)
                    )
        for s in range(parent["ao"].shape[0]):
            for i in range(len(parent["vo"])):
                a0 = dec(parent["ao"][s, i])
                amount = a0 + dec(fields["extracellular_amount_increment"][s, i])
                volume = dec(parent["vo"][i])
                stored += rt * (
                    amount * ((amount / volume).ln() - 1) - a0 * ((a0 / volume).ln() - 1)
                )
        cells = [p["id"] for p in ion["cells"]]
        outsides = [p["id"] for p in ion["extracellular"]]
        n = len(cells)
        for patch in ion["membranes"]:
            i, o = cells.index(patch["inside"]), n + outsides.index(patch["outside"])
            voltage, before = dec(potential[i] - potential[o]), dec(before_phi[i] - before_phi[o])
            stored += (
                Decimal("0.5e12")
                * dec(patch["capacitance_F"])
                * (voltage - before)
                * (voltage + before)
            )
        if "energy_amount_increment_fmol" in fields:
            pool_initial = parent["energy_initial"]
            current = pool_initial + fields["energy_amount_increment_fmol"]
            stored += sum(
                dec(
                    energy_chemistry.free_energy_change(
                        pool_initial[:, i],
                        current[:, i],
                        parent["vi"][i],
                        parent["vi"][i],
                        parent["temperature"],
                        parent["energy_delta_g0"][i],
                    )
                )
                for i in range(n)
            )
        heat = sum(dec(np.sum(v)) for k, v in fields.items() if k.endswith("_dissipated_energy_pJ"))
        work_names = (
            ("regeneration_supplied_work_pJ",)
            if "energy_amount_increment_fmol" in fields
            else ("metabolic_work_pJ", "plasma_metabolic_work_pJ", "er_metabolic_work_pJ")
        )
        work = sum(
            dec(np.sum(fields[k]))
            for k in (*work_names, "reservoir_work_pJ", "electrode_work_pJ")
            if k in fields
        )
        residual = float(stored + heat - work)
    local = fields["amount_increment"].copy()
    outside = fields["extracellular_amount_increment"].copy() - fields["reservoir_supplied"]
    for j, route in enumerate(ion["membranes"]):
        i, o = cells.index(route["inside"]), outsides.index(route["outside"])
        flux = fields["membrane_transferred"][:, j].copy()
        for c, ch in enumerate(ion["channels"]):
            if ch["membrane_id"] == route["id"]:
                flux += fields["channel_transferred"][:, c]
        if route["pump"] is not None:
            ids = [s["id"] for s in ion["species"]]
            flux[ids.index("Na")] += 3 * fields["pump_cycles"][j]
            flux[ids.index("K")] -= 2 * fields["pump_cycles"][j]
        if "plasma_pump_cycles" in fields:
            ids = [s["id"] for s in ion["species"]]
            flux[ids.index("Ca")] += (
                fields["plasma_pump_cycles"][j]
                + fields["plasma_exchange_cycles"][j]
                + fields["calcium_channel_transferred"][j]
            )
            flux[ids.index("Na")] -= 3 * fields["plasma_exchange_cycles"][j]
        local[:, i] += flux
        outside[:, o] -= flux
    for family, values, names in (("junction", local, cells), ("face", outside, outsides)):
        for j, route in enumerate(ion[family + "s"]):
            values[:, names.index(route["sender"])] += fields[family + "_transferred"][:, j]
            values[:, names.index(route["receiver"])] -= fields[family + "_transferred"][:, j]
    result = dict(
        energy_pJ=residual,
        local_material_fmol=float(np.max(np.abs(local), initial=0)),
        outside_material_fmol=float(np.max(np.abs(outside), initial=0)),
    )
    if "energy_amount_increment_fmol" in fields:
        change = fields["energy_amount_increment_fmol"]
        result.update(
            adenylate_fmol=float(np.max(np.abs(change[0] + change[1]), initial=0)),
            phosphorus_fmol=float(
                np.max(np.abs(3 * change[0] + 2 * change[1] + change[2]), initial=0)
            ),
        )
    return result


def conservation(context, vector):
    """Original electrical/material anchors, chemistry and once-owned fuel work."""
    result = parent_conservation(context, vector)
    parent = context["parent"]
    calcium = parent.get("calcium", parent)
    model = context["parent_definition"]["model"]
    ion = scheduled.leaf(context["parent_definition"])
    fields = unpack(context, vector)
    cells = [cell["id"] for cell in ion["cells"]]
    ions = [row["id"] for row in ion["species"]]
    z = np.asarray(calcium["layout"]["valence"])
    dq_inside = F * 1e-15 * np.sum(z * fields["amount_increment"], axis=0)
    dq_outside = F * 1e-15 * np.sum(z * fields["extracellular_amount_increment"], axis=0)
    result.update(
        original_cell_free_amount_fmol=calcium["ai"].copy(),
        original_outside_amount_fmol=calcium["ao"].copy(),
        original_cell_charge_C=calcium["qi"].copy(),
        original_outside_charge_C=calcium["qo"].copy(),
        cell_charge_C=calcium["qi"] + dq_inside,
        outside_charge_C=calcium["qo"] + dq_outside,
        global_material_residual_fmol=fields["amount_increment"].sum(axis=1)
        + fields["extracellular_amount_increment"].sum(axis=1)
        - fields["reservoir_supplied"].sum(axis=1),
        global_charge_residual_C=float(
            fields["electrode_charge_transferred_C"].sum()
            + F * 1e-15 * np.sum(z * fields["reservoir_supplied"])
        ),
    )
    if "chemical_amount_increment" in fields:
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
            initial_charge = F * 1e-15 * np.sum(z[:, None] * store.n0, axis=0)
            anchor = np.zeros(store.n0.shape[1])
            anchor[store.cy] = calcium["qi"][i] - store.cap * store.membrane["initial_voltage_V"]
            anchor[store.er] = store.cap * store.membrane["initial_voltage_V"]
            backgrounds.append(anchor - initial_charge)
            chemical_initial.append(store.n0.copy())
            chemical_amount.append(current)
            free.append([current[store.ids.index(sid), store.cy] for sid in ions])
            voltage.append(
                store.membrane["initial_voltage_V"]
                + F * 1e-15 / store.cap * np.sum(z * delta[:, store.er])
            )
            expected = np.zeros_like(delta)
            for j, reaction in enumerate(store.reactions):
                k = store.owners.index(reaction["compartment"])
                for s, sid in enumerate(store.ids):
                    coefficient = reaction["products"].get(sid, 0) - reaction["reactants"].get(
                        sid, 0
                    )
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
                [
                    [by_species[sid]["moieties"].get(ion_id, 0) for sid in store.ids]
                    for ion_id in ions
                ]
            )
            ownership.append(content @ delta.sum(axis=1) - fields["amount_increment"][:, i])
        result.update(
            original_chemical_amount_fmol=np.asarray(chemical_initial),
            chemical_fixed_background_C=np.asarray(backgrounds),
            chemical_amount_fmol=np.asarray(chemical_amount),
            free_cytosol_amount_fmol=np.asarray(free).T,
            er_voltage_V=np.asarray(voltage),
            chemical_material_residual_fmol=np.asarray(material),
            chemical_ionic_owner_residual_fmol=np.asarray(ownership),
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
        pool_rows = {row["id"]: row for row in model["energy_pools"]}
        for j, port in enumerate(model["regeneration_ports"]):
            owner = cells.index(pool_rows[port["pool_id"]]["cell_id"])
            regenerated[owner] += fields["regeneration_cycles_fmol"][j]
            heat[owner] += fields["regeneration_dissipated_energy_pJ"][j]
            supplied[owner] += fields["regeneration_supplied_work_pJ"][j]
        free_energy = np.asarray(
            [
                float(
                    energy_chemistry.free_energy_change(
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
        raw["model"]["id"] != "resolved_calcium_energy_extracellular_barriers@1"
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
    for event in () if raw["model"]["intervention"] is None else (raw["model"]["intervention"],):
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
        exchange = energy_chemistry.exchange(
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
