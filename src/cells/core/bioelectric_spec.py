"""Strict host schema for one fixed-volume cell, membrane, and maintained bath.

Kept apart from the older schemas so their serialized meaning stays unchanged.
No model name or assay outcome selects numerical behaviour.
"""

from dataclasses import asdict

from cells.core.specs import (
    BIOELECTRIC_ID,
    BathSpec,
    BioelectricSpec,
    ConfigError,
    ExecutionSpec,
    ExperimentSpec,
    LeakChange,
    MembraneSpec,
    PumpChange,
    SimulationSpec,
    _fields,
    _integer,
    _number,
    _vector,
)

SPECIES = ("Na", "K", "Cl")
UNITS = {
    "amount": "fmol",
    "volume": "pL",
    "time": "s",
    "concentration": "mM",
    "voltage": "V",
    "area": "m2",
    "permeability": "m/s",
    "specific_capacitance": "F/m2",
    "temperature": "K",
    "chemical_drive": "J/mol_cycles",
    "pump_capacity": "fmol_cycles/s",
}


def signed_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{name} must be a finite signed number")
    result = _number(abs(value), name)
    return -result if value < 0 else result


def positive(value, name):
    return _number(value, name, positive=True)


def to_dict(spec):
    m, e, x = spec.model, spec.experiment, spec.execution
    if e.source or e.contact or x.edge_capacity != 0:
        raise ConfigError("Bioelectric cell accepts membrane controls, not source/contact controls")
    if any(type(p) is not LeakChange for p in e.leak) or any(
        type(p) is not PumpChange for p in e.pump
    ):
        raise ConfigError("Membrane control entries do not match their groups")
    membrane, bath = asdict(m.membrane), asdict(m.bath)
    membrane["permeability_m_per_s"] = list(m.membrane.permeability_m_per_s)
    bath.update(kind="clamped", concentration_mM=list(m.bath.concentration_mM))
    execution = asdict(x)
    del execution["edge_capacity"]
    return {
        "schema_version": 1,
        "model": {
            "id": BIOELECTRIC_ID,
            "species": list(SPECIES),
            "units": dict(UNITS),
            "population": {"count": 1, "cell_id": m.cell_id},
            "initial_state": {
                "amount_fmol": list(m.initial_amount),
                "volume_pL": m.volume_pL,
                "voltage_V": m.initial_voltage_V,
            },
            "parameters": {"membrane": membrane, "bath": bath},
        },
        "experiment": {
            "end_time": e.end_time,
            "source": {"kind": "none"},
            "observation_times": list(e.observation_times),
            "membrane_controls": {
                "leak": {
                    "kind": "prescribed_leak_multipliers",
                    "membrane_id": m.membrane.membrane_id,
                    "species": list(SPECIES),
                    "schedule": [
                        {"time": p.time, "multipliers": list(p.multipliers)} for p in e.leak
                    ],
                },
                "pump": {
                    "kind": "prescribed_pump_multiplier",
                    "membrane_id": m.membrane.membrane_id,
                    "schedule": [asdict(p) for p in e.pump],
                },
            },
        },
        "execution": execution,
    }


def parse(data):
    m = _fields(
        data["model"],
        {"id", "species", "units", "population", "initial_state", "parameters"},
        "model",
    )
    if m["species"] != list(SPECIES) or m["units"] != UNITS:
        raise ConfigError("Bioelectric cell requires Na/K/Cl order and its exact physical units")
    pop = _fields(m["population"], {"count", "cell_id"}, "population")
    if type(pop["count"]) is not int or pop["count"] != 1:
        raise ConfigError("This closure supports exactly one active cell and membrane")
    cell_id = _integer(pop["cell_id"], "cell ID")
    initial = _fields(
        m["initial_state"], {"amount_fmol", "volume_pL", "voltage_V"}, "initial_state"
    )
    params = _fields(m["parameters"], {"membrane", "bath"}, "parameters")
    membrane = _fields(params["membrane"], set(MembraneSpec.__dataclass_fields__), "membrane")
    bath = _fields(params["bath"], {*BathSpec.__dataclass_fields__, "kind"}, "bath")
    if bath["kind"] != "clamped" or signed_number(bath["potential_V"], "bath potential") != 0:
        raise ConfigError("This electrical closure requires a clamped bath at potential zero")
    b = BathSpec(
        _integer(bath["bath_id"], "bath ID"),
        _vector(bath["concentration_mM"], 3, "bath concentration", positive),
        0.0,
        positive(bath["temperature_K"], "temperature"),
        signed_number(bath["atp_free_energy_J_per_mol"], "ATP free energy"),
    )
    a = MembraneSpec(
        _integer(membrane["membrane_id"], "membrane ID"),
        _integer(membrane["owner_cell_id"], "membrane owner ID"),
        _integer(membrane["bath_id"], "facing bath ID"),
        positive(membrane["area_m2"], "area"),
        positive(membrane["specific_capacitance_F_per_m2"], "specific capacitance"),
        _vector(membrane["permeability_m_per_s"], 3, "permeabilities"),
        _number(membrane["pump_capacity_fmol_per_s"], "pump capacity"),
    )
    if a.owner_cell_id != cell_id or a.bath_id != b.bath_id:
        raise ConfigError("Membrane endpoints must identify the declared cell and bath")
    model = BioelectricSpec(
        cell_id,
        _vector(initial["amount_fmol"], 3, "initial amounts", positive),
        positive(initial["volume_pL"], "volume"),
        signed_number(initial["voltage_V"], "initial voltage"),
        a,
        b,
    )
    e = _fields(
        data["experiment"],
        {"end_time", "source", "observation_times", "membrane_controls"},
        "experiment",
    )
    if _fields(e["source"], {"kind"}, "source")["kind"] != "none":
        raise ConfigError("This model requires source.kind='none'")
    end = positive(e["end_time"], "end time")
    controls = _fields(e["membrane_controls"], {"leak", "pump"}, "membrane controls")
    groups = []
    for name, kind in (
        ("leak", "prescribed_leak_multipliers"),
        ("pump", "prescribed_pump_multiplier"),
    ):
        fields = {"kind", "membrane_id", "schedule"} | ({"species"} if name == "leak" else set())
        group = _fields(controls[name], fields, f"{name} control")
        if (
            group["kind"] != kind
            or _integer(group["membrane_id"], "control membrane ID") != a.membrane_id
        ):
            raise ConfigError("Control kind/endpoint must match the declared membrane")
        order = list(range(3))
        if name == "leak":
            species = _vector(group["species"], 3, "control species", lambda v, _: v)
            if any(not isinstance(s, str) for s in species) or set(species) != set(SPECIES):
                raise ConfigError("Leak control must name each declared ion exactly once")
            order = [species.index(s) for s in SPECIES]
        if not isinstance(group["schedule"], list) or not group["schedule"]:
            raise ConfigError(f"{name} schedule must be a nonempty list")
        changes = []
        value_key = "multipliers" if name == "leak" else "multiplier"
        for item in group["schedule"]:
            _fields(item, {"time", value_key}, f"{name} change")
            time = _number(item["time"], "control time")
            values = (
                _vector(item[value_key], 3, "leak multipliers")
                if name == "leak"
                else (_number(item[value_key], "pump multiplier"),)
            )
            if any(v > 1 for v in values):
                raise ConfigError("Membrane multipliers must lie in [0, 1]")
            if time > end or (changes and time <= changes[-1].time):
                raise ConfigError("Control times must increase strictly within the horizon")
            changes.append(
                LeakChange(time, tuple(values[i] for i in order))
                if name == "leak"
                else PumpChange(time, values[0])
            )
        if changes[0].time != 0:
            raise ConfigError("Each control group must explicitly start at time zero")
        groups.append(tuple(changes))
    if not isinstance(e["observation_times"], list) or not e["observation_times"]:
        raise ConfigError("observation_times must be a nonempty list")
    times = tuple(_number(t, "observation time") for t in e["observation_times"])
    if any(t > end for t in times) or any(b <= a for a, b in zip(times, times[1:], strict=False)):
        raise ConfigError("Observation times must increase strictly within the horizon")
    x = _fields(
        data["execution"], set(ExecutionSpec.__dataclass_fields__) - {"edge_capacity"}, "execution"
    )
    for key, required in (("backend", "cpu"), ("precision", "float64"), ("solver", "rk4")):
        if x[key] != required:
            raise ConfigError(f"This version requires {key}={required!r}")
    if type(x["jit"]) is not bool:
        raise ConfigError("jit must be a boolean")
    execution = ExecutionSpec(
        positive(x["dt"], "dt"),
        _integer(x["capacity"], "capacity"),
        x["jit"],
        _integer(x["max_steps"], "max_steps"),
        _integer(x["max_trace_bytes"], "max_trace_bytes", maximum=2**53 - 1),
        membrane_capacity=_integer(x["membrane_capacity"], "membrane capacity"),
    )
    # Scalar derived-domain validation, before capacity-sized allocations.
    from cells.models.bioelectric_cell import check_definition

    check_definition(model)
    return SimulationSpec(
        model, ExperimentSpec(end, (), times, leak=groups[0], pump=groups[1]), execution
    )
