"""Versioned cross-region tissue with owned calcium and finite IP3 chemistry."""

from dataclasses import dataclass

from cells.core import ip3_calcium_spec as base
from cells.core import tissue_spec
from cells.core.specs import ConfigError, SimulationSpec

MODEL_ID = "spatial_calcium@5"


@dataclass(frozen=True)
class TissueCalciumModel(base.IP3CalciumModel):
    """Full IP3 calcium family with an explicit coupled tissue electrical law."""


def to_dict(spec):
    raw = base.to_dict(spec)
    raw["model"]["id"] = MODEL_ID
    return raw


def parse(data):
    if data["model"].get("id") != MODEL_ID:
        raise ConfigError("Require the explicit cross-region calcium identity")
    original = base.parse(
        data | {"model": data["model"] | {"id": base.MODEL_ID}},
        ionic_family=tissue_spec,
    )
    spec = SimulationSpec(
        TissueCalciumModel(**vars(original.model)), original.experiment, original.execution
    )
    from cells.models.tissue_calcium import check_definition

    check_definition(spec)
    return spec
