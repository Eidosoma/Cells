"""proton_constant_field_leak@2: the proton leak reading a general binding closure's free h (MT-1b).

docs/MITOCHONDRIA_DESIGN.md §7, the face plan's item 3 (G1's Eq. 19 at h_P, erratum 2's item 1; the
kinds owner's review of 22 November 2026). @1's law (laws/transport/proton_leak.py, the FR-4/FR-5
owner's kernel, unedited), declared as a law of its own that reads rapid_binding@1. That closure's
stage read writes each held ligand's free amount into its row, so the kernel reads free h at both
ends there, as @1 reads B4's:

    J = A P m [h_out B(x) - h_in B(-x)] / 1e-15   (fmol/s, positive inward),   x = F V / (R T).

- **Inert:** it registers nothing itself. Its host, cells.passive_routes@1, runs it through @1's
  mask and fields (passive_leak), so it adds no field, and a route of either law gives the same
  arithmetic on the same read.
- **Its read** (`reads`): where the general closure holds its row, the species registry's
  admission (check_closure_rows) reads it, as it reads a cycle law's. A route law's reads default
  to () (registry/laws.RouteLaw), so @1 and every other route law keep theirs.
- **Its parse check** is the host's (kinds/passive_routes.check_definition): @1's, a valence +1
  row that is the closure's proton row where a closure is declared, and, its own, no end at a node
  of B4's version-1 closure (rapid_proton_buffer@1), whose free h @1 reads.
- **Its comparison rule** is @1's (D344).
"""

from cells.laws.transport import proton_leak
from cells.laws.transport.proton_leak import VALENCE, conductance_S, flux_fmol_s, heat_pJ_s
from cells.modules import RouteLaw

LAW_ID = "proton_constant_field_leak@2"
CLOSURE_READ_ID = "rapid_binding@1"  # The general closure whose free ligand it reads.
__all__ = (
    "CLOSURE_READ_ID",
    "LAW",
    "LAW_ID",
    "VALENCE",
    "conductance_S",
    "flux_fmol_s",
    "heat_pJ_s",
)

# The law's declaration (CORE_SEAMS §8.2): a route law of the passive routes kind, registered by
# the law registry's loader, its source @1's.
LAW = RouteLaw(
    LAW_ID,
    ("membrane",),
    "the Goldman-Hodgkin-Katz constant-field flux at valence +1 of free h, read through the "
    "general binding closure (rapid_binding@1) at each node it holds the proton at (@1's "
    "kernel, laws/transport/proton_leak.py)",
    stage_term="conductance_S",  # Its max-side slope in the stage rule, as @1's.
    host="cells.passive_routes@1",
    provenance="cited",
    source=proton_leak.LAW.source,
    reads=(CLOSURE_READ_ID,),
)
