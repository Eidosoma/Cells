# FR-43 part 3 co-writers: the lead's strings note (protocol §3 and §5; CRITERIA.md:223)

2026-11-26T21:31:50Z, the lead's own commit after the registration tag `fr43-part3-cowriters-registered-2026-11-26` (commit
2421e9e928d227966ce84bd5cd8bdc6b37b40d13), with its own tag `fr43-part3-cowriters-strings-2026-11-26`.

**Order kept:**
- the strings were parsed first: the builder's parse-only pass over all 282 runs (the 250 registered and the 32 retry runs of CRITERIA §7), from the
  lead's frozen snapshot of the registration commit (`/mnt/workspaces/Cells/fr43-registration-20261126/snap-2421e9e9`, clean, empty patch), with
  nothing compiled. Every run parsed and none was refused;
- the lead confirmed that the snapshot's SNAPSHOT.json records exactly the registration commit;
- only then was this note committed.

**Checked:**
- the lists equal the rehearsal's (the builder's operators.json at 458302ba), family by family;
- they equal the protocol's §3 models through the rename map (`src/cells/registry/renamed_ids.py`):
  `integer_unit_population@1`, `local_species_reactions@1` (W5, W5-exact), `templated_polymerisation@1` (W6), over
  `cells.model.resolved_pump_composite@1` on `cells.model.resolved_pump_tissue@3`.
- The source JSON's sha256 is a0606614b272a21b704a31eaa834e86c4c3b88e13025b25ea20356bdac9fec8c (`/mnt/workspaces/Cells/fr43-cowriters-build-20261126/registration-parse-2421e9e9/registered_operators.json`).

**The registered operator IDs per family, in declared order** (the judge compares each run's `operators` with these, exactly):

```json
{
 "W5 population-first": [
  "cells.operator.integer_unit_population@1",
  "cells.operator.local_species_reactions@1"
 ],
 "W5 reactions-first": [
  "cells.operator.local_species_reactions@1",
  "cells.operator.integer_unit_population@1"
 ],
 "W5-exact population-first": [
  "cells.operator.integer_unit_population@1",
  "cells.operator.local_species_reactions@1"
 ],
 "W5-exact reactions-first": [
  "cells.operator.local_species_reactions@1",
  "cells.operator.integer_unit_population@1"
 ],
 "W6 gene-first": [
  "cells.operator.templated_polymerisation@1",
  "cells.operator.integer_unit_population@1"
 ],
 "W6 population-first": [
  "cells.operator.integer_unit_population@1",
  "cells.operator.templated_polymerisation@1"
 ]
}
```
