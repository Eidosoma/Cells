"""Explicit ownership of spatial ions, intracellular chemistry and ER stores."""

from bisect import bisect_right
from dataclasses import dataclass, fields

from cells.core import er_spec, spatial_junction_spec
from cells.core.reaction_spec import ReactionExecution
from cells.core.specs import (
    ConfigError,
    PhysicalIonicGraphChange,
    PhysicalIonicGraphExperimentSpec,
    SimulationSpec,
    SpatialJunctionExecutionSpec,
    SpatialJunctionSpec,
    _fields,
    _integer,
)

MODEL_ID = "spatial_calcium@1"


@dataclass(frozen=True)
class CalciumModel(SpatialJunctionSpec):
    stores: tuple[er_spec.ERModel, ...]


@dataclass(frozen=True)
class CalciumChange(PhysicalIonicGraphChange):
    stores: tuple[er_spec.ERChange, ...]


@dataclass(frozen=True)
class CalciumExperiment(PhysicalIonicGraphExperimentSpec):
    stores: tuple[er_spec.ERExperiment, ...]

    @property
    def changes(self):
        groups = [super().changes, *(s.changes for s in self.stores)]
        times = [[p.time for p in group] for group in groups]
        result = []
        for time in sorted({t for ts in times for t in ts}):
            held = [g[bisect_right(ts, time) - 1] for g, ts in zip(groups, times, strict=True)]
            result.append(CalciumChange(**(vars(held[0]) | {"time": time}), stores=tuple(held[1:])))
        return tuple(result)


@dataclass(frozen=True)
class CalciumExecution(SpatialJunctionExecutionSpec):
    chemical_capacity: int = 2
    reaction_capacity: int = 0


def project(value, kind):
    return kind(**{f.name: getattr(value, f.name) for f in fields(kind)})


def ionic_spec(spec):
    from cells.core.tissue_spec import SOLVER_ID, TissueModel

    kind = TissueModel if spec.execution.field_solver == SOLVER_ID else SpatialJunctionSpec
    return SimulationSpec(
        project(spec.model, kind),
        project(spec.experiment, PhysicalIonicGraphExperimentSpec),
        project(spec.execution, SpatialJunctionExecutionSpec),
    )


def store_spec(spec, index):
    x = spec.execution
    return SimulationSpec(
        spec.model.stores[index],
        spec.experiment.stores[index],
        ReactionExecution(
            dt=x.dt,
            capacity=x.chemical_capacity,
            reaction_capacity=x.reaction_capacity,
            jit=x.jit,
            max_steps=x.max_steps,
            max_trace_bytes=x.max_trace_bytes,
            backend=x.backend,
            precision=x.precision,
            solver=x.solver,
        ),
    )


def to_dict(spec):
    raw = ionic_spec(spec).to_dict()
    raw["model"] = {"id": MODEL_ID, "ionic": raw["model"], "stores": []}
    raw["experiment"]["store_controls"] = []
    for i, cell in enumerate(spec.model.cells):
        store = er_spec.to_dict(store_spec(spec, i))
        raw["model"]["stores"].append({"cell_id": cell.id, "model": store["model"]})
        raw["experiment"]["store_controls"].append(
            {"cell_id": cell.id, "controls": store["experiment"]["controls"]}
        )
    raw["execution"].update(
        chemical_capacity=spec.execution.chemical_capacity,
        reaction_capacity=spec.execution.reaction_capacity,
    )
    return raw


def parse(data, *, ionic_family=spatial_junction_spec):
    model = _fields(data["model"], {"id", "ionic", "stores"}, "spatial calcium model")
    e = _fields(
        data["experiment"],
        {
            "end_time",
            "observation_times",
            "membrane_controls",
            "channel_controls",
            "junction_controls",
            "store_controls",
        },
        "spatial calcium experiment",
    )
    x = _fields(data["execution"], {f.name for f in fields(CalciumExecution)}, "execution")
    ionic_id = (
        "spatial_extracellular@2"
        if ionic_family is spatial_junction_spec
        else ionic_family.MODEL_ID
    )
    if model["id"] != MODEL_ID or model["ionic"].get("id") != ionic_id:
        raise ConfigError("Calcium requires its explicit spatial ionic family")
    ion = ionic_family.parse(
        {
            "schema_version": 1,
            "model": model["ionic"],
            "experiment": {k: v for k, v in e.items() if k != "store_controls"},
            "execution": {f.name: x[f.name] for f in fields(SpatialJunctionExecutionSpec)},
        }
    )
    n = len(ion.model.cells)
    if not 1 <= n <= 16:
        raise ConfigError("Spatial calcium supports 1–16 owned stores per world")
    capacity = _integer(x["chemical_capacity"], "chemical capacity", maximum=64)
    reaction_capacity = _integer(x["reaction_capacity"], "reaction capacity", maximum=1024)
    cids = [c.id for c in ion.model.cells]

    def owned(rows, field):
        if not isinstance(rows, list) or len(rows) != n:
            raise ConfigError("Require one explicitly owned ER store/control per cell")
        mapped = {}
        for row in rows:
            _fields(row, {"cell_id", field}, "owned ER store")
            owner = row["cell_id"]
            if not isinstance(owner, str) or owner not in cids or owner in mapped:
                raise ConfigError("ER owners must match distinct ionic cells")
            mapped[owner] = row[field]
        return [mapped[c] for c in cids]

    stores, experiments = [], []
    for cell, m, controls in zip(
        ion.model.cells,
        owned(model["stores"], "model"),
        owned(e["store_controls"], "controls"),
        strict=True,
    ):
        store = er_spec.parse(
            {
                "model": m,
                "experiment": {
                    "end_time": e["end_time"],
                    "observation_times": e["observation_times"],
                    "controls": controls,
                },
                "execution": {
                    k: x[k]
                    for k in (
                        "backend",
                        "precision",
                        "solver",
                        "dt",
                        "jit",
                        "max_steps",
                        "max_trace_bytes",
                    )
                }
                | {"capacity": capacity, "reaction_capacity": reaction_capacity},
            }
        )
        m = store.model
        names = [s.id for s in m.species]
        if (
            m.temperature_K != ion.model.temperature_K
            or m.standard_concentration_mM != 1
            or not set(ion.model.species_ids) <= set(m.moieties) & set(names)
        ):
            raise ConfigError(
                "ER stores require matching ion species/moieties, temperature "
                "and 1 mM standard state"
            )
        # Other moieties (including charged buffers) remain inside their cell.
        # Stage checks verify their inventories and true chemical charge as well
        # as ionic content; bound calcium is never treated as free calcium.
        cy = next(c for c in m.compartments if c.id == m.membrane.cytosol)
        if cy.volume_pL != cell.volume_pL:
            raise ConfigError("ER cytosol and ionic cell must share one volume")
        for i, name in enumerate(ion.model.species_ids):
            s = m.species[names.index(name)]
            wanted = tuple(int(q == name) for q in m.moieties)
            if (
                s.moieties != wanted
                or s.valence != ion.model.valence[i]
                or s.standard_mu_RT != 0
                or cy.initial_amount_fmol[names.index(name)] != cell.initial_amount_fmol[i]
            ):
                raise ConfigError(
                    "Free ionic species must share initial amounts and their chemical identity"
                )
        if stores and (m.species, m.moieties) != (stores[0].species, stores[0].moieties):
            raise ConfigError("Owned stores require the same chemical species/moiety table")
        stores.append(m)
        experiments.append(store.experiment)
    spec = SimulationSpec(
        CalciumModel(**vars(ion.model), stores=tuple(stores)),
        CalciumExperiment(**vars(ion.experiment), stores=tuple(experiments)),
        CalciumExecution(
            **vars(ion.execution), chemical_capacity=capacity, reaction_capacity=reaction_capacity
        ),
    )
    from cells.models.spatial_calcium import check_definition

    check_definition(spec)
    return spec
