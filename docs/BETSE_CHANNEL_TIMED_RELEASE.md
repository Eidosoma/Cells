# REF-004d: reference-gated timed block/release comparison

2026-09-16, D105. Validation-only work over unchanged accepted Cells production
and pinned BETSE v1.5.0. D104's [reference capture](../reports/REF004D_RELEASE_REFERENCE_CAPTURE.md)
passed; independently reviewing its saved evidence is the first gate of this
explicitly user-authorized job. Software checks are not full experiment results.

## Question and fixed scope

Can each simulator follow its own evolving amounts, capacitor voltage and m/h
through a transport block and release, with complete state continuity and a
resolvable response matching the independent reference?

Retain seven cells, one finite shared bath, K-only Kv1p5 at 298.15 K and matched
constants. Histories a = (0.2, 0.6) and b = (0.6, 0.2) have equal initial m*h,
not equal internal state. The duration is 2 ms; availability changes at 0.5 and
1 ms. No window extension or tolerance selection from simulator results.

| Condition | Availability | Intrinsic maximum permeability |
| --- | --- | --- |
| Baseline | 1 throughout | Positive and fixed |
| Explicit no-op | 1 / 1 / 1 | Positive and fixed |
| Static blocked | 0 throughout | Positive and fixed |
| Suppression/release | 1 / 0 / 1 | Positive and fixed |

No passive background leak, pump, junction, growth, chemistry, geometry change,
new model family, GPU execution or physiological inhibitor interpretation.

## First gate: independent saved-reference review

Authenticate all 34 D104 files, its 182 frozen inputs, runtime and prerequisite
chain. Replay the original saved checker unchanged, while independently
reconstructing both numerical columns for **1,485,380 scalar comparisons**.
Use the alternate audited RHS algebra, nested dense-polynomial basis and
endpoint free-energy calculation; check state carry, one-sided slopes,
analytic blocked gates, reference agreements and no-op comparisons. Independently
recompute the eight signal decisions and signed final history diagnostics.

This is saved-data verification, not a third ODE solve. No reference integration,
BETSE, Cells, NumPy, SciPy or JAX import is permitted in the controller/reviewer.
The reference worker's original float64 solution and 80-digit RHS arithmetic
remain correctly distinguished. Original receipts and failures are immutable.

Only a successful, hash-linked `reference-review-passed.json` permits either
simulator worker. A review failure stops the job before simulation. Workers
authenticate that gate independently; there is no ungated capture CLI.

## Native input and observation boundaries

Run the actual FULL INIT loop, retaining the previously qualified preparation.
A source-specific input hook assigns `maxDm = immutable_baseline * availability`
before the channel update for the selected **elapsed interval**. It never
multiplies the previously blocked value. Its assignment is separate from the
read-only observer; complete numeric state inventories must remain unchanged.

BETSE's inclusive printed loop labels are not elapsed step boundaries. Record
both; select input by integer/Decimal interval indices, never by those labels.
Do not change native clocks, gates, flux routines, methods or source files.
This is an external parameter input, not a built-in BETSE tissue/drug event.

The FULL loop evaluates six ordinary ion fluxes before the channel observation
boundary. Even with zero ordinary permeability, pinned `electroflux` adds its
1e-25 V numerical nonce to voltage in place on each call. Reconstruct these six
ordered additions exactly. The completed blocked-step voltage must equal the
previous completed voltage, not the intermediate nonce-shifted voltage. Keep
the existing physical error limits and direct-charge checks. This detail is
visible near the almost-zero initial voltage, not a new physical voltage source.

Retain D103's exact source-order zero-flux bath averaging, its local material
budget and original-identity diagnostics. Save individual remix records, not
only a summary. Amount conservation, gate-first ordering, one transfer owner,
current export, full native histories and observer noninterference remain checked.

Fresh switch currents are post-hoc evaluations on copied completed state, with
the left and right inputs separately. They are not the integrated current of
the interval just completed. Require that these probes leave native state intact.

## Cells and numerical comparison

Use existing data-defined availability schedules and unchanged CPU float64
checked RK4. Each interval holds its input through all RK stages. Observations
are right-continuous; explicit copied-state RHS/readout probes check both sides
of each switch. A transport block leaves gate kinetics active and preserves
accumulated material/energy exactly in this no-other-flux fixture.

Native timesteps: 25 / 12.5 / 6.25 microseconds, observed and unobserved pairs.
Cells timesteps: 50 / 25 / 12.5 microseconds compiled, plus 50 microseconds eager.
Resume each Cells condition/history at release (1 ms) on its 25 microsecond grid.
Keep all state, layout, ledgers and schedule position in the checkpoint.
Reconstruct the event index from the union of membrane, channel and junction
control times, right-continuously; the old constant-input event-zero assumption
does not apply to no-op or release checkpoints after their switches.

The full panel has **48 native phases / 8,960 updates / 96 input applications /
24 observer pairs**, **32 Cells trajectories / eight resumed segments** and
**48 checkpoints / 2,592 arrays**. Compare at 0, 0.25, 0.5, 0.75, 1, 1.25, 1.5
and 2 ms. Check complete histories, padding, absent mechanisms, thermodynamics,
eager/JIT and restart agreement, exact no-op neutrality, own-state constitutive
laws, finest-grid reference contact, two-step refinement and cross-engine contact.
Reuse the prior unit-specific budgets and refinement rule without modification.
Retain coarse diagnostic misses as failures in their own rows.

Compare signed a-minus-b trajectories for every condition: native/reference,
Cells/reference and cross-engine (12 groups), with the existing two-readout
and cross-engine contrast budgets. Do not require a positive biological memory
effect or select its sign. Independently auditing this new capture remains a
later user-directed task even if every capture check passes.

## Operational and architectural boundaries

Freeze the plan, validation sources, immutable prerequisites, handoff and passing
software receipts before one detached job: CPUs 0–3, **1,800 s total**, native
worker 480 s, Cells worker 600 s, **128 MiB per file / 512 MiB aggregate artifacts**.
These are storage limits, not small RAM allocations. Failures and partial logs
are durable. Never poll, retry, launch a follow-up audit/regression or revise a
registered source automatically. A pass is `timed_release_capture_pass_pending_audit`.

Production remains stable 0.14.0 / accepted development 0.15.0.dev0. Availability
is experiment data; gates and ledgers are explicit state; shared-bath coupling
uses consistent solver stages. Those general contracts remain suitable for
future batched/GPU work. Pinned native reduction and input-hook details stay in
validation adapters, not the production kernel or future multiscale interfaces.
