"""cells.route.constant_field@1: the passive membrane and junction route law of @3, its declaration.

Every membrane patch, junction and channel population of cells.model.resolved_pump_tissue@3 moves each
permeant species by the Goldman-Hodgkin-Katz constant-field flux, whose kernel is
laws/junctions/selective.selective_flux (named in place; docs/CORE_SEAMS_DESIGN.md §8.2). The law
was moved unchanged into @3 with its families (parity, not calibration). It is registered by the
law registry's loader.
"""

from cells.modules import RouteLaw

LAW_ID = "cells.route.constant_field@1"
LAW = RouteLaw(
    LAW_ID,
    ("membrane", "junction"),
    "the Goldman-Hodgkin-Katz constant-field flux of each permeant species "
    "(laws/junctions/selective.selective_flux)",
    host="cells.model.resolved_pump_tissue@3",
)
