"""logmean_electrodiffusion_forms@1: the face law that moves each row a face carries as its forms.

The face note of docs/MITOCHONDRIA_DESIGN.md ("MT-1b's outer membrane", tag
mito-mt1b-face-design-2026-11-22, §2-4; its build plan, §7 item 1). A face declares this law in
place of logmean_electrodiffusion@1, with the same fields (sender, receiver, area, length and one
diffusivity per species). Each row the face carries (a positive diffusivity) moves by Cells' own
discrete electrodiffusion, the log-mean Nernst-Planck flux of numerics/surface_transport, applied
to each of its movers:
- a binder row that the general closure (rapid_binding@1) holds at both of the face's ends moves
  as its forms f, each at its own valence z_f and the row's diffusivity (one class per binder):
  J_f = (D A/L) logmean(c_f,s, c_f,r) [ln(c_f,s/c_f,r) + z_f F dphi/RT]; the binder row changes by
  sum_f J_f and each ligand row by sum_f n_f,l J_f, so a bound form carries its ligands;
- every other row moves as itself, its one form, at the stage read's amount (a ligand row's free
  amount at a closure node, the stored amount elsewhere). A face of this law whose rows are all
  their own form is today's face, row for row: the degenerate case.
- a binder row that the closure holds at one end only is refused in version 1 (its forms have no
  concentration at the other end).

The movers' table is built here (movers, face_factors), from the definition; the kernels are
numerics/surface_transport.forms_face_transport and numerics/surface_imex's forms twins, which take
the movers' end concentrations, valences, factors and row stoichiometry and know nothing of the
closure. Forms faces are their own entity set in resolved_pump_tissue@3 (models/surface_pump_v3),
statically absent unless declared, so no plain face, layout or program of a world without one
changes (D148 case 2). Version 1 runs on the plain IMEX tableaux only: RK4, N2, the projective mode
and the composite families refuse it.
"""

from typing import NamedTuple

import numpy as np

from cells.modules import RouteLaw

LAW_ID = "logmean_electrodiffusion_forms@1"
LAW = RouteLaw(
    LAW_ID,
    ("face",),
    "Cells' own discrete electrodiffusion between two well-mixed outside nodes for each form of "
    "the rows a face carries: the Nernst-Planck flux at each form's logarithmic-mean "
    "concentration, a binder's bound forms carrying their ligands (docs/MITOCHONDRIA_DESIGN.md, "
    "MT-1b's outer membrane, a design, not a reproduction of a paper)",
    host="cells.resolved_pump_tissue@3",
)


class Movers(NamedTuple):
    """The movers of a world's forms faces, one table for every forms face (host arrays).

    names: each mover's name (a row's species ID; a binder form's "<binder row>:<form ID>").
    row: [mover] the species row a row mover reads (-1 for a binder form).
    valence: [mover] its valence (a form's: its base's plus its ligands').
    stoichiometry: [mover, species] the stored rows one unit of the mover changes."""

    names: tuple
    row: object
    valence: object
    stoichiometry: object


def movers(model):
    """The movers of version 1's slice 1: every species row as its own form (row order), so the
    table is the identity and a forms face is its rows' degenerate case. Binder forms join when the
    closure's read is wired (the build plan's item 1, its next part)."""
    species = len(model.species_ids)
    return Movers(
        tuple(model.species_ids),
        np.arange(species, dtype=np.int64),
        np.asarray(model.valence, dtype=float),
        np.eye(species),
    )


def face_factors(model, table):
    """[mover, forms face] D A / L (m^3/s) of each forms face on each of its movers: a row the
    face carries (a positive diffusivity) moves as itself here, at its row mover."""
    factor = np.zeros((len(table.names), len(model.forms_faces)))
    for k, face in enumerate(model.forms_faces):
        for row, diffusivity in enumerate(face.diffusivity_m2_per_s):
            if diffusivity:
                factor[int(np.flatnonzero(table.row == row)[0]), k] = (
                    diffusivity * face.area_m2 / face.length_m
                )
    return factor
