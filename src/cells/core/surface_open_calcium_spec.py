"""Full56 owned calcium with static ideal reservoirs and explicit domain ceilings."""

from dataclasses import dataclass, fields, replace

from cells.core import open_calcium_declarations as admission
from cells.core import surface_calcium_spec as parent
from cells.core.specs import ConfigError, SimulationSpec

MODEL_ID = "resolved_open_calcium@1"
EQUATION_MODEL_ID = parent.HCN_EXTRA_MODEL_ID


@dataclass(frozen=True)
class SurfaceOpenCalciumModel(parent.SurfaceCalciumHCNExtraModel):
    exterior_policy: str
    ionic_moiety_domain_policy: str
    ionic_moiety_ceiling_fmol: tuple | None


def equation_spec(spec):
    """Actual rate-equation inputs, not an admitted closed simulation."""
    return replace(
        spec,
        model=parent.SurfaceCalciumHCNExtraModel(
            **{
                field.name: getattr(spec.model, field.name)
                for field in fields(parent.SurfaceCalciumHCNExtraModel)
            }
        ),
    )


def to_dict(spec):
    if type(spec.model) is not SurfaceOpenCalciumModel:
        raise ConfigError("Require the exact full-catalog open calcium model")
    return admission.augment(parent.to_dict(equation_spec(spec)), spec.model, MODEL_ID)


def parse(data):
    declared, extra = admission.decode(data, MODEL_ID, EQUATION_MODEL_ID, parent)
    spec = SimulationSpec(
        SurfaceOpenCalciumModel(**vars(declared.model), **extra),
        declared.experiment,
        declared.execution,
    )
    from cells.models.surface_open_calcium import check_definition

    check_definition(spec)
    return spec
