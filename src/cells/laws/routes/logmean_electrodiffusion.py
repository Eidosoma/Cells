"""cells.route.logmean_electrodiffusion@1: the face route law between outside nodes of @3, its declaration.

Each face of cells.model.resolved_pump_tissue@3 moves each species between two well-mixed outside nodes by
Cells' own discrete electrodiffusion, the Nernst-Planck flux at the species' logarithmic-mean
concentration, whose kernel is numerics/surface_transport.transport, with its mean
numerics/extracellular_field.logmean (named in place; docs/CORE_SEAMS_DESIGN.md §8.2;
docs/SPATIAL_EXTRACELLULAR_SPEC.md, a design, not a reproduction of a paper). It is registered
by the law registry's loader.
"""

from cells.modules import RouteLaw

LAW_ID = "cells.route.logmean_electrodiffusion@1"
LAW = RouteLaw(
    LAW_ID,
    ("face",),
    "Cells' own discrete electrodiffusion between two well-mixed outside nodes: the "
    "Nernst-Planck flux at the species' logarithmic-mean concentration "
    "(docs/SPATIAL_EXTRACELLULAR_SPEC.md: a design, not a reproduction of a paper)",
    host="cells.model.resolved_pump_tissue@3",
)
