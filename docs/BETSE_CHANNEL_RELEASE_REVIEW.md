# REF-004d: saved-input review with explicit bath remixing

D103, 2026-09-15. The user approved investigating D102's retained failure and
rechecking its saved evidence. This is a separate, versioned review, not an edit
to the failed capture, an automatic retry or a new simulator run.

## What failed and why

All 144 native phases / 288 single updates / 72 observer pairs completed without
warnings. The controller then rejected an exact-identity guard. The first
mismatch was a one-ULP K bath change after the zero-flux ordinary update.

The pinned BETSE `Simulator.update_all_concs` still calls `update_Co` for each
moving species when ordinary flux is zero. In the non-ECM shared-bath branch,
`update_Co` forms the per-face concentrations and takes their mean. A mean of
30 identical represented floats need not return that same float. The blocked
K channel also calls this updater, so it can remix once before the ordinary
updater remixes again; the operation need not be bitwise idempotent.

D102 incorrectly equated zero transport with exact bath-value identity across
these operations. Preserve that original failure and checker. The new contract
replaces only those outside-value identity assumptions with exact checks of the
actual source-defined reduction. **Input application itself still requires exact
state identity**, including cached flux, gates, inventories and numeric metadata.

## Source reconstruction and physical accounting

The installed NumPy version file identifies revision
`dd88c0c19b54ad9ed3533224221285bf0873249a`. Its
[primary reduction source](https://github.com/numpy/numpy/blob/dd88c0c19b54ad9ed3533224221285bf0873249a/numpy/_core/src/umath/loops_utils.h.src)
specifies the eight-accumulator reduction used for these short arrays. The
installed `_methods.py` defines mean as sum followed by division. Vendor the
revision-pinned reduction source and BSD license, bind their hashes, and also
bind the installed version, `_methods.py` and compiled reduction-library bytes.

`review_math.mean30` reconstructs that float64 operation order using standard
Python scalar arithmetic. It accepts only positive, finite, normal, length-30
float vectors in the specified range. Software tests cross-check it against the
actual pinned NumPy binary on 198 uniform, nonuniform and neighboring-float
vectors. This is source-arithmetic reconstruction, not a new transport equation
or a general NumPy implementation.

For each saved single update:

1. Empty-network export must leave all concentration arrays exactly unchanged.
2. Ordinary membrane and junction flux arrays must be zero. Cell and membrane
   concentrations must be exactly unchanged by their ordinary update.
3. Each of six outside species must equal the exact source-order mean of its
   prior 30-face bath vector, repeated across the native representation.
4. For blocked K transport, check its separate zero-flux mean at the channel
   boundary. Other channel-boundary species must remain exact. Check subsequent
   ordinary remixing against its own incoming values, not the previous step's.
5. Charge/voltage updates must not change any concentration array. Blocked cell
   inventories, membrane concentrations and final voltage remain exact; blocked
   flux/current remain exactly zero and intrinsic gates must continue evolving.

Record each of **1,776 zero-flux means**: 288 ordinary updates × six species,
plus 48 blocked K updates. Retain input/output concentrations, exact expected
mean, ULP difference and signed material residual. Fraction arithmetic computes
the residual from represented values without hiding it in a compensation term.
An independent forward-error bound checks the scale of roundoff, but **does not
replace exact source matching or serve as a widened acceptance epsilon**.

Use the original **2e-12 fmol** material budget for each remixing residual, in
addition to the unchanged whole-step six-species conservation checks. All
original gate, GHK flux, current, voltage, metadata, input-prefix, artifact,
observer, no-op and clock checks remain. A structural software test restricts
the versioned checker's changes to the documented boundaries, extra inventory
guard and evidence records. Captured numbers are never corrected or normalized.

## Preservation, coverage and execution

Authenticate D102's registration, source capsule, native worker and original
failure. Because the controller failed before making its final artifact
manifest, the new registration freezes the **605 existing files** at review
registration; do not claim a nonexistent original completion manifest. Explicit
membership checks cover six preparations, 144 complete case packets, logs and
native seed artifacts. Native pickles are hashed, never loaded.

Keep the original failure status and separately enumerate every original exact
guard rejection. The corrected review checks the whole 144-phase / 288-update /
288-input-application / 72-pair panel, not just the first mismatch. Short software
tests use eight representative saved rows; full review belongs to the detached
job. Its source capsule has **175 inputs**: 165 frozen D102 inputs plus ten new
review/document/source-attribution files. Model imports (Cells, BETSE, NumPy,
SciPy and JAX) are forbidden during the actual saved-data review.

Launch one detached review, CPUs 0–3, **180 seconds / 64 MiB aggregate artifacts /
32 MiB per file**. These are ceilings, not RAM allocation or runtime estimates.
Persist raw mean evidence, original rejected identities, comparison summary and
exclusive completion/failure receipts. Return without polling, automatic retry,
reference solve, simulator run or follow-up audit. Only an actual successful
receipt may say `release_input_preflight_review_closed`.

The qualified scope would still be parameter-only input application plus two
single updates per fresh phase. Query times are not elapsed simulation times;
a full-loop timed input hook, piecewise reference, 2 ms dynamic response and
their later audit remain separate gates. No biology, native restart or GPU claim.

## Architectural lesson

Keep transport ownership separate from representation operations such as bath
mixing. Zero physical flux does not guarantee bitwise identity after a floating-
point reduction. Preserve and account for that residual. This NumPy operation
order is a pinned native-validation detail, **not** a new production constraint
on Cells or future GPU reductions. Other backends must qualify their own
reduction behavior within physical error budgets and shared-stage accounting.
