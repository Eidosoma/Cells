# REF-005b native pump–leak lifecycle closeout

2026-09-16, D116. **Native lifecycle scope independently closed.** This is
preparation/transfer evidence, not a matched Cells/BETSE trajectory or biological
validation. The [original handoff](REF005B_PUMP_PREFLIGHT_HANDOFF.md) is unchanged.

## Evidence and independent review

The detached capture completed at **15:41:43 UTC**, in **29.314 s**. All twelve
native runs completed: six controls, each observed and unobserved, with eight
25 µs updates. The independent review completed at **16:01:47 UTC**, in
**1.877 s**, without running either simulator or importing their numerical code.

The new stdlib-only reader and 70-digit Decimal reconstruction verify:

- **73,188 numerical comparisons, 150 physical records, all 48 observed
  updates and six exact observed/unobserved output pairs**.
- All **613 frozen source/configuration/contract inputs**, the exact
  **55-module production inventory**, all **73 result files**, and source-capsule
  membership/bytes; no added files, symlinks or contradictory failure receipt.
- Pump affinity, substrate saturation, signed -3/+2 transfers, passive flux,
  driver density scaling and boundary masks from saved live arguments/returns.
- Intracellular and shared-bath updates, positive concentrations, material
  conservation, charge/voltage reconstruction and elapsed-update chronology.
- Stored float64 array shape/type/byte hashes, including signed zero, and
  native histories tied to actual saved updates rather than raw sample labels.

The pump's third return is an outward-sodium diagnostic before driver scaling
and masking, **not ATP consumption**. Actual signed cycles are reconstructed
from the applied transfers. Source nonce perturbations are explicitly isolated
as compatibility behavior, not copied into the Cells biological law.

| Independent reconstruction | Maximum residual |
| --- | --- |
| Raw pump density | 6.617e-23 mol/m²/s |
| Raw passive / applied density | 1.059e-22 mol/m²/s |
| Intracellular update | 0 mM |
| Shared-bath update | 5.684e-14 mM |
| Global material | 5.015e-13 fmol |
| Voltage | 5.386e-13 V |
| Whole-cell current | 2.423e-27 A |

Whole-cell current and each saved face's current/density relation are checked;
the unexported per-cell face-smoothing weights are **not independently
reconstructed**. Native restart pickles are hashed, not executed: no native
restart qualification is claimed. Stderr contains exactly **24 known disabled-cut
notices**, and nothing else; this is not described as a warning-free capture.

The [26 audit software checks](ref-005b-audit-checks-01.xml) pass in **1.89 s**,
including changed inputs/transfers, clocks, diagnostics, history bytes and import
fencing. Scientific budgets and prior captured sources remain unchanged.

## Immutable identities and next gate

- Capture: `runs/ref-005b-pump-loop-2026-09-16/capture-01`.
  Completion SHA-256:
  `25080e882abfd303b4559132dd94512defa4793305e608afd906c9aeae3359c0`.
- Independent review: `runs/ref-005b-pump-loop-audit-2026-09-16/audit-01`.
  Completion SHA-256:
  `ca6e0f6535531ac772ea4d55e81a251d3b25fc8e4cefc2ec7987a6a357b9065e`.
- Final review status: `native_pump_lifecycle_independently_closed`.

The next [matched pilot](../docs/BETSE_MATCHED_PUMP_PILOT.md) maps this actual
geometry/chemistry into the existing production schema, first checking held-state
rates and single transfers, then short refined trajectories. Energy convergence,
longer relaxation, spatial pump composition, additional transporters, experiments,
GPU execution and full release promotion remain separate gates.
