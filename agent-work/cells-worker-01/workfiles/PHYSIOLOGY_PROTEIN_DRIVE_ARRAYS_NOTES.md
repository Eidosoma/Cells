# Array declared-drive energy admission

Chief assigned new kernel/reference/unit files only. Frozen conditional work,
chemical/electrical/projection and prior sources remain unchanged. Chief owns
shared status, provenance admission, integration and spatial gradients. CPU7
qualification is authorized at one thread,480s/phase,1GiB RSS and>=8GiB host
reserve. No GPU/fuel retry or mutable Root loop/schedule pin is allowed.

Public evaluate takes the complete frozen conditional-work inputs, scalar
float64 external_work_pJ and dissipated_free_energy_pJ, and a required static
nonempty budget_provenance. Recompute associated conditional work inside the
wrapper; no anonymous work receipt is admitted. Provenance declares a model
input, not authenticated authorship or evidence for a physical driving law.
Original material, source, field, parameter, SI geometry and work-precision
refusals propagate. External work is signed; declared dissipation is>=0.

The original host transition energy arithmetic is

    residual = sum(delta G, delta U, D_declared, -W_clamp, -W_external).

Compare the finite residual to the exact original absolute family tolerance:
2e-8pJ for passive/ionic,1e-9pJ for calcium/fuel. The caller cannot supply a
wider tolerance. A separate numerical addition/component bound is reported
and never added to the physical tolerance or substituted as an energy floor.

First subtract the two declarations using error-free two-sum, then grow a
fixed five-component expansion containing the actual chemical/capacitor/clamp
terms and both declaration-difference parts. Keep every remainder and raw term.
This preserves small work lost by naive addition of huge cancelling W/D.
Scale the64eps numerical bound before summing absolute terms, avoiding a false
overflow of the bound when finite maximum declarations exactly cancel.

Normal raw energies and a normal least-bit quantum are conservative precision
admission for backend error-free transforms: otherwise CPU flush-to-zero can
erase a subnormal intermediate remainder. Check exact binary significands;
small exact powers of two can pass. Equal declarations cancel before this
quantum check, so their irrelevant low bits do not force refusal. Preserve raw
IEEE values/payloads for invalid domain/overflow cases. This quantum guard may
refuse a host-arithmetic case that passes the physical tolerance; it never
widens that tolerance. Zero energy is not a substitute for an unresolved sum.

Qualification plan:52 NumPy+three CPU JAX checks;28 complete associated SI
forms and33 pure Decimal/host-arithmetic forms, with fresh Cells/JAX-denied
replay. Full-input cases cover all four ordinary families, initial/evolved
states, reordered/padded owners, unequal clamps/common shifts, signed work,
zero/reversal, tiny neutral residuals, huge equal declarations, missing work,
underlying work-precision refusals and stale source/geometry/budget domains.
Private arithmetic cases cover both signed inside/at/outside tolerance values,
deep cancellation, maximum declarations and normal/subnormal remainder guards.

Read the actual frozen transition.accept residual expression from its captured
AST and execute only that five-term math.fsum expression on associated numeric
components. This is host arithmetic credit, not proposal/loop acceptance.
Host/pure Decimal arithmetic comparison allows4ULP; independent SI/backend
endpoint comparison retains3e-14pJ+3e-10 relative. Tiny pure-chemical residual
comparison retains3e-14 relative+4ULP. Exact saved references must replay.

Compile checks are predeclared as separate resource-bounded phases because the
prior full conditional kernel peaked at1039994880B, close to1GiB. Two compiled
five-term budget kernels cover passive/calcium tolerance classes and invalid
batched declarations; a reduced one-cell/two-clamp full wrapper checks dynamic
protein/field/budget worlds and source/negative-dissipation refusal. Fixed ions,
P, geometry and controls are shared within that batch. No full-wrapper calcium,
fuel, compiled field-solve or performance credit is claimed.

This is energetic consistency of caller declarations. No physical heat/drive
law, stochastic draws, attainable protocol, state publication or accepted loop
is inferred.

## Qualified scope

All 55 checks pass on final sources: 52 NumPy and three separated CPU JAX
checks. The two budget kernels each cover 15 batched arithmetic worlds and
reject dynamic invalid declarations. The reduced full wrapper accepts its
two valid worlds, then refuses one stale protein source and one negative
dissipation declaration; the latter still passes the physical energy equation.
Compiled arithmetic matches frozen host sums exactly; full-wrapper backend
energy error consumes at most 9.035019e-7 of its declared comparison budget.

Fresh Cells/JAX-denied execution exactly replays all 61 reference forms:
28 complete SI and 33 pure Decimal/host-arithmetic cases, 48 admitted and
13 intentionally refused. Largest reference error consumes 0.011228430 of
its predeclared budget; NumPy five-term host arithmetic matches exactly.
Tiny neutral residuals survive declarations as large as finite float64 max.
The missing-work counterexample produces a naive zero but the retained
residual exceeds the original family tolerance, even though the separate
numerical bound is much larger. Neither that bound nor precision refusal
changes the original tolerance.

CPU7 phases took 18.12/4.54/7.06/7.06/38.57 s. Sampled peak 1002299392 B,
observed high-water 1008283648 B, minimum host reserve 20943396864 B.
Original limits pass; all 64 protected files and three owned source hashes
remain exact. No additional computation is running or queued.

Final receipt:
`/mnt/workspaces/Cells/physiology-protein-drive-arrays-tests-20261030-02/result.json`
SHA256 `ed012ece3a9cee707a7fed8e18425afad24e9a58ca542473640ba0b239fedd1b`.
Private source, inputs, per-case results, raw IEEE domain payloads, denied-import
replay, process logs and resource checks live beside it.

Run01 is preserved with 51 passing NumPy checks and one test-only failure:
Python3.13 built-in sum compensates floating addition, so the naive-zero
demonstration was incorrect. Only that demonstration changed to explicit
addition; kernel/reference/physical/numerical tolerances were unchanged.
Its failure receipt SHA256 is
`faf61338e4f95f3550c4a943f3926447d2a38f0802bc369b0ffdae6d4bc5a69a`.
Chief owns independent verification and shared integration/status.
