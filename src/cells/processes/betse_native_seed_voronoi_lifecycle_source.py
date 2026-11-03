# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
"""The two original make_voronoi lifecycle statements, before caller aliases.

Selection belongs to the authenticated constructor CALL witness. Neither
entry repeats the single_cell/svg_override descriptor reads. Mesh numerical
bodies are obtained as original CodeTypes from the actual issued runtime.
"""


class VoronoiLifecycle:
    def single(self, phase, image_mask):
        self.mesh.init_mesh()

    def multi_nonSVG(self, phase, image_mask):
        self.mesh.clip_and_refine(
            image_mask,
            smoothing=None,
            refinement=phase.p.refine_mesh,
            max_steps=phase.p.maximum_voronoi_steps,
            convergence=phase.p.voronoi_convergence,
            fix_bounds=True,
        )
