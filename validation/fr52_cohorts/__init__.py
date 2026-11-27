"""FR-52's independent check of the passive cohort record (docs/PASSIVE_COHORT_DESIGN.md §2.1, §3).

* exact.py: the reference. The identity map's rule read from the declaration on its own, the exact
  update in rationals, the exact distribution by enumerating labelled units, and the trace reader,
  which rebuilds every count from the trace's channels and the declared stoichiometry and checks
  them against the engine's recorded counts (integer_trace_counts) at every event and its saved
  counts at every row.
* worlds.py: the qualification world (two populations on one patch, its two cohorts declared,
  G1's and crossrev's world), its unobserved twin, and a dividing world beside a cohort.

Nothing here imports the engine's cohort kernel (cells.numerics.unit_cohorts): the reference
resolves, updates and enumerates on its own.
"""
