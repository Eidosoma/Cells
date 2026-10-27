"""Neutral mobile leak populations on explicitly identified fixed membrane patches."""

import copy
from dataclasses import asdict, dataclass, replace

from cells.core import surface_tissue_spec as base
from cells.core.bioelectric_spec import positive
from cells.core.multispecies_spec import aligned, identifier
from cells.core.specs import (
    ConfigError,
    SpatialExtracellularExecutionSpec,
    _fields,
    _integer,
    _number,
)

MODEL_ID = "resolved_redistribution@1"
POPULATION_LAW = "neutral_mobile_leak@1"


@dataclass(frozen=True)
class Population:
    id: str
    reference_density_fmol_per_um2: float
    permeability_at_reference_density_m_per_s: tuple[float, ...]
    initial_amount_fmol: tuple[float, ...]
    diffusivity_um2_per_s: float


@dataclass(frozen=True)
class SurfaceEdge:
    id: str
    sender: str
    receiver: str
    width_um: float
    distance_um: float


@dataclass(frozen=True)
class SurfaceRedistributionModel(base.SurfaceTissueModel):
    mobile_populations: tuple[Population, ...]
    surface_edges: tuple[SurfaceEdge, ...]


@dataclass(frozen=True)
class Execution(SpatialExtracellularExecutionSpec):
    population_capacity: int = 0
    surface_edge_capacity: int = 0


def base_spec(spec):
    def project(value, cls):
        return cls(**{k: getattr(value, k) for k in cls.__dataclass_fields__})

    return replace(
        spec,
        model=project(spec.model, base.SurfaceTissueModel),
        execution=project(spec.execution, SpatialExtracellularExecutionSpec),
    )


def to_dict(spec):
    if type(spec.execution) is not Execution:
        raise ConfigError("Mobile surfaces require their population and surface-edge capacities")
    raw = base.to_dict(base_spec(spec))
    m = spec.model
    raw["model"]["id"] = MODEL_ID
    raw["model"]["mobile_populations"] = [
        asdict(p)
        | dict(
            law=POPULATION_LAW,
            initial_amount_fmol=dict(
                zip((v.id for v in m.membranes), p.initial_amount_fmol, strict=True)
            ),
            permeability_at_reference_density_m_per_s=dict(
                zip(m.species_ids, p.permeability_at_reference_density_m_per_s, strict=True)
            ),
        )
        for p in m.mobile_populations
    ]
    raw["model"]["surface_edges"] = [asdict(p) for p in m.surface_edges]
    for k in ("population_capacity", "surface_edge_capacity"):
        raw["execution"][k] = getattr(spec.execution, k)
    return raw


def parse(data, *, allow_empty_populations=False):
    raw = copy.deepcopy(data)
    m, x = raw["model"], raw["execution"]
    if m.get("id") != MODEL_ID or not {"mobile_populations", "surface_edges"} <= m.keys():
        raise ConfigError("Require resolved_redistribution@1 and explicit populations and edges")
    populations, edges = m.pop("mobile_populations"), m.pop("surface_edges")
    if (
        type(populations) is not list
        or (not populations and not allow_empty_populations)
        or type(edges) is not list
    ):
        raise ConfigError("Require a nonempty population list and an explicit surface-edge list")
    capacities = {}
    for key, size in (
        ("population_capacity", len(populations)),
        ("surface_edge_capacity", len(edges)),
    ):
        if key not in x:
            raise ConfigError("Missing execution capacity: " + key)
        capacities[key] = _integer(
            x.pop(key), key, minimum=max(1, size) if key == "population_capacity" else size
        )
    m["id"] = base.MODEL_ID
    original = base.parse(raw)
    b = original.model
    patches = tuple(p.id for p in b.membranes)
    parsed = []
    for p in populations:
        _fields(p, set(Population.__dataclass_fields__) | {"law"}, "mobile population")
        if p["law"] != POPULATION_LAW:
            raise ConfigError("Only neutral always-open mobile leak populations are supported")
        amounts = aligned(p["initial_amount_fmol"], patches, "surface amount", _number)
        # Finite ideal-mixing chemical potentials: each cell is either populated
        # on every patch or entirely empty. No log floor or protein creation.
        for cell in b.cells:
            present = [
                a > 0
                for patch, a in zip(b.membranes, amounts, strict=True)
                if patch.inside == cell.id
            ]
            if not present or (any(present) and not all(present)):
                raise ConfigError(
                    "A population must fill every patch positively or be absent on that cell"
                )
        parsed.append(
            Population(
                identifier(p["id"]),
                positive(p["reference_density_fmol_per_um2"], "reference surface density"),
                aligned(
                    p["permeability_at_reference_density_m_per_s"],
                    b.species_ids,
                    "population permeability",
                ),
                amounts,
                _number(p["diffusivity_um2_per_s"], "surface diffusivity"),
            )
        )
    connections = parse_edges(edges, b.membranes)
    names = [
        p.id
        for family in (
            b.cells,
            b.extracellular,
            b.membranes,
            b.junctions,
            b.faces,
            parsed,
            connections,
        )
        for p in family
    ]
    if len(names) != len(set(names)):
        raise ConfigError("Physical owners, populations and surface edges require unique IDs")
    model = SurfaceRedistributionModel(
        **{k: getattr(b, k) for k in base.SurfaceTissueModel.__dataclass_fields__},
        mobile_populations=tuple(parsed),
        surface_edges=tuple(connections),
    )
    spec = replace(
        original, model=model, execution=Execution(**vars(original.execution), **capacities)
    )
    from cells.models.surface_redistribution import check_definition

    try:
        check_definition(spec)
    except (ArithmeticError, ValueError) as error:
        raise ConfigError("Invalid mobile surface definition: " + str(error)) from error
    return spec


def parse_edges(edges, membranes):
    """Fixed surface connections have one cell owner and one oriented edge."""
    if type(edges) is not list:
        raise ConfigError("Require an explicit surface-edge list")
    owners = {p.id: p.inside for p in membranes}
    connections, pairs = [], set()
    for e in edges:
        _fields(e, set(SurfaceEdge.__dataclass_fields__), "surface edge")
        sender, receiver = identifier(e["sender"]), identifier(e["receiver"])
        if (
            sender not in owners
            or receiver not in owners
            or sender == receiver
            or owners[sender] != owners[receiver]
        ):
            raise ConfigError("Surface edges must join distinct patches belonging to the same cell")
        pair = frozenset((sender, receiver))
        if pair in pairs:
            raise ConfigError("Duplicate surface connection")
        pairs.add(pair)
        connections.append(
            SurfaceEdge(
                identifier(e["id"]),
                sender,
                receiver,
                positive(e["width_um"], "surface edge width"),
                positive(e["distance_um"], "surface edge distance"),
            )
        )
    return tuple(connections)
