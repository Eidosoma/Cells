"""Cut chemical/fuel owners and configured routes without duplicating their work."""

import math
from bisect import bisect_right
from copy import deepcopy

import numpy as np

from cells.core.grid import EventGrid
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, _fields, parse_spec
from cells.core.state import Checkpoint
from cells.core.surface_calcium_energy_transport_excision_spec import (
    MODEL_ID,
    POLICIES,
    SurfaceCalciumEnergyTransportExcisionModel,
    base_spec,
)
from cells.core.surface_calcium_energy_transport_spec import SurfaceCalciumEnergyTransportModel
from cells.core.tissue_excision import ExcisionResult, _chemical_terms, topology
from cells.models import surface_calcium_energy as fuel_model
from cells.models import surface_calcium_energy_transport as active
from cells.models import surface_tissue as passive
from cells.models.registry import get_model
from cells.numerics import surface_field
from cells.processes import betse_tissue_cut as removal
from cells.processes import finite_energy as fuel
from cells.processes.electrochemistry import CHARGE_PER_FMOL, R

GATES = ("channel_gate", "junction_gate", "calcium_gate")
# The parent builds PMCA/ER initial parameters through its legacy maintained-law
# constructors. Their anchor range is narrower than the live positive-pool domain.
# Retain that existing range explicitly; never clip a valid evolved fuel store.
FUEL_ANCHOR_RANGE_MM = (1e-9, 1e3)
CONTROL_GROUPS = {
    "membrane_controls": ("membrane_id", "schedule"),
    "junction_controls": ("junction_id", "schedule"),
    "channel_controls": ("channel_id", "schedule"),
    "pump_controls": ("pump_id", "schedule"),
    "store_controls": ("cell_id", "controls"),
    "plasma_controls": ("membrane_id", "schedule"),
    "calcium_channel_controls": ("channel_id", "schedule"),
    "regeneration_controls": ("regeneration_id", "schedule"),
    "network_transport_controls": ("transporter_id", "schedule"),
}


def ordinary(spec):
    if type(spec.model) is SurfaceCalciumEnergyTransportModel:
        return spec
    if type(spec.model) is SurfaceCalciumEnergyTransportExcisionModel:
        return base_spec(spec)
    raise ConfigError(
        "Transport excision requires resolved_calcium_energy_transport@1 or its excision epoch"
    )


def _point_check(spec, point):
    ordinary(spec)
    implementation = get_model(spec.model)
    initial, layout = implementation.initial_values(spec)
    start = getattr(spec.model, "epoch_start_time", 0.0)
    if (
        type(point) is not Checkpoint
        or isinstance(point.time, bool)
        or not isinstance(point.time, (int, float))
        or not math.isfinite(point.time)
        or not start <= point.time <= spec.experiment.end_time
        or type(point.step_index) is not int
        or type(point.event_index) is not int
        or EventGrid(spec).exact_index(point.time) != point.step_index
        or event_index(spec, point.time) != point.event_index
        or type(point.state) is not implementation.STATE_TYPE
        or type(point.layout) is not implementation.LAYOUT_TYPE
    ):
        raise ConfigError("Invalid complete calcium excision checkpoint or absolute clock")
    for value, template in zip(point.state, initial, strict=True):
        if np.asarray(value).shape != template.shape or np.asarray(value).dtype != template.dtype:
            raise ConfigError(
                "Transport/calcium excision source state shape or precision disagrees"
            )
    if any(
        np.asarray(a).dtype != b.dtype or not np.array_equal(a, b)
        for a, b in zip(point.layout, layout, strict=True)
    ):
        raise ConfigError("Transport/calcium excision source layout does not match its definition")
    if point.time == start and any(
        not np.array_equal(a, b) for a, b in zip(point.state, initial, strict=True)
    ):
        raise ConfigError(
            "Transport/calcium excision source initial state does not match its epoch"
        )
    # Removal is a host boundary and also accepts checkpoints still on a device.
    # NumPy dispatching take() to a JAX array has incompatible mode semantics.
    state = type(point.state)(*(np.asarray(v) for v in point.state))
    implementation.check_values(state, spec)
    table = control_values(spec, [point.time])
    control = type(table)(*(v[0] for v in table))
    if not implementation.control_domain_valid(state, control, layout, layout.active, xp=np):
        raise ConfigError("Transport/calcium excision source actual-control field is invalid")


def capture_source(spec, point):
    _point_check(spec, point)
    return dict(
        definition=spec.to_dict(),
        checkpoint=dict(
            time=point.time,
            step_index=point.step_index,
            event_index=point.event_index,
            state={k: np.asarray(v).tolist() for k, v in point.state._asdict().items()},
            layout={k: np.asarray(v).tolist() for k, v in point.layout._asdict().items()},
        ),
    )


def decode_source(source):
    _fields(source, {"definition", "checkpoint"}, "calcium excision source")
    spec = parse_spec(source["definition"])
    ordinary(spec)
    cp = _fields(
        source["checkpoint"],
        {"time", "step_index", "event_index", "state", "layout"},
        "source checkpoint",
    )
    model = get_model(spec.model)
    initial, template = model.initial_values(spec)
    _fields(cp["state"], set(initial._fields), "complete forty-two-field source state")
    _fields(cp["layout"], set(template._fields), "complete source layout")

    def array(raw, target):
        value = np.asarray(raw)
        if value.size:
            allowed = (
                "fiu" if target.dtype.kind == "f" else "iu" if target.dtype.kind in "iu" else "b"
            )
            if value.dtype.kind not in allowed:
                raise ConfigError("Transport/calcium source array numeric type disagrees")
        converted = value.astype(target.dtype)
        if target.dtype.kind in "iu" and not np.array_equal(value, converted):
            raise ConfigError(
                "Transport/calcium source integer layout exceeds its declared precision"
            )
        if converted.size == target.size == 0:
            converted = converted.reshape(target.shape)
        return converted

    try:
        state = model.STATE_TYPE(*(array(cp["state"][k], v) for k, v in initial._asdict().items()))
        layout = model.LAYOUT_TYPE(
            *(array(cp["layout"][k], v) for k, v in template._asdict().items())
        )
    except (TypeError, ValueError, OverflowError) as error:
        raise ConfigError("Require numeric complete active source arrays") from error
    point = Checkpoint(state, layout, cp["time"], cp["step_index"], cp["event_index"])
    _point_check(spec, point)
    return spec, point


def physical(spec, point):
    """Authoritative chemical inventory and its free-ion electrical view."""
    p = type(point.layout)(*(np.asarray(v) for v in point.layout))
    y = type(point.state)(*(np.asarray(v) for v in point.state))
    m = spec.model
    n, o = len(m.cells), len(m.extracellular)
    free, outside = active.physical_amounts(y, p)
    dq = passive.charge_increment(y, p, xp=np)
    table = control_values(spec, [point.time])
    control = type(table)(*(v[0] for v in table))
    values = active.readouts(y, control, p, xp=np)
    if not values.valid:
        raise ConfigError("Transport/calcium excision source field/chemical domain is invalid")
    chemical = (p.er_initial_amount + y.chemical_amount_increment)[:, :, :2]
    energy = []
    for i, store in enumerate(m.stores):
        volume = np.asarray([v.volume_pL for v in store.compartments])
        mu = np.asarray([s.standard_mu_RT for s in store.species])
        energy.append(
            1e-3
            * R
            * store.temperature_K
            * math.fsum(
                (
                    chemical[i]
                    * (
                        mu[:, None]
                        + np.log(chemical[i] / (volume * store.standard_concentration_mM))
                        - 1
                    )
                ).ravel()
            )
        )
    moieties = np.asarray([s.moieties for s in m.stores[0].species], dtype=float).T
    pool_amount = fuel_model.energy_amounts(y, p)[:, :n]
    invariants = fuel.invariants(pool_amount, xp=np)
    return dict(
        free_amount=free[:, :n],
        outside_amount=outside[:, :o],
        chemical_amount=chemical,
        chemical_species_amount=chemical.sum(axis=-1),
        moiety_amount=np.einsum("ks,nsc->nk", moieties, chemical),
        charge=(p.initial_cell_charge_C + dq[: len(p.active)])[:n],
        outside_charge=(p.initial_outside_charge_C + dq[len(p.active) :])[:o],
        voltage=values.field.rates.membrane_voltage_V[: len(m.membranes)],
        er_voltage=values.kinetic.er_voltage_V,
        chemical_background_C=p.chemical_fixed_charge_C[:, :2],
        er_capacitance=p.er_capacitance,
        chemical_energy_pJ=np.asarray(energy),
        outside_chemical_energy_pJ=math.fsum(
            _chemical_terms(
                outside[:, :o], [v.volume_pL for v in m.extracellular], m.temperature_K
            ).ravel()
        ),
        electrode=values.field.electrode_charge_C[:o],
        potential=values.field.potential_V,
        fuel_amount=pool_amount,
        fuel_moieties=np.stack((invariants.adenylate_fmol, invariants.phosphorus_fmol)),
        fuel_energy_pJ=values.energy.free_energy_pJ[:n],
    )


def derive_tissue(spec, point, removed_ids):
    _point_check(spec, point)
    m, before = spec.model, physical(spec, point)
    fields = {
        "fuel_amount_fmol": removal.OwnedField(
            before["fuel_amount"], "cell", kind="quantity", units="fmol", nonnegative=True
        ),
        "fuel_moieties_fmol": removal.OwnedField(
            before["fuel_moieties"], "cell", kind="quantity", units="fmol", nonnegative=True
        ),
        "fuel_energy_pJ": removal.OwnedField(
            before["fuel_energy_pJ"], "cell", kind="quantity", units="pJ"
        ),
        "chemical_species_fmol": removal.OwnedField(
            before["chemical_species_amount"],
            "cell",
            axis=0,
            kind="quantity",
            units="fmol",
            nonnegative=True,
        ),
        "chemical_moieties_fmol": removal.OwnedField(
            before["moiety_amount"], "cell", axis=0, kind="quantity", units="fmol", nonnegative=True
        ),
        "outside_amount_fmol": removal.OwnedField(
            before["outside_amount"], "environment", kind="quantity", units="fmol", nonnegative=True
        ),
        "cell_charge_C": removal.OwnedField(before["charge"], "cell", kind="quantity", units="C"),
        "chemical_background_C": removal.OwnedField(
            before["chemical_background_C"], "cell", axis=0, kind="quantity", units="C"
        ),
        "chemical_energy_pJ": removal.OwnedField(
            before["chemical_energy_pJ"], "cell", kind="quantity", units="pJ"
        ),
        "er_capacitor_energy_pJ": removal.OwnedField(
            0.5e12 * before["er_capacitance"] * before["er_voltage"] ** 2,
            "cell",
            kind="quantity",
            units="pJ",
            nonnegative=True,
        ),
        "plasma_capacitor_energy_pJ": removal.OwnedField(
            0.5e12 * np.asarray([v.capacitance_F for v in m.membranes]) * before["voltage"] ** 2,
            "membrane",
            kind="quantity",
            units="pJ",
            nonnegative=True,
        ),
    }
    try:
        result = removal.apply_cut(topology(spec), removed_ids, fields)
    except (TypeError, ValueError) as error:
        raise ConfigError("Invalid calcium owner removal: " + str(error)) from error
    plan = result.plan
    if not plan.after.cell_ids:
        return None, result, before
    raw = ordinary(spec).to_dict()["model"]
    ion = raw["ionic"]
    for key, ids in (
        ("cells", plan.after.cell_ids),
        ("membranes", plan.after.membrane_ids),
        ("junctions", plan.after.edge_ids),
    ):
        ion[key] = [v for v in ion[key] if v["id"] in ids]
    for i, row in enumerate(ion["cells"]):
        old = plan.new_to_old["cell"][i]
        amount, charge = before["free_amount"][:, old], before["charge"][old]
        row["initial_amount_fmol"] = dict(zip(m.species_ids, amount.tolist(), strict=True))
        row["initial_charge_C"] = float(charge)
        # This ionic reference represents free cytosol only. Physical bound/ER
        # charges are in the chemical store, whose fixed backgrounds are checked
        # separately. Keeping the OLD effective anchor would double-count them.
        row["fixed_charge_equivalent_fmol"] = float(
            charge / CHARGE_PER_FMOL
            - math.fsum(z * a for z, a in zip(m.valence, amount, strict=True))
        )
    for i, row in enumerate(ion["extracellular"]):
        row["initial_amount_fmol"] = dict(
            zip(m.species_ids, before["outside_amount"][:, i].tolist(), strict=True)
        )
        row["initial_charge_C"] = float(before["outside_charge"][i])
    channels = []
    for i, row in enumerate(ion["channels"]):
        if row["membrane_id"] in plan.after.membrane_ids:
            row["initial_gate"] = np.asarray(point.state.channel_gate)[
                : len(row["initial_gate"]), i
            ].tolist()
            channels.append(row)
    ion["channels"] = channels
    raw["network_transport"]["routes"] = [
        row
        for row in raw["network_transport"]["routes"]
        if row["membrane_id"] in plan.after.membrane_ids
    ]
    edges = {v.id: i for i, v in enumerate(m.junctions)}
    for row in ion["junctions"]:
        row["gate"]["initial_gate"] = float(point.state.junction_gate[edges[row["id"]]])
    cells = {v.id: i for i, v in enumerate(m.cells)}
    if plan.changed:
        pump_owners = {
            cell.id
            for cell, store in zip(m.cells, m.stores, strict=True)
            if store.membrane.pump is not None
        }
        patch_owners = {v.id: v.inside for v in m.membranes}
        pump_owners.update(
            patch_owners[v.membrane_id] for v in m.plasma_routes if v.pump is not None
        )
        low, high = FUEL_ANCHOR_RANGE_MM
        for cell in m.cells:
            if cell.id in plan.after.cell_ids and cell.id in pump_owners:
                concentrations = before["fuel_amount"][:, cells[cell.id]] / cell.volume_pL
                if np.any((concentrations < low) | (concentrations > high)):
                    raise ConfigError(
                        "Finite-fuel cut cannot rebase surviving PMCA/ER fuel concentrations "
                        "outside the inherited [1e-9, 1e3] mM constructor range; "
                        "the source checkpoint remains unchanged"
                    )
    raw["energy_pools"] = [v for v in raw["energy_pools"] if v["cell_id"] in plan.after.cell_ids]
    for row in raw["energy_pools"]:
        row["initial_amount_fmol"] = dict(
            zip(fuel.SPECIES, before["fuel_amount"][:, cells[row["cell_id"]]].tolist(), strict=True)
        )
    retained_pools = {v["id"] for v in raw["energy_pools"]}
    raw["regeneration_ports"] = [
        v for v in raw["regeneration_ports"] if v["pool_id"] in retained_pools
    ]
    raw["stores"] = [v for v in raw["stores"] if v["cell_id"] in plan.after.cell_ids]
    for row in raw["stores"]:
        i = cells[row["cell_id"]]
        store = row["model"]
        names = [v["id"] for v in store["species"]]
        for j, compartment in enumerate(store["compartments"]):
            compartment["initial_amount_fmol"] = dict(
                zip(names, before["chemical_amount"][i, :, j].tolist(), strict=True)
            )
        store["membrane"]["initial_voltage_V"] = float(before["er_voltage"][i])
    raw["ip3_release"] = [v for v in raw["ip3_release"] if v["cell_id"] in plan.after.cell_ids]
    raw["plasma_transport"]["membranes"] = [
        v
        for v in raw["plasma_transport"]["membranes"]
        if v["membrane_id"] in plan.after.membrane_ids
    ]
    membranes = {v.id: i for i, v in enumerate(m.membranes)}
    raw["calcium_channels"] = [
        v for v in raw["calcium_channels"] if v["membrane_id"] in plan.after.membrane_ids
    ]
    for row in raw["calcium_channels"]:
        i = membranes[row["membrane_id"]]
        row["initial_gate"] = dict(
            zip(("m", "h"), np.asarray(point.state.calcium_gate)[:, i].tolist(), strict=True)
        )
    return raw, result, before


def experiment(spec, tissue, time):
    e = deepcopy(ordinary(spec).to_dict()["experiment"])
    ion = tissue["ionic"]
    owners = {
        "membrane_controls": {v["id"] for v in ion["membranes"]},
        "junction_controls": {v["id"] for v in ion["junctions"]},
        "channel_controls": {v["id"] for v in ion["channels"]},
        "pump_controls": {v["pump"]["id"] for v in ion["membranes"] if v["pump"] is not None},
        "store_controls": {v["cell_id"] for v in tissue["stores"]},
        "plasma_controls": {v["id"] for v in ion["membranes"]},
        "calcium_channel_controls": {v["id"] for v in tissue["calcium_channels"]},
        "regeneration_controls": {v["id"] for v in tissue["regeneration_ports"]},
        "network_transport_controls": {v["id"] for v in tissue["network_transport"]["routes"]},
    }
    for key, (owner, _) in CONTROL_GROUPS.items():
        e[key] = [v for v in e[key] if v[owner] in owners[key]]
    carrier = e["membrane_controls"][0]["schedule"]
    clocks = [v["time"] for v in carrier]
    times = sorted({time, *(v.time for v in spec.experiment.changes), *clocks})
    e["membrane_controls"][0]["schedule"] = [
        dict(time=t, availability=carrier[bisect_right(clocks, t) - 1]["availability"])
        for t in times
    ]
    e["observation_times"] = sorted({time, *(t for t in e["observation_times"] if t >= time)})
    return e


def histories(spec, point, plan):
    retained_routes = np.asarray(
        [
            i
            for i, v in enumerate(spec.model.network_transporters)
            if v.membrane_id in plan.after.membrane_ids
        ],
        dtype=np.int64,
    )
    removed_routes = np.asarray(
        [
            i
            for i, v in enumerate(spec.model.network_transporters)
            if v.membrane_id not in plan.after.membrane_ids
        ],
        dtype=np.int64,
    )
    retained_pools = {v.id for v in spec.model.energy_pools if v.cell_id in plan.after.cell_ids}
    retained_ports = np.asarray(
        [i for i, v in enumerate(spec.model.regeneration_ports) if v.pool_id in retained_pools],
        dtype=np.int64,
    )
    removed_ports = np.asarray(
        [i for i, v in enumerate(spec.model.regeneration_ports) if v.pool_id not in retained_pools],
        dtype=np.int64,
    )
    channels = np.asarray(
        [i for i, v in enumerate(spec.model.channels) if v.membrane_id in plan.after.membrane_ids],
        dtype=np.int64,
    )
    removed_channels = np.asarray(
        [
            i
            for i, v in enumerate(spec.model.channels)
            if v.membrane_id not in plan.after.membrane_ids
        ],
        dtype=np.int64,
    )
    indices = {
        "cell_slot": (plan.new_to_old["cell"], plan.removed["cell"]),
        "owned_cell": (plan.new_to_old["cell"], plan.removed["cell"]),
        "extracellular_slot": (plan.new_to_old["environment"], plan.removed["environment"]),
        "membrane_slot": (plan.new_to_old["membrane"], plan.removed["membrane"]),
        "edge_slot": (plan.new_to_old["edge"], plan.removed["edge"]),
        "face_slot": (np.arange(len(spec.model.faces)), np.empty(0, dtype=np.int64)),
        "channel_slot": (channels, removed_channels),
        "regeneration_slot": (retained_ports, removed_ports),
        "network_transport_slot": (retained_routes, removed_routes),
    }
    kept, removed = {}, {}
    for key, axes in active.STATE_AXES.items():
        owned = [(i, indices[k]) for i, k in enumerate(axes) if k in indices]
        if len(owned) != 1:
            raise ConfigError(
                "Transport/calcium excision requires one explicit physical owner per state"
            )
        axis, (a, b) = owned[0]
        value = np.asarray(getattr(point.state, key))
        kept[key], removed[key] = (
            np.take(value, a, axis=axis).tolist(),
            np.take(value, b, axis=axis).tolist(),
        )
    return kept, removed, channels, removed_channels


def transition_report(spec, point, result, before, after_spec=None, after_point=None):
    m, plan = spec.model, result.plan
    kept, removed = plan.new_to_old["cell"], plan.removed["cell"]
    archived, removed_history, channels, removed_channels = histories(spec, point, plan)
    removed_pools = {v.id for v in m.energy_pools if v.cell_id in result.removed_owner_ids["cell"]}
    report = dict(
        law=removal.LAW_ID,
        changed=plan.changed,
        terminal=not bool(plan.after.cell_ids),
        time_s=point.time,
        before_layout_identity=plan.before_identity,
        after_layout_identity=plan.after_identity,
        removed_cell_ids=list(result.removed_owner_ids["cell"]),
        retained_cell_ids=list(plan.after.cell_ids),
        species_ids=list(m.species_ids),
        chemical_species_ids=[v.id for v in m.stores[0].species],
        chemical_moiety_ids=list(m.stores[0].moieties),
        store_compartment_ids={
            c.id: [p.id for p in s.compartments] for c, s in zip(m.cells, m.stores, strict=True)
        },
        fuel_species_ids=list(fuel.SPECIES),
        fuel_moiety_ids=["adenylate", "phosphorus"],
        fuel_pool_cell_ids={v.id: v.cell_id for v in m.energy_pools},
        surviving_pmca_er_anchor_range_mM=list(FUEL_ANCHOR_RANGE_MM),
        removed_fuel_pool_ids=sorted(removed_pools),
        removed_regeneration_port_ids=[
            v.id for v in m.regeneration_ports if v.pool_id in removed_pools
        ],
        network_transporter_membrane_ids={v.id: v.membrane_id for v in m.network_transporters},
        removed_network_transporter_ids=[
            v.id for v in m.network_transporters if v.membrane_id not in plan.after.membrane_ids
        ],
        retained_network_transporter_ids=[
            v.id for v in m.network_transporters if v.membrane_id in plan.after.membrane_ids
        ],
        removed_fuel_amount_fmol=before["fuel_amount"][:, removed].tolist(),
        retained_fuel_amount_fmol=before["fuel_amount"][:, kept].tolist(),
        removed_fuel_moieties_fmol=before["fuel_moieties"][:, removed].tolist(),
        fuel_material_residual_fmol=result.fields["fuel_amount_fmol"].balance_residual.tolist(),
        fuel_moiety_residual_fmol=result.fields["fuel_moieties_fmol"].balance_residual.tolist(),
        removed_fuel_energy_pJ=before["fuel_energy_pJ"][removed].tolist(),
        before_fuel_energy_pJ=math.fsum(before["fuel_energy_pJ"]),
        removed_fuel_standard_energy_J_per_mol={
            v.id: v.delta_g0_J_per_mol for v in m.energy_pools if v.id in removed_pools
        },
        removed_channel_ids=[m.channels[i].id for i in removed_channels],
        retained_channel_ids=[m.channels[i].id for i in channels],
        removed_calcium_channel_ids=[
            v.id for v in m.calcium_channels if v.membrane_id not in plan.after.membrane_ids
        ],
        removed_junction_ids=list(result.removed_owner_ids["edge"]),
        removed_pump_ids=[
            v.pump.id
            for v in m.membranes
            if v.pump is not None and v.id not in plan.after.membrane_ids
        ],
        removed_plasma_route_membrane_ids=[
            v.membrane_id for v in m.plasma_routes if v.membrane_id not in plan.after.membrane_ids
        ],
        removed_store_owner_ids=[m.cells[i].id for i in removed],
        removed_chemical_amount_fmol=before["chemical_amount"][removed].tolist(),
        retained_chemical_amount_fmol=before["chemical_amount"][kept].tolist(),
        removed_chemical_species_fmol=result.fields[
            "chemical_species_fmol"
        ].removed_quantity.tolist(),
        removed_moieties_fmol=result.fields["chemical_moieties_fmol"].removed_quantity.tolist(),
        material_residual_fmol=result.fields["chemical_species_fmol"].balance_residual.tolist(),
        moiety_residual_fmol=result.fields["chemical_moieties_fmol"].balance_residual.tolist(),
        removed_net_charge_C=before["charge"][removed].tolist(),
        removed_chemical_background_C=before["chemical_background_C"][removed].tolist(),
        removed_compartment_volume_pL=[
            [v.volume_pL for v in m.stores[i].compartments] for i in removed
        ],
        removed_er_voltage_V=before["er_voltage"][removed].tolist(),
        removed_er_capacitor_energy_pJ=result.fields[
            "er_capacitor_energy_pJ"
        ].removed_quantity.tolist(),
        removed_capacitor_energy_pJ=result.fields[
            "plasma_capacitor_energy_pJ"
        ].removed_quantity.tolist(),
        removed_chemical_energy_pJ=float(result.fields["chemical_energy_pJ"].removed_total),
        before_chemical_energy_pJ=math.fsum(before["chemical_energy_pJ"])
        + before["outside_chemical_energy_pJ"],
        before_capacitor_energy_pJ=float(
            result.fields["plasma_capacitor_energy_pJ"].previous_total
        ),
        before_er_capacitor_energy_pJ=float(result.fields["er_capacitor_energy_pJ"].previous_total),
        archived_retained_state=archived,
        archived_removed_state=removed_history,
        local_ledger_fields=[k for k in active.STATE_AXES if k not in GATES],
        source_clock=dict(
            time=point.time, step_index=point.step_index, event_index=point.event_index
        ),
        history_policy=POLICIES["state_policy"],
        reference_policy=POLICIES["reference_policy"],
        physical_policy="Excise chemical stores and capacitors; no lysis or neutralization",
        amount_accounting=(
            "Chemical species are authoritative; moieties are projections and free ions are "
            "readouts, never additional material"
        ),
        background_policy=(
            "Re-express the free-ion reference anchor; preserve physical chemical fixed "
            "backgrounds within representation roundoff"
        ),
        fuel_policy=(
            "Preserve neutral transformed ATP/ADP/Pi inventories and their 1-M standard state; "
            "pump metabolic work is internal transfer, regeneration supply is external work"
        ),
        network_transport_policy=(
            "Preserve reversible route parameters, membrane owners and maintained driving work; "
            "all four route ledgers are archived and rebased; supplied work stays external, "
            "without inventing cellular ATP consumption"
        ),
        network_work_external=True,
        network_routes_store_material=False,
        pump_metabolic_work_internal=True,
        energy_claim=(
            "Chemical stores, transformed fuel, ER/plasma capacitor and electrode diagnostics; "
            "no gate or mechanical cutting energy"
        ),
    )
    if after_spec is None:
        report["continuation"] = "Terminal archive; no zero-cell calcium solver"
        return report
    after = physical(after_spec, after_point)
    for actual, expected in (
        (after["fuel_amount"], before["fuel_amount"][:, kept]),
        (after["fuel_moieties"], before["fuel_moieties"][:, kept]),
        (after["chemical_amount"], before["chemical_amount"][kept]),
        (after["free_amount"], before["free_amount"][:, kept]),
        (after["outside_amount"], before["outside_amount"]),
        (after["charge"], before["charge"][kept]),
        (after["outside_charge"], before["outside_charge"]),
        (after["er_voltage"], before["er_voltage"][kept]),
        (
            np.asarray(after_point.state.channel_gate)[:, : len(channels)],
            np.asarray(point.state.channel_gate)[:, channels],
        ),
        (
            np.asarray(after_point.state.junction_gate)[: len(plan.after.edge_ids)],
            np.asarray(point.state.junction_gate)[plan.new_to_old["edge"]],
        ),
        (
            np.asarray(after_point.state.calcium_gate)[:, : len(plan.after.membrane_ids)],
            np.asarray(point.state.calcium_gate)[:, plan.new_to_old["membrane"]],
        ),
    ):
        if not np.array_equal(actual, expected):
            raise ConfigError(
                "Transport/calcium removal changed retained amounts, voltage, charge or gates"
            )
    if plan.changed and any(
        np.any(getattr(after_point.state, k)) for k in active.STATE_AXES if k not in GATES
    ):
        raise ConfigError("Transport/calcium removal local ledgers must start at zero")
    old_background, new_background = (
        before["chemical_background_C"][kept],
        after["chemical_background_C"],
    )
    # Backgrounds are differences of large absolute ionic charges. The existing
    # segment domain separately checks small increment charge/ownership. This
    # explicit representation bound is not a relaxed physical balance budget.
    z = np.asarray([v.valence for v in m.stores[0].species])
    scale = (
        np.abs(old_background)
        + np.abs(new_background)
        + CHARGE_PER_FMOL * np.einsum("s,nsc->nc", np.abs(z), before["chemical_amount"][kept])
    )
    bound = surface_field.CHARGE_ATOL_C + 16 * np.finfo(float).eps * scale
    background_jump = new_background - old_background
    if np.any(np.abs(background_jump) > bound):
        raise ConfigError("Transport/calcium removal changed physical chemical fixed background")
    old_v = before["voltage"][plan.new_to_old["membrane"]]
    new_v = after["voltage"]
    cap = np.asarray([v.capacitance_F for v in after_spec.model.membranes])
    jump = math.fsum(0.5e12 * cap * (new_v - old_v) * (new_v + old_v))
    impulse = after["electrode"] - before["electrode"]
    work = 1e12 * float(np.dot([v.boundary_potential_V for v in m.extracellular], impulse))
    report.update(
        after_fuel_energy_pJ=math.fsum(after["fuel_energy_pJ"]),
        after_chemical_energy_pJ=math.fsum(after["chemical_energy_pJ"])
        + after["outside_chemical_energy_pJ"],
        after_er_capacitor_energy_pJ=math.fsum(
            0.5e12 * after["er_capacitance"] * after["er_voltage"] ** 2
        ),
        after_capacitor_energy_pJ=math.fsum(0.5e12 * cap * new_v**2),
        retained_capacitor_energy_jump_pJ=jump,
        electrode_charge_impulse_C=impulse.tolist(),
        held_boundary_work_impulse_pJ=work,
        unresolved_cut_energy_pJ=jump - work,
        postcut_voltage_V=new_v.tolist(),
        surviving_gates_preserved=True,
        solver_rebuilt=True,
        chemical_background_roundoff_C=background_jump.tolist(),
        chemical_background_roundoff_bound_C=bound.tolist(),
        ionic_reference_fixed_charge_before_fmol=[
            m.cells[i].fixed_charge_equivalent_fmol for i in kept
        ],
        ionic_reference_fixed_charge_after_fmol=[
            v.fixed_charge_equivalent_fmol for v in after_spec.model.cells
        ],
    )
    return report


def excise(spec, checkpoint, removed_cell_ids):
    spec = parse_spec(spec.to_dict())
    source = capture_source(spec, checkpoint)
    tissue, result, before = derive_tissue(spec, checkpoint, removed_cell_ids)
    if not result.plan.changed:
        report = transition_report(spec, checkpoint, result, before, spec, checkpoint)
        report["history_policy"] = "Unchanged complete source, gates, ledgers and clock"
        return ExcisionResult(spec, checkpoint, spec, checkpoint, report)
    if tissue is None:
        return ExcisionResult(
            spec, checkpoint, None, None, transition_report(spec, checkpoint, result, before)
        )
    raw = dict(
        schema_version=1,
        model=dict(
            id=MODEL_ID,
            tissue=tissue,
            excision=dict(POLICIES, source=source, removed_cell_ids=list(removed_cell_ids)),
        ),
        experiment=experiment(spec, tissue, checkpoint.time),
        execution=ordinary(spec).to_dict()["execution"],
    )
    after = parse_spec(raw)
    state, layout = get_model(after.model).initial_values(after)
    point = Checkpoint(
        state,
        layout,
        checkpoint.time,
        EventGrid(after).exact_index(checkpoint.time),
        event_index(after, checkpoint.time),
    )
    _point_check(after, point)
    report = transition_report(spec, checkpoint, result, before, after, point)
    return ExcisionResult(spec, checkpoint, after, point, report)
