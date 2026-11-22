"""Assembly lineages, version 2 (cells.assembly_lineages@2): assemblies with phases and reactions.

The family's second major (the lead's ruling of 17 November 2026 on OL1's design check). Its first
major, cells.assembly_lineages@1, is frozen: single molecules exchanged with a held phase, in one
compartment, with GARD's law set for comparison. Version 2 generalises the channel layer and leaves
every @1 world bitwise unchanged, because no @1 module is edited. It imports what @1 has that is
general, unchanged: the serial folds (folds), the relationship keys (keys), the keyed streams'
derivation and uniforms (streams), and later the partition and continuation kernels.

**What version 2 adds** (docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md §0.1, §2, §6.3 R1-R3; OL1):
- places: a species in a phase, one of the pool (dilute; finite counts or held concentrations),
  the membrane (condensed) and the lumen (dilute);
- steps: reversible, with up to three reactant and three product molecules over places, so
  products may be in the membrane, the lumen or the pool (R1);
- one free-energy function F of the counts, from declared terms (R2): `cells.ideal_mixing@1` and
  `cells.regular_mixing@1` in OL1;
- the event-pair contract: a⁺(n) = s(m) θ⁺(n), a⁻(n + ν) = s(m) θ⁺(n) exp(F(n + ν) − F(n) − w),
  with m = min(n, n + ν) the pair's common state, s(m) ≥ 0 the kinetic factor (the locus extent
  and an optional rate factor, `cells.transition_state_factor@1`), θ⁺ the reactants' encounter
  (`cells.stochastic_mass_action@1`) and w the reservoir work of held species;
- physical units (R3): seconds, a declared temperature, litres and a standard concentration.

**The conventions** a world declares, each a named token with no default (conventions.py), and the
exact forms, are the format page's (the design check's FORMAT, relayed to the references' author).

Nothing here runs at import: this module holds identifiers only.
"""

MODEL_ID = "cells.assembly_lineages@2"

# The laws of OL1, each a declaration in its own home (the static model table's law_homes).
MASS_ACTION = "cells.stochastic_mass_action@1"
TRANSITION_STATE = "cells.transition_state_factor@1"
IDEAL_MIXING = "cells.ideal_mixing@1"
REGULAR_MIXING = "cells.regular_mixing@1"

# OL2's laws (docs/ORIGIN_OF_LIFE_OL2_OL3_CHECK.md §1.2; the design note's §0.2b-§0.2d). Each is
# absent from a world that declares no geometry, so OL1's worlds are unchanged.
BILAYER_GEOMETRY = "cells.bilayer_geometry@1"
PHASE_EXCHANGE = "cells.phase_exchange@1"
MEMBRANE_PERMEATION = "cells.membrane_permeation@1"
OSMOTIC_LUMEN = "cells.osmotic_lumen@1"  # OL2 milestone 2: lumen_volume osmotic.
SHEAR_FISSION = "cells.shear_fission@1"  # OL3 milestone 1: division at shear events.
SHARED_POOL = "cells.shared_pool@1"  # OL2 milestone 3: K slots on one pool (population.py).

# FR-21's shell (D244, D246; docs/ASSEMBLY_SHELL_DESIGN.md §4.2-§4.3): a prescribed wall with a
# declared area and lumen, its own entry law, and a gate factor over the gate's own forms.
PRESCRIBED_SHELL = "cells.prescribed_shell@1"
SHELL_PERMEATION = "cells.shell_permeation@1"
GATE_FACTOR = "cells.gate_factor@1"

# FR-31's Phase A (D287; docs/VESICLE_PORES_LAWS.md, tagged pores-laws-sheet-registered-2026-11-22):
# a pore's nucleation hazard per membrane area (a world's `hazard`), and a tension held over a
# declared interval, an applied protocol (the experiment's `tension_holds`). A world that declares
# neither runs as before.
PORE_NUCLEATION = "cells.pore_nucleation@1"
TENSION_HOLD = "cells.tension_hold@1"

# The family's interfaces, declared in its row of the static model table (registry/model_table.py).
# @1's three stay @1's: a transfer is now a step (not cells.exchange_law@1's single-molecule
# exchange), and a rate factor here is one factor per step pair on its common state (a new major of
# cells.rate_factor_law@1, which is per direction and per type and admits the single-event form).
REACTION_INTERFACE = "cells.reaction_law@1"
RATE_FACTOR_INTERFACE = "cells.rate_factor_law@2"
FREE_ENERGY_INTERFACE = "cells.free_energy_term@1"
GEOMETRY_INTERFACE = "cells.assembly_geometry@1"  # OL2: a geometry kind (§0.2c rule 15).
OPERATOR_INTERFACE = "cells.assembly_operator@1"  # OL3: an operator of the family's lineages.
POPULATION_INTERFACE = "cells.population_structure@1"  # OL2 milestone 3 (§0.2c rule 15).
HAZARD_INTERFACE = "cells.assembly_hazard@1"  # FR-31: a vesicle's hazard on a clock.

MODE = "single_lineage"  # OL1: one assembly per world, no fission (OL3 adds division).
POPULATION = "population"  # OL2 milestone 3: K slots sharing one pool (population.py).
MODES = (MODE, POPULATION)
