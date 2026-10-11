"""Strict finite-inventory assembly. No maintained-bath conversion or reference imports."""

from dataclasses import asdict

from cells.core.bioelectric_spec import positive, signed_number
from cells.core.multispecies_spec import aligned, identifier
from cells.core.physical_ionic_graph_spec import GATE_LAW, _controls, _tuple
from cells.core.specs import (
    FINITE_EXTRACELLULAR_ID,
    ChannelChange,
    ChannelSpec,
    ConfigError,
    ContactChange,
    FiniteCompartmentSpec,
    FiniteExtracellularExecutionSpec,
    FiniteExtracellularSpec,
    FiniteMembraneSpec,
    IonicJunctionSpec,
    LeakChange,
    MembraneSchedule,
    PhysicalIonicGraphExperimentSpec,
    PumpChange,
    SimulationSpec,
    _fields,
    _integer,
    _number,
)
from cells.core.voltage_gated_spec import fraction
from cells.processes.voltage_gates import LAW_ID


def to_dict(spec):
    return assembly_to_dict(spec, FINITE_EXTRACELLULAR_ID, FiniteMembraneSpec, pump_to_dict)


def pump_to_dict(p, ids):
    if type(p.stoichiometry) is not tuple or len(p.stoichiometry) != len(ids):
        raise ConfigError("Species vectors must be complete immutable tuples")
    nu = dict(zip(ids, p.stoichiometry, strict=True))
    if any(type(v) is not int for v in nu.values()):
        raise ConfigError("Pump stoichiometry must be integer")
    if p.pump_id is not None:
        _tuple(p.pump_roles, str, "pump roles", size=2)
        if any(s not in ids for s in p.pump_roles) or any(
            v for s, v in nu.items() if s not in p.pump_roles
        ):
            raise ConfigError("Pump coefficients must bind only its roles")
        return {
            "id": p.pump_id,
            "law": "nak_atp_affinity_tanh@1",
            "roles": dict(zip(("sodium", "potassium"), p.pump_roles, strict=True)),
            "stoichiometry": {s: nu[s] for s in p.pump_roles},
            "capacity_fmol_per_s": p.capacity_fmol_per_s,
            "drive_J_per_mol": p.drive_J_per_mol,
        }
    if (
        p.pump_roles is not None
        or any(nu.values())
        or p.capacity_fmol_per_s != 0
        or p.drive_J_per_mol != 0
    ):
        raise ConfigError("Absent pump cannot own coefficients or roles")
    return None


def junction_to_dict(p, ids):
    values = {}
    for key in ("permeability_m_per_s", "residual_fraction"):
        value = getattr(p, key)
        if type(value) is not tuple or len(value) != len(ids):
            raise ConfigError("Species vectors must be complete immutable tuples")
        values[key] = dict(zip(ids, value, strict=True))
    return {
        "id": p.id,
        "from_cell": p.from_cell,
        "to_cell": p.to_cell,
        "area_m2": p.area_m2,
        **values,
        "gate": {
            k: getattr(p, k)
            for k in ("law", "sensitivity_per_V", "half_voltage_V", "tau_s", "initial_gate")
        },
    }


def assembly_to_dict(
    spec,
    model_id,
    membrane_type,
    serialize_pump,
    *,
    junction_type=IonicJunctionSpec,
    serialize_junction=junction_to_dict,
):
    """Shared geometry/controls; process contracts are supplied by the composing model."""
    m, e, x = spec.model, spec.experiment, spec.execution
    if (
        type(e) is not PhysicalIonicGraphExperimentSpec
        or type(x) is not FiniteExtracellularExecutionSpec
    ):
        raise ConfigError("Finite extracellular model requires its explicit execution and controls")
    ids = m.species_ids
    _tuple(ids, str, "species IDs")
    if not ids or len(set(ids)) != len(ids):
        raise ConfigError("Require nonempty distinct species IDs")

    def mapped(value):
        if type(value) is not tuple or len(value) != len(ids):
            raise ConfigError("Species vectors must be complete immutable tuples")
        return dict(zip(ids, value, strict=True))

    def compartment(c):
        if type(c) is not FiniteCompartmentSpec:
            raise ConfigError("Require an explicit finite compartment")
        return asdict(c) | {"initial_amount_fmol": mapped(c.initial_amount_fmol)}

    _tuple(m.cells, FiniteCompartmentSpec, "cells")
    _tuple(m.membranes, membrane_type, "membranes", size=len(m.cells))
    _tuple(m.channels, ChannelSpec, "channels")
    _tuple(m.junctions, junction_type, "junctions")
    _tuple(e.membranes, MembraneSchedule, "membrane schedules", size=len(m.membranes))
    channel_map = {c.membrane_id: c for c in m.channels}
    if (
        len(channel_map) != len(m.channels)
        or tuple(channel_map[p.id] for p in m.membranes if p.id in channel_map) != m.channels
    ):
        raise ConfigError("Channels must bind unique membranes in owner order")
    local, schedules = [], []
    for cell, p, schedule in zip(m.cells, m.membranes, e.membranes, strict=True):
        _tuple(schedule.leak, LeakChange, "leak schedule")
        _tuple(schedule.pump, PumpChange, "pump schedule")
        pump = serialize_pump(p, ids)
        c = channel_map.get(p.id)
        if c is not None:
            if type(c.initial_gate) is not tuple or len(c.initial_gate) != 2:
                raise ConfigError("Channel requires an immutable m/h pair")
            c = asdict(c) | {"initial_gate": dict(zip(("m", "h"), c.initial_gate, strict=True))}
        local.append(
            {
                "cell": compartment(cell) | {"initial_voltage_V": p.initial_voltage_V},
                "membrane": {
                    "id": p.id,
                    "inside": p.inside,
                    "outside": p.outside,
                    "area_m2": p.area_m2,
                    "specific_capacitance_F_per_m2": p.specific_capacitance_F_per_m2,
                    "passive": {
                        "law": "constant_field@1",
                        "permeability_m_per_s": mapped(p.permeability_m_per_s),
                    },
                    "pump": pump,
                },
                "channel": c,
            }
        )
        schedules.append(
            {
                "membrane_id": p.id,
                "leak": [
                    {"time": c.time, "multipliers": mapped(c.multipliers)} for c in schedule.leak
                ],
                "pump": [asdict(c) for c in schedule.pump],
            }
        )
    controls = {}
    for name, objects, groups, kind in (
        ("channel", m.channels, e.channels, ChannelChange),
        ("junction", m.junctions, e.junctions, ContactChange),
    ):
        _tuple(groups, tuple, name + " schedules", size=len(objects))
        for group in groups:
            _tuple(group, kind, name + " changes")
        controls[name + "_controls"] = [
            {name + "_id": obj.id, "schedule": [asdict(c) for c in group]}
            for obj, group in zip(objects, groups, strict=True)
        ]
    edges = [serialize_junction(p, ids) for p in m.junctions]
    z = mapped(m.valence)
    return {
        "schema_version": 1,
        "model": {
            "id": model_id,
            "species": [{"id": s, "valence": z[s]} for s in ids],
            "temperature_K": m.temperature_K,
            "extracellular": compartment(m.extracellular),
            "cells": local,
            "junctions": edges,
        },
        "experiment": {
            "end_time": e.end_time,
            "observation_times": list(e.observation_times),
            "membrane_controls": schedules,
            **controls,
        },
        "execution": asdict(x)
        | {"material_balance_atol_fmol": mapped(x.material_balance_atol_fmol)},
    }


def parse(data):
    from cells.models.finite_extracellular import check_definition

    return parse_assembly(data, FiniteExtracellularSpec, parse_membrane, check_definition)


def parse_membrane(p, cell, outside, ids, z, voltage):
    pump, roles, pid, nu, capacity, drive = p["pump"], None, None, (0,) * len(ids), 0.0, 0.0
    if pump is not None:
        _fields(
            pump,
            {"id", "law", "roles", "stoichiometry", "capacity_fmol_per_s", "drive_J_per_mol"},
            "pump",
        )
        pid = identifier(pump["id"])
        _fields(pump["roles"], {"sodium", "potassium"}, "pump roles")
        roles = tuple(identifier(pump["roles"][r]) for r in ("sodium", "potassium"))
        if (
            pump["law"] != "nak_atp_affinity_tanh@1"
            or roles[0] == roles[1]
            or any(s not in ids or z[ids.index(s)] != 1 for s in roles)
        ):
            raise ConfigError("Na/K pump requires its supported law and distinct +1 roles")
        coeff = _fields(pump["stoichiometry"], set(roles), "pump coefficients")
        if any(
            type(coeff[s]) is not int or coeff[s] != v for s, v in zip(roles, (-3, 2), strict=True)
        ):
            raise ConfigError("Na/K pump requires exactly -3/+2 coefficients")
        nu = tuple(coeff.get(s, 0) for s in ids)
        capacity = _number(pump["capacity_fmol_per_s"], "pump capacity")
        drive = signed_number(pump["drive_J_per_mol"], "pump drive")
    return FiniteMembraneSpec(
        identifier(p["id"]),
        cell.id,
        outside.id,
        positive(p["area_m2"], "area"),
        positive(p["specific_capacitance_F_per_m2"], "specific capacitance"),
        aligned(p["passive"]["permeability_m_per_s"], ids, "permeability"),
        signed_number(voltage, "initial voltage"),
        pid,
        roles,
        nu,
        capacity,
        drive,
    ), pid


def parse_junction(p, ids):
    _fields(
        p,
        {
            "id",
            "from_cell",
            "to_cell",
            "area_m2",
            "permeability_m_per_s",
            "residual_fraction",
            "gate",
        },
        "junction",
    )
    g = _fields(
        p["gate"],
        {"law", "sensitivity_per_V", "half_voltage_V", "tau_s", "initial_gate"},
        "junction gate",
    )
    edge = IonicJunctionSpec(
        *(identifier(p[k]) for k in ("id", "from_cell", "to_cell")),
        positive(p["area_m2"], "junction area"),
        aligned(p["permeability_m_per_s"], ids, "junction permeability"),
        aligned(p["residual_fraction"], ids, "junction residual", fraction),
        g["law"],
        positive(g["sensitivity_per_V"], "junction sensitivity"),
        _number(g["half_voltage_V"], "half voltage"),
        positive(g["tau_s"], "junction tau"),
        fraction(g["initial_gate"], "junction initial gate"),
    )
    if edge.law != GATE_LAW:
        raise ConfigError("Junction needs supported law")
    return edge


def parse_assembly(
    data,
    model_type,
    bind_membrane,
    check_definition,
    *,
    bind_junction=parse_junction,
    backends=None,
    outside_compartments=(),
):
    """Validate shared finite ownership without translating one pump law into another."""
    root = _fields(
        data["model"],
        {"id", "species", "temperature_K", "extracellular", "cells", "junctions"},
        "model",
    )
    if type(root["species"]) is not list or not root["species"]:
        raise ConfigError("Species must be an explicit nonempty ordered list")
    species = [_fields(s, {"id", "valence"}, "species") for s in root["species"]]
    ids, z = tuple(identifier(s["id"]) for s in species), tuple(s["valence"] for s in species)
    if len(set(ids)) != len(ids) or any(
        type(v) is not int or v not in (-3, -2, -1, 1, 2, 3) for v in z
    ):
        raise ConfigError("Require unique species and nonzero integer valence in [-3, 3]")
    temperature = positive(root["temperature_K"], "temperature")
    e = _fields(
        data["experiment"],
        {
            "end_time",
            "observation_times",
            "membrane_controls",
            "channel_controls",
            "junction_controls",
        },
        "experiment",
    )
    end = positive(e["end_time"], "end time")
    if type(e["observation_times"]) is not list or not e["observation_times"]:
        raise ConfigError("Observation times must be a nonempty list")
    times = tuple(_number(t, "observation time") for t in e["observation_times"])
    if any(t > end for t in times) or any(b <= a for a, b in zip(times, times[1:], strict=False)):
        raise ConfigError("Observation times must strictly increase within the horizon")
    controls = {
        name: _controls(e[name + "_controls"], name + "_id", fields)
        for name, fields in (
            ("membrane", ("leak", "pump")),
            ("channel", ("schedule",)),
            ("junction", ("schedule",)),
        )
    }

    def schedule(entries, key, kind, number):
        if type(entries) is not list or not entries:
            raise ConfigError("Every control requires an explicit nonempty schedule")
        changes = []
        for p in entries:
            _fields(p, {"time", key}, "control change")
            time = _number(p["time"], "control time")
            if time > end or (changes and time <= changes[-1].time):
                raise ConfigError("Control times must strictly increase within the horizon")
            changes.append(kind(time, number(p[key], key)))
        if changes[0].time != 0:
            raise ConfigError("Every control schedule must start explicitly at zero")
        return tuple(changes)

    def compartment(raw, *, cell=False):
        _fields(
            raw,
            {"id", "volume_pL", "initial_amount_fmol", "fixed_charge_equivalent_fmol"}
            | ({"initial_voltage_V"} if cell else set()),
            "compartment",
        )
        return FiniteCompartmentSpec(
            identifier(raw["id"]),
            positive(raw["volume_pL"], "volume"),
            aligned(raw["initial_amount_fmol"], ids, "initial amounts", positive),
            signed_number(raw["fixed_charge_equivalent_fmol"], "fixed charge"),
        )

    outside = compartment(root["extracellular"])
    outside_by_id = {c.id: c for c in (outside, *outside_compartments)}
    if len(outside_by_id) != 1 + len(outside_compartments):
        raise ConfigError("Outside owners must be distinct")
    if type(root["cells"]) is not list or not root["cells"] or type(root["junctions"]) is not list:
        raise ConfigError("Require a nonempty cell list and an explicit junction list")
    cells, membranes, channels, edges, ms, cs, es = [], [], [], [], [], [], []
    owners = list(outside_by_id)
    for entry in root["cells"]:
        _fields(entry, {"cell", "membrane", "channel"}, "local cell")
        cell = compartment(entry["cell"], cell=True)
        p = _fields(
            entry["membrane"],
            {
                "id",
                "inside",
                "outside",
                "area_m2",
                "specific_capacitance_F_per_m2",
                "passive",
                "pump",
            },
            "membrane",
        )
        mid = identifier(p["id"])
        if (
            p["inside"] != cell.id
            or type(p["outside"]) is not str
            or p["outside"] not in outside_by_id
        ):
            raise ConfigError("Membrane must face its cell and a declared finite outside")
        passive = _fields(p["passive"], {"law", "permeability_m_per_s"}, "passive mechanism")
        if passive["law"] != "constant_field@1":
            raise ConfigError("Unsupported passive law")
        membrane, pid = bind_membrane(
            p, cell, outside_by_id[p["outside"]], ids, z, entry["cell"]["initial_voltage_V"]
        )
        if pid is not None:
            owners.append(pid)
        if mid not in controls["membrane"]:
            raise ConfigError("Every membrane requires identified controls")
        group = controls["membrane"][mid]
        ms.append(
            MembraneSchedule(
                schedule(
                    group["leak"],
                    "multipliers",
                    LeakChange,
                    lambda v, k: aligned(v, ids, k, fraction),
                ),
                schedule(group["pump"], "multiplier", PumpChange, fraction),
            )
        )
        c = entry["channel"]
        if c is not None:
            _fields(c, set(ChannelSpec.__dataclass_fields__), "channel")
            g = _fields(c["initial_gate"], {"m", "h"}, "channel initial gate")
            channel = ChannelSpec(
                identifier(c["id"]),
                identifier(c["membrane_id"]),
                identifier(c["species_id"]),
                c["kinetic_law"],
                _number(c["max_permeability_m_per_s"], "channel permeability"),
                _number(c["abundance"], "channel abundance"),
                (fraction(g["m"], "m"), fraction(g["h"], "h")),
            )
            if (
                channel.membrane_id != mid
                or channel.kinetic_law != LAW_ID
                or channel.species_id not in ids
                or z[ids.index(channel.species_id)] != 1
            ):
                raise ConfigError(
                    "Channel must bind its declared membrane, supported law and +1 species"
                )
            if channel.id not in controls["channel"]:
                raise ConfigError("Every channel requires identified controls")
            cs.append(
                schedule(
                    controls["channel"][channel.id]["schedule"],
                    "availability",
                    ChannelChange,
                    fraction,
                )
            )
            channels.append(channel)
            owners.append(channel.id)
        cells.append(cell)
        membranes.append(membrane)
        owners.extend((cell.id, mid))
    cell_ids, pairs = [c.id for c in cells], set()
    for p in root["junctions"]:
        edge = bind_junction(p, ids)
        pair = frozenset((edge.from_cell, edge.to_cell))
        if len(pair) != 2 or not pair <= set(cell_ids) or pair in pairs:
            raise ConfigError(
                "Junction needs supported law, distinct inside endpoints and a unique physical edge"
            )
        pairs.add(pair)
        if edge.id not in controls["junction"]:
            raise ConfigError("Every junction requires identified controls")
        es.append(
            schedule(
                controls["junction"][edge.id]["schedule"], "open_fraction", ContactChange, fraction
            )
        )
        owners.append(edge.id)
        edges.append(edge)
    if len(set(owners)) != len(owners) or any(
        set(controls[name]) != {p.id for p in objects}
        for name, objects in (("membrane", membranes), ("channel", channels), ("junction", edges))
    ):
        raise ConfigError("Require globally unique physical IDs and exact control owners")
    x = _fields(
        data["execution"], set(FiniteExtracellularExecutionSpec.__dataclass_fields__), "execution"
    )
    if backends is None:
        backends = ("cpu", "gpu") if data["model"]["id"] == "finite_extracellular@2" else ("cpu",)
    if x["backend"] not in backends:
        raise ConfigError(f"This model requires backend in {backends}")
    if x["backend"] == "gpu" and x["jit"] is not True:
        raise ConfigError("GPU execution requires jit=True")
    for key, required in (("precision", "float64"), ("solver", "rk4")):
        if x[key] != required:
            raise ConfigError(f"This version requires {key}={required!r}")
    if type(x["jit"]) is not bool:
        raise ConfigError("jit must be a boolean")
    execution = FiniteExtracellularExecutionSpec(
        backend=x["backend"],
        dt=positive(x["dt"], "dt"),
        jit=x["jit"],
        max_steps=_integer(x["max_steps"], "max_steps"),
        max_trace_bytes=_integer(x["max_trace_bytes"], "max_trace_bytes", maximum=2**53 - 1),
        material_balance_atol_fmol=aligned(
            x["material_balance_atol_fmol"], ids, "material tolerance", positive
        ),
        **{
            key: _integer(x[key], key, minimum=n)
            for key, n in (
                ("capacity", len(cells)),
                ("membrane_capacity", len(membranes)),
                ("channel_capacity", len(channels)),
                ("edge_capacity", len(edges)),
                ("extracellular_capacity", 1),
            )
        },
    )
    model = model_type(
        ids, z, temperature, outside, tuple(cells), tuple(membranes), tuple(channels), tuple(edges)
    )
    try:
        check_definition(model)
    except ConfigError:
        raise
    except (ArithmeticError, ValueError) as error:
        raise ConfigError("Derived finite-compartment arithmetic exceeds float64") from error
    return SimulationSpec(
        model,
        PhysicalIonicGraphExperimentSpec(end, times, tuple(ms), tuple(cs), tuple(es)),
        execution,
    )
