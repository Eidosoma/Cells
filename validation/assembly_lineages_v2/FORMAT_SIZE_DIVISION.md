# The engine's output format for the size-threshold division (`cells.operator.size_threshold_division@1`)

OL6 S7. This page adds to `FORMAT.md` and `FORMAT_OL2.md` what a world writes when it declares
the size-threshold division (`size_division.py`). A world that does not declare it writes
exactly what those pages describe: no key, row, record or legend entry below appears in it.

The state-triggered division of the OL6 design note's §6.8 (G2; D304), by Protocol G's §3
interface contract (tag `ol6-protocol-g-registered-2026-11-23`). It is @1's
`cells.operator.size_threshold_fission@1`, with its draw layout, partition, continuation and keys, in version
2's worlds. Its first reader is Protocol G's scope 2, the GARD limit through 50 fissions.

## The world

- **The declaration**, a single lineage's:

  ```json
  "division": {"law": "cells.operator.size_threshold_division@1", "size": 80,
               "partition": {"rule": "exact_fraction", "fraction": 0.5},
               "continuation": "first"}
  ```

  - `size` is an integer in [2, 2^20], at most `molecule_capacity`.
  - `fraction` lies strictly between 0 and 1, with floor(fraction × size) ≥ 1.
  - `continuation` is `first`.
- **Version 1 refuses:**
  - a geometry, since a vesicle's physical division is `cells.operator.shear_fission@1`'s (D2);
  - finite lumen places;
  - a step whose forward changes the membrane's count by more than one molecule, so the trigger is
    exact;
  - a founder whose membrane holds `size` or more;
  - population mode, schedules, tension holds and `diagnostic: true`;
  - `cells.assembly_representation.rate_equations@1`, by name.

  `trace` and `uniforms` are admitted.

## A division

- **The trigger.** A committed event that moves one molecule into the membrane and brings its
  count N to `size`. The division then acts at once, at that event's time, before the next draw.
  No draw is discarded.
- **The draw.** Domain 2 (partition), the parent's carrier key, counter 0.
  - The occupied membrane places are listed by type in declared order, the membrane's places in
    place order, and place k takes the k-th uniform.
  - Only the first N are read. Under partitionable threefry they are the first N of any longer
    draw at that address, @1's draw of `molecule_capacity` among them.
- **The partition.** Rank the places by u ascending, ties by place.
  - The first floor(f N) go to the first daughter, with floor taken in float64 as @1's take is.
  - The second daughter is the parent less the first.
- **The keys.** The daughters take `s:c` and `s:c+1` from the parent's counter, the first the lower.
  - The first daughter is followed. It continues the counter and becomes the slot's occupant.
  - Its event stream (domain 1, its key) starts at counter 0: its age restarts.
  - The second daughter leaves for `sink:discard`.
- **The booking.** w = F_m(first) + F_m(second) − F_m(parent), from an unmodelled agent and
  signed; the sink takes F_m(second). F_m is the membrane's own part of F, so the pool's part
  cancels.
- **The event guard.** A trigger that is also the guard's last event divides, and the lineage then
  ends `event_limit`.

## The bundle (size-division worlds only; every other bundle is unchanged)

- **records.npz** adds:
  - `division_work_kT` and `discarded_free_energy_kT` [row], both cumulative;
  - the fission table, one row per division, at its trigger:
    - `fission_time`;
    - `fission_event`, the trigger's index among the lineage's committed events from 1, so the
      trace's events after it are the followed daughter's;
    - `fission_parent`, `fission_parent_generation` and `fission_size` (N);
    - `fission_parent_counts` [fission, place];
    - `fission_daughters` [fission, 2], the keys;
    - `fission_daughter_counts` [fission, 2, place], each daughter's membrane with the pool as it
      was;
    - `fission_followed` (0), `fission_work_kT` and `fission_discarded_kT`;
  - with `uniforms: true`, `partition_uniforms` [fission, N]: the partition's draw, place k's the
    k-th.
- **row_kind** adds `division` (4), a row after each division at its trigger's time, holding the
  followed daughter.
- **run.json** adds:
  - `division`: the operator's declaration (its contract in words), the declared block, and the
    count of fissions;
  - `ssa.draw`'s text: a daughter's counter starts at 0;
  - `lifecycle.division`;
  - `engine_models.operators` names the operator.
- **relations.json and relations.npz** are `cells.relations@2`:
  - the lives: the founder, each parent `divided`, the first daughter in `slot:0`, and the second
    `not_followed`;
  - one `fission` event per division, at its parent, not scheduled, paid by
    `source:unmodelled_agent` (payer of `division_work_kT`);
  - each second daughter's molecules to `sink:discard`, per species.
