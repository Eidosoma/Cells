# Scoped native normal ion/material join

Chief approved a new no-ECM join and CPU1 qualification after B23. The source
contract retains actual ordered ion calls and complete intermediate states;
it does not compose the entire native FULL solver. Shared initialization,
depleted-fuel refinement, salt/water energy and temperature staging stay with
their assigned owners. All component/capture/reference/test files are new.

The selected native loop resets flux buffers, then runs membrane electroflux,
update_gj and update_intra per ordered moving ion. Final update_all_concs runs
update_Co, adds gap flux to bulk alone, then no_negs per ordered moving ion.
Each ordinary three-moving-ion call has20 full observed states: initial,
reset, nine flux/refresh stages and nine commit/clipping stages. No-moving-ion
calls have two. Twelve four-call histories therefore cover48 calls/888 states.

Every state includes bulk and membrane concentrations, scalar-per-ion bath,
membrane voltage, complete membrane/gap flux buffers, gap voltage and fields,
and gap opening. Binding pins original IDs, ownership/partner/boundary axes,
areas, volumes, lengths, normals, valences, diffusion, constants and flags.
Per-call drives supply explicit dt, runtime temperature and gap block. Source
configured temperature is separate. Published parent/candidate/trace arrays
are immutable; lineage, full raw inputs and every intermediate are retained.

Literal edge behavior matters. electroflux adds1e-25 in place to its voltage
argument. Membrane calls therefore mutate sim.vm once per moving ion. Gap
field is computed before the gap-voltage nonce. update_intra copies old bulk
after both flux calculations. update_Co refreshes membrane buffers after the
membrane exchange; later gap bulk changes and negative-bulk clipping do not
refresh those buffers. Signed finite membrane/bath values are retained for
the next call. The mixed bath is an unweighted membrane mean. Source no_negs
clips negative bulk, refuses NaN and can accept infinity. The component's
stricter finite guard preserves the complete actual refused trial.

Per-species ledgers retain membrane and gap transfer, clipping-created moles,
bulk/bath changes, source mixing residual and membrane/bulk disagreement.
They explain source arithmetic without inferring physical material, charge
or energy conservation. Source flux signs and all physical tolerances remain
unchanged. Pumps, events, networks, ECM, geometry mutation, voltage-sensitive
gap callbacks, field/voltage feedback and native initialization are excluded.

Qualification plans42 checks,15 isolated authenticated native captures and24
fresh independent reference forms. The native capture runs actual selected
loop statements and full called numerical bodies with read-only observations.
The reference independently carries Decimal owner sums and flux equations at
precisions90/140. Only in-place nonce stores round to binary64 explicitly.
Every complete stage array/dtype must match actual host source exactly;
independent errors use propagated gross scales and named per-unit floors.
Cases include neutral/zero-voltage nonce, temperature split, moving order,
stationary species, boundary masks, permutation, stale state, clipping, bath
depletion, asymmetric gap measures and actual NaN/overflow/infinity trials.

The established bounded supervisor enforces one CPU1 thread,480s maximum,
1GiB process-tree RSS and8GiB reserve. Source/native/runtime/import guards and
all raw failures are durable. Root explicitly announced eight shared source
edits; two occur in the historical124-file protection set (grid.py/specs.py).
Their historical hashes are retained, and122 other files remain protected.
Those shared files are not imported by the scientific component checks. The
frozen snapshot records their captured bytes independently; no historical
result or active job input is rewritten. Numerical result is tracked in the
own queue/receipt and sent to Chief for the shared PROGRESS.md update.
