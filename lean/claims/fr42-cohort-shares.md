<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# Neutral arrival-time cohorts share one physical loss rate

Allocating one well-mixed population’s loss among cohorts in proportion to their amounts preserves the total loss, the total after one step, and readouts evaluated on those pooled totals. For quadratic loss, a tracked cohort and the difference from an independently evolved blank can give different answers.

## Assumptions

- The finite inventory includes the unlabelled remainder. The physical rate J(N) is computed once on the total N, with J(0) = 0. A cohort of size n receives J(N)·n/N for an occupied pool and zero for an empty pool.
- The step identity uses a common step size. Applying the readout identity to energy or heat requires the engine to evaluate these quantities from the physical pool.
- The exact example starts with two old units and one new unit, with no further arrivals, and uses N′ = −N². The comparison blank begins with only the two old units.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.ArrivalCohort.empty_label](../CellsProofs/Chemistry/ArrivalCohort.lean#L18)
- [CellsProofs.Chemistry.ArrivalCohort.sum_shares](../CellsProofs/Chemistry/ArrivalCohort.lean#L21)
- [CellsProofs.Chemistry.ArrivalCohort.step_total](../CellsProofs/Chemistry/ArrivalCohort.lean#L34)
- [CellsProofs.Chemistry.ArrivalCohort.pooled_readout](../CellsProofs/Chemistry/ArrivalCohort.lean#L44)
- [CellsProofs.Chemistry.ArrivalCohort.quadratic_share](../CellsProofs/Chemistry/ArrivalCohort.lean#L52)
- [CellsProofs.Chemistry.ArrivalCohort.remaining_initial](../CellsProofs/Chemistry/ArrivalCohort.lean#L63)
- [CellsProofs.Chemistry.ArrivalCohort.remaining_derivative](../CellsProofs/Chemistry/ArrivalCohort.lean#L67)
- [CellsProofs.Chemistry.ArrivalCohort.quadratic_example](../CellsProofs/Chemistry/ArrivalCohort.lean#L78)

Direct proof subject `cells.operator.neutral_arrival_labels@1`

Proof sources [FR-42 design requirement](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/docs/FEATURE_REQUESTS.md#fr-42--neutral-arrival-time-labels-that-leave-the-dynamics-unchanged) · [D289 adopts share vectors on the physical population](https://github.com/Eidosoma/Cells/blob/4e944a5634adafe1944235e540c6a7f0e564a144/docs/DECISIONS.md#d289-fr-42-is-built-as-option-a-labels-as-share-vectors-on-the-physical-row) · [FR-38 erratum B on class rows and the blank](https://github.com/Eidosoma/Cells/blob/184fc81cdfc0ea1b04eded5152c6cbbd2d5ea956/docs/TEMPLATED_POLYMERISATION_LAWS.md#913-erratum-b-the-label-rows-are-not-neutral-labels) · [Mathlib division of a finite sum, imported for the cohort balance](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Algebra/BigOperators/Field.lean#L22) · [Mathlib quotient derivative, imported for the survivor curve](https://github.com/leanprover-community/mathlib4/blob/c44e0c8ee63ca166450922a373c7409c5d26b00b/Mathlib/Analysis/Calculus/Deriv/Inv.lean#L143)

## Numerical comparison

**Checked.** Five quadratic-loss pools kept their shares bit for bit. At one second, the three-unit pool held 0.7499996135 fmol including 0.2499998712 fmol from the new cohort, within 10⁻⁶ fmol of 3/4 and 1/4. The analytical two-unit blank gives a difference of 1/12 fmol. All 42 shared history fields and 76 shared observations, including energy records, matched bit for bit when labels were enabled. Diagnostics agreed. In FR-49 World L the labelled and unlabelled twins also matched on shared physics beside a compartment. The development replay on cd3b7b09 adds label arrival, local expression exclusions and a 900 s restart through 1,260 s. A paired owner–compartment transfer proof remains open.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.neutral_arrival_labels@1`, `cells.local_species_reactions@1`, `cells.scheduled_species_turnover@1`

[Finite-step bisection, allocation and empty-row handling](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/src/cells/numerics/label_shares.py#L64) · [Label declarations, schedules and share update](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/src/cells/operators/species_labels.py) · [Composite half-step calls the label owner](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/src/cells/models/pump_composite.py#L1752) · [One-way reaction reports](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/src/cells/operators/species_reactions.py#L1692) · [Turnover reports](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/src/cells/operators/species_turnover.py#L611) · [Summation along the label axis](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/src/cells/numerics/species_sums.py) · [Compiled twin worlds, window integrals and tolerances](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/tests/unit/test_neutral_arrival_labels.py#L465) · [Composite tissue and production/clearance fixture](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/validation/tissue/secreted_species_fixtures.py) · [Reaction fixture and schedules](https://github.com/Eidosoma/Cells/blob/73afa19b5ddcb50405280d6d46207a25c41fec24/validation/tissue/species_reactions_fixtures.py) · [Exact endpoint and normalized label amounts](https://github.com/Eidosoma/Cells/blob/7e41a441b51b5a84ec57febb04b1e7a8f801674d/lean/CellsProofs/Chemistry/ArrivalSurvival.lean) · [Quadratic cohort and blank reference](https://github.com/Eidosoma/Cells/blob/7e41a441b51b5a84ec57febb04b1e7a8f801674d/lean/CellsProofs/Chemistry/ArrivalCohort.lean) · [Paired Actn1 isotope signals and GEO sample accessions](https://github.com/Eidosoma/Cells/blob/7e41a441b51b5a84ec57febb04b1e7a8f801674d/lean/checks/data/jovanovic2015_actn1.json) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/7e41a441b51b5a84ec57febb04b1e7a8f801674d/lean/checks/arrival_survival.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/7e41a441b51b5a84ec57febb04b1e7a8f801674d/lean/PROGRESS.md#fr42-neutral-survival)

[Tested engine 73afa19b5ddc](https://github.com/Eidosoma/Cells/commit/73afa19b5ddcb50405280d6d46207a25c41fec24) · [Evidence checkpoint 7e41a441b51b](https://github.com/Eidosoma/Cells/commit/7e41a441b51b5a84ec57febb04b1e7a8f801674d)

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.neutral_arrival_labels@1`, `cells.cell_owned_compartments@1`, `cells.templated_polymerisation@1`

[Compartment admission with labels](https://github.com/Eidosoma/Cells/blob/cd3b7b09d8252f445a976f0506767f1aaf38c53d/src/cells/operators/compartments.py#L584) · [Gene routes allowed beside a compartment](https://github.com/Eidosoma/Cells/blob/cd3b7b09d8252f445a976f0506767f1aaf38c53d/src/cells/operators/templated_polymerisation.py#L1430) · [Native passive-label update](https://github.com/Eidosoma/Cells/blob/cd3b7b09d8252f445a976f0506767f1aaf38c53d/src/cells/operators/species_labels.py) · [Allocation of a physical amount among labels](https://github.com/Eidosoma/Cells/blob/cd3b7b09d8252f445a976f0506767f1aaf38c53d/src/cells/numerics/label_shares.py) · [Matched World L fixtures](https://github.com/Eidosoma/Cells/blob/cd3b7b09d8252f445a976f0506767f1aaf38c53d/validation/fr49/worlds.py#L48) · [Twin and checkpoint comparisons](https://github.com/Eidosoma/Cells/blob/cd3b7b09d8252f445a976f0506767f1aaf38c53d/validation/fr49/judge_l.py) · [Bitwise restart at 900 s](https://github.com/Eidosoma/Cells/blob/cd3b7b09d8252f445a976f0506767f1aaf38c53d/tests/unit/test_fr49_world_l_resume.py#L18) · [Per-population label sum and pooled readout](https://github.com/Eidosoma/Cells/blob/73e7e9d7b639ce366d3a9e26d4b6af8b977d7b67/lean/CellsProofs/Chemistry/ArrivalCohort.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/73e7e9d7b639ce366d3a9e26d4b6af8b977d7b67/tests/unit/test_fr49_world_l.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/73e7e9d7b639ce366d3a9e26d4b6af8b977d7b67/lean/PROGRESS.md#nov24-main-audit)

[Tested engine cd3b7b09d825](https://github.com/Eidosoma/Cells/commit/cd3b7b09d8252f445a976f0506767f1aaf38c53d) · [Evidence checkpoint 73e7e9d7b639](https://github.com/Eidosoma/Cells/commit/73e7e9d7b639ce366d3a9e26d4b6af8b977d7b67)

## Biological evidence

**Open.** The surviving fraction of an identified arrival cohort within the same physical pool, paired with that pool’s total at the observation time.

In mock-treated mouse dendritic cells the 5 h Actn1 heavy fractions were 17.19% and 10.11%. The paired channel sum supplies the denominator. Recycling limits how precisely the heavy fraction measures newly made protein. For RNA pulse–chase assays, old nucleotide can still enter new RNA after a medium switch. Mapping that switch to a defined arrival cohort requires the incorporation history. [Pendleton, Fig. 2](https://rnajournal.cshlp.org/content/24/6/778.full) · [Gasser, Fig. 5](https://doi.org/10.1002/anie.201916272)

**Unit** Fraction of paired isotope signal

### jovanovic-2015-actn1-mock

Pulse SILAC after an isotope switch in mouse dendritic cells. The four samples have proteome-normalized iBAQ signals. Figure 1B, Figure 3F and GEO GSE59792, Actn1, paired 5 h MOCK medium and heavy samples. [Jovanovic et al. (2015), Science 347, 1259038](https://doi.org/10.1126/science.1259038)

- **Evidence role** descriptive
- **Observed** 0.13649927 Fraction of paired isotope signal

Sample SD 0.050071 across the two paired fractions. Both isotope channels were present in both replicates.

Within-replicate normalization cancels in H/(H+M). Its denominator is computed from the same two measurements. Recycled precursor can enter newly made protein. A common loss rate and the quadratic-loss example remain untested by this measurement. [Dataset manifest](../checks/data/jovanovic2015_actn1.json) · [Comparison verdict](../PROGRESS.md#fr42-neutral-survival)

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
