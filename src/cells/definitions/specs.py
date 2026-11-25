"""Strict, model-specific data definitions; no implicit unit conversion."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cells.registry.model_table import MODELS

if TYPE_CHECKING:
    from cells.definitions.surface_tissue_spec import SurfaceExperiment, SurfaceTissueModel

UNITS = {"amount": "fmol", "volume": "pL", "time": "s"}
REACTION_TRANSPORT_ID = "reaction_transport@1"


class ConfigError(ValueError):
    """A definition cannot be executed without changing its declared meaning."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ConfigError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def read_json(path: str | Path) -> dict:
    def reject_constant(value: str) -> None:
        raise ConfigError(f"Non-finite JSON number: {value}")

    try:
        return json.loads(
            Path(path).read_text(),
            object_pairs_hook=_unique_pairs,
            parse_constant=reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON: {exc}") from exc


def require_fields(value: Any, expected: set[str], name: str) -> dict:
    """value, an object with exactly the expected keys (a public parsing helper: kinds and
    external modules parse their declarations with it; docs/INNER_MODEL_V4_DESIGN.md §7.4 (k))."""
    if not isinstance(value, dict):
        raise ConfigError(f"{name} must be an object")
    missing, unknown = expected - value.keys(), value.keys() - expected
    if missing or unknown:
        raise ConfigError(f"{name}: missing={sorted(missing)}, unknown={sorted(unknown)}")
    return value


def finite_number(value: Any, name: str, *, positive: bool = False) -> float:
    """value as a finite, nonnegative float (positive if asked); booleans are refused (public)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{name} must be a finite number")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ConfigError(f"{name} exceeds float64 range") from exc
    if not math.isfinite(result) or result < 0 or (positive and result == 0):
        raise ConfigError(f"{name} must be finite and {'positive' if positive else 'nonnegative'}")
    return result


def bounded_integer(value: Any, name: str, *, minimum: int = 1, maximum: int = 2**31 - 1) -> int:
    """value, an int (never a bool or a float) in [minimum, maximum] (public)."""
    if type(value) is not int or not minimum <= value <= maximum:
        raise ConfigError(f"{name} must be an integer in [{minimum}, {maximum}]")
    return value


# The private names stay as aliases for the many existing callers (the lead, 15 November).
_fields = require_fields
_number = finite_number
_integer = bounded_integer


@dataclass(frozen=True)
class SpeciesContactSpec:
    contact_id: int
    from_cell_id: int
    to_cell_id: int
    permeability: tuple[float, ...]  # In the declared species order; pL/s.


@dataclass(frozen=True)
class ReactionTransportSpec:
    species: tuple[str, str]
    cell_ids: tuple[int, ...]
    initial_amounts: tuple[tuple[float, ...], ...]  # [species, cell]
    volumes: tuple[float, ...]
    from_species: str
    to_species: str
    forward_rate: tuple[float, ...]  # Per-cell 1/s.
    reverse_rate: tuple[float, ...]
    contacts: tuple[SpeciesContactSpec, ...]


@dataclass(frozen=True)
class ChannelSpec:
    id: str
    membrane_id: str
    species_id: str
    kinetic_law: str
    max_permeability_m_per_s: float
    abundance: float
    initial_gate: tuple[float, float]  # Explicit activation m and inactivation h.


@dataclass(frozen=True)
class RateJunctionSpec:
    id: str
    from_cell: str
    to_cell: str
    area_m2: float
    permeability_m_per_s: tuple[float, ...]
    law: str
    threshold_voltage_V: float
    minimum_open_fraction: float
    initial_gate: float  # Intrinsic conductance, including the minimum opening.


@dataclass(frozen=True)
class FiniteCompartmentSpec:
    id: str
    volume_pL: float
    initial_amount_fmol: tuple[float, ...]
    fixed_charge_equivalent_fmol: float


@dataclass(frozen=True)
class MaintainedMetabolismSpec:
    kind: str
    atp_mM: float
    adp_mM: float
    pi_mM: float
    delta_g0_J_per_mol: float


@dataclass(frozen=True)
class KineticPumpSpec:
    id: str
    law: str
    roles: tuple[str, str]
    stoichiometry: tuple[int, ...]
    capacity_fmol_per_s: float
    km_na_mM: float
    km_k_mM: float
    km_atp_mM: float
    metabolism: MaintainedMetabolismSpec


@dataclass(frozen=True)
class ExtracellularFaceSpec:
    id: str
    sender: str
    receiver: str
    area_m2: float
    length_m: float
    diffusivity_m2_per_s: tuple[float, ...]


@dataclass(frozen=True)
class GraphContactChange:
    time: float
    open_fractions: tuple[float, ...]  # Normalized to model contact order.


@dataclass(frozen=True)
class ChannelChange:
    time: float
    availability: float


@dataclass(frozen=True)
class ExperimentSpec:
    end_time: float
    observation_times: tuple[float, ...]
    contact: tuple[GraphContactChange, ...]

    @property
    def changes(self):
        return self.contact


@dataclass(frozen=True)
class ExecutionSpec:
    dt: float
    capacity: int
    jit: bool
    max_steps: int
    max_trace_bytes: int
    backend: str = "cpu"
    precision: str = "float64"
    solver: str = "rk4"
    edge_capacity: int = 0
    membrane_capacity: int = 0


@dataclass(frozen=True)
class MultispeciesExecutionSpec(ExecutionSpec):
    material_balance_atol_fmol: tuple[float, ...] = ()  # Declared species order.


@dataclass(frozen=True)
class SpatialExtracellularExecutionSpec(MultispeciesExecutionSpec):
    extracellular_capacity: int = 0
    face_capacity: int = 0
    field_solver: str = ""  # Declared by every definition.


@dataclass(frozen=True)
class SimulationSpec:
    model: ReactionTransportSpec | SurfaceTissueModel
    experiment: ExperimentSpec | SurfaceExperiment
    execution: ExecutionSpec
    # Opt-in coarse projective mode (definitions/projective_spec.py), serialized as
    # execution.projective. None, the default, is the fine engine, unchanged.
    projective: Any = None
    # Opt-in step-doubled energy check (definitions/energy_check_spec.py; FR-18's X2, D224),
    # serialized as execution.energy_check. None, the default, keeps today's energy check, and
    # the definition's serialization and digest are unchanged. Added by the @3 owner at the
    # lead's word (a recorded exception in this file).
    energy_check: Any = None
    # Opt-in fine windows (definitions/fine_window_spec.py; C, D235), serialized as
    # execution.fine_windows. None, the default, keeps today's clock, and the definition's
    # serialization and digest are unchanged. Added by C's builder at the lead's word (D235).
    fine_windows: Any = None

    def to_dict(self) -> dict:
        result = self._fine_dict()
        if self.projective is not None:
            from cells.definitions.projective_spec import to_dict as projective_to_dict

            result["execution"]["projective"] = projective_to_dict(self.projective)
        if self.energy_check is not None:
            from cells.definitions.energy_check_spec import to_dict as energy_check_to_dict

            result["execution"]["energy_check"] = energy_check_to_dict(self.energy_check)
        if self.fine_windows is not None:
            from cells.definitions.fine_window_spec import to_dict as fine_windows_to_dict

            result["execution"]["fine_windows"] = fine_windows_to_dict(self.fine_windows)
        return result

    def _fine_dict(self) -> dict:
        m, e, x = self.model, self.experiment, self.execution
        from cells.definitions.apical_vertex_spec import ApicalVertexModel
        from cells.definitions.apical_vertex_spec import to_dict as apical_vertex_to_dict

        if isinstance(m, ApicalVertexModel):
            return apical_vertex_to_dict(self)
        from cells.definitions.surface_pump_water_v2_spec import SurfacePumpRegulatedWaterModel
        from cells.definitions.surface_pump_water_v2_spec import to_dict as pump_water_v2_to_dict

        if isinstance(m, SurfacePumpRegulatedWaterModel):
            return pump_water_v2_to_dict(self)
        from cells.definitions.surface_pump_water_spec import SurfacePumpWaterModel
        from cells.definitions.surface_pump_water_spec import to_dict as pump_water_to_dict

        if isinstance(m, SurfacePumpWaterModel):
            return pump_water_to_dict(self)
        from cells.definitions.cell_replacement_spec import CellReplacementModel
        from cells.definitions.cell_replacement_spec import to_dict as replacement_to_dict

        if isinstance(m, CellReplacementModel):
            return replacement_to_dict(self)
        from cells.definitions.pump_composite_spec import CompositeModel
        from cells.definitions.pump_composite_spec import to_dict as composite_to_dict

        if isinstance(m, CompositeModel):
            return composite_to_dict(self)
        from cells.definitions.surface_pump_v3_spec import SurfacePumpChannelModel
        from cells.definitions.surface_pump_v3_spec import to_dict as pump_v3_to_dict

        if isinstance(m, SurfacePumpChannelModel):
            return pump_v3_to_dict(self)
        from cells.definitions.surface_pump_v2_spec import SurfacePumpModel as SurfacePumpModelV2
        from cells.definitions.surface_pump_v2_spec import to_dict as pump_v2_to_dict

        if isinstance(m, SurfacePumpModelV2):
            return pump_v2_to_dict(self)
        from cells.definitions.surface_pump_spec import SurfacePumpModel, to_dict

        if isinstance(m, SurfacePumpModel):
            return to_dict(self)
        from cells.definitions.surface_kinetic_spec import SurfaceCatalogModel, SurfaceKineticModel
        from cells.definitions.surface_kinetic_spec import to_dict as surface_kinetic_to_dict
        from cells.definitions.surface_tissue_spec import SurfaceTissueModel
        from cells.definitions.surface_tissue_spec import to_dict as surface_tissue_to_dict

        if type(m) is SurfaceTissueModel:
            return surface_tissue_to_dict(self)
        if type(m) in (SurfaceKineticModel, SurfaceCatalogModel):
            return surface_kinetic_to_dict(self)
        from cells.models.assembly_lineages.spec import LineageModel
        from cells.models.assembly_lineages.spec import to_dict as lineage_to_dict

        if isinstance(m, LineageModel):
            return lineage_to_dict(self)
        from cells.models.assembly_lineages_v2.spec import AssemblyModel
        from cells.models.assembly_lineages_v2.spec import to_dict as assembly_to_dict

        if isinstance(m, AssemblyModel):
            return assembly_to_dict(self)
        if isinstance(x, MultispeciesExecutionSpec):
            raise ConfigError("Multispecies execution settings require their own model identity")
        if not isinstance(e, ExperimentSpec):
            raise ConfigError("Experiment type does not match the declared model")
        if not isinstance(m, ReactionTransportSpec):
            raise ConfigError(f"Unknown model specification type: {type(m).__name__}")
        if x.membrane_capacity != 0:
            raise ConfigError("This model does not support membrane controls or capacity")
        if any(type(p) is not GraphContactChange for p in e.contact):
            raise ConfigError("Control entries do not match the declared model's control family")
        return {
            "schema_version": 1,
            "model": {
                "id": REACTION_TRANSPORT_ID,
                "units": dict(UNITS),
                "species": list(m.species),
                "population": {"count": len(m.cell_ids), "cell_ids": list(m.cell_ids)},
                "initial_state": {
                    "amount": [list(row) for row in m.initial_amounts],
                    "volume": list(m.volumes),
                },
                "parameters": {
                    "reaction": {
                        "from_species": m.from_species,
                        "to_species": m.to_species,
                        "forward_rate": list(m.forward_rate),
                        "reverse_rate": list(m.reverse_rate),
                    },
                    "contacts": [
                        {
                            "contact_id": c.contact_id,
                            "from_cell_id": c.from_cell_id,
                            "to_cell_id": c.to_cell_id,
                            "permeability": list(c.permeability),
                        }
                        for c in m.contacts
                    ],
                },
            },
            "experiment": {
                "end_time": e.end_time,
                "source": {"kind": "none"},
                "observation_times": list(e.observation_times),
                "contact": {
                    "kind": "prescribed_contact_open_fractions",
                    "contact_ids": [c.contact_id for c in m.contacts],
                    "schedule": [
                        {"time": p.time, "open_fractions": list(p.open_fractions)}
                        for p in e.contact
                    ],
                },
            },
            "execution": {
                "backend": x.backend,
                "precision": x.precision,
                "solver": x.solver,
                "dt": x.dt,
                "capacity": x.capacity,
                "jit": x.jit,
                "max_steps": x.max_steps,
                "max_trace_bytes": x.max_trace_bytes,
                "edge_capacity": x.edge_capacity,
            },
        }

    @property
    def fingerprint(self) -> str:
        # Python callers may supply 20 where JSON parsing resolves 20.0. Hash
        # the validated numerical meaning, not that incidental representation.
        return digest(parse_spec(self.to_dict()).to_dict())


def parse_spec(data: dict) -> SimulationSpec:
    _fields(data, {"schema_version", "model", "experiment", "execution"}, "definition")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ConfigError("Only schema_version 1 is supported")
    if isinstance(data["execution"], dict) and "fine_windows" in data["execution"]:
        from cells.definitions.fine_window_spec import parse_definition as fine_window_definition

        return fine_window_definition(data, parse_spec)
    if isinstance(data["execution"], dict) and "energy_check" in data["execution"]:
        from cells.definitions.energy_check_spec import parse_definition as energy_definition

        return energy_definition(data, parse_spec)
    if isinstance(data["execution"], dict) and "projective" in data["execution"]:
        from cells.definitions.projective_spec import parse_definition

        return parse_definition(data, parse_spec)
    if isinstance(data["model"], dict) and data["model"].get("id") == "apical_vertex_mechanics@1":
        from cells.definitions.apical_vertex_spec import parse as parse_apical_vertex

        return parse_apical_vertex(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_pump_tissue@1":
        from cells.definitions.surface_pump_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_pump_tissue@2":
        from cells.definitions.surface_pump_v2_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_pump_tissue@3":
        from cells.definitions.surface_pump_v3_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_tissue@1":
        from cells.definitions.surface_tissue_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_tissue@2":
        from cells.definitions.surface_kinetic_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_tissue@8":
        from cells.definitions.surface_kinetic_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_pump_water@1":
        from cells.definitions.surface_pump_water_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_pump_water@2":
        from cells.definitions.surface_pump_water_v2_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_pump_replacement@1":
        from cells.definitions.cell_replacement_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_pump_composite@1":
        from cells.definitions.pump_composite_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "cells.assembly_lineages@1":
        from cells.models.assembly_lineages.spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "cells.assembly_lineages@2":
        from cells.models.assembly_lineages_v2.spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == REACTION_TRANSPORT_ID:
        return _parse_reaction_transport(data)
    if not isinstance(data["model"], dict):
        raise ConfigError("model must be an object")
    raise ConfigError(f"Unknown model: {data['model'].get('id')!r}; available: {', '.join(MODELS)}")


def _vector(value, size, name, convert=_number):
    if not isinstance(value, list) or len(value) != size:
        raise ConfigError(f"{name} must be a list of length {size}")
    return tuple(convert(v, name) for v in value)


def _parse_reaction_transport(data):
    m = _parse_reaction_transport_model(data["model"])
    experiment = _fields(
        data["experiment"], {"end_time", "source", "observation_times", "contact"}, "experiment"
    )
    end_time = _number(experiment["end_time"], "end time", positive=True)
    source = _fields(experiment["source"], {"kind"}, "source")
    if source["kind"] != "none":
        raise ConfigError("This model requires source.kind='none'")
    contact = _parse_graph_control(experiment["contact"], m, end_time)
    observations = experiment["observation_times"]
    if not isinstance(observations, list) or not observations:
        raise ConfigError("observation_times must be a nonempty list")
    times = tuple(_number(t, "observation time") for t in observations)
    if any(t > end_time for t in times) or any(
        b <= a for a, b in zip(times, times[1:], strict=False)
    ):
        raise ConfigError("observation times must be strictly increasing and within the horizon")
    execution = _fields(
        data["execution"],
        {
            "backend",
            "precision",
            "solver",
            "dt",
            "capacity",
            "jit",
            "max_steps",
            "max_trace_bytes",
            "edge_capacity",
        },
        "execution",
    )
    for name, required in {"backend": "cpu", "precision": "float64", "solver": "rk4"}.items():
        if execution[name] != required:
            raise ConfigError(
                f"This version requires {name}={required!r}; requested {execution[name]!r}"
            )
    if type(execution["jit"]) is not bool:
        raise ConfigError("jit must be a boolean")
    x = ExecutionSpec(
        dt=_number(execution["dt"], "dt", positive=True),
        capacity=_integer(execution["capacity"], "capacity"),
        jit=execution["jit"],
        max_steps=_integer(execution["max_steps"], "max_steps"),
        max_trace_bytes=_integer(
            execution["max_trace_bytes"], "max_trace_bytes", maximum=2**53 - 1
        ),
        edge_capacity=_integer(execution["edge_capacity"], "edge capacity", minimum=0),
    )
    if x.capacity < len(m.cell_ids) or x.edge_capacity < len(m.contacts):
        raise ConfigError("Cell/edge capacities must fit all declared cells and contacts")
    return SimulationSpec(m, ExperimentSpec(end_time, times, tuple(contact)), x)


def _parse_reaction_transport_model(model):
    _fields(model, {"id", "units", "species", "population", "initial_state", "parameters"}, "model")
    if model["units"] != UNITS:
        raise ConfigError(f"This model requires exactly {UNITS}; no implicit unit conversion")
    species = model["species"]
    if (
        not isinstance(species, list)
        or len(species) != 2
        or any(not isinstance(s, str) or not s.isascii() or not s.isidentifier() for s in species)
        or len(set(species)) != 2
    ):
        raise ConfigError("Reversible conversion requires two distinct ASCII species identifiers")
    population = _fields(model["population"], {"count", "cell_ids"}, "population")
    count = _integer(population["count"], "cell count")
    ids = _vector(population["cell_ids"], count, "cell IDs", _integer)
    if len(set(ids)) != count:
        raise ConfigError("Cell IDs must be distinct")
    initial = _fields(model["initial_state"], {"amount", "volume"}, "initial_state")
    amounts = _vector(initial["amount"], 2, "species amounts", lambda v, n: _vector(v, count, n))
    volumes = _vector(
        initial["volume"], count, "volumes", lambda v, n: _number(v, n, positive=True)
    )
    if not math.isfinite(sum(sum(row) for row in amounts)) or not math.isfinite(sum(volumes)):
        raise ConfigError("Total graph amount and volume must fit finite float64")
    parameters = _fields(model["parameters"], {"reaction", "contacts"}, "parameters")
    reaction = _fields(
        parameters["reaction"],
        {"from_species", "to_species", "forward_rate", "reverse_rate"},
        "reaction",
    )
    first, second = reaction["from_species"], reaction["to_species"]
    if first not in species or second not in species or first == second:
        raise ConfigError("Reaction must connect the two distinct declared species")
    forward = _vector(reaction["forward_rate"], count, "forward rates")
    reverse = _vector(reaction["reverse_rate"], count, "reverse rates")
    if not isinstance(parameters["contacts"], list):
        raise ConfigError("contacts must be a list; use [] for a contact-free world")
    contacts, seen = [], set()
    id_set = set(ids)
    for entry in parameters["contacts"]:
        c = _fields(entry, {"contact_id", "from_cell_id", "to_cell_id", "permeability"}, "contact")
        identity = _integer(c["contact_id"], "contact ID")
        sender = _integer(c["from_cell_id"], "contact from-cell ID")
        receiver = _integer(c["to_cell_id"], "contact to-cell ID")
        if identity in seen:
            raise ConfigError("Contact IDs must be distinct")
        if sender == receiver or sender not in id_set or receiver not in id_set:
            raise ConfigError("Contact endpoints must be distinct declared cell IDs")
        seen.add(identity)
        contacts.append(
            SpeciesContactSpec(
                identity, sender, receiver, _vector(c["permeability"], 2, "species permeabilities")
            )
        )
    return ReactionTransportSpec(
        tuple(species), ids, amounts, volumes, first, second, forward, reverse, tuple(contacts)
    )


def _parse_graph_control(value, model, end_time):
    control = _fields(value, {"kind", "contact_ids", "schedule"}, "graph contact control")
    if control["kind"] != "prescribed_contact_open_fractions":
        raise ConfigError("Graph control requires kind='prescribed_contact_open_fractions'")
    ids = _vector(control["contact_ids"], len(model.contacts), "control contact IDs", _integer)
    expected = tuple(c.contact_id for c in model.contacts)
    if len(set(ids)) != len(ids) or set(ids) != set(expected):
        raise ConfigError("Control contact IDs must identify every physical contact exactly once")
    slots = {identity: slot for slot, identity in enumerate(ids)}
    order = [slots[identity] for identity in expected]
    if not isinstance(control["schedule"], list) or not control["schedule"]:
        raise ConfigError("Graph contact schedule must be a nonempty list")
    changes = []
    for item in control["schedule"]:
        _fields(item, {"time", "open_fractions"}, "graph contact change")
        time = _number(item["time"], "contact time")
        fractions = _vector(item["open_fractions"], len(ids), "contact open fractions")
        if any(v > 1 for v in fractions):
            raise ConfigError("Contact open fractions must be in [0, 1]")
        if time > end_time or (changes and time <= changes[-1].time):
            raise ConfigError("Contact times must be strictly increasing and within the horizon")
        changes.append(GraphContactChange(time, tuple(fractions[index] for index in order)))
    if changes[0].time != 0:
        raise ConfigError("Graph contact schedule must explicitly start at time 0")
    return changes


def load_spec(path: str | Path) -> SimulationSpec:
    return parse_spec(read_json(path))
