# Next build: explicit multispecies membrane assembly

2026-09-09, D045–D048. **SPEC-005 and NUM-006 are complete as references.** The
[physical contract](MULTISPECIES_MEMBRANE_SPEC.md) and
[1,546-check result](../reports/SPEC005_DESIGN_CHECK.md) now implement the brief
retained below. [NUM-006 now qualifies 14 short trajectory cases](../reports/NUM006_REFERENCE.md)
and a bounded RK4/cubic candidate. CORE-006 now implements the
[new CPU/JAX assembly](MULTISPECIES_MEMBRANE.md);
[bounded production acceptance passes](../reports/CORE006_ACCEPTANCE.md).
The original brief below remains a design-history record, not current status.
This begins stage 1 of the [BETSE capability roadmap](BETSE_CAPABILITY_ROADMAP.md).

## Smallest useful step

Generalize species/charge and membrane assembly with **one well-mixed cell,
one fixed membrane and one maintained bath**. Separate the species list,
compartment geometry, membrane endpoints and selected transport laws from the
numerical runner. The same definitions should later compose into communicating
cells and finite environments; they do not implement those extensions now.

Keep the old `bioelectric_cell@1` and its saved results unchanged. Begin with
a standalone scalar reference and proposed versioned definitions. A later
CORE-006 production assembly gets a new identity after numerical qualification.

## Specify and exercise next

- Species have stable IDs, signed valence and units; distinguish transported
  species from fixed intracellular charge and maintained bath background charge.
- Cell and bath definitions own different state/support. Keep amounts primary,
  volume fixed and concentrations derived. A maintained bath has an exchange
  ledger, not a fictional finite inventory.
- The membrane owns area/capacitance and endpoint mappings. Derive the electrical
  closure for this one-membrane case; do not generalize its affine anchor to
  arbitrary surfaces by assertion.
- Reuse the existing passive constant-field law where applicable. A selected
  pump declares stoichiometry and a named energy/kinetic law independently of
  species ordering. No inferred calcium, buffer or chloride transporter is added
  simply to improve the closed RPTEC pilot.
- Resolve bindings and numerical arrays on the host, then use pure array
  operators. No per-cell object dispatch, organ-specific branch or arbitrary
  code expression in the configuration.

Use two kinds of **synthetic engineering fixture**, neither a calibrated cell:

1. A Na/K/Cl reduction with exactly the previous model's equations and boundary,
   checking the new assembly against its independent reference.
2. A small divalent-ion fixture checking generic valence/charge accounting and
   passive electrochemical limits. Specify its balanced bath/background and
   valid positive domain before calculating. An inactive route must remain
   inactive without silently dropping its charge contribution.

Species-order permutation must change storage order, not physics. Adding a
species must not quietly alter chloride, fixed charge, initial voltage or pump
stoichiometry. Invalid/incomplete mechanisms should be rejected explicitly.

## Completion criteria for SPEC-005

Write the actual schema, equations, domain and support/accounting assumptions;
freeze the synthetic cases and numerical tolerances before evaluation. Supply
an independent instantaneous reference covering units, Nernst/zero-voltage
limits, passive dissipation, pump stoichiometry/stall where included, and
material/charge identities. Record failures and non-identifiable quantities.

Then qualify trajectories in the new regime against independent/refined CPU
methods before CORE-006 production acceptance, complete snapshots and regression
checks. Do not reuse old timestep bounds for a new divalent/kinetic regime.
Short fixtures suffice to exercise the contract; they do not imply long-time
physiology or BETSE parity.

## Not part of this first step

No new BIO-002 fitting, experimental pass criterion, general ionic graph,
calcium signaling network, finite bath, electrode/pipette dynamics, spatial
field, changing geometry, multirate solver, GPU runtime or performance study.
Those remain explicit extensions in the capability and execution documents.
No legacy model identifier or historical validation result is reinterpreted.
