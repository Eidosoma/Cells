# Optional ideal-protein chemistry and conditional endpoint work

New worker files implement only pure chemical endpoint reports and conditional
work algebra. Chief owns the separate read-only work view, field/clamp inputs,
reference field integration and later live RHS/order/cursor work. Original
stocks, anchors, geometry, field/component/loop kernels and public I/O are untouched.

## Stable contract and physical frame

`physiology_protein_thermodynamics.evaluate(protein, binding, *, temperature_K,
standard_concentration_mol_m3, gas_constant_J_mol_K=R)` returns
`ProteinThermodynamics`, including physical cell/exterior owner energies in pJ,
ideal chemical potentials in J/mol, zero-stock masks and declared parameters.
Actual fixed owner m3 volumes and ID mappings reuse the qualified projection
geometry. Membrane concentration views are not inventory.

This optional Cells functional is
`Gchem = R*T*sum[n*(log(c/c0)-1)]`, with chemical mu0=0 at the declared c0. It is
the fixed-volume primitive of `mu=R*T*log(c/c0)`; the symbol G here denotes that
explicit chemical functional, without pressure-volume or temperature-path work.
Native BETSE supplies no energy law for its protein noise. No native energy,
heat, Brownian/FDT or noise-work claim follows from this choice.

`change(reference_protein, current_protein, binding, *, same parameters)` returns
`ProteinFreeEnergyChange`, with baseline/current reports, owner and total chemical
energy changes, exact material-balance strings and `strict_conservation_valid`.
The explicit reference never changes. General endpoint changes can be reported;
open-material changes do not qualify for the closed-protein work diagnostic.
The common standard-state contribution retains the actual net amount change.
Standard-state independence is an identity only when that net change is zero.

At zero concentration, energy is its continuous zero limit and ideal chemical
potential is explicitly minus infinity. No concentration floor is introduced.
Tiny concentrations are multiplied by actual volumes and energy scales before
float conversion, so an unrepresentable intermediate mol readout does not erase
a representable pJ change. Nonzero unrepresentable energy raises an exception
with exact raw evidence. Material strings/representability flags retain mol
diagnostics below float64 resolution.

Logarithms use 160-digit precision; products/sums use a fresh explicit 4096-digit
context and exact float inputs. Changes use unrounded owner terms, not a
subtraction of rounded totals. Unchanged large owners therefore do not erase
tiny changed owners, and equilibrium second-order changes remain visible.
The independent reference uses named raw-source pL/fmol arithmetic, direct
activity ratios, and 640-digit absolute endpoint energies.

## Conditional work interpretation

`endpoint_work(change, *, capacitor_energy_change_pJ, clamp_work_pJ)` returns
`ProteinEndpointWork.conditional_reversible_driving_work_pJ`; the earlier
`reversible_driving_work_pJ` name is an alias with the same conditional meaning.
The formula is `delta Gchem + delta Ucapacitor - Wclamp`, with clamp work positive
into the system. All scalar inputs are explicit and signed; a negative result
is retained. Exact input algebra avoids loss when large capacitor/clamp terms
cancel. Closed work requires the original strict 3e-13 gross material bound;
stock-resolution-only projection acceptance does not qualify here.

This is a conditional reversible endpoint requirement with fixed ion stocks,
temperature, geometry and the supplied clamp contribution. It is not an
attainable minimum or total protocol work. The same-state fields may support
ongoing ionic currents and holding dissipation; no time/path or holding work is
inferred from two endpoints. Heat, entropy production and stochastic work are
not inferred. Chief derives held-boundary electrode work and stable capacitor
energy differences independently, and reports charge-input roundoff/closure.

## Remaining coupling questions

- A live charged-protein law must specify transfer paths/order, electrical and
  chemical driving work, holding currents, dissipation and any stochastic drive.
  The endpoint identity alone cannot define those quantities or a noise law.
- Material sources/reservoirs need their own chemical-potential/work terms.
  Protein reservoirs are not inferred from held ionic baths or voltage clamps.
- Changing T, standard state, geometry, valence or reference inventories is a
  different physical protocol with extra terms; none is applied implicitly.
- This chemical layer can report some tiny-stock energies outside the charge
  projection's float mol domain. That does not extend field/coupled acceptance.
- Only explicit protein deltas relative to the original charge baseline may
  enter later fields. Original initial-charge anchors are never replaced here.

Qualification ownership and fixed inputs/limits are in
`physiology_protein_thermodynamics_workqueue.json`. Chief reports its separate
22 read-only work-view comparisons passing at
`/mnt/workspaces/Cells/physiology-protein-work-view-20261030-02/completion-verification.json`.
Its initial wrapper-seal failure is retained; those comparisons are not coupled
trajectory evidence or new worker biological cases.

## Frozen qualification and retained fixture failure

All 54 checks are qualified: 53 original passing cases are reused by exact
whole-module AST correspondence outside one corrected fixture, plus its fresh
focused pass. Core/reference bytes and all tolerances stayed unchanged.
A fresh process denying Cells/JAX imports replays 25 actual named cases in
75 chemical endpoint/change forms and 20 conditional-work forms. Saved reference
values replay exactly; maximum error is 0.063298 of the fixed 3e-15 relative plus
two-ULP budget, with true zeros exact.

The first tiny-transfer fixture was correctly refused by strict material
closure. Its helper multiplied density by volume into subnormal mol values
before dividing back to density. The observed net material error was
1.9040e-324 mol versus a 1.2e-327 mol tolerance. The original failed run and the
reproduced refusal remain intact. Forming the same tiny transfer as
`density*(Vcell/Voutside)` gives 3.3156e-331 mol residual under the unchanged gate.
Its nonzero -8.75824e-301 pJ chemical change survives cancellation of equal
1e308 pJ supplied capacitor/clamp inputs. This is an arithmetic/endpoint test,
not evidence of a realizable huge-energy field or protocol.

Final receipt:
`/mnt/workspaces/Cells/physiology-protein-thermodynamics-tests-20261030-02/result.json`,
SHA256 `54cbf39e24bc657e7f097f0a43fb24354117d878aa75bc8684262f439d3bcb0c`.
The focused/reference phases took 3.28/11.31 s, peak RSS 233590784/38625280 B,
with host reserve above 23 GB. The original 53-pass/one-failure run is preserved
at `physiology-protein-thermodynamics-tests-20261030-01`. Copied scientific
evidence stayed byte-exact. Full frozen hashes, 35 protected sources, AST/JUnit
correspondence and raw quantities are in the workqueue/receipt.

Chief's separate 22 work-view comparisons use the identical frozen 3a240c5 core.
No existing kernel, public I/O, PROGRESS, source anchor or accepted stock changed
in this worker lane. No GPU, long run or active campaign query was performed.
