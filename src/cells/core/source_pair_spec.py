"""Strict nominal-coordinate pair schema; no source assay names or implicit units."""

from dataclasses import asdict

from cells.core.specs import (
    SOURCE_PAIR_ID,
    ConfigError,
    ContactChange,
    ExecutionSpec,
    LeakChange,
    MembraneSchedule,
    PumpChange,
    RoutePairExperimentSpec,
    SimulationSpec,
    SourceContactSpec,
    SourceMembraneSpec,
    SourcePairSpec,
    _fields,
    _integer,
    _number,
    _vector,
)

PARAMETER_SET = "bitsey-b2cb370-emt-pair-simple"
IONS = ("Na", "K", "Cl")
REGULATION = ("miR200_total", "Zeb_mRNA_total", "ZEB_prot")
CONTEXT = ("P", "snail", "ST")
ROUTES = ("ions", "mirna")
UNITS = {
    "time": "bitsey_time_unit",
    "ionic_concentration": "mol/m3",
    "regulatory_coordinate": "bitsey_scaled_coordinate",
    "voltage": "V",
    "length": "m",
    "diffusion": "m2/bitsey_time_unit",
}


def bounded(value, name, lower=0, upper=1000):
    value = _number(value, name)
    if not lower <= value <= upper:
        raise ConfigError(f"{name} must lie in [{lower}, {upper}]")
    return value


def to_dict(spec):
    m, e, x = spec.model, spec.experiment, spec.execution
    if not isinstance(e, RoutePairExperimentSpec) or len(e.membranes) != 2 or len(e.contacts) != 2:
        raise ConfigError("Source pair requires two membrane groups and two independent routes")
    if len(m.membranes) != 2:
        raise ConfigError("Source pair requires two declared membranes")
    if (
        any(type(p) is not LeakChange for g in e.membranes for p in g.leak)
        or any(type(p) is not PumpChange for g in e.membranes for p in g.pump)
        or any(type(p) is not ContactChange for g in e.contacts for p in g)
    ):
        raise ConfigError("Control entry types must match their declared groups")
    contact = asdict(m.contact)
    contact["ion_diffusion"] = list(m.contact.ion_diffusion)
    return {
        "schema_version": 1,
        "model": {
            "id": SOURCE_PAIR_ID,
            "units": dict(UNITS),
            "ionic_species": list(IONS),
            "regulatory_coordinates": list(REGULATION),
            "population": {"count": 2, "cell_ids": list(m.cell_ids)},
            "initial_state": {
                "ions": [list(r) for r in m.initial_ions],
                "regulation": [list(r) for r in m.initial_regulation],
            },
            "parameters": {
                "parameter_set": PARAMETER_SET,
                "context": {name: list(row) for name, row in zip(CONTEXT, m.context, strict=True)},
                "membranes": [asdict(a) | {"diffusion": list(a.diffusion)} for a in m.membranes],
                "bath": {"kind": "clamped", "bath_id": m.bath_id, "ions": list(m.bath_ions)},
                "contact": contact,
            },
        },
        "experiment": {
            "end_time": e.end_time,
            "source": {"kind": "none"},
            "observation_times": list(e.observation_times),
            "membrane_controls": [
                {
                    "membrane_id": a.membrane_id,
                    "leak": [{"time": p.time, "multipliers": list(p.multipliers)} for p in g.leak],
                    "pump": [asdict(p) for p in g.pump],
                }
                for a, g in zip(m.membranes, e.membranes, strict=True)
            ],
            "contact_controls": [
                {
                    "route": route,
                    "contact_id": m.contact.contact_id,
                    "schedule": [{"time": p.time, "multiplier": p.open_fraction} for p in group],
                }
                for route, group in zip(ROUTES, e.contacts, strict=True)
            ],
        },
        "execution": asdict(x),
    }


def schedule(entries, end, *, leak=False, contact=False):
    if not isinstance(entries, list) or not entries:
        raise ConfigError("Each control group requires a nonempty schedule")
    result = []
    key = "multipliers" if leak else "multiplier"
    for entry in entries:
        _fields(entry, {"time", key}, "control change")
        time = _number(entry["time"], "control time")
        if time > end or (result and time <= result[-1].time):
            raise ConfigError("Control times must increase strictly within the horizon")

        def fraction(v, n):
            return bounded(v, n, upper=1)

        result.append(
            LeakChange(time, _vector(entry[key], 3, "leak multipliers", fraction))
            if leak
            else (ContactChange if contact else PumpChange)(time, fraction(entry[key], key))
        )
    if result[0].time != 0:
        raise ConfigError("Each control group must explicitly start at time zero")
    return tuple(result)


def parse(data):
    m = _fields(
        data["model"],
        {
            "id",
            "units",
            "ionic_species",
            "regulatory_coordinates",
            "population",
            "initial_state",
            "parameters",
        },
        "model",
    )
    if (
        m["units"] != UNITS
        or m["ionic_species"] != list(IONS)
        or m["regulatory_coordinates"] != list(REGULATION)
    ):
        raise ConfigError("Source pair requires exact nominal units and declared coordinate order")
    pop = _fields(m["population"], {"count", "cell_ids"}, "population")
    if type(pop["count"]) is not int or pop["count"] != 2:
        raise ConfigError("This first source-compatible profile requires two active cells")
    ids = _vector(pop["cell_ids"], 2, "cell IDs", _integer)
    if len(set(ids)) != 2:
        raise ConfigError("Cell IDs must be distinct")
    state = _fields(m["initial_state"], {"ions", "regulation"}, "initial state")
    ions = _vector(
        state["ions"], 3, "ions", lambda r, n: _vector(r, 2, n, lambda v, k: bounded(v, k, 1e-6))
    )
    regulation = _vector(
        state["regulation"], 3, "regulation", lambda r, n: _vector(r, 2, n, bounded)
    )
    p = _fields(
        m["parameters"], {"parameter_set", "context", "membranes", "bath", "contact"}, "parameters"
    )
    if p["parameter_set"] != PARAMETER_SET:
        raise ConfigError("Unknown source parameter set; no implicit source/physical conversion")
    context = _fields(p["context"], set(CONTEXT), "fixed context")
    context = tuple(_vector(context[name], 2, name, bounded) for name in CONTEXT)
    bath = _fields(p["bath"], {"kind", "bath_id", "ions"}, "bath")
    if bath["kind"] != "clamped":
        raise ConfigError("The first source profile requires one clamped bath")
    bath_id = _integer(bath["bath_id"], "bath ID")
    bath_ions = _vector(bath["ions"], 3, "bath ions", lambda v, n: bounded(v, n, 1e-6))
    membranes = _vector(
        p["membranes"],
        2,
        "membranes",
        lambda a, n: _fields(a, set(SourceMembraneSpec.__dataclass_fields__), n),
    )
    by_owner, membrane_ids = {}, set()
    for a in membranes:
        membrane = SourceMembraneSpec(
            _integer(a["membrane_id"], "membrane ID"),
            _integer(a["owner_cell_id"], "membrane owner"),
            _integer(a["bath_id"], "membrane bath"),
            _vector(a["diffusion"], 3, "membrane diffusion"),
        )
        if (
            membrane.owner_cell_id not in ids
            or membrane.owner_cell_id in by_owner
            or membrane.membrane_id in membrane_ids
            or membrane.bath_id != bath_id
        ):
            raise ConfigError("Each cell needs one identified membrane facing the declared bath")
        by_owner[membrane.owner_cell_id] = membrane
        membrane_ids.add(membrane.membrane_id)
    membranes = tuple(by_owner[identity] for identity in ids)
    c = _fields(p["contact"], set(SourceContactSpec.__dataclass_fields__), "contact")
    contact = SourceContactSpec(
        _integer(c["contact_id"], "contact ID"),
        _integer(c["from_cell_id"], "sender ID"),
        _integer(c["to_cell_id"], "receiver ID"),
        _vector(c["ion_diffusion"], 3, "ion diffusion"),
        _number(c["mirna_diffusion"], "miRNA diffusion"),
        c["gate_profile"],
        c["swap_hemichannels"],
    )
    if {contact.from_cell_id, contact.to_cell_id} != set(ids):
        raise ConfigError("Contact must connect the distinct declared cells")
    if (
        contact.gate_profile not in (None, "45/45", "40/37")
        or type(contact.swap_hemichannels) is not bool
    ):
        raise ConfigError("Unknown gate profile or invalid hemichannel orientation")
    if contact.gate_profile is None and contact.swap_hemichannels:
        raise ConfigError("Ungated contact has no hemichannels to swap")
    model = SourcePairSpec(ids, ions, regulation, context, membranes, bath_id, bath_ions, contact)
    e = _fields(
        data["experiment"],
        {"end_time", "source", "observation_times", "membrane_controls", "contact_controls"},
        "experiment",
    )
    if _fields(e["source"], {"kind"}, "source")["kind"] != "none":
        raise ConfigError("This model has no prescribed source injection")
    end = _number(e["end_time"], "end time", positive=True)
    if not isinstance(e["observation_times"], list) or not e["observation_times"]:
        raise ConfigError("Observation times must be a nonempty list")
    times = tuple(_number(v, "observation time") for v in e["observation_times"])
    if any(v > end for v in times) or any(b <= a for a, b in zip(times, times[1:], strict=False)):
        raise ConfigError("Observation times must increase strictly within the horizon")
    controls = _vector(
        e["membrane_controls"],
        2,
        "membrane controls",
        lambda g, n: _fields(g, {"membrane_id", "leak", "pump"}, n),
    )
    groups = {}
    for g in controls:
        identity = _integer(g["membrane_id"], "control membrane ID")
        if identity not in membrane_ids or identity in groups:
            raise ConfigError("Controls must identify each declared membrane exactly once")
        groups[identity] = MembraneSchedule(
            schedule(g["leak"], end, leak=True), schedule(g["pump"], end)
        )
    contacts = _vector(
        e["contact_controls"],
        2,
        "route controls",
        lambda g, n: _fields(g, {"route", "contact_id", "schedule"}, n),
    )
    routes = {}
    for g in contacts:
        if (
            g["route"] not in ROUTES
            or g["route"] in routes
            or _integer(g["contact_id"], "control contact ID") != contact.contact_id
        ):
            raise ConfigError("Controls must identify both distinct routes on the declared contact")
        routes[g["route"]] = schedule(g["schedule"], end, contact=True)
    x = _fields(data["execution"], set(ExecutionSpec.__dataclass_fields__), "execution")
    for key, value in (("backend", "cpu"), ("precision", "float64"), ("solver", "rk4")):
        if x[key] != value:
            raise ConfigError(f"This version requires {key}={value!r}")
    if type(x["jit"]) is not bool:
        raise ConfigError("jit must be a boolean")
    execution = ExecutionSpec(
        _number(x["dt"], "dt", positive=True),
        _integer(x["capacity"], "cell capacity", minimum=2),
        x["jit"],
        _integer(x["max_steps"], "max steps"),
        _integer(x["max_trace_bytes"], "max trace bytes", maximum=2**53 - 1),
        edge_capacity=_integer(x["edge_capacity"], "edge capacity"),
        membrane_capacity=_integer(x["membrane_capacity"], "membrane capacity", minimum=2),
    )
    from cells.models.source_pair import check_definition

    check_definition(model)
    return SimulationSpec(
        model,
        RoutePairExperimentSpec(
            end,
            times,
            tuple(groups[a.membrane_id] for a in membranes),
            tuple(routes[name] for name in ROUTES),
        ),
        execution,
    )
