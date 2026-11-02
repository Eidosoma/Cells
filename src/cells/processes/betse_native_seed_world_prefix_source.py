# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
# ruff: noqa: F821
"""Literal make_world entry and native phase-kind helpers, before make_voronoi.

The full original lattice body is reused read-only from the existing literal
module. No normalized parameter stores, alternate Cells, or image are created.
"""

from cells.processes import betse_native_single_cell_caller_lattice_source as lattice


class WorldPrefix:
    def make_world(self, phase):
        phase.callbacks.progress_stated("Creating pseudo-random cell cluster...")
        phase.die_unless_kind_seed()
        if phase.p.svg_override is True:
            self.parse_svg(phase.p)
        else:
            self._make_cell_lattice(phase.p)


class PhaseKind:
    def die_unless_kind_seed(self):
        self._die_unless_kind(SimPhaseKind.SEED)

    def _die_unless_kind(self, *kinds):
        if self.kind not in kinds:
            kinds_name = (str(kind) for kind in kinds)
            kinds_name_joined = strjoin.join_as_disconjunction_double_quoted(*kinds_name)
            raise BetseSimPhaseException(
                'Simulation phase "{}" not {}.'.format(self.kind, kinds_name_joined)
            )


LATTICE = lattice.CellsKernel._make_cell_lattice
