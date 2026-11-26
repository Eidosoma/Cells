"""Assembly lineages (cells.model.assembly_lineages@1): a stochastic assembly family.

An assembly holds integer counts of declared molecule types. It exchanges single molecules with a
held phase (a reservoir whose activities the world fixes), grows to a declared size, splits at
random, and one daughter continues its lineage. The family is general machinery, named for what
it is (D192's G1; D197): Cells' own first-principles origin-of-life engine runs on it, with laws
derived from physical chemistry. Its pieces, one module each:

* family: the declared type family, with one standard transfer potential per type;
* spec: the definition (a world, its laws, the experiment and the execution);
* streams: keyed random streams, the module design's RNG contract (§5) and its first consumer;
* kernel: the exact stochastic simulation algorithm (the direct method), vmapped over lanes;
* exchange: the exchange law between the held phase and an ideal-mixing assembly;
* balance: the kernel's local detailed-balance check, which classifies a law as passive;
* fission, continuation: the size-triggered fission with its exact random partition, and the
  continuation of one daughter, with the lineage table;
* keys: carrier keys (a counter per sub-lineage), lives with their end reasons, and the run
  qualifier: the relationship keys, frozen (D202);
* ledger: the stochastic thermodynamic ledger (event heat, declared non-monotone);
* records: the run bundle (world record, run record, arrays and manifest);
* runner, model: the family's own runner shape (one lineage, every descendant, checkpoints and
  branches), and its entry in the model registry;
* reference: a host oracle that replays the kernel's events from supplied uniforms.

A rate-factor law is optional. A world without one runs exchange alone, and its programs hold no
factor code. GARD's catalysis (Segre, Ben-Eli and Lancet 2000, as the Plastic Heredity preprint
reconstructs it) is one declared law set of this kind, in gard.py, used only for comparison.

Nothing here runs at import: this module holds identifiers only.
"""

MODEL_ID = "cells.model.assembly_lineages@1"
EXCHANGE_LAW = "cells.exchange.reservoir_exchange@1"
FISSION = "cells.operator.size_threshold_fission@1"
CONTINUATION = "cells.operator.daughter_continuation@1"

# GARD's law set, for comparison only (gard.py).
GARD_SINGLE_EVENT = "cells.rate_factor.gard_catalysis_single_event@1"
GARD_PAIR_CONSISTENT = "cells.rate_factor.gard_catalysis_pair_consistent@1"
# The pair-consistent form with its cache of beta n held exactly (D244, D246); @1 keeps its bits.
GARD_PAIR_CONSISTENT_V2 = "cells.rate_factor.gard_catalysis_pair_consistent@2"

# The family's interfaces, declared in its row of the static model table
# (registry/model_table.py). The `cells` namespace is Cells' own (MODULE_SYSTEM_DESIGN §2.3), and
# the names are general: Cells' own origin-of-life laws implement the same interfaces (D197). The
# table also lists the homes that register the family's laws (exchange.py, gard.py) and operators
# (fission.py, continuation.py), which the registries import by name.
EXCHANGE_INTERFACE = "cells.exchange_law@1"
RATE_FACTOR_INTERFACE = "cells.rate_factor_law@1"
OPERATOR_INTERFACE = "cells.lineage_operator@1"

MODE = "single_lineage"  # One continuing assembly per world: one daughter is followed.
EVERY_DESCENDANT = "every_descendant"  # Every daughter lives (RELATIONSHIPS_DESIGN §1.4, P-a).
MODES = (MODE, EVERY_DESCENDANT)
