"""Assembly lineages (cells.assembly_lineages@1): a stochastic assembly family.

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

MODEL_ID = "cells.assembly_lineages@1"
EXCHANGE_LAW = "cells.reservoir_exchange@1"
FISSION = "cells.size_threshold_fission@1"
CONTINUATION = "cells.daughter_continuation@1"

# GARD's law set, for comparison only (gard.py).
GARD_SINGLE_EVENT = "cells.gard_catalysis_single_event@1"
GARD_PAIR_CONSISTENT = "cells.gard_catalysis_pair_consistent@1"

# The family's own interfaces, in its own namespace (CORE_SEAMS_DESIGN §8.1: "a family's own";
# the law template admits a `cells` interface only if it is one of the cells interfaces).
EXCHANGE_INTERFACE = "assembly_lineages.exchange_law@1"
RATE_FACTOR_INTERFACE = "assembly_lineages.rate_factor@1"
OPERATOR_INTERFACE = "assembly_lineages.operator@1"
# The family's built-in law homes. Each registers its laws on the law registry's BUILTIN through
# the public call, as an outside package would; factors.load_homes imports them by name, once.
LAW_HOMES = ("cells.models.assembly_lineages.exchange", "cells.models.assembly_lineages.gard")

MODE = "single_lineage"  # One continuing assembly per world: one daughter is followed.
EVERY_DESCENDANT = "every_descendant"  # Every daughter lives (RELATIONSHIPS_DESIGN §1.4, P-a).
MODES = (MODE, EVERY_DESCENDANT)
