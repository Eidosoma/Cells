"""Cell-owned, finite cytosolic IP3 controls the existing ER release route."""

from dataclasses import asdict, dataclass, fields

from cells.core import gated_calcium_spec as base
from cells.core.multispecies_spec import identifier
from cells.core.reaction_spec import bounded
from cells.core.spatial_calcium_spec import project
from cells.core.specs import ConfigError, SimulationSpec, _fields, _integer
from cells.processes.ip3_release import LAW_ID

MODEL_ID = "spatial_calcium@4"


@dataclass(frozen=True)
class IP3Release:
    cell_id: str
    species_id: str
    law: str
    activation_mM: float
    activation_n: int


@dataclass(frozen=True)
class IP3CalciumModel(base.GatedCalciumModel):
    ip3_release: tuple[IP3Release, ...]


def base_spec(spec):
    return SimulationSpec(
        project(spec.model, base.GatedCalciumModel), spec.experiment, spec.execution
    )


def to_dict(spec):
    raw = base.to_dict(base_spec(spec))
    raw["model"]["id"] = MODEL_ID
    raw["model"]["ip3_release"] = [asdict(p) for p in spec.model.ip3_release]
    return raw


def parse(data, *, ionic_family=None):
    _fields(
        data["model"],
        {"id", "ionic", "stores", "plasma_transport", "calcium_channels", "ip3_release"},
        "IP3 calcium model",
    )
    if data["model"]["id"] != MODEL_ID:
        raise ConfigError("Require the explicit IP3 calcium model identity")
    original = base.parse(
        data
        | {
            "model": {k: v for k, v in data["model"].items() if k != "ip3_release"}
            | {"id": base.MODEL_ID}
        },
        **({} if ionic_family is None else {"ionic_family": ionic_family}),
    )
    cells = [c.id for c in original.model.cells]
    rows = data["model"]["ip3_release"]
    if not isinstance(rows, list) or len(rows) != len(cells):
        raise ConfigError("Require one IP3 release binding per cell")
    bindings = {}
    for row in rows:
        _fields(row, {f.name for f in fields(IP3Release)}, "IP3 release binding")
        owner, species = identifier(row["cell_id"]), identifier(row["species_id"])
        if owner not in cells or owner in bindings:
            raise ConfigError("IP3 release owners must match distinct ionic cells")
        store = original.model.stores[cells.index(owner)]
        ids = [s.id for s in store.species]
        if (
            row["law"] != LAW_ID
            or species != "IP3"
            or species not in ids
            or "IP3" not in store.moieties
        ):
            raise ConfigError(
                "IP3 release requires its named law and explicit free IP3 species/moiety"
            )
        free = store.species[ids.index(species)]
        if free.moieties != tuple(int(k == "IP3") for k in store.moieties):
            raise ConfigError(
                "IP3 release must read free IP3, not a bound complex or ionic species"
            )
        if store.membrane.release is None:
            raise ConfigError("IP3 control requires an explicit ER calcium release route")
        bindings[owner] = IP3Release(
            owner,
            species,
            LAW_ID,
            bounded(row["activation_mM"], "IP3 activation concentration", 1e-12, 1e6),
            _integer(row["activation_n"], "IP3 Hill power", maximum=8),
        )
    return SimulationSpec(
        IP3CalciumModel(**vars(original.model), ip3_release=tuple(bindings[c] for c in cells)),
        original.experiment,
        original.execution,
    )
