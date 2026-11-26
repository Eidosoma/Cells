"""cells.route.logmean_electrodiffusion_forms@1: the face law that moves each row a face carries as its forms.

The face note of docs/MITOCHONDRIA_DESIGN.md ("MT-1b's outer membrane", tag
mito-mt1b-face-design-2026-11-22, §2-4; its build plan, §7 item 1). A face declares this law in
place of cells.route.logmean_electrodiffusion@1, with the same fields (sender, receiver, area, length and one
diffusivity per species). Each row the face carries (a positive diffusivity) moves by Cells' own
discrete electrodiffusion, the log-mean Nernst-Planck flux of numerics/surface_transport, applied
to each of its movers:
- a binder row that the general closure (cells.binding.rapid_binding@1) holds at both of the face's ends moves
  as its forms f, each at its own valence z_f and the row's diffusivity (one class per binder):
  J_f = (D A/L) logmean(c_f,s, c_f,r) [ln(c_f,s/c_f,r) + z_f F dphi/RT]; the binder row changes by
  sum_f J_f and each ligand row by sum_f n_f,l J_f, so a bound form carries its ligands;
- every other row moves as itself, its one form, at the stage read's amount (a ligand row's free
  amount at a closure node, the stored amount elsewhere). A face of this law whose rows are all
  their own form is today's face, row for row: the degenerate case.
- a binder row that the closure holds at one end only is refused in version 1 (its forms have no
  concentration at the other end).

The movers' table is built here (movers, face_factors), from the definition and the binders'
forms, which the caller gives as data (the species registry's forms_of: a law imports Cells only
through cells.modules); the kernels are numerics/surface_transport.forms_face_transport and
numerics/surface_imex's forms twins, which take the movers' end concentrations, valences, factors
and row stoichiometry and know nothing of the closure.

Provenance: parity with cells.route.logmean_electrodiffusion@1, whose expression it applies to each mover; a
face whose rows are all their own form steps as today's face, bitwise, which its test checks with
a planted error. The forms, their valences and their classes' diffusivities are the definition's.

Forms faces are their own entity set in cells.model.resolved_pump_tissue@3 (models/surface_pump_v3), statically
absent unless declared, so no plain face, layout or program of a world without one changes (D148
case 2). Version 1 runs on the plain IMEX tableaux only: RK4, N2, the projective mode and the
composite families refuse it, and so does FR-42 for a labelled row a forms face moves.
"""

from typing import NamedTuple

import numpy as np

from cells.modules import RouteLaw

LAW_ID = "cells.route.logmean_electrodiffusion_forms@1"
CLOSURE_READ_ID = (
    "cells.binding.rapid_binding@1"  # The general closure whose forms a forms face moves.
)
LAW = RouteLaw(
    LAW_ID,
    ("face",),
    "Cells' own discrete electrodiffusion between two well-mixed outside nodes for each form of "
    "the rows a face carries: the Nernst-Planck flux at each form's logarithmic-mean "
    "concentration, a binder's bound forms carrying their ligands (docs/MITOCHONDRIA_DESIGN.md, "
    "MT-1b's outer membrane, a design, not a reproduction of a paper)",
    host="cells.model.resolved_pump_tissue@3",
    provenance="parity",  # cells.route.logmean_electrodiffusion@1's expression per mover (module docstring).
    test=(
        "tests/unit/test_rapid_binding_world.py::"
        "test_a_forms_face_of_rows_as_themselves_steps_as_todays_face"
    ),
)


class Movers(NamedTuple):
    """The movers of a world's forms faces, one table for every forms face (host arrays).

    names: each mover's name (a row's species ID; a binder form's "<binder row>:<form ID>").
    row: [mover] the species row a row mover reads (-1 for a binder form).
    binder: [mover] a binder form's binder, its index in the closure's binders (-1 for a row).
    form: [mover] a binder form's index among its binder's forms, base first (-1 for a row).
    carrier: [mover] the species row whose diffusivity moves the mover: a row mover's own, a
      binder form's binder row (one class per binder: all its forms move at its diffusivity).
    valence: [mover] its valence (a form's: its base's plus its ligands').
    stoichiometry: [mover, species] the stored rows one unit of the mover changes."""

    names: tuple
    row: object
    binder: object
    form: object
    carrier: object
    valence: object
    stoichiometry: object


def general_closure(model):
    """The general closure's declaration (cells.binding.rapid_binding@1) among the model's kinds, or None."""
    for _, declaration in getattr(model, "kinds", ()):
        if getattr(declaration, "read_id", None) == CLOSURE_READ_ID and hasattr(
            declaration, "closure_rows"
        ):
            return declaration
    return None


def carriage(model):
    """({(face ID, row): "forms" or "itself"} for every row a forms face carries, [refusals]): a
    binder row of the general closure that the closure holds at both of the face's ends moves as
    its forms; one it holds at one end only is refused (version 1: its forms have no concentration
    at the other end); every other row moves as itself."""
    closure = general_closure(model)
    binders, held = set(), {}
    if closure is not None:
        binders = {row for row, _ in closure.k_on}
        held = {node: set(rows) for node, rows in closure.binders}
    out, errors = {}, []
    for face in getattr(model, "forms_faces", ()):
        for row, diffusivity in zip(model.species_ids, face.diffusivity_m2_per_s, strict=True):
            if not diffusivity:
                continue
            ends = [row in held.get(node, ()) for node in (face.sender, face.receiver)]
            if row in binders and all(ends):
                out[(face.id, row)] = "forms"
            elif row in binders and any(ends):
                at, other = (
                    (face.sender, face.receiver) if ends[0] else (face.receiver, face.sender)
                )
                errors.append(
                    f"Forms face {face.id} carries the binder row {row}, which the closure holds "
                    f"at {at} and not at {other}: its forms have no concentration there (version 1)"
                )
            else:
                out[(face.id, row)] = "itself"
    return out, errors


def form_binders(model):
    """The binder rows some forms face moves as their forms, sorted."""
    return sorted({row for (_, row), how in carriage(model)[0].items() if how == "forms"})


def moved_rows_of(model, forms):
    """{forms face ID: (species, ...)}: the rows each forms face moves in the step: each row it
    carries as itself, and each binder row it carries as forms with its forms' ligand rows. forms:
    {binder row: its forms, base first ((form ID, ((ligand, n), ...), mu°/RT), ...)}, the species
    registry's, for every binder some face moves as its forms."""
    out = {}
    for (face, row), how in carriage(model)[0].items():
        rows = out.setdefault(face, set())
        rows.add(row)
        if how == "forms":
            for _, counts, _ in forms[row]:
                rows.update(ligand for ligand, n in counts if n)
    return {face: tuple(sorted(rows)) for face, rows in out.items()}


def movers(model, network=None, forms=None):
    """The movers' table: every species row as its own form (row order), then, for each binder row
    a forms face moves as its forms, each of that binder's forms, base first, in the closure's
    binder order. network: the general closure's layout arrays (binding_rows, binding_counts,
    binding_present, and its ligand count), and forms: the binders' forms as moved_rows_of takes
    them, both needed only where a binder moves as its forms."""
    species = len(model.species_ids)
    names = list(model.species_ids)
    row = list(range(species))
    binder, form, carrier = [-1] * species, [-1] * species, list(range(species))
    valence = [float(z) for z in model.valence]
    stoichiometry = [np.eye(species)[r] for r in range(species)]
    carried = form_binders(model)
    if carried:
        if network is None or forms is None:
            raise ValueError(
                "A binder that moves as its forms needs the general closure's arrays and its forms"
            )
        rows, counts, present, ligands = network
        for b, species_row in enumerate(rows[ligands:]):
            name = model.species_ids[int(species_row)]
            if name not in carried:
                continue
            ids = [fid for fid, _, _ in forms[name]]
            for k in np.flatnonzero(present[b]):
                vector = np.eye(species)[int(species_row)].copy()
                charge = float(model.valence[int(species_row)])
                for ligand, n in enumerate(counts[b, k]):
                    if n:
                        vector[int(rows[ligand])] += n
                        charge += n * model.valence[int(rows[ligand])]
                names.append(f"{name}:{ids[k]}")
                row.append(-1)
                binder.append(b)
                form.append(int(k))
                carrier.append(int(species_row))
                valence.append(charge)
                stoichiometry.append(vector)
    return Movers(
        tuple(names),
        np.asarray(row, dtype=np.int64),
        np.asarray(binder, dtype=np.int64),
        np.asarray(form, dtype=np.int64),
        np.asarray(carrier, dtype=np.int64),
        np.asarray(valence, dtype=float),
        np.asarray(stoichiometry, dtype=float),
    )


def mover_count(model, forms):
    """The movers' number, from the definition and the binders' forms (as moved_rows_of takes
    them), without the closure's arrays: every species row, and each form of each binder some
    forms face moves as its forms."""
    return len(model.species_ids) + sum(len(forms[row]) for row in form_binders(model))


def face_factors(model, table):
    """[mover, forms face] D A / L (m^3/s) of each forms face on each of its movers: a row the face
    carries as itself at its row mover, and a binder it carries as its forms at each of its form
    movers, every one at the binder row's diffusivity (one class per binder)."""
    how = carriage(model)[0]
    factor = np.zeros((len(table.names), len(model.forms_faces)))
    for k, face in enumerate(model.forms_faces):
        for row, diffusivity in enumerate(face.diffusivity_m2_per_s):
            if not diffusivity:
                continue
            value = diffusivity * face.area_m2 / face.length_m
            if how[(face.id, model.species_ids[row])] == "forms":
                factor[(table.carrier == row) & (table.binder >= 0), k] = value
            else:
                factor[int(np.flatnonzero(table.row == row)[0]), k] = value
    return factor
