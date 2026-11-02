# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
"""Literal first four make_voronoi statements, before mesh branch selection.

Only the selected body is retained here. Phase/Cells classes, native wrapper,
parameter descriptors and image helpers are authenticated by the driver; no
method is attached to or replaced on an existing phase or Cells instance.
"""

# ruff: noqa: F821
NATIVE_FILE = "betse/science/cells.py"
NATIVE_SHA256 = "be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2"


class VoronoiImagePrefix:
    def make_voronoi(self, phase):
        logs.log_info("Creating Voronoi geometry... ")
        from betse.science.tissue.picker.tispickimage import TissuePickerImage

        image_picker = TissuePickerImage(
            filename=phase.p.tissue_default.picker_image_filename, dirname=phase.p.conf_dirname
        )
        image_mask = image_picker.get_image_mask(cells=self)  # noqa: F841
