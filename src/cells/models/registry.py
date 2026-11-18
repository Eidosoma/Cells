"""Small explicit model registry: no dynamic plugins or organ-name branches.

Each module supplies state/layout types, initialization, a pure RHS, numerical
checks, read-only observations, and a summary. Scientific meaning stays there;
the runner owns scheduling, integration, replay, and resource policy.
"""

from cells.core.legacy_entry import legacy
from cells.core.specs import ConfigError, ReactionTransportSpec
from cells.models import reaction_transport


def get_model(spec):
    from cells.core.apical_vertex_spec import ApicalVertexModel

    if isinstance(spec, ApicalVertexModel):
        from cells.models import apical_vertex

        return apical_vertex
    from cells.core.cell_replacement_spec import CellReplacementModel
    from cells.core.surface_pump_spec import SurfacePumpModel
    from cells.core.surface_pump_v2_spec import SurfacePumpModel as SurfacePumpModelV2
    from cells.core.surface_pump_v3_spec import SurfacePumpChannelModel
    from cells.core.surface_pump_water_spec import SurfacePumpWaterModel
    from cells.core.surface_pump_water_v2_spec import SurfacePumpRegulatedWaterModel

    if isinstance(spec, SurfacePumpRegulatedWaterModel):  # One model per inner structure.
        from cells.models import surface_pump_water_v2

        return surface_pump_water_v2.model_for(spec)
    if isinstance(spec, SurfacePumpWaterModel):
        from cells.models import surface_pump_water

        return surface_pump_water.model_for(spec)
    if isinstance(spec, CellReplacementModel):
        from cells.models import cell_replacement

        return cell_replacement.model_for(spec)
    from cells.core.pump_composite_spec import CompositeModel

    if isinstance(spec, CompositeModel):  # One cached implementation per operator list.
        from cells.models import pump_composite

        return pump_composite.model_for(spec)
    if isinstance(spec, SurfacePumpChannelModel):  # One implementation per declared structure.
        from cells.models import surface_pump_v3

        return surface_pump_v3.model_for(spec)
    if isinstance(spec, SurfacePumpModelV2):
        from cells.models import surface_pump_v2

        return surface_pump_v2
    if isinstance(spec, SurfacePumpModel):
        from cells.models import surface_pump

        return surface_pump
    if isinstance(spec, ReactionTransportSpec):
        return reaction_transport
    from cells.models.assembly_lineages.spec import LineageModel

    if isinstance(spec, LineageModel):  # Its own event-driven runner shape (runner.py there).
        from cells.models.assembly_lineages import model as lineages

        return lineages
    from cells.models.assembly_lineages_v2.spec import AssemblyModel

    if isinstance(spec, AssemblyModel):  # Version 2: its own event-driven runner shape.
        from cells.models.assembly_lineages_v2 import model as assemblies

        return assemblies
    model = legacy().model_for(spec)  # The older families (D188 R1).
    if model is not None:
        return model
    raise ConfigError(f"No registered implementation for {type(spec).__name__}")
