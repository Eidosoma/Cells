# Native ECM material chronology

Chief assigned this lane after the environment field component. It closes the
missing normal ECM material order beyond B08 standalone environment transport;
Key's pump and no-ECM gate/current/voltage implementations remain read-only.
Chief owns project status in `PROGRESS.md`; this note describes the contract.

`src/cells/processes/betse_ecm_transport.py` exposes `bind`, `state`, `drive` and
`step`. It rebinds a separate original environment geometry declaration, plus
explicit fixed junction geometry, ordered moving species, transport coefficients
and source branch controls. Derived maps/areas/divergence operators are never
accepted as prepared input. Complete immutable states and source drives bind to
their original declaration; resealed/mutable buffers are rejected. The component
admits at most three source calls in a history, matching the planned bounded fixed-budget
checks; this round has an unresolved independent-accuracy failure. That cap is a component scope limit, not a native solver rule.

External seams are old electric field/flow, channel multiplier, fixed gap block,
boundary bath and post-rho/post-boundary-mask accumulated membrane flux. Pump
flux enters before any ion boundary clamp; separate late flux enters after all
ions. Pump rates, gate/handler/network callbacks, direct material mutations,
field solve and voltage update do not run here. Supplied closed-cluster flux
seams must already be zero on the native outer membrane mask. The conditional
source correspondence does not authenticate an external pump or handler law.

For each moving ion, native membrane electroflux samples pre-clamp environment
and stale membrane concentration, mutates vm by its nonce, computes fixed-gap
flux, clamps/transports the environment row and refreshes membrane concentration.
After all ions and the separate late seam, native material commit performs
membrane+ECM exchange, gap bulk-only update and no_negs clipping/NaN refusal.
Stationary species retain stored pump/late flux without material commit. Gap
temperature is configured p.T, while membrane/ECM temperature is runtime T.

Native collocated derivative signs and sequential integrator additions remain
literal. Fast ECM exchange assigns the last mapped membrane flux, then multiplies
the site's total membrane area. Slow exchange area-sums each membrane. These
are distinct when duplicate mappings carry different fluxes. Full clamp,
transport, smoothing, exchange, gap and clipping amount ledgers expose those
effects; signed environmental/membrane values and clipping additions remain
visible. The independent conservative membrane scatter oracle quantifies the
fast-exchange defect. It is separate from native collocated transport; the
existing B08 conservative face law remains separate and unchanged. No physical
material/charge/energy or full-native solver parity is claimed.

`validation/betse/betse_ecm_transport_protocol.json` pins seven native files and
fixes field-specific budgets before runs. It executes unchanged original reset,
moving-ion and material statements/functions with read-only trace copies. The
two external flux additions are labeled adapter inputs outside captured native
statements. Independent Decimal equations, owner/site loops and conservative
exchange accounting run at 100/160 digits with both complete rounded buffers
retained. Source nonce stores explicitly round to binary64. Fixed per-unit
budgets apply to complete short histories without propagated allowances. Amount
budgets account for bounded manufactured inventory subtraction. Raw binary64
failures are compared to actual native arrays; high precision is not claimed
to reproduce native overflow. Fresh replay CLIs deny Cells/BETSE/JAX imports;
they were not launched for ECM because the checks failed this round.

The original `signed_environment` stress case remains **failed**, with run02
reporting 39/40 checks passed. Actual/native full arrays agree before the failed
assertion, but `ledger.membrane_bulk_difference_mol_m3` exceeds the unchanged
independent concentration budget: absolute error 1.7448660538927198e-12,
fraction 5.816019768552954, against the 3e-13 floor plus 6e-12 relative term.
The supplied pump flux 5e5 produces large nearly equal cell/membrane values;
subtracting those values loses accuracy at the small diagnostic scale. This is
an observed accuracy failure, with conditioning as the diagnosis to review.
Neither the original case nor its panel is converted to a pass.

Run02 retains complete actual/native precomparison arrays for this failure.
Its 100/160-digit references were calculated before the failing assertion, but
the complete failed reference buffers were not separately retained. No numerical
reconstruction or audit was performed after Chief stopped further launches.
The separately named `low_inventory_signed_environment` scenario is prepared
statically with initial/bath concentration 1e-4 and pump flux10. It is additional
coverage, not a repair or refinement of the original stress case; it has no
completed qualification result.

Run03 launched just before Chief's stop message arrived. The retry was cancelled
under that interpretation, and Chief subsequently clarified that an already
active computation could finish; since cancellation had completed, no restart
was authorized. Partial evidence and the cancellation receipt are preserved.
No native/reference replay completed for ECM this round. Further numerical
launches and the saved02 evidence review await the next user instruction.
