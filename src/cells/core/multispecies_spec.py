"""Named, dimensioned one-cell assembly resolved to immutable host tuples.

This is a new production identity, not an extension of an old serialized model
or a loader for the independently frozen reference schema. No test data imports.
"""

from dataclasses import asdict

from cells.core.bioelectric_spec import positive, signed_number
from cells.core.specs import (
    MULTISPECIES_ID,
    ConfigError,
    ExperimentSpec,
    LeakChange,
    MultispeciesExecutionSpec,
    MultispeciesSpec,
    PumpChange,
    SimulationSpec,
    _fields,
    _integer,
    _number,
)


def identifier(value):
    if (
        not isinstance(value, str)
        or not value
        or not value.isascii()
        or any(not (c.isalnum() or c in "_-") for c in value)
    ):
        raise ConfigError("IDs require nonempty ASCII letters, digits, underscore or hyphen")
    return value


def aligned(mapping, ids, name, number=_number):
    _fields(mapping, set(ids), name)
    return tuple(number(mapping[s], name) for s in ids)


def to_dict(spec):
    m, e, x = spec.model, spec.experiment, spec.execution
    if type(e) is not ExperimentSpec or e.source or e.contact:
        raise ConfigError("Multispecies membrane requires only its independent membrane controls")
    if type(x) is not MultispeciesExecutionSpec or x.edge_capacity != 0:
        raise ConfigError("Multispecies membrane requires its own execution schema, without edges")
    if any(type(p) is not LeakChange for p in e.leak) or any(
        type(p) is not PumpChange for p in e.pump
    ):
        raise ConfigError("Control entries do not match their declared groups")
    ids = m.species_ids
    # Validate before dictionary construction, including Python-created specs.
    if not isinstance(ids, tuple) or not ids or any(not isinstance(s, str) for s in ids):
        raise ConfigError("Species IDs must be a nonempty immutable tuple")
    if len(set(ids)) != len(ids):
        raise ConfigError("Species IDs must be distinct")

    def mapped(values):
        if not isinstance(values, tuple) or len(values) != len(ids):
            raise ConfigError("Aligned arrays must be complete immutable species tuples")
        return dict(zip(ids, values, strict=True))

    pump = None
    if any(type(nu) is not int for nu in mapped(m.stoichiometry).values()):
        raise ConfigError("Stoichiometry must consist of integers, not booleans/floats")
    if m.pump_id is not None:
        if not isinstance(m.pump_roles, tuple) or len(m.pump_roles) != 2:
            raise ConfigError("Pump requires immutable sodium/potassium role bindings")
        stoichiometry = mapped(m.stoichiometry)
        if any(s not in ids for s in m.pump_roles) or any(
            nu != 0 for s, nu in stoichiometry.items() if s not in m.pump_roles
        ):
            raise ConfigError(
                "Pump roles/stoichiometry do not identify only their declared species"
            )
        pump = {
            "id": m.pump_id,
            "law": "nak_atp_affinity_tanh@1",
            "roles": dict(zip(("sodium", "potassium"), m.pump_roles, strict=True)),
            "stoichiometry": {s: stoichiometry[s] for s in m.pump_roles},
            "capacity_fmol_per_s": m.capacity_fmol_per_s,
            "drive_J_per_mol": m.drive_J_per_mol,
        }
    elif (
        m.pump_roles is not None
        or any(mapped(m.stoichiometry).values())
        or m.capacity_fmol_per_s != 0
        or m.drive_J_per_mol != 0
    ):
        raise ConfigError("Absent pump cannot own roles, flux, capacity or drive")
    valence = mapped(m.valence)
    execution = asdict(x)
    del execution["edge_capacity"]
    execution["material_balance_atol_fmol"] = mapped(x.material_balance_atol_fmol)
    return {
        "schema_version": 1,
        "model": {
            "id": MULTISPECIES_ID,
            "species": [{"id": s, "valence": valence[s]} for s in ids],
            "cell": {
                "id": m.cell_id,
                "volume_pL": m.volume_pL,
                "initial_amount_fmol": mapped(m.initial_amount_fmol),
                "fixed_charge_equivalent_fmol": m.fixed_charge_equivalent_fmol,
                "initial_voltage_V": m.initial_voltage_V,
            },
            "bath": {
                "id": m.bath_id,
                "temperature_K": m.temperature_K,
                "concentration_mM": mapped(m.bath_mM),
                "background_charge_mM": m.bath_background_charge_mM,
            },
            "membrane": {
                "id": m.membrane_id,
                "inside": m.cell_id,
                "outside": m.bath_id,
                "area_m2": m.area_m2,
                "specific_capacitance_F_per_m2": m.specific_capacitance_F_per_m2,
                "passive": {
                    "law": "constant_field@1",
                    "permeability_m_per_s": mapped(m.permeability_m_per_s),
                },
                "pump": pump,
            },
        },
        "experiment": {
            "end_time": e.end_time,
            "observation_times": list(e.observation_times),
            "membrane_controls": {
                "membrane_id": m.membrane_id,
                "leak": [{"time": p.time, "multipliers": mapped(p.multipliers)} for p in e.leak],
                "pump": [asdict(p) for p in e.pump],
            },
        },
        "execution": execution,
    }


def parse(data):
    root = _fields(data["model"], {"id", "species", "cell", "bath", "membrane"}, "model")
    if not isinstance(root["species"], list) or not root["species"]:
        raise ConfigError("Species must be a nonempty ordered list")
    species = [_fields(s, {"id", "valence"}, "species") for s in root["species"]]
    ids = tuple(identifier(s["id"]) for s in species)
    z = tuple(s["valence"] for s in species)
    if len(set(ids)) != len(ids) or any(
        type(v) is not int or v not in (-3, -2, -1, 1, 2, 3) for v in z
    ):
        raise ConfigError(
            "Species IDs must be unique; valence must be a nonzero integer in [-3, 3]"
        )
    cell = _fields(
        root["cell"],
        {
            "id",
            "volume_pL",
            "initial_amount_fmol",
            "fixed_charge_equivalent_fmol",
            "initial_voltage_V",
        },
        "cell",
    )
    bath = _fields(
        root["bath"], {"id", "temperature_K", "concentration_mM", "background_charge_mM"}, "bath"
    )
    membrane = _fields(
        root["membrane"],
        {"id", "inside", "outside", "area_m2", "specific_capacitance_F_per_m2", "passive", "pump"},
        "membrane",
    )
    owners = tuple(identifier(v["id"]) for v in (cell, bath, membrane))
    if membrane["inside"] != cell["id"] or membrane["outside"] != bath["id"]:
        raise ConfigError("The single membrane must face the declared cell and maintained bath")
    passive = _fields(membrane["passive"], {"law", "permeability_m_per_s"}, "passive mechanism")
    if passive["law"] != "constant_field@1":
        raise ConfigError("Unsupported passive law")
    pump, roles, pump_id = membrane["pump"], None, None
    nu, capacity, drive = (0,) * len(ids), 0.0, 0.0
    if pump is not None:
        _fields(
            pump,
            {"id", "law", "roles", "stoichiometry", "capacity_fmol_per_s", "drive_J_per_mol"},
            "pump",
        )
        pump_id = identifier(pump["id"])
        if pump["law"] != "nak_atp_affinity_tanh@1":
            raise ConfigError("Unsupported pump law")
        _fields(pump["roles"], {"sodium", "potassium"}, "pump roles")
        roles = tuple(identifier(pump["roles"][r]) for r in ("sodium", "potassium"))
        if roles[0] == roles[1] or any(s not in ids or z[ids.index(s)] != 1 for s in roles):
            raise ConfigError("Na/K pump roles require distinct monovalent positive species")
        stoichiometry = _fields(pump["stoichiometry"], set(roles), "pump stoichiometry")
        if any(
            type(stoichiometry[s]) is not int or stoichiometry[s] != v
            for s, v in zip(roles, (-3, 2), strict=True)
        ):
            raise ConfigError("Na/K pump requires exactly the declared -3/+2 role coefficients")
        nu = tuple(stoichiometry.get(s, 0) for s in ids)
        capacity = _number(pump["capacity_fmol_per_s"], "pump capacity")
        drive = signed_number(pump["drive_J_per_mol"], "pump drive")
        owners += (pump_id,)
    if len(set(owners)) != len(owners):
        raise ConfigError("Cell, bath, membrane and pump IDs must be distinct")
    model = MultispeciesSpec(
        ids,
        z,
        *owners[:3],
        positive(cell["volume_pL"], "volume"),
        positive(membrane["area_m2"], "area"),
        positive(membrane["specific_capacitance_F_per_m2"], "specific capacitance"),
        positive(bath["temperature_K"], "temperature"),
        aligned(cell["initial_amount_fmol"], ids, "initial amounts", positive),
        aligned(bath["concentration_mM"], ids, "bath concentrations", positive),
        aligned(passive["permeability_m_per_s"], ids, "permeabilities"),
        signed_number(cell["fixed_charge_equivalent_fmol"], "fixed charge"),
        signed_number(cell["initial_voltage_V"], "initial voltage"),
        signed_number(bath["background_charge_mM"], "bath background charge"),
        pump_id,
        roles,
        nu,
        capacity,
        drive,
    )
    e = _fields(
        data["experiment"], {"end_time", "observation_times", "membrane_controls"}, "experiment"
    )
    end = positive(e["end_time"], "end time")
    controls = _fields(e["membrane_controls"], {"membrane_id", "leak", "pump"}, "membrane controls")
    if controls["membrane_id"] != model.membrane_id:
        raise ConfigError("Controls must identify the declared membrane")
    groups = []
    for name, key in (("leak", "multipliers"), ("pump", "multiplier")):
        if not isinstance(controls[name], list) or not controls[name]:
            raise ConfigError("Both membrane control groups require nonempty schedules")
        changes = []
        for item in controls[name]:
            _fields(item, {"time", key}, f"{name} control")
            time = _number(item["time"], "control time")
            values = (
                aligned(item[key], ids, "leak multipliers")
                if name == "leak"
                else (_number(item[key], "pump multiplier"),)
            )
            if any(v > 1 for v in values):
                raise ConfigError("Membrane multipliers must lie in [0, 1]")
            if time > end or (changes and time <= changes[-1].time):
                raise ConfigError("Control times must strictly increase within the horizon")
            changes.append(
                LeakChange(time, values) if name == "leak" else PumpChange(time, values[0])
            )
        if changes[0].time != 0:
            raise ConfigError("Each independent control group must start explicitly at zero")
        groups.append(tuple(changes))
    if not isinstance(e["observation_times"], list) or not e["observation_times"]:
        raise ConfigError("Observation times must be a nonempty list")
    times = tuple(_number(t, "observation time") for t in e["observation_times"])
    if any(t > end for t in times) or any(b <= a for a, b in zip(times, times[1:], strict=False)):
        raise ConfigError("Observation times must strictly increase within the horizon")
    x = _fields(
        data["execution"],
        set(MultispeciesExecutionSpec.__dataclass_fields__) - {"edge_capacity"},
        "execution",
    )
    for key, required in (("backend", "cpu"), ("precision", "float64"), ("solver", "rk4")):
        if x[key] != required:
            raise ConfigError(f"This version requires {key}={required!r}")
    if type(x["jit"]) is not bool:
        raise ConfigError("jit must be a boolean")
    execution = MultispeciesExecutionSpec(
        positive(x["dt"], "dt"),
        _integer(x["capacity"], "capacity"),
        x["jit"],
        _integer(x["max_steps"], "max_steps"),
        _integer(x["max_trace_bytes"], "max_trace_bytes", maximum=2**53 - 1),
        membrane_capacity=_integer(x["membrane_capacity"], "membrane capacity"),
        material_balance_atol_fmol=aligned(
            x["material_balance_atol_fmol"], ids, "material balance tolerance", positive
        ),
    )
    # Derived physical preflight precedes every capacity-sized allocation.
    from cells.models.multispecies_membrane import check_definition

    check_definition(model)
    return SimulationSpec(
        model, ExperimentSpec(end, (), times, leak=groups[0], pump=groups[1]), execution
    )
