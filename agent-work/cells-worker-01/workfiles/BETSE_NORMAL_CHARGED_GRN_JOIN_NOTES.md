# Charged GRN cold initialization and normal dispatch

This separate `charged_grn` package preserves original charged cold compensation,
its owner/default writes, and the compensated material handoff before subsequent
ordinary source calls. Chief requested static preparation only. Numerical status
and provenance belong in the workqueue and frozen receipt; no worker numerical
qualification is implied.

The concrete context is the existing explicit three-cell/nine-membrane no-ECM
geometry and float64 source buffers, extended with a genuine sixth stationary
`M(-1)` row and six boundary concentrations. Existing `Na(+1)`/`K(+1)` roles and
the new M index are obtained through `get_ion`. The caller subtracts its supplied
M concentration from its P(-1) input to retain their nominal combined ionic
charge. That manufactured input recipe is archived before any constructor; it
does not repair native compensation or assert a physiological initialization.
X/Y have equal monovalent signs and source formal charge scale `1e-6` (or `2e-6`),
with a separate zero-charge control. The X-to-Y reaction retains charge weighting.

Original `tissue_init` computes scalar Qcells/Qenv, compensates the cell before
the environment, and sets `charge_has_been_balanced=True` after both return.
Positive Q removes K bulk and Na environment/boundary; negative Q removes M
bulk and M environment/boundary. Source ionic membrane caches are unchanged.
The port adopts these actual cold ionic arrays into its immutable material
parent while retaining voltage, gate cache/clocks and pump diagnostic proxies.
The native and port hot bridges retain all public owner/Core/Molecule fields,
boundary/simulator state, ionic snapshots and read-only compensation events.
Cold readers are not rerun on ordinary subsequent calls.

The negative-cell admission uses M bulk mean while its refusal uses M membrane
mean. The explicit threshold-gap case leaves cell M unchanged, publishes gene
charge, and ultimately marks balanced. This defect is retained and diagnosed.
Four distinct raw capacity refusals use the original `BetseSimConfException`;
environment refusals retain completed cell compensation and rho writes but leave
the balanced flag False. Failed and frozen predecessor evidence stays untouched.

Independent Decimal90/140 cold references use only inputs saved before source or
port constructors. They predict ionic/boundary changes, source flags/publication,
sequential failure stages, per-species ion and gene amounts, and ionic/formal
charge ledgers. Explicit primitive binary64 stores describe the source Q sum;
independent Decimal formulas retain raw inventories and charge separately. The
existing warm local reference equations and numerical budgets are unchanged.
All cold budgets are specified a priori in the protocol. Tests save actual,
reference, error and budget arrays before assertions and verify exact native
state and the material handoff.

Counterion removal is a material sink, and the boundary scalar is not an implicit
reservoir inventory. Source charge scaling does not rescale numeric gene amount.
Cold environment rho and subsequent no-ECM publication differ: normal enabled
publication writes zero molecular environment rho; disabled publication retains
the previous cold environment write. Source-effective bath bookkeeping, declared
single-bath defects and directed-GJ changes remain separate. No physical global
or energetic conservation, finite/shared-fuel coupling, biological calibration,
standalone sim-grn, full Simulator/mesh/YAML lifecycle or independently carried
trajectory accuracy follows.

Reuse the established static freeze driver and bounded runner. Chief owns any
requested numerical scheduling. The neutral GRN02, pending transporter03 and
all older protected scientific files must remain byte-identical.
