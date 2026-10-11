"""Strict two-cell diagonal-capacitance closure; IDs resolve before device allocation.

Reuses the physical one-cell schema for each membrane and its independent leak/
pump schedules. The maintained bath is declared once. No implied time conversion,
instantaneous gate, graph growth, or source-compatible parameter profile.
"""

from dataclasses import asdict, replace

from cells.core import bioelectric_spec as single
from cells.core.specs import (
    BIOELECTRIC_ID,
    BIOELECTRIC_PAIR_ID,
    BioelectricPairSpec,
    ConfigError,
    ContactChange,
    ExperimentSpec,
    MembraneSchedule,
    PairExperimentSpec,
    SelectiveContactSpec,
    SimulationSpec,
    _fields,
    _integer,
    _number,
    _vector,
)

UNITS = {**single.UNITS, "gate": "fraction", "gate_sensitivity": "1/V", "energy": "pJ"}


def fraction(value, name):
    result = _number(value, name)
    if result > 1:
        raise ConfigError(f"{name} must lie in [0, 1]")
    return result


def to_dict(spec):
    m, e, x = spec.model, spec.experiment, spec.execution
    if not isinstance(e, PairExperimentSpec) or len(m.cells) != 2 or len(e.membranes) != 2:
        raise ConfigError("Physical pair requires two cells and their independent membrane groups")
    if any(type(c) is not ContactChange for c in e.contact):
        raise ConfigError("Contact controls must be prescribed fractions")
    if m.cells[0].bath != m.cells[1].bath:
        raise ConfigError("Physical pair requires one shared clamped bath and chemical drive")
    records = [
        single.to_dict(
            SimulationSpec(
                cell,
                ExperimentSpec(e.end_time, (), e.observation_times, leak=g.leak, pump=g.pump),
                replace(x, edge_capacity=0),
            )
        )
        for cell, g in zip(m.cells, e.membranes, strict=True)
    ]
    contact = asdict(m.contact)
    for name in ("permeability_m_per_s", "residual"):
        contact[name] = list(getattr(m.contact, name))
    return {
        "schema_version": 1,
        "model": {
            "id": BIOELECTRIC_PAIR_ID,
            "species": list(single.SPECIES),
            "units": dict(UNITS),
            "population": {"count": 2, "cell_ids": [c.cell_id for c in m.cells]},
            "initial_state": {
                "amount_fmol": [[c.initial_amount[s] for c in m.cells] for s in range(3)],
                "volume_pL": [c.volume_pL for c in m.cells],
                "voltage_V": [c.initial_voltage_V for c in m.cells],
            },
            "parameters": {
                "membranes": [r["model"]["parameters"]["membrane"] for r in records],
                "bath": records[0]["model"]["parameters"]["bath"],
                "contact": contact,
            },
        },
        "experiment": {
            "end_time": e.end_time,
            "observation_times": list(e.observation_times),
            "source": {"kind": "none"},
            "membrane_controls": [r["experiment"]["membrane_controls"] for r in records],
            "contact": {
                "kind": "prescribed_contact_multiplier",
                "contact_id": m.contact.contact_id,
                "schedule": [{"time": p.time, "multiplier": p.open_fraction} for p in e.contact],
            },
        },
        "execution": asdict(x),
    }


def parse(data):
    m = _fields(
        data["model"],
        {"id", "species", "units", "population", "initial_state", "parameters"},
        "model",
    )
    if m["species"] != list(single.SPECIES) or m["units"] != UNITS:
        raise ConfigError("Physical pair requires Na/K/Cl order and exact physical units")
    pop = _fields(m["population"], {"count", "cell_ids"}, "population")
    if type(pop["count"]) is not int or pop["count"] != 2:
        raise ConfigError("This diagonal closure supports exactly two active cells")
    ids = _vector(pop["cell_ids"], 2, "cell IDs", _integer)
    if len(set(ids)) != 2:
        raise ConfigError("Cell IDs must be unique")
    initial = _fields(
        m["initial_state"], {"amount_fmol", "volume_pL", "voltage_V"}, "initial state"
    )
    amounts = _vector(
        initial["amount_fmol"],
        3,
        "amount rows",
        lambda row, name: _vector(row, 2, name, single.positive),
    )
    volumes = _vector(initial["volume_pL"], 2, "volumes", single.positive)
    voltages = _vector(initial["voltage_V"], 2, "voltages", single.signed_number)
    p = _fields(m["parameters"], {"membranes", "bath", "contact"}, "parameters")
    membranes = _vector(
        p["membranes"],
        2,
        "membranes",
        lambda v, name: _fields(v, set(single.MembraneSpec.__dataclass_fields__), name),
    )
    by_owner, membrane_ids = {}, set()
    for membrane in membranes:
        owner = _integer(membrane["owner_cell_id"], "membrane owner")
        identity = _integer(membrane["membrane_id"], "membrane ID")
        if owner not in ids or owner in by_owner or identity in membrane_ids:
            raise ConfigError("Each cell requires one uniquely identified effective membrane")
        by_owner[owner] = membrane
        membrane_ids.add(identity)
    e = _fields(
        data["experiment"],
        {"end_time", "source", "observation_times", "membrane_controls", "contact"},
        "experiment",
    )
    groups = _vector(
        e["membrane_controls"],
        2,
        "membrane controls",
        lambda v, name: _fields(v, {"leak", "pump"}, name),
    )
    by_membrane = {}
    for group in groups:
        if not isinstance(group["leak"], dict):
            raise ConfigError("Leak control must be an object")
        identity = _integer(group["leak"].get("membrane_id"), "control membrane ID")
        if identity not in membrane_ids or identity in by_membrane:
            raise ConfigError("Membrane controls must identify each declared membrane exactly once")
        by_membrane[identity] = group
    if not isinstance(data["execution"], dict) or "edge_capacity" not in data["execution"]:
        raise ConfigError("Execution must explicitly include edge_capacity")
    execution = dict(data["execution"])
    edges = _integer(execution.pop("edge_capacity"), "edge capacity")
    cells, schedules = [], []
    for i, identity in enumerate(ids):
        membrane = by_owner[identity]
        # The shared one-cell parser validates units, all scalar domains, endpoints,
        # scheduling, solver policy, and resource fields without large allocation.
        cell = single.parse(
            {
                "model": {
                    "id": BIOELECTRIC_ID,
                    "species": list(single.SPECIES),
                    "units": dict(single.UNITS),
                    "population": {"count": 1, "cell_id": identity},
                    "initial_state": {
                        "amount_fmol": [row[i] for row in amounts],
                        "volume_pL": volumes[i],
                        "voltage_V": voltages[i],
                    },
                    "parameters": {"membrane": membrane, "bath": p["bath"]},
                },
                "experiment": {key: e[key] for key in ("end_time", "source", "observation_times")}
                | {"membrane_controls": by_membrane[membrane["membrane_id"]]},
                "execution": execution,
            }
        )
        cells.append(cell.model)
        schedules.append(MembraneSchedule(cell.experiment.leak, cell.experiment.pump))
    x = replace(cell.execution, edge_capacity=edges)
    if x.capacity < 2 or x.membrane_capacity < 2:
        raise ConfigError("Physical pair requires cell and membrane capacities >= 2")
    contact = _fields(p["contact"], set(SelectiveContactSpec.__dataclass_fields__), "contact")
    c = SelectiveContactSpec(
        _integer(contact["contact_id"], "contact ID"),
        _integer(contact["from_cell_id"], "from cell ID"),
        _integer(contact["to_cell_id"], "to cell ID"),
        single.positive(contact["area_m2"], "contact area"),
        _vector(contact["permeability_m_per_s"], 3, "contact permeabilities"),
        _vector(contact["residual"], 3, "residual fractions", fraction),
        single.positive(contact["sensitivity_per_V"], "gate sensitivity"),
        _number(contact["half_voltage_V"], "gate half voltage"),
        single.positive(contact["tau_s"], "gate time constant"),
        fraction(contact["initial_gate"], "initial gate"),
    )
    if {c.from_cell_id, c.to_cell_id} != set(ids):
        raise ConfigError("Contact must connect the two distinct declared cells")
    group = _fields(e["contact"], {"kind", "contact_id", "schedule"}, "contact control")
    if (
        group["kind"] != "prescribed_contact_multiplier"
        or _integer(group["contact_id"], "control contact ID") != c.contact_id
    ):
        raise ConfigError("Contact control must identify the declared contact and multiplier kind")
    if not isinstance(group["schedule"], list) or not group["schedule"]:
        raise ConfigError("Contact schedule must be a nonempty list")
    changes = []
    for entry in group["schedule"]:
        _fields(entry, {"time", "multiplier"}, "contact change")
        time = _number(entry["time"], "contact time")
        if time > cell.experiment.end_time or (changes and time <= changes[-1].time):
            raise ConfigError("Contact times must increase strictly within the horizon")
        changes.append(ContactChange(time, fraction(entry["multiplier"], "contact multiplier")))
    if changes[0].time != 0:
        raise ConfigError("Contact schedule must explicitly start at time zero")
    model = BioelectricPairSpec(tuple(cells), c)
    from cells.models.bioelectric_pair import check_definition

    check_definition(model)
    return SimulationSpec(
        model,
        PairExperimentSpec(
            cell.experiment.end_time,
            cell.experiment.observation_times,
            tuple(schedules),
            tuple(changes),
        ),
        x,
    )
